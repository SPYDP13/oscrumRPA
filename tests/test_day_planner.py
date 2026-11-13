from datetime import datetime

from taskRefinings.dayPlanner import plan_days, session_hours, split_hours, working_days


def at(day, hm):
    return datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M")


def commit(day, hm, project, title="t", repo="g/r"):
    return {"day": day, "at": at(day, hm), "project": project, "title": title, "repo": repo}


def hours_by_day(blocks):
    total = {}
    for b in blocks:
        total[b["day"]] = total.get(b["day"], 0) + b["hours"]
    return total


def test_jours_ouvres_et_point_de_reprise():
    # lundi 26/10 → vendredi 30/10, week-end exclu
    assert working_days("2026-10-26T00:00:00Z", "2026-11-01T23:59:59Z") == [
        "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
    # point de reprise « lundi 23:59:59 » : lundi déjà saisi, on commence mardi
    assert working_days("2026-10-26T23:59:59Z", "2026-10-27T23:59:59Z") == ["2026-10-27"]


def test_sessions():
    assert session_hours([]) == 0
    assert session_hours([at("2026-10-27", "10:00")]) == 0.5
    # 9h → 11h même session (écarts ≤ 2h) : 2h + 0.5
    assert session_hours([at("2026-10-27", h) for h in ("09:00", "10:30", "11:00")]) == 2.5
    # deux sessions : (0 + 0.5) + (1 + 0.5)
    assert session_hours([at("2026-10-27", h) for h in ("08:00", "14:00", "15:00")]) == 2.0


def test_split_somme_exacte_au_quart_d_heure():
    for total in (8, 7.25, 5.5, 0.75):
        split = split_hours(total, {"a": 3.3, "b": 1.1, "c": 0.4})
        assert abs(sum(split.values()) - total) < 1e-9
        assert all((h * 4).is_integer() for h in split.values())
    split = split_hours(8, {"a": 3, "b": 1})
    assert split == {"a": 6.0, "b": 2.0}
    # pas assez d'heures pour tout le monde : quart d'heure minimum, puis les plus lourds seulement
    assert sum(split_hours(0.5, {"a": 3, "b": 2, "c": 1}).values()) == 0.5


def test_journee_avec_commits_sur_deux_projets():
    day = "2026-10-27"
    commits = [commit(day, "09:00", "12"), commit(day, "11:00", "12"), commit(day, "15:00", "34")]
    blocks, warnings = plan_days([day], commits, {}, "99")
    assert hours_by_day(blocks) == {day: 8.0}
    by_project = {b["project"]: b["hours"] for b in blocks}
    assert by_project["12"] > by_project["34"] >= 0.5
    assert all(b["kind"] == "commits" for b in blocks)
    assert not warnings


def test_reunions_gardent_leur_duree_et_le_reste_fait_8h():
    day = "2026-10-27"
    blocks, _ = plan_days([day], [commit(day, "10:00", "12")], {day: [("Daily", 0.5), ("Sprint review", 2)]}, "99")
    assert hours_by_day(blocks) == {day: 5.5}       # + 2.5 h de réunions = 8 h


def test_jour_vide_suivi_reunion_puis_suite_du_travail_de_la_veille():
    d1, d2 = "2026-10-27", "2026-10-28"
    blocks, _ = plan_days([d1, d2], [commit(d1, "10:00", "12", "ajout ecran paiement")], {d2: [("Atelier", 2)]}, "99")
    d2_blocks = [b for b in blocks if b["day"] == d2]
    kinds = {b["kind"]: b for b in d2_blocks}
    assert kinds["meeting_followup"]["hours"] == 1.0 and kinds["meeting_followup"]["project"] == "99"
    assert kinds["continuation"]["project"] == "12"
    assert kinds["continuation"]["commits"] == ["ajout ecran paiement"]
    assert hours_by_day(blocks) == {d1: 8.0, d2: 6.0}   # + 2 h de réunion


def test_jour_sans_rien_activites_generiques_sur_le_projet_par_defaut():
    day = "2026-10-27"
    blocks, _ = plan_days([day], [], {}, "99", ["Revue de code", "Support"])
    assert [(b["kind"], b["project"], b["label"], b["hours"]) for b in blocks] == [
        ("generic", "99", "Revue de code", 4.0), ("generic", "99", "Support", 4.0)]


def test_plus_de_8h_de_reunions():
    day = "2026-10-27"
    blocks, warnings = plan_days([day], [commit(day, "10:00", "12")], {day: [("Seminaire", 9)]}, "99")
    assert blocks == [] and warnings


def test_commit_hors_periode_ignore():
    blocks, _ = plan_days(["2026-10-27"], [commit("2026-10-20", "10:00", "12")], {}, "99")
    assert all(b["kind"] == "generic" for b in blocks)


def test_heures_declarees_remplacent_les_8h():
    d1, d2 = "2026-10-27", "2026-10-28"
    blocks, _ = plan_days([d1, d2], [commit(d1, "10:00", "12"), commit(d2, "10:00", "12")],
                          {d1: [("Daily", 0.5)]}, "99", hours_by_day={d1: 11.0})
    assert hours_by_day(blocks) == {d1: 10.5, d2: 8.0}   # 11 h déclarées dont 0.5 h de réunion ; d2 inchangé
