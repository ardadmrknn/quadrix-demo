# FullMetalPomak Instagram Tester Geri Bildirimleri — Quadrix Kod Tabanı Analizi

> **Bu belgenin kaynağı `v2` deposudur.** `quadrix-demo`'ya kopyalanma nedeni: aşağıdaki bulgular **demo kodunda da geçerlidir** (2026-11-05 doğrulaması). Belgedeki `file:///` bağlantıları ve satır numaraları **v2** ağacına aittir.
>
> **Demo'da doğrulanan karşılıklar:**
>
> | Bulgu | v2 konumu | Demo konumu |
> | :--- | :--- | :--- |
> | `show_ghost` ayarı okunmuyor | `src/game.py:5928` | [`src/game.py:5546`](../../quadrix-demo/src/game.py#L5546) |
> | Ghost parçanın kendi rengiyle çiziliyor | `src/game.py:5943` | [`src/game.py:5561`](../../quadrix-demo/src/game.py#L5561) |
> | Maks. 3 ardışık parça filtresi | `src/game.py:1451` | [`src/game.py:1357`](../../quadrix-demo/src/game.py#L1357) |
> | Workshop parçaları torbaya giriyor | `src/game.py:2154` | [`src/game.py:2043`](../../quadrix-demo/src/game.py#L2043) |
>
> Ölçüm betikleri demo ağacında yoktur; ölçümler `v2/scratch/` altındadır.


**İnceleme tarihi:** 4 Kasım 2026  
**Kaynak konuşma:** [`tester insatgram konuşmaları/message_1.html`](../tester%20insatgram%20konus%CC%A7malar%C4%B1/message_1.html)  
**Konuşma:** `burak_ysyn` ↔ `FullMetalPomak`  
**Kapsam:** Sohbette oyunla ilgili geçen tüm gözlemler, istekler, şikâyetler, olumlu sinyaller ve bunların mevcut Quadrix kaynak koduyla çapraz kontrolü.

> Bu belge yalnızca araştırma ve analiz içindir. Bu inceleme sırasında `src/`, `tests/` veya başka bir ürün kodu değiştirilmemiştir. Çalışma ağacında inceleme başlamadan önce mevcut olan kullanıcı değişiklikleri korunmuştur.

## 0. İlişkili belgeler — aynı kaynak sohbetin üç analizi

Bu belge, `message_1.html` sohbetinin **üç ayrı analiz turundan** biridir. Üçü de aynı ham veriyi işler; farkları kapsam ve yaklaşımdadır:

| Belge | Başlık sayısı | Yaklaşım | Bu belgede olmayan içerik |
| :--- | ---: | :--- | :--- |
| **Bu belge** (`TESTER_INSTAGRAM_FEEDBACK_ANALIZI_TR.md`) | 16 | Temkinli — "kodda mevcut" ile "oyuncuda doğrulanmış" ayrı tutulur, hüküm öncesi saha testi ister | — |
| [`fullmetalpomak_feedback_analizi.md`](fullmetalpomak_feedback_analizi.md) | 13 | Ölçüm odaklı — kritik iddialar gerçek `Game` nesnesiyle ampirik doğrulanır | **#12 SRS/SRS+** ve **#13 Speedrun denetimi** (bu sohbette yok, ayrı kaynaklardan) |
| [`ikinci_geri_bildirim_seti_analizi.md`](ikinci_geri_bildirim_seti_analizi.md) | 14 | Karşılaştırmalı — başka bir oyuncunun (`aboooo/`) bağımsız bulguları | **Cascade bozukluğu, O spawn, hold oryantasyonu, mini T-spin puanı, kombo off-by-one** ve 5 konuda bağımsız teyit |

### 0.1 Yalnızca bu belgede bulunan ve doğrulanmış 3 bulgu

Bu üç konu diğer iki belgede **yok**; kodla doğrulandı:

| # | Bulgu | Kod kanıtı | Durum |
| :--- | :--- | :--- | :--- |
| **1** | **`show_ghost` ayarı ghost çizimine bağlı değil.** Ayar modelde, UI'da ve lokalizasyonda mevcut; `game.py` içinde **hiç okunmuyor**. Ghost `effects_enabled` kontrolüyle koşulsuz çiziliyor. | Ayar: [`settings_manager.py:369`](../src/settings_manager.py#L369), [`settings_screen_tabbed.py:287`](../src/settings_screen_tabbed.py#L287), [`graphics_menu.py:42`](../src/graphics_menu.py#L42) · Çizim: [`game.py:5928`](../src/game.py#L5928) (`if not self.game_over and self.effects_enabled:`) | **Kesin tutarsızlık** — oyuncu ayarı kapatır, ghost kaybolmaz |
| **2** | **Aynı parça tipinde maksimum 3 ardışık kısıtı** torba sırasını bozuyor. | [`game.py:1451`](../src/game.py#L1451) `_max_consecutive_same_piece = 3`, [`game.py:2126`](../src/game.py#L2126) `_would_exceed_max_consecutive`, [`game.py:2187-2212`](../src/game.py#L2187) seçim döngüsü indeksleri atlıyor | **Kesin** — "7 milyonda her tip tam 1/7" iddiası bu filtre yüzünden geçersiz |
| **3** | **Workshop parçaları torbaya otomatik girer** → oyun içi dağılım sabit değil, havuz büyüklüğüne bağlı. | [`game.py:2154`](../src/game.py#L2154) `_get_workshop_piece_factories()` → `_refill_piece_bag` içinde `base + workshop` birleştiriliyor | **Kesin** — dağılım atölye içeriğine göre değişir |

### 0.2 Bu belgenin doğruladığı, diğerlerinin de işlediği ortak nokta

**Clear/fall animasyonunda ayrı bir senkron noktası:** `line_clear_animation` 30 karelik bir flash sayacı ([`game.py:3829`](../src/game.py#L3829)), ama `_line_clear_animation_active()` kararını bu sayaçtan **değil** sweep/falling listelerinden veriyor ([`game.py:5262-5274`](../src/game.py#L5262)). İki ayrı zaman çizelgesi. Bu, ikinci belgedeki #D (ARE) ve ana belgedeki #7 ile aynı kökü paylaşır.

### 0.3 Karşılaştırmalı öncelik hükmü

Üç belge birlikte okunduğunda öncelik sırası şudur:

1. **Cascade modu** — yalnızca ikinci belgede; bir modu oynanamaz kılıyor (P0)
2. **SRS I tablosu** — üç belgede de var (bu belgede D-pad/rotation bağlamında kısmen); en çok teyitli sorun (P0)
3. **Clear/fall senkronu** — üçünde de var; bu belge **dört olayın ayrı ölçülmesini** öneren en titiz doğrulama planını sunuyor (P0)
4. **Lock out / buffer zone** — ana + ikinci belgede; bu belgede "spawn algısı" olarak geçiyor, "kesin bug" olarak işaretlenmemiş (P0)
5. **`show_ghost` bağlantısı** — yalnızca burada; düzeltmesi en kolay (3 satır), etkisi net (P1)

## 1. İnceleme yöntemi ve kanıt sınırları

- Instagram dışa aktarımındaki **132 mesaj bloğu** kronolojik olarak okunmuştur.
- Oyunla ilgisiz selamlaşma, arama ve kısa tepki mesajları ayrıştırılmış; ancak bir feedback’in anlamını tamamlayan kısa yanıtlar bağlamda tutulmuştur.
- Dört fotoğraf ve iki video mesaj içindeki medya bağlantılarıyla eşleştirilmiştir. Buna ek olarak kullanıcının verdiği iki uzun Instagram ekran görüntüsü tam çözünürlükte (1220×22361 ve 1220×22485) parçalara bölünerek yakınlaştırılmış ve okunmuştur.
- Videoların teknik bilgisi `ffprobe` ile kontrol edilmiştir: ikisi de **360×640 portre video**, süreleri yaklaşık **45,93 sn** ve **24,80 sn**’dir. Kare örnekleri incelendiğinde ilk video Game Modes ekranını, ikinci video ana dashboard/menü ekranını göstermektedir.
- Kod referansları mevcut dosyalardaki satır numaralarıyla verilmiştir. Satır numaraları rapor yazıldığı andaki çalışma ağacına aittir.
- “Kodda mevcut” ile “oyuncu deneyiminde doğrulanmış” ayrılmıştır. Özellikle Campaign 17’nin kesin olarak imkânsız olduğu iddia edilmemiş; bunun yeniden oynanması gereken bir denge/uygulanabilirlik riski olduğu belirtilmiştir.

## 2. Yönetici özeti

Tester’ın yaklaşık 15 dakikalık gerçek oynanıştan sonra verdiği geri bildirimler; okunabilirlik, HUD akışı, clear/fall senkronu, spawn geometrisi, rastgeleleştirme sözleşmesi ve yönlendirme/ürün katmanlarında yoğunlaşıyor:

1. **Oyun içi okunabilirlik:** Neon görünüm beğeniliyor; fakat mor arka plan ile mor T parçası birbirine yaklaşınca aktif parçanın konumu ve outline’ı hızlı oyunda ayırt edilemiyor.
2. **Next/Hold ve clear/fall akışı:** Next parçaları küçük bulunuyor; Hold düzeni beklenenden farklı. Clear sweep’i, blok düşüşü, yeni parça ve puan bildirimleri eşzamanlı algıda akışkanlığı bozabiliyor.
3. **Spawn geometrisi:** Parçanın görünür tahta dışından doğduğu algısı oluşuyor; 20×10 görünür alan ile gizli spawn satırlarının oyuncuya yansıması yeniden doğrulanmalı.
4. **Randomizer sözleşmesi:** Tester, 7 milyon çekişlik istatistik doğrulaması ve modern 7’li bag beklentisi soruyor; mevcut kod 7 standart parça için 3 kopyalı 21 elemanlı tek torba kullanıyor.
5. **Campaign hedefi ve zorluk kalibrasyonu:** 17. seviyedeki iki Quadrix hedefi, sınırlı hamle bütçesi içinde uygulanabilirlik açısından sorgulanıyor. Tester hedefi ilk anda anlamamış; görev açıklamasının oyun akışında daha görünür ve yönlendirici olması gerekiyor.
6. **Ürün yönlendirmesi ve ana menü bilgi mimarisi:** Çok sayıda mod olmasına rağmen “ana mod ne, hedef ne?” sorusu ortaya çıkıyor. Asimetrik dashboard kartları kasıtlı olsa da bu niyet oyuncu için yeterince açık değil.

İkincil bulgular: 8BitDo Xbox/XInput cihazında D-pad ve kontrol gösterimi için cihaz bazlı QA ihtiyacı, Block Styles ekranında 3–5 hazır stil isteği ve test sırasında Lunar bakiyesinin yetmemesi. Lunar gözlemi tek başına ekonomi dengesizliği kanıtı değildir.

Olumlu sinyaller de güçlüdür: Tester oyunu yaklaşık 15 dakika oynamış, neon estetiği beğenmiş, “süper” ve “kral idealinde” gibi olumlu ifadeler kullanmış, kör oynanış videosu ve kontrol ekranı görüntüleri göndermiş, ayrıca tekrar oynayabileceğini belirtmiştir. Bu, sorunların oyunun temel fikrinden çok okunabilirlik, yönlendirme ve denge katmanında toplandığını düşündürür.

## 3. Önceliklendirme

| Öncelik | Konu | Neden |
|---|---|---|
| **P0/P1** | Aktif T parçası, outline ve kontrast | Tetris oynanışında parça tanıma doğrudan karar hızını etkiliyor; tester bunu hızlı oyunda yaşadığını söylüyor. |
| **P0/P1** | Next/Hold boyutu ve yerleşimi | Parça okuma akışı bozuluyor; tester açıkça beklenen düzeni tarif ediyor. |
| **P0/P1** | Campaign 17 hedef/hamle uygulanabilirliği | Somut seviye, somut Quadrix hedefi ve somut hamle bütçesi var; yeniden oynanabilir test gerektiriyor. |
| **P1** | Görevlerin keşfedilebilirliği | Görev kodda mevcut ve çiziliyor, fakat tester hedefi ancak sonradan anlıyor. |
| **P1** | Ana menü yönlendirmesi | Çok seçenekli yapı, ana mod ve oyunun amacı konusunda belirsizlik yaratıyor. |
| **P2** | 8BitDo/XInput cihaz QA’sı | Kodda genel destek var; konuşma belirli donanımda doğrulama ihtiyacını gösteriyor. |
| **P2** | Hazır Block Styles kataloğu | Mevcut ekran parça başına Default/Custom sunuyor; tester 3–5 seçilebilir hazır stil istiyor. |
| **P2** | Lunar yeterliliği | Tek bir test akışındaki “yetmedi” gözlemi var; kullanım ve fiyat verisi olmadan denge hükmü verilemez. |

## 4. Ayrıntılı feedback analizi

### 4.1 Neon estetik beğeniliyor; T parçası ve outline hızlı oyunda seçilemiyor

**Konuşma kanıtı — 12:18, mesajlar 005–012:**

- Tester: **“2 tane takıldığım şey oldu”**
- Tester: **“Neon estetik çok iyi ama, arkaplan mor t taş da benzer renkte ya, hızlı oynucam dersem clarity sorun oluyor”**
- Tester: **“Zor seçiyorum t nin nerede olduğunu”**
- Tester: **“Görünmüyo outline”**
- Geliştirici: **“Arka plan opaklığını azaltıp arttırabiliyorsunuz / Ayarlardan”**
- Tester: **“Süper”**

**Kod karşılığı:**

- Aktif parça [src/game.py:5975-6002](../src/game.py#L5975) içinde çiziliyor ve `draw_textured_block` kullanıyor.
- Normal blok için ortak çizim yolu [src/game.py:2405-2422](../src/game.py#L2405) içinde `draw_jelly_block` çağırıyor.
- Texture kullanan bloklarda border yolu [src/game.py:2430-2444](../src/game.py#L2430) mevcut.
- Ghost parça çizimi [src/game.py:5926-5973](../src/game.py#L5926) içinde yalnız `effects_enabled` açıkken çalışıyor. Texture ghost için alpha 80, fallback ghost için alpha 50 ve 2 px renk border kullanılıyor ([5928-5972](../src/game.py#L5928)).
- Ayarlarda `show_ghost` seçeneği tanımlı ([src/settings_screen_tabbed.py:285-290](../src/settings_screen_tabbed.py#L285)), değeri okunuyor ([src/settings_screen_tabbed.py:1215-1218](../src/settings_screen_tabbed.py#L1215)), ayrıca varsayılanı `True` ([src/settings_manager.py:369](../src/settings_manager.py#L369)). Buna rağmen `src/game.py` içindeki ghost çizim yolu `show_ghost` değerini okumuyor; `effects_enabled` kontrolüne bağlı kalıyor.
- Arka plan, efekt ve menü şeffaflığı ayarları [src/settings_screen_tabbed.py:292-307](../src/settings_screen_tabbed.py#L292) ve runtime değer atamaları [src/settings_screen_tabbed.py:3051-3058](../src/settings_screen_tabbed.py#L3051) ile mevcut.

**Analiz:**

Bu geri bildirim “outline hiç implement edilmemiş” şeklinde okunmamalı; kodda border çizimi var. Sorun, oyuncunun gerçek görüşünde border’ın renk yakınlığı, ghost alpha’sı, neon efekt yoğunluğu ve mor arka planla birleştiğinde yeterli ayrımı üretememesi. Tester’ın “hızlı oynayacaksam” vurgusu bunu kozmetik bir tercih olmaktan çıkarıp oynanış okunabilirliği problemine dönüştürüyor.

Ayrıca ayarlarda görünen `show_ghost` seçeneği ile çizim davranışı arasında doğrulanabilir bir tutarsızlık var: seçenek kullanıcıya ghost’u kontrol ediyormuş gibi sunuluyor, fakat `game.py` bu ayarı kullanmıyor. Bu, rapordaki en güçlü kod destekli bulgulardan biridir.

**Doğrulama durumu:**

- Neon estetik beğenisi: **konuşma ile doğrulandı**.
- T/mor arka plan kontrast sorunu: **gerçek oynanış gözlemiyle doğrulandı**.
- Outline’ın kodda bulunmadığı iddiası: **yanlış; kodda border yolu var**.
- `show_ghost` ayarının ghost çizimine bağlandığı iddiası: **kod tarafından doğrulanmıyor; tersine bağlantı görünmüyor**.

**İnceleme önerisi:** Varsayılan renk/arka plan kombinasyonları, ghost border kalınlığı ve `show_ghost` ayarının gerçek çizim davranışı birlikte ele alınmalı. Değişiklik öncesi ve sonrası hızlı T parçası senaryosu ile ekran görüntüsü veya kısa oynanış karşılaştırması alınmalı.

### 4.2 Next piece küçük; oyuncu parçayı çevresel görüşle tanımak istiyor

**Konuşma kanıtı — 12:19–12:20, mesajlar 013–028:**

- Tester: **“Bir de next piece”**
- Tester: **“Küçük”**
- Tester: **“Kral idealinde bana kalırsa / Vizyonumun odaksız kısmında / Rengi gözümün ısırıp / Ne taş gelceğini anlamam lazım / Bakmaya gerek olmadan”**
- Donanım bağlamı: **“24 ve 43, iki tane var”**, **“1080 :(”**

**Kod karşılığı:**

- Sağ HUD geometrisi [src/game.py:460-499](../src/game.py#L460) içinde tahtanın sağına yerleştiriliyor; panel genişliği ekran ve layout sınırlarıyla kısıtlanıyor.
- Next başlığı ve iki next kutusu [src/game.py:6102-6120](../src/game.py#L6102) içinde çiziliyor.
- Next kutusu boyutu içerik genişliğine ve `hud_scale` değerine bağlı; hedef boyut `96 * pixel_ratio` ile `66 * hud_scale` arasındaki sınıra sokuluyor ([src/game.py:6110-6113](../src/game.py#L6110)).
- İki kutu yan yana çiziliyor ve parçalar kutu içindeki bütçeye göre küçültülüyor ([src/game.py:6116-6168](../src/game.py#L6116)).

**Analiz:**

Kodda iki next parçası destekleniyor; sorun bilgi miktarının varlığı değil, okunabilirlik bütçesi. Tester’ın istediği şey “ekrana bakıp ayrıntılı incelemek” değil, parçayı odak dışı görüşte renk ve silüetinden tanımak. İki küçük kutunun aynı anda gösterilmesi, özellikle 1080 yüksekliğinde ve uzaktan izlenen 43 inç ekranda parçanın görsel ağırlığını azaltabilir. Bu gözlem, kullanıcıdan gelen gerçek donanım bağlamıyla birlikte değerlendirilmelidir; 24 ve 43 inç ekranların fiziksel izleme mesafesi bilinmediği için tek bir evrensel piksel eşiği çıkarılamaz.

**İnceleme önerisi:** Next kutularının fiziksel ekran boyutuna göre değil, etkili görüş mesafesi ve oyuncunun hızlı tanıma süresine göre değerlendirilmesi; silüet, renk ve kutu boyutu birlikte test edilmelidir. Bir sonraki parça ile ikinci sonraki parçanın hiyerarşisi de ayrı bir karar noktasıdır.

### 4.3 Hold/Next yerleşimi beklenen akışla uyuşmuyor

**Konuşma kanıtı — 12:21–12:27, mesajlar 030–042:**

- Tester: **“Holdun solda, direkt sonraki next piecein sağda büyük olmasını”**
- Tester: **“Hold garip yerde sizde”**
- Tester: **“Sanki 3. Taşımmış gibi”**
- Geliştirici: **“Nedense sizde hold yazısı yanlış yerde durmus kayma olmuş”**
- Geliştirici ekran görüntüsü/video ister; tester oynarken kör video çektiğini söyler.

**Kod karşılığı:**

- Mevcut sağ HUD önce Next başlığını ve iki Next kutusunu çiziyor ([src/game.py:6102-6170](../src/game.py#L6102)).
- Hold etiketi ve kutusu Next bölümünün altında çiziliyor ([src/game.py:6172-6249](../src/game.py#L6172)).
- Hold kutusu `content_x` hizasından başlıyor; kodda aynı `hold_box_rect` ataması iki kez tekrarlanıyor ([src/game.py:6247-6249](../src/game.py#L6247)). Bu tek başına görsel bug kanıtı değildir, fakat yerleşim hesabının incelenmesi gereken bir kod kokusudur.
- İkinci Hold cebi varsa panel dar olduğunda sağa sığmazsa alta stack ediliyor ([src/game.py:6283-6309](../src/game.py#L6283)).
- HUD paneli tahtanın sağına zorlanıyor ([src/game.py:464-475](../src/game.py#L464)).

**Analiz:**

Tester’ın tarif ettiği beklenen bilgi mimarisi “Hold solda, öne çıkan Next sağda” şeklinde. Mevcut temel akış ise aynı sağ panel içinde **Next üstte, Hold altta**. Dolayısıyla bu yalnızca bir etiket kayması değil, panelin görsel önceliklendirmesiyle oyuncunun zihinsel modeli arasındaki uyumsuzluk olabilir. Geliştiricinin “sizde hold yazısı yanlış yerde durmus” demesi belirli çözünürlük/ölçek kombinasyonunda ek bir konumlandırma sapması olabileceğini gösteriyor.

**Doğrulama durumu:**

- Mevcut kodun Next’i Hold’un üstünde çizdiği: **doğrulandı**.
- Tester’ın istediği Hold solda/Next sağda düzeninin mevcut kodda olduğu: **doğrulanmadı; temel kod akışı bunu göstermiyor**.
- Belirli 24/43 inç 1080 düzeninde etiket kaymasının her zaman oluştuğu: **kanıtlanmadı; tester görüntüsü ve kod sinyali var, yeniden üretim gerekir**.

**İnceleme önerisi:** 1920×1080, 24 inç ve 43 inç izleme mesafeleriyle HUD ekran görüntüsü alınmalı; etiket, kutu ve parça silüetlerinin birbirine göre hiyerarşisi ölçülmeli.

### 4.4 Blind oynanış videosu geri bildirimlerin gerçek kullanım kanıtı olduğunu gösteriyor

**Konuşma kanıtı — mesajlar 041–048:**

- Geliştirici ekran görüntüsü ister: **“Görsel olarak sizde nasıl duracağını anlayıp ona göre geliştiririm”**.
- Tester: **“Blind video çektim zaten / Oynarken”**.
- Geliştirici: tester’ın önerilerini ilk yapılacaklar listesine alacağını belirtir.

**Medya:**

- `videos/1188212720355106.mp4` — yaklaşık 45,93 sn. Kare örneklerinde Game Modes menüsü görülüyor.
- `videos/1661597162339016.mp4` — yaklaşık 24,80 sn. Kare örneklerinde dashboard/ana menü görülüyor.

**Analiz:**

Bu kayıtlar, feedback’in menüye bakıp yapılan soyut bir tasarım yorumundan ibaret olmadığını; oyuncunun oynarken fark ettiği akış problemlerine dayandığını gösteriyor. Özellikle Next/Hold ve aktif parça okunabilirliği için oynanış sırasında alınmış gözlem, statik ekran görüntüsünden daha değerlidir.

### 4.5 Block Styles: 3–5 hazır stil isteği

**Konuşma kanıtı — 12:35–12:36, mesajlar 055–060:**

- Tester: **“Ayarlasaydınız ya 3-5 tane premade stil”**.
- Geliştirici: şu anda toplam iki stil olduğunu, istenirse artırabileceğini söylüyor.
- Geliştirici ayrıca mağazada çok içerik olduğunu belirtir.

**Medya:**

- `photos/28959238020385411` — Block Styles ekranı. Ekranda parça satırlarında `Default` ve `Custom` seçenekleri, sağda parça önizlemeleri ve dikey liste görülüyor.

**Kod karşılığı:**

- Block Styles ekranı [src/menu.py:11319-11418](../src/menu.py#L11319) içinde her parça için kart, Default/Custom butonları ve önizleme çiziyor.
- Özel renk/texture akışı `draw_uniform_button` ve özel önizlemeyle [src/menu.py:11366-11398](../src/menu.py#L11366) kuruluyor.
- Önizleme renderer’ı [src/menu.py:11422-11450](../src/menu.py#L11422) içinde parça geometrisini ve rengi çiziyor.
- [src/block_styles.py:12-14](../src/block_styles.py#L12) yedi temel ve dört ek parça adını tanımlıyor; [src/block_styles.py:121-146](../src/block_styles.py#L121) ise ayarlardan parça başına custom color/texture yükleyen yöneticiyi içeriyor. Bu yüzeyde 3–5 adlandırılmış hazır tema kataloğu görünmüyor.

**Analiz:**

Mevcut ürün yüzeyi “parça başına varsayılan veya özel görünüm” sunuyor. Tester’ın talebi ise oyuncuya birden fazla bütünsel, hazır, hızlı seçilebilir stil vermek. Bu nedenle öneri mevcut custom renk düzeninin tekrarı değil; ürün düzeyinde hazır tema/preset katalog ihtiyacıdır.

**Doğrulama durumu:**

- Default/Custom yüzeyi: **kod ve fotoğrafla doğrulandı**.
- 3–5 hazır stil kataloğunun mevcut olmadığı: **incelenen Block Styles ve BlockStyleManager yüzeyinde doğrulandı**.
- Tester’ın bunu zorunlu bug olarak gördüğü: **hayır; açık ürün isteği olarak sınıflandırılmalı**.

### 4.6 Lunar yetersizliği: ekonomi sinyali var, denge hükmü yok

**Konuşma kanıtı — 12:36, mesaj 061:**

- Tester: **“Lunarım yetmedi”**.

Konuşmanın devamında geliştirici, test akışında Lunar yüklemesi yapmayı ve parça atölyesinin bol Lunar gerektireceğini söyler. Bu, tester’ın mağaza/özelleştirme akışında kaynak sınırına çarptığını gösterir.

**Analiz:**

Bu tek gözlem şu iddiaları kanıtlamaz:

- Lunar ekonomisinin genel olarak dengesiz olduğu,
- fiyatların tüm kullanıcılar için çok yüksek olduğu,
- ödül temposunun yetersiz olduğu.

Bunun kanıtlanması için tester’ın başlangıç bakiyesi, hangi ürünü/kaç ürünü almaya çalıştığı, fiyat, kazanma süresi ve aynı akışın tekrarları gerekir. Raporlama düzeyi “kaynak erişimi/deney akışı sürtünmesi” olmalıdır.

### 4.7 Campaign görev hedefi ilk anda anlaşılmıyor

**Konuşma kanıtı — 12:38–12:42, mesajlar 063–070:**

- Geliştirici: **“Görevlerden dolayı geçemediniz ikili satır temizleme istiyordu”**.
- Tester: **“Evet sonradan anladım”**.
- Tester: **“Keşfediyorum / Blind kere blind”**.
- Geliştirici tekrar oynama ve Lunar desteği önerir.

**Kod karşılığı:**

- Campaign görevleri level config’ten oluşturuluyor ([src/campaign/campaign_mode.py:528-539](../src/campaign/campaign_mode.py#L528)).
- Sol bilgi paneli görevleri çiziyor; açıklamalar en fazla iki satıra sarılıyor ([src/campaign/campaign_mode.py:1694-1835](../src/campaign/campaign_mode.py#L1694)).
- Görev ilerlemesi açıklama altında gösteriliyor ([src/campaign/campaign_mode.py:1822-1845](../src/campaign/campaign_mode.py#L1822)).
- Kalan blok bütçesi ve varsa kalan süre ayrıca gösteriliyor ([src/campaign/campaign_mode.py:1946-2012](../src/campaign/campaign_mode.py#L1946)).
- Görev tamamlanması oyun event’leriyle kontrol ediliyor ([src/campaign/campaign_mode.py:801-838](../src/campaign/campaign_mode.py#L801)).

**Analiz:**

Kodda görev verisi ve görev HUD’ı mevcut. Buna rağmen oyuncunun “sonradan anladım” demesi, problemin görevlerin yokluğu değil; ilk bakışta önceliğinin, açıklık derecesinin veya oyun sırasında yeterince görünür geri bildirim vermesinin zayıf olabileceğini gösteriyor. Özellikle “ikili satır temizleme” gibi Tetris terminolojisine dayanan hedeflerin yeni oyuncu için ne anlama geldiği net olmayabilir.

Bu nedenle bulgu “Campaign objective missing” değildir. Doğru tanım: **objective exists, but objective comprehension/discoverability is weak in the observed run**.

### 4.8 Campaign 17: iki Quadrix için hamle bütçesi sorgulanıyor

**Konuşma kanıtı — 12:49–12:53, mesajlar 087–105:**

- Geliştirici zorluk düşük geliyorsa bildirilmesini ister ve Türkiye’de Tetris oynayan tester bulmanın zor olduğunu söyler.
- Geliştirici oyunun çok nerflendiğini ve ayrı bir sistem düşündüklerini belirtir.
- Tester: **“17de takıldım demin”**.
- Tester: **“2 quadrix istiyor 17 hamlede”**.
- Tester: **“Görece boş tahtada 17 18 taşla 2 quadrix kolay değil”**.
- Tester ayrıca şu alternatifi önerir: **“Hamle sayısı yerine bana kalırsa süreli yapın… açılış ekranına bir seviye tespit sınavı… easy normal hard… Pieces per second ölçerseniz”**.
- Geliştirici Campaign için zorluk formülü bulunduğunu ve bazı levellarda sorun fark ettiklerini kabul eder.

**Kod karşılığı:**

- Level 17 açık override ile `move_limit: 23`, ikinci yıldız için `18` hamle ve üçüncü yıldız için `85` saniye kullanıyor ([src/campaign/level_data.py:539](../src/campaign/level_data.py#L539)).
- Genel blok limiti `req/tightness` modelinden hesaplanıp 15–120 aralığına sıkıştırılıyor ([src/campaign/level_data.py:100-120](../src/campaign/level_data.py#L100), [src/campaign/difficulty_model.py:238-246](../src/campaign/difficulty_model.py#L238)).
- Campaign her parça kilitlendiğinde `moves_count` artırıyor ([src/campaign/campaign_mode.py:710-714](../src/campaign/campaign_mode.py#L710)).
- Limit dolduğunda görevler tamamlanmadıysa level başarısız oluyor ([src/campaign/campaign_mode.py:790-795](../src/campaign/campaign_mode.py#L790)).
- LevelConfig hem `time_limit` hem `move_limit` alanlarını destekliyor ([src/campaign/level_data.py:49-64](../src/campaign/level_data.py#L49)); Campaign runtime’da süre limiti de kontrol ediliyor ([src/campaign/campaign_mode.py:667-671](../src/campaign/campaign_mode.py#L667)).

**Analiz:**

Bu, rapordaki en somut denge test adaylarından biridir: belirli level, belirli Quadrix hedefi ve belirli parça/hamle bütçesi vardır. Ancak kaynak kod tek başına “level kesin imkânsız” sonucunu vermez. Parça RNG’si, oyuncunun becerisi, Hold kullanımı, hedefin nasıl sayıldığı ve gerçek tahta durumu deterministik oynanarak ölçülmelidir.

Tester’ın “hamle yerine süre” önerisi doğrudan uygulanmış bir bug düzeltmesi değil, tasarım alternatifidir. Mevcut sistem zaten hem süre hem hamle sınırını desteklediği için, bu öneri için yeni altyapıdan önce level bazında A/B dengeleme yapılabilir.

**Önerilen araştırma testi:** Level 17 için sabit seed’lerle deney seti; Quadrix hedefinin tamamlanma yüzdesi, ortalama kullanılan hamle, başarısızlık nedeni ve gerekli parça/hold koşulları kaydedilmeli. Bu test yapılmadan “imkânsız” veya “oyuncu hatası” denmemeli.

### 4.9 8BitDo Xbox/XInput ve D-pad uyumluluğu

**Konuşma kanıtı — 12:45–12:48, mesajlar 073–082:**

- Geliştirici: **“Gamepad ile tüm testleri yapmıştım ama sanırsam arcade stick için ekstra güncelleme yapmam gerekecek”**.
- Tester: **“Aslında gamepad ya, yani alet gamepad taklidi yapıyor”**.
- Tester: **“D pad ayarındayım şuan”**.
- Tester cihazı **“8bitdo xbox versiyon”**, **“Xinput dümdüz”** diye tanımlıyor.
- Fotoğraflar: fiziksel cihaz (`photos/1499723578885740`) ve kontrol ayarları (`photos/4130128133957162`). İkinci görüntüde bazı satırlarda `Unknown` değerleri görülüyor.

**Kod karşılığı:**

- Varsayılan oyun içi hareketleri D-pad ve sol stick’e bağlıyor ([src/gamepad_manager.py:316-333](../src/gamepad_manager.py#L316)).
- D-pad yönleri `rotate`, `soft_drop`, `move_left`, `move_right` aksiyonlarına merkezî olarak bağlanıyor ([src/gamepad_manager.py:446-484](../src/gamepad_manager.py#L446)).
- Menü D-pad ve A/B onay/geri aksiyonları da tanımlı ([src/gamepad_manager.py:378-386](../src/gamepad_manager.py#L378)).
- XInput/Xbox cihazı algılama ve ham buton normalizasyonu var ([src/gamepad_manager.py:1211-1237](../src/gamepad_manager.py#L1211), [src/gamepad_manager.py:1306-1360](../src/gamepad_manager.py#L1306)).
- Ayarlar ekranı menü dışı trigger atamalarının işlenmediğini açıkça söylüyor; buton veya D-pad seçilmesini istiyor ([src/settings_screen_tabbed.py:471-485](../src/settings_screen_tabbed.py#L471)).

**Analiz:**

Kodda genel XInput ve D-pad yolu mevcut. Bu nedenle “Quadrix hiçbir XInput cihazını desteklemiyor” sonucu çıkarılamaz. Fakat tester’ın cihazı fiziksel olarak Xbox düzenini taklit eden 8BitDo ve ekran görüntüsünde `Unknown` görünen kontrol satırları, iki ayrı QA yüzeyine işaret eder:

1. Aygıtın SDL/Steam Input tarafından hangi isim ve buton indeksleriyle raporlandığı,
2. Aksiyonun çalışmasından bağımsız olarak ayarlar ekranında kullanıcıya hangi label’ın gösterildiği.

Bu, genel destek eksikliğinden çok belirli donanım için cihaz matrisi ve UI label doğrulaması gerektiren bir bulgudur.

### 4.10 Ana menü: çok özellik var, fakat ana mod ve hedef anlaşılmıyor

**Konuşma kanıtı — 12:54–12:55, mesajlar 106–110:**

- Tester: **“Oyunda bi tık şey sıkıntısı var ya aslına bakarsan”**.
- Tester: **“Çok şey var ama oyun yönlendiremiyor”**.
- Tester: **“Ana mod ne”**.
- Tester: **“Hedef ne”**.
- Geliştirici: **“Haklısınız, onu çok düşündük”**.

**Medya:**

- `videos/1188212720355106.mp4` karelerinde Game Modes ekranı görülüyor.
- `videos/1661597162339016.mp4` karelerinde dashboard/ana menü, Card Mastery, Campaign, Game Modes, leaderboard ve başka paneller birlikte görülüyor.
- `photos/4080059668792265` ana dashboard’ın çok panelli yapısını gösteriyor.

**Kod karşılığı:**

- Dashboard action map’inde New Gen Tetris, PvP, Piece Workshop, Campaign, Extras, Store, Co-op, Tutorial ve Achievements aynı ana yüzeyde yer alıyor ([src/menu.py:1797-1807](../src/menu.py#L1797)).
- Dashboard draw döngüsü bu panelleri tek akışta çiziyor ([src/menu.py:4125-4168](../src/menu.py#L4125)).
- New Gen Tetris için özel `Play` paneli, Campaign için ayrı quick-play paneli bulunuyor ([src/menu.py:3633-3778](../src/menu.py#L3633)).

**Analiz:**

Tester’ın sorusu bir gameplay bug’ı değil; bilgi mimarisi/onboarding bulgusudur. Oyunda içerik çokluğu tek başına sorun değildir, ancak ilk oturumda oyuncu hangi modun “temel deneyim” olduğunu ve ilk hedefin ne olduğunu çıkaramıyorsa keşif maliyeti yükselir. Kullanıcı tarafından verilen “ana oyun modunu ön plana çıkarmak için sol tarafta büyük yapmak istedik” açıklaması tasarım niyetini doğrular; fakat ekran fotoğrafları bu niyetin oyuncu tarafından otomatik olarak okunmadığını gösteriyor.

**İnceleme önerisi:** Yeni oyuncuya menüyü 10–15 saniye serbest bırakıp “ilk neye basarsın, oyunun amacı ne?” sorusu sorulmalı. Bu, görsel hiyerarşinin gerçekten yönlendirip yönlendirmediğini ölçer.

### 4.11 Ana menü kartları asimetrik ve boyutları farklı

**Konuşma kanıtı — 12:55–12:56, mesajlar 112–120:**

- Tester: **“Şu menüleri asimetrik yapma fikri kimin”**.
- Tester: **“Niye farklı boylardalar”**.
- Tester bu bölümde video gönderir.
- Geliştirici: ana oyun modunu öne çıkarmak için sol tarafı büyük yaptıklarını, tasarım bilgisinin yetersiz kaldığını söyler.

**Kod karşılığı:**

- Dashboard genişlikleri yaklaşık `%28, %17, %17, %12` ve kalan kolon olarak bölünüyor ([src/menu.py:4071-4084](../src/menu.py#L4071)).
- `new_gen_tetris` birden fazla satırı kapsayan büyük panel; PvP/Co-op da uzun paneller; diğerleri farklı satır ve inset değerleri kullanıyor ([src/menu.py:1774-1807](../src/menu.py#L1774)).
- Seçili/hover panel farklı çizim davranışıyla tekrar çiziliyor ([src/menu.py:4125-4168](../src/menu.py#L4125)).

**Analiz:**

Asimetri kaza sonucu oluşmuş görünmüyor; layout fonksiyonu bunu açıkça ve kasıtlı olarak üretiyor. Ancak kasıtlı olması oyuncu açısından anlaşılır olduğu anlamına gelmez. Büyük panelin “ana mod” olarak okunabilmesi için başlık, eylem etiketi, ilk hedef ve diğer panellerle görsel ağırlık ilişkisi aynı anda yeterince net olmalıdır.

Bu feedback’i “simetri zorunlu” şeklinde yorumlamak doğru olmaz. Tester’ın asıl sinyali, **farklı boyutların nedenini ve menüdeki önceliği kendi başına çıkaramaması**dır.

### 4.12 Clear/fall animasyonu sırasında oyun akışı senkron değil

**Yeni ekran görüntüsü kanıtı — 4 Kasım konuşması, `Screenshot_2026-11-04-14-51-08-313_com.instagram.android.jpg`:**

- Tester: **“Clear animasyonuyla taşların aşağı inişinde / Sıkıntı çıkarıyor hızlı oynamaya çalışınca”**.
- Tester daha sonra gözlemi özetliyor: **“Max potansiyelimde oynamaya çalıştım, next ve hold sıkıntı”**, **“Clear ve fall animasyonu problematik”**, **“Puan bildirimleri kör edebiliyor”**, **“Genel olarak gameplayin akışkanlığını bozmamak lazım.”**
- Tester: **“Bazı elementler donuyor bazıları oynamaya devam ediyor.”**
- TGM karşılaştırmasında line-clear görselinin iyi olduğu, fakat orada **her şeyin birlikte dondurulduğu**, animasyon bitene kadar düşen parçaların da hareket etmediği söyleniyor. Öneri: **oyunu/ düşen parçaları animasyon bitene kadar dondurmak ve animasyonu biraz hızlandırmak**.
- Tester bunu doğru uygulanırsa oyuncuya kısa bir **“micro breath”** verdiği şeklinde çerçeveliyor.

**Kod karşılığı:**

- Satır temizleme başladığında [src/game.py:3778-3832](../src/game.py#L3778) sweep, wave ve düşen blok animasyonları kuyruğa alınıyor; `_start_block_fall_animation()` blokların hedef konumlarını önceden güncelliyor ([src/game.py:3838-3894](../src/game.py#L3838)).
- Normal otomatik gravity `_automatic_gravity_paused()` üzerinden sweep veya `falling_block_animations` varken duruyor ([src/game.py:5262-5280](../src/game.py#L5262)); ancak soft-drop basılıysa bu kilit kalkıyor. Ayrıca kullanıcı girdisi `handle_input()` içinde hard/soft drop akışını sürdürebiliyor. Bu nedenle kod “hiçbir şey hareket etmez” biçiminde tam bir modal freeze uygulamıyor.
- Sweep ilerlemesi ve blokların düşme offset’i ayrı güncelleniyor ([src/game.py:5430-5475](../src/game.py#L5430)); çizimde board zaten yeni occupancy ile gösterilirken bloklar `current_offset` ile görsel olarak eski konumdan hedefe taşınıyor ([src/game.py:5794-5831](../src/game.py#L5794)).
- Clear sonrası yeni aktif parça `lock_and_new_piece()` içinde hemen kuyruktan alınıyor ([src/game.py:4943-5145](../src/game.py#L4943)); yeni parçanın otomatik gravity’si animasyon boyunca durdurulsa da parça mevcut ve manuel girdi alabilir.
- `line_clear_animation` için ayrı 30 frame’lik flash sayacı tutuluyor ([src/game.py:3829-3834](../src/game.py#L3829)), fakat `_line_clear_animation_active()` kararını bu sayaçtan değil sweep/falling listelerinden veriyor ([src/game.py:5262-5274](../src/game.py#L5262)). Bu, görsel flash sürerken oynanış pause kararının başka bir zaman çizelgesinde ilerleyebilmesine yol açabilecek ayrı bir senkron noktasıdır.
- Puan/clear popup’ı tahta merkezinin yaklaşık üçte bir yüksekliğine çiziliyor ([src/game.py:6547-6589](../src/game.py#L6547)); çift/üçlü/Quadrix bildirimleri 90–120 frame tutuluyor ([src/game.py:5081-5105](../src/game.py#L5081)). Başarım toast’ları ayrıca tahta altındaki şeritte çiziliyor ([src/game.py:7785-8019](../src/game.py#L7785)).

**Analiz:**

Bu geri bildirim salt “animasyon yavaş” değildir. Tester’ın tarif ettiği algı, board state’inin temizleme anında güncellenmesi, üst blokların görsel offset ile sonradan düşmesi, yeni parçanın hemen oluşturulması ve kullanıcı girdisinin bazı kanallarda devam etmesi arasındaki zaman farkından doğabilir. Kodda otomatik gravity’nin durduğu doğrulanıyor; fakat yeni parça yaşam döngüsü ve soft/hard drop istisnaları nedeniyle TGM’deki tüm oyun durumunu donduran tek modal state yok. Dolayısıyla “kod kesin olarak donmuyor” demek kadar “kod sorunu çözmüş” demek de doğru olmaz.

**Öncelik:** **P0/P1 gameplay-flow**. Yeniden üretimde şu dört olay ayrı ölçülmeli: (1) clear tetiklenmesi, (2) sweep bitişi, (3) falling-block animasyonu bitişi, (4) yeni parçanın input kabul etmeye başlaması. Puan popup’ının aktif tahta/oyuncu görüşünü kapatıp kapatmadığı da aynı kayıt içinde ölçülmeli.

### 4.13 Spawn yüksekliği ve görünür tahta sınırı algısı

**Yeni ekran görüntüsü kanıtı — `Screenshot_2026-11-04-14-51-08-313_com.instagram.android.jpg`:**

- Tester: **“Şimdi farkettim taşı yanlış yerde spawnlıyorsunuz”**.
- Tester 20×10 beklenen alan ile 22/23×10 görünen tahtaları karşılaştırıyor ve parçanın üstünün görünür alanın dışında spawn olduğunu söylüyor: **“Tahtanın ‘dışında’”**, **“Bak nerde spawn oluyor taşlar”**.
- Devamında TGM tarzı spawn/rotation, parçanın görünmeden önce döndürülmesi ve 24×10 tahta gibi referanslar tartışılıyor.

**Kod karşılığı:**

- Standart alan sabiti [src/constants.py:10-14](../src/constants.py#L10) içinde `BOARD_WIDTH=10`, `BOARD_HEIGHT=20`.
- Parçalar iki gizli satırla görünür alanın üstünden başlatılıyor: `HIDDEN_SPAWN_ROWS=2`, `get_piece_spawn_y()` negatif başlangıç y’si üretiyor ([src/pieces.py:97-135](../src/pieces.py#L97)).
- `skip_hidden_rows()` aktif parçayı görünür hale gelene kadar aşağı taşıyor ([src/pieces.py:138-155](../src/pieces.py#L138)); temel oyun bunu spawn sonrasında çağırıyor ([src/game.py:1468-1472](../src/game.py#L1468)).
- Spawn x’i tahta genişliğine göre merkezliyor; y ise parçanın ilk dolu satırı ve gizli satır sayısından hesaplanıyor ([src/game.py:2374-2397](../src/game.py#L2374)).
- Board, negatif y’yi geçerli kabul ediyor; ancak `lock_piece()` görünür alan üstündeki hücreleri yazmıyor ve taşma/top-out sinyali üretiyor ([src/board.py:68-86](../src/board.py#L68), [src/board.py:103-115](../src/board.py#L103)).

**Analiz:**

Kod gerçekliği 20×10 görünür alan + iki satırlık gizli spawn tamponu. Bu, teknik olarak 22/23 satırlık oynanabilir tahta kurulduğu anlamına gelmez. Ancak `skip_hidden_rows()` nedeniyle standart akışta parça hemen görünür alana çekiliyor; rotasyon öncesi/sonrası şekil üst dolu satırları değiştiğinde veya özel/workshop şekillerinde oyuncunun gördüğü ilk pozisyon beklenen guideline davranışından farklı hissedebilir. Bu nedenle tester’ın “kesin bug” iddiası henüz doğrulanmış değil; fakat **spawn geometrisi ve rotation-before-spawn davranışı için somut QA vakası**dır.

**Önerilen doğrulama:** Her standart parça ve başlangıç rotasyonu için spawn `x/y`, ilk görünür dolu hücre, tahta üst kenarı ve ilk kullanıcı input zamanı kaydedilmeli. 20×10 görünür alan ile kullanılan gizli satır konvansiyonu ekranda/rehberde açıkça adlandırılmalı.

### 4.14 Bag/random sistemi: gözlenen beklenti, mevcut kod ve iletişim riski

**Yeni ekran görüntüsü kanıtı — `Screenshot_2026-11-04-14-51-51-265_com.instagram.android.jpg`:**

- Tester: **“Gerçek random mu oyun”** ve **“Hiç test kodu yazdın mı istatistik açısından / 7 milyon taş çeksek 1’er milyon olacak mı”**.
- Geliştirici cevaplarında 3 torbadan söz ediyor; konuşmanın ilerleyen kısmında tester “Neden 7’li torba değil btw” diyor.
- Geliştirici: **“Torba zaten 7’li hocam / 3 tane 7’li torba / Yani bir torbada 21 blok var.”**
- Tester Tetrio/modern Tetris seçeneklerini soruyor ve tek torbanın karıştırılıp tüm parçaları tüketmesi beklentisini dile getiriyor: **“Bi torba jenere ediyor, hepsini kullanıyor”**. Ayrıca **“Bu arada ben tek torba taraftarı değilim, ama genel beklenti o yönde”** diyor.
- Tester’ın son ürün beklentisi: **geliştirici seçeneklerinde torba sayısının değiştirilebilmesi**. Geliştirici de bir torba sayısı ayarı sunabileceğini söylüyor.

**Kod karşılığı:**

- Temel `Game` sınıfı pool’daki her standart + workshop parça türünden `_bag_copies=3` kopya üretip tek listede karıştırıyor ([src/game.py:1449-1459](../src/game.py#L1449), [src/game.py:2145-2166](../src/game.py#L2145)). Yedi standart parça ve workshop parçaları yoksa torba uzunluğu **7×3=21**; workshop parçaları eklenirse 21’den büyür.
- Parçalar torba bitene kadar sırayla tüketiliyor; boşalınca yeni torba oluşturuluyor ([src/game.py:2168-2215](../src/game.py#L2168)). Bu, konuşmadaki “3 ayrı torba” ifadesinden farklı olarak çalışma zamanında **tek 21’lik (veya workshop ile daha büyük) torba başına 3 kopya** modelidir; üç 7’li torba nesnesi yok.
- Kod ayrıca aynı parça kimliğinin art arda üçten fazla gelmesini engelleyen ek bir seçim filtresi kullanıyor ([src/game.py:2100-2143](../src/game.py#L2100)). Bu, torbanın içeriğini değiştirmez; torba sırasını seçme sırasında bazı indeksleri atlayabilir ve tam uniform sıra beklentisini değiştirir.
- `Piece Workshop` havuzu torbaya otomatik ekleniyor ([src/game.py:2093-2098](../src/game.py#L2093)). Dolayısıyla “7 milyon çekişte her standart parça tam 1/7” iddiası workshop parçaları açıkken geçerli değildir; dağılım havuz büyüklüğüne göre değişir.
- Co-op ve PvP aynı temel davranıştan farklı olabilir: Co-op’ta oyuncu başına `7 tip × 2 kopya` bag’i var ([src/coop_game.py:1109-1125](../src/coop_game.py#L1109)); PvP sequence üretiminde `bag_copies=3` ve `list(range(total))*3` kullanılıyor ([src/pvp_game.py:1833-1875](../src/pvp_game.py#L1833)). Bu nedenle “oyun genelinde tek bir random kuralı” diye anlatmak doğru değildir.

**Analiz:**

Tester’ın sorusu bir bug raporundan çok **istatistiksel doğrulanabilirlik ve oyuncuya açıklanan bag sözleşmesi** talebidir. Kodun temel tek oyunculu uygulaması, 7’li tek torba × 3 kopya yaklaşımına eşdeğer 21 elemanlı bir torba kuruyor; torbalar ardışık olarak yenileniyor. Ancak aynı türü üçten fazla art arda engelleyen ek filtre ve workshop havuzunun genişlemesi, “her 7 parça tam birer kez” gibi basit bir varsayımı kırabilir. Bu nedenle 7 milyonluk test sorusu anlamlıdır; mevcut incelemede böyle bir istatistik testinin bulunduğuna dair ayrı bir test dosyası/kanıt bulunmadı.

**Öncelik:** **P1 açıklık/denge araştırması**. Kullanıcıya gösterilecek ayar sözleşmesi netleştirilmeli: “bag size”, “copies per piece”, “workshop pieces included” ve “max consecutive repeat” ayrı parametrelerdir. Tek oyunculu, PvP ve co-op dağılımları ayrı test edilmelidir.

### 4.15 Ses/tema/mağaza önerileri: ürün fırsatı, doğrulanmış bug değil

**Yeni ekran görüntüsü kanıtı:**

- Tester her taş için özgün spawn sesi fikrini veriyor: **“Her taşın kendine unique bi spawn sesi var… beyni sese daha hızlı reaksiyon veriyor görüntüye kıyasla.”**
- Clear için **“konuşması/ses efekti”** ve lazer/Neon/Iron Man/Kamehameha gibi tematik efekt örnekleri öneriyor: **“Clearlarda da announce konuşması/ses efekti olmalı”**, **“LAZER ekleyebilirsin clear animasyonuna”**.
- Store için **“backgroundlar falan da eklemeyi düşünebilirsin”** diyor.
- Pet konusunda öneri: **“Chibi goku”**, **“kedi koşuyo gökyüzü takip ediyo”**, pet’in lazer atması; konuşma sonunda özel set/tema fikrine dönüyor.
- Ekonomik bağlamda **“Monetizasyon yöntemi sana / Oyunu çok kişiye satmayacağınız belli / Micro tx / Şart”** ve tema, pet, background, ses paketleri fikri geçiyor.

**Kod karşılığı:**

- Oyun sesleri hareket, dönme, clear, lock ve tetris olaylarında çalınıyor ([src/game.py:2885-2954](../src/game.py#L2885), [src/game.py:4996-5106](../src/game.py#L4996)).
- Müzik playlist’i ve shuffle ayarı mevcut ([src/game.py:1645-1669](../src/game.py#L1645)); clear sweep çizimi seçili sweep theme ve pet’i kullanıyor ([src/game.py:5872-5905](../src/game.py#L5872)).
- Bu kod yüzeyinde her standart parçaya özgü spawn SFX veya konuşmalı clear announcer’ı görünmüyor; dolayısıyla öneri mevcut özellikten çok yeni içerik/özelleştirme talebidir.
- Store yüzeyinde kart kategorileri ve oyun içi içerik akışı mevcut olsa da, bu konuşma tek başına background/pet/ses paketlerinin tamamının mevcut olmadığını kanıtlamaz. Bu yüzden “mağazada yok” yerine “genişletme fırsatı” olarak sınıflandırılmalı.

**Analiz:**

Bu bölümde tester oyunun temel oynanışını bozan bir hata bildirmiyor; duyusal geri bildirim ve kişiselleştirme katmanını büyütüyor. Spawn sesleri ve clear announcer’ları hızlı oyun akışında faydalı olabilir, ancak 4.12’deki “puan bildirimleri kör edebiliyor” şikâyetiyle birlikte tasarlanmalı: ses/konuşma, görsel bilgi yükünü azaltmalı; üstüne yeni bir efekt yığını bindirmemeli. Monetizasyon mesajları kullanıcı araştırması sinyalidir, fiyat/mağaza kararı için tek başına pazar kanıtı değildir.

### 4.16 Olumlu sinyaller ve tester bağlılığı

**Konuşma kanıtı:**

- Tester yaklaşık 15 dakika oynadığını söyler (mesaj 003).
- “Neon estetik çok iyi” (006).
- “Süper” (012).
- “Kral idealinde” (017).
- “Ben oynarım ya” (049).
- Kör oynanış videosu, kontrol ayarları ve dashboard görselleri gönderir (mesajlar 059, 072, 077–078, 111, 116).
- Geliştirici, tester’ın geri bildirimlerini mobile sürümün de etkileyeceğini belirtir (mesaj 052).

**Analiz:**

Tester yalnızca kısa bir bakış yapıp ayrılmamış; oyunu oynamış, sorunları oynanış sırasında ayırmış, donanım bağlamı vermiş ve görsel kanıt toplamıştır. Olumlu estetik sinyali ile okunabilirlik şikâyeti birlikte okunmalı: neon estetik korunabilir, fakat kontrast ve hiyerarşi oyuncunun hızlı kararını engellemeyecek şekilde yeniden ölçülmelidir.

## 5. Medya kanıt envanteri

| Kaynak | Konuşma bloğu | İçerik | Analizdeki rolü |
|---|---:|---|---|
| `photos/1499723578885740` | 077 | 8BitDo Xbox düzenli fiziksel kontrolcü | Donanım bağlamı |
| `photos/4130128133957162` | 078 | Gamepad kontrolleri ekranı; bazı satırlarda `Unknown` | Mapping/label QA sinyali |
| `photos/28959238020385411` | 054 | Block Styles ekranı; Default/Custom satırları | Hazır stil talebinin görsel kanıtı |
| `photos/4080059668792265` | 111 | Ana dashboard ve farklı boyutlu paneller | Asimetri ve bilgi mimarisi kanıtı |
| `videos/1188212720355106.mp4` | 072 | Game Modes ekranı; yaklaşık 45,93 sn, 360×640 | Çoklu mod yüzeyi ve keşif bağlamı |
| `videos/1661597162339016.mp4` | 116 | Dashboard/ana menü; yaklaşık 24,80 sn, 360×640 | Ana mod/hiyerarşi bağlamı |
| `Screenshot_2026-11-04-14-51-08-313_com.instagram.android.jpg` | yeni ekran görüntüsü | Clear/fall senkronu, spawn yüksekliği, ses/clear/tema/pet önerileri | Yeni gameplay ve ürün feedbackleri; 1220×22361 uzun konuşma |
| `Screenshot_2026-11-04-14-51-51-265_com.instagram.android.jpg` | yeni ekran görüntüsü | Bag/random istatistikleri, 7’li torba beklentisi, bag ayarı, sandbox/mağaza fikirleri | Yeni random ve ürün yönlendirmesi; 1220×22485 uzun konuşma |

## 6. Kod tabanı açısından doğrulanmış bulgular

1. **HUD mevcut kodda Next üstte, Hold altta çiziliyor.** Tester’ın tarif ettiği Hold solda/Next sağda düzeni temel çizim akışında yok.
2. **Next kutuları içerik genişliği ve ölçekle sınırlandırılıyor.** Tester’ın “küçük” gözlemi mevcut geometrinin fiziksel ekran/izleme mesafesinde yetersiz kalabileceğini gösteriyor.
3. **Ghost ve border çizim yolları mevcut; sorun görünürlük/kontrast olabilir.** “Outline yok” ifadesi kelimesi kelimesine kod gerçeği değil.
4. **`show_ghost` ayarı UI ve ayar modelinde mevcut, fakat `game.py` ghost çizimini bu ayarla bağlamıyor.** Bu doğrudan incelenebilir bir davranış tutarsızlığıdır.
5. **Campaign 17’de açıkça `move_limit=23` ve yıldız için 18 hamle koşulu var.** İki Quadrix hedefinin bu bütçede uygulanabilirliği test edilmelidir.
6. **Campaign hem hareket hem süre sınırını destekliyor.** Tester’ın süre bazlı önerisi altyapı dışı bir talep değildir; mevcut tasarımın alternatif kullanım biçimidir.
7. **Campaign görevleri kodda oluşturuluyor, çiziliyor ve ilerleme gösteriliyor.** Buna rağmen tester hedefi sonradan anlıyor; sorun veri yokluğu değil, keşfedilebilirlik/iletişimdir.
8. **Dashboard asimetrisi kodda kasıtlıdır.** Büyük ve küçük kolon/satır geometrileri açıkça tanımlanmıştır.
9. **8BitDo/XInput için genel normalizasyon ve D-pad haritaları vardır.** Belirli cihaz ve ekran label’ları için gerçek cihaz QA’sı yine gereklidir.
10. **Block Styles yüzeyi parça başına Default/Custom sunuyor; 3–5 hazır tema kataloğu görünmüyor.**
11. **Clear/fall animasyonunda otomatik gravity duruyor, fakat soft/hard input ve yeni aktif parçanın erken yaşam döngüsü nedeniyle TGM tipi tam modal freeze uygulanmıyor.**
12. **Temel tek oyunculu bag, 7 standart parça için 21 elemanlı (3 kopya/tip) tek torba kuruyor; workshop parçaları havuzu büyütüyor ve tekrar filtresi sıralama davranışını etkiliyor.**
13. **Spawn sistemi 20×10 görünür alan + 2 gizli spawn satırı kullanıyor; tester’ın dışarıda spawn algısı teknik olarak henüz bug diye doğrulanmadı, ancak standart/workshop şekiller ve rotasyonla QA gerektiriyor.**
14. **Clear/lock/tetris sesleri mevcut; parça başına spawn SFX ve konuşmalı clear announcer’ı incelenen temel akışta görünmüyor.**

## 7. Önerilen doğrulama planı

Bu bölüm uygulanacak kod değişikliklerini değil, feedback’in sonraki araştırma aşamasında nasıl doğrulanacağını listeler:

1. **Kontrast senaryosu:** Mor arka plan + mor T parçası + hızlı hareket + ghost açık/kapalı. Aynı sahne 1920×1080 ve farklı UI ölçeklerinde kaydedilmeli.
2. **HUD geometri testi:** 24 inç ve 43 inç 1080 ekran senaryolarında Next/Hold etiketleri, kutu boyutları ve oyuncunun bakış mesafesi kaydedilmeli.
3. **Campaign 17 deneyi:** Sabit seed’lerle çoklu oynama; Quadrix sayısı, kullanılan hamle, Hold kullanımı ve başarısızlık noktası ölçülmeli.
4. **Görev keşfi testi:** Oyuncuya açıklama yapılmadan level başlatılmalı; ilk 20 saniyede “ana hedef ne?” sorulmalı.
5. **Dashboard yönlendirme testi:** Yeni oyuncu ilk menüde serbest bırakılmalı; hangi panele gittiği ve “oyunun amacı”nı nasıl ifade ettiği kaydedilmeli.
6. **8BitDo cihaz matrisi:** SDL joystick yolu, Steam Input yolu, D-pad, A/B/X/Y ve ayarlar label’ları ayrı ayrı doğrulanmalı.
7. **Block Styles ürün testi:** Mevcut Default/Custom ile 3–5 hazır preset fikri karşılaştırılmalı; tester’ın seçim süresi ve kişiselleştirme memnuniyeti ölçülmeli.
8. **Lunar akış testi:** Başlangıç bakiyesi, hedef ürün, satın alma maliyeti, kazanma süresi ve test akışının tekrarları kaydedilmeden ekonomi kararı verilmemeli.
9. **Clear/fall timeline testi:** Clear anı, sweep bitişi, düşen blokların offset sıfırlanması, yeni parçanın input kabulü ve popup görünürlüğü aynı zaman çizelgesinde kaydedilmeli.
10. **Bag istatistik testi:** Seed’li ve seedsiz koşullarda standart 7 parça, workshop açık/kapalı, tek oyunculu/PvP/co-op ayrı ayrı örneklenmeli; torba içi dağılım, torba sınırı geçişleri ve art arda tekrar filtresi raporlanmalı.
11. **Spawn/rotation testi:** Standart yedi parça, her rotation state ve en az bir workshop polyomino için başlangıç görünürlüğü ve ilk aktif hücre satırı ekran kaydıyla doğrulanmalı.
12. **Ses okunabilirliği testi:** Spawn/clear ses önerileri uygulanacaksa popup ve sweep ile eşzamanlı ses yoğunluğu, müzik ducking ve kullanıcı kapatma ayarı birlikte ölçülmeli.

## 8. Sonuç

FullMetalPomak’ın geri bildirimleri Quadrix’in temel neon görsel kimliğini reddetmiyor; aksine bu kimliği beğenirken hızlı oyunda okunabilirlik, HUD hiyerarşisi, clear/fall senkronu, spawn geometrisi, randomizer açıklığı, görev anlaşılabilirliği ve ana menü yönlendirmesi konusunda somut sürtünmeler bildiriyor. En acil araştırma alanları aktif T parçasının kontrastı/outline’ı, Next-Hold düzeni, clear/fall zaman çizelgesi ve Campaign 17’nin gerçek oynanabilirlik ölçümüdür.

Kod incelemesi, geri bildirimlerin önemli bölümünü mevcut davranışla açıklıyor: HUD sıralaması ve dashboard asimetrisi doğrudan kodda görülüyor; clear/fall akışında otomatik gravity dururken yeni parça ve manuel input istisnaları bulunuyor; temel tek oyunculu randomizer 3 kopyalı 21 elemanlı torba kuruyor; `show_ghost` ayarı ile ghost çizimi arasında bağlantı eksikliği de doğrulanabilir. Buna karşılık Campaign 17’nin imkânsızlığı, spawn algısının kesin geometrik bug olduğu, XInput desteğinin genel olarak bozuk olduğu veya Lunar ekonomisinin dengesiz olduğu henüz yalnızca bu konuşmayla kesinleştirilemez. Bu başlıklar kontrollü oyun testleriyle tamamlanmalıdır.
