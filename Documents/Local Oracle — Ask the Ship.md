# Local Oracle — "Ask the Ship"

The payoff of the NPU tour: the free-text input answers, from a small llama running
on your own silicon. No call ever leaves the ship.

## What it is

Type into **"✦ ask the ship anything ✦"** and the question goes to a local model
served by FastFlowLM (`flm`) on the NPU. The answer streams back into the narrative
through the same typewriter + sparkle — so it reveals syllable-by-syllable, exactly
as scene 04 promises ("the llama answers in your terminal, syllable by syllable…").
It won't always be right; it's a 3B model. But it's always present, always private.

## How it works (`utils/oracle.py`)

Departmental isolation: the subprocess + network live in one lazy module, so a
stumble is scoped to this file and never blocks the quest. Raw `urllib`, no SDK —
the family's no-SDK / raw-HTTP sovereignty, here pointed at localhost.

1. **Resolve flm** — `probe.resolve_flm()` (PATH, then known install locations, so a
   stale PATH can't hide it).
2. **Wake the server, lazily** — on the first question, `flm serve llama3.2:3b
   --quiet` is started (the model loads onto the NPU, ~6–9s — the "oracle stirs
   awake" beat) and reused for the session. If something is already serving on the
   port, we reuse it and never spawn a second.
3. **Ask** — a POST to `http://127.0.0.1:<port>/v1/chat/completions` (OpenAI-compatible;
   port from `flm port`), with a warm system prompt (the oracle's voice). Off the UI
   thread via `OracleWorker`; the answer streams into `NarrativePanel`.
4. **Fallback** — if flm isn't installed, a gentle nudge back to the summoning rather
   than an error. The ambient weather (`_read_vibe`) still nudges on a question too.

## Transcripts (saved by default)

Every exchange is kept for later fun, mirroring The Majestic's multi-destination
chat persistence:
- **`Documents/Data/Oracle/oracle_<session>.md`** — readable transcript, header +
  timestamped Q&A appended on each ask (the primary, in-repo copy).
- A **second copy** in `~/Documents/GentleAdventures/Oracle/` (and the
  `SingleSharedBraincell_ChatHistory` dir if set) — "several backups, just in case."
- **`Documents/Data/Oracle/flm_serve_<ts>.log`** — flm's own serve output (instead
  of `/dev/null`), the "Start-Transcript when calling flm" capture.

All best-effort and non-blocking — a transcript hiccup never touches the conversation.

## Lifecycle

The server is reused across the session; `Oracle.shutdown()` (called from
`closeEvent`) stops it **only if we started it** — never one the captain ran by hand.

## Wiring

`main_window._on_choice` (quest phase, free text that isn't a `validate`/weather
command) → `_ask_oracle()` → `OracleWorker` → `_on_oracle_answer` streams it in.
`_read_vibe` fires alongside for the ambient mood.

## Deferred / future

- A consuming **daemon on `_signals`** (the intercom) so the world can answer the
  player back through the content authority — the dynamic-story path.
- Streaming tokens (currently one-shot + the typewriter gives the syllable feel).
- Model choice / power-mode (`--pmode`) surfaced to the player.
