#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - probe.py system-state checks the game uses to verify real-world steps
-The ship feels its own pulse and reports back, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("gentle")


def probe_npu() -> bool:
    """Return True if any NPU/AI-Engine device is enumerated on this machine.

    Uses Windows PnP enumeration via PowerShell. False on non-Windows or when
    no NPU is exposed.
    """
    if os.name != "nt":
        return False
    try:
        script = (
            "Get-PnpDevice | Where-Object { "
            "$_.FriendlyName -match 'NPU|IPU|Neural|AI Engine|XDNA' "
            "} | Select-Object -First 1 -ExpandProperty FriendlyName"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        found = bool(result.stdout.strip())
        logger.debug(f"NPU probe: {result.stdout.strip() or 'not found'}")
        return found
    except Exception as e:
        logger.debug(f"NPU probe failed: {e}")
        return False


def probe_lm_studio() -> bool:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "LM Studio" / "LM Studio.exe",
        Path(os.environ.get("ProgramFiles", "")) / "LM Studio" / "LM Studio.exe",
    ]
    return any(p.exists() for p in candidates if str(p))


def probe_local_api(url: str = "http://localhost:1234/v1/models", timeout: float = 1.5) -> bool:
    """Return True if an OpenAI-compatible local server (LM Studio etc.) is up."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False
