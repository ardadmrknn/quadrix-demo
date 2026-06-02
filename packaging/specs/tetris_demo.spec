# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Demo - PyInstaller Windows spec.

Result: dist/QuadrixDemo.exe
"""

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
def _write_runtime_appid_from_source(source_file: Path, variant: str) -> str:
    runtime_dir = REPO_ROOT / 'build' / 'pyinstaller_runtime' / variant
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / 'steam_appid.txt'
    runtime_value = source_file.read_text(encoding='utf-8').strip()
    runtime_file.write_text(f'{runtime_value}\n', encoding='utf-8')
    return str(runtime_file)
write_embedded_layout_module(REPO_ROOT)

block_cipher = None
RUNTIME_STEAM_APPID = _write_runtime_appid_from_source(DEMO_APPID_SOURCE, 'demo_windows')

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

try:
    import setuptools as _st
    _jaraco_dir = Path(_st.__file__).resolve().parent / '_vendor' / 'jaraco' / 'text'
    _lorem = _jaraco_dir / 'Lorem ipsum.txt'
    if _lorem.exists():
        datas.append((str(_lorem), str(Path('setuptools') / '_vendor' / 'jaraco' / 'text')))
except Exception as _e:
    print(f'[spec] Lorem ipsum.txt eklenemedi: {_e}')

hiddenimports = [
    'pygame',
    'pygame._sdl2',
    'pygame._sdl2.video',
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
    'steam_integration',
    'steam_net_bridge',
    'version',
    'version_base',
]

for py_file in SRC_DIR.glob('*.py'):
    module_name = py_file.stem
    if module_name not in {'__init__', 'version_local_windows'}:
        hiddenimports.append(module_name)

for subdir in ['renderers', 'types']:
    subdir_path = SRC_DIR / subdir
    if subdir_path.exists():
        for py_file in subdir_path.glob('*.py'):
            hiddenimports.append(f'{subdir}.{py_file.stem}')

campaign_dir = SRC_DIR / 'campaign'
if campaign_dir.exists():
    hiddenimports.append('campaign')
    for py_file in campaign_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'campaign.{module_name}')

# ── pygame._sdl2 (SDL2 donanım renderer / Steam overlay backend) ──
# PyInstaller'ın pygame için yerleşik hook'u YOKTUR; bu yüzden _sdl2 alt
# modüllerini (video, sdl2, window vb. C-extension .pyd dosyaları) ve onların
# bağımlı SDL2 DLL'lerini AÇIKÇA toplamamız gerekir. Aksi halde frozen build'de
# `import pygame._sdl2.video` başarısız olur ve SDL2 overlay backend hiç çalışmaz.
try:
    from PyInstaller.utils.hooks import collect_submodules as _collect_submodules
    _sdl2_submods = _collect_submodules('pygame._sdl2')
    for _m in _sdl2_submods:
        if _m not in hiddenimports:
            hiddenimports.append(_m)
    print(f'[spec] pygame._sdl2 submodulleri eklendi: {_sdl2_submods}')
except Exception as _sdl2_exc:
    print(f'[spec] UYARI: pygame._sdl2 submodul toplama basarisiz: {_sdl2_exc}')
    for _m in ('pygame._sdl2', 'pygame._sdl2.video', 'pygame._sdl2.sdl2',
               'pygame._sdl2.window', 'pygame._sdl2.audio', 'pygame._sdl2.controller',
               'pygame._sdl2.mixer', 'pygame._sdl2.touch'):
        if _m not in hiddenimports:
            hiddenimports.append(_m)


steam_dll_src = str(REPO_ROOT / 'dll' / 'win64' / 'steam_api64.dll')
if os.path.exists(steam_dll_src):
    binaries = [(steam_dll_src, '.')]
else:
    binaries = []

steam_dylib_src = str(REPO_ROOT / 'dll' / 'osx' / 'libsteam_api.dylib')
if os.path.exists(steam_dylib_src):
    binaries.append((steam_dylib_src, '.'))

_bridge_matches = get_bridge_binaries(REPO_ROOT)
if _bridge_matches:
    binaries.append((_bridge_matches[0], '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_matches[0]}')
else:
    print('[spec] UYARI: steam_net_bridge bulunamadi')

_mingw_dlls = ['libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libwinpthread-1.dll']
_mingw_dir = REPO_ROOT / 'dll' / 'win64'
for _dll_name in _mingw_dlls:
    _dll_path = _mingw_dir / _dll_name
    if _dll_path.exists():
        binaries.append((str(_dll_path), '.'))


# pygame._sdl2 C-extension (.pyd) dosyalari + pygame SDL2 DLL'leri.
# hiddenimports tek basina .pyd'leri fiziksel olarak KOPYALAMAYABILIR (pygame hook'u yok),
# bu yuzden hem _sdl2 .pyd'lerini hem pygame'in dinamik kutuphanelerini acikca topluyoruz.
try:
    import pygame as _pg_mod
    _pg_dir = Path(_pg_mod.__file__).resolve().parent
    _sdl2_dir = _pg_dir / '_sdl2'
    if _sdl2_dir.exists():
        for _pyd in _sdl2_dir.glob('*.pyd'):
            binaries.append((str(_pyd), os.path.join('pygame', '_sdl2')))
            print(f'[spec] pygame._sdl2 .pyd eklendi: {_pyd.name}')
        for _so in _sdl2_dir.glob('*.so'):
            binaries.append((str(_so), os.path.join('pygame', '_sdl2')))
    try:
        from PyInstaller.utils.hooks import collect_dynamic_libs as _cdl
        _pg_libs = _cdl('pygame')
        if _pg_libs:
            binaries.extend(_pg_libs)
            print(f'[spec] pygame dinamik kutuphaneleri eklendi: {len(_pg_libs)} adet')
    except Exception as _pg_lib_exc:
        print(f'[spec] UYARI: pygame dinamik kutuphane toplama basarisiz: {_pg_lib_exc}')
except Exception as _sdl2_bin_exc:
    print(f'[spec] UYARI: pygame._sdl2 .pyd toplama basarisiz: {_sdl2_bin_exc}')

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
        'tkinter',
        '_tkinter',
        'tkinter.colorchooser',
        'tkinter.filedialog',
        'tkinter.simpledialog',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuadrixDemo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=str(REPO_ROOT / 'assets' / 'quadrix_icon.ico'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)