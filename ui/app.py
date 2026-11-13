"""Interface PySide6 du RPA E-PROJET.

Lancement : .venv/bin/python rpa_timesheet.py (ou l'application packagée)
"""
import os
import re
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QDate, QProcess, QProcessEnvironment, Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap, QTextCursor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDateEdit, QListView, QDialog, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from dotenv import dotenv_values

import shutil

import browser_setup
import plan_store
from app_paths import DATA_DIR, FROZEN, LOGS_DIR, entry_command, with_extra_path
from config import ENV_PATH, SECRET_KEYS
from taskProvider.gitlab.syncState import get_last_run, get_last_since, set_resume_date
from taskRefinings import userContext
from taskRefinings.projectMapping import format_mapping, group_of, parse_mapping, resolve
from ui import catalog, checks, scheduler, settings_store
from ui.theme import STYLESHEET

SOURCE_LABELS = {"gitlab": "GitLab", "outlook": "Outlook", "both": "GitLab + Outlook"}
REFINER_LABELS = {"claude": "Claude", "gemini": "Gemini", "mistral": "Mistral"}
TIMESHEET_LABELS = {"eprojet": "E-PROJET", "orangescrum": "OrangeScrum"}
DAYS_FR = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def _label(text: str, name: str = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def _button(text: str, name: str = None) -> QPushButton:
    btn = QPushButton(text)
    if name:
        btn.setObjectName(name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _text_icon(text: str) -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setFont(QFont("Apple Color Emoji", 20))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pix)


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


# ─────────────────────────────────────────────────────────────
class Worker(QThread):
    """Exécute une fonction bloquante (test de connexion, chargement des listes) hors du thread de l'interface"""
    done = Signal(bool, object)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(True, self.fn(*self.args))
        except Exception as e:
            self.done.emit(False, str(e) or e.__class__.__name__)


# ─────────────────────────────────────────────────────────────
class Field(QWidget):
    """Libellé au-dessus, champ sur toute la largeur, aide en dessous ; œil pour les secrets"""

    def __init__(self, key: str, label: str, value: str, placeholder: str = "", hint: str = ""):
        super().__init__()
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if key in SECRET_KEYS:
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
            toggle = QAction(_text_icon("👁"), "Afficher", self.edit)
            toggle.setToolTip("Afficher / masquer")
            toggle.triggered.connect(lambda: self.edit.setEchoMode(
                QLineEdit.EchoMode.Normal if self.edit.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password))
            self.edit.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(label, "fieldLabel"))
        lay.addWidget(self.edit)
        if hint:
            lay.addWidget(_label(hint, "hint", wrap=True))

    def value(self) -> str:
        return self.edit.text().strip()


class Combo:
    """Spécification d'un champ liste déroulante, modifiable à la main (id saisi directement)"""

    def __init__(self, key: str, label: str, options: list, hint: str = ""):
        self.key, self.label, self.options, self.hint = key, label, options, hint


class WideComboBox(QComboBox):
    """La liste déroulante prend toute la largeur du champ (Qt la réduit sinon au texte le plus court)"""

    def showPopup(self):
        self.view().setMinimumWidth(self.width())
        super().showPopup()


class ComboField(QWidget):
    """Liste déroulante « libellé · id » ; la valeur enregistrée est l'id (ou le texte saisi à la main)"""

    def __init__(self, spec: Combo, value: str):
        super().__init__()
        self.combo = WideComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # liste déroulante classique sous le champ (et non la liste macOS centrée sur l'élément courant)
        self.combo.setView(QListView(self.combo))
        self.combo.setMaxVisibleItems(12)
        completer = self.combo.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # saisie « kam » → « KAMBOU Serge »
        completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
        self.set_options(spec.options, value)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_label(spec.label, "fieldLabel"))
        lay.addWidget(self.combo)
        if spec.hint:
            lay.addWidget(_label(spec.hint, "hint", wrap=True))

    def set_options(self, options: list, value: str = None):
        value = self.value() if value is None else value
        self.combo.blockSignals(True)
        self.combo.clear()
        for opt_value, opt_label in options:
            self.combo.addItem(opt_label if opt_label == opt_value else f"{opt_label}  ·  {opt_value}", opt_value)
        self.combo.blockSignals(False)
        self.set_value(value)

    def set_value(self, value: str):
        index = self.combo.findData(value)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        else:
            self.combo.setCurrentIndex(-1)
            self.combo.setEditText(value or "")

    def value(self) -> str:
        index = self.combo.currentIndex()
        if index >= 0 and self.combo.itemText(index) == self.combo.currentText():
            return str(self.combo.itemData(index))
        return self.combo.currentText().strip()


class FormSection(QWidget):
    """Groupe de champs + « Tester la connexion » et, si possible, « Charger les listes » depuis la plateforme"""

    def __init__(self, fields: list, values: dict, check=None, loader=None, depends: dict = None):
        """loader : fonction(valeurs) → {clé: [(id, libellé)]} ou {clé: {valeur_parent: [(id, libellé)]}}
        depends : {clé_enfant: clé_parent} — la liste enfant suit la valeur choisie dans la liste parent"""
        super().__init__()
        self.fields = {}
        self.check, self.loader = check, loader
        self.depends = depends or {}
        self.dependent_options = {}
        self.worker = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        for spec in fields:
            if isinstance(spec, Combo):
                field = ComboField(spec, values.get(spec.key, ""))
                key = spec.key
            else:
                key, label, placeholder, *hint = spec
                field = Field(key, label, values.get(key, ""), placeholder, hint[0] if hint else "")
            self.fields[key] = field
            lay.addWidget(field)

        for child, parent in self.depends.items():
            self.fields[parent].combo.currentIndexChanged.connect(lambda _, c=child: self._update_dependent(c))

        if check or loader:
            row = QHBoxLayout()
            self.buttons = []
            if check:
                btn = _button("Tester la connexion")
                btn.clicked.connect(lambda: self._run(self.check, self._check_done, "⏳ Test en cours…"))
                self.buttons.append(btn)
                row.addWidget(btn)
            if loader:
                btn = _button("⟳  Charger les listes depuis la plateforme")
                btn.clicked.connect(lambda: self._run(self.loader, self._load_done, "⏳ Connexion et chargement des listes…"))
                self.buttons.append(btn)
                row.addWidget(btn)
            row.addStretch()
            self.result = _label("", wrap=True)
            self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.result.hide()
            lay.addSpacing(4)
            lay.addLayout(row)
            lay.addWidget(self.result)
        lay.addStretch()  # garde les champs groupés quand le formulaire est dans une pile plus haute

    def values(self) -> dict:
        return {k: f.value() for k, f in self.fields.items()}

    def _show(self, state: str, text: str):
        self.result.setObjectName(state)
        self.result.setText(text)
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)
        self.result.show()

    def _run(self, fn, on_done, pending: str):
        for b in self.buttons:
            b.setEnabled(False)
        self._show("pending", pending)
        self.worker = Worker(fn, self.values())
        self.worker.done.connect(on_done)
        self.worker.start()

    def _check_done(self, ok: bool, message):
        for b in self.buttons:
            b.setEnabled(True)
        self._show("ok" if ok else "ko", ("✓  " if ok else "✕  ") + str(message))

    def _load_done(self, ok: bool, data):
        for b in self.buttons:
            b.setEnabled(True)
        if not ok:
            self._show("ko", "✕  " + str(data))
            return
        for key, options in data.items():
            if key not in self.fields:
                continue
            if isinstance(options, dict):
                self.dependent_options[key] = options
            else:
                self.fields[key].set_options(options)
        for child in self.depends:
            self._update_dependent(child)
        self._show("ok", "✓  Listes chargées : " + data.get("_summary", ""))

    def _update_dependent(self, child: str):
        by_parent = self.dependent_options.get(child)
        if by_parent is not None:
            parent_value = self.fields[self.depends[child]].value()
            self.fields[child].set_options(by_parent.get(parent_value, []))


class Choice(QWidget):
    """Boutons-cartes exclusifs ; le formulaire de l'option choisie s'affiche dessous"""

    def __init__(self, options: dict, current: str):
        """options : {clé: (libellé du bouton, FormSection)}"""
        super().__init__()
        self.keys = list(options)
        self.forms = {k: form for k, (_, form) in options.items()}
        self.group = QButtonGroup(self)
        self.stack = QStackedWidget()
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        for i, (key, (label, form)) in enumerate(options.items()):
            btn = _button(label, "choice")
            btn.setCheckable(True)
            self.group.addButton(btn, i)
            buttons.addWidget(btn)
            self.stack.addWidget(form)
        self.group.idToggled.connect(lambda i, on: on and self.stack.setCurrentIndex(i))
        self.group.button(self.keys.index(current) if current in self.keys else 0).setChecked(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        lay.addLayout(buttons)
        lay.addWidget(self.stack)

    def current(self) -> str:
        return self.keys[max(0, self.group.checkedId())]


class StepPage(QScrollArea):
    """Page d'étape : titre, sous-titre, contenu défilant"""

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("page")
        self.content = QVBoxLayout(body)
        self.content.setContentsMargins(36, 32, 36, 24)
        self.content.setSpacing(16)
        self.content.addWidget(_label(title, "h2"))
        self.content.addWidget(_label(subtitle, "subtitle", wrap=True))
        self.content.addSpacing(6)
        self.setWidget(body)

    def finish(self):
        self.content.addStretch()


# ─────────────────────────────────────────────────────────────
class MappingEditor(QWidget):
    """Correspondance dépôts GitLab → projets E-PROJET. Une ligne par groupe (règle « groupe/* », sous-groupes
    compris) et une par dépôt (surcharge du groupe). Les dépôts viennent de la détection (événements GitLab) et des
    règles déjà enregistrées ; enregistré sous la forme miniapp/*=12;orange/ompi=34 (PROJECT_MAPPING)."""
    INHERIT = "__groupe__"
    COLS = ("Groupe / dépôt", "Commits (90 j)", "Projet E-PROJET")

    def __init__(self, value: str, gitlab_values, eprojet_values):
        """gitlab_values / eprojet_values : fonctions → valeurs actuelles des formulaires (même non enregistrées)"""
        super().__init__()
        self.gitlab_values, self.eprojet_values = gitlab_values, eprojet_values
        self.rules = parse_mapping(value)
        self.repos = []  # [{"id", "path", "name", "commits"}]
        self.projects = [tuple(p) for p in catalog.cached_eprojet().get("projects", [])]
        self.rows = []   # [(kind, clé, combo)] — kind : group | repo | rule
        self.worker = None

        self.btn_detect = _button("🔎  Détecter mes dépôts (90 derniers jours)")
        self.btn_projects = _button("⟳  Charger les projets E-PROJET")
        self.btn_detect.clicked.connect(self._detect)
        self.btn_projects.clicked.connect(self._load_projects)
        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_detect)
        buttons.addWidget(self.btn_projects)
        buttons.addStretch()
        self.status = _label("", "hint", wrap=True)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(300)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 300)
        self.preview = _label("", "hint", wrap=True)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addLayout(buttons)
        lay.addWidget(self.status)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.preview)
        self._rebuild()

    # ── Lignes ──────────────────────────────────────────────
    def _rebuild(self):
        rules = {p.lower(): t for p, t in self.rules}
        groups = {}  # groupe → [(chemin, id, commits)]
        for r in self.repos:
            groups.setdefault(group_of(r["path"]), []).append((r["path"], r["id"], r["commits"]))
        known_paths = {r["path"].lower() for r in self.repos} | {r["id"] for r in self.repos}
        others = []
        for pattern, _ in self.rules:
            p = pattern.lower()
            if p.endswith("/*") and not set(p[:-2]) & set("*?["):
                groups.setdefault(pattern[:-2], [])
            elif p.isdigit() or set(p) & set("*?["):
                if p not in known_paths:
                    others.append(pattern)
            elif p not in known_paths:
                groups.setdefault(group_of(pattern), []).append((pattern, "", None))

        self.table.setRowCount(0)
        self.rows = []
        bold = QFont()
        bold.setBold(True)
        for group in sorted(groups, key=str.lower):
            self._add_row("group", f"{group}/*", f"📁  {group or '(sans groupe)'}  —  tout le groupe",
                          sum(c or 0 for *_, c in groups[group]) or None, rules.get(f"{group}/*".lower(), ""), bold)
            for path, pid, commits in sorted(groups[group], key=lambda x: x[0].lower()):
                current = rules.get(path.lower()) or rules.get(pid) or self.INHERIT
                self._add_row("repo", path, f"        {path.rsplit('/', 1)[-1]}", commits, current, None, pid)
        for pattern in others:
            self._add_row("rule", pattern, f"Règle « {pattern} »", None, rules.get(pattern.lower(), ""), None)
        self._update_preview()

    def _add_row(self, kind: str, key: str, text: str, commits, current: str, font, pid: str = ""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        name = QTableWidgetItem(text)
        name.setFlags(Qt.ItemFlag.ItemIsEnabled)
        name.setToolTip(key + (f"  (id {pid})" if pid else ""))
        if font:
            name.setFont(font)
        count = QTableWidgetItem("" if commits is None else str(commits))
        count.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(row, 0, name)
        self.table.setItem(row, 1, count)

        combo = QComboBox()
        if kind == "repo":
            combo.addItem("↳ comme le groupe", self.INHERIT)
        else:
            combo.addItem("—  pas de règle", "")
        names = dict(self.projects)
        for project_id, project_name in self.projects:
            combo.addItem(f"{project_name} ({project_id})", project_id)
        if current and current != self.INHERIT and current not in names:
            combo.addItem(f"Projet {current}", current)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.currentIndexChanged.connect(self._update_preview)
        self.table.setCellWidget(row, 2, combo)
        self.rows.append((kind, key, combo))

    # ── Valeur ──────────────────────────────────────────────
    def value(self) -> str:
        rules = []
        for kind, key, combo in self.rows:
            target = combo.currentData()
            if target and target != self.INHERIT:
                rules.append((key, target))
        return format_mapping(rules)

    def _update_preview(self, *_):
        rules = parse_mapping(self.value())
        names = dict(self.projects)
        lines = [f"{len(rules)} règle(s) : " + ("  ·  ".join(f"{p} → {names.get(t, t)}" for p, t in rules) or "aucune")]
        unmapped = [r["path"] for r in self.repos if resolve(rules, r["id"], r["path"]) is None]
        if unmapped:
            lines.append(f"⚠️ {len(unmapped)} dépôt(s) sans projet → rangé(s) dans ton projet principal : "
                         + ", ".join(p.rsplit('/', 1)[-1] for p in unmapped[:8]) + (" …" if len(unmapped) > 8 else ""))
        resp = (self.eprojet_values() or {}).get("EPROJET_RESP_EXTERNE", "")
        resp_lists = catalog.cached_eprojet().get("resp", {})
        missing = [names.get(t, t) for t in dict.fromkeys(t for _, t in rules)
                   if resp and t in resp_lists and resp not in [n for n, _ in resp_lists[t]]]
        if missing:
            lines.append(f"⚠️ Le responsable externe « {resp} » n'est pas rattaché à : {', '.join(missing)}. "
                         "La saisie échouera pour ces projets.")
        self.preview.setText("\n".join(lines))

    # ── Actions ─────────────────────────────────────────────
    def _busy(self, text: str):
        self.rules = parse_mapping(self.value())  # garde les choix en cours avant de reconstruire
        self.btn_detect.setEnabled(False)
        self.btn_projects.setEnabled(False)
        self.status.setText(text)

    def _idle(self, text: str):
        self.btn_detect.setEnabled(True)
        self.btn_projects.setEnabled(True)
        self.status.setText(text)

    def _detect(self):
        g = self.gitlab_values()
        if not (g.get("GITLAB_URL") and g.get("GITLAB_TOKEN")):
            self.status.setText("✕  Renseigne d'abord l'URL et le token GitLab.")
            return
        self._busy("⏳ Lecture de tes événements GitLab…")
        from taskProvider.gitlab.gitlabLogExtrator import discover_projects
        self.worker = Worker(discover_projects, g["GITLAB_URL"].rstrip("/"), g["GITLAB_TOKEN"])
        self.worker.done.connect(self._detect_done)
        self.worker.start()

    def _detect_done(self, ok: bool, data):
        if not ok:
            self._idle(f"✕  {data}")
            return
        self.repos = data
        self._rebuild()
        self._idle(f"✓  {len(data)} dépôt(s) où tu as poussé ces 90 derniers jours. Choisis un projet par groupe, "
                   "et seulement si besoin un projet différent pour un dépôt.")

    def _load_projects(self):
        e = self.eprojet_values()
        if not (e.get("EPROJET_URL") and e.get("EPROJET_USERNAME") and e.get("EPROJET_PASSWORD")):
            self.status.setText("✕  Renseigne d'abord l'URL, le login et le mot de passe E-PROJET.")
            return
        self._busy("⏳ Connexion à E-PROJET et chargement des projets…")
        self.worker = Worker(catalog.fetch_eprojet, e)
        self.worker.done.connect(self._projects_done)
        self.worker.start()

    def _projects_done(self, ok: bool, data):
        if not ok:
            self._idle(f"✕  {data}")
            return
        self.projects = [tuple(p) for p in data.get("EPROJET_PROJECT_ID", [])]
        self._rebuild()
        self._idle(f"✓  {len(self.projects)} projet(s) E-PROJET.")


class MappingDialog(QDialog):
    """« Correspondances… » depuis le tableau de bord : modifiable à tout moment, sans repasser par l'assistant"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correspondances GitLab → E-PROJET")
        self.resize(900, 640)
        v = settings_store.load()
        self.editor = MappingEditor(v["PROJECT_MAPPING"], lambda: v, lambda: v)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(_label("Correspondances GitLab → E-PROJET", "h2"))
        lay.addWidget(_label(MAPPING_HELP, "subtitle", wrap=True))
        lay.addWidget(self.editor, 1)
        buttons = QHBoxLayout()
        cancel, ok = _button("Annuler"), _button("Enregistrer", "primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._save)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

    def _save(self):
        try:
            settings_store.save_keys({"PROJECT_MAPPING": self.editor.value()})
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible : {e}")
            return
        self.accept()


MAPPING_HELP = ("Chaque dépôt GitLab est saisi dans le projet E-PROJET choisi ici. Un projet sur un groupe couvre tous "
                "ses dépôts (sous-groupes compris) ; un dépôt peut avoir son propre projet. Un dépôt sans projet va "
                "dans ton projet principal (le plus utilisé ci-dessus) et est signalé dans le plan, où tu peux le changer.")


# ─────────────────────────────────────────────────────────────
class SetupDialog(QDialog):
    """Assistant de configuration : étapes à gauche, formulaire à droite"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration du RPA Timesheet")
        self.resize(940, 680)
        self.setMinimumSize(820, 600)
        v = settings_store.load()

        # ── 1. Sources
        sources = StepPage("Sources des tâches", "D'où viennent les tâches à saisir dans E-PROJET ? "
                           "Les réunions gardent leur durée réelle, le reste est complété jusqu'à 8 h par jour ouvré.")
        self.cb_gitlab = QCheckBox("GitLab  —  commits de tes projets")
        self.cb_outlook = QCheckBox("Outlook  —  réunions du calendrier Exchange")
        self.cb_gitlab.setChecked(v["TASK_SOURCE"] in ("gitlab", "both"))
        self.cb_outlook.setChecked(v["TASK_SOURCE"] in ("outlook", "both"))
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.addWidget(self.cb_gitlab)
        cl.addWidget(self.cb_outlook)
        sources.content.addWidget(card)
        sources.finish()

        # ── 2. Analyse IA
        refiner = StepPage("Analyse IA", "Le modèle rédige les libellés des tâches à partir des vrais commits. "
                           "Les heures sont calculées par l'application (8 h par jour), pas par le modèle.")
        self.refiner_choice = Choice({
            "claude": ("Claude\nCLI Claude Code", FormSection([
                ("CLAUDE_CLI_PATH", "Commande Claude Code", "claude",
                 "Utilise la connexion de ton CLI Claude Code : pas de clé API à saisir."),
                ("CLAUDE_MODEL", "Modèle", "vide = modèle par défaut du CLI", "Exemples : sonnet, opus"),
            ], v, check=lambda f: checks.check_claude(f["CLAUDE_CLI_PATH"], f["CLAUDE_MODEL"]))),
            "gemini": ("Gemini\nAPI Google", FormSection([
                ("GEMINI_API_KEY", "Clé API Gemini", "AIza…", "À créer sur aistudio.google.com/app/apikey"),
                ("GEMINI_MODEL", "Modèle", "gemini-flash-latest"),
            ], v, check=lambda f: checks.check_gemini(f["GEMINI_API_KEY"], f["GEMINI_MODEL"]))),
            "mistral": ("Mistral\nAgent Mistral", FormSection([
                ("MISTRAL_API_KEY", "Clé API Mistral", ""),
                ("MISTRAL_AGENT_ID", "Id de l'agent", "ag_…"),
                ("MISTRAL_AGENT_VERSION", "Version de l'agent", "vide = dernière version"),
            ], v, check=lambda f: checks.check_mistral(f["MISTRAL_API_KEY"], f["MISTRAL_AGENT_ID"],
                                                       f["MISTRAL_AGENT_VERSION"]))),
        }, v["TASK_REFINER"])
        refiner.content.addWidget(self.refiner_choice)
        refiner.finish()

        # ── 3. GitLab
        gitlab = StepPage("GitLab", "Les dépôts où tu as poussé sont détectés automatiquement, toutes branches "
                          "confondues. Tu les rattaches aux projets E-PROJET à l'étape Correspondances.")
        self.gitlab_form = FormSection([
            ("GITLAB_URL", "URL de l'API GitLab", "https://gitlab.exemple.com/api/v4"),
            ("GITLAB_AUTHOR", "Auteur des commits", "Nom tel qu'affiché dans GitLab"),
            ("GITLAB_TOKEN", "Token d'accès privé", "glpat-…", "GitLab → Préférences → Access Tokens, scope read_api."),
        ], v, check=lambda f: checks.check_gitlab(f["GITLAB_URL"], f["GITLAB_TOKEN"]))
        gitlab.content.addWidget(self.gitlab_form)
        gitlab.finish()
        self.gitlab_page = gitlab

        # ── 4. Outlook
        outlook = StepPage("Outlook", "Réunions du calendrier Exchange. Les réunions refusées, annulées, privées "
                           "et sur la journée entière sont ignorées.")
        self.outlook_form = FormSection([
            ("EXCHANGE_SERVER", "Serveur Exchange", "exchmail.exemple.com"),
            ("EXCHANGE_EMAIL", "Adresse mail", "prenom.nom@exemple.com"),
            ("EXCHANGE_USERNAME", "Login", "facultatif", "Laisse vide pour utiliser l'adresse mail, sinon DOMAINE\\login."),
            ("EXCHANGE_PASSWORD", "Mot de passe", ""),
        ], v, check=lambda f: checks.check_exchange(f["EXCHANGE_SERVER"], f["EXCHANGE_EMAIL"],
                                                    f["EXCHANGE_USERNAME"], f["EXCHANGE_PASSWORD"]))
        outlook.content.addWidget(self.outlook_form)
        outlook.finish()

        # ── 5. Timesheet
        timesheet = StepPage("Timesheet", "Plateforme où les tâches sont créées et les heures saisies.")
        self.timesheet_choice = Choice({
            "eprojet": ("E-PROJET\ne-projet.synelia.tech", FormSection([
                ("EPROJET_URL", "URL", "https://e-projet.synelia.tech/EProjet-1"),
                ("EPROJET_USERNAME", "Login", ""),
                ("EPROJET_PASSWORD", "Mot de passe", ""),
                Combo("EPROJET_RESP_EXTERNE", "Responsable externe",
                      [(v["EPROJET_RESP_EXTERNE"], v["EPROJET_RESP_EXTERNE"])] if v["EPROJET_RESP_EXTERNE"] else [],
                      "« Charger les listes » affiche les responsables de tes projets. Il doit être rattaché aux "
                      "projets choisis à l'étape Correspondances."),
                Combo("EPROJET_TYPE_TACHE_ID", "Type des tâches issues des commits", catalog.EPROJET_TYPES),
                Combo("EPROJET_TYPE_TACHE_REUNION_ID", "Type des réunions et du travail autour", catalog.EPROJET_TYPES),
            ], v, check=lambda f: checks.check_eprojet(f["EPROJET_URL"], f["EPROJET_USERNAME"], f["EPROJET_PASSWORD"]),
                loader=catalog.fetch_eprojet)),
            "orangescrum": ("OrangeScrum\norangescrum.synelia.tech", FormSection([
                ("OSCRUM_URL", "URL", "https://orangescrum.synelia.tech"),
                ("OSCRUM_USERNAME", "Email", "prenom.nom@exemple.com"),
                ("OSCRUM_PASSWORD", "Mot de passe", ""),
                Combo("OSCRUM_PROJECT", "Projet",
                      [(v["OSCRUM_PROJECT"], v["OSCRUM_PROJECT"])] if v["OSCRUM_PROJECT"] else [],
                      "« Charger les listes » affiche tes projets OrangeScrum."),
                Combo("OSCRUM_TASK_TYPE_ID", "Type de tâche", catalog.OSCRUM_TYPES),
                Combo("OSCRUM_ASSIGNEE_ID", "Personne assignée",
                      [(v["OSCRUM_ASSIGNEE_ID"], v["OSCRUM_ASSIGNEE_ID"])] if v["OSCRUM_ASSIGNEE_ID"] else [],
                      "« Charger les listes » puis choisis « Moi » (id propre à chaque compte) ou une autre personne. "
                      "Sinon, sur OrangeScrum "
                      "Quick Task → clic droit sur « Assign To » → Inspecter, et recopie la value de l'option."),
            ], v, check=lambda f: checks.check_orangescrum(f["OSCRUM_URL"], f["OSCRUM_USERNAME"], f["OSCRUM_PASSWORD"]),
                loader=catalog.fetch_orangescrum, depends={"OSCRUM_ASSIGNEE_ID": "OSCRUM_PROJECT"})),
        }, v["TIMESHEET_TARGET"])
        timesheet.content.addWidget(self.timesheet_choice)
        timesheet.finish()

        # ── 6. Correspondances
        mapping = StepPage("Correspondances", MAPPING_HELP)
        self.mapping_editor = MappingEditor(v["PROJECT_MAPPING"], self.gitlab_form.values,
                                            self.timesheet_choice.forms["eprojet"].values)
        mapping.content.addWidget(self.mapping_editor)

        # ── 7. Programmation
        schedule = StepPage("Programmation", "Les réglages sont enregistrés dans .env ; les mots de passe, "
                            "tokens et clés API dans le Trousseau macOS.")
        self.cb_schedule = QCheckBox("Programmer chaque jour ouvré : notification à 17h55, exécution à 18h00")
        self.cb_schedule.setChecked(scheduler.is_installed() or not settings_store.is_configured())
        self.cb_run_now = QCheckBox("Lancer une exécution dès l'enregistrement")
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.addWidget(self.cb_schedule)
        cl.addWidget(_label("Si l'exécution du jour est déjà faite, la notification et l'exécution de 18h "
                            "sont sautées pour la journée.", "hint", wrap=True))
        cl.addSpacing(8)
        cl.addWidget(self.cb_run_now)
        schedule.content.addWidget(card)
        schedule.finish()

        # ── Navigation
        self.steps = [("Sources", sources, None), ("Analyse IA", refiner, None),
                      ("GitLab", gitlab, self.cb_gitlab), ("Outlook", outlook, self.cb_outlook),
                      ("Timesheet", timesheet, None), ("Correspondances", mapping, self.cb_gitlab),
                      ("Programmation", schedule, None)]
        self.stack = QStackedWidget()
        for _, page, _ in self.steps:
            self.stack.addWidget(page)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(16, 28, 16, 20)
        sl.setSpacing(4)
        sl.addWidget(_label("RPA Timesheet", "sidebarTitle"))
        sl.addWidget(_label("Configuration", "hint"))
        sl.addSpacing(18)
        self.step_labels = []
        for name, _, _ in self.steps:
            lbl = _label(name, "step")
            self.step_labels.append(lbl)
            sl.addWidget(lbl)
        sl.addStretch()

        self.btn_back = _button("Précédent")
        self.btn_next = _button("Suivant", "primary")
        btn_cancel = _button("Annuler")
        self.btn_back.clicked.connect(lambda: self._go(-1))
        self.btn_next.clicked.connect(self._next)
        btn_cancel.clicked.connect(self.reject)
        footer = QFrame()
        footer.setObjectName("footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 12, 24, 12)
        fl.addWidget(btn_cancel)
        fl.addStretch()
        fl.addWidget(self.btn_back)
        fl.addWidget(self.btn_next)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self.stack, 1)
        right.addWidget(footer)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(sidebar)
        root.addLayout(right, 1)

        for cb in (self.cb_gitlab, self.cb_outlook):
            cb.toggled.connect(self._update_nav)
        self.current = 0
        self._update_nav()

    # ── Navigation entre étapes ─────────────────────────────
    def _active(self) -> list:
        return [i for i, (_, _, cond) in enumerate(self.steps) if cond is None or cond.isChecked()]

    def _update_nav(self):
        active = self._active()
        pos = active.index(self.current)
        for i, lbl in enumerate(self.step_labels):
            lbl.setVisible(i in active)
            lbl.setObjectName("stepActive" if i == self.current else
                              "stepDone" if i in active and active.index(i) < pos else "step")
            prefix = "✓  " if lbl.objectName() == "stepDone" else ""
            lbl.setText(prefix + self.steps[i][0])
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        self.stack.setCurrentIndex(self.current)
        self.btn_back.setEnabled(pos > 0)
        self.btn_next.setText("Enregistrer" if pos == len(active) - 1 else "Suivant")
        self.btn_next.setEnabled(self.current != 0 or self.cb_gitlab.isChecked() or self.cb_outlook.isChecked())

    def _go(self, delta: int):
        active = self._active()
        self.current = active[active.index(self.current) + delta]
        self._update_nav()

    def _next(self):
        if self.steps[self.current][1] is self.gitlab_page:
            f = self.gitlab_form.values()
            missing = [name for name, ok in (("l'auteur des commits", f["GITLAB_AUTHOR"]),
                                             ("le token d'accès", f["GITLAB_TOKEN"])) if not ok]
            if missing:
                QMessageBox.warning(self, "GitLab", "Renseigne " + " et ".join(missing) + ".")
                return
        active = self._active()
        if active.index(self.current) < len(active) - 1:
            self._go(1)
        else:
            self._save()

    # ── Enregistrement ──────────────────────────────────────
    def task_source(self) -> str:
        g, o = self.cb_gitlab.isChecked(), self.cb_outlook.isChecked()
        return "both" if g and o else "gitlab" if g else "outlook"

    def _save(self):
        values = {"TASK_SOURCE": self.task_source(),
                  "TASK_REFINER": self.refiner_choice.current(),
                  "TIMESHEET_TARGET": self.timesheet_choice.current()}
        for form in (*self.refiner_choice.forms.values(), *self.timesheet_choice.forms.values(),
                     self.gitlab_form, self.outlook_form):
            values.update(form.values())
        values["PROJECT_MAPPING"] = self.mapping_editor.value()
        values["EPROJET_PROJECT_ID"] = settings_store.main_project(values["PROJECT_MAPPING"])
        try:
            settings_store.save(values)
            scheduler.install() if self.cb_schedule.isChecked() else scheduler.uninstall()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible : {e}")
            return
        self.accept()


# ─────────────────────────────────────────────────────────────
class RunDialog(QDialog):
    """Lancement d'une exécution (période courante ou rattrapage) : contexte facultatif, puis prévisualisation du plan
    à valider avant toute saisie dans le timesheet"""

    def __init__(self, custom: bool, context: str = "", parent=None):
        super().__init__(parent)
        self.custom = custom
        self.setWindowTitle("Rattrapage" if custom else "Exécuter maintenant")
        self.setMinimumWidth(520)
        today = QDate.currentDate()
        self.start = QDateEdit(today.addDays(-(today.dayOfWeek() - 1)))  # lundi de la semaine
        self.end = QDateEdit(today)
        for d in (self.start, self.end):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
        self.context = QPlainTextEdit(context)
        self.context.setPlaceholderText("Ex. : lundi mardi je venais vers 10h et finissais vers 21h. "
                                        "Mercredi mise en production du module paiement.")
        self.context.setFixedHeight(90)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        if custom:
            lay.addWidget(_label("Rattrapage sur une période", "h2"))
            dates = QGridLayout()
            dates.addWidget(_label("Du", "fieldLabel"), 0, 0)
            dates.addWidget(_label("Au", "fieldLabel"), 0, 1)
            dates.addWidget(self.start, 1, 0)
            dates.addWidget(self.end, 1, 1)
            lay.addLayout(dates)
            lay.addWidget(_label("E-PROJET n'accepte la saisie que sur les 8 derniers jours. "
                                 "Le point de reprise automatique n'est pas modifié.", "hint", wrap=True))
        else:
            lay.addWidget(_label("Exécuter maintenant", "h2"))
            lay.addWidget(_label(f"Période du {_resume_day():%d/%m/%Y} à aujourd'hui.", "subtitle", wrap=True))
        lay.addWidget(_label("Contexte (facultatif)", "fieldLabel"))
        lay.addWidget(self.context)
        lay.addWidget(_label("Horaires reconnus (jours : lundi, hier, 12/11, ces 2 derniers jours… ; heures : 10h, "
                             "10h30, 21 heures, « j'ai fait 9h30 ») : ils remplacent les 8 h du jour, sans déduire "
                             "de pause (10h → 21h = 11 h). Le reste du texte aide seulement l'IA à rédiger les "
                             "libellés.", "hint", wrap=True))
        lay.addWidget(_label("Le plan s'affiche ensuite pour validation : rien n'est saisi avant.", "hint", wrap=True))
        buttons = QHBoxLayout()
        cancel, ok = _button("Annuler"), _button("Prévisualiser", "primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

    def args(self) -> list:
        """Arguments de --run : période (rattrapage) et contexte"""
        args = ["--since", self.start.date().toString("yyyy-MM-dd"),
                "--until", self.end.date().toString("yyyy-MM-dd")] if self.custom else []
        context = re.sub(r"\s+", " ", self.context.toPlainText()).strip()
        return args + (["--context", context] if context else [])


def _resume_day() -> date:
    """Jour à partir duquel la prochaine exécution saisira (un point de reprise à 23:59:59 = le lendemain)"""
    since = datetime.strptime(get_last_since(), "%Y-%m-%dT%H:%M:%SZ")
    return (since + timedelta(seconds=1)).date() if since.hour == 23 else since.date()


# ─────────────────────────────────────────────────────────────
class ResumeDialog(QDialog):
    """Correction du point de reprise : date à partir de laquelle la prochaine exécution saisit"""

    def __init__(self, current: date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Point de reprise")
        self.setMinimumWidth(460)
        self.day = QDateEdit(QDate(current.year, current.month, current.day))
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd/MM/yyyy")
        self.day.setMaximumDate(QDate.currentDate())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(_label("Corriger le point de reprise", "h2"))
        lay.addWidget(_label("Reprendre à partir du (inclus)", "fieldLabel"))
        lay.addWidget(self.day)
        lay.addWidget(_label("La prochaine exécution saisira les tâches à partir de cette date jusqu'au jour de "
                             "l'exécution. Choisir le lendemain du dernier jour déjà saisi, pour ne rien saisir deux "
                             "fois. E-PROJET n'accepte la saisie que sur les 8 derniers jours.", "hint", wrap=True))
        buttons = QHBoxLayout()
        cancel, ok = _button("Annuler"), _button("Enregistrer", "primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

    def value(self) -> date:
        return self.day.date().toPython()


# ─────────────────────────────────────────────────────────────
class PlanDialog(QDialog):
    """Plan en attente de saisie : cocher / décocher, corriger titres, dates et heures. « Exécuter » saisit ce plan
    tel quel. Réunions qui se chevauchent surlignées : la plus longue est cochée par défaut."""
    COLS = ("Saisir", "Date", "Heures", "Projet", "Titre", "Source")
    CONFLICT = QColor(245, 158, 11, 70)
    UNMAPPED = QColor(59, 130, 246, 55)

    def __init__(self, plan: dict, parent=None, confirm: bool = False):
        """confirm : récapitulatif avant saisie (« Valider et saisir » lance la saisie effective)"""
        super().__init__(parent)
        self.plan = plan
        self.discarded = False
        self.setWindowTitle("Plan de saisie")
        self.resize(1100, 640)

        tasks = plan["tasks"]
        self.table = QTableWidget(len(tasks), len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(5, 280)

        # Projets proposés : listes E-PROJET chargées dans la configuration + projets déjà présents dans le plan
        names = catalog.project_names()
        default = settings_store.load().get("EPROJET_PROJECT_ID", "")
        ids = list(names) + [i for i in [default, *(t.get("eprojet_project_id") for t in tasks)] if i and i not in names]
        ids = list(dict.fromkeys(ids))
        label = lambda i: f"{names[i]} ({i})" if i in names else f"Projet {i}"
        self.project_combos = []

        editable = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        for row, task in enumerate(tasks):
            locked = plan_store.started(task)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | (Qt.ItemFlag(0) if locked else Qt.ItemFlag.ItemIsUserCheckable))
            check.setCheckState(Qt.CheckState.Checked if task.get("include", True) else Qt.CheckState.Unchecked)
            source = task.get("conflict") or ", ".join(task.get("original_commits") or [])
            if task.get("unmapped"):
                source = f"⚠️ dépôt sans correspondance ({task.get('project_id')}) — {source}"
            items = [check,
                     QTableWidgetItem(f"{plan_store.day_of(task):%d/%m/%Y}"),
                     QTableWidgetItem(f"{task['hours']:g}"),
                     QTableWidgetItem(""),
                     QTableWidgetItem(task["title"]),
                     QTableWidgetItem(source)]
            items[5].setToolTip(source)
            for col, item in enumerate(items[1:], 1):
                item.setFlags(editable if col in (1, 2, 4) and not locked else Qt.ItemFlag.ItemIsEnabled)
            for col, item in enumerate(items):
                if locked:
                    item.setToolTip("Déjà créée ou saisie dans le timesheet : non modifiable")
                elif task.get("conflict"):
                    item.setBackground(self.CONFLICT)
                elif task.get("unmapped"):
                    item.setBackground(self.UNMAPPED)
                self.table.setItem(row, col, item)

            combo = QComboBox()
            combo.addItem("—", "")
            for i in ids:
                combo.addItem(label(i), i)
            combo.setCurrentIndex(max(0, combo.findData(task.get("eprojet_project_id") or "")))
            combo.setEnabled(not locked)
            self.table.setCellWidget(row, 3, combo)
            self.project_combos.append(combo)
        self.table.itemChanged.connect(self._update_totals)

        conflicts = sum(1 for t in tasks if t.get("conflict"))
        unmapped = sum(1 for t in tasks if t.get("unmapped"))
        # point de reprise « J 23:59:59 » = à partir du lendemain
        day = lambda s, shift: (datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=shift)).date()
        period = f"{day(plan['since'], 1):%d/%m/%Y} → {day(plan['until'], 0):%d/%m/%Y}"
        self.totals = _label("", "hint", wrap=True)
        schedule = " · ".join(
            f"{DAYS_FR[date.fromisoformat(d).weekday()]} {date.fromisoformat(d):%d/%m} : {userContext.describe(e)}"
            for d, e in sorted((plan.get("schedule") or {}).items()))
        context = (f"🗒 Contexte : « {plan['context']} »" + (f" — horaires retenus : {schedule}" if schedule else
                   " — aucun horaire reconnu (8 h par jour)")) if plan.get("context") else ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(_label("Plan de saisie", "h2"))
        lay.addWidget(_label(
            f"Période {period}{' (rattrapage)' if plan['custom'] else ''} — "
            f"{'validé' if plan.get('validated') else 'non validé'}. Corrige les titres, dates (JJ/MM/AAAA) et heures, "
            "décoche ce qui ne doit pas être saisi. "
            + ("« Valider et saisir » saisit exactement ce plan dans le timesheet ; « Annuler » ne saisit rien."
               if confirm else "La prochaine exécution saisit exactement ce plan.")
            + (f" ⚠️ {conflicts} réunion(s) en conflit (surlignées) : la plus longue est cochée, choisis celle à garder."
               if conflicts else "")
            + (f" 🔵 {unmapped} tâche(s) d'un dépôt sans correspondance (en bleu) : rangées dans ton projet principal, "
               "vérifie le projet." if unmapped else ""), "subtitle", wrap=True))
        if context:
            lay.addWidget(_label(context, "hint", wrap=True))
        lay.addWidget(self.table, 1)
        lay.addWidget(self.totals)
        buttons = QHBoxLayout()
        discard, cancel = _button("Abandonner le plan", "danger"), _button("Annuler")
        ok = _button("Valider et saisir" if confirm else "Valider", "primary")
        discard.clicked.connect(self._discard)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._save)
        buttons.addWidget(discard)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)
        self._update_totals()

    def _row(self, row: int) -> tuple:
        """(cochée, date, heures, titre) ; lève ValueError si la ligne est invalide"""
        cell = lambda col: self.table.item(row, col).text().strip()
        try:
            day = datetime.strptime(cell(1), "%d/%m/%Y").date()
        except ValueError:
            raise ValueError(f"ligne {row + 1} : date « {cell(1)} » invalide (JJ/MM/AAAA)") from None
        try:
            hours = float(cell(2).replace(",", "."))
        except ValueError:
            hours = 0
        if hours <= 0:
            raise ValueError(f"ligne {row + 1} : heures « {cell(2)} » invalides")
        title = re.sub(r"\s+", " ", re.sub(r"['’]", " ", cell(4))).strip()  # pas d'apostrophe dans E-PROJET
        if not title:
            raise ValueError(f"ligne {row + 1} : titre vide")
        project = self.project_combos[row].currentData() or ""
        return self.table.item(row, 0).checkState() == Qt.CheckState.Checked, day, hours, title, project

    def _update_totals(self, *_):
        by_day = {}
        for row in range(self.table.rowCount()):
            try:
                checked, day, hours, _, _ = self._row(row)
            except ValueError:
                continue
            if checked:
                by_day[day] = by_day.get(day, 0) + hours
        days = " · ".join(f"{DAYS_FR[d.weekday()]} {d:%d/%m} : {h:g} h" for d, h in sorted(by_day.items()))
        self.totals.setText(f"Total {sum(by_day.values()):g} h — {days}" if by_day else "Aucune tâche cochée")

    def _save(self):
        try:
            rows = [self._row(row) for row in range(self.table.rowCount())]
        except ValueError as e:
            QMessageBox.warning(self, "Plan", str(e))
            return
        if any(checked and not project for checked, *_, project in rows) and \
                settings_store.load().get("TIMESHEET_TARGET") == "eprojet":
            QMessageBox.warning(self, "Plan", "Choisis un projet pour chaque tâche cochée.")
            return
        for task, (checked, day, hours, title, project) in zip(self.plan["tasks"], rows):
            if plan_store.started(task):
                continue
            task["include"] = checked
            task["hours"] = hours
            task["title"] = title
            if project and project != task.get("eprojet_project_id"):
                task["eprojet_project_id"] = project
                task.pop("unmapped", None)  # projet choisi à la main
            plan_store.set_day(task, day)
        self.plan["validated"] = True
        plan_store.save(self.plan)
        self.accept()

    def _discard(self):
        warning = ("\n\nDes tâches de ce plan sont déjà créées dans le timesheet : elles seront recréées."
                   if plan_store.has_progress(self.plan) else "")
        if QMessageBox.question(self, "Plan", "Abandonner ce plan ? La prochaine exécution relancera l'analyse IA."
                                + warning) != QMessageBox.StandardButton.Yes:
            return
        plan_store.clear()
        self.discarded = True
        self.accept()


# ─────────────────────────────────────────────────────────────
class BrowserDialog(QDialog):
    """Téléchargement (premier lancement) ou réparation du navigateur Chromium utilisé par le RPA"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.installed = browser_setup.is_installed()
        self.setWindowTitle("Navigateur Chromium")
        self.setMinimumSize(560, 360)
        self.output = QPlainTextEdit()
        self.output.setObjectName("log")
        self.output.setReadOnly(True)
        self.btn = _button("Réinstaller" if self.installed else "Télécharger", "primary")
        self.btn.clicked.connect(self._start)
        later = _button("Fermer" if self.installed else "Plus tard")
        later.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(_label("Navigateur Chromium" if self.installed else "Navigateur manquant", "h2"))
        lay.addWidget(_label("Chromium est installé. Réinstalle-le uniquement si le RPA n'arrive plus à ouvrir le "
                             "navigateur (≈ 150 Mo)." if self.installed else
                             "Le RPA pilote un navigateur Chromium pour saisir les tâches. Il n'est pas inclus "
                             "dans l'application (ou il a été supprimé) : il faut le télécharger (≈ 150 Mo).",
                             "subtitle", wrap=True))
        lay.addWidget(self.output, 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(later)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self.process = None

    def _start(self):
        self.btn.setEnabled(False)
        self.btn.setText("Téléchargement…")
        command = entry_command("--reinstall-browser" if self.installed else "--install-browser")
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(lambda: self.output.appendPlainText(
            bytes(self.process.readAllStandardOutput()).decode(errors="replace").rstrip()))
        self.process.finished.connect(self._done)
        self.process.start(command[0], command[1:])

    def _done(self, code: int, _status):
        if code == 0 and browser_setup.is_installed():
            self.accept()
            return
        self.btn.setEnabled(True)
        self.btn.setText("Réessayer")
        self.output.appendPlainText("\n❌ Téléchargement échoué — vérifie la connexion internet puis réessaie.")


# ─────────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        lay.addWidget(_label(title.upper(), "cardTitle"))
        self.value = _label("—", "cardValue", wrap=True)
        self.detail = _label("", "hint", wrap=True)
        lay.addWidget(self.value)
        lay.addWidget(self.detail)

    def set(self, value: str, detail: str = ""):
        self.value.setText(value)
        self.detail.setText(detail)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPA Timesheet")
        self.resize(1180, 780)
        self.process = None
        self.log_file = None
        self.run_args, self.confirm_args = [], None

        # En-tête
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_label("RPA Timesheet", "h1"))
        titles.addWidget(_label("GitLab / Outlook  →  analyse IA  →  tâches et heures dans le timesheet", "subtitle"))
        header.addLayout(titles)
        header.addStretch()
        self.btn_config = _button("⚙  Configuration")
        self.btn_config.clicked.connect(self.open_setup)
        self.btn_mapping = _button("🔗  Correspondances")
        self.btn_mapping.clicked.connect(self.open_mapping)
        self.btn_browser = _button("🌐  Navigateur")
        self.btn_browser.clicked.connect(lambda: BrowserDialog(self).exec())
        header.addWidget(self.btn_mapping, alignment=Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.btn_browser, alignment=Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.btn_config, alignment=Qt.AlignmentFlag.AlignTop)

        # Cartes d'état
        self.card_sources = StatCard("Sources")
        self.card_refiner = StatCard("Analyse IA")
        self.card_timesheet = StatCard("Timesheet")
        self.card_last = StatCard("Dernière exécution")
        self.card_next = StatCard("Prochaine exécution")
        cards = QHBoxLayout()
        cards.setSpacing(14)
        for c in (self.card_sources, self.card_refiner, self.card_timesheet, self.card_last, self.card_next):
            cards.addWidget(c, 1)

        # Actions
        self.btn_run = _button("▶  Exécuter maintenant", "primary")
        self.btn_preview = _button("Aperçu sans saisie")
        self.btn_plan = _button("📋  Plan…")
        self.btn_period = _button("Rattrapage…")
        self.btn_resume = _button("Point de reprise…")
        self.btn_stop = _button("■  Arrêter", "danger")
        self.btn_schedule = _button("")
        self.btn_run.clicked.connect(self.run_now)
        self.btn_preview.clicked.connect(lambda: self.start_run(["--dry-run"]))
        self.btn_period.clicked.connect(self.run_period)
        self.btn_resume.clicked.connect(self.edit_resume)
        self.btn_plan.clicked.connect(self.open_plan)
        self.btn_stop.clicked.connect(self.stop_run)
        self.btn_schedule.clicked.connect(self.toggle_schedule)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        for b in (self.btn_run, self.btn_preview, self.btn_plan, self.btn_period, self.btn_resume, self.btn_stop):
            actions.addWidget(b)
        actions.addStretch()
        actions.addWidget(self.btn_schedule)

        # Journal
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        self.log.setPlaceholderText("Le journal de l'exécution s'affichera ici.")
        self.lbl_status = _label("", "hint")
        log_header = QHBoxLayout()
        log_header.addWidget(_label("Journal", "h2"))
        log_header.addStretch()
        log_header.addWidget(self.lbl_status)

        root = QWidget()
        root.setObjectName("page")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(18)
        lay.addLayout(header)
        lay.addLayout(cards)
        lay.addLayout(actions)
        lay.addLayout(log_header)
        lay.addWidget(self.log, 1)
        self.setCentralWidget(root)

        self.refresh()

    # ── État ────────────────────────────────────────────────
    def refresh(self):
        v = settings_store.load()
        self.card_sources.set(SOURCE_LABELS.get(v["TASK_SOURCE"], v["TASK_SOURCE"]),
                              "commits + réunions" if v["TASK_SOURCE"] == "both" else
                              "réunions du calendrier" if v["TASK_SOURCE"] == "outlook" else "commits")
        claude_found = shutil.which(v["CLAUDE_CLI_PATH"] or "claude", path=with_extra_path(os.environ.get("PATH", "")))
        self.card_refiner.set(REFINER_LABELS.get(v["TASK_REFINER"], v["TASK_REFINER"]),
                              {"claude": "CLI Claude Code" if claude_found else "⚠️ CLI claude introuvable",
                               "gemini": v["GEMINI_MODEL"],
                               "mistral": f"agent {v['MISTRAL_AGENT_ID'][:14]}…"}.get(v["TASK_REFINER"], ""))

        target = v["TIMESHEET_TARGET"]
        rules = len(parse_mapping(v["PROJECT_MAPPING"]))
        self.card_timesheet.set(TIMESHEET_LABELS.get(target, target),
                                f"{rules} correspondance(s)" if target == "eprojet" else v["OSCRUM_PROJECT"])

        last = get_last_run()
        resume = f"reprise au {_resume_day():%d/%m/%Y}"
        if last == date.today().isoformat():
            self.card_last.set("Aujourd'hui", resume)
        elif last:
            self.card_last.set(datetime.strptime(last, "%Y-%m-%d").strftime("%d/%m/%Y"), resume)
        else:
            self.card_last.set("—", resume)

        installed = scheduler.is_installed()
        nxt = scheduler.next_run()
        if installed and nxt:
            self.card_next.set(f"{DAYS_FR[nxt.weekday()]} {nxt:%d/%m à %H:%M}", "notification 5 min avant")
        else:
            self.card_next.set("Non programmée" if not installed else "—",
                               "" if installed else "active la programmation pour 18h")
        self.btn_schedule.setText("Désactiver la programmation" if installed else "Programmer 17h55 / 18h")

        plan = plan_store.load()
        conflicts = plan and any(t.get("conflict") for t in plan["tasks"]) and not plan.get("validated")
        self.btn_plan.setText(f"📋  Plan ({sum(1 for t in plan['tasks'] if t.get('include', True))})"
                              f"{' ⚠️' if conflicts else ''}…" if plan else "📋  Plan…")
        self.btn_plan.setToolTip("Plan en attente : saisi tel quel à la prochaine exécution" if plan else
                                 "Aucun plan en attente : « Aperçu sans saisie » en prépare un")

        running = self.process is not None
        for b in (self.btn_run, self.btn_preview, self.btn_period, self.btn_resume, self.btn_config, self.btn_mapping):
            b.setEnabled(not running)
        self.btn_plan.setEnabled(bool(plan) and not running)
        self.btn_stop.setVisible(running)
        self.lbl_status.setText("⏳ Exécution en cours…" if running else "")

    # ── Actions ─────────────────────────────────────────────
    def open_setup(self):
        dialog = SetupDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            if dialog.cb_run_now.isChecked():
                self.run_now()

    def toggle_schedule(self):
        try:
            scheduler.uninstall() if scheduler.is_installed() else scheduler.install()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Programmation impossible : {e}")
        self.refresh()

    def run_now(self):
        self._launch(RunDialog(False, self._pending_context(), self))

    def run_period(self):
        self._launch(RunDialog(True, self._pending_context(), self))

    @staticmethod
    def _pending_context() -> str:
        plan = plan_store.load()
        return (plan or {}).get("context", "")

    def _launch(self, dialog: RunDialog):
        """Prévisualisation (--dry-run) puis plan à valider ; la saisie effective n'est lancée qu'après validation"""
        if self.process or dialog.exec() != QDialog.DialogCode.Accepted:
            return
        args = dialog.args()
        self.start_run(args + ["--dry-run"])
        self.confirm_args = args

    def edit_resume(self):
        dialog = ResumeDialog(min(_resume_day(), date.today()), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            set_resume_date(dialog.value())
            self._append(f"\n📌 Point de reprise corrigé : prochaine exécution à partir du {dialog.value():%d/%m/%Y}\n")
            self.refresh()

    def open_mapping(self):
        if MappingDialog(self).exec() == QDialog.DialogCode.Accepted:
            self._append("\n🔗 Correspondances enregistrées (prises en compte à la prochaine analyse)\n")
            self.refresh()

    def open_plan(self, confirm_args: list = None):
        """confirm_args : récapitulatif d'une exécution prévisualisée ; validé, il est saisi aussitôt"""
        plan = plan_store.load()
        if not plan:
            return
        dialog = PlanDialog(plan, self, confirm=confirm_args is not None)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted and dialog.discarded:
            self._append("\n🗑 Plan abandonné\n")
        elif accepted and confirm_args is not None:
            self._append("\n📋 Plan validé : saisie dans le timesheet\n")
            self.refresh()
            self.start_run(confirm_args)
            return
        elif accepted:
            self._append("\n📋 Plan validé : saisi tel quel à la prochaine exécution\n")
        elif confirm_args is not None:
            self._append("\n⏸ Saisie annulée : le plan est conservé (« Plan… » pour le revoir)\n")
        self.refresh()

    def start_run(self, args: list):
        if self.process:
            return
        self.run_args = args
        self.confirm_args = None
        os.makedirs(LOGS_DIR, exist_ok=True)
        self.log_file = open(os.path.join(LOGS_DIR, f"rpa_{date.today().isoformat()}.log"), "a", encoding="utf-8")
        self._append(f"\n===== {datetime.now():%d/%m/%Y %H:%M:%S} — main.py {' '.join(args)} =====\n")

        env = QProcessEnvironment.systemEnvironment()
        # Le .env chargé au démarrage de l'interface est dans son environnement : on le retire pour que
        # l'exécution relise le .env tel qu'enregistré (sinon d'anciennes valeurs l'emportent)
        for key in (*settings_store.FIELDS, *dotenv_values(ENV_PATH)):
            env.remove(key)
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PATH", with_extra_path(env.value("PATH")))  # CLI claude, même hors terminal

        self.stopped_by_user = False
        self.process = QProcess(self)
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(DATA_DIR)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(
            lambda: self._append(bytes(self.process.readAllStandardOutput()).decode(errors="replace")))
        self.process.finished.connect(self._run_finished)
        command = entry_command("--run", *args)  # l'application se relance elle-même en mode exécution
        self.process.start(command[0], command[1:])
        self.refresh()

    def stop_run(self):
        if self.process:
            self.stopped_by_user = True
            self.process.kill()

    def _run_finished(self, code: int, status):
        stopped = self.stopped_by_user
        ok = code == 0 and status == QProcess.ExitStatus.NormalExit
        if stopped:
            end = "■ Arrêtée"
        elif ok:
            end = "✅ Terminé"
        elif status == QProcess.ExitStatus.CrashExit:
            end = "❌ Interrompue (processus arrêté brutalement)"
        else:
            end = f"❌ Échec (code {code})"
        self._append(f"\n===== {end} =====\n")
        self.log_file.close()
        self.log_file = None  # sinon _append écrit dans un fichier fermé (ValueError) et la saisie validée ne part pas
        self.process = None
        self.refresh()
        if not ok and not stopped:
            QMessageBox.warning(self, "RPA Timesheet", "L'exécution a échoué — voir le journal.")
        elif ok and "--dry-run" in self.run_args:
            # l'aperçu est un plan à relire / corriger ; après « Exécuter » ou « Rattrapage », sa validation lance la saisie
            confirm, self.confirm_args = self.confirm_args, None
            self.open_plan(confirm)

    def _append(self, text: str):
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        if self.log_file:
            self.log_file.write(text)
            self.log_file.flush()

    def closeEvent(self, event):
        if self.process and QMessageBox.question(
                self, "RPA Timesheet", "Une exécution est en cours. L'arrêter et quitter ?") \
                != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self.stop_run()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RPA Timesheet")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    if not settings_store.is_configured():
        window.open_setup()
    if not browser_setup.is_installed():
        BrowserDialog(window).exec()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
