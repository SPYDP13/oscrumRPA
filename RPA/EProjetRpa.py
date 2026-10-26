import math
from urllib.parse import urljoin
from collections import defaultdict
from datetime import datetime

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

from RPA.capture import save_failure
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

    Progression notée dans chaque tâche (eprojet_id, done) et signalée par on_progress (enregistrement du plan) :
    une relance après échec ne recrée pas les tâches et ne ressaisit pas les heures déjà faites.
    Saisie incomplète (jour hors fenêtre, ligne introuvable) → exception en fin d'exécution.
    """

    ACTIVITY_PATH = "/timeSheetTacheParJour/activity"

    def __init__(self, task_list: list, on_progress=None):
        self.taskList = task_list
        self.on_progress = on_progress or (lambda: None)
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
            try:
                problems = self._run(page)
            except Exception:
                save_failure(page, "eprojet")
                raise
            finally:
                browser.close()

        if problems:
            raise RuntimeError("❌ Saisie incomplète — " + " ; ".join(problems) +
                               ". Le point de reprise n'avance pas et le plan est conservé : corrige-le (« Plan… » : "
                               "changer la date ou décocher la tâche) puis relance.")
        print("\n🎉 Tous les timesheets ont été remplis !")

    def _run(self, page: Page) -> list:
        self._login(page)

        # Jours ouverts à la saisie : une tâche hors fenêtre n'est pas créée (elle resterait sans heures)
        day_urls = self._day_urls(page)
        pending = [t for t in self.taskList if not t.get('done')]
        in_window = [t for t in pending if self._parse_day(t['date']).strftime("%d-%m-%Y") in day_urls]
        out_of_window = [t for t in pending if all(t is not w for w in in_window)]

        # Création des tâches
        for i, task in enumerate(in_window):
            print(f"\n[{i + 1}/{len(in_window)}] Création : {task['title']}")
            if task.get('eprojet_id'):
                print(f"  ↪ Déjà créée lors d'une exécution précédente (id={task['eprojet_id']})")
                continue
            self._create_task(page, task)
            self.on_progress()
            print(f"Tâche créée : {task['title']} (id={task.get('eprojet_id')})")

        print(f"\n🎉 {len(in_window)} tâche(s) prête(s) !")

        # Remplissage des timesheets
        missing = self.add_time_sheet(page, in_window, day_urls)

        problems = []
        if out_of_window:
            days = sorted({self._parse_day(t['date']) for t in out_of_window})
            problems.append(f"{len(out_of_window)} tâche(s) hors de la fenêtre de saisie E-PROJET (8 derniers jours) : "
                            + ", ".join(d.strftime('%d/%m/%Y') for d in days))
        if missing:
            problems.append(f"ligne introuvable dans le suivi quotidien pour : {', '.join(missing)}")
        return problems

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
        project_id = task.get('eprojet_project_id') or EPROJET_PROJECT_ID
        if not project_id:
            raise RuntimeError(f"❌ Aucun projet E-PROJET pour '{task['title']}' (projet par défaut non configuré)")
        self._select_bootstrap(page, "taches_projetId", project_id)
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
        try:
            option.wait_for(timeout=20000)
        except Exception:
            raise RuntimeError(f"❌ Responsable externe « {EPROJET_RESP_EXTERNE} » introuvable dans la liste de ce "
                               "projet E-PROJET : il n'est peut-être pas rattaché à ce projet") from None
        option.click()
        page.wait_for_timeout(300)

    # ─────────────────────────────────────────────────────────────
    def _select_bootstrap(self, page: Page, select_id: str, value: str):
        """Sélectionne une option d'un bootstrap-select en cliquant comme un utilisateur"""
        text = page.eval_on_selector(f"#{select_id}",
                                     "(s, v) => ([...s.options].find(o => o.value === v) || {text: ''}).text.trim()",
                                     str(value))
        if not text:
            raise RuntimeError(f"❌ Valeur « {value} » absente de la liste {select_id} dans E-PROJET "
                               "(projet ou type inaccessible avec ce compte ? Recharge les listes dans la configuration)")
        button = page.locator(f'button[data-id="{select_id}"]')
        button.click()
        menu = button.locator("xpath=..").locator(".dropdown-menu")
        menu.locator("li a span.text").get_by_text(text, exact=True).click()
        page.wait_for_timeout(300)

    # ─────────────────────────────────────────────────────────────
    def _day_urls(self, page: Page) -> dict:
        """Jours disponibles : {"16-10-2026": "/EProjet-1/timeSheetTacheParJour/activityByDay/395", ...}"""
        page.goto(f"{EPROJET_URL}{self.ACTIVITY_PATH}")
        return page.evaluate("""
        () => Object.fromEntries(
            [...document.querySelectorAll('#timeSheetTachePar_timeSheetJourId_tabActivityStarted option')]
                .map(o => [o.text.trim().split(' ').pop(), o.value]))
        """)

    # ─────────────────────────────────────────────────────────────
    def add_time_sheet(self, page: Page, task_list: list, day_urls: dict) -> list:
        """
        Reçoit une liste de tâches déjà schedulées (date + hours assignés), toutes dans la fenêtre de saisie.
        Groupe par jour et saisit les heures dans le suivi quotidien. Retourne les titres des lignes introuvables.
        """
        day_map = defaultdict(list)
        for task in task_list:
            day_map[self._parse_day(task['date'])].append(task)

        missing = []
        for dt in sorted(day_map.keys()):
            tasks_for_day = day_map[dt]
            total_h = round(sum(t['hours'] for t in tasks_for_day), 2)
            print(f"\n📅 {dt.strftime('%A %d %b')} → {total_h}h — {len(tasks_for_day)} tâche(s)")

            # url relative à l'hôte (elle contient déjà le chemin de l'application)
            page.goto(urljoin(EPROJET_URL, day_urls[dt.strftime("%d-%m-%Y")]))
            page.wait_for_selector("#timeSheetTacheParJourActivityUserByProjet")

            filled = []
            for task in tasks_for_day:
                if self._fill_timesheet_row(page, task, task['hours']):
                    filled.append(task)
                else:
                    missing.append(task['title'])

            if filled:
                page.click('#timeSheetTacheParJourActivityUserByProjet button[type="submit"]')
                page.wait_for_load_state("networkidle")
                for task in filled:
                    task['done'] = True
                self.on_progress()
                print(f"  ✅ Sauvegardé ({len(filled)} ligne(s))")
        return missing

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
