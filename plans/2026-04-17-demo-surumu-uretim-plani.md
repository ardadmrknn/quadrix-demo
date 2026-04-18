# Plan: Demo Surumu Uretim Plani

**Created:** 2026-04-17  
**Last Updated:** 2026-04-18 (kod tabani audit senkronu)  
**Status:** Updated Draft - Ready for Implementation

## Ozet

Quadrix icin Steam Demo (ve/veya Next Fest) paketi hazirlanacak. Demo surumde:

- Bazi modlar kilitli olacak, secimde tam surume yonlendirme verilecek.
- Solo kampanya yalnizca Dunya 1 (level 1-20) acik olacak.
- Co-op kampanya yalnizca Dunya 1 (level 1-10) acik olacak.
- Ayri build spec ve ayri runtime AppID/app-name kullanilacak.

Bu plan mevcut kod yapisina gore guncellendi: `ExtrasScreen.handle_input`, `Menu.handle_input`, `CampaignLevelSelect` ve mevcut build scriptleri baz alindi.

---

## Kod Tabanı Durumu (2026-04-18)

### Dogrulanan Noktalar

- `src/extras_menu.py`: mod secimi `handle_input` icinden id donuyor, kart cizimi `_draw_modern_mode_card`.
- `src/menu.py`: online secimler split-polygon akisinda (`online_pvp`, `online_coop`) mouse + keyboard yolundan donuyor.
- `src/campaign/level_select.py`: sinif adi `CampaignLevelSelect`, kilit kontrolu `_is_level_unlocked`.
- `src/campaign/coop_level_select.py`: ayri secim sinifi (`CoopLevelSelect`), dunya yapisi 2 dunya / 20 level.
- Windows build girisi `scripts/build/build_windows_exe.ps1`.
- macOS build girisi `scripts/build/build_macos_app.sh` ve varsayilan spec `tetris_macos_allinone.spec`.
- `tools/versioning.py` yalnizca `'windows'` anahtarini destekliyor.
- `src/data_paths.py` app ayrimi icin `QUADRIX_APP_NAME` env destekliyor.

### Onceki Taslaktan Duzeltilen Hatalar

- Kampanya limiti solo icin 10 degil 20 level.
- `pygame.webbrowser` yok; dogru kullanim `webbrowser.open`.
- `extras_menu.py` icinde `_handle_card_click` yok; kilitleme `handle_input` seviyesinde yapilacak.
- `LevelSelect` yerine `CampaignLevelSelect`.
- Windows build `.sh` degil mevcut `.ps1` uzerinden akmali.
- `bump_platform_version(..., 'windows_demo'/'macos_demo')` su an desteklenmiyor.
- Save ayirimi `data_paths.py` icine hardcode degil app-name/env stratejisiyle yapilmali.

---

## Hedef Kilit Politikasi

### Extras Modlari

Acik:

- Classic Mode
- Sprint Mode
- Ultra Mode
- Zen Mode

Kilitli:

- Quadrix Extra
- Kart Ustaligi
- Wide Mode
- Survival Mode
- Cascade Mode
- Hardcore Mode

### Ana Menu

Acik:

- Campaign (solo)
- PvP local
- Co-op local

Kilitli:

- Online PvP
- Online Co-op

### Kampanya

- Solo: Dunya 1 acik, Dunya 2-5 kilitli.
- Co-op: Dunya 1 acik, Dunya 2 kilitli.

---

## Faz Plani

### Faz 1 - Demo Konfig Altyapisi

**Dosyalar:** `src/demo_config.py` (yeni), `scripts/build/write_demo_config.py` (yeni)

`src/demo_config.py` taslagi:

```python
# Build pipeline bu dosyayi yazar.
# Default: full build
IS_DEMO = False

DEMO_LOCKED_EXTRAS_MODE_IDS = {
    'Quadrix Extra',
    'Kart Ustaligi',
    'Wide Mode',
    'Survival Mode',
    'Cascade Mode',
    'Hardcore Mode',
}

DEMO_LOCKED_MAIN_ACTIONS = {'online_pvp', 'online_coop'}

# Solo campaign: world*20
DEMO_SOLO_WORLD_LIMIT = 1

# Co-op campaign: world*10
DEMO_COOP_WORLD_LIMIT = 1

DEMO_STEAM_STORE_URL = 'https://store.steampowered.com/app/XXXXXXX'
DEMO_APP_NAME = 'quadrix_demo'
```

`write_demo_config.py` gereksinimi:

- `--mode full|demo` argumani alir.
- Dosyayi deterministik yazar.
- Build sonunda `full` geri yazimi destekler.

Not: import stili proje ile uyumlu olmali (`try: from .demo_config ... except: from demo_config ...`).

---

### Faz 2 - Extras Ekraninda Kilitleme

**Dosya:** `src/extras_menu.py`

Uygulama noktasi:

- Cizim: `_draw_modern_mode_card` icinde locked overlay + `DEMO` badge.
- Input: `handle_input` icinde `RETURN/SPACE` ve mouse click donuslerinden once locked check.

Davranis:

- Kilitli mod secilirse oyun moda gecmez.
- Ortak helper ile "tam surumde mevcut" modal/toast gosterilir.
- Istek halinde `webbrowser.open(DEMO_STEAM_STORE_URL)` cagrilir.

---

### Faz 3 - Ana Menu Online Kilitleri

**Dosya:** `src/menu.py`

Uygulama noktasi:

- Keyboard akisi: `handle_input` icindeki `current_option == 'pvp_2_players'` ve `current_option == 'coop_mode'` `RETURN/SPACE` branch'leri.
- Mouse akisi: `MOUSEBUTTONDOWN` icindeki `pvp_online_polygon` / `coop_online_polygon` branch'leri.

Davranis:

- `online_pvp` veya `online_coop` donmeden once demo kilit kontrolu.
- Kilitliyse aksiyon iptal + demo upgrade modal/toast.
- Local PvP / local Co-op davranisi degismez.

---

### Faz 4 - Kampanya Kilitleme

#### 4a. Solo Kampanya

**Dosya:** `src/campaign/level_select.py`

Uygulama noktasi:

- `CampaignLevelSelect._is_level_unlocked(level_num)` icine demo siniri eklenir.
- `handle_input` icindeki dunya tab degisiminde demo world limit disina gecis engellenir.
- `_draw_world_tabs` ve `_draw_level_button` icinde demo kilidi gorseli eklenir.

Kural:

- `DEMO_SOLO_WORLD_LIMIT = 1` iken `level_num > 20` kilitli.

#### 4b. Co-op Kampanya

**Dosya:** `src/campaign/coop_level_select.py`

Uygulama noktasi:

- `CoopLevelSelect._is_level_unlocked(level_num)` demo limiti ile sarilir.
- `handle_input` icinde world tab click kontrolu eklenir.
- Grid/tab ciziminde kilitli dunya ve level gorseli verilir.

Kural:

- `DEMO_COOP_WORLD_LIMIT = 1` iken `level_num > 10` kilitli.

---

### Faz 5 - Build ve Paketleme

#### 5a. Demo Spec Dosyalari

Yeni dosyalar:

- `packaging/specs/tetris_demo.spec` (Windows)
- `packaging/specs/tetris_demo_macos_allinone.spec` (macOS)

Baz alinacaklar:

- Windows: `tetris_playtest.spec`
- macOS: `tetris_macos_allinone.spec`

Ortak farklar:

- Demo AppID runtime datasina eklenir (`config/runtime/steam_appid_demo.txt` -> paket icinde `steam_appid.txt` hedefi).
- Build basinda `write_demo_config.py --mode demo`.
- Build sonunda `write_demo_config.py --mode full` (geri donus garanti).

#### 5b. Windows Build Akisi

Mevcut script baz alinacak:

- `scripts/build/build_windows_exe.ps1 -SpecFile packaging/specs/tetris_demo.spec`

Not:

- Ayrica yeni `.sh` eklemek yerine mevcut `.ps1` tekrar kullanilacak.
- `tools/versioning.py` iki secenek:
  - Demo buildde otomatik bump yapmama (onerilen baslangic).
  - Veya `LOCAL_VERSION_FILES` icine `windows_demo` destegi ekleyip ayri lokal versiyon dosyasi tutma.

#### 5c. macOS Build Akisi

Mevcut script `scripts/build/build_macos_app.sh` su an spec'i sabitliyor. Iki yol:

- Scripti `--spec` parametreli hale getir.
- Veya demo icin kucuk wrapper script ekle ve `SPEC_FILE=tetris_demo_macos_allinone.spec` ile cagir.

---

### Faz 6 - Demo Kimligi ve Save Ayrimi

**Dosyalar:** `src/main.py` (veya erken bootstrap nokta), `src/demo_config.py`

`data_paths.py` zaten env destekli. Bu yuzden yeni hardcode gerekmez.

Yontem:

- Demo buildde erken asamada:
  - `os.environ.setdefault('QUADRIX_APP_NAME', DEMO_APP_NAME)`

Sonuc:

- Full ve demo save/cloud/local path dogal ayrilir.

---

### Faz 7 - UI Mesaj Katmani (Opsiyonel ama Onerilen)

Tekrarsiz kilit mesaji icin ortak helper modulu:

- `src/demo_upgrade_prompt.py` (yeni)

Icerik:

- `show_demo_upgrade_prompt(screen, settings_manager, ...)`
- Web acma: `webbrowser.open`
- Lokalizasyon anahtarlari: `demo_mode_locked_title`, `demo_mode_locked_body`, `demo_upgrade_cta`

Bu helper `extras_menu.py`, `menu.py`, `campaign/level_select.py`, `campaign/coop_level_select.py` tarafinda tekrar kullanilir.

---

### Faz 8 - Testler

**Dosyalar:**

- `tests/test_demo_mode.py` (yeni)
- `tests/test_demo_menu_locks.py` (yeni)
- `tests/test_demo_campaign_limits.py` (yeni)

Kapsam:

1. Demo config: mode writer full/demo gecisleri dogru dosya uretiyor.
2. Extras: kilitli mod id seciminde mod donus engelleniyor.
3. Menu: online pvp/coop donusleri demo modda bloklaniyor.
4. Solo campaign: level 21 kilitli, level 20 acik.
5. Co-op campaign: level 11 kilitli, level 10 acik.
6. `QUADRIX_APP_NAME` demo iken path ayrimi dogru.

---

## Uygulama Sirasi

1. Faz 1 (demo config + writer)
2. Faz 2-4 (oyun ici kilit mekanikleri)
3. Faz 5 (spec/build entegrasyonu)
4. Faz 6 (app-name/save ayrimi)
5. Faz 7 (opsiyonel ortak prompt UI)
6. Faz 8 (testler)

---

## Non-Goals

- Demo -> full save/progress migration
- Demo'ya ozel yeni icerik veya ozel tutorial
- Matchmaking tarafinda demo-ozel lobby kurali
- Notarization/codesign otomasyonunun yeniden tasarimi

---

## Acik Sorular

1. Demo AppID ve store URL net mi?
2. Kilitli/acik mod listesi aynen kabul mu?
3. Demo buildde version bump isteniyor mu, isteniyorsa ayri `windows_demo` version dosyasi acilsin mi?
4. macOS tarafinda tek script parametreli mi olsun, yoksa demo icin ayri wrapper mi tercih?
5. UI'da tam modal mi, hafif toast + buton mu isteniyor?
