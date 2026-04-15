# UI Scaling Audit: Retina ve 1080p Ustu Ekranlar

**Created:** 2026-04-15
**Status:** Analysis Complete, Implementation Plan Ready

## Kapsam

Bu dokuman, oyunun mevcut olcekleme yapisini su iki problem uzerinden inceler:

1. macOS Retina ekranda yapilan olcekleme degisikliklerinin gorunurde uygulanmamasi.
2. 1080p ustu ve fiziksel olarak buyuk ekranlarda oyunun hala gorece kucuk kalmasi.

Ek olarak su hipotez degerlendirildi:

- Yuksek cozumunurluklu 13 inch Retina ve 16.1 inch buyuk ekranlarda oyun fiilen ayni olcek/geometri ile yerlestigi icin, buyuk ekranda ekran kullanim orani dusuyor olabilir.

Bu inceleme statik kod analizi, mevcut testler ve dokumantasyon uzerinden yapildi. Bu ortamda gercek MacBook M2 Air veya 16.1 inch hedef cihazda canli runtime dogrulamasi yapilmadi.

## Ozet Sonuc

Iki ana kok neden gorunuyor:

1. **Olcekleme zinciri parcali.** Bazi ekranlar effective/logical display size kullanirken, ana menu popup/content, oyun ici overlay ve bazi campaign/coop yollarinda hala raw surface boyutu kullaniliyor.
2. **Gameplay geometri tavanlari cok sert.** Tek oyunculu ve coop tarafta board hucre boyutu ile HUD panel genisligi yuksek cozumunurlukte buyumek yerine sabit tavana carpiyor.

Sonuc olarak:

- Retina ekranlarda effective-size duzeltmeleri sadece bu zinciri kullanan ekranlarda etkili oluyor.
- Oyun alani ve HUD gibi kritik alanlar buyuk ekranlarda daha fazla yer kaplamak yerine daha cok bosluk birakiyor.

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

Eksik olanlar:

- Buyuk ekranlarda gameplay alaninin ekran kullanim oranini test eden regression test yok.
- Tek oyuncu/coop board geometri buyumesinin istenen davranişi icin kabul testi yok.
- Retina macOS'ta menu popup/content ile gameplay overlay yollarinin effective-size migrasyonunu test eden entegre senaryo yok.

## Sayisal Etki Ozeti

### Senaryo A: MacBook Retina mantigi

Varsayim:

- Logical window size: 1440x900
- Physical display surface: 2880x1800

Effective-size kullanan ekranlar icin:

- 1366x768 referansli UI scale yaklasik `min(1440/1366, 900/768) = 1.05`

Raw surface kullanan popup/content yollarinda:

- 1920x1080 referansli scale `min(2880/1920, 1800/1080) = 1.5+`
- Ama cap nedeniyle 1.16 veya 1.35'e sabitleniyor.

Sonuc:

- Effective-size duzeltmesi sadece onu kullanan katmanda gorunur.
- Raw katmanlar Retina'da dogal olarak cap'e vurur ve degisiklikler "uygulanmamis" gibi hissedilir.

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
4. Yuksek cozumunurlukte erken tavana vuran sabitler:
   - single player cell cap = 40
   - coop cell cap = 40
   - single player HUD panel width max = 220
   - coop side panel baseline = 120
   - popup/content scale cap'leri = 1.16 / 1.20 / 1.35 gibi dusuk ust sinirlar

### Ikincil kok neden

- Oyun bugun fiilen tek display mode'da calistigi icin fullscreen mode farklarini kullanarak davranis izole etmek mumkun degil.

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

- MacBook Air M2 Retina
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