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
import signal
import subprocess
import sys
import sys as _sys
import threading
import time
from datetime import datetime, date

from PyQt6.QtWidgets import QApplication, QWidget, QInputDialog, QMenu, QLineEdit, QMessageBox
from PyQt6.QtCore import Qt, QPoint, QTimer, QSettings
from PyQt6.QtGui import QPainter


VERSION = "1.0.0"

log = logging.getLogger(__name__)


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
from control_panel import ControlPanel

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
}

RESPONSE_MOOD_TRIGGERS: dict[State, list[str]] = {
    State.HAPPY:    ["!", "haha", "great", "awesome", "yay", "love",
                     "exciting", "wonderful", "amazing"],
    State.DANCING:  ["♪", "dance", "music", "party"],
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
        self._worker: ClaudeWorker | None       = None
        self._haiku_worker: ClaudeWorker | None = None
        self._trivia_worker: ClaudeWorker | None = None
        self._twentyq_worker: ClaudeWorker | None = None
        self._drag_pos: QPoint | None    = None
        self._press_global: QPoint       = QPoint()
        self._is_dragging: bool          = False
        self._panel: ControlPanel | None = None
        self._second_pip: "CompanionWindow | None" = None

        self._history: list[tuple[str, str]] = []
        self._pending_user_msg: str = ""

        # Trivia / 20Q game state
        self._trivia_score: list[int] = [0, 0]   # [wins, losses]
        self._twentyq_secret: str = ""
        self._twentyq_count: int  = 0

        self.setFixedSize(self._char.canvas_w, self._char.canvas_h)
        self._bubble = BubbleWindow()
        self._bubble_queue: list[tuple[int, str, str]] = []   # (priority, text, style)
        self._bubble.bubble_closed.connect(self._drain_bubble_queue)

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

        self._music_timer = QTimer(self)
        self._music_timer.timeout.connect(self._check_music)
        self._music_timer.start(45_000)
        self._last_music_title: str       = ""
        self._song_fact_worker: ClaudeWorker | None = None
        self._last_song_fact_time: float  = 0.0   # epoch; enforces 10-min gap

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._check_stats)
        self._stats_timer.start(5 * 60_000)   # every 5 min

        # ── Weather (once per session) ────────────────────────────────────────
        self._weather_fetched = False
        QTimer.singleShot(8_000, self._fetch_weather)

        # ── Startup greeting ─────────────────────────────────────────────────
        if not is_second:
            QTimer.singleShot(1200, self._greet)
            QTimer.singleShot(3_000, self._check_daily_events)
        else:
            QTimer.singleShot(1200, self._second_pip_greet)

        model = self._settings.value("model", "claude-sonnet-4-6")
        log.info("Pip session started — version %s, model %s", VERSION, model)

    # ── Always-on-top + minimize ──────────────────────────────────────────────

    def _toggle_minimize(self):
        self._minimized = not self._minimized
        if self._minimized:
            self._bubble.hide()
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
            self._personality.save()
        except Exception:
            log.error("Error saving personality on close", exc_info=True)
        for timer in (
            self._anim_timer, self._idle_timer, self._return_timer,
            self._click_timer, self._dream_timer, self._typing_check,
            self._pomo_timer, self._window_timer, self._music_timer,
            self._stats_timer, self._hydration_timer, self._eyestrain_timer,
        ):
            timer.stop()
        if hasattr(self, "_kb_listener") and self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
        log.info("Session ended cleanly")
        event.accept()

    # ── Animation ─────────────────────────────────────────────────────────────

    def _tick(self):
        self._anim_counter = (self._anim_counter + 1) % 4
        if self._char.state != State.IDLE or self._anim_counter == 0:
            self._char.next_frame()
        self._char.tick_color()
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
            self._char.draw(p)

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
        text, ok = QInputDialog.getText(
            None, f"Talk to {self._personality.name}",
            "Say something:",
            QLineEdit.EchoMode.Normal,
            prefill,
        )
        if not ok or not text.strip():
            return

        user_text = text.strip()

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

        log.info("Claude call started: %r", user_text[:80])
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
        self._worker.start()

        self._personality.after_interaction(user_text)

    def _on_response(self, response: str):
        elapsed = time.time() - getattr(self, "_call_start", time.time())
        log.info("Claude response received in %.1fs", elapsed)
        if self._pending_user_msg:
            self._history.append(("user", self._pending_user_msg))
            self._history.append(("assistant", response))
            self._pending_user_msg = ""
            if len(self._history) > MAX_HISTORY_TURNS * 2:
                self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        resp_mood = _detect_response_mood(response)
        final_state = resp_mood if resp_mood else State.TALKING
        self._char.set_state(final_state)
        self._personality.log_mood(final_state.name)
        self._show_bubble(response, priority=BUBBLE_HIGH)
        bubble_ms = max(6000, len(response.split()) * 300)
        self._return_timer.start(bubble_ms + 500)
        QTimer.singleShot(1000, self._check_achievements)

    def _on_error(self, msg: str):
        self._pending_user_msg = ""
        self._char.set_state(State.IDLE)
        self._show_bubble(f"Oops! {msg}", priority=BUBBLE_HIGH)
        self._return_timer.start(5000)

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
        text = QApplication.instance().clipboard().text().strip()
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
                with self._keypress_lock:
                    self._last_keypress = time.time()
            self._kb_listener = keyboard.Listener(on_press=_on_press, daemon=True)
            self._kb_listener.start()
        except Exception:
            self._kb_listener = None

    def _check_typing_idle(self):
        if self._char.state in (State.SLEEPING, State.THINKING, State.TALKING):
            return
        now = time.time()
        with self._keypress_lock:
            last = self._last_keypress
        idle_min = (now - last) / 60

        # 20-min typing idle check
        if idle_min >= 20:
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

        # 2-hour screen-time nudge
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
            msg = self._personality.time_quip()
        else:
            self._char.set_state(State.HAPPY)
            msg = random.choice([
                "Hey, back already! 👋", "Miss me? 😊",
                "Welcome back~", "Oh, you're back!",
            ])

        self._personality.log_mood("HAPPY")
        self._show_bubble(msg, priority=BUBBLE_NORMAL)
        self._return_timer.start(6000)

        if not self._personality._data.get("profile_complete", False):
            QTimer.singleShot(5000, self._run_profile_questionnaire)

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
            ["quip", "dance", "sleep", "happy", "think", "time_greet", "haiku"],
            weights=[28, 18, 13, 16, 9, 6, 10],
        )[0]

        log.info("Idle event: %s", ev)

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
        self._char.set_state(State.IDLE)

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
        worker = ClaudeWorker(prompt, sys_p, model=model)
        worker.response_ready.connect(lambda f: self._on_interest_fact(f))
        worker.error_occurred.connect(lambda _: None)
        worker.start()
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
                pass
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
        worker = ClaudeWorker(prompt, sys_p, model=model)
        worker.response_ready.connect(lambda j: self._on_joke_ready(j))
        worker.error_occurred.connect(lambda _: None)
        worker.start()

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
        worker = ClaudeWorker(prompt, sys_p, model=model)
        worker.response_ready.connect(lambda t: self._on_skill_tip(t))
        worker.error_occurred.connect(lambda _: None)
        worker.start()
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
            pass

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
                     priority: int = BUBBLE_NORMAL):
        if self._minimized:
            return
        if not self._bubble.isVisible():
            self._show_bubble_now(text, style)
            return
        if priority == BUBBLE_LOW:
            return  # ambient chatter — don't interrupt or queue
        # Queue: insert in priority order (highest first), cap at 3 items
        self._bubble_queue.append((priority, text, style))
        self._bubble_queue.sort(key=lambda x: x[0], reverse=True)
        if len(self._bubble_queue) > 3:
            self._bubble_queue.pop()  # drop the lowest-priority tail

    def _show_bubble_now(self, text: str, style: str):
        log.info("Bubble shown: style=%s len=%d", style, len(text))
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        words = len(text.split())
        duration_ms = max(6000, words * 300)
        self._bubble.show_text(text, anchor, duration_ms, style=style)

    def _drain_bubble_queue(self):
        if self._minimized or not self._bubble_queue:
            return
        _, text, style = self._bubble_queue.pop(0)
        self._show_bubble_now(text, style)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _show_menu(self, pos: QPoint):
        menu = QMenu()
        menu.addAction(f"Chat with {self._personality.name}", self._open_chat)
        menu.addAction("Control Panel", self._open_panel)
        menu.addSeparator()

        pomo_label = "Stop Pomodoro ⏹" if self._pomo_running else "Start Pomodoro 🍅"
        menu.addAction(pomo_label, self._start_pomodoro)
        menu.addAction("Rock Paper Scissors 🪨", self._play_rps)
        menu.addAction("Trivia Quiz 🎯", self._play_trivia)
        menu.addAction("20 Questions 🔍", self._play_twenty_q)
        menu.addSeparator()

        notes = self._personality.get_notes()
        notes_label = f"My Notes 📌 ({len(notes)})" if notes else "My Notes 📌 (empty)"
        menu.addAction(notes_label, self._show_notes)

        twin_label = "Dismiss Twin 👋" if (self._second_pip and not self._second_pip.isHidden()) else "Summon Twin 👯"
        menu.addAction(twin_label, self._spawn_second_pip)
        menu.addSeparator()

        history_label = (f"Clear History  ({len(self._history) // 2} turns)"
                         if self._history else "Clear History  (empty)")
        clear_action = menu.addAction(history_label)
        clear_action.setEnabled(bool(self._history))
        clear_action.triggered.connect(self._clear_history)
        menu.addSeparator()

        menu.addSeparator()
        focus_label = "🔇 Stop Focus Mode" if self._focus_mode else "🎯 Focus Mode"
        menu.addAction(focus_label, self._toggle_focus_mode)
        menu.addAction("🎯 Focus Zone Timer", self._start_focus_zone)
        menu.addAction("🌬️ Breathing Exercise", self._breathing_exercise)
        menu.addAction("📊 Today's Stats", self._show_session_stats)
        bookmarks = self._personality.get_bookmarks() if hasattr(self._personality, 'get_bookmarks') else []
        if bookmarks:
            menu.addAction(f"🔖 My Bookmarks ({len(bookmarks)})", self._show_bookmarks)

        menu.addAction("Rename", self._rename)
        menu.addAction("Quit", QApplication.quit)
        menu.exec(pos)

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
            self._panel = ControlPanel(self._personality, self._settings, MCP_CONFIG)
            self._panel.settings_changed.connect(self._on_settings_changed)
            self._panel.breathing_requested.connect(self._breathing_exercise)
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

    def _rename(self):
        name, ok = QInputDialog.getText(
            None, "Rename", "New name:",
            QLineEdit.EchoMode.Normal,
            self._personality.name,
        )
        if ok and name.strip():
            self._personality.name = name.strip()


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
