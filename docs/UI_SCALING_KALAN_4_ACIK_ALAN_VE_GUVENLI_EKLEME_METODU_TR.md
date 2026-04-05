# UI Scaling Kalan 4 Acik Alan ve Guvenli Ekleme Metodu

Tarih: 2026-04-05
Durum: Repo snapshot'ina gore acik kalan UI scaling alanlari ve dusuk riskli uygulama sirasi
Kapsam: Campaign popup/HUD, gameplay overlay ve popup kopru yuzeyleri

## ÖNEMLİ REF.

bu dosya incelenirken "plans\2026-03-09-non-main-menu-ui-scaling-plan.md" kaynak dosyası da incelenmelidir

## GUNCELLEME (2026-04-05 / Faz 6)

- `src/campaign/campaign_ui.py` icindeki campaign modal/popup ailesi ortak modal scale yardimcisina tasindi.
- Bu dokumandaki 4 acik alan siniflandirmasindan ilk lane kapanmistir.
- Aktif kalan acik alanlar artik sunlardir:
  1. Campaign yan panel/HUD ailesi
  2. Gameplay overlay ve mod panel ailesi
  3. Popup kopru ve tutorial/callout ailesi
- Regression kilidi olarak `tests/test_phase6_campaign_modal_ui_scaling.py` eklendi.
- Audit notu: campaign fail ekraninin aktif runtime cizimi `src/campaign/campaign_mode.py` icindeki game-over overlay zincirinden gelir; `src/campaign/campaign_ui.py` fail overlay'i uyumluluk/test yolu olarak kalir.

## 1. Amac

Bu notun amaci, ortak `ui_scaling` altyapisina henuz alinmamis alanlari tek yerde toplamak ve bu alanlari mevcut hassas duzeni en az bozacak sekilde nasil tasimamiz gerektigini netlestirmektir.

Ana ilke:

- global davranisi bir anda degistirmemek,
- mevcut draw/input geometrisini korumak,
- buyuk refactor yerine yerel wrapper ve kademeli donusum uygulamak,
- her dalgada tek bir UI ailesine dokunmak.

## 2. Neden 4 Acik Alan Olarak Ayiriyoruz

Ana plan dosyasinda teknik olarak acik kalan bolumler Faz 6-8 olarak gorunuyor. Ancak uygulama riski acisindan Faz 8'i tek parca ele almak fazla genis bir degisim alanina donusuyor.

Bu nedenle kalan is, uygulama guvenligi icin 4 ayri alana bolunmelidir:

1. Campaign modal/popup ailesi
2. Campaign yan panel/HUD ailesi
3. Gameplay overlay ve mod panel ailesi
4. Popup kopru ve tutorial/callout ailesi

Bu bolunme, mevcut davranisi korurken degisikligin etki alanini daraltir.

## 3. Ortak Koruma Kurallari

- Yeni global font sistemi yazilmayacak.
- Mevcut public helper isimleri korunacak; gerekiyorsa icleri ortak helper'a yonlendirilecek.
- Draw ve input geometrisi ayni scale kaynagindan beslenecek.
- Sabit cap degerleri bir anda kaldirilmeyecek; once `scaled_cap` mantigina alinacak.
- Bir dosyada ilk adim, mevcut referans davranisi silmek degil, ortak helper etrafina yerel adapter sarmalamak olacak.
- `max_scale=1.0` davranisi topluca kaldirilmayacak; sadece ilgili ekranin onceki okunabilirlik sinirlari korunarak tasinacak.
- Animasyon, fade, state machine ve input akisi ile ayni commit icinde gereksiz layout refactor yapilmayacak.

## 4. Acik Alan 1: Campaign Modal / Popup Ailesi

### Dosyalar

- `src/campaign/campaign_ui.py`

### Kapsam

- level complete paneli
- fail paneli
- bu panellerin header, footer, padding, font ve ic bloklari

### Mevcut risk

- Panel boyutlari ekran bazli buyuyor ama ic padding ve tipografi buyuk oranda sabit piksel.
- Ayni panel icinde panel rect ile font/padding farkli mantiklardan besleniyor.
- Bu aile, oyun loop'u ustunde ciziliyor; gorsel bozulma hemen fark edilir.

### Guvenli ekleme metodu

1. Dosya icine yeni global mantik degil, yerel bir `modal_scale` adapter'i eklenmeli.
2. Bu adapter ortak `get_modal_scale(...)` veya `get_scale(...)` ustunden calismali.
3. Ilk dalgada sadece su sinif metrikleri tasinmali:
   - panel width/height
   - panel padding
   - header/footer yukseklikleri
   - baslik, alt baslik ve footer fontlari
4. Panel ici mikro layout ilk adimda tamamen yeniden kurulmamali.
5. Mevcut animasyon offset'leri aynen korunmali; sadece sabit piksel sabitleri `s()` benzeri yardimciyla olceklenmeli.

### En az bozan teknik desen

- `campaign_ui.py` icinde yerel `ui_scale`/`s()` yardimcisi tanimla.
- Eski sabitleri dogrudan silme; once `s(32)`, `s(88)`, `s(40)` gibi adapter gecisi yap.
- `retro_style.get_font(...)` ve `_get_font(...)` cagrilarinda boyut hesaplarini ayni `s()` zincirine bagla.
- Basari ve fail panelini ayni commit'te tasirken ayni helper'i paylastir, ama iki panelin icerik akisini birlestirme.

### Ilk dogrulama kapisi

- 1366x768, 1920x1080, 2560x1440 ve 3840x2160 manuel popup smoke test
- baslik tasmasi, footer overlap'i, retry butonu ve metin merkezleme kontrolu

## 5. Acik Alan 2: Campaign Yan Panel / HUD Ailesi

### Dosyalar

- `src/campaign/campaign_mode.py`

### Kapsam

- sol campaign bilgi paneli
- sag HUD paneli
- alt bilgi alanlari
- objective, next, hold, stats bloklari

### Mevcut risk

- Panel genislikleri 340 px ve 220 px gibi sert cap'lere bagli.
- Board geometriğiyle komsu calisiyor; panelin buyumesi board tasmasi yaratabilir.
- Font, panel genisligi ve icerik araligi farkli kaynaklardan geliyor.

### Guvenli ekleme metodu

1. Panel anchor mantigi degistirilmemeli; sadece boyut metrikleri ortak scale kaynagina baglanmali.
2. Ilk adimda panelin `x/y` konum mantigi korunmali.
3. `panel_width = min(220, ...)` gibi sabit cap'ler direkt silinmemeli; once `min(s(220), ...)` benzeri `scaled_cap` modeline alinmali.
4. Fontlar topluca yeni sisteme gecirilmemeli; sadece panel basligi, alt baslik ve ana sayisal degerler ayni scale kaynagindan beslenmeli.
5. Board ile panel arasindaki bosluklar da ayni helper'a alinmali ki panel buyurken carpismasin.

### En az bozan teknik desen

- `campaign_mode.py` icinde yerel bir `_campaign_hud_scale()` veya mevcut helper icine ortak `get_content_scale(...)` baglantisi kur.
- Cagri noktalarini yeniden adlandirma; mevcut draw fonksiyonlari icinde `s()` adapter'i kullan.
- Sol panel ve sag panel ayni commit'te olabilir, ama objective/mode-info alt bloklari ikinci adimda ele alinmali.

### Ilk dogrulama kapisi

- boss ve mini-boss level HUD smoke test
- next/hold kutularinin kirpilmamasi
- objective text wrap ve stats alignment kontrolu

## 6. Acik Alan 3: Gameplay Overlay ve Mod Panel Ailesi

### Dosyalar

- `src/game.py`
- `src/game_modes.py`
- `src/game_modes_advanced.py`
- `src/game_modes_extra.py`

### Kapsam

- oyun ici sayac panelleri
- survival paneli
- kart secim overlay'leri
- mod bazli ek bilgi panelleri
- oyun ici secim / bilgi / workshop popup'lari

### Mevcut risk

- Farkli dosyalarda farkli shrink-only helper'lar var.
- Bazi yardimcilar buyumeyi 1.0'da kesiyor.
- Fazla sayida popup ve overlay ayni aileye bagli; tek hamlede degistirmek yuksek regresyon riski tasir.

### Guvenli ekleme metodu

1. Ilk hedef, tum cagri noktalarini degistirmek degil, mevcut helper'lari ortak `ui_scaling` uzerine yeniden baglamaktir.
2. `game.py` icindeki `_ui_scale()` yerel wrapper olarak korunmali ama hesabi ortak helper'a devredilmeli.
3. `game_modes.py`, `game_modes_advanced.py` ve `game_modes_extra.py` icindeki helper isimleri korunmali; sadece ic mantik ortak helper ile uyumlu hale getirilmeli.
4. Sabit popup boyutlari bir anda responsive yeniden yazilmamali; once `popup_width = s(500)` gibi kontrollu gecis uygulanmali.
5. Kart overlay ve sayac panelleri ayni dalgada olmamali; once ortak helper baglantisi, sonra popup sabitleri ele alinmali.

### En az bozan teknik desen

- Var olan `_counter_scale_from_base`, `_survival_panel_scale`, `_get_overlay_scale` gibi fonksiyonlari silme.
- Bu fonksiyonlari, ortak helper'a delegasyon yapan compatibility wrapper'a cevir.
- Cagri noktalarini buyuk toplu rename'den kacin.
- Her alt aile icin ayri test/smoke turu kullan:
  - sprint/ultra
  - survival
  - card/workshop overlay

### Ilk dogrulama kapisi

- sprint ve ultra panel okunabilirligi
- survival panel tasma kontrolu
- card workshop ve piece selection popup merkezleme ve input rect kontrolu

## 7. Acik Alan 4: Popup Kopru ve Tutorial / Callout Ailesi

### Dosyalar

- `src/main.py`
- `src/tutorial.py`

### Kapsam

- fullscreen intro/start popup zinciri
- zen start popup
- tutorial callout ve gecis panelleri

### Mevcut risk

- Bu yuzeyler bazen gameplay ile menu arasinda kopru gorevi goruyor.
- Buradaki geometri, sadece cizim degil, event rect ve akis baslatma mantigina da dokunuyor.
- Faz 8 ile ayni ailede gorunse de uygulama davranisi farkli oldugu icin ayri ele alinmali.

### Guvenli ekleme metodu

1. `main.py` icindeki `_fullscreen_popup_scale(...)` helper'i silinmemeli; ortak helper'a baglanan yerel compatibility wrapper olarak korunmali.
2. Popup panel hesaplarinda sadece boyut/padding/font zinciri ortak scale kaynagina alinmali.
3. Event rect ve state gecis mantigi aynen korunmali.
4. `tutorial.py` icinde mevcut `_sx(...)` kullanimlari korunabilir; ilk adimda sadece kaynak `ui_scale` hesaplamasi ortak helper ile hizalanmali.
5. Tutorial ekranlarinda metin wrap ve kart/callout rect mantigi ayni commit'te topluca refactor edilmemeli.

### En az bozan teknik desen

- Main popup helper'larini compatibility wrapper olarak tut.
- Tutorial tarafinda sadece scale kaynaginin merkezilesmesini yap; step state ve animation matematiklerini elleme.
- Bu aile en sona kalmali; once campaign ve gameplay panel aileleri stabilize edilmeli.

### Ilk dogrulama kapisi

- mode intro popup acilis testi
- zen popup secim/input testi
- tutorial callout metin tasmasi ve ilerleme kontrolu

## 8. Onerilen Uygulama Sirasi

En dusuk riskli sira su olmali:

1. Campaign modal/popup ailesi
2. Campaign yan panel/HUD ailesi
3. Gameplay overlay ve mod panel ailesi
4. Popup kopru ve tutorial/callout ailesi

Bu siranin nedeni:

- once oyun disi ama oyun ustu modal katmani stabil hale gelir,
- sonra board'a komsu campaign HUD ele alinir,
- sonra gameplay alt aileleri wrapper tabanli merkezilesir,
- en son akis koprusu ve tutorial gibi hassas event yuzeylerine gecilir.

## 9. Uygulama Sirasinda Kacinilacak Hatalar

- Faz 6-8'i tek PR/tek commit gibi buyuk bir blokta tasimak
- Eski helper isimlerini topluca silmek
- Board geometriğini ve panel geometriğini ayni anda yeniden kurmak
- Font sistemini global capta buyutmeye kalkmak
- Input rect ile draw rect'i farkli helper'lardan hesaplamak
- Manual smoke test yapmadan sadece unit test gecisini yeterli saymak

## 10. Pratik Karar Ozeti

Eger hedef en sorunsuz ilerleme ve mevcut hassas duzeni korumak ise, uygulanacak strateji su olmalidir:

- once adapter, sonra gercek migration,
- once local wrapper, sonra ic sabitlerin `s()` zincirine alinmasi,
- once tek aile, sonra sonraki aile,
- once geometri kaynagini merkezilestirme, sonra ince polish.

Bu notun amaci hizli gitmek degil, geri donus maliyeti dusuk bir sira kurmaktir.
