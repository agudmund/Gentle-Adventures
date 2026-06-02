#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - quest.py the NPU adventure beats, scene by scene
-Every beat was written before you knew you needed it, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json

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
# ─────────────────────────────────────────────────────────────────────────────

QUEST: list[dict] = [
    {
        "id": "awakening",
        "title": "GENTLE ADVENTURES, 01 — AWAKENING",
        "image_prompt": _prompt(
            "The captain wakes at the helm of a small starship console. Three glowing "
            "lights on the console — one familiar pale-blue (labeled CPU), one familiar "
            "violet (labeled GPU), and a third light, never seen before, pulsing in soft "
            "warm gold and labeled XDNA 2. The captain leans in, curious, eyes wide."
        ),
        "narrative": (
            "The captain stirs. The ship hums a new tune.\n\n"
            "Three lights blink on the main console — one familiar, one known, one… new.\n"
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
            "\"XDNA is a grid of small minds,\" it says. \"Not one big brain — many\n"
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
            "'Performance' — three vertical meters labeled CPU, GPU, NPU. The first "
            "two flicker with normal activity; the NPU meter sits perfectly at zero, "
            "waiting. The captain points at it with a tiny gloved hand, fascinated."
        ),
        "narrative": (
            "The diagnostic spirits respond to your call.\n"
            "A panel materializes — three meters, three names.\n\n"
            "CPU dances with everyday work. GPU naps quietly.\n"
            "The third meter — NPU — sits at zero, waiting to be invited.\n\n"
            "\"It only works for guests who bring AI errands,\" the computer murmurs.\n\n"
            "▸ On your machine: press Ctrl+Shift+Esc and look at the Performance tab.\n"
            "  See if you can find the NPU entry yourself."
        ),
        "choices": [
            {"label": "I see it", "next": "blur"},
            {"label": "Ask how to wake it", "next": "wake_lore"},
        ],
        "verify": "npu",
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
            "  • Local AI oracles — small models that fit in its memory.\n"
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
            "bridge has softened into a pastel galaxy of bokeh and stars — magical "
            "background blur. The NPU meter visible in a corner glows softly active. "
            "The captain smiles, charmed by their own blurred backdrop."
        ),
        "narrative": (
            "Your first errand is gentle.\n\n"
            "Settings → Bluetooth & devices → Cameras → your webcam.\n"
            "Under Windows Studio Effects, switch on Background blur.\n"
            "Then open any camera preview — the Camera app will do.\n\n"
            "Watch the meters. CPU stays cool. Fans stay quiet. The NPU — finally —\n"
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
            "A local oracle — a small mind that runs right on your ship's NPU —\n"
            "would answer you without ever calling the cloud spirits. Smaller of\n"
            "voice, but always present, always private, always close.\n\n"
            "Fetch the summoner first: FastFlowLM, a tiny runtime that speaks to\n"
            "the NPU directly (fastflowlm.com, installed in under a minute). Then\n"
            "call your first oracle down with a single line:\n"
            "    > flm run llama3.2:3b"
        ),
        "choices": [
            {"label": "Validate the ship first", "action": "validate_ship"},
            {"label": "I have cast the rite", "next": "arrival"},
            {"label": "Ask what models do", "next": "model_lore"},
        ],
        "verify": "fastflowlm",
    },
    {
        "id": "model_lore",
        "title": "GENTLE ADVENTURES, 04.5 — WHAT IS A LOCAL MODEL",
        "image_prompt": _prompt(
            "A row of small pastel creatures — a llama, an owl, a fox, each carrying "
            "a tiny scroll labeled with parameter counts (3B, 7B, 8B). The captain "
            "studies them like a kindly zookeeper."
        ),
        "narrative": (
            "\"A model is a frozen mind,\" the AI says. \"Trained on books and code\n"
            "and conversations, then captured into a file you can carry.\"\n\n"
            "\"The big ones — like the cloud spirits — would never fit on your ship.\n"
            "The small ones do. They are gentler, less knowing, but always with you.\"\n\n"
            "\"For your first oracle, try Llama 3.2 — three billion parameters,\n"
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
            "From it emerges a llama — soft, three billion parameters, friendly.\n"
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
            "You ask it: \"What is the meaning of low-power inference?\"\n\n"
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
            "Leave FastFlowLM running as a local server — an OpenAI-compatible\n"
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
            "llama by their side. All three console lights — CPU, GPU, NPU — glow "
            "harmoniously in soft pinks, blues, and gold. Stars drift past the viewport. "
            "The mood is peaceful, complete."
        ),
        "narrative": (
            "The tour complete.\n\n"
            "Three workers on the ship, three different gifts.\n"
            "You'll know when to call which now.\n\n"
            "The cloud spirits remain — vast, intelligent, summoned by need.\n"
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


class _Ledger:
    """Live Quest_Log with the bundled QUEST as a graceful fallback.

    v1 fetches the sheet ONCE and caches it for the process (fast, no per-node
    UI freeze). refresh() re-pulls. Live per-node hot-reload — re-reading on
    every scene entry so a browser edit applies instantly — is the next tick:
    it needs an off-UI-thread worker (the shared worker registry) so the read
    never stalls the window. Until then, refresh() or a relaunch re-pulls.
    """

    def __init__(self):
        self._scenes: list[dict] | None = None
        self.source = "unloaded"   # 'sheet' | 'bundled' once loaded

    def _fetch_live(self) -> list[dict] | None:
        # Deferred import: keeps quest.py free of network deps until first use,
        # and lets the bundled fallback work even if utils/sheets is absent.
        try:
            from utils.sheets import SheetsClient, SheetsError
        except Exception as e:
            logger.warning(f"[ledger] sheets client unavailable: {e}")
            return None
        try:
            rows = SheetsClient().read_sheet("Quest_Log")
        except SheetsError as e:
            logger.info(f"[ledger] live Quest_Log unavailable ({e}); using bundled scenes")
            return None
        except Exception as e:
            logger.warning(f"[ledger] unexpected Quest_Log read error: {e}; using bundled scenes")
            return None
        scenes = _rows_to_scenes(rows)
        if not scenes:
            logger.info("[ledger] Quest_Log empty; using bundled scenes")
            return None
        logger.info(f"[ledger] loaded {len(scenes)} scene(s) from the live Quest_Log")
        return scenes

    def scenes(self) -> list[dict]:
        if self._scenes is None:
            live = self._fetch_live()
            if live:
                self._scenes, self.source = live, "sheet"
            else:
                self._scenes, self.source = list(QUEST), "bundled"
        return self._scenes

    def refresh(self) -> list[dict]:
        self._scenes = None
        return self.scenes()

    def get(self, scene_id: str) -> dict | None:
        for scene in self.scenes():
            if scene["id"] == scene_id:
                return scene
        return None


_ledger = _Ledger()


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
