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

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from data.quest import QUEST, get_scene
from graphics.Theme import Theme
from graphics.widgets import InteractionBar, NarrativePanel, SceneView, TitleBar
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

        win_cfg = settings.get("window", {})
        self.setWindowTitle(win_cfg.get("title", "Gentle Adventures"))
        self.resize(int(win_cfg.get("width", 960)), int(win_cfg.get("height", 1080)))
        self.setStyleSheet(f"background-color: {Theme.frame_black};")
        # Frameless: hide the OS titlebar — our custom TitleBar provides the
        # window controls + drag (mirrors Intricate's chrome). Deliberately NOT
        # WindowStaysOnTopHint: this is an app window, not an always-on-top overlay.
        self.setWindowFlag(Qt.FramelessWindowHint, True)

        self._build_layout()
        self._start()

    # ───── layout ─────

    def _build_layout(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.scene_view = SceneView()
        self.narrative = NarrativePanel()
        self.interaction = InteractionBar()
        self.interaction.choice_made.connect(self._on_choice)

        layout.addWidget(self.title_bar)
        layout.addWidget(self.scene_view, stretch=1)
        layout.addWidget(self.narrative)
        layout.addWidget(self.interaction)

        self.setCentralWidget(central)

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
