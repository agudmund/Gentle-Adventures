#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - widgets.py the Sierra chrome — title bar, scene view, narrative, interaction
-The chrome that holds the wonder, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QPixmap, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Family chrome — the titlebar matches Intricate / The Majestic by drawing from
# the shared Pretty Widgets Theme, the Chandler42 font helper, and pill tooltips.
from pretty_widgets.graphics.Theme import Theme as Fam
from pretty_widgets.utils.fonts import chandler42
from pretty_widgets.PrettyTooltip import install_tooltip
from pretty_widgets.PrettyCombo import combo as pretty_combo


# ─────────────────────────────────────────────────────────────────────────────
# Title bar — "GENTLE ADVENTURES, 03 (Cont.)" style strip across the top
# ─────────────────────────────────────────────────────────────────────────────


class TitleBar(QWidget):
    """Family-signature frameless titlebar — absolute-positioned to match
    Intricate / The Majestic.

    Layout (left → right):
        [ PrettyCombo "Gentle Adventures" | ✦ curtains | InfoBar typewriter … | – □ ✕ ]

    Children are placed by counting pixels from the LEFT edge (combo at
    _COMBO_X, curtains right of it) — the family technique that lands cleanly,
    instead of Qt auto-centering which never does. min/max/exid are pinned to
    the right edge; the InfoBar typewriter fills the gap. Drag anywhere to move;
    double-click the left half toggles fullscreen. OS titlebar hidden, so this
    is the only handle.
    """

    curtains_clicked = Signal()    # roll up into the strip / expand back out

    # Family-consistent proportions from the shared Theme.
    _BAR_H = max(Fam.handleHeightTop, Fam.titleFontSize + 8)
    _BTN_W = _BAR_H
    _GAP   = Fam.toolbarBtnGap
    # Fixed pixel offset from the left for the combo (the family's toolbarTitleX
    # trick — deterministic, no auto-centering). Tuned for GA's 960px default;
    # nudge this one number to slide the combo + curtains cluster left/right.
    _COMBO_X = 360
    _COMBO_W = 172
    # Titlebar InfoBar font — 9px at a 25px handle, the family reference ratio
    # (Intricate main_window.py:456). Gentle white (textPrimary), never the teal
    # title accent: the infobar whispers, it doesn't shout.
    _INFO_FONT_PX = max(6, round(Fam.handleHeightTop * 9 / 25))
    # Curtains brand: the colourful share-arrow sticker (Family-3), copied from
    # intricate/icons/Stickers — the bright version of the iconic.png fallback.
    _CURTAINS_ICON = "Stickers/Intricate.ico"

    def __init__(self):
        super().__init__()
        self.setFixedHeight(self._BAR_H)
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        # ── center: single-entry PrettyCombo faking a project selector — the
        #    same look-and-feel trick The Majestic uses ──
        self._combo = pretty_combo()
        self._combo.addItem("Gentle Adventures")
        self._combo.setParent(self)
        self._combo.setFixedWidth(self._COMBO_W)

        # ── brand / curtains button ──
        self._btn_curtains = self._control(
            "✦", self.curtains_clicked.emit, icon_name=self._CURTAINS_ICON, accent=True,
            tooltip="Roll the window up into this strip — click again to expand",
        )
        self._btn_curtains.setParent(self)

        # ── InfoBar / title — Chandler42 script-italic in lombardi-lake teal.
        #    set_title() types it out char-by-char (the "infobar typing speed"),
        #    so a scene title reveals like a line of typewriter prose. Fills the
        #    central gap between the curtains button and the right cluster. ──
        self._label = QLabel("", self)
        self._label.setAlignment(Qt.AlignCenter)
        # Click-through so a press over the title still drags the window.
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._label.setFont(chandler42(size_px=self._INFO_FONT_PX))
        self._label.setStyleSheet(f"color: {Fam.textPrimary};")

        # ── right cluster: minimize / maximize / exid ──
        self._btn_min = self._control("–", self._on_minimize, icon_name=Fam.iconTray, tooltip="Minimize")
        self._btn_max = self._control("□", self._on_maximize, icon_name=Fam.iconMaximize, tooltip="Maximize")
        self._btn_close = self._control(
            "✕", self._on_close, icon_name=Fam.iconClose, close=True,
            tooltip="Exid, not a typo.  It's an exit button named exid",
        )
        for b in (self._btn_min, self._btn_max, self._btn_close):
            b.setParent(self)

        self._drag_pos = None
        # typewriter state for the title / infobar reveal
        self._tw_full = ""
        self._tw_index = 0
        self._tw_timer = None

    # ── window controls ──────────────────────────────────────────────────────

    def _control(self, glyph: str = "", slot=None, icon_name: str | None = None,
                 close: bool = False, accent: bool = False, tooltip: str = "") -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(self._BTN_W, self._BAR_H)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        if icon_name:
            # Family icons resolve via Theme.icon() → app icons/ then the asset
            # vault ($SingleSharedBraincell_AssetVault/Icons). Missing → honest
            # circle, no crash. main.py's FamTheme.reload() loads the mappings.
            btn.setIcon(QIcon(Fam.icon(icon_name)))
            btn.setIconSize(QSize(Fam.toolbarBtnIconSize, Fam.toolbarBtnIconSize))
        elif glyph:
            btn.setText(glyph)
        if tooltip:
            btn.setToolTip(tooltip)
            install_tooltip(btn)   # pill-shaped family tooltip (Chandler42 italic)
        btn.setProperty("_qss_close", close)
        btn.setProperty("_qss_accent", accent)
        btn.setStyleSheet(self._btn_qss(close, accent))
        btn.clicked.connect(slot)
        return btn

    def _btn_qss(self, close: bool, accent: bool) -> str:
        """Per-button stylesheet derived from the family palette; shared by
        _control (build) and restyle (live re-tint)."""
        base_fg  = Fam.titleColor if accent else Fam.textPrimary
        hover_bg = "#c0392b" if close else Fam.backDrop
        hover_fg = "#ffffff" if close else Fam.textPrimary
        return (
            "QPushButton {"
            f"  background: transparent; color: {base_fg};"
            "   border: none; font-size: 13px; font-family: 'Segoe UI Symbol'; }"
            f"QPushButton:hover {{ background: {hover_bg}; color: {hover_fg}; }}"
        )

    def restyle(self):
        """Re-tint the bar + controls from the live family palette. The settings
        watcher fires this after Theme.reload(), so a Color Picker edit in The
        Settlers ripples into the titlebar without a restart."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        for b in (self._btn_curtains, self._btn_min, self._btn_max, self._btn_close):
            b.setStyleSheet(self._btn_qss(bool(b.property("_qss_close")),
                                          bool(b.property("_qss_accent"))))
        self._label.setStyleSheet(f"color: {Fam.textPrimary};")

    # ── absolute layout — pixels from the left (the family technique) ─────────

    def _reposition(self):
        h, gap = self._BAR_H, self._GAP

        # Combo at a fixed offset from the left; curtains immediately right of it.
        self._combo.move(self._COMBO_X, (h - self._combo.height()) // 2)
        self._combo.raise_()
        cur_x = self._COMBO_X + self._combo.width() + gap * 3
        self._btn_curtains.move(cur_x, (h - self._btn_curtains.height()) // 2)
        self._btn_curtains.raise_()

        # Right cluster pinned to the right edge: exid, then max, then min.
        w = self.width()
        ex = w - self._btn_close.width() - Fam.toolbarRightMargin
        mx = ex - self._btn_max.width() - gap
        mn = mx - self._btn_min.width() - gap
        for btn, x in ((self._btn_close, ex), (self._btn_max, mx), (self._btn_min, mn)):
            btn.move(x, (h - btn.height()) // 2)
            btn.raise_()

        # InfoBar fills the gap between the curtains button and the right cluster.
        left_edge  = cur_x + self._btn_curtains.width() + gap * 4
        right_edge = mn - gap * 4
        self._label.setGeometry(left_edge, 0, max(40, right_edge - left_edge), h)
        self._label.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()

    def _on_minimize(self):
        # Minimize-to-tray (family behaviour): hide the window and surface the
        # tray icon. It comes back via the tray icon click or its Show menu.
        self.window().minimize_to_tray()

    def _on_maximize(self):
        # Taskbar-aware maximize lives on the window (work_area / manual
        # geometry, family-consistent) — the bar just triggers it.
        self.window().toggle_maximize()

    def reflect_maximized(self, maxed: bool):
        """Keep the max/restore icon in sync with the window state.

        restore_node.ico is dev-only (intricate/icons) and not in the shared
        asset vault yet, so the maximize icon stays for both states until it
        lands there — Fam.icon() would otherwise draw an honest circle.
        """
        self._btn_max.setIcon(QIcon(Fam.icon(Fam.iconMaximize)))

    def _on_close(self):
        self.window().close()

    def _toggle_fullscreen(self):
        w = self.window()
        if w.isFullScreen():
            w.showNormal()
        else:
            w.showFullScreen()

    # ── window drag (frameless) — Intricate's globalPosition-delta move ───────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            w = self.window()
            if getattr(w, "is_window_maximized", None) and w.is_window_maximized():
                # Dragging a maximized window restores it, then follows the cursor.
                w.restore_window()
            new_pos = event.globalPosition().toPoint()
            w.move(w.pos() + (new_pos - self._drag_pos))
            self._drag_pos = new_pos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Left half only → fullscreen toggle; right half is the control cluster.
        if event.button() == Qt.LeftButton and event.position().x() < self.width() / 2:
            self._toggle_fullscreen()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    # ── InfoBar typewriter — the family's Chandler42 reveal ───────────────────

    def set_title(self, text: str):
        """Type the title/message out char-by-char at the family's infobar pace
        — 85% brisk keystrokes, 15% little pauses — for an organic reveal.
        Replaces the old instant setText (Majestic / Intricate do the same)."""
        if self._tw_timer is not None:
            self._tw_timer.stop()
        self._tw_full = text or ""
        self._tw_index = 0
        self._label.setText("")
        self._tw_timer = QTimer(self)
        self._tw_timer.setSingleShot(True)
        self._tw_timer.timeout.connect(self._tw_tick)
        self._tw_timer.start(random.randint(20, 60))

    def _tw_tick(self):
        self._tw_index += 1
        self._label.setText(self._tw_full[:self._tw_index])
        if self._tw_index < len(self._tw_full):
            delay = random.choices(
                [random.randint(25, 65), random.randint(80, 160)],
                weights=[85, 15],
            )[0]
            self._tw_timer.start(delay)
        else:
            self._tw_timer = None


# ─────────────────────────────────────────────────────────────────────────────
# Scene view — square scene image with loading and error states
# ─────────────────────────────────────────────────────────────────────────────


class SceneView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(560)
        self.setStyleSheet(f"background-color: {Fam.backDrop};")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            f"color: {Fam.primaryBorder}; "
            f"background-color: {Fam.backDrop};"
        )
        font = QFont()
        font.setPointSize(11)
        font.setItalic(True)
        self._image_label.setFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)

        self._current_pixmap: QPixmap | None = None

    def show_loading(self):
        self.show_placeholder("✦ the painter is painting ✦")

    def show_placeholder(self, text: str):
        self._current_pixmap = None
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(text)

    def show_image(self, pixmap: QPixmap):
        self._current_pixmap = pixmap
        self._image_label.setText("")
        self._rescale()

    def show_error(self, message: str):
        self._current_pixmap = None
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(
            f"the painter went quiet\n\n{message}\n\n"
            f"(check your GEMINI_API_KEY and try again)"
        )

    def resizeEvent(self, event):  # noqa: N802 — Qt naming
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        scaled = self._current_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)


# ─────────────────────────────────────────────────────────────────────────────
# Narrative panel — the story text + verification accent
# ─────────────────────────────────────────────────────────────────────────────


class NarrativePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(140)
        self.setStyleSheet(f"background-color: {Fam.nodeBg};")

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        font = QFont()
        font.setPointSize(13)
        self._text.setFont(font)
        self._text.setStyleSheet(f"color: {Fam.textPrimary};")

        self._verified = QLabel()
        self._verified.setAlignment(Qt.AlignRight)
        vfont = QFont()
        vfont.setPointSize(10)
        vfont.setBold(True)
        self._verified.setFont(vfont)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 14)
        layout.setSpacing(6)
        layout.addWidget(self._text)
        layout.addWidget(self._verified)

    def set_text(self, body: str, verified: bool | None = None):
        self._text.setText(body)
        if verified is True:
            self._verified.setText("★ system confirmed")
            self._verified.setStyleSheet(f"color: {Fam.healthColorCalm};")
        elif verified is False:
            self._verified.setText("○ not yet detected — try the step on your machine")
            self._verified.setStyleSheet(f"color: {Fam.primaryBorder};")
        else:
            self._verified.setText("")


# ─────────────────────────────────────────────────────────────────────────────
# Interaction bar — preset buttons + free-form parser input
# ─────────────────────────────────────────────────────────────────────────────


class InteractionBar(QWidget):
    choice_made = Signal(object, str)  # (choice_dict_or_None, free_text)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(110)
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        self._buttons_row = QHBoxLayout()
        self._buttons_row.setSpacing(10)

        self._parser = QLineEdit()
        self._parser.setPlaceholderText("✦ ask the ship anything ✦")
        self._parser.setStyleSheet(
            f"QLineEdit {{ "
            f"background-color: {Fam.backDrop}; "
            f"color: {Fam.textPrimary}; "
            f"border: 1px solid {Fam.primaryBorder}; "
            f"border-radius: 16px; "
            f"padding: 8px 16px; "
            f"font-size: 13pt; "
            f"}}"
            f"QLineEdit:focus {{ border: 1px solid {Fam.titleColor}; }}"
        )
        pfont = QFont()
        pfont.setPointSize(12)
        self._parser.setFont(pfont)
        self._parser.returnPressed.connect(self._on_parser_submit)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 12, 20, 14)
        outer.setSpacing(10)
        outer.addLayout(self._buttons_row)
        outer.addWidget(self._parser)

        self._buttons: list[QPushButton] = []
        self._choices: list[dict] = []

    def set_choices(self, choices: list[dict]):
        # Tear down old buttons (including the trailing stretch item)
        while self._buttons_row.count():
            item = self._buttons_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()
        self._choices = choices

        for idx, choice in enumerate(choices):
            btn = QPushButton(choice["label"])
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ "
                f"background-color: {Fam.buttonBg}; "
                f"color: {Fam.textPrimary}; "
                f"border: 1px solid {Fam.buttonBorder}; "
                f"border-radius: 14px; "
                f"padding: 8px 18px; "
                f"font-size: 12pt; "
                f"}}"
                f"QPushButton:hover {{ background-color: {Fam.backDrop}; "
                f"border: 1px solid {Fam.titleColor}; color: {Fam.buttonTextHover}; }}"
            )
            btn.clicked.connect(lambda _checked=False, i=idx: self._on_button(i))
            self._buttons_row.addWidget(btn)
            self._buttons.append(btn)
        self._buttons_row.addStretch(1)

    def set_parser_visible(self, visible: bool):
        self._parser.setVisible(visible)
        if visible:
            self._parser.setFocus()

    def set_parser_placeholder(self, text: str):
        self._parser.setPlaceholderText(text)

    def set_parser_mode(self, mode: str):
        """mode in {'free', 'key', 'hidden'}."""
        if mode == "hidden":
            self.set_parser_visible(False)
            return
        if mode == "key":
            self._parser.setEchoMode(QLineEdit.Password)
            self.set_parser_placeholder("✦ paste your Gemini key here ✦")
        else:
            self._parser.setEchoMode(QLineEdit.Normal)
            self.set_parser_placeholder("✦ ask the ship anything ✦")
        self.set_parser_visible(True)

    def clear_parser(self):
        self._parser.clear()

    def _on_button(self, index: int):
        if 0 <= index < len(self._choices):
            self.choice_made.emit(self._choices[index], "")

    def _on_parser_submit(self):
        text = self._parser.text().strip()
        if not text:
            return
        self._parser.clear()
        self.choice_made.emit(None, text)


# ─────────────────────────────────────────────────────────────────────────────
# Bottom toolbar — branded weight beneath the interaction bar
# ─────────────────────────────────────────────────────────────────────────────


class BottomToolbar(QWidget):
    """Family-signature bottom toolbar — the branded strip that gives the
    window visual weight below the 'ask the ship' prompt and frames the
    rolled-up silhouette.

    A thin infobar strip (gentle-white whisper, click to collapse) sits over a
    row of placeholder feature buttons. Collapsing slides the buttons away,
    leaving just the strip pinned to the bottom edge. The simple cousin of
    Intricate's bottom bar — no splitter, no InfoBar routing, just chrome.
    """

    strip_clicked = Signal()    # emitted on collapse/expand toggle

    _STRIP_H = max(Fam.handleHeightTop, 28)
    # A touch larger than the titlebar's 9px whisper — the bottom strip is
    # roomier, so the infobar can breathe without shouting. Same gentle white.
    _INFO_FONT_PX = max(8, round(Fam.handleHeightTop * 11 / 25))
    # Feature placeholders to wire up during dev — clicking whispers a status
    # into the strip until the real feature lands.
    _PLACEHOLDERS = ("inventory", "map", "journal", "codex")

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._collapsed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 0, 10, 6)
        outer.setSpacing(4)

        # ── infobar strip (doubles as the collapse handle) ──
        self._strip = QWidget()
        self._strip.setFixedHeight(self._STRIP_H)
        self._strip.setCursor(Qt.PointingHandCursor)
        self._strip.setStyleSheet("background: transparent;")
        strip_layout = QHBoxLayout(self._strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)
        self._info = QLabel("", self._strip)
        self._info.setAlignment(Qt.AlignCenter)
        self._info.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._info.setFont(chandler42(size_px=self._INFO_FONT_PX))
        self._info.setStyleSheet(f"color: {Fam.textPrimary};")
        strip_layout.addWidget(self._info, stretch=1)
        outer.addWidget(self._strip)
        self._strip.mousePressEvent = lambda e: self.toggle_collapse()

        # ── placeholder feature buttons ──
        self._buttons_row = QWidget()
        row = QHBoxLayout(self._buttons_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)
        self._buttons: list[QPushButton] = []
        for name in self._PLACEHOLDERS:
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(96)
            btn.setStyleSheet(self._placeholder_qss())
            btn.clicked.connect(lambda _c=False, n=name: self.set_info(f"✦ {n} — not wired up yet ✦"))
            row.addWidget(btn)
            self._buttons.append(btn)
        row.addStretch(1)
        outer.addWidget(self._buttons_row)

    def _placeholder_qss(self) -> str:
        # Muted (primaryBorder text/border) so placeholders read as dormant
        # tools, not live actions — they brighten to the teal accent on hover.
        return (
            f"QPushButton {{ background: {Fam.buttonBg}; color: {Fam.primaryBorder};"
            f" border: 1px solid {Fam.primaryBorder}; border-radius: 12px;"
            f" padding: 6px 14px; font-size: 10pt; }}"
            f"QPushButton:hover {{ border: 1px solid {Fam.titleColor};"
            f" color: {Fam.textPrimary}; }}"
        )

    def set_info(self, text: str):
        """Whisper a line into the bottom infobar strip."""
        self._info.setText(text)

    def toggle_collapse(self):
        """Slide the buttons away (collapse to the strip) or bring them back."""
        self._collapsed = not self._collapsed
        self._buttons_row.setVisible(not self._collapsed)
        self.strip_clicked.emit()

    def restyle(self):
        """Re-tint from the live family palette (settings watcher → reload)."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._info.setStyleSheet(f"color: {Fam.textPrimary};")
        for b in self._buttons:
            b.setStyleSheet(self._placeholder_qss())
