"""Construit l'application avec PyInstaller, sur la machine cible :
  macOS   → dist/RPA Timesheet.app
  Windows → dist/RPA Timesheet/RPA Timesheet.exe   (PyInstaller ne compile pas pour un autre système)

Usage : python build.py
Le navigateur Chromium n'est pas inclus : l'application le télécharge au premier lancement.
"""
import os
import shutil
import sys

import PyInstaller.__main__

APP_NAME = "RPA Timesheet"
ROOT = os.path.dirname(os.path.abspath(__file__))
SEP = os.pathsep  # séparateur source/destination de --add-data (« : » sur macOS, « ; » sous Windows)

args = [
    os.path.join(ROOT, "rpa_timesheet.py"),
    "--name", APP_NAME,
    "--windowed",                      # pas de console (.app sur macOS)
    "--noconfirm", "--clean",
    "--distpath", os.path.join(ROOT, "dist"),
    "--workpath", os.path.join(ROOT, "build"),
    "--specpath", os.path.join(ROOT, "build"),
    # ressources lues à l'exécution (app_paths.resource)
    "--add-data", f"{os.path.join(ROOT, 'certs')}{SEP}certs",
    "--add-data", f"{os.path.join(ROOT, 'ui', 'assets')}{SEP}ui/assets",
    # modules chargés dynamiquement (choix de l'IA et du timesheet, backends du trousseau)
    "--hidden-import", "taskRefinings.ClaudeTaskRefiner",
    "--hidden-import", "taskRefinings.GeminiTaskRefiner",
    "--hidden-import", "taskRefinings.MistralTaskRefiner",
    "--hidden-import", "RPA.EProjetRpa",
    "--hidden-import", "RPA.OrangeScrumRpa",
    "--collect-submodules", "keyring.backends",
    "--collect-data", "tzdata",          # fuseaux horaires (Windows n'en fournit pas à Python)
    "--collect-data", "exchangelib",
    "--collect-data", "certifi",
    # inutiles et volumineux
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
]
if sys.platform == "darwin":
    args += ["--osx-bundle-identifier", "tech.synelia.rpa-timesheet"]

if __name__ == "__main__":
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    PyInstaller.__main__.run(args)
    target = f"dist/{APP_NAME}.app" if sys.platform == "darwin" else f"dist/{APP_NAME}/{APP_NAME}.exe"
    print(f"\n✅ Application construite : {target}")
