# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""Space Invaders: a ~30-second self-playing arcade simulation.

Canonical SI in miniature: 5 x 11 alien grid with three alien types
(squid, crab, octopus) across five row-colored ranks, a player ship that
auto-tracks the closest column and fires on a cooldown, alien bullets
falling from the bottom-most alien in random columns, four destructible
bunkers, and an occasional UFO flyover for bonus points.

The march speeds up as aliens die -- the iconic difficulty ramp from
1978.

Everything renders on a virtual 224 x 256 arcade canvas that scales
uniformly to fit the target widget, with antialiasing off for
pixel-art crispness. Self-contained -- no bundled assets.
"""

import random

from core import (
    QtCore, QtGui, NO_PEN, ANTIALIASING, ALIGN_CENTER, register_scene,
)
from scenes._common import fade_envelope


_DURATION_MS = 30000

_CANVAS_W = 224
_CANVAS_H = 256

_CELL_W = 16
_CELL_H = 14
_GRID_ORIGIN_X = 24
_GRID_ORIGIN_Y = 44

# Sprites. '#' = lit pixel. Two frames per alien type for the march animation.
_SQUID_A = [
    "..####..",
    ".######.",
    "########",
    "##.##.##",
    "########",
    "..#..#..",
    ".#.##.#.",
    "#.#..#.#",
]
_SQUID_B = [
    "..####..",
    ".######.",
    "########",
    "##.##.##",
    "########",
    ".#.##.#.",
    "#......#",
    ".#....#.",
]
_CRAB_A = [
    ".#.......#.",
    "..#.....#..",
    ".#########.",
    "##.#####.##",
    "###########",
    "#.#######.#",
    "#.#.....#.#",
    "...##.##...",
]
_CRAB_B = [
    ".#.......#.",
    "#.#.....#.#",
    "#.#######.#",
    "##.#####.##",
    "###########",
    ".#########.",
    "..#.....#..",
    ".#.......#.",
]
_OCTO_A = [
    "....####....",
    ".##########.",
    "############",
    "###.####.###",
    "############",
    "...##..##...",
    "..##.##.##..",
    "##........##",
]
_OCTO_B = [
    "....####....",
    ".##########.",
    "############",
    "###.####.###",
    "############",
    "..##.##.##..",
    ".#..#..#..#.",
    "#.#......#.#",
]

_PLAYER = [
    "......#......",
    ".....###.....",
    ".....###.....",
    ".###########.",
    "#############",
    "#############",
    "#############",
    "#############",
]

_UFO = [
    "....########....",
    "...##########...",
    "..############..",
    ".##.##.##.##.##.",
    "################",
    ".##############.",
    "...###....###...",
    "....#......#....",
]

# (sprite_a, sprite_b, color, points)
_ROW_CONFIG = (
    (_SQUID_A, _SQUID_B, QtGui.QColor(255, 110, 150), 30),
    (_CRAB_A,  _CRAB_B,  QtGui.QColor(240, 210,  80), 20),
    (_CRAB_A,  _CRAB_B,  QtGui.QColor(240, 210,  80), 20),
    (_OCTO_A,  _OCTO_B,  QtGui.QColor( 90, 230, 120), 10),
    (_OCTO_A,  _OCTO_B,  QtGui.QColor( 90, 230, 120), 10),
)


_BUNKER_SHAPE = [
    "...############...",
    "..##############..",
    ".################.",
    "##################",
    "##################",
    "##################",
    "##################",
    "##################",
    "#####........#####",
    "####..........####",
    "###............###",
    "##..............##",
]
_BUNKER_W = len(_BUNKER_SHAPE[0])
_BUNKER_H = len(_BUNKER_SHAPE)
_BUNKER_Y = _CANVAS_H - 44
_BUNKER_XS = (20, 72, 124, 176)  # four bunkers across the bottom


# Color palettes (RGB tuples). One is picked at random per run.
# "rows" is row-indexed (5 rows). Other keys cover player / UFO / bunker sprites.
_PALETTES = (
    # Classic arcade-overlay
    {"rows": ((255, 110, 150), (240, 210,  80), (240, 210,  80), ( 90, 230, 120), ( 90, 230, 120)),
     "player": ( 90, 230, 120), "ufo": (255,  80,  80), "bunker": ( 90, 230, 120)},
    # Monochrome green CRT
    {"rows": ((150, 255, 170), (100, 220, 110), (100, 220, 110), ( 60, 170,  70), ( 60, 170,  70)),
     "player": (150, 255, 170), "ufo": (200, 255, 220), "bunker": (100, 220, 110)},
    # Cyberpunk magenta / cyan
    {"rows": ((255,  80, 255), ( 80, 255, 255), ( 80, 255, 255), (180, 180, 255), (180, 180, 255)),
     "player": ( 80, 255, 200), "ufo": (255, 220,  60), "bunker": (180, 180, 255)},
    # Sunset warm
    {"rows": ((255, 120,  60), (255, 200,  60), (255, 200,  60), (255,  80, 120), (255,  80, 120)),
     "player": (255, 200,  80), "ufo": ( 80, 200, 255), "bunker": (255, 200,  80)},
    # Amber terminal
    {"rows": ((255, 200,  80), (255, 170,  40), (255, 170,  40), (240, 140,  20), (240, 140,  20)),
     "player": (255, 210,  90), "ufo": (255,  80,  80), "bunker": (255, 180,  50)},
)


def _sprite_w(sprite):
    return len(sprite[0])


def _sprite_h(sprite):
    return len(sprite)


class _Game:
    def __init__(self):
        self.rng = random.Random()
        self.palette = self.rng.choice(_PALETTES)
        self.aliens = [
            {"col": c, "row": r, "alive": True}
            for r in range(5) for c in range(11)
        ]
        self.shift_x = 0
        self.shift_y = 0
        self.march_dir = 1
        self.march_timer = 0
        self.march_frame = 0
        self.player_x = _CANVAS_W / 2
        self.target_x = self.player_x
        self.player_shots = []
        self.alien_shots = []
        self.player_cooldown = 500
        self.alien_cooldown = 1200
        self.ufo_x = None
        self.ufo_cooldown = 6500
        self.score = 0
        self.bunkers = [
            [list(row) for row in _BUNKER_SHAPE] for _ in _BUNKER_XS
        ]
        self.outcome = None  # None, "win", "lose"
        self.last_tick_ms = 0


def _alive(game):
    return [a for a in game.aliens if a["alive"]]


def _alien_sprite(row, frame):
    cfg = _ROW_CONFIG[row]
    return cfg[0] if frame == 0 else cfg[1]


def _alien_rect(game, a):
    spr = _alien_sprite(a["row"], 0)
    x = _GRID_ORIGIN_X + game.shift_x + a["col"] * _CELL_W
    y = _GRID_ORIGIN_Y + game.shift_y + a["row"] * _CELL_H
    return x, y, _sprite_w(spr), _sprite_h(spr)


def _march(game, dt_ms):
    alive = _alive(game)
    if not alive:
        return
    remaining = len(alive)
    interval = max(40, int(30 + (remaining / 55.0) * 320))
    game.march_timer += dt_ms
    if game.march_timer < interval:
        return
    game.march_timer = 0
    game.march_frame = 1 - game.march_frame

    step = 2
    min_col = min(a["col"] for a in alive)
    max_col = max(a["col"] for a in alive)
    left  = _GRID_ORIGIN_X + game.shift_x + min_col * _CELL_W
    right = _GRID_ORIGIN_X + game.shift_x + max_col * _CELL_W + 12
    if game.march_dir > 0 and right + step > _CANVAS_W - 6:
        game.shift_y += 6
        game.march_dir = -1
    elif game.march_dir < 0 and left - step < 6:
        game.shift_y += 6
        game.march_dir = 1
    else:
        game.shift_x += game.march_dir * step

    # Check for game over: aliens reached the player line
    bottom = max(_GRID_ORIGIN_Y + game.shift_y + a["row"] * _CELL_H for a in alive) + 8
    if bottom >= _BUNKER_Y + 4:
        game.outcome = "lose"


def _bunker_hit_test(game, x, y):
    """Return (bunker_index, col, row) if (x, y) hits a lit bunker pixel; else None."""
    iy = int(y)
    for i, bx in enumerate(_BUNKER_XS):
        if bx <= x < bx + _BUNKER_W and _BUNKER_Y <= iy < _BUNKER_Y + _BUNKER_H:
            col = int(x - bx)
            row = iy - _BUNKER_Y
            if game.bunkers[i][row][col] == "#":
                return i, col, row
    return None


def _bunker_erode(game, hit, radius=2):
    i, cx, cy = hit
    for ry in range(-radius, radius + 1):
        for rx in range(-radius, radius + 1):
            nx, ny = cx + rx, cy + ry
            if 0 <= nx < _BUNKER_W and 0 <= ny < _BUNKER_H:
                if (rx * rx + ry * ry) <= radius * radius + 1:
                    game.bunkers[i][ny][nx] = "."


def _step(game, dt_ms):
    if game.outcome is not None:
        return
    alive = _alive(game)
    if not alive:
        game.outcome = "win"
        return

    _march(game, dt_ms)

    # Player AI: occasionally retarget to a random alien's column
    game.player_cooldown -= dt_ms
    if game.rng.random() < 0.05:
        tgt = game.rng.choice(alive)
        ax, _, aw, _ = _alien_rect(game, tgt)
        game.target_x = max(10, min(_CANVAS_W - 10, ax + aw / 2))

    # Slide player toward target
    speed = 90.0 * dt_ms / 1000.0
    if game.player_x < game.target_x:
        game.player_x = min(game.target_x, game.player_x + speed)
    elif game.player_x > game.target_x:
        game.player_x = max(game.target_x, game.player_x - speed)

    if game.player_cooldown <= 0:
        game.player_shots.append({
            "x": game.player_x, "y": _CANVAS_H - 26, "vy": -240.0,
        })
        game.player_cooldown = 380 + game.rng.randint(0, 420)

    # Move player shots
    for s in game.player_shots:
        s["y"] += s["vy"] * dt_ms / 1000.0
    for s in list(game.player_shots):
        if s["y"] < -6:
            game.player_shots.remove(s)
            continue
        hit = _bunker_hit_test(game, s["x"], s["y"])
        if hit is not None:
            _bunker_erode(game, hit)
            game.player_shots.remove(s)
            continue
        # Player shot can tag the UFO for bonus
        if game.ufo_x is not None:
            uw = _sprite_w(_UFO)
            if game.ufo_x <= s["x"] <= game.ufo_x + uw and 14 <= s["y"] <= 14 + _sprite_h(_UFO):
                game.score += game.rng.choice((100, 150, 200, 300))
                game.ufo_x = None
                game.ufo_cooldown = 5000 + game.rng.randint(0, 5000)
                game.player_shots.remove(s)
                continue
        # Player shot vs alien
        hit_alien = None
        for a in alive:
            if not a["alive"]:
                continue
            ax, ay, aw, ah = _alien_rect(game, a)
            if ax <= s["x"] <= ax + aw and ay <= s["y"] <= ay + ah:
                hit_alien = a
                break
        if hit_alien is not None:
            hit_alien["alive"] = False
            game.score += _ROW_CONFIG[hit_alien["row"]][3]
            game.player_shots.remove(s)

    # Alien fire from bottom-most alien in a random occupied column
    game.alien_cooldown -= dt_ms
    if game.alien_cooldown <= 0:
        cols = {}
        for a in alive:
            c = a["col"]
            if c not in cols or cols[c]["row"] < a["row"]:
                cols[c] = a
        if cols:
            shooter = game.rng.choice(list(cols.values()))
            ax, ay, aw, ah = _alien_rect(game, shooter)
            game.alien_shots.append({
                "x": ax + aw / 2, "y": ay + ah, "vy": 150.0,
            })
        game.alien_cooldown = 450 + game.rng.randint(0, 1100)

    # Move alien shots + collision (bunkers and player)
    for s in game.alien_shots:
        s["y"] += s["vy"] * dt_ms / 1000.0
    for s in list(game.alien_shots):
        if s["y"] > _CANVAS_H + 4:
            game.alien_shots.remove(s)
            continue
        hit = _bunker_hit_test(game, s["x"], s["y"])
        if hit is not None:
            _bunker_erode(game, hit)
            game.alien_shots.remove(s)
            continue
        # Alien shot vs player
        pw = _sprite_w(_PLAYER)
        ph = _sprite_h(_PLAYER)
        px0 = game.player_x - pw / 2
        py0 = _CANVAS_H - 22
        if px0 <= s["x"] <= px0 + pw and py0 <= s["y"] <= py0 + ph:
            game.alien_shots.remove(s)
            game.outcome = "lose"
            break

    # UFO
    if game.ufo_x is not None:
        game.ufo_x += 55 * dt_ms / 1000.0
        if game.ufo_x > _CANVAS_W + 18:
            game.ufo_x = None
            game.ufo_cooldown = 5000 + game.rng.randint(0, 5000)
    else:
        game.ufo_cooldown -= dt_ms
        if game.ufo_cooldown <= 0:
            game.ufo_x = -float(_sprite_w(_UFO))


def _draw_sprite(painter, sprite, x, y):
    ix = int(x)
    iy = int(y)
    for row, line in enumerate(sprite):
        for col, ch in enumerate(line):
            if ch == "#":
                painter.drawRect(ix + col, iy + row, 1, 1)


def _draw_bunker(painter, grid, x0, y0):
    ix = int(x0)
    iy = int(y0)
    for row, rowdata in enumerate(grid):
        for col, ch in enumerate(rowdata):
            if ch == "#":
                painter.drawRect(ix + col, iy + row, 1, 1)


def _paint(painter, rect, elapsed_ms, overlay):
    if overlay.state is None:
        overlay.state = _Game()
    game = overlay.state

    dt_ms = max(1, elapsed_ms - game.last_tick_ms)
    game.last_tick_ms = elapsed_ms
    _step(game, dt_ms)

    fade = fade_envelope(elapsed_ms, _DURATION_MS)

    painter.setClipRect(rect)
    # Low-alpha arcade backdrop -- widget text underneath stays readable.
    painter.fillRect(rect, QtGui.QColor(4, 4, 10, int(105 * fade)))

    sx = rect.width()  / _CANVAS_W
    sy = rect.height() / _CANVAS_H
    scale = min(sx, sy)
    ox = rect.left() + (rect.width()  - _CANVAS_W * scale) / 2
    oy = rect.top()  + (rect.height() - _CANVAS_H * scale) / 2

    painter.save()
    painter.setRenderHint(ANTIALIASING, False)
    painter.translate(ox, oy)
    painter.scale(scale, scale)
    painter.setPen(QtGui.QPen(NO_PEN))

    # HUD
    font = QtGui.QFont()
    font.setBold(True)
    font.setPointSize(9)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(255, 255, 255, int(255 * fade)))
    painter.drawText(QtCore.QRectF(6, 2, 110, 12), 0, "SCORE {:04d}".format(game.score))
    painter.drawText(QtCore.QRectF(_CANVAS_W - 78, 2, 72, 12), 0, "HI 9999")
    painter.setPen(QtGui.QPen(NO_PEN))

    pal = game.palette

    # Aliens (row-indexed palette color)
    for a in game.aliens:
        if not a["alive"]:
            continue
        cfg = _ROW_CONFIG[a["row"]]
        r, g, b = pal["rows"][a["row"]]
        painter.setBrush(QtGui.QColor(r, g, b, int(255 * fade)))
        ax, ay, _, _ = _alien_rect(game, a)
        spr = cfg[0] if game.march_frame == 0 else cfg[1]
        _draw_sprite(painter, spr, ax, ay)

    # UFO
    if game.ufo_x is not None:
        r, g, b = pal["ufo"]
        painter.setBrush(QtGui.QColor(r, g, b, int(255 * fade)))
        _draw_sprite(painter, _UFO, int(game.ufo_x), 14)

    # Bunkers
    r, g, b = pal["bunker"]
    painter.setBrush(QtGui.QColor(r, g, b, int(255 * fade)))
    for i, bx in enumerate(_BUNKER_XS):
        _draw_bunker(painter, game.bunkers[i], bx, _BUNKER_Y)

    # Player
    pr, pg, pb = pal["player"]
    painter.setBrush(QtGui.QColor(pr, pg, pb, int(255 * fade)))
    pw = _sprite_w(_PLAYER)
    _draw_sprite(painter, _PLAYER, int(game.player_x - pw / 2), _CANVAS_H - 22)

    # Shots
    painter.setBrush(QtGui.QColor(240, 240, 240, int(240 * fade)))
    for s in game.player_shots:
        painter.drawRect(int(s["x"]), int(s["y"]), 1, 4)
    for s in game.alien_shots:
        painter.drawRect(int(s["x"]), int(s["y"]), 1, 4)

    # Ground line (player color, dimmer)
    painter.setBrush(QtGui.QColor(pr, pg, pb, int(200 * fade)))
    painter.drawRect(4, _CANVAS_H - 10, _CANVAS_W - 8, 1)

    # Win / lose overlay
    if game.outcome is not None:
        msg = "YOU WIN" if game.outcome == "win" else "GAME OVER"
        painter.setPen(QtGui.QColor(255, 235, 80, int(255 * fade)))
        big = QtGui.QFont()
        big.setBold(True)
        big.setPointSize(14)
        painter.setFont(big)
        painter.drawText(
            QtCore.QRectF(0, _CANVAS_H / 2 - 10, _CANVAS_W, 20),
            ALIGN_CENTER,
            msg,
        )
        painter.setPen(QtGui.QPen(NO_PEN))

    painter.restore()


register_scene("invaders", _DURATION_MS, _paint)
