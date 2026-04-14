# macOS Co-op Acilis 30 FPS Hissi: Kok Neden ve Kalici Cozum

## Problem Ozeti

Belirti su sekildeydi:

- Sorun esas olarak macOS MacBook M2 ic ekraninda goruluyordu.
- Local co-op moduna giriste ilk acilis perdesi ve ilk yarim saniye belirgin sekilde takiliyordu.
- Oyuncu tarafi hissi 20-30 FPS ve input lag gibiydi.
- Buna ragmen render tarafinda gorunen maliyetler bazen dusuktu; yani sorun ilk bakista sadece cizim yukunden ibaret degildi.

Bu hata klasik tek oyuncu, kart/mastery benzeri akislar veya local PvP kadar belirgin degildi; en belirgin sekilde co-op ailesinde ortaya cikiyordu.

## Bizi Yaniltan Ilk Bulgular

Ilk etapta su alanlar supheliydi:

- acilis perdesinin her kare agir ciziliyor olmasi,
- co-op HUD ve board tarafinda frame basi fazla surface olusturulmasi,
- arka planin ilk karelerde pahali olmasi.

Bunlarin bir kismi gercekten maliyet uretiyordu ve optimize edildi. Ancak asagidaki imza ortaya cikinca asil sorunun sadece render maliyeti olmadigi netlesti:

- render avg/max kabul edilebilir seviyeye indi,
- background maliyeti belirgin sekilde dustu,
- ama logic dt hala yaklasik 33-34 ms civarinda kaldi.

Bu imza, CPU tarafinin yetismemesinden cok frame presentation veya vblank pacing problemine isaret ediyordu.

## Gecici Profiler Ile Gorulen Ana Ipuclari

Tanilama icin co-op acilisinin ilk 500 ms kismina gecici profiler eklendi. Bu arac sonradan koddan cikarildi; amaci sadece kok nedeni bulmakti.

Profiler ile gorulen sira soyleydi:

1. Ilk asamada render_background zirve maliyeti yuksekti.
2. Arka plan yolu optimize edilince render maliyeti anlamli sekilde dustu.
3. Buna ragmen logic dt bazen 33 ms civarinda kalmaya devam etti.
4. Bu da ikinci bir frame pacing problemi oldugunu gosterdi.

## Gercek Kok Neden

Asil kok neden main loop tarafindaki cift flip davranisiydi.

Co-op ailesindeki bazi state'ler ekrani kendi draw akisi icinde zaten flip ediyordu:

- coop
- coop_campaign
- online_coop

Buna ragmen ana loop kare sonunda bir kez daha su paterni calistiriyordu:

- transition overlay ciz
- pygame.display.flip()

Sonuc olarak ayni frame icinde ikinci bir flip denemesi oluyordu. macOS ic ekranda bu davranis vblank'i kacirip kareyi bir sonraki senkrona itebiliyordu. Disaridan gorunen etki su oldu:

- render suresi normal,
- ama efektif frame pacing yari frekansa dusmus gibi,
- logic dt yaklasik 33 ms,
- kullanici hissi 30 FPS ve input lag.

Kisa ozet:

Render problemi vardI, ama son kalan ana sorun render degil cift present/flip problemiydi.

## Yapilan Duzeltmeler

Sorun tek bir satirdan ibaret degildi; iki katmanli bir fix yapildi.

### 1. Co-op acilis render maliyeti dusuruldu

Asagidaki iyilestirmeler korunuyor:

- Acilis perdesi daha hafif dogrudan cizim yoluna cekildi.
- Perde aktifken sadece gorunen orta bolge cizildi; gereksiz full-screen arka plan cizimi azaltildi.
- Outer background + tint kompoziti cache'lenip tekrar kullanildi.
- Bazi frame, HUD ve panel cache'leri acilista prewarm edildi.
- Cesitli co-op render yollarinda frame basi allocation sayisi azaltildi.

Bu degisiklikler tek basina kok nedeni cozmese de ilk 500 ms render sivrilmelerini belirgin sekilde dusurdu.

## 2. Main loop'taki gereksiz ikinci flip kaldirildi

Kalici fix buydu.

Ana loop artik sadece su durumda sonda flip yapiyor:

- transition overlay aktifse, veya
- ilgili state ekrani kendi icinde flip etmiyorsa.

Boylece co-op ailesinde ayni frame icinde ikinci present zorlanmiyor.

## Ilgili Dosyalar

- src/main.py
- src/coop_game.py
- src/background.py
- src/mode_skins.py

## Neden Bu Fix Dogru

Son dogrulama metrikleri soyleydi:

- logic dt yaklasik 17.0 ms
- frame avg/max yaklasik 6.2 / 8.3 ms
- render avg/max yaklasik 4.1 / 4.7 ms
- render_background last/avg/max yaklasik 0.4 / 0.6 / 1.1 ms

Bu tablo su anlama gelir:

- render tarafi artik ana darboz degil,
- frame pacing yari frekansta degil,
- macOS ic ekranindaki acilis akisi normal kare temposuna dondu.

## Benzer Sorun Tekrar Gorulurse Ne Kontrol Edilmeli

Su sira ile bak:

1. Render sureleri dusuk oldugu halde logic dt 33 ms civarinda mi?
2. Problem yalnizca macOS veya sadece belirli display yolunda mi goruluyor?
3. State kendi draw() icinde flip ediyor mu?
4. Main loop ayni frame sonunda tekrar flip ediyor mu?
5. Transition overlay veya baska bir global katman ikinci present zorluyor mu?

Eger render 4-8 ms bandinda oldugu halde kullanici 30 FPS hissediyorsa, once presentation zincirine bakmak gerekir. Ozellikle self-flipping state + global final flip kombinasyonu tekrar kontrol edilmelidir.

## Pratik Not

Bu olaydan cikan en onemli ders su:

Dusuk render maliyeti tek basina yeterli degildir. macOS tarafinda frame pacing, vblank ve display present zinciri bozulursa oyun kağıt uzerinde hizli gorunur ama kullaniciya yavas hissedilir.