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
import sys

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

    # ── Animation ─────────────────────────────────────────────────────────────

    def _tick(self):
        self._char.next_frame()
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
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos is not None:
                moved = (event.globalPosition().toPoint()
                         - self.frameGeometry().topLeft() - self._drag_pos)
                if moved.manhattanLength() < 6:
                    self._open_chat()
            self._drag_pos = None
            self._settings.setValue("x", self.x())
            self._settings.setValue("y", self.y())

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._bubble.hide()

    # ── Chat ──────────────────────────────────────────────────────────────────

    def _open_chat(self):
        text, ok = QInputDialog.getText(
            None, f"Talk to {self._personality.name}",
            "Say something:",
            QLineEdit.EchoMode.Normal,
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
            if len(self._history) > MAX_HISTORY_TURNS * 2 + 2:
                self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        # ── Mood reaction on Claude's reply ───────────────────────────────────
        resp_mood = _detect_response_mood(response)
        self._char.set_state(resp_mood if resp_mood else State.TALKING)
        self._show_bubble(response)
        self._return_timer.start(7000)

    def _on_error(self, msg: str):
        self._pending_user_msg = ""
        self._char.set_state(State.IDLE)
        self._show_bubble(f"Oops! {msg}")
        self._return_timer.start(5000)

    # ── Idle events ───────────────────────────────────────────────────────────

    def _schedule_idle(self):
        min_ms = self._settings.value("idle_min", 30, type=int) * 1000
        max_ms = self._settings.value("idle_max", 90, type=int) * 1000
        self._idle_timer.start(random.randint(min_ms, max_ms))

    def _random_event(self):
        ev = random.choices(
            ["quip", "dance", "sleep", "happy", "think"],
            weights=[35, 20, 15, 20, 10],
        )[0]

        if ev == "quip":
            self._char.set_state(State.IDLE)
            self._show_bubble(self._personality.random_quip())
            self._return_timer.start(6000)
        elif ev == "dance":
            self._char.set_state(State.DANCING)
            self._show_bubble("♪ doo doo doo ♪")
            self._return_timer.start(8000)
        elif ev == "sleep":
            self._char.set_state(State.SLEEPING)
            self._return_timer.start(12000)
        elif ev == "happy":
            self._char.set_state(State.HAPPY)
            self._show_bubble("Yay! 🎉")
            self._return_timer.start(5000)
        elif ev == "think":
            self._char.set_state(State.THINKING)
            self._show_bubble("Hmm... 🤔")
            self._return_timer.start(6000)

        self._schedule_idle()

    def _go_idle(self):
        self._char.set_state(State.IDLE)

    # ── Bubble ────────────────────────────────────────────────────────────────

    def _show_bubble(self, text: str):
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        self._bubble.show_text(text, anchor)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _show_menu(self, pos: QPoint):
        menu = QMenu()
        menu.addAction(f"Chat with {self._personality.name}", self._open_chat)
        menu.addAction("Control Panel", self._open_panel)
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
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
