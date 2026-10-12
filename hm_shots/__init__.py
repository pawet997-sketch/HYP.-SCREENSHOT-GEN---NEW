# -*- coding: utf-8 -*-
"""
HyperMesh Auto-Screenshot & Quality Reporting Tool
==================================================

Python rewrite of the ``Hypermesh_screenshots`` Tcl macro.

Package layout
--------------
hm_bridge   - adapter around the HyperMesh Python/Tcl API (offline-safe)
views       - remembered views (camera + thumbnail + per-view quality metrics)
quality     - quality-check metric registry with editable Tcl recipes
naming      - file naming / folder categorisation (metric or view folders)
layout      - slide layout model (REF / INF slots, presets, JSON persistence)
project     - whole session (settings, views, layout, generated outputs)
capture     - screenshot generation pipeline
pptx_writer - dependency-free PowerPoint (.pptx) writer
gui         - PySide (Qt) user interface
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
