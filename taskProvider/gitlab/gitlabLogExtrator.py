import requests
from datetime import datetime
from config import GITLAB_TOKEN

GITLAB_URL = "https://gitlab.orange.bf/api/v4"
PROJECT_IDS = ["406", "404", "414", "429", "415"]  # ← liste de projets

headers = {
    "PRIVATE-TOKEN": GITLAB_TOKEN
}

params = {
    "author": "SAWADOGO Yves Dieudonne",
    "since": "2026-05-05T00:00:00Z",
    "until": datetime.now().strftime("%Y-%m-%dT23:59:59Z"),
    "per_page": 200,
    "ref_name": "preprod"
}


class GitlabLogExtractor:
    def __init__(self):
        self.gitlab_url = GITLAB_URL
        self.project_ids = PROJECT_IDS  # ← liste
        self.headers = headers
        self.params = params

    def get_gitlab_commit_log(self):
        all_commits = []
        seen_titles = set()

        # Boucle sur chaque projet
        for project_id in self.project_ids:
            print(f"\n🔍 Récupération des commits pour le projet {project_id}...")
            project_commits = self._fetch_commits_for_project(project_id, seen_titles)
            all_commits.extend(project_commits)
            print(f"  → {len(project_commits)} commits récupérés pour le projet {project_id}")

        # Trier tous les commits par date croissante
        all_commits.sort(key=lambda c: datetime.strptime(c["date"].split(" ")[0], "%Y-%m-%d"))

        print(f"\n✅ Total : {len(all_commits)} commits (tous projets, sans doublons, triés par date)\n")

        for c in all_commits:
            print(f"title  : {c['title']}")
            print(f"dateStr: {c['dateStr']}")
            print(f"date   : {c['date']}")
            print(f"author : {c['author']}")
            print(f"project: {c['project_id']}")
            print("-" * 50)

        return all_commits

    def _fetch_commits_for_project(self, project_id: str, seen_titles: set) -> list:
        """Récupère tous les commits d'un projet donné (avec pagination)"""
        commits_result = []
        page = 1

        # Copie des params pour ne pas modifier l'original
        request_params = {**self.params}

        while True:
            request_params["page"] = page
            response = requests.get(
                f"{self.gitlab_url}/projects/{project_id}/repository/commits",
                headers=self.headers,
                params=request_params,
                verify=True
            )

            if response.status_code != 200:
                print(f"Erreur projet {project_id} — {response.status_code} : {response.text}")
                break

            commits = response.json()
            if not commits:
                break

            for commit in commits:
                title = commit["title"].strip()

                # Dédoublonnage par titre (tous projets confondus)
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                raw_date = commit["created_at"]
                dt = datetime.fromisoformat(raw_date)

                # "May 13, Wed 12:00 am"
                date_str = dt.strftime("%b %-d, %a %-I:%M %p").replace("AM", "am").replace("PM", "pm")

                # "2026-5-13 12:00 am"
                date_simple = f"{dt.year}-{dt.month}-{dt.day} {dt.strftime('%-I:%M')} {dt.strftime('%p').lower()}"

                commits_result.append({
                    "title": title,
                    "dateStr": date_str,
                    "date": date_simple,
                    "author": commit["author_name"],
                    "project_id": project_id  # ← traçabilité
                })

            page += 1

        return commits_result

    def debug_gitlab(self):
        for project_id in self.project_ids:
            print(f"\n=== INFOS DU PROJET {project_id} ===")
            r = requests.get(f"{self.gitlab_url}/projects/{project_id}", headers=self.headers, verify=True)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                project = r.json()
                print(f"Nom       : {project['name']}")
                print(f"Namespace : {project['namespace']['full_path']}")
                print(f"Branche   par défaut : {project['default_branch']}")
            else:
                print(f"Projet introuvable : {r.text}")


if __name__ == "__main__":
    extractor = GitlabLogExtractor()
    commits = extractor.get_gitlab_commit_log()

