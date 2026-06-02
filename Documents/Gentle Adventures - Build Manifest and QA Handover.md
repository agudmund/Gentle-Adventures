# Gentle Adventures — Build Manifest & QA Handover

**For:** a fresh reviewer (Gemini) with no prior context on this codebase
**Purpose:** a **second opinion on the base premise and the architectural decisions** — *not* a line-by-line code audit. Read for the *shape* of the thing; the snippets are illustrative (trimmed, with file paths) so you can judge the ideas without reading the whole suite.
**Date:** 2026-06-02 · **Built by:** the author + Claude (Opus 4.8), paired.
**Stack:** Python 3.14 · PySide6 · part of the "Single Shared Braincell" app family.

---

## 0. TL;DR — what we'd like your eyes on

Gentle Adventures (GA) is a frameless, cozy, chibi-Sierra **text-adventure-with-visuals whose subject matter is the player's own computer**. The first adventure teaches the player about the **AMD XDNA2 NPU** inside their laptop — by *playing*, not by reading a manual. It is deliberately *meta*: an illustrated quest whose goal is to wake up and use the very neural engine the app is running on.

We've built the spine and five of the seven planned "systems" in a single intense day. Before we build the rest, we want a gut-check on the **premise** and the **design ethos** (Section 5 has the specific questions). Be a skeptic — that's the job.

---

## 1. The premise (what GA is, and the values it's built on)

- **A game that teaches you your own hardware.** Each scene is a live-generated illustration (Gemini image model) + narrative; the quest walks the player from "what's that third meter?" to running a local LLM on their NPU.
- **Family citizen.** GA shares a `Theme`, logger, settings, the `pretty_widgets` toolkit, and a **swappable LLM seam** with sibling apps. Nothing here is a one-off.
- **Design ethos we're enforcing** (the things worth QA-ing *against*):
  1. **Gentleness / "whisper volume."** No walls of red, no nags, no ruckus. Invitation, never demand.
  2. **Contextual absence.** A missing capability is voiced *in-world* (in the story), never surfaced as an error state or a disabled button.
  3. **Raw-HTTP sovereignty.** We talk to Anthropic / Google / Sheets over raw `urllib`, never a vendor SDK — so an SDK breaking change can never paralyze us.
  4. **Tonal harmonizers.** Each domain (look, vocabulary, narrative) has a *single in-tone authoring surface* everything downstream reads from, so tone structurally cannot fragment.
  5. **Curatorial > generative; deterministic where possible.** The machine is disposable; the workflow is the asset.

---

## 2. Architecture at a glance

```
data/      pure-Python state + the quest (no Qt)
  quest.py            — scenes (id, narrative, choices, verify, *_absent), Ledger overlay
graphics/  Qt rendering + self-contained "citizens"
  weather.py          — Psychological Weather overlay   (System 2)
  scene_map.py        — visited-locked jump map
  sidebar.py          — left rail + 2×3 control corner
  widgets.py          — title bar, narrative panel, scene view, bottom toolbar
utils/     fail-able features, lazy-imported so faults stay scoped
  text.py             — swappable Claude/Gemini text backend (family seam)
  sheets.py           — Google Apps Script proxy client (the Ledger courier)
  lantern.py          — gentle error helper                (System 3)
  sticker_loot.py     — award-from-library reward          (System 4)
  probe.py            — NPU / FastFlowLM hardware probes
main_window.py        — the orchestrator (scene loading, workers, wiring)
```

Two patterns recur and are worth understanding:

- **"Citizens."** `weather`, `scene_map`, `lantern`, `sidebar` are swappable, self-contained modules the window plugs in. *Delete the module + its few lines of wiring and the feature is simply gone* — no tendrils.
- **Worker registry.** Every network/subprocess call runs off the UI thread; stale results (e.g. from a scene you've already left) are dropped by id-guards.

---

## 3. What's built — system by system

### Section I — The Ledger (Google Sheets state spine)

**Premise:** quest content and a player "heartbeat" live in a Google Sheet, reached through a **Google Apps Script web-app proxy** (chosen over a service account / API key). No Google SDK — raw `urllib`. The proxy *always* returns HTTP 200 and puts errors in the body, so we inspect the body, not the status. The client is pure transport; mapping rows→scenes is the Ledger's job in `quest.py`.

```python
# utils/sheets.py — error discrimination (auth vs API) over raw urllib
def _send(self, req):
    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
        raw = resp.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Not JSON → almost always Google's login HTML = web app not
        # deployed with access 'Anyone'.
        raise SheetsAuthError("proxy did not return JSON — check 'Anyone' access.")
    if isinstance(data, dict) and data.get("error"):
        err = str(data["error"])
        raise (SheetsAuthError if "unauth" in err.lower() else SheetsAPIError)(err)
    return data
```

Secrets (`GA_WebApp` URL, `GA_Ledger` token) come from the **environment**, never disk.

---

### The swappable text backend (shared family seam)

**Premise:** all of GA's *text* goes through a `Backend` protocol — Claude by default (`claude-opus-4-8`), Gemini swappable (`gemini-3.5-flash`) — shared with the rest of the family. Construction never hits the network; a missing key only surfaces when `complete()` is actually called.

```python
# shared_braincell/llm.py
class Backend(Protocol):
    name: str
    model: str
    def complete(self, messages: list[dict], *, system: str | None = None,
                 max_tokens: int = 1024, temperature: float | None = None) -> str: ...

# utils/text.py — one doorway; Claude leads, Gemini on a whim
def build_text_backend(settings: dict, app_dir: Path) -> Backend:
    cfg = {**_DEFAULTS, **(settings.get("llm", {}) or {})}
    if str(cfg.get("text_backend")).lower() == "gemini":
        return make_backend("gemini", model=cfg["gemini_model"], api_key=load_api_key(app_dir))
    return make_backend("claude", model=cfg["claude_model"])
```

---

### System 1 — The Hardware Oracle ("Sentient Settings")

**Premise:** once per session, the ship's-computer voice names your *real* silicon in one warm line, generated from the actual hardware spec — the game teaching you your machine, by name.

```python
# main_window.py
def _summon_oracle(self, engine_name: str) -> None:
    spec = raw_hardware_spec()
    system = ("You are the gentle ship's computer ... reply with ONE short, warm, "
              "in-character line that names the NPU's silicon family and offers to "
              "calibrate it. Tone: 'Ah — fifty TOPS of XDNA 2 stirring awake. Let me "
              "tune the plasma injectors for you.'")
    self._request_text([{"role": "user", "content": f"...{spec}..."}],
                       system=system, tag="oracle", on_ready=self._on_oracle_text, ...)
```

---

### System 2 — Psychological Weather  ← **the showcase, two phases done**

**Premise:** we took an old Unity rain experiment (`BaseRainScript.cs`, Digital Ruby) that "proved beautiful", and translated its *math* — not its code — into a PySide `QPainter` overlay. Then we wired it to the player's **emotional vibe**, read live.

**Unity → PySide translation:**

| Unity concept | PySide translation |
|---|---|
| `RainIntensity` (0–1) | the master knob — driven by the vibe vector |
| `RainFallEmissionRate = (max/lifetime)·I` | live droplet count = `MAX_DROPS · level` |
| `RainMistThreshold 0.5`, mist ∝ `I²` | fog gradient fades in past 0.5, opacity ∝ `level²` |
| `WindChangeInterval(5,30s)` | new wind target every 5–30s, **eased** toward |
| `LoopingAudioSource` volume `Mathf.Lerp` | we lerp *intensity itself* + the palette, so shifts breathe in |

3D Unity got "visual weight" free from a camera; in flat 2D we synthesized it with per-drop **depth (0.35–1.0)** scaling length, speed, brightness, and wind response (near-heavy, far-faint) — that parallax is what reads as weight rather than "dots falling."

**(a) the engine core** — `graphics/weather.py`, a click-through "glass-pane" overlay:

```python
def _tick(self):
    self._level += (self._target - self._level) * _LEVEL_LERP        # intensity tide
    # wind retargets every 5..30s, eased; palette eases toward _tint_target ...
    target_n = int(_MAX_DROPS * self._level)                          # emission rate
    while len(self._drops) < target_n: self._drops.append(_Drop(w, h))
    # advance & recycle; an idle clear sky parks the timer (costs nothing)
```

**(b) the vibe → look mapping** — the overlay owns its own "feel":

```python
def set_vibe(self, energy, calm):
    e, c = clamp01(energy), clamp01(calm)
    intensity = clamp(0.12 + c*0.62 - e*0.18, 0, 0.85)   # calm → rain; gusto → clear
    cool, warm = (188,200,238), (245,222,196)            # lavender ↔ sun-pastel
    tint = QColor(*[int(cool[i] + (warm[i]-cool[i])*e) for i in range(3)])
    self.set_palette(tint); self.set_intensity(intensity)  # both EASE in
```

**(c) reading the vibe from free text** — tolerant of whatever the model returns:

```python
# main_window.py — the player types into "ask the ship anything"
def _read_vibe(self, text):
    system = ('... Reply with ONLY a compact JSON object: '
              '{"energy": <0-1>, "calm": <0-1>, "mood": "<words>"} ...')
    self._request_text([{"role":"user","content": text[:400]}],
                       system=system, tag="vibe", on_ready=self._on_vibe_text, ...)

@staticmethod
def _parse_vibe(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)            # shrug off fences/prose
    obj = json.loads(m.group(0))
    return clamp01(obj["energy"]), clamp01(obj["calm"]), str(obj.get("mood",""))[:40]
```

**Validated end-to-end against the live backend:** *"best day in computing ever!!!"* → `energy 0.97 / calm 0.1` (→ clear, warm sky); *"sipping coffee, watching the light come up slow"* → `energy 0.2 / calm 0.85` (→ gentle lavender rain). Async; **silent on absence** (no backend → the sky just holds).

---

### System 3 — The Lantern (gentle error helper)

**Premise:** when a real tool stumbles (e.g. `flm validate`), the player never sees a wall of red. A pure, offline, deterministic classifier tags the stumble and a **warm "let me hold a light to this" line** appears in the narrative; the raw trace goes to the **log only**.

```python
# utils/lantern.py — cheap, offline, kind
_PATTERNS = [("port", re.compile(r"(?i)address already in use|EADDRINUSE|...")),
             ("env",  re.compile(r"(?i)api[_ ]?key.*(not set|missing)|\b40[13]\b|...")),
             ("missing", re.compile(r"(?i)command not found|no module named|..."))]
_GENTLE = {"missing": "The thing we reached for isn't on the shelf yet. Let's fetch "
                      "it first, then carry on. 🔦", ...}
```

`LanternWatch(QThread)` streams a command's output (utf-8/replace so emoji can't crash it), strips ANSI colour, and emits `settled(exit_code, gentle_line, classification, raw_tail)`. A failure *always* earns a gentle line; a clean run says nothing.

---

### System 4 — Sticker loot (award-from-library)

**Premise:** a verified beat blooms a **real sticker from the `iconic` asset library** over the scene (once per scene), with a whispered achievement. We deliberately chose *award-from-library* over *generation* — the procedural-generation ambition is parked in System 5's sandbox. `utils/sticker_loot.py` maps scene → sticker; `main_window._maybe_award_sticker` blooms it. Silent no-op if a scene has no reward.

---

### No-NPU narrative branch (contextual absence, voiced in-world)

**Premise — the purest expression of the ethos:** on a machine *without* an NPU, an NPU-gated scene does **not** dead-end on "not detected." The story itself becomes the gentle guide.

```python
# main_window._load_scene
if verify_kind == "npu" and not verified:
    narrative = scene.get("narrative_absent") or (scene["narrative"] + "\n\n" + NO_NPU_NOTE)
    choices   = scene.get("choices_absent")   or scene["choices"]
```

```python
# data/quest.py — the 'discovery' scene's no-NPU variant (excerpt)
"narrative_absent": (
    "... \"There's no neural engine aboard this ship, captain,\" the computer says ...\n"
    "A kind guide told me the very same, once ... 'you'll want a vessel with a neural\n"
    "engine in its heart — an AMD XDNA 2, or one of its cousins.'\n"
    "So I visited a merchant ... and traded honest riches and a pocketful of simulated\n"
    "gold tokens for one. (I did try to pay in hugs and kind praises first. Sweet\n"
    "currency, the merchant smiled — but not yet legal tender in this timeline.)"
),
```

Pure contextual absence in the story layer — no error, no crash, testable on a no-NPU machine.

---

### Polish (citizens & feel)

Visited-locked jump map (`scene_map.py`); a family-signature 2×3 control corner in the sidebar with a "working" meter (canonical pink-gradient bar that fades in + *breathes* while any worker runs); curtains roll-up with a hair-thin "hem weight" counterweight; titlebar that Title-Cases the scene caption and fades after announcing; default-arrow cursor (a spatial-canvas-native choice, not framework default).

---

## 4. What remains (roadmap)

- **System 2 — Phase 3:** the same vibe read also shifts the image `STYLE_PREAMBLE` (sun-drenched sparkles vs. soothing twilight bokeh), morphs the **window theme** hexes, and tilts the **narrative tone**. (Most invasive arm — touches the image pipeline + live Theme.)
- **System 5 — Infinite "Beyond the Rim" side quests** (procedural, the generative sandbox).
- **Section III — "The Flex":** high-end visual contrast / fluid backdrop.
- **Loose ends:** resume-to-last-scene on launch · wire bottom-toolbar buttons · re-bake scene 4 image · end-to-end FastFlowLM summoning play-test.

---

## 5. The questions we'd actually like answered

Please be a skeptic on the **premise and the ethos**, not the syntax:

1. **Is the core premise sound** — a narrative adventure whose *subject* is the player's own hardware, teaching an abstract thing (an NPU) by play? Does it hold up as a *learning* vehicle, or does the charm fight the pedagogy?
2. **Contextual absence vs. clarity.** We voice missing capabilities *in-world* (the no-NPU merchant beat) rather than as explicit UI. For a *teaching* tool, is that the right call, or does a learner need blunter signposting? Where's the line?
3. **The vibe → weather → (palette/narrative) loop** — delightful, or gimmicky? Does mood-reactive ambience *serve* a learning experience or distract from it?
4. **The 3-layer state** (filesystem + Google Sheet "Ledger" + in-app session) — justified for a single-player cozy game, or over-engineered?
5. **Gentleness as a constraint.** Is there a point where "whisper volume" *under-informs* someone who needs to actually do a thing (install a runtime, flip a setting)?
6. **Raw-HTTP, no-SDK stance** — sound resilience, or reinventing wheels we'll regret?

Anything that makes you go "wait, why?" is exactly what we want to hear.

*— End of handover.*
