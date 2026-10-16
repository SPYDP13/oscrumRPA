import argparse


def run(since: str = None, until: str = None, dry_run: bool = False):
    """since / until : "AAAA-MM-JJ" (période imposée) ; dry_run : analyse sans saisie dans le timesheet"""
    from taskExecutor.gitlab.GitlabOrangeScrumExecutor import GitlabOrangeScrumExecutor

    executor = GitlabOrangeScrumExecutor(since=f"{since}T00:00:00Z" if since else None,
                                         until=f"{until}T23:59:59Z" if until else None)
    executor.init_task_list()
    if not dry_run:
        executor.execute()


def add_run_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--since", help="début de période imposée (AAAA-MM-JJ), pour un rattrapage")
    parser.add_argument("--until", help="fin de période imposée (AAAA-MM-JJ), pour un rattrapage")
    parser.add_argument("--dry-run", action="store_true",
                        help="analyse uniquement : affiche les tâches sans rien saisir dans le timesheet")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="RPA Timesheet : GitLab / Outlook → tâches et heures")
    add_run_arguments(parser)
    args = parser.parse_args()
    run(args.since, args.until, args.dry_run)
