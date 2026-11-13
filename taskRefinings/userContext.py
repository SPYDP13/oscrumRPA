"""Contexte libre saisi par l'utilisateur au lancement (facultatif), ex. :
« lundi et mardi je venais vers 9h30 et rentrais vers 21h30, jeudi 9h a 18h et aujourd'hui 11h a 15h ».

Les horaires déclarés sont lus SANS IA (expressions simples, en français) : ils fixent les heures du jour à la place
des 8 h par défaut (10h → 21h = 11 h, sans déduire de pause : l'utilisateur déclare son temps de présence). Le texte
complet est aussi transmis à l'IA, mais uniquement pour la rédaction des libellés.

Lecture : chaque heure (ou durée) est rattachée aux jours cités juste avant elle ; des jours cités à la suite
(« lundi et mardi ») forment un même groupe ; des heures citées avant tout jour vont au premier groupe qui suit.

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
_WEEKDAY = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")s?\b")
_BEFORE_YESTERDAY = re.compile(r"\bavant[- ]?hier\b")
_YESTERDAY = re.compile(r"(?<!avant-)(?<!avant )(?<!avant)\bhier\b")
_TODAY = re.compile(r"\b(?:aujourd ?'? ?hui|auj|today|ce jour)\b")
_ALL = re.compile(r"\b(?:toute la semaine|tous les jours|chaque jour)\b")


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("â", "a"), ("û", "u"), ("ô", "o"), ("î", "i")):
        text = text.replace(a, b)
    return text


def _day_refs(text: str, days: list, today: date) -> list:
    """Mentions de jours : [(position, [jours de la période])] — liste vide si le jour cité est hors période"""
    refs = []
    for m in _WEEKDAY.finditer(text):
        same = [d for d in days if date.fromisoformat(d).weekday() == WEEKDAYS[m.group(1)]]
        refs.append((m.start(), same[-1:]))   # le plus récent de la période
    for m in _DATE.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        year = (int(y) + 2000 if len(y) == 2 else int(y)) if y else today.year
        try:
            refs.append((m.start(), [date(year, mo, d).isoformat()]))
        except ValueError:
            pass
    for regex, delta in ((_BEFORE_YESTERDAY, 2), (_YESTERDAY, 1), (_TODAY, 0)):
        for m in regex.finditer(text):
            refs.append((m.start(), [(today - timedelta(days=delta)).isoformat()]))
    for m in _LAST_N.finditer(text):
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1)]
        refs.append((m.start(), [d for d in days if d <= today.isoformat()][-n:] if n > 0 else []))
    for m in _ALL.finditer(text):
        refs.append((m.start(), list(days)))
    return [(pos, [d for d in found if d in days]) for pos, found in refs]


def _span(start: str, end: str) -> float:
    delta = (datetime.strptime(end, "%H:%M") - datetime.strptime(start, "%H:%M")).total_seconds() / 3600
    return round(delta * 4) / 4


def describe(entry: dict) -> str:
    """{"start": "10:00", "end": "21:00", "hours": 11.0} → « 10:00-21:00 (11 h) »"""
    span = f"{entry['start']}-{entry['end']} " if entry.get("start") else ""
    return f"{span}({entry['hours']:g} h)"


def _entry(group: dict):
    """Horaires d'un groupe de jours : durée déclarée, sinon première et dernière heure citées"""
    if group["duration"] is not None:
        return {"start": None, "end": None, "hours": group["duration"]}
    times = group["times"]
    if not times:
        return None
    if len(times) >= 2:
        start, end = times[0], times[-1]
    elif times[0] >= "12:00":
        start, end = DEFAULT_START, times[0]
    else:
        start, end = times[0], DEFAULT_END
    return {"start": start, "end": end, "hours": _span(start, end)}


def parse_schedule(text: str, days: list, today: date = None) -> tuple:
    """
    text  : contexte libre de l'utilisateur
    days  : jours ouvrés « AAAA-MM-JJ » de la période
    Retourne ({jour: {"start": "10:00" | None, "end": "21:00" | None, "hours": 11.0}}, avertissements).
    """
    today = today or date.today()
    text = _norm(text or "")
    events = [(pos, "days", found) for pos, found in _day_refs(text, days, today)]
    for m in _DURATION.finditer(text):
        whole, minutes = m.group(1, 2) if m.group(1) else m.group(3, 4)
        events.append((m.start(), "duration",
                       round((float(whole.replace(",", ".")) + int(minutes or 0) / 60) * 4) / 4))
    without_durations = _DURATION.sub(lambda m: " " * len(m.group(0)), text)   # mêmes positions
    for m in _TIME.finditer(without_durations):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if h <= 23 and mi <= 59:
            events.append((m.start(), "time", f"{h:02d}:{mi:02d}"))
    events.sort(key=lambda e: e[0])

    groups, current, orphans = [], None, {"days": [], "times": [], "duration": None}
    for pos, kind, value in events:
        if kind == "days":
            if current is None or not current["open"]:
                current = {"days": [], "times": [], "duration": None, "open": True}
                if not groups and (orphans["times"] or orphans["duration"] is not None):
                    current["times"], current["duration"] = orphans["times"], orphans["duration"]
                    orphans = {"days": [], "times": [], "duration": None}
                groups.append(current)
            current["days"] += [d for d in value if d not in current["days"]]
            continue
        if current is not None:
            current["open"] = False   # jours cités ensuite : nouveau groupe
        if current is None:
            if kind == "time":
                orphans["times"].append(value)
            else:
                orphans["duration"] = value
        elif kind == "time":
            current["times"].append(value)
        else:
            current["duration"] = value

    schedule, warnings = {}, []
    if orphans["times"] or orphans["duration"] is not None:
        warnings.append("contexte : horaires sans jour reconnu (ignorés) — cite le jour (lundi, hier, 12/11…)")
    for group in groups:
        entry = _entry(group)
        if entry is None or not group["days"]:
            continue   # jour sans horaire (contexte pour les libellés) ou jour hors de la période
        if not MIN_DAY_HOURS <= entry["hours"] <= MAX_DAY_HOURS:
            warnings.append(f"contexte : {describe(entry)} incohérent pour "
                            f"{', '.join(group['days'])} (ignoré)")
            continue
        for d in group["days"]:
            schedule[d] = entry
    return schedule, warnings
