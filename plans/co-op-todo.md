# QUADRIX Co-op Modu — Uygulama Todo Listesi

**Oluşturulma:** 09.04.2026  
**Referans:** `plans/co-op sistemi detaylı .md` (V1.1)  
**Yaklaşım:** PvP akışını temel alan coop fork  

---

## Genel Kural

Her faz bittiğinde **Faz Sonu İnceleme** adımı çalıştırılır:

- Hatalı kod var mı? (logic bug, off-by-one, yanlış koşul)
- Eksik kod var mı? (edge case, unhandled state, missing return)
- Yanlış kod var mı? (tasarıma uymayan davranış, kopyala-yapıştır artığı)
- Gereksiz kod var mı? (dead code, kullanılmayan import, PvP'den kalan rekabet mantığı)
- Testler geçiyor mu? (`./scripts/test/run_tests.sh -q`)

İnceleme sonucu bulunan her sorun o faz içinde düzeltilir, sonraki faza geçilmez.

---

## FAZ 0 — Hazırlık ve Altyapı Kontrolü

### 0.1 Mevcut Board genişlik desteğini doğrula
- [ ] `src/board.py` → `__init__` imzasında `width` parametresinin 20 ile çalıştığını teyit et
- [ ] `Board(width=20, height=20)` ile bir test board oluştur, `grid`, `occupancy`, `owners` boyutlarının 20×20 olduğunu doğrula
- [ ] `clear_lines()` mantığının width=20'de düzgün çalıştığını doğrula (satır silme, gravity)

### 0.2 PvP akışını anla ve referans noktalarını işaretle
- [ ] `src/pvp_game.py` → `__init__` yapısını oku: `board1/board2`, `current_piece1/2`, `next_piece1/2`, `fall_time1/2`, `fall_speed1/2`
- [ ] `handle_input()` → iki oyunculu input akışını oku: `_resolve_pvp_controls()`, DAS sistemi, soft drop
- [ ] `update()` → per-player gravity tick mantığını oku: `fall_time` accumulator, `lock_and_new_piece(player_num)`
- [ ] `draw()` → çift board render'ını oku: `calculate_board_positions()`, header, center panel
- [ ] `lock_and_new_piece()` → parça kilitleme + yeni spawn akışını oku
- [ ] Pause menü akışını oku: ESC/P toggle, `_handle_pause_menu_input`, `_draw_pause_menu`

### 0.3 Parça sistemi referansını oku
- [ ] `src/pieces.py` → `Piece.__init__` imzası: `x=3, y=0, shape_index`
- [ ] `src/pieces.py` → `SHAPES`, `COLORS`, `SHAPE_NAMES` dizileri
- [ ] PvP'deki `generate_pieces()` ve `get_next_piece()` bag sistemi

### 0.4 Kontrol ayarlarını doğrula
- [ ] `src/settings_manager.py` → `DEFAULT_CONTROLS['pvp']` → P1 WASD, P2 yön tuşları yapısını teyit et
- [ ] PvP'nin `_resolve_pvp_controls()` içinde bu ayarları nasıl keycodes'a çevirdiğini oku
- [ ] Co-op'un aynı PvP control yapısını doğrudan kullanabileceğini onayla

### 0.5 Hold piece mevcut durumu
- [ ] `src/game.py` → `held_piece`, `can_hold` attr'lerini oku (tek oyuncu hold mantığı)
- [ ] PvP'de hold YOK olduğunu teyit et → co-op hold sıfırdan yazılacak
- [ ] Game.py'deki hold swap mantığını referans olarak işaretle (C tuşu, swap, `can_hold` flag)

### ✅ Faz 0 Sonu İnceleme
- [ ] Bu fazda kod değişikliği yok; sadece okuma ve doğrulama
- [ ] Herhangi bir varsayım yanlışsa tasarım belgesini güncelle
- [ ] Devam etmeden önce tüm referans noktaları netleşmiş olmalı

---

## FAZ 1 — CoopBoard Sınıfı (`src/coop_board.py`)

### 1.1 Dosya oluştur ve temel yapıyı kur
- [ ] `src/coop_board.py` oluştur
- [ ] `from src.board import Board` import et
- [ ] `CoopBoard` sınıfını tanımla, `Board`'dan miras al

### 1.2 `__init__` metodu
- [ ] `super().__init__(width=20, height=20)` çağır → 20 sütun, 20 satır
- [ ] `self.p1_columns = range(0, 10)` — P1 bölgesi
- [ ] `self.p2_columns = range(10, 20)` — P2 bölgesi
- [ ] `self.midline_col = 10` — orta çizgi sütun indeksi (P2 başlangıcı)

### 1.3 `is_valid_position_for_player(piece, player)` metodu
- [ ] Standart `is_valid_position` mantığını çağır (board sınırları + dolu hücre kontrolü)
- [ ] Ek olarak parçanın tüm hücrelerinin oyuncunun bölgesinde olduğunu kontrol et
- [ ] P1 → tüm hücreler `0 <= x < 10` olmalı
- [ ] P2 → tüm hücreler `10 <= x < 20` olmalı
- [ ] Hem hareket hem rotasyon bu fonksiyondan geçmeli

### 1.4 `get_spawn_position(player)` metodu
- [ ] P1 spawn: `x = 3, y = 0` (standart, sol taraf ortası)
- [ ] P2 spawn: `x = 13, y = 0` (sağ taraf ortası, 10 + 3)
- [ ] Parça genişliğine göre spawn x'in bölge içinde kalmasını garanti et

### 1.5 `can_spawn(player)` metodu
- [ ] Verilen oyuncu için spawn pozisyonunda `is_valid_position_for_player` çağır
- [ ] True dönerse parça spawn edilebilir, False dönerse oyuncu freeze olmalı
- [ ] Bu metot freeze kararının tek kaynağı olacak

### 1.6 `clear_lines()` override
- [ ] `super().clear_lines()` çağır — mevcut 20 sütunlu satır temizleme + gravity aynen çalışır
- [ ] Ek olarak: temizlenen satırlardaki `owners` grid'inden P1/P2 katkısını hesapla
- [ ] Her temizlenen satırda kaç hücre P1'e, kaç hücre P2'ye ait olduğunu say
- [ ] Katkı bilgisini return value olarak veya attribute olarak döndür
- [ ] `self.last_clear_p1_cells` ve `self.last_clear_p2_cells` gibi attr'ler tut

### 1.7 `lock_piece(piece, player)` override / wrapper
- [ ] Mevcut `lock_piece(piece)` mantığını çağır
- [ ] `owners` grid'ine oyuncu bilgisi yazıldığını doğrula (mevcut Board zaten `piece.name` yazıyor)
- [ ] Co-op'ta owner'ı oyuncu bazlı ayırt edebilmek için `piece.name` yerine `"P1"` / `"P2"` yazılıp yazılmayacağına karar ver
- [ ] **Karar:** `owners` grid'ine `"P1"` veya `"P2"` string'i yazılacak (katkı hesabı için)

### 1.8 Board skorlama stratejisi
- [ ] Board'un dahili `self.score` attr'ünü KULLANMA — co-op'ta `team_score` CoopGame'de tutulacak
- [ ] `clear_lines()` dönüş değerinden temizlenen satır sayısını al
- [ ] Skor hesaplaması CoopGame tarafında yapılacak (Board'un kendi score artışını pas geç veya sıfırla)
- [ ] **Dikkat:** Board.clear_lines() içinde `self.score +=` satırı var — bu co-op'ta istenmeyen davranış üretebilir
- [ ] Çözüm: `clear_lines()` override'ında score artışını `team_score`'a yönlendir VEYA Board.score'u ignore edip CoopGame'de ayrı hesapla

### ✅ Faz 1 Sonu İnceleme
- [ ] `CoopBoard()`'u başlat, `width=20, height=20` doğrula
- [ ] `is_valid_position_for_player` testleri: P1 parça P2 alanına taşamaz, P2 parça P1 alanına taşamaz
- [ ] `get_spawn_position` her iki oyuncu için doğru koordinat döndürüyor
- [ ] `can_spawn` dolu/boş board'da doğru çalışıyor
- [ ] `clear_lines` 20 sütunlu tam satırda temizleme yapıyor, kısmi satırda yapmıyor
- [ ] `lock_piece` owners grid'ine doğru oyuncu bilgisi yazıyor
- [ ] Skor çift sayım riski yok (Board.score vs team_score net ayrılmış)
- [ ] PvP'den kalan gereksiz kod yok
- [ ] Import'lar temiz, unused import yok
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 2 — CoopGame Çekirdek Sınıfı (`src/coop_game.py`)

### 2.1 Dosya oluştur ve temel yapıyı kur
- [ ] `src/coop_game.py` oluştur
- [ ] PvP'nin `__init__` imza yapısını referans al (sound_enabled, effects_enabled, screen, fullscreen, user_manager, settings_manager, sound_manager)
- [ ] `CoopGame` sınıfını tanımla (object'ten türetilecek, Game'den değil)

### 2.2 `__init__` — Board ve parça sistemi
- [ ] `self.board = CoopBoard()` — tek ortak 20×20 board
- [ ] Parça bag sistemi kur (PvP'nin `generate_pieces` ve `get_next_piece` mantığını adapte et)
- [ ] **Önemli fark:** Co-op'ta P1 ve P2 **bağımsız** parça akışları alacak (aynı sequence DEĞİL)
- [ ] `self.p1_piece_bag` ve `self.p2_piece_bag` ayrı bag'ler
- [ ] `self.p1_current_piece`, `self.p1_next_piece` — P1 aktif ve sonraki parça
- [ ] `self.p2_current_piece`, `self.p2_next_piece` — P2 aktif ve sonraki parça
- [ ] İlk parçaları spawn et: `_spawn_initial_pieces()`

### 2.3 `__init__` — Oyun durumu
- [ ] `self.game_over = False`
- [ ] `self.paused = False`
- [ ] `self.pause_menu_selected = 0`
- [ ] `self.team_score = 0`
- [ ] `self.total_lines_cleared = 0`
- [ ] `self.level = 1`
- [ ] `self.p1_contribution_pct = 50`
- [ ] `self.p2_contribution_pct = 50`
- [ ] `self.p1_total_cells = 0`, `self.p2_total_cells = 0` — katkı takibi

### 2.4 `__init__` — Freeze sistemi
- [ ] `self.p1_frozen = False`
- [ ] `self.p2_frozen = False`

### 2.5 `__init__` — Shared hold sistemi
- [ ] `self.shared_hold_piece = None`
- [ ] `self.p1_hold_used = False` — P1 aktif parçası için hold kullanıldı mı
- [ ] `self.p2_hold_used = False` — P2 aktif parçası için hold kullanıldı mı
- [ ] `self.hold_last_player = None` — son hold'a koyan oyuncu (görsel gösterim için)

### 2.6 `__init__` — Zamanlama
- [ ] `self.p1_fall_time = 0`, `self.p2_fall_time = 0` — gravity accumulator
- [ ] `self.fall_speed = 900` — ortak global hız (ms)
- [ ] `self.elapsed_time = 0` — toplam oyun süresi
- [ ] `self.clock = pygame.time.Clock()`

### 2.7 `__init__` — DAS (Delayed Auto Shift) sistemi
- [ ] P1 için: `self.p1_das_direction`, `self.p1_das_timer`, `self.p1_das_repeat_timer`, `self.p1_das_charged`
- [ ] P2 için: `self.p2_das_direction`, `self.p2_das_timer`, `self.p2_das_repeat_timer`, `self.p2_das_charged`
- [ ] DAS sabitleri: `DAS_DELAY = 170`, `DAS_REPEAT = 50` (PvP ile aynı)
- [ ] P1 için: `self.p1_soft_drop_active`, `self.p1_soft_drop_timer`
- [ ] P2 için: `self.p2_soft_drop_active`, `self.p2_soft_drop_timer`

### 2.8 `__init__` — Kontroller ve pencere
- [ ] `self.pvp_controls = self._resolve_pvp_controls()` — PvP ile aynı metodu kullan
- [ ] `self.screen = screen or pygame.display.get_surface()`
- [ ] `self.window_width, self.window_height = self.screen.get_size()`
- [ ] `self.fullscreen = fullscreen`
- [ ] Ses ve efekt yöneticilerini sakla

### 2.9 `__init__` — Tema ve görsel
- [ ] `self.sound` — SoundManager referansı
- [ ] `self.settings_manager` referansı
- [ ] Block style ve tema bilgisini yükle (PvP'nin `_apply_block_style` mantığı)
- [ ] `self.mode_skin` — mode_skins'ten co-op skin'i al (veya PvP varsayılanını kullan)

### ✅ Faz 2 Sonu İnceleme
- [ ] `CoopGame()` hatasız başlatılabiliyor
- [ ] Board 20×20 oluşuyor
- [ ] İki oyuncu için ayrı parçalar spawn ediliyor
- [ ] P1 parçası sol tarafta (x=3), P2 parçası sağ tarafta (x=13) spawn oluyor
- [ ] Tüm attr'ler doğru başlangıç değerlerinde
- [ ] PvP'den kopyalanan ama co-op'ta kullanılmayan attr yok (winner, match_mode, p1_eliminated vb.)
- [ ] Import'lar temiz
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 3 — Input Yönetimi

### 3.1 `_resolve_pvp_controls()` metodu
- [ ] PvP'deki implementasyonu kopyala ve adapte et
- [ ] `settings_manager.get_controls()` → `pvp` → `player1` / `player2` yapısını oku
- [ ] Fallback: P1 WASD, P2 yön tuşları
- [ ] Hold tuşu ekle: P1 → `left shift` (veya PvP hard_drop'u), P2 → `space`
- [ ] **Dikkat:** PvP'de P1 hard_drop = `left shift`, P2 hard_drop = `space`
- [ ] Co-op hold için yeni tuş mı yoksa mevcut hard_drop tuşu mu kullanılacak?
- [ ] **Karar gerekli:** Hold tuşu ayrı mı olacak? Eğer PvP tuşlarını kullanıyorsak hard_drop ve hold çakışmamalı
- [ ] Geçici çözüm: P1 hold = `e` veya `q`, P2 hold = `right shift` veya `numpad 0` gibi yeni tuş

### 3.2 `handle_input()` — Ana input döngüsü
- [ ] `pygame.event.get()` ile event loop
- [ ] `QUIT` event → `return False`
- [ ] `VIDEORESIZE` event → pencere boyutu güncelle
- [ ] `KEYDOWN` event dispatch:

### 3.3 `handle_input()` — Pause kontrolü
- [ ] ESC veya P tuşu → pause toggle
- [ ] Pause durumundayken: `_handle_pause_menu_input(event)` çağır
- [ ] Resume / Main Menu seçenekleri
- [ ] Pause durumundayken oyun input'u engellenmeli

### 3.4 `handle_input()` — P1 input (frozen değilse)
- [ ] `if not self.p1_frozen:` kontrolü
- [ ] Sola hareket: `board.is_valid_position_for_player(piece, 'P1')` ile kontrol
- [ ] Sağa hareket: aynı kontrol
- [ ] Rotasyon: döndürülmüş parçanın `is_valid_position_for_player` geçmesi gerekli
- [ ] Soft drop: `p1_current_piece.y += 1`, geçersizse geri al
- [ ] Hard drop: parçayı en aşağı indir + kilitle
- [ ] Hold: `_use_shared_hold('P1')` çağır
- [ ] DAS başlatma: tuş basıldığında `p1_das_direction` set et

### 3.5 `handle_input()` — P2 input (frozen değilse)
- [ ] `if not self.p2_frozen:` kontrolü
- [ ] P1 ile aynı mantık, P2 tuşları ve P2 parçası ile
- [ ] `is_valid_position_for_player(piece, 'P2')` kullanılmalı

### 3.6 `handle_input()` — KEYUP event'leri
- [ ] P1 ve P2 DAS sıfırlama
- [ ] P1 ve P2 soft drop sıfırlama

### 3.7 DAS güncelleme yardımcı metotları
- [ ] `_update_das(player, dt)` — PvP'deki DAS mantığını adapte et
- [ ] Her frame `update()` içinden çağrılacak
- [ ] Frozen oyuncu için DAS güncellemesi yapılmamalı

### ✅ Faz 3 Sonu İnceleme
- [ ] P1 tuşları P1 parçasını hareket ettiriyor, P2 parçasını etkilemiyor
- [ ] P2 tuşları P2 parçasını hareket ettiriyor, P1 parçasını etkilemiyor
- [ ] Frozen oyuncunun tuşları hiçbir şey yapmıyor
- [ ] Parçalar orta çizgiyi geçemiyor (rotasyon dahil)
- [ ] Hold tuşu çakışma yaratmıyor
- [ ] Pause/ESC düzgün çalışıyor
- [ ] DAS her iki oyuncu için bağımsız çalışıyor
- [ ] Keyup'ta state sıfırlamaları doğru
- [ ] PvP'den kalan rekabet input'u yok
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 4 — Oyun Döngüsü (update)

### 4.1 `update(dt_ms)` — Ana güncelleme metodu
- [ ] `if self.game_over or self.paused: return`
- [ ] `self.elapsed_time += dt_ms`
- [ ] DAS güncelle: `_update_das('P1', dt_ms)`, `_update_das('P2', dt_ms)`

### 4.2 `update()` — P1 gravity tick
- [ ] `if not self.p1_frozen:` kontrolü
- [ ] `self.p1_fall_time += dt_ms`
- [ ] `if self.p1_fall_time >= self.fall_speed:`
  - [ ] `self.p1_fall_time = 0`
  - [ ] `self.p1_current_piece.y += 1`
  - [ ] `if not self.board.is_valid_position_for_player(piece, 'P1'):`
    - [ ] `piece.y -= 1` (geri al)
    - [ ] `self._lock_and_new_piece('P1')` çağır

### 4.3 `update()` — P2 gravity tick
- [ ] P1 ile aynı mantık, P2 attr'leri ile

### 4.4 `_lock_and_new_piece(player)` metodu
- [ ] `self.board.lock_piece(piece, player)` çağır — parçayı board'a kilitle
- [ ] `cleared = self.board.clear_lines()` çağır — satır temizle
- [ ] `if cleared > 0:` → skor güncelle, seviye güncelle, katkı güncelle
- [ ] Skor hesaplama: Board'un kendi hesaplamasını mı kullanacağız yoksa ayrı mı yapacağız?
  - [ ] **Öneri:** Board.clear_lines() zaten score hesaplıyor; bu değeri `self.team_score += board.score - prev_score` şeklinde delta olarak al
  - [ ] Alternatif: Board.score'u tamamen ignore et, co-op'a özel basit formül kullan
- [ ] Seviye hesaplama: `self.level = (self.total_lines_cleared // 5) + 1`
- [ ] Hız güncelleme: `self.fall_speed = max(100, 900 - (self.level - 1) * 50)` (veya benzeri eğri)
- [ ] Katkı yüzdesi güncelle: `_update_contribution(cleared_info)`
- [ ] Clear sonrası freeze kontrolü: `_try_unfreeze_players()`
- [ ] Yeni parça spawn et: `_try_spawn_for_player(player)`

### 4.5 `_try_spawn_for_player(player)` metodu
- [ ] `if self.board.can_spawn(player):` → yeni parça oluştur ve ata
  - [ ] `piece = self._get_next_piece(player)`
  - [ ] `piece.x, piece.y = self.board.get_spawn_position(player)`
  - [ ] `self._apply_block_style(piece)`
  - [ ] Hold reset: `self.pX_hold_used = False`
- [ ] `else:` → oyuncuyu freeze et
  - [ ] `self.pX_frozen = True`
  - [ ] Diğer oyuncu da frozen mı kontrol et → `_check_double_freeze()`

### 4.6 `_check_double_freeze()` metodu
- [ ] `if self.p1_frozen and self.p2_frozen:` → `self.game_over = True`
- [ ] Game over ses efekti çal
- [ ] Game over state'i kaydet

### 4.7 `_try_unfreeze_players()` metodu
- [ ] Satır temizliği sonrası çağrılır
- [ ] `if self.p1_frozen and self.board.can_spawn('P1'):`
  - [ ] P1'i hemen unfreeze ETME — bir sonraki düşüş tickinde spawn et
  - [ ] `self.p1_pending_unfreeze = True` flag'i set et
- [ ] `if self.p2_frozen and self.board.can_spawn('P2'):`
  - [ ] Aynı mantık P2 için
- [ ] `update()` içinde: `if self.p1_pending_unfreeze and fall_tick:` → gerçek unfreeze yap
  - [ ] `self.p1_frozen = False`
  - [ ] `self.p1_pending_unfreeze = False`
  - [ ] `_try_spawn_for_player('P1')`

### 4.8 `_update_contribution(clear_info)` metodu
- [ ] Temizlenen satırlardaki P1/P2 hücre sayısından katkı yüzdesi hesapla
- [ ] `self.p1_total_cells += p1_cells`
- [ ] `self.p2_total_cells += p2_cells`
- [ ] `total = self.p1_total_cells + self.p2_total_cells`
- [ ] `if total > 0:`
  - [ ] `self.p1_contribution_pct = round(100 * self.p1_total_cells / total)`
  - [ ] `self.p2_contribution_pct = 100 - self.p1_contribution_pct`

### 4.9 Parça üretimi
- [ ] `_get_next_piece(player)` — bag'den sonraki parçayı al
- [ ] P1 ve P2 için ayrı bag'ler: `self.p1_piece_bag`, `self.p2_piece_bag`
- [ ] Bag boşsa yeniden doldur: `_refill_bag(player)` — 7 parça × 2 kopya, shuffle
- [ ] `_apply_block_style(piece)` — tema renklerini uygula

### ✅ Faz 4 Sonu İnceleme
- [ ] Gravity her iki oyuncu için bağımsız çalışıyor
- [ ] Parça kilitleme → satır temizleme → skor güncelleme zinciri doğru
- [ ] Team score doğru artıyor, çift sayım yok
- [ ] Seviye ve hız artışı doğru çalışıyor
- [ ] Freeze: spawn edilemezse oyuncu donuyor
- [ ] Unfreeze: alan açılınca bir sonraki düşüş tickinde, hemen değil
- [ ] Çift freeze = game over
- [ ] Katkı yüzdesi doğru hesaplanıyor
- [ ] Parça bag'leri bağımsız çalışıyor, P1/P2 farklı parçalar alıyor
- [ ] Edge case: P1 lock → P2 alanında satır temizler → P2 unfreeze olabilir
- [ ] Edge case: Her iki oyuncu aynı frame'de lock ederse sıralı işlenir
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 5 — Shared Hold Sistemi

### 5.1 `_use_shared_hold(player)` metodu
- [ ] `if player == 'P1' and self.p1_hold_used: return` — zaten kullandıysa engelle
- [ ] `if player == 'P2' and self.p2_hold_used: return`

### 5.2 Hold slotu boşsa
- [ ] Oyuncunun aktif parçasını `self.shared_hold_piece`'e koy
- [ ] Bag'den yeni parça çek ve oyuncuya ver
- [ ] Yeni parça spawn pozisyonuna yerleştir
- [ ] `self.pX_hold_used = True`
- [ ] `self.hold_last_player = player`

### 5.3 Hold slotunda parça varsa (swap)
- [ ] Hold'daki parçayı çek → eski: `held = self.shared_hold_piece`
- [ ] Oyuncunun aktif parçasını hold'a koy → `self.shared_hold_piece = current`
- [ ] Çekilen parçayı oyuncuya ver: `self.pX_current_piece = held`
- [ ] Çekilen parçanın pozisyonunu oyuncunun spawn pozisyonuna sıfırla
- [ ] Çekilen parçanın rotasyonunu sıfırla (state 0)
- [ ] `self.pX_hold_used = True`
- [ ] `self.hold_last_player = player`

### 5.4 Hold parçası alan kontrolü
- [ ] Swap sonrası çekilen parçanın oyuncunun alanında geçerli pozisyonda olduğunu kontrol et
- [ ] `if not self.board.is_valid_position_for_player(held, player):` → swap yapılmasın? veya parçayı spawn pozisyonunda dene
- [ ] Edge case: Eğer hold'dan çekilen parça bile sığmıyorsa → swap iptal et, orijinal durumu koru

### 5.5 Hold reset zamanlaması
- [ ] `p1_hold_used` → P1 parçası kilitlendiğinde sıfırlanır (`_lock_and_new_piece` içinde)
- [ ] `p2_hold_used` → P2 parçası kilitlendiğinde sıfırlanır
- [ ] Bu, her aktif parça için bir kez hold kullanılabilmesini garanti eder

### ✅ Faz 5 Sonu İnceleme
- [ ] P1 hold yapıyor → parça shared slot'a gidiyor, P1 yeni parça alıyor
- [ ] P2 hold yapıyor → dolu slot'tan swap yapıyor, P1'in bıraktığı parça P2'ye geliyor
- [ ] Aynı aktif parça için iki kez hold yapılamıyor
- [ ] Parça kilitlenince hold hakkı sıfırlanıyor
- [ ] Hold'dan çekilen parça doğru oyuncu alanında spawn oluyor
- [ ] Hold'dan çekilen parça sığmazsa swap iptal ediliyor (crash yok)
- [ ] Sonsuz hold döngüsü yok (parça başına tek kullanım kuralı)
- [ ] `self.hold_last_player` doğru güncelleniyor
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 6 — Render Sistemi (draw)

### 6.1 `calculate_board_position()` metodu
- [ ] Tek 20 sütunlu board için ekran pozisyonu hesapla
- [ ] PvP'nin `calculate_board_positions()` referans alınacak ama iki board yerine tek geniş board
- [ ] `cell_size = min(max_cell_h, max_cell_w, 40)` — responsive hesaplama
- [ ] `board_pixel_width = 20 * cell_size`
- [ ] `board_pixel_height = 20 * cell_size`
- [ ] Board'u ekranda ortala
- [ ] `self.board_offset_x`, `self.board_offset_y` hesapla
- [ ] Yan paneller için yer bırak (sol: P1 next/hold, sağ: P2 next/hold)

### 6.2 `draw()` — Ana çizim metodu
- [ ] `self.screen.fill(bg_color)` — arkaplan
- [ ] `self.calculate_board_position()` — pozisyon güncelle
- [ ] `self._draw_board()` — board grid + kilitli bloklar
- [ ] `self._draw_midline()` — orta çizgi (sütun 9-10 arası)
- [ ] `self._draw_active_pieces()` — P1 ve P2 aktif parçaları
- [ ] `self._draw_ghost_pieces()` — her iki oyuncu için ghost/shadow
- [ ] `self._draw_hud()` — skor, seviye, zaman, katkı
- [ ] `self._draw_side_panels()` — next parçalar + shared hold
- [ ] `if self.p1_frozen: self._draw_freeze_overlay('P1')`
- [ ] `if self.p2_frozen: self._draw_freeze_overlay('P2')`
- [ ] `if self.paused: self._draw_pause_menu()`
- [ ] `if self.game_over: self._draw_game_over()`
- [ ] `pygame.display.flip()`

### 6.3 `_draw_board()` metodu
- [ ] Board grid'ini hücre hücre çiz
- [ ] Her dolu hücre için renk bilgisini `self.board.grid[y][x]`'den al
- [ ] Blok stili uygula (jelly, flat, vb.)
- [ ] Grid çizgileri (opsiyonel, ince)

### 6.4 `_draw_midline()` metodu
- [ ] Sütun 9 ve 10 arasına dikey çizgi çiz
- [ ] Renk: beyaz veya temaya uygun, alpha ile
- [ ] Kalınlık: 2-3px
- [ ] Board'un üstünden altına tam uzanmalı

### 6.5 `_draw_active_pieces()` metodu
- [ ] P1 aktif parçasını çiz (frozen değilse)
- [ ] P2 aktif parçasını çiz (frozen değilse)
- [ ] Her hücre `board_offset_x + piece.x * cell_size` ile konumlanır

### 6.6 `_draw_ghost_pieces()` metodu
- [ ] P1 ghost: aktif parçayı en alt geçerli pozisyona düşür (alpha 30-50%)
- [ ] P2 ghost: aynı mantık
- [ ] Ghost hesaplamasında `is_valid_position_for_player` kullanılmalı

### 6.7 `_draw_hud()` metodu
- [ ] Üst bar: "QUADRIX CO-OP" başlığı
- [ ] Team score: `UIFonts.get(size).render(str(self.team_score), ...)`
- [ ] Level göstergesi
- [ ] Zaman göstergesi: elapsed_time'dan `MM:SS` formatı
- [ ] Katkı göstergesi: "P1 %50 — P2 %50" benzeri metin
- [ ] Satır sayısı: `self.total_lines_cleared`

### 6.8 `_draw_side_panels()` metodu
- [ ] Sol panel: P1 next parça önizlemesi
- [ ] Sağ panel: P2 next parça önizlemesi
- [ ] Orta veya araya yerleştirilmiş: Shared Hold kutusu
- [ ] Hold kutusunda `self.shared_hold_piece` çizilir (varsa)
- [ ] Hold kutusunun yanında "SHARED HOLD" etiketi
- [ ] Son bırakan oyuncu küçük metinle gösterilebilir (opsiyonel)

### 6.9 `_draw_freeze_overlay(player)` metodu
- [ ] Frozen oyuncunun board alanı üzerine yarı saydam overlay
- [ ] P1 frozen → sol 10 sütun üzerine overlay
- [ ] P2 frozen → sağ 10 sütun üzerine overlay
- [ ] Overlay içinde basit metin: "WAITING..." veya lokalize edilmiş metin
- [ ] Diğer oyuncunun alanı etkilenmemeli

### 6.10 `_draw_pause_menu()` metodu
- [ ] PvP'nin pause menüsünü referans al
- [ ] Ekranın ortasında yarı saydam panel
- [ ] "PAUSED" başlığı
- [ ] "Resume" / "Main Menu" seçenekleri
- [ ] Seçili öğe vurgulanmış

### 6.11 `_draw_game_over()` metodu
- [ ] Ekranın ortasında game over paneli
- [ ] "GAME OVER" başlığı
- [ ] Final team score
- [ ] Katkı yüzdeleri
- [ ] Toplam süre, satır sayısı
- [ ] "Press any key to continue" veya "ESC for menu"

### ✅ Faz 6 Sonu İnceleme
- [ ] 20 sütunlu board ekranda düzgün render ediliyor
- [ ] Orta çizgi doğru yerde (sütun 9-10 arası)
- [ ] P1 ve P2 parçaları doğru pozisyonlarda çiziliyor
- [ ] Ghost parçalar doğru hesaplanıyor ve kendi alanları dışına çıkmıyor
- [ ] HUD okunaklı ve responsive (farklı pencere boyutlarında test et)
- [ ] Side panel'ler (next + hold) doğru konumda
- [ ] Freeze overlay sadece ilgili alanı kaplıyor
- [ ] Pause menü düzgün çiziliyor ve input alıyor
- [ ] Game over ekranı doğru bilgileri gösteriyor
- [ ] Performans: 60fps düşmüyor (gereksiz render yok)
- [ ] Font kullanımı: `UIFonts.get()` veya `retro_style.get_font()` ile tutarlı
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 7 — Main Loop Entegrasyonu

### 7.1 `src/main.py` — coop_mode aksiyonunu bağla
- [ ] Mevcut placeholder'ı bul: `elif action == 'coop_mode':` (satır ~2021)
- [ ] `menu.show_info()` çağrısını kaldır
- [ ] PvP launch pattern'ini referans al (satır ~1946-1963)
- [ ] `CoopGame` import et
- [ ] CoopGame'i başlat:
  ```python
  coop_game = CoopGame(
      sound_enabled=settings_manager.get('sound_enabled', True),
      effects_enabled=settings_manager.get('particle_effects', False),
      user_manager=user_manager,
      settings_manager=settings_manager,
      sound_manager=sound_manager,
  )
  ```
- [ ] Game loop:
  ```python
  while True:
      alive = coop_game.handle_input()
      if not alive:
          break
      coop_game.update()
      coop_game.draw()
      clock.tick(60)
  ```
- [ ] Loop sonrası menüye dön

### 7.2 `src/menu.py` — Co-op kartını aktifleştir
- [ ] `menu_dashboard_sub_coop_mode` metnini "Coming soon"dan "2 Oyuncu Co-op" gibi bir şeye değiştir
- [ ] Eğer kart "coming soon" badge gösteriyorsa bu badge'i kaldır
- [ ] `flat_title_band_panels`'dan `coop_mode`'u çıkar (eğer normal title bar istiyorsak) veya bırak
- [ ] Kartın renk ve ikonunu koru: `(80, 230, 160)` yeşil tonu

### 7.3 `handle_input()` dönüş değeri
- [ ] `handle_input()` → `True` = devam, `False` = çık (menüye dön)
- [ ] ESC veya "Main Menu" seçilince `return False`
- [ ] Game over'da ESC → `return False`
- [ ] Pencere kapatma (QUIT) → `return False`

### ✅ Faz 7 Sonu İnceleme
- [ ] Menüden co-op kartına tıklayınca oyun başlıyor
- [ ] Oyun bitince (game over + dismiss) menüye dönüyor
- [ ] ESC ile pause → "Main Menu" → menüye dönüyor
- [ ] Pencere kapatma düzgün çalışıyor
- [ ] main.py'deki import temiz
- [ ] Menü kartı aktif görünüyor, "coming soon" badge yok
- [ ] PvP ve diğer modlar etkilenmemiş
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 8 — Lokalizasyon

### 8.1 Co-op HUD metinleri
- [ ] `src/localization.py`'ye yeni key'ler ekle (en az TR ve EN, diğer diller fallback ile dolar):
  - [ ] `coop_team_score` → TR: "Takım Skoru", EN: "Team Score"
  - [ ] `coop_level` → TR: "Seviye", EN: "Level"
  - [ ] `coop_lines` → TR: "Satırlar", EN: "Lines"
  - [ ] `coop_contribution` → TR: "Katkı", EN: "Contribution"
  - [ ] `coop_shared_hold` → TR: "Ortak Hold", EN: "Shared Hold"

### 8.2 Freeze ve durum metinleri
- [ ] `coop_frozen_waiting` → TR: "Alan Bekleniyor...", EN: "Waiting for Space..."
- [ ] `coop_frozen_help` → TR: "Takım arkadaşın satır temizlemeli", EN: "Your teammate must clear lines"
- [ ] `coop_game_over` → TR: "OYUN BİTTİ", EN: "GAME OVER"
- [ ] `coop_game_over_both_frozen` → TR: "İki oyuncu da sıkıştı!", EN: "Both players stuck!"

### 8.3 Menü ve açıklama metinleri
- [ ] `menu_dashboard_sub_coop_mode` güncelle → TR: "Yerel 2 Oyunculu Co-op", EN: "Local 2-Player Co-op"
- [ ] `coop_paused` → TR: "DURAKLATILDI", EN: "PAUSED"
- [ ] `coop_resume` → TR: "Devam Et", EN: "Resume"
- [ ] `coop_main_menu` → TR: "Ana Menü", EN: "Main Menu"

### 8.4 Game over sonuç metinleri
- [ ] `coop_final_score` → TR: "Final Skor", EN: "Final Score"
- [ ] `coop_total_lines` → TR: "Toplam Satır", EN: "Total Lines"
- [ ] `coop_total_time` → TR: "Toplam Süre", EN: "Total Time"
- [ ] `coop_press_continue` → TR: "Devam etmek için bir tuşa bas", EN: "Press any key to continue"

### ✅ Faz 8 Sonu İnceleme
- [ ] Tüm yeni key'ler en az TR ve EN dilinde tanımlı
- [ ] `t('yeni_key')` çağrıları doğru string döndürüyor
- [ ] HUD, freeze overlay, game over ekranında tüm metinler lokalize
- [ ] Mevcut key'ler bozulmamış
- [ ] Fallback sistemi çalışıyor (diğer dillerde EN gösteriliyor)
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 9 — Ses Entegrasyonu

### 9.1 Mevcut sesleri bağla
- [ ] Parça kilitleme sesi: `self.sound.play('lock')` — mevcut
- [ ] Satır temizleme sesi: `self.sound.play('clear')` — mevcut
- [ ] Hard drop sesi: `self.sound.play('hard_drop')` — mevcut
- [ ] Game over sesi: `self.sound.play('gameover')` — mevcut
- [ ] Rotasyon sesi: `self.sound.play('rotate')` — mevcut
- [ ] Hareket sesi: `self.sound.play('move')` — mevcut (opsiyonel)

### 9.2 Pause sesleri
- [ ] Pause'da müzik duck: `self.sound.duck_music()`
- [ ] Resume'da müzik unduck: `self.sound.unduck_music()`

### 9.3 Hold sesi
- [ ] Hold kullanımında ses: `self.sound.play('hold')` — mevcut mi kontrol et
- [ ] Yoksa `self.sound.play('rotate')` ile başla

### 9.4 Müzik
- [ ] Co-op başlarken müzik playlist'i ayarla (mevcut game müziğini kullan)
- [ ] `self.sound.set_music_playlist(shuffle=True)` — settings'e göre

### ✅ Faz 9 Sonu İnceleme
- [ ] Tüm oyun aksiyonlarında uygun ses çalıyor
- [ ] Ses çalmaya çalışırken crash yok (ses kapalıysa da)
- [ ] Pause'da müzik düşüyor, resume'da geri geliyor
- [ ] `./scripts/test/run_tests.sh -q` geçiyor

---

## FAZ 10 — Test ve Edge Case'ler

### 10.1 Manuel oynanış testi
- [ ] İki oyuncu aynı anda rahat oynayabiliyor mu?
- [ ] Parçalar doğru alanlarda kalıyor mu?
- [ ] Satır temizleme sadece 20/20 doluysa mı oluyor?

### 10.2 Freeze senaryoları
- [ ] P1 freeze → P2 oynamaya devam → P2 satır temizliyor → P1 unfreeze
- [ ] P2 freeze → P1 oynamaya devam → P1 satır temizliyor → P2 unfreeze
- [ ] P1 ve P2 aynı anda freeze → game over
- [ ] P1 freeze → P2 de kısa süre sonra freeze → game over
- [ ] Unfreeze'den sonra parça doğru pozisyonda spawn oluyor mu?

### 10.3 Hold senaryoları
- [ ] P1 hold yapıyor (boş slot) → P1 yeni parça alıyor, eski parça hold'da
- [ ] P2 hold yapıyor (dolu slot) → P2 hold'daki parçayı alıyor, P2'nin parçası hold'a gidiyor
- [ ] P1 tekrar hold yapıyor → aynı aktif parça için 2. kez hold reddediliyor
- [ ] P1 parçasını kilitliyor → P1 yeni parça alıyor → artık tekrar hold yapabilir
- [ ] Hold'dan çekilen parça karşı alanın boyutuna sığıyor mu? (I-parçası yatay 4 blok)

### 10.4 Skor ve seviye
- [ ] Tek satır temizleme → doğru puan
- [ ] Tetris (4 satır) → doğru bonus
- [ ] Seviye atlama → hız artışı
- [ ] Katkı yüzdesi mantıklı değerler gösteriyor

### 10.5 Pencere boyutu
- [ ] Küçük pencere (1280×720) → board sığıyor, HUD okunuyor
- [ ] Büyük pencere (1920×1080) → board ortalı, boşluklar dengeli
- [ ] Fullscreen → sorunsuz

### 10.6 Birim testleri
- [ ] `tests/test_coop_board.py` oluştur:
  - [ ] Board oluşturma (20×20)
  - [ ] `is_valid_position_for_player` sınır kontrolü
  - [ ] `can_spawn` boş ve dolu board'da
  - [ ] `clear_lines` tam ve kısmi satır
  - [ ] `lock_piece` owner bilgisi
- [ ] `tests/test_coop_game.py` oluştur:
  - [ ] Game başlatma
  - [ ] Freeze state geçişleri
  - [ ] Hold swap mantığı
  - [ ] Skor hesaplama
  - [ ] Çift freeze = game over

### ✅ Faz 10 Sonu İnceleme
- [ ] Tüm edge case'ler manuel test edildi
- [ ] Birim testleri yazıldı ve geçiyor
- [ ] Crash veya hang senaryosu yok
- [ ] Performans sorunu yok
- [ ] `./scripts/test/run_tests.sh -q` geçiyor (mevcut testler dahil)

---

## FAZ 11 — Final İnceleme ve Polish

### 11.1 Kod kalitesi
- [ ] Tüm dosyalarda unused import kontrolü
- [ ] PvP'den kopyalanmış ama co-op'ta kullanılmayan kod kontrolü (winner, match_mode, p1_eliminated vb.)
- [ ] Tutarsız isimlendirme kontrolü (player/'P1' string karışımı vb.)
- [ ] Magic number kontrolü → sabitler tanımlanmış mı

### 11.2 Robustness
- [ ] Sound manager None olduğunda crash yok
- [ ] Settings manager None olduğunda fallback değerler çalışıyor
- [ ] Pencere resize sırasında crash yok
- [ ] Alt+Tab veya focus kaybında crash yok

### 11.3 Tasarım uyumu
- [ ] Co-op tasarım belgesindeki tüm V1 kararları uygulanmış mı?
  - [ ] Local endless co-op ✓
  - [ ] P1: WASD, P2: yön tuşları ✓
  - [ ] Tek ortak board ✓
  - [ ] Ortak team score ✓
  - [ ] Katkı yüzdesi göstergesi ✓
  - [ ] Tek ortak hold slotu ✓
  - [ ] Freeze ve unfreeze akışı ✓
  - [ ] Spawn bazlı freeze ✓
  - [ ] Çift freeze = game over ✓
  - [ ] Unfreeze bir sonraki düşüş tickinde ✓

### 11.4 Mevcut sisteme zarar vermeme kontrolü
- [ ] PvP modu hala düzgün çalışıyor
- [ ] Tek oyuncu modları hala düzgün çalışıyor
- [ ] Campaign hala düzgün çalışıyor
- [ ] Menüdeki diğer kartlar etkilenmemiş
- [ ] Mevcut testler hala geçiyor

### 11.5 Belge güncelleme
- [ ] `plans/co-op sistemi detaylı .md` → V1 implementasyon durumunu güncelle
- [ ] `AGENTS.md` → co-op dosyalarını ilgili bölümlere ekle (coop_board.py, coop_game.py)

### ✅ Faz 11 Sonu İnceleme (Final)
- [ ] Tüm fazların kendi incelemesi geçilmiş
- [ ] Kod temiz, gereksiz parça yok
- [ ] Tasarım belgesiyle %100 uyumlu
- [ ] Mevcut oyun bozulmamış
- [ ] `./scripts/test/run_tests.sh -q` geçiyor
- [ ] Manuel: menüden co-op aç → oyna → freeze → unfreeze → hold → game over → menüye dön

---

## Özet: Faz Akışı

| Faz | Konu | Çıktı |
|-----|------|-------|
| 0 | Hazırlık | Okuma ve doğrulama |
| 1 | CoopBoard | `src/coop_board.py` — 20×20 board + sınır + clear |
| 2 | CoopGame init | `src/coop_game.py` — sınıf yapısı + tüm attr'ler |
| 3 | Input | handle_input — iki oyunculu tuş yönetimi |
| 4 | Update | Gravity, lock, clear, freeze, unfreeze, skor döngüsü |
| 5 | Shared Hold | Hold swap, handoff, parça başına tek kullanım |
| 6 | Render | draw — board, HUD, side panel, freeze, pause, game over |
| 7 | Entegrasyon | main.py + menu.py bağlantısı |
| 8 | Lokalizasyon | TR/EN metinler |
| 9 | Ses | Mevcut ses efektleri + müzik |
| 10 | Test | Manuel + birim testler |
| 11 | Final | Kod kalitesi, robustness, tasarım uyumu |

---

**Toplam yeni dosyalar:** 4 (coop_board.py, coop_game.py, test_coop_board.py, test_coop_game.py)  
**Modifiye dosyalar:** 3 (main.py, menu.py, localization.py) + opsiyonel (AGENTS.md, tasarım belgesi)
