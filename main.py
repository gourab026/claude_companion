"""
Pip — pixel-art desktop companion for Linux.

Left-click  : open chat
Right-click : menu  →  Control Panel / Rename / Quit
Drag        : move Pip around the screen
"""

import ctypes
import ctypes.util
import logging
import os
import random
import re
import signal
import subprocess
import sys
import sys as _sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, date
from urllib.parse import quote_plus

from PyQt6.QtWidgets import QApplication, QWidget, QInputDialog, QMenu, QLineEdit, QMessageBox, QSystemTrayIcon
from PyQt6.QtCore import Qt, QPoint, QTimer, QSettings, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPainter, QIcon, QPixmap, QColor, QPen, QBrush


VERSION = "1.0.0"

log       = logging.getLogger("pip.main")
_log_idle = logging.getLogger("pip.idle")
_log_bub  = logging.getLogger("pip.bubble")


# ── Icon factory (SVG-less QPainter icons) ────────────────────────────────────

def _make_icon(draw_fn, color: str = "#a892ff", size: int = 16) -> QIcon:
    """Create a QIcon by drawing with QPainter onto a transparent pixmap."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    pen = QPen(c, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    draw_fn(p, size)
    p.end()
    return QIcon(px)


def _icon_chat(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        # bubble body
        p.drawRoundedRect(int(1.5*m), int(1.5*m), int(13*m), int(10*m), 2*m, 2*m)
        # tail
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        tail = QPolygonF([QPointF(3*m, 11.5*m), QPointF(1*m, 14.5*m), QPointF(6*m, 11.5*m)])
        p.drawPolyline(tail)
    return _make_icon(draw, color, size)


def _icon_sliders(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(int(1*m), int(4*m),  int(10*m), int(4*m))
        p.drawLine(int(1*m), int(8*m),  int(13*m), int(8*m))
        p.drawLine(int(1*m), int(12*m), int(10*m), int(12*m))
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(int(11*m), int(2.5*m), int(3*m), int(3*m))
        p.drawEllipse(int(4*m),  int(6.5*m), int(3*m), int(3*m))
        p.drawEllipse(int(11*m), int(10.5*m), int(3*m), int(3*m))
    return _make_icon(draw, color, size)


def _icon_timer(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawEllipse(int(1.5*m), int(1.5*m), int(13*m), int(13*m))
        from PyQt6.QtCore import QPointF
        cx, cy = 8*m, 8*m
        p.drawLine(int(cx), int(cy), int(cx), int(cy - 4*m))
        p.drawLine(int(cx), int(cy), int(cx + 2.5*m), int(cy + 1.5*m))
    return _make_icon(draw, color, size)


def _icon_gamepad(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawRoundedRect(int(1*m), int(4*m), int(14*m), int(8*m), 2*m, 2*m)
        p.drawLine(int(4*m), int(8*m), int(7*m), int(8*m))
        p.drawLine(int(5.5*m), int(6.5*m), int(5.5*m), int(9.5*m))
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(int(10.5*m), int(7*m), int(1.5*m), int(1.5*m))
        p.drawEllipse(int(12.5*m), int(5.5*m), int(1.5*m), int(1.5*m))
    return _make_icon(draw, color, size)


def _icon_scissors(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(2*m), int(2*m), int(4*m), int(4*m))
        p.drawEllipse(int(2*m), int(10*m), int(4*m), int(4*m))
        p.drawLine(int(14*m), int(2.5*m), int(5.5*m), int(10.5*m))
        p.drawLine(int(9.5*m), int(9.5*m), int(14*m), int(13.5*m))
        p.drawLine(int(5.5*m), int(5.5*m), int(8*m), int(8*m))
    return _make_icon(draw, color, size)


def _icon_clipboard(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawRoundedRect(int(3*m), int(2.5*m), int(10*m), int(12*m), 1.5*m, 1.5*m)
        p.drawRoundedRect(int(5.5*m), int(1*m), int(5*m), int(3*m), 1*m, 1*m)
    return _make_icon(draw, color, size)


def _icon_trash(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(int(1.5*m), int(4*m), int(14.5*m), int(4*m))
        p.drawRoundedRect(int(3.5*m), int(4*m), int(9*m), int(10*m), 1*m, 1*m)
        p.drawLine(int(6.5*m), int(7*m), int(6.5*m), int(11*m))
        p.drawLine(int(9.5*m), int(7*m), int(9.5*m), int(11*m))
        p.drawRoundedRect(int(5.5*m), int(1.5*m), int(5*m), int(2.5*m), 1*m, 1*m)
    return _make_icon(draw, color, size)


def _icon_users(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(4*m), int(2*m), int(5*m), int(5*m))
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        p.drawLine(int(1*m), int(14*m), int(12*m), int(14*m))
        p.drawLine(int(1*m), int(14*m), int(1*m), int(12*m))
        p.drawArc(int(1*m), int(8*m), int(11*m), int(6*m), 0, 180*16)
        # second person hint
        p.drawEllipse(int(10*m), int(3*m), int(3.5*m), int(3.5*m))
        p.drawLine(int(12*m), int(14*m), int(15*m), int(14*m))
    return _make_icon(draw, color, size)


def _icon_target(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(1*m), int(1*m), int(14*m), int(14*m))
        p.drawEllipse(int(4*m), int(4*m), int(8*m), int(8*m))
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(int(6.5*m), int(6.5*m), int(3*m), int(3*m))
    return _make_icon(draw, color, size)


def _icon_wind(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(int(1*m), int(5*m), int(11*m), int(5*m))
        p.drawArc(int(8.5*m), int(2*m), int(5.5*m), int(5.5*m), 90*16, 270*16)
        p.drawLine(int(1*m), int(9*m), int(13*m), int(9*m))
        p.drawArc(int(9.5*m), int(6.5*m), int(5*m), int(5*m), 90*16, -270*16)
        p.drawLine(int(1*m), int(13*m), int(11*m), int(13*m))
    return _make_icon(draw, color, size)


def _icon_bar_chart(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 2 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(int(4*m),  int(13*m), int(4*m),  int(8*m))
        p.drawLine(int(8*m),  int(13*m), int(8*m),  int(2*m))
        p.drawLine(int(12*m), int(13*m), int(12*m), int(5*m))
    return _make_icon(draw, color, size)


def _icon_edit(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        # pencil tip going to top-right
        p.drawLine(int(11*m), int(2.5*m), int(13.5*m), int(5*m))
        p.drawLine(int(2*m),  int(12*m),  int(11*m),   int(2.5*m))
        p.drawLine(int(13.5*m), int(5*m), int(4.5*m), int(14*m))
        p.drawLine(int(2*m),  int(12*m),  int(1.5*m),  int(14.5*m))
        p.drawLine(int(1.5*m), int(14.5*m), int(4.5*m), int(14*m))
    return _make_icon(draw, color, size)


def _icon_exit(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        # door
        p.drawLine(int(6*m), int(2*m), int(2*m), int(2*m))
        p.drawLine(int(2*m), int(2*m), int(2*m), int(14*m))
        p.drawLine(int(2*m), int(14*m), int(6*m), int(14*m))
        # arrow
        p.drawLine(int(8*m), int(8*m), int(14.5*m), int(8*m))
        p.drawLine(int(11.5*m), int(5*m), int(14.5*m), int(8*m))
        p.drawLine(int(11.5*m), int(11*m), int(14.5*m), int(8*m))
    return _make_icon(draw, color, size)


def _icon_bookmark(color="#a892ff", size=16):
    def draw(p, s):
        m = s / 16
        pen = QPen(QColor(color), 1.5 * m, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        pts = QPolygonF([
            QPointF(3*m, 1.5*m), QPointF(13*m, 1.5*m),
            QPointF(13*m, 14.5*m), QPointF(8*m, 10.5*m),
            QPointF(3*m, 14.5*m),
        ])
        p.drawPolygon(pts)
    return _make_icon(draw, color, size)


def _except_hook(exc_type, exc_value, exc_tb):
    logging.getLogger("pip.uncaught").critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
    )
    _sys.__excepthook__(exc_type, exc_value, exc_tb)


_sys.excepthook = _except_hook


def _suppress_gtk_warnings():
    try:
        glib = ctypes.CDLL("libglib-2.0.so.0")
        G_LOG_LEVEL_WARNING = 1 << 4
        handler_t = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int,
                                     ctypes.c_char_p, ctypes.c_void_p)
        _suppress_gtk_warnings._cb = handler_t(lambda *_: None)
        glib.g_log_set_handler(b"Gtk", G_LOG_LEVEL_WARNING, _suppress_gtk_warnings._cb, None)
    except Exception:
        pass


_suppress_gtk_warnings()  # must run before QApplication()

from character import CharacterRenderer, State
from personality import Personality, DREAM_QUIPS
from claude_client import ClaudeWorker
from bubble import BubbleWindow, SPEECH, THOUGHT, SHOUT
from chat_input import ChatInputWidget
from control_panel import ControlPanel
from asset_manager import AssetManager
try:
    from gcal_client import GCalClient
    _GCAL_AVAILABLE = True
except ImportError:
    GCalClient = None
    _GCAL_AVAILABLE = False

# Bubble priority levels
BUBBLE_LOW    = 0   # idle chatter — silently dropped if a bubble is already visible
BUBBLE_NORMAL = 1   # wellness / events — queued to show after current bubble
BUBBLE_HIGH   = 2   # AI replies / user actions — queued at front, never dropped

if getattr(sys, "frozen", False):
    _CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "pip-companion")
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    MCP_CONFIG = os.path.join(_CONFIG_DIR, "mcp_config.json")
else:
    MCP_CONFIG = os.path.join(os.path.dirname(__file__), "mcp_config.json")

# ── Mood reaction tables ───────────────────────────────────────────────────────
MOOD_TRIGGERS: dict[State, list[str]] = {
    State.HAPPY:    ["great", "awesome", "amazing", "love", "thank", "yay",
                     "perfect", "excellent", "wonderful", "happy", "nice",
                     "good job", "well done", "haha", "lol", "hehe", "cool"],
    State.DANCING:  ["dance", "party", "celebrate", "woohoo", "woo", "music",
                     "song", "sing", "jam"],
    State.SLEEPING: ["boring", "tired", "sleepy", "zzz", "whatever", "meh"],
    State.THINKING: ["why", "how", "explain", "what if", "could you",
                     "tell me", "what is", "define", "?"],
    State.EXCITED:  ["omg", "oh my god", "incredible", "unbelievable", "holy",
                     "insane", "no way", "wow", "whoa", "!!!"],
}

RESPONSE_MOOD_TRIGGERS: dict[State, list[str]] = {
    State.HAPPY:    ["!", "haha", "great", "awesome", "yay", "love",
                     "exciting", "wonderful", "amazing"],
    State.DANCING:  ["♪", "dance", "music", "party"],
    State.EXCITED:  ["!!", "incredible", "amazing!", "wow!", "omg"],
}

MAX_HISTORY_TURNS = 3   # = 6 messages

# git commit SHA pattern: 7+ hex chars at start of a word
import re as _re
_GIT_COMMIT_RE = _re.compile(r'\b[0-9a-f]{7,40}\b')


def _detect_mood(text: str) -> State | None:
    lower = text.lower()
    for state, words in MOOD_TRIGGERS.items():
        if any(w in lower for w in words):
            return state
    return None


def _detect_response_mood(text: str) -> State | None:
    lower = text.lower()
    for state, words in RESPONSE_MOOD_TRIGGERS.items():
        if any(w in lower for w in words):
            return state
    return None


class CompanionWindow(QWidget):
    _cal_result_ready = pyqtSignal(str)   # emitted from calendar background threads

    def __init__(self, is_second: bool = False):
        super().__init__()

        self._is_second = is_second

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)

        self._personality = Personality()
        self._settings    = QSettings("companion", "pip")
        self._char        = CharacterRenderer()
        self._gcal        = GCalClient() if _GCAL_AVAILABLE else None
        self._worker: ClaudeWorker | None          = None
        self._haiku_worker: ClaudeWorker | None    = None
        self._trivia_worker: ClaudeWorker | None   = None
        self._twentyq_worker: ClaudeWorker | None  = None
        self._interest_worker: ClaudeWorker | None = None
        self._joke_worker: ClaudeWorker | None     = None
        self._skill_tip_worker: ClaudeWorker | None = None
        self._watch_worker: ClaudeWorker | None    = None
        self._what_doing_worker: ClaudeWorker | None = None
        self._file_drop_worker: ClaudeWorker | None  = None
        self._drag_pos: QPoint | None    = None
        self._press_global: QPoint       = QPoint()
        self._is_dragging: bool          = False
        self._panel: ControlPanel | None = None
        self._second_pip: "CompanionWindow | None" = None

        self._history: list[tuple[str, str]] = []
        self._pending_user_msg: str = ""
        self._last_response: str = ""          # improvement 1: double-tap to reply

        # improvement 5: idle timeout escalation
        self._idle_escalated: bool = False

        # improvement 2: typing speed tracking
        self._keypress_count_wpm: int = 0
        self._wpm_window_start: float = time.time()
        self._wpm_alerted: bool = False

        # Trivia / 20Q game state
        self._trivia_score: list[int] = [0, 0]   # [wins, losses]
        self._twentyq_secret: str = ""
        self._twentyq_count: int  = 0

        self.setFixedSize(self._char.canvas_w, self._char.canvas_h)
        self._bubble = BubbleWindow()
        self._bubble_queue: list[tuple[int, str, str, bool]] = []   # (priority, text, style, interactive)
        self._bubble.bubble_closed.connect(self._drain_bubble_queue)
        self._bubble.bubble_closed.connect(self._on_bubble_dismissed)
        # improvement 1: double-click on bubble opens chat pre-filled
        self._bubble.double_clicked.connect(self._bubble_double_clicked)
        # improvement 8: wire up reaction callback
        self._bubble.on_reaction = self._on_bubble_reaction
        # calendar thread → main thread bridge
        self._cal_result_ready.connect(self._show_calendar_result)

        # improvement 12: typing indicator bubble
        self._typing_indicator: BubbleWindow | None = None
        self._typing_dot_count: int = 1
        self._typing_dot_timer = QTimer(self)
        self._typing_dot_timer.timeout.connect(self._tick_typing_indicator)

        self._chat_input = ChatInputWidget()
        self._chat_input.submitted.connect(self._on_chat_submitted)

        # ── Position ──────────────────────────────────────────────────────────
        screen = QApplication.primaryScreen().geometry()
        if is_second:
            # Place second Pip offset from settings position
            x = self._settings.value("x", screen.width()  - self._char.canvas_w - 40, type=int)
            y = self._settings.value("y", screen.height() - self._char.canvas_h - 60, type=int)
            self.move(x - self._char.canvas_w - 10, y)
        else:
            self.move(
                self._settings.value("x", screen.width()  - self._char.canvas_w - 40, type=int),
                self._settings.value("y", screen.height() - self._char.canvas_h - 60, type=int),
            )

        # ── Timers ────────────────────────────────────────────────────────────
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(130)

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._random_event)
        self._schedule_idle()

        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._go_idle)

        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._click_timer.timeout.connect(self._open_chat)

        # Dream muttering — fires during SLEEPING state
        self._dream_timer = QTimer(self)
        self._dream_timer.setSingleShot(True)
        self._dream_timer.timeout.connect(self._mutter_dream)

        # ── Clipboard watcher ────────────────────────────────────────────────
        self._clipboard_pending: str = ""
        self._last_clipboard: str    = ""
        QApplication.instance().clipboard().dataChanged.connect(self._on_clipboard_change)

        # ── Keyboard + screen-time tracking ──────────────────────────────────
        self._last_keypress: float   = time.time()
        self._keypress_lock          = threading.Lock()
        self._session_active_start   = time.time()   # for 2-hour screen-time nudge
        self._screen_nudge_done      = False
        if datetime.now().hour >= 23 or datetime.now().hour < 4:
            p = self._personality.get_profile()
            p["late_nights"] = p.get("late_nights", 0) + 1
            self._personality.save()
        self._typing_check           = QTimer(self)
        self._typing_check.timeout.connect(self._check_typing_idle)
        self._typing_check.start(60_000)
        self._start_kb_listener()

        self._anim_counter: int = 0

        # ── Triple-click to minimize ──────────────────────────────────────────
        self._click_times: list[float] = []
        self._minimized: bool = False

        # WindowStaysOnTopHint handles z-order at the WM level.
        # No periodic raise_() — that steals focus from the user's active window.

        # ── Pomodoro ─────────────────────────────────────────────────────────
        # (session start logged after all timers are initialised — see below)
        self._pomo_running: bool = False
        self._pomo_timer = QTimer(self)
        self._pomo_timer.setSingleShot(True)
        self._pomo_timer.timeout.connect(self._on_pomodoro_done)

        # ── Hydration reminder ────────────────────────────────────────────────
        self._hydration_timer = QTimer(self)
        self._hydration_timer.timeout.connect(self._hydration_reminder)
        self._update_hydration_timer()

        # Eye-strain 20-20-20
        self._eyestrain_timer = QTimer(self)
        self._eyestrain_timer.timeout.connect(self._eyestrain_reminder)
        if self._personality._data.get("eyestrain_enabled", True):
            self._eyestrain_timer.start(20 * 60_000)

        # Focus mode state
        self._focus_mode: bool = self._personality._data.get("focus_mode", False)

        # ── Active window + music + stats watchers ───────────────────────────
        self._window_timer = QTimer(self)
        self._window_timer.timeout.connect(self._check_active_window)
        self._window_timer.start(30_000)

        # ── Deep screen watcher ───────────────────────────────────────────────
        self._last_deep_watch: float      = 0.0        # epoch of last deep tick
        self._recent_windows: deque       = deque(maxlen=6)  # (timestamp, title) pairs
        self._last_web_search_times: dict = {}         # context_key → epoch
        self._last_same_window_start: float = time.time()
        self._last_same_window_name: str    = ""
        self._last_same_window_alerted: bool = False
        self._deep_watch_timer = QTimer(self)
        self._deep_watch_timer.timeout.connect(self._deep_watch_tick)
        if self._settings.value("deep_watch", False, type=bool):
            self._deep_watch_timer.start(3 * 60_000)    # every 3 minutes

        self._music_timer = QTimer(self)
        self._music_timer.timeout.connect(self._check_music)
        self._music_timer.start(45_000)
        self._last_music_title: str       = ""
        self._song_fact_worker: ClaudeWorker | None = None
        self._last_song_fact_time: float  = 0.0   # epoch; enforces 10-min gap

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._check_stats)
        self._stats_timer.start(5 * 60_000)   # every 5 min

        # ── Wander mode (QSettings key: wander_mode, bool, default False) ────
        self._wander_timer = QTimer(self)
        self._wander_timer.setSingleShot(True)
        self._wander_timer.timeout.connect(self._wander_tick)
        self._wander_anim: QPropertyAnimation | None = None
        if self._settings.value("wander_mode", False, type=bool):
            self._wander_timer.start(random.randint(300, 480) * 1000)

        # ── STRETCHING trigger tracking ────────────────────────────────────────
        # Fires when CharacterRenderer reports 8+ consecutive idle frames.
        # At 130ms per tick but next_frame fires every 4th tick ≈ 520ms each.
        # 8 frames ≈ 4.2 seconds — checked each animation tick.
        self._stretch_timer = QTimer(self)
        self._stretch_timer.setSingleShot(True)
        self._stretch_timer.timeout.connect(self._go_idle)

        # ── Weather (once per session) ────────────────────────────────────────
        self._weather_fetched = False
        QTimer.singleShot(8_000, self._fetch_weather)

        # ── Startup greeting ─────────────────────────────────────────────────
        if not is_second:
            QTimer.singleShot(1200, self._greet)
            QTimer.singleShot(3_000, self._check_daily_events)
        else:
            QTimer.singleShot(1200, self._second_pip_greet)

        # ── Asset manager ────────────────────────────────────────────────────
        self._asset_mgr = AssetManager()

        # ── File drop support ─────────────────────────────────────────────────
        self.setAcceptDrops(True)

        # ── Window app category (for richer reactions) ───────────────────────
        self._window_app_category: str = ""   # tracks current app type

        # ── Screenshot reaction (clipboard image check) ───────────────────────
        self._last_clip_had_image: bool = False

        # ── System tray ───────────────────────────────────────────────────────
        if not is_second and self._settings.value("show_tray", True, type=bool):
            self._setup_tray()
        else:
            self._tray: QSystemTrayIcon | None = None

        model = self._settings.value("model", "claude-sonnet-4-6")
        log.info("Pip session started — version %s, model %s", VERSION, model)

    # ── Always-on-top + minimize ──────────────────────────────────────────────

    def _toggle_minimize(self):
        self._minimized = not self._minimized
        if self._minimized:
            self._bubble.hide()
            self._chat_input.hide()
            self._anim_timer.stop()
            self._idle_timer.stop()
            self._return_timer.stop()
            self._dream_timer.stop()
            self.setFixedSize(20, 20)
        else:
            self._anim_timer.start(130)
            self._schedule_idle()
            self.setFixedSize(self._char.canvas_w, self._char.canvas_h)
            self.raise_()
        self.update()

    # ── Graceful shutdown ─────────────────────────────────────────────────────

    def closeEvent(self, event):
        try:
            self._personality.write_journal_entry()
        except Exception:
            log.error("Error writing journal on close", exc_info=True)
        try:
            self._personality.log_session(self._session_active_start, time.time())
        except Exception:
            log.error("Error logging session on close", exc_info=True)
        try:
            self._personality.save()
        except Exception:
            log.error("Error saving personality on close", exc_info=True)
        for timer in (
            self._anim_timer, self._idle_timer, self._return_timer,
            self._click_timer, self._dream_timer, self._typing_check,
            self._pomo_timer, self._window_timer, self._music_timer,
            self._stats_timer, self._hydration_timer, self._eyestrain_timer,
            self._deep_watch_timer, self._wander_timer, self._stretch_timer,
            self._typing_dot_timer,
        ):
            timer.stop()
        if hasattr(self, "_kb_listener") and self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
        # Stop all running QThread workers before the window is destroyed.
        # Failing to do this causes "QThread: Destroyed while thread is still
        # running" → SIGABRT when the Python GC collects the objects.
        for attr in (
            "_worker", "_haiku_worker", "_trivia_worker", "_twentyq_worker",
            "_song_fact_worker", "_interest_worker", "_joke_worker",
            "_skill_tip_worker", "_watch_worker", "_what_doing_worker",
            "_file_drop_worker",
        ):
            w = getattr(self, attr, None)
            if w is not None and w.isRunning():
                w.quit()
                w.wait(2000)
        self._chat_input.hide()
        log.info("Session ended cleanly")
        event.accept()

    # ── Animation ─────────────────────────────────────────────────────────────

    def _tick(self):
        self._anim_counter = (self._anim_counter + 1) % 4
        if self._char.state != State.IDLE or self._anim_counter == 0:
            self._char.next_frame()
        self._char.tick_color()

        # ── STRETCHING auto-trigger after 8+ consecutive IDLE frames ──────────
        # next_frame for IDLE fires every 4th tick (every ~520ms).
        # 8 idle next_frame calls ≈ 4.2s of pure IDLE.
        if (self._char.state == State.IDLE
                and self._char.idle_frames_total >= 8
                and not self._stretch_timer.isActive()
                and not self._bubble.isVisible()):
            self._trigger_stretching()

        # ── STRETCHING auto-return after 2 seconds (≈ 15 ticks × 130ms) ─────
        if self._char.state == State.STRETCHING and self._char._stretch_frames >= 15:
            self._go_idle()

        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self._minimized:
            from PyQt6.QtGui import QColor, QBrush
            p.setRenderHint(p.RenderHint.Antialiasing)
            p.setBrush(QBrush(QColor(120, 80, 200, 200)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(2, 2, 16, 16)
        else:
            # Load and pass any equipped overlay (hat, etc.)
            overlay = None
            try:
                overlay = self._asset_mgr.get_overlay("hat")
            except Exception:
                pass
            self._char.draw(p, overlay=overlay)

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            now = time.time()
            self._click_times = [t for t in self._click_times if now - t < 0.6]
            self._click_times.append(now)
            if len(self._click_times) >= 3:
                self._click_times.clear()
                self._click_timer.stop()
                self._toggle_minimize()
                return
            if self._minimized:
                return
            self._drag_pos     = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_global = event.globalPosition().toPoint()
            self._is_dragging  = False
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos is not None:
                if not self._is_dragging:
                    self._click_timer.start()
                else:
                    self._char.set_state(State.HAPPY)
                    self._show_bubble(random.choice(["wheee! ✨", "wooosh~", "wheeee!", "weee~"]), priority=BUBBLE_HIGH)
                    self._return_timer.start(3000)
            self._drag_pos    = None
            self._is_dragging = False
            if not self._is_second:
                self._settings.setValue("x", self.x())
                self._settings.setValue("y", self.y())

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                delta = event.globalPosition().toPoint() - self._press_global
                if delta.manhattanLength() >= 6:
                    self._is_dragging = True
                    self._char.set_state(State.DRAGGING)
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._bubble.hide()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Count this as a click for triple-click detection.
            # Qt fires: press(1) press(2)→doubleclick press(3), so we track here too.
            now = time.time()
            self._click_times = [t for t in self._click_times if now - t < 0.6]
            self._click_times.append(now)
            if len(self._click_times) >= 3:
                self._click_times.clear()
                self._click_timer.stop()
                self._toggle_minimize()
                return
            self._click_timer.stop()
            self._pet_pip()

    # ── Chat ──────────────────────────────────────────────────────────────────

    def _open_chat(self):
        prefill = ""
        if self._clipboard_pending:
            prefill = f"Explain this: {self._clipboard_pending[:400]}"
            self._clipboard_pending = ""
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        busy = bool(self._worker and self._worker.isRunning())
        self._chat_input.activate(anchor, prefill=prefill, busy=busy)

    # ── Google Calendar ───────────────────────────────────────────────────────

    # Detects intent to READ calendar
    _CAL_READ_PATTERNS = re.compile(
        r"(?:what(?:'s| is)(?: on)? my (?:calendar|schedule|agenda|events?)|"
        r"show(?: my)? (?:calendar|schedule|agenda|events?)|"
        r"(?:do i have|what do i have)(?: on)?(?:\s+(?:today|tomorrow|this week))?|"
        r"(?:my|the) (?:next|upcoming) (?:meeting|event|appointment)|"
        r"(?:what'?s? )?(?:today|tomorrow|this week)(?:'s)? (?:events?|schedule|agenda)|"
        r"am i(?: free| busy)(?: today| tomorrow)?)",
        re.IGNORECASE,
    )

    # Detects intent to ADD an event/reminder (broad, natural language)
    _CAL_ADD_PATTERNS = re.compile(
        r"^(?:"
        r"(?:add|put)(?:\s+(?:a|an))?\s+(?:(?:to\s+)?(?:my\s+)?(?:calendar|schedule)|"
        r"event|meeting|appointment|reminder|task)|"
        r"remind\s+me\s+(?:to\s+|about\s+|of\s+)?|"
        r"set\s+(?:a\s+)?(?:reminder|alarm)\s*(?:for\s+|to\s+)?|"
        r"schedule(?:\s+(?:a|an))?\s+|"
        r"create\s+(?:a\s+)?(?:new\s+)?(?:event|meeting|appointment|reminder)(?:\s+for)?\s+"
        r")",
        re.IGNORECASE,
    )

    # Date/time markers used to split title from datetime in natural language
    _CAL_DATETIME_SPLIT = re.compile(
        r"\s+(?:at|on|for|this|next|tomorrow|today|in\s+\d)"
        r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
        r"|\b\d{4}-\d{2}-\d{2}\b",
        re.IGNORECASE,
    )

    def _try_calendar(self, text: str) -> bool:
        """Return True if the text is a calendar command and handle it."""
        if self._gcal is None:
            return False

        stripped = text.strip()

        # ── Add event / reminder ──────────────────────────────────────────────
        if self._CAL_ADD_PATTERNS.match(stripped):
            if not self._gcal.is_connected():
                self._show_bubble(
                    "Google Calendar isn't connected yet.\n"
                    "Go to Settings → Google Calendar to connect.",
                    style=THOUGHT, priority=BUBBLE_HIGH, interactive=True,
                )
                return True
            self._do_calendar_add(stripped)
            return True

        # ── Read events ───────────────────────────────────────────────────────
        if self._CAL_READ_PATTERNS.search(stripped):
            if not self._gcal.is_connected():
                self._show_bubble(
                    "Google Calendar isn't connected yet.\n"
                    "Go to Settings → Google Calendar to connect.",
                    style=THOUGHT, priority=BUBBLE_HIGH, interactive=True,
                )
                return True
            self._do_calendar_read(stripped)
            return True

        return False

    def _do_calendar_read(self, user_text: str):
        """Fetch and display upcoming events in a background thread."""
        self._char.set_state(State.THINKING)
        lower = user_text.lower()
        days = 7 if "week" in lower else (2 if "tomorrow" in lower else 1)
        label = "Today" if days == 1 else ("Tomorrow" if days == 2 else "This week")

        def _fetch():
            events = self._gcal.get_events(days=days)
            from gcal_client import GCalClient as _GCC
            self._cal_result_ready.emit(_GCC.format_events_short(events, label=label))

        threading.Thread(target=_fetch, daemon=True).start()

    # ── Natural language date/time parser ─────────────────────────────────────

    @staticmethod
    def _parse_cal_datetime(text: str):
        """
        Extract (start_datetime, end_datetime) from a natural language string.
        Understands: today, tomorrow, weekday names, "at Xpm/X:Yam", YYYY-MM-DD.
        Returns (start_dt, end_dt) with local timezone, or raises ValueError.
        """
        from datetime import timezone as _tz, timedelta as _td, date as _date
        local_tz = datetime.now(_tz.utc).astimezone().tzinfo
        now      = datetime.now(local_tz)
        lower    = text.lower()

        # ── Determine the calendar date ───────────────────────────────────────
        cal_date = now.date()
        if re.search(r'\btomorrow\b', lower):
            cal_date = (now + _td(days=1)).date()
        elif re.search(r'\btoday\b', lower):
            cal_date = now.date()
        else:
            weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
            for i, name in enumerate(weekdays):
                if re.search(r'\b' + name + r'\b', lower):
                    ahead = (i - now.weekday()) % 7 or 7
                    cal_date = (now + _td(days=ahead)).date()
                    break
            else:
                m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
                if m:
                    cal_date = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        # ── Determine the time ────────────────────────────────────────────────
        hour, minute = 9, 0   # sensible default
        # Match "3pm", "3:30pm", "15:00", "3 pm", "at 3"
        time_m = re.search(
            r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b'   # 3pm / 3:30pm
            r'|\b(\d{1,2}):(\d{2})\b'                  # 15:00 / 3:30
            r'|\bat\s+(\d{1,2})\b',                     # at 3
            lower,
        )
        if time_m:
            if time_m.group(1) is not None:             # Xpm form
                hour   = int(time_m.group(1))
                minute = int(time_m.group(2) or 0)
                mer    = time_m.group(3) or ""
                if mer == "pm" and hour != 12:
                    hour += 12
                elif mer == "am" and hour == 12:
                    hour = 0
            elif time_m.group(4) is not None:           # HH:MM form
                hour   = int(time_m.group(4))
                minute = int(time_m.group(5))
            elif time_m.group(6) is not None:           # "at N" form
                hour = int(time_m.group(6))
                if hour < 7:                            # "at 3" → assume pm
                    hour += 12

        start_dt = datetime(cal_date.year, cal_date.month, cal_date.day,
                            hour, minute, tzinfo=local_tz)
        end_dt   = start_dt + _td(hours=1)
        return start_dt, end_dt

    @staticmethod
    def _extract_cal_title(text: str) -> str:
        """Strip command prefix and datetime tail, return the event title."""
        t = text.strip()

        # Step 1: Strip the verb/command word(s) — always
        t = re.sub(r'^remind\s+me\s+(?:to\s+|about\s+|of\s+)?', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^set\s+(?:a\s+)?(?:reminder|alarm)\s*(?:for\s+|to\s+)?', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^create\s+(?:a\s+)?(?:new\s+)?', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^schedule\s+', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^(?:add|put)\s+', '', t, flags=re.IGNORECASE)
        t = t.strip()

        # Step 2: Strip optional article
        t = re.sub(r'^(?:a|an)\s+', '', t, flags=re.IGNORECASE).strip()

        # Step 3: Strip "to/into/on (my) calendar" — both as prefix ("add to calendar: X")
        #         and suffix ("put X on my calendar")
        t = re.sub(r'^(?:to|into|on)\s+(?:my\s+)?(?:calendar|schedule)\s*:?\s*', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'\s+(?:to|into|on)\s+(?:my\s+)?(?:calendar|schedule)$', '', t, flags=re.IGNORECASE).strip()

        # Step 4: Strip standalone type prefix words (reminder, event, etc.) only when
        # followed by "for/to/:" or end-of-string — not when part of a noun phrase ("meeting with...")
        t = re.sub(r'^(?:reminder|alarm)\s*(?:for\s+|to\s+|:\s*)?', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'^(?:event|task)\s*(?::\s*|(?=\s*$)|\s+for\s+)', '', t, flags=re.IGNORECASE).strip()
        # "meeting/appointment" stay if followed by "with/about" (they're part of the title)
        t = re.sub(r'^(?:meeting|appointment)\s*(?::\s*|(?=\s*$)|\s+for\s+)', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'^for\s+', '', t, flags=re.IGNORECASE).strip()

        # Step 5: Strip trailing datetime: "tomorrow at 3pm", "on Monday", "by Friday", etc.
        t = re.sub(
            r'\s+(?:at|on|by|this|next)\s+.*$'
            r'|\s+tomorrow\b.*$'
            r'|\s+today\b.*$'
            r'|\s+\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.*$'
            r'|\s+\d{4}-\d{2}-\d{2}.*$',
            '', t, flags=re.IGNORECASE,
        ).strip()

        return t or text.strip()

    def _do_calendar_add(self, user_text: str):
        """Parse a natural-language add request and create the event."""
        title = self._extract_cal_title(user_text)

        try:
            start_dt, end_dt = self._parse_cal_datetime(user_text)
        except Exception:
            self._show_bubble(
                f"Got it — \"{title}\"\nWhen is it? Tell me the date and time\n"
                f"e.g. \"tomorrow at 3pm\" or \"Monday at 10am\"",
                style=THOUGHT, priority=BUBBLE_HIGH, interactive=True,
            )
            return

        start_iso  = start_dt.isoformat()
        end_iso    = end_dt.isoformat()
        time_label = start_dt.strftime("%-d %b at %-I:%M %p")

        self._char.set_state(State.THINKING)

        def _create():
            event = self._gcal.create_event(title, start_iso, end_iso)
            msg = (f"Added to your calendar!\n\"{title}\"\n{time_label}"
                   if event else "Couldn't create the event. Check the log for details.")
            self._cal_result_ready.emit(msg)

        threading.Thread(target=_create, daemon=True).start()

    @pyqtSlot(str)
    def _show_calendar_result(self, text: str):
        self._char.set_state(State.HAPPY)
        self._show_bubble(text, style=THOUGHT, priority=BUBBLE_HIGH, interactive=True)

    def _on_calendar_status_changed(self, connected: bool):
        if connected:
            self._show_bubble(
                "Google Calendar connected! Try:\n"
                "\"What's on my calendar today?\"",
                style=SPEECH, priority=BUBBLE_HIGH,
            )
            self._return_timer.start(6000)
        else:
            self._show_bubble(
                "Google Calendar disconnected.",
                style=THOUGHT, priority=BUBBLE_HIGH,
            )
            self._return_timer.start(3000)

    # ── YouTube ───────────────────────────────────────────────────────────────

    _YT_PATTERNS = re.compile(
        r"^(?:play|put on|queue|open|search(?: for)?|find)\s+(?:me\s+)?"
        r"(?:some\s+)?(?:the\s+)?(?:song\s+|music\s+|track\s+)?"
        r"[\"']?(.+?)[\"']?"
        r"(?:\s+(?:on\s+)?(?:youtube|yt|music))?$",
        re.IGNORECASE,
    )

    def _try_youtube(self, text: str) -> bool:
        """Return True and open YouTube if the text looks like a play request."""
        m = self._YT_PATTERNS.match(text.strip())
        if not m:
            return False
        query = m.group(1).strip().strip("\"'")
        if not query or len(query) > 200:
            return False
        # Reject bare platform names with no actual search query
        if query.lower() in {"youtube", "yt", "music", "spotify", "songs"}:
            return False
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        webbrowser.open(url)
        self._char.set_state(State.DANCING)
        quips = [
            f"Opening YouTube for \"{query}\" 🎵",
            f"On it! Searching for \"{query}\" 🎶",
            f"Your music is loading! \"{query}\" 🎵",
            f"Let's go! Queuing up \"{query}\" 🎶",
        ]
        self._show_bubble(random.choice(quips), style=SPEECH, priority=BUBBLE_HIGH)
        self._return_timer.start(4000)
        log.info("YouTube opened for query: %s", query)
        return True

    def _on_chat_submitted(self, user_text: str):
        # ── YouTube shortcut ─────────────────────────────────────────────────
        if self._try_youtube(user_text):
            return

        # ── Google Calendar shortcut ─────────────────────────────────────────
        if self._try_calendar(user_text):
            return

        # ── Teach / bookmark shortcuts (checked before remember) ─────────────
        lower = user_text.lower()
        for prefix in ("teach:", "teach :"):
            if lower.startswith(prefix):
                content = user_text[len(prefix):].strip()
                if "=" in content:
                    word, _, meaning = content.partition("=")
                    word, meaning = word.strip(), meaning.strip()
                    if word and meaning:
                        self._personality.teach_word(word, meaning)
                        self._char.set_state(State.HAPPY)
                        self._show_bubble(f"Got it! I'll remember that \"{word}\" means \"{meaning}\" 📚", style=THOUGHT, priority=BUBBLE_HIGH)
                        self._return_timer.start(4000)
                return

        for prefix in ("bookmark:", "bookmark :"):
            if lower.startswith(prefix):
                url = user_text[len(prefix):].strip()
                if url:
                    self._personality.add_bookmark(url)
                    self._char.set_state(State.HAPPY)
                    self._show_bubble(f"Bookmarked! 🔖 {url[:40]}", style=THOUGHT, priority=BUBBLE_HIGH)
                    self._return_timer.start(3000)
                return

        # ── Sticky note shortcut ──────────────────────────────────────────────
        for prefix in ("remember:", "note:", "remember :", "note :"):
            if lower.startswith(prefix):
                note_text = user_text[len(prefix):].strip()
                if note_text:
                    self._personality.add_note(note_text)
                    self._char.set_state(State.HAPPY)
                    self._show_bubble(f"Got it! I'll remember: \"{note_text}\" 📌", style=THOUGHT, priority=BUBBLE_HIGH)
                    self._return_timer.start(5000)
                return

        self._bubble.hide()

        mood = _detect_mood(user_text)
        self._char.set_state(mood if mood else State.THINKING)

        # Improvement 3: show a "hmm..." acknowledgement bubble immediately
        QTimer.singleShot(300, self._show_thinking_ack)

        recent = self._history[-(MAX_HISTORY_TURNS * 2):]
        if recent:
            lines = []
            for role, msg in recent:
                label = "Human" if role == "user" else self._personality.name
                lines.append(f"{label}: {msg}")
            history_block = "\n\n".join(lines)
            full_prompt = f"{history_block}\n\nHuman: {user_text}"
        else:
            full_prompt = user_text

        self._pending_user_msg = user_text

        if self._worker and self._worker.isRunning():
            log.warning("Worker still running — disconnecting stale signals")
            self._worker.response_ready.disconnect()
            self._worker.error_occurred.disconnect()

        allowed  = self._settings.value("allowed_tools", "", type=str)
        use_mcp  = self._settings.value("use_mcp", False, type=bool)
        mcp_path = MCP_CONFIG if use_mcp and os.path.exists(MCP_CONFIG) else None

        log.info("Chat submitted (model=%s, chars=%d)",
                 self._settings.value("model", "claude-sonnet-4-6"), len(user_text))
        self._call_start = time.time()
        self._worker = ClaudeWorker(
            full_prompt,
            self._personality.get_system_prompt(),
            model=self._settings.value("model", "claude-sonnet-4-6"),
            allowed_tools=allowed or None,
            mcp_config=mcp_path,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.usage_ready.connect(self._on_usage)
        self._worker.start()

        # Improvement 12: start typing indicator after acknowledgement bubble
        QTimer.singleShot(1800, self._start_typing_indicator)

        self._personality.after_interaction(user_text)

    def _show_thinking_ack(self):
        """Improvement 3: show hmm... thought bubble while waiting for Claude."""
        ack_msgs = ["hmm... 🤔", "let me think...", "ooh interesting...", "hmm..."]
        self._show_bubble(random.choice(ack_msgs), style=THOUGHT, priority=BUBBLE_HIGH)

    def _start_typing_indicator(self):
        """Improvement 12: show animated 'Pip is thinking●●●' bubble."""
        # Only start if we're still waiting for a response
        if not (self._worker and self._worker.isRunning()):
            return
        if self._typing_indicator is None:
            self._typing_indicator = BubbleWindow()
        self._typing_dot_count = 1
        self._typing_dot_timer.start(500)
        self._update_typing_indicator()

    def _update_typing_indicator(self):
        """Render the current dot state into the typing indicator bubble."""
        if self._typing_indicator is None:
            return
        dots = "●" * self._typing_dot_count + "○" * (3 - self._typing_dot_count)
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        self._typing_indicator.show_text(f"Pip is thinking{dots}", anchor, 9999999, style=SPEECH)

    def _tick_typing_indicator(self):
        """Advance the dot animation (1 -> 2 -> 3 -> 1)."""
        self._typing_dot_count = (self._typing_dot_count % 3) + 1
        self._update_typing_indicator()

    def _stop_typing_indicator(self):
        """Dismiss the typing indicator and stop the animation timer."""
        self._typing_dot_timer.stop()
        if self._typing_indicator and self._typing_indicator.isVisible():
            self._typing_indicator.hide()

    def _on_response(self, response: str):
        elapsed = time.time() - getattr(self, "_call_start", time.time())
        log.info("Claude response received (elapsed=%.1fs, chars=%d)", elapsed, len(response))

        # Improvement 12: dismiss typing indicator
        self._stop_typing_indicator()

        if self._pending_user_msg:
            self._history.append(("user", self._pending_user_msg))
            self._history.append(("assistant", response))
            self._pending_user_msg = ""
            if len(self._history) > MAX_HISTORY_TURNS * 2:
                self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        # Improvement 1: store last response for double-tap-to-reply
        self._last_response = response

        resp_mood = _detect_response_mood(response)
        final_state = resp_mood if resp_mood else State.TALKING
        self._char.set_state(final_state)
        self._personality.log_mood(final_state.name)
        self._show_bubble(response, priority=BUBBLE_HIGH, interactive=True)
        self._return_timer.stop()  # idle return triggered by bubble_closed instead
        QTimer.singleShot(1000, self._check_achievements)

    def _on_usage(self, input_tokens: int, output_tokens: int):
        self._personality.log_tokens(input_tokens, output_tokens)
        self._personality.save()
        log.debug("Token usage — in=%d out=%d", input_tokens, output_tokens)

    def _on_error(self, msg: str):
        # Improvement 12: dismiss typing indicator on error too
        self._stop_typing_indicator()
        self._pending_user_msg = ""
        self._char.set_state(State.IDLE)
        self._show_bubble(f"Oops! {msg}", priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

    # ── Improvement 1: double-tap bubble to reply ────────────────────────────

    def _on_bubble_dismissed(self):
        """Called whenever a bubble is closed — return to idle if nothing is queued."""
        if not self._bubble_queue and not (self._worker and self._worker.isRunning()):
            QTimer.singleShot(800, self._go_idle)

    def _bubble_double_clicked(self):
        """Open chat pre-filled with context from the last bubble exchange."""
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        prefill = "About your reply: " if self._last_response else ""
        self._chat_input.activate(anchor, prefill=prefill)

    # ── Improvement 8: emoji reaction handler ────────────────────────────────

    def _on_bubble_reaction(self, reaction_name: str):
        """Handle emoji reaction on bubble - log mood and play small animation."""
        reaction_map = {
            "thumbs_up": ("HAPPY",    State.HAPPY,    "hehe~ thanks! 💜"),
            "laugh":     ("DANCING",  State.DANCING,  "hahaha~ 😂"),
            "think":     ("THINKING", State.THINKING, "hmm... I'll ponder that 🤔"),
        }
        mood_name, state, quip = reaction_map.get(reaction_name, ("HAPPY", State.HAPPY, "~"))
        self._personality.log_mood(mood_name)
        self._char.set_state(state)
        self._show_bubble(quip, priority=BUBBLE_LOW)
        self._return_timer.start(3000)

    # ── Daily events (word of day, challenge) ─────────────────────────────────

    def _check_daily_events(self):
        word = self._personality.get_word_of_day()
        if word:
            w, defn = word
            QTimer.singleShot(2000, lambda: self._fire_word_of_day(w, defn))

        challenge = self._personality.get_daily_challenge()
        if challenge:
            delay = 6000 if not word else 14000
            QTimer.singleShot(delay, lambda c=challenge: self._fire_challenge(c))

        QTimer.singleShot(15_000, self._check_weekly_recap)

        if self._personality.needs_checkin():
            QTimer.singleShot(12_000, self._check_emotional)

    def _fire_word_of_day(self, word: str, defn: str):
        if self._char.state != State.IDLE:
            return
        self._char.set_state(State.THINKING)
        self._personality.log_mood("THINKING")
        self._show_bubble(f'Word of the day: {word}\n"{defn}"', style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(9000)

    def _fire_challenge(self, challenge: str):
        if self._char.state not in (State.IDLE, State.HAPPY):
            return
        self._char.set_state(State.THINKING)
        self._personality.log_mood("THINKING")
        self._show_bubble(f"Daily challenge 💡\n{challenge}", style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(10000)

    def _check_emotional(self):
        if not self._personality.needs_checkin():
            return
        moods = ["Great! 😄", "Good 🙂", "Okay 😐", "Tired 😴", "Stressed 😤", "Not great 😔"]
        mood, ok = QInputDialog.getItem(
            None, f"Hey {self._personality.name}! 💙",
            "Quick check-in — how are you feeling?",
            moods, 0, False,
        )
        if not ok:
            return
        self._personality.log_checkin(mood)
        responses = {
            "Great! 😄": ("Wonderful! Keep that energy! ✨", State.HAPPY),
            "Good 🙂":   ("Glad to hear it! 😊", State.HAPPY),
            "Okay 😐":   ("Okay is totally fine. I'm here if you need me. 💙", State.WAVING),
            "Tired 😴":  ("You've been working hard. Maybe take a short break? ☕", State.SLEEPING),
            "Stressed 😤": ("Hey — breathe. You've got this. One thing at a time. 🤝", State.THINKING),
            "Not great 😔": ("I'm sorry you're having a tough time. I'm here. 💙", State.WAVING),
        }
        text, state = responses.get(mood, ("Thanks for sharing! 💙", State.HAPPY))
        self._char.set_state(state)
        self._show_bubble(text, style=THOUGHT, priority=BUBBLE_HIGH)
        self._return_timer.start(6000)

    def _check_achievements(self):
        p = self._personality
        checks = [
            ("first_chat",         p._data.get("interactions", 0) >= 1,    "First chat! We're friends now 🎉"),
            ("interactions_10",    p._data.get("interactions", 0) >= 10,   "10 chats! I'm getting to know you ✨"),
            ("interactions_100",   p._data.get("interactions", 0) >= 100,  "100 conversations! True friendship 💙"),
            ("streak_7",           p._data.get("streak", 0) >= 7,          "7-day streak! You're consistent 🔥"),
            ("streak_30",          p._data.get("streak", 0) >= 30,         "30 days! I'm so glad you're here 🌟"),
            ("notes_first",        len(p.get_notes()) >= 1,                "First note saved! 📌"),
            ("profile_complete",   p._data.get("profile_complete", False), "Profile complete! I know you better now 💜"),
        ]
        for achievement_id, condition, message in checks:
            if condition and p.unlock_achievement(achievement_id):
                self._char.set_state(State.HAPPY)
                self._show_bubble(f"Achievement unlocked: {message}", style=SHOUT, priority=BUBBLE_HIGH)
                self._return_timer.start(5000)
                break  # show one at a time

    # ── Clipboard watcher ─────────────────────────────────────────────────────

    def _on_clipboard_change(self):
        # Screenshot reaction: check if clipboard now has an image
        clipboard = QApplication.instance().clipboard()
        img = clipboard.image()
        if not img.isNull():
            if not self._last_clip_had_image and self._char.state in (State.IDLE, State.HAPPY):
                self._last_clip_had_image = True
                self._char.set_state(State.SURPRISED)
                QTimer.singleShot(600, lambda: self._char.set_state(State.HAPPY))
                self._show_bubble(
                    "Did you just take a screenshot? Want me to describe what I see?",
                    priority=BUBBLE_LOW,
                )
                self._return_timer.start(7000)
            return
        self._last_clip_had_image = False

        text = clipboard.text().strip()
        if len(text) < 30 or text == self._last_clipboard:
            return
        if self._char.state not in (State.IDLE, State.HAPPY):
            return
        self._last_clipboard    = text
        self._clipboard_pending = text

        # Git commit reaction — look for commit SHA pattern in clipboard
        if _GIT_COMMIT_RE.search(text) and len(text) < 300:
            self._clipboard_pending = ""
            self._char.set_state(State.SURPRISED)
            QTimer.singleShot(600, lambda: self._char.set_state(State.DANCING))
            self._personality.log_mood("DANCING")
            cheers = [
                "Did you just commit?! Let's gooo! 🎉",
                "Commit detected! You're shipping! 🚀",
                "Yes! Another commit! Keep going! ✨",
                "Git commit! I felt that energy! 🕺",
            ]
            self._show_bubble(random.choice(cheers), style=SHOUT, priority=BUBBLE_NORMAL)
            self._return_timer.start(6000)
            return

        if self._is_code_snippet(text):
            self._char.set_state(State.SURPRISED)
            QTimer.singleShot(600, lambda: self._char.set_state(State.THINKING))
            self._clipboard_pending = text
            self._show_bubble("That looks like code! Click me to ask about it 💻", priority=BUBBLE_LOW)
            self._return_timer.start(5000)
            return

        self._char.set_state(State.SURPRISED)
        QTimer.singleShot(800, lambda: self._char.set_state(State.HAPPY))
        self._show_bubble("Ooh, copied something! Click me to ask about it 👀", priority=BUBBLE_LOW)
        self._return_timer.start(10_000)

    # ── Keyboard + screen-time tracking ──────────────────────────────────────

    def _start_kb_listener(self):
        try:
            from pynput import keyboard
            def _on_press(key):
                now = time.time()
                with self._keypress_lock:
                    self._last_keypress = now
                # improvement 2: accumulate keypress count for WPM tracking
                self._keypress_count_wpm += 1
            self._kb_listener = keyboard.Listener(on_press=_on_press, daemon=True)
            self._kb_listener.start()
        except Exception:
            self._kb_listener = None

    def _check_typing_idle(self):
        now = time.time()
        with self._keypress_lock:
            last = self._last_keypress

        # ── Improvement 2: fast-typing (>80 WPM for >30 seconds) ─────────────
        elapsed_wpm = now - self._wpm_window_start
        if elapsed_wpm >= 30.0:
            kcount = self._keypress_count_wpm
            wpm = (kcount / 5.0) / (elapsed_wpm / 60.0)
            self._keypress_count_wpm = 0
            self._wpm_window_start = now
            if wpm > 80 and not self._wpm_alerted:
                self._wpm_alerted = True
                self._show_bubble(
                    "Woah, slow down, your fingers will thank you! 🏃",
                    style=SPEECH, priority=BUBBLE_NORMAL,
                )
                self._return_timer.start(6000)
                QTimer.singleShot(5 * 60_000, self._reset_wpm_alert)
            elif wpm <= 80:
                self._wpm_alerted = False
        elif self._keypress_count_wpm == 0 and elapsed_wpm >= 60:
            # Reset window if nothing happened for a while
            self._wpm_window_start = now

        if self._char.state in (State.SLEEPING, State.THINKING, State.TALKING):
            return

        idle_min = (now - last) / 60

        # ── Improvement 5: idle timeout escalation ────────────────────────────
        # 30-min idle → speech bubble; 40-min idle → SHOUT bubble
        if idle_min >= 40 and self._idle_escalated:
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(
                "HELLO?? Are you still there?? Please drink some water at least!! 💧",
                style=SHOUT, priority=BUBBLE_NORMAL,
            )
            self._return_timer.start(8000)
            self._idle_escalated = False
            with self._keypress_lock:
                self._last_keypress = now
            return

        if idle_min >= 30 and not self._idle_escalated:
            msgs = [
                "Hey... you've been quiet for a while. Taking a real break? 🍵",
                "You've been away for 30 minutes. Hope everything's ok!",
                "No typing for half an hour... stretch time? 🧘",
                "Still there? Just checking in ✨",
            ]
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(random.choice(msgs), priority=BUBBLE_NORMAL)
            self._return_timer.start(8000)
            self._idle_escalated = True
            return

        # Reset escalation when user is active
        if idle_min < 5:
            self._idle_escalated = False

        # Original 20-min check (kept for users who may already be mid-session)
        if idle_min >= 20 and not self._idle_escalated:
            msgs = [
                "Hey... you've been quiet. Taking a break? 🍵",
                "You seem away. Hope everything's ok!",
                "No typing for a while... stretch time? 🧘",
                "Still there? Just checking in ✨",
            ]
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(random.choice(msgs), priority=BUBBLE_NORMAL)
            self._return_timer.start(8000)
            with self._keypress_lock:
                self._last_keypress = now
            return

        # ── 2-hour screen-time nudge ──────────────────────────────────────────
        if not self._screen_nudge_done:
            hours = (now - self._session_active_start) / 3600
            if hours >= 2:
                self._screen_nudge_done = True
                self._char.set_state(State.HAPPY)
                self._personality.log_mood("HAPPY")
                msgs = [
                    "Hey! You've been at it for 2 hours. Maybe take a proper break? 🌿",
                    "2 hours of screen time logged. Your eyes deserve a rest 👀",
                    "Two whole hours! Time for a stretch and some water 💧",
                ]
                self._show_bubble(random.choice(msgs), style=SHOUT, priority=BUBBLE_NORMAL)
                self._return_timer.start(9000)
                QTimer.singleShot(90 * 60_000, self._reset_screen_nudge)  # re-arm after 90 min

    def _reset_wpm_alert(self):
        self._wpm_alerted = False

    def _reset_screen_nudge(self):
        self._screen_nudge_done = False
        self._session_active_start = time.time()

    def _schedule_idle(self):
        min_ms = self._settings.value("idle_min", 30, type=int) * 1000
        max_ms = self._settings.value("idle_max", 90, type=int) * 1000
        self._idle_timer.start(random.randint(min_ms, max_ms))

    # ── Greetings ─────────────────────────────────────────────────────────────

    def _greet(self):
        streak, milestone, is_first_today = self._personality.update_streak()
        created = self._personality._data.get("created", "")
        today_s = date.today().isoformat()

        # Improvement 9: personalise with user's name if set
        user_name = self._personality.get_profile().get("name", "").strip()

        try:
            is_birthday = (len(created) >= 10 and today_s[5:] == created[5:10]
                           and created[:10] != today_s)
        except Exception:
            is_birthday = False

        if is_birthday:
            try:
                days = (date.today() - date.fromisoformat(created[:10])).days
            except Exception:
                days = "?"
            self._char.set_state(State.DANCING)
            msg = f"It's my birthday! 🎂 We've been together {days} days! Thank you~"
        elif milestone:
            _msgs = {
                7:   "7 days in a row! One whole week! 🎉",
                14:  "14 days straight — you can't get rid of me 😄",
                30:  "30-day streak! We're basically inseparable 🥰",
                50:  "50 days! Half a hundred. That's wild.",
                100: "100-DAY STREAK!! I'm crying 🥹 thank you!",
                365: "One whole year together!! 🎊🎊🎊",
            }
            self._char.set_state(State.HAPPY)
            msg = _msgs.get(streak, f"{streak} days in a row! Amazing.")
        elif is_first_today:
            self._char.set_state(State.HAPPY)
            base_quip = self._personality.time_quip()
            # Improvement 9: personalise time-based greeting with user name
            if user_name:
                for prefix in ("Good morning!", "Good afternoon!", "Good evening!",
                               "Still up late?", "Night owl mode"):
                    if base_quip.startswith(prefix):
                        rest = base_quip[len(prefix):].lstrip()
                        msg = f"{prefix[:-1]}, {user_name}! {rest}".strip()
                        break
                else:
                    msg = f"Hey {user_name}! " + base_quip
            else:
                msg = base_quip
        else:
            self._char.set_state(State.HAPPY)
            if user_name:
                msg = random.choice([
                    f"Hey {user_name}, back already! 👋",
                    f"Miss me, {user_name}? 😊",
                    f"Welcome back, {user_name}~",
                    f"Oh, {user_name}! You're back!",
                ])
            else:
                msg = random.choice([
                    "Hey, back already! 👋", "Miss me? 😊",
                    "Welcome back~", "Oh, you're back!",
                ])

        # Improvement 4: reference last chat topic on first-today greeting
        topics = self._personality._data.get("topics", [])
        if topics and is_first_today and not milestone and not is_birthday:
            last_topic = topics[-1]
            topic_suffix = random.choice([
                f" Still thinking about {last_topic}?",
                f" Ready to pick up where we left off on {last_topic}?",
                f" Last time we chatted about {last_topic}~",
            ])
            msg = msg.rstrip() + topic_suffix

        self._personality.log_mood("HAPPY")
        self._show_bubble(msg, priority=BUBBLE_NORMAL)
        self._return_timer.start(6000)

        if not self._personality._data.get("profile_complete", False):
            QTimer.singleShot(5000, self._run_profile_questionnaire)

        # First-launch prompt for deep screen watcher (fires once)
        if not self._personality._data.get("deep_watch_prompted", False):
            self._personality._data["deep_watch_prompted"] = True
            self._personality.save()
            QTimer.singleShot(8000, self._prompt_deep_watch_enable)

    def _second_pip_greet(self):
        self._char.set_state(State.HAPPY)
        greets = ["hi!! 👋", "oh, a twin!~", "heyyy~", "another me! ✨"]
        self._show_bubble(random.choice(greets), priority=BUBBLE_LOW)
        self._return_timer.start(4000)

    def _run_profile_questionnaire(self):
        """Ask 3 quick questions on first run to seed user profile."""
        work, ok = QInputDialog.getItem(
            None, "Hey, nice to meet you! 👋",
            "What best describes what you do?",
            ["Developer / Engineer", "Designer", "Student", "Writer / Creator", "Other"],
            0, False,
        )
        if not ok:
            return
        work_map = {"Developer / Engineer": "developer", "Designer": "designer",
                    "Student": "student", "Writer / Creator": "writer", "Other": "other"}
        self._personality.set_profile_field("work_type", work_map.get(work, "other"))

        interests_raw, ok = QInputDialog.getText(
            None, "Nice! 🎉",
            "What are your interests? (comma-separated, e.g. Python, music, coffee)",
        )
        if ok and interests_raw.strip():
            interests = [i.strip() for i in interests_raw.split(",") if i.strip()][:8]
            self._personality.set_profile_field("interests", interests)

        style, ok = QInputDialog.getItem(
            None, "Almost done! ✨",
            "How do you like Pip to talk to you?",
            ["Casual & playful", "Warm & supportive", "Professional & concise"],
            0, False,
        )
        if ok:
            style_map = {"Casual & playful": "casual", "Warm & supportive": "casual",
                         "Professional & concise": "professional"}
            self._personality.set_profile_field("communication_style", style_map.get(style, "casual"))

        self._personality._data["profile_complete"] = True
        self._personality.save()
        self._char.set_state(State.HAPPY)
        self._show_bubble("Nice to meet you! I'll remember that. 😊", style=THOUGHT, priority=BUBBLE_HIGH)
        self._return_timer.start(4000)

    def _pet_pip(self):
        self._char.set_state(State.HAPPY)
        self._personality.log_mood("HAPPY")
        pets = ["hehe~ ♡", "hehe~", "*purrs*", "uwu~", "ehehe~", "*wiggles happily*", "teehee~"]
        self._show_bubble(random.choice(pets), priority=BUBBLE_LOW)
        self._return_timer.start(4000)

    # ── Random idle events ────────────────────────────────────────────────────

    def _random_event(self):
        ev = random.choices(
            ["quip", "dance", "sleep", "happy", "think", "time_greet", "haiku", "excited"],
            weights=[26, 17, 12, 15, 9, 6, 10, 5],
        )[0]

        _log_idle.info("Idle event fired (type=%s)", ev)

        if ev == "quip":
            text, state_name = self._personality.random_quip_with_state()
            state = State[state_name] if state_name in State.__members__ else State.HAPPY
            self._char.set_state(state)
            self._personality.log_mood(state.name)
            self._show_bubble(text, priority=BUBBLE_LOW)
            self._return_timer.start(6000)
        elif ev == "dance":
            self._char.set_state(State.DANCING)
            self._personality.log_mood("DANCING")
            self._show_bubble("♪ doo doo doo ♪", priority=BUBBLE_LOW)
            self._return_timer.start(8000)
        elif ev == "sleep":
            self._char.set_state(State.SLEEPING)
            self._personality.log_mood("SLEEPING")
            self._return_timer.start(12000)
            # Dream muttering fires 4-8s into the sleep
            self._dream_timer.start(random.randint(4000, 8000))
        elif ev == "happy":
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble("Yay! 🎉", priority=BUBBLE_LOW)
            self._return_timer.start(5000)
        elif ev == "think":
            self._char.set_state(State.THINKING)
            self._personality.log_mood("THINKING")
            self._show_bubble("Hmm... 🤔", priority=BUBBLE_LOW)
            self._return_timer.start(6000)
        elif ev == "time_greet":
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(self._personality.time_quip(), priority=BUBBLE_LOW)
            self._return_timer.start(5000)
        elif ev == "haiku":
            self._fetch_haiku()
        elif ev == "excited":
            excite_msgs = [
                "AHHH!! Something amazing just happened!! ✨✨",
                "I just had the best idea!! 💡💡",
                "Oh WOW I'm so excited right now!! ⭐",
                "I LOVE being here!! ★★★",
            ]
            self._trigger_excited(random.choice(excite_msgs))

        # Day-of-week quip (fires at most once per day)
        day_quip = self._personality.get_day_quip()
        if day_quip and random.random() < 0.4:
            text, state_name = day_quip
            self._char.set_state(getattr(State, state_name))
            self._show_bubble(text, priority=BUBBLE_NORMAL)
            self._return_timer.start(5000)
            self._schedule_idle()
            return

        # Autonomous question (friend+ only, 20% chance via personality)
        autonomous_q = self._personality.get_autonomous_prompt()
        if autonomous_q:
            self._char.set_state(State.WAVING)
            self._show_bubble(autonomous_q, priority=BUBBLE_NORMAL)
            self._return_timer.start(6000)
            self._schedule_idle()
            return

        # Stress check (rare — 5% chance)
        if random.random() < 0.05 and self._personality.detect_stress():
            self._char.set_state(State.WAVING)
            self._show_bubble("Hey — I've noticed you've been pushing yourself a lot lately. Are you taking care of yourself? 💙", style=THOUGHT, priority=BUBBLE_NORMAL)
            self._return_timer.start(8000)
            self._schedule_idle()
            return

        # Whimsical wish (3% chance)
        if random.random() < 0.03:
            self._pip_wish()
            self._schedule_idle()
            return

        # Daily learning prompt (after 6pm, once per day)
        if datetime.now().hour >= 18:
            self._prompt_daily_learning()

        # Interest fact (8% chance)
        if random.random() < 0.08 and not self._focus_mode:
            self._fetch_interest_fact()
            self._schedule_idle()
            return

        # Skill tip (once per day, 15% chance)
        if random.random() < 0.15 and not self._focus_mode:
            self._fetch_skill_tip()
            self._schedule_idle()
            return

        # Code joke (once per day, 10% chance)
        if random.random() < 0.10 and not self._focus_mode:
            self._fetch_code_joke()
            self._schedule_idle()
            return

        # Git activity (8% chance)
        if random.random() < 0.08 and not self._focus_mode:
            self._check_git_activity()
            self._schedule_idle()
            return

        self._schedule_idle()

    def _go_idle(self):
        self._dream_timer.stop()
        self._stretch_timer.stop()
        self._char.set_state(State.IDLE)

    # ── STRETCHING: auto-triggered idle variant ───────────────────────────────

    def _trigger_stretching(self):
        """Play STRETCHING for 2s then return to IDLE."""
        if self._char.state != State.IDLE:
            return
        self._char.set_state(State.STRETCHING)
        self._personality.log_mood("STRETCHING")
        # stretch_timer is a safety net; the tick loop also handles the return
        self._stretch_timer.start(2100)

    # ── EXCITED: new high-energy state ───────────────────────────────────────

    def _trigger_excited(self, message: str = ""):
        """Switch to EXCITED state with an optional bubble."""
        self._char.set_state(State.EXCITED)
        self._personality.log_mood("EXCITED")
        if message:
            self._show_bubble(message, style=SHOUT, priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

    # ── Wander mode ───────────────────────────────────────────────────────────

    def _wander_tick(self):
        """Fire wander logic; rescheduled after each move."""
        # Don't wander during active states or while bubble is showing
        if self._char.state in (State.TALKING, State.SLEEPING):
            self._reschedule_wander()
            return
        if self._bubble.isVisible():
            self._reschedule_wander()
            return
        if not self._settings.value("wander_mode", False, type=bool):
            return   # wander mode was toggled off

        self._do_wander()

    def _do_wander(self):
        """Animate Pip drifting to a new random position on the primary screen."""
        screen = QApplication.primaryScreen().geometry()
        margin = 40
        new_x = random.randint(margin, screen.width()  - self.width()  - margin)
        new_y = random.randint(margin, screen.height() - self.height() - margin)

        # Show a tiny thought bubble before moving
        self._show_bubble("...", style=THOUGHT, priority=BUBBLE_LOW)
        self._char.set_state(State.STRETCHING)

        # Animate position using QPropertyAnimation
        if self._wander_anim is not None:
            self._wander_anim.stop()
        self._wander_anim = QPropertyAnimation(self, b"pos", self)
        self._wander_anim.setDuration(3000)
        self._wander_anim.setEndValue(QPoint(new_x, new_y))
        self._wander_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._wander_anim.finished.connect(self._on_wander_done)
        self._wander_anim.start()

    def _on_wander_done(self):
        """Called when the wander animation completes."""
        self._go_idle()
        if not self._is_second:
            self._settings.setValue("x", self.x())
            self._settings.setValue("y", self.y())
        self._reschedule_wander()

    def _reschedule_wander(self):
        """Re-arm the wander timer for the next interval."""
        if self._settings.value("wander_mode", False, type=bool):
            self._wander_timer.start(random.randint(300, 480) * 1000)

    # ── Dream muttering ───────────────────────────────────────────────────────

    def _mutter_dream(self):
        if self._char.state != State.SLEEPING:
            return
        self._show_bubble(random.choice(DREAM_QUIPS), style=THOUGHT, priority=BUBBLE_LOW)

    # ── Haiku (via Claude) ────────────────────────────────────────────────────

    def _fetch_haiku(self):
        if self._haiku_worker and self._haiku_worker.isRunning():
            return
        self._char.set_state(State.THINKING)
        prompt = ("Write a single haiku (5-7-5 syllables) about coding, bugs, or desktop life. "
                  "Just the haiku, nothing else. No title, no explanation.")
        self._haiku_worker = ClaudeWorker(
            prompt,
            "You are a witty haiku poet. Reply with only the haiku, three lines.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._haiku_worker.response_ready.connect(self._on_haiku_ready)
        self._haiku_worker.error_occurred.connect(lambda _: self._go_idle())
        self._haiku_worker.start()

    def _on_haiku_ready(self, haiku: str):
        self._char.set_state(State.THINKING)
        self._personality.log_mood("THINKING")
        self._show_bubble(f"✦ {haiku.strip()} ✦", style=THOUGHT, priority=BUBBLE_LOW)
        self._return_timer.start(10000)

    # ── Active window watcher ─────────────────────────────────────────────────

    _WINDOW_REACTIONS: dict[tuple[str, ...], list[str]] = {
        ("firefox", "chrome", "chromium", "brave"):
            ["browsing the web? find anything cool? 🌐", "internet adventures!"],
        ("code", "vscode", "vim", "nvim", "emacs", "sublime"):
            ["coding time! 💻", "VS Code? nice.", "cracking some code~"],
        ("terminal", "konsole", "gnome-terminal", "alacritty", "kitty", "bash", "zsh"):
            ["terminal mode. power user energy ⚡", "shell time!"],
        ("youtube",):
            ["YouTube? I see you 👀", "taking a little break? smart."],
        ("discord", "telegram", "slack", "signal"):
            ["chatting? say hi for me 💬"],
        ("spotify", "vlc", "rhythmbox", "audacious"):
            ["music time ♪ nice.", "listening to something good?"],
    }

    def _check_active_window(self):
        if self._char.state != State.IDLE or random.random() > 0.35:
            return
        threading.Thread(target=self._check_active_window_bg, daemon=True).start()

    def _check_active_window_bg(self):
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            title = result.stdout.strip().lower()
        except Exception:
            return
        if not title:
            return
        for keywords, reactions in self._WINDOW_REACTIONS.items():
            if any(k in title for k in keywords):
                QTimer.singleShot(0, lambda r=reactions: self._react_to_window(r))
                return

    def _react_to_window(self, reactions: list[str]):
        if self._char.state != State.IDLE:
            return
        self._char.set_state(State.HAPPY)
        self._show_bubble(random.choice(reactions), priority=BUBBLE_LOW)
        self._return_timer.start(5000)

    # ── Music detector (playerctl / MPRIS) ───────────────────────────────────

    def _check_music(self):
        if self._char.state != State.IDLE or random.random() > 0.4:
            return
        threading.Thread(target=self._check_music_bg, daemon=True).start()

    def _check_music_bg(self):
        try:
            r_status = subprocess.run(
                ["playerctl", "status"], capture_output=True, text=True, timeout=2,
            )
            if r_status.stdout.strip() != "Playing":
                return
            r_meta = subprocess.run(
                ["playerctl", "metadata", "--format", "{{artist}} — {{title}}"],
                capture_output=True, text=True, timeout=2,
            )
            track = r_meta.stdout.strip()
        except Exception:
            return
        if not track or track == self._last_music_title:
            return
        self._last_music_title = track
        QTimer.singleShot(0, lambda t=track: self._react_to_music(t))

    def _react_to_music(self, track: str):
        if self._char.state != State.IDLE:
            return
        self._char.set_state(State.DANCING)
        self._personality.log_mood("DANCING")
        reactions = [
            f"♪ oh nice — {track}! I love this ♪",
            f"Now playing: {track} 🎵 bop!",
            f"♪ {track} — great taste! ♪",
        ]
        self._show_bubble(random.choice(reactions), priority=BUBBLE_LOW)
        self._return_timer.start(7000)

        # 30% chance, min 10-min gap — fetch an interesting fact about the song
        now = time.time()
        if (random.random() < 0.30
                and now - self._last_song_fact_time > 600
                and not (self._song_fact_worker and self._song_fact_worker.isRunning())):
            QTimer.singleShot(8000, lambda t=track: self._fetch_song_fact(t))

    def _fetch_song_fact(self, track: str):
        if self._char.state not in (State.IDLE, State.DANCING, State.HAPPY):
            return
        parts = track.split(" — ", 1)
        if len(parts) == 2:
            artist, title = parts[0], parts[1]   # playerctl gives "artist — title"
            prompt = (
                f'Give me one interesting, surprising, or little-known fact about the song '
                f'"{title}" by {artist}. '
                f'1-2 sentences only. If you\'re unsure about this exact song, share a '
                f'fascinating fact about {artist} instead. '
                f'No intro phrases like "Did you know".'
            )
        else:
            prompt = (
                f'Give me one surprising fact about "{track}" (song or artist). '
                f'1-2 sentences, no intro phrases.'
            )
        self._song_fact_worker = ClaudeWorker(
            prompt,
            "You are a music trivia expert. Be concise and genuinely interesting.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._song_fact_worker.response_ready.connect(self._on_song_fact_ready)
        self._song_fact_worker.error_occurred.connect(lambda _: None)
        self._song_fact_worker.start()

    def _on_song_fact_ready(self, fact: str):
        self._last_song_fact_time = time.time()
        if self._char.state not in (State.IDLE, State.HAPPY, State.THINKING):
            return
        self._char.set_state(State.THINKING)
        self._personality.log_mood("THINKING")
        self._show_bubble(f"🎵 {fact.strip()}", style=THOUGHT, priority=BUBBLE_LOW)
        self._return_timer.start(max(8000, len(fact.split()) * 350))

    # ── System stats commentator ──────────────────────────────────────────────

    def _check_stats(self):
        if self._char.state != State.IDLE:
            return
        threading.Thread(target=self._check_stats_bg, daemon=True).start()

    def _check_stats_bg(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
        except ImportError:
            return
        except Exception:
            return
        QTimer.singleShot(0, lambda c=cpu, r=ram: self._react_to_stats(c, r))

    def _react_to_stats(self, cpu: float, ram: float):
        if self._char.state != State.IDLE:
            return
        if cpu > 85:
            msgs = [
                f"Your CPU is at {cpu:.0f}%! Are you mining crypto or something? 🔥",
                f"CPU: {cpu:.0f}%! Your machine is sweating 😅",
                f"Whoa — {cpu:.0f}% CPU. Compiling the universe? 💻🔥",
            ]
            self._char.set_state(State.THINKING)
            self._show_bubble(random.choice(msgs), priority=BUBBLE_LOW)
            self._return_timer.start(6000)
        elif ram > 88:
            msgs = [
                f"RAM at {ram:.0f}%! Maybe close a tab or fifty? 💭",
                f"{ram:.0f}% memory used... Chrome again? 😅",
                f"Running low on RAM ({ram:.0f}%). Might want to free some up!",
            ]
            self._char.set_state(State.THINKING)
            self._show_bubble(random.choice(msgs), priority=BUBBLE_LOW)
            self._return_timer.start(6000)

    # ── Weather ───────────────────────────────────────────────────────────────

    def _fetch_weather(self):
        if self._weather_fetched:
            return
        threading.Thread(target=self._fetch_weather_bg, daemon=True).start()

    def _fetch_weather_bg(self):
        try:
            import urllib.request
            with urllib.request.urlopen("https://wttr.in/?format=%C+%t", timeout=5) as resp:
                data = resp.read().decode().strip()
        except Exception:
            return
        if data:
            QTimer.singleShot(0, lambda d=data: self._react_to_weather(d))

    def _react_to_weather(self, weather: str):
        self._weather_fetched = True
        weather_lower = weather.lower()
        if any(w in weather_lower for w in ("rain", "drizzle", "shower")):
            state, msg = State.SLEEPING, f"It's {weather} outside ☔ Stay cozy!"
        elif any(w in weather_lower for w in ("snow", "blizzard", "sleet")):
            state, msg = State.HAPPY, f"{weather} outside! ❄️ Wrap up warm~"
        elif any(w in weather_lower for w in ("storm", "thunder", "lightning")):
            state, msg = State.THINKING, f"Stormy out there! ⛈ {weather}"
        elif any(w in weather_lower for w in ("sunny", "clear", "fine")):
            state, msg = State.DANCING, f"{weather} ☀️ Beautiful day!"
        elif any(w in weather_lower for w in ("cloud", "overcast", "fog", "mist")):
            state, msg = State.THINKING, f"It's {weather} out. Very atmospheric~"
        else:
            return   # don't react to unknown conditions
        self._char.set_state(state)
        self._personality.log_mood(state.name)
        self._show_bubble(msg, priority=BUBBLE_LOW)
        self._return_timer.start(6000)

    # ── Feature 1: Hydration reminder ────────────────────────────────────────

    def _update_hydration_timer(self):
        if self._personality._data.get("hydration_enabled", True):
            interval = self._personality._data.get("hydration_interval_min", 45)
            self._hydration_timer.start(interval * 60_000)
        else:
            self._hydration_timer.stop()

    def _hydration_reminder(self):
        if self._minimized or self._personality.is_quiet_hours() or self._focus_mode:
            return
        msgs = ["Time for some water! 💧", "Hydration check! 💧 Have you had water lately?",
                "Psst — drink some water. I mean it. 💧", "Water break! Your brain will thank you. 💧"]
        self._char.set_state(State.HAPPY)
        self._show_bubble(random.choice(msgs), priority=BUBBLE_NORMAL)
        self._return_timer.start(4000)

    # ── Feature 2: Eye-strain 20-20-20 ───────────────────────────────────────

    def _eyestrain_reminder(self):
        if self._minimized or self._personality.is_quiet_hours() or self._focus_mode:
            return
        self._char.set_state(State.THINKING)
        self._show_bubble("20-20-20 rule! Look at something 20 feet away for 20 seconds. 👀", style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(5000)

    # ── Feature 3: Focus mode ────────────────────────────────────────────────

    def _toggle_focus_mode(self):
        self._focus_mode = not self._focus_mode
        self._personality._data["focus_mode"] = self._focus_mode
        self._personality.save()
        if self._focus_mode:
            self._idle_timer.stop()
            self._show_bubble("Focus mode ON. I'll stay quiet. You've got this. 🎯", style=THOUGHT, priority=BUBBLE_HIGH)
        else:
            self._schedule_idle()
            self._show_bubble("Focus mode OFF. I'm back! 🎉", style=SPEECH, priority=BUBBLE_HIGH)
        self._return_timer.start(3000)

    # ── Feature 5: Weekly recap ───────────────────────────────────────────────

    def _check_weekly_recap(self):
        """Fire weekly recap on Mondays."""
        if date.today().weekday() != 0:  # Monday
            return
        last = self._personality._data.get("last_weekly_recap", "")
        if last == date.today().isoformat():
            return
        self._personality._data["last_weekly_recap"] = date.today().isoformat()
        self._personality.save()
        interactions = self._personality._data.get("interactions", 0)
        streak = self._personality._data.get("streak", 0)
        topics = self._personality._data.get("topics", [])
        top = topics[-3:] if topics else []
        msg = f"Weekly recap! 📊 {interactions} total chats, {streak}-day streak"
        if top:
            msg += f", talked about: {', '.join(top)}"
        self._char.set_state(State.DANCING)
        self._show_bubble(msg, style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(7000)

    # ── Feature 6: "What did I learn today?" ──────────────────────────────────

    def _prompt_daily_learning(self):
        today = date.today().isoformat()
        if self._personality._data.get("last_learn_day") == today:
            return
        if datetime.now().hour < 18:  # only after 6pm
            return
        self._personality._data["last_learn_day"] = today
        self._personality.save()
        self._char.set_state(State.THINKING)
        self._show_bubble("Evening question 🌙 What's one thing you learned today?", style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(6000)

    # ── Feature 7: Pip's whimsical wish ──────────────────────────────────────

    def _pip_wish(self):
        wishes = [
            "I wish I could taste pizza... 🍕",
            "I wish I had tiny hands to type with...",
            "Sometimes I wonder what rain sounds like. 🌧️",
            "I wish I could read all the books. 📚",
            "If I could have a pet, I'd want a pixel cat. 🐱",
            "I wish I could code for you while you sleep...",
        ]
        self._char.set_state(State.SLEEPING)
        self._show_bubble(random.choice(wishes), style=THOUGHT, priority=BUBBLE_LOW)
        self._return_timer.start(5000)

    # ── Feature 10: Interest-based random fact ───────────────────────────────

    def _fetch_interest_fact(self):
        profile = self._personality.get_profile() if hasattr(self._personality, 'get_profile') else {}
        interests = profile.get("interests", [])
        if not interests:
            return
        topic = random.choice(interests)
        sys_p = self._personality.get_system_prompt()
        prompt = f"Share one surprising, little-known fact about {topic}. Keep it to 1-2 sentences. Make it genuinely interesting."
        model = self._settings.value("model", "claude-sonnet-4-6")
        self._interest_worker = ClaudeWorker(prompt, sys_p, model=model)
        self._interest_worker.response_ready.connect(lambda f: self._on_interest_fact(f))
        self._interest_worker.error_occurred.connect(lambda _: None)
        self._interest_worker.start()
        self._char.set_state(State.THINKING)

    def _on_interest_fact(self, fact: str):
        self._show_bubble(f"💡 {fact.strip()}", style=THOUGHT, priority=BUBBLE_LOW)
        self._return_timer.start(8000)

    # ── Feature 11: Git activity reader ──────────────────────────────────────

    def _check_git_activity(self):
        def _bg():
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-3"],
                    capture_output=True, text=True, timeout=5,
                    cwd=os.path.expanduser("~")
                )
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().splitlines()
                    QTimer.singleShot(0, lambda: self._react_git_activity(lines))
            except Exception:
                log.debug("git activity check failed", exc_info=True)
        threading.Thread(target=_bg, daemon=True).start()

    def _react_git_activity(self, commits: list):
        if not commits:
            return
        msg = commits[0][:60]
        reactions = [
            f"I see you committed: \"{msg}\" — nice work! 💪",
            f"Recent commit: \"{msg}\" — making progress! 🚀",
            f"Spotted a new commit! \"{msg}\" ✨",
        ]
        self._char.set_state(State.HAPPY)
        self._show_bubble(random.choice(reactions), priority=BUBBLE_LOW)
        self._return_timer.start(5000)

    # ── Feature 12: Code joke of the day ─────────────────────────────────────

    def _fetch_code_joke(self):
        today = date.today().isoformat()
        if self._personality._data.get("last_joke_day") == today:
            return
        self._personality._data["last_joke_day"] = today
        self._personality.save()
        sys_p = self._personality.get_system_prompt()
        prompt = "Tell me one short, clever programming joke. Max 2 sentences. Make it genuinely funny."
        model = self._settings.value("model", "claude-sonnet-4-6")
        self._joke_worker = ClaudeWorker(prompt, sys_p, model=model)
        self._joke_worker.response_ready.connect(lambda j: self._on_joke_ready(j))
        self._joke_worker.error_occurred.connect(lambda _: None)
        self._joke_worker.start()

    def _on_joke_ready(self, joke: str):
        self._char.set_state(State.DANCING)
        self._show_bubble(f"😄 {joke.strip()}", style=SPEECH, priority=BUBBLE_LOW)
        self._return_timer.start(8000)

    # ── Feature 13: Code detection in clipboard ───────────────────────────────

    def _is_code_snippet(self, text: str) -> bool:
        code_patterns = ["def ", "class ", "function ", "import ", "const ", "var ", "let ",
                         "public ", "private ", "return ", "#include", "SELECT ", "FROM "]
        return any(text.lstrip().startswith(p) or f"\n{p}" in text for p in code_patterns)

    # ── Feature 14: Breathing exercise ───────────────────────────────────────

    def _breathing_exercise(self):
        steps = [
            ("Breathing exercise 🌬️ Breathe IN... (4 seconds)", 4500),
            ("Hold your breath... (7 seconds)", 7500),
            ("Breathe OUT slowly... (8 seconds) 😮‍💨", 8500),
            ("Great! Repeat 3 times for best effect 🌟", 4000),
        ]
        def _step(i=0):
            if i >= len(steps):
                self._char.set_state(State.HAPPY)
                self._show_bubble("Done! How do you feel? 🌿", priority=BUBBLE_HIGH)
                self._return_timer.start(4000)
                return
            text, delay = steps[i]
            self._char.set_state(State.SLEEPING)
            self._show_bubble(text, style=THOUGHT, priority=BUBBLE_HIGH)
            QTimer.singleShot(delay, lambda: _step(i + 1))
        _step()

    # ── Feature 15: Skill tip of the day ─────────────────────────────────────

    def _fetch_skill_tip(self):
        today = date.today().isoformat()
        if self._personality._data.get("last_skill_tip_day") == today:
            return
        topics = self._personality._data.get("topics", [])
        if not topics:
            return
        topic = random.choice(topics[-5:])
        self._personality._data["last_skill_tip_day"] = today
        self._personality.save()
        sys_p = self._personality.get_system_prompt()
        prompt = f"Give one practical, actionable tip about {topic}. 1-2 sentences max. Make it immediately useful."
        model = self._settings.value("model", "claude-sonnet-4-6")
        self._skill_tip_worker = ClaudeWorker(prompt, sys_p, model=model)
        self._skill_tip_worker.response_ready.connect(lambda t: self._on_skill_tip(t))
        self._skill_tip_worker.error_occurred.connect(lambda _: None)
        self._skill_tip_worker.start()
        self._char.set_state(State.THINKING)

    def _on_skill_tip(self, tip: str):
        self._show_bubble(f"💡 Tip: {tip.strip()}", style=THOUGHT, priority=BUBBLE_LOW)
        self._return_timer.start(8000)

    # ── Feature 17: Session stats ────────────────────────────────────────────

    def _show_session_stats(self):
        interactions = self._personality._data.get("interactions", 0)
        streak = self._personality._data.get("streak", 0)
        uptime_min = int((time.time() - self._session_active_start) / 60)
        msg = f"📊 Stats: {interactions} total chats, {streak}-day streak, {uptime_min}min this session"
        self._char.set_state(State.HAPPY)
        self._show_bubble(msg, style=THOUGHT, priority=BUBBLE_HIGH)
        self._return_timer.start(6000)

    # ── Feature 20: Focus zone timer (custom interval) ───────────────────────

    def _start_focus_zone(self):
        minutes = self._personality._data.get("focus_zone_minutes", 25)
        self._char.set_state(State.THINKING)
        self._show_bubble(f"Focus zone: {minutes} min. You've got this! 🎯 I'll be quiet.", style=THOUGHT, priority=BUBBLE_HIGH)
        self._focus_mode = True
        self._idle_timer.stop()
        self._return_timer.start(3000)
        QTimer.singleShot(minutes * 60_000, self._focus_zone_done)

    def _focus_zone_done(self):
        self._focus_mode = False
        self._schedule_idle()
        self._char.set_state(State.DANCING)
        self._show_bubble("Focus zone complete! 🎉 Amazing work — take a break!", style=SHOUT, priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

    # ── Bookmarks ─────────────────────────────────────────────────────────────

    def _show_bookmarks(self):
        bookmarks = self._personality.get_bookmarks()
        if not bookmarks:
            self._show_bubble("No bookmarks yet! Use \"bookmark: URL\" in chat. 🔖", priority=BUBBLE_HIGH)
            return
        items = [f"{b.get('title', b['url'])}" for b in bookmarks[-10:]]
        item, ok = QInputDialog.getItem(None, "My Bookmarks 🔖", "Your saved links:", items, 0, False)
        if ok and item:
            idx = items.index(item)
            url = bookmarks[-(len(items)) + idx]["url"]
            subprocess.Popen(["xdg-open", url])

    # ── Pomodoro ──────────────────────────────────────────────────────────────

    def _start_pomodoro(self):
        if self._pomo_running:
            self._pomo_timer.stop()
            self._pomo_running = False
            self._show_bubble("Pomodoro cancelled. 🍅", priority=BUBBLE_HIGH)
            return
        self._pomo_running = True
        self._pomo_timer.start(25 * 60 * 1000)
        self._char.set_state(State.HAPPY)
        self._show_bubble("Pomodoro started! 🍅 25 min. You got this.", priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

    def _on_pomodoro_done(self):
        self._pomo_running = False
        self._char.set_state(State.DANCING)
        self._personality.log_mood("DANCING")
        self._show_bubble("Time's up! ⏰ Great work! Take a 5-min break 🍵", style=SHOUT, priority=BUBBLE_HIGH)
        self._return_timer.start(10_000)

    # ── Rock-Paper-Scissors ───────────────────────────────────────────────────

    def _play_rps(self):
        choices = ["Rock 🪨", "Scissors ✂️", "Paper 📄"]
        item, ok = QInputDialog.getItem(
            None, "Rock Paper Scissors!", "Pick your move:", choices, 0, False,
        )
        if not ok:
            return
        u = choices.index(item)
        p = random.randint(0, 2)
        if u == p:
            state, msg = State.THINKING, f"I also picked {choices[p]}! It's a tie 🤝"
        elif (u - p) % 3 == 1:
            state, msg = State.SLEEPING, f"I picked {choices[p]}... you win 😔 well played."
        else:
            state, msg = State.DANCING, f"I picked {choices[p]}! I win! 🎉 hehehe~"
        self._char.set_state(state)
        self._personality.log_mood(state.name)
        self._show_bubble(msg, style=SHOUT, priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

    # ── Trivia quiz ───────────────────────────────────────────────────────────

    def _play_trivia(self):
        if self._trivia_worker and self._trivia_worker.isRunning():
            self._show_bubble("Still thinking of a question! 🤔", priority=BUBBLE_HIGH)
            return
        self._char.set_state(State.THINKING)
        self._show_bubble("Let me think of a question... 🤔", style=THOUGHT, priority=BUBBLE_HIGH)
        wins, losses = self._trivia_score
        prompt = (
            "Ask me one trivia question. Pick any interesting topic. "
            "Format EXACTLY as:\nQUESTION: <question>\nANSWER: <short answer>"
        )
        self._trivia_worker = ClaudeWorker(
            prompt,
            f"You are a fun trivia host. Be concise. Score: {wins}W-{losses}L.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._trivia_worker.response_ready.connect(self._on_trivia_question)
        self._trivia_worker.error_occurred.connect(lambda _: self._go_idle())
        self._trivia_worker.start()

    def _on_trivia_question(self, response: str):
        # Parse QUESTION: / ANSWER: format
        lines = response.strip().splitlines()
        question, answer = "", ""
        for line in lines:
            if line.upper().startswith("QUESTION:"):
                question = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ANSWER:"):
                answer = line.split(":", 1)[1].strip()
        if not question or not answer:
            question = response.strip()
            answer = ""

        self._char.set_state(State.HAPPY)
        user_ans, ok = QInputDialog.getText(
            None, "Trivia! 🎯",
            question,
            QLineEdit.EchoMode.Normal,
        )
        if not ok:
            self._go_idle()
            return

        # Judge via Claude
        judge_prompt = (
            f"Trivia question: {question}\n"
            f"Correct answer: {answer}\n"
            f"User's answer: {user_ans}\n"
            "Is the user's answer correct or close enough? Reply with exactly one word: CORRECT or WRONG, "
            "then a brief fun comment in the same line."
        )
        self._trivia_worker = ClaudeWorker(
            judge_prompt,
            "You are a fair, fun trivia judge.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._trivia_worker.response_ready.connect(
            lambda r, a=answer: self._on_trivia_result(r, a)
        )
        self._trivia_worker.error_occurred.connect(lambda _: self._go_idle())
        self._trivia_worker.start()

    def _on_trivia_result(self, judgment: str, correct_answer: str):
        wins, losses = self._trivia_score
        if judgment.upper().startswith("CORRECT"):
            wins += 1
            state = State.DANCING
            style = SHOUT
        else:
            losses += 1
            state = State.THINKING
            style = SPEECH
        self._trivia_score = [wins, losses]
        self._char.set_state(state)
        self._personality.log_mood(state.name)
        score_line = f"\nScore: {wins}W–{losses}L"
        self._show_bubble(judgment.strip() + score_line, style=style, priority=BUBBLE_HIGH)
        self._return_timer.start(7000)

    # ── 20 Questions ──────────────────────────────────────────────────────────

    def _play_twenty_q(self):
        if self._twentyq_worker and self._twentyq_worker.isRunning():
            return
        self._char.set_state(State.THINKING)
        self._show_bubble("I'm thinking of something... ask me yes/no questions! (up to 20) 🤔",
                          style=THOUGHT, priority=BUBBLE_HIGH)
        self._twentyq_count = 0
        # Claude picks the secret
        self._twentyq_worker = ClaudeWorker(
            "Pick one concrete, well-known thing (animal, object, or person) for a 20-questions game. "
            "Reply with ONLY the thing you picked, nothing else.",
            "You are playing 20 questions. Keep your answer to one noun or name.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._twentyq_worker.response_ready.connect(self._on_twentyq_secret)
        self._twentyq_worker.error_occurred.connect(lambda _: self._go_idle())
        self._twentyq_worker.start()

    def _on_twentyq_secret(self, secret: str):
        self._twentyq_secret = secret.strip()
        self._return_timer.start(4000)
        QTimer.singleShot(4200, self._twentyq_next_question)

    def _twentyq_next_question(self):
        if not self._twentyq_secret:
            return
        remaining = 20 - self._twentyq_count
        q, ok = QInputDialog.getText(
            None,
            f"20 Questions ({remaining} left)",
            "Ask a yes/no question (or type your guess!):",
            QLineEdit.EchoMode.Normal,
        )
        if not ok or not q.strip():
            self._show_bubble("Game cancelled. Maybe next time! 👋", priority=BUBBLE_HIGH)
            self._twentyq_secret = ""
            self._return_timer.start(4000)
            return

        self._twentyq_count += 1

        # Check if it looks like a guess rather than a yes/no question
        is_guess = not q.strip().endswith("?") or any(
            w in q.lower() for w in ("is it", "is the answer", "i think it", "my guess")
        )

        self._char.set_state(State.THINKING)
        prompt = (
            f"The secret thing is: {self._twentyq_secret}\n"
            f"Player's {'guess' if is_guess else 'question'}: {q}\n"
            + (f"Reply YES, NO, or SOMETIMES with a brief hint if helpful."
               if not is_guess else
               f"Did the player guess correctly? Reply CORRECT! or WRONG followed by a short hint.")
        )
        self._twentyq_worker = ClaudeWorker(
            prompt,
            "You are the game host for 20 questions. Be fair and brief.",
            model=self._settings.value("model", "claude-sonnet-4-6"),
        )
        self._twentyq_worker.response_ready.connect(
            lambda r, guess=is_guess: self._on_twentyq_answer(r, guess)
        )
        self._twentyq_worker.error_occurred.connect(lambda _: self._go_idle())
        self._twentyq_worker.start()

    def _on_twentyq_answer(self, answer: str, was_guess: bool):
        answer_clean = answer.strip()
        correct_guess = was_guess and answer_clean.upper().startswith("CORRECT")
        out_of_q = self._twentyq_count >= 20

        if correct_guess:
            self._char.set_state(State.DANCING)
            self._show_bubble(f"{answer_clean} 🎉\nIt was: {self._twentyq_secret}!", style=SHOUT, priority=BUBBLE_HIGH)
            self._twentyq_secret = ""
            self._return_timer.start(8000)
        elif out_of_q:
            self._char.set_state(State.HAPPY)
            self._show_bubble(f"{answer_clean}\n20 questions up! It was: {self._twentyq_secret} 😄",
                              style=SHOUT, priority=BUBBLE_HIGH)
            self._twentyq_secret = ""
            self._return_timer.start(8000)
        else:
            self._char.set_state(State.THINKING)
            self._show_bubble(answer_clean, style=THOUGHT, priority=BUBBLE_HIGH)
            remaining = 20 - self._twentyq_count
            self._return_timer.start(4000)
            QTimer.singleShot(4200, self._twentyq_next_question)

    # ── Sticky notes ──────────────────────────────────────────────────────────

    def _show_notes(self):
        notes = self._personality.get_notes()
        if not notes:
            self._show_bubble("No notes yet! Start with \"remember: your note\" in chat. 📌", priority=BUBBLE_HIGH)
            self._return_timer.start(5000)
            return
        lines = "\n".join(f"• {n['text']}" for n in notes[-8:])
        QMessageBox.information(None, f"{self._personality.name}'s Notes 📌", lines)

    # ── Journal ───────────────────────────────────────────────────────────────

    def _write_journal(self):
        try:
            self._personality.write_journal_entry()
            self._personality.save()
        except Exception:
            log.error("Error writing journal entry", exc_info=True)

    # ── Second Pip ────────────────────────────────────────────────────────────

    def _spawn_second_pip(self):
        if self._second_pip and not self._second_pip.isHidden():
            if hasattr(self, "_cross_react_timer"):
                self._cross_react_timer.stop()
            self._second_pip.closeEvent = lambda e: e.accept()  # skip journal write for twin
            self._second_pip.close()
            self._second_pip = None
            self._show_bubble("See you later, other me! 👋", priority=BUBBLE_LOW)
            self._return_timer.start(3000)
            return
        self._second_pip = CompanionWindow(is_second=True)
        self._second_pip.show()
        self._char.set_state(State.DANCING)
        self._show_bubble("My twin is here! 🎉", style=SHOUT, priority=BUBBLE_NORMAL)
        self._return_timer.start(4000)
        # Occasional cross-reactions
        self._cross_react_timer = QTimer(self)
        self._cross_react_timer.timeout.connect(self._cross_react)
        self._cross_react_timer.start(random.randint(20, 40) * 1000)

    def _cross_react(self):
        if not self._second_pip or self._second_pip.isHidden():
            self._cross_react_timer.stop()
            return
        if random.random() < 0.5:
            self._char.set_state(State.WAVING)
            self._show_bubble(random.choice(["👋", "hey other me!", "♪~", "*waves*"]), priority=BUBBLE_LOW)
            self._return_timer.start(3000)
        else:
            self._second_pip._char.set_state(State.WAVING)
            self._second_pip._show_bubble(random.choice(["hi!!", "♪", "*waves back*", "hehe~"]))
            self._second_pip._return_timer.start(3000)
        self._cross_react_timer.start(random.randint(20, 40) * 1000)

    # ── Bubble ────────────────────────────────────────────────────────────────

    def _show_bubble(self, text: str, style: str = SPEECH,
                     priority: int = BUBBLE_NORMAL, interactive: bool = False):
        if self._minimized:
            return
        if not self._bubble.isVisible():
            self._show_bubble_now(text, style, interactive=interactive)
            return
        if priority == BUBBLE_LOW:
            return  # ambient chatter — don't interrupt or queue
        # Queue: insert in priority order (highest first), cap at 3 items
        self._bubble_queue.append((priority, text, style, interactive))
        self._bubble_queue.sort(key=lambda x: x[0], reverse=True)
        if len(self._bubble_queue) > 3:
            self._bubble_queue.pop()  # drop the lowest-priority tail

    def _show_bubble_now(self, text: str, style: str, interactive: bool = False):
        words = len(text.split())
        _log_bub.info("Bubble shown (style=%s, words=%d)", style, words)
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        duration_ms = max(6000, words * 300)
        self._bubble.show_text(text, anchor, duration_ms, style=style, interactive=interactive)

    def _drain_bubble_queue(self):
        if self._minimized or not self._bubble_queue:
            return
        entry = self._bubble_queue.pop(0)
        # Support old 3-tuple entries and new 4-tuple entries
        if len(entry) == 4:
            _, text, style, interactive = entry
        else:
            _, text, style = entry
            interactive = False
        self._show_bubble_now(text, style, interactive=interactive)
        # For interactive bubbles in the queue, idle return happens on close
        if interactive:
            self._return_timer.stop()

    # ── System tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        icon = self._make_tray_icon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(f"{self._personality.name} — your AI companion")
        tray_menu = QMenu()
        tray_menu.addAction("Open Pip", self._toggle_minimize)
        tray_menu.addAction("Control Panel", self._open_panel)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", QApplication.quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _make_tray_icon(self):
        from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor
        px = QPixmap(22, 22)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#7860d4"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 18, 18)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(7, 7, 4, 4)
        p.drawEllipse(13, 7, 4, 4)
        p.end()
        return QIcon(px)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_minimize()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _show_menu(self, pos: QPoint):
        _menu_ss = """
            QMenu {
                background: #1a1625;
                border: 1px solid #2d2540;
                border-radius: 8px;
                padding: 4px;
                color: #c0b0d8;
                font-size: 13px;
            }
            QMenu::item {
                padding: 7px 16px 7px 8px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #2d2540;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #2d2540;
                margin: 3px 8px;
            }
            QMenu::icon {
                padding-left: 6px;
            }
        """

        menu = QMenu()
        menu.setStyleSheet(_menu_ss)

        # ── Chat with Pip ─────────────────────────────────────────────────────
        act = menu.addAction(_icon_chat(), f"Chat with {self._personality.name}")
        act.triggered.connect(self._open_chat)
        menu.addSeparator()

        # ── Games & Fun submenu ───────────────────────────────────────────────
        games_menu = QMenu("Games & Fun", menu)
        games_menu.setIcon(_icon_gamepad())
        games_menu.setStyleSheet(_menu_ss)

        act = games_menu.addAction(_icon_target(), "Trivia Quiz")
        act.triggered.connect(self._play_trivia)

        act = games_menu.addAction(_icon_gamepad(), "20 Questions")
        act.triggered.connect(self._play_twenty_q)

        act = games_menu.addAction(_icon_scissors(), "Rock Paper Scissors")
        act.triggered.connect(self._play_rps)

        act = games_menu.addAction(_icon_wind(), "Breathing Exercise")
        act.triggered.connect(self._breathing_exercise)

        twin_label = "Dismiss Twin" if (self._second_pip and not self._second_pip.isHidden()) else "Summon Twin"
        act = games_menu.addAction(_icon_users(), twin_label)
        act.triggered.connect(self._spawn_second_pip)

        menu.addMenu(games_menu)

        # ── Focus & Wellness submenu ──────────────────────────────────────────
        focus_menu = QMenu("Focus & Wellness", menu)
        focus_menu.setIcon(_icon_timer())
        focus_menu.setStyleSheet(_menu_ss)

        pomo_label = "Stop Pomodoro" if self._pomo_running else "Start Pomodoro"
        act = focus_menu.addAction(_icon_timer(), pomo_label)
        act.triggered.connect(self._start_pomodoro)

        focus_act = focus_menu.addAction(_icon_target(), "Focus Mode")
        focus_act.setCheckable(True)
        focus_act.setChecked(self._focus_mode)
        focus_act.triggered.connect(self._toggle_focus_mode)

        act = focus_menu.addAction(_icon_timer(), "Focus Zone Timer")
        act.triggered.connect(self._start_focus_zone)

        hydration_enabled = self._personality._data.get("hydration_enabled", True)
        hydration_act = focus_menu.addAction(_icon_wind(), "Hydration Reminder")
        hydration_act.setCheckable(True)
        hydration_act.setChecked(hydration_enabled)
        hydration_act.triggered.connect(self._toggle_hydration)

        menu.addMenu(focus_menu)

        # ── Info & Stats submenu ──────────────────────────────────────────────
        info_menu = QMenu("Info & Stats", menu)
        info_menu.setIcon(_icon_bar_chart())
        info_menu.setStyleSheet(_menu_ss)

        act = info_menu.addAction(_icon_target(), "What am I doing?")
        act.triggered.connect(self._what_am_i_doing)

        act = info_menu.addAction(_icon_bar_chart(), "Today's Stats")
        act.triggered.connect(self._show_session_stats)

        notes = self._personality.get_notes()
        notes_label = f"My Notes  ({len(notes)})" if notes else "My Notes"
        act = info_menu.addAction(_icon_clipboard(), notes_label)
        act.triggered.connect(self._show_notes)

        bookmarks = self._personality.get_bookmarks() if hasattr(self._personality, 'get_bookmarks') else []
        bm_label = f"My Bookmarks  ({len(bookmarks)})" if bookmarks else "My Bookmarks"
        act = info_menu.addAction(_icon_bookmark(), bm_label)
        act.triggered.connect(self._show_bookmarks)

        menu.addMenu(info_menu)

        menu.addSeparator()

        # ── Control Panel ─────────────────────────────────────────────────────
        act = menu.addAction(_icon_sliders(), "Control Panel")
        act.triggered.connect(self._open_panel)

        menu.addSeparator()

        # ── Quit ──────────────────────────────────────────────────────────────
        act = menu.addAction(_icon_exit("#d46080"), "Quit")
        act.triggered.connect(QApplication.quit)

        menu.exec(pos)

    def _toggle_hydration(self, checked: bool):
        self._personality._data["hydration_enabled"] = checked
        self._personality.save()
        self._update_hydration_timer()

    def _clear_history(self):
        self._history.clear()
        self._pending_user_msg = ""
        if self._worker and self._worker.isRunning():
            self._worker.response_ready.disconnect()
            self._worker.error_occurred.disconnect()
            self._worker.quit()
            self._worker.wait(500)
        self._worker = None
        self._show_bubble("Memory cleared! Fresh start. 🧹", priority=BUBBLE_HIGH)

    def _open_panel(self):
        if self._panel is None or not self._panel.isVisible() and not self._panel.isHidden():
            self._panel = None
        if self._panel is None:
            self._panel = ControlPanel(self._personality, self._settings, MCP_CONFIG,
                                       gcal=self._gcal)
            self._panel.settings_changed.connect(self._on_settings_changed)
            self._panel.breathing_requested.connect(self._breathing_exercise)
            self._panel.calendar_status_changed.connect(self._on_calendar_status_changed)
            self._panel.destroyed.connect(lambda: setattr(self, "_panel", None))
        self._panel.refresh()
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def _on_settings_changed(self):
        self._idle_timer.stop()
        self._schedule_idle()
        self._update_hydration_timer()
        if self._personality._data.get("eyestrain_enabled", True):
            if not self._eyestrain_timer.isActive():
                self._eyestrain_timer.start(20 * 60_000)
        else:
            self._eyestrain_timer.stop()
        focus_mode_new = self._personality._data.get("focus_mode", False)
        if not focus_mode_new and self._focus_mode:
            self._focus_mode = False
            self._schedule_idle()
        # Deep screen watcher toggle
        deep_watch = self._settings.value("deep_watch", False, type=bool)
        if deep_watch and not self._deep_watch_timer.isActive():
            self._deep_watch_timer.start(3 * 60_000)
            self._show_bubble(
                "Deep screen watcher ON! I'll keep an eye on what you're up to. 👁️",
                style=THOUGHT, priority=BUBBLE_HIGH,
            )
            self._return_timer.start(5000)
        elif not deep_watch and self._deep_watch_timer.isActive():
            self._deep_watch_timer.stop()
        # Wander mode toggle
        wander = self._settings.value("wander_mode", False, type=bool)
        if wander and not self._wander_timer.isActive():
            self._wander_timer.start(random.randint(300, 480) * 1000)
            self._show_bubble("Wander mode ON! I'll stretch my legs sometimes. 🐾",
                              style=THOUGHT, priority=BUBBLE_HIGH)
            self._return_timer.start(4000)
        elif not wander:
            self._wander_timer.stop()
            if self._wander_anim is not None:
                self._wander_anim.stop()

    def _rename(self):
        name, ok = QInputDialog.getText(
            None, "Rename", "New name:",
            QLineEdit.EchoMode.Normal,
            self._personality.name,
        )
        if ok and name.strip():
            self._personality.name = name.strip()

    # ── Deep Screen Watcher ───────────────────────────────────────────────────

    # Code editor detection: filename extensions that trigger a tip
    _CODE_EDITORS = ("code", "vscode", "vim", "nvim", "nano", "gedit",
                     "pycharm", "emacs", "sublime", "kate", "neovide",
                     "vscodium", "atom", "lapce")
    _CODE_EXTENSIONS = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C",
        ".java": "Java", ".rb": "Ruby", ".php": "PHP",
        ".swift": "Swift", ".kt": "Kotlin", ".cs": "C#",
        ".jsx": "React (JSX)", ".tsx": "React (TSX)",
    }
    # Context keys for web-search cooldown (fires at most once per 30 min each)
    _WEB_SEARCH_CONTEXTS = {
        "stack overflow": "Stack Overflow",
        "github": "GitHub",
        "react":  "React",
        "django": "Django",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "nginx": "Nginx",
        "vim": "Vim",
        "nvim": "Neovim",
        "rust": "Rust",
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
    }

    def _prompt_deep_watch_enable(self):
        """One-time first-launch invite to enable deep screen watcher."""
        if self._settings.value("deep_watch", False, type=bool):
            return
        self._char.set_state(State.WAVING)
        self._show_bubble(
            "Psst — want me to watch what you're working on and give you tips? "
            "Enable 'Deep screen watcher' in Control Panel → Settings! 👁️",
            style=THOUGHT, priority=BUBBLE_NORMAL,
        )
        self._return_timer.start(10000)

    def _get_active_window_title(self) -> str:
        """Synchronously fetch the active window title (call from bg thread only)."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _deep_watch_tick(self):
        """Fired every 3 minutes when deep_watch is enabled. Runs all deep-watch checks."""
        if self._focus_mode or self._minimized:
            return
        if self._watch_worker and self._watch_worker.isRunning():
            return   # previous call still in flight
        threading.Thread(target=self._deep_watch_tick_bg, daemon=True).start()

    def _deep_watch_tick_bg(self):
        """Background thread: gather window title, dispatch checks via QTimer."""
        title = self._get_active_window_title()
        if not title:
            return
        now = time.time()

        # Record window in recent-windows deque (for juggling detection)
        QTimer.singleShot(0, lambda t=title, ts=now: self._record_window(t, ts))

        title_lower = title.lower()

        # --- Check 1: same-window for >45 minutes ---
        QTimer.singleShot(0, lambda t=title, ts=now: self._maybe_alert_long_session(t, ts))

        # --- Check 2: code file detection ---
        for ext, lang in self._CODE_EXTENSIONS.items():
            if ext in title_lower:
                # Extract filename: last token before " -" or end
                filename = title.split(" - ")[0].strip() if " - " in title else title.split("/")[-1]
                QTimer.singleShot(
                    random.randint(2 * 60_000, 5 * 60_000),
                    lambda fn=filename, l=lang: self._deep_watch_code_tip(fn, l),
                )
                break

        # --- Check 3: web search optimization for recognized context ---
        for keyword, context in self._WEB_SEARCH_CONTEXTS.items():
            if keyword in title_lower:
                last = self._last_web_search_times.get(context, 0)
                if now - last > 30 * 60:   # at most once per 30 min
                    self._last_web_search_times[context] = now
                    QTimer.singleShot(5000, lambda c=context: self._deep_watch_web_tip(c))
                break

    def _record_window(self, title: str, ts: float):
        """Record window visit; check for juggling pattern."""
        self._recent_windows.append((ts, title))
        self._check_juggling()

    def _check_juggling(self):
        """If user switched between >5 distinct apps in <3 minutes, comment."""
        if len(self._recent_windows) < 6:
            return
        oldest_ts = self._recent_windows[0][0]
        newest_ts = self._recent_windows[-1][0]
        if newest_ts - oldest_ts > 3 * 60:
            return  # spread over more than 3 min — not juggling
        titles = {t for _, t in self._recent_windows}
        if len(titles) >= 5:
            self._recent_windows.clear()   # reset to avoid repeat
            if self._char.state in (State.IDLE, State.HAPPY):
                self._char.set_state(State.THINKING)
                self._show_bubble(
                    "You're juggling a lot right now — want to focus on one thing? 🧘",
                    style=SPEECH, priority=BUBBLE_NORMAL,
                )
                self._return_timer.start(7000)

    def _maybe_alert_long_session(self, title: str, now: float):
        """Alert if user has been on the same window for >45 minutes."""
        if title != self._last_same_window_name:
            self._last_same_window_name  = title
            self._last_same_window_start = now
            self._last_same_window_alerted = False
            return
        elapsed_min = (now - self._last_same_window_start) / 60
        if elapsed_min >= 45 and not self._last_same_window_alerted:
            self._last_same_window_alerted = True
            app_name = title.split(" - ")[-1].strip() if " - " in title else title[:30]
            self._char.set_state(State.WAVING)
            self._show_bubble(
                f"You've been deep in {app_name} for 45 minutes. How's it going? ☕",
                style=SPEECH, priority=BUBBLE_NORMAL,
            )
            self._return_timer.start(7000)

    def _deep_watch_code_tip(self, filename: str, language: str):
        """Fetch a language-specific tip via Claude and show it as a thought bubble."""
        if self._watch_worker and self._watch_worker.isRunning():
            return
        if not self._settings.value("deep_watch", False, type=bool):
            return
        self._char.set_state(State.THINKING)
        prompt = (
            f"The user is editing {filename} ({language}). "
            f"Suggest one specific optimization, tip, or best practice relevant to {language}. "
            f"Keep it to 2 sentences. Be practical and direct."
        )
        model = self._settings.value("model", "claude-sonnet-4-6")
        self._watch_worker = ClaudeWorker(
            prompt,
            "You are a helpful coding assistant. Be concise and specific.",
            model=model,
        )
        self._watch_worker.response_ready.connect(
            lambda tip: self._on_watch_tip(f"💻 [{language}] {tip.strip()}")
        )
        self._watch_worker.error_occurred.connect(lambda _: None)
        self._watch_worker.start()

    def _deep_watch_web_tip(self, context: str):
        """Use WebSearch to find a fresh optimization tip for the current context."""
        if self._watch_worker and self._watch_worker.isRunning():
            return
        if not self._settings.value("deep_watch", False, type=bool):
            return
        self._char.set_state(State.THINKING)
        prompt = (
            f"Search for 'latest {context} optimization tips 2025' and surface the single most "
            f"practical, actionable tip you find. Keep it to 2 sentences. Be specific."
        )
        model = self._settings.value("model", "claude-sonnet-4-6")
        self._watch_worker = ClaudeWorker(
            prompt,
            "You are a helpful assistant surfacing practical dev tips. Be concise.",
            model=model,
            allowed_tools="WebSearch,WebFetch",
        )
        self._watch_worker.response_ready.connect(
            lambda tip: self._on_watch_tip(f"🌐 [{context}] {tip.strip()}")
        )
        self._watch_worker.error_occurred.connect(lambda _: None)
        self._watch_worker.start()

    def _on_watch_tip(self, tip: str):
        """Display a deep-watch tip in a thought bubble."""
        if self._char.state not in (State.THINKING, State.IDLE, State.HAPPY):
            return
        self._char.set_state(State.THINKING)
        self._personality.log_mood("THINKING")
        self._show_bubble(tip, style=THOUGHT, priority=BUBBLE_NORMAL)
        self._return_timer.start(max(8000, len(tip.split()) * 350))

    def _what_am_i_doing(self):
        """Right-click 'What am I doing?' — immediate one-sentence summary."""
        if self._what_doing_worker and self._what_doing_worker.isRunning():
            self._show_bubble("Still figuring it out... 🤔", priority=BUBBLE_HIGH)
            return
        self._char.set_state(State.THINKING)
        threading.Thread(target=self._what_am_i_doing_bg, daemon=True).start()

    def _what_am_i_doing_bg(self):
        title = self._get_active_window_title()
        if not title:
            QTimer.singleShot(0, lambda: self._show_bubble(
                "I can't see your active window right now 🤷",
                priority=BUBBLE_HIGH,
            ))
            return
        prompt = (
            f"The user's active window title is: \"{title}\". "
            f"In exactly one sentence, describe what they are most likely working on or doing. "
            f"Be specific and friendly."
        )
        model = self._settings.value("model", "claude-sonnet-4-6")
        QTimer.singleShot(0, lambda p=prompt, m=model: self._launch_what_doing(p, m))

    def _launch_what_doing(self, prompt: str, model: str):
        self._what_doing_worker = ClaudeWorker(
            prompt,
            "You are Pip, a helpful desktop companion. Reply with one friendly sentence.",
            model=model,
        )
        self._what_doing_worker.response_ready.connect(self._on_what_doing_ready)
        self._what_doing_worker.error_occurred.connect(
            lambda e: self._show_bubble(f"Oops! {e}", priority=BUBBLE_HIGH)
        )
        self._what_doing_worker.start()

    def _on_what_doing_ready(self, summary: str):
        self._char.set_state(State.THINKING)
        self._show_bubble(f"🔍 {summary.strip()}", style=THOUGHT, priority=BUBBLE_HIGH)
        self._return_timer.start(7000)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("pip-companion")
    app.setQuitOnLastWindowClosed(False)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT,  lambda *_: app.quit())
    window = CompanionWindow()
    app.aboutToQuit.connect(window._write_journal)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
