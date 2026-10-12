# -*- coding: utf-8 -*-
"""
HyperMesh Auto-Screenshot & Quality Reporting Tool - launcher.

Inside HyperMesh:   File > Run > Python script ...  -> choose this file
Standalone / demo:  python hm_screenshot_tool.py --demo

The ``hm_shots`` package must sit next to this file.
"""
import os
import sys


def _locate_package_dir():
    candidates = []
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:                     # some "run script" hosts exec() the file
        pass
    argv = getattr(sys, "argv", None) or []
    candidates += [os.path.dirname(os.path.abspath(argv[0])) if argv and argv[0] else "",
                   os.environ.get("HM_SHOTS_DIR", ""), os.getcwd()]
    for d in candidates:
        if d and os.path.isdir(os.path.join(d, "hm_shots")):
            return d
    return ""


_dir = _locate_package_dir()
if _dir and _dir not in sys.path:
    sys.path.insert(0, _dir)

from hm_shots.gui.app import run  # noqa: E402

window = run((getattr(sys, "argv", None) or [])[1:])
