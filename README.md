# Gentle Adventures

A cozy illustrated quest game about the computer it runs on.

You are the captain of a small ship (your laptop). Something aboard has just woken up: the NPU, a grid of small minds that has been waiting kindly for you to notice it. Gentle Adventures walks you through meeting it, scene by scene, in the voice of the ship's computer. Chibi-Sierra art, soft pastel palette, whisper volume throughout. The lessons are real (Windows Studio Effects, a local llama running on the NPU via FastFlowLM), but they arrive as errands in a story, never as a manual.

Part of the Single Shared Braincell family, alongside Intricate, The Majestic, and Pretty Widgets.

## What it does

- **Tells a quest in illustrated scenes.** Each scene is a Gemini-rendered chibi illustration, a passage of narrative, and a small set of choices. The story teaches you what an XDNA NPU is and then has you actually use it.
- **Runs a local oracle.** The payoff errand summons `llama3.2:3b` onto the NPU through FastFlowLM, then opens a free-text channel to it. Questions are answered from inside the ship; nothing leaves the machine. Transcripts are kept in `Documents/Data/Oracle/`.
- **Reads its story from a ledger.** The quest's source of truth is a Google Sheet (the `Quest_Log` tab), reached through a tiny Apps Script proxy with raw `urllib` — the proxy's source of record is versioned in-repo at `apps_script/Code.gs` (edit here, paste there, redeploy). The bundled quest in `quest.py` is the offline fallback, and the committed floor refreshes itself from the live Sheet on every launch. The story is editable state: it can be rewritten while the game lives on.
- **Remembers the captain.** `player_state.json` is a local-first cache over the same Sheet: progress writes locally first (instant, never fails), then syncs upward, so offline play never loses anything.
- **Carries psychological weather.** A click-through overlay of rain, wind, and mist whose intensity follows the story's emotional state.
- **Degrades by absence, not by error.** No NPU aboard? The scene becomes a kind, patient place that imagines one. Missing FastFlowLM gets an in-world nudge. Nothing in the game shows a red wall.

## Two adventures

The title bar carries a narrative selector, fed by a drop-in registry in `quest.py`. Each narrative is one Quest_Log-shaped tab in the same Sheet; add a tab and a registry line, and a new adventure appears in the selector.

- **Gentle Adventures** (default): the NPU tour described above. The ship learns to use its own small grid of minds.
- **HY-World**: the orbital twin. Some thoughts are bigger than one small ship, so the captain climbs to a second light holding steady in orbit: their own GPU machine on AWS, an EC2 box built for the heavy paint and the long thinking, with answers sent home as if they'd never left. A short three-beat ascent ends in a confirmation scene where two little real-time mini-games (Llama no Drama Lama, and The Void and the Noid) are the soft proof the orbital twin is awake. The live probe gating that final scene wires in once the box is up.

The active choice persists in `active_narrative.txt`, and each narrative keeps its own offline floor (`Documents/Data/quest_floor.json`, `Documents/Data/hyworld_floor.json`) resynced from the live Sheet.

## Running it

| Way | How |
|---|---|
| Play | Double-click `Gentle Adventures.vbs` (headless, no console) |
| Develop | `python main.py` from the app directory |
| Standalone | `Gentle Adventures.exe` (thin frozen build over the shared family runtime, produced by `build.py`) |

Needs Python 3.11+ with the family packages installed editable (`pretty_widgets`, `shared_braincell`, `leopold`). Credentials live in environment variables only, never on disk: `GEMINI_GENTLE_KEY` for scene images (GA's own key slot; the generic `GEMINI_API_KEY` / `SingleSharedBraincell_GeminiKey` remain as fallbacks), the family keychain's `ANTHROPIC_API_KEY` entry for Claude text (keychain-first, never a persisted env var), `GA_WebApp` and `GA_Ledger` for the Sheet proxy. A first-run wizard handles the Gemini key and stores it straight into the environment.

## Autostart (login)

Gentle Adventures comes up on every login. The canonical rail is a Windows Scheduled Task, registered declaratively: the repo ships `autostart_task.xml`, and Compass's install pass (`_util\install.bat` via `Compass.setup`, the `step_app_autostart` step) wires it on any machine the app is present on. No Startup-folder shortcut; the task supersedes it.

The task passes `--minimized` everywhere. Per-machine startup behaviour is the app's own decision, not the launcher's: on the TV-role machine (Sakura) `utils/identity.is_wake_display()` overrides the flag and GA wakes maximized as the boot heartbeat, while every other machine keeps the tray autostart. One task definition, one flag; the fleet's differences live in code that can explain itself. The trigger carries no delay, so login behaviour matches the old immediate shortcut on both machines.

GA carries the family singleton port guard (port 47323, the suite convention), and a duplicate launch is a summons — a live-python duplicate asks the running instance to show itself and exits (2026-07-20), while since 2026-07-23 a FROZEN duplicate is a changing of the guard: a live dev incumbent yields the stage to the fresh exe (the build→exe swap, with the ring's previous generation as crash-net understudy), and a frozen incumbent simply fronts itself. Still keep exactly one autostart rail per machine: the moment the task registers, any old Startup-folder `.lnk` should retire, so login doesn't race two instances at the knock.

```powershell
Get-ScheduledTask -TaskName 'Gentle Adventures Autostart'   # State -> Ready
```

## How it's built

```
main.py / main_window.py   App shell and orchestrator; worker threads for
                           every network and subprocess call
quest.py                   The quest itself: scenes, choices, verify rules,
                           and the style preamble that keeps the art consistent
graphics/                  Self-contained UI citizens: widgets, scene map,
                           keepsake shelf, captain's log, ship's codex,
                           sidebar, psychological weather
utils/                     Fail-able features, lazy-imported so a fault stays
                           scoped to one file: sheets client, player state,
                           NPU probe, oracle, text backends, sticker loot
Images/                    Icons (brand mark, stickers) and cached
                           Gemini-rendered scene art
Audio/                     Narrator takes, played when their scene lands
                           (scene text is coupled to these recordings)
Documents/                 Design briefs, the narrator voice guide, build
                           manifest, oracle transcripts
settings.toml              Live-read window, theme, model, and game values
```

Five principles are enforced throughout (see `Documents/Gentle Adventures - Build Manifest and QA Handover.md`):

1. **Gentleness.** Whisper volume, no nags, nothing punitive.
2. **Contextual absence.** A missing capability is voiced in-world, never surfaced as an error state.
3. **Raw-HTTP sovereignty.** No vendor SDKs anywhere; Google, Gemini, and Claude are all reached with raw `urllib`.
4. **Tonal harmonizers.** One authoring surface per domain, so the voice stays single.
5. **Curatorial over generative.** Deterministic wherever possible; generation is used where it serves the craft.

The narrator's voice has its own canon in `Documents/Gentle Adventures - Narrator Voice Guide.md`: the ship speaks kindly, machines breathe and stir rather than execute, and every real command the player learns is woven into the story as an errand.

---

*Built using a single shared braincell by Yours Truly and various Intelligences, For Enjoying.*
