#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - widgets.py the Sierra chrome — title bar, scene view, narrative, interaction
-The chrome that holds the wonder, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QVariantAnimation
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor, QPainter, QPen, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
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
# Resize grip — bottom-right window resize handle (ported from Intricate)
# ─────────────────────────────────────────────────────────────────────────────
class ResizeGrip(QWidget):
    """Bottom-right window resize handle, ported from Intricate's main-window grip.

    Drags the target window's geometry from the corner, clamped to the window's
    minimum size. Like the rest of the family it keeps the plain arrow cursor —
    the OS diagonal resize cursor stays *hidden*; the painted three-line glyph is
    the affordance. Self-contained and raised above the layout, so it works over
    whatever child fills the corner (the scene view / bottom toolbar, in GA).
    """

    _SIZE = 20   # widget footprint; the glyph tucks into its lower-right

    def __init__(self, target_window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._win = target_window
        self._drag = False
        self._press_global = None
        self._press_size = None
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setToolTip("Drag to resize the window")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(Fam.textPrimary)
        col.setAlpha(140)
        p.setPen(QPen(col, 2))
        w, h = self.width(), self.height()
        # Three nested diagonal ticks — the universal resize-corner glyph.
        for off in (4, 9, 14):
            p.drawLine(w - off, h - 4, w - 4, h - off)
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag = True
            self._press_global = event.globalPosition().toPoint()
            self._press_size = self._win.size()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag and self._press_global is not None:
            delta = event.globalPosition().toPoint() - self._press_global
            # Absolute floors as well as the window minimum — the curtains roll
            # zeroes setMinimumHeight() mid-gesture and doesn't restore it, so
            # minimumHeight() alone could let the grip shrink the window to nothing.
            floor_w = max(self._win.minimumWidth(), 320)
            floor_h = max(self._win.minimumHeight(), 240)
            new_w = max(floor_w, self._press_size.width()  + delta.x())
            new_h = max(floor_h, self._press_size.height() + delta.y())
            self._win.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag = False
        event.accept()

    def restyle(self) -> None:
        """Re-tint on live palette reload."""
        self.update()


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
    narrative_changed = Signal(str)  # selected narrative key (titlebar selector)

    # Titlebar height = the shared suite value (Theme.handleHeightTop), the exact
    # number Intricate / The Majestic use — so GA's bar matches the family rather
    # than standing taller. The old max(handleHeightTop, titleFontSize+8) silently
    # won at 30px over the suite's 25 (the "feels thicker" the board flagged), and
    # everything keyed off _BAR_H — button width, the 9px-at-25px info-font ratio —
    # was misaligned as a result. One shared source now; the dependents realign.
    _BAR_H = Fam.handleHeightTop
    # Titlebar controls = the suite's shared toolbarBtnSize (19px square), the same
    # as Intricate / The Majestic — NOT the full bar height. Icons already use
    # Fam.toolbarBtnIconSize (15); _reposition centres the 19px button in the bar.
    _BTN_W = Fam.toolbarBtnSize
    _GAP   = Fam.toolbarBtnGap
    # Combo + curtains sit at the suite's shared fixed-from-left positions
    # (Theme.toolbarTitleX / toolbarCurtainsX) — the family's deterministic,
    # no-auto-centering technique — so GA's titlebar elements line up with
    # Intricate / The Majestic instead of drifting ~110px left.
    _COMBO_X = Fam.toolbarTitleX
    # Combo fills the span between the title anchor and the curtains button (minus a
    # 4px gap) — the exact formula Intricate's _fit_project_selector uses — so it
    # ends just shy of the curtains instead of stopping ~54px short. = 226 at the
    # suite spacing, and tracks the shared vars if they ever change.
    _COMBO_W = Fam.toolbarCurtainsX - Fam.toolbarTitleX - 4
    # Titlebar InfoBar font — 9px at a 25px handle, the family reference ratio
    # (Intricate main_window.py:456). Gentle white (textPrimary), never the teal
    # title accent: the infobar whispers, it doesn't shout.
    _INFO_FONT_PX = max(6, round(Fam.handleHeightTop * 9 / 25))
    # Curtains brand: the colourful share-arrow sticker (Family-3), copied from
    # intricate/icons/Stickers — the bright version of the iconic.png fallback.
    _CURTAINS_ICON = "Stickers/Intricate.ico"
    # Title display: announce, hold, then fade off (Majestic infobar timing).
    _TITLE_HOLD_MS = 3500
    _TITLE_FADE_MS = 700
    # De-allcaps to Title Case but keep real acronyms uppercase.
    _ACRONYMS = {"XDNA", "NPU", "CPU", "GPU", "AI", "FLM", "FIN", "OS", "LM"}

    def __init__(self):
        super().__init__()
        self.setFixedHeight(self._BAR_H)
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        # ── center: single-entry PrettyCombo faking a project selector — the
        #    same look-and-feel trick The Majestic uses ──
        self._combo = pretty_combo()
        self._combo.setParent(self)
        self._combo.setFixedWidth(self._COMBO_W)
        # Narrative selector — registry-driven (data.quest.NARRATIVES). With one
        # narrative it reads as the old single-entry label; add a narrative tab
        # and it becomes a live switcher: currentIndexChanged -> narrative_changed
        # -> main_window swaps the active Quest_Log tab. blockSignals while
        # populating (Qt fires activated on programmatic setCurrentIndex).
        from data.quest import narratives as _narratives, active_narrative_key as _active_nk
        self._combo.blockSignals(True)
        for _n in _narratives():
            self._combo.addItem(_n["label"], _n["key"])
        _ai = self._combo.findData(_active_nk())
        if _ai >= 0:
            self._combo.setCurrentIndex(_ai)
        self._combo.blockSignals(False)
        self._combo.currentIndexChanged.connect(
            lambda _i: self.narrative_changed.emit(self._combo.currentData() or ""))

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
        # The title announces, holds, then fades off. Opacity rides a graphics
        # effect so the fade never rebuilds the stylesheet.
        self._label_fx = QGraphicsOpacityEffect(self._label)
        self._label_fx.setOpacity(1.0)
        self._label.setGraphicsEffect(self._label_fx)
        self._fade_anim = None

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
        btn.setFixedSize(self._BTN_W, self._BTN_W)   # square, suite-consistent (19px)
        # Default arrow cursor on the titlebar controls — the tactile feel of
        # gently touching them; no hand-pointer swap on hover.
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
        _control (build) and restyle (live re-tint). No hover glow — the icon
        buttons are tactile enough on their own, so hovering leaves them blank
        (close/accent kept in the signature for call-site stability)."""
        base_fg = Fam.titleColor if accent else Fam.textPrimary
        return (
            "QPushButton {"
            f"  background: transparent; color: {base_fg};"
            "   border: none; font-size: 13px; font-family: 'Segoe UI Symbol'; }"
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
        cur_x = Fam.toolbarCurtainsX   # suite-shared curtains X (matches Intricate)
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
            delta = new_pos - self._drag_pos
            if getattr(w, "_curtains_collapsed", False):
                # Rolled up → the window rides a vertical rail (x locked), so
                # moving the family's apps feels like sliding faders rather than
                # floating windows; free-float only when expanded. Clamp y so the
                # strip can't leave the visible desktop (reserve auto-hide taskbar
                # room — full−available height, min 48px). Mirrors Intricate.
                screen = w.screen()
                full, avail = screen.geometry(), screen.availableGeometry()
                taskbar_h = max(full.height() - avail.height(), 48)
                new_y = max(avail.top(), w.pos().y() + delta.y())
                new_y = min(new_y, full.bottom() - w.height() - taskbar_h + 5)
                w.move(w.pos().x(), new_y)
            else:
                w.move(w.pos() + delta)
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

    def _prettify_title(self, raw: str) -> str:
        """Display form of a scene title: drop the chapter token (', 01.5 — ')
        and de-allcaps to Title Case, keeping known acronyms uppercase.
        'GENTLE ADVENTURES, 01.5 — LORE: XDNA' -> 'Gentle Adventures: Lore: XDNA'."""
        t = re.sub(r",\s*\d+(?:\.\d+)?\s*[—–-]\s*", ": ", raw)
        out = []
        for w in t.split(" "):
            bare = w.rstrip(":,")
            tail = w[len(bare):]
            if bare.upper() in self._ACRONYMS:
                out.append(bare.upper() + tail)
            elif bare:
                out.append(bare[:1].upper() + bare[1:].lower() + tail)
            else:
                out.append(w)
        return " ".join(out)

    def set_title(self, text: str):
        """Prettify the scene title, type it out char-by-char at the family's
        infobar pace (85% brisk keystrokes, 15% little pauses), then hold and
        fade it off (Majestic's infobar timing)."""
        if self._tw_timer is not None:
            self._tw_timer.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
            self._fade_anim = None
        self._label_fx.setOpacity(1.0)
        self._tw_full = self._prettify_title(text or "")
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
            # Announced — hold a beat, then fade off.
            QTimer.singleShot(self._TITLE_HOLD_MS, self._start_title_fade)

    def _start_title_fade(self):
        anim = QVariantAnimation(self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(self._TITLE_FADE_MS)
        anim.valueChanged.connect(lambda v: self._label_fx.setOpacity(float(v)))
        anim.start()
        self._fade_anim = anim   # keep a ref so it isn't GC'd mid-fade


# ─────────────────────────────────────────────────────────────────────────────
# Scene view — square scene image with loading and error states
# ─────────────────────────────────────────────────────────────────────────────


class SceneView(QWidget):
    # Framed like an Intricate node — a gentle padded border around the scene
    # image. _MARGIN insets the frame from the window edge; _PADDING is the
    # breathing gap between the border and the image (nodeBg matte shows
    # through, exactly like a node's content inset).
    _MARGIN = 16
    _PADDING = 10

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 360)
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(self._frame_qss())
        font = QFont()
        font.setPointSize(11)
        font.setItalic(True)
        self._image_label.setFont(font)

        # Centre the framed square in the view — the border hugs the image (no
        # dead side-matte), windowBg breathing around it in the column.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._MARGIN, self._MARGIN, self._MARGIN, self._MARGIN)
        layout.addWidget(self._image_label, alignment=Qt.AlignCenter)

        self._current_pixmap: QPixmap | None = None

    def _frame_qss(self) -> str:
        """Intricate's node frame, drawn from the family Theme so it matches the
        canvas nodes (nodeBorder / nodeBorderWidth / nodeRoundRadius / nodeBg)
        and re-tints with primary_border live."""
        return (
            f"QLabel {{ color: {Fam.primaryBorder};"
            f" background-color: {Fam.nodeBg};"
            f" border: {int(Fam.nodeBorderWidth)}px solid {Fam.nodeBorder};"
            f" border-radius: {int(Fam.nodeRoundRadius)}px;"
            f" padding: {self._PADDING}px; }}"
        )

    def restyle(self):
        """Re-tint the frame from the live family palette (settings watcher)."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._image_label.setStyleSheet(self._frame_qss())
        self._fit()

    def show_loading(self):
        self.show_placeholder("✦ the painter is painting ✦")

    def show_placeholder(self, text: str):
        self._current_pixmap = None
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(text)
        self._fit()

    def show_image(self, pixmap: QPixmap):
        self._current_pixmap = pixmap
        self._image_label.setText("")
        self._fit()

    def show_error(self, message: str):
        self._current_pixmap = None
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(
            f"the painter went quiet\n\n{message}\n\n"
            f"(check your GEMINI_API_KEY and try again)"
        )
        self._fit()

    def flash_sticker(self, path: str):
        """Celebration: a reward sticker blooms over the scene, holds, and fades.
        A transient overlay child — it never disturbs the framed image beneath,
        and deletes itself when the bloom finishes."""
        pm = QPixmap(path)
        if pm.isNull():
            return
        box = max(120, int(min(self.width(), self.height()) * 0.5))
        lbl = QLabel(self)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lbl.setStyleSheet("background: transparent;")
        lbl.setPixmap(pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lbl.adjustSize()
        lbl.move((self.width() - lbl.width()) // 2, (self.height() - lbl.height()) // 2)
        lbl.show()
        lbl.raise_()

        eff = QGraphicsOpacityEffect(lbl)
        lbl.setGraphicsEffect(eff)
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.18, 1.0)   # bloom in
        anim.setKeyValueAt(0.72, 1.0)   # hold
        anim.setEndValue(0.0)           # fade out
        anim.setDuration(1900)
        anim.valueChanged.connect(lambda v: eff.setOpacity(float(v)))
        anim.finished.connect(lbl.deleteLater)
        anim.start()
        self._sticker_anim = anim   # keep a ref so it isn't GC'd mid-bloom

    def resizeEvent(self, event):  # noqa: N802 — Qt naming
        super().resizeEvent(event)
        self._fit()

    def _fit(self):
        """Hug a centred square. The framed label is sized to the smaller of the
        available width/height (minus the outer margin), so the node border
        wraps the square image with no dead matte; windowBg breathes around it.
        Square source art fills the frame exactly; text placeholders centre in
        the same square box so loading/error read consistently."""
        inset = 2 * (int(Fam.nodeBorderWidth) + self._PADDING)
        box = max(1, min(self.width(), self.height()) - 2 * self._MARGIN)
        self._image_label.setFixedSize(box, box)
        if self._current_pixmap is not None and not self._current_pixmap.isNull():
            side = max(1, box - inset)
            scaled = self._current_pixmap.scaled(
                QSize(side, side), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._image_label.setPixmap(scaled)


# ─────────────────────────────────────────────────────────────────────────────
# Narrative panel — the story text + verification accent
# ─────────────────────────────────────────────────────────────────────────────


class NarrativePanel(QWidget):
    """The story column — text streams in like a typewriter rather than landing as
    a finished block, so a scene reads as a thought arriving, not a notepad page.

    Two borrowed mechanics, woven together:
      • Pacing — from The Majestic's proofreader: a char batch + delay that scale
        with how much text is left, so a long passage doesn't crawl (1 char/tick
        with an 85/15 brisk-vs-human-pause jitter for short text, up to 8/tick for
        long) — the gentle hand-typed cadence that's so smooth to read.
      • Glow — from the legacy Notepad-Duplex-Turbo render preview: a tight bright
        sparkle rides the print head (a few chars, pure white, brighter than the
        cream body) and the text settles to textPrimary just behind it, so a spark
        travels across the line as it lands rather than half the line staying lit.

    A generation stamp guards the settle callbacks: when a scene swaps mid-reveal
    (e.g. the NPU 'feeling for the engine' interstitial giving way to the resolved
    narrative), the previous generation's pending settles are dropped, so stale
    flashes can never repaint the new text — the re-trigger stays clean, not busy.
    """

    _GLOW_CHARS = 3   # width of the travelling sparkle (chars kept bright at the head)
    _GLOW_MS = 150    # how long the final spark lingers once the line finishes

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(280)
        # Blend with the window — in the side-by-side layout the narrative is a
        # text column on windowBg, with the framed image as the one bordered
        # focal element beside it (no competing panel block).
        self.setStyleSheet(f"background-color: {Fam.windowBg};")

        # A read-only QTextEdit (not a QLabel): per-run char formatting is what the
        # glow needs, and it gives mouse/keyboard selection for free, so a command
        # like 'flm run llama3.2:3b' lifts straight off the page.
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFrameShape(QTextEdit.NoFrame)
        self._text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text.document().setDocumentMargin(0)   # the layout owns the inset
        self._text.setStyleSheet(
            f"QTextEdit {{ background: transparent; color: {Fam.textPrimary};"
            f" border: none; }}"
        )
        font = QFont()
        font.setPointSize(13)
        self._text.setFont(font)
        self._text.viewport().setCursor(Qt.IBeamCursor)

        self._verified = QLabel()
        self._verified.setAlignment(Qt.AlignRight)
        vfont = QFont()
        vfont.setPointSize(10)
        vfont.setBold(True)
        self._verified.setFont(vfont)

        # Story fills the column; verification line pinned to the bottom.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 28, 20)
        layout.setSpacing(6)
        layout.addWidget(self._text, 1)
        layout.addWidget(self._verified)

        # Paragraph divider asset: GA's own play sticker (the app logo), with a
        # 2px white rule out from its centre — the Majestic's "lines and stickers"
        # treatment, dropped between paragraphs as the reveal crosses them.
        from utils.paths import app_root
        _play = app_root() / "icons" / "playIcon.png"
        self._play_url = _play.as_uri() if _play.exists() else ""

        # ── typewriter state ─────────────────────────────────────────────────
        self._tw_timer = QTimer(self)
        self._tw_timer.setSingleShot(True)
        self._tw_timer.timeout.connect(self._tw_tick)
        self._tw_buffer = ""        # current paragraph's text still to reveal
        self._segments: list = []   # upcoming ('text', str) / ('sep', None) segments
        self._generation = 0        # bumped per set_text/cut; guards stale settles
        self._lit_from = 0          # doc position dividing settled text from the sparkle
        self._glow_color = QColor("#ffffff")         # a bright white sparkle …
        self._base_color = QColor(Fam.textPrimary)   # … settling to the cream body

    def restyle(self):
        """Re-tint from the live family palette (settings watcher → reload)."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._text.setStyleSheet(
            f"QTextEdit {{ background: transparent; color: {Fam.textPrimary};"
            f" border: none; }}"
        )
        self._glow_color = QColor("#ffffff")
        self._base_color = QColor(Fam.textPrimary)

    def cut(self):
        """Stop any in-progress reveal at once — the captain swapped scenes, so
        we're 'done with this one'. Bumping the generation drops the old reveal's
        pending settle/tail callbacks; the next set_text starts fresh. Crucially it
        also frees the event loop — a running tick-timer was starving the deferred
        scene-apply, so the new text used to wait for the old to finish printing."""
        self._generation += 1
        self._tw_timer.stop()
        self._tw_buffer = ""
        self._segments = []

    def set_text(self, body: str, verified: bool | None = None):
        # Bump the generation FIRST: any settle callbacks still pending from the
        # previous scene now belong to an old generation and will no-op, so they
        # can't repaint this fresh text.
        self._generation += 1
        self._tw_timer.stop()
        self._text.clear()
        self._tw_buffer = ""
        self._lit_from = 0

        # Weave a divider between paragraphs: text, sep, text, sep, … (empty
        # paragraphs are skipped so two dividers never stack).
        self._segments = []
        first = True
        for para in (body or "").split("\n\n"):
            if not para.strip():
                continue
            if not first:
                self._segments.append(("sep", None))
            self._segments.append(("text", para))
            first = False

        if verified is True:
            self._verified.setText("★ system confirmed")
            self._verified.setStyleSheet(f"color: {Fam.healthColorCalm};")
        elif verified is False:
            self._verified.setText("○ not yet detected — try the step on your machine")
            self._verified.setStyleSheet(f"color: {Fam.primaryBorder};")
        else:
            self._verified.setText("")

        if self._segments:
            self._tw_timer.start(10)   # first character lands almost at once

    def _tw_tick(self):
        # Pull the next paragraph (inserting any dividers we cross) once the
        # current one is spent.
        while not self._tw_buffer and self._segments:
            kind, payload = self._segments.pop(0)
            if kind == "sep":
                self._insert_separator()
            elif payload:
                self._tw_buffer = payload
        if not self._tw_buffer:
            # All paragraphs revealed — let the final spark shine a beat, settle it.
            gen = self._generation
            QTimer.singleShot(self._GLOW_MS, lambda g=gen: self._settle_tail(g))
            return
        rem = len(self._tw_buffer)
        # Batch + delay scale with what's left (The Majestic's pacing curve).
        if rem > 500:
            n, delay = 8, random.randint(18, 35)
        elif rem > 200:
            n, delay = 4, random.randint(25, 50)
        elif rem > 80:
            n, delay = 2, random.randint(30, 60)
        else:
            n = 1
            # 85% brisk, 15% a human breath — the cadence that reads as thinking.
            delay = random.choices(
                [random.randint(25, 65), random.randint(80, 160)],
                weights=[85, 15],
            )[0]

        chunk = self._tw_buffer[:n]
        self._tw_buffer = self._tw_buffer[n:]

        # Reveal the new run in the bright sparkle colour at the head.
        cur = QTextCursor(self._text.document())
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(self._glow_color)
        cur.insertText(chunk, fmt)
        end = cur.position()

        # Keep only the last _GLOW_CHARS bright; settle everything behind the
        # sparkle to the cream body at once. The lit region stays a tight
        # travelling dot, never a long tail — independent of batch speed.
        settle_to = max(self._lit_from, end - self._GLOW_CHARS)
        if settle_to > self._lit_from:
            self._recolor(self._lit_from, settle_to, self._base_color)
            self._lit_from = settle_to

        # Keep the loop turning; the next tick pulls the following paragraph (and
        # any divider) once this one is spent, or settles the final spark if done.
        self._tw_timer.start(delay)

    def _insert_separator(self):
        """Drop GA's play-sticker divider between paragraphs. Settle any lingering
        sparkle first, then advance _lit_from past the divider so the recolour pass
        never reaches back across it."""
        cur = QTextCursor(self._text.document())
        cur.movePosition(QTextCursor.MoveOperation.End)
        if self._lit_from < cur.position():
            self._recolor(self._lit_from, cur.position(), self._base_color)
        cur.insertHtml(self._separator_html())
        cur.movePosition(QTextCursor.MoveOperation.End)
        self._lit_from = cur.position()

    def _separator_html(self) -> str:
        # The Majestic idiom: a full-width table with the play sticker in a rowspan
        # cell so the 2px white rule meets it at the sticker's vertical centre.
        img = (f'<img src="{self._play_url}" width="18" height="18" />'
               if self._play_url else "&nbsp;")
        return (
            '<table width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="margin-top:16px; margin-bottom:12px;">'
            '<tr>'
            f'<td rowspan="2" width="26" valign="middle">{img}</td>'
            '<td style="border-bottom:2px solid #ffffff;">&nbsp;</td>'
            '</tr>'
            '<tr><td>&nbsp;</td></tr>'
            '</table>'
        )

    def _settle_tail(self, gen: int):
        """Settle the trailing sparkle once the line has fully landed — unless a
        newer scene has taken over (generation moved on)."""
        if gen != self._generation:
            return
        end = max(0, self._text.document().characterCount() - 1)
        self._recolor(self._lit_from, end, self._base_color)
        self._lit_from = end

    def _recolor(self, start: int, end: int, color: QColor):
        doc = self._text.document()
        last = max(0, doc.characterCount() - 1)   # valid cursor positions: 0..last
        cur = QTextCursor(doc)
        cur.setPosition(min(start, last))
        cur.setPosition(min(end, last), QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cur.mergeCharFormat(fmt)


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

    strip_clicked = Signal()       # emitted on collapse/expand toggle
    feature_clicked = Signal(str)  # a placeholder feature button was clicked (by name)

    _STRIP_H = max(Fam.handleHeightTop, 28)
    # A touch larger than the titlebar's 9px whisper — the bottom strip is
    # roomier, so the infobar can breathe without shouting. Same gentle white.
    _INFO_FONT_PX = max(8, round(Fam.handleHeightTop * 11 / 25))
    # Feature placeholders to wire up during dev — clicking whispers a status
    # into the strip until the real feature lands.
    _PLACEHOLDERS = ("inventory", "map", "journal", "codex")
    # Spectral pulse — a passive gold "the ether answered" tick (Intricate's
    # meov colour-pulse mechanism, but one-shot and gold): a brief flash on the
    # infobar confirming a full cloud round-trip, no system logs in the UI.
    _PULSE_GOLD = "#e8c46a"     # warm XDNA-2 gold — the heartbeat reached the stars
    _PULSE_MS = 900             # one textPrimary → gold → textPrimary flash
    _PULSE_HOLD_MS = 1600       # sparkle dwell before the prior whisper returns
    _LEDGER_DIM   = "#4a4a4a"   # dim grey — the Ledger dot when there's no proxy
    _LEDGER_AMBER = "#d8a657"   # warm amber — saved on board, syncing to the cloud
    _LEDGER_GREEN = "#7ac47a"   # soft sage — live & synced; the family's green status-dot (cf. GitNode), calm "on" not alarm
    _LEDGER_RED   = "#ff3030"   # bright alarm red — Ledger OFF; large + loud so it's impossible to miss

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
        # Ledger status dot (far left): green when the cloud Ledger is live, amber
        # while syncing, and a big bright red when OFF (progress still saved on
        # board). A glanceable health light; hover gives the word.
        self._ledger_state = "off"
        self._ledger_dot = QLabel("●", self._strip)
        self._ledger_dot.setFixedWidth(24)   # wide enough for the larger OFF glyph
        self._ledger_dot.setAlignment(Qt.AlignCenter)
        self._ledger_dot.setCursor(Qt.ArrowCursor)
        install_tooltip(self._ledger_dot)   # family pill tooltip; reads toolTip() live on hover
        strip_layout.addWidget(self._ledger_dot)
        self._info = QLabel("", self._strip)
        self._info.setAlignment(Qt.AlignCenter)
        self._info.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._info.setFont(chandler42(size_px=self._INFO_FONT_PX))
        self._info.setStyleSheet(f"color: {Fam.textPrimary};")
        strip_layout.addWidget(self._info, stretch=1)
        strip_layout.addSpacing(24)   # mirror the dot so the whisper stays centred
        self.set_ledger_state("off")
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
            btn.clicked.connect(lambda _c=False, n=name: self.feature_clicked.emit(n))
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

    def set_ledger_state(self, state) -> None:
        """Light the Ledger status dot — three states:
          'live'    green — synced to the cloud Ledger (calm 'on')
          'pending' amber — saved on board, syncing (or waiting for the line to clear)
          'off'     RED   — no cloud connection; bright + large so it can't be missed
        A legacy bool is accepted (True -> live, False -> off) for safety."""
        if isinstance(state, bool):
            state = "live" if state else "off"
        self._ledger_state = state
        col = {"live": self._LEDGER_GREEN, "pending": self._LEDGER_AMBER,
               "off": self._LEDGER_RED}.get(state, self._LEDGER_RED)
        tip = {"live": "Ledger: live — synced to the cloud",
               "pending": "Ledger: saving on board, syncing when the line clears",
               "off": "Ledger: OFF — no cloud connection (progress still safe on board)"}.get(state, "")
        # OFF is loud: bright red AND considerably larger than the calm green, so a
        # dropped connection catches the eye at a glance rather than hiding.
        f = self._ledger_dot.font()
        f.setPointSize(20 if state == "off" else 12)
        self._ledger_dot.setFont(f)
        self._ledger_dot.setStyleSheet(f"color: {col}; background: transparent;")
        self._ledger_dot.setToolTip(tip)

    def set_info(self, text: str):
        """Whisper a line into the bottom infobar strip."""
        self._info.setText(text)

    def spectral_pulse(self, message: str = "✦ ✧ ✦"):
        """A passive 'the ether answered' tick: flash the infobar gold and show
        a brief sparkle, then quietly restore the prior whisper. Confirms a full
        cloud round-trip (the Sheets ping-pong) without spilling system logs into
        the UI — Intricate's meov colour-pulse, one-shot and in gold."""
        prior = self._info.text()
        self._info.setText(message)

        anim = QVariantAnimation(self)
        anim.setStartValue(QColor(Fam.textPrimary))
        anim.setKeyValueAt(0.5, QColor(self._PULSE_GOLD))
        anim.setEndValue(QColor(Fam.textPrimary))
        anim.setDuration(self._PULSE_MS)
        anim.valueChanged.connect(
            lambda c: self._info.setStyleSheet(f"color: {c.name()};"))
        anim.start()
        self._pulse_anim = anim   # keep a ref so it isn't GC'd mid-flash

        def _restore():
            self._info.setStyleSheet(f"color: {Fam.textPrimary};")
            if self._info.text() == message:   # only if nothing newer arrived
                self._info.setText(prior)
        QTimer.singleShot(self._PULSE_HOLD_MS, _restore)

    def toggle_collapse(self):
        """Slide the buttons away (collapse to the strip) or bring them back."""
        self._collapsed = not self._collapsed
        self._buttons_row.setVisible(not self._collapsed)
        self.strip_clicked.emit()

    def restyle(self):
        """Re-tint from the live family palette (settings watcher → reload)."""
        self.setStyleSheet(f"background-color: {Fam.windowBg};")
        self._info.setStyleSheet(f"color: {Fam.textPrimary};")
        self.set_ledger_state(self._ledger_state)   # re-tint the dot for its state
        for b in self._buttons:
            b.setStyleSheet(self._placeholder_qss())
