"""Point d'entrée unique de l'application (aussi celui de l'exécutable packagé).

  (sans argument)        ouvre l'interface
  --run [--since …]      exécute le RPA (lancé par l'interface)
  --scheduled            exécution programmée de 18h : sautée si déjà faite aujourd'hui, notifications
  --notify-upcoming      notification de 17h55 (sautée si l'exécution du jour est déjà faite)
  --install-browser      télécharge le navigateur Chromium de Playwright
  --diagnostic           affiche les chemins et l'état de l'installation
"""
import argparse
import os
import sys
from datetime import date, datetime

import app_paths  # en premier : définit PLAYWRIGHT_BROWSERS_PATH pour la version packagée


def _ensure_streams():
    """Version packagée sans console : stdout/stderr peuvent être absents ; journal toujours en UTF-8"""
    for name, fd in (("stdout", 1), ("stderr", 2)):
        stream = getattr(sys, name)
        if stream is None:
            try:
                stream = open(fd, "w", encoding="utf-8", errors="replace", buffering=1, closefd=False)
            except OSError:
                stream = open(os.devnull, "w")
            setattr(sys, name, stream)
        elif hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


class _Tee:
    """Écrit à la fois dans le flux d'origine et dans le fichier journal"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def _run(args) -> int:
    import browser_setup
    from main import run

    if not args.dry_run and not browser_setup.is_installed():
        print("🌐 Premier lancement : téléchargement du navigateur Chromium…")
        if not browser_setup.install():
            print("❌ Téléchargement du navigateur impossible")
            return 1
    run(args.since, args.until, args.dry_run)
    return 0


def _scheduled(args) -> int:
    from notifier import notify
    from taskProvider.gitlab.syncState import get_last_run

    if get_last_run() == date.today().isoformat():
        print(f"{datetime.now():%d/%m/%Y %H:%M} : exécution déjà faite aujourd'hui, ignorée")
        return 0

    os.makedirs(app_paths.LOGS_DIR, exist_ok=True)
    log = open(os.path.join(app_paths.LOGS_DIR, f"rpa_{date.today().isoformat()}.log"), "a", encoding="utf-8")
    sys.stdout = sys.stderr = _Tee(sys.stdout, log)
    print(f"\n===== {datetime.now():%d/%m/%Y %H:%M:%S} — exécution programmée =====")

    notify("RPA Timesheet", "Exécution en cours…")
    try:
        code = _run(args)
    except Exception as e:
        print(f"❌ {e}")
        code = 1
    if code == 0:
        notify("RPA Timesheet ✅", "Tâches et heures saisies avec succès")
    else:
        notify("RPA Timesheet ❌", f"Échec — voir le journal rpa_{date.today().isoformat()}.log")
    return code


def _notify_upcoming() -> int:
    from notifier import notify
    from taskProvider.gitlab.syncState import get_last_run

    if get_last_run() != date.today().isoformat():
        notify("RPA Timesheet", "Le RPA démarre dans 5 minutes (18h00). Enregistre ton travail.")
    return 0


def _diagnostic() -> int:
    import shutil
    import browser_setup
    import keyring

    print(f"Exécutable      : {sys.executable} ({'packagé' if app_paths.FROZEN else 'développement'})")
    print(f"Ressources      : {app_paths.RESOURCE_DIR}")
    print(f"Données (.env)  : {app_paths.DATA_DIR}")
    print(f"État / marqueur : {app_paths.STATE_DIR}")
    print(f"Navigateurs     : {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '(cache Playwright par défaut)')}")
    installed = browser_setup.is_installed()
    print(f"Chromium        : {'installé' if installed else 'à télécharger'}")
    if installed:
        try:
            print(f"Lancement       : OK (Chromium {browser_setup.launch_test()})")
        except Exception as e:
            print(f"Lancement       : ÉCHEC — {e}")
    print(f"Trousseau       : {type(keyring.get_keyring()).__name__}")
    import secret_vault
    from config import SECRET_KEYS
    secrets = secret_vault.load(SECRET_KEYS)
    for key in SECRET_KEYS:
        print(f"  {key:<17} : {'présent' if secrets.get(key) else 'absent'}")
    print(f"Certificat      : {os.path.exists(app_paths.resource('certs', 'sectigo-public-server-auth-ca-dv-r36.pem'))}")
    print(f"CLI claude      : {shutil.which('claude', path=app_paths.with_extra_path(os.environ.get('PATH', ''))) or 'introuvable'}")
    return 0


def main() -> int:
    from main import add_run_arguments

    parser = argparse.ArgumentParser(prog="RPA Timesheet", description="GitLab / Outlook → tâches et heures")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true", help="exécute le RPA")
    mode.add_argument("--scheduled", action="store_true", help="exécution programmée (18h)")
    mode.add_argument("--notify-upcoming", action="store_true", help="notification de 17h55")
    mode.add_argument("--install-browser", action="store_true", help="télécharge Chromium")
    mode.add_argument("--diagnostic", action="store_true", help="affiche l'état de l'installation")
    add_run_arguments(parser)
    args, _ = parser.parse_known_args()  # macOS peut ajouter des arguments (-psn_…) au lancement d'une .app

    if not (args.run or args.scheduled or args.notify_upcoming or args.install_browser or args.diagnostic):
        from ui.app import main as ui_main
        return ui_main()

    _ensure_streams()
    os.environ["PATH"] = app_paths.with_extra_path(os.environ.get("PATH", ""))  # CLI claude hors terminal
    try:
        if args.run:
            return _run(args)
        if args.scheduled:
            return _scheduled(args)
        if args.notify_upcoming:
            return _notify_upcoming()
        if args.install_browser:
            import browser_setup
            return 0 if browser_setup.install() else 1
        return _diagnostic()
    except Exception as e:
        # message lisible dans le journal (sans fenêtre d'erreur PyInstaller sous Windows)
        import traceback
        traceback.print_exc()
        print(f"\n{e if str(e).startswith('❌') else f'❌ {e}'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
