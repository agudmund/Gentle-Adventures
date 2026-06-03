# Sheets Ledger — Setup & "Why Is It Off?"

Gentle Adventures can run its quest from a **live Google Sheet** (the *Ledger*) and
push a **Player_State heartbeat** back up to it. This is optional: when it's not
configured, GA runs perfectly on the **bundled quest** baked into `data/quest.py`.
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

## Architecture notes (for the curious)

- Transport: `utils/sheets.py` (`SheetsClient`) — raw `urllib`, the proxy always
  answers **HTTP 200** with errors in the body, so the client inspects the body.
- Content: `data/quest.py` (`_Ledger`) maps `Quest_Log` rows → scene dicts by
  **column name** (robust to column reordering), with the bundled `QUEST` as the
  fallback.
- Config resolution: `load_proxy_config()` — environment first, then
  `.sheets_proxy.json`. Raises `SheetsAuthError` if neither yields both values,
  which is exactly what flips the Ledger to OFF (gracefully).
