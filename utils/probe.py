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
import shutil
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


def probe_gpu() -> str | None:
    """This machine's GPU name(s), joined — or None off Windows / on failure.
    Clones probe_npu's dependency-free PowerShell idiom (Win32_VideoController)."""
    if os.name != "nt":
        return None
    try:
        script = (
            "(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty Name) -join '; '"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=8,
        )
        out = result.stdout.strip()
        return out or None
    except Exception as e:
        logger.debug(f"GPU probe failed: {e}")
        return None


def raw_hardware_spec() -> dict:
    """Gather RAW hardware strings (CPU / GPU / NPU device names, RAM in GB) —
    distinct from probe_npu's *friendly* descriptor. This is what the Hardware
    Oracle sends up to the text model so it can speak about the actual silicon.
    Returns {} off Windows or on failure (the Oracle is cosmetic — never blocks).
    """
    if os.name != "nt":
        return {}
    try:
        # All single-quoted PS strings + the -f operator (no nested double quotes
        # to escape), matching probe_npu's style. One call gathers everything.
        script = (
            "$cpu = (Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | "
            "Select-Object -First 1 -ExpandProperty Name); "
            "$gpu = ((Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty Name) -join '; '); "
            "$npu = (Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Class -eq 'ComputeAccelerator' -or "
            "$_.FriendlyName -match 'NPU|IPU|Neural|AI Engine|AI Boost|XDNA|Hexagon' } | "
            "Select-Object -First 1 -ExpandProperty FriendlyName); "
            "$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem "
            "-ErrorAction SilentlyContinue).TotalPhysicalMemory / 1GB); "
            "Write-Output ('CPU={0}' -f $cpu); Write-Output ('GPU={0}' -f $gpu); "
            "Write-Output ('NPU={0}' -f $npu); Write-Output ('RAM={0}' -f $ram)"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=10,
        )
        spec: dict = {}
        for line in result.stdout.splitlines():
            key, sep, val = line.strip().partition("=")
            if sep and val.strip():
                spec[key.strip().lower()] = val.strip()
        logger.info(f"hardware spec: {spec}")
        return spec
    except Exception as e:
        logger.debug(f"hardware spec probe failed: {e}")
        return {}


def probe_fastflowlm() -> bool:
    """True if FastFlowLM (the `flm` NPU runtime) is installed — detected via the
    flm CLI on PATH, with a couple of known install locations as backup. This is
    the genuine 'oracle on the NPU' tool scene 04 summons."""
    if shutil.which("flm"):
        return True
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "FastFlowLM" / "flm.exe",
        Path(os.environ.get("ProgramFiles", "")) / "FastFlowLM" / "flm.exe",
    ]
    return any(p.exists() for p in candidates if str(p))


def probe_local_api(url: str = "http://localhost:1234/v1/models", timeout: float = 1.5) -> bool:
    """Return True if an OpenAI-compatible local server (LM Studio etc.) is up."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False
