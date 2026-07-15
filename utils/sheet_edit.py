#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - sheet_edit.py a surgical, clobber-safe single-cell sheet editor
-Change one true word in the Ledger without disturbing its neighbours, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# One-line tweaks to the live Ledger WITHOUT the re-mint clobber. The sanitize
# --push path rewrites every row from the (often stale) bundled canon; this finds
# exactly one cell containing `old`, replaces the substring, and writes the rows
# back — everything else byte-for-byte untouched. Backs up first, verifies after,
# and auto-restores if the read-after-write check fails.
#
#   python utils/sheet_edit.py Quest_Log "old text" "new text"            # dry run
#   python utils/sheet_edit.py Quest_Log "old text" "new text" --apply    # write

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:                                   # UTF-8 stdout so sheet unicode never crashes cp1252
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from utils.paths import app_root
from utils.sheets import SheetsClient


def edit_cell(tab: str, old: str, new: str, apply: bool = False) -> int:
    c = SheetsClient()
    rows = c.read_sheet(tab)
    if not rows:
        print(f"tab {tab!r} is empty or unreadable"); return 1

    hits = [(r, col) for r, row in enumerate(rows)
            for col, cell in enumerate(row) if isinstance(cell, str) and old in cell]
    if len(hits) != 1:
        print(f"ABORT: expected exactly 1 occurrence of {old!r}, found {len(hits)}: {hits}")
        return 2

    r, col = hits[0]
    before = rows[r][col]
    after = before.replace(old, new)
    print(f"match: row {r + 1} (id {rows[r][0]!r}), col {col}")
    print(f"  before: {before[:140]!r}")
    print(f"  after : {after[:140]!r}")
    if not apply:
        print("(dry run — pass --apply to write to the live sheet)")
        return 0

    bkdir = app_root() / "Documents" / "Data"
    bkdir.mkdir(parents=True, exist_ok=True)
    bkf = bkdir / f"{tab}_backup_{time.strftime('%Y%m%d-%H%M%S')}.json"
    bkf.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    orig = json.loads(json.dumps(rows))   # deep copy for restore

    rows[r][col] = after
    c.replace_rows(tab, rows[1:])         # data rows only; header preserved

    back = c.read_sheet(tab)
    new_ok = any(isinstance(x, str) and new in x for row in back for x in row)
    old_gone = not any(isinstance(x, str) and old in x for row in back for x in row)
    count_ok = len(back) == len(orig)
    if new_ok and old_gone and count_ok:
        print(f"OK: written + verified (backup -> {bkf.name})")
        return 0
    print("!! verify FAILED -> restoring from backup")
    c.replace_rows(tab, orig[1:])
    return 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Surgical single-cell find/replace on a GA Ledger tab (clobber-safe).")
    ap.add_argument("tab", help="sheet tab name, e.g. Quest_Log")
    ap.add_argument("old", help="exact substring to find (must occur in exactly one cell)")
    ap.add_argument("new", help="replacement substring")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default is a dry-run preview)")
    a = ap.parse_args(argv)
    return edit_cell(a.tab, a.old, a.new, apply=a.apply)


if __name__ == "__main__":
    sys.exit(main())
