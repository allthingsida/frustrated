"""Core runtime for the ida-frustrated plugin.

Exposes a tiny registry (`register_effect`) that drop-in animation modules
under animations/ call at import time, plus `frustrate()` -- the single
entry point wired to the plugin hotkey.
"""

from __future__ import annotations

import importlib
import os
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


@dataclass(frozen=True)
class EffectSpec:
    name: str
    duration_ms: int
    paint: object


EFFECTS = {}


def register_effect(name, duration_ms, paint):
    """Register an effect painter with signature (painter, snapshot, rect, progress, overlay)."""
    EFFECTS[name] = EffectSpec(name, int(duration_ms), paint)
    return EFFECTS[name]


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


_index = 0
_busy = False


def _current_target():
    if ida_kernwin is not None:
        twidget = ida_kernwin.get_current_widget()
        if twidget:
            return ida_kernwin.PluginForm.TWidgetToPyQtWidget(twidget)
    app = QtWidgets.QApplication.instance()
    return app.focusWidget() if app is not None else None


def load_animations():
    """Import every .py file under animations/ once so each registers its effect."""
    if EFFECTS:
        return
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(plugin_dir, "animations")
    if not os.path.isdir(directory):
        return
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(".py") or entry.startswith(("_", ".")):
            continue
        try:
            importlib.import_module(f"animations.{entry[:-3]}")
        except Exception as exc:
            if ida_kernwin is not None:
                ida_kernwin.msg(f"[ida-frustrated] failed to load animation '{entry}': {exc}\n")


def frustrate():
    """Play the next effect on the currently focused widget."""
    global _index, _busy
    if _busy or not EFFECTS:
        return
    target = _current_target()
    if target is None or not target.isVisible():
        return
    specs = list(EFFECTS.values())
    spec = specs[_index % len(specs)]
    _index += 1

    overlay = EffectOverlay(target, spec)
    _busy = True

    def _done(*_):
        global _busy
        _busy = False

    overlay.destroyed.connect(_done)
    overlay.start()
