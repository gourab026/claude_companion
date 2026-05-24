import json
import logging
import os
import subprocess
import time
import webbrowser
from datetime import datetime as _dt
from pathlib import Path

from PyQt6.QtGui import QPainter, QColor, QIcon, QPixmap, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSlider, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QSpinBox,
    QTextEdit, QMessageBox, QCheckBox,
    QListWidget, QListWidgetItem, QDialog,
    QDialogButtonBox, QRadioButton, QButtonGroup,
    QScrollArea, QSplitter, QFileDialog, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, pyqtSlot, QSize, QTimer

from personality import Personality, DEFAULTS

log = logging.getLogger("pip.main")

LOG_FILE = os.path.join(os.path.expanduser("~"), ".pip-companion.log")


# ── Icon factory ──────────────────────────────────────────────────────────────

def _cp_make_icon(draw_fn, color: str = "#a892ff", size: int = 18) -> QIcon:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.5 * (size / 16), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    draw_fn(p, size)
    p.end()
    return QIcon(px)


def _tab_icon_home(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(1*m), int(1*m), int(14*m), int(14*m))
        p.drawLine(int(8*m), int(7*m), int(8*m), int(12*m))
        p.setBrush(QBrush(QColor("#a892ff")))
        p.drawEllipse(int(7*m), int(4*m), int(2*m), int(2*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_character(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(5*m), int(1.5*m), int(6*m), int(6*m))
        p.drawArc(int(1*m), int(9*m), int(14*m), int(7*m), 0, 180*16)
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_memory(size=18):
    def draw(p, s):
        m = s / 16
        p.drawRoundedRect(int(3*m), int(3*m), int(10*m), int(12*m), 1*m, 1*m)
        p.drawRoundedRect(int(5.5*m), int(1*m), int(5*m), int(4*m), 1*m, 1*m)
        p.drawLine(int(5.5*m), int(8*m),  int(10.5*m), int(8*m))
        p.drawLine(int(5.5*m), int(11*m), int(9*m),    int(11*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_settings(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(5.5*m), int(5.5*m), int(5*m), int(5*m))
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            p.drawLine(int((8+dx*3)*m), int((8+dy*3)*m),
                       int((8+dx*5)*m), int((8+dy*5)*m))
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            p.drawLine(int((8+dx*2.5)*m), int((8+dy*2.5)*m),
                       int((8+dx*4)*m), int((8+dy*4)*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_log(size=18):
    def draw(p, s):
        m = s / 16
        p.drawRoundedRect(int(1.5*m), int(2*m), int(13*m), int(12*m), 1.5*m, 1.5*m)
        p.drawLine(int(3.5*m), int(6*m), int(5.5*m), int(8*m))
        p.drawLine(int(5.5*m), int(8*m), int(3.5*m), int(10*m))
        p.drawLine(int(7*m), int(8*m), int(12.5*m), int(8*m))
    return _cp_make_icon(draw, "#a892ff", size)


# ── Module-level layout helpers ───────────────────────────────────────────────

def _section_label(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "color: #7860d4; font-size: 10px; font-weight: 700; "
        "letter-spacing: 1.5px; padding: 10px 0 4px 0; background: transparent;"
    )
    return lbl


def _hdivider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("QFrame { color: #1e1830; margin: 2px 0; }")
    return f


def _setting_row(label_text: str, widget: QWidget, hint: str = "") -> QWidget:
    """A horizontal row: [label + optional hint | widget] in a card."""
    row = QWidget()
    row.setStyleSheet(
        "QWidget { background: #130f20; border-radius: 8px; } "
        "QLabel { background: transparent; }"
    )
    h = QHBoxLayout(row)
    h.setContentsMargins(12, 9, 12, 9)
    h.setSpacing(10)
    col = QVBoxLayout()
    col.setSpacing(1)
    lbl = QLabel(label_text)
    lbl.setStyleSheet("color: #ccc4e0; font-size: 13px; background: transparent;")
    col.addWidget(lbl)
    if hint:
        hl = QLabel(hint)
        hl.setStyleSheet("color: #5a4f70; font-size: 11px; background: transparent;")
        col.addWidget(hl)
    h.addLayout(col, 1)
    h.addWidget(widget)
    return row


# ── Slider / row helpers (kept identical) ────────────────────────────────────

def _slider() -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(0, 100)
    s.setFixedWidth(160)
    return s


def _row(slider: QSlider, label: QLabel) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    label.setFixedWidth(36)
    h.addWidget(slider)
    h.addWidget(label)
    return w


# ═════════════════════════════════════════════════════════════════════════════
# ControlPanel
# ═════════════════════════════════════════════════════════════════════════════

class ControlPanel(QWidget):
    settings_changed        = pyqtSignal()
    breathing_requested     = pyqtSignal()
    calendar_status_changed = pyqtSignal(bool)
    voice_config_changed    = pyqtSignal(bool, str, str)
    _gcal_done              = pyqtSignal(bool, str)

    def __init__(self, personality: Personality, settings: QSettings,
                 mcp_config_path: str, gcal=None, parent=None):
        super().__init__(parent)
        self._p    = personality
        self._s    = settings
        self._mcp  = mcp_config_path
        self._gcal = gcal
        self.setWindowTitle("Pip — Control Panel")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(740, 720)

        # ── Master stylesheet ─────────────────────────────────────────────────
        self.setStyleSheet("""
            QWidget {
                background: #0a0812;
                color: #ccc4e0;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            /* ── West-side tab bar ── */
            QTabWidget::pane {
                border: 1px solid #1e1830;
                border-radius: 10px;
                background: #111020;
                margin-left: 4px;
            }
            QTabBar {
                background: #0a0812;
            }
            QTabBar::tab {
                background: transparent;
                color: #4a4060;
                padding: 10px 18px;
                border-radius: 8px;
                margin: 2px 4px;
                font-size: 13px;
                font-weight: 500;
                min-height: 36px;
                text-align: left;
            }
            QTabBar::tab:selected {
                background: #1a1530;
                color: #a892ff;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                background: #141028;
                color: #7860d4;
            }

            /* Inner (memory) tab widget — flat North style */
            QTabWidget#inner_tabs::pane {
                border: 1px solid #1e1830;
                border-radius: 6px;
                background: #0e0c1a;
                margin-top: 0px;
            }
            QTabWidget#inner_tabs QTabBar::tab {
                padding: 6px 14px;
                min-height: 26px;
                font-size: 12px;
            }

            QPushButton {
                background: #1a1530;
                color: #a892ff;
                border: 1px solid #2a2048;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #241d40;
                border-color: #7860d4;
            }
            QPushButton:pressed {
                background: #7860d4;
                color: #ffffff;
            }
            QPushButton#primary_btn {
                background: #7860d4;
                color: #ffffff;
                border: none;
                font-weight: 700;
                padding: 9px 20px;
                font-size: 13px;
            }
            QPushButton#primary_btn:hover {
                background: #8f76e8;
            }
            QPushButton#primary_btn:pressed {
                background: #6350b8;
            }
            QPushButton#danger_btn {
                color: #d46080;
                border-color: #d46080;
            }
            QPushButton#danger_btn:hover {
                background: #2d1f28;
            }

            QLineEdit, QTextEdit, QPlainTextEdit {
                background: #130f20;
                border: 1px solid #1e1830;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ccc4e0;
                selection-background-color: #7860d4;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #7860d4;
            }
            QSpinBox {
                background: #130f20;
                border: 1px solid #1e1830;
                border-radius: 6px;
                padding: 4px 8px;
                color: #ccc4e0;
                min-width: 72px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #1e1830;
                border: none;
                border-radius: 3px;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #7860d4;
            }
            QComboBox {
                background: #130f20;
                border: 1px solid #1e1830;
                border-radius: 6px;
                padding: 5px 10px;
                color: #ccc4e0;
                min-width: 140px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #130f20;
                border: 1px solid #1e1830;
                color: #ccc4e0;
                selection-background-color: #7860d4;
            }
            QCheckBox {
                spacing: 8px;
                color: #ccc4e0;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #2a2048;
                border-radius: 4px;
                background: #130f20;
            }
            QCheckBox::indicator:checked {
                background: #7860d4;
                border-color: #7860d4;
            }
            QLabel {
                color: #8878a0;
                background: transparent;
            }
            QListWidget {
                background: #130f20;
                border: 1px solid #1e1830;
                border-radius: 6px;
                color: #ccc4e0;
            }
            QListWidget::item:selected {
                background: #241d40;
                color: #a892ff;
            }
            QListWidget::item:hover {
                background: #18122a;
            }
            QGroupBox {
                border: 1px solid #1e1830;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 10px;
                color: #5a4f70;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
            }
            QSlider::groove:horizontal {
                background: #1e1830;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #7860d4;
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -5px 0;
            }
            QSlider::sub-page:horizontal {
                background: #7860d4;
                border-radius: 2px;
            }
            QRadioButton {
                spacing: 8px;
                color: #ccc4e0;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #2a2048;
                border-radius: 7px;
                background: #130f20;
            }
            QRadioButton::indicator:checked {
                background: #7860d4;
                border-color: #7860d4;
            }
            QScrollBar:vertical {
                background: #0a0812;
                width: 6px;
                border-radius: 3px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1e1830;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7860d4;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: #0a0812;
                height: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #1e1830;
                border-radius: 3px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal { width: 0; }
            QDialogButtonBox QPushButton { min-width: 70px; }
        """)

        # ── Search box ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search settings…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet("""
            QLineEdit {
                background: #111020;
                border: 1px solid #1e1830;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ccc4e0;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #7860d4; }
        """)
        self._search.textChanged.connect(self._on_search)

        # Internal signal: GCal background thread → main thread
        self._gcal_done.connect(self._gcal_on_connect_done_ui)

        # ── Build tabs ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.West)
        self._tabs.setIconSize(QSize(18, 18))

        self._tabs.addTab(self._build_home_tab(),      _tab_icon_home(),      "Home")
        self._tabs.addTab(self._build_character_tab(), _tab_icon_character(), "Character")
        self._tabs.addTab(self._build_memory_tab(),    _tab_icon_memory(),    "Memory")
        self._tabs.addTab(self._build_settings_tab(),  _tab_icon_settings(),  "Settings")
        self._tabs.addTab(self._build_log_tab(),       _tab_icon_log(),       "Log")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addWidget(self._search)
        root.addWidget(self._tabs)

        # Tab indices: Home=0, Character=1, Memory=2, Settings=3, Log=4
        self._search_tab_map = {
            # Home
            "home": 0, "overview": 0, "mood": 0, "streak": 0, "stats": 0,
            "pomodoro": 0, "focus mode": 0, "breathing": 0, "journal": 0,
            "session": 0, "uptime": 0,
            # Character
            "character": 1, "personality": 1, "name": 1, "humor": 1,
            "playfulness": 1, "helpfulness": 1, "traits": 1, "quips": 1,
            "profile": 1, "work": 1, "interests": 1, "communication": 1,
            "vocabulary": 1, "achievements": 1, "checkin": 1, "reset": 1,
            "cosmetics": 1, "hat": 1, "appearance": 1,
            # Memory
            "memory": 2, "notes": 2, "note": 2, "bookmarks": 2, "bookmark": 2,
            "diary": 2, "mood history": 2, "mood chart": 2,
            # Settings
            "settings": 3, "model": 3, "idle": 3, "position": 3,
            "log file": 3, "sound": 3, "interval": 3,
            "calendar": 3, "google calendar": 3, "gcal": 3,
            "voice": 3, "microphone": 3, "speech": 3, "mic": 3, "whisper": 3,
            "tools": 3, "mcp": 3, "web search": 3, "bash": 3,
            "deep watch": 3, "screen watcher": 3,
            "hydration": 3, "eyestrain": 3, "wellness": 3,
            "quiet hours": 3, "focus zone": 3,
            # Log
            "log": 4, "error": 4, "debug": 4, "warning": 4,
        }

        self._reload_mcp_list()
        self._gcal_refresh_ui()

    # ── Scrollable wrapper ────────────────────────────────────────────────────

    def _scrollable(self, w: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(w)
        return sa

    # ═══════════════════════════════════════════ Search ═══════════════════════

    def _on_search(self, text: str):
        q = text.strip().lower()
        if not q:
            return
        for keyword, tab_idx in self._search_tab_map.items():
            if keyword in q or q in keyword:
                self._tabs.setCurrentIndex(tab_idx)
                return
        for i in range(self._tabs.count()):
            if q in self._tabs.tabText(i).lower():
                self._tabs.setCurrentIndex(i)
                return

    # ═══════════════════════════════════════════ Tab 0 — Home ════════════════

    def _build_home_tab(self) -> QWidget:
        def _stat_card(title: str, value: str, accent: str) -> QFrame:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: #111020; border: 1px solid {accent}40; "
                f"border-radius: 10px; padding: 8px; }}"
            )
            card_lo = QVBoxLayout(card)
            card_lo.setSpacing(4)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(f"color: {accent}; font-size: 11px; font-weight: 600;")
            val_lbl = QLabel(value)
            val_lbl.setObjectName("val")
            val_lbl.setStyleSheet("color: #e0d8f8; font-size: 18px; font-weight: 700;")
            card_lo.addWidget(title_lbl)
            card_lo.addWidget(val_lbl)
            return card

        inner = QWidget()
        lo = QVBoxLayout(inner)
        lo.setSpacing(14)
        lo.setContentsMargins(16, 16, 16, 16)

        # ── Identity banner ───────────────────────────────────────────────────
        banner = QWidget()
        banner.setStyleSheet(
            "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 10px; }"
        )
        b_lo = QVBoxLayout(banner)
        b_lo.setContentsMargins(16, 14, 16, 14)
        b_lo.setSpacing(4)
        d = self._p._data
        name_lbl = QLabel(d.get("name", "Pip"))
        name_lbl.setStyleSheet(
            "color: #a892ff; font-size: 22px; font-weight: 700; background: transparent;"
        )
        b_lo.addWidget(name_lbl)
        self._home_mood_lbl = QLabel()
        self._home_mood_lbl.setStyleSheet("color: #8878a0; font-size: 13px; background: transparent;")
        b_lo.addWidget(self._home_mood_lbl)
        self._home_rel_lbl = QLabel()
        self._home_rel_lbl.setStyleSheet("color: #7860d4; font-size: 12px; font-weight: 600; background: transparent;")
        b_lo.addWidget(self._home_rel_lbl)
        lo.addWidget(banner)

        # ── Stat cards row ────────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._home_streak_card = _stat_card("🔥 Streak",   "0 days", "#f0a030")
        self._home_chats_card  = _stat_card("💬 Chats",    "0",      "#a892ff")
        self._home_uptime_card = _stat_card("⏱ Session",  "0 min",  "#60c0a0")
        for c in [self._home_streak_card, self._home_chats_card, self._home_uptime_card]:
            cards_row.addWidget(c)
        lo.addLayout(cards_row)

        # ── Quick actions ─────────────────────────────────────────────────────
        actions_widget = QWidget()
        actions_widget.setStyleSheet(
            "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 10px; }"
        )
        a_lo = QHBoxLayout(actions_widget)
        a_lo.setContentsMargins(12, 10, 12, 10)
        a_lo.setSpacing(10)
        actions_hdr = QLabel("QUICK ACTIONS")
        actions_hdr.setStyleSheet(
            "color: #4a4060; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; background: transparent;"
        )
        a_lo.addWidget(actions_hdr)
        a_lo.addStretch()
        pomo_btn   = QPushButton("🍅 Pomodoro")
        focus_btn  = QPushButton("🎯 Focus Mode")
        breath_btn = QPushButton("🌬️ Breathing")
        pomo_btn.clicked.connect(self._request_pomodoro)
        focus_btn.clicked.connect(self._request_focus)
        breath_btn.clicked.connect(self._trigger_breathing)
        for btn in [pomo_btn, focus_btn, breath_btn]:
            a_lo.addWidget(btn)
        lo.addWidget(actions_widget)

        # ── Usage table ───────────────────────────────────────────────────────
        usage_widget = QWidget()
        usage_widget.setStyleSheet(
            "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 10px; }"
        )
        u_lo = QVBoxLayout(usage_widget)
        u_lo.setContentsMargins(14, 12, 14, 12)
        u_lo.setSpacing(6)
        u_hdr = QLabel("USAGE — LAST 7 DAYS")
        u_hdr.setStyleSheet(
            "color: #4a4060; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; background: transparent;"
        )
        u_lo.addWidget(u_hdr)
        self._usage_table = QLabel()
        self._usage_table.setFont(QFont("Monospace", 10))
        self._usage_table.setStyleSheet("color: #8878a0; line-height: 160%; background: transparent;")
        self._usage_table.setWordWrap(True)
        self._usage_table.setTextFormat(Qt.TextFormat.RichText)
        u_lo.addWidget(self._usage_table)
        lo.addWidget(usage_widget)

        # ── Last journal entry ────────────────────────────────────────────────
        journal_widget = QWidget()
        journal_widget.setStyleSheet(
            "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 10px; }"
        )
        j_lo = QVBoxLayout(journal_widget)
        j_lo.setContentsMargins(14, 12, 14, 12)
        j_lo.setSpacing(6)
        j_hdr = QLabel("LAST JOURNAL ENTRY")
        j_hdr.setStyleSheet(
            "color: #4a4060; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; background: transparent;"
        )
        j_lo.addWidget(j_hdr)
        self._home_journal_lbl = QLabel("No entries yet.")
        self._home_journal_lbl.setStyleSheet("color: #5a4f70; font-style: italic; background: transparent;")
        self._home_journal_lbl.setWordWrap(True)
        j_lo.addWidget(self._home_journal_lbl)
        lo.addWidget(journal_widget)

        # ── Word / challenge of day ───────────────────────────────────────────
        today_widget = QWidget()
        today_widget.setStyleSheet(
            "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 10px; }"
        )
        t_lo = QVBoxLayout(today_widget)
        t_lo.setContentsMargins(14, 12, 14, 12)
        t_lo.setSpacing(6)
        t_hdr = QLabel("TODAY")
        t_hdr.setStyleSheet(
            "color: #4a4060; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; background: transparent;"
        )
        t_lo.addWidget(t_hdr)
        self._home_word_lbl = QLabel("—")
        self._home_word_lbl.setWordWrap(True)
        self._home_word_lbl.setStyleSheet("color: #8878a0; background: transparent;")
        t_lo.addWidget(self._home_word_lbl)
        lo.addWidget(today_widget)

        lo.addStretch()
        return self._scrollable(inner)

    def _request_pomodoro(self):
        self.breathing_requested.emit()

    def _request_focus(self):
        pass

    def _home_refresh(self):
        """Update Home tab dynamic values — called by refresh()."""
        d = self._p._data
        self._home_mood_lbl.setText(f"Mood: {d.get('mood', 'happy').capitalize()}")
        self._home_rel_lbl.setText(
            f"Relationship: {self._p.relationship_label}  "
            f"({d.get('interactions', 0)} interactions)"
        )
        streak = d.get("streak", 0)
        self._home_streak_card.findChild(QLabel, "val").setText(
            f"{streak} day{'s' if streak != 1 else ''}"
        )
        self._home_chats_card.findChild(QLabel, "val").setText(str(d.get("interactions", 0)))
        uptime_min = int((time.time() - getattr(self, "_session_start", time.time())) / 60)
        self._home_uptime_card.findChild(QLabel, "val").setText(f"{uptime_min} min")
        journal = d.get("journal", [])
        if journal:
            last = journal[-1]
            self._home_journal_lbl.setText(f"[{last['date']}] {last['entry'][:120]}")
        else:
            self._home_journal_lbl.setText("No entries yet.")
        word = d.get("word_of_day", "")
        challenge = d.get("daily_challenge", "")
        parts = []
        if word:
            parts.append(f"Word: {word}")
        if challenge:
            parts.append(f"Challenge: {challenge}")
        self._home_word_lbl.setText("\n".join(parts) if parts else "—")

        rows = self._p.get_daily_usage(7)
        if rows:
            def _tok(n):
                return f"{n:,}" if n < 1_000_000 else f"{n/1_000_000:.1f}M"
            def _min(m):
                return f"{m}m" if m < 60 else f"{m//60}h{m%60:02d}m"
            header = (
                "<table width='100%' cellspacing='4' style='color:#8878a0;font-size:11px'>"
                "<tr>"
                "<th align='left' style='color:#5a4f70'>Date</th>"
                "<th align='right' style='color:#5a4f70'>In</th>"
                "<th align='right' style='color:#5a4f70'>Out</th>"
                "<th align='right' style='color:#5a4f70'>Total</th>"
                "<th align='right' style='color:#5a4f70'>Time</th>"
                "<th align='right' style='color:#5a4f70'>Sessions</th>"
                "</tr>"
            )
            trs = []
            for r in rows:
                accent = "#a892ff" if r["date"] == str(__import__("datetime").date.today()) else "#8878a0"
                trs.append(
                    f"<tr style='color:{accent}'>"
                    f"<td>{r['date'][5:]}</td>"
                    f"<td align='right'>{_tok(r['input_tokens'])}</td>"
                    f"<td align='right'>{_tok(r['output_tokens'])}</td>"
                    f"<td align='right'><b>{_tok(r['total_tokens'])}</b></td>"
                    f"<td align='right'>{_min(r['total_minutes'])}</td>"
                    f"<td align='right'>{r['session_count']}</td>"
                    f"</tr>"
                )
            self._usage_table.setText(header + "".join(trs) + "</table>")
        else:
            self._usage_table.setText(
                "<i style='color:#5a4f70'>No usage data yet — start chatting!</i>"
            )

    # ═══════════════════════════════════════════ Tab 1 — Character ═══════════

    def _build_character_tab(self) -> QWidget:
        inner = QWidget()
        lo = QVBoxLayout(inner)
        lo.setSpacing(6)
        lo.setContentsMargins(16, 16, 16, 16)

        # ── IDENTITY ──────────────────────────────────────────────────────────
        lo.addWidget(_section_label("IDENTITY"))
        lo.addWidget(_hdivider())

        id_card = QWidget()
        id_card.setStyleSheet(
            "QWidget { background: #111020; border-radius: 10px; } QLabel { background: transparent; }"
        )
        id_lo = QVBoxLayout(id_card)
        id_lo.setContentsMargins(16, 14, 16, 14)
        id_lo.setSpacing(8)

        name_row = QHBoxLayout()
        name_lbl = QLabel("Name")
        name_lbl.setStyleSheet("color: #ccc4e0; font-size: 13px;")
        name_lbl.setFixedWidth(120)
        self._name_edit = QLineEdit()
        name_row.addWidget(name_lbl)
        name_row.addWidget(self._name_edit)
        id_lo.addLayout(name_row)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        stat_data = [
            ("Total interactions", None),
            ("Current mood",       None),
            ("Companion since",    None),
            ("Daily streak",       None),
            ("Relationship",       None),
        ]
        self._interactions_lbl = QLabel()
        self._mood_lbl         = QLabel()
        self._created_lbl      = QLabel()
        self._streak_lbl       = QLabel()
        self._relationship_lbl = QLabel()
        stat_widgets = [
            self._interactions_lbl, self._mood_lbl, self._created_lbl,
            self._streak_lbl, self._relationship_lbl,
        ]
        stat_labels = [
            "Total interactions", "Current mood", "Companion since",
            "Daily streak", "Relationship",
        ]
        for row_i, (ltext, sw) in enumerate(zip(stat_labels, stat_widgets)):
            lbl = QLabel(ltext)
            lbl.setStyleSheet("color: #5a4f70; font-size: 12px;")
            sw.setStyleSheet("color: #ccc4e0; font-size: 12px;")
            stats_grid.addWidget(lbl, row_i, 0)
            stats_grid.addWidget(sw,  row_i, 1)
        id_lo.addLayout(stats_grid)
        lo.addWidget(id_card)

        lo.addSpacing(12)

        # ── PERSONALITY ───────────────────────────────────────────────────────
        lo.addWidget(_section_label("PERSONALITY"))
        lo.addWidget(_hdivider())

        trait_card = QWidget()
        trait_card.setStyleSheet(
            "QWidget { background: #111020; border-radius: 10px; } QLabel { background: transparent; }"
        )
        tc_lo = QVBoxLayout(trait_card)
        tc_lo.setContentsMargins(16, 14, 16, 14)
        tc_lo.setSpacing(10)

        self._humor_s   = _slider()
        self._playful_s = _slider()
        self._helpful_s = _slider()
        self._humor_l   = QLabel()
        self._playful_l = QLabel()
        self._helpful_l = QLabel()
        for s, l in [(self._humor_s, self._humor_l),
                     (self._playful_s, self._playful_l),
                     (self._helpful_s, self._helpful_l)]:
            s.valueChanged.connect(lambda v, lb=l: lb.setText(f"{v}%"))

        for trait_name, slider, label in [
            ("Humor",       self._humor_s,   self._humor_l),
            ("Playfulness", self._playful_s, self._playful_l),
            ("Helpfulness", self._helpful_s, self._helpful_l),
        ]:
            t_row = QHBoxLayout()
            t_lbl = QLabel(trait_name)
            t_lbl.setStyleSheet("color: #ccc4e0; font-size: 13px;")
            t_lbl.setFixedWidth(100)
            t_row.addWidget(t_lbl)
            t_row.addWidget(_row(slider, label), 1)
            tc_lo.addLayout(t_row)

        topics_lbl = QLabel("Topics Pip remembers")
        topics_lbl.setStyleSheet("color: #5a4f70; font-size: 11px; padding-top: 6px;")
        tc_lo.addWidget(topics_lbl)
        self._topics_view = QTextEdit()
        self._topics_view.setReadOnly(True)
        self._topics_view.setMaximumHeight(56)
        tc_lo.addWidget(self._topics_view)

        quips_lbl = QLabel("Custom quips (one per line)")
        quips_lbl.setStyleSheet("color: #5a4f70; font-size: 11px; padding-top: 4px;")
        tc_lo.addWidget(quips_lbl)
        self._quips_edit = QTextEdit()
        self._quips_edit.setMaximumHeight(72)
        self._quips_edit.setPlaceholderText("Type your own quips here, one per line…")
        tc_lo.addWidget(self._quips_edit)

        save_quips_btn = QPushButton("Save Custom Quips")
        save_quips_btn.clicked.connect(self._save_custom_quips)
        tc_lo.addWidget(save_quips_btn)

        p_btns = QHBoxLayout()
        save_personality_btn  = QPushButton("Save Personality")
        reset_personality_btn = QPushButton("Reset Personality")
        reset_personality_btn.setObjectName("danger_btn")
        save_personality_btn.clicked.connect(self._save_personality)
        reset_personality_btn.clicked.connect(self._reset_personality)
        p_btns.addWidget(save_personality_btn)
        p_btns.addWidget(reset_personality_btn)
        p_btns.addStretch()
        tc_lo.addLayout(p_btns)

        lo.addWidget(trait_card)

        lo.addSpacing(12)

        # ── YOUR PROFILE ──────────────────────────────────────────────────────
        lo.addWidget(_section_label("YOUR PROFILE"))
        lo.addWidget(_hdivider())

        profile_card = QWidget()
        profile_card.setStyleSheet(
            "QWidget { background: #111020; border-radius: 10px; } QLabel { background: transparent; }"
        )
        pc_lo = QVBoxLayout(profile_card)
        pc_lo.setContentsMargins(16, 14, 16, 14)
        pc_lo.setSpacing(8)

        pf = QFormLayout()
        pf.setSpacing(8)
        self._user_name_edit = QLineEdit()
        self._user_name_edit.setPlaceholderText("e.g. Alex  (used in greetings)")
        pf.addRow("Your name:", self._user_name_edit)

        self._work_combo = QComboBox()
        self._work_combo.addItems([
            "(not set)", "Developer / Engineer", "Designer",
            "Student", "Writer / Creator", "Other"
        ])
        pf.addRow("Work type:", self._work_combo)

        self._comm_combo = QComboBox()
        self._comm_combo.addItems(["casual", "professional", "playful", "brief", "detailed"])
        pf.addRow("Communication style:", self._comm_combo)

        self._interests_edit = QLineEdit()
        self._interests_edit.setPlaceholderText("e.g. Python, music, coffee (comma-separated)")
        pf.addRow("Interests:", self._interests_edit)
        pc_lo.addLayout(pf)

        save_profile_btn = QPushButton("Save Profile")
        save_profile_btn.clicked.connect(self._save_profile)
        pc_lo.addWidget(save_profile_btn)
        lo.addWidget(profile_card)

        lo.addSpacing(12)

        # ── HISTORY ───────────────────────────────────────────────────────────
        lo.addWidget(_section_label("HISTORY"))
        lo.addWidget(_hdivider())

        history_card = QWidget()
        history_card.setStyleSheet(
            "QWidget { background: #111020; border-radius: 10px; } QLabel { background: transparent; }"
        )
        hc_lo = QVBoxLayout(history_card)
        hc_lo.setContentsMargins(16, 14, 16, 14)
        hc_lo.setSpacing(8)

        hc_lo.addWidget(QLabel("Recent check-ins:"))
        self._checkin_list = QListWidget()
        self._checkin_list.setMaximumHeight(90)
        hc_lo.addWidget(self._checkin_list)

        hc_lo.addWidget(QLabel("Achievements:"))
        self._achievement_list = QListWidget()
        self._achievement_list.setMaximumHeight(80)
        hc_lo.addWidget(self._achievement_list)

        hc_lo.addWidget(QLabel("Your vocabulary:"))
        self._vocab_list = QListWidget()
        self._vocab_list.setMaximumHeight(70)
        hc_lo.addWidget(self._vocab_list)
        lo.addWidget(history_card)

        lo.addSpacing(12)

        # ── COSMETICS ─────────────────────────────────────────────────────────
        lo.addWidget(_section_label("COSMETICS"))
        lo.addWidget(_hdivider())

        from asset_manager import AssetManager
        self._asset_mgr = AssetManager()

        cosm_card = QWidget()
        cosm_card.setStyleSheet(
            "QWidget { background: #111020; border-radius: 10px; } QLabel { background: transparent; }"
        )
        cosm_outer = QVBoxLayout(cosm_card)
        cosm_outer.setContentsMargins(16, 14, 16, 14)
        cosm_outer.setSpacing(8)

        install_row = QHBoxLayout()
        folder_btn = QPushButton("Install from folder…")
        zip_btn    = QPushButton("Install from zip…")
        folder_btn.clicked.connect(self._install_asset_folder)
        zip_btn.clicked.connect(self._install_asset_zip)
        install_row.addWidget(folder_btn)
        install_row.addWidget(zip_btn)
        install_row.addStretch()
        cosm_outer.addLayout(install_row)

        self._cosm_container = QWidget()
        self._cosm_layout    = QVBoxLayout(self._cosm_container)
        self._cosm_layout.setSpacing(6)
        self._cosm_layout.setContentsMargins(0, 0, 0, 0)
        cosm_outer.addWidget(self._cosm_container)
        lo.addWidget(cosm_card)

        self._refresh_cosmetics()

        lo.addStretch()
        return self._scrollable(inner)

    # ═══════════════════════════════════════════ Tab 2 — Memory ══════════════

    def _build_memory_tab(self) -> QWidget:
        inner_tabs = QTabWidget()
        inner_tabs.setObjectName("inner_tabs")
        inner_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # ── Notes ─────────────────────────────────────────────────────────────
        notes_w = QWidget()
        n_lo = QVBoxLayout(notes_w)
        n_lo.setContentsMargins(12, 12, 12, 12)
        n_lo.setSpacing(8)
        n_lo.addWidget(QLabel(
            'Notes saved via chat ("remember: your note").\n'
            "Select a note and press Delete to remove it."
        ))
        self._notes_list = QListWidget()
        n_lo.addWidget(self._notes_list)
        n_btns = QHBoxLayout()
        del_btn   = QPushButton("Delete Selected")
        clear_btn = QPushButton("Clear All")
        del_btn.clicked.connect(self._delete_selected_note)
        clear_btn.clicked.connect(self._clear_all_notes)
        n_btns.addWidget(del_btn)
        n_btns.addWidget(clear_btn)
        n_btns.addStretch()
        n_lo.addLayout(n_btns)
        inner_tabs.addTab(notes_w, "Notes")

        # ── Bookmarks ─────────────────────────────────────────────────────────
        bm_w = QWidget()
        bm_lo = QVBoxLayout(bm_w)
        bm_lo.setContentsMargins(12, 12, 12, 12)
        bm_lo.setSpacing(8)
        bm_lo.addWidget(QLabel('Links saved via chat ("bookmark: url"):'))
        self._bookmarks_list = QListWidget()
        bm_lo.addWidget(self._bookmarks_list)
        bm_btns = QHBoxLayout()
        open_btn   = QPushButton("Open")
        del_bm_btn = QPushButton("Delete")
        open_btn.clicked.connect(self._open_selected_bookmark)
        del_bm_btn.clicked.connect(self._delete_selected_bookmark)
        bm_btns.addWidget(open_btn)
        bm_btns.addWidget(del_bm_btn)
        bm_btns.addStretch()
        bm_lo.addLayout(bm_btns)
        inner_tabs.addTab(bm_w, "Bookmarks")

        # ── Journal ───────────────────────────────────────────────────────────
        journal_w = QWidget()
        j_lo = QVBoxLayout(journal_w)
        j_lo.setContentsMargins(12, 12, 12, 12)
        self._journal_view = QTextEdit()
        self._journal_view.setReadOnly(True)
        j_lo.addWidget(self._journal_view)
        inner_tabs.addTab(journal_w, "Journal")

        # ── Mood ──────────────────────────────────────────────────────────────
        mood_w = QWidget()
        m_lo = QVBoxLayout(mood_w)
        m_lo.setContentsMargins(12, 12, 12, 12)
        m_lo.setSpacing(6)
        m_lo.addWidget(QLabel("Today's mood activity (updates when Pip reacts):"))
        self._mood_chart = MoodChart(self._p._data.get("mood_log", []))
        m_lo.addWidget(self._mood_chart)
        m_lo.addStretch()
        inner_tabs.addTab(mood_w, "Mood")

        return inner_tabs

    # ═══════════════════════════════════════════ Tab 3 — Settings ════════════

    def _build_settings_tab(self) -> QWidget:
        inner = QWidget()
        lo = QVBoxLayout(inner)
        lo.setSpacing(6)
        lo.setContentsMargins(16, 16, 16, 16)

        # ── AI MODEL ─────────────────────────────────────────────────────────
        lo.addWidget(_section_label("AI MODEL"))
        lo.addWidget(_hdivider())
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "claude-sonnet-4-6",
            "claude-opus-4-7",
            "claude-haiku-4-5",
        ])
        idx = self._model_combo.findText(self._s.value("model", "claude-sonnet-4-6"))
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        lo.addWidget(_setting_row("Model", self._model_combo, "Affects response quality and speed"))

        lo.addSpacing(10)

        # ── BEHAVIOR ─────────────────────────────────────────────────────────
        lo.addWidget(_section_label("BEHAVIOR"))
        lo.addWidget(_hdivider())

        self._idle_min = QSpinBox()
        self._idle_min.setRange(10, 300)
        self._idle_min.setSuffix(" sec")
        self._idle_min.setValue(self._s.value("idle_min", 30, type=int))
        self._idle_max = QSpinBox()
        self._idle_max.setRange(30, 600)
        self._idle_max.setSuffix(" sec")
        self._idle_max.setValue(self._s.value("idle_max", 90, type=int))

        idle_row = QWidget()
        idle_row.setStyleSheet(
            "QWidget { background: #130f20; border-radius: 8px; } QLabel { background: transparent; }"
        )
        ir = QHBoxLayout(idle_row)
        ir.setContentsMargins(12, 9, 12, 9)
        ir.setSpacing(10)
        ir_lbl = QLabel("Random event interval")
        ir_lbl.setStyleSheet("color: #ccc4e0; font-size: 13px;")
        ir.addWidget(ir_lbl, 1)
        ir.addWidget(QLabel("min"))
        ir.addWidget(self._idle_min)
        ir.addWidget(QLabel("max"))
        ir.addWidget(self._idle_max)
        lo.addWidget(idle_row)

        self._bubble_sound_cb = QCheckBox()
        self._bubble_sound_cb.setChecked(self._s.value("bubble_sound", False, type=bool))
        lo.addWidget(_setting_row(
            "Bubble sound",
            self._bubble_sound_cb,
            "Play a soft beep when a new bubble appears"
        ))

        lo.addSpacing(10)

        # ── VOICE INPUT ───────────────────────────────────────────────────────
        lo.addWidget(_section_label("VOICE INPUT"))
        lo.addWidget(_hdivider())

        self._voice_enabled_cb = QCheckBox()
        self._voice_enabled_cb.setChecked(self._s.value("voice_enabled", True, type=bool))
        lo.addWidget(_setting_row(
            "Enable microphone button",
            self._voice_enabled_cb,
            "Shows mic button in the chat bubble"
        ))

        self._voice_engine_combo = QComboBox()
        self._voice_engine_combo.addItems(["google", "whisper"])
        engine = self._s.value("voice_engine", "google", type=str)
        self._voice_engine_combo.setCurrentIndex(0 if engine == "google" else 1)
        lo.addWidget(_setting_row(
            "Speech engine",
            self._voice_engine_combo,
            "google = online · whisper = local (pip install openai-whisper)"
        ))

        self._voice_lang_combo = QComboBox()
        self._voice_lang_combo.addItems([
            "en-US", "en-GB", "en-AU",
            "fr-FR", "de-DE", "es-ES", "pt-BR",
            "ja-JP", "zh-CN", "hi-IN",
        ])
        lang = self._s.value("voice_language", "en-US", type=str)
        lang_idx = self._voice_lang_combo.findText(lang)
        self._voice_lang_combo.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        lo.addWidget(_setting_row("Language", self._voice_lang_combo))

        install_hint = QLabel(
            "Required: pip install SpeechRecognition pyaudio"
        )
        install_hint.setStyleSheet("color: #4a4060; font-size: 11px; padding-left: 4px;")
        lo.addWidget(install_hint)

        lo.addSpacing(10)

        # ── GOOGLE CALENDAR ───────────────────────────────────────────────────
        lo.addWidget(_section_label("GOOGLE CALENDAR"))
        lo.addWidget(_hdivider())

        gcal_card = QWidget()
        gcal_card.setStyleSheet(
            "QWidget { background: #130f20; border-radius: 8px; } QLabel { background: transparent; }"
        )
        gcal_lo = QHBoxLayout(gcal_card)
        gcal_lo.setContentsMargins(12, 9, 12, 9)
        gcal_lo.setSpacing(10)
        gcal_col = QVBoxLayout()
        gcal_col.setSpacing(2)
        gcal_title = QLabel("Connect Google Calendar")
        gcal_title.setStyleSheet("color: #ccc4e0; font-size: 13px;")
        self._gcal_status_lbl = QLabel("Status: Not connected")
        self._gcal_status_lbl.setStyleSheet("color: #ff8888; font-size: 11px; font-weight: bold;")
        gcal_col.addWidget(gcal_title)
        gcal_col.addWidget(self._gcal_status_lbl)
        gcal_lo.addLayout(gcal_col, 1)
        self._gcal_connect_btn = QPushButton("Connect Google Calendar")
        self._gcal_connect_btn.clicked.connect(self._gcal_toggle_connection)
        gcal_lo.addWidget(self._gcal_connect_btn)
        lo.addWidget(gcal_card)

        lo.addSpacing(10)

        # ── WELLNESS ─────────────────────────────────────────────────────────
        lo.addWidget(_section_label("WELLNESS"))
        lo.addWidget(_hdivider())

        self._hydration_cb = QCheckBox()
        self._hydration_cb.setChecked(self._s.value("hydration_enabled", True, type=bool))
        lo.addWidget(_setting_row(
            "Hydration reminders",
            self._hydration_cb,
            "Pip will remind you to drink water"
        ))

        self._hydration_spin = QSpinBox()
        self._hydration_spin.setRange(15, 120)
        self._hydration_spin.setSuffix(" min")
        self._hydration_spin.setValue(self._s.value("hydration_interval_min", 45, type=int))
        lo.addWidget(_setting_row("Reminder interval", self._hydration_spin))

        self._eyestrain_cb = QCheckBox()
        self._eyestrain_cb.setChecked(self._s.value("eyestrain_enabled", True, type=bool))
        lo.addWidget(_setting_row(
            "20-20-20 eye-strain reminders",
            self._eyestrain_cb,
            "Every 20 minutes — look 20 feet away for 20 seconds"
        ))

        breath_btn = QPushButton("🌬️  Start Breathing Exercise")
        breath_btn.clicked.connect(self._trigger_breathing)
        lo.addWidget(breath_btn)

        lo.addSpacing(10)

        # ── SCREEN & FOCUS ───────────────────────────────────────────────────
        lo.addWidget(_section_label("SCREEN & FOCUS"))
        lo.addWidget(_hdivider())

        self._deep_watch_cb = QCheckBox()
        self._deep_watch_cb.setChecked(self._s.value("deep_watch", False, type=bool))
        lo.addWidget(_setting_row(
            "Deep screen watcher",
            self._deep_watch_cb,
            "Watches your active window every 3 min — gives tips and nudges"
        ))

        self._quiet_hours_cb = QCheckBox()
        self._quiet_hours_cb.setChecked(self._s.value("quiet_hours_enabled", False, type=bool))
        lo.addWidget(_setting_row(
            "Quiet hours",
            self._quiet_hours_cb,
            "No idle bubbles during quiet hours"
        ))

        self._quiet_start_spin = QSpinBox()
        self._quiet_start_spin.setRange(0, 23)
        self._quiet_start_spin.setSuffix(":00")
        self._quiet_start_spin.setValue(self._s.value("quiet_hours_start", 22, type=int))

        self._quiet_end_spin = QSpinBox()
        self._quiet_end_spin.setRange(0, 23)
        self._quiet_end_spin.setSuffix(":00")
        self._quiet_end_spin.setValue(self._s.value("quiet_hours_end", 8, type=int))

        quiet_range_row = QWidget()
        quiet_range_row.setStyleSheet(
            "QWidget { background: #130f20; border-radius: 8px; } QLabel { background: transparent; }"
        )
        qr = QHBoxLayout(quiet_range_row)
        qr.setContentsMargins(12, 9, 12, 9)
        qr.setSpacing(10)
        qr_lbl = QLabel("Quiet hours range")
        qr_lbl.setStyleSheet("color: #ccc4e0; font-size: 13px;")
        qr.addWidget(qr_lbl, 1)
        qr.addWidget(QLabel("from"))
        qr.addWidget(self._quiet_start_spin)
        qr.addWidget(QLabel("until"))
        qr.addWidget(self._quiet_end_spin)
        lo.addWidget(quiet_range_row)

        self._focus_zone_spin = QSpinBox()
        self._focus_zone_spin.setRange(5, 120)
        self._focus_zone_spin.setSuffix(" min")
        self._focus_zone_spin.setValue(self._s.value("focus_zone_minutes", 25, type=int))
        lo.addWidget(_setting_row(
            "Focus zone duration",
            self._focus_zone_spin,
            "How long a focus session lasts before Pip checks in"
        ))

        lo.addSpacing(10)

        # ── TOOLS ────────────────────────────────────────────────────────────
        lo.addWidget(_section_label("TOOLS"))
        lo.addWidget(_hdivider())

        self._web_search_cb = QCheckBox()
        self._web_search_cb.setChecked(
            "WebSearch" in self._s.value("allowed_tools", "", type=str)
        )
        lo.addWidget(_setting_row(
            "Enable Web Search",
            self._web_search_cb,
            "Passes WebSearch + WebFetch to Claude CLI"
        ))

        self._bash_cb = QCheckBox()
        self._bash_cb.setChecked(
            "Bash" in self._s.value("allowed_tools", "", type=str)
        )
        lo.addWidget(_setting_row(
            "Enable Bash tool",
            self._bash_cb,
            "Lets Pip run shell commands — only enable if you trust the model"
        ))

        lo.addSpacing(10)

        # ── MCP SERVERS ──────────────────────────────────────────────────────
        lo.addWidget(_section_label("MCP SERVERS"))
        lo.addWidget(_hdivider())

        self._use_mcp_cb = QCheckBox()
        self._use_mcp_cb.setChecked(self._s.value("use_mcp", False, type=bool))
        lo.addWidget(_setting_row(
            "Enable MCP servers",
            self._use_mcp_cb,
            "Load external MCP tool servers when chatting"
        ))

        self._mcp_list = QListWidget()
        self._mcp_list.setMaximumHeight(130)
        lo.addWidget(self._mcp_list)

        mcp_btns = QHBoxLayout()
        add_btn  = QPushButton("Add Server")
        edit_btn = QPushButton("Edit")
        del_btn  = QPushButton("Remove")
        add_btn.clicked.connect(self._add_mcp_server)
        edit_btn.clicked.connect(self._edit_mcp_server)
        del_btn.clicked.connect(self._remove_mcp_server)
        for b in [add_btn, edit_btn, del_btn]:
            mcp_btns.addWidget(b)
        mcp_btns.addStretch()
        lo.addLayout(mcp_btns)

        mcp_json_lbl = QLabel("Raw mcp_config.json:")
        mcp_json_lbl.setStyleSheet("color: #5a4f70; font-size: 11px; padding-top: 4px;")
        lo.addWidget(mcp_json_lbl)
        self._mcp_json_view = QTextEdit()
        self._mcp_json_view.setReadOnly(True)
        self._mcp_json_view.setMaximumHeight(90)
        lo.addWidget(self._mcp_json_view)

        lo.addSpacing(10)

        # ── POSITION ─────────────────────────────────────────────────────────
        lo.addWidget(_section_label("POSITION"))
        lo.addWidget(_hdivider())

        reset_pos_btn = QPushButton("Reset to Default Position")
        reset_pos_btn.clicked.connect(self._reset_position)
        lo.addWidget(reset_pos_btn)

        lo.addSpacing(4)

        open_log_btn = QPushButton("Open Log File")
        open_log_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", LOG_FILE]))
        lo.addWidget(open_log_btn)

        lo.addSpacing(16)

        # ── SAVE ALL ─────────────────────────────────────────────────────────
        save_all_btn = QPushButton("Save Settings")
        save_all_btn.setObjectName("primary_btn")
        save_all_btn.clicked.connect(self._save_all_settings)
        lo.addWidget(save_all_btn)

        lo.addStretch()
        return self._scrollable(inner)

    # ═══════════════════════════════════════════ Tab 4 — Log ════════════════

    def _build_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        self._log_filters: dict[str, QCheckBox] = {}
        for level in ['ERROR', 'WARNING', 'INFO', 'DEBUG']:
            cb = QCheckBox(level)
            cb.setChecked(True)
            cb.stateChanged.connect(self._refresh_log)
            self._log_filters[level] = cb
            filter_row.addWidget(cb)
        filter_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_log)
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear_log)
        filter_row.addWidget(refresh_btn)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Monospace", 9))
        self._log_view.setStyleSheet(
            "QTextEdit { background:#0a0812; color:#ccc4e0; border:1px solid #1e1830; }"
        )
        layout.addWidget(self._log_view)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(5000)
        self._refresh_log()
        return widget

    # ── Log level color map ───────────────────────────────────────────────────
    _LOG_LEVEL_COLORS = {
        'ERROR':    '#d46080',
        'CRITICAL': '#d46080',
        'WARNING':  '#f0c030',
        'INFO':     '#ccc4e0',
        'DEBUG':    '#5a4f70',
    }

    def _refresh_log(self):
        log_path = Path.home() / ".pip-companion.log"
        if not log_path.exists():
            self._log_view.setPlainText("(log file not found)")
            return
        try:
            lines = log_path.read_text(errors='replace').splitlines()[-100:]
        except Exception:
            log.error("Failed to read log file", exc_info=True)
            self._log_view.setPlainText("(error reading log file)")
            return

        active_levels = {lvl for lvl, cb in self._log_filters.items() if cb.isChecked()}
        html_lines = []
        for line in lines:
            line_level = 'INFO'
            parts = line.split(' | ', 2)
            if len(parts) >= 2:
                seg = parts[1].strip()
                for lvl in ('CRITICAL', 'ERROR', 'WARNING', 'DEBUG', 'INFO'):
                    if seg == lvl or seg.startswith(lvl):
                        line_level = lvl
                        break
            check_level = 'ERROR' if line_level == 'CRITICAL' else line_level
            if check_level not in active_levels:
                continue
            color = self._LOG_LEVEL_COLORS.get(line_level, '#ccc4e0')
            safe = (line.replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;'))
            html_lines.append(f'<span style="color:{color};">{safe}</span>')

        self._log_view.setHtml(
            '<html><body style="background:#0a0812; font-family:monospace; font-size:9pt;">'
            + '<br>'.join(html_lines)
            + '</body></html>'
        )
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        log_path = Path.home() / ".pip-companion.log"
        try:
            log_path.write_text("")
        except Exception:
            log.error("Failed to clear log file", exc_info=True)
        self._refresh_log()

    # ═══════════════════════════════════════════ Refresh (public) ═════════════

    def refresh(self):
        self._home_refresh()
        d = self._p._data
        self._name_edit.setText(d["name"])
        self._interactions_lbl.setText(str(d["interactions"]))
        self._mood_lbl.setText(d["mood"].capitalize())
        self._created_lbl.setText(d.get("created", "?")[:10])
        streak = d.get("streak", 0)
        self._streak_lbl.setText(f"{streak} day{'s' if streak != 1 else ''} 🔥" if streak else "0 days")
        self._relationship_lbl.setText(
            f"{self._p.relationship_label}  ({d.get('interactions', 0)} interactions)"
        )
        self._humor_s.setValue(int(d["humor"]       * 100))
        self._playful_s.setValue(int(d["playfulness"] * 100))
        self._helpful_s.setValue(int(d["helpfulness"] * 100))
        topics = d.get("topics", [])
        self._topics_view.setPlainText(", ".join(topics) if topics else "(none yet)")
        custom = d.get("custom_quips", [])
        self._quips_edit.setPlainText("\n".join(custom))
        journal = d.get("journal", [])
        if journal:
            lines = [f"{e['date']}: {e['entry']}" for e in reversed(journal[-30:])]
            self._journal_view.setPlainText("\n".join(lines))
        else:
            self._journal_view.setPlainText("No entries yet — come back tomorrow!")
        self._mood_chart.set_log(d.get("mood_log", []))
        self._reload_mcp_list()
        # Notes
        self._notes_list.clear()
        for note in self._p.get_notes():
            ts = note.get("t", "")[:16].replace("T", " ")
            item = QListWidgetItem(f"[{ts}]  {note['text']}")
            self._notes_list.addItem(item)
        # Bookmarks
        self._bookmarks_list.clear()
        for bm in self._p.get_bookmarks():
            title = bm.get("title") or bm.get("url", "")
            self._bookmarks_list.addItem(title)
        # Profile
        profile = self._p.get_profile()
        self._user_name_edit.setText(profile.get("name", ""))
        work_rev = {"": 0, "developer": 1, "designer": 2, "student": 3, "writer": 4, "other": 5}
        self._work_combo.setCurrentIndex(work_rev.get(profile.get("work_type", ""), 0))
        comm_options = ["casual", "professional", "playful", "brief", "detailed"]
        comm = profile.get("communication_style", "casual")
        self._comm_combo.setCurrentIndex(comm_options.index(comm) if comm in comm_options else 0)
        self._interests_edit.setText(", ".join(profile.get("interests", [])))
        self._checkin_list.clear()
        for c in reversed(profile.get("checkins", [])[-7:]):
            self._checkin_list.addItem(f"{c['date']}: {c['mood']}")
        self._achievement_list.clear()
        for a in profile.get("achievements_unlocked", []):
            self._achievement_list.addItem(f"🏆 {a.replace('_', ' ')}")
        self._vocab_list.clear()
        for word, meaning in profile.get("vocabulary", {}).items():
            self._vocab_list.addItem(f"{word} = {meaning}")

    # ═══════════════════════════════════════════ Personality actions ══════════

    def _save_personality(self):
        name = self._name_edit.text().strip()
        if name:
            self._p._data["name"] = name
        self._p._data["humor"]       = self._humor_s.value()   / 100
        self._p._data["playfulness"] = self._playful_s.value() / 100
        self._p._data["helpfulness"] = self._helpful_s.value() / 100
        self._p.save()
        self.settings_changed.emit()
        self.refresh()
        QMessageBox.information(self, "Saved", "Personality updated!")

    def _reset_personality(self):
        if QMessageBox.question(
            self, "Reset",
            "Wipe all of Pip's memories and traits?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            from personality import DATA_FILE
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            self._p.load()
            self.refresh()
            self.settings_changed.emit()

    def _save_custom_quips(self):
        lines = self._quips_edit.toPlainText().splitlines()
        self._p.set_custom_quips(lines)
        QMessageBox.information(self, "Saved", "Custom quips saved!")

    def _save_profile(self):
        work_map = {
            "(not set)": "", "Developer / Engineer": "developer",
            "Designer": "designer", "Student": "student",
            "Writer / Creator": "writer", "Other": "other",
        }
        work_text = self._work_combo.currentText()
        self._p.set_profile_field("work_type", work_map.get(work_text, ""))
        self._p.set_profile_field("communication_style", self._comm_combo.currentText())
        interests = [i.strip() for i in self._interests_edit.text().split(",") if i.strip()]
        self._p.set_profile_field("interests", interests)
        user_name = self._user_name_edit.text().strip()
        self._p.set_profile_field("name", user_name)
        QMessageBox.information(self, "Saved", "Profile saved!")

    def _delete_selected_note(self):
        row = self._notes_list.currentRow()
        if row >= 0:
            self._p.clear_note(row)
            self.refresh()

    def _clear_all_notes(self):
        if QMessageBox.question(
            self, "Clear Notes", "Delete all saved notes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._p.clear_all_notes()
            self.refresh()

    def _open_selected_bookmark(self):
        row = self._bookmarks_list.currentRow()
        if row >= 0:
            bmarks = self._p.get_bookmarks()
            if row < len(bmarks):
                webbrowser.open(bmarks[row].get("url", ""))

    def _delete_selected_bookmark(self):
        row = self._bookmarks_list.currentRow()
        if row >= 0:
            bmarks = self._p.get_bookmarks()
            if row < len(bmarks):
                bmarks.pop(row)
                self._p._data.setdefault("user_profile", {})["bookmarks"] = bmarks
                self._p.save()
                self.refresh()

    # ═══════════════════════════════════════════ Tools actions ════════════════

    def _save_tools(self):
        """Save tool settings without showing a dialog (called by _save_all_settings)."""
        tools = []
        if self._web_search_cb.isChecked():
            tools += ["WebSearch", "WebFetch"]
        if self._bash_cb.isChecked():
            tools.append("Bash")
        self._s.setValue("allowed_tools", ",".join(tools))
        self.settings_changed.emit()

    def _save_mcp(self):
        """Save MCP settings without showing a dialog (called by _save_all_settings)."""
        self._s.setValue("use_mcp", self._use_mcp_cb.isChecked())
        self.settings_changed.emit()

    # ═══════════════════════════════════════════ MCP server management ════════

    def _load_mcp_data(self) -> dict:
        if os.path.exists(self._mcp):
            try:
                with open(self._mcp) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"mcpServers": {}}

    def _save_mcp_data(self, data: dict):
        with open(self._mcp, "w") as f:
            json.dump(data, f, indent=2)

    def _reload_mcp_list(self):
        data = self._load_mcp_data()
        self._mcp_list.clear()
        for name, cfg in data.get("mcpServers", {}).items():
            kind = "http" if "url" in cfg else "stdio"
            item = QListWidgetItem(f"[{kind}]  {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._mcp_list.addItem(item)
        self._mcp_json_view.setPlainText(json.dumps(data, indent=2))

    def _add_mcp_server(self):
        dlg = McpServerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = self._load_mcp_data()
            name, cfg = dlg.result()
            data["mcpServers"][name] = cfg
            self._save_mcp_data(data)
            self._reload_mcp_list()

    def _edit_mcp_server(self):
        item = self._mcp_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        data = self._load_mcp_data()
        cfg  = data["mcpServers"].get(name, {})
        dlg  = McpServerDialog(self, name=name, cfg=cfg)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name, new_cfg = dlg.result()
            del data["mcpServers"][name]
            data["mcpServers"][new_name] = new_cfg
            self._save_mcp_data(data)
            self._reload_mcp_list()

    def _remove_mcp_server(self):
        item = self._mcp_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Remove", f"Remove MCP server '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            data = self._load_mcp_data()
            data["mcpServers"].pop(name, None)
            self._save_mcp_data(data)
            self._reload_mcp_list()

    # ═══════════════════════════════════════════ Settings actions ════════════

    def _save_settings(self):
        """Save core AI/behavior/voice settings. Does NOT show a dialog."""
        if self._idle_min.value() >= self._idle_max.value():
            QMessageBox.warning(self, "Invalid", "Minimum must be less than maximum.")
            return
        self._s.setValue("model",        self._model_combo.currentText())
        self._s.setValue("idle_min",     self._idle_min.value())
        self._s.setValue("idle_max",     self._idle_max.value())
        self._s.setValue("deep_watch",   self._deep_watch_cb.isChecked())
        self._s.setValue("bubble_sound", self._bubble_sound_cb.isChecked())
        v_enabled  = self._voice_enabled_cb.isChecked()
        v_engine   = self._voice_engine_combo.currentText()
        v_language = self._voice_lang_combo.currentText()
        self._s.setValue("voice_enabled",  v_enabled)
        self._s.setValue("voice_engine",   v_engine)
        self._s.setValue("voice_language", v_language)
        self.settings_changed.emit()
        self.voice_config_changed.emit(v_enabled, v_engine, v_language)

    def _save_wellness(self):
        """Save wellness settings. Does NOT show a dialog."""
        self._s.setValue("hydration_enabled", self._hydration_cb.isChecked())
        self._s.setValue("hydration_interval_min", self._hydration_spin.value())
        self._s.setValue("eyestrain_enabled", self._eyestrain_cb.isChecked())
        self._p._data["hydration_enabled"] = self._hydration_cb.isChecked()
        self._p._data["hydration_interval_min"] = self._hydration_spin.value()
        self._p._data["eyestrain_enabled"] = self._eyestrain_cb.isChecked()
        self._p.save()
        self.settings_changed.emit()

    def _save_focus(self):
        """Save focus/quiet-hours settings. Does NOT show a dialog."""
        self._s.setValue("quiet_hours_enabled", self._quiet_hours_cb.isChecked())
        self._s.setValue("quiet_hours_start", self._quiet_start_spin.value())
        self._s.setValue("quiet_hours_end", self._quiet_end_spin.value())
        self._s.setValue("focus_zone_minutes", self._focus_zone_spin.value())
        self._p._data["quiet_hours_enabled"] = self._quiet_hours_cb.isChecked()
        self._p._data["quiet_hours_start"] = self._quiet_start_spin.value()
        self._p._data["quiet_hours_end"] = self._quiet_end_spin.value()
        self._p._data["focus_zone_minutes"] = self._focus_zone_spin.value()
        self._p.save()
        self.settings_changed.emit()

    def _save_all_settings(self):
        """Master save — consolidates all settings tabs into a single save action."""
        self._save_settings()
        self._save_wellness()
        self._save_focus()
        self._save_tools()
        self._save_mcp()
        QMessageBox.information(self, "Saved", "All settings saved!")

    def _reset_position(self):
        self._s.remove("x")
        self._s.remove("y")
        QMessageBox.information(self, "Done", "Position reset. Restart Pip to apply.")

    def _trigger_breathing(self):
        self.breathing_requested.emit()

    # ── Google Calendar helpers ───────────────────────────────────────────────

    def _gcal_refresh_ui(self):
        """Update status label and button text to match current connection state."""
        if self._gcal is None:
            self._gcal_status_lbl.setText(
                "Status: google libraries not installed "
                "(pip install google-api-python-client google-auth-oauthlib)"
            )
            self._gcal_status_lbl.setStyleSheet("color: #ff8888; font-size: 10px;")
            self._gcal_connect_btn.setEnabled(False)
            return
        if self._gcal.is_connected():
            self._gcal_status_lbl.setText("Status: Connected ✓")
            self._gcal_status_lbl.setStyleSheet("color: #88ff88; font-size: 11px; font-weight: bold;")
            self._gcal_connect_btn.setText("Disconnect")
        else:
            self._gcal_status_lbl.setText("Status: Not connected")
            self._gcal_status_lbl.setStyleSheet("color: #ff8888; font-size: 11px; font-weight: bold;")
            self._gcal_connect_btn.setText("Connect Google Calendar")

    def _gcal_toggle_connection(self):
        if self._gcal is None:
            return
        if self._gcal.is_connected():
            reply = QMessageBox.question(
                self, "Disconnect Google Calendar",
                "Disconnect your Google Calendar?\n"
                "Pip will no longer be able to read or manage your events.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._gcal.disconnect()
                self._gcal_refresh_ui()
                self.calendar_status_changed.emit(False)
        else:
            self._gcal_start_connect()

    def _gcal_start_connect(self):
        """Start the OAuth flow; show a setup dialog if credentials.json is missing."""
        from gcal_client import CREDS_FILE
        if not CREDS_FILE.exists():
            self._gcal_show_setup_dialog()
            return
        self._gcal_run_oauth()

    def _gcal_show_setup_dialog(self):
        """Guide the user through one-time Google Cloud credentials setup."""
        from gcal_client import CREDS_FILE, CONFIG_DIR
        dlg = QDialog(self)
        dlg.setWindowTitle("Google Calendar Setup")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet("QDialog { background: #0a0812; color: #ccc4e0; }")
        lo = QVBoxLayout(dlg)

        title = QLabel("<b>One-time setup — takes about 2 minutes</b>")
        title.setTextFormat(Qt.TextFormat.RichText)
        lo.addWidget(title)

        steps = QLabel(
            "Pip needs a Google OAuth credentials file to connect.\n\n"
            "Step 1 — Click the button below to open Google Cloud Console.\n"
            "Step 2 — Create a project (or pick an existing one).\n"
            "Step 3 — Go to APIs & Services → Library → enable \"Google Calendar API\".\n"
            "Step 4 — Go to APIs & Services → OAuth consent screen:\n"
            "         • Fill in App name and support email, then Save.\n"
            "         • Scroll to \"Test users\" → Add Users → add your Gmail address.\n"
            "Step 5 — Go to APIs & Services → Credentials → Create Credentials\n"
            "         → OAuth client ID → Application type: Desktop app → Create.\n"
            "Step 6 — Click the download icon (↓) next to your new credential.\n"
            "Step 7 — Click \"Browse\" below to select the downloaded file.\n"
            "Step 8 — Click \"Connect\" — your browser will open for Google login."
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("font-size: 11px; color: #ccc4e0;")
        lo.addWidget(steps)

        btn_row = QHBoxLayout()
        open_creds_btn = QPushButton("Open Credentials page")
        open_creds_btn.clicked.connect(lambda: webbrowser.open(
            "https://console.cloud.google.com/apis/credentials"
        ))
        open_consent_btn = QPushButton("Open OAuth Consent screen")
        open_consent_btn.clicked.connect(lambda: webbrowser.open(
            "https://console.cloud.google.com/apis/credentials/consent"
        ))
        btn_row.addWidget(open_creds_btn)
        btn_row.addWidget(open_consent_btn)
        lo.addLayout(btn_row)

        browse_row = QHBoxLayout()
        self._gcal_creds_path_lbl = QLabel("File: (not selected)")
        self._gcal_creds_path_lbl.setStyleSheet("color: #9888b8; font-size: 11px;")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(lambda: self._gcal_browse_in_dialog(dlg, connect_btn))
        browse_row.addWidget(self._gcal_creds_path_lbl, 1)
        browse_row.addWidget(browse_btn)
        lo.addLayout(browse_row)

        btns = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        connect_btn = QPushButton("Connect")
        connect_btn.setEnabled(False)
        connect_btn.clicked.connect(lambda: (dlg.accept(), self._gcal_run_oauth()))
        btns.addWidget(cancel_btn)
        btns.addWidget(connect_btn)
        lo.addLayout(btns)

        dlg.exec()

    def _gcal_browse_in_dialog(self, dlg: "QDialog", connect_btn: "QPushButton"):
        from gcal_client import CREDS_FILE, CONFIG_DIR
        import shutil
        path, _ = QFileDialog.getOpenFileName(
            dlg, "Select downloaded credentials JSON",
            os.path.expanduser("~/Downloads"), "JSON files (*.json)"
        )
        if path:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if os.path.abspath(path) != str(CREDS_FILE):
                shutil.copy2(path, CREDS_FILE)
            self._gcal_creds_path_lbl.setText(f"File: {os.path.basename(path)} ✓")
            self._gcal_creds_path_lbl.setStyleSheet("color: #88ff88; font-size: 11px;")
            connect_btn.setEnabled(True)

    def _gcal_run_oauth(self):
        """Start the OAuth flow — opens browser for Google login."""
        self._gcal_connect_btn.setEnabled(False)
        self._gcal_status_lbl.setText("Status: Opening browser for Google login…")
        self._gcal_status_lbl.setStyleSheet("color: #ffdd88; font-size: 11px; font-weight: bold;")
        self._gcal.connect(on_done=self._gcal_on_connect_done)

    def _gcal_on_connect_done(self, success: bool, message: str):
        self._gcal_done.emit(success, message)

    def _gcal_on_connect_done_ui(self, success: bool, message: str):
        self._gcal_connect_btn.setEnabled(True)
        if success:
            self._gcal_refresh_ui()
            self.calendar_status_changed.emit(True)
        else:
            self._gcal_status_lbl.setText("Status: Connection failed")
            self._gcal_status_lbl.setStyleSheet("color: #ff8888; font-size: 11px; font-weight: bold;")
            QMessageBox.warning(self, "Google Calendar", f"Could not connect:\n\n{message}")

    # ═══════════════════════════════════════════ Cosmetics helpers ════════════

    def _refresh_cosmetics(self):
        """Rebuild the cosmetics catalog display."""
        if not hasattr(self, "_asset_mgr"):
            from asset_manager import AssetManager
            self._asset_mgr = AssetManager()

        while self._cosm_layout.count():
            item = self._cosm_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        catalog  = self._asset_mgr.load_catalog()
        equipped = self._asset_mgr.get_equipped()

        if not catalog:
            lbl = QLabel("No assets installed yet.\nUse the buttons above to install some!")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #5a4f70; padding: 24px;")
            self._cosm_layout.addWidget(lbl)
            self._cosm_layout.addStretch()
            return

        categories: dict[str, list[dict]] = {}
        for item in catalog:
            cat = item.get("category", "other")
            categories.setdefault(cat, []).append(item)

        for cat, items in sorted(categories.items()):
            cat_label = QLabel(cat.upper())
            cat_label.setStyleSheet(
                "color: #5a4f70; font-size: 10px; letter-spacing: 1px; padding: 6px 0 2px 0;"
            )
            self._cosm_layout.addWidget(cat_label)

            for item in items:
                item_id     = item.get("id", "")
                item_name   = item.get("name", item_id)
                is_equipped = equipped.get(cat) == item_id

                row = QWidget()
                row.setFixedHeight(40)
                row.setStyleSheet(
                    "QWidget { background: #241d40; border: 1px solid #a892ff; border-radius: 6px; }"
                    if is_equipped else
                    "QWidget { background: #111020; border: 1px solid #1e1830; border-radius: 6px; }"
                )
                rl = QHBoxLayout(row)
                rl.setContentsMargins(8, 4, 8, 4)

                name_lbl = QLabel(item_name)
                name_lbl.setStyleSheet(
                    "color: #a892ff; font-weight: 600;" if is_equipped else "color: #ccc4e0;"
                )
                rl.addWidget(name_lbl, 1)

                if is_equipped:
                    btn = QPushButton("Unequip")
                    btn.setStyleSheet(
                        "QPushButton { color: #d46080; border: 1px solid #d46080; "
                        "border-radius: 4px; padding: 2px 10px; }"
                        "QPushButton:hover { background: #2d1f28; }"
                    )
                    btn.clicked.connect(lambda checked=False, c=cat: self._unequip_asset(c))
                else:
                    btn = QPushButton("Equip")
                    btn.setStyleSheet(
                        "QPushButton { color: #a892ff; border: 1px solid #2a2048; "
                        "border-radius: 4px; padding: 2px 10px; }"
                        "QPushButton:hover { background: #241d40; }"
                    )
                    btn.clicked.connect(
                        lambda checked=False, c=cat, i=item_id: self._equip_asset(c, i)
                    )
                rl.addWidget(btn)
                self._cosm_layout.addWidget(row)

        self._cosm_layout.addStretch()

    def _equip_asset(self, category: str, item_id: str):
        self._asset_mgr.equip(category, item_id)
        self._refresh_cosmetics()

    def _unequip_asset(self, category: str):
        self._asset_mgr.equip(category, None)
        self._refresh_cosmetics()

    def _install_asset_folder(self):
        if not hasattr(self, "_asset_mgr"):
            from asset_manager import AssetManager
            self._asset_mgr = AssetManager()
        folder = QFileDialog.getExistingDirectory(self, "Select Asset Folder")
        if folder:
            ok = self._asset_mgr.install_from_folder(folder)
            if ok:
                QMessageBox.information(self, "Installed", f"Asset installed from:\n{folder}")
                self._refresh_cosmetics()
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"Could not install asset from:\n{folder}\n\n"
                    "Make sure the folder contains a manifest.json."
                )

    def _install_asset_zip(self):
        if not hasattr(self, "_asset_mgr"):
            from asset_manager import AssetManager
            self._asset_mgr = AssetManager()
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Asset Zip", "", "Zip files (*.zip)"
        )
        if path:
            ok = self._asset_mgr.install_from_zip(path)
            if ok:
                QMessageBox.information(self, "Installed", f"Asset installed from:\n{path}")
                self._refresh_cosmetics()
            else:
                QMessageBox.warning(self, "Error", f"Could not install asset from:\n{path}")


# ═══════════════════════════════════════ MCP Server dialog ═══════════════════

class McpServerDialog(QDialog):
    def __init__(self, parent=None, name: str = "", cfg: dict = None):
        super().__init__(parent)
        cfg = cfg or {}
        self.setWindowTitle("MCP Server")
        self.setMinimumWidth(360)
        self.setStyleSheet("QDialog { background: #0a0812; color: #ccc4e0; }")

        lo = QVBoxLayout(self)

        nf = QFormLayout()
        self._name = QLineEdit(name)
        nf.addRow("Server name:", self._name)
        lo.addLayout(nf)

        type_box = QGroupBox("Connection type")
        type_lo = QHBoxLayout(type_box)
        self._stdio_rb = QRadioButton("stdio  (local command)")
        self._http_rb  = QRadioButton("HTTP / SSE  (remote URL)")
        bg = QButtonGroup(self)
        bg.addButton(self._stdio_rb)
        bg.addButton(self._http_rb)
        type_lo.addWidget(self._stdio_rb)
        type_lo.addWidget(self._http_rb)
        lo.addWidget(type_box)

        self._stdio_box = QGroupBox("stdio config")
        sf = QFormLayout(self._stdio_box)
        self._cmd  = QLineEdit(cfg.get("command", ""))
        self._args = QLineEdit(" ".join(cfg.get("args", [])))
        self._env  = QTextEdit()
        self._env.setMaximumHeight(70)
        self._env.setPlaceholderText("KEY=value  (one per line)")
        env_str = "\n".join(f"{k}={v}" for k, v in cfg.get("env", {}).items())
        self._env.setPlainText(env_str)
        sf.addRow("Command:",  self._cmd)
        sf.addRow("Args:",     self._args)
        sf.addRow("Env vars:", self._env)
        lo.addWidget(self._stdio_box)

        self._http_box = QGroupBox("HTTP / SSE config")
        hf = QFormLayout(self._http_box)
        self._url = QLineEdit(cfg.get("url", ""))
        self._url.setPlaceholderText("http://localhost:3000/sse")
        hf.addRow("URL:", self._url)
        lo.addWidget(self._http_box)

        if "url" in cfg:
            self._http_rb.setChecked(True)
        else:
            self._stdio_rb.setChecked(True)

        self._stdio_rb.toggled.connect(self._update_visibility)
        self._update_visibility()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        lo.addWidget(btns)

    def _update_visibility(self):
        self._stdio_box.setVisible(self._stdio_rb.isChecked())
        self._http_box.setVisible(self._http_rb.isChecked())

    def _validate(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Server name is required.")
            return
        if self._stdio_rb.isChecked() and not self._cmd.text().strip():
            QMessageBox.warning(self, "Error", "Command is required for stdio servers.")
            return
        if self._http_rb.isChecked() and not self._url.text().strip():
            QMessageBox.warning(self, "Error", "URL is required for HTTP servers.")
            return
        self.accept()

    def result(self) -> tuple[str, dict]:
        name = self._name.text().strip()
        if self._stdio_rb.isChecked():
            cfg: dict = {"command": self._cmd.text().strip()}
            args = self._args.text().split()
            if args:
                cfg["args"] = args
            env = {}
            for line in self._env.toPlainText().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            if env:
                cfg["env"] = env
        else:
            cfg = {"url": self._url.text().strip()}
        return name, cfg


# ═══════════════════════════════════════ Mood chart ══════════════════════════

class MoodChart(QWidget):
    _COLORS = {
        "HAPPY":    QColor(255, 215,  50),
        "DANCING":  QColor(200, 120, 240),
        "TALKING":  QColor(110, 200, 140),
        "THINKING": QColor(140, 190, 255),
        "SLEEPING": QColor(180, 210, 255),
    }
    _ORDER = ["HAPPY", "DANCING", "TALKING", "THINKING", "SLEEPING"]

    def __init__(self, mood_log: list, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._counts: dict[str, int] = {}
        self.set_log(mood_log)

    def set_log(self, mood_log: list):
        today = _dt.now().date().isoformat()
        counts = {k: 0 for k in self._ORDER}
        for entry in mood_log:
            s = entry.get("s", "")
            if entry.get("t", "").startswith(today) and s in counts:
                counts[s] += 1
        self._counts = counts
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0a0812"))

        if sum(self._counts.values()) == 0:
            p.setPen(QColor("#5a4f70"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No mood data yet today.\nInteract with Pip to see stats!")
            return

        w, h = self.width(), self.height()
        pad = 16
        label_h = 18
        bar_area_h = h - pad * 2 - label_h
        n = len(self._ORDER)
        slot_w = (w - pad * 2) // n
        bar_w = max(8, slot_w - 10)
        max_c = max(self._counts.values()) or 1

        for i, name in enumerate(self._ORDER):
            count = self._counts[name]
            bar_h = int(count / max_c * bar_area_h)
            x = pad + i * slot_w + (slot_w - bar_w) // 2
            y = pad + bar_area_h - bar_h
            color = self._COLORS[name]

            track_color = QColor(color)
            track_color.setAlpha(40)
            p.fillRect(x, pad, bar_w, bar_area_h, track_color)

            if bar_h > 0:
                p.fillRect(x, y, bar_w, bar_h, color)

            p.setPen(QColor("#5a4f70"))
            p.drawText(x, pad + bar_area_h + label_h - 2, name[:4])
            if count:
                p.setPen(QColor(color))
                p.drawText(x + 2, y - 3, str(count))
