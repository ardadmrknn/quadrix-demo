# Online PvP Akış ve Davranış Rehberi

Bu belge, Online PvP modunun **oyuncu açısından** ve **çalışma akışı bakımından** nasıl davrandığını anlatır. Mimari, kod katmanları, derleme ve dağıtım için kanonik kaynak: [ONLINE_PVP_ARCHITECTURE.md](ONLINE_PVP_ARCHITECTURE.md). Bu iki belge birbirini tekrar etmez.

> **Bu dosya nedir?** Davranışsal akış: lobi → countdown → maç → sonuç, mesaj türleri, garbage politikası, kazanma/kaybetme kuralı.
> **Bu dosya ne değil?** Mimari katmanlar, derleme talimatları, thread güvenliği detayları (orası architecture belgesinde).

Ana referans dosyalar:

- `src/online_pvp_game.py` — durum makinesi, çizim, mesaj işleme
- `src/steam_networking.py` — Python wrapper, JSON serialize/deserialize
- `src/board.py` — tahta ve satır temizleme mantığı

## 1. Genel Amaç

Online PvP, Steam P2P (ISteamNetworkingMessages) üzerinden iki oyuncunun aynı anda 1v1 Tetris maçı yapmasını sağlar.

Sistemin temel hedefleri:

- iki oyuncunun aynı parça sırasını alması (deterministik 7-bag)
- her oyuncunun kendi tahtasını yerel gibi oynaması
- rakibin tahtasını ve aktif parçasını ağ üzerinden görmesi
- biri elenince maçın bitmesi

Hiçbir özel sunucu (dedicated server) yoktur; iletişim Steam relay üzerinden P2P yapılır.

## 2. Durum Makinesi

Online PvP, `OnlineState` durum makinesi ile çalışır:

```
LOBBY_MENU ──► WAITING ──► READY_CHECK ──► COUNTDOWN ──► PLAYING
                                                          │   │
                                                          ▼   ▼
                                                   GAME_OVER  DISCONNECTED
```

| Durum | Anlamı |
| --- | --- |
| `LOBBY_MENU` | Oyuncu lobi oluşturur, koda göre katılır veya lobi listesine bakar |
| `WAITING` | Lobi kurulmuştur, rakip beklenir |
| `READY_CHECK` | İki oyuncu da lobidedir; hazır durumu beklenir |
| `COUNTDOWN` | Host oyunu başlatır, 3-2-1 geri sayım oynar |
| `PLAYING` | Gerçek maç bu aşamada çalışır |
| `GAME_OVER` | Maç sonucu belli olmuştur |
| `DISCONNECTED` | Rakip bağlantıdan düşmüştür veya çıkmıştır |

## 3. Lobi ve Maç Başlatma

### 3.1 Lobi oluşturma / katılma

Oyuncular farklı yollarla aynı lobide buluşabilir:

- Steam daveti (Steam overlay üzerinden)
- 6 haneli **lobi kodu** (host'un metadata'sından üretilir)
- tam **lobby ID**
- public lobi listesi (`request_lobby_list()` ile filtreli)

Lobi kurulduktan sonra iki tarafta da `SteamNetworking` aktif olur ve event/message kuyruğu işlenmeye başlanır.

### 3.2 Hazır kontrolü

Her iki oyuncu da hazır olduğunda host tarafı oyunu başlatır.

Host şu kritik bilgileri yollar:

- `seed` (deterministik parça sırası için)
- önceden üretilmiş parça dizisinin ilk bölümü (max 500 parça)

Böylece iki taraf da aynı sırayla aynı parçaları alır.

### 3.3 Countdown

`COUNTDOWN` sırasında oyun fiziği henüz akmaz. Sayaç bitince `_start_game()` çağrılır ve gerçek maç başlar.

## 4. Maç İçindeki Ana Döngü

`PLAYING` durumunda her frame şu sırayla çalışır:

1. Ağ olayları ve mesajları işlenir (`net.tick()` → `run_callbacks()` + `poll_events()` + `poll_messages()`)
2. Oyuncu input'u alınır
3. Aktif parça düşürülür
4. Lock gecikmesi kontrol edilir
5. Gerekirse parça kilitlenir, satır temizlenir
6. Periyodik olarak rakibe board snapshot gönderilir (~500ms)
7. Rakibin aktif parçası ve skoru güncellenir

Bu sayede oyuncu kendi tarafında yerel hissiyle oynarken rakip tarafı ağdan gelen verilerle canlı tutulur.

## 5. Parça Akışı

Her oyuncuda bir aktif parça ve bir sonraki parça vardır. Akış:

1. Aktif parça spawn olur
2. Oyuncu sağa/sola hareket ettirir, döndürür, soft drop veya hard drop yapar
3. Parça aşağı daha fazla inemiyorsa lock timer çalışır
4. Lock süresi dolarsa parça tahtaya yazılır
5. Satır temizleme hesaplanır
6. Yeni parça alınır

> Online PvP için en kritik tasarım kararı: iki tarafın **parça sırası aynıdır**. Bu adalet için zorunludur.

## 6. Ağ Üzerinden Senkronlanan Veriler

Online PvP tam bir lockstep simülasyon değildir. Bunun yerine hibrit bir model kullanır.

### 6.1 Mesaj türleri (ana hatlarıyla)

| Mesaj | Yön | Güvenilirlik | Açıklama |
| --- | --- | --- | --- |
| `ready` | ↔ | Reliable | Oyuncu hazır sinyali |
| `game_start` | Host → Guest | Reliable | `{seed, timestamp, pieces[0:500]}` |
| `garbage` | ↔ | Reliable | `{lines, gap}` (Online PvP'de devre dışı, aşağıda bkz.) |
| `board_state` | ↔ | Unreliable | `{grid, score, lines, level}` — periyodik snapshot |
| `score_update` | ↔ | Unreliable | `{score, lines, level}` |
| `active_piece` | ↔ | Unreliable | Rakibin aktif parça pozisyonu (düşük gecikme) |
| `game_over` / `eliminated` | ↔ | Reliable | Oyuncu elendi bildirimi |
| `pause_request` / `resume` | ↔ | Reliable | Duraklama/devam sinyali |
| `rematch` | ↔ | Reliable | Tekrar oyna isteği |

Tüm mesajlar JSON formatında, `CHANNEL_GAME (0)` üzerinden gönderilir.

### 6.2 Board snapshot

Rakibin tahtası belirli aralıklarla gönderilir. Snapshot içinde tipik olarak:

- grid (BOARD_HEIGHT × BOARD_WIDTH)
- score
- lines
- level
- bazı efekt yardımcı alanları

bulunur. Bu sayede sağ tarafta rakibin güncel tahtası çizilir.

### 6.3 Aktif parça pozisyonu

Rakibin o anda oynadığı aktif parça ayrı, düşük gecikmeli mesajlarla gönderilir. Bu, sadece snapshot beklemek yerine rakibin daha canlı görünmesini sağlar.

### 6.4 Mesaj doğrulama (güvenlik)

- **Gönderici doğrulaması:** Yalnızca `opponent_steam_id` eşleşen mesajlar işlenir.
- **Alan clamping:** lines [0,20], score [0,999999], level [0,30], gap [0,BOARD_WIDTH-1].
- **Grid doğrulama:** BOARD_HEIGHT × BOARD_WIDTH boyut kontrolü.
- **Piece sequence limiti:** GAME_START `pieces` max 500 eleman.
- **C++ session filtering:** `OnSessionRequest` yalnızca lobby üyelerinden veya 30 saniyelik allowlist penceresindeki oyunculardan kabul eder.

## 7. Çöp Satır (Garbage) Politikası

Online PvP'de çöp satırı mantığı **devre dışıdır**.

Bu yüzden:

- satır temizlemek rakibe garbage göndermez
- rakipten gelen garbage saldırısı uygulanmaz
- kenardaki kırmızı garbage göstergesi görünmez

Maç akışı düz bir 1v1 yarış mantığına yakındır: kim daha uzun dayanır ve daha temiz oynarsa kazanır.

> Local PvP'de garbage hâlâ aktiftir; bu kapatma yalnızca Online PvP içindir.

## 8. Kırmızı Çizgi / Kırmızı Sayaç

Online PvP'de bu gösterge artık kullanılmaz.

## 9. Kazanma / Kaybetme Mantığı

Online PvP, oyun içi sonuç kararında Local PvP ile aynı kuralı kullanır.

Temel kural:

- Sadece bir taraf elendiyse diğer taraf kazanır.
- İki taraf da elendiyse skor karşılaştırılır.
- Skorlar eşitse beraberlik olur.

Online tarafında tek fark, rakibin elendiği bilgisinin ağdan birkaç frame geç gelebileceği için bu kararın mesaj geldiğinde netleşmesidir.

### 9.1 Normal yenilgi (top-out)

Oyuncu yeni parçayı geçerli pozisyonda spawn edemezse kaybeder. Klasik top-out mantığı.

### 9.2 Garbage kaynaklı yenilgi yok

Garbage devre dışı olduğu için bu senaryo Online PvP'de geçerli değildir.

### 9.3 Rakip ayrılırsa

Rakip maç sırasında lobiden düşerse veya ayrılırsa yerel oyuncu kazanan ilan edilir.

### 9.4 Eş zamanlı ölüm

İki taraf da elendiyse sistem skor karşılaştırmasına gider:

- Skorun yüksekse sen kazanırsın.
- Rakibin skoru yüksekse rakip kazanır.
- Skorlar eşitse beraberlik olur.

Bu, Online tarafta Local PvP sonucunu korumak için kullanılan tie-break yaklaşımıdır.

## 10. Görsel ve Efekt Katmanı

Online PvP düz grid değildir; maç içinde şunlar çalışır:

- rakip aktif parça gösterimi
- satır temizleme flash efekti
- line sweep
- wave efektleri
- particle efektleri
- block fall animasyonu
- modern board skin ve textured block çizimi

Bu sayede Online PvP, Local PvP'ye yakın bir görsel akışla ilerler.

## 11. Kontrol Zamanlaması

Online PvP, diğer modlardan bağımsız sabit giriş zamanlamaları kullanır:

- DAS delay: 160 ms
- DAS repeat: 105 ms
- Soft drop speed: 55 ms

Bu değerler ayar ekranındaki genel gameplay slider'larından bağımsızdır.

## 12. Bilinmesi Gereken Tasarım Sınırları

- Board snapshot tabanlı gösterim **tam deterministik eşzamanlı simülasyon değildir**.
- Rakip tahta görünümü ağ gecikmesine göre biraz geriden gelebilir.
- Simultane ölüm çözümü skor tabanlıdır.
- Tüm mesajlar **tek kanal (kanal 0)** üzerinden gider.

Bu seçimler, tam rekabetçi lockstep yerine pratik ve kararlı bir uygulama hedeflendiğini gösterir.

## 13. Kısa Özet

Online PvP mantığı tek cümlede şöyledir:

> İki oyuncu aynı parça sırasıyla oynar, kendi tahtasını yerel olarak yönetir, rakibin durumunu ağdan alır ve spawn edemeyen taraf maçı kaybeder.

## 14. İlgili Dokümanlar

- Mimari rehberi (kod katmanları, derleme, thread güvenliği): [ONLINE_PVP_ARCHITECTURE.md](ONLINE_PVP_ARCHITECTURE.md)
- Steam köprüsü EXE/.app entegrasyonu (generated): [EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md)
- Steam köprüsü derleme rehberi: [../steamworks/steam_net_bridge/README_BUILD.md](../steamworks/steam_net_bridge/README_BUILD.md)

## 15. Geliştirme Notu

Bu belge davranışı anlatır; mevcut davranışın her kısmının ideal olduğu anlamına gelmez.

Özellikle şu alanlar gelecekte revize edilmeye adaydır:

- Simultane ölüm tie-break kuralının yeniden tasarlanması
- Top-out kontrolünün daha açık ve daha savunulabilir hale getirilmesi
- Çoklu kanal mesajlaşma (şu an tüm mesajlar kanal 0 üzerinden)
