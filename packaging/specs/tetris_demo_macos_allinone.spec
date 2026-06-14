# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Demo - macOS all-in-one app bundle.

Result: dist/Quadrix Demo.app
"""

import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault('STEAM_APP_ID', '4635310')

REPO_ROOT = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.bridge_artifacts import get_bridge_binaries
from tools.embed_menu_layout import write_embedded_layout_module

SRC_DIR = REPO_ROOT / 'src'
DEMO_APPID_SOURCE = REPO_ROOT / 'config' / 'runtime' / 'steam_appid_demo.txt'


def _load_version_string(version_file: Path) -> str:
    spec = importlib.util.spec_from_file_location('version_base_spec', version_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'version modulu yuklenemedi: {version_file}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(getattr(module, 'VERSION'))


def _write_runtime_appid_from_source(source_file: Path, variant: str) -> str:
    runtime_dir = REPO_ROOT / 'build' / 'pyinstaller_runtime' / variant
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / 'steam_appid.txt'
    runtime_value = source_file.read_text(encoding='utf-8').strip()
    runtime_file.write_text(f'{runtime_value}\n', encoding='utf-8')
    return str(runtime_file)


APP_VERSION = _load_version_string(SRC_DIR / 'version_base.py')
write_embedded_layout_module(REPO_ROOT)

block_cipher = None
RUNTIME_STEAM_APPID = _write_runtime_appid_from_source(DEMO_APPID_SOURCE, 'demo_macos')

datas = [
    (str(REPO_ROOT / 'assets'), 'assets'),
    (str(REPO_ROOT / 'music'), 'music'),
    (str(REPO_ROOT / 'backgrounds'), 'backgrounds'),
    (str(REPO_ROOT / 'avatars'), 'avatars'),
    (str(REPO_ROOT / 'font'), 'font'),
    (str(REPO_ROOT / 'campaign_levels.csv'), '.'),
    (RUNTIME_STEAM_APPID, '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'menu_layout_runtime.json'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'credits_layout.json'), '.'),
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'assets'), 'src/assets'),
    (str(SRC_DIR / 'settings.json'), 'src'),
    (str(SRC_DIR / 'localization_auto_overrides.json'), 'src'),
]

datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

try:
    import pygame as _pg
    _freesans = Path(_pg.__file__).resolve().parent / 'freesansbold.ttf'
    if _freesans.exists():
        datas.append((str(_freesans), 'pygame'))
except Exception as _e:
    print(f'[spec] freesansbold.ttf eklenemedi: {_e}')

hiddenimports = [
    'PIL',
    'PIL.Image',
    'PIL.ImageSequence',
    'PIL.GifImagePlugin',
    'PIL.PngImagePlugin',
    'pygame',
    'pygame.mixer',
    'pygame.font',
    'pygame.image',
    'pygame.transform',
    'pygame.display',
    'pygame.event',
    'pygame.time',
    'pygame.draw',
    'pygame.surface',
    'pygame.rect',
    'pygame.color',
    'pygame.key',
    'pygame.mouse',
    'pygame.cursors',
    'pygame.locals',
    'pygame.sprite',
    'pygame.math',
    'pygame.gfxdraw',
    'pygame.freetype',
    'pygame.scrap',
    'pygame.pixelcopy',
    'json',
    'csv',
    'pathlib',
    'platform',
    'random',
    'time',
    'datetime',
    'math',
    'copy',
    'collections',
    'functools',
    'threading',
    'os',
    'sys',
    'typing',
    'array',
    'shutil',
    'subprocess',
    'importlib',
    'importlib.util',
    'hashlib',
    'io',
    'struct',
    'traceback',
    'logging',
    'enum',
    'dataclasses',
    'itertools',
    'operator',
    're',
    'string',
    'textwrap',
    'urllib',
    'urllib.request',
    'http',
    'http.client',
    'socket',
    'ssl',
    'contextlib',
    'abc',
    'weakref',
    'xml',
    'xml.etree',
    'xml.etree.ElementTree',
    'plistlib',
    'jaraco',
    'jaraco.text',
    'jaraco.functools',
    'jaraco.context',
    'more_itertools',
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'packaging.markers',
    'platformdirs',
    'zipp',
    'steam_net_bridge',
    'version',
    'version_base',
]

for py_file in SRC_DIR.glob('*.py'):
    module_name = py_file.stem
    if module_name not in {'__init__', 'version_local_windows'}:
        hiddenimports.append(module_name)

campaign_dir = SRC_DIR / 'campaign'
if campaign_dir.exists():
    hiddenimports.append('campaign')
    for py_file in campaign_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'campaign.{module_name}')

renderers_dir = SRC_DIR / 'renderers'
if renderers_dir.exists():
    hiddenimports.append('renderers')
    for py_file in renderers_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'renderers.{module_name}')

types_dir = SRC_DIR / 'types'
if types_dir.exists():
    hiddenimports.append('types')
    for py_file in types_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'types.{module_name}')

steam_dylib_src = str(REPO_ROOT / 'dll' / 'osx' / 'libsteam_api.dylib')
if os.path.exists(steam_dylib_src):
    binaries = [(steam_dylib_src, '.')]
else:
    binaries = []

_bridge_matches = get_bridge_binaries(REPO_ROOT)
if _bridge_matches:
    binaries.append((_bridge_matches[0], '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_matches[0]}')
else:
    print('WARNING: steam_net_bridge not found - Online PvP calismayacak!')

a = Analysis(
    [str(SRC_DIR / 'main.py')],
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(REPO_ROOT / 'packaging' / 'pyinstaller' / 'hooks' / 'pyi_rth_quadrix_data.py')],
    excludes=[
        'matplotlib',
        'numpy',
        'pygame.surfarray',
        'pandas',
        'scipy',
        'cv2',
        'tensorflow',
        'torch',
        'sklearn',
        'IPython',
        'notebook',
        'jupyter',
        'tkinter',
        'PyQt5',
        'PySide2',
        'PySide6',
        'PyQt6',
        'xmlrpc',
        'unittest',
        'doctest',
        'pdb',
        'profile',
        'pydoc',
        'lib2to3',
        'distutils',
        'setuptools',
        'pip',
        'ensurepip',
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
    name='QuadrixDemo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_ROOT / 'assets' / 'Tetris.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='QuadrixDemo',
)

app = BUNDLE(
    coll,
    name='Quadrix Demo.app',
    icon=str(REPO_ROOT / 'assets' / 'Tetris.icns'),
    bundle_identifier='com.burakyasayan.quadrix.demo',
    version=APP_VERSION,
    info_plist={
        'CFBundleName': 'Quadrix Demo',
        'CFBundleDisplayName': 'Quadrix Demo',
        'CFBundleGetInfoString': 'Quadrix Demo - Steam Demo',
        'CFBundleIdentifier': 'com.burakyasayan.quadrix.demo',
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleExecutable': 'QuadrixDemo',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'QDRX',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSMinimumSystemVersion': '11.0',
        'LSApplicationCategoryType': 'public.app-category.games',
        'NSHumanReadableCopyright': '(c) 2026 Burak Yasayan. All rights reserved.',
        'NSDocumentsFolderUsageDescription': 'Quadrix Demo uses this to save game data.',
        'NSMicrophoneUsageDescription': 'This app does not access the microphone.',
        'NSAllowsArbitraryLoads': True,
        'LSBackgroundOnly': False,
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
    },
)