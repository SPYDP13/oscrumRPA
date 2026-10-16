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
APP_VERSION = "1.0.0"                  # à incrémenter à chaque version distribuée
COMPANY = "Synelia"
DESCRIPTION = "Remplissage automatique du timesheet (E-PROJET / OrangeScrum)"
ROOT = os.path.dirname(os.path.abspath(__file__))
SEP = os.pathsep  # séparateur source/destination de --add-data (« : » sur macOS, « ; » sous Windows)

args = [
    os.path.join(ROOT, "rpa_timesheet.py"),
    "--name", APP_NAME,
    "--windowed",                      # pas de console (.app sur macOS)
    "--noconfirm", "--clean",
    "--noupx",                         # exécutable compressé par UPX = davantage de détections antivirus
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

VERSION_FILE = os.path.join(ROOT, "build", "version_info.txt")
if sys.platform == "win32":
    args += ["--version-file", VERSION_FILE]


def write_version_file():
    """Informations affichées dans Propriétés → Détails du .exe (éditeur, version…) : un exécutable sans éditeur ni
    version est jugé plus suspect par les antivirus."""
    numbers = tuple(int(n) for n in APP_VERSION.split(".")) + (0,) * (4 - len(APP_VERSION.split(".")))
    strings = {
        "CompanyName": COMPANY,
        "FileDescription": DESCRIPTION,
        "FileVersion": APP_VERSION,
        "InternalName": APP_NAME,
        "LegalCopyright": f"© {COMPANY}",
        "OriginalFilename": f"{APP_NAME}.exe",
        "ProductName": APP_NAME,
        "ProductVersion": APP_VERSION,
    }
    entries = ",\n".join(f"          StringStruct({k!r}, {v!r})" for k, v in strings.items())
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040C04B0', [
{entries}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
""")

if __name__ == "__main__":
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    if sys.platform == "win32":
        write_version_file()
    PyInstaller.__main__.run(args)
    target = f"dist/{APP_NAME}.app" if sys.platform == "darwin" else f"dist/{APP_NAME}/{APP_NAME}.exe"
    print(f"\n✅ Application construite : {target}")
