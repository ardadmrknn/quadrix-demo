# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - macOS All-in-One .app Bundle
PyInstaller Spec Dosyası

Tüm asset'ler, sesler, görseller, fontlar, ayarlar tek bir .app içine paketlenir.
Windows'taki tek-EXE deneyiminin macOS karşılığıdır.

Kullanım:
    python3 -m PyInstaller packaging/specs/tetris_macos_allinone.spec --noconfirm

Sonuç: dist/Quadrix.app
"""

import importlib.util
import os
import sys
from pathlib import Path

# ── Build-time menü layout embedleme ──
REPO_ROOT = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from tools.embed_menu_layout import write_embedded_layout_module
from tools.bridge_artifacts import get_bridge_binaries

SRC_DIR = REPO_ROOT / 'src'


def _load_version_string(version_file: Path) -> str:
    spec = importlib.util.spec_from_file_location('version_base_spec', version_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'version modulu yuklenemedi: {version_file}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(getattr(module, 'VERSION'))


APP_VERSION = _load_version_string(SRC_DIR / 'version_base.py')

# Menü layoutunu Python modülüne göm (build öncesi)
write_embedded_layout_module(REPO_ROOT)

block_cipher = None

# ═══════════════════════════════════════════════════════════════════
#  DATA FILES - Tüm görseller, sesler, fontlar, ayarlar
# ═══════════════════════════════════════════════════════════════════
datas = [
    # ── Ana asset ağacı (UI, efektler, emoji, kartlar, kampanya görselleri, maskot) ──
    (str(REPO_ROOT / 'assets'), 'assets'),

    # ── Müzik dosyaları (20 MP3 parça, ~69MB) ──
    (str(REPO_ROOT / 'music'), 'music'),

    # ── Arka plan görselleri ──
    (str(REPO_ROOT / 'backgrounds'), 'backgrounds'),

    # ── Avatar görselleri ──
    (str(REPO_ROOT / 'avatars'), 'avatars'),

    # ── Apple emoji görselleri: runtime'da kullanılmaz ──
    # Emojiler assets/ui/emoji/ altında ASCII adlarla mevcuttur.
    # (str(REPO_ROOT / 'apple_emojis'), 'apple_emojis'),

    # ── Font dosyaları (CJK, paperlogy, cinecaption) ──
    (str(REPO_ROOT / 'font'), 'font'),

    # ── Kampanya level tanımları ──
    (str(REPO_ROOT / 'campaign_levels.csv'), '.'),

    # ── Runtime yapılandırmaları ──
    (str(REPO_ROOT / 'config' / 'runtime' / 'steam_appid.txt'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'config' / 'runtime' / 'menu_layout_runtime.json'), '.'),

    # ── src içi kaynaklar ──
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'assets'), 'src/assets'),
]

# credits_layout.json (opsiyonel)
_credits = REPO_ROOT / 'config' / 'runtime' / 'credits_layout.json'
if _credits.exists():
    datas.append((str(_credits), '.'))

# src/settings.json (opsiyonel)
_src_settings = SRC_DIR / 'settings.json'
if _src_settings.exists():
    datas.append((str(_src_settings), 'src'))

# Sadece var olan dizin/dosyaları ekle (build hatasını önle)
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

# ═══════════════════════════════════════════════════════════════════
#  HIDDEN IMPORTS - Dinamik olarak yüklenen tüm modüller
# ═══════════════════════════════════════════════════════════════════
hiddenimports = [
    'PIL',
    'PIL.Image',
    'PIL.ImageSequence',
    'PIL.GifImagePlugin',
    'PIL.PngImagePlugin',

    # ── Pygame alt modülleri ──
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

    # ── Python standart kütüphane ──
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

    # ── pkg_resources bağımlılıkları (PyInstaller runtime hook) ──
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

    # ── Steam Net Bridge (Online PvP) ──
    'steam_net_bridge',
    'version',
    'version_base',
]

# ── src/ altındaki tüm Python modüllerini ekle ──
for py_file in SRC_DIR.glob('*.py'):
    module_name = py_file.stem
    if module_name != '__init__':
        hiddenimports.append(module_name)

# ── src/campaign/ alt paketi ──
campaign_dir = SRC_DIR / 'campaign'
if campaign_dir.exists():
    hiddenimports.append('campaign')
    for py_file in campaign_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'campaign.{module_name}')

# ── src/renderers/ alt paketi ──
renderers_dir = SRC_DIR / 'renderers'
if renderers_dir.exists():
    hiddenimports.append('renderers')
    for py_file in renderers_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'renderers.{module_name}')

# ── src/types/ alt paketi (genişleme için) ──
types_dir = SRC_DIR / 'types'
if types_dir.exists():
    hiddenimports.append('types')
    for py_file in types_dir.glob('*.py'):
        module_name = py_file.stem
        if module_name != '__init__':
            hiddenimports.append(f'types.{module_name}')

# ═══════════════════════════════════════════════════════════════════
#  STEAM SDK - libsteam_api.dylib
# ═══════════════════════════════════════════════════════════════════
# macOS .app bundle'da Contents/MacOS/ içine yerleşir (Steam'in beklediği konum)
steam_dylib_src = str(REPO_ROOT / 'dll' / 'osx' / 'libsteam_api.dylib')
if os.path.exists(steam_dylib_src):
    _steam_binaries = [(steam_dylib_src, '.')]
    print(f'[spec] libsteam_api.dylib eklendi: {steam_dylib_src}')
else:
    _steam_binaries = []
    print(f'WARNING: libsteam_api.dylib not found at {steam_dylib_src}')

# ═══════════════════════════════════════════════════════════════════
#  STEAM NET BRIDGE - Online PvP (Pybind11 C++ modülü)
# ═══════════════════════════════════════════════════════════════════
_bridge_matches = get_bridge_binaries(REPO_ROOT)
if _bridge_matches:
    _bridge_path = _bridge_matches[0]
    _steam_binaries.append((_bridge_path, '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_path}')
else:
    print('WARNING: steam_net_bridge not found — Online PvP çalışmayacak!')

# ═══════════════════════════════════════════════════════════════════
#  ANALYSIS
# ═══════════════════════════════════════════════════════════════════
a = Analysis(
    [str(SRC_DIR / 'main.py')],
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=_steam_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(REPO_ROOT / 'packaging' / 'pyinstaller' / 'hooks' / 'pyi_rth_quadrix_data.py')],
    excludes=[
        # Gereksiz büyük modüller (boyutu azaltmak için)
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

# ═══════════════════════════════════════════════════════════════════
#  PYZ - Pure Python modülleri sıkıştır
# ═══════════════════════════════════════════════════════════════════
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ═══════════════════════════════════════════════════════════════════
#  EXE - macOS yürütülebilir dosyası
# ═══════════════════════════════════════════════════════════════════
#
# macOS'ta "all-in-one" = .app bundle.
# Kullanıcıya tek bir Quadrix.app olarak görünür.
# exclude_binaries=True → COLLECT ile .app/Contents/MacOS/ altına toplanır.
#
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Quadrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,                   # Strip debug sembollerini (boyutu azalt)
    upx=False,                    # macOS'ta UPX sorun çıkarabilir
    console=False,                # GUI uygulama - terminal penceresi açma
    disable_windowed_traceback=False,
    argv_emulation=False,         # macOS Finder argüman emülasyonu (kapalı: pygame kendi işliyor)
    target_arch='arm64',          # Apple Silicon (değiştirmek için: 'x86_64' veya 'universal2')
    codesign_identity=None,       # Opsiyonel: Developer ID ile imzalama
    entitlements_file=None,
    icon=str(REPO_ROOT / 'assets' / 'Tetris.icns'),
)

# ═══════════════════════════════════════════════════════════════════
#  COLLECT - Tüm dosyaları .app içine topla
# ═══════════════════════════════════════════════════════════════════
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='Quadrix',
)

# ═══════════════════════════════════════════════════════════════════
#  BUNDLE - macOS .app Bundle (All-in-One)
# ═══════════════════════════════════════════════════════════════════
#
# Bu adım, COLLECT çıktısını bir .app klasörüne sarar:
#   Quadrix.app/
#     Contents/
#       Info.plist          ← Uygulama meta verileri
#       MacOS/
#         Quadrix           ← Yürütülebilir
#       Resources/
#         Tetris.icns       ← Uygulama ikonu
#       Frameworks/         ← Paylaşılan kütüphaneler (SDL2, pygame vb.)
#
app = BUNDLE(
    coll,
    name='Quadrix.app',
    icon=str(REPO_ROOT / 'assets' / 'Tetris.icns'),
    bundle_identifier='com.burakyasayan.quadrix',
    version=APP_VERSION,
    info_plist={
        # ── Temel Bilgiler ──
        'CFBundleName': 'Quadrix',
        'CFBundleDisplayName': 'Quadrix',
        'CFBundleGetInfoString': 'Quadrix - Tetris Full Edition',
        'CFBundleIdentifier': 'com.burakyasayan.quadrix',
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleExecutable': 'Quadrix',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'QDRX',

        # ── Görünüm & Uyumluluk ──
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,    # Dark mode desteği
        'NSSupportsAutomaticGraphicsSwitching': True,

        # ── macOS Versiyon Gereksinimleri ──
        'LSMinimumSystemVersion': '11.0',           # macOS Big Sur+

        # ── App Store / Finder Kategorisi ──
        'LSApplicationCategoryType': 'public.app-category.games',

        # ── Telif Hakkı ──
        'NSHumanReadableCopyright': '© 2026 Burak Yasayan. Tüm hakları saklıdır.',

        # ── Güvenlik & İzinler ──
        # Dosya kaydetme (kullanıcı verileri ~/Library/Application Support/ altına)
        'NSDocumentsFolderUsageDescription': 'Quadrix oyun verilerini kaydetmek için kullanılır.',

        # ── Ses Kontrolü ──
        'NSMicrophoneUsageDescription': 'Bu uygulama mikrofona erişmez.',

        # ── Ağ Erişimi (Steam Leaderboard için) ──
        'NSAllowsArbitraryLoads': True,

        # ── Ek macOS özellikleri ──
        'LSBackgroundOnly': False,           # Arka plan uygulaması değil
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
    },
)
