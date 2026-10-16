import json
import os
from datetime import date

from app_paths import DATA_DIR
from config import APP_SUPPORT_DIR

# Fichier local (non versionné) qui garde la trace de la dernière synchronisation
STATE_FILE = os.path.join(DATA_DIR, ".sync_state.json")

# Date (AAAA-MM-JJ) de la dernière exécution réussie — hors de ~/Documents pour que les tâches
# launchd de 17h55 / 18h puissent la lire et sauter la journée si l'exécution est déjà faite
LAST_RUN_FILE = os.path.join(APP_SUPPORT_DIR, "last_run")

# Date de départ utilisée uniquement lors du tout premier lancement (aucun état sauvegardé)
DEFAULT_SINCE = "2026-07-24T00:00:00Z"


def get_last_since() -> str:
    """Retourne le point de départ (since) : la dernière date sauvegardée, ou DEFAULT_SINCE si première exécution."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            since = data.get("since")
            if since:
                return since
    return DEFAULT_SINCE


def save_last_since(until: str):
    """Sauvegarde la date jusqu'à laquelle on vient de synchroniser, pour reprendre à partir de là au prochain lancement."""
    with open(STATE_FILE, "w") as f:
        json.dump({"since": until}, f)


def get_last_run() -> str:
    """Date de la dernière exécution réussie ("2026-10-16"), ou "" si aucune."""
    try:
        with open(LAST_RUN_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def save_last_run():
    os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
    with open(LAST_RUN_FILE, "w") as f:
        f.write(date.today().isoformat())
