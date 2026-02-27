"""Campaign Modu - 100 Level Quadrix Macerası

Game class'ından türeyen ana campaign modu.
Her level için farklı görevler ve zorluklar sunar.
"""
from __future__ import annotations

import pygame
import random
import math
from typing import Dict, Any, List, Optional, TYPE_CHECKING

try:
    from ..game import Game  # type: ignore
    from ..constants import COLORS, BLACK, BOARD_WIDTH, BOARD_HEIGHT  # type: ignore
    from ..pieces import SHAPE_NAMES  # type: ignore
    from ..localization import t  # type: ignore
except Exception:
    from game import Game
    from constants import COLORS, BLACK, BOARD_WIDTH, BOARD_HEIGHT
    from pieces import SHAPE_NAMES
    from localization import t

from .level_data import get_level, get_total_levels, LevelConfig, get_world_info
from .objectives import (
    Objective,
    ClearLinesObjective,
    ScoreObjective,
    TetrisObjective,
    ComboObjective,
    TimeObjective,
    SpecialBlockObjective,
    MoveEfficiencyObjective,
    ClearGarbageObjective,
    create_objective,
)
from .special_blocks import (
    SpecialBlockManager,
    SpecialBlockType,
    create_level_special_blocks,
)
from .campaign_ui import campaign_ui_effects


class CampaignMode(Game):
    """Campaign Modu - 100 Level Quadrix Macerası"""
    
    def __init__(
        self,
        current_level: int = 1,
        difficulty: str = 'Normal',
        sound_enabled: bool = True,
        effects_enabled: bool = True,
        achievement_manager = None,
        theme_manager = None,
        screen = None,
        fullscreen: bool = False,
        settings_manager = None,
        user_manager = None,
        score_manager = None,
    ):
        """Campaign modunu başlat
        
        Args:
            current_level: Oynanacak level numarası (1-100)
            Diğer argümanlar Game class'ına aktarılır
        """
        # Level bilgisini yükle
        self.current_level_num = current_level
        self.level_config: Optional[LevelConfig] = get_level(current_level)
        
        if not self.level_config:
            raise ValueError(f"Geçersiz level numarası: {current_level}")
        
        # Parça seed'i (hızlı tekrar için deterministik sıra)
        self._piece_seed = random.randint(0, 2**31 - 1)
        
        # Game class'ını başlat
        super().__init__(
            difficulty=difficulty,
            sound_enabled=sound_enabled,
            effects_enabled=effects_enabled,
            achievement_manager=achievement_manager,
            theme_manager=theme_manager,
            screen=screen,
            fullscreen=fullscreen,
            settings_manager=settings_manager,
            user_manager=user_manager,
            game_mode='campaign',
            score_manager=score_manager,
            piece_rng_seed=self._piece_seed,
        )
        
        self.mode_name = t('campaign_title')
        self.controls_under_stats = True
        
        # Level state
        self.level_complete = False
        self.level_failed = False
        self.paused = False

        # Hızlı tekrar için seed sakla
        self._quick_retry_seed = self._piece_seed
        
        # Zamanlama
        self.start_time = pygame.time.get_ticks()
        self.elapsed_time = 0.0
        
        # Hamle sayacı
        self.moves_count = 0
        
        # Yıldız koşulları için istatistikler
        self.total_combos = 0           # Toplam combo sayısı
        self.max_combo_chain = 0        # En uzun combo zinciri (üst üste combo)
        self.current_combo_chain = 0    # Mevcut combo zinciri
        self.tetris_count = 0           # Quadrix sayısı (4'lü)
        self.double_count = 0           # Double sayısı (2'li)
        self.triple_count = 0           # Triple sayısı (3'lü)
        
        # Görevleri oluştur
        self.objectives: List[Objective] = self._create_objectives()
        
        # Yıldız sistemi
        self.earned_stars = 0
        self.star_conditions = self.level_config.stars
        
        # Level-specific hız ayarla
        self.fall_speed = self.level_config.speed
        
        # İzin verilen blokları ayarla
        self._allowed_pieces = self.level_config.allowed_pieces
        
        # === BOSS VE MINI BOSS KONTROLLERI ===
        # Level son hanesi
        level_last_digit = self.current_level_num % 10
        
        # Mini Boss: 5 ile bitenler (5, 15, 25, 35...) - Hold devre dışı
        self.is_mini_boss = level_last_digit == 5
        
        # Boss: 0 ile bitenler (10, 20, 30, 40...) - Next piece gizli
        self.is_boss = level_last_digit == 0 and self.current_level_num > 0
        
        # Özel kurallar
        # Mini boss veya boss ise hold devre dışı
        if self.is_mini_boss or self.is_boss:
            self.can_hold = False
            self._no_hold_permanent = True
            self._show_hold_x = True  # Saklama alanında X göster
        else:
            self.can_hold = not self.level_config.no_hold
            self._no_hold_permanent = self.level_config.no_hold
            self._show_hold_x = False
        
        # Boss ise next piece gizli
        self._hide_next_pieces = self.is_boss
        
        # Özel blok yöneticisi
        self.special_block_manager = SpecialBlockManager()
        self._init_special_blocks()
        
        # Çöp blokları yerleştir (level 6+)
        self._place_garbage_blocks()
        
        # UI için font cache
        self._init_campaign_fonts()
        
        # İlerleme yöneticisi referansı (lazy load)
        self._progress_manager = None
    
    def _place_garbage_blocks(self) -> None:
        """Level konfigürasyonuna göre sabit şekilli çöp blokları yerleştir"""
        if not self.level_config:
            return
        
        # Level 6'dan önce çöp blok yok
        if self.current_level_num < 6:
            return
        
        # Board referansı
        if not self.board or not hasattr(self.board, 'grid'):
            return
        
        # Çöp grid'i oluştur (level'a göre sabit şekil)
        from .level_data import generate_garbage_grid
        
        board_width = self.board.width
        board_height = self.board.height
        
        garbage_grid = generate_garbage_grid(
            rows=10,  # Max satır, ama şekil kendi boyutunu belirler
            cols=board_width, 
            pattern='shape',  # Artık sabit şekil kullanıyoruz
            level=self.current_level_num
        )
        
        if not garbage_grid:
            return
        
        garbage_rows = len(garbage_grid)
        
        # Görev tipini kontrol et - clear_garbage görevi varsa gri renk kullan
        is_clear_garbage_mission = any(
            obj_config.get('type') == 'clear_garbage' 
            for obj_config in self.level_config.objectives
        )
        
        if is_clear_garbage_mission:
            # Günlük görevdeki gibi gri/mor tonunda çöp rengi
            GARBAGE_GRAY = (70, 70, 100)
            print(f"[GARBAGE] Level {self.current_level_num}: ÇÖP TEMİZLEME GÖREVİ - Gri bloklar")
        else:
            print(f"[GARBAGE] Level {self.current_level_num}: {garbage_rows} satır şekil yerleştiriliyor")
        
        # Blok renkleri
        if is_clear_garbage_mission:
            # Çöp temizleme görevi: Tek renk gri
            garbage_colors = [(70, 70, 100)]  # Gri/mor ton (günlük görevdeki gibi)
        else:
            # Normal görevler: Quadrix standart renkleri
            garbage_colors = [
                (0, 255, 255),    # Cyan (I)
                (255, 255, 0),    # Yellow (O)
                (128, 0, 128),    # Purple (T)
                (0, 255, 0),      # Green (S)
                (255, 0, 0),      # Red (Z)
                (0, 0, 255),      # Blue (J)
                (255, 165, 0),    # Orange (L)
            ]
        
        placed_count = 0
        for row_idx, garbage_row in enumerate(garbage_grid):
            # Board'un alt kısmına yerleştir
            board_y = board_height - garbage_rows + row_idx
            
            if board_y < 0 or board_y >= board_height:
                continue
            
            for col_idx, cell_value in enumerate(garbage_row):
                if col_idx >= board_width:
                    continue
                
                if cell_value > 0:
                    # Renk seç
                    if is_clear_garbage_mission:
                        color = garbage_colors[0]  # Her zaman gri
                    else:
                        color_idx = (cell_value - 1) % len(garbage_colors)
                        color = garbage_colors[color_idx]
                    
                    # Board grid'ine yerleştir
                    self.board.grid[board_y][col_idx] = color
                    # OCCUPANCY'Yİ DE GÜNCELLE - bu olmadan bloklar görünmez!
                    self.board.occupancy[board_y][col_idx] = True
                    placed_count += 1
        
        print(f"[GARBAGE] ✅ {placed_count} hücre yerleştirildi!")
        
        # ClearGarbageObjective varsa hedefini güncelle
        if is_clear_garbage_mission and placed_count > 0:
            for obj in self.objectives:
                if isinstance(obj, ClearGarbageObjective):
                    obj.set_initial_garbage(placed_count)
                    print(f"[GARBAGE] ClearGarbageObjective hedefi: {placed_count} hücre")
        
    def _init_special_blocks(self) -> None:
        """Level konfigürasyonuna göre özel blokları başlat"""
        if not self.level_config or not self.level_config.special_blocks:
            return
        
        # Level'da tanımlı özel blokları oluştur
        for block_config in self.level_config.special_blocks:
            block_type_str = block_config.get('type', '')
            count = block_config.get('count', 0)
            
            if not block_type_str or count <= 0:
                continue
            
            try:
                block_type = SpecialBlockType(block_type_str)
            except ValueError:
                continue
            
            # Önceden yerleştirilmiş bloklar için pozisyon hesapla
            # Board'un alt yarısına rastgele yerleştir
            import random
            board_width = self.board.width if self.board else 10
            board_height = self.board.height if self.board else 20
            
            available_positions = []
            start_row = max(board_height // 2, board_height - 8)
            
            for y in range(start_row, board_height - 1):
                for x in range(board_width):
                    available_positions.append((x, y))
            
            random.shuffle(available_positions)
            
            for i in range(min(count, len(available_positions))):
                x, y = available_positions[i]
                self.special_block_manager.add_special_block(x, y, block_type, **block_config)
    
    def _init_campaign_fonts(self) -> None:
        """Campaign için font cache ve ikonları oluştur"""
        self.campaign_font_large = pygame.font.Font(None, 48)
        self.campaign_font_medium = pygame.font.Font(None, 36)
        self.campaign_font_small = pygame.font.Font(None, 28)
        self.campaign_font_tiny = pygame.font.Font(None, 22)
        
        # Yıldız ve tik ikonlarını yükle
        self._load_campaign_icons()
    
    def _load_campaign_icons(self) -> None:
        """Yıldız ve tik ikonlarını yükle"""
        import os
        
        # Varsayılan değerler
        self.star_icon_small = None
        self.star_icon_medium = None
        self.star_icon_large = None
        self.tick_icon = None
        
        # Yıldız ikonunu yükle
        star_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'ui', 'yıldız.png'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'yıldız.png'),
            'assets/ui/yıldız.png',
        ]
        
        for path in star_paths:
            try:
                if os.path.exists(path):
                    star_img = pygame.image.load(path).convert_alpha()
                    # 3 farklı boyutta yıldız (HUD okunabilirliği artırıldı)
                    self.star_icon_small = pygame.transform.smoothscale(star_img, (16, 16))
                    self.star_icon_medium = pygame.transform.smoothscale(star_img, (20, 20))
                    self.star_icon_large = pygame.transform.smoothscale(star_img, (26, 26))
                    print(f"✅ Yıldız ikonu yüklendi: {path}")
                    break
            except Exception as e:
                print(f"⚠️ Yıldız ikonu yüklenemedi: {e}")
        
        # Tik işareti surface oluştur (daha okunaklı)
        tick_size = 18
        self.tick_icon = pygame.Surface((tick_size, tick_size), pygame.SRCALPHA)
        # Tik çiz
        tick_color = (0, 255, 100)  # Yeşil
        pygame.draw.line(self.tick_icon, tick_color, (3, 9), (7, 14), 3)
        pygame.draw.line(self.tick_icon, tick_color, (7, 14), (15, 5), 3)
    
    def _create_objectives(self) -> List[Objective]:
        """Level konfigürasyonundan görevleri oluştur"""
        if not self.level_config:
            return [ClearLinesObjective(target=10)]
        
        objectives = []
        for obj_config in self.level_config.objectives:
            obj_type = obj_config.get('type', 'clear_lines')
            obj = create_objective(obj_type, **obj_config)
            objectives.append(obj)
        
        return objectives
    
    # === BLOK KISITLAMA ===
    
    def _get_base_piece_factories(self) -> list:
        """Sadece izin verilen blokları döndür"""
        if not hasattr(self, '_allowed_pieces') or not self._allowed_pieces:
            return super()._get_base_piece_factories()
        
        return [self._make_named_piece_factory(name) for name in self._allowed_pieces]
    
    # === HIZ KONTROL ===
    
    def get_initial_speed(self) -> int:
        """Level'a özel başlangıç hızı"""
        if self.level_config:
            return self.level_config.speed
        return 800
    
    def get_current_speed(self) -> int:
        """Campaign modunda hız sabit kalır (level-based)"""
        return self.get_initial_speed()
    
    # === OYUN DÖNGÜSÜ ===
    
    def update(self, dt: float) -> None:
        """Oyun durumunu güncelle"""
        # UI efektlerini her zaman güncelle (animasyonlar için)
        dt_seconds = dt / 1000.0
        campaign_ui_effects.update(dt_seconds)
        
        if self.level_complete or self.level_failed:
            return
        
        # Süre güncelle
        self.elapsed_time = (pygame.time.get_ticks() - self.start_time) / 1000.0
        
        # Zaman görevlerini güncelle
        self._emit_event('time_update', {'elapsed': self.elapsed_time})
        
        # Özel blokları güncelle (timer blokları vb.)
        special_events = self.special_block_manager.update(dt_seconds, self.board)
        
        # Patlama veya timer olayları varsa işle
        if special_events.get('explosions'):
            for explosion in special_events['explosions']:
                self._emit_event('explosion', explosion)
                # Patlama görsel efekti
                if explosion.get('center'):
                    cell_size = getattr(self, 'cell_size', 30)
                    cx, cy = explosion['center']
                    campaign_ui_effects.trigger_explosion(
                        cx * cell_size, 
                        cy * cell_size, 
                        cell_size
                    )
                # Patlama puanı
                cleared = len(explosion.get('cleared_cells', []))
                if cleared > 0:
                    self.board.score += cleared * 10
        
        if special_events.get('points_earned', 0) > 0:
            self.board.score += special_events['points_earned']
        
        # Zaman limiti kontrolü
        if self.level_config and self.level_config.time_limit:
            if self.elapsed_time >= self.level_config.time_limit:
                self._handle_level_failed(t('campaign_fail_time'))
                return
        
        # Normal oyun güncellemesi
        super().update(dt)
        
        # Skor güncelleme eventi
        self._emit_event('score_update', {'score': self.board.score})
        
        # Görev tamamlama kontrolü
        self._check_objectives_completion()
    
    def lock_and_new_piece(self) -> None:
        """Parçayı kilitle ve görevleri güncelle"""
        # Hamle sayacını artır
        self.moves_count += 1
        self._emit_event('piece_placed', {'moves': self.moves_count})
        
        # Önceki satır sayısını kaydet
        prev_lines = self.board.lines_cleared
        prev_combo = self.board.combo
        prev_tetrises = self.board.tetrises
        
        # Temizlenen satırları takip et (özel bloklar için)
        prev_grid = [row[:] for row in self.board.grid]
        
        # Normal kilitleme işlemi
        super().lock_and_new_piece()
        
        # Satır temizlendi mi?
        new_lines = self.board.lines_cleared - prev_lines
        if new_lines > 0:
            # Temizlenen satırları bul
            cleared_rows = []
            for y in range(len(prev_grid)):
                if y < len(self.board.grid):
                    # Satır değiştiyse temizlenmiş olabilir
                    if prev_grid[y] != self.board.grid[y]:
                        cleared_rows.append(y)
            
            # Sadece gerçekten temizlenen (boş olmayan) satırları filtrele
            actually_cleared = []
            for row in cleared_rows:
                if row < len(prev_grid) and all(cell is not None for cell in prev_grid[row]):
                    actually_cleared.append(row)
            
            # Özel blokları satır temizleme için güncelle
            if actually_cleared:
                special_result = self.special_block_manager.on_line_cleared(
                    actually_cleared, self.board
                )
                
                # Eriyen buz bloklarını event olarak gönder
                if special_result.get('ice_melted'):
                    self._emit_event('special_block_cleared', {
                        'type': 'ice',
                        'count': len(special_result['ice_melted'])
                    })
                
                # Toplanan puan
                if special_result.get('points_earned', 0) > 0:
                    self.board.score += special_result['points_earned']
                
                # Özel blokları aşağı kaydır
                self.special_block_manager.shift_blocks_down(actually_cleared)
            
            self._emit_event('lines_cleared', {
                'lines': new_lines,
                'total_lines': self.board.lines_cleared
            })
            
            # === YILDIZ İSTATİSTİKLERİ ===
            # Double (2'li), Triple (3'lü), Quadrix (4'lü) sayımı
            if new_lines == 2:
                self.double_count += 1
            elif new_lines == 3:
                self.triple_count += 1
            elif new_lines >= 4:
                self.tetris_count += 1
                self._emit_event('tetris', {
                    'count': self.board.tetrises,
                    'new': self.board.tetrises - prev_tetrises
                })
        
        # === COMBO TAKİBİ ===
        if self.board.combo > prev_combo:
            # Combo devam ediyor
            self.total_combos += 1
            self.current_combo_chain += 1
            self.max_combo_chain = max(self.max_combo_chain, self.current_combo_chain)
            self._emit_event('combo_update', {'combo': self.board.combo})
        elif new_lines == 0 and prev_combo > 0:
            # Combo kırıldı
            self.current_combo_chain = 0
            self._emit_event('combo_break', {'last_combo': prev_combo})
        
        # Blok sınırı kontrolü
        if self.level_config and self.level_config.move_limit:
            if self.moves_count >= self.level_config.move_limit:
                # Görevler tamamlandı mı kontrol et
                if not all(obj.completed for obj in self.objectives):
                    self._handle_level_failed(t('campaign_fail_blocks'))
        
        # Hold kuralını uygula
        if self._no_hold_permanent:
            self.can_hold = False
    
    def _emit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Tüm görevlere event gönder"""
        for objective in self.objectives:
            objective.update(self, event_type, event_data)
    
    def _check_objectives_completion(self) -> None:
        """Tüm görevler tamamlandı mı kontrol et"""
        if all(obj.completed for obj in self.objectives):
            self._handle_level_complete()
    
    def _handle_level_complete(self) -> None:
        """Level tamamlandığında"""
        if self.level_complete:
            return
        
        self.level_complete = True
        
        # Yıldızları hesapla
        self.earned_stars = self._calculate_stars()
        
        # UI animasyonunu başlat
        campaign_ui_effects.start_level_complete(self.earned_stars)
        
        # Başarı sesi
        if self.sound_enabled and self.sound:
            self.sound.play('level_up')
        
        # İlerlemeyi kaydet
        self._save_progress()
        
        # Finalize
        self.finalize_run(playtime=int(self.elapsed_time))
    
    def _handle_level_failed(self, reason: str = "") -> None:
        """Level başarısız olduğunda"""
        if self.level_failed:
            return
        
        self.level_failed = True
        self.fail_reason = reason
        
        # UI animasyonunu başlat
        campaign_ui_effects.start_level_failed(reason)
        
        # Başarısızlık sesi
        if self.sound_enabled and self.sound:
            self.sound.play('game_over')

    def _is_star_condition_met(self, condition: Dict[str, Any]) -> bool:
        """Yıldız koşulu sağlandı mı?"""
        condition_type = condition.get('type')
        target_value = condition.get('value', 0)

        if condition_type == 'complete':
            return all(obj.completed for obj in self.objectives)

        if condition_type == 'score':
            return self.board.score >= target_value

        if condition_type == 'combo':
            return self.total_combos >= target_value

        if condition_type == 'multi_clear':
            if target_value == 2:
                return (self.double_count + self.triple_count + self.tetris_count) >= 1
            if target_value == 3:
                return (self.triple_count + self.tetris_count) >= 1
            return self.double_count >= 1 or self.triple_count >= 1

        if condition_type == 'tetris':
            return self.tetris_count >= target_value

        if condition_type == 'combo_chain':
            return self.max_combo_chain >= target_value

        if condition_type == 'time_limit':
            return bool(self.level_complete and self.elapsed_time <= target_value)

        if condition_type == 'time':
            return self.elapsed_time <= target_value

        if condition_type == 'efficiency':
            main_progress = self.objectives[0].progress if self.objectives else 0
            return main_progress >= target_value

        if condition_type == 'extra_lines':
            total_lines = self.board.lines_cleared if self.board else 0
            main_target = 0
            if self.objectives and hasattr(self.objectives[0], 'target'):
                main_target = self.objectives[0].target
            return total_lines >= main_target + target_value

        return False

    def _calculate_stars(self) -> int:
        """Yıldız sayısını hesapla"""
        stars = 0
        condition_results = {}

        for star_num, condition in self.star_conditions.items():
            condition_results[int(star_num)] = self._is_star_condition_met(condition)

        if condition_results.get(1, False):
            stars = 1
            if condition_results.get(2, False):
                stars = 2
                if condition_results.get(3, False):
                    stars = 3

        return stars
    
    def _save_progress(self) -> None:
        """İlerlemeyi kaydet"""
        if not self.settings_manager:
            return
        
        # Mevcut ilerlemeyi al
        progress = self.settings_manager.get('campaign_progress', {})
        if not isinstance(progress, dict):
            progress = {}
        
        completed = progress.get('completed_levels', {})
        if not isinstance(completed, dict):
            completed = {}
        
        # Bu level'ın verilerini güncelle
        level_key = str(self.current_level_num)
        existing = completed.get(level_key, {})
        
        # Sadece daha iyi sonuçları kaydet
        best_stars = max(self.earned_stars, existing.get('stars', 0))
        best_score = max(self.board.score, existing.get('best_score', 0))
        
        completed[level_key] = {
            'stars': best_stars,
            'best_score': best_score,
            'completed': True,
            'attempts': existing.get('attempts', 0) + 1
        }
        
        # En yüksek level'ı güncelle
        highest = max(self.current_level_num, progress.get('highest_level', 0))
        
        # Toplam yıldızları hesapla
        total_stars = sum(l.get('stars', 0) for l in completed.values())
        
        progress['completed_levels'] = completed
        progress['highest_level'] = highest
        progress['total_stars'] = total_stars
        progress['current_world'] = (highest - 1) // 20 + 1
        
        self.settings_manager.set('campaign_progress', progress)
        self.settings_manager.save()

        # Kampanya yıldız başarımlarını kontrol et
        if self.achievement_manager:
            ach_kwargs = {'campaign_total_stars': total_stars}
            if self.current_level_num == 50:
                ach_kwargs['campaign_level_50_stars'] = best_stars
            if self.current_level_num == 100:
                ach_kwargs['campaign_level_100_stars'] = best_stars
            new_achs = self.achievement_manager.update_stats(**ach_kwargs)
            for ach_id in new_achs:
                achievement = self.achievement_manager.get_achievement(ach_id)
                if achievement:
                    self.achievement_notifications.append({
                        'achievement': achievement,
                        'time': pygame.time.get_ticks(),
                        'alpha': 255
                    })
    
    # === INPUT HANDLING ===
    
    def handle_input(self):
        """Kullanıcı girdilerini işle"""
        if self.level_complete or self.level_failed:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'
                    if event.key == pygame.K_r:
                        self.restart()
                        return True
                    if event.key == pygame.K_f:
                        self.quick_restart()
                        return True
                    if event.key == pygame.K_s:
                        return 'campaign_select'
                    if event.key == pygame.K_m:
                        return 'main_menu'
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.level_complete:
                        # Sonraki level'a geç
                        return 'next_level'
            return True
        
        return super().handle_input()
    
    def _reset_level_state(self) -> None:
        """Level state'ini sıfırla"""
        self.level_complete = False
        self.level_failed = False
        self.start_time = pygame.time.get_ticks()
        self.elapsed_time = 0.0
        self.moves_count = 0
        self.earned_stars = 0

        # Yıldız istatistiklerini sıfırla
        self.total_combos = 0
        self.max_combo_chain = 0
        self.current_combo_chain = 0
        self.tetris_count = 0
        self.double_count = 0
        self.triple_count = 0

        # Görevleri sıfırla
        for obj in self.objectives:
            obj.reset()

        # Özel blok yöneticisini sıfırla ve yeniden oluştur
        self.special_block_manager = SpecialBlockManager()
        self._init_special_blocks()

        # Çöp bloklarını yeniden yerleştir
        self._place_garbage_blocks()

        # Hız ayarla
        self.fall_speed = self.get_initial_speed()

    def restart(self) -> None:
        """Level'ı yeniden başlat"""
        self._piece_seed = random.randint(0, 2**31 - 1)
        self._quick_retry_seed = self._piece_seed
        self._piece_rng_seed = self._piece_seed
        super().restart()
        self._reset_level_state()

    def quick_restart(self) -> None:
        """Level'ı aynı parça seed'i ile yeniden başlat"""
        if getattr(self, '_quick_retry_seed', None) is None:
            self._quick_retry_seed = getattr(self, '_piece_rng_seed', None)
        self._piece_rng_seed = self._quick_retry_seed
        super().restart()
        self._reset_level_state()
    
    # === UI/HUD ===
    
    def draw_mode_info(self, info_x: int, info_y: int) -> int:
        """Sol panelde level bilgilerini göster"""
        from retro_style import retro_style
        from ui_theme import UIFonts
        from localization import get_language
        
        board_offset_x, board_offset_y = self.get_board_offset()
        
        # Renkler (merkezi tema)
        from ui_theme import UIColors
        NEON_GOLD = UIColors.NEON_GOLD
        NEON_CYAN = UIColors.NEON_CYAN
        NEON_PURPLE = UIColors.NEON_MAGENTA
        THEME_BORDER = UIColors.BUTTON_BORDER
        THEME_ACCENT = UIColors.NEON_CYAN
        NEON_GREEN = UIColors.NEON_GREEN
        STAR_COLORS = {
            1: UIColors.TEXT_SECONDARY,  # Gümüş
            2: (255, 200, 100),          # Bronz
            3: UIColors.NEON_GOLD,       # Altın
        }
        
        # Panel boyutları - daha geniş ve adaptif (okunabilirlik odaklı)
        available_left = max(240, int(board_offset_x) - 26)
        panel_width = max(280, min(340, available_left))
        max_panel_h = int(self.screen.get_height() - board_offset_y - 14)
        panel_height = max(500, min(620, max_panel_h))
        panel_x = board_offset_x - panel_width - 20
        if panel_x < 10:
            panel_x = 10
        panel_y = board_offset_y
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Glass panel
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=175,
            border_color=THEME_ACCENT,
            glow=False
        )

        def wrap_text_lines(font: pygame.font.Font, text: str, max_width: int, max_lines: int = 2) -> list[str]:
            raw = str(text or '').strip()
            if not raw:
                return []
            words = raw.split()
            if not words:
                return []
            lines: list[str] = []
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
                    if len(lines) >= max_lines - 1:
                        break
            if len(lines) < max_lines:
                lines.append(current)
            return lines[:max_lines]

        # Başlık arka planı (okunabilirlik)
        header_bg = pygame.Rect(panel_rect.x + 10, panel_rect.y + 10, panel_width - 20, 60)
        header_surf = pygame.Surface(header_bg.size, pygame.SRCALPHA)
        header_surf.fill((*UIColors.BG_MEDIUM, 190))
        self.screen.blit(header_surf, header_bg.topleft)
        pygame.draw.rect(self.screen, THEME_BORDER, header_bg, 1, border_radius=10)

        # İçerik arka planı
        content_bg = pygame.Rect(panel_rect.x + 10, panel_rect.y + 74, panel_width - 20, panel_height - 86)
        content_surf = pygame.Surface(content_bg.size, pygame.SRCALPHA)
        content_surf.fill((*UIColors.BG_DARK, 160))
        self.screen.blit(content_surf, content_bg.topleft)
        pygame.draw.rect(self.screen, UIColors.GLASS_BORDER[:3], content_bg, 1, border_radius=10)
        
        # === LEVEL BİLGİSİ ===
        header_font = UIFonts.subheading()
        title_font = UIFonts.get(24, bold=True)
        lang = get_language()
        level_name = self.level_config.name.get(lang, self.level_config.name.get('en', f"{t('level')} {self.current_level_num}"))
        world_info = get_world_info(self.level_config.world)
        world_name = world_info['name'].get(lang, world_info['name'].get('en', t('world')))
        
        # Dünya ve Level
        world_text = header_font.render(world_name, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(world_text, (panel_rect.x + 18, panel_rect.y + 16))
        
        level_label = f"{t('level')} {self.current_level_num}: {level_name}"
        level_lines = wrap_text_lines(title_font, level_label, panel_width - 42, max_lines=2)
        base_y = panel_rect.y + 42
        for idx, line in enumerate(level_lines):
            level_text = title_font.render(line, True, NEON_GOLD)
            self.screen.blit(level_text, (panel_rect.x + 18, base_y + idx * 22))
        
        # Ayırıcı çizgi
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + 15, panel_rect.y + 78),
            (panel_rect.right - 15, panel_rect.y + 78), 1
        )
        
        # === GÖREVLER ===
        obj_font = UIFonts.body()
        progress_font = UIFonts.get(20)
        y_offset = panel_rect.y + 102
        
        for obj in self.objectives:
            # Görev durumu
            status_color = NEON_GREEN if obj.completed else UIColors.TEXT_PRIMARY
            
            # X pozisyonu
            x_pos = panel_rect.x + 15
            
            # Görev durum simgesi (daha belirgin)
            icon_size = 18
            icon_center = (x_pos + icon_size // 2, y_offset + 12)
            if obj.completed:
                pygame.draw.circle(self.screen, (12, 120, 70), icon_center, 9)
                pygame.draw.circle(self.screen, (40, 255, 155), icon_center, 9, 1)
                pygame.draw.line(self.screen, (220, 255, 230), (x_pos + 4, y_offset + 12), (x_pos + 8, y_offset + 16), 2)
                pygame.draw.line(self.screen, (220, 255, 230), (x_pos + 8, y_offset + 16), (x_pos + 15, y_offset + 7), 2)
            else:
                pygame.draw.circle(self.screen, (*UIColors.BG_MEDIUM, 210), icon_center, 9)
                pygame.draw.circle(self.screen, UIColors.TEXT_MUTED, icon_center, 9, 1)
                pygame.draw.line(self.screen, UIColors.TEXT_MUTED, (x_pos + 5, y_offset + 7), (x_pos + 14, y_offset + 16), 2)
                pygame.draw.line(self.screen, UIColors.TEXT_MUTED, (x_pos + 14, y_offset + 7), (x_pos + 5, y_offset + 16), 2)
            x_pos += 24
            
            # Görev açıklaması - parantez kısmını temizle
            desc = obj.get_description(lang)
            
            # Parantez varsa temizle (sadece ana metni göster)
            if '(' in desc:
                desc = desc.split('(')[0].strip()
            
            # Görev adı (sarmalı)
            desc_lines = wrap_text_lines(obj_font, desc, panel_rect.right - 22 - x_pos, max_lines=2)
            text_y = y_offset
            for line in desc_lines:
                desc_surface = obj_font.render(line, True, status_color)
                self.screen.blit(desc_surface, (x_pos, text_y))
                text_y += 21
            
            # 2. Satır - İlerleme
            progress_y = text_y + 2
            progress_text = obj.get_progress_text()
            progress_surface = progress_font.render(progress_text, True, status_color)
            self.screen.blit(progress_surface, (x_pos, progress_y))
            
            # İlerleme barı
            bar_y = progress_y + 22
            bar_width = panel_width - 54
            bar_height = 8
            
            # Arka plan
            pygame.draw.rect(
                self.screen, UIColors.SLIDER_BG,
                (panel_rect.x + 25, bar_y, bar_width, bar_height),
                border_radius=4
            )
            
            # Doluluk
            fill_width = int(bar_width * obj.get_progress_ratio())
            if fill_width > 0:
                fill_color = NEON_GREEN if obj.completed else UIColors.SLIDER_FILL
                pygame.draw.rect(
                    self.screen, fill_color,
                    (panel_rect.x + 25, bar_y, fill_width, bar_height),
                    border_radius=4
                )
            
            y_offset = bar_y + bar_height + 14
        
        # === YILDIZ KOŞULLARI ===
        # Ayırıcı çizgi
        star_section_y = y_offset + 8
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + 20, star_section_y),
            (panel_rect.right - 20, star_section_y), 1
        )
        
        star_font = UIFonts.get(19)
        star_y = star_section_y + 10
        
        # Başlık
        star_title = star_font.render(f"{t('campaign_star_conditions_title')}:", True, UIColors.TEXT_PRIMARY)
        self.screen.blit(star_title, (panel_rect.x + 20, star_y))
        star_y += 26
        
        # Her yıldız koşulunu göster
        star_conditions = self.level_config.stars
        current_score = self.board.score
        
        # Hangi yıldızların kazanıldığını hesapla
        earned_stars_num = self._calculate_stars()
        
        for star_num in [1, 2, 3]:
            condition = star_conditions.get(star_num, {})
            cond_type = condition.get('type', 'complete')
            cond_value = condition.get('value', 0)
            
            # Yıldız rengi
            star_color = STAR_COLORS.get(star_num, NEON_GOLD)
            
            # Koşul metni
            formatted_value = f"{cond_value:,}"
            if lang == 'tr':
                formatted_value = formatted_value.replace(',', '.')

            if cond_type == 'complete':
                cond_text = t('campaign_cond_complete')
            elif cond_type == 'score':
                cond_text = t('campaign_cond_score', value=formatted_value)
            elif cond_type == 'combo':
                cond_text = t('campaign_cond_combo', value=formatted_value)
            elif cond_type == 'multi_clear':
                if cond_value == 2:
                    cond_text = t('campaign_cond_multi_clear_2')
                elif cond_value == 3:
                    cond_text = t('campaign_cond_multi_clear_3')
                else:
                    cond_text = t('campaign_cond_multi_clear_n', value=formatted_value)
            elif cond_type == 'tetris':
                cond_text = t('campaign_cond_tetris', value=formatted_value)
            elif cond_type == 'combo_chain':
                cond_text = t('campaign_cond_combo_chain', value=formatted_value)
            elif cond_type == 'time_limit':
                cond_text = t('campaign_cond_time_limit', value=formatted_value)
            elif cond_type == 'extra_lines':
                cond_text = t('campaign_cond_extra_lines', value=formatted_value)
            elif cond_type == 'efficiency':
                cond_text = t('campaign_cond_efficiency', value=formatted_value)
            elif cond_type == 'time':
                cond_text = t('campaign_cond_time', value=formatted_value)
            else:
                desc = condition.get('description', {})
                cond_text = desc.get(lang, desc.get('en', str(cond_type)))
            
            # X pozisyonu
            x_pos = panel_rect.x + 20
            
            # Yıldız PNG'lerini çiz (eğer yüklüyse)
            star_icon = self.star_icon_medium or self.star_icon_small
            if star_icon:
                # star_num kadar yıldız çiz
                for i in range(star_num):
                    self.screen.blit(star_icon, (x_pos + i * 18, star_y + 1))
                x_pos += star_num * 18 + 8
            else:
                # Fallback: * sembolleri
                star_symbols = "*" * star_num
                star_surf = star_font.render(star_symbols, True, star_color)
                self.screen.blit(star_surf, (x_pos, star_y))
                x_pos += star_surf.get_width() + 8
            
            # Koşul metni (sarmalı)
            tick_slot = 24 if earned_stars_num >= star_num else 0
            max_text_w = max(60, panel_rect.right - 20 - x_pos - tick_slot)
            cond_lines = wrap_text_lines(star_font, cond_text, max_text_w, max_lines=2)
            text_y = star_y
            text_width = 0
            for line in cond_lines:
                text_surface = star_font.render(line, True, star_color)
                self.screen.blit(text_surface, (x_pos, text_y))
                text_width = max(text_width, text_surface.get_width())
                text_y += 20
            
            # Tik işareti (koşul tamamlandıysa)
            is_completed = earned_stars_num >= star_num
            if is_completed and self.tick_icon:
                tick_x = x_pos + text_width + 8
                self.screen.blit(self.tick_icon, (tick_x, star_y + 1))
            
            used_h = max(20, len(cond_lines) * 20)
            star_y += used_h + 6
        
        # === BLOK SINIRI GÖSTERİMİ (Premium) ===
        limit_font = UIFonts.small()
        limit_title_font = UIFonts.body()
        
        # Ayırıcı çizgi
        block_section_y = star_y + 8
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + 20, block_section_y),
            (panel_rect.right - 20, block_section_y), 1
        )
        
        block_y = block_section_y + 10
        
        # Blok limiti her zaman var
        block_limit = self.level_config.move_limit or 0
        remaining_blocks = max(0, block_limit - self.moves_count)
        usage_ratio = self.moves_count / block_limit if block_limit > 0 else 0.0
        
        # Renk geçişi: Yeşil -> Sarı -> Turuncu -> Kırmızı
        if remaining_blocks <= 3:
            block_color = UIColors.NEON_RED
        elif remaining_blocks <= 5:
            # Titreşim efekti - son 5 blokta
            pulse = abs(math.sin(pygame.time.get_ticks() / 200.0))
            r = int(255 * 0.7 + 255 * 0.3 * pulse)
            g = int(80 * pulse)
            block_color = (r, g, 0)
        elif remaining_blocks <= 10:
            block_color = UIColors.NEON_ORANGE if hasattr(UIColors, 'NEON_ORANGE') else (255, 165, 0)
        elif usage_ratio > 0.5:
            block_color = (255, 200, 50)  # Sarı
        else:
            block_color = NEON_GREEN
        
        # Başlık: "Kalan Blok" ikonu ile
        block_title = t('campaign_block_limit_title')
        title_surf = limit_title_font.render(block_title, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(title_surf, (panel_rect.x + 20, block_y))
        
        # Sayı gösterimi (sağ hizalı) 
        count_text = f"{remaining_blocks}/{block_limit}"
        count_surf = limit_title_font.render(count_text, True, block_color)
        count_x = panel_rect.right - 20 - count_surf.get_width()
        self.screen.blit(count_surf, (count_x, block_y))
        
        block_y += 22
        
        # Progress bar 
        bar_x = panel_rect.x + 20
        bar_width = panel_width - 40
        bar_height = 10
        
        # Bar arka planı (koyu)
        bar_bg_rect = pygame.Rect(bar_x, block_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, UIColors.SLIDER_BG, bar_bg_rect, border_radius=5)
        
        # Doluluk barı (kalan blok oranı)
        fill_ratio = remaining_blocks / block_limit if block_limit > 0 else 1.0
        fill_width = int(bar_width * fill_ratio)
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_x, block_y, fill_width, bar_height)
            pygame.draw.rect(self.screen, block_color, fill_rect, border_radius=5)
            
            # Parlak kenar efekti (üst kısım)
            if fill_width > 4:
                highlight_rect = pygame.Rect(bar_x + 2, block_y + 1, fill_width - 4, 3)
                highlight_color = tuple(min(255, c + 80) for c in block_color)
                highlight_surf = pygame.Surface(highlight_rect.size, pygame.SRCALPHA)
                highlight_surf.fill((*highlight_color, 100))
                self.screen.blit(highlight_surf, highlight_rect.topleft)
        
        # Bar kenarlığı
        pygame.draw.rect(self.screen, THEME_BORDER, bar_bg_rect, 1, border_radius=5)
        
        block_y += bar_height + 8
        
        # Zaman limiti (varsa)
        if self.level_config.time_limit:
            remaining = max(0, self.level_config.time_limit - self.elapsed_time)
            time_color = UIColors.NEON_RED if remaining < 30 else UIColors.TEXT_SECONDARY
            time_text = t('campaign_remaining_time', seconds=int(remaining))
            time_surface = limit_font.render(time_text, True, time_color)
            self.screen.blit(time_surface, (panel_rect.x + 20, block_y))
        
        return 0
    
    def draw_mode_overlay(self) -> None:
        """Mod overlay'ini çiz"""
        from retro_style import retro_style
        from ui_theme import UIColors, UIFonts
        
        # Sol paneli çiz
        self.draw_mode_info(0, 0)
        
        # === SAĞ PANEL: YILDIZLAR VE İLERLEME ===
        target_rect = getattr(self, '_hud_mode_info_area', None)
        
        if target_rect:
            rx, ry, rw, rh = target_rect
            rh = min(rh, 160)
            info_rect = pygame.Rect(rx, ry, rw, rh)
        else:
            hud_panel = getattr(self, '_hud_panel_rect', None)
            if hud_panel:
                info_rect = pygame.Rect(hud_panel.x, hud_panel.bottom + 20, hud_panel.width, 140)
            else:
                offset_x, offset_y = self.get_board_offset()
                info_rect = pygame.Rect(
                    offset_x + self.board.width * self.get_cell_size() + 20,
                    offset_y + 300, 240, 140
                )
        
        # Glass panel
        theme_border = UIColors.NEON_CYAN
        retro_style.draw_glass_panel(
            self.screen,
            info_rect,
            alpha=175,
            border_color=theme_border,
            glow=self.level_complete
        )

        # Oranlı yerleşim
        padding = 14
        inner_x = info_rect.x + padding
        inner_y = info_rect.y + padding
        inner_w = info_rect.width - padding * 2
        inner_h = info_rect.height - padding * 2

        # Toplam ilerleme (başlık kaldırıldı)
        progress_font = UIFonts.small()
        progress_text = f"{t('level')} {self.current_level_num}/100"
        progress_surface = progress_font.render(progress_text, True, UIColors.TEXT_SECONDARY)
        self.screen.blit(progress_surface, (inner_x, inner_y))

        # Geçen süre (yıldız yerleşimi için önce hesapla)
        time_font = UIFonts.small()
        mins = int(self.elapsed_time // 60)
        secs = int(self.elapsed_time % 60)
        time_text = f"{t('time')}: {mins}:{secs:02d}"
        time_surface = time_font.render(time_text, True, UIColors.TEXT_SECONDARY)
        time_y = info_rect.bottom - padding - time_surface.get_height()

        # Yıldızlar (panel oranına göre büyüt, minimum büyük boyut)
        star_area_top = inner_y + progress_surface.get_height() + 6
        star_area_bottom = time_y - 6
        star_area_h = max(0, star_area_bottom - star_area_top)
        star_gap = max(10, int(inner_w * 0.06))
        max_star_size_by_w = int((inner_w - star_gap * 2) / 3)
        desired_star_size = int(info_rect.height * 0.35)
        star_size = min(max_star_size_by_w, desired_star_size)
        star_size = max(44, star_size)
        if star_area_h > 0 and star_size > star_area_h:
            star_size = max(44, min(star_size, star_area_h))
        stars_total_w = star_size * 3 + star_gap * 2
        star_start_x = info_rect.x + (info_rect.width - stars_total_w) // 2
        star_y = star_area_top + max(0, (star_area_h - star_size) // 2)
        star_font = UIFonts.get(max(28, star_size), bold=True)
        
        for i in range(3):
            star_x = star_start_x + i * (star_size + star_gap)
            star_color = UIColors.NEON_GOLD if i < self.earned_stars else UIColors.TEXT_MUTED
            
            # Yıldız PNG kullan (varsa)
            if self.star_icon_medium:
                scaled_star = pygame.transform.smoothscale(self.star_icon_medium, (star_size, star_size))
                if i < self.earned_stars:
                    self.screen.blit(scaled_star, (star_x, star_y))
                else:
                    darkened = scaled_star.copy()
                    darkened.fill((80, 80, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    self.screen.blit(darkened, (star_x, star_y))
            else:
                # Fallback: * sembolü
                star_text = "*"
                star_surface = star_font.render(star_text, True, star_color)
                self.screen.blit(star_surface, (star_x, star_y))
        
        # Geçen süre
        self.screen.blit(time_surface, (inner_x, time_y))
        
        # === BİTİŞ EKRANLARI ===
        if self.level_complete:
            self._draw_level_complete_overlay()
        elif self.level_failed:
            self._draw_level_failed_overlay()
    
    def _draw_level_complete_overlay(self) -> None:
        """Level tamamlandı ekranı - premium animasyonlu UI"""
        from localization import get_language
        lang = get_language()
        
        level_name = self.level_config.name.get(lang, self.level_config.name.get('en', f"{t('level')} {self.current_level_num}"))

        # Hedefler listesi
        objectives_payload = []
        for obj in self.objectives:
            desc = obj.get_description(lang)
            objectives_payload.append({
                'text': desc,
                'progress': obj.get_progress_text(),
                'ratio': obj.get_progress_ratio(),
                'completed': obj.completed,
            })

        # İstatistikler
        stats_payload = [
            (t('time'), f"{self.elapsed_time:.1f}s"),
            (t('moves'), str(self.moves_count)),
            (t('campaign_max_combo'), str(self.max_combo_chain)),
            (t('tetris_label'), str(self.tetris_count)),
        ]

        # Ödüller
        reward_score = f"{int(self.board.score):,}"
        if lang == 'tr':
            reward_score = reward_score.replace(',', '.')
        rewards_payload = [
            (t('score'), reward_score),
            (t('stars'), f"{self.earned_stars}/3"),
            ("XP", str(self.level_config.xp_reward)),
            (t('campaign_reward_card_cosmetic'), t('none')),
        ]

        # Yıldız koşulları
        star_conditions_payload = []
        for star_num in sorted(self.star_conditions.keys()):
            condition = self.star_conditions[star_num]
            desc = condition.get('description', {}).get(lang, condition.get('description', {}).get('en', ''))
            star_conditions_payload.append({
                'star': star_num,
                'text': desc,
                'met': self._is_star_condition_met(condition),
            })

        # Sonraki level özeti
        next_level_payload = None
        next_level_num = self.get_next_level_num()
        if next_level_num:
            next_level = get_level(next_level_num)
        else:
            next_level = None

        if next_level:
            next_level_name = next_level.name.get(lang, next_level.name.get('en', f"{t('level')} {next_level.level}"))
            difficulty_label = self._difficulty_label_from_speed(next_level.speed, lang)

            next_objective_texts = []
            for obj_def in next_level.objectives[:2]:
                obj = create_objective(obj_def.get('type', 'clear_lines'), **obj_def)
                desc = obj.get_description(lang)
                next_objective_texts.append(desc)

            rules = []
            if next_level.no_hold:
                rules.append(t('campaign_rule_no_hold'))
            if next_level.no_preview:
                rules.append(t('campaign_rule_no_preview'))
            if next_level.cascade_mode:
                rules.append(t('campaign_rule_cascade'))
            if next_level.time_limit:
                rules.append(t('campaign_rule_time_limit', value=next_level.time_limit))
            if next_level.move_limit:
                rules.append(t('campaign_rule_block_limit', value=next_level.move_limit))
            if next_level.special_blocks:
                rules.append(t('campaign_rule_special_blocks', value=len(next_level.special_blocks)))

            if not rules:
                rules.append(t('campaign_rules_standard'))

            next_level_payload = {
                'title': f"{next_level.level}. {next_level_name}",
                'lines': [
                    f"{t('campaign_difficulty')}: {difficulty_label} ({next_level.speed}ms)",
                    f"{t('objectives')}: {len(next_level.objectives)}",
                    *next_objective_texts,
                    f"{t('campaign_rules')}: {', '.join(rules)}",
                ]
            }

            # Yeni içerik: dünya değişiyorsa
            if next_level.world > self.level_config.world:
                world_info = get_world_info(next_level.world)
                world_name = world_info['name'].get(lang, world_info['name'].get('en', f"{t('world')} {next_level.world}"))
                rewards_payload.append((t('campaign_new_world'), world_name))
        else:
            world_info = get_world_info(self.level_config.world)
            world_name = world_info['name'].get(lang, world_info['name'].get('en', f"{t('world')} {self.level_config.world}"))
            world_progress = self.current_level_num - world_info['start_level'] + 1
            total_world_levels = world_info['total_levels']
            next_level_payload = {
                'title': t('campaign_complete'),
                'lines': [
                    f"{t('world')}: {world_name}",
                    f"{t('campaign_world_progress')}: {world_progress}/{total_world_levels}",
                ]
            }

            # Kampanya ilerlemesi (toplam yıldız)
            if self.settings_manager:
                progress = self.settings_manager.get('campaign_progress', {})
                total_stars = progress.get('total_stars')
                if total_stars is not None:
                    rewards_payload.append((t('total_stars'), str(total_stars)))
        
        # Patlama ve parçacık efektlerini çiz
        campaign_ui_effects.draw_explosions(self.screen)
        campaign_ui_effects.draw_particles(self.screen)
        
        # Ana overlay
        campaign_ui_effects.draw_level_complete_overlay(
            self.screen,
            self.earned_stars,
            self.board.score,
            level_name,
            lang,
            objectives=objectives_payload,
            stats=stats_payload,
            rewards=rewards_payload,
            next_level=next_level_payload,
            star_conditions=star_conditions_payload,
            is_last_level=self.is_last_level(),
        )
    
    def _draw_level_failed_overlay(self) -> None:
        """Level başarısız ekranı - premium animasyonlu UI"""
        from localization import get_language
        lang = get_language()
        
        reason = getattr(self, 'fail_reason', '')
        
        campaign_ui_effects.draw_level_failed_overlay(
            self.screen,
            reason,
            lang
        )

    def _difficulty_label_from_speed(self, speed_ms: int, lang: str = 'tr') -> str:
        """Hız değerinden zorluk etiketi üret"""
        if speed_ms >= 800:
            return t('difficulty_easy')
        if speed_ms >= 650:
            return t('difficulty_normal')
        if speed_ms >= 500:
            return t('difficulty_hard')
        return t('difficulty_expert')
    
    # === YARDIMCI METODLAR ===
    
    def get_next_level_num(self) -> Optional[int]:
        """Sonraki level numarasını döndür"""
        next_level = self.current_level_num + 1
        if next_level <= get_total_levels():
            return next_level
        return None
    
    def is_last_level(self) -> bool:
        """Son level mi?"""
        return self.current_level_num >= get_total_levels()
    
    def _draw_right_hud_panel(self, offset_x, offset_y, board_width, board_height, skin, ui_skin, text_color, accent_color, label_color):
        """Campaign moduna özel HUD paneli - Boss/Mini Boss kuralları ile"""
        from retro_style import retro_style
        from localization import t
        
        # Sağ panel - bilgi paneli arka planı
        info_x = offset_x + board_width + 25
        header_y = offset_y + 10
        
        # Panel genişliği ve yüksekliği hesapla
        panel_width = min(220, max(180, self.window_width - (offset_x + board_width + 40)))
        panel_height = min(board_height, self.window_height - header_y - 40)
        
        panel_rect = pygame.Rect(info_x, header_y, panel_width, panel_height)
        
        # Ana panel arka planı (Glassmorphism)
        self._draw_hud_glass_panel(panel_rect)
        
        # İçerik Y pozisyonu
        curr_y = header_y + 20
        content_x = info_x + 15
        content_w = panel_width - 30
        
        # Başlık - Neon Glow
        badge_text = t('campaign_title')
        title_center = (info_x + panel_width // 2, curr_y)
        title_font = retro_style.get_font(28, bold=True)
        
        # Boss level ise özel renk
        if self.is_boss:
            title_accent = (255, 50, 50)  # Kırmızı
        elif self.is_mini_boss:
            title_accent = (255, 165, 0)  # Turuncu
        else:
            title_accent = accent_color
        
        for off in range(2, 0, -1):
            glow_surf = title_font.render(badge_text, True, (*title_accent, 50))
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(title_center[0], title_center[1] + off)))
        title_surf = title_font.render(badge_text, True, title_accent)
        title_rect = title_surf.get_rect(center=title_center)
        self.screen.blit(title_surf, title_rect)
        
        curr_y += 35
        
        # Level bilgisi
        level_text = f"{t('level')} {self.current_level_num}"
        if self.is_boss:
            level_text += f" ({t('campaign_boss')})"
        elif self.is_mini_boss:
            level_text += f" ({t('campaign_mini_boss')})"
        
        sub_font = retro_style.get_font(16)
        sub_surf = sub_font.render(level_text, True, text_color)
        sub_rect = sub_surf.get_rect(center=(title_center[0], curr_y))
        self.screen.blit(sub_surf, sub_rect)
        curr_y += 25
        
        curr_y += 10
        
        # --- NEXT PIECES ---
        next_label = retro_style.get_font(18).render(t('next'), True, label_color)
        self.screen.blit(next_label, (content_x, curr_y))
        
        curr_y += 25
        box_size = 60
        gap = 15
        
        for i in range(2):
            bx = content_x + i * (box_size + gap)
            by = curr_y
            box_rect = pygame.Rect(bx, by, box_size, box_size)
            
            # Kutu arkaplanı
            if not self._draw_custom_frame(box_rect, "box_frame.png", padding=4):
                pygame.draw.rect(self.screen, (20, 25, 40, 180), box_rect, border_radius=8)
                pygame.draw.rect(self.screen, (60, 70, 100), box_rect, 1, border_radius=8)
            
            # Boss ise ? göster
            if self._hide_next_pieces:
                # Soru işareti göster
                q_font = retro_style.get_font(36, bold=True)
                q_surf = q_font.render("?", True, (255, 100, 100))
                q_rect = q_surf.get_rect(center=box_rect.center)
                self.screen.blit(q_surf, q_rect)
            elif i < len(self.next_piece_queue):
                # Normal parça çizimi
                p = self.next_piece_queue[i]
                p_tex = getattr(p, 'texture_surface', None)
                pw = len(p.shape[0]) if p.shape else 1
                ph = len(p.shape) if p.shape else 1
                pcm = getattr(p, 'color_matrix', None)
                
                mini_cell = 12
                px_w = pw * mini_cell
                px_h = ph * mini_cell
                off_x = bx + (box_size - px_w) // 2
                off_y = by + (box_size - px_h) // 2
                
                for r_idx, row in enumerate(p.shape):
                    for c_idx, val in enumerate(row):
                        if val:
                            cx = off_x + c_idx * mini_cell
                            cy = off_y + r_idx * mini_cell
                            s_info = self._make_texture_slice(p, c_idx, r_idx, pw, ph)
                            c = p.color
                            if pcm is not None:
                                try:
                                    v = pcm[r_idx][c_idx]
                                    if v is not None:
                                        c = v
                                except Exception:
                                    pass
                            self.draw_textured_block(cx, cy, mini_cell - 1, c, p_tex, s_info)
        
        curr_y += box_size + 20
        
        # --- HOLD PIECE ---
        hold_label = retro_style.get_font(18).render(t('hold'), True, label_color)
        self.screen.blit(hold_label, (content_x, curr_y))
        
        curr_y += 25
        hold_box_rect = pygame.Rect(content_x, curr_y, box_size + 20, box_size)
        
        if not self._draw_custom_frame(hold_box_rect, "box_frame.png", padding=4):
            pygame.draw.rect(self.screen, (20, 25, 40, 180), hold_box_rect, border_radius=8)
            pygame.draw.rect(self.screen, (60, 70, 100), hold_box_rect, 1, border_radius=8)
        
        # Mini boss veya boss ise X göster
        if self._show_hold_x:
            # Büyük X çiz
            x_font = retro_style.get_font(48, bold=True)
            x_surf = x_font.render("X", True, (255, 80, 80))
            x_rect = x_surf.get_rect(center=hold_box_rect.center)
            self.screen.blit(x_surf, x_rect)
        elif self.held_piece:
            # Normal held piece çizimi
            hp = self.held_piece
            hp_tex = getattr(hp, 'texture_surface', None)
            pw = len(hp.shape[0]) if hp.shape else 1
            ph = len(hp.shape) if hp.shape else 1
            mini_cell = 14
            px_w = pw * mini_cell
            px_h = ph * mini_cell
            off_x = hold_box_rect.x + (hold_box_rect.width - px_w) // 2
            off_y = hold_box_rect.y + (hold_box_rect.height - px_h) // 2
            
            d_color = getattr(hp, '_original_color', None) or hp.color
            hpcm = getattr(hp, 'color_matrix', None)
            
            for r_idx, row in enumerate(hp.shape):
                for c_idx, val in enumerate(row):
                    if val:
                        cx = off_x + c_idx * mini_cell
                        cy = off_y + r_idx * mini_cell
                        s_info = self._make_texture_slice(hp, c_idx, r_idx, pw, ph) if hp_tex else None
                        c = d_color
                        if hpcm is not None:
                            try:
                                v = hpcm[r_idx][c_idx]
                                if v is not None:
                                    c = v
                            except Exception:
                                pass
                        self.draw_textured_block(cx, cy, mini_cell - 1, c, hp_tex, s_info)
            
            if not self.can_hold:
                # Kilit overlay
                lock_surf = pygame.Surface(hold_box_rect.size, pygame.SRCALPHA)
                lock_surf.fill((0, 0, 0, 100))
                self.screen.blit(lock_surf, hold_box_rect.topleft)
                lx, ly = hold_box_rect.center
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly-10), (lx+10, ly+10), 3)
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly+10), (lx+10, ly-10), 3)
        
        curr_y += box_size + 30
        
        # --- SCORE & STATS ---
        stats_h = 240
        stats_rect = pygame.Rect(content_x, curr_y, content_w, stats_h)
        self._hud_stats_rect = stats_rect
        self._hud_panel_rect = panel_rect
        self._hud_content_x = content_x
        self._hud_content_w = content_w
        
        # Stats background
        stats_surf = pygame.Surface(stats_rect.size, pygame.SRCALPHA)
        for i in range(stats_h):
            a = 180 + int(40 * (i / stats_h))
            pygame.draw.line(stats_surf, (20, 24, 35, a), (0, i), (content_w, i))
        self.screen.blit(stats_surf, stats_rect.topleft)
        pygame.draw.rect(self.screen, (50, 60, 80), stats_rect, 1, border_radius=12)
        
        stat_y_cur = curr_y + 15
        
        def draw_stat_row(label, value, y_pos, color_val=accent_color):
            l_surf = retro_style.get_font(16).render(label, True, (160, 170, 190))
            self.screen.blit(l_surf, (content_x + 15, y_pos))
            
            v_surf = retro_style.get_font(24, bold=True).render(str(value), True, color_val)
            v_rect = v_surf.get_rect(topright=(content_x + content_w - 15, y_pos - 4))
            self.screen.blit(v_surf, v_rect)
            
            line_y = y_pos + 32
            pygame.draw.line(self.screen, (255, 255, 255, 30), (content_x + 10, line_y), (content_x + content_w - 10, line_y))
            return 45
        
        stat_y_cur += draw_stat_row(t('score'), f'{self.board.score:,}'.replace(',', '.'), stat_y_cur, accent_color)
        stat_y_cur += draw_stat_row(t('lines'), str(self.board.lines_cleared), stat_y_cur, text_color)
        stat_y_cur += draw_stat_row(t('level'), str(self.current_level_num), stat_y_cur)
        
        if self.board.combo > 1:
            draw_stat_row(t('combo'), f'x{self.board.combo}', stat_y_cur, (255, 200, 50))
        elif self.board.tetrises > 0:
            draw_stat_row('Quadrix', str(self.board.tetrises), stat_y_cur, (100, 255, 100))
        
        # Mod info
        mode_info_y = stats_rect.bottom + 15
        self._hud_mode_info_area = (
            int(content_x),
            int(mode_info_y),
            int(content_w),
            int(max(0, self.window_height - mode_info_y - 8)),
        )
