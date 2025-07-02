# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.datastruct import Tree

block_cipher = None

project_root = os.path.abspath('.')

database_tree = Tree(os.path.join(project_root, 'Database'), prefix='Database')

a = Analysis(
    ['apps/admin_view.py'],  # main script for admin view app
    pathex=[project_root],
    binaries=[],
    datas=[
        ('Resources/logo.png', 'Resources'),
        ('Resources/clockIn.png', 'Resources'),
        ('Resources/stopButton.jpg', 'Resources'),
        ('lib/dateandtime.py', 'lib'),
        database_tree,
    ],
    hiddenimports=collect_submodules('tktimepicker'),  # keep or adjust imports if admin_view uses others
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ShiftAdminView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False  # GUI app, no console window
)
