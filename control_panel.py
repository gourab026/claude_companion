import json
import logging
import os
import subprocess
import time
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
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, QSize, QTimer

from personality import Personality, DEFAULTS

log = logging.getLogger("pip.main")


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


def _tab_icon_personality(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(5*m), int(1.5*m), int(6*m), int(6*m))
        p.drawArc(int(1*m), int(9*m), int(14*m), int(7*m), 0, 180*16)
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_profile(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(5*m), int(1.5*m), int(6*m), int(6*m))
        p.drawLine(int(8*m), int(7.5*m), int(8*m), int(14*m))
        p.drawLine(int(5*m), int(11*m), int(11*m), int(11*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_mood(size=18):
    def draw(p, s):
        m = s / 16
        p.drawLine(int(2*m), int(13*m), int(2*m),  int(7*m))
        p.drawLine(int(6*m), int(13*m), int(6*m),  int(3*m))
        p.drawLine(int(10*m), int(13*m), int(10*m), int(6*m))
        p.drawLine(int(14*m), int(13*m), int(14*m), int(10*m))
        p.drawLine(int(1*m),  int(13*m), int(15*m), int(13*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_journal(size=18):
    def draw(p, s):
        m = s / 16
        p.drawRoundedRect(int(2*m), int(1.5*m), int(12*m), int(13*m), 1.5*m, 1.5*m)
        p.drawLine(int(5*m), int(5*m),  int(11*m), int(5*m))
        p.drawLine(int(5*m), int(8*m),  int(11*m), int(8*m))
        p.drawLine(int(5*m), int(11*m), int(9*m),  int(11*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_notes(size=18):
    def draw(p, s):
        m = s / 16
        p.drawRoundedRect(int(3*m), int(3*m), int(10*m), int(12*m), 1*m, 1*m)
        p.drawRoundedRect(int(5.5*m), int(1*m), int(5*m), int(4*m), 1*m, 1*m)
        p.drawLine(int(5.5*m), int(8*m),  int(10.5*m), int(8*m))
        p.drawLine(int(5.5*m), int(11*m), int(9*m),    int(11*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_tools(size=18):
    def draw(p, s):
        m = s / 16
        # wrench shape approximation
        p.drawLine(int(3*m), int(13*m), int(9*m), int(7*m))
        p.drawEllipse(int(1*m), int(10*m), int(4*m), int(4*m))
        p.drawEllipse(int(10*m), int(1.5*m), int(4.5*m), int(4.5*m))
        p.drawLine(int(9*m), int(7*m), int(13*m), int(3*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_settings(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(5.5*m), int(5.5*m), int(5*m), int(5*m))
        # gear teeth approximation - 4 lines at cardinal points
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            p.drawLine(int((8+dx*3)*m), int((8+dy*3)*m),
                       int((8+dx*5)*m), int((8+dy*5)*m))
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            p.drawLine(int((8+dx*2.5)*m), int((8+dy*2.5)*m),
                       int((8+dx*4)*m), int((8+dy*4)*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_wellness(size=18):
    def draw(p, s):
        m = s / 16
        p.setBrush(Qt.BrushStyle.NoBrush)
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        pts = QPolygonF([
            QPointF(8*m,  14*m),
            QPointF(2*m,  8*m),
            QPointF(2*m,  5.5*m),
            QPointF(4.5*m, 3*m),
            QPointF(8*m,  6*m),
            QPointF(11.5*m, 3*m),
            QPointF(14*m,  5.5*m),
            QPointF(14*m,  8*m),
        ])
        p.drawPolygon(pts)
    return _cp_make_icon(draw, "#d46080", size)


def _tab_icon_focus(size=18):
    def draw(p, s):
        m = s / 16
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(1*m), int(1*m), int(14*m), int(14*m))
        p.drawEllipse(int(4.5*m), int(4.5*m), int(7*m), int(7*m))
        p.setBrush(QBrush(QColor("#a892ff")))
        p.drawEllipse(int(6.5*m), int(6.5*m), int(3*m), int(3*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_about(size=18):
    def draw(p, s):
        m = s / 16
        p.drawEllipse(int(1*m), int(1*m), int(14*m), int(14*m))
        p.drawLine(int(8*m), int(7*m), int(8*m), int(12*m))
        p.setBrush(QBrush(QColor("#a892ff")))
        p.drawEllipse(int(7*m), int(4*m), int(2*m), int(2*m))
    return _cp_make_icon(draw, "#a892ff", size)


def _tab_icon_log(size=18):
    """Terminal/console icon: a rectangle with three horizontal lines."""
    def draw(p, s):
        m = s / 16
        # outer frame
        p.drawRoundedRect(int(1.5*m), int(2*m), int(13*m), int(12*m), 1.5*m, 1.5*m)
        # prompt chevron
        p.drawLine(int(3.5*m), int(6*m), int(5.5*m), int(8*m))
        p.drawLine(int(5.5*m), int(8*m), int(3.5*m), int(10*m))
        # cursor bar
        p.drawLine(int(7*m), int(8*m), int(12.5*m), int(8*m))
    return _cp_make_icon(draw, "#a892ff", size)


LOG_FILE = os.path.join(os.path.expanduser("~"), ".pip-companion.log")



def _tab_icon_cosmetics(size=18):
    def draw(p, s):
        m = s / 16
        # hat shape
        p.drawLine(int(2*m), int(10*m), int(14*m), int(10*m))
        p.drawRoundedRect(int(4*m), int(4*m), int(8*m), int(6*m), 1*m, 1*m)
        p.drawLine(int(6*m), int(4*m), int(7*m), int(2*m))
        p.drawLine(int(7*m), int(2*m), int(9*m), int(2*m))
    return _cp_make_icon(draw, "#c888ff", size)

class ControlPanel(QWidget):
    settings_changed    = pyqtSignal()
    breathing_requested = pyqtSignal()

    def __init__(self, personality: Personality, settings: QSettings,
                 mcp_config_path: str, parent=None):
        super().__init__(parent)
        self._p   = personality
        self._s   = settings
        self._mcp = mcp_config_path
        self.setWindowTitle("Pip — Control Panel")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(580, 640)

        # ── Dark theme stylesheet ─────────────────────────────────────────────
        self.setStyleSheet("""
            QWidget {
                background: #0f0d1a;
                color: #c0b0d8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #2d2540;
                border-radius: 8px;
                background: #1a1625;
                margin-top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #5a4f70;
                padding: 8px 14px;
                border-radius: 6px;
                margin: 2px 1px;
                min-width: 0px;
            }
            QTabBar::tab:selected {
                background: #2d2540;
                color: #a892ff;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background: #1f1830;
                color: #8878a0;
            }
            QPushButton {
                background: #1a1625;
                color: #a892ff;
                border: 1px solid #2d2540;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2d2540;
                border-color: #7860d4;
            }
            QPushButton:pressed {
                background: #7860d4;
                color: #ffffff;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 6px;
                padding: 6px 10px;
                color: #c0b0d8;
                selection-background-color: #7860d4;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #7860d4;
            }
            QSpinBox {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 6px;
                padding: 4px 8px;
                color: #c0b0d8;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #2d2540;
                border: none;
                border-radius: 3px;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #7860d4;
            }
            QComboBox {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 6px;
                padding: 5px 10px;
                color: #c0b0d8;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background: #1a1625;
                border: 1px solid #2d2540;
                color: #c0b0d8;
                selection-background-color: #7860d4;
            }
            QCheckBox {
                spacing: 8px;
                color: #c0b0d8;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #2d2540;
                border-radius: 4px;
                background: #1a1625;
            }
            QCheckBox::indicator:checked {
                background: #7860d4;
                border-color: #7860d4;
            }
            QLabel {
                color: #8878a0;
            }
            QListWidget {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 6px;
                color: #c0b0d8;
            }
            QListWidget::item:selected {
                background: #2d2540;
                color: #a892ff;
            }
            QListWidget::item:hover {
                background: #1f1830;
            }
            QScrollBar:vertical {
                background: #0f0d1a;
                width: 6px;
                border-radius: 3px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #2d2540;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7860d4;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #0f0d1a;
                height: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #2d2540;
                border-radius: 3px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QGroupBox {
                border: 1px solid #2d2540;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 10px;
                color: #5a4f70;
                font-size: 11px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
            }
            QSlider::groove:horizontal {
                background: #2d2540;
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
                color: #c0b0d8;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #2d2540;
                border-radius: 7px;
                background: #1a1625;
            }
            QRadioButton::indicator:checked {
                background: #7860d4;
                border-color: #7860d4;
            }
            QDialogButtonBox QPushButton {
                min-width: 70px;
            }
        """)

        # ── Search box ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search settings…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet("""
            QLineEdit {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 6px;
                padding: 6px 10px;
                color: #c0b0d8;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #7860d4;
            }
        """)
        self._search.textChanged.connect(self._on_search)

        def _scrollable(w):
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QScrollArea.Shape.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sa.setWidget(w)
            return sa

        self._tabs = QTabWidget()
        self._tabs.setIconSize(QSize(18, 18))
        self._tabs.addTab(self._home_tab(),                    _tab_icon_about(),       "Home")
        self._tabs.addTab(_scrollable(self._personality_tab()),_tab_icon_personality(), "Personality")
        self._tabs.addTab(_scrollable(self._journal_mood_tab()),_tab_icon_mood(),       "Journal & Mood")
        self._tabs.addTab(_scrollable(self._notes_bm_tab()),   _tab_icon_notes(),       "Notes & Bookmarks")
        self._tabs.addTab(_scrollable(self._tools_tab()),      _tab_icon_tools(),       "Tools")
        self._tabs.addTab(_scrollable(self._cosmetics_tab()),  _tab_icon_cosmetics(),   "Cosmetics")
        self._tabs.addTab(_scrollable(self._settings_tab()),   _tab_icon_settings(),    "Settings")
        self._tabs.addTab(self._build_log_tab(),               _tab_icon_log(),         "Log")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._search)
        root.addWidget(self._tabs)

        # Search keyword → tab index map (populated after tabs are built)
        self._search_tab_map = {
            # Home
            "home": 0, "overview": 0, "mood": 0, "streak": 0, "stats": 0,
            "pomodoro": 0, "focus mode": 0, "breathing": 0, "journal": 0,
            # Personality
            "personality": 1, "name": 1, "humor": 1, "playfulness": 1,
            "helpfulness": 1, "traits": 1, "quips": 1, "profile": 1,
            "work": 1, "interests": 1, "communication": 1, "vocabulary": 1,
            "achievements": 1, "checkin": 1, "reset": 1,
            # Journal & Mood
            "journal": 2, "diary": 2, "mood history": 2, "mood chart": 2,
            # Notes & Bookmarks
            "notes": 3, "note": 3, "bookmarks": 3, "bookmark": 3,
            # Tools
            "tools": 4, "mcp": 4, "web search": 4, "bash": 4, "deep watch": 4,
            "wander": 4, "screen watcher": 4, "server": 4,
            # Settings
            "settings": 5, "model": 5, "idle": 5, "position": 5,
            "log file": 5, "sound": 5, "interval": 5,
            # Log
            "log": 6, "error": 6, "debug": 6, "warning": 6,
        }

    # ═══════════════════════════════════════════ Search handler ══════════════

    def _on_search(self, text: str):
        q = text.strip().lower()
        if not q:
            return
        # Find the best matching tab
        for keyword, tab_idx in self._search_tab_map.items():
            if keyword in q or q in keyword:
                self._tabs.setCurrentIndex(tab_idx)
                return
        # Fallback: search all tab names
        for i in range(self._tabs.count()):
            if q in self._tabs.tabText(i).lower():
                self._tabs.setCurrentIndex(i)
                return

    # ═══════════════════════════════════════════ Home tab ════════════════════

    def _home_tab(self):
        def _stat_card(title: str, value: str, accent: str) -> QFrame:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: #1a1625; border: 1px solid {accent}40; "
                f"border-radius: 10px; padding: 8px; }}"
            )
            card_lo = QVBoxLayout(card)
            card_lo.setSpacing(2)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(f"color: {accent}; font-size: 11px; font-weight: 600;")
            val_lbl = QLabel(value)
            val_lbl.setObjectName("val")
            val_lbl.setStyleSheet("color: #e0d8f8; font-size: 18px; font-weight: 700;")
            card_lo.addWidget(title_lbl)
            card_lo.addWidget(val_lbl)
            return card

        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        lo = QVBoxLayout(inner)
        lo.setSpacing(12)
        lo.setContentsMargins(8, 8, 8, 8)

        # ── Pip identity banner ───────────────────────────────────────────────
        d = self._p._data
        identity_box = QGroupBox()
        identity_box.setStyleSheet("QGroupBox { border: 1px solid #2d2540; border-radius: 10px; padding: 14px; }")
        id_lo = QVBoxLayout(identity_box)

        name_lbl = QLabel(d.get("name", "Pip"))
        name_lbl.setStyleSheet("color: #a892ff; font-size: 24px; font-weight: 700;")
        id_lo.addWidget(name_lbl)

        self._home_mood_lbl = QLabel()
        self._home_mood_lbl.setStyleSheet("color: #8878a0; font-size: 13px;")
        id_lo.addWidget(self._home_mood_lbl)

        self._home_rel_lbl = QLabel()
        self._home_rel_lbl.setStyleSheet("color: #7860d4; font-size: 12px; font-weight: 600;")
        id_lo.addWidget(self._home_rel_lbl)
        lo.addWidget(identity_box)

        # ── Stat cards row ────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._home_streak_card  = _stat_card("🔥 Streak",       "0 days",  "#f0a030")
        self._home_chats_card   = _stat_card("💬 Chats",         "0",       "#a892ff")
        self._home_uptime_card  = _stat_card("⏱ Session",       "0 min",   "#60c0a0")
        for c in [self._home_streak_card, self._home_chats_card, self._home_uptime_card]:
            stats_row.addWidget(c)
        lo.addLayout(stats_row)

        # ── Quick actions ─────────────────────────────────────────────────────
        actions_box = QGroupBox("Quick Actions")
        a_lo = QHBoxLayout(actions_box)
        pomo_btn  = QPushButton("🍅 Start Pomodoro")
        focus_btn = QPushButton("🎯 Focus Mode")
        breath_btn = QPushButton("🌬️ Breathing")
        pomo_btn.clicked.connect(self._request_pomodoro)
        focus_btn.clicked.connect(self._request_focus)
        breath_btn.clicked.connect(self._trigger_breathing)
        for btn in [pomo_btn, focus_btn, breath_btn]:
            btn.setStyleSheet("""
                QPushButton { background: #1a1625; color: #a892ff; border: 1px solid #2d2540;
                              border-radius: 6px; padding: 8px 12px; font-weight: 500; }
                QPushButton:hover { background: #2d2540; border-color: #7860d4; }
                QPushButton:pressed { background: #7860d4; color: #fff; }
            """)
            a_lo.addWidget(btn)
        lo.addWidget(actions_box)

        # ── Last journal entry ────────────────────────────────────────────────
        journal_box = QGroupBox("Last Journal Entry")
        j_lo = QVBoxLayout(journal_box)
        self._home_journal_lbl = QLabel("No entries yet.")
        self._home_journal_lbl.setStyleSheet("color: #5a4f70; font-style: italic;")
        self._home_journal_lbl.setWordWrap(True)
        j_lo.addWidget(self._home_journal_lbl)
        lo.addWidget(journal_box)

        # ── Word / challenge of day ───────────────────────────────────────────
        daily_box = QGroupBox("Today")
        d_lo = QVBoxLayout(daily_box)
        self._home_word_lbl = QLabel("—")
        self._home_word_lbl.setWordWrap(True)
        self._home_word_lbl.setStyleSheet("color: #8878a0;")
        d_lo.addWidget(self._home_word_lbl)
        lo.addWidget(daily_box)

        lo.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return w

    def _request_pomodoro(self):
        """Quick-action button — emitted as a breathing-style signal chain."""
        self.breathing_requested.emit()  # reuse signal; main.py overrides as needed

    def _request_focus(self):
        pass  # placeholder; toggled via right-click menu

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
        # Word/challenge
        word = d.get("word_of_day", "")
        challenge = d.get("daily_challenge", "")
        parts = []
        if word:
            parts.append(f"Word: {word}")
        if challenge:
            parts.append(f"Challenge: {challenge}")
        self._home_word_lbl.setText("\n".join(parts) if parts else "—")

    # ═══════════════════════════════════════════ Personality tab ═════════════

    def _personality_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        # Identity
        id_box = QGroupBox("Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        id_form.addRow("Name:", self._name_edit)
        lo.addWidget(id_box)

        # Stats
        stats_box = QGroupBox("Stats")
        sf = QFormLayout(stats_box)
        self._interactions_lbl  = QLabel()
        self._mood_lbl          = QLabel()
        self._created_lbl       = QLabel()
        self._streak_lbl        = QLabel()
        self._relationship_lbl  = QLabel()
        sf.addRow("Total interactions:", self._interactions_lbl)
        sf.addRow("Current mood:",       self._mood_lbl)
        sf.addRow("Companion since:",    self._created_lbl)
        sf.addRow("Daily streak:",       self._streak_lbl)
        sf.addRow("Relationship:",       self._relationship_lbl)
        lo.addWidget(stats_box)

        # Traits
        traits_box = QGroupBox("Personality Traits")
        tf = QFormLayout(traits_box)
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
        tf.addRow("Humor:",       _row(self._humor_s,   self._humor_l))
        tf.addRow("Playfulness:", _row(self._playful_s, self._playful_l))
        tf.addRow("Helpfulness:", _row(self._helpful_s, self._helpful_l))
        lo.addWidget(traits_box)

        # Topics
        topics_box = QGroupBox("Topics Pip Remembers")
        tv = QVBoxLayout(topics_box)
        self._topics_view = QTextEdit()
        self._topics_view.setReadOnly(True)
        self._topics_view.setMaximumHeight(60)
        tv.addWidget(self._topics_view)
        lo.addWidget(topics_box)

        # Custom quips
        quips_box = QGroupBox("Custom Quips (one per line)")
        qv = QVBoxLayout(quips_box)
        self._quips_edit = QTextEdit()
        self._quips_edit.setMaximumHeight(80)
        self._quips_edit.setPlaceholderText("Type your own quips here, one per line…")
        save_quips_btn = QPushButton("Save Custom Quips")
        save_quips_btn.clicked.connect(self._save_custom_quips)
        qv.addWidget(self._quips_edit)
        qv.addWidget(save_quips_btn)
        lo.addWidget(quips_box)

        # ── Your Profile (merged from former Profile tab) ─────────────────────
        profile_box = QGroupBox("Your Profile")
        pf = QFormLayout(profile_box)
        self._user_name_edit = QLineEdit()
        self._user_name_edit.setPlaceholderText("e.g. Alex  (used in greetings)")
        pf.addRow("Your name:", self._user_name_edit)
        self._work_combo = QComboBox()
        self._work_combo.addItems(["(not set)", "Developer / Engineer", "Designer", "Student", "Writer / Creator", "Other"])
        pf.addRow("Work type:", self._work_combo)
        self._comm_combo = QComboBox()
        self._comm_combo.addItems(["casual", "professional", "playful", "brief", "detailed"])
        pf.addRow("Communication style:", self._comm_combo)
        self._interests_edit = QLineEdit()
        self._interests_edit.setPlaceholderText("e.g. Python, music, coffee (comma-separated)")
        pf.addRow("Interests:", self._interests_edit)
        save_profile_btn = QPushButton("Save Profile")
        save_profile_btn.clicked.connect(self._save_profile)
        pf.addRow("", save_profile_btn)

        self._checkin_list = QListWidget()
        self._checkin_list.setMaximumHeight(90)
        pf.addRow("Recent check-ins:", self._checkin_list)
        self._achievement_list = QListWidget()
        self._achievement_list.setMaximumHeight(80)
        pf.addRow("Achievements:", self._achievement_list)
        self._vocab_list = QListWidget()
        self._vocab_list.setMaximumHeight(70)
        pf.addRow("Your vocab:", self._vocab_list)
        lo.addWidget(profile_box)

        # Buttons
        btns = QHBoxLayout()
        save_btn  = QPushButton("Save Changes")
        reset_btn = QPushButton("Reset Personality")
        reset_btn.setStyleSheet(
            "QPushButton { color: #d46080; border-color: #d46080; }"
            "QPushButton:hover { background: #2d1f28; border-color: #d46080; }"
        )
        save_btn.clicked.connect(self._save_personality)
        reset_btn.clicked.connect(self._reset_personality)
        btns.addWidget(save_btn)
        btns.addWidget(reset_btn)
        lo.addLayout(btns)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Profile tab ═════════════════

    def _profile_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        form = QFormLayout()

        # Improvement 9: "Your name" field
        self._user_name_edit = QLineEdit()
        self._user_name_edit.setPlaceholderText("e.g. Alex  (used in greetings)")
        form.addRow("Your name:", self._user_name_edit)

        self._work_combo = QComboBox()
        self._work_combo.addItems(["(not set)", "Developer / Engineer", "Designer", "Student", "Writer / Creator", "Other"])
        form.addRow("Work type:", self._work_combo)

        self._comm_combo = QComboBox()
        self._comm_combo.addItems(["casual", "professional", "playful", "brief", "detailed"])
        form.addRow("Communication style:", self._comm_combo)

        self._interests_edit = QLineEdit()
        self._interests_edit.setPlaceholderText("e.g. Python, music, coffee (comma-separated)")
        form.addRow("Interests:", self._interests_edit)

        lay.addLayout(form)

        save_btn = QPushButton("Save Profile")
        save_btn.clicked.connect(self._save_profile)
        lay.addWidget(save_btn)

        lay.addWidget(QLabel("Recent check-ins:"))
        self._checkin_list = QListWidget()
        self._checkin_list.setMaximumHeight(120)
        lay.addWidget(self._checkin_list)

        lay.addWidget(QLabel("Achievements:"))
        self._achievement_list = QListWidget()
        self._achievement_list.setMaximumHeight(100)
        lay.addWidget(self._achievement_list)

        lay.addWidget(QLabel("Vocabulary (word = meaning):"))
        self._vocab_list = QListWidget()
        self._vocab_list.setMaximumHeight(80)
        lay.addWidget(self._vocab_list)

        lay.addStretch()
        return w

    def _save_profile(self):
        work_map = {"(not set)": "", "Developer / Engineer": "developer", "Designer": "designer",
                    "Student": "student", "Writer / Creator": "writer", "Other": "other"}
        work_text = self._work_combo.currentText()
        self._p.set_profile_field("work_type", work_map.get(work_text, ""))
        self._p.set_profile_field("communication_style", self._comm_combo.currentText())
        interests = [i.strip() for i in self._interests_edit.text().split(",") if i.strip()]
        self._p.set_profile_field("interests", interests)
        # Improvement 9: save user's name
        user_name = self._user_name_edit.text().strip()
        self._p.set_profile_field("name", user_name)
        QMessageBox.information(self, "Saved", "Profile saved!")

    # ═══════════════════════════════════════ Journal & Mood tab (combined) ════

    def _journal_mood_tab(self):
        """Combined tab: journal diary + mood history chart."""
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setSpacing(8)
        lo.setContentsMargins(6, 6, 6, 6)

        # Journal section
        j_box = QGroupBox("Pip's Journal")
        j_lo = QVBoxLayout(j_box)
        j_lo.addWidget(QLabel("Daily diary — written at the end of each session:"))
        self._journal_view = QTextEdit()
        self._journal_view.setReadOnly(True)
        self._journal_view.setMaximumHeight(180)
        j_lo.addWidget(self._journal_view)
        lo.addWidget(j_box)

        # Mood history section
        m_box = QGroupBox("Mood History")
        m_lo = QVBoxLayout(m_box)
        m_lo.addWidget(QLabel("Today's mood activity (updates when Pip reacts):"))
        self._mood_chart = MoodChart(self._p._data.get("mood_log", []))
        m_lo.addWidget(self._mood_chart)
        lo.addWidget(m_box)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════ Notes & Bookmarks tab (combined) ═

    def _notes_bm_tab(self):
        """Combined tab: notes + bookmarks."""
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setSpacing(8)
        lo.setContentsMargins(6, 6, 6, 6)

        # Notes section
        n_box = QGroupBox("Notes")
        n_lo = QVBoxLayout(n_box)
        n_lo.addWidget(QLabel(
            "Notes saved via chat (\"remember: your note\").\n"
            "Select a note and press Delete to remove it."
        ))
        self._notes_list = QListWidget()
        n_lo.addWidget(self._notes_list)
        btns = QHBoxLayout()
        del_btn = QPushButton("Delete Selected")
        clear_btn = QPushButton("Clear All")
        del_btn.clicked.connect(self._delete_selected_note)
        clear_btn.clicked.connect(self._clear_all_notes)
        btns.addWidget(del_btn)
        btns.addWidget(clear_btn)
        n_lo.addLayout(btns)
        lo.addWidget(n_box)

        # Bookmarks section
        bm_box = QGroupBox("Bookmarks")
        bm_lo = QVBoxLayout(bm_box)
        bm_lo.addWidget(QLabel("Links saved via chat (\"bookmark: url\"):"))
        self._bookmarks_list = QListWidget()
        bm_lo.addWidget(self._bookmarks_list)
        bm_btns = QHBoxLayout()
        open_btn = QPushButton("Open")
        del_bm_btn = QPushButton("Delete")
        open_btn.clicked.connect(self._open_selected_bookmark)
        del_bm_btn.clicked.connect(self._delete_selected_bookmark)
        bm_btns.addWidget(open_btn)
        bm_btns.addWidget(del_bm_btn)
        bm_lo.addLayout(bm_btns)
        lo.addWidget(bm_box)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Notes tab ══════════════════

    def _notes_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.addWidget(QLabel(
            "Notes saved via chat (\"remember: your note\").\n"
            "Select a note and press Delete to remove it."
        ))
        self._notes_list = QListWidget()
        lo.addWidget(self._notes_list)
        btns = QHBoxLayout()
        del_btn   = QPushButton("Delete Selected")
        clear_btn = QPushButton("Clear All")
        del_btn.clicked.connect(self._delete_selected_note)
        clear_btn.clicked.connect(self._clear_all_notes)
        btns.addWidget(del_btn)
        btns.addWidget(clear_btn)
        lo.addLayout(btns)
        return w

    # ═══════════════════════════════════════════ Journal tab ════════════════

    def _journal_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.addWidget(QLabel("Pip's daily diary (written at the end of each session):"))
        self._journal_view = QTextEdit()
        self._journal_view.setReadOnly(True)
        lo.addWidget(self._journal_view)
        return w

    # ═══════════════════════════════════════════ Mood History tab ════════════

    def _mood_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.addWidget(QLabel("Today's mood activity (updates when Pip reacts):"))
        self._mood_chart = MoodChart(self._p._data.get("mood_log", []))
        lo.addWidget(self._mood_chart)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Tools & MCP tab ═════════════

    def _tools_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        # Built-in tools
        tools_box = QGroupBox("Built-in Tool Permissions")
        tlo = QVBoxLayout(tools_box)

        self._web_search_cb = QCheckBox("Enable Web Search  (WebSearch + WebFetch)")
        self._web_search_cb.setToolTip(
            "Passes --allowedTools WebSearch,WebFetch to the Claude CLI.\n"
            "Pip can then look things up on the web when answering questions."
        )
        self._web_search_cb.setChecked(
            "WebSearch" in self._s.value("allowed_tools", "", type=str)
        )
        tlo.addWidget(self._web_search_cb)

        self._bash_cb = QCheckBox("Enable Bash tool  (lets Pip run shell commands)")
        self._bash_cb.setToolTip(
            "Passes Bash in --allowedTools. Use only if you trust the model\n"
            "to execute commands on your machine."
        )
        self._bash_cb.setChecked(
            "Bash" in self._s.value("allowed_tools", "", type=str)
        )
        tlo.addWidget(self._bash_cb)

        save_tools_btn = QPushButton("Save Tool Settings")
        save_tools_btn.clicked.connect(self._save_tools)
        tlo.addWidget(save_tools_btn)
        lo.addWidget(tools_box)

        # MCP servers
        mcp_box = QGroupBox("MCP Servers")
        mlo = QVBoxLayout(mcp_box)

        self._use_mcp_cb = QCheckBox("Enable MCP servers")
        self._use_mcp_cb.setChecked(self._s.value("use_mcp", False, type=bool))
        mlo.addWidget(self._use_mcp_cb)

        self._mcp_list = QListWidget()
        self._mcp_list.setMaximumHeight(140)
        mlo.addWidget(self._mcp_list)

        mcp_btns = QHBoxLayout()
        add_btn  = QPushButton("Add Server")
        edit_btn = QPushButton("Edit")
        del_btn  = QPushButton("Remove")
        add_btn.clicked.connect(self._add_mcp_server)
        edit_btn.clicked.connect(self._edit_mcp_server)
        del_btn.clicked.connect(self._remove_mcp_server)
        for b in [add_btn, edit_btn, del_btn]:
            mcp_btns.addWidget(b)
        mlo.addLayout(mcp_btns)

        # Raw JSON viewer
        mlo.addWidget(QLabel("Raw mcp_config.json:"))
        self._mcp_json_view = QTextEdit()
        self._mcp_json_view.setReadOnly(True)
        self._mcp_json_view.setMaximumHeight(100)
        mlo.addWidget(self._mcp_json_view)

        save_mcp_btn = QPushButton("Save MCP Settings")
        save_mcp_btn.clicked.connect(self._save_mcp)
        mlo.addWidget(save_mcp_btn)

        lo.addWidget(mcp_box)
        lo.addStretch()
        self._reload_mcp_list()
        return w


    # ═══════════════════════════════════════════ Cosmetics tab ═══════════════

    def _cosmetics_tab(self):
        from asset_manager import AssetManager
        self._asset_mgr = AssetManager()

        w = QWidget()
        outer = QVBoxLayout(w)

        # Install buttons row
        install_row = QHBoxLayout()
        folder_btn = QPushButton("Install from folder...")
        zip_btn    = QPushButton("Install from zip...")
        folder_btn.clicked.connect(self._install_asset_folder)
        zip_btn.clicked.connect(self._install_asset_zip)
        install_row.addWidget(folder_btn)
        install_row.addWidget(zip_btn)
        install_row.addStretch()
        outer.addLayout(install_row)

        # Scrollable catalog area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cosm_container = QWidget()
        self._cosm_layout    = QVBoxLayout(self._cosm_container)
        self._cosm_layout.setSpacing(6)
        scroll.setWidget(self._cosm_container)
        outer.addWidget(scroll)

        self._refresh_cosmetics()
        return w

    def _refresh_cosmetics(self):
        """Rebuild the cosmetics catalog display."""
        if not hasattr(self, "_asset_mgr"):
            from asset_manager import AssetManager
            self._asset_mgr = AssetManager()

        # Clear existing widgets
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

        # Group by category
        categories: dict[str, list[dict]] = {}
        for item in catalog:
            cat = item.get("category", "other")
            categories.setdefault(cat, []).append(item)

        for cat, items in sorted(categories.items()):
            cat_label = QLabel(cat.upper())
            cat_label.setStyleSheet("color: #5a4f70; font-size: 10px; letter-spacing: 1px; padding: 6px 0 2px 0;")
            self._cosm_layout.addWidget(cat_label)

            for item in items:
                item_id      = item.get("id", "")
                item_name    = item.get("name", item_id)
                is_equipped  = equipped.get(cat) == item_id

                row = QWidget()
                row.setFixedHeight(40)
                row_style = (
                    "QWidget { background: #2d2540; border: 1px solid #a892ff; border-radius: 6px; }"
                    if is_equipped else
                    "QWidget { background: #1a1625; border: 1px solid #2d2540; border-radius: 6px; }"
                )
                row.setStyleSheet(row_style)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(8, 4, 8, 4)

                name_lbl = QLabel(item_name)
                name_lbl.setStyleSheet("color: #c0b0d8;" if not is_equipped else "color: #a892ff; font-weight: 600;")
                rl.addWidget(name_lbl, 1)

                if is_equipped:
                    btn = QPushButton("Unequip")
                    btn.setStyleSheet(
                        "QPushButton { color: #d46080; border: 1px solid #d46080; border-radius: 4px; padding: 2px 10px; }"
                        "QPushButton:hover { background: #2d1f28; }"
                    )
                    btn.clicked.connect(lambda checked=False, c=cat: self._unequip_asset(c))
                else:
                    btn = QPushButton("Equip")
                    btn.setStyleSheet(
                        "QPushButton { color: #a892ff; border: 1px solid #2d2540; border-radius: 4px; padding: 2px 10px; }"
                        "QPushButton:hover { background: #2d2540; }"
                    )
                    btn.clicked.connect(lambda checked=False, c=cat, i=item_id: self._equip_asset(c, i))
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
                QMessageBox.warning(self, "Error", f"Could not install asset from:\n{folder}\n\nMake sure the folder contains a manifest.json.")

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

    # ═══════════════════════════════════════════ Settings tab ════════════════

    def _settings_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        model_box = QGroupBox("AI Model")
        mf = QFormLayout(model_box)
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "claude-sonnet-4-6",
            "claude-opus-4-7",
            "claude-haiku-4-5",
        ])
        idx = self._model_combo.findText(self._s.value("model", "claude-sonnet-4-6"))
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        mf.addRow("Model:", self._model_combo)
        lo.addWidget(model_box)

        idle_box = QGroupBox("Random Event Interval")
        idf = QFormLayout(idle_box)
        self._idle_min = QSpinBox()
        self._idle_min.setRange(10, 300); self._idle_min.setSuffix(" sec")
        self._idle_min.setValue(self._s.value("idle_min", 30, type=int))
        self._idle_max = QSpinBox()
        self._idle_max.setRange(30, 600); self._idle_max.setSuffix(" sec")
        self._idle_max.setValue(self._s.value("idle_max", 90, type=int))
        idf.addRow("Minimum:", self._idle_min)
        idf.addRow("Maximum:", self._idle_max)
        lo.addWidget(idle_box)

        pos_box = QGroupBox("Window Position")
        plo = QVBoxLayout(pos_box)
        reset_pos = QPushButton("Reset to Default Position")
        reset_pos.clicked.connect(self._reset_position)
        plo.addWidget(reset_pos)
        lo.addWidget(pos_box)

        watcher_box = QGroupBox("Screen Watcher")
        wlo = QVBoxLayout(watcher_box)
        self._deep_watch_cb = QCheckBox("Deep screen watcher")
        self._deep_watch_cb.setToolTip(
            "When enabled, Pip watches your active window every 3 minutes:\n"
            "• Gives language-specific tips when you edit code files\n"
            "• Searches for optimization tips for recognized tools\n"
            "• Alerts you if you're juggling too many apps at once\n"
            "• Nudges you after 45 minutes in the same window\n"
            "\nDefault: off. Use 'What am I doing?' in the right-click menu anytime."
        )
        self._deep_watch_cb.setChecked(self._s.value("deep_watch", False, type=bool))
        wlo.addWidget(self._deep_watch_cb)
        lo.addWidget(watcher_box)

        # Improvement 10: bubble sound toggle
        sound_box = QGroupBox("Bubble Sound")
        slo = QVBoxLayout(sound_box)
        self._bubble_sound_cb = QCheckBox("Play a soft beep when a new bubble appears")
        self._bubble_sound_cb.setChecked(self._s.value("bubble_sound", False, type=bool))
        slo.addWidget(self._bubble_sound_cb)
        lo.addWidget(sound_box)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        lo.addWidget(save_btn)

        log_btn = QPushButton("Open Log File")
        log_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", LOG_FILE]))
        lo.addWidget(log_btn)

        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ About tab ═══════════════════

    def _about_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lbl = QLabel(
            "<h2>Pip — Desktop Companion</h2>"
            "<p>A pixel-art AI companion powered by the <b>Claude Code CLI</b>.<br>"
            "No API key needed — uses your local Claude Code session.</p>"
            "<hr>"
            "<p><b>Controls</b><br>"
            "&nbsp;• Left-click → chat &nbsp;• Right-click → menu &nbsp;• Drag → move</p>"
            "<p><b>Personality</b><br>"
            "Pip tracks topics, drifts in humor &amp; playfulness over time,<br>"
            "and adapts her mood based on your conversations.</p>"
            "<p><b>Tools</b><br>"
            "Enable Web Search so Pip can look things up.<br>"
            "Add MCP servers for custom integrations.</p>"
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        lo.addWidget(lbl)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Refresh (public) ════════════

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
        # Profile tab
        profile = self._p.get_profile()
        # Improvement 9: populate user name
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
                import webbrowser
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

    def _save_custom_quips(self):
        lines = self._quips_edit.toPlainText().splitlines()
        self._p.set_custom_quips(lines)
        QMessageBox.information(self, "Saved", "Custom quips saved!")

    # ═══════════════════════════════════════════ Tools actions ════════════════

    def _save_tools(self):
        tools = []
        if self._web_search_cb.isChecked():
            tools += ["WebSearch", "WebFetch"]
        if self._bash_cb.isChecked():
            tools.append("Bash")
        self._s.setValue("allowed_tools", ",".join(tools))
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Tool settings saved!")

    def _save_mcp(self):
        self._s.setValue("use_mcp", self._use_mcp_cb.isChecked())
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "MCP settings saved!")

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
        if self._idle_min.value() >= self._idle_max.value():
            QMessageBox.warning(self, "Invalid", "Minimum must be less than maximum.")
            return
        self._s.setValue("model",        self._model_combo.currentText())
        self._s.setValue("idle_min",     self._idle_min.value())
        self._s.setValue("idle_max",     self._idle_max.value())
        self._s.setValue("deep_watch",   self._deep_watch_cb.isChecked())
        self._s.setValue("bubble_sound", self._bubble_sound_cb.isChecked())
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Settings saved!")

    def _reset_position(self):
        self._s.remove("x"); self._s.remove("y")
        QMessageBox.information(self, "Done", "Position reset. Restart Pip to apply.")

    # ═══════════════════════════════════════════ Wellness tab ════════════════

    def _wellness_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        form = QFormLayout()
        self._hydration_cb = QCheckBox("Enable hydration reminders")
        self._hydration_cb.setChecked(self._s.value("hydration_enabled", True, type=bool))
        form.addRow(self._hydration_cb)

        self._hydration_spin = QSpinBox()
        self._hydration_spin.setRange(15, 120)
        self._hydration_spin.setSuffix(" min")
        self._hydration_spin.setValue(self._s.value("hydration_interval_min", 45, type=int))
        form.addRow("Reminder interval:", self._hydration_spin)

        self._eyestrain_cb = QCheckBox("Enable 20-20-20 eye-strain reminders (every 20 min)")
        self._eyestrain_cb.setChecked(self._s.value("eyestrain_enabled", True, type=bool))
        form.addRow(self._eyestrain_cb)

        lay.addLayout(form)

        breathing_btn = QPushButton("Start Breathing Exercise 🌬️")
        breathing_btn.clicked.connect(self._trigger_breathing)
        lay.addWidget(breathing_btn)

        save_btn = QPushButton("Save Wellness Settings")
        save_btn.clicked.connect(self._save_wellness)
        lay.addWidget(save_btn)
        lay.addStretch()
        return w

    # ═══════════════════════════════════════════ Focus tab ════════════════════

    def _focus_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        form = QFormLayout()

        self._quiet_hours_cb = QCheckBox("Enable quiet hours (no idle bubbles)")
        self._quiet_hours_cb.setChecked(self._s.value("quiet_hours_enabled", False, type=bool))
        form.addRow(self._quiet_hours_cb)

        self._quiet_start_spin = QSpinBox()
        self._quiet_start_spin.setRange(0, 23)
        self._quiet_start_spin.setSuffix(":00")
        self._quiet_start_spin.setValue(self._s.value("quiet_hours_start", 22, type=int))
        form.addRow("Quiet from:", self._quiet_start_spin)

        self._quiet_end_spin = QSpinBox()
        self._quiet_end_spin.setRange(0, 23)
        self._quiet_end_spin.setSuffix(":00")
        self._quiet_end_spin.setValue(self._s.value("quiet_hours_end", 8, type=int))
        form.addRow("Quiet until:", self._quiet_end_spin)

        self._focus_zone_spin = QSpinBox()
        self._focus_zone_spin.setRange(5, 120)
        self._focus_zone_spin.setSuffix(" min")
        self._focus_zone_spin.setValue(self._s.value("focus_zone_minutes", 25, type=int))
        form.addRow("Focus zone duration:", self._focus_zone_spin)

        lay.addLayout(form)
        save_btn = QPushButton("Save Focus Settings")
        save_btn.clicked.connect(self._save_focus)
        lay.addWidget(save_btn)
        lay.addStretch()
        return w

    def _save_wellness(self):
        self._s.setValue("hydration_enabled", self._hydration_cb.isChecked())
        self._s.setValue("hydration_interval_min", self._hydration_spin.value())
        self._s.setValue("eyestrain_enabled", self._eyestrain_cb.isChecked())
        self._p._data["hydration_enabled"] = self._hydration_cb.isChecked()
        self._p._data["hydration_interval_min"] = self._hydration_spin.value()
        self._p._data["eyestrain_enabled"] = self._eyestrain_cb.isChecked()
        self._p.save()
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Wellness settings saved!")

    def _save_focus(self):
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
        QMessageBox.information(self, "Saved", "Focus settings saved!")

    def _trigger_breathing(self):
        self.breathing_requested.emit()

    # ═══════════════════════════════════════════ Log tab ═════════════════════

    def _build_log_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Filter row
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
            "QTextEdit { background:#0a0812; color:#c0b0d8; border:1px solid #2d2540; }"
        )
        layout.addWidget(self._log_view)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(5000)
        self._refresh_log()
        return widget

    # Level color map for the log viewer
    _LOG_LEVEL_COLORS = {
        'ERROR':    '#d46080',
        'CRITICAL': '#d46080',
        'WARNING':  '#f0c030',
        'INFO':     '#c0b0d8',
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

        # Determine which levels are visible
        active_levels = {lvl for lvl, cb in self._log_filters.items() if cb.isChecked()}

        html_lines = []
        for line in lines:
            # Detect level from the structured format:
            # "2026-05-21 13:45:01 | INFO     | pip.claude — ..."
            # Split on ' | ' and check the second segment (index 1).
            line_level = 'INFO'  # default
            parts = line.split(' | ', 2)
            if len(parts) >= 2:
                seg = parts[1].strip()
                for lvl in ('CRITICAL', 'ERROR', 'WARNING', 'DEBUG', 'INFO'):
                    if seg == lvl or seg.startswith(lvl):
                        line_level = lvl
                        break

            # Filter by checkbox (CRITICAL maps to ERROR checkbox)
            check_level = 'ERROR' if line_level == 'CRITICAL' else line_level
            if check_level not in active_levels:
                continue

            color = self._LOG_LEVEL_COLORS.get(line_level, '#c0b0d8')
            # Escape HTML special chars
            safe = (line.replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;'))
            html_lines.append(f'<span style="color:{color};">{safe}</span>')

        self._log_view.setHtml(
            '<html><body style="background:#0a0812; font-family:monospace; font-size:9pt;">'
            + '<br>'.join(html_lines)
            + '</body></html>'
        )
        # Scroll to bottom
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        log_path = Path.home() / ".pip-companion.log"
        try:
            log_path.write_text("")
        except Exception:
            log.error("Failed to clear log file", exc_info=True)
        self._refresh_log()


# ═══════════════════════════════════════ MCP Server dialog ═══════════════════

class McpServerDialog(QDialog):
    def __init__(self, parent=None, name: str = "", cfg: dict = None):
        super().__init__(parent)
        cfg = cfg or {}
        self.setWindowTitle("MCP Server")
        self.setMinimumWidth(360)
        # Inherit dark theme from parent; ensure dialog background matches
        self.setStyleSheet("""
            QDialog { background: #0f0d1a; color: #c0b0d8; }
        """)

        lo = QVBoxLayout(self)

        # Name
        nf = QFormLayout()
        self._name = QLineEdit(name)
        nf.addRow("Server name:", self._name)
        lo.addLayout(nf)

        # Type
        type_box = QGroupBox("Connection type")
        type_lo = QHBoxLayout(type_box)
        self._stdio_rb = QRadioButton("stdio  (local command)")
        self._http_rb  = QRadioButton("HTTP / SSE  (remote URL)")
        bg = QButtonGroup(self)
        bg.addButton(self._stdio_rb); bg.addButton(self._http_rb)
        type_lo.addWidget(self._stdio_rb); type_lo.addWidget(self._http_rb)
        lo.addWidget(type_box)

        # stdio fields
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

        # HTTP fields
        self._http_box = QGroupBox("HTTP / SSE config")
        hf = QFormLayout(self._http_box)
        self._url = QLineEdit(cfg.get("url", ""))
        self._url.setPlaceholderText("http://localhost:3000/sse")
        hf.addRow("URL:", self._url)
        lo.addWidget(self._http_box)

        # Detect initial type
        if "url" in cfg:
            self._http_rb.setChecked(True)
        else:
            self._stdio_rb.setChecked(True)

        self._stdio_rb.toggled.connect(self._update_visibility)
        self._update_visibility()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
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

        # Dark background fill
        p.fillRect(self.rect(), QColor("#0f0d1a"))

        if sum(self._counts.values()) == 0:
            p.setPen(QColor("#5a4f70"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No mood data yet today.\nInteract with Pip to see stats!")
            return

        w, h   = self.width(), self.height()
        pad    = 16
        label_h = 18
        bar_area_h = h - pad * 2 - label_h
        n      = len(self._ORDER)
        slot_w = (w - pad * 2) // n
        bar_w  = max(8, slot_w - 10)
        max_c  = max(self._counts.values()) or 1

        for i, name in enumerate(self._ORDER):
            count  = self._counts[name]
            bar_h  = int(count / max_c * bar_area_h)
            x      = pad + i * slot_w + (slot_w - bar_w) // 2
            y      = pad + bar_area_h - bar_h
            color  = self._COLORS[name]

            # Bar background (empty track)
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


# ═══════════════════════════════════════ Helpers ═════════════════════════════

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
