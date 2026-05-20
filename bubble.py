from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize
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


class BubbleWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._text  = ""
        self._style = SPEECH
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._font = QFont("Sans", 11)

    def mousePressEvent(self, event):
        self._hide_timer.stop()
        self.hide()

    def show_text(self, text: str, anchor: QPoint, duration_ms: int = 6000,
                  style: str = SPEECH):
        self._text  = text
        self._style = style
        self._update_geometry(anchor)
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

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

        w = text_w + PADDING_H * 2
        h = text_h + PADDING_V * 2 + TAIL_H

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
        self.setFixedSize(w, h)
        self.move(x, y)

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

    def _paint_speech(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, bubble_h, 10, 10)
        tx = w // 2
        path.moveTo(tx - 8, bubble_h)
        path.lineTo(tx, bubble_h + TAIL_H)
        path.lineTo(tx + 8, bubble_h)
        p.setBrush(BUBBLE_BG)
        p.setPen(BUBBLE_BORDER)
        p.drawPath(path)

    def _paint_thought(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H
        # Main rounded rect (slightly more rounded than speech)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, bubble_h, 18, 18)
        p.setBrush(THOUGHT_BG)
        p.setPen(THOUGHT_BORDER)
        p.drawPath(path)
        # Dot tail: three circles descending toward Pip
        cx = w // 2
        for i, (dx, dy, r) in enumerate([(0, TAIL_H * 0.3, 4), (3, TAIL_H * 0.7, 3), (5, TAIL_H, 2)]):
            p.setBrush(THOUGHT_BG)
            p.drawEllipse(int(cx + dx - r), int(bubble_h + dy - r), r * 2, r * 2)

    def _paint_shout(self, p: QPainter):
        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H
        # Spiky border: draw a star-burst polygon
        import math
        cx, cy = w / 2, bubble_h / 2
        rx, ry = w / 2 - 2, bubble_h / 2 - 2   # outer radii
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
        p.setBrush(SHOUT_BG)
        p.setPen(SHOUT_BORDER)
        p.drawPath(path)
        # Simple triangle tail
        tx = w // 2
        p.setBrush(SHOUT_BG)
        tail = QPainterPath()
        tail.moveTo(tx - 6, bubble_h)
        tail.lineTo(tx, bubble_h + TAIL_H)
        tail.lineTo(tx + 6, bubble_h)
        tail.closeSubpath()
        p.drawPath(tail)
