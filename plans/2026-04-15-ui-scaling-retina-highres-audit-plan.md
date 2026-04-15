# UI Scaling Audit: Retina ve 1080p Ustu Ekranlar

**Created:** 2026-04-15
**Status:** Analysis Updated with MacBook Air M2 Runtime Notes

## Kapsam

Bu dokuman, oyunun mevcut olcekleme yapisini su iki problem uzerinden inceler:

1. macOS Retina ekranda yapilan olcekleme degisikliklerinin gorunurde uygulanmamasi.
2. 1080p ustu ve fiziksel olarak buyuk ekranlarda oyunun hala gorece kucuk kalmasi.

Ek olarak su hipotez degerlendirildi:

- Yuksek cozumunurluklu 13 inch Retina ve 16.1 inch buyuk ekranlarda oyun fiilen ayni olcek/geometri ile yerlestigi icin, buyuk ekranda ekran kullanim orani dusuyor olabilir.

Bu guncellemede statik kod analizi, mevcut testler, dokumantasyon ve sinirli cihaz-runtime dogrulamasi birlikte kullanildi. Mevcut makinede sistem bilgisi, AppKit/NSScreen metrikleri ve ilgili testler dogrulandi; ancak oyunun tum popup/menu/gameplay akislarinin canli goruntu karsilastirmasi bu turda yapilmadi.

## Bu Cihazda Dogrulanan Veriler

Bu workspace'in calistigi cihaz uzerinde asagidaki veriler runtime olarak dogrulandi:

- Model: MacBook Air M2 (`Mac14,2`)
- Dahili panel: `2560x1664 Retina` (`system_profiler SPDisplaysDataType`)
- AppKit logical frame: `1470x956` point (`NSScreen.mainScreen().frame()`)
- AppKit backing rect: `2940x1912` pixel (`NSScreen.convertRectToBacking_(frame)`)
- `backingScaleFactor`: `2.0`
- `src/platform_utils.py::get_native_resolution()` bu cihazda `1470x956` donduruyor
- Ilgili regresyonlar calistirildi: `tests/test_platform_effective_ui_size.py`, `tests/test_phase3_ui_scaling.py`, `tests/test_phase8_overlay_ui_scaling.py`, `tests/test_phase8_main_popup_ui_scaling.py` -> `73 passed`

Bu veri seti iki kritik noktayi netlestiriyor:

1. Bu MacBook'ta logical size `1440x900` degil, su anki display mode icin `1470x956`.
2. Raw/backing boyutu, panelin native `2560x1664` pikselinden bile buyuk bir uzayda (`2940x1912`) temsil edilebiliyor. Bu nedenle raw-surface bazli clamp'ler yalnizca Retina 2x degil, macOS'in scaled mode davranisindan da etkileniyor.

## Ozet Sonuc

Iki ana kok neden gorunuyor:

1. **Olcekleme zinciri parcali.** Bazi ekranlar effective/logical display size kullanirken, ana menu popup/content, oyun ici overlay ve bazi campaign/coop yollarinda hala raw surface boyutu kullaniliyor.
2. **Gameplay geometri tavanlari cok sert.** Tek oyunculu ve coop tarafta board hucre boyutu ile HUD panel genisligi yuksek cozumunurlukte buyumek yerine sabit tavana carpiyor.

Sonuc olarak:

- Retina ekranlarda effective-size duzeltmeleri sadece bu zinciri kullanan ekranlarda etkili oluyor.
- Oyun alani ve HUD gibi kritik alanlar buyuk ekranlarda daha fazla yer kaplamak yerine daha cok bosluk birakiyor.
- Mevcut MacBook Air M2'de classic gameplay geometri problemi, Retina normalize edilse bile ayri olarak devam ediyor; cunku `1470x956` logical boyutta bile `get_cell_size()` klasik `10x20` tahta icin yine `40` tavana vuruyor.

## Mevcut Yapi

### 1. Display modu fiilen always-fullscreen

Kod tabani artik gercek bir pencere modu secimi yapmiyor.

- `src/platform_utils.py::create_display(...)` icinde girilen parametrelerden bagimsiz olarak `fullscreen = True`, `borderless = True`, `resizable = False` zorlanıyor.
- `src/main.py` baslangicta daima `create_display(..., fullscreen=True, borderless=True)` cagiriyor.
- `src/settings_manager.py` eski `borderless_fullscreen` ve `resolution` anahtarlarini temizliyor.
- `src/platform_utils.py::is_fullscreen_toggle(...)` daima `False` donuyor.
- `src/main.py::_toggle_fullscreen(...)` ve `src/game.py::toggle_fullscreen(...)` gercek mod degisimi yapmiyor; sadece tam ekranı yeniden uyguluyor.

### 2. macOS Retina yolu

macOS tarafinda su kararlar alinmis:

- `src/main.py` icinde `SDL_VIDEO_HIGHDPI_DISABLED=0` set ediliyor. Yani HiDPI aktif.
- `src/platform_utils.py::get_native_resolution()` macOS'ta logical point boyutunu hedefliyor.
- `src/platform_utils.py::create_display(...)` macOS'ta `pygame.NOFRAME | pygame.DOUBLEBUF` ile borderless fullscreen olusturuyor.
- `docs/macos_borderless_fullscreen.md` de bu secimin, native fullscreen crash riskini engellemek icin bilerek yapildigini dogruluyor.

Bu tasarimda pencere logical size uzerinden kurulur, fakat aktif display surface fiziksel piksel boyutunda olabilir. Kodun bazi bolumleri logical size, bazi bolumleri fiziksel surface size kullandigi icin Retina davranisi tek tip degil.

Mevcut MacBook Air M2 dogrulamasi bu noktayi daha da guclendiriyor:

- Panel native boyutu `2560x1664`
- AppKit logical frame `1470x956`
- AppKit backing rect `2940x1912`

Yani macOS scaled mode altinda `logical size`, `native panel pixel size` ve `backing/raw pixel size` ayni sey degil. Bu nedenle raw surface kullanan helper'lar sadece Retina 2x degil, scaled mode yuzunden de oldugundan buyuk bir koordinat uzayina bakabiliyor.

### 3. Effective-size katmani var, ama sadece parcali kullaniliyor

Ortak helper katmani mevcut:

- `src/platform_utils.py::get_window_logical_size(...)`
- `src/platform_utils.py::get_effective_ui_size(...)`
- `src/ui_scaling.py::resolve_ui_scale_size(...)`
- `src/ui_scaling.py::get_effective_scale(...)`

Bu helper'lar aktif display surface icin logical/effective boyutu kullanip, offscreen surface'lerde raw size'i korumayi hedefliyor.

### 4. Effective-size kullanan ekranlar

Asagidaki ekranlar effective/logical UI size kullaniyor:

- `src/menu.py::_ui_scale()`
- `src/game.py::_ui_scale()`
- `src/graphics_menu.py::_ui_scale()`
- `src/guide_screen.py::_ui_scale()`
- `src/settings_screen_tabbed.py::_ui_scale()`
- `src/extras_menu.py::_extras_ui_scale()`

### 5. Hala raw surface kullanan kritik yollar

Asagidaki yollar hala raw surface boyutundan hesap yapıyor:

- `src/menu.py::_fullscreen_panel_scale()`
- `src/menu.py::_menu_panel_content_scale()`
- `src/main.py::_fullscreen_popup_scale()`
- `src/game.py::_overlay_ui_scale()`
- `src/campaign/level_select.py::_get_ui_scale()`
- `src/coop_game.py::_ui_scale()`

Bu ayrim, Retina'da "bazi ekran degisiyor, bazi ekran hic degismiyor" hissini tam olarak acikliyor.

### 6. Mouse/input zinciri Retina icin buyuk olcude normalize edilmis durumda

Mevcut audit, MacBook tarafindaki ana problemin temel mouse koordinati degil gorsel/layout scaling oldugunu da gosteriyor:

- `src/platform_utils.py::normalize_mouse_pos(...)`
- `src/platform_utils.py::get_mouse_pos()`
- `src/main.py`, `src/menu.py` ve `src/game.py` icindeki bircok click/hover call-site'i bu helper'lari kullaniyor

Bu, popup/menu migrasyonunda hitbox parity'sinin yine de test edilmesi gerektigi gercegini degistirmiyor; ancak mevcut kok neden pointer normalization eksikligi degil.

## Bulgular

### Bulgı 1: Retina'da olcekleme degisiklikleri tum oyuna uygulanmiyor

Bu problem gercek ve kodla tutarli.

Neden:

- Effective-size zinciri sadece bazi ekranlarda devrede.
- Ana menu ic panel/content yolu ve popup'lar hala raw surface boyutundan olcekleniyor.
- Oyun ici overlay/pause/game-over ailesi de raw canvas olceginde kaliyor.

Ozellikle `tests/test_phase3_ui_scaling.py` mevcut niyeti acikca dogruluyor:

- Menu genel UI scale preset'ten etkileniyor.
- Ama `menu._fullscreen_panel_scale()` ve `menu._menu_panel_content_scale()` etkilenmiyor.

Yani bug yalnizca "Retina detection calismiyor" degil; asil sorun, Retina'yi normalize eden helper'in butun gorunur UI katmanlarina tasinmamis olmasi.

### Bulgi 1A: Bu MacBook'ta raw/backing ayrismasi generic Retina orneginden daha sert

Ilk plan versiyonundaki `1440x900 logical / 2880x1800 physical` senaryosu, genel bir Retina ornegiydi. Mevcut cihazda runtime dogrulamasi su tabloyu verdi:

- logical frame: `1470x956`
- backing rect: `2940x1912`
- native panel: `2560x1664`

Bu su anlama geliyor:

- `raw surface` kullanan helper'lar, bu cihazda panelin native pikselinden bile buyuk bir backing uzayina bakabilir.
- Dolayisiyla `menu._fullscreen_panel_scale()`, `menu._menu_panel_content_scale()`, `main._fullscreen_popup_scale()` ve `game._overlay_ui_scale()` gibi clamp'li helper'lar cap'e cok daha erken vurur.
- Bu nedenle MacBook tarafinda "yaptigim olcek degisikligi uygulanmadi" hissi, yalnizca logical-vs-physical 2x farkindan degil, scaled desktop mode davranisindan da beslenebilir.

### Bulgı 2: Buyuk ekranlarda oyun kucuk kaliyor, cunku gameplay geometri buyumuyor

Bu problem de gercek ve root cause cok net.

Tek oyunculu gameplay tarafinda:

- `src/game.py::get_cell_size()` board hucre boyutunu `min(cell_width, cell_height, 40)` ile hesapliyor.
- Yani hucre boyutu **40 px ustune cikamiyor**.
- `src/game.py::_draw_right_hud_panel(...)` HUD panel genisligini `min(220, max(120, available_right))` ile hesapliyor.
- HUD olcegi de `max(0.72, min(1.05, panel_width / 220.0))` ile sinirli.

Bu su anlama geliyor:

- 10x20 klasik board icin maksimum board boyutu fiilen 400x800 px.
- Sag HUD paneli de fiilen 220 px ustune cikamiyor.
- 2560x1440, 2560x1600, 2880x1800 gibi ekranlarda kalan alan sadece bos margin olarak kaliyor.

Ornek:

- 2560x1440 ekranda klasik board icin hucre boyutu hesabı tavana carpar ve 40 olur.
- Board genisligi 400 px, yuksekligi 800 px olur.
- Bu, tam ekran bir 1440p/QHD alanda gorece cok kucuk bir oyun merkezi demektir.

Co-op tarafta da ayni desen var:

- `src/coop_game.py::_calculate_layout()` icinde `cs = int(min(40, cell_by_h, cell_by_w))`
- Sol/sag panel icin `side_panel = 120`

Yani coop da yuksek cozumunurlukte buyumek yerine ayni tavana kilitleniyor.

### Bulgı 3: Kullanici hipotezi parcali olarak dogru

Hipotez: 13 inch Retina ile 16.1 inch buyuk ekran ayni olcekle yerlesiyor olabilir.

Karar: **Parcali olarak dogru.**

Dogru olan kisim:

- Yuksek cozumunurlukte bircok yol clamp/cap nedeniyle ayni nihai olcege vuruyor.
- Gameplay geometri tarafinda hucre boyutu hem Retina hem de buyuk yuksek cozumunurluklu panelde ayni 40 px tavana carparak ayni board geometrisini uretebilir.
- Raw popup/content scale yollarinda da yuksek cozumunurluklu surface hemen tavana vuruyor.

Eksik olan kisim:

- Kod bugun fiziksel ekran inch bilgisini olcekleme girdisi olarak kullanmiyor.
- Pygame/SDL akisi icinde kararlar logical size, raw surface size ve birkac sabit cap uzerinden veriliyor.
- Yani problem dogrudan "13 inch vs 16.1 inch" bilgisinin kullanilmamasi degil; esas problem **aynı yuksek cozumunurluk sinifindaki ekranlarin cok erken tavana vurmasi** ve gameplay geometri icin buyume alaninin kapanmasi.

Kisa haliyle:

- Kod ayni fiziksel panel boyutuna gore degil,
- ama ayni ya da benzer yuksek DPI / yuksek cozumunurluk kosullarinda **aynı clamped geometriyi** uretebiliyor.

### Bulgı 4: Sorun gercek bir fullscreen vs borderless seciminden kaynaklanmiyor

Kullanici istegindeki "tam ekran / cerceveli tam ekran seciminin etkisi" arastirildi.

Sonuc:

- Kod tabaninda bugun kullanicinin secebildigi gercek bir exclusive fullscreen / borderless fullscreen / windowed ayrimi yok.
- Uygulama fiilen hep borderless fullscreen gibi davraniyor.
- Windows/Linux'ta yalnizca borderless set_mode beklenen boyutu vermezse exclusive fullscreen fallback var.
- macOS'ta ise NOFRAME borderless yol bilincli olarak kullaniliyor; native fullscreen crash nedeniyle bu tercih edilmıs.

Bu yuzden su anki davranis icin "kullanici windowed secseydi duzelir miydi" sorusunun pratik bir karsiligi yok; o mod zaten yok.

Ama mode farki dolayli olarak yine onemli:

- macOS NOFRAME + HiDPI yolunda pencere logical, surface fiziksel olabilir.
- Eger olcekleme raw surface'ten hesaplanırsa Retina normalize edilmemis olur.

Yani burada sorun mod secimi degil, **moddan bagimsiz metrik secimi**.

### Bulgı 5: Test coverage helper katmaninda var, ama buyuk ekran gameplay occupancy icin eksik

Mevcut testler su alanlari koruyor:

- `tests/test_platform_effective_ui_size.py` macOS icin `2880x1800 surface -> 1440x900 effective` davranisini dogruluyor.
- `tests/test_phase3_ui_scaling.py`, `tests/test_phase5_settings_ui_scaling.py`, `tests/test_ui_scaling.py` effective-scale helper cap davranisini dogruluyor.
- `tests/test_phase8_overlay_ui_scaling.py` overlay yolunun bilerek raw kaldigini ve `game.get_cell_size()` icinde `40` cap'inin aktif oldugunu dogruluyor.
- Bu guncellemede ilgili testlerin secili alt kumesi calistirildi ve mevcut durumda geciyor.

Eksik olanlar:

- Buyuk ekranlarda gameplay alaninin ekran kullanim oranini test eden regression test yok.
- Tek oyuncu/coop board geometri buyumesinin istenen davranişi icin kabul testi yok.
- Retina macOS'ta menu popup/content ile gameplay overlay yollarinin effective-size migrasyonunu test eden entegre senaryo yok.
- Mevcut MacBook Air M2 scaled mode'unu dogrudan modelleyen `1470x956 logical / 2940x1912 backing` regression testi yok.

## Sayisal Etki Ozeti

### Senaryo A: Bu MacBook Air M2'de gorulen Retina + scaled mode mantigi

Varsayim:

- Logical frame: `1470x956`
- Cocoa backing rect: `2940x1912`
- Panel native resolution: `2560x1664`

Effective-size kullanan ekranlar icin:

- 1366x768 referansli UI scale yaklasik `min(1470/1366, 956/768) = 1.07`

Raw surface kullanan popup/content yollarinda:

- 1920x1080 referansli scale `min(2940/1920, 1912/1080) = 1.53+`
- Ama cap nedeniyle 1.16 veya 1.35'e sabitleniyor.

Classic gameplay geometri icin:

- `SIDE_PANEL_WIDTH = 180`, `INFO_PANEL_HEIGHT = 120`
- logical bazda bile `min((1470-180)//10, (956-120)//20, 40) = 40`

Bu kritik cunku su sonuca goturur:

- menu/popup tarafinda raw-vs-effective ayrismasi gercekten var
- ama gameplay occupancy bug'i bunun otesinde, mevcut MacBook logical boyutunda bile kendi basina tekrarliyor

Sonuc:

- Effective-size duzeltmesi sadece onu kullanan katmanda gorunur.
- Raw katmanlar Retina'da dogal olarak cap'e vurur ve degisiklikler "uygulanmamis" gibi hissedilir.
- Gameplay geometri tarafinda ise effective-size'a gecmek tek basina yetmez; `40` cap kaldigi surece bu cihazda da oyun ayni kucuk merkez hissini verir.

### Senaryo B: 16.1 inch yuksek cozumunurluklu ekran

Varsayim:

- Surface size: 2560x1600

Tek oyunculu board hucre boyutu:

- Genislikten gelen teorik hucre boyutu cok daha yuksek olur.
- Yukseklikten gelen teorik hucre boyutu da 40'tan buyuktur.
- Son karar yine `min(..., 40)` nedeniyle 40 olur.

Sonuc:

- Board yine 400x800 px bandinda kalir.
- HUD panel yine 220 px bandinda kalir.
- Fiziksel ekran buyudukce oyun alanı gorece daha az yer kapliyormus gibi gorunur.

## Kok Nedenler

### Birincil kok nedenler

1. UI olceginin tek otoriteden hesaplanmamasi.
2. Gameplay geometri ile UI tipografisinin ayni problem sanilmasi.
3. Retina uyumlulugunun helper katmaninda cozulup draw/layout zincirlerine tam tasinmamasi.
4. Ekran aileleri arasinda referans boyutlarinin tutarsiz olmasi (`1366x768`, `1400x900`, `1920x1080`).
5. Yuksek cozumunurlukte erken tavana vuran sabitler:
   - single player cell cap = 40
   - coop cell cap = 40
   - single player HUD panel width max = 220
   - coop side panel baseline = 120
   - popup/content scale cap'leri = 1.16 / 1.20 / 1.35 gibi dusuk ust sinirlar

### Ikincil kok neden

- Oyun bugun fiilen tek display mode'da calistigi icin fullscreen mode farklarini kullanarak davranis izole etmek mumkun degil.

## Asil Sorun Tam Olarak Ne?

Bu bug tek bir yerde degil, uc farkli katmanda olusuyor:

### Katman A: Display metric secimi karisik

- Bazi yerler logical/effective size kullaniyor.
- Bazi yerler raw surface size kullaniyor.
- Bazi yerler de dogrudan window width/height cache'i veya sabit referans kullaniyor.

Bu nedenle "Retina destegi var" demek teknik olarak dogru olsa da, bu destek oyunun tum gorunen UI'sina yayilmis degil.

### Katman B: Gameplay geometri UI scale'den bagimsiz ve sert sinirli

- Board boyutu font buyumesinden degil, `get_cell_size()` ve layout helper'larindan geliyor.
- Bu helper'larda 40 px gibi sert ust sinirlar var.
- Dolayisiyla kullanici font/panel olcegini buyutse bile board ve HUD ayni kalabiliyor.

Bu katman, buyuk ekranda oyunun kucuk kalmasinin asil sebebi.

### Katman C: Kullanici olcek ayari kapsam olarak dar

`ui_scale_preset` bugun yalnizca `apply_ui_scale_preset(...)` veya `get_effective_scale(...)` kullanan yolları etkiliyor.

Etkilenmeyen ornekler:

- `src/game.py::get_cell_size()`
- `src/game.py::_draw_right_hud_panel(...)`
- `src/coop_game.py::_calculate_layout()`
- `src/menu.py::_fullscreen_panel_scale()`
- `src/menu.py::_menu_panel_content_scale()`
- `src/main.py::_fullscreen_popup_scale()`

Bu yuzden kullanicinin "olcekleme degisikligi MacBook Retina'da uygulanmiyor" hissi teknik olarak su anlama geliyor:

- preset bazi text/padding/layout yollarina yansiyor,
- ama kullanicinin gozunun takildigi board/popup/HUD gibi ana gorunen alanlara yansimiyor.

## Neden Kullanici Ayari Sorunu Tek Basina Cozmuyor?

Bugun ayar zinciri su sekilde:

- `src/settings_manager.py` icindeki `_sync_ui_scale_preset()` -> `ui_scaling.set_ui_scale_preset(...)`
- Bu da `src/ui_scaling.py::apply_ui_scale_preset(...)` uzerinden sadece belirli wrapper'lara etki ediyor.

Pratikte bu su demek:

- `menu._ui_scale()` gibi yollar buyuyor/kuculuyor.
- Ama `game.get_cell_size()` gibi gameplay geometri hesaplari hic etkilenmiyor.
- Bu yuzden kullanici ayari ile "oyun daha okunakli" hale gelebilir, ama "oyun ekranda daha buyuk yer kaplasin" problemi cozulmez.

Bu ayrim planin ana karari olmali:

- **UI readability scaling** ve
- **gameplay occupancy scaling**

ayni sey degil.

## Kodda Nereler Oynanmali?

Asagidaki liste, degisikligin nerede baslayip nereye yayilacagini netlestirir.

### 1. Once degisecek cekirdek dosyalar

#### `src/game.py`

Bu dosya tek oyunculu gameplay'nin asıl kok noktasidir.

Mutlaka degisecek fonksiyonlar:

- `update_fonts()`
  - su an `_active_ui_size()` kullaniyor
  - font kararlarini raw canvas yerine effective UI metric'ten almasi daha dogru
- `get_cell_size()`
  - `min(cell_width, cell_height, 40)` siniri burada
  - bu fonksiyon tek oyunculu board'un buyuk ekranlarda neden buyumedigini belirliyor
- `get_board_offset()`
  - `SIDE_PANEL_WIDTH` sabiti ve eski board genisligi varsayimi ile merkezi hesapliyor
  - board buyudugunde HUD ile birlikte yeniden tasarlanmasi gerekiyor
- `_draw_right_hud_panel(...)`
  - `panel_width = min(220, max(120, available_right))` burada
  - panel genisligi ve `hud_scale` buyuk ekranlarda erken kilitleniyor
- `_overlay_ui_scale(...)`
  - pause / quit / game-over overlay zincirinin giris noktasi
  - Retina migrasyonunda bu helper tek basina degil, tum overlay rect zinciri ile birlikte ele alinmali

Bu dosyada yalnizca `40` sayisini buyutmek yetmez. Daha dogru cozum, board rect ve HUD panel rect'i icin ortak bir gameplay layout helper uretmektir.

Onerilen yeni helper yapisi:

- `_compute_gameplay_layout_metrics()` veya benzeri tek kaynakli bir helper
- Donmesi gereken alanlar:
  - `cell_size`
  - `board_rect`
  - `hud_panel_rect`
  - `usable_play_band`
  - `gameplay_scale` ya da `occupancy_profile`

Bu helper kurulmadan parca parca degisiklik yapmak, modlar arasinda yeni sapmalar uretir.

#### `src/coop_game.py`

Bu dosya coop tarafindaki ayni problemin kok noktasi.

Mutlaka degisecek fonksiyonlar:

- `_ui_scale()`
  - hala `self.window_width / 1366`, `self.window_height / 768` tabanli raw hesap yapiyor
- `_calculate_layout()`
  - `side_panel = 120`
  - `cs = int(min(40, cell_by_h, cell_by_w))`
  - coop board, sol panel ve sag panel bu noktada tavana vuruyor
- `_draw_hud(...)`
  - alt/ust bar yukseklikleri ve fontlar `_ui_scale()` ile buyuyor, ama panel alani `_calculate_layout()` kadar buyumuyor
- `_draw_side_panels(...)`
  - yan preview kartlari `_side_panel_width` uzerinden ciziliyor; layout buyumeden bu panel de buyumez

Burada da sadece `40 -> 52` gibi bir degisiklik yeterli degil. `src/game.py` ile uyumlu ikinci bir gameplay occupancy policy gerekiyor.

### 2. Base gameplay degisince audit edilecek bagimli dosyalar

#### `src/game_modes.py`

- `HardcoreMode._draw_right_hud_panel(...)` kendi panel genisligi ve spacing mantigini override ediyor.
- Base `Game` hud'u buyutulurse bu override tekrar stale hale gelebilir.

#### `src/campaign/campaign_mode.py`

- Campaign kendi `_draw_right_hud_panel(...)` yoluna sahip.
- Ayrica `_get_campaign_hud_scale(...)` ve `_get_campaign_right_hud_panel_rect(...)` ile base `Game` HUD'undan ayrismis kendi layout politikasini kullaniyor.
- Base gameplay board rect'i degisirse campaign hud panel rect'i ve boss/mini-boss icerik akisinin birlikte yeniden kontrol edilmesi gerekiyor.

#### `src/campaign/coop_campaign_mode.py`

- Bu sinif ayri bir layout helper override etmiyor; `CoopGame` mirasi uzerinden `_ui_scale()` ve `_calculate_layout()` sonucunu kullaniyor.
- Bu nedenle `src/coop_game.py` tarafindaki occupancy degisikligi co-op campaign'e dogrudan yansiyacak.
- Kabul testleri yalnizca coop sandbox modu degil, coop campaign akisini da kapsamalı.

#### `src/game_modes_extra.py`

Bu dosya kritik, cunku kendi board geometri override'larini yapiyor:

- `get_board_offset()`
- `get_cell_size()`

Ozellikle Mystery mode zaten sol ve sag paneli ozel hesapliyor ve yine `40` cap kullaniyor. Base `Game` duzelse bile bu dosya ayri kalirsa buyuk ekran bug'i mod bazli geri doner.

### 3. Retina / popup / raw UI migrasyonu icin degisecek dosyalar

#### `src/menu.py`

Degistirilmesi gereken helper'lar:

- `_fullscreen_panel_scale()`
- `_menu_panel_content_scale()`

Ama burada sadece helper'lari effective-size'a cevirmek yeterli degil. Bu helper'larin kullandigi tum panel rect/hitbox zinciri de audit edilmeli.

Pratikte su yaklasim daha guvenli:

- once menu icin `panel geometry` ve `panel content` ayrimini aciklastir
- sonra geometry tarafini effective-size ya da normalized container metric ile tası
- en son input rect'lerini ayni metric'ten turet

#### `src/main.py`

- `_fullscreen_popup_scale(screen)` bugun raw surface size kullaniyor.
- Bu helper intro/zen/tutorial benzeri popup girislerinde kullaniliyor.
- Eger effective-size'a gecilecekse popup rect hesaplari, backdrop clamp ve button rect'leri birlikte tasinmali.

Burada yapilacak en saglikli degisiklik tek helper degil, ortak popup metrics wrapper'i yazmaktir.

Onerilen yeni helper:

- `_get_popup_metrics(screen)`
- Donmesi gerekenler:
  - `ui_scale`
  - `panel_width`
  - `panel_height`
  - `padding`
  - `title/body/button font size`

#### `src/game.py` overlay callers

`_overlay_ui_scale(...)` kullanan su aileler birlikte tasinmali:

- pause menu
- quit confirm
- game over / result overlay

Sebep:

- Bunlarin panel rect'i, fontu, button rect'i ve mouse hitbox'i birbirine bagli.
- Sadece font scale veya sadece panel scale degisirse hover/click alanlari bozulabilir.

#### `src/campaign/level_select.py`

- `_get_ui_scale()` hala raw `get_scale(...)` kullaniyor.
- Ayrica bu ekran `1400x900` referansina bagli; ana menu ve popup aileleriyle ayni baseline'i paylasmiyor.
- Bu ekran buyuk ihtimalle birinci gorunen root cause degil, ama Retina parity icin backlog'a alinmali.

## Kodda Ne Oynanmamali?

Asagidaki kisayollar cazip ama yanlis yon olur:

### 1. Sadece sabitleri buyutmek

Ornek:

- `SIDE_PANEL_WIDTH`
- `INFO_PANEL_HEIGHT`
- `DEFAULT_WINDOW_WIDTH`
- `DEFAULT_WINDOW_HEIGHT`

Bu sabitleri global degistirmek butun modlara dogrudan yayilir ve dusuk cozumunurlukte yeni kirilmalar uretir.

### 2. Sadece `ui_scale_preset` multiplier'larini buyutmek

Bu, gameplay occupancy'yi degistirmez. Sadece etkiledigi ekranlarda text/padding'i buyutur; hatta popup ile icerik arasinda yeni dengesizlik uretir.

### 3. Ilk adim olarak `create_display()` veya fullscreen modelini degistirmek

Display mode semantigi bu bug'in kok nedeni degil. Once layout ve metric secimi duzeltilmeli.

### 4. Tek basina `get_effective_ui_size()` helper'ini degistirmek

Helper bugun amacina uygun calisiyor olabilir; asil problem bu helper'in tutarli kullanilmamasi. Helper'i zorlamak yerine call site'lari duzeltmek daha guvenli.

## Onerilen Kod Degisiklik Biçimi

En temiz yol, mevcut kodu tek tek "buraya da bir cap ekle / buraya da bir scale carp" seviyesinde yamalamak degil.

### Adim 1: Gameplay layout'i merkezi hale getir

`src/game.py` icinde tek noktali metrics helper yaz:

- input:
  - active canvas size
  - effective UI size
  - board width/height
  - mode/profile bilgisi
- output:
  - `cell_size`
  - `board_rect`
  - `right_panel_rect`
  - `hud_scale`

Sonra su fonksiyonlar bu helper'dan beslensin:

- `get_cell_size()`
- `get_board_offset()`
- `_draw_right_hud_panel(...)`

### Adim 2: Coop icin ayni politikayi ayri helper'a tası

`src/coop_game.py::_calculate_layout()` tek cikis noktasi kalabilir, ama ic mantigi tek oyuncu ile ayni occupancy politikasini kullanmali.

Minimum beklenti:

- `40` cap profile-based olmali
- `120` yan panel baseline'i buyuk ekranlarda sabit kalmamali

### Adim 3: Raw popup ailesini metrics tabanli yap

`src/main.py` ve `src/game.py` icindeki popup/overlay code'u icin ortak bir pattern kullan:

- once panel rect hesapla
- sonra font/padding/button rect'i panel rect'ten turet
- input hitbox'larini ayni rect'ten besle

Boylece effective-size migrasyonu yapildiginda click alanlari kaymaz.

## Hangi Testler Dogrudan Etkilenecek?

Kod degistiginde su testler muhtemelen guncellenecek:

- `tests/test_platform_effective_ui_size.py`
  - generic macOS logical/effective davranisi korunurken, mevcut MacBook scaled mode case'i eklenebilir
- `tests/test_phase8_overlay_ui_scaling.py`
  - bugun `game.get_cell_size()` icin `40` cap davranisini bekliyor
- `tests/test_coop.py`
  - coop panel ve layout beklentileri yeni yan panel genislikleriyle degisebilir
- `tests/test_phase3_ui_scaling.py`
  - menu raw helper'lari effective-size zincirine alinırsa mevcut beklentiler degisecek

Yeni eklenmesi gereken testler:

- mevcut MacBook Air M2 case'i: `1470x956 logical`, `2940x1912 backing`, `2560x1664 native panel` notu ile helper regression
- `2560x1440`, `2560x1600`, `2880x1800` gibi buyuk ekran senaryolari
- single player board occupancy regression
- coop board occupancy regression
- campaign HUD / right panel parity regression
- popup rect + button hitbox parity regression

## En Hizli Kullanici Gozuyle Kazanim Nerede?

Kullaniciya ilk gorunur duzelme icin en yuksek ROI su sirada:

1. `src/game.py` icinde board + right HUD buyutme
2. `src/coop_game.py` icinde coop layout buyutme
3. `src/main.py` popup metrics duzeltmesi
4. `src/menu.py` raw content/modal scale migrasyonu

Bu sira su yuzden onemli:

- kullanici buyuk ekranda asil olarak oyun alaninin kucuklugunu fark ediyor
- sonra popup/menu tarafindaki Retina tutarsizligi fark ediliyor

Yani ilk kod degisikligi gameplay occupancy olmali; popup/menu migrasyonu ikinci dalga olmali.

## Onerilen Strateji

Bu problemi ilk turda fiziksel inch tespitiyle cozmek gerekmiyor. Daha dogru yon su:

1. UI okunabilirligi icin logical/effective size kullan.
2. Gameplay occupancy icin ayri bir geometri politikasi tanimla.
3. Buyuk ekranlarda board ve HUD'un daha fazla alan kullanmasina izin ver.
4. Raw overlay/menu yollarini kontrollu migration ile effective-size uyumlu hale getir.

## Uygulama Plani

### Phase 1: Scaling Policy Kilidi

**Hedef:** Tek bir ortak karar metni olusturmak.

Kararlar:

- Text/font/padding/tab gibi okumaya dayali UI elemanlari logical/effective size bazli hesaplanacak.
- Board, HUD panel, preview box, modal rect gibi geometri elemanlari ayri "occupancy" kurallari ile hesaplanacak.
- Raw surface scale sadece gercekten fiziksel canvas'a bagli efekt/backdrop yollarinda kalacak.

Teslimatlar:

- Tek kaynakli scaling policy notu
- `raw geometry`, `effective ui`, `gameplay occupancy` kavramlarinin acik tanimi

### Phase 2: Gameplay Geometry Buyume Tavani Acma

**Hedef:** Buyuk ekranlarda oyunun gercekten daha fazla alan kullanmasi.

Single player icin:

- `src/game.py::get_cell_size()` icindeki `40` cap kaldirilacak veya daha yuksek/profile-based hale getirilecek.
- Board genisligi sadece `SIDE_PANEL_WIDTH` dusulerek degil, hedef ekran kullanim oraniyla belirlenecek.
- HUD panel genisligi `max 220` yerine ekran genisligine gore buyuyebilecek.

Co-op icin:

- `src/coop_game.py::_calculate_layout()` icindeki `40` cap ve `120` side panel baseline buyuk ekran profiline gore yeniden tasarlanacak.

Kabul kriterleri:

- 2560x1440 ve 2560x1600 ekranlarda board/hud, 1366x768'e gore anlamli sekilde daha buyuk olmalı.
- Buyume sadece bos margin üretmemeli.

### Phase 3: Retina Uyumlulugu Icin Raw UI Yollarini Azaltma

**Hedef:** Retina'da "bazi seyler buyuyor, bazi seyler hic degismiyor" etkisini bitirmek.

Migrasyon adaylari:

- `src/menu.py::_menu_panel_content_scale()`
- `src/menu.py::_fullscreen_panel_scale()`
- `src/main.py::_fullscreen_popup_scale()`
- `src/game.py::_overlay_ui_scale()`

Onemli not:

- Bu helper'lar dogrudan effective-size'a cevrilmemeli.
- Onlari kullanan rect/hitbox/container zinciri de beraber tasinmali.
- Aksi halde popup rect ile icerik scale birbirinden kopar.

Kabul kriterleri:

- Retina macOS'ta popup/panel/content olcegi logical size degistiginde tutarli sekilde tepki vermeli.
- Input hitbox'lari ile cizim geometriği ayrismamali.

### Phase 4: Display Mode Semantics Temizligi

**Hedef:** Kodun neyi destekledigini acik hale getirmek.

Secenek A:

- Uygulama resmi olarak "always borderless fullscreen" kalsin.
- Ayar ve isimlendirme de bunu acikca yansitsin.

Secenek B:

- Gercek exclusive fullscreen, borderless fullscreen ve windowed modlari yeniden getir.
- Ama scaling hesaplari mode flag'lerine gore degil, effective/logical metrics + occupancy policy uzerinden calissin.

Oneri:

- Bu bugi cozmeye Phase 4 gerekli degil.
- Once Phase 1-3 uygulanmali.

### Phase 5: Test ve Donanim Dogrulama

**Hedef:** Bu konunun tekrar kirilmasini engellemek.

Eklenmesi gereken testler:

- `tests/test_gameplay_large_display_occupancy.py`
  - single player cell size 2560x1440 ve 2560x1600 senaryolarinda 1366x768'e gore buyumeli
- `tests/test_coop_large_display_occupancy.py`
  - coop layout daha buyuk ekranlarda daha fazla alan kullanmali
- `tests/test_retina_popup_scaling.py`
  - logical window size ile physical surface size ayrismasinda popup/content helper'lari beklenen kaynaktan hesap yapmali
- menu/game overlay migration sonrasi regression testleri

Manuel dogrulama matrisi:

- MacBook Air M2 Retina (`Mac14,2`) - current scaled mode: `1470x956 logical`, `2940x1912 backing`, panel native `2560x1664`
- 16.1 inch 1080p ustu Windows laptop ekranı
- Windows 100%, 125%, 150% DPI scaling
- Borderless fallback ve display recover senaryolari

## Oncelik Sirasi

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 5
5. Phase 4

## Net Karar

Bu sorunun ana nedeni fullscreen secenekleri degil.

Ana nedenler:

- parcali scaling mimarisi,
- Retina logical size ile raw surface size'in ayni seymis gibi kullanilmasi,
- ve gameplay geometri tarafindaki sert buyume tavanlari.

Ilk uygulanmasi gereken duzeltme, gameplay alaninin buyuk ekranlarda daha cok alan kullanmasini saglamak ve effective-size politikasini popup/menu/overlay zincirlerine kontrollu sekilde yaymaktir.
