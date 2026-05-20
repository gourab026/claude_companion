"""
Pip — pixel-art desktop companion for Linux.

Left-click  : open chat
Right-click : menu  →  Control Panel / Rename / Quit
Drag        : move Pip around the screen
"""

import os
import random
import sys

from PyQt6.QtWidgets import QApplication, QWidget, QInputDialog, QMenu, QLineEdit
from PyQt6.QtCore import Qt, QPoint, QTimer, QSettings
from PyQt6.QtGui import QPainter

from character import CharacterRenderer, State
from personality import Personality
from claude_client import ClaudeWorker
from bubble import BubbleWindow
from control_panel import ControlPanel

MCP_CONFIG = os.path.join(os.path.dirname(__file__), "mcp_config.json")


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

        self._char.set_state(State.THINKING)
        self._bubble.hide()

        allowed = self._settings.value("allowed_tools", "", type=str)
        use_mcp = self._settings.value("use_mcp", False, type=bool)
        mcp_path = MCP_CONFIG if use_mcp and os.path.exists(MCP_CONFIG) else None

        self._worker = ClaudeWorker(
            text.strip(),
            self._personality.get_system_prompt(),
            model=self._settings.value("model", "claude-sonnet-4-6"),
            allowed_tools=allowed or None,
            mcp_config=mcp_path,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

        self._personality.after_interaction(text.strip())

    def _on_response(self, text: str):
        self._char.set_state(State.TALKING)
        self._show_bubble(text)
        self._return_timer.start(7000)

    def _on_error(self, msg: str):
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
        menu.addAction("Rename", self._rename)
        menu.addAction("Quit", QApplication.quit)
        menu.exec(pos)

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
