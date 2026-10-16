"""Notifications système : Centre de notifications sur macOS, notification de la barre des tâches sous Windows."""
import subprocess

from app_paths import IS_MAC, IS_WINDOWS


def notify(title: str, message: str):
    try:
        if IS_MAC:
            script = f'display notification "{_escape(message)}" with title "{_escape(title)}" sound name "Glass"'
            subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, timeout=10)
        elif IS_WINDOWS:
            _notify_qt(title, message)
    except Exception as e:  # une notification ratée ne doit jamais faire échouer l'exécution
        print(f"(notification impossible : {e})")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _notify_qt(title: str, message: str):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    app = QApplication.instance() or QApplication([])
    pix = QPixmap(32, 32)
    pix.fill(QColor("#2563eb"))
    tray = QSystemTrayIcon(QIcon(pix))
    tray.show()
    tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 8000)
    QTimer.singleShot(9000, app.quit)
    app.exec()
    tray.hide()
