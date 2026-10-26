"""Capture d'écran et page HTML au moment d'un échec du RPA, dans le dossier des journaux"""
import os
from datetime import datetime

from app_paths import LOGS_DIR


def save_failure(page, name: str):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        base = os.path.join(LOGS_DIR, f"echec_{name}_{datetime.now():%Y%m%d_%H%M%S}")
        page.screenshot(path=f"{base}.png", full_page=True)
        with open(f"{base}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"📸 Capture de l'échec : {base}.png (+ .html) — page {page.url}")
    except Exception as e:  # la capture ne doit pas masquer l'erreur d'origine
        print(f"(capture impossible : {e})")
