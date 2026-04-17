# Plan: Demo Sürümü Üretim Planı

**Created:** 2026-04-17
**Status:** Draft — Ready for Review

## Özet

Quadrix'in Steam Demo (ve/veya Steam Next Fest) için ayrı bir demo sürümü üretilecek. Demo sürümde:

- Belirli modlar kilitli — kart gösterimli, tıklamada "tam sürüm" yönlendirme modal'ı
- Kampanya yalnızca Dünya 1 (ilk 10 level) — geri kalanı kilitli
- Yeni bağımsız build spec dosyaları: `tetris_demo.spec` (Windows EXE) + `tetris_demo_macos.spec` (macOS .app)
- Build-time sabit ile kontrol (`IS_DEMO = True`) — runtime şüphe yok, flag değiştirilemez

Tam sürüm kodu değişmez. `IS_DEMO = False` olduğunda hiçbir kısıtlama çalışmaz.

---

## Context & Analiz

**İlgili Dosyalar:**

| Dosya                                  | Rol                                                           |
| -------------------------------------- | ------------------------------------------------------------- |
| `src/constants.py`                     | Oyun sabitleri — `IS_DEMO` buraya eklenmez; ayrı modül tercih |
| `src/extras_menu.py`                   | Mod kartları — `MODE_ID_TO_STATS_KEY` ile 10 mod tanımlı      |
| `src/menu.py`                          | Ana menü — Campaign / PvP / Coop giriş noktaları              |
| `src/campaign/level_select.py`         | Level seçim ekranı — dünya/level kilitleme burada             |
| `packaging/specs/tetris.spec`          | Windows tam sürüm spec                                        |
| `packaging/specs/tetris_macos.spec`    | macOS tam sürüm spec                                          |
| `packaging/specs/tetris_playtest.spec` | Steam Playtest spec — demo spec buna yakın                    |
| `config/runtime/steam_appid.txt`       | Steam AppID — demo için ayrı dosya gerekebilir                |
| `scripts/build/build_macos_app.sh`     | macOS build giriş noktası                                     |
| `tools/versioning.py`                  | Platform build versiyonlama                                   |

**Mevcut Modlar (extras_menu.py):**

| Mod ID        | Öneri    |
| ------------- | -------- |
| Classic Mode  | **Açık** |
| Sprint Mode   | **Açık** |
| Ultra Mode    | **Açık** |
| Zen Mode      | **Açık** |
| Quadrix Extra | Kilitli  |
| Kart Ustalığı | Kilitli  |
| Wide Mode     | Kilitli  |
| Survival Mode | Kilitli  |
| Cascade Mode  | Kilitli  |
| Hardcore Mode | Kilitli  |

**Ana Menü Modları:**

| Mod             | Öneri                           |
| --------------- | ------------------------------- |
| Kampanya (solo) | **Açık** — Dünya 1 (level 1-10) |
| Yerel PvP       | **Açık**                        |
| Yerel Co-op     | **Açık**                        |
| Online PvP      | Kilitli                         |
| Online Co-op    | Kilitli                         |

> Kilitli liste `src/demo_config.py` içinde değiştirilebilir — kod dokunmadan ayarlanabilir.

**Demo AppID Politikası:**

Steam'de demo, ana oyundan farklı AppID ile yayınlanır (Steam Next Fest için zorunlu). `config/runtime/steam_appid_demo.txt` ayrı tutulur; spec build sırasında `steam_appid.txt` yerine bu dosya paketlenir.

---

## Faz Planı

### Faz 1 — Demo Flag Altyapısı

**Dosyalar:** `src/demo_config.py` (yeni), `scripts/build/write_demo_config.py` (yeni)

**Yapılacaklar:**

1. `src/demo_config.py` oluştur — **default: tam sürüm**

   ```python
   # Bu dosya build-time script tarafından üretilir.
   # Manuel değiştirme: demo test için IS_DEMO = True yap.
   IS_DEMO: bool = False
   DEMO_LOCKED_MODES: set = {
       'Quadrix Extra', 'Kart Ustalığı', 'Wide Mode',
       'Survival Mode', 'Cascade Mode', 'Hardcore Mode',
   }
   DEMO_LOCKED_MAIN_MODES: set = {'online_pvp', 'online_coop'}
   DEMO_CAMPAIGN_WORLD_LIMIT: int = 1   # Dünya 1 = level 1-10
   DEMO_STEAM_STORE_URL: str = 'https://store.steampowered.com/app/XXXXXXX'
   ```

2. `scripts/build/write_demo_config.py` — build pipeline'ının çağırdığı tek satırlık yazar:
   ```python
   # python scripts/build/write_demo_config.py
   # Çıktıyı src/demo_config.py üzerine yazar, IS_DEMO = True
   ```

**Kural:** `IS_DEMO` runtime'da asla değiştirilemez. Sadece build sırasında yazılır. Kullanıcı ayarı veya env var girilmez.

---

### Faz 2 — Mod Kilitleme (Extras Ekranı)

**Dosyalar:** `src/extras_menu.py`

**Yapılacaklar:**

1. `ExtrasScreen.__init__` başında `from src.demo_config import IS_DEMO, DEMO_LOCKED_MODES` (veya relative import).

2. Kart çizim fonksiyonunda (`_draw_mode_card` veya benzeri) kilitli mod için:
   - Kart üzerine yarı şeffaf overlay
   - Sağ üst köşeye `DEMO` etiketi (veya kilit ikonu)
   - Normal hover/seçim efekti gizli

3. Kart tıklama handler'ında (`_handle_card_click`):
   - Kilitli mod → `_show_demo_upgrade_modal()` çağır
   - Normal akış engellensin

4. `_show_demo_upgrade_modal()` — küçük dialog:
   - "Bu mod tam sürümde mevcut." mesajı
   - "Steam'de Gör" butonu → `pygame.webbrowser.open(DEMO_STEAM_STORE_URL)` (veya `webbrowser.open`)
   - "Kapat" butonu

---

### Faz 3 — Ana Menü Kilitleri (PvP / Co-op / Online)

**Dosyalar:** `src/menu.py`

**Yapılacaklar:**

1. Online PvP ve Online Co-op tile/buton çiziminde `IS_DEMO` check:
   - Kilitli görünüm (gri / DEMO badge)
   - Tıklamada aynı `_show_demo_upgrade_modal()` çağrısı

2. Yerel PvP ve Yerel Co-op etkilenmez.

---

### Faz 4 — Kampanya Kısıtlaması

**Dosyalar:** `src/campaign/level_select.py`

**Yapılacaklar:**

1. `LevelSelect._draw_level_button` (veya benzeri) içinde:

   ```python
   if IS_DEMO and level_num > DEMO_CAMPAIGN_WORLD_LIMIT * 10:
       # kilitli görünüm
   ```

   > Dünya 1 = level 1-10; `DEMO_CAMPAIGN_WORLD_LIMIT = 1` → level 11+ kilitli.

2. Level butonu tıklama handler:
   - Kilitli level → `_show_demo_upgrade_modal()` çağır

3. Dünya kilidi (world 2+) — ayrı görsel: dünya başlığı üzerinde kilit overlay.

**Not:** Co-op kampanya (`src/campaign/coop_level_select.py`) da aynı mantıkla kısıtlanır: `world > DEMO_CAMPAIGN_WORLD_LIMIT` → kilitli.

---

### Faz 5 — Demo Build Spec Dosyaları

#### 5a. Windows EXE: `packaging/specs/tetris_demo.spec`

`tetris_playtest.spec` baz alınır, şu farklar:

- `write_demo_config.py` çalıştırılır (IS_DEMO=True yazar) build başında
- `steam_appid.txt` → demo AppID dosyasından beslenir (`config/runtime/steam_appid_demo.txt`)
- `os.environ.setdefault('STEAM_APP_ID', '<DEMO_APP_ID>')`
- EXE adı: `QuadrixDemo` (veya `Quadrix Demo`)
- `bump_platform_version` → `'windows_demo'` tag'i ile çağrılır

#### 5b. macOS App: `packaging/specs/tetris_demo_macos.spec`

`tetris_macos.spec` baz alınır, aynı farklar uygulanır:

- `write_demo_config.py` çağrısı
- Demo AppID
- Bundle name: `Quadrix Demo`
- `bump_platform_version(REPO_ROOT, 'macos_demo')`

#### 5c. Build Script'leri

`scripts/build/build_demo_windows.sh`:

```bash
#!/usr/bin/env bash
set -e
python scripts/build/write_demo_config.py
python -m PyInstaller packaging/specs/tetris_demo.spec --noconfirm
```

`scripts/build/build_demo_macos.sh`:

```bash
#!/usr/bin/env bash
set -e
python scripts/build/write_demo_config.py
python -m PyInstaller packaging/specs/tetris_demo_macos.spec --noconfirm
# macOS codesign / notarize adımları (tam sürümle aynı)
```

**Önemli:** `write_demo_config.py` çalıştıktan sonra `src/demo_config.py` `IS_DEMO = True` olur. Build bittikten sonra `git checkout src/demo_config.py` ile geri alınır (CI pipeline'a not).

---

### Faz 6 — Demo Splash / Banner

**Dosyalar:** `src/splash_screen.py` veya `src/menu.py`

**Yapılacaklar (opsiyonel, öneri):**

1. `IS_DEMO` aktifken ana menü başlık alanında küçük `DEMO` rozeti / banner.
2. İlk açılışta tek seferlik "Demo sürümünü oynuyorsunuz" bilgi modal'ı (`demo_intro_shown` flag'i `settings.txt` üzerinde tutulur).

---

### Faz 7 — Save Data Politikası

**Karar:** Demo save verisi tam sürümle **ayrı** tutulur.

- Steam'de demo farklı AppID → Steam Cloud zaten ayrı.
- Local save için `data_paths.py` içinde:
  ```python
  if IS_DEMO:
      SAVE_DIR = Path(user_data_dir()) / 'QuadrixDemo'
  else:
      SAVE_DIR = Path(user_data_dir()) / 'Quadrix'
  ```
- Demo'dan tam sürüme geçiş kolaylığı için "ilerleme aktarımı" bu planın **dışında** — gelecek plan.

---

### Faz 8 — Testler

**Dosyalar:** `tests/test_demo_mode.py` (yeni)

**Test Kapsamı:**

1. `IS_DEMO = False` → `DEMO_LOCKED_MODES` boş sayılır, hiçbir mod kilitlenmez
2. `IS_DEMO = True` → `DEMO_LOCKED_MODES` içindeki modlar "locked" döner
3. Kampanya: `IS_DEMO = True`, `level_num = 11` → locked; `level_num = 10` → açık
4. `write_demo_config.py` çalıştırıldığında `IS_DEMO = True` yazılır
5. Demo modal kapatma akışı — `_show_demo_upgrade_modal` birim testi

---

## Uygulama Sırası

```
Faz 1 (Altyapı)
  └─ Faz 2 (Extras kilidi)
  └─ Faz 3 (Menü kilidi)
  └─ Faz 4 (Kampanya kilidi)
      └─ Faz 5 (Build spec)
          └─ Faz 6 (Splash — opsiyonel)
Faz 7 (Save data — Faz 1 ile paralel yapılabilir)
Faz 8 (Testler — her fazın sonunda)
```

---

## Non-Goals (Bu Planın Dışı)

- Demo → tam sürüm ilerleme aktarımı
- Demo'ya özel içerik (ekstra tutorial seviyesi vs.)
- Online demo lobi / matchmaking kısıtlaması (sadece erişim engeli yeterli)
- Demo indirme süresi optimizasyonu (asset küçültme)
- macOS notarization otomasyonu (mevcut script kullanılır)

---

## Açık Sorular

1. **Demo AppID** belli mi? `DEMO_STEAM_STORE_URL` ve `steam_appid_demo.txt` için AppID girilmeli.
2. **Hangi modlar açık?** Yukarıdaki tablo öneri — onay isteniyor.
3. **Co-op kampanya demo limiti** → Dünya 1 yeterli mi?
4. **Demo banner** (Faz 6) isteniyor mu? Opsiyonel işaretlendi.
5. **Build pipeline CI** var mı? `git checkout src/demo_config.py` adımı CI'ya eklenmeli.
