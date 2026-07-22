#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - sidebar.py the left rail, home of the lower-corner control grid
-A quiet console of faders and meters, family-signature, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QVariantAnimation, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QProgressBar,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from pretty_widgets.graphics.Theme import Theme as Fam


def _ti(name: str, default: int) -> int:
    """A Theme value coerced to int, with a fallback (the metaclass returns a
    sentinel for missing keys, so guard the numeric layout dims)."""
    v = getattr(Fam, name, None)
    try:
        v = v() if callable(v) else v
        return int(v)
    except Exception:
        return default


class Sidebar(QWidget):
    """Family-signature left rail (its own citizen — the window calls it).

    Hosts the lower-corner 2×3 control grid, cloned from Intricate / The Majestic
    (visually identical): a bottom row of 3 progress-bar slots and a row above of
    3 slider slots. The "2×3" is faked with two stacked QHBoxLayouts whose empty
    cells are fixed-size QSpacerItem slots — that keeps the columns aligned with
    no real grid (the family idiom).

    For now exactly ONE cell is live: a 'working' meter (vertical QProgressBar,
    canonical 4-stop pink gradient) that fades in and gently breathes while any
    background worker runs, then fades out when idle. The other five cells are
    reserved spacers — scaffolding for the coming control board.
    """

    def __init__(self):
        super().__init__()
        sz = _ti("iconButtonSize", 44)
        self._bar_w = max(8, sz // 3)
        self._bar_h = sz * 2
        pad = _ti("sidebarPadding", 8)
        gap = _ti("sidebarButtonGap", 6)

        self.setFixedWidth(_ti("sidebarWidth", sz * 2))
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(gap)

        # ── sliders row (Expanding) — three reserved slots for future faders.
        # Its Expanding policy (NOT a stretch) absorbs the slack and pushes the
        # bars row to the bottom; with real vertical sliders it also lets them
        # travel full height. (Per Intricate's layout note.)
        sliders_row = QWidget()
        sliders_row.setStyleSheet("background: transparent;")
        sliders_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sr = QHBoxLayout(sliders_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(0)
        sr.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        for _ in range(3):
            sr.addSpacerItem(self._slot())
        layout.addWidget(sliders_row)
        layout.addSpacing(2)

        # ── progress-bars row (bottom-anchored) — two reserved slots + the bar.
        bars_row = QWidget()
        bars_row.setStyleSheet("background: transparent;")
        br = QHBoxLayout(bars_row)
        br.setContentsMargins(0, 0, 0, 0)
        br.setSpacing(0)
        br.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        br.addSpacerItem(self._slot())
        br.addSpacerItem(self._slot())
        self._bar = self._make_bar()
        br.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(bars_row, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(4)

        # The working meter rests invisible; it fades in only while busy.
        self._fx = QGraphicsOpacityEffect(self._bar)
        self._fx.setOpacity(0.0)
        self._bar.setGraphicsEffect(self._fx)
        self._fade = None
        self._breathe = None

    # ── construction helpers ───────────────────────────────────────────────

    def _slot(self) -> QSpacerItem:
        """A reserved cell — the exact footprint a real control would occupy, so
        the two rows' columns line up. The whole 2×3 alignment trick."""
        return QSpacerItem(self._bar_w, self._bar_h, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _bar_qss(self) -> str:
        # Canonical family progress-bar look: vertical 4-stop pink gradient,
        # bottom-to-top (y1:1 -> y2:0). Identical to Intricate / The Majestic.
        return (
            f"QProgressBar {{ background: {Fam.backDrop};"
            f" border: 1px solid {Fam.primaryBorder}; border-radius: 3px; }}"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:1, x2:0, y2:0,"
            " stop:0 #1e1e1e, stop:0.4 #5c3e4f, stop:0.7 #a56a85, stop:1 #d87a9e);"
            " border-radius: 2px; }"
        )

    def _make_bar(self) -> QProgressBar:
        bar = QProgressBar()
        bar.setOrientation(Qt.Orientation.Vertical)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedWidth(self._bar_w)
        bar.setMinimumHeight(self._bar_h)
        bar.setStyleSheet(self._bar_qss())
        return bar

    def restyle(self) -> None:
        """Re-tint from the live family palette (settings watcher → reload)."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._bar.setStyleSheet(self._bar_qss())

    # ── the 'working' signal ────────────────────────────────────────────────

    def set_working(self, working: bool) -> None:
        """Fade the meter in and breathe while busy; fade out + rest when idle."""
        if working:
            self._fade_to(1.0)
            self._start_breathe()
        else:
            self._stop_breathe()
            self._fade_to(0.0)
            self._bar.setValue(0)

    def _fade_to(self, target: float) -> None:
        if self._fade is not None:
            self._fade.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._fx.opacity())
        anim.setEndValue(float(target))
        anim.setDuration(400)
        anim.valueChanged.connect(lambda v: self._fx.setOpacity(float(v)))
        anim.start()
        self._fade = anim

    def _start_breathe(self) -> None:
        if self._breathe is not None and self._breathe.state() == QPropertyAnimation.State.Running:
            return
        anim = QPropertyAnimation(self._bar, b"value", self)
        anim.setStartValue(0)
        anim.setKeyValueAt(0.5, 100)
        anim.setEndValue(0)
        anim.setDuration(1600)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        anim.start()
        self._breathe = anim

    def _stop_breathe(self) -> None:
        if self._breathe is not None:
            self._breathe.stop()
            self._breathe = None
