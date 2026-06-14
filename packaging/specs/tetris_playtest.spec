# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - PyInstaller Spec Dosyası (Steam Playtest)
Playtest AppID: 4428040

Kullanım:
    python -m PyInstaller packaging/specs/tetris_playtest.spec --noconfirm
"""

import os
import sys
from pathlib import Path

# Proje kök dizini (spec dosyası packaging/specs/ altında)
REPO_ROOT = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from tools.embed_menu_layout import write_embedded_layout_module
from tools.bridge_artifacts import get_bridge_binaries
from tools.versioning import bump_platform_version

SRC_DIR = REPO_ROOT / 'src'
write_embedded_layout_module(REPO_ROOT)

_new_version, _build, _version_file = bump_platform_version(REPO_ROOT, 'windows')
print(f'[spec] Windows surumu guncellendi: {_new_version} (build {_build}) -> {_version_file.name}')

block_cipher = None


def _write_runtime_appid(app_id: str, variant: str) -> str:
    runtime_dir = REPO_ROOT / 'build' / 'pyinstaller_runtime' / variant
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / 'steam_appid.txt'
    runtime_file.write_text(f'{app_id}\n', encoding='utf-8')
    return str(runtime_file)


RUNTIME_STEAM_APPID = _write_runtime_appid('4428040', 'playtest')

# Oyun runtime'ında kullanılan tüm kaynakları topla
datas = [
    # Tüm görsel/ses asset ağacı
    (str(REPO_ROOT / 'assets'), 'assets'),

    # Diğer medya klasörleri
    (str(REPO_ROOT / 'music'), 'music'),
    (str(REPO_ROOT / 'backgrounds'), 'backgrounds'),
    (str(REPO_ROOT / 'avatars'), 'avatars'),

    # Dil/font profilleri için font dosyaları
    (str(REPO_ROOT / 'font'), 'font'),

    # Apple emoji görselleri: runtime'da kullanılmaz.
    # Emojiler assets/ui/emoji/ altında ASCII adlarla mevcuttur.
    # (str(REPO_ROOT / 'apple_emojis'), 'apple_emojis'),

    # Kampanya level tanımları
    (str(REPO_ROOT / 'campaign_levels.csv'), '.'),

    # Runtime yapılandırmaları
    (RUNTIME_STEAM_APPID, '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'menu_layout_runtime.json'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'credits_layout.json'), '.'),

    # src içi kaynaklar
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'settings.json'), 'src'),
    (str(SRC_DIR / 'localization_auto_overrides.json'), 'src'),
]

# Sadece var olan dizinleri ekle
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# pygame varsayılan font (freesansbold.ttf) — paketli ortamda eksik olabilir (belt-and-suspenders)
try:
    import pygame as _pg
    _freesans = Path(_pg.__file__).resolve().parent / 'freesansbold.ttf'
    if _freesans.exists():
        datas.append((str(_freesans), 'pygame'))
        print(f'[spec] freesansbold.ttf eklendi: {_freesans}')
except Exception as _e:
    print(f'[spec] freesansbold.ttf eklenemedi: {_e}')

# Gizli importlar (dinamik olarak yüklenen modüller)
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
    'steam_net_bridge',    # Steam Networking bridge (Pybind11, Online PvP)
    'version',
    'version_base',
    'version_local_windows',
]

# src klasöründeki tüm Python modüllerini ekle
for py_file in SRC_DIR.glob('*.py'):
    module_name = py_file.stem
    if module_name != '__init__':
        hiddenimports.append(module_name)

# Alt klasörlerdeki modüller
for subdir in ['renderers', 'types']:
    subdir_path = SRC_DIR / subdir
    if subdir_path.exists():
        for py_file in subdir_path.glob('*.py'):
            module_name = f"{subdir}.{py_file.stem}"
            hiddenimports.append(module_name)

# src/campaign/ alt paketi
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
    print(f'[spec] pygame._sdl2 submodülleri eklendi: {_sdl2_submods}')
except Exception as _sdl2_exc:
    print(f'[spec] UYARI: pygame._sdl2 submodül toplama başarısız: {_sdl2_exc}')
    for _m in ('pygame._sdl2', 'pygame._sdl2.video', 'pygame._sdl2.sdl2',
               'pygame._sdl2.window', 'pygame._sdl2.audio', 'pygame._sdl2.controller',
               'pygame._sdl2.mixer', 'pygame._sdl2.touch'):
        if _m not in hiddenimports:
            hiddenimports.append(_m)

# Steamworks DLL - dll/win64/ klasöründen al, EXE içine göm (onefile)
# Steam, DLL'i _MEIPASS'tan ctypes ile yükler; ayrı dosya gerekmez.
steam_dll_src = str(REPO_ROOT / 'dll' / 'win64' / 'steam_api64.dll')
if os.path.exists(steam_dll_src):
    binaries = [(steam_dll_src, '.')]  # EXE içine gömülür, _MEIPASS'a çıkarılır
else:
    binaries = []
    print(f"WARNING: steam_api64.dll not found at {steam_dll_src}")

# Steamworks macOS dylib - dll/osx/ klasöründen al (.app bundle için)
# macOS üzerinde build edildiğinde Contents/MacOS/ içine yerleşir (Steam'in beklediği konum)
steam_dylib_src = str(REPO_ROOT / 'dll' / 'osx' / 'libsteam_api.dylib')
if os.path.exists(steam_dylib_src):
    binaries.append((steam_dylib_src, '.'))
    print(f'[spec] libsteam_api.dylib eklendi: {steam_dylib_src}')
else:
    print(f'[spec] libsteam_api.dylib bulunamadı (macOS build değilse normaldir): {steam_dylib_src}')

# Steam Networking bridge (Pybind11 C++ modülü) — Online PvP için
_bridge_matches = get_bridge_binaries(REPO_ROOT)
if _bridge_matches:
    _bridge_path = _bridge_matches[0]
    binaries.append((_bridge_path, '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_path}')
else:
    print('[spec] UYARI: steam_net_bridge bulunamadı')

# MinGW runtime DLL'leri — steam_net_bridge.pyd bunlara bağımlı (GCC ile derlendi)
_mingw_dlls = ['libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libwinpthread-1.dll']
_mingw_dir = REPO_ROOT / 'dll' / 'win64'
for _dll_name in _mingw_dlls:
    _dll_path = _mingw_dir / _dll_name
    if _dll_path.exists():
        binaries.append((str(_dll_path), '.'))
        print(f'[spec] MinGW DLL eklendi: {_dll_path.name}')
    else:
        print(f'[spec] UYARI: MinGW DLL bulunamadı: {_dll_path}')

# pygame._sdl2 C-extension (.pyd) dosyaları + pygame SDL2 DLL'leri.
# hiddenimports tek başına .pyd'leri fiziksel olarak KOPYALAMAYABİLİR (pygame hook'u yok),
# bu yüzden hem _sdl2 .pyd'lerini hem pygame'in dinamik kütüphanelerini açıkça topluyoruz.
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
            print(f'[spec] pygame dinamik kütüphaneleri eklendi: {len(_pg_libs)} adet')
    except Exception as _pg_lib_exc:
        print(f'[spec] UYARI: pygame dinamik kütüphane toplama başarısız: {_pg_lib_exc}')
except Exception as _sdl2_bin_exc:
    print(f'[spec] UYARI: pygame._sdl2 .pyd toplama başarısız: {_sdl2_bin_exc}')

a = Analysis(
    [str(SRC_DIR / 'main.py')],  # Ana giriş noktası
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(REPO_ROOT / 'packaging' / 'pyinstaller' / 'hooks' / 'pyi_rth_quadrix_data.py')],
    excludes=[
        # tkinter artık kullanılmıyor (pygame tabanlı color_picker/file_dialog)
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
    name='Quadrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
