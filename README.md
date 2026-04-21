# IDA Frustrated

An IDA Pro plugin that animates the currently focused widget when you press
`Ctrl+Alt+T`. Each press advances to the next animation in the registered
rotation (rotate -> shake -> zoom -> wrap).

> The idea -- and the name -- come from Ghidra, whose docking framework
> triggers "frustrated" emphasis animations when a user keeps hammering the
> same provider shortcut. This plugin ports the snapshot/overlay model to IDA
> and exposes it as a single deliberate hotkey instead of a rapid-click trap.
>
> It's a work in progress and not a 1:1 port of Ghidra's frustrated mode --
> for now it's manual invocation only, just for giggles.

## Demo

See it in action on [X / @allthingsida](https://x.com/allthingsida/status/2046476512719958414?s=20).

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

- Focus the view you want to frustrate (Disassembly, Pseudocode, Graph, etc.).
- Press `Ctrl+Alt+T`.
- Press it again for the next animation. The plugin cycles deterministically
  through every registered effect.

## Adding animations (drop-in)

Animations live as individual Python files under `animations/`. On plugin load
every `.py` file in that folder is imported in alphabetical order, and each one
is expected to register one or more effects at import time.

Each paint callback has this signature:

```python
paint(painter, snapshot, rect, progress, overlay)
```

- `painter`  - `QPainter` already configured with antialiasing enabled.
- `snapshot` - `QPixmap` grabbed from the target widget at animation start.
- `rect`     - `QRect` in the overlay's coordinate space where `snapshot` lives.
- `progress` - `float` in `[0, 1]`, eased with `InOutCubic`.
- `overlay`  - the `EffectOverlay` itself; call `overlay.erase_original(painter, rect)`
  first if you want to clear the real widget before drawing.

Minimal example -- drop this as `animations/flash.py`:

```python
from ida_frustrated_core import QtGui, register_effect

def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)
    painter.drawPixmap(rect, snapshot)
    alpha = int(180 * (1.0 - abs(progress - 0.5) * 2.0))
    painter.fillRect(rect, QtGui.QColor(255, 255, 255, alpha))

register_effect("flash", 500, _paint)
```

Restart IDA and `flash` joins the cycle at its alphabetical slot (between
`%` and `r`, so: `flash` -> `rotate` -> `shake` -> `zoom`).

## Manual trigger

From the IDA Python console:

```python
import ida_frustrated_core as core
core.EFFECTS      # registered effects, in cycle order
core.frustrate()  # play the next effect on the focused widget
```

## License

MIT -- see [LICENSE](LICENSE). Written by Elias Bachaalany.
