# Plan: Kart Ustalığı Reroll + Görev Modu Retry + Pause Music Ducking + Menü Müziği Slider Live

**Created:** 2026-02-28
**Status:** Ready for Atlas Execution

## Summary

Bu iş paketi 5 değişiklik içerir: (1) Kart Ustalığı (Mystery/Card Mastery) kart seçim ekranına “Reroll/Yeniden Çek” butonu eklemek, (2) Görev/Kampanya modunda (CampaignMode) başarısız/tamamlandı overlay’lerinde ve ESC pause menüsünde “Tekrar Dene” seçeneğini görünür ve çalışır hale getirmek, (3) Kampanya başarısız overlay’ini “oyun bitti” (Game Over) ekran çizimine yaklaştırmak ve kırmızı varyantını kullanmak, (4) ESC ile pause açıldığında müziği “duck” ederek azaltmak ve kapatınca geri almak, (5) Ayarlardaki “Ana Menü Müziği” slider’ının mouse sürüklemede anlık ses güncellemesini düzeltmek.

Öncelik: Görev modunda retry seçeneği (önemli) ve slider bug fix.

## Context & Analysis

**Relevant Files:**
- src/game_modes_extra.py: Kart Ustalığı akışı (`MysteryMode`, `MysteryCardUI`, `MysteryCardManager`); “Kart almadan devam et” butonu ve input handling burada.
- src/campaign/campaign_mode.py: Görev/Kampanya oyun döngüsü; `level_failed`, `level_complete` overlay state’leri ve `handle_input()`.
- src/campaign/campaign_ui.py: Kampanya overlay çizimleri (`CampaignUIEffects.draw_level_failed_overlay`, `draw_level_complete_overlay`).
- src/game.py: ESC pause menüsü, `self.paused` state geçişleri, “game over” overlay çizimi `_draw_game_over_overlay()` ve click target’lar.
- src/sound.py: `SoundManager` müzik ses seviyesi ve mixer kontrolü; duck/unduck yok.
- src/pvp_game.py: Pause state değişimleri (ESC/P) — ducking burada da uygulanmalı.
- src/settings_screen_tabbed.py: Slider güncelleme; MOUSEMOTION drag path action’ı yutuyor.
- src/main.py: Ayar ekranı action’larını uyguluyor; `change_menu_music_volume` aksiyonunda `menu_sound.set_music_volume(...)` çağırıyor.
- src/localization.py: Yeni UI metinleri için tüm dillere key eklenmeli; aksi halde `test_localization_no_missing_keys_any_language.py` kırılır.

**Key Functions/Classes:**
- `MysteryCardUI.draw_selection_overlay()` ve `handle_mouse_click()` (src/game_modes_extra.py)
- `MysteryMode.handle_input()` ve `MysteryCardManager.prepare_selection()` (src/game_modes_extra.py)
- `CampaignMode.handle_input()`, `_handle_level_failed()`, `_handle_level_complete()`, `draw_mode_overlay()` (src/campaign/campaign_mode.py)
- `CampaignUIEffects.draw_level_failed_overlay()` / `draw_level_complete_overlay()` (src/campaign/campaign_ui.py)
- `Game._draw_game_over_overlay()` ve `Game.handle_input()` game-over click targets (src/game.py)
- `SoundManager.set_music_volume()` / `_compute_volume()` (src/sound.py)
- `TabbedSettingsScreen.handle_input()` slider drag (src/settings_screen_tabbed.py)

**Patterns & Conventions:**
- Overlay panelleri için `retro_style.draw_glass_panel(...)` ve buton için `retro_style.draw_uniform_button(...)` yaygın.
- UI ölçekleme: `Game` içinde `_ui_scale()` / `_sx()`; kampanya overlay’leri çoğunlukla ham pixel kullanıyor.
- Ayar action’ları string olarak dönüyor; `main.py` bu action’ları uygular.

## Implementation Phases

### Phase 1: Kart Ustalığı kart seçim ekranına Reroll butonu

**Objective:** Kart seçim overlay’inde, “Kart almadan devam et” butonunun yanında “Reroll / Yeniden Çek” butonu görünsün ve tıklayınca kart havuzu yeniden çekilsin (overlay kapanmadan).

**Files to Modify/Create:**
- src/game_modes_extra.py
- src/localization.py

**Steps (TDD):**
1. Test (hafif/unit): `MysteryCardUI.handle_mouse_click()` için yeni bir tıklama hedefi eklenince `'REROLL'` döndürdüğünü doğrulayan test tasarla (pygame stub’ı ile). Alternatif: en azından yeni localization key’lerinin tüm dillerde varlığını doğrulayan test ekle (repo zaten bunu yapıyor).
2. `MysteryCardUI` içinde `reroll_button_rect` state’i ekle (skip butonu paterniyle aynı).
3. `draw_selection_overlay()` içinde `skip_button_rect` yanına/sağına butonu çiz (stil: mevcut buton çizimi veya `retro_style.draw_uniform_button`).
4. `handle_mouse_click()` içinde `reroll_button_rect` hit-test yapıp `'REROLL'` döndür.
5. `MysteryMode.handle_input()` içinde `choice == 'REROLL'` dalı ekle:
   - `card_manager.prepare_selection()` ile yeni kartlar üret
   - `card_ui.reset()` ve/veya widget listesini yeniden kur (mevcut reset akışı bozulmadan)
   - overlay kapanmasın (`_close_card_selection()` çağrılmasın)
6. Localization: tüm dillere yeni key ekle (öneri: `card_reroll_selection`).

**Acceptance Criteria:**
- [ ] Kart seçim ekranında “Kart almadan devam et” yanında bir “Reroll/Yeniden Çek” butonu görünür.
- [ ] Butona basınca seçimdeki 3 kart anında değişir; ekran kapanmaz.
- [ ] `pytest` lokalizasyon testleri dahil geçer.

---

### Phase 2: Görev modunda başarısız/tamamlandı overlay’lerinde “Tekrar Dene” seçeneği

**Objective:** Kampanya/görev modunda oyuncu ana menüye dönmeden, hem başarısız overlay’inde hem tamamlandı overlay’inde “Tekrar Dene” seçeneğini görüp kullanabilsin.

**Files to Modify/Create:**
- src/campaign/campaign_ui.py
- src/campaign/campaign_mode.py
- src/localization.py

**Implementation Notes:**
- Mevcut durumda başarısız overlay’i sadece hint metni gösteriyor (klavye ile R/F). Tamamlandı overlay’inde R zaten var ama UI butonu yok.
- İstenen “seçenek” için en düşük riskli yol: overlay’in altına 1–2 adet `draw_uniform_button` (Tekrar Dene / Ana Menü veya Tekrar Dene / Devam) eklemek ve click rect’lerini `CampaignUIEffects` üzerinde saklamak.

**Steps (TDD):**
1. Test: `CampaignMode` overlay aktifken MOUSEBUTTONDOWN ile “Tekrar Dene” rect’ine tıklanınca `restart()` veya `quick_restart()` çağrıldığını doğrulayan bir test yaz (Sound/pygame stub ile).
2. `CampaignUIEffects.draw_level_failed_overlay()` içine buton çizimi ekle:
   - “Tekrar Dene” butonu (alt kısım)
   - (opsiyonel ama pratik) “Ana Menü” butonu
   - Rect’leri `self._level_failed_click_targets` benzeri alana yaz.
3. `CampaignUIEffects.draw_level_complete_overlay()` içine benzer “Tekrar Dene” butonu ekle (mevcut “ENTER/next level” akışı bozulmadan).
4. `CampaignMode.handle_input()` içinde `self.level_failed` ve `self.level_complete` bloklarına MOUSEBUTTONDOWN handler ekle:
   - `campaign_ui_effects` üzerinde son çizimdeki click targets’ı kontrol et
   - “Tekrar Dene” → `self.restart()` (veya tercih edilirse `self.quick_restart()`)
   - “Ana Menü” → `'main_menu'` veya mevcut akışa uygun return
5. Localization: buton label’ları için key ekle (öneri: `retry`, `continue`, `main_menu`). Repo içinde bazıları zaten olabilir; varsa reuse et.

**Acceptance Criteria:**
- [ ] Görev modunda başarısız overlay’inde “Tekrar Dene” seçeneği görünür ve çalışır.
- [ ] Görev modunda tamamlandı overlay’inde “Tekrar Dene” seçeneği görünür ve çalışır.
- [ ] Retry, menüye dönmeden aynı level’i yeniden başlatır.

---

### Phase 3: Görev modunda ESC menüsünde “Tekrar Dene” seçeneği

**Objective:** Görev modunda ESC pause menüsünde “Tekrar Dene” (restart) seçeneği net şekilde bulunsun.

**Files to Modify/Create:**
- src/game.py
- src/campaign/campaign_mode.py (gerekirse override)
- src/localization.py (gerekirse)

**Implementation Options:**
- **Option A (en az değişiklik):** Var olan pause menüsündeki “Yeniden Başlat” seçeneğini kampanya modunda “Tekrar Dene” label’ı ile göster (aksiyon aynı kalsın: `restart`).
- **Option B:** Pause menüye yeni bir satır ekleme (riskli: düzen/test etkisi), tavsiye edilmez.

**Steps (TDD):**
1. Test: Kampanya modunda pause menü açıldığında restart satırının label’ı beklenen localization key’i ile çiziliyor mu (görsel test zor). Daha uygulanabilir: `pause_menu_options` listesinin kampanyada farklılaştığını unit-test ile doğrula.
2. `CampaignMode` içinde `pause_menu_options`’ı override et veya `Game`’de “restart label”’ı bir method/prop ile özelleştir.
3. Aksiyon tarafını değiştirme: `Game._handle_pause_menu_input()` zaten `'restart'` döndürüyor; kampanya `restart()` override’ı level state’i sıfırlamalı.

**Acceptance Criteria:**
- [ ] Görev modunda ESC pause menüsünde “Tekrar Dene” seçeneği görünür.
- [ ] Seçildiğinde ana menüye dönmeden level yeniden başlar.

---

### Phase 4: Başarısız ekranını “Oyun Bitti” çizimi ile aynı hale getirme (kırmızı varyant)

**Objective:** Kampanya “başarısız” ekranı, bloklar üst üste binince gelen “Oyun Bitti” ekranı ile aynı layout/çizimi kullansın; sadece tema kırmızı olsun.

**Files to Modify/Create:**
- src/game.py
- src/campaign/campaign_mode.py
- (muhtemel) src/retro_style.py (küçük helper çıkarımı)

**Recommended Approach (pragmatik + paylaşım):**
- `Game._draw_game_over_overlay(skin)` fonksiyonunu **tema ve başlık override** alacak şekilde genişlet:
  - `theme`/palette (mavi oyun bitti, kırmızı başarısız)
  - `title_text` (“OYUN BİTTİ” vs “BAŞARISIZ”)
  - (gerekirse) bazı bölümleri kapatmak için flag’ler (stars/record/confetti)
- Kampanya başarısız overlay’i çizilirken bu fonksiyon **kırmızı tema** ile çağrılır.

**Implementation Details:**
- `_draw_game_over_overlay` şu an `skin` parametresini kullanmıyor; bu parametre tema geçişi için güvenli bir hook.
- Click target mekanizması `_game_over_click_targets` üzerinden zaten var; kampanya `handle_input` içinde `self.level_failed` durumunda aynı target’ları kontrol edebilir.

**Steps (TDD):**
1. Test: `_draw_game_over_overlay` tema parametresi verildiğinde border/gradient renkleri farklı set ediliyor mu (unit test zor). Daha uygulanabilir: tema seçimi için küçük, pure bir yardımcı fonksiyon (`get_end_overlay_theme(kind)`) yaz ve onu test et.
2. `_draw_game_over_overlay` içindeki hard-coded renkleri tema objesinden oku.
3. Kampanya başarısız çizim yolunu değiştir:
   - `CampaignMode._draw_level_failed_overlay()` içinde `campaign_ui_effects.draw_level_failed_overlay` yerine `_draw_game_over_overlay(..., theme=RED_FAIL, title=t('campaign_failed_title'))` çağır.
4. Input: kampanya başarısız ekranında click ile “Tekrar Dene / Menü” çalışmalı (Phase 2 ile birlikte uyumlu).

**Acceptance Criteria:**
- [ ] Kampanya başarısız ekranı, “Oyun Bitti” ekranıyla aynı layout/çizimi kullanır.
- [ ] Başarısız paneli kırmızı tema ile görünür.

---

### Phase 5: ESC ile pause açılınca müzik ducking

**Objective:** Oyun içindeyken ESC ile pause menüsü açıldığında arka plan müziği daha düşük seviyeye düşsün; pause kapatılınca eski seviyeye dönsün.

**Files to Modify/Create:**
- src/sound.py
- src/game.py
- src/pvp_game.py

**Steps (TDD):**
1. Test: `SoundManager` için `duck_music()` / `unduck_music()` eklenince `_compute_volume()` çıktısının duck factor ile çarpıldığını doğrula (pygame mixer stub).
2. `SoundManager` içine duck state ekle (örn. `_music_duck_factor: float = 1.0`).
3. `set_music_volume()` ve `_compute_volume()` yollarının her ikisinde de duck factor’ün uygulandığından emin ol (pygame.mixer.music ve channel-based track yolları).
4. `Game.handle_input()` içinde pause açılan/kapanan tüm geçiş noktalarına duck/unduck ekle:
   - ESC ile pause açma
   - P ile toggle
   - pause menüden resume
   - pause menüden restart
5. `pvp_game.py` içinde aynı pause/resume noktalarına duck/unduck ekle.

**Acceptance Criteria:**
- [ ] Pause menüsü açıkken müzik seviyesi belirgin şekilde azalır.
- [ ] Oyuna dönünce müzik eski seviyesine döner.

---

### Phase 6: Ayarlarda “Ana Menü Müziği” slider’ı mouse sürüklemede anlık çalışsın

**Objective:** Ayarlar ekranında “Ana Menü Müziği” ses barı mouse ile sürüklenirken `menu_sound` volümü anında güncellensin.

**Files to Modify/Create:**
- src/settings_screen_tabbed.py
- (gerekirse) test: test_settings_menu_music_volume_slider_drag_live.py (veya mevcut test dosyasına ek)

**Root Cause (bulundu):**
- `TabbedSettingsScreen.handle_input()` içinde MOUSEMOTION drag path’inde `_set_slider_from_x(...)` dönüş değeri discard ediliyor; bu yüzden `main.py` action’ı alamıyor.

**Steps (TDD):**
1. Test: Drag aktifken ( `_slider_drag_active=True` ) MOUSEMOTION event’i `handle_input()`’a verildiğinde `change_menu_music_volume` action’ı döndürdüğünü doğrula.
2. Kod: MOUSEMOTION drag path’ini `return self._set_slider_from_x(...)` olacak şekilde düzelt.
3. Regression: Diğer slider’ların (music/sfx) drag ile action üretmeye devam ettiğini doğrula.

**Acceptance Criteria:**
- [ ] “Ana Menü Müziği” slider’ı sürüklenirken ana menü müziği anında kısılıp açılır.
- [ ] `pytest` geçer.

## Open Questions

1. “Tekrar Dene” kampanyada `restart()` mi yoksa `quick_restart()` mi olmalı?
   - **Option A:** `restart()` (yeni seed) — daha “yeni deneme” hissi.
   - **Option B:** `quick_restart()` (aynı seed) — adil/tekrarlanabilir.
   - **Recommendation:** Varsayılan `restart()`; ayrıca klavye kısayolları (R/F) korunabilir.

2. Kampanya başarısız ekranında “Oyun Bitti” overlay’inin stars/record gibi bölümleri gösterilsin mi?
   - **Option A:** Aynen kalsın (tam aynı ekran) — istekle en uyumlu.
   - **Option B:** Kampanyaya uygun bölümler kapatılsın (sade) — daha temiz ama “aynı ekran” iddiası zayıflar.
   - **Recommendation:** Önce Option A ile hızlı uyum; gerekirse flag ile Option B.

## Risks & Mitigation

- **Risk:** `Game._draw_game_over_overlay` çok büyük; tema parametreleştirme hata riski.
  - **Mitigation:** Sadece renk/palette bloklarını soyutla; layout ve zaman çizelgesine dokunma. Kapsamlı manuel test.
- **Risk:** Kampanya overlay input’u ile `Game.handle_input` çakışması.
  - **Mitigation:** Kampanya overlay aktifken click target kontrolünü `CampaignMode.handle_input` içinde açıkça yap; `self.game_over` flag’ini kampanya için set etmeyip sadece overlay çizimini reuse et.

## Success Criteria

- [ ] Kart Ustalığı kart seçiminde reroll butonu mevcut.
- [ ] Görev modunda başarısız/tamamlandı/ESC menülerinde “Tekrar Dene” seçeneği var ve menüye dönmeden çalışıyor.
- [ ] Kampanya başarısız ekranı “Oyun Bitti” overlay çizimi ile aynı, kırmızı temalı.
- [ ] Pause açıkken müzik duck olur, kapanınca geri gelir.
- [ ] “Ana Menü Müziği” slider’ı anlık çalışır.
- [ ] Tüm testler geçer.

## Notes for Atlas

- Bu plan uygulanırken **tüm kodları Sisyphus yazsın** (özel not).
- Lokalizasyon eklerken tüm diller için anahtar eklenmeli; aksi halde localization testleri kırılır.
