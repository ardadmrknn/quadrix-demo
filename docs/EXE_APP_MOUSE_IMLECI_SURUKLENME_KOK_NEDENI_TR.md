# Exe/App Buildlerinde Mouse Imlecinin Asagi Suruklenmesi: Kok Neden ve Cozum

Bu belge, paketlenmis exe/app buildlerinde gorulen mouse imlecinin yukari gitmek yerine asagi dogru cekiliyormus gibi davranmasinin gercek nedenini ve uygulanan duzeltmeyi ozetler.

## Kisa Cevap

Sorun, genel mouse girisinden degil, gamepad tarafindaki sag stick tabanli mouse emulasyonundan geliyordu.

- [src/gamepad_manager.py](../src/gamepad_manager.py) icinde sag stick eksenleri mouse hareketine cevriliyordu.
- Bu akista ham axis verisi her frame `pygame.mouse.set_pos(...)` ile fiziksel imlece uygulanıyordu.
- Deadzone dusuktu ve neutral merkez kalibrasyonu yoktu.
- Bu nedenle hafif stick drift, Steam Input sanal kontrolcu ofseti veya build ortamina ozel analog bias, imleci surekli asagi cekebiliyordu.

Uygulanan cozum, sag stick mouse emulasyonunu drift'e dayanikli hale getirmek oldu.

## Belirti

Kullanici tarafinda gorulen davranis su sekildeydi:

- Mouse imleci yukari dogru rahat hareket etmiyordu.
- Imlec sanki gorunmeyen bir guc tarafindan asagi dogru cekiliyordu.
- Bu durum ozellikle menu ve ayar ekranlarinda hissediliyordu.
- Sorun gelistirme ortaminda her zaman tekrar etmeyebilirken exe/app buildlerinde daha belirgin olabiliyordu.

Bu desen, klasik bir koordinat normalize hatasindan cok, arka planda imleci aktif olarak yeniden konumlandiran baska bir giris kaynagi olduguna isaret ediyordu.

## Neden Build'de Daha Gorunur Hale Gelebiliyor

Paketlenmis buildlerde su etkenler daha sik devreye girebilir:

- Steam Input veya baska bir sanal kontrolcu katmani
- Sisteme bagli ama aktif kullanilmayan bir gamepad
- Fiziksel kontrolcude hafif analog drift
- Overlay ya da runtime farklari nedeniyle joystick eksenlerinin gelistirme ortamindan farkli okunmasi

Kod, bu tur kucuk sapmalari "gercek mouse hareketi" gibi kabul edince, semptom kullaniciya imlecin kendi kendine asagi kaymasi olarak yansiyordu.

## Asil Kok Neden

Sorunun merkezindeki akış [src/gamepad_manager.py](../src/gamepad_manager.py) icindeki sag stick -> mouse emulasyonu yoluydu.

Temel problem noktaları:

- Sag stick icin kullanilan mouse deadzone esigi dusuktu.
- Neutral merkez icin runtime kalibrasyon yoktu.
- Aktivasyon ve birakma esikleri ayri degildi.
- Ham axis degerleri her zaman guvenli kabul ediliyordu.
- Hata veya display rebuild aninda mouse emulasyon state'i temizlenmiyordu.
- Son adimda `pygame.mouse.set_pos(...)` cagrisi ile fiziksel imlec dogrudan tasiniyordu.

Bu kombinasyonun sonucu su oldu:

- Eger sag stick Y ekseninde hafif bir pozitif bias varsa,
- kod bunu kucuk ama surekli bir asagi hareket olarak yorumladi,
- her frame yeni mouse konumu yazarak imleci kullanicinin hareketine karsi itti.

Yani sorun "mouse koordinati yanlis hesaplaniyor" degildi. Sorun, mouse'un arka planda gamepad kaynakli sentetik bir girdiyle surekli yeniden konumlandirilmasiydi.

## Uygulanan Cozum

Duzenleme [src/gamepad_manager.py](../src/gamepad_manager.py) icinde yapildi.

### 1. Sag stick icin neutral baseline eklendi

`GamepadState` icine sag stick'in ham degerlerini ve neutral merkezini takip eden alanlar eklendi.

Amac:

- kontrolcunun dogal merkez kaymasini runtime sirasinda tanimak,
- bu kaymayi mouse hareketi sanmamak.

### 2. Mouse emulasyonu yalnizca belirgin hareketle aktive oluyor

Kucuk analog sapmalar artik mouse emulasyonunu baslatmiyor.

- Aktivasyon esigi yuksek tutuldu.
- Birakma esigi ayrildi.
- Boylece hysteresis benzeri bir davranis elde edildi.

Sonuc:

- stick hafif sapti diye mouse hareketi baslamiyor,
- ancak kullanici kasitli sekilde sag stick'i iterse emulasyon hala calisiyor.

### 3. Radial deadzone uygulandi

X ve Y eksenlerini ayri ayri kesmek yerine, toplam vektor buyuklugune gore deadzone uygulanıyor.

Bu sayede:

- capraz drift daha dogru filtreleniyor,
- gercek kullanici hareketi daha tutarli olculuyor.

### 4. Ham axis degerleri sanitize ediliyor

Artik axis degeri okunurken:

- sayiya cevrilemiyorsa sifira dusuruluyor,
- `NaN` veya sonsuzsa sifira dusuruluyor,
- aralik disiysa `[-1.0, 1.0]` bandina cekiliyor.

Bu, bozuk cihaz verisi veya runtime anormalliklerinin tekrar ayni sorunu farkli yoldan uretmesini zorlastiriyor.

### 5. Display yoksa veya hata olursa state resetleniyor

Display surface gecici olarak yoksa ya da mouse emulasyonu akisinda sessiz bir exception olursa, mouse emulasyon state'i temizleniyor.

Bu sayede:

- eski frame'den kalan aktif mouse emulasyonu state'i tekrar kullanilmiyor,
- pencere yeniden kurulurken veya surface degisirken gizli drift birikimi kalmiyor.

## Tekrar Riskine Karsi Neden Daha Guvenli

Yeni akista ayni semptomun tekrarlamasi icin su kosullarin birlikte olmasi gerekir:

- sag stick bias'i neutral kalibrasyonu asacak kadar buyuk olmali,
- ayni bias aktivasyon esigini de gecmeli,
- kullanici tarafindan kasitli giris gibi gorunmeli,
- buna ragmen radial deadzone ve release mantigindan gecmeli.

Pratikte bu, hafif drift ve sanal kontrolcu ofsetlerinin artik genel menu mouse davranisini bozmasini ciddi sekilde zorlastirir.

## Incelenen Diger Mouse Yeniden Konumlandirma Noktasi

Kod tabaninda baska bir `pygame.mouse.set_pos(...)` kullanimı daha var:

- [src/game_modes_extra.py](../src/game_modes_extra.py)

Bu cagrinin baglami farkli:

- yalnizca sniper overlay aktifken,
- mouse'u oyun tahtasi sinirlari icinde tutmak icin,
- mod-ozel bir clamp davranisi olarak calisiyor.

Bu nedenle genel menu veya exe/app acilisindaki imlec asagi suruklenmesi sorununun ana kaynagi bu degildi.

## Dogrulama

Sorunun geri donmemesi icin su regresyon testleri eklendi:

- [tests/test_gamepad_mouse_emulation.py](../tests/test_gamepad_mouse_emulation.py)

Bu testler sunlari dogruluyor:

- hafif drift mouse'u oynatmamali,
- ilk frame bias neutral kabul edilip imleci suruklememeli,
- kasitli sag stick hareketi hala mouse motion uretmeli.

Hedefli test paketi gecti.

Tam pytest kosusunda bu issue ile iliskili yeni bir hata kalmadi. Kalan iki fail bu sorunla bagimsiz durumda:

- [tests/test_lb_write.py](../tests/test_lb_write.py) icindeki 403 Forbidden partner API problemi
- [tests/test_phase4_ui_scaling.py](../tests/test_phase4_ui_scaling.py) icindeki MagicMock `__spec__` problemi

## Sonuc

Sorun, mouse sisteminin kendisinden degil, gamepad tarafinda mouse'u taklit eden yardimci yolun fazla agresif olmasindan kaynaklaniyordu.

Kok neden suydu:

- sag stick girdisi,
- yeterli drift korumasi olmadan,
- dogrudan fiziksel imlec konumuna yaziliyordu.

Cozum su oldu:

- neutral kalibrasyon,
- aktivasyon/birakma esikleri,
- radial deadzone,
- axis sanitization,
- hata/display kaybi durumunda state reseti,
- ve regresyon testleri.

Ozetle: imleci asagi ceken sey mouse degil, drift'e duyarli gamepad mouse emulasyonuydu; cozum de bu emulasyonu kasitli girdi disinda sessiz kalacak sekilde yeniden tasarlamak oldu.