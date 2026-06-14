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
    from ..retro_style import retro_style  # type: ignore
    from ..platform_utils import get_mouse_pos  # type: ignore
    from ..ui_scaling import get_projected_effective_scale, scale_px  # type: ignore
except Exception:
    from game import Game
    from constants import COLORS, BLACK, BOARD_WIDTH, BOARD_HEIGHT
    from pieces import SHAPE_NAMES
    from localization import t
    from retro_style import retro_style
    from platform_utils import get_mouse_pos
    from ui_scaling import get_projected_effective_scale, scale_px

from .level_data import get_level, get_total_levels, LevelConfig, get_world_info, resolve_star_condition_text
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


CAMPAIGN_HUD_REFERENCE_SIZE = (1366.0, 768.0)


class CampaignMode(Game):
    """Campaign Modu - 100 Level Quadrix Macerası"""
    _TRACKED_SPECIAL_BLOCK_TYPES = ('ice', 'locked', 'bomb', 'star', 'timer')
    
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
        sound_manager = None,
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
        
        # Level'a izinli blok havuzunu base Game init'ten önce ver.
        # Aksi halde ilk current/next queue varsayılan 7 bloktan dolabilir.
        self._allowed_pieces = list(self.level_config.allowed_pieces)
        
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
            sound_manager=sound_manager,
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

        # === FAZ 2: Yeni yıldız tipleri için sayaçlar ===
        self._hard_drop_count = 0       # Pristine yıldızı için
        self._hold_use_count = 0        # No-hold yıldızı için
        self._single_lines_count = 0    # tetris_only için (1'li temizleme)
        self._prev_held_piece = None    # Hold tracking için snapshot
        # === FAZ 2: Boss mekanik state ===
        self._boss_rain_count = 0
        self._boss_rain_timer = 0.0
        self._boss_seal_timer = 0.0
        self._boss_dark_timer = 0.0
        self._dark_preview_visible = True
        self._missing_piece_name: Optional[str] = None
        
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
        self._reset_special_block_clear_tracking()
        
        # Çöp blokları yerleştir (level 6+)
        self._place_garbage_blocks()
        
        # UI için font cache
        self._init_campaign_fonts()
        
        # İlerleme yöneticisi referansı (lazy load)
        self._progress_manager = None

        # === FAZ 2: Boss/Mini-Boss eşsiz mekanikleri __init__-time uygula ===
        boss_type = self._boss_get_type()
        if boss_type == 'fast':
            # Mini-boss tip α: %15 hızlandırma
            try:
                self.fall_speed = max(150, int(self.fall_speed * 0.85))
            except Exception:
                pass
        elif boss_type == 'missing':
            # Mini-boss tip β: pool'dan 1 parça çıkar (deterministik seed)
            # Faz 3 not:
            # missing parça çıkarma init time'da uygulanır, base Game.__init__'tan
            # SONRA. Game.__init__ next_piece_queue'yu zaten 5-7 parçayla
            # doldurmuş olabilir. Bu queue içindeki parçalar ÇIKARILMAZ — eski
            # parçalar oynanır, sonraki yeni parçalar _allowed_pieces'tan oluşur
            # (factory üzerinden). Yani level başlangıcında oyuncu missing
            # parçaya 1-2 kez denk gelebilir. Bu kabul edildi (mini-boss
            # gözlenebilir bir transition'dur, sürpriz değildir).
            #
            # Faz 4: queue purge eklendi — _purge_missing_piece_from_queue
            # init time queue'yu yeni filtreden parçalarla yeniler. Eski not
            # tarihsel kayıt; davranış artık queue'da missing parça olmamasıdır.
            try:
                allowed = list(self._allowed_pieces) if isinstance(self._allowed_pieces, list) else []
                if len(allowed) > 1:
                    rng = random.Random((self._piece_seed or 0) ^ 0xC2B2AE3D)
                    removed = rng.choice(allowed)
                    self._missing_piece_name = removed
                    self._allowed_pieces = [p for p in allowed if p != removed]
                    # Faz 4: Queue purge — mevcut next_piece_queue ve current_piece
                    # missing parçayı içerebilir; yeni filtreden parçalarla değiştir.
                    self._purge_missing_piece_from_queue()
            except Exception:
                pass
    
    def _start_music_playlist(self, force=False):
        """Kampanya dünyasına özel müzik playlist'ini başlat.

        Önce dünyaya ait playlist kontrol edilir (campaign_world1 .. campaign_world5).
        Yoksa genel campaign playlist'ine, o da yoksa Game varsayılanına düşer.
        """
        if not self.sound or not self.sound.music_enabled:
            return

        world = getattr(self.level_config, 'world', None)
        world_key = f'campaign_world{world}' if world else None
        playlist_values = []

        if world_key and self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_mode_music_playlist(world_key)
            except Exception:
                playlist_values = []

        if not playlist_values and self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_music_playlist_for_mode('campaign')
            except Exception:
                playlist_values = []

        if playlist_values:
            import random as _rng
            track_keys = []
            for value in playlist_values:
                track_key = self.sound.ensure_track_available(value)
                if track_key:
                    track_keys.append(track_key)
            if track_keys:
                do_shuffle = bool(self.settings_manager.get('music_shuffle', False)) if self.settings_manager else False
                start_index = 0 if do_shuffle else _rng.randrange(len(track_keys))
                self.sound.set_music_playlist(track_keys, loop=True, start_index=start_index, autoplay=True, force=force, shuffle=do_shuffle)
                self.current_music_track = track_keys[start_index]
                return

        # Dünyaya özel veya kampanya playlist'i yoksa Game varsayılanını kullan
        super()._start_music_playlist(force=force)

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
        """Level konfigürasyonuna göre özel blokları başlat.

        Faz 1 (deterministik yerleşim): Layout, level seed'inden türeyen
        izole bir random.Random instance kullanır. Global random durumu
        kirletilmez. Aynı seed → aynı (x,y) listesi → puzzle hissi.
        quick_restart aynı seed kullandığı için layout aynı kalır;
        restart yeni seed üretir, layout değişir.
        """
        if not self.level_config or not self.level_config.special_blocks:
            return

        # Level seed'inden türeyen izole RNG. Layout seed'i level numarasıyla
        # karıştırılarak sabitlenir; piece_seed her quick_restart'ta sabit.
        layout_seed = (getattr(self, '_piece_seed', 0) or 0) ^ (self.current_level_num * 0x9E3779B1)
        layout_rng = random.Random(layout_seed)

        board_width = self.board.width if self.board else 10
        board_height = self.board.height if self.board else 20

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
            # Board'un alt yarısına deterministik olarak yerleştir
            available_positions = []
            start_row = max(board_height // 2, board_height - 8)

            for y in range(start_row, board_height - 1):
                for x in range(board_width):
                    available_positions.append((x, y))

            layout_rng.shuffle(available_positions)

            for i in range(min(count, len(available_positions))):
                x, y = available_positions[i]
                self.special_block_manager.add_special_block(x, y, block_type, **block_config)
    
    def _init_campaign_fonts(self) -> None:
        """Campaign için font cache ve ikonları oluştur"""
        self.campaign_font_large = retro_style.get_font(48, bold=False)
        self.campaign_font_medium = retro_style.get_font(36, bold=False)
        self.campaign_font_small = retro_style.get_font(28, bold=False)
        self.campaign_font_tiny = retro_style.get_font(22, bold=False)
        
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
        self._campaign_icon_scale_cache = {}
        
        # Yıldız ikonunu yükle
        star_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'ui', 'yildiz.png'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'yildiz.png'),
            'assets/ui/yildiz.png',
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

    def _get_scaled_campaign_icon(self, cache_key: str, target_size: int, base_surface: Optional[pygame.Surface]) -> Optional[pygame.Surface]:
        if base_surface is None or target_size <= 0:
            return None

        cache = getattr(self, '_campaign_icon_scale_cache', None)
        if cache is None:
            cache = {}
            self._campaign_icon_scale_cache = cache

        key = (cache_key, int(target_size))
        cached = cache.get(key)
        if cached is not None:
            return cached

        if base_surface.get_width() == target_size and base_surface.get_height() == target_size:
            scaled = base_surface
        else:
            scaled = pygame.transform.smoothscale(base_surface, (target_size, target_size))
        cache[key] = scaled
        return scaled

    def _get_campaign_star_icon(self, target_size: int) -> Optional[pygame.Surface]:
        base_surface = self.star_icon_large or self.star_icon_medium or self.star_icon_small
        return self._get_scaled_campaign_icon('star', target_size, base_surface)

    def _get_campaign_tick_icon(self, target_size: int) -> Optional[pygame.Surface]:
        return self._get_scaled_campaign_icon('tick', target_size, self.tick_icon)
    
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

    def wants_mouse_visible(self) -> bool:
        """Campaign modunda başarısız/tamamlandı ekranlarında mouse görünür olsun"""
        if getattr(self, 'level_failed', False) or getattr(self, 'level_complete', False):
            return True
        return super().wants_mouse_visible()
    
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

        # Faz 2: Boss mekanik ticker (super.update'tan ÖNCE; rain push board state'i değiştirir)
        try:
            self._boss_phase_update(dt_seconds)
        except Exception as exc:
            print(f"[CAMPAIGN] _boss_phase_update error: {exc}")

        # Faz 2: Hold tracking — held_piece geçişi
        try:
            current_held = getattr(self, 'held_piece', None)
            if current_held is not self._prev_held_piece:
                # Geçiş oldu: ya boştan dolu, ya swap
                if current_held is not None:
                    self._hold_use_count += 1
                self._prev_held_piece = current_held
        except Exception:
            pass
        
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

        self._emit_special_block_clear_deltas()
        
        # Zaman limiti kontrolü
        if self.level_config and self.level_config.time_limit:
            if self.elapsed_time >= self.level_config.time_limit:
                self._handle_level_failed(t('campaign_fail_time'))
                return
        
        # Normal oyun güncellemesi
        super().update(dt)

        # Oyun alanı doldu (taşlar üste ulaştı) → campaign başarısız ekranına yönlendir
        # game_over flag'ini sıfırla ki parent'ın standart "OYUN BİTTİ" overlay'i gösterilmesin
        if getattr(self, 'game_over', False) and not self.level_failed:
            self.game_over = False
            self._game_over_active = False
            self._game_over_pending = False
            self._handle_level_failed(t('campaign_fail_board'), skip_sound=True)
            return
        
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

                # Toplanan puan
                if special_result.get('points_earned', 0) > 0:
                    self.board.score += special_result['points_earned']

                # Özel blokları aşağı kaydır
                self.special_block_manager.shift_blocks_down(actually_cleared)
                self._emit_special_block_clear_deltas()
            
            self._emit_event('lines_cleared', {
                'lines': new_lines,
                'total_lines': self.board.lines_cleared
            })
            
            # === YILDIZ İSTATİSTİKLERİ ===
            # Single (1'li), Double (2'li), Triple (3'lü), Quadrix (4'lü) sayımı
            if new_lines == 1:
                self._single_lines_count += 1
            elif new_lines == 2:
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

    def _reset_special_block_clear_tracking(self) -> None:
        self._special_block_clear_counts = {
            block_type: 0 for block_type in self._TRACKED_SPECIAL_BLOCK_TYPES
        }

    def _emit_special_block_clear_deltas(self) -> None:
        manager = getattr(self, 'special_block_manager', None)
        if manager is None:
            return

        counts = getattr(self, '_special_block_clear_counts', None)
        if not isinstance(counts, dict):
            self._reset_special_block_clear_tracking()
            counts = self._special_block_clear_counts

        for block_type in self._TRACKED_SPECIAL_BLOCK_TYPES:
            try:
                current_count = int(manager.get_cleared_count(block_type) or 0)
            except Exception:
                current_count = 0

            previous_count = int(counts.get(block_type, 0) or 0)
            if current_count > previous_count:
                self._emit_event('special_block_cleared', {
                    'block_type': block_type,
                    'count': current_count - previous_count,
                })
            counts[block_type] = current_count
    
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
    
    def _handle_level_failed(self, reason: str = "", *, skip_sound: bool = False) -> None:
        """Level başarısız olduğunda"""
        if self.level_failed:
            return
        
        self.level_failed = True
        self.fail_reason = reason
        
        # UI animasyonunu başlat
        campaign_ui_effects.start_level_failed(reason)
        
        # Campaign fail ekranında müzik her zaman kesilmeli.
        # sound_enabled ses efektleri toggle'ı olduğu için burada gate olarak kullanılamaz.
        # Aksi halde SFX kapalıyken blok/süre limiti fail akışı sessiz kalıp müzik çalmaya devam eder.
        if not skip_sound and self.sound:
            self.sound.play_game_over_sequence()

        # Faz 1: Fail attempts sayacını artır (success attempts'tan ayrı alan)
        try:
            self._record_fail_attempt()
        except Exception as exc:
            print(f"[CAMPAIGN] _record_fail_attempt failed: {exc}")

    # === FAZ 2: Hard drop tracker (pristine yıldızı için) ===
    def trigger_hard_drop_screen_shake(self):
        """Game.trigger_hard_drop_screen_shake override.

        Hard drop sayacı bu hook'tan ilerletilir. Bilinen kısıtlama:
        Game.handle_input içinde `if self.effects_enabled and drop_distance > 0:`
        ile gated; effects_enabled=False ise bu çağrı atlanır ve sayaç artmaz
        (pristine yıldızı için sahte pozitif riski). Tasarım kararı: §Karar B,
        sadece Katman 1 (override) kullanıldı.
        """
        self._hard_drop_count += 1
        super().trigger_hard_drop_screen_shake()

    # === FAZ 4: Mini-boss missing queue purge ===
    def _purge_missing_piece_from_queue(self) -> None:
        """next_piece_queue ve current_piece'tan missing parçayı temizler.

        Mini-boss 'missing' init time uygulanır; Game.__init__ next_piece_queue'yu
        eski filtre ile (7 parça) doldurmuş olabilir. Bu helper missing parçayı
        yeni filtreden parça ile değiştirerek queue başında oyuncunun missing
        parçayı görmesini engeller.

        Edge case: spawn_new_piece factory _get_base_piece_factories üzerinden
        çalışır; CampaignMode override'ı _allowed_pieces'a göre filtre uygular.
        Missing parça çıkarıldığı için spawn_new_piece o parçayı döndürmez;
        ama defansif loop limiti (5 deneme) sonsuz döngüyü engeller.
        """
        if not self._missing_piece_name:
            return
        if not hasattr(self, 'next_piece_queue') or not self.next_piece_queue:
            return

        new_queue = []
        for piece in self.next_piece_queue:
            piece_name = getattr(piece, 'name', None)
            if piece_name == self._missing_piece_name:
                replacement = None
                for _ in range(5):  # Defansif loop limiti
                    candidate = self.spawn_new_piece()
                    if getattr(candidate, 'name', None) != self._missing_piece_name:
                        replacement = candidate
                        break
                if replacement is not None:
                    new_queue.append(replacement)
                else:
                    new_queue.append(piece)
                    print(f"[CAMPAIGN] missing piece purge: replacement not found")
            else:
                new_queue.append(piece)
        self.next_piece_queue = new_queue

        # current_piece de missing olabilir — yeni filtreden parça ile değiştir
        if hasattr(self, 'current_piece') and self.current_piece:
            if getattr(self.current_piece, 'name', None) == self._missing_piece_name:
                for _ in range(5):
                    candidate = self.spawn_new_piece()
                    if getattr(candidate, 'name', None) != self._missing_piece_name:
                        self.current_piece = candidate
                        if hasattr(self, '_position_piece_at_spawn'):
                            try:
                                self._position_piece_at_spawn(self.current_piece)
                            except Exception:
                                pass
                        break

    # === FAZ 2: Boss/Mini-Boss eşsiz mekanikler ===

    def _boss_get_type(self) -> Optional[str]:
        """Boss/mini-boss tipini döndür ya da None.

        Faz 3: level_data.get_boss_type_for_level'a delege.
        Single source of truth — divergence imkansız.
        """
        from .level_data import get_boss_type_for_level
        return get_boss_type_for_level(self.current_level_num)

    def _boss_phase_update(self, dt_seconds: float) -> None:
        """Boss-specific update logic. update(dt) içinde her tick çağrılır."""
        boss_type = self._boss_get_type()
        if boss_type is None:
            return

        if boss_type == 'rain':
            self._boss_rain_update(dt_seconds)
        elif boss_type == 'seal':
            self._boss_seal_update(dt_seconds)
        elif boss_type == 'dark':
            self._boss_dark_update(dt_seconds)
        elif boss_type == 'final':
            # Level 100: 3 fazlı runtime, ana objective progress'ine göre
            # ratio < 0 veya > 1 ise 0 olarak ele al (defansif clamp).
            ratio = 0.0
            try:
                if self.objectives:
                    ratio = max(0.0, min(1.0, float(self.objectives[0].get_progress_ratio())))
            except Exception:
                ratio = 0.0
            self._boss_rain_update(dt_seconds)
            if ratio >= 0.33:
                self._boss_seal_update(dt_seconds)
            if ratio >= 0.66:
                self._boss_dark_update(dt_seconds)
        # 'fast' ve 'missing' mini-boss tipleri __init__ time uygulanır;
        # update sırasında ek iş yok.

    def _boss_rain_update(self, dt_seconds: float) -> None:
        """Tip A — Yağmur. Her 30 saniyede 1 satır çöp push."""
        self._boss_rain_timer += dt_seconds
        if self._boss_rain_timer >= 30.0:
            self._boss_rain_timer = 0.0
            self._boss_push_garbage_row()

    def _boss_seal_update(self, dt_seconds: float) -> None:
        """Tip B — Mühürleme. Her 45 saniyede 1 dolu hücre LOCKED'a dönüşür."""
        self._boss_seal_timer += dt_seconds
        if self._boss_seal_timer >= 45.0:
            self._boss_seal_timer = 0.0
            self._boss_seal_apply_lock()

    def _boss_dark_update(self, dt_seconds: float) -> None:
        """Tip C — Karanlık. Önizleme 4s gizli + 2s açık döngüsü."""
        self._boss_dark_timer += dt_seconds
        # 6s peryot: 4s gizli, 2s açık
        cycle = self._boss_dark_timer % 6.0
        # 0..4 → gizli, 4..6 → açık
        new_visible = cycle >= 4.0
        if new_visible != self._dark_preview_visible:
            self._dark_preview_visible = new_visible
            self._hide_next_pieces = not new_visible

    def _boss_push_garbage_row(self) -> None:
        """Alttan çöp satırı push (Tip A).

        online_pvp_game._apply_pending_garbage pattern'i sıfırdan kopyalandı
        (board.py'a dokunulmadı, online_pvp_game'den import yapılmadı).
        Overflow guard: üst satır doluysa push'u atla.
        """
        if not self.board:
            return

        # Overflow guard: üst satırda dolu hücre varsa push'u atla,
        # oyuncu mevcut parçayı yerleştirsin.
        try:
            top_occ = self.board.occupancy[0]
            if any(top_occ):
                return
        except (IndexError, AttributeError):
            return

        rng = random.Random((self._piece_seed or 0) + self._boss_rain_count)
        gap_col = rng.randint(0, self.board.width - 1)
        garbage_color = (90, 90, 100)

        # board.grid manipülasyonu — board.py'a yeni metod eklenmedi
        try:
            self.board.grid.pop(0)
            self.board.occupancy.pop(0)
            if hasattr(self.board, 'texture_grid'):
                self.board.texture_grid.pop(0)
            if hasattr(self.board, 'owners'):
                self.board.owners.pop(0)
            if hasattr(self.board, 'gold'):
                self.board.gold.pop(0)

            new_row = [garbage_color if x != gap_col else None for x in range(self.board.width)]
            new_occ = [x != gap_col for x in range(self.board.width)]

            self.board.grid.append(new_row)
            self.board.occupancy.append(new_occ)
            if hasattr(self.board, 'texture_grid'):
                self.board.texture_grid.append([None] * self.board.width)
            if hasattr(self.board, 'owners'):
                self.board.owners.append([None] * self.board.width)
            if hasattr(self.board, 'gold'):
                self.board.gold.append([False] * self.board.width)

            self._boss_rain_count += 1

            # Aktif parça yukarı kayar; geçersiz pozisyona düşerse fail
            if hasattr(self, 'current_piece') and self.current_piece:
                try:
                    self.current_piece.y -= 1
                    if hasattr(self.board, 'is_valid_position'):
                        if not self.board.is_valid_position(self.current_piece):
                            self._handle_level_failed(t('campaign_fail_boss_overflow'), skip_sound=False)
                except Exception:
                    pass
        except Exception as exc:
            print(f"[CAMPAIGN] _boss_push_garbage_row error: {exc}")

    def _boss_seal_apply_lock(self) -> None:
        """Rastgele 1 dolu hücreye LOCKED special block uygula (Tip B).

        Boş board → bu tick atla; timer reset edildi (45s sonra tekrar dene).

        Faz 3 dokümantasyon notu — Seal RNG belirsizliği:
        Seed timer-tabanlı: piece_seed + int(timer*100) + len(candidates).
        Bu deterministik DEĞİL — aynı level'da iki run aynı kalıbı üretmeyebilir.
        Tasarım kararı: Seal her tetiklemede farklı hücre seçsin; board state'i
        evrildiğine göre kararlar farklılaşmalı (deterministik puzzle istenmiyor).
        quick_restart farklı seal kalıbı görür; bu kabul edilebilir.
        """
        if not self.board:
            return

        # Tüm dolu hücreleri topla
        candidates = []
        try:
            for y in range(self.board.height):
                for x in range(self.board.width):
                    if self.board.occupancy[y][x]:
                        # Zaten special block varsa atla
                        if (x, y) in self.special_block_manager.special_blocks:
                            continue
                        candidates.append((x, y))
        except (IndexError, AttributeError):
            return

        if not candidates:
            return  # Boş board, atla

        rng = random.Random((self._piece_seed or 0) + int(self._boss_seal_timer * 100) + len(candidates))
        x, y = rng.choice(candidates)
        try:
            self.special_block_manager.add_special_block(x, y, SpecialBlockType.LOCKED)
        except Exception as exc:
            print(f"[CAMPAIGN] _boss_seal_apply_lock error: {exc}")

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

        if condition_type == 'move_limit':
            return bool(self.level_complete and self.moves_count <= target_value)

        if condition_type == 'efficiency':
            main_progress = self.objectives[0].progress if self.objectives else 0
            return main_progress >= target_value

        if condition_type == 'extra_lines':
            total_lines = self.board.lines_cleared if self.board else 0
            main_target = 0
            if self.objectives and hasattr(self.objectives[0], 'target'):
                main_target = self.objectives[0].target
            return total_lines >= main_target + target_value

        # === FAZ 2: Yeni yıldız tipleri ===

        if condition_type == 'no_hold_run':
            # Level boyunca hold tuşunu hiç kullanma
            return bool(self.level_complete and self._hold_use_count == 0)

        if condition_type == 'pristine':
            # Hard drop kullanmadan tamamla.
            # Bilinen kısıtlama: effects_enabled=False senaryosunda
            # trigger_hard_drop_screen_shake() çağrılmaz; sahte pozitif riski
            # kabul edildi (Faz 2 raporu — known limitation).
            return bool(self.level_complete and self._hard_drop_count == 0)

        if condition_type == 'garbage_speed':
            # clear_garbage objective tamamlandı + X saniye içinde
            try:
                from .objectives import ClearGarbageObjective as _CGO
            except Exception:
                _CGO = None
            has_clear_garbage_done = False
            if _CGO is not None:
                has_clear_garbage_done = any(
                    isinstance(o, _CGO) and o.completed for o in self.objectives
                )
            else:
                has_clear_garbage_done = any(
                    getattr(o, 'completed', False) and o.__class__.__name__ == 'ClearGarbageObjective'
                    for o in self.objectives
                )
            return bool(has_clear_garbage_done and self.elapsed_time <= target_value)

        if condition_type == 'tetris_only':
            # Tüm temizlenen satırlar Quadrix mı?
            # single/double/triple count sıfır olmalı; en az 1 Quadrix var.
            # Bomba ile temizlenen 1-3 satırlık clearler bu sayaçları artırır →
            # oyuncuya bilinçli risk (yıldız metni "Sadece Quadrix temizle").
            return bool(
                self.level_complete
                and self.tetris_count >= 1
                and self._single_lines_count == 0
                and self.double_count == 0
                and self.triple_count == 0
            )

        if condition_type == 'min_score':
            return bool(self.level_complete and self.board.score >= target_value)

        return False

    def _calculate_stars(self) -> int:
        """Yıldız sayısını hesapla.

        Karma model (Faz 1, kararlı 2026-05):
        - 1. yıldız her zaman zorunlu: condition_1 (genelde 'complete')
          sağlanmadıysa toplam = 0. Level complete olmadan yıldız yok.
        - 2 ve 3 birbirinden bağımsız: 1. sağlandıktan sonra 2 ve 3
          ayrı ayrı değerlendirilir. Oyuncu 1+3 alabilir (ortayı atlar).
        """
        condition_results = {}

        for star_num, condition in self.star_conditions.items():
            condition_results[int(star_num)] = self._is_star_condition_met(condition)

        if not condition_results.get(1, False):
            return 0

        stars = 1
        if condition_results.get(2, False):
            stars += 1
        if condition_results.get(3, False):
            stars += 1
        return stars
    
    def _save_progress(self) -> None:
        """İlerlemeyi kaydet"""
        if not self.settings_manager:
            return
        
        # Mevcut ilerlemeyi al
        progress = self.user_manager.get_campaign_progress()
        if not isinstance(progress, dict):
            progress = {}
        
        completed = progress.get('completed_levels', {})
        if not isinstance(completed, dict):
            completed = {}
        
        # Bu level'ın verilerini güncelle
        level_key = str(self.current_level_num)
        existing = completed.get(level_key, {})

        # === Faz 1: First-clear / improvement flag tespiti (save'den ÖNCE) ===
        was_completed_before = bool(existing.get('completed', False))
        prev_stars = int(existing.get('stars', 0) or 0)
        prev_score = int(existing.get('best_score', 0) or 0)
        is_first_clear = not was_completed_before
        is_star_improvement = (self.earned_stars > prev_stars)
        is_score_improvement = (self.board.score > prev_score)
        # Dış katmanlardan erişilebilir olsun (overlay payload için)
        self._last_run_flags = {
            'first_clear': is_first_clear,
            'star_improvement': is_star_improvement,
            'score_improvement': is_score_improvement,
            'previous_stars': prev_stars,
            'previous_score': prev_score,
        }

        # Sadece daha iyi sonuçları kaydet
        best_stars = max(self.earned_stars, prev_stars)
        best_score = max(self.board.score, prev_score)

        # === Faz 3: Bireysel star_flags (1+3 senaryosu için) ===
        # Karma yıldız modelinde her slot bağımsız değerlendirilir.
        # En iyi flag'ler: bu run'da kazandığı + önceki run'larda kazandığı (OR).
        condition_results: Dict[int, bool] = {}
        for star_num, condition in self.star_conditions.items():
            try:
                condition_results[int(star_num)] = self._is_star_condition_met(condition)
            except Exception:
                condition_results[int(star_num)] = False

        prev_star_flags = existing.get('star_flags', {})
        if not isinstance(prev_star_flags, dict):
            prev_star_flags = {}
        # Karma model: 1. yıldız zorunlu. 1 sağlanmadıysa hiçbir flag set edilmez.
        first_met_now = condition_results.get(1, False)
        new_star_flags: Dict[str, bool] = {}
        for num in (1, 2, 3):
            prev_flag = bool(prev_star_flags.get(str(num), False))
            now_flag = bool(condition_results.get(num, False)) if first_met_now else False
            new_star_flags[str(num)] = prev_flag or now_flag

        completed[level_key] = {
            'stars': best_stars,
            'best_score': best_score,
            'completed': True,
            # attempts: SUCCESS sayısı (Faz 1 öncesi davranışla geriye uyumlu).
            # Fail denemeleri ayrı 'fail_attempts' alanında tutulur.
            'attempts': existing.get('attempts', 0) + 1,
            'fail_attempts': int(existing.get('fail_attempts', 0) or 0),
            # Faz 3: Bireysel yıldız flag'leri (opsiyonel, geriye uyumlu).
            # Eski save'de bu alan yoksa preview cumulatif fallback yapar.
            'star_flags': new_star_flags,
        }
        
        # En yüksek level'ı güncelle
        highest = max(self.current_level_num, progress.get('highest_level', 0))
        
        # Toplam yıldızları hesapla
        total_stars = sum(l.get('stars', 0) for l in completed.values())
        
        progress['completed_levels'] = completed
        progress['highest_level'] = highest
        progress['total_stars'] = total_stars
        progress['current_world'] = (highest - 1) // 20 + 1
        
        self.user_manager.save_campaign_progress(progress)
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

    def _record_fail_attempt(self) -> None:
        """Fail edilen denemeleri sayar ve kaydeder.

        attempts (success) ile ayrı 'fail_attempts' alanı tutulur. Bu, oyuncunun
        bir leveli kaç kez denediğini görmesi için altyapı sağlar.
        Save layout migration testini kırmaz; eski kayıtlarda alan yoksa
        default 0 olarak okunur.
        """
        if not self.settings_manager or not self.user_manager:
            return

        try:
            progress = self.user_manager.get_campaign_progress()
        except Exception:
            progress = None
        if not isinstance(progress, dict):
            progress = {}

        completed = progress.get('completed_levels', {})
        if not isinstance(completed, dict):
            completed = {}

        level_key = str(self.current_level_num)
        existing = completed.get(level_key, {})
        if not isinstance(existing, dict):
            existing = {}

        new_entry = {
            'stars': int(existing.get('stars', 0) or 0),
            'best_score': int(existing.get('best_score', 0) or 0),
            'completed': bool(existing.get('completed', False)),
            'attempts': int(existing.get('attempts', 0) or 0),
            'fail_attempts': int(existing.get('fail_attempts', 0) or 0) + 1,
        }
        completed[level_key] = new_entry
        progress['completed_levels'] = completed

        try:
            self.user_manager.save_campaign_progress(progress)
        except Exception as exc:
            print(f"[CAMPAIGN] _record_fail_attempt save error: {exc}")
    
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
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = get_mouse_pos()
                    # Peek (göz) butonu — tıklanınca paneli gizle/göster
                    peek_rect = getattr(self, '_game_over_peek_rect', None)
                    if peek_rect and peek_rect.collidepoint(pos):
                        self._game_over_peek_active = not getattr(self, '_game_over_peek_active', False)
                        continue
                    # Peek modundayken diğer butonlara tıklama yok
                    if getattr(self, '_game_over_peek_active', False):
                        continue
                    if self.level_failed:
                        # Önce yeni game_over_overlay butonlarını kontrol et (kırmızı tema)
                        targets = getattr(self, '_game_over_click_targets', {})
                        if isinstance(targets, dict):
                            if targets.get('restart') and targets['restart'].collidepoint(pos):
                                self.restart()
                                return True
                            if targets.get('menu') and targets['menu'].collidepoint(pos):
                                return 'main_menu'
                        # Fallback: eski campaign_ui_effects butonları
                        btns = getattr(campaign_ui_effects, '_failed_buttons', {})
                        if btns.get('retry') and btns['retry'].collidepoint(pos):
                            self.restart()
                            return True
                        if btns.get('menu') and btns['menu'].collidepoint(pos):
                            return 'main_menu'
                    if self.level_complete:
                        btns = getattr(campaign_ui_effects, '_complete_buttons', {})
                        if btns.get('retry') and btns['retry'].collidepoint(pos):
                            self.restart()
                            return True
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

        # Başarısız overlay state sıfırla (yeniden başlayışta animasyon yeniden başlasın)
        self._fail_game_over_active = False

        # Yıldız istatistiklerini sıfırla
        self.total_combos = 0
        self.max_combo_chain = 0
        self.current_combo_chain = 0
        self.tetris_count = 0
        self.double_count = 0
        self.triple_count = 0

        # Faz 2: Yeni yıldız tipi sayaçları
        self._hard_drop_count = 0
        self._hold_use_count = 0
        self._single_lines_count = 0
        self._prev_held_piece = None
        # Faz 2: Boss mekanik state sıfırla
        self._boss_rain_count = 0
        self._boss_rain_timer = 0.0
        self._boss_seal_timer = 0.0
        self._boss_dark_timer = 0.0
        self._dark_preview_visible = True

        # Görevleri sıfırla
        for obj in self.objectives:
            obj.reset()

        # Özel blok yöneticisini sıfırla ve yeniden oluştur
        self.special_block_manager = SpecialBlockManager()
        self._init_special_blocks()
        self._reset_special_block_clear_tracking()

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

    def _get_campaign_hud_scale(self, surface_or_size=None) -> float:
        """Campaign gameplay panelleri icin preset'ten bagimsiz ekran bazli scale.

        Campaign icindeki HUD/panel geometriği base gameplay layout gibi davranmali;
        global compact preset bu panel ailesini ekstra kucultmemeli.
        """
        target = surface_or_size or getattr(self, 'screen', None)
        if target is None:
            target = (
                getattr(self, 'window_width', int(CAMPAIGN_HUD_REFERENCE_SIZE[0])),
                getattr(self, 'window_height', int(CAMPAIGN_HUD_REFERENCE_SIZE[1])),
            )
        return get_projected_effective_scale(
            target,
            min_scale=0.74,
            max_scale=1.12,
            reference_size=CAMPAIGN_HUD_REFERENCE_SIZE,
            apply_preset=False,
        )

    def _scale_campaign_hud_px(self, value: int | float, ui_scale: float, minimum: int = 1) -> int:
        return scale_px(value, ui_scale, minimum=minimum)

    def _get_left_gameplay_reserve_width(self) -> int:
        ui_scale = self._get_campaign_hud_scale(getattr(self, 'screen', None) or self._active_ui_size())
        return self._scale_campaign_hud_px(340, ui_scale) + self._scale_campaign_hud_px(20, ui_scale, minimum=0)

    def _get_campaign_left_panel_rect(self, board_offset_x: int, board_offset_y: int) -> pygame.Rect:
        screen_w, screen_h = self.screen.get_size()
        ui_scale = self._get_campaign_hud_scale((screen_w, screen_h))
        s = lambda value, minimum=1: self._scale_campaign_hud_px(value, ui_scale, minimum=minimum)

        safe_left_margin = s(10)
        board_gap = s(20, minimum=0)
        actual_left_space = max(0, int(board_offset_x) - board_gap - safe_left_margin)
        panel_width = min(s(340), max(s(220), actual_left_space))

        max_panel_h = max(s(260), int(screen_h) - int(board_offset_y) - s(14, minimum=0))
        panel_height = min(max_panel_h, max(s(500), min(s(620), max_panel_h)))

        panel_x = max(safe_left_margin, int(board_offset_x) - panel_width - board_gap)
        panel_y = int(board_offset_y)
        return pygame.Rect(panel_x, panel_y, panel_width, panel_height)

    def _get_campaign_right_hud_panel_rect(
        self,
        offset_x: int,
        offset_y: int,
        board_width: int,
        board_height: int,
    ) -> pygame.Rect:
        screen_w, screen_h = self.screen.get_size()
        ui_scale = self._get_campaign_hud_scale((screen_w, screen_h))
        s = lambda value, minimum=1: self._scale_campaign_hud_px(value, ui_scale, minimum=minimum)

        header_y = int(offset_y) + s(10, minimum=0)
        info_x = int(offset_x) + int(board_width) + s(25, minimum=0)

        available_right = int(screen_w) - (int(offset_x) + int(board_width) + s(40, minimum=0))
        panel_width = min(s(220), max(s(140), available_right))
        panel_width = max(s(120), min(panel_width, max(s(120), int(screen_w) - s(24, minimum=0))))

        info_x = min(info_x, int(screen_w) - panel_width - s(12, minimum=0))

        available_panel_h = max(s(180), int(screen_h) - header_y - s(40, minimum=0))
        panel_height = min(int(board_height), available_panel_h)
        panel_height = min(panel_height, max(s(180), int(screen_h) - header_y - s(12, minimum=0)))
        return pygame.Rect(info_x, header_y, panel_width, panel_height)

    @staticmethod
    def _get_block_limit_hud_state(move_limit: Optional[int], moves_count: int) -> tuple[str, tuple[int, int, int], float]:
        """Return display text, color and fill ratio for the campaign block limit bar."""
        from ui_theme import UIColors

        if not move_limit or move_limit <= 0:
            return "∞", UIColors.NEON_GREEN, 1.0

        remaining_blocks = max(0, move_limit - moves_count)
        usage_ratio = moves_count / move_limit

        if remaining_blocks <= 3:
            block_color = UIColors.NEON_RED
        elif remaining_blocks <= 5:
            pulse = abs(math.sin(pygame.time.get_ticks() / 200.0))
            r = int(255 * 0.7 + 255 * 0.3 * pulse)
            g = int(80 * pulse)
            block_color = (r, g, 0)
        elif remaining_blocks <= 10:
            block_color = UIColors.NEON_ORANGE if hasattr(UIColors, 'NEON_ORANGE') else (255, 165, 0)
        elif usage_ratio > 0.5:
            block_color = (255, 200, 50)
        else:
            block_color = UIColors.NEON_GREEN

        return f"{remaining_blocks}/{move_limit}", block_color, remaining_blocks / move_limit
    
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

        ui_scale = self._get_campaign_hud_scale(self.screen)
        s = lambda value, minimum=1: self._scale_campaign_hud_px(value, ui_scale, minimum=minimum)
        panel_rect = self._get_campaign_left_panel_rect(board_offset_x, board_offset_y)
        self._campaign_left_panel_rect = panel_rect
        panel_width = panel_rect.width
        panel_height = panel_rect.height
        
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
        header_bg = pygame.Rect(panel_rect.x + s(10), panel_rect.y + s(10), panel_width - s(20), s(60, minimum=40))
        header_surf = pygame.Surface(header_bg.size, pygame.SRCALPHA)
        header_surf.fill((*UIColors.BG_MEDIUM, 190))
        self.screen.blit(header_surf, header_bg.topleft)
        pygame.draw.rect(self.screen, THEME_BORDER, header_bg, 1, border_radius=s(10, minimum=6))

        # İçerik arka planı
        content_bg = pygame.Rect(panel_rect.x + s(10), panel_rect.y + s(74, minimum=50), panel_width - s(20), panel_height - s(86, minimum=60))
        content_surf = pygame.Surface(content_bg.size, pygame.SRCALPHA)
        content_surf.fill((*UIColors.BG_DARK, 160))
        self.screen.blit(content_surf, content_bg.topleft)
        pygame.draw.rect(self.screen, UIColors.GLASS_BORDER[:3], content_bg, 1, border_radius=s(10, minimum=6))
        
        # === LEVEL BİLGİSİ ===
        header_font = UIFonts.get(s(15, minimum=10))
        title_font = UIFonts.get(s(16, minimum=11), bold=True)
        lang = get_language()
        level_name = self.level_config.name.get(lang, self.level_config.name.get('en', f"{t('level')} {self.current_level_num}"))
        world_info = get_world_info(self.level_config.world)
        world_name = world_info['name'].get(lang, world_info['name'].get('en', t('world')))
        
        # Dünya ve Level
        world_text = header_font.render(world_name, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(world_text, (panel_rect.x + s(18), panel_rect.y + s(16)))
        
        level_label = f"{t('level')} {self.current_level_num}: {level_name}"
        level_lines = wrap_text_lines(title_font, level_label, panel_width - s(42), max_lines=2)
        base_y = panel_rect.y + s(42)
        for idx, line in enumerate(level_lines):
            level_text = title_font.render(line, True, NEON_GOLD)
            self.screen.blit(level_text, (panel_rect.x + s(18), base_y + idx * s(22, minimum=14)))
        
        # Ayırıcı çizgi
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + s(15), panel_rect.y + s(78, minimum=54)),
            (panel_rect.right - s(15), panel_rect.y + s(78, minimum=54)), 1
        )
        
        # === GÖREVLER ===
        obj_font = UIFonts.get(s(14, minimum=10))
        progress_font = UIFonts.get(s(13, minimum=10))
        y_offset = panel_rect.y + s(102, minimum=72)
        
        for obj in self.objectives:
            # Görev durumu
            status_color = NEON_GREEN if obj.completed else UIColors.TEXT_PRIMARY
            
            # X pozisyonu
            x_pos = panel_rect.x + s(15)
            
            # Görev durum simgesi (daha belirgin)
            icon_size = s(18, minimum=12)
            icon_radius = max(1, s(9, minimum=5))
            icon_center = (x_pos + icon_size // 2, y_offset + s(12, minimum=8))
            if obj.completed:
                pygame.draw.circle(self.screen, (12, 120, 70), icon_center, icon_radius)
                pygame.draw.circle(self.screen, (40, 255, 155), icon_center, icon_radius, 1)
                pygame.draw.line(self.screen, (220, 255, 230), (x_pos + s(4, minimum=2), y_offset + s(12, minimum=8)), (x_pos + s(8, minimum=4), y_offset + s(16, minimum=10)), max(1, s(2, minimum=1)))
                pygame.draw.line(self.screen, (220, 255, 230), (x_pos + s(8, minimum=4), y_offset + s(16, minimum=10)), (x_pos + s(15, minimum=9), y_offset + s(7, minimum=4)), max(1, s(2, minimum=1)))
            else:
                pygame.draw.circle(self.screen, (*UIColors.BG_MEDIUM, 210), icon_center, icon_radius)
                pygame.draw.circle(self.screen, UIColors.TEXT_MUTED, icon_center, icon_radius, 1)
                pygame.draw.line(self.screen, UIColors.TEXT_MUTED, (x_pos + s(5, minimum=3), y_offset + s(7, minimum=4)), (x_pos + s(14, minimum=8), y_offset + s(16, minimum=10)), max(1, s(2, minimum=1)))
                pygame.draw.line(self.screen, UIColors.TEXT_MUTED, (x_pos + s(14, minimum=8), y_offset + s(7, minimum=4)), (x_pos + s(5, minimum=3), y_offset + s(16, minimum=10)), max(1, s(2, minimum=1)))
            x_pos += s(24, minimum=16)
            
            # Görev açıklaması - parantez kısmını temizle
            desc = obj.get_description(lang)
            
            # Parantez varsa temizle (sadece ana metni göster)
            if '(' in desc:
                desc = desc.split('(')[0].strip()
            
            # Görev adı (sarmalı)
            desc_lines = wrap_text_lines(obj_font, desc, panel_rect.right - s(22) - x_pos, max_lines=2)
            text_y = y_offset
            for line in desc_lines:
                desc_surface = obj_font.render(line, True, status_color)
                self.screen.blit(desc_surface, (x_pos, text_y))
                text_y += s(21, minimum=14)
            
            # 2. Satır - İlerleme
            progress_y = text_y + s(2, minimum=0)
            progress_text = obj.get_progress_text()
            progress_surface = progress_font.render(progress_text, True, status_color)
            self.screen.blit(progress_surface, (x_pos, progress_y))
            
            # İlerleme barı
            bar_y = progress_y + s(22, minimum=14)
            bar_width = panel_width - s(54)
            bar_height = s(8, minimum=4)
            bar_radius = max(1, s(4, minimum=2))
            
            # Arka plan
            pygame.draw.rect(
                self.screen, UIColors.SLIDER_BG,
                (panel_rect.x + s(25), bar_y, bar_width, bar_height),
                border_radius=bar_radius
            )
            
            # Doluluk
            fill_width = int(bar_width * obj.get_progress_ratio())
            if fill_width > 0:
                fill_color = NEON_GREEN if obj.completed else UIColors.SLIDER_FILL
                pygame.draw.rect(
                    self.screen, fill_color,
                    (panel_rect.x + s(25), bar_y, fill_width, bar_height),
                    border_radius=bar_radius
                )
            
            y_offset = bar_y + bar_height + s(14, minimum=8)
        
        # === YILDIZ KOŞULLARI ===
        # Ayırıcı çizgi
        star_section_y = y_offset + s(8, minimum=4)
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + s(20), star_section_y),
            (panel_rect.right - s(20), star_section_y), 1
        )
        
        star_font = UIFonts.get(s(13, minimum=10))
        star_y = star_section_y + s(10, minimum=6)
        
        # Başlık
        star_title = star_font.render(f"{t('campaign_star_conditions_title')}:", True, UIColors.TEXT_PRIMARY)
        self.screen.blit(star_title, (panel_rect.x + s(20), star_y))
        star_y += s(26, minimum=18)
        
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
                # Faz 2/4 koşul tipleri (no_hold_run, pristine, tetris_only,
                # min_score, garbage_speed) yalnızca description_key taşır;
                # resolve_star_condition_text bunları lokalize eder.
                cond_text = resolve_star_condition_text(condition, lang)
            
            # X pozisyonu
            x_pos = panel_rect.x + s(20)
            
            # Yıldız PNG'lerini çiz (eğer yüklüyse)
            star_icon = self._get_campaign_star_icon(s(20, minimum=14))
            if star_icon:
                # star_num kadar yıldız çiz
                for i in range(star_num):
                    self.screen.blit(star_icon, (x_pos + i * s(18, minimum=12), star_y + s(1, minimum=0)))
                x_pos += star_num * s(18, minimum=12) + s(8, minimum=4)
            else:
                # Fallback: * sembolleri
                star_symbols = "*" * star_num
                star_surf = star_font.render(star_symbols, True, star_color)
                self.screen.blit(star_surf, (x_pos, star_y))
                x_pos += star_surf.get_width() + s(8, minimum=4)
            
            # Koşul metni (sarmalı)
            tick_icon = self._get_campaign_tick_icon(s(18, minimum=14)) if earned_stars_num >= star_num else None
            tick_slot = (tick_icon.get_width() + s(8, minimum=4)) if tick_icon else 0
            max_text_w = max(s(60, minimum=40), panel_rect.right - s(20) - x_pos - tick_slot)
            cond_lines = wrap_text_lines(star_font, cond_text, max_text_w, max_lines=2)
            text_y = star_y
            text_width = 0
            for line in cond_lines:
                text_surface = star_font.render(line, True, star_color)
                self.screen.blit(text_surface, (x_pos, text_y))
                text_width = max(text_width, text_surface.get_width())
                text_y += s(20, minimum=14)
            
            # Tik işareti (koşul tamamlandıysa)
            is_completed = earned_stars_num >= star_num
            if is_completed and tick_icon:
                tick_x = x_pos + text_width + s(8, minimum=4)
                self.screen.blit(tick_icon, (tick_x, star_y + s(1, minimum=0)))
            
            used_h = max(s(20, minimum=14), len(cond_lines) * s(20, minimum=14))
            star_y += used_h + s(6, minimum=4)
        
        # === BLOK SINIRI GÖSTERİMİ (Premium) ===
        limit_font = UIFonts.get(s(12, minimum=10))
        limit_title_font = UIFonts.get(s(14, minimum=11), bold=True)
        
        # Ayırıcı çizgi
        block_section_y = star_y + s(8, minimum=4)
        pygame.draw.line(
            self.screen, THEME_BORDER,
            (panel_rect.x + s(20), block_section_y),
            (panel_rect.right - s(20), block_section_y), 1
        )
        
        block_y = block_section_y + s(10, minimum=6)
        
        count_text, block_color, fill_ratio = self._get_block_limit_hud_state(
            self.level_config.move_limit,
            self.moves_count,
        )
        
        # Başlık: "Kalan Blok" ikonu ile
        block_title = t('campaign_block_limit_title')
        title_surf = limit_title_font.render(block_title, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(title_surf, (panel_rect.x + s(20), block_y))
        
        # Sayı gösterimi (sağ hizalı)
        count_surf = limit_title_font.render(count_text, True, block_color)
        count_x = panel_rect.right - s(20) - count_surf.get_width()
        self.screen.blit(count_surf, (count_x, block_y))
        
        block_y += s(22, minimum=14)
        
        # Progress bar 
        bar_x = panel_rect.x + s(20)
        bar_width = panel_width - s(40)
        bar_height = s(10, minimum=5)
        bar_radius = max(1, s(5, minimum=2))
        
        # Bar arka planı (koyu)
        bar_bg_rect = pygame.Rect(bar_x, block_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, UIColors.SLIDER_BG, bar_bg_rect, border_radius=bar_radius)
        
        # Doluluk barı (kalan blok oranı)
        fill_width = int(bar_width * fill_ratio)
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_x, block_y, fill_width, bar_height)
            pygame.draw.rect(self.screen, block_color, fill_rect, border_radius=bar_radius)
            
            # Parlak kenar efekti (üst kısım)
            if fill_width > s(4, minimum=2):
                highlight_rect = pygame.Rect(bar_x + s(2, minimum=1), block_y + s(1, minimum=0), fill_width - s(4, minimum=2), s(3, minimum=1))
                highlight_color = tuple(min(255, c + 80) for c in block_color)
                highlight_surf = pygame.Surface(highlight_rect.size, pygame.SRCALPHA)
                highlight_surf.fill((*highlight_color, 100))
                self.screen.blit(highlight_surf, highlight_rect.topleft)
        
        # Bar kenarlığı
        pygame.draw.rect(self.screen, THEME_BORDER, bar_bg_rect, 1, border_radius=bar_radius)
        
        block_y += bar_height + s(8, minimum=4)
        
        # Zaman limiti (varsa)
        if self.level_config.time_limit:
            remaining = max(0, self.level_config.time_limit - self.elapsed_time)
            time_color = UIColors.NEON_RED if remaining < 30 else UIColors.TEXT_SECONDARY
            time_text = t('campaign_remaining_time', seconds=int(remaining))
            time_surface = limit_font.render(time_text, True, time_color)
            self.screen.blit(time_surface, (panel_rect.x + s(20), block_y))
        
        return 0
    
    def draw_mode_overlay(self) -> None:
        """Mod overlay'ini çiz"""
        from retro_style import retro_style
        from ui_theme import UIColors, UIFonts

        ui_scale = self._get_campaign_hud_scale(self.screen)
        s = lambda value, minimum=1: self._scale_campaign_hud_px(value, ui_scale, minimum=minimum)
        
        # Sol paneli çiz
        self.draw_mode_info(0, 0)
        
        # === SAĞ PANEL: YILDIZLAR VE İLERLEME ===
        target_rect = getattr(self, '_hud_mode_info_area', None)
        
        if target_rect:
            rx, ry, rw, rh = target_rect
            rh = min(rh, s(160, minimum=110))
            info_rect = pygame.Rect(rx, ry, rw, rh)
        else:
            hud_panel = getattr(self, '_hud_panel_rect', None)
            if hud_panel:
                info_rect = pygame.Rect(hud_panel.x, hud_panel.bottom + s(20, minimum=10), hud_panel.width, s(140, minimum=100))
            else:
                offset_x, offset_y = self.get_board_offset()
                info_rect = pygame.Rect(
                    offset_x + self.board.width * self.get_cell_size() + s(20, minimum=10),
                    offset_y + s(300, minimum=220), s(240, minimum=180), s(140, minimum=100)
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
        padding = s(14, minimum=8)
        inner_x = info_rect.x + padding
        inner_y = info_rect.y + padding
        inner_w = info_rect.width - padding * 2
        inner_h = info_rect.height - padding * 2

        # Toplam ilerleme (başlık kaldırıldı)
        progress_font = UIFonts.get(s(13, minimum=10))
        progress_text = f"{t('level')} {self.current_level_num}/100"
        progress_surface = progress_font.render(progress_text, True, UIColors.TEXT_SECONDARY)
        self.screen.blit(progress_surface, (inner_x, inner_y))

        # Geçen süre (yıldız yerleşimi için önce hesapla)
        time_font = UIFonts.get(s(13, minimum=10))
        mins = int(self.elapsed_time // 60)
        secs = int(self.elapsed_time % 60)
        time_text = f"{t('time')}: {mins}:{secs:02d}"
        time_surface = time_font.render(time_text, True, UIColors.TEXT_SECONDARY)
        time_y = info_rect.bottom - padding - time_surface.get_height()

        # Yıldızlar (panel oranına göre büyüt, minimum büyük boyut)
        star_area_top = inner_y + progress_surface.get_height() + s(6, minimum=2)
        star_area_bottom = time_y - s(6, minimum=2)
        star_area_h = max(0, star_area_bottom - star_area_top)
        star_gap = max(s(10, minimum=6), int(inner_w * 0.06))
        max_star_size_by_w = int((inner_w - star_gap * 2) / 3)
        desired_star_size = int(info_rect.height * 0.35)
        star_size = min(max_star_size_by_w, desired_star_size)
        star_size = max(s(44, minimum=28), star_size)
        if star_area_h > 0 and star_size > star_area_h:
            star_size = max(s(44, minimum=28), min(star_size, star_area_h))
        stars_total_w = star_size * 3 + star_gap * 2
        star_start_x = info_rect.x + (info_rect.width - stars_total_w) // 2
        star_y = star_area_top + max(0, (star_area_h - star_size) // 2)
        star_font = UIFonts.get(max(s(28, minimum=18), star_size), bold=True)

        # Faz 2: 1+3 senaryosunda doğru yıldız işaretleme.
        # In-game (level_complete=False): canlı koşul state'i göster.
        # Post-complete (level_complete=True): kazanılan yıldızlara göre soldan doldur
        # (earned_stars=2 → "★ ★ ☆"). Karma model gereği post-complete'te slot bazlı
        # da gösterilmek istenirse condition_results üstünden çiz; şu an sadeleştirildi:
        condition_results: Dict[int, bool] = {}
        for star_num, condition in self.star_conditions.items():
            try:
                condition_results[int(star_num)] = self._is_star_condition_met(condition)
            except Exception:
                condition_results[int(star_num)] = False

        for i in range(3):
            star_num = i + 1
            star_x = star_start_x + i * (star_size + star_gap)

            # In-game: canlı koşul state. Post-complete: ilgili slot kazanıldı mı?
            # Karma model: 1. yıldız zorunlu, 2 ve 3 bağımsız → slot bazlı işaretleme.
            is_earned = condition_results.get(star_num, False)
            # Karma model: 1. yıldız sağlanmadıysa diğerleri sayılmaz (görsel olarak da)
            if not condition_results.get(1, False):
                is_earned = False

            star_color = UIColors.NEON_GOLD if is_earned else UIColors.TEXT_MUTED

            # Yıldız PNG kullan (varsa)
            scaled_star = self._get_campaign_star_icon(star_size)
            if scaled_star:
                if is_earned:
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

        # Faz 1: First-clear / improvement etiketleri (varsa)
        run_flags = getattr(self, '_last_run_flags', None)
        if isinstance(run_flags, dict):
            if run_flags.get('first_clear'):
                rewards_payload.append((t('campaign_first_clear'), '★'))
            if run_flags.get('star_improvement'):
                prev = run_flags.get('previous_stars', 0)
                rewards_payload.append((
                    t('campaign_new_star_record'),
                    f"{prev} → {self.earned_stars}",
                ))
            if run_flags.get('score_improvement'):
                prev_score = int(run_flags.get('previous_score', 0) or 0)
                prev_score_text = f"{prev_score:,}"
                if lang == 'tr':
                    prev_score_text = prev_score_text.replace(',', '.')
                rewards_payload.append((
                    t('campaign_new_score_record'),
                    f"{prev_score_text} → {reward_score}",
                ))

        # Yıldız koşulları
        star_conditions_payload = []
        for star_num in sorted(self.star_conditions.keys()):
            condition = self.star_conditions[star_num]
            desc = resolve_star_condition_text(condition, lang)
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
                progress = self.user_manager.get_campaign_progress()
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
        """Level başarısız ekranı - Oyun bitti ekranıyla aynı layout, kırmızı tema."""
        from localization import t
        _red_theme = {
            'panel_border_color': (220, 50, 70),
            'panel_glow_color':   (160, 25, 40),
            'panel_fill_tint':    (30, 8, 12),
            'card_fill_tint':     (38, 12, 18),
            'card_border_color':  (140, 50, 65),
            'gradient_tint':      (20, 5, 8),
            'title_text':         t('campaign_failed_title'),
            'skip_stars':         True,   # başarısızlıkta yıldız yok
            'skip_record':        True,   # başarısızlıkta rekor yok
            'state_prefix':       'fail_',
        }
        self._draw_game_over_overlay(None, alt_theme=_red_theme)

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

        screen_w, screen_h = self.screen.get_size()
        ui_scale = self._get_campaign_hud_scale((screen_w, screen_h))
        s = lambda value, minimum=1: self._scale_campaign_hud_px(value, ui_scale, minimum=minimum)

        panel_rect = self._get_campaign_right_hud_panel_rect(offset_x, offset_y, board_width, board_height)
        info_x = panel_rect.x
        header_y = panel_rect.y
        panel_width = panel_rect.width
        self._campaign_hud_title_rect = None
        self._campaign_hud_subtitle_rect = None
        self._hud_next_label_rect = None
        self._hud_hold_label_rect = None
        
        # Ana panel arka planı (Glassmorphism)
        self._draw_hud_glass_panel(panel_rect)
        
        # İçerik Y pozisyonu
        side_padding = max(s(8, minimum=6), min(s(15, minimum=10), max(s(8, minimum=6), panel_width // 8)))
        curr_y = header_y + s(16, minimum=10)
        content_x = info_x + side_padding
        content_w = max(40, panel_width - (side_padding * 2))
        
        # Başlık - fitted text ile panel genisligine sigdir
        badge_text = t('campaign_title')
        title_center_x = info_x + panel_width // 2
        title_max_width = max(30, content_w - s(4, minimum=2))
        
        # Boss level ise özel renk
        if self.is_boss:
            title_accent = (255, 50, 50)  # Kırmızı
        elif self.is_mini_boss:
            title_accent = (255, 165, 0)  # Turuncu
        else:
            title_accent = accent_color

        title_surf = self._render_hud_fitted_text(
            badge_text,
            title_accent,
            title_max_width,
            s(28, minimum=18),
            s(11, minimum=8),
            bold=True,
        )
        title_rect = title_surf.get_rect(midtop=(title_center_x, curr_y))
        for off in range(2, 0, -1):
            glow_surf = title_surf.copy()
            glow_surf.set_alpha(70)
            self.screen.blit(glow_surf, glow_surf.get_rect(midtop=(title_center_x, curr_y + off)))
        self.screen.blit(title_surf, title_rect)
        self._campaign_hud_title_rect = title_rect.copy()
        
        curr_y = title_rect.bottom + s(8, minimum=6)
        
        # Level bilgisi
        level_text = f"{t('level')} {self.current_level_num}"
        if self.is_boss:
            level_text += f" ({t('campaign_boss')})"
        elif self.is_mini_boss:
            level_text += f" ({t('campaign_mini_boss')})"

        sub_surf = self._render_hud_fitted_text(
            level_text,
            text_color,
            title_max_width,
            s(16, minimum=11),
            s(9, minimum=7),
            bold=False,
        )
        sub_rect = sub_surf.get_rect(midtop=(title_center_x, curr_y))
        self.screen.blit(sub_surf, sub_rect)
        self._campaign_hud_subtitle_rect = sub_rect.copy()
        curr_y = sub_rect.bottom + s(10, minimum=6)

        # Faz 2: Boss/Mini-Boss sözel etiket (renkli, boss tipine göre)
        boss_type = self._boss_get_type()
        if boss_type:
            label_key = {
                'rain': 'campaign_boss_rain',
                'seal': 'campaign_boss_seal',
                'dark': 'campaign_boss_dark',
                'final': 'campaign_boss_final',
                'fast': 'campaign_miniboss_fast',
                'missing': 'campaign_miniboss_missing',
            }.get(boss_type)
            if label_key:
                # Boss kırmızı, mini-boss turuncu
                boss_color = (255, 80, 80) if self.is_boss else (255, 165, 0)
                boss_label_surf = self._render_hud_fitted_text(
                    t(label_key),
                    boss_color,
                    title_max_width,
                    s(13, minimum=10),
                    s(8, minimum=7),
                    bold=True,
                )
                boss_label_rect = boss_label_surf.get_rect(midtop=(title_center_x, curr_y))
                self.screen.blit(boss_label_surf, boss_label_rect)
                curr_y = boss_label_rect.bottom + s(6, minimum=4)

        curr_y += s(10, minimum=6)
        
        # --- NEXT PIECES ---
        next_label = self._render_hud_fitted_text(
            t('next'),
            label_color,
            content_w,
            s(18, minimum=12),
            s(10, minimum=8),
            bold=False,
        )
        next_label_rect = next_label.get_rect(topleft=(content_x, curr_y))
        self.screen.blit(next_label, next_label_rect)
        self._hud_next_label_rect = next_label_rect.copy()
        
        curr_y = next_label_rect.bottom + s(14, minimum=8)
        box_size = min(s(60, minimum=44), max(s(42, minimum=32), int(content_w * 0.34)))
        gap = max(s(10, minimum=6), int(content_w * 0.08))
        
        for i in range(2):
            bx = content_x + i * (box_size + gap)
            by = curr_y
            box_rect = pygame.Rect(bx, by, box_size, box_size)
            
            # Kutu arkaplanı
            if not self._draw_custom_frame(box_rect, "box_frame.png", padding=s(4, minimum=2)):
                pygame.draw.rect(self.screen, (20, 25, 40, 180), box_rect, border_radius=s(8, minimum=4))
                pygame.draw.rect(self.screen, (60, 70, 100), box_rect, 1, border_radius=s(8, minimum=4))
            
            # Boss ise ? göster
            if self._hide_next_pieces:
                # Soru işareti göster
                q_font = retro_style.get_font(s(36, minimum=20), bold=True)
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
                
                mini_cell = max(s(12, minimum=8), int(box_size * 0.2))
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
        
        curr_y += box_size + s(20, minimum=10)
        
        # --- HOLD PIECE ---
        hold_label = self._render_hud_fitted_text(
            t('hold'),
            label_color,
            content_w,
            s(18, minimum=12),
            s(10, minimum=8),
            bold=False,
        )
        hold_label_rect = hold_label.get_rect(topleft=(content_x, curr_y))
        self.screen.blit(hold_label, hold_label_rect)
        self._hud_hold_label_rect = hold_label_rect.copy()
        
        curr_y = hold_label_rect.bottom + s(14, minimum=8)
        hold_box_rect = pygame.Rect(content_x, curr_y, box_size + s(20, minimum=12), box_size)
        
        if not self._draw_custom_frame(hold_box_rect, "box_frame.png", padding=s(4, minimum=2)):
            pygame.draw.rect(self.screen, (20, 25, 40, 180), hold_box_rect, border_radius=s(8, minimum=4))
            pygame.draw.rect(self.screen, (60, 70, 100), hold_box_rect, 1, border_radius=s(8, minimum=4))
        
        # Mini boss veya boss ise X göster
        if self._show_hold_x:
            # Büyük X çiz
            x_font = retro_style.get_font(s(48, minimum=24), bold=True)
            x_surf = x_font.render("X", True, (255, 80, 80))
            x_rect = x_surf.get_rect(center=hold_box_rect.center)
            self.screen.blit(x_surf, x_rect)
        elif self.held_piece:
            # Normal held piece çizimi
            hp = self.held_piece
            hp_tex = getattr(hp, 'texture_surface', None)
            pw = len(hp.shape[0]) if hp.shape else 1
            ph = len(hp.shape) if hp.shape else 1
            mini_cell = max(s(14, minimum=9), int(box_size * 0.22))
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
                pygame.draw.line(self.screen, (200, 50, 50), (lx - s(10, minimum=6), ly - s(10, minimum=6)), (lx + s(10, minimum=6), ly + s(10, minimum=6)), max(1, s(3, minimum=2)))
                pygame.draw.line(self.screen, (200, 50, 50), (lx - s(10, minimum=6), ly + s(10, minimum=6)), (lx + s(10, minimum=6), ly - s(10, minimum=6)), max(1, s(3, minimum=2)))
        
        curr_y += box_size + s(30, minimum=18)
        
        # --- SCORE & STATS ---
        available_stats_h = max(s(120, minimum=100), panel_rect.bottom - curr_y - s(12, minimum=0))
        stats_h = min(available_stats_h, max(s(150, minimum=120), min(s(240, minimum=150), available_stats_h)))
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
        pygame.draw.rect(self.screen, (50, 60, 80), stats_rect, 1, border_radius=s(12, minimum=6))
        
        stat_y_cur = curr_y + s(15, minimum=8)
        
        def draw_stat_row(label, value, y_pos, color_val=accent_color):
            l_surf = retro_style.get_font(s(16, minimum=11)).render(label, True, (160, 170, 190))
            self.screen.blit(l_surf, (content_x + s(15, minimum=8), y_pos))
            
            v_surf = retro_style.get_font(s(24, minimum=15), bold=True).render(str(value), True, color_val)
            v_rect = v_surf.get_rect(topright=(content_x + content_w - s(15, minimum=8), y_pos - s(4, minimum=2)))
            self.screen.blit(v_surf, v_rect)
            
            line_y = y_pos + s(32, minimum=20)
            inset = s(10, minimum=6)
            pygame.draw.line(self.screen, (255, 255, 255, 30), (content_x + inset, line_y), (content_x + content_w - inset, line_y))
            return s(45, minimum=28)
        
        stat_y_cur += draw_stat_row(t('score'), f'{self.board.score:,}'.replace(',', '.'), stat_y_cur, accent_color)
        stat_y_cur += draw_stat_row(t('lines'), str(self.board.lines_cleared), stat_y_cur, text_color)
        stat_y_cur += draw_stat_row(t('level'), str(self.current_level_num), stat_y_cur)
        
        if self.board.combo > 1:
            draw_stat_row(t('combo'), f'x{self.board.combo}', stat_y_cur, (255, 200, 50))
        elif self.board.tetrises > 0:
            draw_stat_row('Quadrix', str(self.board.tetrises), stat_y_cur, (100, 255, 100))
        
        # Mod info
        mode_info_y = stats_rect.bottom + s(15, minimum=8)
        self._hud_mode_info_area = (
            int(content_x),
            int(mode_info_y),
            int(content_w),
            int(max(0, screen_h - mode_info_y - 8)),
        )
