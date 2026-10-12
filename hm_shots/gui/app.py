# -*- coding: utf-8 -*-
"""Application entry point - works both inside HyperMesh and standalone."""
from __future__ import annotations

import os
import sys
from typing import List, Optional

_window = None   # keep the window alive inside HyperMesh's embedded interpreter


def run(argv: Optional[List[str]] = None, demo: bool = False, session: str = "") -> object:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--demo" in args:
        demo = True
    dark = "--dark" in args
    lang = ""
    for a in args:
        if a.startswith("--lang="):
            lang = a.split("=", 1)[1]
        elif a.lower().endswith(".json") and os.path.isfile(a):
            session = a

    from .qt import ensure_app, exec_
    app, created = ensure_app(["hm_shots"])
    app.setApplicationName("HyperMesh Shots")

    from ..hm_bridge import DemoBridge, HMBridge
    from ..project import Project, autosave_path
    from ..i18n import set_lang

    bridge = DemoBridge() if demo else HMBridge()
    project = None
    if session and os.path.isfile(session):
        try:
            project = Project.load(session)
        except (OSError, ValueError, KeyError):
            project = None
    elif os.path.isfile(autosave_path()):
        try:
            project = Project.load(autosave_path())
            project.path = ""      # autosave is not the user's session file
        except (OSError, ValueError, KeyError):
            project = None
    if project is None:
        project = Project()
    if lang:
        project.settings.lang = lang
        set_lang(lang)

    from .main_window import MainWindow
    global _window
    _window = MainWindow(bridge, project, dark=dark)
    _window.show()
    if project.views:
        _window.set_status(_window.status_lab.text() + "  ·  " + (
            "Przywrócono poprzednią sesję (%d widoków)." if project.settings.lang != "en" else "Previous session restored (%d views).") % len(project.views))
    # Inside HyperWorks the host application already runs the Qt event loop,
    # so the window is simply shown (non-blocking).  Standalone we created the
    # QApplication ourselves and have to run the loop.
    if created:
        exec_(app)
    return _window
