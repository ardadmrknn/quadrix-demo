# Online Co-op Modu — Detaylı Analiz ve Mimari Tasarım

> **Tarih:** 13 Nisan 2026  
> **Kapsam:** Mevcut yerel co-op modunun (CoopGame) online'a taşınması için A'dan Z'ye teknik analiz  
> **Hedef:** Steam P2P üzerinden 2 oyunculu kooperatif Tetris

---

## İçindekiler

1. [Mevcut Sistem Haritası](#1-mevcut-sistem-haritası)
2. [Yerel Co-op — Nasıl Çalışıyor?](#2-yerel-co-op--nasıl-çalışıyor)
3. [Online PvP — Mevcut Altyapı](#3-online-pvp--mevcut-altyapı)
4. [Temel Sorun: Co-op vs PvP Farkları](#4-temel-sorun-co-op-vs-pvp-farkları)
5. [Senkronizasyon Modeli Seçenekleri](#5-senkronizasyon-modeli-seçenekleri)
6. [Önerilen Mimari: Hibrit Otoriter Host](#6-önerilen-mimari-hibrit-otoriter-host)
7. [Mesaj Protokolü Tasarımı](#7-mesaj-protokolü-tasarımı)
8. [Board Senkronizasyon Detayları](#8-board-senkronizasyon-detayları)
9. [Parça (Piece) Senkronizasyonu](#9-parça-piece-senkronizasyonu)
10. [Freeze / Unfreeze Senkronizasyonu](#10-freeze--unfreeze-senkronizasyonu)
11. [Kampanya Modu Entegrasyonu](#11-kampanya-modu-entegrasyonu)
12. [Lobi ve Matchmaking](#12-lobi-ve-matchmaking)
13. [Latency ve Hata Toleransı](#13-latency-ve-hata-toleransı)
14. [UI / UX Değişiklikleri](#14-ui--ux-değişiklikleri)
15. [Dosya / Modül Planı](#15-dosya--modül-planı)
16. [Aşamalı Uygulama Planı](#16-aşamalı-uygulama-planı)
17. [Riskler ve Açık Sorular](#17-riskler-ve-açık-sorular)
18. [Mevcut Kodda Yeniden Kullanılabilecek Yapılar](#18-mevcut-kodda-yeniden-kullanılabilecek-yapılar-detaylı-satır-referansları)

---

## 1. Mevcut Sistem Haritası

### Yerel Co-op Dosyaları
| Dosya | Satır | Sorumluluk |
|-------|-------|------------|
| `src/coop_game.py` | 3129 | Ana co-op oyun döngüsü, 2 oyuncu input, çizim, HUD, pause menü |
| `src/coop_board.py` | 122 | 20×20 paylaşımlı board, midline duvarı, owner tracking |
| `src/campaign/coop_campaign_mode.py` | 621 | CoopGame ← kampanya hedef/yıldız katmanı |
| `src/campaign/coop_level_select.py` | 329 | 2 dünya, 20 level seçim ekranı |
| `src/campaign/coop_level_data.py` | 304 | 20 level konfigürasyonu |
| `src/campaign/coop_objectives.py` | 189 | Co-op'a özel hedefler (balanced, freeze recovery, vb.) |

### Online PvP Dosyaları (Yeniden Kullanılacak)
| Dosya | Satır | Sorumluluk |
|-------|-------|------------|
| `src/online_pvp_game.py` | 5987 | PvP oyun mantığı, durum makinesi, lobi UI, çizim |
| `src/steam_networking.py` | 861 | Python networking wrapper, JSON mesajlaşma, MsgType sabitleri |
| `steamworks/steam_net_bridge/steam_net_bridge.cpp` | ~502 | C++ Pybind11 bridge, Steam SDK çağrıları |
| `src/steam_integration.py` | — | Pump thread, pause/resume mekanizması |

### İlişkili Temel Dosyalar
| Dosya | Satır | Sorumluluk |
|-------|-------|------------|
| `src/board.py` | 399 | Temel Board sınıfı (`BOARD_WIDTH=10`, `BOARD_HEIGHT=20`) |
| `src/pieces.py` | 254 | Parça tanımları, SHAPES, `HIDDEN_SPAWN_ROWS=2` |
| `src/constants.py` | — | `DAS_DELAY=200`, `DAS_REPEAT=200`, `DEFAULT_LOCK_DELAY=500` |
| `src/main.py` | — | `_handle_online_pvp()` (satır 2942+), state machine entegrasyonu |

---

## 2. Yerel Co-op — Nasıl Çalışıyor?

### 2.1 Board Yapısı

```
        P1 Alanı (0-9)     │    P2 Alanı (10-19)
     ┌──────────────────────┼──────────────────────┐
  0  │ . . . . . . . . . .  │  . . . . . . . . . . │
  1  │ . . . . . . . . . .  │  . . . . . . . . . . │
     │          ...         │         ...          │
  19 │ ■ ■ . . ■ ■ ■ . . .  │  . . . ■ ■ ■ . . ■ ■ │
     └──────────────────────┼──────────────────────┘
                          MIDLINE (sert duvar, geçilemez)
```

- **Grid:** 20 satır × 20 sütun
- **5 paralel katman:** `grid` (renk), `occupancy` (bool), `owners` ("P1"/"P2"/None), `texture_grid`, `gold`
- **Midline:** Sütun 10 — parçalar karşı tarafa geçemez
- **Gizli spawn alanı:** y < 0 (2 satır), parçalar burada oluşur

### 2.2 Oyuncu Durumları (Her Oyuncu İçin Bağımsız)

**Kesin sabitler** (`src/constants.py`):
- `DAS_DELAY = 200` ms — İlk hareket sonrası bekleme süresi (satır 57)
- `DAS_REPEAT = 200` ms — Tekrar hızı (satır 58)
- `DEFAULT_LOCK_DELAY = 500` ms — Yere değdikten sonra kilitlenme süresi (satır 53)
- `HIDDEN_SPAWN_ROWS = 2` — Görünmez spawn satırları (`src/pieces.py:54`)

**CoopGame sınıf sabitleri** (`src/coop_game.py`):
- `_SOFT_DROP_SPEED = 50` ms — Soft drop tekrar aralığı
- `fall_speed = 900.0` ms — Başlangıç düşme hızı

```python
# Aktif Parçalar
p1_current_piece, p1_next_piece, p1_hold_piece
p2_current_piece, p2_next_piece, p2_hold_piece

# Parça Torbası (Bağımsız RNG)
_p1_bag: list[int]  # 7-piece × 2 = 14 parça per refill
_p2_bag: list[int]  # random.shuffle() ile karıştırılır

# Yerçekimi
p1_fall_time, p2_fall_time  # Birikimci (ms)
fall_speed = 900.0          # Paylaşılan global hız (ms)

# DAS (Auto-Repeat) — DAS_DELAY=200ms, DAS_REPEAT=200ms
p1_das_direction, p1_das_timer, p1_das_charged, p1_das_repeat_timer
p2_das_direction, p2_das_timer, p2_das_charged, p2_das_repeat_timer

# Soft Drop — _SOFT_DROP_SPEED=50ms
p1_soft_drop_active, p1_soft_drop_timer
p2_soft_drop_active, p2_soft_drop_timer

# Lock Delay — DEFAULT_LOCK_DELAY=500ms
p1_grounded, p1_lock_timer
p2_grounded, p2_lock_timer

# Donma
p1_frozen, p2_frozen
_p1_pending_unfreeze, _p2_pending_unfreeze
```

### 2.3 Skor ve Katkı Sistemi

```python
team_score          # Toplam takım skoru
total_lines_cleared # Toplam temizlenen satır
level               # = (total_lines_cleared // 5) + 1       ← coop_game.py
fall_speed          # = max(100.0, 900.0 - (level - 1) * 40.0)  ← coop_game.py

# Katkı takibi (hücre bazında — CoopBoard.last_clear_p1_cells / p2_cells)
p1_total_cells, p2_total_cells        # Temizlenen hücrelerdeki parça sayısı
p1_contribution_pct, p2_contribution_pct  # Yüzde
p1_score_contribution, p2_score_contribution  # Skor bazlı
```

**Not:** `CoopGame` herhangi bir sınıftan **türemez** (standalone class). `CoopCampaignMode(CoopGame)` kampanya katmanıdır.

### 2.4 Olay Sistemi (Event Emitter)

CoopGame şu olayları yayınlar (kampanya modu bunları dinler):

| Olay | Veri |
|------|------|
| `piece_placed` | `{player, piece}` |
| `lines_cleared` | `{lines, total_lines, player, p1_cells, p2_cells}` |
| `score_update` | `{score}` |
| `tetris` | `{player}` |
| `hold_used` | `{player}` |
| `player_frozen` | `{player}` |
| `time_update` | `{elapsed}` |

### 2.5 Input Akışı

```
Oyuncu 1 (WASD):                         Oyuncu 2 (Arrow Keys):
  A / D      → move_left / move_right      ← / → (Arrow)
  W          → rotate                      ↑ (Arrow)
  S          → soft_drop                   ↓ (Arrow)
  LShift     → hard_drop                   Space
  E          → hold                        RShift
  P          → pause (ortak)
     │                                        │
     ▼                                        ▼
handle_input() → pygame KEYDOWN/KEYUP eventleri
     │                                        │
     ▼                                        ▼
_try_move('P1', dx)                     _try_move('P2', dx)
_try_rotate('P1')                       _try_rotate('P2')
_hard_drop('P1')                        _hard_drop('P2')
_use_shared_hold('P1')                  _use_shared_hold('P2')
```

**Kaynak:** `_resolve_controls()` metodu — `coop_game.py`

### 2.6 Lock → Spawn Akışı

`_lock_and_new_piece(player: str)` — `coop_game.py`:
```
1. board.lock_piece_for_player(piece, player)    // Parçayı board'a yaz, owner'ı set et
2. player_locked_out = board.consume_last_lock_out()
3. _emit_event('piece_placed', {...})
4. cleared = satır temizleme sonucu
5. if cleared > 0:
   a. team_score += delta
   b. pX_score_contribution += delta
   c. level = (total_lines_cleared // 5) + 1
   d. fall_speed = max(100.0, 900.0 - (level - 1) * 40.0)
   e. p1_total_cells += board.last_clear_p1_cells
   f. p2_total_cells += board.last_clear_p2_cells
   g. _emit_event('lines_cleared', {lines, total_lines, player, p1_cells, p2_cells})
   h. _try_unfreeze_players()               // Donmuş oyuncu açılabilir mi?
6. hold_used[player] = False
7. if player_locked_out → _freeze_player(player) → return
8. _try_spawn_for_player(player)               // Yeni parça spawn
```

**Game Over tetikleyicisi:** `_freeze_player()` → `_check_double_freeze()` → iki oyuncu da donmuşsa → `_activate_game_over()`

---

## 3. Online PvP — Mevcut Altyapı

### 3.1 Katman Mimarisi

```
┌─────────────────────────────────────────────────────┐
│  OnlinePvPGame (UI + Oyun Mantığı)                  │
├─────────────────────────────────────────────────────┤
│  SteamNetworking (Python Wrapper)                   │
│  - JSON serialize/deserialize                       │
│  - Event queue, message queue                       │
│  - Lazy bridge import                               │
├─────────────────────────────────────────────────────┤
│  SteamNetBridge (C++ Pybind11)                      │
│  - ISteamMatchmaking (lobiler)                      │
│  - ISteamNetworkingMessages (P2P mesajlaşma)        │
│  - ISteamFriends (isim çözümleme)                   │
├─────────────────────────────────────────────────────┤
│  Steam SDK / Steam Relay Network                    │
└─────────────────────────────────────────────────────┘
```

### 3.2 Mevcut Senkronizasyon Modeli (PvP)

- **Model:** Bağımsız simülasyon + periyodik snapshot
- **Parça sırası:** Ortak seed'den deterministik üretim (200 parça) — `_generate_pieces()` (satır 2519)
- **Board durumu:** Her 100ms unreliable `board_state` snapshot — `_send_board_snapshot()` (satır 3220)
- **Parça pozisyonu:** Her hareket sonrası unreliable `piece_pos` — `_send_piece_position()` (satır 3269)
- **Skor:** Unreliable `score_update`
- **Oyun sonu:** Reliable `game_over` / `eliminated`

### 3.3 Durum Makinesi

`OnlineState` sınıfı — `online_pvp_game.py:228-235`:
```python
class OnlineState:
    LOBBY_MENU   = 'lobby_menu'    # Lobi oluştur / katıl ekranı
    WAITING      = 'waiting'       # Lobide rakip bekleniyor
    READY_CHECK  = 'ready_check'   # İki oyuncu da hazır mı?
    COUNTDOWN    = 'countdown'     # 3-2-1 geri sayım
    PLAYING      = 'playing'       # Oyun devam ediyor
    GAME_OVER    = 'game_over'     # Maç bitti
    DISCONNECTED = 'disconnected'  # Bağlantı koptu
```

### 3.4 Mesaj Tipleri (Mevcut)

`MsgType` sınıfı — `steam_networking.py:272-288`:
```python
class MsgType:
    READY           = 'ready'
    GAME_START      = 'game_start'
    GAME_OVER       = 'game_over'
    PAUSE_REQUEST   = 'pause_request'
    RESUME          = 'resume'
    REMATCH         = 'rematch'
    GARBAGE_ATTACK  = 'garbage'
    PIECE_LOCKED    = 'piece_locked'
    BOARD_STATE     = 'board_state'
    SCORE_UPDATE    = 'score_update'
    ELIMINATED      = 'eliminated'
    PIECE_POSITION  = 'piece_pos'
```

### 3.5 Kanal Durumu

`steam_networking.py:232-234` — Platformlar arası uyumluluk nedeniyle **tüm kanallar 0**:
```python
CHANNEL_GAME    = 0  # TÜM mesajlar bu kanal üzerinden gönderilir
CHANNEL_STATE   = 0  # (eski: 1) — artık CHANNEL_GAME ile aynı
CHANNEL_CONTROL = 0  # (eski: 2) — artık CHANNEL_GAME ile aynı
```

### 3.6 Mevcut C++ Bridge Yetenekleri

| Yetenek | Durum | Satır Ref | Co-op İçin |
|---------|-------|-----------|------------|
| Lobi oluştur/katıl (2+ kişi) | ✅ | `steam_networking.py:471, 494` | Doğrudan kullanılabilir |
| P2P mesaj (reliable/unreliable) | ✅ | `steam_networking.py:650` | Doğrudan kullanılabilir |
| Lobi metadata (key-value) | ✅ | `steam_networking.py:731-748` | Mod bilgisi eklenebilir |
| Lobi broadcast (`send_message_to_lobby`) | ✅ | `steam_networking.py:661` | Python'da send() zaten fallback olarak kullanıyor |
| Çoklu kanal | ❌ | `steam_networking.py:232-234` | Hepsi 0; tek kanal kalmalı |
| Session filtering | ✅ | C++ bridge OnSessionRequest | Kullanılabilir |
| `is_host` property | ✅ | `steam_networking.py:385` | Host/guest ayrımı için hazır |

---

## 4. Temel Sorun: Co-op vs PvP Farkları

### 4.1 Paylaşımlı Board Problemi

**PvP'de:** Her oyuncu kendi board'unu simüle eder. Rakibin board'u sadece görsel (snapshot).

**Co-op'ta:** İki oyuncu **AYNI board'u** paylaşıyor. Bir oyuncunun parçası ötekinin tarafında satır temizleyebilir. Bu, her iki tarafın board durumunu birebir aynı tutmasını **zorunlu** kılar.

```
PvP: Oyuncu A board'u ← A kontrol eder      Rakip board'u ← sadece görsel
Co-op: Paylaşımlı board ← HER İKİ oyuncu kontrol eder ← SENKRON OLMALI
```

### 4.2 Çapraz Etkileşim Noktaları

| Etkileşim | Açıklama | Senkronizasyon Gerekliliği |
|-----------|----------|---------------------------|
| **Satır temizleme** | P1'in parçası + P2'nin hücreleri aynı satırda → birlikte temizlenir | Board durumu birebir aynı olmalı |
| **Freeze/Unfreeze** | P2 satır temizlerse P1'in donması açılabilir | Unfreeze kararı iki tarafta aynı olmalı |
| **Skor paylaşımı** | `team_score` her iki parça kilidi sonrası güncellenir | Tutarlı olmalı |
| **Katkı yüzdesi** | `p1_cells` vs `p2_cells` oranı | Owner bilgisi senkron olmalı |
| **Seviye/Hız** | `total_lines_cleared` → `level` → `fall_speed` | Tutarsızlık iki tarafta farklı hıza neden olur |

### 4.3 Neden PvP Modeli Doğrudan Uygulanamaz?

1. **Bağımsız simülasyon imkansız:** PvP'de iki board bağımsız. Co-op'ta tek board için deterministik olmalı.
2. **Snapshot yetmez:** PvP'de rakibin board'u ~100ms gecikmeli gösterilir, sorun değil. Co-op'ta board gecikmesi = parçalar çakışır.
3. **Yapısal farklılık:** PvP → "2 ayrı tahta" (bağımsız). Co-op → "1 ortak tahta" (bağımlı).

---

## 5. Senkronizasyon Modeli Seçenekleri

### Seçenek A: Tam Deterministik (Lockstep)

```
Her frame:
  1. İki oyuncu input'larını gönderir
  2. İkisi de aynı input'ları aynı sırada uygular
  3. Deterministik RNG → aynı parçalar, aynı sonuçlar
```

| Avantaj | Dezavantaj |
|---------|-----------|
| Board her zaman senkron | Input gecikmesi = oyun hızında gecikme |
| Minimum bant genişliği (sadece input) | Python float hassasiyeti → desync riski |
| Hile koruması (her iki taraf doğrular) | Bir oyuncu yavaşlarsa öteki de yavaşlar |
| | Rollback implementasyonu çok karmaşık |

**Uygunluk:** ⚠️ Riskli. Tetris gibi hızlı oyunlarda input gecikmesi kabul edilemez olabilir. Ayrıca Python'da tam determinizm garanti etmek zor (float işlemler, random state).

---

### Seçenek B: Otoriter Host (Authority Model) ⭐ ÖNERİLEN

```
Host (Oyuncu A):
  - Board simülasyonunun TEK sahibi
  - Her iki oyuncunun parça fiziğini hesaplar
  - Satır temizleme, skor, freeze kararları host'ta
  - Sonuçları guest'e gönderir

Guest (Oyuncu B):
  - Input gönderir (move, rotate, drop, hold)
  - Host'tan gelen board durumunu render eder
  - Kendi parçasını _lokal olarak tahmin eder_ (client prediction)
```

| Avantaj | Dezavantaj |
|---------|-----------|
| Board HER ZAMAN tutarlı (tek kaynak) | Guest'in input'unda gecikme hissedilir |
| Basit implementasyon (mevcut CoopGame = host) | Host avantajı (0ms latency) |
| Hile koruması (host otoritesi) | Host çökerse oyun biter |
| Mevcut CoopGame kodu çoğunlukla reuse edilebilir | |

**Uygunluk:** ✅ En uygun. Tetris mekanikleri frame-perfect hız gerektirmez; 50-100ms gecikme kabul edilebilir.

---

### Seçenek C: Bölünmüş Otorite (Split Authority)

```
Oyuncu A: Kendi tarafının (sol 10 sütun) otoritesi
Oyuncu B: Kendi tarafının (sağ 10 sütun) otoritesi
Satır temizleme: İki tarafın mutabakatı gerekir
```

| Avantaj | Dezavantaj |
|---------|-----------|
| İki oyuncu eşit gecikme | Satır temizleme senkronizasyonu çok karmaşık |
| Host avantajı yok | İki otorite → conflict resolution gerekir |
| | Owner tracking cross-border uyumsuzluk riski |

**Uygunluk:** ❌ Aşırı karmaşık. Midline duvarı sayesinde parçalar geçmez ama satır temizleme HER İKİ tarafı kapsıyor.

---

### Model Karşılaştırma Özeti

| Kriter | A: Lockstep | B: Otoriter Host | C: Split Authority |
|--------|-------------|-------------------|-------------------|
| Implementasyon zorluğu | Yüksek | **Orta** | Çok yüksek |
| Gecikme toleransı | Düşük | **Yüksek** | Orta |
| Board tutarlılığı | Garantili | **Garantili** | Riskli |
| Mevcut kod yeniden kullanımı | Düşük | **Yüksek** | Düşük |
| Hile koruması | Yüksek | **Yüksek** | Düşük |
| Adalet (fairness) | Mükemmel | Host avantajı var | Mükemmel |

**Karar: Seçenek B — Otoriter Host** → en iyi denge.

---

## 6. Önerilen Mimari: Hibrit Otoriter Host

### 6.1 Genel Şema

```
┌───────────────────────────┐          Steam P2P           ┌───────────────────────────┐
│  HOST (Oyuncu A)          │◄──────── Messages ─────────►│  GUEST (Oyuncu B)         │
│                           │                              │                           │
│  ┌─────────────────────┐  │     guest_input (reliable)   │  ┌─────────────────────┐  │
│  │ CoopGame             │  │◄────────────────────────────│  │ OnlineCoopClient    │  │
│  │ (tam simülasyon)     │  │                              │  │ (prediction +       │  │
│  │                      │  │──── board_state (unreli.)───►│  │  render)            │  │
│  │ P1: lokal input      │  │──── piece_state (unreli.)───►│  │                     │  │
│  │ P2: ağdan gelen input│  │──── lock_event (reliable) ──►│  │ P2: lokal input     │  │
│  │                      │  │──── game_event (reliable) ──►│  │ → host'a gönder     │  │
│  └─────────────────────┘  │                              │  └─────────────────────┘  │
└───────────────────────────┘                              └───────────────────────────┘
```

### 6.2 Host Sorumlulukları

1. **Tam CoopGame simülasyonu** — mevcut yerel co-op koduyla birebir aynı
2. **P1 input:** Doğrudan pygame event'lerinden
3. **P2 input:** Network'ten gelen `guest_input` mesajlarından
4. **Yayın:** Board state, piece pozisyonu, skor, olayları guest'e gönderir
5. **Otorite:** Satır temizleme, freeze, scoring kararları sadece host'ta

### 6.3 Guest Sorumlulukları

1. **Input gönderme:** Her tuşa basışta host'a `guest_input` mesajı
2. **Lokal Prediction (opsiyonel ama önerilen):**
   - Kendi parçasının hareketini lokal olarak tahmin eder
   - Host'tan gelen durum ile karşılaştırır
   - Uyumsuzluk varsa host'un durumuna snap eder
3. **Render:** Host'tan gelen board durumunu çizer
4. **Kendi HUD:** Skor, seviye, katkı bilgilerini host'tan alır

### 6.4 Prediction Detayı (Guest P2 Parçası)

```
Guest tuşa basar → lokal olarak parçayı hareket ettirir (anında görsel tepki)
                 → aynı anda host'a input mesajı gönderir
                 
Host mesajı alır → CoopGame'de P2 input'unu uygular
               → sonucu guest'e gönderir

Guest sonucu alır → kendi tahminini host'unkiyle karşılaştırır
                 → eşleşiyorsa: hiçbir şey yapma (smooth)
                 → farklıysa: host'un pozisyonuna geç (snap/interpolate)
```

**Ne zaman uyumsuzluk olur?**
- Parça duvarla çarpışır (guest duvarın farkında değilse)
- Lock delay tetiklenir (zamanlama farkı)
- Aynı satırda çakışma

---

## 7. Mesaj Protokolü Tasarımı

### 7.1 Guest → Host Mesajları

#### `guest_input` (Reliable)
```json
{
  "type": "guest_input",
  "action": "move_left|move_right|rotate|hard_drop|soft_drop_start|soft_drop_stop|hold|das_start|das_stop",
  "seq": 142,
  "ts": 1712990000123
}
```

- **action:** Oyuncu aksiyonu
- **seq:** Monoton artan sıra numarası (duplikasyon/sıralama kontrolü)
- **ts:** Guest'in lokal zamanı (istatistik/debug amaçlı)

#### `guest_ready` (Reliable)
```json
{
  "type": "guest_ready"
}
```

#### `guest_pause` (Reliable)
```json
{
  "type": "guest_pause"
}
```

### 7.2 Host → Guest Mesajları

#### `board_state` (Unreliable, her ~80-100ms)
```json
{
  "type": "board_state",
  "grid": [[[R,G,B], null, ...], ...],
  "owners": [["P1", null, "P2", ...], ...],
  "team_score": 4500,
  "total_lines": 18,
  "level": 4,
  "fall_speed": 740.0,
  "p1_contrib_pct": 55,
  "p2_contrib_pct": 45,
  "p1_frozen": false,
  "p2_frozen": false,
  "seq": 87
}
```

#### `piece_state` (Unreliable, her input sonrası veya ~50ms)
```json
{
  "type": "piece_state",
  "p1_current": {"x": 3, "y": 8, "si": 2, "r": 1},
  "p2_current": {"x": 14, "y": 5, "si": 0, "r": 0},
  "p1_next_si": 4,
  "p2_next_si": 6,
  "p1_hold_si": 1,
  "p2_hold_si": null,
  "p1_ghost_y": 17,
  "p2_ghost_y": 15,
  "seq": 312,
  "input_ack": 140
}
```

- **input_ack:** Guest'in en son işlenen input sequence numarası (prediction doğrulama)
- **ghost_y:** Ghost piece pozisyonu (guest'in tekrar hesaplamaması için)

#### `lock_event` (Reliable)
```json
{
  "type": "lock_event",
  "player": "P1",
  "piece": {"x": 3, "y": 17, "si": 2, "r": 1},
  "cleared_lines": [18, 19],
  "new_score": 4800,
  "new_level": 5,
  "p1_frozen": false,
  "p2_frozen": false,
  "p1_pending_unfreeze": false,
  "p2_pending_unfreeze": true
}
```

#### `game_event` (Reliable)
```json
{
  "type": "game_event",
  "event": "game_over|level_complete|level_failed|pause|resume|countdown",
  "data": { ... }
}
```

#### `game_start` (Reliable)
```json
{
  "type": "game_start",
  "seed": 847291,
  "p1_bag": [3, 1, 5, 0, 6, 2, 4, ...],
  "p2_bag": [6, 0, 2, 4, 1, 5, 3, ...],
  "fall_speed": 900,
  "level_config": { ... },
  "timestamp": 1712990000000
}
```

### 7.3 Çift Yönlü Ortak Mesajlar

#### `ready` / `not_ready` (Reliable)
#### `ping` / `pong` (Unreliable — latency ölçümü)

```json
{
  "type": "ping",
  "ts": 1712990000123,
  "seq": 5
}
```

### 7.4 Bant Genişliği Tahmini

| Mesaj | Boyut | Frekans | Bant (~) |
|-------|-------|---------|----------|
| `guest_input` | ~80 byte | ~10/sn (en kötü) | 800 B/s |
| `board_state` | ~4 KB (kompres edilmemiş) | 10/sn | 40 KB/s |
| `piece_state` | ~200 byte | 20/sn | 4 KB/s |
| `lock_event` | ~300 byte | ~1/sn | 300 B/s |
| **Toplam** | | | **~45 KB/s** |

**Optimizasyon seçenekleri:**
- Board grid'i delta encoding (sadece değişen hücreleri gönder) → %80 azaltma
- Grid renk paletini indeksle (RGB yerine 1 byte) → %66 azaltma
- `board_state` frekansını 5/sn'ye düşür (lock_event anlık günceller) → %50 azaltma
- Sonuç: **~5-10 KB/s** hedeflenebilir

---

## 8. Board Senkronizasyon Detayları

### 8.1 Board State Akışı

```
HOST tarafı:
  CoopGame.update(dt)
    ├── P1 input (lokal) → _try_move, _try_rotate, _hard_drop
    ├── P2 input (ağdan) → _try_move, _try_rotate, _hard_drop
    ├── Gravity ticks
    ├── Lock delays
    └── _lock_and_new_piece()
         ├── board.lock_piece_for_player()
         ├── board.clear_lines()  ← OTORİTER KARAR
         ├── skor güncelleme
         ├── freeze/unfreeze kararı
         └── → lock_event mesajı → Guest'e gönder
              → board_state mesajı → Guest'e gönder

GUEST tarafı:
  OnlineCoopClient.update(dt)
    ├── Kendi input'unu host'a gönder
    ├── Prediction: kendi parçasını lokal hareket ettir
    ├── Host'tan gelen mesajları işle:
    │    ├── board_state → tam board render'ını güncelle
    │    ├── piece_state → parça pozisyonlarını güncelle, prediction doğrula
    │    ├── lock_event → kilit animasyonu, skor güncelleme
    │    └── game_event → oyun durumu değişikliği
    └── Render
```

### 8.2 Board Verisi Neler İçermeli?

**Tam snapshot (ilk bağlantı + periyodik):**
```python
{
    'grid': [[(R,G,B) or None] * 20] * 20,   # Renk bilgisi (çizim için)
    'owners': [['P1'/'P2'/None] * 20] * 20,  # Katkı takibi (HUD için)
}
```

**Delta update (lock_event sonrası):**
```python
{
    'changed_cells': [(x, y, color_or_none, owner_or_none), ...],
    'cleared_rows': [18, 19],                 # Silinip kayan satırlar
}
```

### 8.3 Owner Tracking Senkronizasyonu

**Neden önemli:** Co-op'un en önemli mekanikleri:
- Katkı yüzdesi HUD'u (her iki oyuncu görür)
- BalancedContributionObjective (kampanya hedefi)
- Skor paylaşımı hesaplaması

**Çözüm:** Owner bilgisi `board_state` içinde gönderilmeli. Alternatif olarak, sadece `lock_event`'te hangi oyuncunun hangi hücreleri koyduğu yeterli olabilir — guest kendi board kopyasını tutup lock eventlerden güncelleyebilir.

---

## 9. Parça (Piece) Senkronizasyonu

### 9.1 Bag Sistemi

Yerel co-op'ta her oyuncu bağımsız bag'e sahip: `_p1_bag`, `_p2_bag`.

**Online'da 2 seçenek:**

**A) Seed-Based Determinism (Basit, Önerilen):**
```python
# Host game_start mesajında:
{
  "p1_seed": 12345,
  "p2_seed": 67890
}
# İki taraf aynı seed'den aynı bag'leri üretir
# Pro: Minimum bant genişliği, next piece'i host beklemeden gösterir
# Con: random.shuffle() deterministik olmalı (Python'da: random.seed(x) → garanti)
```

**B) Explicit Piece List (Güvenli):**
```python
# Host game_start mesajında veya periyodik olarak:
{
  "p1_pieces": [3, 1, 5, 0, 6, 2, 4, 1, 3, ...],  # İlk 50 parça
  "p2_pieces": [6, 0, 2, 4, 1, 5, 3, 0, 6, ...]
}
# Pro: %100 garanti senkron
# Con: Daha fazla veri; host yeni parça ürettiğinde göndermesi gerekir
```

**Hibrit Öneri:**
- `game_start`'ta ilk 50 parçayı explicit gönder (her iki oyuncu için)
- Tükenince host yeni 50'li batch üretip gönderir
- Bu hem güvenli hem de bant genişliği dostu

### 9.2 Parça Pozisyonu Senkronizasyonu

**Host → Guest (sürekli):**
- `piece_state` mesajları ile iki oyuncunun aktif parça pozisyonu
- Guest kendi parçası için prediction kullanır, host'un pozisyonuyla doğrular

**Guest → Host (input-driven):**
- `guest_input` mesajları ile sadece aksiyonları gönderir
- Host fizik hesabını kendi simülasyonunda yapar

---

## 10. Freeze / Unfreeze Senkronizasyonu

### 10.1 Problem

Freeze/unfreeze mekanizması zamanlama-hassas. `coop_game.py`'deki kesin akış:

```python
# _try_unfreeze_players() — satır temizliği sonrası çağrılır
def _try_unfreeze_players(self):
    if self.p1_frozen:
        test = Piece(x=0, y=0, shape_index=self.p1_next_piece.shape_index)
        self._place_at_spawn(test, 'P1')
        if self.board.is_valid_position_for_player(test, 'P1'):
            self._p1_pending_unfreeze = True  # Hemen değil, flag set
    # P2 için aynı...

# _freeze_player() — spawn başarısız olduğunda
def _freeze_player(self, player):
    self.p1_frozen = True        # veya p2_frozen
    self.p1_current_piece = None # parçayı kaldır
    self._emit_event('player_frozen', {'player': player})
    self._check_double_freeze()  # İkisi de donmuşsa → game over

# _check_double_freeze()
def _check_double_freeze(self):
    if self.p1_frozen and self.p2_frozen:
        self._activate_game_over()
```

```
Frame N:   P1 kilitledi → spawn alanı dolu → P1 DONDU
Frame N+5: P2 satır temizledi → P1'in spawn alanı açıldı → _p1_pending_unfreeze = True
Frame N+8: P1 gravity tick'inde → _do_unfreeze() → P1 aktif
```

Eğer iki taraf farklı frame'lerde hareket ederse unfreeze zamanlaması uyuşmayabilir.

### 10.2 Çözüm: Host Otoritesi

**Host karar verir:**
1. Freeze tetiklenmesi → `lock_event` mesajında `p1_frozen: true`
2. Unfreeze kararı → `lock_event` mesajında `p1_pending_unfreeze: true`
3. Gerçek unfreeze → `piece_state` mesajında P1'in yeni parçası görünür

**Guest sadece host'un kararını uygular.** Kendi freeze/unfreeze hesabı yapmaz.

---

## 11. Kampanya Modu Entegrasyonu

### 11.1 Mevcut Yapı

```python
class CoopCampaignMode(CoopGame):
    # CoopGame'in üstüne hedef/yıldız katmanı ekler
    # _on_game_event() ile olayları dinler
    # _save_progress() ile ilerlemeyi kaydeder
```

### 11.2 Online Kampanya Nasıl Çalışacak?

**Seçenek 1: Sadece Host Kampanya Takibi Yapar**
```
Host:
  OnlineCoopCampaignMode(CoopCampaignMode)
    - Hedef takibi + yıldız hesabı host'ta
    - İlerleme host'un save'ine yazılır
    - Guest'e hedef durumu game_event ile gönderilir

Guest:
  - HUD'da hedef ilerlemesini gösterir (host'tan gelen veriyle)
  - Kendi save'ine de yazabilir (her iki oyuncu ilerleme kazanır)
```

**Seçenek 2: İki Taraf da Kampanya Takibi Yapar (Paralel)**
```
Her iki taraf CoopCampaignMode çalıştırır
Host → olayları gönderir
Guest → olayları alır ve kendi objective'lerine uygular
Pro: İki tarafın da save'i güncel
Con: Uyumsuzluk riski (skor farkı → farklı yıldız)
```

**Öneri:** Seçenek 1 güvenli; host'un hesapladığı yıldız/skor guest'e de gönderilir ve her iki save'e yazılır.

### 11.3 Hangi Level'in Oynanacağı?

- Level seçimi lobi ekranında yapılır
- Host level'i seçer, metadata'ya yazar: `lobby_data['level'] = '7'`
- Guest katılınca level bilgisini görür
- İkisi de `game_start` mesajıyla level config'i alır

---

## 12. Lobi ve Matchmaking

### 12.1 Lobi Metadata Genişlemesi

Mevcut PvP lobi metadata'sına ek alanlar:

```python
# Co-op lobi metadata'sı
net.set_lobby_data('game', 'quadrix')
net.set_lobby_data('mode', 'coop')           # YENİ: pvp / coop ayrımı
net.set_lobby_data('sub_mode', 'endless')     # YENİ: endless / campaign
net.set_lobby_data('campaign_level', '7')     # YENİ: kampanya ise level no
net.set_lobby_data('host_name', 'Burak')
net.set_lobby_data('visibility', 'private')
net.set_lobby_data('lobby_code', '847291')
net.set_lobby_data('metadata_ready', 'true')
```

### 12.2 Lobi Filtreleme

```python
# Co-op lobi araması
net.add_request_lobby_list_string_filter('game', 'quadrix')
net.add_request_lobby_list_string_filter('mode', 'coop')
# Opsiyonel: campaign/endless filtresi
```

### 12.3 Matchmaking Akışı

```
Ana Menü → "Online Co-op" → Lobi Ekranı
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
   "Lobi Oluştur"        "Kod ile Katıl"       "Lobi Listesi"
         │                      │                      │
    ┌────▼────┐            ┌────▼────┐            ┌────▼────┐
    │ Endless │            │ Kodu    │            │ Açık    │
    │ veya    │            │ gir     │            │ lobileri│
    │Campaign │            │ → join  │            │ listele │
    │ seç     │            └─────────┘            │ → join  │
    └────┬────┘                                   └─────────┘
         │ (campaign seçildiyse)
    ┌────▼────────┐
    │ Level seç   │
    │ (host only) │
    └────┬────────┘
         │
    ┌────▼────────────┐
    │ WAITING         │ ← Rakip bekleniyor
    │ Kod gösteriliyor│
    └────┬────────────┘
         │ Rakip katıldı
    ┌────▼────────────┐
    │ READY_CHECK     │ ← İki oyuncu "Hazır" butonuna basar
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ COUNTDOWN (3-2-1)│
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ PLAYING         │ ← Co-op oyun aktif
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ GAME_OVER       │ ← Her iki oyuncu donmuş / hedef tamamlandı / zaman doldu
    └─────────────────┘
```

### 12.4 Online Co-op Giriş / Bekleme Ekranı Temeli

Evet, bu dosyada bunun **temeli var**; ama bu temel daha çok akış ve fonksiyon referansı seviyesindeydi. Online co-op için ayrıca şu net karar alınmalı:

- Online co-op'un **giriş, lobi, bekleme, ready-check, countdown ve disconnected ekranları** Online PvP'deki hazır online shell üzerinden kurulmalı.
- Online co-op'un **maç içi ekranı** ise Online PvP'den değil, yerel `CoopGame` render zincirinden türetilmeli.

Mevcut Online PvP ekran temeli:
- `online_pvp_game.py:4422-4778` → `_draw_lobby_menu()`
- `online_pvp_game.py:4779-4869` → `_draw_join_code_input()`
- `online_pvp_game.py:4870-5016` → `_draw_waiting_screen()`
- `online_pvp_game.py:5017-5160` → `_draw_ready_check()`
- `online_pvp_game.py:5161-5191` → `_draw_countdown()`
- `online_pvp_game.py:5912-5941` → `_draw_disconnected()`

Bu ekranların panel çizim altyapısı ise zaten ortak helper'lara dayanıyor:
- `retro_style.py:393` → `get_font()`
- `retro_style.py:481` → `get_fitting_font()`
- `retro_style.py:727` → `draw_glass_panel()`
- `retro_style.py:1069` → `draw_uniform_button()`

Yani teknik olarak online co-op için sıfırdan yeni bir lobi/bekleme görsel sistemi yazmak gerekmiyor. Doğru yaklaşım, Online PvP online-shell ekranlarını reuse edip metinleri, aksiyonları, accent renklerini ve birkaç panel içeriğini co-op'a çevirmek.

### 12.5 Online Co-op Lobi / Bekleme Ekranı Reuse Planı

#### Ekran Bazlı Reuse Matrisi

| Online PvP ekranı | Satır | Online Co-op'ta kullanım | Gerekli değişiklik |
|-------------------|-------|--------------------------|--------------------|
| `_draw_lobby_menu()` | 4422-4778 | **Birebir temel alınır** | Sol buton aksiyonları ve sağ panel liste filtre metinleri co-op'a çevrilir |
| `_draw_join_code_input()` | 4779-4869 | **Neredeyse birebir alınır** | Başlık/metinler PvP yerine co-op olarak değiştirilir |
| `_draw_waiting_screen()` | 4870-5016 | **Birebir temel alınır** | "Rakip Bekleniyor" → "Takım Arkadaşı Bekleniyor"; geri aksiyonu co-op lobiye döner |
| `_draw_ready_check()` | 5017-5160 | **Güçlü temel olarak alınır** | VS başlığı ve metin dili co-op'a çevrilir; mode/level badge eklenir |
| `_draw_countdown()` | 5161-5191 | **Birebir alınır** | Yalnızca tema rengi gerekiyorsa güncellenir |
| `_draw_disconnected()` | 5912-5941 | **Birebir temel alınır** | Metinler co-op semantiğine çevrilir |

#### Panel Bazlı Reuse Planı

1. **Lobi giriş ekranı**
   - `_draw_lobby_menu()` içindeki sol aksiyon kolonu korunur.
   - PvP aksiyonları yerine şu aksiyonlar konur:
     - `create_coop_endless_lobby`
     - `create_coop_campaign_lobby`
     - `join_coop_by_code`
     - `find_coop_lobbies`
   - Sağdaki mevcut cam panel lobi listesi korunur.
   - Sadece rozet/metinler değişir:
     - `Açık lobi`
     - `Kilitli co-op lobi`
     - `Endless`
     - `Kampanya L7`

2. **Kod ile katıl paneli**
   - `_draw_join_code_input()` neredeyse aynen alınır.
   - 6 haneli kod kutuları, copy/paste davranışı, submit butonu aynen kalır.
   - Sadece localization anahtarları co-op varyantına çevrilir.

3. **Bekleme ekranı**
   - `_draw_waiting_screen()` içindeki merkez cam panel korunur.
   - Büyük lobby code gösterimi, `Kodu Kopyala`, `Arkadaş Davet Et` butonları aynen kalır.
   - Değişecek alanlar:
     - başlık: `Rakip Bekleniyor...` → `Takım Arkadaşı Bekleniyor...`
     - geri butonu: `PvP Alanına Geri Dön` → `Co-op Alanına Geri Dön`
     - durum mesajları co-op semantiğiyle güncellenir
   - Eğer lobby campaign ise panelde ek badge gösterilir:
     - `Kampanya`
     - `Level 7`

4. **Ready-check ekranı**
   - `_draw_ready_check()` içindeki iki kolonlu avatar paneli korunur.
   - `VS` başlığı doğrudan kullanılabilir ama co-op için daha doğru iki seçenek var:
     - `CO-OP`
     - veya ortada takım ikonu / zincir / bağ simgesi
   - READY badge sistemi aynen korunur.
   - Alt alana ek bilgi satırı eklenir:
     - `Mod: Endless`
     - veya `Mod: Kampanya • Level 7`

5. **Countdown ve disconnect**
   - Countdown ekranı yeniden tasarlanmaz; doğrudan PvP temelinden gelir.
   - Disconnect ekranı da aynı panel estetiğiyle reuse edilir.

#### Mimari Uygulama Planı

`online_coop_game.py` içinde şu ayrım yapılmalı:

```python
# online shell states
LOBBY_MENU
WAITING
READY_CHECK
COUNTDOWN
DISCONNECTED

# in-match state
PLAYING
GAME_OVER
```

- `LOBBY_MENU`, `WAITING`, `READY_CHECK`, `COUNTDOWN`, `DISCONNECTED`:
  - Online PvP'deki panel/düğme iskeleti reuse edilir.
  - Ortak helper'lar: `draw_glass_panel`, `draw_uniform_button`, `get_font`, `get_fitting_font`
- `PLAYING`, `GAME_OVER`:
  - Yerel `CoopGame` görsel zinciri reuse edilir.

Bu ayrım önemli; çünkü online co-op'ta **online shell = PvP'den reuse**, **maç içi render = CoopGame'den reuse** olmalı.

#### V1 İçin Net Karar

İlk sürümde online co-op giriş/bekleme ekranı için:
- sıfırdan yeni panel sistemi yazılmayacak,
- Online PvP lobi/bekleme panel kompozisyonu temel alınacak,
- yalnızca metin, renk, aksiyon, mode badge ve level badge katmanı değiştirilecek.

### 12.6 Online Co-op Giriş / Bekleme Ekranı Tam Wireframe Planı

Bu alt bölüm, online co-op için yapılacak online-shell ekranlarının tam ekran yerleşim planını tanımlar. Amaç, implementasyon sırasında "hangi panel nereye oturacak?" sorusunu açık bırakmamaktır.

#### 12.6.1 Lobi Menü Ekranı Wireframe

**Kaynak temel:** `online_pvp_game.py:4422-4778` `_draw_lobby_menu()`

**Yerleşim mantığı:**
- Üstte tam genişlik başlık alanı
- Solda aksiyon kolonu
- Sağda lobi listesi cam paneli
- En altta durum mesajı ve Steam ID

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ONLINE CO-OP                                      │
│                Steam üzerinden 2 oyunculu online co-op                      │
│                                                                              │
│  ┌──────────────────────────────┐   ┌────────────────────────────────────┐   │
│  │ ── Özel Co-op ──             │   │ Mevcut Co-op Lobileri              │   │
│  │ [ Endless Özel Lobi ]        │   │ [Tümü] [Açık Lobiler]        [12] │   │
│  │ [ Kampanya Özel Lobi ]       │   │ ───────────────────────────────── │   │
│  │ [ Kod ile Katıl ]            │   │ ┌───────────────────────────────┐ │   │
│  │ [ Arkadaş Davet Et ]         │   │ │ Burak'ın Lobisi               │ │   │
│  │                              │   │ │ 1/2 oyuncu · Endless · Kod... │ │   │
│  │ ┌──────────────────────────┐ │   │ │ [Katıl]                       │ │   │
│  │ │ 6 haneli kod kutuları    │ │   │ └───────────────────────────────┘ │   │
│  │ │ [_][_][_][_][_][_]       │ │   │ ┌───────────────────────────────┐ │   │
│  │ │ [ Kodla Katıl ]          │ │   │ │ Elif'in Lobisi                │ │   │
│  │ └──────────────────────────┘ │   │ │ 2/2 oyuncu · Kampanya L7      │ │   │
│  │                              │   │ │ [Dolu]                        │ │   │
│  │ ── Herkese Açık ──           │   │ └───────────────────────────────┘ │   │
│  │ [ Açık Endless Lobi ]        │   │ ...                                │   │
│  │ [ Açık Kampanya Lobi ]       │   └────────────────────────────────────┘   │
│  │ [ Co-op Lobi Bul ]           │                                            │
│  │ [ Ana Menüye Dön ]           │                                            │
│  └──────────────────────────────┘                                            │
│                                                                              │
│                      Durum mesajı / hata metni                              │
│                             Steam ID: ...                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Co-op için ekran davranışı:**
- Sol panel PvP'deki gibi buton-dominant kalır.
- Sağ panel PvP'deki gibi liste görünümü olarak kalır.
- `join_code_active=True` olduğunda sol panel içinde kod giriş alt paneli açılır.
- Kampanya lobi oluşturulacaksa butona basınca level picker akışı açılır; level seçildikten sonra lobby create yapılır.

**Bu ekranın bağlandığı state alanları:**
- `_lobby_list` — mevcut bulunan lobiler
- `_lobby_list_filter` — `all` / `public`
- `_lobby_list_fetching` — yükleniyor durumu
- `_join_code_active` — kod paneli açık mı
- `_join_code_error` — kod giriş hatası
- `_status_msg` — alt bilgi/hata mesajı

#### 12.6.2 Bekleme Ekranı Wireframe

**Kaynak temel:** `online_pvp_game.py:4870-5016` `_draw_waiting_screen()`

**Yerleşim mantığı:**
- Ortada tek büyük cam panel
- Üstte başlık ve kısa animasyon
- Orta bölümde büyük lobby code
- Alt bölümde copy / invite / back aksiyonları

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                    ┌──────────────────────────────────────┐                  │
│                    │ Takım Arkadaşı Bekleniyor...         │                  │
│                    │ ●●○                                   │                  │
│                    │                                      │                  │
│                    │ [ Mod: Endless ]                     │                  │
│                    │ veya                                 │                  │
│                    │ [ Mod: Kampanya ] [ Level 7 ]        │                  │
│                    │                                      │                  │
│                    │ Lobi Kodu                            │                  │
│                    │            482 917                   │                  │
│                    │    Bu kodu arkadaşınla paylaş        │                  │
│                    │                                      │                  │
│                    │ [ Kodu Kopyala ]                    │                  │
│                    │                                      │                  │
│                    │ ───── veya Steam'den davet et ───── │                  │
│                    │                                      │                  │
│                    │ [ Arkadaş Davet Et ]                │                  │
│                    │ [ Co-op Lobi Alanına Dön ]          │                  │
│                    └──────────────────────────────────────┘                  │
│                                                                              │
│                         Durum mesajı / kopyalandı vb.                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Co-op için ekran davranışı:**
- Eğer lobby `endless` ise tek mode badge gösterilir.
- Eğer lobby `campaign` ise mode badge + level badge birlikte gösterilir.
- `invite_friend` aksiyonu korunur.
- Lobby code büyük ve birincil çağrı öğesi olarak korunur; bu ekranın merkezinde kalmalı.

**Bu ekranın bağlandığı state alanları:**
- `_lobby_code`
- `_status_msg`
- `selected_submode` veya eşdeğeri (`endless` / `campaign`)
- `selected_campaign_level` veya eşdeğeri

#### 12.6.3 Ready-Check Ekranı Wireframe

**Kaynak temel:** `online_pvp_game.py:5017-5160` `_draw_ready_check()`

**Yerleşim mantığı:**
- Ortada büyük merkezi cam panel
- Sol ve sağda iki oyuncu kartı
- Ortada PvP'deki `VS` alanı yerine co-op başlık/ikon alanı
- Altta ready butonu veya "rakip bekleniyor" badge'i

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                 ┌──────────────────────────────────────────┐                 │
│                 │                 CO-OP                    │                 │
│                 │        veya takım ikonu / zincir         │                 │
│                 │                                          │                 │
│                 │   ┌────────────┐   │   ┌────────────┐    │                 │
│                 │   │ Avatar      │   │   │ Avatar      │   │                 │
│                 │   │ Sen         │   │   │ Burak       │   │                 │
│                 │   │ READY       │   │   │ Bekleniyor  │   │                 │
│                 │   └────────────┘   │   └────────────┘    │                 │
│                 │                                          │                 │
│                 │ [ Mod: Endless ]                         │                 │
│                 │ veya                                     │                 │
│                 │ [ Mod: Kampanya ] [ Level 7 ]            │                 │
│                 │                                          │                 │
│                 │ [ Hazırım! ]                             │                 │
│                 │ veya                                     │                 │
│                 │ [ Rakip bekleniyor... ]                  │                 │
│                 │                                          │                 │
│                 │ [ Ana Menüye Dön ]                       │                 │
│                 └──────────────────────────────────────────┘                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Co-op için ekran davranışı:**
- PvP'deki iki kolonlu avatar dizilimi korunur.
- Ortadaki dikey ayırıcı korunur.
- `VS` yerine `CO-OP` ya da takım sembolü gelmesi daha doğru olur.
- `my_ready` ve `opponent_ready` akışı PvP ile birebir reuse edilir.
- Eğer kampanya modundaysa, alt orta bölümde level badge zorunlu gösterilir.

**Bu ekranın bağlandığı state alanları:**
- `my_ready`
- `opponent_ready`
- `net.my_steam_id`
- `net.opponent_steam_id`
- `net.opponent_name`
- `_status_msg` (opsiyonel alt bilgi)
- `selected_submode`
- `selected_campaign_level`

#### 12.6.4 Wireframe Uygulama Kuralı

Bu üç ekran için şu kural geçerli olmalı:
- Panel konumları, boşluklar ve buton dili mümkün olduğunca PvP ile aynı kalsın.
- Değişen şey layout değil; metin, ikonografi, accent renkleri ve mode/level içerikleri olsun.
- Böylece kullanıcı Online PvP'den tanıdığı online akışı Online Co-op'ta da anında tanır.

### 12.7 Lobby Menu / Waiting / Ready-Check Component Kırılımı

Bu bölüm, ekranların hangi UI bileşenlerinden oluşacağını ve her bir bileşenin hangi state'e bağlanacağını tanımlar.

#### 12.7.1 Ortak Shell Bileşenleri

| Component | Kaynak | Sorumluluk | State / Props |
|-----------|--------|------------|---------------|
| `OnlineShellTitle` | PvP title block | Ekran başlığı + alt açıklama | `title_key`, `subtitle_key` |
| `GlassPanelCard` | `draw_glass_panel()` | Cam panel arka planı | `rect`, `accent_color`, `glow` |
| `PrimaryActionButton` | `draw_uniform_button()` | Ana aksiyon butonları | `label`, `shortcut`, `action`, `hovered` |
| `StatusMessageFooter` | PvP lobby/waiting footer | Alt bilgi/hata mesajı | `_status_msg` |
| `OnlineShellBadge` | PvP badge pattern | Mode/level/visibility rozeti | `text`, `color` |

#### 12.7.2 Lobby Menu Component Ağacı

```text
OnlineCoopLobbyMenuScreen
├── OnlineShellTitle
├── CoopLobbyActionRail
│   ├── SectionHeader("Özel Co-op")
│   ├── CreatePrivateEndlessButton
│   ├── CreatePrivateCampaignButton
│   ├── JoinByCodeToggleButton
│   ├── InviteFriendButton
│   ├── JoinCodeEntryPanel (conditional)
│   ├── SectionHeader("Herkese Açık")
│   ├── CreatePublicEndlessButton
│   ├── CreatePublicCampaignButton
│   ├── FindCoopLobbyButton
│   └── BackButton
├── CoopLobbyListPanel
│   ├── LobbyFilterTabs
│   ├── LobbyCountBadge
│   ├── LobbyListItems[]
│   │   ├── LobbyName
│   │   ├── LobbyMetaRow
│   │   ├── LobbyBadgeRow
│   │   └── JoinLobbyButton
│   └── EmptyOrLoadingState
└── StatusMessageFooter
```

**Bileşen detayları:**

1. `CoopLobbyActionRail`
   - Kaynak: `_draw_lobby_menu()` sol kolon yapısı
   - Sorumluluk: create/join/find/back aksiyonlarının merkezi paneli
   - State:
     - `_join_code_active`
     - `_join_code_error`
   - Emit ettiği aksiyonlar:
     - `create_coop_endless_private`
     - `create_coop_campaign_private`
     - `create_coop_endless_public`
     - `create_coop_campaign_public`
     - `toggle_join_code`
     - `find_coop_lobbies`
     - `back`

2. `JoinCodeEntryPanel`
   - Kaynak: `_draw_join_code_input()`
   - Sorumluluk: 6 haneli kodu giriş ve submit etme
   - State:
     - `_join_code_active`
     - `_join_code_input`
     - `_join_code_error`
   - Emit:
     - `join_code_submit`
     - `join_code_field_focus`

3. `CoopLobbyListPanel`
   - Kaynak: `_draw_lobby_menu()` sağ lobi listesi paneli
   - Sorumluluk: bulunan co-op lobileri gösterme
   - State:
     - `_lobby_list`
     - `_lobby_list_filter`
     - `_lobby_list_fetching`
     - `_lobby_list_scroll`
   - Her item için ek data:
     - `sub_mode`
     - `campaign_level`
     - `visibility`
     - `requires_code`

4. `LobbyListItem`
   - Sorumluluk: tek lobby kartı
   - Alt alanlar:
     - host adı
     - oyuncu sayısı
     - visibility badge
     - submode badge (`Endless` / `Kampanya`)
     - level badge (opsiyonel)
     - join button

#### 12.7.3 Waiting Screen Component Ağacı

```text
OnlineCoopWaitingScreen
├── WaitingPanelCard
│   ├── WaitingTitle
│   ├── DotAnimation
│   ├── CoopModeBadgeRow
│   ├── LobbyCodeBlock
│   │   ├── LobbyCodeLabel
│   │   ├── LobbyCodeValue
│   │   └── LobbyCodeHint
│   ├── CopyCodeButton
│   ├── InviteSeparator
│   ├── InviteFriendButton
│   └── BackToCoopLobbyButton
└── StatusMessageFooter
```

**Bileşen detayları:**

1. `CoopModeBadgeRow`
   - State:
     - `selected_submode`
     - `selected_campaign_level`
   - Görünüm:
     - `Endless` ise tek rozet
     - `Campaign` ise iki rozet: mod + level

2. `LobbyCodeBlock`
   - Kaynak: PvP waiting screen code section
   - State:
     - `_lobby_code`
   - Sorumluluk:
     - lobby code'u büyük tipografiyle göstermek
     - oyuncuyu paylaşmaya yönlendirmek

3. `WaitingActionStack`
   - İçerik:
     - `CopyCodeButton`
     - `InviteFriendButton`
     - `BackToCoopLobbyButton`
   - Emit:
     - `copy_lobby_code`
     - `invite_friend`
     - `back_to_coop_lobby`

#### 12.7.4 Ready-Check Screen Component Ağacı

```text
OnlineCoopReadyCheckScreen
├── ReadyCheckPanelCard
│   ├── CoopHeaderMark
│   ├── PlayerReadyColumn(Self)
│   │   ├── AvatarFrame
│   │   ├── PlayerName
│   │   └── ReadyBadgeOrWaitingText
│   ├── CenterDivider
│   ├── PlayerReadyColumn(Opponent)
│   │   ├── AvatarFrame
│   │   ├── PlayerName
│   │   └── ReadyBadgeOrWaitingText
│   ├── CoopModeBadgeRow
│   ├── ReadyPrimaryAction
│   └── ExitSecondaryAction
└── StatusMessageFooter
```

**Bileşen detayları:**

1. `PlayerReadyColumn`
   - Kaynak: PvP `_draw_ready_check()` avatar kolonları
   - State:
     - `steam_id`
     - `display_name`
     - `ready`
   - Alt yardımcısı:
     - `_get_steam_avatar_surface()` (bkz. `online_pvp_game.py` avatar helper bölümü)

2. `CoopHeaderMark`
   - PvP'de `VS`
   - Co-op'ta seçenekler:
     - sabit `CO-OP` metni
     - veya tema uygun takım ikonu
   - V1 için en güvenli çözüm: `CO-OP` text mark

3. `ReadyPrimaryAction`
   - State:
     - `my_ready`
   - Davranış:
     - `my_ready=False` → `Hazırım!` butonu
     - `my_ready=True` → pasif `Rakip bekleniyor...` rozeti

4. `ExitSecondaryAction`
   - PvP pattern'i korunur
   - Co-op'ta aksiyon `exit_coop_lobby` veya `exit_menu`

#### 12.7.5 Ekranlar Arası Shared Component Kararı

Kod tarafında aynı görünümü korumak için şu yapı önerilir:

```python
class OnlineCoopShellRenderer:
    def draw_lobby_menu(...): ...
    def draw_join_code_input(...): ...
    def draw_waiting_screen(...): ...
    def draw_ready_check(...): ...
    def draw_countdown(...): ...
    def draw_disconnected(...): ...
```

veya daha hafif çözüm:

```python
class OnlineCoopGame:
    # OnlinePvPGame'deki ilgili draw bloklarını adapte ederek içerir
```

**Tercih:** V1'de hızlı ilerlemek için `OnlineCoopGame` içine adapte edilmiş draw blokları alınır. Kod tekrarı büyürse V2'de `OnlineCoopShellRenderer` ayrılır.

#### 12.7.6 Component Seviyesinde Kabul Kriterleri

- Lobby menu'de action rail ve lobby list paneli aynı frame'de birlikte görünmeli.
- Join code paneli açıldığında sol kolon akışı bozulmamalı; liste paneli yerinde kalmalı.
- Waiting screen'de lobby code merkezi odak olmalı; mod/level bilgisi code alanını gölgelememeli.
- Ready-check ekranında iki oyuncu kartı simetrik hizalanmalı.
- Ready durumu yalnızca badge rengiyle değil, metinle de anlaşılmalı.
- Tüm shell ekranları aynı cam panel ve buton helper'larını kullanmalı; ayrı stil ailesi oluşmamalı.

---

## 13. Latency ve Hata Toleransı

### 13.1 Gecikme Telafisi

| Bileşen | Hedef | Strateji |
|---------|-------|----------|
| Guest input → host'a ulaşması | ~50-100ms | Client prediction ile gizle |
| Host board state → guest'e ulaşması | ~50-100ms | Interpolation ile smooth |
| Lock event → guest animasyonu | ~50-100ms | Reliable mesaj, hemen uygula |
| Piece position sync | ~30-60ms | Unreliable, yüksek frekans |

### 13.2 Client Prediction Detayı

```
Guest Input Prediction:

1. Guest "sola hareket" tuşuna basar
2. LOKAL: Guest kendi parçasının kopyasını sola kaydırır (anında)
3. AĞ: guest_input{action: "move_left", seq: 142} → host'a gönder
4. Host mesajı alır, CoopGame'de _try_move('P2', -1) çağırır
5. Host sonucu: piece_state{p2_current: {x: 13, ...}, input_ack: 142} → guest'e gönder
6. Guest alır:
   - input_ack == 142, son prediction ile karşılaştır
   - x eşleşiyor → sorun yok
   - x farklı (duvarla çarpışmış) → host'un x'ine snap et
```

**Prediction NE İÇİN yapılır:**
- `move_left`, `move_right` → pozisyon tahmini
- `rotate` → rotasyon tahmini
- `soft_drop` → y pozisyonu tahmini

**Prediction YAPILMAZ:**
- `hard_drop` → lock'a neden olur, host'un onayını bekle
- `hold` → parça değişimi, host'un next piece bilgisi gerekli
- Lock delay → zamanlama host'a bağlı

### 13.3 Bağlantı Kopması

```
Bağlantı Kopması Akışı:

1. Guest'ten 3 saniye mesaj gelmezse:
   - Host: "Bağlantı sorunlu..." uyarısı göster
   - Host: oyunu duraklatmayı TEKLİF et (PvP'de yoktu, co-op'ta mantıklı)
   
2. Guest'ten 8 saniye mesaj gelmezse:
   - Host: "Bağlantı koptu" ekranı
   - Seçenekler: "Bekle" / "Tekli devam et" / "Çık"
   
3. Host'tan 3 saniye mesaj gelmezse:
   - Guest: "Host ile bağlantı kurulamıyor..." uyarısı
   
4. Host'tan 8 saniye mesaj gelmezse:
   - Guest: "Bağlantı koptu" → Ana menüye dön
```

**Yeniden bağlanma (Reconnect):**
- Kısa kopmalarda (<5 sn): otomatik yeniden bağlan
- Host full board_state gönderir (recovery snapshot)
- Guest state'i host'unkiyle değiştirir

### 13.4 Pause Senkronizasyonu

**PvP'den farklı olarak co-op'ta pause ORTAKTIR:**
- Herhangi biri ESC'ye basınca → iki tarafta da duraklar
- Resume de ortak (iki tarafın "devam" demesi gerekir veya pause eden devam eder)

---

## 14. UI / UX Değişiklikleri

### 14.1 Ana Menü

Mevcut menü düzeni:
```
[Solo] [PvP Lokal] [Co-op Lokal] [Online PvP] [Kampanya] [Co-op Kampanya]
```

Eklenmesi gereken:
```
[Online Co-op]     → Endless mod veya Kampanya seçimi
[Online Co-op Kampanya]  → Level seçim + online
```

Veya mevcut "Online" butonunun altında mod seçimi:
```
[ Online ] → { PvP | Co-op Endless | Co-op Kampanya }
```

### 14.2 Lobi Ekranı Değişiklikleri

PvP lobi ekranından farklılar:

| Eleman | PvP | Co-op |
|--------|-----|-------|
| Başlık | "Online PvP" | "Online Co-op" |
| Mod göstergesi | — | "Endless" veya "Kampanya Level 7" |
| Level seçici | — | Host: Level seç butonu, Guest: salt okunur |
| Hazır butonu | "Hazır" | "Hazır" (aynı) |
| Renk teması | Kırmızı/mavi | Yeşil/turkuaz (kooperatif hissi) |

### 14.3 Oyun İçi HUD

```
┌──────────────────────────────────────────┐
│  Takım Skoru: 4500    Level: 4           │
│  Satırlar: 18   Süre: 2:35              │
│  ──────────────────────────────────       │
│  [P1 Katkı ██████░░ 55%]                │
│  [P2 Katkı █████░░░ 45%]                │
│                                          │
│     P1 (Sen)          P2 (Burak)         │
│  Hold | Board  10×20 sütun  | Board Hold │ 
│  Next |  (midline duvarı)   | Next       │
│       |                     |            │
│  ⚡ 0ms               📡 47ms           │  ← Gecikme göstergesi (YENİ)
│                                          │
│  [Hedef 1: 20 satır temizle ██████ 85%]  │  ← Kampanya hedefleri
│  [Hedef 2: Dengeli katkı ≥30% ✓]        │
└──────────────────────────────────────────┘
```

### 14.4 Gecikme Göstergesi (Yeni)

- Host: 0ms (her zaman)
- Guest: RTT/2 gösterilir (ping/pong mesajlarından hesaplanır)
- Renk kodlu: Yeşil (<60ms), Sarı (60-120ms), Kırmızı (>120ms)

### 14.5 Yerel ile Birebir Görsel Parite İlkesi

Bu başlık kritik: **online co-op oyun içi ekranı, görsel olarak Online PvP'ye değil yerel CoopGame'e benzeyecek.**

Yani oyun içi render tarafında ana referans:
- `coop_game.py:2191` → `_render_game()`
- `coop_game.py:2380` → `_calculate_layout()`
- `coop_game.py:2412` → `_draw_grid()`
- `coop_game.py:2428` → `_draw_locked_blocks()`
- `coop_game.py:2458` → `_draw_piece()`
- `coop_game.py:2488` → `_draw_ghost()`
- `coop_game.py:2541` → `_draw_hud()`
- `coop_game.py:2596` → `_draw_side_panels()`
- `coop_game.py:2709` → `_draw_freeze_overlay()`
- `coop_game.py:2740` → `_draw_pause_menu()`
- `coop_game.py:2840` → `_draw_game_over_screen()`

**Önemli mimari sonucu:**
- Online PvP'deki `online_pvp_game.py:5192` `_draw_game()` ve `online_pvp_game.py:5576` `_draw_opponent_board()` doğrudan oyun içi layout temeli yapılmamalı.
- Çünkü PvP ekranı doğal olarak "benim tahta + rakip tahta" kompozisyonuna göre tasarlanmış.
- Co-op'ta ise hedef, yerel co-op ile aynı board yerleşimi, aynı HUD yoğunluğu, aynı side panel düzeni ve aynı cam panel estetiği.

Bu yüzden en temiz yaklaşım:
1. `CoopGame` render helper'larını shared bir render katmanına çıkarmak.
2. Host ve guest bu ortak render katmanını kullanmak.
3. Online katmanın sadece state beslemesi yapması; görsel kompozisyonu yeniden icat etmemesi.

### 14.6 Davranış, Ayar ve Ses Paritesi

Yerel ile aynı his sadece görselden gelmiyor; davranış ve ayar akışı da aynı kalmalı.

**Yerel co-op referans noktaları:**
- `coop_game.py:365` → `_resolve_controls()`
- `coop_game.py:410` → `_ensure_pause_settings_screen()`
- `coop_game.py:433` → `_sync_runtime_settings_from_manager()`
- `coop_game.py:1744` → `handle_input()`
- `coop_game.py:1930` → `update()`
- `coop_game.py:168-174` → `music_enabled`, `sound_enabled`, `music_volume`, `sfx_volume` başlangıç sync'i
- `coop_game.py:187-195` → `bg_transparency`, `ThemeManager`, `BlockStyleManager`
- `coop_game.py:2088-2115` → pause menüsünden müzik/sfx toggle ve volume slider davranışı

Online co-op'ta bunlar korunmalı:
- Aynı kontrol remap sistemi
- Aynı pause içi settings ekranı
- Aynı ses aç/kapa ve volume slider davranışı
- Aynı theme / block style / arka plan transparency okuma akışı
- Aynı oyun içi ayar değişikliği sonrası runtime sync mantığı

### 14.7 Yerel-Parite Kabul Kriterleri

Online co-op işi "tamam" sayılmadan önce aşağıdaki checklist sağlanmalı:

- Aynı pencere boyutunda local co-op ve online co-op board yerleşimi piksel seviyesinde aynı görünmeli.
- Cell size, board offset, next/hold panel hizası local ile aynı hesaplanmalı.
- Ghost piece, locked block, grid çizimi ve side panel kartları aynı görsel dili kullanmalı.
- Freeze overlay, pause menüsü ve game over ekranı local ile aynı olmalı; yalnızca online'a özel ek bilgiler ayrı satır olarak eklenmeli.
- Parçacık efektleri, hard drop trail ve screen shake yoğunluğu local ile aynı olmalı.
- Müzik/sfx toggle, volume slider, pause settings ekranı davranışı local ile aynı olmalı.
- Online maç sırasında PvP'ye özgü rakip-header kompozisyonu kullanılmamalı.
- Bir oyuncu ağ üzerinden bağlı diye HUD sadeleştirilmemeli; hedef local co-op görünümünü korumak.

---

## 15. Dosya / Modül Planı

### 15.1 Yeni Dosyalar

| Dosya | Satır (tahmin) | Sorumluluk |
|-------|---------------|------------|
| `src/online_coop_game.py` | ~2000-3000 | Ana online co-op modülü (state machine, host/guest rolleri, lobi UI, render) |

> **Not:** Tek dosya yaklaşımı önerilir. `OnlineCoopGame` sınıfı host/guest ayrımını internal olarak yapar — tıpkı `OnlinePvPGame`'in tek dosyada hem host hem guest yönetmesi gibi.
>
> **Opsiyonel:** Dosya aşırı büyürse ikinci adımda yalnızca mesaj sabitleri ve encode/decode yardımcıları için `src/online_coop_protocol.py` ayrılabilir. İlk iterasyonda zorunlu değil.

### 15.2 Değiştirilecek Mevcut Dosyalar

| Dosya | Değişiklik | Tahmini Ekleme |
|-------|-----------|----------------|
| `src/coop_game.py` | `inject_remote_input()` metodu | ~40 satır |
| `src/steam_networking.py` | `MsgType`'a 5 yeni sabit | ~5 satır |
| `src/menu.py` | "Online Co-op" dashboard tile | ~15 satır |
| `src/main.py` | `_handle_online_coop()` + state + import | ~80 satır |
| `src/localization.py` | Yeni çeviri anahtarları | ~20 satır |
| `src/constants.py` | Online co-op sabitleri (opsiyonel) | ~5 satır |

### 15.3 Dokunulmayacak Dosyalar

| Dosya | Neden |
|-------|-------|
| `steamworks/steam_net_bridge/steam_net_bridge.cpp` | Mevcut C++ API tüm ihtiyaçları karşılıyor |
| `src/coop_board.py` | Board mantığı host tarafında birebir çalışacak |
| `src/board.py` | Temel grid yapısı değişmeyecek |
| `src/pieces.py` | Parça tanımları değişmeyecek |
| `src/campaign/coop_level_data.py` | Level verileri değişmeyecek |
| `src/campaign/coop_objectives.py` | Hedef mantığı değişmeyecek |
| `src/campaign/coop_campaign_mode.py` | Host tarafında zaten çalışıyor; online'a özel değişiklik gerektirmiyor |
| `src/steam_integration.py` | Pump thread mekanizması mevcut haliyle yeterli |

---

## 16. Aşamalı Uygulama Planı

### Aşama 1: Temel Altyapı (Tahmini Kapsam: Orta)

1. **İlk iterasyonda protokolü `online_coop_game.py` içinde tut:**
  - Mesaj tipleri (sabitler)
  - Serialization/deserialization yardımcıları
  - Board grid encoding/decoding
  - Dosya büyürse ikinci iterasyonda `online_coop_protocol.py` ayrılabilir

2. **`coop_game.py` genişlet:**
   - P2 input injection API'si ekle:
     ```python
     def inject_remote_input(self, player: str, action: str):
         """Network'ten gelen input'u uygula"""
     ```
   - Event emitter'a network callback hook ekle

3. **`online_coop_game.py` oluştur — sadece endless mod:**
   - State machine: LOBBY_MENU → WAITING → READY_CHECK → COUNTDOWN → PLAYING → GAME_OVER
   - Host rolü: CoopGame instance + network yayın
   - Guest rolü: Board render + prediction + input gönderme

### Aşama 2: Lobi ve Matchmaking

4. **Lobi ekranı UI:**
   - Mod seçimi (Endless / Campaign)
   - Lobi oluşturma, kod ile katılma, liste
   - Ready check

5. **`menu.py` ve `main.py` entegrasyonu:**
   - Ana menüye "Online Co-op" eklenmesi
   - Yaşam döngüsü yönetimi

### Aşama 3: Client Prediction

6. **Guest-side prediction:**
   - Lokal parça takibi
   - Host ACK ile doğrulama
   - Snap/interpolation
   - Ghost piece

### Aşama 4: Kampanya Entegrasyonu

7. **Online kampanya desteği:**
   - Level seçim ekranı (host seçer)
   - Hedef takibi (host-otoriter)
   - Yıldız ve ilerleme kaydetme (her iki taraf)

### Aşama 5: Polish ve Edge Cases

8. **Bağlantı kopması / yeniden bağlanma**
9. **Pause senkronizasyonu**
10. **Gecikme göstergesi UI**
11. **Board delta encoding optimizasyonu**

---

## 17. Riskler ve Açık Sorular

### 17.1 Teknik Riskler

| Risk | Olasılık | Etki | Azaltma |
|------|----------|------|---------|
| Python float determinizm | Orta | Board desync | Otoriter host modeli bunu ortadan kaldırır |
| Guest input gecikmesi → kötü UX | Yüksek | Oynanabilirlik | Client prediction zorunlu |
| Board state mesaj boyutu | Düşük | Bant genişliği | Delta encoding, palet indeksleme |
| Lock delay zamanlama farklılığı | Orta | Görsel uyumsuzluk | Host otoritesi; guest sadece render |
| Freeze/unfreeze race condition | Orta | Oyun durumu hatası | Host tek karar verici |
| Mevcut C++ bridge cross-platform channel sorunu | Düşük | Kanal kullanılamaz | Tek kanal kullanmaya devam |

### 17.2 Tasarım Kararları (Henüz Kesinleşmemiş)

| Soru | Seçenekler | Değerlendirme |
|------|-----------|---------------|
| Host kim olacak? | Lobi kuran otomatik host / Oy | Lobi kuran = host (basit, PvP ile tutarlı) |
| Guest kendi save'ine yazabilir mi? | Evet / Hayır | Evet — ikisi de ilerleme kazanmalı |
| Campaign level'i kim seçer? | Sadece host / İkisi de önerir | Sadece host (basit) |
| Prediction scope | Sadece move/rotate / Hard drop dahil | Sadece move/rotate (güvenli) |
| Board snapshot frekansı | 5/sn / 10/sn / event-driven | Event-driven + 5/sn periyodik |
| Reconnect desteği | Var / Yok (v1) | V1'de yok, v2'de ekle |

### 17.3 UX Açık Soruları

1. **Host avantajı:** Host 0ms gecikme ile oynar, guest ~50-100ms. Bu co-op'ta kabul edilebilir mi? (PvP'den farklı olarak rekabet yok, sadece işbirliği)

2. **Ortak pause:** Bir oyuncu pause'a basınca diğeri de durmalı mı? Yoksa sadece kendi tarafı mı dursun?

3. **Chat / ping sistemi:** Oyuncuların iletişim kurması için basit bir ping/emoji sistemi gerekli mi?

4. **Katkı yüzdesi:** Guest'in katkısı network gecikmesi yüzünden düşük kalırsa → BalancedContributionObjective adaletsiz olabilir. Kampanya hedeflerinde gecikme toleransı eklenmeli mi?

5. **Aynı level'i farklı yıldızlarla bitirme:** Host 3 yıldız alır ama guest bağlantı sorunu yüzünden 2 yıldız alırsa → host'un yıldızı mı geçerli?

---

## 18. Mevcut Kodda Yeniden Kullanılabilecek Yapılar (Detaylı Satır Referansları)

Bu bölüm, online co-op implementasyonunda doğrudan kopyalanabilecek veya adapte edilebilecek mevcut kod bloklarını **kesin satır numaralarıyla** belirtir.

### 18.1 `src/steam_networking.py` — %100 Yeniden Kullanılabilir

Tüm networking alt katmanı **hiçbir değişiklik gerektirmeden** online co-op için kullanılabilir.

| Yapı | Satır | Kullanım |
|------|-------|----------|
| `SteamNetworking` sınıfı | Tümü | Ana networking API — init, tick, send, shutdown |
| `generate_lobby_code()` | 255-265 | Lobi kodu üretimi (MD5-based 6 hane) |
| `MsgType` sabitleri | 272-288 | Mevcut mesaj tipleri + co-op yenileri eklenecek |
| `NetEvent` / `NetMessage` | 189-220 | Event/message veri sınıfları |
| `shutdown()` | 435-457 | Temizlik (bridge, lobby leave, state reset) |
| `create_lobby()` | 464-490 | Lobi oluşturma (Invisible/Public type) |
| `join_lobby()` | 496-503 | Lobiye katılma |
| `set_lobby_data()` | 564-570 | Lobi metadata yazma |
| `get_lobby_data()` | 572-579 | Lobi metadata okuma |
| `send()` | 650-664 | JSON P2P mesaj gönderimi (reliable/unreliable) |
| `send_board_state()` | 674-677 | Board snapshot gönder (unreliable) — co-op format adaptasyonu lazım |
| `send_piece_position()` | 679-692 | Parça pozisyonu gönder (unreliable) |
| `send_game_start()` | 700-709 | Oyun başlat mesajı (reliable) — co-op payload genişletilecek |
| `send_ready()` | 711-713 | Hazır sinyali (reliable) |
| `send_game_over()` | 715-722 | Oyun bitti sinyali (reliable) |
| `on()` event handler | 726-730 | Olay dinleyicisi kaydı |
| `tick()` | 743-769 | Frame-başı polling (callbacks + events + messages) |
| `is_host` property | 385-386 | Host/guest ayrımı — co-op'ta doğrudan kullanılır |
| `_TICK_ERROR_THRESHOLD = 5` | 345 | Ardışık hata sonrası networking devre dışı |

**Co-op için eklenecek yeni `MsgType` sabitleri** (mevcut `MsgType` sınıfına):
```python
# Online Co-op ek mesaj tipleri
GUEST_INPUT     = 'guest_input'
PIECE_STATE     = 'piece_state'
LOCK_EVENT      = 'lock_event'
GAME_EVENT      = 'game_event'
OBJECTIVE_STATE = 'objective_state'
```

### 18.2 `src/online_pvp_game.py` — Kısmen Yeniden Kullanılabilir

#### Doğrudan Kopyalanabilir Bloklar

| Yapı | Satır | Açıklama |
|------|-------|----------|
| `OnlineState` enum | 228-235 | Durum makinesi durumları — co-op için birebir aynı |
| `_init_networking()` | 861-910 | Bridge başlatma, pump pause, event handler kaydı |
| `_on_lobby_created()` | 918-945 | Lobi oluşturuldu handler (kod üretimi, metadata set) |
| `_create_lobby()` | 947-950 | Lobi oluşturma isteği |
| `_start_countdown()` | 2536-2546 | 3-2-1 geri sayım başlatma |
| `_generate_pieces()` | 2519-2534 | Deterministik parça dizisi üretimi (seed-based 7-bag×3) |
| `_validate_grid()` | 2315-2326 | Board grid boyut doğrulama |
| `_clamp_int()` | 1795-1806 | Güvenlik: alan değeri sınırlama |
| `_cleanup()` | 5942-5987 | Net shutdown + pump resume + state temizliği |
| Disconnect grace timer | 450, 984-995 | 5000ms bağlantı kopması toleransı |
| Session ping backoff | 439-441, 1015-1018 | Exponential backoff (500ms → 4000ms) |
| `STATE_SNAPSHOT_INTERVAL = 100` | 431 | Board snapshot gönderim aralığı |

#### Adapte Edilecek Bloklar

| Yapı | Satır | Ne Değişecek |
|------|-------|-------------|
| `_check_both_ready()` | 2484-2518 | game_start payload'una co-op bag'leri + level config eklenmeli |
| `_start_game()` | 2547-2620 | `Board()` yerine `CoopBoard()`, 2 oyuncu parça spawn |
| `_send_board_snapshot()` | 3220-3268 | 10×20 → 20×20, owners grid eklenmeli |
| `_send_piece_position()` | 3269-3285 | Tek parça → 2 parça (P1+P2) + ghost_y |
| `_process_messages()` | 2328-2480 | PvP mesaj türleri → co-op mesaj türleri |

#### Lobi UI Çizim Kodları (Referans)

| Çizim fonksiyonu | Satır | Açıklama |
|-----------------|-------|----------|
| `_draw_lobby_menu()` | 4422-4778 | Ana lobi menüsü (oluştur/katıl/liste) |
| `_draw_join_code_input()` | 4779-4869 | Kod girişi UI |
| `_draw_waiting_screen()` | 4870-5016 | Bekleme ekranı (kod gösterimi) |
| `_draw_ready_check()` | 5017-5160 | Ready check UI |
| `_draw_countdown()` | 5161-5191 | 3-2-1 geri sayım animasyonu |
| `_draw_game_over_overlay()` | 5715-5911 | Oyun sonu ekranı |
| `_draw_disconnected()` | 5912-5941 | Bağlantı koptu ekranı |
| `_draw_pause_overlay()` | 5415-5451 | Duraklama menüsü |

#### Panel Çizim Yardımcıları (Ortak Reuse Katmanı)

| Yardımcı | Dosya / Satır | Kullanım |
|----------|---------------|----------|
| `get_font()` | `retro_style.py:393` | Başlık, alt başlık, badge fontları |
| `get_fitting_font()` | `retro_style.py:481` | Bekleme ekranı gibi dinamik başlıklarda |
| `draw_glass_panel()` | `retro_style.py:727` | Tüm cam panel arka planları |
| `draw_uniform_button()` | `retro_style.py:1069` | Lobi aksiyon butonları, copy/invite/ready butonları |

#### Online Co-op Ekran Shell Planı

`online_pvp_game.py` içindeki online-shell çizimleri, online co-op için şu şekilde adapte edilmeli:

| Hedef ekran | PvP referansı | Reuse seviyesi | Not |
|-------------|---------------|----------------|-----|
| Giriş / Lobi menüsü | `_draw_lobby_menu()` | Yüksek | Buton aksiyonları co-op'a çevrilir |
| Kod ile katıl | `_draw_join_code_input()` | Çok yüksek | Metin/localization değişir |
| Bekleme ekranı | `_draw_waiting_screen()` | Çok yüksek | Başlık ve geri aksiyonu değişir |
| Hazır ekranı | `_draw_ready_check()` | Yüksek | VS başlığı co-op semantiğine çevrilir |
| Geri sayım | `_draw_countdown()` | Çok yüksek | Neredeyse aynen kullanılır |
| Bağlantı koptu | `_draw_disconnected()` | Çok yüksek | Metinler co-op'a çevrilir |

**Not:** Bu UI blokları ~2400 satırlık çizim kodu içerir. Co-op versiyonunda:
- Renk teması değişecek (kırmızı/mavi → yeşil/turkuaz)
- "Rakip" metinleri → "Takım arkadaşı" olacak
- Mod seçici (Endless/Campaign) eklenecek
- Level seçim entegrasyonu eklenecek

### 18.3 `src/coop_game.py` — Küçük Modifikasyon Gerekli

#### Doğrudan Kullanılacak (Değişiklik Yok)

Tüm oyun fiziği, çizim, HUD, pause menüsü, parçacık efektleri → **host tarafında birebir çalışacak**.

| Yapı | Satır | Açıklama |
|------|-------|----------|
| `__init__()` | 141+ | Tüm state başlatma |
| `_resolve_controls()` | 365 | Yerel ile aynı kontrol çözümleme |
| `_ensure_pause_settings_screen()` | 410 | Pause içi ayar ekranı |
| `_sync_runtime_settings_from_manager()` | 433 | Runtime ayar sync |
| `restart()` | 921 | Aynı config ile hızlı restart |
| `handle_input()` | 1744 | Yerel input işleme |
| `update()` | 1930 | Fizik, gravity, DAS, soft drop, lock delay |
| `_render_game()` | 2191 | Oyun içi ana render pipeline |
| `draw()` | 2371 | Frame render entry point |
| `_calculate_layout()` | 2380 | Board ve panel yerleşimi |
| `_draw_grid()` | 2412 | Grid çizimi |
| `_draw_locked_blocks()` | 2428 | Kilitli bloklar |
| `_draw_piece()` | 2458 | Aktif parça |
| `_draw_ghost()` | 2488 | Ghost piece |
| `_draw_hud()` | 2541 | Skor, süre, katkı HUD'u |
| `_draw_side_panels()` | 2596 | Hold / next kartları |
| `_draw_freeze_overlay()` | 2709 | Donma overlay |
| `_draw_pause_menu()` | 2740 | Duraklama menüsü |
| `_draw_game_over_screen()` | 2840 | Oyun sonu ekranı |
| `trigger_screen_shake()` | 1120 | Screen shake |
| `create_lock_explosion()` | 1132 | Lock patlama efekti |
| `draw_particles()` | 1189 | Parçacık render |
| `draw_ambient_particles()` | 1231 | Ambiyans parçacıkları |
| `create_drop_trail()` | 1249 | Hard drop trail |

**Görsel parite açısından kritik karar:**
- Oyun içi online co-op ekranı bu çizim zincirini reuse etmeli.
- `online_pvp_game.py` içindeki in-match çizim zinciri yalnızca lobi/pause/disconnected gibi online-spesifik yüzeylerde referans alınmalı.
- Eğer guest tarafında tam `CoopGame` instance kullanılamıyorsa, yukarıdaki render fonksiyonları shared renderer/mixin olarak ayrılmalı.

#### Eklenecek: Input Injection API

Host tarafında P2 input'unu network'ten alabilmek için `coop_game.py`'ye eklenecek tek şey:

```python
def inject_remote_input(self, player: str, action: str) -> bool:
    """Network'ten gelen input'u oyun motoruna enjekte et.
    
    Args:
        player: 'P1' veya 'P2'
        action: 'move_left' | 'move_right' | 'rotate' | 'hard_drop' |
                'soft_drop_start' | 'soft_drop_stop' | 'hold' |
                'das_start_left' | 'das_start_right' | 'das_stop'
    Returns:
        True başarılı, False başarısız (frozen, game over, vb.)
    """
    if action == 'move_left':
        return self._try_move(player, -1)
    elif action == 'move_right':
        return self._try_move(player, 1)
    elif action == 'rotate':
        return self._try_rotate(player)
    elif action == 'hard_drop':
        self._hard_drop(player)
        return True
    elif action == 'soft_drop_start':
        # DAS ve soft drop state'lerini set et
        ...
    elif action == 'hold':
        self._use_shared_hold(player)
        return True
    return False
```

#### Eklenecek: Event Network Hook

Mevcut `_emit_event()` dinleyici listesi var. Host, online co-op'ta bir listener ekleyerek olayları ağa yönlendirebilir:

```python
# Host tarafında:
coop_game._event_listeners.append(self._on_coop_game_event)

def _on_coop_game_event(self, event_type: str, event_data: dict):
    """CoopGame olaylarını guest'e ilet."""
    self.net.send({'type': 'game_event', 'event': event_type, 'data': event_data}, reliable=True)
```

### 18.4 `src/coop_board.py` — Değişiklik Yok

Tüm board mantığı host tarafında çalışacak. Guest sadece host'tan gelen grid verisini render edecek.

| Yapı | Satır | Açıklama |
|------|-------|----------|
| `CoopBoard(Board)` | Tümü (122 satır) | 20×20 board, MIDLINE=10 |
| `is_valid_position_for_player()` | 39 | Pozisyon doğrulama (midline dahil) |
| `get_spawn_position()` | 59 | P1: (3, y), P2: (13, y) spawn |
| `lock_piece_for_player()` | 77 | Kilitleme + owner set |
| `clear_lines()` | 97 | Satır temizleme + p1/p2 hücre sayımı |

### 18.5 `src/main.py` — Entegrasyon Noktası

Mevcut online PvP entegrasyonu referans alınacak:

| Yapı | Satır | Açıklama |
|------|-------|----------|
| PvP import | 150, 188 | `from .online_pvp_game import OnlinePvPGame` |
| Menü action handler | 1982-1997 | `elif action in ('online_pvp', 'Online PvP')` |
| Mode intro popup | 1983 | `_run_popup_and_sync_screen(_show_mode_intro_popup, ...)` |
| Game instance oluşturma | 1988-1996 | `OnlinePvPGame(screen=..., ...)` |
| State set | 1997 | `state = 'online_pvp'` |
| `_handle_online_pvp()` | 2942-3020 | Oyun döngüsü: handle_input → update → draw |
| Cleanup on error | 2956, 2965, 2984 | `online_pvp._cleanup()` |
| Screen resize forwarding | 2976-2979 | Window boyut senkronizasyonu |

**Co-op için kopyalanacak pattern:**
```python
# main.py'ye eklenecek (satır ~2000 civarı):
elif action in ('online_coop', 'Online Co-op'):
    if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'online_coop', ...):
        continue
    online_coop_game = OnlineCoopGame(
        screen=screen, fullscreen=fullscreen,
        user_manager=user_manager, settings_manager=settings_manager,
        sound_manager=menu_sound,
    )
    _handle_online_coop._game = online_coop_game
    state = 'online_coop'

# Ve yeni handler (satır ~3020 sonrası):
def _handle_online_coop(delta_ms):
    # _handle_online_pvp() ile birebir aynı yapı
    ...
```

### 18.6 Kampanya Sistemi — Değişiklik Yok

| Dosya | Satır | Açıklama |
|-------|-------|----------|
| `campaign/coop_campaign_mode.py` | 621 | Host tarafında birebir çalışır |
| `campaign/coop_level_data.py` | 304 | 20 level konfigürasyonu — değişmez |
| `campaign/coop_objectives.py` | 189 | Hedef sınıfları — değişmez |
| `campaign/coop_level_select.py` | 329 | Host tarafında level seçimi — online adaptasyon lazım |

### 18.7 Özet: Değişiklik Matrisi

| Dosya | Değişiklik | Kapsam |
|-------|-----------|--------|
| `src/steam_networking.py` | `MsgType`'a 5 yeni sabit ekle | 5 satır |
| `src/coop_game.py` | `inject_remote_input()` metodu ekle | ~40 satır |
| `src/main.py` | `_handle_online_coop()` + menü entegrasyonu | ~80 satır |
| `src/online_coop_game.py` | **YENİ DOSYA** — Ana online co-op modülü | ~2000-3000 satır |
| `src/localization.py` | Yeni çeviri anahtarları | ~20 satır |
| `src/menu.py` | "Online Co-op" dashboard tile | ~15 satır |

**Toplam tahmini yeni/değişen kod:** ~2200-3200 satır
**Mevcut koddan yeniden kullanılan:** ~4000+ satır (coop_game + networking + board + kampanya)

---

## Ekler

### Ek A: Mevcut CoopGame Event Flow Diyagramı

```
                    ┌──────────────┐
                    │  CoopGame    │
                    │  .update()   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        P1 Gravity    P2 Gravity    DAS/Soft Drop
              │            │            │
              ▼            ▼            ▼
        _step_piece_down  _step_piece_down  _try_move/_try_rotate
              │            │
       (grounded?)   (grounded?)
              │            │
              ▼            ▼
        Lock Timer    Lock Timer
              │            │
       (timer >= delay?) (timer >= delay?)
              │            │
              ▼            ▼
     _lock_and_new_piece  _lock_and_new_piece
              │            │
              ├─ lock_piece_for_player()
              ├─ clear_lines()
              ├─ score update
              ├─ level/speed update
              ├─ _emit_event() ──────► Listeners (Campaign)
              ├─ _try_unfreeze_players()
              └─ _try_spawn_for_player()
```

### Ek B: Online Mesaj Akış Diyagramı (Önerilen)

```
HOST                                    GUEST
 │                                        │
 │ ◄──── guest_ready ───────────────────  │
 │ ────── host_ready ──────────────────►  │
 │                                        │
 │ ────── game_start{seed,pieces,cfg}──►  │
 │                                        │
 │ ═══════ PLAYING ═══════════════════    │
 │                                        │
 │ ◄──── guest_input{move_left,seq:1} ── │
 │ (host uygular, P2 sola kayar)        │
 │                                        │
 │ ──── piece_state{p2:{x:13},ack:1} ──► │
 │                                        │
 │ (P1 lokal: parça kilitledi)           │
 │ ──── lock_event{P1,cleared:[18]}────► │
 │ ──── board_state{grid,score,...} ───► │
 │                                        │
 │ ◄──── guest_input{hard_drop,seq:2} ── │
 │ (host P2 hard drop uygular)          │
 │ ──── lock_event{P2,cleared:[17,18]}─► │
 │                                        │
 │ (her 100ms)                           │
 │ ──── board_state{...} ──────────────► │
 │ ──── piece_state{...} ──────────────► │ 
 │                                        │
 │ (İkisi de freeze → game over)         │
 │ ──── game_event{game_over,...} ─────► │
 │                                        │
```

### Ek C: Hızlı Bileşen Özet Tablosu

> Detaylı satır referansları için bkz. [Bölüm 18](#18-mevcut-kodda-yeniden-kullanılabilecek-yapılar-detaylı-satır-referansları)

| Bileşen | Durum | Değişiklik |
|---------|-------|-----------|
| SteamNetworking + SteamNetBridge | ✅ %100 reuse | MsgType'a 5 sabit ekle |
| CoopGame (3129 satır) | ✅ %99 reuse | inject_remote_input() ekle (~40 satır) |
| CoopBoard (122 satır) | ✅ %100 reuse | Değişiklik yok |
| Kampanya sistemi (1143 satır) | ✅ %100 reuse | Değişiklik yok |
| OnlinePvPGame (5987 satır) | ⚠️ Kısmi reuse | State machine, lobi UI, networking init kopyalanacak |
| main.py entegrasyonu | ⚠️ Kısmi reuse | _handle_online_pvp() pattern'i kopyalanacak |
