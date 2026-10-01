# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""Shared helpers for scene animations.

Intentionally small. Pulls Qt classes from `core` so every
scene keeps going through the same Qt-binding probe (PySide6/PyQt6/PySide2/
PyQt5). The `_` prefix in the filename keeps `load_animations()` from
importing this module as a scene.
"""

from __future__ import annotations

import math

from core import QtCore, QtGui


def fade_envelope(elapsed_ms, duration_ms, in_ms=500, out_ms=2000):
    """Return a 0 -> 1 -> 0 envelope using absolute-millisecond ramps.

    Defaults: 0.5 s fade-in, 2 s fade-out -- uniform across all scenes so
    the feel is consistent regardless of total duration. The plateau in
    the middle holds at 1.0. Scenes that need a different feel can pass
    custom `in_ms` / `out_ms`.
    """
    if duration_ms <= 0:
        return 0.0
    if elapsed_ms < in_ms:
        return max(0.0, elapsed_ms / in_ms)
    remaining = duration_ms - elapsed_ms
    if remaining < out_ms:
        return max(0.0, remaining / out_ms)
    return 1.0


def lerp(a, b, t):
    return a + (b - a) * t


def with_alpha(color, alpha):
    """Return a copy of `color` with a new alpha (0-255, clamped)."""
    c = QtGui.QColor(color)
    c.setAlpha(int(max(0, min(255, alpha))))
    return c


def ensure_state(overlay, factory):
    """Initialize `overlay.state` once via `factory()`; return it."""
    if overlay.state is None:
        overlay.state = factory()
    return overlay.state


def tick_dt_ms(state, elapsed_ms, attr="last_tick_ms"):
    """Return ms since the last call. Requires `state` to carry `attr` (default 'last_tick_ms')."""
    prev = getattr(state, attr, 0)
    setattr(state, attr, elapsed_ms)
    return max(1, elapsed_ms - prev)


def strobe(elapsed_ms, period_ms, phase=0.0, sharpness=3):
    """Sharp-peaked 0..1 strobe using a powered sine; defaults feel like a siren flash."""
    if period_ms <= 0:
        return 0.0
    a = math.sin(2 * math.pi * (elapsed_ms / period_ms + phase))
    return max(0.0, a) ** sharpness


def pulse(elapsed_ms, period_ms, phase=0.0):
    """Smooth 0..1..0 sinusoidal pulse."""
    if period_ms <= 0:
        return 0.0
    return 0.5 + 0.5 * math.sin(2 * math.pi * (elapsed_ms / period_ms + phase))


def text_bbox(font, text):
    """Portable text bounding rect (QRect)."""
    fm = QtGui.QFontMetrics(font)
    return fm.boundingRect(text)


def draw_centered_text(painter, center_x, center_y, text, font, color):
    """Draw `text` centered exactly around (center_x, center_y) with the given font + color."""
    painter.setFont(font)
    painter.setPen(color)
    r = text_bbox(font, text)
    painter.drawText(int(center_x - r.width() / 2 - r.left()),
                     int(center_y - r.height() / 2 - r.top()),
                     text)


def make_font(size, bold=True, family=None):
    """Small QFont factory with defaults that read well on pixel overlays."""
    font = QtGui.QFont() if family is None else QtGui.QFont(family)
    font.setBold(bold)
    font.setPointSize(int(size))
    return font
