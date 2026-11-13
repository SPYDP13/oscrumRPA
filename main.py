import argparse


def run(since: str = None, until: str = None, dry_run: bool = False, context: str = None):
    """since / until : "AAAA-MM-JJ" (période imposée) ; dry_run : analyse sans saisie dans le timesheet ;
    context : contexte libre (horaires déclarés, ex. « lundi mardi de 10h à 21h »)"""
    import sys
    from config import check_config
    from taskExecutor.gitlab.GitlabOrangeScrumExecutor import GitlabOrangeScrumExecutor

    check_config()

    executor = GitlabOrangeScrumExecutor(since=f"{since}T00:00:00Z" if since else None,
                                         until=f"{until}T23:59:59Z" if until else None, context=context)
    executor.init_task_list()
    if dry_run:
        return
    # En terminal : récapitulatif à valider avant la saisie effective (l'interface, elle, affiche le plan)
    if sys.stdin.isatty() and input("\nSaisir ces tâches dans le timesheet ? [o/N] ").strip().lower() not in ("o", "oui", "y"):
        print("⏸ Saisie annulée : le plan est conservé (relancer pour le saisir tel quel)")
        return
    executor.execute()


def add_run_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--since", help="début de période imposée (AAAA-MM-JJ), pour un rattrapage")
    parser.add_argument("--until", help="fin de période imposée (AAAA-MM-JJ), pour un rattrapage")
    parser.add_argument("--dry-run", action="store_true",
                        help="analyse uniquement : affiche les tâches sans rien saisir dans le timesheet")
    parser.add_argument("--context", help="contexte libre, ex. « lundi mardi de 10h à 21h » : horaires déclarés "
                                          "(heures du jour à la place de 8 h) et précisions pour les libellés")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="RPA Timesheet : GitLab / Outlook → tâches et heures")
    add_run_arguments(parser)
    args = parser.parse_args()
    run(args.since, args.until, args.dry_run, args.context)
