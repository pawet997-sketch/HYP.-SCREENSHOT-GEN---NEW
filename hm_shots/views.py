# -*- coding: utf-8 -*-
"""Remembered views: camera numbers, thumbnail, recorded display layout and the
per-view quality-check selection."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass
class MetricSetting:
    """One quality check attached to a view."""
    key: str
    enabled: bool = False
    threshold: Optional[float] = None   # None -> metric default
    hide_passed: bool = True            # show only the elements outside the limit

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "enabled": self.enabled, "threshold": self.threshold, "hide_passed": self.hide_passed}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MetricSetting":
        thr = d.get("threshold")
        return cls(key=str(d.get("key", "")), enabled=bool(d.get("enabled", False)),
                   threshold=None if thr is None else float(thr), hide_passed=bool(d.get("hide_passed", True)))


@dataclass
class ViewRecord:
    id: int
    name: str
    view: List[float]
    selected: bool = True
    thumb_b64: str = ""
    thumb_fmt: str = "png"
    shot_path: str = ""          # full-size frame captured at "remember" time (WYSIWYG)
    disp: str = ""               # recorded display-layout commands (command.tcl tail)
    plain: bool = True           # take the plain (no metric) screenshot
    metrics: List[MetricSetting] = field(default_factory=list)
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    # ---- metric helpers
    def metric(self, key: str) -> MetricSetting:
        for m in self.metrics:
            if m.key == key:
                return m
        m = MetricSetting(key=key)
        self.metrics.append(m)
        return m

    def has_metric(self, key: str) -> bool:
        return any(m.key == key for m in self.metrics)

    def enabled_metrics(self, order: Optional[Sequence[str]] = None) -> List[MetricSetting]:
        enabled = [m for m in self.metrics if m.enabled]
        if order:
            rank = {k: i for i, k in enumerate(order)}
            enabled.sort(key=lambda m: rank.get(m.key, 10_000))
        return enabled

    def shot_kinds(self, order: Optional[Sequence[str]] = None) -> List[str]:
        """Ordered list of screenshot kinds: 'plain' and/or metric keys."""
        kinds: List[str] = ["plain"] if self.plain else []
        kinds += [m.key for m in self.enabled_metrics(order)]
        return kinds

    @property
    def view_text(self) -> str:
        return "VS: " + " ".join(_fmt(v) for v in self.view)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "view": list(self.view), "selected": self.selected,
            "thumb_b64": self.thumb_b64, "thumb_fmt": self.thumb_fmt, "shot_path": self.shot_path,
            "disp": self.disp, "plain": self.plain, "metrics": [m.to_dict() for m in self.metrics],
            "created": self.created,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ViewRecord":
        return cls(
            id=int(d.get("id", 0)), name=str(d.get("name", "")), view=[float(v) for v in d.get("view", [])],
            selected=bool(d.get("selected", True)), thumb_b64=str(d.get("thumb_b64", "")),
            thumb_fmt=str(d.get("thumb_fmt", "png")), shot_path=str(d.get("shot_path", "")),
            disp=str(d.get("disp", "")), plain=bool(d.get("plain", True)),
            metrics=[MetricSetting.from_dict(m) for m in d.get("metrics", [])],
            created=str(d.get("created", "")),
        )


def _fmt(v: float) -> str:
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


class ViewStore:
    """Ordered collection of ViewRecord with stable ids."""

    def __init__(self) -> None:
        self.views: List[ViewRecord] = []
        self.next_id = 1

    def __len__(self) -> int:
        return len(self.views)

    def __iter__(self):
        return iter(self.views)

    def add(self, view: Sequence[float], name: str = "", **kw: Any) -> ViewRecord:
        rec = ViewRecord(id=self.next_id, name=name or "", view=[float(v) for v in view], **kw)
        if not rec.name:
            rec.name = "Widok %d" % rec.id
        self.next_id += 1
        self.views.append(rec)
        return rec

    def get(self, view_id: int) -> Optional[ViewRecord]:
        for v in self.views:
            if v.id == view_id:
                return v
        return None

    def index(self, view_id: int) -> int:
        for i, v in enumerate(self.views):
            if v.id == view_id:
                return i
        return -1

    def remove(self, view_id: int) -> Optional[ViewRecord]:
        i = self.index(view_id)
        return self.views.pop(i) if i >= 0 else None

    def move(self, view_id: int, delta: int) -> bool:
        i = self.index(view_id)
        j = i + delta
        if i < 0 or j < 0 or j >= len(self.views):
            return False
        self.views[i], self.views[j] = self.views[j], self.views[i]
        return True

    def duplicate(self, view_id: int) -> Optional[ViewRecord]:
        src = self.get(view_id)
        if src is None:
            return None
        d = src.to_dict()
        d["id"] = self.next_id
        d["name"] = src.name + " (kopia)"
        self.next_id += 1
        rec = ViewRecord.from_dict(d)
        self.views.insert(self.index(view_id) + 1, rec)
        return rec

    def clear(self) -> None:
        self.views = []

    def selected(self) -> List[ViewRecord]:
        return [v for v in self.views if v.selected]

    def set_all_selected(self, flag: bool) -> None:
        for v in self.views:
            v.selected = flag

    def names(self) -> List[str]:
        return [v.name for v in self.views]

    def to_dict(self) -> Dict[str, Any]:
        return {"next_id": self.next_id, "views": [v.to_dict() for v in self.views]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ViewStore":
        store = cls()
        store.views = [ViewRecord.from_dict(v) for v in d.get("views", [])]
        store.next_id = max([int(d.get("next_id", 1))] + [v.id + 1 for v in store.views])
        return store

    def extend_from(self, other: Iterable[ViewRecord]) -> None:
        for v in other:
            d = v.to_dict()
            d["id"] = self.next_id
            self.next_id += 1
            self.views.append(ViewRecord.from_dict(d))
