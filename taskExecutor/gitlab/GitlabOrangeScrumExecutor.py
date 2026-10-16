from taskProvider.gitlab.gitlabLogExtrator import GitlabLogExtractor
from taskProvider.gitlab.syncState import save_last_since
from taskProvider.outlook.outlookCalendarExtractor import OutlookCalendarExtractor
from config import EXCHANGE_EMAIL, EXCHANGE_PASSWORD, TASK_SOURCE
from RPA.EProjetRpa import EProjetRpa
from taskRefinings.AutoTaskScheduleRefiner import AutoTaskScheduleRefiner
from taskRefinings.GeminiTaskRefiner import GeminiTaskRefiner
from taskRefinings.MistralTaskRefiner import MistralTaskRefiner
from taskRefinings.ClaudeTaskRefiner import ClaudeTaskRefiner

class GitlabOrangeScrumExecutor:
    def __init__(self):
        pass
        self.taskList = []
        self.extractor = GitlabLogExtractor()

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

        # 2. Analyse et refactorisation avec Gemini (determine date et hours pour la tache)
        # analyser = GeminiTaskRefiner(commits=tasks, since=self.extractor.params["since"], until=self.extractor.params["until"])
        # Pour utiliser Mistral a la place de Gemini :
        # analyser = MistralTaskRefiner(commits=tasks, since=self.extractor.params["since"], until=self.extractor.params["until"])
        # Pour utiliser Claude (via le CLI `claude`, sans cle API) :
        analyser = ClaudeTaskRefiner(commits=tasks, since=self.extractor.params["since"], until=self.extractor.params["until"],
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
        # Ancienne plateforme : from RPA.OrangeScrumRpa import OrangeScrumRpa ; OrangeScrumRpa(self.taskList)
        rpa = EProjetRpa(self.taskList)
        rpa.create_tasks()

        # Une fois les tâches et timesheets créées avec succès, on mémorise le point d'arrêt
        # pour que le prochain lancement reprenne automatiquement à partir de cette date.
        save_last_since(self.extractor.params["until"])
