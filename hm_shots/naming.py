# -*- coding: utf-8 -*-
"""File naming and folder categorisation.

* a screenshot taken with a quality metric goes to ``<out>/<Metric>/`` and its
  file name starts with the metric label (``Aspect_Ratio_REF_Widok_1.jpg``)
* a plain screenshot (no metric) goes to ``<out>/<ViewName>/``
"""
from __future__ import annotations

import os
import re
from typing import Dict, Optional

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

DEFAULT_PATTERN_METRIC = "{metric}_{phase}_{view}"
DEFAULT_PATTERN_PLAIN = "{view}_{phase}"


def sanitize(name: str, fallback: str = "shot", ascii_only: bool = False) -> str:
    """Make a string safe for file and folder names."""
    s = (name or "").strip()
    if ascii_only:
        s = s.translate(_PL)
    s = _BAD.sub("_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._ ")
    return s or fallback


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return ""


def fill_pattern(pattern: str, tokens: Dict[str, str]) -> str:
    """``str.format``-like substitution that tolerates empty / missing tokens and
    collapses the underscores they leave behind."""
    try:
        s = pattern.format_map(_Safe({k: (v or "") for k, v in tokens.items()}))
    except (ValueError, KeyError):
        s = pattern
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"(^_+|_+$)", "", s)
    return sanitize(s)


def folder_name(view_name: str, metric_label: Optional[str]) -> str:
    """Folder for a shot: metric label, or the view name when no metric was used."""
    return sanitize(metric_label) if metric_label else sanitize(view_name)


def shot_basename(pattern: str, view_name: str, metric_label: str, phase: str, extra: Optional[Dict[str, str]] = None) -> str:
    tokens = {"view": sanitize(view_name), "metric": sanitize(metric_label) if metric_label else "",
              "phase": sanitize(phase) if phase else ""}
    if extra:
        tokens.update(extra)
    return fill_pattern(pattern, tokens)


def next_index(directory: str, prefix: str = "") -> int:
    """Next free sequential number based on existing ``prefix_NNN`` files."""
    mx = 0
    try:
        names = os.listdir(directory)
    except OSError:
        return 1
    for n in names:
        stem = os.path.splitext(n)[0]
        if prefix and not stem.startswith(prefix):
            continue
        m = re.search(r"(\d+)$", stem)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def unique_path(directory: str, base: str, ext: str, overwrite: bool) -> str:
    """Target path; when not overwriting, append ``_2``, ``_3`` ... until free."""
    ext = ext.lstrip(".")
    path = os.path.join(directory, "%s.%s" % (base, ext))
    if overwrite or not os.path.exists(path):
        return path
    i = 2
    while True:
        cand = os.path.join(directory, "%s_%d.%s" % (base, i, ext))
        if not os.path.exists(cand):
            return cand
        i += 1
