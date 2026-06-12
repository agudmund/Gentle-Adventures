#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - resync_floor.py refresh the committed offline floor from the live Sheet
-So a fresh clone with no network still opens on current canon, not a stale ghost, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# Pulls the live Quest_Log and writes Documents/Data/quest_floor.json — the
# committed offline floor the Ledger prefers over the (hand-formatted,
# drift-prone) inline QUEST when there's no network AND no per-tab snapshot.
# Re-run whenever the Sheet has moved on (as a module, so `quest` is importable):
#   python -m utils.resync_floor
#
# Source-side only: the frozen app keeps the inline QUEST as its compiled-in
# backstop (it almost never hits the floor — the snapshot mirrors the Sheet after
# the first online run). This keeps fresh CLONES current without bundling a loose
# data file into the shared runtime.

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from quest import _rows_to_scenes
from utils.sheets import SheetsClient


def main() -> int:
    rows = SheetsClient().read_sheet("Quest_Log")
    scenes = _rows_to_scenes(rows)
    if not scenes:
        print("Quest_Log empty or unreadable — floor NOT updated.")
        return 1
    out = Path(__file__).resolve().parent.parent / "Documents" / "Data" / "quest_floor.json"
    out.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"resynced floor: {len(scenes)} scene(s) -> {out.relative_to(out.parent.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
