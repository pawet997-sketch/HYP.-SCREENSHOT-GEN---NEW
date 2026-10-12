# -*- coding: utf-8 -*-
"""Tile card for one remembered view: thumbnail + name + quality checks."""
from __future__ import annotations

import os
from typing import Dict

from ..i18n import tr
from ..quality import MetricRegistry
from ..views import ViewRecord
from .qt import Qt, QtWidgets, Signal
from .widgets import badge, pixmap_from_b64, placeholder_pixmap, repolish

TILE_W = 330
THUMB_W = TILE_W - 28
THUMB_H = int(THUMB_W * 0.6)


class MetricRow(QtWidgets.QWidget):
    changed = Signal()

    def __init__(self, metric, setting, parent=None) -> None:
        super().__init__(parent)
        self.metric_def = metric
        self.setting = setting
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.check = QtWidgets.QCheckBox(metric.name)
        self.check.setObjectName("MetricCheck")
        self.check.setChecked(bool(setting.enabled))
        self.check.setToolTip(tr("Zrób zrzut z tą kontrolą jakości (natywna legenda HyperMesh)",
                                 "Take a screenshot with this quality check (native HyperMesh legend)"))
        self.check.toggled.connect(self._on_toggle)
        lay.addWidget(self.check, 1)
        self.sym = QtWidgets.QLabel(metric.symbol)
        self.sym.setObjectName("Muted")
        self.sym.setToolTip(tr("Elementy poza limitem: wartość %s próg", "Elements outside the limit: value %s limit") % metric.symbol)
        lay.addWidget(self.sym)
        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setDecimals(metric.decimals)
        self.spin.setSingleStep(metric.step)
        self.spin.setRange(-1e6, 1e6)
        self.spin.setValue(metric.default_threshold if setting.threshold is None else float(setting.threshold))
        self.spin.setFixedWidth(78)
        self.spin.setToolTip(tr("Wartość graniczna dla tego widoku", "Limit value for this view"))
        self.spin.valueChanged.connect(self._on_thr)
        lay.addWidget(self.spin)
        self.only = QtWidgets.QToolButton()
        self.only.setText("⊘")
        self.only.setCheckable(True)
        self.only.setChecked(bool(setting.hide_passed))
        self.only.setToolTip(tr("Pokaż tylko elementy poza limitem (ukryj resztę siatki)",
                                "Show only the elements outside the limit (hide the rest of the mesh)"))
        self.only.toggled.connect(self._on_only)
        lay.addWidget(self.only)
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        on = self.check.isChecked()
        self.spin.setEnabled(on)
        self.only.setEnabled(on)
        self.sym.setEnabled(on)

    def _on_toggle(self, on: bool) -> None:
        self.setting.enabled = bool(on)
        self._sync_enabled()
        self.changed.emit()

    def _on_thr(self, v: float) -> None:
        self.setting.threshold = float(v)
        self.changed.emit()

    def _on_only(self, on: bool) -> None:
        self.setting.hide_passed = bool(on)
        self.changed.emit()


class ViewTile(QtWidgets.QFrame):
    changed = Signal()
    test_requested = Signal(int)
    refresh_requested = Signal(int)
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    edit_requested = Signal(int)
    move_requested = Signal(int, int)
    copy_requested = Signal(int)

    def __init__(self, rec: ViewRecord, registry: MetricRegistry, parent=None) -> None:
        super().__init__(parent)
        self.rec = rec
        self.registry = registry
        self.setObjectName("Tile")
        self.setProperty("selected", bool(rec.selected))
        self.setFixedWidth(TILE_W)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self._rows: Dict[str, MetricRow] = {}
        self._build()

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(6)
        self.sel = QtWidgets.QCheckBox()
        self.sel.setChecked(bool(self.rec.selected))
        self.sel.setToolTip(tr("Uwzględnij ten widok przy generowaniu", "Include this view when generating"))
        self.sel.toggled.connect(self._on_select)
        head.addWidget(self.sel)
        self.name = QtWidgets.QLineEdit(self.rec.name)
        self.name.setObjectName("NameEdit")
        self.name.setToolTip(tr("Nazwa widoku (użyta w nazwach plików i folderów)", "View name (used in file and folder names)"))
        self.name.editingFinished.connect(self._on_name)
        head.addWidget(self.name, 1)
        self.idlab = badge("#%d" % self.rec.id, "muted")
        head.addWidget(self.idlab)
        menu_btn = QtWidgets.QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setToolTip(tr("Więcej akcji", "More actions"))
        menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(menu_btn)
        menu.addAction(tr("Edytuj widok…", "Edit view…"), lambda: self.edit_requested.emit(self.rec.id))
        menu.addAction(tr("Duplikuj", "Duplicate"), lambda: self.duplicate_requested.emit(self.rec.id))
        menu.addAction(tr("Kopiuj dane widoku (VS)", "Copy view data (VS)"), lambda: self.copy_requested.emit(self.rec.id))
        menu.addSeparator()
        menu.addAction(tr("Przesuń w górę", "Move up"), lambda: self.move_requested.emit(self.rec.id, -1))
        menu.addAction(tr("Przesuń w dół", "Move down"), lambda: self.move_requested.emit(self.rec.id, 1))
        menu.addSeparator()
        menu.addAction(tr("Usuń", "Delete"), lambda: self.delete_requested.emit(self.rec.id))
        menu_btn.setMenu(menu)
        head.addWidget(menu_btn)
        root.addLayout(head)

        self.thumb_frame = QtWidgets.QFrame()
        self.thumb_frame.setObjectName("Thumb")
        self.thumb_frame.setFixedSize(THUMB_W, THUMB_H)
        tl = QtWidgets.QVBoxLayout(self.thumb_frame)
        tl.setContentsMargins(2, 2, 2, 2)
        self.thumb = QtWidgets.QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setCursor(Qt.PointingHandCursor)
        self.thumb.setToolTip(tr("Kliknij: ustaw ten widok w HyperMesh", "Click: apply this view in HyperMesh"))
        self.thumb.mousePressEvent = lambda e: self.test_requested.emit(self.rec.id)  # type: ignore[assignment]
        tl.addWidget(self.thumb)
        root.addWidget(self.thumb_frame, 0, Qt.AlignHCenter)
        self.update_thumbnail()

        badges = QtWidgets.QHBoxLayout()
        badges.setSpacing(4)
        self.b_layout = badge("⚙ " + tr("układ", "layout"), "")
        self.b_layout.setToolTip(tr("Widok ma nagrane komendy układu wyświetlania (odtwarzane przed zrzutem)",
                                    "This view has recorded display-layout commands (replayed before the shot)"))
        self.b_frame = badge("◉ " + tr("klatka", "frame"), "ok")
        self.b_frame.setToolTip(tr("Zapisana pełna klatka z chwili zapamiętania (WYSIWYG)", "Full frame stored at remember time (WYSIWYG)"))
        self.b_cam = QtWidgets.QLabel()
        self.b_cam.setObjectName("Hint")
        badges.addWidget(self.b_layout)
        badges.addWidget(self.b_frame)
        badges.addStretch(1)
        badges.addWidget(self.b_cam)
        root.addLayout(badges)

        self.plain = QtWidgets.QCheckBox(tr("Zwykły zrzut (bez metryki)", "Plain screenshot (no metric)"))
        self.plain.setChecked(bool(self.rec.plain))
        self.plain.toggled.connect(self._on_plain)
        root.addWidget(self.plain)

        self.metrics_box = QtWidgets.QVBoxLayout()
        self.metrics_box.setSpacing(4)
        root.addLayout(self.metrics_box)
        self.rebuild_metrics()

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(4)
        for text, tip, sig in (
            (tr("Testuj", "Test"), tr("Ustaw ten widok w oknie HyperMesh", "Apply this view in the HyperMesh window"), self.test_requested),
            (tr("Miniatura", "Thumbnail"), tr("Odśwież miniaturę (ustawia widok i robi zrzut)", "Refresh the thumbnail (applies the view, captures)"), self.refresh_requested),
        ):
            b = QtWidgets.QPushButton(text)
            b.setProperty("kind", "small")
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, s=sig: s.emit(self.rec.id))
            actions.addWidget(b)
        actions.addStretch(1)
        for glyph, tip, fn in (
            ("↑", tr("Przesuń w górę", "Move up"), lambda: self.move_requested.emit(self.rec.id, -1)),
            ("↓", tr("Przesuń w dół", "Move down"), lambda: self.move_requested.emit(self.rec.id, 1)),
            ("✎", tr("Edytuj widok", "Edit view"), lambda: self.edit_requested.emit(self.rec.id)),
            ("🗑", tr("Usuń widok", "Delete view"), lambda: self.delete_requested.emit(self.rec.id)),
        ):
            t = QtWidgets.QToolButton()
            t.setText(glyph)
            t.setToolTip(tip)
            t.setCursor(Qt.PointingHandCursor)
            t.clicked.connect(fn)
            actions.addWidget(t)
        root.addLayout(actions)
        self.refresh_badges()

    # --------------------------------------------------------- updates
    def rebuild_metrics(self) -> None:
        while self.metrics_box.count():
            item = self.metrics_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._rows = {}
        for m in self.registry.active_metrics():
            row = MetricRow(m, self.rec.metric(m.key))
            row.changed.connect(self.changed.emit)
            self.metrics_box.addWidget(row)
            self._rows[m.key] = row
        self.updateGeometry()

    def update_thumbnail(self) -> None:
        pm = pixmap_from_b64(self.rec.thumb_b64)
        if pm is None or pm.isNull():
            pm = placeholder_pixmap(THUMB_W - 4, THUMB_H - 4, tr("brak miniatury", "no thumbnail"))
        else:
            pm = pm.scaled(THUMB_W - 4, THUMB_H - 4, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumb.setPixmap(pm)

    def refresh_badges(self) -> None:
        self.b_layout.setVisible(bool(self.rec.disp))
        self.b_frame.setVisible(bool(self.rec.shot_path) and os.path.isfile(self.rec.shot_path))
        n = len(self.rec.view)
        self.b_cam.setText(tr("kamera: %d wart.", "camera: %d values") % n)
        self.b_cam.setToolTip(self.rec.view_text)

    def refresh_from_record(self) -> None:
        self.name.setText(self.rec.name)
        self.sel.setChecked(bool(self.rec.selected))
        self.plain.setChecked(bool(self.rec.plain))
        self.update_thumbnail()
        self.refresh_badges()
        self.rebuild_metrics()

    # ---------------------------------------------------------- events
    def _on_select(self, on: bool) -> None:
        self.rec.selected = bool(on)
        self.setProperty("selected", bool(on))
        repolish(self)
        self.changed.emit()

    def _on_name(self) -> None:
        new = self.name.text().strip()
        if not new:
            self.name.setText(self.rec.name)
            return
        if new != self.rec.name:
            self.rec.name = new
            self.changed.emit()

    def _on_plain(self, on: bool) -> None:
        self.rec.plain = bool(on)
        self.changed.emit()
