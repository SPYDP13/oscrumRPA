from playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from datetime import datetime
from collections import defaultdict

from config import OSCRUM_USERNAME, OSCRUM_PASSWORD, OSCRUM_PROJECT  # ← import depuis config



class OrangeScrumRpa:
    def __init__(self, task_list: list):
        self.taskList = task_list
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

            page.goto("https://orangescrum.synelia.tech/dashboard")
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

                page.click("text=Quick Task")
                page.fill("#inline_qktask", task["title"])
                page.evaluate(f"""
                () => {{
                    document.querySelector("#qt_due_dat").value = "{task['dateStr']}";
                    document.querySelector("#QT_due_dat").value = "{task['date']}";
                }}
                """)
                page.select_option("#qt_task_type", value="10")
                page.select_option("#quick-assign", value="289")
                page.click("#quickcase_qt")
                page.wait_for_selector("#new_task_label")
                page.wait_for_timeout(1000)
                print(f"Tâche créée : {task['title']}")

            print(f"\n🎉 {len(self.taskList)} tâche(s) créée(s) avec succès !")

            # Remplissage des timesheets
            self.add_time_sheet(page, self.taskList)

            browser.close()

    # ─────────────────────────────────────────────────────────────
    def add_time_sheet(self, page: Page, task_list: list):
        """
        Reçoit une liste de tâches déjà schedulées (date + hours assignés).
        Groupe par jour et remplit les timesheets.
        """
        if not task_list:
            print("❌ Aucune tâche à planifier")
            return

        # Grouper les tâches par jour
        day_map = defaultdict(list)
        for task in task_list:
            day_key = task['date'].split(' ')[0]  # "2026-5-4"
            day_map[day_key].append(task)

        def parse_day(s):
            p = s.split('-')
            return datetime(int(p[0]), int(p[1]), int(p[2]))

        page.goto("https://orangescrum.synelia.tech/timelog#/timesheet")
        page.wait_for_selector(".weakly-nav")

        current_week = None

        for day_str in sorted(day_map.keys(), key=parse_day):
            tasks_for_day = day_map[day_str]
            dt = parse_day(day_str)
            target_month_day = dt.strftime("%b %-d")  # "May 4"
            week = dt.isocalendar()[:2]

            # Naviguer vers la bonne semaine si elle change
            if week != current_week:
                self._navigate_to_week(page, target_month_day)
                current_week = week

            # Cliquer sur le jour exact
            day_spans = page.query_selector_all(".weakly-nav .day")
            for span in day_spans:
                if target_month_day in span.inner_text():
                    span.click()
                    page.wait_for_timeout(1500)
                    total_h = round(sum(t['hours'] for t in tasks_for_day), 1)
                    print(f"\n📅 {dt.strftime('%A %d %b')} → {total_h}h — {len(tasks_for_day)} tâche(s)")
                    break

            # Remplir chaque tâche avec ses heures assignées
            for task in tasks_for_day:
                self._fill_timesheet_row(page, task, task['hours'])

        print("\n🎉 Tous les timesheets ont été remplis !")

    # ─────────────────────────────────────────────────────────────
    def _navigate_to_week(self, page: Page, target_month_day: str):
        """Navigue vers la semaine contenant target_month_day, dans les 2 directions"""
        MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

        def parse_md(s):
            """Extrait (mois, jour) depuis 'May 4' ou 'Sunday\nApr 12'"""
            for word in s.replace('\n', ' ').split():
                if word[:3] in MONTHS:
                    idx = s.replace('\n', ' ').split().index(word)
                    parts = s.replace('\n', ' ').split()
                    try:
                        return MONTHS[word[:3]], int(parts[idx + 1])
                    except (IndexError, ValueError):
                        pass
            return 0, 0

        target_m, target_d = parse_md(target_month_day)
        max_clicks = 104
        clicks = 0

        while clicks < max_clicks:
            day_spans = page.query_selector_all(".weakly-nav .day")
            week_dates = [s.inner_text().strip() for s in day_spans]

            if any(target_month_day in d for d in week_dates):
                print(f"  ✅ Semaine trouvée pour {target_month_day} ({clicks} clic(s))")
                return

            # Détecter la direction : comparer avec le premier jour visible
            direction = "prev"
            for wd in week_dates:
                curr_m, curr_d = parse_md(wd)
                if curr_m > 0:
                    direction = "next" if (target_m, target_d) > (curr_m, curr_d) else "prev"
                    break

            selector = ".timesheet_sp.next" if direction == "next" else ".timesheet_sp.prev"
            page.click(selector)
            page.wait_for_timeout(800)
            clicks += 1

        print(f"  ❌ Semaine non trouvée pour {target_month_day}")

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
