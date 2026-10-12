# -*- coding: utf-8 -*-
"""Small dialogs: edit view, add view from text, metric learning, help."""
from __future__ import annotations

from typing import List, Optional

from ..hm_bridge import parse_numbers
from ..i18n import tr
from ..views import ViewRecord
from .qt import QtWidgets, exec_
from .widgets import hint_label


class EditViewDialog(QtWidgets.QDialog):
    def __init__(self, rec: Optional[ViewRecord], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Edytuj widok", "Edit view") if rec else tr("Dodaj widok z tekstu", "Add view from text"))
        self.resize(640, 460)
        self.rec = rec
        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit(rec.name if rec else "")
        form.addRow(tr("Nazwa:", "Name:"), self.name)
        lay.addLayout(form)
        lay.addWidget(QtWidgets.QLabel(tr("Dane kamery (VS: 20 liczb z *viewset / hm_winfo viewmatrix):",
                                          "Camera data (VS: 20 numbers from *viewset / hm_winfo viewmatrix):")))
        self.view = QtWidgets.QPlainTextEdit(rec.view_text if rec else "")
        self.view.setObjectName("Code")
        self.view.setFixedHeight(90)
        lay.addWidget(self.view)
        lay.addWidget(QtWidgets.QLabel(tr("Komendy układu wyświetlania (opcjonalnie, odtwarzane przed zrzutem):",
                                          "Display-layout commands (optional, replayed before the shot):")))
        self.disp = QtWidgets.QPlainTextEdit(rec.disp if rec else "")
        self.disp.setObjectName("Code")
        lay.addWidget(self.disp, 1)
        lay.addWidget(hint_label(tr("Wskazówka: wiele widoków naraz – wklej kilka linii „VS: …”, każda stanie się osobnym widokiem.",
                                    "Tip: several views at once – paste several “VS: …” lines, each becomes a separate view.")))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def view_lists(self) -> List[List[float]]:
        """All camera number lists found in the text (one per line with >= 16 numbers)."""
        out: List[List[float]] = []
        for line in self.view.toPlainText().splitlines():
            nums = parse_numbers(line)
            if len(nums) >= 16:
                out.append(nums)
        if not out:
            nums = parse_numbers(self.view.toPlainText())
            if len(nums) >= 16:
                out.append(nums[:20])
        return out


class LearnMetricDialog(QtWidgets.QDialog):
    """Guides the user through recording a quality check from the command file."""

    def __init__(self, metric_name: str, default_thr: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Nagraj komendy metryki: %s", "Record metric commands: %s") % metric_name)
        self.resize(560, 300)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(tr(
            "1. Nagrywanie jest aktywne – w HyperMesh wykonaj kontrolę jakości ręcznie\n"
            "   (np. Tool → Check Elems → %s → check / display) z PONIŻSZĄ wartością graniczną.\n"
            "2. Wróć tutaj i kliknij „Zakończ i zapisz”. Komendy z command.tcl staną się szablonem,\n"
            "   a wpisana wartość zostanie zastąpiona symbolem {thr}.",
            "1. Recording is active – perform the quality check by hand in HyperMesh\n"
            "   (e.g. Tool → Check Elems → %s → check / display) using the limit BELOW.\n"
            "2. Come back and click “Finish and save”. The command.tcl lines become the template\n"
            "   and the typed limit is replaced with {thr}.") % metric_name))
        form = QtWidgets.QFormLayout()
        self.thr = QtWidgets.QDoubleSpinBox()
        self.thr.setDecimals(4)
        self.thr.setRange(-1e6, 1e6)
        self.thr.setValue(default_thr)
        form.addRow(tr("Użyta wartość graniczna:", "Limit value used:"), self.thr)
        lay.addLayout(form)
        lay.addWidget(hint_label(tr("Użyj nietypowej wartości (np. 4.37), aby na pewno została rozpoznana w komendzie.",
                                    "Use an unusual value (e.g. 4.37) so it is recognised unambiguously in the command.")))
        bb = QtWidgets.QDialogButtonBox()
        ok = bb.addButton(tr("Zakończ i zapisz", "Finish and save"), QtWidgets.QDialogButtonBox.AcceptRole)
        ok.setProperty("kind", "primary")
        bb.addButton(QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


def ask_text(parent, title: str, label: str, default: str = "") -> Optional[str]:
    text, ok = QtWidgets.QInputDialog.getText(parent, title, label, QtWidgets.QLineEdit.Normal, default)
    return text if ok else None


class HelpDialog(QtWidgets.QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Pomoc", "Help"))
        self.resize(720, 560)
        lay = QtWidgets.QVBoxLayout(self)
        box = QtWidgets.QTextBrowser()
        box.setOpenExternalLinks(True)
        box.setHtml(text)
        lay.addWidget(box)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        bb.clicked.connect(self.accept)
        lay.addWidget(bb)


def run_dialog(dlg: QtWidgets.QDialog) -> bool:
    return exec_(dlg) == QtWidgets.QDialog.Accepted
