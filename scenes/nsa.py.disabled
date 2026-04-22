"""NSA: green-terminal Matrix rain + CLASSIFIED / GHIDRA watermark + REC indicator.

A visual tribute to Ghidra's maker. Green glyph columns rain down from
the top, a slowly-rotating 'CLASSIFIED / TOP SECRET / GHIDRA' cartouche
sits behind them, and a little red REC dot pulses in the top-right like
a recording light.
"""

from __future__ import annotations

import math
import random

from core import QtCore, QtGui, NO_PEN, register_scene
from scenes._common import (
    fade_envelope, with_alpha, ensure_state, tick_dt_ms, pulse, make_font, text_bbox,
)


_DURATION_MS = 25000

_COL_WIDTH   = 14
_ROW_HEIGHT  = 16
_GLYPHS      = "01$%#@&*?abcdefABCDEFxyz<>[]{}|/\\"

_GREEN      = QtGui.QColor( 90, 255, 120)
_GREEN_DIM  = QtGui.QColor( 40, 160,  70)
_HEAD_WHITE = QtGui.QColor(235, 255, 240)
_RED        = QtGui.QColor(255,  60,  60)

_WATERMARKS = ("CLASSIFIED", "TOP SECRET", "GHIDRA", "INTERCEPT")


class _Drop:
    __slots__ = ("y", "speed", "length", "glyphs", "flip_ms", "flip_period")

    def __init__(self, rng, rect):
        self.y = rng.uniform(-rect.height(), 0)
        self.speed = rng.uniform(80.0, 180.0)
        self.length = rng.randint(8, 22)
        self.glyphs = [rng.choice(_GLYPHS) for _ in range(self.length)]
        self.flip_ms = 0
        self.flip_period = rng.randint(80, 180)

    def advance(self, dt_ms, rng, rect):
        self.y += self.speed * (dt_ms / 1000.0)
        self.flip_ms += dt_ms
        if self.flip_ms >= self.flip_period:
            self.flip_ms = 0
            # scramble one random glyph in the column each flip
            i = rng.randrange(self.length)
            self.glyphs[i] = rng.choice(_GLYPHS)
        if self.y - self.length * _ROW_HEIGHT > rect.height():
            self.y = rng.uniform(-rect.height() * 0.3, 0)
            self.speed = rng.uniform(80.0, 180.0)
            self.length = rng.randint(8, 22)
            self.glyphs = [rng.choice(_GLYPHS) for _ in range(self.length)]


class _State:
    def __init__(self):
        self.rng = random.Random()
        self.drops = None
        self.last_tick_ms = 0
        # Shuffled watermark order -- different cartouche sequence each run
        self.watermarks = list(_WATERMARKS)
        self.rng.shuffle(self.watermarks)
        # Also randomize a few ambient parameters for variety
        self.rec_period_ms = self.rng.uniform(750.0, 1150.0)
        self.watermark_period_ms = self.rng.uniform(2500.0, 3500.0)


def _ensure_drops(state, rect):
    if state.drops is None:
        ncols = max(4, rect.width() // _COL_WIDTH)
        state.drops = [_Drop(state.rng, rect) for _ in range(ncols)]


def _draw_backdrop(painter, rect, fade):
    """Dark green wash. Kept low-alpha so the widget stays legible."""
    painter.fillRect(rect, QtGui.QColor(0, 18, 10, int(85 * fade)))


def _draw_rain(painter, rect, state, fade):
    font = make_font(10, bold=True, family="Courier New")
    painter.setFont(font)
    for i, drop in enumerate(state.drops):
        x = rect.left() + i * _COL_WIDTH
        for k, glyph in enumerate(drop.glyphs):
            y = drop.y - k * _ROW_HEIGHT
            if y < rect.top() - _ROW_HEIGHT or y > rect.bottom() + _ROW_HEIGHT:
                continue
            if k == 0:
                color = with_alpha(_HEAD_WHITE, int(235 * fade))
            else:
                col_fade = max(0.0, 1.0 - k / float(drop.length))
                color = with_alpha(_GREEN if k < 4 else _GREEN_DIM,
                                   int(215 * col_fade * fade))
            painter.setPen(color)
            painter.drawText(int(x), int(y), glyph)


def _draw_watermark(painter, rect, elapsed_ms, fade, state):
    """Rotating, cycling TOP-SECRET cartouche behind the rain (shuffled per run)."""
    idx = int(elapsed_ms / state.watermark_period_ms) % len(state.watermarks)
    text = state.watermarks[idx]
    painter.save()
    painter.translate(rect.center())
    painter.rotate(-18 + 4 * math.sin(elapsed_ms / 1500.0))
    size = int(max(18, min(rect.width() / 11, rect.height() / 6)))
    font = make_font(size)
    bbox = text_bbox(font, text)
    painter.setFont(font)
    painter.setPen(with_alpha(_RED, int(115 * fade)))
    painter.drawText(int(-bbox.width() / 2 - bbox.left()),
                     int(-bbox.height() / 2 - bbox.top()),
                     text)
    # inner thinner ring
    painter.setPen(with_alpha(_GREEN, int(90 * fade)))
    band = "-- -- -- -- -- -- -- -- -- -- -- -- -- --"
    small = make_font(max(8, size // 4))
    painter.setFont(small)
    sbb = text_bbox(small, band)
    painter.drawText(int(-sbb.width() / 2 - sbb.left()),
                     int(bbox.height() / 2 + sbb.height()),
                     band)
    painter.restore()


def _draw_rec(painter, rect, elapsed_ms, fade, state):
    """Pulsing red 'REC' dot + label in the top-right corner."""
    rec = pulse(elapsed_ms, state.rec_period_ms)
    painter.setPen(QtGui.QPen(NO_PEN))
    painter.setBrush(with_alpha(_RED, int((90 + 150 * rec) * fade)))
    painter.drawEllipse(QtCore.QRectF(rect.right() - 26, rect.top() + 10, 10, 10))
    font = make_font(9)
    painter.setFont(font)
    painter.setPen(with_alpha(QtGui.QColor(255, 230, 230), int(230 * fade)))
    painter.drawText(int(rect.right() - 46), int(rect.top() + 20), "REC")


def _draw_scanlines(painter, rect, fade):
    """Very subtle horizontal scan lines for CRT feel."""
    alpha = int(25 * fade)
    if alpha <= 0:
        return
    painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, alpha), 1))
    y = rect.top()
    while y < rect.bottom():
        painter.drawLine(rect.left(), y, rect.right(), y)
        y += 3


def _paint(painter, rect, elapsed_ms, overlay):
    state = ensure_state(overlay, _State)
    fade = fade_envelope(elapsed_ms, _DURATION_MS)
    _ensure_drops(state, rect)

    dt_ms = tick_dt_ms(state, elapsed_ms)
    for drop in state.drops:
        drop.advance(dt_ms, state.rng, rect)

    painter.setClipRect(rect)
    painter.setPen(QtGui.QPen(NO_PEN))

    _draw_backdrop(painter, rect, fade)
    _draw_watermark(painter, rect, elapsed_ms, fade, state)
    _draw_rain(painter, rect, state, fade)
    _draw_scanlines(painter, rect, fade)
    _draw_rec(painter, rect, elapsed_ms, fade, state)


register_scene("nsa", _DURATION_MS, _paint)
