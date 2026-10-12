# -*- coding: utf-8 -*-
"""
Dependency-free image helpers.

* ``image_size(path)``  - (width, height) for PNG / JPEG / BMP / GIF files
* ``write_png(path, w, h, rows)`` - minimal PNG encoder (used for synthetic
  demo captures and placeholder thumbnails when no imaging library exists)
* ``read_bmp(path)`` - decode an uncompressed 24/32-bit BMP into RGB rows
"""
from __future__ import annotations

import os
import struct
import zlib
from typing import List, Optional, Sequence, Tuple


def image_size(path: str) -> Optional[Tuple[int, int]]:
    """Return (width, height) of a PNG/JPEG/GIF/BMP image or None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:6] in (b"GIF87a", b"GIF89a"):
                w, h = struct.unpack("<HH", head[6:10])
                return int(w), int(h)
            if head[:2] == b"BM":
                fh.seek(18)
                w, h = struct.unpack("<ii", fh.read(8))
                return int(w), abs(int(h))
            if head[:2] == b"\xff\xd8":
                return _jpeg_size(fh)
    except (OSError, struct.error):
        return None
    return None


def _jpeg_size(fh) -> Optional[Tuple[int, int]]:
    fh.seek(2)
    while True:
        marker = fh.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        code = marker[1]
        while code == 0xFF:  # padding
            b = fh.read(1)
            if not b:
                return None
            code = b[0]
        if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
            continue
        seg = fh.read(2)
        if len(seg) < 2:
            return None
        (length,) = struct.unpack(">H", seg)
        if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            data = fh.read(5)
            if len(data) < 5:
                return None
            h, w = struct.unpack(">HH", data[1:5])
            return int(w), int(h)
        fh.seek(length - 2, os.SEEK_CUR)


def image_format(path: str) -> str:
    """Lower-case format token (jpg/png/bmp/gif) from the file header, '' if unknown."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
    except OSError:
        return ""
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:2] == b"\xff\xd8":
        return "jpg"
    if head[:2] == b"BM":
        return "bmp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return ""


def write_png(path: str, width: int, height: int, rows: Sequence[bytes]) -> None:
    """Write an 8-bit RGB PNG. ``rows`` = list of ``bytes`` of length width*3."""
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def solid_rows(width: int, height: int, rgb: Tuple[int, int, int]) -> List[bytes]:
    px = bytes(rgb)
    row = px * width
    return [row] * height


def read_bmp(path: str) -> Optional[Tuple[int, int, List[bytes]]]:
    """Decode an uncompressed 24/32-bit BMP. Returns (w, h, rows[top..bottom] as RGB bytes)."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if data[:2] != b"BM" or len(data) < 54:
        return None
    (offset,) = struct.unpack_from("<I", data, 10)
    w, h = struct.unpack_from("<ii", data, 18)
    (bpp,) = struct.unpack_from("<H", data, 28)
    (comp,) = struct.unpack_from("<I", data, 30)
    if bpp not in (24, 32) or comp not in (0, 3):
        return None
    bottom_up = h > 0
    h = abs(h)
    bytes_pp = bpp // 8
    stride = ((w * bytes_pp + 3) // 4) * 4
    rows: List[bytes] = []
    for y in range(h):
        src_y = (h - 1 - y) if bottom_up else y
        start = offset + src_y * stride
        line = data[start:start + w * bytes_pp]
        if len(line) < w * bytes_pp:
            return None
        if bytes_pp == 3:
            rows.append(bytes(_bgr_to_rgb(line, 3)))
        else:
            rows.append(bytes(_bgr_to_rgb(line, 4)))
    return w, h, rows


def _bgr_to_rgb(line: bytes, step: int) -> bytearray:
    out = bytearray(len(line) // step * 3)
    j = 0
    for i in range(0, len(line), step):
        out[j] = line[i + 2]
        out[j + 1] = line[i + 1]
        out[j + 2] = line[i]
        j += 3
    return out


def downsample_rows(width: int, height: int, rows: Sequence[bytes], max_w: int, max_h: int) -> Tuple[int, int, List[bytes]]:
    """Nearest-neighbour downscale keeping aspect ratio (pure Python)."""
    if width <= max_w and height <= max_h:
        return width, height, list(rows)
    scale = min(max_w / float(width), max_h / float(height))
    nw = max(1, int(width * scale))
    nh = max(1, int(height * scale))
    out: List[bytes] = []
    for y in range(nh):
        src = rows[min(height - 1, int(y / scale))]
        line = bytearray(nw * 3)
        for x in range(nw):
            sx = min(width - 1, int(x / scale)) * 3
            line[x * 3:x * 3 + 3] = src[sx:sx + 3]
        out.append(bytes(line))
    return nw, nh, out
