#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - logger.py simple file + console logger
-Every step is remembered, none for shame, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
from pathlib import Path


def init_logger(app_dir: Path) -> logging.Logger:
    logs_dir = app_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / "gentle.log"

    logger = logging.getLogger("gentle")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    logger.info("Gentle Adventures logger ready")
    return logger
