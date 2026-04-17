# macOS Co-op Arka Planinda Daha Opak Akan Bloklar ve Yildizlar: Kok Neden ve Uygulanan Cozum

## Problem Ozeti

Belirti su sekildeydi:

- Co-op arka planinda akan tetromino bloklari ve yildiz benzeri ambient parcaciklar, diger ekranlara gore daha opak gorunuyordu.
- Bu fark en belirgin sekilde macOS tarafinda fark ediliyordu.
- Ilk bakista sorun macOS'a ozel bir efekt kodu veya ayri bir platform branch'i gibi duruyordu.

## Inceleme Sonucu

Kod tabani tarandiginda su ayrim netlesti:

### 1. Akan tetromino sistemi ortak temelden geliyor

Menu, tek oyuncu, guide, extras ve benzeri ekranlar dusen tetromino katmanini `src/background_effects.py` icindeki ortak `FallingBlocksLayer` sinifindan aliyor.

Co-op da ayni temel sinifi kullaniyordu. Yani sorun ayri bir macOS efekt motoru degildi.

Ancak co-op burada iki fark uretiyordu:

- `default` yerine ayri isimli `coop` shared layer kullaniyordu.
- Bu layer icin daha yuksek blok sayisi veriyordu.

Sonuc: temel sinif ortak olsa da co-op gorunumu fiilen diger ekranlarla birebir ayni akmiyordu.

### 2. Yildiz/ambient parcacik sistemi ortak degildi

Tek oyuncu ve PvP tarafindaki ambient parcacik mantigi ile co-op ambient parcacik mantigi ayni helper'i paylasmiyordu.

Co-op kendi `_init_ambient_particles()`, `update_ambient_particles()` ve `draw_ambient_particles()` yolunu kullaniyordu.

Bu yol:

- farkli sayida parcacik,
- farkli boyut dagilimi,
- farkli hareket araligi,
- farkli glow/circle cizim profili

uretiyordu.

Bu da "ayni efekt gibi gorunuyor ama ayni degil" hissinin ikinci kaynagiydi.

### 3. Asil supheli fark: co-op'a ozel arka plan compositing yolu

Co-op ekraninda dis arka plan, diger gameplay ekranlarindan farkli olarak once tek bir cache surface uzerinde kompozitleniyordu.

Bu compositing yolunda:

- arka plan resmi,
- bg transparency,
- outer tint

tek bir pre-baked surface icinde birlestiriliyordu.

Tek oyuncu ve PvP ise bu alani daha dogrudan ciziyordu. Bu yuzden co-op, ayni ayarlar acikken bile farkli blend sonucu uretebiliyordu.

macOS tarafinda farkin daha belirgin hissedilmesinin ana nedeni buydu: sorun macOS'a ozel ayri kod tabani degil, co-op'a ozel render yolunun macOS backend'inde daha belirgin gorunmesiydi.

## Gercek Kok Neden

Kok neden iki katmanliydi:

1. Co-op efektleri diger ekranlarla gorunur anlamda tam parity icinde degildi.
2. Co-op dis arka plan cizimi, diger gameplay ekranlarindan farkli bir kompozit/cache yoluna sahipti.

Yani sorun "macOS icin ayri efekt kodu" degil, "co-op icin farkli render ve efekt profili" idi.

## Uygulanan Cozum

Sorunu kapatmak icin co-op tarafi diger ekranlarla hizalandi.

### 1. Co-op dusen blok katmani default ortak layer'a cekildi

- Co-op artik ayri `coop` layer yerine ortak `default` layer kullaniyor.
- Co-op'a ozel daha yogun blok sayisi profili kaldirildi.

Amac: arka plandaki akan tetromino davranisi menuler ve diger gameplay ekranlariyla ayni temel akisa donsun.

### 2. Co-op ambient parcacik profili game/PvP davranisina yaklastirildi

- Parcacik sayisi,
- boyut araligi,
- alpha araligi,
- hareket hizi,
- glow ve core cizim yolu

game/PvP tarafindaki profile yaklastirildi.

Amac: co-op'taki yildiz/ambient akisi diger ekranlardakiyle ayni hisse gelsin.

### 3. Co-op'a ozel pre-baked outer background composite yolu kaldirildi

Co-op dis arka plani artik:

- gerekirse `draw_full_screen_region()`,
- aksi halde `draw_full_screen()`

ile dogrudan ciziyor.

Outer tint yine uygulanmaya devam ediyor, ancak artik diger gameplay ekranlarina daha yakin bir cizim zinciri kullaniliyor.

Bu degisiklik, macOS'ta daha opak gorunme farkinin ana kaynagini hedefledi.

### 4. Artik gereksiz kalan coop layer senkronizasyonu temizlendi

`main.py` icindeki effects opacity senkronunda co-op'a ozel ayrik layer varsayimi kaldirildi. Cunku co-op artik ortak default layer kullaniyor.

## Etkilenen Dosyalar

- `src/coop_game.py`
- `src/main.py`

Referans mimari:

- `src/background_effects.py`
- `src/game.py`
- `src/pvp_game.py`

## Neden Bu Cozum Dogru

Bu duzeltme yuzeyde alpha sayisi oynamak yerine kok nedeni hedefliyor:

- platforma ozel bir bug varsaymiyor,
- co-op ile diger ekranlar arasindaki render farkini kaldiriyor,
- ortak efekt davranisini tek tabana yaklastiriyor,
- macOS'ta daha belirgin gorunen farkin kaynak noktasini daraltiyor.

Kisa ozet:

Sorun macOS'a ozel ayri kod degildi.
Sorun co-op'un diger ekranlardan farkli render edilmesiydi.
Kalici cozum de co-op'u diger ekranlarla ayni davranisa cekmek oldu.

## Dogrulama

Kod degisikligi sonrasi asagidaki dogrulama yapildi:

- `src/coop_game.py` Python compile OK
- `src/main.py` Python compile OK

Not:

Bu belge kod seviyesi kok neden analizi ve uygulanan duzeltmeyi anlatir.
Final goruntu parity onayi macOS cihaz uzerinde yapilmalidir.

## Benzer Sorun Tekrar Gorulurse Ne Kontrol Edilmeli

Su sirayla bak:

1. Ekran ortak helper kullaniyor mu, yoksa benzer gorunup ayri efekt profili mi uretiyor?
2. Shared layer ismi ve blok sayisi diger ekranlarla ayni mi?
3. Ambient parcaciklar ortak helper yerine mod-ozel cizim mi kullaniyor?
4. Arka plan once cache/composite edilip sonra mi blit ediliyor?
5. macOS'ta fark varsa, bu fark platform branch'inden mi geliyor yoksa mevcut cizim yolunun backend uzerindeki daha gorunur sonucundan mi doguyor?

Bu olaydan cikan ana ders su:

Ayni asset'i ve ayni temel sinifi kullanmak tek basina yeterli degil. Eger render zinciri farkliysa, son goruntu de farkli olur.
