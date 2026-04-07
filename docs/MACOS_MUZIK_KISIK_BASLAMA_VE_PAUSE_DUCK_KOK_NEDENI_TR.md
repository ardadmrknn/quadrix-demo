# macOS'ta Müzik Kısık Başlıyor, Pause Aç-Kapa Sonrası Düzeliyor: Kök Neden ve Çözüm

Bu belge, macOS'ta oyun modlarına girildiğinde müziğin düşük sesle başlaması ve `P` ile pause menüsü açılıp kapatıldıktan sonra normal seviyeye dönmesi probleminin kök nedenini ve uygulanan düzeltmeyi özetler.

## Kısa Cevap

Sorun, müzik dosyasının kendisinde veya macOS mixer başlatmasında değil, paylaşılan `SoundManager` örneği üzerinde taşınan geçici bir ses durumundaydı.

- Pause menüsü açıldığında müzik `duck_music()` ile kısılıyordu.
- Bu kısılma durumu `SoundManager` içindeki `_music_duck_factor` alanında tutuluyordu.
- Menü ve gameplay aynı `SoundManager` örneğini paylaştığı için bu geçici state sahne/mod geçişine sızabiliyordu.
- Yeni moda girildiğinde ilk müzik seviyesi, yanlışlıkla eski duck factor ile hesaplanıyordu.
- Kullanıcı `P` ile pause aç-kapa yaptığında `duck_music()` ve ardından `unduck_music()` tekrar çalışıyor, factor `1.0` olduğu için müzik doğru seviyeye geri dönüyordu.

Özetle sorun, kalıcı ayar değil; temizlenmeyen geçici pause duck state'iydi.

## Belirti

Kullanıcı tarafında görülen davranış şuydu:

- Herhangi bir moda girildiğinde müzik normalden kısık başlıyor.
- Aynı oturumda `P` ile pause menüsü açılıp tekrar kapatılınca müzik normal seviyede çalmaya devam ediyor.
- Sorun özellikle macOS tarafında fark ediliyor çünkü ses seviyesi farkı ilk track başlangıcında belirgin hissediliyor.

Bu davranış şuna işaret eder:

- Müziğin base volume ayarı tamamen yanlış değil.
- Ses seviyesi daha sonra doğru uygulanabiliyor.
- Demek ki problem, track yükleme değil; başlangıç anında uygulanan state zincirinde.

## İnceleme Özeti

Araştırmada şu alanlar kontrol edildi:

- `src/sound.py` içindeki `play_music()`, `set_music_volume()`, `duck_music()`, `unduck_music()` ve `_compute_volume()` akışı
- `src/game.py`, `src/pvp_game.py` ve `src/online_pvp_game.py` içindeki pause aç/kapa davranışı
- `src/main.py` içindeki paylaşılan `menu_sound` örneğinin menüden oyuna ve oyundan menüye nasıl taşındığı
- Gameplay ve menu volume ayarlarının hangi akışlarda yeniden uygulandığı

Kritik gözlem şuydu:

- `SoundManager._compute_volume()` sesi hesaplarken `music_volume * track_multiplier * _music_duck_factor` kullanıyor.
- `_music_duck_factor` değeri `duck_music()` ile düşüyor, `unduck_music()` ile tekrar `1.0` oluyor.
- Ancak sahne değişiminde bu transient state her zaman sıfırlanmıyordu.

Bu yüzden yeni track doğru `music_volume` ile değil, eski duck factor ile başlıyordu.

## Asıl Kök Neden

Ses sistemi tek bir paylaşımlı `SoundManager` örneğini yeniden kullanıyor.

Bu tasarım doğru ve performans açısından gerekli. Ancak şu ayrım kritik:

- `music_volume` ve `sfx_volume` kalıcı kullanıcı ayarıdır.
- `_music_duck_factor` sadece geçici pause state'idir.

Sorun, geçici state'in kalıcı nesne üzerinde tutulup sahne değişiminde temizlenmemesiydi.

Örnek akış:

1. Kullanıcı bir ekranda pause açar.
2. `duck_music()` çağrılır ve `_music_duck_factor = 0.25` olur.
3. Aynı `SoundManager` örneği başka moda taşınır.
4. Yeni mod ilk track'i başlatırken `play_music()` içindeki `_compute_volume()` hâlâ `0.25` factor ile çalışır.
5. Müzik düşük sesle başlar.
6. Kullanıcı `P` ile pause aç-kapa yapınca `unduck_music()` factor'ü `1.0` yapar ve volume yeniden uygulanır.

Bu nedenle belirti tam olarak şöyle görünür:

- ilk başlangıç kısık
- pause aç-kapa sonrası normal

## Ek Bulgular

İnceleme sırasında şu ikinci risk de doğrulandı:

- `menu_sound` paylaşılarak PvP ve Online PvP içine enjekte edildiğinde, constructor içinde gameplay volume ayarları her zaman yeniden uygulanmıyordu.

Bu, duck state kadar kritik olmasa da menü state'inin gameplay'e taşınmasını kolaylaştırıyordu. Bu yüzden düzeltme sadece duck factor temizliğiyle sınırlı bırakılmadı; bazı mod girişlerinde gameplay ses ayarları da tekrar yükletildi.

## Nasıl Çözüldü

Çözüm, geçici pause state'ini sahne girişlerinde açıkça temizlemek oldu.

Uygulanan değişiklikler:

1. `src/game.py`
   `Game` kurucusunda, paylaşılan ses yöneticisi ayarlardan beslendikten sonra `unduck_music()` çağrıldı.

2. `src/pvp_game.py`
   `PvPGame` kurucusunda:
   - `music_enabled`
   - `sound_enabled`
   - `music_volume`
   - `sfx_volume`
   yeniden ayarlandı.
   Ardından `unduck_music()` çağrıldı ve sonra PvP müziği başlatıldı.

3. `src/online_pvp_game.py`
   `OnlinePvPGame` kurucusunda aynı mantık uygulandı:
   gameplay ses ayarları yeniden yüklendi, sonra `unduck_music()` ile transient pause state temizlendi.

4. `src/main.py`
   Ana menü müziği başlatılmadan önce ve oyundan menüye dönüş akışlarında `menu_sound.unduck_music()` çağrısı eklendi.

Bu sayede:

- paylaşılan `SoundManager` örneği korunmaya devam etti
- performans avantajı kaybedilmedi
- sadece pause'a ait geçici duck state sahne sınırında sıfırlandı

## Neden `stop_music()` İçine Konulmadı?

İlk bakışta `stop_music()` içinde `_music_duck_factor` temizlemek cazip görünebilir. Ancak bu fazla geniş bir davranış değişikliği olurdu.

Çünkü pause menüsündeki bazı akışlarda kullanıcı doğrudan müziği kapatıp tekrar açabiliyor. Böyle bir durumda `stop_music()` içine gömülü global reset, başka ses davranışlarını da dolaylı olarak değiştirebilir.

Bu yüzden düzeltme daha dar kapsamlı yapıldı:

- transient state, gerçekten sahne/mod başlangıcı olan yerlerde temizlendi
- pause içi seçenek akışları gereksiz yere yeniden tanımlanmadı

Bu yaklaşım daha güvenli ve niyet açısından daha nettir.

## Etkilenen Kod Alanları

Doğrudan güncellenen dosyalar:

- `src/game.py`
- `src/pvp_game.py`
- `src/online_pvp_game.py`
- `src/main.py`
- `tests/test_mode_entry_shared_sound_manager.py`

Sorunun mantıksal merkezi:

- `src/sound.py` içindeki `_compute_volume()`
- `src/sound.py` içindeki `duck_music()` / `unduck_music()`
- paylaşılan `menu_sound` örneğinin menü ve gameplay arasında tekrar kullanılması

## Doğrulama

Değişiklik sonrası ilgili regresyon testleri çalıştırıldı.

Geçen hedefli testler:

- `tests/test_mode_entry_shared_sound_manager.py`
- `tests/test_ingame_esc_opens_pause_menu.py`
- `tests/test_menu_music_global_tick.py`
- `tests/test_online_pvp_pause_freezes_input.py`

Toplam doğrulanan test sonucu:

- 21 test geçti

Tam test paketi bu değişiklik turunda baştan koşturulmadı; doğrulama, doğrudan bu bug ile ilişkili akışlara odaklandı.

## Sonuç

Sorun şuydu:

- Paylaşılan ses yöneticisi doğruydu ama pause için kullanılan geçici duck state sahne geçişlerinde temizlenmiyordu.
- Yeni modun ilk müziği, yanlışlıkla eski duck factor ile başlıyordu.

Çözüm şuydu:

- Menü ve gameplay girişlerinde `unduck_music()` ile transient pause state açıkça temizlendi.
- PvP ve Online PvP girişlerinde gameplay ses ayarları yeniden uygulandı.

Özetle: macOS'ta müziğin kısık başlamasının ana sebebi mixer init veya track dosyası değil, paylaşılan `SoundManager` üzerinde kalan pause duck state sızıntısıydı.