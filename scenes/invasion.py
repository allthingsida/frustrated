# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""Invasion: copies of the app/window icon swoop, arc, and spiral across the widget.

A tip of the hat to Ghidra's `AnimationUtils.showTheDragonOverComponent(...)`
-- Ghidra's version flew a dragon icon; this one grabs whatever icon the
Qt application or the hosting IDA window is advertising and sends a flock
of them on varied trajectories. Falls back to a drawn sparkle glyph if
no icon is available.
"""

import math
import random

from core import QtCore, QtGui, QtWidgets, ALIGN_CENTER, register_scene
from scenes._common import fade_envelope


_DURATION_MS = 20000


def _best_icon(overlay):
    """Prefer the hosting window's icon (likely IDA's), then the QApplication icon."""
    candidates = []
    window = overlay.parentWidget()
    if window is not None:
        try:
            ic = window.windowIcon()
            if ic is not None and not ic.isNull():
                candidates.append(ic)
        except RuntimeError:
            pass
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            ic = app.windowIcon()
            if ic is not None and not ic.isNull():
                candidates.append(ic)
        except RuntimeError:
            pass
    return candidates[0] if candidates else None


class _Bogey:
    """One icon traversing the scene."""

    def __init__(self, rect, rng, birth_ms):
        self.birth_ms = birth_ms
        self.ttl_ms = rng.randint(3500, 6500)
        self.size = rng.uniform(28, 84)
        self.spin = rng.uniform(-160.0, 160.0)
        self.rot0 = rng.uniform(0.0, 360.0)

        self.kind = rng.choice(("straight", "arc", "swoop"))
        edge = rng.choice(("left", "right", "top", "bottom"))
        pad = self.size
        if edge == "left":
            self.x0 = rect.left() - pad
            self.y0 = rng.uniform(rect.top(), rect.bottom())
            self.vx = rng.uniform(110.0, 210.0)
            self.vy = rng.uniform(-50.0, 50.0)
        elif edge == "right":
            self.x0 = rect.right() + pad
            self.y0 = rng.uniform(rect.top(), rect.bottom())
            self.vx = -rng.uniform(110.0, 210.0)
            self.vy = rng.uniform(-50.0, 50.0)
        elif edge == "top":
            self.x0 = rng.uniform(rect.left(), rect.right())
            self.y0 = rect.top() - pad
            self.vx = rng.uniform(-60.0, 60.0)
            self.vy = rng.uniform(90.0, 180.0)
        else:  # bottom
            self.x0 = rng.uniform(rect.left(), rect.right())
            self.y0 = rect.bottom() + pad
            self.vx = rng.uniform(-60.0, 60.0)
            self.vy = -rng.uniform(90.0, 180.0)

        self.wave_amp = rng.uniform(35.0, 110.0) if self.kind == "arc" else 0.0
        self.wave_freq = rng.uniform(1.4, 3.2)
        # "swoop" = gentle gravity-like downward pull after entry
        self.swoop_g = 60.0 if self.kind == "swoop" else 0.0

    def position(self, elapsed_ms):
        t = (elapsed_ms - self.birth_ms) / 1000.0
        x = self.x0 + self.vx * t
        y = self.y0 + self.vy * t + 0.5 * self.swoop_g * t * t
        if self.kind == "arc" and self.wave_amp > 0:
            speed = math.hypot(self.vx, self.vy)
            if speed > 0:
                nx = -self.vy / speed
                ny = self.vx / speed
                phase = math.sin(t * self.wave_freq) * self.wave_amp
                x += nx * phase
                y += ny * phase
        return x, y

    def rotation(self, elapsed_ms):
        t = (elapsed_ms - self.birth_ms) / 1000.0
        return self.rot0 + self.spin * t

    def alpha(self, elapsed_ms):
        local = (elapsed_ms - self.birth_ms) / self.ttl_ms
        if local < 0.12:
            return local / 0.12
        if local > 0.80:
            return max(0.0, (1.0 - local) / 0.20)
        return 1.0

    def alive(self, elapsed_ms):
        return (elapsed_ms - self.birth_ms) < self.ttl_ms


class _State:
    def __init__(self):
        self.rng = random.Random()
        self.bogeys = []
        self.next_spawn_ms = 0
        self.icon = None
        self.icon_checked = False


def _draw_fallback(painter, size):
    font = QtGui.QFont()
    font.setPointSize(max(10, int(size * 0.65)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(255, 215, 64, 235))
    painter.drawText(
        QtCore.QRectF(-size, -size, size * 2, size * 2),
        ALIGN_CENTER,
        "*",
    )


def _paint(painter, rect, elapsed_ms, overlay):
    if overlay.state is None:
        overlay.state = _State()
    state = overlay.state
    if not state.icon_checked:
        state.icon = _best_icon(overlay)
        state.icon_checked = True

    rng = state.rng

    painter.setClipRect(rect)

    if elapsed_ms < _DURATION_MS * 0.85:
        while state.next_spawn_ms <= elapsed_ms:
            state.bogeys.append(_Bogey(rect, rng, elapsed_ms))
            state.next_spawn_ms = elapsed_ms + rng.randint(450, 1300)

    state.bogeys = [b for b in state.bogeys if b.alive(elapsed_ms)]

    overall = fade_envelope(elapsed_ms, _DURATION_MS)

    for b in state.bogeys:
        x, y = b.position(elapsed_ms)
        a = b.alpha(elapsed_ms) * overall
        if a <= 0.0:
            continue

        painter.save()
        painter.translate(x, y)
        painter.rotate(b.rotation(elapsed_ms))
        painter.setOpacity(a)

        if state.icon is not None:
            size_i = int(b.size)
            pixmap = state.icon.pixmap(QtCore.QSize(size_i, size_i))
            if not pixmap.isNull():
                painter.drawPixmap(-size_i // 2, -size_i // 2, pixmap)
            else:
                _draw_fallback(painter, b.size)
        else:
            _draw_fallback(painter, b.size)

        painter.restore()


register_scene("invasion", _DURATION_MS, _paint)
