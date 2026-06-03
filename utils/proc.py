#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - proc.py keep helper subprocesses off the desktop
-A console tool spawned from the windowed ship should never flash a window, For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

import os

# GA runs windowed (pythonw), so any console subprocess it spawns gets its OWN
# console window, flashing in the taskbar (the scene-2 NPU probe, the flm oracle
# and validate, ...). CREATE_NO_WINDOW suppresses that, keeping helpers as silent
# background tasks. Pass it as `creationflags=CREATE_NO_WINDOW`; it is 0 on
# non-Windows (subprocess accepts creationflags=0 on every platform), so the call
# site stays portable.
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
