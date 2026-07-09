#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - identity.py the ship's signature on every outbound call
-One name, one version, so our traffic is never anonymous noise in another's log, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import os
import socket

__version__ = "0.1.0"
_APP_NAME = "GentleAdventures"

# Gentle Adventures' own Gemini key slot — outranks the legacy .gemini_key
# file and the generic GEMINI_API_KEY in shared_braincell's key resolution,
# so this app's painter is keyed independently of its siblings.
GEMINI_KEY_ENV = "GEMINI_GENTLE_KEY"


def user_agent(feature: str = "") -> str:
    """Family User-Agent: ``GentleAdventures[/<Feature>]/<version> (SingleSharedBraincell)``.

    The single source of truth for outbound identity — every HTTP call imports
    this, so the version can never drift per call site. Bump ``__version__``
    here once and every signed request follows. Optional ``feature`` inserts a
    sub-segment, e.g. ``user_agent("Oracle")`` -> ``GentleAdventures/Oracle/0.1.0 (...)``.
    """
    segment = f"/{feature}" if feature else ""
    return f"{_APP_NAME}{segment}/{__version__} (SingleSharedBraincell)"


def is_wake_display() -> bool:
    """True on the TV-role machine (Sakura) that autologins straight to a
    chromeless desktop with a hidden taskbar — a screen with no visual "is it
    up yet?" cue. There GA starts MAXIMIZED and its sleeping-captain wake scene
    IS the boot heartbeat (offline while the antenna warms, waking into scene
    one the moment it connects), instead of minimizing to tray. Every other
    machine keeps the tray autostart.

    Mirrors Compass's hostname->role derivation ('tv' for Sakura). An explicit
    ``GA_WAKE_DISPLAY`` env var (1/0) overrides the hostname guess, so the role
    never has to be hardcoded to one machine when the fleet grows a second TV.
    """
    override = os.environ.get("GA_WAKE_DISPLAY")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on")
    return socket.gethostname().strip().lower() == "sakura"
