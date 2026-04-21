"""Sine-wave scale pulse."""

import math

from ida_frustrated_core import QtCore, register_effect


def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)
    scale = 1.0 + 0.75 * math.sin(progress * math.pi)
    draw_rect = QtCore.QRect(0, 0, int(rect.width() * scale), int(rect.height() * scale))
    draw_rect.moveCenter(rect.center())
    painter.drawPixmap(draw_rect, snapshot)


register_effect("zoom", 850, _paint)
