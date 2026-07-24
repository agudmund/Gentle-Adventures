# Sheets Ledger — State Machine

How Gentle Adventures uses its shared Google Sheet, and the tools that keep it honest.

## The model: the Sheet is the live source of truth

The `Quest_Log` tab of the shared Google Sheet is the **live, dynamically-editable
source of truth** — the state machine. At startup the `_Ledger` (in `quest.py`)
reads `Quest_Log` through the Apps Script proxy (`shared_braincell.sheets`, the
family courier, raw urllib) and
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

## Narratives: one Quest_Log-shaped tab per adventure

The Ledger is not married to a single story. `NARRATIVES` in `quest.py` is a
drop-in registry mapping a narrative key to a Sheet tab, and the titlebar carries a
selector fed by it. Add a tab to the Sheet plus one registry line, and a new
adventure appears in the selector with the full Ledger machinery behind it (live
canon, offline floor, sanitizer coverage). The active choice persists in
`active_narrative.txt`; `switch_narrative()` repoints the Ledger and re-pulls.

Registered today:

- **`npu` → `Quest_Log`** (default): the bundled NPU tour. Everything in this
  document was written against this tab; it remains the reference narrative.
- **`hyworld` → `HY_World`**: the secondary adventure, **HY-World, the orbital
  twin**. Where the NPU tour is about the small grid of minds inside the ship,
  HY-World is the bigger room: the captain's own GPU machine on AWS (an EC2 box)
  for the heavy paint and the long thinking, with answers sent home as if they'd
  never left. A three-beat ascent (`hy_ascent` → `hy_arrival` → `hy_warmup`) ends
  in `hy_confirm`, where two little real-time mini-games (Llama no Drama Lama, and
  The Void and the Noid) bloom on the station wall as the soft, dial-free proof
  the twin is awake.

The `HY_World` tab is live in the Sheet (created 2026-06-12) and is canon for
the adventure, same as `Quest_Log`; the inline `HYWORLD_QUEST` and the committed
floor remain the offline safety net.

### The hyworld verify — live (2026-06-12)

`hy_confirm` carries `verify: "hyworld"`, now wired end-to-end: the probe
(`utils/hyworld.py`) shells the `aws` CLI — the family's silent-subprocess
pattern, no SDK in-app — and the scene verifies only when the EC2 twin reports
`running`. Asleep, the scene plays its absent face from the new optional Sheet
columns `Narrative_Absent` / `Choices_Absent_JSON` (general to any verify kind):
a dark patient wall offering **Wake the orbital twin**, which starts the
instance on a worker, narrates on the bottom strip, and re-enters the scene when
the twin settles to `running`. On app exit (the closeEvent ritual behind tray
Restart / Exit / Live), `tuck_in_hyworld` sends a detached `stop-instances` so
the cores never stay warm for an empty room. `[hyworld]` in GA's settings.toml
names the instance, profile, and region. The render-proof — the two little
games painted live by the twin — remains the next chapter, once something on
the box is listening.

### Per-tab offline floors

Each tab keeps its own committed floor file, resynced from the live Sheet by
`utils/resync_floor.py`: `_FLOOR_FILES` maps `Quest_Log` → `Documents/Data/quest_floor.json`
and `HY_World` → `Documents/Data/hyworld_floor.json`. A floor file is preferred over the
compiled-in lists (`QUEST`, `HYWORLD_QUEST`) so a fresh clone with no network
still opens on current content; the inline lists remain the frozen-build backstop.

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
