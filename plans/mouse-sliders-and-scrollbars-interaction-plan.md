# Plan: Ayarlar Slider’ları ve Scrollbar’ları Mouse ile Etkileşimli Yapma

**Created:** 26 Şubat 2026  
**Status:** Ready for Atlas Execution

## Summary

Bu çalışma; (1) Ayarlar ekranındaki yüzde/slider bar’larının mouse ile tıklanıp sürüklenerek değiştirilebilmesini, (2) “< >” ile değişen selector/slider ayarlarında mouse tıklamasının sadece tek yöne değil iki yöne de çalışmasını, (3) Ayarlar ve ana menü dil panelindeki scrollbar’ların panelin biraz sağına/dışına taşınmasını ve mouse ile sürüklenebilir olmasını sağlar.

## Context & Analysis

**Relevant Files:**
- `src/settings_screen_tabbed.py`: Ayarlar listesi çizimi + input. Slider çizimi `_draw_inline_slider`, mouse click şu an her satır için `_handle_setting_action(K_RETURN)` çağırıyor.
- `src/menu.py`: Ana menü dil paneli `_draw_menu_language_panel` ve `_handle_menu_language_panel_input`.
- `src/retro_style.py`: `RetroStyle.draw_scrollbar(...)` yalnızca çizer, `thumb_rect` döndürür.
- (Opsiyonel) `src/ui_components.py`: `Slider` sınıfı var ama şu an kullanılmıyor; bu iş için entegre etmek görsel/akış riskini artırır.

**Key Findings (root causes):**
- `settings_screen_tabbed.py` içinde mouse satır tıklaması her zaman `K_RETURN` gönderiyor; bu da `selector` tipinde daima ileri (sağ) yönde cycle demek. Bu yüzden “tek tarafa hareket” hissi oluşuyor.
- Slider bar’lar çiziliyor ama mouse drag/click ile değer set edilmiyor.
- `retro_style.draw_scrollbar` `container_rect.right - bar_width - 4` ile kendi track konumunu hesaplıyor. Caller tarafında `container_rect.width` çok küçük verilmiş (örn. menu dil panelinde 4px), bu da track’in panel içine gömülmesine yol açıyor.
- Menu dil panelinde `MOUSEWHEEL` sonrası yalnız alt sınır clamp var; üst sınır clamp eksik.
- Menu dil paneli `max_scroll` hesapları her öğe sonrası `gap` eklediği için 1 gap kadar fazla çıkıyor.
- Scrollbar’lar dekoratif: thumb rect döndürülüyor ama event’lerde drag mantığı yok.

**Conventions/Patterns:**
- Scroll state: `scroll_offset` / `menu_language_panel_scroll` px-tabanlı int.
- Scrollbar render: `retro_style.draw_scrollbar(...)`.
- Ayarlar satır yüksekliği: `row_h = 58`.

## Implementation Phases

### Phase 1: Settings slider’larını mouse ile ayarlama (click + drag)

**Objective:** Ayarlardaki tüm `type='slider'` item’lar mouse ile tıklanıp sürüklenerek değişebilsin.

**Files to Modify:**
- `src/settings_screen_tabbed.py`

**Steps:**
1. `SettingsScreenTabbed.__init__` içinde slider drag state ekle:
   - `self._slider_drag_active: bool`
   - `self._slider_drag_key: str | None`
   - `self._slider_drag_item: dict | None`
   - `self._slider_drag_row_rect: pygame.Rect | None` (veya option index)
   - `self._slider_drag_bar_rect: pygame.Rect | None`
2. Slider geometry’yi tek yerden hesaplamak için küçük helper ekle (aynı layout’ı draw + input paylaşsın):
   - Örn: `_slider_layout(rect, item) -> dict` döndürsün:
     - `bar_rect`, `left_arrow_rect`, `right_arrow_rect`, `value_rect` (gerekirse)
   - Mevcut `_draw_inline_slider` içindeki `bar_left/bar_right` hesapları ve font ölçümleri bu helper’a taşınsın.
3. Değer setleme için helper ekle:
   - `_set_slider_from_mouse_x(item, x, bar_rect)`:
     - $ratio = clamp((x - bar\_rect.x)/bar\_rect.w)$
     - `value = min + ratio*(max-min)`
     - `step` ile snap: `round(value/step)*step` (float step’lerde hata için küçük epsilon kullan)
     - `min/max` clamp
     - `percent` slider’larda mevcut davranışla uyumlu rounding (`round(...,2)` veya `int`)
     - `_set_value(key, value)` + gerekiyorsa `settings_manager.save()` çağrı politikası mevcut pattern’e göre korunmalı.
4. `handle_input` içinde `MOUSEBUTTONDOWN button=1` sırasında:
   - Satır tıklaması tespit edildiğinde, item `type == 'slider'` ise:
     - `layout = _slider_layout(row_rect, item)`
     - Eğer `pos` `bar_rect` içindeyse: `_set_slider_from_mouse_x(...)` + `self._slider_drag_active=True` (drag başlat)
     - Eğer `pos` `left_arrow_rect` içindeyse: `_handle_setting_action(pygame.K_LEFT)`
     - Eğer `pos` `right_arrow_rect` içindeyse: `_handle_setting_action(pygame.K_RIGHT)`
     - Aksi halde: mevcut davranış (sadece select) kalsın.
5. `MOUSEMOTION` sırasında:
   - Eğer `self._slider_drag_active` ise hover ile `selected` güncellemesini SKIP et.
   - `pos.x`’e göre `_set_slider_from_mouse_x(...)` çağır.
6. `MOUSEBUTTONUP button=1` ile drag’i kapat.

**Acceptance Criteria:**
- [ ] Ayarlardaki slider’lar (örn. `music_volume`, `sfx_volume`, `bg_transparency`, `das_delay` vb.) bar üzerinde sürüklenince anlık değişir.
- [ ] Slider bar’a tek tık değeri o noktaya taşır.
- [ ] Drag sırasında satır hover seçimi “zıplamaz”.

---

### Phase 2: Settings “< >” selector ayarlarında mouse ile iki yön (sol/sağ) desteği

**Objective:** Mouse tıklaması `selector` tipinde sadece ileri (sağ) değil; sol ok bölgesinde geri, sağ ok bölgesinde ileri çalışsın.

**Files to Modify:**
- `src/settings_screen_tabbed.py`

**Steps:**
1. `selector` çizimindeki arrow merkezleri `_draw_selector_value` içinde hesaplanıyor.
   - Normal selector path’i için `_draw_selector_value` dönüşünü genişlet:
     - `return {'left_rect': ..., 'right_rect': ..., 'value_rect': ...}` gibi.
   - Bu rect’ler `handle_input`’te kullanılacak.
2. `draw()` sırasında zaten `self._keybind_slot_rects` gibi bir liste tutuluyor. Benzer şekilde:
   - `self._selector_click_rects` (option index -> rect dict) gibi bir state oluştur.
   - `_draw_setting_item` → `_draw_selector_value` dönüşünü yakalayıp `self._selector_click_rects[i] = returned_dict` şeklinde sakla.
3. `handle_input` içinde satır tıklaması selector ise:
   - `rects = self._selector_click_rects[i]` al.
   - `pos` `left_rect` içindeyse `_handle_setting_action(pygame.K_LEFT)`
   - `pos` `right_rect` içindeyse `_handle_setting_action(pygame.K_RIGHT)`
   - `pos` value alanındaysa: mevcut davranış (ister K_RIGHT cycle, ister music_selector için picker açma) — aşağıdaki Phase 2.1’e bak.
4. `music_selector` için mouse mapping:
   - Sol/sağ ok: `K_LEFT/K_RIGHT` ile cycle
   - Value alanına click: `K_RETURN` ile picker açma (`_open_music_picker`)

**Acceptance Criteria:**
- [ ] `selector` tipinde mouse ile sol oka tıklayınca değer geri gider, sağ oka tıklayınca ileri gider.
- [ ] Önceden var olan klavye davranışı değişmez.

---

### Phase 3: Settings scrollbar’ı panelin dışına taşıma + mouse drag

**Objective:** Ayarlar listesindeki scrollbar (sağdaki) panelin biraz daha sağına/dışına alınsın ve thumb sürüklenerek scroll edilebilsin.

**Files to Modify:**
- `src/settings_screen_tabbed.py`

**Steps:**
1. Scrollbar container rect’i `content_rect.right - ...` yerine `panel.right + OFFSET` bazlı hesapla.
   - `retro_style.draw_scrollbar` track’i `container_rect.right - bar_width - 4` ile çizdiği için, istediğimiz track_x = `panel.right + OFFSET` olacak şekilde `container_rect.width = bar_width + 4` ver:
     - Örn: `bar_width = 8`, `container_w = 12`.
     - `sb_container_rect = pygame.Rect(panel.right + OFFSET, content_rect.y, container_w, content_rect.height)`
2. `draw()` sonunda `thumb_rect = retro_style.draw_scrollbar(...)` dönüşünü sakla:
   - `self._settings_sb_container_rect`
   - `self._settings_sb_thumb_rect`
   - `self._settings_sb_drag_active`, `self._settings_sb_drag_offset_y`
3. `handle_input`:
   - `MOUSEBUTTONDOWN`: pos thumb_rect içindeyse drag başlat, `drag_offset_y = pos.y - thumb_rect.y`
   - `MOUSEMOTION`: drag aktifse
     - track_y = container.top + 4
     - track_h = container.height - 8
     - thumb_h = thumb_rect.height
     - max_scroll = `_max_scroll(content_rect)`
     - yeni_thumb_y = clamp(pos.y - drag_offset_y, track_y, track_y + track_h - thumb_h)
     - ratio = (y - track_y) / max(1, (track_h - thumb_h))
     - `scroll_offset = int(ratio * max_scroll)`
   - `MOUSEBUTTONUP`: drag kapat.
4. Drag sırasında normal hover seçimi ve satır click işleme öncelik sırası:
   - Önce scrollbar drag start kontrolü
   - Sonra slider/selector click
   - En son default row select

**Acceptance Criteria:**
- [ ] Ayarlar scrollbar’ı panelin sağında (dışarıda) görünür.
- [ ] Thumb sürüklenince liste scroll olur.
- [ ] Mousewheel davranışı bozulmaz.

---

### Phase 4: Ana menü dil paneli scrollbar’ı dışarı taşıma + mouse drag + clamp düzeltmeleri

**Objective:** Dil panelindeki scrollbar panelin dışına taşsın, mouse ile sürüklenebilsin; wheel clamp ve max_scroll doğru olsun.

**Files to Modify:**
- `src/menu.py`

**Steps:**
1. `_menu_language_panel_max_scroll`’da total height hesabını düzelt:
   - `total_h = n*(item_h+gap) - gap` (n>0 ise), böylece son gap fazlalığı kalkar.
2. `_handle_menu_language_panel_input` içinde `MOUSEWHEEL` sonrası hem alt hem üst clamp uygula:
   - `self.menu_language_panel_scroll = clamp(0, ..., max_scroll)`
3. `_draw_menu_language_panel` içinde scrollbar’ı dışarı taşı:
   - `bar_width = 8`, `container_w = bar_width + 4`
   - `OFFSET = 6..12` aralığında seç
   - `sb_container_rect = pygame.Rect(panel_rect.right + OFFSET, list_rect.y, container_w, list_rect.height)`
   - `self.menu_language_panel_thumb_rect = retro_style.draw_scrollbar(..., container_rect=sb_container_rect, bar_width=bar_width, ...)`
   - Ayrıca `self.menu_language_panel_sb_container_rect = sb_container_rect` sakla.
4. Drag state ekle:
   - `self.menu_language_panel_sb_drag_active`, `self.menu_language_panel_sb_drag_offset_y`
5. `_handle_menu_language_panel_input`:
   - `MOUSEBUTTONDOWN`: eğer pos thumb_rect içinde ise drag başlat ve return (paneli kapatma logic’ine düşmesin)
   - `MOUSEMOTION`: drag aktifse `menu_language_panel_scroll` ratio ile güncelle ve return
   - `MOUSEBUTTONUP`: drag kapat
6. Panel dışı tıklama ile kapanma kontrolünü scrollbar alanını kapsayacak şekilde genişlet:
   - “inside” = panel_rect OR sb_container_rect (veya sb_container_rect.inflate) içinde mi?
   - inside değilse paneli kapat.

**Acceptance Criteria:**
- [ ] Dil panel scrollbar’ı panelin dışında (sağında) görünür.
- [ ] Scrollbar sürüklenince listede kaydırma çalışır.
- [ ] Scroll değerleri her zaman `[0, max_scroll]` aralığında kalır.
- [ ] Scrollbar alanına tıklamak paneli kapatmaz.

---

## Tests

Bu değişiklikler ağırlıklı olarak Pygame input/rect etkileşimi olduğu için tam entegrasyon testi pahalı olabilir. Yine de en azından “saf” hesap fonksiyonlarına unit test eklemek önerilir.

**Önerilen yeni test dosyası:** `test_ui_mouse_interactions.py`
- Slider mapping helper testi:
  - Verilen `bar_rect` ve `(min,max,step)` için x→value snap/clamp doğrulansın.
- Scrollbar drag mapping helper testi (opsiyonel):
  - track/thumb parametreleriyle mouse_y→scroll_offset clamp doğrulansın.

Eğer helper’lar sınıf içine gömülecekse, testler doğrudan bu helper fonksiyonlarını çağırmalı (event loop’a girmeden).

## Open Questions

1. Scrollbar dışa taşıma offset’i kaç px olmalı?
   - **Option A:** `OFFSET=6` (minimal)
   - **Option B:** `OFFSET=12` (daha belirgin, daha kolay tıklanır)
   - **Recommendation:** `OFFSET=8..10` aralığı.

2. Slider’da click bar dışında ama satır içinde olunca ne olsun?
   - **Option A:** Sadece seçsin, değer değiştirmesin.
   - **Option B:** Satırın sağ yarısı = artır, sol yarısı = azalt.
   - **Recommendation:** A (yanlışlıkla değer değişimini azaltır).

## Risks & Mitigation

- **Risk:** Drag sırasında mevcut `MOUSEMOTION` hover selection logic’i `selected`’ı sürekli değiştirip drag’i bozabilir.
  - **Mitigation:** Drag aktifken hover update ve satır click aksiyonlarını kısa devre et.

- **Risk:** `draw_scrollbar`’ın `container_rect` geometri kuralı (right-bar_width-4) yanlış anlaşılırsa track konumu kayabilir.
  - **Mitigation:** Container genişliğini `bar_width+4` yapıp `x=istenen_track_x` kuralını sabitle.

- **Risk:** Menu dil paneli dışa taşan scrollbar tıklanınca panel kapanabilir.
  - **Mitigation:** “panel dışı click → close” kontrolüne scrollbar container’ını dahil et.

## Success Criteria

- [ ] Ayarlar ekranındaki tüm slider’lar mouse ile sürüklenerek değişir.
- [ ] Ayarlar ekranındaki selector’larda mouse ile sol/sağ yönlü değişim mümkündür (tek yöne kilitli değil).
- [ ] Ayarlar ve ana menü dil panelindeki scrollbar’lar panelin dışında daha sağda konumlanır.
- [ ] Bu scrollbar’lar mouse ile sürüklenebilir ve wheel/clamp mantığı tutarlıdır.

## Notes for Atlas

- `src/ui_components.py` içindeki `Slider` sınıfını bu iş için entegre etmeyin; mevcut `settings_screen_tabbed.py` slider çizimi görsel olarak özelleştirilmiş (renkler + music/sfx smooth animasyon) ve refactor riski var.
- `settings_screen_tabbed.py` içinde mouse click akışı şu an `K_RETURN` ile selector’ları her zaman ileri cycle ediyor; kullanıcı şikayetinin ana sebebi bu.
- `menu.py` dil panelinde `sb_rect.width=4` verildiği için `draw_scrollbar` track’i 16px içeri düşüyor; container rect’i düzeltmeden sadece `x` oynamak yeterli olmayabilir.
