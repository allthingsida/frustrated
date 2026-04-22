"""Lava lamp: warm metaball-ish blobs drift up and sink back down.

Each blob is drawn as a soft radial gradient that fades to fully transparent
at its edge. Where blobs overlap, the alpha stacks and the overlap region
reads as a merged shape -- a cheap metaball approximation without any
marching-squares math. Three palette presets (warm orange, acid green,
electric pink) shuffle in per run. Pure ambient mood, no text or UI chrome.
"""

from __future__ import annotations

import math
import random

from core import QtCore, QtGui, NO_PEN, register_scene
from scenes._common import fade_envelope, with_alpha, ensure_state, pulse


_DURATION_MS = 30000


# Each palette: (name, core_color, rim_color, backdrop_top, backdrop_bottom).
_PALETTES = (
    ("warm",
     QtGui.QColor(255, 160,  60),
     QtGui.QColor(255,  70,  30),
     QtGui.QColor( 45,  15,  10),
     QtGui.QColor( 90,  30,  15)),
    ("acid",
     QtGui.QColor(170, 255,  90),
     QtGui.QColor( 40, 200,  60),
     QtGui.QColor( 10,  30,  15),
     QtGui.QColor( 25,  70,  30)),
    ("pink",
     QtGui.QColor(255, 120, 210),
     QtGui.QColor(220,  40, 170),
     QtGui.QColor( 30,  10,  40),
     QtGui.QColor( 70,  20,  75)),
)


class _Blob:
    __slots__ = ("base_x_frac", "sway_amp_frac", "sway_period_ms",
                 "rise_period_ms", "phase", "radius_frac",
                 "radius_pulse_period_ms", "radius_pulse_phase")

    def __init__(self, rng):
        self.base_x_frac = rng.uniform(0.18, 0.82)
        self.sway_amp_frac = rng.uniform(0.05, 0.14)
        self.sway_period_ms = rng.uniform(4500.0, 8500.0)
        self.rise_period_ms = rng.uniform(9000.0, 16000.0)
        self.phase = rng.uniform(0.0, 1.0)
        # Radius scales off the smaller widget dimension so blobs stay
        # proportionate on narrow tool windows and wide disassembly views.
        self.radius_frac = rng.uniform(0.14, 0.26)
        self.radius_pulse_period_ms = rng.uniform(2800.0, 5400.0)
        self.radius_pulse_phase = rng.uniform(0.0, 1.0)


class _Bubble:
    """Tiny static specular highlight near the top -- sells the glass jar feel."""
    __slots__ = ("x_frac", "y_frac", "r", "twinkle_period", "twinkle_phase")

    def __init__(self, rng):
        self.x_frac = rng.uniform(0.08, 0.92)
        self.y_frac = rng.uniform(0.05, 0.22)
        self.r = rng.uniform(1.0, 2.4)
        self.twinkle_period = rng.uniform(1800.0, 3600.0)
        self.twinkle_phase = rng.uniform(0.0, 1.0)


class _State:
    def __init__(self):
        self.rng = random.Random()
        self.palette = self.rng.choice(_PALETTES)
        n_blobs = self.rng.randint(5, 8)
        self.blobs = [_Blob(self.rng) for _ in range(n_blobs)]
        self.bubbles = [_Bubble(self.rng) for _ in range(self.rng.randint(8, 14))]


def _draw_backdrop(painter, rect, palette, fade):
    _, _, _, bg_top, bg_bot = palette
    grad = QtGui.QLinearGradient(rect.center().x(), rect.top(),
                                 rect.center().x(), rect.bottom())
    grad.setColorAt(0.0, with_alpha(bg_top, int(150 * fade)))
    grad.setColorAt(1.0, with_alpha(bg_bot, int(130 * fade)))
    painter.fillRect(rect, QtGui.QBrush(grad))


def _blob_position(blob, elapsed_ms, rect):
    """Return (cx, cy, radius_px) for the blob at this instant."""
    t_rise = elapsed_ms / blob.rise_period_ms + blob.phase
    # Smooth sinusoid: blob rises from near-bottom, hovers at top, sinks back.
    # Use half-sine so the blob stays within a meaningful vertical band.
    y_frac = 0.5 - 0.42 * math.sin(2 * math.pi * t_rise)
    cy = rect.top() + rect.height() * y_frac

    sway = math.sin(2 * math.pi * (elapsed_ms / blob.sway_period_ms + blob.phase))
    cx = rect.left() + rect.width() * (blob.base_x_frac + blob.sway_amp_frac * sway)

    r_mult = 1.0 + 0.18 * (pulse(elapsed_ms, blob.radius_pulse_period_ms,
                                  blob.radius_pulse_phase) - 0.5) * 2.0
    r_px = min(rect.width(), rect.height()) * blob.radius_frac * r_mult
    return cx, cy, r_px


def _draw_blob(painter, cx, cy, r_px, core_color, rim_color, fade):
    grad = QtGui.QRadialGradient(cx, cy, r_px)
    grad.setColorAt(0.00, with_alpha(core_color, int(200 * fade)))
    grad.setColorAt(0.45, with_alpha(core_color, int(120 * fade)))
    grad.setColorAt(0.80, with_alpha(rim_color, int(45 * fade)))
    grad.setColorAt(1.00, with_alpha(rim_color, 0))
    painter.setBrush(QtGui.QBrush(grad))
    painter.drawEllipse(QtCore.QPointF(cx, cy), r_px, r_px)


def _draw_bubbles(painter, rect, state, elapsed_ms, fade):
    painter.setPen(QtGui.QPen(NO_PEN))
    for b in state.bubbles:
        twinkle = 0.4 + 0.6 * pulse(elapsed_ms, b.twinkle_period, b.twinkle_phase)
        alpha = int(190 * twinkle * fade)
        if alpha <= 0:
            continue
        cx = rect.left() + rect.width() * b.x_frac
        cy = rect.top() + rect.height() * b.y_frac
        painter.setBrush(QtGui.QColor(255, 240, 220, alpha))
        painter.drawEllipse(QtCore.QPointF(cx, cy), b.r, b.r)


def _paint(painter, rect, elapsed_ms, overlay):
    state = ensure_state(overlay, _State)
    fade = fade_envelope(elapsed_ms, _DURATION_MS)

    painter.setClipRect(rect)
    painter.setPen(QtGui.QPen(NO_PEN))

    _draw_backdrop(painter, rect, state.palette, fade)

    _, core_color, rim_color, _, _ = state.palette
    for blob in state.blobs:
        cx, cy, r_px = _blob_position(blob, elapsed_ms, rect)
        _draw_blob(painter, cx, cy, r_px, core_color, rim_color, fade)

    _draw_bubbles(painter, rect, state, elapsed_ms, fade)


register_scene("lava_lamp", _DURATION_MS, _paint)
