#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - resync_floor.py refresh the committed offline floor from the live Sheet
-So a fresh clone with no network still opens on current canon, not a stale ghost, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# Pulls each registered narrative tab (quest._FLOOR_FILES) and rewrites its
# committed offline floor — Documents/Data/quest_floor.json and friends — the
# tier the Ledger prefers over the (drift-prone) inline lists when there's no
# network AND no per-tab snapshot. Mirror maintenance under the Sheet-is-canon
# doctrine: canon flows DOWN into the mirrors, never the reverse.
#
# Two callers, one engine:
#   launch — FloorResyncWorker (main_window.py) runs resync() quietly on every
#            app start: write-on-change, best-effort, offline keeps the disk
#            floor as-was. A fresh clone heals itself on its first online run.
#   manual — python -m utils.resync_floor   (same engine, printed report)
#
# Both source runs and the frozen exe resolve the floor via app_root(), the same
# door the Ledger's reader uses, so there is exactly one floor per checkout.

from __future__ import annotations

import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from quest import _FLOOR_FILES, _rows_to_scenes
from utils.logger import get_logger
from utils.paths import app_root
from utils.sheets import SheetsClient, SheetsError

logger = get_logger("gentle")


def resync(emit=None) -> tuple[int, int]:
    """Refresh every registered tab's committed floor from the live Sheet.
    Returns (updated, failures). Write-on-change: an unmoved canon leaves the
    file — and therefore the git tree — untouched. Per-tab best-effort: a tab
    that's unreachable or empty keeps its existing floor and counts as a
    failure; the caller decides how loudly that matters. Constructing the
    SheetsClient raises SheetsAuthError when the proxy isn't configured —
    also the caller's call."""
    say = emit or (lambda line: logger.debug(f"[floor] {line}"))
    client = SheetsClient()
    data_dir = app_root() / "Documents" / "Data"
    updated = failures = 0
    for tab, fn in _FLOOR_FILES.items():
        try:
            scenes = _rows_to_scenes(client.read_sheet(tab))
        except SheetsError as e:
            say(f"{tab} unreachable ({e}) — {fn} kept as-is.")
            failures += 1
            continue
        if not scenes:
            say(f"{tab} empty or unreadable — {fn} kept as-is.")
            failures += 1
            continue
        text = json.dumps(scenes, ensure_ascii=False, indent=2)
        out = data_dir / fn
        try:
            current = out.read_text(encoding="utf-8") if out.exists() else None
        except (OSError, ValueError):
            # An unreadable floor (disk fault, foreign-encoding re-save) reads as
            # 'different' — the one file most in need of the heal below.
            current = None
        if current == text:
            say(f"{tab} floor already current ({len(scenes)} scene(s)).")
            continue
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(out)   # atomic publish — a cold-start reader never sees a torn floor
        except OSError as e:
            say(f"{fn} not writable ({e}) — floor kept as-is.")
            failures += 1
            continue
        updated += 1
        say(f"resynced floor: {tab} {len(scenes)} scene(s) -> Documents/Data/{fn}")
    return updated, failures


def main() -> int:
    _updated, failures = resync(emit=print)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
