# Quadrix Demo — Linux (.elf) Paketleme ve Derleme Rehberi

> Son güncelleme: 2026-06-17
> Kapsam: Linux (.elf) derlemeleri + Steam entegrasyonu + C++ Steam Bridge derlemesi.
> Bu kılavuz `quadrix-demo/` kod tabanı için özelleştirilmiştir.

Bu kılavuz, Windows (.exe) ve macOS (.app) için kullanılan mevcut paketleme mekanizmalarının Linux (.elf) platformuna nasıl uyarlanacağını, PyInstaller spec dosyalarında yapılması gereken değişiklikleri ve derleme süreçlerini detaylandırmaktadır.

---

## 1. Mevcut Paketleme Mekanizmasının Analizi (Windows vs macOS)

Mevcut projelerde paketleme işlemi platforma özel olarak şu şekilde işlenmektedir:

| Platform | Dosya Biçimi | Paketleme Tipi | Steam Kitaplığı | C++ Bridge Uzantısı | PyInstaller Çıktısı |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Windows** | Portable Executable (`.exe`) | One-File (Tek Dosya) | `steam_api64.dll` | `steam_net_bridge.cp312-win_amd64.pyd` | `EXE()` bloğunda her şey gömülüdür. |
| **macOS** | Mach-O (`.app` Bundle) | One-Folder (Klasör) + BUNDLE | `libsteam_api.dylib` | `steam_net_bridge.so` (veya `.dylib`) | `COLLECT()` ve `BUNDLE()` ile paket yapısı oluşur. |
| **Linux** | ELF (`.elf` / İkili Dosya) | One-File veya One-Folder | `libsteam_api.so` | `steam_net_bridge.cpython-312-x86_64-linux-gnu.so` | `EXE()` tek dosya veya `COLLECT()` dizin çıktısı. |

### Windows Paketleme Akışı (Özet):
1. `build_windows_demo.ps1` orkestratörü çalışır.
2. `write_demo_config.py --mode demo` ile `src/demo_config.py` içinde `IS_DEMO = True` yapılır.
3. MSVC, CMake ve Pybind11 kullanılarak C++ Steam bridge derlenir ve `steam_net_bridge.pyd` üretilir.
4. PyInstaller, `tetris_demo.spec` dosyasını okur.
5. `pygame._sdl2` modülünün C uzantıları (`.pyd`) ve SDL2 DLL'leri açıkça toplanıp `binaries` listesine eklenir (Steam Overlay'in çalışması için bu adım kritiktir).
6. Tüm varlıklar (assets, music, backgrounds vb.) ve `steam_api64.dll` tek bir `.exe` dosyasında birleştirilir.
7. Derleme bitince config `full` moduna geri döndürülür.

---

## 2. Linux (.elf) Paketlemesi İçin Ön Koşullar

PyInstaller çapraz derlemeyi (cross-compilation) desteklemediği için Linux ikili dosyası (.elf) yalnızca bir Linux ortamında derlenebilir.

1. **İşletim Sistemi Ortamı:** Fiziksel bir Linux dağıtımı (tercihen Ubuntu 20.04+ veya Debian), Windows üzerinde **WSL (Windows Subsystem for Linux)** veya bir **Docker Konteyneri**.
2. **Derleme Araçları:**
   ```bash
   sudo apt-get update
   sudo apt-get install build-essential cmake patchelf python3.12 python3.12-dev python3-pip
   ```
3. **Python Bağımlılıkları:**
   ```bash
   pip install pygame-ce==2.5.7 numpy>=2.4.6 Pillow>=12.2.0 requests>=2.34.2 pyinstaller>=6.20 pybind11
   ```
4. **SDL2 Geliştirme Kütüphaneleri (Gerekirse):** Pygame-ce kendi SDL kütüphanelerini barındırır ancak yerel derlemelerde sistem kütüphanelerine ihtiyaç duyulabilir:
   ```bash
   sudo apt-get install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
   ```

---

## 3. Linux İçin Steam SDK ve C++ Bridge Derleme Adımları

Linux derlemesinde Steamworks entegrasyonu ve Online PvP lobileri için iki kritik dinamik kütüphanenin (.so) hazırlanması gerekir:

### 3.1 `libsteam_api.so` Konumlandırılması
1. Steamworks SDK (`sdk/redistributable_binaries/linux64/`) içerisinden `libsteam_api.so` dosyasını alın.
2. Proje kök dizininde `dll/linux64/` adında bir klasör oluşturup bu dosyayı oraya kopyalayın:
   `dll/linux64/libsteam_api.so`

### 3.2 Linux C++ Steam Bridge Derlemesi
`steamworks/steam_net_bridge/` altında Linux uyumlu bir derleme betiği (`build.sh`) yazılmalı veya CMake doğrudan tetiklenmelidir:
```bash
cd steamworks/steam_net_bridge
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
```
Bu derleme sonucunda `steamworks/steam_net_bridge/` altında Python'ın içe aktarabileceği paylaşımlı kütüphane oluşur:
* Dosya adı örneği: `steam_net_bridge.cpython-312-x86_64-linux-gnu.so`
* Bu dosya daha sonra PyInstaller tarafından taranarak paket içerisine yerleştirilecektir.

---

## 4. Demo Linux Spec Dosyası Yapılandırması (`tetris_demo_linux.spec`)

Mevcut Windows spec dosyasından yola çıkarak Linux platformu için oluşturulması gereken `packaging/specs/tetris_demo_linux.spec` yapılandırma mantığı ve eklenmesi gereken kod parçacıkları aşağıda detaylandırılmıştır.

### 4.1 Linux'a Özgü Yol ve İsimlendirme Ayarları
Spec dosyasının başında, platform kontrolü ve Linux binary yolları şu şekilde tanımlanmalıdır:

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Demo AppID zorunlu olarak set edilir
os.environ.setdefault('STEAM_APP_ID', '4635310')

REPO_ROOT = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.embed_menu_layout import write_embedded_layout_module
from tools.bridge_artifacts import get_bridge_binaries

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
# Linux Demo AppID dosyasının oluşturulması
RUNTIME_STEAM_APPID = _write_runtime_appid_from_source(DEMO_APPID_SOURCE, 'demo_linux')
```

### 4.2 Linux Dinamik Kütüphanelerini (.so) Toplama
Linux paketinde `binaries` listesine Steam API kütüphanesi, C++ bridge ve Pygame-ce'in SDL2 donanım ivmeli render modülleri eklenmelidir:

```python
binaries = []

# 1. Steamworks Linux Shared Library (.so)
steam_so_src = str(REPO_ROOT / 'dll' / 'linux64' / 'libsteam_api.so')
if os.path.exists(steam_so_src):
    binaries.append((steam_so_src, '.')) # Paket köküne kopyalanır
else:
    print("[spec] UYARI: libsteam_api.so bulunamadı!")

# 2. Steam Networking Bridge (.so)
_bridge_matches = get_bridge_binaries(REPO_ROOT)
if _bridge_matches:
    _bridge_path = _bridge_matches[0]
    binaries.append((_bridge_path, '.'))
    print(f'[spec] steam_net_bridge eklendi: {_bridge_path}')
else:
    print('[spec] UYARI: steam_net_bridge.so bulunamadı!')

# 3. Pygame-ce Linux C-Extension (.so) Dosyalarının Toplanması
try:
    import pygame as _pg_mod
    _pg_dir = Path(_pg_mod.__file__).resolve().parent
    _sdl2_dir = _pg_dir / '_sdl2'
    if _sdl2_dir.exists():
        for _so in _sdl2_dir.glob('*.so'):
            binaries.append((str(_so), os.path.join('pygame', '_sdl2')))
            print(f'[spec] pygame._sdl2 .so eklendi: {_so.name}')
            
    from PyInstaller.utils.hooks import collect_dynamic_libs as _cdl
    _pg_libs = _cdl('pygame')
    if _pg_libs:
        binaries.extend(_pg_libs)
        print(f'[spec] pygame dinamik kütüphaneleri eklendi: {len(_pg_libs)} adet')
except Exception as _sdl2_bin_exc:
    print(f'[spec] UYARI: pygame._sdl2 kütüphaneleri toplanamadı: {_sdl2_bin_exc}')
```

### 4.3 Veri Dosyaları (`datas`) ve Büyük/Küçük Harf Duyarlılığı
Linux dosya sistemi büyük/küçük harfe duyarlıdır (case-sensitive). Dosya ve klasör yollarının birebir eşleştiğinden emin olunmalıdır.

```python
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
```

### 4.4 Analiz ve Yürütülebilir Dosya Tanımı (`EXE` Bloğu)
Linux için tek dosyadan oluşan (`onefile`) ELF paketi oluşturmak için `EXE()` yapılandırması:

```python
a = Analysis(
    [str(SRC_DIR / 'main.py')],
    pathex=[str(SRC_DIR), str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(REPO_ROOT / 'packaging' / 'pyinstaller' / 'hooks' / 'pyi_rth_quadrix_data.py')],
    excludes=excludes_list,
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
    name='QuadrixDemo', # Demo çalıştırılabilir dosya adı
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
```

---

## 5. Linux Üzerinde Derleme ve Paketleme Adımları

Tüm hazırlıklar tamamlandıktan sonra, Linux ortamında derleme yapmak için şu adımlar sırasıyla takip edilir:

### 5.1 Demo Sürümü Derleme Adımları
Demo sürümü derlenirken config orkestrasyonunu sağlamak için kök dizinde şu komutlar çalıştırılır:
1. `python3 scripts/build/write_demo_config.py --mode demo` komutuyla yapılandırma `IS_DEMO = True` durumuna getirilir.
2. `pyinstaller packaging/specs/tetris_demo_linux.spec --noconfirm --clean` çalıştırılır.
3. `python3 scripts/build/write_demo_config.py --mode full` komutuyla yapılandırma tekrar güvenli moda geri döndürülür.
* Çıktı `dist/QuadrixDemo` olarak üretilir.

---

## 6. Linux ELF İkili Dosyalarında Dikkat Edilmesi Gereken Hatalar ve Çözümleri

### 6.1 `libsteam_api.so: cannot open shared object file` Hatası
* **Çözüm:** Derlenen binary'nin kütüphane arama yolu `patchelf` aracıyla kontrol edilmeli veya oyun çalıştırılırken `LD_LIBRARY_PATH` belirtilmelidir:
  ```bash
  LD_LIBRARY_PATH=. ./QuadrixDemo
  ```

### 6.2 Ekran Kartı Sürücü Hataları ve OpenGL / SDL Uyuşmazlığı
* **Çözüm:** Pygame başlatılırken yazılımsal render fallback mekanizmasının aktif olduğundan emin olunmalıdır. Log dosyaları takip edilerek SDL video sürücüsü gerekirse değiştirilebilir:
  ```bash
  SDL_VIDEODRIVER=x11 ./QuadrixDemo
  ```

### 6.3 Dosya İzinleri
* Paketleme sonrasında üretilen `.elf` dosyasının çalıştırılabilir iznine sahip olduğundan emin olunmalıdır:
  ```bash
  chmod +x dist/QuadrixDemo
  ```
