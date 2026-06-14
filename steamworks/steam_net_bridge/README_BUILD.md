# Quadrix Steam Net Bridge Build Rehberi

Bu klasördeki native modül, Quadrix'in Steam tabanlı ağ katmanını Python tarafına açan köprüdür. Online PvP lobi, mesajlaşma ve Steam networking işlemleri bu build çıktısına dayanır.

> **Bu dosya nedir?** Köprünün kanonik derleme rehberi (Windows / macOS / Linux).
> **Bu dosya ne değil?** Online PvP mimari/akış rehberi (orası [../../docs/ONLINE_PVP_ARCHITECTURE.md](../../docs/ONLINE_PVP_ARCHITECTURE.md) içinde) veya EXE/.app paketleme rehberi (orası generated [../../docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](../../docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md) içinde).

## Ne Derleniyor?

- Pybind11 ile oluşturulan `steam_net_bridge` modülü
- Steamworks SDK başlıkları ve platform kütüphaneleri ile linklenen native artifact
- Çıktı olarak runtime tarafından okunacak dosyalar `local_artifacts/bridge` altına kopyalanır

## Gereksinimler

### Ortak

1. Steamworks SDK
   - İndirme: https://partner.steamgames.com
   - Konum: `steamworks/sdk/`
   - Beklenen örnek dosya: `steamworks/sdk/public/steam/steam_api.h`

2. Python
   - **Önerilen ve birincil hedef:** 3.12 (proje `pyproject.toml` `requires-python = ">=3.12"`)
   - 3.11 köprüsü tarihsel olarak desteklenmiştir; yeni paketler için 3.12 kullanın.
   - İsterseniz build scriptlerine `QUADRIX_PYTHON` ortam değişkeni ile özel yorumlayıcı verebilirsiniz

3. CMake 3.18+

4. pybind11
   - Scriptler eksikse yüklemeyi dener
   - Elle kurmak isterseniz: `python3.12 -m pip install pybind11`

### Windows

- Visual Studio 2022 veya 2019
- C++ desktop development workload
- Alternatif olarak Visual Studio Build Tools

### macOS

- Xcode Command Line Tools

```bash
xcode-select --install
```

### Linux

- GCC veya Clang araç zinciri
- Tipik paket: `build-essential`

## Beklenen Dizin Yapısı

```text
steamworks/
├── sdk/
│   ├── public/steam/steam_api.h
│   ├── redistributable_bin/win64/steam_api64.lib
│   ├── redistributable_bin/osx/libsteam_api.dylib
│   └── redistributable_bin/linux64/libsteam_api.so
└── steam_net_bridge/
    ├── CMakeLists.txt
    ├── steam_net_bridge.cpp
    ├── build.bat
    └── build.sh
```

## Derleme

### Windows

```bat
cd steamworks\steam_net_bridge
build.bat
```

Build scripti:

- önce `py -3.12`, sonra sistem Python'unu dener
- Visual Studio 2022 jeneratörünü, gerekirse 2019'u kullanır
- çıktıyı `local_artifacts\bridge` altına kopyalar

### macOS / Linux

```bash
cd steamworks/steam_net_bridge
chmod +x build.sh
./build.sh
```

Notlar:

- macOS tarafında script varsayılan olarak universal build hedefleyebilir
- Gerekirse `QUADRIX_MACOS_ARCHS` ile mimari listesini değiştirebilirsiniz
- Çıktı yine `local_artifacts/bridge` altına kopyalanır

## Build Sonucu

Başarılı bir build sonrası beklenen hedefler:

- `local_artifacts/bridge/steam_net_bridge*.pyd` veya `*.so`
- macOS için ayrıca `local_artifacts/bridge/libsteam_api.dylib`

Repodaki runtime ve paketleme akışı bu klasörü öncelikli kullanır.

## Hızlı Doğrulama

Build sonrası Python tarafında test etmek için:

```python
import sys
sys.path.insert(0, "local_artifacts/bridge")

import steam_net_bridge

bridge = steam_net_bridge.SteamNetBridge()
print(bridge.init())
print(bridge.get_my_steam_id())
```

`bridge.init()` çağrısının başarılı olması için Steam istemcisinin açık ve oturumun giriş yapılmış olması gerekir.

## Runtime Notları

- Online PvP akışı Steam client'a bağlıdır
- Overlay tabanlı davet akışları için Steam overlay açık olmalıdır
- Python sürümü ile build artifact sürümü eşleşmelidir; yanlış yorumlayıcıyla derlerseniz modül import edilmeyebilir

## Sık Görülen Sorunlar

### Steamworks SDK bulunamadı

- SDK'yı `steamworks/sdk/` altına yanlış seviyede çıkarmış olabilirsiniz
- `public/steam/steam_api.h` dosyasının gerçekten mevcut olduğunu kontrol edin

### cmake bulunamadı

Windows:

```powershell
winget install cmake
```

macOS:

```bash
brew install cmake
```

### pybind11 bulunamadı

```bash
python3.12 -m pip install pybind11
```

### Modül import edilemiyor

- Build'i kullandığınız Python sürümü ile oyunu çalıştırdığınız Python sürümü eşleşmiyor olabilir
- `local_artifacts/bridge` altında gerçekten yeni artifact oluştuğunu kontrol edin

### Steam tarafı bağlanmıyor

- Steam istemcisini açın
- Hesabın giriş yapmış olduğundan emin olun
- Overlay kapalıysa lobi davetleri beklendiği gibi çalışmayabilir

## İlgili Dokümanlar

- Ana proje özeti: [../../README.md](../../README.md)
- Online PvP mimarisi: [../../docs/ONLINE_PVP_ARCHITECTURE.md](../../docs/ONLINE_PVP_ARCHITECTURE.md)
- Online PvP akış notları: [../../docs/ONLINE_PVP_FLOW_TR.md](../../docs/ONLINE_PVP_FLOW_TR.md)
- Build ve yayın rehberi: [../../docs/BUILD_AND_UPLOAD.md](../../docs/BUILD_AND_UPLOAD.md)
