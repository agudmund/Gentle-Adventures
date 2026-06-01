#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - probe.py system-state checks the game uses to verify real-world steps
-The ship feels its own pulse and reports back, for Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

from __future__ import annotations

import logging
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("gentle")


def probe_npu() -> str | None:
    """Detect this machine's NPU and return a friendly engine descriptor — the
    'ship's engine' the game names — or None if no NPU is present.

    Strategy (dependency-free, built-in PowerShell — no wmi/pywin32):
      • The clean, vendor-neutral signal is the PnP class 'ComputeAccelerator':
        Windows files every NPU there regardless of vendor. (On this AMD
        Ryzen AI machine the device is 'NPU Compute Accelerator Device',
        service 'IpuMcdmDriver' — note: NOT 'amdipu', which varies by chip,
        so we match on class, not service name.)
      • A FriendlyName regex backstops it for any device that misses the class.
      • The CPU name supplies the vendor flavour (AMD XDNA / Intel AI Boost /
        Qualcomm Hexagon), since the NPU device name itself is generic.

    None on non-Windows or when no accelerator is enumerated.
    """
    if os.name != "nt":
        return None
    try:
        # Single-quoted PS strings + the -f format operator → no nested double
        # quotes to escape through subprocess. NPU name and CPU name come back
        # joined by '|||'.
        script = (
            "$d = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Class -eq 'ComputeAccelerator' -or "
            "$_.FriendlyName -match 'NPU|IPU|Neural|AI Engine|AI Boost|XDNA|Hexagon' } | "
            "Select-Object -First 1 -ExpandProperty FriendlyName; "
            "if (-not $d) { exit }; "
            "$c = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | "
            "Select-Object -First 1 -ExpandProperty Name; "
            "Write-Output ('{0}|||{1}' -f $d, $c)"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        out = result.stdout.strip()
        if not out:
            logger.debug("NPU probe: no compute-accelerator device present")
            return None
        npu_name, _, cpu_name = out.partition("|||")
        descriptor = _npu_descriptor(npu_name.strip(), cpu_name.strip())
        logger.info(f"NPU probe: {descriptor}  (device '{npu_name.strip()}')")
        return descriptor
    except Exception as e:
        logger.debug(f"NPU probe failed: {e}")
        return None


def _npu_descriptor(npu_name: str, cpu_name: str) -> str:
    """Build the engine descriptor from the NPU device + CPU vendor.

    The NPU's own FriendlyName is usually generic ('NPU Compute Accelerator
    Device'), so the CPU name is what reveals the silicon family.
    """
    cpu = cpu_name.lower()
    if "ryzen ai" in cpu:
        # 'Ryzen AI 3xx' is the 300-series branding — XDNA 2 silicon.
        return "AMD Ryzen AI — XDNA 2 NPU"
    if "amd" in cpu and "ryzen" in cpu:
        return "AMD Ryzen AI — XDNA NPU"
    if "intel" in cpu and ("ultra" in cpu or "core" in cpu):
        return "Intel AI Boost NPU"
    if "snapdragon" in cpu or "qualcomm" in cpu:
        return "Qualcomm Hexagon NPU"
    # Real accelerator, unrecognised vendor — fall back to the device name.
    return npu_name or "Neural Processing Unit"


def probe_lm_studio() -> bool:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "LM Studio" / "LM Studio.exe",
        Path(os.environ.get("ProgramFiles", "")) / "LM Studio" / "LM Studio.exe",
    ]
    return any(p.exists() for p in candidates if str(p))


def probe_local_api(url: str = "http://localhost:1234/v1/models", timeout: float = 1.5) -> bool:
    """Return True if an OpenAI-compatible local server (LM Studio etc.) is up."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False
