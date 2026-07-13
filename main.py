#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - main.py application bootstrap
-The captain wakes and the bridge hums anew, for Enjoying
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
    # primitive; mirrors The Settlers). Silent exit if a Gentle Adventures is
    # already running, so a double/quintuple-clicked launcher opens one app.
    if not is_singleton("Gentle Adventures", start_port=_INSTANCE_START_PORT):
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
