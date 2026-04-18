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

Acik (6):

- Classic Mode
- Sprint Mode
- Ultra Mode
- Zen Mode
- Card Mastery (Kart Ustaligi)
- Wide Mode

Kilitli (7):

- Quadrix Extra
- Challenge Mode (Görev Modu) — *Özel kilit*: D1 ilk 20 aşama acik, 21+ kilitli
- Daily Challenge (Günlük Görev) — Tam kilitleme
- Survival Mode (Hayatta Kalma)
- Cascade Mode (Çağlayan)
- Hardcore Mode
- [future expansions]

### Ana Menu

Acik:

- Campaign (solo)
- PvP local
- Co-op local

Kilitli:

- Online PvP
- Online Co-op

### Kampanya

- Solo: Dunya 1 (level 1-20) acik, Dunya 2-5 kilitli.
- Co-op: Dunya 1 (level 1-10) acik, Dunya 2 kilitli.

---

## Kilit Tipleri (Lock Type Definitions)

### Tip 1: Tam Kilitleme (Full Lock)

Mod seciminde `handle_input` return noktasinda kilit kontrolu. Secilemez.

**Uygulanacaklar:**
- Quadrix Extra
- Daily Challenge
- Hardcore Mode
- Online PvP
- Online Co-op

**Davranis:**
- Kilitli mod icona hover → "Tam sürümde mevcut" badge
- Seçilirse → upgrade modal/toast + Store URL link

---

### Tip 2: Kismi Kilitleme (Partial Lock - Intro Stages)

Mod aciklaniyor ama icerik kismı kilitli (level siniri).

**Uygulanacaklar:**
- Challenge Mode: D1 ilk 20 aşama acik, 21+ D2-Dx seviyesi kilitli
- (Gelecek: Daily Challenge ile benzer intro pattern istenirse aynı yontemle)

**Davranis:**
- Moda giris acik
- Level secim ekraninda level > 20 görsel kilit + tooltip "ilk 20 aşama için demo"
- Level 21+ tiklanirsa kilit modal

---

### Tip 3: Gecis Kilitleme (Transition Lock - Menu Navigation)

Ana menu icinde online secenekleri donusuklestir ve redirect.

**Uygulanacaklar:**
- Online PvP (menu'de pvp_online_polygon)
- Online Co-op (menu'de coop_online_polygon)

**Davranis:**
- Keyboard/mouse seciminde "full" build'e donuslendirme modal
- Local PvP/Co-op normal calisir

---

### Kilit Mesaji Bicimi

Uc ortak mesaj:

1. **Full Lock (Tam Kilitleme):**
   ```
   "Bu mod tam sürümde mevcut."
   [Tap to upgrade] [Close]
   → webbrowser.open(DEMO_STEAM_STORE_URL)
   ```

2. **Partial Lock (Kısmi Kilitleme):**
   ```
   "İlk 20 aşama tanıtım amaçlıdır. Diğer seviyeleri tam sürümde oyna."
   [Tap to upgrade] [Close]
   ```

3. **Transition Lock (Geçiş Kilitleme):**
   ```
   "Çevrimiçi oyunlar tam sürümde mevcut."
   [Go to store] [Back to Menu]
   ```

---

## Faz Plani

### Faz 1 - Demo Konfig Altyapisi

**Dosyalar:** `src/demo_config.py` (yeni), `scripts/build/write_demo_config.py` (yeni)

`src/demo_config.py` taslagi:

```python
# Build pipeline bu dosyayi yazar.
# Default: full build
IS_DEMO = False

# Tip 1: Tam kilitleme — mode id'leri
DEMO_LOCKED_EXTRAS_MODE_IDS = {
    'Quadrix Extra',
    'Challenge Mode',          # ← Özel: kısmi kilit alt tip
    'Daily Challenge',
    'Survival Mode',
    'Cascade Mode',
    'Hardcore Mode',
}

# Tip 2: Challenge Mode — özel kısmi kilit (sadece Challenge'a has)
DEMO_CHALLENGE_UNLOCKED_STAGES = 20  # D1 level 1-20

DEMO_LOCKED_MAIN_ACTIONS = {'online_pvp', 'online_coop'}

# Solo campaign: world*20
DEMO_SOLO_WORLD_LIMIT = 1

# Co-op campaign: world*10
DEMO_COOP_WORLD_LIMIT = 1

DEMO_STEAM_STORE_URL = 'https://store.steampowered.com/app/XXXXXXX'
DEMO_APP_NAME = 'quadrix_demo'

# Lokalizasyon turleri — demo_upgrade_prompt.py'de kullanilir
DEMO_LOCK_MESSAGES = {
    'full_lock': 'demo_mode_full_lock_title',      # "Bu mod tam sürümde mevcut"
    'partial_lock': 'demo_mode_partial_lock_title',  # "İlk 20 aşama tanıtım..."
    'transition_lock': 'demo_mode_transition_lock_title',  # "Çevrimiçi oyunlar..."
}
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

- Cizim: `_draw_modern_mode_card` icinde locked overlay + "DEMO KILIT" badge.
- Input: `handle_input` icinde `RETURN/SPACE` ve mouse click donuslerinden once locked check.

Davranis:

1. **Tam Kilitleme** (Quadrix Extra, Daily Challenge, Survival, Cascade, Hardcore):
   - Mod secilirse oyun moda gecmez.
   - Full-lock upgrade modal gosterilir: "Bu mod tam sürümde mevcut"

2. **Kismi Kilitleme** (Challenge Mode):
   - Mod acilir ve level secim ekranina gider.
   - Level secimde level > 20 icin partial-lock modal gosterilir.
   - DEMO_CHALLENGE_UNLOCKED_STAGES = 20 degeri ile sinir tutulur.

Ortak davranis:
- Kilit gorselinde store URL link saglayan buton.
- `webbrowser.open(DEMO_STEAM_STORE_URL)` cagrilir.

---

### Faz 3 - Ana Menu Online Kilitleri

**Dosya:** `src/menu.py`

Uygulama noktasi:

- Keyboard akisi: `handle_input` icindeki online donusu imi control etmeli, transition-lock modal gostermelidir.
- Mouse akisi: `MOUSEBUTTONDOWN` icindeki `online_pvp_polygon` / `online_coop_polygon` branch'leri.

Davranis:

- **Online PvP** seçilirse: transition-lock modal "Çevrimiçi oyunlar tam sürümde mevcut"
- **Online Co-op** seçilirse: aynı transition-lock modal
- **Local PvP / Local Co-op** normal calisir (davranis degismez)
- Modal butonlari: [Go to Store] → webbrowser.open(), [Back to Menu] → iptal

---

### Faz 4 - Kampanya Kilitleme

#### 4a. Solo Kampanya (Campaign Mode)

**Dosya:** `src/campaign/level_select.py`

Uygulama noktasi:

- `CampaignLevelSelect._is_level_unlocked(level_num)` icine demo siniri eklenir.
- `handle_input` icindeki dunya tab degisiminde demo world limit disina gecis engellenir.
- `_draw_world_tabs` ve `_draw_level_button` icinde demo kilidi gorseli eklenir.

Kural:

- `DEMO_SOLO_WORLD_LIMIT = 1` iken world > 1 veya level_num > 20 kilitli.

#### 4b. Co-op Kampanya (Co-op Campaign)

**Dosya:** `src/campaign/coop_level_select.py`

Uygulama noktasi:

- `CoopLevelSelect._is_level_unlocked(level_num)` demo limiti ile sarilir.
- `handle_input` icinde world tab click kontrolu eklenir.
- Grid/tab ciziminde kilitli dunya ve level gorseli verilir.

Kural:

- `DEMO_COOP_WORLD_LIMIT = 1` iken world > 1 veya level_num > 10 kilitli.

#### 4c. Challenge Modu Kismi Kilitleme (Campaign → Challenge Mode)

**Dosya:** `src/campaign/level_select.py` (Challenge Mode'a uyarlanan versiyon)

Challenge Mode'un kendi seviye sistemi varsa, o sisteme:

Uygulama noktasi:

- Level secim ekraninda level_num > DEMO_CHALLENGE_UNLOCKED_STAGES (20) icin kilitli gorseli.
- Level 21+ tiklanirsa partial-lock modal: "İlk 20 aşama tanıtım amaçlıdır..."

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

- `show_demo_full_lock_prompt(screen, settings_manager, ...)` — Tip 1
- `show_demo_partial_lock_prompt(screen, settings_manager, ...)` — Tip 2 (Challenge-specific)
- `show_demo_transition_lock_prompt(screen, settings_manager, ...)` — Tip 3
- `webbrowser.open()` uygulama
- Lokalizasyon anahtarlari: `demo_mode_full_lock_title`, `demo_mode_partial_lock_title`, `demo_mode_transition_lock_title`

Kullanacaklar:
- `extras_menu.py`: `show_demo_full_lock_prompt()` (tüm tam kilitler) ve `show_demo_partial_lock_prompt()` (Challenge partial kilit)
- `menu.py`: `show_demo_transition_lock_prompt()` (Online PvP/Co-op)
- `campaign/level_select.py`: `show_demo_partial_lock_prompt()` (Challenge level 21+)

---

### Faz 8 - Testler

**Dosyalar:**

- `tests/test_demo_mode.py` (yeni)
- `tests/test_demo_menu_locks.py` (yeni)
- `tests/test_demo_campaign_limits.py` (yeni)

Kapsam:

1. Demo config: mode writer full/demo gecisleri dogru dosya uretiyor.
2. Extras (Tam Kilit): kilitli mod id seciminde mod donus engelleniyor.
3. Extras (Kismi Kilit): Challenge Mode moda girer, level 21+ tiklanirsa modal gosteriliyor.
4. Menu: online pvp/coop donusleri demo modda bloklaniyor; local calisir.
5. Solo campaign: world 2+ kilitli, level 21+ kilitli.
6. Co-op campaign: world 2 kilitli, level 11+ kilitli.
7. Challenge level selection: level 1-20 acik, 21+ kilitli.
8. `QUADRIX_APP_NAME` demo iken path ayrimi dogru.
9. Kilit prompt modal'lari doğru kilit türü mesaji gösteriyor (full/partial/transition).

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
2. ~~Kilitli/acik mod listesi aynen kabul mu?~~ → **Kapatıldı**: Challenge, Daily Challenge, Cascade, Survival, Quadrix Extra (tam kilit) + Online PvP/Co-op. Diğerleri açık.
3. ~~Kilit mekanigi tipleri?~~ → **Kapatıldı**: 3 tip — Tam kilit (full lock), Kısmi kilit (partial lock, Challenge D1 ilk 20), Geçiş kilidi (transition lock, Online).
4. Demo buildde version bump isteniyor mu, isteniyorsa ayri `windows_demo` version dosyasi acilsin mi?
5. macOS tarafinda tek script parametreli mi olsun, yoksa demo icin ayri wrapper mi tercih?
6. UI'da tam modal mi, hafif toast + buton mu isteniyor? (Modal tercih edilmiş durumda.)
