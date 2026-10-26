import os

import plan_store
from taskProvider.gitlab.gitlabLogExtrator import GitlabLogExtractor
from taskProvider.gitlab.syncState import save_last_since, save_last_run
from taskProvider.outlook.outlookCalendarExtractor import OutlookCalendarExtractor
from config import EPROJET_PROJECT_ID, EXCHANGE_EMAIL, EXCHANGE_PASSWORD, TASK_SOURCE, TIMESHEET_TARGET
from taskRefinings.factory import get_refiner_class

class GitlabOrangeScrumExecutor:
    def __init__(self, since: str = None, until: str = None):
        """since / until : période imposée (rattrapage). Sinon : depuis la dernière synchro jusqu'à aujourd'hui."""
        self.taskList = []
        self.plan = None
        self.custom_period = bool(since or until)
        self.extractor = GitlabLogExtractor(since=since, until=until)

    def init_task_list(self):
        since, until = self.extractor.params["since"], self.extractor.params["until"]

        # Plan en attente (aperçu éventuellement corrigé, ou exécution interrompue) : saisi tel quel, sans rappeler l'IA
        pending = plan_store.load()
        if plan_store.reusable(pending, since, until, self.custom_period):
            print(f"📋 Plan en attente repris (créé le {pending['created'].replace('T', ' à ')}"
                  f"{', validé' if pending.get('validated') else ''}) — pas de nouvel appel à l'IA")
            self.plan = pending
        else:
            if pending:
                print("⚠️ Plan en attente d'une autre période (ou ancien aperçu) remplacé"
                      + (" — des tâches en avaient déjà été créées dans le timesheet" if plan_store.has_progress(pending) else ""))
            self.plan = plan_store.new(since, until, self.custom_period, self._generate(since, until))
            plan_store.save(self.plan)

        self.taskList = [t for t in self.plan["tasks"] if t.get("include", True)]
        for c in self.taskList:
            print(f"title  : {c['title']}")
            print(f"dateStr: {c['dateStr']}")
            print(f"date   : {c['date']}")
            print(f"author : {c['author']}")
            print(f"project: {c['project_id']} → E-PROJET {c.get('eprojet_project_id') or '?'}"
                  f"{' (non classé)' if c.get('unmapped') else ''}")
            print(f"hours  : {c['hours']}")
            print(f"original_commits: {c['original_commits']}")
            print("-" * 50)
        for c in self.plan["tasks"]:
            if not c.get("include", True):
                print(f"⏭  écartée : {c['title']} [{c['hours']}h] {c.get('conflict', '')}")

    def _generate(self, since: str, until: str) -> list:
        # 1. Source des tâches (TASK_SOURCE dans .env) : commits GitLab, réunions Outlook, ou les deux
        print(f"📥 Source des tâches : {TASK_SOURCE}")
        tasks = []
        if TASK_SOURCE in ("gitlab", "both"):
            tasks = self.extractor.get_gitlab_commit_log()

        meetings = []
        if TASK_SOURCE in ("outlook", "both"):
            if not (EXCHANGE_EMAIL and EXCHANGE_PASSWORD):
                raise ValueError("TASK_SOURCE inclut outlook mais EXCHANGE_EMAIL / EXCHANGE_PASSWORD sont vides dans .env")
            meetings = OutlookCalendarExtractor(since=since, until=until).get_meetings()

        # 2. Heures (8 h / jour, calculées) puis libellés rédigés par l'IA (TASK_REFINER : claude, gemini, mistral)
        refiner_class = get_refiner_class()
        refiner = refiner_class(commits=tasks, since=since, until=until, meetings=meetings)
        result = refiner.execute()
        if refiner.unmapped_repos and os.environ.get("RPA_SCHEDULED"):
            from notifier import notify
            notify("RPA Timesheet — dépôts à classer",
                   f"{len(refiner.unmapped_repos)} dépôt(s) saisi(s) dans le projet par défaut : "
                   + ", ".join(r.rsplit('/', 1)[-1] for r in refiner.unmapped_repos[:5])
                   + ". Ajoute une règle dans « Correspondances ».")
        return result

    def execute(self):
        if TIMESHEET_TARGET == "eprojet":
            orphans = [t["title"] for t in self.taskList if not plan_store.started(t)
                       and not (t.get("eprojet_project_id") or EPROJET_PROJECT_ID)]
            if orphans:
                raise RuntimeError(f"❌ {len(orphans)} tâche(s) sans projet E-PROJET (ex. « {orphans[0]} ») : choisis un "
                                   "projet par défaut (Configuration → Timesheet) ou complète le plan (« Plan… »).")
        if self.taskList:
            # Plateforme de timesheet (TIMESHEET_TARGET dans .env) : E-PROJET ou OrangeScrum.
            # La progression est enregistrée dans le plan au fil de l'eau (reprise après échec).
            if TIMESHEET_TARGET == "orangescrum":
                from RPA.OrangeScrumRpa import OrangeScrumRpa
                rpa = OrangeScrumRpa(self.taskList, on_progress=lambda: plan_store.save(self.plan))
            else:
                from RPA.EProjetRpa import EProjetRpa
                rpa = EProjetRpa(self.taskList, on_progress=lambda: plan_store.save(self.plan))
            rpa.create_tasks()  # lève une exception si la saisie est incomplète : plan conservé
        else:
            print("ℹ️ Aucune tâche à saisir sur la période")
        plan_store.clear()

        # Une période imposée (rattrapage) ne touche ni au point de reprise ni à l'exécution du jour
        if self.custom_period:
            return

        # Une fois les tâches et timesheets créées avec succès, on mémorise le point d'arrêt
        # pour que le prochain lancement reprenne automatiquement à partir de cette date,
        # ainsi que la date du jour (les exécutions programmées de la journée sont alors sautées).
        save_last_since(self.plan["until"])
        save_last_run()
