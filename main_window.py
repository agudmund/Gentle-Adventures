#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - main_window.py top-level window, setup wizard, and scene orchestrator
-We frame the new world and welcome the player home, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve, QRect, QTimer, QEvent
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QWidget,
    QSystemTrayIcon,
)

from data.quest import all_scenes, first_scene_id, get_scene, reload_quest, switch_narrative, NO_NPU_NOTE, NPU_PROBING_NOTE
from pretty_widgets.graphics.Theme import Theme as Fam
from graphics.widgets import BottomToolbar, InteractionBar, NarrativePanel, ResizeGrip, SceneView, TitleBar
from graphics.scene_map import SceneMap
from graphics.sidebar import Sidebar
from graphics.weather import WeatherOverlay
from shared_braincell.gemini_image import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiImageClient,
    load_api_key,
    load_selected_model,
    pick_default_image_model,
    save_api_key,
    save_selected_model,
    validate_key,
)
from utils.probe import probe_fastflowlm, probe_npu, raw_hardware_spec, resolve_flm
from utils.oracle import Oracle
from utils.scene_cache import SceneCache
from utils.sheets import SheetsClient, SheetsError
from utils.player_state import PlayerStateStore
from utils.text import build_text_backend
from utils.sticker_loot import award_for_scene
from utils.lantern import LanternWatch
from utils.logger import get_logger

logger = get_logger("gentle")

STUDIO_URL = "https://aistudio.google.com/apikey"


# ─────────────────────────────────────────────────────────────────────────────
# Worker threads — keep network calls off the UI thread
# ─────────────────────────────────────────────────────────────────────────────


class KeyValidationWorker(QThread):
    succeeded = Signal(list)  # accessible image models
    failed = Signal(str, bool)  # error message, is_auth_error

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            models = validate_key(self.api_key)
            self.succeeded.emit(models)
        except GeminiAuthError as e:
            self.failed.emit(str(e), True)
        except GeminiAPIError as e:
            self.failed.emit(str(e), False)


class SceneRequestWorker(QThread):
    image_ready = Signal(bytes, str)
    image_failed = Signal(str, str)

    def __init__(self, client: GeminiImageClient, prompt: str, scene_id: str,
                 reference_path: Path | None = None):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.scene_id = scene_id
        self.reference_path = reference_path

    def run(self):
        import time
        seed = (f", seeded from {self.reference_path.name}"
                if self.reference_path and self.reference_path.exists() else "")
        logger.info(
            f"[image] requesting '{self.scene_id}' via {self.client.model} "
            f"(prompt {len(self.prompt)} chars{seed}) — painter is painting"
        )
        t0 = time.perf_counter()
        try:
            data = self.client.generate(self.prompt, reference_path=self.reference_path)
            logger.info(
                f"[image] '{self.scene_id}' delivered in "
                f"{time.perf_counter() - t0:.1f}s ({len(data)} bytes)"
            )
            self.image_ready.emit(data, self.scene_id)
        except (GeminiAuthError, GeminiAPIError) as e:
            logger.warning(
                f"[image] '{self.scene_id}' failed after "
                f"{time.perf_counter() - t0:.1f}s: {e}"
            )
            self.image_failed.emit(str(e), self.scene_id)


class PlayerStateSyncWorker(QThread):
    """Flush (or hydrate) the local-first PlayerStateStore against the Sheet, off
    the UI thread. `synced(reached)` reports whether the cloud round-trip
    succeeded; the store keeps any unsynced changes safe on board regardless, so
    the quest never waits and a disconnect never costs progress."""

    synced = Signal(bool)   # True if the Sheet was reached and pending cleared

    def __init__(self, store, hydrate: bool = False):
        super().__init__()
        self.store = store
        self.hydrate = hydrate

    def run(self):
        try:
            ok = self.store.hydrate() if self.hydrate else self.store.flush()
            self.synced.emit(bool(ok))
        except Exception as e:
            logger.info(f"[state] sync worker error: {e}")
            self.synced.emit(False)


class TextWorker(QThread):
    """Run a swappable-backend text completion off the UI thread. `tag` names the
    caller (e.g. 'oracle') so one path can serve many features."""

    text_ready = Signal(str, str)    # (text, tag)
    text_failed = Signal(str, str)   # (error, tag)

    def __init__(self, backend, messages, system=None, max_tokens=1024,
                 temperature=None, tag=""):
        super().__init__()
        self.backend = backend
        self.messages = messages
        self.system = system
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.tag = tag

    def run(self):
        try:
            out = self.backend.complete(
                self.messages, system=self.system,
                max_tokens=self.max_tokens, temperature=self.temperature)
            self.text_ready.emit(out, self.tag)
        except Exception as e:
            self.text_failed.emit(str(e), self.tag)


class NpuProbeWorker(QThread):
    """Feel for the ship's silicon OFF the UI thread. Both probe_npu() (the
    friendly engine descriptor) and raw_hardware_spec() (for the Oracle's
    calibration line) are PowerShell subprocess calls with a ~1-2s cold start —
    run on the UI thread they froze the first NPU scene's swap solid. This runs
    them once, off-thread, and hands back (engine | None, spec_dict). The spec is
    only fetched when there's actually an NPU to talk about."""

    probed = Signal(object, object)   # (engine: str | None, spec: dict)

    def run(self):
        try:
            engine = probe_npu()
        except Exception as e:
            logger.info(f"[npu] probe worker error: {e}")
            engine = None
        spec: dict = {}
        if engine:
            try:
                spec = raw_hardware_spec()
            except Exception as e:
                logger.info(f"[npu] hardware-spec worker error: {e}")
                spec = {}
        self.probed.emit(engine, spec)


_LEDGER_PULSE_MS = 10000   # realtime loop heartbeat: re-pull the live Quest_Log (ms)


class LedgerRefreshWorker(QThread):
    """Re-pull the live Quest_Log off the UI thread — the realtime loop's heartbeat
    fetch. A Sheet edit made mid-session (by the captain in a browser, or one day by
    an external daemon evolving the story) flows into the running game. Emits the
    reload result dict {'changed','quarantined','source','version'} — last-good is
    never cleared on a failed/empty/reverting pull. See State Sync v2.md."""

    refreshed = Signal(object)   # the reload result dict

    def run(self):
        try:
            result = reload_quest()
        except Exception as e:
            logger.info(f"[ledger] refresh worker error: {e}")
            result = {"changed": False, "quarantined": False}
        self.refreshed.emit(result)


class OracleWorker(QThread):
    """Put one question to the local NPU oracle (flm's llama) off the UI thread. The
    first ask wakes the server (model load onto the NPU, a few seconds) — that's the
    'oracle stirs awake' beat; later asks are quick. Emits answered(text) or
    failed(reason); never blocks the quest."""

    answered = Signal(str)
    failed = Signal(str)

    def __init__(self, oracle, question: str, system: str = ""):
        super().__init__()
        self.oracle = oracle
        self.question = question
        self.system = system

    def run(self):
        try:
            self.answered.emit(self.oracle.ask(self.question, system=self.system))
        except Exception as e:
            self.failed.emit(str(e))


class WorkerRegistry:
    """Tracks live QThreads so several run concurrently without the old single-
    slot clobber — validation, scene render, ledger sync (and soon the Oracle,
    stickers, sandbox) all coexist. Reaps each on finish; stop_all() drains them
    on shutdown.

    No quit/wait when superseding work: a blocking urllib call can't be
    interrupted anyway, and the callers' scene-id guards already ignore a stale
    result, so a superseded scene render simply lands and is dropped — without
    the freeze the old quit()+wait() caused on the UI thread.
    """

    def __init__(self, on_busy_changed=None):
        self._workers: list = []
        self._quiet: set = set()   # workers that don't drive the 'working' meter
        # Called with True when the first LOUD worker starts, False when the last
        # finishes — drives the sidebar's 'working' meter.
        self.on_busy_changed = on_busy_changed

    def _loud(self) -> int:
        return sum(1 for w in self._workers if w not in self._quiet)

    def run(self, worker, quiet: bool = False) -> None:
        # quiet=True: tracked + drained on shutdown like any worker, but doesn't
        # flash the 'working' meter — for background pulses (the realtime Ledger
        # heartbeat) rather than a painter at work.
        was_busy = self._loud() > 0
        self._workers.append(worker)
        if quiet:
            self._quiet.add(worker)
        worker.finished.connect(lambda: self._reap(worker))
        worker.start()
        if not quiet and not was_busy and self.on_busy_changed:
            self.on_busy_changed(True)

    def _reap(self, worker) -> None:
        try:
            self._workers.remove(worker)
        except ValueError:
            pass
        self._quiet.discard(worker)
        if self._loud() == 0 and self.on_busy_changed:
            self.on_busy_changed(False)

    def stop_all(self) -> None:
        for w in list(self._workers):
            try:
                if w.isRunning():
                    w.quit()
                    w.wait(2000)
            except RuntimeError:
                pass  # already torn down


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────


class GentleAdventuresApp(QMainWindow):
    # Leave a sliver below a maximized window so an auto-hide taskbar can still
    # be triggered and never gets occluded — matches Intricate's constant.
    _TASKBAR_TRIGGER_MARGIN = 5

    def __init__(self, settings: dict, app_dir: Path):
        super().__init__()
        self.settings = settings
        self.app_dir = app_dir

        scenes_subdir = settings.get("paths", {}).get("scenes_dir", "scenes")
        self.scenes_dir = app_dir / scenes_subdir
        # Image-state manager — checks/loads/stores baked scene art so a scene
        # is painted once and reloaded forever (the cache is committed to the
        # repo, so it travels with a clone and survives close/reopen).
        self.scene_cache = SceneCache(self.scenes_dir)

        default_model = settings.get("gemini", {}).get("model", "gemini-2.5-flash-image")
        selected = load_selected_model(app_dir) or default_model
        self.image_client = GeminiImageClient(app_dir=app_dir, model=selected)

        self._workers = WorkerRegistry(on_busy_changed=self._on_workers_busy_changed)
        self.current_scene: dict | None = None
        self._visited: set[str] = set()   # scene ids reached — gates the map
        self._oracle_summoned = False     # Hardware Oracle fires once per session
        self._oracle_line = ""            # cached calibration line once it arrives
        self._npu_probed = False          # NPU probe is cached (it can't change mid-session)
        self._npu_engine: str | None = None
        self._earned_stickers: set[str] = set()   # scene ids already rewarded (session dedupe)
        # Ledger write-back: push Player_State up as the captain plays. Built
        # once; None (silently) when the proxy isn't configured — contextual
        # absence, never an error banner. The sync runs off the UI thread.
        try:
            self.sheets: SheetsClient | None = SheetsClient()
        except SheetsError as e:
            self.sheets = None
            # Clear, actionable, once at startup — this is a graceful fallback,
            # NOT an error: the bundled quest carries the game. Spelled out so a
            # glance at the log says exactly what's off and how to turn it on.
            logger.info(
                "[sheets] LEDGER OFF: live cloud sync + Player_State heartbeat are "
                "disabled; running on the bundled quest (graceful fallback, not an "
                "error). To enable, the in-app 'Opening the Ledger' setup handles it at "
                "launch (paste the web-app URL + token, no relaunch needed), or set "
                f"GA_WebApp + GA_Ledger in the environment. Setup: Documents/Sheets Ledger Setup.md. [why: {e}]"
            )
        # Player_State logbook: local-first cache with the Sheet as the source of
        # truth. Every state write lands here instantly (progress is never lost to
        # a disconnect); flush/hydrate sync against the cloud off the UI thread.
        self.player_state = PlayerStateStore(self.sheets, app_dir)
        # The on-device oracle (flm's local llama) for "ask the ship" — built lazily;
        # nothing starts until the first question wakes the server. See utils/oracle.py.
        self.oracle = Oracle()
        # Swappable text backend (Claude default, Gemini on demand) for the ship's
        # voice — Oracle, vibe, ghost-repair, missions. Built once; None silently
        # if misconfigured (contextual absence). Calls run via the worker registry.
        try:
            self.text_backend = build_text_backend(settings, app_dir)
        except Exception as e:
            self.text_backend = None
            logger.info(f"[text] backend unavailable: {e}")
        self.available_models: list[str] = []
        self.phase: str = "quest"  # set properly in _start
        self._curtains_collapsed = False
        self._curtain_anim = None
        self._is_maxed = False
        self._restore_geom_max = None
        self._quitting = False            # tray "Exit" / Ctrl-C set this; ✕ restarts
        self._restore_maximized = False   # set by _restore_window_geometry
        self._window_state_path = app_dir / "window_state.json"

        win_cfg = settings.get("window", {})
        self.setWindowTitle(win_cfg.get("title", "Gentle Adventures"))
        self._restore_window_geometry(win_cfg)
        self._apply_window_theme()
        # Frameless + always-on-top: hide the OS titlebar (our custom TitleBar
        # provides controls + drag) and float above other windows — the family
        # default (Intricate, The Majestic, The Settlers all set this). No
        # overlap headache: each app's titlebar is the only persistent chrome,
        # and the curtains gesture rolls the window down to a thin strip when
        # it needs to get out of the way.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self._build_layout()
        # Resizable from the bottom-right (ported from Intricate's grip): a
        # min-size floor + a corner handle that drags the geometry. No OS resize
        # cursor (family convention) — the painted glyph is the affordance.
        self.setMinimumSize(480, 360)
        self.resize_grip = ResizeGrip(self, parent=self.centralWidget())
        self.resize_grip.raise_()
        self._position_resize_grip()
        self._setup_system_tray()
        self._start()

        # Re-apply last session's maximized state once the loop is running
        # (work_area needs the shown window's screen).
        if self._restore_maximized:
            QTimer.singleShot(0, self.maximize_window)

    # ───── theme ─────

    def _apply_window_theme(self):
        """Paint the window chrome from the shared family palette.

        window_bg / primary_border / text_primary all flow from The Settlers'
        Color Picker via the shared settings.toml, so a tweak there ripples into
        Gentle Adventures exactly as it does across the rest of the family
        (Window Bg #282828 by default).
        """
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {Fam.windowBg}; }}"
            f"QToolTip {{ background: {Fam.windowBg}; color: {Fam.textPrimary};"
            f" border: 1px solid {Fam.primaryBorder}; padding: 5px 9px; }}"
        )

    def _reapply_theme(self):
        """Live re-tint: the settings watcher fires this after Theme.reload(),
        so an external palette edit repaints the window and titlebar at once."""
        self._apply_window_theme()
        if hasattr(self, "title_bar"):
            self.title_bar.restyle()
        if hasattr(self, "bottom_toolbar"):
            self.bottom_toolbar.restyle()
        if hasattr(self, "scene_view"):
            self.scene_view.restyle()
        if hasattr(self, "scene_map"):
            self.scene_map.restyle()
        if hasattr(self, "sidebar"):
            self.sidebar.restyle()
        if hasattr(self, "narrative"):
            self.narrative.restyle()
        if hasattr(self, "resize_grip"):
            self.resize_grip.restyle()

    def _on_workers_busy_changed(self, busy: bool) -> None:
        """Worker registry crossed idle<->busy: fade the sidebar 'working' meter
        in and breathe while anything runs, out when all's quiet."""
        if hasattr(self, "sidebar"):
            self.sidebar.set_working(busy)

    # ───── window resize grip ─────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_grip()

    def _position_resize_grip(self):
        """Keep the bottom-right resize handle pinned to the corner, and tuck it
        away while the curtains are rolled up (no resizing a collapsed strip)."""
        grip = getattr(self, "resize_grip", None)
        if grip is None:
            return
        if hasattr(self, "_body") and not self._body.isVisible():
            grip.hide()
            return
        c = self.centralWidget()
        if c is None:
            return
        m = 3
        grip.move(c.width() - grip.width() - m, c.height() - grip.height() - m)
        grip.show()
        grip.raise_()

    # ───── narrative swap ─────

    def _on_narrative_changed(self, key: str):
        """Titlebar narrative selector changed -> point the Ledger at that
        narrative's Quest_Log tab and restart it at its opening scene. (No-op for
        a single registered narrative; live once a second tab is dropped in.)"""
        if not key:
            return
        switch_narrative(key)
        try:
            self.player_state.set("current_scene", first_scene_id())
        except Exception:
            pass
        self._load_scene(first_scene_id())
        logger.info(f"[narrative] switched to '{key}'")

    # ───── layout ─────

    def _build_layout(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.curtains_clicked.connect(self.toggle_curtains)
        self.title_bar.narrative_changed.connect(self._on_narrative_changed)
        layout.addWidget(self.title_bar)

        # Everything below the titlebar lives in one container so the curtain
        # roll can hide it in a single move — and, crucially, hide it on a
        # *delay* so it stays visible for the first stretch of the roll (the
        # "oompf"). Grouping also means no stray sliver peeks past the strip.
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.scene_view = SceneView()
        # The scene navigator is a standalone, swappable module (graphics/
        # scene_map.py). It shares the right pane with the scene image via a
        # QStackedWidget — the window flips between them; neither knows about
        # the other. Plug-and-play: delete the module + this wiring and it's gone.
        self.scene_map = SceneMap()
        # Populated lazily when the map is first opened (_toggle_map), so window
        # construction never blocks on a live Quest_Log fetch.
        self.scene_map.scene_picked.connect(self._on_map_pick)
        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(self.scene_view)   # index 0 — the painted scene
        self._right_stack.addWidget(self.scene_map)    # index 1 — the jump map

        self.narrative = NarrativePanel()
        self.interaction = InteractionBar()
        self.interaction.choice_made.connect(self._on_choice)
        self.bottom_toolbar = BottomToolbar()
        self.bottom_toolbar.feature_clicked.connect(self._on_feature)
        self.sidebar = Sidebar()   # left rail — hosts the lower-corner control grid

        # Visual-novel split: narrative column on the left, the right pane (scene
        # image OR jump map, via the stack) on the right. Choices/parser and the
        # bottom toolbar span full width beneath it. 1:1 stretch is a taste knob.
        self._split = QWidget()
        split_row = QHBoxLayout(self._split)
        split_row.setContentsMargins(0, 0, 0, 0)
        split_row.setSpacing(0)
        split_row.addWidget(self.sidebar)                  # left rail (fixed width)
        split_row.addWidget(self.narrative, stretch=1)
        split_row.addWidget(self._right_stack, stretch=1)

        body_layout.addWidget(self._split, stretch=1)
        body_layout.addWidget(self.interaction)
        body_layout.addWidget(self.bottom_toolbar)
        # Hair-thin blank strip pinned to the very bottom — the curtain's hem
        # weight. On roll-up everything above hides at once (top→bottom); this
        # sliver is the only thing left to drop, so its slightly-late motion is
        # what the retina reads as weight — without the busy parser/buttons/
        # toolbar lingering through the curl.
        self._curtain_weight = QWidget()
        self._curtain_weight.setFixedHeight(3)
        self._curtain_weight.setStyleSheet(f"background-color: {Fam.windowBg};")
        body_layout.addWidget(self._curtain_weight)
        layout.addWidget(self._body, stretch=1)

        self.setCentralWidget(central)

        # ── Psychological Weather (System 2) ─────────────────────────────────
        # A click-through ambient overlay riding over the narrative+scene row.
        # Its one public knob is set_intensity(0..1); Phase 1 drives it via the
        # free-text 'rain'/'storm'/'clear'/'weather N' words, Phase 2 from the
        # Gemini-read vibe vector. A standalone citizen (graphics/weather.py) —
        # delete the module + this wiring and the weather is simply gone.
        self._weather = WeatherOverlay(self._split)
        self._weather.setGeometry(self._split.rect())
        self._weather.raise_()
        self._weather.show()
        self._split.installEventFilter(self)  # keep it sized to the row

        # Hydrate the logbook from the Ledger at startup (Sheet = source of truth),
        # off-thread; the dot rides the result. No proxy -> dim + a soft whisper.
        if self.sheets:
            self._set_ledger_indicator("pending")   # connecting...
            hydr = PlayerStateSyncWorker(self.player_state, hydrate=True)
            hydr.synced.connect(self._on_state_hydrated)
            self._workers.run(hydr)
        else:
            self._set_ledger_indicator("off")

        # ── Realtime state loop ──────────────────────────────────────────────
        # The Sheet is the live source of truth, so poll it on a gentle heartbeat:
        # every _LEDGER_PULSE_MS we re-pull Quest_Log off the UI thread and, if the
        # scene the captain is standing in changed under them, re-stream it in
        # place. This is what makes the quest dynamically editable WHILE it's played
        # — the groundwork for a story with no fixed ending, where an external
        # client can reshape the sheet and the running game answers. Sheet-only.
        self._ledger_refreshing = False
        if self.sheets:
            self._ledger_pulse = QTimer(self)
            self._ledger_pulse.timeout.connect(self._tick_ledger)
            self._ledger_pulse.start(_LEDGER_PULSE_MS)

    def eventFilter(self, obj, event):
        # Keep the weather overlay covering the narrative+scene row as it resizes.
        if obj is getattr(self, "_split", None) and event.type() == QEvent.Resize:
            if hasattr(self, "_weather"):
                self._weather.setGeometry(self._split.rect())
                self._weather.raise_()
        return super().eventFilter(obj, event)

    # ───── realtime state loop (the Sheet is canon, so the game watches it) ─────

    def changeEvent(self, event):
        # Pause/resume the realtime heartbeat with focus + window state, so a long
        # idle (or sleeping) session doesn't quietly burn Apps Script quota.
        if event.type() in (QEvent.ActivationChange, QEvent.WindowStateChange):
            self._update_ledger_pulse()
        super().changeEvent(event)

    def _update_ledger_pulse(self):
        """Run the heartbeat only while the window is active, un-minimised, and the
        curtains are open. On waking, pull once immediately so a re-focus shows the
        latest at once, then resume the steady pulse."""
        if not hasattr(self, "_ledger_pulse"):
            return
        awake = (self.isActiveWindow() and not self.isMinimized()
                 and not self._curtains_collapsed)
        if awake:
            if not self._ledger_pulse.isActive():
                self._tick_ledger()                       # pull fresh on wake
                self._ledger_pulse.start(_LEDGER_PULSE_MS)
        else:
            self._ledger_pulse.stop()

    def _tick_ledger(self):
        """Heartbeat: re-pull the live Quest_Log off the UI thread, unless a pull is
        already in flight (never stack network calls). Runs as a QUIET worker so it
        never flashes the 'working' meter — a background pulse, not a painter."""
        if self._ledger_refreshing or not self.sheets:
            return
        self._ledger_refreshing = True
        worker = LedgerRefreshWorker()
        worker.refreshed.connect(self._on_ledger_refreshed)
        self._workers.run(worker, quiet=True)

    def _on_ledger_refreshed(self, result):
        self._ledger_refreshing = False
        if isinstance(result, dict) and result.get("quarantined"):
            # A backward content edit was held back (the revert guard) — surface it
            # and keep the good version. The performer's intercom, not a silent swap.
            self.bottom_toolbar.set_info(
                "✦ a backward edit to the tale was held back — keeping the good version ✦")
            return
        if not (isinstance(result, dict) and result.get("changed")) or self.current_scene is None:
            return
        fresh = get_scene(self.current_scene["id"])
        if fresh is None:
            return
        cur = self.current_scene
        if (fresh.get("narrative") != cur.get("narrative")
                or fresh.get("choices") != cur.get("choices")
                or fresh.get("title") != cur.get("title")):
            logger.info(f"[ledger] live edit to scene '{fresh['id']}' — re-streaming in place")
            self._relive_scene(fresh)

    def _relive_scene(self, fresh: dict):
        """A scene's Sheet content changed under us (the live state machine moved):
        re-apply its title / narrative / choices in place. The narrative re-streams,
        so the edit arrives like weather; the art and the Ledger heartbeat writes are
        left untouched — only the words and the options shifted."""
        self.current_scene = fresh
        self.title_bar.set_title(fresh["title"])
        verify_kind = fresh.get("verify")
        if verify_kind == "npu":
            verified = self._npu_engine is not None
        else:
            verified = self._verify(verify_kind)
        if verify_kind == "npu" and not verified:
            narrative = fresh.get("narrative_absent") or (fresh["narrative"] + "\n\n" + NO_NPU_NOTE)
            choices = fresh.get("choices_absent") or fresh["choices"]
        else:
            narrative = fresh["narrative"]
            choices = fresh["choices"]
        self.narrative.set_text(narrative, verified=verified)
        self.interaction.set_choices(choices)

    # ───── curtains ─────

    def toggle_curtains(self):
        """Roll the window up into just its titlebar strip, or expand it back
        out — auto-maximizing to the taskbar-aware work area on expand. Mirrors
        Intricate's curtains gesture (animated geometry, no resize-grip)."""
        bar_h = self.title_bar.height()
        self.setMinimumHeight(0)  # allow shrinking below the natural minimum
        collapsing = not self._curtains_collapsed
        start = self.geometry()

        # Family roll timing: up snappy, down weighted, OutExpo easing — the
        # same feel as Intricate / The Majestic (windowRollTimingUp/Down).
        duration = Fam.windowRollTimingUp if collapsing else Fam.windowRollTimingDown
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(duration)
        anim.setEasingCurve(getattr(QEasingCurve, Fam.windowRollEasing, QEasingCurve.OutExpo))
        anim.setStartValue(start)
        anim.setEndValue(
            QRect(start.x(), start.y(), start.width(), bar_h) if collapsing
            else self.work_area()      # auto-maximize on expand
        )

        if collapsing:
            # Hide ALL body content immediately, in top→bottom order (so the
            # paint pipeline drops them in visual order — micro-timing that the
            # eye reads as a clean, deterministic curl). Nothing busy lingers:
            # narrative, scene pane, parser, choices, map buttons, toolbar — gone
            # at once. Only the hair-thin blank hem strip rides on, delay-hidden
            # with the body at 2/3 — its slightly-late drop is the whole "weight"
            # the retina needs (a seamstress's bottom-weight, simulated in 3px).
            self._split.hide()
            self.interaction.hide()
            self.bottom_toolbar.hide()
            hide_delay = max(1, int(duration * 2 / 3))
            QTimer.singleShot(hide_delay, self._body.hide)
        else:
            # Grow the blank hem back in first, then reveal the content LAST
            # (after the roll settles) so everything lays out / scales once, at
            # final size — not on every frame of the way out.
            self._body.show()
            QTimer.singleShot(duration, self._reveal_body_content)

        anim.start()
        self._curtain_anim = anim          # keep a ref so it isn't GC'd mid-roll
        self._curtains_collapsed = collapsing
        self._is_maxed = not collapsing    # the expanded strip fills the work area
        self.title_bar.reflect_maximized(self._is_maxed)
        self._update_ledger_pulse()        # curtains down -> pause the heartbeat

    def _reveal_body_content(self) -> None:
        """Re-show the body's content widgets after an expand settles (or on a
        maximize). Guarded so it's safe to call before _build_layout finishes."""
        for w in (getattr(self, "_split", None), getattr(self, "interaction", None),
                  getattr(self, "bottom_toolbar", None)):
            if w is not None:
                w.show()

    # ───── maximize (taskbar-aware work area, family-consistent) ─────

    def work_area(self) -> QRect:
        """The taskbar-aware work rectangle. Qt's availableGeometry already
        excludes a visible taskbar; trim _TASKBAR_TRIGGER_MARGIN off the bottom
        so an auto-hide taskbar's reveal zone stays reachable. This is the
        known-good baseline Intricate falls back to (it layers a 5-reader
        resolution consensus on top for driver-botch edge cases; the plain
        availableGeometry path is the default we share here)."""
        a = self.screen().availableGeometry()
        return QRect(a.x(), a.y(), a.width(),
                     max(1, a.height() - self._TASKBAR_TRIGGER_MARGIN))

    def is_window_maximized(self) -> bool:
        return self._is_maxed

    def maximize_window(self):
        if not self._is_maxed:
            self._restore_geom_max = self.geometry()
        # If we were rolled up, bring the body back before growing — otherwise
        # the window would expand to a blank strip.
        if self._curtains_collapsed and hasattr(self, "_body"):
            self._body.show()
            self._reveal_body_content()   # never leave content hidden from a prior roll
            self._curtains_collapsed = False
        self.setGeometry(self.work_area())
        self._is_maxed = True
        self.title_bar.reflect_maximized(True)

    def restore_window(self):
        if self._restore_geom_max is not None:
            self.setGeometry(self._restore_geom_max)
        self._is_maxed = False
        self.title_bar.reflect_maximized(False)

    def toggle_maximize(self):
        self.restore_window() if self._is_maxed else self.maximize_window()

    # ───── system tray ─────

    def _setup_system_tray(self) -> None:
        """System tray icon with a Show / Exit menu. The icon is playIcon —
        Gentle Adventures' brand mark, copied into icons/ from the family set."""
        self._tray_icon = QSystemTrayIcon(self)
        icon_path = self.app_dir / "icons" / "playIcon.ico"
        if icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self._tray_icon.setIcon(self.windowIcon())
        # Tooltip doubles as the Windows Personalization-panel display name.
        self._tray_icon.setToolTip("Gentle Adventures")

        try:
            from pretty_widgets.PrettyMenu import PrettyMenu
            tray_menu = PrettyMenu(self)
        except Exception:
            from PySide6.QtWidgets import QMenu
            tray_menu = QMenu(self)
        tray_menu.addAction("Show", self._restore_from_tray)
        tray_menu.addSeparator()
        tray_menu.addAction("Exit", self._quit_app)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

        # Self-heal the Personalization > Taskbar panel so the entry reads
        # "Gentle Adventures" with the playIcon mark instead of "Python" with
        # a stale snapshot. Silent no-op on failure — see Intricate's
        # Documents/Design/Icon Pipeline.md › The Brand Mark Refresh Chain.
        try:
            self._heal_systray_panel_metadata()
        except Exception:
            logger.debug("[systray] panel-metadata self-heal raised — continuing", exc_info=True)

    def _heal_systray_panel_metadata(self) -> None:
        """Write our identity to the two HKCU surfaces Windows reads for the
        systray Personalization panel: the AUMID metadata key and any matching
        NotifyIconSettings entry (snapshot PNG + tooltip). Idempotent, HKCU-only,
        non-fatal on every step."""
        import sys
        import winreg
        from PySide6.QtCore import QBuffer, QIODevice

        icon_path = self.app_dir / "icons" / "playIcon.ico"
        if not icon_path.exists():
            return

        try:
            aumid_key = r"Software\Classes\AppUserModelId\SingleSharedBraincell.GentleAdventures"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, aumid_key) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Gentle Adventures")
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(icon_path))
        except OSError:
            pass

        pixmap = QIcon(str(icon_path)).pixmap(32, 32)
        if pixmap.isNull():
            return
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        png_bytes = bytes(buf.data())
        buf.close()
        if not png_bytes:
            return

        my_exe = Path(sys.executable).name.lower()
        targets = {my_exe}
        if my_exe == "pythonw.exe":
            targets.add("python.exe")
        elif my_exe == "python.exe":
            targets.add("pythonw.exe")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Control Panel\NotifyIconSettings") as nis:
                i = 0
                while True:
                    try:
                        subname = winreg.EnumKey(nis, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(nis, subname, 0,
                                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                            try:
                                exe, _ = winreg.QueryValueEx(k, "ExecutablePath")
                            except FileNotFoundError:
                                continue
                            if not exe or Path(exe).name.lower() not in targets:
                                continue
                            winreg.SetValueEx(k, "InitialTooltip", 0, winreg.REG_SZ, "Gentle Adventures")
                            winreg.SetValueEx(k, "IconSnapshot", 0, winreg.REG_BINARY, png_bytes)
                    except OSError:
                        continue
        except OSError:
            pass

    def minimize_to_tray(self) -> None:
        """Hide the window into the system tray (the titlebar – button)."""
        self._tray_icon.show()
        self.hide()

    def _restore_from_tray(self) -> None:
        """Bring the window back from the tray."""
        self.show()
        self.raise_()
        self.activateWindow()
        self._tray_icon.hide()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_from_tray()

    # ───── boot flow ─────

    def _start(self):
        key = load_api_key(self.app_dir)
        if not key:
            self._enter_setup_key()
            return

        # We have a key cached — validate it (cheap) to confirm models are still accessible.
        self._enter_setup_loading("Whispering to the Gemini Council…")
        self._run_validation(key)

    # ───── setup: key entry ─────

    def _enter_setup_key(self, error: str | None = None):
        self.phase = "setup_key"
        self.title_bar.set_title("GENTLE ADVENTURES, 00 — COMMISSIONING THE PAINTER")
        body = (
            "Before the ship wakes up, we commission the painter.\n\n"
            "Paste the key the Gem handed you below, then press Enter.\n\n"
            "Pro accounts get the stronger painters.  The studio will provide you with keys.\n"
            "Press the button if you need one."
        )
        if error:
            body = f"{body}\n\n✦ painter says: {error}"
        self.narrative.set_text(body, verified=None)
        # Scene 0 is the one frame the painter can't paint for itself — it shows
        # BEFORE a key is connected, so it ships pre-rendered in scenes/. Show it
        # when present; fall back to the placeholder if it's ever missing (e.g. a
        # partial clone or a stripped build).
        if self.scene_cache.has("commissioning"):
            self.scene_view.show_image(QPixmap(str(self.scene_cache.path("commissioning"))))
        else:
            self.scene_view.show_placeholder("✦ awaiting commission ✦")
        self.interaction.set_choices([{"label": "Open the studio", "action": "open_studio"}])
        self.interaction.set_parser_mode("key")

    # ───── setup: validation in flight ─────

    def _enter_setup_loading(self, message: str):
        self.phase = "setup_loading"
        self.title_bar.set_title("GENTLE ADVENTURES, 00 — CONSULTING THE STUDIO")
        self.narrative.set_text(message, verified=None)
        self.scene_view.show_placeholder("✦ consulting ✦")
        self.interaction.set_choices([])
        self.interaction.set_parser_mode("hidden")

    def _run_validation(self, api_key: str):
        worker = KeyValidationWorker(api_key)
        worker.succeeded.connect(self._on_validation_success)
        worker.failed.connect(self._on_validation_failure)
        self._workers.run(worker)
        self._pending_key = api_key

    def _on_validation_success(self, models: list):
        self.available_models = models
        if not load_api_key(self.app_dir):
            save_api_key(self.app_dir, self._pending_key)
        self._pending_key = ""

        # Honour an existing saved selection if it's still accessible
        selected = load_selected_model(self.app_dir)
        if selected and selected in models:
            self.image_client.set_model(selected)
            self._after_painter()
            return

        # Otherwise auto-pick the strongest and offer override
        default = pick_default_image_model(models) or models[0]
        self.image_client.set_model(default)
        save_selected_model(self.app_dir, default)
        self._enter_setup_model(default)

    def _on_validation_failure(self, error: str, is_auth: bool):
        if is_auth:
            # Bad key — wipe stored copy so we don't loop on it
            kf = self.app_dir / ".gemini_key"
            if kf.exists():
                try:
                    kf.unlink()
                except OSError:
                    pass
            self._enter_setup_key(error="that key didn't open the door. try another one?")
        else:
            self._enter_setup_key(error=f"the studio's offline — {error}")

    # ───── setup: model picker (confirm or override) ─────

    def _enter_setup_model(self, default_model: str):
        self.phase = "setup_model"
        self.title_bar.set_title("GENTLE ADVENTURES, 00 — CHOOSING THE BRUSH")
        lines = ["Painter confirmed.", "", f"Default brush: {default_model}", ""]
        if len(self.available_models) > 1:
            lines.append("Other brushes the painter offered:")
            for m in self.available_models[:8]:
                marker = "●" if m == default_model else "○"
                lines.append(f"  {marker} {m}")
        self.narrative.set_text("\n".join(lines), verified=True)
        self.scene_view.show_placeholder("✦ painter ready ✦")

        choices = [{"label": "Begin the log", "action": "begin_quest"}]
        for m in self.available_models[:4]:
            if m != default_model:
                choices.append({"label": f"Use {m}", "action": "pick_model", "model": m})
        self.interaction.set_choices(choices)
        self.interaction.set_parser_mode("hidden")

    # ───── setup: the Ledger (optional Sheets sync, scene 0.5) ─────

    def _after_painter(self):
        """Painter (Gemini) is ready. Offer the optional Ledger / Sheets setup ONCE if
        it isn't configured yet; otherwise go straight to the quest."""
        if getattr(self, "_sheets_offered", False):
            self._enter_quest()
            return
        try:
            from utils.sheets import load_proxy_config
            load_proxy_config(self.app_dir)   # raises if neither env nor file configures it
            configured = True
        except Exception:
            configured = False
        if configured:
            self._enter_quest()
        else:
            self._enter_setup_sheets()

    def _enter_setup_sheets(self):
        """Scene 0.5: an in-app shortcut to set the Sheets-proxy creds as PERSISTENT
        env vars. Two steps (URL, then a masked token); the token lives only in the
        environment, never on disk. Skippable: the ship keeps a local log without it."""
        self._sheets_offered = True
        self.phase = "setup_sheets"
        self._sheets_step = "url"
        self._sheets_url = ""
        self.title_bar.set_title("GENTLE ADVENTURES, 00.5 — OPENING THE LEDGER")
        body = (
            "Before we set sail, we can open the ship's Ledger: a cloud logbook that\n"
            "remembers your journey and lets the story grow between visits.\n\n"
            "Paste the Ledger's web-app URL below, then press Enter.\n\n"
            "No Ledger yet?  You can sail without it; the ship keeps its own local log."
        )
        self.narrative.set_text(body, verified=None)
        if self.scene_cache.has("ledger"):
            self.scene_view.show_image(QPixmap(str(self.scene_cache.path("ledger"))))
        else:
            self.scene_view.show_placeholder("✦ opening the ledger ✦")
        self.interaction.set_choices([{"label": "Sail without the Ledger", "action": "skip_sheets"}])
        self.interaction.set_parser_mode("free")
        self.interaction.set_parser_placeholder("✦ paste the Ledger web-app URL ✦")

    def _bring_ledger_online(self) -> bool:
        """Scene 0.5 just set the Sheets creds, but self.sheets was None since launch
        (unconfigured then), so the heartbeat + hydrate were gated off. Re-create the
        client, re-point the logbook, and start them now, so the Ledger goes live THIS
        session instead of waiting for a relaunch. Best-effort: a bad URL/token just
        fails the first read and the game keeps its local log."""
        try:
            from utils.sheets import SheetsClient
            self.sheets = SheetsClient()
        except Exception as e:
            logger.info(f"[sheets] Ledger still offline after setup: {e}")
            return False
        self.player_state._sheets = self.sheets
        if not hasattr(self, "_ledger_pulse"):
            self._ledger_pulse = QTimer(self)
            self._ledger_pulse.timeout.connect(self._tick_ledger)
        self._ledger_pulse.start(_LEDGER_PULSE_MS)
        self._set_ledger_indicator("pending")
        hydr = PlayerStateSyncWorker(self.player_state, hydrate=True)
        hydr.synced.connect(self._on_state_hydrated)
        self._workers.run(hydr)
        return True

    # ───── quest ─────

    def _enter_quest(self):
        self.phase = "quest"
        # Resume where the captain left off. PlayerStateStore tracks current_scene
        # (local-first, synced to the Sheet), so it's the live last-position — the
        # legacy [game].last_scene was read here but never written, so resume always
        # fell through to the opening. Fall back: current_scene -> last_scene -> start.
        start_id = (self.player_state.get("current_scene")
                    or self.settings.get("game", {}).get("last_scene")
                    or first_scene_id())
        if get_scene(start_id) is None:   # saved id no longer in the quest -> open
            start_id = first_scene_id()
        self._load_scene(start_id)

    def _load_scene(self, scene_id: str):
        scene = get_scene(scene_id)
        if scene is None:
            logger.error(f"Unknown scene id: {scene_id}")
            return

        # Any scene load returns the right pane to the painted view (e.g. after
        # picking from the jump map).
        self._right_stack.setCurrentWidget(self.scene_view)

        # Swapping scenes signals "done with this one": stop the current reveal at
        # once. Beyond the clean cut, this frees the event loop — a running reveal's
        # tick-timer was starving the deferred _apply_scene below, so the new
        # scene's text used to wait for the old one to finish printing.
        self.narrative.cut()

        # Lead with the loading feedback. If this scene needs a fresh painting,
        # raise the working meter + "the painter is painting" placeholder NOW and
        # let them paint, THEN swap the new scene in on the next event-loop tick.
        # Otherwise the meter only fades in once a worker starts — i.e. *after*
        # the new text is already on screen, so it reads as trailing the scene
        # change instead of leading it (the snag the captain caught on 'discovery').
        # Cached scenes have their art in hand: apply at once, no meter, no wait.
        if self.scene_cache.has(scene_id):
            self._apply_scene(scene)
        else:
            self.scene_view.show_loading()
            self.sidebar.set_working(True)
            QTimer.singleShot(0, lambda: self._apply_scene(scene))

    def _apply_scene(self, scene: dict):
        scene_id = scene["id"]
        self._visited.add(scene_id)   # unlocks this scene in the map

        logger.info(f"Loading scene: {scene_id}")
        # The scene we're leaving — its cached image seeds the next render so
        # palette, lighting, and character design carry forward (image-to-image).
        prev_scene_id = self.current_scene["id"] if self.current_scene else None
        self.current_scene = scene

        self.title_bar.set_title(scene["title"])
        self.interaction.set_parser_mode("free")
        # The parser hint follows the scene: when a llama is in the room, address
        # it directly; otherwise it's the ship at large. Content-driven so it
        # tracks wherever the llama appears, no per-scene wiring needed.
        _blob = f"{scene.get('title', '')} {scene.get('narrative', '')}".lower()
        self.interaction.set_parser_placeholder(
            "✦ Ask the Lama… ✦" if "llama" in _blob else "✦ ask the ship anything ✦")

        # Kick the painting first — it never depended on the NPU probe and it's
        # the long pole anyway.
        self._begin_scene_art(scene, prev_scene_id)

        # The first NPU scene shells PowerShell twice (engine probe + hardware
        # spec, ~1-2s each cold). Doing that on the UI thread froze the swap into
        # scene 2 — and because the freeze held the event loop, the working meter
        # couldn't even start until it was over. So: probe OFF the UI thread. Show
        # a gentle "feeling for the engine" line, let the meter run, and fill in
        # the resolved narrative/choices/engine-line when the probe lands. Once
        # cached (or for any non-NPU scene) it resolves instantly, in-line.
        verify_kind = scene.get("verify")
        if verify_kind == "npu" and not self._npu_probed:
            self.narrative.set_text(NPU_PROBING_NOTE, verified=False)
            self.interaction.set_choices([])   # which path is known only after the probe
            worker = NpuProbeWorker()
            worker.probed.connect(
                lambda engine, spec, s=scene: self._on_npu_probed(s, engine, spec))
            self._workers.run(worker)
        else:
            npu_engine = self._npu_descriptor() if verify_kind == "npu" else None
            self._resolve_scene(scene, npu_engine, spec=None)

    def _on_npu_probed(self, scene: dict, engine, spec: dict) -> None:
        """The off-thread probe landed: cache it (the engine can't change within a
        session), then resolve the scene — unless the captain already navigated
        elsewhere while we probed, in which case we only keep the cached result."""
        self._npu_engine = engine
        self._npu_probed = True
        if self.current_scene is scene:
            self._resolve_scene(scene, engine, spec=spec)

    def _resolve_scene(self, scene: dict, npu_engine, spec: dict | None) -> None:
        """Apply the verification-dependent half of a scene: which narrative and
        choices to show, the engine line, the Ledger heartbeat, the reward sticker.
        Split from _apply_scene so the first NPU scene can fill these in from the
        probe worker while the page itself has already painted. `spec` is the raw
        hardware dict the probe gathered (for the Oracle); None on the in-line path."""
        scene_id = scene["id"]
        verify_kind = scene.get("verify")
        if verify_kind == "npu":
            verified = npu_engine is not None
        else:
            verified = self._verify(verify_kind)

        # No NPU aboard: let the story BE the gentle guide instead of a dead
        # "not detected". A scene may carry its own narrative_absent (the rich
        # first-contact guide on 'discovery'); any other NPU-gated scene simply
        # gets NO_NPU_NOTE appended so the tour reads as a lovely 'someday'.
        if verify_kind == "npu" and not verified:
            narrative = scene.get("narrative_absent") or (scene["narrative"] + "\n\n" + NO_NPU_NOTE)
            choices = scene.get("choices_absent") or scene["choices"]
        else:
            narrative = scene["narrative"]
            choices = scene["choices"]
        self.narrative.set_text(narrative, verified=verified)
        self.interaction.set_choices(choices)

        # When a scene checks the NPU, the ship names the engine it found on the
        # bottom strip — the game teaching you your actual silicon, by name.
        if npu_engine:
            if self._oracle_line:
                self.bottom_toolbar.set_info(self._oracle_line)
            else:
                self.bottom_toolbar.set_info(f"✦ engine detected: {npu_engine} ✦")
                self._summon_oracle(npu_engine, spec or {})

        # Heartbeat: push our position up to the Ledger (Player_State). The
        # round-trip confirmation arrives as a passive gold spectral pulse.
        updates = {"current_scene": scene_id}
        if verify_kind == "npu":
            updates["npu_active"] = 1 if verified else 0
        self._sync_player_state(updates)

        # Reward: a verified beat earns a sticker from the iconic library (once).
        if verified:
            self._maybe_award_sticker(scene_id)

    def _begin_scene_art(self, scene: dict, prev_scene_id: str | None) -> None:
        scene_id = scene["id"]
        if self.scene_cache.has(scene_id):
            # Baked art — reload it, never re-commission the painter.
            self.scene_view.show_image(QPixmap(str(self.scene_cache.path(scene_id))))
        else:
            self.scene_view.show_loading()
            # Seed from the previous scene's image when we have one cached.
            ref = (self.scene_cache.path(prev_scene_id)
                   if prev_scene_id and self.scene_cache.has(prev_scene_id) else None)
            self._request_image(scene_id, scene["image_prompt"], ref)

    def _request_image(self, scene_id: str, prompt: str, reference_path: Path | None = None):
        worker = SceneRequestWorker(self.image_client, prompt, scene_id, reference_path)
        worker.image_ready.connect(self._on_image_ready)
        worker.image_failed.connect(self._on_image_failed)
        self._workers.run(worker)

    def _on_image_ready(self, data: bytes, scene_id: str):
        cache_path = self.scene_cache.store(scene_id, data)
        if self.current_scene is not None and self.current_scene["id"] == scene_id:
            self.scene_view.show_image(QPixmap(str(cache_path)))

    def _on_image_failed(self, error: str, scene_id: str):
        if self.current_scene is not None and self.current_scene["id"] == scene_id:
            self.scene_view.show_error(error)

    # ───── ledger write-back (Player_State heartbeat) ─────

    def _sync_player_state(self, updates: dict) -> None:
        """Local-FIRST: persist to the on-board logbook instantly (a disconnect can
        never cost progress), then attempt the cloud push off the UI thread. The dot
        goes amber the moment there's unsynced data, gold once the Ledger confirms.
        With no proxy it still saves locally — the dot just stays dim."""
        self.player_state.set(updates)
        if not self.sheets:
            self._set_ledger_indicator("off")
            return
        self._set_ledger_indicator("pending")
        worker = PlayerStateSyncWorker(self.player_state)
        worker.synced.connect(self._on_state_synced)
        self._workers.run(worker)

    def _on_state_synced(self, reached: bool) -> None:
        if reached:
            # Reached the stars and came back — gold tick + dot to live (unless
            # newer changes are already buffered behind it).
            self.bottom_toolbar.spectral_pulse()
            self._set_ledger_indicator("live" if not self.player_state.has_pending() else "pending")
        else:
            # Push deferred — changes are safe on board; we'll catch the cloud up.
            self._set_ledger_indicator("pending")

    def _on_state_hydrated(self, reached: bool) -> None:
        # Startup pull settled: live if the cloud answered and nothing's buffered;
        # otherwise amber (offline, on the local logbook) or dim (no proxy).
        if reached and not self.player_state.has_pending():
            self._set_ledger_indicator("live")
        else:
            self._set_ledger_indicator("pending" if self.sheets else "off")

    def _set_ledger_indicator(self, state: str) -> None:
        """Reflect the Ledger on the bottom-strip dot — 'live' (gold, synced) /
        'pending' (amber, saved on board & syncing) / 'off' (dim, no proxy) — with
        a single gentle whisper the first time it goes fully dark."""
        prev = getattr(self, "_ledger_state", None)
        self._ledger_state = state
        if hasattr(self, "bottom_toolbar"):
            self.bottom_toolbar.set_ledger_state(state)
        if state == "off" and prev != "off":
            self.bottom_toolbar.set_info("✦ the ledger sleeps — your progress is kept safe on board ✦")

    # ───── text generation (swappable Claude/Gemini backend) ─────

    def _request_text(self, messages, *, system=None, max_tokens=1024,
                      temperature=None, tag="", on_ready=None, on_failed=None) -> bool:
        """Fire a text completion off the UI thread via the worker registry.
        on_ready(text, tag) / on_failed(error, tag) are connected if given.
        Returns False (no-op) when no text backend is configured — callers treat
        a missing backend as silent absence, never an error in the UI."""
        if not self.text_backend:
            if on_failed:
                on_failed("no text backend configured", tag)
            return False
        worker = TextWorker(self.text_backend, messages, system=system,
                            max_tokens=max_tokens, temperature=temperature, tag=tag)
        if on_ready:
            worker.text_ready.connect(on_ready)
        if on_failed:
            worker.text_failed.connect(on_failed)
        self._workers.run(worker)
        return True

    # ───── Hardware Oracle (Sentient Settings) ─────

    def _summon_oracle(self, engine_name: str, spec: dict | None = None) -> None:
        """Once per session: ask the ship's-computer voice to name the silicon in
        one short, warm calibration line, given the RAW hardware spec. Async and
        cosmetic — never blocks the quest; on failure the plain engine line stays.

        `spec` is gathered off the UI thread by NpuProbeWorker and handed in — the
        old synchronous raw_hardware_spec() call here was a second ~1-2s PowerShell
        freeze on the first NPU scene. Falls back to just the engine name if absent."""
        if self._oracle_summoned:
            return
        self._oracle_summoned = True
        spec = spec or {}
        spec_text = "\n".join(f"{k}: {v}" for k, v in spec.items()) or f"npu: {engine_name}"
        system = (
            "You are the gentle ship's computer in a cozy chibi space adventure that "
            "teaches a captain about their laptop's NPU. Given the ship's real hardware, "
            "reply with ONE short, warm, in-character line (max ~20 words) that names the "
            "NPU's silicon family and offers to calibrate it. No preamble, no lists, no "
            "surrounding quotes — just the line itself. Tone example: 'Ah — fifty TOPS of "
            "XDNA 2 stirring awake. Let me tune the plasma injectors for you.'"
        )
        user = (f"The ship's engine reads as: {engine_name}.\n\n"
                f"Real hardware:\n{spec_text}\n\n"
                "Name it and offer to calibrate, in one gentle line.")
        self._request_text(
            [{"role": "user", "content": user}],
            system=system, tag="oracle",
            on_ready=self._on_oracle_text, on_failed=self._on_oracle_failed,
        )

    def _on_oracle_text(self, text: str, tag: str) -> None:
        line = " ".join(text.strip().split())   # collapse stray newlines/spaces
        if not line:
            return
        self._oracle_line = f"✦ {line} ✦"
        self.bottom_toolbar.set_info(self._oracle_line)

    def _on_oracle_failed(self, error: str, tag: str) -> None:
        # Cosmetic — keep the plain engine line, never surface the error in the UI.
        logger.info(f"[oracle] calibration line unavailable: {error}")

    # ───── sticker loot (awarded from the iconic library) ─────

    def _maybe_award_sticker(self, scene_id: str) -> None:
        """Once per session per scene: a verified beat blooms a reward sticker
        (a real iconic-library asset) over the scene + whispers the achievement.
        Silent no-op if the scene has no reward or the asset is missing."""
        if scene_id in self._earned_stickers:
            return
        award = award_for_scene(scene_id, self.app_dir)
        if not award:
            return
        path, name = award
        self._earned_stickers.add(scene_id)
        self.scene_view.flash_sticker(str(path))
        self.bottom_toolbar.set_info(f"✦ sticker earned — {name} ✦")

    # ───── The Lantern (gentle real-tool runner) ─────

    def _light_command(self, cmd, label: str = "checking") -> None:
        """Run a real command (e.g. flm) off the UI thread through The Lantern,
        via the worker registry; the result lands in the bottom strip (the
        free-text 'validate' command). Snag -> gentle lit line; raw -> log only."""
        worker = LanternWatch(cmd, label)
        worker.settled.connect(self._on_lantern_settled)
        self._workers.run(worker)
        self.bottom_toolbar.set_info(f"✦ {label}… ✦")

    def _lantern_rewrite_request(self, classification, raw: str, on_ready) -> None:
        """Ask the text backend for a richer in-character repair line. No-op when
        there's no backend — the offline classifier copy already stands. Raw goes
        to the log only; only a trimmed tail reaches the model (benign for flm)."""
        if not self.text_backend:
            return
        system = (
            "You are The Lantern — a gentle companion in a cozy chibi space "
            "adventure. A tool just stumbled. Given its raw output, reply with ONE "
            "or two warm sentences that name the snag plainly and offer the single "
            "concrete next step, in a calm 'let me light this for you' voice. No "
            "preamble, no lists, no surrounding quotes — just the line."
        )
        kind = classification.get("kind") if classification else "unknown"
        user = f"Stumble kind: {kind}.\nLast output:\n{raw[-800:]}"
        self._request_text([{"role": "user", "content": user}], system=system,
                           tag="lantern", on_ready=on_ready)

    def _on_lantern_settled(self, code: int, gentle: str, classification, raw: str) -> None:
        # Bottom-strip target (the free-text 'validate' command).
        if code == 0:
            self.bottom_toolbar.set_info("✦ all lit and well — your ship checks out ✦")
            return
        self.bottom_toolbar.set_info(gentle or "✦ a small tangle — handled ✦")
        self._lantern_rewrite_request(classification, raw, self._on_lantern_rewrite)

    def _on_lantern_rewrite(self, text: str, tag: str) -> None:
        line = " ".join(text.strip().split())
        if line:
            self.bottom_toolbar.set_info(f"🔦 {line}")

    # ── Quest beat: "validate your ship" — The Lantern reports into the narrative ──

    def _validate_ship(self) -> None:
        """Quest-beat action: run the real `flm validate` and report into the
        NarrativePanel — a clean bill of health, or a gentle repair if the ship's
        NPU/runtime needs a nudge. Never blocks; raw trace -> log only."""
        self.narrative.set_text("✦ The Lantern lifts its light and checks your ship…",
                                verified=None)
        # Run flm by its RESOLVED full path, not by name — it may be installed but
        # not on this process's PATH (the stale-env case). Falls back to bare "flm"
        # only when truly not found, where the Lantern's "not installed" line is right.
        worker = LanternWatch([resolve_flm() or "flm", "validate"], "validating the ship")
        worker.settled.connect(self._on_validate_settled)
        self._workers.run(worker)

    def _on_validate_settled(self, code: int, gentle: str, classification, raw: str) -> None:
        if code == 0:
            found = [ln for ln in raw.splitlines() if ln.strip()][:4]
            body = ("Your ship is sound. The Lantern found:\n\n"
                    + "\n".join(found)
                    + "\n\nAll lit and well — your NPU is ready. ✦")
            self.narrative.set_text(body, verified=True)
            return
        self.narrative.set_text(f"🔦 {gentle}", verified=False)
        self._lantern_rewrite_request(classification, raw, self._on_validate_rewrite)

    def _on_validate_rewrite(self, text: str, tag: str) -> None:
        line = " ".join(text.strip().split())
        if line:
            self.narrative.set_text(f"🔦 {line}", verified=False)

    # ───── shutdown ─────

    def closeEvent(self, event):
        """The ✕ button refreshes the app: save window state, sweep bytecode,
        relaunch a fresh instance, and close this one — Intricate's
        restart-on-close, so the edit→restart loop never touches the console.
        Tray 'Exit' and Ctrl-C set self._quitting to skip the relaunch and
        actually leave. pycache is swept BEFORE the spawn so the child's own
        startup purge owns a clean tree (no race)."""
        self._save_window_state()
        self._workers.stop_all()   # drain in-flight threads cleanly before relaunch
        self.oracle.shutdown()     # stop our local oracle server (only if we started one)
        try:
            from utils.housekeeping import clean_pycache
            n = clean_pycache(self.app_dir)
            logger.info(f"Cleaned Python cache on exit ({n} tree(s) swept).")
        except Exception as e:
            logger.warning(f"pycache cleanup on exit failed: {e}")
        if hasattr(self, "_tray_icon"):
            self._tray_icon.hide()
        if not self._quitting:
            self._spawn_restart()
        super().closeEvent(event)

    # ───── window state + restart ─────

    def _restore_window_geometry(self, win_cfg: dict) -> None:
        """Restore last session's size/position from the JSON sidecar, falling
        back to settings.toml [window] defaults. Maximized state is re-applied
        after show (see __init__) since work_area needs the live screen."""
        state = {}
        try:
            if self._window_state_path.exists():
                state = json.loads(self._window_state_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"window state load failed: {e}")
        w = int(state.get("width", win_cfg.get("width", 960)))
        h = int(state.get("height", win_cfg.get("height", 1080)))
        self.resize(w, h)
        if "x" in state and "y" in state:
            self.move(int(state["x"]), int(state["y"]))
        self._restore_maximized = bool(state.get("maximized", False))

    def _save_window_state(self) -> None:
        """Persist size/position + maximized flag so the next launch reopens the
        same way. When maximized, store the pre-maximize geometry so a later
        unmaximize returns to a sane size rather than the work-area rect."""
        maxed = self._is_maxed
        geom = (self._restore_geom_max
                if maxed and self._restore_geom_max is not None else self.geometry())
        state = {
            "x": geom.x(), "y": geom.y(),
            "width": geom.width(), "height": geom.height(),
            "maximized": maxed,
        }
        try:
            self._window_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"window state save failed: {e}")

    def _quit_app(self) -> None:
        """True exit (tray 'Exit') — sets the quit flag so closeEvent skips the
        ✕-button relaunch and the app actually leaves."""
        self._quitting = True
        self.close()

    def _spawn_restart(self) -> None:
        """Relaunch a fresh instance. The child inherits this console (no
        creationflags), so logs keep flowing and Ctrl-C still quits — unlike
        Intricate's CREATE_NO_WINDOW, which fits its .lnk launch but would
        detach our dev console. To leave for good: tray 'Exit' or Ctrl-C."""
        try:
            main_py = self.app_dir / "main.py"
            subprocess.Popen([sys.executable, str(main_py)])
            logger.info("[restart] spawned a fresh session — back in a blink ✨")
        except Exception as e:
            logger.warning(f"[restart] spawn failed (closing without relaunch): {e}")

    # ───── map (scene navigator) ─────

    def _scene_index(self):
        """The (scene_id, title) pairs backing the map, from the live Ledger
        (the Quest_Log sheet, or the bundled scenes when it's empty/offline)."""
        return [(s["id"], s.get("title", s["id"])) for s in all_scenes()]

    def _on_feature(self, name: str):
        """Bottom-toolbar feature buttons. 'map' is wired (scene navigator);
        the others still whisper 'not wired up yet' until they land."""
        if name == "map":
            self._toggle_map()
            return
        self.bottom_toolbar.set_info(f"✦ {name} — not wired up yet ✦")

    def _toggle_map(self):
        """Flip the right pane between the painted scene and the jump map — a
        quest-time navigator so we can leap anywhere while building. The map is
        its own module; the window just switches which widget the stack shows.
        Before the log begins there are no scenes to jump to."""
        if self.phase != "quest":
            self.bottom_toolbar.set_info("✦ the map opens once the log begins ✦")
            return
        if self._right_stack.currentWidget() is self.scene_map:
            self._right_stack.setCurrentWidget(self.scene_view)
            self.bottom_toolbar.set_info("")
        else:
            self.scene_map.set_scenes(self._scene_index(), self._visited)
            self._right_stack.setCurrentWidget(self.scene_map)
            self.bottom_toolbar.set_info("✦ map — choose a scene ✦")

    def _on_map_pick(self, scene_id: str):
        # The map announces the picked id; loading it flips the stack back to
        # the painted scene (see _load_scene), so the map closes itself.
        self._load_scene(scene_id)

    # ───── input dispatch ─────

    def _on_choice(self, choice: object, free_text: str):
        # Parser submission (free_text) — dispatch by phase
        if free_text:
            if self.phase == "setup_key":
                self._enter_setup_loading("Whispering to the Gemini Council…")
                self._run_validation(free_text)
                return
            if self.phase == "setup_sheets":
                if self._sheets_step == "url":
                    self._sheets_url = free_text
                    self._sheets_step = "token"
                    self.narrative.set_text(
                        "Good.  Now paste the Ledger token (it stays hidden as you type),\n"
                        "then press Enter.", verified=None)
                    self.interaction.set_parser_mode("key")   # masked echo, like the key field
                    self.interaction.set_parser_placeholder("✦ paste the Ledger token (hidden) ✦")
                    self.interaction.clear_parser()
                else:
                    from shared_braincell.winenv import set_user_env
                    set_user_env("GA_WebApp", self._sheets_url)
                    set_user_env("GA_Ledger", free_text)
                    logger.info("[sheets] Ledger creds saved to the environment + this session")
                    online = self._bring_ledger_online()
                    # A read-only confirmation beat; the captain sets sail when ready.
                    self.phase = "setup_sheets_done"
                    self.interaction.clear_parser()
                    self.interaction.set_parser_mode("hidden")
                    self.narrative.set_text(
                        "The Ledger is open.  Your journey will be remembered."
                        if online else
                        "Saved.  The Ledger opens on your next voyage.",
                        verified=True)
                    self.interaction.set_choices([{"label": "Set sail ✦", "action": "begin_quest"}])
                return
            if self.phase == "quest":
                cmd = free_text.strip().lower()
                if cmd in ("validate", "validate ship", "light"):
                    # The Lantern runs the real `flm validate` and lights any snag.
                    self._light_command([resolve_flm() or "flm", "validate"], "checking the ship")
                    return
                logger.info(f"Parser input: {free_text!r}")
                # System 2 (Psychological Weather) — Phase 1 manual dial, so the
                # overlay can be seen and tuned before the vibe vector (Phase 2)
                # drives it from the Gemini-read mood. A recognised weather word
                # sets the rain; anything else falls through untouched.
                if self._weather_command(cmd):
                    return
                # System 2 Phase 2 — read the vibe vector from the free text and
                # let the weather answer it (intensity + palette morph). Async and
                # silent on absence: no backend → no vibe, the sky simply holds.
                self._read_vibe(free_text)      # ambient: the world reads the mood
                self._ask_oracle(free_text)     # primary: the local NPU oracle answers
                return
            return

        # Button click — dispatch by action
        if not isinstance(choice, dict):
            return

        action = choice.get("action")
        if action == "open_studio":
            webbrowser.open(STUDIO_URL)
            return
        if action == "begin_quest":
            self._after_painter()
            return
        if action == "skip_sheets":
            self._enter_quest()
            return
        if action == "pick_model":
            model = choice.get("model")
            if model:
                self.image_client.set_model(model)
                save_selected_model(self.app_dir, model)
                self._after_painter()
            return
        if action == "quit":
            self.close()
            return
        if action == "validate_ship":
            self._validate_ship()
            return

        nxt = choice.get("next")
        if nxt:
            self._load_scene(nxt)

    def _weather_command(self, text: str) -> bool:
        """Phase-1 manual weather dial (System 2). Returns True if the text was a
        weather word (so the caller stops dispatching). 'weather 0.7' sets an
        exact intensity; named moods map to gentle presets; 'clear'/'sun' rests
        it. The intensity eases in — the overlay does the tide, not a snap."""
        if not hasattr(self, "_weather"):
            return False
        presets = {
            "clear": 0.0, "sun": 0.0, "sunny": 0.0, "calm": 0.0,
            "drizzle": 0.3, "mist": 0.55, "rain": 0.6,
            "storm": 0.9, "downpour": 1.0,
        }
        parts = text.split()
        if parts and parts[0] == "weather":
            try:
                level = float(parts[1]) if len(parts) > 1 else 0.5
            except ValueError:
                level = 0.5
            self._weather.set_intensity(level)
            logger.info(f"Weather (manual): intensity -> {max(0.0, min(1.0, level)):.2f}")
            return True
        if text in presets:
            self._weather.set_intensity(presets[text])
            logger.info(f"Weather (manual): {text!r} -> {presets[text]:.2f}")
            return True
        return False

    # ───── the local oracle — "ask the ship" answers on-device (flm) ─────

    def _ask_oracle(self, question: str) -> None:
        """Put the captain's question to the LOCAL NPU oracle (flm's llama) and stream
        the answer into the narrative — no call leaves the ship. If flm isn't aboard,
        gently point back to the summoning. Off the UI thread; the model load on the
        first ask is the 'stirs awake' beat. Never blocks the quest."""
        self._oracle_question = question
        if not resolve_flm():
            self.narrative.set_text(
                "✦ The oracle isn't aboard yet — summon it first: fetch FastFlowLM, "
                "then run flm run llama3.2:3b. Once it's here, ask me anything. ✦",
                verified=False, question=question)
            return
        self.narrative.set_text(
            "✦ the oracle stirs, gathering a small private thought… ✦",
            verified=None, question=question)
        system = (
            "You are the on-device oracle — a small local llama running on the ship's "
            "NPU in a cozy chibi space adventure. Answer the captain's question warmly "
            "and plainly in 1-3 short sentences. You are smaller of voice than the cloud "
            "spirits and won't always be right, but you are always present and private — "
            "no call ever leaves the ship. No preamble, no lists, no quotes — just the "
            "answer, gently."
        )
        worker = OracleWorker(self.oracle, question, system)
        worker.answered.connect(self._on_oracle_answer)
        worker.failed.connect(self._on_oracle_failed)
        self._workers.run(worker)

    def _on_oracle_answer(self, text: str) -> None:
        line = (text or "").strip()
        if line:
            self.narrative.set_text(line, verified=None,
                                    question=getattr(self, "_oracle_question", None))

    def _on_oracle_failed(self, error: str) -> None:
        logger.info(f"[oracle] {error}")
        self.narrative.set_text(
            "✦ the oracle drew a quiet breath and couldn't quite answer — it's a small "
            "mind, and sometimes it rests. Try once more in a moment. ✦", verified=False,
            question=getattr(self, "_oracle_question", None))

    # ───── Psychological Weather — the vibe vector (System 2 Phase 2) ─────

    def _read_vibe(self, text: str) -> None:
        """Ask the text backend to read the captain's message as a tiny vibe
        vector (energy / calm), then let the weather answer it. Cosmetic and
        async — never blocks the quest, never surfaces an error in the UI."""
        if not hasattr(self, "_weather"):
            return
        snippet = (text or "").strip()[:400]
        if not snippet:
            return
        system = (
            "You are the quiet weather-sense of a cozy chibi space adventure. Read "
            "the emotional vibe of the captain's message. Reply with ONLY a compact "
            "JSON object and nothing else: {\"energy\": <0.0-1.0>, \"calm\": <0.0-1.0>, "
            "\"mood\": \"<one or two gentle words>\"}. energy = how lively, excited, "
            "triumphant, high-gusto it feels. calm = how quiet, reflective, restful, "
            "slow-morning it feels. No prose, no markdown, no code fences."
        )
        self._request_text(
            [{"role": "user", "content": snippet}],
            system=system, tag="vibe",
            on_ready=self._on_vibe_text, on_failed=self._on_vibe_failed,
        )

    def _on_vibe_text(self, text: str, tag: str) -> None:
        energy, calm, mood = self._parse_vibe(text)
        if energy is None:
            logger.info(f"[vibe] unparseable reply, sky holds: {text!r}")
            return
        self._weather.set_vibe(energy, calm)
        logger.info(f"[vibe] energy={energy:.2f} calm={calm:.2f} mood={mood!r}")

    def _on_vibe_failed(self, error: str, tag: str) -> None:
        # Silent by design — no backend / a hiccup just means the sky holds steady.
        logger.info(f"[vibe] read unavailable: {error}")

    @staticmethod
    def _parse_vibe(text: str):
        """Pull {energy, calm, mood} from the model's reply, tolerant of stray
        prose or code fences. Returns (None, None, None) if unparseable."""
        if not text:
            return (None, None, None)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return (None, None, None)
        try:
            obj = json.loads(m.group(0))
        except (ValueError, TypeError):
            return (None, None, None)

        def _clamp(v):
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                return None

        energy = _clamp(obj.get("energy"))
        calm = _clamp(obj.get("calm"))
        if energy is None or calm is None:
            return (None, None, None)
        mood = str(obj.get("mood", "")).strip()[:40]
        return (energy, calm, mood)

    # ───── verification ─────

    def _npu_descriptor(self) -> str | None:
        """Cached NPU probe. The engine can't change within a session, so we
        shell PowerShell ONCE (on the first NPU scene) and reuse the result —
        instead of paying that ~1-2s subprocess on every NPU-scene navigation,
        which was the scene-nav lag."""
        if not self._npu_probed:
            self._npu_engine = probe_npu()
            self._npu_probed = True
        return self._npu_engine

    def _verify(self, kind: str | None):
        if kind is None:
            return None
        # 'npu' is resolved directly in _load_scene — it needs the engine
        # descriptor (for the bottom strip), not just this bool.
        if kind == "fastflowlm":
            return probe_fastflowlm()
        return None
