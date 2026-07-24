# State Sync v2 — the grandMA on a Google Sheet

How Gentle Adventures keeps its world (content) and its playthrough (progress) in
sync with the shared Google Sheet, designed in the family's arena-concert frame and
borrowing the proven soul of the Settlers↔Intricate `settings.toml` live-sync.

## The metaphor (the whole design in one image)

Front-of-house at an arena show: one operator, hands on a grandMA lighting desk,
fires precise DMX out to hundreds of fixtures all night. It is **one-directional in
the sense that matters — only the operator writes the lights.** Yet information pours
*into* that operator constantly: the intercom, watching the stage, the artist's
in-ear panic. None of that is a write; it's all advisory. The performer can signal
"I'm in trouble," but never reaches over and grabs a fader. Every change to the rig
funnels through one set of hands.

So the system is **single-writer on authority, many-to-one on information.** The
back-channel doesn't break the one-way rule — it *feeds* it. The operator is a
**decision funnel**, not a passive transmitter. That is the entire architecture.

## The two authority pipes (DMX)

A given datum moves in exactly one direction and has exactly one writer. The reader
never writes back the thing it reads.

| | CONTENT — the world/script | PROGRESS — the playthrough |
|---|---|---|
| Sheet tab | `Quest_Log` | `Player_State` |
| Flow | sheet → game (**down**) | game → sheet (**up**) |
| Sole writer | the author (browser) / future daemon | the game |
| Game's role | **strict reader — never writes content cells** | sole writer; separate tab |
| Floor on failure | bundled `QUEST` in `quest.py` | local `player_state.json` |

Zero overlap: the two concerns never contend for the same bytes. **This is the
structural fix** — GA's "I have cast the rite came back" bug was the game and an
external editor both touching content with no single hand and no version to
arbitrate. Under v2 it cannot recur by construction.

## The intercom (the out-of-band back-channel)

A *separate, low-bandwidth* region — its own tab, `_signals` — where the game (the
performer) can post something **critical** upstream to the content authority (the
operator) **without writing content** (without grabbing the grandMA). The author /
daemon watches `_signals` and *decides* whether to re-author content (and bump the
version). The game informs; the operator authors.

A player choice that should reshape the world does not write the world — it speaks
into the intercom; the daemon decides and re-fires. This is the principled home for
every "exception to one-way": never a reversal of a pipe, always a second wire. We
**reserve the socket now** (`SheetsProxyClient.write_signal`) even before anything
consumes it, so the dynamic-story future plugs in without re-architecting.

## The machinery (seven borrowed principles + two remote compensations)

From the Settlers↔Intricate TOML sync (months hiccup-free), applied here:

1. **Single sovereign writer** — per region, above.
2. **One-way per concern** — per region, above.
3. **Atomic publish, in spirit** — progress flushes as ONE idempotent batch write
   (absolute state, not deltas → safe to retry); content is swapped into the live
   store only after a *full successful* fetch+parse, never row-by-row into the live
   set.
4. **Last-good cache is never cleared on a bad read** — `_Ledger.reload()` builds
   the new scene set in a *local* variable and swaps the live store only on success.
   A failed / empty / throttled / malformed pull leaves the previous content fully
   live and logs "keeping previous content." Mirrors Theme's `_store` surviving a
   bad parse.
5. **Sentinel floor so missing/malformed never crashes** — bundled `QUEST` is the
   absolute floor (empty cache *and* no network still renders a real game). Missing
   scene fields fall to per-field placeholders, never `None`-into-render. The
   "always draw a circle" guarantee, at the content level.
6. **Per-row fault isolation** — each `Quest_Log` row parses in its own try/except;
   one malformed row is dropped (and logged), every valid row loads.
7. **Pull-on-access + coalesced apply** — the game reads scenes from the in-memory
   store at use-time; a content change re-streams the *current* scene once (the
   typewriter already coalesces).

Two things the filesystem gave free that a remote, externally-mutable store does not:

8. **Change detection without a push** — Sheets has no file-watch, so the heartbeat
   polls. At GA's scale it fetches `Quest_Log` and compares a **content hash** to the
   last-applied; unchanged → do nothing (the "file-watch stays quiet" analog). *Scale
   path (deferred): poll a cheap `_meta!version` token and fetch the body only when it
   advances — the Drive `revisionId` / a monotonic version cell.*
9. **Explicit version arbitration** — the net-new primitive with no local analog. A
   `_meta!version` monotonic integer; the game records the version it loaded and
   **quarantines any pull whose version is lower than live** (a silent backward step
   is suspect) — surfaced (log + in-game banner), last-good retained. *This is the
   arbiter that was missing.* When `_meta` is absent the game runs on hash-detection
   alone (any edit propagates; no revert guard) — graceful either way.

## The sheet contract

- `Quest_Log` — content. Columns per `_SHEET_COLUMNS`. Written only by the author /
  daemon / the operator tool (`sanitize_sheets.py --push`). The game never writes it.
- `Player_State` — progress. Written only by the game (`SheetsProxyClient.write_state("Player_State", …)`).
- `_meta` *(optional)* — a `version` cell (monotonic int). `--push` bumps it; the
  Apps Script `onEdit` trigger (snippet in *Sheets Ledger Setup.md*, "The revert
  guard") auto-bumps it on human browser edits once pasted into the Sheet's
  script project — the paste is the arming step.
- `_signals` *(reserved)* — the intercom. Game appends; daemon reads. Socket built,
  no consumer yet.

## Failure modes & how each is absorbed

- **No creds / LEDGER OFF** → bundled floor; the dot goes big-red (loud, can't be missed).
- **Network fails / 429 / timeout** → keep last-good in memory; cold start loads the
  local snapshot; retry next heartbeat. Never blank, never crash.
- **Malformed cell / bad row** → that row dropped + logged; the rest load.
- **Missing field** → per-field sentinel placeholder.
- **Sheet reverted to an older version** → quarantined + bannered; last-good kept.
- **Rapid edits** → coalesced; the current scene re-streams once.
- **Foreign-path / cross-machine** → progress is local-first; content floor is bundled.

## Built now vs deferred

- **Now:** two-pipe discipline; `_Ledger` v2 (last-good-never-cleared, local snapshot
  cold-start, per-row isolation, bundled floor, content-hash change detection, version
  arbitration when `_meta` present); intercom socket; heartbeat consumes the new
  contract; `--push` bumps `_meta!version` best-effort.
- **Deferred:** Drive `revisionId` cheap-token polling for scale; the daemon that
  consumes `_signals`. (The `onEdit` auto-bump graduated 2026-07-23: snippet +
  arming instructions shipped in *Sheets Ledger Setup.md*; what remains deferred
  is only the in-browser paste, which no repo commit can perform.)
