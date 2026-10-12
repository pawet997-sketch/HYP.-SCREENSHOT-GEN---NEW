# -*- coding: utf-8 -*-
"""
Quality-check metrics (Aspect Ratio, Jacobian, Skewness, ...).

Each metric is driven by a *recipe*: a list of HyperMesh Tcl commands with a
``{thr}`` placeholder for the limit value.  The native ``*elementtest*``
commands of the Check Elements panel are used, so HyperMesh draws its own
highlighting / legend.  Because command signatures differ between HyperMesh
releases the recipes are editable in the GUI and can be *learned* from the
command file: perform the check once by hand, the tool records the commands
and turns the typed limit into ``{thr}``.

Recipe sections
---------------
recipe       - run the check (highlights / colours failing elements)
hide_passed  - optional extra commands that leave only the failing elements
               on screen (elements outside the limit)
cleanup      - restore the display after the screenshot
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .i18n import tr

_NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")

PRELUDE = ['*createmark elements 1 "displayed"']
HIDE_PASSED = [
    '*createmark elements 1 "displayed"',
    "*markdifference elements 1 elements 2",
    "*maskentitymark elements 1 1",
]
CLEANUP = [
    "*clearmark elements 1",
    "*clearmark elements 2",
    "*unmaskall",
]
NOISE = ("*viewset", "*jpegfilenamed", "*pngfilenamed", "*bmpfilenamed", "*tifffilenamed",
         "*setbackground", "*sethardcopy", "*hardcopy", "*screencapture", "*quitapplication",
         "hm_redraw", "*clearmark", "*unmaskall")


@dataclass
class Metric:
    key: str
    label: str                 # folder / file prefix (ASCII)
    name_pl: str
    name_en: str
    default_threshold: float
    fail_when: str             # 'above' | 'below'
    recipe: List[str]
    hide_passed: List[str] = field(default_factory=lambda: list(HIDE_PASSED))
    cleanup: List[str] = field(default_factory=lambda: list(CLEANUP))
    decimals: int = 2
    step: float = 0.1
    builtin: bool = True

    @property
    def name(self) -> str:
        return tr(self.name_pl, self.name_en)

    @property
    def symbol(self) -> str:
        return ">" if self.fail_when == "above" else "<"

    def describe_limit(self, thr: float) -> str:
        return "%s %s" % (self.symbol, _fmt(thr, self.decimals))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key, "label": self.label, "name_pl": self.name_pl, "name_en": self.name_en,
            "default_threshold": self.default_threshold, "fail_when": self.fail_when,
            "recipe": list(self.recipe), "hide_passed": list(self.hide_passed), "cleanup": list(self.cleanup),
            "decimals": self.decimals, "step": self.step, "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Metric":
        return cls(
            key=str(d["key"]), label=str(d.get("label", d["key"])), name_pl=str(d.get("name_pl", d["key"])),
            name_en=str(d.get("name_en", d["key"])), default_threshold=float(d.get("default_threshold", 1.0)),
            fail_when=str(d.get("fail_when", "above")), recipe=list(d.get("recipe", [])),
            hide_passed=list(d.get("hide_passed", HIDE_PASSED)), cleanup=list(d.get("cleanup", CLEANUP)),
            decimals=int(d.get("decimals", 2)), step=float(d.get("step", 0.1)), builtin=bool(d.get("builtin", False)),
        )


def _fmt(v: float, decimals: int = 2) -> str:
    s = ("%." + str(decimals) + "f") % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def _test(cmd: str) -> List[str]:
    return PRELUDE + ["*%s elements 1 {thr} 2 2 0 0 0 0 0" % cmd]


BUILTIN_METRICS: List[Metric] = [
    Metric("aspect", "Aspect_Ratio", "Aspect Ratio", "Aspect ratio", 5.0, "above", _test("elementtestaspect")),
    Metric("jacobian", "Jacobian", "Jacobian", "Jacobian", 0.7, "below", _test("elementtestjacobian")),
    Metric("skew", "Skewness", "Skewness (skośność)", "Skewness", 60.0, "above", _test("elementtestskew"), step=1.0, decimals=1),
    Metric("warpage", "Warpage", "Warpage (wypaczenie)", "Warpage", 15.0, "above", _test("elementtestwarpage"), step=1.0, decimals=1),
    Metric("min_length", "Min_Length", "Min. długość boku", "Min. edge length", 1.0, "below", _test("elementtestlength")),
    Metric("min_angle_quad", "Quad_Min_Angle", "Quad – min. kąt", "Quad – min. angle", 45.0, "below", _test("elementtestquad"), step=1.0, decimals=1),
    Metric("min_angle_tria", "Tria_Min_Angle", "Tria – min. kąt", "Tria – min. angle", 20.0, "below", _test("elementtesttria"), step=1.0, decimals=1),
    Metric("chordal", "Chordal_Dev", "Odchyłka cięciwy", "Chordal deviation", 0.1, "above", _test("elementtestchordaldeviation"), decimals=3, step=0.01),
    Metric("tet_collapse", "Tet_Collapse", "Tet collapse", "Tet collapse", 0.1, "below", _test("elementtesttetcollapse"), step=0.01),
]
DEFAULT_ACTIVE = ["aspect", "jacobian", "skew"]


class MetricRegistry:
    """All known metrics + which ones are shown on the view tiles."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Metric] = {}
        for m in BUILTIN_METRICS:
            self.metrics[m.key] = copy.deepcopy(m)
        self.active: List[str] = list(DEFAULT_ACTIVE)

    # ---- access
    def get(self, key: str) -> Optional[Metric]:
        return self.metrics.get(key)

    def keys(self) -> List[str]:
        return list(self.metrics.keys())

    def all(self) -> List[Metric]:
        return list(self.metrics.values())

    def active_metrics(self) -> List[Metric]:
        return [self.metrics[k] for k in self.active if k in self.metrics]

    def label(self, key: str) -> str:
        m = self.get(key)
        return m.label if m else key

    def threshold_for(self, key: str, override: Optional[float]) -> float:
        m = self.get(key)
        if override is not None:
            return float(override)
        return m.default_threshold if m else 0.0

    def set_active(self, keys: Iterable[str]) -> None:
        self.active = [k for k in keys if k in self.metrics]

    def add_custom(self, key: str, label: str, name: str, threshold: float, fail_when: str = "above",
                   recipe: Optional[List[str]] = None) -> Metric:
        key = re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_") or "custom"
        base = key
        n = 2
        while key in self.metrics:
            key = "%s_%d" % (base, n)
            n += 1
        m = Metric(key, label or key, name or key, name or key, threshold, fail_when,
                   list(recipe or PRELUDE), builtin=False)
        self.metrics[key] = m
        return m

    def remove(self, key: str) -> bool:
        m = self.metrics.get(key)
        if m is None or m.builtin:
            return False
        del self.metrics[key]
        self.active = [k for k in self.active if k != key]
        return True

    def reset(self, key: str) -> None:
        for m in BUILTIN_METRICS:
            if m.key == key:
                self.metrics[key] = copy.deepcopy(m)

    # ---- recipe rendering
    @staticmethod
    def render(lines: Iterable[str], thr: float, decimals: int = 6) -> List[str]:
        out: List[str] = []
        txt = ("%." + str(decimals) + "f") % thr
        txt = txt.rstrip("0").rstrip(".") if "." in txt else txt
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line.replace("{thr}", txt))
        return out

    def commands_for(self, key: str, thr: float, hide_passed: bool) -> List[str]:
        m = self.get(key)
        if m is None:
            return []
        cmds = self.render(m.recipe, thr, m.decimals + 4)
        if hide_passed and m.hide_passed:
            cmds += self.render(m.hide_passed, thr, m.decimals + 4)
        return cmds

    def cleanup_for(self, key: str) -> List[str]:
        m = self.get(key)
        return list(m.cleanup) if m else list(CLEANUP)

    # ---- learning from the HyperMesh command file
    @staticmethod
    def learn_recipe(lines: Iterable[str], threshold_used: Optional[float]) -> List[str]:
        """Turn recorded command-file lines into a template.

        Lines unrelated to element checks (camera, captures) are dropped and
        every number equal to ``threshold_used`` becomes ``{thr}``.
        """
        out: List[str] = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if any(line.startswith(n) for n in NOISE):
                continue
            if threshold_used is not None:
                def repl(m: "re.Match[str]") -> str:
                    try:
                        if abs(float(m.group(0)) - float(threshold_used)) < 1e-6:
                            return "{thr}"
                    except ValueError:
                        pass
                    return m.group(0)
                line = _NUM.sub(repl, line)
            out.append(line)
        return out

    # ---- persistence
    def to_dict(self) -> Dict[str, Any]:
        return {"active": list(self.active), "metrics": [m.to_dict() for m in self.metrics.values()]}

    def load_dict(self, d: Dict[str, Any]) -> None:
        if not d:
            return
        for md in d.get("metrics", []):
            try:
                m = Metric.from_dict(md)
            except (KeyError, ValueError, TypeError):
                continue
            if m.key in self.metrics and self.metrics[m.key].builtin:
                m.builtin = True
            self.metrics[m.key] = m
        if d.get("active"):
            self.set_active(d["active"])
