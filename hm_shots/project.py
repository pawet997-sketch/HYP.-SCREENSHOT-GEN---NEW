# -*- coding: utf-8 -*-
"""
Project / session: settings, remembered views, metric registry, slide layout
and the list of generated screenshots.  Everything is saved in one JSON file
(thumbnails embedded) so a REF session can be reopened later for the INF
phase on another model - or another day.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import naming
from .i18n import tr
from .layout import ROLE_ANY, ROLE_INF, ROLE_REF, SlideLayout, Slot
from .pptx_writer import DeckSpec, PictureSpec, PlaceholderSpec, SlideSpec
from .quality import MetricRegistry
from .views import ViewRecord, ViewStore

PHASES = (ROLE_REF, ROLE_INF)
PROJECT_VERSION = 1


@dataclass
class Settings:
    out_dir: str = ""
    use_model_dir: bool = False
    fmt: str = "jpg"                      # jpg | png | bmp
    overwrite: bool = True
    pattern_metric: str = naming.DEFAULT_PATTERN_METRIC
    pattern_plain: str = naming.DEFAULT_PATTERN_PLAIN
    comparison: bool = True               # REF vs INF mode
    phase: str = ROLE_REF
    tag_ref: str = "REF"
    tag_inf: str = "INF"
    background: str = ""                  # '' = leave, else '#rrggbb'
    high_quality: bool = True
    use_stored_frames: bool = False       # export the frame captured at "remember" for plain shots
    replay_disp: bool = True              # replay recorded display-layout commands before a shot
    settle_ms: int = 250
    pptx_path: str = ""
    pptx_auto: bool = True
    pptx_title: str = "Raport jakości siatki"
    pptx_title_slide: bool = True
    pptx_slide_titles: bool = True
    pptx_captions: bool = True
    lang: str = "pl"
    theme: str = "light"
    command_file: str = ""                # override of the HyperMesh command file

    def phase_tag(self, phase: str) -> str:
        if not self.comparison or not phase:
            return ""
        return self.tag_ref if phase == ROLE_REF else self.tag_inf

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Settings":
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k) and v is not None:
                try:
                    setattr(s, k, type(getattr(s, k))(v))
                except (TypeError, ValueError):
                    pass
        if s.phase not in PHASES:
            s.phase = ROLE_REF
        return s


@dataclass
class ShotOutput:
    view_id: int
    view_name: str
    kind: str                 # 'plain' or metric key
    metric_label: str
    threshold: Optional[float]
    phase: str                # 'REF' / 'INF' / '' (single mode)
    path: str
    ok: bool = True
    error: str = ""
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def key(self) -> Tuple[int, str, str]:
        return (self.view_id, self.kind, self.phase)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ShotOutput":
        thr = d.get("threshold")
        return cls(view_id=int(d.get("view_id", 0)), view_name=str(d.get("view_name", "")), kind=str(d.get("kind", "plain")),
                   metric_label=str(d.get("metric_label", "")), threshold=None if thr is None else float(thr),
                   phase=str(d.get("phase", "")), path=str(d.get("path", "")), ok=bool(d.get("ok", True)),
                   error=str(d.get("error", "")), ts=str(d.get("ts", "")))


@dataclass
class ShotJob:
    """One screenshot to take."""
    view: ViewRecord
    kind: str
    metric_label: str
    metric_name: str
    threshold: Optional[float]
    hide_passed: bool
    phase: str

    @property
    def is_metric(self) -> bool:
        return self.kind != "plain"

    def label(self, registry: MetricRegistry) -> str:
        if not self.is_metric:
            return self.view.name
        m = registry.get(self.kind)
        lim = m.describe_limit(self.threshold) if (m and self.threshold is not None) else ""
        return "%s – %s %s" % (self.view.name, self.metric_name, lim)


@dataclass
class Placement:
    slot: Slot
    role: str
    image: str
    caption: str
    placeholder: str
    key: Tuple[int, str]


@dataclass
class SlidePlan:
    index: int
    title: str
    subtitle: str
    placements: List[Placement]


class Project:
    def __init__(self) -> None:
        self.settings = Settings()
        self.views = ViewStore()
        self.metrics = MetricRegistry()
        self.layout = SlideLayout.default(True)
        self.outputs: List[ShotOutput] = []
        self.model_files: Dict[str, str] = {ROLE_REF: "", ROLE_INF: ""}
        self.path = ""
        self.dirty = False

    # ----------------------------------------------------------- outputs
    def record_output(self, out: ShotOutput) -> None:
        self.outputs = [o for o in self.outputs if o.key != out.key]
        self.outputs.append(out)
        self.dirty = True

    def output_for(self, view_id: int, kind: str, phase: str) -> Optional[ShotOutput]:
        for o in self.outputs:
            if o.key == (view_id, kind, phase) and o.ok:
                return o
        return None

    def outputs_for_phase(self, phase: str) -> List[ShotOutput]:
        return [o for o in self.outputs if o.phase == phase]

    def forget_outputs(self, phase: Optional[str] = None) -> None:
        self.outputs = [o for o in self.outputs if phase is not None and o.phase != phase]
        self.dirty = True

    # --------------------------------------------------------------- jobs
    def current_phase(self) -> str:
        return self.settings.phase if self.settings.comparison else ""

    def shot_jobs(self, views: Optional[List[ViewRecord]] = None, phase: Optional[str] = None) -> List[ShotJob]:
        phase = self.current_phase() if phase is None else phase
        jobs: List[ShotJob] = []
        order = self.metrics.keys()
        for v in (views if views is not None else self.views.selected()):
            for kind in v.shot_kinds(order):
                if kind == "plain":
                    jobs.append(ShotJob(v, "plain", "", "", None, False, phase))
                    continue
                m = self.metrics.get(kind)
                if m is None:
                    continue
                ms = v.metric(kind)
                jobs.append(ShotJob(v, kind, m.label, m.name, self.metrics.threshold_for(kind, ms.threshold),
                                    ms.hide_passed, phase))
        return jobs

    def job_folder(self, job: ShotJob) -> str:
        return naming.folder_name(job.view.name, job.metric_label if job.is_metric else None)

    def job_basename(self, job: ShotJob) -> str:
        s = self.settings
        tag = s.phase_tag(job.phase)
        if job.is_metric:
            return naming.shot_basename(s.pattern_metric, job.view.name, job.metric_label, tag)
        return naming.shot_basename(s.pattern_plain, job.view.name, "", tag)

    # ----------------------------------------------------------- the deck
    def _keys(self) -> List[Tuple[ViewRecord, str]]:
        keys: List[Tuple[ViewRecord, str]] = []
        order = self.metrics.keys()
        for v in self.views.selected():
            for kind in v.shot_kinds(order):
                keys.append((v, kind))
        return keys

    def _key_label(self, v: ViewRecord, kind: str) -> str:
        if kind == "plain":
            return v.name
        m = self.metrics.get(kind)
        if m is None:
            return "%s – %s" % (v.name, kind)
        thr = self.metrics.threshold_for(kind, v.metric(kind).threshold)
        return "%s – %s %s" % (v.name, m.name, m.describe_limit(thr))

    def deck_plan(self) -> List[SlidePlan]:
        """Assign every (view, kind) to slide slots according to the layout."""
        s = self.settings
        lay = self.layout
        keys = self._keys()
        slides: List[SlidePlan] = []
        if s.comparison and lay.comparison:
            refs = lay.slots_by_role(ROLE_REF)
            infs = lay.slots_by_role(ROLE_INF)
            pairs = max(1, min(len(refs), len(infs))) if (refs and infs) else max(1, len(refs or infs))
            groups: Dict[int, List[Tuple[int, ViewRecord, str]]] = {}
            for idx, (v, kind) in enumerate(keys):
                groups.setdefault(idx // pairs, []).append((idx % pairs, v, kind))
            for si in sorted(groups):
                placements: List[Placement] = []
                labels: List[str] = []
                for j, v, kind in groups[si]:
                    label = self._key_label(v, kind)
                    labels.append(label)
                    multi = pairs > 1
                    for role, slots in ((ROLE_REF, refs), (ROLE_INF, infs)):
                        if j >= len(slots):
                            continue
                        out = self.output_for(v.id, kind, role)
                        tag = s.phase_tag(role)
                        cap = ("%s · %s" % (tag, label)) if multi else tag
                        placements.append(Placement(slots[j], role, out.path if out else "", cap,
                                                    "%s\n%s" % (tag, label), (v.id, kind)))
                title = labels[0] if len(labels) == 1 else tr("Porównanie %s / %s", "Comparison %s / %s") % (s.tag_ref, s.tag_inf)
                subtitle = "" if len(labels) == 1 else " | ".join(labels)
                slides.append(SlidePlan(len(slides), title, subtitle, placements))
            return slides
        slots = lay.slots or [Slot("any1", ROLE_ANY, lay.margin, lay.content_top(), 1 - 2 * lay.margin, 1 - lay.content_top() - lay.margin)]
        n = len(slots)
        phase = self.current_phase()
        for si in range((len(keys) + n - 1) // n):
            chunk = keys[si * n:(si + 1) * n]
            placements = []
            labels = []
            for j, (v, kind) in enumerate(chunk):
                label = self._key_label(v, kind)
                labels.append(label)
                out = self.output_for(v.id, kind, phase)
                placements.append(Placement(slots[j], slots[j].role, out.path if out else "", label if n > 1 else "",
                                            label, (v.id, kind)))
            title = labels[0] if len(labels) == 1 else tr("Widoki", "Views")
            subtitle = "" if len(labels) == 1 else " | ".join(labels)
            slides.append(SlidePlan(si, title, subtitle, placements))
        return slides

    def deck_spec(self) -> DeckSpec:
        s = self.settings
        lay = self.layout
        slides: List[SlideSpec] = []
        for plan in self.deck_plan():
            spec = SlideSpec(title=plan.title if s.pptx_slide_titles else "", subtitle=plan.subtitle if s.pptx_slide_titles else "")
            for p in plan.placements:
                if p.image:
                    spec.pictures.append(PictureSpec(p.image, p.slot, p.caption, p.role))
                else:
                    spec.placeholders.append(PlaceholderSpec(p.slot, p.placeholder, p.role))
            slides.append(spec)
        lines = [time.strftime("%Y-%m-%d")]
        for ph in PHASES:
            if self.model_files.get(ph):
                lines.append("%s: %s" % (s.phase_tag(ph) or ph, os.path.basename(self.model_files[ph])))
        return DeckSpec(slides=slides, aspect=lay.aspect, show_title=lay.show_title and s.pptx_slide_titles,
                        title_height=lay.title_height, margin=lay.margin, caption_height=lay.caption_height,
                        deck_title=s.pptx_title if s.pptx_title_slide else "", title_slide_lines=lines,
                        show_captions=s.pptx_captions)

    def default_pptx_path(self) -> str:
        base = self.settings.out_dir or os.getcwd()
        return os.path.join(base, "raport_siatki.pptx")

    # -------------------------------------------------------- persistence
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hm_shots_project": PROJECT_VERSION,
            "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
            "settings": self.settings.to_dict(),
            "views": self.views.to_dict(),
            "metrics": self.metrics.to_dict(),
            "layout": self.layout.to_dict(),
            "outputs": [o.to_dict() for o in self.outputs],
            "model_files": dict(self.model_files),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Project":
        p = cls()
        p.settings = Settings.from_dict(d.get("settings", {}))
        p.views = ViewStore.from_dict(d.get("views", {}))
        p.metrics.load_dict(d.get("metrics", {}))
        if d.get("layout"):
            p.layout = SlideLayout.from_dict(d["layout"])
        p.outputs = [ShotOutput.from_dict(o) for o in d.get("outputs", [])]
        p.model_files.update({k: str(v) for k, v in (d.get("model_files") or {}).items() if k in PHASES})
        return p

    def save_copy(self, path: str) -> None:
        """Write the project to ``path`` without making it the session file."""
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def save(self, path: str) -> None:
        self.save_copy(path)
        self.path = path
        self.dirty = False

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "hm_shots_project" not in data:
            raise ValueError("not an HM Shots project file")
        p = cls.from_dict(data)
        p.path = path
        return p


def user_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".hm_shots")
    os.makedirs(d, exist_ok=True)
    return d


def autosave_path() -> str:
    return os.path.join(user_dir(), "autosave.hmshots.json")
