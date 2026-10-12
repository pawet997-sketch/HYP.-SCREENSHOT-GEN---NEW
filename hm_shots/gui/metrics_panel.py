# -*- coding: utf-8 -*-
"""Configuration of quality-check metrics: which ones appear on the tiles,
their default limits and the HyperMesh command recipes (editable / learned)."""
from __future__ import annotations

from typing import Optional

from ..i18n import tr
from ..quality import Metric
from .qt import Qt, QtWidgets, Signal
from .widgets import button, hint_label


class MetricsPanel(QtWidgets.QWidget):
    changed = Signal()
    learn_requested = Signal(str)
    test_requested = Signal(str)

    def __init__(self, project, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._current: Optional[str] = None
        self._updating = False
        self._build()
        self.reload()

    @property
    def registry(self):
        return self.project.metrics

    def _build(self) -> None:
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(QtWidgets.QLabel(tr("Metryki widoczne na kafelkach widoków:", "Metrics shown on the view tiles:")))
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumWidth(220)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentItemChanged.connect(lambda cur, _prev: self._select(cur))
        left.addWidget(self.list, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button("↑", "small", tr("Wyżej", "Up"), lambda: self._move(-1)))
        row.addWidget(button("↓", "small", tr("Niżej", "Down"), lambda: self._move(1)))
        row.addStretch(1)
        row.addWidget(button(tr("+ Własna", "+ Custom"), "small", tr("Dodaj własną metrykę", "Add a custom metric"), self._add_custom))
        row.addWidget(button(tr("Usuń", "Remove"), "small", tr("Usuń własną metrykę", "Remove the custom metric"), self._remove))
        left.addLayout(row)
        root.addLayout(left, 0)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(6)
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(10)
        self.label = QtWidgets.QLineEdit()
        self.label.setToolTip(tr("Prefiks plików i nazwa folderu dla tej metryki", "File prefix and folder name for this metric"))
        self.label.editingFinished.connect(self._apply_fields)
        form.addRow(tr("Prefiks / folder:", "Prefix / folder:"), self.label)
        self.name_pl = QtWidgets.QLineEdit()
        self.name_pl.editingFinished.connect(self._apply_fields)
        form.addRow(tr("Nazwa (PL):", "Name (PL):"), self.name_pl)
        self.name_en = QtWidgets.QLineEdit()
        self.name_en.editingFinished.connect(self._apply_fields)
        form.addRow(tr("Nazwa (EN):", "Name (EN):"), self.name_en)
        thr_row = QtWidgets.QHBoxLayout()
        self.thr = QtWidgets.QDoubleSpinBox()
        self.thr.setDecimals(4)
        self.thr.setRange(-1e6, 1e6)
        self.thr.valueChanged.connect(lambda _v: self._apply_fields())
        thr_row.addWidget(self.thr)
        self.fail = QtWidgets.QComboBox()
        self.fail.addItem(tr("element zły, gdy wartość > próg", "element fails when value > limit"), "above")
        self.fail.addItem(tr("element zły, gdy wartość < próg", "element fails when value < limit"), "below")
        self.fail.currentIndexChanged.connect(lambda _i: self._apply_fields())
        thr_row.addWidget(self.fail, 1)
        form.addRow(tr("Domyślny próg:", "Default limit:"), thr_row)
        right.addLayout(form)

        right.addWidget(QtWidgets.QLabel(tr("Komendy kontroli ({thr} = wartość graniczna):", "Check commands ({thr} = limit value):")))
        self.recipe = QtWidgets.QPlainTextEdit()
        self.recipe.setObjectName("Code")
        self.recipe.setFixedHeight(70)
        self.recipe.textChanged.connect(self._apply_text)
        right.addWidget(self.recipe)
        right.addWidget(QtWidgets.QLabel(tr("Komendy „tylko elementy poza limitem” (opcjonalne):", "“Only elements outside the limit” commands (optional):")))
        self.hide = QtWidgets.QPlainTextEdit()
        self.hide.setObjectName("Code")
        self.hide.setFixedHeight(62)
        self.hide.textChanged.connect(self._apply_text)
        right.addWidget(self.hide)
        right.addWidget(QtWidgets.QLabel(tr("Komendy porządkujące po zrzucie:", "Cleanup commands after the shot:")))
        self.cleanup = QtWidgets.QPlainTextEdit()
        self.cleanup.setObjectName("Code")
        self.cleanup.setFixedHeight(62)
        self.cleanup.textChanged.connect(self._apply_text)
        right.addWidget(self.cleanup)

        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(button(tr("● Nagraj z HyperMesh…", "● Record from HyperMesh…"), "primary",
                              tr("Wykonaj kontrolę ręcznie w HM – komendy z command.tcl staną się szablonem",
                                 "Perform the check by hand in HM – the command.tcl lines become the template"),
                              lambda: self._current and self.learn_requested.emit(self._current)))
        btns.addWidget(button(tr("Testuj na modelu", "Test on model"), "",
                              tr("Uruchom komendy z domyślnym progiem na otwartym modelu", "Run the commands with the default limit on the open model"),
                              lambda: self._current and self.test_requested.emit(self._current)))
        btns.addWidget(button(tr("Przywróć domyślne", "Restore defaults"), "", "", self._reset))
        btns.addStretch(1)
        right.addLayout(btns)
        right.addWidget(hint_label(tr(
            "Domyślne szablony używają natywnych komend panelu Check Elements (*elementtestaspect, *elementtestjacobian, *elementtestskew…), "
            "dzięki czemu HyperMesh sam rysuje wyróżnienie i legendę. Jeśli w Twojej wersji HyperMesh składnia jest inna, "
            "nagraj komendy („Nagraj z HyperMesh…”) lub popraw je ręcznie. Po zrzucie wykonywane są komendy porządkujące.",
            "The default templates use the native Check Elements commands (*elementtestaspect, *elementtestjacobian, *elementtestskew…), "
            "so HyperMesh draws its own highlighting and legend. If your HyperMesh release uses a different syntax, record the commands "
            "(“Record from HyperMesh…”) or edit them by hand. The cleanup commands run after each shot.")))
        root.addLayout(right, 1)

    # ------------------------------------------------------------- model
    def reload(self) -> None:
        self._updating = True
        self.list.clear()
        active = self.registry.active
        ordered = [self.registry.get(k) for k in active if self.registry.get(k)]
        ordered += [m for m in self.registry.all() if m.key not in active]
        for m in ordered:
            it = QtWidgets.QListWidgetItem(m.name + ("" if m.builtin else "  ★"))
            it.setData(Qt.UserRole, m.key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if m.key in active else Qt.Unchecked)
            self.list.addItem(it)
        self._updating = False
        if self.list.count():
            self.list.setCurrentRow(0)

    def _metric(self) -> Optional[Metric]:
        return self.registry.get(self._current) if self._current else None

    def _select(self, item) -> None:
        self._current = item.data(Qt.UserRole) if item else None
        m = self._metric()
        self._updating = True
        for w in (self.label, self.name_pl, self.name_en, self.thr, self.fail, self.recipe, self.hide, self.cleanup):
            w.setEnabled(m is not None)
        if m is not None:
            self.label.setText(m.label)
            self.name_pl.setText(m.name_pl)
            self.name_en.setText(m.name_en)
            self.thr.setDecimals(max(2, m.decimals))
            self.thr.setValue(m.default_threshold)
            self.fail.setCurrentIndex(0 if m.fail_when == "above" else 1)
            self.recipe.setPlainText("\n".join(m.recipe))
            self.hide.setPlainText("\n".join(m.hide_passed))
            self.cleanup.setPlainText("\n".join(m.cleanup))
        self._updating = False

    def refresh_current(self) -> None:
        cur = self.list.currentItem()
        self._select(cur)

    def _apply_fields(self) -> None:
        m = self._metric()
        if self._updating or m is None:
            return
        m.label = self.label.text().strip() or m.label
        m.name_pl = self.name_pl.text().strip() or m.name_pl
        m.name_en = self.name_en.text().strip() or m.name_en
        m.default_threshold = float(self.thr.value())
        m.fail_when = self.fail.currentData() or "above"
        self._refresh_item_text()
        self.project.dirty = True
        self.changed.emit()

    def _apply_text(self) -> None:
        m = self._metric()
        if self._updating or m is None:
            return
        m.recipe = [ln for ln in self.recipe.toPlainText().splitlines() if ln.strip()]
        m.hide_passed = [ln for ln in self.hide.toPlainText().splitlines() if ln.strip()]
        m.cleanup = [ln for ln in self.cleanup.toPlainText().splitlines() if ln.strip()]
        self.project.dirty = True

    def _refresh_item_text(self) -> None:
        it = self.list.currentItem()
        m = self._metric()
        if it is not None and m is not None:
            self._updating = True
            it.setText(m.name + ("" if m.builtin else "  ★"))
            self._updating = False

    def _on_item_changed(self, _item) -> None:
        if self._updating:
            return
        keys = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                keys.append(it.data(Qt.UserRole))
        self.registry.set_active(keys)
        self.project.dirty = True
        self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        new = row + delta
        if row < 0 or new < 0 or new >= self.list.count():
            return
        self._updating = True
        it = self.list.takeItem(row)
        self.list.insertItem(new, it)
        self.list.setCurrentRow(new)
        self._updating = False
        self._on_item_changed(None)

    def _add_custom(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, tr("Własna metryka", "Custom metric"),
                                                  tr("Nazwa metryki (np. Min Size):", "Metric name (e.g. Min Size):"))
        if not ok or not name.strip():
            return
        key = name.strip().lower().replace(" ", "_")
        m = self.registry.add_custom(key, name.strip().replace(" ", "_"), name.strip(), 1.0)
        self.registry.active.append(m.key)
        self.reload()
        self.list.setCurrentRow(self.list.count() - 1)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == m.key:
                self.list.setCurrentRow(i)
        self.project.dirty = True
        self.changed.emit()

    def _remove(self) -> None:
        m = self._metric()
        if m is None:
            return
        if m.builtin:
            QtWidgets.QMessageBox.information(self, tr("Metryka wbudowana", "Built-in metric"),
                                              tr("Wbudowanych metryk nie można usunąć – odznacz ją, aby ukryć na kafelkach.",
                                                 "Built-in metrics cannot be removed – untick it to hide it on the tiles."))
            return
        self.registry.remove(m.key)
        self.reload()
        self.project.dirty = True
        self.changed.emit()

    def _reset(self) -> None:
        m = self._metric()
        if m is None:
            return
        self.registry.reset(m.key)
        self.refresh_current()
        self.project.dirty = True
        self.changed.emit()
