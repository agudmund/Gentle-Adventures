#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - journal.py the captain's log, a history of conversations with the ship
-The last of the captains logs kept every question the ship was ever asked, and the answers still glowed, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pretty_widgets.graphics.Theme import Theme as Fam


# ─────────────────────────────────────────────────────────────────────────────
# Captain's log — the journal, and the journal is the Puff transcripts
# ─────────────────────────────────────────────────────────────────────────────


class CaptainsLog(QWidget):
    """The journal: a browsable history of every "ask the ship" conversation,
    read straight from the Puff transcripts already written to disk. Sharing the
    right pane via the window's QStackedWidget, same plug-and-play shape as
    SceneMap — the window hands over the entry list; the log renders and pages.

    Two views inside one widget: the LIST (newest first, one button per
    session) and the READING view (the transcript text with a way back). The
    window never knows which view is showing.

    Contract:
        set_entries([(title, path), ...])  — populate, newest first
        restyle()                          — live palette re-tint
    """

    # Match SceneView's outer inset so the stacked swap doesn't visibly jump.
    _MARGIN = 16

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._area.setStyleSheet(self._area_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._MARGIN, self._MARGIN, self._MARGIN, self._MARGIN)
        layout.addWidget(self._area)

        self._entries: list[tuple[str, Path]] = []
        self._open_entry: tuple[str, Path] | None = None
        self._build()

    # ── styling (live-reload aware) ───────────────────────────────────────────

    def _area_qss(self) -> str:
        """Frame the scroll area like SceneView's node-bordered image."""
        return (
            f"QScrollArea {{ background-color: {Fam.nodeBg};"
            f" border: {int(Fam.nodeBorderWidth)}px solid {Fam.nodeBorder};"
            f" border-radius: {int(Fam.nodeRoundRadius)}px; }}"
        )

    def _btn_qss(self) -> str:
        return (
            f"QPushButton {{ background-color: {Fam.buttonBg}; color: {Fam.textPrimary};"
            f" border: 1px solid {Fam.buttonBorder}; border-radius: 12px;"
            f" padding: 9px 16px; font-size: 12pt; text-align: left; }}"
            f"QPushButton:hover:enabled {{ background-color: {Fam.backDrop};"
            f" border: 1px solid {Fam.titleColor}; color: {Fam.buttonTextHover}; }}"
        )

    def restyle(self):
        """Re-tint from the live family palette; rebuilds the current view."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._area.setStyleSheet(self._area_qss())
        self._build()

    # ── content ───────────────────────────────────────────────────────────────

    def set_entries(self, entries):
        """Populate the log. `entries`: iterable of (title, path), newest first.
        The window owns the scan (where transcripts live is its knowledge);
        the log owns the reading. Repopulating returns to the list view."""
        self._entries = [(str(t), Path(p)) for t, p in entries]
        self._open_entry = None
        self._build()

    def _build(self):
        if self._open_entry is not None:
            self._build_reading(*self._open_entry)
        else:
            self._build_list()

    def _build_list(self):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        header = QLabel("✦ the captain's log — conversations with the ship ✦")
        header.setAlignment(Qt.AlignCenter)
        hfont = QFont()
        hfont.setPointSize(11)
        hfont.setItalic(True)
        header.setFont(hfont)
        header.setStyleSheet(f"color: {Fam.primaryBorder};")
        col.addWidget(header)

        if not self._entries:
            empty = QLabel("✦ the log is empty — ask the ship something and it will remember ✦")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {Fam.primaryBorder}; font-size: 11pt;")
            col.addStretch(1)
            col.addWidget(empty)
            col.addStretch(2)
            self._area.setWidget(container)
            return

        for title, path in self._entries:
            btn = QPushButton(title)
            btn.setStyleSheet(self._btn_qss())
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, t=title, p=path: self._open(t, p))
            col.addWidget(btn)

        col.addStretch(1)
        self._area.setWidget(container)

    def _open(self, title: str, path: Path):
        self._open_entry = (title, path)
        self._build_reading(title, path)

    def _build_reading(self, title: str, path: Path):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(10)

        back = QPushButton("✦ back to the log ✦")
        back.setStyleSheet(self._btn_qss())
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self._back)
        col.addWidget(back)

        header = QLabel(title)
        header.setAlignment(Qt.AlignCenter)
        hfont = QFont()
        hfont.setPointSize(11)
        hfont.setItalic(True)
        header.setFont(hfont)
        header.setStyleSheet(f"color: {Fam.primaryBorder};")
        col.addWidget(header)

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = "✦ this page would not open — the file may have sailed on ✦"

        body = QLabel(text)
        body.setTextFormat(Qt.PlainText)   # transcripts render as written, no markup surprises
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        body.setStyleSheet(f"color: {Fam.textPrimary}; font-size: 10.5pt;")
        col.addWidget(body)

        col.addStretch(1)
        self._area.setWidget(container)

    def _back(self):
        self._open_entry = None
        self._build_list()
