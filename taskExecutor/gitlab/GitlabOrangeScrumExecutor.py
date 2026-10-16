from taskProvider.gitlab.gitlabLogExtrator import GitlabLogExtractor
from taskProvider.gitlab.syncState import save_last_since, save_last_run
from taskProvider.outlook.outlookCalendarExtractor import OutlookCalendarExtractor
from config import EXCHANGE_EMAIL, EXCHANGE_PASSWORD, TASK_SOURCE, TIMESHEET_TARGET
from taskRefinings.AutoTaskScheduleRefiner import AutoTaskScheduleRefiner
from taskRefinings.factory import get_refiner_class

class GitlabOrangeScrumExecutor:
    def __init__(self, since: str = None, until: str = None):
        """since / until : période imposée (rattrapage). Sinon : depuis la dernière synchro jusqu'à aujourd'hui."""
        self.taskList = []
        self.custom_period = bool(since or until)
        self.extractor = GitlabLogExtractor(since=since, until=until)

    def init_task_list(self):
        # 1. Source des tâches (TASK_SOURCE dans .env) : commits GitLab, réunions Outlook, ou les deux
        print(f"📥 Source des tâches : {TASK_SOURCE}")
        tasks = []
        if TASK_SOURCE in ("gitlab", "both"):
            tasks = self.extractor.get_gitlab_commit_log()

        meetings = []
        if TASK_SOURCE in ("outlook", "both"):
            if not (EXCHANGE_EMAIL and EXCHANGE_PASSWORD):
                raise ValueError("TASK_SOURCE inclut outlook mais EXCHANGE_EMAIL / EXCHANGE_PASSWORD sont vides dans .env")
            meetings = OutlookCalendarExtractor(since=self.extractor.params["since"],
                                                until=self.extractor.params["until"]).get_meetings()

        # 2. Analyse IA (TASK_REFINER dans .env : claude, gemini ou mistral) : titres, jours et heures
        refiner_class = get_refiner_class()
        analyser = refiner_class(commits=tasks, since=self.extractor.params["since"], until=self.extractor.params["until"],
                                 meetings=meetings)
        self.taskList = analyser.execute()

        for c in self.taskList:
            print(f"title  : {c['title']}")
            print(f"dateStr: {c['dateStr']}")
            print(f"date   : {c['date']}")
            print(f"author : {c['author']}")
            print(f"project: {c['project_id']}")
            print(f"hours  : {c['hours']}")
            print(f"original_commits: {c['original_commits']}")
            print("-" * 50)

        #Pour repartire les taches de maniere automatique et aleatoir (40h par semaine) utiliser AutoTaskScheduleRefiner.schedule
        # scheduler = AutoTaskScheduleRefiner()
        # scheduler.schedule(tasks=self.taskList, since=self.extractor.params["since"], until=self.extractor.params["until"])

    def execute(self):
        if self.taskList:
            # Plateforme de timesheet (TIMESHEET_TARGET dans .env) : E-PROJET ou OrangeScrum
            if TIMESHEET_TARGET == "orangescrum":
                from RPA.OrangeScrumRpa import OrangeScrumRpa
                rpa = OrangeScrumRpa(self.taskList)
            else:
                from RPA.EProjetRpa import EProjetRpa
                rpa = EProjetRpa(self.taskList)
            rpa.create_tasks()
        else:
            print("ℹ️ Aucune tâche à saisir sur la période")

        # Une période imposée (rattrapage) ne touche ni au point de reprise ni à l'exécution du jour
        if self.custom_period:
            return

        # Une fois les tâches et timesheets créées avec succès, on mémorise le point d'arrêt
        # pour que le prochain lancement reprenne automatiquement à partir de cette date,
        # ainsi que la date du jour (les exécutions programmées de la journée sont alors sautées).
        save_last_since(self.extractor.params["until"])
        save_last_run()
