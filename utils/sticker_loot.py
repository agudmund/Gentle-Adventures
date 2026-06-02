#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - sticker_loot.py reward stickers, awarded from the iconic library
-Reach a true beat, earn a real sticker; the ship hands you a keepsake, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

from pathlib import Path

# Reward stickers are AWARDED from the official Intricate sticker library
# (one-way-copied from the iconic repo into graphics/stickers/) — NOT generated.
# They're hand-made brand assets, so they stay crisp and on-brand. Each entry
# maps a verify-bearing scene id to (sticker filename, achievement name). This
# is a purely cosmetic taste map — re-point freely; the mechanism doesn't care.
_SCENE_STICKERS: dict[str, tuple[str, str]] = {
    "discovery": ("Awake.png", "NPU Awakened"),
    "blur":      ("Loop.png",  "The Gentle Blur"),
    "summoning": ("Play.png",  "The Summoning Cast"),
    "arrival":   ("Chat.png",  "Your Oracle, Online"),
}


def stickers_dir(app_dir: Path) -> Path:
    return Path(app_dir) / "graphics" / "stickers"


def award_for_scene(scene_id: str, app_dir: Path) -> tuple[Path, str] | None:
    """The sticker earned by verifying a scene, or None.

    Returns (png_path, achievement_name) when the scene has a mapped reward and
    the asset actually exists; None otherwise (silent absence — a missing
    sticker must never break the quest)."""
    entry = _SCENE_STICKERS.get(scene_id)
    if not entry:
        return None
    filename, name = entry
    path = stickers_dir(app_dir) / filename
    return (path, name) if path.exists() else None
