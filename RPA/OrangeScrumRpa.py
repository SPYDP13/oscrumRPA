from playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from datetime import date, datetime
from collections import defaultdict

from RPA.capture import save_failure
from config import (OSCRUM_URL, OSCRUM_USERNAME, OSCRUM_PASSWORD, OSCRUM_PROJECT,  # ← import depuis config
                    OSCRUM_TASK_TYPE_ID, OSCRUM_ASSIGNEE_ID)
from dateformat import month_day

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def parse_day_label(text: str, near: date):
    """'May 4' ou 'Sunday\\nApr 12' → date. L'écran n'affiche pas l'année : on prend celle qui place le jour au plus
    près de near (fin décembre / début janvier dans la même semaine). None si illisible."""
    parts = text.replace('\n', ' ').split()
    for idx, word in enumerate(parts):
        if word[:3] in MONTHS:
            try:
                month, day = MONTHS[word[:3]], int(parts[idx + 1])
                candidates = [date(y, month, day) for y in (near.year - 1, near.year, near.year + 1)]
            except (IndexError, ValueError):
                continue
            return min(candidates, key=lambda d: abs((d - near).days))
    return None


class OrangeScrumRpa:
    """Progression notée dans chaque tâche (oscrum_created, done) et signalée par on_progress (enregistrement du
    plan) : une relance après échec ne recrée pas les tâches. Jour introuvable → exception en fin d'exécution."""

    def __init__(self, task_list: list, on_progress=None):
        self.taskList = task_list
        self.on_progress = on_progress or (lambda: None)
        print("====== Les taches a ajouter =====")
        for task in self.taskList:
            print(f"title  : {task['title']}")
            print(f"dateStr: {task['dateStr']}")
            print(f"date   : {task['date']}")
            print(f"author : {task['author']}")
            print("-" * 50)

    def create_tasks(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            try:
                missing_days = self._run(page)
            except Exception:
                save_failure(page, "orangescrum")
                raise
            finally:
                browser.close()

        if missing_days:
            raise RuntimeError(f"❌ Saisie incomplète — jour(s) introuvable(s) dans la timesheet OrangeScrum : "
                               f"{', '.join(d.strftime('%d/%m/%Y') for d in missing_days)}. Le point de reprise "
                               f"n'avance pas et le plan est conservé : relance pour reprendre.")
        print("\n🎉 Tous les timesheets ont été remplis !")

    def _run(self, page: Page) -> list:
        page.goto(f"{OSCRUM_URL}/dashboard")
        page.fill("#email", OSCRUM_USERNAME)
        page.fill("#password", OSCRUM_PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_selector("#new_task_label")
        print("Connexion réussie")

        # ── Sélection du projet
        print(f"Sélection du projet : {OSCRUM_PROJECT}")

        # Ouvrir le dropdown projet
        page.click("#prj_ahref")
        page.wait_for_timeout(800)

        # .ttc exclut le lien "All" — cible uniquement les vrais liens projet
        page.click(f'.proj_lnks.ttc:has-text("{OSCRUM_PROJECT}")')
        page.wait_for_timeout(1500)  # Attendre le rechargement du dashboard sur ce projet

        print(f"Projet sélectionné : {OSCRUM_PROJECT}")

        # Création des tâches
        for i, task in enumerate(self.taskList):
            print(f"\n[{i + 1}/{len(self.taskList)}] Création : {task['title']}")
            if task.get("oscrum_created"):
                print("  ↪ Déjà créée lors d'une exécution précédente")
                continue

            page.click("text=Quick Task")
            page.fill("#inline_qktask", task["title"])
            page.evaluate("""
            ([dateStr, date]) => {
                document.querySelector("#qt_due_dat").value = dateStr;
                document.querySelector("#QT_due_dat").value = date;
            }
            """, [task['dateStr'], task['date']])
            page.select_option("#qt_task_type", value=str(OSCRUM_TASK_TYPE_ID))
            page.select_option("#quick-assign", value=str(OSCRUM_ASSIGNEE_ID))
            page.click("#quickcase_qt")
            page.wait_for_selector("#new_task_label")
            page.wait_for_timeout(1000)
            task["oscrum_created"] = True
            self.on_progress()
            print(f"Tâche créée : {task['title']}")

        print(f"\n🎉 {len(self.taskList)} tâche(s) créée(s) avec succès !")

        # Remplissage des timesheets
        return self.add_time_sheet(page, [t for t in self.taskList if not t.get("done")])

    # ─────────────────────────────────────────────────────────────
    def add_time_sheet(self, page: Page, task_list: list) -> list:
        """
        Reçoit une liste de tâches déjà schedulées (date + hours assignés).
        Groupe par jour et remplit les timesheets. Retourne les jours introuvables.
        """
        if not task_list:
            return []

        # Grouper les tâches par jour
        day_map = defaultdict(list)
        for task in task_list:
            p = task['date'].split(' ')[0].split('-')  # "2026-5-4"
            day_map[date(int(p[0]), int(p[1]), int(p[2]))].append(task)

        page.goto(f"{OSCRUM_URL}/timelog#/timesheet")
        page.wait_for_selector(".weakly-nav")

        current_week = None
        missing_days = []

        for day in sorted(day_map):
            tasks_for_day = day_map[day]
            dt = datetime(day.year, day.month, day.day)
            week = day.isocalendar()[:2]

            # Naviguer vers la bonne semaine si elle change
            if week != current_week:
                self._navigate_to_week(page, day)
                current_week = week

            # Cliquer sur le jour exact
            if not self._select_day(page, day):
                missing_days.append(day)
                continue

            total_h = round(sum(t['hours'] for t in tasks_for_day), 1)
            print(f"\n📅 {dt.strftime('%A %d %b')} → {total_h}h — {len(tasks_for_day)} tâche(s)")

            # Remplir chaque tâche avec ses heures assignées
            for task in tasks_for_day:
                # Certains écrans reviennent sur la date du jour après sauvegarde
                self._select_day(page, day)
                self._fill_timesheet_row(page, task, task['hours'])
                task["done"] = True
                self.on_progress()

        return missing_days

    # ─────────────────────────────────────────────────────────────
    def _visible_days(self, page: Page, near: date) -> list:
        return [(span, parse_day_label(span.inner_text(), near)) for span in page.query_selector_all(".weakly-nav .day")]

    # ─────────────────────────────────────────────────────────────
    def _navigate_to_week(self, page: Page, target: date):
        """Navigue vers la semaine contenant target, dans les 2 directions"""
        max_clicks = 104
        clicks = 0

        while clicks < max_clicks:
            days = [d for _, d in self._visible_days(page, target) if d]

            if target in days:
                print(f"  ✅ Semaine trouvée pour {month_day(target)} ({clicks} clic(s))")
                return

            if not days:
                print("  ❌ Impossible de lire les jours visibles")
                return

            if target < days[0]:
                direction = "prev"
            elif target > days[-1]:
                direction = "next"
            else:
                print(f"  ⚠️ La date {month_day(target)} semble dans la plage visible mais non détectée")
                return

            selector = ".timesheet_sp.next" if direction == "next" else ".timesheet_sp.prev"
            page.click(selector)
            page.wait_for_timeout(800)
            clicks += 1

        print(f"  ❌ Semaine non trouvée pour {month_day(target)}")

    # ─────────────────────────────────────────────────────────────
    def _hours_to_str(self, h: float) -> str:
        """Convertit 2.5 → '02:30'"""
        total_minutes = int(h * 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

    # ─────────────────────────────────────────────────────────────
    def _fill_timesheet_row(self, page: Page, task: dict, hours: float = 2.0):
        print(f"  ➕ {task['title']} ({self._hours_to_str(hours)})")

        # Ouvrir "Add line item" si visible
        add_line_btn = page.query_selector("td.add_line_item")
        if add_line_btn and add_line_btn.is_visible():
            add_line_btn.click()
            page.wait_for_timeout(1000)
        else:
            print("  ⚠️ 'Add line item' non visible, on continue...")

        # ── Projet ──────────────────────────────────────────────
        page.click('[ng-model="projectM.selected"] .select2-choice')
        page.wait_for_timeout(500)
        page.fill('[ng-model="projectM.selected"] .ui-select-search', OSCRUM_PROJECT)
        page.wait_for_timeout(800)
        page.click(f'li.ui-select-choices-row:has(div[title="{OSCRUM_PROJECT}"])')
        page.wait_for_timeout(1000)

        # ── Tâche ───────────────────────────────────────────────
        page.click('[ng-model="taskM.selected"] .select2-choice')
        page.wait_for_timeout(500)
        page.fill('[ng-model="taskM.selected"] .ui-select-search', task['title'])
        page.wait_for_timeout(1000)
        page.click('#ui-select-choices-2 li.ui-select-choices-row:first-child')
        page.wait_for_timeout(500)

        # ── Heures ──────────────────────────────────────────────
        page.fill('#ngh', self._hours_to_str(hours))
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")

        # ── Sauvegarde ──────────────────────────────────────────
        page.click('#btnSave')
        page.wait_for_timeout(2000)

        print(f"  ✅ Sauvegardé : {task['title']} — {self._hours_to_str(hours)}")

    # ─────────────────────────────────────────────────────────────
    def _select_day(self, page: Page, target: date) -> bool:
        """Sélectionne un jour visible dans la semaine courante."""
        for span, day in self._visible_days(page, target):
            if day == target:
                span.click()
                page.wait_for_timeout(1500)
                return True

        print(f"  ⚠️ Jour non trouvé dans la semaine visible : {month_day(target)}")
        return False
