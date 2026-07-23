#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - main.py application bootstrap
-The captain wakes and the bridge hums anew, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import ctypes
import signal
import sys
from pathlib import Path

# ── Startup bytecode purge — runs BEFORE any project import ───────────────────
# If a previous run crashed or was force-killed, closeEvent's sweep never ran,
# so a stale .pyc could be sitting here waiting to be imported. Clear it first,
# with raw shutil inline — never load a project helper to do this, because that
# helper's own .pyc could be the stale one. Sweeps the in-tree __pycache__ and,
# when bytecode is redirected (PYTHONPYCACHEPREFIX), this app's mirror subtree.
import shutil as _shutil

_APP_DIR = Path(__file__).resolve().parent
_purge_roots = [_APP_DIR]
_pc_prefix = getattr(sys, "pycache_prefix", None)
if _pc_prefix:
    _purge_roots.append(Path(_pc_prefix, *_APP_DIR.parts[1:]))
for _base in _purge_roots:
    for _pc in list(_base.rglob("__pycache__")):
        try:
            _shutil.rmtree(_pc)
        except Exception:
            pass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from main_window import GentleAdventuresApp
from utils.logger import init_logger
from utils.paths import app_root
from utils.settings import load_settings
from pretty_widgets.utils.fonts import register_app_fonts
from pretty_widgets.graphics.Theme import Theme as FamTheme
from pretty_widgets.utils.settings import init_watcher
from shared_braincell import is_singleton

# Singleton knock port — the suite convention (Intricate 47321, The Settlers
# 47322, Gentle Adventures 47323; instance_lock walks upward if taken). The
# port is accounted for in the edge port-surfaces registry (Compass.edge).
_INSTANCE_START_PORT = 47323


def _ring_fallback() -> None:
    """The changing-of-the-guard crash net (review 2026-07-23): when a fresh
    exe dies mid-boot AFTER a live incumbent yielded it the stage, nobody is
    left running — and the artifact most likely to be broken is exactly the
    untested new build. The BuildArchive ring's previous generation is the
    last-known-good understudy: spawn it detached so the stage is never left
    empty. One generation deep by design — the child carries GA_SWAP_FALLBACK
    so a broken previous can't chain the ring into a loop."""
    import os
    import subprocess
    if os.environ.get("GA_SWAP_FALLBACK"):
        return
    prev = (Path(os.environ.get("LOCALAPPDATA", "")) / "SingleSharedBraincell"
            / "BuildArchive" / "Gentle Adventures" / "Gentle Adventures_previous.exe")
    try:
        if prev.exists():
            from shared_braincell.console import DAEMON_FLAGS
            env = dict(os.environ, GA_SWAP_FALLBACK="1")
            subprocess.Popen([str(prev)], env=env, creationflags=DAEMON_FLAGS,
                             stdin=subprocess.DEVNULL, close_fds=True)
            print("Gentle Adventures — the fresh build fell mid-boot; the "
                  "previous generation steps in from the ring.")
    except Exception:
        pass   # the net must never add its own crash to the crash


def main() -> int:
    # Emergency dev interrupt: restore the OS-default SIGINT so Ctrl-C in the
    # launching shell hard-kills the app even while Qt's event loop holds the
    # GIL (Python signal handlers otherwise never get a turn). Mirrors Intricate.
    # A hard kill skips closeEvent's sweep — the startup purge above covers it.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app_dir = app_root()   # frozen-aware: next to the .exe, not inside _internal/
    init_logger(app_dir)
    settings = load_settings(app_dir / "settings.toml")

    # Singleton guard — handshake-validated, port-range fallback (the family
    # primitive; mirrors The Settlers). A duplicate launch is a SUMMONS, not a
    # no-op: it asks the primary to show itself (drained by a QTimer in the
    # window), so a second `python main.py` wakes a tray-hidden instance
    # instead of vanishing without a trace (2026-07-20 lifecycle review).
    # And since 2026-07-23 a FROZEN duplicate is a changing of the guard —
    # the build→exe swap: a fresh exe arriving while a live-python dev
    # instance holds the stage asks it to yield (the incumbent runs its full
    # exit ritual and the lock releases at its exit), then claims and boots.
    # Running a build inherently means switching to the exe; the systray
    # 'Live' action stays the deliberate door in the other direction. A
    # frozen incumbent just fronts itself — the ordinary duplicate case.
    took_the_helm = False   # set when a live incumbent yielded the stage to us
    if not is_singleton("Gentle Adventures", start_port=_INSTANCE_START_PORT):
        from shared_braincell import send_command
        frozen = bool(getattr(sys, "frozen", False))
        cmd = "frozen-arrival" if frozen else "show"
        delivered = send_command("Gentle Adventures", {"cmd": cmd},
                                 _INSTANCE_START_PORT)
        if frozen and delivered:
            # A live incumbent hands the stage key over IMMEDIATELY on
            # draining the command (it releases before its exit ritual), so a
            # yield lands within a second or two; a frozen twin keeps the
            # stage and fronts itself instead. The window is deliberately
            # SHORT: a hidden poller lingering after "twin kept the stage"
            # could bind a lock freed by a tray-Exit seconds later and
            # resurrect an app the user just dismissed (review 2026-07-23).
            import time
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                time.sleep(0.5)
                if is_singleton("Gentle Adventures", start_port=_INSTANCE_START_PORT):
                    print("Gentle Adventures — the live instance yielded the "
                          "stage; this fresh build takes the helm.")
                    took_the_helm = True
                    break
            else:
                print("Gentle Adventures is already sailing (a frozen twin "
                      "kept the stage) — asked her to come to the window.")
                return 0
        else:
            print("Gentle Adventures is already sailing — asked her to come to "
                  f"the window ({'heard' if delivered else 'no reply'}).")
            return 0

    # The boot tail rides inside the changing-of-the-guard crash net: when we
    # took the helm from a yielded incumbent, a death anywhere in here would
    # leave ZERO instances running (review 2026-07-23) — the ring's previous
    # generation steps in. A normal cold boot re-raises exactly as before.
    try:
        # Windows taskbar identity — bind the taskbar / jumplist / systray to our
        # own AUMID instead of the generic "Python" launcher. Mirrors The Majestic.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "SingleSharedBraincell.GentleAdventures")
        except Exception:
            pass

        app = QApplication(sys.argv)
        # Window + taskbar icon: the Play sticker, Gentle Adventures' brand mark,
        # sourced from the Iconic single-source set (GA Images/Icons retired).
        _app_icon = Path.home() / "Desktop" / "Iconic" / "Images" / "Stickers" / "Intricate" / "Play.ico"
        if _app_icon.exists():
            app.setWindowIcon(QIcon(str(_app_icon)))
        register_app_fonts()  # load Chandler42's full style table before any widget builds

        # Load the shared family Theme (colors + [theme.icons]) so the titlebar
        # icons resolve from the asset vault, and live-reload it when the shared
        # settings.toml changes — same wiring as the rest of the suite.
        # GA no longer keeps a repo-local icon folder (Images/Icons retired); every
        # icon single-sources from Iconic, so there's no app-local subfolder override.
        FamTheme.reload()
        _watcher = init_watcher()
        _watcher.changed.connect(FamTheme.reload)

        # Per-machine wake. The TV-role box (Sakura) autologins to a chromeless
        # desktop with no taskbar, so it has no visual "is it up yet?" cue — there
        # GA starts MAXIMIZED and its sleeping-captain wake scene IS the boot
        # heartbeat, overriding any --minimized the login shortcut still passes.
        # Machine awareness drives this now, not the flag (see identity.is_wake_display).
        from utils.identity import is_wake_display
        wake_display = is_wake_display()
        start_in_tray = ("--minimized" in sys.argv) and not wake_display
        window = GentleAdventuresApp(settings=settings, app_dir=app_dir,
                                     start_in_tray=start_in_tray)
        _watcher.changed.connect(window._reapply_theme)  # live palette ripple from The Settlers
        # --minimized (login autostart): live in the systray only, exactly like the
        # titlebar minimize button and The Settlers' autostart — no taskbar button,
        # the window comes back via the tray icon's click / Show.
        if start_in_tray:
            window.minimize_to_tray()
        elif wake_display:
            window.show()
            window.maximize_window()   # the wake spectacle, front and centre
            # Pull focus off the login taskbar so it can auto-hide again — claimed
            # now and re-claimed shortly after, since the shell can finish booting
            # (and grab focus for the Start button) after we first showed.
            from PySide6.QtCore import QTimer
            window.claim_foreground()
            QTimer.singleShot(1500, window.claim_foreground)
            QTimer.singleShot(6000, window.claim_foreground)
        else:
            window.show()
        return app.exec()
    except Exception:
        if took_the_helm:
            _ring_fallback()
        raise


if __name__ == "__main__":
    sys.exit(main())
