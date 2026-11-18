# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Base directory
BASE_DIR = os.path.abspath(SPECPATH)

# Collect data files from packages that need internal assets
customtkinter_datas = collect_data_files('customtkinter')
reportlab_datas = collect_data_files('reportlab')

# Project assets and sample files
datas = [
    (os.path.join(BASE_DIR, 'assets'), 'assets'),
    (os.path.join(BASE_DIR, 'samples'), 'samples'),
    (os.path.join(BASE_DIR, 'custom_positions.json'), '.'),
] + customtkinter_datas + reportlab_datas

# Hidden imports to ensure win32, pystray, and GUI submodules are included
hiddenimports = [
    'customtkinter',
    'pystray',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL._tkinter_finder',
    'reportlab',
    'reportlab.pdfgen.canvas',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
    'reportlab.pdfbase.pdfmetrics',
    'reportlab.pdfbase.ttfonts',
    'openpyxl',
    'win32gui',
    'win32con',
    'win32ui',
    'win32print',
    'path_utils',
    'config',
    'database',
    'renderer',
    'printer',
    'batch_processor',
    'tray_manager',
    'version',
    'updater',
] + collect_submodules('customtkinter')

a = Analysis(
    ['app.py'],
    pathex=[BASE_DIR],
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
    name='CertificateStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE_DIR, 'assets', 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CertificateStudio',
)
