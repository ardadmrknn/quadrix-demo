# Windows Display Scale Etki Envanteri ve Kapatma Refactor Plani

Tarih: 2026-04-26
Durum: Arastirma ve uygulama plani
Kapsam: Windows'taki ekran olcegi ayarinin oyun ici UI scale kararlarini etkiledigi ekran ailelerini tek tek cikarmak ve bu etkiyi kod tabaninda en temiz sekilde nasil kapatmak gerektigini tarif etmek

## 1. Kisa Sonuc

- Windows display scale etkisi bu projede tesadufi degil; platform katmanindan ortak ui_scaling katmanina, oradan da birden fazla ekran ailesine tasinmis durumda.
- Etkiyi tamamen kapatmanin en temiz yolu DPI awareness'i sokmek degil.
- En temiz yol, UI scale icin kullanilan boyut kaynagini merkezilestirmek ve Windows'ta "effective/logical size" yerine "raw display surface size" politikasina gecmektir.
- Bu refactor platform yardimcilarini silmeden yapilmali; aksi halde mouse/input/dpi dogrulugu ve gelecekteki platform ayrimlari gereksiz yere bozulur.

## 2. Bugunku Etkinin Kanit Zinciri

Windows olceginin UI'yi etkileme zinciri bugun su sekilde calisiyor:

1. src/main.py icinde \_init_windows_dpi_awareness() acilis sirasinda cagriliyor.
2. src/platform_utils.py icinde \_get_windows_window_scale_factor(), get_window_logical_size() ve get_effective_ui_size() aktif display surface icin DPI normalize boyut uretiyor.
3. src/ui_scaling.py icinde resolve_ui_scale_size(), get_effective_scale() ve get_projected_effective_scale() bu effective boyutu ortak scale girdisi olarak kullaniyor.
4. Menu, gameplay, campaign ve cesitli yardimci ekranlar bu wrapper'lari kendi \_ui_scale() veya panel/modal scale helper'larinda cagiriyor.
5. tests/test_platform_effective_ui_size.py bu davranisin bilincli ve testle kilitlenmis oldugunu gosteriyor.

Ozet:

- Windows scale etkisi tek bir dosyada degil.
- Bu etki platform -> ortak helper -> ekran wrapper'i zincirinde dagitilmis durumda.

## 3. Windows Display Scale'den Etkilenen Ekran Aileleri

Asagidaki liste, kodda dogrudan bu zincire baglanan ekran ailelerini tek tek ayirir.

### 3.1 Platform ve ortak helper ailesi

Bu aile ekrana cikmaz, ama tum etkinin kok girisidir.

- src/main.py
  - \_init_windows_dpi_awareness()
- src/platform_utils.py
  - \_get_windows_window_scale_factor()
  - get_window_logical_size()
  - get_effective_ui_size()
- src/ui_scaling.py
  - resolve_ui_scale_size()
  - get_effective_scale()
  - get_projected_effective_scale()

Not:

- Refactor'in merkez noktasi burasi olmalidir.
- Ekranlarda tek tek ham fallback yazmak yerine, once bu katmanda policy otoritesi kurulmalidir.

### 3.2 Ana menu ailesi

- src/menu.py
  - \_effective_ui_size()
  - \_ui_scale()
  - \_fullscreen_panel_scale()
  - \_menu_panel_content_scale()

Etki tipi:

- Ana menu okunabilirlik, panel boyutu ve kart icerigi Windows scale'e duyarli.
- Menu ailesi bu etkinin kullanici tarafinda en gorunur yuzlerinden biri.

### 3.3 Ana popup ve acilis panel ailesi

- src/main.py
  - \_fullscreen_popup_scale()

Etki tipi:

- Tam ekran popup/panel boyutlari projected effective scale zincirine bagli.
- Menu disi temel popup davranisini etkileyen ayri bir giris noktasi oldugu icin ayri takip edilmelidir.

### 3.4 Ana gameplay ailesi

- src/game.py
  - \_effective_ui_size()
  - \_ui_scale()
  - \_overlay_ui_scale()

Etki tipi:

- Oyun ici genel HUD, overlay ve panel olcek kararlarinin ana omurgasi burada.
- Diger gameplay turevlerinin bir kismi bu davranisi miras alir veya ayni kalibi tekrarlar.

### 3.5 Co-op gameplay ailesi

- src/coop_game.py
  - \_effective_ui_size()
  - \_ui_scale()

Etki tipi:

- Ortak board co-op ekraninda UI scale karari Windows effective-size zincirine bagli.

### 3.6 Yerel PvP ailesi

- src/pvp_game.py
  - \_ui_scale()

Etki tipi:

- PvP oturumu kendi UI wrapper'i ile projected effective scale kullaniyor.

### 3.7 Online PvP ailesi

- src/online_pvp_game.py
  - \_ui_scale()

Etki tipi:

- Online PvP ekranlari Windows scale'den etkileniyor.
- PvP ile ayni desen ama ayri dosya oldugu icin migrasyonda ayrica sayilmalidir.

### 3.8 Online Co-op ailesi

- src/online_coop_game.py
  - \_ui_scale()

Etki tipi:

- Online co-op UI scale'i de projected effective scale ile bagli.

### 3.9 Ayarlar ailesi

- src/settings_screen_tabbed.py
  - \_ui_scale()

Etki tipi:

- Tablar, satir yogunlugu, slider ve scrollbar geometri zinciri Windows scale etkisi tasiyor.
- Input geometri ve draw geometri beraber hareket ettigi icin yuksek blast-radius bolgelerden biri.

### 3.10 Grafik ayarlari ailesi

- src/graphics_menu.py
  - \_ui_scale()

Etki tipi:

- Grafik ayarlari kartlari ve satir/prompt boyutlari effective-size politikasina bagli.

### 3.11 Kilavuz ailesi

- src/guide_screen.py
  - \_ui_scale()

Etki tipi:

- Kilavuz paneli, kartlar ve sekme sunumu Windows scale'den etkileniyor.

### 3.12 Extras / oyun modlari menusu ailesi

- src/extras_menu.py
  - \_extras_ui_scale()

Etki tipi:

- Mod kartlari ve menu yogunlugu projected effective scale zincirine bagli.

### 3.13 Tutorial / modal yardim ailesi

- src/tutorial.py
  - \_tutorial_modal_scale()

Etki tipi:

- Tutorial modal ailesi Windows scale degisince boyut kararini degistiriyor.

### 3.14 Piece workshop ailesi

- src/piece_workshop.py
  - \_ui_scale()

Etki tipi:

- Workshop panelleri ve yazi olcegi bu zincire bagli.

### 3.15 Campaign level select ailesi

- src/campaign/level_select.py
  - \_get_ui_scale()

Etki tipi:

- Campaign level secim ekraninin kart, baslik ve liste yogunlugu Windows scale'e duyarli.

### 3.16 Co-op campaign level select ailesi

- src/campaign/coop_level_select.py
  - \_ui_scale()

Etki tipi:

- Co-op campaign level secimi de ayni projected effective scale yolunu kullaniyor.

### 3.17 Campaign gameplay HUD ailesi

- src/campaign/campaign_mode.py
  - \_get_campaign_hud_scale()

Etki tipi:

- Campaign HUD compact preset'ten ayrildi, ama hala effective-size zincirine bagli.
- Yani kullanici ayar preset etkisi kapandi; Windows display scale etkisi kapanmadi.

### 3.18 Mode overlay / mystery card overlay ailesi

- src/game_modes_extra.py
  - \_get_overlay_scale()
  - \_card_ui_scale()

Etki tipi:

- Kart secim overlay'i ve kart modu HUD/font olcegi projected effective scale kullaniyor.
- Bu aile gameplay turevinde oldugu icin ana Game migrasyonu bittikten sonra ayrica audit edilmelidir.

## 4. Ne Tam Olarak Kapatilmak Isteniyor

Hedef su olmali:

- Windows'taki OS display scale degissin veya degismesin, oyunun UI scale kararlari ayni raw display surface boyutundan turetilsin.

Hedef su olmamali:

- Windows DPI awareness'i tamamen silmek.
- Mouse normalize, pencere DPI sorgusu veya platform helper'larini yok etmek.
- macOS Retina logical-size davranisini kazara bozmak.

Bu ayrim onemli, cunku bugunku problem "platform helper var" degil; "genel UI scale kararlari varsayilan olarak bu helper'a baglanmis" olmasi.

## 5. En Temiz Refactor Yaklasimi

En temiz yol, platform helper'larini oldugu gibi birakip UI scale icin kullanilan boyut kaynagini merkezi bir policy ile secmektir.

Onerilen ana fikir:

- effective-size helper'lari var olmaya devam etsin
- ama ekran ailelerinin genel UI scale wrapper'lari Windows'ta artik effective-size degil raw-size kullansin
- bu secim ekran bazli daginik if/else ile degil, ortak bir policy katmani ile yapilsin

### 5.1 Ortak kavramlari yeniden adlandir

Bugun bircok yerde \_effective_ui_size() ismi, "UI scale icin kullanilan boyut" anlamina geliyor. Windows etkisi kapatilinca bu isim teknik olarak yaniltici hale gelir.

Refactor hedefi:

- \_effective_ui_size() yerine daha dogru isimli bir ara kavram getir
  - ornek: \_ui_scale_basis_size()
  - veya: \_ui_scale_size()

Bu degisiklik su dosyalarda ilk dalgada ele alinmali:

- src/menu.py
- src/game.py
- src/coop_game.py

Neden:

- Refactor sonrasinda helper artik her zaman effective olmayabilir.
- Isimlendirmeyi duzeltmeden politika degisikligi yapmak kodun niyetini bulaniklastirir.

### 5.2 ui_scaling katmanina acik bir size-basis policy ekle

Bugun resolve_ui_scale_size() ve get_projected_effective_scale() effective-size'i varsayilan secim gibi tasiyor.

Temiz cozum:

- src/ui_scaling.py icinde boyut kaynaginin acik secilebildigi genel bir API olustur
- effective ve raw yollarini ayni soyutlama altinda topla

Ornek yon:

- size_basis = raw_surface | effective_display
- veya policy = platform_default | raw_only | effective_only

Onemli nokta:

- get_projected_effective_scale() gibi mevcut helper'lar geriye donuk uyumluluk icin bir sure alias olarak kalabilir
- yeni ekran wrapper'lari ise genel policy tabanli API'ye tasinmalidir

Bu adim neden temizdir:

- platform helper'lar silinmez
- macOS icin gerekli gorulen logical-size yolu korunabilir
- Windows icin yalnizca UI scale karari kapatilir
- per-screen yamalar yerine ortak otorite olusur

### 5.3 Windows icin tek bir proje politikasi tanimla

Refactor hedefi "hangi helper cagirilsin" sorusunu her ekrana birakmamak olmali.

Onerilen politika:

- Windows: raw_surface
- macOS: mevcut karar korunacaksa effective_display kalabilir
- Linux: mevcut davranis ihtiyaca gore raw_surface veya mevcut default

Bu politika tek bir yerde durmali:

- tercihen src/ui_scaling.py icindeki ortak wrapper katmaninda
- ikinci tercih olarak src/platform_utils.py ile ui_scaling arasinda yeni bir policy helper'inda

Burada asil hedef su:

- ekran siniflari Windows mu, macOS mu diye bakmasin
- ekran siniflari sadece "ortak UI scale basis'ini getir" desin

### 5.4 Migrasyonu ekran ailelerine degil omurga wrapper'lara dayandir

Refactor sirasi tek tek butun ekranlara dağilarak baslamamali. Once omurga wrapper'lar tasinmali.

Ilk dalga:

- src/menu.py
- src/game.py
- src/coop_game.py
- src/main.py

Ikinci dalga:

- src/settings_screen_tabbed.py
- src/graphics_menu.py
- src/guide_screen.py
- src/extras_menu.py
- src/tutorial.py
- src/piece_workshop.py

Ucuncu dalga:

- src/campaign/level_select.py
- src/campaign/coop_level_select.py
- src/campaign/campaign_mode.py
- src/pvp_game.py
- src/online_pvp_game.py
- src/online_coop_game.py
- src/game_modes_extra.py

Neden bu sira:

- once ana omurgayi merkezde duzeltmek tekrar isi azaltir
- sonra izole menuler gecirilir
- en son gameplay/campaign/overlay kenar durumlari audit edilir

### 5.5 Platform helper'larini silme, rolunu daralt

src/platform_utils.py icindeki effective helper'lar tamamen kaldirilirsa iki risk cikar:

1. Testlerle kilitlenmis platform davranisi gereksiz yere bozulur.
2. Gelecekte belli ekranlarda effective-size tekrar gerekli olursa yol kapanir.

Bu yuzden en temiz refactor su olmali:

- get_effective_ui_size() kalsin
- get_window_logical_size() kalsin
- bunlar "opsiyonel platform bilgisi" olarak kalsin
- ama genel UI scale politikasinin varsayilani olmaktan ciksin

## 6. Neden Diger Cozumler Daha Kotu

### 6.1 DPI awareness'i kaldirmak neden kotu

- Bulanik render riski yaratir.
- Mouse/input koordinat davranisini etkileyebilir.
- Windows'un uygulamayi disaridan buyutmesine gecerek kontrolu oyundan cikarir.

### 6.2 get_projected_effective_scale() helper'ini global olarak degistirmek neden riskli

- macOS logical-size kullanan yollar kazara bozulabilir.
- Offscreen ve popup audit'lerinde daha once dikkat edilen ayrimlar tekrar karisabilir.
- Isim ayni kalirken davranis kokten degisirse kod okunurlugu duser.

### 6.3 Her ekranda ayri raw fallback yazmak neden kotu

- Drift uretir.
- Yeni ekranlar ayni hatayi tekrarlar.
- Bir sure sonra ayni karar 10 farkli helper'a dagilir.

## 7. Onerilen Uygulama Fazlari

### Faz 1 - Ortak policy katmanini ekle

Amac:

- UI scale icin boyut kaynagini tek yerden secmek.

Yapilacaklar:

- src/ui_scaling.py icinde size basis secimini destekleyen genel wrapper ekle.
- Effective ve raw yollarini ayni API altinda topla.
- Mevcut effective helper'lari uyumluluk alias'i olarak koru.

Tamamlanma kriteri:

- Yeni bir ekran wrapper'i platforma bakmadan tek policy cagrisi ile raw/effective secimi yapabilsin.

### Faz 2 - Omurga siniflarin helper adlarini duzelt

Amac:

- Effective olmayan bir davranisi effective diye adlandirmamayi garanti etmek.

Yapilacaklar:

- src/menu.py, src/game.py, src/coop_game.py icindeki ara size helper'larini yeni isimlere tasi.
- Bu helper'lar ortak policy katmanini cagirir hale gelsin.

Tamamlanma kriteri:

- Ana menu ve ana gameplay ailesi Windows'ta artik ortak raw policy'den besleniyor olsun.

### Faz 3 - Menu ve utility ekranlarini tasi

Amac:

- Windows scale etkisini kullanicinin sik gordugu ekranlardan kaldirmak.

Yapilacaklar:

- settings, graphics, guide, extras, tutorial, piece workshop ailelerini ortak policy'ye tasi.

Tamamlanma kriteri:

- Ayni raw surface boyutu altinda Windows scale 100, 125, 150 oldugunda bu ekranlarin \_ui_scale sonuclari degismiyor olsun.

### Faz 4 - Gameplay, campaign ve overlay kenar durumlarini tasi

Amac:

- Kampanya HUD ve mod overlay gibi son kalan bagimli yuzeyleri de ayni politikaya cekmek.

Yapilacaklar:

- game, coop, pvp, online, campaign, mystery overlay ailelerini audit et.
- apply_preset=False gibi mevcut davranislari koruyup sadece size basis kaynagini degistir.

Tamamlanma kriteri:

- Windows scale sadece platform bilgisi olarak kalir; gameplay scale kararini artik degistirmez.

## 8. Test ve Dogrulama Plani

Bu refactor kodlandiginda yalniz platform helper testleri yetmez. UI sonucunu da kilitlemek gerekir.

Onerilen test paketi:

1. tests/test_ui_scaling.py
   - raw basis ile effective basis ayri test edilmeli
   - Windows policy raw oldugunda scale sonucunun DPI factor'den bagimsiz oldugu kilitlenmeli

2. Menu/gameplay smoke testleri
   - src/menu.py \_ui_scale()
   - src/game.py \_ui_scale()
   - src/game.py \_overlay_ui_scale()
   - src/campaign/campaign_mode.py \_get_campaign_hud_scale()

3. Settings ve guide/regresyon testleri
   - settings_screen_tabbed
   - graphics_menu
   - guide_screen
   - extras_menu

4. Platform testleri korunmali
   - tests/test_platform_effective_ui_size.py helper davranisini test etmeye devam etmeli
   - fakat artik "genel UI bunu kullanir" varsayimi olmamali

En kritik yeni assertion sinifi:

- Ayni display surface boyutunda \_get_windows_window_scale_factor() 1.0 ve 1.5 oldugunda secili ekran wrapper'larinin dondurdugu UI scale ayni kalmali.

## 9. Son Tavsiye

Bu isin en temiz versiyonu su cizgidir:

- Windows DPI awareness kalsin
- platform effective-size helper'lari kalsin
- ama ekran ailelerinin genel UI scale kararlari ortak bir raw-surface policy'ye tasinsin

Bu cizgi, hem bugunku etkilenme zincirini tamamen kapatir hem de daha onceki high-density, popup, offscreen-surface ve gameplay overlay auditlerinde kazanilan ayrimlari gereksiz yere bozmaz.
