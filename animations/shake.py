"""Horizontal sine-wave shake."""

import math

from ida_frustrated_core import QtCore, register_effect


def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)
    amplitude = max(8, min(28, rect.width() // 18))
    offset = int(math.sin(progress * math.pi * 8) * amplitude)
    draw_rect = QtCore.QRect(rect)
    draw_rect.translate(offset, 0)
    painter.drawPixmap(draw_rect, snapshot)


register_effect("shake", 425, _paint)
