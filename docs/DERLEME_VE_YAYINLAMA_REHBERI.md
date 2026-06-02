# Quadrix — Derleme ve Steam Yayınlama Rehberi

> Son güncelleme: 2026-06-02
> Kapsam: Windows (.exe) ve macOS (.app) derlemeleri + Steam'e yükleme.
> İki ayrı kod tabanı vardır:
> - **`v2/`** → Tam sürüm (Quadrix) + Playtest.
> - **`quadrix-demo/`** → Demo sürümü (Quadrix Demo).
>
> Tüm Windows derlemeleri **Python 3.12** (`py -3.12`, pygame-ce 2.5.6) ile yapılır.
> Build script'leri C++ Steam bridge'ini (`steam_net_bridge`) MSVC + CMake + pybind11 ile
> otomatik derler, ardından PyInstaller'ı çalıştırır.

---

## 0. Ön Koşullar

- **Python 3.12** kurulu (`py -3.12` çalışmalı). Farklıysa `QUADRIX_PYTHON` env'i ile yol verilebilir.
- **Visual Studio 2022** (MSVC C++) + **CMake** — Steam bridge derlemesi için.
- **PyInstaller**, **pybind11**, **pygame-ce 2.5.6** Python 3.12 ortamında kurulu.
- Steam yüklemesi için **SteamCMD** (`steamworks/sdk/tools/ContentBuilder/builder/steamcmd.exe`).

> NOT: Build script'leri `py -3.12`'yi otomatik bulur. `cd` ile script klasörüne girmeye gerek
> yoktur; script kendi repo kökünü bulur. Komutları ilgili repo kökünden çalıştırın.

---

## 1. Hızlı Başvuru — Hangi Derleme Hangi Komutla?

| Sürüm | Platform | Çıktı | Komut (repo kökünden) |
|---|---|---|---|
| **Tam (Full/Playtest)** | Windows | `dist\Quadrix.exe` | `v2`: `powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris_playtest.spec'` |
| **Tam (mağaza/full)** | Windows | `dist\Quadrix.exe` | `v2`: `powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris.spec'` |
| **Tam (İngilizce)** | Windows | `dist\Quadrix.exe` | `v2`: `powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris_en.spec'` |
| **Demo** | Windows | `dist\QuadrixDemo.exe` | `quadrix-demo`: `powershell -File .\scripts\build\build_windows_demo.ps1 -Clean -RebuildBridge` |
| **Tam** | macOS | `dist/Quadrix.app` | `v2`: `bash scripts/build/build_macos_app.sh` |
| **Demo** | macOS | `dist/QuadrixDemo.app` | `quadrix-demo`: `bash scripts/build/build_macos_demo_app.sh` |

> `-Clean`: `build/`, `dist/` ve bridge build klasörlerini siler (temiz derleme).
> `-RebuildBridge`: C++ Steam bridge'ini sıfırdan derler (kaynak değiştiyse otomatik de tetiklenir).

---

## 2. Windows Derleme — Detay

### 2.1 Tam sürüm (v2)
```powershell
# v2 repo kökünden:
powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris_playtest.spec'
```
- Steam **Playtest** (test) için: `tetris_playtest.spec` → AppID 4428040, Depot 4428041.
- Mağaza/yayın için: `tetris.spec`.
- Çıktı: `v2\dist\Quadrix.exe`.

### 2.2 Demo sürümü (quadrix-demo)
```powershell
# quadrix-demo repo kökünden:
powershell -File .\scripts\build\build_windows_demo.ps1 -Clean -RebuildBridge
```
Bu orkestratör script şunları yapar (sırayla):
1. `write_demo_config.py --mode demo` → `src/demo_config.py`'yi DEMO moduna çevirir (`IS_DEMO = True`).
2. `build_windows_exe.ps1 -SpecFile 'packaging/specs/tetris_demo.spec'` → bridge + PyInstaller.
3. Çıktıyı `dist\QuadrixDemo.exe` olarak üretir.
4. **finally:** `write_demo_config.py --mode full` → config'i tekrar FULL moda döndürür
   (kod tabanı demo modunda kalmaz; bu adım her durumda çalışır).

> ⚠️ Demo'yu doğrudan `build_windows_exe.ps1` ile derlemeyin — demo config yazılmaz/geri
> alınmaz. Daima `build_windows_demo.ps1` kullanın.

### 2.3 Steam Overlay (SDL2) paketleme garantisi
Tüm Windows spec'leri `pygame._sdl2` submodüllerini, `.pyd` dosyalarını (özellikle
`video.cp312-win_amd64.pyd`) ve pygame SDL2 DLL'lerini açıkça toplar. Build log'unda şu satır
GÖRÜLMELİDİR:
```
[spec] pygame._sdl2 .pyd eklendi: video.cp312-win_amd64.pyd
```
Görülmezse SDL2 overlay backend frozen build'de devre dışı kalır (oyun yine çalışır ama Steam
overlay/ekran görüntüsü sorunları geri döner). Detay: `docs/STEAM_OVERLAY_SDL2_REHBER_VE_DURUM.md`.

---

## 3. macOS Derleme — Detay

```bash
# v2 repo kökünden (tam sürüm):
bash scripts/build/build_macos_app.sh

# quadrix-demo repo kökünden (demo):
bash scripts/build/build_macos_demo_app.sh
```
- macOS'ta SDL2 overlay katmanı **no-op**'tur (Steam overlay sorunları macOS'ta yaşanmaz).
- Çıktı: `dist/Quadrix.app` / `dist/QuadrixDemo.app`.

---

## 4. Steam'e Yükleme (SteamCMD)

### 4.1 AppID / Depot Haritası
| Sürüm | AppID | Windows Depot | macOS Depot | App build VDF |
|---|---|---|---|---|
| Tam (Playtest) | 4428040 | 4428041 | 4428043 | `v2/steamworks/scripts/app_build_playtest.vdf` |
| Tam (Full/her iki platform) | 4428040 | 4428041 | 4428043 | `v2/steamworks/scripts/app_build_full.vdf` |
| **Demo** | **4635310** | **4635311** | (macOS: `app_build_demo_macos.vdf`) | `quadrix-demo/steamworks/scripts/app_build_demo.vdf` |

> **`SetLive` tüm VDF'lerde boştur ("")** — yani yükleme yapılır ama hiçbir branch otomatik
> canlıya alınmaz. Canlıya almak için Steamworks panelinden ilgili build manuel "Set Live"
> yapılır. Bu bilinçli/güvenli varsayılandır.

### 4.2 Demo Yükleme Komutu (AppID 4635310, Depot 4635311)
```powershell
# quadrix-demo repo kökünden, önce QuadrixDemo.exe derlenmiş olmalı (bkz. §2.2):
.\steamworks\sdk\tools\ContentBuilder\builder\steamcmd.exe +login <STEAM_KULLANICI> +run_app_build "%CD%\steamworks\scripts\app_build_demo.vdf" +quit
```
- `app_build_demo.vdf`: AppID 4635310, Depot 4635311, `SetLive ""` (canlıya alma yok).
- `depot_build_demo_windows.vdf` depo içeriğini `dist\` (veya ContentRoot) altından toplar;
  `*.pdb`, `*.log`, `*.spec`, `steam_appid.txt` ve tam-sürüm exe/app adları hariç tutulur.
- `ContentRoot`/`BuildOutput` VDF'de boşsa SteamCMD repo köküne göre çözer; gerekirse VDF'de
  `ContentRoot` = `dist` olarak ayarlanır.

> Yükleme öncesi `dist\QuadrixDemo.exe`'nin güncel olduğundan emin olun. Aynı klasörde eski
> tam-sürüm `Quadrix.exe` varsa depo VDF'i onu zaten hariç tutar.

### 4.3 Tam Sürüm (Playtest) Yükleme
```powershell
# v2 repo kökünden:
.\steamworks\sdk\tools\ContentBuilder\builder\steamcmd.exe +login <STEAM_KULLANICI> +run_app_build "%CD%\steamworks\scripts\app_build_playtest.vdf" +quit
```

---

## 5. Tipik Tam Akış (Demo Örneği)

```powershell
# 1) quadrix-demo repo köküne geç (PowerShell)
Set-Location 'C:\Users\arda demirkan\Desktop\v2_23022026\quadrix-demo'

# 2) Demo exe derle (config otomatik demo→full döner)
powershell -File .\scripts\build\build_windows_demo.ps1 -Clean -RebuildBridge

# 3) Çıktıyı doğrula
Get-Item dist\QuadrixDemo.exe

# 4) Steam'e yükle (SetLive yok; panelden manuel canlıya alınır)
.\steamworks\sdk\tools\ContentBuilder\builder\steamcmd.exe +login <STEAM_KULLANICI> +run_app_build "%CD%\steamworks\scripts\app_build_demo.vdf" +quit
```

---

## 6. Doğrulama Kontrol Listesi (her derleme sonrası)

- [ ] Build log'da `pygame._sdl2 .pyd eklendi: video.cp312-win_amd64.pyd` var.
- [ ] Build log'da `steam_net_bridge.cp312-win_amd64.pyd kopyalandi` ve `Derleme basarili` var.
- [ ] Çıktı exe oluştu (`dist\Quadrix.exe` veya `dist\QuadrixDemo.exe`).
- [ ] Demo derlemesi sonrası `src/demo_config.py` içinde `IS_DEMO = False` (full'e döndü).
- [ ] (Steam) `SetLive ""` — istenmeyen otomatik canlıya alma yok.

---

## 7. İlgili Dosyalar

- `scripts/build/build_windows_exe.ps1` — çekirdek Windows build (param: `-Clean`, `-RebuildBridge`, `-SpecFile`).
- `quadrix-demo/scripts/build/build_windows_demo.ps1` — demo orkestratör (config + spec).
- `scripts/build/write_demo_config.py` — `src/demo_config.py`'yi demo/full moduna yazar.
- `scripts/build/build_macos_app.sh` / `build_macos_demo_app.sh` — macOS derleme.
- `packaging/specs/*.spec` — PyInstaller spec'leri (Windows spec'lerinde pygame._sdl2 toplama).
- `steamworks/scripts/app_build_*.vdf` + `depot_build_*.vdf` — Steam yükleme yapılandırması.
- `steamworks/sdk/tools/ContentBuilder/builder/steamcmd.exe` — yükleme aracı.
- `docs/STEAM_OVERLAY_SDL2_REHBER_VE_DURUM.md` — overlay mimarisi ve sorun giderme.
