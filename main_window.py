#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - main_window.py top-level window, setup wizard, and scene orchestrator
-We frame the new world and welcome the player home, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QSystemTrayIcon

from data.quest import QUEST, get_scene
from pretty_widgets.graphics.Theme import Theme as Fam
from graphics.widgets import BottomToolbar, InteractionBar, NarrativePanel, SceneView, TitleBar
from utils.gemini import (
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
from utils.probe import probe_lm_studio, probe_npu

logger = logging.getLogger("gentle")

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

    def __init__(self, client: GeminiImageClient, prompt: str, scene_id: str):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.scene_id = scene_id

    def run(self):
        try:
            data = self.client.generate(self.prompt)
            self.image_ready.emit(data, self.scene_id)
        except (GeminiAuthError, GeminiAPIError) as e:
            logger.warning(f"Image gen failed for {self.scene_id}: {e}")
            self.image_failed.emit(str(e), self.scene_id)


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
        self.scenes_dir.mkdir(exist_ok=True)

        default_model = settings.get("gemini", {}).get("model", "gemini-2.5-flash-image-preview")
        selected = load_selected_model(app_dir) or default_model
        self.image_client = GeminiImageClient(app_dir=app_dir, model=selected)

        self.current_worker: QThread | None = None
        self.current_scene: dict | None = None
        self.available_models: list[str] = []
        self.phase: str = "quest"  # set properly in _start
        self._curtains_collapsed = False
        self._curtain_anim = None
        self._is_maxed = False
        self._restore_geom_max = None

        win_cfg = settings.get("window", {})
        self.setWindowTitle(win_cfg.get("title", "Gentle Adventures"))
        self.resize(int(win_cfg.get("width", 960)), int(win_cfg.get("height", 1080)))
        self._apply_window_theme()
        # Frameless + always-on-top: hide the OS titlebar (our custom TitleBar
        # provides controls + drag) and float above other windows — the family
        # default (Intricate, The Majestic, The Settlers all set this). No
        # overlap headache: each app's titlebar is the only persistent chrome,
        # and the curtains gesture rolls the window down to a thin strip when
        # it needs to get out of the way.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self._build_layout()
        self._setup_system_tray()
        self._start()

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

    # ───── layout ─────

    def _build_layout(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.curtains_clicked.connect(self.toggle_curtains)
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
        self.narrative = NarrativePanel()
        self.interaction = InteractionBar()
        self.interaction.choice_made.connect(self._on_choice)
        self.bottom_toolbar = BottomToolbar()

        body_layout.addWidget(self.scene_view, stretch=1)
        body_layout.addWidget(self.narrative)
        body_layout.addWidget(self.interaction)
        body_layout.addWidget(self.bottom_toolbar)
        layout.addWidget(self._body, stretch=1)

        self.setCentralWidget(central)

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
            # Delay-hide the body so it stays visible for the first ~2/3 of the
            # roll — the window reads as physically pulling its thickness up
            # into the strip (bottom toolbar and all), not just shrinking. That
            # stagger is the "oompf". Mirrors Intricate main_window.py:1187.
            hide_delay = max(1, int(duration * 2 / 3))
            QTimer.singleShot(hide_delay, self._body.hide)
        else:
            # Show the body up front so it grows back into view as we expand.
            self._body.show()

        anim.start()
        self._curtain_anim = anim          # keep a ref so it isn't GC'd mid-roll
        self._curtains_collapsed = collapsing
        self._is_maxed = not collapsing    # the expanded strip fills the work area
        self.title_bar.reflect_maximized(self._is_maxed)

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
        """System tray icon with a Show / Exit menu. The icon is playIconic —
        Gentle Adventures' brand mark, copied into icons/ from the family set."""
        self._tray_icon = QSystemTrayIcon(self)
        icon_path = self.app_dir / "icons" / "playIconic.ico"
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
        tray_menu.addAction("Exit", self.close)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

        # Self-heal the Personalization > Taskbar panel so the entry reads
        # "Gentle Adventures" with the playIconic mark instead of "Python" with
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

        icon_path = self.app_dir / "icons" / "playIconic.ico"
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
            "Before the captain wakes, we commission the painter.\n\n"
            "Paste the key the Gemini Council gave you below, then press Enter.\n\n"
            "Pro accounts get the stronger painters. The studio gives keys away —\n"
            "press the button if you need one."
        )
        if error:
            body = f"{body}\n\n✦ painter says: {error}"
        self.narrative.set_text(body, verified=None)
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
        if isinstance(self.current_worker, QThread) and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        worker = KeyValidationWorker(api_key)
        worker.succeeded.connect(self._on_validation_success)
        worker.failed.connect(self._on_validation_failure)
        worker.start()
        self.current_worker = worker
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
            self._enter_quest()
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

    # ───── quest ─────

    def _enter_quest(self):
        self.phase = "quest"
        start_id = self.settings.get("game", {}).get("last_scene") or QUEST[0]["id"]
        if get_scene(start_id) is None:
            start_id = QUEST[0]["id"]
        self._load_scene(start_id)

    def _load_scene(self, scene_id: str):
        scene = get_scene(scene_id)
        if scene is None:
            logger.error(f"Unknown scene id: {scene_id}")
            return

        logger.info(f"Loading scene: {scene_id}")
        self.current_scene = scene

        self.title_bar.set_title(scene["title"])
        verified = self._verify(scene.get("verify"))
        self.narrative.set_text(scene["narrative"], verified=verified)
        self.interaction.set_choices(scene["choices"])
        self.interaction.set_parser_mode("free")

        cached = self.scenes_dir / f"{scene_id}.png"
        if cached.exists():
            self.scene_view.show_image(QPixmap(str(cached)))
        else:
            self.scene_view.show_loading()
            self._request_image(scene["id"], scene["image_prompt"])

    def _request_image(self, scene_id: str, prompt: str):
        if isinstance(self.current_worker, QThread) and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        worker = SceneRequestWorker(self.image_client, prompt, scene_id)
        worker.image_ready.connect(self._on_image_ready)
        worker.image_failed.connect(self._on_image_failed)
        worker.start()
        self.current_worker = worker

    def _on_image_ready(self, data: bytes, scene_id: str):
        cache_path = self.scenes_dir / f"{scene_id}.png"
        cache_path.write_bytes(data)
        logger.info(f"Cached scene image: {cache_path.name} ({len(data)} bytes)")
        if self.current_scene is not None and self.current_scene["id"] == scene_id:
            self.scene_view.show_image(QPixmap(str(cache_path)))

    def _on_image_failed(self, error: str, scene_id: str):
        if self.current_scene is not None and self.current_scene["id"] == scene_id:
            self.scene_view.show_error(error)

    # ───── shutdown ─────

    def closeEvent(self, event):
        """Sweep Python bytecode on the way out — the ✕ button (and every other
        exit path, since they all funnel through here) clears the cache so the
        next launch always runs fresh code. Mirrors Intricate's shutdown janitor;
        the whole point of the edit→restart loop staying painless."""
        try:
            from utils.housekeeping import clean_pycache
            n = clean_pycache(self.app_dir)
            logger.info(f"Cleaned Python cache on exit ({n} tree(s) swept).")
        except Exception as e:
            logger.warning(f"pycache cleanup on exit failed: {e}")
        if hasattr(self, "_tray_icon"):
            self._tray_icon.hide()
        super().closeEvent(event)

    # ───── input dispatch ─────

    def _on_choice(self, choice: object, free_text: str):
        # Parser submission (free_text) — dispatch by phase
        if free_text:
            if self.phase == "setup_key":
                self._enter_setup_loading("Whispering to the Gemini Council…")
                self._run_validation(free_text)
                return
            if self.phase == "quest":
                logger.info(f"Parser input: {free_text!r}")
                # Future hop: route to Claude or the local llama for in-character reply
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
            self._enter_quest()
            return
        if action == "pick_model":
            model = choice.get("model")
            if model:
                self.image_client.set_model(model)
                save_selected_model(self.app_dir, model)
                self._enter_quest()
            return
        if action == "quit":
            self.close()
            return

        nxt = choice.get("next")
        if nxt:
            self._load_scene(nxt)

    # ───── verification ─────

    def _verify(self, kind: str | None):
        if kind is None:
            return None
        if kind == "npu":
            return probe_npu()
        if kind == "lm_studio":
            return probe_lm_studio()
        return None
