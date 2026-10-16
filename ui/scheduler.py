"""Programmation des jours ouvrés : notification à 17h55, exécution à 18h00.
macOS : launchd (~/Library/LaunchAgents) · Windows : Planificateur de tâches (schtasks).
Les deux tâches sont sautées si l'exécution du jour est déjà faite (marqueur last_run)."""
import os
import plistlib
import shlex
import subprocess
from datetime import datetime, timedelta

from app_paths import DATA_DIR, IS_MAC, IS_WINDOWS, LOGS_DIR, entry_command, with_extra_path
from taskProvider.gitlab.syncState import LAST_RUN_FILE, get_last_run

WEEKDAYS = range(1, 6)  # lundi → vendredi (isoweekday)
NOTIFY_TIME = (17, 55)
RUN_TIME = (18, 0)


# ── macOS : launchd ─────────────────────────────────────────
AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
NOTIFY_LABEL = "tech.synelia.eprojet-rpa.notify"
RUN_LABEL = "tech.synelia.eprojet-rpa.run"


def _plist_path(label: str) -> str:
    return os.path.join(AGENTS_DIR, f"{label}.plist")


def _calendar(hour: int, minute: int) -> list:
    return [{"Weekday": d, "Hour": hour, "Minute": minute} for d in WEEKDAYS]


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _notify_plist() -> dict:
    # Commande autonome (sans fichier du projet) : lisible par launchd même si le projet est dans ~/Documents
    applescript = ('display notification "Le RPA démarre dans 5 minutes (18h00). Enregistre ton travail." '
                   'with title "RPA Timesheet" sound name "Glass"')
    command = (f'[ "$(cat {shlex.quote(LAST_RUN_FILE)} 2>/dev/null)" = "$(date +%F)" ] '
               f'|| /usr/bin/osascript -e {shlex.quote(applescript)}')
    return {"Label": NOTIFY_LABEL, "ProgramArguments": ["/bin/zsh", "-c", command],
            "StartCalendarInterval": _calendar(*NOTIFY_TIME)}


def _run_plist() -> dict:
    logs = os.path.join(LOGS_DIR, "launchd.log")
    return {"Label": RUN_LABEL, "ProgramArguments": entry_command("--scheduled"), "WorkingDirectory": DATA_DIR,
            "EnvironmentVariables": {"PATH": with_extra_path("/usr/bin:/bin:/usr/sbin:/sbin")},
            "StandardOutPath": logs, "StandardErrorPath": logs,
            "StartCalendarInterval": _calendar(*RUN_TIME)}


def _mac_install():
    os.makedirs(AGENTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    for label, plist in ((NOTIFY_LABEL, _notify_plist()), (RUN_LABEL, _run_plist())):
        path = _plist_path(label)
        subprocess.run(["launchctl", "bootout", _domain(), path], capture_output=True)
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        subprocess.run(["launchctl", "bootstrap", _domain(), path], check=True, capture_output=True)


def _mac_uninstall():
    for label in (NOTIFY_LABEL, RUN_LABEL):
        path = _plist_path(label)
        subprocess.run(["launchctl", "bootout", _domain(), path], capture_output=True)
        if os.path.exists(path):
            os.remove(path)


def _mac_is_installed() -> bool:
    return subprocess.run(["launchctl", "print", f"{_domain()}/{RUN_LABEL}"], capture_output=True).returncode == 0


# ── Windows : Planificateur de tâches ───────────────────────
WIN_NOTIFY_TASK = r"RPA Timesheet\Notification"
WIN_RUN_TASK = r"RPA Timesheet\Execution"
WIN_DAYS = "MON,TUE,WED,THU,FRI"


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _win_install():
    for task, (hour, minute), mode in ((WIN_NOTIFY_TASK, NOTIFY_TIME, "--notify-upcoming"),
                                       (WIN_RUN_TASK, RUN_TIME, "--scheduled")):
        r = _schtasks("/Create", "/F", "/TN", task, "/TR", subprocess.list2cmdline(entry_command(mode)),
                      "/SC", "WEEKLY", "/D", WIN_DAYS, "/ST", f"{hour:02d}:{minute:02d}")
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or r.stdout.strip())


def _win_uninstall():
    for task in (WIN_NOTIFY_TASK, WIN_RUN_TASK):
        _schtasks("/Delete", "/F", "/TN", task)


def _win_is_installed() -> bool:
    return _schtasks("/Query", "/TN", WIN_RUN_TASK).returncode == 0


# ── API commune ─────────────────────────────────────────────
def install():
    if IS_WINDOWS:
        _win_install()
    elif IS_MAC:
        _mac_install()
    else:
        raise RuntimeError("Programmation disponible uniquement sur macOS et Windows")


def uninstall():
    if IS_WINDOWS:
        _win_uninstall()
    elif IS_MAC:
        _mac_uninstall()


def is_installed() -> bool:
    if IS_WINDOWS:
        return _win_is_installed()
    return IS_MAC and _mac_is_installed()


def next_run() -> datetime | None:
    """Prochaine exécution programmée (en sautant aujourd'hui si déjà exécuté ou 18h passée)"""
    if not is_installed():
        return None
    now = datetime.now()
    day = now.date()
    for _ in range(8):
        run_at = datetime(day.year, day.month, day.day, *RUN_TIME)
        already_done = day.isoformat() == get_last_run()
        if day.isoweekday() in WEEKDAYS and run_at > now and not already_done:
            return run_at
        day += timedelta(days=1)
    return None
