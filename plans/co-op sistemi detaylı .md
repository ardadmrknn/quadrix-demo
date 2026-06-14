# QUADRIX Co-op Modu — V1 Tasarım Belgesi

**Versiyon:** 1.1  
**Tarih:** 09.04.2026  
**Statü:** V1 Scope Sabitlendi  
**Format:** Markdown

---

## 📑 İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [V1 Kapsamı](#v1-kapsamı)
3. [Temel Mekanikler](#temel-mekanikler)
4. [UI/UX Tasarımı](#uiux-tasarımı)
5. [Teknik Mimari](#teknik-mimari)
6. [Geliştirilecek Dosyalar](#geliştirilecek-dosyalar)
7. [Geliştirme Sırası](#geliştirme-sırası)
8. [Sonraki Fazlar](#sonraki-fazlar)

---

## 🎮 Genel Bakış

### Konsept

QUADRIX Co-op Modu, iki oyuncuyu **20 sütunlu ortak bir oyun alanına** yerleştiren yerel bir kooperatif modudur. Sol tarafın 10 sütunu Oyuncu 1'e, sağ tarafın 10 sütunu Oyuncu 2'ye aittir. Satırlar yalnızca tüm 20 hücre dolduğunda temizlenir. Bu yapı oyunu yarış değil, koordinasyon oyunu haline getirir.

### V1 Hedefi

Bu belge artık ilk oynanabilir sürüme odaklıdır. İlk sürümün hedefi:

- Aynı cihazda iki oyunculu, sorunsuz çalışan **local endless co-op**
- Tek ortak 20x20 tahta
- İki aktif parça, bağımsız parça akışları
- Oyuncu bazlı hold slotları ile esnek parça saklama
- Spawn bazlı freeze sistemi

### Hedef Kitle

- Aynı cihazda birlikte oynamak isteyen iki oyuncu
- Koordinasyon ve iletişim odaklı puzzle deneyimi arayanlar
- Gelecekte online co-op'a genişleyebilecek bir temel bekleyen oyuncular

### Oyun Süresi

- **Local Endless V1:** 5-30 dakika

---

## ✅ V1 Kapsamı

### V1 İçinde Olanlar

- Local endless co-op
- P1: WASD, P2: yön tuşları
- Tek ortak board
- Ortak team score
- Katkı yüzdesi göstergesi
- Oyuncu bazlı iki hold slotu
- Freeze ve unfreeze akışı

### V1 Dışında Olanlar

- Online co-op
- Campaign objective entegrasyonu
- Ayrı co-op achievement seti
- Ayrı co-op settings ekranı
- Gelişmiş netcode / Steam lobby akışı

### Sabitlenen Tasarım Kararları

| Konu | Karar |
|------|-------|
| İlk sürüm | Sadece local endless co-op |
| Teknik başlangıç | PvP akışını temel alan coop fork yaklaşımı |
| Freeze tetikleme | Yeni parça spawn edilemezse freeze |
| Çift freeze | Anında game over |
| Unfreeze | Alan açıldıktan sonra bir sonraki düşüş tickinde |
| Hold | Oyuncu bazlı ayrı slotlar, her oyuncu kendi hold'unu kullanır |
| Kontroller | P1 WASD, P2 yön tuşları |
| Skor | Team score + katkı yüzdesi |
| Online | Daha sonraki faz |
| Campaign | Daha sonraki faz |

---

## 🕹️ Temel Mekanikler

### 1. Oyun Alanı

```
┌─────────────────────────────────────────┐
│   P1 (10 sütun)   │   P2 (10 sütun)    │
│                   │                     │
│  [████████░░]     │  [░░████████]       │
│  [██████░░░░]     │  [██░░░░░░░░]       │
│  [██████████]     │  [██████████]       │ ← 20/20 dolu!
└─────────────────────────────────────────┘
```

- **Toplam board:** 20 sütun × 20 satır
- **P1 bölgesi:** sütun 0-9
- **P2 bölgesi:** sütun 10-19
- **Orta çizgi:** ince, sürekli görünen sert ayraç
- Parçalar hiçbir koşulda karşı tarafa geçemez

### 2. Satır Temizleme Mantığı

Bir satır yalnızca tüm 20 hücre doluysa temizlenir:

```
Satır Durumu                  Sonuç
─────────────────────────────────────────
│██████████│░░░░░░░░░░│   → Temizlenmez
│██████████│██████████│   → ✅ TEMİZLENİR
│░░░░░░░░░░│██████████│   → Temizlenmez
```

### 3. Parça Dağılımı

P1 ve P2 tamamen bağımsız parça akışları alır:

```
Sıra    P1 Parçası    P2 Parçası
────────────────────────────────
1       I             Z
2       O             T
3       L             S
...     ...           ...
```

Bu sayede iki oyuncu aynı problemi farklı şekillerde çözer ve co-op hissi doğal kalır.

### 4. Dondurma Sistemi

Freeze, oyuncunun yeni parçası kendi alanında **spawn edilemediği anda** devreye girer.

**Davranış:**

- O oyuncuya yeni aktif parça verilmez
- Input geçici olarak kapanır
- Ekranda bekleme overlay'i görünür
- Diğer oyuncu oyuna devam eder

**Unfreeze:**

- Satır temizliği sonrası ilgili oyuncunun alanında spawn boşluğu oluşursa
- Oyuncu hemen değil, **bir sonraki düşüş tickinde** yeniden oyuna döner

**Çift freeze:**

- İki oyuncu da aynı anda spawn edemez duruma düşerse oyun biter

```
T=0s    : P2 parçasını kilitledi
T=0.1s  : Yeni P2 parçası spawn testinden geçemedi → P2 frozen
T=4s    : P1 ortak satırı tamamladı ve temizledi
T=4.1s  : P2 alanında yeniden boşluk oluştu
T=4.8s  : Bir sonraki düşüş tickinde P2 için spawn tekrar denendi → oyun devam
```

### 5. Parça Sınırı

Parçalar orta çizgide sert duvara çarpar:

```
Parça: L-Tetromino (P1'de)
├─ Sağa kayarken P2 alanına taşmaya çalışırsa
└─ Hareket veya rotasyon geçersiz sayılır
```

Bu kural rotasyon sırasında da geçerlidir.

### 6. Hız Sistemi

V1'de hız **ortak global hız** olarak çalışır. İki oyuncu farklı akışta parça oynasa da düşüş temposu tek değerdir.

- Seviye artışı takımın toplam temizlediği satırlara bağlıdır
- İki oyuncudan biri daha rahat oynasa bile diğerine ayrı hız uygulanmaz
- Amaç rekabet değil, ortak ritimdir

### 7. Skor Sistemi

V1 HUD'da ana skor kaynağı **team score** olacaktır.

- Team score, co-op board'un tek resmi skoru olarak tutulur
- Katkı yüzdesi, temizlenen satır anlarındaki katkıdan türetilen yardımcı bir göstergedir
- V1'de katkı yüzdesi yalnızca görsel geri bildirimdir; asıl ilerleme metriği team score'dur

**Katkı yüzdesi kuralı:**

- Her clear anında katkı iki taraf arasında paylaştırılır
- V1'de bu gösterim yaklaşık bir HUD metriğidir
- Sert 10+10 alan bölünmesi nedeniyle bu oran çoğu senaryoda 50/50'ye yakın görünür
- Gerçek parça sahipliği takibi V1 dışında bırakılmıştır

### 8. Oyuncu Bazlı Hold Sistemi

V1 implementasyonunda hold sistemi **oyuncu bazlı iki ayrı slot** olarak çalışacaktır.

**Kural:**

- P1 yalnızca kendi hold slotunu kullanır
- P2 yalnızca kendi hold slotunu kullanır
- Her oyuncu kendi aktif parçasını kendi hold alanında saklar
- Hold akışı, iki oyuncunun input ve panel düzenini sade tutacak şekilde ayrılmıştır

**Davranış:**

- Amaç, aynı ortak board üzerinde oynarken her oyuncunun kendi kurtarma aracını korumasıdır
- Koordinasyon, ortak board temizliği ve katkı ritminden gelir; hold aktarımından değil

**Denge kuralı:**

- Her oyuncu, elindeki aktif parça için bir kez hold kullanabilir
- Aynı aktif parça sonsuz hold zincirine sokulamaz
- Diğer oyuncu kendi hold slotunu bağımsız olarak kullanabilir

---

## 🎨 UI/UX Tasarımı

### 1. Ana Oyun Ekranı

```
┌────────────────────────────────────────────────────┐
│  QUADRIX CO-OP   LEVEL 3   TIME 04:12              │
├────────────────────────────────────────────────────┤
│                 TEAM SCORE: 4,800                  │
│             P1 Katkı %50   P2 Katkı %50            │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │              20 SÜTUN ORTAK BOARD           │  │
│  │      P1 ALANI        │       P2 ALANI       │  │
│  │                      │   (WAITING FOR P1)   │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  P1 Hold:[T]  Next P1:[I]  Next P2:[Z]  P2 Hold:[L]│
└────────────────────────────────────────────────────┘
```

### 2. Freeze Overlay

```
┌────────────────────────────────────────────────────┐
│  P2 WAITING FOR SPACE                              │
├────────────────────────────────────────────────────┤
│  P2 yeni parçasını spawn edemiyor                  │
│                                                    │
│  P1 ortak satırı tamamlayıp alan açmalı            │
│                                                    │
│  Satır temizlenirse P2 bir sonraki tickte döner    │
└────────────────────────────────────────────────────┘
```

### 3. Satır Temizleme Animasyonu

- Orta çizgiye doğru veya orta çizgiden dışarı açılan takım vurgusu
- Tek oyuncu başarısı gibi değil, ortak clear hissi veren efekt
- Sesler mevcut clear seslerinden başlayabilir; V1'de yeni ses paketi şart değil

### 4. Hold Göstergesi

Hold kutuları oyuncuların kendi next panelleriyle eşleşecek şekilde yan panellerde konumlanmalıdır.

- Sol tarafta P1 next + P1 hold
- Sağ tarafta P2 next + P2 hold
- Her hold kutusu kendi oyuncusunun tuş bağını göstermelidir

### 5. Minimal Görsel Ayırım

- Orta çizgi sürekli görünür
- P1 ve P2 renk tonlarıyla ayrılmaz
- Aynı tema ve aynı blok paleti korunur
- Co-op hissi görsel kutuplaşmayla değil, mekanikle oluşturulur

---

## 🏗️ Teknik Mimari

### Mimari Yaklaşım

V1, sıfırdan bağımsız bir sistem yerine **PvP akışını temel alan coop fork yaklaşımı** ile geliştirilecektir.

Bu şu anlama gelir:

- PvP'deki pencere, pause, input ritmi ve genel oyun akışı referans alınır
- Ancak iki ayrı board modeli bırakılır
- Yerine tek ortak 20 sütunlu board kullanılır
- Rekabet mantıkları çıkarılır, koordinasyon mantıkları eklenir

**Önemli karar:**

- Amaç doğrudan PvPGame'i aynen kullanmak değildir
- Amaç PvP'deki hazır iki oyunculu akıştan faydalanıp co-op'a uygun tek-board yapıya dönüştürmektir
- Bu nedenle başlangıç implementasyonu pratikte bir fork/kopyala-budala yaklaşımı olabilir

### Yüksek Seviye Diyagram

```
┌─────────────────────────────────────────────────┐
│              coop_game.py  (CoopGame)           │
│  PvP akışından türetilmiş yerel co-op döngüsü   │
│  tek ortak board, çift aktif parça, ayrı hold slotları │
└────────┬───────────────────────────────┬────────┘
         │                               │
    ┌────▼─────────┐               ┌─────▼──────────┐
    │ coop_board.py│               │ main/menu akışı│
    │ width = 20   │               │ coop_mode route│
    └──────────────┘               └────────────────┘
         │
         ├──► board.py          (genişlik parametreli temel board)
         ├──► pvp_game.py       (referans alınan iki oyunculu akış)
         ├──► game.py           (genel draw/spawn/board ölçek mantığı)
         ├──► pieces.py         (parça üretimi)
         ├──► localization.py   (yeni HUD ve durum metinleri)
         └──► main.py           (placeholder coop action yerine gerçek launch)
```

### Temel State Yapısı

```python
class CoopGame:
    def __init__(self, ...):
        self.board = CoopBoard()

        self.p1_current_piece = ...
        self.p1_next_piece = ...
        self.p2_current_piece = ...
        self.p2_next_piece = ...

      self.p1_hold_piece = None
      self.p2_hold_piece = None
        self.p1_hold_used = False
        self.p2_hold_used = False

        self.p1_frozen = False
        self.p2_frozen = False

        self.team_score = 0
        self.p1_contribution_pct = 50
        self.p2_contribution_pct = 50
```

### Kritik Metotlar

- `_spawn_piece(player)`
- `_try_spawn_for_player(player)`
- `_lock_piece(player)`
- `_update_freeze_state_after_lock(player)`
- `_try_unfreeze_players()`
- `_use_shared_hold(player)`
- `update(dt_ms)`
- `handle_input()`
- `draw()`

### V1 İçin Uygulama Notları

- Mevcut geniş board desteği yeniden kullanılmalıdır
- Çekirdek draw mantığı ilk aşamada coop_game içinde kalabilir
- Ayrı coop_renderer dosyası V1 için zorunlu değildir
- Mevcut PvP tuş düzeni doğrudan başlangıç varsayılanı olarak kullanılabilir

---

## 📁 Geliştirilecek Dosyalar

## V1 Yeni Dosyalar

| Dosya | Amaç |
|---|---|
| `src/coop_board.py` | 20 sütunlu ortak tahta ve orta çizgi sınır kontrolü |
| `src/coop_game.py` | Yerel co-op ana oyun sınıfı |

## V1 Modifiye Edilecek Dosyalar

| Dosya | Değişiklik |
|---|---|
| `src/main.py` | `coop_mode` placeholder yerine gerçek oyun akışı başlatılır |
| `src/menu.py` | Mevcut co-op kartı placeholder durumundan çıkarılır |
| `src/localization.py` | Co-op HUD, freeze ve hold panel metinleri eklenir |

## V1'de Bilinçli Olarak Dokunulmayacak Alanlar

| Dosya/Alan | Neden |
|---|---|
| `src/steam_networking.py` | Online co-op V1 scope dışında |
| `src/campaign/objectives.py` | Campaign entegrasyonu V1 scope dışında |
| `src/game_modes.py` | V1 co-op ayrı entry akışıyla ilerleyebilir |
| `src/sound.py` | İlk sürüm mevcut seslerle çıkabilir |

---

## 🚀 Geliştirme Sırası

### Faz 1: Core Local Co-op

**Hedef:** Oynanabilir, local endless çekirdek döngü

1. `coop_board.py` oluştur
   - 20 sütunlu board
   - P1 ve P2 sütun sınırları
   - Orta çizgi sert duvar kontrolü

2. `coop_game.py` oluştur
   - PvP akışını temel alan yerel co-op sınıfı
   - Tek ortak board
   - İki aktif parça ve iki next akışı
   - Spawn bazlı freeze sistemi
   - Çift freeze = game over

3. Oyuncu bazlı hold sistemini ekle
   - P1 ve P2 için ayrı hold slotları
   - Her oyuncu için parça başına tek hold kullanım kuralı
   - Hold kutularını oyuncu panelleriyle hizala

**Test:**

- P1 ve P2 aynı anda oynayabilmeli
- Parçalar karşı tarafa taşmamalı
- Tek oyuncu freeze olunca diğeri devam edebilmeli
- İki oyuncu da spawn edemezse oyun bitmeli

### Faz 2: HUD ve Oyun Akışı

**Hedef:** Oyunun okunabilir ve anlaşılır hale gelmesi

4. HUD düzenini kur
   - Team score
   - Katkı yüzdesi
   - P1/P2 hold göstergeleri
   - Freeze overlay

5. Mevcut co-op menü aksiyonunu bağla
   - `coop_mode` artık bilgi mesajı vermek yerine oyunu açmalı

6. Co-op metinlerini ekle
   - freeze bekleme mesajları
   - hold panel etiketleri
   - coop başlık ve kısa açıklamalar

**Test:**

- Menüden co-op açılabilmeli
- HUD'da roller ve durumlar net anlaşılmalı
- Hold kutuları ilk bakışta hangi oyuncuya ait olduğu anlaşılır olmalı

### Faz 3: Input ve Polish

**Hedef:** Rahat oynanan ilk sürüm

7. Varsayılan keyboard düzenini sabitle
   - P1: WASD
   - P2: yön tuşları

8. Freeze ve hold davranışlarını oynanış testinden geçir
   - özellikle anlık handoff hissi
   - yanlışlıkla spam veya sonsuz döngü üretmemesi

9. İlk dengeleme turu
   - hız hissi
   - hold kullanım değeri
   - freeze baskısı

**Test:**

- İki oyuncu aynı klavyede rahat oynayabilmeli
- Hold taktiksel hissettirmeli
- Oyun kaotik ama anlaşılır kalmalı

---

## ⏭️ Sonraki Fazlar

### Faz 4: Campaign Entegrasyonu

Bu faz V1 sonrasına bırakılmıştır.

Planlanan başlıklar:

- Co-op objective türleri
- Co-op level setleri
- Yıldız sistemi ile entegrasyon

### Faz 5: Online Co-op

Bu faz V1 sonrasına bırakılmıştır.

Planlanan başlıklar:

- Steam lobby / invite akışı
- Shared board authority modeli
- Senkronizasyon stratejisi
- Gecikme toleransı ve disconnect kuralları

### Faz 6: Ses ve Özel Efektler

- Co-op'a özel clear vurguları
- Freeze sesleri
- Hold geri bildirimi

---

## 📊 V1 Tasarım Kararları Özeti

| Soru | Karar |
|------|-------|
| İlk sürüm nedir? | Local endless co-op |
| Mimari başlangıç nedir? | PvP tabanlı coop fork |
| Kaybetme koşulu nedir? | İki oyuncu da spawn edemezse game over |
| Tek freeze olursa ne olur? | Oyuncu donar, diğeri devam eder |
| Unfreeze ne zaman olur? | Alan açıldıktan sonraki düşüş tickinde |
| Hold sistemi nedir? | Oyuncu bazlı ayrı slotlar, parça başına tek kullanım |
| Kontrol düzeni nedir? | P1 WASD, P2 yön tuşları |
| Skor nasıl gösterilir? | Team score + katkı yüzdesi |
| Online var mı? | V1'de yok |
| Campaign var mı? | V1'de yok |

---

## 🎯 Başarı Kriterleri

V1 co-op modu aşağıdaki durumlarda başarılı kabul edilir:

- ✅ İki oyuncu menüden co-op modunu açıp aynı cihazda oynayabiliyor
- ✅ 20 sütunlu ortak board sorunsuz çalışıyor
- ✅ Orta çizgi sert sınır gibi davranıyor
- ✅ Freeze sistemi spawn bazlı ve anlaşılır çalışıyor
- ✅ Tek oyuncu freeze olduğunda diğer oyuncu akışı sürdürebiliyor
- ✅ Çift freeze senaryosu temiz şekilde game over'a gidiyor
- ✅ Hold sistemi iki oyuncu için de okunaklı ve taktiksel hissettiriyor
- ✅ HUD ilk bakışta okunuyor

---

## 📝 Notlar

- Mevcut geniş tahta desteği ve iki oyunculu PvP akışı V1 için önemli referans noktalarıdır.
- Katkı yüzdesi V1'de yardımcı HUD verisidir; kesin istatistik sistemi değildir.
- Hold sistemi, iki oyunculu akışın temel ergonomi parçası olduğu için V1'de özellikle test edilmelidir.
- Online ve campaign fazları ayrı tasarım kararları gerektirdiğinden bilinçli olarak ertelenmiştir.

---

## 10.04.2026 Güncel Durum Eki

Bu belgenin üst bölümleri ilk V1 kapsamını ve o sıradaki tasarım kararlarını tarihsel kayıt olarak korur. Repo daha sonra bu ilk kapsamın ötesine geçtiği için aşağıdaki ek bölüm, eski metni silmeden güncel implementasyon durumunu özetler.

### İlk V1 Tasarımından Sonra Gerçekte Uygulanan Alanlar

- Local endless co-op teslim edildi ve menüden erişilebilir hale geldi.
- Co-op campaign, ilk planda sonraki faz olarak görünse de daha sonra ayrı bir katman olarak uygulandı.
- Oyuncu bazlı iki hold slotu, freeze/unfreeze akışı, ortak skor ve katkı yüzdeleri gerçek runtime davranışı olarak yerleşti.
- Genişletilmiş game over ekranı, restart akışı ve göz/peek davranışı eklendi.
- Co-op için mod bazlı müzik playlist seçimi ve ortak game over müzik kesme akışı bağlandı.

### Sonradan Netleşen Davranış ve Mimari Notlar

- Hold sistemi artık tarihsel bir öneri değil, resmi runtime davranışı olarak oyuncu bazlı ayrı slot modeline oturmuştur.
- Co-op görsel dili PvP tint'inden ayrılmış, classic temele daha yakın hale getirilmiştir.
- Satır temizleme Luna sweep'i ana oyundaki zaman/mesafe temelli hesap yaklaşımına hizalanmıştır.
- Particle effects ayarı artık tek bir açık/kapalı anahtar değil; `off`, `low`, `medium`, `high` seviye modeliyle çalışır.
- Screen shake, particle toggle'dan bağımsız genel efekt katmanı olarak ele alınır.

### Doğrulama ve Audit Notu

- Co-op ve ilişkili modlar için birden fazla audit turu yapıldı.
- Son geniş doğrulama koşusunda test seti `748 passed, 7 skipped` sonucuna ulaştı.
- Ayrıntılı oturum kaydı için `reports/2026-04-10-coop-chat-oturumu-detayli-dokum.md` dosyasındaki ek bölümler birlikte okunmalıdır.

---

**Belge Sonu**