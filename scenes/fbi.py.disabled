"""FBI: yellow/black caution tape, a wandering flashlight, and a sliding banner.

Top and bottom crime-scene stripes scroll in opposite directions. A soft
flashlight cone drifts across the middle. A "FBI - OPEN UP!" banner slides
right-to-left once per scene. Designed to stay transparent enough that
the widget beneath remains readable.
"""

from __future__ import annotations

import math
import random

from core import QtCore, QtGui, NO_PEN, register_scene
from scenes._common import (
    fade_envelope, with_alpha, ensure_state, make_font, text_bbox,
)


_DURATION_MS = 18000

_YELLOW = QtGui.QColor(255, 205, 0)
_BLACK  = QtGui.QColor(0, 0, 0)
_WHITE  = QtGui.QColor(255, 255, 255)

_BANNERS = (
    "FBI -- OPEN UP!",
    "FEDERAL BUREAU OF INVESTIGATION",
    "WE HAVE A WARRANT",
    "STEP AWAY FROM THE DISASSEMBLY",
    "THIS IS A RAID",
    "HANDS WHERE WE CAN SEE THEM",
    "YOU ARE UNDER INVESTIGATION",
    "SURRENDER THE BINARIES",
)


class _State:
    def __init__(self):
        rng = random.Random()
        self.banner_text = rng.choice(_BANNERS)


def _draw_caution_tape(painter, rect, y, height, shift, fade):
    """Diagonal yellow/black stripes of given height at vertical `y`."""
    painter.setPen(QtGui.QPen(NO_PEN))
    painter.fillRect(QtCore.QRectF(rect.left(), y, rect.width(), height),
                     with_alpha(_YELLOW, int(200 * fade)))
    painter.setBrush(with_alpha(_BLACK, int(200 * fade)))
    stripe_w = height
    x = rect.left() - height + (shift % (stripe_w * 2))
    while x < rect.right() + height:
        path = QtGui.QPainterPath()
        path.moveTo(x, y)
        path.lineTo(x + stripe_w, y)
        path.lineTo(x + stripe_w - height, y + height)
        path.lineTo(x - height, y + height)
        path.closeSubpath()
        painter.drawPath(path)
        x += stripe_w * 2


def _draw_flashlight(painter, rect, elapsed_ms, fade):
    """A soft white radial cone drifting horizontally through the middle."""
    t = elapsed_ms / 1000.0
    cx = rect.left() + rect.width() * (0.5 + 0.38 * math.sin(t * 0.7))
    cy = rect.center().y() + rect.height() * 0.10 * math.sin(t * 0.5 + 1.2)
    r = max(rect.width(), rect.height()) * 0.25
    grad = QtGui.QRadialGradient(cx, cy, r)
    grad.setColorAt(0.0, QtGui.QColor(255, 255, 220, int(85 * fade)))
    grad.setColorAt(0.7, QtGui.QColor(255, 255, 220, int(18 * fade)))
    grad.setColorAt(1.0, QtGui.QColor(255, 255, 220, 0))
    painter.fillRect(rect, QtGui.QBrush(grad))


def _draw_backdrop(painter, rect, fade):
    """Very light darkening wash so tape/banner pop without drowning the widget."""
    painter.fillRect(rect, QtGui.QColor(10, 10, 15, int(55 * fade)))


def _draw_banner(painter, rect, elapsed_ms, fade, state):
    """Sliding banner across the center, once per scene. Text is randomized per run."""
    font = make_font(int(max(16, rect.height() * 0.14)))
    text = state.banner_text
    bbox = text_bbox(font, text)
    total_travel = rect.width() + bbox.width() + 80
    duration_s = _DURATION_MS / 1000.0 * 0.9
    speed = total_travel / duration_s
    x = rect.right() + 40 - (elapsed_ms / 1000.0) * speed
    y = rect.center().y()
    # dark chip background behind the text, for legibility even at low alpha
    pad = 10
    chip = QtCore.QRectF(x - pad, y - bbox.height() / 2 - pad,
                         bbox.width() + pad * 2, bbox.height() + pad * 2)
    painter.setPen(QtGui.QPen(NO_PEN))
    painter.setBrush(with_alpha(_BLACK, int(170 * fade)))
    painter.drawRoundedRect(chip, 6, 6)
    painter.setPen(with_alpha(_YELLOW, int(245 * fade)))
    painter.setFont(font)
    painter.drawText(int(x), int(y + bbox.height() / 2 - bbox.bottom()), text)


def _paint(painter, rect, elapsed_ms, overlay):
    state = ensure_state(overlay, _State)
    fade = fade_envelope(elapsed_ms, _DURATION_MS)
    painter.setClipRect(rect)

    _draw_backdrop(painter, rect, fade)
    _draw_flashlight(painter, rect, elapsed_ms, fade)

    tape_h = max(14, int(rect.height() * 0.055))
    shift = int(elapsed_ms * 0.06)
    _draw_caution_tape(painter, rect, rect.top(), tape_h, shift, fade)
    _draw_caution_tape(painter, rect, rect.bottom() - tape_h, tape_h, -shift, fade)

    _draw_banner(painter, rect, elapsed_ms, fade, state)


register_scene("fbi", _DURATION_MS, _paint)
