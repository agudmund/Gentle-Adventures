#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-Gentle Adventures - build.py build automation
-OneDir build with shared runtime junction and curated log output For Enjoying
-Built using a single shared braincell by Yours Truly and various Intelligences
"""

# Ported from The Settlers' build.py (the family's reference build pipeline):
# OneDir + shared-runtime junction (_internal -> ../_runtime) + curated log
# filter + 3-slot archive rotation + version-stamped Build Version.md, then a
# relaunch. Deltas vs Settlers: app name/icon, GA's hidden-import set (GA reads
# settings via stdlib tomllib so NO tomli_w; GA DOES use shared_braincell's
# gemini_image / llm / winenv submodules + QtMultimedia is unused), and the
# --version-file is optional (passed only if Documents/version_info.txt exists).
#
# IMPORTANT — runtime dependency: this build junctions _internal to the shared
# ../_runtime, so that runtime MUST already carry GA's deps. The shared runtime
# is rebuilt by ../_runtime/build_runtime.py; if GA introduces a dep the
# collector there doesn't import yet (e.g. shared_braincell.gemini_image / .llm
# / .winenv), add it to that collector and rebuild the runtime FIRST. See the
# "Build pipeline split" rule — touch both for bundled deps.

import shutil
import os
import sys
import re
import datetime
import subprocess
import hashlib
import json
from pathlib import Path
from send2trash import send2trash

# --- Configuration ---
appName      = "Gentle Adventures"
entryPoint   = "main.py"
iconsFolder  = "Images/Icons"
appIconFile  = "playIcon.ico"               # GA's brand mark (matches main.py's window/taskbar icon)
docsFolder   = str(Path("Documents") / "Build")

# Shared runtime — built by _runtime/build_runtime.py
_RUNTIME_DIR = Path(os.environ.get(
    "SingleSharedBraincell_Runtime",
    Path(__file__).parent.parent / "_runtime"
))


# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller log filter
# ─────────────────────────────────────────────────────────────────────────────
# Each tolerable pattern is explicitly silenced — never quietly. We count
# occurrences and surface them as "noted: <reason> (×N)" at the end of the
# build step.  Anything not in this list passes through unfiltered, so a
# genuinely new warning never gets buried in noise.
#
# (regex, swallow_continuation, count_label_or_None)
_TOLERABLE = [
    (re.compile(r"^\d+ INFO: (PyInstaller|Python|Platform|Python environment|wrote)\b"),
     False, None),
    (re.compile(r"WARNING: Disabling UPX for .+ due to CFG!"),
     False, "CFG-protected DLL skipped by UPX"),
    (re.compile(r"WARNING: Failed to upx strip on '.+'!"),
     True, "UPX NotCompressibleException (DLL already optimal)"),
    (re.compile(r"WARNING: Output from upx command:"),
     True, None),
    (re.compile(r"WARNING: Execution of '\w+' failed on attempt #\d+ / \d+:"),
     False, "Defender lock retry on EXE write"),
]
_PYINSTALLER_LINE = re.compile(r"^\d+\s+(INFO|WARNING|ERROR|DEBUG|CRITICAL):")


class _LogFilter:
    """Streams PyInstaller output through the tolerable-pattern allowlist.

    Anything matching the allowlist is counted and silenced; everything
    else passes through unchanged. Tally is exposed via .summary() for
    the post-build report.
    """

    def __init__(self):
        self._swallowing = False
        self._counts: dict[str, int] = {}

    def feed(self, line: str) -> str | None:
        """Returns the line to print, or None to drop it silently."""
        if self._swallowing:
            if _PYINSTALLER_LINE.match(line):
                self._swallowing = False
            else:
                return None  # continuation of the swallowed warning

        for pattern, multi, label in _TOLERABLE:
            if pattern.search(line):
                if label is not None:
                    self._counts[label] = self._counts.get(label, 0) + 1
                if multi:
                    self._swallowing = True
                return None

        return line

    def summary(self) -> list[str]:
        """One-line-per-pattern summary of what was silenced."""
        return [f"noted - {label} (x{count})"
                for label, count in self._counts.items()]


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def killRunningInstance() -> bool:
    """taskkill the running app if autostart fired it before this build.
    Returns True iff something was actually killed."""
    result = subprocess.run(
        ["taskkill", "/IM", f"{appName}.exe", "/F"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


class BuildManager:
    """Utility to handle build rotations, documentation, and forensic hashing."""

    exeName = f"{appName}.exe"
    prevExe = f"{appName}_previous.exe"
    archExe = f"{appName}_archive.exe"

    docName = "Build Version.md"
    prevDoc = "Build Version Previous.md"
    archDoc = "Build Version Archive.md"

    @classmethod
    def getFileHash(cls, filePath: Path) -> str:
        if not filePath.exists():
            return "n/a (new build)"
        sha256Hash = hashlib.sha256()
        with open(filePath, "rb") as f:
            for byteBlock in iter(lambda: f.read(4096), b""):
                sha256Hash.update(byteBlock)
        return sha256Hash.hexdigest()[:16]

    @classmethod
    def rotateAndArchive(cls, root: Path):
        archiveDir = root / "archive"
        ensure_dir(archiveDir)
        docsDir = root / docsFolder
        ensure_dir(docsDir)

        currentExeFile = root / cls.exeName
        oldHash = cls.getFileHash(currentExeFile)

        rotationSummary = []

        prevExeFile = archiveDir / cls.prevExe
        archExeFile = archiveDir / cls.archExe

        if archExeFile.exists():
            send2trash(str(archExeFile))

        if prevExeFile.exists():
            prevExeFile.rename(archExeFile)
            rotationSummary.append(f"archive/{cls.prevExe} -> archive/{cls.archExe}")

        if currentExeFile.exists():
            try:
                currentExeFile.rename(prevExeFile)
                rotationSummary.append(f"{cls.exeName} -> archive/{cls.prevExe}")
            except PermissionError:
                return None, []

        currentDocFile = docsDir / cls.docName
        prevDocFile    = docsDir / cls.prevDoc
        archDocFile    = docsDir / cls.archDoc

        if archDocFile.exists():
            send2trash(str(archDocFile))

        if prevDocFile.exists():
            prevDocFile.rename(archDocFile)
            rotationSummary.append(f"{docsFolder}/{cls.prevDoc} -> {docsFolder}/{cls.archDoc}")

        if currentDocFile.exists():
            currentDocFile.rename(prevDocFile)
            rotationSummary.append(f"{docsFolder}/{cls.docName} -> {docsFolder}/{cls.prevDoc}")

        return oldHash, rotationSummary

    @classmethod
    def updateVersionMarkdown(cls, root: Path, newHash: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d - %H:%M")
        content = (
            f"# Build Version\n\n"
            f"**Timestamp:** `{timestamp}`\n"
            f"**Signature:** `{newHash}`\n"
            f"**Status:** `Stable Daily Build`\n"
        )
        docsPath = root / docsFolder
        with open(docsPath / cls.docName, "w", encoding="utf-8") as f:
            f.write(content)
        return timestamp

    @classmethod
    def finalizeAndCleanup(cls, root: Path) -> tuple[str, str]:
        """Move thin exe from dist/ to project root, create runtime junction.
        Returns (newHash, junction_target_str)."""
        distFolder  = root / "dist"
        buildFolder = root / "build"
        onedirFolder = distFolder / appName
        newExePath   = onedirFolder / cls.exeName

        newHash = "unknown"
        if newExePath.exists():
            newHash = cls.getFileHash(newExePath)
            dest = root / cls.exeName
            if dest.exists():
                send2trash(str(dest))
            shutil.move(str(newExePath), str(dest))

        internal = root / "_internal"
        if internal.exists():
            subprocess.run(["cmd", "/c", "rmdir", str(internal)],
                           capture_output=True)
            if internal.exists():
                shutil.rmtree(internal)
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(internal), str(_RUNTIME_DIR)],
            check=True, capture_output=True,
        )
        # Born hidden — _internal is build plumbing, never browsed by hand.
        # /L sets the attribute on the junction itself, not the target.
        subprocess.run(["attrib", "+h", str(internal), "/L"], capture_output=True)

        for folder in [buildFolder, distFolder]:
            if folder.exists():
                try:
                    send2trash(str(folder))
                except Exception:
                    pass

        return newHash, str(_RUNTIME_DIR)


def runPyInstaller(projectRoot: Path, args: list[str], log_path: Path) -> tuple[int, _LogFilter]:
    """Streams PyInstaller through the log filter. Saves full unfiltered
    output to log_path for forensics. Returns (exit_code, filter)."""
    flt = _LogFilter()
    cmd = [sys.executable, "-m", "PyInstaller", *args, "--log-level=WARN"]
    with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(projectRoot),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            logf.write(line + "\n")
            shown = flt.feed(line)
            if shown is not None:
                print(f"      {shown}")
        proc.wait()
    return proc.returncode, flt


def buildApp(launch: bool = True):
    projectRoot = Path(__file__).parent.absolute()
    pyinstaller_log = projectRoot / docsFolder / "last_build.log"
    ensure_dir(pyinstaller_log.parent)

    print(f"\nBuilding {appName} (onedir + shared runtime)\n")

    # ── [1/6] Validate shared runtime ────────────────────────────────────
    print("[1/6] Validate shared runtime")
    if not (_RUNTIME_DIR / "PySide6").is_dir():
        print(f"      ERROR - shared runtime not found at {_RUNTIME_DIR}")
        print(f"              run _runtime/build_runtime.py first.")
        return 1
    manifest_path = _RUNTIME_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(f"      ok - PySide6 {manifest.get('PySide6', '?')}, "
              f"pretty_widgets {manifest.get('pretty_widgets', '?')}, "
              f"hash {manifest.get('hash', '?')}")
    else:
        print("      ok - runtime present (no manifest)")

    # ── [2/6] Stop running instance ──────────────────────────────────────
    print("[2/6] Stop running instance")
    if killRunningInstance():
        print(f"      ok - terminated {appName}.exe (was running)")
    else:
        print(f"      ok - no running instance")

    # ── [3/6] Rotate archives ────────────────────────────────────────────
    print("[3/6] Rotate archives")
    rotation = BuildManager.rotateAndArchive(projectRoot)
    if rotation == (None, []):
        print(f"      ERROR - {appName}.exe is locked; taskkill should have caught this")
        return 1
    previousSignature, rotationLogs = rotation
    if rotationLogs:
        for log in rotationLogs:
            print(f"      ok - {log}")
    else:
        print("      ok - nothing to rotate (first build)")

    # ── [4/6] Build via PyInstaller ──────────────────────────────────────
    print("[4/6] Build via PyInstaller")
    print(f"      streaming - full log at {pyinstaller_log.relative_to(projectRoot)}")
    appIcon     = projectRoot / iconsFolder / appIconFile
    versionInfo = projectRoot / "Documents" / "version_info.txt"
    pyinstaller_args = [
        entryPoint,
        f"--name={appName}",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={appIcon}",
        # GA Qt surface (frameless window + scene view) — three modules only.
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        # Shared widget kit.
        "--hidden-import=pretty_widgets",
        "--hidden-import=pretty_widgets.graphics.Theme",
        "--hidden-import=pretty_widgets.utils.settings",
        "--hidden-import=pretty_widgets.utils.fonts",
        "--hidden-import=pretty_widgets.PrettyButton",
        "--hidden-import=pretty_widgets.PrettyLabel",
        "--hidden-import=pretty_widgets.PrettyCombo",
        "--hidden-import=pretty_widgets.PrettyTooltip",
        # Shared braincell — GA uses settings + logger + Gemini image gen +
        # the text LLM client + the NPU/winenv probe. (No tomli_w: GA reads
        # settings via stdlib tomllib.)
        "--hidden-import=shared_braincell",
        "--hidden-import=shared_braincell.settings",
        "--hidden-import=shared_braincell.logger",
        "--hidden-import=shared_braincell.gemini_image",
        "--hidden-import=shared_braincell.llm",
        "--hidden-import=shared_braincell.winenv",
        "--hidden-import=leopold",
        # GA is pure Qt — keep pygame out even if it's installed in the env
        # for sibling apps (see the family's pygame-hook-trap note).
        "--exclude-module=pygame",
    ]
    if versionInfo.exists():
        pyinstaller_args.append(f"--version-file={versionInfo}")
    else:
        print("      note - Documents/version_info.txt absent; building without "
              "embedded version resource")
    rc, flt = runPyInstaller(projectRoot, pyinstaller_args, pyinstaller_log)
    if rc != 0:
        print(f"      ERROR - PyInstaller exited with code {rc}")
        return rc
    notes = flt.summary()
    if notes:
        for note in notes:
            print(f"      {note}")
    print("      ok - bundle built")

    # ── [5/6] Promote artifact ───────────────────────────────────────────
    print("[5/6] Promote artifact")
    newSignature, junctionTarget = BuildManager.finalizeAndCleanup(projectRoot)
    print(f"      ok - {appName}.exe at project root")
    print(f"      ok - junction _internal -> {junctionTarget}")

    # ── [6/6] Document build ─────────────────────────────────────────────
    print("[6/6] Document build")
    buildTime = BuildManager.updateVersionMarkdown(projectRoot, newSignature)
    print(f"      ok - signature {newSignature}")
    print(f"      ok - timestamp {buildTime}")

    # ── Finish ───────────────────────────────────────────────────────────
    print()
    print(f"Build complete - {appName}.exe (was {previousSignature})")

    finalExe = projectRoot / f"{appName}.exe"
    if finalExe.exists():
        os.utime(str(finalExe))
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
        if launch:
            subprocess.Popen([str(finalExe)])
            print(f"Launched - check tray for {newSignature}")
        else:
            print()
            print("  " + "=" * 62)
            print(f"  ** NEW BUILD: {appName}  ({newSignature})")
            print(f"  ** RESTART {appName} to load it - any running instance is")
            print(f"  ** still the OLD build until you close and reopen it.")
            print("  " + "=" * 62)
    return 0


if __name__ == "__main__":
    # --no-launch: build but don't pop the window (used by Compass.build during
    # install, where launching every freshly-built app would be chaos). The loud
    # restart banner above stands in for the launch.
    sys.exit(buildApp(launch="--no-launch" not in sys.argv))
