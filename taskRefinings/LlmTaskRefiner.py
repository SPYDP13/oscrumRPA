import json
import re
from collections import defaultdict
from datetime import datetime

from config import (EPROJET_PROJECT_ID, EPROJET_TYPE_TACHE_REUNION_ID, GENERIC_TASKS, GITLAB_AUTHOR,
                    PROJECT_MAPPING)
from dateformat import date_str as format_date_str
from taskRefinings import dayPlanner
from taskRefinings.projectMapping import resolve

MAX_TASKS_PER_BLOCK = 3
MAX_TITLE = 150


class LlmTaskRefiner:
    """
    Transforme commits et réunions en tâches de timesheet, 8 h pile par jour ouvré.

    - Les heures sont calculées par le code (taskRefinings/dayPlanner.py) : réunions à leur durée réelle, reste
      réparti entre projets selon l'activité réelle, jours sans commit comblés de manière réaliste.
    - Chaque dépôt GitLab est rattaché à un projet E-PROJET (règles PROJECT_MAPPING, sinon projet par défaut).
    - Le modèle ne fait que rédiger les libellés à partir des vrais commits. S'il échoue, un libellé de secours est
      utilisé : l'IA ne bloque jamais l'exécution.
    Chaque sous-classe n'implémente que _call_llm().
    """
    NAME = "IA"

    def __init__(self, commits: list, since: str, until: str, meetings: list = None):
        """
        commits  : commits GitLab (GitlabLogExtractor : sha, title, authored_at, project_id, project_path…)
        since    : "2026-04-20T00:00:00Z" (ou « J 23:59:59 » : point de reprise, la période commence au lendemain)
        until    : "2026-05-31T23:59:59Z"
        meetings : réunions Outlook (OutlookCalendarExtractor) — reprises telles quelles avec leur durée réelle
        """
        self.commits = commits
        self.since = since
        self.until = until
        self.meetings = meetings or []
        self._flag_overlaps()
        self.kept_meetings = [m for m in self.meetings if m["include"]]
        self.unmapped_repos = []
        self.warnings = []

    # ─────────────────────────────────────────────────────────────
    def _flag_overlaps(self):
        """Réunions qui se chevauchent le même jour : seule la plus longue est gardée par défaut. Les autres restent
        dans le plan, décochées (« include »), pour que l'utilisateur puisse choisir dans l'aperçu"""
        by_day = defaultdict(list)
        for m in self.meetings:
            m["include"] = True
            by_day[m["date"].split(" ")[0]].append(m)

        for day_meetings in by_day.values():
            day_meetings.sort(key=lambda m: m["start"])
            cluster, end = [], ""
            for m in day_meetings + [None]:
                if m and cluster and m["start"] < end:  # "HH:MM" : comparaison de chaînes = chronologique
                    cluster.append(m)
                    end = max(end, m["end"])
                    continue
                if len(cluster) > 1:
                    keep = max(cluster, key=lambda c: c["hours"])
                    for c in cluster:
                        c["include"] = c is keep
                        c["conflict"] = "chevauche : " + ", ".join(
                            f"{o['title']} ({o['start']}-{o['end']})" for o in cluster if o is not c)
                if m:
                    cluster, end = [m], m["end"]

    # ─────────────────────────────────────────────────────────────
    def execute(self) -> list:
        working_days = dayPlanner.working_days(self.since, self.until)
        if not working_days:
            print("❌ Aucun jour ouvrable trouvé")
            return []

        print(f"📅 {len(working_days)} jours ouvrables")
        print(f"📝 {len(self.commits)} commits à analyser")
        print(f"📆 {len(self.meetings)} réunion(s) Outlook")
        if not self.commits:
            print("⚠️ Aucun commit sur la période : les journées sont comblées par le suivi des réunions et des "
                  "activités génériques. Si tu as poussé du code, vérifie l'auteur GitLab dans la configuration.")

        meeting_tasks = self._meeting_tasks(working_days)
        blocks, warnings = dayPlanner.plan_days(
            working_days, self._planner_commits(), self._meetings_by_day(), EPROJET_PROJECT_ID,
            GENERIC_TASKS or dayPlanner.DEFAULT_GENERIC_TASKS)
        self.warnings += warnings

        labels = self._write_labels([b for b in blocks if b["kind"] != "generic"])
        result = meeting_tasks + self._tasks_from_blocks(blocks, labels)
        self._unique_titles(result)
        self._print_summary(result)
        return result

    # ─────────────────────────────────────────────────────────────
    def _planner_commits(self) -> list:
        """Commits pour le calcul des heures, rattachés à leur projet E-PROJET (règle, sinon projet par défaut)"""
        result, unmapped = [], {}
        for c in self.commits:
            at = datetime.fromisoformat(c["authored_at"])
            project = resolve(PROJECT_MAPPING, c.get("project_id"), c.get("project_path", ""))
            if project is None:
                unmapped[c.get("project_path") or c.get("project_id")] = True
                project = EPROJET_PROJECT_ID or None
            result.append({"day": at.date().isoformat(), "at": at, "project": project, "title": c["title"],
                           "repo": c.get("project_path") or str(c.get("project_id", ""))})
        self.unmapped_repos = sorted(unmapped)
        if self.unmapped_repos:
            self.warnings.append("dépôt(s) sans règle de correspondance, saisis dans le projet par défaut "
                                 f"({EPROJET_PROJECT_ID or 'non défini'}) : " + ", ".join(self.unmapped_repos))
        return result

    def _meetings_by_day(self) -> dict:
        """{"2026-10-14": [(titre, heures), …]} — réunions gardées"""
        by_day = defaultdict(list)
        for m in self.kept_meetings:
            by_day[self._day(m["date"]).isoformat()].append((m["title"], m["hours"]))
        return by_day

    # ─────────────────────────────────────────────────────────────
    def _meeting_tasks(self, working_days: list) -> list:
        """Une tâche E-PROJET (type réunion) par réunion, avec sa durée réelle, sur le projet par défaut"""
        result = []
        for m in self.meetings:
            dt = self._day(m["date"])
            if dt.isoformat() not in working_days:
                continue
            result.append({
                # la date dans le titre évite les doublons des réunions récurrentes
                "title": self._clean(f"Reunion - {m['title']}") + f" ({dt:%d/%m})",
                **self._date_fields(dt),
                "author": GITLAB_AUTHOR or "",
                "hours": m["hours"],
                "project_id": "outlook",
                "eprojet_project_id": EPROJET_PROJECT_ID or None,
                "kind": "meeting",
                "type_tache_id": EPROJET_TYPE_TACHE_REUNION_ID,
                "original_commits": [f"Outlook {m['start']}-{m['end']}"],
                "include": m["include"],
                **({"conflict": m["conflict"]} if m.get("conflict") else {}),
            })
        return result

    # ─────────────────────────────────────────────────────────────
    def _write_labels(self, blocks: list) -> dict:
        """{id du bloc: [(titre, heures), …]} rédigés par le modèle ; {} si pas de bloc ou en cas d'échec"""
        if not blocks:
            return {}
        print(f"\n🤖 Rédaction des libellés par {self.NAME} ({len(blocks)} bloc(s))…")
        raw_text = ""
        try:
            raw_text = self._call_llm(self._build_prompt(blocks))
            items = self._parse_json(raw_text)
        except Exception as e:
            self.warnings.append(f"rédaction {self.NAME} impossible ({str(e)[:200]}) : libellés de secours utilisés")
            if raw_text:
                print(f"Réponse brute :\n{raw_text[:1000]}")
            return {}

        known = {b["id"]: b for b in blocks}
        by_block = defaultdict(list)
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            bid = str(item.get("bloc") or item.get("block") or item.get("id") or "")
            title = self._clean(str(item.get("title") or ""))
            try:
                hours = float(item.get("hours") or 0)
            except (TypeError, ValueError):
                hours = 0
            if bid in known and title:
                by_block[bid].append((title, hours))

        labels = {}
        for bid, entries in by_block.items():
            entries = entries[:MAX_TASKS_PER_BLOCK]
            weights = {i: h if h > 0 else 1 for i, (_, h) in enumerate(entries)}
            split = dayPlanner.split_hours(known[bid]["hours"], weights)  # somme ramenée aux heures du bloc
            labels[bid] = [(entries[i][0], h) for i, h in split.items() if h > 0]
        missing = len(blocks) - len(labels)
        if missing:
            self.warnings.append(f"{missing} bloc(s) sans libellé {self.NAME} : libellé de secours utilisé")
        return labels

    def _build_prompt(self, blocks: list) -> str:
        source = [{"bloc": b["id"], "jour": b["day"], "heures": b["hours"], "nature": b["kind"],
                   "depots": [r.rsplit("/", 1)[-1] for r in b["repos"]], "commits": b["commits"]} for b in blocks]
        return f"""Tu rédiges des libellés de tâches de timesheet à partir de commits Git RÉELS.
Les heures de chaque bloc sont déjà calculées : tu ne changes pas le total d'un bloc.

## Blocs
{json.dumps(source, ensure_ascii=False, indent=2)}

## Pour chaque bloc
- Produis 1 à {MAX_TASKS_PER_BLOCK} tâches. La somme de leurs heures = exactement les heures du bloc.
- Heures en multiples de 0.25, minimum 0.5 par tâche.
- Regroupe les commits liés dans une même tâche (ex. « fix bug », « fix bug again » → une seule tâche).

## Rédaction
- Français clair et professionnel, qui décrit le travail métier, pas le code.
- Décris UNIQUEMENT le travail visible dans les commits du bloc. N'invente aucune fonctionnalité, aucun écran,
  aucun module qui n'apparaît pas dans les commits.
- nature « continuation » : le bloc prolonge le travail des commits cités (faits un jour voisin). Formule-le comme
  une suite : tests, corrections, finalisation, revue de ce travail.
- nature « meeting_followup » : préparation, compte rendu ou suivi des réunions citées, sans inventer leur contenu.
- INTERDIT : apostrophe (ni ' ni ’). Écris « Mise a jour ecran » plutôt que « Mise à jour de l'écran ».
- Pas de date dans le titre (elle est ajoutée automatiquement). Titre de 120 caractères au plus.

## Format de réponse
Réponds UNIQUEMENT avec un tableau JSON valide, sans markdown ni texte autour :
[{{"bloc": "b1", "title": "Titre en francais", "hours": 2.5}}]
"""

    @staticmethod
    def _parse_json(raw_text: str):
        text = raw_text.strip()
        if "```" in text:  # balises markdown éventuelles
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        if isinstance(parsed, dict):  # tableau parfois englobé dans une clé (ex. {"taches": [...]})
            parsed = next((v for v in parsed.values() if isinstance(v, list)), None)
            if parsed is None:
                raise ValueError("aucun tableau de tâches dans la réponse")
        return parsed

    # ─────────────────────────────────────────────────────────────
    def _call_llm(self, prompt: str) -> str:
        """Envoie le prompt au modèle et retourne le texte généré — implémenté par chaque refiner"""
        raise NotImplementedError

    # ─────────────────────────────────────────────────────────────
    def _tasks_from_blocks(self, blocks: list, labels: dict) -> list:
        result = []
        unmapped = set(self.unmapped_repos)
        for b in blocks:
            dt = datetime.strptime(b["day"], "%Y-%m-%d")
            for title, hours in labels.get(b["id"]) or [(self._fallback_title(b), b["hours"])]:
                task = {
                    "title": f"{title[:MAX_TITLE].rstrip(' ,;:-')} ({dt:%d/%m})",
                    **self._date_fields(dt),
                    "author": GITLAB_AUTHOR or "",
                    "hours": hours,
                    "project_id": ", ".join(b["repos"]) or {"generic": "generique",
                                                            "meeting_followup": "outlook"}.get(b["kind"], "?"),
                    "eprojet_project_id": b["project"],
                    "kind": b["kind"],
                    "original_commits": ([f"suite de : {c}" for c in b["commits"]] if b["kind"] == "continuation"
                                         else b["commits"] or ["activité générique"]),
                    "include": True,
                }
                if b["kind"] == "meeting_followup":
                    task["type_tache_id"] = EPROJET_TYPE_TACHE_REUNION_ID
                if unmapped & set(b["repos"]):
                    task["unmapped"] = True
                result.append(task)
        return result

    def _fallback_title(self, block: dict) -> str:
        """Libellé sans IA, construit uniquement à partir des sources du bloc"""
        if block["kind"] == "generic":
            return self._clean(block["label"])
        names = ", ".join(r.rsplit("/", 1)[-1] for r in block["repos"])
        details = ", ".join(block["commits"][:3]) + (" …" if len(block["commits"]) > 3 else "")
        prefix = {"commits": f"Developpement {names}", "continuation": f"Suite du travail sur {names}",
                  "meeting_followup": "Preparation et suivi"}[block["kind"]]
        return self._clean(f"{prefix} : {details}" if details else prefix)

    @staticmethod
    def _unique_titles(tasks: list):
        """Deux tâches du même jour ne peuvent pas porter le même titre (reprise par titre dans E-PROJET)"""
        seen = defaultdict(int)
        for t in tasks:
            seen[t["title"]] += 1
            if seen[t["title"]] > 1:
                t["title"] = f"{t['title']} - {seen[t['title']]}"

    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _clean(title: str) -> str:
        """Pas d'apostrophe (refusée par E-PROJET), espaces normalisés"""
        return re.sub(r"\s+", " ", re.sub(r"['’‘`]", " ", title)).strip()

    @staticmethod
    def _day(simple: str):
        """'2026-10-5 9:05 am' → date(2026, 10, 5)"""
        y, m, d = simple.split(" ")[0].split("-")
        return datetime(int(y), int(m), int(d)).date()

    @staticmethod
    def _date_fields(dt) -> dict:
        dt = datetime(dt.year, dt.month, dt.day)
        return {"dateStr": format_date_str(dt, "09:00 am"), "date": f"{dt.year}-{dt.month}-{dt.day} 09:00 am"}

    # ─────────────────────────────────────────────────────────────
    def _print_summary(self, tasks: list):
        tasks = [t for t in tasks if t.get("include", True)]
        print(f"\n✅ {len(tasks)} tâches\n")

        day_map = defaultdict(list)
        for task in tasks:
            day_map[self._day(task["date"])].append(task)

        for day in sorted(day_map):
            day_tasks = day_map[day]
            total_h = sum(t["hours"] for t in day_tasks)
            status = "✅" if abs(total_h - dayPlanner.DAY_HOURS) < 0.01 else "⚠️"
            print(f"  {status} {day:%A %d %b} : {total_h:g}h — {len(day_tasks)} tâche(s)")
            for t in day_tasks:
                flag = " ⚠️ non classé" if t.get("unmapped") else ""
                print(f"    • [{t['hours']:g}h] [projet {t.get('eprojet_project_id') or '?'}{flag}] {t['title']}")
                print(f"      ↳ source : {', '.join(t['original_commits']) or '-'}")

        for w in self.warnings:
            print(f"⚠️ {w}")
