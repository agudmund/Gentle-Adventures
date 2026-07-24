#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - add_lookout_scene.py one-shot ledger migration: the Lookout
-A small glass dome added to the orbital twin, where wondering is free, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# One-shot operator migration (2026-06-12): adds the hy_lookout scene to the
# live HY_World tab and links it from hy_confirm's both faces. Sheet is canon;
# this is the deliberate, reviewable write that puts the scene there. Safe to
# re-run (idempotent: updates in place, appends only if missing).

import json

from utils.identity import sheets_client

LOOKOUT_NARRATIVE = (
    "A narrow stair curls up from the games wall to a small glass dome — "
    "the lookout.\n\n"
    "A long brass glass rests on the rail, already aimed at the twin's berth. "
    "The ship asks the harbour the same small question your console asks — "
    "“how is she?” — and the harbour always answers plainly.\n\n"
    "Raise the glass whenever you wonder, Captain. Wondering is free; only "
    "the warm cores cost coin."
)

LOOKOUT_PROMPT = (
    "A tiny chibi astronaut in a small round glass observatory dome atop a "
    "pastel space station, peering through a long brass telescope aimed at a "
    "distant warm station-light among soft stars, cozy 3D, glossy toy finish, "
    "dreamy bokeh, gentle volumetric light."
)

CONFIRM_CHOICES = [
    {"label": "Watch them play", "next": "hy_confirm"},
    {"label": "Up to the lookout", "next": "hy_lookout"},
    {"label": "Home, to the ship", "next": "hy_ascent"},
]
CONFIRM_CHOICES_ABSENT = [
    {"label": "Wake the orbital twin", "action": "wake_hyworld"},
    {"label": "Up to the lookout", "next": "hy_lookout"},
    {"label": "Home, to the ship", "next": "hy_ascent"},
]
LOOKOUT_CHOICES = [
    {"label": "Ask after the twin", "action": "hyworld_status"},
    {"label": "Back to the games", "next": "hy_confirm"},
    {"label": "Home, to the ship", "next": "hy_ascent"},
]


def main() -> int:
    client = sheets_client()
    rows = client.read_sheet("HY_World")
    header = [str(h).strip() for h in rows[0]]
    data = [r for r in rows[1:] if str(r[0] if r else "").strip()]
    col = {name: header.index(name) for name in header if name}

    for r in data:
        while len(r) < len(header):
            r.append("")

    ids = [str(r[col["Scene_ID"]]).strip() for r in data]

    for r in data:
        if str(r[col["Scene_ID"]]).strip() == "hy_confirm":
            r[col["Choices_JSON"]] = json.dumps(CONFIRM_CHOICES)
            r[col["Choices_Absent_JSON"]] = json.dumps(CONFIRM_CHOICES_ABSENT)

    if "hy_lookout" not in ids:
        row = [""] * len(header)
        row[col["Scene_ID"]] = "hy_lookout"
        row[col["Title"]] = "HY-World, 04 — The Lookout"
        row[col["Narrative_Template"]] = LOOKOUT_NARRATIVE
        row[col["Choices_JSON"]] = json.dumps(LOOKOUT_CHOICES)
        row[col["Image_Prompt"]] = LOOKOUT_PROMPT
        data.append(row)

    print(f"writing {len(data)} data rows")
    print(client.replace_rows("HY_World", data))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
