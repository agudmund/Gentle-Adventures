#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - settings.py TOML loader
-The dials live in one place, by one hand, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from pathlib import Path

import tomllib


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)
