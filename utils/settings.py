#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - settings.py TOML loader
-The dials live in one place, by one hand, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)
