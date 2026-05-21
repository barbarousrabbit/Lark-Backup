# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('core', 'core'), ('assets', 'assets')],
    hiddenimports=[
        'core.api_service', 'core.file_manager', 'core.network', 'core.notification',
        'core.process_manager', 'core.retry_manager', 'core.scheduler', 'config.config',
        'core.data_comparator', 'core.alert_window', 'core.report_generator',
        'requests', 'schedule', 'psutil', 'win10toast', 'openpyxl',
        'psutil._psutil_windows', 'psutil._psutil_posix', 'psutil._common',
        'requests.packages.urllib3', 'urllib3', 'certifi', 'charset_normalizer',
        'threading', 'datetime', 'time', 'os', 'sys', 'logging', 'json', 'socket',
        'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.reader.excel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'customtkinter', '_tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LarkBackup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\file_download.ico'],
)
