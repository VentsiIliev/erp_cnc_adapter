# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ERP-CNC Adapter.

Builds a single-file EXE that bundles the FastAPI application,
all src/ packages, and the version module.
"""

import os
import sys

block_cipher = None

# SPECPATH is the directory containing this .spec file (util_scripts/).
# Project root is one level up.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Icon for the EXE (use resources/logo.ico if available)
_icon_path = os.path.join(PROJECT_ROOT, 'resources', 'logo.ico')
ICON = _icon_path if os.path.exists(_icon_path) else None

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'src', 'update_worker.py'), 'src'),
        (os.path.join(PROJECT_ROOT, 'src', 'web', 'templates'), os.path.join('src', 'web', 'templates')),
        (os.path.join(PROJECT_ROOT, 'src', 'web', 'static'), os.path.join('src', 'web', 'static')),
        (os.path.join(PROJECT_ROOT, 'resources'), 'resources'),
    ],
    hiddenimports=[
        # FastAPI / Uvicorn internals that PyInstaller may miss
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # Application modules
        'src',
        'src.app',
        'src.core',
        'src.core.app_state',
        'src.core.config',
        'src.core.logging_config',
        'src.update_worker',
        'src.api',
        'src.api.cnc_start',
        'src.api.cnc_stop',
        'src.api.cnc_motion',
        'src.api.health',
        'src.api.job_load',
        'src.api.job_start',
        'src.api.job_status',
        'src.api.job_unload',
        'src.api.jog_pad_launcher',
        'src.api.update',
        'src.api.update_page',
        'src.api.schemas',
        'src.api.schemas.job',
        'src.api.schemas.update',
        'src.cnc',
        'src.cnc.cnc_client',
        'src.cnc.cnc_client_protocol',
        'src.cnc.connection_manager',
        'src.cnc.mock_cnc_client',
        'src.jog_pad',
        'src.jog_pad.jog_pad',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'version',
        # multipart form support
        'multipart',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='erp-cnc-adapter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

