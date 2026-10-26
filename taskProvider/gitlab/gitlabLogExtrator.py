"""Commits GitLab de l'auteur sur la période.

Dépôts : détectés automatiquement à partir des événements « pushed » de l'utilisateur du token (tous les dépôts où
il a poussé, toutes branches), ou liste blanche GITLAB_PROJECTS si elle est renseignée (id[:branche]).
Commits : dédoublonnés par SHA (un commit présent sur plusieurs branches ou dépôts n'est compté qu'une fois),
commits de merge ignorés, jour = date d'écriture (authored_date, stable après un rebase).
"""
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

from config import GITLAB_TOKEN, GITLAB_URL, GITLAB_AUTHOR, GITLAB_PROJECTS
from dateformat import date_simple as format_date_simple, date_str as format_date_str

REQUEST_TIMEOUT = 30   # secondes, par requête GitLab
PER_PAGE = 100         # maximum accepté par l'API GitLab
MAX_EVENT_PAGES = 50


def default_period() -> tuple:
    """(since, until) d'une exécution normale : depuis le point de reprise jusqu'à ce soir"""
    from taskProvider.gitlab.syncState import get_last_since
    return get_last_since(), datetime.now().strftime("%Y-%m-%dT23:59:59Z")


def _get(url: str, token: str, params: dict = None) -> requests.Response:
    return requests.get(url, headers={"PRIVATE-TOKEN": token}, params=params, verify=True, timeout=REQUEST_TIMEOUT)


def pushed_projects(gitlab_url: str, token: str, after: str, before: str) -> dict:
    """{project_id: nombre de commits poussés} d'après les événements « pushed » de l'utilisateur du token.
    after / before : « AAAA-MM-JJ », bornes exclues (contrainte de l'API GitLab)"""
    counts, page = {}, 1
    while page <= MAX_EVENT_PAGES:
        r = _get(f"{gitlab_url}/events", token,
                 {"action": "pushed", "after": after, "before": before, "per_page": PER_PAGE, "page": page})
        if r.status_code != 200:
            raise RuntimeError(f"❌ GitLab, événements — {r.status_code} : {r.text[:300]}")
        events = r.json()
        if not events:
            break
        for ev in events:
            pid = str(ev.get("project_id") or "")
            if pid:
                counts[pid] = counts.get(pid, 0) + int((ev.get("push_data") or {}).get("commit_count") or 0)
        page += 1
    return counts


def project_info(gitlab_url: str, token: str, project_id: str) -> dict:
    """{"id", "path", "name"} — path = chemin complet du dépôt (groupe/sous-groupe/depot)"""
    r = _get(f"{gitlab_url}/projects/{quote(str(project_id), safe='')}", token)
    if r.status_code != 200:
        raise RuntimeError(f"❌ GitLab, projet {project_id} — {r.status_code} : {r.text[:300]}")
    p = r.json()
    return {"id": str(p["id"]), "path": p.get("path_with_namespace", str(project_id)), "name": p.get("name", "")}


def discover_projects(gitlab_url: str, token: str, days: int = 90) -> list:
    """Dépôts où l'utilisateur a poussé ces `days` derniers jours, triés par chemin (écran « Correspondances »)"""
    today = datetime.now().date()
    counts = pushed_projects(gitlab_url, token, (today - timedelta(days=days + 1)).isoformat(),
                             (today + timedelta(days=1)).isoformat())
    projects = []
    for pid, count in counts.items():
        try:
            info = project_info(gitlab_url, token, pid)
        except RuntimeError:
            continue  # dépôt supprimé ou devenu inaccessible
        info["commits"] = count
        projects.append(info)
    return sorted(projects, key=lambda p: p["path"].lower())


class GitlabLogExtractor:
    def __init__(self, since: str = None, until: str = None):
        """since / until ("2026-10-12T00:00:00Z") : période imposée, sinon reprise depuis la dernière synchro"""
        default_since, default_until = default_period()
        self.gitlab_url = GITLAB_URL
        self.token = GITLAB_TOKEN
        self.params = {"author": GITLAB_AUTHOR, "since": since or default_since, "until": until or default_until}

    # ─────────────────────────────────────────────────────────────
    def _targets(self) -> list:
        """[(project_id, branche)] à parcourir ; branche "" = toutes les branches"""
        if GITLAB_PROJECTS:
            print("📌 Liste blanche GITLAB_PROJECTS : " + ", ".join(f"{p}:{b}" if b else p for p, b in GITLAB_PROJECTS))
            return GITLAB_PROJECTS
        since = datetime.strptime(self.params["since"], "%Y-%m-%dT%H:%M:%SZ").date()
        until = datetime.strptime(self.params["until"], "%Y-%m-%dT%H:%M:%SZ").date()
        counts = pushed_projects(self.gitlab_url, self.token, (since - timedelta(days=1)).isoformat(),
                                 (until + timedelta(days=1)).isoformat())
        print(f"🔎 {len(counts)} dépôt(s) détecté(s) (événements « pushed » de la période)")
        return [(pid, "") for pid in counts]

    # ─────────────────────────────────────────────────────────────
    def get_gitlab_commit_log(self) -> list:
        all_commits, seen = [], set()
        infos = {}
        for project_id, branch in self._targets():
            if project_id not in infos:
                infos[project_id] = project_info(self.gitlab_url, self.token, project_id)
            info = infos[project_id]
            commits = self._fetch_commits(info, branch, seen)
            all_commits.extend(commits)
            print(f"  → {info['path']}{' @' + branch if branch else ''} : {len(commits)} commit(s)")

        all_commits.sort(key=lambda c: c["authored_at"])
        print(f"\n✅ Total : {len(all_commits)} commits (tous dépôts, dédoublonnés par SHA, sans merges)\n")
        for c in all_commits:
            print(f"  {c['authored_at'][:16].replace('T', ' ')}  [{c['project_path']}]  {c['title']}")
        return all_commits

    # ─────────────────────────────────────────────────────────────
    def _fetch_commits(self, info: dict, branch: str, seen: set) -> list:
        """Commits de l'auteur sur un dépôt (une branche, ou toutes), pagination comprise"""
        params = {"since": self.params["since"], "until": self.params["until"], "per_page": PER_PAGE}
        if self.params.get("author"):
            params["author"] = self.params["author"]
        if branch:
            params["ref_name"] = branch
        else:
            params["all"] = "true"

        since_day = (datetime.strptime(self.params["since"], "%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=1)).date()
        until_day = datetime.strptime(self.params["until"], "%Y-%m-%dT%H:%M:%SZ").date()

        result, page = [], 1
        while True:
            params["page"] = page
            r = _get(f"{self.gitlab_url}/projects/{quote(info['id'], safe='')}/repository/commits", self.token, params)
            # Commits manquants = timesheet incomplète : on arrête tout (le point de reprise n'avance pas)
            if r.status_code != 200:
                raise RuntimeError(f"❌ GitLab, dépôt {info['path']}{' branche ' + branch if branch else ''} — "
                                   f"{r.status_code} : {r.text[:300]}")
            commits = r.json()
            if not commits:
                break
            for commit in commits:
                sha = commit["id"]
                if sha in seen or len(commit.get("parent_ids") or []) > 1:  # déjà vu, ou commit de merge
                    continue
                seen.add(sha)
                dt = datetime.fromisoformat(commit.get("authored_date") or commit["created_at"])
                if not since_day <= dt.date() <= until_day:
                    # écrit avant la période mais poussé / rebasé dedans : rattaché au jour du commit
                    dt = datetime.fromisoformat(commit.get("committed_date") or commit["created_at"])
                result.append({
                    "sha": sha,
                    "title": commit["title"].strip(),
                    "authored_at": dt.isoformat(),
                    "dateStr": format_date_str(dt),
                    "date": format_date_simple(dt),
                    "author": commit.get("author_name", ""),
                    "project_id": info["id"],
                    "project_path": info["path"],
                    "project_name": info["name"],
                })
            page += 1
        return result


if __name__ == "__main__":
    GitlabLogExtractor().get_gitlab_commit_log()
