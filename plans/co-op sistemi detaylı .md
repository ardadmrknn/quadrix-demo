# QUADRIX Co-op Modu — Detaylı Tasarım Belgesi

**Versiyon:** 1.0  
**Tarih:** 21.03.2026  
**Statü:** Final Tasarım  
**Format:** Markdown

---

## 📑 İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Temel Mekanikler](#temel-mekanikler)
3. [Oyun Kuralları](#oyun-kuralları)
4. [UI/UX Tasarımı](#uiux-tasarımı)
5. [Teknik Mimarı](#teknik-mimarı)
6. [Geliştirilecek Dosyalar](#geliştirilecek-dosyalar)
7. [Geliştirme Sırası](#geliştirme-sırası)

---

## 🎮 Genel Bakış

### Konsept

QUADRIX Co-op Modu, iki oyuncuyu **20 sütunlu ortak bir oyun alanına** yerleştirerek tasarlanmış bir kooperatif puzzle oyunudur. Sol taraf (10 sütun) Oyuncu 1, sağ taraf (10 sütun) Oyuncu 2 tarafından kontrol edilir. Satırlar yalnızca tüm 20 hücre dolduğunda temizlenir — bu mekanik doğal olarak **iletişim, koordinasyon ve karşılıklı bağımlılık** yaratır.

### Hedef Kitle

- Arkadaşlarla aynı cihazda oynayan casual oyuncular
- Online co-op'u Steam üzerinden deneyimlemek isteyenler
- Takım çalışmasını önemseyen oyun grupları

### Oyun Süresi

- **Sonsuz Mod:** 5-30 dakika
- **Kampanya Hedefleri:** 3-10 dakika per seviye

---

## 🕹️ Temel Mekanikler

### 1. Oyun Alanı

```
┌─────────────────────────────────────────┐
│   P1 (10 sütun)   │   P2 (10 sütun)    │
│                   │                     │
│  [████████░░]     │  [░░████████]       │
│  [██████░░░░]     │  [██░░░░░░░░]       │
│  [████████████]   │  [████████████]     │ ← 20/20 dolu!
├─────────────────┼─────────────────┤
│ P1: 3 satır hazır │ P2: 3 satır hazır │
└─────────────────────────────────────────┘
```

- **Toplam:** 20 sütun × satır sayısı normal oyun alanındaki satır sayısı olacak
- **P1 Bölgesi:** Sütun 1-10
- **P2 Bölgesi:** Sütun 11-20
- **Orta Çizgi:** Ince ve belirgin divider

### 2. Satır Temizleme Mantığı

Bir satır **yalnızca tüm 20 hücre doluysa** temizlenir:

```
Satır Durumu                  Sonuç
─────────────────────────────────────────
│████████████│░░░░░░░░░░│   → Temizlenmez
│████████████│██████████│   → ✅ TEMİZLENİR
│░░░░░░░░░░│██████████│   → Temizlenmez
```

**Skor Hesabı:**
- 1 satır temizleme: 100 puan (Team Score + Bireysel katkı kaydedilir)
- 2 satır aynı anda: 300 puan (senkron bonus +100)
- 3 satır: 500 puan
- 4 satır: 800 puan

---

## 📋 Oyun Kuralları

### Kural 1: Dondurma Sistemi

**Durum:** Oyuncu 2'nin tahtası doldu (20 satır)

```
T=0s    : P2 son parçasını yerleştirdi
T=0.5s  : P2 tahtası tamamen dolu → DONDURULDU
          • P2'nin ekranında "Waiting for P1..." yazar
          • P2'ye yeni parça GELMİYOR
          • P2 input almıyor (tuşlar çalışmıyor)

T=5s    : P1 kendi yarısını doldurup satırı temizledi
T=5.5s  : Satır temizlendi → P2'nin tahtasında boşluk oluştu
          • P2 dondurma kurtuldu → eline parça geliyor
          • P2 yeniden kontrol alıyor
```

**Teknik Detay:**
```python
# CoopGame._check_freeze_status() içinde
def _check_freeze_status(self) -> None:
    if self._is_player_section_full(player=1):
        self.board.p1_frozen = True
    if self._is_player_section_full(player=2):
        self.board.p2_frozen = True

def _is_player_section_full(self, player: int) -> bool:
    """Oyuncunun bölgesindeki en üst satırda dolu hücre var mı?"""
    cols = self.board.P1_COLS if player == 1 else self.board.P2_COLS
    return any(self.board.occupancy[0][col] for col in cols)
```

### Kural 2: Parça Sınırı (Sert Sınır)

Parçalar **orta çizgide kesin olarak durur** — karşı tarafa hiçbir şekilde geçemez:

```
Parça: L-Tetromino (P1'de)
├─ Sütun 8, 9 doldururken 10'a ulaşmaya çalışırsa
└─ DUVARA ÇARPAR → Sütun 10'a geçemez

Sonuç: Parça rotasyon/hareket yapamaz, geçersiz konumdadır
```

### Kural 3: Parça Dağılımı (Bağımsız)

P1 ve P2 **tamamen farklı rastgele parça sıraları** alır:

```
Sıra    P1 Parçası    P2 Parçası
────────────────────────────────
1       I (Çubuk)     Z (Zikzak)
2       O (Kare)      T (T-şekli)
3       L (L-şekli)   S (S-şekli)
...     ...           ...
```

**Avantaj:** Oyuncuların farklı stratejileri öğrenmesi, farklı zorluklar yaşaması daha organik co-op hissini yaratır.

### Kural 4: Hız Sistemi (Aynı Hız)

Her iki oyuncu **aynı seviyede hızlanır:**

```
Temizlenen Satır    Seviye    Düşüş Hızı (ms)
─────────────────────────────────────────────
0-10                1         800ms
11-30               2         700ms
31-60               3         600ms
...
```

Her oyuncu kendi satır sayısını izlerken, **hız global**dir. Biri daha hızlı temizlese bile diğeri yavaşlamaz.

### Kural 5: Skor Sistemi (Hibrit)

```
Ekranda Gösterilen:

╔════════════════════════════════════╗
║       TEAM SCORE: 2,400            ║
╠════════════════════════════════════╣
║ P1 Katkı: 1,200 (50%)              ║
║ P2 Katkı: 1,200 (50%)              ║
╚════════════════════════════════════╝
```

**Hesaplama:**
- Satır temizlenmesi = +100 puan / satır
- Her iki oyuncu da eşit kredisi alır (doldurdukları sütunları sayar)
- Bireysel katkı oranı = (P1 dolu sütun sayısı / 10) × toplam skor

---

## 🎨 UI/UX Tasarımı

### 1. Ana Oyun Ekranı

```
┌────────────────────────────────────────────────────┐
│  QUADRIX CO-OP  |  Level: 2  |  Time: 3:45         │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ P1 SCORE: 1,200  │  TEAM: 2,400  │  P2: 1,200
│  ├──────────┬───────┼───────┬────────┤           │
│  │          │       │       │        │           │
│  │  ████    │  ███  │ ████  │  ████  │           │
│  │ ████░    │ ░█████ │  ███░ │ ░████  │           │
│  │████░░░  │ ░░████ │ ░░███ │ ░░███░ │           │
│  │          │       │ (P2 bekleniyor)            │
│  └──────────┴───────┼───────┴────────┘           │
│  Next P1: [I]       │  Next P2: [Z]              │
│  Hold: [O]          │  Hold: [T]                 │
└────────────────────────────────────────────────────┘
```

### 2. Dondurma Ekranı (P2 Dolu)

```
┌────────────────────────────────────────────────────┐
│  P2 WAITING FOR P1                                 │
├────────────────────────────────────────────────────┤
│  P2'nin tahtası TAMAMEN DOLU                       │
│                                                    │
│  ⏳ P1 1 daha satır temizlemeli...                │
│                                                    │
│  [Animasyonlu pulse efekti]                        │
│  "Come on P1!" sesi (opsiyonel)                    │
└────────────────────────────────────────────────────┘
```

### 3. Satır Temizleme Animasyonu

```
Seçenek A: Orta çizgiden patla
├─ Satır 15 de 20 hücre dolmuş
├─ Orta çizgiden başlayarak iki tarafa açılan efekt
└─ "SYNCED!" yazısı ekrana patlayan partiküller ile

Seçenek B: Takım kutlaması
├─ Her iki tarafta da farklı renkli flash
├─ Ses: Güçlü drum + cheering
└─ +100 combo bonus göstergesi
```

### 4. Minimal Görsel Ayırım

- **Orta çizgi:** İnce, gri veya açık renkli divider (5-10px)
- **Blok renkleri:** Her iki tarafta da aynı (Tetris standart 7 renk)
- **Arka plan:** Birleşik, her iki tarafta da aynı
- **Hiçbir renk tonlama:** P1'i mavi, P2'yi kırmızı yapmuyoruz

---

## 🏗️ Teknik Mimarı

### Mimarı Diyagramı

```
┌─────────────────────────────────────────────────┐
│           coop_game.py  (CoopGame)              │
│  (Ana oyun döngüsü, dondurma mantığı,           │
│   team score, input yönetimi)                   │
└────────┬───────────────────────────────┬────────┘
         │                               │
    ┌────▼─────────┐        ┌────────────▼────┐
    │ coop_board.py│        │ coop_renderer.py│
    │ (CoopBoard)  │        │ (Render logic,  │
    │ width=20     │        │  orta çizgi,    │
    │ Board extend)│        │  freeze overlay)│
    └──────────────┘        └─────────────────┘
         │
         ├──► board.py          (Board — base class, width parametresiyle)
         ├──► pieces.py         (Piece, create_piece_by_index, SHAPES)
         ├──► constants.py      (BOARD_HEIGHT, COLORS, BLACK...)
         ├──► sound.py          (SoundManager — ses geri bildirimi)
         ├──► localization.py   (t() — çeviri fonksiyonu)
         ├──► retro_style.py    (draw_glass_panel, get_font)
         ├──► ui_theme.py       (UIFonts, UIColors)
         ├──► gamepad_manager.py (İki oyuncu input)
         └──► platform_utils.py  (create_display, normalize_mouse_pos)
```

> **Önemli:** `CoopGame` doğrudan `object`'ten türetilecek. `PvPGame`'den miras almak **yanlıştır** — `PvPGame` 2 ayrı `Board`, eleme sistemi ve VS paneli başlatır; bunların hiçbiri co-op'ta gerekmez. `PvPGame`'in ortak utility metodları (`_ui_scale`, `_sx`, ses yönetimi) `CoopGame` içine kopyalanacak.

### Sınıf Yapısı

```python
# ───────────────────────────────────────
# src/coop_board.py
# ───────────────────────────────────────
from board import Board
from constants import BLACK

class CoopBoard(Board):
    """20 sütunlu co-op oyun tahtası.
    
    P1 bölgesi: sütun 0-9
    P2 bölgesi: sütun 10-19
    Satır yalnızca tüm 20 hücre doluysa temizlenir.
    """
    TOTAL_COLS: int = 20
    P1_COLS: range = range(0, 10)
    P2_COLS: range = range(10, 20)

    def __init__(self) -> None:
        # Board.__init__ width/height parametrelerini zaten destekliyor.
        # super() çağrısı tüm grid'leri (occupancy, texture_grid, gold,
        # owners...) doğru şekilde başlatır.
        super().__init__(width=20, height=20)
        self.p1_frozen: bool = False
        self.p2_frozen: bool = False

    def is_valid_position(self, piece, dx: int = 0, dy: int = 0,
                          player: int = 0) -> bool:
        """Parça sınır kontrolü — player verilmişse bölge sınırı da kontrol edilir.
        
        Board.is_valid_position imzasıyla uyumlu (dx, dy).
        Ek player parametresi orta çizgiyi zorlar.
        """
        if player != 0:
            allowed_cols = self.P1_COLS if player == 1 else self.P2_COLS
            # piece.get_cells() -> [(abs_x, abs_y), ...]
            for px, py in piece.get_cells():
                if (px + dx) not in allowed_cols:
                    return False
        # Zemin/occupancy kontrolü üst sınıfa bırakılır
        return super().is_valid_position(piece, dx, dy)

    # Board.clear_lines() width=20 üzerinden çalışacağı için
    # override GEREKMİYOR. Mevcut cascade loop doğru çalışır.


# ───────────────────────────────────────
# src/coop_game.py  (iskelet)
# ───────────────────────────────────────
from coop_board import CoopBoard
from pieces import Piece, create_piece_by_index
from sound import SoundManager
from localization import t
from ui_theme import UIFonts
import random

class CoopGame:
    """Co-op oyun döngüsü — PvPGame'den değil object'ten türer."""

    def __init__(self, screen, sound_manager=None,
                 settings_manager=None) -> None:
        self.screen = screen
        self.settings_manager = settings_manager
        self.sound: SoundManager = sound_manager or SoundManager()

        # Tek ortak tahta (20 sütun)
        self.board = CoopBoard()

        # Birbirinden bağımsız parça sıraları
        self.p1_current_piece: Piece | None = self._spawn_piece(player=1)
        self.p1_next_piece:    Piece | None = self._spawn_piece(player=1)
        self.p2_current_piece: Piece | None = self._spawn_piece(player=2)
        self.p2_next_piece:    Piece | None = self._spawn_piece(player=2)

        # Skor
        self.team_score: int = 0
        self.p1_contribution: int = 0  # Bireysel katkı (puan bazlı)
        self.p2_contribution: int = 0

        # Oyun durumu
        self.game_over: bool = False
        self.paused: bool = False

        # Zamanlama
        self.fall_time_p1: int = 0
        self.fall_time_p2: int = 0
        self.fall_speed:   int = 800  # ms — her iki oyuncu aynı global hız

    # ── Parça üretimi ─────────────────────────────────────
    def _spawn_piece(self, player: int) -> Piece:
        """Oyuncunun bölgesinde merkeze konumlanmış yeni parça."""
        start_x = 3 if player == 1 else 13  # P1: 0-9, P2: 10-19
        idx = random.randint(0, 6)
        return create_piece_by_index(idx, x=start_x, y=0)

    # ── Dondurma mantığı ──────────────────────────────────
    def _is_player_section_full(self, player: int) -> bool:
        """Oyuncunun bölgesinin en üst satırında dolu hücre var mı?"""
        cols = self.board.P1_COLS if player == 1 else self.board.P2_COLS
        return any(self.board.occupancy[0][col] for col in cols)

    def _check_freeze_status(self) -> None:
        if self._is_player_section_full(player=1):
            self.board.p1_frozen = True
        if self._is_player_section_full(player=2):
            self.board.p2_frozen = True

    def _apply_unfreeze_if_needed(self) -> None:
        """Satır temizlendikten sonra donmuş oyuncuyu kurtarır."""
        if self.board.p1_frozen and not self._is_player_section_full(1):
            self.board.p1_frozen = False
        if self.board.p2_frozen and not self._is_player_section_full(2):
            self.board.p2_frozen = False

    # ── Skor ─────────────────────────────────────────────
    @staticmethod
    def _calc_score(cleared: int, level: int = 1) -> int:
        """Nintendo Guideline benzeri puan hesabı."""
        table = [0, 100, 300, 500, 800]
        return table[min(cleared, 4)] * level

    # ── Ana güncelleme döngüsü ────────────────────────────
    def update(self, dt_ms: int) -> None:
        """Her frame çağrılır. dt_ms = delta time milisaniye."""
        # P1 düşüş
        if not self.board.p1_frozen:
            self.fall_time_p1 += dt_ms
            if self.fall_time_p1 >= self.fall_speed:
                self.fall_time_p1 = 0
                self._step_piece(player=1)

        # P2 düşüş (dondurulmamışsa)
        if not self.board.p2_frozen:
            self.fall_time_p2 += dt_ms
            if self.fall_time_p2 >= self.fall_speed:
                self.fall_time_p2 = 0
                self._step_piece(player=2)

        # Satır temizleme (her iki oyuncudan sonra)
        cleared = self.board.clear_lines()   # Board.clear_lines() width=20 ile çalışır
        if cleared > 0:
            gained = self._calc_score(cleared)
            self.team_score += gained
            self._apply_unfreeze_if_needed()
            # Seviye = (toplam satır // 5) + 1 → Board otomatik hesaplar

    def _step_piece(self, player: int) -> None:
        """Parçayı bir adım aşağı düşür; zemine değdiyse kilitle."""
        piece = self.p1_current_piece if player == 1 else self.p2_current_piece
        if piece is None:
            return
        if self.board.is_valid_position(piece, dy=1, player=player):
            piece.y += 1
        else:
            self.board.lock_piece(piece)   # Board.lock_piece() → clear_lines'ı çağırır
            self._check_freeze_status()
            # Yeni parça üret
            if player == 1:
                self.p1_current_piece = self.p1_next_piece
                self.p1_next_piece    = self._spawn_piece(1)
            else:
                self.p2_current_piece = self.p2_next_piece
                self.p2_next_piece    = self._spawn_piece(2)
```

---

## 📁 Geliştirilecek Dosyalar

### Yeni Dosyalar

| Dosya | Amaç | Dayandığı API / Sınıf |
|---|---|---|
| `src/coop_board.py` | 20 sütunlu ortak tahta | `Board(width=20, height=20)` — `super().__init__()` ile |
| `src/coop_game.py` | Co-op oyun döngüsü | `object` — bağımsız, `PvPGame`'den türemez |
| `src/coop_renderer.py` | Co-op render pipeline | `retro_style.draw_glass_panel()`, `UIFonts`, `UIColors` |

> **Not:** Ayrı bir `CoopPlayer` sınıfına gerek yok. Parça durumu `CoopGame` içinde `p1_current_piece` / `p2_current_piece` alanları olarak tutulur. `Piece` ve `create_piece_by_index` doğrudan `pieces.py`'den kullanılır.

### Modifiye Edilecek Dosyalar

| Dosya | Değişiklik | İlgili Fonksiyon/Bölge |
|---|---|---|
| `src/menu.py` | "Co-op" mod kartı ekle | `_draw_main_dashboard_tile()`, `_menu_panel_content_scale()` |
| `src/game_modes.py` | `CoopMode` sınıfı/kaydı ekle | Dosyanın sonuna eklenir |
| `src/localization.py` | `coop_*` anahtar kelimeleri ekle | Her dil bloğuna (TR, EN, DE ...) |
| `src/campaign/objectives.py` | Co-op hedef tipleri ekle | `CoopSurvive`, `CoopClear`, `CoopSync` |
| `src/gamepad_manager.py` | Co-op tuş bağlaması | Mevcut `pvp` kontrol şeması yanına `coop` bloğu |
| `src/steam_networking.py` | Online co-op session | `PvPSession` benzeri `CoopSession` — bu dosya online altyapıyı barındırır |
| `src/ui_components.py` | Dondurma overlay bileşeni | `draw_freeze_overlay(screen, player, message)` |

---

## 🚀 Geliştirme Sırası

### Faz 1: Temel Mekanik (Hafta 1)

**Hedef:** Yerel 2 oyuncu koşu durumu

1. `coop_board.py` oluştur
   - 20 sütun grid
   - `is_valid_position()` — sert sınır kontrolü
   - `check_and_clear_rows()` — 20 hücre temizleme
   - Dondurma state'leri

2. `coop_player.py` oluştur
   - `player_id` (1 veya 2) ile kontrol
   - Kendi yarısını temsil etsin

3. `coop_game.py` oluştur
   - `PvPGame` fork'la
   - Dondurma mantığı
   - Team Score + bireysel katkı

**Test:** Bir oyuncu doldurmuş, diğeri tamamladığında satır temizlensin

### Faz 2: Render & UI (Hafta 1-2)

4. `coop_renderer.py` oluştur
   - Orta çizgi
   - İki oyuncu skoru (hibrit gösterim)
   - Orta çizgide satır temizleme animasyonu

5. `menu.py` genişlet
   - Main menu > Mode > Co-op Local/Online

6. `ui_components.py` ekle
   - "Waiting for P1/P2..." overlay

**Test:** Oyun visual olarak anlaşılır hale gelsin

### Faz 3: Yerel Input (Hafta 2)

7. Input binding
   - P1: OK tuşları (↑ dönüş, ← sola, → sağa, ↓ aşağı)
   - P2: WASD (W dönüş, A sola, D sağa, S aşağı)
   - `gamepad_manager.py` zaten var, gerek varsa tuş ataması özelleştir

**Test:** İki oyuncu aynı klavyeden rahat oynasın

### Faz 4: Kampanya & Hedefler (Hafta 2-3)

8. `campaign/objectives.py` genişlet
   - `CoopSurvive(duration=120)` — 2 dakika hayatta kal
   - `CoopClear(count=10)` — 10 satır temizle
   - `CoopSync(count=5)` — 5 kez senkronize temizle

9. Campaign level'ları oluştur
   - Co-op Easy: 5 satır temizle
   - Co-op Normal: 10 satır / 3 dakika
   - Co-op Hard: 20 satır / dayanma

**Test:** Hedefler düzgün tetiklenir, yıldız sistemi çalışır

### Faz 5: Online Co-op (Hafta 3-4)

10. `steam_networking.py` genişlet
    - Mevcut `PvPSession` altyapısını incele, benzer `CoopSession` sınıfı ekle
    - `online_pvp_game.py`'den **fork alma** — sadece networking katmanını al
    - Her frame'de P1/P2 parça state'ini karşı tarafa gönder (parça tipi, x, y, rotasyon)
    - Dondurma sinyali ayrıca iletilmeli: `frozen_player: int | None`

11. Steam entegrasyon (`steam_integration.py` + `steam_networking.py`)
    - Co-op session invite (mevcut `invite` fonksiyonu genişletilir)
    - P1/P2 rol atamı: lobi sahibi P1, davet edilen P2
    - Senkronizasyon testi: 200ms+ gecikme senaryosu

**Test:** Arkadaşla internet üzerinden oynayın; dondurma state'i her iki tarafta senkronize görünmeli

### Faz 6: Ses & Feedback (Hafta 4)

12. `sound.py` genişlet
    - Dondurma sesi (P2'ye "hızlan" sinyali)
    - Satır temizleme (senkronize)
    - Team bonus (combo ses)

**Test:** Ses geri bildirimi tam hissi tamamlasın

### Faz 7: Polish & Balans (Hafta 4-5)

13. Playtest & bug fix
14. Skor dengeleme
15. Hız eğrisini test
16. Steam achievement entegrasyonu (opsiyonel)

---

## 📊 Tasarım Kararları Özeti

| Soru | Cevap | Karar |
|------|-------|-------|
| Kaybetme koşulu | Ortak can barı | P2 dolarsa dondurulur |
| Dondurma mekanizmi | Tam dondurma | Input + parça durdurulur |
| Parça sınırı | Sert sınır | Orta çizgide duvar |
| Skor sistemi | Hibrit | Team + bireysel katkı |
| Hız sistemi | Aynı hız | Her iki oyuncu seviyelenir |
| Mod yapısı | İkisi de | Sonsuz + kampanya hedefleri |
| Online | Evet | Yerel + Steam online |
| Görsel | Minimal | Ince çizgi, aynı renkler |
| Parça dağılımı | Bağımsız | Farklı rastgele sıralar |
| Kontrol (local) | Tek klavye | P1: OK tuşları, P2: WASD |

---

## 🎯 Başarı Kriterleri

Co-op modu aşağıdaki durumlarda **başarılı** kabul edilir:

- ✅ İki oyuncu sorunsuz lokal oyun oynayabiliyor
- ✅ Dondurma mekanizmi düzgün çalışıyor (visual feedback net)
- ✅ Satır temizleme animasyonu tatmin edici
- ✅ Team Score doğru hesaplanıyor
- ✅ Kampanya hedefleri co-op için kullanılabiliyor
- ✅ Steam online session'ında senkronizasyon sorunsuz
- ✅ Playtest sonrası oynanış **eğlenceli ve stresli** (iyi şekilde)

---

## 📝 Notlar

- **Performans:** 20 sütun x 20 satır = 400 hücre. Standart 10x20'den iki kat — optimizasyon gerekebilir.
- **Ağ Gecikmesi:** Online'da senkronizasyon kritik; mevcut Steam networking test edilmeli.
- **UI Ölçekleme:** 20 sütun ekranda yer kaplar — Quadrix'teki responsive ölçekleme formülleri ayarlanmalı.
- **Ses Tasarımı:** Dondurma feedback'i oyunu heyecanlı kılacak — ses önemli.

---

**Belge Sonu**