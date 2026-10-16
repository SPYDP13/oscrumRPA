"""Chemins de l'application, en mode développement (python …) comme en mode packagé (PyInstaller .app / .exe).

- RESOURCE_DIR : fichiers fournis avec l'application (certificat, icônes) — lecture seule une fois packagée
- DATA_DIR     : configuration (.env), point de reprise, journaux — écrits par l'application
                 · développement : le dossier du projet (comportement historique)
                 · packagé : dossier de données utilisateur (~/Library/Application Support/RPA Timesheet,
                   %LOCALAPPDATA%\\RPA Timesheet sous Windows)
- STATE_DIR    : toujours le dossier de données utilisateur (hors de ~/Documents, lisible par la tâche
                 programmée sans autorisation macOS) — marqueur de dernière exécution
"""
import os
import sys

from platformdirs import user_data_dir

APP_NAME = "RPA Timesheet"
FROZEN = getattr(sys, "frozen", False)
IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = getattr(sys, "_MEIPASS", PROJECT_DIR)
STATE_DIR = user_data_dir(APP_NAME, appauthor=False)
DATA_DIR = STATE_DIR if FROZEN else PROJECT_DIR
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# Navigateur Playwright : téléchargé au premier lancement dans les données utilisateur (version packagée)
BROWSERS_DIR = os.path.join(STATE_DIR, "ms-playwright")
if FROZEN:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_DIR

os.makedirs(DATA_DIR, exist_ok=True)


def resource(*parts: str) -> str:
    return os.path.join(RESOURCE_DIR, *parts)


def entry_command(*args: str) -> list:
    """Commande pour relancer l'application dans un autre mode (--run, --scheduled-run, …)"""
    if FROZEN:
        return [sys.executable, *args]
    return [sys.executable, "-W", "ignore", os.path.join(PROJECT_DIR, "rpa_timesheet.py"), *args]


def extra_path_dirs() -> list:
    """Dossiers où se trouve habituellement le CLI `claude` (absents du PATH d'une app lancée hors terminal)"""
    home = os.path.expanduser("~")
    if IS_WINDOWS:
        return [os.path.join(home, ".local", "bin"), os.path.join(os.environ.get("APPDATA", ""), "npm")]
    return [os.path.join(home, ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin"]


def with_extra_path(path: str) -> str:
    return os.pathsep.join([*extra_path_dirs(), path or ""])
