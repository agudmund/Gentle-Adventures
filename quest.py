#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - quest.py the NPU adventure beats, scene by scene
-Every beat was written before you knew you needed it, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("gentle")

# ─────────────────────────────────────────────────────────────────────────────
# Shared visual contract for the image-gen prompts.
# Every scene prompt is composed by combining this preamble with the
# scene-specific imagery — keeps the chibi-Sierra style coherent across frames.
# ─────────────────────────────────────────────────────────────────────────────

STYLE_PREAMBLE = (
    "chibi 3D rendered illustration, kawaii style, soft pastel palette of pinks blues "
    "and warm cream, sparkle particles drifting through the air, glossy plastic toy "
    "finish, a tiny brave captain character with huge bright eyes and a soft round helmet, "
    "square 1:1 framing, soft dreamy bokeh, gentle volumetric light. "
)


def _prompt(specific: str) -> str:
    return STYLE_PREAMBLE + specific


# ─────────────────────────────────────────────────────────────────────────────
# Quest scenes — ordered, but lookup is by id so branching is easy.
# Each scene:
#   id          : string id (unique)
#   title       : the GENTLE ADVENTURES caption shown in the title bar
#   image_prompt: full text sent to Gemini (already styled)
#   narrative   : the story panel text
#   choices     : list of buttons. Each has label + next (scene id) or action.
#   verify      : optional — "npu" | "fastflowlm" | None — system probe to confirm
#   narrative_absent / choices_absent : optional — shown INSTEAD when verify=="npu"
#                 fails (no NPU aboard). Lets the story itself become the gentle
#                 guide. A verify=="npu" scene without its own narrative_absent
#                 simply gets NO_NPU_NOTE appended, so the tour reads as a lovely
#                 'someday' rather than a broken step.
# ─────────────────────────────────────────────────────────────────────────────

# Appended to any NPU-gated scene's narrative when no neural engine is found and
# the scene carries no richer narrative_absent of its own. Contextual absence,
# voiced in-world — never a grey "not detected".
NO_NPU_NOTE = (
    "(No neural engine aboard this ship yet, so this errand stays a story for "
    "now, lovely to imagine, and waiting patiently for the day you bring an "
    "XDNA-hearted vessel home.)"
)

# Shown for a breath while the ship feels for its silicon off the UI thread (the
# first NPU scene shells PowerShell, ~1-2s). A gentle, clearly-transient line so
# the page can land instantly and the resolved narrative fills in once the probe
# returns — never a frozen window.
NPU_PROBING_NOTE = (
    "The ship goes quiet a moment, feeling along its own spine,\n"
    "listening for the engine that waits somewhere in the silicon…"
)

QUEST: list[dict] = [
    {
        "id": "awakening",
        "title": "GENTLE ADVENTURES, 01 — AWAKENING",
        "image_prompt": _prompt(
            "The captain wakes at the helm of a small starship console. Three glowing "
            "lights on the console: one familiar pale-blue (labeled CPU), one familiar "
            "violet (labeled GPU), and a third light, never seen before, pulsing in soft "
            "warm gold and labeled XDNA 2. The captain leans in, curious, eyes wide."
        ),
        "narrative": (
            "The captain stirs. The ship hums a new tune.\n\n"
            "Three lights blink on the main console: one familiar, one known, one… new.\n"
            "The new light pulses with a slow, patient rhythm. Waiting.\n"
            "A small label glows beneath it: XDNA 2."
        ),
        "choices": [
            {"label": "Examine the new light", "next": "discovery"},
            {"label": "Ask what XDNA means", "next": "lore_xdna"},
        ],
        "verify": None,
    },
    {
        "id": "lore_xdna",
        "title": "GENTLE ADVENTURES, 01.5 — LORE: XDNA",
        "image_prompt": _prompt(
            "The ship's small AI hologram (a friendly translucent pastel sphere with "
            "two big eyes) materializes above the console, gesturing toward a floating "
            "diagram of a grid of tiny tiles connected by glowing dataflow lines."
        ),
        "narrative": (
            "The ship's friendly AI puffs into being above the console.\n\n"
            "\"XDNA is a grid of small minds,\" it says. \"Not one big brain, but many\n"
            "tiny ones, each doing a sliver of the math, passing the result to the\n"
            "next. The original blueprints came from Xilinx. AMD brought them aboard.\"\n\n"
            "\"It is not a CPU. It is not a GPU. It is a third kind of worker.\""
        ),
        "choices": [
            {"label": "Now examine the new light", "next": "discovery"},
        ],
        "verify": None,
    },
    {
        "id": "discovery",
        "title": "GENTLE ADVENTURES, 02 — DIAGNOSTIC CALL",
        "image_prompt": _prompt(
            "The captain pulls down a floating glowing diagnostic panel labeled "
            "'Performance': three vertical meters labeled CPU, GPU, NPU. The first "
            "two flicker with normal activity; the NPU meter sits perfectly at zero, "
            "waiting. The captain points at it with a tiny gloved hand, fascinated."
        ),
        "narrative": (
            "The diagnostic spirits respond to your call.\n"
            "A panel materializes: three meters, three names.\n\n"
            "CPU dances with everyday work. GPU naps quietly.\n"
            "The third meter, NPU, sits at zero, waiting to be invited.\n\n"
            "\"It only works for guests who bring AI errands,\" the computer murmurs.\n\n"
            "▸ On your machine: press Ctrl+Shift+Esc and look at the Performance tab.\n"
            "  See if you can find the NPU entry yourself."
        ),
        "choices": [
            {"label": "I see it", "next": "blur"},
            {"label": "Ask how to wake it", "next": "wake_lore"},
        ],
        "verify": "npu",
        # Shown instead when there's no NPU aboard (e.g. opened on Sakura). The
        # missing third meter becomes the story's gentlest teaching moment.
        "narrative_absent": (
            "The diagnostic spirits respond to your call.\n"
            "A panel materializes: three meters, three names.\n\n"
            "CPU dances with everyday work. GPU naps quietly.\n"
            "But where the third meter should be, there is only a soft, kind space.\n\n"
            "\"There's no neural engine aboard this ship, captain,\" the computer says,\n"
            "gentle as ever. \"The fancy things, the little local oracles, the\n"
            "quiet dreaming. They need one to call home.\"\n\n"
            "A kind guide told me the very same, once. \"If you'd like to play with\n"
            "the wondrous things,\" they said, \"you'll want a vessel with a neural\n"
            "engine in its heart, an AMD XDNA 2, or one of its cousins.\"\n\n"
            "So I visited a merchant (bright shelves, patient eyes) and traded\n"
            "honest riches and a pocketful of simulated gold tokens for one. (I did\n"
            "try to pay in hugs and kind praises first. Sweet currency, the merchant\n"
            "smiled, but not yet legal tender in this timeline.)\n\n"
            "The offer stands whenever you're ready, captain. Until then, the ship\n"
            "sails just fine on the gentler winds."
        ),
        "choices_absent": [
            {"label": "Ask what XDNA means", "next": "lore_xdna"},
            {"label": "Sail on, gentle and unhurried", "next": "blur"},
        ],
    },
    {
        "id": "wake_lore",
        "title": "GENTLE ADVENTURES, 02.5 — HOW TO WAKE A WORKER",
        "image_prompt": _prompt(
            "The pastel AI sphere holds up a tiny scroll with three glowing icons: "
            "a camera with a blur halo, a small llama silhouette, and a stylized "
            "transcript page. The captain looks attentively."
        ),
        "narrative": (
            "\"The NPU answers when called for three kinds of errand,\" the AI explains.\n\n"
            "  • Camera and audio effects, run gently and constantly.\n"
            "  • Local AI oracles: small models that fit in its memory.\n"
            "  • Transcription, captioning, anything that listens patiently.\n\n"
            "\"The first errand is the easiest. Want to try?\""
        ),
        "choices": [
            {"label": "Try the first errand", "next": "blur"},
        ],
        "verify": None,
    },
    {
        "id": "blur",
        "title": "GENTLE ADVENTURES, 03 — THE GENTLE BLUR",
        "image_prompt": _prompt(
            "The captain stands inside a glowing video-call window. Behind them, the "
            "bridge has softened into a pastel galaxy of bokeh and stars, magical "
            "background blur. The NPU meter visible in a corner glows softly active. "
            "The captain smiles, charmed by their own blurred backdrop."
        ),
        "narrative": (
            "Your first errand is gentle.\n\n"
            "Settings → Bluetooth & devices → Cameras → your webcam.\n"
            "Under Windows Studio Effects, switch on Background blur.\n"
            "Then open any camera preview (the Camera app will do).\n\n"
            "Watch the meters. CPU stays cool. Fans stay quiet. The NPU, finally,\n"
            "stirs, painting the blur in real time. This is what gentle work looks like."
        ),
        "choices": [
            {"label": "It works ✦", "next": "summoning"},
            {"label": "Marvel a moment", "next": "summoning"},
        ],
        "verify": "npu",
    },
    {
        "id": "summoning",
        "title": "GENTLE ADVENTURES, 04 — THE SUMMONING",
        "image_prompt": _prompt(
            "The captain stands before a tall ornate magical doorway labeled "
            "'FastFlowLM', glowing teal and gold. In their hand is a tiny glowing "
            "terminal scroll reading 'flm run llama3.2'. Around the doorway, small "
            "icons of llamas, owls, and tiny robots peek out shyly."
        ),
        "narrative": (
            "The second errand needs invocation.\n\n"
            "A local oracle (a small mind that runs right on your ship's NPU)\n"
            "would answer you without ever calling the cloud spirits. Smaller of\n"
            "voice, but always present, always private, always close.\n\n"
            "Fetch the summoner first: FastFlowLM, a tiny runtime that speaks to\n"
            "the NPU directly (fastflowlm.com, installed in under a minute). Then\n"
            "call your first oracle down with a single line:\n"
            "    > flm run llama3.2:3b"
        ),
        "choices": [
            {"label": "Validate the ship first", "action": "validate_ship"},
            {"label": "The oracle is awake", "next": "arrival"},
            {"label": "Ask what models do", "next": "model_lore"},
        ],
        "verify": "fastflowlm",
    },
    {
        "id": "model_lore",
        "title": "GENTLE ADVENTURES, 04.5 — WHAT IS A LOCAL MODEL",
        "image_prompt": _prompt(
            "A row of small pastel creatures: a llama, an owl, a fox, each carrying "
            "a tiny scroll labeled with parameter counts (3B, 7B, 8B). The captain "
            "studies them like a kindly zookeeper."
        ),
        "narrative": (
            "\"A model is a frozen mind,\" the AI says. \"Trained on books and code\n"
            "and conversations, then captured into a file you can carry.\"\n\n"
            "\"The big ones, like the cloud spirits, would never fit on your ship.\n"
            "The small ones do. They are gentler, less knowing, but always with you.\"\n\n"
            "\"For your first oracle, try Llama 3.2, three billion parameters,\n"
            "small enough to run right on your NPU.\""
        ),
        "choices": [
            {"label": "Back to the doorway", "next": "summoning"},
        ],
        "verify": None,
    },
    {
        "id": "arrival",
        "title": "GENTLE ADVENTURES, 05 — ARRIVAL",
        "image_prompt": _prompt(
            "A glowing portal opens on the bridge. From it walks a small soft pastel "
            "llama with kind eyes and tiny sparkles around its hooves. The captain "
            "kneels and offers a hand. The NPU meter in the background glows warmly."
        ),
        "narrative": (
            "The portal opens.\n\n"
            "From it emerges a llama: soft, three billion parameters, friendly.\n"
            "Llama 3.2 3B walks to your side and bows its small head.\n\n"
            "The NPU graph blooms. Forty teraops light up like an aurora.\n"
            "Your private oracle is here."
        ),
        "choices": [
            {"label": "Greet the llama", "next": "dialogue"},
            {"label": "Ask the llama a question", "next": "dialogue"},
        ],
        "verify": "npu",
    },
    {
        "id": "dialogue",
        "title": "GENTLE ADVENTURES, 06 — DIALOGUE",
        "image_prompt": _prompt(
            "The captain and the pastel llama sit side by side at a small console, "
            "speech bubbles drifting between them. One bubble holds a tiny question "
            "mark, the other a tiny lightbulb. The NPU meter in the corner is active."
        ),
        "narrative": (
            "You ask it: \"What do you feed a sparrow if one were so inclined to find one in a window on a spaceship?\"\n\n"
            "The llama answers in your terminal, syllable by syllable.\n"
            "No call leaves the ship. No server warms in a faraway data center.\n"
            "Just the NPU, breathing softly, doing what it was made for.\n\n"
            "Ask it anything. It will not always be right, but it will always be here."
        ),
        "choices": [
            {"label": "Continue", "next": "gate"},
        ],
        "verify": None,
    },
    {
        "id": "gate",
        "title": "GENTLE ADVENTURES, 07 — THE LOCALHOST GATE",
        "image_prompt": _prompt(
            "On the bridge appears a small ornate door floating in the air, glowing "
            "soft gold. Above it floats the inscription 'localhost · OpenAI'. Beyond "
            "the door, faint friendly silhouettes of other tools and ships approach, "
            "knocking politely."
        ),
        "narrative": (
            "The final discovery: your llama can serve other ships too.\n\n"
            "Leave FastFlowLM running as a local server: an OpenAI-compatible\n"
            "door on your own machine. Any tool that speaks the old protocol can\n"
            "knock and be answered, and every word still stays aboard your ship.\n\n"
            "Your private oracle, available to your whole fleet."
        ),
        "choices": [
            {"label": "Open the door", "next": "resonance"},
        ],
        "verify": None,
    },
    {
        "id": "resonance",
        "title": "GENTLE ADVENTURES, 08 — RESONANCE",
        "image_prompt": _prompt(
            "Wide shot of the bridge. The captain stands at the helm with the pastel "
            "llama by their side. All three console lights (CPU, GPU, NPU) glow "
            "harmoniously in soft pinks, blues, and gold. Stars drift past the viewport. "
            "The mood is peaceful, complete."
        ),
        "narrative": (
            "The tour complete.\n\n"
            "Three workers on the ship, three different gifts.\n"
            "You'll know when to call which now.\n\n"
            "The cloud spirits remain: vast, intelligent, summoned by need.\n"
            "But the NPU stays close, quiet, ready,\n"
            "breathing in time with your laptop.\n\n"
            "[ FIN ]"
        ),
        "choices": [
            {"label": "Start again", "next": "awakening"},
            {"label": "Close the log", "action": "quit"},
        ],
        "verify": None,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# The Ledger — the quest's source of truth.
#
# The 11 scenes above are now the BUNDLED FALLBACK. The live source is the
# Quest_Log tab of the shared Google Sheet (read through utils/sheets.py over
# the Apps Script proxy). When the sheet is populated, edits made in a browser
# flow into the game; when it's empty or unreachable, the bundled scenes keep
# the quest fully playable. Either way main_window's get_scene() contract is
# unchanged.
# ─────────────────────────────────────────────────────────────────────────────

# Quest_Log column header → scene-dict key. Mapped by NAME (robust to column
# reordering in the sheet), not by fixed index.
_SHEET_COLUMNS = {
    "Scene_ID": "id",
    "Title": "title",
    "Narrative_Template": "narrative",
    "Choices_JSON": "choices",
    "Verify_Trigger": "verify",
    "Image_Prompt": "image_prompt",
}


def _rows_to_scenes(rows: list[list]) -> list[dict]:
    """Map a Quest_Log value matrix (header row first) into scene dicts.
    Returns [] when there's nothing usable, so the caller can fall back."""
    if not rows or len(rows) < 2:
        return []
    header = [str(h).strip() for h in rows[0]]
    scenes: list[dict] = []
    for raw in rows[1:]:
        if not raw or not str(raw[0]).strip():
            continue  # skip blank rows
        cells = dict(zip(header, raw))
        sid = str(cells.get("Scene_ID", "")).strip()
        if not sid:
            continue
        # Choices_JSON is hand-editable in a browser cell — guard the parse so a
        # malformed edit degrades to a dead-end scene instead of crashing the app.
        raw_choices = cells.get("Choices_JSON") or "[]"
        try:
            choices = json.loads(raw_choices) if isinstance(raw_choices, str) else raw_choices
            if not isinstance(choices, list):
                raise ValueError("Choices_JSON did not parse to a list")
        except Exception as e:
            logger.warning(f"[ledger] scene {sid!r}: bad Choices_JSON ({e}); using empty choices")
            choices = []
        scenes.append({
            "id": sid,
            "title": str(cells.get("Title", "") or ""),
            "narrative": str(cells.get("Narrative_Template", "") or ""),
            "choices": choices,
            "verify": (str(cells.get("Verify_Trigger") or "").strip() or None),
            "image_prompt": str(cells.get("Image_Prompt", "") or ""),
        })
    return scenes


# Last-good content snapshot for cold starts (an offline launch loads this rather
# than a blank game); bundled QUEST is the floor beneath it. See State Sync v2.md.
from utils.paths import app_root as _app_root
_SNAPSHOT = _app_root() / "quest_cache.json"


def _scenes_hash(scenes) -> str:
    """Stable, order-sensitive fingerprint of a scene set — the change-detect token
    that stands in for the file-watch the local TOML sync gets for free."""
    try:
        blob = json.dumps(scenes, sort_keys=True, ensure_ascii=False)
    except Exception:
        blob = repr(scenes)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── HY-World narrative (the 'hyworld' tab) — a short orbital-twin tour ─────────
# Bundled inline (compiled into the PYZ, so it plays frozen) for the HY_World
# narrative tab. A short 3-beat climb to the orbital GPU + a confirmation page
# whose two little games (Llama no Drama Lama / The Void and the Noid) are the
# soft proof HY-World is running. verify:'hyworld' on the last scene is the probe
# hook for Part B's gated half (render-proof + live probe wire in once the EC2 box
# is up). A live HY_World Sheet tab, if created later, overrides this.
HYWORLD_QUEST = [
    {
        "id": "hy_ascent",
        "title": "HY-World, 00 — The Long Climb",
        "narrative": (
            "Some thoughts are bigger than one small ship.\n\n"
            "The NPU does what it can, breathing softly — but tonight the captain "
            "looks up, past the blur, to a second light holding steady in orbit.\n\n"
            "HY-World. A bigger room, built for the heavy thinking. Still ours — "
            "just further up.\n\n"
            "Shall we climb?"
        ),
        "choices": [
            {"label": "Climb to HY-World", "next": "hy_arrival"},
            {"label": "Ask what waits up there", "next": "hy_arrival"},
        ],
        "verify": None,
        "image_prompt": (
            "A chibi astronaut in a soft pastel-pink spaceship bridge looking up "
            "through a round window at a second glowing station-light holding steady "
            "in orbit among stars, cozy 3D, soft bloom, gentle palette."
        ),
    },
    {
        "id": "hy_arrival",
        "title": "HY-World, 01 — The Orbital Twin",
        "narrative": (
            "The hatch opens onto a wide, humming hall.\n\n"
            "Not a faraway data centre — yours. The same little mind as the ship's "
            "llama, only with room to stretch: more memory, more cores, the heavy "
            "paint and the long thinking the NPU would labour over.\n\n"
            "\"When I can't carry it alone,\" the ship murmurs, \"I pass it up here. "
            "It comes back in your own voice — never a borrowed giant.\"\n\n"
            "The orbital twin waits, patient and bright."
        ),
        "choices": [{"label": "See what it can do", "next": "hy_warmup"}],
        "verify": None,
        "image_prompt": (
            "A chibi astronaut drifting into a wide glowing pastel orbital-station "
            "hall, soft humming machines and warm light, big friendly cores, cozy 3D."
        ),
    },
    {
        "id": "hy_warmup",
        "title": "HY-World, 02 — Warming the Cores",
        "narrative": (
            "A dial turns. Far-off fans rise from a whisper to a gentle roar, then "
            "settle.\n\n"
            "The cores warm — starlight pooling in glass. This is where the big "
            "pictures get painted and the long answers get thought, then sent home "
            "to the ship as if they'd never left.\n\n"
            "\"Almost ready,\" the twin says. \"Shall we see if it's truly awake?\""
        ),
        "choices": [{"label": "Wake the little games", "next": "hy_confirm"}],
        "verify": None,
        "image_prompt": (
            "Glowing pastel GPU cores warming up like starlight pooling in glass "
            "tubes, a small chibi astronaut watching with wonder, soft warm bloom, cozy 3D."
        ),
    },
    {
        "id": "hy_confirm",
        "title": "HY-World, 03 — Two Little Games",
        "narrative": (
            "If HY-World is awake, two little games bloom on the wall:\n\n"
            "Llama no Drama Lama — a calm llama hops from tile to tile, never "
            "flustered, answering riddles without a single bead of sweat.\n\n"
            "The Void and the Noid — tiny void-noids tumble out of the dark, and you "
            "boop them gently back to sleep.\n\n"
            "The orbital twin paints them in real time. If you can see them playing, "
            "HY-World is running — soft proof, no dials to read.\n\n"
            "Welcome to the bigger room, Captain."
        ),
        "choices": [
            {"label": "Watch them play", "next": "hy_confirm"},
            {"label": "Home, to the ship", "next": "hy_ascent"},
        ],
        "verify": "hyworld",
        "image_prompt": (
            "Two playful pastel mini-game vignettes glowing on an orbital-station "
            "wall: a calm cute llama hopping (Llama no Drama Lama) and tiny round "
            "dark blobs with sleepy eyes tumbling out of a soft void being gently "
            "booped (void-noids), cozy 3D, warm proof-of-life glow, chibi style."
        ),
    },
]


# Per-tab committed floor files (resynced from the live Sheet by
# utils/resync_floor.py). Falls back to the inline lists below when absent/frozen.
_FLOOR_FILES = {"Quest_Log": "quest_floor.json", "HY_World": "hyworld_floor.json"}


def _load_floor_json(tab: str) -> list[dict] | None:
    """The committed offline floor for `tab` (e.g. Documents/Data/quest_floor.json),
    resynced from the live Sheet. Preferred over the inline lists so a fresh clone
    with no network + no snapshot opens on current content. Resolves via app_root()
    (frozen-aware), so source runs and the frozen exe in the repo root read the
    same floor; the inline lists remain the backstop when it's absent."""
    fn = _FLOOR_FILES.get(tab)
    if not fn:
        return None
    try:
        p = _app_root() / "Documents" / "Data" / fn
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception as e:
        logger.debug(f"[ledger] {fn} unreadable ({e}); using the inline floor")
    return None


def _inline_floor(tab: str) -> list[dict]:
    """The compiled-in backstop scene set for `tab` (works frozen)."""
    return HYWORLD_QUEST if tab == "HY_World" else QUEST


class _Ledger:
    """The CONTENT authority pipe (sheet -> game). See Documents/State Sync v2.md.

    The Sheet's Quest_Log is the sole thing the author writes; the game is a strict
    reader. The live in-memory scene set is the only thing rendered, and it is NEVER
    cleared by a bad read — a failed / empty / throttled / malformed pull keeps the
    previous content fully live (last-good, principle 4). A local snapshot persists
    the last-good set so a cold start with no network still launches a real game, and
    bundled QUEST is the absolute floor under that (principle 5). reload() detects
    change via a content hash (principle 8) and arbitrates reverts via an optional
    _meta!version (principle 9): a pull whose version went BACKWARD is quarantined and
    the last-good kept.
    """

    def __init__(self):
        self._scenes: list[dict] | None = None
        self.source = "unloaded"           # 'sheet' | 'snapshot' | 'bundled'
        self._hash = ""                    # fingerprint of the live set
        self._version: int | None = None   # last accepted _meta!version
        self._tab = "Quest_Log"            # active narrative's Sheet tab (swappable)

    def set_tab(self, tab: str) -> None:
        """Point the Ledger at a different narrative tab. Clears the live set so
        the next read pulls the new tab; the OLD tab's last-good stays on disk in
        its own per-tab snapshot, so switching back is instant + offline-safe."""
        if tab != self._tab:
            self._tab = tab
            self._scenes = None
            self._hash = ""
            self._version = None

    def _snap_path(self) -> Path:
        """Per-tab snapshot file. The default tab keeps the legacy filename so
        existing caches still load; other narratives cache alongside it."""
        if self._tab == "Quest_Log":
            return _SNAPSHOT
        safe = "".join(c if c.isalnum() else "_" for c in self._tab)
        return _SNAPSHOT.with_name(f"quest_cache_{safe}.json")

    # ── fetch (worker-thread safe; never raises to the caller) ─────────────────
    def _fetch_live(self) -> list[dict] | None:
        # Deferred import: keeps quest.py free of network deps until first use,
        # and lets the bundled fallback work even if utils/sheets is absent.
        try:
            from utils.sheets import SheetsClient, SheetsError
        except Exception as e:
            logger.warning(f"[ledger] sheets client unavailable: {e}")
            return None
        try:
            rows = SheetsClient().read_sheet(self._tab)
        except SheetsError as e:
            logger.debug(f"[ledger] Quest_Log unavailable ({e}); keeping previous content")
            return None
        except Exception as e:
            logger.warning(f"[ledger] unexpected Quest_Log read error: {e}; keeping previous content")
            return None
        scenes = _rows_to_scenes(rows)
        if not scenes:
            logger.info("[ledger] Quest_Log empty; keeping previous content")
            return None
        return scenes

    def _fetch_version(self) -> int | None:
        """Optional monotonic _meta!version (the revert arbiter). None when absent —
        then change-detection rests on the content hash alone (any edit still
        propagates; only the explicit revert guard is unavailable)."""
        try:
            from utils.sheets import SheetsClient
            rows = SheetsClient().read_sheet("_meta")
            for row in rows or []:
                cells = [str(c).strip() for c in row]
                if len(cells) >= 2 and cells[0].lower() == "version":
                    return int(float(cells[1]))
        except Exception:
            pass
        return None

    # ── snapshot (cold-start last-good) ────────────────────────────────────────
    def _load_snapshot(self) -> list[dict] | None:
        snap = self._snap_path()
        try:
            if snap.exists():
                data = json.loads(snap.read_text(encoding="utf-8"))
                scenes = data.get("scenes")
                if scenes:
                    self._version = data.get("version")
                    return scenes
        except Exception as e:
            logger.warning(f"[ledger] snapshot unreadable ({e})")
        return None

    def _save_snapshot(self) -> None:
        snap = self._snap_path()
        try:
            tmp = snap.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"version": self._version, "scenes": self._scenes},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(snap)   # atomic publish of the local last-good
        except Exception as e:
            logger.debug(f"[ledger] snapshot write skipped ({e})")

    # ── cold load + reads ──────────────────────────────────────────────────────
    def scenes(self) -> list[dict]:
        if self._scenes is None:
            live = self._fetch_live()
            if live:
                self._version = self._fetch_version()
                self._scenes, self.source, self._hash = live, "sheet", _scenes_hash(live)
                self._save_snapshot()
                logger.info(f"[ledger] loaded {len(live)} scene(s) from the live {self._tab} (v{self._version})")
            else:
                snap = self._load_snapshot()
                if snap:
                    self._scenes, self.source, self._hash = snap, "snapshot", _scenes_hash(snap)
                    logger.info(f"[ledger] offline — loaded {len(snap)} scene(s) from the local snapshot")
                else:
                    fj = _load_floor_json(self._tab)
                    floor = fj if fj else list(_inline_floor(self._tab))
                    src = "floor-json" if fj else "bundled"
                    self._scenes, self.source, self._hash = floor, src, _scenes_hash(floor)
                    logger.info(f"[ledger] using {len(floor)} {src} scene(s) for {self._tab} — the floor")
        return self._scenes

    def refresh(self) -> list[dict]:
        self._scenes = None
        return self.scenes()

    def reload(self) -> dict:
        """Heartbeat fetch (worker thread). Pull the live Quest_Log and swap it into
        the live set ONLY on a clean, non-reverting pull. Returns:
          {'changed': bool, 'quarantined': bool, 'source': str, 'version': int|None}
        'changed' is True only when the content hash actually moved; 'quarantined' is
        True when the pull's version went backward (a suspected revert) — the live
        content is kept and the caller may surface a banner. Last-good is never cleared."""
        self.scenes()   # ensure a baseline exists (cold-start on the first call)
        live = self._fetch_live()
        if not live:
            return {"changed": False, "quarantined": False, "source": self.source, "version": self._version}
        new_hash = _scenes_hash(live)
        if new_hash == self._hash:
            return {"changed": False, "quarantined": False, "source": self.source, "version": self._version}
        new_version = self._fetch_version()
        if (new_version is not None and self._version is not None and new_version < self._version):
            logger.warning(f"[ledger] QUARANTINED a backward content pull "
                           f"(v{new_version} < live v{self._version}) — keeping last-good")
            return {"changed": False, "quarantined": True, "source": self.source, "version": self._version}
        self._scenes, self.source, self._hash = live, "sheet", new_hash
        if new_version is not None:
            self._version = new_version
        self._save_snapshot()
        logger.info(f"[ledger] live content updated ({len(live)} scenes, v{self._version}) — re-applying")
        return {"changed": True, "quarantined": False, "source": "sheet", "version": self._version}

    def get(self, scene_id: str) -> dict | None:
        for scene in self.scenes():
            if scene["id"] == scene_id:
                return scene
        return None


# ── Narrative registry — each narrative is one Quest_Log-shaped Sheet tab ─────
# Drop-in: add an entry here (and create the matching tab in the Sheet) and it
# shows up in the titlebar narrative selector automatically. 'npu' is the bundled
# default tour; HY-World drops in the moment its tab exists.
NARRATIVES = [
    {"key": "npu", "label": "Gentle Adventures", "tab": "Quest_Log"},
    {"key": "hyworld", "label": "HY-World", "tab": "HY_World"},
]
DEFAULT_NARRATIVE = "npu"
_ACTIVE_FILE = _app_root() / "active_narrative.txt"


def narratives() -> list[dict]:
    """The registered narratives — the titlebar selector reads this."""
    return list(NARRATIVES)


def _tab_for(key: str) -> str:
    return next((n["tab"] for n in NARRATIVES if n["key"] == key), "Quest_Log")


def active_narrative_key() -> str:
    """The persisted active narrative key (DEFAULT_NARRATIVE if unset/unknown)."""
    try:
        k = _ACTIVE_FILE.read_text(encoding="utf-8").strip()
        if any(n["key"] == k for n in NARRATIVES):
            return k
    except Exception:
        pass
    return DEFAULT_NARRATIVE


_ledger = _Ledger()
_ledger.set_tab(_tab_for(active_narrative_key()))   # honour the persisted choice at boot


def switch_narrative(key: str) -> list[dict]:
    """Point the Ledger at narrative `key`'s tab, persist the choice, and re-pull.
    Unknown key -> no-op (returns the current scenes)."""
    if not any(n["key"] == key for n in NARRATIVES):
        logger.warning(f"[ledger] unknown narrative '{key}'; ignoring")
        return _ledger.scenes()
    try:
        _ACTIVE_FILE.write_text(key, encoding="utf-8")
    except Exception as e:
        logger.debug(f"[ledger] could not persist active narrative ({e})")
    _ledger.set_tab(_tab_for(key))
    return _ledger.refresh()


def get_scene(scene_id: str) -> dict | None:
    """A scene by id, from the live Ledger (sheet or bundled fallback)."""
    return _ledger.get(scene_id)


def all_scenes() -> list[dict]:
    """Every scene, in order — the live Ledger view (sheet or bundled)."""
    return _ledger.scenes()


def first_scene_id() -> str:
    """The id of the opening scene (the quest's natural start)."""
    scenes = _ledger.scenes()
    return scenes[0]["id"] if scenes else QUEST[0]["id"]


def refresh_quest() -> list[dict]:
    """Drop the cache and re-pull the live Quest_Log. Returns the scene list."""
    return _ledger.refresh()


def reload_quest() -> dict:
    """Heartbeat re-pull of the live Quest_Log (worker-thread safe). Returns the
    reload result dict {'changed','quarantined','source','version'}; last-good is
    never cleared on failure. See State Sync v2.md."""
    return _ledger.reload()
