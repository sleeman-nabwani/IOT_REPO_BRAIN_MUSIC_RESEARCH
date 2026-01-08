# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for Brain Music Sync.
This compiles the Python application into a Windows executable.
"""

import os

# Since this spec is in setup/, we need to reference the project root
project_root = os.path.dirname(SPECPATH)

block_cipher = None

# Analysis: Collect all dependencies
a = Analysis(
    [os.path.join(project_root, 'server/gui_app.py')],
    pathex=[],
    binaries=[],
    datas=[
        # No need to bundle MIDI files - they'll be external and writable
        # Include one default base model (optional)
        (os.path.join(project_root, 'research/LightGBM/results/models/lgbm_model.joblib'), 'research/LightGBM/results/models'),
    ],
    hiddenimports=[
        # Scikit-learn internals (required for LightGBM/Ridge)
        'sklearn.utils._cython_blas',
        'sklearn.neighbors.typedefs',
        'sklearn.neighbors.quad_tree',
        'sklearn.tree._utils',
        'sklearn.utils._weight_vector',
        # ML libraries
        'lightgbm',
        'lightgbm.sklearn',
        'optuna',
        'optuna.storages',
        # MIDI support
        'mido',
        'mido.backends',
        'mido.backends.rtmidi',
        'rtmidi',
        # Data science stack
        'pandas',
        'numpy',
        'matplotlib',
        'matplotlib.backends',
        'matplotlib.backends.backend_tkagg',
        # Serial communication
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        # Standard library (sometimes missed)
        'queue',
        'threading',
        'subprocess',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'pytest',
        'IPython',
        'jupyter',
        'sphinx',
        'notebook',
    ],
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
    name='BrainMusicSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, 'App.ico'),  # Custom app icon (same dir as spec)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BrainMusicSync',
)

