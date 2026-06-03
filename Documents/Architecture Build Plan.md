# Gentle Adventures — Architecture Build Plan

> Generated 2026-06-02 from a read-only scoping pass (7 architect agents over the live
> codebase + 1 synthesis pass). Grounded against the real repo at
> `C:\Users\thebe\Desktop\Gentle-Adventures`. This is the build map for the
> Architecture Bible's 7 systems — sequencing, shared infrastructure, decisions
> the captain must make, and the quick wins.
>
> Companion to the Asana project (7 parent tasks + 28 subtasks). This doc is the
> *how and in what order*; Asana is the *checklist*.

---

## Status — 2026-06-03 (what shipped, and how the plan evolved)

Most of this plan is now built — and several pieces landed *differently* (better) than
the original map imagined. This section is the current reality; everything below it is
preserved as the original build record.

**Shipped ✅**
- **Worker registry** — `WorkerRegistry` in `main_window.py`, now with a `quiet=True`
  mode for background pulses. The single-slot collision bug (finding #3) is gone.
- **Section I — Sheets state machine (the SPINE)** — built, then **rebuilt as State Sync
  v2** (see `State Sync v2.md`). It diverged from the plan in two good ways: **(a)** the
  transport is an **Apps Script web-app proxy** (`utils/sheets.py`, raw urllib over one
  deployed URL + a shared token) — NOT a raw Sheets-v4 client — which *sidesteps* the
  OAuth/service-account auth blocker entirely (Captain Blocker #1 resolved by avoiding
  it). **(b)** `data/quest.py`'s `_Ledger` is content-down with last-good-never-cleared,
  content-hash change-detection, a local snapshot floor, and version arbitration;
  `PlayerStateStore` is the local-first progress-up pipe. Plus the **realtime heartbeat
  loop** (idle/curtains-paused) and `utils/sanitize_sheets.py` (ledger lint + canon re-mint).
- **Hardware Oracle** — `probe_npu` / `raw_hardware_spec` + the `_summon_oracle`
  calibration line on the bottom strip (display-only, per Blocker #6).
- **Text path** — built broader than planned: a **swappable text backend** (Claude
  default, Gemini on demand) through the registry, not Gemini-only.
- **System 2 — Psychological Weather** — `weather.py` (rain engine + vibe vector) +
  `_read_vibe`; in-process palette morph only (never writes the shared TOML, per Blocker #4).
- **System 3 — Ghost in the Machine** — `utils/lantern.py` (The Lantern): offline
  classifier + gentle copy, off-UI `LanternWatch`, optional text-backend rewrite.
- **System 4 — Sticker loot** — `_maybe_award_sticker` off the verify-probe, dedup'd.
- **The local-model bridge** — shipped as **`utils/oracle.py`** (the "ask the ship"
  oracle): `flm serve llama3.2:3b` + a localhost OpenAI-compatible POST, transcripts
  saved by default. This *is* the `local_model.py` the plan scoped for System 5 — built
  early as the tour's payoff. See `Local Oracle — Ask the Ship.md`.
- **Narrative & shell** — streaming typewriter + travelling-white sparkle, play-sticker
  paragraph dividers, instant scene-swap cut; headless launcher (`Gentle Adventures.vbs`),
  loud-red OFF ledger dot, flm-by-resolved-full-path.

**Remaining ⏳**
- **System 5 — Beyond the Rim side quests** — the local-model bridge exists (oracle.py),
  but the sandbox beat + mission validation + the side-quest loop are not built. The
  `_signals` **intercom** socket is reserved for the daemon path (see State Sync v2.md).
- **Section III — The Flex (fluid backdrop)** — not started (own phase).
- **State Sync v2 follow-ups** — a `_meta` version tab (activates the revert guard) +
  an Apps Script `onEdit` trigger to auto-bump it; the Drive-`revisionId` scale path.
- **Polish** — the per-letter sparkle option (noted); the `_signals` daemon consumer.

**Captain Blockers — status:** #1 (Sheets auth) **sidestepped** by the Apps Script
proxy (shared-token, no OAuth). #4 (palette scope) — in-process morph only. #6 (Oracle
scope) — display-only calibration shipped; the separate "ask the ship" oracle answers
via the local model. The remaining blockers attach to the unbuilt System 5 / Section III.

---

## TL;DR — the three findings that reshape everything

1. **Five systems all need the same thing: a Gemini *text* path.** `utils/gemini.py`
   is image-only today (`_generate_content` hardcodes `responseModalities:["IMAGE","TEXT"]`
   and only digs out the image part). The Oracle, System 2 (vibe), System 3 (ghost
   rewrite), and System 5 (missions) each independently specified a text-generation
   call. **Build it once.**

2. **Three systems all rewrite `data/quest.py`.** Section I (Ledger refactor),
   System 2 (render-time mood preamble), and System 5 (sandbox beat) all touch the
   same file. These **cannot be parallelized** — they must be sequenced so the shapes
   compose instead of three-way conflicting. Do the Ledger first, then layer mood,
   then the sandbox beat.

3. **The single `self.current_worker` slot is a latent bug.** `main_window.py` reuses
   one worker handle (line ~130, quit/wait at ~582-589). The moment two workers run at
   once (a sticker generating *while* a scene renders), one `quit()/wait()`s the other
   and cancels in-flight work. Systems 4 and 5 both flagged this as their #1 likely bug.
   **A small worker registry, built early, kills it before it bites.**

---

## Recommended build order

A **shared-infrastructure pass** comes first (it unblocks almost everything), then
systems in ascending risk/dependency order. **Section III (the Flex / fluid backdrop)
is deliberately off the critical path** — it's large, purely aesthetic, fully
independent, and best shipped in its own phase.

| # | System | Effort | Why here |
|---|--------|--------|----------|
| 0 | **Shared infrastructure pass** | — | Gemini text path + worker registry + text-model resolution. Removes duplicated work from 5 systems and kills the worker-collision bug. |
| 1 | **Section I — Google Sheets state machine (the SPINE)** | large | Systems 4 & 5 write back to its `Player_State` write-path; must exist first. Auth-model decision gates the write-path. |
| 2 | **Hardware Oracle (Sentient Settings)** | medium | Lowest-risk consumer of the new text path; cosmetic (never blocks the quest); has a ready-made seam. Best early momentum win. |
| 3 | **System 3 — Ghost in the Machine** | medium | Self-contained, reuses text path + registry, independent of the spine — can run in parallel with Section I. |
| 4 | **System 2 — Psychological Weather & dynamic palette** | large | Riskiest aesthetic blast-radius + forces the `quest.py` render-time refactor. Sequence after the Ledger. |
| 5 | **System 4 — Procedural sticker loot drops** | medium | Reuses GeminiImageClient + SceneCache wholesale. Needs the worker registry. Can trigger off the existing verify-probe immediately. |
| 6 | **System 5 — Beyond the Rim side quests** | large | Long pole: needs text path + Sheets write + a net-new local-model bridge. Unlocks only at the `resonance` beat. Gate it last. |
| — | **Section III — High-end visual contrast (The Flex)** | large | Own phase. Ship the pre-baked video-loop variant first; QOpenGLWidget shader as optional Phase 2, gated behind a `[backdrop]` flag. |

### Critical path
`Gemini text path + worker registry` → `Section I Sheets client (write_player_state spine, gated on the auth-model decision)` → `System 5 (needs text + Sheets-write + new local-model bridge, unlocks after the core quest is stable)`.

System 5 is the long pole — the only system depending on **all three** shared pieces
plus a brand-new FastFlowLM inference wrapper. **Section I's service-account-vs-API-key
auth decision is the single highest-leverage unblock**: an API-key-only path reads fine
then 401/403s on the first `Player_State` write, silently breaking Systems 4 and 5.

---

## Shared infrastructure (build once, reuse everywhere)

- **Gemini TEXT path** in `utils/gemini.py` — `generate_text()`/`GeminiTextClient` over
  the *existing* `_http_request` + `:generateContent` (responseModalities TEXT), with a
  strict-JSON-with-neutral-fallback parser. Reuses `load_api_key`, `GEMINI_BASE`,
  `GeminiAuthError`/`GeminiAPIError`.
- **Worker registry / multi-slot QThread manager** in `main_window.py` — replaces the
  single `self.current_worker` slot. Every new worker (Oracle, Vibe, Ghost, Sticker,
  Sandbox, Validation) clones the existing `KeyValidationWorker`/`SceneRequestWorker`
  idiom and registers instead of clobbering.
- **`utils/sheets.py`** — raw-urllib Google Sheets v4 client mirroring `gemini.py`
  (`SheetsAuthError`/`SheetsAPIError`, `_sheets_request` reusing the 401/403 split,
  file-then-env credential loaders, token caching). `read_range` + `write_player_state`
  is the spine. Build once in Section I; Systems 4 & 5 both independently scoped a
  duplicate — don't let them.
- **`utils/local_model.py`** — FastFlowLM bridge. Preferred: urllib POST to the
  OpenAI-compatible `flm serve` at `localhost:1234` (reuse `probe_local_api`'s URL
  convention); fallback: `subprocess flm run llama3.2:3b`. Today `probe.py` only
  *detects* `flm`; nothing runs inference. System 5 owns it, but Section I's
  `verify=="fastflowlm"` and System 3's watched runtime both touch FastFlowLM — centralize here.
- **Text-model resolution** in `settings.toml` (`[gemini] text_model` distinct from the
  pinned image model) + a one-time reachability check — `validate_key` only enumerates
  IMAGE models, so every text consumer otherwise risks a 404/403 at runtime.
- **Credential file-then-env + `.gitignore` convention** (the `.gemini_key` pattern) —
  reused for `.sheets_creds.json` / spreadsheet id. Never commit secrets.

---

## Captain blockers (decisions only you can make, before/while building)

1. **AUTH MODEL for Google Sheets** *(gates Section I write-path → Systems 4 & 5)*:
   service-account JSON (read+write, but RS256 JWT signing needs either a pure-Python
   signer to keep the stdlib-only ethos, OR a crypto dep like PyJWT/cryptography that
   breaks the "no third-party networking deps" posture) **vs** API key (read-only —
   can't satisfy the required `Player_State` writes without OAuth). Pick *and* accept
   the cost.
2. **Provision Google Cloud**: Sheets API v4 enabled, a credential file, a shared
   spreadsheet ID with the service account granted edit access, and a test sheet
   pre-populated with `Quest_Log` + `Player_State` tabs migrated from the current
   10-scene `data/quest.py` content.
3. **TEXT MODEL choice** + confirmation it's reachable by your AI Studio key (affects
   all five text consumers).
4. **System 2 palette-morph scope** *(aesthetic)*: in-process-only override
   **(strongly recommended)** vs writing the shared family TOML (would repaint
   Intricate / The Settlers / The Majestic in lockstep). Plus the actual mood palette
   hex codes (sun-drenched vs twilight-lavender) and snap-to-named-moods vs interpolate.
5. **System 4 sticker style** *(aesthetic)*: die-cut flat-vector look, palette,
   transparent background; and persistence policy (commit earned stickers like
   `scenes/`, or gitignore as per-user runtime state).
6. **Oracle scope**: is the LLM-generated `settings.toml` fragment actually *written to
   disk* (real risk: LLM-authored config corrupting the live-reloaded shared palette) or
   display-only flavor? **Recommend display-only for v1.**
7. **System 3 privacy**: raw stack traces (which can contain local paths/env values)
   sent to Gemini — confirm acceptable, or restrict to scrubbed/classified summaries.
8. **Spec/codebase reconciliation**: the bible references `*NodeData` files, a
   spreadsheet, and an `image_prompt`-less `Quest_Log` column set — none match the
   as-built code (single `quest.py` module; `image_prompt` required by the painter for
   *every* scene). Confirm Section I adds an **`Image_Prompt` column** and that
   "verification cell flips True" maps to the verify-probe surface.

---

## Quick wins (lowest effort, highest visible payoff)

- **Hardware Oracle calibration line** — add `probe_gpu()` to `probe.py` (clone
  `probe_npu`'s subprocess idiom) + a `raw_hardware_spec()`, feed it through the new
  text path into the *existing* `bottom_toolbar.set_info` seam at `main_window.py:569`.
  Highly visible ("Ah, 40 Teraops of XDNA 2 power!"), cosmetic, never blocks the quest,
  and validates the shared text client. Keep it display-only.
- **System 3 offline classifier** — the regex classifier (blocked port / missing env
  var / missing module) + hand-written gentle fallback copy delivers the "no red wall
  of stack trace" payoff *before* the Gemini rewrite is even wired, and de-risks the
  privacy question.
- **De-hardcode "Forty teraops"** in `data/quest.py:207` (the `arrival` scene) to
  reflect the real probed figure — trivial edit, immediate authenticity payoff once the
  Oracle exists.
- **System 4 sticker reward off the existing verify-probe** (not waiting on the spine) +
  `StickerCache` cloned from `SceneCache` + a celebration reusing the `toggle_curtains`
  `QPropertyAnimation` idiom — a delightful, visible loot moment built almost entirely
  from existing patterns.
- **Build the worker registry early** — small, invisible, but unblocks Systems 2/4/5
  simultaneously and kills the #1 likely bug.

---

## Per-system notes

### Section I — Google Sheets state machine (Ledger of Fate) · large
- **Today:** story fully hardcoded in `data/quest.py` (`QUEST: list[dict]`, `get_scene()`,
  `_BY_ID`). Each scene carries `id, title, image_prompt, narrative, choices, verify`.
  `main_window._enter_quest`/`_load_scene`/`_on_choice`/`_verify` consume those keys.
  Networking precedent: `gemini._http_request` (raw urllib, 401/403 split). Threading:
  `KeyValidationWorker`/`SceneRequestWorker`. Credentials: `load_api_key` (file→env).
- **Net-new:** `utils/sheets.py` (client + read/write), `data/quest.py` → Ledger class
  keeping the `get_scene(scene_id)->dict|None` signature, re-read-on-entry for live
  browser edits. Keep `STYLE_PREAMBLE`/`_prompt()`.
- **Watch:** writes require OAuth/service-account (API-key-only silently 401s on write);
  per-node synchronous reads must go through a QThread or they freeze the typewriter
  reveal; hand-authored `Choices_JSON` is a parse hazard (guard with a safe fallback
  scene); Sheets quotas can 429 a hot-reload-every-node loop; **`image_prompt` is absent
  from the spec's columns but required by the painter — add an `Image_Prompt` column.**

### Hardware Oracle (Sentient Settings) · medium
- **Today:** `probe_npu()` returns a *friendly* descriptor (not raw specs); no
  `probe_gpu()`. The npu-verify branch in `_load_scene` (557-569) already writes an
  engine line to `bottom_toolbar.set_info` — the natural calibration seam.
- **Net-new:** `probe_gpu()` + `raw_hardware_spec()` in `probe.py`; text calibration call
  in `gemini.py`; `HardwareOracleWorker` (clone `SceneRequestWorker`).
- **Watch:** LLM-authored `settings.toml` could corrupt the live-reloaded shared palette
  — prefer **display-only** for v1; Windows exposes no real NPU TOPS, so figures are
  model-inferred from silicon name; cache the calibration (render-once ethos); degrade
  gracefully on no-NPU/offline/no-key.

### System 2 — Psychological Weather & dynamic palette · large
- **Today:** the free-text hook exists but is a **log-and-drop stub** in `_on_choice`
  (quest phase, ~line 686). `STYLE_PREAMBLE` is a frozen constant baked into each scene's
  `image_prompt` at import. `_reapply_theme()` + per-widget `restyle()` already morph the
  whole window live — but only the external file watcher triggers it today.
- **Net-new:** `analyze_vibe()` text call; `VibeWorker`; `_apply_weather(vibe)`;
  render-time preamble composition (the structural `quest.py` refactor); mood-keyed cache.
- **Watch:** **shared-palette blast radius** — morph in-process only, never write the
  shared TOML; `SceneCache` keys on bare `scene_id`, so mood art is masked unless the key
  includes mood; `InteractionBar` has no `restyle()` (would need adding for full re-tint);
  text model may not be in `available_models`.

### System 3 — Ghost in the Machine · medium
- **Today:** no stream-capture subsystem. `_spawn_restart` is the only `Popen` (inherits
  console, no capture). `NarrativePanel.set_text` is the sink. **`setupLMStudio.ps1` is
  retired/absent** — swap the bible's example for an `flm` command at build time.
- **Net-new:** `utils/process_watch.py` (low-priority QThread Popen line-streamer + regex
  classifier); text path in `gemini.py`; `GhostRewriteWorker`.
- **Watch:** keep `readline()` + the Gemini call off the UI thread; raw traces leak local
  paths/env (privacy call); Windows pipe/encoding (text=True, UTF-8, child must flush);
  classifier-driven offline fallback so the red wall *never* shows.

### System 4 — Procedural sticker loot drops · medium
- **Today:** no spreadsheet — the **real trigger is the per-scene `verify` probe flipping
  True** in `_load_scene` (556-561). `GeminiImageClient` + `SceneCache` + the
  `toggle_curtains` animation idiom are all directly reusable. `graphics/stickers/` doesn't
  exist yet.
- **Net-new:** `utils/sticker_loot.py` (`StickerCache` + `build_sticker_prompt`);
  `StickerRequestWorker` with its **own** handle; celebration UI in `widgets.py`; optional
  `achievement` field on verify-bearing scenes.
- **Watch:** **worker-slot collision** (#1 bug — needs the registry); double-fire on
  revisit (dedupe via `StickerCache.has()`); failed sticker must be non-fatal; restart-on-
  close loses in-session earned-sets unless persisted (files survive, so `has()` is the
  source of truth).

### System 5 — Beyond the Rim side quests · large
- **Today:** linear visual-novel loop; no sandbox, no Sheets, no local inference. The
  `resonance` beat (08) ends `[ FIN ]` — the natural unlock point. The `_on_choice`
  free-text stub is the mission-answer capture point. `probe_fastflowlm`/`probe_local_api`
  detect but never *run* the model.
- **Net-new:** `utils/local_model.py` (run + validate via `flm serve`/`flm run`);
  `utils/sheets.py` (shared with Section I); text path; sandbox beat in `quest.py`;
  `SandboxWorker` + `MissionValidationWorker`; completion-state sidecar (`window_state.json`
  pattern).
- **Watch:** `llama3.2:3b` is a noisy PASS/FAIL judge — forgiving retry + strict parsing;
  worker collisions (registry); Sheets write-auth is the biggest unknown; subprocess
  fragility (`flm run` buffering/quoting on Windows); persist progress before the
  self-restart-on-close.

### Section III — High-end visual contrast (The Flex) · large · own phase
- **Today:** no background layer; every foreground widget paints an opaque `windowBg`
  fill; pure layout Z-stacking. PySide6 ships `QtOpenGL`/`QtOpenGLWidgets`/`QtMultimedia`.
  `.gitattributes` already marks `*.mp4`/`*.webm` binary (pre-baked loop checks in cleanly).
- **Net-new:** `graphics/backdrop.py` (`FluidBackdrop` via QMovie/QVideoWidget, optional
  `ShaderBackdrop` via QOpenGLWidget); `QStackedLayout(StackAll)` in `_build_layout`;
  translucent glassmorphic foreground QSS; `[backdrop]` settings; a seamless loop asset.
- **Watch:** **performance** — pause on curtains-up / tray / unfocus (the single most
  important guard); Z-order regressions with the absolute-positioned TitleBar; legibility
  over a churning background (Qt has no cheap real-time backdrop-blur); translucent +
  frameless + always-on-top can produce compositor artifacts on Windows; degrade to
  `mode='off'` gracefully. **Ship the pre-baked video loop first; shader is Phase 2.**

---

## Structural collisions to manage deliberately

1. **Three systems rewrite `data/quest.py`** (Section I Ledger, System 2 render-time
   preamble, System 5 sandbox beat). Sequence: Ledger first → then mood → then sandbox.
2. **`image_prompt` is required by the painter for every scene** but absent from the
   spec's `Quest_Log` columns — Section I must add an `Image_Prompt` column (or derive
   it) or `SceneView` breaks.

## Across-the-board principles
- Every text round-trip adds latency + quota cost → follow the family
  **render-once-cache-forever** ethos (cache Oracle calibration; cache vibe where sensible).
- Every new path must **degrade gracefully offline** — the quest must never be blocked by
  a cosmetic or networked step.
