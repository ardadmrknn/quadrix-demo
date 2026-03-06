"""PvP (2 Oyunculu) Mod"""
import pygame
import random
import math
import sys
import os
from pathlib import Path
from board import Board
from pieces import Piece, create_piece_by_index, SHAPES
from constants import *
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from mode_skins import apply_board_tint, apply_outer_tint, draw_board_overlay, get_mode_skin
from retro_style import retro_style
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from themes import ThemeManager, CUSTOM_THEME_NAME
from block_styles import BlockStyleManager, TextureSlice
from platform_utils import create_display, get_display_flags, normalize_mouse_pos, get_mouse_pos, set_app_icon
from localization import t
from ui_theme import UIColors, UIFonts

def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return os.path.normpath(str(base_path / relative_path))


class PvPGame:
    """2 oyunculu PvP oyun sınıfı"""

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.20) -> float:
        """Pencere boyutuna bağlı genel UI ölçeği."""
        try:
            scale = min(float(self.window_width) / 1366.0, float(self.window_height) / 768.0)
        except Exception:
            scale = 1.0
        return max(min_scale, min(max_scale, scale))

    def _sx(self, value: int | float, scale: float | None = None, minimum: int = 1) -> int:
        """Sabit piksel değerini UI ölçeğine göre dönüştür."""
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    @property
    def pause_menu_options(self):
        """Dil değiştiğinde dinamik güncellenen pause menü seçenekleri"""
        return list(self._pause_menu_keys)

    def wants_mouse_visible(self) -> bool:
        # Normal gameplay: gizli; pause / oyun sonu / isim ekranı gibi UI'de görünür.
        if getattr(self, 'show_exit_prompt', False):
            return True
        if getattr(self, 'paused', False):
            return True
        if getattr(self, 'game_over', False):
            return True
        if getattr(self, 'name_input_active', False):
            return True
        return False

    def _particle_effects_enabled(self) -> bool:
        if not getattr(self, 'effects_enabled', True):
            return False
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            return False
        try:
            return bool(sm.get('particle_effects', False))
        except Exception:
            return False
    
    def __init__(
        self,
        sound_enabled=True,
        effects_enabled=True,
        screen=None,
        fullscreen=False,
        user_manager=None,
        settings_manager=None,
        sound_manager=None,
    ):
        """PvP oyunu başlat"""
        if not pygame.get_init():
            pygame.init()
        
        # User manager ve Settings manager
        self.user_manager = user_manager
        self.settings_manager = settings_manager
        self.pvp_controls = self._resolve_pvp_controls()
        
        # Eğer ekran verilmişse onu kullan, yoksa yeni oluştur
        if screen is not None:
            self.screen = screen
            self.window_width = screen.get_width()
            self.window_height = screen.get_height()
            self.fullscreen = fullscreen
        else:
            # Geniş pencere (2 tahta yan yana) - Daha büyük başlangıç boyutu
            self.window_width = 1400
            self.window_height = 1000
            
            self.screen = create_display(self.window_width, self.window_height, fullscreen=False, resizable=True)
            self.fullscreen = False
        
        try:
            pygame.display.set_caption('Quadrix')
        except Exception:
            pass
        try:
            import os
            _pvp_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
            set_app_icon(_pvp_assets)
        except Exception:
            pass
        
        # Ses yöneticisi (menüden enjekte edilebilir)
        self.sound = sound_manager if sound_manager is not None else SoundManager()
        self.sound.enabled = True  # Müzik için her zaman açık
        self.sound.sfx_enabled = sound_enabled  # Ses efektleri ayarı
        if self.settings_manager:
            self.sound.music_enabled = self.settings_manager.get('music_enabled', True)
        self.current_music_track = None
        self.effects_enabled = effects_enabled
        self._start_pvp_music()
        
        # Arka plan yöneticileri
        self.background = BackgroundManager()  # Ana arka plan
        self.board_background = BackgroundManager()  # Quadrix alanları için ayrı arka plan
        
        # Ana arka planı tam opak yap (1.0 = %100 opak, transparanlık yok)
        self.background.set_transparency(1.0)
        
        # Board background'a ayarlardaki transparanlığı uygula
        if self.settings_manager:
            bg_transparency = self.settings_manager.get('bg_transparency', 1.0)
            self.board_background.set_transparency(bg_transparency)
        else:
            self.board_background.set_transparency(1.0)
        
        self.load_background_image()
        self.load_board_background()
        
        # Tema sistemi (tek oyunculu ile aynı)
        self.theme_manager = ThemeManager(self.settings_manager)
        if self.settings_manager:
            active_theme = self.settings_manager.get('theme', self.settings_manager.get('active_theme', 'Classic'))
            self.theme_manager.set_theme(active_theme)
        self.mode_skin = get_mode_skin('pvp')

        # Blok stili / texture sistemi (tek oyunculu ile aynı temel)
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None
        self._texture_rotation_cache = {}
        
        # İki oyuncu
        self.board1 = Board()  # Oyuncu 1 (Sol - WASD)
        self.board2 = Board()  # Oyuncu 2 (Sağ - Ok tuşları)
        
        # Senkronize parçalar (her iki oyuncu aynı parçaları alır)
        self.piece_sequence = []
        self.current_piece_index = 0
        self.generate_pieces(100)  # 100 parça önceden oluştur
        
        # Oyuncu 1 parçaları
        self.current_piece1 = self.get_next_piece()
        self.next_piece1 = self.get_next_piece()
        
        # Oyuncu 2 parçaları (aynı sıra)
        self.current_piece_index = 0  # Sıfırla
        self.current_piece2 = self.get_next_piece()
        self.next_piece2 = self.get_next_piece()
        
        # Tema renklerini parçalara uygula
        self.apply_theme_to_pieces()
        
        # Oyun durumu
        self.game_over = False
        self.winner = None  # 1, 2, veya 'draw'
        self.paused = False

        # ESC ile çıkış onayı (tek oyunculu ile aynı davranış)
        self.show_exit_prompt = False
        self.exit_yes_rect: pygame.Rect | None = None
        self.exit_no_rect: pygame.Rect | None = None

        # PvP maç modu: 'timed' (süreli) veya 'endless' (süresiz)
        self.match_mode = 'timed'  # Varsayılan: süreli
        self.custom_duration_minutes = 2  # Kullanıcının seçtiği süre (dakika)
        self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
        self.match_elapsed_ms = 0
        self.match_active = False
        self.match_end_reason: str | None = None  # 'time' | 'elimination' | None
        self._last_timer_seconds: int | None = None

        # Eleme durumu: spawn edemeyen (veya top-out olan) oyuncu elenir
        self.p1_eliminated = False
        self.p2_eliminated = False

        # Duraklama menüsü (tek oyunculu ile aynı)
        self.pause_menu_selected = 0
        self._pause_menu_keys = ['resume', 'music', 'music_volume', 'sound_effects', 'sfx_volume', 'main_menu']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active: bool = False
        self._pause_vol_drag_option: str = ''
        
        # Game over ekranı buton rect'leri (mouse desteği için)
        self._game_over_restart_rect: pygame.Rect | None = None
        self._game_over_menu_rect: pygame.Rect | None = None
        
        # Oyuncu isimleri
        self.player1_name = ""
        self.player2_name = ""
        self.name_input_active = True  # İsim girişi ekranı
        self.current_input = 1  # Hangi oyuncunun ismini giriyoruz (1 veya 2, 3=mod seçimi, 4=süre ayarı)
        
        # Zamanlama - Her oyuncu için ayrı hız
        self.fall_time1 = 0
        self.fall_time2 = 0
        self.fall_speed1 = 900  # Oyuncu 1 sabit hız
        self.fall_speed2 = 900  # Oyuncu 2 sabit hız
        self.speed_increase_per_milestone = 0  # Hızlanma yok
        self.min_fall_speed = 900  # Sabit hız
        
        # Fontlar
        self.font_large = UIFonts.get(72)
        self.font_vs = UIFonts.get(120)  # VS için çok büyük font
        self.font_medium = UIFonts.get(36)
        self.font_small = UIFonts.get(24)
        
        # Partiküller
        self.particles = []

        # Satır temizleme efekt sistemi (ana oyundaki gibi gelişmiş)
        self.p1_line_flash_rows = []
        self.p2_line_flash_rows = []
        self.p1_line_flash_timer = 0  # Frame bazlı timer
        self.p2_line_flash_timer = 0
        self.p1_line_glow_alpha = 0
        self.p2_line_glow_alpha = 0
        self.p1_wave_effects = []  # Dalga efektleri
        self.p2_wave_effects = []
        self.p1_line_sweep_rows = []
        self.p1_line_sweep_progress = 0.0
        self.p1_line_sweep_active = False
        self.p2_line_sweep_rows = []
        self.p2_line_sweep_progress = 0.0
        self.p2_line_sweep_active = False
        self.p1_falling_block_animations = []
        self.p2_falling_block_animations = []
        self.p1_drop_trails = []
        self.p2_drop_trails = []
        self.block_fall_speed = 0.08
        
        # Arka plan parçacıkları (ambient effect)
        self.ambient_particles = []
        self.create_ambient_particles()

        # İsim giriş ekranı için arka plan tetris blokları efekti
        self.name_background_fx = get_shared_falling_blocks_layer('default') if self.effects_enabled else None
        
        # Screen shake efekti
        self.screen_shake = 0
        self.shake_intensity = 0
        
        # Havai fişek sistemi (her 1000 puan) - Her oyuncu için ayrı
        self.p1_last_milestone = 0
        self.p2_last_milestone = 0
        self.p1_firework_active = False
        self.p2_firework_active = False
        self.p1_firework_time = 0
        self.p2_firework_time = 0
        
        # DAS (Delayed Auto Shift) - Her oyuncu için ayrı
        # Oyuncu 1
        self.p1_das_direction = 0  # -1: sol, 0: yok, 1: sağ
        self.p1_das_timer = 0
        self.p1_das_repeat_timer = 0
        self.p1_das_charged = False
        # Oyuncu 2
        self.p2_das_direction = 0
        self.p2_das_timer = 0
        self.p2_das_repeat_timer = 0
        self.p2_das_charged = False
        
        # Soft drop (hızlı düşüş) - Her oyuncu için ayrı
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0
        self.p2_soft_drop_active = False
        self.p2_soft_drop_timer = 0
        self.soft_drop_speed = 50  # Soft drop hızı (ms)
        
        # Oyun alanı pozisyonları (parçacıklar için)
        self.cell_size = 50
        self.center_panel_width = 320
        self.header_height = 64
        self.header_top = 28
        self.board_top = 120
        self.board_gap = 24
        self._layout_key = None
        self._board_grid_cache = {'key': None, 'surface': None}

        # Kilitli blokları cache'le (her frame tüm grid'i çizme maliyetini azalt)
        self._locked_board_cache = {
            1: {'key': None, 'surface': None, 'dirty': True},
            2: {'key': None, 'surface': None, 'dirty': True},
        }

        # Ambient particle sprite cache (surface allocation azalt)
        self._ambient_sprite_cache = {}

        # PvP draw cache (surface allocation azalt)
        self._board_accent_overlay_cache = {}
        self.calculate_board_positions()
        
        self._vs_panel_surface = None
        self._vs_panel_dirty = True
    
    def apply_theme_to_pieces(self):
        """Tema + blok stili görünümünü mevcut parçalara uygula (ana oyun temeli)."""
        for piece in (self.current_piece1, self.next_piece1, self.current_piece2, self.next_piece2):
            self._apply_block_style(piece)

    def _apply_block_style(self, piece):
        if not piece:
            return
        base_color = self.theme_manager.get_piece_color(piece.name) if self.theme_manager else piece.color
        if self.block_style_manager:
                allow_color_override = bool(
                    self.theme_manager
                    and getattr(self.theme_manager, 'theme_name', None) == CUSTOM_THEME_NAME
                )
                self.block_style_manager.apply_to_piece(
                    piece,
                    base_color,
                    allow_color_override=allow_color_override,
                )
        else:
            piece.color = base_color
            # Texture sistemi yoksa garantiye al
            piece.texture_path = None
            piece.texture_surface = None
            piece.texture_surface_original = None
    
    def _find_closest_theme_color(self, color):
        """Bir rengi en yakın tema rengine eşleştir"""
        if not self.theme_manager:
            return color
        
        # Tüm parça renklerini al
        theme_colors = {
            self.theme_manager.get_piece_color('I'),
            self.theme_manager.get_piece_color('O'),
            self.theme_manager.get_piece_color('T'),
            self.theme_manager.get_piece_color('S'),
            self.theme_manager.get_piece_color('Z'),
            self.theme_manager.get_piece_color('J'),
            self.theme_manager.get_piece_color('L')
        }
        
        # En yakın rengi bul
        min_distance = float('inf')
        closest_color = color
        for theme_color in theme_colors:
            distance = sum((a - b) ** 2 for a, b in zip(color[:3], theme_color[:3]))
            if distance < min_distance:
                min_distance = distance
                closest_color = theme_color
        
        return closest_color

    def _mark_locked_board_dirty(self, player: int) -> None:
        cache = self._locked_board_cache.get(player)
        if cache is not None:
            cache['dirty'] = True

    def _start_block_fall_animation(self, player: int, board: Board, cleared_rows: list[int]) -> None:
        if not cleared_rows:
            return
        animations = []
        lines_count = len(cleared_rows)
        cell_size = self.cell_size
        for row in range(board.height):
            for col in range(board.width):
                if board.occupancy[row][col]:
                    animations.append({
                        'row': row,
                        'col': col,
                        'current_offset': -lines_count * cell_size,
                        'target_offset': 0,
                        'sweep_trigger': col / max(1, board.width - 1),
                        'started': False,
                    })
        if player == 1:
            self.p1_falling_block_animations = animations
        else:
            self.p2_falling_block_animations = animations

    def _get_block_fall_offset(self, player: int, row: int, col: int) -> float:
        animations = self.p1_falling_block_animations if player == 1 else self.p2_falling_block_animations
        for anim in animations:
            if anim['row'] == row and anim['col'] == col:
                return anim['current_offset']
        return 0

    def _get_ambient_sprite(self, radius: int, alpha: int, glow: bool) -> pygame.Surface:
        """Create/reuse small cached circle sprites for ambient particles."""
        radius = max(1, int(radius))
        alpha = int(max(0, min(255, int(alpha))))
        alpha_bucket = int(alpha // 16) * 16
        key = (radius, alpha_bucket, 1 if glow else 0)
        cached = self._ambient_sprite_cache.get(key)
        if cached is not None:
            return cached

        size = radius * (4 if glow else 2)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        color = (200, 200, 255, alpha_bucket)
        pygame.draw.circle(surf, color, center, radius * (2 if glow else 1))
        self._ambient_sprite_cache[key] = surf
        return surf

    def _resolve_pvp_controls(self):
        defaults = {
            'player1': {
                'move_left': pygame.K_a,
                'move_right': pygame.K_d,
                'soft_drop': pygame.K_s,
                'hard_drop': pygame.K_LSHIFT,
                'rotate': pygame.K_w,
            },
            'player2': {
                'move_left': pygame.K_LEFT,
                'move_right': pygame.K_RIGHT,
                'soft_drop': pygame.K_DOWN,
                'hard_drop': pygame.K_SPACE,
                'rotate': pygame.K_UP,
            },
            'pause': pygame.K_p,
        }
        if not self.settings_manager:
            return defaults
        controls = self.settings_manager.get_controls()
        pvp_config = controls.get('pvp', {}) if isinstance(controls, dict) else {}
        resolved = {
            'player1': {},
            'player2': {},
        }
        for player in ('player1', 'player2'):
            player_cfg = pvp_config.get(player, {}) if isinstance(pvp_config, dict) else {}
            resolved[player] = {
                action: self._binding_to_keycode(player_cfg.get(action), defaults[player][action])
                for action in defaults[player]
            }
        single_cfg = controls.get('single_player', {}) if isinstance(controls, dict) else {}
        resolved['pause'] = self._binding_to_keycode(single_cfg.get('pause'), defaults['pause'])
        return resolved

    @staticmethod
    def _binding_to_keycode(binding, fallback):
        if isinstance(binding, int):
            return binding
        if isinstance(binding, str):
            try:
                return pygame.key.key_code(binding)
            except ValueError:
                return fallback
        return fallback

    @staticmethod
    def _key_label(key_code):
        try:
            return pygame.key.name(key_code).upper()
        except ValueError:
            return str(key_code)

    def _start_pvp_music(self):
        """Start the arena music respecting user preferences."""
        if not getattr(self.sound, 'music_enabled', True):
            return
        playlist_values = []
        if self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_music_playlist_for_mode('pvp')
            except Exception:
                playlist_values = []
        if playlist_values:
            track_keys = []
            for value in playlist_values:
                track_key = self.sound.ensure_track_available(value)
                if track_key:
                    track_keys.append(track_key)
            if track_keys:
                do_shuffle = bool(self.settings_manager.get('music_shuffle', False)) if self.settings_manager else False
                if do_shuffle:
                    start_index = 0
                else:
                    start_index = random.randrange(len(track_keys))
                self.sound.set_music_playlist(track_keys, loop=True, start_index=start_index, autoplay=True, force=True, shuffle=do_shuffle)
                self.current_music_track = track_keys[start_index]
                return

        preferred = None
        if self.settings_manager:
            overrides = self.settings_manager.get_mode_music_overrides()
            preferred = overrides.get('pvp')
            if not preferred:
                preferred = self.settings_manager.get('pvp_music')
            if not preferred:
                preferred = self.settings_manager.get('game_music')
        track_key = self.sound.ensure_track_available(preferred or 'pvp_1')
        if track_key:
            self.sound.set_music_playlist([track_key], loop=True, autoplay=True, force=True)
            self.current_music_track = track_key

    def _get_vs_panel_surface(self, panel_width=None):
        """Return (and rebuild if needed) the cached VS panel surface."""
        target_width = panel_width if panel_width else min(400, max(280, self.window_width // 3))
        target_height = 180  # Daha kompakt panel
        needs_rebuild = (
            self._vs_panel_surface is None
            or self._vs_panel_surface.get_width() != target_width
            or self._vs_panel_surface.get_height() != target_height
            or self._vs_panel_dirty
        )
        if needs_rebuild:
            surface = pygame.Surface((target_width, target_height), pygame.SRCALPHA)
            self._render_vs_panel(surface)
            self._vs_panel_surface = surface
            self._vs_panel_dirty = False
        return self._vs_panel_surface

    def _render_vs_panel(self, surface: pygame.Surface) -> None:
        """Draw the neon VS centerpiece once onto the provided surface."""
        skin = self.mode_skin
        rect = surface.get_rect()
        surface.fill((0, 0, 0, 0))

        pygame.draw.rect(surface, skin.panel_bg, rect, border_radius=15)
        pygame.draw.rect(surface, skin.panel_border, rect, 3, border_radius=15)

        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*skin.accent, 24), rect.inflate(-12, -12), border_radius=12)
        surface.blit(glow, (0, 0))

        # Oyuncu isimleri ve VS - yan yana: OYUNCU1 VS OYUNCU2
        name_font = self.font_medium
        p1_label = (self.player1_name or t('pvp_player1')).upper()
        p2_label = (self.player2_name or t('pvp_player2')).upper()
        
        # VS yazısı
        vs_font = UIFonts.get(60)
        vs_text = vs_font.render('VS', True, skin.accent)
        vs_shadow = vs_font.render('VS', True, (10, 10, 10))
        
        # İsimleri render et
        p1_text = name_font.render(p1_label, True, CYAN)
        p2_text = name_font.render(p2_label, True, MAGENTA)
        
        # Pozisyonları hesapla - ortada VS, solda P1, sağda P2
        center_y = rect.centery - 15
        vs_rect = vs_text.get_rect(center=(rect.centerx, center_y))
        
        # Oyuncu 1 - VS'nin solunda
        p1_rect = p1_text.get_rect(midright=(vs_rect.left - 15, center_y))
        # Oyuncu 2 - VS'nin sağında  
        p2_rect = p2_text.get_rect(midleft=(vs_rect.right + 15, center_y))
        
        # Çiz
        surface.blit(vs_shadow, vs_rect.move(2, 2))
        surface.blit(vs_text, vs_rect)
        surface.blit(p1_text, p1_rect)
        surface.blit(p2_text, p2_rect)

        # Kontrol bilgileri
        info_font = self.font_small
        pause_label = self._key_label(self.pvp_controls['pause'])
        hint = info_font.render(f'{pause_label}: {t("pvp_pause_hint")}  •  ESC: {t("pvp_pause_hint")}', True, skin.text_color)
        surface.blit(hint, hint.get_rect(center=(rect.centerx, rect.centery + 40)))

        # Match timer - süreli modda geri sayım, süresiz modda geçen süre
        if self.match_mode == 'timed':
            remaining_ms = max(0, int(self.match_duration_ms) - int(getattr(self, 'match_elapsed_ms', 0) or 0))
            total_seconds = remaining_ms // 1000
            mm = total_seconds // 60
            ss = total_seconds % 60
            timer_label = f"{t('time_left')}: {mm}:{ss:02d}"
        else:
            # Süresiz mod - geçen süreyi göster
            elapsed_ms = int(getattr(self, 'match_elapsed_ms', 0) or 0)
            total_seconds = elapsed_ms // 1000
            mm = total_seconds // 60
            ss = total_seconds % 60
            timer_label = f"{t('time')}: {mm}:{ss:02d} ∞"
        timer = info_font.render(timer_label, True, skin.text_color)
        surface.blit(timer, timer.get_rect(center=(rect.centerx, rect.centery + 70)))
    
    def calculate_board_positions(self):
        """Oyun tahtalarının ekran pozisyonlarını hesapla"""
        key = (int(self.window_width), int(self.window_height))
        if self._layout_key == key:
            return

        self._layout_key = key
        width, height = key

        # Minimal ve simetrik: iki board + ortada VS panel, her şey pencereye sığacak şekilde ölçeklenir.
        outer_margin = 24
        header_height = int(getattr(self, 'header_height', 64) or 64)
        header_top = int(getattr(self, 'header_top', 28) or 28)
        board_gap = int(getattr(self, 'board_gap', 24) or 24)

        # Board alanları, üst oyuncu kartlarının hemen altına hizalansın.
        # Böylece farklı pencere boyutlarında boşluk/taşma daha tutarlı olur.
        # Biraz yukarı taşı (-25)
        board_top = header_top + header_height + 24 - 25

        # Yüksekliğe göre cell_size
        bottom_margin = 60
        available_h = max(200, height - board_top - bottom_margin)
        cell_by_h = available_h // BOARD_HEIGHT

        # Genişliğe göre cell_size (VS paneli dahil)
        target_center = min(420, max(260, width // 5))
        available_w = max(200, width - 2 * outer_margin - target_center - 2 * board_gap)
        cell_by_w = available_w // (2 * BOARD_WIDTH)

        cell_size = int(min(50, cell_by_h, cell_by_w))
        cell_size = int(max(20, cell_size))

        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size

        # Ortadaki panel genişliği: kalan boşluğa göre ayarla
        remaining = width - (2 * board_width) - 2 * board_gap
        center_panel_width = int(min(420, max(240, remaining)))
        # Çok sıkışık durumlarda paneli küçült
        if remaining < 240:
            center_panel_width = int(max(200, remaining))
        # Yine de minimum boşluk bırak
        if width - (2 * board_width + center_panel_width + 2 * board_gap) < 2 * outer_margin:
            center_panel_width = int(max(200, width - 2 * outer_margin - 2 * board_width - 2 * board_gap))

        total_w = 2 * board_width + center_panel_width + 2 * board_gap
        start_x = (width - total_w) // 2
        start_x = int(max(outer_margin, start_x))

        self.cell_size = cell_size
        self.center_panel_width = center_panel_width
        self.header_height = header_height
        self.header_top = header_top
        self.board_top = board_top
        self.board_gap = board_gap

        self.p1_offset_x = start_x
        self.p2_offset_x = start_x + board_width + board_gap + center_panel_width + board_gap
        self.p1_offset_y = board_top
        self.p2_offset_y = board_top

        # Grid cache invalidate
        self._board_grid_cache['key'] = None
        self._board_grid_cache['surface'] = None

        # Locked board caches invalidate (layout/cell değişti)
        self._mark_locked_board_dirty(1)
        self._mark_locked_board_dirty(2)

    def _get_board_grid_surface(self, cell_size: int):
        """Return cached semi-transparent grid surface sized to the board."""
        skin = self.mode_skin
        key = (int(cell_size), tuple(getattr(skin, 'grid_color', (50, 50, 80))), BOARD_WIDTH, BOARD_HEIGHT)
        cached = self._board_grid_cache
        if cached.get('key') == key and cached.get('surface') is not None:
            return cached['surface']

        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        surface = pygame.Surface((board_width, board_height), pygame.SRCALPHA)
        grid_color = getattr(skin, 'grid_color', (50, 50, 80))

        # Daha minimalist görünüm: grid çizgilerini alpha ile yumuşat.
        grid_alpha = 70
        line_color = (*grid_color[:3], grid_alpha)

        for x in range(BOARD_WIDTH + 1):
            pygame.draw.line(surface, line_color, (x * cell_size, 0), (x * cell_size, board_height))
        for y in range(BOARD_HEIGHT + 1):
            pygame.draw.line(surface, line_color, (0, y * cell_size), (board_width, y * cell_size))

        cached['key'] = key
        cached['surface'] = surface
        return surface

    def _draw_player_header(self, rect: pygame.Rect, name: str, accent_color, score: int, lines: int, controls_label: str):
        skin = self.mode_skin
        # Glass panel (ana UI ile uyumlu)
        retro_style.draw_glass_panel(self.screen, rect, alpha=190, border_color=accent_color)
        pygame.draw.rect(self.screen, (*accent_color[:3], 120), rect, 2, border_radius=16)

        # Accent underline
        underline = pygame.Rect(rect.x + 14, rect.bottom - 6, rect.width - 28, 3)
        pygame.draw.rect(self.screen, accent_color, underline, border_radius=2)

        title = self.font_medium.render(name, True, accent_color)
        title_rect = title.get_rect(midleft=(rect.x + 16, rect.centery - 10))
        self.screen.blit(title, title_rect)

        # Sağ tarafta kompakt skor/satır
        info_color = skin.text_color
        score_s = self.font_small.render(f'{t("pvp_score")} {score:,}'.replace(',', '.'), True, info_color)
        lines_s = self.font_small.render(f'{t("pvp_lines")} {lines}', True, info_color)
        self.screen.blit(score_s, score_s.get_rect(midright=(rect.right - 16, rect.centery - 12)))
        self.screen.blit(lines_s, lines_s.get_rect(midright=(rect.right - 16, rect.centery + 12)))

        # Kontrol etiketi (minimal)
        ctrl_color = tuple(int(c * 0.75) for c in skin.text_color[:3])
        ctrl = self.font_small.render(controls_label, True, ctrl_color)
        self.screen.blit(ctrl, ctrl.get_rect(bottomleft=(rect.x + 16, rect.bottom - 10)))
    
    def load_background_image(self):
        """Arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_pvp_main', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.background.load_image(custom_bg):
                print(f"✨ Özel PvP ana arka plan yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - PyInstaller için resource_path kullan
        # Varsayılan: outer_backgrounds/outer_background (PvP ana arka plan)
        possible_paths = [
            resource_path('backgrounds/outer_backgrounds.png'),
            resource_path('backgrounds/outer_background.png'),
            resource_path('backgrounds/outer_background.jpg'),
            resource_path('backgrounds/background.png'),
            resource_path('backgrounds/background.jpg'),
            resource_path('backgrounds/anime_bg.png'),
            resource_path('backgrounds/waifu.png'),
        ]
        
        for path in possible_paths:
            if self.background.load_image(path):
                print(f"✨ PvP Arka plan yüklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ PvP için arka plan resmi bulunamadı. backgrounds/ klasörüne resim ekleyin!")
    
    def load_board_background(self):
        """Quadrix oyun alanları için ayrı arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_pvp_board', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.board_background.load_image(custom_bg):
                print(f"✨ Özel PvP oyun alanı arka planı yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - Quadrix alanları için ayrı arka plan
        # Varsayılan: game_background (oyun alanı)
        possible_paths = [
            resource_path('backgrounds/game_background.png'),
            resource_path('backgrounds/game_background.jpg'),
            resource_path('backgrounds/board_background.png'),
            resource_path('backgrounds/board_background.jpg'),
            resource_path('backgrounds/board_bg.png'),
            resource_path('backgrounds/tetris_bg.png'),
            resource_path('backgrounds/game_bg.jpg'),
        ]
        
        for path in possible_paths:
            if self.board_background.load_image(path):
                print(f"✨ Quadrix alanlari icin arka plan yuklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ Quadrix alanlari icin ayri arka plan bulunamadi (opsiyonel)")
    
    def update_transparency(self, value):
        """Transparanlık ayarını güncelle.

        Amaç: menülerdeki ve oyun alanlarındaki transparanlık aynı davransın.
        """
        if self.board_background:
            self.board_background.set_transparency(value)
            print(f"🎨 PvP board background transparanlığı güncellendi: %{int(value * 100)}")
        if getattr(self, 'background', None) is not None:
            try:
                self.background.set_transparency(value)
            except Exception:
                pass
    
    def generate_pieces(self, count: int) -> None:
        """Torba (bag) sistemiyle önceden belirlenmiş parça sırası oluştur.

        Pool'daki her parça tipinden ``_bag_copies`` (3) kadar kopya bir torbaya
        atılıp karıştırılır.  İstenen ``count`` kadar parça üretilene kadar
        torbalar oluşturulmaya devam eder.  Üst üste aynı parça sınırı korunur.
        """
        if not hasattr(self, '_max_consecutive_same_piece'):
            self._max_consecutive_same_piece = 3
        if not hasattr(self, '_last_piece_index'):
            self._last_piece_index = None
        if not hasattr(self, '_last_piece_streak'):
            self._last_piece_streak = 0

        limit = int(getattr(self, '_max_consecutive_same_piece', 3) or 3)
        total = len(SHAPES)
        bag_copies = 3  # Her parça tipinden kaç kopya

        generated = 0
        while generated < count:
            # Yeni torba oluştur: her indeksten bag_copies kadar kopya
            bag: list[int] = list(range(total)) * bag_copies
            random.shuffle(bag)

            for piece_index in bag:
                # Üst üste aynı parça sınırını kontrol et
                if (
                    self._last_piece_index is not None
                    and piece_index == self._last_piece_index
                    and int(getattr(self, '_last_piece_streak', 0) or 0) >= limit
                    and total > 1
                ):
                    # Bu parçayı atla - torbadaki sonrakine geç
                    continue

                if piece_index == self._last_piece_index:
                    self._last_piece_streak = int(getattr(self, '_last_piece_streak', 0) or 0) + 1
                else:
                    self._last_piece_index = piece_index
                    self._last_piece_streak = 1

                self.piece_sequence.append(piece_index)
                generated += 1
                if generated >= count:
                    break
    
    def get_next_piece(self):
        """Sıradaki parçayı al (her iki oyuncu için aynı)"""
        if self.current_piece_index >= len(self.piece_sequence):
            self.generate_pieces(50)
        
        piece_index = self.piece_sequence[self.current_piece_index]
        self.current_piece_index += 1
        piece = Piece(x=3, y=0, shape_index=piece_index)

        # Tema + blok stili uygula
        self._apply_block_style(piece)
        
        return piece
    
    def handle_input(self):
        """Kullanıcı girdilerini işle"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.VIDEORESIZE:
                req_w = max(event.w, 800)
                req_h = max(event.h, 600)
                self.screen = create_display(req_w, req_h, fullscreen=False, resizable=True)
                # Daima surface'tan gerçek piksel boyutunu al
                self.window_width = self.screen.get_width()
                self.window_height = self.screen.get_height()
                self._vs_panel_dirty = True
                self.calculate_board_positions()
                continue

            # Çıkış onayı açıksa tüm input'u burada yakala
            if getattr(self, 'show_exit_prompt', False) and not getattr(self, 'name_input_active', False):
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        self.show_exit_prompt = False
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_y):
                        return 'menu'
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    if self.exit_yes_rect and self.exit_yes_rect.collidepoint(pos):
                        try:
                            self.sound.play('click')
                        except Exception:
                            pass
                        return 'menu'
                    if self.exit_no_rect and self.exit_no_rect.collidepoint(pos):
                        try:
                            self.sound.play('move')
                        except Exception:
                            pass
                        self.show_exit_prompt = False
                    continue

                # Diğer event'leri yut
                continue

            # Duraklatılmışsa mouse kontrollerini işle (tek oyunculu ile aynı)
            if self.paused and not self.game_over and event.type in (pygame.MOUSEMOTION, pygame.MOUSEWHEEL, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                pause_action = self._handle_pause_menu_input(event)
                if pause_action == 'resume':
                    self.paused = False
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.unduck_music()
                elif pause_action == 'main_menu':
                    return 'menu'
                continue
            
            # İsim girişi/mod seçimi ekranında fare desteği
            if self.name_input_active and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                mouse_action = self._handle_setup_mouse_click(pos)
                if mouse_action:
                    continue
            
            if event.type == pygame.KEYDOWN:
                controls1 = self.pvp_controls['player1']
                controls2 = self.pvp_controls['player2']
                # İsim girişi ekranındayken
                if self.name_input_active:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'  # Ana menüye dön
                    
                    if self.current_input == 1:
                        if event.key == pygame.K_RETURN and len(self.player1_name) > 0:
                            self.current_input = 2
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_BACKSPACE:
                            self.player1_name = self.player1_name[:-1]
                            self._vs_panel_dirty = True
                        elif len(self.player1_name) < 12 and event.unicode.isprintable():
                            self.player1_name += event.unicode
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 2:
                        if event.key == pygame.K_RETURN and len(self.player2_name) > 0:
                            self.current_input = 3  # Mod seçimine geç
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_BACKSPACE:
                            self.player2_name = self.player2_name[:-1]
                            self._vs_panel_dirty = True
                        elif len(self.player2_name) < 12 and event.unicode.isprintable():
                            self.player2_name += event.unicode
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 3:
                        # Mod seçimi: Sol/Sağ ok ile değiştir
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            self.match_mode = 'endless' if self.match_mode == 'timed' else 'timed'
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RETURN:
                            if self.match_mode == 'timed':
                                self.current_input = 4  # Süre ayarına geç
                            else:
                                # Süresiz mod - direkt oyuna başla
                                self.name_input_active = False
                                self._vs_panel_dirty = True
                                self.match_active = False
                                self.match_elapsed_ms = 0
                                self.match_end_reason = None
                                self._last_timer_seconds = None
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_input = 2  # Geri dön
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 4:
                        # Süre ayarı: Sol/Sağ ok ile değiştir (1-10 dakika)
                        if event.key == pygame.K_LEFT:
                            self.custom_duration_minutes = max(1, self.custom_duration_minutes - 1)
                            self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RIGHT:
                            self.custom_duration_minutes = min(10, self.custom_duration_minutes + 1)
                            self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RETURN:
                            # Oyuna başla
                            self.name_input_active = False
                            self._vs_panel_dirty = True
                            self.match_active = False
                            self.match_elapsed_ms = 0
                            self.match_end_reason = None
                            self._last_timer_seconds = None
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_input = 3  # Mod seçimine geri dön
                            self._vs_panel_dirty = True
                    continue
                
                # P - Duraklat
                if event.key == self.pvp_controls['pause']:
                    self.paused = not self.paused
                    if self.paused:
                        self.pause_menu_selected = 0
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.duck_music()
                    else:
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                    continue

                # Duraklatılmışsa menü kontrollerini işle
                if self.paused:
                    pause_action = self._handle_pause_menu_input(event)
                    if pause_action == 'resume':
                        self.paused = False
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                    elif pause_action == 'main_menu':
                        return 'menu'
                    continue

                # Game over iken ESC - ana menüye dön
                if self.game_over and event.key == pygame.K_ESCAPE:
                    return 'menu'

                # Oyun sırasında ESC - pause menüsünü aç
                if event.key == pygame.K_ESCAPE:
                    self.paused = True
                    self.pause_menu_selected = 0
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.duck_music()
                    continue
                
                if self.game_over:
                    if event.key == pygame.K_r:
                        self.restart(preserve_session=True)
                    continue
                
                if self.paused:
                    continue
                
                # OYUNCU 1 KONTROLLER (WASD + Shift/Ctrl)
                if not self.board1.is_game_over():
                    # A - Sol (DAS ile)
                    if event.key == controls1['move_left']:
                        moved = self._try_move_left_p1()
                        if moved:
                            self.sound.play('move')
                        self.p1_das_direction = -1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    
                    # D - Sağ (DAS ile)
                    elif event.key == controls1['move_right']:
                        moved = self._try_move_right_p1()
                        if moved:
                            self.sound.play('move')
                        self.p1_das_direction = 1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    
                    # S - Aşağı (soft drop) - tuşa basılınca hızlı düş
                    elif event.key == controls1['soft_drop']:
                        self.p1_soft_drop_active = True
                        self.p1_soft_drop_timer = 0
                        # İlk hareketi hemen yap
                        self.current_piece1.y += 1
                        if not self.board1.is_valid_position(self.current_piece1):
                            self.current_piece1.y -= 1
                    
                    # W - Döndür
                    elif event.key == controls1['rotate']:
                        original_x = self.current_piece1.x
                        self.current_piece1.rotate()
                        if not self.board1.is_valid_position(self.current_piece1):
                            for dx in [1, -1, 2, -2]:
                                self.current_piece1.x = original_x + dx
                                if self.board1.is_valid_position(self.current_piece1):
                                    break
                            else:
                                self.current_piece1.x = original_x
                                for _ in range(3):
                                    self.current_piece1.rotate()
                        self.sound.play('rotate')
                    
                    # Shift - Hard drop
                    elif event.key == controls1['hard_drop']:
                        start_y = self.current_piece1.y
                        drop_distance = 0
                        
                        while self.board1.is_valid_position(self.current_piece1, dy=1):
                            self.current_piece1.y += 1
                            drop_distance += 1

                        if self.effects_enabled and drop_distance > 0:
                            self._create_drop_trail(
                                1,
                                self.current_piece1,
                                self.p1_offset_x,
                                self.p1_offset_y,
                                self.cell_size,
                                start_y,
                                drop_distance,
                                trail_type='hard',
                            )
                        
                        self.lock_and_new_piece(1)
                        self.sound.play('drop')
                
                # OYUNCU 2 KONTROLLER (Ok tuşları + Space)
                if not self.board2.is_game_over():
                    # Sol ok (DAS ile)
                    if event.key == controls2['move_left']:
                        moved = self._try_move_left_p2()
                        if moved:
                            self.sound.play('move')
                        self.p2_das_direction = -1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    
                    # Sağ ok (DAS ile)
                    elif event.key == controls2['move_right']:
                        moved = self._try_move_right_p2()
                        if moved:
                            self.sound.play('move')
                        self.p2_das_direction = 1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    
                    # Aşağı ok - tuşa basılınca hızlı düş
                    elif event.key == controls2['soft_drop']:
                        self.p2_soft_drop_active = True
                        self.p2_soft_drop_timer = 0
                        # İlk hareketi hemen yap
                        self.current_piece2.y += 1
                        if not self.board2.is_valid_position(self.current_piece2):
                            self.current_piece2.y -= 1
                    
                    # Yukarı ok - Döndür
                    elif event.key == controls2['rotate']:
                        original_x = self.current_piece2.x
                        self.current_piece2.rotate()
                        if not self.board2.is_valid_position(self.current_piece2):
                            for dx in [1, -1, 2, -2]:
                                self.current_piece2.x = original_x + dx
                                if self.board2.is_valid_position(self.current_piece2):
                                    break
                            else:
                                self.current_piece2.x = original_x
                                for _ in range(3):
                                    self.current_piece2.rotate()
                        self.sound.play('rotate')
                    
                    # Space - Hard drop
                    elif event.key == controls2['hard_drop']:
                        start_y = self.current_piece2.y
                        drop_distance = 0
                        
                        while self.board2.is_valid_position(self.current_piece2, dy=1):
                            self.current_piece2.y += 1
                            drop_distance += 1

                        if self.effects_enabled and drop_distance > 0:
                            self._create_drop_trail(
                                2,
                                self.current_piece2,
                                self.p2_offset_x,
                                self.p2_offset_y,
                                self.cell_size,
                                start_y,
                                drop_distance,
                                trail_type='hard',
                            )
                        
                        self.lock_and_new_piece(2)
                        self.sound.play('drop')
            
            # Game over ekranında mouse tıklama kontrolü
            if self.game_over and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                # Peek butonu kontrolü
                peek_rect = getattr(self, '_game_over_peek_rect', None)
                if peek_rect and peek_rect.collidepoint(pos):
                    self._game_over_peek_active = not getattr(self, '_game_over_peek_active', False)
                elif not getattr(self, '_game_over_peek_active', False):
                    if self._game_over_restart_rect and self._game_over_restart_rect.collidepoint(pos):
                        self.sound.play('click')
                        self.restart(preserve_session=True)
                    elif self._game_over_menu_rect and self._game_over_menu_rect.collidepoint(pos):
                        self.sound.play('click')
                        return 'menu'
            
            # Tuş bırakıldığında DAS'ı ve soft drop'u durdur
            if event.type == pygame.KEYUP:
                controls1 = self.pvp_controls['player1']
                controls2 = self.pvp_controls['player2']
                # Oyuncu 1
                if event.key == controls1['move_left']:
                    if self.p1_das_direction == -1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls1['move_right']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_right_p1()
                            if moved:
                                self.sound.play('move')
                            self.p1_das_direction = 1
                            self.p1_das_timer = 0
                            self.p1_das_repeat_timer = 0
                            self.p1_das_charged = False
                        else:
                            self.p1_das_direction = 0
                            self.p1_das_charged = False
                elif event.key == controls1['move_right']:
                    if self.p1_das_direction == 1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls1['move_left']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_left_p1()
                            if moved:
                                self.sound.play('move')
                            self.p1_das_direction = -1
                            self.p1_das_timer = 0
                            self.p1_das_repeat_timer = 0
                            self.p1_das_charged = False
                        else:
                            self.p1_das_direction = 0
                            self.p1_das_charged = False
                elif event.key == controls1['soft_drop']:
                    self.p1_soft_drop_active = False
                # Oyuncu 2
                elif event.key == controls2['move_left']:
                    if self.p2_das_direction == -1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls2['move_right']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_right_p2()
                            if moved:
                                self.sound.play('move')
                            self.p2_das_direction = 1
                            self.p2_das_timer = 0
                            self.p2_das_repeat_timer = 0
                            self.p2_das_charged = False
                        else:
                            self.p2_das_direction = 0
                            self.p2_das_charged = False
                elif event.key == controls2['move_right']:
                    if self.p2_das_direction == 1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls2['move_left']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_left_p2()
                            if moved:
                                self.sound.play('move')
                            self.p2_das_direction = -1
                            self.p2_das_timer = 0
                            self.p2_das_repeat_timer = 0
                            self.p2_das_charged = False
                        else:
                            self.p2_das_direction = 0
                            self.p2_das_charged = False
                elif event.key == controls2['soft_drop']:
                    self.p2_soft_drop_active = False
        
        return True

    def _handle_pause_menu_input(self, event):
        """Duraklama menüsü girdilerini işle (tek oyunculu ile aynı davranış)."""

        def apply_option(option: str):
            if option == 'resume':
                return 'resume'
            if option == 'music':
                self.sound.music_enabled = not self.sound.music_enabled
                if self.settings_manager:
                    self.settings_manager.set('music_enabled', self.sound.music_enabled)
                if self.sound.music_enabled:
                    # Müzik tekrar açıldıysa PvP playlist'ini başlat (shuffle/playlist korunur)
                    self._start_pvp_music()
                else:
                    self.sound.stop_music()
                return None
            if option == 'sound_effects':
                self.sound.sfx_enabled = not self.sound.sfx_enabled
                if self.settings_manager:
                    self.settings_manager.set('sound_enabled', self.sound.sfx_enabled)
                return None
            if option == 'main_menu':
                return 'main_menu'
            return None

        def adjust_volume(option: str, delta: float | None = None, absolute: float | None = None):
            if option == 'music_volume':
                if absolute is None:
                    target = self.sound.music_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_music_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('music_volume', new_vol)
            elif option == 'sfx_volume':
                if absolute is None:
                    target = self.sound.sfx_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('sfx_volume', new_vol)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.pause_menu_selected = (self.pause_menu_selected - 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key == pygame.K_DOWN:
                self.pause_menu_selected = (self.pause_menu_selected + 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                option = self.pause_menu_options[self.pause_menu_selected]
                return apply_option(option)
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                option = self.pause_menu_options[self.pause_menu_selected]
                delta = 0.1 if event.key == pygame.K_RIGHT else -0.1
                adjust_volume(option, delta=delta)
                return None
            if event.key == pygame.K_ESCAPE:
                return 'resume'
            # P tuşu pause toggle, menüde "Devam Et" gibi davransın
            if event.key == self.pvp_controls.get('pause'):
                return 'resume'
            return None

        if event.type == pygame.MOUSEWHEEL:
            option = self.pause_menu_options[self.pause_menu_selected]
            if option in ('music_volume', 'sfx_volume'):
                delta = 0.05 if event.y > 0 else -0.05
                adjust_volume(option, delta=delta)
            else:
                step = -1 if event.y > 0 else 1
                self.pause_menu_selected = (self.pause_menu_selected + step) % len(self.pause_menu_options)
                self.sound.play('move')
            return None

        if event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            if self._pause_vol_drag_active and self._pause_vol_drag_option:
                bar_rect = (getattr(self, '_pause_volume_rects', {}) or {}).get(self._pause_vol_drag_option)
                if bar_rect and bar_rect.width > 0:
                    ratio = (pos[0] - bar_rect.x) / bar_rect.width
                    adjust_volume(self._pause_vol_drag_option, absolute=max(0.0, min(1.0, ratio)))
                return None
            for idx, rect in enumerate(getattr(self, '_pause_option_rects', []) or []):
                if rect and rect.collidepoint(pos):
                    if idx != self.pause_menu_selected:
                        self.pause_menu_selected = idx
                    break
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            for idx, rect in enumerate(getattr(self, '_pause_option_rects', []) or []):
                if rect and rect.collidepoint(pos):
                    self.pause_menu_selected = idx
                    option = self.pause_menu_options[idx]
                    if option in ('music_volume', 'sfx_volume'):
                        bar_rect = (getattr(self, '_pause_volume_rects', {}) or {}).get(option)
                        if bar_rect and bar_rect.width > 0:
                            ratio = (pos[0] - bar_rect.x) / bar_rect.width
                            adjust_volume(option, absolute=max(0.0, min(1.0, ratio)))
                            self._pause_vol_drag_active = True
                            self._pause_vol_drag_option = option
                        return None
                    return apply_option(option)
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pause_vol_drag_active = False
            self._pause_vol_drag_option = ''
            return None

        return None

    def _draw_pause_menu(self):
        """Tek oyuncudaki duraklama menüsü panelini PvP'de çiz."""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(self._sx(520, ui_scale), width - self._sx(100, ui_scale))
        option_count = len(self.pause_menu_options)
        item_h = self._sx(56, ui_scale)
        gap = self._sx(10, ui_scale)
        top_pad = self._sx(78, ui_scale)
        bottom_pad = self._sx(64, ui_scale)
        panel_height = top_pad + option_count * item_h + (option_count - 1) * gap + bottom_pad
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=180, border_color=(*retro_style.accent, 140), glow=True)

        title_font = retro_style.get_font(self._sx(30, ui_scale, minimum=16), bold=True)
        title_surf = title_font.render(t('paused'), True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + self._sx(18, ui_scale)))

        self._pause_option_rects = []
        self._pause_volume_rects = {}
        _pause_mouse_pos = get_mouse_pos()

        start_y = panel_rect.y + top_pad
        for i, option in enumerate(self.pause_menu_options):
            y = start_y + i * (item_h + gap)
            button_rect = pygame.Rect(panel_rect.x + self._sx(22, ui_scale), y, panel_rect.width - self._sx(44, ui_scale), item_h)
            self._pause_option_rects.append(button_rect)

            is_selected = i == self.pause_menu_selected
            label = t(option)
            sub_text = None
            color_code = retro_style.primary

            if option == 'resume':
                color_code = retro_style.success
                sub_text = 'ENTER / P'
            elif option == 'main_menu':
                color_code = retro_style.secondary
                sub_text = 'ESC'
            elif option == 'music':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.music_enabled else t('off')
            elif option == 'sound_effects':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.sfx_enabled else t('off')
            elif option == 'music_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.music_volume * 100)}%  < >"
            elif option == 'sfx_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.sfx_volume * 100)}%  < >"

            _pv_hover = button_rect.collidepoint(_pause_mouse_pos)
            retro_style.draw_uniform_button(
                self.screen,
                button_rect,
                label,
                sub_text=sub_text,
                color_code=color_code,
                selected=is_selected,
                state='hover' if _pv_hover else 'normal',
            )

            if option == 'music_volume':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(
                    self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                    self.sound.music_volume, (0, 210, 255), int(self.sound.music_volume * 100),
                    is_selected, ui_scale,
                )
            elif option == 'sfx_volume':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(
                    self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                    self.sound.sfx_volume, (255, 185, 0), int(self.sound.sfx_volume * 100),
                    is_selected, ui_scale,
                )

        hint_font = retro_style.get_font(self._sx(16, ui_scale, minimum=10), bold=False)
        hint_surf = hint_font.render(t('pause_hint'), True, (150, 165, 190))
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - self._sx(16, ui_scale)))

    def _draw_game_over_screen(self):
        """Oyun sonu ekranı - Duraklama menüsüyle aynı estetik tema"""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale(min_scale=0.68, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # ============================================
        # PEEK MODU - Oyun alanını görmek için
        # ============================================
        if getattr(self, '_game_over_peek_active', False):
            # Peek modunda sadece sağ alt köşede göz butonu göster
            peek_btn_size = s(48)
            peek_btn_x = width - peek_btn_size - s(20)
            peek_btn_y = height - peek_btn_size - s(20)
            self._game_over_peek_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
            
            # Yuvarlak beyaz arka plan
            center = self._game_over_peek_rect.center
            radius = peek_btn_size // 2
            pygame.draw.circle(self.screen, (255, 255, 255), center, radius)
            pygame.draw.circle(self.screen, (100, 200, 255), center, radius, 2)
            
            # Göz ikonu - PNG ikon kullan
            peek_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'kart_secim_sagust.png')
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                peek_icon_path = os.path.join(sys._MEIPASS, 'assets', 'kart_secim_sagust.png')
            try:
                from asset_manager import load_image
                peek_icon = load_image(peek_icon_path)
                icon_size = int(peek_btn_size * 0.65)
                peek_icon = pygame.transform.smoothscale(peek_icon, (icon_size, icon_size))
                icon_rect = peek_icon.get_rect(center=self._game_over_peek_rect.center)
                self.screen.blit(peek_icon, icon_rect)
            except Exception:
                # Fallback: metin göster
                fallback_font = retro_style.get_font(s(20, minimum=12), bold=True)
                eye_surf = fallback_font.render("X", True, (100, 200, 255))
                self.screen.blit(eye_surf, eye_surf.get_rect(center=self._game_over_peek_rect.center))
            return
        
        # Yarı saydam karartma overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        
        # İsimler
        p1_name = (self.player1_name if self.player1_name else t('pvp_player1')).upper()
        p2_name = (self.player2_name if self.player2_name else t('pvp_player2')).upper()
        
        # Skorlar
        score1 = int(getattr(self.board1, 'score', 0) or 0)
        score2 = int(getattr(self.board2, 'score', 0) or 0)
        lines1 = int(getattr(self.board1, 'lines_cleared', 0) or 0)
        lines2 = int(getattr(self.board2, 'lines_cleared', 0) or 0)
        
        # Kazanan bilgisi
        if self.winner == 1:
            winner_name = p1_name
            winner_color = UIColors.NEON_CYAN
            loser_name = p2_name
        elif self.winner == 2:
            winner_name = p2_name
            winner_color = UIColors.NEON_MAGENTA
            loser_name = p1_name
        else:
            winner_name = None
            winner_color = UIColors.NEON_YELLOW
        
        # Panel boyutları
        panel_width = min(s(480), width - s(80))
        panel_height = s(380)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        
        # Cam panel çiz (duraklama menüsüyle aynı)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=200, border_color=(*winner_color[:3], 160), glow=True)
        
        # Göz butonu - panelin sağ üst köşesinde
        peek_btn_size = s(40)
        peek_btn_x = panel_rect.right - peek_btn_size - s(16)
        peek_btn_y = panel_rect.y + s(16)
        self._game_over_peek_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
        
        # Göz butonu arka planı - Yuvarlak beyaz
        mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
        peek_hovered = mouse_pos is not None and self._game_over_peek_rect.collidepoint(mouse_pos)
        center = self._game_over_peek_rect.center
        radius = peek_btn_size // 2
        pygame.draw.circle(self.screen, (255, 255, 255), center, radius)
        border_color_peek = (100, 200, 255) if peek_hovered else (180, 180, 200)
        pygame.draw.circle(self.screen, border_color_peek, center, radius, 2)
        
        # Göz ikonu - PNG ikon kullan
        peek_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'kart_secim_sagust.png')
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            peek_icon_path = os.path.join(sys._MEIPASS, 'assets', 'kart_secim_sagust.png')
        try:
            from asset_manager import load_image
            peek_icon = load_image(peek_icon_path)
            icon_size = int(peek_btn_size * 0.65)
            peek_icon = pygame.transform.smoothscale(peek_icon, (icon_size, icon_size))
            icon_rect = peek_icon.get_rect(center=self._game_over_peek_rect.center)
            self.screen.blit(peek_icon, icon_rect)
        except Exception:
            # Fallback: metin göster
            fallback_font = retro_style.get_font(s(16, minimum=10), bold=True)
            eye_surf = fallback_font.render("O", True, (100, 200, 255) if peek_hovered else (180, 180, 200))
            self.screen.blit(eye_surf, eye_surf.get_rect(center=self._game_over_peek_rect.center))
        
        # Bitiş nedeni (üstte küçük badge)
        reason_text = ''
        if getattr(self, 'match_end_reason', None) == 'time':
            reason_text = t('pvp_time_up')
        elif getattr(self, 'match_end_reason', None) == 'elimination':
            reason_text = t('pvp_top_out')
        
        if reason_text:
            reason_font = retro_style.get_font(s(18, minimum=11), bold=True)
            reason_surf = reason_font.render(reason_text, True, (180, 190, 210))
            self.screen.blit(reason_surf, reason_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + s(20)))
        
        # Kazanan başlığı
        title_y = panel_rect.y + s(55)
        if winner_name:
            title_font = retro_style.get_font(s(42, minimum=20), bold=True)
            title_surf = title_font.render(winner_name, True, winner_color)
            self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=title_y))
            
            subtitle_font = retro_style.get_font(s(22, minimum=12), bold=False)
            subtitle_surf = subtitle_font.render(t('pvp_wins'), True, (200, 210, 230))
            self.screen.blit(subtitle_surf, subtitle_surf.get_rect(centerx=panel_rect.centerx, top=title_y + s(50)))
        else:
            title_font = retro_style.get_font(s(42, minimum=20), bold=True)
            title_surf = title_font.render(t('pvp_draw'), True, winner_color)
            self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=title_y))
        
        # Ayırıcı çizgi
        line_y = title_y + s(90)
        pygame.draw.line(self.screen, (*winner_color[:3], 100), 
                (panel_rect.x + s(40), line_y), 
                (panel_rect.right - s(40), line_y), 2)
        
        # Skor kartları
        card_y = line_y + s(20)
        card_width = (panel_width - s(80)) // 2
        card_height = s(100)
        
        # Oyuncu 1 kartı
        p1_card = pygame.Rect(panel_rect.x + s(25), card_y, card_width, card_height)
        p1_border_color = UIColors.NEON_CYAN if self.winner == 1 else (80, 90, 110)
        pygame.draw.rect(self.screen, (30, 35, 50), p1_card, border_radius=10)
        pygame.draw.rect(self.screen, p1_border_color, p1_card, 2, border_radius=10)
        
        # Oyuncu 1 ismi
        p1_name_font = retro_style.get_font(s(18, minimum=11), bold=True)
        p1_name_surf = p1_name_font.render(p1_name, True, UIColors.NEON_CYAN)
        self.screen.blit(p1_name_surf, p1_name_surf.get_rect(centerx=p1_card.centerx, top=p1_card.y + s(10)))
        
        # Oyuncu 1 skor
        p1_score_font = retro_style.get_font(s(28, minimum=14), bold=True)
        p1_score_surf = p1_score_font.render(f'{score1:,}'.replace(',', '.'), True, (255, 255, 255))
        self.screen.blit(p1_score_surf, p1_score_surf.get_rect(centerx=p1_card.centerx, top=p1_card.y + s(35)))
        
        # Oyuncu 1 satır
        p1_lines_font = retro_style.get_font(s(16, minimum=10), bold=False)
        p1_lines_surf = p1_lines_font.render(f'{lines1} {t("pvp_lines_suffix")}', True, (150, 160, 180))
        self.screen.blit(p1_lines_surf, p1_lines_surf.get_rect(centerx=p1_card.centerx, top=p1_card.y + s(70)))
        
        # VS
        vs_font = retro_style.get_font(s(24, minimum=12), bold=True)
        vs_surf = vs_font.render('VS', True, (100, 110, 130))
        self.screen.blit(vs_surf, vs_surf.get_rect(center=(panel_rect.centerx, card_y + card_height // 2)))
        
        # Oyuncu 2 kartı
        p2_card = pygame.Rect(panel_rect.right - s(25) - card_width, card_y, card_width, card_height)
        p2_border_color = UIColors.NEON_MAGENTA if self.winner == 2 else (80, 90, 110)
        pygame.draw.rect(self.screen, (30, 35, 50), p2_card, border_radius=10)
        pygame.draw.rect(self.screen, p2_border_color, p2_card, 2, border_radius=10)
        
        # Oyuncu 2 ismi
        p2_name_surf = p1_name_font.render(p2_name, True, UIColors.NEON_MAGENTA)
        self.screen.blit(p2_name_surf, p2_name_surf.get_rect(centerx=p2_card.centerx, top=p2_card.y + s(10)))
        
        # Oyuncu 2 skor
        p2_score_surf = p1_score_font.render(f'{score2:,}'.replace(',', '.'), True, (255, 255, 255))
        self.screen.blit(p2_score_surf, p2_score_surf.get_rect(centerx=p2_card.centerx, top=p2_card.y + s(35)))
        
        # Oyuncu 2 satır
        p2_lines_surf = p1_lines_font.render(f'{lines2} {t("pvp_lines_suffix")}', True, (150, 160, 180))
        self.screen.blit(p2_lines_surf, p2_lines_surf.get_rect(centerx=p2_card.centerx, top=p2_card.y + s(70)))
        
        # Fark bilgisi (kazanan varsa)
        if self.winner and self.winner != 'draw':
            diff_y = card_y + card_height + s(15)
            diff_lines = abs(lines1 - lines2)
            diff_score = abs(score1 - score2)
            
            diff_font = retro_style.get_font(s(16, minimum=10), bold=True)
            diff_text = f'+{diff_score:,} {t("pvp_points_diff")}  •  +{diff_lines} {t("pvp_lines_diff")}'.replace(',', '.')
            diff_surf = diff_font.render(diff_text, True, winner_color)
            self.screen.blit(diff_surf, diff_surf.get_rect(centerx=panel_rect.centerx, top=diff_y))
        
        # Alt butonlar
        button_y = panel_rect.bottom - s(70)
        button_width = s(180)
        button_height = s(44)
        button_gap = s(20)
        
        # Mouse pozisyonu al (hover efekti için)
        mouse_pos = get_mouse_pos()
        
        # Yeniden oyna butonu
        restart_rect = pygame.Rect(panel_rect.centerx - button_width - button_gap // 2, button_y, button_width, button_height)
        restart_hover = restart_rect.collidepoint(mouse_pos)
        retro_style.draw_uniform_button(
            self.screen, restart_rect, t('pvp_restart'), sub_text='R',
            color_code=retro_style.success, selected=restart_hover
        )
        self._game_over_restart_rect = restart_rect
        
        # Menüye dön butonu
        menu_rect = pygame.Rect(panel_rect.centerx + button_gap // 2, button_y, button_width, button_height)
        menu_hover = menu_rect.collidepoint(mouse_pos)
        retro_style.draw_uniform_button(
            self.screen, menu_rect, t('main_menu'), sub_text='ESC',
            color_code=retro_style.secondary, selected=menu_hover
        )
        self._game_over_menu_rect = menu_rect
    
    def _try_move_left_p1(self):
        """Oyuncu 1 sola hareket"""
        if self.current_piece1 is None:
            return False
        self.current_piece1.x -= 1
        if not self.board1.is_valid_position(self.current_piece1):
            self.current_piece1.x += 1
            return False
        return True
    
    def _try_move_right_p1(self):
        """Oyuncu 1 sağa hareket"""
        if self.current_piece1 is None:
            return False
        self.current_piece1.x += 1
        if not self.board1.is_valid_position(self.current_piece1):
            self.current_piece1.x -= 1
            return False
        return True
    
    def _try_move_left_p2(self):
        """Oyuncu 2 sola hareket"""
        if self.current_piece2 is None:
            return False
        self.current_piece2.x -= 1
        if not self.board2.is_valid_position(self.current_piece2):
            self.current_piece2.x += 1
            return False
        return True
    
    def _try_move_right_p2(self):
        """Oyuncu 2 sağa hareket"""
        if self.current_piece2 is None:
            return False
        self.current_piece2.x += 1
        if not self.board2.is_valid_position(self.current_piece2):
            self.current_piece2.x -= 1
            return False
        return True
    
    def _update_das(self, delta_time):
        """Her iki oyuncu için DAS güncelle"""
        try:
            delay_ms = float(self.settings_manager.get('das_delay', DAS_DELAY)) if self.settings_manager else float(DAS_DELAY)
        except Exception:
            delay_ms = float(DAS_DELAY)
        try:
            repeat_ms = float(self.settings_manager.get('das_repeat', DAS_REPEAT)) if self.settings_manager else float(DAS_REPEAT)
        except Exception:
            repeat_ms = float(DAS_REPEAT)
        delay_ms = max(0.0, delay_ms)
        repeat_ms = max(1.0, repeat_ms)
        
        # Oyuncu 1 DAS
        if self.p1_das_direction != 0 and self.current_piece1 and not self.board1.is_game_over():
            self.p1_das_timer += delta_time
            if not self.p1_das_charged:
                if self.p1_das_timer >= delay_ms:
                    overshoot = max(0.0, self.p1_das_timer - delay_ms)
                    self.p1_das_charged = True
                    self.p1_das_repeat_timer = overshoot
                    if self.p1_das_direction == -1:
                        if self._try_move_left_p1():
                            self.sound.play('move')
                    elif self.p1_das_direction == 1:
                        if self._try_move_right_p1():
                            self.sound.play('move')
            else:
                self.p1_das_repeat_timer += delta_time
                while self.p1_das_repeat_timer >= repeat_ms:
                    self.p1_das_repeat_timer -= repeat_ms
                    if self.p1_das_direction == -1:
                        if self._try_move_left_p1():
                            self.sound.play('move')
                        else:
                            self.p1_das_repeat_timer = 0
                            break
                    elif self.p1_das_direction == 1:
                        if self._try_move_right_p1():
                            self.sound.play('move')
                        else:
                            self.p1_das_repeat_timer = 0
                            break
        
        # Oyuncu 2 DAS
        if self.p2_das_direction != 0 and self.current_piece2 and not self.board2.is_game_over():
            self.p2_das_timer += delta_time
            if not self.p2_das_charged:
                if self.p2_das_timer >= delay_ms:
                    overshoot = max(0.0, self.p2_das_timer - delay_ms)
                    self.p2_das_charged = True
                    self.p2_das_repeat_timer = overshoot
                    if self.p2_das_direction == -1:
                        if self._try_move_left_p2():
                            self.sound.play('move')
                    elif self.p2_das_direction == 1:
                        if self._try_move_right_p2():
                            self.sound.play('move')
            else:
                self.p2_das_repeat_timer += delta_time
                while self.p2_das_repeat_timer >= repeat_ms:
                    self.p2_das_repeat_timer -= repeat_ms
                    if self.p2_das_direction == -1:
                        if self._try_move_left_p2():
                            self.sound.play('move')
                        else:
                            self.p2_das_repeat_timer = 0
                            break
                    elif self.p2_das_direction == 1:
                        if self._try_move_right_p2():
                            self.sound.play('move')
                        else:
                            self.p2_das_repeat_timer = 0
                            break
    
    def _update_soft_drop(self, delta_time):
        """Her iki oyuncu için soft drop (hızlı düşüş) güncelle"""
        # Oyuncu 1 soft drop
        if self.p1_soft_drop_active and self.current_piece1 and not self.board1.is_game_over():
            self.p1_soft_drop_timer += delta_time
            if self.p1_soft_drop_timer >= self.soft_drop_speed:
                self.p1_soft_drop_timer = 0
                self.current_piece1.y += 1
                if not self.board1.is_valid_position(self.current_piece1):
                    self.current_piece1.y -= 1
                    # Alt sınıra ulaştı, parçayı kilitle
                    self.lock_and_new_piece(1)
                    self.p1_soft_drop_active = False
        
        # Oyuncu 2 soft drop
        if self.p2_soft_drop_active and self.current_piece2 and not self.board2.is_game_over():
            self.p2_soft_drop_timer += delta_time
            if self.p2_soft_drop_timer >= self.soft_drop_speed:
                self.p2_soft_drop_timer = 0
                self.current_piece2.y += 1
                if not self.board2.is_valid_position(self.current_piece2):
                    self.current_piece2.y -= 1
                    # Alt sınıra ulaştı, parçayı kilitle
                    self.lock_and_new_piece(2)
                    self.p2_soft_drop_active = False
    
    def trigger_screen_shake(self, intensity=10, duration=15):
        """Ekran titremesi efekti başlat"""
        if not self._particle_effects_enabled():
            return
        self.shake_intensity = intensity
        self.screen_shake = duration

    def create_particles(self, count, x, y, colors, speed=5):
        """Genel amaçlı parçacık oluşturucu"""
        if not self._particle_effects_enabled():
            return
        
        for _ in range(count):
            angle = random.uniform(0, 2 * 3.14159)
            s = random.uniform(speed * 0.5, speed * 1.5)
            
            # Yukarı doğru hafif eğim
            vx = math.cos(angle) * s
            vy = math.sin(angle) * s - (speed * 0.2)
            
            self.particles.append({
                'x': float(x),
                'y': float(y),
                'vx': vx,
                'vy': vy,
                'life': random.randint(30, 60),
                'max_life': 60,
                'color': random.choice(colors),
                'size': random.randint(3, 6),
                'glow': True
            })

    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size, board=None):
        """Satır temizlendiğinde parçacık efektleri"""
        if not self._particle_effects_enabled():
            return
        
        sparkle_colors = [
            (255, 255, 255), (255, 255, 200), (255, 215, 0),
            (0, 255, 255), (255, 100, 255)
        ]
        
        for row in cleared_rows:
            for col in range(BOARD_WIDTH):
                cell_x = board_offset_x + col * cell_size + cell_size // 2
                cell_y = board_offset_y + row * cell_size + cell_size // 2
                
                cell_color = random.choice(sparkle_colors)
                # Renk bilgisi board'dan alınıyorsa
                if board and hasattr(board, 'last_cleared_colors') and row in board.last_cleared_colors:
                    try:
                        row_colors = board.last_cleared_colors[row]
                        if col < len(row_colors) and row_colors[col] != BLACK:
                            cell_color = row_colors[col]
                    except Exception:
                        pass
                
                # Her hücre için parçacıklar
                for _ in range(random.randint(4, 7)):
                    speed = random.uniform(4, 8)
                    vx = speed * random.uniform(-1, 1)
                    vy = speed * random.uniform(-1, 0.5) - 2
                    
                    self.particles.append({
                        'x': float(cell_x + random.randint(-5, 5)),
                        'y': float(cell_y + random.randint(-5, 5)),
                        'vx': vx,
                        'vy': vy,
                        'life': random.randint(40, 80),
                        'max_life': 80,
                        'color': cell_color,
                        'size': random.randint(3, 5),
                        'glow': True
                    })

    def lock_and_new_piece(self, player):
        """Parçayı kilitle ve yeni parça oluştur"""
        if player == 1:
            if self.effects_enabled:
                color_matrix = getattr(self.current_piece1, 'color_matrix', None)
                for row_i, row in enumerate(self.current_piece1.shape):
                    for col_i, cell in enumerate(row):
                        if not cell:
                            continue
                        board_col = self.current_piece1.x + col_i
                        board_row = self.current_piece1.y + row_i
                        if not (0 <= board_col < BOARD_WIDTH and 0 <= board_row < BOARD_HEIGHT):
                            continue
                        cell_color = self.current_piece1.color
                        if color_matrix is not None:
                            try:
                                matrix_color = color_matrix[row_i][col_i]
                                if matrix_color is not None:
                                    cell_color = matrix_color
                            except Exception:
                                pass
                        screen_x = self.p1_offset_x + board_col * self.cell_size + self.cell_size // 2
                        screen_y = self.p1_offset_y + board_row * self.cell_size + self.cell_size // 2
                        self.create_lock_explosion(screen_x, screen_y, cell_color, cell_size=self.cell_size)
            
            lines = self.board1.lock_piece(self.current_piece1)
            self._mark_locked_board_dirty(1)
            
            if lines > 0:
                # Gelişmiş satır temizleme efektleri (ana oyundaki gibi)
                if self.board1.last_cleared_lines and self.effects_enabled:
                    cleared_rows = list(self.board1.last_cleared_lines)
                    self.p1_line_flash_rows = cleared_rows
                    self.p1_line_flash_timer = 20  # Ana oyunla aynı
                    self.p1_line_glow_alpha = 255
                    self.p1_line_sweep_rows = cleared_rows
                    self.p1_line_sweep_progress = 0.0
                    self.p1_line_sweep_active = True
                    
                    # Parçacık efektleri (ana oyundaki gelişmiş versiyon)
                    self.create_line_clear_particles(
                        cleared_rows, 
                        self.p1_offset_x, 
                        self.p1_offset_y, 
                        self.cell_size,
                        board=self.board1
                    )
                    
                    # Dalga efektleri - her satır için (ana oyunla aynı parametreler)
                    for row in cleared_rows:
                        wave_y = self.p1_offset_y + row * self.cell_size + self.cell_size // 2
                        wave_x = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
                        self.p1_wave_effects.append({
                            'x': wave_x,
                            'y': wave_y,
                            'radius': 0,
                            'max_radius': BOARD_WIDTH * self.cell_size,
                            'alpha': 200,
                            'color': (255, 255, 255),  # Beyaz - ana oyunla aynı
                            'speed': 15  # Ana oyunla aynı hız
                        })
                    
                    # Ekran titremesi (ana oyunla aynı)
                    if lines < 4:
                        self.trigger_screen_shake(intensity=3 + lines * 2, duration=8)
                    self._start_block_fall_animation(1, self.board1, cleared_rows)
                
                self.sound.play('line' if lines < 4 else 'tetris')
                
                # Quadrix için özel efekt (ana oyunla aynı)
                if lines == 4 and self.effects_enabled:
                    center_x = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
                    center_y = self.p1_offset_y + (BOARD_HEIGHT * self.cell_size) // 2
                    self.create_particles(
                        count=150,
                        x=center_x,
                        y=center_y,
                        colors=[YELLOW, ORANGE, (255, 215, 0), CYAN],
                        speed=10
                    )
                    self.trigger_screen_shake(intensity=15, duration=20)
            
            self.current_piece1 = self.next_piece1
            self.next_piece1 = self.get_next_piece()
            
            if not self.board1.is_valid_position(self.current_piece1):
                # Oyuncu 1 öldü - Oyun devam eder, sadece işaretle
                print("🔴 Oyuncu 1 öldü! Oyuncu 2 devam ediyor...")
                self.p1_eliminated = True
                # Tek taraf elendiyse maç biter
                if not self.p2_eliminated:
                    self.winner = 2
                    self.game_over = True
                    self.match_end_reason = 'elimination'
                    self.sound.play('gameover')
                    return
                # İki oyuncu da öldüyse kazananı belirle
                if self.board2.is_game_over():
                    self.determine_winner()
        
        else:  # player == 2
            if self.effects_enabled:
                color_matrix = getattr(self.current_piece2, 'color_matrix', None)
                for row_i, row in enumerate(self.current_piece2.shape):
                    for col_i, cell in enumerate(row):
                        if not cell:
                            continue
                        board_col = self.current_piece2.x + col_i
                        board_row = self.current_piece2.y + row_i
                        if not (0 <= board_col < BOARD_WIDTH and 0 <= board_row < BOARD_HEIGHT):
                            continue
                        cell_color = self.current_piece2.color
                        if color_matrix is not None:
                            try:
                                matrix_color = color_matrix[row_i][col_i]
                                if matrix_color is not None:
                                    cell_color = matrix_color
                            except Exception:
                                pass
                        screen_x = self.p2_offset_x + board_col * self.cell_size + self.cell_size // 2
                        screen_y = self.p2_offset_y + board_row * self.cell_size + self.cell_size // 2
                        self.create_lock_explosion(screen_x, screen_y, cell_color, cell_size=self.cell_size)
            
            lines = self.board2.lock_piece(self.current_piece2)
            self._mark_locked_board_dirty(2)
            
            if lines > 0:
                # Gelişmiş satır temizleme efektleri (ana oyundaki gibi)
                if self.board2.last_cleared_lines and self.effects_enabled:
                    cleared_rows = list(self.board2.last_cleared_lines)
                    self.p2_line_flash_rows = cleared_rows
                    self.p2_line_flash_timer = 20  # Ana oyunla aynı
                    self.p2_line_glow_alpha = 255
                    self.p2_line_sweep_rows = cleared_rows
                    self.p2_line_sweep_progress = 0.0
                    self.p2_line_sweep_active = True
                    
                    # Parçacık efektleri (ana oyundaki gelişmiş versiyon)
                    self.create_line_clear_particles(
                        cleared_rows, 
                        self.p2_offset_x, 
                        self.p2_offset_y, 
                        self.cell_size,
                        board=self.board2
                    )
                    
                    # Dalga efektleri - her satır için (ana oyunla aynı parametreler)
                    for row in cleared_rows:
                        wave_y = self.p2_offset_y + row * self.cell_size + self.cell_size // 2
                        wave_x = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
                        self.p2_wave_effects.append({
                            'x': wave_x,
                            'y': wave_y,
                            'radius': 0,
                            'max_radius': BOARD_WIDTH * self.cell_size,
                            'alpha': 200,
                            'color': (255, 255, 255),  # Beyaz - ana oyunla aynı
                            'speed': 15  # Ana oyunla aynı hız
                        })
                    
                    # Ekran titremesi (ana oyunla aynı)
                    if lines < 4:
                        self.trigger_screen_shake(intensity=3 + lines * 2, duration=8)
                    self._start_block_fall_animation(2, self.board2, cleared_rows)
                
                self.sound.play('line' if lines < 4 else 'tetris')
                
                # Quadrix için özel efekt (ana oyunla aynı)
                if lines == 4 and self.effects_enabled:
                    center_x = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
                    center_y = self.p2_offset_y + (BOARD_HEIGHT * self.cell_size) // 2
                    self.create_particles(
                        count=150,
                        x=center_x,
                        y=center_y,
                        colors=[YELLOW, ORANGE, (255, 215, 0), MAGENTA],
                        speed=10
                    )
                    self.trigger_screen_shake(intensity=15, duration=20)
            
            self.current_piece2 = self.next_piece2
            self.next_piece2 = self.get_next_piece()
            
            if not self.board2.is_valid_position(self.current_piece2):
                # Oyuncu 2 öldü - Oyun devam eder, sadece işaretle
                print("🔴 Oyuncu 2 öldü! Oyuncu 1 devam ediyor...")
                self.p2_eliminated = True
                if not self.p1_eliminated:
                    self.winner = 1
                    self.game_over = True
                    self.match_end_reason = 'elimination'
                    self.sound.play('gameover')
                    return
                # İki oyuncu da öldüyse kazananı belirle
                if self.board1.is_game_over():
                    self.determine_winner()
    
    def determine_winner(self):
        """Kazananı belirle.

        Mantık:
        - Tek oyuncu elendiyse diğer oyuncu kazanır.
        - Süre bittiyse (kimse yanmadıysa) skor karşılaştırması yapılır.
        - İki oyuncu da elendiyse skor karşılaştırması yapılır.
        """
        score1 = int(getattr(self.board1, 'score', 0) or 0)
        score2 = int(getattr(self.board2, 'score', 0) or 0)
        lines1 = int(getattr(self.board1, 'lines_cleared', 0) or 0)
        lines2 = int(getattr(self.board2, 'lines_cleared', 0) or 0)

        # Süreli modda süre bittiğinde: satır sayısını önemseme, sadece skor.
        if getattr(self, 'match_end_reason', None) == 'time':
            if score1 > score2:
                self.winner = 1
                print(f"🏆 Oyuncu 1 KAZANDI! (Süre bitti, Skor: {score1} vs {score2})")
            elif score2 > score1:
                self.winner = 2
                print(f"🏆 Oyuncu 2 KAZANDI! (Süre bitti, Skor: {score2} vs {score1})")
            else:
                self.winner = 'draw'
                print(f"🤝 BERABERE! (Süre bitti, Skor: {score1}-{score2})")

            self.game_over = True
            self.sound.play('gameover')

            # Kullanıcı istatistiklerini güncelle
            if self.user_manager:
                if self.winner == 1:
                    self.user_manager.update_pvp_stats(win=True)
                    print(f"💾 PvP istatistikleri güncellendi: KAZANDI")
                elif self.winner == 2:
                    self.user_manager.update_pvp_stats(win=False)
                    print(f"💾 PvP istatistikleri güncellendi: KAYBETTİ")
                else:
                    self.user_manager.update_pvp_stats(win=False)
                    print(f"💾 PvP istatistikleri güncellendi: BERABERE")
            return

        # Süresiz/süreli fark etmeksizin: elenme varsa elenmeyen kazanır.
        if self.p1_eliminated and not self.p2_eliminated:
            self.winner = 2
        elif self.p2_eliminated and not self.p1_eliminated:
            self.winner = 1
        else:
            # İki oyuncu da elendiyse skor ile belirle (eşitse berabere).
            if score1 > score2:
                self.winner = 1
                print(f"🏆 Oyuncu 1 KAZANDI! (Skor: {score1} vs {score2})")
            elif score2 > score1:
                self.winner = 2
                print(f"🏆 Oyuncu 2 KAZANDI! (Skor: {score2} vs {score1})")
            else:
                self.winner = 'draw'
                print(f"🤝 BERABERE! (Satır: {lines1}-{lines2}, Skor: {score1}-{score2})")
        
        self.game_over = True
        self.sound.play('gameover')
        
        # Kullanıcı istatistiklerini güncelle
        if self.user_manager:
            # PvP oyun sayısını artır ve kazanan/kaybedeni kaydet
            if self.winner == 1:
                self.user_manager.update_pvp_stats(win=True)
                print(f"💾 PvP istatistikleri güncellendi: KAZANDI")
            elif self.winner == 2:
                self.user_manager.update_pvp_stats(win=False)
                print(f"💾 PvP istatistikleri güncellendi: KAYBETTİ")
            else:
                # Beraberlik - oyun sayısını artır ama kazanan/kaybeden yok
                self.user_manager.update_pvp_stats(win=False)
                print(f"💾 PvP istatistikleri güncellendi: BERABERE")
    
    def create_particles(self, count, x=None, y=None, colors=None, speed=5):
        """Partiküller oluştur - optimize edilmiş"""
        if not self._particle_effects_enabled():
            return
        
        # Varsayılan konum
        if x is None:
            x = random.randint(0, self.window_width)
        if y is None:
            y = random.randint(0, self.window_height // 2)
        
        # Varsayılan renkler
        if colors is None:
            colors = [CYAN, YELLOW, MAGENTA, GREEN, RED]
        
        for _ in range(count):
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 2 - 1),
                'vy': speed * (random.random() * 2 - 1),
                'life': random.randint(20, 40),  # Daha kısa ömür
                'max_life': 40,
                'color': random.choice(colors),
                'size': random.randint(2, 4)  # Daha küçük
            }
            self.particles.append(particle)
    
    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size, board=None):
        """Satır temizlendiğinde SÜPER parçacıklar oluştur - ANA OYUN İLE AYNI (GELİŞTİRİLMİŞ VERSİYON)"""
        if not self._particle_effects_enabled():
            return
        
        # Parlak renkler paleti
        sparkle_colors = [
            (255, 255, 255),  # Beyaz
            (255, 255, 200),  # Sıcak beyaz
            (255, 215, 0),    # Altın
            (0, 255, 255),    # Cyan
            (255, 100, 255),  # Pembe
        ]
        
        for row in cleared_rows:
            # Satırdaki tüm hücrelerden parçacıklar saçıl
            for col in range(BOARD_WIDTH):
                # Hücrenin ekran pozisyonu
                cell_x = board_offset_x + col * cell_size + cell_size // 2
                cell_y = board_offset_y + row * cell_size + cell_size // 2
                
                # Hücre rengi - last_cleared_colors'dan al (satır silinmeden kaydedilmiş)
                try:
                    if board and hasattr(board, 'last_cleared_colors') and row in board.last_cleared_colors:
                        row_colors = board.last_cleared_colors[row]
                        if col < len(row_colors) and row_colors[col] != BLACK:
                            cell_color = row_colors[col]
                        else:
                            cell_color = random.choice(sparkle_colors)
                    else:
                        cell_color = random.choice(sparkle_colors)
                except Exception:
                    cell_color = random.choice(sparkle_colors)
                
                # === ANA PATLAMA PARÇACIKLARı ===
                # Her hücreden 6-10 ana parçacık
                for _ in range(random.randint(6, 10)):
                    speed = random.uniform(4, 12)
                    
                    # Yatay hareket daha baskın (satır boyunca saçılım)
                    vx = speed * random.uniform(-1.5, 1.5)
                    vy = speed * random.uniform(-1, 0.5) - 2  # Yukarı doğru
                    
                    particle = {
                        'x': float(cell_x + random.randint(-3, 3)),
                        'y': float(cell_y + random.randint(-3, 3)),
                        'vx': vx,
                        'vy': vy,
                        'life': random.randint(40, 80),
                        'max_life': 80,
                        'color': cell_color,
                        'size': random.randint(3, 7),
                        'glow': True
                    }
                    self.particles.append(particle)
                
                # === KIVILCIM PARÇACIKLARı ===
                # Her 2 hücreden 1 kıvılcım
                if col % 2 == 0:
                    for _ in range(random.randint(2, 4)):
                        spark_color = random.choice(sparkle_colors)
                        spark_speed = random.uniform(8, 15)
                        
                        particle = {
                            'x': float(cell_x),
                            'y': float(cell_y),
                            'vx': spark_speed * random.uniform(-1, 1),
                            'vy': -spark_speed * random.uniform(0.3, 1) - 5,  # Güçlü yukarı
                            'life': random.randint(20, 40),
                            'max_life': 40,
                            'color': spark_color,
                            'size': random.randint(2, 4),
                            'glow': True,
                            'spark': True  # Kıvılcım işareti
                        }
                        self.particles.append(particle)
            
            # === SATIR ORTASINDAN YILDIZ EFEKTİ ===
            center_x = board_offset_x + (BOARD_WIDTH * cell_size) // 2
            center_y = board_offset_y + row * cell_size + cell_size // 2
            
            # Merkezi patlama - yıldız şeklinde
            for i in range(16):
                angle = (i / 16) * 2 * math.pi
                star_speed = random.uniform(6, 14)
                
                particle = {
                    'x': float(center_x),
                    'y': float(center_y),
                    'vx': math.cos(angle) * star_speed,
                    'vy': math.sin(angle) * star_speed - 2,
                    'life': random.randint(30, 60),
                    'max_life': 60,
                    'color': random.choice(sparkle_colors),
                    'size': random.randint(4, 8),
                    'glow': True
                }
                self.particles.append(particle)
    
    def update_particles(self, dt_ms: float | None = None):
        """Partikülleri güncelle (dt tabanlı - game.py ile aynı akıcılık)"""
        if not self.particles:
            return
        
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666

        alive = []
        for particle in self.particles:
            particle['x'] += particle.get('vx', 0) * dt_frames
            particle['y'] += particle.get('vy', 0) * dt_frames
            particle['vy'] += 0.5 * dt_frames  # Yerçekimi (dt tabanlı)
            particle['vx'] *= 0.98 ** dt_frames  # Hava sürtünmesi (dt tabanlı)
            particle['life'] = float(particle.get('life', 0)) - dt_frames
            if particle['life'] > 0:
                alive.append(particle)
        self.particles = alive

    def create_lock_explosion(self, x, y, color, cell_size=25):
        """Ana oyundaki gibi hücre bazlı kilitlenme patlaması oluştur."""
        if not self._particle_effects_enabled():
            return

        base_color = tuple(color[:3]) if color else (128, 128, 128)
        bright_color = tuple(min(255, int(c * 1.3)) for c in base_color)
        dim_color = tuple(max(0, int(c * 0.7)) for c in base_color)
        white_tint = tuple(min(255, c + 80) for c in base_color)
        color_palette = [base_color, bright_color, dim_color, white_tint, (255, 255, 255)]

        particle_count = random.randint(6, 10)
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(2, 5)
            self.particles.append({
                'x': float(x + random.uniform(-3, 3)),
                'y': float(y + random.uniform(-3, 3)),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - 1,
                'life': random.randint(20, 40),
                'max_life': 40,
                'color': random.choice(color_palette),
                'size': random.randint(2, 4),
                'glow': True,
            })

        self.particles.append({
            'x': float(x),
            'y': float(y),
            'vx': 0,
            'vy': -0.5,
            'life': 12,
            'max_life': 12,
            'color': white_tint,
            'size': int(cell_size * 0.4),
            'glow': True,
        })

    def _get_drop_trail_store(self, player: int):
        return self.p1_drop_trails if player == 1 else self.p2_drop_trails

    def _create_drop_trail(self, player: int, piece: Piece | None, board_x: int, board_y: int,
                           cell_size: int, start_y: int, distance: int,
                           trail_type: str = 'hard'):
        """Oyuncu bazlı sert düşüş izi oluştur."""
        if not self.effects_enabled or not piece or distance <= 0:
            return

        trail_store = self._get_drop_trail_store(player)
        for row_idx, row in enumerate(piece.shape):
            for col_idx, cell in enumerate(row):
                if not cell:
                    continue
                block_x = board_x + (piece.x + col_idx) * cell_size
                block_y = board_y + start_y * cell_size + row_idx * cell_size
                trail_height = distance * cell_size
                if trail_height <= 0:
                    continue

                if trail_type == 'hard':
                    alpha = 180
                    trail_width = cell_size - 4
                    fade_speed = 15
                else:
                    alpha = 80
                    trail_width = max(2, cell_size // 2)
                    fade_speed = 20

                color = tuple(getattr(piece, 'color', (128, 128, 128))[:3])
                bright_color = (
                    min(255, color[0] + 50),
                    min(255, color[1] + 50),
                    min(255, color[2] + 50),
                )
                trail_store.append({
                    'x': block_x + (cell_size - trail_width) // 2,
                    'y': block_y,
                    'width': trail_width,
                    'height': trail_height,
                    'color': bright_color,
                    'alpha': alpha,
                    'fade_speed': fade_speed,
                })

    def _update_drop_trails(self, dt_frames: float):
        """Oyuncu bazlı trail efektlerini güncelle."""
        for trail_store_name in ('p1_drop_trails', 'p2_drop_trails'):
            trail_store = getattr(self, trail_store_name, [])
            for trail in trail_store:
                trail['alpha'] -= trail['fade_speed'] * dt_frames
            setattr(self, trail_store_name, [trail for trail in trail_store if trail['alpha'] > 0])

    def _draw_drop_trails(self, player: int):
        """İlgili oyuncunun drop trail efektlerini çiz."""
        for trail in self._get_drop_trail_store(player):
            if trail['alpha'] <= 0:
                continue
            trail_surface = pygame.Surface((int(trail['width']), int(trail['height'])), pygame.SRCALPHA)
            segments = max(1, int(trail['height'] // 4))
            segment_height = trail['height'] / segments
            for i in range(segments):
                segment_alpha = int(trail['alpha'] * (1 - i / segments))
                if segment_alpha <= 0:
                    continue
                y_pos = int(i * segment_height)
                height = max(1, int(segment_height + 1))
                color_with_alpha = (*trail['color'], segment_alpha)
                pygame.draw.rect(
                    trail_surface,
                    color_with_alpha,
                    (0, y_pos, int(trail['width']), height),
                    border_radius=max(1, int(trail['width']) // 4),
                )
            self.screen.blit(trail_surface, (int(trail['x']), int(trail['y'])))
    
    def create_ambient_particles(self):
        """Arka plan için ambient parçacıklar oluştur"""
        if not self._particle_effects_enabled():
            return
        for _ in range(random.randint(50, 100)):
            particle = {
                'x': random.uniform(0, self.window_width),
                'y': random.uniform(0, self.window_height),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.2, 0.8),
                'size': random.randint(1, 3),
                'alpha': random.randint(50, 150),
                'pulse': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.02, 0.05)
            }
            self.ambient_particles.append(particle)
    
    def update_ambient_particles(self, dt_ms: float | None = None):
        """Ambient parçacıkları güncelle (dt tabanlı)"""
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666
        
        for particle in self.ambient_particles:
            particle['x'] += particle['vx'] * dt_frames
            particle['y'] += particle['vy'] * dt_frames
            particle['pulse'] += particle['pulse_speed'] * dt_frames
            
            if particle['y'] > self.window_height:
                particle['y'] = -10
                particle['x'] = random.uniform(0, self.window_width)
            
            if particle['x'] < -10:
                particle['x'] = self.window_width + 10
            elif particle['x'] > self.window_width + 10:
                particle['x'] = -10
    
    def draw_ambient_particles(self):
        """Ambient parçacıkları çiz"""
        for particle in self.ambient_particles:
            pulse_alpha = int(particle['alpha'] + math.sin(particle['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            
            color = (200, 200, 255)
            pos = (int(particle['x']), int(particle['y']))
            size = particle['size']
            
            if size > 1:
                glow_surface = self._get_ambient_sprite(size, pulse_alpha // 3, glow=True)
                self.screen.blit(glow_surface, (pos[0] - glow_surface.get_width() // 2, pos[1] - glow_surface.get_height() // 2))
            
            particle_surface = self._get_ambient_sprite(size, pulse_alpha, glow=False)
            self.screen.blit(particle_surface, (pos[0] - particle_surface.get_width() // 2, pos[1] - particle_surface.get_height() // 2))
    
    def trigger_screen_shake(self, intensity=10, duration=15):
        """Ekran titremesi efekti başlat (dt tabanlı)"""
        if not self._particle_effects_enabled():
            return
        self._screen_shake_initial = max(1.0, float(duration))
        self.screen_shake = float(duration)
        self.shake_intensity = intensity
    
    def update_screen_shake(self, dt_ms: float | None = None):
        """Ekran titremesini güncelle (dt tabanlı)"""
        if self.screen_shake > 0:
            try:
                dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
            except Exception:
                dt = 16.666
            dt = max(0.0, min(100.0, dt))
            dt_frames = dt / 16.666
            self.screen_shake = max(0, self.screen_shake - dt_frames)
    
    def get_shake_offset(self):
        """Ekran titremesi için offset hesapla"""
        if self.screen_shake > 0:
            initial = getattr(self, '_screen_shake_initial', 15.0)
            decay = self.screen_shake / initial
            shake_x = random.randint(-self.shake_intensity, self.shake_intensity)
            shake_y = random.randint(-self.shake_intensity, self.shake_intensity)
            return (int(shake_x * decay), int(shake_y * decay))
        return (0, 0)
    
    def _get_rotated_surface(self, surface, rotation):
        rotation = (rotation or 0) % 4
        if surface is None or rotation == 0:
            return surface
        surf_id = id(surface)
        cache_entry = self._texture_rotation_cache.get(surf_id)
        if not cache_entry or cache_entry.get('surface') is not surface:
            cache_entry = {'surface': surface, 'variants': {}}
            self._texture_rotation_cache[surf_id] = cache_entry
        variants = cache_entry['variants']
        if rotation not in variants:
            angle = -90 * rotation
            variants[rotation] = pygame.transform.rotate(surface, angle)
        return variants[rotation]

    def _render_texture_slice(self, surface, slice_info, size):
        rotated = self._get_rotated_surface(surface, getattr(slice_info, 'rotation', 0))
        if rotated is None:
            return None

        tex_w, tex_h = rotated.get_size()
        bounds = {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}
        if self.block_style_manager:
            bounds = self.block_style_manager.get_slice_bounds(slice_info.piece_name)

        u0 = bounds['x'] + (slice_info.rel_x / slice_info.width) * bounds['w']
        u1 = bounds['x'] + ((slice_info.rel_x + 1) / slice_info.width) * bounds['w']
        v0 = bounds['y'] + (slice_info.rel_y / slice_info.height) * bounds['h']
        v1 = bounds['y'] + ((slice_info.rel_y + 1) / slice_info.height) * bounds['h']

        rect = pygame.Rect(
            int(u0 * tex_w),
            int(v0 * tex_h),
            max(1, int((u1 - u0) * tex_w)),
            max(1, int((v1 - v0) * tex_h)),
        )
        rect.clamp_ip(rotated.get_rect())
        cell_surface = rotated.subsurface(rect)
        return pygame.transform.smoothscale(cell_surface, (size, size))

    def _draw_texture_cell(self, x, y, size, texture_surface, texture_slice, dst):
        scaled = self._render_texture_slice(texture_surface, texture_slice, size)
        if scaled is None:
            return
        dst.blit(scaled, (x, y))

    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice=None, dst: pygame.Surface | None = None):
        """Ana oyun temeli: texture varsa dilimle + jelly border, yoksa jelly."""
        target = dst or self.screen
        if texture_surface is not None and texture_slice is not None:
            self._draw_texture_cell(x, y, size, texture_surface, texture_slice, target)
            draw_jelly_border(target, x, y, size, color)
            return
        draw_jelly_block(target, x, y, size, color)
    
    def draw_particles(self):
        """Partikülleri çiz - İYİLEŞTİRİLMİŞ GLOW EFEKTİ"""
        for particle in self.particles:
            # Alpha değeri (sönme efekti)
            alpha_ratio = particle['life'] / particle['max_life']
            alpha = int(255 * alpha_ratio)
            
            # Boyut (küçülme efekti)
            size = max(1, int(particle['size'] * alpha_ratio))
            
            color = particle['color']
            pos = (int(particle['x']), int(particle['y']))
            
            # Glow efekti varsa
            if particle.get('glow', False) and size > 2:
                # Dış halo
                halo_size = size + 4
                halo_color = tuple(min(255, int(c * 0.6)) for c in color[:3])
                halo_surface = pygame.Surface((halo_size * 2, halo_size * 2), pygame.SRCALPHA)
                pygame.draw.circle(halo_surface, (*halo_color, int(alpha * 0.3)), (halo_size, halo_size), halo_size)
                self.screen.blit(halo_surface, (pos[0] - halo_size, pos[1] - halo_size))
                
                # Orta halo
                mid_size = size + 2
                mid_color = tuple(min(255, int(c * 0.8)) for c in color[:3])
                mid_surface = pygame.Surface((mid_size * 2, mid_size * 2), pygame.SRCALPHA)
                pygame.draw.circle(mid_surface, (*mid_color, int(alpha * 0.5)), (mid_size, mid_size), mid_size)
                self.screen.blit(mid_surface, (pos[0] - mid_size, pos[1] - mid_size))
            
            # Ana parçacık
            pygame.draw.circle(self.screen, color, pos, size)
            
            # Parlama efekti (iç kısım) - daha parlak
            if size > 2:
                inner_size = max(1, size - 1)
                inner_color = tuple(min(255, c + 80) for c in color[:3])
                pygame.draw.circle(self.screen, inner_color, pos, inner_size)
                
                # Merkez ışık noktası
                if size > 3:
                    core_color = tuple(min(255, c + 120) for c in color[:3])
                    pygame.draw.circle(self.screen, core_color, pos, 1)
    
    def create_firework(self, x, y, player=None):
        """Havai fişek efekti oluştur - optimize edilmiş"""
        if not self._particle_effects_enabled():
            return
        
        # Oyuncuya özel renkler
        if player == 1:
            colors = [(0, 255, 255), (0, 200, 255), (100, 255, 255), (255, 255, 255)]  # Cyan tonları
        elif player == 2:
            colors = [(255, 0, 255), (255, 100, 255), (200, 0, 255), (255, 255, 255)]  # Magenta tonları
        else:
            colors = [(255, 215, 0), (255, 165, 0), (255, 50, 50), (50, 255, 50)]  # Karışık
        
        main_color = random.choice(colors)
        
        # Dairesel patlama - optimize edilmiş
        particle_count = random.randint(12, 18)  # 22-32'den düşürüldü
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * 3.14159
            speed = random.uniform(2, 5)  # Daha yavaş
            
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1),
                'vy': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1) - 2,
                'life': random.randint(35, 55),  # Daha kısa ömür
                'max_life': 55,
                'color': main_color if random.random() > 0.3 else random.choice(colors),
                'size': random.randint(3, 6),  # Daha küçük
                'type': 'firework'
            }
            self.particles.append(particle)
    
    def create_player_fireworks(self, player):
        """Belirli bir oyuncu için havai fişek gösterisi"""
        if not self._particle_effects_enabled():
            return
        
        # Oyuncunun oyun alanı etrafında havai fişekler
        if player == 1:
            base_x = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
        else:
            base_x = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
        
        firework_count = random.randint(1, 2)
        for _ in range(firework_count):
            x = base_x + random.randint(-100, 100)
            y = random.randint(self.window_height // 4, 2 * self.window_height // 3)
            self.create_firework(x, y, player)
    
    def update(self, delta_time):
        """Oyun durumunu güncelle"""
        try:
            if self.sound_enabled:
                self.sound.update_music_playlist()
        except Exception:
            pass
        if self.name_input_active or self.game_over or self.paused or getattr(self, 'show_exit_prompt', False):
            return

        # Start the match timer the first frame after name entry.
        if not self.match_active:
            self.match_active = True
            self.match_elapsed_ms = 0
            self.match_end_reason = None
            self._last_timer_seconds = None

        # Update match timer; only check time limit in timed mode
        self.match_elapsed_ms += int(delta_time)
        
        if self.match_mode == 'timed':
            remaining_ms = int(self.match_duration_ms) - int(self.match_elapsed_ms)
            remaining_ms = max(0, remaining_ms)
            remaining_seconds = remaining_ms // 1000
            if self._last_timer_seconds != remaining_seconds:
                self._last_timer_seconds = remaining_seconds
                self._vs_panel_dirty = True
            if remaining_ms <= 0 and not self.game_over:
                self.match_end_reason = 'time'
                self.determine_winner()
                return
        else:
            # Süresiz mod - sadece elapsed time'ı göster
            elapsed_seconds = self.match_elapsed_ms // 1000
            if self._last_timer_seconds != elapsed_seconds:
                self._last_timer_seconds = elapsed_seconds
                self._vs_panel_dirty = True
        
        # DAS (Delayed Auto Shift) güncelle - basılı tutarak yatay hareket
        self._update_das(delta_time)
        
        # Soft drop güncelle - basılı tutarak hızlı düşüş
        self._update_soft_drop(delta_time)
        
        # dt değerini sakla (dt-tabanlı parçacık güncellemesi için)
        self._last_dt_ms = delta_time
        
        # Partikülleri güncelle (dt tabanlı)
        self.update_particles(dt_ms=delta_time)
        self.update_ambient_particles(dt_ms=delta_time)
        self.update_screen_shake(dt_ms=delta_time)

        # Frame bazlı delta hesapla (60 FPS varsayım)
        dt_frames = delta_time / 16.67 if delta_time > 0 else 1.0

        if self.p1_drop_trails or self.p2_drop_trails:
            self._update_drop_trails(dt_frames)
        
        # Satır flash timer güncelle (ana oyundaki gibi - 20 frame)
        if self.p1_line_flash_timer > 0:
            self.p1_line_flash_timer = max(0, self.p1_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.p1_line_flash_timer / 20.0))
            self.p1_line_glow_alpha = int(255 * ratio)
            if self.p1_line_flash_timer <= 0:
                self.p1_line_flash_rows = []
                self.p1_line_glow_alpha = 0
        
        if self.p2_line_flash_timer > 0:
            self.p2_line_flash_timer = max(0, self.p2_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.p2_line_flash_timer / 20.0))
            self.p2_line_glow_alpha = int(255 * ratio)
            if self.p2_line_flash_timer <= 0:
                self.p2_line_flash_rows = []
                self.p2_line_glow_alpha = 0

        if self.p1_line_sweep_active:
            self.p1_line_sweep_progress += dt_frames * 0.06
            if self.p1_line_sweep_progress >= 1.0:
                self.p1_line_sweep_progress = 1.0
                self.p1_line_sweep_active = False
                self.p1_line_sweep_rows = []

        if self.p2_line_sweep_active:
            self.p2_line_sweep_progress += dt_frames * 0.06
            if self.p2_line_sweep_progress >= 1.0:
                self.p2_line_sweep_progress = 1.0
                self.p2_line_sweep_active = False
                self.p2_line_sweep_rows = []
        
        # Dalga efektlerini güncelle (ana oyundaki gibi)
        for wave in self.p1_wave_effects[:]:
            wave['radius'] += wave['speed'] * dt_frames
            wave['alpha'] = int(200 * (1 - wave['radius'] / wave['max_radius']))
            if wave['radius'] >= wave['max_radius'] or wave['alpha'] <= 0:
                self.p1_wave_effects.remove(wave)
        
        for wave in self.p2_wave_effects[:]:
            wave['radius'] += wave['speed'] * dt_frames
            wave['alpha'] = int(200 * (1 - wave['radius'] / wave['max_radius']))
            if wave['radius'] >= wave['max_radius'] or wave['alpha'] <= 0:
                self.p2_wave_effects.remove(wave)

        if self.p1_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.p1_falling_block_animations:
                if not anim.get('started', False) and self.p1_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.p1_falling_block_animations = [
                anim for anim in self.p1_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]

        if self.p2_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.p2_falling_block_animations:
                if not anim.get('started', False) and self.p2_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.p2_falling_block_animations = [
                anim for anim in self.p2_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]
        
        # Oyuncu 1 milestone kontrolü
        p1_milestone = (self.board1.score // 1000) * 1000
        if p1_milestone > self.p1_last_milestone and p1_milestone > 0:
            self.p1_last_milestone = p1_milestone
            self.create_player_fireworks(1)
            self.p1_firework_active = True
            self.p1_firework_time = 120
            self.sound.play('tetris')
            self.trigger_screen_shake(intensity=12, duration=15)  # Screen shake
            # Oyuncu 1 hızını artır
            old_speed = self.fall_speed1
            self.fall_speed1 = max(self.min_fall_speed, self.fall_speed1 - self.speed_increase_per_milestone)
            print(f"🎆 Oyuncu 1: {p1_milestone} PUAN! Hız: {old_speed}ms -> {self.fall_speed1}ms 🚀")
        
        # Oyuncu 2 milestone kontrolü
        p2_milestone = (self.board2.score // 1000) * 1000
        if p2_milestone > self.p2_last_milestone and p2_milestone > 0:
            self.p2_last_milestone = p2_milestone
            self.create_player_fireworks(2)
            self.p2_firework_active = True
            self.p2_firework_time = 120
            self.sound.play('tetris')
            self.trigger_screen_shake(intensity=12, duration=15)  # Screen shake
            # Oyuncu 2 hızını artır
            old_speed = self.fall_speed2
            self.fall_speed2 = max(self.min_fall_speed, self.fall_speed2 - self.speed_increase_per_milestone)
            print(f"🎆 Oyuncu 2: {p2_milestone} PUAN! Hız: {old_speed}ms -> {self.fall_speed2}ms 🚀")
        
        # Havai fişek sürelerini güncelle
        if self.p1_firework_active:
            self.p1_firework_time -= 1
            if self.p1_firework_time <= 0:
                self.p1_firework_active = False
        
        if self.p2_firework_active:
            self.p2_firework_time -= 1
            if self.p2_firework_time <= 0:
                self.p2_firework_active = False
        
        # Oyuncu 1 otomatik düşüş (kendi hızıyla)
        if not self.board1.is_game_over():
            self.fall_time1 += delta_time
            if self.fall_time1 >= self.fall_speed1:
                self.fall_time1 = 0
                self.current_piece1.y += 1
                
                if not self.board1.is_valid_position(self.current_piece1):
                    self.current_piece1.y -= 1
                    self.lock_and_new_piece(1)
        
        # Oyuncu 2 otomatik düşüş (kendi hızıyla)
        if not self.board2.is_game_over():
            self.fall_time2 += delta_time
            if self.fall_time2 >= self.fall_speed2:
                self.fall_time2 = 0
                self.current_piece2.y += 1
                
                if not self.board2.is_valid_position(self.current_piece2):
                    self.current_piece2.y -= 1
                    self.lock_and_new_piece(2)
    
    def draw_board(self, board, current_piece, offset_x, offset_y, cell_size):
        """Bir oyun tahtasını çiz"""
        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        skin = self.mode_skin
        player_accent = UIColors.NEON_CYAN if board is self.board1 else UIColors.NEON_MAGENTA
        
        # Arka plan - Quadrix alanı için özel arka plan varsa onu kullan
        board_rect = pygame.Rect(offset_x, offset_y, board_width, board_height)
        
        if self.board_background.is_loaded():
            # Özel tetris alan arka planı çiz
            self.board_background.draw(self.screen, board_rect)
        else:
            # Varsayılan siyah arka plan
            pygame.draw.rect(self.screen, (6, 6, 16), board_rect)
        apply_board_tint(self.screen, board_rect, skin)
        draw_board_overlay(self.screen, board_rect, skin)

        # Oyuncuya göre çok hafif tint + border (alanları daha net ayırır) - cache'li
        accent_key = (int(board_width), int(board_height), player_accent)
        accent_overlay = self._board_accent_overlay_cache.get(accent_key)
        if accent_overlay is None:
            accent_overlay = pygame.Surface(board_rect.size, pygame.SRCALPHA).convert_alpha()
            accent_overlay.fill((*player_accent[:3], 18))
            self._board_accent_overlay_cache[accent_key] = accent_overlay
        self.screen.blit(accent_overlay, board_rect.topleft)

        pygame.draw.rect(self.screen, player_accent, board_rect, 2, border_radius=14)

        # Cache'li, alpha'lı grid (daha sade)
        grid_surface = self._get_board_grid_surface(cell_size)
        self.screen.blit(grid_surface, (offset_x, offset_y))

        # Kilitli bloklar - cache'li surface (performans)
        player_idx = 1 if board is self.board1 else 2
        cache_entry = self._locked_board_cache[player_idx]
        cache_key = (int(cell_size), int(board_width), int(board_height))
        animating_fall = bool(self.p1_falling_block_animations) if player_idx == 1 else bool(self.p2_falling_block_animations)
        if cache_entry.get('surface') is None or cache_entry.get('key') != cache_key or cache_entry.get('dirty') or animating_fall:
            locked_surface = pygame.Surface((board_width, board_height), pygame.SRCALPHA).convert_alpha()
            locked_surface.fill((0, 0, 0, 0))
            block_size = cell_size - 2
            for y in range(BOARD_HEIGHT):
                row = board.grid[y]
                for x in range(BOARD_WIDTH):
                    c = row[x]
                    if c != BLACK:
                        slice_info = None
                        tex = None
                        try:
                            slice_info = board.texture_grid[y][x]
                        except Exception:
                            slice_info = None
                        if slice_info is not None and self.block_style_manager:
                            tex = self.block_style_manager.get_texture_surface(slice_info.piece_name)
                        block_x = x * cell_size + 1
                        block_y = y * cell_size + 1
                        block_y += self._get_block_fall_offset(player_idx, y, x)
                        self.draw_textured_block(block_x, block_y, block_size, c, tex, slice_info, dst=locked_surface)
            cache_entry['surface'] = locked_surface
            cache_entry['key'] = cache_key
            cache_entry['dirty'] = animating_fall

        self.screen.blit(cache_entry['surface'], (offset_x, offset_y))

        if self.effects_enabled:
            self._draw_drop_trails(player_idx)
        
        # Mevcut parça - 3D DOKULU
        if not board.is_game_over():
            tex = getattr(current_piece, 'texture_surface', None)
            piece_w = len(current_piece.shape[0]) if current_piece.shape else 1
            piece_h = len(current_piece.shape) if current_piece.shape else 1
            for ly, prow in enumerate(current_piece.shape):
                for lx, val in enumerate(prow):
                    if not val:
                        continue
                    x = current_piece.x + lx
                    y = current_piece.y + ly
                    if y < 0:
                        continue
                    block_x = offset_x + x * cell_size + 1
                    block_y = offset_y + y * cell_size + 1
                    block_size = cell_size - 2
                    slice_info = None
                    if tex is not None:
                        slice_info = TextureSlice(
                            current_piece.name,
                            rel_x=lx,
                            rel_y=ly,
                            width=piece_w or 1,
                            height=piece_h or 1,
                            rotation=getattr(current_piece, 'rotation_state', 0),
                        )
                    draw_color = current_piece.color
                    color_matrix = getattr(current_piece, 'color_matrix', None)
                    if color_matrix is not None:
                        try:
                            cell_color = color_matrix[ly][lx]
                            if cell_color is not None:
                                draw_color = cell_color
                        except Exception:
                            pass
                    self.draw_textured_block(block_x, block_y, block_size, draw_color, tex, slice_info)

        # ===== SATIR TEMİZLEME EFEKTLERİ (ANA OYUNLA BİREBİR AYNI) =====
        flash_rows = self.p1_line_flash_rows if board is self.board1 else self.p2_line_flash_rows
        glow_alpha = self.p1_line_glow_alpha if board is self.board1 else self.p2_line_glow_alpha
        sweep_rows = self.p1_line_sweep_rows if board is self.board1 else self.p2_line_sweep_rows
        sweep_progress = self.p1_line_sweep_progress if board is self.board1 else self.p2_line_sweep_progress
        sweep_active = self.p1_line_sweep_active if board is self.board1 else self.p2_line_sweep_active

        if self.effects_enabled and sweep_rows and sweep_active:
            sweep_width = max(3, int(cell_size * 1.5))
            for row in sweep_rows:
                if 0 <= row < BOARD_HEIGHT:
                    row_y = offset_y + row * cell_size
                    sweep_x = offset_x + int(sweep_progress * (board_width + sweep_width)) - sweep_width
                    for i in range(sweep_width):
                        half = max(1, sweep_width // 2)
                        intensity = 1.0 - abs(i - half) / half
                        alpha = int(255 * intensity * (1.0 - sweep_progress * 0.3))
                        line_x = sweep_x + i
                        if offset_x <= line_x < offset_x + board_width and alpha > 0:
                            pygame.draw.line(
                                self.screen,
                                (255, 255, 255),
                                (line_x, row_y),
                                (line_x, row_y + cell_size),
                                1,
                            )
                    if sweep_progress > 0:
                        lit_width = min(int(sweep_progress * board_width), int(board_width))
                        if lit_width > 0:
                            lit_surface = pygame.Surface((lit_width, cell_size), pygame.SRCALPHA)
                            lit_surface.fill((255, 255, 255, int(180 * (1.0 - sweep_progress * 0.8))))
                            self.screen.blit(lit_surface, (offset_x, row_y))
        
        # Flash overlay - temizlenen satırlar için beyaz parlama
        if self.effects_enabled and flash_rows and glow_alpha > 0:
            # Cache: her frame yeni surface yaratmak yerine yeniden kullan
            flash_cache = getattr(self, '_line_clear_flash_cache', None)
            if flash_cache is None:
                flash_cache = {}
                self._line_clear_flash_cache = flash_cache
            glow_cache = getattr(self, '_line_clear_glow_cache', None)
            if glow_cache is None:
                glow_cache = {}
                self._line_clear_glow_cache = glow_cache

            for row in flash_rows:
                if 0 <= row < BOARD_HEIGHT:
                    # Satır için parlayan overlay
                    flash_rect = pygame.Rect(
                        offset_x, 
                        offset_y + row * cell_size, 
                        board_width, 
                        cell_size
                    )
                    
                    # Ana beyaz parlama (ana oyunla aynı)
                    flash_alpha = min(255, glow_alpha)
                    flash_key = (int(board_width), int(cell_size))
                    flash_surface = flash_cache.get(flash_key)
                    if flash_surface is None or flash_surface.get_size() != (int(board_width), int(cell_size)):
                        flash_surface = pygame.Surface((int(board_width), int(cell_size)), pygame.SRCALPHA)
                        flash_surface.fill((255, 255, 255, 255))
                        flash_cache[flash_key] = flash_surface
                    flash_surface.set_alpha(int(flash_alpha))
                    self.screen.blit(flash_surface, flash_rect.topleft)
                    
                    # Kenarlarda ışık efekti (gradient benzeri) - ana oyunla aynı
                    if glow_alpha > 100:
                        glow_height = cell_size // 2
                        # Üst/alt glow gradient'lerini cache'le
                        glow_surf_alpha = int(flash_alpha * 0.5)
                        if glow_height > 0 and glow_surf_alpha > 0:
                            top_key = (int(board_width), int(glow_height), 'top')
                            top_glow = glow_cache.get(top_key)
                            if top_glow is None or top_glow.get_size() != (int(board_width), int(glow_height)):
                                top_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                                for i in range(int(glow_height)):
                                    a = int(255 * (1.0 - (i / max(1, glow_height - 1))))
                                    pygame.draw.line(top_glow, (255, 255, 200, a), (0, i), (int(board_width), i))
                                glow_cache[top_key] = top_glow
                            top_glow.set_alpha(glow_surf_alpha)
                            self.screen.blit(top_glow, (offset_x, offset_y + row * cell_size - glow_height))

                            bottom_key = (int(board_width), int(glow_height), 'bottom')
                            bottom_glow = glow_cache.get(bottom_key)
                            if bottom_glow is None or bottom_glow.get_size() != (int(board_width), int(glow_height)):
                                bottom_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                                for i in range(int(glow_height)):
                                    a = int(255 * (i / max(1, glow_height - 1)))
                                    pygame.draw.line(bottom_glow, (255, 255, 200, a), (0, i), (int(board_width), i))
                                glow_cache[bottom_key] = bottom_glow
                            bottom_glow.set_alpha(glow_surf_alpha)
                            self.screen.blit(bottom_glow, (offset_x, offset_y + (row + 1) * cell_size))
        
        # Dalga efektleri çiz (ana oyunla aynı - yatay elips)
        wave_effects = self.p1_wave_effects if board is self.board1 else self.p2_wave_effects
        if self.effects_enabled:
            for wave in wave_effects:
                if wave['alpha'] > 0:
                    # Yatay dalga çizgisi (ana oyunla aynı)
                    wave_surface = pygame.Surface((int(wave['radius'] * 2), 6), pygame.SRCALPHA)
                    wave_color = (*wave['color'], wave['alpha'])
                    pygame.draw.ellipse(wave_surface, wave_color, wave_surface.get_rect())
                    wave_x = wave['x'] - wave['radius']
                    wave_y = wave['y'] - 3
                    self.screen.blit(wave_surface, (int(wave_x), int(wave_y)))
    
    def draw(self):
        """Ekranı çiz"""
        # Pencere boyutu değiştiyse layout'u yenile
        self.calculate_board_positions()

        # Screen shake offset hesapla
        shake_x, shake_y = self.get_shake_offset()
        
        # Ekranı temizle
        self.screen.fill(self.mode_skin.outer_bg)
        
        # Ambient particles'ı en arkada çiz
        self.draw_ambient_particles()
        
        # İsim girişi ekranı
        if self.name_input_active:
            self.draw_name_input()
            return
        
        cell_size = self.cell_size
        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        vs_panel_width = int(self.center_panel_width)

        offset_x1 = int(self.p1_offset_x + shake_x)
        offset_x2 = int(self.p2_offset_x + shake_x)
        start_y = int(self.p1_offset_y + shake_y)
        
        # Arka planları çiz - Ana arka plan (tüm ekran)
        if self.background.is_loaded():
            self.background.draw(self.screen, (0, 0, self.window_width, self.window_height))

        # Ana menü benzeri arka plan tetris blokları kayma/düşme efekti (PvP gameplay)
        if self.effects_enabled and self.name_background_fx:
            self.name_background_fx.update(self.screen)
            self.name_background_fx.draw(self.screen)

        apply_outer_tint(self.screen, self.mode_skin)
        
        # Oyuncu başlık panelleri (minimal)
        header_y = int(self.header_top + shake_y)
        header_h = int(self.header_height)
        p1_header = pygame.Rect(offset_x1, header_y, board_width, header_h)
        p2_header = pygame.Rect(offset_x2, header_y, board_width, header_h)

        p1_name = (self.player1_name if self.player1_name else t('player_1')).upper()
        p2_name = (self.player2_name if self.player2_name else t('player_2')).upper()

        self._draw_player_header(p1_header, p1_name, UIColors.NEON_CYAN, int(self.board1.score), int(self.board1.lines_cleared), 'WASD')
        self._draw_player_header(p2_header, p2_name, UIColors.NEON_MAGENTA, int(self.board2.score), int(self.board2.lines_cleared), t('arrows').upper())

        # OYUNCU 1 (Sol)
        self.draw_board(self.board1, self.current_piece1, offset_x1, start_y, cell_size)
        
        # OYUNCU 2 (Sağ)
        self.draw_board(self.board2, self.current_piece2, offset_x2, start_y, cell_size)
        
        # ORTADAKİ VS PANELİ
        center_x = self.window_width // 2
        vs_surface = self._get_vs_panel_surface(vs_panel_width)
        center_y = start_y + board_height // 2
        vs_rect = vs_surface.get_rect(center=(center_x, center_y))
        self.screen.blit(vs_surface, vs_rect)
        
        # Pause
        if self.paused and not self.game_over:
            self._draw_pause_menu()
        
        # Game Over / Kazanan - Duraklama menüsüyle aynı tema
        if self.game_over:
            self._draw_game_over_screen()
        
        # Oyuncu 1 milestone mesajı
        if self.p1_firework_active and self.p1_firework_time > 0:
            pulse = abs((self.p1_firework_time % 20) - 10) / 10.0
            color_intensity = int(155 + 100 * pulse)
            
            msg = f"{self.p1_last_milestone:,} 🎆".replace(',', '.')
            msg_surf = self.font_large.render(msg, True, (0, color_intensity, 255))
            
            # Oyuncu 1'in alanı üzerinde
            x_pos = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
            msg_rect = msg_surf.get_rect(center=(x_pos, 200))
            
            # Gölge
            shadow = self.font_large.render(msg, True, BLACK)
            shadow_rect = shadow.get_rect(center=(x_pos + 3, 203))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(msg_surf, msg_rect)
        
        # Oyuncu 2 milestone mesajı
        if self.p2_firework_active and self.p2_firework_time > 0:
            pulse = abs((self.p2_firework_time % 20) - 10) / 10.0
            color_intensity = int(155 + 100 * pulse)
            
            msg = f"{self.p2_last_milestone:,} 🎆".replace(',', '.')
            msg_surf = self.font_large.render(msg, True, (255, 0, color_intensity))
            
            # Oyuncu 2'nin alanı üzerinde
            x_pos = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
            msg_rect = msg_surf.get_rect(center=(x_pos, 200))
            
            # Gölge
            shadow = self.font_large.render(msg, True, BLACK)
            shadow_rect = shadow.get_rect(center=(x_pos + 3, 203))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(msg_surf, msg_rect)
        
        # Partikülleri çiz (en üstte)
        if self.effects_enabled:
            self.draw_particles()
        
        if getattr(self, 'show_exit_prompt', False):
            self._draw_exit_prompt_overlay()


    def _draw_exit_prompt_overlay(self):
        width, height = self.screen.get_size()
        ui_scale = self._ui_scale(min_scale=0.68, max_scale=1.16)

        def _fit_font_size(text: str, base_size: int, min_size: int, max_width: int, bold: bool = False) -> pygame.font.Font:
            size = max(min_size, int(base_size))
            while size > min_size:
                f = retro_style.get_font(size, bold=bold)
                if f.size(text)[0] <= max_width:
                    return f
                size -= 1
            return retro_style.get_font(min_size, bold=bold)

        # Dim overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(self._sx(520, ui_scale), width - self._sx(100, ui_scale))
        panel_height = self._sx(240, ui_scale)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)

        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=180,
            border_color=(*retro_style.accent, 140),
            glow=True,
        )

        title_font = _fit_font_size(
            t('quit_confirm_title'),
            self._sx(30, ui_scale, minimum=16),
            self._sx(15, ui_scale, minimum=11),
            panel_rect.width - self._sx(30, ui_scale),
            bold=True,
        )
        title_surf = title_font.render(t('quit_confirm_title'), True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + self._sx(18, ui_scale)))

        body_font = retro_style.get_font(self._sx(18, ui_scale, minimum=12), bold=False)
        body_color = (210, 225, 245)
        body_rect = pygame.Rect(
            panel_rect.x + self._sx(26, ui_scale),
            panel_rect.y + self._sx(64, ui_scale),
            panel_rect.width - self._sx(52, ui_scale),
            self._sx(70, ui_scale),
        )
        retro_style.draw_wrapped_text(
            self.screen,
            t('quit_confirm_message'),
            body_font,
            body_color,
            body_rect,
            align='center',
            line_spacing=self._sx(6, ui_scale),
        )

        button_width = min(self._sx(200, ui_scale), (panel_rect.width - self._sx(26, ui_scale) * 2 - self._sx(16, ui_scale)) // 2)
        button_height = self._sx(54, ui_scale)
        spacing = self._sx(16, ui_scale)
        total_width = button_width * 2 + spacing
        start_x = panel_rect.centerx - total_width // 2
        button_y = panel_rect.bottom - button_height - self._sx(48, ui_scale)

        yes_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        no_rect = pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height)

        retro_style.draw_uniform_button(
            self.screen,
            yes_rect,
            t('quit_confirm_yes_label'),
            color_code=retro_style.success,
            selected=False,
        )
        retro_style.draw_uniform_button(
            self.screen,
            no_rect,
            t('quit_confirm_no_label'),
            color_code=retro_style.secondary,
            selected=False,
        )

        self.exit_yes_rect = yes_rect
        self.exit_no_rect = no_rect

        hint_font = _fit_font_size(
            t('quit_confirm_select_hint'),
            self._sx(16, ui_scale, minimum=10),
            self._sx(10, ui_scale, minimum=8),
            panel_rect.width - self._sx(24, ui_scale),
            bold=False,
        )
        hint = hint_font.render(t('quit_confirm_select_hint'), True, (150, 165, 190))
        self.screen.blit(hint, hint.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - self._sx(14, ui_scale)))
        

    
    def restart(self, preserve_session: bool = False):
        """Oyunu yeniden başlat.

        preserve_session=True ise oyuncu isimlerini/kurulum ekranını korur ve
        doğrudan yeni maça başlar.
        """
        from board import Board
        
        # Board'ları tamamen yeniden oluştur (temiz grid ile)
        self.board1 = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT)
        self.board2 = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT)
        
        # Board cache'lerini temizle
        self._locked_board_cache = {
            1: {'key': None, 'surface': None, 'dirty': True},
            2: {'key': None, 'surface': None, 'dirty': True},
        }
        
        # Yeni parça sırası
        self.piece_sequence = []
        self.current_piece_index = 0
        self.generate_pieces(100)
        
        # Oyuncu 1 parçaları
        self.current_piece1 = self.get_next_piece()
        self.next_piece1 = self.get_next_piece()
        
        # Oyuncu 2 parçaları (aynı sıra)
        self.current_piece_index = 0
        self.current_piece2 = self.get_next_piece()
        self.next_piece2 = self.get_next_piece()
        
        # Tema renklerini parçalara uygula
        self.apply_theme_to_pieces()
        
        # Oyun durumu sıfırla
        self.game_over = False
        self.winner = None
        self.paused = False
        if hasattr(self, 'sound') and self.sound:
            self.sound.unduck_music()
        self._game_over_peek_active = False
        self._game_over_peek_rect = None
        
        # Maç durumu sıfırla
        self.match_active = False
        self.match_elapsed_ms = 0
        self.match_end_reason = None
        self._last_timer_seconds = None
        
        # Eleme durumu sıfırla
        self.p1_eliminated = False
        self.p2_eliminated = False
        
        # Zamanlama sıfırla
        self.fall_time1 = 0
        self.fall_time2 = 0
        self.fall_speed1 = 900
        self.fall_speed2 = 900
        
        # Milestone ve havai fişek sıfırla
        self.p1_last_milestone = 0
        self.p2_last_milestone = 0
        self.p1_firework_active = False
        self.p2_firework_active = False
        self.p1_firework_time = 0
        self.p2_firework_time = 0
        
        # DAS sıfırla
        self.p1_das_direction = 0
        self.p1_das_timer = 0
        self.p1_das_repeat_timer = 0
        self.p1_das_charged = False
        self.p2_das_direction = 0
        self.p2_das_timer = 0
        self.p2_das_repeat_timer = 0
        self.p2_das_charged = False
        
        # Soft drop sıfırla
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0
        self.p2_soft_drop_active = False
        self.p2_soft_drop_timer = 0
        
        # Satır temizleme efektlerini sıfırla
        self.p1_line_flash_rows = []
        self.p2_line_flash_rows = []
        self.p1_line_flash_timer = 0
        self.p2_line_flash_timer = 0
        self.p1_line_glow_alpha = 0
        self.p2_line_glow_alpha = 0
        self.p1_wave_effects = []
        self.p2_wave_effects = []
        self.p1_line_sweep_rows = []
        self.p2_line_sweep_rows = []
        self.p1_line_sweep_progress = 0.0
        self.p2_line_sweep_progress = 0.0
        self.p1_line_sweep_active = False
        self.p2_line_sweep_active = False
        self.p1_falling_block_animations = []
        self.p2_falling_block_animations = []
        self.p1_drop_trails = []
        self.p2_drop_trails = []
        
        # Partiküller ve ambient efektler sıfırla
        self.particles = []
        self.ambient_particles = []
        self.create_ambient_particles()
        
        # Screen shake sıfırla
        self.screen_shake = 0
        self.shake_intensity = 0
        
        if preserve_session and (self.player1_name and self.player2_name):
            # Aynı oturumla devam et: isim/ayar ekranını tekrar sorma.
            self.name_input_active = False
            self.current_input = 3
        else:
            # İsim giriş ekranına geri dön
            self.name_input_active = True
            self.current_input = 1
            self.player1_name = ''
            self.player2_name = ''
        
        # VS panel'i yenile
        self._vs_panel_dirty = True
        
        print("🔄 PvP oyunu tamamen sıfırlandı!")
    
    def draw_name_input(self):
        """Retro stile uygun PvP isim giriş ekranı."""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        retro_style.draw_background(self.screen)

        # Ana menü benzeri arka plan tetris blokları kayma/düşme efekti
        if self.effects_enabled and self.name_background_fx:
            self.name_background_fx.update(self.screen)
            self.name_background_fx.draw(self.screen)

        # Adım 3 ve 4 için farklı başlık
        if self.current_input >= 3:
            title_text = t('pvp_title_settings')
        else:
            title_text = t('pvp_title_names')
        title_rect = retro_style.draw_title(self.screen, title_text, (width // 2, s(110)))

        sub_font = retro_style.get_font(s(24, minimum=12), bold=False)
        sub_color = UIColors.TEXT_SECONDARY
        
        # Adıma göre focus color ve subtitle
        if self.current_input == 1:
            focus_color = UIColors.NEON_CYAN
            subtitle_text = t('pvp_subtitle_names')
        elif self.current_input == 2:
            focus_color = UIColors.NEON_MAGENTA
            subtitle_text = t('pvp_subtitle_names')
        elif self.current_input == 3:
            focus_color = UIColors.NEON_ORANGE
            subtitle_text = t('pvp_subtitle_mode')
        else:
            focus_color = UIColors.NEON_GOLD
            subtitle_text = t('pvp_subtitle_duration')
        
        subtitle = sub_font.render(subtitle_text, True, sub_color)
        self.screen.blit(subtitle, subtitle.get_rect(center=(width // 2, title_rect.bottom + s(28))))

        panel_w = min(s(900), width - s(160))
        panel_h = s(420) if self.current_input >= 3 else s(340)  # Mod seçimi için daha büyük panel
        panel_rect = pygame.Rect(width // 2 - panel_w // 2, title_rect.bottom + s(60), panel_w, panel_h)

        # Ana UI temasına uygun glass panel
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=195, border_color=focus_color)
        pygame.draw.rect(self.screen, (*focus_color, 120), panel_rect, 2, border_radius=16)

        if self.current_input <= 2:
            # İsim giriş alanları
            inner_pad_x = s(36)
            inner_pad_top = s(28)
            gap_y = s(28)
            field_height = s(116)
            field1 = pygame.Rect(panel_rect.x + inner_pad_x, panel_rect.y + inner_pad_top, panel_rect.width - inner_pad_x * 2, field_height)
            field2 = pygame.Rect(panel_rect.x + inner_pad_x, field1.bottom + gap_y, panel_rect.width - inner_pad_x * 2, field_height)
            # Tıklama tespiti için sakla
            self._name_field1_rect = field1.copy()
            self._name_field2_rect = field2.copy()

            self._draw_name_field(
                field1,
                t('pvp_player1_wasd'),
                self.player1_name,
                UIColors.NEON_CYAN,
                self.current_input == 1,
                ['W', 'A', 'S', 'D'],
            )
            self._draw_name_field(
                field2,
                t('pvp_player2_arrows'),
                self.player2_name,
                UIColors.NEON_MAGENTA,
                self.current_input == 2,
                ['UP', 'DN', 'LT', 'RT'],
            )

            progress_font = retro_style.get_font(s(20, minimum=12), bold=False)
            progress_text = progress_font.render(f'{t("pvp_step")} {self.current_input}/4', True, focus_color)
            self.screen.blit(progress_text, progress_text.get_rect(center=(width // 2, panel_rect.bottom + s(34))))
            
            # Progress bar (adım noktaları)
            dot_y = panel_rect.bottom + s(58)
            dot_radius = s(6)
            dot_spacing = s(24)
            total_dots = 4
            dots_start_x = width // 2 - (total_dots * dot_spacing) // 2 + dot_spacing // 2
            for dot_i in range(total_dots):
                dot_x = dots_start_x + dot_i * dot_spacing
                if dot_i + 1 <= self.current_input:
                    # Tamamlanmış adım - dolu
                    pygame.draw.circle(self.screen, focus_color, (dot_x, dot_y), dot_radius)
                else:
                    # Bekleyen adım - boş
                    pygame.draw.circle(self.screen, (60, 70, 90), (dot_x, dot_y), dot_radius)
                    pygame.draw.circle(self.screen, (80, 90, 110), (dot_x, dot_y), dot_radius, 1)

        else:
            # Mod seçimi ve süre ayarı
            self._draw_mode_selection(panel_rect)
    
    def _draw_name_field(self, rect, label, value, accent_color, is_active, keys):
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        # Oyuncu numarası etiketi (alan üstünde)
        label_font = retro_style.get_font(s(22, minimum=12), bold=True)
        label_color = accent_color if is_active else (140, 150, 170)
        self.screen.blit(label_font.render(label, True, label_color), (rect.x + s(2), rect.y - s(32)))

        field_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

        # Aktif alan için neon glow efekti
        if is_active:
            # Dıştaki parlak glow (büyük, soluk)
            glow_rect = field_surface.get_rect().inflate(s(8), s(8))
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            glow_color = (*accent_color[:3], 35)
            pygame.draw.rect(glow_surf, glow_color, glow_surf.get_rect(), border_radius=22)
            field_surface.blit(glow_surf, (-s(4), -s(4)))

            # Gradient arka plan (üstten alta koyu -> hafif aydınlık)
            for i in range(rect.height):
                ratio = i / max(1, rect.height - 1)
                r = int(15 + 20 * ratio)
                g = int(18 + 22 * ratio)
                b = int(30 + 30 * ratio)
                a = 230
                pygame.draw.line(field_surface, (r, g, b, a), (0, i), (rect.width, i))
        else:
            # İnaktif alan: düz koyu arka plan
            fill = (*UIColors.BG_MEDIUM[:3], 200) if hasattr(UIColors, 'BG_MEDIUM') else (22, 26, 40, 200)
            field_surface.fill(fill)

        # Border - aktif alan daha parlak
        border_color = accent_color if is_active else (60, 70, 90)
        border_width = 3 if is_active else 1
        pygame.draw.rect(field_surface, border_color, field_surface.get_rect(), border_width, border_radius=18)

        # İç highlight çizgisi (üst kenar)
        if is_active:
            highlight_color = (*accent_color[:3], 50)
            pygame.draw.line(field_surface, highlight_color, (s(12), 1), (rect.width - s(12), 1))

        # İsim metni
        display = value if value else t('pvp_enter_name')
        text_color = UIColors.TEXT_PRIMARY if value else (100, 110, 130)

        if is_active:
            # Yanıp sönen cursor
            import time
            cursor_visible = int(time.time() * 2) % 2 == 0
            if cursor_visible:
                display += '|'
            text_color = (255, 255, 255)

        name_font = retro_style.get_font(s(36, minimum=16), bold=True)
        clipped = display[:18]
        name_surface = name_font.render(clipped, True, text_color)
        name_rect = name_surface.get_rect(midleft=(s(24), int(field_surface.get_height() * 0.45)))
        field_surface.blit(name_surface, name_rect)

        # Alt bilgi metni
        hint_font = retro_style.get_font(s(16, minimum=10), bold=False)
        if is_active:
            hint_text = t('pvp_max_chars')
            hint_color = (*accent_color[:3],)
        else:
            hint_text = t('pvp_enter_confirm')
            hint_color = (100, 110, 130)
        hint_surface = hint_font.render(hint_text, True, hint_color)
        field_surface.blit(hint_surface, (s(24), field_surface.get_height() - s(30)))

        # Tuş göstergeleri
        key_color = accent_color if is_active else (80, 90, 110)
        self._draw_keycaps(field_surface, keys, key_color, is_active)

        self.screen.blit(field_surface, rect.topleft)

    def _draw_keycaps(self, surface, keys, color, is_active=False):
        if not keys:
            return
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        cap_font = retro_style.get_font(s(16, minimum=10), bold=True)
        cap_size = s(32)
        spacing = s(8)
        total_width = len(keys) * cap_size + (len(keys) - 1) * spacing
        start_x = surface.get_width() - total_width - s(20)
        y = surface.get_height() - cap_size - s(14)
        for idx, key in enumerate(keys):
            cap_rect = pygame.Rect(start_x + idx * (cap_size + spacing), y, cap_size, cap_size)
            # Arka plan
            bg_color = (15, 18, 30) if is_active else (8, 10, 24)
            pygame.draw.rect(surface, bg_color, cap_rect, border_radius=8)
            # Border
            pygame.draw.rect(surface, color, cap_rect, 2, border_radius=8)
            # İç parlama
            if is_active:
                inner = cap_rect.inflate(-6, -6)
                pygame.draw.rect(surface, (*color[:3], 20), inner, border_radius=5)
            # Tuş etiketi
            label = cap_font.render(key, True, color)
            surface.blit(label, label.get_rect(center=cap_rect.center))

    def _draw_mode_selection(self, panel_rect):
        """Mod seçimi ve süre ayarı ekranını çiz."""
        width = self.window_width
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # Panel başlığı
        title_label_rect = pygame.Rect(panel_rect.x + s(18), panel_rect.y + s(14), panel_rect.width - s(36), s(26))
        title_label = retro_style.render_fit_text(t('pvp_match_settings'), UIColors.NEON_GOLD, title_label_rect.width, s(20, minimum=12), bold=True)
        self.screen.blit(title_label, title_label.get_rect(midleft=(title_label_rect.left, title_label_rect.centery)))
        
        inner_pad_x = s(36)
        inner_pad_top = s(56)
        
        # Mod seçimi
        mode_y = panel_rect.y + inner_pad_top
        mode_label_font = retro_style.get_font(s(24, minimum=12), bold=True)
        mode_value_font = retro_style.get_font(s(32, minimum=14))
        
        mode_label = mode_label_font.render(t('pvp_match_mode'), True, UIColors.TEXT_PRIMARY)
        self.screen.blit(mode_label, (panel_rect.x + inner_pad_x, mode_y))
        
        # Mod butonları - kullanıcı değiştir ekranı stili
        btn_width = s(150)
        btn_height = s(50)
        btn_gap = s(30)
        total_btn_width = btn_width * 2 + btn_gap
        btn_start_x = panel_rect.centerx - total_btn_width // 2
        btn_y = mode_y + s(40)
        
        # Süreli mod butonu
        timed_rect = pygame.Rect(btn_start_x, btn_y, btn_width, btn_height)
        self._timed_btn_rect = timed_rect  # Fare için sakla
        timed_active = self.match_mode == 'timed'
        # Aktif: cyan arka plan + beyaz yazi, Pasif: koyu arka plan + gri yazi
        timed_bg = UIColors.NEON_CYAN if timed_active else (45, 55, 70)
        timed_text_color = (15, 25, 35) if timed_active else UIColors.TEXT_SECONDARY
        pygame.draw.rect(self.screen, timed_bg, timed_rect, border_radius=s(14))
        pygame.draw.rect(self.screen, (255, 255, 255, 100) if timed_active else (80, 90, 110), timed_rect, 2, border_radius=s(14))
        timed_text = mode_value_font.render(t('pvp_timed'), True, timed_text_color)
        self.screen.blit(timed_text, timed_text.get_rect(center=timed_rect.center))
        
        # Süresiz mod butonu
        endless_rect = pygame.Rect(btn_start_x + btn_width + btn_gap, btn_y, btn_width, btn_height)
        self._endless_btn_rect = endless_rect  # Fare için sakla
        endless_active = self.match_mode == 'endless'
        # Aktif: koyu mor arka plan + beyaz yazi, Pasif: koyu arka plan + gri yazi
        endless_bg = (100, 60, 130) if endless_active else (45, 55, 70)
        endless_text_color = (255, 255, 255) if endless_active else UIColors.TEXT_SECONDARY
        pygame.draw.rect(self.screen, endless_bg, endless_rect, border_radius=s(14))
        pygame.draw.rect(self.screen, (255, 255, 255, 100) if endless_active else (80, 90, 110), endless_rect, 2, border_radius=s(14))
        endless_text = mode_value_font.render(t('pvp_endless'), True, endless_text_color)
        self.screen.blit(endless_text, endless_text.get_rect(center=endless_rect.center))
        
        # Mod açıklaması
        desc_font = retro_style.get_font(s(18, minimum=10), bold=False)
        if self.match_mode == 'timed':
            desc_text = t('pvp_timed_desc')
        else:
            desc_text = t('pvp_endless_desc')
        desc = desc_font.render(desc_text, True, UIColors.TEXT_SECONDARY)
        self.screen.blit(desc, desc.get_rect(center=(panel_rect.centerx, btn_y + btn_height + s(25))))
        
        # Başla butonu (süresiz modda)
        start_btn_y = btn_y + btn_height + s(60)
        start_btn_rect = pygame.Rect(panel_rect.centerx - s(100), start_btn_y, s(200), s(50))
        self._start_btn_rect = start_btn_rect
        
        if self.match_mode == 'endless':
            # Süresiz modda direkt başla butonu göster
            start_bg = (55, 140, 90)  # Yesil arka plan
            pygame.draw.rect(self.screen, start_bg, start_btn_rect, border_radius=s(14))
            pygame.draw.rect(self.screen, (255, 255, 255, 100), start_btn_rect, 2, border_radius=s(14))
            start_text = mode_value_font.render(t('pvp_start'), True, (255, 255, 255))
            self.screen.blit(start_text, start_text.get_rect(center=start_btn_rect.center))
        
        # Süre ayarı (sadece süreli modda göster)
        if self.match_mode == 'timed':
            duration_y = btn_y + btn_height + s(60)
            duration_label = mode_label_font.render(t('pvp_match_duration'), True, UIColors.TEXT_PRIMARY)
            self.screen.blit(duration_label, (panel_rect.x + inner_pad_x, duration_y))
            
            # Süre seçici
            slider_y = duration_y + s(45)
            
            # Sol ok butonu - kullanici ekrani stili
            arrow_size = s(50)
            left_arrow_rect = pygame.Rect(panel_rect.centerx - s(150), slider_y, arrow_size, arrow_size)
            self._left_arrow_rect = left_arrow_rect  # Fare için sakla
            left_hover = self.current_input == 4
            left_bg = (70, 85, 110) if left_hover else (45, 55, 70)
            pygame.draw.rect(self.screen, left_bg, left_arrow_rect, border_radius=s(10))
            pygame.draw.rect(self.screen, (255, 255, 255, 100) if left_hover else (80, 90, 110), left_arrow_rect, 2, border_radius=s(10))
            # Ok çizimi (Unicode yerine polygon)
            arrow_color = (255, 255, 255) if left_hover else UIColors.TEXT_SECONDARY
            cx, cy = left_arrow_rect.center
            arrow_points = [(cx + s(8), cy - s(12)), (cx - s(8), cy), (cx + s(8), cy + s(12))]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points)
            
            # Süre değeri
            duration_value = retro_style.get_font(s(48, minimum=18), bold=True)
            duration_text = duration_value.render(f'{self.custom_duration_minutes} {t("pvp_minutes")}', True, UIColors.NEON_GOLD)
            self.screen.blit(duration_text, duration_text.get_rect(center=(panel_rect.centerx, slider_y + arrow_size // 2)))
            
            # Sağ ok butonu - kullanici ekrani stili
            right_arrow_rect = pygame.Rect(panel_rect.centerx + s(100), slider_y, arrow_size, arrow_size)
            self._right_arrow_rect = right_arrow_rect  # Fare için sakla
            right_hover = self.current_input == 4
            right_bg = (70, 85, 110) if right_hover else (45, 55, 70)
            pygame.draw.rect(self.screen, right_bg, right_arrow_rect, border_radius=s(10))
            pygame.draw.rect(self.screen, (255, 255, 255, 100) if right_hover else (80, 90, 110), right_arrow_rect, 2, border_radius=s(10))
            # Ok çizimi (Unicode yerine polygon)
            cx, cy = right_arrow_rect.center
            arrow_points = [(cx - s(8), cy - s(12)), (cx + s(8), cy), (cx - s(8), cy + s(12))]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points)
            
            # Süre aralığı bilgisi
            range_text = desc_font.render(t('pvp_duration_range'), True, UIColors.TEXT_SECONDARY)
            self.screen.blit(range_text, range_text.get_rect(center=(panel_rect.centerx, slider_y + arrow_size + s(20))))
            
            # Başla butonu - kullanici ekrani stili
            start_btn_y = slider_y + arrow_size + s(50)
            start_btn_rect = pygame.Rect(panel_rect.centerx - s(100), start_btn_y, s(200), s(50))
            self._start_btn_rect = start_btn_rect
            start_bg = (55, 140, 90)  # Yesil arka plan
            pygame.draw.rect(self.screen, start_bg, start_btn_rect, border_radius=s(14))
            pygame.draw.rect(self.screen, (255, 255, 255, 100), start_btn_rect, 2, border_radius=s(14))
            start_text = mode_value_font.render(t('pvp_start'), True, (255, 255, 255))
            self.screen.blit(start_text, start_text.get_rect(center=start_btn_rect.center))
        
        # İlerleme ve footer
        progress_font = retro_style.get_font(s(20, minimum=12), bold=False)
        current_step = 4 if (self.current_input == 4 or (self.current_input == 3 and self.match_mode == 'endless')) else 3
        max_step = 3 if self.match_mode == 'endless' else 4
        focus_color = UIColors.NEON_GOLD if self.current_input == 4 else UIColors.NEON_ORANGE
        progress_text = progress_font.render(f'{t("pvp_step")} {min(self.current_input, max_step)}/{max_step}', True, focus_color)
        self.screen.blit(progress_text, progress_text.get_rect(center=(width // 2, panel_rect.bottom + s(34))))
        

    
    def _handle_setup_mouse_click(self, pos):
        """Mod seçimi ekranında fare tıklamalarını işle."""
        if self.current_input <= 2:
            # İsim alanlarına tıklama ile odak değiştir
            if hasattr(self, '_name_field1_rect') and self._name_field1_rect.collidepoint(pos):
                if self.current_input != 1:
                    self.current_input = 1
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                return True
            if hasattr(self, '_name_field2_rect') and self._name_field2_rect.collidepoint(pos):
                if self.current_input != 2:
                    self.current_input = 2
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                return True
            return False

        if self.current_input >= 3:
            # Süreli mod butonu
            if hasattr(self, '_timed_btn_rect') and self._timed_btn_rect.collidepoint(pos):
                self.match_mode = 'timed'
                self.current_input = 4  # Süre ayarına geç
                self._vs_panel_dirty = True
                self.sound.play('move')
                return True
            
            # Süresiz mod butonu
            if hasattr(self, '_endless_btn_rect') and self._endless_btn_rect.collidepoint(pos):
                self.match_mode = 'endless'
                self._vs_panel_dirty = True
                self.sound.play('move')
                return True
            
            # Sol ok butonu (süre azalt)
            if hasattr(self, '_left_arrow_rect') and self._left_arrow_rect.collidepoint(pos):
                if self.match_mode == 'timed':
                    self.custom_duration_minutes = max(1, self.custom_duration_minutes - 1)
                    self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                    return True
            
            # Sağ ok butonu (süre artır)
            if hasattr(self, '_right_arrow_rect') and self._right_arrow_rect.collidepoint(pos):
                if self.match_mode == 'timed':
                    self.custom_duration_minutes = min(10, self.custom_duration_minutes + 1)
                    self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                    return True
            
            # Başla butonu
            if hasattr(self, '_start_btn_rect') and self._start_btn_rect.collidepoint(pos):
                self.name_input_active = False
                self._vs_panel_dirty = True
                self.match_active = False
                self.match_elapsed_ms = 0
                self.match_end_reason = None
                self._last_timer_seconds = None
                self.sound.play('rotate')
                return True
        
        return False

    def run(self):
        """Ana oyun döngüsü"""
        running = True
        
        while running:
            try:
                fps_limit = int(self.settings_manager.get('fps_limit', 0) or 0) if self.settings_manager else 0
            except Exception:
                fps_limit = 0
            delta_time = self.clock.tick(fps_limit if fps_limit > 0 else 0)
            
            running = self.handle_input()
            self.update(delta_time)
            self.draw()
        
        pygame.quit()
