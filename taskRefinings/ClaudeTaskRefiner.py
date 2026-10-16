import json
import shutil
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

from config import CLAUDE_CLI_PATH, CLAUDE_MODEL, EPROJET_TYPE_TACHE_REUNION_ID

CLAUDE_TIMEOUT_SECONDS = 600


class ClaudeTaskRefiner:
    def __init__(self, commits: list, since: str, until: str, meetings: list = None):
        """
        commits  : liste plate de tous les commits (avec project_id)
        since    : "2026-04-20T00:00:00Z"
        until    : "2026-05-31T23:59:59Z" (params["until"] de GitlabLogExtractor)
        meetings : réunions Outlook (OutlookCalendarExtractor) — reprises telles quelles avec leur
                   durée réelle, les commits complètent les heures restantes
        """
        self.commits = commits
        self.since = since
        self.until = until
        self.meetings = meetings or []

    # ─────────────────────────────────────────────────────────────
    def execute(self) -> list:
        working_days = self._get_working_days()

        if not working_days:
            print("❌ Aucun jour ouvrable trouvé")
            return []

        print(f"📅 {len(working_days)} jours ouvrables")
        print(f"📝 {len(self.commits)} commits à analyser")
        print(f"📆 {len(self.meetings)} réunion(s) Outlook")

        # Réunions : durée réelle. Le reste jusqu'aux 40h/semaine est complété par Claude
        # à partir des commits, ou à défaut à partir des réunions (préparation, compte rendu, suivi...)
        meeting_tasks = self._meeting_tasks(working_days)
        if self.commits:
            filler_tasks = self._analyse_with_claude(working_days)
        elif meeting_tasks:
            filler_tasks = self._analyse_with_claude(working_days, from_meetings=True)
        else:
            filler_tasks = []

        result = meeting_tasks + filler_tasks
        self._print_summary(result)
        return result

    # ─────────────────────────────────────────────────────────────
    def _meeting_hours_by_day(self) -> dict:
        """{"2026-10-14": 1.5, ...} — heures de réunion par jour"""
        hours = defaultdict(float)
        for m in self.meetings:
            hours[datetime.strptime(m["date"].split(" ")[0], "%Y-%m-%d").strftime("%Y-%m-%d")] += m["hours"]
        return hours

    # ─────────────────────────────────────────────────────────────
    def _meeting_tasks(self, working_days: list) -> list:
        """Une tâche E-PROJET (type Projet) par réunion, avec sa durée réelle"""
        result = []
        for m in self.meetings:
            dt = datetime.strptime(m["date"].split(" ")[0], "%Y-%m-%d")
            if dt.strftime("%Y-%m-%d") not in working_days:
                continue
            result.append({
                # la date dans le titre évite les doublons des réunions récurrentes
                "title": f"Reunion - {m['title']} ({dt:%d/%m})",
                "dateStr": dt.strftime("%b %-d, %a 09:00 am"),
                "date": f"{dt.year}-{dt.month}-{dt.day} 09:00 am",
                "author": "SAWADOGO Yves Dieudonne",
                "hours": m["hours"],
                "project_id": "outlook",
                "type_tache_id": EPROJET_TYPE_TACHE_REUNION_ID,
                "original_commits": [f"Outlook {m['start']}-{m['end']}"],
            })
        return result

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

        meeting_hours = self._meeting_hours_by_day()

        result = []
        for (year, week_num), days in week_groups.items():
            n = len(days)
            # Semaine partielle → proportionnel à 40h, moins les heures déjà prises par les réunions
            target_hours = round(40 * n / 5) - sum(meeting_hours.get(d, 0) for d in days)
            result.append({
                "semaine": f"{year}-W{week_num:02d}",
                "jours": days,
                "heures_cibles": max(0, target_hours),
                "heures_reunions_par_jour": {d: meeting_hours[d] for d in days if meeting_hours.get(d)},
                "min_par_jour": 5,
                "max_par_jour": 12
            })
        return result

    # ─────────────────────────────────────────────────────────────
    def _build_prompt(self, working_days: list, from_meetings: bool = False) -> str:
        weeks_info = self._get_weeks_info(working_days)

        if from_meetings:
            source_json = json.dumps(
                [{"title": m["title"], "date": m["date"], "hours": m["hours"]} for m in self.meetings],
                ensure_ascii=False, indent=2)
            intro = ("Il n'y a aucun commit Git sur la période. À partir de ces réunions, crée le travail "
                     "réalisé autour d'elles pour compléter un plan de timesheet professionnel.")
            source_title = "Réunions (déjà saisies avec leur durée réelle)"
            source_rules = """### 2. Tâches autour des réunions
- Crée des tâches réalistes liées aux sujets des réunions : préparation, analyse des besoins,
  rédaction des comptes rendus et spécifications, mise en oeuvre et suivi des actions décidées
- Ne recopie PAS la réunion elle-même (elle est déjà saisie)
- Une tâche de préparation se place le jour de la réunion ou avant, le suivi le jour même ou après

### 3. Attribution des jours
- Assigne chaque tâche à un jour ouvrable de la liste
- Distribue équitablement les tâches sur tous les jours disponibles

### 4. Durées
- Définis une durée réaliste par tâche (multiples de 0.5h)"""
            example_source = '"original_commits": ["titre de la reunion source"]'
        else:
            source_json = json.dumps(
                [{"title": c["title"], "date": c["date"], "project_id": c.get("project_id", "?")}
                 for c in self.commits],
                ensure_ascii=False, indent=2)
            intro = "Analyse ces commits Git et crée un plan de timesheet professionnel."
            source_title = "Commits Git à analyser"
            source_rules = """### 2. Fusion des commits
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
- Fonctionnalité complexe : 3h à 4h"""
            example_source = '"original_commits": ["titre commit 1", "titre commit 2"]'

        prompt = f"""
Tu es un expert en gestion de projet informatique. {intro}

## {source_title} :
{source_json}

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

{source_rules}

### 5. Réunions
- Les heures de réunion (**heures_reunions_par_jour**) sont déjà saisies à part : ne crée PAS de tâche pour elles
- Les **heures_cibles** sont déjà diminuées des heures de réunion
- Place moins de tâches les jours chargés en réunions

## Contraintes OBLIGATOIRES sur les heures :
- ✅ Total par semaine = exactement les **heures_cibles** indiquées pour chaque semaine
- ✅ Par jour (tâches + heures de réunion du jour) : minimum **5h**, maximum **12h**
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
    {example_source}
  }}
]
"""
        return prompt

    # ─────────────────────────────────────────────────────────────
    def _call_claude(self, prompt: str) -> str:
        """Appelle Claude Code en ligne de commande (mode non interactif) et retourne le texte genere"""
        if shutil.which(CLAUDE_CLI_PATH) is None:
            raise FileNotFoundError(f"CLI Claude introuvable : {CLAUDE_CLI_PATH}")

        cmd = [
            CLAUDE_CLI_PATH,
            "-p",                          # mode print (non interactif)
            "--output-format", "json",
            "--tools", "",                 # aucun outil : generation de texte uniquement
            "--no-session-persistence",
        ]
        if CLAUDE_MODEL:
            cmd += ["--model", CLAUDE_MODEL]

        # Le prompt passe par stdin (evite les limites de taille des arguments)
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Claude CLI a echoue ({proc.returncode}) : {proc.stderr.strip()[:500] or proc.stdout.strip()[:500]}")

        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"Erreur Claude : {data.get('result')}")
        return (data.get("result") or "").strip()

    # ─────────────────────────────────────────────────────────────
    def _analyse_with_claude(self, working_days: list, from_meetings: bool = False) -> list:
        print("\n🤖 Analyse Claude en cours" + (" (à partir des réunions)..." if from_meetings else "..."))

        prompt = self._build_prompt(working_days, from_meetings)
        # print(prompt)
        raw_text = ""

        try:
            raw_text = self._call_claude(prompt)

            # Nettoyer les balises markdown si Claude les ajoute
            if "```" in raw_text:
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            parsed = json.loads(raw_text)

            # Claude peut renvoyer soit un tableau brut, soit un objet
            # englobant le tableau dans une clé (ex: {"timesheet": [...]})
            if isinstance(parsed, dict):
                tasks_raw = next((v for v in parsed.values() if isinstance(v, list)), None)
                if tasks_raw is None:
                    raise ValueError(f"Aucun tableau de tâches trouvé dans la réponse Claude : {parsed}")
            else:
                tasks_raw = parsed

        except json.JSONDecodeError as e:
            print(f"❌ Erreur parsing JSON Claude : {e}")
            print(f"Réponse brute :\n{raw_text[:1000]}")
            return []
        except Exception as e:
            print(f"❌ Erreur Claude : {e}")
            return []

        # Formater pour OrangeScrumRpa
        result = []
        for task in tasks_raw:
            dt = datetime.strptime(task["date"], "%Y-%m-%d")

            # Format dateStr : "Apr 20, Mon 09:00 am"
            date_str = dt.strftime("%b %-d, %a 09:00 am")
            # Format date simple : "2026-4-20 09:00 am"
            date_simple = f"{dt.year}-{dt.month}-{dt.day} 09:00 am"

            item = {
                "title": task["title"],
                "dateStr": date_str,
                "date": date_simple,
                "author": "SAWADOGO Yves Dieudonne",
                "hours": float(task.get("hours", 1.0)),
                "project_id": task.get("project_id", "?"),
                "original_commits": task.get("original_commits", [])
            }
            if from_meetings:
                item["type_tache_id"] = EPROJET_TYPE_TACHE_REUNION_ID  # travail autour des réunions → Projet
            result.append(item)

        return result

    # ─────────────────────────────────────────────────────────────
    def _print_summary(self, tasks: list):
        print(f"\n✅ {len(tasks)} tâches après analyse Claude\n")

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
                print(f"      ↳ source : {orig}")

        print(f"\n📊 Total heures par semaine :")
        for (year, week_num), hours in sorted(week_hours.items()):
            status = "✅" if hours == 40 else "⚠️"
            print(f"  {status} Semaine {week_num} ({year}) : {hours}h")
