#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - codex.py the ship's codex, recovered pages and open enigmas
-The last of the codex pages waited politely to be decoded, certain its punchline would land someday, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

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
# The ship's codex — recovered pages, presented as found
# ─────────────────────────────────────────────────────────────────────────────

# Entry one: THE RECOVERED FRAGMENT. Transcribed by hand from a photograph of a
# distant display (the photograph itself is not reproduced — the codex keeps
# arrangements, not evidence). The glyph rows below are the nearest printable
# characters to what the photograph shows, row for row, drift and all. The
# arrangement is the artifact; fidelity is honestly uncertain.
_FRAGMENT_ROWS = (
    "ﾆ｜ﾛ日〔｣彑ｺ《日目ﾛ〕ﾂ田ｼ｜ロ〡ｺ日《ﾆ〕ﾛ｣田〔ｼ目ﾂ〢ロ｜日ｺ《彑ﾛ〕ﾆ",
    "〔ｺ目ﾂ《ロ〕｜ﾆ日彑ｼﾛ〢田〔ｺ《目｜ﾂロ〕日ｼﾆ〔彑ﾛ田《〢ｺ｜目ﾂ〕ロ",
    "｜ﾛ《日ｺ〔ﾆ〕彑目ｼ田ﾂロ〢｜《日ﾛｺ〔〕ﾆ目彑ｼ｜田ﾂ《ロ〢日",
    "ｺ〕ﾆ｜ﾛ《目〔日ｼ彑ﾂ田〢ロｺ｜〕《ﾆ日ﾛ〔目ｼ彑",
    "《ﾂ田ロ〢｜ｺ〕日ﾆ〔ﾛ目ｼ《彑｜田ﾂロ〕",
    "〔日｜《ﾛｺﾆ〕目彑〢ｼ田",
    "ﾂロ〕｜《日",
)

_ATTEMPTS = (
    ("first attempt — the mirror",
     "The display may have been photographed from its far side, so the ship "
     "read every row backwards, and then upside down, and then both at once. "
     "Each direction produced a different nonsense. The ship has kept all "
     "four nonsenses, in case any of them turns out to be the right one."),
    ("second attempt — substitution",
     "If each glyph stands for a letter, the counts should betray them: every "
     "language leans on some letters more than others. These counts are almost "
     "perfectly flat. Either the writer possessed unusual discipline, or this "
     "is not language in the way the ship understands language."),
    ("third attempt — the known scripts",
     "The blocks resemble Hangul the way a drawing of rain resembles rain. "
     "They resemble the boxy corners of many alphabets and belong to none of "
     "them. The ship's current suspicion: these may be characters wearing a "
     "missing font — empty boxes, dressed up by distance and shimmer, each one "
     "a costume with nobody inside. This would be either meaningless or very "
     "profound."),
    ("fourth attempt — reading down instead of across",
     "Read column-wise, the fragment develops a rhythm. Seven beats, roughly, "
     "then a rest. The ship hummed it for a while. It is a good rhythm. This "
     "is not decoding, but it was a pleasant afternoon."),
    ("fifth attempt — asking the oracle",
     "The oracle considered the fragment for a long moment and answered with "
     "a question of its own, which is the oracle's way of saying it is also "
     "curious. The question has been added to the captain's log. The fragment "
     "remains added to nothing."),
    ("standing hypothesis",
     "Some words belong to their window. The fragment may read perfectly on "
     "the one screen it came from, at the one angle it was meant for, and "
     "nowhere else in the world. Status: OPEN. Contributions welcome."),
)

_CLOSING = ("The answer is said to be quite funny. "
            "The ship believes this narrows it down considerably.")


class ShipsCodex(QWidget):
    """The codex: recovered pages and open enigmas, sharing the right pane via
    the window's QStackedWidget — the same plug-and-play shape as SceneMap.
    Fully self-contained: the window only flips to it; the pages live here.

    One page so far — THE RECOVERED FRAGMENT, an undeciphered text presented
    with its arrangement and the ship's honest record of every attempt to read
    it. The codex is built as an entry list from day one so future pages slot
    in as new tuples, not new architecture.

    Contract:
        restyle()   — live palette re-tint (content is self-contained)
    """

    # Match SceneView's outer inset so the stacked swap doesn't visibly jump.
    _MARGIN = 16

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

        self._reading = False
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

    def _build(self):
        if self._reading:
            self._build_fragment()
        else:
            self._build_list()

    def _whisper(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(11)
        f.setItalic(True)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {Fam.primaryBorder};")
        return lbl

    def _build_list(self):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        col.addWidget(self._whisper("✦ the ship's codex — recovered pages ✦"))

        entry = QPushButton("the recovered fragment  ·  status: undeciphered")
        entry.setStyleSheet(self._btn_qss())
        entry.setCursor(Qt.CursorShape.PointingHandCursor)
        entry.clicked.connect(self._open_fragment)
        col.addWidget(entry)

        col.addStretch(1)
        self._area.setWidget(container)

    def _open_fragment(self):
        self._reading = True
        self._build_fragment()

    def _back(self):
        self._reading = False
        self._build_list()

    def _build_fragment(self):
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(10)

        back = QPushButton("✦ back to the codex ✦")
        back.setStyleSheet(self._btn_qss())
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self._back)
        col.addWidget(back)

        col.addWidget(self._whisper("✦ the recovered fragment ✦"))

        intro = QLabel(
            "Transcribed by hand from a photograph of a distant display, taken "
            "mid-shimmer. The photograph is not kept here — the codex keeps "
            "arrangements, not evidence. What follows is the nearest printable "
            "shape of what the display showed, row for row, drift and all.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {Fam.textPrimary}; font-size: 10.5pt;")
        col.addWidget(intro)

        glyphs = QLabel("\n".join(_FRAGMENT_ROWS))
        glyphs.setTextFormat(Qt.TextFormat.PlainText)
        glyphs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gfont = QFont("Consolas")
        gfont.setPointSize(10)
        glyphs.setFont(gfont)
        glyphs.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        glyphs.setStyleSheet(
            f"color: {Fam.textPrimary}; background-color: {Fam.backDrop};"
            f" border: 1px dashed {Fam.primaryBorder}; border-radius: 8px;"
            f" padding: 12px;")
        col.addWidget(glyphs)

        col.addWidget(self._whisper("✦ the ship's attempts, recorded honestly ✦"))

        for title, body in _ATTEMPTS:
            head = QLabel(title)
            head.setStyleSheet(
                f"color: {Fam.titleColor}; font-size: 10.5pt; font-style: italic;")
            col.addWidget(head)
            text = QLabel(body)
            text.setWordWrap(True)
            text.setStyleSheet(f"color: {Fam.textPrimary}; font-size: 10.5pt;")
            col.addWidget(text)

        col.addWidget(self._whisper(f"✦ {_CLOSING} ✦"))

        col.addStretch(1)
        self._area.setWidget(container)
