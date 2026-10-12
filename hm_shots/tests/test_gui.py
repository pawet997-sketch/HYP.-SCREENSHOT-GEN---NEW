# -*- coding: utf-8 -*-
"""Offscreen GUI smoke test (skipped when no Qt binding is installed)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from hm_shots.gui.qt import QtWidgets, process_events  # noqa: E402
    HAVE_QT = True
except Exception:  # noqa: BLE001
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "no Qt binding")
class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["test"])

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="hmshots_gui_")
        os.environ["HOME"] = self.tmp

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_workflow(self) -> None:
        from hm_shots.hm_bridge import DemoBridge
        from hm_shots.project import Project
        from hm_shots.gui.main_window import MainWindow

        bridge = DemoBridge()
        project = Project()
        project.settings.out_dir = os.path.join(self.tmp, "shots")
        project.settings.pptx_path = os.path.join(self.tmp, "deck.pptx")
        win = MainWindow(bridge, project)
        win.resize(1300, 820)
        win.show()
        process_events()
        win.remember_view()
        bridge.rotate_view(1)
        win.remember_view()
        self.assertEqual(len(win.tiles), 2)
        tile = win.tiles[project.views.views[0].id]
        tile._rows["aspect"].check.setChecked(True)
        tile._rows["aspect"].spin.setValue(3.3)
        self.assertEqual(project.views.views[0].metric("aspect").threshold, 3.3)
        win.generate()
        process_events()
        self.assertEqual(len(project.outputs), 3)
        win._on_phase("INF")
        win.generate()
        self.assertEqual(len(project.outputs), 6)
        self.assertTrue(os.path.isfile(project.settings.pptx_path))
        le = win.layout_editor
        le.pairs.setValue(2)
        le.preset_tb()
        self.assertEqual(len(project.layout.slots), 4)
        le.mirror("lr")
        le.set_slide(1)
        le.add_slot("REF")
        le._items[-1].setSelected(True)
        le.delete_selected()
        self.assertEqual(len(project.layout.slots), 4)
        win._on_lang("en")
        win._toggle_theme()
        process_events()
        path = os.path.join(self.tmp, "s.hmshots.json")
        win.project.save(path)
        self.assertTrue(win.load_session_file(path))
        self.assertEqual(len(win.project.views), 2)
        win.close()


if __name__ == "__main__":
    unittest.main()
