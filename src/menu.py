"""Ana menü ve UI bileşenleri"""

import math
import re
import os
import sys
import json
import threading
import uuid
from datetime import datetime
from typing import Any
from pathlib import Path
import webbrowser
from urllib.parse import quote

import pygame

# macOS detection - SRCALPHA surface'ler bazen crash yapabiliyor
_IS_MACOS = sys.platform == 'darwin'

from constants import *
from retro_style import retro_style
from background_effects import FallingBlocksLayer, get_shared_falling_blocks_layer
from block_styles import BlockStyleManager, ALL_PIECE_NAMES
from renderers.jelly_renderer import draw_jelly_block
from workshop_blocks import WORKSHOP_MODES, DEFAULT_PIECE_COLORS
from themes import CUSTOM_THEME_NAME
from avatar_presets import resolve_avatar_value
from localization import t, get_text, get_language, set_language, get_language_name, SUPPORTED_LANGUAGES, get_all_languages, is_language_complete, get_language_flag
from ui_language_profile import apply_language_ui_profile, get_font_for_language
from platform_utils import (
    is_primary_modifier,
    get_modifier_key_name,
    is_fullscreen_toggle,
    build_support_email_body_template,
    normalize_mouse_pos,
    get_mouse_pos,
    get_native_resolution,
)
from ui_theme import UIColors, UIFonts
from asset_manager import load_image
from text_cache import render_text
from gamepad_manager import get_gamepad_manager, is_gamepad_connected
from steam_leaderboards import SteamLeaderboardService
from achievements import ACHIEVEMENTS, get_achievement_name
from user_manager import DAILY_MAX_FAILURES
try:
    from menu_layout_embedded import EMBEDDED_MENU_LAYOUT
except Exception:
    EMBEDDED_MENU_LAYOUT = {}
try:
    from campaign.level_data import get_level as _campaign_get_level
except Exception:
    _campaign_get_level = None


# SOS / Contact links
CONTACT_EMAIL = 'vibecode.production@gmail.com'
INSTAGRAM_URL = 'https://www.instagram.com/vibecode.production/'


def _build_gmail_compose_url(to_email: str, subject: str = '', body: str = '') -> str:
    to_email = (to_email or '').strip()
    subject_q = quote(subject or '')
    body_q = quote(body or '')
    # Gmail web compose endpoint
    return f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(to_email)}&su={subject_q}&body={body_q}"


CLASSIC_PIECE_ORDER = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
CLASSIC_COLOR_LOOKUP = {name: COLORS[idx] for idx, name in enumerate(CLASSIC_PIECE_ORDER)}
EXTRA_COLOR_LOOKUP = {
    'Plus': (255, 0, 255),
    'Y': (0, 255, 255),
    'Domino': (255, 128, 0),
    'BigSquare': (255, 215, 0),
}

PIECE_PREVIEW_SHAPES = {
    'I': [(0, 1), (1, 1), (2, 1), (3, 1)],
    'O': [(0, 0), (1, 0), (0, 1), (1, 1)],
    'T': [(1, 0), (0, 1), (1, 1), (2, 1)],
    'S': [(1, 0), (2, 0), (0, 1), (1, 1)],
    'Z': [(0, 0), (1, 0), (1, 1), (2, 1)],
    'J': [(0, 0), (0, 1), (1, 1), (2, 1)],
    'L': [(2, 0), (0, 1), (1, 1), (2, 1)],
    'Plus': [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],
    'Y': [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (1, 2)],
    'Domino': [(0, 0), (1, 0)],
    'BigSquare': [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)]
}

PIECE_LABELS = {
    'I': 'I Bloğu (Çubuk)',
    'O': 'O Bloğu (Kare)',
    'T': 'T Bloğu (T)',
    'S': 'S Bloğu (Sol)',
    'Z': 'Z Bloğu (Sağ)',
    'J': 'J Bloğu (Sol köşe)',
    'L': 'L Bloğu (Sağ köşe)',
    'Plus': '+ Bloğu (Artı)',
    'Y': 'Y Bloğu (Denge)',
    'Domino': 'Domino (2\'li)',
    'BigSquare': 'Mega Kare'
}

def _resolve_root_dir() -> Path:
    """Return the directory that stores runtime assets (PyInstaller safe)."""
    meipass = getattr(sys, '_MEIPASS', None)
    if isinstance(meipass, str) and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def _resolve_menu_layout_runtime_path() -> Path:
    """Source-run layout override path (development only)."""
    project_layout = Path(__file__).resolve().parent.parent / 'menu_layout_runtime.json'
    return project_layout


def _decode_layout_payload(raw: Any) -> tuple[
    dict[str, Any],
    str,
    tuple[int, int] | None,
    tuple[int, int, int, int] | None,
]:
    rects = raw.get('rects', {}) if isinstance(raw, dict) else {}
    if not isinstance(rects, dict):
        rects = {}

    coord_space = ''
    reference_window = None
    reference_canvas = None
    if isinstance(raw, dict):
        coord_space = str(raw.get('coord_space', '')).strip().lower()
        rw = raw.get('reference_window')
        if isinstance(rw, list) and len(rw) == 2:
            try:
                reference_window = (max(1, int(rw[0])), max(1, int(rw[1])))
            except Exception:
                reference_window = None
        rc = raw.get('reference_canvas')
        if isinstance(rc, list) and len(rc) == 4:
            try:
                reference_canvas = (int(rc[0]), int(rc[1]), max(1, int(rc[2])), max(1, int(rc[3])))
            except Exception:
                reference_canvas = None
    if not coord_space:
        coord_space = 'canvas_pct' if reference_canvas is not None else 'screen_pct'

    return rects, coord_space, reference_window, reference_canvas


ROOT_DIR = _resolve_root_dir()
LOGO_PATH_CANDIDATES = [
    ROOT_DIR / 'backgrounds' / 'logo.png',
    ROOT_DIR / 'backgrounds' / 'lo.png',
    ROOT_DIR / 'public' / 'logo.png',
    ROOT_DIR / 'assets' / 'logo.png',
]

AVATAR_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')


def get_control_tabs():
    """Yerelleştirilmiş kontrol sekmeleri"""
    return [
        ('single_player', t('tab_single_player')),
        ('pvp.player1', t('tab_pvp_player1')),
        ('pvp.player2', t('tab_pvp_player2')),
        ('gamepad', t('tab_gamepad')),
    ]


def get_control_actions():
    """Yerelleştirilmiş kontrol eylemleri"""
    
    single_player_actions = [
        ('move_left', t('ctrl_move_left')),
        ('move_right', t('ctrl_move_right')),
        ('soft_drop', t('ctrl_soft_drop')),
        ('hard_drop', t('ctrl_hard_drop')),
        ('rotate', t('ctrl_rotate')),
        ('hold', t('ctrl_hold')),
        ('pause', t('ctrl_pause')),
        ('fullscreen_toggle', t('ctrl_fullscreen_toggle')),
    ]
    
    return {
        'single_player': single_player_actions,
        'pvp.player1': [
            ('move_left', t('ctrl_move_left')),
            ('move_right', t('ctrl_move_right')),
            ('soft_drop', t('ctrl_soft_drop')),
            ('hard_drop', t('ctrl_hard_drop')),
            ('rotate', t('ctrl_rotate')),
        ],
        'pvp.player2': [
            ('move_left', t('ctrl_move_left')),
            ('move_right', t('ctrl_move_right')),
            ('soft_drop', t('ctrl_soft_drop')),
            ('hard_drop', t('ctrl_hard_drop')),
            ('rotate', t('ctrl_rotate')),
        ],
    }


def get_mode_music_entries():
    """Yerelleştirilmiş müzik modu girişleri"""
    return [
        ('campaign', t('music_campaign')),
        ('classic', t('music_classic')),
        ('daily', t('music_daily')),
        ('sprint', t('music_sprint')),
        ('ultra', t('music_ultra')),
        ('zen', t('music_zen')),
        ('tetris2', t('music_tetris2')),
        ('mystery', t('music_mystery')),
        ('wide', t('music_wide')),
        ('survival', t('music_survival')),
        ('cascade', t('music_cascade')),
        ('pvp', t('music_pvp')),
        ('hardcore', t('music_hardcore')),
    ]


# Eski değişkenler geriye uyumluluk için (deprecate edilecek)
CONTROL_TABS = [
    ('single_player', 'Tek Oyuncu'),
    ('pvp.player1', 'PvP - Oyuncu 1'),
    ('pvp.player2', 'PvP - Oyuncu 2'),
]

CONTROL_ACTIONS = {
    'single_player': [
        ('move_left', 'Sola kay'),
        ('move_right', 'Sağa kay'),
        ('soft_drop', 'Hızlı indir'),
        ('hard_drop', 'Anında bırak'),
        ('rotate', 'Döndür'),
        ('hold', 'Hold / değiştir'),
        ('pause', 'Duraklat'),
    ],
    'pvp.player1': [
        ('move_left', 'Sola kay'),
        ('move_right', 'Sağa kay'),
        ('soft_drop', 'Hızlı indir'),
        ('hard_drop', 'Anında bırak'),
        ('rotate', 'Döndür'),
    ],
    'pvp.player2': [
        ('move_left', 'Sola kay'),
        ('move_right', 'Sağa kay'),
        ('soft_drop', 'Hızlı indir'),
        ('hard_drop', 'Anında bırak'),
        ('rotate', 'Döndür'),
    ],
}

MODE_MUSIC_ENTRIES = [
    ('campaign', 'Görev Modu'),
    ('classic', 'Klasik (Tek Oyuncu)'),
    ('daily', 'Daily Challenge'),
    ('sprint', 'Sprint Mode'),
    ('ultra', 'Ultra Mode'),
    ('zen', 'Zen Mode'),
    ('tetris2', 'Quadrix Extra'),
    ('mystery', 'Kart Ustalığı'),
    ('wide', 'Wide Mode'),
    ('survival', 'Survival Mode'),
    ('cascade', 'Cascade Mode'),
    ('pvp', 'LocalPvP (2 Oyuncu)'),
    ('hardcore', 'Hardcore Mode'),
]

BUILT_IN_TRACK_CHOICES = []

SUPPORTED_MUSIC_EXTENSIONS = ('.wav', '.ogg', '.mp3', '.mod', '.xm', '.it')


def get_piece_base_color(piece_name, theme_manager=None):
    if theme_manager:
        try:
            return theme_manager.get_piece_color(piece_name)
        except Exception:
            pass
    if piece_name in CLASSIC_COLOR_LOOKUP:
        return CLASSIC_COLOR_LOOKUP[piece_name]
    return EXTRA_COLOR_LOOKUP.get(piece_name, (200, 200, 200))

class Menu:
    """Ana menü sınıfı"""
    
    def __init__(self, screen, user_manager=None, settings_manager=None):
        """Menüyü başlat"""
        self.screen = screen
        self.user_manager = user_manager
        self.settings_manager = settings_manager
        self.font_menu = retro_style.get_font(32, bold=True)
        self.font_small = retro_style.get_font(24)
        
        self._update_options()
        self.selected = 0
        self.state = 'main'  # main, highscores, settings
        self.option_rects = []  # Mouse için hitbox'lar
        self.color_edit_buttons = []  # Özel renk düzenleme butonları
        self.color_reset_buttons = []  # Renk sıfırlama butonları
        self.scroll_offset = 0  # Kaydırma için
        self._nav_source = 'mouse'  # 'mouse' veya 'keyboard' — input kaynağı ayrımı
        self._mouse_in_panel = False  # Mouse option_rects üzerinde mi?
        self.fullscreen = False  # Tam ekran durumu
        self.background_fx = get_shared_falling_blocks_layer('default')
        # Belirli menü kartlarının içinde (cam panel arkasında) domino yağmuru
        domino_shapes = [[(0, 0), (1, 0)], [(0, 0), (0, 1)]]
        domino_colors = [UIColors.NEON_CYAN, UIColors.NEON_GREEN, UIColors.NEON_MAGENTA]
        self._card_domino_fx = {
            'achievements': FallingBlocksLayer(block_count=6, layer_alpha=200, shape_pool=domino_shapes, color_pool=domino_colors),
            'switch_user': FallingBlocksLayer(block_count=6, layer_alpha=200, shape_pool=domino_shapes, color_pool=domino_colors),
        }
        self._logo_surface = None
        self._logo_size = 0
        self._logo_image_original = None
        self._logo_image_failed = False
        self.show_exit_prompt = False
        self.exit_yes_rect = None
        self.exit_no_rect = None
        self.info_message = ''
        self.info_timer = 0
        self.daily_hint = ''
        self.daily_hint_color = retro_style.accent
        self.daily_challenge_title = ''
        self.show_daily_prompt = False
        self.daily_prompt_selected = 0
        self.daily_prompt_challenge = None
        self.daily_play_rect = None
        self.daily_cancel_rect = None
        self.campaign_quick_play_rect = None
        self.campaign_quick_level = 1
        self._hero_avatar_surface = None
        self._hero_avatar_signature = None

        self._emoji_font_cache = {}

        # SOS (Contact) UI
        self.sos_open = False
        self.sos_button_rect = None
        self.sos_panel_rect = None
        self.sos_mail_rect = None
        self.sos_instagram_rect = None

        # Corner buttons (köşe butonları)
        self.corner_settings_rect = None
        self.corner_language_rect = None
        self.corner_mute_rect = None
        self.corner_switch_user_rect = None
        self.corner_credits_rect = None
        self.corner_achievements_rect = None
        self.corner_guide_rect = None
        self._is_muted = False  # Ses durumu (dışarıdan set edilir)

        # Main menu dil paneli (köşe dil butonu için)
        self.menu_language_panel_open = False
        self.menu_language_panel_selected = 0
        self.menu_language_panel_scroll = 0
        self.menu_language_panel_item_rects = []
        self.menu_language_panel_rect = None
        # Scrollbar drag state
        self.menu_language_panel_sb_thumb_rect: 'pygame.Rect | None' = None
        self.menu_language_panel_sb_container_rect: 'pygame.Rect | None' = None
        self.menu_language_panel_sb_drag_active: bool = False
        self.menu_language_panel_sb_drag_offset_y: int = 0

        # Emoji icon cache (assets/emoji/ klasöründen yüklenen PNG'ler)
        self._emoji_icon_cache = {}

        # Grid overlay cache (menu arka planındaki ince ızgara)
        self._grid_overlay_cache = None
        self._grid_overlay_cache_size = None

        # Showcase card rects (sol taraftaki tanıtım kartları)
        self.showcase_piece_workshop_rect = None
        self.showcase_block_styles_rect = None
        self._showcase_anim_tick = 0  # Animasyon sayacı

        # Main menu UI surface caches (avoid per-frame Surface allocations)
        self._hero_header_cache = None
        self._hero_header_cache_signature = None
        self._sos_fill_overlay_cache = None
        self._sos_fill_overlay_cache_signature = None
        self._tile_flavor_scaled_cache = {}

        # Ana menü sağ-alt: Steam skor paneli (Kart Ustalığı)
        # publisher_key ve app_id sadece ortam değişkenleriyle aktif olur;
        # proxy yoksa ve STEAM_WEB_API_KEY set edilmişse direct fallback devreye girer.
        self._leaderboard_service = SteamLeaderboardService(
            backend_base_url=os.getenv('LEADERBOARD_BACKEND_URL', 'http://127.0.0.1:8787'),
            publisher_key=os.getenv('STEAM_WEB_API_KEY', ''),
            app_id=int(os.getenv('STEAM_APP_ID', '0') or '0'),
        )
        self._mystery_lb_tab = 'global'
        self._mystery_lb_tab_rects = {}
        self._mystery_lb_entries = {'global': [], 'friends': []}
        self._mystery_lb_error = ''
        self._mystery_lb_last_fetch_ms = -120_000
        self._mystery_lb_refresh_ms = 45_000
        self._mystery_lb_loading = False

        # Steam oyuncu profil cache: steam_id -> {personaname, avatarmedium, ...}
        self._steam_player_cache: dict[str, dict] = {}
        # Avatar image cache: avatar_url -> bytes (arka planda indirildi)
        self._steam_avatar_bytes: dict[str, bytes] = {}
        # Avatar surface cache: avatar_url -> pygame.Surface (main thread'de oluşturuldu)
        self._steam_avatar_surf: dict[str, pygame.Surface | None] = {}

        # Dashboard panel context cache
        self._panel_context_cache = None
        self._panel_context_cache_sig = None
        self._achievements_panel_cache = {
            'path': None,
            'mtime': None,
            'recent': [],
            'percent': 0,
        }

        # Menü yerleşimi runtime override (tools/apply_menu_layout_from_editor.py çıktısı)
        self._layout_override_path = _resolve_menu_layout_runtime_path()
        self._layout_override_cache = None
        self._layout_override_mtime = None
        self._layout_override_coord_space = 'screen_pct'
        self._layout_override_reference_window = None
        self._layout_override_reference_canvas = None

    def _get_grid_overlay(self, size: tuple[int, int]) -> pygame.Surface:
        cached = self._grid_overlay_cache
        if cached is not None and self._grid_overlay_cache_size == size:
            return cached
        width, height = size
        # macOS: SRCALPHA surface'ler bazen crash yapabiliyor
        if _IS_MACOS:
            # macOS için basit non-alpha surface
            grid_overlay = pygame.Surface((width, height))
            grid_overlay.fill((20, 20, 30))  # Koyu arka plan
            grid_overlay.set_colorkey((20, 20, 30))  # Transparent yap
            grid_color = (60, 60, 70)
            step = 30
            for x in range(0, width, step):
                pygame.draw.line(grid_overlay, grid_color, (x, 0), (x, height))
            for y in range(0, height, step):
                pygame.draw.line(grid_overlay, grid_color, (0, y), (width, y))
        else:
            grid_overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            grid_color = (190, 190, 200, 30)
            step = 30
            for x in range(0, width, step):
                pygame.draw.line(grid_overlay, grid_color, (x, 0), (x, height))
            for y in range(0, height, step):
                pygame.draw.line(grid_overlay, grid_color, (0, y), (width, y))
        self._grid_overlay_cache = grid_overlay
        self._grid_overlay_cache_size = size
        return grid_overlay
    
    def _update_options(self):
        """Dile göre menü seçeneklerini güncelle"""
        # Menü seçenekleri artık dil-bağımsız anahtarlarla tutulur.
        # Görünen etiketler draw() sırasında t(key) ile üretilir.
        # Yeni dashboard yerleşiminde görünen kutular + köşe aksiyonları.
        self.options = [
            # Merkez paneller (indeks 0-8) — tuş navigasyonu bu aralıkta kalır
            'new_gen_tetris',
            'piece_workshop',
            'extras',
            'pvp_2_players',
            'tutorial_mode',
            'achievements',
            'daily_challenge',
            'campaign_mode',
            'block_styles',

            # Köşe/kısayol aksiyonları (sadece fare ile erişilir)
            'high_scores',
            'switch_user',
            'settings',
            'guide',
            'credits',

            # Çıkış
            'exit',
        ]
        # Tuş navigasyonu sadece merkez paneller arasında gezinir
        self._nav_panel_max_idx = 8  # Son merkez panel indeksi (block_styles)

    def _ui_scale(self) -> float:
        """Ana menü için pencereye bağlı UI ölçeği üret.

        Referans çözünürlük: 1366x768
        Çok küçük ekranlarda aşırı sıkışmayı, çok büyük ekranlarda da
        kontrolsüz büyümeyi engellemek için clamp uygulanır.
        """
        width, height = self.screen.get_size()
        scale = min(width / 1366.0, height / 768.0)
        return max(0.78, min(1.20, scale))

    def _fullscreen_panel_scale(self) -> float:
        """Modal/popup paneller için fullscreen referanslı ölçek.

        Referans: oyun içi çıkış popup'ı ile aynı ölçek davranışı.
        Borderless fullscreen'de native çözünürlüğü temel alır.
        """
        width, height = self.screen.get_size()
        ref_w, ref_h = width, height

        try:
            if self.settings_manager is not None:
                is_fullscreen = bool(self.settings_manager.get('fullscreen', False))
                is_borderless = bool(self.settings_manager.get('borderless_fullscreen', True))
                if is_fullscreen and is_borderless:
                    native_w, native_h = get_native_resolution()
                    if native_w > 0 and native_h > 0:
                        ref_w, ref_h = native_w, native_h
        except Exception:
            pass

        scale = min(ref_w / 1366.0, ref_h / 768.0)
        return max(0.68, min(1.16, scale))

    def _menu_panel_content_scale(self) -> float:
        """Ana menü kart içerikleri için ekran boyutuna bağlı ölçek.

        Dashboard panel rect'leri runtime layout'ta yüzde bazlı ölçeklendiği için
        içerik (metin/padding/mikro öğeler) de aynı referansla ölçeklenmelidir.
        Aksi halde düşük çözünürlükte içerik fazla büyük kalır ve panel içinde
        sıkışma/taşma hissi oluşur.
        """
        width, height = self.screen.get_size()
        scale = min(width / 1920.0, height / 1080.0)
        return max(0.72, min(1.16, scale))

    def _is_modal_open(self) -> bool:
        """Herhangi bir modal pencere açık mı kontrol et."""
        return self.sos_open or getattr(self, 'show_exit_prompt', False) or getattr(self, 'show_daily_prompt', False)

    # ─── 2D Panel Navigasyonu (Klavye + Gamepad) ────────────────────────────

    def _get_nav_keys(self) -> dict[str, tuple[int, ...]]:
        """Ayarlardaki blok hareket tuşlarını (primary+secondary) menü
        navigasyonu için de kullanılacak şekilde çöz.

        Döner: {'left': (K_LEFT, K_a, ...), 'right': ..., 'up': ..., 'down': ...}
        Ok tuşları her zaman dahildir; ayarlarda atanan özel tuşlar ek olarak eklenir.
        Sonuçlar ~2 saniye cache'lenir.
        """
        now = pygame.time.get_ticks()
        cached = getattr(self, '_nav_keys_cache', None)
        cached_time = getattr(self, '_nav_keys_cache_time', 0)
        if cached is not None and (now - cached_time) < 2000:
            return cached

        base: dict[str, list[int]] = {
            'left':  [pygame.K_LEFT],
            'right': [pygame.K_RIGHT],
            'up':    [pygame.K_UP],
            'down':  [pygame.K_DOWN],
        }
        action_dir = {
            'move_left':  'left',
            'move_right': 'right',
            'soft_drop':  'down',
            'rotate':     'up',
        }
        sm = self.settings_manager
        if sm is not None:
            try:
                controls = sm.get_controls()
                sp = controls.get('single_player', {})
                for action, direction in action_dir.items():
                    binding = sp.get(action, {})
                    for slot in ('primary', 'secondary'):
                        key_name = binding.get(slot) if isinstance(binding, dict) else binding
                        if key_name is None or (isinstance(key_name, str) and not key_name.strip()):
                            continue
                        try:
                            kc = int(key_name) if isinstance(key_name, int) else pygame.key.key_code(key_name)
                        except (ValueError, TypeError):
                            continue
                        if kc not in base[direction]:
                            base[direction].append(kc)
            except Exception:
                pass
        result = {d: tuple(keys) for d, keys in base.items()}
        self._nav_keys_cache = result
        self._nav_keys_cache_time = now
        return result

    def _find_spatial_neighbor(self, direction: str) -> int:
        """Mekânsal navigasyon: mevcut seçili panelden *direction* yönündeki
        en uygun komşuyu bul ve indeksini döndür.

        direction: 'left' | 'right' | 'up' | 'down'

        Algoritma:
        1. Yön eksenindeki aday panelleri filtrele.
        2. Yukarı/aşağı yönde: yatayda örtüşen (overlap) panelleri öncelikli
           seç. Örtüşme yoksa çapraz sapma ağır cezalandırılır.
        3. Sol/sağ yönde: dikey sapma hafif cezalanır.
        4. Aday yoksa mevcut indeks korunur (wrap yok).
        """
        rects = self.option_rects
        if not rects:
            return self.selected

        cur_idx = self.selected
        if cur_idx < 0 or cur_idx >= len(rects):
            return 0

        cur = rects[cur_idx]
        if cur.width <= 0 or cur.height <= 0:
            return cur_idx

        cx, cy = cur.centerx, cur.centery
        best_idx = cur_idx
        best_score = float('inf')

        max_nav = getattr(self, '_nav_panel_max_idx', len(rects) - 1)
        for i, r in enumerate(rects):
            if i == cur_idx:
                continue
            # Sadece merkez paneller arasında gezin
            if i > max_nav:
                continue
            if r.width <= 0 or r.height <= 0:
                continue
            rx, ry = r.centerx, r.centery

            # Yön filtresi
            if direction == 'right' and rx <= cx:
                continue
            if direction == 'left' and rx >= cx:
                continue
            if direction == 'down' and ry <= cy:
                continue
            if direction == 'up' and ry >= cy:
                continue

            if direction in ('left', 'right'):
                # Sol/sağ: dikey sapma hafif cezalı
                main_dist = abs(rx - cx)
                cross_dist = abs(ry - cy)
                score = main_dist + cross_dist * 0.5
            else:
                # Yukarı/aşağı: yatay örtüşme (overlap) kontrolü
                # İki panelin X aralıkları örtüşüyor mu?
                overlap_left = max(cur.left, r.left)
                overlap_right = min(cur.right, r.right)
                has_overlap = overlap_left < overlap_right

                main_dist = abs(ry - cy)
                cross_dist = abs(rx - cx)

                if has_overlap:
                    # Örtüşen paneller: çapraz sapma çok düşük cezalı
                    score = main_dist + cross_dist * 0.1
                else:
                    # Örtüşmeyen paneller: çapraz sapma çok ağır cezalı
                    score = main_dist + cross_dist * 5.0

            if score < best_score:
                best_score = score
                best_idx = i

        return best_idx


    def _load_layout_overrides(self) -> dict[str, Any]:
        if getattr(sys, 'frozen', False):
            if self._layout_override_cache is not None and self._layout_override_mtime == -1:
                return self._layout_override_cache
            rects, coord_space, reference_window, reference_canvas = _decode_layout_payload(EMBEDDED_MENU_LAYOUT)
            self._layout_override_cache = rects
            self._layout_override_mtime = -1
            self._layout_override_coord_space = coord_space
            self._layout_override_reference_window = reference_window
            self._layout_override_reference_canvas = reference_canvas
            return rects

        path = _resolve_menu_layout_runtime_path()
        if path != self._layout_override_path:
            self._layout_override_path = path
            self._layout_override_cache = None
            self._layout_override_mtime = None

        try:
            stat = path.stat()
            mtime = stat.st_mtime
        except Exception:
            self._layout_override_cache = None
            self._layout_override_mtime = None
            self._layout_override_coord_space = 'screen_pct'
            self._layout_override_reference_window = None
            self._layout_override_reference_canvas = None
            return {}

        if self._layout_override_cache is not None and self._layout_override_mtime == mtime:
            return self._layout_override_cache

        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            rects, coord_space, reference_window, reference_canvas = _decode_layout_payload(raw)

            self._layout_override_cache = rects
            self._layout_override_mtime = mtime
            self._layout_override_coord_space = coord_space
            self._layout_override_reference_window = reference_window
            self._layout_override_reference_canvas = reference_canvas
            return rects
        except Exception:
            self._layout_override_cache = {}
            self._layout_override_mtime = mtime
            self._layout_override_coord_space = 'screen_pct'
            self._layout_override_reference_window = None
            self._layout_override_reference_canvas = None
            return {}

    def _apply_layout_override_rect(
        self,
        key: str,
        default_rect: pygame.Rect,
        screen_w: int,
        screen_h: int,
        *,
        min_w: int = 24,
        min_h: int = 24,
    ) -> pygame.Rect:
        rects = self._load_layout_overrides()
        data = rects.get(key)
        if not isinstance(data, dict):
            return default_rect

        try:
            x_pct = float(data.get('x_pct'))
            y_pct = float(data.get('y_pct'))
            w_pct = float(data.get('w_pct'))
            h_pct = float(data.get('h_pct'))
        except Exception:
            return default_rect

        out_w = max(1, int(screen_w))
        out_h = max(1, int(screen_h))

        # Tüm koordinatlar screen_pct: editör 1920×1080 referansıyla yüzde kaydeder,
        # oyun kendi ekran boyutuyla çarpar.
        x = int(out_w * x_pct)
        y = int(out_h * y_pct)
        w = int(out_w * w_pct)
        h = int(out_h * h_pct)

        w = max(min_w, min(out_w, w))
        h = max(min_h, min(out_h, h))
        x = max(0, min(x, out_w - w))
        y = max(0, min(y, out_h - h))
        return pygame.Rect(x, y, w, h)

    def handle_input(self, event):
        """Menü girdilerini işle (klavye + mouse)"""
        if self.menu_language_panel_open:
            was_open = True
            action = self._handle_menu_language_panel_input(event)
            if action is not None:
                return action
            # Panel tıklama ile kapandıysa event'i yut; kör tıklama ile tekrar açılmasın
            if was_open and not self.menu_language_panel_open:
                return None
            if self.menu_language_panel_open:
                return None

        # --- Modal açıkken arka plan girdilerini engelle ---
        if self._is_modal_open():
            # ESC ile SOS panelini kapat
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.sos_open:
                self.sos_open = False
                self.show_exit_prompt = False
                self.show_daily_prompt = False
                return 'main_menu'
            # SOS paneli açıkken sadece panel içi tıklamalara izin ver
            if self.sos_open and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                if self.sos_mail_rect and self.sos_mail_rect.collidepoint(mouse_pos):
                    try:
                        url = _build_gmail_compose_url(
                            CONTACT_EMAIL,
                            subject=t('sos_email_subject'),
                            body=build_support_email_body_template(),
                        )
                        webbrowser.open(url, new=2)
                        self.show_info(t('opening_gmail'), duration=180)
                    except Exception:
                        self.show_info(t('browser_open_failed'), duration=240)
                    self.sos_open = False
                    return None
                if self.sos_instagram_rect and self.sos_instagram_rect.collidepoint(mouse_pos):
                    try:
                        webbrowser.open(INSTAGRAM_URL, new=2)
                        self.show_info(t('opening_instagram'), duration=180)
                    except Exception:
                        self.show_info(t('browser_open_failed'), duration=240)
                    self.sos_open = False
                    return None
                # Dışarı tıklayınca kapat
                if self.sos_panel_rect and not self.sos_panel_rect.collidepoint(mouse_pos):
                    self.sos_open = False
                    return None
            # Modal açıkken diğer tüm girdileri yut
            return None

        # --- Normal (modal kapalı) girdi işleme ---
        max_nav = getattr(self, '_nav_panel_max_idx', len(self.options) - 1)
        if event.type == pygame.KEYDOWN:
            nav = self._get_nav_keys()
            navigated = False
            if event.key in nav['up']:
                new_idx = self._find_spatial_neighbor('up')
                if new_idx != self.selected:
                    self.selected = new_idx
                else:
                    # Fallback: merkez paneller arasında wrap
                    self.selected = (self.selected - 1) % (max_nav + 1)
                navigated = True
                self._ensure_visible()
            elif event.key in nav['down']:
                new_idx = self._find_spatial_neighbor('down')
                if new_idx != self.selected:
                    self.selected = new_idx
                else:
                    self.selected = (self.selected + 1) % (max_nav + 1)
                navigated = True
                self._ensure_visible()
            elif event.key in nav['left']:
                new_idx = self._find_spatial_neighbor('left')
                if new_idx != self.selected:
                    self.selected = new_idx
                    navigated = True
                    self._ensure_visible()
            elif event.key in nav['right']:
                new_idx = self._find_spatial_neighbor('right')
                if new_idx != self.selected:
                    self.selected = new_idx
                    navigated = True
                    self._ensure_visible()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                # Mouse modunda panel dışındayken Enter/Space tetiklemez
                if getattr(self, '_nav_source', 'mouse') == 'mouse' and not getattr(self, '_mouse_in_panel', True):
                    return None
                return self.options[self.selected]
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
            if navigated:
                self._nav_source = 'keyboard'
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        elif event.type == pygame.MOUSEMOTION:
            # Tuş navigasyonu aktifken fare hover seçimi değiştirmez
            if getattr(self, '_nav_source', 'mouse') != 'keyboard':
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                self._mouse_in_panel = False
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        self._mouse_in_panel = True
                        if i != self.selected:
                            self.selected = i
                            self._nav_source = 'mouse'
                        break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._nav_source = 'mouse'  # Tıklama ile fare hover tekrar aktif
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos

            if self.campaign_quick_play_rect and self.campaign_quick_play_rect.collidepoint(mouse_pos):
                return f'campaign_quick_start_{int(self.campaign_quick_level or 1)}'

            # SOS panel/button click handling (main menu only)
            if self.sos_button_rect and self.sos_button_rect.collidepoint(mouse_pos):
                self.sos_open = not self.sos_open
                return None

            # Showcase card click handling (sol taraftaki tanıtım kartları)
            if self.showcase_piece_workshop_rect and self.showcase_piece_workshop_rect.collidepoint(mouse_pos):
                return 'piece_workshop'
            if self.showcase_block_styles_rect and self.showcase_block_styles_rect.collidepoint(mouse_pos):
                return 'block_styles'

            # Corner button click handling (köşe butonları)
            if self.corner_settings_rect and self.corner_settings_rect.collidepoint(mouse_pos):
                return 'settings'
            if self.corner_language_rect and self.corner_language_rect.collidepoint(mouse_pos):
                if self.menu_language_panel_open:
                    self._close_menu_language_panel()
                else:
                    self._open_menu_language_panel()
                return None
            if self.corner_mute_rect and self.corner_mute_rect.collidepoint(mouse_pos):
                return 'toggle_mute_quick'
            if self.corner_switch_user_rect and self.corner_switch_user_rect.collidepoint(mouse_pos):
                return 'switch_user'
            if self.corner_credits_rect and self.corner_credits_rect.collidepoint(mouse_pos):
                return 'credits'
            if self.corner_achievements_rect and self.corner_achievements_rect.collidepoint(mouse_pos):
                return 'high_scores'
            if self.corner_guide_rect and self.corner_guide_rect.collidepoint(mouse_pos):
                return 'guide'

            # Sağ-alt skor paneli sekmeleri
            for tab_key, tab_rect in self._mystery_lb_tab_rects.items():
                if tab_rect and tab_rect.collidepoint(mouse_pos):
                    if self._mystery_lb_tab != tab_key:
                        self._mystery_lb_tab = tab_key
                        self._refresh_mystery_leaderboard_cache(force=True)
                    return None

            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    return self.options[i]
        return None

    def _main_menu_list_metrics(self) -> tuple[int, int, int, int]:
        """Main menü seçenek listesinin ölçülerini tek kaynaktan üret.

        draw() ile scroll clamp/ensure_visible aynı değerleri kullanmalı.
        """
        width, height = self.screen.get_size()
        scale = self._ui_scale()

        hero_margin_x = int(120 * scale)
        hero_top = int(40 * scale)
        hero_h = max(110, int(140 * scale))
        hero_width = min(int(560 * scale), max(320, width - hero_margin_x))
        hero_rect = pygame.Rect((width - hero_width) // 2, hero_top, hero_width, hero_h)
        hero_rect = self._apply_layout_override_rect('hero_panel', hero_rect, width, height, min_w=220, min_h=90)

        list_top = int(hero_rect.bottom + (80 * scale))
        spacing = max(72, int(90 * scale))
        card_height = max(50, int(56 * scale))
        bottom_margin = max(90, int(120 * scale))
        visible_height = max(0, int(height - list_top - bottom_margin))
        return list_top, spacing, card_height, visible_height

    def _ensure_visible(self):
        """Make sure the currently selected item is scrolled into view"""
        list_top, spacing, card_height, visible_height = self._main_menu_list_metrics()
        item_y = list_top + self.selected * spacing - self.scroll_offset
        if item_y < list_top:
            self.scroll_offset -= list_top - item_y
        elif item_y > list_top + visible_height - card_height:
            self.scroll_offset += item_y - (list_top + visible_height - card_height)
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

    def _max_scroll(self):
        _list_top, spacing, _card_height, visible_height = self._main_menu_list_metrics()
        total_height = max(0, len(self.options) * spacing)
        return max(0, total_height - max(visible_height, 0))

    def _draw_main_dashboard_tile(
        self,
        rect: pygame.Rect,
        title: str,
        selected: bool,
        accent_color: tuple[int, int, int],
        subtitle: str = '',
        hover: bool = False,
        panel_key: str = '',
        panel_context: dict[str, Any] | None = None,
    ) -> pygame.Rect:
        """Ana menüdeki büyük kutu/panel kartını çiz."""
        panel_scale = self._menu_panel_content_scale()
        sp = lambda v, minimum=1: max(minimum, int(round(v * panel_scale)))

        is_highlighted = selected or hover
        hover_growth_w = sp(10)
        hover_growth_h = sp(8)
        draw_rect = rect.inflate(hover_growth_w, hover_growth_h) if is_highlighted else rect

        alpha = 230 if is_highlighted else 180
        retro_style.draw_glass_panel(self.screen, draw_rect, alpha=alpha, border_color=accent_color)

        if is_highlighted:
            # Neon glow efekti: altta kalsın (flavor/görselin altında)
            # Panel sınırı dışına taşmaması için draw_rect ile kırpılıyor
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(draw_rect)
            for glow_i in range(3, 0, -1):
                glow_rect = draw_rect.inflate(glow_i * 4, glow_i * 4)
                glow_alpha = max(10, 60 - glow_i * 18)
                glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*accent_color[:3], glow_alpha), glow_surf.get_rect(), width=2, border_radius=14 + glow_i * 2)
                self.screen.blit(glow_surf, glow_rect.topleft)
            self.screen.set_clip(prev_clip)

        # Katman sırası: panel arka planı -> flavor görsel -> panel üst çizimleri
        self._draw_dashboard_tile_flavor(draw_rect, panel_key, accent_color, hover)

        # Her zaman tüm karta (yazı alanı dahil) hafif siyah overlay uygula
        fill = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
        fill.fill((0, 0, 0, 48 if is_highlighted else 38))
        self.screen.blit(fill, draw_rect.topleft)

        pygame.draw.rect(
            self.screen,
            (*accent_color[:3], 255 if is_highlighted else 140),
            draw_rect,
            3 if is_highlighted else 2,
            border_radius=14,
        )

        title_area_h = max(sp(32), int(draw_rect.height * 0.40))
        title_area = pygame.Rect(draw_rect.x + sp(16), draw_rect.y + sp(10), draw_rect.width - sp(24), title_area_h)
        title_font_size = max(sp(16), min(sp(26), int(min(draw_rect.width, draw_rect.height) * 0.12)))
        title_font = retro_style.get_font(title_font_size, bold=True)

        # Eğer başlık tek satıra sığmıyorsa font küçültülerek tek satıra indirilir.
        _min_title_font = max(sp(11), sp(12))
        while title_font_size > _min_title_font:
            if title_font.size(title)[0] <= title_area.width:
                break
            title_font_size -= 1
            title_font = retro_style.get_font(title_font_size, bold=True)

        # Başlık metninin gerçek boyutunu ölç, tam o alana koyu arka plan çiz
        _title_lines = retro_style.wrap_text(title, title_font, title_area.width)
        _line_h = title_font.get_linesize()
        _title_text_h = max(_line_h, len(_title_lines) * _line_h + max(0, len(_title_lines) - 1) * sp(2))
        _tbg_pad_x = sp(8)
        _tbg_pad_y = sp(9)
        _tbg_w = min(draw_rect.width - sp(8), title_area.width + _tbg_pad_x * 2)
        _tbg_h = _title_text_h + _tbg_pad_y * 2
        _tbg = pygame.Surface((_tbg_w, _tbg_h), pygame.SRCALPHA)
        pygame.draw.rect(_tbg, (8, 12, 30, 210), _tbg.get_rect(),
                         border_top_left_radius=14, border_top_right_radius=14,
                         border_bottom_left_radius=8, border_bottom_right_radius=8)
        pygame.draw.rect(_tbg, (*accent_color[:3], 110), _tbg.get_rect(), 1,
                         border_top_left_radius=14, border_top_right_radius=14,
                         border_bottom_left_radius=8, border_bottom_right_radius=8)
        self.screen.blit(_tbg, (draw_rect.x + sp(4), draw_rect.y))

        retro_style.draw_wrapped_text(
            self.screen,
            title,
            title_font,
            UIColors.TEXT_PRIMARY,
            title_area,
            align='left' if draw_rect.width > 170 else 'center',
            line_spacing=2,
        )

        if subtitle:
            # Açıklama metni: küçük panellerde taşmayı önlemek için çok satırlı mini alt-panel
            tutorial_subtitle = panel_key == 'tutorial_mode'
            sub_base_size = sp(19) if tutorial_subtitle else (sp(16) if draw_rect.height < 160 else sp(15))
            sub_min_size = sp(13) if tutorial_subtitle else sp(10)
            sub_pad_x = sp(12)
            sub_pad_y = sp(6)
            sub_max_w = draw_rect.width - sp(36)
            text_w = max(40, sub_max_w - sub_pad_x * 2 - 4)
            max_lines = 1 if tutorial_subtitle else (2 if draw_rect.height < 185 else 1)

            font_size = sub_base_size
            sub_font = retro_style.get_font(font_size, bold=False)
            wrapped_lines = retro_style.wrap_text(subtitle, sub_font, text_w)
            while len(wrapped_lines) > max_lines and font_size > sub_min_size:
                font_size -= 1
                sub_font = retro_style.get_font(font_size, bold=False)
                wrapped_lines = retro_style.wrap_text(subtitle, sub_font, text_w)

            if len(wrapped_lines) > max_lines:
                wrapped_lines = wrapped_lines[:max_lines]
                if not tutorial_subtitle:
                    last_line = wrapped_lines[-1].rstrip()
                    if not last_line.endswith('…'):
                        wrapped_lines[-1] = f"{last_line}…"

            line_h = sub_font.get_linesize()
            line_gap = max(1, sp(2))
            text_h = len(wrapped_lines) * line_h + max(0, len(wrapped_lines) - 1) * line_gap
            max_line_w = max((sub_font.size(line)[0] for line in wrapped_lines), default=0)

            sub_bg_w = min(sub_max_w, max_line_w + sub_pad_x * 2 + 8)
            sub_bg_h = text_h + sub_pad_y * 2
            sub_bg_x = draw_rect.x + sp(18)
            sub_bg_y = draw_rect.bottom - sub_bg_h - sp(8)

            # Alt-panel arka plan
            sub_bg = pygame.Surface((sub_bg_w, sub_bg_h), pygame.SRCALPHA)
            pygame.draw.rect(sub_bg, (15, 22, 42, 170), sub_bg.get_rect(), border_radius=8)
            # Sol accent çizgi
            pygame.draw.rect(sub_bg, (*accent_color[:3], 140), pygame.Rect(0, 3, 3, sub_bg_h - 6), border_radius=2)
            # Kenarlık
            pygame.draw.rect(sub_bg, (*accent_color[:3], 55), sub_bg.get_rect(), 1, border_radius=8)
            self.screen.blit(sub_bg, (sub_bg_x, sub_bg_y))

            subtitle_color = UIColors.TEXT_PRIMARY if tutorial_subtitle else UIColors.TEXT_SECONDARY
            line_y = sub_bg_y + sub_pad_y
            for line in wrapped_lines:
                line_surf = sub_font.render(line, True, subtitle_color)
                self.screen.blit(line_surf, (sub_bg_x + sub_pad_x + sp(4), line_y))
                line_y += line_h + line_gap

        if panel_context and panel_key:
            self._draw_panel_micro_content(draw_rect, panel_key, accent_color, panel_context, hover)

        return draw_rect

    def _draw_dashboard_tile_flavor(
        self,
        rect: pygame.Rect,
        panel_key: str,
        accent_color: tuple[int, int, int],
        hover: bool,
    ) -> None:
        """Panel adına göre arka plan dekoratif efekt (tetris blokları kaldırıldı)."""
        panel_flavor_map = {
            'new_gen_tetris': {
                'path': str(ROOT_DIR / 'assets' / 'main_theme' / 'kart_panel_effect.png'),
                'cache_attr': '_kart_panel_effect_image',
                'fail_attr': '_kart_panel_effect_load_failed',
                'override_key': 'new_gen_tetris_sticker',
            },
            'tutorial_mode': {
                'path': str(ROOT_DIR / 'assets' / 'main_theme' / 'eğitim_panel_effect.png'),
                'cache_attr': '_tutorial_panel_effect_image',
                'fail_attr': '_tutorial_panel_effect_load_failed',
                'override_key': 'tutorial_mode_sticker',
            },
            'piece_workshop': {
                'path': str(ROOT_DIR / 'assets' / 'main_theme' / 'atölye_panel_back_effect.png'),
                'cache_attr': '_piece_workshop_panel_effect_image',
                'fail_attr': '_piece_workshop_panel_effect_load_failed',
                'fit_full': True,
            },
            'block_styles': {
                'path': str(ROOT_DIR / 'assets' / 'main_theme' / 'blok_görünüm.png'),
                'cache_attr': '_block_styles_panel_effect_image',
                'fail_attr': '_block_styles_panel_effect_load_failed',
                'fit_full': True,
            },
        }

        flavor = panel_flavor_map.get(panel_key)
        if flavor is None:
            return

        panel_scale = self._menu_panel_content_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * panel_scale)))

        if bool(flavor.get('fit_full', False)):
            full_img_path = flavor['path']
            full_cache_attr = str(flavor['cache_attr'])
            full_fail_attr = str(flavor['fail_attr'])
            full_cached_image = getattr(self, full_cache_attr, None)
            full_load_failed = getattr(self, full_fail_attr, False)

            if full_cached_image is None and not full_load_failed:
                try:
                    loaded = load_image(full_img_path, convert_alpha=True)
                    if loaded is not None:
                        setattr(self, full_cache_attr, loaded)
                    else:
                        setattr(self, full_fail_attr, True)
                except Exception:
                    setattr(self, full_fail_attr, True)

            full_source = getattr(self, full_cache_attr, None)
            if full_source is not None:
                back_zone = rect.inflate(-s(2), -s(2))
                src_w, src_h = full_source.get_size()
                if src_w > 0 and src_h > 0 and back_zone.width >= s(32) and back_zone.height >= s(32):
                    zoom = 1.06 if hover else 1.0
                    cover_w = max(1, int(back_zone.width * zoom))
                    cover_h = max(1, int(cover_w * (src_h / max(1, src_w))))
                    if cover_h < back_zone.height * zoom:
                        cover_h = max(1, int(back_zone.height * zoom))
                        cover_w = max(1, int(cover_h * (src_w / max(1, src_h))))

                    scaled_back_key = (
                        'fit_full',
                        panel_key,
                        src_w,
                        src_h,
                        cover_w,
                        cover_h,
                        bool(hover),
                    )
                    scaled_back = self._tile_flavor_scaled_cache.get(scaled_back_key)
                    if scaled_back is None:
                        scaled_back = pygame.transform.smoothscale(full_source, (cover_w, cover_h))
                        self._tile_flavor_scaled_cache[scaled_back_key] = scaled_back
                    back_x = back_zone.centerx - cover_w // 2
                    back_y = back_zone.centery - cover_h // 2

                    prev_clip = self.screen.get_clip()
                    self.screen.set_clip(back_zone)
                    self.screen.blit(scaled_back, (back_x, back_y))
                    hover_alpha = 90 if hover else 98
                    flavor_overlay = pygame.Surface(back_zone.size, pygame.SRCALPHA)
                    flavor_overlay.fill((0, 0, 0, hover_alpha))
                    self.screen.blit(flavor_overlay, back_zone.topleft)
                    self.screen.set_clip(prev_clip)
            return

        img_path = flavor['path']
        cache_attr = str(flavor['cache_attr'])
        fail_attr = str(flavor['fail_attr'])
        override_key = str(flavor['override_key'])
        cached_image = getattr(self, cache_attr, None)
        load_failed = getattr(self, fail_attr, False)

        if cached_image is None and not load_failed:
            try:
                loaded = load_image(img_path, convert_alpha=True)
                if loaded is not None:
                    setattr(self, cache_attr, loaded)
                else:
                    setattr(self, fail_attr, True)
                    return
            except Exception:
                setattr(self, fail_attr, True)
                return

        source = getattr(self, cache_attr, None)
        if source is None:
            return

        inner = rect.inflate(-s(16), -s(16))
        sticker_zone = pygame.Rect(
            inner.x + s(8),
            inner.y + int(inner.height * 0.24),
            max(s(40), inner.width - s(12)),
            max(s(48), int(inner.height * 0.58)),
        )

        # Sticker zone runtime layout'tan override edilebilir.
        # Editörde ayarlanan sticker rect'i oyunda da birebir uygulanır.
        screen_w, screen_h = self.screen.get_size()
        sticker_zone = self._apply_layout_override_rect(
            override_key,
            sticker_zone,
            screen_w,
            screen_h,
            min_w=max(40, s(36)),
            min_h=max(40, s(36)),
        )
        if sticker_zone.width < s(32) or sticker_zone.height < s(32):
            return

        src_w, src_h = source.get_size()
        if src_w <= 0 or src_h <= 0:
            return

        # Tam ekran referanslı panel ölçeğine bağlı, panel-içi uniform ölçek.
        # contain-fit: görsel panel boyutuna göre düzgün küçülüp büyür.
        zoom = 1.02 if hover else 1.0
        fit_scale = min(
            sticker_zone.width / max(1, src_w),
            sticker_zone.height / max(1, src_h),
        )
        fit_scale = max(0.01, fit_scale * 0.96 * zoom)
        target_w = max(1, int(src_w * fit_scale))
        target_h = max(1, int(src_h * fit_scale))

        scaled_key = (
            'sticker',
            panel_key,
            src_w,
            src_h,
            target_w,
            target_h,
            bool(hover),
        )
        scaled = self._tile_flavor_scaled_cache.get(scaled_key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(source, (target_w, target_h))
            self._tile_flavor_scaled_cache[scaled_key] = scaled
        draw_x = sticker_zone.centerx - target_w // 2
        draw_y = sticker_zone.centery - target_h // 2

        panel_clip = rect.inflate(-s(2), -s(2))
        effective_clip = sticker_zone.clip(panel_clip)
        if effective_clip.width <= 0 or effective_clip.height <= 0:
            return

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(effective_clip)
        self.screen.blit(scaled, (draw_x, draw_y))
        self.screen.set_clip(prev_clip)

    def show_info(self, message, duration=180):
        """Kısa bilgi mesajı göster"""
        self.info_message = message
        self.info_timer = duration

    def set_daily_hint(self, text, color=None, challenge_title=None):
        """Daily Challenge satırı için bilgi etiketi ayarla"""
        self.daily_hint = text or ''
        if color is not None:
            self.daily_hint_color = color
        if challenge_title is not None:
            self.daily_challenge_title = challenge_title or ''

    def set_user_manager(self, user_manager):
        """Menüde görüntülenen aktif kullanıcı referansını güncelle."""
        self.user_manager = user_manager
        self._hero_avatar_surface = None
        self._hero_avatar_signature = None

    def set_settings_manager(self, settings_manager):
        """Menüde kullanılan ayar yöneticisini güncelle."""
        self.settings_manager = settings_manager

    def _get_campaign_levels(self) -> tuple[int, int]:
        """Campaign için son/sonraki level bilgisini döndür (1-100)."""
        progress = {}
        try:
            settings = getattr(self, 'settings_manager', None)
            if settings is not None:
                progress = settings.get('campaign_progress', {}) or {}
        except Exception:
            progress = {}

        highest = 0
        try:
            highest = int(progress.get('highest_level', 0) or 0)
        except Exception:
            highest = 0

        highest = max(0, min(100, highest))
        last_level = max(1, highest) if highest > 0 else 1
        next_level = min(100, highest + 1) if highest < 100 else 100
        return last_level, next_level

    def _get_recent_achievements_panel_data(self, lang: str | None = None) -> tuple[list[str], int]:
        """Son 3 başarı adı ve toplam tamamlanma yüzdesi."""
        if lang is None:
            try:
                lang = get_language()
            except Exception:
                lang = 'tr'
        total_achievements = max(1, len(ACHIEVEMENTS))
        fallback_percent = 0
        try:
            profile = self.user_manager.get_user_data() if self.user_manager else None
            if isinstance(profile, dict):
                hints = [
                    int(profile.get('total_games', 0) or 0),
                    int(profile.get('total_lines', 0) or 0),
                    int(profile.get('total_tetrises', 0) or 0),
                ]
                fallback_percent = min(100, max(0, sum(1 for v in hints if v > 0) * 5))
        except Exception:
            fallback_percent = 0

        if not self.user_manager:
            return [], fallback_percent

        try:
            ach_path = self.user_manager.get_achievements_file()
            if not ach_path:
                return [], fallback_percent
            path_obj = Path(ach_path)
            if not path_obj.exists():
                return [], fallback_percent

            mtime = path_obj.stat().st_mtime
            cache = self._achievements_panel_cache
            if cache.get('path') == str(path_obj) and cache.get('mtime') == mtime and cache.get('lang') == lang:
                return cache.get('recent', []), int(cache.get('percent', fallback_percent) or fallback_percent)

            raw = json.loads(path_obj.read_text(encoding='utf-8'))
            unlocked = raw.get('unlocked', {}) if isinstance(raw, dict) else {}
            if not isinstance(unlocked, dict):
                unlocked = {}

            def _unlock_sort_key(item: tuple[str, str]):
                date_text = str(item[1] or '')
                try:
                    return datetime.strptime(date_text, '%Y-%m-%d %H:%M').timestamp()
                except Exception:
                    return 0.0

            sorted_items = sorted(unlocked.items(), key=_unlock_sort_key, reverse=True)
            recent_ids = [achievement_id for achievement_id, _ in sorted_items[:3]]
            recent_names = [get_achievement_name(achievement_id) for achievement_id in recent_ids]
            percent = int(round((len(unlocked) / total_achievements) * 100))

            self._achievements_panel_cache = {
                'path': str(path_obj),
                'mtime': mtime,
                'lang': lang,
                'recent': recent_names,
                'percent': max(0, min(100, percent)),
            }
            return recent_names, max(0, min(100, percent))
        except Exception:
            return [], fallback_percent

    def _build_dashboard_panel_context(self, lang: str) -> dict[str, Any]:
        """Ana panel kartları için dinamik UI içerikleri üret."""
        active_user = None
        try:
            active_user = self.user_manager.get_current_user() if self.user_manager else None
        except Exception:
            active_user = None

        status = None
        try:
            status = self.user_manager.get_daily_status() if self.user_manager else None
        except Exception:
            status = None

        fails = int((status or {}).get('fails', 0) or 0)
        remaining_lives = max(0, DAILY_MAX_FAILURES - fails)
        daily_title = (self.daily_challenge_title or '').strip()
        if not daily_title:
            daily_title = t('menu_dashboard_daily_fallback')

        recent_achievements, achievement_percent = self._get_recent_achievements_panel_data(lang)
        last_level, next_level = self._get_campaign_levels()

        # Campaign level name
        campaign_level_name = ''
        try:
            if _campaign_get_level is not None:
                lv = _campaign_get_level(next_level)
                if lv and hasattr(lv, 'name') and isinstance(lv.name, dict):
                    campaign_level_name = lv.name.get(lang, lv.name.get('tr', ''))
        except Exception:
            campaign_level_name = ''

        signature = (
            lang,
            active_user,
            str(daily_title),
            remaining_lives,
            tuple(recent_achievements),
            achievement_percent,
            last_level,
            next_level,
            campaign_level_name,
        )
        if self._panel_context_cache is not None and self._panel_context_cache_sig == signature:
            return self._panel_context_cache

        context = {
            'daily_title': daily_title,
            'daily_lives': remaining_lives,
            'daily_max_lives': DAILY_MAX_FAILURES,
            'recent_achievements': recent_achievements,
            'achievement_percent': achievement_percent,
            'campaign_last_level': last_level,
            'campaign_next_level': next_level,
            'campaign_level_name': campaign_level_name,
        }
        self._panel_context_cache = context
        self._panel_context_cache_sig = signature
        return context

    def _draw_panel_micro_content(
        self,
        rect: pygame.Rect,
        panel_key: str,
        accent_color: tuple[int, int, int],
        panel_context: dict[str, Any],
        hover: bool,
    ) -> None:
        """Panel kartları için kısa açıklama/durum öğeleri çiz."""
        lang = get_language()
        panel_scale = self._menu_panel_content_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * panel_scale)))
        pad_l = s(18)  # Sol padding (strip sonrası)
        pad_r = s(14)  # Sağ padding
        content_w = rect.width - pad_l - pad_r

        if panel_key == 'daily_challenge':
            title_text = str(panel_context.get('daily_title') or '')
            lives = int(panel_context.get('daily_lives', 0) or 0)
            max_lives = int(panel_context.get('daily_max_lives', DAILY_MAX_FAILURES) or DAILY_MAX_FAILURES)

            # --- Mavi kalp PNG ---
            heart_img_size = max(s(22), min(s(32), int((rect.height / 4) * panel_scale)))
            spacing = heart_img_size + s(6)
            total_w = max_lives * spacing - 6
            start_x = rect.right - pad_r - total_w
            heart_top = rect.y + s(14)

            # Kalp PNG yükle ve cache'le
            if not hasattr(self, '_blue_heart_cache') or self._blue_heart_cache is None or self._blue_heart_cache_size != heart_img_size:
                try:
                    raw = load_image(str(ROOT_DIR / 'assets' / 'emoji' / 'blue_heart.png'))
                    if raw:
                        self._blue_heart_cache = pygame.transform.smoothscale(raw, (heart_img_size, heart_img_size))
                    else:
                        self._blue_heart_cache = None
                except Exception:
                    self._blue_heart_cache = None
                self._blue_heart_cache_size = heart_img_size
                # Gri versiyon
                if self._blue_heart_cache:
                    gray = self._blue_heart_cache.copy()
                    gray.set_alpha(60)
                    self._gray_heart_cache = gray
                else:
                    self._gray_heart_cache = None

            for i in range(max_lives):
                hx = start_x + i * spacing
                hy = heart_top
                alive = i < lives
                heart_surf = self._blue_heart_cache if alive else self._gray_heart_cache
                if heart_surf:
                    self.screen.blit(heart_surf, (hx, hy))
                else:
                    # Fallback: basit daire kalp
                    color = (0, 180, 255) if alive else (60, 60, 75)
                    alpha = 230 if alive else 90
                    r = heart_img_size // 3
                    cx_fb = hx + heart_img_size // 2
                    cy_fb = hy + heart_img_size // 2
                    pygame.draw.circle(self.screen, (*color, alpha), (cx_fb - r // 2, cy_fb - 2), r)
                    pygame.draw.circle(self.screen, (*color, alpha), (cx_fb + r // 2, cy_fb - 2), r)
                    tip = [(cx_fb - r, cy_fb + 2), (cx_fb + r, cy_fb + 2), (cx_fb, cy_fb + r + 4)]
                    pygame.draw.polygon(self.screen, (*color, alpha), tip)

            # --- Alt yazı (görev açıklaması) — cam panel kutucuğu içinde ---
            text_y = rect.y + max(s(56), int(rect.height * 0.52))
            text_font = retro_style.get_fitting_font(title_text, base_size=s(18), max_width=content_w - s(16), bold=False, min_size=max(10, s(13)))
            text_surf = text_font.render(title_text, True, UIColors.TEXT_PRIMARY)
            # Panel kutucuğu
            t_pad_x = s(10)
            t_pad_y = s(5)
            t_box_w = min(content_w, text_surf.get_width() + t_pad_x * 2 + s(4))
            t_box_h = text_surf.get_height() + t_pad_y * 2
            t_box_x = rect.x + pad_l
            t_box_y = text_y - t_pad_y
            t_box = pygame.Surface((t_box_w, t_box_h), pygame.SRCALPHA)
            pygame.draw.rect(t_box, (12, 28, 48, 180), t_box.get_rect(), border_radius=9)
            for hy in range(min(6, t_box_h // 4)):
                ha = int(20 * (1 - hy / 6))
                pygame.draw.line(t_box, (255, 255, 255, ha), (4, hy), (t_box_w - 4, hy))
            pygame.draw.rect(t_box, (*accent_color[:3], 80), t_box.get_rect(), 1, border_radius=9)
            self.screen.blit(t_box, (t_box_x, t_box_y))
            self.screen.blit(text_surf, text_surf.get_rect(midleft=(t_box_x + t_pad_x + s(2), text_y + text_surf.get_height() // 2)))

        elif panel_key == 'achievements':
            items = panel_context.get('recent_achievements', [])[:3]
            percent = int(panel_context.get('achievement_percent', 0) or 0)
            gold = UIColors.NEON_GOLD

            # --- Büyük achievement kartları ---
            card_top = rect.y + max(s(50), int(rect.height * 0.26))
            available_h = rect.bottom - card_top - s(40)  # Altta progress bar için yer bırak
            card_h = max(s(26), min(s(36), available_h // 3 - s(4)))
            card_w = max(140, content_w)
            card_x = rect.x + pad_l

            for idx in range(min(3, max(len(items), 1))):
                has_item = idx < len(items)
                label = str(items[idx]) if has_item else t('menu_dashboard_no_achievements')
                cy = card_top + idx * (card_h + s(5))
                card_rect = pygame.Rect(card_x, cy, card_w, card_h)

                # Cam panel arka plan
                card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                bg_alpha = 175 if has_item else 120
                pygame.draw.rect(card_surf, (18, 24, 48, bg_alpha), card_surf.get_rect(), border_radius=8)
                # Üst highlight (cam efekti)
                hl_h = min(8, card_h // 3)
                for hy in range(hl_h):
                    ha = int(18 * (1 - hy / max(1, hl_h)))
                    pygame.draw.line(card_surf, (255, 255, 255, ha), (4, hy), (card_w - 4, hy))
                # Border (altın neon)
                pygame.draw.rect(card_surf, (*gold, 110 if has_item else 45), card_surf.get_rect(), 1, border_radius=8)

                # Yıldız ikonu
                star_cx, star_cy = 18, card_h // 2
                star_size = max(6, min(9, card_h // 3))
                star_color = (*gold, 230) if has_item else (80, 80, 95, 120)
                star_points = []
                for si in range(10):
                    angle = math.pi / 2 + (2 * math.pi * si / 10)
                    sr = star_size if si % 2 == 0 else max(3, star_size // 2)
                    sx = star_cx + sr * math.cos(angle)
                    sy = star_cy - sr * math.sin(angle)
                    star_points.append((sx, sy))
                pygame.draw.polygon(card_surf, star_color, star_points)

                # Başarı adı
                text_color = UIColors.TEXT_PRIMARY if has_item else UIColors.TEXT_MUTED
                name_font = retro_style.get_fitting_font(label, base_size=s(16), max_width=card_w - s(40), bold=has_item, min_size=max(10, s(11)))
                name_surf = name_font.render(label, True, text_color)
                card_surf.blit(name_surf, name_surf.get_rect(midleft=(32, card_h // 2)))

                self.screen.blit(card_surf, card_rect.topleft)

            # --- Tamamlanma çubuğu ---
            bar_w = max(84, content_w)
            bar_h = s(8)
            bar_x = rect.x + pad_l
            bar_y = rect.bottom - s(24)
            pygame.draw.rect(self.screen, (28, 40, 58, 190), pygame.Rect(bar_x, bar_y, bar_w, bar_h), border_radius=5)
            fill_w = int(bar_w * max(0, min(100, percent)) / 100.0)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (*gold, 220), pygame.Rect(bar_x, bar_y, fill_w, bar_h), border_radius=5)
            pct_label = t('menu_dashboard_completion_percent', percent=percent)
            pct_font = retro_style.get_fitting_font(pct_label, base_size=s(14), max_width=bar_w, bold=False, min_size=max(9, s(10)))
            pct_surf = pct_font.render(pct_label, True, UIColors.TEXT_SECONDARY)
            self.screen.blit(pct_surf, pct_surf.get_rect(midleft=(bar_x, bar_y - s(10))))

        elif panel_key == 'campaign_mode':
            last_level = int(panel_context.get('campaign_last_level', 1) or 1)
            next_level = int(panel_context.get('campaign_next_level', 1) or 1)
            level_name = str(panel_context.get('campaign_level_name', '') or '')

            # --- Level bilgi paneli (stilize) ---
            info_y = rect.y + max(s(50), int(rect.height * 0.35))

            if next_level == last_level:
                lv_main = t('menu_dashboard_campaign_level_single', level=next_level)
                lv_sub = ''
            else:
                lv_main = t('menu_dashboard_campaign_levels', last=last_level, next=next_level)
                lv_sub = level_name

            lv_pad_x = s(10)
            lv_pad_y = s(6)
            lv_font = retro_style.get_fitting_font(lv_main, base_size=s(18), max_width=content_w - lv_pad_x * 2, bold=True, min_size=max(11, s(13)))
            lv_surf = lv_font.render(lv_main, True, accent_color)

            # Panel yüksekliği: level adı varsa daha yüksek
            lv_panel_h = lv_surf.get_height() + lv_pad_y * 2
            if lv_sub:
                lv_panel_h += s(18)
            lv_panel_w = max(lv_surf.get_width() + lv_pad_x * 2 + 8, min(content_w, 180))
            lv_panel_x = rect.x + pad_l
            lv_panel_y = info_y

            # Panel arka plan
            lv_bg = pygame.Surface((lv_panel_w, lv_panel_h), pygame.SRCALPHA)
            pygame.draw.rect(lv_bg, (12, 28, 48, 185), lv_bg.get_rect(), border_radius=10)
            # Üst highlight
            for hy in range(min(6, lv_panel_h // 4)):
                ha = int(20 * (1 - hy / 6))
                pygame.draw.line(lv_bg, (255, 255, 255, ha), (6, hy), (lv_panel_w - 6, hy))
            # Kenarlık
            pygame.draw.rect(lv_bg, (*accent_color[:3], 80), lv_bg.get_rect(), 1, border_radius=10)
            self.screen.blit(lv_bg, (lv_panel_x, lv_panel_y))

            # Level metni
            self.screen.blit(lv_surf, lv_surf.get_rect(midleft=(lv_panel_x + lv_pad_x + 4, lv_panel_y + lv_pad_y + lv_surf.get_height() // 2)))

            # --- Level adı (panel içinde) ---
            if lv_sub:
                name_font = retro_style.get_fitting_font(lv_sub, base_size=s(14), max_width=lv_panel_w - s(20), bold=False, min_size=max(10, s(11)))
                name_surf = name_font.render(lv_sub, True, UIColors.TEXT_SECONDARY)
                self.screen.blit(name_surf, name_surf.get_rect(midleft=(lv_panel_x + lv_pad_x + s(4), lv_panel_y + lv_pad_y + lv_surf.get_height() + s(10))))

            # --- Hızlı Devam butonu ---
            btn_w = max(s(115), min(s(160), rect.width - s(26)))
            btn_h = s(32)
            # Sağ-alt yerine panelin orta-alt boş alanına taşı
            btn_x = rect.x + (rect.width - btn_w) // 2
            btn_y = rect.bottom - btn_h - s(52)
            btn_min_y = rect.y + int(rect.height * 0.58)
            btn_max_y = rect.bottom - btn_h - s(40)
            btn_y = max(btn_min_y, min(btn_y, btn_max_y))
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            btn_hover = btn_rect.collidepoint(get_mouse_pos())

            btn_surf = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
            bg_alpha = 225 if btn_hover else 185
            pygame.draw.rect(btn_surf, (15, 25, 40, bg_alpha), btn_surf.get_rect(), border_radius=10)
            # Üst highlight
            for hy in range(min(10, btn_h // 3)):
                ha = int(28 * (1 - hy / 10))
                pygame.draw.line(btn_surf, (255, 255, 255, ha), (4, hy), (btn_w - 4, hy))
            border_alpha = 240 if btn_hover else 175
            pygame.draw.rect(btn_surf, (*accent_color[:3], border_alpha), btn_surf.get_rect(), 2, border_radius=10)
            if btn_hover:
                glow = pygame.Surface((btn_w + 8, btn_h + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*accent_color[:3], 30), glow.get_rect(), border_radius=12)
                self.screen.blit(glow, (btn_rect.x - 4, btn_rect.y - 4))
            btn_label = t('menu_dashboard_quick_continue')
            btn_font = retro_style.get_fitting_font(btn_label, base_size=s(15), max_width=btn_w - s(18), bold=True, min_size=max(10, s(11)))
            btn_text_surf = btn_font.render(btn_label, True, UIColors.TEXT_PRIMARY)
            btn_surf.blit(btn_text_surf, btn_text_surf.get_rect(center=(btn_w // 2, btn_h // 2)))
            # Sol tarafta küçük üçgen ok ikonu
            arrow_x = s(12)
            arrow_cy = btn_h // 2
            arrow_size = s(6)
            arrow_pts = [(arrow_x, arrow_cy - arrow_size), (arrow_x, arrow_cy + arrow_size), (arrow_x + arrow_size + 2, arrow_cy)]
            pygame.draw.polygon(btn_surf, (*accent_color[:3], 220), arrow_pts)

            self.screen.blit(btn_surf, btn_rect.topleft)
            self.campaign_quick_play_rect = btn_rect
            self.campaign_quick_level = next_level

        elif panel_key == 'pvp_2_players':
            # Local PvP butonu kaldırıldı – subtitle yeterli
            pass

    def draw(self):
        """Menüyü retro Atari estetiğiyle çiz."""
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        self.exit_yes_rect = None
        self.exit_no_rect = None
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        # Her frame'de mouse pozisyonunu kontrol et (hover gecikmesini önlemek için)
        # Modal açıkken arka plan hover'larını devre dışı bırak
        # Klavye/gamepad navigasyonu sırasında fare seçimi ezmesin
        if not self._is_modal_open() and getattr(self, '_nav_source', 'mouse') == 'mouse':
            try:
                mouse_pos = get_mouse_pos()
                for i, rect in enumerate(self.option_rects):
                    if rect and rect.width > 0 and rect.collidepoint(mouse_pos):
                        if self.selected != i:
                            self.selected = i
                        break
            except Exception:
                pass

        # Grid efekti kaldırıldı - daha temiz görünüm

        hero_margin_x = int(120 * scale)
        hero_top = int(40 * scale)
        hero_h = max(110, int(140 * scale))
        hero_width = min(int(560 * scale), max(320, width - hero_margin_x))
        hero_rect = pygame.Rect((width - hero_width) // 2, hero_top, hero_width, hero_h)
        hero_rect = self._apply_layout_override_rect('hero_panel', hero_rect, width, height, min_w=220, min_h=90)
        # Header frame: Avatar + QUADRIX aynı panel içinde (menü kartlarından ayrı, daha belirgin çerçeve)
        fill = UIColors.GLASS_BG if len(UIColors.GLASS_BG) == 4 else (*UIColors.BG_MEDIUM, 210)
        hero_header_signature = (hero_rect.size, fill, UIColors.NEON_CYAN)
        header = self._hero_header_cache
        if header is None or self._hero_header_cache_signature != hero_header_signature:
            header = pygame.Surface(hero_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(header, fill, header.get_rect(), border_radius=26)
            # üst highlight
            pygame.draw.rect(header, (255, 255, 255, 18), header.get_rect().inflate(-10, -10), width=1, border_radius=22)
            # neon frame
            pygame.draw.rect(header, (*UIColors.NEON_CYAN, 140), header.get_rect(), width=2, border_radius=26)
            self._hero_header_cache = header
            self._hero_header_cache_signature = hero_header_signature
        self.screen.blit(header, hero_rect.topleft)

        icon_size = max(72, int(92 * scale))
        icon_rect = pygame.Rect(
            hero_rect.x + int(24 * scale),
            hero_rect.y + int(16 * scale),
            icon_size,
            icon_size,
        )
        badge_surface = self._build_active_user_badge(icon_rect.width)
        if badge_surface is None:
            badge_surface = self._get_logo_surface(icon_rect.width)
        self.screen.blit(badge_surface, icon_rect)

        # Aktif kullanıcı adı (avatarın altında)
        active_username = None
        try:
            active_username = self.user_manager.get_current_user() if self.user_manager else None
        except Exception:
            active_username = None
        if active_username:
            name_rect = pygame.Rect(icon_rect.x - 6, icon_rect.bottom + 6, icon_rect.width + 12, 22)
            name_surf = retro_style.render_fit_text(active_username, UIColors.TEXT_SECONDARY, name_rect.width, 18, bold=True)
            shadow = retro_style.render_fit_text(active_username, (0, 0, 0), name_rect.width, 18, bold=True)
            shadow.set_alpha(120)
            self.screen.blit(shadow, shadow.get_rect(center=(name_rect.centerx + 1, name_rect.centery + 1)))
            self.screen.blit(name_surf, name_surf.get_rect(center=name_rect.center))

        # Başlık: ana UI temasıyla uyumlu neon cyan + kontrollü glow
        title_text = 'QUADRIX'
        start_x = icon_rect.right + int(36 * scale)
        text_right = hero_rect.right - int(16 * scale)
        text_width = max(80, text_right - start_x)
        center_y = hero_rect.centery - int(10 * scale)

        title_size = 96
        min_title_size = 64
        title_font = retro_style.get_font(title_size, bold=True)
        title_surf = render_text(title_font, title_text, True, UIColors.NEON_CYAN)
        while title_surf.get_width() > text_width and title_size > min_title_size:
            title_size -= 2
            title_font = retro_style.get_font(title_size, bold=True)
            title_surf = render_text(title_font, title_text, True, UIColors.NEON_CYAN)

        glow = render_text(title_font, title_text, True, UIColors.NEON_CYAN)
        glow.set_alpha(40)
        shadow = render_text(title_font, title_text, True, (0, 0, 0))
        shadow.set_alpha(170)
        outline = render_text(title_font, title_text, True, UIColors.NEON_CYAN)
        outline.set_alpha(160)

        title_x = start_x + (text_width - title_surf.get_width()) // 2
        title_pos = (title_x, center_y - title_surf.get_height() // 2)
        self.screen.blit(shadow, (title_pos[0] + 4, title_pos[1] + 4))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(glow, (title_pos[0] + dx, title_pos[1] + dy))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.screen.blit(outline, (title_pos[0] + dx, title_pos[1] + dy))
        self.screen.blit(title_surf, title_pos)

        # Başlık altı bilgilendirme metni
        subtitle_text = t('menu_header_subtitle')
        subtitle_font = retro_style.get_font(18, bold=False)
        subtitle_surf = retro_style.render_fit_text(
            subtitle_text,
            UIColors.TEXT_SECONDARY,
            max(10, text_width),
            16,
            bold=False,
        )
        subtitle_rect = subtitle_surf.get_rect()
        subtitle_rect.midtop = (start_x + text_width // 2, title_pos[1] + title_surf.get_height() - 6)
        # Panel dışına taşmasın
        if subtitle_rect.right > hero_rect.right - 16:
            subtitle_rect.right = hero_rect.right - 16
        if subtitle_rect.bottom > hero_rect.bottom - 10:
            subtitle_rect.bottom = hero_rect.bottom - 10
        self.screen.blit(subtitle_surf, subtitle_rect)

        # --- SOS button (top-right) ---
        sos_w, sos_h = 110, 44
        sos_margin = 24
        self.sos_button_rect = pygame.Rect(width - sos_margin - sos_w, sos_margin, sos_w, sos_h)
        self.sos_button_rect = self._apply_layout_override_rect('sos_button', self.sos_button_rect, width, height, min_w=80, min_h=34)
        sos_hover = self.sos_button_rect.collidepoint(get_mouse_pos())
        border = UIColors.NEON_RED
        # Make SOS button visually "red" while staying on-theme (glass + neon red frame)
        retro_style.draw_glass_panel(self.screen, self.sos_button_rect, alpha=210 if (sos_hover or self.sos_open) else 170, border_color=border)
        sos_fill_signature = (self.sos_button_rect.size, UIColors.NEON_RED, 26)
        fill_overlay = self._sos_fill_overlay_cache
        if fill_overlay is None or self._sos_fill_overlay_cache_signature != sos_fill_signature:
            fill_overlay = pygame.Surface(self.sos_button_rect.size, pygame.SRCALPHA)
            fill_overlay.fill((*UIColors.NEON_RED, 26))
            self._sos_fill_overlay_cache = fill_overlay
            self._sos_fill_overlay_cache_signature = sos_fill_signature
        self.screen.blit(fill_overlay, self.sos_button_rect.topleft)
        pygame.draw.rect(self.screen, (*border, 160), self.sos_button_rect, 2, border_radius=12)
        sos_label = retro_style.render_fit_text('SOS', UIColors.NEON_RED, sos_w - 16, 24, bold=True)
        self.screen.blit(sos_label, sos_label.get_rect(center=self.sos_button_rect.center))

        # SOS panel rect'lerini başlat (overlay+panel çizimi aşağıda, tüm elemanlardan sonra)
        self.sos_panel_rect = None
        self.sos_mail_rect = None
        self.sos_instagram_rect = None

        # --- Köşe butonları (Ayarlar, Ses, Kullanıcı Değiştir, Emeği Geçenler) ---
        self._draw_corner_buttons()
        self._draw_menu_language_panel()

        # "Neo-retro arcade deneyimi" etiketi kullanıcı isteğiyle kaldırıldı.

        # Dashboard tabanlı yerleşim (taslak iskelete yakın panel düzeni)
        self._update_options()
        lang = get_language()
        content_top = hero_rect.bottom + max(8, int(10 * scale))
        frame_margin_x = max(170, int(188 * scale))
        frame_w = max(620, width - frame_margin_x * 2)
        frame_h = min(int(height * 0.74), height - content_top - max(26, int(32 * scale)))
        frame_h = max(360, frame_h)
        frame_rect = pygame.Rect((width - frame_w) // 2, content_top, frame_w, frame_h)

        grid_x = frame_rect.x
        grid_w = frame_rect.width
        content_h = frame_rect.height

        gap = max(8, int(10 * scale))
        col1 = int(grid_w * 0.28)
        col2 = int(grid_w * 0.17)
        col3 = int(grid_w * 0.17)
        col4 = int(grid_w * 0.12)
        col5 = grid_w - (col1 + col2 + col3 + col4 + gap * 4)
        if col5 < 130:
            col5 = 130
            col3 = max(120, col3 - 20)
            col2 = max(120, col2 - 10)

        x1 = grid_x
        x2 = x1 + col1 + gap
        x3 = x2 + col2 + gap
        x4 = x3 + col3 + gap
        x5 = x4 + col4 + gap

        row1 = int(content_h * 0.43)
        row2 = int(content_h * 0.14)
        row3 = max(84, content_h - row1 - row2 - gap * 2)
        y1 = frame_rect.y
        y2 = y1 + row1 + gap
        y3 = y2 + row2 + gap
        content_bottom = y1 + content_h
        lower_start = y3
        lower_side_inset = max(8, int(10 * scale))
        lower_bottom_lift = max(30, int(38 * scale))
        lower_h = max(84, content_bottom - lower_start - lower_bottom_lift)
        leaderboard_h = max(180, content_bottom - lower_start)
        right_gap = max(8, int(10 * scale))
        tutorial_w = max(96, int(col5 * 0.34))
        achievements_w = max(110, col5 - tutorial_w - right_gap)
        if tutorial_w + right_gap + achievements_w > col5:
            achievements_w = max(96, col5 - tutorial_w - right_gap)

        action_rect_map: dict[str, pygame.Rect] = {
            'new_gen_tetris': pygame.Rect(x1, y1, col1, row1 + row2 + gap),
            'daily_challenge': pygame.Rect(x1 + lower_side_inset, lower_start, max(96, col1 - (lower_side_inset * 2)), lower_h),
            'piece_workshop': pygame.Rect(x2, y1, col2, row1),
            'campaign_mode': pygame.Rect(x2 + lower_side_inset, lower_start, max(96, col2 - (lower_side_inset * 2)), lower_h),
            'extras': pygame.Rect(x3, y1, col3, row1),
            'block_styles': pygame.Rect(x3 + lower_side_inset, lower_start, max(96, col3 - (lower_side_inset * 2)), lower_h),
            'pvp_2_players': pygame.Rect(x4, y1, col4, row1 + row2 + gap),
            'tutorial_mode': pygame.Rect(x5, y1, tutorial_w, row1),
            'achievements': pygame.Rect(x5 + tutorial_w + right_gap, y1, achievements_w, row1),
        }
        for action_key, action_rect in list(action_rect_map.items()):
            action_rect_map[action_key] = self._apply_layout_override_rect(action_key, action_rect, width, height, min_w=90, min_h=70)

        mystery_lb_rect = pygame.Rect(x5, lower_start, col5, leaderboard_h)
        mystery_lb_rect = self._apply_layout_override_rect('steam_scores', mystery_lb_rect, width, height, min_w=180, min_h=140)

        panel_context = self._build_dashboard_panel_context(lang)
        self.campaign_quick_play_rect = None

        action_title_map = {
            'new_gen_tetris': t('new_gen_tetris'),
            'daily_challenge': t('daily_challenge'),
            'piece_workshop': t('piece_workshop'),
            'campaign_mode': t('menu_dashboard_campaign_title'),
            'extras': t('extras'),
            'block_styles': t('block_styles'),
            'pvp_2_players': t('menu_dashboard_pvp_title'),
            'tutorial_mode': t('tutorial_mode'),
            'achievements': t('achievements'),
        }

        action_subtitle_map = {
            'new_gen_tetris': '',
            'daily_challenge': '',
            'piece_workshop': t('menu_dashboard_sub_piece_workshop'),
            'campaign_mode': '',
            'extras': '',
            'block_styles': t('menu_dashboard_sub_block_styles'),
            'pvp_2_players': t('menu_dashboard_sub_pvp'),
            'tutorial_mode': t('menu_dashboard_sub_tutorial'),
            'achievements': '',
        }

        action_color_map = {
            'new_gen_tetris': UIColors.NEON_MAGENTA,
            'daily_challenge': (0, 200, 255),        # Mavi (kalp teması)
            'piece_workshop': UIColors.NEON_MAGENTA,
            'campaign_mode': UIColors.NEON_GREEN,
            'extras': UIColors.NEON_CYAN,
            'block_styles': (180, 120, 255),           # Mor
            'pvp_2_players': UIColors.NEON_ORANGE,
            'tutorial_mode': (0, 210, 210),            # Teal
            'achievements': UIColors.NEON_GOLD,
        }

        mouse_pos = get_mouse_pos()
        panel_hover_inflate_w = max(8, int(10 * scale))
        panel_hover_inflate_h = max(6, int(8 * scale))
        hovered_panel_draws: list[tuple[str, pygame.Rect, bool]] = []
        drawn_panel_rects: dict[str, pygame.Rect] = {}

        for action_key, rect in action_rect_map.items():
            option_index = self.options.index(action_key) if action_key in self.options else -1
            is_selected = option_index == self.selected
            hover_expanded = rect.inflate(panel_hover_inflate_w, panel_hover_inflate_h).collidepoint(mouse_pos)

            # Klavye/gamepad ile seçilen panel de hover efekti göstersin
            if hover_expanded or is_selected:
                hovered_panel_draws.append((action_key, rect, is_selected))
                continue

            draw_rect = self._draw_main_dashboard_tile(
                rect,
                action_title_map.get(action_key, t(action_key)),
                is_selected,
                action_color_map.get(action_key, UIColors.NEON_CYAN),
                subtitle=action_subtitle_map.get(action_key, ''),
                hover=False,
                panel_key=action_key,
                panel_context=panel_context,
            )
            drawn_panel_rects[action_key] = draw_rect

        for action_key, rect, is_selected in hovered_panel_draws:
            accent = action_color_map.get(action_key, UIColors.NEON_CYAN)
            draw_rect = self._draw_main_dashboard_tile(
                rect,
                action_title_map.get(action_key, t(action_key)),
                is_selected,
                accent,
                subtitle=action_subtitle_map.get(action_key, ''),
                hover=True,
                panel_key=action_key,
                panel_context=panel_context,
            )
            drawn_panel_rects[action_key] = draw_rect
            if is_selected:
                pygame.draw.rect(self.screen, (*accent[:3], 220), draw_rect, 2, border_radius=16)

        self._draw_mystery_leaderboard_panel(mystery_lb_rect)

        # Sağ alt çıkış butonu (taslaktaki ayrı kutu)
        exit_w = max(124, int(132 * scale))
        exit_h = max(52, int(58 * scale))
        exit_margin = max(14, int(18 * scale))
        exit_rect = pygame.Rect(width - exit_w - exit_margin, height - exit_h - exit_margin, exit_w, exit_h)
        exit_rect = self._apply_layout_override_rect('exit_button', exit_rect, width, height, min_w=84, min_h=40)
        exit_selected = self.options[self.selected] == 'exit' if self.options else False
        exit_hover = exit_rect.inflate(panel_hover_inflate_w, panel_hover_inflate_h).collidepoint(mouse_pos) or exit_selected
        drawn_exit_rect = self._draw_main_dashboard_tile(
            exit_rect,
            t('exit'),
            exit_selected,
            UIColors.NEON_RED,
            hover=exit_hover,
            panel_key='exit',
        )

        # Sürüm numarası — çıkış butonunun hemen üstünde, sağ alt köşe
        try:
            from version import VERSION as _GAME_VERSION
        except ImportError:
            _GAME_VERSION = ''
        if _GAME_VERSION:
            _ver_font = retro_style.get_font(max(11, int(13 * scale)), bold=False)
            _ver_surf = _ver_font.render(f'v{_GAME_VERSION}', True, (120, 130, 150))
            _ver_x = exit_rect.right - _ver_surf.get_width()
            _ver_y = exit_rect.top - _ver_surf.get_height() - max(3, int(4 * scale))
            self.screen.blit(_ver_surf, (_ver_x, _ver_y))

        # Option hitbox'larını yeni düzene göre yeniden kur
        self.option_rects = []
        for option in self.options:
            if option in action_rect_map:
                self.option_rects.append(drawn_panel_rects.get(option, action_rect_map[option]).inflate(6, 4))
            elif option == 'exit':
                self.option_rects.append(drawn_exit_rect.inflate(6, 4))
            elif option == 'settings' and self.corner_settings_rect:
                self.option_rects.append(self.corner_settings_rect)
            elif option == 'switch_user' and self.corner_switch_user_rect:
                self.option_rects.append(self.corner_switch_user_rect)
            elif option == 'guide' and self.corner_guide_rect:
                self.option_rects.append(self.corner_guide_rect)
            elif option == 'credits' and self.corner_credits_rect:
                self.option_rects.append(self.corner_credits_rect)
            elif option == 'high_scores' and self.corner_achievements_rect:
                self.option_rects.append(self.corner_achievements_rect)
            else:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))

        if self.info_timer > 0 and self.info_message:
            info_font = retro_style.get_font(22, bold=True)
            info_surface = info_font.render(self.info_message, True, retro_style.accent)
            info_rect = info_surface.get_rect(center=(width // 2, height - 90))
            self.screen.blit(info_surface, info_rect)
            self.info_timer -= 1
        elif self.info_timer <= 0:
            self.info_message = ''
        # --- SOS overlay + panel (en üst katman - tüm menü elemanlarının üzerinde) ---
        if self.sos_open:
            dim_overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            dim_overlay.fill((0, 0, 0, 210))
            self.screen.blit(dim_overlay, (0, 0))

            # Tam ekran (1920x1080) referanslı ölçekleme
            fs = self._fullscreen_panel_scale()
            sp = lambda v, minimum=1: max(minimum, int(round(v * fs)))

            panel_w = min(sp(820), max(sp(520), width - sp(100)))
            panel_h = min(sp(520), max(sp(360), height - sp(120)))
            panel_x = (width - panel_w) // 2
            panel_y = (height - panel_h) // 2
            self.sos_panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

            # Glass panel + tek çerçeve
            retro_style.draw_glass_panel(self.screen, self.sos_panel_rect, alpha=220, border_color=UIColors.NEON_CYAN)
            pygame.draw.rect(self.screen, (*UIColors.NEON_CYAN, 130), self.sos_panel_rect, 2, border_radius=sp(14))

            # --- Butonlar (Mail + Instagram) ---
            pad = sp(24)
            btn_h = sp(62)
            btn_y = panel_y + sp(28)
            btn_w = (panel_w - pad * 3) // 2
            btn1 = pygame.Rect(panel_x + pad, btn_y, btn_w, btn_h)
            btn2 = pygame.Rect(panel_x + pad * 2 + btn_w, btn_y, btn_w, btn_h)
            self.sos_mail_rect = btn1
            self.sos_instagram_rect = btn2

            # İkon yükleme (cache'li)
            if not hasattr(self, '_sos_gmail_icon'):
                self._sos_gmail_icon = None
                self._sos_insta_icon = None
                try:
                    _base = ROOT_DIR
                    _mail_path = _base / 'assets' / 'emoji' / 'e-mail-symbol.png'
                    _insta_path = _base / 'assets' / 'emoji' / 'camera.png'
                    if _mail_path.exists():
                        self._sos_gmail_icon = pygame.image.load(str(_mail_path)).convert_alpha()
                    if _insta_path.exists():
                        self._sos_insta_icon = pygame.image.load(str(_insta_path)).convert_alpha()
                except Exception:
                    pass
            _mail_icon = self._sos_gmail_icon
            _insta_icon = self._sos_insta_icon

            for rect, label, color, icon in (
                (btn1, t('sos_mail'), UIColors.NEON_GREEN, _mail_icon),
                (btn2, t('sos_instagram'), UIColors.NEON_MAGENTA, _insta_icon),
            ):
                hover = rect.collidepoint(get_mouse_pos())
                draw_rect = rect.inflate(sp(6), sp(4)) if hover else rect

                # Arka plan
                btn_bg = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
                if hover:
                    pygame.draw.rect(btn_bg, (*color, 35), btn_bg.get_rect(), border_radius=sp(14))
                    highlight_rect = pygame.Rect(4, 2, draw_rect.width - 8, 1)
                    pygame.draw.rect(btn_bg, (*color, 60), highlight_rect)
                else:
                    pygame.draw.rect(btn_bg, (25, 32, 52, 200), btn_bg.get_rect(), border_radius=sp(14))
                self.screen.blit(btn_bg, draw_rect.topleft)

                # Neon glow efekti (hover)
                if hover:
                    glow_surf = pygame.Surface((draw_rect.width + sp(16), draw_rect.height + sp(16)), pygame.SRCALPHA)
                    glow_rect_s = glow_surf.get_rect()
                    pygame.draw.rect(glow_surf, (*color, 25), glow_rect_s, border_radius=sp(18))
                    pygame.draw.rect(glow_surf, (*color, 15), glow_rect_s.inflate(-4, -4), border_radius=sp(16))
                    self.screen.blit(glow_surf, (draw_rect.x - sp(8), draw_rect.y - sp(8)))

                # Glass panel
                retro_style.draw_glass_panel(self.screen, draw_rect, alpha=230 if hover else 170, border_color=color)

                # Çerçeve
                border_width = 3 if hover else 2
                border_alpha = 220 if hover else 120
                pygame.draw.rect(self.screen, (*color, border_alpha), draw_rect, border_width, border_radius=sp(14))

                # İçerik: İkon + Metin
                icon_size = sp(26)
                icon_margin = sp(10)
                text_max_w = draw_rect.width - sp(24)
                if icon is not None:
                    text_max_w = draw_rect.width - icon_size - icon_margin - sp(24)

                txt_color = (255, 255, 255) if hover else UIColors.TEXT_PRIMARY
                txt = retro_style.render_fit_text(label, txt_color, text_max_w, sp(20), bold=True)

                if icon is not None:
                    if not hasattr(self, '_sos_scaled_icons'):
                        self._sos_scaled_icons = {}
                    cache_key = id(icon)
                    if cache_key not in self._sos_scaled_icons or self._sos_scaled_icons[cache_key].get_size() != (icon_size, icon_size):
                        self._sos_scaled_icons[cache_key] = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                    scaled_icon = self._sos_scaled_icons[cache_key]
                    total_w = icon_size + icon_margin + txt.get_width()
                    start_x = draw_rect.centerx - total_w // 2
                    icon_y_pos = draw_rect.centery - icon_size // 2
                    self.screen.blit(scaled_icon, (start_x, icon_y_pos))
                    self.screen.blit(txt, (start_x + icon_size + icon_margin, draw_rect.centery - txt.get_height() // 2))
                else:
                    self.screen.blit(txt, txt.get_rect(center=draw_rect.center))

                # Alt çizgi animasyonu (hover)
                if hover:
                    underline_w = int(draw_rect.width * 0.6)
                    underline_x = draw_rect.centerx - underline_w // 2
                    underline_y_pos = draw_rect.bottom - sp(6)
                    pygame.draw.line(self.screen, (*color, 180), (underline_x, underline_y_pos), (underline_x + underline_w, underline_y_pos), 2)

            # --- Maskot alanı (alt bölüm) ---
            mascot_area_top = btn_y + btn_h + sp(20)
            mascot_area_h = max(sp(80), panel_y + panel_h - mascot_area_top)
            mascot_area_w = panel_w - pad * 2
            mascot_area_rect = pygame.Rect(panel_x + pad, mascot_area_top, mascot_area_w, mascot_area_h)
            self._sos_mascot_rect = mascot_area_rect

            # Maskot görseli varsa çiz, yoksa placeholder göster
            mascot_img = getattr(self, '_sos_mascot_img', None)
            if mascot_img is None and not getattr(self, '_sos_mascot_tried', False):
                self._sos_mascot_tried = True
                try:
                    mascot_candidates = [
                        ROOT_DIR / 'assets' / 'maskot' / 'sos_maskot.png',
                        ROOT_DIR / 'assets' / 'mascot.png',
                    ]
                    for mascot_path in mascot_candidates:
                        if mascot_path.exists():
                            self._sos_mascot_img = pygame.image.load(str(mascot_path)).convert_alpha()
                            mascot_img = self._sos_mascot_img
                            break
                except Exception:
                    self._sos_mascot_img = None

            if mascot_img is not None:
                # Maskotu alan içine sığdır (aspect ratio koru)
                img_w, img_h = mascot_img.get_size()
                if img_w <= 0 or img_h <= 0:
                    mascot_img = None

            if mascot_img is not None:
                base_scale = min(mascot_area_w / img_w, mascot_area_h / img_h)
                manual_zoom = 1.08
                fit_scale = base_scale * manual_zoom
                draw_w = max(1, int(img_w * fit_scale))
                draw_h = max(1, int(img_h * fit_scale))
                cache_key = (draw_w, draw_h)
                if not hasattr(self, '_sos_mascot_scaled') or getattr(self, '_sos_mascot_scaled_key', None) != cache_key:
                    self._sos_mascot_scaled = pygame.transform.smoothscale(mascot_img, (draw_w, draw_h))
                    self._sos_mascot_scaled_key = cache_key
                mascot_draw = self._sos_mascot_scaled
                # İki butonun arasındaki boşluğun yatay ortası
                btn_gap_center_x = btn1.right + (btn2.left - btn1.right) // 2
                mascot_x = btn_gap_center_x - draw_w // 2 + sp(120)
                # Panel altına yasla
                mascot_y = panel_y + panel_h - draw_h
                self.screen.blit(mascot_draw, (mascot_x, mascot_y))

        if self.show_exit_prompt:
            self._draw_exit_prompt_panel()

        if self.show_daily_prompt:
            self._draw_daily_prompt_panel()

        # Gamepad bağlıysa küçük gösterge
        self._draw_gamepad_indicator()

    def notify_menu_activated(self):
        """Ana menüye her dönüşte/girişte çağrılır; leaderboard'u zorla yeniler."""
        # Yükleme devam ediyorsa iptal et, yeni istek başlat
        self._mystery_lb_loading = False
        self._mystery_lb_last_fetch_ms = -120_000
        # Avatar surface cache'ini temizle: yeni yuvarlama/çözünürlük için
        # (bytes cache'i koru - yeniden indirmemek için)
        self._steam_avatar_surf.clear()
        self._refresh_mystery_leaderboard_cache(force=True)

    def _refresh_mystery_leaderboard_cache(self, force: bool = False):
        """Kart Ustalığı için Steam leaderboard cache'ini yenile."""
        if self._mystery_lb_loading:
            return

        now = pygame.time.get_ticks()
        if not force and (now - self._mystery_lb_last_fetch_ms) < self._mystery_lb_refresh_ms:
            return
        self._mystery_lb_last_fetch_ms = now

        service = self._leaderboard_service
        if not service.is_configured():
            self._mystery_lb_entries = {'global': [], 'friends': []}
            self._mystery_lb_error = t('menu_lb_error_config_missing')
            return

        self._mystery_lb_loading = True
        if not self._mystery_lb_entries.get('global') and not self._mystery_lb_entries.get('friends'):
            self._mystery_lb_error = t('menu_lb_loading')

        def _fetch_worker():
            try:
                # Steam SDK varsa, ticket ve steam_id'yi servise ilet
                try:
                    import steam_integration as _si
                    if _si.is_available():
                        if not service.steam_ticket:
                            _ticket = _si.get_auth_session_ticket()
                            if _ticket:
                                service.steam_ticket = _ticket
                        if not service.current_steam_id:
                            service.current_steam_id = _si.get_steam_id_str()
                except Exception:
                    pass

                global_entries = service.fetch_mode_highscores('mystery', limit=10)
                global_error = service.last_error

                friend_entries = service.fetch_mode_friend_highscores('mystery', limit=10)
                friend_error = service.last_error

                self._mystery_lb_entries = {
                    'global': global_entries,
                    'friends': friend_entries,
                }

                active_key = self._mystery_lb_tab
                active_entries = self._mystery_lb_entries.get(active_key, [])
                if active_entries:
                    self._mystery_lb_error = ''
                elif active_key == 'friends':
                    normalized_friend_error = str(friend_error or '').strip().lower()
                    if (
                        (not normalized_friend_error)
                        or ('token' in normalized_friend_error)
                        or ('oturum' in normalized_friend_error)
                        or ('bearer' in normalized_friend_error)
                        or ('friends_auth_required' in normalized_friend_error)
                    ):
                        self._mystery_lb_error = t('menu_lb_error_friends_auth')
                    else:
                        self._mystery_lb_error = friend_error
                else:
                    self._mystery_lb_error = global_error or t('menu_lb_error_global_missing')

                # Tüm girdilerdeki steam_id'leri topla
                all_entries = list(global_entries) + list(friend_entries)
                new_ids = [
                    str(e.get('steam_id', '') or '')
                    for e in all_entries
                    if str(e.get('steam_id', '') or '').strip()
                    and str(e.get('steam_id', '')).strip() not in self._steam_player_cache
                ]
                new_ids = list(dict.fromkeys(new_ids))  # deduplicate
                if new_ids:
                    try:
                        summaries = service.fetch_player_summaries(new_ids)
                        self._steam_player_cache.update(summaries)
                        # Avatar URL'lerini arka planda indir
                        def _download_avatars(to_download: dict):
                            import io
                            for sid, info in to_download.items():
                                url = str(info.get('avatarmedium') or info.get('avatar') or '').strip()
                                if url and url not in self._steam_avatar_bytes:
                                    try:
                                        import requests as _req
                                        resp = _req.get(url, timeout=5)
                                        if resp.status_code == 200:
                                            self._steam_avatar_bytes[url] = resp.content
                                    except Exception:
                                        pass
                        threading.Thread(target=_download_avatars, args=(dict(summaries),), daemon=True).start()
                    except Exception:
                        pass

            except Exception as exc:
                self._mystery_lb_error = t('menu_lb_error_fetch_failed', error=str(exc))
            finally:
                self._mystery_lb_loading = False

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _draw_mystery_leaderboard_panel(self, panel_rect: pygame.Rect | None = None):
        """Ana menü sağ-alt: Kart Ustalığı Steam skor paneli."""
        self._refresh_mystery_leaderboard_cache(force=False)
        panel_scale = self._menu_panel_content_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * panel_scale)))

        if panel_rect is None:
            width, height = self.screen.get_size()
            scale = self._ui_scale()
            panel_w = max(300, min(int(380 * scale), width // 3))
            panel_h = max(360, int(500 * scale))
            panel_x = width - panel_w - max(14, int(24 * scale))
            panel_y = max(int(150 * scale), height - panel_h - max(30, int(52 * scale)))

            # Dar pencerelerde sağ-alt panel, ortadaki ana menü kartlarıyla üst üste binebilir.
            # Bu durumda paneli gizleyerek layout çakışmasını önle.
            menu_card_w = min(int(460 * scale), width - int(120 * scale))
            menu_right = (width // 2) + (menu_card_w // 2)
            min_gap = max(10, int(20 * scale))
            if panel_x < (menu_right + min_gap):
                self._mystery_lb_tab_rects = {}
                return

            panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        else:
            panel_rect = panel_rect.copy()

        if panel_rect.width < 220 or panel_rect.height < 180:
            self._mystery_lb_tab_rects = {}
            return

        # Panel rengi: Lavanta/mor tonu
        score_accent = (140, 120, 255)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=200, border_color=score_accent)
        pygame.draw.rect(self.screen, (*score_accent, 160), panel_rect, 2, border_radius=14)

        title_font = retro_style.get_font(s(22), bold=True)
        subtitle_font = retro_style.get_font(s(14), bold=False)
        title_surf = title_font.render(t('menu_lb_title'), True, UIColors.TEXT_PRIMARY)
        subtitle_surf = subtitle_font.render(t('menu_lb_subtitle'), True, UIColors.TEXT_SECONDARY)
        self.screen.blit(title_surf, (panel_rect.x + s(16), panel_rect.y + s(12)))
        self.screen.blit(subtitle_surf, (panel_rect.x + s(16), panel_rect.y + s(38)))

        tab_y = panel_rect.y + s(62)
        tab_h = s(32)
        tab_gap = s(10)
        tab_w = (panel_rect.width - s(16) * 2 - tab_gap) // 2

        global_rect = pygame.Rect(panel_rect.x + s(16), tab_y, tab_w, tab_h)
        friends_rect = pygame.Rect(global_rect.right + tab_gap, tab_y, tab_w, tab_h)
        self._mystery_lb_tab_rects = {
            'global': global_rect,
            'friends': friends_rect,
        }

        tabs = [
            ('global', t('menu_lb_tab_global'), (100, 180, 255)),
            ('friends', t('menu_lb_tab_friends'), (255, 140, 200)),
        ]
        mouse_pos = get_mouse_pos()
        for tab_key, tab_label, tab_color in tabs:
            rect = self._mystery_lb_tab_rects[tab_key]
            selected = self._mystery_lb_tab == tab_key
            tab_hover = rect.collidepoint(mouse_pos)
            # Tab arka plan
            tab_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            tab_bg_alpha = 200 if selected else (165 if tab_hover else 130)
            pygame.draw.rect(tab_surf, (18, 24, 48, tab_bg_alpha), tab_surf.get_rect(), border_radius=8)
            # Üst highlight
            hl_h = min(6, rect.height // 4)
            for hy_idx in range(hl_h):
                ha = int(22 * (1 - hy_idx / max(1, hl_h)))
                pygame.draw.line(tab_surf, (255, 255, 255, ha), (3, hy_idx), (rect.width - 3, hy_idx))
            # Border
            border_a = 220 if selected else (140 if tab_hover else 90)
            pygame.draw.rect(tab_surf, (*tab_color, border_a), tab_surf.get_rect(), 2, border_radius=8)
            # Metin
            label_color = (255, 255, 255) if selected else UIColors.TEXT_SECONDARY
            tab_font = retro_style.get_fitting_font(tab_label, base_size=s(15), max_width=rect.width - s(12), bold=True, min_size=max(9, s(11)))
            tab_text = tab_font.render(tab_label, True, label_color)
            tab_surf.blit(tab_text, tab_text.get_rect(center=(rect.width // 2, rect.height // 2)))
            self.screen.blit(tab_surf, rect.topleft)

        list_rect = pygame.Rect(panel_rect.x + s(14), tab_y + tab_h + s(10), panel_rect.width - s(28), panel_rect.height - (tab_y + tab_h + s(10) - panel_rect.y) - s(14))
        list_bg = pygame.Surface((list_rect.width, list_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(list_bg, (10, 14, 28, 160), list_bg.get_rect(), border_radius=10)
        pygame.draw.rect(list_bg, (*score_accent, 50), list_bg.get_rect(), 1, border_radius=10)
        self.screen.blit(list_bg, list_rect.topleft)

        active_entries = self._mystery_lb_entries.get(self._mystery_lb_tab, [])
        if not active_entries:
            message = self._mystery_lb_error or t('menu_lb_no_scores')
            msg_font = retro_style.get_fitting_font(message, base_size=s(16), max_width=list_rect.width - s(24), bold=False, min_size=max(9, s(11)))
            msg_surf = msg_font.render(message, True, UIColors.TEXT_MUTED)
            self.screen.blit(msg_surf, msg_surf.get_rect(center=list_rect.center))
            return

        max_rows = min(10, len(active_entries))
        # Satır yüksekliğini mevcut listeye dinamik sığdır (min 26 px)
        row_h = max(s(26), (list_rect.height - s(10)) // max(1, max_rows))
        base_y = list_rect.y + s(5)
        medal_colors = [UIColors.NEON_GOLD, (200, 200, 210), (200, 140, 80)]  # Altın, Gümüş, Bronz
        # Aktif Steam kullanıcısını vurgula
        _current_sid = str(self._leaderboard_service.current_steam_id or '').strip()
        for idx in range(max_rows):
            entry = active_entries[idx]
            row_rect = pygame.Rect(list_rect.x + s(6), base_y + idx * row_h, list_rect.width - s(12), row_h - s(5))
            steam_id = str(entry.get('steam_id', '') or '')
            is_self = bool(_current_sid and steam_id == _current_sid)
            row_surf = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
            if is_self:
                pygame.draw.rect(row_surf, (40, 60, 100, 200), row_surf.get_rect(), border_radius=8)
                pygame.draw.rect(row_surf, (100, 180, 255, 120), row_surf.get_rect(), 2, border_radius=8)
            else:
                pygame.draw.rect(row_surf, (16, 22, 38, 170), row_surf.get_rect(), border_radius=8)
                pygame.draw.rect(row_surf, (*score_accent, 60), row_surf.get_rect(), 1, border_radius=8)
            medal_c = medal_colors[idx] if idx < 3 else UIColors.TEXT_MUTED
            self.screen.blit(row_surf, row_rect.topleft)

            rank = int(entry.get('rank', idx + 1) or (idx + 1))
            score = int(entry.get('score', 0) or 0)

            # Oyuncu adı: cache varsa personaname, yoksa kısa steam_id
            player_info = self._steam_player_cache.get(steam_id, {})
            persona = str(player_info.get('personaname', '') or '').strip()
            if persona:
                user_label = persona
            elif steam_id:
                user_label = steam_id[-10:] if len(steam_id) > 10 else steam_id
            else:
                user_label = t('menu_lb_unknown_user')

            # Avatar surface: bytes varsa main thread'de yükle
            avatar_surf: pygame.Surface | None = None
            avatar_url = str(player_info.get('avatarmedium') or player_info.get('avatar') or '').strip()
            if avatar_url:
                if avatar_url not in self._steam_avatar_surf:
                    raw_bytes = self._steam_avatar_bytes.get(avatar_url)
                    if raw_bytes:
                        try:
                            import io as _io
                            av_size_pre = max(20, min(s(32), row_rect.height - s(8)))
                            loaded = pygame.image.load(_io.BytesIO(raw_bytes))
                            # macOS'ta convert_alpha() SRCALPHA surface'i crash yapabilir;
                            # Steam avatar'ları JPEG olduğundan convert() her zaman yeterli.
                            scaled = pygame.transform.smoothscale(loaded.convert(), (av_size_pre, av_size_pre))
                            self._steam_avatar_surf[avatar_url] = scaled
                        except Exception:
                            self._steam_avatar_surf[avatar_url] = None
                avatar_surf = self._steam_avatar_surf.get(avatar_url)

            rank_color = medal_c if idx < 3 else UIColors.TEXT_SECONDARY
            rank_font = retro_style.get_font(s(16), bold=True)
            score_font = retro_style.get_font(s(16), bold=True)

            rank_surf = rank_font.render(f'#{rank}', True, rank_color)
            score_surf = score_font.render(f"{score:,}".replace(',', '.'), True, (235, 245, 255))

            # Sıra numarası
            rank_x = row_rect.x + s(10)
            rank_y = row_rect.centery - rank_surf.get_height() // 2
            self.screen.blit(rank_surf, (rank_x, rank_y))

            # Avatar
            av_size = max(20, min(s(32), row_rect.height - s(8)))
            av_x = rank_x + rank_surf.get_width() + s(8)
            av_y = row_rect.centery - av_size // 2
            av_rect_draw = pygame.Rect(av_x, av_y, av_size, av_size)
            border_c = medal_c[:3] if idx < 3 else UIColors.TEXT_MUTED[:3]
            border_a = 160 if idx < 3 else 70
            if avatar_surf:
                if _IS_MACOS:
                    # macOS: SRCALPHA/BLEND_RGBA_MIN yerine kare kırpmalı blit + elips border
                    self.screen.blit(avatar_surf, av_rect_draw.topleft)
                else:
                    # Yuvarlak kırpma maskesi (SRCALPHA — masaüstü/Windows/Linux)
                    try:
                        mask_surf = pygame.Surface((av_size, av_size), pygame.SRCALPHA)
                        pygame.draw.ellipse(mask_surf, (255, 255, 255, 255), mask_surf.get_rect())
                        av_rgba = avatar_surf.convert_alpha()
                        av_rgba.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                        self.screen.blit(av_rgba, av_rect_draw.topleft)
                    except Exception:
                        self.screen.blit(avatar_surf, av_rect_draw.topleft)
                # Elips border (her platformda güvenli)
                pygame.draw.ellipse(self.screen, (*border_c, border_a), av_rect_draw, 1)
            else:
                # Placeholder: SRCALPHA intermediate surface — macOS'ta son derece küçük tutarak riski azalt
                ph_surf = pygame.Surface((av_size, av_size), pygame.SRCALPHA) if not _IS_MACOS else None
                if ph_surf:
                    pygame.draw.ellipse(ph_surf, (*border_c, 55), ph_surf.get_rect())
                    pygame.draw.ellipse(ph_surf, (*border_c, 90), ph_surf.get_rect(), 1)
                    # Baş
                    ph_r = max(3, av_size // 6)
                    pygame.draw.circle(ph_surf, (*border_c, 120), (av_size // 2, av_size // 3), ph_r)
                    # Gövde
                    body_r = pygame.Rect(av_size // 2 - ph_r, av_size // 2, ph_r * 2, av_size // 3)
                    pygame.draw.ellipse(ph_surf, (*border_c, 90), body_r)
                    self.screen.blit(ph_surf, av_rect_draw.topleft)
                else:
                    # macOS: sadece elips border çiz
                    pygame.draw.ellipse(self.screen, border_c, av_rect_draw, 1)

            # Oyuncu adı
            name_x = av_x + av_size + s(7)
            score_right = row_rect.right - score_surf.get_width() - s(14)
            max_name_w = max(10, score_right - name_x - s(8))
            name_font = retro_style.get_fitting_font(user_label, base_size=s(14), max_width=max_name_w, bold=False, min_size=max(9, s(10)))
            name_surf = name_font.render(user_label, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(name_surf, (name_x, row_rect.centery - name_surf.get_height() // 2))

            # Skor
            self.screen.blit(score_surf, (score_right, row_rect.centery - score_surf.get_height() // 2))

    def _draw_gamepad_indicator(self):
        """Ekranın sağ alt köşesinde gamepad bağlantı göstergesi çiz"""
        try:
            gpm = get_gamepad_manager()
            if not gpm.is_connected():
                return

            width, height = self.screen.get_size()
            label = gpm.get_gamepad_type_label()
            if not label:
                label = t('menu_gamepad_label')

            font = retro_style.get_font(14, bold=False)
            # PNG emoji ikon + metin
            from emoji_renderer import emoji_surface
            _gp_emoji = emoji_surface('🎮', 18)
            label_surf = font.render(f' {label}', True, (100, 220, 160))
            if _gp_emoji:
                text_surf = pygame.Surface((18 + label_surf.get_width(), max(18, label_surf.get_height())), pygame.SRCALPHA)
                text_surf.blit(_gp_emoji, (0, (text_surf.get_height() - 18) // 2))
                text_surf.blit(label_surf, (18, (text_surf.get_height() - label_surf.get_height()) // 2))
            else:
                text_surf = font.render(f'🎮 {label}', True, (100, 220, 160))
            text_rect = text_surf.get_rect()

            # Arka plan paneli
            padding_x, padding_y = 12, 6
            bg_rect = pygame.Rect(
                width - text_rect.width - padding_x * 2 - 10,
                height - text_rect.height - padding_y * 2 - 10,
                text_rect.width + padding_x * 2,
                text_rect.height + padding_y * 2,
            )

            bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (15, 25, 35, 160), bg_surf.get_rect(), border_radius=8)
            pygame.draw.rect(bg_surf, (100, 220, 160, 80), bg_surf.get_rect(), width=1, border_radius=8)
            self.screen.blit(bg_surf, bg_rect)

            self.screen.blit(text_surf, (bg_rect.x + padding_x, bg_rect.y + padding_y))
        except Exception:
            pass

    def _draw_exit_prompt_panel(self):
        width, height = self.screen.get_size()
        panel_scale = self._fullscreen_panel_scale()

        # Dim overlay (koyu - arka planı tamamen karart)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        self.screen.blit(overlay, (0, 0))

        side_pad_total = max(80, int(100 * panel_scale))
        panel_width = min(int(520 * panel_scale), width - side_pad_total)
        panel_height = min(int(240 * panel_scale), height - max(60, int(80 * panel_scale)))
        panel_width = max(360, panel_width)
        panel_height = max(180, panel_height)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=180, border_color=(*retro_style.accent, 140), glow=True)

        title_font = retro_style.get_font(max(20, int(30 * panel_scale)), bold=True)
        title_surf = title_font.render(t('exit_confirm_title'), True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + max(12, int(18 * panel_scale))))

        body_font = retro_style.get_font(max(14, int(18 * panel_scale)), bold=False)
        body_color = (210, 225, 245)
        pad_x = max(18, int(26 * panel_scale))
        body_top = panel_rect.y + max(46, int(64 * panel_scale))
        body_h = max(50, int(70 * panel_scale))
        body_rect = pygame.Rect(panel_rect.x + pad_x, body_top, panel_rect.width - (pad_x * 2), body_h)
        retro_style.draw_wrapped_text(
            self.screen,
            t('exit_confirm_message'),
            body_font,
            body_color,
            body_rect,
            align='center',
            line_spacing=max(3, int(6 * panel_scale)),
        )

        spacing = max(10, int(16 * panel_scale))
        button_width = min(int(200 * panel_scale), (panel_rect.width - pad_x * 2 - spacing) // 2)
        button_height = max(38, int(54 * panel_scale))
        total_width = button_width * 2 + spacing
        start_x = panel_rect.centerx - total_width // 2
        button_y = panel_rect.bottom - button_height - max(24, int(48 * panel_scale))

        yes_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        no_rect = pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height)

        mouse_pos = get_mouse_pos()

        for rect, label, sub_label, btn_color in (
            (yes_rect, t('menu_yes_exit'), t('menu_hint_enter_y'), retro_style.success),
            (no_rect, t('cancel'), t('menu_hint_esc_n'), retro_style.secondary),
        ):
            hover = rect.collidepoint(mouse_pos)
            # Hover'da buton hafifçe büyüsün
            draw_rect = rect.inflate(6, 4) if hover else rect

            # Arka plan: hover'da renkli dolgu
            btn_bg = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            if hover:
                pygame.draw.rect(btn_bg, (*btn_color, 35), btn_bg.get_rect(), border_radius=12)
                # Üst parlama çizgisi
                highlight_rect = pygame.Rect(4, 2, draw_rect.width - 8, 1)
                pygame.draw.rect(btn_bg, (*btn_color, 60), highlight_rect)
            else:
                pygame.draw.rect(btn_bg, (20, 26, 42, 200), btn_bg.get_rect(), border_radius=12)
            self.screen.blit(btn_bg, draw_rect.topleft)

            # Neon glow efekti (hover)
            if hover:
                glow_surf = pygame.Surface((draw_rect.width + 12, draw_rect.height + 12), pygame.SRCALPHA)
                glow_rect = glow_surf.get_rect()
                pygame.draw.rect(glow_surf, (*btn_color, 25), glow_rect, border_radius=16)
                pygame.draw.rect(glow_surf, (*btn_color, 15), glow_rect.inflate(-4, -4), border_radius=14)
                self.screen.blit(glow_surf, (draw_rect.x - 6, draw_rect.y - 6))

            # Çerçeve
            border_width = 3 if hover else 1
            border_alpha = 220 if hover else 100
            pygame.draw.rect(self.screen, (*btn_color, border_alpha), draw_rect, border_width, border_radius=12)

            # Metin
            txt_color = (255, 255, 255) if hover else (220, 230, 245)
            title_font_btn = retro_style.get_fitting_font(label, max(14, int(20 * panel_scale)), draw_rect.width - 40, bold=True)
            title_surf_btn = title_font_btn.render(label, True, txt_color)
            sub_font = retro_style.get_font(max(10, int(13 * panel_scale)), bold=False)
            sub_surf = sub_font.render(sub_label, True, (140, 155, 180) if not hover else (*btn_color, 200))

            gap = 3
            total_h = title_surf_btn.get_height() + gap + sub_surf.get_height()
            text_x = draw_rect.x + 14
            text_start_y = draw_rect.centery - total_h // 2
            self.screen.blit(title_surf_btn, (text_x, text_start_y))
            self.screen.blit(sub_surf, (text_x, text_start_y + title_surf_btn.get_height() + gap))

        self.exit_yes_rect = yes_rect
        self.exit_no_rect = no_rect

        hint_font = retro_style.get_font(max(12, int(16 * panel_scale)), bold=False)
        hint = hint_font.render(t('menu_hint_select'), True, (150, 165, 190))
        self.screen.blit(hint, hint.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - max(10, int(14 * panel_scale))))

    def _draw_daily_prompt_panel(self):
        width, height = self.screen.get_size()
        panel_scale = self._fullscreen_panel_scale()

        # Dim overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        side_margin = max(40, int(50 * panel_scale))
        panel_width = min(int(600 * panel_scale), width - side_margin * 2)
        panel_height = min(int(320 * panel_scale), height - max(90, int(120 * panel_scale)))
        panel_width = max(420, panel_width)
        panel_height = max(220, panel_height)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=180, border_color=(*retro_style.accent, 140), glow=True)

        title_text = t('daily_prompt_title')
        title_font = retro_style.get_font(max(18, int(28 * panel_scale)), bold=True)
        title_surf = title_font.render(title_text, True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + max(10, int(16 * panel_scale))))

        challenge = self.daily_prompt_challenge or {}
        name = str(challenge.get('name') or '').strip()
        briefing = str(challenge.get('briefing') or '').strip()
        desc = str(challenge.get('description') or '').strip()
        objective_line = str(challenge.get('objective_line') or '').strip()
        rule_line = str(challenge.get('rule_line') or '').strip()
        reward_line = str(challenge.get('reward_line') or '').strip()
        effects = challenge.get('effects') or []

        def _strip_prefix(text: str) -> str:
            txt = str(text or '').strip()
            for prefix in ('Hedef: ', 'Objective: ', 'Kural: ', 'Rule: ', 'Başarısızlık: ', 'Failure: ', 'Ödül: ', 'Reward: '):
                if txt.startswith(prefix):
                    return txt[len(prefix):].strip()
            return txt

        def _shorten(text: str, limit: int = 64) -> str:
            txt = str(text or '').strip()
            if len(txt) <= limit:
                return txt
            return txt[: max(1, limit - 1)].rstrip() + '…'

        body_font = retro_style.get_font(max(13, int(18 * panel_scale)), bold=False)
        body_color = (210, 225, 245)
        pad_x = max(16, int(26 * panel_scale))
        body_top = panel_rect.y + max(42, int(62 * panel_scale))
        body_h = max(90, int(150 * panel_scale))
        body_rect = pygame.Rect(panel_rect.x + pad_x, body_top, panel_rect.width - (pad_x * 2), body_h)

        # Paneli sade tut: en fazla 5 satır, sadece kritik bilgiler
        lines = []
        if name:
            lines.append(_shorten(name, 46))

        compact_objective = _strip_prefix(objective_line)
        if compact_objective:
            lines.append(_shorten(f"Hedef: {compact_objective}", 64))

        compact_rule = _strip_prefix(rule_line)
        if compact_rule and 'Standart günlük meydan okuma' not in compact_rule:
            lines.append(_shorten(f"Kural: {compact_rule}", 64))

        compact_reward = _strip_prefix(reward_line)
        if compact_reward:
            lines.append(_shorten(f"Ödül: {compact_reward}", 64))

        if effects:
            # Görsel kalabalığı önlemek için sadece tek etki satırı
            lines.append(_shorten(f"• {str(effects[0])}", 58))

        if len(lines) < 2:
            fallback = briefing or desc
            if fallback:
                lines.append(_shorten(fallback, 64))

        lines = lines[:5]

        text = '\n'.join(lines) if lines else t('daily_prompt_missing')
        retro_style.draw_wrapped_text(
            self.screen,
            text,
            body_font,
            body_color,
            body_rect,
            align='center',
            line_spacing=max(3, int(6 * panel_scale)),
        )

        spacing = max(10, int(16 * panel_scale))
        button_width = min(int(220 * panel_scale), (panel_rect.width - pad_x * 2 - spacing) // 2)
        button_height = max(38, int(54 * panel_scale))
        total_width = button_width * 2 + spacing
        start_x = panel_rect.centerx - total_width // 2
        button_y = panel_rect.bottom - button_height - max(24, int(48 * panel_scale))

        play_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        cancel_rect = pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height)

        play_label = t('play')
        cancel_label = t('menu_back')
        play_hint = 'ENTER'
        cancel_hint = 'ESC'

        retro_style.draw_uniform_button(
            self.screen,
            play_rect,
            play_label,
            sub_text=play_hint,
            color_code=retro_style.success,
            selected=self.daily_prompt_selected == 0,
        )
        retro_style.draw_uniform_button(
            self.screen,
            cancel_rect,
            cancel_label,
            sub_text=cancel_hint,
            color_code=retro_style.secondary,
            selected=self.daily_prompt_selected == 1,
        )

        self.daily_play_rect = play_rect
        self.daily_cancel_rect = cancel_rect

        hint_font = retro_style.get_font(max(11, int(16 * panel_scale)), bold=False)
        hint = hint_font.render(t('menu_hint_select'), True, (150, 165, 190))
        self.screen.blit(hint, hint.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - max(10, int(14 * panel_scale))))

    def _draw_prompt_button(self, rect, label, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=18)
        pygame.draw.rect(self.screen, (255, 255, 255, 60), rect, 2, border_radius=18)
        text = retro_style.render_fit_text(label, WHITE, rect.width - 24, 24, bold=False)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _get_logo_surface(self, size):
        size = max(64, size)
        if not self._logo_surface or self._logo_size != size:
            self._logo_surface = self._build_logo_surface(size)
            self._logo_size = size
        return self._logo_surface

    def _build_logo_surface(self, size):
        image = self._load_logo_image()
        if image is not None:
            return self._compose_logo_surface(image, size)
        return self._build_vector_logo_surface(size)

    def _load_logo_image(self):
        if self._logo_image_original is not None or self._logo_image_failed:
            return self._logo_image_original
        for candidate in LOGO_PATH_CANDIDATES:
            if candidate.exists():
                try:
                    self._logo_image_original = load_image(str(candidate), convert_alpha=True)
                    print(f"[LOGO] Menü logosu yüklendi: {candidate}")
                    return self._logo_image_original
                except Exception as exc:  # pragma: no cover - diagnostics only
                    print(f"[LOGO] Menü logosu yüklenemedi ({candidate}): {exc}")
        self._logo_image_failed = True
        return None

    def _compose_logo_surface(self, image, size):
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        inset = 8
        scale_target = size - inset * 2
        width, height = image.get_size()
        if width == 0 or height == 0:
            return self._build_vector_logo_surface(size)
        scale_ratio = min(scale_target / width, scale_target / height)
        scaled_size = (
            max(1, int(width * scale_ratio)),
            max(1, int(height * scale_ratio)),
        )
        logo = pygame.transform.smoothscale(image, scaled_size)

        # Soft drop shadow to integrate with hero card
        shadow = pygame.Surface((scaled_size[0] + 12, scaled_size[1] + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), shadow.get_rect(), border_radius=24)
        surface.blit(shadow, shadow.get_rect(center=(size // 2 + 2, size // 2 + 4)))
        surface.blit(logo, logo.get_rect(center=(size // 2, size // 2)))

        # Neon bezel to match previous aesthetic
        center = size // 2
        radius = center - 2
        pygame.draw.circle(surface, (8, 12, 28), (center, center), radius, 3)
        pygame.draw.circle(surface, (255, 216, 120), (center, center), radius - 4, 2)
        pygame.draw.circle(surface, (60, 180, 255), (center, center), radius - 10, 1)
        return surface

    def _build_vector_logo_surface(self, size):
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        radius = center - 4

        pygame.draw.circle(surface, (8, 10, 26), (center, center), radius)
        pygame.draw.circle(surface, (4, 6, 18), (center, center), radius - 6)

        ring_color = (255, 240, 120)
        pygame.draw.circle(surface, ring_color, (center, center), radius - 2, 6)
        pygame.draw.circle(surface, ring_color, (center, center), radius - 16, 3)

        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        for thickness, alpha in ((10, 70), (6, 120), (3, 200)):
            pygame.draw.circle(glow, (255, 240, 140, alpha), (center, center), radius - 3, thickness)
        surface.blit(glow, (0, 0))

        layout = [
            ('I', (0, 255, 221), -90),
            ('T', (190, 120, 255), -35),
            ('O', (255, 214, 0), 5),
            ('S', (0, 220, 140), 55),
            ('Z', (255, 90, 140), 105),
            ('L', (255, 150, 50), 160),
            ('L', (255, 150, 50), 200),
            ('J', (0, 160, 255), 225),
        ]
        font = retro_style.get_font(max(20, size // 5))
        letter_radius = radius - 18
        for char, color, angle in layout:
            rad = math.radians(angle)
            pos = (
                center + int(math.cos(rad) * letter_radius),
                center + int(math.sin(rad) * letter_radius),
            )
            text = font.render(char, True, color)
            text_rect = text.get_rect(center=pos)
            shadow = font.render(char, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(pos[0] + 2, pos[1] + 2))
            surface.blit(shadow, shadow_rect)
            surface.blit(text, text_rect)

        return surface

    def _build_active_user_badge(self, size):
        if not self.user_manager:
            self._hero_avatar_surface = None
            self._hero_avatar_signature = None
            return None
        user_data = self.user_manager.get_user_data()
        if not user_data:
            self._hero_avatar_surface = None
            self._hero_avatar_signature = None
            return None
        avatar_value = user_data.get('avatar', None)
        accent_color = self._normalize_color(user_data.get('avatar_color', retro_style.primary))
        signature = (avatar_value, accent_color, size)
        if self._hero_avatar_signature == signature and self._hero_avatar_surface is not None:
            return self._hero_avatar_surface
        surface = self._draw_avatar_badge_surface(avatar_value, accent_color, size)
        self._hero_avatar_signature = signature
        self._hero_avatar_surface = surface
        return surface

    def _normalize_color(self, color):
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            try:
                return tuple(int(max(0, min(255, c))) for c in color[:3])
            except (TypeError, ValueError):
                pass
        return retro_style.primary

    def _draw_avatar_badge_surface(self, avatar_value, accent_color, size):
        size = max(64, size)
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        radius = center - 4

        # 1. Önce dolu arka plan dairesi — accent_color ile
        bg_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(bg_surf, (*accent_color, 240), (center, center), radius)
        surface.blit(bg_surf, (0, 0))

        # 2. Hafif parlama (içe doğru beyaz kenar)
        pygame.draw.circle(surface, (255, 255, 255, 22), (center, center), radius)

        # 3. Avatar bitmap
        avatar_size = max(32, size - 24)
        avatar_bitmap = self._resolve_avatar_bitmap(avatar_value, avatar_size)
        if avatar_bitmap:
            masked = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            mask = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            cut_r = max(2, avatar_size // 2 - 2)
            pygame.draw.circle(mask, (255, 255, 255, 255), (avatar_size // 2, avatar_size // 2), cut_r)
            masked.blit(avatar_bitmap, (0, 0))
            masked.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(masked, masked.get_rect(center=(center, center)))

        # 4. Dış rim: accent rengi + neon
        rim_color = accent_color if accent_color else UIColors.NEON_CYAN
        pygame.draw.circle(surface, (*rim_color, 230), (center, center), radius, width=3)
        pygame.draw.circle(surface, (*UIColors.NEON_CYAN, 120), (center, center), radius + 1, width=2)

        return surface

    def _resolve_avatar_bitmap(self, avatar_value, target_size):
        candidate_paths = []
        resolved = resolve_avatar_value(avatar_value) if avatar_value else None
        if resolved and self._looks_like_image_path(resolved):
            candidate_paths.append(resolved)
        if avatar_value and self._looks_like_image_path(avatar_value):
            candidate_paths.append(avatar_value)
        for path in candidate_paths:
            if path and os.path.exists(path):
                try:
                    image = load_image(path, convert_alpha=True)
                    # En-boy oranını koruyarak ortadan kes (center-crop)
                    src_w, src_h = image.get_size()
                    scale = target_size / min(src_w, src_h) if min(src_w, src_h) > 0 else 1.0
                    scaled_w = max(target_size, int(src_w * scale))
                    scaled_h = max(target_size, int(src_h * scale))
                    img = pygame.transform.smoothscale(image, (scaled_w, scaled_h))
                    crop_x = (scaled_w - target_size) // 2
                    crop_y = (scaled_h - target_size) // 2
                    cropped = pygame.Surface((target_size, target_size), pygame.SRCALPHA)
                    cropped.blit(img, (0, 0), area=pygame.Rect(crop_x, crop_y, target_size, target_size))
                    return cropped
                except Exception:
                    continue
        # Emoji avatar'lar bazı sistem fontlarında kare/kutucuk olarak görünebildiği için
        # güvenli bir vektör (shape) fallback kullan.
        return self._render_default_avatar_surface(target_size)

    def _render_default_avatar_surface(self, target_size):
        size = max(24, int(target_size))
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size // 2
        cy = size // 2

        # Head
        head_r = max(4, size // 5)
        head_y = cy - head_r
        pygame.draw.circle(surface, (235, 240, 255, 230), (cx, head_y), head_r)
        pygame.draw.circle(surface, (0, 0, 0, 60), (cx, head_y + 2), head_r, width=2)

        # Shoulders / body
        body_w = max(10, int(size * 0.62))
        body_h = max(8, int(size * 0.38))
        body_x = cx - body_w // 2
        body_y = cy + head_r // 2
        body_rect = pygame.Rect(body_x, body_y, body_w, body_h)
        pygame.draw.rect(surface, (235, 240, 255, 190), body_rect, border_radius=max(6, size // 6))
        pygame.draw.rect(surface, (0, 0, 0, 45), body_rect, width=2, border_radius=max(6, size // 6))
        return surface

    def _looks_like_image_path(self, value):
        if not isinstance(value, str):
            return False
        lower = value.lower()
        return any(lower.endswith(ext) for ext in AVATAR_IMAGE_EXTENSIONS)

    def _render_emoji_surface(self, emoji, target_size):
        # Önce Apple emoji PNG dene
        from emoji_renderer import emoji_surface
        surf = emoji_surface(emoji, target_size)
        if surf:
            return surf
        # PNG yoksa font render fallback
        font = self._get_emoji_font(target_size * 2)
        glyph = font.render(emoji, True, WHITE)
        glyph = pygame.transform.smoothscale(glyph, (target_size, target_size))
        surface = pygame.Surface((target_size, target_size), pygame.SRCALPHA)
        surface.blit(glyph, glyph.get_rect(center=(target_size // 2, target_size // 2)))
        return surface

    def _get_emoji_font(self, size):
        size = max(32, int(size))
        font = self._emoji_font_cache.get(size)
        if not font:
            font = UIFonts.get(size)
            self._emoji_font_cache[size] = font
        return font

    # ------------------------------------------------------------------
    # Corner Button System (Köşe Butonları)
    # ------------------------------------------------------------------

    def _load_emoji_icon(self, name: str, size: int) -> pygame.Surface | None:
        """assets/emoji/ klasöründen PNG ikonu yükle ve cache'le."""
        key = (name, size)
        cached = self._emoji_icon_cache.get(key)
        if cached is not None:
            return cached if cached is not False else None

        try:
            base = ROOT_DIR
            path = base / 'assets' / 'emoji' / f'{name}.png'
            if path.exists():
                img = pygame.image.load(str(path)).convert_alpha()
                img = pygame.transform.smoothscale(img, (size, size))
                self._emoji_icon_cache[key] = img
                return img
        except Exception:
            pass
        self._emoji_icon_cache[key] = False
        return None

    def _draw_showcase_cards(self):
        """Ana menünün sol tarafına Parça Atölyesi ve Blok Görünümleri showcase kartları çiz.

        Kartlar glassmorphism temasına uyumlu, mini tetris parça önizlemeleri içerir.
        Yeterli yatay alan yoksa (dar ekranlar) kartlar gizlenir.
        """
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        self._showcase_anim_tick += 1

        # Menü listesi ortalanmış durumda. Sol taraftaki boşluğa kartları yerleştir.
        card_width_main = min(int(460 * scale), width - int(120 * scale))
        menu_left_edge = (width - card_width_main) // 2

        # Kartlar için yeterli alan kontrolü (en az 200px boşluk sol tarafta)
        available_left = menu_left_edge - int(30 * scale)
        if available_left < max(150, int(180 * scale)):
            self.showcase_piece_workshop_rect = None
            self.showcase_block_styles_rect = None
            return

        card_w = min(int(190 * scale), available_left - max(10, int(20 * scale)))
        card_h = max(150, int(210 * scale))
        card_x = max(10, int(20 * scale))
        gap = max(10, int(18 * scale))

        # Hero rect'in altından başla
        hero_top = int(40 * scale)
        hero_h = max(110, int(140 * scale))
        hero_rect_bottom = hero_top + hero_h
        card_top = hero_rect_bottom + int(80 * scale)

        # Dikey alan kontrolü
        needed_height = card_h * 2 + gap + int(80 * scale)
        if card_top + needed_height > height:
            # Kartları küçült veya gizle
            card_h = max(150, (height - card_top - gap - int(80 * scale)) // 2)
            if card_h < 150:
                self.showcase_piece_workshop_rect = None
                self.showcase_block_styles_rect = None
                return

        mouse_pos = get_mouse_pos()

        # ── KART 1: Parça Atölyesi (üstte) ──
        rect1 = pygame.Rect(card_x, card_top, card_w, card_h)
        self.showcase_piece_workshop_rect = rect1
        hover1 = rect1.collidepoint(mouse_pos)
        self._draw_showcase_card(
            rect1,
            title=t('piece_workshop') or 'Parça Atölyesi',
            subtitle=t('piece_workshop_showcase_desc') or 'Kendi parçalarını tasarla!',
            accent_color=UIColors.NEON_MAGENTA,
            hover=hover1,
            card_type='workshop',
        )

        # ── KART 2: Blok Görünümleri (altta) ──
        rect2 = pygame.Rect(card_x, rect1.bottom + gap, card_w, card_h)
        self.showcase_block_styles_rect = rect2
        hover2 = rect2.collidepoint(mouse_pos)
        self._draw_showcase_card(
            rect2,
            title=t('block_styles') or 'Blok Görünümleri',
            subtitle=t('block_styles_showcase_desc') or 'Renkleri özelleştir!',
            accent_color=UIColors.NEON_GREEN,
            hover=hover2,
            card_type='styles',
        )

    def _draw_showcase_card(
        self,
        rect: pygame.Rect,
        title: str,
        subtitle: str,
        accent_color: tuple,
        hover: bool = False,
        card_type: str = 'workshop',
    ) -> pygame.Rect:
        """Tek bir showcase kartı çiz: glass panel + mini parça previews + metin."""
        # Kart içi ölçek: 190x210 referansına göre
        card_scale = min(rect.width / 190.0, rect.height / 210.0)
        panel_scale = self._menu_panel_content_scale()
        card_scale = max(0.78, min(1.30, card_scale * panel_scale))

        # Glass arka plan
        alpha = 210 if hover else 160
        retro_style.draw_glass_panel(self.screen, rect, alpha=alpha, border_color=accent_color)

        # Hover efekti: hafif renkli dolgu
        if hover:
            fill = pygame.Surface(rect.size, pygame.SRCALPHA)
            fill.fill((*accent_color[:3], 25))
            self.screen.blit(fill, rect.topleft)

        # Neon çerçeve
        border_alpha = 200 if hover else 120
        pygame.draw.rect(self.screen, (*accent_color[:3], border_alpha), rect, 2, border_radius=14)

        pad = max(10, int(14 * card_scale))
        inner_x = rect.x + pad + max(4, int(6 * card_scale))
        inner_w = rect.width - (pad * 2) - max(4, int(6 * card_scale))

        # ── Mini tetris parça önizlemeleri (kartın üst yarısı) ──
        preview_area_top = rect.y + pad
        text_area_h = max(62, int(78 * card_scale))
        preview_area_h = max(64, rect.height - text_area_h - pad)
        cell_size = max(7, min(int(14 * card_scale), inner_w // 12))

        if card_type == 'workshop':
            # Parça Atölyesi: farklı şekillerde parçalar göster (Plus, Y, özel)
            preview_pieces = ['Plus', 'T', 'Y', 'L']
            preview_colors = [
                UIColors.NEON_MAGENTA,
                UIColors.NEON_CYAN,
                (255, 165, 0),  # Orange
                (0, 255, 150),  # Green
            ]
        else:
            # Blok Görünümleri: klasik parçalar farklı renklerde
            preview_pieces = ['I', 'O', 'S', 'Z', 'J']
            preview_colors = [
                UIColors.NEON_CYAN,
                (255, 215, 0),  # Gold
                UIColors.NEON_GREEN,
                UIColors.NEON_RED,
                (138, 43, 226),  # Purple
            ]

        # Parçaları grid düzeninde çiz
        pieces_per_row = 2
        piece_margin = max(4, int(8 * card_scale))
        col_w = (inner_w - piece_margin) // pieces_per_row
        rows = ((len(preview_pieces) + pieces_per_row - 1) // pieces_per_row)
        row_h = max(18, (preview_area_h - piece_margin) // rows)

        tick = self._showcase_anim_tick

        for idx, (pname, pcolor) in enumerate(zip(preview_pieces, preview_colors)):
            col = idx % pieces_per_row
            row = idx // pieces_per_row
            px = inner_x + col * (col_w + piece_margin // 2)
            py = preview_area_top + row * row_h

            shape = PIECE_PREVIEW_SHAPES.get(pname, [(0, 0)])
            # Şekli merkeze al
            min_sx = min(c[0] for c in shape)
            max_sx = max(c[0] for c in shape)
            min_sy = min(c[1] for c in shape)
            max_sy = max(c[1] for c in shape)
            shape_w = (max_sx - min_sx + 1) * cell_size
            shape_h = (max_sy - min_sy + 1) * cell_size
            offset_x = px + (col_w - shape_w) // 2
            offset_y = py + (row_h - shape_h) // 2

            # Hafif nefes alan parlaklık animasyonu
            brightness = 0.7 + 0.3 * abs(math.sin((tick + idx * 20) * 0.03))
            r = min(255, int(pcolor[0] * brightness))
            g = min(255, int(pcolor[1] * brightness))
            b = min(255, int(pcolor[2] * brightness))
            draw_color = (r, g, b)

            for cx, cy in shape:
                bx = offset_x + (cx - min_sx) * cell_size
                by = offset_y + (cy - min_sy) * cell_size
                cs = cell_size - 1
                # Arka plandaki düşen blokların jelly stiliyle çiz
                cell_surf = pygame.Surface((cs, cs), pygame.SRCALPHA)
                draw_jelly_block(cell_surf, 0, 0, cs, draw_color)
                cell_surf.set_alpha(200)
                self.screen.blit(cell_surf, (bx, by))

        # ── Başlık metni ──
        title_y = rect.bottom - max(62, int(82 * card_scale))
        title_font_sz = max(18, int(22 * card_scale))
        title_surf = retro_style.render_fit_text(
            title, UIColors.TEXT_PRIMARY, inner_w, title_font_sz, bold=True, min_size=14
        )
        self.screen.blit(title_surf, title_surf.get_rect(midleft=(inner_x, title_y)))

        # ── Alt açıklama (girintili mini panel) ──
        desc_y = title_y + max(22, int(28 * card_scale))
        desc_font_sz = max(13, int(16 * card_scale))
        desc_pad_x = max(8, int(10 * card_scale))
        desc_pad_y = max(4, int(5 * card_scale))
        desc_surf = retro_style.render_fit_text(
            subtitle, UIColors.TEXT_SECONDARY, inner_w - desc_pad_x * 2 - 6, desc_font_sz, bold=False, min_size=11
        )
        desc_bg_w = min(inner_w, desc_surf.get_width() + desc_pad_x * 2 + 6)
        desc_bg_h = desc_surf.get_height() + desc_pad_y * 2
        desc_bg_x = inner_x
        desc_bg_y = desc_y - desc_pad_y
        desc_bg = pygame.Surface((desc_bg_w, desc_bg_h), pygame.SRCALPHA)
        pygame.draw.rect(desc_bg, (15, 22, 42, 150), desc_bg.get_rect(), border_radius=7)
        pygame.draw.rect(desc_bg, (*accent_color[:3], 140), pygame.Rect(0, 3, 3, desc_bg_h - 6), border_radius=2)
        pygame.draw.rect(desc_bg, (*accent_color[:3], 45), desc_bg.get_rect(), 1, border_radius=7)
        self.screen.blit(desc_bg, (desc_bg_x, desc_bg_y))
        self.screen.blit(desc_surf, desc_surf.get_rect(midleft=(desc_bg_x + desc_pad_x + 4, desc_y + desc_surf.get_height() // 2)))

        # ── "Aç →" hover göstergesi ──
        if hover:
            arrow_text = '→'
            arrow_surf = retro_style.render_fit_text(
                arrow_text, accent_color, max(22, int(30 * card_scale)), max(18, int(22 * card_scale)), bold=True
            )
            self.screen.blit(
                arrow_surf,
                arrow_surf.get_rect(midright=(rect.right - max(8, int(12 * card_scale)), rect.bottom - max(12, int(20 * card_scale))))
            )

        return rect

    def _draw_corner_button(
        self,
        rect: pygame.Rect,
        icon_text: str | None = None,
        icon_surface: pygame.Surface | None = None,
        accent_color: tuple[int, int, int] | None = None,
        is_active: bool = False,
    ) -> None:
        """Tüm köşe butonları için ortak çizim metodu.

        Glassmorphism + neon border temalı, SOS butonu ile aynı aileden.
        ``accent_color`` butonun neon çerçeve rengidir.
        ``is_active`` True ise buton "basılı/aktif" görünür (örn. mute açıkken).
        """
        if accent_color is None:
            accent_color = UIColors.NEON_CYAN

        mouse_pos = get_mouse_pos()
        hover = rect.collidepoint(mouse_pos)

        # Glass arka plan
        alpha = 210 if (hover or is_active) else 160
        retro_style.draw_glass_panel(self.screen, rect, alpha=alpha, border_color=accent_color)

        # İnce renkli dolgu overlay (hover/aktif durumda)
        if hover or is_active:
            fill = pygame.Surface(rect.size, pygame.SRCALPHA)
            fill.fill((*accent_color[:3], 30 if hover else 20))
            self.screen.blit(fill, rect.topleft)

        # Neon çerçeve
        border_alpha = 180 if (hover or is_active) else 120
        pygame.draw.rect(self.screen, (*accent_color[:3], border_alpha), rect, 2, border_radius=12)

        # İkon çiz
        if icon_surface is not None:
            icon_rect = icon_surface.get_rect(center=rect.center)
            self.screen.blit(icon_surface, icon_rect)
        elif icon_text:
            label = retro_style.render_fit_text(icon_text, UIColors.TEXT_PRIMARY, rect.width - 8, min(22, rect.height - 8), bold=True)
            self.screen.blit(label, label.get_rect(center=rect.center))

    def _draw_gear_icon(self, size: int) -> pygame.Surface:
        """Pygame ile vektörel dişli (⚙) ikonu çiz."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        r_outer = int(size * 0.42)
        r_inner = int(size * 0.26)
        r_hole = int(size * 0.14)
        teeth = 8
        points = []
        for i in range(teeth * 2):
            angle = math.pi * 2 * i / (teeth * 2) - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        pygame.draw.polygon(surf, UIColors.TEXT_PRIMARY, points)
        pygame.draw.circle(surf, (0, 0, 0, 0), (cx, cy), r_hole)
        # Delik için arka planı temizle
        hole_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(hole_surf, (255, 255, 255, 255), (cx, cy), r_hole)
        # BLEND ile deliği aç
        surf.blit(hole_surf, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return surf

    def _draw_speaker_icon(self, size: int, muted: bool = False) -> pygame.Surface:
        """Pygame ile hoparlör / sessize alma ikonu çiz."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        s = size  # referans boyut

        # Hoparlör gövdesi (basit trapez/dikdörtgen + üçgen)
        body_w = int(s * 0.18)
        body_h = int(s * 0.28)
        body_x = int(cx - s * 0.16)
        body_y = cy - body_h // 2
        pygame.draw.rect(surf, UIColors.TEXT_PRIMARY, (body_x, body_y, body_w, body_h))

        # Huni (üçgen)
        cone_points = [
            (body_x + body_w, body_y),
            (body_x + body_w + int(s * 0.18), int(cy - s * 0.22)),
            (body_x + body_w + int(s * 0.18), int(cy + s * 0.22)),
            (body_x + body_w, body_y + body_h),
        ]
        pygame.draw.polygon(surf, UIColors.TEXT_PRIMARY, cone_points)

        if muted:
            # X işareti
            x_offset = int(cx + s * 0.14)
            x_size = int(s * 0.16)
            line_w = max(2, int(s * 0.06))
            pygame.draw.line(surf, UIColors.NEON_RED, (x_offset, cy - x_size), (x_offset + x_size * 2, cy + x_size), line_w)
            pygame.draw.line(surf, UIColors.NEON_RED, (x_offset, cy + x_size), (x_offset + x_size * 2, cy - x_size), line_w)
        else:
            # Ses dalgaları (yaylar)
            wave_x = int(cx + s * 0.16)
            for i, r in enumerate([int(s * 0.14), int(s * 0.22)]):
                alpha = 220 - i * 60
                color = (*UIColors.NEON_CYAN[:3], alpha)
                pygame.draw.arc(surf, color,
                                (wave_x, cy - r, r * 2, r * 2),
                                -math.pi / 3, math.pi / 3, max(2, int(s * 0.04)))

        return surf

    def _draw_user_switch_icon(self, size: int) -> pygame.Surface:
        """Kullanıcı değiştir ikonu (iki ok + kişi silueti)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        s = size

        # Kişi silueti
        head_r = int(s * 0.13)
        pygame.draw.circle(surf, UIColors.TEXT_PRIMARY, (cx, int(cy - s * 0.1)), head_r)
        body_rect = pygame.Rect(int(cx - s * 0.18), int(cy + s * 0.06), int(s * 0.36), int(s * 0.2))
        pygame.draw.rect(surf, UIColors.TEXT_PRIMARY, body_rect, border_radius=max(4, int(s * 0.06)))

        # Döngüsel oklar (sağ üst ve sol alt)
        arrow_color = UIColors.NEON_MAGENTA
        lw = max(2, int(s * 0.05))
        # Sağ üst ok
        pygame.draw.arc(surf, arrow_color,
                        (int(cx + s * 0.08), int(cy - s * 0.38), int(s * 0.32), int(s * 0.32)),
                        -math.pi / 2, math.pi / 2, lw)
        # Ok ucu
        ax, ay = int(cx + s * 0.24), int(cy - s * 0.06)
        pygame.draw.polygon(surf, arrow_color, [
            (ax, ay - int(s * 0.06)),
            (ax + int(s * 0.08), ay),
            (ax, ay + int(s * 0.06)),
        ])
        # Sol alt ok
        pygame.draw.arc(surf, arrow_color,
                        (int(cx - s * 0.4), int(cy + s * 0.06), int(s * 0.32), int(s * 0.32)),
                        math.pi / 2, math.pi * 1.5, lw)
        ax2, ay2 = int(cx - s * 0.24), int(cy + s * 0.38)
        pygame.draw.polygon(surf, arrow_color, [
            (ax2, ay2 - int(s * 0.06)),
            (ax2 - int(s * 0.08), ay2),
            (ax2, ay2 + int(s * 0.06)),
        ])
        return surf

    def _draw_credits_icon(self, size: int) -> pygame.Surface:
        """Emeği geçenler ikonu (yıldız/kalp)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        # Yıldız çiz
        r_outer = int(size * 0.38)
        r_inner = int(size * 0.18)
        points_count = 5
        star_points = []
        for i in range(points_count * 2):
            angle = math.pi * 2 * i / (points_count * 2) - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            star_points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        pygame.draw.polygon(surf, UIColors.NEON_GOLD, star_points)
        # İç kenarlık
        pygame.draw.polygon(surf, (*UIColors.NEON_GOLD[:3], 80), star_points, 1)
        return surf

    def _draw_trophy_icon(self, size: int) -> pygame.Surface:
        """Başarılar ikonu (kupa/trophy)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        s = size
        color = UIColors.NEON_GOLD
        # Kupa gövdesi (üst yarı)
        cup_top = int(s * 0.12)
        cup_bottom = int(s * 0.55)
        cup_left = int(s * 0.25)
        cup_right = int(s * 0.75)
        cup_body = pygame.Rect(cup_left, cup_top, cup_right - cup_left, cup_bottom - cup_top)
        pygame.draw.rect(surf, color, cup_body, border_radius=4)
        # Kulplar (sol ve sağ yaylar)
        handle_w = int(s * 0.08)
        # Sol kulp
        pygame.draw.arc(surf, color,
                        (int(s * 0.10), int(s * 0.16), int(s * 0.20), int(s * 0.30)),
                        math.pi * 0.5, math.pi * 1.5, max(2, handle_w))
        # Sağ kulp
        pygame.draw.arc(surf, color,
                        (int(s * 0.70), int(s * 0.16), int(s * 0.20), int(s * 0.30)),
                        -math.pi * 0.5, math.pi * 0.5, max(2, handle_w))
        # Sap (dikey çizgi)
        stem_x = s // 2
        stem_top = cup_bottom
        stem_bottom = int(s * 0.72)
        pygame.draw.line(surf, color, (stem_x, stem_top), (stem_x, stem_bottom), max(2, int(s * 0.08)))
        # Taban
        base_y = stem_bottom
        base_left = int(s * 0.28)
        base_right = int(s * 0.72)
        base_h = int(s * 0.10)
        pygame.draw.rect(surf, color, (base_left, base_y, base_right - base_left, base_h), border_radius=2)
        return surf

    def _draw_book_icon(self, size: int) -> pygame.Surface:
        """Kılavuz ikonu (kitap/book)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        s = size
        color = (100, 200, 255)  # Açık mavi
        # Kitap gövdesi
        book_left = int(s * 0.18)
        book_top = int(s * 0.12)
        book_w = int(s * 0.64)
        book_h = int(s * 0.76)
        pygame.draw.rect(surf, color, (book_left, book_top, book_w, book_h), border_radius=3)
        # Sırt (sol kenar koyu şerit)
        spine_w = int(s * 0.10)
        pygame.draw.rect(surf, (*color[:3],), (book_left, book_top, spine_w, book_h), border_radius=2)
        darker = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        pygame.draw.rect(surf, darker, (book_left, book_top, spine_w, book_h), border_radius=2)
        # Sayfa çizgileri
        line_color = (255, 255, 255, 140)
        line_x1 = book_left + spine_w + int(s * 0.08)
        line_x2 = book_left + book_w - int(s * 0.08)
        for i in range(3):
            ly = book_top + int(s * 0.22) + i * int(s * 0.16)
            pygame.draw.line(surf, line_color, (line_x1, ly), (line_x2, ly), 1)
        # Kenarlık
        pygame.draw.rect(surf, (*color[:3], 100), (book_left, book_top, book_w, book_h), 1, border_radius=3)
        return surf

    def _draw_corner_buttons(self):
        """Ana menüde köşe butonlarını çiz."""
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        btn_size = max(42, int(52 * scale))
        margin = max(14, int(18 * scale))
        gap = max(6, int(8 * scale))  # Butonlar arası boşluk

        # --- SOL ÜST: Ayarlar (dişli) ---
        self.corner_settings_rect = pygame.Rect(margin, margin, btn_size, btn_size)
        self.corner_settings_rect = self._apply_layout_override_rect('settings_button', self.corner_settings_rect, width, height, min_w=30, min_h=30)
        settings_icon_size = int(min(self.corner_settings_rect.w, self.corner_settings_rect.h) * 0.56)
        gear_icon = self._load_emoji_icon('gear', settings_icon_size) or self._draw_gear_icon(settings_icon_size)
        self._draw_corner_button(
            self.corner_settings_rect,
            icon_surface=gear_icon,
            accent_color=UIColors.NEON_CYAN,
        )

        # --- SOL ÜST ALT: Dil (dünya) ---
        language_y = margin + btn_size + gap
        self.corner_language_rect = pygame.Rect(margin, language_y, btn_size, btn_size)
        self.corner_language_rect = self._apply_layout_override_rect('language_button', self.corner_language_rect, width, height, min_w=30, min_h=30)
        language_icon_size = int(min(self.corner_language_rect.w, self.corner_language_rect.h) * 0.56) + 2
        world_icon = self._load_emoji_icon('language_icon', language_icon_size)
        if world_icon is None:
            world_icon = self._render_emoji_surface('🌍', language_icon_size)
        self._draw_corner_button(
            self.corner_language_rect,
            icon_surface=world_icon,
            accent_color=(255, 90, 90),
        )

        # --- SOL ÜST + 1: Sessize Al ---
        mute_x = margin + btn_size + gap
        self.corner_mute_rect = pygame.Rect(mute_x, margin, btn_size, btn_size)
        self.corner_mute_rect = self._apply_layout_override_rect('mute_button', self.corner_mute_rect, width, height, min_w=30, min_h=30)

        # Emoji ikonunu dene, yoksa vektörel çiz
        emoji_icon_name = 'mute' if self._is_muted else 'sound'
        mute_icon_size = int(min(self.corner_mute_rect.w, self.corner_mute_rect.h) * 0.56)
        emoji_icon = self._load_emoji_icon(emoji_icon_name, mute_icon_size)
        if emoji_icon is None:
            emoji_icon = self._draw_speaker_icon(mute_icon_size, muted=self._is_muted)

        self._draw_corner_button(
            self.corner_mute_rect,
            icon_surface=emoji_icon,
            accent_color=UIColors.NEON_RED if self._is_muted else UIColors.NEON_GREEN,
            is_active=self._is_muted,
        )

        # --- SAĞ ÜST (SOS altı): Kullanıcı Değiştir ---
        # SOS butonunun hemen altına yerleştir
        sos_bottom = self.sos_button_rect.bottom if self.sos_button_rect else margin + btn_size
        switch_x = width - margin - btn_size
        switch_y = sos_bottom + gap
        self.corner_switch_user_rect = pygame.Rect(switch_x, switch_y, btn_size, btn_size)
        self.corner_switch_user_rect = self._apply_layout_override_rect('switch_user_button', self.corner_switch_user_rect, width, height, min_w=30, min_h=30)
        switch_icon_size = int(min(self.corner_switch_user_rect.w, self.corner_switch_user_rect.h) * 0.56)
        user_icon = self._load_emoji_icon('person', switch_icon_size) or self._draw_user_switch_icon(switch_icon_size)
        self._draw_corner_button(
            self.corner_switch_user_rect,
            icon_surface=user_icon,
            accent_color=UIColors.NEON_MAGENTA,
        )

        # --- SOL ALT: Emeği Geçenler ---
        credits_y = height - margin - btn_size
        self.corner_credits_rect = pygame.Rect(margin, credits_y, btn_size, btn_size)
        self.corner_credits_rect = self._apply_layout_override_rect('credits_button', self.corner_credits_rect, width, height, min_w=30, min_h=30)
        credits_icon_size = int(min(self.corner_credits_rect.w, self.corner_credits_rect.h) * 0.56)
        credits_icon = self._load_emoji_icon('star', credits_icon_size) or self._draw_credits_icon(credits_icon_size)
        self._draw_corner_button(
            self.corner_credits_rect,
            icon_surface=credits_icon,
            accent_color=UIColors.NEON_GOLD,
        )

        # --- SOL ALT + 1: Yüksek skorlar (credits'in yanı) ---
        ach_x = margin + btn_size + gap
        self.corner_achievements_rect = pygame.Rect(ach_x, credits_y, btn_size, btn_size)
        self.corner_achievements_rect = self._apply_layout_override_rect('high_scores_button', self.corner_achievements_rect, width, height, min_w=30, min_h=30)
        high_scores_icon_size = int(min(self.corner_achievements_rect.w, self.corner_achievements_rect.h) * 0.56)
        trophy_icon = self._load_emoji_icon('trophy', high_scores_icon_size) or self._draw_trophy_icon(high_scores_icon_size)
        self._draw_corner_button(
            self.corner_achievements_rect,
            icon_surface=trophy_icon,
            accent_color=UIColors.NEON_GOLD,
        )

        # --- SOL ALT ÜST: Kılavuz (credits'in üstü) ---
        guide_y = credits_y - btn_size - gap
        self.corner_guide_rect = pygame.Rect(margin, guide_y, btn_size, btn_size)
        self.corner_guide_rect = self._apply_layout_override_rect('guide_button', self.corner_guide_rect, width, height, min_w=30, min_h=30)
        guide_icon_size = int(min(self.corner_guide_rect.w, self.corner_guide_rect.h) * 0.56)
        book_icon = self._load_emoji_icon('book', guide_icon_size) or self._draw_book_icon(guide_icon_size)
        self._draw_corner_button(
            self.corner_guide_rect,
            icon_surface=book_icon,
            accent_color=(100, 200, 255),
        )

    def _get_menu_language_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for code, native_name, _flag, _complete in get_all_languages():
            options.append((code, native_name))
        return options

    def _open_menu_language_panel(self) -> None:
        self.menu_language_panel_open = True
        self.menu_language_panel_scroll = 0
        self.menu_language_panel_item_rects = []
        self.menu_language_panel_sb_drag_active = False
        self.menu_language_panel_sb_drag_offset_y = 0
        self.menu_language_panel_sb_thumb_rect = None
        self.menu_language_panel_sb_container_rect = None
        langs = self._get_menu_language_options()
        codes = [code for code, _label in langs]
        try:
            self.menu_language_panel_selected = codes.index(get_language())
        except Exception:
            self.menu_language_panel_selected = 0

    def _close_menu_language_panel(self) -> None:
        self.menu_language_panel_open = False
        self.menu_language_panel_scroll = 0
        self.menu_language_panel_item_rects = []
        self.menu_language_panel_rect = None
        self.menu_language_panel_sb_drag_active = False
        self.menu_language_panel_sb_drag_offset_y = 0
        self.menu_language_panel_sb_thumb_rect = None
        self.menu_language_panel_sb_container_rect = None

    def _apply_menu_language_choice(self, lang_code: str) -> str | None:
        if not lang_code:
            return None
        if lang_code == get_language():
            return None
        set_language(lang_code)
        apply_language_ui_profile(lang_code)
        try:
            if self.settings_manager:
                self.settings_manager.set('language', lang_code)
        except Exception:
            pass
        self._update_options()
        return 'language_changed'

    def _get_menu_language_panel_rect(self) -> pygame.Rect | None:
        if not self.corner_language_rect:
            return None
        width, height = self.screen.get_size()
        panel_w = min(210, max(170, width - 32))
        item_h = 30
        gap = 4
        total_h = len(self._get_menu_language_options()) * (item_h + gap)
        visible_h = min(240, max(120, height - 220))
        panel_h = min(total_h + 12, visible_h)

        panel_x = self.corner_language_rect.left
        if panel_x + panel_w > width - 12:
            panel_x = width - panel_w - 12
        panel_x = max(12, panel_x)

        panel_y = self.corner_language_rect.bottom + 8
        if panel_y + panel_h > height - 12:
            panel_y = height - panel_h - 12
        panel_y = max(12, panel_y)

        return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    def _menu_language_panel_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        n = len(self._get_menu_language_options())
        total_h = n * (item_h + gap) - (gap if n > 0 else 0)
        return max(0, total_h - max(visible_h, 0))

    def _menu_language_panel_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.menu_language_panel_selected * (item_h + gap)
        if y < self.menu_language_panel_scroll:
            self.menu_language_panel_scroll = y
        elif y > self.menu_language_panel_scroll + visible_h - item_h:
            self.menu_language_panel_scroll = y - (visible_h - item_h)
        self.menu_language_panel_scroll = max(0, min(self.menu_language_panel_scroll, self._menu_language_panel_max_scroll(visible_h, item_h, gap)))

    def _handle_menu_language_panel_input(self, event):
        langs = self._get_menu_language_options()
        if not langs:
            self._close_menu_language_panel()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_menu_language_panel()
                return None
            if event.key == pygame.K_UP:
                self.menu_language_panel_selected = (self.menu_language_panel_selected - 1) % len(langs)
                return None
            if event.key == pygame.K_DOWN:
                self.menu_language_panel_selected = (self.menu_language_panel_selected + 1) % len(langs)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                code, _label = langs[self.menu_language_panel_selected]
                action = self._apply_menu_language_choice(code)
                self._close_menu_language_panel()
                return action

        elif event.type == pygame.MOUSEWHEEL:
            item_h, gap = 30, 4
            visible_h = (self.menu_language_panel_rect.height - 12) if self.menu_language_panel_rect else 200
            ms = self._menu_language_panel_max_scroll(visible_h, item_h, gap)
            self.menu_language_panel_scroll -= event.y * 30
            self.menu_language_panel_scroll = max(0, min(self.menu_language_panel_scroll, ms))
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Scrollbar drag
            if self.menu_language_panel_sb_drag_active and self.menu_language_panel_sb_container_rect:
                sb_c = self.menu_language_panel_sb_container_rect
                track_y = sb_c.top + 4
                track_h = sb_c.height - 8
                thumb_h = self.menu_language_panel_sb_thumb_rect.height if self.menu_language_panel_sb_thumb_rect else 30
                visible_h = (self.menu_language_panel_rect.height - 12) if self.menu_language_panel_rect else 200
                ms = self._menu_language_panel_max_scroll(visible_h, 30, 4)
                new_thumb_top = pos[1] - self.menu_language_panel_sb_drag_offset_y - track_y
                new_thumb_top = max(0, min(new_thumb_top, track_h - thumb_h))
                ratio = new_thumb_top / max(1, track_h - thumb_h)
                self.menu_language_panel_scroll = int(ratio * ms)
                return None
            # Item hover
            for rect, idx in self.menu_language_panel_item_rects:
                if rect.collidepoint(pos):
                    self.menu_language_panel_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Scrollbar thumb drag başlatma
            if self.menu_language_panel_sb_thumb_rect and self.menu_language_panel_sb_thumb_rect.collidepoint(pos):
                self.menu_language_panel_sb_drag_active = True
                self.menu_language_panel_sb_drag_offset_y = pos[1] - self.menu_language_panel_sb_thumb_rect.y
                return None
            for rect, idx in self.menu_language_panel_item_rects:
                if rect.collidepoint(pos):
                    self.menu_language_panel_selected = idx
                    code, _label = langs[self.menu_language_panel_selected]
                    action = self._apply_menu_language_choice(code)
                    self._close_menu_language_panel()
                    return action
            # Scrollbar alanına tıklama paneli kapatmasın
            sb_area = self.menu_language_panel_sb_container_rect
            in_panel = self.menu_language_panel_rect and self.menu_language_panel_rect.collidepoint(pos)
            in_sb = sb_area is not None and sb_area.inflate(8, 0).collidepoint(pos)
            if not in_panel and not in_sb:
                self._close_menu_language_panel()
            return None

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.menu_language_panel_sb_drag_active = False
            self.menu_language_panel_sb_drag_offset_y = 0

        return None

    def _draw_menu_language_panel(self) -> None:
        if not self.menu_language_panel_open:
            return
        langs = self._get_menu_language_options()
        if not langs:
            return

        panel_rect = self._get_menu_language_panel_rect()
        if panel_rect is None:
            return
        self.menu_language_panel_rect = panel_rect

        language_accent = (255, 90, 90)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=language_accent, glow=False)
        list_rect = pygame.Rect(panel_rect.x + 6, panel_rect.y + 6, panel_rect.width - 12, panel_rect.height - 12)
        item_h = 30
        gap = 4
        self.menu_language_panel_item_rects = []

        self.menu_language_panel_scroll = max(0, min(self.menu_language_panel_scroll, self._menu_language_panel_max_scroll(list_rect.height, item_h, gap)))
        self._menu_language_panel_ensure_visible(list_rect.height, item_h, gap)

        self.screen.set_clip(list_rect)
        for idx, (code, label) in enumerate(langs):
            y = list_rect.y + idx * (item_h + gap) - self.menu_language_panel_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue
            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.menu_language_panel_item_rects.append((r, idx))
            selected = idx == self.menu_language_panel_selected

            bg = (56, 34, 42, 230) if selected else (26, 18, 30, 178)
            border = language_accent if selected else (120, 74, 88)
            pygame.draw.rect(self.screen, bg, r, border_radius=8)
            pygame.draw.rect(self.screen, border, r, 2 if selected else 1, border_radius=8)

            cjk_font = get_font_for_language(code, 18)
            text_font = cjk_font or retro_style.get_font(18, bold=selected)
            txt = text_font.render(str(label), True, (255, 235, 235) if selected else (218, 208, 220))
            self.screen.blit(txt, (r.x + 10, r.y + (r.height - txt.get_height()) // 2))

        self.screen.set_clip(None)

        total_h = len(langs) * (item_h + gap) - gap
        if total_h > list_rect.height:
            # Scrollbar’ı panel'in sağına/dışına konumlandır
            # bar_width=8 → container.right = panel_rect.right+18 → track_x = panel_rect.right+6
            sb_bar_w = 8
            sb_container = pygame.Rect(
                panel_rect.right + 6, list_rect.y,
                sb_bar_w + 4, list_rect.height,
            )
            self.menu_language_panel_sb_container_rect = sb_container
            self.menu_language_panel_sb_thumb_rect = retro_style.draw_scrollbar(
                self.screen,
                sb_container,
                self.menu_language_panel_scroll,
                total_h,
                list_rect.height,
                bar_width=sb_bar_w,
                color=(255, 90, 90),
            )
        else:
            self.menu_language_panel_sb_thumb_rect = None
            self.menu_language_panel_sb_container_rect = None

    def set_muted(self, muted: bool):
        """Dışarıdan ses durumunu güncelle (main.py'den çağrılır)."""
        self._is_muted = bool(muted)


class ControlSettingsScreen:
    """Tuş atamalarını düzenleyen ekran."""

    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font_title = retro_style.get_font(46)
        self.font_tab = retro_style.get_font(26)
        self.font_option = retro_style.get_font(28)
        self.font_value = retro_style.get_font(22, bold=False)
        self.font_small = retro_style.get_font(20, bold=False)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.control_config = self.settings_manager.get_controls()
        self.active_tab = 0
        self.selected_action = 0
        self.waiting_for_key = False
        self.pending_action = None
        self.pending_slot = None
        self.binding_slot = 'primary'  # sadece Tek Oyuncu sekmesinde kullanılır
        self.status_message = t('control_status_hint')
        self.tab_rects = []
        self.action_rects = []
        self.gamepad_subtab = 0  # 0=Genel, 1=Oyun İçi, 2=Kart Modu, 3=Ana Menü
        self.gamepad_subtab_rects = []  # Alt-sekme tıklama alanları

    def _is_single_player_tab(self):
        return self._current_tab_key() == 'single_player'

    def _is_gamepad_tab(self):
        return self._current_tab_key() == 'gamepad'

    # ─── Gamepad tab yardımcıları ───────────────────────────────────────
    def _get_gamepad_rows(self):
        """Aktif alt-sekmeye göre gamepad satırlarını döndürür.
        Her eleman: (row_key, label, row_type)
          row_type: 'toggle' | 'slider' | 'button' | 'info' | 'separator'
        """
        if self.gamepad_subtab == 0:
            return self._get_gamepad_general_rows()
        elif self.gamepad_subtab == 1:
            return self._get_gamepad_game_rows()
        elif self.gamepad_subtab == 2:
            return self._get_gamepad_card_rows()
        else:
            return self._get_gamepad_menu_rows()

    def _get_gamepad_general_rows(self):
        """Genel ayarlar: etkin, titreşim, deadzone."""
        return [
            ('enabled',    t('gp_enabled'),        'toggle'),
            ('rumble',     t('gp_rumble'),          'toggle'),
            ('deadzone',   t('gp_deadzone'),        'slider'),
            ('mouse_sensitivity', t('gp_mouse_sensitivity'), 'slider'),
        ]

    def _get_gamepad_game_rows(self):
        """Oyun içi kontroller."""
        return [
            ('_move_info', t('gp_move_direction'),  'info'),
            ('hard_drop',  t('gp_hard_drop'),       'button'),
            ('hold',       t('gp_hold'),            'button'),
            ('pause',      t('gp_pause'),           'button'),
            ('main_menu_prompt', t('gp_main_menu_prompt'), 'button'),
            ('discard_held', t('gp_discard_held'),  'button'),
        ]

    def _get_gamepad_menu_rows(self):
        """Ana menü kontrolleri."""
        return [
            ('_nav_info',     t('gp_menu_navigate'),  'info'),
            ('menu_confirm',  t('gp_menu_confirm'),   'button'),
            ('menu_back',     t('gp_menu_back'),      'button'),
            ('menu_tab_next', t('gp_menu_tab_next'),  'button'),
            ('menu_tab_prev', t('gp_menu_tab_prev'),  'button'),
        ]

    def _get_gamepad_card_rows(self):
        """Kart modu kontrolleri (Kart Ustaligi)."""
        return [
            ('card_rewind', t('gp_card_rewind'), 'button'),
            ('card_sniper', t('gp_card_sniper'), 'button'),
            ('card_time_capsule_save', t('gp_card_time_capsule_save'), 'button'),
            ('card_time_capsule_restore', t('gp_card_time_capsule_restore'), 'button'),
            ('card_phase_shift', t('gp_card_phase_shift'), 'button'),
            ('card_ghost', t('gp_card_ghost'), 'button'),
            ('card_hammer', t('gp_card_hammer'), 'button'),
            ('card_bomb', t('gp_card_bomb'), 'button'),
            ('hold2', t('gp_hold2'), 'button'),
        ]

    def _gamepad_cfg(self):
        """Geçerli gamepad ayarlarını döndür."""
        cfg = self.control_config.get('gamepad')
        if cfg is None:
            from settings_manager import DEFAULT_CONTROLS
            cfg = dict(DEFAULT_CONTROLS.get('gamepad', {}))
            self.control_config['gamepad'] = cfg
        return cfg

    # ─── Input ──────────────────────────────────────────────────────────

    def handle_input(self, event):
        # Gamepad rebind sonrası: aynı frame'deki sentetik KEYDOWN'ı yut
        if getattr(self, '_swallow_next_keydown', False) and event.type == pygame.KEYDOWN:
            self._swallow_next_keydown = False
            return None

        # Gamepad buton bekleme modu
        if self.waiting_for_key and self._is_gamepad_tab():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.waiting_for_key = False
                self.pending_action = None
                return None
            if event.type == pygame.JOYBUTTONDOWN:
                self._apply_gamepad_button(event.button)
                return None
            # LT/RT trigger desteği - axis 4/5 basıldığında algıla
            if event.type == pygame.JOYAXISMOTION and event.axis in (4, 5):
                # Trigger değeri > 0.5 ise basılmış say
                trigger_val = (event.value + 1.0) / 2.0  # -1..1 → 0..1
                if trigger_val >= 0.5:
                    # LT = axis 4 → özel index 100, RT = axis 5 → özel index 101
                    trigger_index = 100 if event.axis == 4 else 101
                    self._apply_gamepad_button(trigger_index)
                return None
            return None

        if self.waiting_for_key:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.waiting_for_key = False
                    self.pending_action = None
                    self.pending_slot = None
                else:
                    key_name = pygame.key.name(event.key)
                    self._apply_binding(key_name)
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

            if self._is_gamepad_tab():
                return self._handle_gamepad_tab_key(event)

            if event.key == pygame.K_UP:
                self.selected_action = (self.selected_action - 1) % len(self._current_actions())
            elif event.key == pygame.K_DOWN:
                self.selected_action = (self.selected_action + 1) % len(self._current_actions())
            elif event.key == pygame.K_LEFT and self._is_single_player_tab():
                self.binding_slot = 'primary'
            elif event.key == pygame.K_RIGHT and self._is_single_player_tab():
                self.binding_slot = 'secondary'
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._begin_rebind()
            elif event.key == pygame.K_TAB:
                mods = pygame.key.get_mods()
                self._cycle_tab(-1 if mods & pygame.KMOD_SHIFT else 1)
            elif event.key == pygame.K_RIGHTBRACKET:
                self._cycle_tab(1)
            elif event.key == pygame.K_LEFTBRACKET:
                self._cycle_tab(-1)
            elif event.key == pygame.K_r:
                self._reset_active_tab()
            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._revert_selected_binding()
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.action_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected_action = idx
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.tab_rects):
                if rect.collidepoint(mouse_pos):
                    self.active_tab = idx
                    self.selected_action = 0
                    return None
            # Gamepad alt-sekme tıklama
            if self._is_gamepad_tab():
                for idx, rect in enumerate(self.gamepad_subtab_rects):
                    if rect.collidepoint(mouse_pos):
                        self.gamepad_subtab = idx
                        self.selected_action = 0
                        return None
            for idx, rect in enumerate(self.action_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected_action = idx
                    if self._is_gamepad_tab():
                        self._handle_gamepad_row_click(idx)
                    else:
                        self._begin_rebind()
                    return None
        elif event.type == pygame.MOUSEWHEEL:
            total = self._gamepad_row_count() if self._is_gamepad_tab() else len(self._current_actions())
            if event.y > 0:
                self.selected_action = (self.selected_action - 1) % total
            else:
                self.selected_action = (self.selected_action + 1) % total
        return None

    def _handle_gamepad_tab_key(self, event):
        """Gamepad sekmesinde klavye tuşu işle."""
        rows = self._get_gamepad_rows()
        # Alt-sekmelerde header/separator yok; info satırları hariç hepsi navigable
        navigable = [(i, r) for i, r in enumerate(rows) if r[2] not in ('separator',)]
        nav_len = len(navigable)
        if nav_len == 0:
            return None

        if event.key == pygame.K_UP:
            cur_nav = self._gamepad_nav_index(navigable, self.selected_action)
            new_nav = (cur_nav - 1) % nav_len
            self.selected_action = navigable[new_nav][0]
        elif event.key == pygame.K_DOWN:
            cur_nav = self._gamepad_nav_index(navigable, self.selected_action)
            new_nav = (cur_nav + 1) % nav_len
            self.selected_action = navigable[new_nav][0]
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._handle_gamepad_row_click(self.selected_action)
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._handle_gamepad_row_lr(self.selected_action, event.key)
        elif event.key == pygame.K_TAB:
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_SHIFT:
                self._cycle_tab(-1)
            else:
                self._cycle_tab(1)
        elif event.key == pygame.K_r:
            self._reset_active_tab()
        elif event.key == pygame.K_PAGEDOWN or event.key == pygame.K_RIGHTBRACKET:
            # Sonraki alt-sekme
            self.gamepad_subtab = (self.gamepad_subtab + 1) % 4
            self.selected_action = 0
        elif event.key == pygame.K_PAGEUP or event.key == pygame.K_LEFTBRACKET:
            # Önceki alt-sekme
            self.gamepad_subtab = (self.gamepad_subtab - 1) % 4
            self.selected_action = 0
        return None

    def _gamepad_nav_index(self, navigable, selected):
        """selected_action'a karşılık gelen navigable index."""
        for i, (row_idx, _) in enumerate(navigable):
            if row_idx == selected:
                return i
        return 0

    def _gamepad_row_count(self):
        return len(self._get_gamepad_rows())

    def _handle_gamepad_row_click(self, idx):
        """Gamepad satırına tıklama / enter."""
        rows = self._get_gamepad_rows()
        if idx < 0 or idx >= len(rows):
            return
        row_key, _, row_type = rows[idx]
        cfg = self._gamepad_cfg()

        if row_type == 'toggle':
            cfg[row_key] = not cfg.get(row_key, True)
            self._persist_controls()
        elif row_type == 'slider':
            if row_key == 'deadzone':
                # Enter ile 0.05 artır, sınırlama dahilinde
                val = cfg.get('deadzone', 0.35)
                val = round(val + 0.05, 2)
                if val > 0.9:
                    val = 0.1
                cfg['deadzone'] = val
            elif row_key == 'mouse_sensitivity':
                # Enter ile 0.1 artır, sınırlama dahilinde
                val = cfg.get('mouse_sensitivity', 1.0)
                val = round(val + 0.1, 2)
                if val > 2.0:
                    val = 0.5
                cfg['mouse_sensitivity'] = val
            self._persist_controls()
        elif row_type == 'button':
            self.waiting_for_key = True
            self.pending_action = row_key
            self.status_message = t('gp_press_button')

    def _handle_gamepad_row_lr(self, idx, key):
        """Gamepad satırında sol/sağ ok tuşu."""
        rows = self._get_gamepad_rows()
        if idx < 0 or idx >= len(rows):
            return
        row_key, _, row_type = rows[idx]
        cfg = self._gamepad_cfg()

        if row_type == 'toggle':
            cfg[row_key] = not cfg.get(row_key, True)
            self._persist_controls()
        elif row_type == 'slider':
            if row_key == 'deadzone':
                val = cfg.get('deadzone', 0.35)
                delta = 0.05 if key == pygame.K_RIGHT else -0.05
                val = round(max(0.1, min(0.9, val + delta)), 2)
                cfg['deadzone'] = val
            elif row_key == 'mouse_sensitivity':
                val = cfg.get('mouse_sensitivity', 1.0)
                delta = 0.1 if key == pygame.K_RIGHT else -0.1
                val = round(max(0.5, min(2.0, val + delta)), 2)
                cfg['mouse_sensitivity'] = val
            self._persist_controls()

    def _apply_gamepad_button(self, button_index):
        """Basılan gamepad butonunu mevcut aksiyona ata."""
        cfg = self._gamepad_cfg()
        if self.pending_action:
            cfg[self.pending_action] = button_index
            self.waiting_for_key = False
            self.pending_action = None
            # Rebind tamamlandıktan sonra aynı frame'de gelen sentetik
            # KEYDOWN eventini yutmak için flag ayarla. Aksi halde örneğin
            # B ile rebind yapıldığında sentetik K_ESCAPE ayarlar ekranını kapatır.
            self._swallow_next_keydown = True
            self._persist_controls()

    # ─── Draw ───────────────────────────────────────────────────────────

    def draw(self):
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        # ── Panel (ayarlar ekranı stiliyle aynı) ──
        pw = min(1200, max(700, int(width * 0.88)))
        ph = min(850, max(500, int(height * 0.88)))
        px = (width - pw) // 2
        py = (height - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)

        # Gölge
        shadow = pygame.Surface((pw + 10, ph + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 60), shadow.get_rect(), border_radius=16)
        self.screen.blit(shadow, (px + 5, py + 5))
        # Arka plan
        panel_surf = pygame.Surface(panel.size, pygame.SRCALPHA)
        panel_surf.fill((12, 16, 32, 235))
        for yy in range(min(30, ph // 4)):
            alpha = int(15 * (1 - yy / 30))
            pygame.draw.line(panel_surf, (255, 255, 255, alpha), (0, yy), (pw, yy))
        self.screen.blit(panel_surf, panel.topleft)
        pygame.draw.rect(self.screen, (60, 70, 100), panel, 2, border_radius=14)
        pygame.draw.line(self.screen, (80, 140, 220), (px + 2, py + 1), (px + pw - 2, py + 1), 1)

        # ── Başlık (panel içinde) ──
        title_font = retro_style.get_font(36)
        title_text = t('panel_controls')
        title_surf = title_font.render(title_text, True, (220, 235, 255))
        self.screen.blit(title_surf, (px + 24, py + 14))

        # Başlık altı çizgi
        pygame.draw.line(self.screen, (50, 60, 90), (px + 14, py + 56), (px + pw - 14, py + 56), 1)

        # ── Sekmeler (panel içinde) ──
        self.tab_rects = []
        control_tabs = get_control_tabs()
        tab_gap = 6
        inner_w = pw - 40
        tab_width = (inner_w - tab_gap * (len(control_tabs) - 1)) // len(control_tabs)
        tab_y = py + 64
        tab_h = 40
        for idx, (_, label) in enumerate(control_tabs):
            tx = px + 20 + idx * (tab_width + tab_gap)
            rect = pygame.Rect(tx, tab_y, tab_width, tab_h)
            self.tab_rects.append(rect)
            is_active = (idx == self.active_tab)
            # Tab arka plan
            tab_bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            if is_active:
                tab_bg.fill((35, 55, 90, 220))
            else:
                tab_bg.fill((20, 28, 48, 160))
            self.screen.blit(tab_bg, rect.topleft)
            # Alt çizgi (aktif)
            if is_active:
                indicator = pygame.Rect(rect.x, rect.bottom - 3, rect.width, 3)
                pygame.draw.rect(self.screen, (80, 180, 255), indicator)
            # Tab label
            label_color = (255, 255, 255) if is_active else (140, 155, 180)
            tab_font = retro_style.get_fitting_font(label, 18, tab_width - 10, bold=is_active)
            label_surface = tab_font.render(label, True, label_color)
            self.screen.blit(label_surface, label_surface.get_rect(center=rect.center))

        # Gamepad sekmesi ise özel çizim
        if self._is_gamepad_tab():
            self._draw_gamepad_tab(width, height, tab_y, tab_h)
            return

        # ── Tuş kartları (panel içinde) ──
        self.action_rects = []
        actions = self._current_actions()
        current_values = self._resolve_section(self.control_config, self._current_tab_key())
        card_width = pw - 56
        card_h = 58
        card_gap = 6
        content_top = tab_y + tab_h + 16
        content_bottom = py + ph - 18

        clip_rect = pygame.Rect(px + 18, content_top, pw - 36, content_bottom - content_top)
        self.screen.set_clip(clip_rect)

        for idx, (action_key, label) in enumerate(actions):
            y_pos = content_top + idx * (card_h + card_gap)
            rect = pygame.Rect(px + 28, y_pos, card_width, card_h)
            self.action_rects.append(rect)
            selected = (idx == self.selected_action)

            # Tuş değeri
            value = current_values.get(action_key)
            if self._is_single_player_tab() and isinstance(value, dict):
                primary_label = self._format_key_label(value.get('primary'))
                secondary_label = self._format_key_label(value.get('secondary'))
                if self.binding_slot == 'primary':
                    key_label = f'[{primary_label}] | {secondary_label}'
                else:
                    key_label = f'{primary_label} | [{secondary_label}]'
            else:
                key_label = self._format_key_label(value)

            # Satır arka planı (ayarlar paneli stili)
            bg_alpha = 180 if selected else 130
            bg_color = (28, 38, 60) if selected else (18, 24, 42)
            row_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            row_surf.fill((*bg_color, bg_alpha))
            if selected:
                for ry in range(min(8, rect.height // 4)):
                    a = int(15 * (1 - ry / 8))
                    pygame.draw.line(row_surf, (255, 255, 255, a), (0, ry), (rect.width, ry))
            self.screen.blit(row_surf, rect.topleft)

            if selected:
                pygame.draw.rect(self.screen, (80, 160, 255, 180), rect, 1, border_radius=6)
            else:
                pygame.draw.rect(self.screen, (40, 50, 70), rect, 1, border_radius=6)

            # Label
            label_color = (255, 255, 255) if selected else (190, 200, 215)
            lbl_font = retro_style.get_fitting_font(label.upper(), 22, int(rect.width * 0.42), bold=True)
            lbl_surf = lbl_font.render(label.upper(), True, label_color)
            self.screen.blit(lbl_surf, (rect.x + 24, rect.centery - lbl_surf.get_height() // 2))

            # Tuş değeri (sağ tarafta)
            val_font = retro_style.get_fitting_font(key_label, 20, int(rect.width * 0.45), bold=True)
            val_surf = val_font.render(key_label, True, (100, 200, 255))
            self.screen.blit(val_surf, (rect.right - val_surf.get_width() - 24, rect.centery - val_surf.get_height() // 2))

        self.screen.set_clip(None)

        # Tuş bekleme overlay
        if self.waiting_for_key:
            self._draw_waiting_overlay(width, height)

    def _draw_gamepad_tab(self, width, height, tab_y, tab_h):
        """Gamepad sekmesi çizimi - alt-sekmeli yapı ile."""
        from gamepad_manager import get_gamepad_manager, is_gamepad_connected

        gpm = get_gamepad_manager()
        cfg = self._gamepad_cfg()

        card_width = min(500, width - 120)
        card_h = 52
        card_gap = 6
        start_y = tab_y + tab_h + 16

        # ── Bağlantı durumu ──
        connected = is_gamepad_connected()
        status_text = t('gp_status_connected') if connected else t('gp_status_disconnected')
        if connected:
            gp_name = gpm.get_gamepad_type_label()
            status_text = f"{status_text}  —  {gp_name}"
        status_surf = self.font_small.render(status_text, True,
                                              (100, 220, 140) if connected else (220, 100, 100))
        self.screen.blit(status_surf, status_surf.get_rect(center=(width // 2, start_y)))
        start_y += 26

        # ── Alt-sekmeler çiz ──
        subtab_labels = [
            t('gp_section_general'),
            t('gp_section_ingame'),
            t('gp_section_card'),
            t('gp_section_menu'),
        ]
        subtab_w = min(150, max(100, (card_width - 16) // 4))
        subtab_h = 36
        subtab_gap = 6
        total_subtab_w = subtab_w * len(subtab_labels) + subtab_gap * (len(subtab_labels) - 1)
        subtab_start_x = (width - total_subtab_w) // 2
        self.gamepad_subtab_rects = []

        for idx, label in enumerate(subtab_labels):
            rect = pygame.Rect(
                subtab_start_x + idx * (subtab_w + subtab_gap),
                start_y,
                subtab_w,
                subtab_h,
            )
            self.gamepad_subtab_rects.append(rect)
            is_active = (idx == self.gamepad_subtab)
            if is_active:
                bg_color = (50, 100, 160)
                border_color = (100, 180, 255)
            else:
                bg_color = (25, 35, 55)
                border_color = (60, 75, 100)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=8)
            label_color = (255, 255, 255) if is_active else (160, 170, 190)
            sub_font = retro_style.get_font(20, bold=is_active)
            label_surf = sub_font.render(label, True, label_color)
            self.screen.blit(label_surf, label_surf.get_rect(center=rect.center))

        start_y += subtab_h + 14

        # ── Aktif alt-sekmenin satırlarını çiz ──
        rows = self._get_gamepad_rows()
        self.action_rects = []

        for idx, (row_key, label, row_type) in enumerate(rows):
            y_pos = start_y + idx * (card_h + card_gap)

            if row_type == 'separator':
                sep_rect = pygame.Rect((width - card_width) // 2, y_pos + card_h // 2 - 1, card_width, 2)
                self.action_rects.append(sep_rect)
                pygame.draw.rect(self.screen, (50, 60, 80), sep_rect)
                continue

            rect = pygame.Rect((width - card_width) // 2, y_pos, card_width, card_h)
            self.action_rects.append(rect)
            selected = (idx == self.selected_action)

            if row_type == 'toggle':
                val = cfg.get(row_key, True)
                val_text = t('gp_on') if val else t('gp_off')
                val_color = (100, 220, 140) if val else (180, 80, 80)
                retro_style.draw_setting_row(
                    self.screen, rect, label.upper(), f'◀  {val_text}  ▶',
                    selected=selected,
                    label_color=(255, 255, 255) if selected else (200, 200, 200),
                    value_color=val_color,
                    strip_color=(80, 180, 120),
                    kind='default',
                )
            elif row_type == 'slider':
                if row_key == 'deadzone':
                    val = cfg.get('deadzone', 0.35)
                else:
                    val = cfg.get('mouse_sensitivity', 1.0)
                val_text = f'◀  {val:.2f}  ▶'
                retro_style.draw_setting_row(
                    self.screen, rect, label.upper(), val_text,
                    selected=selected,
                    label_color=(255, 255, 255) if selected else (200, 200, 200),
                    value_color=(180, 180, 255),
                    strip_color=(100, 120, 200),
                    kind='default',
                )
            elif row_type == 'info':
                # Bilgi satırı (sadece gösterim)
                info_value = 'SOL STICK'
                retro_style.draw_setting_row(
                    self.screen, rect, label.upper(), info_value,
                    selected=selected,
                    label_color=(180, 200, 220) if selected else (150, 170, 190),
                    value_color=(120, 160, 200),
                    strip_color=(60, 100, 140),
                    kind='default',
                )
            elif row_type == 'button':
                btn_idx = cfg.get(row_key, -1)
                if btn_idx is None or btn_idx < 0:
                    display_label = t('gp_unbound')
                else:
                    xbox_lbl = gpm.get_button_index_label(btn_idx, 'xbox')
                    ps_lbl = gpm.get_button_index_label(btn_idx, 'playstation')
                    if xbox_lbl == ps_lbl:
                        display_label = xbox_lbl
                    else:
                        display_label = f'{xbox_lbl}  /  {ps_lbl}'

                retro_style.draw_setting_row(
                    self.screen, rect, label.upper(), display_label,
                    selected=selected,
                    label_color=(255, 255, 255) if selected else (200, 200, 200),
                    value_color=(255, 200, 100),
                    strip_color=(200, 130, 50),
                    kind='default',
                )

        # Alt-sekme navigasyon ipucu
        hint_text = "PgUp/PgDn: Alt Sekme"
        hint_surf = self.font_small.render(hint_text, True, (100, 110, 140))
        hint_y = start_y + len(rows) * (card_h + card_gap) + 8
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(width // 2, hint_y)))

        # Tuş bekleme overlay (gamepad buton)
        if self.waiting_for_key:
            self._draw_waiting_overlay(width, height, gamepad_mode=True)

    def _draw_waiting_overlay(self, width, height, gamepad_mode=False):
        """Tuş/buton bekleme overlay'i çiz."""
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        # Modal kutu
        modal_w, modal_h = 400, 130
        modal_rect = pygame.Rect((width - modal_w) // 2, (height - modal_h) // 2, modal_w, modal_h)
        pygame.draw.rect(self.screen, (20, 30, 55), modal_rect, border_radius=16)
        pygame.draw.rect(self.screen, retro_style.accent, modal_rect, 3, border_radius=16)
        if gamepad_mode:
            prompt_text = t('gp_press_button')
        else:
            prompt_text = t('press_key')
        prompt = self.font_option.render(prompt_text, True, (255, 255, 255))
        self.screen.blit(prompt, prompt.get_rect(center=(modal_rect.centerx, modal_rect.centery - 12)))
        sub_prompt = self.font_small.render(f"ESC: {t('btn_cancel')}", True, (180, 190, 210))
        self.screen.blit(sub_prompt, sub_prompt.get_rect(center=(modal_rect.centerx, modal_rect.centery + 24)))


    def _current_tab_key(self):
        return get_control_tabs()[self.active_tab][0]

    def _current_actions(self):
        return get_control_actions()[self._current_tab_key()]

    def _begin_rebind(self):
        self.waiting_for_key = True
        self.pending_action = self._current_actions()[self.selected_action][0]
        self.pending_slot = self.binding_slot if self._is_single_player_tab() else None
        self.status_message = t('press_key')

    def _apply_binding(self, key_name):
        section = self._resolve_section(self.control_config, self._current_tab_key())
        if self.pending_action:
            if self._is_single_player_tab():
                current = section.get(self.pending_action)
                if not isinstance(current, dict):
                    current = {'primary': current, 'secondary': ''}
                    section[self.pending_action] = current
                slot = self.pending_slot or 'primary'
                current[slot] = key_name
                self.status_message = f"{key_name.upper()}"
            else:
                section[self.pending_action] = key_name
                self.status_message = f"{key_name.upper()}"
            self.pending_action = None
            self.pending_slot = None
            self.waiting_for_key = False
            self._persist_controls()

    def _cycle_tab(self, delta):
        self.active_tab = (self.active_tab + delta) % len(get_control_tabs())
        self.selected_action = 0
        if not self._is_single_player_tab():
            self.binding_slot = 'primary'

    def _reset_active_tab(self):
        defaults = self._resolve_section(self.settings_manager.get_default_controls(), self._current_tab_key())
        section = self._resolve_section(self.control_config, self._current_tab_key())
        section.clear()
        section.update(defaults)
        self.status_message = t('control_tab_reset')
        self._persist_controls()

    def _revert_selected_binding(self):
        defaults = self._resolve_section(self.settings_manager.get_default_controls(), self._current_tab_key())
        section = self._resolve_section(self.control_config, self._current_tab_key())
        action_key = self._current_actions()[self.selected_action][0]
        if self._is_single_player_tab() and isinstance(defaults.get(action_key), dict):
            current = section.get(action_key)
            if not isinstance(current, dict):
                current = {'primary': current, 'secondary': ''}
                section[action_key] = current
            slot = self.binding_slot
            current[slot] = defaults[action_key].get(slot, '')
            self.status_message = t('menu_key_reset')
        else:
            section[action_key] = defaults[action_key]
            self.status_message = t('menu_key_reset')
        self._persist_controls()

    def _persist_controls(self):
        self.settings_manager.set('controls', self.control_config)
        self.control_config = self.settings_manager.get_controls()
        # Gamepad ayarları değiştiyse manager'a bildir
        try:
            from gamepad_manager import reload_gamepad_settings
            reload_gamepad_settings()
        except Exception:
            pass

    def _resolve_section(self, data, key):
        node = data
        for part in key.split('.'):
            node = node[part]
        return node

    def _format_key_label(self, value):
        if value is None:
            return '—'
        if isinstance(value, int):
            try:
                return pygame.key.name(value).upper()
            except ValueError:
                return str(value)
        return str(value).upper()



class HighScoreScreen:
    """High score ekranı - Kutucuklu grid görünüm"""
    
    # Desteklenen modlar, görünen isimleri ve renkleri
    MODES = [
        ('classic', 'mode_label_classic', (100, 200, 255)),
        ('sprint', 'mode_label_sprint', (255, 215, 0)),
        ('ultra', 'mode_label_ultra', (255, 50, 50)),
        ('zen', 'mode_label_zen', (100, 255, 200)),
        ('mystery', 'mode_label_card_mastery', (255, 150, 255)),
        ('survival', 'mode_label_survival', (255, 100, 150)),
        ('cascade', 'mode_label_cascade', (80, 150, 255)),
        ('wide', 'mode_label_wide', (100, 255, 255)),
        ('hardcore', 'mode_label_hardcore', (255, 80, 80)),
    ]
    
    def __init__(self, screen, score_manager, user_manager=None, steam_mode_scores=None):
        """High score ekranını başlat"""
        self.screen = screen
        self.score_manager = score_manager
        self.user_manager = user_manager
        self.steam_mode_scores = {} if steam_mode_scores is None else steam_mode_scores
        self.scroll_y = 0
        self.max_scroll = 0
        self.card_rects = []  # Kart hitbox'ları
        self.selected_card = 0
        # Menüyle aynı shared katman
        self.background_fx = get_shared_falling_blocks_layer('default')

    def handle_input(self, event):
        """Input işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.scroll_y = max(0, self.scroll_y - 60)
            elif event.key == pygame.K_DOWN:
                self.scroll_y = min(self.max_scroll, self.scroll_y + 60)
            elif event.key == pygame.K_ESCAPE:
                return 'back'
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - int(event.y) * 40))
    
    def draw(self):
        """High score ekranını çiz - Kutucuklu grid görünüm"""
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        retro_style.draw_title(self.screen, t('high_scores_title'), (width // 2, 50))

        # Grid parametreleri
        padding = 30
        cols = 3
        card_spacing = 20
        content_width = min(1200, width - padding * 2)
        content_x = (width - content_width) // 2
        card_width = (content_width - card_spacing * (cols - 1)) // cols
        card_height = 200
        
        content_top = 100
        visible_height = height - content_top - 60
        
        # Toplam yükseklik hesapla
        rows = (len(self.MODES) + cols - 1) // cols
        total_height = rows * (card_height + card_spacing)
        self.max_scroll = max(0, total_height - visible_height + 40)
        
        # Scroll'u clamp et
        self.scroll_y = max(0, min(self.max_scroll, self.scroll_y))
        
        # Clipping alanı oluştur
        clip_rect = pygame.Rect(0, content_top, width, visible_height)
        
        # Kartları çiz
        self.card_rects = []
        for i, (mode_key, mode_label_key, mode_color) in enumerate(self.MODES):
            col = i % cols
            row = i // cols
            
            x = content_x + col * (card_width + card_spacing)
            y = content_top + row * (card_height + card_spacing) - self.scroll_y
            
            card_rect = pygame.Rect(x, y, card_width, card_height)
            self.card_rects.append(card_rect)
            
            # Görünür mü kontrol et
            if y + card_height < content_top or y > height - 60:
                continue
            
            # Skorları al
            steam_scores = self.steam_mode_scores.get(mode_key, [])
            if steam_scores:
                scores = steam_scores[:3]
            elif self.user_manager:
                scores = self.user_manager.get_mode_highscores(mode_key, limit=3)
            else:
                scores = []
            
            self._draw_mode_card(card_rect, t(mode_label_key), mode_color, scores)
        
        # Alt bilgi
        hint_font = retro_style.get_font(16, bold=False)
        hint_text = t('high_scores_hint')
        hint_surf = hint_font.render(hint_text, True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(width // 2, height - 25)))
        
        # Scroll göstergesi
        if self.max_scroll > 0:
            self._draw_scroll_indicator(width - 25, content_top, 10, visible_height)
    
    def _draw_mode_card(self, rect, mode_name, mode_color, scores):
        """Mod kartını çiz"""
        # Kart arka planı
        card_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 25, 40, 220), card_surf.get_rect(), border_radius=12)
        self.screen.blit(card_surf, rect.topleft)
        
        # Çerçeve
        pygame.draw.rect(self.screen, mode_color, rect, 2, border_radius=12)
        
        # Üst başlık bandı
        header_height = 36
        header_rect = pygame.Rect(rect.x, rect.y, rect.width, header_height)
        header_surf = pygame.Surface((rect.width, header_height), pygame.SRCALPHA)
        pygame.draw.rect(header_surf, (*mode_color, 50), header_surf.get_rect(), 
                        border_top_left_radius=12, border_top_right_radius=12)
        self.screen.blit(header_surf, header_rect.topleft)
        
        # Mod ismi
        name_font = retro_style.get_font(18, bold=True)
        name_surf = name_font.render(mode_name, True, mode_color)
        self.screen.blit(name_surf, name_surf.get_rect(center=(rect.centerx, rect.y + header_height // 2)))
        
        # Skor listesi
        score_area_y = rect.y + header_height + 10
        score_area_h = rect.height - header_height - 15
        
        if not scores:
            # Skor yoksa mesaj
            no_score_font = retro_style.get_font(14, bold=False)
            no_score_surf = no_score_font.render(t('no_scores'), True, retro_style.text_muted)
            self.screen.blit(no_score_surf, no_score_surf.get_rect(center=(rect.centerx, score_area_y + score_area_h // 2)))
            return
        
        # Skorları göster (max 3)
        row_height = score_area_h // 3
        
        for i, entry in enumerate(scores[:3]):
            row_y = score_area_y + i * row_height
            
            # Sıra numarası
            rank_font = retro_style.get_font(16, bold=True)
            rank_color = mode_color if i == 0 else retro_style.text_secondary
            rank_text = f"#{i + 1}"
            rank_surf = rank_font.render(rank_text, True, rank_color)
            self.screen.blit(rank_surf, (rect.x + 15, row_y + row_height // 2 - rank_surf.get_height() // 2))
            
            # Skor
            score_val = entry.get('score', 0)
            score_text = f"{score_val:,}".replace(',', '.')
            score_font = retro_style.get_font(18, bold=True)
            score_color = (255, 255, 255) if i == 0 else retro_style.text_primary
            score_surf = score_font.render(score_text, True, score_color)
            self.screen.blit(score_surf, score_surf.get_rect(center=(rect.centerx, row_y + row_height // 2)))
            
            # Tarih (sağda, küçük)
            date_text = entry.get('date', '')[:10] if entry.get('date') else ''
            if date_text:
                date_font = retro_style.get_font(11, bold=False)
                date_surf = date_font.render(date_text, True, retro_style.text_muted)
                self.screen.blit(date_surf, (rect.right - date_surf.get_width() - 10, 
                                            row_y + row_height // 2 - date_surf.get_height() // 2))
            
            # Ayırıcı çizgi
            if i < len(scores) - 1:
                line_y = row_y + row_height - 1
                pygame.draw.line(self.screen, (*mode_color, 40), 
                               (rect.x + 15, line_y), (rect.right - 15, line_y), 1)
    
    def _draw_scroll_indicator(self, x, y, width, height):
        """Scroll göstergesini çiz"""
        if self.max_scroll <= 0:
            return
        
        # Track
        track_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (50, 60, 80), track_rect, border_radius=5)
        
        # Thumb
        thumb_height = max(30, height * height // (height + self.max_scroll))
        thumb_y = y + (self.scroll_y / self.max_scroll) * (height - thumb_height) if self.max_scroll > 0 else y
        thumb_rect = pygame.Rect(x, thumb_y, width, thumb_height)
        pygame.draw.rect(self.screen, retro_style.accent, thumb_rect, border_radius=5)




class AchievementScreen:
    """Başarılar ekranı"""
    
    def __init__(self, screen, achievement_manager):
        """Başarı ekranını başlat"""
        self.screen = screen
        self.achievement_manager = achievement_manager
        self._font_lang = None
        self.font_name = retro_style.get_font(30)
        self.font_desc = retro_style.get_font(20, bold=False)
        self.font_progress = retro_style.get_font(24)
        self._refresh_fonts_for_language(force=True)
        self.scroll_offset = 0
        # Menüyle aynı shared katman: ekran geçişlerinde animasyon kesilmesin.
        self.background_fx = get_shared_falling_blocks_layer('default')

    def _refresh_fonts_for_language(self, force: bool = False) -> None:
        """Aktif dile göre başarı ekranı fontlarını güncelle.

        CJK dillerinde özel font fallback kullanır; diğer dillerde retro_style fontlarına döner.
        """
        try:
            lang = get_language()
        except Exception:
            lang = 'en'

        if not force and self._font_lang == lang:
            return

        cjk_name = get_font_for_language(lang, 30)
        cjk_desc = get_font_for_language(lang, 20)
        cjk_progress = get_font_for_language(lang, 24)

        if cjk_name and cjk_desc and cjk_progress:
            self.font_name = cjk_name
            self.font_desc = cjk_desc
            self.font_progress = cjk_progress
        else:
            self.font_name = retro_style.get_font(30)
            self.font_desc = retro_style.get_font(20, bold=False)
            self.font_progress = retro_style.get_font(24)

        self._font_lang = lang
    
    def handle_input(self, event):
        """Input işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.scroll_offset = max(0, self.scroll_offset - 40)
            elif event.key == pygame.K_DOWN:
                self.scroll_offset += 40
            elif event.key == pygame.K_ESCAPE:
                return 'back'
        elif event.type == pygame.MOUSEWHEEL:
            # Mouse scroll desteği
            self.scroll_offset -= event.y * 40
            self.scroll_offset = max(0, self.scroll_offset)
        return None
    
    def draw(self):
        """Başarı ekranını çiz"""
        self._refresh_fonts_for_language()
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        title_rect = retro_style.draw_title(self.screen, t('achievements_title'), (width // 2, 70), emoji='☆')

        def _ellipsize(text: str, font: pygame.font.Font, max_width: int) -> str:
            if max_width <= 0:
                return ''
            if font.size(text)[0] <= max_width:
                return text
            ell = '...'
            # Fast path for tiny widths
            if font.size(ell)[0] > max_width:
                return ''
            trimmed = text
            while trimmed and font.size(trimmed + ell)[0] > max_width:
                trimmed = trimmed[:-1]
            return trimmed + ell

        def _draw_achievement_icon(slot_rect: pygame.Rect, achievement_id: str, unlocked: bool) -> None:
            """UI-safe başarı ikonu çiz. Önce Apple emoji PNG dene, yoksa vektörel fallback."""
            border = UIColors.NEON_CYAN if unlocked else UIColors.GLASS_BORDER[:3]
            alpha = 205 if unlocked else 165
            retro_style.draw_glass_panel(
                self.screen,
                slot_rect,
                alpha=alpha,
                border_color=border,
                glow=unlocked,
            )

            # PNG emoji dene
            from achievements import ACHIEVEMENTS as _ACH_DEFS
            ach_def = _ACH_DEFS.get(achievement_id)
            if ach_def:
                icon_char = ach_def.get('icon', '')
                if icon_char:
                    from emoji_renderer import emoji_surface
                    icon_size = max(16, min(slot_rect.width, slot_rect.height) - 14)
                    surf = emoji_surface(icon_char, icon_size)
                    if surf:
                        if not unlocked:
                            # Kilitli: yarı saydam + gri tonlama efekti
                            surf = surf.copy()
                            surf.set_alpha(120)
                        self.screen.blit(surf, surf.get_rect(center=slot_rect.center))
                        return

            # İç glyph rengi
            glyph = UIColors.NEON_CYAN if unlocked else (140, 150, 170)
            inner = slot_rect.inflate(-14, -14)
            if inner.width <= 0 or inner.height <= 0:
                return

            # Basit kategori çıkarımı
            if achievement_id.startswith('score_'):
                # 3 bar
                bar_w = max(2, inner.width // 6)
                gap = max(2, (inner.width - 3 * bar_w) // 2)
                heights = [inner.height * 0.45, inner.height * 0.7, inner.height * 0.95]
                x = inner.x
                for h in heights:
                    r = pygame.Rect(x, int(inner.bottom - h), bar_w, int(h))
                    pygame.draw.rect(self.screen, glyph, r, border_radius=3)
                    x += bar_w + gap
                return

            if achievement_id.startswith('lines_'):
                # 3 yatay çizgi
                line_h = max(2, inner.height // 6)
                gap = max(2, (inner.height - 3 * line_h) // 2)
                y = inner.y
                for _ in range(3):
                    r = pygame.Rect(inner.x, y, inner.width, line_h)
                    pygame.draw.rect(self.screen, glyph, r, border_radius=3)
                    y += line_h + gap
                return

            if achievement_id.startswith('tetris_') or achievement_id == 'first_tetris':
                # 4 blok (I-tetromino)
                block_gap = 2
                bw = max(3, (inner.width - 3 * block_gap) // 4)
                bh = max(3, min(inner.height, bw))
                y = inner.y + (inner.height - bh) // 2
                x = inner.x + (inner.width - (4 * bw + 3 * block_gap)) // 2
                for i in range(4):
                    r = pygame.Rect(x + i * (bw + block_gap), y, bw, bh)
                    pygame.draw.rect(self.screen, glyph, r, border_radius=3)
                return

            if achievement_id.startswith('level_'):
                # ok yukarı
                cx = inner.centerx
                top = inner.y
                bottom = inner.bottom
                stem_w = max(3, inner.width // 5)
                stem_h = max(6, inner.height // 2)
                stem = pygame.Rect(cx - stem_w // 2, bottom - stem_h, stem_w, stem_h)
                pygame.draw.rect(self.screen, glyph, stem, border_radius=3)
                arrow = [(cx, top), (inner.right, top + inner.height // 3), (inner.left, top + inner.height // 3)]
                pygame.draw.polygon(self.screen, glyph, arrow)
                return

            if achievement_id.startswith('games_') or achievement_id in ('first_game',):
                # play üçgeni
                tri = [(inner.left, inner.top), (inner.left, inner.bottom), (inner.right, inner.centery)]
                pygame.draw.polygon(self.screen, glyph, tri)
                return

            if achievement_id.startswith('combo_'):
                # zigzag
                pts = [
                    (inner.left, inner.top + inner.height * 0.25),
                    (inner.left + inner.width * 0.35, inner.top + inner.height * 0.55),
                    (inner.left + inner.width * 0.65, inner.top + inner.height * 0.35),
                    (inner.right, inner.top + inner.height * 0.7),
                ]
                pygame.draw.lines(self.screen, glyph, False, [(int(x), int(y)) for x, y in pts], 4)
                return

            if achievement_id.startswith('pvp_'):
                # X
                pygame.draw.line(self.screen, glyph, inner.topleft, inner.bottomright, 4)
                pygame.draw.line(self.screen, glyph, inner.bottomleft, inner.topright, 4)
                return

            # Varsayılan: küçük kare
            pygame.draw.rect(self.screen, glyph, inner, border_radius=4)

        # Skorlar ekranıyla aynı dar/ortalanmış içerik genişliği
        content_width = min(980, max(0, width - 240))
        content_x = (width - content_width) // 2

        progress = self.achievement_manager.get_progress()
        unlocked_count = len(self.achievement_manager.unlocked)
        total_count = len(self.achievement_manager.get_all_achievements())
        summary_rect = pygame.Rect(content_x, title_rect.bottom + 20, content_width, 150)
        retro_style.draw_panel(self.screen, summary_rect, title=t('progress'))

        progress_text_str = t('menu_achievements_progress', count=unlocked_count, total=total_count, percent=f'{progress:.1f}')
        progress_text = self.font_progress.render(
            progress_text_str,
            True,
            (220, 230, 240),
        )
        self.screen.blit(progress_text, progress_text.get_rect(midtop=(width // 2, summary_rect.y + 30)))

        bar_rect = pygame.Rect(summary_rect.x + 30, summary_rect.bottom - 60, summary_rect.width - 60, 26)
        pygame.draw.rect(self.screen, (26, 28, 52), bar_rect, border_radius=12)
        # Segment (tetromino blok) progress bar
        segment_count = 20
        inner = bar_rect.inflate(-8, -8)
        gap = 4
        total_gap = gap * (segment_count - 1)
        seg_w = max(2, (inner.width - total_gap) // segment_count)
        seg_h = inner.height
        filled_segments = int(round((progress / 100.0) * segment_count))
        filled_segments = max(0, min(segment_count, filled_segments))
        for idx in range(segment_count):
            x = inner.x + idx * (seg_w + gap)
            seg_rect = pygame.Rect(x, inner.y, seg_w, seg_h)
            seg_color = UIColors.NEON_CYAN if idx < filled_segments else (38, 44, 72)
            pygame.draw.rect(self.screen, seg_color, seg_rect, border_radius=6)
        pygame.draw.rect(self.screen, UIColors.NEON_CYAN, bar_rect, 2, border_radius=12)

        list_top = summary_rect.bottom + 20
        item_height = 92
        item_spacing = 14
        achievements = self.achievement_manager.get_all_achievements()
        total_content = len(achievements) * (item_height + item_spacing)
        visible_height = height - list_top - 140
        max_scroll = max(0, total_content - max(0, visible_height))
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        # Panellerin üst panele taşmasını ve alta çıkmasını engelle
        clip_rect = pygame.Rect(0, list_top, width, max(0, visible_height))
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        for i, ach in enumerate(achievements):
            y_pos = list_top + i * (item_height + item_spacing) - self.scroll_offset
            if y_pos < list_top - item_height or y_pos > height - 120:
                continue

            row_rect = pygame.Rect(content_x, y_pos, content_width, item_height)
            # Locked/Unlocked farkını ana neon/glass tema ile ver
            unlocked = bool(ach.get('unlocked'))
            row_alpha = 205 if unlocked else 170
            border_color = UIColors.NEON_CYAN if unlocked else UIColors.GLASS_BORDER[:3]
            retro_style.draw_glass_panel(
                self.screen,
                row_rect,
                alpha=row_alpha,
                border_color=border_color,
                glow=unlocked,
            )

            slot_rect = pygame.Rect(0, 0, 60, 60)
            slot_rect.center = (row_rect.x + 45, row_rect.centery)
            _draw_achievement_icon(slot_rect, str(ach.get('id', '')), unlocked)

            # Typography: daha temiz hiyerarşi + ellipsis
            right_info_pad = 220
            text_left = row_rect.x + 90
            text_max_w = max(0, row_rect.width - (text_left - row_rect.x) - right_info_pad)

            name_color = UIColors.NEON_CYAN if unlocked else (220, 225, 235)
            name_text = _ellipsize(str(ach.get('name', '')), self.font_name, text_max_w)
            name_surface = self.font_name.render(name_text, True, name_color)
            self.screen.blit(name_surface, (text_left, row_rect.y + 12))

            desc_color = (200, 210, 230) if unlocked else (150, 165, 190)
            desc_text = _ellipsize(str(ach.get('description', '')), self.font_desc, text_max_w)
            desc_surface = self.font_desc.render(desc_text, True, desc_color)
            self.screen.blit(desc_surface, (text_left, row_rect.y + 52))

            if ach['unlocked'] and ach['unlock_date']:
                date_surface = self.font_desc.render(ach['unlock_date'], True, (180, 255, 200))
                date_rect = date_surface.get_rect(right=row_rect.right - 20, centery=row_rect.centery)
                self.screen.blit(date_surface, date_rect)
            elif not ach.get('unlocked'):
                progress_text = ach.get('progress_text')
                if progress_text:
                    progress_surface = self.font_desc.render(progress_text, True, (160, 180, 210))
                    progress_rect = progress_surface.get_rect(
                        right=row_rect.right - 20,
                        centery=row_rect.centery,
                    )
                    self.screen.blit(progress_surface, progress_rect)

        self.screen.set_clip(prev_clip)

        # Scrollbar çiz — panellerin hemen dışına, sağ tarafa
        if total_content > visible_height:
            scrollbar_rect = pygame.Rect(
                content_x + content_width + 4,
                list_top,
                20,
                visible_height
            )
            retro_style.draw_scrollbar(
                self.screen,
                scrollbar_rect,
                self.scroll_offset,
                total_content,
                visible_height
            )



class ModeMusicScreen:
    """Per-mode music selection UI."""

    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font_title = retro_style.get_font(48)
        self.font_option = retro_style.get_font(30)
        self.font_value = retro_style.get_font(24)
        self.font_small = retro_style.get_font(20)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.modes = [
            ('campaign', t('music_campaign')),
            ('classic', t('music_classic')),
            ('daily', t('music_daily')),
            ('sprint', t('music_sprint')),
            ('ultra', t('music_ultra')),
            ('zen', t('music_zen')),
            ('tetris2', t('music_tetris2')),
            ('mystery', t('music_mystery')),
            ('wide', t('music_wide')),
            ('survival', t('music_survival')),
            ('cascade', t('music_cascade')),
            ('pvp', t('music_pvp')),
            ('hardcore', t('music_hardcore')),
        ]
        self.selected = 0
        self.scroll_offset = 0
        self.option_rects = []
        self.music_root = (ROOT_DIR / 'music').resolve()
        self.track_options = []
        self._rebuild_track_options()
        self._refresh_overrides()

        # Track picker overlay state
        self.picker_open = False
        self.picker_mode_key = None
        self.picker_selected = 0
        self.picker_scroll = 0
        self.picker_item_rects: list[tuple[pygame.Rect, int]] = []

    def _overlay_layout(self):
        width, height = self.screen.get_size()

        panel_w = min(860, width - 120)
        panel_h = min(560, height - 160)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        list_top = panel_rect.y + 86
        list_left = panel_rect.x + 18
        list_right = panel_rect.right - 18
        list_bottom = panel_rect.bottom - 60
        list_rect = pygame.Rect(list_left, list_top, list_right - list_left, list_bottom - list_top)

        # Keep enough vertical room for title + selected track label (sub_text)
        # so the overlay matches the Music Hub row style.
        item_h = 72
        gap = 10
        return panel_rect, list_rect, item_h, gap

    def _overlay_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self.modes) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _overlay_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.selected * (item_h + gap)
        if y < self.scroll_offset:
            self.scroll_offset = y
        elif y > self.scroll_offset + visible_h - item_h:
            self.scroll_offset = y - (visible_h - item_h)
        self.scroll_offset = max(0, min(self.scroll_offset, self._overlay_max_scroll(visible_h, item_h, gap)))

    def handle_input_overlay(self, event):
        """Handle input when used as an overlay/modal inside another screen.

        Returns:
            - 'close' when ESC or outside click
            - 'toggle_fullscreen' when F11 toggle requested
            - None otherwise
        """
        if self.picker_open:
            # Picker already behaves like an overlay.
            return self._handle_picker_input(event)

        panel_rect, list_rect, item_h, gap = self._overlay_layout()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'close'
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.modes)
                self._overlay_ensure_visible(list_rect.height, item_h, gap)
                return None
            if event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.modes)
                self._overlay_ensure_visible(list_rect.height, item_h, gap)
                return None
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._open_picker_for_selected_mode()
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._apply_track(self.modes[self.selected][0], None)
                return None
            if event.key == pygame.K_r:
                self._rebuild_track_options()
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self._overlay_max_scroll(list_rect.height, item_h, gap)))
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Outside click closes (like other modals)
            if not panel_rect.collidepoint(pos):
                return 'close'
            for idx, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = idx
                    self._open_picker(self.modes[idx][0])
                    return None
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = idx
                    self._apply_track(self.modes[idx][0], None)
                    return None

        return None

    def draw_overlay(self):
        """Draw a modal-style version of the ModeMusic screen."""
        width, height = self.screen.get_size()

        # Dim background
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_rect, list_rect, item_h, gap = self._overlay_layout()
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('mode_music'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        summary_text = t('custom_count').format(count=len(self.overrides))
        sub = subtitle_font.render(summary_text, True, (170, 190, 220))
        self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 50))

        # Clamp scroll + keep selection visible
        self.scroll_offset = max(0, min(self.scroll_offset, self._overlay_max_scroll(list_rect.height, item_h, gap)))
        self._overlay_ensure_visible(list_rect.height, item_h, gap)

        # List
        self.option_rects = []
        self.screen.set_clip(list_rect)
        for idx, (mode_key, label) in enumerate(self.modes):
            y = list_rect.y + idx * (item_h + gap) - self.scroll_offset
            if y + item_h < list_rect.y or y > list_rect.bottom:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue

            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.option_rects.append(r)

            selected = idx == self.selected
            value = self._current_value(mode_key)
            value_label = self._track_label_for_value(value)
            # Keep subtext short
            max_chars = 34
            if len(value_label) > max_chars:
                value_label = value_label[: max_chars - 3] + '...'

            color_code = retro_style.accent if value else retro_style.primary
            retro_style.draw_uniform_button(
                self.screen,
                r,
                label,
                sub_text=value_label,
                color_code=color_code,
                selected=selected,
            )

        self.screen.set_clip(None)

        # Scrollbar
        total_h = len(self.modes) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(panel_rect.right - 12, list_rect.y, 6, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.scroll_offset, total_h, list_rect.height)

        hint = subtitle_font.render(t('menu_theme_hint'), True, (140, 160, 190))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))

        if self.picker_open:
            self._draw_track_picker()

    def _refresh_overrides(self):
        self.overrides = self.settings_manager.get_mode_music_overrides()

    def _rebuild_track_options(self):
        # Include a "default" option (None) at the top
        def _normalize_name(value_or_label):
            if value_or_label is None:
                return ''
            raw = str(value_or_label)
            if raw.startswith('file:'):
                raw = raw[5:]
            try:
                raw = Path(raw).stem
            except Exception:
                pass
            raw = raw.replace('_', ' ').replace('-', ' ').strip().lower()
            return ''.join(ch for ch in raw if ch.isalnum())

        self.track_options = [{'label': t('track_default_label'), 'value': None}]
        seen_names = set()

        for label, value in BUILT_IN_TRACK_CHOICES:
            norm = _normalize_name(value or label)
            if norm:
                seen_names.add(norm)
            self.track_options.append({'label': label, 'value': value})

        for rel_path in self._scan_music_files():
            norm = _normalize_name(rel_path)
            if norm in seen_names:
                continue
            display_name = Path(rel_path).stem.replace('_', ' ').title()
            self.track_options.append({
                'label': f"{display_name} {t('track_file_suffix')}",
                'value': f"file:{rel_path}"
            })
            if norm:
                seen_names.add(norm)

    def _scan_music_files(self):
        if not self.music_root.exists():
            return []
        files = []
        for dirpath, _, filenames in os.walk(self.music_root):
            for filename in filenames:
                if Path(filename).suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS:
                    full_path = Path(dirpath) / filename
                    rel_path = full_path.relative_to(self.music_root).as_posix()
                    files.append(rel_path)
        return sorted(files)

    def _current_value(self, mode_key):
        return self.overrides.get(mode_key, None)

    def _track_label_for_value(self, value):
        for option in self.track_options:
            if option['value'] == value:
                return option['label']
        if value and value.startswith('file:'):
            return t('track_file_prefix', path=value[5:])
        if value:
            return value
        return t('track_default_label')

    def _apply_track(self, mode_key, value):
        self.settings_manager.set_mode_music_override(mode_key, value)
        self._refresh_overrides()

    def _open_picker_for_selected_mode(self):
        if not self.modes:
            return
        mode_key = self.modes[self.selected][0]
        self._open_picker(mode_key)

    def _open_picker(self, mode_key):
        self.picker_open = True
        self.picker_mode_key = mode_key
        self.picker_scroll = 0

        # Preselect currently active track
        current = self._current_value(mode_key)
        idx = 0
        for i, option in enumerate(self.track_options):
            if option['value'] == current:
                idx = i
                break
        self.picker_selected = idx

    def _close_picker(self):
        self.picker_open = False
        self.picker_mode_key = None
        self.picker_item_rects = []

    def _picker_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self.track_options) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _picker_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.picker_selected * (item_h + gap)
        if y < self.picker_scroll:
            self.picker_scroll = y
        elif y > self.picker_scroll + visible_h - item_h:
            self.picker_scroll = y - (visible_h - item_h)
        self.picker_scroll = max(0, min(self.picker_scroll, self._picker_max_scroll(visible_h, item_h, gap)))

    def _handle_picker_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_picker()
                return None
            if event.key == pygame.K_UP:
                self.picker_selected = (self.picker_selected - 1) % len(self.track_options)
                return None
            if event.key == pygame.K_DOWN:
                self.picker_selected = (self.picker_selected + 1) % len(self.track_options)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.picker_mode_key is not None:
                    chosen = self.track_options[self.picker_selected]['value']
                    self._apply_track(self.picker_mode_key, chosen)
                self._close_picker()
                return None
            if event.key == pygame.K_r:
                self._rebuild_track_options()
                # Keep selection in bounds
                self.picker_selected = max(0, min(self.picker_selected, len(self.track_options) - 1))
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.picker_scroll -= event.y * 36
            # Clamp later in draw (needs visible height). Keep non-negative here.
            self.picker_scroll = max(0, self.picker_scroll)
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.picker_item_rects:
                if rect.collidepoint(pos):
                    self.picker_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                # click on an item selects
                for rect, idx in self.picker_item_rects:
                    if rect.collidepoint(pos):
                        self.picker_selected = idx
                        if self.picker_mode_key is not None:
                            chosen = self.track_options[self.picker_selected]['value']
                            self._apply_track(self.picker_mode_key, chosen)
                        self._close_picker()
                        return None
                # click outside closes
                self._close_picker()
                return None

        return None

    def _cycle_track(self, mode_key, step):
        if not self.track_options:
            return
        current = self._current_value(mode_key)
        current_idx = 0
        for idx, option in enumerate(self.track_options):
            if option['value'] == current:
                current_idx = idx
                break
        new_idx = (current_idx + step) % len(self.track_options)
        self._apply_track(mode_key, self.track_options[new_idx]['value'])

    def _ensure_visible(self):
        width, height = self.screen.get_size()
        start_y = 150
        spacing = 92
        item_y = start_y + self.selected * spacing - self.scroll_offset
        visible_height = max(0, height - start_y - 200)
        if item_y < start_y:
            self.scroll_offset -= start_y - item_y
        elif item_y > start_y + visible_height - 80:
            self.scroll_offset += item_y - (start_y + visible_height - 80)
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

    def _max_scroll(self):
        height = self.screen.get_height()
        start_y = 150
        spacing = 92
        visible_height = max(0, height - start_y - 220)
        total_height = len(self.modes) * spacing
        return max(0, total_height - max(visible_height, 0))

    def handle_input(self, event):
        if self.picker_open:
            return self._handle_picker_input(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.modes)
                self._ensure_visible()
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.modes)
                self._ensure_visible()
            elif event.key == pygame.K_LEFT:
                self._open_picker_for_selected_mode()
            elif event.key == pygame.K_RIGHT:
                self._open_picker_for_selected_mode()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._apply_track(self.modes[self.selected][0], None)
            elif event.key == pygame.K_r:
                self._rebuild_track_options()
            elif event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = idx
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = idx
                    if event.button in (1, 3):
                        self._open_picker(self.modes[idx][0])
                    elif event.button == 2:
                        self._apply_track(self.modes[idx][0], None)
                    break
        return None

    def _draw_track_picker(self):
        width, height = self.screen.get_size()

        # Dim background
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_w = min(720, width - 120)
        panel_h = min(520, height - 160)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('menu_music_select'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        if self.picker_mode_key:
            mode_label = None
            for k, lbl in self.modes:
                if k == self.picker_mode_key:
                    mode_label = lbl
                    break
            if mode_label:
                sub = subtitle_font.render(mode_label, True, (170, 190, 220))
                self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 50))

        # List area
        list_top = panel_rect.y + 86
        list_left = panel_rect.x + 18
        list_right = panel_rect.right - 18
        list_bottom = panel_rect.bottom - 60
        list_rect = pygame.Rect(list_left, list_top, list_right - list_left, list_bottom - list_top)

        item_h = 44
        gap = 8
        self.picker_item_rects = []

        # Clamp scroll
        self.picker_scroll = max(0, min(self.picker_scroll, self._picker_max_scroll(list_rect.height, item_h, gap)))
        self._picker_ensure_visible(list_rect.height, item_h, gap)

        self.screen.set_clip(list_rect)
        for idx, option in enumerate(self.track_options):
            y = list_rect.y + idx * (item_h + gap) - self.picker_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue

            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.picker_item_rects.append((r, idx))

            selected = idx == self.picker_selected
            bg = (35, 55, 90, 220) if selected else (18, 24, 40, 170)
            border = retro_style.accent if selected else (60, 70, 90)
            pygame.draw.rect(self.screen, bg, r, border_radius=10)
            pygame.draw.rect(self.screen, border, r, 2 if selected else 1, border_radius=10)

            text_font = retro_style.get_font(22, bold=selected)
            label = option['label']
            txt = text_font.render(label, True, (255, 255, 255) if selected else (205, 215, 235))
            self.screen.blit(txt, (r.x + 14, r.y + (r.height - txt.get_height()) // 2))

        self.screen.set_clip(None)

        # Scrollbar
        total_h = len(self.track_options) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(panel_rect.right - 12, list_rect.y, 6, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.picker_scroll, total_h, list_rect.height)

        # Footer hints
        hint = subtitle_font.render(t('menu_music_hint'), True, (140, 160, 190))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))

    def draw(self):
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)

        # ── Panel (ayarlar ekranı stiliyle aynı) ──
        pw = min(1200, max(700, int(width * 0.88)))
        ph = min(850, max(500, int(height * 0.88)))
        px = (width - pw) // 2
        py = (height - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)

        # Gölge
        shadow = pygame.Surface((pw + 10, ph + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 60), shadow.get_rect(), border_radius=16)
        self.screen.blit(shadow, (px + 5, py + 5))
        # Arka plan
        panel_surf = pygame.Surface(panel.size, pygame.SRCALPHA)
        panel_surf.fill((12, 16, 32, 235))
        for yy in range(min(30, ph // 4)):
            alpha = int(15 * (1 - yy / 30))
            pygame.draw.line(panel_surf, (255, 255, 255, alpha), (0, yy), (pw, yy))
        self.screen.blit(panel_surf, panel.topleft)
        pygame.draw.rect(self.screen, (60, 70, 100), panel, 2, border_radius=14)
        pygame.draw.line(self.screen, (80, 140, 220), (px + 2, py + 1), (px + pw - 2, py + 1), 1)

        # ── Başlık (panel içinde) ──
        title_font = retro_style.get_font(36)
        title_text = t('track_title')
        title_surf = title_font.render(title_text, True, (220, 235, 255))
        self.screen.blit(title_surf, (px + 24, py + 14))

        # Başlık altı çizgi
        pygame.draw.line(self.screen, (50, 60, 90), (px + 14, py + 56), (px + pw - 14, py + 56), 1)

        # ── Özet bilgi chip ──
        summary_text = t('track_summary', count=len(self.overrides))
        chip_font = self.font_small
        chip_surf = chip_font.render(summary_text, True, (200, 230, 255))
        chip_w = chip_surf.get_width() + 40
        chip_rect = pygame.Rect(px + 24, py + 64, chip_w, 32)
        chip_bg = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
        chip_bg.fill((30, 40, 60, 180))
        self.screen.blit(chip_bg, chip_rect.topleft)
        pygame.draw.rect(self.screen, (60, 80, 110), chip_rect, 1, border_radius=14)
        self.screen.blit(chip_surf, (chip_rect.x + 20, chip_rect.centery - chip_surf.get_height() // 2))

        # ── İçerik alanı ──
        content_top = py + 104
        content_bottom = py + ph - 18
        content_left = px + 18
        content_width = pw - 36
        list_visible_h = content_bottom - content_top

        item_height = 72
        spacing = 10

        self.option_rects = []

        clip_rect = pygame.Rect(content_left, content_top, content_width, list_visible_h)
        self.screen.set_clip(clip_rect)

        for idx, (mode_key, label) in enumerate(self.modes):
            y_pos = content_top + idx * (item_height + spacing) - self.scroll_offset

            if y_pos + item_height < content_top or y_pos > content_bottom:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue

            item_rect = pygame.Rect(content_left + 8, y_pos, content_width - 16, item_height)
            self.option_rects.append(item_rect)

            is_selected = idx == self.selected

            # Satır arka planı (ayarlar paneli stili)
            bg_alpha = 180 if is_selected else 130
            bg_color = (28, 38, 60) if is_selected else (18, 24, 42)
            row_surf = pygame.Surface(item_rect.size, pygame.SRCALPHA)
            row_surf.fill((*bg_color, bg_alpha))
            if is_selected:
                for ry in range(min(8, item_rect.height // 4)):
                    a = int(15 * (1 - ry / 8))
                    pygame.draw.line(row_surf, (255, 255, 255, a), (0, ry), (item_rect.width, ry))
            self.screen.blit(row_surf, item_rect.topleft)

            if is_selected:
                pygame.draw.rect(self.screen, (80, 160, 255, 180), item_rect, 1, border_radius=6)
            else:
                pygame.draw.rect(self.screen, (40, 50, 70), item_rect, 1, border_radius=6)

            # Sol ikon
            icon_rect = pygame.Rect(item_rect.x + 16, item_rect.centery - 20, 40, 40)
            icon_bg = pygame.Surface(icon_rect.size, pygame.SRCALPHA)
            icon_bg.fill((15, 20, 30, 200))
            self.screen.blit(icon_bg, icon_rect.topleft)
            pygame.draw.rect(self.screen, (50, 60, 85), icon_rect, 1, border_radius=6)
            note_char = ">" if not is_selected else ">>"
            icon_font = retro_style.get_font(20)
            icon_surf = icon_font.render(note_char, True, (80, 160, 255) if is_selected else (100, 120, 150))
            self.screen.blit(icon_surf, icon_surf.get_rect(center=icon_rect.center))

            # Mod ismi
            title_color = (255, 255, 255) if is_selected else (190, 200, 215)
            title_font = retro_style.get_fitting_font(label, 22, item_rect.width // 2, bold=True)
            title_surf = title_font.render(label, True, title_color)
            self.screen.blit(title_surf, (item_rect.x + 70, item_rect.y + 12))

            # Müzik değeri
            value = self._current_value(mode_key)
            value_label = self._track_label_for_value(value)

            val_color = (100, 200, 255) if value else (150, 160, 180)

            val_font = self.font_value
            max_val_width = item_rect.width - 200
            final_val_label = value_label
            if val_font.size(value_label)[0] > max_val_width:
                while val_font.size(final_val_label + "...")[0] > max_val_width and len(final_val_label) > 0:
                    final_val_label = final_val_label[:-1]
                final_val_label += "..."

            val_surf = val_font.render(final_val_label, True, val_color)
            self.screen.blit(val_surf, (item_rect.x + 70, item_rect.y + 40))

            # Sağ ok (seçiliyse)
            if is_selected:
                arrow_font = retro_style.get_font(20, bold=True)
                arrow_color = (80, 160, 255)
                arrow_r = arrow_font.render('>', True, arrow_color)
                self.screen.blit(arrow_r, (item_rect.right - 30, item_rect.centery - arrow_r.get_height() // 2))

        self.screen.set_clip(None)

        # Scrollbar
        total_h = len(self.modes) * (item_height + spacing)
        if total_h > list_visible_h:
            sb_rect = pygame.Rect(px + pw - 24, content_top, 5, list_visible_h)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.scroll_offset, total_h, list_visible_h)

        if self.picker_open:
            self._draw_track_picker()


class MusicSettingsScreen:
    """Müzik ayarları ekranı - playlist tabanlı yönetim."""

    def __init__(self, screen, settings_manager, sound_manager=None):
        self.screen = screen
        self.settings_manager = settings_manager
        self.sound_manager = sound_manager

        self.font_title = retro_style.get_font(46)
        self.font_option = retro_style.get_font(28, bold=True)
        self.font_value = retro_style.get_font(22)
        self.font_small = retro_style.get_font(18)
        self.background_fx = get_shared_falling_blocks_layer('default')

        self.view = 'main'  # main | mode_select | playlist
        self.selected = 0
        self.scroll_offset = 0
        self.main_item_rects: list[tuple[pygame.Rect, int]] = []

        self.modes = [
            ('campaign', t('music_campaign')),
            ('classic', t('music_classic')),
            ('daily', t('music_daily')),
            ('sprint', t('music_sprint')),
            ('ultra', t('music_ultra')),
            ('zen', t('music_zen')),
            ('tetris2', t('music_tetris2')),
            ('mystery', t('music_mystery')),
            ('wide', t('music_wide')),
            ('survival', t('music_survival')),
            ('cascade', t('music_cascade')),
            ('pvp', t('music_pvp')),
            ('hardcore', t('music_hardcore')),
        ]
        self.mode_selected = 0
        self.mode_scroll = 0
        self.mode_item_rects: list[tuple[pygame.Rect, int]] = []

        self.music_root = (ROOT_DIR / 'music').resolve()
        self.track_options = []
        self._rebuild_track_options()

        self.playlist_target = None  # menu | game | campaign | mode
        self.playlist_mode_key = None
        self.playlist = []
        self.playlist_selected = 0
        self.playlist_scroll = 0
        self.playlist_item_rects: list[tuple[pygame.Rect, int]] = []

        self.picker_open = False
        self.picker_selected = 0
        self.picker_scroll = 0
        self.picker_item_rects: list[tuple[pygame.Rect, int]] = []

    def _main_items(self):
        menu_list = self.settings_manager.get_menu_music_playlist() if self.settings_manager else []
        game_list = self.settings_manager.get_game_music_playlist() if self.settings_manager else []
        campaign_list = self.settings_manager.get_campaign_music_playlist() if self.settings_manager else []
        mode_lists = self.settings_manager.get_mode_music_playlists() if self.settings_manager else {}
        return [
            ('menu', t('menu_music'), f"{len(menu_list)} parça"),
            ('game', t('game_music'), f"{len(game_list)} parça"),
            ('campaign', t('music_campaign'), f"{len(campaign_list)} parça"),
            ('mode', t('mode_music_label'), f"{len(mode_lists)} liste"),
            ('back', t('back'), ''),
        ]

    def _scan_music_files(self):
        if not self.music_root.exists():
            return []
        files = []
        for dirpath, _, filenames in os.walk(self.music_root):
            for filename in filenames:
                if Path(filename).suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS:
                    full_path = Path(dirpath) / filename
                    rel_path = full_path.relative_to(self.music_root).as_posix()
                    files.append(rel_path)
        return sorted(files)

    def _rebuild_track_options(self):
        options = []
        seen_values = set()
        seen_names = set()

        def _normalize_name(value_or_label):
            if value_or_label is None:
                return ''
            raw = str(value_or_label)
            if raw.startswith('file:'):
                raw = raw[5:]
            try:
                raw = Path(raw).stem
            except Exception:
                pass
            raw = raw.replace('_', ' ').replace('-', ' ').strip().lower()
            return ''.join(ch for ch in raw if ch.isalnum())

        if self.sound_manager:
            try:
                tracks = self.sound_manager.get_available_tracks()
                for track_info in tracks.get('external', []):
                    name = track_info.get('name', '')
                    if not name:
                        continue
                    value = str(name)
                    if value in seen_values:
                        continue
                    seen_values.add(value)
                    norm = _normalize_name(value)
                    if norm:
                        seen_names.add(norm)
                    label = value.replace('_', ' ').title()
                    options.append({'label': label, 'value': value})
            except Exception:
                pass

        for rel_path in self._scan_music_files():
            value = f"file:{rel_path}"
            if value in seen_values:
                continue
            norm = _normalize_name(rel_path)
            if norm in seen_names:
                continue
            seen_values.add(value)
            display_name = Path(rel_path).stem.replace('_', ' ').title()
            options.append({'label': f"{display_name} (dosya)", 'value': value})
            if norm:
                seen_names.add(norm)

        self.track_options = options

    def _label_for_value(self, value):
        for option in self.track_options:
            if option['value'] == value:
                return option['label']
        if value and isinstance(value, str) and value.startswith('file:'):
            return f"Dosya: {value[5:]}"
        return str(value)

    def _load_playlist(self, target, mode_key=None):
        self.playlist_target = target
        self.playlist_mode_key = mode_key
        if not self.settings_manager:
            self.playlist = []
            return

        if target == 'menu':
            self.playlist = list(self.settings_manager.get_menu_music_playlist())
        elif target == 'game':
            self.playlist = list(self.settings_manager.get_game_music_playlist())
        elif target == 'campaign':
            self.playlist = list(self.settings_manager.get_campaign_music_playlist())
        else:
            self.playlist = list(self.settings_manager.get_mode_music_playlist(mode_key))

        self.playlist_selected = 0
        self.playlist_scroll = 0

    def _save_playlist(self):
        if not self.settings_manager:
            return None
        if self.playlist_target == 'menu':
            self.settings_manager.set_menu_music_playlist(self.playlist)
            return 'menu_playlist_changed'
        if self.playlist_target == 'game':
            self.settings_manager.set_game_music_playlist(self.playlist)
            return 'game_playlist_changed'
        if self.playlist_target == 'campaign':
            self.settings_manager.set_campaign_music_playlist(self.playlist)
            return 'campaign_playlist_changed'
        if self.playlist_target == 'mode' and self.playlist_mode_key:
            self.settings_manager.set_mode_music_playlist(self.playlist_mode_key, self.playlist)
            return 'mode_playlist_changed'
        return None

    def _list_max_scroll(self, total_items, item_h, gap, visible_h):
        total_h = total_items * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _ensure_visible(self, selected, item_h, gap, visible_h, scroll_value):
        y = selected * (item_h + gap)
        if y < scroll_value:
            scroll_value = y
        elif y > scroll_value + visible_h - item_h:
            scroll_value = y - (visible_h - item_h)
        max_scroll = self._list_max_scroll(max(1, selected + 1), item_h, gap, visible_h)
        return max(0, min(scroll_value, max_scroll))

    def _open_picker(self):
        self.picker_open = True
        self.picker_selected = 0
        self.picker_scroll = 0
        self.picker_item_rects = []

    def _close_picker(self):
        self.picker_open = False
        self.picker_item_rects = []

    def handle_input(self, event):
        if self.picker_open:
            return self._handle_picker_input(event)

        if self.view == 'main':
            return self._handle_main_input(event)
        if self.view == 'mode_select':
            return self._handle_mode_input(event)
        if self.view == 'playlist':
            return self._handle_playlist_input(event)
        return None

    def _handle_main_input(self, event):
        items = self._main_items()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(items)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                key = items[self.selected][0]
                if key == 'menu':
                    self._load_playlist('menu')
                    self.view = 'playlist'
                elif key == 'game':
                    self._load_playlist('game')
                    self.view = 'playlist'
                elif key == 'campaign':
                    self._load_playlist('campaign')
                    self.view = 'playlist'
                elif key == 'mode':
                    self.view = 'mode_select'
                elif key == 'back':
                    return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.main_item_rects:
                if rect.collidepoint(pos):
                    self.selected = idx
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.main_item_rects:
                if rect.collidepoint(pos):
                    self.selected = idx
                    key = items[self.selected][0]
                    if key == 'menu':
                        self._load_playlist('menu')
                        self.view = 'playlist'
                    elif key == 'game':
                        self._load_playlist('game')
                        self.view = 'playlist'
                    elif key == 'campaign':
                        self._load_playlist('campaign')
                        self.view = 'playlist'
                    elif key == 'mode':
                        self.view = 'mode_select'
                    elif key == 'back':
                        return 'back'
                    break
        return None

    def _handle_mode_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.view = 'main'
                return None
            if event.key == pygame.K_UP:
                self.mode_selected = (self.mode_selected - 1) % len(self.modes)
            elif event.key == pygame.K_DOWN:
                self.mode_selected = (self.mode_selected + 1) % len(self.modes)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                mode_key = self.modes[self.mode_selected][0]
                self._load_playlist('mode', mode_key)
                self.view = 'playlist'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.mode_scroll -= event.y * 30
            self.mode_scroll = max(0, self.mode_scroll)

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.mode_item_rects:
                if rect.collidepoint(pos):
                    self.mode_selected = idx
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.mode_item_rects:
                if rect.collidepoint(pos):
                    self.mode_selected = idx
                    mode_key = self.modes[self.mode_selected][0]
                    self._load_playlist('mode', mode_key)
                    self.view = 'playlist'
                    break

        return None

    def _handle_playlist_input(self, event):
        total_items = len(self.playlist) + 1  # +1: Ekle
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.view = 'mode_select' if self.playlist_target == 'mode' else 'main'
                return None
            if event.key == pygame.K_UP:
                self.playlist_selected = (self.playlist_selected - 1) % total_items
            elif event.key == pygame.K_DOWN:
                self.playlist_selected = (self.playlist_selected + 1) % total_items
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.playlist_selected == 0:
                    self._open_picker()
            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.playlist_selected > 0:
                    idx = self.playlist_selected - 1
                    if 0 <= idx < len(self.playlist):
                        del self.playlist[idx]
                        self.playlist_selected = max(0, min(self.playlist_selected, len(self.playlist)))
                        return self._save_playlist()
            elif event.key == pygame.K_LEFT:
                if self.playlist_selected > 1:
                    idx = self.playlist_selected - 1
                    self.playlist[idx - 1], self.playlist[idx] = self.playlist[idx], self.playlist[idx - 1]
                    self.playlist_selected -= 1
                    return self._save_playlist()
            elif event.key == pygame.K_RIGHT:
                idx = self.playlist_selected - 1
                if 0 <= idx < len(self.playlist) - 1:
                    self.playlist[idx + 1], self.playlist[idx] = self.playlist[idx], self.playlist[idx + 1]
                    self.playlist_selected += 1
                    return self._save_playlist()
            elif event.key == pygame.K_r:
                self._rebuild_track_options()
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.playlist_scroll -= event.y * 30
            self.playlist_scroll = max(0, self.playlist_scroll)

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.playlist_item_rects:
                if rect.collidepoint(pos):
                    self.playlist_selected = idx
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.playlist_item_rects:
                if rect.collidepoint(pos):
                    self.playlist_selected = idx
                    if idx == 0:
                        self._open_picker()
                    break

        return None

    def _handle_picker_input(self, event):
        if not self.track_options:
            self._close_picker()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_picker()
                return None
            if event.key == pygame.K_UP:
                self.picker_selected = (self.picker_selected - 1) % len(self.track_options)
            elif event.key == pygame.K_DOWN:
                self.picker_selected = (self.picker_selected + 1) % len(self.track_options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                chosen = self.track_options[self.picker_selected]
                self.playlist.append(chosen['value'])
                self._close_picker()
                return self._save_playlist()
            elif event.key == pygame.K_r:
                self._rebuild_track_options()
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.picker_scroll -= event.y * 36
            self.picker_scroll = max(0, self.picker_scroll)

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.picker_item_rects:
                if rect.collidepoint(pos):
                    self.picker_selected = idx
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.picker_item_rects:
                if rect.collidepoint(pos):
                    self.picker_selected = idx
                    chosen = self.track_options[self.picker_selected]
                    self.playlist.append(chosen['value'])
                    self._close_picker()
                    return self._save_playlist()

        return None

    def draw(self):
        width, height = self.screen.get_size()

        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        self._title_rect = retro_style.draw_title(self.screen, t('tracks'), (width // 2, 70), emoji='🎵')

        if self.view == 'main':
            self._draw_main()
        elif self.view == 'mode_select':
            self._draw_mode_select()
        elif self.view == 'playlist':
            self._draw_playlist()

        if self.picker_open:
            self._draw_picker()

    def _draw_main(self):
        width, height = self.screen.get_size()
        title_rect = getattr(self, '_title_rect', None)
        start_y = (title_rect.bottom + 40) if title_rect else 150

        card_width = min(620, width - 120)
        card_height = 74
        spacing = 92

        items = self._main_items()
        self.main_item_rects = []
        for idx, (key, label, value) in enumerate(items):
            r = pygame.Rect((width - card_width) // 2, start_y + idx * spacing, card_width, card_height)
            self.main_item_rects.append((r, idx))
            selected = idx == self.selected
            strip_color = (112, 160, 255)
            kind = 'submenu'
            if key == 'mode':
                strip_color = retro_style.accent
            if key == 'back':
                strip_color = (255, 100, 120)
                kind = 'default'
            retro_style.draw_setting_row(
                self.screen,
                r,
                label,
                value,
                selected=selected,
                label_color=(255, 255, 255) if selected else (200, 200, 200),
                value_color=(150, 200, 255),
                strip_color=strip_color,
                kind=kind,
            )


    def _draw_mode_select(self):
        width, height = self.screen.get_size()
        title_rect = getattr(self, '_title_rect', None)
        start_y = (title_rect.bottom + 40) if title_rect else 150

        card_width = min(620, width - 120)
        item_h = 74
        gap = 12
        list_rect = pygame.Rect((width - card_width) // 2, start_y, card_width, height - start_y - 120)
        self.mode_item_rects = []

        self.mode_scroll = max(0, min(self.mode_scroll, self._list_max_scroll(len(self.modes), item_h, gap, list_rect.height)))

        self.screen.set_clip(list_rect)
        for idx, (mode_key, label) in enumerate(self.modes):
            y = list_rect.y + idx * (item_h + gap) - self.mode_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue
            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.mode_item_rects.append((r, idx))

            selected = idx == self.mode_selected
            retro_style.draw_setting_row(
                self.screen,
                r,
                label,
                '',
                selected=selected,
                label_color=(255, 255, 255) if selected else (200, 200, 200),
                value_color=(150, 200, 255),
                strip_color=(100, 220, 150),
                kind='selector',
            )

        self.screen.set_clip(None)


    def _draw_playlist(self):
        width, height = self.screen.get_size()
        title_rect = getattr(self, '_title_rect', None)
        start_y = (title_rect.bottom + 40) if title_rect else 150

        card_width = min(620, width - 120)
        item_h = 74
        gap = 12
        list_rect = pygame.Rect((width - card_width) // 2, start_y, card_width, height - start_y - 120)
        total_items = len(self.playlist) + 1
        self.playlist_item_rects = []

        self.playlist_scroll = max(0, min(self.playlist_scroll, self._list_max_scroll(total_items, item_h, gap, list_rect.height)))

        self.screen.set_clip(list_rect)
        for idx in range(total_items):
            y = list_rect.y + idx * (item_h + gap) - self.playlist_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue
            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.playlist_item_rects.append((r, idx))

            selected = idx == self.playlist_selected
            if idx == 0:
                label = t('playlist_add')
                value = ''
                strip_color = (100, 220, 150)
                kind = 'submenu'
            else:
                value = self.playlist[idx - 1]
                label = self._label_for_value(value)
                value = ''
                strip_color = (112, 160, 255)
                kind = 'default'

            retro_style.draw_setting_row(
                self.screen,
                r,
                label,
                value,
                selected=selected,
                label_color=(255, 255, 255) if selected else (200, 200, 200),
                value_color=(150, 200, 255),
                strip_color=strip_color,
                kind=kind,
            )

        self.screen.set_clip(None)


    def _draw_picker(self):
        width, height = self.screen.get_size()

        # Dim background
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        self.screen.blit(dim, (0, 0))

        panel_w = min(720, width - 140)
        panel_h = min(520, height - 180)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('menu_music_select'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        # List area inside modal
        list_top = panel_rect.y + 70
        list_left = panel_rect.x + 18
        list_right = panel_rect.right - 18
        list_bottom = panel_rect.bottom - 24
        list_rect = pygame.Rect(list_left, list_top, list_right - list_left, list_bottom - list_top)

        item_h = 64
        gap = 10
        self.picker_item_rects = []

        self.picker_scroll = max(0, min(self.picker_scroll, self._list_max_scroll(len(self.track_options), item_h, gap, list_rect.height)))

        self.screen.set_clip(list_rect)
        for idx, option in enumerate(self.track_options):
            y = list_rect.y + idx * (item_h + gap) - self.picker_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue
            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.picker_item_rects.append((r, idx))

            selected = idx == self.picker_selected
            retro_style.draw_setting_row(
                self.screen,
                r,
                option['label'],
                '',
                selected=selected,
                label_color=(255, 255, 255) if selected else (200, 200, 200),
                value_color=(150, 200, 255),
                strip_color=(112, 160, 255),
                kind='selector',
            )

        self.screen.set_clip(None)


class BackgroundSelectorScreen:
    """Arka plan seçici ekranı - Her oyun modu için ayrı arka plan seçimi"""
    
    def __init__(self, screen, settings_manager):
        """Arka plan seçici ekranını başlat"""
        self.screen = screen
        self.settings_manager = settings_manager
        self.font_title = retro_style.get_font(46)
        self.font_option = retro_style.get_font(28)
        self.font_small = retro_style.get_font(20, bold=False)

        # Arka plan efektleri (ayar ekranları ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        self.options = [
            'bg_show',
            'bg_transparency',
            'bg_main',
            'bg_single',
            'bg_outer',
            'bg_pvp_main',
            'bg_pvp_board',
            'bg_wide',
            'bg_back'
        ]
        self.selected = 0
        self.option_rects = []
        
        # Arka plan ayarlarını yükle
        self.background_enabled = settings_manager.get('background_enabled', True)
        self.transparency = settings_manager.get('bg_transparency', 0.3)  # 0.25, 0.5, 0.75, 1.0
        self.backgrounds = {
            'main': settings_manager.get('bg_main', None),
            'single': settings_manager.get('bg_single', None),
            'outer': settings_manager.get('bg_outer', None),
            'pvp_main': settings_manager.get('bg_pvp_main', None),
            'pvp_board': settings_manager.get('bg_pvp_board', None),
            'wide': settings_manager.get('bg_wide', None),
        }
        
        # Cache için değişkenler
        self._cached_background = None
        self._cached_size = None

        # UI/layout/value caches
        self._layout_cache_size = None
        self._panel_rect = None
        self._value_cache_key = None
        self._value_cache = {}

        # For item mapping
        self._bg_keys = [None, None, 'main', 'single', 'outer', 'pvp_main', 'pvp_board', 'wide', None]
    
    def invalidate_cache(self):
        """Cache'i temizle (ekran boyutu değiştiğinde kullan)"""
        self._cached_background = None
        self._cached_size = None
        self._layout_cache_size = None
        self._panel_rect = None
        self._value_cache_key = None
        self._value_cache = {}

    def _sync_from_settings_manager(self) -> None:
        if not self.settings_manager:
            return
        changed = False
        try:
            enabled = bool(self.settings_manager.get('background_enabled', True))
            if enabled != self.background_enabled:
                self.background_enabled = enabled
                changed = True
        except Exception:
            pass

        try:
            trans = float(self.settings_manager.get('bg_transparency', 0.3))
            if abs(trans - float(self.transparency)) > 1e-6:
                self.transparency = trans
                changed = True
        except Exception:
            pass

        mapping = {
            'main': 'bg_main',
            'single': 'bg_single',
            'outer': 'bg_outer',
            'pvp_main': 'bg_pvp_main',
            'pvp_board': 'bg_pvp_board',
            'wide': 'bg_wide',
        }
        for k, skey in mapping.items():
            try:
                v = self.settings_manager.get(skey, None)
            except Exception:
                v = self.backgrounds.get(k)
            if self.backgrounds.get(k) != v:
                self.backgrounds[k] = v
                changed = True

        if changed:
            self._value_cache_key = None
            self._value_cache = {}

    def _ensure_layout(self, width: int, height: int) -> None:
        if self._layout_cache_size == (width, height) and self._panel_rect is not None and self.option_rects:
            return

        panel_w = min(760, width - 120)
        # Fit buttons nicely even on short windows
        panel_h = min(720, height - 220)
        panel_x = (width - panel_w) // 2
        panel_y = 140
        if panel_y + panel_h > height - 90:
            panel_y = max(110, (height - panel_h) // 2)
        self._panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        pad = 18
        card_h = 64
        gap = 12
        start_y = self._panel_rect.y + pad
        card_w = self._panel_rect.width - pad * 2
        self.option_rects = []
        for i in range(len(self.options)):
            y = start_y + i * (card_h + gap)
            r = pygame.Rect(self._panel_rect.x + pad, y, card_w, card_h)
            self.option_rects.append(r)

        self._layout_cache_size = (width, height)

    def _compute_value_cache_key(self):
        bgs = tuple((k, self.backgrounds.get(k)) for k in ('main', 'single', 'outer', 'pvp_main', 'pvp_board', 'wide'))
        return (bool(self.background_enabled), float(self.transparency), bgs)

    def _get_option_display(self, i: int):
        key = self._compute_value_cache_key()
        if key != self._value_cache_key:
            self._value_cache_key = key
            self._value_cache = {}

        if i in self._value_cache:
            return self._value_cache[i]

        sub_text = None
        checked = False
        color_code = 'graphics'

        if i == 0:
            sub_text = t('on') if self.background_enabled else t('off')
            checked = bool(self.background_enabled)
            color_code = 'toggle'
        elif i == 1:
            trans_percent = int(round(float(self.transparency) * 100))
            sub_text = f'< %{trans_percent} >'
            color_code = 'selector'
        elif i < 8 and self._bg_keys[i]:
            bg_key = self._bg_keys[i]
            bg_path = self.backgrounds.get(bg_key)
            if bg_path and os.path.exists(bg_path):
                filename = os.path.basename(bg_path)
                if len(filename) > 34:
                    filename = filename[:31] + '...'
                sub_text = filename
                checked = True
            else:
                sub_text = t('bg_default')
                checked = False
            color_code = 'submenu'
        else:
            sub_text = None
            checked = False
            color_code = 'default'

        self._value_cache[i] = (sub_text, checked, color_code)
        return self._value_cache[i]
    
    def _get_background_surface(self, width, height):
        """Arka plan surface'ini cache'le"""
        if self._cached_background is None or self._cached_size != (width, height):
            # Gradient arka plan oluştur
            bg_surface = pygame.Surface((width, height))
            for i in range(height):
                color_r = int(5 + (i / height) * 5)
                color_g = int(5 + (i / height) * 5)
                color_b = int(10 + (i / height) * 10)
                pygame.draw.line(bg_surface, (color_r, color_g, color_b), (0, i), (width, i))
            
            self._cached_background = bg_surface
            self._cached_size = (width, height)
        
        return self._cached_background
    
    def handle_input(self, event):
        """Girdi işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                # Transparanlık ayarı için ok tuşları
                if self.selected == 1:
                    transparency_values = [0.25, 0.5, 0.75, 1.0]
                    current_idx = transparency_values.index(self.transparency) if self.transparency in transparency_values else 1
                    if event.key == pygame.K_RIGHT:
                        current_idx = (current_idx + 1) % len(transparency_values)
                    else:
                        current_idx = (current_idx - 1) % len(transparency_values)
                    self.transparency = transparency_values[current_idx]
                    self.settings_manager.set('bg_transparency', self.transparency)
                    return 'change_transparency'
            elif event.key == pygame.K_RETURN:
                if self.selected == 0:
                    # Arka Plan Göster toggle
                    self.background_enabled = not self.background_enabled
                    self.settings_manager.set('background_enabled', self.background_enabled)
                    return 'toggle_background'
                elif self.selected == 2:
                    return 'select_bg_main'
                elif self.selected == 3:
                    return 'select_bg_single'
                elif self.selected == 4:
                    return 'select_bg_outer'
                elif self.selected == 5:
                    return 'select_bg_pvp_main'
                elif self.selected == 6:
                    return 'select_bg_pvp_board'
                elif self.selected == 7:
                    return 'select_bg_wide'
                elif self.selected == 8:
                    return 'back'
            elif event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
            elif event.key == pygame.K_DELETE:
                # Seçili arka planı sil (ilk 2 seçenek hariç)
                if self.selected == 2:
                    self.backgrounds['main'] = None
                    self.settings_manager.set('bg_main', None)
                    print("🗑️ Ana arka plan silindi")
                elif self.selected == 3:
                    self.backgrounds['single'] = None
                    self.settings_manager.set('bg_single', None)
                    print("🗑️ Tek oyuncu arka planı silindi")
                elif self.selected == 4:
                    self.backgrounds['outer'] = None
                    self.settings_manager.set('bg_outer', None)
                    print("🗑️ Dış alan arka planı silindi")
                elif self.selected == 5:
                    self.backgrounds['pvp_main'] = None
                    self.settings_manager.set('bg_pvp_main', None)
                    print("🗑️ PvP ana arka plan silindi")
                elif self.selected == 6:
                    self.backgrounds['pvp_board'] = None
                    self.settings_manager.set('bg_pvp_board', None)
                    print("🗑️ PvP oyun alanı arka planı silindi")
                elif self.selected == 7:
                    self.backgrounds['wide'] = None
                    self.settings_manager.set('bg_wide', None)
                    print("🗑️ Geniş mod arka planı silindi")
        
        # Mouse kontrolü
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Sol tık
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        if i == 0:
                            # Toggle background enabled
                            self.background_enabled = not self.background_enabled
                            self.settings_manager.set('background_enabled', self.background_enabled)
                            return 'toggle_background'
                        elif i == 2:
                            return 'select_bg_main'
                        elif i == 3:
                            return 'select_bg_single'
                        elif i == 4:
                            return 'select_bg_outer'
                        elif i == 5:
                            return 'select_bg_pvp_main'
                        elif i == 6:
                            return 'select_bg_pvp_board'
                        elif i == 7:
                            return 'select_bg_wide'
                        elif i == 8:
                            return 'back'
        
        return None
    
    def draw(self):
        """Arka plan seçici ekranını çiz - OPTİMİZE EDİLDİ"""
        width, height = self.screen.get_size()

        # Keep local state in sync (file selection happens in main loop)
        self._sync_from_settings_manager()

        # Ana tema arkaplanı
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        
        # Title - use shared retro_style draw_title for consistency
        title_rect = retro_style.draw_title(self.screen, t('bg_title'), (width // 2, 70), emoji='🖼️')
        

        # Panel + seçenekler
        self._ensure_layout(width, height)
        if self._panel_rect:
            retro_style.draw_glass_panel(self.screen, self._panel_rect, alpha=160, border_color=retro_style.primary)

        for i, option in enumerate(self.options):
            is_selected = i == self.selected
            card_rect = self.option_rects[i]
            sub_text, checked, color_code = self._get_option_display(i)

            label = t(option)

            retro_style.draw_uniform_button(
                self.screen,
                card_rect,
                label,
                sub_text=sub_text,
                state='hover' if is_selected else 'normal',
                color_code=color_code,
                selected=is_selected,
                checked=checked,
            )


class BlockStyleSettingsScreen:
    """Blok renkleri ve doku seçim ekranı."""

    def __init__(self, screen, theme_manager, settings_manager):
        self.screen = screen
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
        self.block_style_manager = BlockStyleManager(settings_manager)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.piece_names = list(ALL_PIECE_NAMES)
        self.selected = 0
        self.scroll_offset = 0
        self.option_rects = []
        self.font_title = retro_style.get_font(46)
        self.font_option = retro_style.get_font(28)
        self.font_small = retro_style.get_font(20, bold=False)
        self.mode = 'block_styles'
        self.mode_labels = {
            'block_styles': 'block_style_mode_block',
            'custom_theme': 'block_style_mode_custom'
        }
        self.custom_theme_colors = self._read_custom_theme_colors()
        self._sync_custom_theme_colors()
        self.placement_mode = False

        # Mouse çift tık ile renk seçimi
        self._last_click_ms = 0
        self._last_click_index = None
        self._double_click_ms = 350

        # Mouse çift tık ile renk seçimi
        self._last_click_ms = 0
        self._last_click_index = None
        self._double_click_ms = 350

    def _switch_active_theme_to_custom(self):
        """Blok görünümü rengi değişince aktif temayı Özel Tema'ya geçir.

        Not: Mevcut Özel Tema renklerini değiştirmez; sadece seçili temayı değiştirir.
        """
        if self.settings_manager:
            self.settings_manager.set('theme', CUSTOM_THEME_NAME)
        if self.theme_manager:
            self.theme_manager.set_theme(CUSTOM_THEME_NAME)

    def _base_color(self, piece_name):
        return get_piece_base_color(piece_name, self.theme_manager)

    @staticmethod
    def _clamp_channel(value):
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError):
            return 0

    def _read_custom_theme_colors(self):
        if not self.settings_manager:
            return {}
        raw = self.settings_manager.get('custom_theme_colors', {}) or {}
        parsed = {}
        for name, color in raw.items():
            if name in ALL_PIECE_NAMES and isinstance(color, (list, tuple)) and len(color) == 3:
                parsed[name] = tuple(self._clamp_channel(c) for c in color)
        return parsed

    def _sync_custom_theme_colors(self):
        latest = self._read_custom_theme_colors()
        if latest != self.custom_theme_colors:
            self.custom_theme_colors = latest
            if self.theme_manager:
                self.theme_manager.update_custom_theme(self.custom_theme_colors, persist=False)

    def _save_custom_theme_colors(self):
        if not self.settings_manager:
            if self.theme_manager:
                self.theme_manager.update_custom_theme(self.custom_theme_colors, persist=False)
            return
        serializable = {name: list(color) for name, color in self.custom_theme_colors.items()}
        self.settings_manager.set('custom_theme_colors', serializable)
        if self.theme_manager:
            self.theme_manager.update_custom_theme(self.custom_theme_colors, persist=False)

    def _get_custom_theme_color(self, piece_name):
        return self.custom_theme_colors.get(piece_name, self._base_color(piece_name))

    def _get_display_color(self, piece_name):
        if self.mode == 'custom_theme':
            return self._get_custom_theme_color(piece_name)
        return self.block_style_manager.get_color(piece_name, self._base_color(piece_name))

    def _clamp_scroll(self):
        card_spacing = 90
        height = self.screen.get_height()
        visible = max(0, height - 220)
        max_scroll = max(0, len(self.piece_names) * card_spacing - visible)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def _move_selection(self, delta):
        self.selected = (self.selected + delta) % len(self.piece_names)
        self._ensure_visible()

    def _ensure_visible(self):
        card_spacing = 90
        start_y = 160
        item_y = start_y + self.selected * card_spacing - self.scroll_offset
        height = self.screen.get_height()
        if item_y < 140:
            self.scroll_offset -= 140 - item_y
        elif item_y > height - 160:
            self.scroll_offset += item_y - (height - 160)
        self._clamp_scroll()

    def _choose_color(self):
        piece_name = self.piece_names[self.selected]
        fallback = self._base_color(piece_name)
        current = self._get_display_color(piece_name)
        from color_picker import pygame_color_picker
        chosen = pygame_color_picker(self.screen, initial_color=current, piece_name=piece_name)
        if chosen:
            color = (chosen[0], chosen[1], chosen[2])
            if self.mode == 'custom_theme':
                self.custom_theme_colors[piece_name] = color
                self._save_custom_theme_colors()
                self._switch_active_theme_to_custom()
                print(f"🎨 {piece_name} {CUSTOM_THEME_NAME} rengini {color} olarak ayarladı")
            else:
                self.block_style_manager.set_color(piece_name, color)
                self._switch_active_theme_to_custom()
                print(f"🎨 {piece_name} rengi güncellendi: {color}")

    def _reset_color(self):
        piece_name = self.piece_names[self.selected]
        if self.mode == 'custom_theme':
            if piece_name in self.custom_theme_colors:
                self.custom_theme_colors.pop(piece_name, None)
                self._save_custom_theme_colors()
            print(f"↩️ {piece_name} {CUSTOM_THEME_NAME} rengini varsayılan temaya döndürdü")
        else:
            self.block_style_manager.reset_color(piece_name)
            print(f"↩️ {piece_name} rengi varsayılan temaya döndü")

    def _reset_all_to_theme(self):
        # Clear all block style customizations and custom theme colors
        self.block_style_manager.reset_all()
        self.custom_theme_colors.clear()
        self._save_custom_theme_colors()
        if self.settings_manager:
            # Also clear the block_styles in settings so defaults from theme are used
            self.settings_manager.set('block_styles', {})
        print(t('block_style_reset_all_log'))

    def _draw_icon_button(self, rect, icon_type, is_selected):
        # Hover check
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = rect.collidepoint(mouse_pos)
        
        # Background
        bg_color = (60, 80, 100) if is_hovered else (40, 50, 70)
        border_color = (120, 140, 180) if is_hovered else (70, 80, 100)
        
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=8)
        pygame.draw.rect(self.screen, border_color, rect, 1, border_radius=8)
        
        # Text Label
        center = rect.center
        label_text = ""
        text_color = (255, 255, 255) if is_hovered else (200, 200, 200)
        
        if icon_type == 'edit':
            label_text = t('block_style_btn_custom')
            text_color = (130, 200, 255) if is_hovered else (100, 150, 255)
        elif icon_type == 'reset':
            label_text = t('block_style_btn_default')
            text_color = (255, 180, 100) if is_hovered else (200, 140, 80)
            
        font = retro_style.get_font(14, bold=False)
        txt = font.render(label_text, True, text_color)
        self.screen.blit(txt, txt.get_rect(center=center))

    def draw(self):
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        title_rect = retro_style.draw_title(self.screen, t('panel_block_styles'), (width // 2, 70), emoji='🎨')
        # Başlığın altındaki tuş ipuçları kaldırıldı (mouse odaklı kullanım)

        self._sync_custom_theme_colors()

        self.option_rects = []
        self.color_edit_buttons = []
        self.color_reset_buttons = []
        
        start_y = title_rect.bottom + 40
        card_width = min(780, width - 120)
        card_height = 78
        card_spacing = 92
        snapshot = self.block_style_manager.get_style_snapshot()

        for i, piece_name in enumerate(self.piece_names):
            y_pos = start_y + i * card_spacing - self.scroll_offset
            if y_pos < 140 or y_pos > height - 140:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue
            card_x = (width - card_width) // 2
            card_rect = pygame.Rect(card_x, y_pos, card_width, card_height)
            is_selected = i == self.selected

            # Kart arkaplanı
            if is_selected:
                glow = pygame.Surface((card_width + 16, card_height + 16), pygame.SRCALPHA)
                pygame.draw.rect(glow, (120, 200, 255, 90), glow.get_rect(), border_radius=14)
                self.screen.blit(glow, (card_x - 8, y_pos - 8))
                pygame.draw.rect(self.screen, (70, 90, 110), card_rect, border_radius=12)
                pygame.draw.rect(self.screen, retro_style.accent, card_rect, 3, border_radius=12)
            else:
                panel = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
                panel.fill((40, 50, 70, 210))
                self.screen.blit(panel, (card_x, y_pos))
                pygame.draw.rect(self.screen, (100, 120, 150), card_rect, 1, border_radius=12)

            display_color = self._get_display_color(piece_name)
            display_color = self._get_display_color(piece_name)
            sub_text = f"#{display_color[0]:02x}{display_color[1]:02x}{display_color[2]:02x}"

            retro_style.draw_uniform_button(
                self.screen,
                card_rect,
                piece_name,
                sub_text=sub_text,
                state='hover' if is_selected else 'normal',
                color_code='graphics',
                selected=is_selected,
                checked=False,
                preview_color=display_color,
            )
            style = snapshot.get(piece_name, {}) if self.mode == 'block_styles' else {}
            preview_rect = pygame.Rect(card_x + card_width - 130, y_pos + 10, 110, card_height - 20)

            # Özel Renk ve Sıfırlama Butonları
            if self.mode == 'block_styles':
                btn_h = 28
                btn_w_custom = 60
                btn_w_reset = 80
                
                # Butonları kartın alt kenarına hizalı fakat metin hizasında konumla
                btn_y = card_rect.bottom - btn_h - 18
                
                # Edit (Özel) - Preview'in solunda
                edit_btn_x = preview_rect.left - btn_w_custom - 15
                edit_btn_rect = pygame.Rect(edit_btn_x, btn_y, btn_w_custom, btn_h)
                self._draw_icon_button(edit_btn_rect, 'edit', is_selected)
                self.color_edit_buttons.append((edit_btn_rect, i))
                
                # Reset (Varsayılan) - Edit butonunun solunda
                reset_btn_x = edit_btn_rect.left - btn_w_reset - 10
                reset_btn_rect = pygame.Rect(reset_btn_x, btn_y, btn_w_reset, btn_h)
                self._draw_icon_button(reset_btn_rect, 'reset', is_selected)
                self.color_reset_buttons.append((reset_btn_rect, i))
            
            self._draw_piece_preview(piece_name, display_color, preview_rect, is_selected)

            self.option_rects.append(card_rect)

        # Scrollbar çiz
        visible_height = height - start_y - 140
        total_content = len(self.piece_names) * card_spacing
        if total_content > visible_height:
            scrollbar_rect = pygame.Rect(
                (width + card_width) // 2 + 20,
                start_y,
                12,
                visible_height
            )
            retro_style.draw_scrollbar(
                self.screen,
                scrollbar_rect,
                self.scroll_offset,
                total_content,
                visible_height
            )

    def _draw_piece_preview(self, piece_name, color, rect, selected):
        preview_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel_color = (30, 38, 55, 210)
        preview_surface.fill(panel_color)
        shape = PIECE_PREVIEW_SHAPES.get(piece_name)
        if shape:
            min_x = min(x for x, _ in shape)
            max_x = max(x for x, _ in shape)
            min_y = min(y for _, y in shape)
            max_y = max(y for _, y in shape)
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            cell_size = max(8, min((rect.width - 20) // width, (rect.height - 20) // height))
            offset_x = (rect.width - cell_size * width) // 2
            offset_y = (rect.height - cell_size * height) // 2
            for x, y in shape:
                px = (x - min_x) * cell_size + offset_x
                py = (y - min_y) * cell_size + offset_y
                draw_jelly_block(preview_surface, px, py, cell_size, color)
        else:
            box = preview_surface.get_rect().inflate(-18, -18)
            size = max(8, min(box.width, box.height))
            x = box.centerx - size // 2
            y = box.centery - size // 2
            draw_jelly_block(preview_surface, x, y, size, color)

        border_color = retro_style.accent if selected else (90, 110, 150)
        pygame.draw.rect(preview_surface, border_color, preview_surface.get_rect(), 2, border_radius=12)
        self.screen.blit(preview_surface, rect)

    def _mode_footer_lines(self):
        if self.mode == 'block_styles':
            return [
                t('block_style_footer_line1_block'),
                t('block_style_footer_line2_block')
            ]
        return [
            t(
                'block_style_footer_line1_custom',
                theme=self.theme_manager.theme_name if self.theme_manager else t('theme_label_fallback'),
            ),
            t('block_style_footer_line2_custom', theme=CUSTOM_THEME_NAME)
        ]

    def _toggle_mode(self):
        self.mode = 'custom_theme' if self.mode == 'block_styles' else 'block_styles'
        label_key = self.mode_labels.get(self.mode, '')
        label = t(label_key, default='') if label_key else ''
        if self.mode == 'custom_theme':
            label = label.format(theme=CUSTOM_THEME_NAME)
        print(t('block_style_mode_changed_log').format(mode=label))

    def _copy_from_current_theme(self):
        if not self.theme_manager:
            return
        source_colors = self.theme_manager.current_theme.pieces_colors
        self.custom_theme_colors = {
            name: source_colors.get(name, self._base_color(name))
            for name in self.piece_names
        }
        self._save_custom_theme_colors()
        print(t('block_style_copy_log').format(source=self.theme_manager.theme_name, target=CUSTOM_THEME_NAME))


    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            # Mouse ile seçilebilen öğeler için ok/enter gibi tuş ataması yok.
            # Geri / tam ekran / mod değiştir gibi global aksiyonlar kalsın.
            if event.key == pygame.K_TAB:
                self._toggle_mode()
            elif event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
            elif event.key == pygame.K_r:
                # SHIFT+R: tümünü sıfırla; R: seçiliyi sıfırla
                if hasattr(event, 'mod') and event.mod & pygame.KMOD_SHIFT:
                    self._reset_all_to_theme()
                else:
                    self._reset_color()
            elif event.key == pygame.K_c and self.mode == 'custom_theme':
                self._copy_from_current_theme()
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self._clamp_scroll()
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                
                # Check color edit/reset buttons (Block Styles Mode)
                if self.mode == 'block_styles':
                    for rect, idx in self.color_edit_buttons:
                        if rect.collidepoint(mouse_pos):
                            self.selected = idx
                            self._choose_color()
                            return None
                    for rect, idx in self.color_reset_buttons:
                        if rect.collidepoint(mouse_pos):
                            self.selected = idx
                            self._reset_color()
                            return None

                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected = i
                        now_ms = pygame.time.get_ticks()
                        if self._last_click_index == i and (now_ms - self._last_click_ms) <= self._double_click_ms:
                            self._choose_color()
                            self._last_click_index = None
                            self._last_click_ms = 0
                        else:
                            self._last_click_index = i
                            self._last_click_ms = now_ms
                        break
        return None

class BlockWorkshopScreen:
    def __init__(self, screen, settings_manager, theme_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.theme_manager = theme_manager
        self.block_style_manager = BlockStyleManager(settings_manager)
        self.font_title = retro_style.get_font(46)
        self.font_option = retro_style.get_font(26)
        self.font_small = retro_style.get_font(20, bold=False)
        self.board_width = 10
        self.board_height = 20
        self.available_modes = WORKSHOP_MODES
        self.piece_names = list(ALL_PIECE_NAMES)
        self.board = self._empty_board()
        self.sets = []
        self.active_set_id = None
        self.set_chip_rects = []
        self.package_action_rects = []
        self.set_mode_dialog = False
        self.set_mode_focus = 0
        self.set_mode_tag_rects = []
        self._load_sets_from_settings()
        self.board = self._load_board()
        self.cursor_x = self.board_width // 2
        self.cursor_y = self.board_height // 2
        self.selected_piece = 0
        self.rotation = 0
        self.message = ''
        self.message_timer = 0
        self.last_board_rect = pygame.Rect(0, 0, 0, 0)
        self.last_cell_size = 24
        self.manager_open = False
        self.manager_selected = 0
        self.manager_scroll = 0
        self.manager_mode_focus = 0
        self.saved_block_items = []
        self._refresh_manager_items(reset_selection=True)

    def save_on_exit(self):
        """Persist current workshop edits when the screen is being closed."""
        try:
            self._save_board(auto=True)
        except Exception:
            # Best effort: never block app shutdown.
            return

    def refresh_styles(self):
        self.block_style_manager = BlockStyleManager(self.settings_manager)

    def reload_from_settings(self):
        self._load_sets_from_settings()
        self.board = self._load_board()
        self.set_mode_dialog = False
        if self.manager_open:
            self.manager_items = self._build_manager_items()
            self.manager_selected = 0
            self.manager_scroll = 0
            self.manager_mode_focus = 0

    def handle_input(self, event):
        if self.set_mode_dialog:
            return self._handle_set_mode_input(event)
        if self.manager_open:
            return self._handle_manager_input(event)
        if event.type == pygame.KEYDOWN:
            mods = getattr(event, 'mod', pygame.key.get_mods())
            if event.key == pygame.K_ESCAPE:
                self._save_board(auto=True)
                return 'back'
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                self._save_board(auto=True)
                return 'toggle_fullscreen'
            # Save (Ctrl/Cmd+S). Keep Shift+S for backwards compatibility.
            if event.key == pygame.K_s and (is_primary_modifier(mods) or (mods & pygame.KMOD_SHIFT)):
                self._save_board()
                return None
            if event.key == pygame.K_LEFTBRACKET:
                self._cycle_sets(-1)
            elif event.key == pygame.K_RIGHTBRACKET:
                self._cycle_sets(1)
            elif event.key == pygame.K_F2:
                self._rename_active_set()
            elif event.key == pygame.K_n and is_primary_modifier(mods):
                self._create_new_set(copy_current=False)
                return None
            elif event.key == pygame.K_d and is_primary_modifier(mods):
                self._create_new_set(copy_current=True)
                return None
            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and is_primary_modifier(mods):
                self._delete_active_set()
                return None
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._move_cursor(-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._move_cursor(1, 0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._move_cursor(0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move_cursor(0, 1)
            elif event.key == pygame.K_TAB:
                self._cycle_piece(1)
            elif event.key in (pygame.K_p,):
                self._cycle_piece(1)
            elif event.key in (pygame.K_o,):
                self._cycle_piece(-1)
            elif event.key == pygame.K_q:
                self._rotate_piece(-1)
            elif event.key == pygame.K_e:
                self._rotate_piece(1)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._stamp_piece()
            elif event.key == pygame.K_BACKSPACE:
                self._erase_cell(self.cursor_x, self.cursor_y)
            elif event.key in (pygame.K_DELETE, pygame.K_c):
                self._clear_board()
            elif event.key == pygame.K_l:
                self.reload_from_settings()
                self._set_message(t('block_workshop_message_loaded'))
            elif event.key == pygame.K_r:
                self.rotation = 0
            elif event.key == pygame.K_k:
                self._choose_cell_color(self.cursor_x, self.cursor_y, reset=bool(mods & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_m:
                if is_primary_modifier(mods):
                    self._open_set_mode_dialog()
                else:
                    self._enter_manager()
            elif event.key == pygame.K_HOME:
                self.cursor_x = 0
                self.cursor_y = 0
            elif event.key == pygame.K_END:
                self.cursor_x = self.board_width - 1
                self.cursor_y = self.board_height - 1
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            cell = self._pos_to_cell(pos)
            if cell:
                self.cursor_x, self.cursor_y = cell
                if event.button == 1:
                    self._paint_cell(*cell)
                elif event.button == 3:
                    self._erase_cell(*cell)
        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0] or event.buttons[2]:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                cell = self._pos_to_cell(pos)
                if cell:
                    self.cursor_x, self.cursor_y = cell
                    if event.buttons[0]:
                        self._paint_cell(*cell)
                    elif event.buttons[2]:
                        self._erase_cell(*cell)
        return None

    def draw(self):
        """Modern Blok Atölyesi UI'ı çiz"""
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        
        # Başlık
        title_rect = retro_style.draw_title(self.screen, t('block_workshop_title'), (width // 2, 60), emoji='🧱')
        
        # Tip text - glass panel içinde
        tip_text = t('block_workshop_tip')
        tip_font = retro_style.get_font(16, bold=False)
        tip = tip_font.render(tip_text, True, (170, 190, 220))
        tip_rect = tip.get_rect(center=(width // 2, title_rect.bottom + 18))
        self.screen.blit(tip, tip_rect)

        # Aktif paket bilgisi
        active = self._get_active_set()
        meta_bottom = tip_rect.bottom
        if active:
            # Paket chip
            chip_font = retro_style.get_font(15, bold=True)
            from emoji_renderer import emoji_surface as _es
            _pkg_icon = _es('📦', 18)
            _chip_label = chip_font.render(f" {active['name']}", True, retro_style.primary)
            if _pkg_icon:
                chip_surf = pygame.Surface((18 + _chip_label.get_width(), max(18, _chip_label.get_height())), pygame.SRCALPHA)
                chip_surf.blit(_pkg_icon, (0, (chip_surf.get_height() - 18) // 2))
                chip_surf.blit(_chip_label, (18, (chip_surf.get_height() - _chip_label.get_height()) // 2))
            else:
                chip_surf = chip_font.render(f"📦 {active['name']}", True, retro_style.primary)
            chip_rect = chip_surf.get_rect(center=(width // 2, tip_rect.bottom + 20))
            
            # Chip background
            chip_bg_rect = chip_rect.inflate(24, 10)
            chip_bg = pygame.Surface(chip_bg_rect.size, pygame.SRCALPHA)
            chip_bg.fill((20, 30, 55, 180))
            self.screen.blit(chip_bg, chip_bg_rect.topleft)
            pygame.draw.rect(self.screen, (*retro_style.primary, 150), chip_bg_rect, 1, border_radius=chip_bg_rect.height // 2)
            self.screen.blit(chip_surf, chip_rect)
            meta_bottom = chip_bg_rect.bottom + 8

        # Board alanı hesaplama
        board_area_width = max(220, width - 380)
        board_area_height = max(220, height - meta_bottom - 180)
        cell_size = max(16, min(board_area_width // self.board_width, board_area_height // self.board_height))
        board_pixel_width = cell_size * self.board_width
        board_pixel_height = cell_size * self.board_height
        board_rect = pygame.Rect(50, meta_bottom + 20, board_pixel_width, board_pixel_height)
        self.last_board_rect = board_rect
        self.last_cell_size = cell_size

        # Board container - glass panel
        container_rect = board_rect.inflate(20, 20)
        retro_style.draw_glass_panel(self.screen, container_rect, alpha=150, border_color=(60, 80, 120))
        
        # Board çiz
        self._draw_board_cells(board_rect, cell_size)
        self._draw_preview(board_rect, cell_size)
        self._draw_cursor(board_rect, cell_size)

        # Side panel - palet ve kontroller
        side_rect = pygame.Rect(board_rect.right + 30, board_rect.top - 10, width - board_rect.right - 80, board_rect.height + 20)
        if side_rect.width > 140:
            retro_style.draw_glass_panel(self.screen, side_rect, alpha=160, border_color=retro_style.primary)
            self._draw_side_panel(side_rect)

        # Alt kontrol paneli
        footer_rect = pygame.Rect(40, height - 100, width - 80, 75)
        retro_style.draw_glass_panel(self.screen, footer_rect, alpha=140, border_color=(50, 70, 100))
        
        instructions = [
            t('block_workshop_instructions_line1'),
            t('block_workshop_instructions_line2', modifier=get_modifier_key_name()),
        ]
        inst_font = retro_style.get_font(14, bold=False)
        for idx, text in enumerate(instructions):
            info = inst_font.render(text, True, (160, 180, 210))
            self.screen.blit(info, info.get_rect(center=(width // 2, footer_rect.y + 20 + idx * 22)))

        # Mesaj gösterimi
        if self.message_timer > 0:
            msg_font = retro_style.get_font(18, bold=True)
            note = msg_font.render(self.message, True, retro_style.accent)
            note_rect = note.get_rect(center=(width // 2, footer_rect.bottom - 12))
            self.screen.blit(note, note_rect)
            self.message_timer -= 1

        # Overlay'ler
        if self.manager_open:
            self._draw_manager_overlay(width, height)
        if self.set_mode_dialog:
            self._draw_set_mode_overlay(width, height)

    def _draw_board_cells(self, board_rect, cell_size):
        """Board hücrelerini modern gradient stilinde çiz"""
        for y in range(self.board_height):
            for x in range(self.board_width):
                rect = pygame.Rect(board_rect.x + x * cell_size, board_rect.y + y * cell_size, cell_size, cell_size)
                
                # Hafif grid çizgisi
                grid_color = (30, 40, 65, 80)
                pygame.draw.rect(self.screen, (25, 32, 55), rect, 1)
                
                cell = self.board[y][x]
                if cell:
                    color = self._get_cell_color(cell)
                    inner = rect.inflate(-3, -3)
                    
                    # Gradient effect - üst kısım daha açık
                    pygame.draw.rect(self.screen, color, inner, border_radius=4)
                    
                    # Üst highlight
                    highlight_rect = pygame.Rect(inner.x + 2, inner.y + 1, inner.width - 4, inner.height // 3)
                    highlight_color = (min(color[0] + 50, 255), min(color[1] + 50, 255), min(color[2] + 50, 255), 60)
                    highlight_surf = pygame.Surface(highlight_rect.size, pygame.SRCALPHA)
                    highlight_surf.fill(highlight_color)
                    self.screen.blit(highlight_surf, highlight_rect.topleft)

    def _draw_cursor(self, board_rect, cell_size):
        """Neon glow cursor çiz"""
        rect = pygame.Rect(
            board_rect.x + self.cursor_x * cell_size,
            board_rect.y + self.cursor_y * cell_size,
            cell_size,
            cell_size,
        )
        
        # Dış glow
        glow_rect = rect.inflate(6, 6)
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (*retro_style.accent, 50), glow_surf.get_rect(), border_radius=4)
        self.screen.blit(glow_surf, glow_rect.topleft)
        
        # İç kenar
        pygame.draw.rect(self.screen, retro_style.accent, rect, 2, border_radius=2)

    def _draw_preview(self, board_rect, cell_size):
        """Parça önizleme overlay'i - ghost style"""
        cells = self._world_cells(self.cursor_x, self.cursor_y)
        color = self._get_piece_color(self.piece_names[self.selected_piece])
        
        for x, y in cells:
            if 0 <= x < self.board_width and 0 <= y < self.board_height:
                rect = pygame.Rect(board_rect.x + x * cell_size, board_rect.y + y * cell_size, cell_size, cell_size)
                
                # Ghost fill
                ghost_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
                ghost_color = (*color, 80)
                pygame.draw.rect(ghost_surf, ghost_color, ghost_surf.get_rect().inflate(-4, -4), border_radius=3)
                self.screen.blit(ghost_surf, rect.topleft)
                
                # Border glow
                pygame.draw.rect(self.screen, color, rect.inflate(-5, -5), 2, border_radius=3)

    def _draw_side_panel(self, side_rect):
        """Modern yan panel - parça paleti ve bilgiler"""
        selected_name = self.piece_names[self.selected_piece]
        color = self._get_piece_color(selected_name)
        
        # Seçili parça başlığı
        header_font = retro_style.get_font(22, bold=True)
        from emoji_renderer import emoji_surface as _es2
        _ruler_icon = _es2('📐', 22)
        _hdr_text = header_font.render(f' {selected_name}', True, color)
        if _ruler_icon:
            label = pygame.Surface((22 + _hdr_text.get_width(), max(22, _hdr_text.get_height())), pygame.SRCALPHA)
            label.blit(_ruler_icon, (0, (label.get_height() - 22) // 2))
            label.blit(_hdr_text, (22, (label.get_height() - _hdr_text.get_height()) // 2))
        else:
            label = header_font.render(f'📐 {selected_name}', True, color)
        self.screen.blit(label, (side_rect.x + 16, side_rect.y + 14))

        # Önizleme alanı - glass effect
        preview_rect = pygame.Rect(side_rect.x + 14, side_rect.y + 50, side_rect.width - 28, 100)
        preview_bg = pygame.Surface(preview_rect.size, pygame.SRCALPHA)
        preview_bg.fill((12, 18, 35, 200))
        self.screen.blit(preview_bg, preview_rect.topleft)
        pygame.draw.rect(self.screen, (50, 65, 100), preview_rect, 1, border_radius=8)
        self._draw_piece_preview(preview_rect, selected_name)

        # Bilgi satırları
        info_font = retro_style.get_font(14, bold=False)
        info_lines = [
            t('block_workshop_side_info_cells', count=len(PIECE_PREVIEW_SHAPES.get(selected_name, []))),
            t('block_workshop_side_info_angle', angle=self.rotation * 90),
        ]
        for idx, text in enumerate(info_lines):
            line = info_font.render(text, True, (180, 195, 220))
            self.screen.blit(line, (side_rect.x + 16, preview_rect.bottom + 10 + idx * 20))

        # Kayıtlı bloklar (tahtadaki bağlı bloklar) - Ctrl+S / auto-save sonrası güncellenir
        saved_items = getattr(self, 'saved_block_items', [])
        saved_title_y = preview_rect.bottom + 10 + len(info_lines) * 20 + 10
        title_font = retro_style.get_font(16, bold=True)
        title = title_font.render(t('block_workshop_saved_blocks_title'), True, (235, 240, 255))
        self.screen.blit(title, (side_rect.x + 16, saved_title_y))
        count_font = retro_style.get_font(13, bold=False)
        count_text = count_font.render(t('block_workshop_saved_blocks_count', count=len(saved_items)), True, (180, 195, 220))
        self.screen.blit(count_text, (side_rect.right - 16 - count_text.get_width(), saved_title_y + 2))

        row_y = saved_title_y + 22
        row_height = 34
        row_gap = 4
        max_rows = 3
        shown = min(max_rows, len(saved_items))
        for row_idx in range(shown):
            entry = saved_items[row_idx]
            row_rect = pygame.Rect(side_rect.x + 10, row_y + row_idx * (row_height + row_gap), side_rect.width - 20, row_height)
            row_surf = pygame.Surface(row_rect.size, pygame.SRCALPHA)
            row_surf.fill((22, 30, 50, 150))
            self.screen.blit(row_surf, row_rect.topleft)
            pygame.draw.rect(self.screen, (45, 55, 80), row_rect, 1, border_radius=4)

            mini_rect = pygame.Rect(row_rect.x + 6, row_rect.y + 5, 30, row_rect.height - 10)
            mini_surface = pygame.Surface(mini_rect.size, pygame.SRCALPHA)
            self._draw_block_preview(mini_surface, pygame.Rect(0, 0, mini_rect.width, mini_rect.height), entry)
            self.screen.blit(mini_surface, mini_rect.topleft)

            label = t(
                'block_workshop_saved_block_label',
                index=row_idx + 1,
                cells=len(entry['cells']),
                width=entry['bounds']['width'],
                height=entry['bounds']['height'],
            )
            label_font = retro_style.get_font(13, bold=False)
            label_text = label_font.render(label, True, (200, 210, 230))
            self.screen.blit(label_text, (mini_rect.right + 10, row_rect.y + 9))

        saved_section_bottom = row_y + (shown * (row_height + row_gap)) + 10

        # Parça listesi - modern kartlar
        list_top = max(preview_rect.bottom + 58, saved_section_bottom)
        card_height = 28
        card_padding = 4
        
        for idx, name in enumerate(self.piece_names):
            item_y = list_top + idx * (card_height + card_padding)
            if item_y > side_rect.bottom - 30:
                break
            
            is_selected = idx == self.selected_piece
            
            # Kart arka planı
            card_rect = pygame.Rect(side_rect.x + 10, item_y, side_rect.width - 20, card_height)
            card_surf = pygame.Surface(card_rect.size, pygame.SRCALPHA)
            card_bg = (35, 45, 70, 200) if is_selected else (22, 30, 50, 150)
            card_surf.fill(card_bg)
            self.screen.blit(card_surf, card_rect.topleft)
            
            # Kenar
            border_col = retro_style.primary if is_selected else (45, 55, 80)
            pygame.draw.rect(self.screen, border_col, card_rect, 1, border_radius=4)
            
            # Renk swatch
            swatch = pygame.Rect(card_rect.x + 6, card_rect.y + 5, 18, 18)
            piece_color = self._get_piece_color(name)
            pygame.draw.rect(self.screen, piece_color, swatch, border_radius=3)
            pygame.draw.rect(self.screen, (255, 255, 255, 40), swatch, 1, border_radius=3)
            
            # İsim
            name_font = retro_style.get_font(14, bold=is_selected)
            label_color = retro_style.primary if is_selected else (180, 195, 220)
            text = name_font.render(name, True, label_color)
            self.screen.blit(text, (swatch.right + 10, card_rect.y + 6))

    def _cycle_sets(self, delta):
        if not self.sets:
            return
        current_index = self._get_active_set_index()
        next_index = (current_index + delta) % len(self.sets)
        target_id = self.sets[next_index]['id']
        self._activate_set_by_id(target_id)

    def _activate_set_by_id(self, set_id):
        if set_id == self.active_set_id:
            return
        self._save_board(auto=True)
        for entry in self.sets:
            if entry['id'] == set_id:
                self.active_set_id = set_id
                self.board = self._deserialize_board(entry['board'])
                self.cursor_x = self.board_width // 2
                self.cursor_y = self.board_height // 2
                self._persist_sets()
                self._set_message(t('block_workshop_set_loaded', name=entry['name']), duration=150)
                self._refresh_manager_items(reset_selection=True)
                return

    def _draw_piece_preview(self, preview_rect, piece_name):
        cells = self._piece_cells(piece_name)
        if not cells:
            return
        max_dim = max(max(x for x, _ in cells) + 1, max(y for _, y in cells) + 1)
        cell_size = max(10, min((preview_rect.width - 20) // max_dim, (preview_rect.height - 20) // max_dim))
        start_x = preview_rect.x + (preview_rect.width - cell_size * max_dim) // 2
        start_y = preview_rect.y + (preview_rect.height - cell_size * max_dim) // 2
        color = self._get_piece_color(piece_name)
        for x, y in cells:
            rect = pygame.Rect(start_x + x * cell_size, start_y + y * cell_size, cell_size, cell_size)
            pygame.draw.rect(self.screen, color, rect.inflate(-4, -4), border_radius=4)
            pygame.draw.rect(self.screen, (35, 40, 70), rect, 1)

    def _draw_package_section(self, panel_surface, panel_rect):
        panel_width, panel_height = panel_surface.get_size()
        section_rect = pygame.Rect(24, panel_height - 210, panel_width - 48, 90)
        section_rect = section_rect.clamp(pygame.Rect(0, 0, panel_width, panel_height))
        pygame.draw.rect(panel_surface, (18, 24, 46), section_rect, border_radius=10)
        title = self.font_small.render(t('block_workshop_packages_title'), True, (235, 240, 255))
        panel_surface.blit(title, (section_rect.x + 12, section_rect.y + 6))
        self.set_chip_rects = []
        self.package_action_rects = []
        if not self.sets:
            empty = self.font_small.render(
                t('block_workshop_no_packages', modifier=get_modifier_key_name()),
                True,
                (200, 210, 230),
            )
            panel_surface.blit(empty, empty.get_rect(center=section_rect.center))
            return
        chip_area_x = section_rect.x + 12
        chip_area_y = section_rect.y + 30
        chip_height = 24
        max_width = section_rect.width - 24
        current_x = chip_area_x
        current_y = chip_area_y
        for idx, entry in enumerate(self.sets):
            label = f"{idx + 1}. {entry['name']}"
            if len(label) > 24:
                label = label[:21] + '...'
            text = self.font_small.render(label, True, (240, 245, 255))
            chip_width = min(max_width, text.get_width() + 26)
            if current_x + chip_width > chip_area_x + max_width:
                current_x = chip_area_x
                current_y += chip_height + 6
            if current_y + chip_height > section_rect.bottom - 36:
                break
            chip_rect = pygame.Rect(current_x, current_y, chip_width, chip_height)
            is_active = entry['id'] == self.active_set_id
            # Use uniform chip draw
            retro_style.draw_chip(panel_surface, chip_rect, label, active=is_active)
            screen_rect = pygame.Rect(
                panel_rect.x + chip_rect.x,
                panel_rect.y + chip_rect.y,
                chip_rect.width,
                chip_rect.height,
            )
            self.set_chip_rects.append((screen_rect, entry['id']))
            self.set_chip_rects.append((screen_rect, entry['id']))
            current_x += chip_width + 8

        actions = [
            (t('block_workshop_action_new'), 'new'),
            (t('block_workshop_action_duplicate'), 'duplicate'),
            (t('block_workshop_action_rename'), 'rename'),
            (t('block_workshop_action_delete'), 'delete'),
            (t('block_workshop_action_modes'), 'modes'),
        ]
        action_y = section_rect.bottom - 30
        spacing = 8
        usable_width = section_rect.width - 24 - spacing * (len(actions) - 1)
        button_width = max(60, usable_width // len(actions))
        for idx, (label, action_id) in enumerate(actions):
            btn_rect = pygame.Rect(
                section_rect.x + 12 + idx * (button_width + spacing),
                action_y,
                button_width,
                24,
            )
            # Use the unified button style but smaller
            # Transform rect to panel-local coords for draw_uniform_button
            global_rect = pygame.Rect(panel_rect.x + btn_rect.x, panel_rect.y + btn_rect.y, btn_rect.width, btn_rect.height)
            retro_style.draw_uniform_button(panel_surface, btn_rect, label, sub_text=None, state='normal', color_code='general', selected=False, checked=False)
            screen_rect = pygame.Rect(
                panel_rect.x + btn_rect.x,
                panel_rect.y + btn_rect.y,
                btn_rect.width,
                btn_rect.height,
            )
            self.package_action_rects.append((screen_rect, action_id))

    def _handle_package_chip_click(self, pos):
        for rect, set_id in self.set_chip_rects:
            if rect.collidepoint(pos):
                self._activate_set_by_id(set_id)
                self._refresh_manager_items(reset_selection=True)
                return True
        return False

    def _handle_package_action_click(self, pos):
        for rect, action in self.package_action_rects:
            if rect.collidepoint(pos):
                self._trigger_package_action(action)
                return True
        return False

    def _trigger_package_action(self, action):
        if action == 'new':
            self._create_new_set(copy_current=False)
        elif action == 'duplicate':
            self._create_new_set(copy_current=True)
        elif action == 'rename':
            self._rename_active_set()
        elif action == 'delete':
            self._delete_active_set()
        elif action == 'modes':
            self._open_set_mode_dialog()

    def _refresh_manager_items(self, *, reset_selection=False):
        self.manager_items = self._build_manager_items()
        self.saved_block_items = list(self.manager_items)
        if self.manager_open:
            self._ensure_manager_visible()
            if reset_selection:
                self.manager_selected = 0

    def _default_modes(self):
        return [mode for mode, _ in self.available_modes]

    def _create_cell(self, piece_name) -> dict[str, Any]:
        return {
            'piece': piece_name,
            'color': None,
            'modes': self._default_modes(),
        }

    def _normalize_modes(self, modes):
        if not self.available_modes:
            return []
        ordered = [mode for mode, _ in self.available_modes]
        normalized = [m for m in ordered if m in (modes or [])]
        if normalized:
            return normalized
        return [ordered[0]]

    def _get_cell_color(self, cell):
        if cell and cell.get('color'):
            return cell['color']
        return self._get_piece_color(cell['piece']) if cell else (80, 80, 80)

    def _move_cursor(self, dx, dy):
        self.cursor_x = max(0, min(self.board_width - 1, self.cursor_x + dx))
        self.cursor_y = max(0, min(self.board_height - 1, self.cursor_y + dy))

    def _cycle_piece(self, delta):
        self.selected_piece = (self.selected_piece + delta) % len(self.piece_names)

    def _rotate_piece(self, delta):
        self.rotation = (self.rotation + delta) % 4

    def _paint_cell(self, x, y):
        piece = self.piece_names[self.selected_piece]
        self.board[y][x] = self._create_cell(piece)
        self._save_board(auto=True)

    def _erase_cell(self, x, y):
        if self.board[y][x]:
            self.board[y][x] = None
            self._save_board(auto=True)

    def _clear_board(self):
        self.board = [[None for _ in range(self.board_width)] for _ in range(self.board_height)]
        self._save_board(auto=True)
        self._set_message(t('block_workshop_clear_board'))

    def _stamp_piece(self):
        cells = self._world_cells(self.cursor_x, self.cursor_y)
        if not cells:
            return
        if any(not (0 <= x < self.board_width and 0 <= y < self.board_height) for x, y in cells):
            self._set_message(t('block_workshop_out_of_bounds'))
            return
        piece = self.piece_names[self.selected_piece]
        for x, y in cells:
            self.board[y][x] = self._create_cell(piece)
        self._save_board(auto=True)

    def _choose_cell_color(self, x, y, reset=False):
        cell = self.board[y][x]
        if not cell:
            self._set_message(t('block_workshop_cell_empty'))
            return
        if reset:
            cell['color'] = None
            self._save_board(auto=True)
            self._set_message(t('block_workshop_cell_color_reset'))
            return
        fallback = cell.get('color') or self._get_piece_color(cell['piece'])
        rgb_tuple = self._prompt_color_choice(fallback)
        if rgb_tuple:
            cell['color'] = tuple(int(v) for v in rgb_tuple[:3])
            self._save_board(auto=True)
            self._set_message(t('block_workshop_cell_color_updated'))

    def _piece_cells(self, piece_name):
        base = PIECE_PREVIEW_SHAPES.get(piece_name)
        if not base:
            return []
        cells = base[:]
        for _ in range(self.rotation % 4):
            cells = [(y, -x) for x, y in cells]
            min_x = min(x for x, _ in cells)
            min_y = min(y for _, y in cells)
            cells = [(x - min_x, y - min_y) for x, y in cells]
        return cells

    def _world_cells(self, anchor_x, anchor_y):
        return [(anchor_x + x, anchor_y + y) for x, y in self._piece_cells(self.piece_names[self.selected_piece])]

    def _get_piece_color(self, piece_name):
        # Workshop editor should be stable across theme/game selection. If the user hasn't
        # explicitly painted a cell color, use the workshop defaults instead of theme/block-styles.
        fallback = DEFAULT_PIECE_COLORS.get(piece_name)
        if fallback is None:
            fallback = get_piece_base_color(piece_name, self.theme_manager)
        return fallback

    def _pos_to_cell(self, pos):
        if self.last_board_rect.width == 0 or self.last_board_rect.height == 0:
            return None
        if not self.last_board_rect.collidepoint(pos):
            return None
        rel_x = (pos[0] - self.last_board_rect.x) // self.last_cell_size
        rel_y = (pos[1] - self.last_board_rect.y) // self.last_cell_size
        if 0 <= rel_x < self.board_width and 0 <= rel_y < self.board_height:
            return int(rel_x), int(rel_y)
        return None

    def _empty_board(self) -> list[list[dict[str, Any] | None]]:
        return [[None for _ in range(self.board_width)] for _ in range(self.board_height)]

    def _empty_serialized_board(self):
        return [[None for _ in range(self.board_width)] for _ in range(self.board_height)]

    def _load_sets_from_settings(self):
        used_ids = set()
        sets = []
        raw_sets = self.settings_manager.get('block_workshop_sets', []) if self.settings_manager else []
        if isinstance(raw_sets, list):
            for entry in raw_sets:
                parsed = self._sanitize_set_entry(entry, used_ids)
                if parsed:
                    sets.append(parsed)
        if not sets:
            fallback = self.settings_manager.get('block_workshop_board', []) if self.settings_manager else []
            sets.append(self._make_set_payload(t('block_workshop_default_set'), fallback, used_ids))
        self.sets = sets
        active_id = self.settings_manager.get('block_workshop_active_set') if self.settings_manager else None
        if not active_id or not any(entry['id'] == active_id for entry in self.sets):
            active_id = self.sets[0]['id']
        self.active_set_id = active_id

    def _sanitize_set_entry(self, entry, used_ids):
        if not isinstance(entry, dict):
            return None
        set_id = entry.get('id')
        if not isinstance(set_id, str) or not set_id.strip() or set_id in used_ids:
            set_id = self._generate_unique_set_id(used_ids)
        else:
            used_ids.add(set_id)
        name = str(entry.get('name', t('block_workshop_set_base'))).strip() or t('block_workshop_set_base')
        board_data = entry.get('board') if isinstance(entry.get('board'), list) else self._empty_serialized_board()
        modes = entry.get('modes')
        if isinstance(modes, list):
            normalized = [m for m, _ in self.available_modes if m in modes]
            if not normalized:
                normalized = self._default_modes()
        else:
            normalized = self._default_modes()
        return {
            'id': set_id,
            'name': name[:40],
            'board': board_data,
            'modes': normalized,
        }

    def _make_set_payload(self, name, board_data, used_ids=None):
        set_id = self._generate_unique_set_id(used_ids)
        snapshot = board_data if isinstance(board_data, list) else self._empty_serialized_board()
        return {
            'id': set_id,
            'name': str(name).strip()[:40] or t('block_workshop_set_base'),
            'board': snapshot,
            'modes': self._default_modes(),
        }

    def _generate_unique_set_id(self, used_ids=None):
        if used_ids is None:
            used_ids = {entry['id'] for entry in self.sets if entry.get('id')}
        while True:
            candidate = f"set-{uuid.uuid4().hex[:6]}"
            if candidate not in used_ids:
                used_ids.add(candidate)
                return candidate

    def _make_unique_set_name(self, base):
        desired = (base or t('block_workshop_set_base')).strip()[:40] or t('block_workshop_set_base')
        existing = {entry['name'] for entry in self.sets}
        if desired not in existing:
            return desired
        counter = 2
        while True:
            candidate = f"{desired} {counter}"
            if candidate not in existing:
                return candidate[:40]
            counter += 1

    def _get_active_set(self):
        for entry in self.sets:
            if entry['id'] == self.active_set_id:
                return entry
        return self.sets[0] if self.sets else None

    def _get_active_set_index(self):
        for idx, entry in enumerate(self.sets):
            if entry['id'] == self.active_set_id:
                return idx
        return 0

    def _load_board(self):
        active = self._get_active_set()
        snapshot = active['board'] if active else self._empty_serialized_board()
        return self._deserialize_board(snapshot)

    def _deserialize_board(self, snapshot) -> list[list[dict[str, Any] | None]]:
        board = self._empty_board()
        if not isinstance(snapshot, list):
            return board
        for y, row in enumerate(snapshot):
            if y >= self.board_height or not isinstance(row, list):
                continue
            for x, value in enumerate(row):
                if x >= self.board_width:
                    break
                if isinstance(value, str) and value in self.piece_names:
                    board[y][x] = self._create_cell(value)
                elif isinstance(value, dict):
                    piece = value.get('piece')
                    if piece in self.piece_names:
                        cell = self._create_cell(piece)
                        color = value.get('color')
                        if isinstance(color, (list, tuple)) and len(color) == 3:
                            cell['color'] = tuple(int(max(0, min(255, c))) for c in color)
                        modes = value.get('modes')
                        if isinstance(modes, list):
                            valid = [m for m, _ in self.available_modes if m in modes]
                            if valid:
                                cell['modes'] = valid
                        board[y][x] = cell
        return board

    def _serialize_board(self):
        serialized: list[list[dict[str, Any] | None]] = []
        for row in self.board:
            serialized_row: list[dict[str, Any] | None] = []
            for cell in row:
                if not cell:
                    serialized_row.append(None)
                    continue
                payload: dict[str, Any] = {'piece': cell['piece']}
                if cell.get('color'):
                    payload['color'] = list(cell['color'])
                if cell.get('modes') and cell['modes'] != self._default_modes():
                    payload['modes'] = list(cell['modes'])
                serialized_row.append(payload)
            serialized.append(serialized_row)
        return serialized

    def _persist_sets(self, board_snapshot=None):
        board_snapshot = board_snapshot if board_snapshot is not None else self._serialize_board()
        active = self._get_active_set()
        if active:
            active['board'] = board_snapshot
        if not self.settings_manager:
            return
        payload = []
        for entry in self.sets:
            payload.append({
                'id': entry['id'],
                'name': entry['name'],
                'board': entry['board'],
                'modes': entry['modes'],
            })
        self.settings_manager.update(
            block_workshop_sets=payload,
            block_workshop_active_set=self.active_set_id,
            block_workshop_board=board_snapshot,
        )

    def _save_board(self, auto=False):
        board_snapshot = self._serialize_board()
        active = self._get_active_set()
        if active:
            active['board'] = board_snapshot
        self._persist_sets(board_snapshot)
        if not auto:
            self._set_message(t('block_workshop_saved'))
        self._refresh_manager_items()

    def _generate_default_set_name(self):
        return self._make_unique_set_name(t('block_workshop_set_number', index=len(self.sets) + 1))

    def _create_new_set(self, copy_current=False):
        base_snapshot = self._serialize_board() if copy_current else self._empty_serialized_board()
        active = self._get_active_set()
        desired_name = (
            f"{active['name']} {t('block_workshop_set_copy_suffix')}"
            if (copy_current and active)
            else self._generate_default_set_name()
        )
        new_entry = {
            'id': self._generate_unique_set_id(),
            'name': self._make_unique_set_name(desired_name),
            'board': base_snapshot,
            'modes': list(active['modes']) if (copy_current and active) else self._default_modes(),
        }
        self.sets.append(new_entry)
        self.active_set_id = new_entry['id']
        self.board = self._deserialize_board(base_snapshot)
        self.cursor_x = self.board_width // 2
        self.cursor_y = self.board_height // 2
        self.set_mode_dialog = False
        self._persist_sets(base_snapshot)
        self._set_message(t('block_workshop_new_set_created'), duration=150)
        self._refresh_manager_items(reset_selection=True)

    def _delete_active_set(self):
        if len(self.sets) <= 1:
            self._set_message(t('block_workshop_min_one_set'), duration=150)
            return
        index = self._get_active_set_index()
        removed = self.sets.pop(index)
        next_index = max(0, min(index, len(self.sets) - 1))
        self.active_set_id = self.sets[next_index]['id']
        self.board = self._deserialize_board(self.sets[next_index]['board'])
        self.cursor_x = self.board_width // 2
        self.cursor_y = self.board_height // 2
        self.set_mode_dialog = False
        self._persist_sets()
        self._set_message(t('block_workshop_set_deleted', name=removed['name']), duration=150)
        self._refresh_manager_items(reset_selection=True)

    def _rename_active_set(self):
        entry = self._get_active_set()
        if not entry:
            return
        new_name = self._prompt_text_input(t('block_workshop_set_name_title'), entry['name'])
        if not new_name:
            return
        entry['name'] = self._make_unique_set_name(new_name)
        self._persist_sets()
        self._set_message(t('block_workshop_set_name_updated'), duration=150)
        self._refresh_manager_items()

    def _open_set_mode_dialog(self):
        if not self.sets:
            return
        self.set_mode_dialog = True
        self.set_mode_focus = 0
        self.set_mode_tag_rects = []

    def _handle_set_mode_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                self.set_mode_dialog = False
                return None
            if event.key == pygame.K_LEFT:
                self.set_mode_focus = max(0, self.set_mode_focus - 1)
            elif event.key == pygame.K_RIGHT:
                self.set_mode_focus = min(len(self.available_modes) - 1, self.set_mode_focus + 1)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._toggle_active_set_mode(self.set_mode_focus)
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.available_modes):
                    self.set_mode_focus = idx
                    self._toggle_active_set_mode(idx)
            elif event.key == pygame.K_0:
                idx = 9
                if idx < len(self.available_modes):
                    self.set_mode_focus = idx
                    self._toggle_active_set_mode(idx)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for idx, rect in enumerate(self.set_mode_tag_rects):
                if rect.collidepoint(pos):
                    self.set_mode_focus = idx
                    self._toggle_active_set_mode(idx)
                    break
        return None

    def _draw_set_mode_overlay(self, width, height):
        panel_scale = self._fullscreen_panel_scale()
        panel_width = max(int(360 * panel_scale), min(int(520 * panel_scale), width - max(80, int(120 * panel_scale))))
        panel_height = max(int(220 * panel_scale), min(int(320 * panel_scale), height - max(110, int(160 * panel_scale))))
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((10, 12, 34, 235))
        pygame.draw.rect(panel, retro_style.accent, panel.get_rect(), 2, border_radius=16)
        title = self.font_option.render(t('block_workshop_set_mode_title'), True, (255, 255, 255))
        panel.blit(title, title.get_rect(center=(panel_width // 2, max(22, int(30 * panel_scale)))))
        entry = self._get_active_set()
        if entry:
            subtitle = self.font_small.render(entry['name'], True, (210, 220, 240))
            panel.blit(subtitle, subtitle.get_rect(center=(panel_width // 2, max(48, int(68 * panel_scale)))))
        self.set_mode_tag_rects = []
        columns = 3
        side_pad = max(26, int(40 * panel_scale))
        gap_x = max(8, int(10 * panel_scale))
        tag_width = (panel_width - side_pad * 2 - gap_x * (columns - 1)) // columns
        start_y = max(80, int(110 * panel_scale))
        row_gap = max(42, int(52 * panel_scale))
        tag_h = max(30, int(40 * panel_scale))
        if entry:
            for idx, (mode_key, mode_label_key) in enumerate(self.available_modes):
                col = idx % columns
                row = idx // columns
                tag_rect = pygame.Rect(side_pad + col * (tag_width + gap_x), start_y + row * row_gap, tag_width, tag_h)
                enabled = mode_key in entry['modes']
                fill_color = (70, 120, 95) if enabled else (32, 36, 60)
                border_color = retro_style.accent if idx == self.set_mode_focus else (90, 98, 140)
                pygame.draw.rect(panel, fill_color, tag_rect, border_radius=10)
                pygame.draw.rect(panel, border_color, tag_rect, 2, border_radius=10)
                label = self.font_small.render(('✓ ' if enabled else '  ') + t(mode_label_key), True, (240, 245, 255))
                panel.blit(label, label.get_rect(center=tag_rect.center))
                screen_rect = pygame.Rect(tag_rect)
                screen_rect.topleft = (panel_rect.x + tag_rect.x, panel_rect.y + tag_rect.y)
                self.set_mode_tag_rects.append(screen_rect)
        instructions = [
            t('block_workshop_set_mode_hint_line1'),
            t('block_workshop_set_mode_hint_line2'),
        ]
        for idx, text in enumerate(instructions):
            hint = self.font_small.render(text, True, (185, 200, 230))
            panel.blit(hint, hint.get_rect(center=(panel_width // 2, panel_height - max(26, int(40 * panel_scale)) + idx * max(14, int(20 * panel_scale)))))
        self.screen.blit(panel, panel_rect.topleft)

    def _toggle_active_set_mode(self, mode_index):
        entry = self._get_active_set()
        if not entry or mode_index >= len(self.available_modes):
            return
        mode_key = self.available_modes[mode_index][0]
        modes = list(entry['modes'])
        if mode_key in modes:
            if len(modes) > 1:
                modes = [m for m in modes if m != mode_key]
        else:
            modes.append(mode_key)
        modes = self._normalize_modes(modes)
        entry['modes'] = modes
        self._persist_sets()
        self._set_message(t('block_workshop_set_modes_updated'), duration=120)
        self._refresh_manager_items()

    def _set_message(self, text, duration=180):
        self.message = text
        self.message_timer = duration

    def _enter_manager(self):
        self.manager_items = self._build_manager_items()
        if not self.manager_items:
            self._set_message(t('block_workshop_no_saved_blocks'))
            return
        self.manager_open = True
        self.manager_selected = 0
        self.manager_scroll = 0
        self.manager_mode_focus = 0

    def _exit_manager(self):
        self.manager_open = False

    def _build_manager_items(self):
        visited = [[False for _ in range(self.board_width)] for _ in range(self.board_height)]
        items = []
        for y in range(self.board_height):
            for x in range(self.board_width):
                if visited[y][x]:
                    continue
                cell = self.board[y][x]
                if not cell:
                    continue
                block_cells, bounds = self._collect_block_cells(x, y, visited)
                if not block_cells:
                    continue
                all_modes = set()
                for info in block_cells:
                    all_modes.update(info['cell'].get('modes') or self._default_modes())
                entry_modes = self._normalize_modes(list(all_modes))
                for info in block_cells:
                    info['cell']['modes'] = list(entry_modes)
                items.append({
                    'cells': block_cells,
                    'bounds': bounds,
                    'modes': entry_modes
                })
        items.sort(key=lambda entry: (entry['bounds']['min_y'], entry['bounds']['min_x']))
        return items

    def _collect_block_cells(self, start_x, start_y, visited):
        stack = [(start_x, start_y)]
        cells = []
        min_x = max_x = start_x
        min_y = max_y = start_y
        while stack:
            x, y = stack.pop()
            if not (0 <= x < self.board_width and 0 <= y < self.board_height):
                continue
            if visited[y][x]:
                continue
            visited[y][x] = True
            cell = self.board[y][x]
            if not cell:
                continue
            cells.append({'x': x, 'y': y, 'cell': cell})
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < self.board_width and 0 <= ny < self.board_height and not visited[ny][nx]:
                    stack.append((nx, ny))
        bounds = {
            'min_x': min_x,
            'min_y': min_y,
            'width': max_x - min_x + 1,
            'height': max_y - min_y + 1,
        }
        return cells, bounds

    def _ensure_manager_visible(self, visible_rows=8):
        if not self.manager_items:
            self.manager_scroll = 0
            self.manager_selected = 0
            return
        max_index = len(self.manager_items) - 1
        self.manager_selected = max(0, min(self.manager_selected, max_index))
        max_scroll = max(0, len(self.manager_items) - visible_rows)
        if self.manager_selected < self.manager_scroll:
            self.manager_scroll = self.manager_selected
        elif self.manager_selected >= self.manager_scroll + visible_rows:
            self.manager_scroll = self.manager_selected - visible_rows + 1
        self.manager_scroll = max(0, min(self.manager_scroll, max_scroll))

    def _delete_manager_item(self, index):
        if index < 0 or index >= len(self.manager_items):
            return
        entry = self.manager_items.pop(index)
        for info in entry['cells']:
            self.board[info['y']][info['x']] = None
        self._save_board(auto=True)
        if not self.manager_items:
            self._exit_manager()
        else:
            self.manager_selected = max(0, min(self.manager_selected, len(self.manager_items) - 1))

    def _toggle_manager_mode(self, mode_index):
        if not self.manager_items or mode_index >= len(self.available_modes):
            return
        entry = self.manager_items[self.manager_selected]
        mode_key = self.available_modes[mode_index][0]
        modes = list(entry['modes'])
        if mode_key in modes:
            modes = [m for m in modes if m != mode_key]
            if not modes:
                modes = [mode_key]
        else:
            modes.append(mode_key)
        modes = self._normalize_modes(modes)
        entry['modes'] = modes
        for info in entry['cells']:
            info['cell']['modes'] = list(modes)
        self._save_board(auto=True)

    def _handle_manager_input(self, event):
        if event.type == pygame.KEYDOWN:
            mods = getattr(event, 'mod', pygame.key.get_mods())
            if is_primary_modifier(mods):
                if event.key == pygame.K_n:
                    self._create_new_set(copy_current=False)
                    return None
                if event.key == pygame.K_d:
                    self._create_new_set(copy_current=True)
                    return None
                if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                    self._delete_active_set()
                    return None
                if event.key == pygame.K_m:
                    self._open_set_mode_dialog()
                    return None
            if event.key == pygame.K_F2:
                self._rename_active_set()
                return None
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                self._exit_manager()
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                self._exit_manager()
                return 'toggle_fullscreen'
            if event.key == pygame.K_s and (is_primary_modifier(mods) or (mods & pygame.KMOD_SHIFT)):
                self._save_board()
                return None
            if not self.manager_items:
                return None
            if event.key == pygame.K_UP:
                self.manager_selected = max(0, self.manager_selected - 1)
            elif event.key == pygame.K_DOWN:
                self.manager_selected = min(len(self.manager_items) - 1, self.manager_selected + 1)
            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._delete_manager_item(self.manager_selected)
            elif event.key == pygame.K_SPACE:
                self._toggle_manager_mode(self.manager_mode_focus)
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.available_modes):
                    self.manager_mode_focus = idx
                    self._toggle_manager_mode(idx)
            elif event.key == pygame.K_0:
                idx = 9
                if idx < len(self.available_modes):
                    self.manager_mode_focus = idx
                    self._toggle_manager_mode(idx)
            elif event.key == pygame.K_LEFT:
                if self.manager_mode_focus > 0:
                    self.manager_mode_focus -= 1
            elif event.key == pygame.K_RIGHT:
                if self.manager_mode_focus < len(self.available_modes) - 1:
                    self.manager_mode_focus += 1
            elif event.key == pygame.K_RETURN:
                entry = self.manager_items[self.manager_selected]
                first_cell = entry['cells'][0]
                self.cursor_x, self.cursor_y = first_cell['x'], first_cell['y']
                self._exit_manager()
            elif event.key == pygame.K_k:
                entry = self.manager_items[self.manager_selected]
                self._choose_block_color(entry, reset=bool(mods & pygame.KMOD_SHIFT))
            self.manager_items = self._build_manager_items()
            self._ensure_manager_visible()
        elif event.type == pygame.MOUSEWHEEL:
            if not self.manager_items:
                return None
            if event.y > 0:
                self.manager_selected = max(0, self.manager_selected - 1)
            elif event.y < 0:
                self.manager_selected = min(len(self.manager_items) - 1, self.manager_selected + 1)
            self._ensure_manager_visible()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if self._handle_package_chip_click(pos):
                return None
            if self._handle_package_action_click(pos):
                return None
        return None

    def _draw_manager_overlay(self, width, height):
        panel_scale = self._fullscreen_panel_scale()
        panel_width = min(int(780 * panel_scale), width - max(70, int(100 * panel_scale)))
        panel_height = min(int(520 * panel_scale), height - max(86, int(120 * panel_scale)))
        panel_width = max(520, panel_width)
        panel_height = max(340, panel_height)
        top_offset = max(44, int(90 * panel_scale))
        panel_rect = pygame.Rect((width - panel_width) // 2, top_offset, panel_width, panel_height)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((6, 8, 24, 240))
        pygame.draw.rect(panel, retro_style.accent, panel.get_rect(), 2, border_radius=14)
        title = self.font_option.render(t('block_workshop_manager_title'), True, (255, 255, 255))
        panel.blit(title, title.get_rect(midtop=(panel_width // 2, max(6, int(8 * panel_scale)))))

        list_pad_x = max(16, int(24 * panel_scale))
        list_top = max(42, int(60 * panel_scale))
        list_rect = pygame.Rect(list_pad_x, list_top, panel_width - (list_pad_x * 2), panel_height - max(130, int(200 * panel_scale)))
        row_height = max(34, int(48 * panel_scale))
        visible_rows = max(1, list_rect.height // row_height)
        self._ensure_manager_visible(visible_rows)

        if not self.manager_items:
            empty = self.font_small.render(t('block_workshop_manager_empty'), True, (210, 220, 235))
            panel.blit(empty, empty.get_rect(center=list_rect.center))
        else:
            for idx in range(visible_rows):
                item_index = self.manager_scroll + idx
                if item_index >= len(self.manager_items):
                    break
                entry = self.manager_items[item_index]
                row_rect = pygame.Rect(list_rect.x, list_rect.y + idx * row_height, list_rect.width, row_height - max(4, int(6 * panel_scale)))
                highlight = item_index == self.manager_selected
                bg_color = (50, 70, 120, 210) if highlight else (25, 32, 58, 190)
                row_surface = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                row_surface.fill(bg_color)
                label = t(
                    'block_workshop_manager_row_label',
                    index=f"{item_index + 1:02d}",
                    cells=len(entry['cells']),
                    width=entry['bounds']['width'],
                    height=entry['bounds']['height'],
                )
                text = self.font_small.render(label, True, (240, 245, 255))
                row_surface.blit(text, (max(8, int(12 * panel_scale)), max(5, int(8 * panel_scale))))
                mode_hint = ', '.join(entry['modes'])
                hint_text = self.font_small.render(mode_hint, True, (180, 200, 230))
                row_surface.blit(hint_text, (max(8, int(12 * panel_scale)), row_rect.height - max(16, int(22 * panel_scale))))
                preview_rect = pygame.Rect(row_rect.width - max(70, int(90 * panel_scale)), max(4, int(6 * panel_scale)), max(54, int(72 * panel_scale)), row_rect.height - max(8, int(12 * panel_scale)))
                self._draw_block_preview(row_surface, preview_rect, entry)
                panel.blit(row_surface, row_rect.topleft)

        self._draw_package_section(panel, panel_rect)

        detail_rect = pygame.Rect(list_pad_x, panel_height - max(82, int(118 * panel_scale)), panel_width - (list_pad_x * 2), max(64, int(88 * panel_scale)))
        pygame.draw.rect(panel, (18, 24, 46), detail_rect, border_radius=10)
        if self.manager_items:
            entry = self.manager_items[self.manager_selected]
            info = self.font_small.render(
                t(
                    'block_workshop_manager_selected_info',
                    cells=len(entry['cells']),
                    width=entry['bounds']['width'],
                    height=entry['bounds']['height'],
                ),
                True,
                (235, 240, 255)
            )
            panel.blit(info, (detail_rect.x + max(8, int(12 * panel_scale)), detail_rect.y + max(5, int(8 * panel_scale))))
            mode_start_y = detail_rect.y + max(22, int(32 * panel_scale))
            col_width = (detail_rect.width - max(14, int(20 * panel_scale))) // 3
            for idx, (mode_key, mode_label_key) in enumerate(self.available_modes):
                col = idx % 3
                row = idx // 3
                tag_rect = pygame.Rect(
                    detail_rect.x + max(6, int(10 * panel_scale)) + col * col_width,
                    mode_start_y + row * max(20, int(28 * panel_scale)),
                    col_width - max(8, int(12 * panel_scale)),
                    max(18, int(24 * panel_scale)),
                )
                enabled = mode_key in entry['modes']
                border_color = retro_style.accent if idx == self.manager_mode_focus else (80, 90, 130)
                fill_color = (70, 120, 90) if enabled else (40, 44, 70)
                tag_surface = pygame.Surface(tag_rect.size, pygame.SRCALPHA)
                tag_surface.fill(fill_color)
                pygame.draw.rect(tag_surface, border_color, tag_surface.get_rect(), 2, border_radius=8)
                label = self.font_small.render(('✓ ' if enabled else '  ') + t(mode_label_key), True, (240, 245, 255))
                tag_surface.blit(label, (6, 2))
                panel.blit(tag_surface, tag_rect.topleft)

        instructions = [
            t('block_workshop_manager_instructions_line1'),
            t('block_workshop_manager_instructions_line2'),
            t('block_workshop_manager_instructions_line3', modifier=get_modifier_key_name()),
        ]
        for idx, text in enumerate(instructions):
            hint = self.font_small.render(text, True, (190, 205, 235))
            panel.blit(hint, hint.get_rect(center=(panel_width // 2, panel_height - max(26, int(40 * panel_scale)) + idx * max(14, int(20 * panel_scale)))))

        self.screen.blit(panel, panel_rect.topleft)

    def _draw_block_preview(self, surface, rect, entry):
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        preview.fill((12, 16, 30, 180))
        bounds = entry['bounds']
        width = max(1, bounds['width'])
        height = max(1, bounds['height'])
        cell_size = max(4, min((rect.width - 8) // width, (rect.height - 8) // height))
        offset_x = (rect.width - cell_size * width) // 2
        offset_y = (rect.height - cell_size * height) // 2
        for info in entry['cells']:
            color = self._get_cell_color(info['cell'])
            rel_x = info['x'] - bounds['min_x']
            rel_y = info['y'] - bounds['min_y']
            px = offset_x + rel_x * cell_size
            py = offset_y + rel_y * cell_size
            draw_jelly_block(preview, px, py, cell_size, color)
        surface.blit(preview, rect.topleft)

    def _choose_block_color(self, entry, reset=False):
        if not entry or not entry.get('cells'):
            self._set_message(t('block_workshop_block_empty'))
            return
        if reset:
            for info in entry['cells']:
                info['cell']['color'] = None
            self._save_board(auto=True)
            self._set_message(t('block_workshop_block_colors_reset'))
            return
        fallback = None
        for info in entry['cells']:
            color = info['cell'].get('color')
            if color:
                fallback = color
                break
        if fallback is None:
            fallback = self._get_piece_color(entry['cells'][0]['cell']['piece'])
        p_name = entry['cells'][0]['cell'].get('piece', '') if entry.get('cells') else ''
        rgb_tuple = self._prompt_color_choice(fallback, piece_name=p_name)
        if not rgb_tuple:
            return
        chosen = tuple(int(v) for v in rgb_tuple[:3])
        for info in entry['cells']:
            info['cell']['color'] = chosen
        self._save_board(auto=True)
        self._set_message(t('block_workshop_block_color_updated'))

    def _prompt_color_choice(self, fallback, piece_name=""):
        from color_picker import pygame_color_picker
        initial = tuple(int(v) for v in fallback[:3])
        chosen = pygame_color_picker(self.screen, initial_color=initial, piece_name=piece_name)
        return chosen

    def _prompt_text_input(self, title, initial_text=''):
        from color_picker import pygame_text_input
        return pygame_text_input(
            self.screen,
            title=title,
            prompt=t('block_workshop_set_name_prompt'),
            initial_text=initial_text,
        )

    @staticmethod
    def _clamp_channel(value):
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError):
            return 0


class SettingsScreen:
    """Ayarlar ekranı"""
    
    def __init__(self, screen, theme_manager, settings_manager, sound_manager=None):
        """Ayarlar ekranını başlat"""
        self.screen = screen
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
        self.sound_manager = sound_manager
        
        # Dinamik müzik listesi oluştur
        self.music_types = self._build_music_list()
        self.font_title = retro_style.get_font(48)
        self.font_option = retro_style.get_font(30, bold=True)
        self.font_value = retro_style.get_font(24, bold=True)
        self.font_value_small = retro_style.get_font(20, bold=True)
        self.font_small = retro_style.get_font(22, bold=True)
        self.font_hint = retro_style.get_font(20, bold=True)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Dil ayarı
        self.current_language = settings_manager.get('language', 'tr')
        set_language(self.current_language)  # Başlangıçta dili uygula
        apply_language_ui_profile(self.current_language)
        self._refresh_fonts()
        
        self._update_options()
        self.selected = 0
        
        # Ayarları settings_manager'dan yükle
        self.music_enabled = settings_manager.get('music_enabled', True)
        self.music_volume = settings_manager.get('music_volume', 0.5)
        self.sound_enabled = settings_manager.get('sound_enabled', True)
        self.sfx_volume = settings_manager.get('sfx_volume', 0.5)
        self.mute_all = settings_manager.get('mute_all', False)
        self.effects_enabled = settings_manager.get('effects_enabled', True)
        self.background_enabled = settings_manager.get('background_enabled', True)
        self.custom_background = settings_manager.get('custom_background', None)
        self.menu_music = settings_manager.get('menu_music', 'Mainv3')
        self.game_music = settings_manager.get('game_music', 'Klasikv1')
        self.difficulty = 'Normal'  # Sabit değer - artık ayarlanabilir değil
        self.debug_mode = settings_manager.get('debug_mode', False)
        self.card_mode_debug = settings_manager.get('card_mode_debug', False)
        self._show_debug_settings = bool(settings_manager.get('show_debug_settings', False))
        
        self.option_rects = []  # Mouse için hitbox'lar
        self.scroll_offset = 0  # Kaydırma için
        self._update_hints()

        # Smooth animation for slider-like values + cached percent rendering
        self._anim_last_tick = pygame.time.get_ticks()
        self._music_volume_vis = float(self.music_volume)
        self._sfx_volume_vis = float(self.sfx_volume)
        self._music_pct_last = None
        self._sfx_pct_last = None
        self._music_pct_surf = None
        self._sfx_pct_surf = None

        # Theme picker overlay state (Mode Music picker-style)
        self.theme_picker_open = False
        self.theme_picker_selected = 0
        self.theme_picker_scroll = 0
        self.theme_picker_item_rects: list[tuple[pygame.Rect, int]] = []
        self._theme_options_cache: list[str] = []

        # Language side panel (inline, non-overlay)
        self.language_panel_open = False
        self.language_panel_selected = 0
        self.language_panel_scroll = 0
        self.language_panel_item_rects: list[tuple[pygame.Rect, int]] = []
        self.language_panel_anchor_rect: pygame.Rect | None = None
        self.language_panel_rect: pygame.Rect | None = None

        # Music hub + track picker overlays (merge menu/game/mode music into one entry)
        self.music_hub_open = False
        self.music_hub_selected = 0
        self.music_hub_item_rects: list[tuple[pygame.Rect, int]] = []

        self.music_track_picker_open = False
        self.music_track_picker_target = None  # 'menu' | 'game'
        self.music_track_picker_selected = 0
        self.music_track_picker_scroll = 0
        self.music_track_picker_item_rects: list[tuple[pygame.Rect, int]] = []

        # Mode music overlay inside music hub
        self.mode_music_overlay_open = False
        self.mode_music_overlay = ModeMusicScreen(screen, settings_manager)

    def _refresh_fonts(self) -> None:
        self.font_title = retro_style.get_font(48)
        self.font_option = retro_style.get_font(30, bold=True)
        self.font_value = retro_style.get_font(24, bold=True)
        self.font_value_small = retro_style.get_font(20, bold=True)
        self.font_small = retro_style.get_font(22, bold=True)
        self.font_hint = retro_style.get_font(20, bold=True)

    def _get_theme_options(self) -> list[str]:
        try:
            themes = list(self.theme_manager.get_all_theme_names()) if self.theme_manager else []
        except Exception:
            themes = []
        # Cache to avoid repeated list allocations every frame
        if themes:
            self._theme_options_cache = themes
        return self._theme_options_cache

    def _open_theme_picker(self) -> None:
        themes = self._get_theme_options()
        if not themes:
            return
        self.theme_picker_open = True
        self.theme_picker_scroll = 0
        self.theme_picker_item_rects = []

        current = getattr(self.theme_manager, 'theme_name', None)
        try:
            if not isinstance(current, str):
                raise ValueError("Current theme is not a string")
            self.theme_picker_selected = themes.index(current)
        except Exception:
            self.theme_picker_selected = 0

    def _close_theme_picker(self) -> None:
        self.theme_picker_open = False
        self.theme_picker_item_rects = []

    def _get_language_options(self) -> list[tuple[str, str]]:
        langs = []
        for code, native_name, flag, _complete in get_all_languages():
            label = native_name
            langs.append((code, label))
        return langs

    def _open_language_panel(self, anchor_rect: pygame.Rect) -> None:
        self.language_panel_open = True
        self.language_panel_anchor_rect = anchor_rect.copy()
        self.language_panel_scroll = 0
        self.language_panel_item_rects = []
        langs = self._get_language_options()
        codes = [c for c, _ in langs]
        try:
            self.language_panel_selected = codes.index(self.current_language)
        except Exception:
            self.language_panel_selected = 0

    def _close_language_panel(self) -> None:
        self.language_panel_open = False
        self.language_panel_item_rects = []
        self.language_panel_anchor_rect = None
        self.language_panel_rect = None

    def _apply_language_choice(self, lang_code: str) -> str | None:
        if not lang_code:
            return None
        if lang_code == self.current_language:
            return None
        self.current_language = lang_code
        set_language(self.current_language)
        apply_language_ui_profile(self.current_language)
        self._refresh_fonts()
        self.settings_manager.set('language', self.current_language)
        self._update_options()
        self._update_hints()
        return 'language_changed'

    def _language_panel_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self._get_language_options()) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _language_panel_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.language_panel_selected * (item_h + gap)
        if y < self.language_panel_scroll:
            self.language_panel_scroll = y
        elif y > self.language_panel_scroll + visible_h - item_h:
            self.language_panel_scroll = y - (visible_h - item_h)
        self.language_panel_scroll = max(0, min(self.language_panel_scroll, self._language_panel_max_scroll(visible_h, item_h, gap)))

    def _get_language_panel_rect(self, width: int, height: int) -> pygame.Rect | None:
        anchor = self.language_panel_anchor_rect
        if anchor is None:
            return None
        panel_w = 240
        item_h = 34
        gap = 6
        total_h = len(self._get_language_options()) * (item_h + gap)
        visible_h = min(280, max(140, height - 200))
        panel_h = min(total_h + 16, visible_h)

        panel_x = anchor.right + 12
        if panel_x + panel_w > width - 20:
            panel_x = anchor.left - panel_w - 12
        panel_x = max(20, min(panel_x, width - panel_w - 20))

        panel_y = anchor.y
        if panel_y + panel_h > height - 20:
            panel_y = height - 20 - panel_h
        panel_y = max(120, panel_y)

        return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    def _handle_language_panel_input(self, event):
        langs = self._get_language_options()
        if not langs:
            self._close_language_panel()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_language_panel()
                return None
            if event.key == pygame.K_UP:
                self.language_panel_selected = (self.language_panel_selected - 1) % len(langs)
                return None
            if event.key == pygame.K_DOWN:
                self.language_panel_selected = (self.language_panel_selected + 1) % len(langs)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                code, _label = langs[self.language_panel_selected]
                action = self._apply_language_choice(code)
                self._close_language_panel()
                return action
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.language_panel_scroll -= event.y * 30
            self.language_panel_scroll = max(0, self.language_panel_scroll)
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.language_panel_item_rects:
                if rect.collidepoint(pos):
                    self.language_panel_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.language_panel_item_rects:
                if rect.collidepoint(pos):
                    self.language_panel_selected = idx
                    code, _label = langs[self.language_panel_selected]
                    action = self._apply_language_choice(code)
                    self._close_language_panel()
                    return action
            if self.language_panel_rect and not self.language_panel_rect.collidepoint(pos):
                self._close_language_panel()
            return None

        return None

    def _draw_language_panel(self) -> None:
        width, height = self.screen.get_size()
        langs = self._get_language_options()
        if not langs:
            return

        panel_rect = self._get_language_panel_rect(width, height)
        if panel_rect is None:
            return
        self.language_panel_rect = panel_rect

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=200, border_color=retro_style.primary, glow=False)

        list_rect = pygame.Rect(panel_rect.x + 8, panel_rect.y + 8, panel_rect.width - 16, panel_rect.height - 16)

        item_h = 34
        gap = 6
        self.language_panel_item_rects = []
        self.language_panel_scroll = max(0, min(self.language_panel_scroll, self._language_panel_max_scroll(list_rect.height, item_h, gap)))
        self._language_panel_ensure_visible(list_rect.height, item_h, gap)

        self.screen.set_clip(list_rect)
        for idx, (_code, label) in enumerate(langs):
            y = list_rect.y + idx * (item_h + gap) - self.language_panel_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue
            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.language_panel_item_rects.append((r, idx))
            selected = idx == self.language_panel_selected

            bg = (35, 55, 90, 220) if selected else (18, 24, 40, 170)
            border = retro_style.accent if selected else (60, 70, 90)
            pygame.draw.rect(self.screen, bg, r, border_radius=8)
            pygame.draw.rect(self.screen, border, r, 2 if selected else 1, border_radius=8)

            # CJK dilleri için o dilin kendi fontunu kullan (kare sorunu çözümü)
            cjk_font = get_font_for_language(_code, 20)
            if cjk_font:
                text_font = cjk_font
            else:
                text_font = retro_style.get_font(20, bold=selected)
            txt = text_font.render(str(label), True, (255, 255, 255) if selected else (205, 215, 235))
            self.screen.blit(txt, (r.x + 10, r.y + (r.height - txt.get_height()) // 2))

        self.screen.set_clip(None)

        total_h = len(langs) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(panel_rect.right - 8, list_rect.y, 4, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.language_panel_scroll, total_h, list_rect.height)

    def _theme_picker_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        themes = self._get_theme_options()
        total_h = len(themes) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _theme_picker_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.theme_picker_selected * (item_h + gap)
        if y < self.theme_picker_scroll:
            self.theme_picker_scroll = y
        elif y > self.theme_picker_scroll + visible_h - item_h:
            self.theme_picker_scroll = y - (visible_h - item_h)
        self.theme_picker_scroll = max(0, min(self.theme_picker_scroll, self._theme_picker_max_scroll(visible_h, item_h, gap)))

    def _apply_theme_choice(self, theme_name: str) -> None:
        if not theme_name:
            return
        if self.theme_manager:
            self.theme_manager.set_theme(theme_name)
        if self.settings_manager:
            self.settings_manager.set('theme', theme_name)

    def _handle_theme_picker_input(self, event):
        themes = self._get_theme_options()
        if not themes:
            self._close_theme_picker()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_theme_picker()
                return None
            if event.key == pygame.K_UP:
                self.theme_picker_selected = (self.theme_picker_selected - 1) % len(themes)
                return None
            if event.key == pygame.K_DOWN:
                self.theme_picker_selected = (self.theme_picker_selected + 1) % len(themes)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._apply_theme_choice(themes[self.theme_picker_selected])
                self._close_theme_picker()
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.theme_picker_scroll -= event.y * 36
            self.theme_picker_scroll = max(0, self.theme_picker_scroll)
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.theme_picker_item_rects:
                if rect.collidepoint(pos):
                    self.theme_picker_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                # click on an item selects
                for rect, idx in self.theme_picker_item_rects:
                    if rect.collidepoint(pos):
                        self.theme_picker_selected = idx
                        self._apply_theme_choice(themes[self.theme_picker_selected])
                        self._close_theme_picker()
                        return None
                # click outside closes
                self._close_theme_picker()
                return None

        return None

    def _draw_theme_picker(self) -> None:
        width, height = self.screen.get_size()
        themes = self._get_theme_options()
        if not themes:
            return

        # Dim background
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_w = min(720, width - 120)
        panel_h = min(520, height - 160)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('panel_theme'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        current = getattr(self.theme_manager, 'theme_name', '') if self.theme_manager else ''
        if current:
            sub = subtitle_font.render(f'{t("active")}: {current}', True, (170, 190, 220))
            self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 50))

        # List area
        list_top = panel_rect.y + 86
        list_left = panel_rect.x + 18
        list_right = panel_rect.right - 18
        list_bottom = panel_rect.bottom - 60
        list_rect = pygame.Rect(list_left, list_top, list_right - list_left, list_bottom - list_top)

        item_h = 44
        gap = 8
        self.theme_picker_item_rects = []

        self.theme_picker_scroll = max(0, min(self.theme_picker_scroll, self._theme_picker_max_scroll(list_rect.height, item_h, gap)))
        self._theme_picker_ensure_visible(list_rect.height, item_h, gap)

        self.screen.set_clip(list_rect)
        for idx, name in enumerate(themes):
            y = list_rect.y + idx * (item_h + gap) - self.theme_picker_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue

            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.theme_picker_item_rects.append((r, idx))
            selected = idx == self.theme_picker_selected

            bg = (35, 55, 90, 220) if selected else (18, 24, 40, 170)
            border = retro_style.accent if selected else (60, 70, 90)
            pygame.draw.rect(self.screen, bg, r, border_radius=10)
            pygame.draw.rect(self.screen, border, r, 2 if selected else 1, border_radius=10)

            text_font = retro_style.get_font(22, bold=selected)
            txt = text_font.render(str(name), True, (255, 255, 255) if selected else (205, 215, 235))
            self.screen.blit(txt, (r.x + 14, r.y + (r.height - txt.get_height()) // 2))

        self.screen.set_clip(None)

        total_h = len(themes) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(panel_rect.right - 12, list_rect.y, 6, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.theme_picker_scroll, total_h, list_rect.height)

        hint = subtitle_font.render(t('theme_picker_hint'), True, (140, 160, 190))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))

    def sync_from_settings_manager(self):
        """SettingsManager'daki güncel değerleri ekrana yansıt.

        Not: Pause menüsü gibi başka yerlerden ayarlar değiştirildiğinde,
        SettingsScreen içindeki cache'lenmiş alanların güncel kalması için.
        """
        if not self.settings_manager:
            return

        # Ses ayarları
        self.music_enabled = self.settings_manager.get('music_enabled', self.music_enabled)
        self.music_volume = self.settings_manager.get('music_volume', self.music_volume)
        self.sound_enabled = self.settings_manager.get('sound_enabled', self.sound_enabled)
        self.sfx_volume = self.settings_manager.get('sfx_volume', self.sfx_volume)
        self.mute_all = self.settings_manager.get('mute_all', self.mute_all)

        # Diğer sık kullanılan ayarlar
        self.effects_enabled = self.settings_manager.get('effects_enabled', self.effects_enabled)
        self.background_enabled = self.settings_manager.get('background_enabled', self.background_enabled)
        self.menu_music = self.settings_manager.get('menu_music', self.menu_music)
        self.game_music = self.settings_manager.get('game_music', self.game_music)
        self.debug_mode = self.settings_manager.get('debug_mode', self.debug_mode)
        self.card_mode_debug = self.settings_manager.get('card_mode_debug', self.card_mode_debug)

        # Gizli debug ayarları görünürlüğü değiştiyse listeyi güncelle
        show_debug = bool(self.settings_manager.get('show_debug_settings', False))
        if show_debug != getattr(self, '_show_debug_settings', False):
            self._show_debug_settings = show_debug
            prev_key = None
            try:
                prev_key = self.option_keys[self.selected]
            except Exception:
                prev_key = None
            self._update_options()
            self._update_hints()
            # mümkünse aynı seçili öğede kal
            if prev_key and prev_key in getattr(self, 'option_keys', []):
                self.selected = self.option_keys.index(prev_key)
            else:
                self.selected = max(0, min(self.selected, len(self.options) - 1))

        # Dil değiştiyse seçenek listelerini güncelle
        lang = self.settings_manager.get('language', self.current_language)
        if lang != self.current_language:
            self.current_language = lang
            set_language(self.current_language)
            apply_language_ui_profile(self.current_language)
            self._refresh_fonts()
            self._update_options()
            self._update_hints()

    def _get_cached_pct_surface(self, pct: int, for_music: bool) -> pygame.Surface:
        pct = max(0, min(100, int(pct)))
        if for_music:
            if self._music_pct_last != pct or self._music_pct_surf is None:
                self._music_pct_last = pct
                self._music_pct_surf = self.font_value_small.render(f'{pct}%', True, (235, 245, 255))
            return self._music_pct_surf
        else:
            if self._sfx_pct_last != pct or self._sfx_pct_surf is None:
                self._sfx_pct_last = pct
                self._sfx_pct_surf = self.font_value_small.render(f'{pct}%', True, (235, 245, 255))
            return self._sfx_pct_surf

    def _draw_volume_slider(self, card_rect: pygame.Rect, ratio: float, color: tuple[int, int, int], selected: bool, pct_surf: pygame.Surface) -> None:
        """Draw an ASCII-arrow + segmented bar slider inside the settings card."""
        ratio = max(0.0, min(1.0, float(ratio)))

        # Keep slider on the right side, away from the label
        area_right = card_rect.right - 22
        area_left = max(card_rect.x + 260, card_rect.right - 260)
        cy = card_rect.centery

        arrow_font = retro_style.get_font(20, bold=True)
        arrow_color = retro_style.primary if selected else (120, 140, 170)
        left_arrow = arrow_font.render('<', True, arrow_color)
        right_arrow = arrow_font.render('>', True, arrow_color)

        # Place right arrow
        right_arrow_rect = right_arrow.get_rect()
        right_arrow_rect.center = (area_right - right_arrow_rect.width // 2, cy)
        self.screen.blit(right_arrow, right_arrow_rect)

        # Place percent text just left of right arrow
        pct_rect = pct_surf.get_rect()
        pct_rect.midright = (right_arrow_rect.left - 10, cy)
        self.screen.blit(pct_surf, pct_rect)

        # Place left arrow
        left_arrow_rect = left_arrow.get_rect()
        left_arrow_rect.center = (area_left + left_arrow_rect.width // 2, cy)
        self.screen.blit(left_arrow, left_arrow_rect)

        # Bar area between arrows and percent
        bar_left = left_arrow_rect.right + 12
        bar_right = pct_rect.left - 12
        if bar_right <= bar_left + 40:
            return

        bar_h = 12
        bar_rect = pygame.Rect(bar_left, cy - bar_h // 2, bar_right - bar_left, bar_h)

        # Track background
        pygame.draw.rect(self.screen, (30, 35, 55), bar_rect, border_radius=4)
        pygame.draw.rect(self.screen, (60, 70, 90), bar_rect, 1, border_radius=4)

        # Segmented fill (10 segments) with smooth partial segment
        segments = 10
        gap = 2
        usable_w = bar_rect.width - gap * (segments - 1)
        if usable_w <= segments:
            return
        seg_w = usable_w / segments
        seg_h = bar_rect.height - 4
        seg_y = bar_rect.y + 2

        filled = ratio * segments
        full = int(filled)
        frac = filled - full

        for s in range(segments):
            sx = bar_rect.x + int(round(s * (seg_w + gap)))
            w = int(round(seg_w))
            seg_rect = pygame.Rect(sx, seg_y, w, seg_h)
            pygame.draw.rect(self.screen, (70, 85, 110), seg_rect, 1, border_radius=2)

            if s < full:
                pygame.draw.rect(self.screen, color, seg_rect, border_radius=2)
            elif s == full and frac > 0:
                partial_w = max(1, int(seg_rect.width * frac))
                partial_rect = pygame.Rect(seg_rect.x, seg_rect.y, partial_w, seg_rect.height)
                pygame.draw.rect(self.screen, color, partial_rect, border_radius=2)
    
    def _update_options(self):
        """Dile göre ayar seçeneklerini güncelle"""
        show_debug = bool(self.settings_manager.get('show_debug_settings', False)) if self.settings_manager else False
        self._show_debug_settings = show_debug

        # Seçenekler artık anahtarlarla yönetilir; label listesi dile göre üretilir.
        base_keys = [
            # Gameplay & Controls
            'gameplay',
            'controls',
            
            # Visuals & Customization
            'graphics',
            'theme',
            'block_styles',
            'piece_workshop',
            
            # Audio
            'music',
            'music_volume',
            'tracks',
            'sound',
            'sfx_volume',
            'mute_all',
            
            # System
            'language',
        ]
        if show_debug:
            base_keys += ['debug_mode', 'card_debug']
        base_keys += ['back']
        self.option_keys = base_keys

        # Localization sisteminden çevirileri al
        # Her key için önce doğrudan key'i dene, sonra özel key isimlerini dene
        key_to_translation = {
            'controls': 'controls',
            'gameplay': 'gameplay',
            'mute_all': 'mute_all',
            'music': 'music',
            'music_volume': 'music_volume',
            'sound': 'sound_effects',
            'sfx_volume': 'sfx_volume',
            'tracks': 'tracks_label',
            'graphics': 'graphics',
            'theme': 'theme',
            'block_styles': 'block_styles',
            'piece_workshop': 'piece_workshop',
            'language': 'language_setting',
            'debug_mode': 'debug_mode',
            'card_debug': 'card_debug',
            'back': 'back',
        }
        
        # Fallback değerleri (çeviri bulunamazsa)
        fallbacks = {
            'controls': 'Controls',
            'gameplay': 'Gameplay',
            'mute_all': 'Mute All',
            'music': 'Music',
            'music_volume': 'Music Volume',
            'sound': 'Sound Effects',
            'sfx_volume': 'SFX Volume',
            'tracks': 'Tracks',
            'graphics': 'Graphics',
            'theme': 'Theme',
            'block_styles': 'Block Styles',
            'piece_workshop': 'Piece Workshop',
            'language': 'Language',
            'debug_mode': 'Debug Mode',
            'card_debug': 'Card Debug',
            'back': 'Back',
        }
        
        self.options = [get_text(key_to_translation.get(k, k), fallbacks.get(k, k)) for k in self.option_keys]
    
    def _update_hints(self):
        """Dile göre ipuçlarını güncelle - localization sisteminden çevirileri al"""
        # Fallback değerleri (çeviri bulunamazsa)
        fallbacks = {
            'controls': 'Change single player and PvP keys',
            'gameplay': 'DAS, movement speed, drop speed settings',
            'mute_all': 'Mute/unmute all sounds (M key)',
            'music': 'Toggle music on/off',
            'music_volume': 'Adjust music volume (Left/Right)',
            'sound': 'Toggle sound effects on/off',
            'sfx_volume': 'Adjust SFX volume (Left/Right)',
            'tracks': 'Manage music playlists',
            'graphics': 'Detailed graphics and window settings',
            'theme': 'Block colors and theme palette',
            'block_styles': 'Open tetromino color/texture editor',
            'piece_workshop': 'Create custom pieces (max 7 blocks)',
            'language': 'Change game language',
            'debug_mode': 'Show debug messages in terminal',
            'card_debug': 'Show all cards in card selection (debug)',
            'back': 'Back to main menu',
        }
        
        keys = getattr(self, 'option_keys', [])
        self.option_hints = [get_text(f'hint_{k}', fallbacks.get(k, '')) for k in keys]

    def _open_music_hub(self) -> None:
        self.music_hub_open = True
        self.music_hub_selected = 0
        self.music_hub_item_rects = []
        # close other overlays
        self.theme_picker_open = False
        self._close_language_panel()
        self.music_track_picker_open = False
        self.mode_music_overlay_open = False

    def _close_music_hub(self) -> None:
        self.music_hub_open = False
        self.music_hub_item_rects = []
        self.music_track_picker_open = False
        self.music_track_picker_item_rects = []
        self.mode_music_overlay_open = False

    def _open_music_track_picker(self, target: str) -> None:
        self.music_track_picker_open = True
        self.music_track_picker_target = target
        self.music_track_picker_scroll = 0
        self.music_track_picker_item_rects = []

        current = self.menu_music if target == 'menu' else self.game_music
        # preselect current
        idx = 0
        for i, name in enumerate(self.music_types or []):
            if str(name).lower() == str(current).lower():
                idx = i
                break
        self.music_track_picker_selected = idx

    def _close_music_track_picker(self) -> None:
        self.music_track_picker_open = False
        self.music_track_picker_target = None
        self.music_track_picker_item_rects = []

    def _music_track_picker_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self.music_types) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _music_track_picker_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self.music_track_picker_selected * (item_h + gap)
        if y < self.music_track_picker_scroll:
            self.music_track_picker_scroll = y
        elif y > self.music_track_picker_scroll + visible_h - item_h:
            self.music_track_picker_scroll = y - (visible_h - item_h)
        self.music_track_picker_scroll = max(0, min(self.music_track_picker_scroll, self._music_track_picker_max_scroll(visible_h, item_h, gap)))

    def _apply_music_choice(self, target: str, track_name: str):
        if not track_name:
            return None
        if target == 'menu':
            self.menu_music = track_name
            self.settings_manager.set('menu_music', self.menu_music)
            return 'change_menu_music'
        if target == 'game':
            self.game_music = track_name
            self.settings_manager.set('game_music', self.game_music)
            return 'change_game_music'
        return None

    def _handle_music_hub_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_music_hub()
                return None
            if event.key == pygame.K_UP:
                self.music_hub_selected = (self.music_hub_selected - 1) % 3
                return None
            if event.key == pygame.K_DOWN:
                self.music_hub_selected = (self.music_hub_selected + 1) % 3
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                if self.music_hub_selected == 0:
                    self._open_music_track_picker('menu')
                elif self.music_hub_selected == 1:
                    self._open_music_track_picker('game')
                else:
                    # Mode music opens as an overlay modal (ESC returns here)
                    self.mode_music_overlay.screen = self.screen
                    try:
                        self.mode_music_overlay._refresh_overrides()
                    except Exception:
                        pass
                    self.mode_music_overlay_open = True
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            step = -1 if event.y > 0 else 1
            self.music_hub_selected = (self.music_hub_selected + step) % 3
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.music_hub_item_rects:
                if rect.collidepoint(pos):
                    self.music_hub_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.music_hub_item_rects:
                if rect.collidepoint(pos):
                    self.music_hub_selected = idx
                    if idx == 0:
                        self._open_music_track_picker('menu')
                        return None
                    if idx == 1:
                        self._open_music_track_picker('game')
                        return None
                    self.mode_music_overlay.screen = self.screen
                    try:
                        self.mode_music_overlay._refresh_overrides()
                    except Exception:
                        pass
                    self.mode_music_overlay_open = True
                    return None
            # outside closes
            self._close_music_hub()
            return None

        return None

    def _handle_music_track_picker_input(self, event):
        if not self.music_types:
            self._close_music_track_picker()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_music_track_picker()
                return None
            if event.key == pygame.K_UP:
                self.music_track_picker_selected = (self.music_track_picker_selected - 1) % len(self.music_types)
                return None
            if event.key == pygame.K_DOWN:
                self.music_track_picker_selected = (self.music_track_picker_selected + 1) % len(self.music_types)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if not isinstance(self.music_track_picker_target, str):
                    self._close_music_track_picker()
                    return None
                chosen = self.music_types[self.music_track_picker_selected]
                action = self._apply_music_choice(self.music_track_picker_target, chosen)
                self._close_music_track_picker()
                return action
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        elif event.type == pygame.MOUSEWHEEL:
            self.music_track_picker_scroll -= event.y * 36
            self.music_track_picker_scroll = max(0, self.music_track_picker_scroll)
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.music_track_picker_item_rects:
                if rect.collidepoint(pos):
                    self.music_track_picker_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self.music_track_picker_item_rects:
                if rect.collidepoint(pos):
                    self.music_track_picker_selected = idx
                    if not isinstance(self.music_track_picker_target, str):
                        self._close_music_track_picker()
                        return None
                    chosen = self.music_types[self.music_track_picker_selected]
                    action = self._apply_music_choice(self.music_track_picker_target, chosen)
                    self._close_music_track_picker()
                    return action
            # outside closes
            self._close_music_track_picker()
            return None

        return None

    def _draw_music_hub(self) -> None:
        width, height = self.screen.get_size()

        # Dim background
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_w = min(720, width - 120)
        panel_h = min(420, height - 200)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('tracks'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        override_count = len(self.settings_manager.get_mode_music_overrides()) if self.settings_manager else 0
        sub = subtitle_font.render(
            f"Ana: {self.menu_music}   Oyun: {self.game_music}   Mod: {override_count}",
            True,
            (170, 190, 220),
        )
        self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 50))

        items = [
            (t('menu_music'), self.menu_music),
            (t('game_music'), self.game_music),
            (t('mode_music_label'),
             t('custom_count').format(count=override_count) if override_count else t('default')),
        ]

        start_y = panel_rect.y + 96
        item_h = 64
        gap = 12
        self.music_hub_item_rects = []
        for idx, (label, value) in enumerate(items):
            r = pygame.Rect(panel_rect.x + 18, start_y + idx * (item_h + gap), panel_rect.width - 36, item_h)
            self.music_hub_item_rects.append((r, idx))
            selected = idx == self.music_hub_selected
            color_code = retro_style.accent if idx == 2 else retro_style.primary
            retro_style.draw_uniform_button(
                self.screen,
                r,
                label,
                sub_text=str(value),
                color_code=color_code,
                selected=selected,
            )

        hint = subtitle_font.render(t('hint_select_open_close'), True, (140, 160, 190))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))

    def _draw_music_track_picker(self) -> None:
        width, height = self.screen.get_size()

        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_w = min(720, width - 120)
        panel_h = min(520, height - 160)
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title_txt = t('menu_music').upper() if self.music_track_picker_target == 'menu' else t('game_music').upper()
        title = title_font.render(title_txt, True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        current = self.menu_music if self.music_track_picker_target == 'menu' else self.game_music
        sub = subtitle_font.render(t('active_label').format(current=current), True, (170, 190, 220))
        self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 50))

        list_top = panel_rect.y + 86
        list_left = panel_rect.x + 18
        list_right = panel_rect.right - 18
        list_bottom = panel_rect.bottom - 60
        list_rect = pygame.Rect(list_left, list_top, list_right - list_left, list_bottom - list_top)

        item_h = 44
        gap = 8
        self.music_track_picker_item_rects = []
        self.music_track_picker_scroll = max(0, min(self.music_track_picker_scroll, self._music_track_picker_max_scroll(list_rect.height, item_h, gap)))
        self._music_track_picker_ensure_visible(list_rect.height, item_h, gap)

        self.screen.set_clip(list_rect)
        for idx, name in enumerate(self.music_types):
            y = list_rect.y + idx * (item_h + gap) - self.music_track_picker_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue

            r = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self.music_track_picker_item_rects.append((r, idx))

            selected = idx == self.music_track_picker_selected
            bg = (35, 55, 90, 220) if selected else (18, 24, 40, 170)
            border = retro_style.accent if selected else (60, 70, 90)
            pygame.draw.rect(self.screen, bg, r, border_radius=10)
            pygame.draw.rect(self.screen, border, r, 2 if selected else 1, border_radius=10)

            text_font = retro_style.get_font(22, bold=selected)
            txt = text_font.render(str(name), True, (255, 255, 255) if selected else (205, 215, 235))
            self.screen.blit(txt, (r.x + 14, r.y + (r.height - txt.get_height()) // 2))

        self.screen.set_clip(None)

        total_h = len(self.music_types) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(panel_rect.right - 12, list_rect.y, 6, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self.music_track_picker_scroll, total_h, list_rect.height)

        hint = subtitle_font.render(t('hint_select_apply_close'), True, (140, 160, 190))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))
        self.screen.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 36))
    
    def _build_music_list(self):
        """Yerleşik ve harici müzikleri içeren dinamik liste oluştur"""
        # Yerleşik (sentez) müzikler kaldırıldı: sadece harici dosyalar listelenir.
        builtin = []
        
        # Harici müzikleri sound_manager'dan al
        external = []
        if self.sound_manager:
            try:
                tracks = self.sound_manager.get_available_tracks()
                for track_info in tracks.get('external', []):
                    name = track_info.get('name', '')
                    # Yerleşik listede yoksa ekle
                    display_name = name.replace('_', ' ').title()
                    if display_name.lower() not in [b.lower() for b in builtin]:
                        external.append(display_name)
            except Exception as e:
                print(f"⚠️ Harici müzik listesi alınamadı: {e}")
        
        # music/ klasöründeki dosyaları da tara
        try:
            from pathlib import Path
            music_dir = Path(__file__).parent.parent / 'music'
            if music_dir.exists():
                supported = {'.mp3', '.wav', '.ogg', '.flac'}
                for f in music_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in supported:
                        display_name = f.stem.replace('_', ' ').title()
                        # Zaten listede yoksa ekle
                        all_names = [b.lower() for b in builtin + external]
                        if display_name.lower() not in all_names:
                            external.append(display_name)
        except Exception as e:
            print(f"⚠️ Music klasörü taranamadı: {e}")
        
        return builtin + sorted(external)
    
    def refresh_music_list(self):
        """Müzik listesini yenile (yeni dosya eklendiğinde)"""
        self.music_types = self._build_music_list()
    
    def handle_input(self, event):
        """Ayar girdilerini işle (klavye + mouse)"""
        if self.theme_picker_open:
            return self._handle_theme_picker_input(event)

        if self.music_hub_open:
            if self.mode_music_overlay_open:
                action = self.mode_music_overlay.handle_input_overlay(event)
                if action == 'close':
                    self.mode_music_overlay_open = False
                    return None
                return action
            if self.music_track_picker_open:
                return self._handle_music_track_picker_input(event)
            return self._handle_music_hub_input(event)

        if self.language_panel_open:
            action = self._handle_language_panel_input(event)
            if action is not None:
                return action
            # Panel açıkken diğer inputları blokla
            if self.language_panel_open:
                return None

        # Klavye kontrolü
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
                self._ensure_visible()
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
                self._ensure_visible()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                key = None
                try:
                    key = self.option_keys[self.selected]
                except Exception:
                    key = None

                if key == 'language' and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):  # Language
                    # Dili değiştir
                    lang_idx = SUPPORTED_LANGUAGES.index(self.current_language) if self.current_language in SUPPORTED_LANGUAGES else 0
                    if event.key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                        lang_idx = (lang_idx + 1) % len(SUPPORTED_LANGUAGES)
                    else:
                        lang_idx = (lang_idx - 1) % len(SUPPORTED_LANGUAGES)
                    self.current_language = SUPPORTED_LANGUAGES[lang_idx]
                    set_language(self.current_language)
                    apply_language_ui_profile(self.current_language)
                    self._refresh_fonts()
                    self.settings_manager.set('language', self.current_language)
                    # Dil değiştiğinde menü metinlerini güncelle
                    self._update_options()
                    self._update_hints()
                    return 'language_changed'
                elif key == 'music':  # Music toggle
                    self.music_enabled = not self.music_enabled
                    self.settings_manager.set('music_enabled', self.music_enabled)
                    return 'toggle_music'
                elif key == 'music_volume' and event.key in (pygame.K_LEFT, pygame.K_RIGHT):  # Music Volume
                    delta = 0.1 if event.key == pygame.K_RIGHT else -0.1
                    self.music_volume = max(0.0, min(1.0, self.music_volume + delta))
                    self.settings_manager.set('music_volume', self.music_volume)
                    return 'change_music_volume'
                elif key == 'sound':  # Sound Effects toggle
                    self.sound_enabled = not self.sound_enabled
                    self.settings_manager.set('sound_enabled', self.sound_enabled)
                    return 'toggle_sound'
                elif key == 'sfx_volume' and event.key in (pygame.K_LEFT, pygame.K_RIGHT):  # SFX Volume
                    delta = 0.1 if event.key == pygame.K_RIGHT else -0.1
                    self.sfx_volume = max(0.0, min(1.0, self.sfx_volume + delta))
                    self.settings_manager.set('sfx_volume', self.sfx_volume)
                    return 'change_sfx_volume'
                elif key == 'tracks' and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):  # Tracks / Müzikler
                    return 'mode_music'
                elif key == 'mute_all':  # Mute All
                    self.mute_all = not self.mute_all
                    self.settings_manager.set('mute_all', self.mute_all)
                    return 'toggle_mute'
                elif key == 'theme' and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):  # Theme
                    # Theme selection now uses a picker overlay (Mode Music style)
                    self._open_theme_picker()
                elif key == 'controls' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Controls
                    return 'controls'
                elif key == 'block_styles' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Block Styles
                    return 'block_styles'
                elif key == 'piece_workshop' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Piece Workshop
                    return 'piece_workshop'
                elif key == 'graphics' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Graphics
                    return 'graphics'
                elif key == 'gameplay' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Gameplay
                    return 'gameplay'
                elif key == 'guide' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Guide
                    return 'guide'
                elif key == 'debug_mode':  # Debug Mode
                    self.debug_mode = not self.debug_mode
                    self.settings_manager.set('debug_mode', self.debug_mode)
                    return 'toggle_debug'
                elif key == 'card_debug':  # Card Debug
                    self.card_mode_debug = not self.card_mode_debug
                    self.settings_manager.set('card_mode_debug', self.card_mode_debug)
                    return 'toggle_card_mode_debug'
                elif key == 'back' and event.key in (pygame.K_RETURN, pygame.K_SPACE):  # Back
                    return 'back'
            elif event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        
        # Mouse scroll
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            width, height = self.screen.get_size()
            start_y = 150
            card_spacing = 92
            visible_area = height - start_y - 120
            total_content = len(self.options) * card_spacing
            max_scroll = max(0, total_content - max(visible_area, 0))
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        
        # Mouse kontrolü
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Sol tık
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected = i  # Seçimi güncelle
                        # Index'e göre işlem yap
                        key = None
                        try:
                            key = self.option_keys[i]
                        except Exception:
                            key = None

                        # Slider rows: allow mouse click to set volume (matches the drawn slider UI).
                        if key in ('music_volume', 'sfx_volume'):
                            arrow_font = retro_style.get_font(20, bold=True)
                            left_w = arrow_font.size('<')[0]
                            right_w = arrow_font.size('>')[0]
                            area_right = rect.right - 22
                            area_left = max(rect.x + 260, rect.right - 260)
                            if key == 'music_volume':
                                pct = int(round(self._music_volume_vis * 100))
                                pct_w = self.font_value_small.size(f'{pct}%')[0]
                            else:
                                pct = int(round(self._sfx_volume_vis * 100))
                                pct_w = self.font_value_small.size(f'{pct}%')[0]

                            bar_left = area_left + left_w + 12
                            bar_right = area_right - right_w - 10 - pct_w - 12
                            if bar_right > bar_left and bar_left <= mouse_pos[0] <= bar_right:
                                ratio = (mouse_pos[0] - bar_left) / float(bar_right - bar_left)
                                ratio = max(0.0, min(1.0, ratio))
                                if key == 'music_volume':
                                    self.music_volume = ratio
                                    self.settings_manager.set('music_volume', self.music_volume)
                                    return 'change_music_volume'
                                else:
                                    self.sfx_volume = ratio
                                    self.settings_manager.set('sfx_volume', self.sfx_volume)
                                    return 'change_sfx_volume'

                        if key == 'language':  # Language
                            if self.language_panel_open and self.language_panel_anchor_rect and self.language_panel_anchor_rect == rect:
                                self._close_language_panel()
                            else:
                                self._open_language_panel(rect)
                            return None
                        elif key == 'music':  # Music
                            self.music_enabled = not self.music_enabled
                            self.settings_manager.set('music_enabled', self.music_enabled)
                            return 'toggle_music'
                        elif key == 'sound':  # Sound Effects
                            self.sound_enabled = not self.sound_enabled
                            self.settings_manager.set('sound_enabled', self.sound_enabled)
                            return 'toggle_sound'
                        elif key == 'mute_all':  # Mute All
                            self.mute_all = not self.mute_all
                            self.settings_manager.set('mute_all', self.mute_all)
                            return 'toggle_mute'
                        elif key == 'tracks':  # Tracks / Müzikler
                            return 'mode_music'
                        elif key == 'theme':  # Theme
                            self._open_theme_picker()
                            return None
                        elif key == 'controls':  # Controls
                            return 'controls'
                        elif key == 'block_styles':  # Block Styles
                            return 'block_styles'
                        elif key == 'piece_workshop':  # Piece Workshop
                            return 'piece_workshop'
                        elif key == 'graphics':  # Graphics
                            return 'graphics'
                        elif key == 'gameplay':  # Gameplay
                            return 'gameplay'
                        elif key == 'guide':  # Guide
                            return 'guide'
                        elif key == 'debug_mode':  # Debug Mode
                            self.debug_mode = not self.debug_mode
                            self.settings_manager.set('debug_mode', self.debug_mode)
                            return 'toggle_debug'
                        elif key == 'card_debug':  # Card Debug
                            self.card_mode_debug = not self.card_mode_debug
                            self.settings_manager.set('card_mode_debug', self.card_mode_debug)
                            return 'toggle_card_mode_debug'
                        elif key == 'back':  # Back
                            return 'back'
        
        return None
    
    def _ensure_visible(self):
        """Seçili öğenin görünür olmasını sağla"""
        width, height = self.screen.get_size()
        start_y = 150
        card_spacing = 92
        card_height = 74
        top_visible = 130
        bottom_visible = height - 120 - card_height

        item_y = start_y + self.selected * card_spacing - self.scroll_offset
        if item_y < top_visible:
            self.scroll_offset -= (top_visible - item_y)
        elif item_y > bottom_visible:
            self.scroll_offset += (item_y - bottom_visible)

        visible_area = height - start_y - 120
        total_content = len(self.options) * card_spacing
        max_scroll = max(0, total_content - max(visible_area, 0))
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
    
    def draw(self):
        """Ayarlar ekranını çiz - Modern tasarım"""
        width, height = self.screen.get_size()

        # Smooth slider animations (volume) with time-based interpolation
        now_ms = pygame.time.get_ticks()
        dt = (now_ms - getattr(self, '_anim_last_tick', now_ms)) / 1000.0
        self._anim_last_tick = now_ms
        dt = max(0.0, min(0.05, dt))
        speed = 18.0
        self._music_volume_vis += (self.music_volume - self._music_volume_vis) * min(1.0, dt * speed)
        self._sfx_volume_vis += (self.sfx_volume - self._sfx_volume_vis) * min(1.0, dt * speed)

        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        # Grid efekti kaldırıldı
        
        # 3D Başlık (shadow efekti)
        title_text = t('panel_settings')
        for offset in range(6, 0, -2):
            shadow_alpha = int(100 - offset * 15)
            shadow = self.font_title.render(title_text, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(width // 2 + offset, 60 + offset))
            self.screen.blit(shadow, shadow_rect)
        
        title = self.font_title.render(title_text, True, (100, 200, 255))
        title_rect = title.get_rect(center=(width // 2, 60))
        self.screen.blit(title, title_rect)
        
        # Alt çizgi gradient
        for i in range(3):
            line_y = 105 + i
            line_color = (50 + i * 20, 150 + i * 20, 200 + i * 20)
            pygame.draw.line(self.screen, line_color, 
                           (width // 2 - 150, line_y), (width // 2 + 150, line_y), 1)
        
        # Dil bazlı değerler
        on_text = t('on')
        off_text = t('off')
        
        # Ayar seçenekleri - modern kart tasarımı (with left color strip and new toggle/selector visuals)
        self.option_rects = []
        start_y = 150
        card_width = min(620, width - 120)
        card_height = 74
        card_spacing = 92
        override_count = len(self.settings_manager.get_mode_music_playlists())
        
        for i, option in enumerate(self.options):
            y_pos = start_y + i * card_spacing - self.scroll_offset
            
            # Ekran dışındaysa çizme
            if y_pos < 130 or y_pos > height - 120:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue
            
            is_selected = i == self.selected
            
            # Kart pozisyonu
            card_x = (width - card_width) // 2
            card_rect = pygame.Rect(card_x, y_pos, card_width, card_height)
            self.option_rects.append(card_rect)

            # Use unified option card rendering (key-based)
            label = option
            value = ''
            value_color = WHITE
            key = None
            try:
                key = self.option_keys[i]
            except Exception:
                key = None

            if key == 'mute_all':  # Mute All
                # draw_setting_row(kind='toggle') yalnızca sade ON/OFF ve AÇIK/KAPALI metnini "ON" sayar.
                # Emoji/simge eklenirse rozet hep "KAPALI" görünür.
                value = on_text if self.mute_all else off_text
                value_color = (255, 100, 100) if self.mute_all else (100, 255, 100)
            elif key == 'music':  # Music
                value = on_text if self.music_enabled else off_text
                value_color = (100, 255, 100) if self.music_enabled else (255, 100, 100)
            elif key == 'music_volume':  # Music Volume
                pct = int(round(self._music_volume_vis * 100))
                value = ''
                value_color = (100, 200, 255)
            elif key == 'sound':  # Sound Effects
                value = on_text if self.sound_enabled else off_text
                value_color = (100, 255, 100) if self.sound_enabled else (255, 100, 100)
            elif key == 'sfx_volume':  # SFX Volume
                pct = int(round(self._sfx_volume_vis * 100))
                value = ''
                value_color = (255, 200, 100)
            elif key == 'tracks':  # Tracks / Müzikler
                menu_list = self.settings_manager.get_menu_music_playlist()
                game_list = self.settings_manager.get_game_music_playlist()
                if override_count:
                    mode_part = t('settings_tracks_custom', count=override_count)
                else:
                    mode_part = t('settings_tracks_default')
                value = f"{len(menu_list)} / {len(game_list)} / {mode_part}"
                value_color = (150, 200, 255)
            elif key == 'gameplay':  # Gameplay
                value = t('settings_gameplay_hint')
                value_color = (150, 255, 200)
            elif key == 'controls':  # Controls
                value = t('settings_controls_hint')
                value_color = (150, 200, 255)
            elif key == 'graphics':  # Graphics
                value = ''
                value_color = (150, 200, 255)
            elif key == 'theme':  # Theme
                theme_name = getattr(self.theme_manager, 'theme_name', '') if self.theme_manager else ''
                value = f'{theme_name}'
                value_color = (255, 200, 100)
            elif key == 'block_styles':  # Block Styles
                value = t('settings_block_styles_hint')
                value_color = (150, 200, 255)
            elif key == 'piece_workshop':  # Piece Workshop
                value = t('settings_piece_workshop_hint')
                value_color = (150, 200, 255)
            elif key == 'language':  # Language
                lang_name = get_language_name(self.current_language)
                value = f'{lang_name}'
                value_color = (100, 255, 200)
            elif key == 'debug_mode':  # Debug Mode
                value = on_text if self.debug_mode else off_text
                value_color = (100, 255, 100) if self.debug_mode else (255, 100, 100)
            elif key == 'card_debug':  # Card Debug
                value = on_text if self.card_mode_debug else off_text
                value_color = (100, 255, 100) if self.card_mode_debug else (255, 100, 100)
            
            # Determine strip color and kind for this setting
            # default kinds
            kind = 'default'
            strip_color = (100, 100, 110)
            if key == 'graphics':  # Graphics
                strip_color = (112, 160, 255)  # blue
            elif key == 'gameplay':  # Gameplay
                strip_color = (100, 220, 150)  # green
                kind = 'submenu'
            elif key == 'controls':  # Controls
                strip_color = (255, 160, 60)  # orange
                kind = 'submenu'
            elif key in ('debug_mode', 'card_debug'):  # Debug options
                strip_color = (220, 80, 80)  # red
            elif key in ('mute_all', 'music', 'sound', 'debug_mode', 'card_debug'):  # Toggle options
                kind = 'toggle'
            elif key in ('music_volume', 'sfx_volume'):
                kind = 'slider'
            elif key in ('controls', 'gameplay', 'tracks', 'graphics', 'theme', 'block_styles', 'piece_workshop'):
                kind = 'submenu'
            elif value:
                kind = 'selector'

            label_color = (255, 255, 255) if is_selected else (200, 200, 200)
            # draw with new helper
            retro_style.draw_setting_row(
                self.screen,
                card_rect,
                label,
                value,
                selected=is_selected,
                label_color=label_color,
                value_color=value_color,
                strip_color=strip_color,
                kind=kind,
            )

            # Custom slider visuals for volume rows (no special unicode blocks)
            if key == 'music_volume':
                pct_surf = self._get_cached_pct_surface(int(round(self._music_volume_vis * 100)), for_music=True)
                self._draw_volume_slider(card_rect, self._music_volume_vis, (100, 200, 255), is_selected, pct_surf)
            elif key == 'sfx_volume':
                pct_surf = self._get_cached_pct_surface(int(round(self._sfx_volume_vis * 100)), for_music=False)
                self._draw_volume_slider(card_rect, self._sfx_volume_vis, (255, 200, 100), is_selected, pct_surf)
            
            # (Label/value already drawn by draw_option_card)
        
        # Scrollbar (modern neon design)
        total_content = len(self.options) * card_spacing
        visible_area = height - 150 - 120
        max_scroll = max(0, total_content - visible_area)
        if max_scroll > 0:
            scrollbar_rect = pygame.Rect(
                width - 36,
                150,
                12,
                visible_area
            )
            retro_style.draw_scrollbar(
                self.screen,
                scrollbar_rect,
                self.scroll_offset,
                total_content,
                visible_area
            )
        # Açıklama kutusu - glassmorphism bottom panel: re-add decl if missing
        desc_box_height = 60
        desc_box = pygame.Surface((width - 140, desc_box_height), pygame.SRCALPHA)
        desc_box.fill((18, 22, 34, 180))
        desc_rect = desc_box.get_rect(center=(width // 2, height - desc_box_height // 2 - 10))
        pygame.draw.rect(desc_box, (255, 255, 255, 12), desc_box.get_rect(), 1, border_radius=14)
        self.screen.blit(desc_box, desc_rect.topleft)
        
        # Gradient üst çizgi
        for i in range(3):
            line_color = (100 + i * 30, 150 + i * 30, 255)
            pygame.draw.line(self.screen, line_color, 
                           (0, desc_rect.top - 5 + i), (width, desc_rect.top - 5 + i))
        
        # Seçili öğenin açıklamasını göster (option_hints'den)
        if self.selected < len(self.option_hints):
            desc_text = self.option_hints[self.selected]
        else:
            desc_text = ''
        desc_surf = self.font_small.render(desc_text, True, (220, 230, 255))
        desc_surf_rect = desc_surf.get_rect(center=desc_rect.center)
        self.screen.blit(desc_surf, desc_surf_rect)

        if self.language_panel_open:
            self._draw_language_panel()
        
        if self.music_hub_open:
            # Hub always remains the "previous window"
            self._draw_music_hub()
            if self.music_track_picker_open:
                self._draw_music_track_picker()
            elif self.mode_music_overlay_open:
                self.mode_music_overlay.screen = self.screen
                self.mode_music_overlay.draw_overlay()

        if self.theme_picker_open:
            self._draw_theme_picker()



class CreditsScreen:
    """Emeği Geçenler ekranı"""
    
    def __init__(self, screen):
        """Credits ekranını başlat"""
        self.screen = screen
        self._credits_ui_reference_size = self._get_credits_reference_size()
        self._credits_ui_size_signature = None
        self._credits_font_lang = None
        self._refresh_fonts(1.0)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.mouse_pos = (0, 0)

        # Cache static header surfaces (avoid per-frame font rendering)
        self._credits_cache_lang = None
        self._credits_title_text = ''
        self._credits_title_surf = None
        self._credits_title_glow_surf = None
        self._credits_subtitle_surf = None
        self._rebuild_header_cache()
        
        # Testçiler popup durumu
        self.testers_popup_open = False
        self.testers_card_rect = None
        
        # 3 ana kart - Geliştiriciler üstte büyük, diğerleri altta
        self.team_cards = [
            {
                'title': 'Arda Demirkan & Burak Yaşayan',
                'role_key': 'credits_role_founder',
                'role_color': (255, 180, 80),
                'desc_key': 'credits_desc_arda',
                'clickable': False,
                'wide': True  # Geniş kart
            },
            {
                'title_key': 'credits_supporters_title',
                'role_key': 'credits_supporters_role',
                'role_color': (100, 200, 255),
                'desc_key': 'credits_supporters_desc',
                'clickable': True
            },
            {
                'title': 'Suno AI',
                'role_key': 'credits_role_music',
                'role_color': (180, 100, 255),
                'desc_key': 'credits_desc_suno',
                'clickable': False
            },
        ]
        
        # Oyun testçileri listesi
        self.testers_list = [
            'Alpaslan Kibar',
            'Oğzuzhan Arı',
            'Cemal Koparan',
            'Tunahan Mazı',
            'Meda Sönmez',
            'Zeynep Öztürk',
            'Osman Bülbül',
            'Adem Akbıyık'
        ]
        
        # Özel teşekkürler
        self.special_thanks = [
            'credits_special_thanks_1',
            'credits_special_thanks_2',
            'credits_special_thanks_3',
        ]
        self._credits_mascot_left = None
        self._credits_mascot_right = None
        self._credits_mascot_loaded = False

    def _get_credits_reference_size(self) -> tuple[int, int]:
        try:
            info = pygame.display.Info()
            ref_w = int(getattr(info, 'current_w', 0) or 0)
            ref_h = int(getattr(info, 'current_h', 0) or 0)
        except Exception:
            ref_w, ref_h = 0, 0
        if ref_w <= 0 or ref_h <= 0:
            ref_w, ref_h = self.screen.get_size()
        return max(1, ref_w), max(1, ref_h)

    def _credits_ui_scale(self, min_scale: float = 0.62, max_scale: float = 1.05) -> float:
        width, height = self.screen.get_size()
        ref_w, ref_h = self._credits_ui_reference_size
        scale = min(float(width) / max(1.0, float(ref_w)), float(height) / max(1.0, float(ref_h)))
        return max(min_scale, min(max_scale, scale))

    def _credits_sx(self, value: int | float, minimum: int = 1) -> int:
        return max(minimum, int(round(float(value) * self._credits_ui_scale())))

    def _ensure_credits_metrics(self):
        lang = get_language()
        signature = (lang, int(self.screen.get_width()), int(self.screen.get_height()))
        if signature == self._credits_ui_size_signature:
            return
        self._credits_ui_size_signature = signature
        self._refresh_fonts(self._credits_ui_scale())
        self._rebuild_header_cache()

    def _load_credits_mascots(self):
        if self._credits_mascot_loaded:
            return
        self._credits_mascot_loaded = True
        left_candidates = [
            ROOT_DIR / 'assets' / 'maskot' / 'emegi_gecen_l.png',
            ROOT_DIR / 'assets' / 'maskot' / 'sos_maskot.png',
            ROOT_DIR / 'assets' / 'maskot' / 'kilavuz_nasiloynanir.png',
        ]
        right_candidates = [
            ROOT_DIR / 'assets' / 'maskot' / 'emegi_gecen_r.png',
            ROOT_DIR / 'assets' / 'maskot' / 'sos_maskotold.png',
            ROOT_DIR / 'assets' / 'maskot' / 'kilavuz_kartlar.png',
        ]

        def _load_first(paths: list[Path]) -> pygame.Surface | None:
            for path in paths:
                try:
                    if path.exists():
                        return pygame.image.load(str(path)).convert_alpha()
                except Exception:
                    continue
            return None

        self._credits_mascot_left = _load_first(left_candidates)
        self._credits_mascot_right = _load_first(right_candidates)

        if self._credits_mascot_left is None and self._credits_mascot_right is not None:
            self._credits_mascot_left = pygame.transform.flip(self._credits_mascot_right, True, False)
        elif self._credits_mascot_right is None and self._credits_mascot_left is not None:
            self._credits_mascot_right = pygame.transform.flip(self._credits_mascot_left, True, False)

    def _draw_mascot_panel(self, rect: pygame.Rect, image: pygame.Surface | None, scale_factor: float = 1.0) -> None:
        s = self._credits_sx
        inner = rect.inflate(-s(8), -s(8))
        if image is None:
            return

        iw, ih = image.get_size()
        if iw <= 0 or ih <= 0 or inner.width <= 4 or inner.height <= 4:
            return
        # Yüksekliği sabitle (en-boy oranı koru)
        ratio = inner.height / float(ih) * scale_factor
        draw_w = max(1, int(iw * ratio))
        draw_h = max(1, int(ih * ratio))
        # Genişlik paneli taşıyorsa genişliğe göre küçült
        max_w = int(inner.width * max(scale_factor, 1.0))
        if draw_w > max_w:
            ratio2 = max_w / float(draw_w)
            draw_w = max(1, int(draw_w * ratio2))
            draw_h = max(1, int(draw_h * ratio2))
        try:
            scaled = pygame.transform.smoothscale(image, (draw_w, draw_h))
        except Exception:
            scaled = pygame.transform.scale(image, (draw_w, draw_h))
        # Tabanları hizala: her iki maskot da aynı alt çizgide
        self.screen.blit(scaled, scaled.get_rect(midbottom=inner.midbottom))

    def _refresh_fonts(self, ui_scale: float = 1.0):
        self._credits_font_lang = get_language()
        scale = max(0.62, min(1.10, float(ui_scale)))
        fs = lambda base, mn: max(mn, int(round(base * scale)))
        self.font_title = retro_style.get_font(fs(48, 30), bold=True)
        self.font_subtitle = retro_style.get_font(fs(20, 13))
        self.font_section = retro_style.get_font(fs(28, 16), bold=True)
        self.font_name = retro_style.get_font(fs(24, 14), bold=True)
        self.font_role = retro_style.get_font(fs(16, 11), bold=True)
        self.font_body = retro_style.get_font(fs(16, 11), bold=False)
        self.font_small = retro_style.get_font(fs(14, 10), bold=False)
        self.font_footer = retro_style.get_font(fs(12, 9), bold=False)

    def _fullscreen_panel_scale(self) -> float:
        """Credits popup'ları için fullscreen referanslı ölçek."""
        scale = self._credits_ui_scale(min_scale=0.62, max_scale=1.15)
        return max(0.65, min(1.30, scale))

    def _get_testers_popup_rect(self) -> pygame.Rect:
        width, height = self.screen.get_size()
        popup_scale = self._fullscreen_panel_scale()
        popup_w = max(260, min(int(350 * popup_scale), width - max(50, int(90 * popup_scale))))
        popup_h = max(220, min(int(300 * popup_scale), height - max(70, int(110 * popup_scale))))
        return pygame.Rect((width - popup_w) // 2, (height - popup_h) // 2, popup_w, popup_h)

    def _rebuild_header_cache(self):
        self._credits_cache_lang = get_language()
        self._credits_title_text = t('credits_screen_title')
        self._credits_title_surf = self.font_title.render(self._credits_title_text, True, (80, 255, 200))
        self._credits_title_glow_surf = self.font_title.render(self._credits_title_text, True, (40, 200, 150))
        self._credits_title_glow_surf.set_alpha(90)
        self._credits_subtitle_surf = self.font_subtitle.render(t('credits_screen_subtitle'), True, (180, 200, 220))

    def handle_input(self, event):
        """Credits ekranı input handling"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.testers_popup_open:
                    self.testers_popup_open = False
                    return None
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
                
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Popup açıkken dışına tıklama kontrolü
            if self.testers_popup_open:
                popup_rect = self._get_testers_popup_rect()
                if not popup_rect.collidepoint(pos):
                    self.testers_popup_open = False
                return None
            
            # Testçiler kartına tıklama kontrolü
            if self.testers_card_rect and self.testers_card_rect.collidepoint(pos):
                self.testers_popup_open = True
                return None
            
        return None

    def draw(self):
        """Credits ekranını çiz"""
        width, height = self.screen.get_size()
        self._ensure_credits_metrics()

        if self._credits_title_surf is None or self._credits_subtitle_surf is None or self._credits_title_glow_surf is None:
            return
        s = self._credits_sx
        self._load_credits_mascots()

        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        
        # Başlık
        title_rect = self._credits_title_surf.get_rect(center=(width // 2, s(50)))
        # Glow efekti (hafif, cache'li)
        self.screen.blit(self._credits_title_glow_surf, (title_rect.x + s(1), title_rect.y + s(1)))
        self.screen.blit(self._credits_title_surf, title_rect)
        
        # Alt başlık
        self.screen.blit(self._credits_subtitle_surf, self._credits_subtitle_surf.get_rect(center=(width // 2, s(90))))

        # Sağ/Sol büyük maskot panelleri + merkez içerik alanı
        content_top = s(120)
        footer_y = height - s(50)
        content_bottom = max(content_top + s(260), footer_y - s(36))

        # credits_layout.json'dan özel boyutları yükle
        _cl = {}
        try:
            import json as _json
            _cl_path = ROOT_DIR / 'credits_layout.json'
            if _cl_path.exists():
                _cl = _json.loads(_cl_path.read_text(encoding='utf-8'))
        except Exception:
            pass

        side_margin = s(int(_cl.get('side_margin', 24)))
        side_gap = s(int(_cl.get('side_gap', 20)))
        _cl_pw = int(_cl.get('side_panel_w', 0))
        _cl_ph = int(_cl.get('side_panel_h', 0))
        min_center_w = s(560)
        min_side_w = s(120)
        avail_w = width - 2 * side_margin - 2 * side_gap
        if _cl_pw > 0:
            side_panel_w = _cl_pw
        elif avail_w > min_center_w + 2 * min_side_w:
            side_panel_w = min(s(340), (avail_w - min_center_w) // 2)
        else:
            side_panel_w = min_side_w
        side_panel_w = max(min_side_w, side_panel_w)
        if _cl_ph > 0:
            side_panel_h = _cl_ph
        else:
            side_panel_h = max(s(300), content_bottom - content_top)

        left_panel_rect = pygame.Rect(side_margin, content_top, side_panel_w, side_panel_h)
        right_panel_rect = pygame.Rect(width - side_margin - side_panel_w, content_top, side_panel_w, side_panel_h)
        self._draw_mascot_panel(left_panel_rect, self._credits_mascot_left)
        self._draw_mascot_panel(right_panel_rect, self._credits_mascot_right, scale_factor=1.15)

        center_left = left_panel_rect.right + side_gap
        center_right = right_panel_rect.left - side_gap
        if center_right - center_left < s(420):
            center_left = s(20)
            center_right = width - s(20)
        center_w = max(s(320), center_right - center_left)
        
        # Takım Kartları - Geliştiriciler üstte geniş, diğerleri altta yan yana
        self.testers_card_rect = None
        start_y = content_top
        gap_x = s(30)
        gap_y = s(20)
        card_h = s(100)
        card_w = min(s(360), max(s(220), (center_w - gap_x) // 2))
        two_cols = center_w >= s(540)
        
        # Geniş kart genişliği (tam genişlik)
        wide_card_w = min(center_w, card_w * 2 + gap_x)
        cards_bottom = start_y
        
        # Kartları çiz
        small_card_idx = 0  # Küçük kartlar için sayı
        for idx, member in enumerate(self.team_cards):
            is_wide = member.get('wide', False)
            
            if is_wide:
                # Geniş kart - üstte ortalanmış
                card_x = center_left + (center_w - wide_card_w) // 2
                card_y = start_y
                current_card_w = wide_card_w
            else:
                # Küçük kartlar - altta yan yana veya çok dar ekranda alt alta
                if two_cols:
                    col = small_card_idx % 2
                    row = 0
                    small_total_w = card_w * 2 + gap_x
                    row_start_x = center_left + (center_w - small_total_w) // 2
                    card_x = row_start_x + col * (card_w + gap_x)
                    card_y = start_y + card_h + gap_y
                else:
                    col = 0
                    row = small_card_idx
                    card_x = center_left + (center_w - card_w) // 2
                    card_y = start_y + card_h + gap_y + row * (card_h + gap_y)
                current_card_w = card_w
                small_card_idx += 1
            
            card_rect = pygame.Rect(card_x, card_y, current_card_w, card_h)
            cards_bottom = max(cards_bottom, card_rect.bottom)
            
            # Testçiler kartı rect'ini kaydet
            if member.get('clickable'):
                self.testers_card_rect = card_rect
            
            # Hover check
            is_hover = card_rect.collidepoint(self.mouse_pos)
            is_clickable = member.get('clickable', False)
            
            # Glass Panel - tıklanabilir olanlar için özel stil
            if is_clickable and is_hover:
                # Tıklanabilir hover efekti
                retro_style.draw_glass_panel(self.screen, card_rect, alpha=220, border_color=(150, 255, 200))
                pygame.draw.rect(self.screen, (100, 255, 150, 80), card_rect.inflate(s(6), s(6)), max(1, s(3)), border_radius=s(14))
            elif is_hover:
                retro_style.draw_glass_panel(self.screen, card_rect, alpha=200, border_color=member['role_color'])
            else:
                border_color = (80, 150, 120) if is_clickable else (60, 70, 90)
                retro_style.draw_glass_panel(self.screen, card_rect, alpha=140, border_color=border_color)
            
            # İsim (ortalanmış)
            name_color = (150, 255, 200) if (is_clickable and is_hover) else (member['role_color'] if is_hover else WHITE)
            name_text = t(member['title_key']) if member.get('title_key') else member.get('title', '')
            name_surf = self.font_name.render(name_text, True, name_color)
            name_rect = name_surf.get_rect(center=(card_rect.centerx, card_rect.y + s(25)))
            self.screen.blit(name_surf, name_rect)
            
            # Rol (ortalanmış, renkli)
            role_text = t(member['role_key']) if member.get('role_key') else member.get('role', '')
            role_surf = self.font_role.render(role_text, True, member['role_color'])
            role_rect = role_surf.get_rect(center=(card_rect.centerx, card_rect.y + s(50)))
            self.screen.blit(role_surf, role_rect)
            
            # Açıklama (ortalanmış)
            desc_color = (150, 255, 200) if is_clickable else (180, 190, 210)
            desc_text = t(member['desc_key']) if member.get('desc_key') else member.get('desc', '')
            desc_surf = self.font_body.render(desc_text, True, desc_color)
            desc_rect = desc_surf.get_rect(center=(card_rect.centerx, card_rect.y + s(75)))
            self.screen.blit(desc_surf, desc_rect)
        
        # Özel Teşekkürler Bölümü
        thanks_y = cards_bottom + s(30)
        thanks_w = min(s(700), center_w - s(20))
        thanks_h = s(120)
        thanks_rect = pygame.Rect(center_left + (center_w - thanks_w) // 2, thanks_y, thanks_w, thanks_h)

        social_h = s(40)
        social_y = thanks_y + thanks_h + s(20)
        overflow = (social_y + social_h) - content_bottom
        if overflow > 0:
            thanks_rect.y = max(start_y + card_h + s(10), thanks_rect.y - overflow)
            social_y = thanks_rect.bottom + s(20)
        
        retro_style.draw_glass_panel(self.screen, thanks_rect, alpha=100, border_color=(80, 100, 140))
        
        # Özel Teşekkürler Başlığı
        thanks_title = self.font_section.render(t('credits_special_thanks_title'), True, (255, 220, 100))
        self.screen.blit(thanks_title, thanks_title.get_rect(center=(thanks_rect.centerx, thanks_rect.y + s(25))))
        
        # Teşekkür listesi
        for i, key in enumerate(self.special_thanks):
            line_surf = self.font_body.render(t(key), True, (200, 210, 230))
            self.screen.blit(line_surf, line_surf.get_rect(center=(thanks_rect.centerx, thanks_rect.y + s(55) + i * s(22))))
        
        # Sosyal Medya Bilgileri
        social_w = min(s(750), center_w - s(12))
        social_rect = pygame.Rect(center_left + (center_w - social_w) // 2, social_y, social_w, social_h)
        
        retro_style.draw_glass_panel(self.screen, social_rect, alpha=80, border_color=(100, 130, 180))

        social_text = t('credits_social_info').format(email=CONTACT_EMAIL)
        social_surf = self.font_small.render(social_text, True, (180, 200, 240))
        self.screen.blit(social_surf, social_surf.get_rect(center=social_rect.center))
        
        # Copyright ve Footer
        copyright_surf = self.font_footer.render(t('credits_copyright'), True, (140, 150, 170))
        self.screen.blit(copyright_surf, copyright_surf.get_rect(center=(width // 2, footer_y)))

        esc_surf = self.font_footer.render(t('credits_esc_hint'), True, (120, 130, 150))
        self.screen.blit(esc_surf, esc_surf.get_rect(center=(width // 2, footer_y + s(18))))
        
        # === TESTÇILER POPUP ===
        if self.testers_popup_open:
            self._draw_testers_popup()
    
    def _draw_testers_popup(self):
        """Oyun testçileri popup'ını çiz"""
        width, height = self.screen.get_size()
        popup_scale = self._fullscreen_panel_scale()
        
        # Karartma overlay
        dim_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 180))
        self.screen.blit(dim_surf, (0, 0))
        
        # Popup boyutları
        popup_rect = self._get_testers_popup_rect()
        popup_w = popup_rect.width
        popup_h = popup_rect.height
        popup_x = popup_rect.x
        popup_y = popup_rect.y
        
        # Popup arka planı
        retro_style.draw_glass_panel(self.screen, popup_rect, alpha=240, border_color=(100, 200, 255), glow=True)
        
        # Başlık
        title_surf = self.font_section.render(t('credits_testers_title'), True, (100, 200, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(popup_x + popup_w // 2, popup_y + max(22, int(30 * popup_scale)))))
        
        # Alt çizgi
        line_pad = max(26, int(40 * popup_scale))
        line_y = popup_y + max(40, int(55 * popup_scale))
        pygame.draw.line(self.screen, (100, 200, 255), (popup_x + line_pad, line_y), (popup_x + popup_w - line_pad, line_y), 2)
        
        # Testçi listesi (2 sütunlu)
        list_start_y = popup_y + max(55, int(75 * popup_scale))
        col_width = popup_w // 2
        
        for i, name in enumerate(self.testers_list):
            row = i // 2
            col = i % 2
            
            x = popup_x + max(18, int(30 * popup_scale)) + col * col_width
            y = list_start_y + row * max(20, int(28 * popup_scale))
            
            # Bullet point
            bullet_surf = self.font_body.render('•', True, (100, 200, 255))
            self.screen.blit(bullet_surf, (x, y))
            
            # İsim
            name_surf = self.font_body.render(name, True, (220, 230, 250))
            self.screen.blit(name_surf, (x + 18, y))
        
        # Kapatma ipucu
        hint_surf = self.font_small.render(t('credits_testers_close_hint'), True, (150, 160, 180))
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(popup_x + popup_w // 2, popup_y + popup_h - max(16, int(25 * popup_scale)))))

