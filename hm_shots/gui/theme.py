# -*- coding: utf-8 -*-
"""Modern flat theme (light / dark) as a Qt style sheet."""
from __future__ import annotations

LIGHT = {
    "bg": "#F3F4F6", "card": "#FFFFFF", "border": "#E5E7EB", "border_strong": "#D1D5DB",
    "text": "#111827", "muted": "#6B7280", "accent": "#2563EB", "accent_hover": "#1D4ED8", "accent_soft": "#DBEAFE",
    "success": "#059669", "success_hover": "#047857", "danger": "#DC2626", "danger_soft": "#FEE2E2",
    "warn": "#D97706", "ref": "#2563EB", "inf": "#DC2626", "header": "#111827", "header_text": "#F9FAFB",
    "input": "#FFFFFF", "hover": "#F9FAFB", "selected": "#EFF6FF", "scroll": "#CBD5E1", "log_bg": "#0F172A", "log_text": "#E2E8F0",
}
DARK = {
    "bg": "#0F172A", "card": "#1E293B", "border": "#334155", "border_strong": "#475569",
    "text": "#F1F5F9", "muted": "#94A3B8", "accent": "#3B82F6", "accent_hover": "#60A5FA", "accent_soft": "#1E3A8A",
    "success": "#10B981", "success_hover": "#34D399", "danger": "#EF4444", "danger_soft": "#7F1D1D",
    "warn": "#F59E0B", "ref": "#60A5FA", "inf": "#F87171", "header": "#020617", "header_text": "#F8FAFC",
    "input": "#0F172A", "hover": "#273449", "selected": "#1E3A8A", "scroll": "#475569", "log_bg": "#020617", "log_text": "#CBD5E1",
}


def palette(dark: bool) -> dict:
    return DARK if dark else LIGHT


def stylesheet(dark: bool = False) -> str:
    c = palette(dark)
    return """
* { font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif; font-size: 10pt; }
QMainWindow, QDialog, QWidget#Root { background: %(bg)s; color: %(text)s; }
QWidget { color: %(text)s; }
QLabel { background: transparent; }
QLabel#Title { font-size: 15pt; font-weight: 600; color: %(header_text)s; }
QLabel#Subtitle { font-size: 9pt; color: #CBD5E1; }
QLabel#Section { font-size: 11pt; font-weight: 600; color: %(text)s; padding: 2px 0; }
QLabel#Muted { color: %(muted)s; font-size: 9pt; }
QLabel#Hint { color: %(muted)s; font-size: 8.5pt; }
QLabel#Status { color: %(muted)s; }
QLabel#StatusOk { color: %(success)s; font-weight: 600; }
QLabel#StatusErr { color: %(danger)s; font-weight: 600; }
QLabel#StatusWarn { color: %(warn)s; font-weight: 600; }
QFrame#Header { background: %(header)s; border: none; }
QFrame#Header QLabel { color: %(header_text)s; }
QFrame#Card { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#Card[selected="true"] { border: 2px solid %(accent)s; }
QFrame#Card[selected="false"] { border: 1px solid %(border)s; }
QFrame#Tile { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#Tile[selected="true"] { border: 2px solid %(accent)s; }
QFrame#Tile:hover { border-color: %(border_strong)s; }
QFrame#Thumb { background: #0B1220; border: 1px solid %(border)s; border-radius: 8px; }
QFrame#HLine { background: %(border)s; max-height: 1px; min-height: 1px; border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %(scroll)s; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %(scroll)s; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QPushButton { background: %(card)s; border: 1px solid %(border_strong)s; border-radius: 7px; padding: 5px 12px; color: %(text)s; }
QPushButton:hover { background: %(hover)s; border-color: %(accent)s; }
QPushButton:pressed { background: %(accent_soft)s; }
QPushButton:disabled { color: %(muted)s; border-color: %(border)s; }
QPushButton[kind="primary"] { background: %(accent)s; color: white; border: none; font-weight: 600; }
QPushButton[kind="primary"]:hover { background: %(accent_hover)s; }
QPushButton[kind="success"] { background: %(success)s; color: white; border: none; font-weight: 700; font-size: 12pt; padding: 10px 18px; }
QPushButton[kind="success"]:hover { background: %(success_hover)s; }
QPushButton[kind="danger"] { background: transparent; color: %(danger)s; border: 1px solid %(danger)s; }
QPushButton[kind="danger"]:hover { background: %(danger_soft)s; }
QPushButton[kind="ghost"] { background: transparent; border: 1px solid transparent; }
QPushButton[kind="ghost"]:hover { background: %(hover)s; border-color: %(border)s; }
QPushButton[kind="small"] { padding: 2px 8px; font-size: 9pt; }
QPushButton[kind="rec"] { background: %(danger)s; color: white; border: none; font-weight: 600; }
QPushButton:checked[kind="seg"] { background: %(accent)s; color: white; border-color: %(accent)s; }
QPushButton[kind="seg"] { padding: 4px 14px; font-weight: 600; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 3px; color: %(text)s; }
QToolButton:hover { background: %(hover)s; border-color: %(border)s; }
QToolButton:checked { background: %(accent_soft)s; border-color: %(accent)s; color: %(accent)s; }
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: %(input)s; border: 1px solid %(border_strong)s; border-radius: 6px; padding: 4px 6px; selection-background-color: %(accent)s; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: %(accent)s; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: %(muted)s; background: %(bg)s; }
QLineEdit#NameEdit { font-weight: 600; font-size: 10.5pt; border: 1px solid transparent; background: transparent; }
QLineEdit#NameEdit:hover, QLineEdit#NameEdit:focus { border-color: %(border_strong)s; background: %(input)s; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: %(card)s; border: 1px solid %(border)s; selection-background-color: %(accent_soft)s; selection-color: %(text)s; }
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button { width: 14px; border: none; background: transparent; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid %(border_strong)s; border-radius: 4px; background: %(input)s; }
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; image: none; }
QCheckBox::indicator:disabled { background: %(bg)s; }
QCheckBox#MetricCheck { font-weight: 600; }
QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px; border: 1px solid %(border_strong)s; background: %(input)s; }
QRadioButton::indicator:checked { background: %(accent)s; border: 3px solid %(input)s; outline: 1px solid %(accent)s; }
QGroupBox { border: 1px solid %(border)s; border-radius: 8px; margin-top: 12px; padding: 10px 8px 6px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: %(muted)s; }
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 8px; background: %(card)s; top: -1px; }
QTabBar::tab { background: transparent; padding: 7px 14px; margin-right: 2px; border: 1px solid transparent; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; color: %(muted)s; font-weight: 600; }
QTabBar::tab:selected { background: %(card)s; border-color: %(border)s; color: %(accent)s; }
QTabBar::tab:hover { color: %(text)s; }
QProgressBar { border: 1px solid %(border)s; border-radius: 6px; background: %(input)s; text-align: center; height: 14px; color: %(text)s; }
QProgressBar::chunk { background: %(success)s; border-radius: 5px; }
QPlainTextEdit#Log { background: %(log_bg)s; color: %(log_text)s; font-family: Consolas, "Courier New", monospace; font-size: 9pt; border-radius: 8px; }
QPlainTextEdit#Code { font-family: Consolas, "Courier New", monospace; font-size: 9pt; }
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 8px; }
QSplitter::handle:vertical { height: 8px; }
QMenu { background: %(card)s; border: 1px solid %(border)s; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 5px; }
QMenu::item:selected { background: %(accent_soft)s; }
QToolTip { background: %(header)s; color: %(header_text)s; border: 1px solid %(border_strong)s; padding: 4px 6px; border-radius: 5px; }
QListWidget, QTableWidget, QTreeWidget { background: %(input)s; border: 1px solid %(border)s; border-radius: 6px; }
QListWidget::item { padding: 5px 6px; border-radius: 4px; }
QListWidget::item:selected { background: %(accent_soft)s; color: %(text)s; }
QGraphicsView { border: 1px solid %(border)s; border-radius: 8px; background: %(bg)s; }
QLabel#Badge { background: %(accent_soft)s; color: %(accent)s; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
QLabel#BadgeRef { background: %(ref)s; color: white; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 700; }
QLabel#BadgeInf { background: %(inf)s; color: white; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 700; }
QLabel#BadgeOk { background: %(success)s; color: white; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
QLabel#BadgeWarn { background: %(warn)s; color: white; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
QLabel#BadgeMuted { background: %(border)s; color: %(muted)s; border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
""" % c
