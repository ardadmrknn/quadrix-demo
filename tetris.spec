# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - PyInstaller Spec Dosyası
Tek EXE dosyasına paketleme için yapılandırma
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH).resolve()))
from tools.embed_menu_layout import write_embedded_layout_module

# Proje kök dizini
REPO_ROOT = Path(SPECPATH).resolve()
SRC_DIR = REPO_ROOT / 'src'
write_embedded_layout_module(REPO_ROOT)

# ── Otomatik sürüm artırma ──────────────────────────────────────────────────
# Her derlemede src/version.py'deki PATCH sürümü 1 artar: 1.0.0 → 1.0.1 → ...
import re as _re
_ver_file = SRC_DIR / 'version.py'
_ver_text = _ver_file.read_text(encoding='utf-8')
_ver_match = _re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', _ver_text)
_build_match = _re.search(r'BUILD_NUMBER\s*=\s*(\d+)', _ver_text)
if _ver_match:
    _major, _minor, _patch = int(_ver_match.group(1)), int(_ver_match.group(2)), int(_ver_match.group(3))
    _patch += 1
    _build = int(_build_match.group(1)) + 1 if _build_match else _patch
    _new_version = f'{_major}.{_minor}.{_patch}'
    _ver_text = _re.sub(r'VERSION\s*=\s*"[^"]+"', f'VERSION = "{_new_version}"', _ver_text)
    _ver_text = _re.sub(r'BUILD_NUMBER\s*=\s*\d+', f'BUILD_NUMBER = {_build}', _ver_text)
    _ver_file.write_text(_ver_text, encoding='utf-8')
    print(f'[spec] Sürüm güncellendi: {_new_version} (build {_build})')
else:
    _new_version = '1.0.0'
# ────────────────────────────────────────────────────────────────────────────

block_cipher = None

datas = [
    # Tüm görsel/ses asset ağacı
    (str(REPO_ROOT / 'assets'), 'assets'),

    # Diğer medya klasörleri
    (str(REPO_ROOT / 'music'), 'music'),
    (str(REPO_ROOT / 'backgrounds'), 'backgrounds'),
    (str(REPO_ROOT / 'avatars'), 'avatars'),

    # Apple emoji görselleri
    (str(REPO_ROOT / 'apple_emojis'), 'apple_emojis'),

    # Dil/font profilleri için font dosyaları
    (str(REPO_ROOT / 'font'), 'font'),

    # Kampanya level tanımları
    (str(REPO_ROOT / 'campaign_levels.csv'), '.'),

    # Runtime yapılandırmaları
    (str(REPO_ROOT / 'steam_appid.txt'), '.'),
    (str(REPO_ROOT / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'menu_layout_runtime.json'), '.'),
    (str(REPO_ROOT / 'credits_layout.json'), '.'),

    # src içi kaynaklar
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'settings.json'), 'src'),
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
# setuptools jaraco.text Lorem ipsum.txt \u2014 pkg_resources import crash\u0131n\u0131 \u00f6nle
try:
    import setuptools as _st
    _jaraco_dir = Path(_st.__file__).resolve().parent / '_vendor' / 'jaraco' / 'text'
    _lorem = _jaraco_dir / 'Lorem ipsum.txt'
    if _lorem.exists():
        datas.append((str(_lorem), str(Path('setuptools') / '_vendor' / 'jaraco' / 'text')))
        print(f'[spec] Lorem ipsum.txt eklendi: {_lorem}')
    else:
        print(f'[spec] Lorem ipsum.txt bulunamad\u0131: {_lorem}')
except Exception as _e:
    print(f'[spec] Lorem ipsum.txt eklenemedi: {_e}')
# Gizli importlar (dinamik olarak yüklenen modüller)
hiddenimports = [
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
    'steam_integration',  # Steam SDK ctypes wrapper
    'version',            # Sürüm bilgisi modülü
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

# Steamworks DLL - dll/win64/ klasöründen al, EXE içine göm (onefile)
# Steam, DLL'i _MEIPASS'tan ctypes ile yükler; ayrı dosya gerekmez.
steam_dll_src = str(REPO_ROOT / 'dll' / 'win64' / 'steam_api64.dll')
if os.path.exists(steam_dll_src):
    binaries = [(steam_dll_src, '.')]  # EXE içine gömülür, _MEIPASS'a çıkarılır
else:
    binaries = []

a = Analysis(
    [str(SRC_DIR / 'main.py')],  # Ana giriş noktası
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # tkinter artık kullanılmıyor (pygame tabanlı color_picker/file_dialog)
        'tkinter',
        '_tkinter',
        'tkinter.colorchooser',
        'tkinter.filedialog',
        'tkinter.simpledialog',
        # Gereksiz büyük modülleri hariç tut (boyutu azaltmak için)
        'matplotlib',
        # NumPy bu projede artık kullanılmıyor; EXE taşınabilirliğini artırmak için hariç tut.
        'numpy',
        # pygame.surfarray NumPy'yi çekebilir; oyunda kullanılmadığı için hariç tut.
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
    upx=False,  # UPX kapalı: bazı sistemlerde .pyd/.dll yükleme sorunlarını azaltır
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Konsol penceresi gösterme (GUI uygulama)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

)
