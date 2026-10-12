# -*- coding: utf-8 -*-
"""Tiny two-language (PL / EN) string helper."""
from __future__ import annotations

_LANG = "pl"


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = "en" if str(lang).lower().startswith("en") else "pl"


def get_lang() -> str:
    return _LANG


def tr(pl: str, en: str) -> str:
    """Return the Polish or English variant depending on the active language."""
    return en if _LANG == "en" else pl
