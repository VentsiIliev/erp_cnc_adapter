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
        'src.app_state',
        'src.config',
        'src.logging_config',
        'src.update_worker',
        'src.handlers',
        'src.handlers.cnc_start',
        'src.handlers.cnc_stop',
        'src.handlers.health',
        'src.handlers.job_load',
        'src.handlers.job_start',
        'src.handlers.job_status',
        'src.handlers.update',
        'src.handlers.update_page',
        'src.schemas',
        'src.schemas.job',
        'src.schemas.update',
        'src.services',
        'src.services.cnc_client',
        'src.services.cnc_client_protocol',
        'src.services.connection_manager',
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
    upx=True,
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
