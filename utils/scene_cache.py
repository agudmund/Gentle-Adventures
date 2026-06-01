#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - scene_cache.py the image-state manager
-Once painted, a scene is remembered, not repainted, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("gentle")


class SceneCache:
    """Filesystem-backed cache for generated scene images — the app's image
    state.

    A scene's PNG, once the painter delivers it, is written here and reused on
    every revisit and every relaunch (the load path checks ``has`` before ever
    commissioning a new render). The directory is committed into the repo, so
    the canonical scene art travels with a fresh clone: the first open lands
    straight on the baked image instead of waiting on the painter again.

    To force a re-render of a scene, delete its PNG (or call ``discard``) — the
    next visit finds no cache and commissions a fresh one, which then becomes
    the new canonical art on the next commit.
    """

    def __init__(self, scenes_dir: Path):
        self.scenes_dir = Path(scenes_dir)
        self.scenes_dir.mkdir(parents=True, exist_ok=True)

    def path(self, scene_id: str) -> Path:
        """Absolute path where this scene's image lives (whether or not it exists)."""
        return self.scenes_dir / f"{scene_id}.png"

    def has(self, scene_id: str) -> bool:
        """True if a cached image already exists for this scene."""
        return self.path(scene_id).is_file()

    def store(self, scene_id: str, data: bytes) -> Path:
        """Write freshly generated image bytes to the cache; return the path."""
        p = self.path(scene_id)
        p.write_bytes(data)
        logger.info(f"[cache] stored '{scene_id}' → {p.name} ({len(data)} bytes)")
        return p

    def discard(self, scene_id: str) -> bool:
        """Drop a cached image so the next visit re-renders it. True if removed."""
        p = self.path(scene_id)
        if p.is_file():
            p.unlink()
            logger.info(f"[cache] discarded '{scene_id}' — will re-render on next visit")
            return True
        return False

    def cached_ids(self) -> list[str]:
        """Scene ids that currently have a baked image, sorted."""
        return sorted(p.stem for p in self.scenes_dir.glob("*.png"))
