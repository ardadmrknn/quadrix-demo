# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - macOS .app için PyInstaller Spec Dosyası
Versiyon: 1.0.0
"""

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH).resolve()))
from tools.embed_menu_layout import write_embedded_layout_module

# Proje kök dizini
REPO_ROOT = Path(SPECPATH).resolve()
SRC_DIR = REPO_ROOT / 'src'


def _load_version_string(version_file: Path) -> str:
    spec = importlib.util.spec_from_file_location('version_base_spec', version_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'version modulu yuklenemedi: {version_file}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(getattr(module, 'VERSION'))


APP_VERSION = _load_version_string(SRC_DIR / 'version_base.py')

write_embedded_layout_module(REPO_ROOT)

block_cipher = None

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
    (str(REPO_ROOT / 'steam_appid.txt'), '.'),
    (str(REPO_ROOT / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'menu_layout_runtime.json'), '.'),
    (str(REPO_ROOT / 'credits_layout.json'), '.'),

    # src içi kaynaklar
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'assets'), 'src/assets'),
    (str(SRC_DIR / 'settings.json'), 'src'),
]

# Sadece var olan dizinleri ekle
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# pygame-ce varsayılan font (freesansbold.ttf) — paketli ortamda eksik olabilir (belt-and-suspenders)
# NOT: pygame-ce de 'pygame' namespace altında kurulur, bu yüzden import pygame çalışır.
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
    'array',
    'shutil',
    'subprocess',
    'steam_integration',  # Steam SDK ctypes wrapper (macOS: libsteam_api.dylib)
    'steam_net_bridge',    # Steam Networking bridge (Pybind11, Online PvP)
    'version',
    'version_base',
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

# Steamworks macOS dylib - aynı klasörde varsa ekle
# Steamworks dylib - dll/osx/ klasöründen al
# macOS .app bundle'da Contents/MacOS/ içine yerleşir (Steam'in beklediği konum)
steam_dylib_src = str(REPO_ROOT / 'dll' / 'osx' / 'libsteam_api.dylib')
if os.path.exists(steam_dylib_src):
    binaries = [(steam_dylib_src, '.')]  # Contents/MacOS/ içine kopyalanır
else:
    binaries = []

# Steam Networking bridge (Pybind11 C++ modülü) — Online PvP için
for _bridge_path in get_bridge_binaries(REPO_ROOT):
    binaries.append((_bridge_path, '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_path}')

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
        # Gereksiz büyük modülleri hariç tut (boyutu azaltmak için)
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
        'PyQt5',
        'PySide2',
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
    name='Quadrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI uygulama - konsol penceresi yok
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Quadrix',
)

# macOS .app bundle oluştur
app = BUNDLE(
    coll,
    name='Quadrix.app',
    icon=str(REPO_ROOT / 'assets' / 'Tetris.icns'),
    bundle_identifier='com.burakyasayan.quadrix',
    version=APP_VERSION,
    info_plist={
        'CFBundleName': 'Quadrix',
        'CFBundleDisplayName': 'Quadrix',
        'CFBundleGetInfoString': 'Quadrix Full Edition',
        'CFBundleIdentifier': 'com.burakyasayan.tetris',
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleExecutable': 'Quadrix',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'TTRS',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Dark mode desteği
        'LSMinimumSystemVersion': '10.13.0',
        'LSApplicationCategoryType': 'public.app-category.games',
        'NSHumanReadableCopyright': '© 2026 Burak Yasayan. Tüm hakları saklıdır.',
    },
)
