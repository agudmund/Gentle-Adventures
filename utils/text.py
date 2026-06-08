#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - text.py the ship's voice, a swappable Claude/Gemini text client
-One doorway to the oracles; Claude answers by default, Gemini on a whim, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from pathlib import Path

from shared_braincell.llm import Backend, make_backend
from shared_braincell.gemini_image import load_api_key
from utils.logger import get_logger
from utils.identity import user_agent

logger = get_logger("gentle")


# Defaults if settings.toml has no (or a partial) [llm] block. Claude leads for
# reasoning; gemini-3.5-flash is the stable Gemini 3 text model. The image model
# (settings [gemini].model) is a SEPARATE concern — this is text only.
_DEFAULTS = {
    "text_backend": "claude",
    "claude_model": "claude-opus-4-8",
    "gemini_model": "gemini-3.5-flash",
}


def build_text_backend(settings: dict, app_dir: Path) -> Backend:
    """Construct the configured text backend (Claude default, Gemini swappable).

    Reads the [llm] block from settings. For the gemini case we inject GA's own
    resolved key (it may live in a .gemini_key file, which the shared module
    can't see); Claude reads the family env key (SingleSharedBraincell_ApiKey)
    itself. Construction never hits the network — a missing key only surfaces as
    an LLMAuthError when complete() is actually called.
    """
    cfg = {**_DEFAULTS, **(settings.get("llm", {}) or {})}
    name = str(cfg.get("text_backend", "claude")).strip().lower()
    if name == "gemini":
        backend = make_backend("gemini",
                               model=cfg.get("gemini_model", _DEFAULTS["gemini_model"]),
                               api_key=load_api_key(app_dir),
                               user_agent=user_agent())
    else:
        backend = make_backend("claude",
                               model=cfg.get("claude_model", _DEFAULTS["claude_model"]),
                               user_agent=user_agent())
    logger.info(f"[text] backend = {backend.name} ({backend.model})")
    return backend
