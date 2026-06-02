#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - weather.py the psychological-weather overlay
-Soft rain that reads the room and drifts on a wind that keeps changing its mind, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# A self-contained citizen (like scene_map.py and lantern.py): a transparent,
# click-through QPainter overlay that paints gentle weather behind/over the body.
#
# It is a faithful 2D translation of Digital Ruby's Unity BaseRainScript — the
# old experiment that "proved beautiful". The mapping, line-for-line:
#   • RainIntensity (0..1) ............ self._target / self._level (the one knob)
#   • RainFallEmissionRate            . target droplet count  = MAX_DROPS * level
#       = (maxParticles/lifetime)*I    (CheckForRainChange / RainFallEmissionRate)
#   • RainMistThreshold = 0.5 ......... MIST_THRESHOLD; below it, no fog
#   • MistEmissionRate  ∝ I*I ......... fog opacity ramps with level² above thresh
#   • WindSpeedRange / WindChangeInterval(5,30s) . a new wind target every 5..30s,
#       lerped toward smoothly (UpdateWind's nextWindTime + Random.Range)
#   • LoopingAudioSource volume Mathf.Lerp . we lerp the INTENSITY itself, so a
#       mood shift eases in like a tide rather than snapping on.
#
# The only public surface the window needs: set_intensity(0..1), optional
# set_palette(QColor) for the vibe-tinted droplets, and start()/stop().

from __future__ import annotations

import random

from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QPen, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget

# ── tunables (kept gentle on purpose — this is ambience, not a storm window) ──
_FPS = 30
_TICK_MS = int(1000 / _FPS)
_MAX_DROPS = 220          # the droplet budget at full intensity (emission ceiling)
_MIST_THRESHOLD = 0.5     # RainMistThreshold — fog only appears above this
_MIST_MAX_ALPHA = 46      # ceiling alpha for the fog gradient (soft, never opaque)
_DROP_MAX_ALPHA = 120     # ceiling alpha for a near droplet (parallax scales it down)
_WIND_MAX = 2.6           # px/tick horizontal drift at depth 1 (the slant amount)
_LEVEL_LERP = 0.045       # how fast intensity eases toward its target (the tide)
_WIND_LERP = 0.02         # how fast wind eases toward its new target (slower still)

# A soft pastel default — lavender-blue, the "reflective morning" tint. The vibe
# layer overrides this via set_palette (sun-pastel for high gusto, etc.).
_DEFAULT_TINT = QColor(196, 206, 240)


class _Drop:
    """One falling streak. depth (0..1) drives parallax: near drops are longer,
    faster, brighter and feel the wind more; far drops whisper in the back."""

    __slots__ = ("x", "y", "depth", "length", "speed")

    def __init__(self, w: int, h: int):
        self.respawn(w, h, fresh=True)

    def respawn(self, w: int, h: int, fresh: bool = False) -> None:
        self.x = random.uniform(0, max(1, w))
        # fresh drops scatter across the height so rain doesn't "start" in a line;
        # recycled drops re-enter just above the top edge.
        self.y = random.uniform(-40, h) if fresh else random.uniform(-40, -8)
        self.depth = random.uniform(0.35, 1.0)
        self.length = 7 + self.depth * 15
        self.speed = (3.5 + self.depth * 9.0)


class WeatherOverlay(QWidget):
    """Click-through ambient weather. Paints nothing at intensity 0 and sleeps
    its timer once the last drop has fallen, so an idle clear sky costs nothing.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # A "glass pane" child overlay: click-through (never steals a click from
        # the scene/narrative beneath) and never erases its own background, so the
        # siblings below show through wherever no droplet is painted. Painted
        # alpha composites against the shared backing store — true transparency
        # without promoting to a native window.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._tint = QColor(_DEFAULT_TINT)
        self._level = 0.0          # current eased intensity
        self._target = 0.0         # where intensity is heading
        self._drops: list[_Drop] = []

        # wind (the slant), eased toward a target that re-rolls every 5..30s
        self._wind = 0.0
        self._wind_target = 0.0
        self._ticks = 0
        self._next_wind_tick = self._roll_wind_interval()

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ── public knobs ────────────────────────────────────────────────────────

    def set_intensity(self, value: float) -> None:
        """The master dial (Unity's RainIntensity). The level eases toward it —
        a mood change arrives like weather, not like a light switch."""
        self._target = max(0.0, min(1.0, float(value)))
        if self._target > 0.0 and not self._timer.isActive():
            self._timer.start()

    def set_palette(self, color: QColor) -> None:
        """Tint the droplets/fog to match the current vibe (sun-pastel for high
        gusto, deep lavender for quiet reflection). Eased shifts are the window's
        job; here we just adopt the colour."""
        if color is not None and color.isValid():
            self._tint = QColor(color)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # ── the breathing loop ────────────────────────────────────────────────────

    def _roll_wind_interval(self) -> int:
        # WindChangeInterval (5..30s) → ticks. Re-rolled each time wind retargets.
        return int(random.uniform(5.0, 30.0) * _FPS)

    def _tick(self) -> None:
        self._ticks += 1

        # ease intensity toward its target (LoopingAudioSource's volume lerp)
        self._level += (self._target - self._level) * _LEVEL_LERP
        if abs(self._level - self._target) < 0.003:
            self._level = self._target

        # UpdateWind: every 5..30s pick a fresh drift target, then ease toward it
        if self._ticks >= self._next_wind_tick:
            self._wind_target = random.uniform(-_WIND_MAX, _WIND_MAX)
            self._next_wind_tick = self._ticks + self._roll_wind_interval()
        self._wind += (self._wind_target - self._wind) * _WIND_LERP

        w = max(1, self.width())
        h = max(1, self.height())

        # RainFallEmissionRate: how many drops should be alive right now
        target_n = int(_MAX_DROPS * self._level)
        while len(self._drops) < target_n:
            self._drops.append(_Drop(w, h))

        # advance every drop; recycle the ones that fall past the floor (but only
        # back into rotation if we still want that many — else let them retire)
        survivors: list[_Drop] = []
        for d in self._drops:
            d.y += d.speed
            d.x += self._wind * d.depth
            if d.y - d.length > h or d.x < -40 or d.x > w + 40:
                if len(survivors) < target_n:
                    d.respawn(w, h)
                    survivors.append(d)
                # else: drop retires — rain thinning out as the mood lifts
            else:
                survivors.append(d)
        self._drops = survivors

        # an idle, clear sky costs nothing: park the timer once truly at rest
        if self._target <= 0.0 and not self._drops and self._level <= 0.003:
            self._level = 0.0
            self._timer.stop()

        self.update()

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if self._level <= 0.001 and not self._drops:
            return
        h = self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # ── mist / fog: only above RainMistThreshold, opacity ramps with level²
        if self._level > _MIST_THRESHOLD:
            t = (self._level - _MIST_THRESHOLD) / (1.0 - _MIST_THRESHOLD)
            alpha = int(_MIST_MAX_ALPHA * t * t)  # the I*I from MistEmissionRate
            if alpha > 0:
                fog = QColor(self._tint)
                grad = QLinearGradient(0, 0, 0, h)
                top = QColor(fog); top.setAlpha(0)
                bot = QColor(fog); bot.setAlpha(alpha)
                grad.setColorAt(0.0, top)
                grad.setColorAt(1.0, bot)
                p.fillRect(self.rect(), grad)

        # ── droplets: soft slanted streaks, near ones brighter (parallax)
        for d in self._drops:
            a = int(_DROP_MAX_ALPHA * d.depth * min(1.0, self._level * 1.4))
            if a <= 0:
                continue
            col = QColor(self._tint); col.setAlpha(a)
            pen = QPen(col)
            pen.setWidthF(0.8 + d.depth * 1.1)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            # streak runs along the fall, slanted by the wind it's feeling
            dx = self._wind * d.depth * 1.6
            p.drawLine(QPointF(d.x, d.y), QPointF(d.x - dx, d.y - d.length))
        p.end()
