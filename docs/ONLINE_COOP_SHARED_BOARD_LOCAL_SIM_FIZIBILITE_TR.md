# Online Co-op Shared Board ve Yerel Simulasyon Fizibilitesi

Tarih: 5 Mayis 2026

## Ozet

Temel fark su: PvP'de dusuk gecikmeyi saglayan sey ag optimizasyonu degil, yerel otorite sinirinin cok dar olmasi. Senin tusun sadece senin board'unu etkiliyor. Kodda bunun karsiligi iki ayri board olmasi: my_board ve opponent_board [src/online_pvp_game.py](src/online_pvp_game.py#L3203-L3204). Yerelde kendi parcan hemen hareket ediyor, sonra rakibe sadece goruntu icin parca konumu ve periyodik board snapshot gidiyor [src/online_pvp_game.py](src/online_pvp_game.py#L3922-L3978), [src/online_pvp_game.py](src/online_pvp_game.py#L4388-L4558). Gelen paketler de senin oyunun mantigini degil, sadece rakibin gorunumunu guncelliyor [src/online_pvp_game.py](src/online_pvp_game.py#L3075-L3095), [src/online_pvp_game.py](src/online_pvp_game.py#L3809-L3856), [src/online_pvp_game.py](src/online_pvp_game.py#L6491-L6515). Bu yuzden yerel hissedilen gecikme yaklasik bir frame; rakibin paketi gec gelse bile senin hamlen bozulmuyor.

Online co-op'ta ise PvP'deki anlamda iki ayri board yok; tek ortak 20x20 board var ve iki oyuncu o board'un iki yarisini paylasiyor [src/coop_board.py](src/coop_board.py#L39-L59). Host tam CoopGame simulasyonunu olusturup calistiriyor [src/online_coop_game.py](src/online_coop_game.py#L3021-L3048), update dongusunde de gercek oyunu yalnizca host ilerletiyor [src/online_coop_game.py](src/online_coop_game.py#L2314-L2330). Guest'in akisi ise farkli: input gonderiyor, host onu inject_remote_input ile gercek oyuna uyguluyor, sonra host board ve piece state'i geri yolluyor [src/online_coop_game.py](src/online_coop_game.py#L2755-L2888), [src/online_coop_game.py](src/online_coop_game.py#L3153-L3229). Guest tarafinda calisan CoopGame bugun tam otorite degil; render ve tahmin kopyasi [src/online_coop_game.py](src/online_coop_game.py#L2559-L2579), [src/online_coop_game.py](src/online_coop_game.py#L2616-L2698), [src/online_coop_game.py](src/online_coop_game.py#L3276-L3310). Bu yuzden guest kendi hamlesini aninda tahmin edebiliyor ama o hamlenin gercekten dogru olup olmadigini ancak host dondugunde biliyor. Otoriter onay gecikmesi kabaca $RTT$ mertebesinde; lokal prediction sadece bu gecikmeyi maskelemeye yariyor.

## Neden PvP Hizli Hissediliyor?

Buradaki asil problem parcalar birbirine carpiyor problemi degil. Orta cizgi sert duvar oldugu icin P1 ve P2 aktif parcalari dogrudan karsi tarafa gecemiyor [src/coop_board.py](src/coop_board.py#L39-L59). Bu iyi haber. Kotu haber su: satir temizleme 20 sutunun tamamina bakiyor ve owner grid uzerinden iki oyuncunun katkisini birlikte hesapliyor [src/coop_board.py](src/coop_board.py#L77-L110). Kilitleme, yeni parca spawn, freeze, unfreeze ve lock delay kararlari da ayni shared board ustunde veriliyor [src/coop_game.py](src/coop_game.py#L1963-L2230), [src/coop_game.py](src/coop_game.py#L2473-L2615). Yani ayni anda olan iki eylemin tek bir dogru sirasi var.

Basit ornek: $t_0$ aninda P2 soldan saga kayiyor, neredeyse ayni anda P1 hard drop ile bir satiri tamamliyor. Eger satir temizlenirse P2'nin bulundugu satir asagi kayabilir, spawn/freeze durumu degisebilir, contribution ve score degisir. Hangi olayin once islendigI ortak board sonucunu degistirir. Host otoritesi bugun bunu tek merkezde cozuyor.

PvP'de ise rakip state sadece goruntu amacli tuketiliyor. Rakip board ve rakip piece verisi senin oyunun fizik kararina girmiyor; sadece cizimde kullaniliyor [src/online_pvp_game.py](src/online_pvp_game.py#L3809-L3856), [src/online_pvp_game.py](src/online_pvp_game.py#L6491-L6515). Bu nedenle PvP'de bir makinenin kendi board'unu yerelde otoriter isletmesi dogrudan ve dogal bir model.

## Online Co-op'ta Su Anki Model

Bugunku online co-op modelinde host tam simulasyonu calistirir. Guest ise kendi input'unu aninda tahmin eder ama authoritative state'i host'tan alir.

Ana mekanik akisi:

1. Guest input gonderir.
2. Host input'u gercek CoopGame'e inject_remote_input ile uygular.
3. Host board ve aktif parca state'lerini geri yollar.
4. Guest gelen state ile kendi render kopyasini duzeltir.

Bu modelin avantajlari:

- Shared board icin tek gercek karar noktasi vardir.
- Satir temizleme, skor, owner katkisi, freeze/unfreeze gibi ortak kararlar tek yerde verilir.
- Deterministik olmama veya saat farki gibi sorunlar host merkezde bastirilir.

Bu modelin dezavantaji:

- Guest icin gercek onay host round-trip bekler.
- Prediction sadece his iyilestirir; authority degistirmez.

## Her Makinede Tum Shared Board'u Yerelde Simule Etmek Mümkün mu?

Mumkun, ama bunu dogru isimlendirmek lazim. Co-op'ta bunu yapmak, her iki makinede de ayni ortak board'un tamamini deterministik olarak calistirmak anlamina gelir. Bu uc modelden birine cikar.

### 1. Lockstep

Her iki istemci frame N icin iki oyuncunun input'unu da bekler, sonra ayni shared board'u ayni sirayla isler. Bu tutarli calisir ama gecikmeyi azaltmaz; tam tersine yerel input'u bekletir. Amac dusuk input latency ise bu yanlis modeldir.

### 2. Rollback

Iki istemci de ayni shared board'u yerelde hemen simule eder, eksik remote input'lari tahmin eder, gercek input gelince eski frame'e donup yeniden simule eder. Bu model PvP hissine en yakin olan modeldir. Ama mevcut kodda bu kucuk bir port degil, netcode mimarisi degisimi olur.

### 3. Hibrit

Bugunku host otoritesini korur, guest tarafinda daha agresif yerel simulasyon uygularsin. Bu, hissedilen gecikmeyi azaltir ama shared board yuzunden lock, line clear, freeze, unfreeze gibi anlarda yine host duzeltmesi gerekir. Bugunku sistem zaten bunun minimal versiyonunu yapiyor; guest input prediction var ama tam bagimsiz simulasyon yok [src/online_coop_game.py](src/online_coop_game.py#L3276-L3310).

## Rollback Neden Buyuk Is?

Tam rollback neden buyuk is, cunku kod tabaninda bazi temel onkosullar henuz yok.

Iyi taraf:

- CoopGame zaten deterministic bag seed temeline sahip. Match seed gelirse P1 ve P2 icin ayri ama sabit RNG'ler kuruluyor [src/coop_game.py](src/coop_game.py#L238-L256), bag'ler de ayri tutuluyor [src/coop_game.py](src/coop_game.py#L312-L320), [src/coop_game.py](src/coop_game.py#L917-L930). Bu, ayni input akisi verilirse ayni parca sirasi uretilebilir demek.

Kotu taraflar:

- Simulasyon bugun frame-indexli degil, delta_time temelli. CoopGame.update kayan zamanla calisiyor [src/coop_game.py](src/coop_game.py#L2556-L2615), host da guest input'unu ulastigi anda isliyor [src/online_coop_game.py](src/online_coop_game.py#L2835-L2863). Rollback icin input'larin hangi simulasyon frame'ine ait oldugu kesinlesmeli.
- Simulasyon ile sunum ayrismis degil. Ses, partikül, shake, event yayini ve oyun mantigi ayni sinifta ic ice [src/coop_game.py](src/coop_game.py#L1999-L2054), [src/coop_game.py](src/coop_game.py#L2062-L2230), [src/coop_game.py](src/coop_game.py#L2556-L2615). Rollback sirasinda bunlari saf simulasyondan ayirmazsan her yeniden simulasyonda efekt ve sesleri tekrar tetiklersin.
- Bugun protokol input-stream odakli degil; state snapshot odakli. Co-op mesaj semasi guest input ve host state snapshot mantiginda [src/online_coop_game.py](src/online_coop_game.py#L2835-L2888), [src/online_coop_game.py](src/online_coop_game.py#L3153-L3229). Rollback icin frame numarali input paketleri, ack, checksum ve periyodik resync gerekir.
- Full shared state snapshot/restore altyapisi yok. Sadece belli board durumlarini geri yukleyen yerel yardimcilar var; rollback icin board, iki aktif parca, iki next, iki hold, bag index'leri, fall timer'lar, DAS, lock delay, freeze bayraklari, contribution sayaclari ve pending line-clear/unfreeze state'i dahil tum gameplay state'inin buffer'lanmasi gerekir.

## Pratik Sonuc

Mevcut shared-board co-op'u hic degistirmeden PvP ile ayni hissiyata getirmek teoride mumkun, ama bunun yolu PvP optimizasyonlarini kopyalamak degil, shared-board rollback netcode yazmak. Bu ise kucuk/orta olcekli iyilestirme degil, buyuk refactor. Bugunku kod bazinda yapilabilirlik var, ama maliyeti yuksek ve riskli. En pahali kisim ag degil; deterministik frame sistemi ile simulasyon/sunum ayrimi.

En dogru teknik hukum su:

- Ayni shared-board tasarimini koruyup sadece ag katmanini iyilestirerek PvP seviyesine cikamazsin.
- Ayni shared-board tasarimini koruyup rollback yazarsan cikabilirsin, ama bu yeni bir multiplayer cekirdegi sayilir.
- Eger amac PvP kadar hizli hissetsin ise en dusuk riskli yol, co-op tasarimini iki ayri 10x20 board'a cevirmektir. O zaman PvP modeli neredeyse dogrudan uygulanir. Ama bu da artik bugunku shared-board co-op olmaz; farkli bir mod olur.

## Pragmatik Yön

Bugunku moda en uygun pragmatik yon ise hibrit cizgi:

- Host otoritesini koru.
- Guest tarafinda yalniz input ani degil, local gravity, DAS ve lock preview da kostur.
- Host'tan gelen state ile sadece correction yap.
- Lock, line clear, freeze, unfreeze gibi ortak-board olaylarinda host otoritesi kalsin.

Bu yol PvP kadar temiz olmayacak, ama mevcut oyunu parcalamadan hissedilen gecikmeyi daha da asagi ceker.

## Son Hukum

PvP kadar hizli hissettiren model, PvP'de dogrudan board ayriligindan geliyor. Online co-op'ta ayni hissi ayni shared-board tasarimi ile elde etmek istersen, bunun maliyeti tam rollback/shared simulation mimarisi kurmaktir. Bu yapilabilir ama buyuk bir mimari degisimdir. Kucuk bir optimizasyon paketi degildir.

Eger hedef mevcut modu koruyarak input lag'i dusurmekse, en mantikli yol bugunku host-authoritative modeli daha guclu guest-side local simulation ile hibritlestirmektir.
