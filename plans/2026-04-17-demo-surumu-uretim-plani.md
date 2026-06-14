# Plan: Demo Surumu Uretim Plani

**Created:** 2026-04-17  
**Last Updated:** 2026-05-11 (oyunun son kod durumu + Steam demo AppID notlari)  
**Status:** Revised Draft - Ready for Implementation

## Ozet

Quadrix icin Steam Demo paketi hazirlanacak. Demo surum, tam oyunun cekirdek hissini koruyacak ama bazi modlari, online akislarini ve kampanya ilerlemesini tam surume yonlendirecek.

Demo icin yeni Steam AppID: **4635310**. Bu AppID, demo build/spec, runtime `steam_appid.txt`, Steam entegrasyonu, leaderboard/achievement referanslari ve Steamworks panel ayarlari icin ana referans olarak kullanilacak.

Ek demo oynanis notu: **Kart Modu'nda her 5 seviyede bir gelen kart secimi demo icin her 10 seviyede bir olacak sekilde ayarlanacak.** Kod auditinde mevcut Card/Mystery akisi `MysteryCardManager.threshold = 5`, `pending_level_ups` ve level-up akisi ile iliskili gorunuyor; uygulama sirasinda kart secim tetigi demo config uzerinden 10 seviye araligina baglanmali.

---

## Kod Tabani Durumu (2026-05-11)

### Dogrulanan Noktalar

- `src/extras_menu.py`: Extras mod kartlari `_items_base` icinde tanimli. Guncel listede Classic, Sprint, Ultra, Zen, Quadrix Extra, Card Mastery, Wide, Survival, Cascade, Hardcore, Local PvP ve Online PvP kartlari var.
- `src/menu.py`: Ana menu online secimleri `online_pvp` ve `online_coop` return degerleriyle akiyor; mouse ve keyboard yollari ayri kontrol edilmeli.
- `src/campaign/level_select.py`: Solo kampanya `CampaignLevelSelect`, 5 dunya ve toplam 100 level; her dunya 20 level.
- `src/campaign/coop_level_select.py`: Co-op kampanya `CoopLevelSelect`, 2 dunya ve toplam 20 level.
- `src/game_modes_extra.py`: Card Mastery/Mystery modu kart secimlerini `MysteryCardManager`, `pending_level_ups` ve kart secim overlay'iyle yonetiyor. Mevcut esik `threshold = 5`.
- `src/steam_integration.py`: AppID runtime kaynaklarindan okunuyor; varsayilan dev AppID su an `4428040`.
- `src/steam_leaderboards.py`: AppID sirasiyla env ve runtime `steam_appid.txt` kaynaklarindan cozuluyor.
- `config/runtime/steam_appid.txt`: su an `4428040` iceriyor.
- `packaging/specs/tetris_playtest.spec`: playtest AppID olarak `4428040` set ediyor.
- Windows build girisi `scripts/build/build_windows_exe.ps1`.
- macOS build girisi `scripts/build/build_macos_app.sh`; varsayilan spec `packaging/specs/tetris_macos_allinone.spec`.
- `src/data_paths.py` app/save ayrimi icin `QUADRIX_APP_NAME` env destegi sagliyor.

### Build Uyumluluk Auditi

- Windows script uyumlu: `scripts/build/build_windows_exe.ps1` zaten `-SpecFile` parametresi aliyor. Demo build, bu scripti `-SpecFile packaging/specs/tetris_demo.spec` ile cagirabilir.
- Windows spec ayrimi sart: demo spec icindeki `EXE(..., name=...)` degeri full oyundaki `Quadrix` yerine ayri bir cikti vermeli: `QuadrixDemo.exe`.
- macOS script su an dogrudan uyumlu degil: `scripts/build/build_macos_app.sh` icinde `APP_NAME="Quadrix"` ve `SPEC_FILE="packaging/specs/tetris_macos_allinone.spec"` hardcode. Demo `.app` icin ya script `--spec`/`--app-name` parametreleri alacak hale getirilmeli ya da ayri `scripts/build/build_macos_demo_app.sh` wrapper'i eklenmeli.
- macOS spec ayrimi sart: demo spec icindeki `EXE`, `COLLECT`, `BUNDLE`, `bundle_identifier`, `CFBundleName`, `CFBundleDisplayName` ve `CFBundleExecutable` full oyundan ayrilmali.
- Demo ciktilari full oyundan bagimsiz artifact olmali:
  - Windows: `dist/QuadrixDemo.exe`
  - macOS: `dist/Quadrix Demo.app`
- Demo build ana oyunun `config/runtime/steam_appid.txt` dosyasini kalici degistirmemeli. Demo AppID icin ayri `config/runtime/steam_appid_demo.txt` spec tarafindan paket icinde `steam_appid.txt` hedefine map edilmeli.
- Demo build ana oyunun app identity/save identity degerlerini kullanmamali. Build/runtime kimligi `quadrix_demo`; macOS bundle id `com.burakyasayan.quadrix.demo` olmali.

### Revizyon Kararlari

- Demo AppID artik net: **4635310**.
- Plan, eski `XXXXXXX` ve acik soru durumundan cikarildi.
- Demo save/app identity tam oyundan ayrilacak: `QUADRIX_APP_NAME=quadrix_demo`.
- Steam runtime AppID icin paket icinde demo build'e ozel `steam_appid.txt` uretilmeli veya spec tarafindan demo dosyasi `steam_appid.txt` hedefine map edilmeli.
- Demo build full oyunun exe/app ciktilarindan bagimsiz uretilmeli: `QuadrixDemo.exe` ve `Quadrix Demo.app`.
- Kart Modu demo dengesi icin kart secim araligi notu eklendi: **her 5 seviye -> her 10 seviye**.
- Challenge Mode, Daily Challenge ve online akislar icin kilit davranislari korunuyor; UI mesajlari ortak helper ile verilmesi oneriliyor.

---

## Demo Kimligi ve Steam Referanslari

### AppID

- Full/playtest mevcut referans: `4428040`
- Demo AppID: `4635310`

### Uygulama Noktalari

- `config/runtime/steam_appid_demo.txt` yeni dosya olarak eklenmeli ve icerigi `4635310` olmali.
- Demo spec dosyalari paket icine bu dosyayi `steam_appid.txt` hedefiyle koymali.
- Demo build sirasinda `STEAM_APP_ID=4635310` veya `SteamAppId=4635310` env referansi yalnizca demo build/test akisi icin set edilmeli.
- `src/demo_config.py` icinde `DEMO_STEAM_APP_ID = "4635310"` tutulmali.
- Store URL netlesince `DEMO_STEAM_STORE_URL = "https://store.steampowered.com/app/4635310"` olarak referanslanmali.
- Steamworks tarafinda demo app icin achievement/leaderboard/cloud ayarlari full build ile karismayacak sekilde kontrol edilmeli.

---

## Hedef Demo Icerigi

### Acik Modlar

- Classic Mode
- Sprint Mode
- Ultra Mode
- Zen Mode
- Card Mastery / Kart Modu
- Wide Mode
- Local PvP
- Local Co-op
- Solo Campaign: yalnizca Dunya 1, level 1-20
- Co-op Campaign: yalnizca Dunya 1, level 1-10

### Kilitli veya Sinirli Modlar

- Quadrix Extra: tam kilit
- Challenge Mode: intro/sinirli kilit; ilk 20 asama acik, sonrasi kilitli
- Daily Challenge: tam kilit
- Survival Mode: tam kilit
- Cascade Mode: tam kilit
- Hardcore Mode: tam kilit
- Online PvP: gecis kilidi
- Online Co-op: gecis kilidi
- Solo Campaign Dunya 2-5: kilitli
- Co-op Campaign Dunya 2: kilitli

---

## Demo Oynanis Notu: Kart Modu

Kart Modu demo ayari:

- Mevcut tasarim notu: kart secimi her 5 seviyede bir.
- Demo hedefi: kart secimi her 10 seviyede bir.
- Uygulama icin onerilen config:

```python
DEMO_CARD_SELECTION_LEVEL_INTERVAL = 10
FULL_CARD_SELECTION_LEVEL_INTERVAL = 5
```

Kod notu: `src/game_modes_extra.py` icinde secim tetigi su an `MysteryCardManager.threshold = 5`, `notify_lines_cleared`, `pending_level_ups` ve level-up algisi ile baglantili. Buradaki hedef zaman bazli degil, seviye bazlidir: full buildde her 5 seviyede bir, demo buildde her 10 seviyede bir kart secim ekrani gelmeli.

---

## Kilit Tipleri

### Tip 1: Tam Kilitleme

Kilitli moda tiklaninca oyun moda gecmez; demo upgrade modal/toast gosterilir.

Uygulanacaklar:

- Quadrix Extra
- Daily Challenge
- Survival Mode
- Cascade Mode
- Hardcore Mode

Mesaj:

```text
Bu mod tam surumde mevcut.
[Steam'de ac] [Kapat]
```

### Tip 2: Kismi Kilitleme

Mod veya kampanya girisi acik kalir, demo siniri disindaki level/dunya secilemez.

Uygulanacaklar:

- Challenge Mode: ilk 20 asama acik, 21+ kilitli
- Solo Campaign: level 1-20 acik, 21-100 kilitli
- Co-op Campaign: level 1-10 acik, 11-20 kilitli

Mesaj:

```text
Demo bu bolumun ilk asamalarini icerir. Devamini tam surumde oyna.
[Steam'de ac] [Kapat]
```

### Tip 3: Gecis Kilitleme

Ana menu icindeki online secimler secildiginde tam surume yonlendirme gosterilir.

Uygulanacaklar:

- Online PvP
- Online Co-op

Mesaj:

```text
Cevrimici oyunlar tam surumde mevcut.
[Steam'de ac] [Menuye don]
```

---

## Faz Plani

### Faz 1 - Demo Config Altyapisi

Yeni dosyalar:

- `src/demo_config.py`
- `scripts/build/write_demo_config.py`
- `config/runtime/steam_appid_demo.txt`

`src/demo_config.py` hedef icerik:

```python
IS_DEMO = False

DEMO_STEAM_APP_ID = "4635310"
DEMO_STEAM_STORE_URL = "https://store.steampowered.com/app/4635310"
DEMO_APP_NAME = "quadrix_demo"

DEMO_LOCKED_EXTRAS_MODE_IDS = {
    "Quadrix Extra",
    "Daily Challenge",
    "Survival Mode",
    "Cascade Mode",
    "Hardcore Mode",
}

DEMO_PARTIAL_EXTRAS_MODE_IDS = {"Challenge Mode"}
DEMO_LOCKED_MAIN_ACTIONS = {"online_pvp", "online_coop"}

DEMO_CHALLENGE_UNLOCKED_STAGES = 20
DEMO_SOLO_WORLD_LIMIT = 1
DEMO_SOLO_LEVEL_LIMIT = 20
DEMO_COOP_WORLD_LIMIT = 1
DEMO_COOP_LEVEL_LIMIT = 10

DEMO_CARD_SELECTION_LEVEL_INTERVAL = 10
FULL_CARD_SELECTION_LEVEL_INTERVAL = 5
```

`write_demo_config.py`:

- `--mode full|demo` argumani alir.
- Dosyayi deterministik yazar.
- Demo modda `IS_DEMO=True`, AppID `4635310`, AppName `quadrix_demo`.
- Build sonunda full config'e geri donus desteklenir.
- Demo wrapper scriptleri hata alsa bile `finally`/`trap` ile full config'e geri donmek zorundadir; kaynak agac demo modda birakilmamali.

### Faz 2 - Steam AppID ve Runtime Paketleme

Dosyalar:

- `config/runtime/steam_appid_demo.txt`
- `packaging/specs/tetris_demo.spec`
- `packaging/specs/tetris_demo_macos_allinone.spec`
- `scripts/build/build_windows_demo.ps1`
- `scripts/build/build_macos_demo_app.sh`

Kural:

- Demo paket icinde `steam_appid.txt` hedefinin icerigi `4635310` olmali.
- Full/playtest `4428040` dosyasi yanlislikla demo paketine girmemeli.
- `steam_integration._read_app_id_from_runtime_sources()` demo buildde runtime dosyasindan `4635310` okumali.
- `steam_leaderboards.py` demo AppID ile ayri leaderboard ref kullaniyorsa `LEADERBOARD_APP_ID=4635310` veya runtime okuma test edilmeli.

Bagimsiz artifact kurali:

- Demo, ana oyunun exe/app dosyasini overwrite etmeden uretilmeli.
- Windows demo cikti adi: `dist/QuadrixDemo.exe`.
- macOS demo cikti adi: `dist/Quadrix Demo.app`.
- Demo artifactleri Steam'e demo AppID `4635310` altinda yuklenmeli; full/playtest artifactleriyle ayni depot/cikti adi varsayilmamali.

#### Windows Demo Build Akisi

Mevcut script uyumlu oldugu icin demo wrapper ince tutulacak:

```powershell
scripts/build/build_windows_exe.ps1 -SpecFile packaging/specs/tetris_demo.spec
```

`scripts/build/build_windows_demo.ps1` sorumluluklari:

- `write_demo_config.py --mode demo` calistir.
- `scripts/build/build_windows_exe.ps1 -SpecFile packaging/specs/tetris_demo.spec` cagir.
- `finally` blogunda `write_demo_config.py --mode full` calistir.
- Cikti olarak `dist/QuadrixDemo.exe` bekle ve yoksa fail et.

`packaging/specs/tetris_demo.spec` farklari:

- `os.environ.setdefault('STEAM_APP_ID', '4635310')`
- datas icinde `config/runtime/steam_appid_demo.txt` kaynak dosyasi paket icinde `steam_appid.txt` olarak yer almali.
- `EXE(..., name='QuadrixDemo', ...)`
- Hidden importlar full spec ile ayni kalabilir; online modlar demo UI'da kilitli olsa bile Steam SDK/bridge bulunmasi runtime init ve store/overlay uyumu icin sorun yaratmaz.
- Version bump full Windows version dosyasini zorunlu degistirmemeli; demo icin bump kapali veya ayri `windows_demo` version dosyasi kullanilmali.

#### macOS Demo Build Akisi

Mevcut `scripts/build/build_macos_app.sh` dogrudan demo spec alamadigi icin iki secenekten biri uygulanmali; plan karari wrapper/script parametresi eklemektir.

Onerilen yol:

- `build_macos_app.sh` icine `--spec <path>` ve `--app-name <name>` parametreleri ekle.
- `scripts/build/build_macos_demo_app.sh` bu scripti su sekilde cagirir:

```bash
scripts/build/build_macos_app.sh \
  --spec packaging/specs/tetris_demo_macos_allinone.spec \
  --app-name "Quadrix Demo"
```

`scripts/build/build_macos_demo_app.sh` sorumluluklari:

- `write_demo_config.py --mode demo` calistir.
- Demo spec ile macOS build'i baslat.
- `finally`/`trap` ile `write_demo_config.py --mode full` calistir.
- Cikti olarak `dist/Quadrix Demo.app` bekle ve yoksa fail et.

`packaging/specs/tetris_demo_macos_allinone.spec` farklari:

- datas icinde `config/runtime/steam_appid_demo.txt` paket icinde `steam_appid.txt` olarak yer almali.
- Bundle icindeki executable adi bosluksuz tutulmali: `EXE(..., name='QuadrixDemo', ...)`.
- `COLLECT(..., name='QuadrixDemo')`
- `BUNDLE(..., name='Quadrix Demo.app', bundle_identifier='com.burakyasayan.quadrix.demo', ...)`
- `CFBundleName = 'Quadrix Demo'`
- `CFBundleDisplayName = 'Quadrix Demo'`
- `CFBundleGetInfoString = 'Quadrix Demo - Steam Demo'`
- `CFBundleIdentifier = 'com.burakyasayan.quadrix.demo'`
- `CFBundleExecutable = 'QuadrixDemo'`

### Faz 3 - Extras Ekraninda Kilitleme

Dosya:

- `src/extras_menu.py`

Uygulama:

- Kart ciziminde demo kilit overlay'i ve badge.
- `handle_input` icinde keyboard ve mouse secimlerinden once demo kilit kontrolu.
- Tam kilitli modlarda return engellenir ve upgrade prompt acilir.
- Challenge Mode secimi level secime gecmeye devam eder; 20 sonrasi level seciminde kilitlenir.

### Faz 4 - Ana Menu Online Kilitleri

Dosya:

- `src/menu.py`

Uygulama:

- `online_pvp` ve `online_coop` return noktalarinda `IS_DEMO` kontrolu.
- Mouse ve keyboard akislari birlikte korunur.
- Local PvP ve local Co-op davranisi degismez.

### Faz 5 - Kampanya Sinirlari

Solo:

- Dosya: `src/campaign/level_select.py`
- `CampaignLevelSelect._is_level_unlocked(level_num)` demo limitleriyle sarilir.
- Dunya 2-5 tab gecisi demo modda engellenir veya kilit prompt verir.
- Level 21-100 kilitli gorsel alir.

Co-op:

- Dosya: `src/campaign/coop_level_select.py`
- `CoopLevelSelect._is_level_unlocked(level_num)` demo limitleriyle sarilir.
- Dunya 2 tab'i demo modda kilitli gosterilir.
- Level 11-20 kilitli gorsel alir.

### Faz 6 - Kart Modu Demo Araligi

Dosya:

- `src/game_modes_extra.py`

Uygulama:

- Kart secim araligi tek config noktasindan okunur.
- Demo modda kart secimi her 10 seviyede bir olacak sekilde ayarlanir.
- Full build davranisi her 5 seviyede bir olarak korunur.
- Mevcut `threshold = 5` satir/level tetigiyle cakisiyorsa test once mevcut davranisi belgelendirir, sonra kart secim level araligi config'e ayrilir.

### Faz 7 - Save/App Ayrimi

Dosyalar:

- `src/main.py` veya en erken bootstrap noktasi
- `src/demo_config.py`

Uygulama:

```python
if IS_DEMO:
    os.environ.setdefault("QUADRIX_APP_NAME", DEMO_APP_NAME)
```

Sonuc:

- Demo ve full save/cloud/local path'leri karismaz.
- Steam Cloud ayarlari demo AppID `4635310` icin ayrica kontrol edilir.

### Faz 8 - Ortak Demo Prompt Katmani

Yeni dosya:

- `src/demo_upgrade_prompt.py`

Icerik:

- `show_demo_full_lock_prompt(...)`
- `show_demo_partial_lock_prompt(...)`
- `show_demo_transition_lock_prompt(...)`
- `webbrowser.open(DEMO_STEAM_STORE_URL)`

Kullanacak yerler:

- `src/extras_menu.py`
- `src/menu.py`
- `src/campaign/level_select.py`
- `src/campaign/coop_level_select.py`

### Faz 9 - Testler

Yeni veya guncellenecek testler:

- `tests/test_demo_config.py`
- `tests/test_demo_steam_appid.py`
- `tests/test_demo_build_specs.py`
- `tests/test_demo_menu_locks.py`
- `tests/test_demo_campaign_limits.py`
- `tests/test_demo_card_mode_interval.py`

Kapsam:

- Demo config writer full/demo ciktilarini dogru uretiyor.
- Demo AppID `4635310` runtime dosyasindan okunuyor.
- Demo spec `steam_appid_demo.txt` dosyasini `steam_appid.txt` olarak paketliyor.
- Windows demo spec `EXE` adini `QuadrixDemo` yapiyor.
- macOS demo spec `Quadrix Demo.app`, `com.burakyasayan.quadrix.demo` ve `CFBundleDisplayName = Quadrix Demo` degerlerini iceriyor.
- Windows demo wrapper mevcut `build_windows_exe.ps1 -SpecFile packaging/specs/tetris_demo.spec` yolunu kullaniyor.
- macOS demo wrapper veya parametreli script demo spec'i ve `Quadrix Demo` app adini kullaniyor.
- Demo wrapper scriptleri build hata alsa bile `write_demo_config.py --mode full` geri donusunu garanti ediyor.
- Extras tam kilitli modlari return etmiyor.
- Online PvP/Co-op demo modda return etmiyor.
- Solo level 1-20 acik, 21+ kilitli.
- Co-op level 1-10 acik, 11+ kilitli.
- Kart Modu demo araligi 10 seviye, full araligi 5 seviye.
- `QUADRIX_APP_NAME=quadrix_demo` path ayrimini sagliyor.

---

## Uygulama Sirasi

1. Demo config + AppID dosyasi (`4635310`)
2. Demo spec ve wrapper scriptleri: `QuadrixDemo.exe`, `Quadrix Demo.app`
3. Steam AppID paketleme/spec ayrimi
4. Save/app identity ayrimi
5. Extras/menu/kampanya kilitleri
6. Kart Modu her 5 seviye -> her 10 seviye demo ayari
7. Ortak prompt UI
8. Testler ve paket smoke test

---

## Paketleme Smoke Test Checklist

- Demo build acilista Steam runtime AppID olarak `4635310` goruyor.
- Paket icindeki `steam_appid.txt` icerigi `4635310`.
- Windows demo artifacti `dist/QuadrixDemo.exe` olarak uretiliyor.
- macOS demo artifacti `dist/Quadrix Demo.app` olarak uretiliyor.
- macOS demo `Info.plist` icinde bundle id `com.burakyasayan.quadrix.demo`, display name `Quadrix Demo`.
- Demo build ana oyunun `dist/Quadrix.exe` veya `dist/Quadrix.app` ciktilarini artifact adi olarak kullanmiyor.
- Full/playtest build hala `4428040` referansini kullanabiliyor.
- Demo save klasoru full build ile ayriliyor.
- Kilitli modlar secimde oyunu baslatmiyor.
- Store butonu demo Steam sayfasina gidiyor.
- Kart Modu demo buildde her 10 seviyede bir secim veriyor.
- Solo kampanya 20. levelden sonra kilit gosteriyor.
- Co-op kampanya 10. levelden sonra kilit gosteriyor.

---

## Non-Goals

- Demo -> full save/progress migration
- Demo'ya ozel yeni level veya yeni kart icerigi
- Matchmaking tarafinda demo-ozel lobby sistemi
- Notarization/codesign otomasyonunun yeniden tasarimi
- Steamworks panelindeki ticari metinlerin bu repo icinden yonetilmesi

---

## Kapanan Sorular

- Demo AppID: **4635310**
- Demo store URL referansi: `https://store.steampowered.com/app/4635310`
- Demo Windows cikti adi: `QuadrixDemo.exe`
- Demo macOS cikti adi: `Quadrix Demo.app`
- Demo macOS bundle id: `com.burakyasayan.quadrix.demo`
- Demo acik kampanya kapsami: Solo Dunya 1 level 1-20, Co-op Dunya 1 level 1-10
- Demo online politikasi: Online PvP ve Online Co-op kilitli
- Demo Kart Modu hedefi: her 5 seviyede bir kart secimi yerine her 10 seviyede bir kart secimi

## Acik Sorular

1. Demo AppID altinda leaderboard/achievement isimleri full build ile ayni mi kalacak, yoksa demo icin ayri namespace mi kullanilacak?
2. Kart Modu'ndaki mevcut `threshold = 5` davranisi dogrudan kart secim level araligi mi, yoksa satir/level ilerleme esigi mi? Implementasyonda bu ayrim netlestirilip demo icin 10 seviye araligi uygulanacak.
