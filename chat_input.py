"""
ChatInputWidget — inline floating input panel that replaces QInputDialog.

Shows near Pip, non-modal, styled to match Pip's purple theme.
Features: Enter to send, Escape to cancel, Up/Down for message history,
click-outside (WindowDeactivate) to dismiss, busy-state placeholder,
mic button for voice input.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QSize, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont

_BG     = QColor(20, 16, 32, 248)
_BORDER = QColor(120, 96, 212, 200)
_HINT   = QColor(136, 120, 160)

W, H       = 380, 58   # wider to fit mic button
RADIUS     = 14
MARGIN     = 10        # gap below anchor point

_MIC_IDLE = """
    QPushButton {
        background: #2a2040;
        color: #c0b0e0;
        border: none;
        border-radius: 8px;
        font-size: 15px;
    }
    QPushButton:hover   { background: #3a3060; }
    QPushButton:pressed { background: #1a1030; }
    QPushButton:disabled { background: #1a1630; color: #4a3f60; }
"""
_MIC_RECORDING_A = "QPushButton { background:#c03048; color:#fff; border:none; border-radius:8px; font-size:15px; }"
_MIC_RECORDING_B = "QPushButton { background:#e04060; color:#fff; border:none; border-radius:8px; font-size:15px; }"


class ChatInputWidget(QWidget):
    submitted      = pyqtSignal(str)   # user sent a message
    dismissed      = pyqtSignal()      # user cancelled
    voice_listening = pyqtSignal()     # mic opened — Pip should show LISTENING state
    voice_done      = pyqtSignal()     # recording finished (success or error)

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

        self._voice_worker = None   # kept alive to prevent GC
        self._voice_engine   = "google"
        self._voice_language = "en-US"
        self._voice_enabled  = True

        # Pulse timer for recording animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(350)
        self._pulse_state = False
        self._pulse_timer.timeout.connect(self._pulse_mic)

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

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(34, 34)
        self._mic_btn.setToolTip("Voice input — click to speak")
        self._mic_btn.setStyleSheet(_MIC_IDLE)
        self._mic_btn.clicked.connect(self._toggle_voice)

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
        lay.addWidget(self._mic_btn)
        lay.addWidget(self._btn)

    # ── Voice input ───────────────────────────────────────────────────────────

    def set_voice_config(self, enabled: bool, engine: str, language: str):
        self._voice_enabled  = enabled
        self._voice_engine   = engine
        self._voice_language = language
        self._mic_btn.setVisible(enabled)

    def _toggle_voice(self):
        if self._voice_worker and self._voice_worker.isRunning():
            self._voice_worker.terminate()
            self._stop_recording_ui("Cancelled.")
            return
        self._start_recording()

    def _start_recording(self):
        try:
            from voice_input import VoiceWorker, _SR_AVAILABLE
        except ImportError:
            self._field.setPlaceholderText("voice_input.py not found")
            return

        if not _SR_AVAILABLE:
            self._field.setPlaceholderText("Install: pip install SpeechRecognition pyaudio")
            return

        from voice_input import VoiceWorker
        self._voice_worker = VoiceWorker(
            engine=self._voice_engine,
            language=self._voice_language,
            parent=self,
        )
        self._voice_worker.listening_started.connect(self._on_listening_started)
        self._voice_worker.transcription_ready.connect(self._on_transcription)
        self._voice_worker.error_occurred.connect(self._on_voice_error)
        self._voice_worker.finished.connect(lambda: self._stop_recording_ui())

        self._field.setPlaceholderText("Adjusting to background noise…")
        self._mic_btn.setStyleSheet(_MIC_RECORDING_A)
        self._pulse_timer.start()
        self._voice_worker.start()

    def _on_listening_started(self):
        self._field.setPlaceholderText("Listening… speak now")
        self.voice_listening.emit()

    def _on_transcription(self, text: str):
        self._field.setText(text)
        self._field.setFocus()
        self._field.end(False)
        self.voice_done.emit()

    def _on_voice_error(self, msg: str):
        short = msg.split("\n")[0][:55]
        self._field.setPlaceholderText(short)
        self.voice_done.emit()

    def _stop_recording_ui(self, placeholder: str = ""):
        self._pulse_timer.stop()
        self._mic_btn.setStyleSheet(_MIC_IDLE)
        if placeholder:
            self._field.setPlaceholderText(placeholder)
        elif not self._field.text() and not self._field.placeholderText().startswith("Install"):
            self._field.setPlaceholderText("Say something…  ↑↓ history  Esc cancel")

    def _pulse_mic(self):
        self._pulse_state = not self._pulse_state
        self._mic_btn.setStyleSheet(
            _MIC_RECORDING_B if self._pulse_state else _MIC_RECORDING_A
        )

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), RADIUS, RADIUS)
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
