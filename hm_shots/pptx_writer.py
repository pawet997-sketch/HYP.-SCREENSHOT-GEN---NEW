# -*- coding: utf-8 -*-
"""
Dependency-free PowerPoint writer (Office Open XML, .pptx).

Only what the tool needs: blank 16:9 / 4:3 slides with a title text box,
pictures placed at normalised rectangles, captions and dashed placeholder
boxes for slots that are not filled yet (e.g. INF slots before the INF
phase).  The output opens in PowerPoint, LibreOffice and python-pptx.
"""
from __future__ import annotations

import os
import time
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from . import imginfo
from .layout import Slot, fit_image

EMU_W = {"16:9": 12192000, "4:3": 9144000}
EMU_H = 6858000
NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
XML_HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"

COLOR_TITLE = "1F2937"
COLOR_CAPTION = "374151"
COLOR_PLACEHOLDER_FILL = "F3F4F6"
COLOR_PLACEHOLDER_LINE = "9CA3AF"
COLOR_PLACEHOLDER_TEXT = "6B7280"
ROLE_COLORS = {"REF": "2563EB", "INF": "DC2626", "ANY": "4B5563"}


@dataclass
class PictureSpec:
    path: str
    slot: Slot
    caption: str = ""
    role: str = "ANY"


@dataclass
class PlaceholderSpec:
    slot: Slot
    text: str = ""
    role: str = "ANY"


@dataclass
class SlideSpec:
    title: str = ""
    pictures: List[PictureSpec] = field(default_factory=list)
    placeholders: List[PlaceholderSpec] = field(default_factory=list)
    subtitle: str = ""


@dataclass
class DeckSpec:
    slides: List[SlideSpec]
    aspect: str = "16:9"
    show_title: bool = True
    title_height: float = 0.11
    margin: float = 0.035
    caption_height: float = 0.045
    deck_title: str = ""
    title_slide_lines: List[str] = field(default_factory=list)
    font: str = "Calibri"
    show_captions: bool = True


def _emu(frac: float, total: int) -> int:
    return int(round(frac * total))


def _xfrm(x: int, y: int, w: int, h: int) -> str:
    return '<a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>' % (x, y, max(w, 1), max(h, 1))


def _textbox(shape_id: int, name: str, x: int, y: int, w: int, h: int, text: str, size: int, bold: bool,
             color: str, align: str, anchor: str, font: str, fill: str = "", line: str = "", dash: bool = False) -> str:
    sp_pr = _xfrm(x, y, w, h) + '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    sp_pr += ('<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % fill) if fill else "<a:noFill/>"
    if line:
        sp_pr += '<a:ln w="19050"><a:solidFill><a:srgbClr val="%s"/></a:solidFill>%s</a:ln>' % (
            line, '<a:prstDash val="dash"/>' if dash else "")
    paras = []
    for ln in (text or "").split("\n"):
        paras.append(
            '<a:p><a:pPr algn="%s"/><a:r><a:rPr lang="pl-PL" sz="%d"%s dirty="0"><a:solidFill><a:srgbClr val="%s"/>'
            '</a:solidFill><a:latin typeface="%s"/></a:rPr><a:t>%s</a:t></a:r></a:p>'
            % (align, size, ' b="1"' if bold else "", color, escape(font), escape(ln)))
    return (
        '<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        '<p:spPr>%s</p:spPr><p:txBody><a:bodyPr wrap="square" lIns="45720" tIns="27432" rIns="45720" bIns="27432" '
        'anchor="%s"><a:normAutofit/></a:bodyPr><a:lstStyle/>%s</p:txBody></p:sp>'
        % (shape_id, escape(name), sp_pr, anchor, "".join(paras)))


def _picture(shape_id: int, rid: str, name: str, x: int, y: int, w: int, h: int, crop: Optional[Tuple[float, float, float, float]]) -> str:
    src = ""
    if crop:
        l, t, r, b = (int(round(v * 100000)) for v in crop)
        src = '<a:srcRect l="%d" t="%d" r="%d" b="%d"/>' % (l, t, r, b)
    return (
        '<p:pic><p:nvPicPr><p:cNvPr id="%d" name="%s" descr="%s"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/>'
        '</p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="%s"/>%s<a:stretch><a:fillRect/></a:stretch>'
        '</p:blipFill><p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        % (shape_id, escape(name), escape(name), rid, src, _xfrm(x, y, w, h)))


_SPTREE_HEAD = ('<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
                '<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>')


class PptxWriter:
    def __init__(self, deck: DeckSpec) -> None:
        self.deck = deck
        self.W = EMU_W.get(deck.aspect, EMU_W["16:9"])
        self.H = EMU_H
        self.ratio = self.W / float(self.H)
        self._media: Dict[str, str] = {}      # source path -> media file name
        self._media_bytes: Dict[str, bytes] = {}

    # ------------------------------------------------------------- media
    def _media_name(self, path: str) -> Optional[str]:
        if path in self._media:
            return self._media[path]
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            return None
        ext = imginfo.image_format(path) or os.path.splitext(path)[1].lstrip(".").lower() or "bin"
        if ext == "jpeg":
            ext = "jpg"
        name = "image%d.%s" % (len(self._media) + 1, ext)
        self._media[path] = name
        self._media_bytes[name] = data
        return name

    # ------------------------------------------------------------- slides
    def _slide_xml(self, spec: SlideSpec, rels: List[Tuple[str, str, str]]) -> str:
        d = self.deck
        shapes: List[str] = []
        sid = 2
        if d.show_title and (spec.title or spec.subtitle):
            m = _emu(d.margin, self.W)
            th = _emu(d.title_height, self.H)
            txt = spec.title + ("\n" + spec.subtitle if spec.subtitle else "")
            shapes.append(_textbox(sid, "Title", m, _emu(0.02, self.H), self.W - 2 * m, th, txt,
                                   2400 if not spec.subtitle else 2000, True, COLOR_TITLE, "l", "ctr", d.font))
            sid += 1
        for ph in spec.placeholders:
            x, y, w, h = ph.slot.x, ph.slot.y, ph.slot.w, ph.slot.h
            shapes.append(_textbox(sid, "Placeholder %s" % ph.role, _emu(x, self.W), _emu(y, self.H), _emu(w, self.W),
                                   _emu(h, self.H), ph.text, 1400, False, COLOR_PLACEHOLDER_TEXT, "ctr", "ctr", d.font,
                                   fill=COLOR_PLACEHOLDER_FILL, line=COLOR_PLACEHOLDER_LINE, dash=True))
            sid += 1
        for pic in spec.pictures:
            name = self._media_name(pic.path)
            if name is None:
                shapes.append(_textbox(sid, "Missing", _emu(pic.slot.x, self.W), _emu(pic.slot.y, self.H),
                                       _emu(pic.slot.w, self.W), _emu(pic.slot.h, self.H),
                                       "brak pliku:\n%s" % os.path.basename(pic.path), 1200, False,
                                       COLOR_PLACEHOLDER_TEXT, "ctr", "ctr", d.font, fill=COLOR_PLACEHOLDER_FILL,
                                       line="DC2626", dash=True))
                sid += 1
                continue
            rid = "rId%d" % (len(rels) + 2)
            rels.append((rid, RT + "image", "../media/" + name))
            dims = imginfo.image_size(pic.path)
            cap_h = d.caption_height if (d.show_captions and pic.slot.caption) else 0.0
            x, y, w, h, crop = fit_image(pic.slot, dims[0] if dims else None, dims[1] if dims else None, cap_h, self.ratio)
            shapes.append(_picture(sid, rid, os.path.basename(pic.path), _emu(x, self.W), _emu(y, self.H),
                                   _emu(w, self.W), _emu(h, self.H), crop))
            sid += 1
            if cap_h > 0 and pic.caption:
                cy = min(y + h, pic.slot.y + pic.slot.h - cap_h)   # directly under the picture
                shapes.append(_textbox(sid, "Caption", _emu(pic.slot.x, self.W), _emu(cy, self.H),
                                       _emu(pic.slot.w, self.W), _emu(cap_h, self.H), pic.caption, 1200, True,
                                       ROLE_COLORS.get(pic.role, COLOR_CAPTION), "ctr", "ctr", d.font))
                sid += 1
        return (XML_HDR + '<p:sld %s><p:cSld>%s%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
                % (NS, _SPTREE_HEAD, "".join(shapes)))

    def _title_slide_xml(self) -> str:
        d = self.deck
        m = _emu(d.margin, self.W)
        shapes = [
            _textbox(2, "Deck title", m, _emu(0.30, self.H), self.W - 2 * m, _emu(0.18, self.H), d.deck_title,
                     3600, True, COLOR_TITLE, "ctr", "ctr", d.font),
            _textbox(3, "Deck info", m, _emu(0.50, self.H), self.W - 2 * m, _emu(0.30, self.H),
                     "\n".join(d.title_slide_lines), 1600, False, COLOR_CAPTION, "ctr", "t", d.font),
        ]
        return (XML_HDR + '<p:sld %s><p:cSld>%s%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
                % (NS, _SPTREE_HEAD, "".join(shapes)))

    # ------------------------------------------------------------- package
    def write(self, path: str) -> str:
        d = self.deck
        slides_xml: List[str] = []
        slide_rels: List[List[Tuple[str, str, str]]] = []
        if d.deck_title:
            slides_xml.append(self._title_slide_xml())
            slide_rels.append([])
        for spec in d.slides:
            rels: List[Tuple[str, str, str]] = []
            slides_xml.append(self._slide_xml(spec, rels))
            slide_rels.append(rels)
        n = len(slides_xml)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", self._content_types(n))
            z.writestr("_rels/.rels", self._root_rels())
            z.writestr("docProps/core.xml", self._core())
            z.writestr("docProps/app.xml", self._app(n))
            z.writestr("ppt/presentation.xml", self._presentation(n))
            z.writestr("ppt/_rels/presentation.xml.rels", self._presentation_rels(n))
            z.writestr("ppt/presProps.xml", XML_HDR + '<p:presentationPr %s/>' % NS)
            z.writestr("ppt/viewProps.xml", XML_HDR + '<p:viewPr %s><p:gridSpacing cx="76200" cy="76200"/></p:viewPr>' % NS)
            z.writestr("ppt/tableStyles.xml", XML_HDR + '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>')
            z.writestr("ppt/theme/theme1.xml", THEME_XML % (escape(d.font), escape(d.font)))
            z.writestr("ppt/slideMasters/slideMaster1.xml", MASTER_XML % NS)
            z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _rels([
                ("rId1", RT + "slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", RT + "theme", "../theme/theme1.xml")]))
            z.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT_XML % NS)
            z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _rels([
                ("rId1", RT + "slideMaster", "../slideMasters/slideMaster1.xml")]))
            for i, xml in enumerate(slides_xml, start=1):
                z.writestr("ppt/slides/slide%d.xml" % i, xml)
                rels = [("rId1", RT + "slideLayout", "../slideLayouts/slideLayout1.xml")] + slide_rels[i - 1]
                z.writestr("ppt/slides/_rels/slide%d.xml.rels" % i, _rels(rels))
            for name, data in self._media_bytes.items():
                z.writestr("ppt/media/" + name, data)
        if os.path.exists(path):
            os.remove(path)
        os.replace(tmp, path)
        return path

    def _content_types(self, n: int) -> str:
        parts = [
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '<Default Extension="xml" ContentType="application/xml"/>',
            '<Default Extension="jpg" ContentType="image/jpeg"/>',
            '<Default Extension="jpeg" ContentType="image/jpeg"/>',
            '<Default Extension="png" ContentType="image/png"/>',
            '<Default Extension="bmp" ContentType="image/bmp"/>',
            '<Default Extension="gif" ContentType="image/gif"/>',
            '<Default Extension="tif" ContentType="image/tiff"/>',
            '<Default Extension="tiff" ContentType="image/tiff"/>',
            '<Default Extension="bin" ContentType="application/octet-stream"/>',
            '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
            '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
            '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
            '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
            '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>',
            '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>',
            '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>',
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
        ]
        for i in range(1, n + 1):
            parts.append('<Override PartName="/ppt/slides/slide%d.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' % i)
        return XML_HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">%s</Types>' % "".join(parts)

    @staticmethod
    def _root_rels() -> str:
        return _rels([
            ("rId1", RT + "officeDocument", "ppt/presentation.xml"),
            ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
            ("rId3", RT + "extended-properties", "docProps/app.xml")])

    def _core(self) -> str:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return (XML_HDR + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                '<dc:title>%s</dc:title><dc:creator>HM Shots</dc:creator><cp:lastModifiedBy>HM Shots</cp:lastModifiedBy>'
                '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
                '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified></cp:coreProperties>'
                % (escape(self.deck.deck_title or "HyperMesh screenshots"), now, now))

    @staticmethod
    def _app(n: int) -> str:
        return (XML_HDR + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
                'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                '<Application>Microsoft Office PowerPoint</Application><Slides>%d</Slides></Properties>' % n)

    def _presentation(self, n: int) -> str:
        ids = "".join('<p:sldId id="%d" r:id="rId%d"/>' % (256 + i, 10 + i) for i in range(n))
        return (XML_HDR + '<p:presentation %s saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
                '</p:sldMasterIdLst><p:sldIdLst>%s</p:sldIdLst><p:sldSz cx="%d" cy="%d"/><p:notesSz cx="6858000" cy="9144000"/>'
                '<p:defaultTextStyle><a:defPPr><a:defRPr lang="pl-PL"/></a:defPPr><a:lvl1pPr marL="0" algn="l" defTabSz="914400" '
                'rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1"><a:defRPr sz="1800" kern="1200"><a:solidFill><a:schemeClr val="tx1"/>'
                '</a:solidFill><a:latin typeface="+mn-lt"/><a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:lvl1pPr>'
                '</p:defaultTextStyle></p:presentation>' % (NS, ids, self.W, self.H))

    @staticmethod
    def _presentation_rels(n: int) -> str:
        rels = [
            ("rId1", RT + "slideMaster", "slideMasters/slideMaster1.xml"),
            ("rId2", RT + "theme", "theme/theme1.xml"),
            ("rId3", RT + "presProps", "presProps.xml"),
            ("rId4", RT + "viewProps", "viewProps.xml"),
            ("rId5", RT + "tableStyles", "tableStyles.xml"),
        ]
        for i in range(n):
            rels.append(("rId%d" % (10 + i), RT + "slide", "slides/slide%d.xml" % (i + 1)))
        return _rels(rels)


def _rels(items: List[Tuple[str, str, str]]) -> str:
    body = "".join('<Relationship Id="%s" Type="%s" Target="%s"/>' % (i, t, escape(g)) for i, t, g in items)
    return XML_HDR + '<Relationships xmlns="%s">%s</Relationships>' % (REL_NS, body)


def write_pptx(path: str, deck: DeckSpec) -> str:
    return PptxWriter(deck).write(path)


MASTER_XML = XML_HDR + (
    '<p:sldMaster %s><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>' + _SPTREE_HEAD +
    '</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
    'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    '<p:txStyles><p:titleStyle><a:lvl1pPr algn="l"><a:defRPr sz="3200" b="1"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
    '<a:latin typeface="+mj-lt"/></a:defRPr></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800">'
    '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:bodyStyle>'
    '<p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
    '<a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:otherStyle></p:txStyles></p:sldMaster>')

LAYOUT_XML = XML_HDR + (
    '<p:sldLayout %s type="blank" preserve="1"><p:cSld name="Blank">' + _SPTREE_HEAD +
    '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')

THEME_XML = XML_HDR + (
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="HM Shots">'
    '<a:themeElements><a:clrScheme name="HM Shots"><a:dk1><a:srgbClr val="1F2937"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="374151"/></a:dk2><a:lt2><a:srgbClr val="F3F4F6"/></a:lt2><a:accent1><a:srgbClr val="2563EB"/></a:accent1>'
    '<a:accent2><a:srgbClr val="DC2626"/></a:accent2><a:accent3><a:srgbClr val="059669"/></a:accent3><a:accent4><a:srgbClr val="D97706"/></a:accent4>'
    '<a:accent5><a:srgbClr val="7C3AED"/></a:accent5><a:accent6><a:srgbClr val="0891B2"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink>'
    '<a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme>'
    '<a:fontScheme name="HM Shots"><a:majorFont><a:latin typeface="%s"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="%s"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
    '<a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
    '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill>'
    '<a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
    '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle>'
    '<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
    '</a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>')
