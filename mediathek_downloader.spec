# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt6', 'requests', 'yt_dlp', 'yt_dlp.utils', 'yt_dlp.extractor', 'yt_dlp.downloader'],
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
    name='MediathekDownloader',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MediathekDownloader',
)

app = BUNDLE(
    coll,
    name='MediathekDownloader.app',
    icon=None,
    bundle_identifier='de.mediathek.downloader',
    info_plist={
        'CFBundleName': 'Mediathek Downloader',
        'CFBundleDisplayName': 'Mediathek Downloader',
        'CFBundleIdentifier': 'de.mediathek.downloader',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'MediathekDownloader',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
    },
)