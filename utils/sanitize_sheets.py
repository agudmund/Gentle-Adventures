#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - sanitize_sheets.py the Ledger's lint, a value-grep over the live Sheet
-We sweep the cloud grid for words the canon has long since outgrown, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# A small operator tool, two modes:
#   report (default) — grep EVERY cell of the live ledger tabs for retired phrases
#                      and print where they linger. Read-only; surfaces the signal,
#                      never auto-heals (the family's drift-accountability posture).
#   --push           — re-seed the Quest_Log tab from the bundled QUEST mirror in
#                      quest.py. The Sheet is canon (the author writes the Sheet;
#                      mirrors flow down — quest.py's _Ledger docstring and
#                      State Sync v2.md are the doctrine of record): this verb is
#                      a repair-and-bootstrap device — first mint of an empty
#                      Sheet, or correcting a recorded deviation — never an
#                      authoring rail. Diff-preview by default; --apply writes.
#
# Why this and not a generated Sheets CLI: the family already owns an Apps Script
# proxy (shared_braincell.sheets over raw urllib). A Sheets-API CLI would drag in OAuth2 +
# the Google SDK — two breaks with raw-HTTP / no-SDK sovereignty. So we reuse the
# courier we already have. The write path is field-proven: replace_rows() first
# ran against the live proxy 2026-06-05 (the sheet_edit --apply backups on disk),
# and the Quest_Log was re-minted 2026-07-05 (commit e6b721d) to correct the
# July-4 authoring deviation. The dry-run-first guard stays as standing
# discipline, not as a maiden-voyage precaution.

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Run-from-anywhere: put the project root (this file's parent's parent) on the
# path so `utils.*` and `data.*` resolve whether invoked as a module or a script.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.identity import sheets_client                     # noqa: E402
from shared_braincell.sheets import SheetsProxyClient, SheetsError   # noqa: E402
from quest import QUEST, _SHEET_COLUMNS                # noqa: E402

# ── Control surfaces — edit these like a console ─────────────────────────────
# Tabs to sweep. Quest_Log is the content mirror; Player_State is live state.
TABS = ["Quest_Log", "Player_State"]

# Retired phrases / patterns that should no longer appear anywhere in the sheet.
# Add a line whenever you rename canon (e.g. a choice label); the sweep then flags
# any cell still carrying the old wording. Case-insensitive regex.
STALE_PATTERNS = [
    r"cast the rite",   # retired choice label (canon: "The oracle is awake")
]
# ─────────────────────────────────────────────────────────────────────────────


def _col_letter(idx: int) -> str:
    """0-based column index → spreadsheet letters (0→A, 26→AA)."""
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def scan(client: SheetsProxyClient) -> list[dict]:
    """Grep every cell of every TAB against STALE_PATTERNS. Read-only."""
    pats = [(p, re.compile(p, re.IGNORECASE)) for p in STALE_PATTERNS]
    hits: list[dict] = []
    for tab in TABS:
        try:
            rows = client.read_sheet(tab)
        except SheetsError as e:
            print(f"  ! {tab}: unreadable ({e})")
            continue
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                text = "" if cell is None else str(cell)
                for src, rx in pats:
                    if rx.search(text):
                        snippet = text if len(text) <= 80 else text[:77] + "…"
                        hits.append({
                            "tab": tab,
                            "cell": f"{_col_letter(c)}{r + 1}",
                            "pattern": src,
                            "value": snippet,
                        })
    return hits


def _scene_to_row(scene: dict, header: list[str], current_row: list | None) -> list:
    """Serialize a bundled scene into a row matching the live header order. Columns
    the header carries that aren't in _SHEET_COLUMNS keep their current value, so a
    re-mint never blanks an extra note column the sheet may hold."""
    row = []
    for ci, label in enumerate(header):
        key = _SHEET_COLUMNS.get(str(label).strip())
        if key is None:
            row.append(current_row[ci] if current_row and ci < len(current_row) else "")
            continue
        val = scene.get(key, "")
        if key == "choices":
            val = json.dumps(val, ensure_ascii=False)
        elif val is None:
            val = ""
        row.append(val)
    return row


def _quest_log_state(client: SheetsProxyClient):
    """(header, current_data_rows, fresh_data_rows) for Quest_Log, so a push can be
    reviewed before it's made."""
    rows = client.read_sheet("Quest_Log")
    if not rows:
        raise SheetsError("Quest_Log is empty or unreadable — nothing to diff/push.")
    header = [str(h).strip() for h in rows[0]]
    current = rows[1:]
    fresh = [_scene_to_row(s, header, current[i] if i < len(current) else None)
             for i, s in enumerate(QUEST)]
    return header, current, fresh


def report() -> int:
    client = sheets_client()
    print("✦ Ledger sanitizer — scanning for retired phrases ✦\n")
    hits = scan(client)
    if not hits:
        print("  ✓ clean — no stale patterns found.")
        return 0
    print(f"  ⚠ {len(hits)} stale cell(s):\n")
    for h in hits:
        print(f"    {h['tab']}!{h['cell']}  /{h['pattern']}/  →  {h['value']!r}")
    print("\n  Re-seed Quest_Log from the bundled mirror with:  python utils/sanitize_sheets.py --push")
    return 1


def _bump_meta_version(client: SheetsProxyClient) -> None:
    """Best-effort: advance _meta!version after a content re-mint, so the game's
    revert guard has a fresh monotonic number to arbitrate with. Silently skipped if
    there's no _meta tab — the core last-good/hash/floor protections don't need it."""
    try:
        rows = client.read_sheet("_meta")
        cur = 0
        for row in rows or []:
            cells = [str(c).strip() for c in row]
            if len(cells) >= 2 and cells[0].lower() == "version":
                cur = int(float(cells[1]))
                break
        client.replace_rows("_meta", [["version", str(cur + 1)]])
        print(f"  ✓ _meta version bumped to {cur + 1}")
    except Exception as e:
        print(f"  (note: _meta version not bumped — {e}; add a _meta tab with a "
              f"'version' row to enable the revert guard)")


def push(apply: bool) -> int:
    client = sheets_client()
    header, current, fresh = _quest_log_state(client)
    print("✦ Quest_Log re-seed — bundled QUEST mirror → sheet (repair/bootstrap; the Sheet is canon) ✦\n")
    changed = 0
    for i, (scene, fresh_row) in enumerate(zip(QUEST, fresh)):
        cur_row = current[i] if i < len(current) else []
        if [str(x) for x in fresh_row] != [str(x) for x in cur_row]:
            changed += 1
            print(f"    ~ row {i + 2} ({scene['id']}) differs")
    extra = len(current) - len(QUEST)
    if extra > 0:
        print(f"    - {extra} trailing sheet row(s) beyond the bundled mirror would be dropped")
    if changed == 0 and extra == 0:
        print("  ✓ Quest_Log already matches the bundled mirror — nothing to push.")
        return 0
    print(f"\n  {changed} row(s) differ; writing {len(fresh)} mirror row(s) total.")
    if not apply:
        print("  (dry run — re-run with --push --apply to write to the live sheet)")
        return 0
    client.replace_rows("Quest_Log", fresh)
    print("  ✓ Quest_Log re-seeded from the bundled mirror.")
    _bump_meta_version(client)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Grep / sanitize the GA Google Sheet ledger.")
    ap.add_argument("--push", action="store_true",
                    help="re-seed Quest_Log from the bundled QUEST mirror — repair/bootstrap, "
                         "the Sheet is canon (diff preview by default)")
    ap.add_argument("--apply", action="store_true",
                    help="with --push: actually write the sheet (otherwise dry-run only)")
    args = ap.parse_args(argv)
    try:
        return push(apply=args.apply) if args.push else report()
    except SheetsError as e:
        print(f"  ! sheets unavailable: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
