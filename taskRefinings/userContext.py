"""Contexte libre saisi par l'utilisateur au lancement (facultatif), ex. :
« lundi mardi je venais vers 10h et finissais vers 21h ».

Les horaires déclarés sont lus SANS IA (expressions simples, en français) : ils fixent les heures du jour à la place
des 8 h par défaut (10h → 21h = 11 h, sans déduire de pause : l'utilisateur déclare son temps de présence). Le texte
complet est aussi transmis à l'IA, mais uniquement pour la rédaction des libellés.

Fonctions pures (testables seules) : aucune lecture de configuration ni de réseau.
"""
import re
from datetime import date, datetime, timedelta

MIN_DAY_HOURS = 0.25
MAX_DAY_HOURS = 16.0
DEFAULT_START = "09:00"   # une seule heure citée l'après-midi = heure de départ (« jusqu'à 21h ») : arrivée par défaut
DEFAULT_END = "18:00"     # une seule heure citée le matin = heure d'arrivée (« arrivé à 10h ») : départ par défaut

WEEKDAYS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4}
NUMBERS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
           "neuf": 9, "dix": 10}

_TIME = re.compile(r"(?<![\d/.,])(\d{1,2})\s*(?:h(?:eures?)?|:)\s*(\d{2})?(?![\d/])")
# durée déclarée : « j'ai fait 11h », « travaille 9h30 », « 10 heures de travail »
_DURATION = re.compile(
    r"\b(?:fait|travaille|bosse|passe)\s+(?:[a-z']+\s+){0,2}?(\d{1,2}(?:[.,]\d+)?)\s*h(?:eures?)?\s*(\d{2})?"
    r"|(\d{1,2}(?:[.,]\d+)?)\s*h(?:eures?)?\s*(\d{2})?\s*(?:de travail|de boulot|de presence|par jour)")
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_LAST_N = re.compile(r"\b(?:ces|les|mes)\s+(\d+|" + "|".join(NUMBERS) + r")\s+derniers?\s+jours?\b")
_CLAUSE = re.compile(r"[.;\n!?]+")


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("â", "a"), ("û", "u"), ("ô", "o"), ("î", "i")):
        text = text.replace(a, b)
    return text


def _days_in(clause: str, days: list, today: date) -> list:
    """Jours ouvrés de la période cités dans la proposition (dans l'ordre de la période)"""
    found = set()
    for name, wd in WEEKDAYS.items():
        if re.search(rf"\b{name}s?\b", clause):
            same = [d for d in days if date.fromisoformat(d).weekday() == wd]
            if same:
                found.add(same[-1])   # le plus récent de la période
    for m in _DATE.finditer(clause):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        year = (int(y) + 2000 if len(y) == 2 else int(y)) if y else today.year
        try:
            found.add(date(year, mo, d).isoformat())
        except ValueError:
            pass
    if re.search(r"\bavant[- ]hier\b", clause):
        found.add((today - timedelta(days=2)).isoformat())
    if re.search(r"(?<!avant-)(?<!avant )\bhier\b", clause):
        found.add((today - timedelta(days=1)).isoformat())
    if "aujourd'hui" in clause:
        found.add(today.isoformat())
    m = _LAST_N.search(clause)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1)]
        if n > 0:
            found.update([d for d in days if d <= today.isoformat()][-n:])
    if re.search(r"\b(toute la semaine|tous les jours|chaque jour)\b", clause):
        found.update(days)
    return [d for d in days if d in found]


def _times_in(clause: str) -> list:
    """Heures « 10h », « 10h30 », « 10:30 », « 21 heures » → ["10:00", "10:30", …]"""
    result = []
    for m in _TIME.finditer(clause):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if h <= 23 and mi <= 59:
            result.append(f"{h:02d}:{mi:02d}")
    return result


def _span(start: str, end: str) -> float:
    delta = (datetime.strptime(end, "%H:%M") - datetime.strptime(start, "%H:%M")).total_seconds() / 3600
    return round(delta * 4) / 4


def describe(entry: dict) -> str:
    """{"start": "10:00", "end": "21:00", "hours": 11.0} → « 10:00-21:00 (11 h) »"""
    span = f"{entry['start']}-{entry['end']} " if entry.get("start") else ""
    return f"{span}({entry['hours']:g} h)"


def parse_schedule(text: str, days: list, today: date = None) -> tuple:
    """
    text  : contexte libre de l'utilisateur
    days  : jours ouvrés « AAAA-MM-JJ » de la période
    Retourne ({jour: {"start": "10:00" | None, "end": "21:00" | None, "hours": 11.0}}, avertissements).
    Une proposition sans jour reprend les jours de la précédente (« Lundi et mardi. Je finissais vers 21h »).
    """
    today = today or date.today()
    schedule, warnings = {}, []
    last_days = []
    for raw in _CLAUSE.split(text or ""):
        clause = _norm(raw).strip()
        if not clause:
            continue
        clause_days = _days_in(clause, days, today) or last_days
        last_days = clause_days
        duration = _DURATION.search(clause)
        times = _times_in(_DURATION.sub(" ", clause))
        if not (duration or times):
            continue
        if not clause_days:
            warnings.append(f"contexte : horaires sans jour de la période dans « {raw.strip()} » (ignorés)")
            continue

        if duration:
            whole, minutes = duration.group(1, 2) if duration.group(1) else duration.group(3, 4)
            entry = {"start": None, "end": None,
                     "hours": round((float(whole.replace(",", ".")) + int(minutes or 0) / 60) * 4) / 4}
        else:
            if len(times) >= 2:
                start, end = times[0], times[-1]
            elif times[0] >= "12:00":
                start, end = DEFAULT_START, times[0]
            else:
                start, end = times[0], DEFAULT_END
            entry = {"start": start, "end": end, "hours": _span(start, end)}
        if not MIN_DAY_HOURS <= entry["hours"] <= MAX_DAY_HOURS:
            warnings.append(f"contexte : {describe(entry)} incohérent dans « {raw.strip()} » (ignoré)")
            continue
        for d in clause_days:
            schedule[d] = entry
    return schedule, warnings
