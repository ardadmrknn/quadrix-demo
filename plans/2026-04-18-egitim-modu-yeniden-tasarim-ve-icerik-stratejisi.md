# Egitim Modu Yeniden Tasarim ve Icerik Stratejisi

Tarih: 18 Nisan 2026

Durum: Yeni inceleme. Bu dokuman, mevcut kodu 18 Nisan 2026 itibariyla tekrar okuyarak hazirlanmistir. [plans/2026-03-10-egitim-modu-detayli-inceleme-ve-gelistirme-plani.md](2026-03-10-egitim-modu-detayli-inceleme-ve-gelistirme-plani.md) icindeki bircok stratejik yon dogrudur, ancak bugunku kod tabani artik farkli bir noktadadir: lesson katalogu, hub, scenario dersleri, kart secim dersleri ve tutorial progress sistemi zaten eklenmistir. Bu nedenle bugunku ana sorun "altyapi yok" degil; "altyapi var ama oyuncuya dogru sekilde ogretemiyor" sorunudur.

## 1. Bu Dokumanin Amaci

Bu dokumanin amaci sunlardir:

- Egitim modunun bugunku halini bastan asagiya analiz etmek.
- Neden oyuncularin ne yapacaklarini anlamadigini teknik ve UX nedenleriyle aciklamak.
- Egitim Merkezi ekraninin neden ana tema ile uyumsuz hissettirdigini somutlamak.
- Mevcut 13 derslik yapinin neden yetersiz kaldigini anlatmak.
- Egitim modunu yeni oyuncunun oyuna gercekten hazirlanacagi bir "ogretim sistemi"ne cevirecek yeni tasarim yonunu tarif etmek.
- Hangi dosyalarin degisecegini, hangilerinin korunacagini ve hangi risklerin gozetilecegini aciklamak.

Bu dokuman bir uygulama plani degildir. Bu dokuman, neyin degisecegini, neden degisecegini ve hedef sistemin nasil calismasi gerektigini tanimlar.

## 2. Mevcut Sistemin Tam Haritasi

### 2.1 Giris Noktalari

Bugun tutorial sistemine dort farkli kanaldan giriliyor:

1. Klasik tek oyunculu moda ilk kez giren kullanici icin popup daveti:
   [src/main.py](../src/main.py) icindeki _show_tutorial_prompt ve tek oyunculu mod giris akisi.
2. Ana menudeki Egitim kutusu:
   [src/menu.py](../src/menu.py) icindeki tutorial_mode dashboard karti.
3. Rehber ekranindan "ilgili dersi ac" koprusu:
   [src/guide_screen.py](../src/guide_screen.py) icindeki tutorial butonu akisi.
4. Rehber ekranindan dogrudan belirli bir dersi baslatma:
   [src/main.py](../src/main.py) icindeki tutorial_lesson: aksiyonlari.

Bu dagilim ilk bakista iyi gorunuyor. Sorun dagilimda degil, her giris kanalinin ayni ogretim kalitesini vermemesindedir.

### 2.2 Runtime Omurgasi

Bugunku tutorial omurgasi su dosyalara dagilmistir:

- [src/tutorial.py](../src/tutorial.py)
  Ana runtime sinifi, hub cizimi, overlay, result paneli, legacy step akisi, scenario ve card_choice akisi.
- [src/tutorial_lessons.py](../src/tutorial_lessons.py)
  Chapter ve lesson katalogu.
- [src/tutorial_scenarios.py](../src/tutorial_scenarios.py)
  Tahta senaryolari, board metric capture ve scenario evaluation mantigi.
- [src/tutorial_cards.py](../src/tutorial_cards.py)
  Kart secim dersleri, kontrollu kart katalogu, kart secimi sonucu degerlendirme mantigi.
- [src/tutorial_progress.py](../src/tutorial_progress.py)
  Progress shape, chapter unlock ve star hesaplama mantigi.
- [src/user_manager.py](../src/user_manager.py)
  Tutorial progress saklama, tutorial_completed bayragi ve lesson tamamlanma guncellemesi.

Bu ayri moduller teorik olarak saglam bir temel olusturuyor. Sorun, bu temelin uzerine kurulan deneyimin hala oyuncuya neyi neden yaptigini yeterince guclu anlatamamasi.

### 2.3 Mevcut Icerik Yapisi

Bugun 3 chapter ve toplam 13 lesson var.

#### Chapter 1: basics

- move_intro
- rotate_intro
- soft_drop_intro
- hard_drop_intro
- line_clear_intro
- hold_intro
- tutorial_complete

Bu chapter tamamen legacy step mantigi ile ilerliyor.

#### Chapter 2: board_basics

- board_gap_fill
- board_keep_low
- board_vertical_well

Bu chapter kontrollu tahta senaryolari kullaniyor.

#### Chapter 3: card_academy

- card_rescue_pick
- card_long_term_pick
- card_synergy_pick

Bu chapter kontrollu kart secim overlay kullaniyor.

Bu yapi, mart ayindaki eski tutorialdan cok daha iyi bir noktadir. Ancak halen "oyunu ogretme" yerine daha cok "bir kac ilkeyi gosteren mini laboratuvarlar" duzeyindedir.

### 2.4 Progress ve Kilit Sistemi

Bugun progress sistemi chapter bazli tutuluyor:

- lesson tamamlanma
- lesson yildiz sayisi
- chapter tamamlanma
- chapter unlock

Bu sistem [src/tutorial_progress.py](../src/tutorial_progress.py) icinde mevcut ve calisir durumda.

Fakat iki kritik urun kusuru var:

1. Bir chapter tamamlaninca sonraki chapter aciliyor.
   Bu mantik teknik olarak dogru ama ogrencinin hangi beceriyi kazandigi, niye yeni chapterin acildigi veya ne ogrenecegi UI tarafinda neredeyse hic anlatilmiyor.
2. Skip akisi progress verisini bozuyor.
   [src/main.py](../src/main.py) icinde tutorial popup atlandiginda user_manager.set_tutorial_completed(True) cagriliyor.
   [src/user_manager.py](../src/user_manager.py) icindeki set_tutorial_completed(True) ise basics chapterini sanki oynanmis gibi tamamlanmis isaretliyor ve yildiz veriyor.

Bu cok onemli bir sorundur. Oyuncu tutoriali oynamadan geciyor ama sistem onu tutorial tamamlanmis kabul ediyor. Bu su problemlere yol aciyor:

- Oyuncu bir daha dogru zamanda yeniden egitime davet edilmiyor.
- Progress tablosu gercegi yansitmiyor.
- Sonraki chapter kilitleri sahte sekilde acilabiliyor.
- Egitim Merkezi, ogrencinin gercek ihtiyacini gostermek yerine "tamamlandi" yalanini gosterebiliyor.

Bu bugun tutorial sistemindeki en ciddi urun problemi olarak ele alinmalidir.

### 2.5 Mevcut Test Kapsami

Tutorial tarafinda test var ama odagi dar.

Ana tutorial test dosyasi:

- [tests/test_phase8_tutorial_ui_scaling.py](../tests/test_phase8_tutorial_ui_scaling.py)

Bu testler sunlari iyi kapsiyor:

- aktif canvas olcek hesaplari
- hub rectlerinin ekran disina tasmamasi
- overlay ve lesson result panelinin active surface sinirlarini asmamasi
- card overlay baseline referansi

Ama sunlari test etmiyor:

- skip akisinin progress bozmasi
- tutorial popup seciminin kullanici davranisina etkisi
- derslerin ogreticilik kalitesi
- failure feedback mantiginin anlamli olup olmadigi
- guide ekranindan acilan lessonin dogru geri donus akisi
- hub icinde artan ders sayisinda scroll, yogunluk ve okunabilirlik
- localization copy kalitesi ve metin hiyerarsisi

Yani bugunku test paketi tutoriali "ekranda tasmadan ciz" seviyesinde koruyor; "oyuncuya bir sey ogretiyor mu" seviyesinde korumuyor.

## 3. Bugunku Sistemdeki Ana Sorunlar

## 3.1 Onboarding Sorunlari

### 3.1.1 Ilk davet popupi zayif

[src/main.py](../src/main.py) icindeki ilk popup iki butonlu bir soru gibi calisiyor:

- Atla
- Egitimi Oyna

Bu popup su seyleri anlatmiyor:

- Bu egitim ne kadar surer?
- Oyuncuya ne kazandirir?
- Hangi oyunu anlamayi kolaylastirir?
- Ilk once kisa hizli egitim mi, yoksa tam akademi mi oneriliyor?

Popup, oyuncuya fayda yerine karar yuku bindiriyor. Oyuncu okumayi sevmiyorsa dogal olarak skip ediyor.

### 3.1.2 Skip, "tamamlandi" gibi davraniyor

Bu zaten yukarida anlatilan kritik urun hatasidir.

Dogru davranis su olmaliydi:

- skip = henuz tamamlanmadi
- skip = oyuncu daha sonra geri donebilir
- skip = ana menu ve single player girislerinde belli bir sure daha nazik sekilde tekrar hatirlatilabilir

Bugunku davranis ise sunu yapiyor:

- skip = tamamlandi say
- basics tamamlandi kabul et
- bir daha sorma

Bu egitimin varlik sebebine aykiridir.

### 3.1.3 Guide ekranindan giris baglami kopuk

[src/guide_screen.py](../src/guide_screen.py) icinden belirli tutorial lessonlar acilabiliyor.

Bu kopru iyi bir fikir. Ancak bugunku akista su eksikler var:

- Kullanici chapter veya lesson briefing gormeden dogrudan runtime icine atiliyor.
- launch_lesson_id ile acilan tutorial session, hub_return_enabled bayragi nedeniyle huba degil menuye donebiliyor.
- Rehberden geldiyse rehbere, hubdan geldiyse huba, ilk popupdan geldiyse hizli egitime donmesi gereken akillar bugun ayrismamis durumda.

Yani tutoriala giris kaynaklari var ama bu kaynaklara uygun farkli donus senaryolari yok.

## 3.2 Egitim Merkezi UI Sorunlari

Kullanici ekran goruntusunde gordugu Egitim Merkezi paneli teknik olarak duzgun ciziliyor ama urun olarak zayif kaliyor.

### 3.2.1 Ana tema ile gorsel akrabaligi zayif

Ana menudeki tutorial karti [src/menu.py](../src/menu.py) icinde ozel ana tema flavor varligi ile ciziliyor.
Bu kartta su seyler bulunuyor:

- ozel sticker/illustration katmani
- dashboard kart diline uygun parlama ve derinlik
- daha guclu baslik-kutu hiyerarsisi

Egitim Merkezi hub ise [src/tutorial.py](../src/tutorial.py) icinde tamamen generic glass panel katmanlari ile ciziliyor.

Sonuc:

- Ana menude premium gorunen egitim girisi,
- hub ekraninda bir anda sade, soguk ve eski nesil bir modal gibi duruyor.

Yani tema ayni oyun evrenine ait hissettirmiyor.

### 3.2.2 Modal mantigi cok agir, bilgi mimarisi cok zayif

Bugunku hub tek buyuk panel ve onun icinde iki alt panel kullaniyor:

- solda chapter listesi
- sagda lesson listesi

Bu su nedenlerle zayif:

- soldaki chapter kartlari ile sagdaki lesson satirlari ayni gorsel agirlikta degil
- sag panelde secili lesson icin genis bir detay alani yok
- "neden bu dersi oynamaliyim" sorusuna cevap yok
- sure, zorluk, ogretecegi beceri, hata tuzaklari gibi meta bilgiler yok
- CTA butonu lesson iceriginin parcasiyla butunlesmiyor

Kisacasi bu ekran "course catalog" gibi degil, "sol panelden sec sag panelden tikla" tipinde bir admin listesi gibi hissettiriyor.

### 3.2.3 Yogunluk hizli artiyor, scroll yok

Bugun basics chapterinda 7 lesson var ve liste paneli bunu minimum boy kartlarla sigdirmaya calisiyor.

Sorunlar:

- Kartlar sikisiyor.
- Aciklama satirlari kisaliyor.
- Alt kontroller mikrolasiyor.
- Ileride 12-15 derslik chapter geldigi anda ekran kacamaz hale gelecek.

Mevcut hub tasarimi buyumeye uygun degildir.

### 3.2.4 On-screen yonlendirme okunmuyor

Kullanici yorumundaki "solda ipucu var ama okumuyorlar" tespiti cok dogru. Problem sadece kullanici davranisi degil; sistem okutturacak kadar guclu tasarlanmamis.

Bugunki durum:

- kontrol ipuclari kucuk bir satir olarak altta yer aliyor
- lesson hedefleri secilen satirin yaninda sistematik olarak gosterilmiyor
- board derslerinde hedef listesi gameplay ekraninda ikinci bir panelde ciksa da derse girmeden once okunacak briefing yok
- kart derslerinde baglam metni var ama secim baskisi altinda oyuncu direkt karta bakiyor

Yani metin var ama akisin dogal odak noktasinda degil.

## 3.3 Pedagoji Sorunlari

### 3.3.1 Mevcut lessonlar daha cok input ogretiyor

Legacy step tarafi sunlari ogretiyor:

- saga git
- sola git
- rotate yap
- soft drop tut
- hard drop kullan
- hold kullan

Bunlar gerekli ama yeterli degil. Oyuncu tutorial bitince sunlari hala bilmiyor olabilir:

- neden yuzeyi duz tutmak gerekir
- neden bazen satir temizlememek daha iyi olabilir
- hold sadece "parca sakla" degil, ne zaman kullanilan bir plan aracidir
- next queue neden onemlidir
- oyunda risk, tempo ve guvenlik nasil dengelenir

Bugunku tutorial, tus ogretiyor; dusunce modeli ogretmiyor.

### 3.3.2 Board scenario degerlendirmesi fazla kaba

[src/tutorial_scenarios.py](../src/tutorial_scenarios.py) bugun scenario sonucunu temelde uc metric ile degerlendiriyor:

- line_delta
- hole_delta
- height_delta

Bu iyi bir baslangic ama pedagojik olarak eksik.

Eksik kalan seyler:

- oyuncu dogru kuyuya mi oynadi, yoksa sadece sans eseri mi gecti
- gereksiz yan etki yaratti mi
- hold kullanmali miydi
- next queue avantajini kullandi mi
- ideal yerlesimle kendi yerlesimi arasindaki fark neydi

Bu nedenle ders sonucu ekrani bazen "gectin ama neden gectin" veya "kaldin ama aslinda neyi kacirdin" seviyesinde zayif kaliyor.

### 3.3.3 Kart dersleri bilgi veriyor ama tam ogretmiyor

[src/tutorial_cards.py](../src/tutorial_cards.py) icindeki kart secim dersleri sunlari iyi yapiyor:

- kontrollu kart havuzu
- recommended ve acceptable secimler
- secim sonrasi kisa aciklama

Ama sunlari yapmiyor:

- secilen kartin tahtayi nasil etkileyebilecegini gostermiyor
- dogru kart ile yanlis karti yan yana karsilastirmiyor
- kart etkisini run perspektifine baglamiyor
- kart ailelerini sistematik bicimde ogretmiyor

Yani oyuncu "dogru kart buydu" bilgisini goruyor ama "neden bundan sonra da benzer durumlarda bu dogru olacak" ilkesini tam kuramiyor.

### 3.3.4 Failure feedback dar ve bazen gecikmeli

Board scenario sonuc ekrani objective ve coach text gosteriyor. Bu iyi. Ama yetmiyor.

Eksikler:

- oyunun icindeyken daha erken uyari yok
- ayni hatayi ust uste yapiyorsa daha sertlestirilmis ipucu yok
- lesson icindeki fail state ile sonuclar arasinda bazen kopukluk var

Ornek:

- line_clear_intro basarisiz oldugunda senaryo resetleniyor ama neden olmadi pek anlatilmiyor
- scenario dersinde ancak piece lock sonrasi sonuc geliyor; o ana kadar oyuncu hatali yola girdigini anlamayabiliyor

### 3.3.5 Gorunmesi planlanan mikro feedbacklerin bir kismi cizilmiyor

[src/tutorial.py](../src/tutorial.py) icinde _create_mini_success_effect, progress_celebration_text ve iliskili state var.
Fakat _draw_mini_success_effects ve _draw_progress_celebration bugun bos donuyor.

Bu cok onemli bir UX borcudur cunku:

- runtime state, oyuncuya gostermesi gereken mikro odulleri uretiyor
- draw katmani bunlari gercekten gostermiyor

Sonuc olarak tutorial runtime icinde "iyi bir sey yaptin" hissini guclendirecek ara katman kismen bogulmus durumda.

### 3.3.6 Soft drop dersi minik ama gercek bir davranis kusuru tasiyor

[src/tutorial.py](../src/tutorial.py) icinde soft drop hedefi 40 frame olarak kuruluyor ama tamamlama kosulu soft_drop_counter > step_target ile kontrol ediliyor.

Bu, hedef 40 iken teknik olarak 41 frame beklemek anlamina geliyor.

Bu buyuk bir bug degil ama iki acidan onemlidir:

- tutorialdaki en kisa davranislar bile tam olarak güven verici hissettirmeli
- tutorial sistemindeki "hedef gostergesi" ile gercek tamamlama kosulu birebir uyusmali

## 4. Gorsel Inceleme: Neden Egitim Merkezi Kotu Gorunuyor?

Kullanici ekran goruntusundeki sorunlar soyut degil, somut:

- Panel cok buyuk ama bilgi hiyerarsisi zayif.
- Kenarlik sayisi fazla, gorsel odak sayisi fazla, anlamli vurgu az.
- Sol chapter alaninda kutular birbirine benziyor ama her birinin karakteri yok.
- Sag lesson alaninda secili ders ile secili olmayan ders arasinda yeterli bilgi farki yok.
- Basla butonu mekanik olarak altta ama duygusal olarak secili lesson ile bag kurmuyor.
- Alt kontrol aciklamasi okunmayacak kadar pasif duruyor.
- Ekranin bosluklari tasarimli degil; sadece bos.
- Ana menudeki tutorial kartinin parlak, ozel ve premium dili burada devam etmiyor.

Bu nedenle ekran "oyuncuyu egitime davet eden akademi paneli" degil, "oyunun icinde acilan gecici ayar menusu" gibi duruyor.

## 5. Yeni Sistemin Tasarim Ilkeleri

Yeni tutorial sistemi su ilkelere gore kurulmalidir:

### 5.1 Ilke: Oku degil, yap ve gor

Oyuncu uzun metin okumak istemiyorsa sistem buna kirilmamali.
Onun yerine:

- hedefi buyuk ve net goster
- dikkat edilmesi gereken yeri isiklandir
- yanlis hareket oldugunda hemen nedenini soyle
- dogru hareket oldugunda mikro odul ver

### 5.2 Ilke: Lesson baslamadan baglam ver

Her dersin once 5-10 saniyelik briefing alani olmalidir:

- Bu ders ne ogretecek?
- Neden onemli?
- Basari ne demek?
- Hangi hatalara dikkat etmeliyim?

### 5.3 Ilke: Tus degil karar ogret

Egitimin hedefi "UP rotate yapar" seviyesinde kalmamali.
Hedef su olmali:

- burada rotate yapmak neden mantikli
- burada hold niye daha degerli
- burada satir temizlememek neden daha iyi
- burada legendary kart neden yanlis secim

### 5.4 Ilke: Tema birligi kur

Ana menudeki tutorial karti ile Egitim Merkezi ayni aileden hissettirmeli.

Bu nedenle yeni hub:

- ana menu tutorial kartindaki renk ve flavor dilini devralmali
- generic cam panel yiginindan cikmali
- chapterlari siradan liste degil, karakteri olan akademi kartlari gibi gostermeli
- secili lesson icin buyuk bir detay paneli vermeli

### 5.5 Ilke: Dersi bitirmek ile ustalasmak ayri seylerdir

Her lesson icin en az iki seviye olmali:

- tamamlandi
- temiz/ustaca tamamlandi

Bu sayede tutorial sadece gecilen degil, tekrar ziyaret edilen bir sisteme donusebilir.

## 6. Onerilen Yeni Kullanim Akisi

## 6.1 Ilk Acilis Akisi

Bugunku soru popupi yerine su akisa gecilmeli:

1. Kisa davet paneli:
   "90 saniyelik hizli baslangicla oyunun mantigini ogren"
2. Uc secenek:
   - Hizli Baslangic
   - Akademiyi Ac
   - Simdilik Gec
3. Simdilik Gec secenegi progressi tamamlanmis yapmamalidir.
4. Oyuncu single playerda ilk 1-2 oyununda cok erken kaybediyorsa nazik bir tekrar davet tetiklenebilir.

## 6.2 Yeni Egitim Merkezi Akisi

Yeni hub su katmanlarla calismalidir:

### Ust Hero Alan

- Chapter veya secili path icin guclu bir baslik
- Kisa tek satir vaad
- Toplam ilerleme
- Son oynanan ders veya onerilen bir sonraki ders CTA'si

### Sol Akademi Rayi

- Chapterlar sirali ama daha buyuk kimlik kartlari halinde
- Her chapter icin ikon, zorluk, sure, beceri etiketi
- Kilitli chapterda sadece kilit degil, acilis kosulu yazilmali

### Orta Secili Lesson Karti

- lesson basligi
- ne ogretecek
- neden onemli
- tahmini sure
- zorluk
- ogrenecegin beceriler
- basari kriterleri
- ideal hata listesi
- baslat butonu

### Sag Yardimci Alan

- mini video/gif yoksa bile statik tahta diyagrami
- bu derste gorecegin tahta problemi
- bu problem oyunun hangi modlarinda onune cikar

### Alt Alan

- geri butonu
- resume/continue butonu
- son lesson sonucu veya rozetler

Boylece oyuncu bir satir liste secmiyor; bir dersi satin alip baslatir gibi hissediyor.

## 6.3 Lesson Runtime Akisi

Her lesson runtimei 4 asamaya ayrilmalidir:

1. Briefing
2. Guided play
3. Result review
4. Follow-up recommendation

### Briefing

- 1 ana hedef
- 2 ikincil hedef
- neye bakman gerekiyor
- hangi tuzaktan kacin

### Guided play

- canli objective chips
- gerekli oldugunda board uzerinde highlight
- belli sure bosta kalirsa artan siddette ipucu
- ayni hatada ayni copy degil, giderek somutlasan copy

### Result review

- hedef gecti/gecmedi
- hangi davranis iyi yapildi
- hangi davranis zayifti
- ideal hamleye gore fark

### Follow-up recommendation

- tekrar dene
- sonraki derse gec
- ilgili rehber bolumunu ac
- benzer mini challenge dene

## 7. Onerilen Yeni Icerik Mimarisi

Mevcut 3 chapter yapisi bir temel olarak korunabilir ama genisletilmelidir.

Bu kez sadece ornek chapter isimleri vermek yeterli degil. Bundan sonraki uygulama tartismalarinda herkesin ayni seyi kastetmesi icin kanonik hedef katalog acik tanimlanmali.

## 7.1 Kanonik V2 Ogretim Omurgasi

Asagidaki yapi bu dokumanda referans alinan nihai hedef katalogdur.

| Sira | Chapter ID | Ekran Adi | Hedef | Kanonik Lesson Sayisi |
| --- | --- | --- | --- | --- |
| A | quick_start | Hizli Baslangic | Yeni oyuncuya 90 saniyede oynanabilir minimum yetkinlik vermek | 5 |
| B | surface_control | Yuzey Kontrolu | Temiz yuzey, delik onleme, kuyu koruma mantigini oturtmak | 4 |
| C | queue_hold | Queue ve Hold | Gelecek planlama ve hold karar mantigini ogretmek | 4 |
| D | recovery | Kurtarma ve Hayatta Kalma | Kotu board altinda sakin ve dogru onceliklerle oynamayi ogretmek | 4 |
| E | card_foundations | Kart Temelleri | Kart ailelerini, risk etiketlerini ve board baglamini tanitmak | 4 |
| F | card_strategy | Kart Stratejisi ve Sinerji | Uzun vadeli build mantigi ve risk-getiri dengesini ogretmek | 4 |
| G | mastery_exams | Sinavlar ve Ustalik Gorevleri | Ogrenilen ilkeleri daha az ipucuyla birlestirmek | 3 |

Toplam hedef katalog 28 lesson'dan olusur. Bu sayi ilk gunde tek parca olarak ship edilmek zorunda degildir. Ama tasarim ve kod mimarisi bugunden itibaren bu katalogu tasiyabilecek sekilde kurulmalidir.

## 7.2 Mevcut 13 Lesson'dan Yeni Kataloga Gecis Haritasi

Bugunku lessonlar cope atilmayacak; yeni katalog icinde daha dogru yerlere dagitilacaktir.

| Mevcut Lesson | Yeni Hedef Lesson / Akis | Not |
| --- | --- | --- |
| move_intro | qs_move_lane | Davranis korunur, copy ve HUD guclenir |
| rotate_intro | qs_rotate_fit | Dar boslugu gorme baglami eklenir |
| soft_drop_intro | qs_soft_drop_control | Hedef kosulu dogrulanir |
| hard_drop_intro | qs_safe_hard_drop | Guvenli kilitleme mantigi eklenir |
| line_clear_intro | qs_first_clear | Ilk temiz yerlesim dersi olarak korunur |
| hold_intro | plan_hold_save | Temel kontrolden cikarilip plan chapterina tasinir |
| tutorial_complete | quick_start_outro | Ayrik lesson degil, hizli baslangic bitis akisi olur |
| board_gap_fill | surface_gap_fill | Korunur ve briefing eklenir |
| board_keep_low | surface_keep_low | Korunur ve daha zengin feedback alir |
| board_vertical_well | surface_protect_well | Korunur ve kuyu mantigi daha acik anlatilir |
| card_rescue_pick | cards_rescue_now | Korunur ve kart ailesi semantigi eklenir |
| card_long_term_pick | cards_long_term_value | Korunur ve perk vs anlik etki ayrimi netlesir |
| card_synergy_pick | cards_synergy_scale | Korunur ve build baglami buyutulur |

Bu tablo onemlidir cunku yeni sistem sifirdan yazilan farkli bir tutorial degil; mevcut dersleri daha dogru chapter, metadata ve feedback katmanlarina dagitan bir yeniden yapilandirmadir.

## 7.3 Kanonik Chapter ve Lesson Listesi

Asagidaki liste artik "ornek lesson" degil, plan boyunca kullanilacak kanonik hedef listedir.

### Chapter A: Hizli Baslangic

Amac:

- oyuna yeni giren oyuncunun paniğe kapilmadan ilk boardu oynayabilecek minimum kas + zihin koordinasyonunu almasi

Kanonik lesson listesi:

1. qs_move_lane
   Tip: Drill
   Ogretir: saga-sola kaydirmanin panic tepkisi degil, yer acma hareketi oldugunu
   Gecis kaniti: parca iki yone de kontrollu tasinir
2. qs_rotate_fit
   Tip: Drill
   Ogretir: rotate'in sadece tus degil, bosluk okuma karari oldugunu
   Gecis kaniti: dar oyuga dogru donus yapilir
3. qs_soft_drop_control
   Tip: Drill
   Ogretir: parca kilitlemeden gozle kontrol ederek indirmeyi
   Gecis kaniti: soft drop hedef suresi temiz tamamlanir
4. qs_safe_hard_drop
   Tip: Drill
   Ogretir: board okunmusken sert dusurmenin guvenli karar oldugunu
   Gecis kaniti: oyuncu dogru lane'e alip tek hamlede kilitler
5. qs_first_clear
   Tip: Board Puzzle
   Ogretir: ilk satir temizliginde acele degil, temiz yerlesim onceligini
   Gecis kaniti: ilk temizleme delik acmadan yapilir

### Chapter B: Yuzey Kontrolu

Amac:

- yuzeyi duz tutma, delik acmama ve kuyu koruma gibi Tetris okuryazarliginin temelini atmak

Kanonik lesson listesi:

1. surface_gap_fill
   Tip: Board Puzzle
   Ogretir: genis boslugu dogru parcayla kapatip iki satiri temizlemeyi
2. surface_keep_low
   Tip: Board Puzzle
   Ogretir: her hamlede satir temizlemeden de boardu saglikli tutmayi
3. surface_avoid_holes
   Tip: Compare Choice
   Ogretir: kisa vadeli rahatlik icin delik acmanin neden kotu oldugunu
4. surface_protect_well
   Tip: Board Puzzle
   Ogretir: hazir kuyuyu sabirla koruyup buyuk temizlige cevirmeyi

### Chapter C: Queue ve Hold

Amac:

- sadece aktif parcayi degil, sonraki iki parcayi ve holdu da karar uzayina katmayi ogretmek

Kanonik lesson listesi:

1. plan_hold_save
   Tip: Drill
   Ogretir: holdu panik butonu degil, uygun parcayi saklama araci olarak kullanmayi
2. plan_queue_read
   Tip: Compare Choice
   Ogretir: bir sonraki parcaya gore bugunku lane kararini vermeyi
3. plan_hold_vs_place
   Tip: Compare Choice
   Ogretir: bu parcayi simdi koymak mi yoksa holda atmak mi daha degerli sorusunu
4. plan_two_step_setup
   Tip: Board Puzzle
   Ogretir: tek hamle degil iki hamlelik kurulum yapmayi

### Chapter D: Kurtarma ve Hayatta Kalma

Amac:

- kotu board altinda skor hirsini birakip hayatta kalma onceligine gecmeyi ogretmek

Kanonik lesson listesi:

1. recover_make_breathing_room
   Tip: Repair Challenge
   Ogretir: once nefes aldiran alan acmayi
2. recover_hole_or_height
   Tip: Compare Choice
   Ogretir: delik kapatma ile tepe dusurme arasinda oncelik belirlemeyi
3. recover_reduce_ceiling
   Tip: Repair Challenge
   Ogretir: tavan baskisinda guvenli taraf ve hiz kontrolunu
4. recover_wrong_side_escape
   Tip: Repair Challenge
   Ogretir: yanlis tarafa yigilmis boarddan kontrollu cikisi

### Chapter E: Kart Temelleri

Amac:

- kartlari sadece aciklamasi olan objeler olarak degil, board sorunlarina verilen farkli cevaplar olarak ogretmek

Kanonik lesson listesi:

1. cards_rescue_now
   Tip: Card Lab
   Ogretir: riskli boardda kurtarma kartinin neden tempo kartindan once geldigini
2. cards_tempo_trap
   Tip: Card Lab
   Ogretir: board kotuyken hiz ve skor kartlarinin neden tuzak olabilecegini
3. cards_perk_vs_instant
   Tip: Card Lab
   Ogretir: kalici perk ile anlik spell arasindaki zaman ufku farkini
4. cards_long_term_value
   Tip: Card Lab
   Ogretir: guvenli boardda uzun vadeli deger secmeyi

### Chapter F: Kart Stratejisi ve Sinerji

Amac:

- tek kart gucu yerine build omurgasi, perk zinciri ve risk-getiri penceresi okumayi ogretmek

Kanonik lesson listesi:

1. cards_synergy_scale
   Tip: Card Lab
   Ogretir: aktif perklerle uyumlu kart secimini
2. cards_rare_not_auto_pick
   Tip: Card Lab
   Ogretir: nadir kartin her zaman dogru kart olmadigini
3. cards_build_direction
   Tip: Compare Choice
   Ogretir: mevcut run'in nereye gittigine gore kart secmeyi
4. cards_risk_reward_timing
   Tip: Card Lab
   Ogretir: tempo acma penceresini ne zaman zorlaman gerektigini

### Chapter G: Sinavlar ve Ustalik Gorevleri

Amac:

- daha az yardimla birden fazla ilkeyi ayni anda kullanmayi zorunlu kilmak

Kanonik lesson listesi:

1. exam_board_midterm
   Tip: Exam
   Ogretir: yuzey, delik ve kuyu kararlarini tek senaryoda birlestirmeyi
2. exam_plan_midterm
   Tip: Exam
   Ogretir: queue, hold ve risk azaltma kararlarini ayni senaryoda kullanmayi
3. exam_hybrid_final
   Tip: Exam
   Ogretir: board + kart + zamanlama + geri bildirim ogrenisinin final sentezini

## 7.4 Ship Edilecek Ilk Ders Halkasi ve Sonraki Dalga

Bu katalog tek gecede ship edilmeyecegi icin ilk uygulama dalgasi da acik olmali.

Ilk ship halkasi:

- Chapter A: 5 lesson
- Chapter B: 4 lesson
- Chapter C: 4 lesson
- Chapter D: 4 lesson

Ikinci dalga:

- Chapter E: 4 lesson
- Chapter F: 4 lesson

Ucuncu dalga:

- Chapter G: 3 lesson

Bu ayrim sunu saglar:

- once board ve planlama omurgasi oturur
- sonra kart akademisi o omurga uzerine kurulur
- en son sinavlar gelir

## 7.5 Naming, Metadata ve Localization Kurali

Yeni lesson listesi buyudugu icin isimlendirme standardi zorunludur.

Kural:

- quick start lessonlari qs_ ile baslar
- yuzey lessonlari surface_ ile baslar
- planning lessonlari plan_ ile baslar
- recovery lessonlari recover_ ile baslar
- kart lessonlari cards_ ile baslar
- sinav lessonlari exam_ ile baslar

Bu standart sadece okunurluk icin degil, su sebeplerle kritik onemdedir:

- tutorial_lessons.py icinde katalog taramasi kolaylasir
- localization keyleri ile lesson id'ler arasinda duzen kurulur
- progress migration ve recommendation engine daha az string karmaşasi ile calisir
- rehberden tutoriala derin link verilirken kategori belli olur

## 8. Onerilen Lesson Tipleri

Yeni sistemde tum lessonlar ayni turde olmamali.

### 8.1 Drill

Kisa motor beceri dersi.
Ornek: rotate, hard drop, hold.

### 8.2 Board Puzzle

Kontrollu tahta, kontrollu parca, net hedef.
Ornek: deliği kapat, kuyu koru.

### 8.3 Compare Choice

Iki veya uc secenek arasindan dogru stratejiyi sec.
Ornek: hangi yere koyarsan daha temiz kalir.

### 8.4 Card Lab

Kart secimi ve secim sonrasi sonuc analizi.

### 8.5 Repair Challenge

Kotu boarddan cikis bul.

### 8.6 Exam

Az ipucuyla birden cok ilkeyi birlikte uygulat.

Bu cesitlilik egitimi monotonluktan cikarir.

## 9. HUD ve Geri Bildirim Sistemi Onerisi

## 9.1 Mevcut soldaki panel mantigi degismeli

Bugunku tutorial overlay solda tek panel olarak duruyor. Oyuncu bunu okumuyorsa paneli daha da buyutmek cozum degil.

Yeni mantik:

- Bir ana hedef, ekranin merkezi odagina yakin ve daha buyuk gosterilmeli.
- Ikincil hedefler checkbox veya chip gibi kisa bir formatta gosterilmeli.
- "Ipuclari" ana hedeften ayri bir micro coach katmani olmali.
- Oyuncu ayni hatayi yaptikca ipucu daha somutlasmali.

## 9.2 Sonuc paneli daha acik olmali

Bugunku result paneli iyi yonde bir baslangic ama sunlari eklemeli:

- senin secimin
- ideal secim
- neden farkli
- bir sonraki derse hazirsan neden hazirsin
- tekrar denerken neyi farkli denemelisin

Kart dersleri icin bunun yaninda minik once/sonra tahta gosterimi veya etki ozet kutusu olmali.

## 9.3 Failure feedback state machine gerekli

Her lesson su sorulara cevap verebilmeli:

- oyuncu hicbir sey yapmiyor mu
- oyuncu ayni yanlisi tekrar ediyor mu
- oyuncu hedefe yaklasti ama son anda bozdu mu
- oyuncu yanlis mantikla dogru sonucu mu aldi

Bu olmadan tutorial sadece "gecti/kaldi" makinesi gibi kalir.

## 10. Teknik Mimari Yon

Bugunku tutorial.py dosyasi tek parca olarak cok sey yapiyor:

- hub
- overlay
- result panel
- legacy step runtime
- scenario runtime
- card choice runtime
- input handling
- state progression

Bu dosya calisir halde ama buyumeye elverissiz.

Onerilen yon:

### Korunacak moduller

- [src/tutorial_lessons.py](../src/tutorial_lessons.py)
- [src/tutorial_progress.py](../src/tutorial_progress.py)
- [src/tutorial_scenarios.py](../src/tutorial_scenarios.py)
- [src/tutorial_cards.py](../src/tutorial_cards.py)

Bu moduller temel olarak dogru yonde.

### Ayrilmasi gereken sorumluluklar

- tutorial runtime state ve lesson flow
- tutorial hub UI
- tutorial live HUD
- tutorial result review
- tutorial coach / hint escalation

Muhtemel yeni dosyalar:

- src/tutorial_ui.py
- src/tutorial_flow.py
- src/tutorial_review.py
- src/tutorial_coach.py

Bu isimler sabit olmak zorunda degil. Onemli olan soru su:
Tek bir dosya tum tutorial deneyimini tasimaya devam etmemeli.

## 11. Dosya Bazli Etki Alani

### [src/main.py](../src/main.py)

Degisecek konular:

- ilk tutorial popup daveti
- skip semantigi
- quick start ve academy start ayrimi

### [src/menu.py](../src/menu.py)

Degisecek konular:

- tutorial kartindan huba tasinacak gorsel dil
- tutorial giris kutusunda daha net vaad metni

### [src/guide_screen.py](../src/guide_screen.py)

Degisecek konular:

- guide -> tutorial -> guide geri donus akisi
- guide ile lesson briefing arasindaki kopru

### [src/tutorial.py](../src/tutorial.py)

Degisecek konular:

- hub layoutu
- lesson briefing ve runtime HUD
- result panel derinligi
- legacy step davranislari
- mikro feedback cizimleri

### [src/tutorial_lessons.py](../src/tutorial_lessons.py)

Degisecek konular:

- yeni lesson metadata alanlari
- sure, zorluk, beceri etiketi, unlock nedeni, prerequisite, recommendation vb.

### [src/tutorial_scenarios.py](../src/tutorial_scenarios.py)

Degisecek konular:

- daha zengin degerlendirme metricleri
- ideal line, forbidden pattern, optional mastery kriterleri

### [src/tutorial_cards.py](../src/tutorial_cards.py)

Degisecek konular:

- kart aileleri
- secim sonrasi karsilastirmali aciklama
- belki secim sonrasi micro simulation metadatasi

### [src/user_manager.py](../src/user_manager.py)

Degisecek konular:

- skip ve tamamlandi durumunun ayrismasi
- tutorial progressin daha dogru tutulmasi
- last_seen_lesson, recommended_lesson, deferred_tutorial gibi alanlar

### [src/localization.py](../src/localization.py)

Degisecek konular:

- briefing metinleri
- coach metinleri
- hata turleri
- chapter ve lesson aciklamalari

## 12. Onerilen Veri Genisletmeleri

Mevcut lesson tanimlarina su alanlar eklenmeli:

- duration_seconds
- difficulty_level
- skill_tags
- why_it_matters
- failure_modes
- intro_brief_key
- summary_template_key
- recommended_followups
- unlock_reason_key
- mastery_rule_set

Mevcut scenario tanimlarina su alanlar eklenmeli:

- ideal_outcome_label
- common_failures
- forbidden_patterns
- target_columns
- expected_hold_usage
- replay_hint_key

Mevcut card lesson tanimlarina su alanlar eklenmeli:

- card_family
- why_wrong_cards_fail
- board_risk_label
- long_term_value_label
- followup_demo_mode

## 13. Bu Yeniden Tasarimin Nihai Hedefi

Yeni tutorial sistemi su sorulara evet dedirtmelidir:

- Oyuncu ilk 3 dakikada oyunun nasil dusunuldugunu anliyor mu?
- Egitim Merkezi ekranini acinca nereden baslayacagini hemen gorebiliyor mu?
- "Bu dersi neden oynamaliyim" sorusunun cevabi 2 saniye icinde goruluyor mu?
- Basarisiz oldugunda neyi yanlis yaptigini somut olarak gorebiliyor mu?
- Kart dersleri bitince Mystery Mode'a daha az kor giriyor mu?
- Egitim sistemi tekrar ziyaret etmeye deger bir oyun ici akademi gibi hissediyor mu?

Eger bu sorularin cogu hayir ise, tutorial kodu teknik olarak temiz olsa bile urun olarak basarisiz sayilmalidir.

## 14. Net Sonuc

Bugunku tutorial sistemi mart ayindaki haline gore daha gelismis durumda.
Altyapi problemi kismen cozulmus.

Ama bugun asil eksik olan seyler sunlar:

- onboarding semantigi yanlis
- Egitim Merkezi ekrani tema ile butunlesmiyor
- lesson briefing zayif
- canli ogretim dili zayif
- kart ve board dersleri ilke ogretmek yerine sonuc soyluyor
- progress verisi skip akisi nedeniyle kirlenebiliyor

Bu nedenle bundan sonraki hedef "bir iki yeni lesson eklemek" olmamali.
Hedef sunlarin birlikte yeniden kurulmasi olmalidir:

- onboarding
- akademi hub
- lesson briefing
- live coach
- review sistemi
- progress semantigi
- kart ve board pedagojisi

Ancak bu sekilde Egitim Modu oyuncuya gercekten oyunu ogreten, ana tema ile uyumlu ve tekrar ziyaret edilmeye deger bir omurgaya donusebilir.