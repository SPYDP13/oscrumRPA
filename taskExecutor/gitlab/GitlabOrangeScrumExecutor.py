from taskProvider.gitlab.gitlabLogExtrator import GitlabLogExtractor
from RPA.OrangeScrumRpa import OrangeScrumRpa
from taskRefinings.AutoTaskScheduleRefiner import AutoTaskScheduleRefiner
from taskRefinings.GeminiTaskRefiner import GeminiTaskRefiner

class GitlabOrangeScrumExecutor:
    def __init__(self):
        pass
        self.taskList = []
        self.extractor = GitlabLogExtractor()

    def init_task_list(self):
        tasks = self.extractor.get_gitlab_commit_log()

        # 2. Analyse et refactorisation avec Gemini (determine date et hours pour la tache)
        analyser = GeminiTaskRefiner(commits=tasks, since=self.extractor.params["since"])
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
        rpa = OrangeScrumRpa(self.taskList)
        rpa.create_tasks()
