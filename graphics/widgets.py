#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - widgets.py the Sierra chrome — title bar, scene view, narrative, interaction
-The chrome that holds the wonder, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from graphics.Theme import Theme


# ─────────────────────────────────────────────────────────────────────────────
# Title bar — "GENTLE ADVENTURES, 03 (Cont.)" style strip across the top
# ─────────────────────────────────────────────────────────────────────────────


class TitleBar(QWidget):
    """The family-signature frameless title strip — ported from Intricate.

    Layout:  [ ✦ curtains | (infobar lives here) | centered title | – □ ✕ ]

    Brand/curtains button rolls the window up into this strip and back out;
    minimize / maximize / exid controls on the right; drag anywhere to move;
    double-click the LEFT half to toggle fullscreen (kept off the right so it
    never clashes with the control cluster — same reasoning as Intricate's
    hidden gesture). The OS titlebar is hidden, so this bar is the only handle.
    """

    curtains_clicked = Signal()    # roll up into the strip / expand back out

    _BTN_W = 46
    _BAR_H = 56

    def __init__(self):
        super().__init__()
        self.setFixedHeight(self._BAR_H)
        self.setStyleSheet(f"background-color: {Theme.title_bg};")

        # ── brand / curtains button (far left) ──
        self._btn_curtains = self._control(
            "✦", self.curtains_clicked.emit,
            tooltip="Roll the window up into this strip — click again to expand",
        )

        self._label = QLabel("GENTLE ADVENTURES")
        self._label.setAlignment(Qt.AlignCenter)
        # Click-through so a press over the title text still drags the window.
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        font = QFont()
        font.setPointSize(Theme.title_font_pt)
        font.setBold(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        self._label.setFont(font)
        self._label.setStyleSheet(f"color: {Theme.title_text};")

        # 2-button-wide spacer so that, with 1 curtains button on the left and
        # the 3-button cluster on the right, the title sits dead-center.
        left_spacer = QWidget()
        left_spacer.setFixedWidth(self._BTN_W * 2)
        left_spacer.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._btn_min = self._control("–", self._on_minimize, tooltip="Minimize")
        self._btn_max = self._control("□", self._on_maximize, tooltip="Maximize")
        self._btn_close = self._control(
            "✕", self._on_close, close=True,
            tooltip="Exid, not a typo.  It's an exit button named exid",
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._btn_curtains)
        layout.addWidget(left_spacer)
        layout.addWidget(self._label, stretch=1)
        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_max)
        layout.addWidget(self._btn_close)

        self._drag_pos = None

    # ── window controls ──────────────────────────────────────────────────────

    def _control(self, glyph: str, slot, close: bool = False, tooltip: str = "") -> QPushButton:
        btn = QPushButton(glyph)
        btn.setFixedSize(self._BTN_W, self._BAR_H)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        if tooltip:
            btn.setToolTip(tooltip)
        hover_bg = "#c0392b" if close else Theme.button_bg_hover
        hover_fg = "#ffffff" if close else Theme.button_text
        btn.setStyleSheet(
            "QPushButton {"
            f"  background: transparent; color: {Theme.title_text};"
            "   border: none; font-size: 15px; font-family: 'Segoe UI Symbol'; }"
            f"QPushButton:hover {{ background: {hover_bg}; color: {hover_fg}; }}"
        )
        btn.clicked.connect(slot)
        return btn

    def _on_minimize(self):
        self.window().showMinimized()

    def _on_maximize(self):
        w = self.window()
        if w.isMaximized():
            w.showNormal()
            self._btn_max.setText("□")    # □
        else:
            w.showMaximized()
            self._btn_max.setText("❐")    # ❐ (restore)

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
            if w.isMaximized():
                # Dragging a maximized window restores it, then follows the cursor.
                w.showNormal()
                self._btn_max.setText("□")
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

    def set_title(self, text: str):
        self._label.setText(text)


# ─────────────────────────────────────────────────────────────────────────────
# Scene view — square scene image with loading and error states
# ─────────────────────────────────────────────────────────────────────────────


class SceneView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(560)
        self.setStyleSheet(f"background-color: {Theme.scene_placeholder_bg};")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            f"color: {Theme.scene_placeholder_text}; "
            f"background-color: {Theme.scene_placeholder_bg};"
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
        self.setStyleSheet(f"background-color: {Theme.narrative_bg};")

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        font = QFont()
        font.setPointSize(Theme.narrative_font_pt)
        self._text.setFont(font)
        self._text.setStyleSheet(f"color: {Theme.narrative_text};")

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
            self._verified.setStyleSheet(f"color: {Theme.verified_text};")
        elif verified is False:
            self._verified.setText("○ not yet detected — try the step on your machine")
            self._verified.setStyleSheet(f"color: {Theme.narrative_dim};")
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
        self.setStyleSheet(f"background-color: {Theme.interaction_bg};")

        self._buttons_row = QHBoxLayout()
        self._buttons_row.setSpacing(10)

        self._parser = QLineEdit()
        self._parser.setPlaceholderText("✦ ask the ship anything ✦")
        self._parser.setStyleSheet(
            f"QLineEdit {{ "
            f"background-color: {Theme.parser_bg}; "
            f"color: {Theme.parser_text}; "
            f"border: 1px solid {Theme.parser_border}; "
            f"border-radius: 16px; "
            f"padding: 8px 16px; "
            f"font-size: 13pt; "
            f"}}"
            f"QLineEdit:focus {{ border: 1px solid {Theme.button_border}; }}"
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
                f"background-color: {Theme.button_bg}; "
                f"color: {Theme.button_text}; "
                f"border: 1px solid {Theme.button_border}; "
                f"border-radius: 14px; "
                f"padding: 8px 18px; "
                f"font-size: 12pt; "
                f"}}"
                f"QPushButton:hover {{ background-color: {Theme.button_bg_hover}; }}"
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
