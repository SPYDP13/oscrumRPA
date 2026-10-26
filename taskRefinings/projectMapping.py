"""Correspondance dépôts GitLab → projets du timesheet (E-PROJET).

Règles « motif=idProjet » séparées par des « ; » (PROJECT_MAPPING dans .env), par exemple :
    miniapp/*=12;orange/mobile/ompi=34;406=34

Motif :
- id numérique GitLab (« 406 ») ;
- chemin exact du dépôt (« orange/mobile/ompi », champ path_with_namespace) ;
- motif avec jokers sur le chemin (« miniapp/* » : tout le groupe, sous-groupes compris).
Priorité : id exact > chemin exact > motif le plus long. Comparaison sans tenir compte de la casse.
Fonctions pures, sans dépendance à la configuration (testables seules).
"""
import fnmatch

WILDCARDS = set("*?[")


def parse_mapping(raw: str) -> list:
    """« miniapp/*=12;406=34 » → [("miniapp/*", "12"), ("406", "34")] (lignes vides ou invalides ignorées)"""
    rules = []
    for item in (raw or "").replace("\n", ";").split(";"):
        pattern, sep, target = item.partition("=")
        if sep and pattern.strip() and target.strip():
            rules.append((pattern.strip(), target.strip()))
    return rules


def format_mapping(rules: list) -> str:
    return ";".join(f"{pattern}={target}" for pattern, target in rules)


def resolve(rules: list, project_id, project_path: str = ""):
    """Id du projet timesheet pour ce dépôt, ou None si aucune règle ne s'applique"""
    pid, path = str(project_id or "").strip(), (project_path or "").strip().lower()
    best, best_rank = None, None
    for pattern, target in rules:
        p = pattern.strip().lower()
        if p.isdigit():
            rank = (3, len(p)) if p == pid else None
        elif WILDCARDS & set(p):
            rank = (1, len(p)) if path and fnmatch.fnmatchcase(path, p) else None
        else:
            rank = (2, len(p)) if path and p == path else None
        if rank and (best_rank is None or rank > best_rank):
            best, best_rank = target, rank
    return best


def rules_from_projects(gitlab_projects: list, default_target: str) -> list:
    """Ancienne configuration (liste de projets GitLab, tout dans un seul projet timesheet) convertie en règles"""
    if not default_target:
        return []
    ids = []
    for pid, _branch in gitlab_projects:
        if pid not in ids:
            ids.append(pid)
    return [(pid, default_target) for pid in ids]


def group_of(project_path: str) -> str:
    """« a/b/depot » → « a/b » (namespace direct du dépôt), « depot » → «  »"""
    return project_path.rpartition("/")[0]
