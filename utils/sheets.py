#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - sheets.py the Ledger's courier, a raw-urllib Sheets proxy client
-We whisper the ship's state up to the cloud grid and read the quest home, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("gentle")


# The environment is the single source of truth for the proxy URL + shared
# token — secrets live in the environment, never on disk (the same ethos as the
# Gemini key). A .sheets_proxy.json fallback is honoured only if someone really
# wants a file; env wins. Talks to a Google Apps Script web app, NOT the Sheets
# SDK — raw urllib, in keeping with the family's no-SDK / raw-HTTP sovereignty.
_ENV_URL_KEYS = ("GA_WebApp", "GA_WEBAPP", "GA_WEB_APP")
_ENV_TOKEN_KEYS = ("GA_Ledger", "GA_LEDGER")


class SheetsError(Exception):
    """Base for Sheets-proxy failures."""


class SheetsAuthError(SheetsError):
    """Missing or rejected credentials — absent URL/token, bad token, or a web
    app not deployed with 'Anyone' access (Google answers with a login page)."""


class SheetsAPIError(SheetsError):
    """The proxy answered, but with a fault (bad sheet name, script error, …)."""


def _first_env(keys) -> str | None:
    for k in keys:
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    return None


def load_proxy_config(app_dir: Path | None = None) -> tuple[str, str]:
    """Resolve (url, token) from the environment first, then an optional
    .sheets_proxy.json fallback. Raises SheetsAuthError if neither yields both."""
    url = _first_env(_ENV_URL_KEYS)
    token = _first_env(_ENV_TOKEN_KEYS)
    if (not url or not token) and app_dir is not None:
        f = Path(app_dir) / ".sheets_proxy.json"
        if f.exists():
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
                url = url or cfg.get("url")
                token = token or cfg.get("token")
            except Exception as e:
                logger.warning(f"[sheets] .sheets_proxy.json unreadable: {e}")
    if not url or not token:
        raise SheetsAuthError(
            "Sheets proxy not configured — set GA_WebApp (web-app URL) and "
            "GA_Ledger (shared token) in the environment."
        )
    return url, token


class SheetsClient:
    """Tiny raw-urllib client for the Apps Script proxy (no Google SDK).

    The proxy answers JSON over HTTP and ALWAYS returns HTTP 200 — errors arrive
    in the body as {"error": ...}, so we inspect the body, not the status code.

        reads   GET  ?token=&sheet=            -> {"sheet", "values": [[...]]}
        writes  POST {token, sheet, updates}   -> {"ok": true}

    Transport only: mapping Quest_Log rows into scene dicts is the Ledger's job
    (data/quest.py), not this courier's.
    """

    def __init__(self, app_dir: Path | None = None, timeout: float = 15.0):
        self._url, self._token = load_proxy_config(app_dir)
        self.timeout = timeout

    # ── transport ──────────────────────────────────────────────────────────

    def _get(self, sheet: str):
        qs = urllib.parse.urlencode({"token": self._token, "sheet": sheet})
        return self._send(urllib.request.Request(f"{self._url}?{qs}", method="GET"))

    def _post(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        return self._send(req)

    def _send(self, req):
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise SheetsAPIError(f"proxy unreachable: {getattr(e, 'reason', e)}") from e
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Not JSON — almost always Google's auth/login HTML, i.e. the web app
            # isn't deployed with access set to 'Anyone'.
            raise SheetsAuthError(
                "proxy did not return JSON — check the web app is deployed with "
                "access set to 'Anyone'."
            )
        if isinstance(data, dict) and data.get("error"):
            err = str(data["error"])
            if "unauth" in err.lower():
                raise SheetsAuthError(f"proxy rejected the token: {err}")
            raise SheetsAPIError(err)
        return data

    # ── reads ────────────────────────────────────────────────────────────────

    def read_sheet(self, sheet: str) -> list[list]:
        """Return the full value matrix of a tab (rows of cells, header first)."""
        data = self._get(sheet)
        return data.get("values", []) if isinstance(data, dict) else []

    def read_player_state(self) -> dict:
        """Player_State as a {Variable_Name: Value} dict (header row skipped)."""
        rows = self.read_sheet("Player_State")
        out: dict[str, object] = {}
        for row in rows[1:]:
            if row and str(row[0]).strip():
                out[str(row[0])] = row[1] if len(row) > 1 else ""
        return out

    # ── writes ─────────────────────────────────────────────────────────────

    def write_player_state(self, updates) -> dict:
        """Upsert one or more Player_State rows by Variable_Name. The proxy
        stamps Last_Updated. `updates` may be a dict {var: value} or a list of
        {"variable","value"} dicts. Returns the proxy's parsed response.

        This is the SPINE write-path Systems 4 and 5 call back into.
        """
        if isinstance(updates, dict):
            updates = [{"variable": k, "value": v} for k, v in updates.items()]
        logger.info(f"[sheets] writing Player_State ({len(updates)} update(s))")
        return self._post({"token": self._token, "sheet": "Player_State",
                           "updates": updates})

    def replace_rows(self, sheet: str, rows: list[list]) -> dict:
        """Replace a tab's data rows (everything below the header) with `rows`.
        The way to push content UP — e.g. migrating Quest_Log. Newline-safe
        because the payload is JSON, not a pasted TSV. Returns the proxy reply.
        """
        logger.info(f"[sheets] replacing {sheet} data rows ({len(rows)} row(s))")
        return self._post({"token": self._token, "sheet": sheet, "rows": rows})
