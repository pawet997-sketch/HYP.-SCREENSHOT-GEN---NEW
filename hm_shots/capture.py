# -*- coding: utf-8 -*-
"""
Screenshot generation pipeline.

For every selected view and every screenshot kind chosen on its tile
(plain / Aspect Ratio / Jacobian / ...):

1. replay the recorded display layout of the view (optional),
2. run the quality-check recipe with the view's limit (metric shots),
3. restore the camera, redraw, let the graphics settle,
4. capture the graphics window into ``<out>/<Metric or View>/<name>.<fmt>``,
5. run the metric cleanup recipe,
6. record the file in the project so the PPTX deck can pick it up.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

from . import imaging, naming
from .hm_bridge import HMBridge, temp_dir
from .i18n import tr
from .project import Project, ShotJob, ShotOutput
from .views import ViewRecord

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int, str], None]


@dataclass
class GenerateResult:
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    out_dir: str = ""
    folders: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pptx: str = ""
    recipe_failures: int = 0
    disp_failures: int = 0

    def summary(self) -> str:
        parts = [tr("Zapisano %d zrzutów", "Saved %d screenshots") % self.ok]
        if self.failed:
            parts.append(tr("nieudanych: %d", "failed: %d") % self.failed)
        if self.skipped:
            parts.append(tr("pominiętych: %d", "skipped: %d") % self.skipped)
        if self.recipe_failures:
            parts.append(tr("komend metryk z błędem: %d", "metric commands failed: %d") % self.recipe_failures)
        if self.disp_failures:
            parts.append(tr("komend układu z błędem: %d", "layout commands failed: %d") % self.disp_failures)
        if self.pptx:
            parts.append(tr("prezentacja: %s", "presentation: %s") % os.path.basename(self.pptx))
        return ", ".join(parts) + (" → %s" % self.out_dir if self.out_dir else "")


class CommandRecorder:
    """Reads the *new* tail of the HyperMesh command file (command.tcl)."""

    def __init__(self, bridge: HMBridge, override: str = "") -> None:
        self.bridge = bridge
        self.override = override
        self.path = ""
        self.offset = 0
        self.active = False

    def locate(self) -> str:
        if self.override and os.path.isfile(self.override):
            self.path = self.override
        else:
            self.path = self.bridge.command_file()
        return self.path

    def start(self) -> bool:
        if not self.locate():
            self.active = False
            return False
        try:
            self.offset = os.path.getsize(self.path)
        except OSError:
            self.offset = 0
        self.active = True
        return True

    def tail(self) -> List[str]:
        """New lines since start()/last tail(); advances the offset."""
        if not self.path or not os.path.isfile(self.path):
            return []
        try:
            size = os.path.getsize(self.path)
            if size <= self.offset:
                return []
            with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self.offset)
                data = fh.read()
            self.offset = size
        except OSError:
            return []
        return [ln.rstrip("\r") for ln in data.split("\n") if ln.strip()]

    def stop(self) -> List[str]:
        lines = self.tail()
        self.active = False
        return lines


NOISE_PREFIXES = ("*viewset", "*jpegfilenamed", "*pngfilenamed", "*bmpfilenamed", "*tifffilenamed",
                  "*setbackground", "*sethardcopy", "*hardcopy", "*screencapture", "*quitapplication")


def filter_display_commands(lines: List[str]) -> str:
    keep = [ln for ln in lines if ln.strip() and not any(ln.strip().startswith(p) for p in NOISE_PREFIXES)]
    return "\n".join(keep)


class Generator:
    def __init__(self, project: Project, bridge: HMBridge, log: Optional[LogFn] = None,
                 progress: Optional[ProgressFn] = None, pump: Optional[Callable[[], None]] = None) -> None:
        self.project = project
        self.bridge = bridge
        self._log = log or (lambda m: None)
        self._progress = progress or (lambda i, n, m: None)
        self._pump = pump or (lambda: None)
        self.recorder = CommandRecorder(bridge, project.settings.command_file)
        self.disp_replayed: Set[int] = set()     # view ids whose layout ran in this HM session
        self.cancel = False

    # ------------------------------------------------------------ helpers
    def log(self, msg: str) -> None:
        self._log(msg)

    def _settle(self) -> None:
        self.bridge.redraw()
        self._pump()
        ms = max(0, int(self.project.settings.settle_ms))
        if ms:
            t0 = time.time()
            while (time.time() - t0) * 1000 < ms:
                self._pump()
                time.sleep(0.02)

    def frames_dir(self) -> str:
        d = os.path.join(temp_dir(), "frames")
        os.makedirs(d, exist_ok=True)
        return d

    # ------------------------------------------------------- remembering
    def remember_view(self, name: str = "") -> Optional[ViewRecord]:
        nums = self.bridge.get_view()
        if not nums:
            self.log(tr("Nie udało się pobrać widoku (hm_winfo viewmatrix). Czy okno graficzne jest aktywne?",
                        "Could not read the view (hm_winfo viewmatrix). Is the graphics window active?"))
            return None
        disp = ""
        if self.recorder.active:
            disp = filter_display_commands(self.recorder.tail())
        rec = self.project.views.add(nums, name=name, disp=disp)
        if disp:
            self.disp_replayed.add(rec.id)       # the user just performed it on screen
        self.capture_thumbnail(rec)
        self.project.dirty = True
        return rec

    def capture_thumbnail(self, rec: ViewRecord) -> bool:
        fmt = self.project.settings.fmt
        path = os.path.join(self.frames_dir(), "frame_%d_%d.%s" % (rec.id, int(time.time() * 1000), fmt))
        got = self.bridge.capture(path, fmt)
        if not got:
            self.log(tr("Miniatura: zrzut nie powiódł się (%s)", "Thumbnail: capture failed (%s)") % self.bridge.last_error)
            return False
        b64, tfmt = imaging.make_thumbnail(got)
        if b64:
            rec.thumb_b64, rec.thumb_fmt = b64, tfmt
        old = rec.shot_path
        rec.shot_path = got
        if old and old != got and os.path.isfile(old):
            try:
                os.remove(old)
            except OSError:
                pass
        return bool(b64)

    def refresh_thumbnail(self, rec: ViewRecord) -> bool:
        if not self.apply_view(rec):
            return False
        self._settle()
        return self.capture_thumbnail(rec)

    def apply_view(self, rec: ViewRecord, replay_disp: Optional[bool] = None) -> bool:
        replay = self.project.settings.replay_disp if replay_disp is None else replay_disp
        if replay and rec.disp and rec.id not in self.disp_replayed:
            ok, failed, errors = self.bridge.run_lines(rec.disp)
            self.disp_replayed.add(rec.id)
            if failed:
                self.log(tr("Układ widoku „%s”: %d komend nie wykonało się", "Layout of view “%s”: %d commands failed") % (rec.name, failed))
        ok = self.bridge.set_view(rec.view)
        self.bridge.redraw()
        if ok:
            self.bridge.set_view(rec.view)   # repeat after redraw (some builds reset it)
        return ok

    # ----------------------------------------------------------- output
    def resolve_out_dir(self) -> str:
        s = self.project.settings
        if s.use_model_dir:
            md = self.bridge.model_dir()
            if md:
                return md
            self.log(tr("Nie wykryto folderu modelu – używam wskazanego folderu.", "Model folder not detected – using the chosen folder."))
        return s.out_dir.strip()

    # ---------------------------------------------------------- generate
    def run(self, views: Optional[List[ViewRecord]] = None) -> GenerateResult:
        p = self.project
        s = p.settings
        res = GenerateResult()
        jobs = p.shot_jobs(views)
        if not jobs:
            res.errors.append(tr("Brak zaznaczonych widoków / rodzajów zrzutów.", "No selected views / screenshot kinds."))
            return res
        out_dir = self.resolve_out_dir()
        if not out_dir:
            res.errors.append(tr("Wskaż folder zrzutów.", "Choose the screenshot folder."))
            return res
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            res.errors.append(tr("Nie można utworzyć folderu: %s", "Cannot create folder: %s") % exc)
            return res
        res.out_dir = out_dir
        if not self.bridge.available:
            res.errors.append(tr("Brak połączenia z HyperMesh (tryb offline) – zrzuty niemożliwe.",
                                 "HyperMesh not connected (offline mode) – screenshots impossible."))
            return res
        phase = p.current_phase()
        if phase:
            p.model_files[phase] = self.bridge.model_file() or p.model_files.get(phase, "")
        if s.high_quality:
            self.bridge.apply_quality()
        if s.background:
            self.bridge.set_background(s.background)
        n = len(jobs)
        self.cancel = False
        for i, job in enumerate(jobs):
            if self.cancel:
                res.skipped += n - i
                break
            label = job.label(p.metrics)
            self._progress(i, n, label)
            folder = os.path.join(out_dir, p.job_folder(job))
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError as exc:
                res.failed += 1
                res.errors.append("%s: %s" % (label, exc))
                continue
            if folder not in res.folders:
                res.folders.append(folder)
            target = naming.unique_path(folder, p.job_basename(job), s.fmt, s.overwrite)
            got = self._take(job, target, res)
            out = ShotOutput(job.view.id, job.view.name, job.kind, job.metric_label, job.threshold, job.phase,
                             got or target, ok=bool(got), error="" if got else self.bridge.last_error)
            p.record_output(out)
            if got:
                res.ok += 1
                res.files.append(got)
                self.log(tr("✔ %s → %s", "✔ %s → %s") % (label, os.path.relpath(got, out_dir)))
            else:
                res.failed += 1
                res.errors.append("%s: %s" % (label, self.bridge.last_error))
                self.log(tr("✖ %s: %s", "✖ %s: %s") % (label, self.bridge.last_error))
        self._progress(n, n, "")
        if s.pptx_auto:
            try:
                res.pptx = self.write_pptx()
            except Exception as exc:  # noqa: BLE001
                res.errors.append(tr("PPTX: %s", "PPTX: %s") % exc)
        p.dirty = True
        return res

    def _take(self, job: ShotJob, target: str, res: GenerateResult) -> Optional[str]:
        p = self.project
        s = p.settings
        v = job.view
        # WYSIWYG: reuse the frame stored at "remember view" for plain shots
        if not job.is_metric and s.use_stored_frames and v.shot_path and os.path.isfile(v.shot_path):
            try:
                dst = os.path.splitext(target)[0] + os.path.splitext(v.shot_path)[1]
                shutil.copyfile(v.shot_path, dst)
                return dst
            except OSError as exc:
                self.log(tr("Klatka zapisana niedostępna (%s) – renderuję na nowo.", "Stored frame unusable (%s) – re-rendering.") % exc)
        if job.is_metric:
            cmds = p.metrics.commands_for(job.kind, job.threshold or 0.0, job.hide_passed)
            ok, failed, errors = self.bridge.run_lines("\n".join(cmds))
            if failed:
                res.recipe_failures += failed
                for e in errors[:3]:
                    self.log("   " + e)
        try:
            if not self.apply_view(v):
                self.log(tr("Nie udało się ustawić widoku „%s”.", "Could not apply view “%s”.") % v.name)
            self._settle()
            got = self.bridge.capture(target, s.fmt)
        finally:
            if job.is_metric:
                ok, failed, errors = self.bridge.run_lines("\n".join(p.metrics.cleanup_for(job.kind)))
                self.bridge.redraw()
        return got

    # --------------------------------------------------------------- pptx
    def write_pptx(self, path: str = "") -> str:
        from .pptx_writer import write_pptx
        p = self.project
        path = path or p.settings.pptx_path or p.default_pptx_path()
        p.settings.pptx_path = path
        write_pptx(path, p.deck_spec())
        self.log(tr("Prezentacja zapisana: %s", "Presentation saved: %s") % path)
        return path
