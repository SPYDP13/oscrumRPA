
import os
from dotenv import load_dotenv

from app_paths import DATA_DIR, PROJECT_DIR, STATE_DIR

ENV_PATH = os.path.join(DATA_DIR, ".env")

load_dotenv(ENV_PATH)  # Charge le fichier .env (dossier du projet, ou données utilisateur une fois packagé)

# Secrets (tokens, mots de passe) : coffre unique du Trousseau macOS en priorité (saisis via l'interface), sinon .env
KEYRING_SERVICE = "eprojet-rpa"
SECRET_KEYS = ("GITLAB_TOKEN", "EXCHANGE_PASSWORD", "EPROJET_PASSWORD", "OSCRUM_PASSWORD",
               "GEMINI_API_KEY", "MISTRAL_API_KEY")


def get_secret(name: str):
    import secret_vault
    return secret_vault.load(SECRET_KEYS).get(name) or os.getenv(name)


# Valeurs invalides relevées à l'import, signalées au lancement du RPA (check_config) : l'interface doit pouvoir
# s'ouvrir pour les corriger
CONFIG_ERRORS = []


def _choice(name: str, default: str, allowed: tuple) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        CONFIG_ERRORS.append(f"{name} invalide : '{value}' (attendu : {', '.join(allowed)})")
    return value


def check_config():
    if CONFIG_ERRORS:
        raise ValueError("❌ Configuration : " + " ; ".join(CONFIG_ERRORS))


def parse_gitlab_projects(raw: str) -> list:
    """« 406:preprod,404:develop,410 » → [("406", "preprod"), ("404", "develop"), ("410", "")]
    (branche vide = toutes les branches)"""
    pairs = []
    for item in (raw or "").split(","):
        pid, _, branch = item.partition(":")
        if pid.strip():
            pairs.append((pid.strip(), branch.strip()))
    return pairs


def format_gitlab_projects(pairs: list) -> str:
    return ",".join(f"{pid}:{branch}" if branch else pid for pid, branch in pairs)


def legacy_gitlab_projects(project_ids: str, branches: str) -> str:
    """Ancienne configuration (GITLAB_PROJECT_IDS × GITLAB_BRANCHES) convertie en couples projet:branche"""
    ids = [v.strip() for v in (project_ids or "").split(",") if v.strip()]
    names = [v.strip() for v in (branches or "").split(",") if v.strip()]
    return format_gitlab_projects([(pid, b) for pid in ids for b in names])


# Dossier hors de ~/Documents (lisible par la tâche programmée sans autorisation macOS) : marqueur de dernière exécution
APP_SUPPORT_DIR = STATE_DIR

# Analyse IA des tâches : "claude" (CLI Claude Code), "gemini" ou "mistral"
TASK_REFINER = _choice("TASK_REFINER", "claude", ("claude", "gemini", "mistral"))

GEMINI_API_KEY  = get_secret("GEMINI_API_KEY")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MISTRAL_API_KEY = get_secret("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID")
MISTRAL_AGENT_VERSION = os.getenv("MISTRAL_AGENT_VERSION") or None  # vide = dernière version de l'agent
CLAUDE_CLI_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
CLAUDE_MODEL    = os.getenv("CLAUDE_MODEL")  # ex: "sonnet", "opus" — None = modele par defaut du CLI

# Plateforme de timesheet à remplir : "eprojet" ou "orangescrum"
TIMESHEET_TARGET = _choice("TIMESHEET_TARGET", "eprojet", ("eprojet", "orangescrum"))

# OrangeScrum
OSCRUM_URL      = os.getenv("OSCRUM_URL", "https://orangescrum.synelia.tech").rstrip("/")
OSCRUM_USERNAME = os.getenv("OSCRUM_USERNAME")
OSCRUM_PASSWORD = get_secret("OSCRUM_PASSWORD")
OSCRUM_PROJECT = os.getenv("OSCRUM_PROJECT")
OSCRUM_TASK_TYPE_ID = os.getenv("OSCRUM_TASK_TYPE_ID", "10")  # 10 = Update
OSCRUM_ASSIGNEE_ID  = os.getenv("OSCRUM_ASSIGNEE_ID")  # id de la personne assignée (propre à chaque compte)

# GitLab
GITLAB_URL         = os.getenv("GITLAB_URL", "https://gitlab.orange.bf/api/v4")
GITLAB_TOKEN       = get_secret("GITLAB_TOKEN")
GITLAB_AUTHOR      = os.getenv("GITLAB_AUTHOR")
# Facultatif : liste blanche de projets (id[:branche], branche vide = toutes). Vide = détection automatique des
# dépôts où l'utilisateur a poussé sur la période (événements GitLab)
GITLAB_PROJECTS    = parse_gitlab_projects(os.getenv("GITLAB_PROJECTS") or legacy_gitlab_projects(
    os.getenv("GITLAB_PROJECT_IDS"), os.getenv("GITLAB_BRANCHES")))

# E-PROJET (remplace OrangeScrum) — identifiants par défaut repris de OSCRUM_* si non définis
EPROJET_URL      = os.getenv("EPROJET_URL", "https://e-projet.synelia.tech/EProjet-1")
EPROJET_USERNAME = os.getenv("EPROJET_USERNAME") or OSCRUM_USERNAME
EPROJET_PASSWORD = get_secret("EPROJET_PASSWORD") or OSCRUM_PASSWORD
# Projet par défaut : réunions, activités génériques, dépôts sans règle de correspondance
EPROJET_PROJECT_ID      = os.getenv("EPROJET_PROJECT_ID")
EPROJET_RESP_EXTERNE    = os.getenv("EPROJET_RESP_EXTERNE")
EPROJET_TYPE_TACHE_ID   = os.getenv("EPROJET_TYPE_TACHE_ID", "-3")         # Developpement
EPROJET_TYPE_TACHE_REUNION_ID = os.getenv("EPROJET_TYPE_TACHE_REUNION_ID", "-4")  # Projet (réunions Outlook)
EPROJET_STATUT_TACHE_ID = os.getenv("EPROJET_STATUT_TACHE_ID", "-3")       # En cours (à la création)
EPROJET_STATUT_TERMINEE_ID = os.getenv("EPROJET_STATUT_TERMINEE_ID", "-4") # Terminée (après saisie des heures)

# Calendrier Outlook (Exchange on-premise, EWS) — réunions ignorées si EXCHANGE_EMAIL/PASSWORD vides
EXCHANGE_SERVER   = os.getenv("EXCHANGE_SERVER", "exchmail.orange-cit.ci")
EXCHANGE_EMAIL    = os.getenv("EXCHANGE_EMAIL")
EXCHANGE_USERNAME = os.getenv("EXCHANGE_USERNAME")  # ex: DOMAINE\login — si vide, EXCHANGE_EMAIL est utilisé
EXCHANGE_PASSWORD = get_secret("EXCHANGE_PASSWORD")

# Source des tâches : "gitlab" (commits), "outlook" (réunions du calendrier) ou "both" (les deux)
TASK_SOURCE = _choice("TASK_SOURCE", "gitlab", ("gitlab", "outlook", "both"))

# Correspondance dépôts GitLab → projets E-PROJET (taskRefinings/projectMapping.py), ex. « miniapp/*=12;406=34 ».
# Vide : ancienne configuration reprise (projets de GITLAB_PROJECTS → projet par défaut)
from taskRefinings.projectMapping import parse_mapping as _parse_mapping, rules_from_projects as _rules_from_projects

PROJECT_MAPPING = (_parse_mapping(os.getenv("PROJECT_MAPPING"))
                   or _rules_from_projects(GITLAB_PROJECTS, EPROJET_PROJECT_ID))

# Activités génériques (jours sans commit ni réunion), séparées par des « ; » — vide = liste par défaut
GENERIC_TASKS = [t.strip() for t in os.getenv("GENERIC_TASKS", "").split(";") if t.strip()]
