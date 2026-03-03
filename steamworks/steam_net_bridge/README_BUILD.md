# Quadrix Online PvP — Steam Net Bridge Kurulum Rehberi

## Gereksinimler

1. **Steamworks SDK** (ücretsiz)
   - İndir: https://partner.steamgames.com → SDK indirme bağlantısı
   - Çıkar: `steamworks/sdk/` dizinine

2. **Visual Studio 2019 veya 2022** (C++ desktop development workload)
   - Veya: Visual Studio Build Tools (daha hafif)

3. **CMake 3.18+**
   ```
   winget install cmake
   ```

4. **Pybind11**
   ```
   pip install pybind11
   ```

## Dosya Yapısı (SDK çıkarıldıktan sonra)

```
steamworks/
├── sdk/
│   ├── public/
│   │   └── steam/
│   │       ├── steam_api.h
│   │       ├── isteammatchmaking.h
│   │       ├── isteamnetworkingmessages.h
│   │       └── ...
│   └── redistributable_bin/
│       └── win64/
│           ├── steam_api64.dll
│           └── steam_api64.lib
├── steam_net_bridge/
│   ├── steam_net_bridge.cpp    ← C++ kaynak
│   ├── CMakeLists.txt          ← Build yapılandırması
│   └── build.bat               ← Windows derleme scripti
└── ...
```

## Derleme

```bat
cd steamworks\steam_net_bridge
build.bat
```

Başarılı olursa proje kökünde `steam_net_bridge.pyd` dosyası oluşur.

## Test

```python
# Python konsolunda:
import steam_net_bridge
bridge = steam_net_bridge.SteamNetBridge()
print(bridge.init())  # True dönmeli (Steam client açık olmalı)
print(bridge.get_my_steam_id())
```

## Oyunda Kullanım

Ana menüde "Online PvP" seçeneği görünür. Akış:
1. **Özel Lobi Oluştur** → Arkadaş davet et (Steam overlay)
2. **Herkese Açık Lobi** → Açık eşleşme
3. **Maç Bul** → Mevcut lobileri listele
4. İki oyuncu hazır olunca 3-2-1 geri sayım → Maç başlar!

## Mimari Özet

```
┌────────────────────────────┐
│   Python: online_pvp_game  │  ← Pygame oyun döngüsü
│   Python: steam_networking │  ← Yüksek seviye wrapper
└──────────┬─────────────────┘
           │ Her frame: tick() poll_events() poll_messages()
           ▼
┌──────────────────────────────┐
│   C++: steam_net_bridge.pyd  │  ← Pybind11 modül
│   • ISteamMatchmaking        │  ← Lobi oluştur/katıl
│   • ISteamNetworkingMessages │  ← P2P mesaj gönder/al
│   • Valve SDR relay          │  ← IP gizleme, düşük ping
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│   steam_api64.dll            │  ← Valve Steam Client
│   Valve Global Network       │  ← Ücretsiz relay sunucuları
└──────────────────────────────┘
```

## Sorun Giderme

- **"steam_net_bridge.pyd bulunamadı"**: `build.bat` çalıştırın
- **"Steamworks SDK bulunamadı"**: `steamworks/sdk/` altına SDK çıkarın
- **"cmake bulunamadı"**: `winget install cmake` veya cmake.org'dan indirin
- **Lobi oluşturulamıyor**: Steam client açık ve giriş yapılmış olmalı
- **Overlay çalışmıyor**: Steam → Settings → In-Game → Enable overlay
