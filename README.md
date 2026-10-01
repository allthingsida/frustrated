# IDA Frustrated

> *Because everyone deserves a little fun.*

A small dose of joy for IDA Pro. Press `Ctrl+Alt+T` on any focused view
and the plugin picks a random **effect** or **scene** to surprise you with
-- a quick shake, a cartoon rage burst, a 30-second weather front rolling
across your disassembly, or a flock of IDA icons swooping over your
pseudocode. Something fun to lift the mood while you reverse engineer.

The pool is a fair shuffled deck: every registered animation plays once
per round before any repeats, and the same one never fires twice in a row.

> The idea -- and the name -- come from Ghidra, whose docking framework
> triggers "frustrated" emphasis animations when a user keeps hammering the
> same provider shortcut. This plugin started as a port of that
> snapshot/overlay model to IDA, and grew a second trick: long-running
> scenes you can keep working under. Manual invocation only, for giggles.

## Two flavors

| Kind | Lives in | Lifetime | Interacts with widget? | Concurrency |
|------|----------|----------|------------------------|-------------|
| **Effect** | `effects/*.py` | one-shot (~400 ms - 1.5 s) | takes a snapshot; widget is briefly frozen under the overlay | one at a time (rapid presses are coalesced) |
| **Scene**  | `scenes/*.py`     | long-running (~18-30 s)   | non-blocking, low-alpha overlay; the widget stays fully interactive underneath | **one active per widget** -- triggering another scene on the same widget cancels it; scenes on other widgets keep running independently |

Shipped out of the box:

- **Effects** -- `rage`, `rotate`, `shake`, `zoom`.
- **Scenes (enabled by default):**
  - `weather` -- a 30 s sunny -> stormy -> clearing story with drifting
    clouds, a sun, rain streaks, and lightning bolts.
  - `invasion` -- 20 s flock of the host application's icon swooping
    across the widget in varied trajectories (a nod to Ghidra's
    `showTheDragonOverComponent`).
  - `invaders` -- 30 s self-playing Space Invaders simulation: 5 x 11
    alien grid, auto-firing player, bunkers, UFO flyovers, score HUD,
    rendered on a virtual 224 x 256 arcade canvas scaled to fit.
  - `lava_lamp` -- 30 s of warm metaball-ish blobs rising and sinking
    in one of three palettes (warm orange, acid green, electric pink).
    Pure ambient mood.
  - `matrix_rain` -- 25 s pure Matrix-style digital rain: dense
    katakana-flavoured glyph columns at varied speeds with a bright
    white leading glyph and a green fading tail. No watermark, no
    chrome -- just the rain.
- **Scenes (shipped *disabled* -- rename off the `.disabled` suffix to enable):**
  - `police` -- 18 s red/blue siren bar with wig-wag / sync / chase
    flash patterns. The canonical example of the `.disabled` convention
    below.
  - `fbi` -- 18 s yellow/black caution-tape bars top & bottom, a
    wandering flashlight cone, and a sliding "FBI -- OPEN UP!" banner.
  - `nsa` -- 25 s green glyph rain, rotating
    "CLASSIFIED / TOP SECRET / GHIDRA" watermark, and a pulsing REC
    indicator. Tribute to the NSA-birthed roots of Ghidra.
    (Superseded by `matrix_rain` for pure-rain vibe.)
  - `disco` -- 22 s of swaying magenta/cyan/lime/gold spotlight cones
    pulsing to a beat, with a rotating disco ball and sparkles.
  - `terminal` -- 25 s green-phosphor hacker console: fake
    nmap/ssh/root lines type out in monospace over a CRT scanline
    overlay, with occasional red `[!!]` alarm lines.
  - `aurora` -- 28 s of slow cyan/green/magenta aurora ribbons
    undulating above a faint twinkling star field.

## Demo

See it in action on [X / @allthingsida](https://x.com/allthingsida/status/2046514898180657517).

## Install

The Hex-Rays plugin CLI can install directly from this folder (or a zip of
it). From inside the repo:

```sh
hcli plugin install .
```

Or point it at a specific location / archive:

```sh
hcli plugin install path/to/ida-frustrated
hcli plugin install ida-frustrated.zip
```

Start IDA; the plugin shows up as **IDA Frustrated** under Edit > Plugins.

## Usage

- Focus the view you want to decorate (Disassembly, Pseudocode, Graph, etc.).
- Press `Ctrl+Alt+T`. You'll get a random effect or scene.
- Press again for the next. Effects are one-shots; scenes run in the
  background for many seconds and can be cancelled by triggering another
  scene.

## Adding effects (drop-in)

Effects live as individual Python files under `effects/`. On plugin load
every `.py` file in that folder is imported in alphabetical order and is
expected to register one or more effects at import time.

Paint callback signature:

```python
paint(painter, snapshot, rect, progress, overlay)
```

- `painter`  - `QPainter` already configured with antialiasing enabled.
- `snapshot` - `QPixmap` grabbed from the target widget at animation start.
- `rect`     - `QRect` where the snapshot belongs, in overlay coordinates.
- `progress` - `float` in `[0, 1]`, pre-eased with `InOutCubic`.
- `overlay`  - the `EffectOverlay`; call `overlay.erase_original(painter, rect)`
  first if you want to clear the real widget before drawing.

Minimal example -- drop this as `effects/flash.py`:

```python
from core import QtGui, register_effect

def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)
    painter.drawPixmap(rect, snapshot)
    alpha = int(180 * (1.0 - abs(progress - 0.5) * 2.0))
    painter.fillRect(rect, QtGui.QColor(255, 255, 255, alpha))

register_effect("flash", 500, _paint)
```

Restart IDA and `flash` joins the shuffle pool alongside the other
animations. Filename order only controls registration; play order is a
fair random shuffle.

## Adding scenes (drop-in)

Scenes live under `scenes/`. Same drop-in discovery, different registration
call and a different paint signature:

```python
paint(painter, rect, elapsed_ms, overlay)
```

- `painter`    - `QPainter` with antialiasing; no snapshot is captured.
- `rect`       - current target widget `QRect` (re-read every frame, so it
  follows docking / resizing automatically).
- `elapsed_ms` - milliseconds since the scene started.
- `overlay`    - the `SceneOverlay`. Stash per-run state on `overlay.state`
  (initialized to `None`); it's rebuilt on every fresh invocation.

Minimal example -- drop this as `scenes/tint.py`:

```python
from core import QtGui, register_scene

_DURATION_MS = 10000  # 10 seconds

def _paint(painter, rect, elapsed_ms, overlay):
    t = elapsed_ms / _DURATION_MS
    painter.fillRect(rect, QtGui.QColor(120, 180, 255, int(90 * (1 - abs(t - 0.5) * 2))))

register_scene("tint", _DURATION_MS, _paint)
```

Scenes are driven by a ~30 fps `QTimer`, follow the target widget's
geometry every tick, and self-destruct when their duration elapses or
the target widget disappears. Scenes are keyed per widget: triggering a
new scene on the same widget cancels that widget's current scene, but
scenes running on *other* widgets keep going independently.

## How effects and scenes are discovered

At plugin load, `core.load_animations()` walks `effects/` and `scenes/`
alphabetically and imports every `.py` file in each. Each imported
module registers itself with `register_effect(...)` or
`register_scene(...)` at import time — that's the only thing that puts
it into the rotation. Files whose names start with `_` or `.` are
skipped (that's how `scenes/_common.py` stays out of the pool).

## Disabling an effect or scene

To take an animation out of the rotation without deleting it, rename
the file to add a `.disabled` suffix:

```sh
git mv scenes/police.py scenes/police.py.disabled
```

The loader only imports files that end in `.py`, so the renamed file
is skipped entirely — the module is never imported, it never calls
`register_*`, and it never enters the shuffled deck. Re-enable by
stripping the suffix (`git mv scenes/police.py.disabled scenes/police.py`).

## Manual trigger

From the IDA Python console:

```python
import core
core.EFFECTS         # registered effects
core.SCENES          # registered scenes
core.frustrate()     # play a random effect or scene on the focused widget
```

## License

Human-Origin Source License v1.0 (source-available) -- see [LICENSE](LICENSE) and the per-file
`SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0` headers. Copyright (c) 2026 Elias Bachaalany.
Written by Elias Bachaalany.
