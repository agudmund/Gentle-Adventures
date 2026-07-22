#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - inventory.py the keepsake shelf, earned stickers on display
-The last of the keepsake shelves held out both hands and every sticker the journey pressed into them stayed, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pretty_widgets.graphics.Theme import Theme as Fam


# ─────────────────────────────────────────────────────────────────────────────
# Keepsake shelf — the inventory, in this game's own language
# ─────────────────────────────────────────────────────────────────────────────


class KeepsakeShelf(QWidget):
    """A self-contained display of every reward sticker the captain has earned,
    sharing the right pane with the scene image via the window's QStackedWidget
    (the same plug-and-play shape as SceneMap: the window calls set_stickers,
    the shelf renders; neither reaches inside the other).

    Inventory in Gentle Adventures IS the sticker collection — keepsakes from
    true beats, not consumable items. Purely a display case; earning happens in
    the quest (the bloom over the scene stays the celebration, the shelf is
    where the memory lives afterwards, persisted across sessions).

    Contract:
        set_stickers([(png_path, achievement_name), ...])  — populate the shelf
        restyle()                                          — live palette re-tint
    """

    # Match SceneView's outer inset so the stacked swap doesn't visibly jump.
    _MARGIN = 16
    _COLS = 3          # shelf width, in keepsakes
    _STICKER_PX = 108  # display size of each keepsake

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setStyleSheet(self._area_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._MARGIN, self._MARGIN, self._MARGIN, self._MARGIN)
        layout.addWidget(self._area)

        self._stickers: list[tuple[str, str]] = []
        self._build()

    # ── styling (live-reload aware) ───────────────────────────────────────────

    def _area_qss(self) -> str:
        """Frame the scroll area like SceneView's node-bordered image."""
        return (
            f"QScrollArea {{ background-color: {Fam.nodeBg};"
            f" border: {int(Fam.nodeBorderWidth)}px solid {Fam.nodeBorder};"
            f" border-radius: {int(Fam.nodeRoundRadius)}px; }}"
        )

    def restyle(self):
        """Re-tint from the live family palette; rebuilds so labels re-tint too."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._area.setStyleSheet(self._area_qss())
        self._build()

    # ── content ───────────────────────────────────────────────────────────────

    def set_stickers(self, stickers):
        """Populate the shelf. `stickers`: iterable of (png_path, achievement_name),
        in the order they should sit on the shelf. The window owns WHICH keepsakes
        exist (persisted state + this session's earns); the shelf only displays."""
        self._stickers = [(str(p), str(name)) for p, name in stickers]
        self._build()

    def _build(self):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(10)

        header = QLabel("✦ the keepsake shelf ✦")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hfont = QFont()
        hfont.setPointSize(11)
        hfont.setItalic(True)
        header.setFont(hfont)
        header.setStyleSheet(f"color: {Fam.primaryBorder};")
        col.addWidget(header)

        if not self._stickers:
            empty = QLabel("✦ no keepsakes yet — true beats press stickers into your hands ✦")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {Fam.primaryBorder}; font-size: 11pt;")
            col.addStretch(1)
            col.addWidget(empty)
            col.addStretch(2)
            self._area.setWidget(container)
            return

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(16)
        for i, (path, name) in enumerate(self._stickers):
            cell = QVBoxLayout()
            cell.setSpacing(6)

            art = QLabel()
            art.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(path)
            if pix.isNull():
                # Silent absence, in miniature: a keepsake whose asset went
                # missing renders as its name alone rather than breaking the shelf.
                art.setText("✦")
                art.setStyleSheet(f"color: {Fam.primaryBorder}; font-size: 24pt;")
            else:
                art.setPixmap(pix.scaled(
                    self._STICKER_PX, self._STICKER_PX,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

            tag = QLabel(name)
            tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag.setWordWrap(True)
            tag.setStyleSheet(f"color: {Fam.textPrimary}; font-size: 10pt;")

            cell.addWidget(art)
            cell.addWidget(tag)
            holder = QWidget()
            holder.setLayout(cell)
            grid.addWidget(holder, i // self._COLS, i % self._COLS, Qt.AlignmentFlag.AlignTop)

        col.addLayout(grid)
        col.addStretch(1)
        self._area.setWidget(container)
