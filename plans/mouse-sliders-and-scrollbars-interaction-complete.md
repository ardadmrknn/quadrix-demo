# Plan Complete: Mouse Slider & Scrollbar Interaction

Ayarlar ekranındaki slider ve selector bileşenleri artık mouse ile tam etkileşimli. Scrollbar'lar (ayarlar + dil paneli) panel dışına taşındı ve sürüklenebilir yapıldı.

**Phases Completed:** 4 of 4
1. ✅ Phase 1: Slider mouse drag/click
2. ✅ Phase 2: Selector sol/sağ click
3. ✅ Phase 3: Settings scrollbar panel dışına + drag
4. ✅ Phase 4: Dil paneli scrollbar panel dışına + drag

**All Files Created/Modified:**
- src/settings_screen_tabbed.py
- src/menu.py
- test_ui_mouse_slider.py (yeni)

**Key Changes Added:**

*settings_screen_tabbed.py:*
- `_slider_drag_active`, `_slider_drag_item`, `_slider_drag_bar_rect`, `_slider_bar_rects` state'leri
- `_set_slider_from_x(item, x, bar_rect)` helper metodu
- `_draw_inline_slider` slider bar rect'ini her frame cache'liyor
- `MOUSEMOTION` drag sırasında slider değerini günceller, scrollbar drag'ı hesaplar
- `MOUSEBUTTONDOWN` slider bar/ok hit-test; selector için left/right hit-test; scrollbar thumb drag
- `MOUSEBUTTONUP` tüm drag state'leri temizler
- `ESC` handler'ında da drag state temizleme
- `_settings_sb_thumb_rect`, `_settings_sb_container_rect`, `_settings_sb_drag_active` state'leri
- Scrollbar `panel.right + 6` konumunda, `bar_width=10`

*menu.py:*
- `menu_language_panel_sb_*` drag state'leri (4 alan)
- `_open/_close_menu_language_panel` drag state reset
- `_menu_language_panel_max_scroll`: trailing gap fix (`n*(h+gap)-gap`)
- `MOUSEWHEEL`: hem alt hem üst clamp
- `MOUSEMOTION`: scrollbar drag öncelikli, sonra item hover
- `MOUSEBUTTONDOWN`: thumb hit → drag; scrollbar alanına tıklama paneli kapatmaz
- `MOUSEBUTTONUP`: drag temizle
- Scrollbar `panel_rect.right + 6` konumunda, `bar_width=8`

**Test Coverage:**
- Total tests written: 4
- test_ui_mouse_slider.py: `_set_slider_from_x` step snap, clamp, percent/int, sıfır-step testleri
- All tests passing: ✅

**Recommendations for Next Steps:**
- Ayarlardaki diğer scrollbar'lar (müzik picker `_draw_music_picker`) da dışarı taşınabilir; yapı aynı.
- `_set_slider_from_x` içinde min-snap düzeltmesi (`round((raw-min)/step)*step + min`) eklenebilir.
