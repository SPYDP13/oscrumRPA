"""Calcul des heures, sans IA : chaque jour ouvré fait exactement DAY_HOURS (8 h), ou les heures déclarées par
l'utilisateur pour ce jour (contexte du lancement, ex. 10h → 21h = 11 h : voir userContext.py).

Pour chaque jour :
1. les réunions gardent leur durée réelle ;
2. le reste est réparti entre les projets du timesheet au prorata de l'activité réelle du jour (durée des sessions
   de commits) ;
3. un jour sans commit est comblé de manière réaliste, dans cet ordre : préparation / suivi des réunions du jour,
   suite du travail d'un jour voisin (même projet), puis activité générique sur le projet par défaut.

Sortie : des « blocs » {id, day, project, hours, kind, commits, repos, label} que l'IA transforme en libellés
(kind ∈ commits | continuation | meeting_followup | generic ; les blocs « generic » ont déjà leur libellé).
Fonctions pures (testables seules) : aucune lecture de configuration ni de réseau.
"""
from collections import defaultdict
from datetime import datetime, timedelta

DAY_HOURS = 8.0
QUARTER = 0.25
SESSION_GAP = timedelta(hours=2)   # deux commits plus espacés = deux sessions de travail distinctes
SESSION_PAD = 0.5                  # travail avant le premier commit d'une session (h)
NEIGHBOUR_DAYS = 2                 # « suite du travail » : jour actif à 2 jours ouvrés au plus
GENERIC_SPLIT_ABOVE = 4.0          # au-delà, le comblement générique est réparti sur deux activités
DEFAULT_GENERIC_TASKS = ("Revue de code et merge requests", "Support et suivi des anomalies",
                         "Documentation technique", "Coordination et points equipe")


def quarters(hours: float) -> int:
    return int(round(hours / QUARTER))


def session_hours(times: list) -> float:
    """Durée estimée du travail à partir des heures de commit : (dernier − premier) + SESSION_PAD par session"""
    times = sorted(times)
    if not times:
        return 0.0
    total, start, prev = 0.0, times[0], times[0]
    for t in times[1:]:
        if t - prev > SESSION_GAP:
            total += (prev - start).total_seconds() / 3600 + SESSION_PAD
            start = t
        prev = t
    return total + (prev - start).total_seconds() / 3600 + SESSION_PAD


def split_hours(total: float, weights: dict, minimum: float = 0.5) -> dict:
    """Répartit total (au quart d'heure) entre les clés au prorata des poids ; la somme vaut exactement total
    (méthode du plus fort reste). Chaque clé reçoit au moins `minimum` si possible, sinon un quart d'heure ; s'il
    n'y a même pas un quart d'heure par clé, seules les plus lourdes sont servies."""
    units = quarters(total)
    keys = sorted(weights, key=lambda k: (-weights[k], str(k)))
    if units <= 0 or not keys:
        return {k: 0.0 for k in keys}
    min_units = quarters(minimum)
    if min_units * len(keys) > units:
        min_units = 1
    kept = keys[:units // min_units] if min_units * len(keys) > units else keys
    weight_sum = sum(max(weights[k], 0) for k in kept)
    ideal = {k: units * (max(weights[k], 0) / weight_sum if weight_sum else 1 / len(kept)) for k in kept}
    alloc = {k: max(min_units, int(ideal[k])) for k in kept}
    while sum(alloc.values()) < units:   # quarts d'heure restants : aux plus forts restes
        k = max(kept, key=lambda k: (ideal[k] - alloc[k], weights[k]))
        alloc[k] += 1
    while sum(alloc.values()) > units:   # minimum imposé : repris aux plus servis
        k = min((k for k in kept if alloc[k] > min_units), key=lambda k: ideal[k] - alloc[k])
        alloc[k] -= 1
    return {k: alloc.get(k, 0) * QUARTER for k in keys}


def working_days(since: str, until: str) -> list:
    """Jours ouvrés « AAAA-MM-JJ » de la période. Un point de reprise « J 23:59:59 » (fin d'une exécution réussie)
    commence au lendemain : J est déjà saisi."""
    start = (datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=1)).date()
    end = datetime.strptime(until, "%Y-%m-%dT%H:%M:%SZ").date()
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def plan_days(days: list, commits: list, meetings_by_day: dict = None, default_project=None,
              generic_tasks=DEFAULT_GENERIC_TASKS, day_hours: float = DAY_HOURS, hours_by_day: dict = None) -> tuple:
    """
    days            : jours ouvrés « AAAA-MM-JJ » (working_days)
    commits         : [{"day": "AAAA-MM-JJ", "at": datetime, "project": id timesheet ou None, "title", "repo"}]
    meetings_by_day : {"AAAA-MM-JJ": [(titre, heures), …]} — réunions gardées (durée réelle)
    hours_by_day    : {"AAAA-MM-JJ": heures} — heures déclarées par l'utilisateur, à la place de day_hours
    Retourne (blocs, avertissements).
    """
    meetings_by_day = meetings_by_day or {}
    generic_tasks = [g for g in (generic_tasks or DEFAULT_GENERIC_TASKS) if g.strip()] or list(DEFAULT_GENERIC_TASKS)
    by_day = defaultdict(lambda: defaultdict(list))
    for c in commits:
        if c["day"] in days:
            by_day[c["day"]][c["project"]].append(c)

    blocks, warnings = [], []
    generic_turn = 0

    def add(day, project, hours, kind, source=(), label=None):
        if hours <= 0:
            return
        blocks.append({
            "id": f"b{len(blocks) + 1}", "day": day, "project": project, "hours": hours, "kind": kind,
            "commits": [c["title"] for c in source] if kind in ("commits", "continuation") else list(source),
            "repos": sorted({c["repo"] for c in source if c.get("repo")}) if kind in ("commits", "continuation") else [],
            "label": label,
        })

    hours_by_day = hours_by_day or {}
    for i, day in enumerate(days):
        target = hours_by_day.get(day, day_hours)
        meeting_hours = sum(h for _, h in meetings_by_day.get(day, []))
        if meeting_hours > target:
            warnings.append(f"{day} : {meeting_hours:g} h de réunions (plus de {target:g} h), aucun autre travail saisi")
        remaining = quarters(max(0.0, target - meeting_hours)) * QUARTER
        if remaining <= 0:
            continue

        # 1. Activité réelle du jour, répartie entre projets selon la durée des sessions
        projects = by_day.get(day)
        if projects:
            weights = {p: session_hours([c["at"] for c in cs]) for p, cs in projects.items()}
            for project, hours in split_hours(remaining, weights).items():
                add(day, project, hours, "commits", sorted(projects[project], key=lambda c: c["at"]))
            continue

        # 2. Jour sans commit : préparation / suivi des réunions du jour
        if meetings_by_day.get(day):
            followup = min(remaining, max(1.0, quarters(meeting_hours / 2) * QUARTER))
            add(day, default_project, followup, "meeting_followup", [t for t, _ in meetings_by_day[day]])
            remaining -= followup
            if remaining <= 0:
                continue

        # 3. Suite du travail d'un jour voisin (la veille d'abord), sur les mêmes projets
        neighbour = None
        for offset in range(1, NEIGHBOUR_DAYS + 1):
            for j in (i - offset, i + offset):
                if 0 <= j < len(days) and by_day.get(days[j]):
                    neighbour = days[j]
                    break
            if neighbour:
                break
        if neighbour:
            projects = by_day[neighbour]
            weights = {p: session_hours([c["at"] for c in cs]) for p, cs in projects.items()}
            for project, hours in split_hours(remaining, weights).items():
                add(day, project, hours, "continuation", sorted(projects[project], key=lambda c: c["at"]))
            continue

        # 4. Activité générique, vraie et sans détail inventé, sur le projet par défaut
        if remaining > GENERIC_SPLIT_ABOVE:
            first = quarters(remaining / 2) * QUARTER
            parts = [first, remaining - first]
        else:
            parts = [remaining]
        for hours in parts:
            label = generic_tasks[generic_turn % len(generic_tasks)]
            generic_turn += 1
            add(day, default_project, hours, "generic", [], label=label)

    return blocks, warnings
