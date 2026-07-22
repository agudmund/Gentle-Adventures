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
import sys
from pathlib import Path

# Run-from-anywhere: put the project root (this file's parent's parent) on the
# path so `utils.*` resolves no matter how hyworld is reached — imported as
# `utils.hyworld` by the running app, run as `python hyworld.py`, or poked at as
# a bare `import hyworld` in a console opened inside utils/. Idempotent: a no-op
# once the app has already seeded root. Matches sanitize_sheets.py's idiom.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.logger import get_logger          # noqa: E402
from shared_braincell.console import CREATE_NO_WINDOW  # noqa: E402

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


def _raise_tunnel_detached() -> None:
    """The wake ripple (2026-07-13): after a successful wake whisper, fire the
    family `twin` wrapper detached to raise the SSM tunnel once the box reaches
    running (--wait polls for it), so a GA wake ends with https://the-twin/
    answering — same destination as `twin wake` from a console. Best-effort and
    fully detached: WorldMirror itself rides the twin's own systemd unit, this
    only adds the machine-local tunnel; absence of the wrapper is contextual
    absence, never an error."""
    twin_cmd = shutil.which("twin")
    if not twin_cmd:
        logger.debug("[hyworld] no `twin` wrapper on PATH — tunnel stays a console act")
        return
    try:
        import os
        flags = 0
        if os.name == "nt":
            flags = (subprocess.DETACHED_PROCESS
                     | subprocess.CREATE_NEW_PROCESS_GROUP
                     | CREATE_NO_WINDOW)
        subprocess.Popen([twin_cmd, "tunnel", "start", "--wait"],
                         creationflags=flags, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("[hyworld] tunnel ripple sent — https://the-twin/ once she's up")
    except Exception as e:
        logger.debug(f"[hyworld] tunnel ripple stumbled: {e}")


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
        if state in ("pending", "running"):
            _raise_tunnel_detached()
        return str(state)
    except (TypeError, KeyError, IndexError):
        return None


# ── Console utility ───────────────────────────────────────────────────────────
# `python hyworld.py [status|probe|wake|tuck]` — the same whispers the in-game
# `hy` verbs send, runnable straight from a shell for an operator poke. Default
# verb is read-only `status`; wake/tuck carry real AWS side effects (they start /
# stop the paid GPU twin) so they're never the default — you have to name them.
# Loads the live settings.toml exactly as main.py does, and stays contextual-
# absence shaped: an unconfigured or unreachable twin just prints its quiet face.
if __name__ == "__main__":
    from utils.paths import app_root
    from utils.settings import load_settings

    verb = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    settings = load_settings(app_root() / "settings.toml")

    if _cfg(settings) is None:
        print("hyworld: the orbital twin isn't configured on this machine "
              "([hyworld] instance_id missing from settings.toml).")
        sys.exit(0)

    if verb == "status":
        res = status_hyworld(settings)
        if res is None:
            print("hyworld: twin unreachable (no aws CLI / creds / cloud).")
        else:
            state, ip = res
            print(f"hyworld: {state}{' @ ' + ip if ip else ''}")
    elif verb == "probe":
        print(f"hyworld: {probe_hyworld(settings) or 'unreachable'}")
    elif verb == "wake":
        print(f"hyworld: wake -> {wake_hyworld(settings) or 'whisper lost'}")
    elif verb == "tuck":
        ok = tuck_in_hyworld(settings)
        print("hyworld: tuck-in sent — the twin yawns back to sleep" if ok
              else "hyworld: no tuck-in from here.")
    else:
        print(f"hyworld: unknown verb {verb!r} — try: status | probe | wake | tuck")
        sys.exit(2)
