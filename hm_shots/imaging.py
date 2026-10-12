# -*- coding: utf-8 -*-
"""Thumbnail creation with whatever imaging backend exists (Pillow, Qt, pure Python)."""
from __future__ import annotations

import base64
import io
import os
from typing import Optional, Tuple

from . import imginfo

THUMB_W = 360
THUMB_H = 220


def _via_pil(path: str, max_w: int, max_h: int) -> Optional[Tuple[bytes, str]]:
    try:
        from PIL import Image  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_w, max_h))
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            return buf.getvalue(), "png"
    except Exception:  # noqa: BLE001
        return None


def _via_qt(path: str, max_w: int, max_h: int) -> Optional[Tuple[bytes, str]]:
    try:
        from .gui.qt import QtCore, QtGui  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        if QtGui.QGuiApplication.instance() is None:
            return None
        img = QtGui.QImage(path)
        if img.isNull():
            return None
        img = img.scaled(max_w, max_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        ba = QtCore.QByteArray()
        buf = QtCore.QBuffer(ba)
        buf.open(QtCore.QIODevice.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return bytes(ba.data()), "png"
    except Exception:  # noqa: BLE001
        return None


def _via_pure(path: str, max_w: int, max_h: int) -> Optional[Tuple[bytes, str]]:
    fmt = imginfo.image_format(path)
    if fmt == "bmp":
        dec = imginfo.read_bmp(path)
        if dec:
            w, h, rows = imginfo.downsample_rows(dec[0], dec[1], dec[2], max_w, max_h)
            tmp = path + ".thumb.png"
            imginfo.write_png(tmp, w, h, rows)
            with open(tmp, "rb") as fh:
                data = fh.read()
            os.remove(tmp)
            return data, "png"
    if fmt in ("png", "jpg", "gif"):
        with open(path, "rb") as fh:
            return fh.read(), fmt   # no scaler available: keep the original bytes
    return None


def make_thumbnail(path: str, max_w: int = THUMB_W, max_h: int = THUMB_H) -> Tuple[str, str]:
    """Return (base64, fmt) thumbnail for an image file ('' when impossible)."""
    if not path or not os.path.isfile(path):
        return "", ""
    for fn in (_via_pil, _via_qt, _via_pure):
        res = fn(path, max_w, max_h)
        if res:
            return base64.b64encode(res[0]).decode("ascii"), res[1]
    return "", ""


def thumb_bytes(b64: str) -> bytes:
    try:
        return base64.b64decode(b64) if b64 else b""
    except Exception:  # noqa: BLE001
        return b""
