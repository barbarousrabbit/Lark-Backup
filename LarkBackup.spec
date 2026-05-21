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
        'requests', 'schedule', 'psutil', 'openpyxl',
        'psutil._psutil_windows', 'psutil._psutil_posix', 'psutil._common',
        'requests.packages.urllib3', 'urllib3', 'certifi', 'charset_normalizer',
        'threading', 'datetime', 'time', 'os', 'sys', 'logging', 'json', 'socket',
        'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.reader.excel',
        # windows-toasts + winrt namespace packages
        'windows_toasts',
        'windows_toasts.toast', 'windows_toasts.toasters', 'windows_toasts.wrappers',
        'windows_toasts.events', 'windows_toasts.toast_audio', 'windows_toasts.toast_document',
        'winrt', 'winrt._winrt', 'winrt.runtime', 'winrt.runtime._internals', 'winrt.system',
        'winrt.windows', 'winrt.windows.data', 'winrt.windows.data.xml', 'winrt.windows.data.xml.dom',
        'winrt.windows.foundation', 'winrt.windows.foundation.collections',
        'winrt.windows.ui', 'winrt.windows.ui.notifications',
        'winrt._winrt_windows_data_xml_dom', 'winrt._winrt_windows_foundation',
        'winrt._winrt_windows_foundation_collections', 'winrt._winrt_windows_ui_notifications',
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
