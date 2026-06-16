# Demo Senkronizasyon Kılavuzu — 16 Haziran 2026 (V2)

Bu kılavuz `v2` (ana oyun) ile `quadrix-demo` (demo) arasında **16 Haziran 2026** itibarıyla
yapılan **fiili dosya-bazlı diff analizinin** sonucudur. 35 farklı dosya incelendi; her biri
üç kategoriye ayrıldı.

> **Bu kılavuz yalnızca analiz ve planlama aracıdır. Kod uygulaması ayrı adımda yapılır.**

---

## 0. Kategori Tanımları

| Kategori | Anlam                                                            |
| -------- | ---------------------------------------------------------------- |
| **A**    | Demoya **GETİRİLECEK** — demo-uyumlu, kısıt dışı                 |
| **B**    | **GETİRME** — kısıt kapsamı veya demo-özel (demo'da KALMALI)     |
| **C**    | **GETİRME** — yeni oynanış kontrolü (demo şu anki haliyle kalır) |

### Oynanış Kontrolü Kısıtı (Kategori C)

> **Yeni oynanış/giriş kontrolü mekanikleri demoya getirilmez.** Bu kısıt şunları kapsar:
> lock delay refaktörü, CCW rotasyon, DAS/ARR/DCD/SDF ayarları, `prevent_accidental_hard_drops`,
> `cancel_das_on_direction_change`, `prefer_soft_drop_over_movement`, SRS kick tablosu değişiklikleri,
> T-spin tespit/puanlama, hard drop lockout timer, input buffering.
>
> **Neden:** Ana oyundaki bu kontroller hâlâ geliştirilmeye muhtaçtır; demoya şu haliyle taşımak
> demo oynanışını bozabilir.

### Diğer Kısıtlar (Kategori B)

- Online PvP / Online Co-op
- Mağaza sistemi ve mağazadan satın alınabilecekler (slot 4-5-6 mağazadan açma dahil)
- Satır temizleme animasyonu satın alarak değiştirme (`sweep theme`, `pet`, `get_equipped_*`)
- 150k skor sınırı (`DemoUpgradePrompt`, `_demo_score_cap_*`) — demo-özel, **KORUNMALI**
- Mağazadan kart satın alıp havuza dahil etme (`IS_DEMO` kart kilidi) — demo-özel, **KORUNMALI**

---

## 1. TL;DR — Yönetici Özeti

### Demoya GETİRİLECEKLER (Kategori A)

| #   | Alan                                         | Dosya(lar)            | Öncelik |
| --- | -------------------------------------------- | --------------------- | ------- |
| 1   | Slot-bazlı bağımsız charge sistemi (bug fix) | `game_modes_extra.py` | Yüksek  |

| 3 | Gamepad popup/modal pump + pointer-mode | `main.py`, `color_picker.py`, `gamepad_manager.py` | Yüksek |
| 4 | Gamepad hot-plug (menü state'leri) | `main.py` | Orta |
| 5 | Popup hint etiketleri (promptfont/gamepad) | `main.py`, `menu.py`, `game.py` | Orta |
| 6 | Başarım bildirimi PNG ikon çizimi | `game.py` | Orta |
| 8 | Game-over gamepad hint varyantı | `game.py`, `localization.py` | Orta |
| 9 | Daily Challenge lokalizasyon refaktörü | `game_modes_advanced.py`, `localization.py` | Orta |
| 10 | `platform_utils.key_hint_label` (macOS tuş etiketi) | `platform_utils.py` | Düşük |
| 11 | `pump_gamepad_into_event_queue` yardımcısı | `gamepad_manager.py` | Düşük |
| 12 | `ui_scaling` alias senkronizasyonu | `ui_scaling.py` | Düşük |
| 13 | `retro_style` font cache dayanıklılığı | `retro_style.py` | Düşük |
| 14 | `user_manager` slot sayısı get/set API | `user_manager.py` | Düşük |
| 15 | PVP Oyuncu 2 keybind + dual-slot genelleme | `settings_screen_tabbed.py` | Düşük |
| 16 | `bg_transparency` varsayılanı 0.7 → 0.3 | `settings_manager.py`, `game.py`, `main.py`, `menu.py`, `settings_screen_tabbed.py`, `graphics_menu.py` | Opsiyonel |
| 17 | A kategorisi lokalizasyon anahtarları (7) | `localization.py` | Yüksek |
| 18 | Daily Challenge `dc_*` lokalizasyon (91 anahtar) | `localization.py` | Orta (9 ile birlikte) |

### GETİRİLMEYECEKLER (Kategori B + C)

| Alan | Kategori                                  | Neden                                    |
| ---- | ----------------------------------------- | ---------------------------------------- | --------------- |
| 2    | Slotlar doluyken Lunar ödül kartı sistemi | `game_modes_extra.py`, `localization.py` | demoda olmamalı |
| 7    | Maç sonu "Kazanılan Lunar" kutusu         | `game.py`                                | demoda olmamalı |

| CCW rotasyon, DAS/DCD/SDF, lock delay refaktörü | C | Oynanış kontrol kısıtı |
| `pieces.py` SRS kick tablosu genişlemesi | C | Oynanış kontrol kısıtı |
| `settings_screen_tabbed.py` yeni kontrol slider/toggle satırları | C | Oynanış kontrol kısıtı |
| 10 adet `settings_*/dcd_*/sdf_*` lokalizasyon | C | Oynanış kontrol kısıtı |
| Online PvP/Co-op | B | Kısıt |
| Mağaza (store) sistemi + slot 4-5-6 satın alma | B | Kısıt |
| Sweep theme / pet satın alma | B | Kısıt |
| 150k skor sınırı (DemoUpgradePrompt) | B-KORU | Demo-özel, demoda KALMALI |
| IS*DEMO kart kilidi | B-KORU | Demo-özel, demoda KALMALI |
| `board.py` `level_lines_per_level` kaldırma | C/belirsiz | Tempo değişikliği, oynanış |
| `tutorial_scn*_`90 lokalizasyon anahtarı | ayrı özellik | Bu tur kapsamı dışı |
|`campaign\__` 1 lokalizasyon anahtarı | ayrı özellik | Kampanya kapsamı dışı |

---

## 2. Dosya-Bazlı Detay Analizi

### 2.1 Altyapı Dosyaları

#### `platform_utils.py` (+59 satır) — A

`key_hint_label(label: str) -> str` fonksiyonu eklendi. Windows/Linux'ta etiketi olduğu gibi
döndürür; macOS'ta `ENTER→return`, `BACKSPACE→delete`, `ESC→esc`, `CMD→⌘` vb. çevirir.
`'ENTER / ESC'` gibi `/` ayraçlı çoklu etiketler de parça parça çevrilir.

- **Demoda yok.** `get_display_flags`, `create_display`, `normalize_mouse_pos` vb. zaten ortak;
  sadece `key_hint_label` fonksiyonu ve `_MACOS_KEY_LABELS` tablosu eksik.
- **Bağımlılar:** `main.py`, `menu.py`, `game.py` popup hint satırlarında `key_hint_label` çağırıyor.
- **Risk:** Bağımsız yardımcı, yan etkisiz. Düşük risk.

#### `gamepad_manager.py` (+39 satır) — A

`pump_gamepad_into_event_queue(delta_ms, context)` fonksiyonu eklendi. Bloklayıcı
`while pygame.event.get()` döngülerine sahip popup/modal ekranlarda (renk seçici, metin girişi,
mod intro popup) gamepad girişini canlı tutar: context ayarlar, `manager.update()` çağırır,
üretilen sentetik olayları `pygame.event.post()` ile kuyruğa ekler.

- **Demoda yok.** `get_gamepad_manager`, `is_gamepad_connected` vb. zaten ortak; yalnızca
  `pump_gamepad_into_event_queue` eksik.
- **Bağımlılar:** `main.py` (popup'lar), `color_picker.py`. `handle_gamepad_hotplug_event` da
  v2'de eklenmişse import listesini güncelle.
- **Risk:** Bağımsız yardımcı. Düşük risk.

#### `ui_scaling.py` (+9 satır) — A (düşük öncelik)

`normalize_ui_scale_preset` içinde `sys.modules` üzerinden diğer alias'ın `_UI_SCALE_PRESET`
değerini senkronize eden blok eklendi. Test izolasyon düzeltmesi; oyun runtime'ında tetiklenmez.

- **Demoda yok.** Küçük, bağımsız. Düşük öncelik.

#### `retro_style.py` (+30, -30 satır) — A (düşük öncelik)

`_font_is_alive` ve `_cached_font_if_alive` yardımcıları eklendi; `get_font`/`get_mono_font`
içindeki eski cache-geçersizlik kontrolü bu iki yardımcıya refaktör edildi. `pygame.quit()`
sonrası font handle'larını güvenli biçimde yakalar (test izolasyon dayanıklılığı). Runtime
davranışı değişmiyor.

- **Demoda yok.** Fonksiyonel etki yok; test stabilitesi. Düşük öncelik.

#### `ui_scaling.py`, `retro_style.py` öneri: İkisi de bağımsız, doğrudan dosya kopyasıyla getirilebilir. Demo-özel kod yok.

#### `color_picker.py` (+54 satır) — A

`pygame_color_picker` ve `pygame_text_input` bloklayıcı döngülerine gamepad desteği eklendi:

- Pointer modunu bastır (`set_suppress_pointer_mode(True)`), döngü sonunda geri al.
- Her frame `pump_gamepad_into_event_queue(16.0, 'menu')` çağrısı.
- Hint metni `resolve_nav_hint_label('ENTER'/'ESC', ...)` ile gamepad-aware etiketlere dönüştürüldü.

- **Bağımlı:** `gamepad_manager.pump_gamepad_into_event_queue` ve `promptfont_support.resolve_nav_hint_label`.
  Bu iki bağımlılık demoda var mı kontrol et; `pump_gamepad_into_event_queue` bu turda getiriliyor (§2.1 gamepad_manager).
- **Risk:** `pump_gamepad_into_event_queue` gelmeden `color_picker.py` değişikliği `ImportError` verir
  → **bağımlılık sırası önemli**: önce `gamepad_manager`, sonra `color_picker`.

#### `data_paths.py` (+76, -2 satır) — **İNCELE / Dikkatli**

`_detect_steam_appid()` fonksiyonu eklendi: env var, `steam_appid.txt`, `_MEIPASS`, proje kök
gibi konumlardan Steam App ID'sini otomatik tespit eder. `_DEFAULT_APP_NAME` demo ve full için
farklıdır (`quadrix_full` vs `quadrix_demo`).

- **Demo-özel risk:** Demo'nun kendi App ID'si var. Bu değişiklik `_DEFAULT_APP_NAME` mantığını
  değiştiriyor olabilir. **Dosyayı komple kopyalama; sadece `_detect_steam_appid` fonksiyonunu**
  aktarıp `_DEFAULT_APP_NAME = "quadrix_demo"` değerinin korunduğundan emin ol.
- **Öneri:** Bu dosyayı en sona bırak; Steam/build süreciyle test et.

#### `user_manager.py` (+21, -3 satır) — A (düşük öncelik)

- `t()` yardımcısında `sys.modules` lookupı kaldırıldı, doğrudan `localization.t(...)` çağrısı.
- `_load_users` içinde `unlocked_card_slots` profil migrasyonu (eksikse 3 ata).
- `_new_user_data` varsayılanına `unlocked_card_slots: 3` eklendi.
- `get_unlocked_card_slots(username)` ve `set_unlocked_card_slots(count, username)` metotları eklendi.

Slot sistemi demoda zaten var ama `UserManager.get_unlocked_card_slots` / `set_unlocked_card_slots`
demoda yok. `game_modes_extra.py` slot charge sistemi bu API'yi kullanıyorsa birlikte getirilmeli.

#### `sound.py` (+1, -1) — **Yok sayılabilir**

`coin_collect` SFX yorumundaki Türkçe karakter düzeltmesi (kozmetik). Fonksiyonel fark yok.
Demoda `coin_collect` zaten mevcut (önceki senkronizasyondan). **Aksiyon yok.**

#### `background.py` (+2, -2) — **Yok sayılabilir**

Log satırlarında emoji → ASCII (`✅ →[SUCCESS]`, `⚠️ →[WARNING]`). Kozmetik. **Aksiyon yok.**

#### `graphics_menu.py` (+1, -1) — **Opsiyonel**

`bg_transparency` varsayılanı 0.7 → 0.3. `bg_transparency` değişikliği 6 dosyayı etkiliyor
(§2.6). Hepsi birlikte ya değiştirilir ya da hiçbiri. Ayrıca bkz. §2.6.

#### `pieces.py` (+8, -8) — **C (oynanış kontrolü)**

`SRS_KICKS_I` ve `SRS_KICKS_180_I` tablolarına ek kick adımları eklendi. 180 dönüş/SRS+
geliştirmesi. **Getirme.** Demo şu anki SRS haliyle kalır.

#### `board.py` (+1, -6) — **C / Belirsiz**

`level_lines_per_level` özelliği kaldırılıp `self.level = ... // 5` sabit bölmesine geçildi.
Hafif tempo refaktörü. AGENTS.md §7: "board.level'a dokunma." **Getirme.**

---

### 2.2 game.py (+299, -71) — Karışık (A + B + C)

#### Kategori A — GETİRİLECEK

| Bulgu                             | Fonksiyon/Bölge                                                                           | Açıklama                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `key_hint_label` importu          | import bloğu                                                                              | macOS tuş etiketi yardımcısı (platform_utils bağımlı)                           |
| Başarım bildirim PNG ikonu        | `_achievement_notif_icon_cache` init + notif çizim döngüsü                                | `get_achievement_icon_path` ile renkli PNG; `load_image` cache'li               |
| Maç sonu "Kazanılan Lunar" kutusu | `_run_start_lunar`, `_game_over_earned_lunar`, `_current_lunar_balance()`, overlay çizimi | Maç başı bakiye kaydı, game-over'da fark gösterimi (ease-out animasyonlu sayaç) |
| Game-over gamepad hint            | footer çizim                                                                              | Gamepad bağlıyken `game_over_hint_gamepad` (restart_key/menu_key etiketli)      |
| Buton hover highlight şeridi      | `_btn_bg` çizim                                                                           | Hover'da üst kenara ince vurgu çizgisi (görsel düzeltme)                        |
| `bg_transparency` 0.7→0.3         | init + overlay                                                                            | Görsel (§2.6 ile birlikte)                                                      |
| Pause menüsü gamepad nav hint     | `_show_pause_menu` / popup                                                                | `resolve_nav_hint_label` ile gamepad buton ipucu                                |

#### Kategori B — GETİRME

| Bulgu                                                                                    | Bölge                    |
| ---------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------ |
| `get_equipped_line_sweep_theme` / `get_equipped_pet` importu + parametreli sweep çağrısı | `draw_rainbow_cat_sweep` | Satın alınan tema/pet ile sweep değiştirme |

#### Kategori C — GETİRME (Oynanış kontrolü)

| Bulgu                                                                                                 | Bölge                                                 |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Lock delay refaktörü: `_successful_input_this_frame`, `lock_reset_count`, `stall_timer`, `lock_timer` | init + `_update_grounded_after_action` + `update`     |
| DCD / Hard drop lockout timer                                                                         | init + spawn/hold + timer güncelleme + DAS            |
| CCW rotasyon (`rotate_ccw` keybind + `try_rotate_srs(-1)`)                                            | event handler                                         |
| DAS cancel-on-direction-change                                                                        | DAS sıfırlama                                         |
| SDF (Soft Drop Factor)                                                                                | `get_soft_drop_speed` + update + infinite SDF instant |
| `prefer_soft_drop_over_movement` DAS askıya alma                                                      | DAS bloğu                                             |
| `_try_move_left/right` dönüş tipi + input buffer flag                                                 | hareket yardımcıları                                  |

#### Belirsiz

- **T-spin mesaj akışı refaktörü**: İçinde hem mesaj metni kaldırma (C'ye yakın — T-spin tespiti
  bağlı) hem de ses/efekt yeniden düzenleme (A) var. Demo'da `t_spin_type` tespiti zaten mevcut
  (18e4603 commit'i ile geldi); mesaj metni kaldırma kararı iç içe. **Önceki haliyle bırak.**

---

### 2.3 menu.py (+27, -300) — A + B

#### Kategori A — GETİRİLECEK

| Bulgu                                                 | Bölge                                                                      |
| ----------------------------------------------------- | -------------------------------------------------------------------------- |
| `_select_hint_label()` metodu                         | Popup hint: gamepad'e göre `menu_hint_select_gamepad` / `menu_hint_select` |
| `resolve_nav_hint_label` importu (promptfont_support) | Import bloğu, opsiyonel fallback                                           |
| Exit prompt gamepad-aware hint'leri                   | `exit_confirm_hint`/`exit_cancel_hint` = `resolve_nav_hint_label(...)`     |
| Daily prompt gamepad-aware hint'leri                  | play_hint/cancel_hint                                                      |
| `bg_transparency` 0.7→0.3                             | BackgroundSelectorScreen varsayılanı (§2.6 ile birlikte)                   |

#### Kategori B — GETİRME (demo-özel KORU)

Demoda `-` satırları (v2'de yok ama demoda var) — **silinmemeli, korunmalı**:

- `DemoUpgradePrompt` / `show_demo_transition_lock_prompt` importu
- `_maybe_handle_demo_main_action` (online kilit aksiyonu)
- `_is_demo_locked_main_action` + `_draw_locked_split_overlay`
- PvP/Coop split panellerinde `online_locked` overlay
- `_build_main_dashboard_layout` + `_resolve_main_split_mouse_action` (demo-kilit yönlendirmesi)
- `handle_input`/`draw`'da `_demo_upgrade_prompt` aktif/çizim blokları

> **DİKKAT:** menu.py diff'inde `-300` satır var; bunların büyük çoğunluğu demo-kilit kodlarıdır.
> v2 dosyasıyla ezme kesinlikle yapılmamalı; yalnızca `+27` satırlık A kısmını cherry-pick et.

---

### 2.4 main.py (+146, -45) — A + B

#### Kategori A — GETİRİLECEK

| Bulgu                                                                       | Bölge                                           |
| --------------------------------------------------------------------------- | ----------------------------------------------- |
| `_popup_confirm_cancel_hints()` helper                                      | Gamepad bağlıyken confirm/back etiketi döndürür |
| `_show_mode_intro_popup` gamepad pump + hint                                | Bloklayıcı popup'ta gamepad canlı               |
| `_show_zen_start_popup` gamepad pump + hint                                 | Aynı                                            |
| `_show_tutorial_prompt` gamepad pump + hint                                 | Aynı                                            |
| `handle_gamepad_hotplug_event` / `pump_gamepad_into_event_queue` importları | Import bloğu                                    |
| Gamepad hot-plug (menü/UI state'leri)                                       | JOYDEVICEADDED/REMOVED merkezi işleme           |
| `achievement_screen.sound` bağlama                                          | Splash sonrası coin-collect sesi                |
| `achievement_screen.reset_for_open()` None-guard                            | State geçişinde Lunar sayaç reset               |
| `bg_transparency` 0.7→0.3                                                   | Varsayılan (§2.6 ile birlikte)                  |

#### Kategori B — GETİRME

| Bulgu                                                      | Bölge                          |
| ---------------------------------------------------------- | ------------------------------ |
| `demo_config` / `apply_runtime_environment` kaldırılması   | Demo runtime — KORU            |
| `show_demo_store_lock_prompt` → `state = 'store'`          | Mağaza açma — KORU lock prompt |
| `online_coop_present` / `present_and_finalize_online_coop` | Online co-op — GETİRME         |

---

### 2.5 game_modes_extra.py (+273, -215) — A + B

> **Mystery / Kart Ustalığı modu.** En kritik dosya. 150k cap kodu demoda KALMALI.

#### Kategori A — GETİRİLECEK

**1) Slotlar doluyken Lunar ödül kartı sistemi** (demoda YOK, doğrulandı):

- `get_card_title`/`get_card_description`/`_get_card_type_label` Lunar dalları
- `get_choices` içinde dolu-slot kontrolü → seçimi Lunar kazanma kartına çevirme
- `_get_lunar_amount_for_rarity` (nadirliğe göre Lunar miktarı)
- `_is_slot_eligible_card` Lunar elemesi
- `_apply_card_effect` Lunar dalı → `user_manager.add_fragments` (demoda `add_fragments` **var**, uyumlu)
- Lokalizasyon: `lunar_reward_title`, `lunar_reward_desc` (A kategorisi anahtarlar, §2.7)

**2) Slot-bazlı bağımsız charge (hak) sistemi** (demoda YOK, doğrulandı):

- `_active_slot_index_for_ability`, `_get_active_slot_card`, `_get_charges_for_effect`,
  `_set_charges_for_effect`, `_get_and_set_active_slot_for_poll`
- Her yetenek için slot-bazlı property/setter: `_sniper_charges`, `_hole_hunter_charges`,
  `perk_rewind_uses`, `phase_shift_uses_remaining`, `hammer_charges_remaining`,
  `bomb_master_charges`, `_freeze_drop_charges`, `tunnel_charges_remaining`,
  `_hold_destroyer_charges`; `swap_current_piece_shape` override
- `PerkManager.rewind_uses` property
- `update()` içinde g/h/m/b/f tuş bloklarında slot-context try/finally
- `_refresh_slot_charges`, `_open_slot_allocation`, `_activate_slot` slot-context
- **Anlam:** "Aynı kart birden fazla slotta varsa her slotun hakkı bağımsız sayılır" bug fix.
  Demonun mevcut slot sistemine (active_slots/unlocked_slots/SLOT_CARD_SPECS) bağlı.

#### Kategori B — GETİRME / DEMO-ÖZEL KORU

Demoda `-` (v2'de yok, demoda var) — **silinmemeli**:

- `demo_config`, `demo_upgrade_prompt` importları
- `MysteryCardManager` içindeki `IS_DEMO` nadirlik/kart kilidi dalı (mağaza kart kilidi)
- 150k cap blokları: `_get_demo_score_cap`, `_should_trigger_demo_score_cap`,
  `_activate_demo_score_cap_prompt`, `_maybe_activate_demo_score_cap_prompt`,
  `wants_mouse_visible` cap dalı, init/restart cap değişkenleri, `update`/`handle_input`/`draw`
  cap blokları

> **DİKKAT:** Bu dosyada Kategori A (slot charge + Lunar reward) ile demo-özel cap kodu **iç içe**.
> v2 dosyasıyla **komple ezme yapılamaz** — cap kodunu silersin. A öğelerini fonksiyon-fonksiyon
> cherry-pick et; her eklemeden sonra cap kodunun yerinde olduğunu doğrula.

#### Belirsiz

- **init/restart'taki büyük `-` blok (≈100 satır)**: hem cap değişkenleri hem genel perk/efekt
  değişkenleri içeriyor. v2'de bu değişkenler başka yere **taşınmış** olabilir (salt silme değil).
  Cap-dışı kısımların A/B ayrımı dikkat ister; bu blok birebir taşınırsa cap kodunu sürükler.

---

### 2.6 game_modes_advanced.py (+163, -62) — A

**DailyChallengeMode tam lokalizasyon refaktörü** (sadece metin/lokalizasyon, oynanış değil):

- Yardımcılar: `_format_localized_number`, `_format_bonus_multiplier`, `_get_translation_entry`,
  `_translate`, `_challenge_effect_slot_count`, `_expected_localization_keys`,
  `_resolve_challenge_text`, `_resolve_challenge_effects`
- `_build_objective_line` → `dc_target_*`, `_build_rule_line` → `dc_rule_*`,
  `_build_fail_line` → `dc_fail_*`, `_build_reward_line` → `dc_reward_summary`
- `_materialize_texts` çok-dilli çözümleme, `draw_mode_info` hardcoded TR/EN yerine `t(...)`

- **Bağımlı:** 91 adet `dc_*` lokalizasyon anahtarı (demoda YOK, §2.7). Lokalizasyon getirilmezse
  `t()` fallback/default ile çalışır ama tam yerelleştirme için anahtarlar gerekir.
- **Risk:** Daily Challenge modu demoda aktif mi? Aktifse bu refaktör + `dc_*` birlikte getirilmeli.

---

### 2.7 settings_screen_tabbed.py (+102, -30) — A + C

#### Kategori A — GETİRİLECEK

- **PVP Oyuncu 2 keybind bölümü** (`tab_pvp_player2`) + player1'e `action_key`/`section` alanları.
  Demoda `pvp.player1` **var**, player2 **yok**; `_is_dual_slot_section` demoda mevcut.
- `section == 'single_player'` → `_is_dual_slot_section(section)` genelleştirmesi (keybind hint +
  atama yollarında). Demo'da `single_player` özel-durumu kullanılıyorsa, geçişte `_is_dual_slot_section`'ın
  `single_player`'ı da kapsadığını doğrula.
- Close (×) buton docstring/yorum İngilizceleştirme (kozmetik, düşük öncelik).
- `bg_transparency` 0.7→0.3 (§2.8 ile birlikte).

#### Kategori C — GETİRME (Oynanış kontrolü)

Yeni DAS/ARR/DCD/SDF kontrol ayar satırları — **getirilmeyecek**:

- `das_delay` step 10→1; `das_repeat` (ARR) min/max/step 10-500/5 → 0-100/1
- `soft_drop_speed` satırı kaldırılıp: `dcd` (slider), `sdf` (selector),
  `prevent_accidental_hard_drops` (toggle), `cancel_das_on_direction_change` (toggle),
  `prefer_soft_drop_over_movement` (toggle) eklendi
- `SDF_OPTIONS` listesi, `_load_all_settings` yeni anahtar yüklemeleri, reset-defaults tab listesi,
  `sdf` değer gösterimi/selector mantığı, açıklama metinleri, slider fill-color listesi
- **Belirsiz:** `das_delay` 170→167, `das_repeat` 50→33 varsayılan değişiklikleri yeni DAS/ARR
  sisteminin parçası → **C ile birlikte getirme**.

#### `settings_manager.py` (+15, -4) — A + C ayrımı

- **C (GETİRME):** `rotate_ccw` keybind, `das_delay/das_repeat/dcd/sdf` değerleri,
  `prevent_accidental_hard_drops`, `cancel_das_on_direction_change`, `prefer_soft_drop_over_movement`
  varsayılanları + debounced-save listesine eklenmeleri.
- **A (opsiyonel):** `bg_transparency` 0.7→0.3 (§2.8).

> **DİKKAT:** `settings_manager.py` tek dosyada hem C (kontrol ayarları) hem A (bg_transparency) var.
> Sadece `bg_transparency` satırını al; yeni kontrol anahtarlarını **getirme**.

---

### 2.8 bg_transparency Varsayılanı 0.7 → 0.3 — Opsiyonel, 6 dosya

Etkilenen dosyalar: `settings_manager.py`, `game.py`, `main.py`, `menu.py`,
`settings_screen_tabbed.py`, `graphics_menu.py`.

- Bu fonksiyonel değil, **görsel tercih**. Demoda v2 ile görsel parite isteniyorsa **altı yerde
  birlikte** değiştir; istenmiyorsa demo 0.7'de bırakılır.
- **Karar kullanıcıya aittir — ya hepsi ya hiçbiri.**

---

## 3. localization.py Analizi

v2'de **2418** anahtar, demoda **2248**. Fark: **209 anahtar v2'de var demoda yok**, 39 anahtar
demoda var v2'de yok (demo-özel `card_*` isimleri vb. — KORU). 209 eksik anahtarın dağılımı:

| Grup                                                              | Adet | Kategori     | Aksiyon                   |
| ----------------------------------------------------------------- | ---- | ------------ | ------------------------- |
| `dc_*` (Daily Challenge)                                          | 91   | A            | GETİR (§2.6 ile birlikte) |
| `tutorial_scn_*` (eğitim senaryoları)                             | 90   | ayrı özellik | Bu tur KAPSAMI DIŞI       |
| Oynanış kontrolü (`settings_dcd`, `sdf_desc`, `cancel_das_*` vb.) | 10   | C            | GETİRME                   |
| Mağaza/slot (`store_product_mystery_slot_4..6`, `store_slot_*`)   | 10   | B            | GETİRME                   |
| `campaign_cond_move_limit`                                        | 1    | ayrı özellik | KAPSAMI DIŞI              |
| Genel/demo-ilgili                                                 | 7    | A            | GETİR                     |

### 3.1 A Kategorisi Lokalizasyon Anahtarları (7) — GETİR

```
coop_game_over_hint_gamepad
game_over_earned_lunar
game_over_hint_gamepad
lunar_reward_desc
lunar_reward_title
menu_hint_select_gamepad
tutorial_chapter_progress
```

> `game_over_earned_lunar` ve gamepad hint anahtarları demoda zaten olabilir (önceki senkronizasyon).
> Getirmeden önce her birini `grep` ile doğrula; eksik olanları 11 dilde ekle.

### 3.2 GETİRİLMEYECEK Lokalizasyon

- **C (10 anahtar):** `cancel_das_on_direction_change_desc`, `dcd_desc`,
  `prefer_soft_drop_over_movement_desc`, `prevent_accidental_hard_drops_desc`, `sdf_desc`,
  `settings_cancel_das_on_direction_change`, `settings_dcd`,
  `settings_prefer_soft_drop_over_movement`, `settings_prevent_accidental_hard_drops`, `settings_sdf`
- **B (10 anahtar):** `store_product_mystery_slot_4_*` ... `slot_6_*`, `store_slot_*`
- **Ayrı özellik:** 90 `tutorial_scn_*`, 1 `campaign_*`

---

## 4. Kısıt Kapsamı Dosyaları (GETİRME) — Özet

Bu dosyalar diff listesinde farklı çıkıyor ama tamamı veya neredeyse tamamı kısıt kapsamında.
**İçerik analizine girilmedi; GETİRME olarak işaretli.**

| Dosya                                      | Kategori | Not                                               |
| ------------------------------------------ | -------- | ------------------------------------------------- |
| `store_screen.py` (+343, -61)              | B        | Mağaza sistemi — GETİRME                          |
| `online_coop_game.py` (+311, -27)          | B        | Online co-op — GETİRME                            |
| `online_pvp_game.py` (+246, -34)           | B        | Online PvP — GETİRME                              |
| `pvp_game.py` (+121, -10)                  | B/İNCELE | Yerel PvP olabilir; oynanış kontrolü içeriyorsa C |
| `sweep_effects.py` (+49, -48)              | B        | Satır temizleme animasyonu/tema — GETİRME         |
| `campaign/power_ups.py` (+144, -18)        | ayrı     | Kampanya — kapsam dışı                            |
| `campaign/level_data.py` (+54, -64)        | ayrı     | Kampanya — kapsam dışı                            |
| `campaign/level_select.py` (+7, -85)       | ayrı     | Kampanya — kapsam dışı                            |
| `campaign/coop_level_select.py` (+32, -51) | ayrı     | Kampanya co-op — kapsam dışı                      |
| `campaign/coop_level_data.py` (+20, -20)   | ayrı     | Kampanya — kapsam dışı                            |
| `campaign/campaign_mode.py` (+1, -30)      | ayrı     | Kampanya — kapsam dışı                            |
| `campaign/campaign_ui.py` (+16, -4)        | ayrı     | Kampanya — kapsam dışı                            |
| `extras_menu.py` (+2, -79)                 | İNCELE   | Çoğu `-` (demo-özel); ezme yapma                  |

> **pvp_game.py uyarısı:** Yerel PvP demoda destekleniyorsa içindeki gamepad/UI iyileştirmeleri A
> olabilir ama oynanış kontrolü (lock delay/DAS) içeriyorsa C. Getirmeden önce diff'ini ayrıca incele.

---

## 5. Önerilen Entegrasyon Sırası (Kod Adımı İçin)

Bağımlılık sırası kritik. Aşağıdaki sıra `ImportError`/`AttributeError` riskini en aza indirir.

### Faz 1 — Bağımsız altyapı (düşük risk)

1. `platform_utils.py`: `key_hint_label` + `_MACOS_KEY_LABELS` ekle
2. `gamepad_manager.py`: `pump_gamepad_into_event_queue` (+ varsa `handle_gamepad_hotplug_event`) ekle
3. `ui_scaling.py`: alias senkronizasyon bloğu
4. `retro_style.py`: `_font_is_alive` / `_cached_font_if_alive` refaktörü
5. `user_manager.py`: `get_unlocked_card_slots`/`set_unlocked_card_slots` + profil migrasyonu

### Faz 2 — Lokalizasyon (UI'den önce)

6. `localization.py`: A kategorisi 7 anahtar (eksik olanları doğrula, 11 dilde ekle)
7. `localization.py`: 91 `dc_*` anahtarı (Daily Challenge için, §2.6 ile birlikte)

### Faz 3 — Kart Ustalığı (en dikkatli)

8. `game_modes_extra.py`: slot-bazlı charge sistemi (cherry-pick, cap kodunu koru)
9. `game_modes_extra.py`: Lunar ödül kartı sistemi (cherry-pick)
   - Her eklemeden sonra: 150k cap kodu + IS_DEMO kilidi yerinde mi doğrula

### Faz 4 — UI / gamepad

10. `color_picker.py`: gamepad pump + nav hint (gamepad_manager bağımlı — Faz 1 sonrası)
11. `main.py`: popup pump/hint + hot-plug + achievement sound wiring (store/online/demo_config'e DOKUNMA)
12. `menu.py`: `_select_hint_label` + exit/daily gamepad hint (demo-kilit kodlarına DOKUNMA, `+27`'yi cherry-pick)
13. `game.py`: başarım PNG ikonu + maç sonu Lunar kutusu + game-over gamepad hint (sweep theme/pet ve lock-delay/DAS/CCW'ye DOKUNMA)

### Faz 5 — Daily Challenge + ayarlar

14. `game_modes_advanced.py`: Daily Challenge lokalizasyon refaktörü
15. `settings_screen_tabbed.py`: PVP P2 keybind + dual-slot genelleme (DAS/DCD/SDF satırlarına DOKUNMA)

### Faz 6 — Opsiyonel / sona bırak

16. `bg_transparency` 0.7→0.3 (6 dosya, kullanıcı onayıyla, hepsi birlikte)
17. `data_paths.py`: `_detect_steam_appid` (demo App ID korunarak, build ile test)

---

## 6. Yüksek Riskli Invariant'lar (Kırma)

1. **150k cap kodu silinmez.** `game_modes_extra.py` ve `menu.py` v2 ile **komple ezilmez**.
   Cap kodu (`_demo_score_cap_*`, `DemoUpgradePrompt`) demoda KALIR.
2. **IS_DEMO kart kilidi korunur.** Mağazadan kart açma demo-özel kilit mantığı (`MysteryCardManager`).
3. **Oynanış kontrolü getirilmez.** Lock delay, CCW, DAS/ARR/DCD/SDF, SRS kick, T-spin,
   hard-drop lockout — hiçbiri demoya taşınmaz. (`game.py`, `pieces.py`, `board.py`,
   `settings_manager.py`, `settings_screen_tabbed.py` ilgili satırları.)
4. **Online + mağaza + sweep satın alma getirilmez.** `store_screen`, `online_*`, sweep theme/pet.
5. **menu.py / main.py demo-kilit kodu korunur.** `show_demo_store_lock_prompt`,
   `_maybe_handle_demo_main_action`, online kilit overlay'leri silinmez.
6. **Board level ≠ Card level.** `board.level`'a dokunma (AGENTS.md §7). `board.py` tempo
   refaktörü getirilmez.
7. **Bağımlılık sırası.** `color_picker` ve `main.py` popup pump'ı, `gamepad_manager`'daki
   `pump_gamepad_into_event_queue`'dan ÖNCE getirilirse `ImportError`.
8. **Lokalizasyon 11 dil.** Yeni anahtarlar tüm dillerde doldurulur (AGENTS.md §3.5).
9. **data_paths App ID.** `_DEFAULT_APP_NAME = "quadrix_demo"` korunur; full değeriyle ezilmez.

---

## 7. Doğrulama Matrisi (Kod Adımından Sonra)

Demoda test komutu (`AGENTS.md` §6). Dar → geniş sıra:

```powershell
# Kart Ustalığı (slot charge + lunar reward + cap bozulmadı mı)
py -m pytest quadrix-demo/tests -q -k "mystery"
# Başarım / lunar
py -m pytest quadrix-demo/tests/test_achievement_rewards.py -q
# Lokalizasyon
py -m pytest quadrix-demo/tests -q -k "localization"
# Demo gating (150k cap, online/store kilidi bozulmadı mı)
py -m pytest quadrix-demo/tests -q -k "demo"
```

Manuel kontroller:

- Kart Ustalığı: aynı kart 2 slotta → her slotun hakkı bağımsız sayılıyor mu
- Slotlar dolu → kart seçimi Lunar ödül kartına dönüşüyor, `add_fragments` çağrılıyor mu
- Gamepad: mod intro / zen / tutorial popup'larında kontrolcü çalışıyor mu
- **Regresyon:** Mağaza hâlâ kilit prompt açıyor; online kilitli; 150k'da cap prompt tetikleniyor;
  slot sistemi çalışıyor; oynanış kontrolleri (DAS/lock) demonun ESKİ haliyle aynı

---

## 8. Kaynak Referanslar

- Önceki kılavuz: `docs/DEMO_SENKRONIZASYON_KILAVUZU_2026-06-16.md` (V1 — bu V2 onu günceller)
- Operasyonel kurallar: `quadrix-demo/AGENTS.md` (routing §3, invariant §7, doğrulama §6)
- Analiz tarihi: 2026-06-16. v2 son commit `6488c57`, demo son commit `3cd03d2`.
