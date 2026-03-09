# Ana Menu Disi UI Scaling Duzeltme Plani

Tarih: 2026-03-09
Durum: Arastirma tamamlandi, uygulama plani hazir
Kapsam: Ana menu disindaki ekranlar, paneller, modal pencereler ve yogun liste/grid UI'leri

## 1. Problem Tanimi

Ana menu disindaki bircok ekran 1080p ustu cozumunurluklerde yeterince buyumuyor. Sonuc olarak:
- panel ve popup'lar ekrana gore kucuk kaliyor,
- fontlar yeterli oranda buyumuyor,
- padding ve kart boyutlari 1080p davranisina kilitli kaliyor,
- ana menu ile diger ekranlar arasinda gozle gorulur olcek uyumsuzlugu olusuyor.

Ana menu bu sorunu daha az yasiyor, cunku panel yerlesimi yuzde tabanli ve 1920x1080 referansli icerik olcegi kullaniyor. Diger ekranlarda ise olcekleme parcali, yer yer sabit piksel tabanli, yer yer de buyumeyi 1.0'da kesen clamp'lere bagli.

## 2. Arastirma Ozeti

### Referans Davranis

- src/menu.py:
  - `_menu_panel_content_scale()` 1920x1080 referansi ile calisiyor.
  - `_ui_scale()` ve `_fullscreen_panel_scale()` buyumeye belirli olcude izin veriyor.
  - Panel rect'leri yuzde tabanli yerlesim mantigina sahip.

Bu, ana menunun yuksek cozumunurlukte gorece dengeli kalmasinin ana nedeni.

### Sorunlu Desenler

1. Buyumeyi 1.0'da kilitleyen helper'lar var.
- src/extras_menu.py: `_extras_ui_scale(... max_scale=1.0)`
- src/user_screens.py: `_ui_scale(... max_scale=1.0)`
- src/game_modes.py: bazi sayaç/panel helper'lari `max_scale=1.0`
- src/game_modes_advanced.py: survival panel helper'i `max_scale=1.0`
- src/game_modes_extra.py: overlay helper'i `max_scale=1.0`

2. Referans olarak ekranin ilk acilis boyutu veya native ekran boyutu kullaniliyor.
- src/extras_menu.py: `_base_window_size = self.screen.get_size()` ve oran buna gore hesaplanmis. Bu tasarim pratikte "yalnizca kuculme" davranisi uretiyor.
- src/user_screens.py: `_ui_reference_size` icin `pygame.display.Info().current_w/current_h` kullaniliyor. Bu da ozellikle fullscreen veya native boyutta calisirken buyumeyi 1.0 civarina sabitliyor.

3. Layout buyuyor ama font buyumuyor.
- src/campaign/level_select.py: `_get_ui_scale()` `max_scale=1.26` iken `_init_fonts()` icindeki font scale yorumlu sekilde `max_scale=1.0` ile cap'lenmis.
- Sonuc: panel/grid biraz buyurken tipografi geride kaliyor.

4. Hic merkezi olcekleme kullanmayan ekranlar var.
- src/settings_screen_tabbed.py: fontlar ve satir yukseklikleri sabit piksel.
- src/graphics_menu.py: kart genisligi, kart yuksekligi, spacing ve prompt boyutlari sabit piksel.
- src/guide_screen.py: tab panel, geri butonu, hint, kart basliklari ve icerik fontlari buyuk oranda sabit piksel.
- src/campaign/campaign_ui.py: level complete / fail popup'lari ekran boyutuna gore genisliyor ama ic padding, header, fontlar ve alt paneller agirlikla sabit piksel.
- src/campaign/campaign_mode.py: sol/sağ HUD/panel genislikleri ve fontlari agirlikla sabit ust/alt sinirlara bagli.

5. Sabit max panel genislikleri yuksek cozumunurlukte bosluk uretip UI'yi kucuk hissettiriyor.
- src/graphics_menu.py: 620 px kart genisligi
- src/campaign/campaign_mode.py: 340 px / 220 px gibi panel cap'leri
- src/guide_screen.py: 240 px tab panel cap'i

## 3. Risk Bazli Ekran Siniflandirmasi

Bu bolum, planin neden yeniden siralandigini aciklar. Ilk taslakta sorunlu ekranlar dogru tespit edildi, ancak uygulama sirasi gereksiz risk tasiyordu. Proje tekrar incelendiginde ekranlar 4 risk grubuna ayrildi.

### Dusuk Risk: Izole ve zaten kendi responsive akisi olan ekranlar

- src/extras_menu.py
- src/campaign/level_select.py

Neden dusuk risk:
- Ikisinde de yerel scale helper zaten var.
- Layout guncelleme yolu mevcut.
- Ikisi icin de dogrudan veya dolayli test zemini var.
- Etki alani gorece dar; gameplay loop'una dogrudan temas etmiyorlar.

### Orta Risk: Izole ama test yuzeyi zayif ekranlar

- src/graphics_menu.py
- src/guide_screen.py
- src/user_screens.py

Neden orta risk:
- Ana akis disi ekranlar ama cizim ve input geometriği birlikte degisiyor.
- graphics ve guide tarafinda hedef geometri nispeten basit.
- user_screens tarafinda cok fazla panel ve akisa gore degisen rect var.

### Yuksek Risk: Yogun input ve hitbox geometriği ureten ekranlar

- src/settings_screen_tabbed.py

Neden yuksek risk:
- Scroll, slider, sekme, overlay, keybind slot, help tooltip ve option rect mantigi ayni dosyada.
- Gorsel olcek degisince input geometriği de birlikte degisiyor.
- Bu ekran icin mevcut testler var, ama ayni zamanda en cok regresyon riski tasiyan ekranlardan biri.

### Cok Yuksek Risk: Gameplay ustu overlay ve HUD aileleri

- src/campaign/campaign_ui.py
- src/campaign/campaign_mode.py
- src/game.py
- src/game_modes.py
- src/game_modes_advanced.py
- src/game_modes_extra.py
- gerekirse src/main.py icindeki popup helper zinciri

Neden cok yuksek risk:
- Bunlar aktif oyun akisi sirasinda kullaniliyor.
- Sadece goruntu degil, okunabilirlik, odak, board cevresi bosluklari ve oyun hissi etkileniyor.
- Campaign tarafi cift katmanli: bir kisim campaign_ui icinde, bir kisim campaign_mode icinde hesap yapiyor.

## 4. Kok Nedenler

### Kok Neden A: Merkezi bir UI scaling sistemi yok

Kod tabaninda ayni amaca hizmet eden birden fazla helper var:
- `1366x768` referansi kullananlar
- `1920x1080` referansi kullananlar
- acilis boyutunu baz alanlar
- native display boyutunu baz alanlar
- hic helper kullanmayanlar

Bu parcalanma ayni uygulama icinde farkli ekranlarin farkli boy oranlari ve farkli buyume tavanlariyla davranmasina neden oluyor.

### Kok Neden B: "Yuksek cozumunurlukte buyumeyi engelleme" karari fazla agresif uygulanmis

Birden fazla yerde `max_scale=1.0` veya benzeri sinirlar kullanilmis. Bu sinir 1080p ustu tum ekranlarda buyumeyi fiilen durduruyor.

### Kok Neden C: Tipografi ve layout ayni olcekten beslenmiyor

Bazi ekranlar rect/padding boyutlarini buyuturken fontlari sabit tutuyor. Bu da UI'nin kucuk ve bos hissettirmesine yol aciyor.

### Kok Neden D: Sabit piksel cap'leri 1440p, ultrawide ve 4K'da orantisiz kaliyor

Sabit `min/max` panel genislikleri dusuk riskli bir koruma sagliyor ama yuksek cozumunurlukte yeterli degil. Bu yuzden ekranin ortasinda kucuk bir ada gibi duran paneller olusuyor.

## 5. Hedef Mimari ve Guvenlik Sinirlari

Amaç tek bir "her sey icin ayni scale" formulu degil; ortak bir temel uzerine 2-3 profilli bir sistem kurmak.

### Onerilen ortak olcek profilleri

1. `content_scale`
- Referans: 1920x1080
- Kullanim: tam ekran menuler, liste ekranlari, guide/settings/extras gibi ekranlar
- Onerilen cap: `min=0.72`, `max=1.18` veya ekran yogunluguna gore `1.22`

2. `dense_content_scale`
- Referans: 1920x1080
- Kullanim: cok satirli settings, keybind, uzun liste ekranlari
- Onerilen cap: `min=0.74`, `max=1.12` veya `1.16`

3. `modal_scale`
- Referans: 1920x1080
- Kullanim: popup, onay kutusu, tamamlandi/basarisiz modal'lari
- Onerilen cap: `min=0.68`, `max=1.20` veya `1.24`

### Temel ilke

- Buyume icin referans olarak ekranin ilk acilis boyutu veya native display boyutu kullanilmayacak.
- Buyume kararini aktif UI canvas boyutu verecek.
- Panel boyutu, tipografi ve spacing ayni olcek ailesinden beslenecek.
- Sadece okunabilirlik ve tasma riski olan yogun ekranlarda daha dusuk `max_scale` kullanilacak.

### Erken fazlarda dokunulmayacak alanlar

- src/ui_theme.py icindeki UIFonts global boyut sabitleri
- src/ui_theme.py icindeki UIFonts size_scale mekanizmasi
- src/retro_style.py icindeki global font scale davranisi
- src/menu.py ana menu layout sistemi

Gerekce:
- Bunlar global blast radius olusturur.
- Sorunun merkezi global font sistemi degil, ekran bazli parcali scaling mantigi.
- En risksiz ilerleyis, once lokal ekran helper'larini ortak bir yardimciya tasimaktir.

## 6. Uygulama Fazlari

### Faz 0: Baseline ve emniyet kapilari

Amaç:
- Kod degistirmeden once neyi degistirmeyecegimizi, neyi nasil olcecegimizi netlestirmek.

Yapilacaklar:
- Asagidaki ekranlar icin baseline kontrol listesi sabitlenecek:
  - Extras
  - Campaign level select
  - Graphics
  - Guide
  - User screens
  - Settings
- Her faz sonunda calisacak hedefli test listesi tanimlanacak.
- Erken fazlarda global font sistemine dokunmama karari korunacak.

Kabul kriteri:
- Her fazin cikis kosulu net olacak.
- Yardimci modulu eklenmeden hicbir ekran tasinmayacak.

### Faz 1: Ortak scaling yardimcisi cikarma, ama hicbir ekrani henüz tasimama

Amaç:
- Ortak matematik zemini kurmak, ama davranis degisikligini ayri commit/fazlara bolmek.

Yapilacaklar:
- Yeni ortak helper modulu ekle: onerilen yer `src/ui_scaling.py`.
- Burada su API'lerden en az biri tanimlansin:
  - `get_content_scale(screen_or_size, profile='standard')`
  - `get_modal_scale(screen_or_size, profile='standard')`
  - `scale_px(value, scale, minimum=1)`
- Referans cozumunurluk ve clamp profilleri tek yerde tutulacak.
- Helper icin birim test eklenmesi onerilir.
- Bu fazda mevcut ekranlardan hicbiri helper'a gecirilmeyecek.

Kabul kriteri:
- Yeni helper menuden bagimsiz ama ana menu mantigiyla uyumlu olacak.
- Bu faz tek basina davranis degisikligi uretmeyecek.

### Faz 2: En dusuk riskli 2 ekranin tasinmasi

Amaç:
- Ortak helper'i en izole ekranlarda gercek ortama almak.

Oncelikli dosyalar:
- src/extras_menu.py
- src/campaign/level_select.py

Yapilacaklar:
- src/extras_menu.py:
  - `_extras_ui_scale()` artik `_base_window_size` yerine ortak helper kullanacak.
  - `max_scale=1.0` siniri kontrollu bicimde yukseltilacak.
- src/user_screens.py:
- src/campaign/level_select.py:
  - `_init_fonts()` ve `_get_ui_scale()` ayni olcek kaynagindan beslenecek.
  - Font ve layout cap'leri birbirleriyle uyumlu hale getirilecek.

Not:
- Bu fazdan user_screens cikarildi. Sebep, ekran sayisinin fazla ve panel cesitliliginin yuksek olmasi.

Kabul kriteri:
- 1440p ve 4K Windows testlerinde bu ekranlar ana menuye gore belirgin sekilde daha dengeli gorunecek.
- Mevcut extras ve campaign level select testleri gecmeli.

### Faz 3: Kucuk ama izole ekranlarin tasinmasi

Amaç:
- Ana akis disi, gorece basit geometriye sahip ekranlari ikinci dalgada duzeltmek.

Oncelikli dosyalar:
- src/graphics_menu.py
- src/guide_screen.py

Yapilacaklar:
- Her dosya ayri ayri ele alinacak; ikisini tek committe birlestirmemek daha guvenli.
- Her dosya icin yerel `ui_scale` ve `s()` helper'i ortak modulu kullanacak sekilde eklenecek.
- Sabit font olusturma satirlari olcekli hale getir.
- Asagidaki sabitler scale ile beslensin:
  - panel padding
  - row height
  - tab height
  - card width/height limitleri
  - spacing
  - scrollbar offsetleri
  - hint / footer / prompt boyutlari
- `min/max` panel genislikleri korunacaksa, bu limitler de scale'e bagli yeniden hesaplanacak.

Kabul kriteri:
- Ayarlar, Grafik ve Kilavuz ekranlari 1440p ustunde "telefon UI'si gibi kucuk" gorunmeyecek.

Not:
- Bu fazdan settings ekrani cikarildi; cunku settings hitbox/scroll/slider riski ayri ele alinmali.

### Faz 4: User screens ailesini ayri fazda tasima

Amaç:
- Cok sayida panel iceren ama yine de menu-disinda kalan kullanici ekranlarini tek basina ele almak.

Oncelikli dosyalar:
- src/user_screens.py

Yapilacaklar:
- `_ui_reference_size` temelli oran mantigi kaldirilacak veya sadece fallback'e indirgenecek.
- `_ui_scale()` ortak helper'dan beslenecek.
- `_apply_responsive_metrics()` yeni helper ile calisacak.
- Profil listesi, detay paneli, avatar secimi ve form layout'lari birlikte kontrol edilecek.

Kabul kriteri:
- Kullanici secim ve yonetim ekranlari 1440p ustunde belirgin sekilde daha dengeli gorunecek.
- Liste, detay, buton ve avatar hitbox'lari bozulmayacak.

### Faz 5: Settings ekranini tek basina ele alma

Amaç:
- En yuksek UI/input regresyon riskini tek fazda izole etmek.

Oncelikli dosyalar:
- src/settings_screen_tabbed.py

Yapilacaklar:
- Once test kapsami genisletilecek:
  - panel rect hesaplari
  - content rect hesaplari
  - scroll max hesabi
  - option rect / input hizasi
- Sonra su alanlar scale ile beslenecek:
  - panel boyutu
  - tab boyutu
  - row height
  - fontlar
  - scrollbar offsetleri
  - overlay/prompt boyutlari
- Draw ve input geometriği ayni yardimci fonksiyonlardan beslenecek; iki ayri matematik kullanilmayacak.

Kabul kriteri:
- Mevcut settings testleri gecmeli.
- Yeni geometry testleri gecmeli.
- Mouse slider, scrollbar ve tab secimi calismaya devam etmeli.

### Faz 6: Campaign modal ailesini oyundan ayri tasima

Amaç:
- Gameplay hissini bozmadan once sadece campaign popup/modallari responsive hale getirmek.

Oncelikli dosyalar:
- src/campaign/campaign_ui.py

Yapilacaklar:
- Level complete / fail modal'larinda:
  - panel padding
  - header yuksekligi
  - section gap
  - footer/button boyutlari
  - font boyutlari
  ortak modal/profile scale ile beslenecek.

Kabul kriteri:
- Campaign popup ve bilgi panelleri 1080p ustunde kucuk kalmayacak.

Not:
- Bu fazda campaign_mode icindeki board-cevresi HUD panellerine dokunulmayacak.

### Faz 7: Campaign yan panel ve HUD ailesi

Amaç:
- Gameplay yakinindaki campaign panel sistemini sonradan, daha kontrollu ele almak.

Oncelikli dosyalar:
- src/campaign/campaign_mode.py

Yapilacaklar:
- Sol panel ve sag HUD panel cap'leri yeniden degerlendirilecek.
- Gerekirse `max_panel_width = min(scaled_cap, available_space)` hibrit mantigi kurulacak.
- Board etrafindaki guvenli bosluklar korunacak.

Kabul kriteri:
- Panel buyuse de board okunurlugu ve gameplay alani bozulmayacak.

### Faz 8: Oyun ici popup ailesi ve mod overlay'leri

Amaç:
- Menu disi geri kalan panelleri en sona birakmak.

Dosyalar:
- src/game.py
- src/game_modes.py
- src/game_modes_advanced.py
- src/game_modes_extra.py
- gerekirse src/main.py icindeki `_fullscreen_popup_scale()` cagri zinciri

Yapilacaklar:
- Overlay/modal helper'lari ortak `modal_scale` ile hizalanacak.
- `max_scale=1.0` kalan tum overlay/panel helper'lari gozden gecirilecek.
- Her mod ekrani birlikte degil, tek tek ele alinacak.

## 7. Teknik Uygulama Kurallari

### Kurallar

1. Tum yeni ekran helper'lari aktif ekran boyutundan hesap yapacak.
2. Panel, font ve spacing ayri ayri uydurulmayacak; ayni scale ailesi kullanilacak.
3. `max_scale=1.0` ancak bilincli olarak yogun veri ekranlarinda kullanilacak; varsayilan davranis olmayacak.
4. Sabit panel genisligi gerekiyorsa ham piksel cap yerine `scaled_cap` uygulanacak.
5. Yeni helper'lar ana menuyu bozmayacak; menu kendi runtime layout mantigiyla devam edebilir.
6. Ilk fazlarda global font sistemi degistirilmeyecek; lokal ekranlar ortak helper'a opt-in gecirilecek.
7. Bir faz icinde en fazla 1-2 ekran tasinacak; genis toplu migration yapilmayacak.
8. Draw ve input geometriği farkli matematiklerden beslenmeyecek.

### Kacinilacak yaklasimlar

- Her dosyaya baska bir scale helper yazmak
- Sadece font buyutup panel/padding sabit birakmak
- Sadece panel buyutup fontlari sabit birakmak
- Ekran ilk acildigindaki boyutu referans alarak buyume karari vermek
- Native display boyutunu aktif canvas yerine dogrudan buyume referansi yapmak
- UIFonts veya retro_style global scale'ini erken fazlarda topyekun buyutmek
- Settings, campaign ve gameplay overlay'lerini ayni fazda birlikte tasimak

## 8. Test ve Dogrulama Plani

### Faz cikis testleri

- Faz 1:
  - Yeni helper birim testleri
- Faz 2:
  - tests/test_extras_includes_classic.py
  - tests/test_campaign_level_panel_keyboard.py
- Faz 3:
  - hedefli manuel smoke test gerekli
- Faz 4:
  - hedefli manuel smoke test gerekli
- Faz 5:
  - tests/test_settings_fullscreen_restart_confirm.py
  - tests/test_settings_tabbed_inline_mode_playlist_editor.py
  - tests/test_ui_mouse_slider.py
- Faz 6-8:
  - ilgili hedefli pytest testleri + manuel oyun ici smoke test

### Manuel cozumunurluk matrisi

Asgari test:
- 1366x768
- 1600x900
- 1920x1080
- 2560x1440
- 3440x1440
- 3840x2160

Platform onceligi:
- Windows normal DPI / non-retina: birincil hedef
- macOS Retina: regresyon kontrolu

### Gozle kontrol edilecek ekranlar

- Extras
- Ayarlar
- Grafik Ayarlari
- Kilavuz
- Kullanici ekranlari
- Campaign level select
- Campaign level complete/fail popup
- Campaign yan bilgi panelleri

### Kontrol listesi

- Font boyutlari panel oranina uygun mu?
- Panel genisligi/yuksekligi ekran boslugunu mantikli kullaniyor mu?
- Scroll alanlari hala calisiyor mu?
- Uzun lokalizasyonlarda taskinlik oluyor mu?
- 16:9, 16:10 ve ultrawide oranlarda hizalama bozuluyor mu?

## 9. Riskler

### Risk 1: Asiri buyume
- Cozum: ekran yogunluguna gore `standard` ve `dense` profil ayirimi yap.

### Risk 2: Lokalizasyon taskinligi
- Cozum: fontlarda `get_fitting_font()` kullanimini koru ve satir/sutun alanlarini scale ile birlikte yeniden hesapla.

### Risk 3: Bir ekrani duzeltirken baska bir ekranin oranini bozmak
- Cozum: dalga dalga uygula; bir faz kapanmadan sonraki risk sinifina gecme.

### Risk 4: Mac Retina davranisini bozmak
- Cozum: ortak helper aktif canvas boyutundan hesap yapacak, ama macOS tarafinda manuel regresyon kontrolu yapilacak.

### Risk 5: Global font sistemi uzerinden tum oyunu istemeden buyutmek
- Cozum: erken fazlarda src/ui_theme.py ve src/retro_style.py icindeki global boyut/carpan mekaniklerine dokunma.

### Risk 6: Input rect ile cizim rect'inin ayrismasi
- Cozum: settings, guide ve user screens gibi ekranlarda draw ve input ayni rect helper'larindan beslenecek.

## 10. Onerilen Uygulama Sirasi

1. Faz 0: baseline ve emniyet kapilarini netlestir.
2. Faz 1: ortak ui_scaling helper'ini ekle, ama hicbir ekrani tasima.
3. Faz 2: extras_menu ve campaign/level_select ekranlarini tasi.
4. Faz 3: graphics_menu ve guide_screen ekranlarini ayri ayri tasi.
5. Faz 4: user_screens ekran ailesini tek basina tasi.
6. Faz 5: settings_screen_tabbed ekranini ayri bir risk fazi olarak ele al.
7. Faz 6: campaign_ui modal ailesini tasi.
8. Faz 7: campaign_mode yan panel/HUD ailesini tasi.
9. Faz 8: oyun ici popup ve mod overlay ailelerini son dalgada ele al.
10. Tum fazlardan sonra cozumunurluk matrisi ile manuel tur yap.

## 11. Basari Kriterleri

- Ana menu disindaki temel ekranlar 1440p ve 4K'da belirgin sekilde daha buyuk ve dengeli gorunmeli.
- Font, panel ve spacing ayni ekranda birbirinden kopuk olmamali.
- Ana menu ile diger ekranlar arasindaki olcek farki rahatsiz edici seviyeden cikmali.
- Windows non-retina sistemlerde kullanicinin tarif ettigi "1080 ustunde kucuk kaliyor" problemi cozulmeli.
- macOS Retina davranisinda gorunur regresyon olmamali.
- Settings ve user screens gibi input-yogun ekranlarda hitbox regresyonu olmamali.
- Campaign ve oyun ici overlay'lerde gameplay alani daralmamali.

## 12. Sonuc

Sorun tekil bir bug degil, parcali UI scaling mimarisinin bir sonucu. Bu nedenle tek dosyalik lokal yamalar yerine ortak helper + dalgali migration yaklasimi gerekli. En yuksek getirili ilk hamleler:
- ortak helper'i once davranis degisikligi olmadan eklemek,
- mevcut testi olan ve izole ekranlari once tasimak,
- settings ve gameplay overlay gibi yuksek blast-radius alanlari en sona birakmak,
- global font sistemine erken fazlarda dokunmamak.