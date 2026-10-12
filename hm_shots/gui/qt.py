# -*- coding: utf-8 -*-
"""Qt binding compatibility layer: PySide6 > PySide2 > PyQt6 > PyQt5.

HyperWorks ships PySide (2 or 6 depending on the release); the tool only uses
the subset that behaves the same across bindings and smooths over the few
differences here (Signal name, QAction module, exec vs exec_).
"""
from __future__ import annotations

QT_LIB = ""
_err = []
for _name in ("PySide6", "PySide2", "PyQt6", "PyQt5"):
    try:
        _mod = __import__(_name, fromlist=["QtCore", "QtGui", "QtWidgets"])
        QtCore = _mod.QtCore
        QtGui = _mod.QtGui
        QtWidgets = _mod.QtWidgets
        QT_LIB = _name
        break
    except Exception as exc:  # noqa: BLE001
        _err.append("%s: %s" % (_name, exc))
if not QT_LIB:
    raise ImportError(
        "No Qt binding found (PySide6 / PySide2 / PyQt6 / PyQt5).\n"
        "Install one into the Python used by HyperMesh, e.g.:\n"
        "    <hw_install>/python/python.exe -m pip install PySide6\n" + "\n".join(_err))

Qt = QtCore.Qt
Signal = getattr(QtCore, "Signal", None) or getattr(QtCore, "pyqtSignal")
Slot = getattr(QtCore, "Slot", None) or getattr(QtCore, "pyqtSlot")
QAction = getattr(QtGui, "QAction", None) or getattr(QtWidgets, "QAction")
QShortcut = getattr(QtGui, "QShortcut", None) or getattr(QtWidgets, "QShortcut")
IS_QT6 = QT_LIB in ("PySide6", "PyQt6")


def exec_(obj):
    """Run a dialog / menu / app event loop regardless of binding."""
    fn = getattr(obj, "exec", None)
    if fn is None or (QT_LIB in ("PySide2", "PyQt5") and hasattr(obj, "exec_")):
        fn = getattr(obj, "exec_", fn)
    return fn()


def enum_value(e):
    """Integer value of a Qt enum member (Qt6 scoped enums vs Qt5 ints)."""
    return getattr(e, "value", e)


def app_instance():
    return QtWidgets.QApplication.instance()


def ensure_app(argv=None):
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(list(argv or ["hm_shots"]))
        created = True
    return app, created


def process_events() -> None:
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def screen_size():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return 1600, 900
    scr = app.primaryScreen()
    if scr is None:
        return 1600, 900
    g = scr.availableGeometry()
    return g.width(), g.height()
