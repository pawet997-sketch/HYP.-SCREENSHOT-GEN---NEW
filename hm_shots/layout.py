# -*- coding: utf-8 -*-
"""
Slide layout: rectangles (slots) on a 16:9 slide where screenshots land.

Coordinates are normalised (0..1 of slide width / height) so the same layout
works in the on-screen editor and in the PPTX writer.  Slots carry a role:

* ``REF`` / ``INF`` - comparison mode (reference vs. influence model)
* ``ANY``           - single-model mode

Presets: *left / right* and *top / bottom* symmetric arrangements, with 1..N
pairs per slide; ``mirror()`` copies the REF slots to the INF side.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ROLE_REF = "REF"
ROLE_INF = "INF"
ROLE_ANY = "ANY"
ASPECTS = {"16:9": (16.0, 9.0), "4:3": (4.0, 3.0)}


@dataclass
class Slot:
    id: str
    role: str
    x: float
    y: float
    w: float
    h: float
    fit: str = "contain"        # contain | cover
    caption: bool = True

    def rect(self):
        return self.x, self.y, self.w, self.h

    def clamp(self) -> None:
        self.w = min(max(self.w, 0.02), 1.0)
        self.h = min(max(self.h, 0.02), 1.0)
        self.x = min(max(self.x, 0.0), 1.0 - self.w)
        self.y = min(max(self.y, 0.0), 1.0 - self.h)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "role": self.role, "x": round(self.x, 5), "y": round(self.y, 5),
                "w": round(self.w, 5), "h": round(self.h, 5), "fit": self.fit, "caption": self.caption}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Slot":
        s = cls(id=str(d.get("id", "")), role=str(d.get("role", ROLE_ANY)).upper(), x=float(d.get("x", 0)),
                y=float(d.get("y", 0)), w=float(d.get("w", 0.4)), h=float(d.get("h", 0.4)),
                fit=str(d.get("fit", "contain")), caption=bool(d.get("caption", True)))
        s.clamp()
        return s


@dataclass
class SlideLayout:
    name: str = "Lewa / Prawa"
    aspect: str = "16:9"
    slots: List[Slot] = field(default_factory=list)
    show_title: bool = True
    title_height: float = 0.11
    margin: float = 0.035
    gap: float = 0.025
    caption_height: float = 0.045
    preset: str = "lr"           # lr | tb | grid | custom

    # ---- geometry helpers
    @property
    def ratio(self) -> float:
        w, h = ASPECTS.get(self.aspect, ASPECTS["16:9"])
        return w / h

    def content_top(self) -> float:
        return (self.title_height if self.show_title else 0.0) + self.margin

    def slots_by_role(self, role: str) -> List[Slot]:
        return [s for s in self.slots if s.role == role]

    @property
    def comparison(self) -> bool:
        return bool(self.slots_by_role(ROLE_REF) or self.slots_by_role(ROLE_INF))

    def pairs_per_slide(self) -> int:
        if self.comparison:
            return max(1, min(len(self.slots_by_role(ROLE_REF)), len(self.slots_by_role(ROLE_INF))) or 1)
        return max(1, len(self.slots))

    def slot(self, slot_id: str) -> Optional[Slot]:
        for s in self.slots:
            if s.id == slot_id:
                return s
        return None

    def new_slot_id(self, role: str) -> str:
        n = 1
        while self.slot("%s%d" % (role.lower(), n)):
            n += 1
        return "%s%d" % (role.lower(), n)

    def add_slot(self, role: str, x: float = 0.3, y: float = 0.3, w: float = 0.4, h: float = 0.4) -> Slot:
        s = Slot(self.new_slot_id(role), role, x, y, w, h)
        s.clamp()
        self.slots.append(s)
        self.preset = "custom"
        return s

    def remove_slot(self, slot_id: str) -> bool:
        n = len(self.slots)
        self.slots = [s for s in self.slots if s.id != slot_id]
        if len(self.slots) != n:
            self.preset = "custom"
            return True
        return False

    # ---- presets
    def _area(self):
        x0 = self.margin
        y0 = self.content_top()
        return x0, y0, 1.0 - 2 * self.margin, 1.0 - y0 - self.margin

    def apply_left_right(self, pairs: int = 1, comparison: bool = True) -> None:
        """REF column on the left, INF column on the right, ``pairs`` rows."""
        pairs = max(1, int(pairs))
        x0, y0, aw, ah = self._area()
        cw = (aw - self.gap) / 2.0
        rh = (ah - self.gap * (pairs - 1)) / pairs
        self.slots = []
        for i in range(pairs):
            y = y0 + i * (rh + self.gap)
            if comparison:
                self.slots.append(Slot("ref%d" % (i + 1), ROLE_REF, x0, y, cw, rh))
                self.slots.append(Slot("inf%d" % (i + 1), ROLE_INF, x0 + cw + self.gap, y, cw, rh))
            else:
                self.slots.append(Slot("any%d" % (2 * i + 1), ROLE_ANY, x0, y, cw, rh))
                self.slots.append(Slot("any%d" % (2 * i + 2), ROLE_ANY, x0 + cw + self.gap, y, cw, rh))
        self.preset = "lr"
        self.name = "Lewa / Prawa" if comparison else "Dwie kolumny"

    def apply_top_bottom(self, pairs: int = 1, comparison: bool = True) -> None:
        """REF row on top, INF row at the bottom, ``pairs`` columns."""
        pairs = max(1, int(pairs))
        x0, y0, aw, ah = self._area()
        rh = (ah - self.gap) / 2.0
        cw = (aw - self.gap * (pairs - 1)) / pairs
        self.slots = []
        for i in range(pairs):
            x = x0 + i * (cw + self.gap)
            if comparison:
                self.slots.append(Slot("ref%d" % (i + 1), ROLE_REF, x, y0, cw, rh))
                self.slots.append(Slot("inf%d" % (i + 1), ROLE_INF, x, y0 + rh + self.gap, cw, rh))
            else:
                self.slots.append(Slot("any%d" % (2 * i + 1), ROLE_ANY, x, y0, cw, rh))
                self.slots.append(Slot("any%d" % (2 * i + 2), ROLE_ANY, x, y0 + rh + self.gap, cw, rh))
        self.preset = "tb"
        self.name = "Góra / Dół" if comparison else "Dwa wiersze"

    def apply_grid(self, count: int = 1) -> None:
        """Single-model mode: 1, 2, 4 or 6 pictures per slide."""
        count = max(1, int(count))
        cols = 1 if count == 1 else (2 if count <= 4 else 3)
        rows = (count + cols - 1) // cols
        x0, y0, aw, ah = self._area()
        cw = (aw - self.gap * (cols - 1)) / cols
        rh = (ah - self.gap * (rows - 1)) / rows
        self.slots = []
        for i in range(count):
            r, c = divmod(i, cols)
            self.slots.append(Slot("any%d" % (i + 1), ROLE_ANY, x0 + c * (cw + self.gap), y0 + r * (rh + self.gap), cw, rh))
        self.preset = "grid"
        self.name = "Siatka %d" % count

    def mirror(self, axis: str = "lr") -> None:
        """Copy REF slots to INF slots mirrored across the vertical (lr) or
        horizontal (tb) centre line of the content area - instant symmetry."""
        refs = self.slots_by_role(ROLE_REF)
        if not refs:
            return
        x0, y0, aw, ah = self._area()
        new_inf: List[Slot] = []
        for i, s in enumerate(refs):
            if axis == "lr":
                nx = x0 + aw - (s.x - x0) - s.w
                ny = s.y
            else:
                nx = s.x
                ny = y0 + ah - (s.y - y0) - s.h
            slot = Slot("inf%d" % (i + 1), ROLE_INF, nx, ny, s.w, s.h, s.fit, s.caption)
            slot.clamp()
            new_inf.append(slot)
        self.slots = refs + new_inf
        self.preset = "custom"

    def swap_roles(self) -> None:
        for s in self.slots:
            if s.role == ROLE_REF:
                s.role = ROLE_INF
            elif s.role == ROLE_INF:
                s.role = ROLE_REF
        self.slots.sort(key=lambda s: (0 if s.role == ROLE_REF else 1 if s.role == ROLE_INF else 2, s.y, s.x))

    def align(self, what: str) -> None:
        """Quick alignment helpers for the editor: equalise sizes / centre rows."""
        if not self.slots:
            return
        if what == "equal_size":
            w = sum(s.w for s in self.slots) / len(self.slots)
            h = sum(s.h for s in self.slots) / len(self.slots)
            for s in self.slots:
                s.w, s.h = w, h
                s.clamp()
        self.preset = "custom"

    # ---- persistence
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "aspect": self.aspect, "slots": [s.to_dict() for s in self.slots],
            "show_title": self.show_title, "title_height": self.title_height, "margin": self.margin,
            "gap": self.gap, "caption_height": self.caption_height, "preset": self.preset,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SlideLayout":
        lay = cls(
            name=str(d.get("name", "Układ")), aspect=str(d.get("aspect", "16:9")),
            slots=[Slot.from_dict(s) for s in d.get("slots", [])], show_title=bool(d.get("show_title", True)),
            title_height=float(d.get("title_height", 0.11)), margin=float(d.get("margin", 0.035)),
            gap=float(d.get("gap", 0.025)), caption_height=float(d.get("caption_height", 0.045)),
            preset=str(d.get("preset", "custom")),
        )
        if lay.aspect not in ASPECTS:
            lay.aspect = "16:9"
        return lay

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"hm_shots_layout": 1, "layout": self.to_dict()}, fh, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "SlideLayout":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "layout" in data:
            data = data["layout"]
        return cls.from_dict(data)

    @classmethod
    def default(cls, comparison: bool = True) -> "SlideLayout":
        lay = cls()
        if comparison:
            lay.apply_left_right(1, True)
        else:
            lay.apply_grid(1)
        return lay


def layouts_dir(base: Optional[str] = None) -> str:
    d = base or os.path.join(os.path.expanduser("~"), ".hm_shots", "layouts")
    os.makedirs(d, exist_ok=True)
    return d


def fit_image(slot: Slot, img_w: Optional[int], img_h: Optional[int], caption_h: float, ratio: float) -> tuple:
    """Rectangle (normalised) where the picture is drawn inside ``slot``.

    ``ratio`` is the slide width/height ratio - needed because x and y are
    normalised independently.  The caption strip (``caption_h``) is reserved at
    the bottom of the slot when the slot shows captions.
    Returns (x, y, w, h, src_crop) where src_crop is None or (l, t, r, b)
    fractions to crop from the source (``cover`` mode).
    """
    x, y, w, h = slot.x, slot.y, slot.w, slot.h
    if slot.caption and caption_h > 0 and h > caption_h * 2:
        h -= caption_h
    if not img_w or not img_h:
        return x, y, w, h, None
    box_ratio = (w * ratio) / h          # physical aspect of the box
    img_ratio = img_w / float(img_h)
    if slot.fit == "cover":
        if img_ratio > box_ratio:        # crop left/right
            keep = box_ratio / img_ratio
            c = (1.0 - keep) / 2.0
            return x, y, w, h, (c, 0.0, c, 0.0)
        keep = img_ratio / box_ratio
        c = (1.0 - keep) / 2.0
        return x, y, w, h, (0.0, c, 0.0, c)
    if img_ratio > box_ratio:            # limited by width -> anchor to the top
        nh = (w * ratio) / img_ratio
        return x, y, w, nh, None
    nw = (h * img_ratio) / ratio         # limited by height -> centre horizontally
    return x + (w - nw) / 2.0, y, nw, h, None
