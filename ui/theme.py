"""Thème visuel de l'interface (style Fusion + feuille de style Qt)."""
from app_paths import resource

# Avec une feuille de style, Qt ne dessine plus la flèche des listes : on fournit l'icône
CHEVRON = resource("ui", "assets", "chevron-down.svg").replace("\\", "/")

ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
BG = "#f4f6fa"
SURFACE = "#ffffff"
BORDER = "#dde3ec"
TEXT = "#111827"
MUTED = "#6b7280"
SUCCESS = "#15803d"
SUCCESS_BG = "#dcfce7"
ERROR = "#b91c1c"
ERROR_BG = "#fee2e2"
INFO_BG = "#e0e7ff"

STYLESHEET = f"""
* {{ font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, #page {{ background: {BG}; }}

/* ── Titres ─────────────────────────────── */
#h1 {{ font-size: 22px; font-weight: 700; }}
#h2 {{ font-size: 17px; font-weight: 700; }}
#subtitle, #hint {{ color: {MUTED}; }}
#hint {{ font-size: 12px; }}
#fieldLabel {{ font-weight: 600; font-size: 12px; color: #374151; }}

/* ── Cartes ─────────────────────────────── */
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }}
#cardValue {{ font-size: 15px; font-weight: 600; }}

/* ── Champs ─────────────────────────────── */
QLineEdit, QDateEdit {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 10px; min-height: 18px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QDateEdit:focus {{ border: 2px solid {ACCENT}; padding: 7px 9px; }}
QComboBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px; min-height: 22px;
    combobox-popup: 0;
}}
QComboBox:focus {{ border: 2px solid {ACCENT}; }}
QComboBox QLineEdit {{ border: none; padding: 0; background: transparent; }}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; border: none; width: 28px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{CHEVRON}"); width: 14px; height: 14px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER}; selection-background-color: #eff6ff;
    selection-color: {ACCENT}; padding: 4px; outline: none;
}}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 2px 8px; border-radius: 6px; }}

/* ── Boutons ────────────────────────────── */
QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: #eef2f7; }}
QPushButton:disabled {{ color: #9ca3af; background: #f3f4f6; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #93c5fd; color: white; }}
QPushButton#danger {{ color: {ERROR}; }}
QPushButton#choice {{ padding: 14px; text-align: left; border-radius: 10px; }}
QPushButton#choice:checked {{ border: 2px solid {ACCENT}; background: #eff6ff; color: {ACCENT}; }}

/* ── Cases à cocher ─────────────────────── */
QCheckBox {{ spacing: 10px; font-size: 14px; padding: 6px 0; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}

/* ── Barre latérale de l'assistant ─────── */
#sidebar {{ background: #111827; }}
#sidebar QLabel {{ color: #d1d5db; }}
#sidebarTitle {{ color: white; font-size: 16px; font-weight: 700; }}
#step {{ color: #9ca3af; padding: 8px 12px; border-radius: 8px; font-size: 13px; }}
#stepActive {{ color: white; background: {ACCENT}; padding: 8px 12px; border-radius: 8px;
               font-size: 13px; font-weight: 600; }}
#stepDone {{ color: #d1d5db; padding: 8px 12px; border-radius: 8px; font-size: 13px; }}
#footer {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}

/* ── Messages de test ───────────────────── */
#ok {{ background: {SUCCESS_BG}; color: {SUCCESS}; border-radius: 8px; padding: 10px; }}
#ko {{ background: {ERROR_BG}; color: {ERROR}; border-radius: 8px; padding: 10px; }}
#pending {{ background: {INFO_BG}; color: #3730a3; border-radius: 8px; padding: 10px; }}

/* ── Journal ────────────────────────────── */
QPlainTextEdit#log {{
    background: #0f172a; color: #e2e8f0; border: none; border-radius: 12px; padding: 10px;
    font-family: Menlo, monospace; font-size: 12px;
}}
QScrollArea {{ border: none; background: transparent; }}
"""
