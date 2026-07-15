#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - scene_map.py the scene navigator, a plug-and-play jump map
-A first-class module the window calls and the scene yields to, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pretty_widgets.graphics.Theme import Theme as Fam
from pretty_widgets.PrettyTooltip import install_tooltip


# ─────────────────────────────────────────────────────────────────────────────
# Scene map — a standalone, swappable scene navigator
# ─────────────────────────────────────────────────────────────────────────────


class SceneMap(QWidget):
    """A self-contained scene picker that shares the right pane with the scene
    image (the window flips between them in a QStackedWidget).

    Deliberately its own first-class module — like the plug-and-play layout of
    intricate/util — so the map can go through many iterations of look, feel,
    and function without the window or the scene view ever changing. The window
    *calls* it (set_scenes), the map *announces* a pick (scene_picked); neither
    the window nor SceneView reaches inside. Delete this file + the stack wiring
    in main_window and the feature is cleanly gone.

    Contract:
        set_scenes([(scene_id, title), ...])   — populate the list
        scene_picked = Signal(str)             — emitted with the chosen scene_id
        restyle()                              — re-tint on a live palette change
    """

    scene_picked = Signal(str)

    # Match SceneView's outer inset so the stacked swap doesn't visibly jump.
    _MARGIN = 16

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        # A scroll area framed like the node-bordered scene image it sits beside.
        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._area.setStyleSheet(self._area_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._MARGIN, self._MARGIN, self._MARGIN, self._MARGIN)
        layout.addWidget(self._area)

        self._scenes: list[tuple[str, str]] = []
        self._visited: set[str] = set()
        self._build()

    # ── styling (live-reload aware) ───────────────────────────────────────────

    def _area_qss(self) -> str:
        """Frame the scroll area like SceneView's node-bordered image."""
        return (
            f"QScrollArea {{ background-color: {Fam.nodeBg};"
            f" border: {int(Fam.nodeBorderWidth)}px solid {Fam.nodeBorder};"
            f" border-radius: {int(Fam.nodeRoundRadius)}px; }}"
        )

    def _btn_qss(self, locked: bool = False) -> str:
        # Visited scenes are navigable; unvisited ones render locked — the same
        # faded, dashed look as before. The catch: a locked button stays *enabled*
        # rather than calling setEnabled(False), because a disabled QPushButton
        # receives no hover events — and the family pill tooltip (like every Qt
        # tooltip) needs the hover to fire. So "locked" is painted, not disabled:
        # the click is simply never wired and the cursor stays an arrow, so it
        # reads as unreachable while still surfacing the unlock-hint pill.
        if locked:
            return (
                f"QPushButton {{ background: transparent; color: {Fam.primaryBorder};"
                f" border: 1px dashed {Fam.primaryBorder}; border-radius: 12px;"
                f" padding: 9px 16px; font-size: 12pt; text-align: left; }}"
            )
        return (
            f"QPushButton {{ background-color: {Fam.buttonBg}; color: {Fam.textPrimary};"
            f" border: 1px solid {Fam.buttonBorder}; border-radius: 12px;"
            f" padding: 9px 16px; font-size: 12pt; text-align: left; }}"
            f"QPushButton:hover:enabled {{ background-color: {Fam.backDrop};"
            f" border: 1px solid {Fam.titleColor}; color: {Fam.buttonTextHover}; }}"
        )

    def restyle(self):
        """Re-tint from the live family palette (settings watcher → reload).
        Rebuilds the list so every button picks up the fresh palette too."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._area.setStyleSheet(self._area_qss())
        self._build()

    # ── content ───────────────────────────────────────────────────────────────

    def set_scenes(self, scenes, visited=None):
        """Populate the navigator.

        `scenes`  : iterable of (scene_id, title), in order.
        `visited` : iterable of scene_ids the player has already reached. Only
                    those are navigable; the rest render locked, so the map can
                    only send you back to places you've been — new areas are
                    unlocked by playing the adventure, not by jumping ahead.

        One clean seam for the data source: today the window hands us the scene
        list + visited set; when the source changes (Ledger, then the planned
        tree), only the window changes — this module is untouched.
        """
        self._scenes = [(str(sid), str(title)) for sid, title in scenes]
        self._visited = set(visited or ())
        self._build()

    # Subcategory detection (placeholder until the proper tree lands): a chapter
    # number with a fractional part — 01.5, 02.5 — reads as a sub-beat of the
    # whole number before it, so we indent it one notch under its parent.
    _INDENT_PX = 26
    _CHAPTER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")

    def _indent_for(self, title: str) -> int:
        m = self._CHAPTER_RE.search(title or "")
        return 1 if (m and "." in m.group(1)) else 0

    def _build(self):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        header = QLabel("✦ choose a scene ✦")
        header.setAlignment(Qt.AlignCenter)
        hfont = QFont()
        hfont.setPointSize(11)
        hfont.setItalic(True)
        header.setFont(hfont)
        header.setStyleSheet(f"color: {Fam.primaryBorder};")
        col.addWidget(header)

        for scene_id, title in self._scenes:
            btn = QPushButton(title or scene_id)
            visited = scene_id in self._visited
            btn.setStyleSheet(self._btn_qss(locked=not visited))
            if visited:
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(
                    lambda _checked=False, sid=scene_id: self.scene_picked.emit(sid))
            else:
                # Locked: enabled (so the hover-driven pill fires) but never wired
                # to a click, arrow cursor — unreachable, not dead.
                btn.setCursor(Qt.ArrowCursor)
                btn.setToolTip("✦ reach this in the adventure to unlock ✦")
                install_tooltip(btn)

            # Indent sub-beats (01.5, 02.5 …) one notch under their parent.
            row = QHBoxLayout()
            row.setContentsMargins(self._indent_for(title) * self._INDENT_PX, 0, 0, 0)
            row.addWidget(btn)
            col.addLayout(row)

        col.addStretch(1)
        self._area.setWidget(container)
