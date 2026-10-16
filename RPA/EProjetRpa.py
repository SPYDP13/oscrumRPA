import math
from collections import defaultdict
from datetime import datetime

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

from config import (EPROJET_URL, EPROJET_USERNAME, EPROJET_PASSWORD, EPROJET_PROJECT_ID,
                    EPROJET_RESP_EXTERNE, EPROJET_TYPE_TACHE_ID, EPROJET_STATUT_TACHE_ID,
                    EPROJET_STATUT_TERMINEE_ID)


class EProjetRpa:
    """
    RPA pour la plateforme E-PROJET (remplace OrangeScrum).

    Flux :
      1. Connexion (formulaire Spring Security)
      2. Pour chaque tâche : "Ajouter une tâche" → formulaire /taches/useform
      3. "Suivi quotidien des tâches" : pour chaque jour, saisie des heures sur la ligne de la tâche
         ⚠️ La plateforme ne propose que les 8 derniers jours (aujourd'hui inclus).
    """

    ACTIVITY_PATH = "/timeSheetTacheParJour/activity"

    def __init__(self, task_list: list):
        self.taskList = task_list
        print("====== Les taches a ajouter =====")
        for task in self.taskList:
            print(f"title  : {task['title']}")
            print(f"date   : {task['date']}")
            print(f"hours  : {task['hours']}")
            print(f"author : {task['author']}")
            print("-" * 50)

    def create_tasks(self):

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            self._login(page)

            # Création des tâches
            for i, task in enumerate(self.taskList):
                print(f"\n[{i + 1}/{len(self.taskList)}] Création : {task['title']}")
                self._create_task(page, task)
                print(f"Tâche créée : {task['title']} (id={task.get('eprojet_id')})")

            print(f"\n🎉 {len(self.taskList)} tâche(s) créée(s) avec succès !")

            # Remplissage des timesheets
            self.add_time_sheet(page, self.taskList)

            browser.close()

    # ─────────────────────────────────────────────────────────────
    def _login(self, page: Page):
        page.goto(f"{EPROJET_URL}/login")
        page.fill('#loginForm input[name="username"]', EPROJET_USERNAME)
        page.fill('#loginForm input[name="password"]', EPROJET_PASSWORD)
        page.click('#loginForm button[type="submit"]')
        page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            raise RuntimeError("❌ Connexion E-PROJET échouée (identifiants ?)")
        print("Connexion réussie")

    # ─────────────────────────────────────────────────────────────
    def _create_task(self, page: Page, task: dict):
        day = self._parse_day(task['date'])
        day_fr = day.strftime("%d/%m/%Y")
        hours = self._round_quarter(task['hours'])
        days = max(0.25, math.ceil(hours / 8 * 4) / 4)  # min 0.25 j, pas de 0.25

        page.goto(f"{EPROJET_URL}{self.ACTIVITY_PATH}")
        page.wait_for_load_state("networkidle")

        # Tâche déjà créée lors d'un lancement précédent interrompu → on la réutilise
        existing_id = self._find_task_id(page, task['title'])
        if existing_id:
            task['eprojet_id'] = existing_id
            print("  ↪ Déjà présente dans E-PROJET, création ignorée")
            return

        # Le formulaire n'est accessible que via le bouton (un accès direct redirige)
        page.click("a.ts-btn-ajouter")
        page.wait_for_load_state("networkidle")

        # ── Projet : sélection "à la main" pour que la page charge les champs qui en dépendent
        self._select_bootstrap(page, "taches_projetId", EPROJET_PROJECT_ID)
        page.wait_for_load_state("networkidle")
        page.wait_for_function("document.querySelectorAll('#taches_statutTacheId option').length > 1")
        page.wait_for_timeout(500)

        # ── Champs simples
        page.fill("#taches_libelle", task['title'])
        page.select_option("#taches_natureTache", value="TACHE")
        self._select_bootstrap(page, "taches_typeTacheId", task.get('type_tache_id', EPROJET_TYPE_TACHE_ID))
        page.check('input[name="tacheInterne"][value="false"]')
        page.select_option("#taches_statutTacheId", value=str(EPROJET_STATUT_TACHE_ID))

        # ── Responsable externe (select2 avec recherche asynchrone)
        self._select_resp_externe(page)

        # ── Dates (bootstrap-datepicker, format dd/mm/yyyy)
        page.evaluate("""
        d => {
            jQuery('#taches_dateDebutPrev').datepicker('update', d);
            jQuery('#taches_dateFinPrev').datepicker('update', d);
        }
        """, day_fr)

        # ── Charge prévue
        page.fill("#taches_nbJourPrev", str(days))
        page.fill("#taches_nbHeurePrev", str(hours))

        # ── Sauvegarde → redirige vers le suivi quotidien
        page.click('#taches button[type="submit"]')
        page.wait_for_load_state("networkidle")

        if self.ACTIVITY_PATH not in page.url:
            error = page.inner_text(".alert-danger") if page.query_selector(".alert-danger") else "inconnue"
            raise RuntimeError(f"❌ Création échouée pour '{task['title']}' : {error}")

        # Mémoriser l'id de la tâche créée (la plus récente portant ce titre)
        task['eprojet_id'] = self._find_task_id(page, task['title'])

    # ─────────────────────────────────────────────────────────────
    def _find_task_id(self, page: Page, title: str):
        """Id de la tâche active la plus récente portant ce titre (page suivi quotidien), sinon None"""
        return page.evaluate("""
        title => {
            const ids = [...document.querySelectorAll('input[name^="listTaches["][name$="].libelle"]')]
                .filter(i => i.value === title)
                .map(i => Number(document.getElementsByName(i.name.replace('.libelle', '.id'))[0].value));
            return ids.length ? Math.max(...ids) : null;
        }
        """, title)

    # ─────────────────────────────────────────────────────────────
    def _select_resp_externe(self, page: Page):
        """La liste se charge en asynchrone à l'ouverture : attendre qu'elle soit remplie avant de chercher"""
        results = ".select2-container--open .select2-results__option"
        loaded = f"{results}:not(.loading-results)"

        page.click("#taches_responsableExterneId + .select2 .select2-selection")
        page.wait_for_selector(loaded)
        page.wait_for_load_state("networkidle")

        page.locator(".select2-container--open .select2-search__field").press_sequentially(
            EPROJET_RESP_EXTERNE, delay=50)
        option = page.locator(loaded).get_by_text(EPROJET_RESP_EXTERNE, exact=True)
        option.wait_for()
        option.click()
        page.wait_for_timeout(300)

    # ─────────────────────────────────────────────────────────────
    def _select_bootstrap(self, page: Page, select_id: str, value: str):
        """Sélectionne une option d'un bootstrap-select en cliquant comme un utilisateur"""
        text = page.eval_on_selector(f"#{select_id}",
                                     "(s, v) => [...s.options].find(o => o.value === v).text.trim()",
                                     str(value))
        button = page.locator(f'button[data-id="{select_id}"]')
        button.click()
        menu = button.locator("xpath=..").locator(".dropdown-menu")
        menu.locator("li a span.text").get_by_text(text, exact=True).click()
        page.wait_for_timeout(300)

    # ─────────────────────────────────────────────────────────────
    def add_time_sheet(self, page: Page, task_list: list):
        """
        Reçoit une liste de tâches déjà schedulées (date + hours assignés).
        Groupe par jour et saisit les heures dans le suivi quotidien.
        """
        if not task_list:
            print("❌ Aucune tâche à planifier")
            return

        # Grouper les tâches par jour
        day_map = defaultdict(list)
        for task in task_list:
            day_map[self._parse_day(task['date'])].append(task)

        # Jours disponibles : {"16-10-2026": "/EProjet-1/timeSheetTacheParJour/activityByDay/395", ...}
        page.goto(f"{EPROJET_URL}{self.ACTIVITY_PATH}")
        day_urls = page.evaluate("""
        () => Object.fromEntries(
            [...document.querySelectorAll('#timeSheetTachePar_timeSheetJourId_tabActivityStarted option')]
                .map(o => [o.text.trim().split(' ').pop(), o.value]))
        """)

        skipped = []
        for dt in sorted(day_map.keys()):
            tasks_for_day = day_map[dt]
            url = day_urls.get(dt.strftime("%d-%m-%Y"))
            if not url:
                skipped.append(dt)
                print(f"\n⚠️ {dt.strftime('%A %d %b')} hors de la fenêtre de saisie E-PROJET, ignoré")
                continue

            total_h = round(sum(t['hours'] for t in tasks_for_day), 2)
            print(f"\n📅 {dt.strftime('%A %d %b')} → {total_h}h — {len(tasks_for_day)} tâche(s)")

            page.goto(f"{EPROJET_URL.split('/EProjet-1')[0]}{url}")
            page.wait_for_selector("#timeSheetTacheParJourActivityUserByProjet")

            filled = 0
            for task in tasks_for_day:
                if self._fill_timesheet_row(page, task, task['hours']):
                    filled += 1

            if filled:
                page.click('#timeSheetTacheParJourActivityUserByProjet button[type="submit"]')
                page.wait_for_load_state("networkidle")
                print(f"  ✅ Sauvegardé ({filled} ligne(s))")

        if skipped:
            print(f"\n⚠️ {len(skipped)} jour(s) non saisi(s) (plus de 7 jours) : "
                  f"{', '.join(d.strftime('%d/%m/%Y') for d in skipped)}")
        print("\n🎉 Tous les timesheets ont été remplis !")

    # ─────────────────────────────────────────────────────────────
    def _fill_timesheet_row(self, page: Page, task: dict, hours: float) -> bool:
        hours = self._round_quarter(hours)
        print(f"  ➕ {task['title']} ({hours}h)")

        # Ligne retrouvée par id de tâche (sinon par titre), dans le tableau des tâches actives
        name = page.evaluate("""
        ([id, title]) => {
            const form = document.getElementById('timeSheetTacheParJourActivityUserByProjet');
            const match = [...form.querySelectorAll('input[name^="listTaches["][name$="].id"]')]
                .find(i => id ? i.value === String(id)
                              : form.elements[i.name.replace('.id', '.libelle')].value === title);
            return match ? match.name.replace('.id', '') : null;
        }
        """, [task.get('eprojet_id'), task['title']])

        if not name:
            print(f"  ⚠️ Ligne introuvable pour : {task['title']}")
            return False

        # Heures du jour + clôture de la tâche (Terminée, 100 %)
        page.fill(f'input[name="{name}.nbHeureTravaille"]', str(hours))
        page.select_option(f'select[name="{name}.statutTacheId"]', value=EPROJET_STATUT_TERMINEE_ID)
        page.fill(f'input[name="{name}.pourcentageAvanc"]', "100")
        return True

    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_day(s: str) -> datetime:
        """'2026-5-4' ou '2026-5-4 09:00:00' → datetime(2026, 5, 4)"""
        p = s.split(' ')[0].split('-')
        return datetime(int(p[0]), int(p[1]), int(p[2]))

    @staticmethod
    def _round_quarter(h: float) -> float:
        """Les champs heures n'acceptent que des pas de 0.25"""
        return max(0.25, round(h * 4) / 4)
