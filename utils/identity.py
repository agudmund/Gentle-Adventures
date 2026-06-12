#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - identity.py the ship's signature on every outbound call
-One name, one version, so our traffic is never anonymous noise in another's log, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

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
