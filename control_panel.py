import json
import logging
import os
import subprocess
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
        self.setMinimumWidth(460)
        self.setWindowFlags(Qt.WindowType.Window)

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

        tabs = QTabWidget()
        tabs.setIconSize(QSize(18, 18))
        tabs.addTab(self._personality_tab(), _tab_icon_personality(), "Personality")
        tabs.addTab(self._profile_tab(),     _tab_icon_profile(),     "Profile")
        tabs.addTab(self._mood_tab(),        _tab_icon_mood(),        "Mood")
        tabs.addTab(self._journal_tab(),     _tab_icon_journal(),     "Journal")
        tabs.addTab(self._notes_tab(),       _tab_icon_notes(),       "Notes")
        tabs.addTab(self._tools_tab(),       _tab_icon_tools(),       "Tools")
        tabs.addTab(self._settings_tab(),    _tab_icon_settings(),    "Settings")
        tabs.addTab(self._wellness_tab(),    _tab_icon_wellness(),    "Wellness")
        tabs.addTab(self._focus_tab(),       _tab_icon_focus(),       "Focus")
        tabs.addTab(self._about_tab(),       _tab_icon_about(),       "About")
        tabs.addTab(self._build_log_tab(),   _tab_icon_log(),         "Log")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(tabs)

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
        self._work_combo = QComboBox()
        self._work_combo.addItems(["(not set)", "Developer / Engineer", "Designer", "Student", "Writer / Creator", "Other"])
        form.addRow("Work type:", self._work_combo)

        self._comm_combo = QComboBox()
        self._comm_combo.addItems(["casual", "professional", "playful"])
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
        QMessageBox.information(self, "Saved", "Profile saved!")

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
        # Profile tab
        profile = self._p.get_profile()
        work_rev = {"": 0, "developer": 1, "designer": 2, "student": 3, "writer": 4, "other": 5}
        self._work_combo.setCurrentIndex(work_rev.get(profile.get("work_type", ""), 0))
        comm_options = ["casual", "professional", "playful"]
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
        self._s.setValue("model",      self._model_combo.currentText())
        self._s.setValue("idle_min",   self._idle_min.value())
        self._s.setValue("idle_max",   self._idle_max.value())
        self._s.setValue("deep_watch", self._deep_watch_cb.isChecked())
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
