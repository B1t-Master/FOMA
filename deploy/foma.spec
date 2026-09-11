# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FOMA.

Build onedir (default) or onefile (FOMA_ONEFILE=1) via deploy/build.ps1.
"""

import os
from pathlib import Path

root = Path(SPECPATH).parent
entry = str(root / "entry.py")

a = Analysis(
    [entry],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "foma.app",
        "foma.config",
        "foma.events",
        "foma.detection.base",
        "foma.detection.uia_detector",
        "foma.detection.screen_detector",
        "foma.engines.clicker",
        "foma.engines.orchestrator",
        "foma.engines.state",
        "foma.loggers.console_logger",
        "foma.loggers.jsonl_logger",
        "foma.telemetry.metrics",
        "uiautomation",
        "pynput",
        "psutil",
        "mss",
        "cv2",
        "numpy",
    ],
    excludes=["pytest", "mypy", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

onefile = os.environ.get("FOMA_ONEFILE") == "1"
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=onefile,  # exclude_binaries=False => single onedir exe? no: True splits
    name="foma",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)

coll = None
if not onefile:
    exe = EXE(
        pyz,
        a.scripts,
        # onedir: the launcher exe below has no binaries attached
        exclude_binaries=True,
        name="foma",
        debug=False,
        strip=False,
        upx=True,
        console=True,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="foma")