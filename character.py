"""
CharacterRenderer — pure drawing class, NOT a QWidget.
Drawn directly inside CompanionWindow.paintEvent to avoid
Linux X11 child-widget transparency issues.
"""
import random
from enum import Enum, auto
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer

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
BELLY = QColor(145, 135, 225, 140)   # subtle belly shine
BROW  = QColor( 35,  25,  65)        # eyebrow color
GLINT = QColor(255, 255, 255)        # eye glint

# EXCITED tints
EXCITE_SPARK1 = QColor(255, 230,  60)
EXCITE_SPARK2 = QColor(220, 120, 255)

# ── Body shape: (x_start, width) per row ─────────────────────────────────────
BODY_ROWS = [
    (7, 6), (5, 10), (4, 12), (3, 14),
    (2, 16), (2, 16), (2, 16), (2, 16),
    (3, 14), (4, 12), (5, 10), (6, 8), (7, 6),
]
BODY_H = len(BODY_ROWS)  # 13 units

# STRETCHING: body is 2 units taller — extend bottom two rows
STRETCH_EXTRA_ROWS = [
    (7, 6),  # row 13 (extra 1)
    (8, 4),  # row 14 (extra 2)
]


class State(Enum):
    IDLE       = auto()
    TALKING    = auto()
    HAPPY      = auto()
    THINKING   = auto()
    SLEEPING   = auto()
    DANCING    = auto()
    DRAGGING   = auto()
    SURPRISED  = auto()
    WAVING     = auto()
    EXCITED    = auto()   # NEW: energetic bounce, sparkles, arms up
    STRETCHING = auto()   # NEW: idle variant — tall body, arms up, squinting


FRAME_LIMITS = {
    State.IDLE:       4,
    State.TALKING:    3,
    State.HAPPY:      4,
    State.THINKING:   2,
    State.SLEEPING:   4,
    State.DANCING:    6,
    State.DRAGGING:   4,
    State.SURPRISED:  3,
    State.WAVING:     4,
    State.EXCITED:    6,   # fast cycle
    State.STRETCHING: 8,   # plays over ~1s, auto-returns
}

# Subtle body-color tint targets per state (R, G, B). Base BODY = (110, 95, 210).
_STATE_TINTS: dict[State, tuple[int, int, int]] = {
    State.IDLE:        (110,  95, 210),
    State.HAPPY:       (138, 108, 200),   # warmer, slight yellow
    State.DANCING:     (148,  82, 220),   # pink-purple
    State.SLEEPING:    ( 85,  98, 228),   # cool blue
    State.THINKING:    ( 92,  82, 222),   # deeper blue-purple
    State.TALKING:     (112, 102, 215),   # slight teal
    State.DRAGGING:    (122,  78, 232),   # vibrant
    State.SURPRISED:   (145,  88, 215),   # bright violet
    State.WAVING:      (118, 108, 218),   # friendly blue-purple
    State.EXCITED:     (160, 100, 230),   # bright warm violet
    State.STRETCHING:  (105,  92, 208),   # near-idle, slightly dimmer
}

# Ratios to derive DARK and LIGHT variants from the live body color.
_DARK_RATIO  = (0.682, 0.632, 0.810)
_LIGHT_RATIO = (1.455, 1.579, 1.143)

# ── Idle sub-variants ──────────────────────────────────────────────────────────
_IDLE_VARIANTS = ["normal", "look_left", "look_right", "blink_slow"]


class CharacterRenderer:
    """Stateful animation renderer. Call draw() inside a paintEvent."""

    def __init__(self):
        self._state = State.IDLE
        self._frame = 0
        self._cr, self._cg, self._cb = 110.0, 95.0, 210.0  # live tinted color

        # idle variant system
        self._idle_variant: str = "normal"
        self._idle_variant_counter: int = 0   # frames until next variant pick
        self._idle_frames_total: int = 0       # consecutive IDLE frames seen

        # cheek pulse (HAPPY)
        self._cheek_opacity: float = 160.0

        # STRETCHING auto-return callback
        self._stretch_frames: int = 0

        # EXCITED cheek pulse phase
        self._excited_phase: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: State):
        if state != State.IDLE:
            self._idle_frames_total = 0
            self._idle_variant = "normal"
        self._state = state
        self._frame = 0
        if state == State.STRETCHING:
            self._stretch_frames = 0

    def next_frame(self):
        self._frame = (self._frame + 1) % FRAME_LIMITS.get(self._state, 4)

        # IDLE variant bookkeeping
        if self._state == State.IDLE:
            self._idle_frames_total += 1
            self._idle_variant_counter -= 1
            if self._idle_variant_counter <= 0:
                self._pick_idle_variant()

        # STRETCHING auto-step counter
        if self._state == State.STRETCHING:
            self._stretch_frames += 1

        # EXCITED phase (for sparkle animation)
        if self._state == State.EXCITED:
            self._excited_phase = (self._excited_phase + 1) % 6

    def tick_color(self):
        tr, tg, tb = _STATE_TINTS.get(self._state, (110, 95, 210))
        self._cr += (tr - self._cr) * 0.03
        self._cg += (tg - self._cg) * 0.03
        self._cb += (tb - self._cb) * 0.03
        # Snap when close enough to stop unnecessary repaints
        if abs(self._cr - tr) < 0.5: self._cr = float(tr)
        if abs(self._cg - tg) < 0.5: self._cg = float(tg)
        if abs(self._cb - tb) < 0.5: self._cb = float(tb)

        # Cheek pulse on HAPPY
        if self._state == State.HAPPY:
            target = 220.0 if (self._frame % 2 == 0) else 130.0
            self._cheek_opacity += (target - self._cheek_opacity) * 0.15
        else:
            self._cheek_opacity += (160.0 - self._cheek_opacity) * 0.1

    @property
    def state(self) -> State:
        return self._state

    @property
    def idle_frames_total(self) -> int:
        """Consecutive idle frames accumulated — used by main.py for STRETCHING trigger."""
        return self._idle_frames_total

    # canvas size in real pixels — use this for setFixedSize on the window
    canvas_w: int = CW * PX
    canvas_h: int = CH * PX

    def draw(self, p: QPainter, ox: int = 0, oy: int = 0):
        """Draw character at pixel offset (ox, oy)."""
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        s, f = self._state, self._frame

        # ── Bob / xoff per state ──────────────────────────────────────────────
        if s == State.IDLE:
            bob, xoff = [0, 0, -1, 0][f % 4], 0
        elif s == State.HAPPY:
            bob, xoff = [0, -3, -5, -3][f % 4], 0
        elif s == State.DANCING:
            bob  = [0, -2, 0, -2, 0, -2][f % 6]
            xoff = [-2, -1, 0, 1, 2, 1][f % 6]
        elif s == State.DRAGGING:
            bob  = [0, -2, 0, -2][f % 4]
            xoff = [-1, 0, 1, 0][f % 4]
        elif s == State.SURPRISED:
            bob, xoff = [0, -4, -6][f % 3], 0
        elif s == State.WAVING:
            bob, xoff = [0, -1, 0, -1][f % 4], 0
        elif s == State.EXCITED:
            # 2× idle speed — bobs every frame
            bob  = [-3, -6, -3, 0, -3, -6][f % 6]
            xoff = 0
        elif s == State.STRETCHING:
            bob, xoff = -2, 0   # slightly taller feel (shift up)
        else:
            bob, xoff = 0, 0

        bx = ox + (BX + xoff) * PX
        by = oy + (BY + bob)  * PX

        self._shadow(p, bx, by, s)
        self._body(p, bx, by, s)
        self._belly_shine(p, bx, by, s)
        self._highlight(p, bx, by)
        self._arms(p, bx, by, s, f)
        self._eyebrows(p, bx, by, s)
        self._eyes(p, bx, by, s, f)
        self._cheeks(p, bx, by, s, f)
        self._mouth(p, bx, by, s, f)
        self._effects(p, bx, by, s, f)

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _r(self, p, bx, by, rx, ry, rw, rh, color):
        p.fillRect(bx + rx * PX, by + ry * PX, rw * PX, rh * PX, color)

    def _shadow(self, p, bx, by, s):
        # STRETCHING: shadow slightly wider/lower
        if s == State.STRETCHING:
            p.fillRect(bx + 5 * PX, by + (BODY_H + 3) * PX, 10 * PX, PX, SHADE)
        else:
            p.fillRect(bx + 6 * PX, by + (BODY_H + 1) * PX, 8 * PX, PX, SHADE)

    def _body(self, p, bx, by, s):
        r, g, b = int(self._cr), int(self._cg), int(self._cb)
        body_c = QColor(r, g, b)
        dark_c = QColor(int(r * _DARK_RATIO[0]), int(g * _DARK_RATIO[1]), int(b * _DARK_RATIO[2]))
        for row, (xs, w) in enumerate(BODY_ROWS):
            p.fillRect(bx + xs * PX, by + row * PX, w * PX, PX,
                       dark_c if row >= 10 else body_c)
        # STRETCHING: extra 2 rows at the bottom
        if s == State.STRETCHING:
            for ei, (xs, w) in enumerate(STRETCH_EXTRA_ROWS):
                p.fillRect(bx + xs * PX, by + (BODY_H + ei) * PX, w * PX, PX, dark_c)

    def _belly_shine(self, p, bx, by, s):
        """Small lighter ellipse in lower-center — adds depth."""
        if s == State.SLEEPING:
            return
        p.fillRect(bx + 8 * PX, by + 9 * PX,  2 * PX, PX,     BELLY)
        p.fillRect(bx + 7 * PX, by + 10 * PX, 4 * PX, PX,     BELLY)
        p.fillRect(bx + 8 * PX, by + 11 * PX, 2 * PX, PX,     BELLY)

    def _highlight(self, p, bx, by):
        r, g, b = self._cr, self._cg, self._cb
        light_c = QColor(
            min(255, int(r * _LIGHT_RATIO[0])),
            min(255, int(g * _LIGHT_RATIO[1])),
            min(255, int(b * _LIGHT_RATIO[2])),
        )
        # Top-left area highlight (always present — gives roundness)
        self._r(p, bx, by, 6, 1, 2, 1, light_c)
        self._r(p, bx, by, 5, 2, 1, 1, light_c)
        self._r(p, bx, by, 5, 3, 1, 1, light_c)
        self._r(p, bx, by, 4, 4, 1, 1, light_c)

    # ── Arms / nubs ───────────────────────────────────────────────────────────

    def _arms(self, p, bx, by, s, f):
        r, g, b = int(self._cr), int(self._cg), int(self._cb)
        arm_c = QColor(
            min(255, int(r * _LIGHT_RATIO[0])),
            min(255, int(g * _LIGHT_RATIO[1])),
            min(255, int(b * _LIGHT_RATIO[2])),
        )
        dark_arm = QColor(int(r * _DARK_RATIO[0]), int(g * _DARK_RATIO[1]), int(b * _DARK_RATIO[2]))

        if s == State.WAVING:
            # Left arm: static nub at left side
            p.fillRect(bx + 1 * PX, by + 6 * PX, 2 * PX, 2 * PX, arm_c)
            # Right arm: waves — toggles 3px/2px to the right
            rx_off = 3 if f in (1, 3) else 2
            p.fillRect(bx + (20 + rx_off) * PX, by + (4 - (1 if f in (1, 3) else 0)) * PX,
                       2 * PX, 2 * PX, arm_c)

        elif s == State.DANCING:
            # Both arms go up-down alternating
            ly = 4 if f % 2 == 0 else 6
            ry = 6 if f % 2 == 0 else 4
            p.fillRect(bx + 0 * PX,  by + ly * PX, 2 * PX, 2 * PX, arm_c)
            p.fillRect(bx + 20 * PX, by + ry * PX, 2 * PX, 2 * PX, arm_c)

        elif s == State.DRAGGING:
            # Arms extend forward (outward sides)
            p.fillRect(bx - 2 * PX,  by + 6 * PX, 3 * PX, 2 * PX, arm_c)
            p.fillRect(bx + 21 * PX, by + 6 * PX, 3 * PX, 2 * PX, arm_c)

        elif s == State.EXCITED:
            # Both arms raised
            ey = 2 if f % 2 == 0 else 3
            p.fillRect(bx + 0 * PX,  by + ey * PX, 2 * PX, 2 * PX, arm_c)
            p.fillRect(bx + 20 * PX, by + ey * PX, 2 * PX, 2 * PX, arm_c)

        elif s == State.STRETCHING:
            # Arms extended up
            p.fillRect(bx + 0 * PX,  by + 1 * PX, 2 * PX, 2 * PX, arm_c)
            p.fillRect(bx + 20 * PX, by + 1 * PX, 2 * PX, 2 * PX, arm_c)

        else:
            # Default: small nubs at sides
            p.fillRect(bx + 1 * PX,  by + 6 * PX, 2 * PX, 2 * PX, dark_arm)
            p.fillRect(bx + 19 * PX, by + 6 * PX, 2 * PX, 2 * PX, dark_arm)

    # ── Eyebrows ──────────────────────────────────────────────────────────────

    def _eyebrows(self, p, bx, by, s):
        if s in (State.SLEEPING, State.STRETCHING):
            return  # no eyebrows while sleeping or stretching

        # Base Y for brows is 2 units above eyes (eyes at row 3, so brows at row 2→1 depending on mood)
        left_y  = 2
        right_y = 2

        if s == State.HAPPY:
            left_y  = 0   # raised
            right_y = 0
        elif s == State.THINKING:
            right_y = 3   # right brow lower (slight frown on one side)
        elif s == State.SURPRISED:
            left_y  = 0
            right_y = 0   # both very high (same as happy but eyes will be wide)

        # Left eyebrow (2px wide, 1px tall)
        p.fillRect(bx + 5 * PX, by + left_y  * PX, 2 * PX, PX, BROW)
        # Right eyebrow
        p.fillRect(bx + 13 * PX, by + right_y * PX, 2 * PX, PX, BROW)

    # ── Eyes ──────────────────────────────────────────────────────────────────

    def _eyes(self, p, bx, by, s, f):
        # SLEEPING — curved/closed lines
        if s == State.SLEEPING:
            p.fillRect(bx + 4 * PX,  by + 5 * PX, 4 * PX, PX, PUPIL)
            p.fillRect(bx + 12 * PX, by + 5 * PX, 4 * PX, PX, PUPIL)
            return

        # STRETCHING — squinting (horizontal lines)
        if s == State.STRETCHING:
            p.fillRect(bx + 4 * PX,  by + 6 * PX, 4 * PX, PX, PUPIL)
            p.fillRect(bx + 12 * PX, by + 6 * PX, 4 * PX, PX, PUPIL)
            return

        # IDLE blink (slow or regular)
        if s == State.IDLE:
            is_blink_frame = (f == 3)
            if self._idle_variant == "blink_slow":
                # blink lasts frames 2 & 3 instead of just 3
                is_blink_frame = f in (2, 3)
            if is_blink_frame:
                p.fillRect(bx + 4 * PX,  by + 6 * PX, 4 * PX, PX, PUPIL)
                p.fillRect(bx + 12 * PX, by + 6 * PX, 4 * PX, PX, PUPIL)
                return

        # HAPPY — squinty happy eyes
        if s == State.HAPPY and f % 2 == 1:
            for ex in [4, 12]:
                p.fillRect(bx + ex * PX,       by + 4 * PX, 4 * PX, PX, PUPIL)
                p.fillRect(bx + (ex + 1) * PX, by + 5 * PX, 2 * PX, PX, PUPIL)
            return

        # SURPRISED — very wide eyes
        if s == State.SURPRISED:
            for ex in [3, 11]:
                p.fillRect(bx + ex * PX,       by + 2 * PX, 5 * PX, 4 * PX, WHITE)
                p.fillRect(bx + (ex + 1) * PX, by + 2 * PX, 3 * PX, 2 * PX, PUPIL)
                # glint pixel at top-left of pupil
                p.fillRect(bx + (ex + 1) * PX, by + 2 * PX, PX, PX, GLINT)
            return

        # EXCITED — wide sparkly eyes, bigger pupils
        if s == State.EXCITED:
            for ex in [3, 11]:
                p.fillRect(bx + ex * PX, by + 3 * PX, 5 * PX, 3 * PX, WHITE)
                p.fillRect(bx + (ex + 1) * PX, by + 3 * PX, 3 * PX, 3 * PX, PUPIL)
                p.fillRect(bx + (ex + 1) * PX, by + 3 * PX, PX, PX, GLINT)
            return

        # Determine pupil Y offset
        pdy = 4 if s == State.THINKING else (3 if s == State.DRAGGING else 5)

        # Idle sub-variant pupil shifts
        pdx_left  = 0
        pdx_right = 0
        if s == State.IDLE:
            if self._idle_variant == "look_left":
                pdx_left  = -1
                pdx_right = -1
            elif self._idle_variant == "look_right":
                pdx_left  = 1
                pdx_right = 1

        for i, ex in enumerate([4, 12]):
            pdx = pdx_left if i == 0 else pdx_right
            # Eye white (slightly larger — 4×3)
            self._r(p, bx, by, ex,     3,   4, 3, WHITE)
            # Pupil (2×2)
            p.fillRect(bx + (ex + 1 + pdx) * PX, by + pdy * PX, 2 * PX, 2 * PX, PUPIL)
            # Glint pixel at top-left of pupil
            p.fillRect(bx + (ex + 1 + pdx) * PX, by + pdy * PX, PX, PX, GLINT)

    # ── Cheeks ────────────────────────────────────────────────────────────────

    def _cheeks(self, p, bx, by, s, f):
        opacity = int(self._cheek_opacity)
        cheek_c = QColor(255, 160, 180, opacity)
        p.fillRect(bx + 2 * PX,  by + 7 * PX, 3 * PX, 2 * PX, cheek_c)
        p.fillRect(bx + 15 * PX, by + 7 * PX, 3 * PX, 2 * PX, cheek_c)

    # ── Mouth ─────────────────────────────────────────────────────────────────

    def _mouth(self, p, bx, by, s, f):
        if s == State.SLEEPING:
            # Small neutral / slightly closed
            self._r(p, bx, by, 9, 10, 2, 1, MOUTH)

        elif s == State.TALKING and f % 2 == 0:
            # "O" open mouth
            self._r(p, bx, by, 7, 10, 6, 2, MOUTH)
            self._r(p, bx, by, 8, 10, 4, 1, WHITE)

        elif s == State.DRAGGING:
            # Gritted mouth
            self._r(p, bx, by, 7, 10, 6, 2, MOUTH)
            self._r(p, bx, by, 8, 10, 4, 1, WHITE)

        elif s == State.HAPPY or s == State.WAVING:
            # Small U-curve smile
            self._r(p, bx, by, 6,  10, 1, 1, MOUTH)
            self._r(p, bx, by, 7,  11, 6, 1, MOUTH)
            self._r(p, bx, by, 13, 10, 1, 1, MOUTH)

        elif s == State.SURPRISED:
            # Small "O" mouth
            self._r(p, bx, by, 8, 10, 4, 3, MOUTH)
            self._r(p, bx, by, 9, 10, 2, 1, WHITE)

        elif s == State.DANCING or s == State.EXCITED:
            # Wide grin
            self._r(p, bx, by, 5,  10, 1, 1, MOUTH)
            self._r(p, bx, by, 6,  11, 8, 1, MOUTH)
            self._r(p, bx, by, 14, 10, 1, 1, MOUTH)

        elif s == State.STRETCHING:
            # Neutral small line
            self._r(p, bx, by, 8,  10, 4, 1, MOUTH)

        else:
            # IDLE / THINKING / etc: small neutral line with corners
            self._r(p, bx, by, 7,  10, 1, 1, MOUTH)
            self._r(p, bx, by, 8,  11, 4, 1, MOUTH)
            self._r(p, bx, by, 12, 10, 1, 1, MOUTH)

    # ── Effects ───────────────────────────────────────────────────────────────

    def _effects(self, p, bx, by, s, f):
        if s == State.SLEEPING:
            # Z letters floating up, one per frame stage
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

        elif s == State.SURPRISED:
            for iy in [3, 7, 11]:
                p.fillRect(bx - 3 * PX, by + iy * PX, 3 * PX, PX, SPARK)
                p.fillRect(bx + 21 * PX, by + iy * PX, 3 * PX, PX, SPARK)

        elif s == State.WAVING:
            r, g, b = int(self._cr), int(self._cg), int(self._cb)
            light_c = QColor(
                min(255, int(r * _LIGHT_RATIO[0])),
                min(255, int(g * _LIGHT_RATIO[1])),
                min(255, int(b * _LIGHT_RATIO[2])),
            )
            if f in (1, 3):
                p.fillRect(bx + 22 * PX, by - 2 * PX, 2 * PX, 3 * PX, light_c)
            else:
                p.fillRect(bx + 23 * PX, by - 1 * PX, 2 * PX, 3 * PX, light_c)

        elif s == State.EXCITED:
            # Star sparkles at 45° offsets — alternate colors per frame
            phase = self._excited_phase
            spark_positions = [
                (-3, -2), (22, -2),   # sides
                ( 0, 10), (21, 10),   # lower sides
            ]
            col1 = EXCITE_SPARK1 if phase % 2 == 0 else EXCITE_SPARK2
            col2 = EXCITE_SPARK2 if phase % 2 == 0 else EXCITE_SPARK1
            for i, (sx, sy) in enumerate(spark_positions):
                col = col1 if i % 2 == 0 else col2
                # small cross / sparkle shape
                p.fillRect(bx + sx * PX,       by + sy * PX,       PX, 3 * PX, col)
                p.fillRect(bx + (sx - 1) * PX, by + (sy + 1) * PX, 3 * PX, PX, col)

            # Also draw a quick music-note style on alternating frames
            if phase % 3 == 0:
                font = QFont(); font.setPixelSize(PX * 3)
                p.setFont(font); p.setPen(EXCITE_SPARK1)
                p.drawText(bx + 20 * PX, by - 1 * PX, "★")

        elif s == State.STRETCHING:
            # Faint sparkle lines — like a yawn aura
            for iy in [2, 5]:
                p.fillRect(bx - 2 * PX, by + iy * PX, 2 * PX, PX, SHADE)
                p.fillRect(bx + 22 * PX, by + iy * PX, 2 * PX, PX, SHADE)

    # ── Idle variant picker ───────────────────────────────────────────────────

    def _pick_idle_variant(self):
        """Randomly pick the next idle sub-variant; reset the countdown."""
        # Interval: 10–15 seconds. At 130ms/frame and 4-frame IDLE cycle,
        # 1 idle cycle ≈ 0.52s → 10s ≈ 19 cycles → 76 inner frames.
        # But next_frame fires every outer tick (130ms) when idle,
        # reduced by anim_counter in main (fires every 4th tick) → actually
        # next_frame fires ~once every 520ms. So 10s ≈ 19 next_frame calls.
        self._idle_variant_counter = random.randint(19, 29)   # ~10–15s
        self._idle_variant = random.choice(_IDLE_VARIANTS)
