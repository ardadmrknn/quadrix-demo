# Eğitim Modu Detaylı İnceleme ve Geliştirme Planı

Tarih: 10 Mart 2026

## Amaç

Bu doküman, Quadrix içindeki eğitim modunun mevcut durumunu analiz eder ve oyunun temel mekaniklerini, karar verme süreçlerini, kart modu mantığını ve ileri seviye düşünme biçimini oyuncuya öğretecek daha güçlü bir eğitim sistemi için detaylı bir geliştirme planı sunar.

Hedef yalnızca tuş öğretmek değildir.
Hedef, oyuncunun şunları anlamasını sağlamaktır:

- Parçalar neden belirli şekilde yerleştirilir
- İyi ve kötü board durumu nasıl ayırt edilir
- Hold, next queue ve tempo nasıl kullanılır
- Kart seçimi sadece açıklama okuyarak değil, durum analizi yaparak nasıl yapılır
- Kısa vadeli kurtuluş ile uzun vadeli yatırım arasındaki fark nedir
- Oyuncu hata yaptığında sistem sadece reset atmak yerine neden yanlış yaptığını nasıl anlatır

## Kısa Sonuç

Mevcut eğitim modu çalışıyor ama kapsamı dar.
Bugünkü haliyle daha çok temel kontrol pratiği veriyor.
Oyuncuya gerçek anlamda oyun okuryazarlığı, karar mantığı ve kart stratejisi öğretmiyor.

Kod tabanında güçlü olan taraflar:

- Temel tutorial akışı zaten var: [src/tutorial.py](../src/tutorial.py)
- Kart seçimi ve kart etkileri için güçlü altyapı var: [src/game_modes_extra.py](../src/game_modes_extra.py)
- Rehber ekranı ve kart galerisi hazır: [src/guide_screen.py](../src/guide_screen.py)
- Ana menüde eğitim modu için giriş noktası var: [src/menu.py](../src/menu.py), [src/main.py](../src/main.py)
- Kullanıcı tarafında tutorial tamamlandı durumu tutuluyor: [src/user_manager.py](../src/user_manager.py)

Zayıf olan taraflar:

- Tutorial lineer ve sert kodlu
- Sadece 7 küçük adımdan oluşuyor
- Karar öğretmiyor, sadece input öğretiyor
- Kart sistemi oyun içinde derin ama eğitim tarafında pratik senaryo yok
- Rehber büyük ölçüde statik bilgi veriyor, interaktif öğretim yapmıyor
- Oyuncu başarısız olunca neden başarısız olduğu açıklanmıyor

Sonuç olarak doğru yön, mevcut tutorial dosyasını büyütmek değil; eğitim sistemini bölüm bazlı, veri odaklı, senaryo destekli bir öğretim altyapısına dönüştürmektir.

## Mevcut Durum Analizi

### 1. Tutorial Mode

Mevcut tutorial akışı [src/tutorial.py](../src/tutorial.py) içinde yer alıyor.

Merkezi noktalar:

- Tutorial sınıfı: [src/tutorial.py](../src/tutorial.py#L19)
- Adım kurulumları: [src/tutorial.py](../src/tutorial.py#L169)
- Input işleme: [src/tutorial.py](../src/tutorial.py#L441)
- Kilitlenme ve step ilerletme: [src/tutorial.py](../src/tutorial.py#L660)
- Güncelleme akışı: [src/tutorial.py](../src/tutorial.py#L689)
- Overlay çizimi: [src/tutorial.py](../src/tutorial.py#L749)

Şu an öğretilen şeyler:

- Sağa sola hareket
- Rotate
- Soft drop
- Hard drop
- Line clear
- Hold
- Bitirme ekranı

Bu akışın iyi tarafları:

- Oyuncuyu boğmayan kısa yapı
- Basit ve anlaşılır progression
- Tutorial paneli ve hint sistemi var
- Küçük başarı geri bildirimleri oyuncuyu yönlendiriyor

Bu akışın sınırlamaları:

- Oyuncuya sadece mekanik uygulama yaptırıyor
- Neden bu hamlenin doğru olduğu açıklanmıyor
- Board okuma yok
- Stack yönetimi yok
- Next queue planlaması yok
- Hatalı yerleştirme analizi yok
- Kart sistemi yok
- Senaryo çeşitliliği yok
- Bölüm seçimi veya atlama yapısı yok

### 2. Guide Screen

Rehber ekranı [src/guide_screen.py](../src/guide_screen.py) içinde bulunuyor.

Önemli yüzeyler:

- Kart veri listesi: [src/guide_screen.py](../src/guide_screen.py#L45)
- Sekme yapısı: [src/guide_screen.py](../src/guide_screen.py#L294)
- How to play yüzeyi: [src/guide_screen.py](../src/guide_screen.py#L670)
- Kart galerisi yüzeyi: [src/guide_screen.py](../src/guide_screen.py#L864)

Rehber ekranı güçlü çünkü:

- Oyun modlarını tanıtıyor
- Kartları bir galeride gösteriyor
- Kontrolleri ve genel bilgileri içeriyor

Ama eğitim için eksik çünkü:

- Etkileşimli değil
- Oyuncunun bir karar vermesini istemiyor
- Kart seçim mantığını canlı örnekle öğretmiyor
- Board bağlamı göstermiyor

### 3. Kart Sistemi ve Mystery Mode

Kart sisteminin ana omurgası [src/game_modes_extra.py](../src/game_modes_extra.py) içinde.

Önemli noktalar:

- Kart yöneticisi: [src/game_modes_extra.py](../src/game_modes_extra.py#L369)
- Kart seçimi hazırlama: [src/game_modes_extra.py](../src/game_modes_extra.py#L460)
- Weighted sample mantığı: [src/game_modes_extra.py](../src/game_modes_extra.py#L526)
- Perk yöneticisi: [src/game_modes_extra.py](../src/game_modes_extra.py#L3933)
- Kart seçim overlay açılışı: [src/game_modes_extra.py](../src/game_modes_extra.py#L6774)
- Seçim finalize: [src/game_modes_extra.py](../src/game_modes_extra.py#L6839)
- Kart etkilerini uygulama: [src/game_modes_extra.py](../src/game_modes_extra.py#L7055)

Bu sistem eğitim açısından çok değerli çünkü zaten şunlara sahip:

- Kart havuzu
- Nadirlik sistemi
- Ağırlıklı çıkma oranları
- Tek kullanımlık kartlar
- Sınırlı kullanım kartları
- Kalıcı perkler
- Kart seçim UI akışı
- Oyun içi etki uygulama mantığı

Yani kart eğitimi için yeni bir kart sistemi gerekmiyor.
Gereken şey, bu sistemi kontrollü öğretici senaryolara bağlamak.

## Ana Problem Tanımı

Bugünkü eğitim sistemi ile asıl oyun arasında büyük bir öğrenme boşluğu var.

Oyuncu eğitim modunu bitirdiğinde şunları hâlâ bilmiyor olabilir:

- Neden yüzeyi düz tutmak önemlidir
- Neden bazen satır temizlememek daha doğrudur
- Hold ne zaman kullanılmalı
- Kötü board nasıl kurtarılır
- Kart seçiminde hangi durumda hangi kart alınmalı
- Kalıcı perk ile anlık kart etkisi arasında karar nasıl verilir
- Nadir kart her zaman en doğru seçim midir
- Tempo, güvenlik, skor ve sinerji nasıl dengelenir

Bu nedenle eğitim modunun temel tasarım amacı değişmelidir.

Eski amaç:

- Oyuncuya kontrolleri öğretmek

Yeni amaç:

- Oyuncuya Quadrix düşünme biçimini öğretmek

## Yeni Eğitim Sistemi Vizyonu

Önerilen sistem, tek bir tutorial akışı yerine eğitim akademisi yapısında olmalıdır.

Bu akademi üç ana katmana ayrılmalıdır:

### Katman 1: Temel Öğrenme

Amaç:

- Oyuncuya temel kontrolleri ve parça davranışlarını öğretmek

İçerik:

- Hareket
- Rotate
- Soft drop
- Hard drop
- Hold
- Tek satır temizleme
- Quadrix nedir

### Katman 2: Oyun Anlayışı

Amaç:

- Oyuncuya iyi oynama mantığını öğretmek

İçerik:

- Board yüzeyi yönetimi
- Delik oluşturmanın zararı
- Sütun yüksekliği dengesi
- Next queue okuma
- Hold ile plan kurma
- Güvenli ve riskli yerleştirme farkı
- Kurtarma hamleleri

### Katman 3: Kart Akademisi

Amaç:

- Oyuncuya kart seçme, kart kullanma ve sinerji mantığını öğretmek

İçerik:

- Kart türleri
- Anlık etki, sınırlı kullanım, kalıcı perk farkı
- Board durumuna göre doğru kart seçimi
- Tempo kartları vs kurtarma kartları
- Sinerji mantığı
- Nadirlik ve ağırlık sistemi
- Hatalı kart seçiminin sonuçları

## Önerilen Bölüm Yapısı

### Bölüm A: Başlangıç Eğitimi

Alt dersler:

1. Hareket ve alan hissi
2. Dönüş ve duvar yakınında rotate
3. Soft drop ve hard drop farkı
4. Hold mantığı
5. İlk satır temizleme
6. İlk mini sınav

Hedef:

- Oyuncu temel inputları ezberlesin
- Ama ezber düzeyinde kalmasın, oyunun akışını hissetsin

### Bölüm B: Board Okuma

Alt dersler:

1. Düz yüzey neden iyidir
2. Çukur nedir, neden kötüdür
3. Yüksek kolon riski
4. Delik kapatma önceliği
5. Kötü board örneği üzerinde düzeltme
6. Mini challenge: verilen board'u kurtar

Hedef:

- Oyuncu board'a bakıp iyi/kötü karar verebilsin

### Bölüm C: Planlama

Alt dersler:

1. Next queue okuma
2. Hold ile iki hamle sonrası düşünme
3. Güvenli yerleştirme vs açgözlü skor hamlesi
4. Quadrix hazırlama
5. Bazen küçük clear neden daha doğrudur

Hedef:

- Oyuncu tek hamle değil, kısa ufuklu plan yapmayı öğrensin

### Bölüm D: Hata Yönetimi

Alt dersler:

1. Yanlış yerleştirme sonrası ne yapılır
2. Tavan yaklaşırken öncelikler nasıl değişir
3. Kurtarma modunda hangi piece yönetimi yapılır
4. Panik altında tempo düşürme

Hedef:

- Oyuncu hata yaptığında oyunun bittiğini sanmasın

### Bölüm E: Kart Akademisi Temel

Alt dersler:

1. Kart nedir, ne zaman gelir
2. Kart seçimi neden önemlidir
3. Anlık kartlar
4. Sınırlı kullanım kartları
5. Kalıcı perkler
6. Nadirlik sistemi

Hedef:

- Oyuncu kartları yalnızca isimlerinden değil, işlev ailelerinden tanısın

### Bölüm F: Kart Karar Eğitimi

Alt dersler:

1. Bozuk board için kurtarma kartı seçimi
2. Güçlü board için tempo/skor kartı seçimi
3. Uzun vadeli perk yatırım dersi
4. Hak yönetimi gerektiren kartlar
5. Kart sinerjisi dersi
6. Yanlış kart seçimi analizi

Hedef:

- Oyuncu kart seçimini durum okuma ile ilişkilendirsin

### Bölüm G: Ustalık Görevleri

Alt dersler:

1. Sınırlı hamle ile board düzeltme
2. Belirli kartla belirli problemi çözme
3. Yanlış gibi görünen ama doğru kart seçimi senaryosu
4. Karma sınav

Hedef:

- Öğrenilen şeyleri sentezlemek

## Kart Öğretimi İçin Özellikle Eklenmesi Gereken Senaryolar

Kart sistemi oyunun en özgün katmanlarından biri olduğu için burada ezber değil, karar öğretmek gerekir.

### Senaryo 1: Kurtarma Kartı Seçimi

Verilen durum:

- Board bozuk
- Delikler var
- Sağ sütun çok yüksek
- Oyuncu baskı altında

Kart seçenekleri:

- Alt Süpür
- Tepe Kesici
- Hız Patlaması

Öğretilecek şey:

- Parlak görünen kart her zaman doğru kart değildir
- Hız kartı bazen güçlü görünür ama bozuk board'da hatayı büyütür
- Board'un ihtiyacına göre seçim yapılmalıdır

### Senaryo 2: Uzun Vadeli Perk Yatırımı

Verilen durum:

- Board kontrollü
- Tehlike az
- Oyun erken safhada

Kart seçenekleri:

- Ekstra Cep
- Satır temizleyen anlık kart
- Küçük kurtarma kartı

Öğretilecek şey:

- Erken oyunda kalıcı perk seçimi bazen en iyi yatırımdır

### Senaryo 3: Hak Yönetimi

Verilen durum:

- Oyuncuda Geri Sarma veya Şekil Değiştirici gibi sınırlı hak kartı var

Görev:

- Hemen kullanma yerine doğru anı bekleme pratiği

Öğretilecek şey:

- Kaynak yönetimi
- Panik ile strateji farkı

### Senaryo 4: Sinerji Kurma

Verilen durum:

- Oyuncunun aktif perkleri var
- Yeni kart seçimi geliyor

Seçenekler:

- Sinerji Bonus
- Bağımsız güçlü anlık kart
- Düşük değerli utility kart

Öğretilecek şey:

- Mevcut build ile yeni seçim arasındaki ilişki

### Senaryo 5: Nadirlik Yanılgısı

Verilen durum:

- Bir legendary kart ve iki common/uncommon kart gösterilir
- Legendary görsel olarak daha çekicidir

Öğretilecek şey:

- Nadirlik güç anlamına gelir ama her durumda doğruluk anlamına gelmez

## Eğitim Tasarım İlkeleri

Yeni sistem şu ilkelerle tasarlanmalıdır.

### 1. Talimat Yerine Karar Öğretimi

Oyuncuya sadece şu söylenmemeli:

- Şimdi sola git
- Şimdi döndür
- Şimdi bunu seç

Bunun yerine şu öğretilmeli:

- Bu durumda neden bu seçenek daha doğru
- Neden diğer seçimler zayıf kalıyor
- Bu karar kısa ve uzun vadede ne üretir

### 2. Başarısızlık Sonrası Açıklama

Mevcut yapı bazı yerlerde reset odaklı.
Yeni sistemde başarısızlık durumunda şu geri bildirimler verilmelidir:

- Delik bıraktın
- Board yüzeyi çok bozuldu
- Kurtarma kartı yerine tempo kartı seçtin
- Hold'ü geç kullandın
- Hard drop ile güvenli alanı kapattın

### 3. Kısa Ders, Hızlı Geri Bildirim

Uzun, tek oturumluk öğretim yerine küçük dersler daha etkili olur.
Her ders 30 saniye ile 2 dakika arasında bitebilecek kadar kısa tutulmalı.

### 4. Kontrollü Senaryo Kullanımı

Gerçek oyundaki rastgelelik yerine eğitimde şu şeyler kontrollü olmalı:

- Başlangıç board durumu
- Mevcut parça
- Sonraki parçalar
- Gerekirse kart seçenekleri

### 5. Kademeli Serbestlik

İlk derslerde input kısıtlaması olabilir.
İleri derslerde oyuncuya daha fazla özgürlük verilip sonuç analizi yapılmalı.

## Teknik Mimari Önerisi

## Neden Mevcut Yaklaşım Büyütülmemeli

Mevcut [src/tutorial.py](../src/tutorial.py) dosyası step bazlı if/elif yapısıyla ilerliyor.
Bu yaklaşım birkaç ek adım için tolere edilebilir ama bölüm bazlı eğitim, kart senaryoları, yıldız sistemi ve farklı başarı koşulları geldiğinde hızla karmaşıklaşır.

Bu nedenle eğitim sisteminin veri odaklı hale getirilmesi önerilir.

## Önerilen Yeni Yapı

Önerilen yeni dosyalar:

- src/tutorial.py
  Mevcut sınıf korunur ama bir orchestrator haline getirilir
- src/tutorial_lessons.py
  Ders tanımları burada tutulur
- src/tutorial_scenarios.py
  Board setup, forced piece queue, kart seçenekleri gibi senaryo üreticileri burada tutulur
- src/tutorial_progress.py
  İlerleme, yıldız, bölüm tamamlama, en iyi sonuç mantığı burada tutulur
- src/tutorial_ui.py
  Overlay, görev listesi, geri bildirim kutuları, değerlendirme paneli burada tutulur
- src/tutorial_cards.py
  Kart eğitimine özel helper katmanı; gerçek kart sistemini kontrollü şekilde çağırır

Alternatif olarak ilk fazda daha küçük bir ayrıştırma da yapılabilir:

- tutorial.py
- tutorial_lessons.py
- tutorial_progress.py

Bu daha düşük riskli bir başlangıç olur.

## Ders Veri Modeli Önerisi

Her ders aşağıdaki gibi tanımlanmalıdır:

```python
{
    "id": "board_basics_surface_flat",
    "chapter": "board_basics",
    "title_key": "tutorial_lesson_surface_title",
    "description_key": "tutorial_lesson_surface_desc",
    "board_setup": "flat_surface_intro",
    "forced_current_piece": "T",
    "forced_next_pieces": ["I", "O", "L"],
    "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
    "success_condition": "no_holes_after_lock",
    "failure_condition": "creates_hole",
    "hint_keys": [
        "tutorial_hint_surface_1",
        "tutorial_hint_surface_2"
    ],
    "grading": {
        "stars": True,
        "safe_height_bonus": True,
        "speed_bonus": False,
    },
}
```

Bu yaklaşımın avantajı:

- Yeni ders eklemek kolay olur
- Dersler localization ile yönetilebilir
- UI ve gameplay ayrışır
- Kart dersleri de aynı veri modeliyle çalışabilir

## Kart Dersleri İçin Veri Modeli

```python
{
    "id": "card_rescue_pick_01",
    "chapter": "card_academy",
    "title_key": "tutorial_card_rescue_pick_title",
    "description_key": "tutorial_card_rescue_pick_desc",
    "board_setup": "dangerous_spiky_board",
    "forced_current_piece": "S",
    "forced_next_pieces": ["Z", "L", "I"],
    "card_choices": [
        "clear_rows",
        "peak_sculpt",
        "speed_burst_rare"
    ],
    "success_condition": "selects_best_rescue_card",
    "post_selection_demo": True,
    "explanation_key": "tutorial_card_rescue_pick_explanation",
}
```

Bu sayede gerçek kart sistemi korunurken eğitim bağlamında seçenekler kontrol edilebilir.

## UI ve UX Önerileri

### 1. Eğitim Paneli Yeniden Yapılandırılmalı

Mevcut eğitim paneli iyi bir başlangıç ama daha fazla yapı lazım.

Panel katmanları:

- Üstte bölüm adı
- Altında ders adı
- Ana hedef
- Opsiyonel alt hedefler
- Durum bazlı canlı geri bildirim
- Kısa açıklama ya da mentor notu

### 2. Hedef Listesi

Her derste hedefler checkbox gibi görünmeli.

Örnek:

- Deliği kapat
- Board yüksekliğini artırma
- Hold kullanmadan çöz

Bu oyuncunun neyi başarması gerektiğini netleştirir.

### 3. Sonuç Ekranı

Her ders sonunda sadece başarı mesajı gösterilmemeli.

Şunlar gösterilmeli:

- Ne yaptın
- Neyi iyi yaptın
- Hangi hata oluştu
- İstersen tekrar dene
- İstersen bir sonraki derse geç

### 4. Kart Derslerinde Karar Sonrası Açıklama

Oyuncu kartı seçtikten sonra sistem şu yapıda açıklama verebilir:

- Doğru seçim: Bu board'da tepe ve delik problemi vardı, bu nedenle kurtarma kartı daha değerliydi.
- Orta karar: Bu kart işe yarayabilir ama kısa vadeli çözüm sunuyor.
- Zayıf seçim: Tempo kartı aldın ama board zaten riskliydi, bu seçim hatayı büyütebilirdi.

### 5. Rehber ile Eğitim Entegrasyonu

Rehber ekranındaki kart galerisi tamamen statik kalmamalı.
Orta vadede şu akış eklenebilir:

- Kart detayında Bu Kartı Dene butonu
- Tıklandığında ilgili mini eğitim senaryosu açılsın

Bu, [src/guide_screen.py](../src/guide_screen.py) ile tutorial arasında güçlü bağ kurar.

## İçerik Öneri Havuzu

Bu bölüm, ileride ders üretirken kullanılabilecek geniş bir içerik bankasıdır.

### Temel Mekanik Dersleri

- Hareket serbestisi
- Duvar dibinde rotate
- Soft drop ile kontrol
- Hard drop güvenliği
- Hold ilkesi
- Next queue farkındalığı

### Board Dersleri

- Düz yüzey oluşturma
- Deliklerden kaçınma
- Derin kuyu yönetimi
- Yüksek kolon kırma
- Sağ tarafı Quadrix kuyusu olarak koruma
- Gereksiz karmaşa yaratmama

### Strateji Dersleri

- Bir sonraki iki hamleyi planlama
- Riskli skor hamlesi vs güvenli temizleme
- Board kötüleşmeden önce düzeltme
- Hold ile geleceği planlama

### Kurtarma Dersleri

- Çukur kapatma önceliği
- Yüksek tavan baskısı altında güvenli seçim
- Yanlış yerleştirmeden sonra kurtarma
- Panik anında yavaş oyun mantığı

### Kart Akademisi Dersleri

- Kart seçimi ne zaman yapılır
- Kart türleri
- Nadirlik nedir
- Weighted çıkış mantığı
- Kart hakları nasıl yönetilir
- Utility kartlar ne zaman değerlidir
- Perk yatırımının uzun vadeli değeri

### İleri Kart Dersleri

- Sinerji inşası
- Tempo kartları ile skor penceresi açma
- Board kurtarma kartları ile oyun uzatma
- Yanlış build kurmanın riskleri
- Aşırı greed build vs dengeli build

## Kartları Öğretmek İçin Gruplama Önerisi

Mevcut kart kataloğu çok zengin. Eğitim modunda kartları tek tek ezberletmek yerine aileler halinde öğretmek daha doğru olur.

### Aile 1: Anlık Kurtarma Kartları

Örnekler:

- Alt Süpür
- Tepe Kesici
- Gravity Well
- Renk Temizleme
- Blok Manyetiği

Öğretilecek mesaj:

- Board bozulduysa önce nefes aldıran kartlar değerlidir

### Aile 2: Manipülasyon Kartları

Örnekler:

- Row Shuffle
- Laser Drill
- Future Changer
- Block Workshop

Öğretilecek mesaj:

- Bu kartlar doğrudan temizlemek yerine board akışını dönüştürür

### Aile 3: Tempo ve Skor Kartları

Örnekler:

- Hız Patlaması
- Combo Boost
- Line Bonus
- Sinerji Bonus

Öğretilecek mesaj:

- Board güvenliyse bu kartlar çok değerlidir
- Board kötüyse cezaya dönüşebilirler

### Aile 4: Sınırlı Hak Kartları

Örnekler:

- Geri Sarma
- Şekil Değiştirici
- Keskin Nişancı
- Time Capsule
- Tuttuğunu Koparan

Öğretilecek mesaj:

- Asıl güç kartın kendisinde değil, doğru anda kullanılmasındadır

### Aile 5: Kalıcı Perkler

Örnekler:

- Ekstra Cep
- Esnek Sınır
- Sinerji Bonus
- Diğer aktif perkler

Öğretilecek mesaj:

- Bu seçimler run'ın omurgasını değiştirir

## Öğretim Geri Bildirim Sistemi Önerisi

Eğitim modunun en kritik geliştirmelerinden biri geri bildirim katmanıdır.

### Anlık Geri Bildirim Türleri

- Doğru hamle
- Güvenli hamle
- Riskli ama geçerli hamle
- Board'u bozan hamle
- Delik oluşturan hamle
- Yanlış kart seçimi
- Zayıf kaynak kullanımı

### Ders Sonu Geri Bildirim Türleri

- Başarılı
- Kısmen başarılı
- Hedefi geçti ama kötü alışkanlık gösterdi
- Başarısız

### Yıldız Sistemi Önerisi

Her ders için 3 yıldız:

- 1 yıldız: hedef tamamlandı
- 2 yıldız: hedef temiz şekilde tamamlandı
- 3 yıldız: hedef ideal veya öğretici kriterlerle tamamlandı

Örnek kriterler:

- Delik oluşturmadan bitir
- Belirli yükseklik üstüne çıkma
- Hold'ü verimli kullan
- Doğru kartı seç

## İlerleme Sistemi Önerisi

Bugün tutorial tamamlandı mantığı var ama granular değil.
Bu yapı genişletilmeli.

Önerilen ilerleme verileri:

- Tamamlanan bölümler
- Tamamlanan dersler
- Ders başına yıldız sayısı
- İlk geçiş tarihi
- En iyi performans
- Kart akademisi tamamlandı durumu
- Ustalık sınavı tamamlandı durumu

Örnek veri modeli:

```python
{
    "tutorial_progress": {
        "chapters": {
            "basics": {
                "unlocked": True,
                "completed": True,
                "stars": 12,
                "lessons": {
                    "move_intro": {"completed": True, "stars": 3},
                    "rotate_intro": {"completed": True, "stars": 2},
                }
            },
            "card_academy": {
                "unlocked": True,
                "completed": False,
                "stars": 4,
                "lessons": {}
            }
        }
    }
}
```

Bu veri yapısı kullanıcı bazlı saklanabilir.

## Localization İhtiyacı

Bu geliştirme büyük miktarda yeni tutorial metni gerektirecek.

Bu nedenle metin stratejisi önemli.

Öneri:

- İlk fazda yalnızca TR ve EN hazırlanabilir
- Diğer diller için fallback uygulanır
- Sonraki fazda localization genişletilir

Yeni localization kategorileri gerekebilir:

- chapter başlıkları
- lesson başlıkları
- ders açıklamaları
- hata geri bildirimleri
- kart karar açıklamaları
- yıldız kriterleri

Burada dikkat edilmesi gereken şey, büyük localization bloklarını tek seferde kaba patch ile düzenlememek.
Bu repo için daha önce de görüldüğü gibi dar kapsamlı, bağlamı güçlü değişiklikler daha güvenli olur.

## Fazlara Ayrılmış Uygulama Planı

## Faz 1: Mimari Hazırlık ve Temel Ayrıştırma

Amaç:

- Eğitim sistemini büyütebilecek bir iskelet kurmak

İşler:

- Mevcut tutorial akışını ders tanımı odaklı hale getirme
- tutorial_lessons.py oluşturma
- tutorial_progress.py oluşturma
- TutorialMode içinde step if/elif yoğunluğunu azaltma
- Bölüm ve ders kavramını menüden erişilebilir hale getirme

Beklenen çıktı:

- Eski tutorial davranışı korunur
- Yeni dersler eklemek kolaylaşır

## Faz 2: Temel ve Board Eğitimi İçeriği

Amaç:

- Basit input öğretiminden oyun mantığı öğretimine geçmek

İşler:

- Board yüzeyi dersleri
- Delik yönetimi dersleri
- Hold ve next queue dersleri
- Mini değerlendirme ekranı
- Hata geri bildirimi

Beklenen çıktı:

- Oyuncu tutorial sonunda gerçek oyuna daha hazır olur

## Faz 3: Kart Akademisi MVP

Amaç:

- Kart sistemi için ilk öğretici katmanı kurmak

İşler:

- Kart aileleri tanıtımı
- 3 ila 5 kart karar senaryosu
- Kontrollü kart seçim ekranı
- Kart seçimi sonrası açıklama paneli

Beklenen çıktı:

- Oyuncu Mystery Mode'a daha az kör girer

## Faz 4: Gelişmiş Eğitim ve Ustalık Görevleri

Amaç:

- Öğrenilen bilgileri pekiştirmek

İşler:

- Yıldız sistemi
- Karma challenge'lar
- Kart sinerji sınavları
- Kurtarma senaryoları
- Rehber ekranından eğitim açma köprüsü

Beklenen çıktı:

- Eğitim modu oyunun kalıcı bir ikinci omurgasına dönüşür

## MVP İçin Net Kapsam Önerisi

Eğer bu işi kontrollü şekilde başlatmak istiyorsak ilk sürümde şu kapsam yeterli ve doğru olur:

### Mutlaka Olmalı

- Bölüm bazlı eğitim ekranı
- Temel mekaniklerin yeni veri modeliyle taşınması
- 4 ila 6 yeni board mantığı dersi
- 3 kart seçim senaryosu
- Ders tamamlama ve yıldız sistemi temel sürüm

### Sonraya Kalabilir

- Mentor karakter
- Seslendirme benzeri anlatım
- Çok gelişmiş analiz sistemi
- Rehberden tek tık eğitim açma
- Adaptif öneri sistemi

## Riskler ve Dikkat Noktaları

### 1. Tutorial.py Çok Fazla Büyüyebilir

Eğer mevcut yaklaşım üzerine sadece yeni if blokları eklenirse dosya hızla kırılgan hale gelir.

Çözüm:

- Veri odaklı ders sistemi
- UI, scenario ve progress ayrıştırması

### 2. Kart Eğitimi Gerçek Oyundan Kopabilir

Eğer eğitim için sahte kart sistemi yazılırsa oyuncunun öğrendiği şey gerçek run ile örtüşmeyebilir.

Çözüm:

- Mümkün olduğunca [src/game_modes_extra.py](../src/game_modes_extra.py) içindeki gerçek kart selection ve effect mantığını yeniden kullanmak

### 3. Aşırı Uzun Eğitim Oyuncuyu Sıkabilir

Çözüm:

- Bölüm bazlı yapı
- Mini dersler
- İsteyen oyuncu bölümleri seçerek ilerleyebilmeli

### 4. Çok Fazla Yeni Localization Yükü Oluşabilir

Çözüm:

- İlk sürümde sınırlı kapsam
- TR/EN önceliği
- Sonra kalan dillere yayılım

## Doğrudan Kod Tarafında Dokunulacak Muhtemel Dosyalar

Ana dosyalar:

- [src/tutorial.py](../src/tutorial.py)
- [src/main.py](../src/main.py)
- [src/menu.py](../src/menu.py)
- [src/user_manager.py](../src/user_manager.py)
- [src/localization.py](../src/localization.py)

Muhtemel yeni dosyalar:

- src/tutorial_lessons.py
- src/tutorial_progress.py
- src/tutorial_scenarios.py
- src/tutorial_ui.py
- src/tutorial_cards.py

Yeniden kullanılacak güçlü mevcut sistemler:

- [src/game_modes_extra.py](../src/game_modes_extra.py)
- [src/guide_screen.py](../src/guide_screen.py)

## Bu Plan Nasıl Uygulanacak

Bu bölüm, yukarıdaki stratejik kararları doğrudan kod işine çevirir.
Amaç yalnızca ne yapılacağını listelemek değil, gerçekten implement ederken hangi sırayla, hangi dosyada, hangi sorumlulukla ilerleyeceğimizi netleştirmektir.

Temel prensip:

- Önce mevcut tutorial davranışını bozmadan iskelet kurulacak
- Sonra eski 7 adım yeni yapıya taşınacak
- Sonra yeni board dersleri eklenecek
- En son kart akademisi bu iskeletin üstüne oturtulacak

Bu sırayı bozmak risklidir.
Özellikle kart akademisini erken eklemek, tutorial refactor tamamlanmadan yapılırsa hem tutorial.py hem de kart entegrasyonu gereksiz karmaşık hale gelir.

## Uygulama Stratejisi

Pratikte işi üç büyük teknik parçaya ayırmak gerekir:

### Parça 1: Lesson Runtime

Bu katman şu sorumlulukları üstlenecek:

- Hangi dersin aktif olduğunu bilmek
- O dersin board setup'ını uygulamak
- Hangi inputların serbest olduğunu bilmek
- Başarı ve başarısızlık koşulunu değerlendirmek
- Bir sonraki derse geçmek
- Geri bildirim ve ders içi hedefleri taşımak

Bu katmanın merkezi yine tutorial mode olacak ama iç mantığı veri ile beslenecek.

### Parça 2: Progress ve Sonuç Sistemi

Bu katman şu sorumlulukları üstlenecek:

- Kullanıcı bazlı tutorial progress tutmak
- Ders yıldızlarını saklamak
- Bölüm tamamlanma durumunu hesaplamak
- İlk kez tamamlandı mı yoksa tekrar mı oynanıyor ayırt etmek
- Gerekirse eski tutorial_completed bayrağı ile geriye dönük uyumluluğu korumak

### Parça 3: İçerik ve Senaryo Katmanı

Bu katman şu sorumlulukları üstlenecek:

- Lesson tanımları
- Board senaryoları
- Forced current/next piece dizileri
- Kart dersleri için gösterilecek kontrollü kart seçenekleri
- Ders bazlı hint ve değerlendirme kuralları

## Dosya Bazında Uygulama Reçetesi

## 1. src/tutorial.py Nasıl Değiştirilecek

Bu dosya tamamen çöpe atılmamalı.
Mevcut çalışır akış korunmalı ama içerideki sert step mantığı soyutlanmalı.

Yapılacak ana değişiklikler:

- step tabanlı sert akışı lesson tabanlı bir runtime katmanına çevirmek
- Mevcut step sayaçları ders runtime state içine taşımak
- UI çizimini ders verisinden beslemek
- Başarı/başarısızlık kontrolünü if/elif bloğundan çıkarıp helper methodlara taşımak

TutorialMode içinde açılması önerilen yeni methodlar:

- _load_lesson_catalog()
- _start_lesson(lesson_id)
- _apply_lesson_scene(lesson)
- _reset_runtime_state_for_lesson()
- _handle_lesson_action(event)
- _update_lesson_progress(dt)
- _evaluate_success()
- _evaluate_failure()
- _complete_lesson(stars, summary_key=None)
- _retry_current_lesson()
- _advance_to_next_lesson()

Mevcut methodlar nasıl dönüştürülecek:

- _setup_step
  Eski 7 adım için geriye dönük uyumluluk katmanı olabilir ama ana giriş _start_lesson olmalı.
- handle_input
  Dersin izin verdiği action listesine göre yönlendirme yapmalı.
- lock_and_new_piece
  Ders bazlı başarı ve hata değerlendirme hook'u çağırmalı.
- update
  Artık yalnızca animasyon ve sayaç değil, aktif ders koşullarını da değerlendirmeli.
- _draw_tutorial_overlay
  lesson title, hedefler, feedback ve stars preview gibi yeni alanları çizebilecek hale gelmeli.

Önemli not:

İlk fazda mevcut değişken isimlerinin hepsini bir anda kaldırmaya çalışma.
Önce eski step değişkenlerini lesson runtime ile birlikte yaşatmak daha güvenli.
Refactor tamamlanınca gereksiz alanlar ikinci temizlik patch'i ile kaldırılmalı.

## 2. src/tutorial_lessons.py Nasıl Yazılacak

Bu dosya MVP için mutlaka açılmalı.
İlk gerçek ayrıştırma burada başlamalı.

İçermesi gereken ana yapılar:

- CHAPTERS sabiti
- LESSONS listesi
- LESSON_BY_ID lookup map
- LESSON_ORDER veya chapter bazlı sıra dizisi
- Yardımcı access fonksiyonları

Önerilen yapı:

```python
CHAPTERS = [
  {
    "id": "basics",
    "title_key": "tutorial_chapter_basics_title",
    "description_key": "tutorial_chapter_basics_desc",
    "unlocked_by_default": True,
  },
]

LESSONS = [
  {
    "id": "move_intro",
    "chapter": "basics",
    "kind": "legacy_step",
    "legacy_step": 1,
    "title_key": "tutorial_lesson_move_title",
    "description_key": "tutorial_lesson_move_desc",
    "allowed_actions": ["move_left", "move_right"],
    "success_condition": "move_left_right_counts",
  },
]
```

Burada kritik karar:

- İlk fazda legacy_step alanı kullanmak mantıklı
- Böylece eski 7 adımı kırmadan yeni lesson modeli tanımlanabilir

Yani ilk sürümde lesson sistemi tam soyut olmayabilir.
Ama lesson kaynağı ayrı dosyaya taşınmış olur.

## 3. src/tutorial_scenarios.py Nasıl Yazılacak

Bu dosya Faz 1 için zorunlu değil ama Faz 2 ile birlikte açılması daha temiz olur.

İçermesi gereken şeyler:

- Boş board senaryosu
- Tek çukur senaryosu
- Yüksek sağ kolon senaryosu
- Quadrix kuyusu senaryosu
- Kart kararı için riskli board senaryoları

Önerilen API:

```python
def build_scenario(name: str) -> dict:
  return {
    "grid": [...],
    "current_piece": "T",
    "next_pieces": ["I", "O", "L"],
    "hold_piece": None,
  }
```

Önemli prensip:

- Bu dosya yalnızca veri dönmeli
- Pygame çizimi veya game objesine doğrudan dokunmamalı
- TutorialMode bu veriyi alıp uygulasın

## 4. src/tutorial_progress.py Nasıl Yazılacak

Bu dosya progress veri işlemlerini user_manager'dan tamamen koparmak için değil, logic'i izole etmek için açılmalı.

Burada bulunması önerilen helper'lar:

- build_default_tutorial_progress()
- ensure_progress_shape(progress)
- mark_lesson_completed(progress, lesson_id, stars, stats)
- get_chapter_completion(progress, chapter_id)
- get_total_stars(progress)
- unlock_next_chapter_if_needed(progress)

Bu dosya ideal olarak saf veri dönüşümleri yapmalı.
Disk yazma işi burada olmamalı.
Disk yazma yine user_manager üstünden yapılmalı.

## 5. src/user_manager.py Nasıl Genişletilecek

Şu an kullanıcıda tutorial_completed bayrağı var.
Bu iyi ama yeni sistem için yetersiz.

Eklenmesi gereken yeni alan:

- tutorial_progress

Eklenmesi önerilen yeni methodlar:

- get_tutorial_progress(username=None)
- set_tutorial_progress(progress, username=None)
- mark_tutorial_lesson_completed(lesson_id, stars, stats=None, username=None)
- reset_tutorial_progress(username=None)

Geriye dönük uyumluluk kuralı:

- tutorial_completed alanı silinmemeli
- Eğer basics chapter veya tanımlı giriş lesson'ları tamamlandıysa tutorial_completed True yapılabilir
- Eski kullanıcı datası açıldığında tutorial_progress yoksa default oluşturulmalı

Bu migration sessiz yapılmalı.
Ayrı migration script gerekmiyor.

## 6. src/main.py Nasıl Bağlanacak

Ana akışta şu an tutorial mode doğrudan başlatılıyor.
İlk fazda bunu kökten değiştirmeye gerek yok.

Önerilen yaklaşım:

- tutorial_mode aksiyonu yine TutorialMode başlatsın
- Ama TutorialMode içine launch_lesson_id veya launch_chapter_id gibi opsiyonel parametre eklenebilsin

Örnek kullanım:

```python
game = TutorialMode(
  ...,
  launch_lesson_id="move_intro",
)
```

Bu alan ilk sürümde opsiyonel olmalı.
Varsayılan durumda ilk lesson açılsın.

Bu sayede sonraki fazlarda:

- ders seçme ekranından belirli derse atlama
- rehberden kart eğitimine direkt açılma

kolaylaşır.

## 7. src/menu.py İçin Nasıl İlerlenmeli

İlk fazda büyük bir chapter selection ekranı zorunlu değil.
Scope'u kontrollü tutmak için iki aşamalı gitmek daha doğru.

İlk sürüm:

- mevcut Eğitim paneli korunur
- tıklanınca tutorial ilk dersle açılır

İkinci sürüm:

- eğitim açılınca ara chapter selection / lesson hub ekranı gelir

Bu karar önemli çünkü önce tutorial runtime oturmadan ayrı bir eğitim hub ekranı yazmak gereksiz UI yükü getirir.

## 8. src/localization.py Nasıl Genişletilecek

Bu dosyada büyük bir blok ekleme riski var.
Bu yüzden fazlı çalışılmalı.

İlk fazda eklenecek minimum anahtarlar:

- chapter başlıkları
- lesson başlıkları
- lesson açıklamaları
- sonuç ekranı anahtarları
- stars ve objective metinleri

İlk fazda özellikle yapılmaması gereken şey:

- Kart akademisinin bütün lesson metinlerini tek seferde eklemek

Daha doğru yaklaşım:

- Faz 1 için only basics + board lessons
- Faz 3 geldiğinde card academy metinleri ayrı patch ile eklenir

## 9. src/game_modes_extra.py Nasıl Yeniden Kullanılacak

Kart akademisi geldiğinde bu dosyadan kopya mantık çıkarılmamalı.
Kopyalamak yerine kontrollü reuse yapılmalı.

Önerilen reuse noktaları:

- Kart katalog erişimi
- Kart title/description çözümleme
- Kart choice UI'dan bazı çizim/helper mantıkları
- Kart effect apply logic

Ama dikkat:

- Tutorial içinde full MysteryMode başlatmak her zaman doğru olmayabilir
- Özellikle kart seçimi eğitiminde bazen sadece controlled selection overlay gerekir

Bu yüzden Faz 3 için daha sağlıklı yaklaşım şudur:

- tutorial_cards.py içinde eğitim amaçlı bir adapter yazılır
- adapter gerçek kart katalog ve metin helper'larını kullanır
- ama selection sonucu tutorial state'e bağlı değerlendirme yapar

## Sınıf ve Sorumluluk Dağılımı

Bu işin temiz kalması için sorumluluk sınırları net olmalı.

TutorialMode sorumlulukları:

- oyun döngüsü entegrasyonu
- lesson lifecycle
- scene apply etme
- input dispatch
- update ve draw ana akışı

tutorial_lessons.py sorumlulukları:

- lesson metadata
- chapter metadata
- lesson sırası

tutorial_scenarios.py sorumlulukları:

- board ve parça senaryoları

tutorial_progress.py sorumlulukları:

- progress data manipülasyonu

user_manager.py sorumlulukları:

- progress persistence

tutorial_cards.py sorumlulukları:

- kart eğitimine özel controlled selection ve evaluation helper'ları

## Faz 1 Nasıl Yapılacak

Faz 1'in amacı yeni ders eklemek değil, altyapıyı çıkarmaktır.

Adım adım uygulanış:

1. tutorial_lessons.py oluştur.
2. Mevcut 7 step'i lesson tanımı olarak bu dosyaya taşı.
3. TutorialMode içine active_lesson, active_lesson_id, lesson_runtime_state alanlarını ekle.
4. __init__ içinde _start_lesson("move_intro") benzeri bir giriş başlat.
5. _setup_step tamamen silinmesin; lesson tanımı legacy_step ise mevcut step kurulumunu çağıran geçiş katmanı olarak kullanılsın.
6. handle_input içinde step == 1 gibi doğrudan kontrolleri yavaş yavaş _handle_lesson_action içine taşı.
7. Ders tamamlanınca artık next_step yerine next_lesson_id çözülmeye başlasın.
8. user_manager tarafında tutorial_progress default'u eklensin.
9. tutorial_completed bayrağı uyumluluk için korunarak güncellensin.

Faz 1 done kriteri:

- Mevcut tutorial kullanıcı açısından aynı çalışır
- Ama dersler ayrı dosyadan yüklenir
- TutorialMode içinde aktif lesson kavramı oluşur
- Progress verisi kullanıcı profilinde saklanabilir hale gelir

## Faz 2 Nasıl Yapılacak

Bu faz ilk gerçek yeni içerik fazıdır.

Adım adım uygulanış:

1. tutorial_scenarios.py oluştur.
2. En az 4 board senaryosu tanımla.
3. tutorial_lessons.py içine 2 ila 4 yeni board lesson ekle.
4. TutorialMode içinde _apply_lesson_scene methodu ile grid, current_piece, next_piece queue kurulumu yap.
5. _evaluate_success ve _evaluate_failure helper'larını aç.
6. Delik oluştu mu, yüzey çok bozuldu mu, hedef satır temizlendi mi gibi durumları kontrol eden küçük evaluator methodları ekle.
7. Sonuç ekranının sade MVP sürümünü çiz.
8. 1-3 yıldız hesaplayan basit grading kurallarını çalıştır.

Faz 2 done kriteri:

- Oyuncu yeni board derslerini oynayabilir
- Ders sonunda yıldız alır
- Hata yaptığında neden başarısız olduğuna dair kısa geri bildirim görür

## Faz 3 Nasıl Yapılacak

Bu fazda kart akademisinin minimum çalışan sürümü çıkarılmalı.

Adım adım uygulanış:

1. tutorial_cards.py oluştur.
2. game_modes_extra içinden reuse edeceğin helper'ları belirle.
3. En basit senaryo olarak kurtarma kartı seçimi dersini ekle.
4. Bu ders için controlled card_choices desteğini lesson tanımına bağla.
5. TutorialMode içinde kart seçim overlay tetikleyebilen lesson branch aç.
6. Seçim sonrası doğru/orta/zayıf karar açıklaması üret.
7. İstenirse aynı senaryo için post-selection demo oynat.

Bu fazda özellikle kaçınılacak şeyler:

- Tüm MysteryMode UI'sını tutorial içine gömmek
- Kart seçim eğitimi ile tam kart run sistemi yazmaya çalışmak
- Her kart için ayrı eğitim yapmak

Faz 3 done kriteri:

- En az 3 kart seçim senaryosu çalışır
- Oyuncu seçim yapar
- Sistem seçimi değerlendirir
- Kart öğretimi board bağlamına bağlı hale gelir

## Faz 4 Nasıl Yapılacak

Bu faz içerik ve polish fazıdır.

Adımlar:

1. Eğitim hub veya chapter selection ekranı ekle.
2. Ustalık challenge'larını ekle.
3. Rehber ekranı ile tutorial arasında geçiş noktaları ekle.
4. Kart galerisi üstünden mini eğitim açılabilmesini tasarla.
5. Sonuç ekranını daha zengin hale getir.

Faz 4 done kriteri:

- Eğitim yalnızca onboarding değil, tekrar ziyaret edilen bir ürün olur

## İlk Kodlama Sprinti İçin Net Görev Listesi

İlk sprintte yapılması gerekenler bunlar olmalı:

1. tutorial_lessons.py oluştur
2. tutorial_progress.py oluştur
3. user_manager.py içine tutorial_progress getter/setter ekle
4. tutorial.py içine active_lesson yapısını ekle
5. Mevcut 7 step'i lesson veri tanımına taşı
6. TutorialMode başlangıcını lesson-driven hale getir
7. Bir regression testi veya en azından manuel smoke checklist hazırla

İlk sprintte bilinçli olarak yapılmayacaklar:

- Yeni UI hub ekranı
- Kart akademisi
- Rehber entegrasyonu
- Çok büyük localization genişlemesi

## Lesson Runtime İçin Önerilen İç State Yapısı

TutorialMode içinde tek tek dağınık field'lar yerine lesson runtime sözlüğü veya net isimli state alanları kullanılmalı.

Örnek:

```python
self.active_lesson_id = "move_intro"
self.active_lesson = lesson_lookup[self.active_lesson_id]
self.lesson_runtime = {
  "started_at": pygame.time.get_ticks(),
  "move_left_count": 0,
  "move_right_count": 0,
  "rotate_count": 0,
  "soft_drop_frames": 0,
  "feedback_key": None,
  "objectives_completed": set(),
  "failed_reason": None,
}
```

Bu yaklaşımın avantajı:

- her lesson için farklı state eklemek kolay olur
- onlarca self.field ile tutorial.py dağılmaz

## Success ve Failure Evaluation Nasıl Tasarlanmalı

Her lesson tek bir dev if/elif ile çözülmemeli.
Bunun yerine condition registry mantığı daha temiz olur.

Önerilen yaklaşım:

- lesson içinde success_condition string'i var
- TutorialMode içinde bu string'i evaluator method'a map ediyorsun

Örnek:

```python
SUCCESS_EVALUATORS = {
  "move_left_right_counts": self._eval_move_counts,
  "rotate_three_times": self._eval_rotate_counts,
  "no_holes_after_lock": self._eval_no_holes_after_lock,
}
```

Aynı mantık failure_condition için de uygulanmalı.

Bu neden önemli:

- lesson tanımı veri olarak kalır
- gameplay kontrol kodu method bazlı okunabilir olur

## Board Senaryoları Nasıl Üretilecek

Board senaryoları raw grid olarak tutulabilir ama bakım zorlaşabilir.
Bu yüzden mümkünse helper builder kullanmak daha iyi.

Örnek yaklaşım:

```python
def empty_grid(width=10, height=20):
  return [[None for _ in range(width)] for _ in range(height)]

def with_filled_cells(grid, coords, color=(100, 100, 100)):
  for x, y in coords:
    grid[y][x] = color
  return grid
```

Sonra senaryo builder'lar bu helper'ları kullanır.

Bu tercih iyi olur çünkü:

- senaryo okunur kalır
- aynı board varyantlarını değiştirmek kolay olur

## Progress Persistence Nasıl Bağlanacak

user_manager tarafında minimum riskli strateji şu olmalı:

1. Kullanıcı load edilirken tutorial_progress alanı yoksa default oluştur.
2. Ders bitince tutorial_progress güncellenir.
3. Eğer giriş seviyesi lesson'lar tamamlandıysa tutorial_completed True yapılır.
4. Eski sistemde tutorial_completed True ama tutorial_progress boşsa, basics chapter'ı tamamlanmış kabul etmek zorunda değiliz.
5. En güvenlisi, eski kullanıcıya progress default verip tutorial_completed flag'ini korumaktır.

Yani migration agresif olmamalı.

## Menü ve Akış Kararları

Ürün açısından en güvenli akış şu:

İlk sürüm:

- Menudeki Eğitim butonu aynı kalsın
- Tıklayınca tutorial ilk lesson ile başlasın
- Ders bittiğinde otomatik ilerlesin

İkinci sürüm:

- Eğitim ana ekranı gelsin
- Bölümler listelensin
- Oyuncu bölüm seçebilsin
- İlerleme ve yıldızlar gösterilsin

Bu iki aşamalı yaklaşım scope kontrolü için çok önemlidir.

## Test Planı Nasıl Olmalı

Bu işte tam otomatik test yazmak her aşamada kolay olmayabilir.
Bu yüzden hibrit test planı gerekir.

### Kod Seviyesi Testler

Yazılabilecek güvenli testler:

- tutorial_progress helper'ları
- lesson lookup ve lesson order logic'i
- scenario builder helper'ları
- success/failure evaluator'ların saf veri kullanan kısımları

### Manuel Smoke Testler

Her büyük patch sonrası şu checklist çalıştırılmalı:

1. Eğitim modu ana menüden açılıyor mu
2. Mevcut ilk lesson yükleniyor mu
3. Ders tamamlanınca bir sonraki derse geçiyor mu
4. ESC ve çıkış akışı bozuldu mu
5. Tutorial bittiğinde kullanıcı tamamlandı olarak işaretleniyor mu
6. Kaydedilen progress oyunu kapatıp açınca korunuyor mu
7. Yeni board lesson'larda senaryo doğru yükleniyor mu
8. Kart dersi varsa seçim overlay'i açılıyor mu

### Faz 3 Kart Testleri

Ek olarak:

1. Gösterilen kartlar lesson tanımındaki kartlarla birebir aynı mı
2. Doğru seçim açıklaması geliyor mu
3. Yanlış seçimde fallback açıklama bozulmadan geliyor mu

## Done Kriterleri Nasıl Tanımlanmalı

Her faz için kod yazıldı demek yetmez.
Done kriteri açık olmalı.

Faz 1 done:

- tutorial lesson verisi ayrı dosyada
- eski tutorial akışı bozulmamış
- user progress alanı kaydedilebiliyor

Faz 2 done:

- yeni board lesson'lar oynanabiliyor
- yıldız ve sonuç mantığı çalışıyor
- en az bir failure feedback görünür

Faz 3 done:

- en az üç kart kararı senaryosu oynanabiliyor
- seçim sonrası değerlendirme geliyor
- kart öğretimi gerçek board bağlamında yapılıyor

Faz 4 done:

- chapter seçimi veya eğitim hub çalışıyor
- rehberden en az bir tutorial açılabiliyor

## Bilinçli Olarak Ertelenecek Şeyler

Bu maddeler erken fazlarda yapılmamalı:

- Tam mentor karakter sistemi
- Sesli anlatım
- Çok detaylı analitik telemetri
- Kart sistemi için ayrı alternatif runtime
- Tüm diller için aynı anda tam localization
- Rehber ekranını baştan aşağı redesign etmek

Bu ertelemeler zayıflık değil, scope disiplinidir.

## En Doğru Başlangıç Kararı

Bu planı kodlamaya şimdi başlayacaksak ilk gerçek commit seti şu mantıkla hazırlanmalı:

1. Veri modeli çıkar
2. Progress helper'ı çıkar
3. Eski 7 adımı yeni modele taşı
4. Davranışı koru
5. Sonra yeni içerik ekle

Bu sırayı korursak proje güvenli büyür.
Bu sırayı bozarsak tutorial refactor ile içerik geliştirme birbirine girer.

## Somut Backlog Önerisi

### Backlog A: Mimari

- TutorialMode'u lesson-driven yapıya taşımak
- Eğitim ilerleme modelini kullanıcı verisine eklemek
- Ders tanımlarını ayrı dosyaya almak

### Backlog B: İçerik

- 6 temel ders
- 6 board mantığı dersi
- 3 kart kararı dersi
- 1 karma final dersi

### Backlog C: UI

- Ders seçme ekranı
- Hedef listesi
- Sonuç ekranı
- Kart karar açıklama paneli

### Backlog D: Progression

- Bölüm kilit açma
- Yıldız sistemi
- Ders tekrar oynama
- Tamamlanma özeti

## Önerilen İlk Uygulama Sırası

En güvenli geliştirme sırası şu olur:

1. Mevcut tutorial'ı bozmadan lesson veri modelini hazırlamak
2. Eski 7 adımı yeni lesson sistemine taşımak
3. Board okuma derslerini eklemek
4. Progress ve yıldız katmanını eklemek
5. Kart akademisi MVP'sini eklemek
6. Rehber entegrasyonunu yapmak

Bu sıra önemli çünkü önce temel iskelet kurulursa kart akademisi daha temiz oturur.

## Nihai Tavsiye

Bu iş için en doğru ürün kararı şudur:

Eğitim modu tek bir kısa öğretici sahne olmaktan çıkmalı ve oyunun ikinci ana ürünü haline gelmelidir.

Quadrix'in temel kontrol öğretimi zaten çözülebilir durumda.
Asıl değer, oyuncuya şu zihinsel modeli öğretmekten gelir:

- Board'u oku
- Riski fark et
- Kaynaklarını yönet
- Kartı board'a göre seç
- Kısa vadeli kurtuluş ile uzun vadeli değer arasında karar ver

Bu dönüşüm yapılırsa eğitim modu yalnızca yeni oyuncu onboarding aracı olmaz.
Aynı zamanda Kart Ustalığı ve ileri oyun anlayışı için kalıcı bir öğretici sistem haline gelir.

## Hızlı Özet

- Mevcut tutorial iyi bir başlangıç ama fazla dar
- Kart sistemi eğitim için çok güçlü bir hazır altyapı sunuyor
- Rehber ekranı statik, eğitimle entegre edilmeli
- En kritik değişim tuş öğretiminden karar öğretimine geçmek
- En doğru teknik yön veri odaklı lesson tabanlı mimariye geçmek
- En doğru MVP: temel dersler + board okuma + 3 kart karar senaryosu

## Sonraki Adım Önerisi

Bu dokümana göre geliştirmeye başlanacaksa en mantıklı ilk uygulama adımı şudur:

- önce tutorial lesson mimarisi tasarlanmalı,
- sonra mevcut 7 adım bu yeni sisteme taşınmalı,
- ardından board okuma dersleri ve kart akademisi MVP'si eklenmelidir.
