"""Weather: a 30-second atmospheric story -- sunny, gloomy, storm, clearing.

Continuously interpolates between keyframes. Raindrops, drifting clouds,
and the occasional lightning bolt are spawned from phase-driven rates.
Designed to stay legible: the sky is a moderate alpha wash so widget
contents remain readable through the tint.
"""

import math
import random

from core import QtCore, QtGui, NO_PEN, NO_BRUSH, register_scene
from scenes._common import fade_envelope


_DURATION_MS = 30000


# Phase keyframes.
# (t, sky_top_rgb, sky_bot_rgb, sun_alpha, clouds_per_sec, cloud_darkness, drops_per_sec, flashes_per_sec)
_PHASES = (
    (0.00, (135, 206, 235), (195, 228, 245), 1.00, 0.4, 0.00,  0.0, 0.00),  # sunny
    (0.15, (150, 190, 220), (210, 220, 230), 0.70, 1.2, 0.20,  0.0, 0.00),  # partly cloudy
    (0.30, (105, 125, 150), (150, 165, 180), 0.15, 2.3, 0.55,  4.0, 0.05),  # gathering
    (0.50, ( 65,  80, 100), (100, 115, 135), 0.00, 2.8, 0.85, 28.0, 0.45),  # storm peak
    (0.70, (110, 135, 165), (165, 180, 195), 0.30, 1.4, 0.35,  5.0, 0.05),  # clearing
    (1.00, (140, 200, 230), (200, 225, 240), 0.95, 0.4, 0.00,  0.0, 0.00),  # sun back out
)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_rgb(c1, c2, t):
    return (int(_lerp(c1[0], c2[0], t)),
            int(_lerp(c1[1], c2[1], t)),
            int(_lerp(c1[2], c2[2], t)))


def _sample_phase(t):
    for i in range(len(_PHASES) - 1):
        t0 = _PHASES[i][0]
        t1 = _PHASES[i + 1][0]
        if t <= t1:
            p0 = _PHASES[i]
            p1 = _PHASES[i + 1]
            local = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return (_lerp_rgb(p0[1], p1[1], local),
                    _lerp_rgb(p0[2], p1[2], local),
                    _lerp(p0[3], p1[3], local),
                    _lerp(p0[4], p1[4], local),
                    _lerp(p0[5], p1[5], local),
                    _lerp(p0[6], p1[6], local),
                    _lerp(p0[7], p1[7], local))
    last = _PHASES[-1]
    return last[1], last[2], last[3], last[4], last[5], last[6], last[7]


class _State:
    def __init__(self):
        self.rng = random.Random()
        self.clouds = []
        self.drops = []
        self.flash_ms_left = 0
        self.flash_path = None
        self.next_cloud_ms = 0
        self.next_drop_ms = 0
        self.next_flash_ms = 3000
        self.last_tick_ms = 0


def _spawn_cloud(rect, state, darkness):
    rng = state.rng
    scale = rng.uniform(0.55, 1.4)
    y = rect.top() + rng.uniform(0, rect.height() * 0.6)
    x = rect.left() - 160 * scale
    speed = rng.uniform(22, 55) * (0.7 + darkness * 0.8)
    alpha = int(165 + 70 * darkness)
    puffs = []
    for _ in range(rng.randint(3, 6)):
        puffs.append((
            rng.uniform(-55, 55) * scale,
            rng.uniform(-14, 14) * scale,
            rng.uniform(22, 42) * scale,
        ))
    state.clouds.append({
        "x": x, "y": y, "scale": scale, "speed": speed,
        "alpha": alpha, "darkness": darkness, "puffs": puffs,
    })


def _spawn_drop(rect, state):
    rng = state.rng
    state.drops.append({
        "x": rng.uniform(rect.left() - 20, rect.right() + 20),
        "y": rect.top() + rng.uniform(-30, 0),
        "vx": rng.uniform(-140, -90),
        "vy": rng.uniform(520, 780),
        "len": rng.uniform(9, 16),
    })


def _build_bolt(x, y_top, y_bot, rng):
    path = QtGui.QPainterPath()
    path.moveTo(x, y_top)
    steps = rng.randint(5, 8)
    cx = x
    for i in range(1, steps + 1):
        ny = y_top + (y_bot - y_top) * (i / steps)
        cx = cx + rng.uniform(-45, 45)
        path.lineTo(cx, ny)
    return path


def _advance(state, dt_ms, rect, phase):
    _sky_t, _sky_b, _sun, cloud_rate, cloud_dark, rain_rate, flash_rate = phase
    dt = dt_ms / 1000.0
    rng = state.rng

    alive = []
    for c in state.clouds:
        c["x"] += c["speed"] * dt
        if c["x"] <= rect.right() + 200:
            alive.append(c)
    state.clouds = alive

    state.next_cloud_ms -= dt_ms
    if cloud_rate > 0:
        while state.next_cloud_ms <= 0:
            _spawn_cloud(rect, state, cloud_dark)
            state.next_cloud_ms += int(1000.0 / cloud_rate)
    else:
        state.next_cloud_ms = 1000

    alive = []
    for d in state.drops:
        d["x"] += d["vx"] * dt
        d["y"] += d["vy"] * dt
        if d["y"] <= rect.bottom() + 24:
            alive.append(d)
    state.drops = alive

    state.next_drop_ms -= dt_ms
    if rain_rate > 0:
        while state.next_drop_ms <= 0:
            _spawn_drop(rect, state)
            state.next_drop_ms += int(1000.0 / rain_rate)
    else:
        state.next_drop_ms = 200

    state.next_flash_ms -= dt_ms
    if state.next_flash_ms <= 0 and flash_rate > 0:
        state.flash_ms_left = 180
        bolt_x = rng.uniform(rect.left() + 50, rect.right() - 50)
        state.flash_path = _build_bolt(bolt_x, rect.top(), rect.bottom() - 40, rng)
        state.next_flash_ms = int(1000.0 / flash_rate) + rng.randint(-400, 1800)

    if state.flash_ms_left > 0:
        state.flash_ms_left = max(0, state.flash_ms_left - dt_ms)


def _paint(painter, rect, elapsed_ms, overlay):
    if overlay.state is None:
        overlay.state = _State()
    state = overlay.state

    dt_ms = max(1, elapsed_ms - state.last_tick_ms)
    state.last_tick_ms = elapsed_ms

    t = min(1.0, elapsed_ms / _DURATION_MS)
    fade = fade_envelope(elapsed_ms, _DURATION_MS)

    phase = _sample_phase(t)
    sky_top, sky_bot, sun, _cloud_rate, _cloud_dark, _rain_rate, _flash_rate = phase

    _advance(state, dt_ms, rect, phase)

    painter.setClipRect(rect)

    base_alpha = int(110 * fade)  # kept low so the widget underneath stays legible
    gradient = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, QtGui.QColor(sky_top[0], sky_top[1], sky_top[2], base_alpha))
    gradient.setColorAt(1.0, QtGui.QColor(sky_bot[0], sky_bot[1], sky_bot[2], base_alpha))
    painter.fillRect(rect, QtGui.QBrush(gradient))

    if state.flash_ms_left > 0:
        flash_t = state.flash_ms_left / 180.0
        painter.fillRect(rect, QtGui.QColor(255, 255, 220, int(150 * flash_t * fade)))

    if sun > 0.01:
        sun_alpha = int(220 * sun * fade)
        sun_r = max(20, min(50, rect.width() // 18))
        sun_x = rect.right() - sun_r - 20
        sun_y = rect.top() + sun_r + 20
        glow = QtGui.QRadialGradient(sun_x, sun_y, sun_r * 2.8)
        glow.setColorAt(0.0, QtGui.QColor(255, 240, 150, sun_alpha))
        glow.setColorAt(0.4, QtGui.QColor(255, 220, 100, int(sun_alpha * 0.55)))
        glow.setColorAt(1.0, QtGui.QColor(255, 200,  80, 0))
        painter.setPen(QtGui.QPen(NO_PEN))
        painter.setBrush(QtGui.QBrush(glow))
        painter.drawEllipse(QtCore.QPointF(sun_x, sun_y), sun_r * 2.8, sun_r * 2.8)
        painter.setBrush(QtGui.QColor(255, 240, 180, sun_alpha))
        painter.drawEllipse(QtCore.QPointF(sun_x, sun_y), sun_r, sun_r)

    painter.setPen(QtGui.QPen(NO_PEN))
    for c in state.clouds:
        gray = int(250 - 165 * c["darkness"])
        painter.setBrush(QtGui.QColor(gray, gray, gray, int(c["alpha"] * fade)))
        for (px, py, pr) in c["puffs"]:
            painter.drawEllipse(QtCore.QPointF(c["x"] + px, c["y"] + py), pr, pr)

    if state.drops:
        rain_pen = QtGui.QPen(QtGui.QColor(185, 205, 235, int(180 * fade)))
        rain_pen.setWidth(2)
        painter.setPen(rain_pen)
        for d in state.drops:
            tail_x = d["x"] - d["vx"] * 0.022
            tail_y = d["y"] - d["vy"] * 0.022
            painter.drawLine(QtCore.QPointF(tail_x, tail_y),
                             QtCore.QPointF(d["x"],  d["y"]))

    if state.flash_ms_left > 0 and state.flash_path is not None:
        bolt_pen = QtGui.QPen(QtGui.QColor(255, 245, 180, int(255 * fade)))
        bolt_pen.setWidth(3)
        painter.setPen(bolt_pen)
        painter.setBrush(QtGui.QBrush(NO_BRUSH))
        painter.drawPath(state.flash_path)


register_scene("weather", _DURATION_MS, _paint)
