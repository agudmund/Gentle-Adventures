#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - extract_play_icon.py app-icon extraction
-The play sticker became our face, and the window learnt to wear it For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# Author-time one-shot, not a runtime module — run it by hand from the GA repo
# root after the play sticker source is refreshed. GA reuses the same Play
# sticker the rest of the family uses (the shared Iconic master lands here via
# a one-way copy into graphics/stickers/Play.png); this turns that source into
# GA's brand mark. The pipeline mirrors Intricate's extract_play_icon.py:
# largest-component cleanup -> white-matte defringe on semi-transparent edges
# -> trim + square + 1024 resize -> PNG + multi-res ICO. The ICO is what
# build.py bakes into Gentle Adventures.exe via --icon (Images/Icons/playIcon.ico),
# and what main.py / main_window.py load for the window, taskbar and systray.

from PIL import Image
import numpy as np
from scipy.ndimage import label
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = Image.open(ROOT / "graphics" / "stickers" / "Play.png").convert("RGBA")
arr = np.array(src, dtype=np.float32)
r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

# ── Keep largest connected component (kills stray dots) ──────────────
alpha_mask = a > 0
labeled, n = label(alpha_mask)
if n > 0:
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    biggest = sizes.argmax()
    a[labeled != biggest] = 0
    arr[:, :, 3] = a

# ── Defringe against white matte ─────────────────────────────────────
# Anti-aliased edge pixels carry baked-in white from the source matte.
# Reverse the compositing math:  actual = (observed - 255*(1-α)) / α.
# Solid interior pixels (α=255) are left alone.
alpha_norm = np.clip(a / 255.0, 0.001, 1.0)
semi_transparent = (a > 0) & (a < 250)
for ch in range(3):
    original = arr[:, :, ch]
    decontaminated = (original - 255.0 * (1.0 - alpha_norm)) / alpha_norm
    arr[:, :, ch] = np.where(semi_transparent, np.clip(decontaminated, 0, 255), original)

result = Image.fromarray(arr.astype(np.uint8))

# Trim transparent edges
bbox = result.getbbox()
if bbox:
    result = result.crop(bbox)

# Square with slight padding
cw, ch_px = result.size
side = int(max(cw, ch_px) * 1.1)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(result, ((side - cw) // 2, (side - ch_px) // 2))

# Resize to 1024
out = square.resize((1024, 1024), Image.LANCZOS)
icons_dir = ROOT / "Images" / "Icons"
out.save(icons_dir / "playIcon.png")

# Verify: composite on dark node background (same backdrop the family checks against)
verify_dir = ROOT / "Documents" / "Data" / "Icon Pipeline"
verify_dir.mkdir(parents=True, exist_ok=True)
dark_bg = Image.new("RGBA", (1024, 1024), (45, 52, 54, 255))
dark_bg.paste(out, (0, 0), out)
dark_bg.save(verify_dir / "_verify_play_dark.png")

# Multi-resolution ICO (what build.py bakes into the .exe)
sizes = [16, 24, 32, 48, 64, 128, 256]
out.save(icons_dir / "playIcon.ico", format="ICO", sizes=[(s, s) for s in sizes])
print(f"Extracted GA play brand mark {cw}x{ch_px} -> 1024x1024 png + ico")
