"""
ChatInputWidget — inline floating input panel that replaces QInputDialog.

Shows near Pip, non-modal, styled to match Pip's purple theme.
Features: Enter to send, Escape to cancel, Up/Down for message history,
click-outside (WindowDeactivate) to dismiss, busy-state placeholder.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QSize
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont

_BG     = QColor(20, 16, 32, 248)
_BORDER = QColor(120, 96, 212, 200)
_HINT   = QColor(136, 120, 160)

W, H       = 340, 58   # outer widget size
RADIUS     = 14
MARGIN     = 10        # gap below anchor point


class ChatInputWidget(QWidget):
    submitted = pyqtSignal(str)   # user sent a message
    dismissed = pyqtSignal()      # user cancelled

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setFixedSize(W, H)

        self._history: list[str] = []
        self._hist_idx: int = -1   # -1 = not browsing history

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 11, 12, 11)
        lay.setSpacing(8)

        self._field = QLineEdit()
        self._field.setPlaceholderText("Say something…  ↑↓ history  Esc cancel")
        self._field.setFont(QFont("Sans", 11))
        self._field.returnPressed.connect(self._submit)
        self._field.installEventFilter(self)
        self._field.setStyleSheet("""
            QLineEdit {
                background: #100d1c;
                color: #e8e0f0;
                border: none;
                border-radius: 7px;
                padding: 5px 10px;
                selection-background-color: #7860d4;
            }
        """)

        self._btn = QPushButton("↵")
        self._btn.setFixedSize(34, 34)
        self._btn.setToolTip("Send  (Enter)")
        self._btn.clicked.connect(self._submit)
        self._btn.setStyleSheet("""
            QPushButton {
                background: #7860d4;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover   { background: #9478ee; }
            QPushButton:pressed { background: #5040a8; }
            QPushButton:disabled { background: #3a3050; color: #7060a0; }
        """)

        lay.addWidget(self._field)
        lay.addWidget(self._btn)

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), RADIUS, RADIUS)
        p.fillPath(path, _BG)
        p.setPen(_BORDER)
        p.drawPath(path)

    # ── Events ────────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._field and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self._cancel()
                return True
            if key == Qt.Key.Key_Up:
                self._history_step(+1)
                return True
            if key == Qt.Key.Key_Down:
                self._history_step(-1)
                return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        # Close when the OS moves focus to another window (click-outside)
        if event.type() == QEvent.Type.WindowDeactivate and self.isVisible():
            self._cancel()
        super().changeEvent(event)

    # ── History navigation ────────────────────────────────────────────────────

    def _history_step(self, direction: int):
        if not self._history:
            return
        new_idx = self._hist_idx + direction
        if new_idx >= len(self._history):
            return
        if new_idx < 0:
            self._hist_idx = -1
            self._field.clear()
            return
        self._hist_idx = new_idx
        self._field.setText(self._history[-(self._hist_idx + 1)])
        self._field.end(False)

    # ── Public API ────────────────────────────────────────────────────────────

    def activate(self, anchor: QPoint, prefill: str = "", busy: bool = False):
        """Position above *anchor* and show."""
        if busy:
            self._field.setPlaceholderText("Pip is thinking… send anyway to queue")
        else:
            self._field.setPlaceholderText("Say something…  ↑↓ history  Esc cancel")

        self._hist_idx = -1
        self._field.setText(prefill)

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()

        x = anchor.x() - W // 2
        y = anchor.y() - H - MARGIN

        x = max(4, min(x, screen.width()  - W - 4))
        y = max(4, min(y, screen.height() - H - 4))

        self.move(x, y)
        self.show()
        self.raise_()
        self._field.setFocus()
        if prefill:
            self._field.selectAll()

    def set_busy(self, busy: bool):
        """Update placeholder while widget is already open."""
        if busy:
            self._field.setPlaceholderText("Pip is thinking… send anyway to queue")
        else:
            self._field.setPlaceholderText("Say something…  ↑↓ history  Esc cancel")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _submit(self):
        text = self._field.text().strip()
        if not text:
            self._cancel()
            return
        self._history.append(text)
        if len(self._history) > 50:
            self._history.pop(0)
        self._hist_idx = -1
        self._field.clear()
        self.hide()
        self.submitted.emit(text)

    def _cancel(self):
        self._hist_idx = -1
        self._field.clear()
        self.hide()
        self.dismissed.emit()
