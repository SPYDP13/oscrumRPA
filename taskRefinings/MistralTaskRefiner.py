import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

from config import MISTRAL_API_KEY, MISTRAL_AGENT_ID, MISTRAL_AGENT_VERSION

MISTRAL_CONVERSATIONS_URL = "https://api.mistral.ai/v1/conversations"


class MistralTaskRefiner:
    def __init__(self, commits: list, since: str, until: str):
        """
        commits : liste plate de tous les commits (avec project_id)
        since   : "2026-04-20T00:00:00Z"
        until   : "2026-05-31T23:59:59Z" (params["until"] de GitlabLogExtractor)
        """
        self.commits = commits
        self.since = since
        self.until = until

    # ─────────────────────────────────────────────────────────────
    def execute(self) -> list:
        working_days = self._get_working_days()

        if not working_days:
            print("❌ Aucun jour ouvrable trouvé")
            return []

        print(f"📅 {len(working_days)} jours ouvrables")
        print(f"📝 {len(self.commits)} commits à analyser")

        return self._analyse_with_mistral(working_days)

    # ─────────────────────────────────────────────────────────────
    def _get_working_days(self) -> list:
        """Retourne tous les jours ouvrables (lundi→vendredi) entre since et until"""
        since_dt = datetime.strptime(self.since, "%Y-%m-%dT%H:%M:%SZ").date()
        until_dt = datetime.strptime(self.until, "%Y-%m-%dT%H:%M:%SZ").date()

        working_days = []
        d = since_dt
        while d <= until_dt:
            if d.weekday() < 5:
                working_days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return working_days

    # ─────────────────────────────────────────────────────────────
    def _get_weeks_info(self, working_days: list) -> list:
        """Groupe les jours par semaine ISO avec les heures cibles"""
        week_groups = {}
        for day_str in working_days:
            d = datetime.strptime(day_str, "%Y-%m-%d").date()
            week_key = d.isocalendar()[:2]
            week_groups.setdefault(week_key, []).append(day_str)

        result = []
        for (year, week_num), days in week_groups.items():
            n = len(days)
            # Semaine partielle → proportionnel à 40h
            target_hours = round(40 * n / 5)
            result.append({
                "semaine": f"{year}-W{week_num:02d}",
                "jours": days,
                "heures_cibles": target_hours,
                "min_par_jour": 5,
                "max_par_jour": 12
            })
        return result

    # ─────────────────────────────────────────────────────────────
    def _build_prompt(self, working_days: list) -> str:
        commits_json = json.dumps(
            [
                {
                    "title": c["title"],
                    "date": c["date"],
                    "project_id": c.get("project_id", "?")
                }
                for c in self.commits
            ],
            ensure_ascii=False,
            indent=2
        )

        weeks_info = self._get_weeks_info(working_days)

        prompt = f"""
Tu es un expert en gestion de projet informatique. Analyse ces commits Git et crée un plan de timesheet professionnel.

## Commits Git à analyser :
{commits_json}

## Informations par semaine :
{json.dumps(weeks_info, ensure_ascii=False, indent=2)}

## Instructions :

### 1. Refactorisation des titres
- Traduis et reformule chaque titre en **français clair et professionnel**
- Le titre doit décrire la tâche métier, pas le code (ex: "fix null pointer" → "Correction erreur de reference nulle dans le module de paiement")
- ⚠️ **INTERDIT** : N'utilise JAMAIS d'apostrophe (ni `'` ni `'`) dans les titres
- Remplace les constructions avec apostrophe par des alternatives sans apostrophe :
  - "de l'affichage" → "de affichage"
  - "de l'API" → "de API"
  - "Mise à jour de l'écran" → "Mise a jour ecran"
  - "Correction d'une erreur" → "Correction erreur"
  - "Intégration de l'authentification" → "Integration authentification"

### 2. Fusion des commits
- Fusionne les commits similaires, liés, ou de faible valeur en une seule tâche
- Exemples de fusion :
  - "fix bug", "fix bug again", "fix bug final" → "Correction et stabilisation du bug X"
  - "ajout champ A", "ajout champ B" → "Ajout des champs A et B au formulaire"

### 3. Attribution des jours
- Assigne chaque tâche à un jour ouvrable de la liste
- Respecte l'ordre chronologique des commits originaux
- Distribue équitablement les tâches sur tous les jours disponibles

### 4. Durées
- Définis une durée réaliste par tâche selon sa complexité (multiples de 0.5h)
- Simple correction : 0.5h à 1h
- Développement fonctionnel : 1.5h à 3h
- Fonctionnalité complexe : 3h à 4h

## Contraintes OBLIGATOIRES sur les heures :
- ✅ Total par semaine = exactement les **heures_cibles** indiquées pour chaque semaine
- ✅ Par jour : minimum **5h**, maximum **12h**
- ✅ Durée par tâche : entre **0.5h et 4h**
- ✅ Utilise UNIQUEMENT les jours de la liste fournie

## Format de réponse :
Réponds UNIQUEMENT avec un tableau JSON valide. Sans markdown, sans explication, sans texte avant ou après.
[
  {{
    "title": "Titre descriptif en français",
    "date": "2026-04-20",
    "hours": 2.0,
    "project_id": "406",
    "original_commits": ["titre commit 1", "titre commit 2"]
  }}
]
"""
        return prompt

    # ─────────────────────────────────────────────────────────────
    def _call_mistral(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }
        payload = {
            "agent_id": MISTRAL_AGENT_ID,
            "agent_version": MISTRAL_AGENT_VERSION,
            "inputs": [
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post(MISTRAL_CONVERSATIONS_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        outputs = data.get("outputs", [])
        for output in outputs:
            if output.get("type") == "message.output":
                content = output.get("content")
                if isinstance(content, list):
                    return "".join(
                        chunk.get("text", "") for chunk in content if isinstance(chunk, dict)
                    ).strip()
                if isinstance(content, str):
                    return content.strip()

        raise ValueError(f"Réponse Mistral inattendue : {json.dumps(data, ensure_ascii=False)[:500]}")

    # ─────────────────────────────────────────────────────────────
    def _analyse_with_mistral(self, working_days: list) -> list:
        print("\n🤖 Analyse Mistral en cours...")

        prompt = self._build_prompt(working_days)
        # print(prompt)
        raw_text = ""

        try:
            raw_text = self._call_mistral(prompt)

            # Nettoyer les balises markdown si Mistral les ajoute
            if "```" in raw_text:
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            parsed = json.loads(raw_text)

            # L'agent Mistral peut renvoyer soit un tableau brut, soit un objet
            # englobant le tableau dans une clé (ex: {"timesheet": [...]})
            if isinstance(parsed, dict):
                tasks_raw = next((v for v in parsed.values() if isinstance(v, list)), None)
                if tasks_raw is None:
                    raise ValueError(f"Aucun tableau de tâches trouvé dans la réponse Mistral : {parsed}")
            else:
                tasks_raw = parsed

        except json.JSONDecodeError as e:
            print(f"❌ Erreur parsing JSON Mistral : {e}")
            print(f"Réponse brute :\n{raw_text[:1000]}")
            return []
        except Exception as e:
            print(f"❌ Erreur Mistral : {e}")
            return []

        # Formater pour OrangeScrumRpa
        result = []
        for task in tasks_raw:
            dt = datetime.strptime(task["date"], "%Y-%m-%d")

            # Format dateStr : "Apr 20, Mon 09:00 am"
            date_str = dt.strftime("%b %-d, %a 09:00 am")
            # Format date simple : "2026-4-20 09:00 am"
            date_simple = f"{dt.year}-{dt.month}-{dt.day} 09:00 am"

            result.append({
                "title": task["title"],
                "dateStr": date_str,
                "date": date_simple,
                "author": "SAWADOGO Yves Dieudonne",
                "hours": float(task.get("hours", 1.0)),
                "project_id": task.get("project_id", "?"),
                "original_commits": task.get("original_commits", [])
            })

        self._print_summary(result)
        return result

    # ─────────────────────────────────────────────────────────────
    def _print_summary(self, tasks: list):
        print(f"\n✅ {len(tasks)} tâches après analyse Mistral\n")

        day_map = defaultdict(list)
        for task in tasks:
            day_key = task["date"].split(" ")[0]  # "2026-4-20"
            day_map[day_key].append(task)

        def parse_day(day_str):
            parts = day_str.split("-")
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))

        week_hours = defaultdict(float)

        for day_str in sorted(day_map.keys(), key=parse_day):
            day_tasks = day_map[day_str]
            total_h = sum(t["hours"] for t in day_tasks)
            dt = parse_day(day_str)
            week_key = dt.isocalendar()[:2]
            week_hours[week_key] += total_h

            print(f"  {dt.strftime('%A %d %b')} : {total_h}h — {len(day_tasks)} tâche(s)")
            for t in day_tasks:
                orig = ", ".join(t["original_commits"]) if t["original_commits"] else "-"
                print(f"    • [{t['hours']}h] {t['title']}")
                print(f"      ↳ commits : {orig}")

        print(f"\n📊 Total heures par semaine :")
        for (year, week_num), hours in sorted(week_hours.items()):
            status = "✅" if hours == 40 else "⚠️"
            print(f"  {status} Semaine {week_num} ({year}) : {hours}h")
