"""Kılavuz Ekranı - Oyun rehberi ve yardım sistemi"""
import pygame
import math
import os
import sys
from typing import List, Dict, Tuple, Optional, Any
from constants import *
from retro_style import retro_style
from background_effects import get_shared_falling_blocks_layer
from platform_utils import normalize_mouse_pos, is_fullscreen_toggle
from localization import t, get_language
from gamepad_manager import get_gamepad_manager
from ui_scaling import get_projected_effective_scale, scale_px


# ==============================================================================
# UI İkon Dizini
# ==============================================================================
def _get_ui_icon_dir() -> str:
    """PyInstaller uyumlu UI ikon dizini."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'ui'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'ui'))


def _get_maskot_dir() -> str:
    """PyInstaller uyumlu maskot görsel dizini."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'maskot'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'maskot'))


UI_ICON_DIR = _get_ui_icon_dir()
GUIDE_MASKOT_DIR = _get_maskot_dir()

GUIDE_TAB_MASCOT_ICONS = {
    'how_to_play': 'kilavuz_nasiloynanir.png',
    'game_modes': 'kilavuz_oyunmodlari.png',
    'cards': 'kilavuz_kartlar.png',
    'tips_faq': 'kilavuz_ipuclari.png',
}


def _guide_action_label(action: str, keyboard_label: str) -> str:
    try:
        gpm = get_gamepad_manager()
        if getattr(gpm, 'enabled', False) and gpm.is_connected():
            resolved = gpm.get_button_label(action)
            if resolved and resolved != '?':
                return resolved
    except Exception:
        pass
    return keyboard_label


# ==============================================================================
# KART VERİLERİ - İkon ve açıklamalarla
# ==============================================================================
CARD_DATA = [
    # === COMMON / UNCOMMON ===
    {
        'id': 'clear_rows',
        'name_key': 'guide_card_clear_rows_name',
        'desc_key': 'guide_card_clear_rows_desc',
        'icon': 'icon_clean_sweep.png',
        'rarity': 'common',
        'color': (120, 230, 255),
    },
    {
        'id': 'peak_sculpt',
        'name_key': 'guide_card_peak_sculpt_name',
        'desc_key': 'guide_card_peak_sculpt_desc',
        'icon': 'icon_peak_cutter.png',
        'rarity': 'common',
        'color': (140, 255, 210),
    },
    {
        'id': 'row_shuffle',
        'name_key': 'guide_card_row_shuffle_name',
        'desc_key': 'guide_card_row_shuffle_desc',
        'icon': 'icon_row_shuffle.png',
        'rarity': 'common',
        'color': (255, 110, 100),
    },
    {
        'id': 'speed_burst',
        'name_key': 'guide_card_speed_burst_name',
        'desc_key': 'guide_card_speed_burst_desc',
        'icon': 'icon_speed_burst.png',
        'rarity': 'common',
        'color': (255, 180, 50),
    },
    {
        'id': 'mini_bomb',
        'name_key': 'guide_card_mini_bomb_name',
        'desc_key': 'guide_card_mini_bomb_desc',
        'icon': 'icon_mini_bomb.png',
        'rarity': 'uncommon',
        'color': (255, 110, 80),
    },
    # === RARE ===
    {
        'id': 'quantum_tunneling',
        'name_key': 'guide_card_quantum_name',
        'desc_key': 'guide_card_quantum_desc',
        'icon': 'icon_quantum_tunnel.png',
        'rarity': 'rare',
        'color': (180, 200, 255),
    },
    {
        'id': 'hammer',
        'name_key': 'guide_card_hammer_name',
        'desc_key': 'guide_card_hammer_desc',
        'icon': 'icon_hammer.png',
        'rarity': 'rare',
        'color': (230, 210, 140),
    },
    {
        'id': 'laser_drill',
        'name_key': 'guide_card_laser_name',
        'desc_key': 'guide_card_laser_desc',
        'icon': 'icon_laser_drill.png',
        'rarity': 'rare',
        'color': (255, 50, 150),
    },
    {
        'id': 'sniper_shot',
        'name_key': 'guide_card_sniper_name',
        'desc_key': 'guide_card_sniper_desc',
        'icon': 'icon_sniper_shot.png',
        'rarity': 'rare',
        'color': (255, 80, 80),
    },
    {
        'id': 'future_changer',
        'name_key': 'guide_card_future_name',
        'desc_key': 'guide_card_future_desc',
        'icon': 'icon_future_changer.png',
        'rarity': 'rare',
        'color': (150, 255, 200),
    },
    {
        'id': 'freeze_drop',
        'name_key': 'guide_card_freeze_drop_name',
        'desc_key': 'guide_card_freeze_drop_desc',
        'name_fallback': 'Son Düşüş',
        'desc_fallback': '3 hak: F ile bloğu dondur! Sadece sağ-sol ve sert düşüş çalışır.',
        'icon': 'icon_freeze_drop.png',
        'rarity': 'rare',
        'color': (130, 220, 255),
    },
    {
        'id': 'bomb_master',
        'name_key': 'card_bomb_master_title',
        'desc_key': 'card_bomb_master_desc',
        'icon': 'icon_perk_explosive.png',
        'rarity': 'rare',
        'color': (255, 90, 60),
    },
    {
        'id': 'rewind_power',
        'name_key': 'card_rewind_power_title',
        'desc_key': 'card_rewind_power_desc',
        'icon': 'icon_perk_rewind.png',
        'rarity': 'rare',
        'color': (255, 200, 255),
    },
    {
        'id': 'perk_synergy',
        'name_key': 'guide_perk_synergy_name',
        'desc_key': 'guide_perk_synergy_desc',
        'icon': 'icon_perk_synergy.png',
        'rarity': 'rare',
        'color': (255, 220, 140),
    },
    # === EPIC ===
    {
        'id': 'nova_burst',
        'name_key': 'guide_card_nova_name',
        'desc_key': 'guide_card_nova_desc',
        'icon': 'icon_nova_burst.png',
        'rarity': 'epic',
        'color': (255, 120, 196),
    },
    {
        'id': 'gravity_well',
        'name_key': 'guide_card_gravity_name',
        'desc_key': 'guide_card_gravity_desc',
        'icon': 'icon_gravity_well.png',
        'rarity': 'epic',
        'color': (120, 160, 255),
    },
    {
        'id': 'perk_phase',
        'name_key': 'guide_card_phase_name',
        'desc_key': 'guide_card_phase_desc',
        'icon': 'icon_perk_phase.png',
        'rarity': 'epic',
        'color': (255, 200, 255),
    },
    {
        'id': 'perk_second_pocket',
        'name_key': 'guide_card_pocket_name',
        'desc_key': 'guide_card_pocket_desc',
        'icon': 'icon_perk_second_pocket.png',
        'rarity': 'epic',
        'color': (200, 200, 255),
    },
    {
        'id': 'color_cleanse',
        'name_key': 'card_color_cleanse_title',
        'desc_key': 'card_color_cleanse_desc',
        'name_fallback': 'Renk Temizleme',
        'desc_fallback': 'Rastgele bir renkteki tüm blokları temizler.',
        'icon': 'icon_color_fix.png',
        'rarity': 'epic',
        'color': (100, 255, 200),
    },
    # === LEGENDARY ===
    {
        'id': 'perk_flexible_border',
        'name_key': 'guide_card_flexible_border_name',
        'desc_key': 'guide_card_flexible_border_desc',
        'icon': 'icon_perk_flexible_border.png',
        'rarity': 'legendary',
        'color': (255, 200, 100),
    },
    {
        'id': 'block_magnet',
        'name_key': 'guide_card_magnet_name',
        'desc_key': 'guide_card_magnet_desc',
        'icon': 'icon_block_magnet.png',
        'rarity': 'legendary',
        'color': (255, 140, 100),
    },
    {
        'id': 'ghost_echo',
        'name_key': 'guide_card_ghost_name',
        'desc_key': 'guide_card_ghost_desc',
        'icon': 'icon_ghost_echo.png',
        'rarity': 'legendary',
        'color': (200, 200, 255),
    },
    {
        'id': 'time_capsule',
        'name_key': 'guide_card_time_capsule_name',
        'desc_key': 'guide_card_time_capsule_desc',
        'icon': 'icon_time_capsule.png',
        'rarity': 'legendary',
        'color': (120, 255, 200),
    },
    {
        'id': 'block_workshop_card',
        'name_key': 'card_block_workshop_card_title',
        'desc_key': 'card_block_workshop_card_desc',
        'name_fallback': 'Blok Atölyesi',
        'desc_fallback': 'Tek seferlik özel parça oluşturma atölyesini açar.',
        'icon': 'icon_block_workshop.png',
        'rarity': 'legendary',
        'color': (255, 200, 100),
    },
    {
        'id': 'gambler_dice',
        'name_key': 'card_gambler_dice_title',
        'desc_key': 'card_gambler_dice_desc',
        'name_fallback': 'Kumarbazın Zarı',
        'desc_fallback': 'Yüksek riskli zar etkisi: ya büyük kazanç ya büyük ceza.',
        'icon': 'icon_gambler_dice.png',
        'rarity': 'legendary',
        'color': (255, 80, 80),
    },
    {
        'id': 'hold_destroyer',
        'name_key': 'card_hold_destroyer_title',
        'desc_key': 'card_hold_destroyer_desc',
        'name_fallback': 'Tuttuğunu Koparan',
        'desc_fallback': 'B tuşu ile hold parçasını silme hakkı verir (kart seviyesine göre 1-5 hak).',
        'icon': 'icon_hold_destroyer.png',
        'rarity': 'legendary',
        'color': (210, 210, 220),
    },
]

# Rarity renkleri
RARITY_COLORS = {
    'common': (180, 180, 180),
    'uncommon': (80, 200, 80),
    'rare': (80, 140, 255),
    'epic': (180, 80, 255),
    'legendary': (255, 180, 50),
    'perk': (255, 120, 200),
}

RARITY_NAME_KEYS = {
    'common': 'guide_rarity_common',
    'uncommon': 'guide_rarity_uncommon',
    'rare': 'guide_rarity_rare',
    'epic': 'guide_rarity_epic',
    'legendary': 'guide_rarity_legendary',
    'perk': 'guide_rarity_perk',
}


# ==============================================================================
# KILAVUZ VERİLERİ - JSON benzeri yapı (localization key'leri kullanır)
# ==============================================================================

GUIDE_SECTIONS = [
    {
        'id': 'how_to_play',
        'title_key': 'guide_how_to_play_title',
        'icon': '>',
        'content_keys': [
            'guide_how_to_play_intro',
            'guide_how_to_play_controls',
            'guide_how_to_play_scoring',
            'guide_how_to_play_levels',
            'guide_how_to_play_tips',
        ]
    },
    {
        'id': 'game_modes',
        'title_key': 'guide_game_modes_title',
        'icon': '>',
        'content_keys': [
            'guide_mode_campaign',
            'guide_mode_classic',
            'guide_mode_sprint',
            'guide_mode_ultra',
            'guide_mode_zen',
            'guide_mode_survival',
            'guide_mode_cascade',
            'guide_mode_tetris2',
            'guide_mode_wide',
            'guide_mode_mystery',
            'guide_mode_pvp',
            'guide_mode_online_pvp',
            'guide_mode_daily',
            'guide_mode_hardcore',
        ]
    },
    {
        'id': 'cards',
        'title_key': 'guide_cards_title',
        'icon': '>',
        'is_card_gallery': True,  # Özel kart galerisi modu
    },
    {
        'id': 'tips_faq',
        'title_key': 'guide_tips_title',
        'icon': '>',
        'content_keys': [
            'guide_tips_intro',
            'guide_tip_1',
            'guide_tip_2',
            'guide_tip_3',
            'guide_tip_4',
            'guide_tip_5',
            'guide_faq_intro',
            'guide_faq_1',
            'guide_faq_2',
            'guide_faq_3',
        ]
    },
]


class GuideScreen:
    """Kılavuz ekranı - Tab tabanlı rehber sistemi"""
    
    def __init__(self, screen, settings_manager=None):
        """Kılavuz ekranını başlat"""
        self.screen = screen
        self.settings_manager = settings_manager
        
        # Tab ve scroll durumu
        self.selected_tab = 0
        self.scroll_y = 0
        self.max_scroll = 0
        self.scroll_speed = 40
        self._base_scroll_speed = 40
        
        # Kart galerisi için index
        self.card_index = 0
        self.max_cards = len(CARD_DATA)
        
        # Animasyon
        self.tab_hover = -1
        self.back_hover = False
        self.tutorial_hover = False
        self.anim_time = 0
        
        # Cache
        self._content_cache: Dict = {}
        self._last_content_signature: Optional[Tuple[int, int, str]] = None
        self._icon_cache: Dict[str, pygame.Surface] = {}
        
        # Tab rect'leri (mouse için)
        self._tab_rects: List[pygame.Rect] = []

        # Scrollbar drag state
        self._sb_thumb_rect: Optional[pygame.Rect] = None
        self._sb_container_rect: Optional[pygame.Rect] = None
        self._sb_last_panel_rect: Optional[pygame.Rect] = None
        self._sb_drag_active: bool = False
        self._sb_drag_offset_y: int = 0

        # Falling blocks arka plan
        self.falling_blocks = get_shared_falling_blocks_layer()

    def _set_selected_tab(self, tab_index: int) -> None:
        """Seçili sekmeyi güvenli biçimde güncelle ve içerik durumunu sıfırla."""
        if not GUIDE_SECTIONS:
            self.selected_tab = 0
            self.scroll_y = 0
            self.card_index = 0
            return

        self.selected_tab = max(0, min(len(GUIDE_SECTIONS) - 1, int(tab_index)))
        self.scroll_y = 0
        self.card_index = 0

    def _switch_tab(self, delta: int) -> None:
        """Seçili sekmeyi göreli olarak değiştir."""
        if not GUIDE_SECTIONS:
            return
        self._set_selected_tab(self.selected_tab + int(delta))

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.24) -> float:
        return get_projected_effective_scale(
            self.screen,
            min_scale=min_scale,
            max_scale=max_scale,
            reference_size=(1366.0, 768.0),
        )

    def _s(self, value: int | float, minimum: int = 1, *, scale: float | None = None) -> int:
        active_scale = self._ui_scale() if scale is None else float(scale)
        return scale_px(value, active_scale, minimum=minimum)

    def _font(
        self,
        size: int | float,
        *,
        bold: bool = False,
        minimum: int = 9,
        scale: float | None = None,
    ):
        return retro_style.get_font(self._s(size, minimum=minimum, scale=scale), bold=bold)

    def _scroll_step(self) -> int:
        return self._s(self._base_scroll_speed, minimum=24)

    def _scrollbar_track_metrics(self) -> tuple[int, int, int, int]:
        scale = self._ui_scale()
        bar_width = self._s(10, minimum=8, scale=scale)
        padding = self._s(2, minimum=2, scale=scale)
        arrow_zone = max(bar_width, bar_width + padding)
        track_min = self._s(4, minimum=4, scale=scale)
        thumb_fallback = self._s(20, minimum=16, scale=scale)
        return arrow_zone, padding, track_min, thumb_fallback

    def _content_cache_signature(self, width: int) -> Tuple[int, int, str]:
        scale_key = int(round(self._ui_scale() * 1000))
        return int(width), scale_key, str(get_language())
    
    def _load_card_icon(self, icon_name: str, size: int = 80) -> Optional[pygame.Surface]:
        """Kart ikonunu yükle ve cache'le"""
        if not icon_name:  # None veya boş string kontrolü
            return None
            
        cache_key = f"{icon_name}_{size}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        icon_path = os.path.join(UI_ICON_DIR, icon_name)
        if os.path.exists(icon_path):
            try:
                icon = pygame.image.load(icon_path).convert_alpha()
                # Boyutlandır
                icon = pygame.transform.smoothscale(icon, (size, size))
                self._icon_cache[cache_key] = icon
                return icon
            except Exception as e:
                print(f"⚠️ Kart ikonu yüklenemedi: {icon_name} - {e}")
        return None

    def _load_guide_emoji_icon(self, icon_name: str) -> Optional[pygame.Surface]:
        """Kılavuz maskot görselini orijinal boyutta yükle ve cache'le"""
        if not icon_name:
            return None

        cache_key = f"guide_emoji_raw_{icon_name}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        icon_path = os.path.join(GUIDE_MASKOT_DIR, icon_name)
        if not os.path.exists(icon_path):
            return None

        try:
            icon = pygame.image.load(icon_path).convert_alpha()
            self._icon_cache[cache_key] = icon
            return icon
        except Exception as e:
            print(f"⚠️ Kılavuz maskotu yüklenemedi: {icon_name} - {e}")
            return None

    def _get_selected_tab_mascot(self, max_width: int, max_height: int) -> Optional[pygame.Surface]:
        """Seçili sekmeye göre maskotu, verilen alana sığacak tam boyutta döndür"""
        if not GUIDE_SECTIONS or self.selected_tab < 0 or self.selected_tab >= len(GUIDE_SECTIONS):
            return None

        section_id = GUIDE_SECTIONS[self.selected_tab].get('id')
        icon_name = GUIDE_TAB_MASCOT_ICONS.get(section_id)
        resolved_icon_name = icon_name
        mascot = self._load_guide_emoji_icon(icon_name) if icon_name else None
        if mascot is None:
            resolved_icon_name = 'kilavuz_nasiloynanir.png'
            mascot = self._load_guide_emoji_icon(resolved_icon_name)
        if mascot is None:
            return None

        src_w, src_h = mascot.get_size()
        if src_w <= 0 or src_h <= 0 or max_width <= 0 or max_height <= 0:
            return None

        scale = min(max_width / src_w, max_height / src_h)
        draw_w = max(1, int(src_w * scale))
        draw_h = max(1, int(src_h * scale))
        scaled_key = f"guide_emoji_scaled_{resolved_icon_name}_{draw_w}_{draw_h}"
        if scaled_key in self._icon_cache:
            return self._icon_cache[scaled_key]

        scaled = pygame.transform.smoothscale(mascot, (draw_w, draw_h))
        self._icon_cache[scaled_key] = scaled
        return scaled
    
    def _get_tabs(self) -> List[Dict]:
        """Yerelleştirilmiş tab listesi"""
        tabs = []
        for section in GUIDE_SECTIONS:
            tabs.append({
                'id': section['id'],
                'title': t(section['title_key']),
                'icon': section.get('icon', '>'),
            })
        return tabs
    
    def _build_content_surface(self, section_index: int, width: int) -> pygame.Surface:
        """Bölüm içeriğini surface olarak oluştur - Modern görsel tasarım"""
        section = GUIDE_SECTIONS[section_index]
        
        # Kart galerisi için özel işlem
        if section.get('is_card_gallery'):
            return self._build_card_gallery_surface(width)
        
        # Oyun modları için özel görsel layout
        if section['id'] == 'game_modes':
            return self._build_game_modes_surface(width)
        
        # Nasıl oynanır için özel layout
        if section['id'] == 'how_to_play':
            return self._build_how_to_play_surface(width)
        
        # Diğer bölümler için varsayılan
        return self._build_default_content_surface(section, width)
    
    def _build_default_content_surface(self, section: Dict, width: int) -> pygame.Surface:
        scale = self._ui_scale()
        
        # Font hazırla - Okunabilirlik için büyütüldü
        body_font = self._font(20, bold=False, minimum=13, scale=scale)
        header_font = self._font(22, bold=True, minimum=14, scale=scale)
        
        padding = self._s(30, minimum=20, scale=scale)
        content_width = width - padding * 2
        line_height = self._s(36, minimum=24, scale=scale)
        
        # Önce yüksekliği hesapla
        total_height = padding
        
        # Normal içerik hesaplama
        for key in section.get('content_keys', []):
            text = t(key)
            lines = self._wrap_text(text, body_font, content_width)
            total_height += len(lines) * line_height + self._s(24, minimum=16, scale=scale)
        
        total_height += padding + self._s(60, minimum=40, scale=scale)
        
        # Surface oluştur
        surface = pygame.Surface((width, max(total_height, self._s(400, minimum=320, scale=scale))), pygame.SRCALPHA)
        
        # İçeriği çiz
        y = padding
        
        for key in section.get('content_keys', []):
            text = t(key)
            lines = self._wrap_text(text, body_font, content_width)
            
            for line in lines:
                line = line.strip()
                
                # Başlık satırları için ( [BAŞLIK] )
                if line.startswith('[') and line.endswith(']'):
                    current_font = header_font
                    color = retro_style.accent
                    # Köşeli parantezleri kaldır ve ortala
                    render_text = line.strip('[]')
                    y += self._s(10, minimum=6, scale=scale)
                
                # Soru satırları (Q:)
                elif line.startswith('Q:'):
                    current_font = body_font # Font aynı kalsın ama renk değişsin
                    color = (255, 200, 100) # Turuncu
                    render_text = line
                    y += self._s(5, minimum=3, scale=scale)
                    
                # Madde işaretleri
                elif line.startswith('•') or line.startswith('-'):
                    current_font = body_font
                    color = retro_style.success # Yeşilimsi
                    render_text = line
                    
                # Cevap satırları (A:) veya normal metin
                else:
                    current_font = body_font
                    if line.startswith('A:'):
                         color = (200, 200, 255) # Açık mavi
                    else:
                         color = retro_style.text_primary
                    render_text = line
                
                line_surf = current_font.render(render_text, True, color)
                surface.blit(line_surf, (padding, y))
                y += line_height
            
            y += self._s(24, minimum=16, scale=scale)
        
        return surface
    
    def _get_key_display_name(self, key_val: Any) -> str:
        """Tuş değerini (str) kullanıcı dostu isme çevir"""
        if not key_val:
            return ""
        
        s = str(key_val).lower().strip()
        
        # Özel tuşlar için çeviri
        translations = {
            'left': t('key_left_arrow'),
            'right': t('key_right_arrow'),
            'up': t('key_up_arrow'),
            'down': t('key_down_arrow'),
            'space': t('key_space'),
            'return': t('key_enter'),
            'escape': t('key_escape'),
            'left shift': t('key_left_shift'),
            'right shift': t('key_right_shift'),
            'lshift': t('key_left_shift'),
            'rshift': t('key_right_shift'),
            'caps lock': t('key_caps_lock'),
            'tab': t('key_tab'),
            'left ctrl': t('key_left_ctrl'),
            'right ctrl': t('key_right_ctrl'),
            'left alt': t('key_left_alt'),
            'right alt': t('key_right_alt'),
        }
        
        if s in translations:
            return translations[s]
            
        return s.upper()

    def _get_dynamic_controls_text(self) -> str:
        """Ayarlardan güncel kontrolleri oku ve metin oluştur"""
        header = t('guide_controls_header')
        line_fmt = t('guide_controls_line')
        txt = f"{header}\n\n"
        
        # Varsayılanlar (SettingsManager yoksa)
        defaults = {
            'move_left': {'primary': 'left', 'secondary': 'a'},
            'move_right': {'primary': 'right', 'secondary': 'd'},
            'rotate': {'primary': 'up', 'secondary': 'w'},
            'soft_drop': {'primary': 'down', 'secondary': 's'},
            'hard_drop': {'primary': 'space', 'secondary': ''},
            'hold': {'primary': 'c', 'secondary': ''},
            'pause': {'primary': 'p', 'secondary': ''},
        }
        
        controls = defaults
        if self.settings_manager:
            try:
                found = self.settings_manager.get('controls', {}).get('single_player', {})
                if found:
                    controls = found
            except:
                pass

        def fmt_keys(action):
            binds = controls.get(action, {})
            if isinstance(binds, str): # Legacy support
                return self._get_key_display_name(binds)
                
            p = self._get_key_display_name(binds.get('primary', ''))
            s = self._get_key_display_name(binds.get('secondary', ''))
            
            if p and s:
                return f"{p} / {s}"
            if p:
                return p
            if s:
                return s
            return t('none')

        # Satırları oluştur
        # Sol/Sağ
        k_left = fmt_keys('move_left')
        k_right = fmt_keys('move_right')
        # Eğer ok tuşları ise birleştir
        if k_left == t('key_left_arrow') and k_right == t('key_right_arrow'):
            keys_label = t('guide_controls_left_right_arrows')
        else:
            keys_label = f"{k_left} / {k_right}"
        txt += line_fmt.format(keys=keys_label, action=t('guide_action_move')) + "\n\n"

        # Döndürme
        k_rot = fmt_keys('rotate')
        txt += line_fmt.format(keys=k_rot, action=t('guide_action_rotate')) + "\n\n"
        
        # Diğerleri
        txt += line_fmt.format(keys=fmt_keys('soft_drop'), action=t('guide_action_soft_drop')) + "\n\n"
        txt += line_fmt.format(keys=fmt_keys('hard_drop'), action=t('guide_action_hard_drop')) + "\n\n"
        txt += line_fmt.format(keys=fmt_keys('hold'), action=t('guide_action_hold')) + "\n\n"
        pause_keys = f"{fmt_keys('pause')} / {t('key_escape')}"
        txt += line_fmt.format(keys=pause_keys, action=t('guide_action_pause')) + "\n\n"
        txt += line_fmt.format(keys='R', action=t('guide_action_restart'))
        
        return txt

    def _build_how_to_play_surface(self, width: int) -> pygame.Surface:
        """Nasıl Oynanır bölümü - Grid layout kartlar"""
        scale = self._ui_scale()
        padding = self._s(15, minimum=10, scale=scale)
        card_spacing = self._s(15, minimum=10, scale=scale)
        cols = 3
        card_width = (width - padding * 2 - card_spacing * (cols - 1)) // cols
        card_height = self._s(320, minimum=250, scale=scale)
        
        # Dinamik kontroller
        controls_text = self._get_dynamic_controls_text()
        
        # Kart verileri
        cards = [
            {
                'title_key': 'guide_main_objective_title', # ANA AMAÇ
                'content_key': 'guide_how_to_play_intro',
                'color': (100, 255, 218), # Cyan/Turquoise
                'icon': None
            },
            {
                'title': 'CONTROLS',
                'title_key': 'guide_card_controls_title',
                'manual_content': controls_text, # Dinamik içerik
                'content_key': '', # Ignored if manual_content exists
                'color': (100, 200, 255), # Blue
                'icon': None
            },
            {
                'title': 'SCORING',
                'title_key': 'guide_card_scoring_title',
                'content_key': 'guide_how_to_play_scoring',
                'color': (255, 200, 100), # Orange
                'icon': None
            },
            {
                'title': 'LEVELS',
                'title_key': 'guide_card_levels_title',
                'content_key': 'guide_how_to_play_levels',
                'color': (150, 255, 150), # Green
                'icon': None
            },
            {
                'title': 'TIPS',
                'title_key': 'guide_card_tips_title',
                'content_key': 'guide_how_to_play_tips',
                'color': (255, 150, 255), # Purple
                'icon': None
            },
        ]
        
        # Yükseklik hesapla
        rows = (len(cards) + cols - 1) // cols
        total_height = padding + rows * (card_height + card_spacing) + padding
        
        surface = pygame.Surface((width, total_height), pygame.SRCALPHA)
        
        for i, card in enumerate(cards):
            col = i % cols
            row = i // cols
            x = padding + col * (card_width + card_spacing)
            y = padding + row * (card_height + card_spacing)
            
            card_rect = pygame.Rect(x, y, card_width, card_height)
            
            # Kart arka planı
            pygame.draw.rect(surface, (20, 30, 50, 200), card_rect, border_radius=16)
            pygame.draw.rect(surface, card['color'], card_rect, 2, border_radius=16)
            
            # Başlık
            title_text = t(card.get('title_key', ''))
            if title_text.startswith('guide_') or not title_text:
                title_text = card.get('manual_title', card.get('title', ''))
            
            
            
            title_font = self._font(22, bold=True, minimum=14, scale=scale)
            title_surf = title_font.render(title_text, True, card['color'])
            surface.blit(title_surf, (card_rect.x + self._s(20, minimum=14, scale=scale), card_rect.y + self._s(20, minimum=14, scale=scale)))
            
            # Ayırıcı çizgi
            pygame.draw.line(surface, (*card['color'], 100), 
                           (card_rect.x + self._s(20, minimum=14, scale=scale), card_rect.y + self._s(55, minimum=38, scale=scale)),
                           (card_rect.right - self._s(20, minimum=14, scale=scale), card_rect.y + self._s(55, minimum=38, scale=scale)), 1)
            
            # İçerik
            content_font = self._font(16, bold=False, minimum=11, scale=scale)
            
            # Manuel içerik veya localization anahtarı
            if card.get('manual_content'):
                content_text = card['manual_content']
            else:
                content_text = t(card['content_key'])
                
            content_lines = self._wrap_text(content_text, content_font, card_width - self._s(40, minimum=28, scale=scale))
            
            content_y = card_rect.y + self._s(70, minimum=50, scale=scale)
            max_lines = 11 # Karta sığacak satır sayısı
            
            for line in content_lines[:max_lines]:
                if line.strip().startswith('━'): # Eski başlık süslerini atla
                    continue
                    
                line_color = retro_style.text_secondary
                if line.strip().startswith('•') or line.strip().startswith('-'):
                    line_color = retro_style.success
                elif line.strip().endswith(':'):
                    line_color = retro_style.accent
                    
                line_surf = content_font.render(line, True, line_color)
                surface.blit(line_surf, (card_rect.x + self._s(20, minimum=14, scale=scale), content_y))
                content_y += self._s(22, minimum=16, scale=scale)
                
        return surface
    
    def _build_game_modes_surface(self, width: int) -> pygame.Surface:
        """Oyun Modları bölümü - 3 sütunlu grid, gerçek mod ikonları ile"""
        scale = self._ui_scale()
        padding = self._s(20, minimum=12, scale=scale)
        card_spacing = self._s(15, minimum=10, scale=scale)
        cols = 3  # 3 sütunlu grid
        card_width = (width - padding * 2 - card_spacing * (cols - 1)) // cols
        card_height = self._s(280, minimum=220, scale=scale)
        
        # Mod verileri - gerçek ikon dosyaları
        modes = [
            {'name_key': 'guide_mode_name_campaign', 'icon': 'campaign_mode_icon.png', 'color': (187, 255, 0), 'key': 'guide_mode_campaign'},
            {'name_key': 'guide_mode_name_classic', 'icon': 'classic_mode_icon.png', 'color': (100, 200, 255), 'key': 'guide_mode_classic'},
            {'name_key': 'guide_mode_name_sprint', 'icon': 'sprint_mode_icon.png', 'color': (255, 215, 0), 'key': 'guide_mode_sprint'},
            {'name_key': 'guide_mode_name_ultra', 'icon': 'ultra_mode_icon.png', 'color': (255, 50, 50), 'key': 'guide_mode_ultra'},
            {'name_key': 'guide_mode_name_zen', 'icon': 'zen_mode_icon.png', 'color': (100, 255, 200), 'key': 'guide_mode_zen'},
            {'name_key': 'guide_mode_name_survival', 'icon': 'survival_mode_icon.png', 'color': (255, 100, 150), 'key': 'guide_mode_survival'},
            {'name_key': 'guide_mode_name_cascade', 'icon': 'cascade_mode_icon.png', 'color': (80, 150, 255), 'key': 'guide_mode_cascade'},
            {'name_key': 'guide_mode_name_tetris2', 'icon': 'tetris2_mode_icon.png', 'color': (255, 100, 255), 'key': 'guide_mode_tetris2'},
            {'name_key': 'guide_mode_name_wide', 'icon': 'wide_mode_icon.png', 'color': (100, 255, 255), 'key': 'guide_mode_wide'},
            {'name_key': 'guide_mode_name_mystery', 'icon': 'mystery_mode_icon.png', 'color': (255, 150, 255), 'key': 'guide_mode_mystery'},
            {'name_key': 'guide_mode_name_pvp', 'icon': 'pvp_mode_icon.png', 'color': (255, 100, 100), 'key': 'guide_mode_pvp'},
            {'name_key': 'guide_mode_name_online_pvp', 'icon': 'online_pvp_mode_icon.png', 'color': (0, 210, 255), 'key': 'guide_mode_online_pvp'},
            {'name_key': 'guide_mode_name_daily', 'icon': 'daily_mode_icon.png', 'color': (255, 180, 100), 'key': 'guide_mode_daily'},
            {'name_key': 'guide_mode_name_hardcore', 'icon': 'hardcore_mode_icon.png', 'color': (255, 0, 0), 'key': 'guide_mode_hardcore'},
        ]
        
        # Yükseklik hesapla - 3 sütunlu grid
        rows = (len(modes) + cols - 1) // cols
        total_height = padding + rows * (card_height + card_spacing) + 50
        
        surface = pygame.Surface((width, total_height), pygame.SRCALPHA)
        
        # Grid layout
        for i, mode in enumerate(modes):
            col = i % cols
            row = i // cols
            x = padding + col * (card_width + card_spacing)
            y = padding + row * (card_height + card_spacing)
            
            card_rect = pygame.Rect(x, y, card_width, card_height)
            
            # Kart arka planı
            card_surf = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
            pygame.draw.rect(card_surf, (15, 20, 35, 220), card_surf.get_rect(), border_radius=12)
            surface.blit(card_surf, (x, y))
            pygame.draw.rect(surface, mode['color'], card_rect, 2, border_radius=12)
            
            # İkon yükle (icon_cache kullan — disk I/O engellemez)
            icon_size = self._s(100, minimum=72, scale=scale)
            if mode['icon']:
                icon_key = os.path.join('mode_icons', mode['icon'])
                icon = self._load_card_icon(icon_key, icon_size)
                if icon:
                    icon_x = card_rect.centerx - icon_size // 2
                    surface.blit(icon, (icon_x, card_rect.y + self._s(25, minimum=16, scale=scale)))
            
            # Mod ismi
            name_font = self._font(16, bold=True, minimum=11, scale=scale)
            name_text = t(mode.get('name_key', '')) if mode.get('name_key') else mode.get('name', '')
            if not name_text:
                name_text = mode.get('name', '')
            name_surf = name_font.render(name_text, True, mode['color'])
            name_x = card_rect.centerx - name_surf.get_width() // 2
            surface.blit(name_surf, (name_x, card_rect.y + self._s(135, minimum=100, scale=scale)))
            
            # Açıklama - daha kısa, 3 sütuna sığacak şekilde
            desc_font = self._font(14, bold=False, minimum=10, scale=scale)
            desc_text = t(mode['key'])
            # Metni kısalt
            desc_lines = self._wrap_text(desc_text, desc_font, card_width - self._s(16, minimum=12, scale=scale))
            
            desc_y = card_rect.y + self._s(165, minimum=122, scale=scale)
            for line in desc_lines[:5]:  # Max 5 satır
                line_surf = desc_font.render(line, True, retro_style.text_secondary)
                line_x = card_rect.centerx - line_surf.get_width() // 2
                surface.blit(line_surf, (line_x, desc_y))
                desc_y += self._s(18, minimum=13, scale=scale)
        
        return surface
    
    def _build_card_gallery_surface(self, width: int) -> pygame.Surface:
        """Kart galerisi - Tek liste aşağı aksın (Oyun Modları ile aynı stil)"""
        scale = self._ui_scale()
        padding = self._s(20, minimum=12, scale=scale)
        card_spacing = self._s(15, minimum=10, scale=scale)
        cols = 3
        card_width = (width - padding * 2 - card_spacing * (cols - 1)) // cols
        card_height = self._s(280, minimum=220, scale=scale)
        
        # Tüm kartları göster
        page_cards = CARD_DATA
        
        if not page_cards:
            return pygame.Surface((width, 400), pygame.SRCALPHA)
        
        # Yükseklik hesapla
        rows = (len(page_cards) + cols - 1) // cols
        total_height = padding + rows * (card_height + card_spacing) + 50
        
        surface = pygame.Surface((width, total_height), pygame.SRCALPHA)
        
        for i, card in enumerate(page_cards):
            col = i % cols
            row = i // cols
            
            x = padding + col * (card_width + card_spacing)
            y = padding + row * (card_height + card_spacing)
            
            card_rect = pygame.Rect(x, y, card_width, card_height)
            
            # Kart arka planı
            pygame.draw.rect(surface, (20, 30, 50, 220), card_rect, border_radius=12)
            pygame.draw.rect(surface, card['color'], card_rect, 2, border_radius=12)
            
            # İkon - BÜYÜK (Oyun Modları gibi)
            icon_size = self._s(100, minimum=72, scale=scale)
            icon = self._load_card_icon(card.get('icon') or '', icon_size)
            
            if icon:
                icon_x = card_rect.centerx - icon_size // 2
                icon_y = card_rect.y + self._s(25, minimum=16, scale=scale)
                
                # İkon çerçevesi
                border_rect = pygame.Rect(icon_x - 2, icon_y - 2, icon_size + 4, icon_size + 4)
                pygame.draw.rect(surface, card['color'], border_rect, 2, border_radius=5)
                
                # İkon varsa çiz
                surface.blit(icon, (icon_x, icon_y))
            else:
                # İkon yoksa placeholder çizim (Oyun modlarındaki gibi boş kalmasın diye)
                # Buraya basit bir kutu çizilebilir veya boş bırakılabilir
                pass
            
            # Kart İsmi - BÜYÜK (Oyun Modları gibi)
            title_font = self._font(22, bold=True, minimum=14, scale=scale)
            name_key = card.get('name_key', '')
            card_name = t(name_key) if name_key else ''
            if not card_name or card_name == name_key:
                card_name = card.get('name_fallback') or card['id'].replace('_', ' ').title()
            
            # Sığdırma kontrolü (çok uzun isimler için font küçült)
            if len(card_name) > 16:
                 title_font = self._font(18, bold=True, minimum=12, scale=scale)
            
            title_surf = title_font.render(card_name, True, card['color'])
            title_rect = title_surf.get_rect(center=(card_rect.centerx, card_rect.y + self._s(145, minimum=108, scale=scale)))
            surface.blit(title_surf, title_rect)
            
            # Açıklama - BÜYÜK (Oyun Modları gibi)
            desc_font = self._font(16, bold=False, minimum=11, scale=scale)
            desc_key = card.get('desc_key', '')
            desc_text = t(desc_key, button=_guide_action_label('hold2', 'V')) if desc_key else ''
            if not desc_text or desc_text == desc_key:
                desc_text = card.get('desc_fallback') or f"{card['id']} kartı."
            if card.get('id') == 'perk_second_pocket' and '{button}' not in desc_text:
                desc_text = desc_text.replace('V', _guide_action_label('hold2', 'V'), 1)
            
            desc_y = card_rect.y + self._s(175, minimum=130, scale=scale)
            desc_width = card_width - self._s(16, minimum=12, scale=scale)
            
            # Metni sığdır
            lines = self._wrap_text(desc_text, desc_font, desc_width)
            
            line_height = self._s(20, minimum=14, scale=scale)
            max_lines = 5
            
            for line_idx, line in enumerate(lines[:max_lines]):
                line_surf = desc_font.render(line, True, retro_style.text_secondary)
                line_x = card_rect.centerx - line_surf.get_width() // 2
                surface.blit(line_surf, (line_x, desc_y))
                desc_y += line_height
        
        return surface
    
    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Metni satırlara böl"""
        if not text:
            return []
        
        lines = []
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                lines.append('')
                continue
            
            words = paragraph.split(' ')
            current_line = ''
            
            for word in words:
                test_line = current_line + (' ' if current_line else '') + word
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
        
        return lines
    
    def handle_input(self, event) -> Optional[str]:
        """Girdi işle"""
        if event.type == pygame.KEYDOWN:
            scroll_step = self._scroll_step()
            # ESC - Geri
            if event.key == pygame.K_ESCAPE:
                return 'back'

            if event.key == pygame.K_t:
                return self._get_tutorial_action()
            
            # Yukarı/Aşağı - scroll
            if event.key == pygame.K_UP:
                if self.scroll_y > 0:
                    self.scroll_y = max(0, self.scroll_y - scroll_step)
            
            elif event.key == pygame.K_DOWN:
                if self.scroll_y < self.max_scroll:
                    self.scroll_y = min(self.max_scroll, self.scroll_y + scroll_step)

            # LB/RB (gamepad) -> K_LEFTBRACKET / K_RIGHTBRACKET sentetik tuşları.
            # Bu kısayollar sekmeler arasında gezinmek için klavye akışından ayrı tutulur.
            elif event.key == pygame.K_LEFTBRACKET:
                self._switch_tab(-1)
            elif event.key == pygame.K_RIGHTBRACKET:
                self._switch_tab(1)
            
            # Sol/Sağ - sekme değiştirme
            elif event.key == pygame.K_LEFT:
                self._switch_tab(-1)
            
            elif event.key == pygame.K_RIGHT:
                self._switch_tab(1)
            
            # Page Up/Down - scroll
            elif event.key == pygame.K_PAGEUP:
                self.scroll_y = max(0, self.scroll_y - self._s(200, minimum=140))
            
            elif event.key == pygame.K_PAGEDOWN:
                self.scroll_y = min(self.max_scroll, self.scroll_y + self._s(200, minimum=140))
            
            # Tab numaraları (1-4)
            elif pygame.K_1 <= event.key <= pygame.K_4:
                new_tab = event.key - pygame.K_1
                if new_tab < len(GUIDE_SECTIONS):
                    self._set_selected_tab(new_tab)
            
            # Tam ekran
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = normalize_mouse_pos(event.pos) if hasattr(event, 'pos') else event.pos

            if event.button == 1:
                # Scrollbar thumb drag başlat
                if self._sb_thumb_rect and self._sb_thumb_rect.collidepoint(pos):
                    self._sb_drag_active = True
                    self._sb_drag_offset_y = pos[1] - self._sb_thumb_rect.y
                    return None

                # Scrollbar track alanına tıklama → o pozisyona zıpla
                if self._sb_container_rect and self._sb_container_rect.collidepoint(pos):
                    _az, _pad, _track_min, _thumb_default = self._scrollbar_track_metrics()
                    _ty = self._sb_container_rect.top + _az + _pad
                    _th = max(_track_min, self._sb_container_rect.height - _az * 2 - _track_min)
                    _tmh = self._sb_thumb_rect.height if self._sb_thumb_rect else _thumb_default
                    _rel = pos[1] - _ty - _tmh // 2
                    self.scroll_y = int(max(0.0, min(1.0, _rel / max(1, _th - _tmh))) * self.max_scroll)
                    return None

                # Tab tıklama kontrolü
                tab_clicked = self._check_tab_click(pos)
                if tab_clicked is not None and tab_clicked != self.selected_tab:
                    self._set_selected_tab(tab_clicked)
                    return None

                if self._check_tutorial_button_click(pos):
                    return self._get_tutorial_action()

                # Geri buton kontrolü
                if self._check_back_button_click(pos):
                    return 'back'

            # Mouse wheel scroll (eski button 4/5 protokolü)
            elif event.button == 4:
                self.scroll_y = max(0, self.scroll_y - self._scroll_step())
            elif event.button == 5:
                self.scroll_y = min(self.max_scroll, self.scroll_y + self._scroll_step())

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._sb_drag_active = False
                self._sb_drag_offset_y = 0

        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - event.y * self._scroll_step()))

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(event.pos) if hasattr(event, 'pos') else event.pos
            # Scrollbar drag
            if self._sb_drag_active and self._sb_container_rect:
                sb_c = self._sb_container_rect
                arrow_zone, padding, track_min, thumb_default = self._scrollbar_track_metrics()
                track_y = sb_c.top + arrow_zone + padding
                track_h = max(track_min, sb_c.height - arrow_zone * 2 - track_min)
                thumb_h = self._sb_thumb_rect.height if self._sb_thumb_rect else thumb_default
                new_thumb_top = pos[1] - self._sb_drag_offset_y - track_y
                new_thumb_top = max(0, min(new_thumb_top, track_h - thumb_h))
                ratio = new_thumb_top / max(1, track_h - thumb_h)
                self.scroll_y = int(ratio * self.max_scroll)
                return None
            self.tab_hover = self._get_tab_at_pos(pos)
            self.tutorial_hover = self._check_tutorial_button_hover(pos)
            self.back_hover = self._check_back_button_hover(pos)
        
        return None

    def _get_selected_section_id(self) -> str:
        return GUIDE_SECTIONS[self.selected_tab]['id']

    def _get_tutorial_action(self) -> str:
        lesson_map = {
            'how_to_play': 'move_intro',
            'game_modes': 'board_gap_fill',
            'cards': 'card_rescue_pick',
        }
        lesson_id = lesson_map.get(self._get_selected_section_id())
        if lesson_id:
            return f'tutorial_lesson:{lesson_id}'
        return 'tutorial_hub'

    def _get_tutorial_button_label(self) -> str:
        if self._get_selected_section_id() == 'tips_faq':
            return t('guide_open_tutorial_hub')
        return t('guide_open_related_tutorial')

    def _get_bottom_button_rects(self) -> Tuple[pygame.Rect, pygame.Rect]:
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        outer_margin = self._s(40, minimum=32, scale=scale)
        tutorial_w = min(self._s(280, minimum=220, scale=scale), max(self._s(220, minimum=180, scale=scale), width - outer_margin))
        back_w = min(self._s(200, minimum=180, scale=scale), max(self._s(180, minimum=150, scale=scale), width - outer_margin))
        btn_h = self._s(50, minimum=38, scale=scale)
        gap = self._s(16, minimum=12, scale=scale)

        if tutorial_w + back_w + gap <= width - outer_margin:
            total_w = tutorial_w + back_w + gap
            start_x = (width - total_w) // 2
            y = height - btn_h - self._s(25, minimum=18, scale=scale)
            tutorial_rect = pygame.Rect(start_x, y, tutorial_w, btn_h)
            back_rect = pygame.Rect(start_x + tutorial_w + gap, y, back_w, btn_h)
            return tutorial_rect, back_rect

        tutorial_rect = pygame.Rect((width - tutorial_w) // 2, height - btn_h - self._s(85, minimum=64, scale=scale), tutorial_w, btn_h)
        back_rect = pygame.Rect((width - back_w) // 2, height - btn_h - self._s(25, minimum=18, scale=scale), back_w, btn_h)
        return tutorial_rect, back_rect

    def _check_tab_click(self, pos: Tuple[int, int]) -> Optional[int]:
        for i, rect in enumerate(self._tab_rects):
            if rect.collidepoint(pos):
                return i
        return None
    
    def _get_tab_at_pos(self, pos: Tuple[int, int]) -> int:
        for i, rect in enumerate(self._tab_rects):
            if rect.collidepoint(pos):
                return i
        return -1

    def _check_tutorial_button_click(self, pos: Tuple[int, int]) -> bool:
        btn_rect = self._get_tutorial_button_rect()
        return btn_rect.collidepoint(pos)

    def _check_tutorial_button_hover(self, pos: Tuple[int, int]) -> bool:
        btn_rect = self._get_tutorial_button_rect()
        return btn_rect.collidepoint(pos)
    
    def _check_back_button_click(self, pos: Tuple[int, int]) -> bool:
        btn_rect = self._get_back_button_rect()
        return btn_rect.collidepoint(pos)
    
    def _check_back_button_hover(self, pos: Tuple[int, int]) -> bool:
        btn_rect = self._get_back_button_rect()
        return btn_rect.collidepoint(pos)

    def _get_tutorial_button_rect(self) -> pygame.Rect:
        tutorial_rect, _ = self._get_bottom_button_rects()
        return tutorial_rect
    
    def _get_back_button_rect(self) -> pygame.Rect:
        _, back_rect = self._get_bottom_button_rects()
        return back_rect
    
    def draw(self):
        """Kılavuz ekranını çiz"""
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        
        self.anim_time += 16
        
        # Arka plan
        retro_style.draw_background(self.screen)
        
        # Falling blocks efekti
        if self.falling_blocks:
            self.falling_blocks.update(self.screen)
            self.falling_blocks.draw(self.screen)
        
        # Layout hesapla
        tab_panel_width = min(self._s(240, minimum=180, scale=scale), int(width * 0.28))
        content_gap = self._s(30, minimum=20, scale=scale)
        content_x = tab_panel_width + content_gap
        content_width = width - content_x - content_gap
        content_height = height - self._s(180, minimum=140, scale=scale)
        
        # Başlık
        retro_style.draw_title(self.screen, t('guide_title'), (width // 2, self._s(50, minimum=40, scale=scale)))
        
        # Sol tab paneli
        self._draw_tab_panel(tab_panel_width, height)
        
        # Sağ içerik paneli
        self._draw_content_panel(content_x, content_width, content_height)
        
        # Kart navigasyonu (sadece Cards sekmesinde)
        if self.selected_tab == 2:
            self._draw_card_navigation(content_x, content_width, height)
        
        # Alt aksiyonlar
        self._draw_tutorial_button()
        self._draw_back_button()
        
        # Hint text
        self._draw_hints(width, height)
    
    def _draw_tab_panel(self, panel_width: int, height: int):
        scale = self._ui_scale()
        tabs = self._get_tabs()
        tab_height = self._s(64, minimum=48, scale=scale)
        tab_start_y = self._s(110, minimum=88, scale=scale)
        gap = self._s(8, minimum=6, scale=scale)
        left_margin = self._s(16, minimum=12, scale=scale)
        
        self._tab_rects = []
        
        for i, tab in enumerate(tabs):
            tab_rect = pygame.Rect(left_margin, tab_start_y + i * (tab_height + gap), panel_width, tab_height)
            self._tab_rects.append(tab_rect)
            
            is_selected = (i == self.selected_tab)
            is_hovered = (i == self.tab_hover)
            
            if is_selected:
                glow_rect = tab_rect.inflate(self._s(8, minimum=6, scale=scale), self._s(8, minimum=6, scale=scale))
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*retro_style.primary[:3], 40), glow_surf.get_rect(), border_radius=12)
                self.screen.blit(glow_surf, glow_rect.topleft)
                
                bg_color = (30, 40, 65, 220)
                border_color = retro_style.primary
            elif is_hovered:
                bg_color = (25, 35, 55, 200)
                border_color = retro_style.secondary
            else:
                bg_color = (18, 25, 42, 180)
                border_color = (60, 75, 100)
            
            tab_surf = pygame.Surface(tab_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(tab_surf, bg_color, tab_surf.get_rect(), border_radius=12)
            
            highlight_depth = min(self._s(15, minimum=10, scale=scale), tab_rect.height // 4)
            if is_selected or is_hovered:
                for y in range(highlight_depth):
                    h_alpha = int(25 * (1 - y / max(1, highlight_depth)))
                    pygame.draw.line(tab_surf, (255, 255, 255, h_alpha), (0, y), (tab_rect.width, y))
            
            self.screen.blit(tab_surf, tab_rect.topleft)
            pygame.draw.rect(self.screen, border_color, tab_rect, 2, border_radius=12)
            
            strip_color = retro_style.primary if is_selected else (retro_style.secondary if is_hovered else (80, 100, 130))
            strip_w = self._s(6 if is_selected else 4, minimum=3, scale=scale)
            strip_rect = pygame.Rect(tab_rect.x + self._s(3, minimum=2, scale=scale), tab_rect.y + self._s(6, minimum=4, scale=scale), strip_w, tab_rect.height - self._s(12, minimum=8, scale=scale))
            pygame.draw.rect(self.screen, strip_color, strip_rect, border_radius=3)
            
            num_font = self._font(14, bold=True, minimum=10, scale=scale)
            num_color = retro_style.accent if is_selected else retro_style.text_muted
            num_surf = num_font.render(str(i + 1), True, num_color)
            self.screen.blit(num_surf, (tab_rect.x + self._s(16, minimum=12, scale=scale), tab_rect.y + self._s(8, minimum=5, scale=scale)))
            
            text_color = retro_style.text_primary if is_selected else retro_style.text_secondary
            title_surf = retro_style.render_fit_text(tab['title'], text_color, panel_width - self._s(40, minimum=28, scale=scale), self._s(20, minimum=14, scale=scale), bold=is_selected)
            self.screen.blit(title_surf, (tab_rect.x + self._s(16, minimum=12, scale=scale), tab_rect.centery - title_surf.get_height() // 2 + self._s(4, minimum=2, scale=scale)))

        self._draw_tab_panel_mascot(panel_width, height, tab_start_y, tab_height, gap, len(tabs))

    def _draw_tab_panel_mascot(self, panel_width: int, height: int, tab_start_y: int, tab_height: int, gap: int, tab_count: int):
        """Tab listesinin altındaki boş alana maskot paneli çiz"""
        scale = self._ui_scale()
        top_y = tab_start_y + tab_count * (tab_height + gap) + self._s(16, minimum=12, scale=scale)
        bottom_y = min(height - self._s(20, minimum=14, scale=scale), self._get_back_button_rect().top - self._s(12, minimum=8, scale=scale))
        available_height = bottom_y - top_y

        if available_height < self._s(110, minimum=84, scale=scale):
            return

        panel_rect = pygame.Rect(self._s(16, minimum=12, scale=scale), top_y, panel_width, available_height)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (16, 24, 40, 175), panel_surf.get_rect(), border_radius=14)
        self.screen.blit(panel_surf, panel_rect.topleft)
        pygame.draw.rect(self.screen, (70, 90, 120), panel_rect, 2, border_radius=14)

        image_area = panel_rect.inflate(-4, -4)
        mascot = self._get_selected_tab_mascot(image_area.width, image_area.height)
        if mascot is not None:
            mascot_x = image_area.centerx - mascot.get_width() // 2
            mascot_y = image_area.centery - mascot.get_height() // 2
            self.screen.blit(mascot, (mascot_x, mascot_y))


    def _draw_content_panel(self, x: int, width: int, height: int):
        scale = self._ui_scale()
        panel_rect = pygame.Rect(x, self._s(100, minimum=80, scale=scale), width, height)
        
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=170, border_color=retro_style.primary, glow=True)
        
        cache_key = self.selected_tab
        content_signature = self._content_cache_signature(width)
        if content_signature != self._last_content_signature or cache_key not in self._content_cache:
            self._content_cache.clear()
            self._last_content_signature = content_signature
        
        if cache_key not in self._content_cache:
            content_surface = self._build_content_surface(self.selected_tab, width - self._s(50, minimum=36, scale=scale))
            self._content_cache[cache_key] = content_surface
        
        content_surface = self._content_cache[cache_key]
        
        self.max_scroll = max(0, content_surface.get_height() - height + self._s(50, minimum=36, scale=scale))
        self.scroll_y = min(self.scroll_y, self.max_scroll)
        
        try:
            visible_height = min(height - self._s(40, minimum=28, scale=scale), content_surface.get_height() - self.scroll_y)
            if visible_height > 0:
                visible_content = content_surface.subsurface(
                    pygame.Rect(0, self.scroll_y, min(width - self._s(50, minimum=36, scale=scale), content_surface.get_width()), visible_height)
                )
                self.screen.blit(visible_content, (x + self._s(25, minimum=18, scale=scale), panel_rect.y + self._s(20, minimum=14, scale=scale)))
        except ValueError:
            self.screen.blit(content_surface, (x + self._s(25, minimum=18, scale=scale), panel_rect.y + self._s(20, minimum=14, scale=scale) - self.scroll_y))
        
        if self.max_scroll > 0:
            self._draw_scrollbar(panel_rect, height)

    def _draw_scrollbar(self, panel_rect: pygame.Rect, height: int):
        scale = self._ui_scale()
        sb_container = pygame.Rect(
            panel_rect.right - self._s(22, minimum=16, scale=scale),
            panel_rect.y + self._s(8, minimum=6, scale=scale),
            self._s(22, minimum=16, scale=scale),
            height - self._s(16, minimum=12, scale=scale),
        )
        self._sb_container_rect = sb_container
        self._sb_last_panel_rect = panel_rect
        content_height = height + self.max_scroll
        self._sb_thumb_rect = retro_style.draw_scrollbar(
            self.screen,
            sb_container,
            self.scroll_y,
            content_height,
            height,
            bar_width=self._s(10, minimum=8, scale=scale),
        )
    
    def _draw_action_button(
        self,
        btn_rect: pygame.Rect,
        is_hovered: bool,
        text: str,
        accent_color: Tuple[int, int, int],
    ):
        scale = self._ui_scale()
        if is_hovered:
            glow_rect = btn_rect.inflate(self._s(10, minimum=8, scale=scale), self._s(10, minimum=8, scale=scale))
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*accent_color[:3], 35), glow_surf.get_rect(), border_radius=12)
            self.screen.blit(glow_surf, glow_rect.topleft)
            bg_color = (35, 45, 70, 220)
            border_color = accent_color
        else:
            bg_color = (25, 32, 52, 200)
            border_color = (80, 100, 130)

        btn_surf = pygame.Surface(btn_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(btn_surf, bg_color, btn_surf.get_rect(), border_radius=12)
        self.screen.blit(btn_surf, btn_rect.topleft)
        pygame.draw.rect(self.screen, border_color, btn_rect, 2, border_radius=12)

        text_surf = retro_style.render_fit_text(text, (255, 255, 255), btn_rect.width - self._s(30, minimum=24, scale=scale), self._s(20, minimum=14, scale=scale), bold=True)
        text_x = btn_rect.centerx - text_surf.get_width() // 2
        text_y = btn_rect.centery - text_surf.get_height() // 2
        self.screen.blit(text_surf, (text_x, text_y))

    def _draw_tutorial_button(self):
        btn_rect = self._get_tutorial_button_rect()
        text = self._get_tutorial_button_label() + " (T)"
        self._draw_action_button(btn_rect, self.tutorial_hover, text, retro_style.primary)

    def _draw_back_button(self):
        btn_rect = self._get_back_button_rect()
        text = t('back') + " (ESC)"
        self._draw_action_button(btn_rect, self.back_hover, text, retro_style.secondary)
    
    def _draw_card_navigation(self, content_x: int, content_width: int, height: int):
        """Kart navigasyon helper — sayfa göstergesi geri butonuyla çakıştığı için kaldırıldı."""
        pass  # Sayfa X/Y metni geri butonuyla iç içe geçiyordu; kaldırıldı
    
    def _draw_hints(self, width: int, height: int):
        scale = self._ui_scale()
        hint_font = self._font(14, bold=False, minimum=10, scale=scale)
        hint_text = t('guide_hint_navigation')
        
        hint_surf = retro_style.render_fit_text(
            hint_text,
            retro_style.text_muted,
            max(self._s(120, minimum=96, scale=scale), width - self._s(40, minimum=28, scale=scale)),
            hint_font.get_height(),
            bold=False,
        )
        hint_x = width // 2 - hint_surf.get_width() // 2
        self.screen.blit(hint_surf, (hint_x, self._s(80, minimum=60, scale=scale)))
