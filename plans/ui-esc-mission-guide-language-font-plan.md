# Plan: ESC UIX + Görev Modu Panel/Font + Kılavuz + Dil Dropdown Düzeltmeleri

**Created:** 2026-02-26
**Status:** Ready for Atlas Execution

## Summary

Bu çalışma oyun içi ESC (pause + çıkış onayı) ekranlarında eksik hover/etkileşim ("uix") geri bildirimini ana menüdeki ESC onay penceresiyle aynı seviyeye getirir. Görev Modu’nda klavye ile dünya/level gezinirken alttaki bilgi panelinin güncellenmemesi (hover state’in takılı kalması) düzeltilir ve görev modu font ölçeklemesi eski/normal boyutlara çekilir. Kılavuz ekranındaki “Sayfa 1/3” metninin geri butonuyla çakışması kaldırılır ve ana menü dil dropdown’unun ikinci tıklamada kapanmamasına sebep olan event-propagation bug’ı giderilir.

## Context & Analysis

**Relevant Files:**
- src/game.py: Oyun içi pause menüsü (`_draw_pause_menu`, `_handle_pause_menu_input`) ve oyun içi çıkış onayı overlay’i (`_draw_exit_prompt_overlay`, `handle_input` içinde `show_exit_prompt` bloğu).
- src/pvp_game.py: PvP tarafında ayrı pause menüsü çizimi; aynı hover/etkileşim problemi burada da olabilir.
- src/menu.py: Ana menü ESC çıkış onayı paneli (`_draw_exit_prompt_panel`) — referans hover efekti; dil dropdown’un input dispatch’i (`handle_input`, `_handle_menu_language_panel_input`).
- src/campaign/level_select.py: Görev modu ekranı (`CampaignLevelSelect`) — alt panel bilgi seçim mantığı (`_draw_level_info`) ve klavye navigasyonu (`_move_selection`, `_start_world_transition`). Font ölçeklemesi (`_init_fonts`, `_get_ui_scale`).
- src/guide_screen.py: Kılavuz ekranında sayfa göstergesi (`_draw_card_navigation`) ve geri butonu (`_get_back_button_rect`).
- src/ui_theme.py: `UIFonts.SIZE_*` temel font boyutları.

**Key Findings (Root Causes):**
- Görev modu alt paneli `display_level = hovered_level if hovered_level else selected_level` seçiyor; `hovered_level` klavye ile gezince temizlenmediği için panel eski hover edilen level’da kalıyor.
- Ana menü dil dropdown açıkken `handle_input` önce `_handle_menu_language_panel_input` çalıştırıyor; paneli kapatan aynı tıklama daha sonra ana menü handler’ına düşüp dropdown’u tekrar açabiliyor (kapanmıyor gibi görünüyor).
- Oyun içi çıkış onayı overlay’i (`show_exit_prompt`) `MOUSEMOTION`’ı tamamen yutuyor; buton hover’u ancak çizimde hesaplanırsa görünür. Şu an butonlar `draw_uniform_button(... selected=False)` ile çizildiği için hover/etkileşim yok.
- Oyun içi pause menüsü `draw_uniform_button` çağrısında `state='hover'` iletmiyor ve/veya hover çizimde hesaplanmıyor; bu yüzden ana menüdeki onay penceresi kadar “buton etkileşimi” hissi vermiyor.

**Patterns & Conventions:**
- Testlerde pygame ve bağımlılıklar sıkça stub’lanıyor (örn. test_settings_fullscreen_restart_confirm.py). UI state/dispatch bug’ları için birim test yazmak mümkün.

## Implementation Phases

### Phase 1: Görev Modu Panelinin Klavye ile Güncellenmesi

**Objective:** Klavye ile dünya/level seçiminde alt panel (görev/yıldız koşulları) anında seçili level’a göre güncellensin; hover state takılı kalmasın.

**Files to Modify/Create:**
- src/campaign/level_select.py
- (Yeni) test_campaign_level_select_panel_keyboard_nav.py

**Steps (TDD):**
1. Yeni test yaz: `CampaignLevelSelect` instance’ı oluştur (gerekirse `__new__` + alanları manuel set) ve `hovered_level` doluyken `_move_selection()` çağrısının `hovered_level`’ı `None` yaptığını doğrula.
2. Testi çalıştır (fail beklenir).
3. src/campaign/level_select.py içinde:
   - `_move_selection(delta)` sonunda `self.hovered_level = None` ekle.
   - `_start_world_transition(target_world)` içinde dünya değişince `self.hovered_level = None` ekle (veya `_update_selection_for_world()` içinde).
   - Klavye ile direkt dünya değişiminde de (1-5) aynı garanti sağlansın.
4. Testi çalıştır (pass).

**Acceptance Criteria:**
- [ ] Klavye ile level değişince `_draw_level_info()` panel içeriği seçili level’a göre değişir.
- [ ] Mouse hareket etmeden panel “eski hover” seviyesinde kalmaz.

---

### Phase 2: Görev Modu Font Boyutlarını Normalleştirme

**Objective:** Görev Modu ekranındaki metin puntoları eski/normal boyutlara dönsün (özellikle 1080p ve üstünde aşırı büyüme olmasın).

**Files to Modify/Create:**
- src/campaign/level_select.py
- (Opsiyonel) src/ui_theme.py (sadece gerçekten global değerler yanlışsa)
- (Yeni) test_campaign_level_select_font_scale_caps.py

**Steps:**
1. Önce kök nedeni doğrula:
   - `level_select._init_fonts()` içindeki ölçekleme formülü (`min(..., 1.2, w/1400, h/900)`) ve `_get_ui_scale()` ile tutarsızlık var.
   - Global font sabitleri (`UIFonts.SIZE_*`) büyüdüyse, değişikliğin kapsamını değerlendir.
2. Test yaz (stub’lı): `window_width=1920, window_height=1080` iken `_init_fonts()` çağrısında `UIFonts.get()`’e giden size değerlerinin beklenen üst sınırı aşmadığını doğrula (ör. `SIZE_BODY` için 22’ye yakın; hedef: upscaling kapalı ya da daha düşük cap).
3. Uygulama:
   - En düşük riskli çözüm: Görev Modu özelinde `_init_fonts()` ölçeğini `max_scale=1.0` (veya önceki commit’teki değer) ile cap’le.
   - Ayrıca `_init_fonts()` ve `_get_ui_scale()` aynı base çözünürlüğü kullansın (tek kaynak: `_get_ui_scale()`), böylece farklı yerlerde farklı scaling çıkmasın.
4. Testleri çalıştır.

**Acceptance Criteria:**
- [ ] Görev Modu’nda başlık/alt metinler “bariz büyük” görünmez.
- [ ] Değişiklik yalnızca görev modu fontlarını etkiler (global UI bozulmaz).

---

### Phase 3: Oyun İçi Çıkış Onayı (ESC) Buton Etkileşimlerini Ana Menü ile Eşitleme

**Objective:** Oyun içindeki ESC ile açılan çıkış onayı overlay’inde buton hover/etkileşimleri ana menüdeki ESC onay penceresiyle aynı hissi versin.

**Files to Modify/Create:**
- src/game.py
- (Opsiyonel refactor) src/retro_style.py veya src/menu.py (paylaşılan çizim helper’ı)
- (Yeni/opsiyonel) test_game_exit_prompt_hover.py

**Implementation Notes:**
- Referans davranış: src/menu.py `_draw_exit_prompt_panel()` butonları `rect.collidepoint(mouse_pos)` ile her frame hover tespit edip `inflate + glow + border_width` uyguluyor.
- Oyun içi overlay’de `show_exit_prompt` açıkken `MOUSEMOTION` event’i yutuluyor; bu yüzden hover state mutlaka `_draw_exit_prompt_overlay()` içinde mouse pozisyonundan hesaplanmalı.

**Steps:**
1. (Opsiyonel) Test yaz: `_draw_exit_prompt_overlay()` içinde `retro_style.draw_uniform_button` veya yeni helper çağrılarının hover’a göre farklı parametrelerle çalıştığını spy/mock ile doğrula.
2. Uygulama seçenekleri:
   - **Seçenek A (en az değişiklik):** src/game.py `_draw_exit_prompt_overlay()` içinde, src/menu.py’deki hover çizim kodunu (yes/no buton loop’u) birebir uyarlayıp kullan.
   - **Seçenek B (daha temiz):** src/retro_style.py içine `draw_confirm_button(...)` gibi küçük bir helper ekleyip hem src/menu.py hem src/game.py’de aynı helper’ı kullan.
3. Hover tespiti: `mouse_pos = get_mouse_pos()` (menu ile aynı) veya `pygame.mouse.get_pos()`; `yes_rect/no_rect` için hover hesapla.
4. `exit_yes_rect/exit_no_rect` güncel kalmalı; click handling mevcut.

**Acceptance Criteria:**
- [ ] Oyun içi çıkış onayı overlay’inde mouse ile hover görsel geri bildirimi var.
- [ ] Hover efektleri ana menüdeki exit confirm ile tutarlı (inflate/glow/border).

---

### Phase 4: Oyun İçi Pause Menüsü (ESC) Butonlarında “UIX” Hover

**Objective:** Pause menüsündeki seçenekler mouse hover’da net etkileşim/geri bildirim versin; sadece seçili satır değil, hover da çalışsın (event gelmese bile).

**Files to Modify/Create:**
- src/game.py (`_draw_pause_menu`, gerekiyorsa `_handle_pause_menu_input`)
- src/pvp_game.py (benzer pause menüsü varsa)

**Steps:**
1. `_draw_pause_menu()` içinde `mouse_pos` her frame al ve her `button_rect` için `hover = rect.collidepoint(mouse_pos)` hesapla.
2. `retro_style.draw_uniform_button(... state='hover' if hover else 'normal', selected=is_selected)` biçiminde hover state’i ilet.
3. (İsteğe bağlı ama önerilir) “Çift highlight” riskini azaltmak için `pause_menu_nav_source` benzeri basit bir flag ekle:
   - Klavye input’unda `'keyboard'`, mouse motion/click’te `'mouse'`.
   - Çizimde sadece aktif kaynağa göre hover/selected vurgusu yap.
4. Aynı yaklaşımı PvP pause menüsüne uygula.

**Acceptance Criteria:**
- [ ] Pause menüsünde mouse hover ile belirgin vurgulama var.
- [ ] Klavye ile gezinirken seçili satır doğru vurgulanıyor.

---

### Phase 5: Kılavuz Ekranında “Sayfa 1/3” Çakışmasının Kaldırılması

**Objective:** Kılavuz ekranında alttaki sayfa göstergesi geri butonuyla iç içe görünmesin; işe yaramıyorsa kaldır.

**Files to Modify/Create:**
- src/guide_screen.py

**Steps:**
1. `GuideScreen._draw_card_navigation()` şu an sadece sayfa metni çiziyor ve Y konumu geri butonuyla çakışıyor.
2. En basit çözüm (spec’e uygun): sayfa göstergesini tamamen kaldır (fonksiyon no-op veya blit satırını sil).
   - Alternatif: metni daha yukarı taşı (örn. `height - 120`), ama kullanıcı “işe yaramıyorsa kaldır” dediği için kaldırma tercih.

**Acceptance Criteria:**
- [ ] Geri butonu ile çakışan sayfa metni görünmez.

---

### Phase 6: Ana Menü Dil Dropdown’unun İkinci Tıklamada Kapanması

**Objective:** Ana menüde dil seçenekleri kutusu/ikonuna ikinci kez tıklanınca panel kapanabilsin.

**Files to Modify/Create:**
- src/menu.py
- (Yeni) test_menu_language_dropdown_toggle.py

**Root Cause:**
- src/menu.py `handle_input()` içinde panel açıkken önce `_handle_menu_language_panel_input()` çalışıyor; paneli kapatan tıklama daha sonra ana handler’a geçip corner language click logic’iyle paneli tekrar açabiliyor.

**Steps (TDD):**
1. Test yaz (stub’lı):
   - `menu_language_panel_open=True` iken `handle_input(MOUSEBUTTONDOWN, pos=corner_language_rect.center)` çağrısı sonrası `menu_language_panel_open=False` kalmalı.
2. Uygulama:
   - `handle_input()` içinde çağrı öncesi `was_open = self.menu_language_panel_open` al.
   - `_handle_menu_language_panel_input(event)` sonrası:
     - `action is not None` ise dön.
     - Eğer `was_open` True ve artık `menu_language_panel_open` False ise **event’i yutmak için** `return None` yap.
     - Eğer panel hâlâ açıksa zaten `return None`.
3. Testleri çalıştır.

**Acceptance Criteria:**
- [ ] Dil paneli ikinci tıklamada kapanır.
- [ ] Panel kapanırken alttaki menü elemanlarına “tıklama sızması” olmaz.

## Open Questions

1. “Birçok onay kutucuğunda uix yok” kapsamı tam olarak hangi ekranları kapsıyor?
   - **Option A:** Sadece oyun içi ESC (pause + çıkış overlay) ve onların toggle’ları.
   - **Option B:** `retro_style.draw_uniform_button(... checked=...)` kullanan tüm listelerde aynı hover çizim standardı isteniyor.
   - **Recommendation:** Önce ESC kapsamını kesin düzelt (Phase 3-4). Sonra aynı pattern’i `draw_uniform_button` kullanan diğer ekranlara yaymak gerekiyorsa ikinci bir küçük PR.

## Risks & Mitigation

- **Risk:** Hover ve keyboard selection aynı anda iki satırı vurgulayabilir.
  - **Mitigation:** `nav_source` yaklaşımıyla tek vurguyu tercih et (mouse veya keyboard).
- **Risk:** Font ölçeklemesi global sabitlere dokunursa diğer ekranlar küçülebilir.
  - **Mitigation:** İlk etapta sadece `CampaignLevelSelect._init_fonts()` ölçeğini düzelt; `UIFonts.SIZE_*`’e dokunma.
- **Risk:** Dil paneli kapanınca event’i yutmak bazı edge-case’lerde “tıklamadı” hissi verebilir.
  - **Mitigation:** Bu yalnızca panel açıkken ve panel handler’ı event’i kapatmak için kullandığında uygulanmalı.

## Success Criteria

- [ ] Oyun içi ESC çıkış onayı butonları ana menüdeki gibi hover/etkileşim gösterir.
- [ ] Oyun içi pause menüsünde mouse hover geri bildirimi vardır.
- [ ] Görev Modu’nda klavye ile gezinirken alt panel anında güncellenir.
- [ ] Görev Modu fontları “ilk haline” yakın normal boyutlara döner.
- [ ] Kılavuzdaki sayfa göstergesi geri butonuyla çakışmaz (kaldırılır).
- [ ] Ana menü dil dropdown’u ikinci tıklamada kapanır.
- [ ] İlgili testler geçer (`pytest`).

## Notes for Atlas

- UI çizim değişikliklerinde “spec dışı” yeni efekt/animasyon ekleme: sadece istenen hover/etkileşim ve mevcut tasarımın tutarlılığı.
- src/menu.py’de dil paneli için event swallowing fix’i küçük ama kritik; kullanıcı bug’ı bununla birebir örtüşüyor.
- Görev modu fontları için geçmişe dönmek gerekiyorsa `git blame` ile `_init_fonts` scale cap değişimini yakalayıp geri al; global `UIFonts.SIZE_*`’i ancak diğer ekranlar da bozulduysa değerlendir.
