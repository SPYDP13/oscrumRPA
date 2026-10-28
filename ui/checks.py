"""Tests de connexion lancés depuis l'assistant. Chaque fonction renvoie un message ou lève une exception."""
from urllib.parse import quote

import requests


def check_gitlab(url: str, token: str) -> str:
    headers = {"PRIVATE-TOKEN": token}
    r = requests.get(f"{url}/user", headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Token refusé ({r.status_code})")
    ev = requests.get(f"{url}/events", headers=headers, params={"action": "pushed", "per_page": 1}, timeout=15)
    if not ev.ok:
        raise RuntimeError(f"Connecté en tant que {r.json().get('name')}, mais la détection des dépôts est impossible "
                           f"({ev.status_code}) : vérifie le scope read_api du token")
    return f"Connecté en tant que {r.json().get('name')} — détection des dépôts disponible"


def check_exchange(server: str, email: str, username: str, password: str) -> str:
    from exchangelib import Account, Configuration, Credentials, DELEGATE
    from taskProvider.outlook.outlookCalendarExtractor import _install_ca_bundle

    _install_ca_bundle()
    config = Configuration(server=server, credentials=Credentials(username=username or email, password=password))
    account = Account(primary_smtp_address=email, config=config, autodiscover=False, access_type=DELEGATE)
    return f"Calendrier « {account.calendar.name} » accessible ({account.calendar.total_count} éléments)"


def check_eprojet(url: str, username: str, password: str) -> str:
    from ui.catalog import eprojet_session
    eprojet_session(url.rstrip("/"), username, password)
    return "Connexion E-PROJET réussie"


TEST_PROMPT = "Réponds uniquement par le mot OK."


def check_claude(cli_path: str, model: str) -> str:
    from taskRefinings.ClaudeTaskRefiner import ClaudeTaskRefiner
    answer = ClaudeTaskRefiner.ask(TEST_PROMPT, cli_path or "claude", model or None, timeout=120)
    return f"Claude répond : « {answer[:60]} »"


def check_gemini(api_key: str, model: str) -> str:
    from taskRefinings.GeminiTaskRefiner import GeminiTaskRefiner
    answer = GeminiTaskRefiner.ask(TEST_PROMPT, api_key, model or None)
    return f"Gemini ({model or 'gemini-flash-latest'}) répond : « {answer[:60]} »"


def check_mistral(api_key: str, agent_id: str, agent_version: str) -> str:
    from taskRefinings.MistralTaskRefiner import MistralTaskRefiner
    answer = MistralTaskRefiner.ask(TEST_PROMPT, api_key, agent_id, agent_version or None)
    return f"Agent Mistral répond : « {answer[:60]} »"


def check_orangescrum(url: str, username: str, password: str) -> str:
    from ui.catalog import orangescrum_session
    orangescrum_session(url.rstrip("/"), username, password)
    return "Connexion OrangeScrum réussie"
