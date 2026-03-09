# Steam Playtest Yayın Rehberi (Quadrix)

Bu rehber, Steam dokümanlarındaki `Uploading to Steam` ve `Steam Playtest` akışlarını bu repo için pratik hale getirir.

## 1) Steamworks panelinde zorunlu hazırlık

1. Ana oyunun **Associated Packages & DLC** sayfasından bir **Playtest AppID** oluştur.
2. Playtest uygulamasında en az şu ayarları tamamla ve publish et:
   - Library capsule / community assets
   - General Installation > en az 1 launch option
   - Depots > en az 1 depot (Windows için)
3. Ana oyunun store sayfasında **Special Settings** altından Playtest kayıt alanını görünür yap (isteğe bağlı zamanlama).

## 2) Bu repodaki SteamPipe scriptlerini doldur

Dosyalar:
- `steamworks/scripts/app_build_playtest.vdf`
- `steamworks/scripts/depot_build_playtest_windows.vdf`

Aşağıdaki placeholder değerleri gerçek ID'lerle değiştir:
- `__PLAYTEST_APP_ID__`
- `__PLAYTEST_DEPOT_WINDOWS_ID__`
- `__BUILD_DESC__` (örn. `2026-02-17-rc1`)

> Not: `ContentRoot` şu an `..\\..\\dist\\` olarak ayarlı. PyInstaller çıktını farklı klasöre alıyorsan güncelle.

## 3) Build al

Önce oyunun dağıtım dosyasını üret:

```powershell
python -m PyInstaller packaging/specs/tetris.spec --noconfirm
```

## 4) SteamCMD ile Playtest yükle

Steamworks SDK içindeki `steamcmd.exe` yolunu kullan.

### Önerilen (bu repodaki helper script)

```powershell
pwsh -File .\tools\steam_upload_playtest.ps1 \
  -SteamCmdPath "C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" \
  -SteamUser "BUILD_ACCOUNT" \
  -AppBuildScript ".\steamworks\scripts\app_build_playtest.vdf"
```

İlk girişte Steam Guard doğrulaması gerekebilir. CI/CD için Steam `config.vdf` token'ını koru.

### Doğrudan steamcmd

```powershell
"C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" +login BUILD_ACCOUNT +run_app_build ".\steamworks\scripts\app_build_playtest.vdf" +quit
```

## 5) Build’i canlıya al ve oyuncu kabul et

1. Playtest app için **Builds** sayfasına git, yüklenen BuildID’nin `playtest` branch’inde live olduğundan emin ol.
2. Playtest panelinde:
   - `Playable` durumunu aç
   - Katılım türünü seç (`Limited` veya `Open`)
   - Gerekirse ülke filtreleri uygula
3. Oyuncu davetini mağaza kaydı veya Playtest key ile yönet.

## 6) Güvenlik ve mevcut backend notu

Leaderboard için proxy modeli zaten var:
- `backend/steam_leaderboard_proxy.py`
- `src/steam_leaderboards.py`

Playtest için kod tarafında ekstra zorunlu değişiklik yok; ayrı Playtest AppID kullandığın için backend ortamında `STEAM_APP_ID` değerini Playtest AppID’ye göre ayırman yeterli.

## 7) Sık görülen hatalar

- `Invalid content configuration`: Branch’e live build atanmamış veya launch option/depot-package eşleşmesi eksik.
- `Failed to get application info`: AppID yanlış veya build hesabının yetkisi yok.
- Mac/Linux dosya inmiyor: ilgili depolar package’e eklenmemiş.
