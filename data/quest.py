#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - quest.py the NPU adventure beats, scene by scene
-Every beat was written before you knew you needed it, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

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
#   verify      : optional — "npu" | "lm_studio" | None — system probe to confirm
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
        "title": "GENTLE ADVENTURES, 03 — THE SPECTRAL OVERLAY",
        "image_prompt": _prompt(
            "The captain stands inside a glowing video-call window. Behind them, the "
            "bridge has softened into a pastel galaxy of bokeh and stars — magical "
            "background blur. The NPU meter visible in a corner glows softly active. "
            "The captain smiles, charmed by their own blurred backdrop."
        ),
        "narrative": (
            "Your first errand is gentle.\n\n"
            "Settings → Bluetooth & devices → Cameras → your webcam → effects.\n"
            "Toggle the spectral overlay on. Then open any camera preview.\n\n"
            "Watch the meters. CPU stays cool. Fans stay quiet. The NPU — finally —\n"
            "stirs. This is what gentle work looks like."
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
            "'LM STUDIO', glowing teal and gold. In their hand is a tiny scroll "
            "labeled 'setupLMStudio.ps1'. Around the doorway, small icons of llamas, "
            "owls, and tiny robots peek out shyly."
        ),
        "narrative": (
            "The second errand needs invocation.\n\n"
            "A local oracle, summoned and seated, would answer your questions without\n"
            "calling the cloud spirits. Its voice would be smaller — but always present,\n"
            "always private, always close.\n\n"
            "The scroll in your satchel already speaks the rite:\n"
            "    > .\\setupLMStudio.ps1"
        ),
        "choices": [
            {"label": "I have cast the rite", "next": "arrival"},
            {"label": "Ask what models do", "next": "model_lore"},
        ],
        "verify": "lm_studio",
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
            "\"For your first oracle, try Llama 3.2 3B (ONNX). It fits on the NPU.\""
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
            "Llama 3.2 3B (ONNX) walks to your side and bows its small head.\n\n"
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
            "soft gold. Above it floats the inscription 'localhost:1234/v1'. Beyond "
            "the door, faint friendly silhouettes of other tools and ships approach, "
            "knocking politely."
        ),
        "narrative": (
            "The final discovery: your llama can serve other ships too.\n\n"
            "LM Studio → Developer → Start Server.\n"
            "A door opens at localhost:1234, OpenAI-compatible —\n"
            "any tool that speaks the old protocol can knock and be answered.\n\n"
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


_BY_ID = {scene["id"]: scene for scene in QUEST}


def get_scene(scene_id: str) -> dict | None:
    return _BY_ID.get(scene_id)
