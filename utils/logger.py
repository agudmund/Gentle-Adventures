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
    import intricate_log  # noqa: F401 — presence probe
    from shared_braincell.logger import setup_logger as _family_setup
    _HAVE_FAMILY = True
except Exception:
    intricate_log = None  # type: ignore
    _family_setup = None
    _HAVE_FAMILY = False


def get_logger(name: str = "gentle"):
    """Return the shared logger for *name*.

    Family Rust adapter when the suite is installed, GA's stdlib fallback
    otherwise. Cached by name on both paths, so every module that calls
    get_logger("gentle") shares one logger object.
    """
    if _HAVE_FAMILY and _family_setup is not None:
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
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
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
            backend = intricate_log.BACKEND
            path = intricate_log.log_file_path() or "(shared log dir)"
        except Exception:
            backend, path = "family", "(shared log dir)"
        logger.info(f"Gentle Adventures logger ready — intricate_log [{backend}] → {path}")
    else:
        logger.info("Gentle Adventures logger ready — stdlib fallback (family spine not found)")
    return logger
