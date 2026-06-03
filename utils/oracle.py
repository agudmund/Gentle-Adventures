#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - oracle.py the on-device oracle, a raw-urllib client to flm's local llama
-The small mind that answers from inside the ship, no call ever leaving it, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request

from utils.logger import get_logger
from utils.probe import resolve_flm

logger = get_logger("gentle")


class OracleError(Exception):
    """The local oracle couldn't be reached or answered."""


class Oracle:
    """The on-device llama — served by FastFlowLM (`flm serve`) and spoken to over a
    localhost OpenAI-compatible endpoint with raw urllib. No SDK, no call leaving the
    ship: the whole payoff of scene 04, made literal.

    Departmental isolation: the subprocess + network live here, lazily, so a stumble
    is scoped to this one file and never blocks the quest. The server is started
    LAZILY on the first question (the model loads onto the NPU — a few seconds, the
    "oracle stirs awake" beat) and reused for the session. If something is already
    serving on the port we reuse it and never spawn a second; shutdown() stops only a
    server we started ourselves (never one the captain ran by hand).
    """

    def __init__(self, model: str = "llama3.2:3b", host: str = "127.0.0.1"):
        self.model = model
        self.host = host
        self._port: int | None = None
        self._proc: subprocess.Popen | None = None   # set only if WE started serve

    # ── server ───────────────────────────────────────────────────────────────
    def _flm(self) -> str:
        flm = resolve_flm()
        if not flm:
            raise OracleError("flm is not installed — summon the oracle first (scene 04)")
        return flm

    def port(self) -> int:
        if self._port is None:
            try:
                out = subprocess.run([self._flm(), "port"], capture_output=True,
                                     text=True, timeout=8).stdout
                m = re.search(r"\d{2,5}", out or "")
                self._port = int(m.group()) if m else 11434
            except OracleError:
                raise
            except Exception:
                self._port = 11434
        return self._port

    def _base(self) -> str:
        return f"http://{self.host}:{self.port()}"

    def _is_up(self, timeout: float = 2.0) -> bool:
        try:
            with urllib.request.urlopen(f"{self._base()}/v1/models", timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False

    def ensure_server(self, ready_timeout: float = 90.0) -> None:
        """Make sure a server is answering. Reuse one already up; otherwise spawn
        `flm serve <model> --quiet` and wait until /v1/models responds."""
        if self._is_up():
            return
        flm = self._flm()
        logger.info(f"[oracle] waking the local oracle — flm serve {self.model}")
        try:
            self._proc = subprocess.Popen(
                [flm, "serve", self.model, "--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            raise OracleError(f"could not start the oracle server: {e}") from e
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            if self._is_up():
                logger.info("[oracle] the oracle is awake (server up)")
                return
            time.sleep(1.5)
        raise OracleError("the oracle didn't wake in time (server not ready)")

    # ── ask ──────────────────────────────────────────────────────────────────
    def ask(self, question: str, system: str = "", max_tokens: int = 220) -> str:
        """Put one question to the local oracle and return its answer. Blocking —
        callers run this on a worker thread. Raises OracleError on any stumble."""
        self.ensure_server()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": question})
        body = json.dumps({
            "model": self.model, "messages": messages,
            "max_tokens": max_tokens, "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base()}/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise OracleError(f"the oracle fell quiet: {getattr(e, 'reason', e)}") from e
        except Exception as e:
            raise OracleError(f"the oracle's reply was unreadable: {e}") from e
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            raise OracleError(f"the oracle answered in a shape I couldn't read: {e}") from e

    def shutdown(self) -> None:
        """Stop the server, but only if WE started it (never kill one the captain ran)."""
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
