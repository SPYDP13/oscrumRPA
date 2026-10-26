"""Plan de saisie : tâches générées (analyse IA + réunions) en attente de saisie dans le timesheet.

Conservé dans .plan.json (DATA_DIR) jusqu'à une saisie complète :
- l'aperçu enregistre le plan, que l'utilisateur peut corriger (« Plan… » dans l'interface) ; l'exécution saisit
  ce plan-là au lieu de rappeler l'IA
- la progression (tâche créée, heures saisies) y est enregistrée au fil de l'eau : après un échec, la relance
  reprend là où elle s'est arrêtée, sans recréer les tâches déjà créées
"""
import json
import os
from datetime import date, datetime

from app_paths import DATA_DIR
from dateformat import date_str

PLAN_FILE = os.path.join(DATA_DIR, ".plan.json")


def load():
    try:
        with open(PLAN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(plan: dict):
    tmp = PLAN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PLAN_FILE)  # jamais de plan à moitié écrit, même si le processus est tué


def clear():
    try:
        os.remove(PLAN_FILE)
    except OSError:
        pass


def new(since: str, until: str, custom: bool, tasks: list) -> dict:
    return {"since": since, "until": until, "custom": custom,
            "created": datetime.now().isoformat(timespec="seconds"), "validated": False, "tasks": tasks}


def started(task: dict) -> bool:
    """Tâche déjà créée ou saisie dans le timesheet : elle ne doit plus être modifiée dans le plan"""
    return bool(task.get("eprojet_id") or task.get("oscrum_created") or task.get("done"))


def has_progress(plan: dict) -> bool:
    return any(started(t) for t in plan["tasks"])


def reusable(plan, since: str, until: str, custom: bool) -> bool:
    """Plan de la même période. Un aperçu brut (ni validé ni commencé) d'un jour précédent est régénéré, pour
    inclure les derniers commits ; un plan validé ou commencé est toujours repris"""
    if not plan or plan["custom"] != custom or plan["since"] != since:
        return False
    if plan["until"] == until:
        return True
    return not custom and (plan.get("validated") or has_progress(plan))


def day_of(task: dict) -> date:
    """'2026-5-4 09:00 am' → date(2026, 5, 4)"""
    y, m, d = task["date"].split(" ")[0].split("-")
    return date(int(y), int(m), int(d))


def set_day(task: dict, day: date):
    dt = datetime(day.year, day.month, day.day)
    task["dateStr"] = date_str(dt, "09:00 am")
    task["date"] = f"{dt.year}-{dt.month}-{dt.day} 09:00 am"
