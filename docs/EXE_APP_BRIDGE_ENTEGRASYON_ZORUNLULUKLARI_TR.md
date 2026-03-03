# EXE / .app Derlemede Steam Bridge Entegrasyonu (Zorunlu)

Bu doküman, Online PvP için gereken `steam_net_bridge` (Pybind11 C++ modülü) entegrasyonunun
Windows EXE ve macOS `.app` derlemelerine **eksiksiz dahil edilmesi** için zorunlu adımları içerir.

## Neden zorunlu?

`steam_net_bridge` olmadan Online PvP açılmaz ve lobi işlemleri çalışmaz.

- Runtime belirti: `steam_net_bridge.pyd bulunamadi. Derleme gerekli.`
- Sonuç: Özel lobi / açık lobi / davet akışı devreye giremez.

---

## Bu projede bridge için yapılan kritik değişiklikler

Aşağıdaki değişiklikler derleme sürecine **dahil edilmelidir**:

1. `steamworks/steam_net_bridge/build.bat`
   - Python seçimi deterministik hale getirildi.
   - `QUADRIX_PYTHON` env var destekleniyor.
   - Varsayılan olarak `py -3.12` tercih ediliyor.
   - Python ABI’ye göre ayrı build klasörü kullanılıyor: `build_py<major><minor>` (örn. `build_py312`).
   - CMake çağrısına şunlar ekleniyor:
     - `-DPYBIND11_FINDPYTHON=ON`
     - `-DPython_EXECUTABLE=...`
     - `-DPYTHON_EXECUTABLE=...`

2. `steamworks/steam_net_bridge/build.sh`
   - `QUADRIX_PYTHON` destekleniyor.
   - Varsayılan Python seçimi 3.12 öncelikli (`python3.12` -> `python3` -> `python`).
   - Python ABI’ye göre build klasörü kullanılıyor: `build_py<major><minor>`.
   - CMake’e Python executable ve `PYBIND11_FINDPYTHON=ON` veriliyor.
   - `EXT_SUFFIX` ile doğru artifact (`.so`) bulunup köke kopyalanıyor.
   - macOS için `QUADRIX_MACOS_ARCHS` override destekleniyor (varsayılan: `arm64;x86_64`).

3. `steamworks/steam_net_bridge/CMakeLists.txt`
   - `set(PYBIND11_FINDPYTHON ON)`
   - `find_package(Python COMPONENTS Interpreter Development REQUIRED)`
   - `find_package(pybind11 REQUIRED)`

4. Spec dosyaları bridge binary’sini topluyor
   - `tetris.spec`
   - `tetris_macos.spec`
   - `tetris_playtest.spec`
   
   Bu dosyalar proje kökündeki `steam_net_bridge*.pyd` ve `steam_net_bridge*.so` dosyalarını
   `binaries` listesine ekleyecek şekilde yapılandırılmıştır.

---

## Windows EXE build akışı (zorunlu)

## 1) Bridge’i önce derle

```powershell
cd steamworks\steam_net_bridge
build.bat
```

İsteğe bağlı (belirli Python):

```powershell
set QUADRIX_PYTHON=C:\Users\<kullanici>\AppData\Local\Programs\Python\Python312\python.exe
build.bat
```

## 2) Proje kökünde bridge artifact doğrula

```powershell
cd ..\..
dir steam_net_bridge*.pyd
```

Beklenen örnek: `steam_net_bridge.cp312-win_amd64.pyd`

## 3) EXE derle

```powershell
py -m PyInstaller tetris.spec --noconfirm
```

## 4) Build log’da bridge’in toplandığını doğrula

Spec içinde şu log satırı beklenir:
- `[spec] steam_net_bridge eklendi: ...`

---

## macOS .app build akışı (zorunlu)

## 1) Bridge’i önce derle

```bash
cd steamworks/steam_net_bridge
chmod +x build.sh
./build.sh
```

İsteğe bağlı (belirli Python):

```bash
export QUADRIX_PYTHON=/usr/local/bin/python3.12
./build.sh
```

İsteğe bağlı (arch override):

```bash
export QUADRIX_MACOS_ARCHS="arm64;x86_64"
./build.sh
```

## 2) Proje kökünde bridge artifact doğrula

```bash
cd ../..
ls -1 steam_net_bridge*.so
```

## 3) .app derle

- Standart spec ile:

```bash
pyinstaller tetris_macos.spec --noconfirm
```

- veya all-in-one script ile:

```bash
./build_macos_app.sh
```

---

## Derleme öncesi kısa kontrol listesi

- [ ] Steamworks SDK `steamworks/sdk/` altında mevcut
- [ ] Bridge derleme adımı EXE/.app derlemeden **önce** çalıştırıldı
- [ ] Kökte doğru ABI artifact oluştu (`cp312` vb.)
- [ ] PyInstaller spec bridge dosyasını log’da ekledi
- [ ] Üretilen build’de Online PvP ekranında lobi oluşturma çalışıyor

---

## Önemli not

EXE/.app derleme akışında bridge adımı atlanırsa paket build alabilir ama Online PvP çalışma zamanı
özellikleri eksik kalır. Bu yüzden bridge derlemesi, paketleme pipeline’ında **zorunlu pre-step** olarak
çalıştırılmalıdır.
