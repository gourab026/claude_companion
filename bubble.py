from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont, QFontMetrics


BUBBLE_BG   = QColor(255, 255, 240, 235)
BUBBLE_BORDER = QColor(120, 100, 200, 200)
BUBBLE_TEXT = QColor(40, 30, 60)
TAIL_H      = 10   # tail triangle height in px
PADDING     = 12
MAX_WIDTH   = 280


class BubbleWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._text = ""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._font = QFont("Sans", 11)

    def mousePressEvent(self, event):
        self._hide_timer.stop()
        self.hide()

    def show_text(self, text: str, anchor: QPoint, duration_ms: int = 6000):
        self._text = text
        self._update_geometry(anchor)
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _update_geometry(self, anchor: QPoint):
        fm = QFontMetrics(self._font)
        # Wrap text
        lines = []
        for paragraph in self._text.split("\n"):
            words = paragraph.split()
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if fm.horizontalAdvance(test) > MAX_WIDTH - PADDING * 2:
                    if line:
                        lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)

        line_h = fm.height() + 2
        text_w = min(MAX_WIDTH - PADDING * 2, max(fm.horizontalAdvance(l) for l in lines))
        text_h = len(lines) * line_h

        w = text_w + PADDING * 2
        h = text_h + PADDING * 2 + TAIL_H

        # Position bubble above the anchor point, centered
        x = anchor.x() - w // 2
        y = anchor.y() - h

        # Keep on screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = max(4, min(x, screen.width() - w - 4))
        y = max(4, y)

        self._lines = lines
        self._line_h = line_h
        self._text_w = text_w
        self._text_h = text_h
        self.setFixedSize(w, h)
        self.move(x, y)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bubble_h = h - TAIL_H

        path = QPainterPath()
        r = 10
        path.addRoundedRect(0, 0, w, bubble_h, r, r)

        # Tail (centered bottom)
        tx = w // 2
        path.moveTo(tx - 8, bubble_h)
        path.lineTo(tx, bubble_h + TAIL_H)
        path.lineTo(tx + 8, bubble_h)

        p.setBrush(BUBBLE_BG)
        p.setPen(BUBBLE_BORDER)
        p.drawPath(path)

        p.setPen(BUBBLE_TEXT)
        p.setFont(self._font)
        y = PADDING
        for line in self._lines:
            p.drawText(PADDING, y + self._line_h - 4, line)
            y += self._line_h
