# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Pip — Pixel-Art Desktop Companion.

Build:
    cd companion/
    pyinstaller pip_companion.spec

Output:
    dist/pip-companion/   ← onedir bundle (used to make the AppImage)
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# ── Collect all PyQt6 Qt platform plugins and libraries ───────────────────────
qt_data = collect_data_files("PyQt6", subdir="Qt6/plugins")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=collect_dynamic_libs("PyQt6"),
    datas=[
        ("mcp_config.example.json", "."),
        *qt_data,
    ],
    hiddenimports=[
        # PyQt6 modules used at runtime
        "PyQt6.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        # pynput backends on Linux
        "pynput.keyboard._xorg",
        "pynput.mouse._xorg",
        "Xlib",
        "Xlib.display",
        "Xlib.ext",
        "Xlib.ext.record",
        "Xlib.protocol",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "email", "xml", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pip-companion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # no terminal window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="pip-companion",
)
