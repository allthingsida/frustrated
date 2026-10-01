# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""Cartoon rage: red-washed shake, POW starburst, and floating swear symbols."""

import math
import random

from core import QtCore, QtGui, register_effect


_SYMBOLS = "@#$%&!*?"
_COLORS = (
    (210, 30, 30),
    (230, 110, 20),
    (20, 20, 20),
    (90, 30, 140),
)


def _spawn(rect):
    rng = random.Random()
    w, h = max(1, rect.width()), max(1, rect.height())
    count = rng.randint(10, 14)
    particles = []
    for _ in range(count):
        particles.append((
            rng.choice(_SYMBOLS),
            int(rect.left() + rng.uniform(w * 0.15, w * 0.85)),
            int(rect.top()  + rng.uniform(0.0,     h * 0.55)),
            rng.uniform(-40.0, 40.0),
            rng.uniform(-260.0, -140.0),
            rng.uniform(-30.0, 30.0),
            rng.uniform(-180.0, 180.0),
            rng.choice(_COLORS),
            rng.randint(18, 34),
            rng.uniform(0.0, 0.35),
        ))
    return particles


def _star_path(center, outer, inner, points=10):
    path = QtGui.QPainterPath()
    cx, cy = center.x(), center.y()
    for i in range(points * 2):
        r = outer if (i % 2 == 0) else inner
        angle = math.pi / points * i - math.pi / 2
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)

    if not hasattr(overlay, "_rage_state"):
        overlay._rage_state = _spawn(rect)
    particles = overlay._rage_state

    # Layer 1: shaking, red-washed widget
    envelope = math.sin(progress * math.pi)
    amp_x = max(4, min(24, rect.width()  // 22)) * envelope
    amp_y = max(3, min(18, rect.height() // 30)) * envelope
    ox = int(amp_x * math.sin(progress * math.pi * 14))
    oy = int(amp_y * math.sin(progress * math.pi * 11 + 0.7))
    draw_rect = QtCore.QRect(rect)
    draw_rect.translate(ox, oy)
    painter.drawPixmap(draw_rect, snapshot)

    wash_alpha = int(70 * envelope)
    if wash_alpha > 0:
        painter.fillRect(draw_rect, QtGui.QColor(220, 40, 40, wash_alpha))

    # Layer 2: POW starburst
    if progress < 0.85:
        burst = min(1.0, progress / 0.25)
        outer_r = min(rect.width(), rect.height()) * 0.35 * burst
        if outer_r > 1.0:
            if progress < 0.6:
                burst_alpha = 255
            else:
                burst_alpha = max(0, int(255 * (1.0 - (progress - 0.6) / 0.25)))

            painter.save()
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 210, 40, burst_alpha)))
            pen = QtGui.QPen(QtGui.QColor(200, 30, 30, burst_alpha))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawPath(_star_path(rect.center(), outer_r, outer_r * 0.45, points=10))

            label = "POW!"
            font = QtGui.QFont()
            font.setBold(True)
            font.setPointSize(max(10, int(min(rect.width(), rect.height()) / 12)))
            painter.setFont(font)
            painter.setPen(QtGui.QColor(30, 10, 10, burst_alpha))
            metrics = QtGui.QFontMetrics(font)
            text_rect = metrics.boundingRect(label)
            painter.drawText(
                rect.center().x() - text_rect.width()  // 2,
                rect.center().y() + text_rect.height() // 3,
                label,
            )
            painter.restore()

    # Layer 3: floating swear symbols
    for (char, x0, y0, vx, vy, rot0, spin, color, size, t0) in particles:
        if progress < t0:
            continue
        p = (progress - t0) / max(1e-3, 1.0 - t0)
        alpha = max(0, int(255 * (1.0 - p * p)))
        if alpha == 0:
            continue

        painter.save()
        painter.translate(x0 + vx * p, y0 + vy * p)
        painter.rotate(rot0 + spin * p)
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(size)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(color[0], color[1], color[2], alpha))
        painter.drawText(0, 0, char)
        painter.restore()


register_effect("rage", 1200, _paint)
