# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

def collect_folder_files(src_folder, target_folder):
    datas = []
    for root, dirs, files in os.walk(src_folder):
        for file in files:
            full_src = os.path.join(root, file)
            rel_path = os.path.relpath(full_src, src_folder)
            target = os.path.join(target_folder, rel_path)
            datas.append((full_src, target))
    return datas

project_root = os.path.abspath('.')
database_folder = os.path.join(project_root, 'Database')
database_datas = collect_folder_files(database_folder, 'Database')

database_datas = collect_folder_files(os.path.join(project_root, 'Database'), 'Database')

print("Collected files for bundling in Database:")
for src, tgt in database_datas:
    print(f"  {src} -> {tgt}")

a = Analysis(
    [os.path.join(project_root, 'apps', 'app.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'Resources', 'logo.png'), 'Resources'),
        (os.path.join(project_root, 'Resources', 'clockIn.png'), 'Resources'),
        (os.path.join(project_root, 'Resources', 'stopButton.jpg'), 'Resources'),
        (os.path.join(project_root, 'lib', 'dateandtime.py'), 'lib'),
    ] + database_datas,
    hiddenimports=collect_submodules('tktimepicker'),
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
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
