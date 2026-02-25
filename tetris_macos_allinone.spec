# -*- mode: python ; coding: utf-8 -*-
"""
Quadrix Oyunu - macOS All-in-One .app Bundle
PyInstaller Spec Dosyası

Tüm asset'ler, sesler, görseller, fontlar, ayarlar tek bir .app içine paketlenir.
Windows'taki tek-EXE deneyiminin macOS karşılığıdır.

Kullanım:
    python3 -m PyInstaller tetris_macos_allinone.spec --noconfirm

Sonuç: dist/Quadrix.app
"""

import os
import sys
from pathlib import Path

# ── Build-time menü layout embedleme ──
sys.path.insert(0, str(Path(SPECPATH).resolve()))
from tools.embed_menu_layout import write_embedded_layout_module

REPO_ROOT = Path(SPECPATH).resolve()
SRC_DIR = REPO_ROOT / 'src'

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

    # ── Apple emoji görselleri (Türkçe isimli PNG'ler) ──
    (str(REPO_ROOT / 'apple_emojis'), 'apple_emojis'),

    # ── Font dosyaları (CJK, paperlogy, cinecaption) ──
    (str(REPO_ROOT / 'font'), 'font'),

    # ── Kampanya level tanımları ──
    (str(REPO_ROOT / 'campaign_levels.csv'), '.'),

    # ── Runtime yapılandırmaları ──
    (str(REPO_ROOT / 'steam_appid.txt'), '.'),
    (str(REPO_ROOT / 'settings.txt'), '.'),
    (str(REPO_ROOT / 'menu_layout_runtime.json'), '.'),

    # ── src içi kaynaklar ──
    (str(SRC_DIR / 'splashscreen'), 'src/splashscreen'),
    (str(SRC_DIR / 'avatars'), 'src/avatars'),
    (str(SRC_DIR / 'assets'), 'src/assets'),
]

# credits_layout.json (opsiyonel)
_credits = REPO_ROOT / 'credits_layout.json'
if _credits.exists():
    datas.append((str(_credits), '.'))

# src/settings.json (opsiyonel)
_src_settings = SRC_DIR / 'settings.json'
if _src_settings.exists():
    datas.append((str(_src_settings), 'src'))

# Sadece var olan dizin/dosyaları ekle (build hatasını önle)
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# ═══════════════════════════════════════════════════════════════════
#  HIDDEN IMPORTS - Dinamik olarak yüklenen tüm modüller
# ═══════════════════════════════════════════════════════════════════
hiddenimports = [
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
#  ANALYSIS
# ═══════════════════════════════════════════════════════════════════
a = Analysis(
    [str(SRC_DIR / 'main.py')],
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
        'PIL',
        'Pillow',
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
    version='1.0.0',
    info_plist={
        # ── Temel Bilgiler ──
        'CFBundleName': 'Quadrix',
        'CFBundleDisplayName': 'Quadrix',
        'CFBundleGetInfoString': 'Quadrix - Tetris Full Edition',
        'CFBundleIdentifier': 'com.burakyasayan.quadrix',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
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
