# Build & Steam Upload Rehberi

> Quadrix — Windows Playtest (AppID: 4428040 · Depot: 4428041)  
> Son güncelleme: 2026-02-24

---

## Gereksinimler

| Araç | Konum / Sürüm |
|------|---------------|
| Python | 3.12 (`C:\Users\arda demirkan\AppData\Local\Programs\Python\Python312`) |
| PyInstaller | 6.16.0 (`py -m pip install pyinstaller`) |
| steamcmd | `C:\steamcmd\steamcmd.exe` |
| steam_api64.dll | `dll\win64\steam_api64.dll` (Steamworks SDK'dan — partner.steamgames.com/downloads/list) |
| Hesap | `vibecode_production` (Steam Partner, MFA aktif) |

---

## 1. DLL Hazırlığı

Steamworks SDK ZIP'ini partner.steamgames.com/downloads/list adresinden indirip:

```
sdk\redistributable_bin\win64\steam_api64.dll  →  dll\win64\steam_api64.dll
sdk\redistributable_bin\osx\libsteam_api.dylib  →  dll\osx\libsteam_api.dylib
```

`tetris.spec` bu dosyayı otomatik olarak bulur ve EXE içine gömer:
```python
steam_dll_src = str(REPO_ROOT / 'dll' / 'win64' / 'steam_api64.dll')
binaries = [(steam_dll_src, '.')]   # _MEIPASS'a çıkarılır, EXE yanında ayrı dosya gerekmez
```

> **ÖNEMLİ (Online PvP):** EXE/.app derlemeden önce `steam_net_bridge` derlemesi zorunludur.  
> Zorunlu adımlar ve platform bazlı komutlar için: [EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md)

---

## 2. Build (Windows EXE)

```powershell
cd "C:\Users\arda demirkan\Desktop\v2_23022026\v2"
py -m PyInstaller tetris.spec --noconfirm
```

- Çıktı: `dist\Quadrix.exe` (~315 MB, onefile)
- `steam_api64.dll` EXE **içine gömülür** — çalışma anında `_MEIPASS` geçici klasörüne çıkarılır
- `steam_appid.txt` (içerik: `4428040`) proje kökünde bulunmalı; PyInstaller bunu `datas` ile pakete ekler

Build log kaydetmek için:
```powershell
py -m PyInstaller tetris.spec --noconfirm 2>&1 | Tee-Object build_log.txt
```

---

## 3. VDF Politikası (Ortak Dosya)

`steamworks\scripts\app_build_playtest.vdf` artık **ortak şablon** dosyadır. Bu dosyada makineye özel `ContentRoot / BuildOutput` veya günlük `Desc` değişikliği commit etmeyin:

```vdf
"AppBuild"
{
    "AppID"        "4428040"
    "Desc"         "Playtest build"
    "SetLive"      ""
    "ContentRoot"  ""
    "BuildOutput"  ""

    "Depots"
    {
        "4428041"  "depot_build_playtest_windows.vdf"
    }
}
```

- `SetLive ""` → sadece upload, branch'e otomatik push **yapılmaz**
- Runtime değerleri upload scripti tarafından geçici VDF'e yazılır

---

## 4. Steam Upload

### Yöntem A — PS1 scripti (önerilen)

```powershell
.\tools\steam_upload_playtest.ps1 `
    -SteamCmdPath "C:\steamcmd\steamcmd.exe" `
    -SteamUser "vibecode_production" `
    -BuildDescription "Playtest build 2026-03-03 v1.0.27" `
    -SetLive ""
```

Şifre sorulursa girilir; Steam Guard kodu (e-posta) sorulabilir.

### Yöntem B — Doğrudan steamcmd

```powershell
C:\steamcmd\steamcmd.exe `
    +login vibecode_production `
    +run_app_build "C:\Users\arda demirkan\Desktop\v2_23022026\v2\steamworks\scripts\app_build_playtest.vdf" `
    +quit
```

### Upload Sonrası

Başarılı upload çıktısından BuildID okunur:
```
BuildID : 22071739   (2026-02-24 v3 steam-sdk-dll)
```

Steamworks Partner panelinden (partner.steamgames.com/apps/builds/4428040) build'ı **Playtest** branch'ine al.

---

## 5. Steam SDK Entegrasyonu (`src/steam_integration.py`)

Build'a dahil edilen ctypes tabanlı Steamworks SDK wrapper:

| Fonksiyon | Açıklama |
|-----------|----------|
| `init()` | `SteamAPI_Init()` çağırır; persona adını okur |
| `get_persona_name()` | Oturum açık Steam kullanıcı adı |
| `get_auth_session_ticket()` | Arkadaş skor doğrulaması için token |
| `submit_score(mode, score)` | `UploadLeaderboardScore` (KeepBest), async |
| `fetch_global_scores(mode)` | SDK üzerinden global skor listesi |
| `fetch_friend_scores(mode)` | SDK üzerinden arkadaş skor listesi |

DLL yükleme öncelik sırası (`_find_dll()`):
1. `sys._MEIPASS` (PyInstaller bundle)
2. Çalışma dizini (`cwd`)
3. Proje kökü
4. `dll/win64/` (geliştirme ortamı)
5. `dist/`
6. `C:\Program Files (x86)\Steam`

DLL bulunamazsa `init()` sessizce `False` döner; tüm Steam özellikleri no-op olarak çalışır.

---

## 6. macOS Build

macOS build Mac üzerinde yapılmalıdır:

İlk bootstrap sonrası macOS yerel sürüm dosyası bir kez kontrol edilmelidir:

```bash
ls src/version_local_macos.py
git update-index --skip-worktree src/version_local_macos.py
```

- `src/version_local_macos.py` bu aşamada bilerek track edilir ve Mac'e ilk kopya olarak repo'dan gelir
- Bu komuttan sonra macOS build artışları dosyayı yerelde güncelleyebilir; normal geliştirme akışında commit edilmemelidir
- Gerekirse senkronizasyon için skip-worktree kaldırma komutu: `git update-index --no-skip-worktree src/version_local_macos.py`

```bash
# Mac'te proje kökünde:
cp dll/osx/libsteam_api.dylib libsteam_api.dylib   # ya da spec otomatik bulur
pyinstaller tetris_macos.spec --noconfirm
```

Çıktı: `dist/Quadrix.app` — `libsteam_api.dylib` `Contents/MacOS/` içine kopyalanır.

macOS upload için `steamworks\scripts\app_build_playtest_macos.vdf` kullanılır.

---

## 7. Hızlı Özet

```
1. dll\win64\steam_api64.dll var mı? kontrol et
2. app_build_playtest.vdf → Desc tarihini güncelle
3. py -m PyInstaller tetris.spec --noconfirm
4. .\tools\steam_upload_playtest.ps1 -SteamCmdPath C:\steamcmd\steamcmd.exe -SteamUser vibecode_production
5. BuildID'yi partner.steamgames.com'dan Playtest branch'ine al
```
