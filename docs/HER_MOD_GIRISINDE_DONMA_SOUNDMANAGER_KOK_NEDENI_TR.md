# Her Mod Girişindeki Donmanın Kök Nedeni: Tekrarlanan SoundManager Kurulumu

Bu belge, oyun modlarına girerken görülen yaklaşık 2-3 saniyelik donmanın gerçek nedenini ve uygulanan düzeltmeyi özetler.

## Kısa Cevap

Sorun, arka plan resmi yükleme veya geçiş efekti kadar görünür olmayan ama daha pahalı bir ortak yoldu:

- Bazı modlar, ana menüde zaten var olan paylaşımlı ses yöneticisini kullanmıyordu.
- Bunun yerine her mod girişinde yeni bir `SoundManager()` oluşturuluyordu.
- `SoundManager()` kurulumu içinde SFX üretimi ve müzik taraması senkron çalıştığı için giriş anında ana thread bloklanıyordu.

Sonuç olarak donma, ilk girişe özel değil, ilgili modlara her girişte tekrar edebiliyordu.

## Belirti

Kullanıcı tarafında gözlenen davranış:

- Ana menüden herhangi bir oyun moduna girince kısa bir bekleme / donma yaşanması
- Bu donmanın oyun alanı görünmeden hemen önce olması
- Sorunun yalnızca ilk açılışta değil, modlara tekrar tekrar girildiğinde de sürmesi

Bu davranış, tek seferlik cache ısınmasından çok, her girişte yeniden çalışan ortak bir kurulum maliyetine işaret ediyordu.

## İlk Şüpheler ve Neden Yeterli Olmadıkları

Araştırma sırasında şu alanlar da incelendi:

- Menüden çıkıldıktan sonra aynı tick içinde gereksiz `menu.draw()` / `extras.draw()` çağrıları
- Büyük panel görsellerinin ilk kez ölçeklenmesi
- Oyun arka planlarının yüklenmesi ve cachelenmesi
- Ekran geçiş efekti maliyeti
- Müzik dosyasının `pygame.mixer.music.load(...)` ile yeniden yüklenmesi

Bu alanlarda gerçekten iyileştirme yapıldı ve bazı maliyetler düşürüldü. Ancak kullanıcı geri bildirimi kritik bir ipucu verdi:

- Donma her mod girişinde devam ediyordu.

Bu yüzden asıl kök nedenin, her girişte yeniden kurulan ortak bir nesne veya alt sistem olması gerekiyordu.

## Asıl Kök Neden

Ana oyun sınıfında ses yöneticisi şu mantıkla belirleniyordu:

```python
self.sound = sound_manager or SoundManager()
```

Yani bir mod, dışarıdan `sound_manager` almazsa otomatik olarak yeni bir `SoundManager()` kuruyordu.

Sorun şuydu:

- Bazı mod girişlerinde `sound_manager=menu_sound` geçiriliyordu
- Ama birçok modda bu parametre hiç geçirilmiyordu
- Bu yüzden o modlar her açılışta yeni bir `SoundManager()` yaratıyordu

Bu yeni kurulum hafif değildi. Profil ölçümünde görülen ana maliyet:

- `SoundManager.__init__`
- `create_sounds()`
- `create_gameplay_sfx()`
- özellikle `create_layered_sfx()`

Bu yol sentez tabanlı efekt üretimi yaptığı için CPU üzerinde pahalıydı ve ana thread'i blokluyordu.

## Ölçüm Özeti

Yerel ölçümlerde şu tablo görüldü:

- Tek bir `SoundManager()` kurulumu yaklaşık `616 ms` sürdü
- Ayrıntılı profilde bu kurulum yolu yaklaşık `1.7 s` toplam CPU zamanı üretti
- Paylaşımlı ses yöneticisiyle açılan örnek modlar belirgin biçimde hızlandı

Örnek karşılaştırmalar:

- `SprintMode`: yaklaşık `521 ms` -> `205 ms`
- `MysteryMode`: yaklaşık `564 ms` -> `51 ms`

Bu fark, kullanıcının tarif ettiği mod giriş donmasıyla doğrudan uyumludur.

## Nasıl Çözüldü

Çözüm basit ama etkiliydi:

1. Mod sınıflarına `sound_manager` parametresi eklendi.
2. Bu parametre üst sınıfa iletildi.
3. `main.py` içindeki mod açılış akışlarında mevcut `menu_sound` nesnesi bu modlara geçirildi.

Böylece:

- her mod girişinde yeni `SoundManager()` kurulması engellendi
- ses sistemi tek bir paylaşımlı örnek üzerinden yönetildi
- ağır SFX sentezi tekrar tekrar çalışmaz hale geldi

## Etkilenen Kod Alanları

Güncellenen ana dosyalar:

- `src/main.py`
- `src/game_modes.py`
- `src/game_modes_advanced.py`
- `src/game_modes_extra.py`
- `src/campaign/campaign_mode.py`

Sorunun düğüm noktaları:

- `src/game.py` içindeki `self.sound = sound_manager or SoundManager()` hattı
- `src/sound.py` içindeki `SoundManager.__init__` ve SFX üretim akışı

## Önemli Not

Bu düzeltme, daha önce yapılan diğer performans iyileştirmelerini gereksiz kılmaz.

Önceki iyileştirmeler:

- state değişiminden sonra gereksiz menü draw çağrılarını atlama
- ana menü panel görselleri için ön ısıtma / cache
- arka plan ön ısıtma / cache
- geçiş efektini hafifletme

Bunlar yan maliyetleri azalttı. Ancak kullanıcıda tekrar eden donmayı açıklayan ana kök neden, modların bazı kollarında paylaşımlı ses yöneticisinin kullanılmamasıydı.

## Sonuç

Sorun şuydu:

- Her mod girişinde aslında sadece oyun nesnesi kurulmuyordu.
- Bazı modlarda sıfırdan yeni bir ses sistemi de kuruluyordu.
- Bu kurulum pahalı olduğu için girişte hissedilir donma yaratıyordu.

Çözüm şuydu:

- Tüm ilgili mod girişlerini tek bir paylaşımlı `menu_sound` nesnesine bağlamak
- Böylece `SoundManager()` kurulumunu tekrar tekrar çalıştırmamak

Özetle: donmanın ana sebebi görsel geçiş değil, tekrar eden ağır ses yöneticisi kurulumuydu.
