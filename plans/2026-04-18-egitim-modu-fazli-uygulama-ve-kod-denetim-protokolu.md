# Egitim Modu Fazli Uygulama ve Kod Denetim Protokolu

Tarih: 18 Nisan 2026

Durum: Bu dokuman, [plans/2026-04-18-egitim-modu-yeniden-tasarim-ve-icerik-stratejisi.md](2026-04-18-egitim-modu-yeniden-tasarim-ve-icerik-stratejisi.md) icinde tanimlanan yeni tutorial vizyonunu uygulamak icin hazirlanmistir. Bu dokumanin ana farki sudur: yalnizca ne yapilacagini degil, nasil yapilacagini, hangi sirayla yapilacagini ve her faz sonunda kodun nasil denetlenip gerekirse nasil duzeltilecegini tarif eder.

## 1. Bu Dokuman Nasil Kullanilmali?

Her faz icin ayni ritim uygulanmalidir:

1. Faz kapsamindaki kod degisikliklerini yap.
2. Fazin hedef davranisini test et.
3. Degisen dosyalari satir satir incele.
4. Eksik, kirik, uyumsuz veya gereksiz karmasik kod varsa ayni faz icinde duzelt.
5. Ancak ondan sonra sonraki faza gec.

Yani bu planda "faz bitti" demek sunlar yesil olmadan soylenmez:

- davranis dogrulandi
- testler gecti
- diff okundu
- tutorial giris, cikis, progress ve UI akislari elle kontrol edildi
- varsa eksik kod ayni fazda duzeltildi

## 2. Faz Cikis Protokolu

Her fazin sonunda asagidaki zorunlu denetim uygulanmalidir.

### 2.1 Kod Denetim Adimlari

- Degisen dosyalari tekrar oku.
- Faz kapsaminda eklenen yeni method ve state alanlarinin baska akislarda da var oldugunu kontrol et.
- tutorial.py gibi buyuk siniflarda eklenen state alanlarinin __new__ ile olusturulan test nesnelerinde sorun cikarip cikarmadigini dusun.
- lesson, chapter, progress ve localization alanlarinda isim kaymasi var mi diye grep ile kontrol et.
- Main menu, guide, direct lesson launch ve single-player first-run yollarinin hepsinin hala calistigini dogrula.

### 2.2 Test Protokolu

Her fazin sonunda asgari olarak sunlar calistirilmalidir:

- tutorial ile ilgili hedefli test dosyalari
- gerekiyorsa yeni eklenen unit testler
- daha sonra workspace icindeki pytest gorevi

Bu workspace icindeki mevcut test gorevi:

- pytest (py3.12)

Ancak her fazda once hedefli tutorial testleri calismali, sonra tum paket kosulmalidir.

### 2.3 Faz Sonu Elle Kontrol Listesi

Her faz sonunda su sorular elle kontrol edilmelidir:

- tutoriala ilk popup ile giris calisiyor mu
- tutorial skip akisi progressi bozmuyor mu
- ana menuden tutoriala giris calisiyor mu
- guide ekranindan tutorial veya belirli lesson acma calisiyor mu
- lesson bitince donus akisi dogru yere gidiyor mu
- hub hala aktif canvas sinirlarinda kaliyor mu
- localization fallbackleri patlamiyor mu

### 2.4 Faz Sonu Duzeltme KuralI

Faz sonunda su tip problemler tespit edilirse ayni faz icinde duzeltilmelidir:

- state alanlari eksik oldugu icin testlerde AttributeError
- yeni lesson metadata alanlari nedeniyle localization veya progress kirilmasi
- secili lesson ile start butonu arasinda hitbox/flow kopuklugu
- hub veya overlay rectlerinin tasmasi
- main.py ve user_manager.py tarafinda semantik drift

"Sonraki fazda bakariz" denecek problemler sadece polish seviyesinde olanlar olabilir. Semantik veya state hatalari ertelenmemelidir.

## 3. Uygulama Sirasi Neden Bu Sekilde?

Bu planda once onboarding ve progress semantigi duzeltilir, sonra hub UI, sonra lesson runtime, sonra icerik derinligi gelir.

Bunun nedeni sudur:

- Semantik kirik kalirken UI guzellestirmek yanlistir.
- Progress bozukken yeni chapter eklemek yanlistir.
- Hub zayifken lesson sayisini artirmak ekranı daha kotu yapar.
- Runtime feedback gelmeden icerik buyutmek metin coplugu uretir.

Dogru sira:

1. Once dogru semantik
2. Sonra dogru bilgi mimarisi
3. Sonra dogru ogretim akisi
4. Sonra daha zengin icerik

## 3.1 Kanonik Ders Kataloğu Referansi

Bu dokumanda artik su kanonik lesson kimlikleri referans alinacaktir:

- Chapter A / quick_start:
	qs_move_lane, qs_rotate_fit, qs_soft_drop_control, qs_safe_hard_drop, qs_first_clear
- Chapter B / surface_control:
	surface_gap_fill, surface_keep_low, surface_avoid_holes, surface_protect_well
- Chapter C / queue_hold:
	plan_hold_save, plan_queue_read, plan_hold_vs_place, plan_two_step_setup
- Chapter D / recovery:
	recover_make_breathing_room, recover_hole_or_height, recover_reduce_ceiling, recover_wrong_side_escape
- Chapter E / card_foundations:
	cards_rescue_now, cards_tempo_trap, cards_perk_vs_instant, cards_long_term_value
- Chapter F / card_strategy:
	cards_synergy_scale, cards_rare_not_auto_pick, cards_build_direction, cards_risk_reward_timing
- Chapter G / mastery_exams:
	exam_board_midterm, exam_plan_midterm, exam_hybrid_final

Bu liste, [plans/2026-04-18-egitim-modu-yeniden-tasarim-ve-icerik-stratejisi.md](2026-04-18-egitim-modu-yeniden-tasarim-ve-icerik-stratejisi.md) icindeki kanonik katalog ile birebir ayni olmalidir. Bir tarafta degisen isimler diger tarafta ayni commit icinde guncellenmelidir.

## 3.2 Fazlara Gore Somut Lesson Teslimleri

Bu planda yalnizca altyapi degil, hangi faz sonunda hangi lesson setinin gercekten oynanabilir olacagi da net olmalidir.

| Faz | Hedef Teslim | Somut Lesson Sonucu |
| --- | --- | --- |
| Faz 0 | Semantik temizlik | Mevcut lessonlar dogru progress yazar, skip tamamlandi sayilmaz |
| Faz 1 | Onboarding ve quick-start yol | quick_start girisi ve qs_ lesson zincirinin taslagi belirlenir |
| Faz 2 | Yeni hub | Tum chapter kabuklari ve secili lesson detail karti gorunur hale gelir |
| Faz 3 | Briefing + HUD | Chapter A ve Chapter B lessonlari briefing + live HUD ile oynanabilir olur |
| Faz 4 | Derin degerlendirme | Chapter C ve Chapter D lessonlari ideal/kabul edilebilir/fail ayrimiyla oynanabilir olur |
| Faz 5 | Kart akademisi | Chapter E ve Chapter F lessonlari karsilastirmali kart review ile oynanabilir olur |
| Faz 6 | Rehber ve sinav koprusu | Chapter G exam lessonlari ve guide geri donus akislari acilir |
| Faz 7 | Copy ve localization sertlestirme | Tum chapter ve lesson copyleri TR/EN kalitesinde netlesir |
| Faz 8 | Son audit | Tum katalog regression kilidi altina alinir |

Bu tablo ozellikle onemlidir cunku onceki tutorial calismalarinda sik yapilan hata suydu: chapter isimleri konusuluyor ama o faz sonunda hangi derslerin gercekten oynanabilir olacagi belirsiz kaliyordu.

## 4. Faz 0: Acil Dogruluk Duzeltmeleri

Amac:

- Buyuk redesign baslamadan once tutorial davranisini teknik olarak daha dogru hale getirmek.

Bu faz buyuk gorunmez ama kritik oneme sahiptir.

### Faz 0 Kapsami

1. Skip tutorial akisinin basics chapterini tamamlanmis saymasini durdur.
2. Tutorial skip ile tutorial completed kavramini birbirinden ayir.
3. Soft drop lessonindeki off-by-one kosulunu duzelt.
4. Runtime tarafinda uretilen mini success ve progress celebration feedbacklerini ya gercekten ciz ya da state/olusturma tarafindan kaldir.

### Degisecek Dosyalar

- [src/main.py](../src/main.py)
- [src/user_manager.py](../src/user_manager.py)
- [src/tutorial.py](../src/tutorial.py)

### Yapilacak Kod Degisiklikleri

#### 4.0.1 Tutorial skip semantigi

[src/main.py](../src/main.py) icindeki ilk popup skip yolunda artik set_tutorial_completed(True) cagirmamali.

Onerilen yeni alanlar:

- tutorial_prompt_dismissed
- tutorial_prompt_last_seen_at
- tutorial_deferred_count

Bu alanlar user_manager veya settings seviyesinde tutulabilir. Hedef sudur:

- skip = oynanmadi
- skip = daha sonra yeniden davet edilebilir
- tamamlandi = gercekten basics veya hizli baslangic bitti

#### 4.0.2 set_tutorial_completed davranisi

[src/user_manager.py](../src/user_manager.py) icindeki set_tutorial_completed(True) yalnizca gercek tamamlama sonrasinda lesson progressi ileri tasimali.
Bu fonksiyon bir UI secimini degil, oyun ici gercek tamamlama semantigini temsil etmelidir.

#### 4.0.3 Soft drop kosulu

[src/tutorial.py](../src/tutorial.py) icindeki soft_drop_counter > self.step_target kosulu hedef gosterim ile birebir uyumlu hale getirilmeli.

#### 4.0.4 Mikro feedback karari

[src/tutorial.py](../src/tutorial.py) icindeki _draw_mini_success_effects ve _draw_progress_celebration bugun bos. Bu fazda karar verilmeli:

- ya gercekten cizilecekler
- ya da state tarafi sadeleştirilecek

Yarim kalmis bir UX katmani korunmamali.

### Faz 0 Testleri

- skip popupi basics progress yazmiyor mu
- first-run popup skip sonrasi tutorial hub hala gercek progress gosteriyor mu
- soft drop hedefi UI ile uyumlu anda tamamlanıyor mu
- yeni user profili ve eski user profili migrationi bozulmadi mi

### Faz 0 Sonu Kod Denetimi

- [src/main.py](../src/main.py) icinde tutorial prompt cagri noktalari tek tek okunacak.
- [src/user_manager.py](../src/user_manager.py) icinde tutorial_completed, tutorial_progress ve chapter unlock etkileri kontrol edilecek.
- [src/tutorial.py](../src/tutorial.py) icinde soft drop sayaci ve ilgili sub_message akisi birlikte okunacak.

### Faz 0 Sonu OlasI Duzeltmeler

- Eski profillerde basics daha once skip ile tamamlanmis gorunuyorsa migration veya repair script gerekebilir.
- testlerde __new__ ile uretilen TutorialMode nesneleri yeni attr bekliyorsa getattr fallback eklenmelidir.

## 5. Faz 1: Onboarding ve Giris Akisini Yeniden Kurma

Amac:

- Oyuncuyu tutoriala daha dogru anda ve daha dogru vaadle sokmak.

### Faz 1 Kapsami

1. Ilk popupi "Egitimi oyna mi" sorusundan cikarip daha net bir onboarding paneline cevir.
2. Hizli Baslangic, Akademiyi Ac ve Simdilik Gec seceneklerini ekle.
3. Guide, menu ve first-run girislerini ayri intentlerle modele bagla.
4. lesson source / return source kavramini ekle.

### Bu Fazda Somutlasacak Lesson Seti

Bu faz icerik fazi degil gibi gorunse de, quick-start yolunun sinirlari burada sabitlenmelidir. Faz 1 sonunda asagidaki lessonlar resmi olarak "onboarding yolu" kabul edilecektir:

- qs_move_lane
- qs_rotate_fit
- qs_soft_drop_control
- qs_safe_hard_drop
- qs_first_clear

Bu faz sonunda bu lessonlarin hepsinin tam polish ile bitmis olmasi gerekmez. Ama su netlesmis olmalidir:

- hangi sirayla oynanacaklari
- first-run popup'tan hangilerinin acilacagi
- hizli baslangic sonunda huba nasil yonlendirecekleri
- tutorial_completed semantigine nasil baglanacaklari

### Degisecek Dosyalar

- [src/main.py](../src/main.py)
- [src/tutorial.py](../src/tutorial.py)
- [src/guide_screen.py](../src/guide_screen.py)
- gerekirse [src/user_manager.py](../src/user_manager.py)

### Yapilacak Kod Degisiklikleri

#### 5.1.1 Entry intent modeli

TutorialMode veya tutorial flow katmanina su tur bir bilgi eklenmeli:

- entry_source = first_run, menu, guide_hub, guide_lesson
- return_target = menu, guide, hub, next_recommended

Boylece tutorial sonucunda nereye donulecegi launch_lesson_id gibi yan etkili proxylerle degil, acik bir intent modeliyle yonetilir.

#### 5.1.2 Quick start lesson zinciri

Tam basics chapterin tamamini ilk popuptan acmak yerine daha kisa bir quick-start lesson zinciri tanimlanabilir.

Bu zincir:

- 60-90 saniye
- sadece oyunu acmak icin gereken cekirdek mantik
- lesson sonunda "akademinin kalanina gec" CTA'si

Bu zincirin kanonik icerigi bu dokumanda artik sabittir:

1. qs_move_lane
2. qs_rotate_fit
3. qs_soft_drop_control
4. qs_safe_hard_drop
5. qs_first_clear

#### 5.1.3 Re-prompt kurali

Skip eden kullanici icin su kurallardan biri secilmeli:

- ilk 2 oyun sonrasi tekrar nazik hatirlatma
- ilk 3 game over asiri erken olduysa tavsiye
- guide ekraninda tutorial CTA daha guclu vurgulansin

### Faz 1 Testleri

- first-run popup secimleri dogru state yaziyor mu
- guide lesson launch sonrasi donus akisi guide veya huba donebiliyor mu
- menu tutorial girisi akademiyi aciyor mu
- quick start tamamlaninca basics tamamen bitmis sayilmiyor mu yoksa ayri bir state mi aliyor

### Faz 1 Sonu Kod Denetimi

- main.py icindeki tum tutorial giris cagrilari okunacak.
- TutorialMode init ve geri donus mantigi tekrar okunacak.
- guide_screen tutorial buton label ve aksiyonlari intent modeliyle uyusuyor mu kontrol edilecek.

### Faz 1 Sonu OlasI Duzeltmeler

- source/return target drift varsa tek enum veya sabit tablosu olusturulacak.
- launch_lesson_id temelli eski davranisla catisma varsa compatibility katmani eklenecek.

## 6. Faz 2: Egitim Merkezi Hub UI Yeniden Tasarimi

Amac:

- Hubi ana tema ile akraba, daha okunakli ve buyumeye uygun bir akademi ekranina cevirmek.

### Faz 2 Kapsami

1. Mevcut iki panel listesi yerine daha zengin bilgi mimarisi kur.
2. Ana menu tutorial kartinin gorsel dilini huba tasI.
3. Secili lesson icin buyuk detay paneli ekle.
4. Scroll, responsive yogunluk ve chapter buyume stratejisini coz.

### Bu Fazda Somutlasacak Chapter Kabuklari

Faz 2 sonunda tum chapterlar icerik olarak tamamlanmis olmak zorunda degil, ama hub icinde asagidaki chapter kabuklari gorunmelidir:

- quick_start
- surface_control
- queue_hold
- recovery
- card_foundations
- card_strategy
- mastery_exams

Her chapter icin en az su metadata gosterilebilir hale gelmelidir:

- ekran adi
- kisa vaad metni
- lesson sayisi
- zorluk seviyesi
- unlock nedeni veya kilit kosulu

### Degisecek Dosyalar

- [src/tutorial.py](../src/tutorial.py) veya yeni [src/tutorial_ui.py](../src/tutorial_ui.py)
- [src/menu.py](../src/menu.py) referans gorsel dili icin
- gerekirse yeni tutorial UI helper dosyalari

### Yapilacak Kod Degisiklikleri

#### 6.2.1 Hub layout ayrisma

_draw_tutorial_hub icindeki tum layout mantigi tek fonksiyonda kalmamali.
Asgari ayrisma:

- hub root panel
- hero section
- chapter rail
- selected lesson detail card
- footer actions

#### 6.2.2 Gorsel tema entegrasyonu

[src/menu.py](../src/menu.py) icindeki tutorial_mode dashboard kartinin kullandigi accent, flavor, glow ve hierarchy dili referans alinmali.

Bu fazda su varliklar gozden gecirilmeli:

- tutorial panel effect gorseli
- tutorial renk paleti
- baslik/alt baslik tipografisi
- glow ve border agirligi

#### 6.2.3 Lesson detail karti

Secili lesson alani asgari olarak sunlari gostermeli:

- baslik
- aciklama
- why it matters
- sure
- zorluk
- beceri etiketleri
- basari kriterleri
- recommended followup

#### 6.2.4 Buyume stratejisi

Chapter sayisi ve lesson sayisi artinca layout kirilmamali.
Bu nedenle en bastan su kararlar verilmeli:

- dikey scroll mu, sayfalama mi, akordeon mu
- kisaltma mantigi mi, yatay kart akisi mi
- 800x600 minimum yuzeyde ne gorunur kalacak

### Faz 2 Testleri

- mevcut [tests/test_phase8_tutorial_ui_scaling.py](../tests/test_phase8_tutorial_ui_scaling.py) korunacak ve genisletilecek
- hub rectleri hala active canvas sinirinda kaliyor mu
- chapter ve lesson sayisi arttiginda scroll veya page mantigi calisiyor mu
- mouse ve keyboard selection hala stabil mi

### Faz 2 Sonu Kod Denetimi

- Hub draw fonksiyonlari okunacak; tek fonksiyona tekrar yigilma basladiysa ayrisma yapilacak.
- Rect hesaplari ve font wrap mantigi yeniden okunacak.
- Basla butonu, secili lesson karti ve chapter rail arasindaki hitbox uyumu elle denenecek.

### Faz 2 Sonu OlasI Duzeltmeler

- Ders sayisi arttiginda kart yukseklikleri asiri dusuyorsa scroll eklenmeli.
- Baslik ve aciklama cizimleri active canvas testlerinde tasiyorsa layout helper tekrar duzeltilmeli.

## 7. Faz 3: Lesson Briefing ve Live HUD Katmani

Amac:

- Oyuncu derse girmeden once neyi ogrenecegini bilsin ve ders sirasinda hedefleri ekranda net gorebilsin.

### Faz 3 Kapsami

1. Her lesson icin pre-brief paneli ekle.
2. Live HUD'da objective chips, danger hints ve coach line sistemi kur.
3. Mevcut soldaki overlay panel mantigini daha odakli hale getir.
4. Idle ve repeated mistake hint escalation ekle.

### Bu Fazda Gercekten Oynanabilir Olacak Lessonlar

Faz 3 sonunda briefing + live HUD standardi asagidaki lessonlarda gercekten calisiyor olmalidir:

- qs_move_lane
- qs_rotate_fit
- qs_soft_drop_control
- qs_safe_hard_drop
- qs_first_clear
- surface_gap_fill
- surface_keep_low
- surface_avoid_holes
- surface_protect_well

Bu faz bitince oyuncu en azindan boarda nasil bakmasi gerektigini ve tutorial HUD'nin nasil okunacagini ogrenmis olmalidir.

### Degisecek Dosyalar

- [src/tutorial.py](../src/tutorial.py)
- [src/tutorial_lessons.py](../src/tutorial_lessons.py)
- [src/tutorial_scenarios.py](../src/tutorial_scenarios.py)
- gerekirse yeni coach/helper dosyalari

### Yapilacak Kod Degisiklikleri

#### 7.3.1 Lesson briefing metadata

Her lesson tanimina su alanlar eklenmeli:

- intro_title
- intro_summary
- primary_goal
- secondary_goals
- mistake_watchouts
- estimated_time

Bu metadata once su lesson setinde eksiksiz doldurulmalidir:

- tum qs_ lessonlari
- tum surface_ lessonlari

#### 7.3.2 Live coach state machine

Runtime state su olaylari ayirt edebilmeli:

- hic aksiyon yok
- ayni hatali pattern tekrarlandi
- hedefe yakinlasildi
- hedef bozuldu

#### 7.3.3 HUD bolunmesi

Mevcut tek panel yerine:

- ana hedef satiri
- ikincil hedef chips
- coach bubble
- gerekirse board highlight anchor

### Faz 3 Testleri

- briefing ekranindan lessona gecis
- live HUD active canvas ve board layoutu asmiyor mu
- idle timer ve repeated mistake escalation dogru tetikleniyor mu
- briefingsiz guide launch gibi compatibility pathler bozulmadi mi

### Faz 3 Sonu Kod Denetimi

- tutorial.py icindeki state alanlari okunacak; lesson_result_active, waiting_for_enter, hub_active ve briefing_active birbirini yanlis bozmuyor mu bakilacak.
- yeni metadata alanlarinin olmayan eski lessonlarda fallback ile calistigi dogrulanacak.

### Faz 3 Sonu OlasI Duzeltmeler

- if/elif yiginlari buyurse coach mantigi ayri helpera alinacak.
- testlerde __new__ ile uretildigi icin eksik attr riski varsa getattr tabanli fallback eklenecek.

## 8. Faz 4: Lesson Engine ve Degerlendirme Derinlestirme

Amac:

- Tutoriali sadece "hedef tamamlandi" degil, kalite ve niyet acisindan da degerlendiren bir sisteme cevirmek.

### Faz 4 Kapsami

1. Scenario evaluation metriclerini zenginlestir.
2. Board lessonlar icin ideal ve kabul edilebilir sonuc ayrimi kur.
3. Legacy step dersleri icin de daha anlamli completion ve feedback ekle.
4. Result panelini karsilastirmali review paneline evrilt.

### Bu Fazda Gercekten Oynanabilir Olacak Lessonlar

Faz 4 sonunda asagidaki planning ve recovery lessonlari tam degerlendirme mantigi ile oynanabilir olmalidir:

- plan_hold_save
- plan_queue_read
- plan_hold_vs_place
- plan_two_step_setup
- recover_make_breathing_room
- recover_hole_or_height
- recover_reduce_ceiling
- recover_wrong_side_escape

Bu fazin cikisinda tutorial artik sadece "temel tuslar + board basics" degil, gercek karar mantigi ogreten bir sisteme donusmeye baslamis olacaktir.

### Degisecek Dosyalar

- [src/tutorial_scenarios.py](../src/tutorial_scenarios.py)
- [src/tutorial.py](../src/tutorial.py)
- [src/tutorial_lessons.py](../src/tutorial_lessons.py)

### Yapilacak Kod Degisiklikleri

#### 8.4.1 Scenario metric seti

Line, hole ve height yanina ihtiyaca gore su metricler dusunulmeli:

- target column usage
- forbidden hole pattern
- surface roughness
- hold used or not
- queue advantage used
- ideal move family matched

#### 8.4.2 Result paneli

Yeni result paneli su bloklari icermeli:

- gectin/kaldin
- neleri basardin
- hangi hedefleri kacirdin
- ideal hamle ile kendi hamlen arasindaki fark
- sonraki denemede tek odak noktasi

#### 8.4.3 Legacy step modernizasyonu

Move, rotate, soft drop gibi lessonlar da daha canli hale getirilmeli:

- mikro odul
- hareket sayaci
- dogru zamanlama mesaji
- lesson summary

### Faz 4 Testleri

- scenario evaluation saf unit testleri
- result panel objective rendering testleri
- legacy step summary akisi
- fail durumunda reset yerine review gelmesi gereken lessonlar icin regression testleri

### Faz 4 Sonu Kod Denetimi

- Scenario evaluation fonksiyonlarinda basit metriclerden karmasik if bloklarina kayma varsa refactor edilmeli.
- Result panel metinleri ile gercek degerler ayni veri kaynagindan mi geliyor kontrol edilmeli.

### Faz 4 Sonu OlasI Duzeltmeler

- Fazla akilli ama kirilgan rule setler varsa sadeleştirilmeli.
- False positive veren star sistemi ayni fazda revize edilmeli.

## 9. Faz 5: Kart Akademisi 2.0

Amac:

- Kart derslerini dogru karti ezberletmekten cikarip, board ve build baglaminda dusunmeyi ogreten laboratuvara cevirmek.

### Faz 5 Kapsami

1. Kart aileleri mantigini ders yapisina tasi.
2. Kart secimi sonrasi karsilastirmali aciklama getir.
3. Mumkunse secim sonrasi mini sonuc simulasyonu veya before/after ozet kutusu ekle.
4. Uzun vadeli deger, kurtarma degeri ve sinerji kavramlarini ayri ayri ogret.

### Bu Fazda Gercekten Oynanabilir Olacak Lessonlar

Faz 5 sonunda kart akademisinin iki chapteri de oynanabilir olmalidir:

- cards_rescue_now
- cards_tempo_trap
- cards_perk_vs_instant
- cards_long_term_value
- cards_synergy_scale
- cards_rare_not_auto_pick
- cards_build_direction
- cards_risk_reward_timing

Buradaki kritik nokta sudur: Faz 5 sonunda kart tarafi yalnizca eski uc senaryonun makyajlanmis hali gibi kalmamali; sekiz lessonluk ayrik bir karar omurgasi hissettirmelidir.

### Degisecek Dosyalar

- [src/tutorial_cards.py](../src/tutorial_cards.py)
- [src/tutorial_lessons.py](../src/tutorial_lessons.py)
- [src/tutorial.py](../src/tutorial.py)
- gerekirse [src/game_modes_extra.py](../src/game_modes_extra.py) ile sadece kontrollu entegrasyon

### Yapilacak Kod Degisiklikleri

#### 9.5.1 Card family metadata

Her tutorial kart scenarioda su alanlar eklenebilir:

- family_label
- board_risk_label
- value_type = rescue, tempo, setup, perk
- why_best
- why_acceptable
- why_bad

#### 9.5.2 Sonuc karsilastirmasi

Result paneli yalnizca "senin secimin / ideal secim" degil, sunu da gosterir hale gelmeli:

- Senin secimin hangi problemi cozerdi
- Neyi cozemezdi
- Ideal secim neden bu board icin once onu cozmeli

#### 9.5.3 Kart overlay uyumu

Mevcut MysteryCardUI entegrasyonu, tutorial baseline scaling ve overlay referansi ile uyumlu kalmali.
Bu alanda eski scaling testleri kirilmamali.

### Faz 5 Testleri

- kart secim outcome unit testleri
- overlay scaling regression testleri
- farkli card family kopyalarinda localization fallback testleri

### Faz 5 Sonu Kod Denetimi

- tutorial_cards.py icindeki data ve runtime glue ayrimi korunuyor mu
- game_modes_extra tarafina gereksiz tutorial ozel mantigi siziyor mu
- card_ui baseline referansi kirildi mi kontrol edilecek

### Faz 5 Sonu OlasI Duzeltmeler

- Kart lesson sayisi artisinda overlay kalabaliklasiyorsa family bazli filtreleme eklenmeli.
- aciklama metinleri cok uzunsa result panel ozel wrap/layout revizyonu yapilacak.

## 10. Faz 6: Rehber Entegrasyonu, Onerilen Dersler ve Donus Akisi

Amac:

- Tutorial ile guide arasindaki kopruyu urun olarak anlamli hale getirmek.

### Faz 6 Kapsami

1. Guide ekranindan acilan lessonlar briefing ile acilsin.
2. Lesson sonu geri donus kaynaga gore sekillensin.
3. Egitim Merkezi icinde "sana onerilen sonraki ders" katmani eklensin.
4. Gerekirse rehberdeki ilgili bolumlerden tutoriala derin linkler guclendirilsin.

### Bu Fazda Gercekten Oynanabilir Olacak Lessonlar

Faz 6 sonunda sinav chapteri acilmis ve guide ile butunlesmis olmalidir:

- exam_board_midterm
- exam_plan_midterm
- exam_hybrid_final

Bu lessonlarin amaci yeni bilgi vermek degil; daha az yardimla onceki chapterlardan edinilen davranislari birlestirmektir.

### Degisecek Dosyalar

- [src/guide_screen.py](../src/guide_screen.py)
- [src/main.py](../src/main.py)
- [src/tutorial.py](../src/tutorial.py)
- [src/user_manager.py](../src/user_manager.py)

### Yapilacak Kod Degisiklikleri

#### 10.6.1 Return target mantigi

Lesson sonucu asagidaki kurallarla donmeli:

- guide_lesson ise guide veya academy suggestion ekranina
- menu/tutorial_mode ise academy huba
- first_run quick_start ise classic mode intro veya academy continuation ekranina

#### 10.6.2 Recommendation engine lite

Mevcut progress ve last_result verilerine gore:

- sonraki mantikli lesson
- tekrar edilmesi gereken lesson
- henuz acilmamis ama yaklasilan chapter

gibi basit oneriler verilebilir.

### Faz 6 Testleri

- guide lesson launch -> lesson result -> guide donus
- hub lesson launch -> lesson result -> hub donus
- first-run quick start -> finish -> oyun veya academy yonlendirmesi

### Faz 6 Sonu Kod Denetimi

- main.py ve guide_screen.py icindeki tutorial aksiyon stringleri tekrar okunacak.
- tutorial source/return target tablolarinda drift var mi bakilacak.

### Faz 6 Sonu OlasI Duzeltmeler

- Guide ile tutorial arasi string tabanli routing kirilgansa ortak sabit tablo getirilecek.

## 11. Faz 7: Localization, Copy ve Metin Hierarsisi

Amac:

- Yeni tutorial deneyiminin gercekten okunur, kisa ve ogretici copy ile desteklenmesi.

### Faz 7 Kapsami

1. Yeni chapter, lesson, coach ve result copylerini ekle.
2. Uzun metin yerine skimmable kopya yaz.
3. TR ve EN once kaliteli bitir, diger diller icin fallback stratejisi kur.
4. Localization degisikliklerini dar ve guvenli patchlerle yap.

### Bu Fazda Kilitlenecek Ad ve Copy Seti

Faz 7 sonunda asagidaki isim katmanlari artik degismemeye yaklasmalidir:

- 7 chapter ekrani adi
- 28 lesson basligi
- lesson briefing basliklari
- result panel sabit etiketleri
- coach ve fail copy aileleri

Bu fazdan sonra lesson id'lerin ve localization key iskeletinin yeniden adlandirilmasi maliyetli hale gelecegi icin isim kararlari Faz 7 sonuna kadar kapanmalidir.

### Degisecek Dosyalar

- [src/localization.py](../src/localization.py)
- gerekiyorsa tutorial metin veri dosyalari

### Yapilacak Kod Degisiklikleri

#### 11.7.1 Copy stratejisi

Asagidaki metin turleri ayri dusunulmeli:

- onboarding copy
- hub copy
- lesson briefing copy
- in-lesson coach copy
- fail copy
- result summary copy

Her metin 2 saniyede taranabilir olmali. Ozellikle oyuncunun oyun aninda okudugu metinler 1 ana fikirden fazla tasimamali.

#### 11.7.2 Localization guvenligi

Localization buyuk bir dict oldugu icin tutorial ile ilgili anahtarlar dar kapsamli patchlerle eklenmeli ya da guncellenmeli.
Genis ve baglami zayif patchler komsu bloklari bozma riski tasir.

### Faz 7 Testleri

- TR fallback
- EN fallback
- olmayan dillerde copy bos kalmiyor mu
- uzun metinler panel tasmasi yaratiyor mu

### Faz 7 Sonu Kod Denetimi

- yeni eklenen localization keyler lesson metadata ile birebir eslesiyor mu kontrol edilecek.
- metin wrap ve ui tasmasi screenshot ve active canvas testleriyle dogrulanacak.

### Faz 7 Sonu OlasI Duzeltmeler

- Asiri uzun copyler runtime bug degilse bile ayni fazda kisaltilmali.

## 12. Faz 8: Son Audit, Temizlik ve Regression Kilidi

Amac:

- Tum tutorial paketini kapanisa hazir hale getirmek.

### Faz 8 Kapsami

1. Kod tekrarlarini temizle.
2. Kullanilmayan state ve helperlari kaldir.
3. Test paketini genislet.
4. Tutorial ile ilgili temel regresyon senaryolarini kalici hale getir.

### Zorunlu Regression Senaryolari

- first-run popup skip semantigi
- first-run quick start tamamlama
- hub draw active canvas sinirlari
- guide launch ve geri donus
- board scenario result paneli
- card scenario result paneli
- chapter unlock mantigi
- tutorial progress serialization

### Faz 8 Sonu Kod Denetimi

Bu fazda diff sadece okunmaz, asagidaki sorular zorunlu olarak cevaplanir:

- tutorial.py hala gereksiz buyuk mu
- yeni helperlar gercekten sorumluluklari ayirdi mi
- state adlari tutarli mi
- UI scaling testleri, semantic testler ve progress testleri birlikte yesil mi
- skip, completed, unlocked ve recommended kavramlari artik birbirine karismiyor mu

### Faz 8 Sonu OlasI Duzeltmeler

- Bu fazda kalan buglar ayni anda kapanmalidir. Faz 8 sonrasi tutorial paketinde bilinen semantik bug birakilmamalidir.

## 13. Fazlar Arasi Kirmizi Cizgiler

Bu paket uygulanirken sunlar yapilmamalidir:

1. Tum tutorial kodunu tek dev patch ile bastan yazmak.
2. localization.py icine binlerce satirlik kontrolsuz tutorial copy degisimi gommek.
3. Hub UI degismeden lesson sayisini agresif bicimde artirmak.
4. Guide ve first-run girislerini ayni return logic ile zorla birlestirmek.
5. MysteryCardUI entegrasyonunu korumadan tutorial kart overlayini yeniden kurmak.
6. Test paketi sadece scaling yesil diye tutorialin urun olarak hazir oldugunu varsaymak.

## 14. Fazlara Gore Ozet Cikis Kriterleri

### Faz 0 biterse

- skip artik tamamlandi demek degildir
- tutorial semantics temizdir

### Faz 1 biterse

- oyuncu tutoriala daha anlamli bir onboarding ile girer

### Faz 2 biterse

- Egitim Merkezi ana tema ile akraba ve buyumeye uygun hale gelir

### Faz 3 biterse

- oyuncu derse ne ogrenecegini bilerek girer

### Faz 4 biterse

- sistem kaliteyi ve niyeti daha iyi ogretir

### Faz 5 biterse

- kart akademisi ezber degil karar mantigi ogretir

### Faz 6 biterse

- guide, menu ve tutorial artik tek bir urun akisi gibi calisir

### Faz 7 biterse

- tutorial okunur, kisa ve ogretici copy ile tamamlanir

### Faz 8 biterse

- tutorial paketi hem teknik hem urun olarak kapanisa hazir hale gelir

## 15. Net Sonuc

Bu calisma iki ayri sey olarak gorulmemelidir:

- UI guzellestirme
- lesson arttirma

Asil is bunlarin birlikteligiyle tutoriali gercek bir akademi urunune cevirmektir.

Bu nedenle her fazin sonunda yalnizca "kod calisiyor mu" degil, ayni zamanda sunlar da sorulmalidir:

- oyuncu burada ne yapacagini hemen anliyor mu
- oyuncu neden bunu yaptigini anlayabiliyor mu
- oyuncu hata yaptiginda sistem bunu duzgun anlatiyor mu
- ekran ana oyunun premium diliyle ayni aileden hissettiriyor mu

Bu dort sorudan biri bile hayirsa, ilgili faz tekrar gozden gecirilmeli ve eksik kod ayni faz icinde duzeltilmelidir.