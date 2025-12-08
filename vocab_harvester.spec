# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

import de_core_news_sm

project_root = Path(__file__).resolve().parent
model_dir = Path(de_core_news_sm.__file__).parent


def _data(source, target):
    """Helper to add data tuples only when they exist."""
    return [(str(source), target)] if source.exists() else []


datas = []

# Bundle spaCy model
datas += _data(model_dir, "de_core_news_sm")

# Bundle irregular verbs list
datas += _data(project_root / "data" / "irregular_Verbs.txt", "data")

# Bundle existing database folder (will create if missing at runtime)
database_file = project_root / "database" / "vocab.db"
datas += _data(database_file, "database")

hiddenimports = collect_submodules("spacy")

block_cipher = None


a = Analysis(
    ["src/ui/main.py"],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VocabHarvester",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VocabHarvester",
)
