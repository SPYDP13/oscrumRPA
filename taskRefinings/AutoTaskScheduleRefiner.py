from datetime import datetime, timedelta
import random


#/!\ Ce module est utilise pour planifier des tâches sur une période donnée. (faire une repartition d'un nombre donne de tache sur une periode donne de sort a avoir 40h par semaine, 5-12h par jour, en respectant les jours ouvrables et la date de commit des taches)
class AutoTaskScheduleRefiner:

    def schedule(self, tasks: list, since: str, until: str = None) -> list:
        """
        Prend la liste des tâches brutes et retourne la même liste enrichie avec :
        - date    : jour ouvrable assigné  ex: "2026-5-4 09:00 am"
        - dateStr : ex: "May 4, Mon 09:00 am"
        - hours   : durée assignée à la tâche  ex: 3.0
        """
        since_dt = datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ").date()
        until_dt = (
            datetime.now().date()
            if until is None
            else datetime.strptime(until, "%Y-%m-%dT%H:%M:%SZ").date()
        )

        # 1️⃣ Jours ouvrables (lundi → vendredi)
        working_days = []
        d = since_dt
        while d <= until_dt:
            if d.weekday() < 5:
                working_days.append(d)
            d += timedelta(days=1)

        if not working_days:
            print("❌ Aucun jour ouvrable trouvé")
            return []

        print(f"\n📅 {len(working_days)} jours ouvrables du {since_dt} au {until_dt}")

        # 2️⃣ Heures par semaine (40h/sem) → heures par jour (5-12h)
        day_hours = {}
        week_groups = {}
        for day in working_days:
            wk = day.isocalendar()[:2]
            week_groups.setdefault(wk, []).append(day)

        for wk, days in week_groups.items():
            n = len(days)
            target = round(40 * n / 5)           # proportionnel si semaine partielle
            target = max(n * 5, min(n * 12, target))
            hours_list = self._distribute_hours(target, n, 5.0, 12.0)
            for day, h in zip(days, hours_list):
                day_hours[day] = h

        # 3️⃣ Trier les tâches par date de commit
        sorted_tasks = sorted(tasks, key=lambda t: t['date'])

        # 4️⃣ Distribuer les tâches sur les jours en round-robin
        day_tasks = {day: [] for day in working_days}
        for i, task in enumerate(sorted_tasks):
            day = working_days[i % len(working_days)]
            day_tasks[day].append(task)

        # 5️⃣ Assigner les heures par tâche + mettre à jour date/dateStr
        result = []
        for work_day in working_days:
            tasks_for_day = day_tasks[work_day]
            if not tasks_for_day:
                continue

            total_h = day_hours[work_day]
            task_hours = self._split_hours(total_h, len(tasks_for_day))

            # Format des dates pour ce jour
            date_str = work_day.strftime("%b %-d, %a 09:00 am")       # "May 4, Mon 09:00 am"
            date_simple = f"{work_day.year}-{work_day.month}-{work_day.day} 09:00 am"  # "2026-5-4 09:00 am"

            for task, h in zip(tasks_for_day, task_hours):
                result.append({
                    **task,              # conserve title, author, project_id, original_commits...
                    "date": date_simple, # ← jour ouvrable assigné
                    "dateStr": date_str, # ← format affiché
                    "hours": h           # ← durée assignée
                })

        self._print_plan(result)
        return result

    # ─────────────────────────────────────────────────────────────
    def _distribute_hours(self, total: float, n: int, min_h: float = 5.0, max_h: float = 12.0) -> list:
        """Distribue total heures sur n jours (min_h ≤ chaque jour ≤ max_h), par pas de 0.5h"""
        hours = [min_h] * n
        remaining = round(total - min_h * n, 1)

        while remaining > 0:
            candidates = [i for i in range(n) if hours[i] < max_h]
            if not candidates:
                break
            idx = random.choice(candidates)
            add = round(min(0.5, remaining, max_h - hours[idx]), 1)
            hours[idx] = round(hours[idx] + add, 1)
            remaining = round(remaining - add, 1)

        random.shuffle(hours)
        return hours

    # ─────────────────────────────────────────────────────────────
    def _split_hours(self, total_hours: float, n_tasks: int) -> list:
        """Découpe total_hours en n_tasks parts aléatoires (min 0.5h chacune)"""
        if n_tasks == 0:
            return []
        hours = [0.5] * n_tasks
        remaining = round(total_hours - 0.5 * n_tasks, 1)

        while remaining > 0:
            idx = random.randint(0, n_tasks - 1)
            add = round(min(0.5, remaining), 1)
            hours[idx] = round(hours[idx] + add, 1)
            remaining = round(remaining - add, 1)

        return hours

    # ─────────────────────────────────────────────────────────────
    def _print_plan(self, tasks: list):
        print("\n📋 Plan de remplissage :")

        day_map = {}
        for task in tasks:
            key = task['date'].split(' ')[0]  # "2026-5-4"
            day_map.setdefault(key, []).append(task)

        def parse_day(s):
            p = s.split('-')
            return datetime(int(p[0]), int(p[1]), int(p[2]))

        week_totals = {}
        for day_str in sorted(day_map.keys(), key=parse_day):
            day_tasks = day_map[day_str]
            total_h = round(sum(t['hours'] for t in day_tasks), 1)
            dt = parse_day(day_str)
            wk = dt.isocalendar()[:2]
            week_totals[wk] = round(week_totals.get(wk, 0) + total_h, 1)

            print(f"  {dt.strftime('%A %d %b')} : {total_h}h — {len(day_tasks)} tâche(s)")
            for t in day_tasks:
                print(f"    • [{t['hours']}h] {t['title']}")

        print(f"\n📊 Total par semaine :")
        for (year, wk_num), h in sorted(week_totals.items()):
            icon = "✅" if h == 40 else "⚠️"
            print(f"  {icon} Semaine {wk_num} ({year}) : {h}h")
