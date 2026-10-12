# -*- coding: utf-8 -*-
"""Main window of the HyperMesh Auto-Screenshot & Quality Reporting Tool."""
from __future__ import annotations

import os
from typing import Dict, Optional

from .. import __version__
from ..capture import CommandRecorder, Generator
from ..hm_bridge import HMBridge
from ..i18n import get_lang, set_lang, tr
from ..layout import ROLE_INF, ROLE_REF
from ..project import Project, autosave_path
from ..views import ViewRecord
from . import help_text
from .dialogs import EditViewDialog, LearnMetricDialog, HelpDialog, run_dialog
from .layout_editor import LayoutEditor
from .metrics_panel import MetricsPanel
from .qt import QShortcut, Qt, QtCore, QtGui, QtWidgets, process_events, screen_size
from .theme import stylesheet
from .view_tile import TILE_W, ViewTile
from .widgets import Card, FlowLayout, Segmented, badge, button, confirm, hint_label, hline, repolish, warn

BACKGROUNDS = [("", ("bez zmian", "no change")), ("#ffffff", ("białe", "white")), ("#000000", ("czarne", "black")),
               ("#1f1f1f", ("grafit", "graphite")), ("#10243b", ("granat", "navy"))]


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, bridge: HMBridge, project: Optional[Project] = None, dark: bool = False) -> None:
        super().__init__()
        self.bridge = bridge
        self.project = project or Project()
        set_lang(self.project.settings.lang)
        self.dark = dark or self.project.settings.theme == "dark"
        self.generator = Generator(self.project, self.bridge, log=self.log, progress=self._progress, pump=process_events)
        self.tiles: Dict[int, ViewTile] = {}
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1500)
        self._autosave_timer.timeout.connect(self.autosave)
        self.setWindowTitle("HyperMesh Shots %s" % __version__)
        sw, sh = screen_size()
        self.resize(min(1480, int(sw * 0.9)), min(900, int(sh * 0.9)))
        self.setMinimumSize(960, 600)
        self.apply_theme()
        self.build_ui()

    # ================================================================ UI
    def apply_theme(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet(self.dark))
        self.project.settings.theme = "dark" if self.dark else "light"

    def build_ui(self) -> None:
        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        vbox = QtWidgets.QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._header())

        body = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(body)
        bl.setContentsMargins(14, 12, 14, 10)
        bl.setSpacing(10)
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._views_panel())
        self.splitter.addWidget(self._settings_panel())
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setSizes([780, 620])
        bl.addWidget(self.splitter, 1)
        bl.addWidget(self._bottom_bar())
        vbox.addWidget(body, 1)

        self.sc_remember = QShortcut(QtGui.QKeySequence("1"), self)
        self.sc_remember.activated.connect(self.remember_view)
        self.sc_generate = QShortcut(QtGui.QKeySequence("K"), self)
        self.sc_generate.activated.connect(self.generate)
        self.sc_save = QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.sc_save.activated.connect(self.save_session)

        self.rebuild_tiles()
        self.refresh_phase_ui()
        self.set_status(tr("Ustaw model w oknie graficznym i naciśnij 1 (zapamiętaj widok). Generowanie: K.",
                           "Set up the model in the graphics window and press 1 (remember view). Generate: K."))
        if not self.bridge.available:
            self.set_status(tr("Tryb offline – brak połączenia z HyperMesh. Działa edytor układu slajdów, sesje i eksport PPTX.",
                               "Offline mode – HyperMesh not connected. The layout editor, sessions and PPTX export still work."), "warn")

    def _header(self) -> QtWidgets.QFrame:
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("Header")
        lay = QtWidgets.QHBoxLayout(hdr)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(14)
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(0)
        t = QtWidgets.QLabel(tr("HyperMesh – zrzuty ekranu i raport jakości siatki", "HyperMesh – screenshots & mesh quality report"))
        t.setObjectName("Title")
        s = QtWidgets.QLabel(tr("Zapamiętaj widoki → wybierz metryki → generuj → prezentacja PPTX (REF vs INF)",
                                "Remember views → pick metrics → generate → PPTX deck (REF vs INF)"))
        s.setObjectName("Subtitle")
        titles.addWidget(t)
        titles.addWidget(s)
        lay.addLayout(titles, 1)

        mode = self.bridge.describe()
        self.conn_badge = badge(("● " + mode) if self.bridge.available else ("○ " + tr("offline", "offline")),
                                "ok" if self.bridge.mode == "hm" else ("warn" if self.bridge.mode == "demo" else "muted"))
        self.conn_badge.setToolTip("\n".join(self.bridge.log[-6:]) or tr("Brak połączenia", "Not connected"))
        lay.addWidget(self.conn_badge)

        self.cb_compare = QtWidgets.QCheckBox(tr("Porównanie REF / INF", "REF / INF comparison"))
        self.cb_compare.setChecked(self.project.settings.comparison)
        self.cb_compare.setToolTip(tr("Tryb analizy porównawczej: faza REF (model referencyjny) i faza INF (model influencyjny) w jednej prezentacji",
                                      "Comparison mode: REF (reference) and INF (influence) phases in one presentation"))
        self.cb_compare.setStyleSheet("color: #F9FAFB; font-weight: 600;")
        self.cb_compare.toggled.connect(self._on_compare)
        lay.addWidget(self.cb_compare)
        self.phase = Segmented([(ROLE_REF, "REF"), (ROLE_INF, "INF")])
        self.phase.set_value(self.project.settings.phase)
        self.phase.changed.connect(self._on_phase)
        self.phase.setToolTip(tr("Aktywna faza: do niej trafią kolejne zrzuty", "Active phase: the next screenshots go there"))
        lay.addWidget(self.phase)

        self.lang = Segmented([("pl", "PL"), ("en", "EN")])
        self.lang.set_value(get_lang())
        self.lang.changed.connect(self._on_lang)
        lay.addWidget(self.lang)
        theme_btn = button("☾" if not self.dark else "☀", "ghost", tr("Przełącz motyw jasny / ciemny", "Toggle light / dark theme"), self._toggle_theme)
        theme_btn.setStyleSheet("color: #F9FAFB; font-size: 13pt;")
        lay.addWidget(theme_btn)
        help_btn = button("?", "ghost", tr("Pomoc", "Help"), self.show_help)
        help_btn.setStyleSheet("color: #F9FAFB; font-weight: 700;")
        lay.addWidget(help_btn)
        return hdr

    def _views_panel(self) -> QtWidgets.QWidget:
        card = Card()
        card.setMinimumWidth(TILE_W + 64)
        tb = FlowLayout(h_spacing=6, v_spacing=6)
        self.btn_remember = button(tr("● Zapamiętaj widok  (1)", "● Remember view  (1)"), "primary",
                                   tr("Zapisuje bieżącą kamerę z miniaturą", "Stores the current camera with a thumbnail"), self.remember_view)
        tb.addWidget(self.btn_remember)
        tb.addWidget(button(tr("Zaznacz wsz.", "Select all"), "small", "", lambda: self.select_all(True)))
        tb.addWidget(button(tr("Odznacz wsz.", "Deselect all"), "small", "", lambda: self.select_all(False)))
        tb.addWidget(button(tr("Dodaj z tekstu…", "Add from text…"), "small", "", self.add_from_text))
        self.btn_rec = button(tr("● Nagrywaj układ", "● Record layout"), "small",
                              tr("Nagrywa komendy układu wyświetlania z command.tcl i dołącza je do kolejnych zapamiętanych widoków",
                                 "Records display-layout commands from command.tcl and attaches them to the next remembered views"),
                              self.toggle_record)
        tb.addWidget(self.btn_rec)
        tb.addWidget(button(tr("Wyczyść", "Clear"), "danger", tr("Usuń wszystkie widoki", "Remove all views"), self.clear_views))
        card.body.addLayout(tb)
        self.count_lab = QtWidgets.QLabel()
        self.count_lab.setObjectName("Muted")
        card.body.addWidget(self.count_lab)
        card.body.addWidget(hline())

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tiles_host = QtWidgets.QWidget()
        self.flow = FlowLayout(self.tiles_host, margin=2, h_spacing=10, v_spacing=10)
        self.scroll.setWidget(self.tiles_host)
        card.body.addWidget(self.scroll, 1)
        self.empty_lab = QtWidgets.QLabel(tr("Brak widoków.\nUstaw model w oknie graficznym HyperMesh i kliknij „Zapamiętaj widok” (klawisz 1).",
                                             "No views yet.\nSet up the model in the HyperMesh graphics window and click “Remember view” (key 1)."))
        self.empty_lab.setObjectName("Muted")
        self.empty_lab.setAlignment(Qt.AlignCenter)
        card.body.addWidget(self.empty_lab)
        return card

    def _settings_panel(self) -> QtWidgets.QWidget:
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._tab_output(), tr("Zapis", "Output"))
        self.tabs.addTab(self._tab_pptx(), tr("Prezentacja", "Presentation"))
        self.metrics_panel = MetricsPanel(self.project)
        self.metrics_panel.changed.connect(self._on_metrics_changed)
        self.metrics_panel.learn_requested.connect(self.learn_metric)
        self.metrics_panel.test_requested.connect(self.test_metric)
        mp = QtWidgets.QWidget()
        ml = QtWidgets.QVBoxLayout(mp)
        ml.setContentsMargins(12, 12, 12, 12)
        ml.addWidget(self.metrics_panel)
        self.tabs.addTab(mp, tr("Metryki", "Metrics"))
        self.tabs.addTab(self._tab_session(), tr("Sesja", "Session"))
        return self.tabs

    def _scroll_tab(self) -> tuple:
        sa = QtWidgets.QScrollArea()
        sa.setWidgetResizable(True)
        host = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(host)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        sa.setWidget(host)
        return sa, lay

    def _tab_output(self) -> QtWidgets.QWidget:
        s = self.project.settings
        sa, lay = self._scroll_tab()
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(10)
        row = QtWidgets.QHBoxLayout()
        self.ed_dir = QtWidgets.QLineEdit(s.out_dir)
        self.ed_dir.setPlaceholderText(tr("Folder główny zrzutów (podfoldery: metryka lub nazwa widoku)", "Root screenshot folder (subfolders: metric or view name)"))
        self.ed_dir.editingFinished.connect(lambda: self._set("out_dir", self.ed_dir.text().strip()))
        row.addWidget(self.ed_dir, 1)
        row.addWidget(button(tr("Wybierz…", "Browse…"), "", "", self.pick_dir))
        form.addRow(tr("Folder zrzutów:", "Screenshot folder:"), row)
        self.cb_modeldir = QtWidgets.QCheckBox(tr("Zapisuj w folderze otwartego modelu (.hm)", "Save in the open model's folder (.hm)"))
        self.cb_modeldir.setChecked(s.use_model_dir)
        self.cb_modeldir.toggled.connect(lambda v: self._set("use_model_dir", bool(v)))
        form.addRow("", self.cb_modeldir)
        self.cmb_fmt = QtWidgets.QComboBox()
        self.cmb_fmt.addItems(["jpg", "png", "bmp"])
        self.cmb_fmt.setCurrentText(s.fmt)
        self.cmb_fmt.currentTextChanged.connect(lambda v: self._set("fmt", v))
        fr = QtWidgets.QHBoxLayout()
        fr.addWidget(self.cmb_fmt)
        self.cb_overwrite = QtWidgets.QCheckBox(tr("Nadpisuj istniejące pliki (inaczej numeruj _2, _3…)", "Overwrite existing files (otherwise number _2, _3…)"))
        self.cb_overwrite.setChecked(s.overwrite)
        self.cb_overwrite.toggled.connect(lambda v: self._set("overwrite", bool(v)))
        fr.addWidget(self.cb_overwrite, 1)
        form.addRow(tr("Format:", "Format:"), fr)
        self.ed_pat_m = QtWidgets.QLineEdit(s.pattern_metric)
        self.ed_pat_m.editingFinished.connect(lambda: self._set("pattern_metric", self.ed_pat_m.text().strip() or "{metric}_{phase}_{view}"))
        form.addRow(tr("Nazwa (z metryką):", "Name (with metric):"), self.ed_pat_m)
        self.ed_pat_p = QtWidgets.QLineEdit(s.pattern_plain)
        self.ed_pat_p.editingFinished.connect(lambda: self._set("pattern_plain", self.ed_pat_p.text().strip() or "{view}_{phase}"))
        form.addRow(tr("Nazwa (bez metryki):", "Name (plain):"), self.ed_pat_p)
        tags = QtWidgets.QHBoxLayout()
        self.ed_tag_ref = QtWidgets.QLineEdit(s.tag_ref)
        self.ed_tag_ref.setFixedWidth(70)
        self.ed_tag_ref.editingFinished.connect(lambda: self._set("tag_ref", self.ed_tag_ref.text().strip() or "REF"))
        self.ed_tag_inf = QtWidgets.QLineEdit(s.tag_inf)
        self.ed_tag_inf.setFixedWidth(70)
        self.ed_tag_inf.editingFinished.connect(lambda: self._set("tag_inf", self.ed_tag_inf.text().strip() or "INF"))
        tags.addWidget(QtWidgets.QLabel("REF:"))
        tags.addWidget(self.ed_tag_ref)
        tags.addWidget(QtWidgets.QLabel("INF:"))
        tags.addWidget(self.ed_tag_inf)
        tags.addStretch(1)
        form.addRow(tr("Znaczniki faz:", "Phase tags:"), tags)
        lay.addLayout(form)
        lay.addWidget(hint_label(tr(
            "Zrzut z metryką: folder „<Metryka>”, plik „<Metryka>_<faza>_<widok>.<fmt>” (prefiks = metryka). "
            "Zrzut bez metryki: folder „<Widok>”, plik „<Widok>_<faza>”. Dostępne znaczniki: {metric} {view} {phase}.",
            "Metric shot: folder “<Metric>”, file “<Metric>_<phase>_<view>.<fmt>” (prefix = metric). "
            "Plain shot: folder “<View>”, file “<View>_<phase>”. Tokens: {metric} {view} {phase}.")))
        lay.addWidget(hline())

        form2 = QtWidgets.QFormLayout()
        form2.setHorizontalSpacing(10)
        self.cmb_bg = QtWidgets.QComboBox()
        for val, (pl, en) in BACKGROUNDS:
            self.cmb_bg.addItem(tr(pl, en), val)
        self.cmb_bg.setCurrentIndex(max(0, [v for v, _ in BACKGROUNDS].index(s.background) if s.background in [v for v, _ in BACKGROUNDS] else 0))
        self.cmb_bg.currentIndexChanged.connect(lambda _i: self._set("background", self.cmb_bg.currentData() or ""))
        form2.addRow(tr("Tło zrzutu:", "Screenshot background:"), self.cmb_bg)
        self.cb_hq = QtWidgets.QCheckBox(tr("Wysoka jakość (antyaliasing + maks. JPEG, jeśli HM to udostępnia)", "High quality (anti-aliasing + max JPEG where HM exposes it)"))
        self.cb_hq.setChecked(s.high_quality)
        self.cb_hq.toggled.connect(lambda v: self._set("high_quality", bool(v)))
        form2.addRow("", self.cb_hq)
        self.cb_stored = QtWidgets.QCheckBox(tr("Zwykłe zrzuty: użyj klatki zapisanej przy „Zapamiętaj widok” (WYSIWYG)", "Plain shots: use the frame stored at “Remember view” (WYSIWYG)"))
        self.cb_stored.setChecked(s.use_stored_frames)
        self.cb_stored.toggled.connect(lambda v: self._set("use_stored_frames", bool(v)))
        form2.addRow("", self.cb_stored)
        self.cb_disp = QtWidgets.QCheckBox(tr("Odtwarzaj nagrany układ wyświetlania przed zrzutem", "Replay the recorded display layout before the shot"))
        self.cb_disp.setChecked(s.replay_disp)
        self.cb_disp.toggled.connect(lambda v: self._set("replay_disp", bool(v)))
        form2.addRow("", self.cb_disp)
        self.sp_settle = QtWidgets.QSpinBox()
        self.sp_settle.setRange(0, 5000)
        self.sp_settle.setSingleStep(50)
        self.sp_settle.setSuffix(" ms")
        self.sp_settle.setValue(s.settle_ms)
        self.sp_settle.valueChanged.connect(lambda v: self._set("settle_ms", int(v)))
        form2.addRow(tr("Czas na przerysowanie:", "Redraw settle time:"), self.sp_settle)
        lay.addLayout(form2)
        lay.addStretch(1)
        return sa

    def _tab_pptx(self) -> QtWidgets.QWidget:
        s = self.project.settings
        host = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(host)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(10)
        row = QtWidgets.QHBoxLayout()
        self.ed_pptx = QtWidgets.QLineEdit(s.pptx_path)
        self.ed_pptx.setPlaceholderText(tr("(domyślnie: <folder zrzutów>/raport_siatki.pptx)", "(default: <screenshot folder>/raport_siatki.pptx)"))
        self.ed_pptx.editingFinished.connect(lambda: self._set("pptx_path", self.ed_pptx.text().strip()))
        row.addWidget(self.ed_pptx, 1)
        row.addWidget(button(tr("Wybierz…", "Browse…"), "", "", self.pick_pptx))
        form.addRow(tr("Plik PPTX:", "PPTX file:"), row)
        opts = FlowLayout(h_spacing=10, v_spacing=4)
        self.cb_pptx_auto = QtWidgets.QCheckBox(tr("Aktualizuj po generowaniu", "Update after generating"))
        self.cb_pptx_auto.setChecked(s.pptx_auto)
        self.cb_pptx_auto.toggled.connect(lambda v: self._set("pptx_auto", bool(v)))
        self.cb_titles = QtWidgets.QCheckBox(tr("Tytuły slajdów", "Slide titles"))
        self.cb_titles.setChecked(s.pptx_slide_titles)
        self.cb_titles.toggled.connect(lambda v: (self._set("pptx_slide_titles", bool(v)), self.layout_editor.rebuild()))
        self.cb_caps = QtWidgets.QCheckBox(tr("Podpisy REF/INF", "REF/INF captions"))
        self.cb_caps.setChecked(s.pptx_captions)
        self.cb_caps.toggled.connect(lambda v: (self._set("pptx_captions", bool(v)), self.layout_editor.rebuild()))
        self.cb_title_slide = QtWidgets.QCheckBox(tr("Slajd tytułowy:", "Title slide:"))
        self.cb_title_slide.setChecked(s.pptx_title_slide)
        self.cb_title_slide.toggled.connect(lambda v: self._set("pptx_title_slide", bool(v)))
        self.ed_title = QtWidgets.QLineEdit(s.pptx_title)
        self.ed_title.editingFinished.connect(lambda: self._set("pptx_title", self.ed_title.text().strip()))
        self.ed_title.setMinimumWidth(220)
        for w in (self.cb_pptx_auto, self.cb_titles, self.cb_caps, self.cb_title_slide, self.ed_title):
            opts.addWidget(w)
        form.addRow(tr("Opcje:", "Options:"), opts)
        lay.addLayout(form)
        self.layout_editor = LayoutEditor(self.project)
        self.layout_editor.layout_changed.connect(self._schedule_autosave)
        self.layout_editor.status.connect(self.set_status)
        lay.addWidget(self.layout_editor, 1)
        br = QtWidgets.QHBoxLayout()
        br.addStretch(1)
        br.addWidget(button(tr("Zapisz prezentację teraz", "Write the presentation now"), "primary",
                            tr("Buduje PPTX z aktualnych zrzutów i układu (bez robienia nowych zrzutów)",
                               "Builds the PPTX from the current screenshots and layout (no new captures)"), self.write_pptx_now))
        lay.addLayout(br)
        return host

    def _tab_session(self) -> QtWidgets.QWidget:
        sa, lay = self._scroll_tab()
        self.session_lab = QtWidgets.QLabel()
        self.session_lab.setObjectName("Muted")
        self.session_lab.setWordWrap(True)
        lay.addWidget(self.session_lab)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button(tr("Nowa sesja", "New session"), "", "", self.new_session))
        row.addWidget(button(tr("Wczytaj sesję…", "Load session…"), "", "", self.load_session))
        row.addWidget(button(tr("Zapisz", "Save"), "primary", "Ctrl+S", self.save_session))
        row.addWidget(button(tr("Zapisz jako…", "Save as…"), "", "", lambda: self.save_session(True)))
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint_label(tr(
            "Sesja (plik .hmshots.json) zawiera widoki z miniaturami, ustawienia metryk, układ slajdu i listę wykonanych zrzutów. "
            "Przebieg REF → INF: zrób zrzuty REF, zapisz sesję, wczytaj model INF (ten sam HyperMesh lub później), "
            "wczytaj sesję, przełącz fazę na INF i generuj – te same widoki i metryki trafią do tej samej prezentacji.",
            "A session (.hmshots.json) holds the views with thumbnails, metric settings, slide layout and the list of taken screenshots. "
            "REF → INF flow: take the REF shots, save the session, load the INF model (same HyperMesh or later), load the session, "
            "switch the phase to INF and generate – the same views and metrics land in the same presentation.")))
        lay.addWidget(hline())
        form = QtWidgets.QFormLayout()
        self.lab_model_ref = QtWidgets.QLabel("–")
        self.lab_model_inf = QtWidgets.QLabel("–")
        form.addRow(tr("Model REF:", "REF model:"), self.lab_model_ref)
        form.addRow(tr("Model INF:", "INF model:"), self.lab_model_inf)
        crow = QtWidgets.QHBoxLayout()
        self.ed_cmdfile = QtWidgets.QLineEdit(self.project.settings.command_file)
        self.ed_cmdfile.setPlaceholderText(tr("(auto: command.tcl w folderze roboczym HyperMesh)", "(auto: command.tcl in the HyperMesh working folder)"))
        self.ed_cmdfile.editingFinished.connect(self._on_cmdfile)
        crow.addWidget(self.ed_cmdfile, 1)
        crow.addWidget(button(tr("…", "…"), "small", "", self.pick_cmdfile))
        form.addRow(tr("Plik komend HM:", "HM command file:"), crow)
        lay.addLayout(form)
        lay.addWidget(hline())
        lay.addWidget(QtWidgets.QLabel(tr("Wykonane zrzuty (dla prezentacji):", "Taken screenshots (used by the deck):")))
        self.out_table = QtWidgets.QTableWidget(0, 4)
        self.out_table.setHorizontalHeaderLabels([tr("Faza", "Phase"), tr("Widok", "View"), tr("Rodzaj", "Kind"), tr("Plik", "File")])
        self.out_table.horizontalHeader().setStretchLastSection(True)
        self.out_table.verticalHeader().setVisible(False)
        self.out_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.out_table.setMinimumHeight(160)
        lay.addWidget(self.out_table, 1)
        orow = QtWidgets.QHBoxLayout()
        orow.addWidget(button(tr("Usuń wyniki REF", "Forget REF results"), "small", "", lambda: self.forget_outputs(ROLE_REF)))
        orow.addWidget(button(tr("Usuń wyniki INF", "Forget INF results"), "small", "", lambda: self.forget_outputs(ROLE_INF)))
        orow.addWidget(button(tr("Otwórz folder zrzutów", "Open screenshot folder"), "small", "", self.open_out_dir))
        orow.addStretch(1)
        lay.addLayout(orow)
        self.refresh_session_tab()
        return sa

    def _bottom_bar(self) -> QtWidgets.QWidget:
        host = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        row = QtWidgets.QHBoxLayout()
        self.btn_generate = button(tr("▶  Generuj zrzuty  (K)", "▶  Generate screenshots  (K)"), "success",
                                   tr("Zrzuty dla zaznaczonych widoków i wybranych metryk; foldery wg metryk; aktualizacja PPTX",
                                      "Screenshots for the selected views and metrics; folders per metric; PPTX update"), self.generate)
        row.addWidget(self.btn_generate)
        self.btn_cancel = button(tr("Przerwij", "Cancel"), "danger", "", self.cancel_generate)
        self.btn_cancel.setEnabled(False)
        row.addWidget(self.btn_cancel)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        row.addWidget(self.progress, 1)
        self.btn_log = button(tr("Dziennik ▾", "Log ▾"), "ghost", "", self.toggle_log)
        row.addWidget(self.btn_log)
        lay.addLayout(row)
        self.status_lab = QtWidgets.QLabel("")
        self.status_lab.setObjectName("Status")
        self.status_lab.setWordWrap(True)
        lay.addWidget(self.status_lab)
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setObjectName("Log")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(2000)
        self.log_box.setFixedHeight(130)
        self.log_box.setVisible(False)
        lay.addWidget(self.log_box)
        return host

    # ============================================================ helpers
    def _set(self, key: str, value) -> None:
        setattr(self.project.settings, key, value)
        self.project.dirty = True
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        self._autosave_timer.start()

    def set_status(self, msg: str, kind: str = "") -> None:
        self.status_lab.setText(msg)
        self.status_lab.setObjectName({"ok": "StatusOk", "err": "StatusErr", "warn": "StatusWarn"}.get(kind, "Status"))
        repolish(self.status_lab)
        if msg:
            self.log(msg)

    def log(self, msg: str) -> None:
        if hasattr(self, "log_box"):
            self.log_box.appendPlainText(msg)

    def toggle_log(self) -> None:
        vis = not self.log_box.isVisible()
        self.log_box.setVisible(vis)
        self.btn_log.setText(tr("Dziennik ▴", "Log ▴") if vis else tr("Dziennik ▾", "Log ▾"))

    def _progress(self, i: int, n: int, label: str) -> None:
        self.progress.setValue(int(100 * i / n) if n else 0)
        if label:
            self.status_lab.setText(tr("Zrzut %d / %d: %s", "Shot %d / %d: %s") % (i + 1, n, label))
        process_events()

    # ============================================================== tiles
    def rebuild_tiles(self) -> None:
        self.flow.clear()
        self.tiles = {}
        for rec in self.project.views:
            self._add_tile(rec)
        self.update_count()

    def _add_tile(self, rec: ViewRecord) -> ViewTile:
        tile = ViewTile(rec, self.project.metrics)
        tile.changed.connect(self._on_tile_changed)
        tile.test_requested.connect(self.test_view)
        tile.refresh_requested.connect(self.refresh_thumb)
        tile.delete_requested.connect(self.delete_view)
        tile.duplicate_requested.connect(self.duplicate_view)
        tile.edit_requested.connect(self.edit_view)
        tile.move_requested.connect(self.move_view)
        tile.copy_requested.connect(self.copy_view)
        self.flow.addWidget(tile)
        self.tiles[rec.id] = tile
        return tile

    def update_count(self) -> None:
        n = len(self.project.views)
        sel = len(self.project.views.selected())
        jobs = len(self.project.shot_jobs())
        self.count_lab.setText(tr("Zaznaczono %d / %d widoków · zrzutów do wykonania: %d", "Selected %d / %d views · shots to take: %d") % (sel, n, jobs))
        self.empty_lab.setVisible(n == 0)
        self.scroll.setVisible(n > 0)

    def _on_tile_changed(self) -> None:
        self.project.dirty = True
        self.update_count()
        self.layout_editor.rebuild()
        self._schedule_autosave()

    def _on_metrics_changed(self) -> None:
        for tile in self.tiles.values():
            tile.rebuild_metrics()
        self.update_count()
        self.layout_editor.rebuild()
        self._schedule_autosave()

    # ============================================================= actions
    def remember_view(self) -> None:
        if not self.bridge.available:
            self.set_status(tr("Tryb offline – nie można pobrać widoku z HyperMesh.", "Offline mode – cannot read the view from HyperMesh."), "err")
            return
        rec = self.generator.remember_view()
        if rec is None:
            self.set_status(tr("Nie udało się pobrać widoku. Czy okno graficzne HyperMesh jest aktywne?",
                               "Could not read the view. Is the HyperMesh graphics window active?"), "err")
            return
        self._add_tile(rec)
        self.update_count()
        QtCore.QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
        extra = tr(" + układ (%d komend)", " + layout (%d cmds)") % len(rec.disp.splitlines()) if rec.disp else ""
        thumb = tr("tak", "yes") if rec.thumb_b64 else tr("nie", "no")
        self.set_status(tr("Zapamiętano „%s”%s. Miniatura: %s. Widoków: %d.", "Remembered “%s”%s. Thumbnail: %s. Views: %d.")
                        % (rec.name, extra, thumb, len(self.project.views)), "ok")
        self.layout_editor.rebuild()
        self._schedule_autosave()

    def select_all(self, flag: bool) -> None:
        self.project.views.set_all_selected(flag)
        for t in self.tiles.values():
            t.sel.setChecked(flag)
        self.update_count()

    def test_view(self, view_id: int) -> None:
        rec = self.project.views.get(view_id)
        if rec is None:
            return
        if not self.bridge.available:
            self.set_status(tr("Tryb offline.", "Offline mode."), "warn")
            return
        ok = self.generator.apply_view(rec)
        self.set_status(tr("Ustawiono widok „%s”.", "Applied view “%s”.") % rec.name if ok else
                        tr("Nie udało się ustawić widoku „%s”.", "Could not apply view “%s”.") % rec.name, "ok" if ok else "err")

    def refresh_thumb(self, view_id: int) -> None:
        rec = self.project.views.get(view_id)
        if rec is None or not self.bridge.available:
            return
        ok = self.generator.refresh_thumbnail(rec)
        tile = self.tiles.get(view_id)
        if tile:
            tile.update_thumbnail()
            tile.refresh_badges()
        self.set_status(tr("Miniatura odświeżona.", "Thumbnail refreshed.") if ok else tr("Nie udało się odświeżyć miniatury.", "Could not refresh the thumbnail."), "ok" if ok else "err")
        self._schedule_autosave()

    def delete_view(self, view_id: int) -> None:
        rec = self.project.views.get(view_id)
        if rec is None:
            return
        self.project.views.remove(view_id)
        tile = self.tiles.pop(view_id, None)
        if tile:
            self.flow.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        self.update_count()
        self.layout_editor.rebuild()
        self.set_status(tr("Usunięto „%s”. Pozostało: %d.", "Deleted “%s”. Remaining: %d.") % (rec.name, len(self.project.views)))
        self._schedule_autosave()

    def duplicate_view(self, view_id: int) -> None:
        rec = self.project.views.duplicate(view_id)
        if rec is None:
            return
        self.rebuild_tiles()
        self.layout_editor.rebuild()
        self._schedule_autosave()

    def move_view(self, view_id: int, delta: int) -> None:
        if self.project.views.move(view_id, delta):
            self.rebuild_tiles()
            self.layout_editor.rebuild()
            self._schedule_autosave()

    def copy_view(self, view_id: int) -> None:
        rec = self.project.views.get(view_id)
        if rec is None:
            return
        QtWidgets.QApplication.clipboard().setText(rec.view_text)
        self.set_status(tr("Skopiowano dane widoku do schowka.", "View data copied to the clipboard."), "ok")

    def edit_view(self, view_id: int) -> None:
        rec = self.project.views.get(view_id)
        if rec is None:
            return
        dlg = EditViewDialog(rec, self)
        if not run_dialog(dlg):
            return
        rec.name = dlg.name.text().strip() or rec.name
        lists = dlg.view_lists()
        if lists:
            rec.view = lists[0][:20]
        rec.disp = dlg.disp.toPlainText().strip()
        tile = self.tiles.get(view_id)
        if tile:
            tile.refresh_from_record()
        self.layout_editor.rebuild()
        self._schedule_autosave()

    def add_from_text(self) -> None:
        dlg = EditViewDialog(None, self)
        if not run_dialog(dlg):
            return
        lists = dlg.view_lists()
        if not lists:
            warn(self, tr("Brak danych", "No data"), tr("Nie znaleziono co najmniej 16 liczb kamery.", "No camera line with at least 16 numbers found."))
            return
        base = dlg.name.text().strip()
        for i, nums in enumerate(lists):
            name = base if (base and len(lists) == 1) else ("%s %d" % (base, i + 1) if base else "")
            rec = self.project.views.add(nums[:20], name=name, disp=dlg.disp.toPlainText().strip())
            self._add_tile(rec)
        self.update_count()
        self.layout_editor.rebuild()
        self.set_status(tr("Dodano %d widok(ów) z tekstu.", "Added %d view(s) from text.") % len(lists), "ok")
        self._schedule_autosave()

    def clear_views(self) -> None:
        if not self.project.views or not confirm(self, tr("Wyczyść", "Clear"), tr("Usunąć wszystkie zapamiętane widoki?", "Remove all remembered views?")):
            return
        self.project.views.clear()
        self.rebuild_tiles()
        self.layout_editor.rebuild()
        self.set_status(tr("Wyczyszczono widoki.", "Views cleared."))
        self._schedule_autosave()

    def toggle_record(self) -> None:
        rec = self.generator.recorder
        if rec.active:
            rec.stop()
            self.btn_rec.setText(tr("● Nagrywaj układ", "● Record layout"))
            self.btn_rec.setProperty("kind", "small")
            repolish(self.btn_rec)
            self.set_status(tr("Nagrywanie układu zakończone.", "Layout recording stopped."))
            return
        rec.override = self.project.settings.command_file
        if not rec.start():
            self.set_status(tr("Nie znaleziono pliku komend HyperMesh (command.tcl). Wskaż go w zakładce „Sesja”.",
                               "HyperMesh command file (command.tcl) not found. Set it in the “Session” tab."), "err")
            return
        self.btn_rec.setText(tr("■ Zakończ nagrywanie", "■ Stop recording"))
        self.btn_rec.setProperty("kind", "rec")
        repolish(self.btn_rec)
        self.set_status(tr("Nagrywanie układu: wykonaj zmiany w HM (sekcje, maskowanie, style), potem „Zapamiętaj widok”. Plik: %s",
                           "Recording layout: make display changes in HM (sections, masking, styles), then “Remember view”. File: %s") % rec.path, "ok")

    # ------------------------------------------------------------ generate
    def generate(self) -> None:
        if not self.bridge.available:
            self.set_status(tr("Tryb offline – zrzuty wymagają HyperMesh. Prezentację można zapisać w zakładce „Prezentacja”.",
                               "Offline mode – screenshots need HyperMesh. The deck can still be written in the “Presentation” tab."), "err")
            return
        if not self.project.shot_jobs():
            self.set_status(tr("Zaznacz widoki i wybierz rodzaje zrzutów (zwykły / metryki).", "Select views and choose shot kinds (plain / metrics)."), "err")
            return
        if not self.generator.resolve_out_dir():
            self.pick_dir()
            if not self.project.settings.out_dir:
                return
        self.btn_generate.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(0)
        phase = self.project.current_phase()
        self.log("=== %s ===" % (tr("Generowanie – faza %s", "Generating – phase %s") % phase if phase else tr("Generowanie", "Generating")))
        try:
            res = self.generator.run()
        finally:
            self.btn_generate.setEnabled(True)
            self.btn_cancel.setEnabled(False)
        self.layout_editor.invalidate_images()
        self.layout_editor.rebuild()
        for t in self.tiles.values():
            t.refresh_badges()
        self.refresh_session_tab()
        kind = "ok" if res.ok and not res.failed and not res.errors else ("warn" if res.ok else "err")
        msg = res.summary()
        if res.errors:
            msg += " · " + "; ".join(res.errors[:3])
        self.set_status(msg, kind)
        self.autosave()

    def cancel_generate(self) -> None:
        self.generator.cancel = True
        self.set_status(tr("Przerywanie…", "Cancelling…"), "warn")

    def write_pptx_now(self) -> None:
        if not self.project.settings.pptx_path:
            self.pick_pptx()
            if not self.project.settings.pptx_path:
                return
        try:
            path = self.generator.write_pptx()
        except Exception as exc:  # noqa: BLE001
            self.set_status(tr("Błąd zapisu PPTX: %s", "PPTX write error: %s") % exc, "err")
            return
        self.set_status(tr("Prezentacja zapisana: %s", "Presentation saved: %s") % path, "ok")

    # ------------------------------------------------------------- metrics
    def learn_metric(self, key: str) -> None:
        m = self.project.metrics.get(key)
        if m is None:
            return
        rec = CommandRecorder(self.bridge, self.project.settings.command_file)
        if not rec.start():
            warn(self, tr("Brak pliku komend", "No command file"),
                 tr("Nie znaleziono command.tcl. Wskaż plik komend HyperMesh w zakładce „Sesja”.",
                    "command.tcl not found. Set the HyperMesh command file in the “Session” tab."))
            return
        dlg = LearnMetricDialog(m.name, m.default_threshold, self)
        ok = run_dialog(dlg)
        lines = rec.stop()
        if not ok:
            return
        recipe = self.project.metrics.learn_recipe(lines, dlg.thr.value())
        if not recipe:
            warn(self, tr("Nic nie nagrano", "Nothing recorded"),
                 tr("W pliku komend nie pojawiły się nowe komendy. Wykonaj kontrolę w HyperMesh i spróbuj ponownie.",
                    "No new commands appeared in the command file. Perform the check in HyperMesh and try again."))
            return
        m.recipe = recipe
        self.metrics_panel.refresh_current()
        self.project.dirty = True
        self._schedule_autosave()
        self.set_status(tr("Nagrano %d komend dla metryki „%s” (próg → {thr}).", "Recorded %d commands for metric “%s” (limit → {thr}).")
                        % (len(recipe), m.name), "ok")

    def test_metric(self, key: str) -> None:
        m = self.project.metrics.get(key)
        if m is None:
            return
        if not self.bridge.available:
            self.set_status(tr("Tryb offline.", "Offline mode."), "warn")
            return
        cmds = self.project.metrics.commands_for(key, m.default_threshold, True)
        ok, failed, errors = self.bridge.run_lines("\n".join(cmds))
        self.bridge.redraw()
        for e in errors:
            self.log("   " + e)
        self.set_status(tr("Test metryki „%s”: %d OK, %d błędów (komendy porządkujące NIE zostały wykonane – obejrzyj wynik).",
                           "Metric test “%s”: %d OK, %d errors (cleanup NOT run – inspect the result).") % (m.name, ok, failed),
                        "ok" if not failed else "warn")

    # -------------------------------------------------------------- phases
    def refresh_phase_ui(self) -> None:
        s = self.project.settings
        self.phase.setVisible(s.comparison)
        self.phase.set_value(s.phase)
        self.phase.set_labels({ROLE_REF: s.tag_ref, ROLE_INF: s.tag_inf})
        tag = s.phase_tag(s.phase)
        self.btn_generate.setText((tr("▶  Generuj zrzuty %s  (K)", "▶  Generate %s screenshots  (K)") % tag) if tag else tr("▶  Generuj zrzuty  (K)", "▶  Generate screenshots  (K)"))

    def _on_compare(self, on: bool) -> None:
        self._set("comparison", bool(on))
        lay = self.project.layout
        if on and not lay.comparison:
            lay.apply_left_right(1, True)
        elif not on and lay.comparison:
            lay.apply_grid(1)
        self.refresh_phase_ui()
        self.layout_editor.rebuild()
        self.update_count()

    def _on_phase(self, phase: str) -> None:
        self._set("phase", phase)
        self.refresh_phase_ui()
        self.layout_editor.rebuild()
        self.set_status(tr("Aktywna faza: %s – kolejne zrzuty trafią do slotów %s.", "Active phase: %s – the next screenshots go to the %s slots.")
                        % (self.project.settings.phase_tag(phase), phase), "ok")

    def _on_lang(self, lang: str) -> None:
        if lang == get_lang():
            return
        set_lang(lang)
        self.project.settings.lang = lang
        self.rebuild_all()

    def _toggle_theme(self) -> None:
        self.dark = not self.dark
        self.apply_theme()
        self.rebuild_all()

    def rebuild_all(self) -> None:
        """Rebuild the whole UI from project state (language / theme switch)."""
        was_recording = self.generator.recorder.active
        self.build_ui()
        if was_recording:
            self.btn_rec.setText(tr("■ Zakończ nagrywanie", "■ Stop recording"))
            self.btn_rec.setProperty("kind", "rec")
            repolish(self.btn_rec)

    # ------------------------------------------------------------ sessions
    def refresh_session_tab(self) -> None:
        p = self.project
        self.session_lab.setText(tr("Plik sesji: %s", "Session file: %s") % (p.path or tr("(niezapisana – działa autozapis)", "(unsaved – autosave active)")))
        self.lab_model_ref.setText(p.model_files.get(ROLE_REF) or "–")
        self.lab_model_inf.setText(p.model_files.get(ROLE_INF) or "–")
        self.out_table.setRowCount(0)
        for o in p.outputs:
            r = self.out_table.rowCount()
            self.out_table.insertRow(r)
            kind = o.metric_label or tr("zwykły", "plain")
            if o.threshold is not None:
                kind += " (%g)" % o.threshold
            for c, txt in enumerate((o.phase or "–", o.view_name, kind, o.path if o.ok else "✖ " + o.error)):
                it = QtWidgets.QTableWidgetItem(txt)
                it.setToolTip(txt)
                self.out_table.setItem(r, c, it)
        self.out_table.resizeColumnsToContents()

    def forget_outputs(self, phase: str) -> None:
        if not confirm(self, tr("Usuń wyniki", "Forget results"), tr("Usunąć z sesji wyniki fazy %s? (pliki na dysku zostają)", "Forget the %s results in the session? (files stay on disk)") % phase):
            return
        self.project.outputs = [o for o in self.project.outputs if o.phase != phase]
        self.project.dirty = True
        self.refresh_session_tab()
        self.layout_editor.rebuild()
        self._schedule_autosave()

    def new_session(self) -> None:
        if self.project.views and not confirm(self, tr("Nowa sesja", "New session"), tr("Odrzucić bieżącą listę widoków i wyniki?", "Discard the current views and results?")):
            return
        keep = self.project.settings
        self.project = Project()
        self.project.settings = keep
        self.project.outputs = []
        self.project.model_files = {ROLE_REF: "", ROLE_INF: ""}
        self.generator = Generator(self.project, self.bridge, log=self.log, progress=self._progress, pump=process_events)
        self.rebuild_all()
        self.set_status(tr("Nowa sesja.", "New session."))

    def load_session(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Wczytaj sesję", "Load session"),
                                                        self.project.settings.out_dir or os.path.expanduser("~"),
                                                        "HM Shots session (*.hmshots.json *.json)")
        if not path:
            return
        self.load_session_file(path)

    def load_session_file(self, path: str) -> bool:
        try:
            proj = Project.load(path)
        except (OSError, ValueError, KeyError) as exc:
            warn(self, tr("Błąd", "Error"), tr("Nie można wczytać sesji: %s", "Cannot load session: %s") % exc)
            return False
        self.project = proj
        set_lang(proj.settings.lang)
        self.dark = proj.settings.theme == "dark"
        self.apply_theme()
        self.generator = Generator(self.project, self.bridge, log=self.log, progress=self._progress, pump=process_events)
        self.rebuild_all()
        self.set_status(tr("Wczytano sesję: %s (%d widoków, %d zrzutów).", "Session loaded: %s (%d views, %d shots).")
                        % (os.path.basename(path), len(proj.views), len(proj.outputs)), "ok")
        return True

    def save_session(self, save_as: bool = False) -> None:
        path = self.project.path
        if save_as or not path:
            start = os.path.join(self.project.settings.out_dir or os.path.expanduser("~"), "sesja.hmshots.json")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Zapisz sesję", "Save session"), start, "HM Shots session (*.hmshots.json)")
            if not path:
                return
            if not path.endswith(".json"):
                path += ".hmshots.json"
        try:
            self.project.save(path)
        except OSError as exc:
            self.set_status(tr("Nie można zapisać sesji: %s", "Cannot save session: %s") % exc, "err")
            return
        self.refresh_session_tab()
        self.set_status(tr("Sesja zapisana: %s", "Session saved: %s") % path, "ok")

    def autosave(self) -> None:
        """Crash / restart safety net: always a copy in ~/.hm_shots, never the user's file."""
        try:
            self.project.save_copy(autosave_path())
        except OSError:
            pass

    # ------------------------------------------------------------- pickers
    def pick_dir(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Folder zrzutów", "Screenshot folder"), self.project.settings.out_dir or os.path.expanduser("~"))
        if d:
            self.ed_dir.setText(d)
            self._set("out_dir", d)

    def pick_pptx(self) -> None:
        start = self.project.settings.pptx_path or self.project.default_pptx_path()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Plik prezentacji", "Presentation file"), start, "PowerPoint (*.pptx)")
        if path:
            if not path.lower().endswith(".pptx"):
                path += ".pptx"
            self.ed_pptx.setText(path)
            self._set("pptx_path", path)

    def pick_cmdfile(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Plik komend HyperMesh", "HyperMesh command file"), os.getcwd(), "command.tcl (command*.tcl command*.cmf);;All (*)")
        if path:
            self.ed_cmdfile.setText(path)
            self._on_cmdfile()

    def _on_cmdfile(self) -> None:
        self._set("command_file", self.ed_cmdfile.text().strip())
        self.generator.recorder.override = self.project.settings.command_file

    def open_out_dir(self) -> None:
        d = self.generator.resolve_out_dir()
        if d and os.path.isdir(d):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(d))
        else:
            self.set_status(tr("Folder zrzutów nie istnieje.", "The screenshot folder does not exist."), "warn")

    def show_help(self) -> None:
        run_dialog(HelpDialog(help_text.html(), self))

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        self.autosave()
        if self.generator.recorder.active:
            self.generator.recorder.stop()
        super().closeEvent(event)
