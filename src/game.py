"""Quadrix oyun mantığını yönetir"""
import os
import random
import math
import hashlib
import sys
from pathlib import Path
from typing import Dict, List

import pygame
from dataclasses import replace

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _np = None
    _NUMPY_AVAILABLE = False

from block_styles import BlockStyleManager, TextureSlice, TextureRenderCache
from board import Board
from pieces import Piece, SHAPE_NAMES, create_piece_by_index, create_piece_by_name
from constants import *
from sound import SoundManager
from score_manager import ScoreManager
from user_manager import DAILY_MAX_FAILURES
from background import BackgroundManager
from mode_skins import apply_board_tint, apply_outer_tint, draw_board_overlay, get_mode_skin, get_localized_skin_title, get_localized_skin_subtitle
from background_effects import get_shared_falling_blocks_layer
from workshop_blocks import WorkshopBlockDefinition, load_workshop_blocks
from retro_style import retro_style
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from localization import t, get_language
from platform_utils import get_display_flags, create_display, set_app_icon, normalize_mouse_pos, get_mouse_pos
from ui_theme import UIFonts, UIColors
from asset_manager import load_image
from gamepad_manager import get_gamepad_manager, is_gamepad_connected
from effect_surface_cache import EffectSurfaceCache
from sweep_effects import SweepCatState, draw_rainbow_cat_sweep

def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        # CWD'ye güvenme: macOS'ta uygulama farklı bir dizinden başlayabilir.
        # Repo düzeni: <root>/src/<this_file>
        base_path = Path(__file__).resolve().parents[1]
    return os.path.normpath(str(base_path / relative_path))


class Game:
    """Ana oyun sınıfı"""

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.20) -> float:
        """Pencere boyutuna bağlı genel UI ölçeği."""
        try:
            scale = min(float(self.window_width) / 1366.0, float(self.window_height) / 768.0)
        except Exception:
            scale = 1.0
        return max(min_scale, min(max_scale, scale))

    def _sx(self, value: int | float, scale: float | None = None, minimum: int = 1) -> int:
        """Sabit piksel değeri UI ölçeği ile dönüştür."""
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    @staticmethod
    def _binding_from_config(binding, slot: str):
        if isinstance(binding, dict):
            return binding.get(slot)
        return binding

    @staticmethod
    def _binding_to_keycode_or_none(binding):
        if binding is None:
            return None
        if isinstance(binding, str) and not binding.strip():
            return None
        if isinstance(binding, int):
            return binding
        if isinstance(binding, str):
            try:
                return pygame.key.key_code(binding)
            except ValueError:
                return None
        return None

    def _action_keys(self, bindings: dict, action: str) -> tuple:
        primary = bindings.get(action)
        keys: list[int] = []
        if isinstance(primary, int):
            keys.append(primary)
        secondary = getattr(self, 'alt_control_bindings', {}).get(action)
        if isinstance(secondary, int) and secondary != primary:
            keys.append(secondary)
        return tuple(keys)

    @staticmethod
    def _is_focus_loss_event(event) -> bool:
        event_type = getattr(event, 'type', None)
        if event_type is None:
            return False

        focus_loss_types = (
            getattr(pygame, 'WINDOWFOCUSLOST', None),
            getattr(pygame, 'WINDOWMINIMIZED', None),
            getattr(pygame, 'WINDOWHIDDEN', None),
            getattr(pygame, 'APP_WILLENTERBACKGROUND', None),
            getattr(pygame, 'APP_DIDENTERBACKGROUND', None),
        )
        if any(focus_type is not None and event_type == focus_type for focus_type in focus_loss_types):
            return True

        window_event_type = getattr(pygame, 'WINDOWEVENT', None)
        if window_event_type is not None and event_type == window_event_type:
            window_subtype = getattr(event, 'event', None)
            if any(
                focus_type is not None and window_subtype == focus_type
                for focus_type in focus_loss_types[:3]
            ):
                return True

        active_event_type = getattr(pygame, 'ACTIVEEVENT', None)
        if active_event_type is not None and event_type == active_event_type:
            gain = getattr(event, 'gain', 1)
            state = getattr(event, 'state', 0)
            focus_mask = 0
            for attr_name in ('APPINPUTFOCUS', 'APPACTIVE'):
                attr_value = getattr(pygame, attr_name, 0)
                if isinstance(attr_value, int):
                    focus_mask |= attr_value
            return gain == 0 and (state == 0 or focus_mask == 0 or bool(state & focus_mask))

        return False

    def _pause_for_focus_loss(self) -> bool:
        if getattr(self, 'paused', False):
            return False
        if getattr(self, 'game_over', False) or getattr(self, 'show_exit_prompt', False):
            return False
        if getattr(self, 'level_complete', False) or getattr(self, 'level_failed', False):
            return False
        for modal_attr in (
            'card_selection_active',
            '_piece_selection_active',
            '_card_workshop_active',
            '_sniper_overlay_active',
        ):
            if getattr(self, modal_attr, False):
                return False

        self.paused = True
        self.pause_menu_selected = 0
        if hasattr(self, 'sound') and self.sound:
            try:
                self.sound.duck_music()
            except Exception:
                pass
        return True

    def _draw_hud_glass_panel(self, rect: pygame.Rect) -> None:
        """Sağ panelin temel cam panel stilini tek yerden uygula."""
        retro_style.draw_glass_panel(self.screen, rect, alpha=90, border_color=(60, 70, 90))

    def _draw_custom_frame(self, rect: pygame.Rect, asset_name: str, padding: int = 0, hole_punch: bool = False) -> bool:
        """Belirtilen asset varsa rect üzerine (padding ekleyerek) ortalayıp çizer.
        
        Args:
            rect: Çerçevenin etrafına sarılacağı alan (örn: board_rect)
            asset_name: Dosya adı
            padding: Asset'in rect dışına ne kadar taşacağı (border kalınlığı gibi)
            hole_punch: True ise, rect'in kapladığı orta alan çizilmez (maskelenir).
                        Böylece frame efektlerinin oyun alanını kapatması engellenir.
        """
        try:
            # Asset yolunu bul - Öncelik game_ui, sonra ui
            found_path = None
            for folder in ["assets/game_ui", "assets/ui"]:
                p = resource_path(f"{folder}/{asset_name}")
                if os.path.exists(p):
                    found_path = p
                    break
            
            if not found_path:
                return False
            
            # Hedef boyut (scale edilmiş)
            # Frame, rect'ten daha büyük olmalı (padding kadar)
            target_w = int(rect.width + (padding * 2))
            target_h = int(rect.height + (padding * 2))
            
            # Asset load & scale
            # load_image cache kullandığı için performans sorunu yaratmaz
            img = load_image(found_path, size=(target_w, target_h), convert_alpha=True)
            
            # Çizim kordinatları (merkezden hizala)
            draw_x = rect.centerx - (target_w // 2)
            draw_y = rect.centery - (target_h // 2)
            
            if hole_punch and padding > 0:
                # ORTA ALANI BOŞ BIRAKARAK ÇİZ (4 PARÇA BLIT)
                # Bu yöntem, görselin ortasında ne olursa olsun oyun alanını temiz tutar.
                
                # Top Strip: Tüm genişlik, üst padding kadar yükseklik
                self.screen.blit(img, (draw_x, draw_y), (0, 0, target_w, padding))
                
                # Bottom Strip: Tüm genişlik, alt padding
                self.screen.blit(img, (draw_x, draw_y + target_h - padding), (0, target_h - padding, target_w, padding))
                
                # Left Strip: Sol padding, orta yükseklik (rect.height)
                # Y koordinatı: draw_y + padding
                self.screen.blit(img, (draw_x, draw_y + padding), (0, padding, padding, rect.height))
                
                # Right Strip: Sağ padding, orta yükseklik
                # X koordinatı: draw_x + target_w - padding
                self.screen.blit(img, (draw_x + target_w - padding, draw_y + padding), (target_w - padding, padding, padding, rect.height))
            else:
                # Normal çizim (tüm görsel)
                self.screen.blit(img, (draw_x, draw_y))
                
            return True
        except Exception:
            return False

    def wants_mouse_visible(self) -> bool:
        """Oyun sırasında mouse görünür mü?

        İstenen davranış:
        - Normal gameplay: gizli
        - Pause/ESC overlay / oyun sonu gibi UI overlay'leri: görünür
        """
        if getattr(self, 'paused', False):
            return True
        if getattr(self, 'show_exit_prompt', False):
            return True
        if getattr(self, 'game_over', False):
            return True
        return False

    def _particle_effects_enabled(self) -> bool:
        """Parçacık/patlama/ekran titremesi gibi FX'ler açık mı?"""
        if not getattr(self, 'effects_enabled', True):
            return False
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            # Sade varsayılan: ayar yöneticisi yoksa FX kapalı.
            return False
        try:
            return bool(sm.get('particle_effects', False))
        except Exception:
            return False

    def _get_ambient_sprite(self, radius: int, alpha: int, glow: bool) -> pygame.Surface:
        radius = max(1, int(radius))
        alpha = max(0, min(255, int(alpha)))
        draw_radius = radius * (2 if glow else 1)
        return self._effect_surface_cache.get_circle_surface(draw_radius, (200, 200, 255, alpha))
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=True, settings_manager=None, user_manager=None, game_mode='classic', sound_manager=None, block_style_manager: BlockStyleManager | None = None, score_manager: ScoreManager | None = None, piece_rng_seed: int | None = None):
        """Oyunu başlat"""
        pygame.init()
        
        # Settings manager
        self.settings_manager = settings_manager
        self.workshop_blocks_by_mode = self._load_workshop_blocks()
        
        # User manager
        self.user_manager = user_manager
        self.game_mode = game_mode.lower()  # Oyun modunu sakla (classic, sprint, ultra, zen, vb.)
        self.mode_skin = get_mode_skin(self.game_mode)

        # In-game exit confirmation overlay (ESC)
        self.show_exit_prompt = False
        self.exit_yes_rect = None
        self.exit_no_rect = None
        
        # Eğer ekran verilmişse onu kullan, yoksa yeni oluştur
        if screen is not None:
            self.screen = screen
            self.window_width = screen.get_width()
            self.window_height = screen.get_height()
            self.fullscreen = True
        else:
            self.fullscreen = True
            self.screen = create_display(0, 0, fullscreen=True, resizable=False, borderless=True)
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
        
        try:
            pygame.display.set_caption('Quadrix')
        except Exception:
            pass
        try:
            import os
            _g_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
            set_app_icon(_g_assets)
        except Exception:
            pass
        self.clock = pygame.time.Clock()

        # FPS measurement: when the game is driven from src/main.py, this
        # clock may not be ticked, so pygame's get_fps() stays at 0.
        # We compute a rolling FPS from the delta_time passed into update().
        self._fps_value: float = 0.0
        self._fps_accum_ms: float = 0.0
        self._fps_frames: int = 0
        
        # Ayarlar
        self.difficulty = difficulty
        self.sound_enabled = sound_enabled
        self.effects_enabled = effects_enabled
        
        # Animasyon seviyesi (low, medium, medium-high, high)
        # medium-high = orta-belirgin - default
        animation_level = 'medium-high'
        if self.settings_manager:
            animation_level = self.settings_manager.get('animation_level', 'medium-high')
        self.animation_multiplier = self._get_animation_multiplier(animation_level)
        
        # Tema ve blok stili yöneticileri
        self.theme_manager = theme_manager
        if block_style_manager is not None:
            self.block_style_manager = block_style_manager
        elif self.settings_manager:
            self.block_style_manager = BlockStyleManager(self.settings_manager)
        else:
            self.block_style_manager = None
        self._texture_render_cache = TextureRenderCache()
        self._effect_surface_cache = EffectSurfaceCache()
        
        # Ses yöneticisi (menü ile paylaşılabilir)
        self.sound = sound_manager or SoundManager()
        self.sound.enabled = True  # Sound manager her zaman enabled (müzik için)
        self.sound.sfx_enabled = sound_enabled  # Ses efektleri kontrolü
        # Müzik ve ses ayarlarını settings'ten al
        if self.settings_manager:
            self.sound.music_enabled = self.settings_manager.get('music_enabled', True)
            # Ses seviyelerini yükle
            saved_music_vol = self.settings_manager.get('music_volume', 0.3)
            saved_sfx_vol = self.settings_manager.get('sfx_volume', 0.5)
            self.sound.set_music_volume(saved_music_vol)
            self.sound.set_volume(saved_sfx_vol)
        self.control_bindings = self._resolve_single_player_controls()
        self.alt_control_bindings = self._resolve_single_player_secondary_controls(self.control_bindings)
        
        # Müzik durumu
        self.current_music_track = None
        
        # Skor yöneticisi
        self.score_manager = score_manager or ScoreManager()
        self._score_recorded = False
        
        # Arka plan yöneticileri
        self.background_manager = BackgroundManager()  # Ana arka plan
        self.single_background = BackgroundManager()  # Tek oyunculu oyun alanı için ayrı arka plan
        self.outer_background = BackgroundManager()  # Oyun alanı dışındaki alan için arka plan
        
        # Transparanlık ayarını yükle ve uygula
        bg_transparency = self.settings_manager.get('bg_transparency', 0.9)
        self.background_manager.set_transparency(bg_transparency)
        self.single_background.set_transparency(bg_transparency)
        self.outer_background.set_transparency(bg_transparency)
        
        self.load_background_image()
        self.load_single_background()
        self.load_outer_background()
        
        # Başarı yöneticisi
        self.achievement_manager = achievement_manager
        self.achievement_notifications = []  # Yeni başarı bildirimleri
        self._achievement_notif_surface_cache = {}
        self.allow_auto_lock = True
        self.grounded = False
        self.notification_time = 0
        
        # Board boyutları (child class'lar override edebilir)
        if not hasattr(self, 'board_width'):
            self.board_width = BOARD_WIDTH
        if not hasattr(self, 'board_height'):
            self.board_height = BOARD_HEIGHT
        
        # Oyun durumu
        self.board = Board(width=self.board_width, height=self.board_height)

        # Parça RNG (parça sırası deterministik olabilsin)
        self._piece_rng_seed = piece_rng_seed
        self._piece_rng = random.Random()
        if self._piece_rng_seed is not None:
            self._piece_rng.seed(self._piece_rng_seed)

        # Parça rastgeleliği: aynı parçanın üst üste 3'ten fazla gelmesini engelle.
        # (Tüm modlar super().spawn_new_piece() üzerinden bu kuralı alır.)
        self._max_consecutive_same_piece = 3
        self._last_piece_identity = None
        self._last_piece_streak = 0

        # Torba (Bag) Sistemi: pool'daki her parça tipinden _bag_copies kadar
        # kopya torbaya atılıp karıştırılır.  Torba bitene kadar sırayla çekilir,
        # bitince yeni torba oluşturulur.  Workshop parçaları da otomatik dahil.
        self._piece_bag: list = []
        self._bag_copies: int = 3  # Her parça tipinden kaç kopya

        # Parça RNG'yi varsa seed'le
        if getattr(self, '_piece_rng_seed', None) is not None and hasattr(self, '_piece_rng'):
            try:
                self._piece_rng.seed(self._piece_rng_seed)
            except Exception:
                pass

        # Önce kuyruğu doldur, sonra kuyruktan al (senkronizasyon için)
        self.next_piece_queue = [self.spawn_new_piece() for _ in range(3)]  # Sonraki 3 parça
        self.current_piece = self.next_piece_queue.pop(0)  # Kuyruktan ilk parçayı al
        self.held_piece = None  # Saklanan parça
        # Second pocket (V) - used by Mystery Mode perk and unit tests
        self.second_held_piece = None
        self.can_hold2 = True
        self.can_hold = True  # Bu turda hold kullanılabilir mi?
        self.discard_held_uses = 5  # B tuşu ile saklanan parçayı silme hakkı (oyun başına 5)
        self.game_over = False
        self.paused = False
        self.game_over_warning = ""
        self.game_over_warning_timer = 0.0
        
        # Duraklama menüsü
        self.pause_menu_selected = 0
        self.pause_menu_options = ['Devam Et', 'Yeniden Başlat', 'Müzik', 'Müzik Seviyesi', 'Ses Efektleri', 'Efekt Seviyesi', 'Ana Menü']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active: bool = False
        self._pause_vol_drag_option: str = ''
        
        # Tema renklerini parçalara uygula
        self.apply_theme_to_pieces()
        
        # Zamanlama
        self.fall_time = 0
        self.fall_speed = self.get_initial_speed()  # Başlangıç hızı
        
        # Lock Delay Sistemi (Yere Değince Kilitlenme Gecikmesi)
        self.lock_timer = 0
        self.lock_delay = DEFAULT_LOCK_DELAY  # Sabitler modülünden
        self.enable_lock_delay = True  # Her zaman açık
        self.lock_reset_count = 0  # Move reset sayacı (infinity engellemek için)
        self.game_time = 0  # Toplam oyun süresi
        
        # Animasyon
        self.line_clear_animation = 0
        self.line_clear_flash = False
        
        # Satır temizleme efekt sistemi - Sweep (soldan sağa ışık süpürmesi)
        self.line_clear_sweep_rows = []  # Sweep efekti gösterilecek satırlar
        self.line_clear_sweep_progress = 0.0  # 0.0 - 1.0 arası ilerleme
        self.line_clear_sweep_active = False
        self.line_clear_wave_effects = []  # Dalga efektleri listesi
        self.line_clear_pending_rows = []
        self.line_clear_pending_colors = {}
        self._sweep_cat_asset_checked = False
        self._sweep_cat_base_surface = None
        self._sweep_cat_surface_cache = {}
        self._sweep_cat_frame_base_surfaces = []
        self._sweep_cat_frame_surface_cache = {}
        self._sweep_cat_paw_profile = None
        self._sweep_cat_state = SweepCatState()
        
        # Blok düşme animasyonu sistemi
        self.falling_block_animations = []  # Düşen blokların animasyon verileri
        self.block_fall_speed = 0.12  # Düşme hızı
        
        # Drop trail efekti (hard drop ve soft drop için)
        self.drop_trails = []  # [{x, y, color, alpha, width, height}]
        
        # Combo ve mesajlar
        self.combo_message = ""
        self.combo_message_time = 0
        self.show_fps = False
        
        # Partiküller
        self.particles = []
        
        # Arka plan parçacıkları (ambient effect)
        self.ambient_particles = []
        self.create_ambient_particles()

        # Ana menüdekiyle aynı düşen tetromino katmanı
        self.falling_blocks = get_shared_falling_blocks_layer('default') if self.effects_enabled else None
        
        # Screen shake efekti
        self.screen_shake = 0  # Kalan shake süresi
        self.shake_intensity = 0  # Titreme şiddeti

        # HUD seçenekleri
        self.controls_under_stats = False
        
        # Havai fişek sistemi (her 1000 puan)
        self.last_milestone_score = 0  # Son kutlanan milestone skoru
        self.firework_active = False
        self.firework_time = 0
        
        # DAS (Delayed Auto Shift) - Yatay hareket için basılı tutma sistemi
        self.das_direction = 0  # -1: sol, 0: yok, 1: sağ
        self.das_timer = 0  # İlk gecikme sayacı (ms)
        self.das_repeat_timer = 0  # Tekrar sayacı (ms)
        self.das_charged = False  # İlk gecikme tamamlandı mı?
        
        # Fontlar (dinamik olarak güncellenecek)
        # CJK dil profili: oyun başlarken retro_style ve UIFonts profilleri
        # mevcut dile uygun olsun (menüden kalma uyumsuzlukları gider).
        try:
            from ui_language_profile import apply_language_ui_profile as _alup
            from localization import get_language as _gl
            _alup(_gl())
        except Exception:
            pass
        self.update_fonts()
        
        # OYUN İÇİ MÜZİĞİ BAŞLAT
        # Müzik için music_enabled kontrolü yap (sound_enabled ses efektleri için)
        if self.sound.music_enabled:  # Sadece music_enabled kontrolü
            self._start_music_playlist()
        # Shape Mutation cooldown (seconds) and related state
        self._shape_mutation_cooldown = 0.0
        
        # ============================================
        # GAME OVER ANİMASYON SİSTEMİ
        # ============================================
        # Durum yönetimi: pending (bekleme) -> active (aktif)
        self._game_over_pending = False  # Oyun bitti ama efekt bekliyor
        self._game_over_pending_timer = 0.0  # Bekleme süresi (saniye)
        self._game_over_active = False  # Sonuç ekranı aktif
        self._game_over_start_time = 0  # Ekran açılma zamanı (ms)
        
        # Sonuç verileri (bitti anında dondurulur)
        self._final_score = 0
        self._final_lines = 0
        self._final_level = 1
        self._final_tetrises = 0
        self._final_time = 0
        self._final_max_combo = 0
        self._is_new_record = False
        
        # Yıldız sistemi (0.0-5.0 arası float)
        self._earned_stars = 0.0
        self._last_star_sound = 0  # Ses efekti için son gösterilen yıldız
        
        # Skor sayım animasyonu
        self._displayed_score = 0  # Ekranda gösterilen (animasyonlu)
        self._score_count_speed = 0  # Sayım hızı (puan/saniye)
        
        # Konfeti/kutlama efekti
        self._confetti_particles = []
        self._confetti_active = False
        
        # Fade animasyonu
        self._game_over_fade_alpha = 0  # 0-255 arası
    
    def apply_theme_to_pieces(self):
        """Tema renklerini mevcut parçalara uygula"""
        if not self.theme_manager:
            return

        targets = [self.current_piece, self.held_piece, *self.next_piece_queue]
        for piece in targets:
            self._apply_block_style(piece)

    def _start_music_playlist(self, force=False):
        if not self.sound or not self.sound.music_enabled:
            return

        playlist_values = []
        if self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_music_playlist_for_mode(self.game_mode)
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
                self.sound.set_music_playlist(track_keys, loop=True, start_index=start_index, autoplay=True, force=force, shuffle=do_shuffle)
                self.current_music_track = track_keys[start_index]
                return

        preference = None
        if self.settings_manager:
            preference = self.settings_manager.get_music_preference_for_mode(self.game_mode)
        track_key = self.sound.ensure_track_available(preference or 'klasik_1')
        if track_key:
            self.sound.play_music(track_key, loop=True, force=force)
            self.current_music_track = track_key

    def _resolve_single_player_controls(self):
        defaults = {
            'move_left': pygame.K_LEFT,
            'move_right': pygame.K_RIGHT,
            'soft_drop': pygame.K_DOWN,
            'hard_drop': pygame.K_SPACE,
            'rotate': pygame.K_UP,
            'hold': pygame.K_c,
            'hold2': pygame.K_v,
            'pause': pygame.K_p,
            'toggle_fps': pygame.K_f,
        }
        if not self.settings_manager:
            return defaults
        config = self.settings_manager.get_controls().get('single_player', {})
        resolved = {}
        for action, fallback in defaults.items():
            binding = self._binding_from_config(config.get(action), 'primary')
            resolved[action] = self._binding_to_keycode(binding, fallback)
        return resolved

    def _resolve_single_player_secondary_controls(self, primary_bindings: dict | None = None):
        defaults = {
            'move_left': pygame.K_a,
            'move_right': pygame.K_d,
            'soft_drop': pygame.K_s,
            'rotate': pygame.K_w,
        }
        resolved: dict[str, int | None] = {
            'move_left': None,
            'move_right': None,
            'soft_drop': None,
            'hard_drop': None,
            'rotate': None,
            'hold': None,
            'hold2': None,
            'pause': None,
            'toggle_fps': None,
        }
        if not self.settings_manager:
            for action, fallback in defaults.items():
                resolved[action] = fallback
            return resolved

        config = self.settings_manager.get_controls().get('single_player', {})
        for action in resolved.keys():
            binding = self._binding_from_config(config.get(action), 'secondary')
            keycode = self._binding_to_keycode_or_none(binding)
            if keycode is None:
                keycode = defaults.get(action)
            resolved[action] = keycode

        if isinstance(primary_bindings, dict):
            for action, primary in primary_bindings.items():
                if resolved.get(action) == primary:
                    resolved[action] = None
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

    def _apply_block_style(self, piece: Piece | None) -> None:
        """Apply theme color and custom texture to the given piece."""
        if not piece:
            return
        if getattr(piece, '_force_color', None) is not None:
            base_color = piece._force_color
        elif getattr(piece, 'is_workshop_piece', False):
            # Workshop pieces define their own colors; do not let block style colors override them.
            base_color = piece.color
        else:
            base_color = self.theme_manager.get_piece_color(piece.name) if self.theme_manager else piece.color
        if self.block_style_manager:
            if getattr(piece, 'is_workshop_piece', False):
                style_key = getattr(piece, 'style_key', None) or piece.name
                piece.color = base_color
                # If the workshop piece is multi-color, keep it non-textured so
                # per-cell colors remain visible.
                if getattr(piece, 'color_matrix', None) is not None:
                    piece.texture_path = None
                    piece.texture_surface_original = None
                    piece.texture_surface = None
                else:
                    texture_path = self.block_style_manager.get_texture_path(style_key)
                    piece.texture_path = texture_path
                    surface = self.block_style_manager.get_texture_surface(style_key) if texture_path else None
                    piece.texture_surface_original = surface
                    piece.texture_surface = surface
            else:
                self.block_style_manager.apply_to_piece(
                    piece,
                    base_color,
                )
        else:
            piece.color = base_color
            piece.texture_path = None
            piece.texture_surface = None

    def _make_texture_slice(self, piece: Piece | None, rel_x: int, rel_y: int,
                             piece_width: int | None = None, piece_height: int | None = None) -> TextureSlice | None:
        if not piece or not getattr(piece, 'texture_surface', None):
            return None
        width = piece_width if piece_width is not None else (len(piece.shape[0]) if piece.shape else 1)
        height = piece_height if piece_height is not None else (len(piece.shape) if piece.shape else 1)
        width = width or 1
        height = height or 1
        rotation = getattr(piece, 'rotation_state', 0)
        style_key = getattr(piece, 'style_key', None) or piece.name
        return TextureSlice(style_key, rel_x, rel_y, width, height, rotation)
    
    def spawn_new_piece(self):
        """Yeni parça oluştur - override için"""
        piece = self._choose_piece_from_factories(self._get_base_piece_factories())
        self._apply_block_style(piece)
        return piece

    def _load_workshop_blocks(self) -> Dict[str, List[WorkshopBlockDefinition]]:
        if not self.settings_manager:
            return {}
        try:
            definitions = load_workshop_blocks(self.settings_manager)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"⚠️ Atölye blokları yüklenemedi: {exc}")
            return {}
        mapping: Dict[str, List[WorkshopBlockDefinition]] = {}
        for definition in definitions:
            for mode in definition.modes:
                mapping.setdefault(mode, []).append(definition)
        return mapping

    def _get_base_piece_factories(self) -> List:
        return [self._make_named_piece_factory(name) for name in SHAPE_NAMES]

    def _get_workshop_piece_factories(self) -> List:
        definitions = self.workshop_blocks_by_mode.get(self.game_mode, [])
        factories = []
        for definition in definitions:
            factories.append(lambda d=definition: self._create_workshop_piece(d))
        return factories

    def _ensure_piece_repeat_state(self) -> None:
        if not hasattr(self, '_max_consecutive_same_piece'):
            self._max_consecutive_same_piece = 3
        if not hasattr(self, '_last_piece_identity'):
            self._last_piece_identity = None
        if not hasattr(self, '_last_piece_streak'):
            self._last_piece_streak = 0

    def _piece_identity(self, piece: Piece | None) -> str:
        if not piece:
            return ''
        try:
            if getattr(piece, 'is_workshop_piece', False):
                wid = getattr(piece, 'workshop_block_id', None)
                if wid:
                    return f"workshop:{wid}"
        except Exception:
            pass
        name = getattr(piece, 'name', None)
        if isinstance(name, str) and name:
            return f"name:{name}"
        idx = getattr(piece, 'shape_index', None)
        if idx is not None:
            return f"idx:{idx}"
        return 'unknown'

    def _would_exceed_max_consecutive(self, identity: str) -> bool:
        self._ensure_piece_repeat_state()
        if not identity:
            return False
        last = getattr(self, '_last_piece_identity', None)
        streak = int(getattr(self, '_last_piece_streak', 0) or 0)
        limit = int(getattr(self, '_max_consecutive_same_piece', 3) or 3)
        return bool(last) and identity == last and streak >= limit

    def _note_piece_spawn(self, identity: str) -> None:
        self._ensure_piece_repeat_state()
        if not identity:
            return
        if identity == getattr(self, '_last_piece_identity', None):
            self._last_piece_streak = int(getattr(self, '_last_piece_streak', 0) or 0) + 1
        else:
            self._last_piece_identity = identity
            self._last_piece_streak = 1

    def _refill_piece_bag(self) -> None:
        """Torba (bag) sistemini yeniden doldur.

        Mevcut pool'daki (base + workshop) her parça tipinden ``_bag_copies``
        (varsayılan 3) kadar kopya oluşturulup karıştırılır.  Workshop parçaları
        da otomatik olarak dahil edilir; böylece kullanıcı yeni blok eklediğinde
        bir sonraki torba yenilemesinde bu bloklar da torbaya girer.
        """
        base_factories = self._get_base_piece_factories()
        workshop_factories = self._get_workshop_piece_factories()
        all_factories = base_factories + workshop_factories
        if not all_factories:
            all_factories = [self._make_named_piece_factory('I')]

        copies = int(getattr(self, '_bag_copies', 3) or 3)
        bag: list = []
        for factory in all_factories:
            for _ in range(copies):
                bag.append(factory)

        self._piece_rng.shuffle(bag)
        self._piece_bag = bag

    def _choose_piece_from_factories(self, base_factories: List) -> Piece:
        """Torba (bag) sistemiyle parça seç.

        Her parça tipinden ``_bag_copies`` (3) kadar kopya torbaya atılır ve
        karıştırılır.  Torba bitene kadar sırayla çekilir; biten torba
        otomatik olarak yeniden doldurulur.  Üst üste aynı parça sınırı
        hâlâ geçerlidir (ekstra güvenlik katmanı).
        """
        self._ensure_piece_repeat_state()

        # Torba boşsa yeniden doldur
        if not getattr(self, '_piece_bag', None):
            self._refill_piece_bag()

        bag = self._piece_bag

        # Torbadan üst üste aynı parça kuralını ihlal etmeyecek ilk parçayı bul
        chosen_piece: Piece | None = None
        chosen_index: int = 0
        for i in range(len(bag)):
            factory = bag[i]
            try:
                piece = factory()
            except Exception:
                piece = None
            if piece is None:
                piece = self._create_named_piece('I')

            identity = self._piece_identity(piece)
            if not self._would_exceed_max_consecutive(identity):
                chosen_piece = piece
                chosen_index = i
                break
        else:
            # Torbadaki tüm parçalar kuralı ihlal ediyor (nadir) — ilkini al
            factory = bag[0]
            try:
                chosen_piece = factory()
            except Exception:
                chosen_piece = None
            if chosen_piece is None:
                chosen_piece = self._create_named_piece('I')
            chosen_index = 0

        bag.pop(chosen_index)
        identity = self._piece_identity(chosen_piece)
        self._note_piece_spawn(identity)
        return chosen_piece

    def _make_named_piece_factory(self, piece_name: str):
        return lambda name=piece_name: self._create_named_piece(name)

    def _create_named_piece(self, piece_name: str) -> Piece:
        try:
            piece = create_piece_by_name(piece_name, x=0, y=0)
        except ValueError:
            piece = create_piece_by_index(0, x=0, y=0)
        piece.x = self._compute_spawn_x(piece.get_width())
        piece.y = 0
        # Reset per-piece shape mutation flag
        setattr(piece, '_shape_mutated', False)
        return piece

    def swap_current_piece_shape(self) -> bool:
        """Attempt to mutate the current piece's shape (shape mutation/perk_phase).
        Returns True if the swap succeeded, False otherwise.
        """
        if getattr(self, 'current_piece', None) is None:
            return False
        # Only allow when the perk is active
        if not (getattr(self, 'perk_manager', None) and self.perk_manager.is_active('phase_shift')):
            return False

        # Global usage budget (per run) for phase shift.
        # If the attribute doesn't exist, treat as unlimited (non-mystery modes).
        try:
            remaining = getattr(self, 'phase_shift_uses_remaining', None)
        except Exception:
            remaining = None
        if remaining is not None:
            try:
                if int(remaining) <= 0:
                    return False
            except Exception:
                pass
        # Cooldown and per-piece limit
        if getattr(self, '_shape_mutation_cooldown', 0.0) > 0.0:
            return False
        if getattr(self.current_piece, '_shape_mutated', False):
            return False

        name = getattr(self.current_piece, 'name', None)
        if not name:
            return False

        # Allow mode-specific "smart" mutation.
        new_name = None
        try:
            if hasattr(self, '_get_smart_phase_shift_target_name'):
                new_name = getattr(self, '_get_smart_phase_shift_target_name')(name)
        except Exception:
            new_name = None
        if not new_name:
            mapping = {'L': 'J', 'J': 'L', 'Z': 'S', 'S': 'Z', 'I': 'O', 'O': 'I'}
            new_name = mapping.get(name, None)
        # Eğer dönüşüm yok veya aynı bloğa dönüşüyorsa hak düşürme
        if new_name is None or new_name == name:
            return False

        # Create a candidate piece for the new name at the same position
        try:
            new_piece = self._create_named_piece(new_name)
            # Preserve position
            new_piece.x = self.current_piece.x
            new_piece.y = self.current_piece.y
            # Reset rotation to avoid index mismatch
            new_piece.rotation_state = 0
            # Apply block style (e.g., color)
            try:
                new_piece.color = getattr(self.current_piece, 'color', new_piece.color)
            except Exception:
                pass
            # Ensure new piece fits in the current spot - if not, cancel
            if not self.board.is_valid_position(new_piece):
                return False
            # If valid, replace current piece - preserve bomb attributes if any
            old_is_bomb = getattr(self.current_piece, 'is_bomb', False)
            old_bomb_contact = getattr(self.current_piece, '_bomb_contact', False)
            old_original_color = getattr(self.current_piece, '_original_color', None)
            old_force_color = getattr(self.current_piece, '_force_color', None)
            self.current_piece = new_piece
            # Restore bomb attributes to new piece
            if old_is_bomb:
                setattr(self.current_piece, 'is_bomb', True)
            if old_bomb_contact:
                setattr(self.current_piece, '_bomb_contact', True)
            if old_original_color is not None:
                setattr(self.current_piece, '_original_color', old_original_color)
            if old_force_color is not None:
                setattr(self.current_piece, '_force_color', old_force_color)
            # Mark mutated and set cooldown
            setattr(self.current_piece, '_shape_mutated', True)
            self._shape_mutation_cooldown = 0.5

            # Consume one global phase shift use (MysteryMode)
            try:
                remaining2 = getattr(self, 'phase_shift_uses_remaining', None)
            except Exception:
                remaining2 = None
            if remaining2 is not None:
                try:
                    new_remaining = max(0, int(remaining2) - 1)
                    self.phase_shift_uses_remaining = new_remaining
                    # Deactivate perk when uses exhausted
                    if new_remaining <= 0:
                        try:
                            if getattr(self, 'perk_manager', None):
                                self.perk_manager.deactivate('phase_shift')
                        except Exception:
                            pass
                except Exception:
                    pass
            # Apply theme & update visuals
            try:
                self.apply_theme_to_pieces()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _create_workshop_piece(self, definition: WorkshopBlockDefinition) -> Piece:
        piece = Piece(x=0, y=0, shape_index=0)
        piece.shape = [row[:] for row in definition.shape]
        piece.color = definition.color
        piece.name = definition.name
        piece.is_workshop_piece = True  # type: ignore[attr-defined]
        piece.workshop_block_id = definition.identifier  # type: ignore[attr-defined]
        # Optional per-cell color matrix (Piece Workshop multi-color pieces)
        if getattr(definition, 'cell_colors', None):
            try:
                height = len(piece.shape)
                width = len(piece.shape[0]) if height else 0
                cm = [[None for _ in range(width)] for _ in range(height)]
                for (lx, ly), col in definition.cell_colors.items():
                    if 0 <= ly < height and 0 <= lx < width:
                        cm[ly][lx] = col
                piece.color_matrix = cm  # type: ignore[attr-defined]
            except Exception:
                piece.color_matrix = None  # type: ignore[attr-defined]
        # Apply an existing theme/style texture by mapping workshop pieces to a stable built-in style key.
        try:
            from block_styles import ALL_PIECE_NAMES
            token = (definition.identifier or definition.name or 'workshop').encode('utf-8', errors='ignore')
            digest = hashlib.md5(token).digest()
            idx = int.from_bytes(digest[:2], 'big') % len(ALL_PIECE_NAMES)
            piece.style_key = ALL_PIECE_NAMES[idx]  # type: ignore[attr-defined]
        except Exception:
            pass
        piece.texture_path = None
        piece.texture_surface = None
        piece.texture_surface_original = None
        piece.rotation_state = 0
        width = len(piece.shape[0]) if piece.shape else 1
        piece.x = self._compute_spawn_x(width)
        piece.y = 0
        return piece

    def _compute_spawn_x(self, piece_width: int) -> int:
        piece_width = max(1, piece_width)
        preferred = max(0, (self.board_width // 2) - 2)
        max_x = max(0, self.board_width - piece_width)
        return max(0, min(preferred, max_x))
    
    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice: TextureSlice | None = None):
        """Draw either a textured block or the default shaded block.

        Uses the shared jelly renderer for the classic "jelly" look and keeps
        the original texture-slicing path for texture-backed styles.
        """
        # Güvenlik: color None ise varsayılan gri renk kullan
        if color is None:
            color = (128, 128, 128)
        
        if texture_surface is not None and texture_slice is not None:
            # Keep textured content path but complement with a jelly-style border
            self._draw_texture_cell(x, y, size, color, texture_surface, texture_slice)
            draw_jelly_border(self.screen, x, y, size, color)
            return
        # Non-textured jelly block, draw using shared helper
        draw_jelly_block(self.screen, x, y, size, color)
        return
    
    def _render_texture_slice(self, surface, slice_info: TextureSlice, size: int) -> pygame.Surface | None:
        bounds = {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}
        if self.block_style_manager:
            bounds = self.block_style_manager.get_slice_bounds(slice_info.piece_name)
        return self._texture_render_cache.render_slice(surface, slice_info, size, bounds)

    def _draw_texture_cell(self, x, y, size, color, surface, slice_info: TextureSlice) -> None:
        scaled = self._render_texture_slice(surface, slice_info, size)
        if scaled is None:
            return
        self.screen.blit(scaled, (x, y))
        self._draw_texture_border(x, y, size, color, textured=True)
    def _draw_texture_border(self, x, y, size, color, textured=False) -> None:
        if textured:
            border_color = (255, 255, 255)
            inner = (220, 220, 220)
        else:
            border_color = tuple(min(255, int(c * 1.2)) for c in color[:3])
            inner = tuple(max(0, int(c * 0.5)) for c in color[:3])
        pygame.draw.rect(self.screen, border_color, (x, y, size, size), 2, border_radius=4)
        pygame.draw.rect(self.screen, inner, (x + 2, y + 2, size - 4, size - 4), 1, border_radius=3)

    def _get_rotated_surface(self, surface, rotation):
        return self._texture_render_cache.get_rotated_surface(surface, rotation)
    
    def draw_board_background(self, offset_x, offset_y, board_width, board_height):
        """Board arka planını çiz - override edilebilir"""
        # Tek oyunculu için ayrı arka plan varsa onu kullan
        if self.single_background.is_loaded():
            self.single_background.draw(self.screen, (offset_x, offset_y, board_width, board_height))
        elif self.background_manager.is_loaded():
            # Yoksa ana arka planı kullan (geriye dönük uyumluluk)
            self.background_manager.draw(self.screen, (offset_x, offset_y, board_width, board_height))
    
    def load_background_image(self):
        """Arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_main', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.background_manager.load_image(custom_bg):
                print(f"✨ Özel ana arka plan yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - PyInstaller için resource_path kullan
        # Varsayılan: outer_background (tüm oyun genel arka planı)
        possible_paths = [
            resource_path('backgrounds/outer_background.png'),
            resource_path('backgrounds/outer_background.jpg'),
            resource_path('backgrounds/background.png'),
            resource_path('backgrounds/background.jpg'),
            resource_path('backgrounds/anime_bg.png'),
            resource_path('backgrounds/waifu.png'),
        ]
        # Also look in the assets directory if running from src/ or installed package
        possible_paths.extend([
            resource_path('../assets/backgrounds/outer_background.png'),
            resource_path('../assets/backgrounds/outer_background.jpg'),
            resource_path('../assets/backgrounds/background.png'),
            resource_path('../assets/backgrounds/background.jpg'),
            resource_path('../assets/backgrounds/anime_bg.png'),
            resource_path('../assets/backgrounds/waifu.png'),
        ])
        
        for path in possible_paths:
            if self.background_manager.load_image(path):
                print(f"✨ Arka plan yüklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ Arka plan resmi bulunamadı. backgrounds/ klasörüne resim ekleyin!")
    
    def load_single_background(self):
        """Tek oyunculu oyun alanı için ayrı arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_single', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.single_background.load_image(custom_bg):
                print(f"✨ Özel tek oyuncu arka planı yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - Oyun alanı için ayrı arka plan
        # Varsayılan: game_background (oyun alanı)
        possible_paths = [
            resource_path('backgrounds/game_background.png'),
            resource_path('backgrounds/game_background.jpg'),
            resource_path('backgrounds/single_background.png'),
            resource_path('backgrounds/single_background.jpg'),
            resource_path('backgrounds/single_bg.png'),
            resource_path('backgrounds/game_area_bg.png'),
            resource_path('backgrounds/board_background.png'),  # PvP ile paylaşılan
        ]
        possible_paths.extend([
            resource_path('../assets/backgrounds/game_background.png'),
            resource_path('../assets/backgrounds/game_background.jpg'),
            resource_path('../assets/backgrounds/single_background.png'),
            resource_path('../assets/backgrounds/single_background.jpg'),
            resource_path('../assets/backgrounds/single_bg.png'),
            resource_path('../assets/backgrounds/game_area_bg.png'),
            resource_path('../assets/backgrounds/board_background.png'),
        ])
        
        for path in possible_paths:
            if self.single_background.load_image(path):
                print(f"✨ Tek oyuncu oyun alani icin arka plan yuklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ Tek oyuncu oyun alani icin ayri arka plan bulunamadi (opsiyonel)")
    
    def load_outer_background(self):
        """Oyun alanı dışındaki bölge için arka plan resmini yükle"""
        # 1. Klasik mod için özel arka plan (Kullanıcı İsteği)
        if self.game_mode == 'classic':
            klasik_path = resource_path('assets/klasik.png')
            if os.path.exists(klasik_path):
                if self.outer_background.load_image(klasik_path):
                    print(f"✨ Klasik mod arka planı yüklendi: klasik.png")
                    return

        # 2. Custom background kontrolü
        custom_bg = self.settings_manager.get('bg_outer', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.outer_background.load_image(custom_bg):
                print(f"✨ Özel dış alan arka planı yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - Dış alan için arka plan
        possible_paths = [
            resource_path('backgrounds/outer_background.png'),
            resource_path('backgrounds/outer_background.jpg'),
            resource_path('backgrounds/background.png'),
            resource_path('backgrounds/background.jpg'),
            resource_path('backgrounds/bos.jpg'),
        ]
        possible_paths.extend([
            resource_path('../assets/backgrounds/outer_background.png'),
            resource_path('../assets/backgrounds/outer_background.jpg'),
            resource_path('../assets/backgrounds/background.png'),
            resource_path('../assets/backgrounds/background.jpg'),
            resource_path('../assets/backgrounds/bos.jpg'),
        ])
        
        for path in possible_paths:
            if self.outer_background.load_image(path):
                print(f"✨ Dis alan arka plani yuklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ Dis alan arka plani bulunamadi (opsiyonel)")
    
    def get_initial_speed(self):
        """Sabit başlangıç hızı - Kart modu standardı"""
        return 800
    
    def update_fonts(self):
        """Pencere boyutuna göre fontları güncelle"""
        scale = min(self.window_width / DEFAULT_WINDOW_WIDTH, 
                   self.window_height / DEFAULT_WINDOW_HEIGHT)
        self.font_large = UIFonts.get(int(FONT_SIZE_LARGE * scale))
        self.font_medium = UIFonts.get(int(FONT_SIZE_MEDIUM * scale))
        self.font_small = UIFonts.get(int(FONT_SIZE_SMALL * scale))
    
    def get_cell_size(self):
        """Pencere boyutuna göre hücre boyutunu hesapla - CACHE'LENMİŞ"""
        # Cache kontrolü
        current_size = (self.window_width, self.window_height)
        if not hasattr(self, '_cached_cell_size_key') or self._cached_cell_size_key != current_size:
            # Tahta için kullanılabilir alan
            board_area_width = int(self.window_width) - SIDE_PANEL_WIDTH
            board_area_height = int(self.window_height) - INFO_PANEL_HEIGHT
            
            # Her iki boyuta göre en uygun hücre boyutunu seç
            cell_width = board_area_width // self.board_width  # Dinamik genişlik
            cell_height = board_area_height // self.board_height  # Dinamik yükseklik
            
            self._cached_cell_size = min(cell_width, cell_height, 40)  # Max 40px
            self._cached_cell_size_key = current_size
        
        return self._cached_cell_size
    
    def get_board_offset(self):
        """Tahtanın ekrandaki pozisyonunu hesapla (ortalamak için) - CACHE'LENMİŞ"""
        # Cache kontrolü
        current_size = (self.window_width, self.window_height)
        if not hasattr(self, '_cached_offset_key') or self._cached_offset_key != current_size:
            cell_size = self.get_cell_size()
            board_width = self.board_width * cell_size  # Dinamik genişlik
            board_height = self.board_height * cell_size  # Dinamik yükseklik
            
            offset_x = (int(self.window_width) - SIDE_PANEL_WIDTH - board_width) // 2
            offset_y = (int(self.window_height) - board_height) // 2 - 25  # Biraz yukarı taşı
            
            self._cached_offset = (offset_x, offset_y)
            self._cached_offset_key = current_size
        
        return self._cached_offset
    
    def handle_input(self):
        """
        Kullanıcı girdilerini işle
        
        Returns:
            bool: Oyun devam edecekse True
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if self._is_focus_loss_event(event):
                self._pause_for_focus_loss()
                continue

            # Exit confirmation overlay input (returns to main menu instead of closing the app)
            if self.show_exit_prompt:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        self.show_exit_prompt = False
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                        return 'menu'
                    continue
                # Gamepad: B=kapat, A=onayla (menüye dön)
                if event.type == pygame.JOYBUTTONDOWN:
                    try:
                        gp_cfg = self.settings_manager.get_controls().get('gamepad', {})
                        if event.button == gp_cfg.get('menu_back', 1):
                            self.show_exit_prompt = False
                            continue
                        if event.button == gp_cfg.get('menu_confirm', 0):
                            return 'menu'
                    except Exception:
                        pass
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    if self.exit_yes_rect and self.exit_yes_rect.collidepoint(pos):
                        return 'menu'
                    if self.exit_no_rect and self.exit_no_rect.collidepoint(pos):
                        self.show_exit_prompt = False
                    continue
                # Swallow other events while prompt open
                continue
            
            # Pencere boyutu değiştirildiğinde
            if event.type == pygame.VIDEORESIZE:
                # VIDEORESIZE event.w/h logical (point) boyutu taşır.
                # create_display() logical boyutla çağrılır; surface fiziksel piksel olabilir.
                self.screen = create_display(
                    max(event.w, MIN_WINDOW_WIDTH),
                    max(event.h, MIN_WINDOW_HEIGHT),
                    fullscreen=True,
                    resizable=False,
                    borderless=True,
                )
                # Daima surface'tan gerçek piksel boyutunu al
                self.window_width = self.screen.get_width()
                self.window_height = self.screen.get_height()
                self.update_fonts()
                continue

            # Mouse clicks (game over overlay)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.game_over:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    # Peek butonu kontrolü
                    peek_rect = getattr(self, '_game_over_peek_rect', None)
                    if peek_rect and peek_rect.collidepoint(pos):
                        self._game_over_peek_active = not getattr(self, '_game_over_peek_active', False)
                        continue
                    # Peek modundayken diğer butonlara tıklama yok
                    if getattr(self, '_game_over_peek_active', False):
                        continue
                    targets = getattr(self, '_game_over_click_targets', None)
                    if isinstance(targets, dict) and 'restart' in targets and 'menu' in targets:
                        if targets['restart'].collidepoint(pos):
                            self.restart()
                            continue
                        if targets['menu'].collidepoint(pos):
                            return 'menu'

            # Gamepad buton: game over overlay'de B=menü, Y=restart
            if event.type == pygame.JOYBUTTONDOWN and self.game_over:
                try:
                    gp_cfg = self.settings_manager.get_controls().get('gamepad', {})
                    if event.button == gp_cfg.get('menu_back', 1):
                        return 'menu'
                    if event.button == gp_cfg.get('restart', 3):
                        if self.can_restart():
                            self.restart()
                            continue
                except Exception:
                    pass

            # Duraklatılmışsa mouse kontrollerini işle
            if self.paused and not self.game_over and event.type in (pygame.MOUSEMOTION, pygame.MOUSEWHEEL, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                pause_action = self._handle_pause_menu_input(event)
                if pause_action == 'resume':
                    self.paused = False
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.unduck_music()
                elif pause_action == 'restart':
                    self.paused = False
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.unduck_music()
                    self.restart()
                elif pause_action == 'main_menu':
                    return 'menu'
                continue

            # Gamepad buton: pause menüsünde B=devam et (resume)
            if event.type == pygame.JOYBUTTONDOWN and self.paused and not self.game_over:
                try:
                    gp_cfg = self.settings_manager.get_controls().get('gamepad', {})
                    if event.button == gp_cfg.get('menu_back', 1):
                        self.paused = False
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                        continue
                except Exception:
                    pass
            
            if event.type == pygame.KEYDOWN:
                bindings = self.control_bindings
                alt_keys = getattr(self, 'alt_control_bindings', {})
                # Game-over overlay input: R=restart, ESC=direct main menu (no confirmation)
                if self.game_over:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'
                    if event.key == pygame.K_r and self.can_restart():
                        self.restart()
                        continue
                    continue

                # P - Duraklat
                if event.key == bindings['pause']:
                    self.paused = not self.paused
                    if self.paused:
                        self.pause_menu_selected = 0  # Menüyü sıfırla
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
                    elif pause_action == 'restart':
                        self.paused = False
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                        self.restart()
                    elif pause_action == 'main_menu':
                        return 'menu'
                    continue

                # ESC - oyun içindeyken pause menüsünü aç
                if event.key == pygame.K_ESCAPE:
                    self.paused = True
                    self.pause_menu_selected = 0
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.duck_music()
                    continue
                
                # Sol hareket - DAS sistemi ile
                elif event.key in self._action_keys(bindings, 'move_left'):
                    # İlk hareket (anında)
                    moved = self._try_move_left()
                    if moved:
                        self.sound.play('move')
                    # DAS başlat
                    self.das_direction = -1
                    self.das_timer = 0
                    self.das_repeat_timer = 0
                    self.das_charged = False
                
                # Sağ hareket - DAS sistemi ile
                elif event.key in self._action_keys(bindings, 'move_right'):
                    # İlk hareket (anında)
                    moved = self._try_move_right()
                    if moved:
                        self.sound.play('move')
                    # DAS başlat
                    self.das_direction = 1
                    self.das_timer = 0
                    self.das_repeat_timer = 0
                    self.das_charged = False
                
                elif event.key in self._action_keys(bindings, 'soft_drop'):
                    self.fall_speed = FAST_FALL_SPEED
                    # Soft drop points: 1 point per cell (applied during gravity update if fast falling, doing here for responsiveness is tricky without affecting gravity)
                    # Actually, standard Quadrix only awards points if the piece actually moves down due to soft drop.
                    # Implementing that in `_step` or `update` is better, but simple +1 here is acceptable for visual feedback if debounced.
                    # For now, let's just leave it as speed change. Typically soft drop points are added when 'locked' or per frame moved.
                    # Let's add 1 point per manual soft-drop input to keep it simple and rewarding.
                    # self.board.score += 1
                
                # Döndürme
                # Döndürme
                elif event.key in self._action_keys(bindings, 'rotate'):
                    original_x = self.current_piece.x
                    self.current_piece.rotate()
                    
                    success = True

                    # Döndürme geçerli değilse geri al
                    if not self.board.is_valid_position(self.current_piece):
                        success = False
                        # Wall kick dene (kenara çarpıyorsa içeri kaydır)
                        for dx in [1, -1, 2, -2]:
                            self.current_piece.x = original_x + dx
                            if self.board.is_valid_position(self.current_piece):
                                success = True
                                break
                        else:
                            # Hiçbiri işe yaramadı, geri döndür
                            self.current_piece.x = original_x
                            for _ in range(3):
                                # Rotate 3 times to undo the rotation (equivalent to rotate reverse)
                                self.current_piece.rotate()
                    
                    if success:
                        self.sound.play('rotate')
                elif event.key == bindings['hold2']:
                    # Second pocket (V)
                    # Only operate if the perk is active
                    if getattr(self, 'perk_manager', None) and self.perk_manager.is_active('second_pocket'):
                        if self.can_hold2:
                            if getattr(self, 'second_held_piece', None) is None:
                                self.second_held_piece = self.current_piece
                                self.current_piece = self.next_piece_queue.pop(0)
                                self.next_piece_queue.append(self.spawn_new_piece())
                            else:
                                self.current_piece, self.second_held_piece = self.second_held_piece, self.current_piece
                                self.current_piece.x = 3
                                self.current_piece.y = 0
                            self.can_hold2 = False
                            self.apply_theme_to_pieces()
                            self.sound.play('move')
                
                # Hard drop (anında düşür)
                elif event.key == bindings['hard_drop']:
                    # Hayalet parça aktifse özel davranış: bulunduğu yerde kilitle (komşu blok kontrolü ile)
                    is_tunnel = getattr(self.current_piece, 'tunnel', False)
                    if is_tunnel:
                        # Parçanın etrafında en az 1 komşu blok olmalı (boşlukta kilitlenemez)
                        if self._has_adjacent_block(self.current_piece):
                            before_piece = self.current_piece
                            self.lock_and_new_piece()
                        # Komşu blok yoksa - kilitleme yapma
                        continue
                    # otherwise behave as default hard drop
                    drop_distance = 0
                    start_y = self.current_piece.y
                    
                    while self.board.is_valid_position(self.current_piece, dy=1):
                        self.current_piece.y += 1
                        drop_distance += 1
                    
                    # Hard Drop Bonus: 2 points per cell
                    if drop_distance > 0:
                        self.board.score += drop_distance * 2
                    
                    # Hard drop trail efekti - blok rengiyle uyumlu iz
                    if self.effects_enabled and drop_distance > 0:
                        self._create_drop_trail(
                            self.current_piece, 
                            start_y, 
                            drop_distance, 
                            trail_type='hard'
                        )
                    
                    # Hard drop used to give bonus points; now removed per new scoring rules.
                    self.lock_and_new_piece()
                    # Gamepad titreşimi - hard drop
                    try:
                        get_gamepad_manager().rumble(0.3, 0.6, 120)
                    except Exception:
                        pass
                
                # Hold/Swap parça
                elif event.key == bindings['hold']:
                    if self.can_hold:
                        # Do not allow holding a bomb piece: this prevents accidental explosions
                        if getattr(self.current_piece, 'is_bomb', False):
                            try:
                                self.sound.play('deny')
                            except Exception:
                                pass
                        else:
                            if self.held_piece is None:
                                held_name = getattr(self.current_piece, 'name', None)
                                self.held_piece = self.current_piece
                                # Kuyruktan ilk parçayı al
                                self.current_piece = self.next_piece_queue.pop(0)
                                # Kuyruğa yeni parça ekle
                                self.next_piece_queue.append(self.spawn_new_piece())
                                try:
                                    if self.user_manager and held_name:
                                        self.user_manager.record_hold_piece(held_name)
                                except Exception:
                                    pass
                            else:
                                held_name = getattr(self.current_piece, 'name', None)
                                self.current_piece, self.held_piece = self.held_piece, self.current_piece
                                self.current_piece.x = 3
                                self.current_piece.y = 0
                                try:
                                    if self.user_manager and held_name:
                                        self.user_manager.record_hold_piece(held_name)
                                except Exception:
                                    pass
                            self.can_hold = False
                            self.apply_theme_to_pieces()  # Tema renklerini uygula
                            self.sound.play('move')
                
                # B tuşu - Saklanan parçayı sil (5 hak)
                elif event.key == pygame.K_b:
                    if self.held_piece is not None and self.discard_held_uses > 0:
                        self.held_piece = None
                        self.discard_held_uses -= 1
                        self.can_hold = True  # Tekrar hold kullanabilir
                        self.sound.play('clear')  # Silme sesi
                        print(f"🗑️ Saklanan parça silindi! Kalan hak: {self.discard_held_uses}")
                
                # FPS göster/gizle
                elif event.key == bindings['toggle_fps']:
                    self.show_fps = not self.show_fps

                # Shape Mutation (LSHIFT): only if perk_phase is active
                elif event.key == pygame.K_LSHIFT:
                    try:
                        if getattr(self, 'perk_manager', None) and self.perk_manager.is_active('phase_shift'):
                            # ensure we have a piece
                            if getattr(self, 'current_piece', None) is not None:
                                try:
                                    self.swap_current_piece_shape()
                                except Exception:
                                    pass
                    except Exception:
                        pass
            # Tuş bırakıldığında
            if event.type == pygame.KEYUP:
                alt_keys = getattr(self, 'alt_control_bindings', {})
                def _is_pressed(key: int, pressed) -> bool:
                    try:
                        return key < len(pressed) and bool(pressed[key])
                    except Exception:
                        return False
                # Aşağı tuşu bırakıldığında normal hıza dön
                if event.key in self._action_keys(self.control_bindings, 'soft_drop'):
                    self.fall_speed = self.get_current_speed()
                # Sol/Sağ tuşu bırakıldığında DAS'ı durdur
                elif event.key in self._action_keys(self.control_bindings, 'move_left'):
                    if self.das_direction == -1:
                        pressed = pygame.key.get_pressed()
                        other_key = self.control_bindings['move_right']
                        other_alt = alt_keys.get('move_right')
                        if _is_pressed(other_key, pressed) or (isinstance(other_alt, int) and _is_pressed(other_alt, pressed)):
                            moved = self._try_move_right()
                            if moved:
                                self.sound.play('move')
                            self.das_direction = 1
                            self.das_timer = 0
                            self.das_repeat_timer = 0
                            self.das_charged = False
                        else:
                            self.das_direction = 0
                            self.das_charged = False
                elif event.key in self._action_keys(self.control_bindings, 'move_right'):
                    if self.das_direction == 1:
                        pressed = pygame.key.get_pressed()
                        other_key = self.control_bindings['move_left']
                        other_alt = alt_keys.get('move_left')
                        if _is_pressed(other_key, pressed) or (isinstance(other_alt, int) and _is_pressed(other_alt, pressed)):
                            moved = self._try_move_left()
                            if moved:
                                self.sound.play('move')
                            self.das_direction = -1
                            self.das_timer = 0
                            self.das_repeat_timer = 0
                            self.das_charged = False
                        else:
                            self.das_direction = 0
                            self.das_charged = False
        
        return True
    
    def _try_move_left(self):
        """Sola hareket etmeyi dene, başarılıysa True döndür"""
        if self.current_piece is None:
            return False
        
        self.current_piece.x -= 1
        if not self.board.is_valid_position(self.current_piece):
            self.current_piece.x += 1
            return False
            
        return True
    
    def _try_move_right(self):
        """Sağa hareket etmeyi dene, başarılıysa True döndür"""
        if self.current_piece is None:
            return False
        
        self.current_piece.x += 1
        if not self.board.is_valid_position(self.current_piece):
            self.current_piece.x -= 1
            return False
            
        return True
    
    def _update_das(self, delta_time):
        """DAS (Delayed Auto Shift) sistemini güncelle
        
        Basılı tutulan yön tuşu için otomatik tekrar hareketi sağlar.
        İlk basışta anında hareket eder, sonra DAS_DELAY kadar bekler,
        ardından DAS_REPEAT hızında tekrar eder.
        """
        if self.das_direction == 0 or self.current_piece is None:
            return

        # Oynanış ayarlarından DAS değerlerini oku (ms)
        # Not: Settings ekranında das_delay/das_repeat güncelleniyor; burada constants'a bağlı kalmak
        # ayarların etkisiz kalmasına ve akıcılığın bozulmasına neden olur.
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

        def _move_once(direction: int) -> bool:
            if direction == -1:
                if self._try_move_left():
                    self.sound.play('move')
                    return True
                return False
            if direction == 1:
                if self._try_move_right():
                    self.sound.play('move')
                    return True
                return False
            return False
        
        # Süreyi milisaniye cinsinden artır
        self.das_timer += delta_time

        # İlk gecikme henüz dolmadıysa
        if not self.das_charged:
            if self.das_timer >= delay_ms:
                overshoot = max(0.0, self.das_timer - delay_ms)
                self.das_charged = True
                # Gecikme aşımını repeat timer'a aktar (frame bağımsız akıcılık)
                self.das_repeat_timer = overshoot
                _move_once(self.das_direction)

        # Gecikme doldu, tekrar modunda
        if self.das_charged:
            self.das_repeat_timer += delta_time
            # Frame düşüşlerinde kaçan tekrarları telafi et (catch-up)
            while self.das_repeat_timer >= repeat_ms:
                self.das_repeat_timer -= repeat_ms
                if not _move_once(self.das_direction):
                    # Duvara/engelle takıldıysa daha fazla tekrar harcamaya gerek yok
                    self.das_repeat_timer = 0
                    break
    
    def _handle_pause_menu_input(self, event):
        """Duraklama menüsü girdilerini işle"""
        def apply_option(option: str):
            if option == 'Devam Et':
                return 'resume'
            if option == 'Yeniden Başlat':
                return 'restart'
            if option == 'Müzik':
                self.sound.music_enabled = not self.sound.music_enabled
                if self.settings_manager:
                    self.settings_manager.set('music_enabled', self.sound.music_enabled)
                if self.sound.music_enabled:
                    preference = None
                    if self.settings_manager:
                        preference = self.settings_manager.get_music_preference_for_mode(self.game_mode)
                    track_key = self.current_music_track or self.sound.ensure_track_available(preference or 'klasik_1')
                    self.current_music_track = track_key
                    self.sound.play_music(track_key, loop=True)
                else:
                    self.sound.stop_music()
                return None
            if option == 'Ses Efektleri':
                self.sound.sfx_enabled = not self.sound.sfx_enabled
                if self.settings_manager:
                    self.settings_manager.set('sound_enabled', self.sound.sfx_enabled)
                return None
            if option == 'Ana Menü':
                return 'main_menu'
            return None

        def adjust_volume(option: str, delta: float | None = None, absolute: float | None = None):
            if option == 'Müzik Seviyesi':
                if absolute is None:
                    target = self.sound.music_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_music_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('music_volume', new_vol)
            elif option == 'Efekt Seviyesi':
                if absolute is None:
                    target = self.sound.sfx_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('sfx_volume', new_vol)

        if event.type == pygame.KEYDOWN:
            # Ok tuşlarına ek olarak WASD menü navigasyonu
            up_keys = (pygame.K_UP, pygame.K_w)
            down_keys = (pygame.K_DOWN, pygame.K_s)
            left_keys = (pygame.K_LEFT, pygame.K_a)
            right_keys = (pygame.K_RIGHT, pygame.K_d)

            if event.key in up_keys:
                self.pause_menu_selected = (self.pause_menu_selected - 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key in down_keys:
                self.pause_menu_selected = (self.pause_menu_selected + 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                option = self.pause_menu_options[self.pause_menu_selected]
                return apply_option(option)
            if event.key in left_keys or event.key in right_keys:
                option = self.pause_menu_options[self.pause_menu_selected]
                delta = 0.1 if event.key in right_keys else -0.1
                adjust_volume(option, delta=delta)
                return None
            if event.key == pygame.K_BACKSPACE:
                return 'main_menu'
            if event.key in (pygame.K_ESCAPE, self.control_bindings.get('pause', pygame.K_p)):
                return 'resume'
            return None

        if event.type == pygame.MOUSEWHEEL:
            # Wheel navigates options; if on a volume row, it adjusts volume
            option = self.pause_menu_options[self.pause_menu_selected]
            if option in ('Müzik Seviyesi', 'Efekt Seviyesi'):
                delta = 0.05 if event.y > 0 else -0.05
                adjust_volume(option, delta=delta)
            else:
                step = -1 if event.y > 0 else 1
                self.pause_menu_selected = (self.pause_menu_selected + step) % len(self.pause_menu_options)
                self.sound.play('move')
            return None

        if event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            # Sürükleme aktifse bar'ı güncelle (option rects'e bakmadan)
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
                    if option in ('Müzik Seviyesi', 'Efekt Seviyesi'):
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
        """Duraklama menüsünü ana menü çıkış paneli stilinde çiz."""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale()

        # Dim overlay (exit confirm style)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        
        # Lokalize edilmiş seçenek etiketleri
        option_labels = {
            'Devam Et': t('resume'),
            'Yeniden Başlat': t('campaign_retry'),
            'Müzik': t('music'),
            'Müzik Seviyesi': t('music_volume'),
            'Ses Efektleri': t('sound_effects'),
            'Efekt Seviyesi': t('sfx_volume'),
            'Ana Menü': t('main_menu')
        }
        
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

        # Build option hitboxes for mouse
        self._pause_option_rects = []
        self._pause_volume_rects = {}
        # Her frame gerçek fare pozisyonunu al (hover state mouse motion olmadan da çalışır)
        _pause_mouse_pos = get_mouse_pos()

        start_y = panel_rect.y + top_pad
        for i, option in enumerate(self.pause_menu_options):
            y = start_y + i * (item_h + gap)
            button_rect = pygame.Rect(panel_rect.x + self._sx(22, ui_scale), y, panel_rect.width - self._sx(44, ui_scale), item_h)
            self._pause_option_rects.append(button_rect)

            is_selected = i == self.pause_menu_selected
            label = option_labels.get(option, option)
            sub_text = None
            color_code = retro_style.primary

            if option == 'Devam Et':
                color_code = retro_style.success
                sub_text = 'ESC / P'
            elif option == 'Ana Menü':
                color_code = retro_style.secondary
                sub_text = 'BACKSPACE'
            elif option == 'Müzik':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.music_enabled else t('off')
            elif option == 'Ses Efektleri':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.sfx_enabled else t('off')
            elif option == 'Müzik Seviyesi':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.music_volume * 100)}%  < >"
            elif option == 'Efekt Seviyesi':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.sfx_volume * 100)}%  < >"

            _pm_hover = button_rect.collidepoint(_pause_mouse_pos)
            retro_style.draw_uniform_button(
                self.screen,
                button_rect,
                label,
                sub_text=sub_text,
                color_code=color_code,
                selected=is_selected,
                state='hover' if _pm_hover else 'normal',
            )

            # Volume bars (clickable)
            if option == 'Müzik Seviyesi':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                                      self.sound.music_volume, (0, 210, 255), int(self.sound.music_volume * 100), is_selected, ui_scale)
            elif option == 'Efekt Seviyesi':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                                      self.sound.sfx_volume, (255, 185, 0), int(self.sound.sfx_volume * 100), is_selected, ui_scale)

        # Pause kılavuz metni kaldırıldı
    
    def create_particles(self, count, x=None, y=None, colors=None, speed=5):
        """Partiküller oluştur - animasyon seviyesine göre sayı ayarlanır"""
        if not self._particle_effects_enabled():
            return
        
        # Animasyon çarpanına göre parçacık sayısını ayarla
        mult = getattr(self, 'animation_multiplier', 1.0)
        adjusted_count = max(1, int(count * mult))
        
        # Varsayılan konum
        if x is None:
            x = random.randint(0, self.window_width)
        if y is None:
            y = random.randint(0, self.window_height // 2)
        
        # Varsayılan renkler
        if colors is None:
            colors = [CYAN, YELLOW, MAGENTA, GREEN, RED]
        
        for _ in range(adjusted_count):
            angle = random.uniform(0, 2 * 3.14159)  # Rastgele yön
            velocity = random.uniform(1, speed)
            
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': velocity * random.uniform(-1, 1) * speed,
                'vy': velocity * random.uniform(-1, 1) * speed,
                'life': random.randint(30, 60),
                'max_life': 60,
                'color': random.choice(colors),
                'size': random.randint(2, 5)
            }
            self.particles.append(particle)
    
    def create_lock_explosion(self, x, y, color, cell_size=25):
        """Blok kilitlendiğinde hücreden dairesel patlama efekti oluştur.
        
        Args:
            x: Ekran X koordinatı (hücre merkezi)
            y: Ekran Y koordinatı (hücre merkezi)
            color: Parça rengi
            cell_size: Hücre boyutu (piksel)
        """
        if not self._particle_effects_enabled():
            return
        
        # Her hücreden 6-10 parçacık
        particle_count = random.randint(6, 10)
        
        # Renk varyasyonları oluştur (orijinal renk + parlak/koyu versiyonlar)
        base_color = color
        bright_color = tuple(min(255, int(c * 1.3)) for c in base_color[:3])
        dim_color = tuple(max(0, int(c * 0.7)) for c in base_color[:3])
        white_tint = tuple(min(255, c + 80) for c in base_color[:3])
        
        color_palette = [base_color, bright_color, dim_color, white_tint, (255, 255, 255)]
        
        for i in range(particle_count):
            # Dairesel yayılım için açı hesapla
            angle = (i / particle_count) * 2 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(2, 5)
            
            # Hız vektörleri (dışa doğru yayılım)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 1  # Hafif yukarı doğru
            
            # Başlangıç pozisyonunu hafif rastgele yap
            start_x = x + random.uniform(-3, 3)
            start_y = y + random.uniform(-3, 3)
            
            particle = {
                'x': float(start_x),
                'y': float(start_y),
                'vx': vx,
                'vy': vy,
                'life': random.randint(20, 40),
                'max_life': 40,
                'color': random.choice(color_palette),
                'size': random.randint(2, 4),
                'glow': True
            }
            self.particles.append(particle)
        
        # Merkez parlaması (kısa ömürlü büyük parçacık)
        spark_particle = {
            'x': float(x),
            'y': float(y),
            'vx': 0,
            'vy': -0.5,
            'life': 12,
            'max_life': 12,
            'color': white_tint,
            'size': int(cell_size * 0.4),
            'glow': True
        }
        self.particles.append(spark_particle)
    
    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size):
        """Satır temizlendiğinde SÜPER parçacıklar oluştur - GELİŞTİRİLMİŞ VERSİYON"""
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
            for col in range(self.board_width):  # Dinamik genişlik
                # Hücrenin ekran pozisyonu
                cell_x = board_offset_x + col * cell_size + cell_size // 2
                cell_y = board_offset_y + row * cell_size + cell_size // 2
                
                # Hücre rengi - last_cleared_colors'dan al (satır silinmeden kaydedilmiş)
                try:
                    if hasattr(self.board, 'last_cleared_colors') and row in self.board.last_cleared_colors:
                        row_colors = self.board.last_cleared_colors[row]
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
                    angle = random.uniform(0, 2 * 3.14159)
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
            center_x = board_offset_x + (self.board_width * cell_size) // 2
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

    def _start_block_fall_animation(self, cleared_rows: list):
        """Silinen satırların üstündeki bloklar için düşme animasyonu başlat.
        
        Board zaten güncellendi - satırlar silindi ve üsttekiler kaydı.
        Her blok, sweep o sütuna ulaştığında düşmeye başlayacak.
        """
        if not cleared_rows:
            return
        
        # Temizle - yeni animasyon başlıyor
        self.falling_block_animations = []
        
        # Kaç satır silindi?
        lines_count = len(cleared_rows)
        cell_size = self.get_cell_size()
        board_pixel_width = self.board.width * cell_size
        sweep_width = self._get_line_sweep_length_px(cell_size, lines_count)
        sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
        
        # Board zaten güncellendi, tüm dolu hücrelere düşme animasyonu ver
        # Her blok, sweep o sütuna geldiğinde düşmeye başlayacak
        for y in range(self.board.height):
            for x in range(self.board.width):
                if self.board.occupancy[y][x]:
                    # Bu blok lines_count satır yukarıdan düşüyor
                    offset = -lines_count * cell_size
                    # Sweep trigger: ışık çubuğu bu sütunun merkezine geldiğinde başlat
                    column_center_px = (x + 0.5) * cell_size
                    sweep_trigger = column_center_px / sweep_travel_px
                    sweep_trigger = max(0.0, min(1.0, sweep_trigger))
                    self.falling_block_animations.append({
                        'row': y,
                        'col': x,
                        'current_offset': offset,  # Negatif = yukarıda
                        'target_offset': 0,
                        'sweep_trigger': sweep_trigger,  # Sweep bu değere gelince başla
                        'started': False  # Henüz başlamadı
                    })

    def _get_line_sweep_length_px(self, cell_size: int, cleared_count: int) -> int:
        """Satır temizleme sweep genişliği (piksel)."""
        if cleared_count >= 4:
            blocks = 2
        elif cleared_count >= 3:
            blocks = 3
        elif cleared_count == 2:
            blocks = 2
        else:
            blocks = 1
        return max(1, int(blocks * cell_size))

    def _detect_custom_cat_paw_profile(self, src_surface: pygame.Surface):
        """Custom cat sprite'ta ayak bölgelerini alt koyu piksellerden tahmin et."""
        try:
            width, height = src_surface.get_size()
        except Exception:
            return None

        if width <= 4 or height <= 4:
            return None

        scan_start = max(0, int(height * 0.65))
        min_alpha = 40
        dark_limit = 95

        columns = []

        if _NUMPY_AVAILABLE:
            try:
                rgb_arr = pygame.surfarray.array3d(src_surface)    # (w, h, 3)
                alpha_arr = pygame.surfarray.array_alpha(src_surface)  # (w, h)

                rgb_scan = rgb_arr[:, scan_start:, :]
                alpha_scan = alpha_arr[:, scan_start:]

                visible = alpha_scan >= min_alpha
                dark = _np.all(rgb_scan <= dark_limit, axis=2)
                dark_visible = visible & dark

                dark_counts = dark_visible.sum(axis=1)
                valid_x = _np.where(dark_counts > 0)[0]

                for x in valid_x:
                    col = dark_visible[x]
                    dark_ys = _np.where(col)[0]
                    dark_count = int(dark_counts[x])
                    min_dark_y = int(dark_ys[0]) + scan_start
                    max_dark_y = int(dark_ys[-1]) + scan_start
                    columns.append((int(x), dark_count, min_dark_y, max_dark_y))
            except Exception:
                columns = []

        if not columns:
            for x in range(width):
                dark_count = 0
                min_dark_y = None
                max_dark_y = -1
                for y in range(scan_start, height):
                    r, g, b, a = src_surface.get_at((x, y))
                    if a < min_alpha:
                        continue
                    if r <= dark_limit and g <= dark_limit and b <= dark_limit:
                        dark_count += 1
                        if min_dark_y is None:
                            min_dark_y = y
                        if y > max_dark_y:
                            max_dark_y = y

                if dark_count > 0 and min_dark_y is not None:
                    columns.append((x, dark_count, min_dark_y, max_dark_y))

        if not columns:
            return None

        clusters = []
        current = [columns[0]]
        for item in columns[1:]:
            if item[0] - current[-1][0] <= 1:
                current.append(item)
            else:
                clusters.append(current)
                current = [item]
        if current:
            clusters.append(current)

        cluster_info = []
        for cluster in clusters:
            c_start = cluster[0][0]
            c_end = cluster[-1][0]
            c_width = c_end - c_start + 1
            if c_width > max(3, width // 5):
                continue

            total_dark = sum(v[1] for v in cluster)
            max_dark_y = max(v[3] for v in cluster)
            min_dark_y = min(v[2] for v in cluster)
            weighted_center = int(round(sum(v[0] * v[1] for v in cluster) / float(max(1, total_dark))))

            # Alt kenara yakın, dar kümeleri ayak adayı olarak öne çıkar.
            bottom_bonus = max(0, max_dark_y - scan_start)
            score = (total_dark * 2) + (bottom_bonus * 3) - c_width
            if max_dark_y < height - 3:
                score -= 8

            cluster_info.append({
                'center_x': weighted_center,
                'score': score,
                'min_y': min_dark_y,
                'max_y': max_dark_y,
            })

        if len(cluster_info) < 2:
            return None

        cluster_info.sort(key=lambda c: c['score'], reverse=True)
        selected = cluster_info[:4]
        selected.sort(key=lambda c: c['center_x'])

        leg_top_y = min(c['min_y'] for c in selected)
        baseline_y = max(c['max_y'] for c in selected)
        denom_w = float(max(1, width - 1))
        denom_h = float(max(1, height - 1))
        x_norms = [max(0.0, min(1.0, c['center_x'] / denom_w)) for c in selected]

        return {
            'x_norms': x_norms,
            'leg_top_norm': max(0.0, min(1.0, leg_top_y / denom_h)),
            'baseline_norm': max(0.0, min(1.0, baseline_y / denom_h)),
        }

    def _trim_transparent_surface(self, src_surface: pygame.Surface) -> pygame.Surface:
        """Sprite etrafındaki şeffaf boşlukları kırp."""
        try:
            trim_rect = src_surface.get_bounding_rect(min_alpha=8)
        except Exception:
            return src_surface

        if trim_rect.width <= 0 or trim_rect.height <= 0:
            return src_surface
        if trim_rect.width == src_surface.get_width() and trim_rect.height == src_surface.get_height():
            return src_surface
        return src_surface.subsurface(trim_rect).copy()

    def _sanitize_sprite_alpha(self, src_surface: pygame.Surface, alpha_cutoff: int = 140) -> pygame.Surface:
        """Pixel-art sprite için yarı saydam artefaktları temizle (0/255 alpha)."""
        try:
            surface = src_surface.copy()
            cutoff = max(1, min(254, int(alpha_cutoff)))
            if _NUMPY_AVAILABLE:
                try:
                    alpha_view = pygame.surfarray.pixels_alpha(surface)
                    alpha_view[:] = _np.where(alpha_view < cutoff, 0, 255)
                    del alpha_view
                    return surface
                except Exception:
                    pass
            width, height = surface.get_size()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = surface.get_at((x, y))
                    if a < cutoff:
                        surface.set_at((x, y), (r, g, b, 0))
                    else:
                        surface.set_at((x, y), (r, g, b, 255))
            return surface
        except Exception:
            return src_surface

    def _get_custom_sweep_cat_surface(self, target_w: int, target_h: int, phase: int = 0):
        """Varsa kullanıcı PNG'sini (tek veya frame dizisi) yükle ve animasyonlu döndür."""
        target_w = max(1, int(target_w))
        target_h = max(1, int(target_h))
        phase_index = int(phase) % 8

        if not self._sweep_cat_asset_checked:
            self._sweep_cat_asset_checked = True
            self._sweep_cat_surface_cache = {}
            self._sweep_cat_frame_surface_cache = {}
            self._sweep_cat_frame_base_surfaces = []
            self._sweep_cat_paw_profile = None
            try:
                custom_path = resource_path(os.path.join('assets', 'ui', 'line_sweep_cat.png'))
                if os.path.exists(custom_path):
                    self._sweep_cat_base_surface = pygame.image.load(custom_path).convert_alpha()
                    self._sweep_cat_base_surface = self._trim_transparent_surface(self._sweep_cat_base_surface)
                    self._sweep_cat_base_surface = self._sanitize_sprite_alpha(self._sweep_cat_base_surface)
                    self._sweep_cat_paw_profile = self._detect_custom_cat_paw_profile(self._sweep_cat_base_surface)
            except Exception:
                self._sweep_cat_base_surface = None
                self._sweep_cat_paw_profile = None

            try:
                frame_dir = resource_path(os.path.join('assets', 'ui', 'line_sweep_cat_frames'))
                if os.path.isdir(frame_dir):
                    frame_files = [
                        name
                        for name in sorted(os.listdir(frame_dir))
                        if name.lower().endswith('.png')
                    ]
                    for frame_name in frame_files:
                        frame_path = os.path.join(frame_dir, frame_name)
                        try:
                            frame_surface = pygame.image.load(frame_path).convert_alpha()
                        except Exception:
                            continue
                        if frame_surface.get_width() > 0 and frame_surface.get_height() > 0:
                            frame_surface = self._trim_transparent_surface(frame_surface)
                            frame_surface = self._sanitize_sprite_alpha(frame_surface)
                            self._sweep_cat_frame_base_surfaces.append(frame_surface)
                            if self._sweep_cat_paw_profile is None:
                                self._sweep_cat_paw_profile = self._detect_custom_cat_paw_profile(frame_surface)
            except Exception:
                self._sweep_cat_frame_base_surfaces = []

        frame_bases = self._sweep_cat_frame_base_surfaces
        if frame_bases:
            frame_index = int(phase) % len(frame_bases)
            frame_key = (target_h, frame_index)
            cached_frame = self._sweep_cat_frame_surface_cache.get(frame_key)
            if cached_frame is not None:
                return cached_frame

            frame_base = frame_bases[frame_index]
            bw, bh = frame_base.get_size()
            if bw <= 0 or bh <= 0:
                return None

            scale = target_h / float(bh)
            sw = max(1, int(round(bw * scale)))
            sh = max(1, int(round(target_h)))
            frame_surface = pygame.transform.scale(frame_base, (sw, sh))
            self._sweep_cat_frame_surface_cache[frame_key] = frame_surface
            return frame_surface

        base = self._sweep_cat_base_surface
        if base is None:
            return None

        key = (target_h, phase_index)
        cached = self._sweep_cat_surface_cache.get(key)
        if cached is not None:
            return cached

        bw, bh = base.get_size()
        if bw <= 0 or bh <= 0:
            return None

        scale = target_h / float(bh)
        sw = max(1, int(round(bw * scale)))
        sh = max(1, int(round(target_h)))
        scaled = pygame.transform.scale(base, (sw, sh))

        # Tek PNG için GIF benzeri pseudo-animasyon:
        # Ayak profili varsa sadece ayak kolonlarını oynat, yoksa güvenli fallback kullan.
        surface = scaled.copy()
        paw_profile = self._sweep_cat_paw_profile
        if paw_profile and paw_profile.get('x_norms'):
            leg_top = int(paw_profile.get('leg_top_norm', 0.72) * sh)
            leg_top = max(0, min(sh - 1, leg_top))
            leg_h = max(1, sh - leg_top)
            step_pattern = (0, 1, 2, 1, 0, -1, -2, -1)

            for idx, x_norm in enumerate(paw_profile['x_norms'][:4]):
                center_x = int(max(0.0, min(1.0, x_norm)) * (sw - 1))
                patch_w = max(2, sw // 11)
                patch_x = max(0, min(sw - patch_w, center_x - patch_w // 2))
                src_rect = pygame.Rect(patch_x, leg_top, patch_w, leg_h)
                step = step_pattern[(phase_index + idx) % 8]
                surface.blit(scaled, (patch_x, leg_top + step), src_rect)
        else:
            body_cut = max(1, int(sh * 0.70))
            leg_h = max(1, sh - body_cut)
            left_w = max(1, sw // 2)
            right_w = max(1, sw - left_w)
            step_pattern = (0, 1, 2, 1, 0, -1, -2, -1)
            step = step_pattern[phase_index]
            left_src = pygame.Rect(0, body_cut, left_w, leg_h)
            right_src = pygame.Rect(left_w, body_cut, right_w, leg_h)
            surface.blit(scaled, (0, body_cut + step), left_src)
            surface.blit(scaled, (left_w, body_cut - step), right_src)

        self._sweep_cat_surface_cache[key] = surface
        return surface

    def _draw_rainbow_cat_sweep(self, board_rect, sweep_x: int, sweep_width: int, phase: int):
        sweep_height = max(1, int(board_rect.height))
        sweep_y = board_rect.y

        # Custom sprite'ı satır grubunun yüksekliğine göre ölçekle.
        # Sadece sweep_width'e bağlı kalınca çoklu satır temizlemede küçük kalıyordu.
        custom_target_w = max(sweep_width, int(sweep_height * 1.65))
        custom_cat = self._get_custom_sweep_cat_surface(custom_target_w, sweep_height, phase)
        one_col_w = max(1, int(round(board_rect.width / float(max(1, self.board_width)))))

        if custom_cat is not None:
            cat_w = custom_cat.get_width()
            cat_h = custom_cat.get_height()
            cat_x = sweep_x
            cat_y = sweep_y + max(0, (sweep_height - cat_h) // 2)
            tail_attach_x = cat_x + max(1, int(cat_w * 0.14))
            trail_x = board_rect.x
            trail_right = max(trail_x + one_col_w, tail_attach_x)
            tail_width = max(1, trail_right - trail_x)
        else:
            trail_x = sweep_x
            tail_width = sweep_width

        rainbow = [
            (255, 0, 0),
            (255, 128, 0),
            (255, 230, 0),
            (0, 220, 0),
            (0, 150, 255),
            (130, 80, 255),
        ]

        stripe_h = max(1, sweep_height // 6)
        for i in range(6):
            color = rainbow[(i + phase) % 6]
            stripe_y = sweep_y + i * stripe_h
            if i == 5:
                stripe_h_i = max(1, (sweep_y + sweep_height) - stripe_y)
            else:
                stripe_h_i = stripe_h

            stripe_rect = pygame.Rect(trail_x, stripe_y, tail_width, stripe_h_i)
            clip = stripe_rect.clip(board_rect)
            if clip.width <= 0 or clip.height <= 0:
                continue

            pygame.draw.rect(self.screen, color, clip)
            if (i + phase) % 2 == 0 and clip.width > 4:
                pygame.draw.line(
                    self.screen,
                    (255, 255, 255),
                    (clip.x + 1, clip.y),
                    (clip.x + clip.width - 2, clip.y),
                    1,
                )

        if custom_cat is not None:
            custom_rect = custom_cat.get_rect()
            custom_rect.x = cat_x
            custom_rect.y = cat_y
            clip = custom_rect.clip(board_rect)
            if clip.width > 0 and clip.height > 0:
                src = pygame.Rect(clip.x - custom_rect.x, clip.y - custom_rect.y, clip.width, clip.height)
                self.screen.blit(custom_cat, clip.topleft, src)
        
    def _get_block_fall_offset(self, row: int, col: int) -> float:
        """Belirli bir hücre için düşme animasyonu offset'ini döndür."""
        for anim in self.falling_block_animations:
            if anim['row'] == row and anim['col'] == col:
                # Başlamamış bloklar yukarıda kalmalı, başlamışlar düşüyor
                return anim['current_offset']
        return 0
    
    def _create_drop_trail(self, piece, start_y: int, distance: int, trail_type: str = 'hard'):
        """Blok düşüşü için trail efekti oluştur.
        
        trail_type: 'hard' (parlak, uzun iz) veya 'soft' (hafif, kısa iz)
        """
        if not self.effects_enabled:
            return
        
        cell_size = self.get_cell_size()
        offset_x, offset_y = self.get_board_offset()
        
        # Parçanın her bloğu için trail oluştur
        for row_idx, row in enumerate(piece.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    # Blok pozisyonu
                    block_x = offset_x + (piece.x + col_idx) * cell_size
                    block_y = offset_y + start_y * cell_size + row_idx * cell_size
                    
                    # Trail yüksekliği (düşüş mesafesi kadar)
                    trail_height = distance * cell_size
                    
                    if trail_type == 'hard':
                        # Hard drop: parlak, tam iz
                        alpha = 180
                        trail_width = cell_size - 4
                    else:
                        # Soft drop: hafif, ince iz  
                        alpha = 80
                        trail_width = cell_size // 2
                    
                    # Trail rengi - blok renginin daha parlak versiyonu
                    color = piece.color
                    bright_color = (
                        min(255, color[0] + 50),
                        min(255, color[1] + 50),
                        min(255, color[2] + 50)
                    )

                    w = max(1, int(trail_width))
                    h = max(1, int(trail_height))
                    trail_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                    segments = max(1, h // 4)
                    segment_height = h / segments
                    for i in range(segments):
                        seg_alpha = int(255 * (1 - i / segments))
                        y_pos = int(i * segment_height)
                        seg_h = int(segment_height) + 1
                        trail_surface.fill((*bright_color, seg_alpha), (0, y_pos, w, seg_h))

                    if _NUMPY_AVAILABLE:
                        base_alpha = pygame.surfarray.array_alpha(trail_surface).astype(_np.float32)
                    else:
                        base_alpha = None

                    self.drop_trails.append({
                        'x': block_x + (cell_size - trail_width) // 2,
                        'y': block_y,
                        'alpha': float(alpha),
                        'fade_speed': 15 if trail_type == 'hard' else 20,
                        '_surf': trail_surface,
                        '_base_alpha': base_alpha,
                        '_init_alpha': float(alpha),
                        '_color': bright_color,
                    })
    
    def _update_drop_trails(self, dt_frames: float):
        """Drop trail efektlerini güncelle."""
        for trail in self.drop_trails:
            trail['alpha'] -= trail['fade_speed'] * dt_frames
        # Sönmüş trail'leri kaldır
        self.drop_trails = [t for t in self.drop_trails if t['alpha'] > 0]
    
    def _draw_drop_trails(self):
        """Drop trail efektlerini çiz."""
        for trail in self.drop_trails:
            if trail['alpha'] <= 0:
                continue
            surf = trail['_surf']
            if _NUMPY_AVAILABLE and trail['_base_alpha'] is not None:
                scale = trail['alpha'] / trail['_init_alpha']
                view = pygame.surfarray.pixels_alpha(surf)
                _np.copyto(view, trail['_base_alpha'] * scale, casting='unsafe')
                del view
            else:
                w, h = surf.get_size()
                segments = max(1, h // 4)
                segment_height = h / segments
                surf.fill((0, 0, 0, 0))
                color = trail['_color']
                for i in range(segments):
                    seg_alpha = int(trail['alpha'] * (1 - i / segments))
                    y_pos = int(i * segment_height)
                    seg_h = int(segment_height) + 1
                    surf.fill((*color, seg_alpha), (0, y_pos, w, seg_h))
            self.screen.blit(surf, (int(trail['x']), int(trail['y'])))
    
    def create_firework(self, x, y):
        """Havai fişek efekti oluştur"""
        if not self._particle_effects_enabled():
            return
        
        # Rastgele renkler (parlak renkler)
        colors = [
            (255, 50, 50),    # Kırmızı
            (255, 215, 0),    # Altın
            (0, 255, 255),    # Cyan
            (255, 0, 255),    # Magenta
            (50, 255, 50),    # Yeşil
            (255, 165, 0),    # Turuncu
            (147, 112, 219),  # Mor
            (255, 255, 255),  # Beyaz
        ]
        
        # Ana renk seç
        main_color = random.choice(colors)
        
        # Dairesel patlama - 360 derece
        particle_count = random.randint(40, 60)
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * 3.14159
            speed = random.uniform(3, 8)
            
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1) * abs(3.14159 - angle) / 3.14159 * 2,
                'vy': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1) * abs(3.14159 - angle) / 3.14159 * 2 - 3,
                'life': random.randint(60, 100),
                'max_life': 100,
                'color': main_color if random.random() > 0.3 else random.choice(colors),
                'size': random.randint(4, 8),
                'type': 'firework'
            }
            self.particles.append(particle)
    
    def create_multiple_fireworks(self):
        """Birden fazla havai fişek gösterisi"""
        if not self._particle_effects_enabled():
            return
        
        # Ekranın farklı noktalarında 3-5 havai fişek
        firework_count = random.randint(3, 5)
        for _ in range(firework_count):
            x = random.randint(self.window_width // 4, 3 * self.window_width // 4)
            y = random.randint(self.window_height // 4, 2 * self.window_height // 3)
            self.create_firework(x, y)
    
    def update_particles(self, dt_ms: float | None = None):
        """Partikülleri güncelle (dt tabanlı).

        Not: Mevcut hız/yerçekimi ayarları ~60 FPS'e göre ayarlı. Bu yüzden
        dt'yi "frame" ölçeğine çevirip aynı hissi koruyoruz.
        """
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666

        for particle in self.particles[:]:
            # Homing particles support
            target = particle.get('target')
            if target:
                tx, ty = target
                dx = tx - particle['x']
                dy = ty - particle['y']
                dist = max(1, (dx * dx + dy * dy) ** 0.5)
                # adjust velocity towards target with some smoothing
                speed = particle.get('speed_override', 6)
                particle['vx'] = (dx / dist) * speed
                particle['vy'] = (dy / dist) * speed

            particle['x'] += particle.get('vx', 0) * dt_frames
            particle['y'] += particle.get('vy', 0) * dt_frames
            particle['vy'] += 0.5 * dt_frames  # Yerçekimi
            # Frame tabanlı sürtünmeyi dt'ye uyarlamak için üs kullan
            particle['vx'] *= 0.98 ** dt_frames
            particle['life'] = float(particle.get('life', 0)) - dt_frames
            
            if particle['life'] <= 0:
                self.particles.remove(particle)
    
    def _get_animation_multiplier(self, level: str) -> float:
        """Animasyon seviyesine göre çarpan döndür
        
        Args:
            level: 'low', 'medium', 'medium-high', 'high'
        
        Returns:
            0.5, 0.75, 1.0, veya 1.5 çarpan değeri
        """
        multipliers = {
            'low': 0.5,
            'medium': 0.75,
            'medium-high': 1.0,
            'high': 1.5
        }
        return multipliers.get(level, 1.0)
    
    def create_ambient_particles(self):
        """Arka plan için ambient parçacıklar oluştur (yıldız/kar efekti)"""
        if not self._particle_effects_enabled():
            return
        # Animasyon seviyesine göre parçacık sayısı
        base_count = random.randint(50, 100)
        count = int(base_count * getattr(self, 'animation_multiplier', 1.0))
        
        for _ in range(count):
            particle = {
                'x': random.uniform(0, self.window_width),
                'y': random.uniform(0, self.window_height),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.2, 0.8),  # Yavaşça aşağı düşer
                'size': random.randint(1, 3),
                'alpha': random.randint(50, 150),
                'pulse': random.uniform(0, 6.28),  # Nabız efekti için
                'pulse_speed': random.uniform(0.02, 0.05)
            }
            self.ambient_particles.append(particle)
    
    def trigger_screen_shake(self, intensity=10, duration=15):
        """Ekran titremesi efekti başlat (dt tabanlı; duration ~60 FPS frame sayısı gibi).

        Eski davranış: duration her frame 1 azalırdı. Şimdi dt ile ölçekleniyor.
        """
        if not self._particle_effects_enabled():
            return
        mult = getattr(self, 'animation_multiplier', 1.0)
        self._screen_shake_initial = max(1.0, float(duration) * float(mult))
        self.screen_shake = float(self._screen_shake_initial)
        self.shake_intensity = int(intensity * mult)  # Pixel cinsinden şiddet
    
    def update_screen_shake(self, dt_ms: float | None = None):
        """Ekran titremesini güncelle (dt tabanlı)."""
        if self.screen_shake <= 0:
            return
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666
        self.screen_shake = max(0.0, float(self.screen_shake) - dt_frames)
    
    def get_shake_offset(self):
        """Ekran titremesi için offset hesapla"""
        if self.screen_shake > 0:
            # Rastgele yönde titreme
            shake_x = random.randint(-self.shake_intensity, self.shake_intensity)
            shake_y = random.randint(-self.shake_intensity, self.shake_intensity)
            # Süre azaldıkça şiddet azalsın
            initial = float(getattr(self, '_screen_shake_initial', 15.0))
            decay = max(0.0, min(1.0, float(self.screen_shake) / max(1.0, initial)))
            return (int(shake_x * decay), int(shake_y * decay))
        return (0, 0)
    
    def create_power_particles(self, x, y, color, count=30):
        """Güçlendirilmiş parçacık efekti (combo, cascade için)"""
        if not self.effects_enabled:
            return
        
        for _ in range(count):
            angle = random.uniform(0, 2 * 3.14159)
            speed = random.uniform(5, 12)
            
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 2 - 1),
                'vy': speed * (random.random() * 2 - 1) - 4,
                'life': random.randint(60, 120),
                'max_life': 120,
                'color': color,
                'size': random.randint(5, 10),
                'glow': True,
                'trail': True  # İz bırakma efekti
            }
            self.particles.append(particle)
    
    def update_ambient_particles(self, dt_ms: float | None = None):
        """Ambient parçacıkları güncelle (dt tabanlı)."""
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666

        for particle in self.ambient_particles:
            # Hareket
            particle['x'] += particle['vx'] * dt_frames
            particle['y'] += particle['vy'] * dt_frames
            
            # Nabız efekti
            particle['pulse'] += particle['pulse_speed'] * dt_frames
            
            # Ekran dışına çıktıysa yukarıdan tekrar başlat
            if particle['y'] > self.window_height:
                particle['y'] = -10
                particle['x'] = random.uniform(0, self.window_width)
            
            # Yanlara çıktıysa
            if particle['x'] < -10:
                particle['x'] = self.window_width + 10
            elif particle['x'] > self.window_width + 10:
                particle['x'] = -10
    
    def draw_ambient_particles(self):
        """Ambient parçacıkları çiz"""
        for particle in self.ambient_particles:
            # Nabız efekti ile alpha değişimi
            pulse_alpha = int(particle['alpha'] + math.sin(particle['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            
            # Parçacık rengi (beyaz/hafif mavi)
            color = (200, 200, 255)
            
            # Yarı saydam surface
            pos = (int(particle['x']), int(particle['y']))
            size = particle['size']
            
            # Glow efekti
            if size > 1:
                glow_surface = self._get_ambient_sprite(size, pulse_alpha // 3, glow=True)
                self.screen.blit(glow_surface, (pos[0] - size * 2, pos[1] - size * 2))
            
            # Ana nokta
            particle_surface = self._get_ambient_sprite(size, pulse_alpha, glow=False)
            self.screen.blit(particle_surface, (pos[0] - size, pos[1] - size))
    
    def draw_particles(self):
        """Partikülleri çiz - İYİLEŞTİRİLMİŞ GLOW EFEKTİ"""
        # Esnek sınır kontrolü: Tahta dışındaki parçacıkları çizme
        try:
            board_offset_x, board_offset_y = self.get_board_offset()
            cell_size = self.get_cell_size()
            board_pixel_width = self.board_width * cell_size
            board_pixel_height = self.board_height * cell_size
            board_right = board_offset_x + board_pixel_width
            board_left = board_offset_x
        except Exception:
            board_right = None
            board_left = None
        
        for particle in self.particles:
            # Esnek sınır: Tahta dışındaki parçacıkları çizme
            if board_right is not None and board_left is not None:
                px = particle.get('x', 0)
                if px > board_right or px < board_left:
                    continue  # Tahta dışı - çizme
            
            # Alpha değeri (sönme efekti)
            alpha_ratio = particle['life'] / particle['max_life']
            alpha = int(255 * alpha_ratio)
            
            # Boyut (küçülme efekti)
            size = max(1, int(particle['size'] * alpha_ratio))
            
            color = particle.get('color')
            # Güvenlik: Renk None veya geçersiz format ise varsayılan beyaz yap
            if not color or not isinstance(color, (tuple, list)) or len(color) < 3:
                 color = (255, 255, 255)

            pos = (int(particle['x']), int(particle['y']))
            
            # Glow efekti varsa (satır temizleme parçacıkları)
            if particle.get('glow', False) and size > 2:
                # Dış halo (çok yumuşak)
                halo_size = size + 4
                
                try:
                    halo_color = tuple(min(255, int(c * 0.6)) for c in color[:3])
                except Exception:
                    halo_color = (150, 150, 150)
                    
                halo_surface = self._effect_surface_cache.get_circle_surface(halo_size, (*halo_color, int(alpha * 0.3)))
                self.screen.blit(halo_surface, (pos[0] - halo_size, pos[1] - halo_size))
                
                # Orta halo
                mid_size = size + 2
                try:
                    mid_color = tuple(min(255, int(c * 0.8)) for c in color[:3])
                except Exception:
                    mid_color = (200, 200, 200)

                mid_surface = self._effect_surface_cache.get_circle_surface(mid_size, (*mid_color, int(alpha * 0.5)))
                self.screen.blit(mid_surface, (pos[0] - mid_size, pos[1] - mid_size))
            
            # Ana parçacık
            pygame.draw.circle(self.screen, color, pos, size)
            
            # Parlama efekti (iç kısım) - daha parlak
            if size > 2:
                inner_size = max(1, size - 1)
                try:
                    inner_color = tuple(min(255, c + 80) for c in color[:3])
                except Exception:
                    inner_color = (255, 255, 255)
                pygame.draw.circle(self.screen, inner_color, pos, inner_size)
                
                # Merkez ışık noktası
                if size > 3:
                    core_color = tuple(min(255, c + 120) for c in color[:3])
                    pygame.draw.circle(self.screen, core_color, pos, 1)
    
    def toggle_fullscreen(self):
        """Eski çağrılar için ekranı tam ekran olarak yeniden uygula."""
        try:
            now_ms = pygame.time.get_ticks()
        except Exception:
            now_ms = 0
        last_ms = getattr(self, '_last_fullscreen_toggle_ms', -10_000)
        if now_ms - last_ms < 600:
            return
        self._last_fullscreen_toggle_ms = now_ms

        self.fullscreen = True
        self.screen = create_display(
            self.window_width,
            self.window_height,
            fullscreen=True,
            resizable=False,
            borderless=True,
        )
        self.window_width = self.screen.get_width()
        self.window_height = self.screen.get_height()
        
        if self.settings_manager:
            self.settings_manager.set('fullscreen', True)
            self.settings_manager.save_settings()
        
        self.update_fonts()
    
    def get_ghost_y(self):
        """Ghost piece (gölge) pozisyonunu hesapla"""
        ghost_y = self.current_piece.y
        test_piece = self.current_piece.copy()
        
        while self.board.is_valid_position(test_piece):
            test_piece.y += 1
        
        return test_piece.y - 1
    
    def get_current_speed(self):
        """Seviyeye göre düşüş hızını hesapla - Kart modu standardı"""
        initial = self.get_initial_speed()
        speed = initial - (self.board.level - 1) * SPEED_INCREASE_PER_LEVEL
        # Allow mode-specific score multiplier to reduce the interval (increase speed)
        multiplier = getattr(self, 'score_speed_multiplier', 1.0)
        speed = int(speed * multiplier)
        return max(speed, 200)  # Minimum 200ms
    
    def _has_adjacent_block(self, piece):
        """Parçanın en az bir hücresinin yanında (8 yön) bir blok var mı kontrol et.
        Hayalet parça için: boşlukta kilitlenemez kuralı."""
        try:
            cells = piece.get_cells()
            for cx, cy in cells:
                # 8 yönde komşu kontrol (sol, sağ, üst, alt ve çaprazlar)
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    nx, ny = cx + dx, cy + dy
                    # Zemin de komşu sayılır
                    if ny >= self.board.height:
                        return True
                    # Board sınırları dışındaysa atla
                    if nx < 0 or nx >= self.board.width or ny < 0:
                        continue
                    # Bu konum bir başka hücre değilse (parçanın kendi hücresi değil) ve dolu ise
                    if (nx, ny) not in cells and self.board.occupancy[ny][nx]:
                        return True
            return False
        except Exception:
            return True  # Hata durumunda kilitlemeye izin ver
    
    def lock_and_new_piece(self):
        """Mevcut parçayı kilitle ve yeni parça oluştur"""
        if self.effects_enabled:
            # Parçanın HER HÜCRESİNDEN patlama efekti
            cell_size = self.get_cell_size()
            offset_x, offset_y = self.get_board_offset()
            
            # Parçanın tüm hücrelerini al
            piece_cells = self.current_piece.get_cells()
            cm = getattr(self.current_piece, 'color_matrix', None)
            
            # Her hücreden parçacık patlaması oluştur
            for cell_x, cell_y in piece_cells:
                # Hücrenin ekran pozisyonu
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
                
                # Hücre için parçacık patlaması (dairesel yayılım)
                self.create_lock_explosion(
                    x=screen_x,
                    y=screen_y,
                    color=cell_color,
                    cell_size=cell_size
                )
        
        lines_cleared = self.board.lock_piece(self.current_piece)

        # Satır temizlenmiyorsa blok kilitlenme sesi çal
        if lines_cleared == 0:
            self.sound.play('lock')

        # Satır temizleme efektleri
        if lines_cleared > 0:
            # Temizlenen satırları efekt için kaydet (board.lock_piece içinde zaten set edildi)
            cleared_rows = list(self.board.last_cleared_lines) if self.board.last_cleared_lines else []
            self.line_clear_pending_rows = []
            self.line_clear_pending_colors = {}
            if cleared_rows and self.effects_enabled:
                self.line_clear_pending_rows = list(cleared_rows)
                try:
                    pending_colors = {}
                    if hasattr(self.board, 'last_cleared_colors'):
                        for row in cleared_rows:
                            row_colors = self.board.last_cleared_colors.get(row)
                            if row_colors:
                                pending_colors[row] = list(row_colors)
                    self.line_clear_pending_colors = pending_colors
                except Exception:
                    self.line_clear_pending_colors = {}
            
            # Sweep ve animasyon başlat
            if self.effects_enabled and cleared_rows:
                cell_size = self.get_cell_size()
                offset_x, offset_y = self.get_board_offset()
                
                # Soldan sağa ışık süpürmesi başlat
                self.line_clear_sweep_rows = cleared_rows
                self.line_clear_sweep_progress = 0.0
                self.line_clear_sweep_active = True
                
                # Parçacık efektleri - HER HÜCRE İÇİN
                self.create_line_clear_particles(cleared_rows, offset_x, offset_y, cell_size)
                
                # Dalga efekti - her satır için
                for row in cleared_rows:
                    wave_y = offset_y + row * cell_size + cell_size // 2
                    wave_x = offset_x + (self.board_width * cell_size) // 2
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
                # Silinen satırların üstündeki tüm bloklara düşme efekti ver
                self._start_block_fall_animation(cleared_rows)
                
                # Küçük ekran titremesi (1-3 satır için hafif, 4 satır için güçlü)
                if lines_cleared < 4:
                    self.trigger_screen_shake(intensity=3 + lines_cleared * 2, duration=8)
            
            # Animasyon frame sayacı
            self.line_clear_animation = 30 if self.effects_enabled else 0
            self.line_clear_flash = True
            
            # Satırları temizle (efekt bilgisi alındıktan sonra)
            self.board.last_cleared_lines = []
            if hasattr(self.board, 'last_cleared_colors'):
                self.board.last_cleared_colors = {}
            
            # Mesaj ve ses
            if lines_cleared == 4:
                self.combo_message = "QUADRIX! 4 Satır Yok Edildi!"
                self.sound.play('tetris')
                # Gamepad titreşimi - QUADRIX! (güçlü)
                try:
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                except Exception:
                    pass
                
                # SCREEN SHAKE - QUADRIX!
                self.trigger_screen_shake(intensity=15, duration=20)
                
                # Quadrix için ekstra görkemli parçacıklar
                if self.effects_enabled:
                    # Ekranın ortasından altın renkli patlama
                    center_x = self.window_width // 2
                    center_y = self.window_height // 2
                    self.create_particles(
                        count=150,
                        x=center_x,
                        y=center_y,
                        colors=[YELLOW, ORANGE, (255, 215, 0), CYAN],
                        speed=10
                    )
                # QUADRIX mesajı göster
                self.combo_message_time = 120  # 2 saniye göster
            elif lines_cleared >= 2:
                # Satır sayısına göre isim
                if lines_cleared == 2:
                    clear_name = "DOUBLE!"
                elif lines_cleared == 3:
                    clear_name = "TRIPLE!"
                else:
                    clear_name = f"{lines_cleared}x CLEAR!"
                # Combo zinciri aktifse onu da ekle
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"{clear_name}  x{combo_count} Combo"
                else:
                    self.combo_message = clear_name
                self.sound.play('line')
                # Gamepad titreşimi - çoklu satır (orta)
                try:
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass
                
                # Çoklu satır için renkli parçacıklar
                if self.effects_enabled:
                    center_x = self.window_width // 2
                    center_y = self.window_height // 2
                    self.create_particles(
                        count=50 * lines_cleared,
                        x=center_x,
                        y=center_y,
                        colors=[CYAN, MAGENTA, GREEN],
                        speed=6
                    )
                # Mesaj göster sadece 2+ satır için
                self.combo_message_time = 120  # 2 saniye göster
            else:
                # Tek satır - combo varsa göster, yoksa mesaj yok
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"x{combo_count} Combo!"
                    self.combo_message_time = 90  # 1.5 saniye
                else:
                    self.combo_message = ""
                    self.combo_message_time = 0
                self.sound.play('line')
            
            # Başarı kontrolü (oyun sırasında)
            if self.achievement_manager:
                new_achievements = self.achievement_manager.update_stats(
                    score=self.board.score,
                    lines=self.board.lines_cleared,
                    level=self.board.level,
                    tetrises=self.board.tetrises,
                    combo=self.board.combo,
                    game_mode=self.game_mode,
                )
                # Yeni başarıları bildirim listesine ekle
                print(f"[DEBUG] Yeni başarılar: {new_achievements}")
                for ach_id in new_achievements:
                    achievement = self.achievement_manager.get_achievement(ach_id)
                    print(f"[DEBUG] Başarı bilgisi: {achievement}")
                    if achievement:
                        self.achievement_notifications.append({
                            'achievement': achievement,
                            'time': pygame.time.get_ticks(),
                            'alpha': 255
                        })
                        print(f"[DEBUG] Bildirim eklendi! Toplam: {len(self.achievement_notifications)}")
                        self.sound.play('tetris')  # Başarı sesi (tetris sesi güzel)
                        print(f"Başarı Açıldı: {achievement['name']} - {achievement['description']}")
        
        # Kuyruktan ilk parçayı al ve kuyruğa yeni parça ekle
        self.current_piece = self.next_piece_queue.pop(0)
        self.next_piece_queue.append(self.spawn_new_piece())
        # Yeni aktif parça için lock-delay state'ini temizle
        self.grounded = False
        self.lock_timer = 0
        self.lock_reset_count = 0
        self.can_hold = True  # Yeni parçada tekrar hold kullanılabilir
        self.can_hold2 = True
        self.fall_speed = self.get_current_speed()
        
        # Tema renklerini uygula
        self.apply_theme_to_pieces()
        
        # Yeni parça geçerli pozisyonda değilse oyun biter
        if not self.board.is_valid_position(self.current_piece):
            self.game_over = True
            
            # Gamepad titreşimi - game over (uzun, güçlü)
            try:
                get_gamepad_manager().rumble(1.0, 1.0, 600)
            except Exception:
                pass
            
            # Müzik durdur + Ses çal (özel metod)
            if self.sound:
                self.sound.play_game_over_sequence()
            
            self.finalize_run()
    
    def finalize_run(self, playtime: int | None = None) -> None:
        """Persist score, stats, and achievements once per run."""
        if self._score_recorded:
            return
        self._score_recorded = True
        if playtime is None:
            playtime = self.game_time // 1000
        if self.score_manager:
            self.score_manager.add_score(
                self.board.score,
                self.board.lines_cleared,
                self.board.level,
                self.board.tetrises,
                playtime,
            )
        if self.user_manager:
            self.user_manager.update_user_stats(
                games=1,
                score=self.board.score,
                lines=self.board.lines_cleared,
                tetrises=self.board.tetrises,
                combos=self.board.combo,
                highest_combo=self.board.combo,
                level=self.board.level,
                playtime=playtime,
                mode=self.game_mode,
            )
            print(f"Kullanıcı istatistikleri güncellendi: {self.game_mode.upper()} - {self.board.score} puan")
        # Steam leaderboard'una skor gönder — main thread'i bloklamadan arka planda
        _game_mode = self.game_mode
        _board_score = self.board.score
        def _steam_submit_worker():
            try:
                import steam_integration as _steam_int
                if _board_score > 0:
                    _proxy_written = False
                    # Yol 1: Backend proxy güvenli yazım (LEADERBOARD_BACKEND_URL ayarlıysa)
                    _backend_url = os.environ.get('LEADERBOARD_BACKEND_URL', '').strip()
                    if _backend_url and _steam_int.is_available():
                        try:
                            from steam_leaderboards import SteamLeaderboardService
                            _svc = SteamLeaderboardService(
                                backend_base_url=_backend_url,
                                publisher_key=os.environ.get('STEAM_WEB_API_KEY', ''),
                                app_id=int(os.environ.get('STEAM_APP_ID', '0') or '0'),
                                timeout_seconds=3.0,
                            )
                            _ticket = _steam_int.get_auth_session_ticket()
                            if _ticket and _svc.submit_score(_game_mode, _board_score, ticket=_ticket):
                                _proxy_written = True
                                print(f"[Steam] Proxy skor yazımı OK: {_game_mode} → {_board_score}")
                        except Exception as _pe:
                            print(f"[Steam] Proxy skor yazım hatası: {_pe}")
                    # Yol 2: SDK doğrudan yazım (fallback veya proxy yoksa)
                    if not _proxy_written and _steam_int.is_available():
                        _steam_int.submit_score(_game_mode, _board_score)
            except Exception as _se:
                print(f"[Steam] Skor gönderme hatası: {_se}")
        import threading as _thr
        _thr.Thread(target=_steam_submit_worker, daemon=True).start()
        if self.achievement_manager:
            stats = self.achievement_manager.stats
            stats['total_games'] = stats.get('total_games', 0) + 1
            stats['total_lines'] = stats.get('total_lines', 0) + self.board.lines_cleared
            stats['total_tetrises'] = stats.get('total_tetrises', 0) + self.board.tetrises
            new_achievements = self.achievement_manager.update_stats(
                score=self.board.score,
                lines=self.board.lines_cleared,
                level=self.board.level,
                tetrises=self.board.tetrises,
                combo=self.board.combo,
                game_mode=self.game_mode,
                elapsed_seconds=playtime,
            )
            for ach_id in new_achievements:
                achievement = self.achievement_manager.get_achievement(ach_id)
                if achievement:
                    self.achievement_notifications.append(
                        {'achievement': achievement, 'time': pygame.time.get_ticks(), 'alpha': 255}
                    )
                    print(f"Başarı Açıldı: {achievement['name']} - {achievement['description']}")

    def update(self, delta_time):
        """
        Oyun durumunu güncelle
        
        Args:
            delta_time: Son frameden bu yana geçen süre (ms)
        """
        # Update FPS regardless of pause/game_over so the overlay remains meaningful.
        try:
            dt = float(delta_time or 0)
        except Exception:
            dt = 0.0
        # Keep a stable dt reference for effects that update outside this method too.
        self._last_dt_ms = dt
        dt_clamped = max(0.0, min(100.0, dt))
        dt_frames = dt_clamped / 16.666  # ~60 FPS frame scale
        if dt > 0:
            self._fps_accum_ms += dt
            self._fps_frames += 1
            # Update 2x/sec for stability.
            if self._fps_accum_ms >= 500.0:
                self._fps_value = (self._fps_frames * 1000.0) / self._fps_accum_ms
                self._fps_accum_ms = 0.0
                self._fps_frames = 0

        if self.game_over_warning_timer > 0:
            self.game_over_warning_timer = max(0.0, self.game_over_warning_timer - delta_time / 1000.0)
            if self.game_over_warning_timer == 0:
                self.game_over_warning = ""

        if self.game_over or self.paused or self.show_exit_prompt:
            return

        # Soft drop: bazı sistemlerde KEYDOWN/KEYUP kaçabildiği için basılı tuş
        # durumuna göre de fall_speed'i senkron tut.
        try:
            pressed = pygame.key.get_pressed()

            def _is_pressed(key: int) -> bool:
                try:
                    return key < len(pressed) and bool(pressed[key])
                except Exception:
                    return False

            bindings = getattr(self, 'control_bindings', None) or {}
            bound_soft = int(bindings.get('soft_drop', pygame.K_DOWN))
            # Ok tuşu + WASD desteği: S her zaman soft drop alternatifi.
            soft_now = _is_pressed(bound_soft) or _is_pressed(pygame.K_s)
            # Gamepad D-pad / sol stick aşağı yön kontrolü
            if not soft_now:
                try:
                    from gamepad_manager import get_gamepad_manager
                    gpm = get_gamepad_manager()
                    if gpm.is_direction_held('down'):
                        soft_now = True
                except Exception:
                    pass
            soft_prev = bool(getattr(self, '_soft_drop_held', False))
            if soft_now and not soft_prev:
                self.fall_speed = FAST_FALL_SPEED
            elif (not soft_now) and soft_prev:
                self.fall_speed = self.get_current_speed()
            self._soft_drop_held = soft_now
        except Exception:
            pass
        
        # DAS (Delayed Auto Shift) güncelle - basılı tutarak yatay hareket
        self._update_das(delta_time)
        
        # grounded bilgisini frame'ler arasında koru.
        # Her frame burada sıfırlamak lock delay sayaç sürekliliğini bozar.
        
        self.game_time += delta_time

        # Decrement shape mutation cooldown (seconds)
        if getattr(self, '_shape_mutation_cooldown', 0.0) > 0.0:
            self._shape_mutation_cooldown = max(0.0, self._shape_mutation_cooldown - (delta_time / 1000.0))
        
        # Özel milestone eşikleri kontrolü (havai fişek)
        # Eşikler: 1000, 2000, 4000, 8000, 10000, 15000, 20000, 25000, 30000...
        MILESTONE_THRESHOLDS = [1000, 2000, 4000, 8000, 10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000, 100000]
        
        current_score = self.board.score
        next_milestone = None
        
        # Sıradaki geçilmemiş milestone'u bul
        for threshold in MILESTONE_THRESHOLDS:
            if current_score >= threshold and threshold > self.last_milestone_score:
                next_milestone = threshold
                break
        
        # 100000+ için her 50000'de bir milestone
        if next_milestone is None and current_score >= 100000:
            milestone_after_100k = 100000 + ((current_score - 100000) // 50000) * 50000
            if milestone_after_100k > self.last_milestone_score:
                next_milestone = milestone_after_100k
        
        if next_milestone is not None:
            self.last_milestone_score = next_milestone
            # Havai fişek gösterisi başlat
            self.create_multiple_fireworks()
            self.firework_active = True
            self.firework_time = 120  # 2 saniye göster
            self.sound.play('tetris')  # Kutlama sesi
            print(f"🎆 {next_milestone} PUAN MILESTONE! Havai fişek gösterisi!")
        
        # Havai fişek süresini güncelle
        if self.firework_active:
            self.firework_time = float(self.firework_time) - dt_frames
            if self.firework_time <= 0:
                self.firework_active = False
        
        # NOT: Önceden seviyeye göre otomatik (tetris/speedup) müzik geçişi vardı.
        # Yerleşik (sentez) müzikler kaldırıldığı için bu davranış kapalı.
        
        # Animasyonlar
        if self.line_clear_animation > 0:
            self.line_clear_animation = float(self.line_clear_animation) - dt_frames
            frames_left = int(self.line_clear_animation)
            self.line_clear_flash = (frames_left % 10) < 5
            # Animasyon bittiğinde last_cleared_lines'ı temizle
            if self.line_clear_animation <= 0:
                self.line_clear_flash = False
                self.board.last_cleared_lines = []
        
        # Sweep efekti güncelle (soldan sağa ışık süpürmesi)
        if self.line_clear_sweep_active:
            # Sweep hızı, blok düşüşü ile aynı piksel/frame hızında ilerler
            cell_size = self.get_cell_size()
            board_pixel_width = self.board_width * cell_size
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            block_px_per_frame = self.block_fall_speed * 60.0
            sweep_speed = block_px_per_frame / sweep_travel_px
            self.line_clear_sweep_progress += dt_frames * sweep_speed
            if self.line_clear_sweep_progress >= 1.0:
                self.line_clear_sweep_progress = 1.0
                self.line_clear_sweep_active = False
                self.line_clear_sweep_rows = []
                self.line_clear_pending_rows = []
                self.line_clear_pending_colors = {}
        
        # Dalga efektlerini güncelle
        for wave in self.line_clear_wave_effects[:]:
            wave['radius'] += wave['speed'] * dt_frames
            wave['alpha'] = int(200 * (1 - wave['radius'] / wave['max_radius']))
            if wave['radius'] >= wave['max_radius'] or wave['alpha'] <= 0:
                self.line_clear_wave_effects.remove(wave)
        
        # Blok düşme animasyonlarını güncelle
        if self.falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60  # 60 FPS bazlı hız
            sweep_progress = self.line_clear_sweep_progress
            
            for anim in self.falling_block_animations:
                # Sweep bu sütuna ulaştı mı?
                if not anim.get('started', False):
                    if sweep_progress >= anim.get('sweep_trigger', 0):
                        anim['started'] = True
                
                # Sadece başlamış animasyonları güncelle
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            
            # Tamamlanan animasyonları kaldır (offset=0 VE started=True olanlar)
            self.falling_block_animations = [
                a for a in self.falling_block_animations 
                if not (a['current_offset'] >= 0 and a.get('started', False))
            ]
        
        if self.combo_message_time > 0:
            self.combo_message_time = float(self.combo_message_time) - dt_frames
            if self.combo_message_time <= 0:
                self.combo_message_time = 0
        
        # Drop trail efektlerini güncelle
        if self.drop_trails:
            self._update_drop_trails(dt_frames)
        
        # Partiküller
        self.update_particles(dt_ms=dt) 
        self.update_ambient_particles(dt_ms=dt)  # Arka plan parçacıkları
        self.update_screen_shake(dt_ms=dt)  # Ekran titremesi
        
        # --- LOCK DELAY (Yere Değince Bekleme) ---
        # Oyun bitmediyse ve parça varsa
        if not self.game_over and not self.paused and self.current_piece:
            # Altı dolu mu? (Yerde mi?)
            try:
                if not self.board.is_valid_position(self.current_piece, dy=1):
                    if not self.grounded:
                        self.grounded = True
                        self.lock_timer = 0 # Timer başlat
                        self.lock_reset_count = 0
                    
                    # Lock Delay aktifse timer işlet
                    if getattr(self, 'enable_lock_delay', True):
                        self.lock_timer += dt
                        if self.lock_timer >= getattr(self, 'lock_delay', 500):
                            # Süre doldu, kilitle!
                            if getattr(self, 'allow_auto_lock', True):
                                self.lock_and_new_piece()
                                return
                else:
                    # Havada
                    self.grounded = False
                    self.lock_timer = 0
            except Exception:
                pass
        
        # Otomatik düşüş
        self.fall_time += delta_time
        if self.fall_time >= self.fall_speed:
            self.fall_time = 0
            
            self.current_piece.y += 1
            
            # Parça alta çarptı mı?
            if not self.board.is_valid_position(self.current_piece):
                self.current_piece.y -= 1
                # Hayalet parça serbest düşüşte: komşu blok varsa kilitle
                if getattr(self.current_piece, 'tunnel', False):
                    if self._has_adjacent_block(self.current_piece):
                        if getattr(self, 'allow_auto_lock', True):
                            self.lock_and_new_piece()
                        else:
                            self.grounded = True
                    # Komşu blok yoksa kilitleme - parça beklesin
                # Komşu blok yoksa kilitleme - parça beklesin
                elif getattr(self, 'allow_auto_lock', True):
                    # Lock Delay AÇIKSA burada anında kilitleme! Timer dolunca kilitlenecek.
                    # Eğer lock delay kapalıysa hemen kilitle (klasik davranış).
                    if not getattr(self, 'enable_lock_delay', False):
                        self.lock_and_new_piece()
                    else:
                        # Lock delay açıkken grounded olduğunu işaretle
                        self.grounded = True
                else:
                    self.grounded = True
    
    def _draw_base_scene(self):
        """Temel oyun sahnesini flip çağrısı olmadan çiz."""
        # Tema renklerini al (mode skin öncelikli)
        skin = self.mode_skin or get_mode_skin(self.game_mode)

        # Ekstra modlarda oyun alanını tek formata çek: Classic tahta görünümü
        # (desen/overlay yok, classic grid/border/tint). PvP kendi stilini korur.
        _classic_board_mode_keys = {
            "sprint",
            "ultra",
            "zen",
            "tetris2",
            "mystery",
            "wide",
            "survival",
            "cascade",
            "daily",
            "hardcore",
        }
        if skin.key in _classic_board_mode_keys:
            classic = get_mode_skin("classic")
            # Classic board görünümü + modun ana rengi (kart rengi ile eş)
            board_skin = replace(
                classic,
                accent=skin.accent,
                panel_border=skin.accent,
                board_border=skin.accent,
                board_tint=skin.board_tint,
                grid_color=skin.grid_color,
                overlay="none",
                overlay_alpha=0,
            )
        else:
            board_skin = skin

        # Dış UI (arka plan + panel metinleri) için classic görünüm kalsın.
        # Mod rengi sadece oyun alanında (board tint/border/grid) görünsün.
        ui_skin = get_mode_skin("classic") if skin.key in _classic_board_mode_keys else skin

        def _dim(color, amount=60):
            return tuple(max(0, min(255, c - amount)) for c in color)

        bg_color = ui_skin.outer_bg
        grid_color = board_skin.grid_color
        text_color = ui_skin.text_color
        accent_color = ui_skin.accent
        label_color = _dim(text_color, 70)
        
        # Önce tüm ekranı dış alan arka planı ile doldur
        if self.outer_background.is_loaded():
            # Arka planı tüm ekrana çiz
            self.outer_background.draw_full_screen(self.screen)
        else:
            # Arka plan yoksa sadece renk doldur
            self.screen.fill(bg_color)

        apply_outer_tint(self.screen, ui_skin)
        
        # Menüdeki düşen blok animasyonunu paylaş
        if self.effects_enabled and self.falling_blocks:
            self.falling_blocks.update(self.screen)
            self.falling_blocks.draw(self.screen)

        # Ambient parçacıkları arka planda çiz (arka plan üstünde, oyun alanı altında)
        if self.effects_enabled:
            self.draw_ambient_particles()
        
        # Screen shake offset al
        shake_x, shake_y = self.get_shake_offset()
        
        cell_size = self.get_cell_size()
        base_offset_x, base_offset_y = self.get_board_offset()
        
        # Shake offset uygula
        offset_x = base_offset_x + shake_x
        offset_y = base_offset_y + shake_y
        
        # Esnek sınır perk kontrolü (sadece hareket için, görsel değişiklik yok)
        flexible_border_active = False
        try:
            # Board'daki flag'i kontrol et (kalıcı perk)
            if hasattr(self, 'board') and getattr(self.board, 'flexible_border_active', False):
                flexible_border_active = True
            # Perk manager'dan da kontrol et (yedek)
            elif hasattr(self, 'perk_manager') and self.perk_manager.is_active('perk_flexible_border'):
                flexible_border_active = True
        except Exception:
            pass
        
        board_width = self.board_width * cell_size  # Dinamik genişlik
        board_height = self.board_height * cell_size  # Dinamik yükseklik
        
        # Oyun tahtası arka planı (siyah) - esnek sınır GÖRSEL DEĞİŞİKLİK YAPMAZ
        board_rect = pygame.Rect(offset_x, offset_y, board_width, board_height)
        pygame.draw.rect(self.screen, (4, 4, 12), board_rect)
        
        # Arka plan resmini çiz - override edilebilir
        self.draw_board_background(offset_x, offset_y, board_width, board_height)
        apply_board_tint(self.screen, board_rect, board_skin)
        draw_board_overlay(self.screen, board_rect, board_skin)
        
        # Grid çizgileri - esnek sınır GÖRSEL DEĞİŞİKLİK YAPMAZ
        for x in range(self.board_width + 1):  # Dinamik genişlik
            pygame.draw.line(self.screen, grid_color, 
                           (offset_x + x * cell_size, offset_y), 
                           (offset_x + x * cell_size, offset_y + board_height))
        for y in range(self.board_height + 1):  # Dinamik yükseklik
            pygame.draw.line(self.screen, grid_color, 
                           (offset_x, offset_y + y * cell_size), 
                           (offset_x + board_width, offset_y + y * cell_size))

        # Board içeriği kare (grid + bloklar + background) çiziliyor; burada köşe
        # yuvarlatma kullanmak kare dolgu ile birleşince “iki çerçeve” hissi yaratıyordu.
        # Tek bir, tutarlı çerçeve için board border'ı kare çiz.
        # Board içeriği kare (grid + bloklar + background) çiziliyor; burada köşe
        # yuvarlatma kullanmak kare dolgu ile birleşince “iki çerçeve” hissi yaratıyordu.
        # Tek bir, tutarlı çerçeve için board border'ı kare çiz.
        
        # (Frame çizimi blokların üzerine taşındı)
        
        # Tahtadaki kilitli parçaları çiz (animasyonlu satır temizleme)
        locked_offset_x = offset_x
        locked_offset_y = offset_y
        
        for y in range(self.board_height):  # Dinamik yükseklik
            flash = (y in self.board.last_cleared_lines) and self.line_clear_flash
            for x in range(self.board_width):  # Dinamik genişlik
                cell_color = self.board.grid[y][x]
                locked_slice = self.board.texture_grid[y][x]
                if not self.board.occupancy[y][x]:
                    continue
                color = WHITE if flash else cell_color
                texture_surface = None
                texture_slice = None
                if not flash and locked_slice and self.block_style_manager:
                    texture_surface = self.block_style_manager.get_texture_surface(locked_slice.piece_name)
                    texture_slice = locked_slice if texture_surface else None
                block_x = locked_offset_x + x * cell_size + 1
                block_y = locked_offset_y + y * cell_size + 1
                
                # Düşme animasyonu offset'i uygula
                fall_offset = self._get_block_fall_offset(y, x)
                block_y += fall_offset
                
                block_size = cell_size - 2
                self.draw_textured_block(block_x, block_y, block_size, color, texture_surface, texture_slice)

        if (
            self.effects_enabled
            and self.line_clear_sweep_active
            and self.line_clear_pending_rows
            and self.line_clear_pending_colors
        ):
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
            sweep_x = offset_x + int(self.line_clear_sweep_progress * (board_width + sweep_width)) - sweep_width
            sweep_front_x = sweep_x + sweep_width
            block_size = cell_size - 2

            for row in self.line_clear_pending_rows:
                if not (0 <= row < self.board_height):
                    continue
                row_colors = self.line_clear_pending_colors.get(row)
                if not row_colors:
                    continue
                max_cols = min(self.board_width, len(row_colors))
                for x in range(max_cols):
                    color = row_colors[x]
                    if color == BLACK:
                        continue
                    cell_center_x = offset_x + x * cell_size + cell_size // 2
                    # Küp, ışığın ön kenarı hücreye ulaştığında temizlenir.
                    if cell_center_x <= sweep_front_x:
                        continue
                    block_x = offset_x + x * cell_size + 1
                    block_y = offset_y + row * cell_size + 1
                    self.draw_textured_block(block_x, block_y, block_size, color, None, None)
        
        # ===== DROP TRAIL EFEKTLERİ =====
        if self.effects_enabled and self.drop_trails:
            self._draw_drop_trails()
        
        # ===== SATIR TEMİZLEME EFEKTLERİ =====
        # Sweep efekti - soldan sağa ışık süpürmesi (retro arcade tarzı)
        if (
            self.effects_enabled
            and self.line_clear_sweep_rows
            and self.line_clear_sweep_active
        ):
            progress = self.line_clear_sweep_progress
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
            valid_rows = sorted({r for r in self.line_clear_sweep_rows if 0 <= r < self.board_height})
            if valid_rows:
                top_row = valid_rows[0]
                bottom_row = valid_rows[-1]
                group_y = offset_y + top_row * cell_size
                group_h = max(cell_size, (bottom_row - top_row + 1) * cell_size)
                phase = (pygame.time.get_ticks() // 80) % 8

                # Sweep pozisyonu (soldan sağa)
                sweep_x = offset_x + int(progress * (board_width + sweep_width)) - sweep_width
                board_group_rect = pygame.Rect(offset_x, group_y, board_width, group_h)
                draw_rainbow_cat_sweep(self.screen, self._sweep_cat_state, board_group_rect, sweep_x, sweep_width, phase, self.board_width)

                # Hafif beyaz vurgu (temizlenen satırların tamamında)
                glow_alpha = int(70 * (1.0 - progress * 0.4))
                if glow_alpha > 0:
                    glow_w = min(sweep_width, int(board_width))
                    glow_x = max(offset_x, sweep_x)
                    if glow_w > 0:
                        for row in valid_rows:
                            row_y = offset_y + row * cell_size
                            glow_surface = self._effect_surface_cache.get_filled_surface((glow_w, cell_size), (255, 255, 255, glow_alpha))
                            self.screen.blit(glow_surface, (glow_x, row_y))
        
        # Dalga efektleri çiz
        if self.effects_enabled:
            for wave in self.line_clear_wave_effects:
                if wave['alpha'] > 0:
                    # Yatay dalga çizgisi
                    wave_color = (*wave['color'], wave['alpha'])
                    wave_surface = self._effect_surface_cache.get_ellipse_surface((int(wave['radius'] * 2), 6), wave_color)
                    wave_x = wave['x'] - wave['radius']
                    wave_y = wave['y'] - 3
                    self.screen.blit(wave_surface, (int(wave_x), int(wave_y)))
        
        piece_shape = getattr(self.current_piece, 'shape', None)
        piece_width = len(piece_shape[0]) if piece_shape else 1
        piece_height = len(piece_shape) if piece_shape else 1
        current_texture = getattr(self.current_piece, 'texture_surface', None)

        # Ghost piece (gölge) çiz
        if not self.game_over and self.effects_enabled:
            ghost_y = self.get_ghost_y()
            if ghost_y != self.current_piece.y:
                for x, y in self.current_piece.get_cells():
                    # Esnek sınır: dışarıdaki blokları çizme (görünmez alan)
                    if x < 0 or x >= self.board_width:
                        continue
                    ghost_cell_y = y + (ghost_y - self.current_piece.y)
                    if ghost_cell_y >= 0:
                        block_x = offset_x + x * cell_size + 1
                        block_y = offset_y + ghost_cell_y * cell_size + 1
                        block_size = cell_size - 2
                        local_x = x - self.current_piece.x
                        local_y = y - self.current_piece.y
                        ghost_color = self.current_piece.color
                        cm = getattr(self.current_piece, 'color_matrix', None)
                        if cm is not None:
                            try:
                                v = cm[local_y][local_x]
                                if v is not None:
                                    ghost_color = v
                            except Exception:
                                pass
                        ghost_slice = None
                        if current_texture:
                            ghost_slice = self._make_texture_slice(
                                self.current_piece, local_x, local_y, piece_width, piece_height
                            )
                        if current_texture and ghost_slice:
                            ghost_img = self._render_texture_slice(current_texture, ghost_slice, block_size)
                            if ghost_img:
                                ghost_img.set_alpha(80)
                                self.screen.blit(ghost_img, (block_x, block_y))
                                self._draw_texture_border(block_x, block_y, block_size, ghost_color, textured=True)
                                continue
                        # Yarı saydam renkli gölge
                        s = pygame.Surface((block_size, block_size))
                        s.set_alpha(50)
                        s.fill(ghost_color)
                        self.screen.blit(s, (block_x, block_y))
                        pygame.draw.rect(
                            self.screen,
                            ghost_color,
                            (block_x, block_y, block_size, block_size),
                            2,
                        )
        
        # Mevcut parçayı çiz
        if not self.game_over:
            for local_y, row in enumerate(self.current_piece.shape):
                for local_x, cell in enumerate(row):
                    if not cell:
                        continue
                    x = self.current_piece.x + local_x
                    y = self.current_piece.y + local_y
                    # Esnek sınır: dışarıdaki blokları çizme (görünmez alan)
                    if x < 0 or x >= self.board_width:
                        continue
                    if y < 0:
                        continue
                    block_x = offset_x + x * cell_size + 1
                    block_y = offset_y + y * cell_size + 1
                    block_size = cell_size - 2
                    slice_info = self._make_texture_slice(self.current_piece, local_x, local_y, piece_width, piece_height)
                    draw_color = self.current_piece.color
                    cm = getattr(self.current_piece, 'color_matrix', None)
                    if cm is not None:
                        try:
                            v = cm[local_y][local_x]
                            if v is not None:
                                draw_color = v
                        except Exception:
                            pass
                    self.draw_textured_block(block_x, block_y, block_size, draw_color, current_texture, slice_info)
        
        # PNG Çerçeve Kontrolü - Blokların ÜZERİNE çizim (Bezel etkisi)
        # 12px padding ile daha ince ve zarif bir çerçeve
        if not self._draw_custom_frame(board_rect, "board_frame.png", padding=88, hole_punch=True):
            # Fallback: Resim yoksa standart çizgi
            pygame.draw.rect(self.screen, board_skin.board_border, board_rect, 3)

        # Sağ panel - HardcoreMode gibi modlar override edebilir
        self._draw_right_hud_panel(offset_x, offset_y, board_width, board_height, skin, ui_skin, text_color, accent_color, label_color)
        
        # Efektler - partiküller, combo mesajı, milestone, FPS, game over
        self._draw_base_scene_effects(skin)
        
    def _draw_right_hud_panel(self, offset_x, offset_y, board_width, board_height, skin, ui_skin, text_color, accent_color, label_color):
        """Sağ taraftaki HUD panelini çiz - alt sınıflar override edebilir"""
        # Sağ panel - bilgi paneli arka planı
        info_x = offset_x + board_width + 25
        header_y = offset_y + 10
        
        # Panel genişliği ve yüksekliği hesapla
        available_right = int(self.window_width) - (int(offset_x) + int(board_width) + 40)
        panel_width = min(220, max(120, available_right))
        panel_width = max(120, min(panel_width, max(120, int(self.window_width) - 24)))
        info_x = min(info_x, int(self.window_width) - panel_width - 12)
        panel_height = min(board_height, self.window_height - header_y - 40)
        
        panel_rect = pygame.Rect(info_x, header_y, panel_width, panel_height)

        hud_scale = max(0.72, min(1.05, panel_width / 220.0))
        
        # Ana panel arka planı (Glassmorphism)
        self._draw_hud_glass_panel(panel_rect)
        
        # İçerik Y pozisyonu
        curr_y = header_y + max(10, int(20 * hud_scale))
        content_x = info_x + max(8, int(15 * hud_scale))
        content_w = panel_width - (max(8, int(15 * hud_scale)) * 2)
        
        # Başlık
        badge_text = get_localized_skin_title(skin) or t('tetris_label')
        title_center = (info_x + panel_width // 2, curr_y)
        title_font = retro_style.get_font(max(18, int(28 * hud_scale)), bold=True)
        title_surf = title_font.render(badge_text, True, accent_color)
        title_rect = title_surf.get_rect(center=title_center)
        self.screen.blit(title_surf, title_rect)
        
        curr_y += max(20, int(35 * hud_scale))
        subtitle_text = get_localized_skin_subtitle(skin)
        if subtitle_text:
            sub_font = retro_style.get_font(max(12, int(16 * hud_scale)))
            sub_surf = sub_font.render(subtitle_text, True, text_color)
            sub_rect = sub_surf.get_rect(center=(title_center[0], curr_y))
            self.screen.blit(sub_surf, sub_rect)
            curr_y += max(14, int(25 * hud_scale))
            
        curr_y += max(6, int(10 * hud_scale))
        
        # --- NEXT PIECES ---
        next_label = retro_style.get_font(max(12, int(18 * hud_scale))).render(t('next'), True, label_color)
        self.screen.blit(next_label, (content_x, curr_y))
        
        curr_y += max(14, int(25 * hud_scale))
        # 2 Sonraki parça yanyana
        box_size = max(42, min(60, int(60 * hud_scale)))
        gap = max(8, int(15 * hud_scale))
        
        for i in range(2):
            bx = content_x + i * (box_size + gap)
            by = curr_y
            box_rect = pygame.Rect(bx, by, box_size, box_size)
            
            # Kutu arkaplanı
            # Kutu arkaplanı
            if not self._draw_custom_frame(box_rect, "box_frame.png", padding=4):
                pygame.draw.rect(self.screen, (20, 25, 40, 180), box_rect, border_radius=8)
                pygame.draw.rect(self.screen, (60, 70, 100), box_rect, 1, border_radius=8)
            
            if i < len(self.next_piece_queue):
                p = self.next_piece_queue[i]
                p_tex = getattr(p, 'texture_surface', None)
                pw = len(p.shape[0]) if p.shape else 1
                ph = len(p.shape) if p.shape else 1
                pcm = getattr(p, 'color_matrix', None)
                
                # Mini blok çizimi
                mini_cell = max(8, int(12 * hud_scale))
                # Ortalamak için
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
        
        curr_y += box_size + max(10, int(20 * hud_scale))
        
        # --- HOLD PIECE ---
        hold_label = retro_style.get_font(max(12, int(18 * hud_scale))).render(t('hold'), True, label_color)
        self.screen.blit(hold_label, (content_x, curr_y))
        
        # B tuşu hakkı
        discard_uses = getattr(self, 'discard_held_uses', 5)
        d_col = (100, 200, 255) if discard_uses > 0 else (100, 100, 100)
        d_text = t('hud_key_uses', label='B', count=discard_uses)
        d_surf = retro_style.get_font(max(10, int(14 * hud_scale))).render(d_text, True, d_col)
        self.screen.blit(d_surf, (content_x + content_w - d_surf.get_width(), curr_y + 2))
        
        curr_y += max(14, int(25 * hud_scale))
        hold_box_rect = pygame.Rect(content_x, curr_y, box_size + 20, box_size)
        hold_box_rect = pygame.Rect(content_x, curr_y, box_size + 20, box_size)
        if not self._draw_custom_frame(hold_box_rect, "box_frame.png", padding=4):
            pygame.draw.rect(self.screen, (20, 25, 40, 180), hold_box_rect, border_radius=8)
            pygame.draw.rect(self.screen, (60, 70, 100), hold_box_rect, 1, border_radius=8)

        # Second pocket (V): draw a second hold box when the perk is active.
        show_second_pocket = False
        try:
            show_second_pocket = bool(getattr(self, 'perk_manager', None) and self.perk_manager.is_active('second_pocket'))
        except Exception:
            show_second_pocket = False

        second_box_rect = None
        if show_second_pocket:
            gap2 = max(8, int(15 * hud_scale))
            w2 = hold_box_rect.width
            h2 = hold_box_rect.height
            x2 = hold_box_rect.right + gap2
            y2 = hold_box_rect.y
            if x2 + w2 <= content_x + content_w:
                second_box_rect = pygame.Rect(x2, y2, w2, h2)
            else:
                # Fallback: stack below if panel is too narrow.
                second_box_rect = pygame.Rect(content_x, hold_box_rect.bottom + max(8, int(12 * hud_scale)), w2, h2)
            pygame.draw.rect(self.screen, (20, 25, 40, 180), second_box_rect, border_radius=8)
            pygame.draw.rect(self.screen, (60, 70, 100), second_box_rect, 1, border_radius=8)

            # Label: show which key opens the second pocket (bind-aware).
            try:
                keycode = int(self.control_bindings.get('hold2', pygame.K_v))
                key_name = pygame.key.name(keycode) or 'v'
                key_label = key_name.upper() if len(key_name) <= 2 else key_name
            except Exception:
                key_label = 'V'
            hold2_text = f"{key_label}"

            hold2_label = retro_style.get_font(max(12, int(18 * hud_scale))).render(hold2_text, True, label_color)
            label_y = curr_y - max(14, int(25 * hud_scale))
            if second_box_rect.y > hold_box_rect.y:
                label_y = second_box_rect.y - max(14, int(25 * hud_scale))
            self.screen.blit(hold2_label, (second_box_rect.x, label_y))
        
        if self.held_piece:
            hp = self.held_piece
            hp_tex = getattr(hp, 'texture_surface', None)
            pw = len(hp.shape[0]) if hp.shape else 1
            ph = len(hp.shape) if hp.shape else 1
            mini_cell = max(9, int(14 * hud_scale))
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
                # Kilit ikonu (basit çarpı)
                lx, ly = hold_box_rect.center
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly-10), (lx+10, ly+10), 3)
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly+10), (lx+10, ly-10), 3)

        # Draw second held piece content (and lock overlay) when available.
        if second_box_rect is not None:
            shp = getattr(self, 'second_held_piece', None)
            if shp:
                shp_tex = getattr(shp, 'texture_surface', None)
                spw = len(shp.shape[0]) if shp.shape else 1
                sph = len(shp.shape) if shp.shape else 1
                mini_cell = max(9, int(14 * hud_scale))
                px_w = spw * mini_cell
                px_h = sph * mini_cell
                off_x = second_box_rect.x + (second_box_rect.width - px_w) // 2
                off_y = second_box_rect.y + (second_box_rect.height - px_h) // 2

                d_color = getattr(shp, '_original_color', None) or shp.color
                spcm = getattr(shp, 'color_matrix', None)

                for r_idx, row in enumerate(shp.shape):
                    for c_idx, val in enumerate(row):
                        if not val:
                            continue
                        cx = off_x + c_idx * mini_cell
                        cy = off_y + r_idx * mini_cell
                        s_info = self._make_texture_slice(shp, c_idx, r_idx, spw, sph) if shp_tex else None
                        c = d_color
                        if spcm is not None:
                            try:
                                v = spcm[r_idx][c_idx]
                                if v is not None:
                                    c = v
                            except Exception:
                                pass
                        self.draw_textured_block(cx, cy, mini_cell - 1, c, shp_tex, s_info)

            if not getattr(self, 'can_hold2', True):
                lock_surf = pygame.Surface(second_box_rect.size, pygame.SRCALPHA)
                lock_surf.fill((0, 0, 0, 100))
                self.screen.blit(lock_surf, second_box_rect.topleft)
                lx, ly = second_box_rect.center
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly-10), (lx+10, ly+10), 3)
                pygame.draw.line(self.screen, (200, 50, 50), (lx-10, ly+10), (lx+10, ly-10), 3)

        extra_hold_h = 0
        if second_box_rect is not None and second_box_rect.y > hold_box_rect.y:
            extra_hold_h = (second_box_rect.y - hold_box_rect.y)
        curr_y += box_size + extra_hold_h + max(14, int(30 * hud_scale))
        
        # --- SCORE & STATS ---
        # Modern Card Stilinde Scoreboard
        stats_h = max(150, int(240 * hud_scale))
        stats_h = min(stats_h, max(120, panel_rect.bottom - curr_y - 12))
        stats_rect = pygame.Rect(content_x, curr_y, content_w, stats_h)
        # HUD anchor'larını mod overlay'lerinin kullanabilmesi için sakla
        self._hud_stats_rect = stats_rect
        self._hud_panel_rect = panel_rect
        self._hud_content_x = content_x
        self._hud_content_w = content_w
        
        # Stats background (Daha koyu ve gradient)
        stats_surf = pygame.Surface(stats_rect.size, pygame.SRCALPHA)
        # Dikey gradient
        for i in range(stats_h):
             a = 180 + int(40 * (i / stats_h))
             pygame.draw.line(stats_surf, (20, 24, 35, a), (0, i), (content_w, i))
        self.screen.blit(stats_surf, stats_rect.topleft)
        pygame.draw.rect(self.screen, (50, 60, 80), stats_rect, 1, border_radius=12)
        
        # Stat satırları
        stat_y_cur = curr_y + max(8, int(15 * hud_scale))
        
        def draw_stat_row(label, value, y_pos, color_val=accent_color):
            l_surf = retro_style.get_font(max(11, int(16 * hud_scale))).render(label, True, (160, 170, 190))
            self.screen.blit(l_surf, (content_x + max(8, int(15 * hud_scale)), y_pos))
            
            v_surf = retro_style.get_font(max(15, int(24 * hud_scale)), bold=True).render(str(value), True, color_val)
            v_rect = v_surf.get_rect(topright=(content_x + content_w - max(8, int(15 * hud_scale)), y_pos - max(2, int(4 * hud_scale))))
            self.screen.blit(v_surf, v_rect)
            
            # Alt çizgi
            line_y = y_pos + max(20, int(32 * hud_scale))
            inset = max(6, int(10 * hud_scale))
            pygame.draw.line(self.screen, (255, 255, 255, 30), (content_x + inset, line_y), (content_x + content_w - inset, line_y))
            return max(28, int(45 * hud_scale)) # row height

        score_color_override = getattr(self, '_score_color_override', None)
        stat_y_cur += draw_stat_row(t('score'), f'{self.board.score:,}'.replace(',', '.'), stat_y_cur, score_color_override or accent_color)
        stat_y_cur += draw_stat_row(t('lines'), str(self.board.lines_cleared), stat_y_cur, text_color)
        stat_y_cur += draw_stat_row(t('level'), str(self.board.level), stat_y_cur)
        
        if self.board.combo > 1:
            draw_stat_row(t('combo'), f'x{self.board.combo}', stat_y_cur, (255, 200, 50))
        elif self.board.tetrises > 0:
            draw_stat_row(t('tetris_label'), str(self.board.tetrises), stat_y_cur, (100, 255, 100))
            
        # Mod info
        mode_info_y = stats_rect.bottom + max(8, int(15 * hud_scale))

        # Mod overlay'leri için: skor panelinin altındaki boş alan
        self._hud_mode_info_area = (
            int(content_x),
            int(mode_info_y),
            int(content_w),
            int(max(0, self.window_height - mode_info_y - 8)),
        )
    
    def _draw_base_scene_effects(self, skin):
        """Temel sahne efektlerini çiz - partiküller, combo, milestone, FPS, game over"""
        # Partiküller
        if self.effects_enabled:
            self.draw_particles()
        
        # Combo mesajı
        if self.combo_message_time > 0:
            # Mesaj tipine göre renk ayarla
            msg = self.combo_message
            if 'QUADRIX' in msg:
                msg_color = (255, 215, 0)       # Altın
            elif 'TRIPLE' in msg:
                msg_color = (255, 0, 255)        # Magenta
            elif 'DOUBLE' in msg:
                msg_color = (0, 255, 221)        # Cyan
            elif 'Combo' in msg:
                msg_color = (100, 255, 100)      # Yeşil
            else:
                msg_color = YELLOW
            
            # Fade-out efekti (son 30 frame'de solma)
            alpha = min(255, int(self.combo_message_time * 255 / 30)) if self.combo_message_time < 30 else 255
            
            # Daha büyük font
            combo_font = UIFonts.get(int(self.font_large.get_height() * 1.2), bold=True)
            
            combo_surf = combo_font.render(msg, True, msg_color)
            combo_rect = combo_surf.get_rect(center=(self.window_width // 2, 35))
            
            # Fade-out alpha uygula
            if alpha < 255:
                combo_surf.set_alpha(alpha)
            
            # Gölge (koyu renk)
            shadow = combo_font.render(msg, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(self.window_width // 2 + 3, 38))
            if alpha < 255:
                shadow.set_alpha(alpha)
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(combo_surf, combo_rect)
        
        # Havai fişek milestone mesajı - Modern UI teması (Yukarıda, skor bazlı renkler)
        if self.firework_active and self.firework_time > 0:
            # Animasyon hesaplamaları
            frames_left = int(self.firework_time)
            pulse = abs((frames_left % 20) - 10) / 10.0  # 0-1 arası pulse
            scale_factor = 1.0 + 0.03 * pulse  # Hafif büyüme/küçülme
            
            # Panel boyutları ve konum (YUKARIDA)
            milestone_value = self.last_milestone_score
            milestone_text = f"{milestone_value:,}".replace(',', '.')
            
            # Skor bazlı renk paleti - Yeni eşiklere göre
            MILESTONE_COLORS = {
                1000: ((0, 220, 255), "İlk Adım!"),           # 1000 - Cyan
                2000: ((100, 255, 100), "Devam Et!"),         # 2000 - Yeşil
                4000: ((255, 220, 50), "Harika!"),            # 4000 - Sarı
                8000: ((255, 150, 50), "Müthiş!"),            # 8000 - Turuncu
                10000: ((255, 215, 0), "10K Efsane!"),        # 10000 - Altın
                15000: ((255, 100, 200), "Süpersin!"),        # 15000 - Pembe
                20000: ((200, 100, 255), "İnanılmaz!"),       # 20000 - Mor
                25000: ((100, 200, 255), "Ustasın!"),         # 25000 - Açık Mavi
                30000: ((255, 80, 80), "Ateş!"),              # 30000 - Kırmızı
                40000: ((150, 255, 150), "Canavar!"),         # 40000 - Açık Yeşil
                50000: ((255, 200, 100), "50K Legend!"),      # 50000 - Altın Turuncu
                75000: ((200, 150, 255), "Efsane!"),          # 75000 - Lavanta
                100000: ((255, 255, 100), "100K BOSS!"),      # 100000 - Parlak Sarı
            }
            
            # Milestone değerine göre renk bul
            milestone_color, milestone_msg = ((255, 215, 0), "Muhteşem!")  # Varsayılan
            
            if milestone_value in MILESTONE_COLORS:
                milestone_color, milestone_msg = MILESTONE_COLORS[milestone_value]
            elif milestone_value > 100000:
                # 100K+ için özel
                k_value = milestone_value // 1000
                milestone_color = (255, 215, 0)  # Altın
                milestone_msg = f"{k_value}K - Efsanevi!"
            
            panel_width = 280
            panel_height = 90
            
            # Animasyonlu panel boyutu
            animated_w = int(panel_width * scale_factor)
            animated_h = int(panel_height * scale_factor)
            animated_x = (self.window_width - animated_w) // 2
            animated_y = 50  # YUKARIDA - daha üstte
            
            panel_rect = pygame.Rect(animated_x, animated_y, animated_w, animated_h)
            
            # Dış glow efekti - milestone renginde
            glow_alpha = int(80 + 60 * pulse)
            for offset in range(12, 0, -3):
                glow_rect = panel_rect.inflate(offset * 2, offset * 2)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*milestone_color, int(glow_alpha * (1 - offset/12))), 
                               glow_surf.get_rect(), border_radius=16)
                self.screen.blit(glow_surf, glow_rect.topleft)
            
            # Ana panel - Glassmorphism (milestone rengine tinted)
            panel_surf = pygame.Surface((animated_w, animated_h), pygame.SRCALPHA)
            # Gradient arka plan
            for i in range(animated_h):
                alpha = 210 + int(30 * (i / animated_h))
                r_tint = int(milestone_color[0] * 0.08)
                g_tint = int(milestone_color[1] * 0.08)
                b_tint = int(milestone_color[2] * 0.08)
                pygame.draw.line(panel_surf, (10 + r_tint, 12 + g_tint, 30 + b_tint, alpha), 
                               (0, i), (animated_w, i))
            self.screen.blit(panel_surf, panel_rect.topleft)
            
            # Çerçeve - milestone rengi
            pygame.draw.rect(self.screen, (*milestone_color, 220), panel_rect, 3, border_radius=14)
            
            # Ana skor - Büyük ve parlak
            score_font = retro_style.get_font(42, bold=True)
            color_intensity = int(pulse * 40)
            pulse_color = (
                min(255, milestone_color[0] + color_intensity),
                min(255, milestone_color[1] + color_intensity),
                min(255, milestone_color[2] + color_intensity)
            )
            
            # Gölge
            shadow = score_font.render(milestone_text, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(centerx=panel_rect.centerx + 2, centery=panel_rect.centery - 5)
            shadow.set_alpha(150)
            self.screen.blit(shadow, shadow_rect)
            
            # Ana skor metni
            score_surf = score_font.render(milestone_text, True, pulse_color)
            score_rect = score_surf.get_rect(centerx=panel_rect.centerx, centery=panel_rect.centery - 8)
            self.screen.blit(score_surf, score_rect)
            
            # Alt teşvik mesajı - milestone'a özel
            msg_font = retro_style.get_font(14, bold=True)
            msg_surf = msg_font.render(milestone_msg, True, (220, 230, 250))
            msg_rect = msg_surf.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - 10)
            self.screen.blit(msg_surf, msg_rect)
        
        # FPS göster
        if self.show_fps:
            fps = int(self._fps_value or self.clock.get_fps())
            fps_text = self.font_small.render(f'FPS: {fps}', True, GREEN if fps > 50 else RED)
            self.screen.blit(fps_text, (10, 10))
        
        # Oyun bitti mesajı
        if self.game_over:
            self._draw_game_over_overlay(skin)

    def draw_mode_overlay(self):
        """Modların ek bilgileri için çizim kancası."""
        # Varsayılan olarak ekstra çizim yok
        return

    def draw(self):
        """Ekranı çiz ve mod katmanına yer aç."""
        self._draw_base_scene()

        # Oyun bitti ekranında (game over) mod overlay'lerinin üste binmesini engelle.
        # Game over overlay zaten _draw_base_scene() içinde çiziliyor.
        if not self.game_over:
            self.draw_mode_overlay()

        # Başarım bildirimleri game over'da da görünmeli (özellikle finalize_run sırasında açılanlar).
        self.draw_achievement_notifications()

        # Duraklatma menüsü: mod overlay'lerinden sonra çiz ki her zaman üstte kalsın.
        if self.paused and not self.game_over and not self.show_exit_prompt:
            self._draw_pause_menu()

        if self.show_exit_prompt:
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

        # Hover-aware buton çizimi — ana menü exit confirm ile aynı stil
        mouse_pos = get_mouse_pos()
        for _rect, _label, _sub_label, _btn_color in (
            (yes_rect, t('quit_confirm_yes_label'), 'ENTER', retro_style.success),
            (no_rect, t('quit_confirm_no_label'), 'ESC', retro_style.secondary),
        ):
            _hover = _rect.collidepoint(mouse_pos)
            _draw_rect = _rect.inflate(6, 4) if _hover else _rect

            _btn_bg = pygame.Surface(_draw_rect.size, pygame.SRCALPHA)
            if _hover:
                pygame.draw.rect(_btn_bg, (*_btn_color, 35), _btn_bg.get_rect(), border_radius=12)
                _hl_rect = pygame.Rect(4, 2, _draw_rect.width - 8, 1)
                pygame.draw.rect(_btn_bg, (*_btn_color, 60), _hl_rect)
            else:
                pygame.draw.rect(_btn_bg, (20, 26, 42, 200), _btn_bg.get_rect(), border_radius=12)
            self.screen.blit(_btn_bg, _draw_rect.topleft)

            if _hover:
                _glow_surf = pygame.Surface((_draw_rect.width + 12, _draw_rect.height + 12), pygame.SRCALPHA)
                _glow_r = _glow_surf.get_rect()
                pygame.draw.rect(_glow_surf, (*_btn_color, 25), _glow_r, border_radius=16)
                pygame.draw.rect(_glow_surf, (*_btn_color, 15), _glow_r.inflate(-4, -4), border_radius=14)
                self.screen.blit(_glow_surf, (_draw_rect.x - 6, _draw_rect.y - 6))

            _bw = 3 if _hover else 1
            _ba = 220 if _hover else 100
            pygame.draw.rect(self.screen, (*_btn_color, _ba), _draw_rect, _bw, border_radius=12)

            _txt_color = (255, 255, 255) if _hover else (220, 230, 245)
            _btn_font = retro_style.get_fitting_font(_label, self._sx(20, ui_scale, minimum=14), _draw_rect.width - 40, bold=True)
            _btn_surf = _btn_font.render(_label, True, _txt_color)
            _sub_font = retro_style.get_font(self._sx(13, ui_scale, minimum=10), bold=False)
            _sub_color = (*_btn_color,) if _hover else (140, 155, 180)
            _sub_surf = _sub_font.render(_sub_label, True, _sub_color)
            _gap_t = 3
            _total_h = _btn_surf.get_height() + _gap_t + _sub_surf.get_height()
            _ty = _draw_rect.centery - _total_h // 2
            self.screen.blit(_btn_surf, (_draw_rect.x + 14, _ty))
            self.screen.blit(_sub_surf, (_draw_rect.x + 14, _ty + _btn_surf.get_height() + _gap_t))

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


    def _get_cached_peek_icon(self, icon_size):
        """Peek (göz) ikonunu cache'li olarak yükle ve döndür."""
        cache_key = icon_size
        if getattr(self, '_peek_icon_cache_key', None) == cache_key:
            return self._peek_icon_cache
        try:
            peek_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'kart_secim_sagust.png')
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                peek_icon_path = os.path.join(sys._MEIPASS, 'assets', 'kart_secim_sagust.png')
            peek_icon = load_image(peek_icon_path)
            peek_icon = pygame.transform.smoothscale(peek_icon, (icon_size, icon_size))
            self._peek_icon_cache = peek_icon
            self._peek_icon_cache_key = cache_key
            return peek_icon
        except Exception:
            self._peek_icon_cache = None
            self._peek_icon_cache_key = cache_key
            return None

    def _draw_game_over_overlay(self, skin, *, alt_theme: dict | None = None):
        """Oyun bittiğinde animasyonlu yıldız sistemli modern panel göster."""
        ui_scale = self._ui_scale(min_scale=0.68, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # Alt tema ve state prefix desteği
        _theme = alt_theme or {}
        _sp = (_theme.get('state_prefix', '') or '')
        _skip_stars = bool(_theme.get('skip_stars', False))
        _skip_record = bool(_theme.get('skip_record', False))

        # State attribute name aliases (prefix ile çakışma önlenir)
        _go_active_attr = f'_{_sp}game_over_active'
        _go_start_attr = f'_{_sp}game_over_start_time'
        _go_fade_attr = f'_{_sp}game_over_fade_alpha'
        _final_score_attr = f'_{_sp}final_score'
        _final_lines_attr = f'_{_sp}final_lines'
        _final_level_attr = f'_{_sp}final_level'
        _final_tetrises_attr = f'_{_sp}final_tetrises'
        _final_time_attr = f'_{_sp}final_time'
        _final_max_combo_attr = f'_{_sp}final_max_combo'
        _earned_stars_attr = f'_{_sp}earned_stars'
        _stars_shown_attr = f'_{_sp}stars_shown'
        _star_anim_attr = f'_{_sp}star_animation_timer'
        _disp_score_attr = f'_{_sp}displayed_score'
        _count_speed_attr = f'_{_sp}score_count_speed'
        _is_record_attr = f'_{_sp}is_new_record'
        _confetti_attr = f'_{_sp}confetti_particles'
        _confetti_active_attr = f'_{_sp}confetti_active'
        _last_star_attr = f'_{_sp}last_star_sound'
        _cache_attr = f'_{_sp}go_gradient_cache'
        _cache_key_attr = f'_{_sp}go_gradient_cache_key'

        # Mouse ile tıklanabilir butonlar için hedefleri her frame güncelle
        self._game_over_click_targets = {}
        
        # ============================================
        # PEEK MODU - Oyun alanını görmek için
        # ============================================
        if getattr(self, '_game_over_peek_active', False):
            # Peek modunda sadece sağ alt köşede göz butonu göster
            peek_btn_size = s(48)
            peek_btn_x = self.window_width - peek_btn_size - s(20)
            peek_btn_y = self.window_height - peek_btn_size - s(20)
            self._game_over_peek_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
            
            # Yuvarlak beyaz arka plan
            center = self._game_over_peek_rect.center
            radius = peek_btn_size // 2
            pygame.draw.circle(self.screen, (255, 255, 255), center, radius)
            pygame.draw.circle(self.screen, (100, 200, 255), center, radius, 2)
            
            # Göz ikonu - cache'li yükleme
            peek_icon_surf = self._get_cached_peek_icon(int(peek_btn_size * 0.65))
            if peek_icon_surf:
                icon_rect = peek_icon_surf.get_rect(center=self._game_over_peek_rect.center)
                self.screen.blit(peek_icon_surf, icon_rect)
            else:
                # Fallback: metin göster
                fallback_font = retro_style.get_font(s(20, minimum=12), bold=True)
                eye_surf = fallback_font.render("X", True, (100, 200, 255))
                self.screen.blit(eye_surf, eye_surf.get_rect(center=self._game_over_peek_rect.center))
            return
        
        # ============================================
        # DURUM YÖNETİMİ VE ANİMASYON ZAMANLAYICI
        # ============================================
        current_time = pygame.time.get_ticks()
        
        # İlk kez çağrılıyorsa başlat
        if not getattr(self, _go_active_attr, False):
            setattr(self, _go_active_attr, True)
            setattr(self, _go_start_attr, current_time)

            # Sonuç verilerini dondur (artık değişmeyecek)
            setattr(self, _final_score_attr, self.board.score)
            setattr(self, _final_lines_attr, self.board.lines_cleared)
            setattr(self, _final_level_attr, self.board.level)
            setattr(self, _final_tetrises_attr, getattr(self.board, 'tetrises', 0))
            setattr(self, _final_time_attr, self.game_time // 1000)
            setattr(self, _final_max_combo_attr, getattr(self.board, 'max_combo', 0))

            # Yıldız hesapla
            setattr(self, _earned_stars_attr, self._calculate_stars())
            setattr(self, _stars_shown_attr, 0)
            setattr(self, _star_anim_attr, 0.0)

            # Skor animasyonu
            setattr(self, _disp_score_attr, 0)
            _init_final_score = getattr(self, _final_score_attr, 0)
            duration_ms = 1500  # 1.5 saniyede skor sayılsın
            setattr(self, _count_speed_attr, max(1, _init_final_score / (duration_ms / 1000)))

            # Rekor kontrolü (skip_record ise False)
            _is_rec = False if _skip_record else self._check_new_record()
            setattr(self, _is_record_attr, _is_rec)

            # Fade alpha
            setattr(self, _go_fade_attr, 0)

            # Konfeti (sadece rekor kırıldıysa)
            setattr(self, _confetti_attr, [])
            setattr(self, _confetti_active_attr, _is_rec)
        
        # Geçen süre (ms)
        elapsed_ms = current_time - getattr(self, _go_start_attr, current_time)
        elapsed_sec = elapsed_ms / 1000.0
        
        # ============================================
        # ANİMASYON TIMELINE
        # ============================================
        # 0-0.4s: Fade-in
        # 0.2-1.7s: Skor sayımı
        # 1.5-3.0s: Yıldızlar tek tek açılır (her 0.5s'de bir)
        # 1.5s+: Konfeti (rekor varsa)
        
        # Fade-in animasyonu (0-0.4 saniye)
        fade_duration = 0.4
        if elapsed_sec < fade_duration:
            setattr(self, _go_fade_attr, int(240 * (elapsed_sec / fade_duration)))
        else:
            setattr(self, _go_fade_attr, 240)
        
        # Skor sayım animasyonu (0.2-1.7 saniye)
        score_start = 0.2
        score_duration = 1.5
        if elapsed_sec > score_start:
            score_progress = min(1.0, (elapsed_sec - score_start) / score_duration)
            # Ease-out curve: başta hızlı, sonda yavaş
            eased_progress = 1 - (1 - score_progress) ** 3
            setattr(self, _disp_score_attr, int(getattr(self, _final_score_attr, 0) * eased_progress))
        
        # Yıldız animasyonu ses efekti (her tam yıldızda bir ses)
        star_start = 1.5
        star_reveal_speed = 2.0
        if elapsed_sec > star_start:
            current_shown = min(getattr(self, _earned_stars_attr, 0.0), (elapsed_sec - star_start) * star_reveal_speed)
            prev_shown = getattr(self, _last_star_attr, 0)

            # Yeni tam yıldız açıldıysa ses çal
            if int(current_shown) > int(prev_shown):
                if self.sound_enabled:
                    try:
                        self.sound.play('rotate')
                    except Exception:
                        pass
            setattr(self, _last_star_attr, current_shown)
        
        # Konfeti güncelle
        if getattr(self, _confetti_active_attr, False) and elapsed_sec > 1.5:
            self._update_confetti(current_time)
        
        # ============================================
        # ÇİZİM - FADE OVERLAY (cache'li gradient)
        # ============================================
        _go_cache_key = (self.window_width, self.window_height)
        if getattr(self, _cache_key_attr, None) != _go_cache_key:
            _gradient_tint = _theme.get('gradient_tint', (5, 8, 18))
            _go_surf = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            for y in range(self.window_height):
                _a = int(240 * 0.8 + 40 * (y / self.window_height))
                _a = min(_a, 240)
                pygame.draw.line(_go_surf, (*_gradient_tint, _a), (0, y), (self.window_width, y))
            setattr(self, _cache_attr, _go_surf)
            setattr(self, _cache_key_attr, _go_cache_key)
        _go_cached_surf = getattr(self, _cache_attr, None)
        if _go_cached_surf is not None:
            _go_cached_surf.set_alpha(getattr(self, _go_fade_attr, 0))
            self.screen.blit(_go_cached_surf, (0, 0))
        
        # Konfeti çiz (arka planda)
        self._draw_confetti()

        # Panel boyutları
        panel_width = min(max(s(700), self.window_width - s(560)), self.window_width - s(260))
        panel_width = max(s(620), panel_width)
        panel_height = min(max(s(430), self.window_height - s(240)), self.window_height - s(130))
        panel_height = max(s(360), panel_height)
        panel_rect = pygame.Rect(
            (self.window_width - panel_width) // 2,
            (self.window_height - panel_height) // 2,
            panel_width,
            panel_height,
        )

        # İç yerleşim sabitleri (okunabilirlik + hizalama)
        pad_x = s(34)
        inner_left = panel_rect.x + pad_x
        inner_right = panel_rect.right - pad_x
        inner_w = inner_right - inner_left

        # Panel paleti (alt_theme ile override edilebilir)
        panel_border_color = _theme.get('panel_border_color', (88, 146, 255))
        panel_glow_color   = _theme.get('panel_glow_color',   (72, 118, 236))
        panel_fill_tint    = _theme.get('panel_fill_tint',    (10, 16, 34))
        card_fill_tint     = _theme.get('card_fill_tint',     (14, 22, 44))
        card_border_color  = _theme.get('card_border_color',  (74, 104, 162))
        label_color_soft = (198, 212, 238)
        
        # Panel glow efekti
        glow_rect = panel_rect.inflate(s(24), s(24))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (panel_glow_color[0], panel_glow_color[1], panel_glow_color[2], 34), 
                        glow_surf.get_rect(), border_radius=24)
        self.screen.blit(glow_surf, glow_rect.topleft)
        
        # Glass panel
        if alt_theme:
            # Alt tema varsa panel arka planını özel renkle çiz (tint ile)
            _tint_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            _tint_surf.fill((*panel_fill_tint, 216))
            # Üst kenar cam highlight
            _hl_h = min(panel_rect.height // 3, 40)
            for _yl in range(_hl_h):
                _ha = int(25 * (1 - _yl / _hl_h))
                pygame.draw.line(_tint_surf, (255, 255, 255, _ha), (0, _yl), (panel_rect.width, _yl))
            self.screen.blit(_tint_surf, panel_rect.topleft)
            pygame.draw.rect(self.screen, panel_border_color, panel_rect, 2, border_radius=12)
        else:
            retro_style.draw_glass_panel(self.screen, panel_rect, alpha=216, border_color=panel_border_color)
        
        # Göz butonu - panelin sağ üst köşesinde
        peek_btn_size = s(36)
        peek_btn_x = panel_rect.right - peek_btn_size - s(16)
        peek_btn_y = panel_rect.y + s(16)
        self._game_over_peek_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
        
        # Göz butonu arka planı
        mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
        peek_hovered = mouse_pos is not None and self._game_over_peek_rect.collidepoint(mouse_pos)
        center = self._game_over_peek_rect.center
        radius = peek_btn_size // 2
        pygame.draw.circle(self.screen, (255, 255, 255), center, radius)
        border_color = (116, 190, 255) if peek_hovered else (110, 134, 188)
        pygame.draw.circle(self.screen, border_color, center, radius, 2)
        
        # Göz ikonu - cache'li yükleme
        _peek_icon_size = int(peek_btn_size * 0.65)
        peek_icon_surf = self._get_cached_peek_icon(_peek_icon_size)
        if peek_icon_surf:
            icon_rect = peek_icon_surf.get_rect(center=self._game_over_peek_rect.center)
            self.screen.blit(peek_icon_surf, icon_rect)
        else:
            # Fallback: metin göster
            fallback_font = retro_style.get_font(s(16, minimum=10), bold=True)
            eye_surf = fallback_font.render("O", True, (116, 190, 255) if peek_hovered else (160, 182, 220))
            self.screen.blit(eye_surf, eye_surf.get_rect(center=self._game_over_peek_rect.center))

        # BAŞLIK - Survival zafer, alt_theme override, ya da game_over
        is_survival_victory = getattr(self, 'survival_victory', False)
        _title_text_override = _theme.get('title_text', None)
        if _title_text_override:
            title_text = _title_text_override
            title_color = panel_border_color
        elif is_survival_victory:
            title_text = t('survival_victory_title')
            title_color = (255, 215, 0)  # Altın rengi
        else:
            title_text = t('game_over')
            title_color = panel_border_color
            
        title_font = retro_style.get_font(s(48, minimum=24), bold=True)
        title = title_font.render(title_text, True, title_color)
        title_rect = title.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + s(22))

        # Glow'u tek bir yöne kaydırmak yerine etrafa dağıt
        glow_color = (title_color[0], title_color[1], title_color[2])
        glow_surf = title_font.render(title_text, True, glow_color)
        for dx, dy, a in [(-2, 0, 28), (2, 0, 28), (0, -2, 24), (0, 2, 24),
                          (-2, -2, 18), (2, -2, 18), (-2, 2, 18), (2, 2, 18)]:
            glow_surf.set_alpha(a)
            self.screen.blit(glow_surf, (title_rect.x + dx, title_rect.y + dy))
        self.screen.blit(title, title_rect)

        # Alt başlık
        subtitle_font = retro_style.get_font(s(20, minimum=11), bold=False)
        if is_survival_victory:
            subtitle = subtitle_font.render(t('survival_victory_subtitle', minutes=3), True, (100, 255, 150))
        else:
            subtitle = subtitle_font.render(t('game_over_subtitle'), True, (188, 205, 234))
        subtitle_rect = subtitle.get_rect(centerx=panel_rect.centerx, top=title_rect.bottom + s(6))
        self.screen.blit(subtitle, subtitle_rect)

        # Skor kartı - vurgulu cam panel
        score_top = subtitle_rect.bottom + s(12)
        score_rect = pygame.Rect(inner_left, score_top, inner_w, s(68))
        
        # Skor arka plan (daha koyu)
        score_bg = pygame.Surface(score_rect.size, pygame.SRCALPHA)
        score_bg.fill((*panel_fill_tint, 226))
        self.screen.blit(score_bg, score_rect.topleft)
        
        # Skor kenar - neon glow
        pygame.draw.rect(self.screen, (104, 166, 255), score_rect, 2, border_radius=12)
        
        # Skor label ve değer (ANİMASYONLU)
        score_label_font = retro_style.get_font(s(16, minimum=10), bold=True)
        score_label = score_label_font.render(t('final_score'), True, label_color_soft)
        score_label_rect = score_label.get_rect(midleft=(score_rect.x + s(18), score_rect.centery - s(10)))
        self.screen.blit(score_label, score_label_rect)
        
        score_value_font = retro_style.get_font(s(36, minimum=17), bold=True)
        # Animasyonlu skor gösterimi
        displayed = getattr(self, _disp_score_attr, getattr(self, _final_score_attr, 0))
        score_value = score_value_font.render(f'{displayed:,}'.replace(',', '.'), True, WHITE)
        score_value_rect = score_value.get_rect()
        score_value_rect.midright = (score_rect.right - s(18), score_rect.centery + s(2))
        # Hafif gölge: değeri daha belirgin yap
        score_shadow = score_value_font.render(f'{displayed:,}'.replace(',', '.'), True, (0, 0, 0))
        score_shadow.set_alpha(120)
        shadow_rect = score_value_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        self.screen.blit(score_shadow, shadow_rect)
        self.screen.blit(score_value, score_value_rect)
        
        # Rekor göstergesi
        if not _skip_record and getattr(self, _is_record_attr, False):
            record_font = retro_style.get_font(s(16, minimum=10), bold=True)
            record_text = record_font.render(t('new_high_score'), True, (255, 215, 0))
            self.screen.blit(record_text, record_text.get_rect(centerx=score_rect.centerx, top=score_rect.y + s(46)))
        
        # ============================================
        # YILDIZ SİSTEMİ (0-3 Yıldız) — skip_stars ise atlan
        # ============================================
        if not _skip_stars:
            star_area_y = score_rect.bottom + s(8)
            star_size = s(30)
            star_spacing = s(6)
            total_stars = 5
            total_star_width = total_stars * star_size + (total_stars - 1) * star_spacing
            star_start_x = panel_rect.centerx - total_star_width // 2

            earned = getattr(self, _earned_stars_attr, 0.0)  # Float değer

            # Animasyon için gösterilen yıldız sayısı
            # elapsed_sec kullanarak yavaşça açılsın
            star_reveal_start = 1.5  # 1.5 saniyeden sonra başla
            star_reveal_speed = 2.0  # Saniyede 2 yıldız açılsın

            if elapsed_sec > star_reveal_start:
                shown_progress = min(earned, (elapsed_sec - star_reveal_start) * star_reveal_speed)
            else:
                shown_progress = 0.0

            # 5 yıldız çiz
            for i in range(total_stars):
                star_x = star_start_x + i * (star_size + star_spacing)
                star_y = star_area_y

                # Bu yıldız için doluluk oranı hesapla
                if i < int(shown_progress):
                    # Tam dolu yıldız
                    fill_ratio = 1.0
                elif i < shown_progress:
                    # Kısmi dolu yıldız (ondalık kısım)
                    fill_ratio = shown_progress - int(shown_progress)
                else:
                    # Boş yıldız
                    fill_ratio = 0.0

                # Her yıldız için ufak "pop" animasyonu + glow yoğunluğu
                reveal_time = star_reveal_start + (i / max(0.001, star_reveal_speed))
                t_since = max(0.0, elapsed_sec - reveal_time)
                pop = 0.0
                if fill_ratio > 0.0:
                    pop = 0.16 * math.exp(-t_since * 6.0) * math.sin(t_since * 18.0)
                scale = max(0.85, 1.0 + pop)
                glow = min(1.0, 0.35 + 0.55 * fill_ratio + max(0.0, pop) * 1.5)
                self._draw_star(star_x, star_y, star_size, fill_ratio=fill_ratio, scale=scale, glow_intensity=glow)

            # Puan göstergesi (yıldızların altında)
            rating_y = star_area_y + star_size + s(7)
            rating_font = retro_style.get_font(s(18, minimum=10), bold=True)

            # Gösterilen puan (animasyonlu)
            displayed_rating = min(earned, shown_progress)
            rating_text = f"{displayed_rating:.1f} / 5.0"
            rating_color = (255, 215, 0) if displayed_rating >= 4.0 else label_color_soft

            rating_surf = rating_font.render(rating_text, True, rating_color)
            self.screen.blit(rating_surf, rating_surf.get_rect(centerx=panel_rect.centerx, top=rating_y))

            _stats_top_offset = rating_y + s(38)
        else:
            # skip_stars: yıldız/puan gösterimi yok; stats doğrudan skor kartının altında
            _stats_top_offset = score_rect.bottom + s(8)

        # İstatistikler - modern grid
        def format_time(seconds: int) -> str:
            seconds = max(0, int(seconds))
            minutes, sec = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                return f'{hours:02d}:{minutes:02d}:{sec:02d}'
            return f'{minutes:02d}:{sec:02d}'

        # Uyumlu ama ayırt edilebilir stat paleti:
        # Satır=Cyan, Seviye=Amber, Quadrix=Magenta, Süre=Mint
        stats = [
            (t('lines_cleared'), f'{getattr(self, _final_lines_attr, 0)}', (70, 224, 255)),
            (t('level'), f'{getattr(self, _final_level_attr, 0)}', (255, 188, 78)),
            (t('tetris_count'), f"{getattr(self, _final_tetrises_attr, 0)}", (232, 110, 255)),
            (t('time'), format_time(getattr(self, _final_time_attr, 0)), (114, 245, 176)),
        ]

        stats_cols = 2
        stats_gap = s(14)
        col_width = (inner_w - stats_gap) // stats_cols
        stats_top = _stats_top_offset  # Puan göstergesinden sonra (skip_stars ise doğrudan)
        row_height = s(64)  # Üst-alt satır arası boşluk artırıldı
        stat_font_label = retro_style.get_font(s(16, minimum=9), bold=True)
        stat_font_value = retro_style.get_font(s(24, minimum=12), bold=True)

        for idx, (label, value, color) in enumerate(stats):
            col = idx % stats_cols
            row = idx // stats_cols
            x = inner_left + col * (col_width + stats_gap)
            y = stats_top + row * row_height

            # Birim bazlı tint: genel tema koyu kalır, kartlar renk kimliği kazanır.
            stat_bg_color = (
                min(42, 8 + int(color[0] * 0.10)),
                min(48, 12 + int(color[1] * 0.12)),
                min(62, 24 + int(color[2] * 0.14)),
            )
            stat_border_color = (
                min(210, 46 + int(color[0] * 0.50)),
                min(220, 52 + int(color[1] * 0.50)),
                min(235, 70 + int(color[2] * 0.50)),
            )
            stat_value_color = (
                min(255, 90 + int(color[0] * 0.95)),
                min(255, 96 + int(color[1] * 0.95)),
                min(255, 108 + int(color[2] * 0.95)),
            )
            
            # Stat kart arka planı
            stat_rect = pygame.Rect(x, y, col_width, row_height)
            stat_bg = pygame.Surface(stat_rect.size, pygame.SRCALPHA)
            stat_bg.fill((*stat_bg_color, 216))
            self.screen.blit(stat_bg, stat_rect.topleft)
            pygame.draw.rect(self.screen, stat_border_color, stat_rect, 1, border_radius=10)
            
            # Sol renkli çizgi
            pygame.draw.rect(self.screen, color, (stat_rect.x + s(8), stat_rect.y + s(8), s(5), stat_rect.height - s(16)), border_radius=2)
            
            # Label ve değer (değerleri hizalı göster: sağa yasla + dikey padding)
            label_surface = stat_font_label.render(label, True, label_color_soft)
            value_surface = stat_font_value.render(value, True, stat_value_color)

            label_rect = label_surface.get_rect(midleft=(stat_rect.x + s(20), stat_rect.centery))
            value_rect = value_surface.get_rect()
            value_rect.midright = (stat_rect.right - s(14), stat_rect.centery + s(1))

            self.screen.blit(label_surface, label_rect)
            self.screen.blit(value_surface, value_rect)
        
        stats_rows = (len(stats) + stats_cols - 1) // stats_cols
        stats_bottom = stats_top + stats_rows * row_height

        # Kullanıcı bilgisi
        note_font = retro_style.get_font(s(15, minimum=9), bold=False)
        hint_font = retro_style.get_font(s(14, minimum=9), bold=False)

        # Daily mode status
        daily_status_text = None
        if self.game_mode == 'daily' and self.user_manager:
            status = self.user_manager.get_daily_status()
            if status:
                if status.get('completed'):
                    daily_status_text = (t('daily_completed'), (100, 220, 160))
                else:
                    remaining = max(0, DAILY_MAX_FAILURES - status.get('fails', 0))
                    color = (220, 180, 100) if remaining > 0 else (220, 100, 100)
                    daily_status_text = (t('remaining_tries').format(remaining, DAILY_MAX_FAILURES), color)

        # Modern butonlar
        buttons = [
            ('R', t('campaign_retry'), retro_style.primary, 'restart'),
            ('ESC', t('back_to_menu'), (200, 80, 80), 'menu'),
        ]
        button_width = (panel_rect.width - s(84)) // len(buttons)
        button_height = s(48)
        button_y = panel_rect.bottom - s(66)

        # Footer metinlerini istatistikler ile butonlar arasına sıkışmadan yerleştir.
        footer_lines: list[tuple[pygame.Surface, int]] = []
        score_note = hint_font.render(t('game_over_hint'), True, (170, 186, 214))
        footer_lines.append((score_note, s(8)))

        if self.user_manager and self.user_manager.get_current_user():
            current_user = self.user_manager.get_current_user()
            user_text = note_font.render(t('saved_profile').format(current_user), True, (176, 196, 226))
            footer_lines.append((user_text, s(8)))

        if daily_status_text:
            daily_font = retro_style.get_font(s(17, minimum=10), bold=True)
            daily_surf = daily_font.render(daily_status_text[0], True, daily_status_text[1])
            footer_lines.append((daily_surf, s(8)))

        total_footer_h = 0
        for surf, gap_after in footer_lines:
            total_footer_h += surf.get_height() + gap_after
        if total_footer_h > 0:
            total_footer_h -= footer_lines[-1][1]  # son satır sonrası ekstra gap yok

        footer_bottom = button_y - s(10)
        footer_top_min = stats_bottom + s(10)
        footer_top = max(footer_top_min, footer_bottom - total_footer_h)

        y_cursor = footer_top
        for surf, gap_after in reversed(footer_lines):
            self.screen.blit(surf, surf.get_rect(center=(panel_rect.centerx, y_cursor + surf.get_height() // 2)))
            y_cursor += surf.get_height() + gap_after
        
        btn_font_key = retro_style.get_font(s(13, minimum=9), bold=True)
        btn_font_label = retro_style.get_font(s(18, minimum=10), bold=True)
        
        for idx, (key, label, color, action) in enumerate(buttons):
            rect = pygame.Rect(panel_rect.x + s(36) + idx * (button_width + s(12)), button_y, button_width, button_height)
            disabled = action == 'restart' and not self.can_restart()
            hovered = (not disabled) and (mouse_pos is not None) and rect.collidepoint(mouse_pos)
            
            # Mouse click targets
            self._game_over_click_targets[action] = rect

            draw_rect = rect.copy()
            if hovered:
                draw_rect.y -= s(2)
            
            # Button background
            fill_alpha = 228 if hovered else (212 if not disabled else 132)
            fill_color = (28, 44, 78) if hovered else ((22, 34, 62) if not disabled else (15, 20, 36))
            
            btn_surf = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            btn_surf.fill((*fill_color, fill_alpha))
            
            # Üst highlight
            top_hi_alpha = 34 if hovered else (20 if not disabled else 8)
            for hi in range(min(12, draw_rect.height // 3)):
                h_alpha = int(top_hi_alpha * (1 - hi / 12))
                pygame.draw.line(btn_surf, (255, 255, 255, h_alpha), (0, hi), (draw_rect.width, hi))

            # Hover glow (ince dış parlama)
            if hovered:
                glow_rect = draw_rect.inflate(s(10), s(8))
                glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow, (color[0], color[1], color[2], 42), glow.get_rect(), border_radius=10)
                self.screen.blit(glow, glow_rect.topleft)
            
            self.screen.blit(btn_surf, draw_rect.topleft)
            
            # Border
            if disabled:
                border_color = (94, 102, 126)
            else:
                border_color = (min(255, color[0] + 38), min(255, color[1] + 38), min(255, color[2] + 38)) if hovered else color
            pygame.draw.rect(self.screen, border_color, draw_rect, 2, border_radius=10)
            
            # Sol strip
            strip_color = color if not disabled else (76, 84, 104)
            if hovered and not disabled:
                strip_color = (min(255, strip_color[0] + 28), min(255, strip_color[1] + 28), min(255, strip_color[2] + 28))
            pygame.draw.rect(self.screen, strip_color, (draw_rect.x + s(3), draw_rect.y + s(6), s(5), draw_rect.height - s(12)), border_radius=2)
            
            # Key badge
            key_color = color if not disabled else (120, 125, 145)
            if hovered and not disabled:
                key_color = (min(255, key_color[0] + 28), min(255, key_color[1] + 28), min(255, key_color[2] + 28))
            key_surf = btn_font_key.render(key, True, key_color)
            self.screen.blit(key_surf, (draw_rect.x + s(16), draw_rect.y + s(8)))
            
            # Label
            label_color = (250, 252, 255) if hovered and not disabled else ((240, 245, 255) if not disabled else (140, 145, 160))
            label_surf = btn_font_label.render(label, True, label_color)
            self.screen.blit(label_surf, label_surf.get_rect(center=(draw_rect.centerx + s(8), draw_rect.centery + s(4))))

        # Warning message
        if self.game_over_warning and self.game_over_warning_timer > 0:
            warn_font = retro_style.get_font(s(15, minimum=10), bold=True)
            warn_surface = warn_font.render(self.game_over_warning, True, (255, 120, 120))
            warning_y = min(button_y + button_height + s(12), panel_rect.bottom - s(18))
            self.screen.blit(warn_surface, warn_surface.get_rect(center=(panel_rect.centerx, warning_y)))
    
    def draw_achievement_notifications(self):
        """Yeni kazanılan başarıları ekranda göster"""
        if len(self.achievement_notifications) > 0:
            pass  # Debug output removed
        
        current_time = pygame.time.get_ticks()
        y_offset = 18

        def _ease_out_cubic(v: float) -> float:
            v = max(0.0, min(1.0, float(v)))
            return 1.0 - pow(1.0 - v, 3)

        def _get_notif_panel_surface(width: int, height: int) -> tuple[pygame.Surface, pygame.Surface]:
            cache_key = (int(width), int(height))
            cached = self._achievement_notif_surface_cache.get(cache_key)
            if cached is not None:
                return cached

            scale = 2  # supersample for smoother edges/lines
            hi_w = width * scale
            hi_h = height * scale
            radius = 16 * scale

            base_hi = pygame.Surface((hi_w, hi_h), pygame.SRCALPHA)

            # Cam arkaplan + yumuşak üst highlight
            pygame.draw.rect(base_hi, retro_style.glass_bg, base_hi.get_rect(), border_radius=radius)
            highlight_h = min(38 * scale, hi_h // 3)
            for y in range(highlight_h):
                h_alpha = int(28 * (1 - y / max(1, highlight_h)))
                pygame.draw.line(base_hi, (255, 255, 255, h_alpha), (0, y), (hi_w, y))

            gold = UIColors.NEON_GOLD
            border_color = (*gold, 180)
            pygame.draw.rect(base_hi, border_color, base_hi.get_rect(), 2 * scale, border_radius=radius)

            strip_w = 5 * scale
            strip_rect = pygame.Rect(12 * scale, 14 * scale, strip_w, hi_h - 28 * scale)
            pygame.draw.rect(base_hi, (*gold, 165), strip_rect, border_radius=3 * scale)

            # Yıldız ikonu (anti-aliased line + dolgu)
            star_center = (48 * scale, hi_h // 2)
            star_size = 19 * scale
            points = []
            for i in range(10):
                angle = math.pi / 2 + (2 * math.pi * i / 10)
                radius_i = star_size if i % 2 == 0 else max(7 * scale, star_size // 2)
                x = star_center[0] + radius_i * math.cos(angle)
                y = star_center[1] - radius_i * math.sin(angle)
                points.append((x, y))
            pygame.draw.polygon(base_hi, (*gold, 220), points)
            pygame.draw.aalines(base_hi, (255, 246, 190, 245), True, points)

            panel = pygame.transform.smoothscale(base_hi, (width, height))

            # Gölge yüzeyi de cache'le
            shadow = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 92), shadow.get_rect(), border_radius=16)

            result = (panel, shadow)
            self._achievement_notif_surface_cache[cache_key] = result
            return result
        
        def _ellipsis(text: str, font: pygame.font.Font, max_width: int) -> str:
            if not text:
                return ""
            if font.size(text)[0] <= max_width:
                return text
            suffix = "..."
            available = max(0, max_width - font.size(suffix)[0])
            # Incremental trim from the end.
            trimmed = text
            while trimmed and font.size(trimmed)[0] > available:
                trimmed = trimmed[:-1]
            return (trimmed.rstrip() + suffix) if trimmed else suffix

        for notification in self.achievement_notifications[:]:
            elapsed = current_time - notification['time']
            
            # 5 saniye sonra yavaşça kaybolsun
            if elapsed > 5000:
                notification['alpha'] -= 6
                if notification['alpha'] <= 0:
                    self.achievement_notifications.remove(notification)
                    continue
            
            achievement = notification['achievement']
            
            # Bildirim kutusu
            box_width = 392
            box_height = 104
            box_x = self.window_width - box_width - 20
            box_y = y_offset

            # Yumuşak giriş animasyonu (ilk 300ms)
            entry_ms = 300.0
            entry_t = min(1.0, max(0.0, elapsed / entry_ms))
            eased = _ease_out_cubic(entry_t)
            slide_px = int((1.0 - eased) * 24)
            draw_x = box_x + slide_px

            gold = UIColors.NEON_GOLD
            panel_base, shadow_base = _get_notif_panel_surface(box_width, box_height)

            # Hafif gölge (arka plana)
            shadow = shadow_base.copy()
            shadow.set_alpha(int(notification['alpha'] * 0.58))
            self.screen.blit(shadow, (draw_x + 3, box_y + 4))

            # Tema uyumlu panel (cache'den)
            notif = panel_base.copy()

            # Metinler (tema renkleri)
            content_x = 82
            content_w = box_width - content_x - 16

            title = t('achievement_unlocked')
            title_font = retro_style.get_fitting_font(title, base_size=20, max_width=content_w, bold=True, min_size=12)
            title_surf = title_font.render(title, True, gold)
            notif.blit(title_surf, (content_x, 10))

            name = str(achievement.get('name', ''))
            name_font = retro_style.get_fitting_font(name, base_size=19, max_width=content_w, bold=True, min_size=12)
            name_surf = name_font.render(_ellipsis(name, name_font, content_w), True, retro_style.text_primary)
            notif.blit(name_surf, (content_x, 38))

            desc = str(achievement.get('description', ''))
            desc_font = retro_style.get_fitting_font(desc, base_size=15, max_width=content_w, bold=False, min_size=10)
            desc_text = _ellipsis(desc, desc_font, content_w)
            desc_surf = desc_font.render(desc_text, True, retro_style.text_secondary)
            notif.blit(desc_surf, (content_x, 68))

            notif.set_alpha(notification['alpha'])
            self.screen.blit(notif, (draw_x, box_y))
            
            y_offset += box_height + 12
    
    def can_restart(self) -> bool:
        return True

    def show_game_over_warning(self, message: str, duration: float = 2.0) -> None:
        self.game_over_warning = message
        self.game_over_warning_timer = max(0.0, float(duration))
    
    # ============================================
    # GAME OVER YARDIMCI FONKSİYONLARI
    # ============================================
    
    def _calculate_stars(self) -> float:
        """0.0-5.0 yıldız: mevcut skorun kişisel en yükseğe oranı.

        İstenen davranış:
        - Kullanıcının en yüksek skoru 5.0 yıldız kabul edilir.
        - Bu oyundaki skor, en yükseğe oranlanır ve 0.0-5.0 aralığına çevrilir.
        """
        score = float(max(0, getattr(self, '_final_score', self.board.score) or 0))

        best = 0.0
        try:
            if self.score_manager and getattr(self.score_manager, 'highscores', None):
                best = float(
                    max(
                        (int(e.get('score', 0)) for e in (self.score_manager.highscores or []) if isinstance(e, dict)),
                        default=0,
                    )
                )
        except Exception:
            best = 0.0
        # Eğer bu oyun yeni rekor ise, 5.0 yıldız olsun.
        best = max(best, score)
        if best <= 0.0:
            return 0.0

        ratio = max(0.0, min(1.0, score / best))
        return max(0.0, min(5.0, ratio * 5.0))
    
    def _check_new_record(self) -> bool:
        """Mevcut skor rekor mu kontrol et."""
        try:
            if self.score_manager:
                return self.score_manager.is_high_score(self._final_score)
        except Exception:
            pass
        return False
    
    def _draw_star(
        self,
        x,
        y,
        size,
        fill_ratio=1.0,
        color=(255, 215, 0),
        empty_color=(60, 70, 90),
        scale: float = 1.0,
        glow_intensity: float = 0.6,
    ):
        """5 köşeli yıldız çiz - kısmi doluluk + glow + scale desteği.

        Not: Glow/alpha için küçük bir SRCALPHA surface'e çizip ekrana blit eder.
        """
        fill_ratio = float(max(0.0, min(1.0, fill_ratio)))
        scale = float(max(0.7, min(1.6, scale)))
        glow_intensity = float(max(0.0, min(1.0, glow_intensity)))

        # Merkez sabit kalsın; ölçek sadece çizimi büyütüp küçültsün.
        base_cx = x + size * 0.5
        base_cy = y + size * 0.5
        r_outer = (size * 0.5) * scale
        r_inner = (size * 0.25) * scale

        pad = max(6, int(size * 0.18))
        surf_w = int(size * scale) + pad * 2
        surf_h = int(size * scale) + pad * 2
        star_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

        # Surface koordinatlarında merkez
        cx = surf_w * 0.5
        cy = surf_h * 0.5

        # Yıldız noktaları
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((int(px), int(py)))

        # Boş yıldız tabanı
        pygame.draw.polygon(star_surf, (*empty_color, 255), points)
        edge = tuple(min(255, c + 35) for c in empty_color)
        pygame.draw.polygon(star_surf, (*edge, 220), points, 1)

        if fill_ratio > 0.0:
            filled = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
            pygame.draw.polygon(filled, (*color, 255), points)

            # Kısmi doluluk: soldan sağa clip
            fill_w = int((surf_w) * fill_ratio)
            if fill_w > 0:
                star_surf.blit(filled, (0, 0), area=pygame.Rect(0, 0, fill_w, surf_h))

            # Glow: 2 katman outline
            glow_a1 = int(90 * glow_intensity)
            glow_a2 = int(55 * glow_intensity)
            glow_col = (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40))
            if glow_a2 > 0:
                pygame.draw.polygon(star_surf, (*glow_col, glow_a2), points, 6)
            if glow_a1 > 0:
                pygame.draw.polygon(star_surf, (*glow_col, glow_a1), points, 3)

            # İnce parlak kenar
            pygame.draw.polygon(star_surf, (*glow_col, min(255, 180)), points, 1)

        # Ekrana ortalı şekilde blit
        dest = star_surf.get_rect(center=(int(base_cx), int(base_cy)))
        self.screen.blit(star_surf, dest)
    
    def _update_confetti(self, current_time):
        """Konfeti parçacıklarını güncelle ve yenilerini oluştur (zaman-bazlı)."""
        # Bu efekt game_over overlay çiziminde update()'tan bağımsız çalışıyor.
        # O yüzden dt'yi pygame.time.get_ticks() farkından türetiyoruz.
        last = getattr(self, '_confetti_last_time', current_time)
        dt_ms = max(0.0, min(100.0, float(current_time - last)))
        self._confetti_last_time = current_time
        dt_frames = dt_ms / 16.666  # ~60 FPS ölçeği

        # Yeni konfeti parçacıkları ekle (orijinal: frame başına 5 -> 60 FPS'te ~300/sn)
        emit_acc = float(getattr(self, '_confetti_emit_accum', 0.0))
        emit_acc += 5.0 * dt_frames
        emit_count = int(emit_acc)
        self._confetti_emit_accum = emit_acc - emit_count

        capacity = max(0, 200 - len(self._confetti_particles))
        emit_count = min(emit_count, capacity)
        for _ in range(emit_count):
            x = random.randint(0, self.window_width)
            particle = {
                'x': float(x),
                'y': float(-10),
                'vx': random.uniform(-1, 1),
                'vy': random.uniform(2, 4),
                'rotation': random.uniform(0, 360),
                'rotation_speed': random.uniform(-5, 5),
                'color': random.choice([
                    (255, 215, 0),   # Altın
                    (255, 50, 50),   # Kırmızı
                    (50, 255, 50),   # Yeşil
                    (50, 150, 255),  # Mavi
                    (255, 50, 255),  # Magenta
                    (255, 165, 0),   # Turuncu
                    (255, 255, 255), # Beyaz
                ]),
                'size': random.randint(4, 8),
                'shape': random.choice(['rect', 'circle']),
                'life': float(random.randint(200, 400)),
            }
            self._confetti_particles.append(particle)

        # Mevcut parçacıkları güncelle
        for p in self._confetti_particles[:]:
            p['x'] += p['vx'] * dt_frames
            p['y'] += p['vy'] * dt_frames
            p['vy'] += 0.05 * dt_frames  # Hafif yerçekimi
            p['vx'] *= 0.99 ** dt_frames  # Hava sürtünmesi
            p['rotation'] += p['rotation_speed'] * dt_frames
            p['life'] = float(p.get('life', 0.0)) - dt_frames

            # Ekran dışına çıktı veya öldü
            if p['y'] > self.window_height + 20 or p['life'] <= 0:
                self._confetti_particles.remove(p)
    
    def _draw_confetti(self):
        """Konfeti parçacıklarını çiz (optimizeli)."""
        for p in self._confetti_particles:
            x = int(p['x'])
            y = int(p['y'])
            size = p['size']
            color = p['color']
            
            # Alpha fade
            alpha = min(255, int(p['life'] * 2))
            if alpha <= 0:
                continue
            
            if p['shape'] == 'rect':
                # Dönen dikdörtgen - alpha yeterince yüksekse basit çiz
                if alpha >= 240:
                    # Opak: doğrudan rect (surface+rotate+blit yerine)
                    half_w, half_h = size, size // 2
                    pygame.draw.rect(self.screen, color, (x - half_w, y - half_h, size * 2, size))
                else:
                    surf = pygame.Surface((size * 2, size), pygame.SRCALPHA)
                    surf.fill((*color, alpha))
                    rotated = pygame.transform.rotate(surf, p['rotation'])
                    rect = rotated.get_rect(center=(x, y))
                    self.screen.blit(rotated, rect)
            else:
                # Daire - opak ise doğrudan çiz
                if alpha >= 240:
                    pygame.draw.circle(self.screen, color, (x, y), size // 2)
                else:
                    surf = pygame.Surface((size, size), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (*color, alpha), (size // 2, size // 2), size // 2)
                    self.screen.blit(surf, (x - size // 2, y - size // 2))

    def restart(self):
        """Oyunu yeniden başlat"""
        self.game_over_warning = ""
        self.game_over_warning_timer = 0.0
        # Torba (bag) sistemini sıfırla — yeni oyun yeni torba
        self._piece_bag = []
        # Üst üste aynı parça takibini sıfırla
        self._last_piece_identity = None
        self._last_piece_streak = 0
        # Recreate board to ensure no residual references remain and all arrays are fresh
        from board import Board
        self.board = Board(width=self.board_width, height=self.board_height)
        # Also ensure every cell is firmly cleared even if other code mutated occupancy
        for y in range(self.board.height):
            for x in range(self.board.width):
                self.board.grid[y][x] = BLACK
                self.board.texture_grid[y][x] = None
                self.board.occupancy[y][x] = False
        # Önce kuyruğu doldur, sonra kuyruktan al (senkronizasyon için)
        self.next_piece_queue = [self.spawn_new_piece() for _ in range(3)]  # Sonraki 3 parça
        self.current_piece = self.next_piece_queue.pop(0)  # Kuyruktan ilk parçayı al
        self.held_piece = None
        self.second_held_piece = None
        self.can_hold = True
        self.can_hold2 = True
        self.discard_held_uses = 5  # B tuşu hakkını sıfırla
        self.game_over = False
        self.paused = False
        if hasattr(self, 'sound') and self.sound:
            self.sound.unduck_music()
        self.fall_time = 0
        self.fall_speed = self.get_initial_speed()
        self.game_time = 0
        self.line_clear_animation = 0
        self.combo_message = ""
        self.combo_message_time = 0
        self.particles = []
        self.achievement_notifications = []
        self.current_music_track = None
        
        # Sweep ve blok düşme animasyonlarını sıfırla
        self.line_clear_sweep_rows = []
        self.line_clear_sweep_progress = 0.0
        self.line_clear_sweep_active = False
        self.line_clear_pending_rows = []
        self.line_clear_pending_colors = {}
        self.falling_block_animations = []
        self.drop_trails = []  # Drop trail efektlerini sıfırla
        
        # Game over animasyon değişkenlerini sıfırla
        self._game_over_active = False
        self._game_over_pending = False
        self._game_over_peek_active = False
        self._game_over_peek_rect = None
        self._game_over_start_time = 0
        self._final_score = 0
        self._final_lines = 0
        self._final_level = 1
        self._final_tetrises = 0
        self._final_time = 0
        self._earned_stars = 0.0
        self._last_star_sound = 0
        self._displayed_score = 0
        self._confetti_particles = []
        self._confetti_active = False
        self._game_over_fade_alpha = 0
        self._is_new_record = False
        
        # Tema renklerini uygula
        self.apply_theme_to_pieces()
        
        # Müziği tekrar başlat - ayarlardan seçilen müziği kullan
        # force=True: Game over sonrası müziğin kesinlikle yeniden yüklenmesini sağla
        if self.sound_enabled and self.sound.music_enabled:
            self.sound.stop_music()
            self._start_music_playlist(force=True)

        # Reset particles, ambient particles and background falling blocks
        self.particles = []
        self.ambient_particles = []
        self.create_ambient_particles()
        self.falling_blocks = get_shared_falling_blocks_layer('default') if self.effects_enabled else None
