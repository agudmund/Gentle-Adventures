# Sheets Ledger — State Machine

How Gentle Adventures uses its shared Google Sheet, and the tools that keep it honest.

## The model: the Sheet is the live source of truth

The `Quest_Log` tab of the shared Google Sheet is the **live, dynamically-editable
source of truth** — the state machine. At startup the `_Ledger` (in `data/quest.py`)
reads `Quest_Log` through the Apps Script proxy (`utils/sheets.py`, raw urllib) and
serves scenes from it; the bundled `QUEST` list in `quest.py` is the **fallback
baseline** used only when the sheet is empty or unreachable.

This is deliberate — it's a base-test of "can a Google Sheet be a real state
manager?" — and it's the foundation of a bigger ambition: **a story that never has
to end.** Because the state is editable from outside the app, an external client (a
daemon, an AI on a server) can keep extending or reshaping the quest *while it's
being played* — append new scenes as the player nears the current ending, branch the
narrative, swap the whole premise. The same engine that tours an NPU today could,
unchanged, run a butterfly's descent through the levels of Hades tomorrow, rewritten
live with complete disregard for the notion of an ending — a proper telenovela. The
state has to be **dynamically editable to be futureproof**, so the Sheet stays canon.

### Today vs. the next tick

- **Today:** the Ledger reads `Quest_Log` **once per process** and caches it (fast,
  no per-scene network stall). A sheet edit applies on the next launch / `refresh_quest()`.
- **Next (the dynamic-state feature):** re-read `Quest_Log` **per scene entry**, off
  the UI thread (the shared worker registry), so an external edit lands mid-session —
  the live state machine the experiment is for. `_Ledger`'s own docstring already
  flags this as the planned step.

> Direction of authority: **Sheet → game.** `quest.py` is the static "factory default"
> baseline (the offline safety net), NOT the canon. Don't frame `quest.py` as the
> source of truth — that's backwards for this experiment.

## The sanitizer — `utils/sanitize_sheets.py`

A small operator tool over the **existing proxy** (no new SDK/OAuth — raw-HTTP
sovereignty intact; a cli-printing-press Sheets CLI was scoped and rejected as
OAuth/SDK overkill). Two modes:

- **`report` (default, read-only):** greps every cell of the ledger tabs against
  `STALE_PATTERNS` (a top-of-file control surface) and prints where retired wording
  lingers. Surfaces the signal; never auto-heals (drift-accountability posture).
- **`--push` (guarded, dry-run by default; `--apply` writes):** re-seeds `Quest_Log`
  from the bundled `QUEST` baseline. A **recovery / re-seed** tool — for when the live
  sheet drifts stale or you want to reset to factory default — **not** the standing
  sync direction (the sheet is canon, remember). Gives `replace_rows()` its caller.

### The habit

- Rename or retire any wording (a choice label, a phrase)? Add it to `STALE_PATTERNS`
  and run `report` to catch every straggler still sitting in the live sheet.
- `--push --apply` only to **re-seed** a corrupted/stale sheet from the bundled
  baseline (as was done once to clear the retired `"cast the rite"` row that was
  overriding corrected canon in-game).
- It's a deliberate, reviewable command — never a background auto-sync that would hide
  the drift. (Same memory-habit shape as the push→Asana audit.)

## Why the stale row bit us (the cautionary tale)

A corrected choice label lived in `quest.py`, but the **stale `Quest_Log` row
overrode it at runtime** (sheet wins when present), so the game kept showing the old
label across relaunches — looking exactly like a stale-process / cache bug. A headless
`get_scene()` check showed the *right* label only because that shell had no proxy
creds and fell back to bundled. Lesson: when content looks stale in-game, **suspect
the live Sheet first** — it's canon.
