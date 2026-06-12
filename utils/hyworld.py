#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - hyworld.py the orbital twin's wake-up courier (EC2 via the aws CLI)
-A whisper from the small ship, and a bigger room stirs in orbit, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import json
import shutil
import subprocess

from utils.logger import get_logger
from utils.proc import CREATE_NO_WINDOW

logger = get_logger("gentle")

# The orbital twin is the captain's own GPU machine on AWS — see the HY-World
# narrative (quest.py HYWORLD_QUEST) and the Ledger doc. This courier talks to
# it through the `aws` CLI as a silent subprocess: the family pattern (GitNode
# shells git, probe.py shells PowerShell) — no SDK rides inside the app or the
# frozen build. Everything here is contextual-absence shaped: missing config,
# missing CLI, no credentials, or an unreachable cloud all return None and the
# story stays gentle; nothing raises across this boundary.

_PROBE_TIMEOUT = 8.0   # describe-instances — read-only, fast
_WAKE_TIMEOUT = 15.0   # start-instances — AWS accepts and returns promptly


def _cfg(settings: dict) -> dict | None:
    """The [hyworld] settings block, or None when the twin isn't configured
    on this machine (contextual absence — the scene plays its 'asleep' face)."""
    c = settings.get("hyworld", {}) or {}
    if not c.get("instance_id"):
        return None
    return c


def _aws(args: list[str], cfg: dict, timeout: float) -> dict | None:
    """Run one aws CLI call, JSON out. None on any stumble (logged, never raised)."""
    exe = shutil.which("aws")
    if not exe:
        logger.debug("[hyworld] aws CLI not on PATH — twin unreachable from here")
        return None
    cmd = [exe, *args, "--output", "json"]
    if cfg.get("profile"):
        cmd += ["--profile", str(cfg["profile"])]
    if cfg.get("region"):
        cmd += ["--region", str(cfg["region"])]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()
            logger.debug(f"[hyworld] aws {args[1]} failed: {tail[-1] if tail else result.returncode}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        logger.debug(f"[hyworld] aws {args[1]} stumbled: {e}")
        return None


def probe_hyworld(settings: dict) -> str | None:
    """The twin's instance state — 'running', 'stopped', 'pending', 'stopping',
    … — or None when unconfigured/unreachable. verify:'hyworld' counts only
    'running' as awake; everything else plays the scene's absent face."""
    cfg = _cfg(settings)
    if not cfg:
        return None
    payload = _aws(["ec2", "describe-instances",
                    "--instance-ids", str(cfg["instance_id"])], cfg, _PROBE_TIMEOUT)
    try:
        state = payload["Reservations"][0]["Instances"][0]["State"]["Name"]
        logger.info(f"[hyworld] twin state: {state}")
        return str(state)
    except (TypeError, KeyError, IndexError):
        return None


def status_hyworld(settings: dict) -> tuple[str, str] | None:
    """State + public IP, the in-game `hy status`: ("running", "3.92.1.7"),
    ("stopped", ""), … or None when unconfigured/unreachable. The Lookout
    scene asks this — the same describe-instances the console wrapper runs."""
    cfg = _cfg(settings)
    if not cfg:
        return None
    payload = _aws(["ec2", "describe-instances",
                    "--instance-ids", str(cfg["instance_id"])], cfg, _PROBE_TIMEOUT)
    try:
        inst = payload["Reservations"][0]["Instances"][0]
        state = str(inst["State"]["Name"])
        ip = str(inst.get("PublicIpAddress") or "")
        logger.info(f"[hyworld] lookout: twin is {state}{' at ' + ip if ip else ''}")
        return state, ip
    except (TypeError, KeyError, IndexError):
        return None


def tuck_in_hyworld(settings: dict) -> bool:
    """Send the twin back to sleep on app exit — a DETACHED stop-instances that
    outlives the dying process (the Intricate exit-housekeeping pattern), so the
    exit ritual never waits on AWS. Fire-and-forget: stop on an already-stopped
    instance is a no-op, an unreachable cloud just means the whisper is lost.
    True when the whisper was sent (configured + CLI present), False otherwise."""
    cfg = _cfg(settings)
    if not cfg:
        return False
    exe = shutil.which("aws")
    if not exe:
        logger.debug("[hyworld] aws CLI not on PATH — no tuck-in from here")
        return False
    cmd = [exe, "ec2", "stop-instances",
           "--instance-ids", str(cfg["instance_id"]), "--output", "json"]
    if cfg.get("profile"):
        cmd += ["--profile", str(cfg["profile"])]
    if cfg.get("region"):
        cmd += ["--region", str(cfg["region"])]
    try:
        import os
        if os.name == "nt":
            flags = (subprocess.DETACHED_PROCESS
                     | subprocess.CREATE_NEW_PROCESS_GROUP
                     | CREATE_NO_WINDOW)
            subprocess.Popen(cmd, creationflags=flags,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(cmd, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        logger.info("[hyworld] tuck-in sent — the twin yawns back to sleep")
        return True
    except Exception as e:
        logger.debug(f"[hyworld] tuck-in stumbled: {e}")
        return False


def wake_hyworld(settings: dict) -> str | None:
    """Ask AWS to start the twin. Returns the state it reports ('pending' on a
    fresh wake, 'running' if it was already up — start-instances is idempotent),
    or None when the whisper didn't get through. The instance takes a minute or
    two to truly boot; callers should re-probe rather than trust 'pending'."""
    cfg = _cfg(settings)
    if not cfg:
        return None
    payload = _aws(["ec2", "start-instances",
                    "--instance-ids", str(cfg["instance_id"])], cfg, _WAKE_TIMEOUT)
    try:
        state = payload["StartingInstances"][0]["CurrentState"]["Name"]
        logger.info(f"[hyworld] wake requested — twin now: {state}")
        return str(state)
    except (TypeError, KeyError, IndexError):
        return None
