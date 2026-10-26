"""Navigateur Chromium de Playwright : non inclus dans l'application packagée, téléchargé au premier lancement
dans les données utilisateur (PLAYWRIGHT_BROWSERS_PATH, défini par app_paths)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from app_paths import BROWSERS_DIR, FROZEN, IS_WINDOWS


def _chromium_revision() -> str:
    import playwright
    browsers = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    return next(b["revision"] for b in json.loads(browsers.read_text())["browsers"] if b["name"] == "chromium")


def _revision_dir() -> Path:
    return Path(BROWSERS_DIR) / f"chromium-{_chromium_revision()}"


def is_installed() -> bool:
    """Vérifie l'exécutable lui-même : le dossier et le marqueur INSTALLATION_COMPLETE de Playwright peuvent
    survivre à la suppression du navigateur (nettoyage macOS, antivirus…)"""
    if not FROZEN:
        return True  # en développement : navigateur installé par `playwright install` (cache par défaut)
    folder = _revision_dir()
    patterns = ("chrome-win*/chrome.exe",) if IS_WINDOWS else ("chrome-mac*/*.app/Contents/MacOS/*", "chrome-linux*/chrome")
    return any(any(folder.glob(pattern)) for pattern in patterns)


def install(output=print, force: bool = False) -> bool:
    """Télécharge Chromium (≈ 150 Mo) ; output reçoit chaque ligne de progression.
    Une installation cassée (ou force=True) est d'abord supprimée : Playwright la croirait complète à cause de son marqueur.
    --no-shell : pas de « Chrome Headless Shell » (≈ 250 Mo), inutile car le RPA ouvre un navigateur visible"""
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    os.makedirs(BROWSERS_DIR, exist_ok=True)
    if (force or not is_installed()) and _revision_dir().exists():
        shutil.rmtree(_revision_dir(), ignore_errors=True)
    node, cli = compute_driver_executable()
    proc = subprocess.Popen([node, cli, "install", "--no-shell", "chromium"], env=get_driver_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
    for line in proc.stdout:
        output(line.rstrip())
    return proc.wait() == 0


def launch_test() -> str:
    """Démarre réellement Chromium (sans fenêtre) pour vérifier l'installation"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chromium")  # Chromium complet, sans le « headless shell »
        version = browser.version
        browser.close()
    return version
