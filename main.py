"""
Pip — pixel-art desktop companion for Linux.

Left-click  : open chat
Right-click : menu  →  Control Panel / Rename / Quit
Drag        : move Pip around the screen
"""

import ctypes
import ctypes.util
import os
import random
import subprocess
import sys
import threading
import time
from datetime import datetime, date

from PyQt6.QtWidgets import QApplication, QWidget, QInputDialog, QMenu, QLineEdit
from PyQt6.QtCore import Qt, QPoint, QTimer, QSettings
from PyQt6.QtGui import QPainter


def _suppress_gtk_warnings():
    """
    Silence harmless GTK CSS theme warnings like:
      Gtk-WARNING **: Theme parsing error: gtk.css:N: 'border-spacing' is not a valid property
    These come from the system GTK theme using CSS properties not supported by
    the installed GTK version — they are cosmetic noise, not errors.
    We install a no-op GLib log handler for the 'Gtk' domain at WARNING level.
    The callback is stored on the function to prevent GC.
    """
    try:
        glib = ctypes.CDLL("libglib-2.0.so.0")
        G_LOG_LEVEL_WARNING = 1 << 4
        handler_t = ctypes.CFUNCTYPE(
            None,                 # return void
            ctypes.c_char_p,      # log_domain
            ctypes.c_int,         # log_level
            ctypes.c_char_p,      # message
            ctypes.c_void_p,      # user_data
        )
        _suppress_gtk_warnings._cb = handler_t(lambda *_: None)
        glib.g_log_set_handler(
            b"Gtk",
            G_LOG_LEVEL_WARNING,
            _suppress_gtk_warnings._cb,
            None,
        )
    except Exception:
        pass   # non-Linux or glib not found — silently skip


_suppress_gtk_warnings()  # must run before QApplication()

from character import CharacterRenderer, State
from personality import Personality
from claude_client import ClaudeWorker
from bubble import BubbleWindow
from control_panel import ControlPanel

if getattr(sys, "frozen", False):
    _CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "pip-companion")
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    MCP_CONFIG = os.path.join(_CONFIG_DIR, "mcp_config.json")
else:
    MCP_CONFIG = os.path.join(os.path.dirname(__file__), "mcp_config.json")

# ── Mood reaction tables ───────────────────────────────────────────────────────
# Maps animation state → trigger words/phrases scanned in user input.
# First match wins; order of the outer dict sets priority.
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

# Words in *Claude's* reply that trigger a mood override on top of TALKING.
RESPONSE_MOOD_TRIGGERS: dict[State, list[str]] = {
    State.HAPPY:    ["!", "haha", "great", "awesome", "yay", "love",
                     "exciting", "wonderful", "amazing"],
    State.DANCING:  ["♪", "dance", "music", "party"],
}

# How many turns (user + assistant pairs) to keep in session history.
MAX_HISTORY_TURNS = 3   # = 6 messages


def _detect_mood(text: str) -> State | None:
    """Return the first matching mood state for *text*, or None."""
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
    def __init__(self):
        super().__init__()

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool               # no taskbar entry
        )
        # ARGB visual — must be set before show()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)

        # ── Core objects ──────────────────────────────────────────────────────
        self._personality = Personality()
        self._settings    = QSettings("companion", "pip")
        self._char        = CharacterRenderer()
        self._worker: ClaudeWorker | None = None
        self._drag_pos: QPoint | None = None
        self._press_global: QPoint = QPoint()
        self._is_dragging: bool = False
        self._panel: ControlPanel | None = None

        # Session conversation history — list of ("user"|"assistant", text).
        # Capped at MAX_HISTORY_TURNS pairs; cleared when Pip quits or user
        # chooses "Clear History" from the menu.
        self._history: list[tuple[str, str]] = []
        self._pending_user_msg: str = ""   # stored until response arrives

        self.setFixedSize(self._char.canvas_w, self._char.canvas_h)

        # Speech bubble is a separate top-level window (avoids child-widget opacity issues)
        self._bubble = BubbleWindow()

        # ── Position ──────────────────────────────────────────────────────────
        screen = QApplication.primaryScreen().geometry()
        self.move(
            self._settings.value("x", screen.width()  - self._char.canvas_w - 40, type=int),
            self._settings.value("y", screen.height() - self._char.canvas_h - 60, type=int),
        )

        # ── Animation timer ───────────────────────────────────────────────────
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(130)

        # ── Random idle event timer ───────────────────────────────────────────
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._random_event)
        self._schedule_idle()

        # ── Return-to-idle timer ──────────────────────────────────────────────
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._go_idle)

        # ── Double-click guard (delays open_chat to allow pet detection) ──────
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._click_timer.timeout.connect(self._open_chat)

        # ── Clipboard watcher ────────────────────────────────────────────────
        self._clipboard_pending: str = ""
        self._last_clipboard: str = ""
        QApplication.instance().clipboard().dataChanged.connect(self._on_clipboard_change)

        # ── Typing-aware idle ────────────────────────────────────────────────
        self._last_keypress: float = time.time()
        self._keypress_lock = threading.Lock()
        self._typing_check = QTimer(self)
        self._typing_check.timeout.connect(self._check_typing_idle)
        self._typing_check.start(60_000)
        self._start_kb_listener()

        # ── Animation frame counter (for slowing IDLE) ───────────────────────
        self._anim_counter: int = 0

        # ── Pomodoro timer ───────────────────────────────────────────────────
        self._pomo_running: bool = False
        self._pomo_timer = QTimer(self)
        self._pomo_timer.setSingleShot(True)
        self._pomo_timer.timeout.connect(self._on_pomodoro_done)

        # ── Active window watcher ────────────────────────────────────────────
        self._window_timer = QTimer(self)
        self._window_timer.timeout.connect(self._check_active_window)
        self._window_timer.start(30_000)

        # ── Startup greeting ─────────────────────────────────────────────────
        QTimer.singleShot(1200, self._greet)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _tick(self):
        self._anim_counter = (self._anim_counter + 1) % 4
        if self._char.state != State.IDLE or self._anim_counter == 0:
            self._char.next_frame()
        self._char.tick_color()
        self.update()

    # ── Paint (transparency-safe: no child widgets involved) ──────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        # Step 1: clear entire window to transparent (fixes Linux black-box)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        # Step 2: draw character on top
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        self._char.draw(p)

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos    = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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
                    self._show_bubble(random.choice(["wheee! ✨", "wooosh~", "wheeee!", "weee~"]))
                    self._return_timer.start(3000)
            self._drag_pos    = None
            self._is_dragging = False
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
        self._bubble.hide()

        # ── Mood reaction on user input ───────────────────────────────────────
        mood = _detect_mood(user_text)
        self._char.set_state(mood if mood else State.THINKING)

        # ── Build prompt with conversation history ────────────────────────────
        recent = self._history[-(MAX_HISTORY_TURNS * 2):]   # last N pairs
        if recent:
            lines = []
            for role, msg in recent:
                label = "Human" if role == "user" else self._personality.name
                lines.append(f"{label}: {msg}")
            history_block = "\n\n".join(lines)
            full_prompt = f"{history_block}\n\nHuman: {user_text}"
        else:
            full_prompt = user_text

        # ── Store pending message (added to history when response arrives) ────
        self._pending_user_msg = user_text

        allowed  = self._settings.value("allowed_tools", "", type=str)
        use_mcp  = self._settings.value("use_mcp", False, type=bool)
        mcp_path = MCP_CONFIG if use_mcp and os.path.exists(MCP_CONFIG) else None

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
        # ── Append exchange to session history ────────────────────────────────
        if self._pending_user_msg:
            self._history.append(("user", self._pending_user_msg))
            self._history.append(("assistant", response))
            self._pending_user_msg = ""
            # Hard-cap so the list never grows unbounded
            if len(self._history) > MAX_HISTORY_TURNS * 2:
                self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        # ── Mood reaction on Claude's reply ───────────────────────────────────
        resp_mood = _detect_response_mood(response)
        final_state = resp_mood if resp_mood else State.TALKING
        self._char.set_state(final_state)
        self._personality.log_mood(final_state.name)
        self._show_bubble(response)
        bubble_ms = max(6000, len(response.split()) * 300)
        self._return_timer.start(bubble_ms + 500)

    def _on_error(self, msg: str):
        self._pending_user_msg = ""
        self._char.set_state(State.IDLE)
        self._show_bubble(f"Oops! {msg}")
        self._return_timer.start(5000)

    # ── Idle events ───────────────────────────────────────────────────────────

    # ── Clipboard watcher ─────────────────────────────────────────────────────

    def _on_clipboard_change(self):
        text = QApplication.instance().clipboard().text().strip()
        if len(text) < 30 or text == self._last_clipboard:
            return
        if self._char.state not in (State.IDLE, State.HAPPY):
            return
        self._last_clipboard    = text
        self._clipboard_pending = text
        self._show_bubble("Ooh, copied something! Click me to ask about it 👀")
        self._return_timer.start(10_000)

    # ── Typing-aware idle ─────────────────────────────────────────────────────

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
        with self._keypress_lock:
            last = self._last_keypress
        idle_min = (time.time() - last) / 60
        if idle_min >= 20:
            msgs = [
                "Hey... you've been quiet. Taking a break? 🍵",
                "You seem away. Hope everything's ok!",
                "No typing for a while... stretch time? 🧘",
                "Still there? Just checking in ✨",
            ]
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(random.choice(msgs))
            self._return_timer.start(8000)
            with self._keypress_lock:
                self._last_keypress = time.time()

    def _schedule_idle(self):
        min_ms = self._settings.value("idle_min", 30, type=int) * 1000
        max_ms = self._settings.value("idle_max", 90, type=int) * 1000
        self._idle_timer.start(random.randint(min_ms, max_ms))

    def _greet(self):
        streak, milestone, is_first_today = self._personality.update_streak()
        created = self._personality._data.get("created", "")
        today_s = date.today().isoformat()

        # Birthday: same month-day as creation date, but not the creation day itself
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
                7:   f"7 days in a row! One whole week! 🎉",
                14:  f"14 days straight — you can't get rid of me 😄",
                30:  f"30-day streak! We're basically inseparable 🥰",
                50:  f"50 days! Half a hundred. That's wild.",
                100: f"100-DAY STREAK!! I'm crying 🥹 thank you!",
                365: f"One whole year together!! 🎊🎊🎊",
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
        self._show_bubble(msg)
        self._return_timer.start(6000)

    def _pet_pip(self):
        self._char.set_state(State.HAPPY)
        self._personality.log_mood("HAPPY")
        pets = ["hehe~ ♡", "hehe~", "*purrs*", "uwu~", "ehehe~", "*wiggles happily*", "teehee~"]
        self._show_bubble(random.choice(pets))
        self._return_timer.start(4000)

    def _random_event(self):
        ev = random.choices(
            ["quip", "dance", "sleep", "happy", "think", "time_greet"],
            weights=[30, 20, 15, 18, 10, 7],
        )[0]

        if ev == "quip":
            text, state_name = self._personality.random_quip_with_state()
            state = State[state_name] if state_name in State.__members__ else State.HAPPY
            self._char.set_state(state)
            self._personality.log_mood(state.name)
            self._show_bubble(text)
            self._return_timer.start(6000)
        elif ev == "dance":
            self._char.set_state(State.DANCING)
            self._personality.log_mood("DANCING")
            self._show_bubble("♪ doo doo doo ♪")
            self._return_timer.start(8000)
        elif ev == "sleep":
            self._char.set_state(State.SLEEPING)
            self._personality.log_mood("SLEEPING")
            self._return_timer.start(12000)
        elif ev == "happy":
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble("Yay! 🎉")
            self._return_timer.start(5000)
        elif ev == "think":
            self._char.set_state(State.THINKING)
            self._personality.log_mood("THINKING")
            self._show_bubble("Hmm... 🤔")
            self._return_timer.start(6000)
        elif ev == "time_greet":
            self._char.set_state(State.HAPPY)
            self._personality.log_mood("HAPPY")
            self._show_bubble(self._personality.time_quip())
            self._return_timer.start(5000)

        self._schedule_idle()

    def _go_idle(self):
        self._char.set_state(State.IDLE)

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
        self._show_bubble(random.choice(reactions))
        self._return_timer.start(5000)

    # ── Pomodoro ──────────────────────────────────────────────────────────────

    def _start_pomodoro(self):
        if self._pomo_running:
            self._pomo_timer.stop()
            self._pomo_running = False
            self._show_bubble("Pomodoro cancelled. 🍅")
            return
        self._pomo_running = True
        self._pomo_timer.start(25 * 60 * 1000)
        self._char.set_state(State.HAPPY)
        self._show_bubble("Pomodoro started! 🍅 25 min. You got this.")
        self._return_timer.start(5000)

    def _on_pomodoro_done(self):
        self._pomo_running = False
        self._char.set_state(State.DANCING)
        self._personality.log_mood("DANCING")
        self._show_bubble("Time's up! ⏰ Great work! Take a 5-min break 🍵")
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
        self._show_bubble(msg)
        self._return_timer.start(5000)

    # ── Journal ───────────────────────────────────────────────────────────────

    def _write_journal(self):
        try:
            self._personality.write_journal_entry()
            self._personality.save()
        except Exception:
            pass

    # ── Bubble ────────────────────────────────────────────────────────────────

    def _show_bubble(self, text: str):
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        words = len(text.split())
        duration_ms = max(6000, words * 300)  # ~200 wpm reading speed
        self._bubble.show_text(text, anchor, duration_ms)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _show_menu(self, pos: QPoint):
        menu = QMenu()
        menu.addAction(f"Chat with {self._personality.name}", self._open_chat)
        menu.addAction("Control Panel", self._open_panel)
        menu.addSeparator()
        pomo_label = "Stop Pomodoro ⏹" if self._pomo_running else "Start Pomodoro 🍅"
        menu.addAction(pomo_label, self._start_pomodoro)
        menu.addAction("Rock Paper Scissors 🪨", self._play_rps)
        menu.addSeparator()
        history_label = (f"Clear History  ({len(self._history) // 2} turns)"
                         if self._history else "Clear History  (empty)")
        clear_action = menu.addAction(history_label)
        clear_action.setEnabled(bool(self._history))
        clear_action.triggered.connect(self._clear_history)
        menu.addSeparator()
        menu.addAction("Rename", self._rename)
        menu.addAction("Quit", QApplication.quit)
        menu.exec(pos)

    def _clear_history(self):
        self._history.clear()
        self._pending_user_msg = ""
        if self._worker and self._worker.isRunning():
            self._worker.response_ready.disconnect()
            self._worker.error_occurred.disconnect()
            self._worker = None
        self._show_bubble("Memory cleared! Fresh start. 🧹")

    def _open_panel(self):
        if self._panel is None:
            self._panel = ControlPanel(self._personality, self._settings, MCP_CONFIG)
            self._panel.settings_changed.connect(self._on_settings_changed)
        self._panel.refresh()
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def _on_settings_changed(self):
        self._idle_timer.stop()
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
    window = CompanionWindow()
    app.aboutToQuit.connect(window._write_journal)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
