# /Users/yves/Documents/personnel/brvm/OrangeScrumRpa/config.py

import os
from dotenv import load_dotenv

load_dotenv()  # Charge automatiquement le fichier .env

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID", "ag_019f0512d57473a3b28830cbd2517270")
MISTRAL_AGENT_VERSION = int(os.getenv("MISTRAL_AGENT_VERSION", "3"))
CLAUDE_CLI_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
CLAUDE_MODEL    = os.getenv("CLAUDE_MODEL")  # ex: "sonnet", "opus" — None = modele par defaut du CLI
GITLAB_TOKEN    = os.getenv("GITLAB_TOKEN")
OSCRUM_USERNAME = os.getenv("OSCRUM_USERNAME")
OSCRUM_PASSWORD = os.getenv("OSCRUM_PASSWORD")
OSCRUM_PROJECT = os.getenv("OSCRUM_PROJECT")

# E-PROJET (remplace OrangeScrum) — identifiants par défaut repris de OSCRUM_* si non définis
EPROJET_URL      = os.getenv("EPROJET_URL", "https://e-projet.synelia.tech/EProjet-1")
EPROJET_USERNAME = os.getenv("EPROJET_USERNAME") or OSCRUM_USERNAME
EPROJET_PASSWORD = os.getenv("EPROJET_PASSWORD") or OSCRUM_PASSWORD
EPROJET_PROJECT_ID      = os.getenv("EPROJET_PROJECT_ID", "836")           # OBF | ORANGE CONNECT
EPROJET_RESP_EXTERNE    = os.getenv("EPROJET_RESP_EXTERNE", "KAMBOU Serge")
EPROJET_TYPE_TACHE_ID   = os.getenv("EPROJET_TYPE_TACHE_ID", "-3")         # Developpement
EPROJET_TYPE_TACHE_REUNION_ID = os.getenv("EPROJET_TYPE_TACHE_REUNION_ID", "-4")  # Projet (réunions Outlook)
EPROJET_STATUT_TACHE_ID = os.getenv("EPROJET_STATUT_TACHE_ID", "-3")       # En cours (à la création)
EPROJET_STATUT_TERMINEE_ID = os.getenv("EPROJET_STATUT_TERMINEE_ID", "-4") # Terminée (après saisie des heures)

# Calendrier Outlook (Exchange on-premise, EWS) — réunions ignorées si EXCHANGE_EMAIL/PASSWORD vides
EXCHANGE_SERVER   = os.getenv("EXCHANGE_SERVER", "exchmail.orange-cit.ci")
EXCHANGE_EMAIL    = os.getenv("EXCHANGE_EMAIL")
EXCHANGE_USERNAME = os.getenv("EXCHANGE_USERNAME")  # ex: DOMAINE\login — si vide, EXCHANGE_EMAIL est utilisé
EXCHANGE_PASSWORD = os.getenv("EXCHANGE_PASSWORD")

# Source des tâches : "gitlab" (commits), "outlook" (réunions du calendrier) ou "both" (les deux)
TASK_SOURCE = os.getenv("TASK_SOURCE", "gitlab").strip().lower()
if TASK_SOURCE not in ("gitlab", "outlook", "both"):
    raise ValueError(f"TASK_SOURCE invalide : '{TASK_SOURCE}' (attendu : gitlab, outlook ou both)")
