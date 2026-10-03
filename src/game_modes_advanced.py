"""Gelişmiş Quadrix Oyun Modları - Survival, Cascade, Daily Challenge"""

from __future__ import annotations

import random
import os
import math
from datetime import date, timedelta

import pygame

try:
    # When imported as package (e.g. in tests: `import src.game_modes_advanced`)
    from .game import Game  # type: ignore
    from .constants import *  # type: ignore
    from .pieces import create_random_piece  # type: ignore
    from .user_manager import DAILY_MAX_FAILURES  # type: ignore
    from .retro_style import retro_style as ui_style  # type: ignore
    from .text_cache import render_text  # type: ignore
    # P1-4/P1-5 (Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu): safe rect
    # kısıtı + LRU önbellekli satır sarma. Her ikisi de yaprak modül
    # (yalnız platform_utils / text_cache import ederler) — döngü riski yok.
    from .game_over_surfaces import get_render_safe_rect  # type: ignore
    from .ui_text_layout import wrap_text_limited  # type: ignore
except Exception:
    from game import Game
    from constants import *
    from pieces import create_random_piece
    from user_manager import DAILY_MAX_FAILURES
    from retro_style import retro_style as ui_style
    from text_cache import render_text
    from game_over_surfaces import get_render_safe_rect
    from ui_text_layout import wrap_text_limited

class SurvivalMode(Game):
    """
    Survival Mode - Virüs Tehdidi Sistemi (YENİ TASARIM)
    
    KURALLAR:
    - Virüsler mevcut blokları enfekte eder
    - Enfekte bloklar belirli sürede temizlenmezse YENİLİR (silinir)
    - Yenilen blok sayısı 20'ye ulaşırsa GAME OVER
    - 10 dakika hayatta kalırsan KAZANIRSIN
    - Her 5000 puanda yenilen blok sayısı sıfırlanır (Antivirus)
    
    SEVİYELER (her 1 dakikada artar):
    - Seviye 1: Max 25 enfekte, 30 sn yenilme süresi, 4 sn yayılma
    - Seviye 2: Max 35 enfekte, 30 sn yenilme süresi, 3 sn yayılma
    - Seviye 3: Max 40 enfekte, 30 sn yenilme süresi, 2 sn yayılma
    - Seviye 4: Max 45 enfekte, 20 sn yenilme süresi, 1.5 sn yayılma
    - Seviye 5: Max 50 enfekte, 20 sn yenilme süresi, 1 sn yayılma
    """
    
    # Seviye ayarları
    LEVEL_CONFIG = {
        1: {"max_infected": 15, "consume_time": 60000, "spread_interval": 8000, "diagonal": False},
        2: {"max_infected": 15, "consume_time": 60000, "spread_interval": 7000, "diagonal": False},
        3: {"max_infected": 15, "consume_time": 40000, "spread_interval": 6000, "diagonal": False},
        4: {"max_infected": 20, "consume_time": 40000, "spread_interval": 5000, "diagonal": True},
        5: {"max_infected": 20, "consume_time": 30000, "spread_interval": 4000, "diagonal": True},
    }
    
    # Sabitler
    GAME_DURATION = 600000      # 10 dakika (ms)
    MAX_CONSUMED = 20           # Bu kadar blok yenilirse game over
    ANTIVIRUS_SCORE = 5000      # Her 5000 puanda yenilen sayısı sıfırlanır
    LEVEL_UP_INTERVAL = 120000  # Her 2 dakikada seviye artar
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, 
                 achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, 
                 settings_manager=None, user_manager=None, game_mode='survival', score_manager=None, sound_manager=None):
        """Survival mode'u başlat"""
        super().__init__(
            difficulty, sound_enabled, effects_enabled, achievement_manager,
            theme_manager, screen, fullscreen, settings_manager, user_manager,
            game_mode, sound_manager=sound_manager, score_manager=score_manager,
        )

        # Survival panel ölçeği için referans (tam ekran/büyük pencere baz alınır)
        self._survival_panel_base_size = (int(self.window_width), int(self.window_height))
        
        self._init_survival_state()

    def _survival_panel_scale(self, min_scale: float = 0.58, max_scale: float = 1.12) -> float:
        """Survival panel ölçeği: aktif canvas bazlı ortak UI scale wrapper'ı."""
        return self._ui_scale(min_scale=min_scale, max_scale=max_scale)

    def _init_survival_state(self):
        """Survival moduna özgü değişkenleri sıfırla"""
        # Zaman
        self.survival_time = 0
        self.last_level_up_time = 0
        
        # Seviye sistemi
        self.virus_level = 1
        self._apply_level_config()
        
        # Enfekte bloklar: {(x, y): enfekte_zamanı_ms}
        self.infected_blocks = {}
        
        # İstatistikler
        self.consumed_count = 0       # Şu an yenilen (20'ye ulaşırsa game over)
        self.total_consumed = 0       # Toplam yenilen (istatistik)
        self.last_antivirus_score = 0 # Son antivirus aktivasyonu skoru
        
        # Yayılma
        self.last_spread_time = 0
        self.last_spawn_time = 0
        self.spawn_interval = 8000    # İlk virüs spawn aralığı
        
        # Oyun durumu
        self.survival_victory = False
        self.game_over_by_virus = False
        
        # Görsel efektler
        self.consume_particles = []
        self.antivirus_flash = 0
        self.antivirus_flash_duration = 0
        
        # Cache
        self._heart_image = None
        self._virus_icon = None

    def _apply_level_config(self):
        """Mevcut seviyenin ayarlarını uygula"""
        config = self.LEVEL_CONFIG.get(self.virus_level, self.LEVEL_CONFIG[5])
        self.max_infected = config["max_infected"]
        self.consume_time = config["consume_time"]
        self.spread_interval = config["spread_interval"]
        self.diagonal_spread = config["diagonal"]
        
    def get_initial_speed(self):
        """Survival modda sabit hız - zorluk etkisiz"""
        return 600  # Sabit 600ms
    
    def get_current_speed(self):
        """Survival modda hız sabit kalır - seviyeyle hızlanmaz"""
        return 600  # Sabit 600ms
    
    def update(self, delta_time):
        """Oyun durumunu güncelle"""
        if self.game_over or self.paused or getattr(self, 'show_exit_prompt', False):
            return
        
        self.survival_time += delta_time
        
        # 1. ZAFER KONTROLÜ - 10 dakika hayatta kaldın mı?
        if self.survival_time >= self.GAME_DURATION and not self.game_over:
            self._handle_survival_victory()
            return
        
        # 2. SEVİYE ARTIŞI - Her 1 dakikada
        if self.survival_time - self.last_level_up_time >= self.LEVEL_UP_INTERVAL:
            self.last_level_up_time = self.survival_time
            if self.virus_level < 5:
                self.virus_level += 1
                self._apply_level_config()
                self.sound.play('level_up')
                print(f"[Uyarı] VİRÜS SEVİYESİ: {self.virus_level}/5")
                print(f"   Max enfekte: {self.max_infected}, Yenilme süresi: {self.consume_time//1000}sn")
        
        # 3. ANTİVİRÜS KONTROLÜ - Her 5000 puanda yenilen sayısı sıfırlanır
        current_score = self.board.score
        if current_score >= self.last_antivirus_score + self.ANTIVIRUS_SCORE:
            self.last_antivirus_score = (current_score // self.ANTIVIRUS_SCORE) * self.ANTIVIRUS_SCORE
            self._activate_antivirus()
        
        # 4. VİRÜS YAYILMASI
        self._update_virus_spread(delta_time)
        
        # 5. VİRÜS SPAWN (yeni virüs başlatma)
        self._spawn_virus_if_needed()
        
        # 6. BLOK YENİLME KONTROLÜ - Süre dolan bloklar yenilir
        self._check_consumed_blocks()
        
        # 7. GAME OVER KONTROLÜ - 20 blok yenildi mi?
        if self.consumed_count >= self.MAX_CONSUMED:
            self._handle_virus_game_over()
            return
        
        # 8. Antivirus flash efekti azalt
        if self.antivirus_flash > 0:
            self.antivirus_flash -= delta_time
        
        # Normal güncelleme
        super().update(delta_time)
    
    def _handle_survival_victory(self):
        """10 dakika hayatta kaldın - KAZANDIN!"""
        self.game_over = True
        self.survival_victory = True
        self.sound.play('tetris')
        self.trigger_screen_shake(intensity=25, duration=50 / 60.0)
        
        # Bonus puan
        bonus = (self.MAX_CONSUMED - self.consumed_count) * 500 + self.board.lines_cleared * 100
        self.board.score += bonus
        
        print(f"SURVIVAL KAZANILDI! Bonus: {bonus} puan")
        
        if self.effects_enabled:
            active_width, active_height = self._active_ui_size()
            cx, cy = active_width // 2, active_height // 2
            self.create_particles(200, cx, cy, 
                [(255, 215, 0), (255, 200, 40), (0, 255, 221), (255, 255, 255)], speed=12)
        
        self.finalize_run(playtime=self.survival_time // 1000)
    
    def _handle_virus_game_over(self):
        """20 blok yenildi - GAME OVER!"""
        self.game_over = True
        self.game_over_by_virus = True
        self.survival_victory = False
        self.survival_victory = False
        # Gamepad titreşimi - game over (uzun, güçlü)
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(1.0, 1.0, 600)
        except Exception:
            pass
        if self.sound:
            self.sound.play_game_over_sequence()
        self.trigger_screen_shake(intensity=30, duration=60 / 60.0)
        
        print(f"VİRÜS GALİP! {self.consumed_count} blok yenildi.")
        
        if self.effects_enabled:
            active_width, active_height = self._active_ui_size()
            cx, cy = active_width // 2, active_height // 2
            self.create_particles(100, cx, cy, 
                [(255, 50, 50), (100, 0, 0), (50, 150, 50)], speed=8)
        
        self.finalize_run(playtime=self.survival_time // 1000)
    
    def _activate_antivirus(self):
        """Her 5000 puanda: Yenilen sayısı sıfırlanır + tüm enfeksiyonlar temizlenir"""
        print(f"ANTİVİRÜS AKTİF! Yenilen blok sayısı sıfırlandı!")
        
        self.consumed_count = 0
        self.sound.play('level_up')
        self.trigger_screen_shake(intensity=15, duration=30 / 60.0)
        
        # Yeşil flash efekti
        self.antivirus_flash = 500  # 500ms flash
        
        # Tüm enfeksiyonları temizle (blokları silmeden)
        if self.infected_blocks:
            for (x, y) in list(self.infected_blocks.keys()):
                if 0 <= x < self.board_width and 0 <= y < self.board_height:
                    # Enfekte rengi normale çevir
                    if self.board.grid[y][x] != BLACK:
                        self.board.grid[y][x] = CYAN  # Temizlenmiş blok
                    
                    if self.effects_enabled:
                        cell_size = self.get_cell_size()
                        offset_x, offset_y = self.get_board_offset()
                        px = offset_x + x * cell_size + cell_size // 2
                        py = offset_y + y * cell_size + cell_size // 2
                        self.create_particles(8, px, py, [CYAN, WHITE, (100, 255, 100)], speed=4)
            
            self.infected_blocks.clear()
        
        print(f"Tüm enfeksiyonlar temizlendi!")

    def _spawn_virus_if_needed(self):
        """Rastgele bir mevcut bloğa ilk virüsü bulaştır"""
        if len(self.infected_blocks) >= self.max_infected:
            return
        
        # Henüz hiç enfeksiyon yoksa veya spawn zamanı geldiyse
        if self.survival_time - self.last_spawn_time < self.spawn_interval:
            return
        
        # Enfekte edilebilecek blokları bul (mevcut dolu ve enfekte olmayan)
        candidates = []
        for y in range(5, self.board_height):  # Üst 5 satır korumalı
            for x in range(self.board_width):
                if self.board.grid[y][x] != BLACK and (x, y) not in self.infected_blocks:
                    candidates.append((x, y))
        
        if not candidates:
            return
        
        # Alt satırlardan tercihli seçim (alttan yukarı tehdit)
        # Ağırlıklı seçim: alt satırlar daha olası
        weighted = []
        for (x, y) in candidates:
            weight = y  # Alt satırlar (büyük y) daha ağırlıklı
            weighted.extend([(x, y)] * weight)
        
        if weighted:
            target = random.choice(weighted)
            self._infect_block(target[0], target[1])
            self.last_spawn_time = self.survival_time
            
            if self.sound_enabled:
                self.sound.play('rotate')
            
            print(f"Yeni enfeksiyon: ({target[0]}, {target[1]})")

    def _infect_block(self, x, y):
        """Bir bloğu enfekte et"""
        if not (0 <= x < self.board_width and 5 <= y < self.board_height):
            return False
        
        if self.board.grid[y][x] == BLACK:
            return False
        
        if (x, y) in self.infected_blocks:
            return False
        
        if len(self.infected_blocks) >= self.max_infected:
            return False
        
        # Enfekte et
        self.infected_blocks[(x, y)] = self.survival_time
        
        # Bloğu yeşilimsi renge çevir
        self.board.grid[y][x] = (50, 150, 50)  # Enfekte yeşil
        
        return True

    def _update_virus_spread(self, delta_time):
        """Virüslerin komşu bloklara yayılması"""
        if not self.infected_blocks or self.game_over:
            return
        
        if self.survival_time - self.last_spread_time < self.spread_interval:
            return
        
        self.last_spread_time = self.survival_time
        
        # Mevcut enfeksiyonlardan yayılma
        new_infections = []
        current_infected = list(self.infected_blocks.keys())
        random.shuffle(current_infected)
        
        for (vx, vy) in current_infected:
            if len(self.infected_blocks) + len(new_infections) >= self.max_infected:
                break
            
            # Komşu yönler
            neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 4 yön
            if self.diagonal_spread:
                neighbors.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])  # 8 yön
            
            random.shuffle(neighbors)
            
            for dx, dy in neighbors:
                nx, ny = vx + dx, vy + dy
                
                # Sınır kontrolü
                if not (0 <= nx < self.board_width and 5 <= ny < self.board_height):
                    continue
                
                # Zaten enfekte mi?
                if (nx, ny) in self.infected_blocks or (nx, ny) in new_infections:
                    continue
                
                # Boş mu? (sadece dolu bloklara yayıl)
                if self.board.grid[ny][nx] == BLACK:
                    continue
                
                # Yayıl!
                new_infections.append((nx, ny))
                break  # Bu virüs bu turda sadece 1 komşuya yayılsın
        
        # Yeni enfeksiyonları uygula
        for (x, y) in new_infections:
            if self._infect_block(x, y):
                if self.effects_enabled:
                    cell_size = self.get_cell_size()
                    offset_x, offset_y = self.get_board_offset()
                    px = offset_x + x * cell_size + cell_size // 2
                    py = offset_y + y * cell_size + cell_size // 2
                    self.create_particles(5, px, py, [(100, 200, 50), (150, 255, 100)], speed=3)
        
        if new_infections and self.sound_enabled:
            self.sound.play('rotate')

    def _check_consumed_blocks(self):
        """Süresi dolan enfekte blokları yenilir (siler)"""
        if not self.infected_blocks:
            return
        
        current_time = self.survival_time
        to_consume = []
        
        for (x, y), infect_time in list(self.infected_blocks.items()):
            elapsed = current_time - infect_time
            if elapsed >= self.consume_time:
                to_consume.append((x, y))
        
        for (x, y) in to_consume:
            self._consume_block(x, y)

    def _consume_block(self, x, y):
        """Bloğu yenilir - siler ve sayacı artırır"""
        if (x, y) not in self.infected_blocks:
            return
        
        # Enfeksiyon listesinden çıkar
        del self.infected_blocks[(x, y)]
        
        # Bloğu sil
        if 0 <= x < self.board_width and 0 <= y < self.board_height:
            self.board.grid[y][x] = BLACK
            self.board.occupancy[y][x] = False
            self.board.texture_grid[y][x] = None
        
        # Sayacı artır
        self.consumed_count += 1
        self.total_consumed += 1
        
        # Efekt
        if self.effects_enabled:
            cell_size = self.get_cell_size()
            offset_x, offset_y = self.get_board_offset()
            px = offset_x + x * cell_size + cell_size // 2
            py = offset_y + y * cell_size + cell_size // 2
            self.create_particles(15, px, py, 
                [(255, 50, 50), (150, 50, 50), (100, 200, 50)], speed=5)
        
        if self.sound_enabled:
            self.sound.play('drop')
        
        print(f"Blok yenildi! ({x}, {y}) - Toplam: {self.consumed_count}/{self.MAX_CONSUMED}")

    def lock_and_new_piece(self):
        """Parçayı kilitle ve satır temizleme - Survival kurallarıyla"""
        locked_cells = [(x, y) for x, y in self.current_piece.get_cells() if y >= 0]

        # Lock explosion - her hücre için parçacık patlaması
        if self.effects_enabled:
            cell_size = self.get_cell_size()
            offset_x, offset_y = self.get_board_offset()
            piece_cells = self.current_piece.get_cells()
            cm = getattr(self.current_piece, 'color_matrix', None)
            for cell_x, cell_y in piece_cells:
                screen_x = offset_x + cell_x * cell_size + cell_size // 2
                screen_y = offset_y + cell_y * cell_size + cell_size // 2
                cell_color = self.current_piece.color
                if cm is not None:
                    try:
                        lx = cell_x - self.current_piece.x
                        ly = cell_y - self.current_piece.y
                        v = cm[ly][lx]
                        if v is not None:
                            cell_color = v
                    except Exception:
                        pass
                self.create_lock_explosion(x=screen_x, y=screen_y, color=cell_color, cell_size=cell_size)

        lines_cleared = self.board.lock_piece(self.current_piece)

        # Lock-out kontrolü (Tetris Guideline)
        if self.board.is_game_over():
            self.game_over = True
            try:
                from gamepad_manager import get_gamepad_manager
                get_gamepad_manager().rumble(1.0, 1.0, 600)
            except Exception:
                pass
            if self.sound:
                self.sound.play_game_over_sequence()
            self.finalize_run(playtime=self.survival_time // 1000)
            return

        # Satır temizlenmiyorsa blok kilitlenme sesi çal
        if lines_cleared == 0:
            self.sound.play('lock')

        if lines_cleared > 0:
            self.line_clear_animation = 30
            
            # Temizlenen satırlardaki enfeksiyonları kaldır
            cleared_lines = list(self.board.last_cleared_lines)
            self._remove_infections_on_lines(cleared_lines)
            self._shift_infections_after_clear(cleared_lines)

            # Pending rows/colors kaydet (sweep animasyonu için)
            self.line_clear_pending_rows = []
            self.line_clear_pending_colors = {}
            if self.effects_enabled and cleared_lines:
                self.line_clear_pending_rows = list(cleared_lines)
                try:
                    pending_colors = {}
                    if hasattr(self.board, 'last_cleared_colors'):
                        for row in cleared_lines:
                            row_colors = self.board.last_cleared_colors.get(row)
                            if row_colors:
                                pending_colors[row] = list(row_colors)
                    self.line_clear_pending_colors = pending_colors
                except Exception:
                    self.line_clear_pending_colors = {}

            if lines_cleared == 4:
                self.combo_message = "QUADRIX!"
                self.combo_message_time = 120
                self.sound.play('tetris')
                self.trigger_screen_shake(intensity=15, duration=20 / 60.0)
                # Gamepad titreşimi - QUADRIX! (güçlü)
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                except Exception:
                    pass
                
                # Quadrix partikülleri
                if self.effects_enabled:
                    offset_x, offset_y = self.get_board_offset()
                    cell_size = self.get_cell_size()
                    center_x = offset_x + (self.board_width * cell_size) // 2
                    center_y = offset_y + (self.board_height * cell_size) // 2
                    self.create_particles(
                        count=150,
                        x=center_x,
                        y=center_y,
                        colors=[YELLOW, ORANGE, (255, 215, 0), CYAN],
                        speed=10
                    )
            elif lines_cleared >= 2:
                if lines_cleared == 2:
                    clear_name = "DOUBLE!"
                elif lines_cleared == 3:
                    clear_name = "TRIPLE!"
                else:
                    clear_name = f"{lines_cleared}x CLEAR!"
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"{clear_name}  x{combo_count} Combo"
                else:
                    self.combo_message = clear_name
                self.sound.play('line')
                self.combo_message_time = 120
                # Gamepad titreşimi - çoklu satır (orta)
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass
                
                # Çoklu satır partikülleri
                if self.effects_enabled:
                    offset_x, offset_y = self.get_board_offset()
                    cell_size = self.get_cell_size()
                    center_x = offset_x + (self.board_width * cell_size) // 2
                    center_y = offset_y + (self.board_height * cell_size) // 2
                    self.create_particles(
                        count=50 * lines_cleared,
                        x=center_x,
                        y=center_y,
                        colors=[CYAN, MAGENTA, GREEN],
                        speed=6 + lines_cleared
                    )
            else:
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"x{combo_count} Combo!"
                    self.combo_message_time = 90
                else:
                    self.combo_message = ""
                    self.combo_message_time = 0
                self.sound.play('line')
            
            # Standart satır temizleme efektleri (Flash, Wave, Particles)
            if self.effects_enabled:
                cell_size = self.get_cell_size()
                offset_x, offset_y = self.get_board_offset()
                cleared_rows_list = list(self.board.last_cleared_lines) if self.board.last_cleared_lines else cleared_lines
                
                # Flash
                self.line_clear_flash_rows = cleared_rows_list
                self.line_clear_flash_timer = 20
                self.line_clear_glow_alpha = 255
                self.line_clear_flash = True
                
                # Parçacıklar
                try:
                    self.create_line_clear_particles(cleared_rows_list, offset_x, offset_y, cell_size)
                except Exception:
                    pass
                
                # Soldan sağa ışık süpürmesi başlat
                self.line_clear_sweep_rows = cleared_rows_list
                self.line_clear_sweep_progress = 0.0
                self.line_clear_sweep_active = True
                
                # Dalga efekti
                wave_x = offset_x + (self.board_width * cell_size) // 2
                for row in cleared_rows_list:
                    wave_y = offset_y + row * cell_size + cell_size // 2
                    self.line_clear_wave_effects.append({
                        'x': wave_x,
                        'y': wave_y,
                        'radius': 0,
                        'max_radius': self.board_width * cell_size,
                        'alpha': 200,
                        'color': (255, 255, 255),
                        'speed': 15
                    })
                
                # Blok düşme animasyonu başlat
                self._start_block_fall_animation(cleared_rows_list)
                
                # Shake
                if lines_cleared < 4:
                    self.trigger_screen_shake(intensity=3 + lines_cleared * 2, duration=8 / 60.0)

            # Satırları temizle (efekt bilgisi alındıktan sonra)
            self.board.last_cleared_lines = []
            if hasattr(self.board, 'last_cleared_colors'):
                self.board.last_cleared_colors = {}

            if self.achievement_manager:
                new_achievements = self.achievement_manager.update_stats(
                    score=self.board.score, lines=self.board.lines_cleared,
                    level=self.board.level, tetrises=self.board.tetrises,
                    combo=self.board.combo,
                    game_mode=self.game_mode,
                )
                for ach_id in new_achievements:
                    achievement = self.achievement_manager.get_achievement(ach_id)
                    if achievement:
                        self.achievement_notifications.append({
                            'achievement': achievement,
                            'time': pygame.time.get_ticks(),
                            'alpha': 255,
                        })
                        self.sound.play('tetris')
        else:
            self.board.combo = 0

        self.current_piece = self.next_piece_queue.pop(0)
        self._skip_hidden_rows(self.current_piece)
        self.next_piece_queue.append(self.spawn_new_piece())
        # Lock-delay state sıfırla
        self.grounded = False
        self.lock_timer = 0
        self.lock_reset_count = 0
        self.can_hold = True
        self.can_hold2 = True
        self.fall_speed = self.get_current_speed()
        self.apply_theme_to_pieces()

    def _remove_infections_on_lines(self, cleared_rows):
        """Temizlenen satırlardaki enfeksiyonları kaldır"""
        if not cleared_rows:
            return
        cleared_set = set(cleared_rows)
        to_remove = [(x, y) for (x, y) in self.infected_blocks if y in cleared_set]
        for pos in to_remove:
            del self.infected_blocks[pos]
        
        if to_remove:
            print(f"{len(to_remove)} enfeksiyon satır temizliğiyle yok edildi!")

    def _shift_infections_after_clear(self, cleared_rows):
        """Satır temizliğinden sonra enfeksiyonların pozisyonlarını güncelle"""
        if not cleared_rows or not self.infected_blocks:
            return
        
        sorted_cleared = sorted(cleared_rows, reverse=True)
        new_infections = {}
        
        for (x, y), infect_time in self.infected_blocks.items():
            shift_down = sum(1 for cleared_y in sorted_cleared if y < cleared_y)
            new_y = y + shift_down
            
            if 0 <= new_y < self.board_height:
                new_infections[(x, new_y)] = infect_time
        
        self.infected_blocks = new_infections

    def draw_mode_info(self, info_x, info_y):
        """Sol panel - Survival bilgileri"""
        # Bu mod sağ panelde bilgi gösteriyor, sol panel boş bırakılabilir
        return 0

    def _get_survival_infection_overlay(self, cell_size: int, color, bar_width: int, bar_color) -> pygame.Surface:
        cache = getattr(self, '_survival_infection_overlay_cache', None)
        order = getattr(self, '_survival_infection_overlay_cache_order', None)
        if cache is None or order is None:
            cache = {}
            order = []
            self._survival_infection_overlay_cache = cache
            self._survival_infection_overlay_cache_order = order
        size = max(1, int(cell_size))
        key = (size, tuple(color), max(0, min(size, int(bar_width))), tuple(bar_color))
        cached = cache.get(key)
        if cached is not None:
            try:
                order.remove(key)
            except ValueError:
                pass
            order.append(key)
            return cached

        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(overlay, color, (0, 0, size, size), border_radius=4)
        center = (size // 2, size // 2)
        pygame.draw.circle(overlay, (50, 150, 50, 255), center, size // 4)
        pygame.draw.circle(overlay, (200, 255, 200, 255), center, size // 6)
        if bar_width > 0:
            pygame.draw.rect(overlay, bar_color, (0, 0, int(bar_width), 4))
        cache[key] = overlay
        order.append(key)
        while len(order) > 160:
            old_key = order.pop(0)
            cache.pop(old_key, None)
        return overlay

    def draw_mode_overlay(self):
        """Survival modu overlay - Enfekte bloklar ve UI panelleri"""
        if self.game_over:
            return
        
        from retro_style import retro_style
        active_width, active_height = self._active_ui_size()
        
        cell_size = self.get_cell_size()
        offset_x, offset_y = self.get_board_offset()
        current_time = self.survival_time
        
        # Antivirus flash efekti
        if self.antivirus_flash > 0:
            flash_alpha = int(100 * (self.antivirus_flash / 500))
            flash_surf = self._get_solid_alpha_surface((active_width, active_height), (100, 255, 100, flash_alpha))
            self.screen.blit(flash_surf, (0, 0))
        
        # === ENFEKSİYON OVERLAY'LERİ ===
        for (x, y), infect_time in self.infected_blocks.items():
            if not (0 <= x < self.board_width and 0 <= y < self.board_height):
                continue
            
            px = offset_x + x * cell_size
            py = offset_y + y * cell_size
            
            # Kalan süre hesapla
            elapsed = current_time - infect_time
            remaining = max(0, self.consume_time - elapsed)
            progress = elapsed / self.consume_time  # 0 -> 1
            
            # Arka plan - kalan süreye göre renk
            if progress < 0.5:
                color = (100, 200, 50, 150)  # Yeşil
            elif progress < 0.75:
                color = (200, 200, 50, 180)  # Sarı
            else:
                color = (200, 50, 50, 200)  # Kırmızı
                # Yanıp sönme
                if (pygame.time.get_ticks() // 200) % 2 == 0:
                    color = (255, 100, 100, 220)

            # Zamanlayıcı bar (üstte)
            bar_height = 4
            bar_width = int(cell_size * (1 - progress))
            bar_color = (100, 255, 100) if progress < 0.5 else (255, 200, 50) if progress < 0.75 else (255, 50, 50)
            overlay = self._get_survival_infection_overlay(cell_size, color, bar_width, bar_color)
            self.screen.blit(overlay, (px, py))
        
        # === SAĞ PANEL - SURVIVAL BİLGİLERİ ===
        self._draw_survival_panel()

    def _draw_survival_panel(self):
        """Sağ üst köşede survival bilgi paneli - BÜYÜK VE GÜZELLEŞTİRİLMİŞ

        P1-4 (Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu): panel içeriği
        ölç-önce dikey bütçeye bağlanır. Eski kod sabit s() ritmiyle (içerik
        toplamı ~s(340)) çiziyordu; %175/%200 preset + kısa pencere
        yüksekliği kombinasyonunda panel zemini (floor s(300) / ekran payı)
        içeriği tutamıyor, son bloklar çerçevenin altına taşıyordu. Yeni
        sözleşme (game.py stats bloğu / Hardcore panel deseni):
        1. Panel boyutu RenderGeometry safe rect'ine göre kısıtlanır; kısıt
           clamp'ten ÖNCE uygulanır (Rect.clamp küçültmez — büyük panel
           clamp'te yine taşar).
        2. Blok yükseklikleri gerçek font ölçümüyle dinamik üretilir
           (get_height / font.size — plan aşamasında Surface tahsisi yok).
        3. Kuantalı flow ladder (1.0→0.52) ritmi + font tabanlarını bütçeye
           sığdırır; yetmezse opsiyonel bloklar (antivirus → enfeksiyon →
           virüs seviyesi) düşürülür. Zorunlu bloklar (başlık/süre/tüketilen)
           asla düşmez.
        4. Etiketler inner_w'ye, antivirus bilgi satırı etiketle ÇAKIŞMAYAN
           paya ellipsis'lenir (Wide Arena C1 dersi: sağdan hizalanan değer
           sol etiketi ezebilir).
        Demo notu: v2 eşlemesi — glow/gradient/ayırıcı/title yüzeyleri artık
        önbellekli (kare-başı Surface tahsisi yasağı, CLAUDE.md); eski demo
        kodunda bunlar her kare yeniden üretiliyordu.
        """
        from retro_style import retro_style
        from localization import t

        ui_scale = self._survival_panel_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        active_width, active_height = self._active_ui_size()

        # Metinler ölçüm aşaması için önce toplanır (draw yalnız plan tüketir;
        # kare-başı Surface tahsisi yasak — CLAUDE.md).
        title_text = t('mode_survival')
        time_label_text = t('survival_panel_time_left')
        level_label_text = t('survival_panel_virus_level')
        consumed_label_text = t('survival_panel_consumed')
        infect_label_text = t('survival_panel_active_infection')
        av_label_text = t('survival_panel_antivirus')
        next_av = self.last_antivirus_score + self.ANTIVIRUS_SCORE
        current_score = self.board.score
        score_to_av = next_av - current_score
        if score_to_av > 0:
            av_info_text = t('survival_panel_points_remaining', points=score_to_av)
            av_info_bold = False
        else:
            av_info_text = t('survival_panel_ready')
            av_info_bold = True

        # Panel boyutları - BÜYÜTÜLDÜ
        panel_w = min(s(260), max(s(220), int(active_width) - s(24)))
        panel_h = min(s(390), max(s(300), int(active_height) - s(24)))

        # Board konumunu al
        board_x, board_y = self.get_board_offset()

        # P1-4: safe rect varsa panel BOYUTU önce ona göre kısıtlanır, sonra
        # konum clamp'lenir; geometry yoksa mevcut tam-ekran davranışı korunur.
        safe_rect = get_render_safe_rect(self.screen)
        bounds = safe_rect if safe_rect is not None else pygame.Rect(0, 0, int(active_width), int(active_height))
        panel_w = min(panel_w, max(s(120), bounds.width - 2 * s(8)))
        panel_h = min(panel_h, max(s(160), bounds.height - 2 * s(8)))

        # KONUMLANDIRMA (Kullanıcı isteği: Board'un soluna yapışık)
        # Panel sağ kenarı = Board sol kenarı - biraz boşluk
        panel_x = board_x - panel_w - s(15)
        # Üst kenarı board ile aynı hizada
        panel_y = board_y
        panel_x = max(s(8), min(panel_x, int(active_width) - panel_w - s(8)))
        panel_y = max(s(8), min(panel_y, int(active_height) - panel_h - s(8)))

        # === ANA PANEL ===
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        if safe_rect is not None:
            panel_rect = panel_rect.clamp(safe_rect)
        self._survival_panel_rect = panel_rect

        # Tehlike seviyesine göre border rengi ve glow
        danger_ratio = self.consumed_count / self.MAX_CONSUMED
        if danger_ratio < 0.4:
            border_color = (0, 255, 180)    # Cyan-yeşil
        elif danger_ratio < 0.7:
            border_color = (255, 200, 50)   # Sarı
        else:
            border_color = (255, 50, 80)    # Kırmızı

        # === SOLID ARKA PLAN (Transparan değil) ===
        # Dış glow efekti
        glow_rect = panel_rect.inflate(s(10), s(10))
        glow_surf = self._get_rounded_rect_surface(glow_rect.size, (*border_color, 50), border_radius=16)
        self.screen.blit(glow_surf, glow_rect.topleft)

        # Ana arka plan - SOLID koyu renk (opak)
        pygame.draw.rect(self.screen, (18, 22, 40), panel_rect, border_radius=12)

        # İç gradient efekti için üst kısım biraz daha açık
        inner_rect = panel_rect.inflate(-s(4), -s(4))
        grad_h = s(50)
        grad_key = (int(inner_rect.width), int(grad_h))
        if getattr(self, '_survival_panel_gradient_key', None) != grad_key:
            gradient_surf = pygame.Surface((inner_rect.width, grad_h), pygame.SRCALPHA)
            for i in range(grad_h):
                alpha = int(25 * (1 - i / max(1, grad_h)))
                pygame.draw.line(gradient_surf, (100, 120, 150, alpha), (0, i), (inner_rect.width, i))
            self._survival_panel_gradient_surface = gradient_surf
            self._survival_panel_gradient_key = grad_key
        gradient_surf = self._survival_panel_gradient_surface
        self.screen.blit(gradient_surf, (inner_rect.x, inner_rect.y))

        # Ana çerçeve - kalın ve parlak
        pygame.draw.rect(self.screen, border_color, panel_rect, 3, border_radius=12)

        # İç çerçeve - ince dekoratif
        inner_border = panel_rect.inflate(-8, -8)
        inner_border_color = (border_color[0] // 2, border_color[1] // 2, border_color[2] // 2)
        pygame.draw.rect(self.screen, inner_border_color, inner_border, 1, border_radius=10)

        # Köşe süslemeleri kaldırıldı (Kullanıcı isteği)

        # === İÇERİK BÜTÇESİ (P1-4) =========================================
        # Ölç-önce plan: her (düşürme, flow) adayı yalnız font ölçümüyle
        # değerlendirilir — Surface tahsisi yok. En az blok düşüren, sonra en
        # büyük flow'lu aday seçilir (bilgi kaybı minimize).
        cx = panel_rect.x + s(20)
        inner_w = panel_w - s(40)
        pad_top = s(18)
        pad_bottom = s(14)
        content_budget = max(s(60), panel_h - pad_top - pad_bottom)

        # Opsiyonel blok grupları — düşürme sırası (en az kritik önce).
        optional_groups = ('antivirus', 'infection', 'virus_level')

        def _build_content_plan(flow, dropped):
            """Bir (flow, dropped) adayı için blok planı (yalnız ölçüm)."""
            fs = lambda v, minimum=1: max(minimum, int(round(v * ui_scale * flow)))
            pick_font = lambda size, bold=False, minimum=9: retro_style.get_font(
                max(max(8, int(round(minimum * flow))), fs(size)), bold=bold)

            title_font = pick_font(24, bold=True, minimum=12)
            time_label_font = pick_font(13, bold=True)
            time_font = pick_font(38, bold=True, minimum=18)
            label_font = pick_font(13, bold=True)
            small_font = pick_font(11, bold=av_info_bold)
            level_font = pick_font(14, bold=True)

            # Yatay uygunluk: antivirus bilgi satırı etiket payıyla sınırlı.
            av_label_fit = self._ellipsis_text(av_label_text, label_font, inner_w)
            av_info_max_w = max(fs(30), inner_w - label_font.size(av_label_fit)[0] - fs(8))
            av_info_fit = self._ellipsis_text(av_info_text, small_font, av_info_max_w)

            blocks = []

            def _add_block(name, advance, content_h, gap):
                # Dinamik satır yüksekliği: ilerleme tabanı ile ölçülen içerik
                # yüksekliğinin büyüğü (rapor: 'satır yüksekliği dinamik olsun').
                blocks.append((name, max(advance, content_h + gap)))

            # Zorunlu bloklar: başlık, ayırıcı, süre, tüketilen göstergesi.
            _add_block('title', fs(42), title_font.get_height(), fs(8))
            _add_block('separator', fs(16), fs(2), fs(6))
            _add_block('time_label', fs(24), time_label_font.get_height(), fs(6))
            _add_block('time_value', fs(48), time_font.get_height(), fs(8))
            if 'virus_level' not in dropped:
                _add_block('level_label', fs(24), label_font.get_height(), fs(6))
                _add_block('level_boxes', fs(32), fs(20), fs(10))
            _add_block('consumed_label', fs(24), label_font.get_height(), fs(6))
            _add_block('consumed_bar', fs(32), fs(22), fs(8))
            if 'infection' not in dropped:
                _add_block('infect_label', fs(24), label_font.get_height(), fs(6))
                _add_block('infect_bar', fs(32), fs(22), fs(8))
            if 'antivirus' not in dropped:
                _add_block('av_label', fs(20), max(label_font.get_height(), small_font.get_height()), fs(4))
                _add_block('av_bar', fs(22), fs(22), 0)

            return {
                'flow': flow,
                'dropped': dropped,
                'fs': fs,
                'fonts': {
                    'title': title_font,
                    'time_label': time_label_font,
                    'time_value': time_font,
                    'label': label_font,
                    'small': small_font,
                    'level': level_font,
                },
                'texts': {
                    'title': self._ellipsis_text(title_text, title_font, inner_w),
                    'time_label': self._ellipsis_text(time_label_text, time_label_font, inner_w),
                    'level_label': self._ellipsis_text(level_label_text, label_font, inner_w),
                    'consumed_label': self._ellipsis_text(consumed_label_text, label_font, inner_w),
                    'infect_label': self._ellipsis_text(infect_label_text, label_font, inner_w),
                    'av_label': av_label_fit,
                    'av_info': av_info_fit,
                },
                'blocks': blocks,
                'total_h': sum(block_h for _name, block_h in blocks),
            }

        chosen_plan = None
        for drop_count in range(len(optional_groups) + 1):
            dropped = frozenset(optional_groups[:drop_count])
            for flow_candidate in (1.0, 0.88, 0.76, 0.64, 0.52):
                candidate = _build_content_plan(flow_candidate, dropped)
                if candidate['total_h'] <= content_budget:
                    chosen_plan = candidate
                    break
            if chosen_plan is not None:
                break
        if chosen_plan is None:
            # Hiçbir aday sığmadı: en küçük flow + yalnız zorunlu bloklar
            # (Hardcore panel sözleşmesi — satırlar en küçük planla çizilir,
            # sessiz kayıp olmaz; taşma bilinçli olarak kabul edilir).
            chosen_plan = _build_content_plan(0.52, frozenset(optional_groups))

        fs = chosen_plan['fs']
        fonts = chosen_plan['fonts']
        texts = chosen_plan['texts']
        block_heights = dict(chosen_plan['blocks'])
        block_rects = {}

        # İç padding (dikey bütçe pad_top/pad_bottom ile aynı eksende)
        cy = panel_rect.y + pad_top

        # === BAŞLIK - Büyük ve neon efektli ===
        # Glow kopyaları + ana yüzey tek anahtarla önbelleklenir (dil/danger
        # rengi sınırlı küme üretir; kare-başı 4x copy() yasağı — CLAUDE.md).
        title_font = fonts['title']
        title_key = (id(title_font), texts['title'], tuple(border_color[:3]))
        if getattr(self, '_survival_title_key', None) != title_key:
            glow_base = render_text(title_font, texts['title'], True, border_color)
            title_glow = glow_base.copy()
            title_glow.set_alpha(50)
            self._survival_title_glow_surface = title_glow
            self._survival_title_surface = render_text(title_font, texts['title'], True, (255, 255, 255))
            self._survival_title_key = title_key
        for offset in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
            self.screen.blit(self._survival_title_glow_surface, (cx + offset[0], cy + offset[1]))

        # Ana başlık
        self.screen.blit(self._survival_title_surface, (cx, cy))
        block_rects['title'] = pygame.Rect(
            cx, cy, self._survival_title_surface.get_width(), self._survival_title_surface.get_height())
        cy += block_heights['title']

        # Ayırıcı çizgi - gradient efektli
        sep_h = fs(2)
        sep_key = (int(inner_w), int(sep_h), tuple(border_color[:3]))
        if getattr(self, '_survival_separator_key', None) != sep_key:
            sep_surf = pygame.Surface((inner_w, sep_h), pygame.SRCALPHA)
            half_w = max(1, inner_w / 2)
            for i in range(inner_w):
                alpha = int(200 * (1 - abs(i - half_w) / half_w))
                color = (*border_color[:3], max(50, alpha))
                pygame.draw.line(sep_surf, color, (i, 0), (i, sep_h))
            self._survival_separator_surface = sep_surf
            self._survival_separator_key = sep_key
        self.screen.blit(self._survival_separator_surface, (cx, cy))
        block_rects['separator'] = pygame.Rect(cx, cy, inner_w, sep_h)
        cy += block_heights['separator']

        # === KALAN SÜRE - Büyük ve belirgin ===
        time_left = max(0, self.GAME_DURATION - self.survival_time)
        minutes = int(time_left // 60000)
        seconds = int((time_left % 60000) // 1000)

        time_label = render_text(fonts['time_label'], texts['time_label'], True, (180, 190, 210))
        self.screen.blit(time_label, (cx, cy))
        block_rects['time_label'] = pygame.Rect(cx, cy, time_label.get_width(), time_label.get_height())
        cy += block_heights['time_label']

        # Süre rengi ve animasyonu
        if time_left < 30000:
            flash = (pygame.time.get_ticks() // 200) % 2 == 0
            time_color = (255, 50, 80) if flash else (200, 80, 100)
        elif time_left < 60000:
            time_color = (255, 200, 50)
        else:
            time_color = (100, 255, 180)

        time_val = fonts['time_value'].render(f"{minutes}:{seconds:02d}", True, time_color)
        self.screen.blit(time_val, (cx, cy))
        block_rects['time_value'] = pygame.Rect(cx, cy, time_val.get_width(), time_val.get_height())
        cy += block_heights['time_value']

        # === VİRÜS SEVİYESİ - İkonlu ===
        if 'virus_level' not in chosen_plan['dropped']:
            level_label = render_text(fonts['label'], texts['level_label'], True, (180, 190, 210))
            self.screen.blit(level_label, (cx, cy))
            block_rects['level_label'] = pygame.Rect(cx, cy, level_label.get_width(), level_label.get_height())
            cy += block_heights['level_label']

            # Seviye göstergesi - 5 kutu
            box_w = (inner_w - fs(30)) // 5
            box_h = fs(20)
            level_colors = [(100, 255, 100), (180, 255, 80), (255, 220, 50), (255, 140, 50), (255, 50, 80)]

            boxes_rect = pygame.Rect(cx, cy, inner_w, box_h)
            for i in range(5):
                bx = cx + i * (box_w + fs(6))
                is_active = i < self.virus_level

                if is_active:
                    # Aktif seviye - renkli ve parlak
                    pygame.draw.rect(self.screen, level_colors[i], (bx, cy, box_w, box_h), border_radius=5)
                    # Üst parlama efekti
                    shine_surf = self._get_solid_alpha_surface((max(1, box_w - fs(4)), fs(6)), (255, 255, 255, 100))
                    self.screen.blit(shine_surf, (bx + fs(2), cy + fs(2)))
                else:
                    # Pasif seviye - koyu
                    pygame.draw.rect(self.screen, (35, 42, 60), (bx, cy, box_w, box_h), border_radius=5)

                # Çerçeve
                pygame.draw.rect(self.screen, (60, 70, 90), (bx, cy, box_w, box_h), 1, border_radius=5)

            # Seviye yazısı
            level_color = level_colors[min(self.virus_level - 1, 4)]
            level_text = fonts['level'].render(f"LVL {self.virus_level}", True, level_color)
            self.screen.blit(level_text, (cx + inner_w - level_text.get_width(), cy + fs(2)))
            block_rects['level_boxes'] = boxes_rect
            cy += block_heights['level_boxes']

        # === YENİLEN BLOKLAR - KRİTİK GÖSTERGE ===
        consumed_label = render_text(fonts['label'], texts['consumed_label'], True, (180, 190, 210))
        self.screen.blit(consumed_label, (cx, cy))
        block_rects['consumed_label'] = pygame.Rect(cx, cy, consumed_label.get_width(), consumed_label.get_height())
        cy += block_heights['consumed_label']

        # Bar
        bar_h = fs(22)
        consumed_bar_rect = pygame.Rect(cx, cy, inner_w, bar_h)
        pygame.draw.rect(self.screen, (25, 30, 48), consumed_bar_rect, border_radius=11)
        pygame.draw.rect(self.screen, (50, 58, 75), consumed_bar_rect, 1, border_radius=11)

        fill_ratio = self.consumed_count / self.MAX_CONSUMED
        fill_w = int(inner_w * fill_ratio)
        fill_color = (100, 255, 100) if fill_ratio < 0.4 else (255, 200, 50) if fill_ratio < 0.7 else (255, 50, 80)

        if fill_w > 0:
            pygame.draw.rect(self.screen, fill_color, (cx, cy, fill_w, bar_h), border_radius=11)
            # Işıltı efekti
            shine_surf = self._get_solid_alpha_surface((max(1, fill_w - fs(4)), fs(7)), (255, 255, 255, 90))
            self.screen.blit(shine_surf, (cx + fs(2), cy + fs(2)))

        # Sayı (bar içinde, ortalı)
        consumed_text = fonts['label'].render(
            f"{self.consumed_count} / {self.MAX_CONSUMED}", True, (255, 255, 255))
        text_rect = consumed_text.get_rect(center=(cx + inner_w // 2, cy + bar_h // 2))
        self.screen.blit(consumed_text, text_rect)
        block_rects['consumed_bar'] = consumed_bar_rect
        cy += block_heights['consumed_bar']

        # === AKTİF ENFEKSİYONLAR ===
        if 'infection' not in chosen_plan['dropped']:
            infect_label = render_text(fonts['label'], texts['infect_label'], True, (180, 190, 210))
            self.screen.blit(infect_label, (cx, cy))
            block_rects['infect_label'] = pygame.Rect(cx, cy, infect_label.get_width(), infect_label.get_height())
            cy += block_heights['infect_label']

            infect_ratio = len(self.infected_blocks) / max(1, self.max_infected)
            infect_w = int(inner_w * infect_ratio)

            infect_bar_rect = pygame.Rect(cx, cy, inner_w, bar_h)
            pygame.draw.rect(self.screen, (25, 30, 48), infect_bar_rect, border_radius=11)
            pygame.draw.rect(self.screen, (50, 58, 75), infect_bar_rect, 1, border_radius=11)

            infect_color = (100, 200, 80) if infect_ratio < 0.5 else (255, 200, 50) if infect_ratio < 0.8 else (255, 100, 50)

            if infect_w > 0:
                pygame.draw.rect(self.screen, infect_color, (cx, cy, infect_w, bar_h), border_radius=11)
                shine_surf = self._get_solid_alpha_surface((max(1, infect_w - fs(4)), fs(7)), (255, 255, 255, 90))
                self.screen.blit(shine_surf, (cx + fs(2), cy + fs(2)))

            infect_text = fonts['label'].render(
                f"{len(self.infected_blocks)} / {self.max_infected}", True, (255, 255, 255))
            text_rect = infect_text.get_rect(center=(cx + inner_w // 2, cy + bar_h // 2))
            self.screen.blit(infect_text, text_rect)
            block_rects['infect_bar'] = infect_bar_rect
            cy += block_heights['infect_bar']

        # === ANTİVİRÜS DURUMU ===
        if 'antivirus' not in chosen_plan['dropped']:
            av_progress = (current_score - self.last_antivirus_score) / self.ANTIVIRUS_SCORE
            av_progress = min(1.0, max(0, av_progress))

            av_label = render_text(fonts['label'], texts['av_label'], True, (180, 190, 210))
            self.screen.blit(av_label, (cx, cy))

            # Puan bilgisi (sağda) — etiketle çakışmayan paya ellipsis'lenmiş
            av_info = fonts['small'].render(
                texts['av_info'], True, (100, 255, 150) if av_info_bold else (140, 150, 170))
            self.screen.blit(av_info, (cx + inner_w - av_info.get_width(), cy + fs(2)))
            block_rects['av_label'] = pygame.Rect(cx, cy, av_label.get_width(), av_label.get_height())
            block_rects['av_info'] = pygame.Rect(
                cx + inner_w - av_info.get_width(), cy + fs(2), av_info.get_width(), av_info.get_height())
            cy += block_heights['av_label']

            av_bar_rect = pygame.Rect(cx, cy, inner_w, bar_h)
            pygame.draw.rect(self.screen, (25, 30, 48), av_bar_rect, border_radius=11)
            pygame.draw.rect(self.screen, (50, 58, 75), av_bar_rect, 1, border_radius=11)

            av_w = int(inner_w * av_progress)
            av_color = (0, 200, 255) if av_progress < 1.0 else (100, 255, 150)

            if av_w > 0:
                pygame.draw.rect(self.screen, av_color, (cx, cy, av_w, bar_h), border_radius=11)
                shine_surf = self._get_solid_alpha_surface((max(1, av_w - fs(4)), fs(7)), (255, 255, 255, 90))
                self.screen.blit(shine_surf, (cx + fs(2), cy + fs(2)))

            av_text = fonts['label'].render(f"{int(av_progress * 100)}%", True, (255, 255, 255))
            text_rect = av_text.get_rect(center=(cx + inner_w // 2, cy + bar_h // 2))
            self.screen.blit(av_text, text_rect)
            block_rects['av_bar'] = av_bar_rect

        # P1-4: gerçek blit rect'leri containment testleri için kaydedilir.
        content_bottom = max(
            (rect.bottom for rect in block_rects.values()),
            default=panel_rect.y + pad_top,
        )
        self._survival_hud_rects = {
            'panel': panel_rect,
            'bounds': pygame.Rect(bounds),
            'flow': chosen_plan['flow'],
            'dropped': tuple(sorted(chosen_plan['dropped'])),
            'content_budget': int(content_budget),
            'content_bottom': int(content_bottom),
            'blocks': block_rects,
        }

    def restart(self):
        super().restart()
        self._init_survival_state()


class CascadeMode(Game):
    """Cascade Mode - Satır temizlenince bloklar aşağı düşüyor (gravity effect)
    
    NASIL ÇALIŞIR:
    1. Normal Quadrix gibi parça yerleştir
    2. Satır dolduğunda temizlenir
    3. ÜSTTEKİ BLOKLAR AŞAĞI DÜŞER (gravity)
    4. Düşerken YENİ satırlar dolarsa → TEKRAR temizlenir!
    5. Bu zincir devam eder → Her seviye BONUS PUAN!
    
    ÖRNEK:
    Level 1: 1 satır temizle → 100 puan
    Level 2: Düşen bloklar 2 satır daha doldurdu → 200 x 2 = 400 puan
    Level 3: Tekrar 1 satır doldu → 100 x 3 = 300 puan
    TOPLAM: 800 bonus puan! 🎉
    """
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, settings_manager=None, user_manager=None, game_mode='cascade', score_manager=None, sound_manager=None):
        """Cascade mode'u başlat"""
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
        )
        
        # Cascade özellikleri
        self.cascade_animations = []  # Düşen blok animasyonları
        self.cascade_bonus = 0  # Cascade combo bonusu
        self.last_cascade_level = 0  # Son cascade seviyesi (görsel için)
        self.cascade_message_time = 0  # Cascade mesajı gösterme süresi
        # Minimal HUD etiketi için fontlar
        self._cascade_hud_font = ui_style.get_font(26, bold=False)
        self._cascade_hud_font_small = ui_style.get_font(18, bold=False)

    def restart(self):
        """Clear cascade specific state on restart to prevent lingering animations and bonuses."""
        super().restart()
        self.cascade_animations = []
        self.cascade_bonus = 0
        self.last_cascade_level = 0
        self.cascade_message_time = 0
    
    def update(self, delta_time):
        """Cascade mode güncelleme - mesaj zamanlayıcısı ile"""
        # Cascade mesaj zamanlayıcısını azalt
        if self.cascade_message_time > 0:
            self.cascade_message_time -= 1
        
        # Normal güncelleme
        super().update(delta_time)
        
    def lock_and_new_piece(self):
        """Parçayı kilitle - Cascade effect ile"""
        # Lock explosion - her hücre için parçacık patlaması
        if self.effects_enabled:
            cell_size = self.get_cell_size()
            offset_x, offset_y = self.get_board_offset()
            piece_cells = self.current_piece.get_cells()
            cm = getattr(self.current_piece, 'color_matrix', None)
            for cell_x, cell_y in piece_cells:
                screen_x = offset_x + cell_x * cell_size + cell_size // 2
                screen_y = offset_y + cell_y * cell_size + cell_size // 2
                cell_color = self.current_piece.color
                if cm is not None:
                    try:
                        lx = cell_x - self.current_piece.x
                        ly = cell_y - self.current_piece.y
                        v = cm[ly][lx]
                        if v is not None:
                            cell_color = v
                    except Exception:
                        pass
                self.create_lock_explosion(x=screen_x, y=screen_y, color=cell_color, cell_size=cell_size)

        # Parçayı tahtaya yerleştir (occupancy/texture/owners ile tutarlı)
        piece = self.current_piece
        # Top-out: görünür alanın üstünde (y<0) yazılamayan dolu hücre kaldı mı?
        _overflow_top = False
        for ly, row in enumerate(piece.shape):
            for lx, c in enumerate(row):
                if c and (piece.y + ly) < 0:
                    _overflow_top = True
                    break
            if _overflow_top:
                break
        piece_w = len(piece.shape[0]) if getattr(piece, 'shape', None) else 0
        piece_h = len(piece.shape) if getattr(piece, 'shape', None) else 0
        for ly, row in enumerate(piece.shape):
            for lx, c in enumerate(row):
                if not c:
                    continue
                x = piece.x + lx
                y = piece.y + ly
                if 0 <= x < self.board_width and 0 <= y < self.board_height:
                    self.board.grid[y][x] = piece.color
                    self.board.occupancy[y][x] = True
                    self.board.texture_grid[y][x] = None
                    try:
                        self.board.gold[y][x] = bool(getattr(piece, 'is_gold', False))
                    except Exception:
                        pass
                    try:
                        self.board.owners[y][x] = getattr(piece, 'name', None)
                    except Exception:
                        pass
        
        # İlk lock sesi için satır durumunu takip et
        _any_lines_cleared = False

        # Satırları kontrol et ve cascade başlat
        total_cleared = 0
        cascade_level = 0
        
        while True:
            # Dolu satırları bul (occupancy üzerinden)
            lines_to_clear: list[int] = []
            for y in range(self.board_height):
                if all(self.board.occupancy[y][x] for x in range(self.board_width)):
                    lines_to_clear.append(y)

            if not lines_to_clear:
                break

            # Pending rows/colors kaydet (sweep animasyonu için)
            if self.effects_enabled:
                self.line_clear_pending_rows = list(lines_to_clear)
                pending_colors = {}
                for row in lines_to_clear:
                    row_colors = [self.board.grid[row][x] for x in range(self.board_width)]
                    pending_colors[row] = list(row_colors)
                self.line_clear_pending_colors = pending_colors

            # === Satır temizleme animasyonu (Game'dekiyle uyumlu) ===
            # Not: Satırlar hemen silinecek olsa da flash/wave overlay'leri
            # ekranda temizleme hissini verir.
            if self.effects_enabled:
                cell_size = self.get_cell_size()
                board_offset_x, board_offset_y = self.get_board_offset()
                cleared_rows = list(lines_to_clear)

                # Flash overlay
                self.line_clear_flash_rows = cleared_rows
                self.line_clear_flash_timer = 20
                self.line_clear_glow_alpha = 255

                # Dalga efektleri
                wave_x = board_offset_x + (self.board_width * cell_size) // 2
                for row in cleared_rows:
                    wave_y = board_offset_y + row * cell_size + cell_size // 2
                    self.line_clear_wave_effects.append(
                        {
                            'x': wave_x,
                            'y': wave_y,
                            'radius': 0,
                            'max_radius': self.board_width * cell_size,
                            'alpha': 200,
                            'color': (255, 255, 255),
                            'speed': 15,
                        }
                    )

                # Parçacıklar
                try:
                    self.create_line_clear_particles(cleared_rows, board_offset_x, board_offset_y, cell_size)
                except Exception:
                    pass

                # Soldan sağa ışık süpürmesi başlat
                self.line_clear_sweep_rows = cleared_rows
                self.line_clear_sweep_progress = 0.0
                self.line_clear_sweep_active = True

                # Animasyon frame sayacı
                self.line_clear_animation = 30
                self.line_clear_flash = True

                # Hafif shake
                try:
                    if len(cleared_rows) < 4:
                        self.trigger_screen_shake(intensity=3 + len(cleared_rows) * 2, duration=8 / 60.0)
                    else:
                        self.trigger_screen_shake(intensity=12, duration=14 / 60.0)
                except Exception:
                    pass

            _any_lines_cleared = True
            cascade_level += 1
            total_cleared += len(lines_to_clear)

            # Cascade bonusu hesapla (seviye bazlı)
            bonus_multiplier = cascade_level
            level_bonus = len(lines_to_clear) * 100 * bonus_multiplier
            self.cascade_bonus += level_bonus

            # Flash animasyonu
            self.line_clear_flash = True
            self.flash_timer = 0

            # Parçacık efekti - her seviyede daha fazla
            if self.effects_enabled:
                cell_size = self.get_cell_size()
                board_offset_x, board_offset_y = self.get_board_offset()
                particle_count = 20 + (cascade_level * 10)
                self.create_cascade_particles(board_offset_x, board_offset_y, cell_size, particle_count, cascade_level)

            # Satırları sil (tüm grid'lerde) ve ardından per-column gravity uygula
            self.apply_cascade_gravity(lines_to_clear)
            try:
                self.board.apply_gravity()
            except Exception:
                pass
            
            # Base game düşme animasyonunu başlat
            try:
                self._start_block_fall_animation(lines_to_clear)
            except Exception:
                pass

            # Ses efekti - seviyeye göre farklı
            if cascade_level == 1:
                self.sound.play('line' if len(lines_to_clear) < 4 else 'tetris')
            elif cascade_level == 2:
                self.sound.play('line')
                self.sound.play('rotate')
            else:
                self.sound.play('tetris')

            # Quadrix kontrolü
            if len(lines_to_clear) >= 4:
                self.board.tetrises += 1
                # Gamepad titreşimi - QUADRIX!
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                except Exception:
                    pass
            elif len(lines_to_clear) >= 2:
                # Gamepad titreşimi - multi-line
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass
        
        # Cascade seviyesini kaydet (görsel için)
        if cascade_level > 0:
            self.last_cascade_level = cascade_level
            # Daha minimal bildirim için daha kısa süre
            self.cascade_message_time = 90  # ~1.5 saniye
        
        # Lock-out kuralı: cascade sonrası görünür row 0 dolu kaldıysa ya da tepe
        # taşması (top-out) varsa game-over (Board.lock_piece ile aynı kural;
        # negatif/gizli satır "dokunma" mantığı kaldırıldı).
        if _overflow_top or any(self.board.occupancy[0][x] for x in range(self.board_width)):
            self.board.mark_locked_out()
            self.game_over = True
            try:
                from gamepad_manager import get_gamepad_manager
                get_gamepad_manager().rumble(1.0, 1.0, 600)
            except Exception:
                pass
            if self.sound:
                self.sound.play_game_over_sequence()
            self.finalize_run()
            return

        # Satır temizlenmiyorsa blok kilitlenme sesi çal
        if not _any_lines_cleared:
            self.sound.play('lock')

        # Skor/istatistik güncelle
        if total_cleared > 0:
            self.board.lines_cleared += total_cleared
            self.board.level = (self.board.lines_cleared // 5) + 1
            self.board.score += self.cascade_bonus
            self.board.combo += 1

            # Back-to-back tracking
            if total_cleared >= 4:
                if getattr(self.board, 'back_to_back', False):
                    self.board.score += int(self.cascade_bonus * 0.5)  # B2B bonus
                self.board.back_to_back = True
            else:
                self.board.back_to_back = False

            # Perfect clear kontrolü
            if all(not any(row) for row in self.board.occupancy):
                self.board.score += 3000 * self.board.level

            # Combo mesajı (base game ile tutarlı)
            if total_cleared >= 4:
                self.combo_message = "QUADRIX!"
                self.combo_message_time = 120
            elif total_cleared >= 2:
                if total_cleared == 2:
                    clear_name = "DOUBLE!"
                elif total_cleared == 3:
                    clear_name = "TRIPLE!"
                else:
                    clear_name = f"{total_cleared}x CLEAR!"
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"{clear_name}  x{combo_count} Combo"
                else:
                    self.combo_message = clear_name
                self.combo_message_time = 120
            else:
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"x{combo_count} Combo!"
                    self.combo_message_time = 90
                else:
                    self.combo_message = ""
                    self.combo_message_time = 0
            
            # Parçacıklar
            if self.effects_enabled:
                cell_size = self.get_cell_size()
                board_offset_x, board_offset_y = self.get_board_offset()
                self.create_cascade_particles(board_offset_x, board_offset_y, cell_size)
            
            # Başarı kontrolü
            if self.achievement_manager:
                new_achievements = self.achievement_manager.update_stats(
                    score=self.board.score,
                    lines=self.board.lines_cleared,
                    level=self.board.level,
                    tetrises=self.board.tetrises,
                    combo=self.board.combo,
                    game_mode=self.game_mode,
                )
                for ach_id in new_achievements:
                    achievement = self.achievement_manager.get_achievement(ach_id)
                    if achievement:
                        self.achievement_notifications.append({
                            'achievement': achievement,
                            'time': pygame.time.get_ticks(),
                            'alpha': 255,
                        })
                        self.sound.play('tetris')

            # Cascade bonusunu sıfırla
            self.cascade_bonus = 0
        else:
            self.board.combo = 0
        
        # Yeni parça
        self.current_piece = self.next_piece_queue.pop(0)
        self._skip_hidden_rows(self.current_piece)
        self.next_piece_queue.append(self.spawn_new_piece())
        # Lock-delay state sıfırla
        self.grounded = False
        self.lock_timer = 0
        self.lock_reset_count = 0
        self.can_hold = True
        self.can_hold2 = True
        self.apply_theme_to_pieces()
        self.fall_speed = self.get_current_speed()
    
    def apply_cascade_gravity(self, cleared_rows):
        """Temizlenen satırların üstündeki blokları aşağı düşür"""
        # Temizlenen satırları sıralı al (yukarıdan aşağıya)
        cleared_rows = sorted(cleared_rows, reverse=True)
        
        for row in cleared_rows:
            # Bu satırı sil (tüm gridler)
            del self.board.grid[row]
            self.board.grid.insert(0, [BLACK for _ in range(self.board_width)])
            try:
                del self.board.texture_grid[row]
                self.board.texture_grid.insert(0, [None for _ in range(self.board_width)])
            except Exception:
                pass
            try:
                del self.board.occupancy[row]
                self.board.occupancy.insert(0, [False for _ in range(self.board_width)])
            except Exception:
                pass
            try:
                del self.board.gold[row]
                self.board.gold.insert(0, [False for _ in range(self.board_width)])
            except Exception:
                pass
            try:
                del self.board.owners[row]
                self.board.owners.insert(0, [None for _ in range(self.board_width)])
            except Exception:
                pass
    
    def create_cascade_particles(self, offset_x, offset_y, cell_size, count=20, level=1):
        """Cascade efekti için özel parçacıklar - seviyeye göre renk değişir"""
        # Seviyeye göre renk paleti
        if level == 1:
            colors = [CYAN, BLUE]  # Seviye 1: Mavi tonları
        elif level == 2:
            colors = [YELLOW, ORANGE]  # Seviye 2: Sarı-turuncu
        elif level == 3:
            colors = [GREEN, (0, 255, 100)]  # Seviye 3: Yeşil
        else:
            colors = [PURPLE, MAGENTA, (255, 0, 255)]  # Seviye 4+: Mor tonları
        
        for _ in range(count):
            x = offset_x + random.randint(0, self.board_width * cell_size)
            y = offset_y + random.randint(0, self.board_height * cell_size)
            color = random.choice(colors)
            
            life_val = random.randint(40, 80)
            particle = {
                'x': x,
                'y': y,
                'vx': random.uniform(-4, 4),
                'vy': random.uniform(-10, -5),  # Yukarı fırlat
                'color': color,
                'size': random.randint(4, 8),
                'life': life_val,
                'max_life': life_val,
                'glow': True  # Parıldama efekti
            }
            self.particles.append(particle)
    
    def draw_mode_info(self, info_x, info_y):
        """Cascade mode bilgilerini çiz"""
        from localization import t
        cascade_label = render_text(self.font_small, t('mode_cascade'), True, CYAN)
        self.screen.blit(cascade_label, (info_x, info_y))
        
        # Açıklama
        tip = render_text(self.font_small, t('cascade_tip_line1'), True, GRAY)
        self.screen.blit(tip, (info_x, info_y + 30))
        
        tip2 = render_text(self.font_small, t('cascade_tip_line2'), True, YELLOW)
        tip2_rect = tip2.get_rect(topleft=(info_x, info_y + 50))
        self.screen.blit(tip2, tip2_rect.topleft)
        
        # Son cascade bilgisi
        if self.cascade_message_time > 0:
            msg_y = info_y + 80
            
            # Cascade seviyesi
            level_text = self.font_medium.render(t('cascade_level_message', level=self.last_cascade_level), True, ORANGE)
            level_rect = level_text.get_rect(topleft=(info_x, msg_y))
            self.screen.blit(level_text, level_rect.topleft)
            
            # Bonus göster
            if self.last_cascade_level > 1:
                bonus_text = render_text(self.font_small, t('cascade_mega_bonus'), True, GREEN)
                bonus_rect = bonus_text.get_rect(topleft=(info_x, msg_y + 30))
                self.screen.blit(bonus_text, bonus_rect.topleft)
                return bonus_rect.bottom - info_y + 10
            return level_rect.bottom - info_y + 10
        return tip2_rect.bottom - info_y + 10
    
    def draw_mode_overlay(self):
        """Cascade HUD bildirimi: skor panelinin altındaki boşlukta minimal animasyon.
        
        NOT: Kullanıcı isteği üzerine harici overlay kaldırıldı.
        Bu metod boş bırakılarak Game class'ındaki hook karşılanıyor.
        """
        pass


class DailyChallengeMode(Game):
    """Daily Challenge - Her gün değişen zorluklar"""

    LOOKBACK_DAYS = 10
    SELECTION_WINDOW_DAYS = 35

    WEEKLY_PROFILES = {
        0: {'difficulty': (1, 2), 'prefer_tags': ('lines', 'score', 'warmup')},
        1: {'difficulty': (2, 3), 'prefer_tags': ('tetris', 'combo', 'precision')},
        2: {'difficulty': (2, 4), 'prefer_tags': ('garbage', 'fog', 'score')},
        3: {'difficulty': (3, 4), 'prefer_tags': ('precision', 'tetris', 'lines')},
        4: {'difficulty': (4, 5), 'prefer_tags': ('boss', 'garbage', 'holdless', 'combo')},
        5: {'difficulty': (2, 4), 'prefer_tags': ('adventure', 'fog', 'garbage', 'combo')},
        6: {'difficulty': (1, 3), 'prefer_tags': ('recovery', 'lines', 'score', 'combo')},
    }

    def _get_left_gameplay_reserve_width(self) -> int:
        return 320 + 26
    
    # Not: Bu liste "günlük görev envanteri"dir.
    # Amaç: kısa sürede heyecan + baskı hissi verecek hedefler ve net kısıtlar.
    CHALLENGES = [
        {
            'id': 'relay_warmup',
            'name': {'tr': 'Röle Isınması', 'en': 'Relay Warm-up'},
            'briefing': {'tr': 'Kısa bir seans, temiz başlangıç.', 'en': 'Short session, clean opening.'},
            'description': {'tr': 'Ritmi yakala ve satır hedefini tamamla.', 'en': 'Catch the rhythm and finish the line goal.'},
            'speed_multiplier': 1.0,
            'target_lines': 40,
            'bonus': 2.0,
            'difficulty': 1,
            'tags': ['lines', 'warmup', 'recovery'],
            'effects': {
                'tr': ['Dengeli tempo', 'Akış odaklı'],
                'en': ['Balanced pace', 'Flow focused'],
            },
        },
        {
            'id': 'steady_climb',
            'name': {'tr': 'Sabit Tırmanış', 'en': 'Steady Climb'},
            'briefing': {'tr': 'Hız yerine kontrol, kontrol yerine istikrar.', 'en': 'Control over speed, consistency over panic.'},
            'description': {'tr': 'Puan hedefini sakin ve temiz oyunla aş.', 'en': 'Reach the score goal with stable, clean play.'},
            'speed_multiplier': 0.95,
            'target_score': 6500,
            'bonus': 2.2,
            'difficulty': 2,
            'tags': ['score', 'warmup'],
            'effects': {
                'tr': ['Yumuşak tempo', 'Kararlı oyun'],
                'en': ['Smooth pace', 'Consistent play'],
            },
        },
        {
            'id': 'quadrix_lesson',
            'name': {'tr': 'Quadrix Dersi', 'en': 'Quadrix Lesson'},
            'briefing': {'tr': 'Teknik gün: büyük temizliğe odaklan.', 'en': 'Technique day: focus on big clears.'},
            'description': {'tr': 'Sadece 4 satır temizliği geçerli.', 'en': 'Only 4-line clears are valid.'},
            'speed_multiplier': 0.9,
            'target_score': 6200,
            'bonus': 2.8,
            'tetris_only': True,
            'difficulty': 3,
            'tags': ['tetris', 'precision'],
            'effects': {
                'tr': ['Sadece Quadrix', 'Yüksek odak'],
                'en': ['Quadrix-only', 'High focus'],
            },
        },
        {
            'id': 'combo_circuit',
            'name': {'tr': 'Combo Devresi', 'en': 'Combo Circuit'},
            'briefing': {'tr': 'Ritimli oynayıp zinciri büyüt.', 'en': 'Play in rhythm and grow the chain.'},
            'description': {'tr': 'Üst üste satır temizleyerek 6 adım zincir yap.', 'en': 'Build a 6-step chain by clearing lines consecutively.'},
            'speed_multiplier': 0.95,
            'target_combo': 6,
            'bonus': 2.9,
            'difficulty': 3,
            'tags': ['combo', 'adventure'],
            'effects': {
                'tr': ['Ritim odaklı', 'Boş turda zincir sıfırlanır'],
                'en': ['Rhythm-focused', 'Chain pressure'],
            },
        },
        {
            'id': 'fog_patrol',
            'name': {'tr': 'Sis Devriyesi', 'en': 'Fog Patrol'},
            'briefing': {'tr': 'Görüş az, sezgi yüksek.', 'en': 'Low visibility, high instinct.'},
            'description': {'tr': 'Sis altında puan hedefini tamamla.', 'en': 'Reach the score goal under fog.'},
            'speed_multiplier': 0.9,
            'target_score': 6200,
            'bonus': 2.7,
            'modifiers': {'fog_overlay': True},
            'difficulty': 3,
            'tags': ['fog', 'score', 'adventure'],
            'effects': {
                'tr': ['Sisli görüş', 'Dikkatli yerleşim'],
                'en': ['Foggy vision', 'Careful placements'],
            },
        },
        {
            'id': 'debris_escape',
            'name': {'tr': 'Enkazdan Çıkış', 'en': 'Debris Escape'},
            'briefing': {'tr': 'Açılış dar, rota senin.', 'en': 'Tight opening, your route to carve.'},
            'description': {'tr': 'Başlangıç enkazını aşıp satır hedefini bitir.', 'en': 'Clear through opening debris and finish line target.'},
            'speed_multiplier': 0.95,
            'target_lines': 50,
            'bonus': 2.8,
            'modifiers': {'garbage_rows': 5},
            'difficulty': 3,
            'tags': ['garbage', 'lines', 'adventure'],
            'effects': {
                'tr': ['5 çöp satırı', 'Alan açma baskısı'],
                'en': ['5 garbage rows', 'Path carving pressure'],
            },
        },
        {
            'id': 'holdless_dash',
            'name': {'tr': 'Hold’suz Koşu', 'en': 'Holdless Dash'},
            'briefing': {'tr': 'Anlık karar, temiz bitiriş.', 'en': 'Snap decisions, clean finish.'},
            'description': {'tr': 'Hold kapalıyken satır hedefini tamamla.', 'en': 'Finish the line target with Hold disabled.'},
            'speed_multiplier': 0.82,
            'target_lines': 35,
            'bonus': 2.7,
            'modifiers': {'disable_hold': True},
            'difficulty': 3,
            'tags': ['holdless', 'lines', 'precision'],
            'effects': {
                'tr': ['Hold kapalı', 'Hızlı tempo'],
                'en': ['Hold disabled', 'Faster tempo'],
            },
        },
        {
            'id': 'clean_architect',
            'name': {'tr': 'Temiz Mimar', 'en': 'Clean Architect'},
            'briefing': {'tr': 'Bir hata, bir çöküş.', 'en': 'One mistake, one collapse.'},
            'description': {'tr': 'Yeni delik açmadan puan hedefine ulaş.', 'en': 'Reach score goal without creating new holes.'},
            'speed_multiplier': 1.0,
            'target_score': 5200,
            'bonus': 3.0,
            'no_mistakes': True,
            'difficulty': 4,
            'tags': ['no_mistakes', 'precision', 'boss'],
            'effects': {
                'tr': ['Delik açma yasağı', 'Saf kontrol'],
                'en': ['No new holes', 'Pure control'],
            },
        },
        {
            'id': 'pressure_cooker',
            'name': {'tr': 'Basınç Tenceresi', 'en': 'Pressure Cooker'},
            'briefing': {'tr': 'Haftanın boss savaşı.', 'en': 'Boss battle of the week.'},
            'description': {'tr': 'Çöp + Hold yok: puan hedefini baskı altında tamamla.', 'en': 'Garbage + no Hold: finish score target under pressure.'},
            'speed_multiplier': 0.75,
            'target_score': 8500,
            'bonus': 3.0,
            'modifiers': {'garbage_rows': 5, 'disable_hold': True},
            'difficulty': 5,
            'tags': ['boss', 'garbage', 'holdless', 'score'],
            'effects': {
                'tr': ['Hold kapalı', '5 çöp satırı'],
                'en': ['Hold disabled', '5 garbage rows'],
            },
        },
        {
            'id': 'boss_quadrix',
            'name': {'tr': 'Sisli Quadrix', 'en': 'Fogged Quadrix'},
            'briefing': {'tr': 'Görüş dar, hedef büyük.', 'en': 'Narrow sight, huge objective.'},
            'description': {'tr': 'Sis altında sadece Quadrix ile puan topla.', 'en': 'Score using Quadrix-only clears under fog.'},
            'speed_multiplier': 0.85,
            'target_score': 7000,
            'bonus': 3.2,
            'tetris_only': True,
            'modifiers': {'fog_overlay': True},
            'difficulty': 4,
            'tags': ['boss', 'tetris', 'fog', 'precision'],
            'effects': {
                'tr': ['Sisli görüş', 'Sadece Quadrix temizliği'],
                'en': ['Foggy view', 'Quadrix-only clears'],
            },
        },
        {
            'id': 'debris_combo',
            'name': {'tr': 'Enkaz Combo', 'en': 'Debris Combo'},
            'briefing': {'tr': 'Kriz üstünde ritim kur.', 'en': 'Build rhythm on top of chaos.'},
            'description': {'tr': 'Enkaz üzerinde üst üste satır temizleyip 7 adım zincir yap.', 'en': 'Clear lines consecutively over debris and build a 7-step chain.'},
            'speed_multiplier': 0.9,
            'target_combo': 7,
            'bonus': 3.0,
            'modifiers': {'garbage_rows': 4},
            'difficulty': 4,
            'tags': ['garbage', 'combo', 'adventure'],
            'effects': {
                'tr': ['4 çöp satırı', 'Boş turda zincir sıfırlanır'],
                'en': ['4 garbage rows', '7x combo target'],
            },
        },
        {
            'id': 'tight_well',
            'name': {'tr': 'Dar Kuyu', 'en': 'Tight Well'},
            'briefing': {'tr': 'Açılış zorlu, dönüş mümkün.', 'en': 'Harsh opening, recover if you can.'},
            'description': {'tr': 'Dar kuyu başlangıcında puan hedefini tamamla.', 'en': 'Finish score target from a tight-well opening.'},
            'speed_multiplier': 0.92,
            'target_score': 7600,
            'bonus': 2.8,
            'modifiers': {'garbage_rows': 8},
            'difficulty': 4,
            'tags': ['garbage', 'score', 'boss'],
            'effects': {
                'tr': ['8 çöp satırı', 'Zor başlangıç'],
                'en': ['8 garbage rows', 'Hard start'],
            },
        },
        {
            'id': 'weekend_raid',
            'name': {'tr': 'Hafta Sonu Baskını', 'en': 'Weekend Raid'},
            'briefing': {'tr': 'Eğlenceli ama sinsi bir operasyon.', 'en': 'A playful but sneaky operation.'},
            'description': {'tr': 'Sis ve enkazla satır hedefini bitir.', 'en': 'Finish line goal with fog and debris combined.'},
            'speed_multiplier': 0.9,
            'target_lines': 45,
            'bonus': 3.0,
            'modifiers': {'garbage_rows': 3, 'fog_overlay': True},
            'difficulty': 3,
            'tags': ['adventure', 'fog', 'garbage', 'lines'],
            'effects': {
                'tr': ['Sisli görüş', '3 çöp satırı'],
                'en': ['Foggy view', '3 garbage rows'],
            },
        },
    ]

    @classmethod
    def _primary_target(cls, challenge: dict) -> tuple[str, int]:
        """Görevin birincil hedef tipini ve değerini döndür."""
        for key in ('target_score', 'target_lines', 'target_combo'):
            if key in challenge:
                try:
                    return key, int(challenge.get(key) or 0)
                except Exception:
                    return key, 0
        return 'none', 0

    @classmethod
    def _compute_reward_fragments(cls, challenge: dict) -> int:
        """Görev zorluğuna göre günlük ödül parçacık miktarı hesapla."""
        diff = int(challenge.get('difficulty', 3) or 3)
        target_key, target_val = cls._primary_target(challenge)
        base = 70 + (diff * 25)

        if target_key == 'target_score':
            base += int(target_val / 180)
        elif target_key == 'target_lines':
            base += target_val * 3
        elif target_key == 'target_combo':
            base += target_val * 20

        if challenge.get('no_mistakes'):
            base += 30
        if challenge.get('tetris_only'):
            base += 25
        if challenge.get('modifiers', {}).get('disable_hold'):
            base += 20
        if challenge.get('modifiers', {}).get('fog_overlay'):
            base += 15
        if int(challenge.get('modifiers', {}).get('garbage_rows', 0) or 0) > 0:
            base += 10

        return max(80, min(320, int(base)))

    @classmethod
    def _compute_reward_xp(cls, challenge: dict) -> int:
        diff = int(challenge.get('difficulty', 3) or 3)
        return max(50, min(220, 40 + diff * 28))

    @staticmethod
    def _format_localized_number(value: int | float, lang: str) -> str:
        if isinstance(value, float):
            return DailyChallengeMode._format_bonus_multiplier(value, lang)
        formatted = f"{int(value):,}"
        if lang == 'tr':
            return formatted.replace(',', '.')
        return formatted

    @staticmethod
    def _format_bonus_multiplier(value: float, lang: str) -> str:
        formatted = f"{float(value):.2f}".rstrip('0').rstrip('.')
        if lang in {'tr', 'de', 'fr', 'es', 'it', 'pt', 'ru'}:
            formatted = formatted.replace('.', ',')
        return formatted

    @staticmethod
    def _get_translation_entry(key: str) -> dict | None:
        try:
            from localization import TRANSLATIONS
        except Exception:
            return None
        entry = TRANSLATIONS.get(key)
        return entry if isinstance(entry, dict) else None

    @classmethod
    def _translate(cls, key: str, lang: str, default: str | None = None, **kwargs) -> str:
        entry = cls._get_translation_entry(key)
        if entry:
            text = entry.get(lang) or entry.get('en') or entry.get('tr') or (default if default is not None else key)
        else:
            text = default if default is not None else key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                pass
        return str(text)

    @staticmethod
    def _challenge_effect_slot_count(challenge: dict) -> int:
        raw_value = challenge.get('effects')
        if isinstance(raw_value, dict):
            return max((len(value) for value in raw_value.values() if isinstance(value, list)), default=0)
        if isinstance(raw_value, list):
            return len(raw_value)
        return 0

    @classmethod
    def _expected_localization_keys(cls, challenge: dict) -> list[str]:
        challenge_id = str(challenge.get('id') or '').strip()
        if not challenge_id:
            return []

        keys = [
            f"dc_challenge_{challenge_id}_name",
            f"dc_challenge_{challenge_id}_briefing",
            f"dc_challenge_{challenge_id}_description",
        ]
        for idx in range(1, cls._challenge_effect_slot_count(challenge) + 1):
            keys.append(f"dc_challenge_{challenge_id}_effect_{idx}")
        return keys

    @classmethod
    def _resolve_challenge_text(cls, challenge: dict, field: str, lang: str) -> str:
        raw_value = challenge.get(field)
        challenge_id = str(challenge.get('id') or '').strip()
        if challenge_id:
            key = f"dc_challenge_{challenge_id}_{field}"
            if cls._get_translation_entry(key):
                return cls._translate(key, lang, default='')
        if isinstance(raw_value, dict):
            return str(raw_value.get(lang) or raw_value.get('en') or next(iter(raw_value.values()), ''))
        return str(raw_value or '')

    @classmethod
    def _resolve_challenge_effects(cls, challenge: dict, lang: str) -> list[str]:
        raw_value = challenge.get('effects')
        challenge_id = str(challenge.get('id') or '').strip()

        if challenge_id:
            effects: list[str] = []
            idx = 1
            while True:
                key = f"dc_challenge_{challenge_id}_effect_{idx}"
                if not cls._get_translation_entry(key):
                    break
                effect = cls._translate(key, lang, default='').strip()
                if effect:
                    effects.append(effect)
                idx += 1
            if effects:
                return effects

        if isinstance(raw_value, dict):
            localized = raw_value.get(lang) or raw_value.get('en')
            if isinstance(localized, list):
                return list(localized)
            for value in raw_value.values():
                if isinstance(value, list):
                    return list(value)
        if isinstance(raw_value, list):
            return list(raw_value)
        return []

    @classmethod
    def _build_objective_line(cls, challenge: dict, lang: str) -> str:
        target_key, target_val = cls._primary_target(challenge)
        formatted_target = cls._format_localized_number(target_val, lang)
        if target_key == 'target_score':
            return cls._translate('dc_target_score', lang, value=formatted_target)
        if target_key == 'target_lines':
            return cls._translate('dc_target_lines', lang, value=formatted_target)
        if target_key == 'target_combo':
            return cls._translate('dc_target_combo', lang, value=formatted_target)
        return cls._translate('dc_objective_complete', lang)

    @classmethod
    def _build_rule_line(cls, challenge: dict, lang: str) -> str:
        rules: list[str] = []
        modifiers = challenge.get('modifiers', {}) or {}

        if challenge.get('tetris_only'):
            rules.append(cls._translate('dc_rule_only_quadrix', lang))
        if challenge.get('no_mistakes'):
            rules.append(cls._translate('dc_rule_no_new_holes', lang))
        if modifiers.get('disable_hold'):
            rules.append(cls._translate('dc_rule_hold_disabled', lang))
        if modifiers.get('fog_overlay'):
            rules.append(cls._translate('dc_rule_fog_active', lang))
        garbage_rows = int(modifiers.get('garbage_rows', 0) or 0)
        if garbage_rows > 0:
            rules.append(
                cls._translate(
                    'dc_rule_garbage_start',
                    lang,
                    value=cls._format_localized_number(garbage_rows, lang),
                )
            )

        if not rules:
            return cls._translate('dc_rule_standard', lang)
        return cls._translate('dc_rule_prefix', lang) + ' • '.join(rules)

    @classmethod
    def _build_fail_line(cls, challenge: dict, lang: str) -> str:
        max_mistakes = int(challenge.get('max_mistakes', 0) or 0)
        if max_mistakes > 0:
            return cls._translate(
                'dc_fail_max_mistakes',
                lang,
                value=cls._format_localized_number(max_mistakes, lang),
            )
        return cls._translate(
            'dc_fail_attempts_locked',
            lang,
            tries=cls._format_localized_number(DAILY_MAX_FAILURES, lang),
        )

    @classmethod
    def _build_reward_line(cls, challenge: dict, lang: str) -> str:
        fragments = int(challenge.get('reward_fragments', 0) or 0)
        xp = int(challenge.get('reward_xp', 0) or 0)
        bonus = float(challenge.get('bonus', 1.0) or 1.0)
        return cls._translate(
            'dc_reward_summary',
            lang,
            fragments=cls._format_localized_number(fragments, lang),
            xp=cls._format_localized_number(xp, lang),
            bonus=cls._format_bonus_multiplier(bonus, lang),
        )

    @classmethod
    def _enrich_challenge_ui(cls, challenge: dict, lang: str) -> dict:
        """UI için görevte net hedef/kural/ödül satırları üret."""
        out = dict(challenge)
        out['reward_fragments'] = int(out.get('reward_fragments') or cls._compute_reward_fragments(out))
        out['reward_xp'] = int(out.get('reward_xp') or cls._compute_reward_xp(out))

        if not out.get('max_mistakes') and (out.get('tetris_only') or out.get('no_mistakes')):
            out['max_mistakes'] = 1

        out['objective_line'] = cls._build_objective_line(out, lang)
        out['rule_line'] = cls._build_rule_line(out, lang)
        out['fail_line'] = cls._build_fail_line(out, lang)
        out['reward_line'] = cls._build_reward_line(out, lang)
        return out

    @classmethod
    def _materialize_texts(cls, challenge: dict, lang: str) -> dict:
        """Challenge sözlüğündeki çok dilli alanları seçip düzleştir."""
        out = dict(challenge)
        out['name'] = cls._resolve_challenge_text(challenge, 'name', lang)
        out['briefing'] = cls._resolve_challenge_text(challenge, 'briefing', lang)
        out['description'] = cls._resolve_challenge_text(challenge, 'description', lang)
        out['effects'] = cls._resolve_challenge_effects(challenge, lang)
        return out

    @classmethod
    def _day_seed(cls, day: date) -> int:
        return day.year * 10000 + day.month * 100 + day.day

    @classmethod
    def _candidate_indices_for_day(cls, day: date) -> tuple[list[int], set[str]]:
        profile = cls.WEEKLY_PROFILES.get(day.weekday(), {'difficulty': (1, 5), 'prefer_tags': ()})
        min_diff, max_diff = profile.get('difficulty', (1, 5))
        prefer_tags = set(profile.get('prefer_tags', ()))

        indices: list[int] = []
        for idx, challenge in enumerate(cls.CHALLENGES):
            difficulty = int(challenge.get('difficulty', 3) or 3)
            if min_diff <= difficulty <= max_diff:
                indices.append(idx)
        if not indices:
            indices = list(range(len(cls.CHALLENGES)))
        return indices, prefer_tags

    @classmethod
    def _pick_daily_index(cls, day: date) -> int:
        start_day = day - timedelta(days=cls.SELECTION_WINDOW_DAYS)
        picked: dict[date, int] = {}
        cursor = start_day
        while cursor <= day:
            candidates, prefer_tags = cls._candidate_indices_for_day(cursor)
            rng = random.Random(cls._day_seed(cursor))
            ordered = list(candidates)
            rng.shuffle(ordered)
            ordered.sort(
                key=lambda idx: len(prefer_tags.intersection(set(cls.CHALLENGES[idx].get('tags', [])))),
                reverse=True,
            )

            recent_ids = {
                picked[cursor - timedelta(days=offset)]
                for offset in range(1, cls.LOOKBACK_DAYS + 1)
                if (cursor - timedelta(days=offset)) in picked
            }
            allowed = [idx for idx in ordered if idx not in recent_ids]
            picked[cursor] = (allowed or ordered)[0]
            cursor += timedelta(days=1)
        return picked[day]

    @classmethod
    def _compute_adaptive_scale(cls, user_manager) -> tuple[float, int, int]:
        if not user_manager:
            return 1.0, 0, 0
        status = user_manager.get_daily_status()
        if not isinstance(status, dict):
            return 1.0, 0, 0

        history = status.get('history')
        if not isinstance(history, list):
            return 1.0, 0, 0

        today_iso = date.today().isoformat()
        recent_results: list[bool] = []
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            item_date = str(item.get('date') or '')
            if not item_date or item_date >= today_iso:
                continue
            recent_results.append(bool(item.get('success')))
            if len(recent_results) >= 7:
                break

        sample = len(recent_results)
        wins = sum(1 for r in recent_results if r)
        if sample < 3:
            return 1.0, sample, wins

        rate = wins / sample
        if rate >= 0.72:
            return 1.08, sample, wins
        if rate >= 0.60:
            return 1.04, sample, wins
        if rate <= 0.35:
            return 0.92, sample, wins
        if rate <= 0.50:
            return 0.96, sample, wins
        return 1.0, sample, wins

    @classmethod
    def _apply_target_scaling(cls, challenge: dict, scale: float) -> None:
        if abs(scale - 1.0) < 0.01:
            return

        for key, minimum in (('target_score', 2500), ('target_lines', 20), ('target_combo', 3)):
            if key in challenge:
                try:
                    base = int(challenge[key])
                    challenge[key] = max(minimum, int(round(base * scale)))
                except Exception:
                    continue

        try:
            bonus = float(challenge.get('bonus', 2.2))
            if scale > 1.0:
                bonus = min(3.8, bonus + 0.15)
            else:
                bonus = max(1.8, bonus - 0.1)
            challenge['bonus'] = round(bonus, 2)
        except Exception:
            pass

    @classmethod
    def get_today_challenge(cls, day: date | None = None, user_manager=None) -> dict:
        """Bugünün Daily Challenge'ını (deterministik) döndür.

        Not: Global random state'i etkilemez.
        """
        today = day or date.today()
        seed = cls._day_seed(today)
        idx = cls._pick_daily_index(today)
        base = dict(cls.CHALLENGES[idx])
        # Deterministik yan etkiler (garbage delikleri vb.) için seed'i challenge'a iliştir.
        base['_seed'] = seed

        scale, sample, wins = cls._compute_adaptive_scale(user_manager)
        cls._apply_target_scaling(base, scale)
        if sample >= 3:
            base['adaptive_scale'] = scale
            base['adaptive_sample'] = sample
            base['adaptive_wins'] = wins

        try:
            from localization import get_language
            lang = get_language()
        except Exception:
            lang = 'tr'
        materialized = cls._materialize_texts(base, lang)
        return cls._enrich_challenge_ui(materialized, lang)
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, settings_manager=None, user_manager=None, game_mode='daily', score_manager=None, sound_manager=None):
        """Daily Challenge'ı başlat"""
        # Günün challenge'ını önce seç; parça torbasını da aynı günlük seed'e bağlayacağız.
        self.challenge = self.get_today_challenge(user_manager=user_manager)
        self._daily_seed = int(self.challenge.get('_seed', 0) or 0)
        cid = str(self.challenge.get('id') or '')
        cid_mix = sum((i + 1) * ord(ch) for i, ch in enumerate(cid))
        self._daily_piece_seed = (self._daily_seed + cid_mix) & 0xFFFFFFFF

        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
            piece_rng_seed=self._daily_piece_seed,
        )

        # Günün challenge'ı zaten seçildi; runtime state'i bunun üzerinden kur.
        self.challenge_completed = False
        self.modifiers = dict(self.challenge.get('modifiers', {}))
        self.side_effects = list(self.challenge.get('effects', []))
        # Daily'ye özel RNG: global random state'e dokunmadan deterministik davranış.
        self._daily_rng = random.Random(self._daily_piece_seed)
        self.disable_hold = False
        self.fog_overlay = False
        self._daily_outcome_recorded = False
        self.daily_attempt_cap = DAILY_MAX_FAILURES
        self._daily_failed = False
        self.speed_multiplier = float(self.challenge.get('speed_multiplier', 1.0))
        self.controls_under_stats = True
        
        print(f"Günün Zorluğu: {self.challenge.get('name')}")
        print(f"   {self.challenge.get('description')}")
        
        # Challenge'a göre hızı ayarla
        base_speed = self.get_initial_speed()
        self.fall_speed = int(base_speed * self.speed_multiplier)
        
        # Özel kurallar
        self.tetris_only = self.challenge.get('tetris_only', False)
        self.no_mistakes = self.challenge.get('no_mistakes', False)
        self.max_mistakes = int(self.challenge.get('max_mistakes', 0) or 0)
        self.mistakes_made = 0
        self._apply_modifiers()
        
        # Not: global random state'e dokunmuyoruz
    
    def _apply_modifiers(self):
        """Challenge özel modlarını uygula"""
        if not self.modifiers:
            return
        self.disable_hold = self.modifiers.get('disable_hold', False)
        self.fog_overlay = self.modifiers.get('fog_overlay', False)
        garbage_rows = int(self.modifiers.get('garbage_rows', 0) or 0)
        if garbage_rows > 0:
            self._inject_garbage_rows(garbage_rows)

    def _remaining_daily_attempts(self) -> int:
        if not self.user_manager:
            return self.daily_attempt_cap
        status = self.user_manager.get_daily_status()
        if not status:
            return self.daily_attempt_cap
        if status.get('completed'):
            return 0
        return max(0, DAILY_MAX_FAILURES - status.get('fails', 0))
    
    def _inject_garbage_rows(self, count):
        count = min(count, self.board_height - 2)
        rng = getattr(self, '_daily_rng', None) or random.Random(0)
        for idx in range(count):
            target_row = self.board_height - 1 - idx
            hole_x = rng.randint(0, self.board_width - 1)
            for x in range(self.board_width):
                filled = x != hole_x
                self.board.grid[target_row][x] = (70, 70, 100) if filled else BLACK
                self.board.occupancy[target_row][x] = filled
                self.board.texture_grid[target_row][x] = None

    def _count_holes(self) -> int:
        """Board'daki delik sayısını hesapla (boş hücre, üstünde blok varken)."""
        holes = 0
        for x in range(self.board_width):
            seen_block = False
            for y in range(self.board_height):
                filled = bool(self.board.occupancy[y][x])
                if filled:
                    seen_block = True
                elif seen_block:
                    holes += 1
        return holes
    
    def lock_and_new_piece(self):
        """Challenge kuralları ile parça kilitleme"""
        prev_lines = int(getattr(self.board, 'lines_cleared', 0) or 0)
        prev_holes = self._count_holes() if self.no_mistakes else 0

        super().lock_and_new_piece()

        cleared = int(getattr(self.board, 'lines_cleared', 0) or 0) - prev_lines

        # Quadrix-only: 1-3 satır temizliği hata sayılır
        if self.tetris_only and cleared not in (0, 4):
            self.mistakes_made += 1
            print(f"[Hata] Sadece Quadrix yapabilirsin! Hata: {self.mistakes_made}")
            try:
                self.sound.play('drop')
            except Exception:
                pass
            self._check_mistake_failure()

        # No mistakes: yeni delik oluşturmak hata
        if self.no_mistakes:
            after_holes = self._count_holes()
            if after_holes > prev_holes:
                self.mistakes_made += 1
                self._check_mistake_failure("💔 Yeni delik açtın! Challenge başarısız!")

        self.check_challenge_completion()

    def _check_mistake_failure(self, message: str | None = None) -> None:
        """Kural ihlali sayısı limiti aştığında görevi bitir."""
        if int(getattr(self, 'max_mistakes', 0) or 0) <= 0:
            return
        if int(getattr(self, 'mistakes_made', 0) or 0) < int(self.max_mistakes):
            return
        self.game_over = True
        print(message or "Kural ihlali limiti doldu. Challenge başarısız!")

    def wants_mouse_visible(self) -> bool:
        if getattr(self, '_daily_failed', False):
            return True
        return super().wants_mouse_visible()

    def handle_input(self):
        if getattr(self, '_daily_failed', False):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'
                    if event.key == pygame.K_r:
                        self.restart()
                        return True
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    from platform_utils import get_mouse_pos as _get_mouse_pos
                    pos = _get_mouse_pos()
                    targets = getattr(self, '_game_over_click_targets', {})
                    if isinstance(targets, dict):
                        if targets.get('restart') and targets['restart'].collidepoint(pos):
                            self.restart()
                            return True
                        if targets.get('menu') and targets['menu'].collidepoint(pos):
                            return 'main_menu'
            return True
        if self.disable_hold:
            self.can_hold = False
        return super().handle_input()

    def update(self, delta_time):
        if getattr(self, '_daily_failed', False):
            return
        if self.disable_hold:
            self.can_hold = False
        super().update(delta_time)
        # Oyun alanı doldu → günlük görev başarısız ekranına yönlendir
        if getattr(self, 'game_over', False) and not getattr(self, '_daily_failed', False):
            self.game_over = False
            self._game_over_active = False
            self._game_over_pending = False
            self._daily_failed = True

    def get_current_speed(self):
        base = super().get_current_speed()
        scaled = int(base * self.speed_multiplier)
        return max(60, scaled)

    def draw_mode_overlay(self):
        if getattr(self, '_daily_failed', False):
            self._draw_daily_failed_overlay()
            return
        super().draw_mode_overlay()
        if self.fog_overlay and not self.game_over:
            active_width, active_height = self._active_ui_size()
            fog = self._get_solid_alpha_surface((active_width, active_height), (10, 12, 30, 110))
            self.screen.blit(fog, (0, 0))

        # Daily hedef paneli / ilerleme çubuğu
        try:
            # HUD anchor varsa kullan; yoksa draw_mode_info kendi konumunu hesaplar.
            self.draw_mode_info(0, 0)
        except Exception:
            pass

    def _draw_daily_failed_overlay(self) -> None:
        """Günlük görev başarısız ekranı - kırmızı tema."""
        try:
            from localization import t as _t
        except Exception:
            def _t(k, **kw): return k  # type: ignore
        _red_theme = {
            'panel_border_color': (220, 50, 70),
            'panel_glow_color':   (160, 25, 40),
            'panel_fill_tint':    (30, 8, 12),
            'card_fill_tint':     (38, 12, 18),
            'card_border_color':  (140, 50, 65),
            'gradient_tint':      (20, 5, 8),
            'title_text':         _t('campaign_failed_title'),
            'skip_stars':         True,
            'skip_record':        True,
            'state_prefix':       'daily_fail_',
        }
        self._draw_game_over_overlay(None, alt_theme=_red_theme)
    
    def check_challenge_completion(self):
        """Challenge tamamlandı mı kontrol et"""
        if self.challenge_completed:
            return

        # Birden fazla hedef tanımlanmışsa hepsini aynı anda istemek daha tutarlı.
        checks = []
        if 'target_score' in self.challenge:
            try:
                checks.append(self.board.score >= int(self.challenge['target_score']))
            except Exception:
                checks.append(False)
        if 'target_lines' in self.challenge:
            try:
                checks.append(self.board.lines_cleared >= int(self.challenge['target_lines']))
            except Exception:
                checks.append(False)
        if 'target_combo' in self.challenge:
            try:
                checks.append(self.board.combo >= int(self.challenge['target_combo']))
            except Exception:
                checks.append(False)

        completed = all(checks) if checks else False
        
        if completed and not self.challenge_completed:
            self.challenge_completed = True
            # Bonus puan
            bonus = int(self.board.score * (self.challenge['bonus'] - 1))
            self.board.score += bonus
            print(f"Challenge Tamamlandı! Bonus: +{bonus} puan!")
            self.sound.play('tetris')
            
            # Parçacık efekti
            if self.effects_enabled:
                self.create_celebration_particles()
    
    def create_celebration_particles(self):
        """Challenge tamamlanınca kutlama parçacıkları"""
        cell_size = self.get_cell_size()
        offset_x, offset_y = self.get_board_offset()
        
        for _ in range(50):
            x = offset_x + random.randint(0, self.board_width * cell_size)
            y = offset_y + random.randint(0, self.board_height * cell_size)
            color = random.choice([YELLOW, ORANGE, CYAN, GREEN, PURPLE])
            
            life_val = random.randint(60, 120)
            particle = {
                'x': x,
                'y': y,
                'vx': random.uniform(-5, 5),
                'vy': random.uniform(-10, -5),
                'color': color,
                'size': random.randint(4, 8),
                'life': life_val,
                'max_life': life_val  # max_life ekle
            }
            self.particles.append(particle)
    
    def draw_mode_info(self, info_x, info_y):
        """Daily Challenge bilgilerini çiz

        P1-5 (Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu): panel yüksekliği
        sabit %50 ekran oranı yerine İÇERİK BÜTÇESİNDEN türetilir — iç blokların
        gerçek font yükseklikleri toplanır, panel 320-420 aralığında bütçeye
        göre büyütülür/küçültülür, açıklama (description) satır limiti kalan
        yükseklikten dinamik belirlenir. Alt bloklar panel tabanını yükseklik
        farkındalı guard'larla asla aşmaz; hedef/progress ve tüm blok
        rect'leri ``self._daily_panel_rects`` altına kaydedilir.
        """
        from localization import t, get_language

        # Günlük panelini oyun alanının soluna yerleştir
        board_offset_x, board_offset_y = self.get_board_offset()
        available_left = max(220, int(board_offset_x) - 44)
        panel_w = max(240, min(320, available_left))
        top_offset = 24

        panel_x = max(18, int(board_offset_x) - panel_w - 26)
        panel_y = int(board_offset_y) + int(top_offset)

        # Sağdaki skor kartı temeli: koyu gradient + ince border
        pad_x = 18
        pad_top = 14
        pad_bottom = 14
        inner_w = panel_w - pad_x * 2

        # === ÖLÇÜM AŞAMASI (measure-first) ==================================
        # Tüm bloklar inner_w'ye göre ölçülür; panel yüksekliği bu ölçümlerden
        # türetilir. Surface üretimi yalnız LRU önbellekli render_fit_text /
        # wrap_text_limited üzerinden akar (kare-başı tahsis yasağı — CLAUDE.md).
        def _lines_height(lines, font, line_gap):
            if not lines:
                return 0
            return len(lines) * font.get_height() + (len(lines) - 1) * line_gap

        title_txt = t('dc_panel_title')
        title_surf = ui_style.render_fit_text(title_txt, (100, 220, 255), inner_w, 18, bold=True)
        name_txt = str(self.challenge.get('name') or '')
        name_surf = ui_style.render_fit_text(name_txt, (235, 225, 210), inner_w, 26, bold=True)

        desc_txt = str(self.challenge.get('description') or '')
        desc_size, desc_gap = 15, 3
        desc_font = ui_style.get_font(desc_size, bold=False)
        # İstenen (tam) sarma — satır limiti panel bütçesi çıktıktan sonra
        # belirlenir (rapor: 'açıklama satır limitini kalan yüksekliğe göre').
        desc_full_lines = list(wrap_text_limited(desc_txt, desc_font, inner_w).lines) if desc_txt.strip() else []

        briefing_txt = str(self.challenge.get('briefing') or '')
        briefing_size, briefing_gap = 14, 3
        briefing_font = ui_style.get_font(briefing_size, bold=False)
        briefing_lines = list(wrap_text_limited(briefing_txt, briefing_font, inner_w, max_lines=2).lines) if briefing_txt.strip() else []

        if 'target_score' in self.challenge:
            target_text = str(self.challenge.get('objective_line') or t('dc_target_score', value=self.challenge['target_score']))
            progress = min(100, int(self.board.score / self.challenge['target_score'] * 100))
        elif 'target_lines' in self.challenge:
            target_text = str(self.challenge.get('objective_line') or t('dc_target_lines', value=self.challenge['target_lines']))
            progress = min(100, int(self.board.lines_cleared / self.challenge['target_lines'] * 100))
        elif 'target_combo' in self.challenge:
            target_text = str(self.challenge.get('objective_line') or t('dc_target_combo', value=self.challenge['target_combo']))
            progress = min(100, int(self.board.combo / self.challenge['target_combo'] * 100))
        else:
            target_text = t('dc_keep_going')
            progress = 0

        target_size, target_gap = 16, 2
        target_font = ui_style.get_font(target_size, bold=False)
        target_lines = list(wrap_text_limited(str(target_text), target_font, inner_w, max_lines=2).lines) if str(target_text).strip() else []

        progress_h = 14

        completed_surf = None
        bonus_surf = None
        if self.challenge_completed:
            completed_surf = ui_style.render_fit_text(t('dc_completed'), GREEN, inner_w, 18, bold=True)
            bonus_val = self.challenge.get('bonus')
            bonus_text = t(
                'dc_bonus_multiplier',
                bonus=self._format_bonus_multiplier(float(bonus_val or 1.0), get_language()),
            )
            bonus_surf = ui_style.render_fit_text(bonus_text, (255, 200, 50), inner_w, 14, bold=True)

        effects_title_surf = None
        effects_line_groups = []
        fx_size, fx_gap = 14, 2
        fx_font = ui_style.get_font(fx_size, bold=False)
        if self.side_effects:
            effects_title_surf = ui_style.render_fit_text(t('dc_effects_title'), (255, 200, 50), inner_w, 15, bold=True)
            for effect in self.side_effects[:4]:
                group = list(wrap_text_limited(f'- {effect}', fx_font, inner_w, max_lines=2).lines)
                if group:
                    effects_line_groups.append(group)

        detail_groups = []
        detail_size, detail_gap = 13, 2
        detail_font = ui_style.get_font(detail_size, bold=False)
        # Kural / başarısızlık / ödül satırları
        for detail_text, detail_color in (
            (str(self.challenge.get('rule_line') or ''), (205, 215, 235)),
            (str(self.challenge.get('fail_line') or ''), (255, 175, 145)),
            (str(self.challenge.get('reward_line') or ''), (160, 235, 180)),
        ):
            if not detail_text:
                continue
            group = list(wrap_text_limited(detail_text, detail_font, inner_w, max_lines=2).lines)
            if group:
                detail_groups.append((group, detail_color))

        mistakes_lines = []
        mistakes_size, mistakes_gap = 14, 2
        mistakes_font = ui_style.get_font(mistakes_size, bold=False)
        if int(getattr(self, 'max_mistakes', 0) or 0) > 0 and not self.challenge_completed:
            mistakes_text = t('dc_mistakes', made=self.mistakes_made, max=self.max_mistakes)
            mistakes_lines = list(wrap_text_limited(mistakes_text, mistakes_font, inner_w, max_lines=2).lines)

        status_lines = []
        status_color = GREEN
        status_size, status_gap = 14, 2
        status_font = ui_style.get_font(status_size, bold=False)
        streak_surf = None
        if self.user_manager:
            status = self.user_manager.get_daily_status()
            if status:
                if status.get('completed'):
                    status_text = t('dc_today_completed')
                    color = GREEN
                else:
                    remaining = max(0, DAILY_MAX_FAILURES - status.get('fails', 0))
                    status_text = t('dc_remaining_tries', remaining=remaining, max=DAILY_MAX_FAILURES)
                    color = GREEN if remaining > 0 else RED
                status_lines = list(wrap_text_limited(status_text, status_font, inner_w, max_lines=2).lines)
                status_color = color
                # Streak göster
                streak_val = int(status.get('streak', 0) or 0)
                if streak_val > 0:
                    streak_text = t('dc_streak', days=streak_val)
                    streak_surf = ui_style.render_fit_text(streak_text, (150, 220, 255), inner_w, 13, bold=False)

        adaptive_surf = None
        adaptive_scale = float(self.challenge.get('adaptive_scale', 1.0) or 1.0)
        if abs(adaptive_scale - 1.0) >= 0.01:
            if adaptive_scale > 1.0:
                adaptive_txt = t('dc_adaptive_up')
                adaptive_color = (255, 210, 120)
            else:
                adaptive_txt = t('dc_adaptive_down')
                adaptive_color = (140, 220, 170)
            adaptive_surf = ui_style.render_fit_text(adaptive_txt, adaptive_color, inner_w, 12, bold=False)

        # === YÜKSEKLİK BÜTÇESİ ==============================================
        # Açıklamanın ALTINDAKİ tüm bloklar + aralarındaki ilerleme payları.
        below_desc_h = 0
        briefing_h = _lines_height(briefing_lines, briefing_font, briefing_gap)
        if briefing_h > 0:
            below_desc_h += briefing_h + 10
        target_h = _lines_height(target_lines, target_font, target_gap)
        if target_h > 0:
            below_desc_h += target_h + 8
        below_desc_h += progress_h + 12
        if completed_surf is not None:
            below_desc_h += completed_surf.get_height() + 4
        if bonus_surf is not None:
            below_desc_h += bonus_surf.get_height() + 10
        if effects_title_surf is not None:
            below_desc_h += effects_title_surf.get_height() + 5
            for group in effects_line_groups:
                below_desc_h += _lines_height(group, fx_font, fx_gap) + 2
            below_desc_h += 6
        for group, _detail_color in detail_groups:
            below_desc_h += _lines_height(group, detail_font, detail_gap) + 5
        if mistakes_lines:
            below_desc_h += _lines_height(mistakes_lines, mistakes_font, mistakes_gap) + 6
        if status_lines:
            below_desc_h += _lines_height(status_lines, status_font, status_gap) + 6
        if streak_surf is not None:
            below_desc_h += streak_surf.get_height() + 5
        if adaptive_surf is not None:
            below_desc_h += adaptive_surf.get_height() + 4

        fixed_above_desc = pad_top + title_surf.get_height() + 8 + name_surf.get_height() + 10
        desc_full_h = _lines_height(desc_full_lines, desc_font, desc_gap)
        needed_h = fixed_above_desc + (desc_full_h + 10 if desc_full_lines else 0) + below_desc_h + pad_bottom

        # Rapor sözleşmesi: panel 320-420 yükseklik aralığında; içerik küçükse
        # taban 320, sığmazsa tavandan içerik bütçesine göre küçültülür.
        panel_h = max(320, min(420, needed_h))
        # Ekran bütçesi: alt kenar ekranı aşamaz (aşırı kısa pencerede taban 240).
        panel_h = min(panel_h, max(240, int(self.screen.get_height()) - panel_y - 12))

        # Açıklama satır limiti: kalan dikey bütçeden satır sayısına indirgenir.
        desc_avail_h = panel_h - fixed_above_desc - below_desc_h - pad_bottom - (10 if desc_full_lines else 0)
        desc_max_lines = max(0, int(desc_avail_h // max(1, desc_font.get_height() + desc_gap)))
        desc_draw_lines = list(wrap_text_limited(desc_txt, desc_font, inner_w, max_lines=desc_max_lines).lines) if desc_full_lines else []

        # === ÇİZİM ===========================================================
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        inner_x = panel_rect.x + pad_x

        # Sağdaki standart HUD paneli ile aynı stil: glass panel (alpha=90)
        ui_style.draw_glass_panel(self.screen, panel_rect, alpha=90, border_color=(60, 70, 90))

        recorded = {
            'panel': panel_rect,
            'desc_max_lines': int(desc_max_lines),
            'content_budget': int(panel_h),
        }
        cursor = panel_rect.y + pad_top

        def _blit_lines(lines, font, color, font_size, line_gap):
            """Sarılmış satırları LRU önbellekli render_fit_text ile çiz."""
            rects = []
            drawn_h = 0
            for line in lines:
                surf = ui_style.render_fit_text(line, color, inner_w, font_size, bold=False)
                self.screen.blit(surf, (inner_x, cursor + drawn_h))
                rects.append(pygame.Rect(inner_x, cursor + drawn_h, surf.get_width(), surf.get_height()))
                drawn_h += surf.get_height() + line_gap
            if not rects:
                return rects, 0
            return rects, max(0, drawn_h - line_gap)

        self.screen.blit(title_surf, (inner_x, cursor))
        recorded['title'] = pygame.Rect(inner_x, cursor, title_surf.get_width(), title_surf.get_height())
        cursor += title_surf.get_height() + 8

        self.screen.blit(name_surf, (inner_x, cursor))
        recorded['name'] = pygame.Rect(inner_x, cursor, name_surf.get_width(), name_surf.get_height())
        cursor += name_surf.get_height() + 10

        # Açıklama — dinamik satır limitiyle (desc_max_lines).
        desc_rects, desc_draw_h = _blit_lines(desc_draw_lines, desc_font, (160, 170, 190), desc_size, desc_gap)
        recorded['desc_lines'] = desc_rects
        if desc_draw_h > 0:
            cursor += desc_draw_h + 10

        briefing_rects, briefing_draw_h = _blit_lines(briefing_lines, briefing_font, (175, 190, 220), briefing_size, briefing_gap)
        recorded['briefing_lines'] = briefing_rects
        if briefing_draw_h > 0:
            cursor += briefing_draw_h + 10

        target_rects, target_draw_h = _blit_lines(target_lines, target_font, (200, 210, 225), target_size, target_gap)
        recorded['target_lines'] = target_rects
        if target_draw_h > 0:
            cursor += target_draw_h + 8

        # Hedef progress barı — hedef satırının altında (rapor: rect kaydı).
        progress_rect = pygame.Rect(inner_x, cursor, inner_w, progress_h)
        pygame.draw.rect(self.screen, (255, 255, 255, 22), progress_rect, border_radius=8)
        if progress > 0:
            fill_w = int(inner_w * (progress / 100.0))
            color = GREEN if progress >= 100 else YELLOW if progress >= 50 else ORANGE
            pygame.draw.rect(self.screen, color, (inner_x, cursor, fill_w, progress_h), border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255, 40), progress_rect, 1, border_radius=8)
        recorded['progress'] = progress_rect
        cursor = progress_rect.bottom + 12

        if completed_surf is not None:
            self.screen.blit(completed_surf, (inner_x, cursor))
            recorded['completed'] = pygame.Rect(inner_x, cursor, completed_surf.get_width(), completed_surf.get_height())
            cursor += completed_surf.get_height() + 4

        if bonus_surf is not None:
            self.screen.blit(bonus_surf, (inner_x, cursor))
            recorded['bonus'] = pygame.Rect(inner_x, cursor, bonus_surf.get_width(), bonus_surf.get_height())
            cursor += bonus_surf.get_height() + 10

        if effects_title_surf is not None:
            self.screen.blit(effects_title_surf, (inner_x, cursor))
            recorded['effects_title'] = pygame.Rect(inner_x, cursor, effects_title_surf.get_width(), effects_title_surf.get_height())
            cursor += effects_title_surf.get_height() + 5
            effects_line_rects = []
            for group in effects_line_groups:
                group_h = _lines_height(group, fx_font, fx_gap)
                if cursor + group_h > panel_rect.bottom - pad_bottom:
                    break
                group_rects, group_draw_h = _blit_lines(group, fx_font, (200, 210, 235), fx_size, fx_gap)
                effects_line_rects.extend(group_rects)
                cursor += group_draw_h + 2
            recorded['effects_lines'] = effects_line_rects
            cursor += 6

        # Kural / başarısızlık / ödül satırları
        detail_rects = []
        for group, detail_color in detail_groups:
            group_h = _lines_height(group, detail_font, detail_gap)
            if cursor + group_h > panel_rect.bottom - pad_bottom:
                break
            group_rects, group_draw_h = _blit_lines(group, detail_font, detail_color, detail_size, detail_gap)
            detail_rects.extend(group_rects)
            cursor += group_draw_h + 5
        recorded['details'] = detail_rects

        mistakes_rects = []
        if mistakes_lines:
            block_h = _lines_height(mistakes_lines, mistakes_font, mistakes_gap)
            if cursor + block_h <= panel_rect.bottom - pad_bottom:
                mistakes_rects, mistakes_draw_h = _blit_lines(mistakes_lines, mistakes_font, (255, 170, 145), mistakes_size, mistakes_gap)
                cursor += mistakes_draw_h + 6
        recorded['mistakes'] = mistakes_rects

        status_rects = []
        if status_lines:
            block_h = _lines_height(status_lines, status_font, status_gap)
            if cursor + block_h <= panel_rect.bottom - pad_bottom:
                status_rects, status_draw_h = _blit_lines(status_lines, status_font, status_color, status_size, status_gap)
                cursor += status_draw_h + 6
        recorded['status'] = status_rects

        streak_rect = None
        if streak_surf is not None:
            if cursor + streak_surf.get_height() <= panel_rect.bottom - pad_bottom:
                self.screen.blit(streak_surf, (inner_x, cursor))
                streak_rect = pygame.Rect(inner_x, cursor, streak_surf.get_width(), streak_surf.get_height())
                cursor += streak_surf.get_height() + 5
        recorded['streak'] = streak_rect

        adaptive_rect = None
        if adaptive_surf is not None:
            if cursor + adaptive_surf.get_height() <= panel_rect.bottom - pad_bottom:
                self.screen.blit(adaptive_surf, (inner_x, cursor))
                adaptive_rect = pygame.Rect(inner_x, cursor, adaptive_surf.get_width(), adaptive_surf.get_height())
                cursor += adaptive_surf.get_height() + 4
        recorded['adaptive'] = adaptive_rect

        # P1-5: gerçek blit rect'leri containment testleri için kaydedilir.
        all_rects = [
            recorded['title'], recorded['name'], recorded['progress'],
            recorded.get('completed'), recorded.get('bonus'),
            recorded.get('effects_title'), recorded.get('streak'),
            recorded.get('adaptive'),
        ]
        for rect_list in (
            recorded.get('desc_lines'), recorded.get('briefing_lines'),
            recorded.get('target_lines'), recorded.get('effects_lines'),
            recorded.get('details'), recorded.get('mistakes'),
            recorded.get('status'),
        ):
            if rect_list:
                all_rects.extend(rect_list)
        content_bottom = max(
            (rect.bottom for rect in all_rects if rect is not None),
            default=panel_rect.y + pad_top,
        )
        recorded['content_bottom'] = int(content_bottom)
        self._daily_panel_rects = recorded
        return 0

    def can_restart(self) -> bool:
        if not super().can_restart():
            return False
        if self.challenge_completed and self.user_manager:
            status = self.user_manager.get_daily_status()
            if status and status.get('completed'):
                return False
        return self._remaining_daily_attempts() > 0

    def restart(self):
        if not self.can_restart():
            from localization import t

            self.show_game_over_warning(t('dc_no_attempts_left'), 2.2)
            return
        self._daily_outcome_recorded = False
        self._score_recorded = False
        self.challenge_completed = False
        self.mistakes_made = 0
        self._daily_failed = False
        super().restart()
        self._apply_modifiers()
        self.fall_speed = int(self.get_initial_speed() * self.speed_multiplier)

    def finalize_run(self, playtime: int | None = None) -> None:
        super().finalize_run(playtime)
        self.record_daily_outcome(self.challenge_completed)

    def record_daily_outcome(self, success: bool) -> None:
        if getattr(self, '_daily_outcome_recorded', False):
            return
        self._daily_outcome_recorded = True
        if not self.user_manager:
            return
        self.user_manager.register_daily_result(success, challenge_id=self.challenge.get('id'))
        status = self.user_manager.get_daily_status()
        if self.achievement_manager and status:
            try:
                self.achievement_manager.update_stats(
                    daily_max_streak=int(status.get('streak', 0) or 0)
                )
            except Exception:
                pass

        if success:
            reward_fragments = int(self.challenge.get('reward_fragments', 0) or 0)
            reward_xp = int(self.challenge.get('reward_xp', 0) or 0)
            try:
                if reward_fragments > 0 and hasattr(self.user_manager, 'add_fragments'):
                    self.user_manager.add_fragments(reward_fragments)
            except Exception:
                pass
            try:
                if reward_xp > 0 and hasattr(self.user_manager, 'add_xp'):
                    self.user_manager.add_xp('daily', reward_xp)
            except Exception:
                pass
            print("Daily Challenge tamamlandı! Haklar kilitlendi.")
        else:
            remaining = max(0, DAILY_MAX_FAILURES - status.get('fails', 0)) if status else 0
            print(f"Daily Challenge başarısız. Kalan hak: {remaining}/{DAILY_MAX_FAILURES}")
