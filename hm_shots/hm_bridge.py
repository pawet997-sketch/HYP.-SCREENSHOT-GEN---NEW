# -*- coding: utf-8 -*-
"""
Adapter between the tool and HyperMesh.

HyperMesh (HyperWorks 2021+) embeds a Python interpreter that exposes the
``hm`` module (``hm.Model`` wraps the ``*command`` set) and - inside
HyperWorks Desktop - the ``hw`` module with ``hw.evalTcl``.  Different
releases expose slightly different entry points, so the bridge probes a list
of candidates once, remembers what works and falls back gracefully.

Everything the tool needs from HyperMesh goes through this class:

* ``tcl(cmd)``         - evaluate a Tcl command string in HyperMesh
* ``get_view()``       - camera as the 20 numbers used by ``*viewset``
* ``set_view(nums)``   - restore a camera
* ``capture(path)``    - screenshot of the graphics window to a file
* ``redraw()``, ``model_file()``, ``command_file()``, ``run_lines()``

When HyperMesh is not present (the script is started with a plain Python
interpreter) the bridge runs in *offline* mode: the GUI, the slide layout
editor and the PPTX export still work, only view capture is unavailable.
``DemoBridge`` simulates captures with synthetic images so the complete
workflow can be exercised without HyperMesh.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import imginfo

_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


class HMError(RuntimeError):
    """Raised when a HyperMesh operation is impossible in the current mode."""


def parse_numbers(text: Any) -> List[float]:
    """Extract all floats from an arbitrary string / sequence."""
    if text is None:
        return []
    if isinstance(text, (list, tuple)):
        out: List[float] = []
        for item in text:
            out.extend(parse_numbers(item))
        return out
    try:
        return [float(m) for m in _NUM_RE.findall(str(text))]
    except ValueError:
        return []


def tcl_quote(value: Any) -> str:
    """Format a Python value as a single Tcl word."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    s = str(value)
    if s == "":
        return "{}"
    if re.search(r"[\s{}\[\]$\"\;]", s):
        s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        return "{" + s + "}"
    return s


def _try_import(name: str):
    try:
        return __import__(name)
    except Exception:  # noqa: BLE001 - any import failure means "not available"
        return None


def temp_dir() -> str:
    """Writable scratch folder for captures (mirrors the Tcl pickTmpBase)."""
    cands = [os.environ.get(v) for v in ("TEMP", "TMP", "TMPDIR")]
    cands += [tempfile.gettempdir(), os.getcwd(), "C:/Temp", "/tmp"]
    for base in cands:
        if not base:
            continue
        d = os.path.join(base, "hm_shots")
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".wtest")
            with open(probe, "w") as fh:
                fh.write("x")
            os.remove(probe)
            return d
        except OSError:
            continue
    return os.getcwd()


class HMBridge:
    """Live connection to HyperMesh (or offline stub)."""

    CAPTURE_COMMANDS = {
        "jpg": ["*jpegfilenamed"],
        "jpeg": ["*jpegfilenamed"],
        "png": ["*pngfilenamed"],
        "bmp": ["*bmpfilenamed"],
        "tif": ["*tifffilenamed"],
        "tiff": ["*tifffilenamed"],
    }
    HWI_FORMS = [
        ("CaptureActiveWindow", "jpeg"),
        ("CaptureActiveWindow", "JPEG"),
        ("CaptureScreen", "jpeg"),
        ("CaptureScreen", "JPEG"),
        ("CaptureScreenToFile", "jpeg"),
        ("CaptureActiveWindowToFile", "jpeg"),
    ]

    def __init__(self, autodetect: bool = True) -> None:
        self.log: List[str] = []
        self.mode = "offline"            # offline | hm | demo
        self.hm = None
        self.hw = None
        self.model = None
        self._tcl_route: Optional[Callable[[str], Any]] = None
        self._tcl_route_name = ""
        self._cmd_cache: Dict[str, bool] = {}
        self._capture_cmd: Dict[str, str] = {}
        self._hwi_form: Optional[Tuple[str, str]] = None
        self.last_error = ""
        if autodetect:
            self._detect()

    # ------------------------------------------------------------------ setup
    def _note(self, msg: str) -> None:
        self.log.append(msg)
        if len(self.log) > 400:
            del self.log[:100]

    def _detect(self) -> None:
        self.hm = _try_import("hm")
        self.hw = _try_import("hw")
        if self.hm is not None:
            try:
                self.model = self.hm.Model()
            except Exception as exc:  # noqa: BLE001
                self._note("hm.Model() failed: %s" % exc)
                self.model = None
        self._find_tcl_route()
        if self._tcl_route is not None or self.model is not None:
            self.mode = "hm"
        self._note("bridge mode=%s tcl=%s model=%s" % (self.mode, self._tcl_route_name or "-", bool(self.model)))

    def _find_tcl_route(self) -> None:
        candidates: List[Tuple[str, Any]] = []
        for modname in ("hw", "hm", "hwtk", "hwi", "tcl", "Tcl"):
            mod = getattr(self, modname, None) if modname in ("hw", "hm") else _try_import(modname)
            if mod is None:
                continue
            for attr in ("evalTcl", "evaltcl", "hm_evaltcl", "eval_tcl", "tcl", "eval", "tclEval", "TclEval"):
                fn = getattr(mod, attr, None)
                if callable(fn):
                    candidates.append(("%s.%s" % (modname, attr), fn))
        if self.model is not None:
            for attr in ("evalTcl", "evaltcl", "hm_evaltcl", "eval_tcl", "tcl", "tclEval"):
                fn = getattr(self.model, attr, None)
                if callable(fn):
                    candidates.append(("model.%s" % attr, fn))
        for name, fn in candidates:
            try:
                res = fn("expr {1+1}")
                if str(res).strip() == "2":
                    self._tcl_route = fn
                    self._tcl_route_name = name
                    self._note("Tcl route: %s" % name)
                    return
            except Exception as exc:  # noqa: BLE001
                self._note("Tcl route %s rejected: %s" % (name, exc))

    # -------------------------------------------------------------- basics
    @property
    def available(self) -> bool:
        return self.mode != "offline"

    @property
    def has_tcl(self) -> bool:
        return self._tcl_route is not None

    def describe(self) -> str:
        if self.mode == "offline":
            return "offline"
        if self.mode == "demo":
            return "demo"
        return "HyperMesh (%s)" % (self._tcl_route_name or "hm.Model")

    def tcl(self, cmd: str) -> str:
        """Evaluate a Tcl command in HyperMesh; raises HMError when impossible."""
        if self._tcl_route is None:
            raise HMError("No Tcl route to HyperMesh (mode=%s)" % self.mode)
        try:
            res = self._tcl_route(cmd)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            raise HMError("%s -> %s" % (cmd[:120], exc))
        return "" if res is None else str(res)

    def try_tcl(self, cmd: str) -> Tuple[bool, str]:
        try:
            return True, self.tcl(cmd)
        except HMError as exc:
            self._note(str(exc))
            return False, str(exc)

    def cmd_exists(self, name: str) -> bool:
        """Does the Tcl command exist in this build (cached)?"""
        if name in self._cmd_cache:
            return self._cmd_cache[name]
        ok = False
        if self.has_tcl:
            try:
                res = self.tcl("expr {[llength [info commands %s]] || [llength [info commands ::%s]]}" % (name, name))
                ok = res.strip() == "1"
            except HMError:
                ok = False
        self._cmd_cache[name] = ok
        return ok

    def star(self, name: str, *args: Any) -> Any:
        """Run a ``*command``: Tcl route first, then hm.Model method."""
        name = name.lstrip("*")
        if self.has_tcl:
            return self.tcl("*%s %s" % (name, " ".join(tcl_quote(a) for a in args)))
        if self.model is not None:
            fn = getattr(self.model, name, None)
            if callable(fn):
                try:
                    return fn(*args)
                except Exception as exc:  # noqa: BLE001
                    raise HMError("*%s -> %s" % (name, exc))
        raise HMError("*%s unavailable" % name)

    def query(self, name: str, *args: Any) -> Any:
        """Run an ``hm_`` query command."""
        full = name if name.startswith("hm_") else "hm_" + name
        if self.has_tcl:
            return self.tcl("%s %s" % (full, " ".join(tcl_quote(a) for a in args)))
        for owner in (self.model, self.hm):
            fn = getattr(owner, full, None) if owner is not None else None
            if callable(fn):
                try:
                    return fn(*args)
                except Exception as exc:  # noqa: BLE001
                    raise HMError("%s -> %s" % (full, exc))
        raise HMError("%s unavailable" % full)

    def run_lines(self, script: str) -> Tuple[int, int, List[str]]:
        """Execute recorded Tcl lines one by one. Returns (ok, failed, errors)."""
        ok = failed = 0
        errors: List[str] = []
        for line in script.splitlines():
            t = line.strip()
            if not t or t.startswith("#"):
                continue
            try:
                self.tcl(t)
                ok += 1
            except HMError as exc:
                failed += 1
                errors.append(str(exc))
        return ok, failed, errors

    def redraw(self) -> None:
        if not self.available:
            return
        try:
            self.query("redraw")
        except HMError:
            pass

    # ---------------------------------------------------------------- views
    def get_view(self) -> Optional[List[float]]:
        """Camera as the numbers accepted by ``*viewset`` (>= 16) or None."""
        if not self.available:
            return None
        for getter in (lambda: self.query("winfo", "viewmatrix"), lambda: self.query("getviewmatrix")):
            try:
                nums = parse_numbers(getter())
            except HMError:
                continue
            if len(nums) >= 16:
                return nums
        return None

    def set_view(self, nums: Sequence[float]) -> bool:
        if not self.available or len(nums) < 16:
            return False
        try:
            self.star("viewset", *nums)
            return True
        except HMError:
            pass
        try:
            self.query("setviewmatrix", *nums[:16])
            return True
        except HMError:
            return False

    # -------------------------------------------------------------- capture
    def capture(self, path: str, fmt: str = "jpg") -> Optional[str]:
        """Screenshot of the graphics area. Returns the written file path or None.

        HyperMesh classic needs a full path; some builds ignore the directory
        and write into the working directory, so new files there are picked up
        and moved to the requested location (ported from the Tcl macro).
        """
        if not self.available:
            self.last_error = "HyperMesh not connected"
            return None
        fmt = fmt.lower().lstrip(".")
        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        attempts = []
        if fmt in self._capture_cmd:
            attempts.append(self._capture_cmd[fmt])
        attempts += [c for c in self.CAPTURE_COMMANDS.get(fmt, []) if c not in attempts]
        attempts.append("hm_capturescreentofile")
        tcl_path = path.replace("\\", "/")
        for cmd in attempts:
            before = self._snapshot_dirs(path)
            try:
                if cmd.startswith("*"):
                    self.star(cmd, tcl_path)
                else:
                    self.query(cmd, tcl_path)
            except HMError as exc:
                self._note("capture %s failed: %s" % (cmd, exc))
                continue
            got = self._wait_for_file(path, before)
            if got:
                self._capture_cmd[fmt] = cmd
                if self._valid_image(got):
                    return got
                self._note("capture %s produced a degenerate image" % cmd)
        got = self._capture_hwi(path, fmt)
        if got:
            return got
        self.last_error = "no capture command produced a file (%s)" % ", ".join(attempts)
        return None

    def _snapshot_dirs(self, path: str) -> Dict[str, set]:
        dirs = {os.path.dirname(path), os.getcwd()}
        snap: Dict[str, set] = {}
        for d in dirs:
            try:
                snap[d] = set(os.listdir(d))
            except OSError:
                snap[d] = set()
        return snap

    def _wait_for_file(self, path: str, before: Dict[str, set], timeout: float = 2.5) -> Optional[str]:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
            for d, names in before.items():
                try:
                    now = set(os.listdir(d))
                except OSError:
                    continue
                for new in now - names:
                    full = os.path.join(d, new)
                    if os.path.isfile(full) and os.path.getsize(full) > 0 and not new.startswith("."):
                        if full != path:
                            try:
                                shutil.move(full, path)
                            except OSError:
                                return full
                        return path
            time.sleep(0.1)
        return None

    @staticmethod
    def _valid_image(path: str) -> bool:
        dims = imginfo.image_size(path)
        if dims is None:
            return os.path.getsize(path) > 1024
        return dims[0] >= 64 and dims[1] >= 64

    def _capture_hwi(self, path: str, fmt: str) -> Optional[str]:
        """HyperView / HyperWorks Desktop capture through the hwi handle API."""
        if not self.has_tcl or not self.cmd_exists("hwi"):
            return None
        tmp = os.path.join(temp_dir(), "hwic_%d.%s" % (int(time.time() * 1000), fmt)).replace("\\", "/")
        forms = [self._hwi_form] if self._hwi_form else self.HWI_FORMS
        for form in forms:
            if form is None:
                continue
            verb, tok = form
            token = tok if fmt in ("jpg", "jpeg") else (fmt.upper() if tok.isupper() else fmt)
            handle = "hmShotSess%d" % int(time.time() * 1000)
            script = "hwi OpenStack; hwi GetSessionHandle %s; %s %s %s %s; hwi CloseStack" % (
                handle, handle, verb, token, tcl_quote(tmp))
            ok, _ = self.try_tcl(script)
            if not ok:
                self.try_tcl("hwi CloseStack")
                continue
            for _ in range(20):
                if os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
                    break
                time.sleep(0.1)
            if os.path.isfile(tmp) and os.path.getsize(tmp) > 0 and self._valid_image(tmp):
                self._hwi_form = form
                try:
                    shutil.move(tmp, path)
                except OSError:
                    return tmp
                return path
        return None

    # ---------------------------------------------------------- model info
    def model_file(self) -> str:
        """Path of the open .hm file (non-interactive queries only) or ''."""
        if not self.has_tcl:
            return ""
        for cmd in (
            "hm_info hmfilename", "hm_info filename", "hm_info currentfile", "hm_info modelname",
            "hm_info -appinfo CURRENTMODEL", "hm_info -appinfo CURRENTFILE", "hm_info -appinfo MODELFILE",
            "hm_info -appinfo HMFILE", "hm_info -appinfo HMFILENAME", "hm_info -appinfo MODELPATH",
        ):
            ok, res = self.try_tcl(cmd)
            if not ok:
                continue
            res = res.strip()
            if not res:
                continue
            if os.path.isfile(res) or (res.lower().endswith(".hm") and os.path.isdir(os.path.dirname(res))):
                return res
        return ""

    def model_dir(self) -> str:
        f = self.model_file()
        d = os.path.dirname(f) if f else ""
        return d if d and os.path.isdir(d) else ""

    def command_file(self) -> str:
        """HyperMesh command file (command.tcl / command.cmf) or ''."""
        bases = [os.getcwd()]
        if self.has_tcl:
            for cmd in ("hm_info -appinfo COMMANDFILE", "hm_info commandfile"):
                ok, res = self.try_tcl(cmd)
                if ok and res.strip() and os.path.isfile(res.strip()):
                    return res.strip()
            ok, res = self.try_tcl("pwd")
            if ok and res.strip() and os.path.isdir(res.strip()):
                bases.insert(0, res.strip())
        for base in bases:
            for name in ("command.tcl", "command.cmf"):
                p = os.path.join(base, name)
                if os.path.isfile(p):
                    return p
            found = glob.glob(os.path.join(base, "command*.tcl")) + glob.glob(os.path.join(base, "command*.cmf"))
            found = [f for f in found if os.path.isfile(f)]
            if found:
                return max(found, key=os.path.getmtime)
        return ""

    # ------------------------------------------------------------ cosmetics
    def set_background(self, hex_color: str) -> bool:
        """Best-effort background colour change (ported candidates from the Tcl macro)."""
        if not self.has_tcl or not hex_color:
            return False
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return False
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        rf, gf, bf = (round(v / 255.0, 4) for v in (r, g, b))
        done = False
        if self.cmd_exists("hwf::setbackgroundcolor"):
            ok, _ = self.try_tcl("hwf::setbackgroundcolor #%s" % h)
            done = done or ok
        if not done and self.cmd_exists("*setbackgroundgradient"):
            self.try_tcl("*setbackgroundgradient 0")
        if not done:
            for cmd in ("*setbackgroundcolor %s %s %s" % (rf, gf, bf), "*setbackgroundcolor %d %d %d" % (r, g, b),
                        "*setbackgroundcolors %s %s %s %s %s %s" % (rf, gf, bf, rf, gf, bf)):
                if self.cmd_exists(cmd.split()[0]):
                    ok, _ = self.try_tcl(cmd)
                    done = done or ok
        self.redraw()
        return done

    def apply_quality(self) -> bool:
        """Anti-aliasing + max JPEG quality where the build exposes such commands."""
        if not self.has_tcl:
            return False
        any_ok = False
        for group in (("*setantialiasingmode 1", "*setantialiasmode 1", "*setantialiasing 1", "hm_setantialiasing 1"),
                      ("*setjpegquality 100", "*setimagequality 100")):
            for cmd in group:
                if self.cmd_exists(cmd.split()[0]):
                    ok, _ = self.try_tcl(cmd)
                    if ok:
                        any_ok = True
                        break
        return any_ok


class DemoBridge(HMBridge):
    """Simulated HyperMesh: synthetic captures, recorded commands.

    Used by the automated tests and by ``--demo`` so the whole workflow
    (views -> metrics -> folders -> PPTX) can be exercised without HyperMesh.
    """

    def __init__(self) -> None:
        super().__init__(autodetect=False)
        self.mode = "demo"
        self.commands: List[str] = []
        self._view: List[float] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, -100, -100, 100, 100]
        self._tint = 0
        self._metric_tint = 0
        self._tcl_route = self._fake_tcl
        self._tcl_route_name = "demo"
        self.fail_capture = False

    def _fake_tcl(self, cmd: str) -> str:
        self.commands.append(cmd)
        t = cmd.strip()
        if t.startswith("expr"):
            return "2"
        if t.startswith("hm_winfo"):
            return " ".join("%g" % v for v in self._view)
        if t.startswith("*viewset"):
            nums = parse_numbers(t)
            if len(nums) >= 16:
                self._view = nums
            return ""
        if t.startswith("*elementtest") or "elementcheck" in t:
            self._metric_tint = (self._metric_tint % 5) + 1
            return ""
        if t.startswith("*clearmark") or t.startswith("*unmask"):
            self._metric_tint = 0
            return ""
        if "info commands" in t:
            return "0"
        if t.startswith("pwd"):
            return os.getcwd()
        if t.startswith("hm_info"):
            return ""
        return ""

    def rotate_view(self, step: int = 1) -> None:
        self._view = list(self._view)
        self._view[0] = round(((self._view[0] * 10) + step) % 10 / 10.0, 3)
        self._tint = (self._tint + step) % 7

    def capture(self, path: str, fmt: str = "jpg") -> Optional[str]:
        self.commands.append("capture %s" % path)
        if self.fail_capture:
            self.last_error = "demo failure"
            return None
        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        w, h = 320, 200
        base = [(70, 110, 160), (160, 90, 70), (90, 150, 90), (150, 130, 60), (120, 80, 150), (60, 140, 150), (140, 140, 140)][self._tint]
        rows = []
        for y in range(h):
            line = bytearray()
            for x in range(w):
                band = ((x // 20) + (y // 20)) % 2
                col = base if band else tuple(min(255, c + 40) for c in base)
                if self._metric_tint and (x + y) % 17 < self._metric_tint:
                    col = (230, 60, 60)
                line += bytes(col)
            rows.append(bytes(line))
        out = os.path.splitext(path)[0] + ".png"
        imginfo.write_png(out, w, h, rows)
        return out
