# -*- coding: utf-8 -*-
"""
Interactive slide preview / layout editor.

The slide is drawn in a QGraphicsView; every slot is a draggable, resizable
rectangle (REF = blue, INF = red, ANY = grey).  The editor shows the real
content of any slide of the planned deck (pictures already generated, dashed
placeholders for the rest), offers the quick symmetric presets
(left / right, top / bottom), mirroring, grid snapping and JSON save / load
of the arrangement so it can be reused for later REF / INF sessions.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from ..i18n import tr
from ..layout import ROLE_ANY, ROLE_INF, ROLE_REF, SlideLayout, Slot, fit_image, layouts_dir
from .qt import Qt, QtCore, QtGui, QtWidgets, Signal
from .widgets import FlowLayout, button, hint_label

SCENE_W = 960.0
ROLE_COLOR = {ROLE_REF: "#2563EB", ROLE_INF: "#DC2626", ROLE_ANY: "#4B5563"}
HANDLE = 9.0


class SlotItem(QtWidgets.QGraphicsRectItem):
    """One slot rectangle with move / resize behaviour."""

    def __init__(self, slot: Slot, editor: "LayoutEditor") -> None:
        super().__init__()
        self.slot = slot
        self.editor = editor
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self._mode = ""          # move | resize-<edges>
        self._press_scene = QtCore.QPointF()
        self._press_rect = QtCore.QRectF()
        self.label = QtWidgets.QGraphicsSimpleTextItem(self)
        self.label.setZValue(12)
        self.pic = QtWidgets.QGraphicsPixmapItem(self)
        self.pic.setZValue(11)
        self.pic.setTransformationMode(Qt.SmoothTransformation)
        self.caption = QtWidgets.QGraphicsSimpleTextItem(self)
        self.caption.setZValue(12)
        self.ph_text = QtWidgets.QGraphicsSimpleTextItem(self)
        self.ph_text.setZValue(12)
        self.sync_from_slot()

    # ------------------------------------------------------------ geometry
    def sync_from_slot(self) -> None:
        sw, sh = self.editor.scene_size()
        self.setPos(self.slot.x * sw, self.slot.y * sh)
        self.setRect(0, 0, self.slot.w * sw, self.slot.h * sh)
        self._restyle()
        self.editor.decorate(self)

    def commit_to_slot(self) -> None:
        sw, sh = self.editor.scene_size()
        r = self.rect()
        self.slot.x = self.pos().x() / sw
        self.slot.y = self.pos().y() / sh
        self.slot.w = r.width() / sw
        self.slot.h = r.height() / sh
        self.slot.clamp()
        self.editor.slide_layout.preset = "custom"

    def _restyle(self) -> None:
        col = QtGui.QColor(ROLE_COLOR.get(self.slot.role, ROLE_COLOR[ROLE_ANY]))
        pen = QtGui.QPen(col, 2 if self.isSelected() else 1.2)
        if not self.isSelected():
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        fill = QtGui.QColor(col)
        fill.setAlpha(28 if not self.isSelected() else 50)
        self.setBrush(QtGui.QBrush(fill))
        self.label.setBrush(QtGui.QBrush(col))
        f = QtGui.QFont()
        f.setPointSizeF(9)
        f.setBold(True)
        self.label.setFont(f)
        self.label.setText("%s · %s" % (self.slot.role, self.slot.id))
        self.label.setPos(5, 3)

    def itemChange(self, change, value):  # noqa: N802
        if change == QtWidgets.QGraphicsItem.ItemSelectedHasChanged:
            self._restyle()
            self.editor.selection_changed()
        return super().itemChange(change, value)

    # --------------------------------------------------------------- mouse
    def _hit(self, pos: QtCore.QPointF) -> str:
        r = self.rect()
        left = abs(pos.x() - r.left()) <= HANDLE
        right = abs(pos.x() - r.right()) <= HANDLE
        top = abs(pos.y() - r.top()) <= HANDLE
        bottom = abs(pos.y() - r.bottom()) <= HANDLE
        mode = ("t" if top else "b" if bottom else "") + ("l" if left else "r" if right else "")
        return "resize-" + mode if mode else "move"

    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        mode = self._hit(event.pos())
        cursors = {"resize-tl": Qt.SizeFDiagCursor, "resize-br": Qt.SizeFDiagCursor, "resize-tr": Qt.SizeBDiagCursor,
                   "resize-bl": Qt.SizeBDiagCursor, "resize-l": Qt.SizeHorCursor, "resize-r": Qt.SizeHorCursor,
                   "resize-t": Qt.SizeVerCursor, "resize-b": Qt.SizeVerCursor}
        self.setCursor(cursors.get(mode, Qt.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._mode = self._hit(event.pos())
        self._press_scene = event.scenePos()
        self._press_rect = QtCore.QRectF(self.pos(), self.rect().size())
        self.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._mode:
            return
        d = event.scenePos() - self._press_scene
        r = QtCore.QRectF(self._press_rect)
        sw, sh = self.editor.scene_size()
        if self._mode == "move":
            r.translate(d)
        else:
            m = self._mode[len("resize-"):]
            if "l" in m:
                r.setLeft(min(r.left() + d.x(), r.right() - 20))
            if "r" in m:
                r.setRight(max(r.right() + d.x(), r.left() + 20))
            if "t" in m:
                r.setTop(min(r.top() + d.y(), r.bottom() - 20))
            if "b" in m:
                r.setBottom(max(r.bottom() + d.y(), r.top() + 20))
        r = self.editor.snap_rect(r)
        # clamp inside the slide
        if r.left() < 0:
            r.moveLeft(0)
        if r.top() < 0:
            r.moveTop(0)
        if r.right() > sw:
            r.moveRight(sw) if self._mode == "move" else r.setRight(sw)
        if r.bottom() > sh:
            r.moveBottom(sh) if self._mode == "move" else r.setBottom(sh)
        self.setPos(r.topLeft())
        self.setRect(0, 0, r.width(), r.height())
        self.editor.decorate(self)
        self.editor.live_geometry(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._mode:
            self._mode = ""
            self.commit_to_slot()
            self.editor.slot_edited(self)
        super().mouseReleaseEvent(event)


class SlideView(QtWidgets.QGraphicsView):
    def __init__(self, editor: "LayoutEditor") -> None:
        super().__init__()
        self.editor = editor
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform | QtGui.QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setMinimumHeight(260)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.editor.fit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Delete:
            self.editor.delete_selected()
            return
        step = self.editor.grid_step_scene() or 4.0
        moves = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0), Qt.Key_Up: (0, -step), Qt.Key_Down: (0, step)}
        if event.key() in moves:
            self.editor.nudge(*moves[event.key()])
            return
        super().keyPressEvent(event)


class LayoutEditor(QtWidgets.QWidget):
    layout_changed = Signal()
    status = Signal(str)

    def __init__(self, project, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.slide_layout: SlideLayout = project.layout
        self._items: List[SlotItem] = []
        self._pix_cache: Dict[str, QtGui.QPixmap] = {}
        self._slide_index = 0
        self._plan = []
        self._updating = False
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = SlideView(self)
        self.view.setScene(self.scene)
        self._build()
        self.rebuild()

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        bar = FlowLayout(h_spacing=6, v_spacing=6)
        bar.addWidget(QtWidgets.QLabel(tr("Szybki układ:", "Quick layout:")))
        self.pairs = QtWidgets.QSpinBox()
        self.pairs.setRange(1, 6)
        self.pairs.setValue(max(1, self.slide_layout.pairs_per_slide()))
        self.pairs.setToolTip(tr("Ile par REF/INF (lub zdjęć) na jednym slajdzie", "How many REF/INF pairs (or pictures) per slide"))
        self.pairs.setFixedWidth(52)
        bar.addWidget(self.pairs)
        bar.addWidget(button(tr("◧ Lewa / Prawa", "◧ Left / Right"), "", tr("REF po lewej, INF po prawej – symetrycznie", "REF left, INF right – symmetric"), self.preset_lr))
        bar.addWidget(button(tr("⬒ Góra / Dół", "⬒ Top / Bottom"), "", tr("REF u góry, INF u dołu – symetrycznie", "REF top, INF bottom – symmetric"), self.preset_tb))
        bar.addWidget(button(tr("⇋ Lustro L/P", "⇋ Mirror L/R"), "", tr("Odbij sloty REF na stronę INF (symetria pozioma)", "Mirror REF slots onto the INF side (horizontal symmetry)"), lambda: self.mirror("lr")))
        bar.addWidget(button(tr("⇅ Lustro G/D", "⇅ Mirror T/B"), "", tr("Odbij sloty REF na stronę INF (symetria pionowa)", "Mirror REF slots onto the INF side (vertical symmetry)"), lambda: self.mirror("tb")))
        bar.addWidget(button(tr("⇄ Zamień REF↔INF", "⇄ Swap REF↔INF"), "", "", self.swap_roles))
        root.addLayout(bar)

        bar2 = FlowLayout(h_spacing=6, v_spacing=6)
        bar2.addWidget(button(tr("+ REF", "+ REF"), "small", tr("Dodaj slot REF", "Add a REF slot"), lambda: self.add_slot(ROLE_REF)))
        bar2.addWidget(button(tr("+ INF", "+ INF"), "small", tr("Dodaj slot INF", "Add an INF slot"), lambda: self.add_slot(ROLE_INF)))
        bar2.addWidget(button(tr("+ Dowolny", "+ Any"), "small", tr("Dodaj slot bez roli (tryb pojedynczy)", "Add a role-less slot (single mode)"), lambda: self.add_slot(ROLE_ANY)))
        bar2.addWidget(button(tr("Usuń slot", "Delete slot"), "small", "", self.delete_selected))
        bar2.addWidget(button(tr("Wyrównaj rozmiary", "Equalise sizes"), "small", "", self.equalise))
        bar2.addWidget(QtWidgets.QLabel(tr("Siatka:", "Grid:")))
        self.grid = QtWidgets.QComboBox()
        for label, val in ((tr("wył.", "off"), 0.0), ("1 %", 0.01), ("2,5 %", 0.025), ("5 %", 0.05)):
            self.grid.addItem(label, val)
        self.grid.setCurrentIndex(2)
        self.grid.currentIndexChanged.connect(lambda _i: self.rebuild())
        bar2.addWidget(self.grid)
        self.aspect = QtWidgets.QComboBox()
        self.aspect.addItems(["16:9", "4:3"])
        self.aspect.setCurrentText(self.slide_layout.aspect)
        self.aspect.currentTextChanged.connect(self._on_aspect)
        bar2.addWidget(self.aspect)
        self.cb_title = QtWidgets.QCheckBox(tr("Tytuł slajdu", "Slide title"))
        self.cb_title.setChecked(self.slide_layout.show_title)
        self.cb_title.toggled.connect(self._on_title)
        bar2.addWidget(self.cb_title)
        bar2.addWidget(button(tr("💾 Zapisz układ…", "💾 Save layout…"), "", "", self.save_layout))
        bar2.addWidget(button(tr("📂 Wczytaj układ…", "📂 Load layout…"), "", "", self.load_layout))
        root.addLayout(bar2)

        root.addWidget(self.view, 1)

        bottom = FlowLayout(h_spacing=6, v_spacing=6)
        bottom.addWidget(QtWidgets.QLabel(tr("Podgląd slajdu:", "Slide preview:")))
        self.prev_btn = button("◀", "small", "", lambda: self.set_slide(self._slide_index - 1))
        self.next_btn = button("▶", "small", "", lambda: self.set_slide(self._slide_index + 1))
        self.slide_lab = QtWidgets.QLabel("1 / 1")
        bottom.addWidget(self.prev_btn)
        bottom.addWidget(self.slide_lab)
        bottom.addWidget(self.next_btn)
        bottom.addWidget(QtWidgets.QLabel("   " + tr("Slot:", "Slot:")))
        self.sel_lab = QtWidgets.QLabel("–")
        self.sel_lab.setObjectName("Badge")
        bottom.addWidget(self.sel_lab)
        self.spins: Dict[str, QtWidgets.QDoubleSpinBox] = {}
        for key, lab in (("x", "X"), ("y", "Y"), ("w", tr("Szer.", "W")), ("h", tr("Wys.", "H"))):
            bottom.addWidget(QtWidgets.QLabel(lab))
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix(" %")
            sp.setFixedWidth(74)
            sp.valueChanged.connect(lambda _v, k=key: self._spin_changed(k))
            bottom.addWidget(sp)
            self.spins[key] = sp
        self.role = QtWidgets.QComboBox()
        self.role.addItems([ROLE_REF, ROLE_INF, ROLE_ANY])
        self.role.currentTextChanged.connect(self._role_changed)
        bottom.addWidget(self.role)
        self.fit_combo = QtWidgets.QComboBox()
        self.fit_combo.addItem(tr("dopasuj", "fit"), "contain")
        self.fit_combo.addItem(tr("wypełnij (przytnij)", "fill (crop)"), "cover")
        self.fit_combo.currentIndexChanged.connect(self._fit_changed)
        bottom.addWidget(self.fit_combo)
        self.cb_caption = QtWidgets.QCheckBox(tr("Podpis", "Caption"))
        self.cb_caption.toggled.connect(self._caption_changed)
        bottom.addWidget(self.cb_caption)
        root.addLayout(bottom)
        root.addWidget(hint_label(tr(
            "Przeciągnij slot, aby go przesunąć; chwyć krawędź lub róg, aby zmienić rozmiar. Strzałki przesuwają zaznaczony slot, Delete usuwa. "
            "Niebieskie = REF, czerwone = INF. Zdjęcia trafiają do slotów w kolejności widoków i metryk.",
            "Drag a slot to move it; grab an edge or corner to resize. Arrow keys nudge the selected slot, Delete removes it. "
            "Blue = REF, red = INF. Pictures fill the slots in the order of views and metrics.")))
        self._sync_props(None)

    # ------------------------------------------------------------ geometry
    def scene_size(self):
        return SCENE_W, SCENE_W / self.slide_layout.ratio

    def grid_step_scene(self) -> float:
        val = float(self.grid.currentData() or 0.0)
        return val * SCENE_W if val else 0.0

    def snap_rect(self, r: QtCore.QRectF) -> QtCore.QRectF:
        g = float(self.grid.currentData() or 0.0)
        if not g:
            return r
        sw, sh = self.scene_size()
        gx, gy = g * sw, g * sh

        def sn(v: float, step: float) -> float:
            return round(v / step) * step

        out = QtCore.QRectF(sn(r.left(), gx), sn(r.top(), gy), max(gx, sn(r.width(), gx)), max(gy, sn(r.height(), gy)))
        return out

    def fit(self) -> None:
        sw, sh = self.scene_size()
        self.view.fitInView(QtCore.QRectF(-6, -6, sw + 12, sh + 12), Qt.KeepAspectRatio)

    # ------------------------------------------------------------- rebuild
    def set_project(self, project) -> None:
        self.project = project
        self.slide_layout = project.layout
        self.aspect.setCurrentText(self.slide_layout.aspect)
        self.cb_title.setChecked(self.slide_layout.show_title)
        self.pairs.setValue(max(1, self.slide_layout.pairs_per_slide()))
        self.rebuild()

    def rebuild(self) -> None:
        self.slide_layout = self.project.layout
        self.scene.clear()
        self._items = []
        sw, sh = self.scene_size()
        self.scene.setSceneRect(-10, -10, sw + 20, sh + 20)
        slide = self.scene.addRect(0, 0, sw, sh, QtGui.QPen(QtGui.QColor("#9CA3AF"), 1), QtGui.QBrush(QtGui.QColor("#FFFFFF")))
        slide.setZValue(0)
        g = float(self.grid.currentData() or 0.0)
        if g:
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 16), 0.5)
            x = g * sw
            while x < sw:
                self.scene.addLine(x, 0, x, sh, pen).setZValue(1)
                x += g * sw
            y = g * sh
            while y < sh:
                self.scene.addLine(0, y, sw, y, pen).setZValue(1)
                y += g * sh
        if self.slide_layout.show_title:
            th = self.slide_layout.title_height * sh
            self.scene.addRect(0, 0, sw, th, QtGui.QPen(Qt.NoPen), QtGui.QBrush(QtGui.QColor(0, 0, 0, 10))).setZValue(1)
        try:
            self._plan = self.project.deck_plan()
        except Exception:  # noqa: BLE001
            self._plan = []
        self._slide_index = max(0, min(self._slide_index, max(0, len(self._plan) - 1)))
        self._draw_title()
        for slot in self.slide_layout.slots:
            item = SlotItem(slot, self)
            self.scene.addItem(item)
            self._items.append(item)
        self.slide_lab.setText("%d / %d" % (self._slide_index + 1, max(1, len(self._plan))))
        self.fit()
        self._sync_props(None)

    def _draw_title(self) -> None:
        sw, sh = self.scene_size()
        if not self.slide_layout.show_title:
            return
        text = tr("Tytuł slajdu", "Slide title")
        if self._plan and self._slide_index < len(self._plan):
            text = self._plan[self._slide_index].title or text
        t = self.scene.addSimpleText(text)
        f = QtGui.QFont()
        f.setPointSizeF(14)
        f.setBold(True)
        t.setFont(f)
        t.setBrush(QtGui.QBrush(QtGui.QColor("#1F2937")))
        th = self.slide_layout.title_height * sh
        t.setPos(self.slide_layout.margin * sw, (th - t.boundingRect().height()) / 2.0)
        t.setZValue(2)

    def _placement_for(self, slot: Slot):
        if not self._plan or self._slide_index >= len(self._plan):
            return None
        for p in self._plan[self._slide_index].placements:
            if p.slot is slot or p.slot.id == slot.id:
                return p
        return None

    def _pixmap(self, path: str) -> Optional[QtGui.QPixmap]:
        if path in self._pix_cache:
            return self._pix_cache[path]
        pm = QtGui.QPixmap(path) if path and os.path.isfile(path) else QtGui.QPixmap()
        if pm.isNull():
            self._pix_cache[path] = None
            return None
        if pm.width() > 1200:
            pm = pm.scaledToWidth(1200, Qt.SmoothTransformation)
        self._pix_cache[path] = pm
        return pm

    def invalidate_images(self) -> None:
        self._pix_cache = {}

    def decorate(self, item: SlotItem) -> None:
        """Draw the picture / placeholder / caption of the slot for the previewed slide."""
        sw, sh = self.scene_size()
        r = item.rect()
        placement = self._placement_for(item.slot)
        item.pic.setVisible(False)
        item.ph_text.setVisible(False)
        item.caption.setVisible(False)
        if placement is None:
            return
        tmp = Slot(item.slot.id, item.slot.role, item.pos().x() / sw, item.pos().y() / sh, r.width() / sw, r.height() / sh,
                   item.slot.fit, item.slot.caption)
        cap_h = self.slide_layout.caption_height if (self.project.settings.pptx_captions and tmp.caption) else 0.0
        pm = self._pixmap(placement.image) if placement.image else None
        if pm is not None:
            x, y, w, h, crop = fit_image(tmp, pm.width(), pm.height(), cap_h, self.slide_layout.ratio)
            src = pm
            if crop:
                l, t, rr, b = crop
                src = pm.copy(int(l * pm.width()), int(t * pm.height()), int((1 - l - rr) * pm.width()), int((1 - t - b) * pm.height()))
            target_w = max(1.0, w * sw)
            target_h = max(1.0, h * sh)
            item.pic.setPixmap(src)
            sx = target_w / src.width()
            sy = target_h / src.height()
            item.pic.setTransform(QtGui.QTransform().scale(sx, sy))
            item.pic.setPos((x - tmp.x) * sw, (y - tmp.y) * sh)
            item.pic.setVisible(True)
            if cap_h and placement.caption:
                item.caption.setText(placement.caption)
                f = QtGui.QFont()
                f.setPointSizeF(8)
                f.setBold(True)
                item.caption.setFont(f)
                item.caption.setBrush(QtGui.QBrush(QtGui.QColor(ROLE_COLOR.get(placement.role, "#374151"))))
                br = item.caption.boundingRect()
                cy = min((y - tmp.y) * sh + target_h, r.height() - cap_h * sh)
                item.caption.setPos((r.width() - br.width()) / 2.0, cy + (cap_h * sh - br.height()) / 2.0)
                item.caption.setVisible(True)
        else:
            item.ph_text.setText(placement.placeholder.replace("\n", " · "))
            f = QtGui.QFont()
            f.setPointSizeF(8.5)
            item.ph_text.setFont(f)
            item.ph_text.setBrush(QtGui.QBrush(QtGui.QColor("#6B7280")))
            br = item.ph_text.boundingRect()
            item.ph_text.setPos((r.width() - br.width()) / 2.0, (r.height() - br.height()) / 2.0)
            item.ph_text.setVisible(True)

    # ------------------------------------------------------------ actions
    def _emit(self) -> None:
        self.project.dirty = True
        self.layout_changed.emit()

    def preset_lr(self) -> None:
        self.slide_layout.apply_left_right(self.pairs.value(), self.project.settings.comparison)
        self.rebuild()
        self._emit()

    def preset_tb(self) -> None:
        self.slide_layout.apply_top_bottom(self.pairs.value(), self.project.settings.comparison)
        self.rebuild()
        self._emit()

    def preset_grid(self, n: int) -> None:
        self.slide_layout.apply_grid(n)
        self.rebuild()
        self._emit()

    def mirror(self, axis: str) -> None:
        if not self.slide_layout.slots_by_role(ROLE_REF):
            self.status.emit(tr("Brak slotów REF do odbicia.", "No REF slots to mirror."))
            return
        self.slide_layout.mirror(axis)
        self.rebuild()
        self._emit()

    def swap_roles(self) -> None:
        self.slide_layout.swap_roles()
        self.rebuild()
        self._emit()

    def add_slot(self, role: str) -> None:
        n = len(self.slide_layout.slots)
        s = self.slide_layout.add_slot(role, 0.1 + 0.05 * (n % 6), self.slide_layout.content_top() + 0.05 * (n % 6), 0.35, 0.4)
        self.rebuild()
        for it in self._items:
            if it.slot is s:
                it.setSelected(True)
        self._emit()

    def delete_selected(self) -> None:
        sel = [it for it in self._items if it.isSelected()]
        if not sel:
            return
        for it in sel:
            self.slide_layout.remove_slot(it.slot.id)
        self.rebuild()
        self._emit()

    def equalise(self) -> None:
        self.slide_layout.align("equal_size")
        self.rebuild()
        self._emit()

    def nudge(self, dx: float, dy: float) -> None:
        sel = [it for it in self._items if it.isSelected()]
        if not sel:
            return
        sw, sh = self.scene_size()
        for it in sel:
            it.setPos(it.pos().x() + dx, it.pos().y() + dy)
            it.commit_to_slot()
            it.sync_from_slot()
        self._sync_props(sel[0])
        self._emit()

    def set_slide(self, index: int) -> None:
        n = max(1, len(self._plan))
        self._slide_index = max(0, min(index, n - 1))
        self.rebuild()

    def slot_edited(self, item: SlotItem) -> None:
        self._sync_props(item)
        self._emit()

    def live_geometry(self, item: SlotItem) -> None:
        if self._updating:
            return
        self._updating = True
        sw, sh = self.scene_size()
        self.spins["x"].setValue(item.pos().x() / sw * 100)
        self.spins["y"].setValue(item.pos().y() / sh * 100)
        self.spins["w"].setValue(item.rect().width() / sw * 100)
        self.spins["h"].setValue(item.rect().height() / sh * 100)
        self._updating = False

    def selection_changed(self) -> None:
        sel = [it for it in self._items if it.isSelected()]
        self._sync_props(sel[0] if sel else None)

    def _selected_item(self) -> Optional[SlotItem]:
        for it in self._items:
            if it.isSelected():
                return it
        return None

    def _sync_props(self, item: Optional[SlotItem]) -> None:
        self._updating = True
        enabled = item is not None
        for w in list(self.spins.values()) + [self.role, self.fit_combo, self.cb_caption]:
            w.setEnabled(enabled)
        if item is None:
            self.sel_lab.setText("–")
        else:
            s = item.slot
            self.sel_lab.setText("%s · %s" % (s.role, s.id))
            self.spins["x"].setValue(s.x * 100)
            self.spins["y"].setValue(s.y * 100)
            self.spins["w"].setValue(s.w * 100)
            self.spins["h"].setValue(s.h * 100)
            self.role.setCurrentText(s.role)
            self.fit_combo.setCurrentIndex(0 if s.fit == "contain" else 1)
            self.cb_caption.setChecked(s.caption)
        self._updating = False

    def _spin_changed(self, key: str) -> None:
        if self._updating:
            return
        item = self._selected_item()
        if item is None:
            return
        setattr(item.slot, key, self.spins[key].value() / 100.0)
        item.slot.clamp()
        self.slide_layout.preset = "custom"
        item.sync_from_slot()
        self._emit()

    def _role_changed(self, role: str) -> None:
        if self._updating:
            return
        item = self._selected_item()
        if item is None:
            return
        item.slot.role = role
        self.slide_layout.preset = "custom"
        self.rebuild()
        self._emit()

    def _fit_changed(self, idx: int) -> None:
        if self._updating:
            return
        item = self._selected_item()
        if item is None:
            return
        item.slot.fit = self.fit_combo.currentData() or "contain"
        item.sync_from_slot()
        self._emit()

    def _caption_changed(self, on: bool) -> None:
        if self._updating:
            return
        item = self._selected_item()
        if item is None:
            return
        item.slot.caption = bool(on)
        item.sync_from_slot()
        self._emit()

    def _on_aspect(self, text: str) -> None:
        if self._updating:
            return
        self.slide_layout.aspect = text
        self.rebuild()
        self._emit()

    def _on_title(self, on: bool) -> None:
        if self._updating:
            return
        self.slide_layout.show_title = bool(on)
        self.rebuild()
        self._emit()

    # ------------------------------------------------------- persistence
    def save_layout(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Zapisz układ slajdu", "Save slide layout"),
                                                        os.path.join(layouts_dir(), "uklad.hmlayout.json"),
                                                        "HM Shots layout (*.hmlayout.json *.json)")
        if not path:
            return
        try:
            self.slide_layout.save(path)
            self.status.emit(tr("Zapisano układ: %s", "Layout saved: %s") % path)
        except OSError as exc:
            self.status.emit(tr("Nie można zapisać układu: %s", "Cannot save layout: %s") % exc)

    def load_layout(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Wczytaj układ slajdu", "Load slide layout"), layouts_dir(),
                                                        "HM Shots layout (*.hmlayout.json *.json)")
        if not path:
            return
        try:
            lay = SlideLayout.load(path)
        except (OSError, ValueError, KeyError) as exc:
            self.status.emit(tr("Nie można wczytać układu: %s", "Cannot load layout: %s") % exc)
            return
        self.project.layout = lay
        self.slide_layout = lay
        self._updating = True
        self.aspect.setCurrentText(lay.aspect)
        self.cb_title.setChecked(lay.show_title)
        self._updating = False
        self.rebuild()
        self._emit()
        self.status.emit(tr("Wczytano układ: %s", "Layout loaded: %s") % os.path.basename(path))
