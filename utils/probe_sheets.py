#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - probe_sheets.py live round-trip fidelity probe for the Sheets channel
-The last of the honest customs officers opens every suspicious parcel at the border and stamps what actually arrived, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# The standing round-trip test for the Ledger channel, born of the 2026-07-24
# scope pass (Sakura-rail lessons -> the Sheets channel, Asana 1216831654328915).
# Writes the known hazard values through BOTH write paths (updates/upsert and
# rows/replace) against the _probe scratch tab, reads them back, and reports
# per-value fidelity. Run it after every Code.gs paste-and-redeploy — it is the
# proof half of the deploy ritual.
#
#   python -m utils.probe_sheets
#
# What PASS means per hazard, under the 2026-07-24 Code.gs guards:
#   - breath/nfc/nfd/newline: byte-exact Unicode round-trip (NFD stays NFD —
#     live-proven that Sheets never normalizes; narration breath cues are safe)
#   - time/date/leadzero/numstr/scene-id shapes: the '@' guard on both paths
#     (pre-guard, a virgin column coerced '03:00:33' onto the 1899 epoch and
#     ate '3-1' as March 1st)
#   - formula '=1+1': the _literal apostrophe guard (pre-guard it EXECUTED to 2
#     on both paths, straight through the '@' format)
#   - int 42: stays an int ('@' does not textify numbers — live evidence)
# A FAIL on formula/time shapes against an older deployment is the expected
# signature of "the new Code.gs is not deployed yet", not a courier bug.
# Scratch writes only — the probe never touches the live game tabs.

from __future__ import annotations

import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from utils.identity import sheets_client
from shared_braincell.sheets import SheetsError

TAB = "_probe"

HAZARDS = {
    "breath":      "Soft… — and then",   # ellipsis + em-dash (narration breath cues)
    # Escapes, not literals, for the normalization pair: a file writer can
    # silently normalize a combining-mark literal to NFC (it happened twice
    # while authoring this file), and the NFD test then tests nothing.
    "nfc":         "café",                    # NFC precomposed
    "nfd":         "café",                   # NFD decomposed (e + combining acute)
    "newline":     "line1\nline2",
    "time_shape":  "03:00:33",                      # the 2026-06-03 coercion finding
    "date_shape":  "2026-07-24",
    "scene_id":    "3-1",                           # Quest_Log Scene_ID shape
    "leadzero":    "007",
    "numstr":      "3.10",
    "formula":     "=1+1",                          # formula-interpretation hazard
    "plus_lead":   "+alpha",
    "bool_shape":  "TRUE",
    "int_value":   42,                              # a real int — must stay an int
    "empty":       "",
}


def _form(s) -> str:
    if not isinstance(s, str):
        return type(s).__name__
    kinds = []
    if s != unicodedata.normalize("NFC", s):
        kinds.append("not-NFC")
    if s != unicodedata.normalize("NFD", s):
        kinds.append("not-NFD")
    return "+".join(kinds) if kinds else "NFC=NFD"


def _compare(label: str, sent, got) -> bool:
    ok = (sent == got)
    got_form = _form(got) if got is not None else "missing"
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:11s} sent={sent!r} ({_form(sent)})  got={got!r} ({got_form})")
    return ok


def probe() -> int:
    """Run both write paths through the hazard matrix. Returns failure count."""
    c = sheets_client()
    failures = 0

    print("== path 1: write_state (updates/upsert) ==")
    c.write_state(TAB, HAZARDS, create=True, header=["Variable_Name", "Value", "Stamped"])
    state = c.read_state(TAB)
    failures += sum(not _compare(k, v, state.get(k)) for k, v in HAZARDS.items())

    print("== path 2: replace_rows (rows/replace) ==")
    c.replace_rows(TAB, [[k, v] for k, v in HAZARDS.items()])
    matrix = c.read_sheet(TAB)
    back = {str(r[0]): (r[1] if len(r) > 1 else "") for r in matrix[1:] if r and str(r[0]).strip()}
    failures += sum(not _compare(k, v, back.get(k)) for k, v in HAZARDS.items())

    return failures


def main() -> int:
    try:
        failures = probe()
    except SheetsError as e:
        print(f"sheets channel unavailable ({e}) — probe not run.")
        return 2
    print(f"== {'all clear' if not failures else f'{failures} failure(s)'} ==")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
