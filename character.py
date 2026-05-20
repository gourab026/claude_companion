"""
CharacterRenderer — pure drawing class, NOT a QWidget.
Drawn directly inside CompanionWindow.paintEvent to avoid
Linux X11 child-widget transparency issues.
"""
from enum import Enum, auto
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCore import Qt

PX = 4           # pixel-art unit → real pixels
CW, CH = 28, 26  # canvas size in pixel-art units

# Body top-left offset within canvas (in units)
BX, BY = 4, 6
BW = 20  # body width in units

# ── Palette ──────────────────────────────────────────────────────────────────
BODY  = QColor(110,  95, 210)
DARK  = QColor( 75,  60, 170)
LIGHT = QColor(160, 150, 240)
WHITE = QColor(255, 255, 255)
PUPIL = QColor( 20,  15,  40)
CHEEK = QColor(255, 160, 180, 160)
MOUTH = QColor( 55,  35,  90)
SPARK = QColor(255, 215,  50)
ZBLUE = QColor(140, 190, 255)
NOTE  = QColor(255, 200,  80)
SHADE = QColor( 85,  70, 160, 120)

# ── Body shape: (x_start, width) per row ─────────────────────────────────────
BODY_ROWS = [
    (7, 6), (5, 10), (4, 12), (3, 14),
    (2, 16), (2, 16), (2, 16), (2, 16),
    (3, 14), (4, 12), (5, 10), (6, 8), (7, 6),
]
BODY_H = len(BODY_ROWS)  # 13 units


class State(Enum):
    IDLE     = auto()
    TALKING  = auto()
    HAPPY    = auto()
    THINKING = auto()
    SLEEPING = auto()
    DANCING  = auto()
    DRAGGING = auto()


FRAME_LIMITS = {
    State.IDLE: 4, State.TALKING: 3, State.HAPPY: 4,
    State.THINKING: 2, State.SLEEPING: 4, State.DANCING: 6,
    State.DRAGGING: 4,
}


class CharacterRenderer:
    """Stateful animation renderer. Call draw() inside a paintEvent."""

    def __init__(self):
        self._state = State.IDLE
        self._frame = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: State):
        self._state = state
        self._frame = 0

    def next_frame(self):
        self._frame = (self._frame + 1) % FRAME_LIMITS.get(self._state, 4)

    @property
    def state(self) -> State:
        return self._state

    # canvas size in real pixels — use this for setFixedSize on the window
    canvas_w: int = CW * PX
    canvas_h: int = CH * PX

    def draw(self, p: QPainter, ox: int = 0, oy: int = 0):
        """Draw character at pixel offset (ox, oy)."""
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        s, f = self._state, self._frame

        if s == State.IDLE:
            bob, xoff = [0, -1, -2, -1][f % 4], 0
        elif s == State.HAPPY:
            bob, xoff = [0, -3, -5, -3][f % 4], 0
        elif s == State.DANCING:
            bob  = [0, -2, 0, -2, 0, -2][f % 6]
            xoff = [-2, -1, 0, 1, 2, 1][f % 6]
        elif s == State.DRAGGING:
            bob  = [0, -2, 0, -2][f % 4]
            xoff = [-1, 0, 1, 0][f % 4]
        else:
            bob, xoff = 0, 0

        bx = ox + (BX + xoff) * PX
        by = oy + (BY + bob)  * PX

        self._shadow(p, bx, by)
        self._body(p, bx, by)
        self._highlight(p, bx, by)
        self._eyes(p, bx, by, s, f)
        self._cheeks(p, bx, by)
        self._mouth(p, bx, by, s, f)
        self._effects(p, bx, by, s, f)

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _r(self, p, bx, by, rx, ry, rw, rh, color):
        p.fillRect(bx + rx * PX, by + ry * PX, rw * PX, rh * PX, color)

    def _shadow(self, p, bx, by):
        p.fillRect(bx + 6 * PX, by + (BODY_H + 1) * PX, 8 * PX, PX, SHADE)

    def _body(self, p, bx, by):
        for row, (xs, w) in enumerate(BODY_ROWS):
            p.fillRect(bx + xs * PX, by + row * PX, w * PX, PX,
                       DARK if row >= 10 else BODY)

    def _highlight(self, p, bx, by):
        self._r(p, bx, by, 6, 1, 2, 1, LIGHT)
        self._r(p, bx, by, 5, 2, 1, 1, LIGHT)

    def _eyes(self, p, bx, by, s, f):
        if s == State.SLEEPING:
            p.fillRect(bx + 4 * PX,  by + 5 * PX, 4 * PX, PX, PUPIL)
            p.fillRect(bx + 12 * PX, by + 5 * PX, 4 * PX, PX, PUPIL)
            return
        if s == State.HAPPY and f % 2 == 1:
            for ex in [4, 12]:
                p.fillRect(bx + ex * PX,       by + 4 * PX, 4 * PX, PX, PUPIL)
                p.fillRect(bx + (ex + 1) * PX, by + 5 * PX, 2 * PX, PX, PUPIL)
            return
        pdy = 4 if s == State.THINKING else (3 if s == State.DRAGGING else 5)
        for ex in [4, 12]:
            self._r(p, bx, by, ex,     3,   4, 3, WHITE)
            self._r(p, bx, by, ex + 1, pdy, 2, 2, PUPIL)

    def _cheeks(self, p, bx, by):
        p.fillRect(bx + 2 * PX,  by + 7 * PX, 3 * PX, 2 * PX, CHEEK)
        p.fillRect(bx + 15 * PX, by + 7 * PX, 3 * PX, 2 * PX, CHEEK)

    def _mouth(self, p, bx, by, s, f):
        if s == State.SLEEPING:
            self._r(p, bx, by, 9, 10, 2, 1, MOUTH)
        elif s == State.TALKING and f % 2 == 0:
            self._r(p, bx, by, 7, 10, 6, 2, MOUTH)
            self._r(p, bx, by, 8, 10, 4, 1, WHITE)
        elif s == State.DRAGGING:
            self._r(p, bx, by, 7, 10, 6, 2, MOUTH)
            self._r(p, bx, by, 8, 10, 4, 1, WHITE)
        elif s == State.HAPPY:
            self._r(p, bx, by, 6,  10, 1, 1, MOUTH)
            self._r(p, bx, by, 7,  11, 6, 1, MOUTH)
            self._r(p, bx, by, 13, 10, 1, 1, MOUTH)
        else:
            self._r(p, bx, by, 7,  10, 1, 1, MOUTH)
            self._r(p, bx, by, 8,  11, 4, 1, MOUTH)
            self._r(p, bx, by, 12, 10, 1, 1, MOUTH)

    def _effects(self, p, bx, by, s, f):
        if s == State.SLEEPING:
            for i, (zx, zy) in enumerate([(16, -1), (18, -3), (20, -5)][:(f % 4 + 1)]):
                font = QFont(); font.setPixelSize((i + 2) * PX)
                p.setFont(font); p.setPen(ZBLUE)
                p.drawText(bx + zx * PX, by + zy * PX, "z")

        elif s == State.DANCING:
            nx = 0 if f % 2 == 0 else 22
            ny = 2 - (f % 3)
            font = QFont(); font.setPixelSize(PX * 4)
            p.setFont(font); p.setPen(NOTE)
            p.drawText(bx + nx * PX, by + ny * PX, "♪")

        elif s == State.HAPPY:
            for i, (sx, sy) in enumerate([(1, 3), (19, 3), (0, 8), (20, 8)][:(f % 4 + 1)]):
                p.fillRect(bx + sx * PX,       by + sy * PX,       PX, PX, SPARK)
                p.fillRect(bx + (sx + 1) * PX, by + (sy - 1) * PX, PX, PX, SPARK)

        elif s == State.THINKING:
            for i, (dx, dy) in enumerate(zip([11, 13, 15], [3, 2, 1])):
                sz = (i + 1) * PX
                p.fillRect(bx + dx * PX, by + dy * PX, sz, sz, WHITE)

        elif s == State.DRAGGING:
            for iy in [3, 6, 9]:
                p.fillRect(bx - 3 * PX, by + iy * PX, 3 * PX, PX, SPARK)
                p.fillRect(bx + 21 * PX, by + iy * PX, 3 * PX, PX, SPARK)
