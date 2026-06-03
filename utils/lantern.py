#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - lantern.py the Lantern, a companion that lights a tangle when a tool stumbles
-No wall of red; when something snags, a friend beside you holds up a light, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import collections
import re
import subprocess

from PySide6.QtCore import QThread, Signal

from utils.logger import get_logger
from utils.proc import CREATE_NO_WINDOW

_log = get_logger("gentle")

# The Lantern watches a real tool's output (e.g. FastFlowLM's `flm`), and when
# it stumbles, translates the raw trace into a warm "let me light this" line
# instead of a frightening wall of red. This module is the PURE core — no Qt, no
# network — so it's trivially testable; main_window wraps watch_command() in a
# low-priority QThread (LanternWatch) and, later, layers a Gemini rewrite on top.


# ─── Classifier ───────────────────────────────────────────────────────────────
# Cheap, deterministic, offline. Each pattern recognises a common stumble so the
# Lantern can say something specific and kind before (or instead of) any LLM call.

# Real tools (flm included) wrap output in ANSI colour escapes — strip them so
# the gentle NarrativePanel shows clean text and the classifier matches cleanly.
# (Learned by contact: `flm validate` emits \x1b[32m...\x1b[0m green lines.)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("port", re.compile(
        r"(?i)address already in use|EADDRINUSE|port\s+\d+\b.*\b(in use|busy|taken)"
        r"|bind(?:ing)?\s+failed|only one usage of each socket")),
    ("env", re.compile(
        r"(?i)environment variable|env var|api[_ ]?key.*(not set|missing|invalid)"
        r"|\bunauthorized\b|\b40[13]\b|token.*(not set|missing)")),
    ("missing", re.compile(
        r"(?i)not recognized as|command not found|no module named|modulenotfounderror"
        r"|cannot find|is not installed|no such file|could not find|not found")),
]


def classify(text: str) -> dict | None:
    """Tag a stumble by its signature, or None if nothing recognised."""
    hay = text or ""
    for kind, rx in _PATTERNS:
        if rx.search(hay):
            return {"kind": kind}
    return None


# ─── Gentle copy (the Lantern's voice) ─────────────────────────────────────────
# Warm, specific, never alarming. The 🔦 is the lantern's glow — "I've got a light
# on this." Offline fallback; a richer in-character line can be layered via Gemini.

_GENTLE = {
    "port": "Oh — something's already curled up on that spot. Let's gently see who's "
            "there and make a little room. 🔦",
    "env": "A small setting hasn't been whispered in yet. Let's set it, then try the "
           "door again. 🔦",
    "missing": "The thing we reached for isn't on the shelf yet. Let's fetch it first, "
               "then carry on. 🔦",
    "unknown": "A small tangle in the line — nothing's broken. Let me hold a light to "
               "it and we'll smooth it out together. 🔦",
}


def gentle_message(classification: dict | None) -> str:
    """The Lantern's line for a classification. '' means all was well (no stumble)."""
    if not classification:
        return ""
    return _GENTLE.get(classification.get("kind", "unknown"), _GENTLE["unknown"])


# ─── Watch a command ────────────────────────────────────────────────────────────

def watch_command(cmd, on_line=None) -> tuple[int, str, dict | None]:
    """Run *cmd*, streaming stdout+stderr line-by-line (calling on_line(line) per
    line if given), and return (exit_code, tail_text, classification).

    Encoding is utf-8 with errors='replace' so a tool's ✦/emoji output can't crash
    the stream (the cp1252 lesson from the console). classification is set when a
    known stumble signature appears, or {'kind':'unknown'} on any nonzero exit
    with no recognised pattern — so a failure always earns a gentle line; a clean
    run returns None (no message)."""
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return -1, f"{cmd[0]} not found on PATH", {"kind": "missing"}
    except Exception as e:  # pragma: no cover — defensive
        return -1, f"{type(e).__name__}: {e}", {"kind": "unknown"}

    tail: collections.deque[str] = collections.deque(maxlen=60)
    if proc.stdout is not None:
        for line in proc.stdout:
            line = _ANSI.sub("", line.rstrip("\n"))   # strip colour escapes
            tail.append(line)
            if on_line is not None:
                on_line(line)
    proc.wait()

    raw = "\n".join(tail)
    classification = classify(raw)
    if proc.returncode != 0 and classification is None:
        classification = {"kind": "unknown"}
    return proc.returncode, raw, classification


# ─── The Lantern's hands — off-UI-thread runner (its own citizen) ───────────────

class LanternWatch(QThread):
    """Run a command off the UI thread, stream its lines, and on settle hand back
    (exit_code, gentle_message, classification). The raw trace goes to the LOG
    only — never the gentle UI. A self-contained citizen: the window hands it a
    command and listens; it owns the watching, classifying, and lighting."""

    line = Signal(str)
    settled = Signal(int, str, object, str)   # (exit_code, gentle_message, classification, raw_tail)

    def __init__(self, cmd, label: str = ""):
        super().__init__()
        self.cmd = list(cmd)
        self.label = label

    def run(self):
        self.setPriority(QThread.LowestPriority)   # a quiet background tidy
        code, raw, classification = watch_command(self.cmd, on_line=self.line.emit)
        if code != 0:
            _log.warning(f"[lantern] {' '.join(self.cmd)} exited {code}:\n{raw}")
        self.settled.emit(code, gentle_message(classification), classification, raw)

