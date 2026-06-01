#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - housekeeping.py sweep Python bytecode on exit
-She tidies her room before the lights go out, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("gentle")


def _mirror_root(project_root: Path) -> Path | None:
    """Where PYTHONPYCACHEPREFIX mirrors this project's .pyc tree, or None.

    With sys.pycache_prefix set, CPython writes each module's .pyc under
    <prefix>/<source-dir-with-drive-anchor-stripped>/__pycache__/, so this
    project's whole cache lives under <prefix>/<root sans anchor>. Returning
    that lets the sweep clear redirected bytecode (%APPDATA%) — not just the
    in-tree __pycache__ dirs, which are empty once the prefix is active.
    """
    prefix = getattr(sys, "pycache_prefix", None)
    if not prefix:
        return None
    parts = project_root.parts[1:] if project_root.anchor else project_root.parts
    return Path(prefix, *parts)


def clean_pycache(root: str | Path) -> int:
    """Remove __pycache__ dirs + *.pyc under `root`, plus this project's mirror
    subtree under PYTHONPYCACHEPREFIX when bytecode is redirected.

    Best-effort and exception-proof — it runs during shutdown and must never
    block or crash the exit. Returns the number of trees removed.
    """
    root = Path(root)
    removed = 0
    try:
        for item in root.rglob("__pycache__"):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed += 1
        for pyc in root.rglob("*.pyc"):
            pyc.unlink(missing_ok=True)
    except Exception:
        pass

    mirror = _mirror_root(root)
    if mirror and mirror.exists():
        try:
            shutil.rmtree(mirror, ignore_errors=True)
            removed += 1
        except Exception:
            pass

    return removed
