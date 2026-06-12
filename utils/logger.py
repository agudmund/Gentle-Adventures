#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - logger.py family Rust-logger wiring (intricate_log) with a stdlib fallback
-Every step is remembered, none for shame, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
from pathlib import Path

# Prefer the family's Rust logger — intricate_log via shared_braincell.logger.
# It's the same lock-free, timestamped-per-run, retention-managed sink the rest
# of the suite writes to (the shared [shared] log_dir), so Gentle Adventures'
# lines land alongside its siblings, tagged logger="gentle". If the family
# spine isn't importable (a bare clone without the deps), we fall back to a
# stdlib console+file logger so GA still keeps its logs rather than going
# silent — GA's own choice, distinct from the family's NullLogger contract.
try:
    import leopold  # noqa: F401 — presence probe
    from shared_braincell.logger import setup_logger as _family_setup
    from shared_braincell.logger import init_app as _family_init_app
    _HAVE_FAMILY = True
except Exception:
    leopold = None  # type: ignore
    _family_setup = None
    _family_init_app = None
    _HAVE_FAMILY = False

# Set once, before the first family logger is requested — names this process's
# run `gentle_<timestamp>.log` so GA's logs are attributable beside their
# siblings (Intricate, Majestic…) in the shared log dir, rather than all sharing
# the legacy `intricate_` prefix. Falls back silently on an older spine.
_APP_INITED = False


def get_logger(name: str = "gentle"):
    """Return the shared logger for *name*.

    Family Rust adapter when the suite is installed, GA's stdlib fallback
    otherwise. Cached by name on both paths, so every module that calls
    get_logger("gentle") shares one logger object.
    """
    if _HAVE_FAMILY and _family_setup is not None:
        global _APP_INITED
        if not _APP_INITED:
            _APP_INITED = True
            if _family_init_app is not None:
                try:
                    _family_init_app("gentle")   # → gentle_<timestamp>.log
                except Exception:
                    pass   # older spine without init_app — logs as intricate_*
        return _family_setup(name)
    return _stdlib_logger(name)


def _stdlib_logger(name: str) -> logging.Logger:
    """Last-resort console+file logger (the old glorified print-wrapper, kept
    only for machines without the family logger)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    try:
        from utils.paths import app_root
        # Family convention: app-local logs live under Documents/Data/Logs/
        # (the shared [shared] log_dir fallback shape), not a root-level logs/.
        logs_dir = app_root() / "Documents" / "Data" / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logs_dir / "gentle.log", mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)
    return logger


def init_logger(app_dir: Path):
    """Startup entry — wire the logger and announce readiness + the backend.

    `app_dir` is kept for signature compatibility; the family path resolves its
    own shared log dir, and the stdlib fallback derives its own from this file.
    """
    logger = get_logger("gentle")
    if _HAVE_FAMILY:
        try:
            backend = leopold.BACKEND
            path = leopold.log_file_path() or "(shared log dir)"
        except Exception:
            backend, path = "family", "(shared log dir)"
        logger.info(f"Gentle Adventures logger ready — intricate_log [{backend}] → {path}")
    else:
        logger.info("Gentle Adventures logger ready — stdlib fallback (family spine not found)")
    return logger
