# -*- coding: utf-8 -*-
"""Reusable widgets: responsive flow layout, cards, badges, segmented buttons."""
from __future__ import annotations

from typing import List, Optional

from .qt import Qt, QtCore, QtGui, QtWidgets, Signal


class FlowLayout(QtWidgets.QLayout):
    """Layout that wraps its items like text - the tile grid reflows on resize."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 10, v_spacing: int = 10) -> None:
        super().__init__(parent)
        self._items: List[QtWidgets.QLayoutItem] = []
        self._h = h_spacing
        self._v = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        try:
            return Qt.Orientations(0)          # PySide2 / PyQt5
        except TypeError:
            return Qt.Orientation(0)           # PySide6 / PyQt6

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only: bool) -> int:
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_h = 0
        right = rect.right() - m.right()
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > right and line_h > 0:
                x = rect.x() + m.left()
                y += line_h + self._v
                line_h = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x += w + self._h
            line_h = max(line_h, h)
        return y + line_h + m.bottom() - rect.y()

    def clear(self) -> None:
        while self._items:
            item = self._items.pop()
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()


class Card(QtWidgets.QFrame):
    def __init__(self, parent=None, title: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setProperty("selected", False)
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(14, 12, 14, 12)
        self.body.setSpacing(8)
        if title:
            lab = QtWidgets.QLabel(title)
            lab.setObjectName("Section")
            self.body.addWidget(lab)


def section_label(text: str) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    lab.setObjectName("Section")
    return lab


def hint_label(text: str) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    lab.setObjectName("Hint")
    lab.setWordWrap(True)
    return lab


def badge(text: str, kind: str = "") -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    lab.setObjectName({"ref": "BadgeRef", "inf": "BadgeInf", "ok": "BadgeOk", "warn": "BadgeWarn", "muted": "BadgeMuted"}.get(kind, "Badge"))
    lab.setAlignment(Qt.AlignCenter)
    return lab


def button(text: str, kind: str = "", tooltip: str = "", slot=None) -> QtWidgets.QPushButton:
    b = QtWidgets.QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    if tooltip:
        b.setToolTip(tooltip)
    if slot is not None:
        b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b


def hline() -> QtWidgets.QFrame:
    f = QtWidgets.QFrame()
    f.setObjectName("HLine")
    f.setFrameShape(QtWidgets.QFrame.NoFrame)
    return f


class Segmented(QtWidgets.QWidget):
    """Row of mutually exclusive buttons (e.g. REF | INF)."""
    changed = Signal(str)

    def __init__(self, options: List[tuple], parent=None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for value, label in options:
            b = QtWidgets.QPushButton(label)
            b.setCheckable(True)
            b.setProperty("kind", "seg")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self._group.addButton(b)
            lay.addWidget(b)
            self._buttons[value] = b

    def set_value(self, value: str) -> None:
        b = self._buttons.get(value)
        if b is not None:
            b.setChecked(True)

    def value(self) -> Optional[str]:
        for v, b in self._buttons.items():
            if b.isChecked():
                return v
        return None

    def set_labels(self, labels: dict) -> None:
        for v, t in labels.items():
            if v in self._buttons:
                self._buttons[v].setText(t)


def repolish(w: QtWidgets.QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def pixmap_from_b64(b64: str) -> Optional[QtGui.QPixmap]:
    if not b64:
        return None
    data = QtCore.QByteArray.fromBase64(b64.encode("ascii"))
    pm = QtGui.QPixmap()
    return pm if pm.loadFromData(data) else None


def placeholder_pixmap(w: int, h: int, text: str, dark: bool = True) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(w, h)
    pm.fill(QtGui.QColor("#0B1220" if dark else "#E5E7EB"))
    p = QtGui.QPainter(pm)
    p.setPen(QtGui.QColor("#64748B"))
    p.drawText(pm.rect(), Qt.AlignCenter | Qt.TextWordWrap, text)
    p.end()
    return pm


def confirm(parent, title: str, text: str) -> bool:
    res = QtWidgets.QMessageBox.question(parent, title, text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No)
    return res == QtWidgets.QMessageBox.Yes


def info(parent, title: str, text: str) -> None:
    QtWidgets.QMessageBox.information(parent, title, text)


def warn(parent, title: str, text: str) -> None:
    QtWidgets.QMessageBox.warning(parent, title, text)
