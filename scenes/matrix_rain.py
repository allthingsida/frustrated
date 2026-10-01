# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""Matrix rain: dense green katakana-flavoured digital rain. No chrome, no text.

Columns of glyphs fall at independent speeds; the head of each column is
rendered bright white (the iconic "leading glyph" glow), the tail fades
through bright green to black. Glyphs scramble at random intervals so the
columns shimmer instead of reading as static strings. Occasionally a
column "dies" (goes quiet for a moment) and restarts from above, which
adds organic rhythm instead of perfectly-uniform rain.

Compared to the older `nsa` scene (which pairs a sparser rain with a
rotating CLASSIFIED cartouche + REC dot), this one is pure rain --
denser columns, narrower spacing, a brighter head, and no supplementary
chrome. Intended to feel like staring into the Matrix.
"""

from __future__ import annotations

import random

from core import QtCore, QtGui, NO_PEN, register_scene
from scenes._common import fade_envelope, with_alpha, ensure_state, tick_dt_ms


_DURATION_MS = 25000

_COL_WIDTH  = 12
_ROW_HEIGHT = 15

# Mix of katakana + latin + numbers + symbols. Fonts that lack katakana
# glyphs will render tofu boxes for those code points; keeping the ascii
# pool sizable ensures something legible still falls.
_GLYPHS_KATAKANA = (
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
)
_GLYPHS_ASCII = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz$#@%&*?!<>/\\|=+-[]{}"
_GLYPHS = _GLYPHS_KATAKANA + _GLYPHS_ASCII

# Classic Matrix green. Head glyph is near-white; tail cools to dark green.
_HEAD        = QtGui.QColor(220, 255, 230)
_HEAD_GLOW   = QtGui.QColor(140, 255, 200)
_GREEN_BRIGHT = QtGui.QColor( 80, 255, 130)
_GREEN_MID    = QtGui.QColor( 40, 200,  90)
_GREEN_DIM    = QtGui.QColor( 15, 120,  50)


class _Column:
    __slots__ = ("y", "speed", "length", "glyphs", "flip_ms", "flip_period",
                 "alive", "respawn_delay_ms", "rng_salt")

    def __init__(self, rng, rect):
        self._roll(rng, rect, initial=True)

    def _roll(self, rng, rect, initial):
        # Stagger initial spawn across the whole column so the screen isn't empty at t=0.
        if initial:
            self.y = rng.uniform(-rect.height() * 0.8, rect.height() * 0.4)
        else:
            self.y = rng.uniform(-rect.height() * 0.5, -_ROW_HEIGHT)
        self.speed = rng.uniform(110.0, 260.0)
        self.length = rng.randint(10, 28)
        self.glyphs = [rng.choice(_GLYPHS) for _ in range(self.length)]
        self.flip_ms = 0
        self.flip_period = rng.randint(70, 180)
        self.alive = True
        self.respawn_delay_ms = 0
        self.rng_salt = rng.random()

    def advance(self, dt_ms, rng, rect):
        if not self.alive:
            self.respawn_delay_ms -= dt_ms
            if self.respawn_delay_ms <= 0:
                self._roll(rng, rect, initial=False)
            return

        self.y += self.speed * (dt_ms / 1000.0)
        self.flip_ms += dt_ms
        if self.flip_ms >= self.flip_period:
            self.flip_ms = 0
            # Flip 1-3 random glyphs per tick for a shimmery "reading" feel.
            for _ in range(rng.randint(1, 3)):
                i = rng.randrange(self.length)
                self.glyphs[i] = rng.choice(_GLYPHS)

        if self.y - self.length * _ROW_HEIGHT > rect.height():
            # Small chance to go dark for a beat before respawning -- irregular rhythm.
            if rng.random() < 0.18:
                self.alive = False
                self.respawn_delay_ms = rng.randint(200, 1100)
            else:
                self._roll(rng, rect, initial=False)


class _State:
    def __init__(self):
        self.rng = random.Random()
        self.columns = None  # built lazily when we know the rect
        self.last_tick_ms = 0
        self.font = None
        # Per-run variety: slight speed/density jitter baked into each run's columns.
        self.base_speed_mult = self.rng.uniform(0.85, 1.15)


def _ensure_columns(state, rect):
    if state.columns is not None:
        return
    ncols = max(6, rect.width() // _COL_WIDTH)
    state.columns = [_Column(state.rng, rect) for _ in range(ncols)]
    for col in state.columns:
        col.speed *= state.base_speed_mult


def _ensure_font(state):
    if state.font is not None:
        return
    font = QtGui.QFont("Consolas", 11)
    font.setBold(True)
    state.font = font


def _draw_backdrop(painter, rect, fade):
    # A bit heavier than the NSA backdrop -- this scene *is* the rain, so we
    # let it darken the widget more. Still translucent so code stays legible.
    painter.fillRect(rect, QtGui.QColor(0, 8, 3, int(140 * fade)))


def _draw_column(painter, rect, col_x, col, fade):
    """Draw a single column: bright head + fading tail."""
    for k in range(col.length):
        y = col.y - k * _ROW_HEIGHT
        if y < rect.top() - _ROW_HEIGHT or y > rect.bottom() + _ROW_HEIGHT:
            continue

        glyph = col.glyphs[k]
        if k == 0:
            # The iconic leading glyph: paint a soft glow behind a near-white character.
            glow_color = with_alpha(_HEAD_GLOW, int(180 * fade))
            painter.setPen(glow_color)
            painter.drawText(int(col_x) - 1, int(y), glyph)
            painter.drawText(int(col_x) + 1, int(y), glyph)
            painter.setPen(with_alpha(_HEAD, int(250 * fade)))
            painter.drawText(int(col_x), int(y), glyph)
        else:
            # Tail: blend from bright through mid to dim as we walk up.
            t = k / float(col.length)
            if t < 0.25:
                color = _GREEN_BRIGHT
            elif t < 0.65:
                color = _GREEN_MID
            else:
                color = _GREEN_DIM
            alpha = int(235 * (1.0 - t) * fade)
            if alpha <= 0:
                continue
            painter.setPen(with_alpha(color, alpha))
            painter.drawText(int(col_x), int(y), glyph)


def _paint(painter, rect, elapsed_ms, overlay):
    state = ensure_state(overlay, _State)
    fade = fade_envelope(elapsed_ms, _DURATION_MS)
    _ensure_columns(state, rect)
    _ensure_font(state)

    dt_ms = tick_dt_ms(state, elapsed_ms)
    for col in state.columns:
        col.advance(dt_ms, state.rng, rect)

    painter.setClipRect(rect)
    painter.setPen(QtGui.QPen(NO_PEN))
    _draw_backdrop(painter, rect, fade)

    painter.setFont(state.font)
    for i, col in enumerate(state.columns):
        if not col.alive:
            continue
        col_x = rect.left() + i * _COL_WIDTH
        _draw_column(painter, rect, col_x, col, fade)


register_scene("matrix_rain", _DURATION_MS, _paint)
