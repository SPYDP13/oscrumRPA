from taskExecutor.gitlab.GitlabOrangeScrumExecutor import GitlabOrangeScrumExecutor

if __name__ == '__main__':
    print('Hello, World!')

    # Execution gitlab
    gitlabExecutor = GitlabOrangeScrumExecutor()
    gitlabExecutor.init_task_list()
    gitlabExecutor.execute()