# Online PvP Akış ve Mantık Rehberi

Bu belge, Online PvP modunun oyuncu açısından nasıl aktığını ve kod tarafında hangi temel mantıklarla çalıştığını özetler.

Ana referans dosyalar:

- `src/online_pvp_game.py`
- `src/steam_networking.py`
- `src/board.py`

## 1. Genel Amaç

Online PvP, Steam P2P üzerinden iki oyuncunun aynı anda bire bir Tetris maçı yapmasını sağlar.

Sistem şu hedefler üzerine kurulu:

- iki oyuncunun aynı parça sırasını alması
- kendi tahtasını yerel gibi oynaması
- rakibin tahtasını ve aktif parçasını ağ üzerinden görmesi
- biri elenince maçın bitmesi

## 2. Durum Akışı

Online PvP, `OnlineState` durum makinesi ile çalışır.

Temel akış:

1. `LOBBY_MENU`
2. `WAITING`
3. `READY_CHECK`
4. `COUNTDOWN`
5. `PLAYING`
6. `GAME_OVER` veya `DISCONNECTED`

Kısa açıklama:

- `LOBBY_MENU`: Oyuncu lobi oluşturur, koda göre katılır veya lobi listesine bakar.
- `WAITING`: Lobi kurulmuştur, rakip beklenir.
- `READY_CHECK`: İki oyuncu da lobidedir; hazır durumu beklenir.
- `COUNTDOWN`: Host oyunu başlatır, 3-2-1 geri sayım oynar.
- `PLAYING`: Gerçek maç bu aşamada çalışır.
- `GAME_OVER`: Maç sonucu belli olmuştur.
- `DISCONNECTED`: Rakip bağlantıdan düşmüştür veya çıkmıştır.

## 3. Lobi ve Maç Başlatma Mantığı

### 3.1 Lobi oluşturma / katılma

Oyuncular farklı yollarla aynı lobide buluşabilir:

- Steam daveti
- lobi kodu
- tam lobby id
- public lobi listesi

Lobi kurulduktan sonra iki tarafta da `SteamNetworking` aktif olur ve event/message kuyruğu işlenmeye başlanır.

### 3.2 Hazır kontrolü

Her iki oyuncu da hazır olduğunda host tarafı oyunu başlatır.

Host şu kritik bilgileri yollar:

- `seed`
- önceden üretilmiş parça dizisinin ilk bölümü

Böylece iki taraf da aynı sırayla aynı parçaları alır.

### 3.3 Countdown

`COUNTDOWN` sırasında oyun fiziği henüz akmaz. Sayaç bitince `_start_game()` çağrılır ve gerçek maç başlar.

## 4. Maç İçindeki Ana Döngü

`PLAYING` durumunda ana döngü kabaca şu sırayla çalışır:

1. ağ olayları ve mesajları işlenir
2. oyuncu input'u alınır
3. aktif parça düşürülür
4. lock gecikmesi kontrol edilir
5. gerekirse parça kilitlenir
6. periyodik olarak rakibe board snapshot gönderilir
7. rakibin aktif parçası ve skoru güncellenir

Bu yüzden oyuncu kendi tarafında yerel hissiyle oynarken rakip tarafı da ağdan gelen verilerle canlı tutulur.

## 5. Parça Akışı

Her oyuncuda bir aktif parça ve bir sonraki parça vardır.

Akış:

1. aktif parça spawn olur
2. oyuncu sağa/sola hareket ettirir, döndürür, soft drop veya hard drop yapar
3. parça aşağı daha fazla inemiyorsa lock timer çalışır
4. lock süresi dolarsa parça tahtaya yazılır
5. satır temizleme hesaplanır
6. yeni parça alınır

Online PvP için önemli nokta, iki tarafın parça sırasının aynı olmasıdır. Bu adalet için kritik tasarım kararıdır.

## 6. Ağ Üzerinden Senkronlanan Veriler

Online PvP tam bir lockstep simülasyon değildir. Bunun yerine hibrit bir model kullanır.

Gönderilen başlıca veriler:

- hazır durumu
- oyun başlangıç bilgisi
- aktif parça pozisyonu
- skor, satır, level bilgisi
- board snapshot
- game over bilgisi

### 6.1 Board snapshot

Rakibin tahtası belirli aralıklarla gönderilir. Bu snapshot içinde tipik olarak şunlar bulunur:

- grid
- score
- lines
- level
- bazı efekt yardımcı alanları

Bu sayede sağ tarafta rakibin güncel tahtası çizilir.

### 6.2 Aktif parça pozisyonu

Rakibin o anda oynadığı aktif parça ayrı düşük gecikmeli mesajlarla gönderilir.

Bu, sadece snapshot beklemek yerine rakibin daha canlı görünmesini sağlar.

## 7. Çöp Satır Sistemi

Online PvP'de çöp satırı mantığı kaldırılmıştır.

Bu yüzden:

- satır temizlemek rakibe garbage göndermez
- rakipten gelen garbage saldırısı uygulanmaz
- kenardaki kırmızı garbage göstergesi görünmez

Maç akışı artık daha düz bir 1v1 yarış mantığına yakındır: kim daha uzun dayanır ve daha temiz oynarsa o kazanır.

## 8. Kırmızı Çizgi / Kırmızı Sayaç

Online PvP'de artık bu gösterge kullanılmaz.

## 9. Kazanma / Kaybetme Mantığı

Online PvP artık oyun içi sonuç kararında Local PvP ile aynı kuralı kullanır.

Temel kural:

- sadece bir taraf elendiyse diğer taraf kazanır
- iki taraf da elendiyse skor karşılaştırılır
- skorlar eşitse beraberelik olur

Online tarafında tek fark, rakibin elendiği bilgisi ağdan birkaç frame geç gelebileceği için bu kararın mesaj gelince netleşmesidir.

### 9.1 Normal yenilgi

Oyuncu yeni parçayı geçerli pozisyonda spawn edemezse kaybeder.

Bu klasik top-out mantığıdır.

### 9.2 Garbage kaynaklı yenilgi yok

Bu senaryo artık Online PvP için geçerli değildir, çünkü garbage sistemi kapalıdır.

### 9.3 Rakip ayrılırsa

Rakip maç sırasında lobiden düşerse veya ayrılırsa yerel oyuncu kazanan ilan edilir.

### 9.4 Eş zamanlı ölüm

İki taraf da elendiyse sistem Local PvP'deki gibi skor karşılaştırmasına gider.

Sonuç:

- skorun yüksekse sen kazanırsın
- rakibin skoru yüksekse rakip kazanır
- skorlar eşitse beraberelik olur

Bu, Online tarafta Local PvP sonucunu korumak için kullanılan tie-break yaklaşımıdır.

## 10. Görsel ve Efekt Katmanı

Online PvP artık sadece düz grid göstermez. Maç içinde şunlar da çalışır:

- rakip aktif parça gösterimi
- satır temizleme flash efekti
- line sweep
- wave efektleri
- particle efektleri
- block fall animasyonu
- modern board skin ve textured block çizimi

Bu yüzden Online PvP, Local PvP'ye daha yakın bir görsel akışla ilerler.

## 11. Kontrol Zamanlaması

Online PvP, diğer modlardan bağımsız sabit giriş zamanlamaları kullanır.

Mevcut sabitler:

- DAS delay: 160 ms
- DAS repeat: 105 ms
- soft drop speed: 55 ms

Bu değerler ayar ekranındaki genel gameplay slider'larından bağımsızdır.

## 12. Bilinmesi Gereken Tasarım Sınırları

Mevcut sistemin doğasından gelen bazı önemli noktalar vardır:

- board snapshot tabanlı gösterim tam deterministik eşzamanlı simülasyon değildir
- rakip tahta görünümü ağ gecikmesine göre biraz geriden gelebilir
- simultane ölüm çözümü skor tabanlıdır

Bu seçimler tam rekabetçi lockstep bir model yerine daha pratik ve kararlı bir uygulama hedeflediğini gösterir.

## 13. Kısa Özet

Online PvP mantığı tek cümlede şöyledir:

İki oyuncu aynı parça sırasıyla oynar, kendi tahtasını yerel olarak yönetir, rakibin durumunu ağdan alır ve spawn edemeyen taraf maçı kaybeder.

## 14. Geliştirme Notu

Bu belge davranışı anlatır; mevcut davranışın her kısmının ideal olduğu anlamına gelmez.

Özellikle şu alanlar gelecekte revize edilmeye adaydır:

- simultane ölüm tie-break kuralının yeniden tasarlanması
- top-out kontrolünün daha açık ve daha savunulabilir hale getirilmesi