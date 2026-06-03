#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - oracle.py the on-device oracle, a raw-urllib client to flm's local llama
-The small mind that answers from inside the ship, no call ever leaving it, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

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
        self._serve_log = None                        # flm serve output handle (ours)
        self._transcript_stamp: str | None = None     # per-session transcript filename stamp

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
            log_path = self._serve_log_path()
            self._serve_log = open(log_path, "ab") if log_path else None
            self._proc = subprocess.Popen(
                [flm, "serve", self.model, "--quiet"],
                stdout=(self._serve_log or subprocess.DEVNULL),
                stderr=subprocess.STDOUT,
            )
            if log_path:
                logger.info(f"[oracle] flm serve output → {log_path}")
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
            answer = (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            raise OracleError(f"the oracle answered in a shape I couldn't read: {e}") from e
        self._log_exchange(question, answer)
        return answer

    # ── transcripts (save every exchange for later fun) ───────────────────────
    def _serve_log_path(self):
        """File for flm serve's own session output — the 'Start-Transcript when
        calling flm' capture, kept in the GA repo. None if the dir can't be made."""
        try:
            d = Path(__file__).resolve().parent.parent / "Documents" / "Data" / "Oracle"
            d.mkdir(parents=True, exist_ok=True)
            return d / f"flm_serve_{time.strftime('%Y%m%d-%H.%M.%S')}.log"
        except Exception:
            return None

    def _transcript_dirs(self):
        """Where oracle conversations are saved — the GA repo first, then a second
        copy in OS Documents (and the family chat-history dir if set). 'Several
        backups, just in case', mirroring The Majestic's chat persistence."""
        dirs = []
        try:
            dirs.append(Path(__file__).resolve().parent.parent / "Documents" / "Data" / "Oracle")
        except Exception:
            pass
        try:
            dirs.append(Path.home() / "Documents" / "GentleAdventures" / "Oracle")
        except Exception:
            pass
        env = os.environ.get("SingleSharedBraincell_ChatHistory")
        if env:
            dirs.append(Path(env) / "GentleAdventures-Oracle")
        return dirs

    def _log_exchange(self, question: str, answer: str) -> None:
        """Append one Q&A to the session transcript(s) — saved by default so the
        conversations are kept to replay later. Best-effort; never raises."""
        if not self._transcript_stamp:
            self._transcript_stamp = time.strftime("%Y%m%d-%H.%M.%S")
        name = f"oracle_{self._transcript_stamp}.md"
        header = ("# Gentle Adventures — Oracle transcript\n"
                  f"# the on-device llama ({self.model}), session {self._transcript_stamp}\n")
        block = f"\n## {time.strftime('%H:%M:%S')}  ·  Q: {question.strip()}\n\n{answer.strip()}\n"
        for d in self._transcript_dirs():
            try:
                d.mkdir(parents=True, exist_ok=True)
                f = d / name
                if not f.exists():
                    f.write_text(header, encoding="utf-8")
                with f.open("a", encoding="utf-8") as fh:
                    fh.write(block)
            except Exception as e:
                logger.debug(f"[oracle] transcript write skipped for {d} ({e})")

    def shutdown(self) -> None:
        """Stop the server, but only if WE started it (never kill one the captain ran)."""
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._serve_log is not None:
            try:
                self._serve_log.close()
            except Exception:
                pass
            self._serve_log = None
