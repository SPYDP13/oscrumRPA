"""Coffre des secrets (tokens, mots de passe, clés API) : UN SEUL élément dans le Trousseau macOS / le Gestionnaire
d'identification Windows, contenant tous les secrets en JSON.

Un élément par secret obligeait macOS à demander une autorisation par secret ; avec un seul élément, l'application
ne demande l'accès qu'une fois (« Toujours autoriser »). Lu une seule fois par processus."""
import json

SERVICE = "eprojet-rpa"
VAULT_KEY = "secrets"
_cache = None


def _keyring():
    import keyring
    return keyring


def load(legacy_keys: tuple = ()) -> dict:
    """Tous les secrets. Migre au besoin les anciens éléments séparés (un par secret) vers le coffre unique."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = _keyring().get_password(SERVICE, VAULT_KEY)
        _cache = json.loads(raw) if raw else _migrate(legacy_keys)
    except Exception as e:  # accès refusé, trousseau indisponible… → repli sur le .env
        print(f"(trousseau indisponible : {e.__class__.__name__})")
        _cache = {}
    return _cache


def save(values: dict):
    """Remplace le contenu du coffre (les secrets vides sont retirés)"""
    global _cache
    secrets = {k: v for k, v in values.items() if v}
    _keyring().set_password(SERVICE, VAULT_KEY, json.dumps(secrets))
    _cache = secrets


def _migrate(legacy_keys: tuple) -> dict:
    kr = _keyring()
    secrets = {}
    for key in legacy_keys:
        value = kr.get_password(SERVICE, key)
        if value:
            secrets[key] = value
    if secrets:
        kr.set_password(SERVICE, VAULT_KEY, json.dumps(secrets))
        for key in secrets:
            try:
                kr.delete_password(SERVICE, key)
            except Exception:
                pass
    return secrets
