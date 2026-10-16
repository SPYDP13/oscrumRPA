import json
import os

# Fichier local (non versionné) qui garde la trace de la dernière synchronisation
STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sync_state.json"
)

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
