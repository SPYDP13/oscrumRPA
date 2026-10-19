"""Connexion HTTP aux plateformes de timesheet et lecture des listes (projets, types de tâche, personnes)
pour préremplir les listes déroulantes de la configuration. Lecture seule : rien n'est créé."""
import html
import json
import re

from urllib.parse import unquote

import requests

# Valeurs connues, utilisées tant que les listes n'ont pas été chargées depuis la plateforme
EPROJET_TYPES = [("-8", "Autre"), ("-7", "Système"), ("-6", "Support Développement"), ("-5", "Test"),
                 ("-4", "Projet"), ("-3", "Developpement"), ("-2", "Analyse"), ("-1", "Design"),
                 ("1", "Formation"), ("2", "Support Système et Infra"), ("3", "Support Client")]
OSCRUM_TYPES = [("1", "Bug"), ("12", "Change Request"), ("16", "Design"), ("2", "Development"),
                ("3", "Enhancement"), ("11", "Idea"), ("7", "Maintenance"), ("8", "Others"), ("15", "Projet"),
                ("5", "Quality Assurance"), ("9", "Release"), ("4", "Research n Do"), ("14", "Support"),
                ("13", "Systeme"), ("17", "Tache Macro"), ("6", "Unit Testing"), ("10", "Update")]


def _select_options(page: str, select_id: str) -> list:
    m = re.search(r'<select[^>]*id="%s"[^>]*>(.*?)</select>' % re.escape(select_id), page, re.S)
    if not m:
        return []
    return [(v, html.unescape(t).strip())
            for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]*?)\s*</option>', m.group(1)) if v]


# ── E-PROJET ────────────────────────────────────────────────
def eprojet_session(url: str, username: str, password: str) -> requests.Session:
    s = requests.Session()
    s.get(f"{url}/login", timeout=15)
    r = s.post(f"{url}/j_spring_security_check", data={"username": username, "password": password}, timeout=15)
    if "/login" in r.url:
        raise RuntimeError("Identifiants E-PROJET refusés")
    return s


def fetch_eprojet(values: dict) -> dict:
    url = values["EPROJET_URL"].rstrip("/")
    s = eprojet_session(url, values["EPROJET_USERNAME"], values["EPROJET_PASSWORD"])
    # le formulaire n'est servi qu'en venant de la page de suivi (sinon redirection)
    page = s.get(f"{url}/taches/useform", headers={"Referer": f"{url}/timeSheetTacheParJour/activity"},
                 timeout=30).text
    projects = _select_options(page, "taches_projetId")
    types = _select_options(page, "taches_typeTacheId")
    if not projects:
        raise RuntimeError("Formulaire de tâche E-PROJET illisible")

    # responsables externes : par projet (nom complet tel que recherché dans la liste E-PROJET)
    resp_by_project = {}
    for pid, _ in projects:
        r = s.get(f"{url}/PersonneExterne/search/byProjet/tachesUser/{pid}/*",
                  headers={"X-Requested-With": "XMLHttpRequest"}, timeout=15)
        people = r.json() if r.ok else []
        resp_by_project[pid] = [(f"{p['nom']} {p['prenoms']}".strip(),
                                 f"{p['nom']} {p['prenoms']}  ·  {p.get('fonction') or p.get('structureLibelle') or ''}".strip(" ·"))
                                for p in people]
    return {
        "EPROJET_PROJECT_ID": projects,
        "EPROJET_TYPE_TACHE_ID": types,
        "EPROJET_TYPE_TACHE_REUNION_ID": types,
        "EPROJET_RESP_EXTERNE": resp_by_project,
        "_summary": f"{len(projects)} projet(s), {len(types)} type(s) de tâche, "
                    f"{sum(len(v) for v in resp_by_project.values())} responsable(s) externe(s)",
    }


# ── OrangeScrum ─────────────────────────────────────────────
def orangescrum_session(url: str, username: str, password: str) -> requests.Session:
    """Le formulaire CakePHP contient des jetons cachés : on les renvoie tous avec email / mot de passe"""
    s = requests.Session()
    page = s.get(f"{url}/users/login", timeout=15).text
    form = re.search(r'<form[^>]*id="userLoginForm".*?</form>', page, re.S)
    if not form:
        raise RuntimeError("Formulaire de connexion OrangeScrum introuvable")
    data = {name: html.unescape(value) for name, value in
            re.findall(r'<input[^>]*name="([^"]+)"[^>]*?(?:value="([^"]*)")?[^>]*>', form.group(0))
            if "remember" not in name}
    data.update({"data[User][email]": username, "data[User][password]": password})
    r = s.post(f"{url}/users/login", data=data, timeout=15)
    if "userLoginForm" in r.text:
        raise RuntimeError("Identifiants OrangeScrum refusés")
    return s


def fetch_orangescrum(values: dict) -> dict:
    url = values["OSCRUM_URL"].rstrip("/")
    s = orangescrum_session(url, values["OSCRUM_USERNAME"], values["OSCRUM_PASSWORD"])
    page = s.get(f"{url}/dashboard", timeout=60).text

    # projets : liens « showProjectName('NOM%20encodé', 'uniq_id') » (le texte affiché peut être tronqué)
    links = re.findall(r"""showProjectName\('([^']+)',\s*'([0-9a-f]+)'\)""", page)
    uniq_by_name = {html.unescape(unquote(name)): uniq for name, uniq in links}

    # utilisateur connecté (« Me ») et membres de chaque projet (variable JS PUSERS)
    me = re.search(r"""SES_ID\s*=\s*["']?(\d+)""", page)
    me = me.group(1) if me else None
    m = re.search(r"var PUSERS\s*=\s*(\{.*?\});", page, re.S)
    pusers = json.loads(m.group(1)) if m else {}
    users_by_project = {}
    for name, uniq in uniq_by_name.items():
        members = [u["User"] for u in pusers.get(uniq, [])]
        users_by_project[name] = sorted(
            [(u["id"], f"Moi ({html.unescape(u['name'])})" if u["id"] == me else html.unescape(u["name"]))
             for u in members],
            key=lambda o: (o[0] != me, o[1].lower()))

    # types de tâche : tableau JSON [{"Type": {"id", "name"}}]
    t = re.search(r'(\[\{"Type":\{.*?\}\}\])', page, re.S)
    types = [(x["Type"]["id"], html.unescape(x["Type"]["name"])) for x in json.loads(t.group(1))] if t else OSCRUM_TYPES

    return {
        "OSCRUM_PROJECT": [(n, n) for n in uniq_by_name],
        "OSCRUM_TASK_TYPE_ID": sorted(types, key=lambda o: o[1].lower()),
        "OSCRUM_ASSIGNEE_ID": users_by_project,
        "_summary": f"{len(uniq_by_name)} projet(s), {len(types)} type(s) de tâche"
                    + (f" — ton id (Moi) : {me}" if me else ""),
    }
