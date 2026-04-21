"""Core runtime for the ida-frustrated plugin.

Two registries feed a single fair shuffle:

- **Effects** (`animations/*.py`) -- short one-shot painters that grab a widget
  snapshot and animate it. Registered via `register_effect`. Gated by `_busy`
  so effects never overlap.
- **Scenes**  (`scenes/*.py`)     -- long-running, timer-driven overlays that
  leave the widget interactive. Registered via `register_scene`. Singleton:
  triggering a new scene cancels any active one.

`frustrate()` is the single entry point wired to the plugin hotkey. It pops
from a shuffled deck that mixes effects and scenes, and dispatches to the
right overlay class.
"""

from __future__ import annotations

import importlib
import os
import random
import sys
from dataclasses import dataclass


try:
    import ida_kernwin
except ImportError:
    ida_kernwin = None


try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
    except ImportError:
        try:
            from PySide2 import QtCore, QtGui, QtWidgets
        except ImportError:
            from PyQt5 import QtCore, QtGui, QtWidgets


def _qt_value(owner, scoped_name, legacy_name):
    current = owner
    for part in scoped_name.split("."):
        current = getattr(current, part, None)
        if current is None:
            return getattr(owner, legacy_name)
    return current


WA_TRANSPARENT_FOR_MOUSE = _qt_value(QtCore.Qt, "WidgetAttribute.WA_TransparentForMouseEvents", "WA_TransparentForMouseEvents")
WA_NO_SYSTEM_BACKGROUND  = _qt_value(QtCore.Qt, "WidgetAttribute.WA_NoSystemBackground",        "WA_NoSystemBackground")
WA_TRANSLUCENT_BACKGROUND = _qt_value(QtCore.Qt, "WidgetAttribute.WA_TranslucentBackground",    "WA_TranslucentBackground")
NO_FOCUS                 = _qt_value(QtCore.Qt, "FocusPolicy.NoFocus",                          "NoFocus")
EASE_IN_OUT_CUBIC        = _qt_value(QtCore.QEasingCurve, "Type.InOutCubic",                    "InOutCubic")
KEEP_WHEN_STOPPED        = _qt_value(QtCore.QAbstractAnimation, "DeletionPolicy.KeepWhenStopped", "KeepWhenStopped")
ANTIALIASING             = _qt_value(QtGui.QPainter, "RenderHint.Antialiasing",                 "Antialiasing")
SMOOTH_PIXMAP_TRANSFORM  = _qt_value(QtGui.QPainter, "RenderHint.SmoothPixmapTransform",        "SmoothPixmapTransform")
PALETTE_WINDOW           = _qt_value(QtGui.QPalette, "ColorRole.Window",                        "Window")
NO_PEN                   = _qt_value(QtCore.Qt, "PenStyle.NoPen",                               "NoPen")
NO_BRUSH                 = _qt_value(QtCore.Qt, "BrushStyle.NoBrush",                           "NoBrush")
ALIGN_CENTER             = _qt_value(QtCore.Qt, "AlignmentFlag.AlignCenter",                    "AlignCenter")
FONT_TYPEWRITER          = _qt_value(QtGui.QFont, "StyleHint.TypeWriter",                       "TypeWriter")


@dataclass(frozen=True)
class EffectSpec:
    name: str
    duration_ms: int
    paint: object


@dataclass(frozen=True)
class SceneSpec:
    name: str
    duration_ms: int
    paint: object


EFFECTS = {}
SCENES = {}


def register_effect(name, duration_ms, paint):
    """Register a one-shot effect painter.

    Signature: paint(painter, snapshot, rect, progress, overlay).
    """
    EFFECTS[name] = EffectSpec(name, int(duration_ms), paint)
    return EFFECTS[name]


def register_scene(name, duration_ms, paint):
    """Register a long-running scene painter.

    Signature: paint(painter, rect, elapsed_ms, overlay).

    Scenes do not capture a snapshot and do not block the widget underneath.
    Stash per-run state on `overlay.state` (initialized to None).
    Only one scene plays at a time -- a new one cancels the active scene.
    """
    SCENES[name] = SceneSpec(name, int(duration_ms), paint)
    return SCENES[name]


class EffectOverlay(QtWidgets.QWidget):
    """Transparent overlay that paints a transformed snapshot of a target widget."""

    def __init__(self, target, spec):
        window = target.window()
        super().__init__(window)
        self.spec = spec
        self.progress = 0.0
        self.snapshot = target.grab()

        top_left = target.mapTo(window, QtCore.QPoint(0, 0))
        self.base_rect = QtCore.QRect(top_left, target.size())

        self.setAttribute(WA_TRANSPARENT_FOR_MOUSE, True)
        self.setAttribute(WA_NO_SYSTEM_BACKGROUND, True)
        self.setAttribute(WA_TRANSLUCENT_BACKGROUND, True)
        self.setFocusPolicy(NO_FOCUS)
        self.setGeometry(window.rect())

        self.animation = QtCore.QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(spec.duration_ms)
        self.animation.setEasingCurve(EASE_IN_OUT_CUBIC)
        self.animation.valueChanged.connect(self._set_progress)
        self.animation.finished.connect(self.deleteLater)

    def start(self):
        self.show()
        self.raise_()
        self.animation.start(KEEP_WHEN_STOPPED)

    def erase_original(self, painter, rect):
        window = self.parentWidget()
        color = window.palette().color(PALETTE_WINDOW) if window else QtGui.QColor()
        painter.fillRect(rect, color)

    def _set_progress(self, value):
        self.progress = float(value)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        if self.base_rect.isNull():
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(ANTIALIASING, True)
        painter.setRenderHint(SMOOTH_PIXMAP_TRANSFORM, True)
        try:
            self.spec.paint(painter, self.snapshot, self.base_rect, self.progress, self)
        finally:
            painter.end()


class SceneOverlay(QtWidgets.QWidget):
    """Long-running transparent overlay. Timer-driven, follows the target geometry.

    Unlike `EffectOverlay`, this does not capture a snapshot and does not fill
    the widget area -- the target widget stays fully interactive underneath.
    Self-destructs on duration expiry or when the target becomes invisible /
    destroyed.
    """

    FRAME_INTERVAL_MS = 33  # ~30 fps

    def __init__(self, target, spec):
        window = target.window()
        super().__init__(window)
        self.target = target
        self.spec = spec
        self.elapsed_ms = 0
        self.state = None  # scenes stash per-run state here
        self.base_rect = QtCore.QRect()

        self.setAttribute(WA_TRANSPARENT_FOR_MOUSE, True)
        self.setAttribute(WA_NO_SYSTEM_BACKGROUND, True)
        self.setAttribute(WA_TRANSLUCENT_BACKGROUND, True)
        self.setFocusPolicy(NO_FOCUS)
        self._refresh_geometry()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.FRAME_INTERVAL_MS)
        self.timer.timeout.connect(self._tick)

    def _refresh_geometry(self):
        """Re-read the target's current position/size; cover the whole window.

        Returns False if the target is gone or invisible -- caller should stop.
        """
        try:
            if not self.target.isVisible():
                return False
            window = self.target.window()
            if window is None:
                return False
            top_left = self.target.mapTo(window, QtCore.QPoint(0, 0))
            self.base_rect = QtCore.QRect(top_left, self.target.size())
            if self.geometry() != window.rect():
                self.setGeometry(window.rect())
            return True
        except RuntimeError:
            # Qt-wrapped object was deleted under us.
            return False

    def start(self):
        self.show()
        self.raise_()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.hide()
        self.deleteLater()

    def _tick(self):
        self.elapsed_ms += self.FRAME_INTERVAL_MS
        if self.elapsed_ms >= self.spec.duration_ms:
            self.stop()
            return
        if not self._refresh_geometry():
            self.stop()
            return
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        if self.base_rect.isNull():
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(ANTIALIASING, True)
        painter.setRenderHint(SMOOTH_PIXMAP_TRANSFORM, True)
        try:
            self.spec.paint(painter, self.base_rect, self.elapsed_ms, self)
        finally:
            painter.end()


_deck = []
_last = None
_busy = False
_active_scenes = {}  # per-widget scene registry: widget_key -> SceneOverlay


def deck_peek():
    """Debug helper: show what's queued in the shuffled deck right now.

    Returns a list of ``(kind, name)`` tuples in play order. ``kind`` is
    ``"Effect"`` or ``"Scene"``. Useful for confirming that one-shot
    effects really are mixed with scenes -- scenes run 18-30 s and can
    feel dominant even though effects make up ~40% of the pool.

    Example from the IDA Python console:

        import core
        core.deck_peek()
        # [('Scene', 'weather'), ('Effect', 'rage'), ...]
    """
    kinds = {EffectSpec: "Effect", SceneSpec: "Scene"}
    return [(kinds.get(type(s), "?"), s.name) for s in _deck]


def _refill_deck():
    """Return a fresh shuffled deck of every registered effect AND scene.

    If the previous round's last item would land at the head of the new
    deck, swap it with a random deeper slot so the same animation never
    plays twice in a row across refills (globally -- anti-repeat ignores
    which widget an animation played on).
    """
    specs = list(EFFECTS.values()) + list(SCENES.values())
    random.shuffle(specs)
    if _last is not None and len(specs) > 1 and specs[0].name == _last:
        j = random.randrange(1, len(specs))
        specs[0], specs[j] = specs[j], specs[0]
    return specs


def _current_target():
    """Return (widget, key) identifying the focused target, or (None, None).

    The key is stable per underlying IDA view so scenes can be tracked
    per-widget. Prefers IDA's TWidget pointer when available; falls back
    to the Python id() of the PyQt wrapper.
    """
    if ida_kernwin is not None:
        twidget = ida_kernwin.get_current_widget()
        if twidget:
            try:
                widget = ida_kernwin.PluginForm.TWidgetToPyQtWidget(twidget)
            except Exception:
                widget = None
            if widget is not None:
                try:
                    return widget, ("twidget", int(twidget))
                except (TypeError, ValueError):
                    return widget, ("id", id(widget))
    app = QtWidgets.QApplication.instance()
    widget = app.focusWidget() if app is not None else None
    if widget is None:
        return None, None
    return widget, ("id", id(widget))


def _spawn_scene(target, key, spec):
    """Start a scene on `target`; cancel any scene already active on the same widget.

    Each widget has its own slot in `_active_scenes`, so triggering a
    scene on a different widget does NOT cancel scenes running on other
    widgets. Within one widget, newest wins: the previous scene is
    disconnected (so its deferred `destroyed` handler can't clobber the
    new slot) and stopped.
    """
    global _active_scenes
    existing = _active_scenes.pop(key, None)
    if existing is not None:
        try:
            existing.destroyed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            existing.stop()
        except Exception:
            pass

    overlay = SceneOverlay(target, spec)
    _active_scenes[key] = overlay
    overlay.destroyed.connect(lambda *_, k=key: _active_scenes.pop(k, None))
    overlay.start()


def load_animations():
    """Import every .py file under animations/ and scenes/ once so each registers."""
    if EFFECTS or SCENES:
        return
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    for pkg in ("animations", "scenes"):
        directory = os.path.join(plugin_dir, pkg)
        if not os.path.isdir(directory):
            continue
        for entry in sorted(os.listdir(directory)):
            if not entry.endswith(".py") or entry.startswith(("_", ".")):
                continue
            try:
                importlib.import_module(f"{pkg}.{entry[:-3]}")
            except Exception as exc:
                if ida_kernwin is not None:
                    ida_kernwin.msg(f"[ida-frustrated] failed to load '{pkg}/{entry}': {exc}\n")


def frustrate():
    """Play a random effect or scene on the focused widget.

    Fair shuffle: every registered effect/scene plays once per round before
    any repeats, and the same item never plays twice in a row across rounds.
    Effects are one-shot and gated by `_busy` (rapid presses can't overlap).
    Scenes are long-running and **one-active-per-widget** -- triggering a
    new scene on the same widget cancels that widget's scene; triggering
    on a different widget spawns a fresh scene without disturbing the
    other widget's scene.
    """
    global _deck, _last, _busy
    if not EFFECTS and not SCENES:
        return
    target, key = _current_target()
    if target is None or key is None or not target.isVisible():
        return
    if not _deck:
        _deck = _refill_deck()
    spec = _deck[0]

    if isinstance(spec, EffectSpec) and _busy:
        # Another effect is still playing; skip without consuming the slot
        # so the next press still gets this one.
        return

    _deck.pop(0)
    _last = spec.name

    if isinstance(spec, SceneSpec):
        _spawn_scene(target, key, spec)
        return

    overlay = EffectOverlay(target, spec)
    _busy = True

    def _done(*_):
        global _busy
        _busy = False

    overlay.destroyed.connect(_done)
    overlay.start()
