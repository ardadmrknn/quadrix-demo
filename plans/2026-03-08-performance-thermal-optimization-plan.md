# Quadrix Performans ve Termal Optimizasyon Planı

Tarih: 2026-03-08
Durum: Aktif plan, Faz 5 tamamlandi ve onay bekleniyor
Kapsam: macOS + Windows termal yük, CPU/GPU kullanımını düşürme, görsel kaliteyi ve hissedilen akıcılığı koruma

## 0. Mevcut Karar ve Reset Notu

Bu belge yaşayan plan ve uygulama kaydıdır.

Güncel karar:
- Uygulama fazlı şekilde ilerleyecek.
- Her faz sonunda kod geriye dönük incelenecek.
- Sonraki faz için kullanıcı onayı beklenecek.

En kritik yeni karar:
- Oyun varsayılan durumda 60 FPS'e sabitlenmeyecek.
- Oyun varsayılan durumda sınırsız FPS de çalışmayacak.
- Varsayılan davranış, cihazın ve monitörün desteklediği gerçek yenileme hızına kilitlenmek olacak.

Örnek hedef davranış:
- 60 Hz ekranlı MacBook M2 üzerinde varsayılan pacing yaklaşık 60 FPS hedeflemeli.
- 144 Hz monitörlü bir PC üzerinde varsayılan pacing yaklaşık 144 FPS hedeflemeli.
- 240 Hz monitörlü bir sistemde varsayılan pacing yaklaşık 240 FPS hedeflemeli.

Bu yüzden plan boyunca fps_limit değeri 0 artık sınırsız anlamında değil, otomatik yenileme hızı algılama ve o değere kilitlenme hedefiyle ele alınacaktır.

## 1. Amaç

Bu planın amacı, Quadrix içinde gözlenen yüksek ısınma ve gereksiz kaynak tüketimini düşürmektir.

Ana hedefler:
- Görsel kaliteyi düşürmeden optimizasyon yapmak.
- Akıcılığı düşürmeden optimizasyon yapmak.
- Varsayılan frame pacing davranışını cihazın gerçek yenileme hızına uyarlamak.
- Platforma göre farklı davranan pahalı render yollarını kontrol altına almak.
- Menü, normal oyun, Campaign, Local PvP ve Online PvP akışlarını güvenli biçimde korumak.
- Büyük refactor yerine ölçülü ve düşük riskli adımlarla ilerlemek.

## 2. Kırmızı Çizgiler

Bu çalışma boyunca aşağıdaki yöntemler ilk fazlarda kullanılmayacak:
- Çözünürlük düşürme
- HiDPI kapatma
- Efektleri topluca kapatma
- Particle sayısını körlemesine azaltma
- UI panel, glow, gradient, theme görünümünü sadeleştirme
- Oyunu 60 FPS'e zorla sabitleme
- Her cihazda aynı FPS değerine zorla kilitleme
- Sırf serinlik için macOS tarafındaki mevcut görsel/teknik özellikleri kapatma
- Sırf serinlik için Windows tarafındaki kaliteyi koruyan mevcut görsel/teknik özellikleri kapatma

Platform özel net tercih:
- macOS'ta mevcut kalite ve özellik seti korunacak.
- Windows'ta kaliteyi sağlayan mevcut özellik seti korunacak.
- Optimizasyonun ana yöntemi özellik kapatmak değil, aynı kaliteyi daha verimli üretmek olacak.

Bu yöntemler ancak son çare olarak ve açık karar ile değerlendirilir.

## 3. Başarı Kriterleri

Bir optimizasyon ancak aşağıdaki koşulları sağlıyorsa kabul edilir:
- Görsel çıktı öncekiyle aynı veya gözle fark edilmeyecek kadar eşdeğer olmalı.
- Input hissi, drop davranışı ve menü navigasyonu bozulmamalı.
- Varsayılan FPS davranışı, ekranın gerçek yenileme hızına uygun çalışmalı.
- Menü idle durumunda gereksiz CPU/GPU yükü anlamlı biçimde azalmalı.
- Uzun oyun seanslarında sıcaklık ve fan davranışı gözle görülür biçimde iyileşmeli.
- Windows Steam overlay ve macOS fullscreen davranışı bozulmamalı.
- Değişiklikler birden fazla state arasında güvenle taşınmalı.

Termal hedef notu:
- Hedef mutlak olarak "çok düşük sıcaklık" üretmek değildir.
- Hedef, mevcut gereksiz termal yükü azaltmak ve oyunun aynı kaliteyle gereksiz yere aşırı ısınmasını engellemektir.
- Başarı kriteri "oyun 30 derecede çalışsın" değildir.
- Başarı kriteri, oyunun kaliteyi korurken gereksiz şekilde yüksek termal bölgelerde uzun süre kalma eğilimini azaltmaktır.

## 4. Şu Ana Kadar Teyit Edilen Kök Nedenler

### 4.1 Ana loop varsayılan durumda sınırsız FPS çalışabiliyor

Ana problem, ana state loop'un varsayılan durumda ekranın ihtiyaç duyduğundan çok daha fazla frame üretmesidir.

İlgili kod bölgeleri:
- src/main.py içinde ana while running loop'u
- fps_limit ayarı 0 olduğunda clock.tick(0) davranışı

Teknik etkisi:
- Menüde de oyunda da her frame tam redraw olduğu için CPU sürekli aktif kalır.
- GPU tarafı da gereksiz flip ve compositing çalıştırır.
- Bu durum özellikle menü gibi kullanıcı beklerken bile sistemi ısıtır.

Yeni yorum:
- Bu davranışın hedef düzeltmesi sabit 60 FPS değildir.
- Hedef düzeltme, varsayılan durumda cihazın gerçek ekran yenileme hızına kilitlenmektir.

### 4.2 VSync ayarı niyet olarak var, pacing garantisi olarak yok

Kod tabanında SDL_RENDER_VSYNC ayarlanıyor ancak aktif display oluşturma yolu klasik pygame surface zincirini kullanıyor. Bu yüzden gerçek pacing her sistemde güvenilir değil.

Teknik etkisi:
- Bazı cihazlarda monitör Hz kadar kilitlenmek yerine busy-loop davranışı oluşabilir.
- "VSync açık, sorun olmaz" varsayımı güvenli değil.

### 4.3 Windows GL compat katmanı tam frame upload yapıyor

Steam overlay desteği için OpenGL köprüsü kullanılıyor. Bu yol her flip öncesi pygame yüzeyini byte dizisine çevirip tam texture upload yapıyor.

Teknik etkisi:
- Her frame CPU kopyalama maliyeti oluşur.
- Her frame GPU'ya tam ekran texture gönderilir.
- Özellikle yüksek çözünürlük ve sınırsız FPS birleşince Windows'ta termal yük çok artar.

### 4.4 macOS HiDPI gerçek piksel yükünü büyütüyor

macOS tarafında HiDPI aktif. Kullanıcı pencereyi logical boyutta görse de gerçek çizim fiziksel piksel yüzeyinde yapılıyor.

Teknik etkisi:
- Aynı sahne daha fazla piksel üzerinde işlenir.
- Full-screen alpha overlay, glow ve panel compositing maliyeti artar.
- Görsel kalite artışı vardır ama fill-rate maliyeti yüksektir.

### 4.5 Texture-backed block çiziminde per-cell smoothscale maliyeti var

Textured block yolu, slice çıkarıp bunu her draw sırasında yeniden smoothscale ediyor.

Teknik etkisi:
- Textured style aktifse aynı hücre tipi için tekrar tekrar ölçekleme yapılır.
- Bu maliyet oyun, PvP ve bazı modlarda doğrudan frame süresine biner.

### 4.6 Efekt çiziminde geçici alpha surface üretimi yüksek

Particle, glow, wave, modal overlay, button glow ve panel glow akışlarında çok sayıda geçici Surface üretimi var.

Teknik etkisi:
- Python tarafında allocation baskısı artar.
- Pygame alpha blending yükü büyür.
- Özellikle yüksek çözünürlükte menü ve overlay ekranlarında ekstra ısı üretir.

## 5. Risk Sınıflandırması

### Düşük riskli işler
- Ana frame pacing fallback'i düzeltmek
- Texture cell cache eklemek
- Aynı glow ve effect surface'leri cache'lemek
- Overlay ve panel çiziminde yeniden kullanılabilir surface katmanları eklemek

### Orta riskli işler
- Menü ve bazı ekranlarda statik/dinamik katman ayrımı yapmak
- State bazlı redraw iş yükünü azaltmak
- Online PvP ve PvP özel draw yollarında ek cache katmanları kurmak

### Yüksek riskli işler
- GL compat davranışını değiştirmek
- Steam overlay ile ilgili rendering zincirine büyük müdahale etmek
- Display create/rebuild mantığını değiştirmek
- HiDPI/fullscreen davranışını değiştirmek

## 6. Uygulama Stratejisi

Bu iş tek commit'lik tek parça refactor olarak yapılmayacak. Fazlı ve geri dönüşü kolay bir strateji izlenecek.

### Faz 1: Güvenli frame pacing düzeltmesi

Amaç:
- Gereksiz sınırsız frame üretimini kesmek
- Monitör yenileme hızını koruyacak güvenli pacing eklemek
- Varsayılan davranışı cihazın gerçek yenileme hızına otomatik uyarlamak

Yapılacaklar:
- Ana loop'ta fps_limit=0 davranışını "sınırsız" yerine "otomatik yenileme hızı kilidi" yapısına çevirmek.
- VSync varsa onunla uyumlu çalışmak, yoksa ekranın gerçek refresh değerini okuyup o değeri kullanmak.
- 60 Hz, 120 Hz, 144 Hz, 165 Hz, 240 Hz gibi farklı ekranlarda varsayılan pacing'in doğru davranmasını sağlamak.
- Menü, oyun, PvP, Online PvP state'lerinde pacing davranışını ortak ve tutarlı hale getirmek.
- Yalnızca sayısal pacing düzeltmesi yapmak; efekt, çözünürlük ve görsel içeriğe dokunmamak.

Beklenen kazanım:
- Menü idle ısısı belirgin azalır.
- Oyun sırasında gereksiz 300-800 FPS üretimi kesilir.
- Farklı PC ve monitörlerde oyun gereksiz yere 60'a düşmeden, ekranın doğal hızına oturur.
- Görsel kalite ve input hissi korunur.

Risk:
- Düşük

Faz 1 uygulama sonucu:
- Ortak bir frame cap çözümleyicisi eklendi ve fps_limit <= 0 durumu otomatik ekran yenileme hızına bağlandı.
- Ana loop, Local PvP loop ve Online PvP loop aynı çözümleyiciye geçirildi.
- Ayarlar UI'sinde 0 değeri artık MAX yerine Otomatik olarak gösteriliyor.
- Render kalitesine, efekt içeriğine, çözünürlüğe ve platform özelliklerine dokunulmadı.

Faz 1 doğrulama özeti:
- Düzenlenen dosyalarda statik hata kontrolü temiz geçti.
- Dar kapsamlı settings testi çalıştırıldı, ancak test dosyası fullscreen onay modalı davranışında zaten bu fazdan bağımsız görünen başarısızlıklar verdi.
- Bu fazın yaptığı değişiklikler FPS pacing semantiği ile sınırlı kaldı; fullscreen modal akışı değiştirilmedi.
- Faz 1 retrospektif incelemesinde auto modun her frame ekran yenileme hızını sorguladığı görüldü; bu polling kısa süreli cache ile düzeltildi.
- Refresh cache düzeltmesi ve auto etiket semantiği için hedefli regresyon testleri eklendi ve geçti.
- Faz 1-5 toplu geriye dönük incelemede auto refresh sorgusunun display 0'a fazla bağlı kaldığı görüldü; aktif pencerenin current refresh rate yolunu tercih eden ve gerekirse desktop refresh rate listesine düşen seçim mantığı eklendi.

Faz 1 risk notu:
- Otomatik mod artık sınırsız FPS anlamına gelmiyor; eski 0 ayarını kullanan profiller bundan sonra ekran yenileme hızına kilitlenecek.
- Bu davranış değişikliği bilinçli olarak yapıldı, çünkü termal yükün ana kök nedeni buydu.

### Faz 2: Texture cell render cache

Amaç:
- Textured block style kullanılırken aynı hücre ölçekleme işini tekrar tekrar yapmamak

Yapılacaklar:
- Normal oyun için size + piece_name + rel_x + rel_y + rotation bazlı cache eklemek.
- PvP için aynı cache stratejisini eşdeğer biçimde uygulamak.
- Cache invalidation kurallarını basit ve güvenli tutmak.
- Rotated surface cache ile çakışmayacak şekilde ikinci seviye scaled-slice cache kullanmak.

Beklenen kazanım:
- Textured block style açıkken frame time düşer.
- CPU yükü azalır.
- Görüntü birebir aynı kalır.

Risk:
- Düşük

Faz 2 uygulama sonucu:
- Texture-backed hücre render yolu için ortak bir TextureRenderCache sınıfı eklendi.
- Döndürülmüş texture varyantları ve hücre bazlı smoothscale sonuçları cache'lenir hale getirildi.
- Normal oyun, Local PvP ve Online PvP aynı cache mantığına bağlandı.
- Texture slice bounds değişirse cache anahtarı da değişecek şekilde tasarlandı; eski slice semantiği korunuyor.

Faz 2 doğrulama özeti:
- Düzenlenen dosyalarda statik hata kontrolü temiz geçti.
- Texture render cache için hedefli birim testleri eklendi ve geçti.
- Faz 1 regresyon testleri tekrar çalıştırıldı ve bozulma görülmedi.
- Bu faz yalnızca textured block çizim yoluna dokundu; genel render akışı, efekt yoğunluğu ve platform display davranışı değiştirilmedi.
- Faz 2 retrospektif incelemesinde TextureSlice width/height için savunmalı normalizasyon eklendi; bozuk veri gelirse cache yolu artık ZeroDivision üretmeyecek.

Faz 2 risk notu:
- Cache yüzeyi kişi başı sınırsız büyümesin diye surface başına varyant sayısı üst sınıra gelince ilgili variant map temizleniyor.
- Bu tercih performans kazancını korurken karmaşık invalidation mantığı eklememek için bilinçli olarak basit tutuldu.

### Faz 3: Allocation azaltma ve effect surface cache

Amaç:
- Aynı glow/panel/particle yardımcı surface'lerini her frame yeniden oluşturmamak

Yapılacaklar:
- Sık üretilen radial glow benzeri yardımcı yüzeyleri cache'lemek.
- Wave, trail, highlight ve modal overlay için uygun yeniden kullanım noktalarını ayırmak.
- Boyut ve renk bazlı LRU benzeri küçük cache'ler kurmak.
- Aşırı büyük cache oluşumunu engellemek.

Beklenen kazanım:
- Python allocation baskısı azalır.
- Menü ve oyun overlay'lerinde CPU kullanımı düşer.

Risk:
- Düşük ila orta

Faz 3 uygulama sonucu:
- Game, Local PvP ve Online PvP için ortak bir EffectSurfaceCache sınıfı eklendi.
- Ambient particle glow/dot yardımcı surface'leri cache'li hale getirildi.
- Particle halo ve mid-glow yardımcı circle surface'leri yeniden kullanılabilir oldu.
- Satır temizleme sweep sırasında üretilen lit fill surface'leri ve wave ellipse surface'leri cache'e alındı.
- Bu faz menü statik katmanlarını, panel kompozisyonlarını ve trail efektlerini bilinçli olarak kapsam dışı bıraktı; yalnızca en sık tekrarlanan gameplay efekt allocation yollarına dokunuldu.

Faz 3 doğrulama özeti:
- Düzenlenen dosyalarda statik hata kontrolü temiz geçti.
- EffectSurfaceCache için hedefli birim testleri eklendi ve geçti.
- Faz 1 ve Faz 2 hedefli regresyon testleri tekrar çalıştırıldı ve bozulma görülmedi.
- Düzenlenen gameplay dosyaları py_compile ile ayrıca doğrulandı.
- Çalıştırılan dar test seti:
  - tests/test_effect_surface_cache.py
  - tests/test_block_styles_texture_render_cache.py
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Toplam sonuç: 26 test geçti.
- Faz 3 retrospektif incelemesinde cache kapasitesinin testte zorlanabilmesi için explicit max_entries değerinin korunması gerektiği görüldü; minimum kapasite dayatması kaldırıldı ve eviction davranışı test ile doğrulandı.
- Aynı retrospektif turda game.py içindeki mid-glow bloğunda kalan bir girinti hatası derleme kontrolü ile yakalandı, düzeltildi ve testler tekrar geçirildi.
- Devam öncesi ek kod incelemesinde Faz 3 cache yüzeylerinin sonradan set_alpha ile paylaşımlı biçimde mutate edilmediği doğrulandı; yeni bir mantık veya eksik initialization hatası bulunmadı.

Faz 3 risk notu:
- Effect surface cache küçük bir LRU ile sınırlı tutuldu; amaç allocation baskısını düşürürken kontrolsüz yüzey birikimini engellemek.
- Alpha ve renk anahtarları tam değerle tutuluyor; görsel sadakat korunuyor, ancak cache doluluğu artarsa en eski yardımcı yüzeyler yeniden üretilecek.

### Faz 4: Menü ve UI ekranlarında statik/dinamik katman ayrımı

Amaç:
- Her frame aynı panel, aynı büyük kart ve aynı statik arka plan parçalarını tekrar hesaplamamak

Yapılacaklar:
- Ana menüde statik dashboard katmanları için cache yüzeyi oluşturmak.
- Yalnızca hover, selection, animated background ve dynamic text katmanlarını canlı çizmek.
- Gerekirse invalidation anahtarları tanımlamak: dil, ekran boyutu, aktif kullanıcı, mute durumu, layout override, leaderboard verisi.

Beklenen kazanım:
- Menü idle kullanımı daha da düşer.
- Görsel birebir korunur.

Risk:
- Orta

Faz 4 uygulama sonucu:
- Menü tarafında küçük bir SurfaceLRUCache katmanı eklendi.
- Ana dashboard içinde en düşük riskli statik kartlar için non-hover yüzey cache'i kuruldu:
  - daily_challenge
  - achievements
  - piece_workshop
  - block_styles
- Bu kartlar seçili veya hover durumda değilken tüm kart yüzeyi tekrar üretilmek yerine cache'den blit ediliyor.
- Dinamik etkileşimli kartlar bilinçli olarak canlı bırakıldı:
  - new_gen_tetris
  - extras
  - tutorial_mode
  - campaign_mode
  - pvp_2_players
- Böylece hover, alt-butonu ve split seçim davranışları korunurken ana menüdeki statik panel üretim yükü azaltıldı.

Faz 4 doğrulama özeti:
- Düzenlenen dosyalarda statik hata kontrolü temiz geçti.
- Menü ve yeni cache modülleri py_compile ile doğrulandı.
- SurfaceLRUCache için hedefli birim testleri eklendi ve geçti.
- Dashboard tile cache kapısı ve cache key invalidation davranışı için hedefli menü testleri eklendi ve geçti.
- Çalıştırılan dar test seti:
  - tests/test_surface_lru_cache.py
  - tests/test_menu_dashboard_tile_cache.py
  - tests/test_effect_surface_cache.py
  - tests/test_block_styles_texture_render_cache.py
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Toplam sonuç: 32 test geçti.
- Faz 4 retrospektif incelemesinde aynı metin korunurken dil profili/font değiştiğinde cache anahtarının değişmediği görüldü; aktif dil cache key'e eklendi ve test ile doğrulandı.
- Faz 5 öncesi ek kod incelemesinde menü şeffaflığı değiştiğinde statik dashboard kart cache anahtarının değişmediği görüldü; aktif menu transparency değeri cache key'e eklendi ve hedefli test ile doğrulandı.

Faz 4 risk notu:
- Dashboard tile cache yalnızca statik kartların non-hover durumuna uygulanıyor; bu sınır kasıtlı olarak dar tutuldu.
- Etkileşimli buton ve split seçim kartları canlı bırakıldığı için menü davranışında agresif davranış değişikliği riski azaltıldı.

### Faz 5: Windows GL compat ince ayarı

Amaç:
- Steam overlay açıkken oluşan tam-frame upload baskısını kontrol altına almak

Yapılacaklar:
- Önce Faz 1-4 kazanımlarından sonra hala baskın maliyet kalıp kalmadığını doğrulamak.
- GL compat'te davranış değişikliği gerekiyorsa bunu ayrı ve kontrollü fazda yapmak.
- Overlay uyumluluğunu korumayan agresif değişikliklerden kaçınmak.

Beklenen kazanım:
- Özellikle Windows build'lerinde ek termal düşüş

Risk:
- Yüksek

Faz 5 uygulama sonucu:
- Windows GL compat upload yolunda uygun 32-bit surface formatı için doğrudan surface buffer upload desteği eklendi.
- Uyumlu yüzeylerde pygame.image.tostring(..., 'RGBA', True) dönüşüm/kopya adımı atlanır hale getirildi.
- Uyumlu olmayan pixel formatları için eski RGBA fallback yolu korunarak overlay uyumluluğu dar ve savunmalı biçimde muhafaza edildi.

Faz 5 doğrulama özeti:
- GL compat upload kaynağı seçimi için hedefli birim testleri eklendi.
- Uyumlu BGRA yüzeylerde direct-buffer yolunun, uyumsuz yüzeylerde ise RGBA fallback yolunun seçildiği doğrulandı.
- Çalıştırılan dar test seti:
  - tests/test_gl_compat_upload.py
- Toplam sonuç: 3 test geçti.
- Mevcut Faz 4 dar regresyonları tekrar çalıştırılmadı; bu değişiklik GL compat modülüyle sınırlı tutuldu.
- Faz 5 retrospektif incelemesinde direct upload yolunun BGRA desteğini driver/context seviyesinde varsaydığı görüldü; runtime destek kapısı eklendi ve destek yoksa güvenli RGBA fallback korunacak şekilde dar test seti tekrar geçirildi.
- Faz 1-5 toplu geriye dönük incelemede GL compat create_display patch'inin yalnızca modül attribute'unu sardığı, önceden import edilmiş çağrı referanslarını kaçırabildiği görüldü; patch kapsamı genişletildi ve yeniden-kurulum akışları için hedefli regresyon testi eklendi.

Faz 5 risk notu:
- Direct upload yalnızca little-endian, pitch uyumlu, 32-bit yüzeylerde devreye giriyor; beklenmeyen formatlarda fallback korunuyor.
- Gerçek OpenGL context davranışı dar birim testle değil, Windows + Steam overlay smoke ile nihai teyit gerektirir.

## 7. Doğrulama Stratejisi

Her faz sonrası aşağıdaki akışlar elle kontrol edilecek:

### Menü smoke test
- Ana menü açılışı
- 2-3 dakika idle bekleme
- Hover ve seçim animasyonları
- Ayarlar ekranı
- Credits, Achievements, Guide ekranları

### Oyun smoke test
- Classic mod başlatma
- 3-5 dakika normal oynanış
- Pause aç/kapat
- Game over ekranı
- Exit prompt

### Campaign smoke test
- Level select açılışı
- Bir level başlatma
- Fail ve complete akışları

### PvP smoke test
- İsim girişi
- Maç başlatma
- Pause ve game over

### Online PvP smoke test
- Lobi ekranı
- Menüye geri dönüş
- Hata vermeden cleanup

### Platform smoke test
- macOS fullscreen açılış
- Windows Steam overlay açık akış
- Alt-tab / focus-loss sonrası stabilite

## 7A. Faz 1 Manuel Smoke Checklist

Bu checklist yalnızca Faz 1 kapsamını doğrulamak içindir.

Ana beklenti:
- fps_limit=0 artık sınırsız FPS gibi davranmamalı.
- fps_limit=0 artık ekranın gerçek yenileme hızına otomatik oturmalı.
- Görsel akıcılıkta düşüş hissedilmemeli.
- Menü, normal oyun, Local PvP ve Online PvP arasında pacing davranışı tutarlı kalmalı.

Uygulama notu:
- Mümkünse ilk turda ayarlar menüsünde FPS limiti değerini 0 yani Otomatik konuma getirerek test et.
- Mümkünse ikinci turda sabit bir değer seçip Otomatik ile farkı gözlemle.
- İstersen sıcaklık veya fanı ayrıca izle, ama bu checklistin ana kabul kriteri oyun içi davranıştır.

### Faz 1 ayar semantiği kontrolü
- Oyunu aç.
- Grafik ayarlarına gir.
- FPS limiti alanını bul.
- 0 değerinin MAX veya sınırsız yerine Otomatik olarak göründüğünü doğrula.
- FPS limitini 60, 120, 144 veya mevcut listede gördüğün başka bir sabit değere alıp etiketin doğru güncellendiğini doğrula.
- Tekrar 0 yani Otomatik değerine dön.
- Ayarlardan çıkıp yeniden girerek seçimin korunduğunu doğrula.

### Faz 1 ana menü smoke
- Ana menüde 2-3 dakika hiçbir giriş yapmadan bekle.
- Menü animasyonları akıcı kalıyor mu kontrol et.
- Ekranda gereksiz hızlanmış, titreyen veya aşırı hızlı akan bir his var mı kontrol et.
- Mouse ile kartlar arasında dolaş.
- Hover ve seçim animasyonlarında takılma, gecikme veya görsel downgrade var mı kontrol et.
- Menüden Ayarlar, Achievements, Guide gibi ekranlara girip geri dön.
- Her dönüşte menü pacing davranışının aynı kaldığını doğrula.

### Faz 1 normal oyun smoke
- Classic veya standart tek oyunculu bir mod başlat.
- İlk 30 saniyede giriş hissini kontrol et: sağ-sol hareket, rotate, soft drop, hard drop beklenen akıcılıkta mı bak.
- En az 3 dakika normal oynanış yap.
- Parçaların düşüş ritminde anlık hızlanma, mikro takılma veya düzensiz frame pacing hissi var mı kontrol et.
- Pause açıp 5-10 saniye bekle, sonra oyuna dön.
- Pause dönüşünde oyunun akışında bozulma olmadığını doğrula.
- Oyundan çıkıp ana menüye dön.
- Menüye dönüşte pacing davranışının bozulmadığını doğrula.

### Faz 1 Local PvP smoke
- 2 oyunculu yerel PvP akışına gir.
- Oyuncu isim girişleri ve başlangıç ekranı akıcı mı kontrol et.
- Maçı başlat.
- İki tarafta da taş akışı ve input hissi normal mi kontrol et.
- 2-3 dakika oynayıp pause akışını test et.
- Maçtan çıkıp menüye dön.
- Menüye dönüşte anormal pacing değişimi olmadığını doğrula.

### Faz 1 Online PvP smoke
- Online PvP veya lobi ekranına gir.
- Lobi bekleme ekranında kısa süre bekle.
- Ekranın canlı ama kontrolsüz hızda akmadığını doğrula.
- Mümkünse bir oda açma, odaya girme veya geri çıkma akışını dene.
- Ana menüye geri dön.
- Geri dönüş sonrası takılma, donma veya pacing sapması olmadığını doğrula.

### Faz 1 fullscreen ve focus smoke
- macOS kullanıyorsan fullscreen aç.
- Fullscreen geçişinden sonra menü ve oyun akıcılığının korunup korunmadığını kontrol et.
- Pencere moduna geri dön.
- Uygulamayı arka plana alıp tekrar öne getir.
- Focus geri geldiğinde pacing davranışının bozulmadığını doğrula.
- Eğer Windows tarafında da test edeceksen alt-tab sonrası menü ve oyun akışını ayrıca kontrol et.

### Faz 1 sabit limit karşılaştırma smoke
- Grafik ayarlarında FPS limitini sabit bir değere al.
- Ana menüde kısa süre bekle ve davranışı gözlemle.
- Tek oyunculu oyunu kısa süre açıp hissi karşılaştır.
- Tekrar Otomatik moda dön.
- Otomatik modun sınırsız gibi kontrolden çıkmadığını, sabit limite kıyasla ekran yenileme hızına doğal şekilde oturduğunu gözlemle.

### Faz 1 kabul kriteri
- 0 değeri her yerde Otomatik semantiğiyle çalışıyor olmalı.
- Otomatik modda oyun sınırsız FPS gibi davranmamalı.
- Otomatik modda oyun 60 FPS'e zorla çakılı hissettirmemeli.
- Menü, normal oyun, Local PvP ve Online PvP arasında pacing hissi tutarlı olmalı.
- Fullscreen veya focus değişimi sonrası pacing bozulmamalı.
- Görsel kalite, efekt yoğunluğu ve input hissi önceki davranışa göre düşmemeli.

## 7B. Faz 2 Manuel Smoke Checklist

Bu checklist yalnızca Faz 2 kapsamını doğrulamak içindir.

Ana beklenti:
- Textured block style açıkken görsel çıktı öncekiyle aynı kalmalı.
- Normal oyun, Local PvP ve Online PvP içinde texture'lı blok çizimi stabil çalışmalı.
- Texture cache yüzünden yanlış parça deseni, yanlış rotation veya yanlış hücre parçası görünmemeli.

Uygulama notu:
- Bu turda mümkünse texture veya görsel blok stili kullanan bir blok görünümü seç.
- Faz 1'i geçtiğin ayarlarla devam et; burada ana odak pacing değil, textured block doğruluğudur.

### Faz 2 blok stili hazırlık kontrolü
- Oyunu aç.
- Blok görünümü veya textured style seçilebilen ekrana gir.
- Düz renk yerine texture kullanan belirgin bir stil seç.
- Seçimden sonra ana menüye dön ve stilin aktif kaldığını doğrula.

### Faz 2 normal oyun texture smoke
- Classic veya standart tek oyunculu oyunu başlat.
- Farklı parça tiplerinin ekrana gelişini izle.
- Her parçanın hücre içi texture görünümünün tutarlı olduğunu doğrula.
- Rotate ettikçe texture yönünde bozulma, kayma, kırpılma veya yanlış hücre yüzeyi var mı kontrol et.
- Soft drop ve hard drop sırasında texture çizimi anlık bozuluyor mu kontrol et.
- En az 3-5 dakika oynayıp satır temizleme dahil normal akışta texture'ların stabil kaldığını doğrula.

### Faz 2 farklı parça ve rotation smoke
- Mümkün olduğunca I, O, T, S, Z, J ve L parçalarının birkaçını gör.
- Aynı parça farklı rotation durumlarına geçtiğinde texture yanlış yeniden kullanılıyor mu kontrol et.
- Özellikle ince veya uzun parçalarda stretch, bulanıklık sıçraması veya kenar kırılması var mı kontrol et.
- Parça yere oturduktan sonra board üzerindeki texture görünümünün aktif parçadakiyle tutarlı kaldığını doğrula.

### Faz 2 Local PvP texture smoke
- Local PvP akışına gir.
- Maçı başlat ve iki tarafta da birkaç farklı parça üret.
- Sol ve sağ board'da texture'lı blokların eşdeğer doğrulukta çizildiğini doğrula.
- Bir tarafta doğru, diğer tarafta bozuk texture reuse gibi bir durum var mı kontrol et.
- Kısa bir maç oynayıp menüye dön.

### Faz 2 Online PvP texture smoke
- Online PvP veya ilgili board gösteren bir lobi/oyun akışına gir.
- Kendi board'unda texture'lı blok çiziminin normal kaldığını doğrula.
- Eğer rakip board görünüyorsa onun da bozulmadan çizildiğini kontrol et.
- Ekrandan çıkıp tekrar girince texture çiziminde sapma oluşmadığını doğrula.

### Faz 2 kabul kriteri
- Textured block style açıkken görsel kalite düşmemeli.
- Yanlış texture parçası, yanlış rotation eşleşmesi veya yanlış hücre reuse görülmemeli.
- Normal oyun, Local PvP ve Online PvP içinde texture çizimi tutarlı kalmalı.
- Texture cache yüzünden flicker, ani bulanıklaşma veya frame bazlı görüntü sıçraması olmamalı.

## 7C. Faz 3 Manuel Smoke Checklist

Bu checklist yalnızca Faz 3 kapsamını doğrulamak içindir.

Ana beklenti:
- Gameplay efektleri görsel olarak korunmalı.
- Cache'lenen yardımcı effect surface'ler yüzünden alpha, glow veya wave davranışı bozulmamalı.
- Normal oyun, Local PvP ve Online PvP içinde efektler stabil kalmalı.

Uygulama notu:
- Bu turda mümkünse satır temizleme, particle, glow ve benzeri efektlerin sık görüneceği normal bir oynanış akışı seç.
- Amaç performans farkını hissetmekten çok efekt doğruluğunu bozmadan korunduğunu teyit etmektir.

### Faz 3 normal oyun efekt smoke
- Tek oyunculu oyunu başlat.
- Parça hareketi, yere oturma ve board üzerindeki temel glow/ışık hissini gözlemle.
- Birkaç satır temizleyerek satır temizleme efekti sırasında sweep, parlama veya wave görünümünü kontrol et.
- Efektlerin bir anda aşırı opak, aşırı sönük veya yanlış renkte görünüp görünmediğine bak.
- En az 3-5 dakika oynayıp efektlerde zamanla bozulma, birikme hissi veya görsel kirlenme olup olmadığını kontrol et.

### Faz 3 particle ve halo smoke
- Oyunda particle veya küçük glow noktalarının görüldüğü anları özellikle izle.
- Aynı efekt tekrarlandığında boyut, renk ve alpha değerleri tutarlı mı kontrol et.
- Bir efektin başka bir efektin görünümünü kirlettiği paylaşılmış surface hissi var mı kontrol et.
- Hızlı arka arkaya oluşan efektlerde ghosting, iz kalması veya beklenmedik kare şekilli alpha artığı var mı bak.

### Faz 3 pause ve dönüş smoke
- Oyun sırasında pause aç.
- Kısa süre bekleyip oyuna geri dön.
- Pause sonrası ilk birkaç saniyede efektlerin normal devam ettiğini doğrula.
- Menüye dönüp yeni bir oyun başlat.
- Yeni oyunda önceki oturumdan kalan görsel artığın taşınmadığını kontrol et.

### Faz 3 Local PvP efekt smoke
- Local PvP maçı başlat.
- İki board'da da satır temizleme veya benzer efektleri mümkünse gör.
- Sol ve sağ tarafta efekt yoğunluğu veya alpha davranışı farklılaşıyor mu kontrol et.
- Efektler bir board'dan diğerine sızıyor gibi bir reuse hatası var mı kontrol et.

### Faz 3 Online PvP efekt smoke
- Online PvP akışına gir.
- Kendi board'unda gameplay efektlerinin stabil olduğunu doğrula.
- Rakip board görünüyorsa görsel kirlenme veya yanlış glow taşıması var mı bak.
- Akıştan çıkıp menüye dönünce ekranda kalan glow/wave izi olmadığını doğrula.

### Faz 3 kabul kriteri
- Efektlerin rengi, alpha seviyesi ve yoğunluğu önceki kaliteyi korumalı.
- Tekrarlanan efektlerde görsel sapma, ghosting veya paylaşımlı surface mutasyonu görülmemeli.
- Pause, menü dönüşü ve yeni oyun başlangıcında eski efekt artıkları taşınmamalı.
- Normal oyun, Local PvP ve Online PvP içinde efekt davranışı tutarlı kalmalı.

## 7D. Faz 4 Manuel Smoke Checklist

Bu checklist yalnızca Faz 4 kapsamını doğrulamak içindir.

Ana beklenti:
- Ana menü dashboard içindeki statik kartlar cache'den gelirken görsel olarak aynı kalmalı.
- Hover, selection, split seçim ve alt buton içeren dinamik kartlar canlı davranışını korumalı.
- Menü içinde dil, içerik veya ekran değişimi sonrası yanlış cache reuse görülmemeli.

Uygulama notu:
- Bu turda özellikle ana menü dashboard kartlarına odaklan.
- Statik kartlar: daily_challenge, achievements, piece_workshop, block_styles.
- Dinamik bırakılan kartlar: new_gen_tetris, extras, tutorial_mode, campaign_mode, pvp_2_players.

### Faz 4 ana menü idle smoke
- Oyunu aç ve ana menü dashboard ekranında kal.
- 2-3 dakika idle bekle.
- Statik kartlarda flicker, geç yüklenme, boş kart veya yanlış içerik görünümü var mı kontrol et.
- Menü genelinde görsel kalite düşmeden stabil kaldığını doğrula.

### Faz 4 statik kart görsel doğrulama smoke
- daily_challenge kartını incele.
- Görev başlığı ve can kalpleri doğru mu kontrol et.
- achievements kartını incele.
- Son başarı isimleri ve yüzde barı doğru mu kontrol et.
- piece_workshop ve block_styles kartlarında arka plan görseli, başlık ve alt metin doğru mu kontrol et.
- Bu statik kartlara hover yapmadan ekranda kalırken içeriklerin kendiliğinden bozulmadığını doğrula.

### Faz 4 dinamik kart davranış smoke
- new_gen_tetris kartına hover yap.
- Hover highlight, buton ve geçiş hissinin canlı kaldığını doğrula.
- tutorial_mode ve campaign_mode kartlarında hover ve alt içerik davranışını kontrol et.
- pvp_2_players kartında local/online split alanlarının hover ve seçim tepkisini kontrol et.
- Dinamik kartlarda cache'lenmiş gibi donuk veya geç tepki veren bir his olmamalı.

### Faz 4 menü içi geçiş smoke
- Ana menüden Achievements ekranına gir ve geri dön.
- Ana menüden Guide veya benzeri başka bir ekrana gir ve geri dön.
- Ana menüye her dönüşte dashboard kartlarının doğru içerikle geldiğini doğrula.
- Menüden oyuna girip geri dön.
- Dönüşte statik kartların boş, eski veya yanlış içerikle görünmediğini doğrula.

### Faz 4 dil ve içerik invalidation smoke
- Mümkünse dili değiştir.
- Ana menüye dönüp statik kart başlıkları ve alt metinlerinin yeni dilde doğru güncellendiğini doğrula.
- Mümkünse daily challenge veya achievements içeriğini etkileyecek bir durum oluşturup menüye geri dön.
- Kartların eski cache içeriğini göstermediğini doğrula.

### Faz 4 campaign ve pvp özel davranış smoke
- campaign_mode kartındaki hızlı devam butonunu ve level bilgisini kontrol et.
- Bu kartın hover ve buton davranışının canlı kaldığını doğrula.
- pvp_2_players kartında local ve online yarıların ayrı hover tepkisi verdiğini doğrula.
- Bu iki kartta Faz 4 sonrası etkileşim kaybı olmadığını kontrol et.

### Faz 4 kabul kriteri
- Statik kartlar görsel olarak doğru ve stabil kalmalı.
- Dinamik kartlar canlı hover, selection ve alt buton davranışını korumalı.
- Menü içi ekran geçişleri sonrası yanlış veya eski cache içeriği görünmemeli.
- Dil veya içerik değişiminden sonra kart metinleri doğru invalidation ile güncellenmeli.
- Faz 4 değişikliği menü hissini donuklaştırmamalı veya etkileşim gecikmesi üretmemeli.

## 7E. Faz 5 Manuel Smoke Checklist

Bu checklist yalnızca Faz 5 kapsamını doğrulamak içindir.

Ana beklenti:
- Windows + Steam overlay açık akışta görüntü bozulmadan çalışmalı.
- Overlay açıkken oyun frame sunumu stabil kalmalı.
- Direct buffer upload yolu varsa sessizce çalışmalı, yoksa fallback devreye girerken davranış bozulmamalı.
- Faz 5 değişikliği overlay görünürlüğünü, focus davranışını veya pencere stabilitesini kırmamalı.

Uygulama notu:
- Bu checklistin ana değeri gerçek Windows ortamında ve mümkünse Steam üzerinden çalıştırıldığında ortaya çıkar.
- Mümkünse test turunu overlay etkin bir build ile yap.
- Mümkün değilse bu bölümü "beklemede" olarak işaretle; dar birim testler bunu tamamen ikame etmez.

### Faz 5 açılış ve overlay erişim smoke
- Oyunu Windows üzerinde Steam üzerinden başlat.
- Ana menüye sorunsuz ulaşıldığını doğrula.
- Steam overlay kısayolunu aç.
- Overlay'in görünür geldiğini ve oyunun donmadığını doğrula.
- Overlay'i kapat ve oyuna sorunsuz geri dönüldüğünü kontrol et.

### Faz 5 menü ve oynanış geçiş smoke
- Ana menüde 1-2 dakika bekle.
- Bu sırada overlay'i birkaç kez açıp kapat.
- Classic veya benzeri normal bir oyun başlat.
- Oynanış sırasında overlay'i tekrar açıp kapat.
- Görsel yırtılma, siyah ekran, ters çevrilmiş frame veya ağır takılma olup olmadığını kontrol et.

### Faz 5 focus ve pencere durumu smoke
- Oyun açıkken alt-tab yap.
- Oyuna geri dön.
- Mümkünse pencere modu ile fullscreen arasında bir geçiş yap.
- Her adımda görüntünün geri geldiğini ve input'un çalıştığını doğrula.
- Bu akışlarda overlay'in kaybolmadığını veya oyunun boşa düşmediğini kontrol et.

### Faz 5 fallback davranışı smoke
- Mümkünse farklı bir Windows makine veya farklı GPU/driver kombinasyonunda kısa tur yap.
- Overlay açılıp kapanırken davranışın ilk makineyle tutarlı kaldığını kontrol et.
- Beklenmeyen format/driver durumunda bile görüntü üretiminin bozulmadığını doğrula.
- Bu adım doğrudan direct path'i kanıtlamaz; amaç fallback durumunda kırılma olmadığını gözlemlemektir.

### Faz 5 uzun akış smoke
- 5-10 dakikalık kısa bir oynanış yap.
- Bu sırada overlay'i birkaç kez açıp kapat ve en az bir kez menüye geri dön.
- Çıkış akışını normal yoldan tamamla.
- Çıkışta takılma, siyah pencere veya kapanmayan süreç belirtisi olup olmadığını kontrol et.

### Faz 5 kabul kriteri
- Steam overlay görünür çalışmalı ve aç/kapa akışında oyun donmamalı.
- Menü ve oynanışta görsel bozulma, ters frame, siyah ekran veya belirgin yeni stutter oluşmamalı.
- Focus değişimi ve pencere durumu geçişleri sonrası görüntü ve input geri gelmeli.
- Farklı driver/context koşullarında olsa bile en kötü durumda güvenli fallback davranışı gözlemsel olarak korunmalı.
- Faz 5 değişikliği uyumluluğu korurken termal/perf hedefini bozacak görünür regresyon üretmemeli.

## 8. Test ve Güvenlik Notları

Repo'nun mevcut test tabanı tamamen temiz değil. Var olan test collection hataları bu optimizasyon işinden bağımsız mevcut durum olarak kabul edilmeli.

Bu nedenle strateji şu olacak:
- Önce davranış-korumalı küçük değişiklikler
- Sonra hedefli smoke test
- Gerekirse sadece değiştirilen hotspot için yeni test
- İlgisiz mevcut hataları bu çalışmaya katmama

## 9. İlk Uygulanacak Paket

İlk uygulanacak paket bilinçli olarak en düşük riskli olanlardan seçilmiştir.

İlk paket kapsamı:
- Ana frame pacing düzeltmesi
- fps_limit=0 semantiğini sınırsız yerine otomatik yenileme hızı kilidi olarak yeniden tanımlama
- Texture-backed block scaled-slice cache

İlk pakette özellikle dokunulmayacak alanlar:
- Steam overlay GL compat derin refactor
- HiDPI davranışı
- Görsel efekt yoğunluğunu azaltan ayarlar
- Büyük menu layer refactor

## 10. Kabul Edilmeyecek Yaklaşımlar

Bu plan kapsamında aşağıdaki tür değişiklikler başarısız sayılır:
- Oyunun daha serin çalışması için gözle görülür kalite düşüşü yapmak
- Frame pacing'i kullanıcı fark edecek şekilde hantallaştırmak
- 144 Hz veya daha yüksek ekranları gereksiz yere 60 FPS'e düşürmek
- macOS veya Windows'ta kalite sağlayan mevcut özellikleri kapatıp bunu optimizasyon diye sunmak
- Input gecikmesi yaratmak
- Steam overlay veya fullscreen davranışını bozmak
- Sadece benchmark kazanmak için oyun hissini bozan teknik karar almak

## 11. Çalışma Güncelleme Protokolü

Bu dosya yaşayan plan belgesidir.

Kural:
- Her uygulama adımı sonunda bu dosya güncellenecek.
- Tamamlanan fazlar işaretlenecek.
- Yeni risk veya bulgu çıkarsa ilgili bölüme eklenecek.
- Gerekirse "Tamamlandı" kopyası ayrıca üretilecek, ama ana çalışma kaydı bu dosyada kalacak.

## 11A. Faz Bazlı Uygulama Disiplini

Bu plan, tek seferde çok fazlı ve kontrolsüz ilerletilmeyecek.

Zorunlu çalışma düzeni:
- Her faz başlamadan önce ilgili kod bölgeleri yeniden okunacak ve o fazın etkilediği alanlar tekrar doğrulanacak.
- Faz içinde yalnızca o fazın kapsamına giren değişiklikler yapılacak.
- Faz tamamlandıktan sonra yazılan kod geriye dönük olarak tekrar incelenecek.
- Faz sonunda bulunan hatalı, zayıf veya riskli kısımlar mümkünse aynı faz içinde düzeltilecek.
- Faz sonunda doğrulama özeti ve risk notu bu dosyaya eklenecek.
- Faz bittiğinde çalışma durdurulacak ve sonraki faz için kullanıcı onayı beklenecek.

Faz geçiş kuralı:
- Kullanıcı açık şekilde "devam et" veya eşdeğer bir yönlendirme vermeden bir sonraki faza geçilmeyecek.
- Kullanıcı onayı gelirse, planın amacı ve kırmızı çizgileri korunarak sıradaki faza geçilecek.

Kod güvenliği kuralı:
- Hızlı ama kör değişiklik yapılmayacak.
- Her fazda önce anlama ve araştırma, sonra değişiklik, sonra geri dönük inceleme yapılacak.
- Faz sonu incelemesinde gerekirse aynı kod ikinci kez düzeltilerek faz kapatılacak.

Amaç hatırlatma:
- Her fazda hedef, kaliteyi düşürmeden ve platform özelliklerini kapatmadan gereksiz termal yükü azaltmaktır.
- Fazlar arası acele edilmemesi, hata riskini düşürmenin zorunlu parçasıdır.

## 12. Faz Takibi

- [x] Faz 1: Güvenli frame pacing düzeltmesi
- [x] Faz 2: Texture cell render cache
- [x] Faz 3: Allocation azaltma ve effect surface cache
- [x] Faz 4: Menü ve UI statik/dinamik katman ayrımı
- [x] Faz 5: Windows GL compat ince ayarı

## 13. Güncelleme Kaydı

### 2026-03-08
- İlk plan dosyası oluşturuldu.
- Kök nedenler toplandı ve risk seviyeleri ayrıldı.
- İlk uygulanacak paket, düşük riskli iki başlık olarak sabitlendi:
  - Güvenli frame pacing düzeltmesi
  - Texture-backed block scaled-slice cache
- Yeni karar işlendi: varsayılan FPS davranışı 60'a sabitlenmeyecek, cihazın gerçek yenileme hızına otomatik uyarlanacak.
- Şu an uygulama yerine plan düzeltme aşamasında kalınacağı not edildi.
- Kullanıcı tercihi işlendi: macOS ve Windows'ta kalite/özellik kapatma yolu optimizasyon yöntemi olarak kullanılmayacak.
- Termal hedefin "imkansız derecede soğuk çalışma" değil, kalite korunurken gereksiz aşırı ısınmayı azaltmak olduğu eklendi.
- Yeni çalışma disiplini işlendi: her faz sonunda yazılan kod geriye dönük incelenecek, hatalı kısımlar düzeltilmeye çalışılacak ve kullanıcı onayı olmadan sonraki faza geçilmeyecek.
- Faz 1 uygulandı: fps_limit <= 0 davranışı otomatik ekran yenileme hızı kilidine çevrildi.
- Ana loop, Local PvP ve Online PvP pacing akışları ortak çözümleyici ile hizalandı.
- Settings UI tarafında 0 değeri MAX yerine Otomatik olarak gösterilecek şekilde güncellendi.
- Düzenlenen dosyalarda statik hata kontrolü temiz geçti.
- Dar kapsamlı fullscreen settings testi çalıştırıldı; testler fullscreen onay modalı davranışında bu fazdan bağımsız görünen başarısızlıklar verdi.
- Faz 1 retrospektif düzeltmesi yapıldı: auto FPS helper'ındaki per-frame refresh sorgusu cache'lendi.
- Hedefli Faz 1 regresyon testleri eklendi ve geçti:
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Faz 1 burada kapatıldı; Faz 2 için kullanıcı onayı beklenecek.
- Faz 2 uygulandı: textured block hücreleri için ortak TextureRenderCache katmanı eklendi.
- Normal oyun, Local PvP ve Online PvP içindeki per-cell smoothscale yolu cache'li hale getirildi.
- Hedefli Faz 2 regresyon testleri eklendi ve geçti:
  - tests/test_block_styles_texture_render_cache.py
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Faz 2 retrospektif düzeltmesi yapıldı: TextureSlice width/height hesapları bozuk veri durumuna karşı savunmalı hale getirildi.
- Faz 2 burada kapatıldı; Faz 3 için kullanıcı onayı beklenecek.
- Faz 3 uygulandı: gameplay efekt yolları için ortak EffectSurfaceCache katmanı eklendi.
- Normal oyun, Local PvP ve Online PvP içindeki ambient particle sprite, particle halo, line sweep lit fill ve wave surface allocation'ları cache'li hale getirildi.
- Hedefli Faz 3 regresyon testleri eklendi ve geçti:
  - tests/test_effect_surface_cache.py
  - tests/test_block_styles_texture_render_cache.py
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Faz 3 retrospektif düzeltmesi yapıldı: explicit cache kapasitesi korunarak eviction davranışı test ile doğrulandı.
- Faz 3 retrospektif doğrulaması genişletildi: game.py içindeki girinti hatası py_compile ile yakalanıp düzeltildi; dar test seti tekrar geçti.
- Faz 3 için devam öncesi son kod incelemesi yapıldı; cache kullanım noktalarında yeni hata tespit edilmedi.
- Faz 3 burada kapatıldı; Faz 4 için kullanıcı onayı beklenecek.
- Faz 4 uygulandı: ana menü dashboard içindeki statik non-hover kartlar için yüzey cache'i eklendi.
- daily_challenge, achievements, piece_workshop ve block_styles kartları tekrar üretim yerine cache'den blit edilir hale getirildi.
- Hedefli Faz 4 regresyon testleri eklendi ve geçti:
  - tests/test_surface_lru_cache.py
  - tests/test_menu_dashboard_tile_cache.py
  - tests/test_effect_surface_cache.py
  - tests/test_block_styles_texture_render_cache.py
  - tests/test_platform_utils_display_toggle.py
  - tests/test_ui_mouse_slider.py
- Faz 4 retrospektif düzeltmesi yapıldı: aktif dil cache key'e eklendi ve dil profili/font değişimi için invalidation doğrulandı.
- Faz 4 burada kapatıldı; Faz 5 için kullanıcı onayı beklenecek.
- Faz 1 için oyun içi manuel smoke checklist plan dosyasına eklendi.
- Faz 2, Faz 3 ve Faz 4 için oyun içi manuel smoke checklistleri plan dosyasına eklendi.
- Faz 5 öncesi Faz 1-4 kod incelemesinde Faz 4 için ek bir invalidation boşluğu kapatıldı: menu transparency değeri dashboard tile cache key'e eklendi ve dar test seti tekrar geçti.
- Faz 5 uygulandı: Windows GL compat içinde uyumlu 32-bit surface'ler için direct buffer upload yolu eklendi; kopyalı RGBA fallback korunarak risk dar tutuldu.
- Faz 5 hedefli doğrulaması tamamlandı: tests/test_gl_compat_upload.py dar test seti 2/2 geçti.
- Faz 5 retrospektif düzeltmesi yapıldı: direct BGRA upload yolu runtime GL desteğiyle şartlandırıldı; destek yoksa fallback korunuyor ve hedefli test seti 3/3 geçti.
- Faz 5 için Windows + Steam overlay odaklı manuel smoke checklist plan dosyasına eklendi.
- Faz 1-5 toplu geriye dönük incelemede iki ek boşluk kapatıldı: auto refresh sorgusu aktif pencere refresh rate yolunu tercih edecek şekilde düzeltildi; GL compat create_display patch'i daha önce import edilmiş çağrı referanslarını da saracak şekilde genişletildi.