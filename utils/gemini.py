#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - gemini.py raw HTTP client for live scene image generation
-We ask the painter and the painter answers, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("gentle")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY_FILENAME = ".gemini_key"
MODEL_FILENAME = ".gemini_model"


class GeminiAuthError(RuntimeError):
    """Missing, invalid, or rejected API key."""


class GeminiAPIError(RuntimeError):
    """Any non-auth API or transport failure."""


# ─────────────────────────────────────────────────────────────────────────────
# Key resolution — local file wins over env, so the in-app prompt persists.
# ─────────────────────────────────────────────────────────────────────────────


def key_file_path(app_dir: Path) -> Path:
    return app_dir / KEY_FILENAME


def load_api_key(app_dir: Path) -> str | None:
    kf = key_file_path(app_dir)
    if kf.exists():
        key = kf.read_text(encoding="utf-8").strip()
        if key:
            logger.debug(f"Gemini key loaded from {kf.name}")
            return key
    for var in ("GEMINI_API_KEY", "SingleSharedBraincell_GeminiKey", "GOOGLE_API_KEY"):
        env_key = os.environ.get(var)
        if env_key:
            logger.debug(f"Gemini key resolved from env: {var}")
            return env_key
    return None


def save_api_key(app_dir: Path, key: str) -> None:
    kf = key_file_path(app_dir)
    kf.write_text(key.strip(), encoding="utf-8")
    try:
        # Best-effort tighten on POSIX; harmless no-op on Windows
        os.chmod(kf, 0o600)
    except (OSError, NotImplementedError):
        pass
    logger.info(f"Gemini key saved to {kf}")


def load_selected_model(app_dir: Path) -> str | None:
    mf = app_dir / MODEL_FILENAME
    if mf.exists():
        m = mf.read_text(encoding="utf-8").strip()
        if m:
            return m
    return None


def save_selected_model(app_dir: Path, model: str) -> None:
    mf = app_dir / MODEL_FILENAME
    mf.write_text(model.strip(), encoding="utf-8")
    logger.info(f"Selected image model saved: {model}")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────


def _http_request(url: str, *, data: bytes | None = None, timeout: float = 30.0) -> dict:
    method = "POST" if data is not None else "GET"
    headers = {"User-Agent": "GentleAdventures/0.1 (SingleSharedBraincell)"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if e.code in (401, 403):
            raise GeminiAuthError(f"Gemini rejected the key (HTTP {e.code}): {body[:300]}") from e
        raise GeminiAPIError(f"HTTP {e.code} from Gemini: {body[:400]}") from e
    except TimeoutError as e:
        # A read-phase timeout (server slow to respond) raises a bare
        # TimeoutError that sails past URLError — convert it so the worker's
        # GeminiAPIError handler catches it instead of crashing QThread.run().
        raise GeminiAPIError(
            f"Gemini timed out after {timeout:.0f}s — the model or network was slow. "
            "Try again, or switch to a lighter model."
        ) from e
    except urllib.error.URLError as e:
        # urllib wraps connect-phase timeouts in URLError(reason=TimeoutError);
        # surface those cleanly too.
        if isinstance(getattr(e, "reason", None), TimeoutError):
            raise GeminiAPIError(f"Gemini connection timed out after {timeout:.0f}s.") from e
        raise GeminiAPIError(f"Network failure reaching Gemini: {e.reason}") from e


# ─────────────────────────────────────────────────────────────────────────────
# Model discovery — list everything the key has access to, filter to image-gen
# ─────────────────────────────────────────────────────────────────────────────


def _version_key(model_name: str) -> tuple[int, int, str]:
    """Sortable key — (major, minor, name) so newer versions land first when reversed."""
    m = re.search(r"(\d+)\.(\d+)", model_name)
    if m:
        return (int(m.group(1)), int(m.group(2)), model_name)
    return (0, 0, model_name)


def list_image_models(api_key: str) -> list[str]:
    """Query Google for accessible models, filter to image-output capable ones.

    Returns model identifiers (without 'models/' prefix), newest-first.
    Raises GeminiAuthError on bad key, GeminiAPIError on transport issues.
    """
    payload = _http_request(f"{GEMINI_BASE}/models?key={api_key}")
    models = payload.get("models", [])

    accessible = []
    for m in models:
        name = m.get("name", "")
        if not name:
            continue
        short = name.split("/", 1)[1] if "/" in name else name
        lower = short.lower()
        # Filter to image-output capable models. Gemini puts these in two
        # families: gemini-*-image-* (chat models with image output) and
        # imagen-* (dedicated image gen). Both work for our purpose.
        if "image" in lower or lower.startswith("imagen"):
            accessible.append(short)

    accessible.sort(key=_version_key, reverse=True)
    return accessible


# Pinned default for this framework. Per the 2026-06-01 model review:
# gemini-2.5-flash-image is the latency + stability sweet spot (~6s, ~1.4MB
# crisp PNG). The newer flash *preview* tier was both slower (~24s) and
# occasionally stalled past the 90s timeout — in a live interactive loop a
# fast, reliable cycle beats an incremental quality bump. Newer models stay
# available as manual picks in the brush selector; this is just the default.
_PREFERRED_MODEL = "gemini-2.5-flash-image"


def pick_default_image_model(models: list[str]) -> str | None:
    """From a sorted list of accessible image models, pick the default.

    Prefers the pinned _PREFERRED_MODEL when the key can reach it; otherwise
    falls back to the highest gemini-*-image, then highest imagen-*. Returns
    None if the list is empty.
    """
    if not models:
        return None
    if _PREFERRED_MODEL in models:
        return _PREFERRED_MODEL
    gemini_image = [m for m in models if not m.lower().startswith("imagen")]
    return gemini_image[0] if gemini_image else models[0]


def validate_key(api_key: str) -> list[str]:
    """Confirm the key works and report accessible image models. Raises on failure."""
    models = list_image_models(api_key)
    if not models:
        raise GeminiAPIError(
            "Key works, but no image-generation models are visible to it. "
            "Check that image generation is enabled in your Google Cloud / AI Studio billing."
        )
    return models


# ─────────────────────────────────────────────────────────────────────────────
# Image generation client
# ─────────────────────────────────────────────────────────────────────────────


class GeminiImageClient:
    """Minimal HTTP client for Gemini image-output models. Raw stdlib only."""

    def __init__(self, app_dir: Path, model: str = _PREFERRED_MODEL):
        self.app_dir = app_dir
        self.model = model

    def set_model(self, model: str) -> None:
        self.model = model

    def generate(self, prompt: str, timeout: float = 90.0) -> bytes:
        """Generate a single image from `prompt`. Returns raw PNG bytes.

        Routes by model family — the two image families on the Gemini API speak
        different endpoints:
          • imagen-*           → :predict  (dedicated image models)
          • gemini-*-image-*   → :generateContent  (chat models with IMAGE output)
        """
        key = load_api_key(self.app_dir)
        if not key:
            raise GeminiAuthError(
                "No Gemini API key found. Set one through the in-app prompt and try again."
            )

        if self.model.lower().startswith("imagen"):
            return self._generate_imagen(prompt, key, timeout)
        return self._generate_content(prompt, key, timeout)

    def _generate_content(self, prompt: str, key: str, timeout: float) -> bytes:
        """gemini-*-image models: chat-style :generateContent with IMAGE modality.
        The image comes back inline as base64 in candidates[].content.parts[]."""
        url = f"{GEMINI_BASE}/models/{self.model}:generateContent?key={key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        payload = _http_request(url, data=json.dumps(body).encode("utf-8"), timeout=timeout)

        try:
            parts = payload["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        except (KeyError, IndexError, TypeError) as e:
            raise GeminiAPIError(f"Unexpected Gemini response shape: {e}") from e

        raise GeminiAPIError("Gemini response contained no image payload")

    def _generate_imagen(self, prompt: str, key: str, timeout: float) -> bytes:
        """imagen-* models: the dedicated :predict endpoint.

        Different shape from :generateContent — the prompt goes in `instances`,
        knobs in `parameters`, and the image returns as base64 in
        predictions[].bytesBase64Encoded. sampleCount is pinned to 1 (the -ultra
        variant only ever returns a single image anyway)."""
        url = f"{GEMINI_BASE}/models/{self.model}:predict?key={key}"
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1},
        }
        payload = _http_request(url, data=json.dumps(body).encode("utf-8"), timeout=timeout)

        try:
            for pred in payload["predictions"]:
                b64 = pred.get("bytesBase64Encoded") or pred.get("bytes_base64_encoded")
                if b64:
                    return base64.b64decode(b64)
        except (KeyError, IndexError, TypeError) as e:
            raise GeminiAPIError(f"Unexpected Imagen response shape: {e}") from e

        raise GeminiAPIError("Imagen response contained no image payload")
