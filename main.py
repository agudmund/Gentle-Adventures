#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - main.py application bootstrap
-The captain wakes and the bridge hums anew, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from main_window import GentleAdventuresApp
from utils.logger import init_logger
from utils.settings import load_settings


def main() -> int:
    app_dir = Path(__file__).resolve().parent
    init_logger(app_dir)
    settings = load_settings(app_dir / "settings.toml")

    app = QApplication(sys.argv)
    window = GentleAdventuresApp(settings=settings, app_dir=app_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
