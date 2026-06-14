# UI Scaling Audit Ozet

## Kisa Sonuc

- Asil bug iki parca:
  - scaling zinciri parcali
  - gameplay geometri cap'li
- Retina fix tek basina yetmez.
- Buyuk ekran bug'i tek basina da var.
- `ui_scale_preset` okunurluk artirir. Board + HUD buyutmez.

## Bu Cihazda Dogrulananlar

- Model: MacBook Air M2 (`Mac14,2`)
- Panel native: `2560x1664`
- AppKit logical: `1470x956`
- AppKit backing: `2940x1912`
- `backingScaleFactor`: `2.0`
- `src/platform_utils.py::get_native_resolution()` -> `1470x956`
- Secili testler: `73 passed`

Ana anlam:

- macOS'ta `logical size`, `native panel pixel`, `backing/raw pixel` ayni sey degil.
- Raw surface kullanan helper'lar gerektiginden buyuk uzaya bakiyor.
- Clamp erken vuruyor. Kullanici "olcek degismedi" hissediyor.

## Asil Sorun

### Katman A: Metric secimi karisik

- Bazi ekranlar effective/logical size kullan.
- Bazi ekranlar raw/backing surface kullan.
- Bazi yollar eski `window_width/window_height` veya sabit referans kullan.

Sonuc: Retina destegi var gibi. Ama tum UI'ya yayilmamis.

### Katman B: Gameplay geometri sert sinirli

- Board boyutu font scale'den gelmiyor.
- Board boyutu `get_cell_size()` ve layout helper'lardan geliyor.
- Bu helper'larda hard cap var.

Sonuc: Kullanici UI scale buyutse bile board + HUD ayni kalabiliyor.

### Katman C: Kullanici olcek ayari dar kapsamli

`ui_scale_preset` su yollari etkiliyor:

- `apply_ui_scale_preset(...)`
- `get_effective_scale(...)`

Ama su kritik yollari etkilemiyor:

- `src/game.py::get_cell_size()`
- `src/game.py::_draw_right_hud_panel(...)`
- `src/coop_game.py::_calculate_layout()`
- `src/menu.py::_fullscreen_panel_scale()`
- `src/menu.py::_menu_panel_content_scale()`
- `src/main.py::_fullscreen_popup_scale()`

## Buyuk Ekranda Neden Kucuk Kaliyor?

### Single player

`src/game.py` kok nokta:

- `get_cell_size()` -> `min(cell_width, cell_height, 40)`
- `get_board_offset()` -> eski `SIDE_PANEL_WIDTH` varsayimi ile ortalama
- `_draw_right_hud_panel(...)` -> `panel_width = min(220, max(120, available_right))`
- HUD scale -> `max(0.72, min(1.05, panel_width / 220.0))`

Net sonuc:

- Classic `10x20` board en fazla `400x800 px`
- Sag HUD panel en fazla `220 px`
- `2560x1440`, `2560x1600`, `2880x1800` gibi ekranlarda fazla alan bos margin olur

### Co-op

`src/coop_game.py` kok nokta:

- `_ui_scale()` hala raw `1366x768` oranli
- `_calculate_layout()` -> `side_panel = 120`
- `_calculate_layout()` -> `cs = int(min(40, cell_by_h, cell_by_w))`

Net sonuc:

- Co-op board da erken tavana vurur
- Yan paneller buyuk ekranda yeterince buyumez

## Retina'da Neden "Bazi Yerler Degisiyor, Bazi Yerler Degismiyor"?

Effective-size kullanan ekranlar:

- `src/menu.py::_ui_scale()`
- `src/game.py::_ui_scale()`
- `src/graphics_menu.py::_ui_scale()`
- `src/guide_screen.py::_ui_scale()`
- `src/settings_screen_tabbed.py::_ui_scale()`
- `src/extras_menu.py::_extras_ui_scale()`

Raw kalan kritik yollar:

- `src/menu.py::_fullscreen_panel_scale()`
- `src/menu.py::_menu_panel_content_scale()`
- `src/main.py::_fullscreen_popup_scale()`
- `src/game.py::_overlay_ui_scale()`
- `src/campaign/level_select.py::_get_ui_scale()`
- `src/coop_game.py::_ui_scale()`

Net sonuc:

- Text/padding/layout'in bir kismi logical size ile tepki verir
- Popup/content/overlay/gameplay'in bir kismi raw/backing size ile clamp olur

## Tam Ekran Modu Kok Neden mi?

Hayir.

- Uygulama fiilen always borderless fullscreen gibi calisiyor.
- Gercek exclusive / borderless / windowed secimi kullaniciya acik degil.
- Bu bug mode secimi degil, metric secimi + layout policy bug'i.

## Once Nereler Oynanmali?

### 1. `src/game.py`

Once burasi.

Degisecek fonksiyonlar:

- `update_fonts()`
  - raw canvas yerine effective UI metric kullan
- `get_cell_size()`
  - `40` hard cap kaldir ya da profile yap
- `get_board_offset()`
  - board + HUD beraber yeniden hesapla
- `_draw_right_hud_panel(...)`
  - `220` max panel width kaldir/profile yap
- `_overlay_ui_scale(...)`
  - overlay rect + font + hitbox zinciri ile beraber ele al

Dogru yon:

- yeni helper yaz: `_compute_gameplay_layout_metrics()`
- donsun:
  - `cell_size`
  - `board_rect`
  - `hud_panel_rect`
  - `usable_play_band`
  - `hud_scale` veya `occupancy_profile`

Sonra su fonksiyonlar bu helper'dan beslensin:

- `get_cell_size()`
- `get_board_offset()`
- `_draw_right_hud_panel(...)`

### 2. `src/coop_game.py`

Ikinci oncelik.

Degisecek fonksiyonlar:

- `_ui_scale()`
- `_calculate_layout()`
- `_draw_hud(...)`
- `_draw_side_panels(...)`

Burada da tek tek sayi buyutme degil, ortak occupancy policy lazim.

### 3. Popup / overlay / menu raw yollar

Ucuncu dalga.

#### `src/main.py`

- `_fullscreen_popup_scale()`
- popup rect + button rect + padding birlikte tasinmali

#### `src/game.py`

- pause menu
- quit confirm
- game over / result overlay

#### `src/menu.py`

- `_fullscreen_panel_scale()`
- `_menu_panel_content_scale()`
- panel geometry + content geometry + hitbox ayni metric'ten uretilmeli

#### `src/campaign/level_select.py`

- `_get_ui_scale()` backlog, ama Retina parity icin gerekli

## Base Gameplay Degisince Audit Gereken Dosyalar

- `src/game_modes.py`
  - `HardcoreMode._draw_right_hud_panel(...)`
- `src/campaign/campaign_mode.py`
  - campaign HUD rect + campaign HUD scale helper'lari
- `src/campaign/coop_campaign_mode.py`
  - `CoopGame` layout degisikligi dogrudan yansir, regression test gerekir
- `src/game_modes_extra.py`
  - `get_cell_size()`
  - `get_board_offset()`
  - ozellikle Mystery mode yine `40` cap kullaniyor

## Kodda Ne Oynanmamali?

- `SIDE_PANEL_WIDTH`, `INFO_PANEL_HEIGHT`, `DEFAULT_WINDOW_WIDTH`, `DEFAULT_WINDOW_HEIGHT` gibi global sabitleri rastgele buyutma
- Sadece `ui_scale_preset` multiplier buyutme
- Ilk adimda `create_display()` veya fullscreen modelini degistirme
- Tek basina `get_effective_ui_size()` helper'ini zorlama

Sebep:

- Bunlar kok nedeni cozmez
- Dusuk cozumunurlukte yeni regressions uretir

## Dogru Uygulama Sirasi

1. Gameplay occupancy policy kilitle
2. `src/game.py` board + right HUD buyut
3. `src/coop_game.py` layout buyut
4. Popup/overlay metrics zinciri kur
5. Menu raw scale migration yap
6. Test + cihaz dogrulama genislet

## Ilk Gorunur Kazanim Nerede?

En hizli user etkisi:

1. single player board + HUD buyutme
2. coop board + side panel buyutme
3. popup/menu Retina parity

Sebep:

- Kullanici once oyun alaninin kucuklugunu gorur
- Sonra popup/menu tarafindaki Retina tutarsizligini fark eder

## Test Tarafi

Mevcut testler helper davranisini koruyor. Ama sunlar eksik:

- single player large display occupancy regression
- coop large display occupancy regression
- current MacBook scaled mode regression (`1470x956 logical`, `2940x1912 backing`)
- popup rect + button hitbox parity regression
- campaign HUD parity regression

Yeni test adaylari:

- `tests/test_gameplay_large_display_occupancy.py`
- `tests/test_coop_large_display_occupancy.py`
- `tests/test_retina_popup_scaling.py`

## Tek Cumlelik Karar

Asil sorun fullscreen secimi degil. Asil sorun: parcali scaling mimarisi + raw/backing metric kullanan UI yollar + gameplay geometri hard cap'leri.
