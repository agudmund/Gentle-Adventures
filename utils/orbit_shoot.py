#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - orbit_shoot.py commission the painter for a surveyor's orbit
-Six angles of the same room, painted on purpose, so a world model can rebuild it, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# The Gemini-as-location-scout experiment (2026-06-12): multi-view
# reconstruction (HY-World's WorldMirror on the orbital twin) wants several
# views of the SAME scene. This tool asks the painter for a deliberate orbit
# around a reference scene image — same room, swung camera — producing the
# input set a surveyor needs. Run from the GA root:
#
#   python -m utils.orbit_shoot Images/Scenes/awakening.png <out_dir>
#
# Each view is seeded from the reference (style + room continuity) with a
# per-view camera instruction. Whether an image model can hold one room's
# geometry across eight made-up camera positions IS the experiment.

from __future__ import annotations

import sys
from pathlib import Path

from shared_braincell.gemini_image import GeminiImageClient
from utils.identity import GEMINI_KEY_ENV, user_agent

SCENE_BRIEF = (
    "the same cozy pastel spaceship bridge interior as the reference image — "
    "round porthole window with starfield, plump pink couches, the rounded "
    "console with its glowing buttons — empty, no characters present, "
)

# (filename stem, camera instruction) — an eight-stop orbit plus two braces.
VIEWS = [
    ("orbit_00_front",      "camera straight ahead facing the console and window, eye level"),
    ("orbit_01_left45",     "camera orbited 45 degrees to the left of the console, eye level, "
                            "window now off to the right side of frame"),
    ("orbit_02_left90",     "camera at 90 degrees left profile view of the console and couches, "
                            "window edge-on at the right"),
    ("orbit_03_right45",    "camera orbited 45 degrees to the right of the console, eye level, "
                            "window now off to the left side of frame"),
    ("orbit_04_right90",    "camera at 90 degrees right profile view of the console and couches, "
                            "window edge-on at the left"),
    ("orbit_05_reverse",    "camera standing at the window looking back across the console "
                            "toward the couches and the cabin door behind them"),
    ("orbit_06_high",       "camera raised high near the ceiling looking down at the console "
                            "and couches at a three-quarter angle"),
    ("orbit_07_low_wide",   "camera low near the floor, wide view taking in console, couches "
                            "and window together"),
]


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python -m utils.orbit_shoot <reference.png> <out_dir>")
        return 1
    ref = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not ref.exists():
        print(f"reference not found: {ref}")
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    client = GeminiImageClient(app_dir=Path("."), model="gemini-2.5-flash-image",
                               user_agent=user_agent("OrbitShoot"),
                               key_env_var=GEMINI_KEY_ENV)
    for stem, camera in VIEWS:
        out = out_dir / f"{stem}.png"
        if out.exists():
            print(f"have    {out.name}")
            continue
        prompt = (
            "chibi 3D rendered illustration, kawaii style, soft pastel palette, "
            "glossy plastic toy finish, square 1:1 framing, consistent gentle "
            "volumetric light, " + SCENE_BRIEF + camera +
            ", physically consistent room layout across views"
        )
        png = client.generate(prompt, reference_path=ref)
        out.write_bytes(png)
        print(f"painted {out.name} ({len(png)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
