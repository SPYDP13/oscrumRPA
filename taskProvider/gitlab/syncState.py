import json
import os
from datetime import date, timedelta

from app_paths import DATA_DIR
from config import APP_SUPPORT_DIR

# Fichier local (non versionné) qui garde la trace de la dernière synchronisation
STATE_FILE = os.path.join(DATA_DIR, ".sync_state.json")

# Date (AAAA-MM-JJ) de la dernière exécution réussie — hors de ~/Documents pour que les tâches
# launchd de 17h55 / 18h puissent la lire et sauter la journée si l'exécution est déjà faite
LAST_RUN_FILE = os.path.join(APP_SUPPORT_DIR, "last_run")



def get_last_since() -> str:
    """Retourne le point de départ (since) : la dernière date sauvegardée. Au tout premier lancement (aucun état),
    le lundi de la semaine en cours, enregistré aussitôt pour ne pas glisser à la semaine suivante."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            since = data.get("since")
            if since:
                return since
    today = date.today()
    since = f"{today - timedelta(days=today.weekday())}T00:00:00Z"
    save_last_since(since)
    return since


def save_last_since(until: str):
    """Sauvegarde la date jusqu'à laquelle on vient de synchroniser, pour reprendre à partir de là au prochain lancement."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"since": until}, f)


def set_resume_date(day: date):
    """Correction manuelle : la prochaine exécution reprend à partir de ce jour (inclus). Le marqueur last_run est
    effacé pour que l'exécution programmée du jour ne soit pas sautée."""
    save_last_since(f"{day.isoformat()}T00:00:00Z")
    try:
        os.remove(LAST_RUN_FILE)
    except OSError:
        pass


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
