#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - player_state.py the ship's logbook, a local-first cache over the cloud Ledger
-Progress kept close to home, whispered up to the stars whenever the line is clear, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("gentle")


class PlayerStateStore:
    """Local-first cache for Player_State, with the Google Sheet as the source of
    truth (the captain's deliberate Sheets-FIRST choice).

    The shape of it:
      • set() writes the LOCAL cache FIRST (instant, never fails) and marks the
        keys pending. So the game can never lose progress to a network drop — the
        cloud was only ever holding a copy.
      • flush() pushes the pending keys up to the Sheet; on success they clear.
      • hydrate() (startup) pulls the Sheet as the base truth, overlays any local
        pending on top (so offline progress isn't clobbered by a stale cloud row),
        persists, and flushes the pending back up — keeping the Sheet canonical.

    Disk writes are atomic (temp + os.replace) so a crash mid-write can't corrupt
    the logbook. Thread-safe: the UI thread set()s while a worker flush()es; the
    network call happens OUTSIDE the lock so it never stalls the UI.
    """

    def __init__(self, sheets, app_dir: Path):
        self._sheets = sheets                              # SheetsProxyClient | None
        self._path = Path(app_dir) / "player_state.json"
        self._tmp = self._path.parent / (self._path.name + ".tmp")
        self._lock = threading.Lock()
        self._state: dict = {}
        self._pending: dict = {}
        self._load()

    # ── disk ──────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._state = dict(data.get("state", {}))
                self._pending = dict(data.get("pending", {}))
                logger.info(f"[state] local logbook loaded "
                            f"({len(self._state)} keys, {len(self._pending)} pending)")
        except Exception as e:
            logger.warning(f"[state] local cache unreadable ({e}); starting fresh")

    def _save_locked(self) -> None:
        """Persist atomically. Caller MUST hold self._lock."""
        payload = {
            "state": self._state,
            "pending": self._pending,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            self._tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
            self._tmp.replace(self._path)   # atomic on the same volume
        except Exception as e:
            logger.warning(f"[state] could not write local logbook: {e}")

    # ── reads ───────────────────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        with self._lock:
            return self._state.get(key, default)

    def all(self) -> dict:
        with self._lock:
            return dict(self._state)

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def configured(self) -> bool:
        return self._sheets is not None

    # ── writes (local-first) ──────────────────────────────────────────────────

    def set(self, updates: dict) -> None:
        """Apply updates to the working state, mark them pending, and persist the
        local cache immediately. Always succeeds (no network). Call flush() after
        to attempt the cloud push."""
        if not updates:
            return
        with self._lock:
            for k, v in updates.items():
                self._state[k] = v
                self._pending[k] = v
            self._save_locked()

    # ── cloud sync ──────────────────────────────────────────────────────────────

    def flush(self) -> bool:
        """Push pending keys to the Sheet. True if everything synced (or nothing
        was pending); False if there's no proxy / the push failed (pending is kept
        to retry next time). The network call runs OUTSIDE the lock."""
        if self._sheets is None:
            return False
        with self._lock:
            if not self._pending:
                return True
            snapshot = dict(self._pending)
        try:
            # The SPINE write-path Systems 4 and 5 call back into — Player_State
            # upserts, through the family courier's generalized key-value surface.
            self._sheets.write_state("Player_State", snapshot)
        except Exception as e:
            logger.info(f"[state] flush deferred — {len(snapshot)} key(s) kept on board ({e})")
            return False
        with self._lock:
            # Clear only what we just synced; any set() that landed during the
            # network write keeps its newer value pending for the next flush.
            for k, v in snapshot.items():
                if self._pending.get(k) == v:
                    del self._pending[k]
            self._save_locked()
        logger.info(f"[state] flushed {len(snapshot)} key(s) up to the Ledger")
        return True

    def hydrate(self) -> bool:
        """Startup: pull the Sheet (source of truth) into the cache, overlay any
        local pending (offline progress wins over a stale cloud row), persist, then
        flush the pending back up. True if the Sheet was reachable (→ live), False
        if we're running on the local logbook alone (offline fallback)."""
        if self._sheets is None:
            return False
        try:
            remote = self._sheets.read_state("Player_State")
        except Exception as e:
            logger.info(f"[state] remote hydrate unavailable; sailing on the local logbook ({e})")
            return False
        with self._lock:
            merged = dict(remote)
            merged.update(self._pending)   # local pending wins over the cloud
            self._state = merged
            self._save_locked()
        self.flush()   # push any buffered local changes so the Sheet catches up
        logger.info(f"[state] hydrated from the Ledger ({len(remote)} key(s) from the cloud)")
        return True
