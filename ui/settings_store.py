"""Lecture / écriture de la configuration : réglages dans .env, secrets dans le Trousseau macOS."""
import os

import secret_vault
from dotenv import dotenv_values, set_key, unset_key

from config import ENV_PATH, SECRET_KEYS

# Valeurs proposées quand rien n'est encore configuré
DEFAULTS = {
    "TASK_SOURCE": "gitlab",
    "TASK_REFINER": "claude",
    "TIMESHEET_TARGET": "eprojet",
    "OSCRUM_URL": "https://orangescrum.synelia.tech",
    "OSCRUM_TASK_TYPE_ID": "10",
    "OSCRUM_ASSIGNEE_ID": "289",
    "EPROJET_TYPE_TACHE_ID": "-3",
    "EPROJET_TYPE_TACHE_REUNION_ID": "-4",
    "CLAUDE_CLI_PATH": "claude",
    "GEMINI_MODEL": "gemini-flash-latest",
    "MISTRAL_AGENT_ID": "ag_019f0512d57473a3b28830cbd2517270",
    "MISTRAL_AGENT_VERSION": "3",
    "GITLAB_URL": "https://gitlab.orange.bf/api/v4",
    "GITLAB_AUTHOR": "SAWADOGO Yves Dieudonne",
    "GITLAB_BRANCHES": "preprod",
    "GITLAB_PROJECT_IDS": "406,404,414,429,415,531,622",
    "EXCHANGE_SERVER": "exchmail.orange-cit.ci",
    "EPROJET_URL": "https://e-projet.synelia.tech/EProjet-1",
    "EPROJET_PROJECT_ID": "836",
    "EPROJET_RESP_EXTERNE": "KAMBOU Serge",
}

FIELDS = (
    "TASK_SOURCE", "TASK_REFINER",
    "CLAUDE_CLI_PATH", "CLAUDE_MODEL",
    "GEMINI_API_KEY", "GEMINI_MODEL",
    "MISTRAL_API_KEY", "MISTRAL_AGENT_ID", "MISTRAL_AGENT_VERSION",
    "GITLAB_URL", "GITLAB_AUTHOR", "GITLAB_BRANCHES", "GITLAB_PROJECT_IDS", "GITLAB_TOKEN",
    "EXCHANGE_SERVER", "EXCHANGE_EMAIL", "EXCHANGE_USERNAME", "EXCHANGE_PASSWORD",
    "TIMESHEET_TARGET",
    "EPROJET_URL", "EPROJET_USERNAME", "EPROJET_PASSWORD", "EPROJET_PROJECT_ID", "EPROJET_RESP_EXTERNE",
    "EPROJET_TYPE_TACHE_ID", "EPROJET_TYPE_TACHE_REUNION_ID",
    "OSCRUM_URL", "OSCRUM_USERNAME", "OSCRUM_PASSWORD", "OSCRUM_PROJECT", "OSCRUM_TASK_TYPE_ID", "OSCRUM_ASSIGNEE_ID",
)


def load() -> dict:
    env = dotenv_values(ENV_PATH) if os.path.exists(ENV_PATH) else {}
    secrets = secret_vault.load(SECRET_KEYS)
    values = {}
    for key in FIELDS:
        if key in SECRET_KEYS:
            values[key] = secrets.get(key) or env.get(key) or ""
        else:
            values[key] = env.get(key) or DEFAULTS.get(key, "")
    # Ancienne configuration OrangeScrum reprise si E-PROJET n'est pas encore renseigné
    values["EPROJET_USERNAME"] = values["EPROJET_USERNAME"] or env.get("OSCRUM_USERNAME") or ""
    values["EPROJET_PASSWORD"] = values["EPROJET_PASSWORD"] or values["OSCRUM_PASSWORD"]
    return values


def save(values: dict):
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "w").close()
    # tous les secrets dans un seul élément du trousseau (une seule autorisation macOS)
    secret_vault.save({k: (values.get(k) or "").strip() for k in SECRET_KEYS})
    env = dotenv_values(ENV_PATH)
    for key in FIELDS:
        if key in SECRET_KEYS:
            if key in env:
                unset_key(ENV_PATH, key)  # le secret ne reste pas en clair dans .env
        else:
            set_key(ENV_PATH, key, (values.get(key) or "").strip(), quote_mode="never")
    set_key(ENV_PATH, "UI_CONFIGURED", "1", quote_mode="never")


def is_configured() -> bool:
    return os.path.exists(ENV_PATH) and dotenv_values(ENV_PATH).get("UI_CONFIGURED") == "1"
