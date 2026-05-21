from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont, QFontMetrics


BUBBLE_BG     = QColor(255, 255, 240, 235)
BUBBLE_BORDER = QColor(120, 100, 200, 200)
BUBBLE_TEXT   = QColor(40, 30, 60)
SHOUT_BG      = QColor(255, 245, 200, 240)
SHOUT_BORDER  = QColor(200, 80, 60, 220)
THOUGHT_BG    = QColor(240, 240, 255, 230)
THOUGHT_BORDER= QColor(100, 120, 200, 180)
TAIL_H        = 10   # tail triangle height in px
PADDING_H     = 14   # left/right padding
PADDING_V     = 12   # top/bottom padding
MAX_WIDTH     = 300
# kept for external code that may import PADDING
PADDING       = PADDING_H

# Style constants
SPEECH  = "speech"   # default rounded bubble with triangle tail
THOUGHT = "thought"  # cloud-like with dot tail
SHOUT   = "shout"    # spiky border, warm background

# Extra bottom padding when "Got it" label is shown
_GOTIT_H = 20


class BubbleWindow(QWidget):
    bubble_closed   = pyqtSignal()   # emitted when bubble hides (timer or click)
    double_clicked  = pyqtSignal()   # emitted on double-click (for reply feature)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._text       = ""
        self._style      = SPEECH
        self._interactive = False   # if True, no auto-timer; show "Got it" label
        self._hovered    = False    # hover state for highlight effect
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_timer_close)

        # Safety timeout for interactive bubbles (90 seconds)
        self._safety_timer = QTimer(self)
        self._safety_timer.setSingleShot(True)
        self._safety_timer.timeout.connect(self._on_timer_close)

        self._font = QFont("Sans", 11)

        # "Got it" label for interactive mode
        self._gotit = QLabel("✓ Got it", self)
        self._gotit.setFont(QFont("Sans", 8))
        self._gotit.setStyleSheet("color: #5a4f70; background: transparent; padding: 2px 4px;")
        self._gotit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gotit.hide()
        self._gotit.mousePressEvent = lambda e: self._dismiss()

        # Reaction buttons (shown after speech bubble — 3 emoji buttons)
        self._reaction_btns: list[QLabel] = []
        for emoji in ["👍", "😂", "🤔"]:
            btn = QLabel(emoji, self)
            btn.setFont(QFont("Sans", 14))
            btn.setStyleSheet(
                "background: rgba(30,20,50,180); border-radius: 10px; padding: 2px 4px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(30, 30)
            btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn.hide()
            self._reaction_btns.append(btn)

        # Wire reaction clicks
        self._reaction_btns[0].mousePressEvent = lambda e: self._on_reaction("thumbs_up", 0)
        self._reaction_btns[1].mousePressEvent = lambda e: self._on_reaction("laugh", 1)
        self._reaction_btns[2].mousePressEvent = lambda e: self._on_reaction("think", 2)

        # Callback invoked when a reaction is clicked: fn(reaction_name)
        self.on_reaction = None

        # Fade timer for reaction buttons (5 seconds)
        self._reaction_fade_timer = QTimer(self)
        self._reaction_fade_timer.setSingleShot(True)
        self._reaction_fade_timer.timeout.connect(self._hide_reactions)

        # Track double-click timing
        self._last_click_time: float = 0.0

        # Enable mouse tracking for hover
        self.setMouseTracking(True)

    # ── Hover tracking ────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    # ── Timer callbacks ───────────────────────────────────────────────────────

    def _on_timer_close(self):
        self._dismiss()

    def _dismiss(self):
        self._safety_timer.stop()
        self._hide_timer.stop()
        self._hide_reactions()
        self._gotit.hide()
        self.hide()
        self.bubble_closed.emit()

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        import time
        now = time.time()
        if now - self._last_click_time < 0.35:
            # Double-click
            self.double_clicked.emit()
        self._last_click_time = now
        self._dismiss()

    # ── Public API ────────────────────────────────────────────────────────────

    def show_text(self, text: str, anchor: QPoint, duration_ms: int = 6000,
                  style: str = SPEECH, interactive: bool = False):
        self._text        = text
        self._style       = style
        self._interactive = interactive
        self._hovered     = False
        self._update_geometry(anchor)
        self._hide_reactions()

        # Position "Got it" label bottom-right of bubble body
        if interactive:
            self._gotit.show()
            self._gotit.adjustSize()
            bh = self.height() - TAIL_H - _GOTIT_H
            self._gotit.move(
                self.width() - self._gotit.width() - PADDING_H,
                bh + (_GOTIT_H - self._gotit.height()) // 2,
            )
            self._hide_timer.stop()
            self._safety_timer.start(90_000)  # 90-second safety cap
        else:
            self._gotit.hide()
            self._safety_timer.stop()
            self._hide_timer.start(duration_ms)

        self.show()
        self.raise_()

        # Show reaction buttons for speech bubbles (non-interactive)
        if style == SPEECH and not interactive:
            self._place_reactions()
            for btn in self._reaction_btns:
                btn.show()
                btn.setWindowOpacity(1.0)
            self._reaction_fade_timer.start(5000)

    def _place_reactions(self):
        """Position the three reaction buttons just below the bubble body."""
        bh = self.height() - TAIL_H  # bottom of text area
        total_w = len(self._reaction_btns) * 32 + (len(self._reaction_btns) - 1) * 4
        start_x = (self.width() - total_w) // 2
        y = bh - 30 - 4   # just inside bottom of bubble
        for i, btn in enumerate(self._reaction_btns):
            btn.move(start_x + i * 36, y)

    def _hide_reactions(self):
        self._reaction_fade_timer.stop()
        for btn in self._reaction_btns:
            btn.hide()

    def _on_reaction(self, name: str, idx: int):
        # Hide all reaction buttons after click
        self._hide_reactions()
        if callable(self.on_reaction):
            self.on_reaction(name)

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _update_geometry(self, anchor: QPoint):
        fm = QFontMetrics(self._font)
        lines = []
        for paragraph in self._text.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if fm.horizontalAdvance(test) > MAX_WIDTH - PADDING_H * 2:
                    if line:
                        lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)

        line_h = fm.lineSpacing()
        text_w = min(MAX_WIDTH - PADDING_H * 2,
                     max((fm.horizontalAdvance(l) for l in lines), default=0))
        text_h = len(lines) * line_h

        extra_bottom = _GOTIT_H if self._interactive else 0

        w = text_w + PADDING_H * 2
        h = text_h + PADDING_V * 2 + TAIL_H + extra_bottom

        x = anchor.x() - w // 2
        y = anchor.y() - h

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = max(4, min(x, screen.width() - w - 4))
        y = max(4, y)

        self._lines   = lines
        self._line_h  = line_h
        self._text_w  = text_w
        self._text_h  = text_h
        self._extra_bottom = extra_bottom
        self.setFixedSize(w, h)
        self.move(x, y)

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._style == SHOUT:
            self._paint_shout(p)
        elif self._style == THOUGHT:
            self._paint_thought(p)
        else:
            self._paint_speech(p)

        # Draw text (common to all styles)
        p.setPen(BUBBLE_TEXT)
        p.setFont(self._font)
        flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        y = PADDING_V
        for line in self._lines:
            rect = QRect(PADDING_H, y, self._text_w, self._line_h)
            p.drawText(rect, flags, line)
            y += self._line_h

    def _hover_bg(self, base: QColor) -> QColor:
        """Return a slightly darker version of base colour when hovered."""
        if not self._hovered:
            return base
        c = QColor(base)
        c.setAlpha(min(255, base.alpha() + 30))
        # Darken slightly
        c.setRed(max(0, c.red() - 15))
        c.setGreen(max(0, c.green() - 15))
        c.setBlue(max(0, c.blue() - 15))
        return c

    def _hover_border(self, base: QColor) -> QColor:
        """Return a brighter border colour when hovered (pulse effect)."""
        if not self._hovered:
            return base
        c = QColor(base)
        c.setAlpha(min(255, base.alpha() + 60))
        c.setRed(min(255, c.red() + 30))
        c.setBlue(min(255, c.blue() + 20))
        return c

    def _paint_speech(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H - self._extra_bottom
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, bubble_h, 10, 10)
        tx = w // 2
        path.moveTo(tx - 8, bubble_h)
        path.lineTo(tx, bubble_h + TAIL_H)
        path.lineTo(tx + 8, bubble_h)
        p.setBrush(self._hover_bg(BUBBLE_BG))
        pen_color = self._hover_border(BUBBLE_BORDER)
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtGui import QPen as _QPen
        if self._hovered:
            p.setPen(_QPen(pen_color, 2.0))
        else:
            p.setPen(pen_color)
        p.drawPath(path)

    def _paint_thought(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H - self._extra_bottom
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, bubble_h, 18, 18)
        p.setBrush(self._hover_bg(THOUGHT_BG))
        pen_color = self._hover_border(THOUGHT_BORDER)
        from PyQt6.QtGui import QPen as _QPen
        if self._hovered:
            p.setPen(_QPen(pen_color, 2.0))
        else:
            p.setPen(pen_color)
        p.drawPath(path)
        # Dot tail: three circles descending toward Pip
        cx = w // 2
        for i, (dx, dy, r) in enumerate([(0, TAIL_H * 0.3, 4), (3, TAIL_H * 0.7, 3), (5, TAIL_H, 2)]):
            p.setBrush(self._hover_bg(THOUGHT_BG))
            p.drawEllipse(int(cx + dx - r), int(bubble_h + dy - r), r * 2, r * 2)

    def _paint_shout(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H - self._extra_bottom
        import math
        cx, cy = w / 2, bubble_h / 2
        rx, ry = w / 2 - 2, bubble_h / 2 - 2
        spikes = 16
        points = []
        for i in range(spikes * 2):
            angle = math.pi * i / spikes - math.pi / 2
            r = (rx if i % 2 == 0 else rx * 0.88,
                 ry if i % 2 == 0 else ry * 0.88)
            points.append((cx + r[0] * math.cos(angle), cy + r[1] * math.sin(angle)))
        path = QPainterPath()
        path.moveTo(*points[0])
        for pt in points[1:]:
            path.lineTo(*pt)
        path.closeSubpath()
        p.setBrush(self._hover_bg(SHOUT_BG))
        pen_color = self._hover_border(SHOUT_BORDER)
        from PyQt6.QtGui import QPen as _QPen
        if self._hovered:
            p.setPen(_QPen(pen_color, 2.0))
        else:
            p.setPen(pen_color)
        p.drawPath(path)
        # Simple triangle tail
        tx = w // 2
        p.setBrush(self._hover_bg(SHOUT_BG))
        tail = QPainterPath()
        tail.moveTo(tx - 6, bubble_h)
        tail.lineTo(tx, bubble_h + TAIL_H)
        tail.lineTo(tx + 6, bubble_h)
        tail.closeSubpath()
        p.drawPath(tail)
