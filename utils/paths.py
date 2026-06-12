#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - paths.py the frozen-aware home finder
-Wherever the ship sails, it always knows the way home, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """The app's on-disk home: the folder holding the .exe when frozen, or the
    project root (the parent of this ``utils/`` package) when run from source.

    Why this exists — PyInstaller --onedir bundles the code under ``_internal/``,
    which GA junctions to the SHARED ``../_runtime``. So in a frozen build any
    ``Path(__file__).parent...`` in a *non-entry* module resolves INTO the shared
    runtime, not next to the .exe: asset reads miss (Images/Icons/, Images/Scenes/, the play
    sticker) and — worse — writes (logs, Documents/Data, caches) would pollute
    the runtime that every family app junctions to. Always derive app-local
    paths from here, never from a non-entry module's ``__file__``.

    The entry script (``main.py``) is the one place ``__file__`` happens to land
    on the .exe dir when frozen, but it should use this too, for one source of
    truth.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
