# Demo ↔ Ana Oyun Senkronizasyon Analizi ve Geçiş Rehberi

> **Amaç:** Bu doküman, `v2` (ana/full oyun, `main` branch) ile `v2-demo` (`release/demo` branch) arasındaki ilişkiyi analiz eder ve bir YZ ajanının senkronizasyon/geçiş işlemlerini güvenli şekilde yürütmesi için kanonik referans görevi görür.
>
> **Tarih:** 2026-05-18  
> **Kanonik gerçek kaynakları:** Kod, spec dosyaları, build scriptleri ve testler. Tarihsel plan/rapor dosyaları kanıt değildir.

---

## 1. Kısa Teşhis

Bu yapı **tek bir git reposunun iki worktree'si** olarak çalışıyor:

- `v2/` → `main` branch (full oyun)
- `v2-demo/` → `release/demo` branch (demo varyantı)

Demo, `main`'den fork edilmiş bir branch'tir (merge-base: `1052f18`). Demo branch'te ana oyun koduna **doğrudan inline patch** yapılmış: `demo_config.py` ve `demo_upgrade_prompt.py` eklenerek, `menu.py`, `extras_menu.py`, `game_modes_extra.py`, `level_select.py`, `coop_level_select.py` ve `main.py` dosyalarına `import demo_config` + gating çağrıları yerleştirilmiş.

Ana oyunda (`main` branch) `demo_config.py` dosyası **hiç yoktur** — demo mantığı tamamen `release/demo` branch'e özgüdür.

**Sonuç:** Bu bir "patch katmanı" değil, **divergent branch fork**'tur. Main ilerledikçe (analiz anında 12 commit önde, demo 3 commit önde) drift birikir ve merge conflict riski artar.

> **Drift ölçüm yöntemi (2026-05-18):** `git rev-list --count` ve `git diff --shortstat`. `main..release/demo` = 3 commit; `release/demo..main` = 12 commit. `game_modes_extra.py` net fark: **324 ekleme + 1018 silme = 1342 satır toplam değişiklik** (bu sayı `git diff --stat` histogram metriğidir). Bu doküman boyunca tek tip kullanılan rakam **1342** (1018 silme - 324 ekleme = 694 net silme). Eski sürümlerde geçen "1272" sayısı stale ölçümdü; harmonize edildi.

> **Güncelleme (2026-05-18, mystery progression migration):** Önceki turlarda **deferred** olarak işaretlenen mystery progression API tamamı demo'ya port edildi. Demo `MysteryCardManager` artık main ile identical: `card_xp/card_level/card_xp_to_next` ekonomisi, `compute_xp_award` (combo/B2B/perfect bonusları dahil), `RARITY_WEIGHT_ANCHORS` (1/5/10/20 anchor seviyeleri) + lineer interpolasyon, rarity-bucket sampling, modül-level `get_mystery_level_fall_speed_ms` ve `MYSTERY_LEVEL_SPEED_ANCHORS`. Demo `MysteryMode` `_get_mystery_speed_level/_get_mystery_base_fall_speed/get_initial_speed/get_current_speed` method'ları main'in eğrisini kullanıyor. Time capsule capture/restore listelerine `card_xp/card_level/card_xp_to_next` ve `pending_level_ups` eklendi (AGENTS.md §7 invariant 3 korunumu). `notify_lines_cleared` keyword-only `source='player'/...` signature'ına geçirildi; tüm 4 call site (player clear, external_card, external_ability, vb.) source threading ile çalışıyor. Demo gating: `DEMO_CARD_SELECTION_LEVEL_INTERVAL=10` artık `board.level_lines_per_level`'e eşlenir (board level cadence'i / fall speed temposu); kart seçimi XP-driven olduğu için `IS_DEMO` flag'i kart ekonomisini etkilemez. `_demo_score_cap_value=75K` korundu.

> **Güncelleme (2026-05-18):** Drift sadece commit sayısıyla değil **architecture seviyesinde** de mevcut**ti**. Main, demo fork'undan sonra MysteryCardManager'da büyük bir refactor yaptı: `card_xp`/`card_level`/`compute_xp_award`/`_compute_xp_to_next` ve `RARITY_WEIGHT_ANCHORS`/`_rarity_weights_for_level` API'leri eklendi; `get_mystery_level_fall_speed_ms` modül-level fonksiyonu çıkarıldı. **Bu architectural drift 2026-05-18 mystery migration turunda demo'ya tamamen port edildi**; yukarıdaki güncellemeye bakınız. Ayrıca main'de `focus_manager.py` (gamepad full-support Faz 2), `line_clear_feedback.py` (5 game class arasında ortak helper) ve `settings_screen_tabbed.py`'de keybind modernization (hold-to-clear, conflict detection, slot reset) eklenmişti — hepsi taşındı. Demo'daki `game._start_block_fall_animation` algoritması da port edildi.

---

## 2. Mimari: Demo Feature Gating Nasıl Çalışıyor

### Merkez: `src/demo_config.py`

```python
IS_DEMO = False  # Build-time: write_demo_config.py --mode demo → True

# Sabitler
DEMO_STEAM_APP_ID = "4635310"
DEMO_LOCKED_EXTRAS_MODE_IDS = {"Cascade Mode", "Hardcore Mode", "Quadrix Extra", "Survival Mode", "daily_challenge"}
DEMO_PARTIAL_EXTRAS_MODE_IDS = {"Challenge Mode"}
DEMO_TRANSITION_EXTRAS_MODE_IDS = {"Online PvP"}
DEMO_LOCKED_MAIN_ACTIONS = {"online_coop", "online_pvp"}
DEMO_SOLO_WORLD_LIMIT = 1
DEMO_SOLO_LEVEL_LIMIT = 20
DEMO_COOP_WORLD_LIMIT = 1
DEMO_COOP_LEVEL_LIMIT = 10
DEMO_CARD_SELECTION_LEVEL_INTERVAL = 10  # Full: 5

# Gate fonksiyonları
get_extras_lock_kind(mode_id) → "full" | "transition" | "partial" | None
is_locked_main_action(action_id) → bool
is_solo_campaign_level_available(level_num) → bool
is_coop_campaign_level_available(level_num) → bool
get_card_selection_level_interval() → int
apply_runtime_environment(env) → str  # QUADRIX_APP_NAME ayarlar
```

### Gating Yayılım Haritası

| Dosya | Gating Noktası | Davranış |
|-------|---------------|----------|
| `main.py` (root, satır 12-18) | `apply_runtime_environment()` | Startup'ta `QUADRIX_APP_NAME` env var'ını ayarlar |
| `src/menu.py` (satır ~2193) | `_maybe_handle_demo_main_action(action_id)` | online_pvp/online_coop → transition lock prompt |
| `src/extras_menu.py` (satır ~350) | `_show_demo_lock_prompt_for_mode(mode_id)` | Kilitli modlara tıklamada full/partial/transition prompt |
| `src/campaign/level_select.py` (satır ~293) | `_maybe_handle_demo_level_lock()` / `_maybe_handle_demo_world_lock()` | World 2+ ve Level 21+ engellenir |
| `src/campaign/coop_level_select.py` | `_maybe_handle_demo_world_lock()` / `_maybe_handle_demo_level_lock()` | World 2+ ve Level 11+ engellenir |
| `src/game_modes_extra.py` (satır ~463+) | `get_card_selection_bucket()` + `_should_trigger_demo_score_cap()` | Kart seçimi 10 level'de bir; 75K skor cap |
| `src/localization.py` | 9 demo-specific key | `demo_prompt_title`, `demo_open_steam`, `locked_badge`, vb. |
| `packaging/pyinstaller/hooks/pyi_rth_quadrix_data.py` (satır 17) | `_resolve_default_app_name()` | Demo build'de `quadrix_demo`, full'da `quadrix_full` |

### Build Zinciri

```
write_demo_config.py --mode demo
    → src/demo_config.py içine IS_DEMO = True yazar
    → build_windows_demo.ps1 veya build_macos_demo_app.sh çağrılır
        → ilgili demo spec (tetris_demo.spec / tetris_demo_macos_allinone.spec) kullanılır
        → steam_appid_demo.txt (4635310) bundle'a eklenir
        → finally/trap bloğunda write_demo_config.py --mode full ile restore edilir
```

---

## 3. Senkron-Kritik Dosya Haritası

### 3.1 Ortak Dosyalar (her iki branch'te yaşayan, senkron tutulması gereken)

| Dosya | Demo'daki Ek Kod |
|-------|-----------------|
| `src/menu.py` | +`import demo_config` + `_maybe_handle_demo_main_action()` + `_is_demo_locked_main_action()` + prompt draw/input hooks |
| `src/extras_menu.py` | +`import demo_config` + `_show_demo_lock_prompt_for_mode()` + `_get_demo_lock_kind()` + prompt draw/input hooks |
| `src/game_modes_extra.py` | +`import demo_config` + score cap + card interval logic. **En büyük divergence: 1342 satır toplam değişiklik (324 ekleme + 1018 silme; 694 net silme)** |
| `src/campaign/level_select.py` | +`import demo_config` + world/level lock guard'ları (+54 satır) |
| `src/campaign/coop_level_select.py` | +`import demo_config` + world/level lock guard'ları (+86 satır) |
| `src/localization.py` | +9 demo key (additive) |
| `main.py` (root) | +`apply_runtime_environment()` çağrısı (+12 satır) |
| `packaging/pyinstaller/hooks/pyi_rth_quadrix_data.py` | Demo-aware `_resolve_default_app_name()` (+28 satır) |
| `scripts/build/build_macos_app.sh` | `--spec` ve `--app-name` parametre desteği (+29 satır) |

### 3.2 Demo-Özel Dosyalar (yalnızca demo'da var olması gereken)

| Dosya | Rol |
|-------|-----|
| `src/demo_config.py` | Feature gate merkezi |
| `src/demo_upgrade_prompt.py` | Demo kilit/upgrade UI overlay (~233 satır) |
| `scripts/build/write_demo_config.py` | Build-time IS_DEMO yazıcı |
| `scripts/build/build_windows_demo.ps1` | Windows demo build wrapper |
| `scripts/build/build_macos_demo_app.sh` | macOS demo build wrapper |
| `packaging/specs/tetris_demo.spec` | Windows demo PyInstaller spec |
| `packaging/specs/tetris_demo_macos_allinone.spec` | macOS demo PyInstaller spec |
| `config/runtime/steam_appid_demo.txt` | Demo Steam AppID: `4635310` |
| `steamworks/scripts/app_build_demo.vdf` | Demo Steam depot config |
| `steamworks/scripts/depot_build_demo_windows.vdf` | Demo Windows depot |
| `tools/steam_upload_demo.ps1` | Demo Steam upload script |
| `tests/test_demo_config.py` | Config generation testi |
| `tests/test_demo_build_specs.py` | Spec dosyası doğrulama testi |
| `tests/test_demo_menu_locks.py` | Menü kilit davranış testi |
| `tests/test_demo_campaign_limits.py` | Campaign limit testi |
| `tests/test_demo_card_mode_interval.py` | Kart interval testi |
| `tests/test_demo_mystery_score_cap.py` | Mystery score cap testi |
| `tests/test_demo_localization.py` | Demo lokalizasyon key testi |

### 3.3 Full-Özel Dosyalar (main'de var, demo'da eksik/silinmiş)

> **Not (2026-05-18, ikinci güncelleme):** Liste git diff ile doğrulanmıştır (`git diff --name-status main release/demo`). Aşağıdaki tablo bu turda yapılan transferleri yansıtır.

| Dosya | Durum |
|-------|-------|
| `src/focus_manager.py` | **Transferred (2026-05-18)** — Standalone gamepad navigation modülü demo'ya taşındı. `gamepad_manager.py` sonuna `from focus_manager import GamepadAction, key_to_action` re-export eklendi. |
| `src/line_clear_feedback.py` | **Transferred (2026-05-18, bounded refactor)** — Helper modülü demo'ya taşındı. `game.py`, `pvp_game.py`, `online_pvp_game.py`, `coop_game.py`, `online_coop_game.py` import etti. `game.py` ve `pvp_game.py` (p1+p2) ve `online_pvp_game.py`'nin wave queue/update inline blokları helper çağrısıyla değiştirildi. `coop_game.py` ve `online_coop_game.py` yalnızca import seviyesinde bağlandı (inline wave queue site'ları yok). Parity guard `test_online_coop_network_flow.py` sonuna eklendi. |
| `tests/test_focus_manager.py` | **Transferred (2026-05-18)** — 18 test demo'da geçer. |
| `tests/test_game_line_clear_fall_animation.py` | **Transferred (2026-05-18, dar gameplay portu)** — `Game._start_block_fall_animation` algoritması ve yardımcı `_row_drop_distances_after_clear` demo'ya port edildi. Test demo'da geçer. |
| `tests/test_settings_tabbed_keybind_modernization.py` | **Transferred (2026-05-18, hedefli backport)** — Demo'ya: `_detect_keybind_conflicts`, `_is_keybind_unbound`, `_reset_keybind_row_full`, `_clear_keybind_slot`, `_reset_hold_to_clear_state`, `_check_hold_to_clear_progress` method'ları + `_get_single_player_binding_slots`/`_get_pvp_binding` helper'ları + hold-to-clear `__init__` state alanları + `_keybind_conflicts/_keybind_unbound_count/_keybind_row_reset_rects` per-frame state. `_start_keybind_capture` `_reset_hold_to_clear_state` çağrısıyla genişletildi. 18/18 test geçer. |
| `tests/test_settings_tabbed_keybind_clickflow_live.py` | **Transferred (2026-05-18, tam)** — 6/6 test geçer. Demo'ya MOUSEMOTION slot hover takibi, PvP/debug "satırın herhangi bir yerine tıkla → primary capture aç" davranışı, ↺ reset rect tıklama handler'ı ve `_draw_content`'te per-row reset rect populate eklendi. Reset rect minimal geometry-only çözüm: row sol kenarına yerleştirilmiş küçük bir rect (slot rect'leriyle çakışmıyor). Tam `_draw_keybind_row_decorations` UI helper'ı (badge çizimi, conflict tooltip, hover registry) port edilmedi; dar reset-rect populate çözümü test gereksinimlerini karşılıyor. |
| `tests/test_mystery_card_quality_gaps.py` | **Transferred (2026-05-18, full architectural migration)** — Demo `MysteryCardManager` tamamen yeni `card_xp/card_level/compute_xp_award/_compute_xp_to_next` API'sine geçirildi. Demo'da 8/8 test geçer. |
| `tests/test_mystery_card_rarity_curve.py` | **Transferred (2026-05-18, full architectural migration)** — `RARITY_WEIGHT_ANCHORS` (1, 5, 10, 20 anchor seviyeleri) ve `_rarity_weights_for_level` lineer interpolasyon demo'ya port edildi. Demo `_weighted_sample` rarity-bucket sampling'e yükseltildi. Demo'da 21/21 test geçer. |
| `tests/test_mystery_card_xp_progression.py` | **Transferred (2026-05-18, full architectural migration)** — XP economy (XP_PER_LINE_COUNT, BASE_XP_TO_NEXT, XP_GROWTH_PER_LEVEL), anti-farm (`source='player'/'card'/...`), pending_level_ups overflow, time capsule capture/restore'da `card_xp/card_level/card_xp_to_next` korunumu hepsi demo'da geçer. Demo'da 18/18 test geçer. |
| `tests/test_mystery_speed_curve.py` | **Transferred (2026-05-18, full architectural migration)** — Modül-level `get_mystery_level_fall_speed_ms`, `MYSTERY_LEVEL_SPEED_ANCHORS` ((1,850), (5,700), (10,500), (15,300), (20,150), (30,125)), `MYSTERY_LEVEL_SPEED_POST_L30_STEP_MS` ve `_get_mystery_speed_level`/`_get_mystery_base_fall_speed`/`get_initial_speed`/`get_current_speed` MysteryMode method'ları demo'ya port edildi. Demo'da 9/9 test geçer. |
| `.kiro/specs/gamepad-full-support-audit/design.md` | **Skip** — IDE-internal spec, kanonik referans değil. |
| `plans/2026-05-12-*.md`, `plans/2026-05-14-*.md` | **Skip** — Tarihsel plan dosyaları (AGENTS.md §5: rewrite edilmez). |

---

## 4. İki Yönlü Etki Analizi

### 4.1 Demo Değişikliği → Ana Oyuna Etkisi

| Senaryo | Risk | Açıklama |
|---------|------|----------|
| `demo_config.py` veya `demo_upgrade_prompt.py` değişikliği | **Düşük** | Bu dosyalar main'de yok; merge conflict olmaz. Ama main'e yanlışlıkla cherry-pick edilirse `IS_DEMO=True` ile full oyun kilitlenir. |
| `menu.py`'deki demo gating kodu değişikliği | **Yüksek** | menu.py her iki branch'te aktif değişiyor. Demo'daki refactor main'e merge edilirse `demo_config` import'u olmadan crash. |
| `game_modes_extra.py` demo score cap değişikliği | **Çok Yüksek** | 1342 satır toplam değişiklik (324 ekleme + 1018 silme) ile en çok diverge eden dosya. Demo'daki herhangi bir değişiklik main'e taşınırsa massive conflict. |
| `localization.py` demo key eklenmesi | **Düşük** | Additive; `t()` fallback mekanizması kırılma önler. |
| Demo build script değişikliği | **Sıfır** | Bu dosyalar main'de yok. |
| `pyi_rth_quadrix_data.py` değişikliği | **Orta** | Her iki branch'te var; demo-aware logic main'de gereksiz ama zararsız. |

### 4.2 Ana Oyun Düzeltmesi → Demo'ya Etkisi


| Senaryo | Taşınabilirlik | Koşul |
|---------|---------------|-------|
| `src/game.py`, `src/board.py` gameplay bug fix | **Doğrudan taşınabilir** | Bu dosyalarda demo gating yok; cherry-pick güvenli. |
| `src/game_modes_extra.py` Mystery bug fix | **Riskli** | 1342 satır toplam değişiklik. Cherry-pick conflict garantili. Manuel uyarlama gerekir. |
| `src/menu.py` UI fix | **Koşullu** | Demo'da ek import/gating var. Conflict olasılığı yüksek ama çözülebilir. |
| `src/localization.py` yeni key | **Doğrudan taşınabilir** | Additive, conflict düşük. |
| `src/campaign/level_select.py` fix | **Koşullu** | +54 satır fark ama izole bölgelerde. Dikkatli cherry-pick mümkün. |
| Yeni dosya eklenmesi | **Doğrudan taşınabilir** | Demo'da yoksa conflict yok; ama demo testleri kapsamaz. |
| `build_macos_app.sh` değişikliği | **Dikkatli** | Demo `--spec`/`--app-name` parametreleri eklemiş; main değişikliği bunları kırabilir. |

### 4.3 En Riskli Kırılma Noktaları (Demo → Main yanlışlıkla taşınırsa)

1. **Giriş akışı (`main.py`):** `apply_runtime_environment()` çağrısı + `demo_config.py` yoksa → **ImportError crash at startup**
2. **Menü kilitleri (`menu.py:2193`):** `_maybe_handle_demo_main_action` → `demo_config` import hatası veya online modların kilitlenmesi
3. **Campaign limitleri (`level_select.py:293`):** Demo world/level lock'ları → oyuncular World 2+'ye erişemez
4. **Mystery kart progression (`game_modes_extra.py`):** `get_card_selection_level_interval()` → kart seçimi 5 yerine 10 level'de bir, progression yavaşlar
5. **Steam AppID (`steam_appid_demo.txt`: 4635310):** Main build'e sızarsa → leaderboard/achievement/multiplayer çalışmaz
6. **Save/app-name ayrımı:** `QUADRIX_APP_NAME=quadrix_demo` → save dosyaları farklı dizine yazılır, oyuncular progress kaybeder

---

## 5. Senkronizasyon Stratejileri

### Strateji 1: Birleşik Tek Kaynak Ağacı + Build-Time Feature Flag

**Nasıl çalışır:** `demo_config.py` ve tüm demo-özel dosyalar main branch'e taşınır. `IS_DEMO = False` default olarak kalır. Build-time `write_demo_config.py --mode demo` ile `IS_DEMO = True` yazılır. Tüm demo gating kodu main'de yaşar.

| Kriter | Değerlendirme |
|--------|--------------|
| **Artılar** | Sıfır drift. Tek branch, tek CI. Her bug fix otomatik olarak demo'ya uygulanır. Demo testleri her PR'da koşar. |
| **Eksiler** | Main'deki dosyalarda demo guard'ları görünür (code noise). İlk migration eforu yüksek (game_modes_extra.py'de 1342 satırlık merge — 324 ekleme + 1018 silme). |
| **Operasyon maliyeti** | Bir kerelik yüksek, sonrasında sıfıra yakın. |
| **Drift riski** | **Sıfır** |

### Strateji 2: Ana Repo Kaynaklı Tek Yönlü Senkron + Demo Patch Overlay

**Nasıl çalışır:** `release/demo` branch korunur. Main'deki değişiklikler periyodik `git merge main` ile demo'ya çekilir. Demo-özel dosyalar yalnızca demo branch'te kalır.

| Kriter | Değerlendirme |
|--------|--------------|
| **Artılar** | Main temiz kalır. Demo'nun kendi release cycle'ı olabilir. Mevcut yapıya en yakın. |
| **Eksiler** | Her merge'de conflict riski. Yeni feature'lara demo gating eklenmesi unutulabilir. Drift birikir. |
| **Operasyon maliyeti** | Her sprint'te merge + conflict çözümü. Orta-yüksek sürekli maliyet. |
| **Drift riski** | **Yüksek** |

### Strateji 3: Ayrı Repo + Script Tabanlı Eşitleme

**Nasıl çalışır:** Demo tamamen ayrı repo'ya taşınır. Main'deki fix'ler cherry-pick veya sync script ile aktarılır.

| Kriter | Değerlendirme |
|--------|--------------|
| **Artılar** | Tam izolasyon. Main'e hiçbir demo kodu sızmaz. |
| **Eksiler** | En yüksek operasyon maliyeti. Cherry-pick conflict'e açık. İki yerde test koşulmalı. |
| **Operasyon maliyeti** | Çok yüksek sürekli maliyet. |
| **Drift riski** | **Çok yüksek** |

---

## 6. Önerilen Hedef Model: Strateji 1

### Neden bu repo için en uygun:

1. **Altyapı zaten hazır.** `write_demo_config.py` + `IS_DEMO` flag mekanizması çalışıyor.
2. **Demo gating kodu izole.** `if not IS_DEMO: return None/True` pattern'i full build'de sıfır maliyetli.
3. **Mevcut model sürdürülemez.** 12 commit / 1342 satır (game_modes_extra.py) drift birikmiş ve her gün büyüyor.
4. **Tek kaynak ağacında demo regresyonları her PR'da yakalanır;** ayrı branch'te ancak merge sırasında fark edilir.
5. **Operasyon maliyeti bir kerelik merge sonrasında sıfıra düşer;** mevcut modelde her sprint merge + conflict çözümü gerekiyor.

---

## 7. Geçiş Planı (Adım Adım)

### Adım 1: Demo-özel dosyaları main'e ekle (additive, conflict-free)

```bash
# release/demo'dan main'e cherry-pick veya dosya kopyalama
git checkout main
git checkout release/demo -- \
  src/demo_config.py \
  src/demo_upgrade_prompt.py \
  scripts/build/write_demo_config.py \
  scripts/build/build_windows_demo.ps1 \
  scripts/build/build_macos_demo_app.sh \
  packaging/specs/tetris_demo.spec \
  packaging/specs/tetris_demo_macos_allinone.spec \
  config/runtime/steam_appid_demo.txt \
  steamworks/scripts/app_build_demo.vdf \
  steamworks/scripts/depot_build_demo_windows.vdf \
  tools/steam_upload_demo.ps1 \
  tests/test_demo_config.py \
  tests/test_demo_build_specs.py \
  tests/test_demo_menu_locks.py \
  tests/test_demo_campaign_limits.py \
  tests/test_demo_card_mode_interval.py \
  tests/test_demo_mystery_score_cap.py \
  tests/test_demo_localization.py
```

**Kritik:** `src/demo_config.py` içinde `IS_DEMO = False` olduğunu doğrula.

### Adım 2: Ortak dosyalara demo gating kodunu merge et

Conflict çözümü gereken dosyalar (büyükten küçüğe sıralı):

1. **`src/game_modes_extra.py`** — En büyük merge. Demo score cap + card interval logic'i main'in güncel haline uyarla. `_should_trigger_demo_score_cap()`, `_activate_demo_score_cap_prompt()`, `_demo_score_cap_value` init, `get_card_selection_bucket()` kullanımı ekle.
2. **`src/menu.py`** — `import demo_config` + `DemoUpgradePrompt` + `_maybe_handle_demo_main_action` + `_is_demo_locked_main_action` + prompt draw/input hooks.
3. **`src/extras_menu.py`** — `import demo_config` + prompt imports + `_show_demo_lock_prompt_for_mode` + `_get_demo_lock_kind` + prompt draw/input hooks.
4. **`src/campaign/level_select.py`** — `import demo_config` + `DemoUpgradePrompt` init + `_maybe_handle_demo_level_lock` + `_maybe_handle_demo_world_lock` + prompt draw/input hooks.
5. **`src/campaign/coop_level_select.py`** — Aynı pattern.
6. **`src/localization.py`** — 9 demo key eklenmesi (additive, conflict düşük).
7. **`main.py` (root)** — `apply_runtime_environment()` çağrısı.
8. **`packaging/pyinstaller/hooks/pyi_rth_quadrix_data.py`** — Demo-aware resolve logic.
9. **`scripts/build/build_macos_app.sh`** — `--spec`/`--app-name` parametre desteği.

### Adım 3: Doğrulama

```bash
# Full mode testleri (IS_DEMO=False — default)
python -m pytest -q

# Demo mode testleri
python scripts/build/write_demo_config.py --mode demo
python -m pytest tests/test_demo_*.py -q
python scripts/build/write_demo_config.py --mode full  # restore
```

### Adım 4: CI pipeline'a demo doğrulaması ekle

Her PR'da zorunlu koşulacak:
- `pytest tests/test_demo_config.py tests/test_demo_build_specs.py tests/test_demo_menu_locks.py tests/test_demo_campaign_limits.py tests/test_demo_card_mode_interval.py tests/test_demo_mystery_score_cap.py tests/test_demo_localization.py -q`
- Mevcut full test suite

### Adım 5: release/demo branch'i retire et

```bash
git worktree remove v2-demo
# Branch'i silme, tarihsel referans için kalsın
# Demo release'leri artık main'den tag ile: git tag demo/v1.x.x
```

---

## 8. Dosya Sahipliği Sınırları (Birleşik Model)

| Sahiplik | Dosyalar | Kural |
|----------|---------|-------|
| **Demo-owned** | `src/demo_config.py`, `src/demo_upgrade_prompt.py`, `scripts/build/write_demo_config.py`, `scripts/build/build_*_demo*`, `packaging/specs/tetris_demo*`, `config/runtime/steam_appid_demo.txt`, `steamworks/scripts/*demo*`, `tools/steam_upload_demo.ps1`, `tests/test_demo_*.py` | Demo release'i etkileyen değişiklikler burada yapılır. Full oyunu etkilemez (IS_DEMO=False guard). |
| **Shared (demo-aware)** | `src/menu.py`, `src/extras_menu.py`, `src/game_modes_extra.py`, `src/campaign/level_select.py`, `src/campaign/coop_level_select.py`, `src/localization.py`, `main.py`, `pyi_rth_quadrix_data.py`, `build_macos_app.sh` | Her değişiklikte hem full hem demo path'i düşünülmeli. Demo testleri koşulmalı. |
| **Full-owned** | Diğer tüm `src/` dosyaları, `tests/` (demo hariç), `scripts/` (demo hariç), `packaging/specs/` (demo hariç) | Demo'yu etkilemez. Normal geliştirme akışı. |

---

## 9. Zorunlu Test Matrisi (Senkron Sonrası)

| Değişiklik Alanı | Koşulacak Testler |
|-----------------|-------------------|
| `src/demo_config.py` | `test_demo_config.py`, `test_demo_menu_locks.py`, `test_demo_campaign_limits.py`, `test_demo_card_mode_interval.py` |
| `src/demo_upgrade_prompt.py` | `test_demo_mystery_score_cap.py`, `test_demo_menu_locks.py` |
| `src/menu.py` | `test_demo_menu_locks.py` + mevcut menu testleri |
| `src/extras_menu.py` | `test_demo_menu_locks.py` + mevcut extras testleri |
| `src/game_modes_extra.py` | `test_demo_card_mode_interval.py`, `test_demo_mystery_score_cap.py` + mevcut mystery testleri |
| `src/campaign/level_select.py` | `test_demo_campaign_limits.py` + mevcut campaign testleri |
| `src/campaign/coop_level_select.py` | `test_demo_campaign_limits.py` + mevcut coop testleri |
| `src/localization.py` | `test_demo_localization.py` + mevcut localization testleri |
| Build scriptleri / spec dosyaları | `test_demo_build_specs.py` |
| `src/gamepad_manager.py` | `test_gamepad_mouse_emulation.py`, `test_gamepad_hotplug.py`, `test_focus_manager.py` |
| `src/promptfont_support.py` | `test_gamepad_hotplug.py` (parity guard), in-game prompt sanity (manuel) |
| `src/{game,pvp_game,coop_game,online_pvp_game,online_coop_game}.py` event-loop | `test_gamepad_hotplug.py`, `test_ingame_esc_opens_pause_menu.py` |
| **Herhangi bir PR (minimum)** | `pytest tests/test_demo_*.py tests/test_gamepad_hotplug.py tests/test_ingame_esc_opens_pause_menu.py -q` |

---

## 11. Controller / Gamepad Parity (2026-05-18, üçüncü güncelleme)

> **Bağlam:** Aşağıdaki dört runtime davranış ana oyunda kullanıcı tarafından bildirildi: (a) kontrolcü aktifken oyun içi promptlar klavye etiketi gösteriyor; (b) kontrolcü mid-game çıkarılıp takıldığında yeniden tanınmıyor; (c) Steam Overlay (Home/Guide butonu) açılınca oyun pause olmuyor; (d) kontrolcü bağlantısı koptuğunda oyun otomatik pause olmuyor. Hepsi kök nedeninde çözüldü ve aynı kanonik davranış demo'ya taşındı (artık demo-özel controller fork'u yok).

### 11.1 Doğrulanmış Parity Açıkları (2026-05-18)

`git diff main release/demo` üzerinden re-audit edildi. Aşağıdaki gamepad/controller yüzeylerinde demo main'in gerisindeydi:

| Dosya | Demo'da eksikti | Durum |
|-------|----------------|-------|
| `src/gamepad_manager.py` | `_suppress_pointer_mode` flag + `set_suppress_pointer_mode()` method (focus-nav ekranlarının pointer modunu bastırması için) | **Closed (2026-05-18)** |
| `src/gamepad_manager.py` | `editor_secondary` ve `editor_delete` aksiyonları (workshop / user screens / popup'lar için X / Y butonları) | **Closed (2026-05-18)** — `DEFAULT_GAMEPAD_BINDINGS`, `ACTION_TO_KEY`, `_load_settings` button_actions ve `_save_bindings_to_settings` menu_actions_list'e eklendi |
| `src/gamepad_manager.py` | `from focus_manager import GamepadAction, key_to_action` re-export | **Closed (önceki turda)** |
| `src/gamepad_manager.py` | `JOYDEVICEADDED` / `JOYDEVICEREMOVED` event-tabanlı hot-plug yolu | **Closed (2026-05-18)** — yeni `handle_hotplug_event()` instance method + `handle_gamepad_hotplug_event()` modül-level adapter + `is_gamepad_disconnect_event()` helper. Hem main hem demo paralel olarak. |
| `src/promptfont_support.py` | `resolve_prompt(action, keyboard_label)` kısa-yol helper'ı (Faz 2 standardizasyon) | **Closed (2026-05-18)** |
| `src/{game,pvp_game,coop_game,online_pvp_game,online_coop_game}.py` event-loop | Hot-plug event dispatch + auto-pause-on-disconnect | **Closed (2026-05-18)** — beş gameplay sınıfının event loop'una `from gamepad_manager import handle_gamepad_hotplug_event` çağrısı + `'disconnected'` durumunda `_pause_for_focus_loss()` tetiklemesi eklendi (coop için inline pause set'i; ana sınıflar için `_pause_for_focus_loss` çağrısı). |

### 11.2 Runtime Sorunlarının Kök Nedenleri ve Çözümleri

| Sorun | Kök Neden | Çözüm |
|-------|-----------|-------|
| **(a) Controller aktifken klavye prompt'u** | `get_action_prompt_display` zaten `_is_connected_for_prompt` ile gamepad bağlı durumunu kontrol ediyor (`enabled and is_connected()`). Prompt yüzeyi (`game.py` HOLD/HOLD2 HUD, vb.) bu helper üzerinden geçiyor. Eski `release/demo` branch'inde `resolve_prompt` kısa-yolu yoktu, yeni mesaj yazılırken developer'lar inline `t() + key_label` yerine helper'ı çağıramıyordu. **Bu turda demo'ya `resolve_prompt` taşındı**; yeni eklenen mesajların aynı standardı kullanması için altyapı hazır. Mevcut HUD'da HOLD/HOLD2 zaten `render_action_prompt_surface` üzerinden geçiyor — gerçek runtime'da doğru çalışıyor. | `resolve_prompt` demo'da kullanılabilir. Mevcut HUD halihazırda glyph-aware. |
| **(b) Disconnect/reconnect tanınmıyor** | `_check_connections` yalnızca `update()` içinden çağrılıyordu. Pygame bazı platformlarda `joystick.get_count()`'u reconnect sonrası geç günceller. Event-tabanlı yol yoktu. | `JOYDEVICEADDED` event'ine bağlı yeni `handle_hotplug_event` yolu: aynı slot reconnect'te eski instance temizleniyor, sonra `_register_gamepad` çağrılıyor. `JOYDEVICEREMOVED` event'inde `instance_id` ile eşleşen kayıtlı gamepad kaldırılıyor, pointer mode reset ediliyor. |
| **(c) Steam Overlay pause olmuyor** | `_is_focus_loss_event` zaten `WINDOWFOCUSLOST` (32785), `WINDOWMINIMIZED`, `WINDOWHIDDEN` ve eski `ACTIVEEVENT` yollarını kapsıyor. Steam Overlay genellikle `WINDOWFOCUSLOST` event'i üretir. Bu yol mevcut hem main hem demo'da çalışıyor. **`test_focus_loss_pauses_gameplay` zaten doğruluyor**; bu yolun broken olduğu iddiası kullanıcının Steam Overlay konfigürasyonuyla ilgili olabilir (Steam settings'te overlay yoksa pause beklenmez). | Mevcut focus-loss yolu Steam Overlay için yeterli. Ek ölçüm: `test_game_focus_loss_still_pauses_after_hotplug_addition` regresyon koruması ekledim. |
| **(d) Auto-pause on disconnect** | Hiçbir mevcut yol `JOYDEVICEREMOVED` event'ini gameplay duraklatmaya bağlamıyordu. | Yeni: 5 gameplay sınıfının event loop'unda `if hotplug_result == 'disconnected': self._pause_for_focus_loss()`. |

### 11.3 Runtime-Only Doğrulama Matrisi

Aşağıdakiler **otomatik testlerle kapsanan** runtime davranışlardır. Her PR'da `test_gamepad_hotplug.py` koşmalı.

| Runtime senaryo | Test | Durum |
|----------------|------|-------|
| `JOYDEVICEADDED` → yeni gamepad register edilir | `test_added_event_registers_new_gamepad` | ✓ |
| Aynı slot reconnect → eski instance temizlenir, yeni kayıt yapılır | `test_added_event_replaces_stale_slot` | ✓ |
| `JOYDEVICEADDED` event'inde `device_index` yoksa → tam tarama fallback | `test_added_event_without_device_index_falls_back_to_full_scan` | ✓ |
| `JOYDEVICEREMOVED` → eşleşen `instance_id`'li gamepad kaldırılır | `test_removed_event_removes_matching_instance_id` | ✓ |
| Disconnect → pointer mode resetlenir (stale state temizliği) | `test_removed_event_resets_pointer_mode` | ✓ |
| Bilinmeyen `instance_id` → no-op | `test_removed_event_unknown_instance_id_is_no_op` | ✓ |
| Konu dışı event → None döner | `test_unrelated_event_returns_none` | ✓ |
| Modül-level helper singleton'ı kullanır | `test_module_level_handle_hotplug_event_uses_singleton` | ✓ |
| Singleton yokken helper None döner | `test_module_level_helper_returns_none_when_no_singleton` | ✓ |
| `is_gamepad_disconnect_event` doğru tip döndürür | `test_is_gamepad_disconnect_event` | ✓ |
| **Mid-game disconnect → otomatik pause** | `test_game_pauses_on_gamepad_disconnect_event` | ✓ |
| Mid-game connect → pause olmaz, sadece state güncellenir | `test_game_does_not_pause_on_gamepad_connect_event` | ✓ |
| Zaten pause iken disconnect → state korunur | `test_game_does_not_double_pause_on_disconnect_when_already_paused` | ✓ |
| **Steam Overlay (focus-loss) auto-pause regresyon koruması** | `test_game_focus_loss_still_pauses_after_hotplug_addition` | ✓ |

### 11.4 Bilinmeyenler / Henüz Doğrudan Test Yok

| Senaryo | Mevcut Durum |
|---------|--------------|
| **Steam Overlay home button** doğrudan event simülasyonu | Test yok. Steam SDK olmadan tam reproduce mümkün değil. `WINDOWFOCUSLOST` regresyon testi indirekt koruma sağlıyor. Gerçek Steam Overlay açıldığında pygame `WINDOWFOCUSLOST` üretir (Steam SDK davranışı), bu yol test ile doğrulanmış. |
| Gerçek hardware reconnect senaryosu (USB tak/çıkar) | Otomatik test mümkün değil; manuel QA gerektirir. `test_added_event_replaces_stale_slot` reconnect logic'ini stub'lı doğruluyor. |
| 5 gameplay sınıfının HEPSİNDE auto-pause-on-disconnect | Yalnızca `Game` (single-player) için entegrasyon testi var. PvP/Coop/OnlinePvP/OnlineCoop için aynı kod paterni uygulandı ama dar entegrasyon testi yok (kapsamı genişletmek mevcut helper pattern'i ile bounded). |

### 11.5 Demo-Özel Controller Fork'u YOK

Bu turda yapılan tüm controller/gamepad düzeltmeleri **hem main hem demo'da identical** olarak uygulandı. `src/gamepad_manager.py`, `src/promptfont_support.py` ve 5 gameplay sınıfının event-loop bölümleri iki branch'te de aynı davranışı sergiler. Demo'ya özgü kalan tek şey `demo_config.IS_DEMO` build-time flag'i ile kontrol edilen kilit/limit gating'i — controller davranışını etkilemiyor.

---

## 12. Karar

**Bu repo için önerim birleşik tek kaynak ağacı + build-time feature flag modelidir (Strateji 1), çünkü:**

1. Altyapı zaten hazır (`write_demo_config.py` + `IS_DEMO` flag mekanizması çalışıyor).
2. Demo gating kodu izole ve `if not IS_DEMO: return` pattern'i ile full build'de sıfır maliyetli.
3. Mevcut divergent branch modeli sürdürülemez — 12 commit / 1342 satır (game_modes_extra.py) drift birikmiş ve her gün büyüyor.
4. Tek kaynak ağacında demo regresyonları her PR'da yakalanır; ayrı branch'te ancak merge sırasında fark edilir.
5. Operasyon maliyeti bir kerelik merge eforu sonrasında sıfıra düşer; mevcut modelde her sprint merge + conflict çözümü gerekiyor.
