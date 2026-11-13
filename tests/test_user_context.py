from datetime import date

from taskRefinings.userContext import parse_schedule

# lundi 09/11 → vendredi 13/11/2026 ; « aujourd'hui » = vendredi 13
DAYS = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
TODAY = date(2026, 11, 13)


def parse(text):
    return parse_schedule(text, DAYS, TODAY)


def test_exemple_lundi_mardi_10h_21h():
    schedule, warnings = parse("lundi mardi je venais à 10h environ et finissais vers 21h")
    assert schedule == {d: {"start": "10:00", "end": "21:00", "hours": 11.0} for d in ("2026-11-09", "2026-11-10")}
    assert not warnings


def test_derniers_jours_et_heure_de_depart_seule():
    schedule, _ = parse("ces deux derniers jours je reste au bureau jusqu'à 20h30")
    assert schedule == {d: {"start": "09:00", "end": "20:30", "hours": 11.5} for d in ("2026-11-12", "2026-11-13")}


def test_hier_et_minutes():
    schedule, _ = parse("Hier : 8h45 - 19h15. Avant-hier arrivée 11h")
    assert schedule["2026-11-12"]["hours"] == 10.5
    assert schedule["2026-11-11"] == {"start": "11:00", "end": "18:00", "hours": 7.0}


def test_duree_declaree_et_date():
    schedule, _ = parse("le 11/11 j'ai fait 9h30 de travail")
    assert schedule == {"2026-11-11": {"start": None, "end": None, "hours": 9.5}}


def test_jours_repris_de_la_phrase_precedente():
    schedule, _ = parse("Mercredi grosse mise en prod. Je suis resté de 9h à 22h")
    assert schedule == {"2026-11-11": {"start": "09:00", "end": "22:00", "hours": 13.0}}


def test_texte_sans_horaire_ou_sans_jour():
    assert parse("") == ({}, [])
    assert parse("mise en production du module paiement mardi") == ({}, [])
    schedule, warnings = parse("je finissais vers 21h")
    assert schedule == {} and warnings


def test_horaires_incoherents_ignores():
    schedule, warnings = parse("lundi de 21h à 10h")
    assert schedule == {} and warnings


def test_phrase_reelle_plusieurs_jours_et_horaires():
    # période du mardi 10 au vendredi 13 : « lundi » est hors période, « jeudi hier » = jeudi 12, « today » = vendredi 13
    days = ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    schedule, warnings = parse_schedule(
        "lundi et mardi j avais des seances longues de support de test mais je venais vers 9h30 et rentrais vers "
        "21h30, jeudi hier 9h a 18h et today j ais 2 grosses courses donc reduit pour dire 11h a 15h", days, TODAY)
    assert schedule == {"2026-11-10": {"start": "09:30", "end": "21:30", "hours": 12.0},
                        "2026-11-12": {"start": "09:00", "end": "18:00", "hours": 9.0},
                        "2026-11-13": {"start": "11:00", "end": "15:00", "hours": 4.0}}
    assert not warnings


def test_heures_avant_le_jour():
    schedule, _ = parse("de 10h à 21h lundi et mardi")
    assert set(schedule) == {"2026-11-09", "2026-11-10"} and schedule["2026-11-09"]["hours"] == 11.0
