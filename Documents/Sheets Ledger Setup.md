# Sheets Ledger — Setup & "Why Is It Off?"

Gentle Adventures can run its quest from a **live Google Sheet** (the *Ledger*) and
push a **Player_State heartbeat** back up to it. This is optional: when it's not
configured, GA runs perfectly on the **bundled quest** baked into `quest.py`.
Nothing breaks — the cloud layer is a bonus, not a dependency.

This note explains how to tell whether the Ledger is on, and how to turn it on.

---

## How to tell if it's OFF

At launch, GA logs **one clear line**. If the Ledger is off you'll see:

```
[sheets] LEDGER OFF: live cloud sync + Player_State heartbeat are disabled;
running on the bundled quest (graceful fallback, not an error). To enable, the
in-app 'Opening the Ledger' setup handles it at launch (paste the web-app URL +
token, no relaunch needed), or set GA_WebApp + GA_Ledger in the environment.
Setup: Documents/Sheets Ledger Setup.md. [why: ...]
```

When it's **on**, you'll instead see (roughly):

```
[ledger] loaded N scene(s) from the live Quest_Log
```

and the bottom strip gives a small **gold spectral pulse** each time a
Player_State heartbeat round-trips successfully.

> The log lives in the shared logs folder — by default
> `~/Documents/SingleSharedBraincell/Logs/` (or the `[shared] log_dir` from the
> shared settings, rehomed to this machine's user profile automatically).

---

## How to turn it ON

The Ledger talks to a **Google Apps Script web app** (a proxy in front of the
Sheet — no Google SDK, raw HTTPS, token-gated). GA needs two values:

| What | Where it comes from |
|---|---|
| **`GA_WebApp`** | the Apps Script **web-app URL** (`…/exec`), deployed with access = **Anyone** |
| **`GA_Ledger`** | the **shared token** the proxy checks on every request |

### Option A — the in-app setup (easiest; no relaunch)

When the Ledger isn't configured, GA shows the **"Opening the Ledger"** screen
(scene 0.5) right after the painter is confirmed. Paste the web-app URL, then the
token (masked as you type); GA persists both as **user** environment variables AND
brings the Ledger online in the same session, so it lights up immediately. "Sail
without the Ledger" skips it, and it re-offers on the next launch while it stays
unconfigured.

### Option B — set the environment variables yourself (secrets stay off disk)

Set them as **user** environment variables, then **relaunch GA** (a running
process won't see env vars set after it started; Option A avoids this entirely):

```powershell
[Environment]::SetEnvironmentVariable('GA_WebApp', 'https://script.google.com/macros/s/XXXX/exec', 'User')
[Environment]::SetEnvironmentVariable('GA_Ledger', 'your-shared-token',                          'User')
```

> Open a **new** shell (or relaunch the launcher) afterwards so the refreshed
> environment is inherited. The keys are read from the environment first,
> precisely so they never have to live in a file.

### Option C — `.sheets_proxy.json` fallback (if you prefer a file)

Drop a file named `.sheets_proxy.json` in the GA app directory:

```json
{ "url": "https://script.google.com/macros/s/XXXX/exec", "token": "your-shared-token" }
```

Environment variables **win** over this file if both are present.

---

## Common reasons it's off (in order of likelihood)

1. **GA was launched before the env vars were set** → relaunch.
2. **Launched from an environment that doesn't inherit user env vars** (e.g. an
   IDE/terminal started earlier) → start a fresh shell, relaunch.
3. **Web app not deployed as "Anyone"** → Google returns a login page (not JSON);
   GA reports this as an auth problem. Re-deploy the Apps Script with access
   set to **Anyone**.
4. **Token mismatch** → the proxy rejects the request; fix `GA_Ledger`.
5. **No network / proxy unreachable** → transient; GA falls back gracefully.

In every one of these cases GA keeps running on the bundled quest — the only
thing you lose is live editing of scenes from the Sheet and the heartbeat.

---

## The revert guard (`_meta`) — arming it

The Ledger carries an optional **revert arbiter** (State Sync v2, principles 8–9):
a `_meta` tab holding a monotonic `version` integer. The game records the version
it loaded and **quarantines any pull whose version went backward** (a silent
backward step is suspect) — last-good kept, banner surfaced. When `_meta` is
absent the game runs on content-hash detection alone (every edit still
propagates; only the explicit revert guard is unavailable) and logs `vNone`.

The client side is fully wired and arms itself the moment the tab exists.
`sanitize_sheets.py --push --apply` already bumps the version when it writes.
What the Sheet cannot do alone is bump the version on **human browser edits** —
that needs a tiny Apps Script trigger, and Apps Script triggers can only be
installed from the Sheet's own script project in the browser.

**To arm the guard** — the `onEdit` function in
[`apps_script/Code.gs`](../apps_script/Code.gs) (the proxy's **source of
record** since 2026-07-23 — the browser project should always match that file).
Paste the whole file over the project's Code.gs and save. The trigger **creates
`_meta` itself** on the first content edit, so there is no separate tab-creation
step — paste, save, edit any content cell once, and the next GA session logs
`v1` instead of `vNone`.

**The deploy ritual** (for the doGet/doPost half): web-app changes only go live
after Deploy → Manage deployments → edit → **New version** — the `/exec` URL
(`GA_WebApp`) never changes. The `onEdit` trigger is the exception: simple
triggers run from the saved head script immediately, no redeploy needed.

**The token lives in Script Properties, never in the source**: Project Settings
→ Script Properties → `GA_TOKEN`, same value as the `GA_Ledger` environment
variable. Rotation is a one-property flip on each side. (Set the property
BEFORE deploying a new version — the upgraded proxy answers `unauthorized`
until it's there.)

Worth knowing (verified live, 2026-07-23):

- `onEdit` is a *simple trigger* — it fires on **human browser edits only**.
  Proxy/API writes don't fire it, which is the right shape: `--push` bumps the
  version itself, and any future writer daemon must do the same (mirror
  `_bump_meta_version` in `sanitize_sheets.py`).
- Pre-upgrade lore, kept for era-dating: the original proxy's **GET threw
  uncaught on a missing tab** (Google answered an HTML error page, which the
  client could only classify as auth-shaped), while POST answered a clean
  `{"error": "no such sheet"}`. The upgraded proxy wraps doGet so every failure
  answers JSON. A `vNone` with an otherwise healthy Ledger still simply means
  the `_meta` tab doesn't exist yet.
- The original proxy **could not create tabs**; the upgraded one can, opt-in
  only (`create: true` on POST, plus the self-creating `_signals` intercom
  socket) — a typo'd tab name stays an error, never a tab.
- The upgrade also completed the `_signals` **append handler** (stamped rows,
  the client's `write_signal` now actually delivers), added `op=list` /
  `op=version` GETs (tab discovery + the cheap heartbeat token), attached
  `version` to every read, and planted the **type-fidelity guard** — the
  Player_State value column is forced to plain text on every upsert, so a
  time-shaped string is never again coerced onto the 1899 spreadsheet epoch
  (the 2026-06-03 DISCOVERY finding, closed at the proxy).

- **2026-07-24 — the Sakura-lessons hardening** (deployed same day). `doPost`
  mutations now serialize under `LockService` (one writer at a time at the
  seam), every write path passes the `_scalar`/`_literal` guards — non-scalar
  values store as deterministic JSON text, leading-`=` strings store as
  literal text instead of executing as formulas — and the bulk-rows path
  carries the same `'@'` type guard as updates (a virgin column had been
  coercing `'03:00:33'` onto the 1899 epoch and eating a `3-1` Scene_ID as
  March 1st, both live-proven before the fix).

- **The proof half of the deploy ritual**: after every Code.gs paste-and-
  redeploy, run `python -m utils.probe_sheets` — the standing round-trip
  fidelity probe writes the known hazard matrix through both write paths
  against the `_probe` scratch tab and reports per-value PASS/FAIL. All 28
  green is the finish line; formula FAILs against an older deployment are the
  expected "not deployed yet" signature, not a courier bug.

---

## Architecture notes (for the curious)

- Transport: `shared_braincell.sheets` (`SheetsProxyClient`) — the family courier,
  lifted from `utils/sheets.py` 2026-07-24. Raw `urllib`, the proxy always
  answers **HTTP 200** with errors in the body, so the client inspects the body.
  GA binds its slots + identity in `utils/identity.py` (`sheets_client()`).
- Content: `quest.py` (`_Ledger`) maps `Quest_Log` rows → scene dicts by
  **column name** (robust to column reordering), with the bundled `QUEST` as the
  fallback.
- Config resolution: `load_proxy_config()` — the app's own env-key slots first
  (GA passes `GA_WebApp` / `GA_Ledger`), then `.sheets_proxy.json`. Raises
  `SheetsAuthError` if neither yields both values, which is exactly what flips
  the Ledger to OFF (gracefully).
