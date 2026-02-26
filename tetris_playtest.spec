# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - PyInstaller Spec Dosyası (Steam Playtest)
Playtest AppID: 4428040

Kullanım:
    python -m PyInstaller tetris_playtest.spec --noconfirm
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

block_cipher = None

# Playtest AppID'yi ortam değişkeni olarak göm
# Not: steam_appid.txt kök dizinde zaten mevcut; bu env tanımı
# PyInstaller boot kancasının STEAM_APP_ID'yi ayarlaması için eklenir.
os.environ.setdefault('STEAM_APP_ID', '4428040')

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

    # Apple emoji görselleri
    (str(REPO_ROOT / 'apple_emojis'), 'apple_emojis'),

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
    print(f"WARNING: steam_api64.dll not found at {steam_dll_src}")

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
