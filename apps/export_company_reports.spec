# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['export_company_reports.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('Database/*', 'Database'),               # include entire Database folder (users.json, configs, etc.)
        ('Fyrirtaeki/*', 'Fyrirtaeki'),           # shift logs folder
        ('logo.png', '.'),                        # any images or assets needed
        ('clockIn.png', '.'),
        ('stopButton.jpg', '.'),
    ],
    hiddenimports=collect_submodules('openpyxl'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='export_company_reports',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True  # True if you want console output; False hides console window
)
