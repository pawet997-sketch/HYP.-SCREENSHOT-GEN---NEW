# -*- coding: utf-8 -*-
"""Unit tests for the non-GUI modules (run: python -m unittest discover -s hm_shots/tests)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import zipfile

from hm_shots import imginfo, naming
from hm_shots.capture import CommandRecorder, Generator, filter_display_commands
from hm_shots.hm_bridge import DemoBridge, HMBridge, parse_numbers, tcl_quote
from hm_shots.layout import ROLE_ANY, ROLE_INF, ROLE_REF, SlideLayout, Slot, fit_image
from hm_shots.project import Project, ShotOutput
from hm_shots.pptx_writer import DeckSpec, PictureSpec, PlaceholderSpec, SlideSpec, write_pptx
from hm_shots.quality import MetricRegistry
from hm_shots.views import ViewStore


class TmpDirMixin:
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="hmshots_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class ImgInfoTests(TmpDirMixin, unittest.TestCase):
    def test_png_roundtrip_and_size(self) -> None:
        p = os.path.join(self.tmp, "a.png")
        imginfo.write_png(p, 40, 30, imginfo.solid_rows(40, 30, (10, 20, 30)))
        self.assertEqual(imginfo.image_size(p), (40, 30))
        self.assertEqual(imginfo.image_format(p), "png")

    def test_downsample(self) -> None:
        w, h, rows = imginfo.downsample_rows(400, 200, imginfo.solid_rows(400, 200, (1, 2, 3)), 100, 100)
        self.assertEqual((w, h), (100, 50))
        self.assertEqual(len(rows[0]), 300)


class BridgeTests(unittest.TestCase):
    def test_parse_and_quote(self) -> None:
        self.assertEqual(parse_numbers("VS: 1 -2.5 3e2"), [1.0, -2.5, 300.0])
        self.assertEqual(tcl_quote("C:/a b/c.jpg"), "{C:/a b/c.jpg}")
        self.assertEqual(tcl_quote(2.5), "2.5")
        self.assertEqual(tcl_quote(""), "{}")

    def test_offline_bridge(self) -> None:
        b = HMBridge(autodetect=False)
        self.assertFalse(b.available)
        self.assertIsNone(b.get_view())
        self.assertFalse(b.set_view([1] * 20))

    def test_demo_bridge_view_roundtrip(self) -> None:
        b = DemoBridge()
        v = b.get_view()
        self.assertEqual(len(v), 20)
        nums = list(v)
        nums[16] = -55.0
        self.assertTrue(b.set_view(nums))
        self.assertEqual(b.get_view()[16], -55.0)


class NamingTests(TmpDirMixin, unittest.TestCase):
    def test_sanitize_and_patterns(self) -> None:
        self.assertEqual(naming.sanitize('Widok: łącznik/1?'), "Widok_łącznik_1")
        self.assertEqual(naming.shot_basename("{metric}_{phase}_{view}", "Widok 1", "Aspect_Ratio", "REF"), "Aspect_Ratio_REF_Widok_1")
        self.assertEqual(naming.shot_basename("{view}_{phase}", "Widok 1", "", ""), "Widok_1")
        self.assertEqual(naming.folder_name("Widok 1", "Jacobian"), "Jacobian")
        self.assertEqual(naming.folder_name("Widok 1", None), "Widok_1")

    def test_unique_path(self) -> None:
        p1 = naming.unique_path(self.tmp, "x", "jpg", overwrite=False)
        open(p1, "w").close()
        self.assertTrue(naming.unique_path(self.tmp, "x", "jpg", overwrite=False).endswith("x_2.jpg"))
        self.assertEqual(naming.unique_path(self.tmp, "x", "jpg", overwrite=True), p1)


class QualityTests(unittest.TestCase):
    def test_render_and_commands(self) -> None:
        reg = MetricRegistry()
        cmds = reg.commands_for("aspect", 4.5, hide_passed=False)
        self.assertIn("*elementtestaspect elements 1 4.5 2 2 0 0 0 0 0", cmds)
        self.assertEqual(len(reg.commands_for("aspect", 4.5, hide_passed=True)), len(cmds) + 3)
        self.assertEqual(reg.get("jacobian").describe_limit(0.7), "< 0.7")

    def test_learn_recipe(self) -> None:
        lines = ['*createmark elements 1 "displayed"', "*elementtestaspect elements 1 4.370000 2 2 0 0 0 0 0",
                 "*viewset 1 0 0 0", "*jpegfilenamed x.jpg"]
        recipe = MetricRegistry.learn_recipe(lines, 4.37)
        self.assertEqual(recipe, ['*createmark elements 1 "displayed"', "*elementtestaspect elements 1 {thr} 2 2 0 0 0 0 0"])

    def test_custom_and_persistence(self) -> None:
        reg = MetricRegistry()
        m = reg.add_custom("min size", "Min_Size", "Min size", 2.0, "below", ["*elementtestlength elements 1 {thr} 2 2 0 0 0 0 0"])
        reg.active.append(m.key)
        d = reg.to_dict()
        reg2 = MetricRegistry()
        reg2.load_dict(d)
        self.assertIn(m.key, reg2.active)
        self.assertFalse(reg2.get(m.key).builtin)
        self.assertTrue(reg2.get("aspect").builtin)
        self.assertTrue(reg2.remove(m.key))
        self.assertFalse(reg2.remove("aspect"))


class LayoutTests(TmpDirMixin, unittest.TestCase):
    def test_presets(self) -> None:
        lay = SlideLayout()
        lay.apply_left_right(2, True)
        refs, infs = lay.slots_by_role(ROLE_REF), lay.slots_by_role(ROLE_INF)
        self.assertEqual((len(refs), len(infs)), (2, 2))
        self.assertLess(refs[0].x, infs[0].x)
        self.assertAlmostEqual(refs[0].w, infs[0].w)
        lay.apply_top_bottom(1, True)
        self.assertLess(lay.slots_by_role(ROLE_REF)[0].y, lay.slots_by_role(ROLE_INF)[0].y)
        lay.apply_grid(4)
        self.assertEqual(len(lay.slots), 4)
        self.assertFalse(lay.comparison)

    def test_mirror_symmetry(self) -> None:
        lay = SlideLayout()
        lay.slots = [Slot("ref1", ROLE_REF, 0.05, 0.2, 0.3, 0.5)]
        lay.mirror("lr")
        inf = lay.slots_by_role(ROLE_INF)[0]
        x0, _y0, aw, _ah = lay._area()
        self.assertAlmostEqual(inf.x + inf.w - x0, x0 + aw - 0.05, places=6)
        self.assertAlmostEqual(inf.y, 0.2)

    def test_fit_image(self) -> None:
        slot = Slot("a", ROLE_ANY, 0.1, 0.1, 0.4, 0.5)
        x, y, w, h, crop = fit_image(slot, 1600, 900, 0.05, 16 / 9)
        self.assertIsNone(crop)
        self.assertAlmostEqual(w, 0.4)
        self.assertAlmostEqual(h, 0.4)         # 16:9 picture in a box of 0.4 width -> 0.4 height
        slot.fit = "cover"
        _x, _y, _w, _h, crop = fit_image(slot, 1600, 900, 0.05, 16 / 9)
        self.assertIsNotNone(crop)

    def test_save_load(self) -> None:
        lay = SlideLayout.default(True)
        p = os.path.join(self.tmp, "l.json")
        lay.save(p)
        lay2 = SlideLayout.load(p)
        self.assertEqual([s.to_dict() for s in lay.slots], [s.to_dict() for s in lay2.slots])


class ViewStoreTests(unittest.TestCase):
    def test_store_ops(self) -> None:
        st = ViewStore()
        a = st.add([1] * 20)
        b = st.add([2] * 20, name="B")
        self.assertEqual(a.name, "Widok 1")
        self.assertTrue(st.move(b.id, -1))
        self.assertEqual(st.views[0].id, b.id)
        d = st.duplicate(a.id)
        self.assertEqual(len(st), 3)
        a.metric("aspect").enabled = True
        a.plain = False
        self.assertEqual(a.shot_kinds(), ["aspect"])
        st2 = ViewStore.from_dict(st.to_dict())
        self.assertEqual(st2.names(), st.names())
        self.assertEqual(st2.next_id, st.next_id)
        self.assertIsNotNone(d)


class PptxTests(TmpDirMixin, unittest.TestCase):
    def test_write_and_structure(self) -> None:
        img = os.path.join(self.tmp, "i.png")
        imginfo.write_png(img, 64, 40, imginfo.solid_rows(64, 40, (200, 100, 50)))
        slot_a = Slot("ref1", ROLE_REF, 0.05, 0.15, 0.4, 0.7)
        slot_b = Slot("inf1", ROLE_INF, 0.55, 0.15, 0.4, 0.7)
        deck = DeckSpec(slides=[SlideSpec("T", [PictureSpec(img, slot_a, "REF", ROLE_REF)], [PlaceholderSpec(slot_b, "INF", ROLE_INF)])],
                        deck_title="Deck")
        out = write_pptx(os.path.join(self.tmp, "d.pptx"), deck)
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            self.assertIn("ppt/slides/slide2.xml", names)
            self.assertIn("ppt/media/image1.png", names)
            xml = z.read("ppt/slides/slide2.xml").decode("utf-8")
            self.assertIn("<p:pic>", xml)
            self.assertIn('prstDash val="dash"', xml)
            self.assertIn("[Content_Types].xml", names)
        try:
            from pptx import Presentation  # type: ignore
        except Exception:  # noqa: BLE001
            return
        prs = Presentation(out)
        self.assertEqual(len(prs.slides), 2)


class PipelineTests(TmpDirMixin, unittest.TestCase):
    def _project(self) -> Project:
        p = Project()
        p.settings.out_dir = os.path.join(self.tmp, "out")
        p.settings.pptx_path = os.path.join(self.tmp, "out", "deck.pptx")
        return p

    def test_generate_ref_inf_folders_and_deck(self) -> None:
        p = self._project()
        b = DemoBridge()
        g = Generator(p, b)
        v1 = g.remember_view("Widok ogólny")
        v2 = g.remember_view("Łącznik")
        self.assertTrue(v1.thumb_b64)
        v1.metric("aspect").enabled = True
        v1.metric("aspect").threshold = 4.5
        v2.plain = False
        v2.metric("jacobian").enabled = True
        res = g.run()
        self.assertEqual((res.ok, res.failed), (3, 0), res.errors)
        out = p.settings.out_dir
        self.assertEqual(sorted(os.listdir(out)), ["Aspect_Ratio", "Jacobian", "Widok_ogólny", "deck.pptx"])
        self.assertTrue(os.path.isfile(os.path.join(out, "Aspect_Ratio", "Aspect_Ratio_REF_Widok_ogólny.png")))
        self.assertTrue(os.path.isfile(os.path.join(out, "Jacobian", "Jacobian_REF_Łącznik.png")))
        self.assertTrue(os.path.isfile(os.path.join(out, "Widok_ogólny", "Widok_ogólny_REF.png")))
        # the metric recipe ran with the per-view limit and cleanup followed
        self.assertTrue(any("*elementtestaspect elements 1 4.5" in c for c in b.commands))
        self.assertTrue(any(c.startswith("*clearmark") for c in b.commands))
        plan = p.deck_plan()
        self.assertEqual(len(plan), 3)
        self.assertTrue(plan[0].placements[0].image)      # REF filled
        self.assertFalse(plan[0].placements[1].image)     # INF empty -> placeholder
        p.settings.phase = ROLE_INF
        res2 = g.run()
        self.assertEqual(res2.ok, 3)
        plan = p.deck_plan()
        self.assertTrue(all(pl.image for s in plan for pl in s.placements))
        self.assertTrue(os.path.isfile(p.settings.pptx_path))

    def test_session_roundtrip_keeps_outputs(self) -> None:
        p = self._project()
        g = Generator(p, DemoBridge())
        g.remember_view("A")
        g.run()
        path = os.path.join(self.tmp, "s.hmshots.json")
        p.save(path)
        p2 = Project.load(path)
        self.assertEqual(len(p2.outputs), 1)
        self.assertEqual(p2.outputs[0].phase, ROLE_REF)
        self.assertEqual(p2.views.views[0].name, "A")
        with open(path, encoding="utf-8") as fh:
            self.assertIn("hm_shots_project", json.load(fh))

    def test_single_mode_grid(self) -> None:
        p = self._project()
        p.settings.comparison = False
        p.layout.apply_grid(2)
        g = Generator(p, DemoBridge())
        for i in range(3):
            g.remember_view("V%d" % i)
        res = g.run()
        self.assertEqual(res.ok, 3)
        self.assertEqual(os.path.basename(res.files[0]), "V0.png")
        plan = p.deck_plan()
        self.assertEqual([len(s.placements) for s in plan], [2, 1])

    def test_offline_generate_reports_error(self) -> None:
        p = self._project()
        p.views.add([1] * 20)
        res = Generator(p, HMBridge(autodetect=False)).run()
        self.assertEqual(res.ok, 0)
        self.assertTrue(res.errors)

    def test_command_recorder_and_filter(self) -> None:
        cmd = os.path.join(self.tmp, "command.tcl")
        with open(cmd, "w") as fh:
            fh.write("*old 1\n")
        rec = CommandRecorder(HMBridge(autodetect=False), override=cmd)
        self.assertTrue(rec.start())
        with open(cmd, "a") as fh:
            fh.write("*displaycollector components 1\n*viewset 1 2 3\n*maskentitymark elements 1 1\n")
        lines = rec.stop()
        self.assertEqual(filter_display_commands(lines), "*displaycollector components 1\n*maskentitymark elements 1 1")

    def test_record_output_replaces_same_key(self) -> None:
        p = Project()
        p.record_output(ShotOutput(1, "v", "plain", "", None, "REF", "a.png"))
        p.record_output(ShotOutput(1, "v", "plain", "", None, "REF", "b.png"))
        self.assertEqual(len(p.outputs), 1)
        self.assertEqual(p.output_for(1, "plain", "REF").path, "b.png")


if __name__ == "__main__":
    unittest.main()
