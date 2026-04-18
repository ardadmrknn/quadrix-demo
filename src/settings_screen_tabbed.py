"""
Sekmeli Ayarlar Ekranı - Referans görseldeki gibi panel tabanlı tabbed settings.

Tek bir panel içinde 6 sekme:
  OYUN | GÖRÜNTÜ | SES | KONTROLLER | ÖZELLEŞTİRME | DİĞER

Her sekme kendi içinde bölüm başlıkları (section header) ve ayar satırları içerir.
"""

import os
import unicodedata
from pathlib import Path

import pygame
from constants import *
from retro_style import retro_style
from platform_utils import normalize_mouse_pos, get_mouse_pos
from background_effects import get_shared_falling_blocks_layer
from localization import (
    t, get_text, get_language, set_language, get_language_name,
    SUPPORTED_LANGUAGES, get_all_languages,
)
from ui_language_profile import apply_language_ui_profile, get_font_for_language
from menu import get_control_actions, get_mode_music_entries, get_campaign_phase_entries, BUILT_IN_TRACK_CHOICES, SUPPORTED_MUSIC_EXTENSIONS
from gamepad_manager import get_gamepad_manager, reload_gamepad_settings
from promptfont_support import get_gamepad_prompt_glyph, fit_promptfont_glyph_surface

try:
    from gamepad_manager import normalize_gamepad_event_button, normalize_gamepad_trigger_event
except ImportError:
    def normalize_gamepad_event_button(event):
        button = getattr(event, 'button', None)
        if isinstance(button, (int, float)) and not isinstance(button, bool):
            return int(button)
        return None

    def normalize_gamepad_trigger_event(event):
        if getattr(event, 'type', None) != getattr(pygame, 'JOYAXISMOTION', None):
            return None
        axis = getattr(event, 'axis', None)
        try:
            axis_index = int(axis)
        except Exception:
            return None
        if axis_index not in (4, 5):
            return None
        try:
            trigger_val = float(getattr(event, 'value', 0.0))
        except Exception:
            trigger_val = 0.0
        if trigger_val < 0.0:
            trigger_val = (trigger_val + 1.0) / 2.0
        if trigger_val >= 0.5:
            return 100 if axis_index == 4 else 101
        return None
from ui_scaling import UI_SCALE_PRESETS, get_projected_effective_scale, normalize_ui_scale_preset, scale_px


# ---------------------------------------------------------------------------
# Yardımcı: Lokalizasyon kısa yolu – key yoksa fallback döndürür
# ---------------------------------------------------------------------------
def _t(key: str, fallback: str = '') -> str:
    """t() wrapper – çeviri bulunamazsa fallback döndürür."""
    val = t(key)
    if val == key and fallback:
        return fallback
    return val


def _scale_menu_alpha(alpha: int) -> int:
    scaler = getattr(retro_style, '_scale_menu_alpha', None)
    if callable(scaler):
        try:
            return int(scaler(alpha))
        except Exception:
            pass

    try:
        value = int(alpha)
    except Exception:
        value = 0
    value = max(0, min(255, value))

    try:
        multiplier = float(getattr(retro_style, '_menu_transparency', 1.0))
    except Exception:
        multiplier = 1.0
    multiplier = max(0.0, min(1.0, multiplier))
    return int(value * multiplier)


_KNOWN_GAMEPAD_PROMPT_TYPES = {'xbox', 'playstation', 'nintendo', 'unknown'}


# ---------------------------------------------------------------------------
# Sekme ve ayar tanımları
# ---------------------------------------------------------------------------

# Her sekme (tab) bir dict:
#   'key':      sekme kimlik anahtarı
#   'label_tr': Türkçe etiket
#   'label_en': İngilizce etiket
TAB_DEFS = [
    {'key': 'game',      'loc_key': 'settings_tab_game', 'label_tr': 'OYUN', 'label_en': 'GAME'},
    {'key': 'display',   'loc_key': 'settings_tab_display', 'label_tr': 'GÖRÜNTÜ', 'label_en': 'DISPLAY'},
    {'key': 'audio',     'loc_key': 'settings_tab_audio', 'label_tr': 'SES', 'label_en': 'AUDIO'},
    {'key': 'controls',  'loc_key': 'settings_tab_controls', 'label_tr': 'KONTROLLER', 'label_en': 'CONTROLS'},
    {'key': 'customize', 'loc_key': 'settings_tab_customize', 'label_tr': 'ÖZELLEŞTİRME', 'label_en': 'CUSTOMIZE'},
    {'key': 'other',     'loc_key': 'settings_tab_other', 'label_tr': 'DİĞER', 'label_en': 'OTHER'},
]

_SETTINGS_REFERENCE_SIZE = (1366.0, 768.0)

_UI_SCALE_PRESET_LABELS = {
    'compact': ('Kompakt', 'Compact'),
    'normal': ('Normal', 'Normal'),
    'large': ('Buyuk', 'Large'),
}


def _tab_label(tab_def: dict) -> str:
    loc_key = tab_def.get('loc_key')
    if loc_key:
        localized = t(str(loc_key))
        if localized != str(loc_key):
            return localized

    lang = get_language()
    if lang == 'tr':
        return tab_def['label_tr']
    return tab_def['label_en']


def _ui_scale_preset_label(preset: str) -> str:
    normalized = normalize_ui_scale_preset(preset)
    tr_label, en_label = _UI_SCALE_PRESET_LABELS[normalized]
    return tr_label if get_language() == 'tr' else en_label


# Ayar tipleri:
#   'toggle'   – açık / kapalı
#   'selector' – < değer > okları
#   'slider'   – sürgü (min/max/step)
#   'submenu'  – alt menüye yönlendirme (>)
#   'section'  – bölüm başlığı (çizilir, seçilemez)


def _build_tab_content(tab_key: str, sm, show_debug: bool = False) -> list[dict]:
    """Verilen sekme için ayar öğeleri listesini oluştur."""
    items: list[dict] = []

    if tab_key == 'game':
        items.append({'type': 'section', 'loc_key': 'settings_section_gameplay', 'label_tr': 'OYNANIŞ', 'label_en': 'GAMEPLAY'})
        items.append({
            'type': 'slider', 'key': 'das_delay',
            'loc_key': 'settings_das_delay',
            'label_tr': 'Basılı Tutma Gecikmesi', 'label_en': 'Hold Delay (DAS)',
            'min': 50, 'max': 300, 'step': 10, 'suffix': 'ms',
        })
        items.append({
            'type': 'slider', 'key': 'das_repeat',
            'loc_key': 'settings_das_repeat',
            'label_tr': 'Basılı Tutma Kayma Hızı', 'label_en': 'Hold Move Speed (ARR)',
            'min': 10, 'max': 500, 'step': 5, 'suffix': 'ms',
        })
        items.append({
            'type': 'slider', 'key': 'soft_drop_speed',
            'loc_key': 'settings_soft_drop_speed',
            'label_tr': 'Aşağı Tuşu Düşüş Hızı', 'label_en': 'Down Key Drop Speed',
            'min': 20, 'max': 100, 'step': 5, 'suffix': 'ms',
        })

    elif tab_key == 'display':
        items.append({'type': 'section', 'loc_key': 'settings_section_screen', 'label_tr': 'EKRAN', 'label_en': 'SCREEN'})
        items.append({
            'type': 'toggle', 'key': 'vsync',
            'loc_key': 'vsync',
            'label_tr': 'VSync', 'label_en': 'VSync',
        })
        items.append({
            'type': 'selector', 'key': 'fps_limit',
            'loc_key': 'fps_limit',
            'label_tr': 'FPS Limiti', 'label_en': 'FPS Limit',
        })
        items.append({
            'type': 'selector', 'key': 'ui_scale_preset',
            'label_tr': 'Arayuz Olcegi', 'label_en': 'UI Scale',
        })

        items.append({'type': 'section', 'loc_key': 'settings_section_visual', 'label_tr': 'GÖRSEL', 'label_en': 'VISUAL'})
        items.append({
            'type': 'toggle', 'key': 'show_ghost',
            'loc_key': 'show_ghost',
            'label_tr': 'Gölge Bloğu', 'label_en': 'Ghost Piece',
        })
        items.append({
            'type': 'toggle', 'key': 'background_enabled',
            'loc_key': 'show_background',
            'label_tr': 'Arka Plan', 'label_en': 'Background',
        })
        items.append({
            'type': 'slider', 'key': 'bg_transparency',
            'loc_key': 'bg_transparency',
            'label_tr': 'Arka Plan Şeffaflığı', 'label_en': 'BG Transparency',
            'min': 0.0, 'max': 1.0, 'step': 0.1, 'suffix': '%', 'percent': True,
        })
        items.append({
            'type': 'slider', 'key': 'effects_opacity',
            'loc_key': 'effects_opacity',
            'label_tr': 'Efekt Şeffaflığı', 'label_en': 'Effects Opacity',
            'min': 0.0, 'max': 1.0, 'step': 0.1, 'suffix': '%', 'percent': True,
        })
        items.append({
            'type': 'slider', 'key': 'menu_transparency',
            'loc_key': 'menu_transparency',
            'label_tr': 'Menü Şeffaflığı', 'label_en': 'Menu Transparency',
            'min': 0.0, 'max': 1.0, 'step': 0.1, 'suffix': '%', 'percent': True,
        })
        items.append({
            'type': 'slider', 'key': 'particle_effects',
            'loc_key': 'particle_effects',
            'label_tr': 'Parçacık Efektleri', 'label_en': 'Particle Effects',
            'min': 0, 'max': 3, 'step': 1,
        })

    elif tab_key == 'audio':
        items.append({'type': 'section', 'loc_key': 'settings_section_music', 'label_tr': 'MÜZİK', 'label_en': 'MUSIC'})
        items.append({
            'type': 'toggle', 'key': 'music_enabled',
            'loc_key': 'music',
            'label_tr': 'Müzik', 'label_en': 'Music',
        })
        items.append({
            'type': 'slider', 'key': 'music_volume',
            'loc_key': 'music_volume',
            'label_tr': 'Müzik Ses Seviyesi', 'label_en': 'Music Volume',
            'min': 0.0, 'max': 1.0, 'step': 0.05, 'suffix': '%', 'percent': True,
        })
        items.append({
            'type': 'slider', 'key': 'menu_music_volume',
            'loc_key': 'menu_music_volume',
            'label_tr': 'Ana Menü Müzik Seviyesi', 'label_en': 'Menu Music Volume',
            'min': 0.0, 'max': 1.0, 'step': 0.05, 'suffix': '%', 'percent': True,
        })

        items.append({'type': 'section', 'loc_key': 'settings_section_sound_effects', 'label_tr': 'SES EFEKTLERİ', 'label_en': 'SOUND EFFECTS'})
        items.append({
            'type': 'toggle', 'key': 'sound_enabled',
            'loc_key': 'sound_effects',
            'label_tr': 'Ses Efektleri', 'label_en': 'Sound Effects',
        })
        items.append({
            'type': 'slider', 'key': 'sfx_volume',
            'loc_key': 'sfx_volume',
            'label_tr': 'Efekt Ses Seviyesi', 'label_en': 'SFX Volume',
            'min': 0.0, 'max': 1.0, 'step': 0.05, 'suffix': '%', 'percent': True,
        })

        items.append({'type': 'section', 'loc_key': 'settings_section_general', 'label_tr': 'GENEL', 'label_en': 'GENERAL'})
        items.append({
            'type': 'toggle', 'key': 'mute_all',
            'loc_key': 'mute_all',
            'label_tr': 'Tümünü Sessize Al', 'label_en': 'Mute All',
        })

        # Müzik modu seçicileri (eski ModeMusicScreen yerine)
        items.append({
            'type': 'toggle', 'key': 'music_shuffle',
            'loc_key': 'music_shuffle',
            'label_tr': 'Müzik Karıştır (Shuffle)', 'label_en': 'Shuffle Music',
        })
        items.append({'type': 'section', 'loc_key': 'settings_section_mode_music', 'label_tr': 'MOD MÜZİKLERİ', 'label_en': 'MODE MUSIC'})
        for mode_key, mode_label in get_mode_music_entries():
            items.append({
                'type': 'music_selector', 'key': f'mode_music_{mode_key}',
                'mode_key': mode_key,
                'label': mode_label,
                'label_tr': mode_label, 'label_en': mode_label,
            })

    elif tab_key == 'controls':
        # Kontrol tuşları inline (eski ControlSettingsScreen yerine)
        ctrl_actions = get_control_actions()
        items.append({'type': 'section', 'loc_key': 'tab_single_player', 'label_tr': 'TEK OYUNCU', 'label_en': 'SINGLE PLAYER'})
        for action_key, label in ctrl_actions.get('single_player', []):
            items.append({
                'type': 'keybind', 'key': f'ctrl_sp_{action_key}',
                'action_key': action_key, 'section': 'single_player',
                'label_tr': label, 'label_en': label,
            })
        items.append({'type': 'section', 'loc_key': 'tab_pvp_player1', 'label_tr': 'PVP - OYUNCU 1', 'label_en': 'PVP - PLAYER 1'})
        for action_key, label in ctrl_actions.get('pvp.player1', []):
            items.append({
                'type': 'keybind', 'key': f'ctrl_pvp1_{action_key}',
                'action_key': action_key, 'section': 'pvp.player1',
                'label_tr': label, 'label_en': label,
            })
        items.append({'type': 'section', 'loc_key': 'tab_pvp_player2', 'label_tr': 'PVP - OYUNCU 2', 'label_en': 'PVP - PLAYER 2'})
        for action_key, label in ctrl_actions.get('pvp.player2', []):
            items.append({
                'type': 'keybind', 'key': f'ctrl_pvp2_{action_key}',
                'action_key': action_key, 'section': 'pvp.player2',
                'label_tr': label, 'label_en': label,
            })

        ingame_gamepad_actions = [
            ('hard_drop', _t('gp_hard_drop', 'Anında bırak')),
            ('hold', _t('gp_hold', 'Hold / Değiştir')),
            ('hold2', _t('card_perk_second_pocket_title', 'Ekstra Cep')),
            ('pause', _t('gp_pause', 'Duraklat')),
            ('discard_held', _t('gp_discard_held', 'Tutulanı At')),
        ]
        outgame_gamepad_actions = [
            ('menu_confirm', _t('gp_menu_confirm', 'Menü Onay')),
            ('menu_back', _t('gp_menu_back', 'Menü Geri')),
            ('menu_tab_next', _t('gp_menu_tab_next', 'Sekme Sonraki')),
            ('menu_tab_prev', _t('gp_menu_tab_prev', 'Sekme Önceki')),
        ]
        items.append({'type': 'section', 'loc_key': 'settings_gp_section_ingame', 'label_tr': 'GAMEPAD - OYUN İÇİ', 'label_en': 'GAMEPAD - IN-GAME'})
        items.append({
            'type': 'slider', 'key': 'ctrl_gp_rumble',
            'loc_key': 'gp_rumble',
            'label_tr': _t('gp_rumble', 'Titreşim'), 'label_en': _t('gp_rumble', 'Vibration'),
            'min': 0, 'max': 3, 'step': 1,
        })
        for action_key, label in ingame_gamepad_actions:
            items.append({
                'type': 'keybind', 'key': f'ctrl_gp_{action_key}',
                'action_key': action_key, 'section': 'gamepad.ingame',
                'label_tr': label, 'label_en': label,
            })
        items.append({'type': 'section', 'loc_key': 'settings_gp_section_outgame', 'label_tr': 'GAMEPAD - OYUN DIŞI', 'label_en': 'GAMEPAD - OUT OF GAME'})
        for action_key, label in outgame_gamepad_actions:
            items.append({
                'type': 'keybind', 'key': f'ctrl_gp_{action_key}',
                'action_key': action_key, 'section': 'gamepad.outgame',
                'label_tr': label, 'label_en': label,
            })

    elif tab_key == 'customize':
        items.append({'type': 'section', 'loc_key': 'settings_section_blocks', 'label_tr': 'BLOKLAR', 'label_en': 'BLOCKS'})
        items.append({
            'type': 'submenu', 'key': 'block_styles',
            'loc_key': 'block_styles',
            'label_tr': 'Blok Stilleri', 'label_en': 'Block Styles',
        })
        items.append({
            'type': 'submenu', 'key': 'piece_workshop',
            'loc_key': 'piece_workshop',
            'label_tr': 'Parça Atölyesi', 'label_en': 'Piece Workshop',
        })

    elif tab_key == 'other':
        items.append({'type': 'section', 'loc_key': 'settings_section_system', 'label_tr': 'SİSTEM', 'label_en': 'SYSTEM'})
        items.append({
            'type': 'selector', 'key': 'language',
            'loc_key': 'language',
            'label_tr': 'Dil', 'label_en': 'Language',
        })
        if show_debug:
            items.append({'type': 'section', 'loc_key': 'settings_section_developer', 'label_tr': 'GELİŞTİRİCİ', 'label_en': 'DEVELOPER'})
            items.append({
                'type': 'toggle', 'key': 'debug_mode',
                'loc_key': 'debug_mode',
                'label_tr': 'Debug Modu', 'label_en': 'Debug Mode',
            })
            items.append({
                'type': 'toggle', 'key': 'card_mode_debug',
                'loc_key': 'card_debug',
                'label_tr': 'Kart Debug', 'label_en': 'Card Debug',
            })

    return items


def _item_label(item: dict) -> str:
    loc_key = item.get('loc_key')
    if loc_key:
        localized = t(str(loc_key))
        if localized != str(loc_key):
            return localized

    if 'label' in item and item.get('label'):
        return str(item.get('label'))

    lang = get_language()
    if lang == 'tr':
        return item.get('label_tr', '')
    return item.get('label_en', '')


def _latinize_track_display_name(raw_name: str) -> str:
    """Parça adını Türkçe latin alfabe uyumlu, okunur forma getir."""
    if not raw_name:
        return ''

    text = str(raw_name).replace('_', ' ').replace('-', ' ').strip()
    if not text:
        return ''

    # Unicode ayır, diakritikleri sadeleştir
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))

    # Türkçe latin alfabeye yakın normalize
    tr_map = str.maketrans({
        'ı': 'i', 'İ': 'I',
        'ğ': 'g', 'Ğ': 'G',
        'ş': 's', 'Ş': 'S',
        'ç': 'c', 'Ç': 'C',
        'ö': 'o', 'Ö': 'O',
        'ü': 'u', 'Ü': 'U',
    })
    text = text.translate(tr_map)

    cleaned_chars: list[str] = []
    prev_space = False
    for ch in text:
        if ch.isalnum():
            cleaned_chars.append(ch)
            prev_space = False
        elif ch.isspace() and not prev_space:
            cleaned_chars.append(' ')
            prev_space = True

    normalized = ''.join(cleaned_chars).strip()
    if not normalized:
        return _t('track_custom_fallback', 'Ozel Parca')
    return normalized.title()


# ---------------------------------------------------------------------------
# Ana Sınıf
# ---------------------------------------------------------------------------

class TabbedSettingsScreen:
    """Sekmeli ayarlar ekranı – tek panel içinde tüm ayar kategorileri."""

    FPS_LIMITS = [0, 60, 90, 120, 144, 240]

    def __init__(
        self,
        screen: pygame.Surface,
        theme_manager,
        settings_manager,
        sound_manager=None,
    ) -> None:
        self.screen = screen
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
        self.sound_manager = sound_manager

        # Arka plan efektleri
        self.background_fx = get_shared_falling_blocks_layer('default')

        # Sekme durumu
        self.current_tab = 0  # Aktif sekme indeksi
        self.selected = 0      # Seçili ayar satırı indeksi (section hariç)
        self.scroll_offset = 0
        self.option_rects: list[pygame.Rect] = []

        self._ui_reference_size = _SETTINGS_REFERENCE_SIZE
        self._ui_scale_current = 1.0
        self._font_scale_signature = None
        self._base_font_title_size = 36
        self._base_font_tab_size = 20
        self._base_font_section_size = 20
        self._base_font_label_size = 24
        self._base_font_value_size = 22
        self._base_font_small_size = 18
        self._base_font_hint_size = 16

        # Font'lar
        self._apply_responsive_metrics()

        # Tüm ayar değerlerini settings_manager'dan yükle
        self._load_all_settings()

        # Sekme içeriklerini oluştur
        self._rebuild_tab_content()

        # Smooth slider animasyonları
        self._anim_last_tick = pygame.time.get_ticks()
        self._music_volume_vis = float(self.music_volume)
        self._menu_music_volume_vis = float(self.menu_music_volume)
        self._sfx_volume_vis = float(self.sfx_volume)

        # Tab rect'leri (mouse için)
        self._tab_rects: list[pygame.Rect] = []

        # VSync restart prompt
        self._vsync_prompt_active = False
        self._vsync_prompt_choice = 0
        self._vsync_prompt_buttons: list[pygame.Rect] = []

        # Display mode confirm (geri uyumluluk: fullscreen selector testleri)
        self._display_mode_confirm_active = False
        self._display_mode_confirm_prev_fullscreen = bool(self.fullscreen)
        self._display_mode_confirm_target_fullscreen = bool(self.fullscreen)
        self._display_mode_confirm_yes_rect: pygame.Rect | None = None
        self._display_mode_confirm_no_rect: pygame.Rect | None = None

        # SettingsScreen uyumluluk alanları (main.py bunlara erişiyor)
        self.music_enabled = self.settings_manager.get('music_enabled', True)
        self.sound_enabled = self.settings_manager.get('sound_enabled', True)
        self.effects_enabled = self.settings_manager.get('effects_enabled', True)
        self.background_enabled = self.settings_manager.get('background_enabled', True)
        self.menu_music = self.settings_manager.get('menu_music', 'main_1')
        self.game_music = self.settings_manager.get('game_music', 'klasik_1')
        self.mute_all = self.settings_manager.get('mute_all', False)
        self.debug_mode = self.settings_manager.get('debug_mode', False)
        self.card_mode_debug = self.settings_manager.get('card_mode_debug', False)
        self.difficulty = 'Normal'
        self.custom_background = self.settings_manager.get('custom_background', None)
        self._show_debug_settings = bool(self.settings_manager.get('show_debug_settings', False))
        self.current_language = self.settings_manager.get('language', 'tr')

        # ── Kontrol tuş bağlama (keybind) durumu ──
        self._control_config = self.settings_manager.get_controls()
        self._last_known_gamepad_prompt_type = self._normalize_gamepad_prompt_type(
            self.settings_manager.get('last_gamepad_prompt_type', None)
        )
        self._waiting_for_key = False
        self._pending_keybind_item = None  # keybind item dict'i
        self._pending_keybind_slot = 'primary'
        self._single_player_bind_slot = 'primary'
        self._gamepad_bind_slot = 'primary'
        self._swallow_next_keydown = False
        self._swallow_next_gamepad_click = False
        self._swallow_next_gamepad_click_deadline_ms = 0
        self._capture_started_by_gamepad_click = False
        self._keybind_slot_rects: list[dict | None] = []
        self._help_icon_rects: list[tuple[pygame.Rect, str]] = []

        # ── Müzik modu seçicileri (music_selector) ──
        self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()
        self._music_root = Path(__file__).resolve().parent.parent / 'music'
        self._track_options = self._build_track_options()
        self._music_picker_open = False
        self._music_picker_mode_key = None
        self._music_picker_selected = 0
        self._music_picker_scroll = 0
        self._music_picker_item_rects: list[tuple[pygame.Rect, int]] = []

        # ── Mod playlist editörü (inline overlay) ──
        self._playlist_edit_active = False
        self._playlist_edit_mode_key = None
        self._playlist_edit_items = []
        self._playlist_edit_selected = 0
        self._playlist_edit_scroll = 0
        self._playlist_edit_picker_open = False
        self._playlist_edit_picker_selected = 0
        self._playlist_edit_picker_scroll = 0
        self._playlist_edit_item_rects: list[tuple[pygame.Rect, int]] = []
        self._playlist_edit_picker_rects: list[tuple[pygame.Rect, int]] = []

        # ── Kampanya faz seçici overlay ──
        self._campaign_phase_select_active = False
        self._campaign_phase_selected = 0
        self._campaign_phase_item_rects: list[tuple[pygame.Rect, int]] = []

        # Slider mouse cache + drag state
        self._slider_bar_rects: dict = {}
        self._slider_action_rects: dict = {}
        self._slider_drag_active: bool = False
        self._slider_drag_key: str = ''
        self._slider_drag_item: dict | None = None
        self._slider_drag_bar_rect: pygame.Rect | None = None

        # Close button rect
        self._close_btn_rect: pygame.Rect | None = None

        # Settings scrollbar drag state
        self._settings_sb_thumb_rect: pygame.Rect | None = None
        self._settings_sb_container_rect: pygame.Rect | None = None
        self._settings_sb_drag_active: bool = False
        self._settings_sb_drag_offset_y: int = 0

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.22) -> float:
        try:
            return get_projected_effective_scale(
                self.screen,
                min_scale=min_scale,
                max_scale=max_scale,
                reference_size=getattr(self, '_ui_reference_size', _SETTINGS_REFERENCE_SIZE),
            )
        except Exception:
            return 1.0

    def _s(self, value: int | float, minimum: int = 1) -> int:
        return scale_px(value, getattr(self, '_ui_scale_current', 1.0), minimum=minimum)

    def _font(self, size: int | float, *, bold: bool = False, minimum: int = 8):
        return retro_style.get_font(self._s(size, minimum=minimum), bold=bold)

    def _fit_font(
        self,
        text: str,
        size: int | float,
        max_width: int,
        *,
        bold: bool = False,
        minimum: int = 8,
    ):
        return retro_style.get_fitting_font(
            text,
            self._s(size, minimum=minimum),
            max_width,
            bold=bold,
            min_size=self._s(minimum, minimum=minimum),
        )

    def _apply_responsive_metrics(self) -> None:
        self._ui_scale_current = self._ui_scale()
        self._refresh_fonts()

    def _screen_size(self, default: tuple[int, int] = (1366, 768)) -> tuple[int, int]:
        screen = getattr(self, 'screen', None)
        if screen is None:
            return default
        try:
            if hasattr(screen, 'get_size'):
                width, height = screen.get_size()
            elif hasattr(screen, 'get_width') and hasattr(screen, 'get_height'):
                width, height = screen.get_width(), screen.get_height()
            else:
                return default
            return max(1, int(width)), max(1, int(height))
        except Exception:
            return default

    def _layout_metrics(self) -> dict[str, int | pygame.Rect]:
        self._apply_responsive_metrics()
        width, height = self._screen_size()

        panel_max_w = self._s(1200, minimum=760)
        panel_min_w = self._s(700, minimum=540)
        panel_max_h = self._s(850, minimum=560)
        panel_min_h = self._s(500, minimum=420)
        panel_w = min(panel_max_w, max(panel_min_w, int(width * 0.88)))
        panel_h = min(panel_max_h, max(panel_min_h, int(height * 0.88)))
        panel = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)

        tab_bar = pygame.Rect(
            panel.x,
            panel.y + self._s(56, minimum=42),
            panel.width,
            self._s(44, minimum=34),
        )
        content = pygame.Rect(
            panel.x + self._s(18, minimum=12),
            panel.y + self._s(110, minimum=84),
            panel.width - self._s(36, minimum=24),
            panel.height - self._s(124, minimum=96),
        )

        return {
            'panel': panel,
            'tab_bar': tab_bar,
            'content': content,
            'panel_shadow_pad': self._s(10, minimum=8),
            'panel_shadow_offset': self._s(5, minimum=4),
            'panel_shadow_radius': self._s(16, minimum=12),
            'panel_border_radius': self._s(14, minimum=10),
            'panel_border_width': self._s(2, minimum=1),
            'title_pad_x': self._s(20, minimum=14),
            'title_pad_y': self._s(10, minimum=8),
            'title_rule_y': self._s(48, minimum=36),
            'title_rule_inset': self._s(10, minimum=8),
            'tab_inner_margin': self._s(10, minimum=8),
            'tab_gap': self._s(6, minimum=4),
            'tab_indicator_height': self._s(3, minimum=2),
            'row_height': self._s(58, minimum=44),
            'section_height': self._s(40, minimum=30),
            'row_inset_x': self._s(8, minimum=6),
            'row_inset_y': self._s(2, minimum=1),
            'row_inner_height_delta': self._s(6, minimum=4),
            'scroll_step': self._s(30, minimum=18),
            'scrollbar_gap': self._s(6, minimum=4),
            'scrollbar_bar_width': self._s(10, minimum=8),
            'scrollbar_padding': self._s(2, minimum=2),
            'scrollbar_track_min': self._s(4, minimum=4),
            'scrollbar_thumb_fallback': self._s(30, minimum=20),
        }

    def _content_total_height(self, row_h: int | None = None, section_h: int | None = None) -> int:
        metrics = self._layout_metrics()
        row_height = int(row_h if row_h is not None else metrics['row_height'])
        section_height = int(section_h if section_h is not None else metrics['section_height'])
        total = 0
        for item in getattr(self, '_tab_items', []):
            total += section_height if item.get('type') == 'section' else row_height
        return total

    def _settings_scrollbar_layout(
        self,
        panel: pygame.Rect | None = None,
        content: pygame.Rect | None = None,
    ) -> dict[str, int | pygame.Rect]:
        metrics = self._layout_metrics()
        panel_rect = panel or metrics['panel']
        content_rect = content or metrics['content']
        bar_width = int(metrics['scrollbar_bar_width'])
        padding = int(metrics['scrollbar_padding'])
        container = pygame.Rect(
            panel_rect.right + int(metrics['scrollbar_gap']),
            content_rect.y,
            bar_width + padding * 2,
            content_rect.height,
        )
        arrow_zone = max(bar_width, bar_width + padding)
        track_y = container.top + arrow_zone + padding
        track_h = max(
            int(metrics['scrollbar_track_min']),
            container.height - arrow_zone * 2 - int(metrics['scrollbar_track_min']),
        )
        track_bottom = track_y + track_h
        return {
            'container': container,
            'bar_width': bar_width,
            'padding': padding,
            'arrow_zone': arrow_zone,
            'track_y': track_y,
            'track_h': track_h,
            'up_arrow_rect': pygame.Rect(
                container.x,
                container.top,
                container.width,
                max(0, track_y - container.top),
            ),
            'down_arrow_rect': pygame.Rect(
                container.x,
                track_bottom,
                container.width,
                max(0, container.bottom - track_bottom),
            ),
            'thumb_fallback': int(metrics['scrollbar_thumb_fallback']),
        }

    def _campaign_phase_overlay_metrics(self) -> dict[str, int | pygame.Rect]:
        self._apply_responsive_metrics()
        width, height = self._screen_size((1280, 720))
        panel_w = min(self._s(680, minimum=520), width - self._s(100, minimum=72))
        panel_h = min(self._s(540, minimum=420), height - self._s(80, minimum=60))
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        item_h = self._s(68, minimum=52)
        gap = self._s(10, minimum=6)
        return {
            'panel': panel_rect,
            'title_x': panel_rect.x + self._s(24, minimum=16),
            'title_y': panel_rect.y + self._s(18, minimum=14),
            'list_y': panel_rect.y + self._s(70, minimum=54),
            'item_h': item_h,
            'gap': gap,
            'item_x': panel_rect.x + self._s(20, minimum=14),
            'item_w': panel_rect.width - self._s(40, minimum=28),
        }

    def _music_picker_metrics(self) -> dict[str, int | pygame.Rect]:
        self._apply_responsive_metrics()
        width, height = self._screen_size((1280, 720))
        panel_w = min(self._s(880, minimum=640), width - self._s(140, minimum=96))
        panel_h = min(self._s(680, minimum=500), height - self._s(120, minimum=84))
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        panel_right = panel_rect.x + panel_rect.width
        list_rect = pygame.Rect(
            panel_rect.x + self._s(20, minimum=14),
            panel_rect.y + self._s(90, minimum=68),
            panel_rect.width - self._s(40, minimum=28),
            panel_rect.height - self._s(130, minimum=96),
        )
        return {
            'panel': panel_rect,
            'list_rect': list_rect,
            'item_h': self._s(52, minimum=40),
            'gap': self._s(8, minimum=6),
            'scroll_step': self._s(36, minimum=24),
            'title_x': panel_rect.x + self._s(20, minimum=14),
            'title_y': panel_rect.y + self._s(18, minimum=14),
            'subtitle_y': panel_rect.y + self._s(52, minimum=40),
            'scrollbar_x': panel_right - self._s(12, minimum=8),
            'scrollbar_w': self._s(6, minimum=4),
        }

    def _playlist_overlay_metrics(self) -> dict[str, int | pygame.Rect]:
        self._apply_responsive_metrics()
        width, height = self._screen_size((1280, 720))
        panel_w = min(self._s(920, minimum=680), width - self._s(120, minimum=84))
        panel_h = min(self._s(730, minimum=540), height - self._s(90, minimum=64))
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        panel_right = panel_rect.x + panel_rect.width
        panel_bottom = panel_rect.y + panel_rect.height
        list_rect = pygame.Rect(
            panel_rect.x + self._s(20, minimum=14),
            panel_rect.y + self._s(86, minimum=64),
            panel_rect.width - self._s(40, minimum=28),
            panel_rect.height - self._s(206, minimum=154),
        )

        picker_w = min(self._s(760, minimum=560), width - self._s(180, minimum=120))
        picker_h = min(self._s(580, minimum=420), height - self._s(180, minimum=120))
        picker_rect = pygame.Rect((width - picker_w) // 2, (height - picker_h) // 2, picker_w, picker_h)
        picker_right = picker_rect.x + picker_rect.width
        picker_list_rect = pygame.Rect(
            picker_rect.x + self._s(18, minimum=14),
            picker_rect.y + self._s(62, minimum=48),
            picker_rect.width - self._s(36, minimum=28),
            picker_rect.height - self._s(84, minimum=64),
        )
        return {
            'panel': panel_rect,
            'list_rect': list_rect,
            'item_h': self._s(52, minimum=40),
            'gap': self._s(8, minimum=6),
            'scroll_step': self._s(30, minimum=18),
            'title_x': panel_rect.x + self._s(20, minimum=14),
            'title_y': panel_rect.y + self._s(16, minimum=12),
            'subtitle_y': panel_rect.y + self._s(50, minimum=38),
            'scrollbar_rect': pygame.Rect(
                panel_right - self._s(22, minimum=16),
                list_rect.y,
                self._s(22, minimum=16),
                list_rect.height,
            ),
            'hint_x': panel_rect.x + self._s(20, minimum=14),
            'hint_y': panel_bottom - self._s(28, minimum=20),
            'action_h': self._s(38, minimum=30),
            'action_gap': self._s(10, minimum=8),
            'action_y': list_rect.bottom + self._s(10, minimum=8),
            'picker': picker_rect,
            'picker_list_rect': picker_list_rect,
            'picker_item_h': self._s(48, minimum=38),
            'picker_gap': self._s(8, minimum=6),
            'picker_scroll_step': self._s(36, minimum=24),
            'picker_title_x': picker_rect.x + self._s(18, minimum=14),
            'picker_title_y': picker_rect.y + self._s(14, minimum=10),
            'picker_scrollbar_rect': pygame.Rect(
                picker_right - self._s(22, minimum=16),
                picker_list_rect.y,
                self._s(22, minimum=16),
                picker_list_rect.height,
            ),
        }

    # ------------------------------------------------------------------
    # Ayar yükleme
    # ------------------------------------------------------------------

    def _load_all_settings(self) -> None:
        sm = self.settings_manager
        # Gameplay
        self.das_delay = sm.get('das_delay', 170)
        self.das_repeat = sm.get('das_repeat', 50)
        self.soft_drop_speed = sm.get('soft_drop_speed', 50)
        # Display
        self.fullscreen = True
        self.resolution = 'auto'
        self.vsync = sm.get('vsync', True)
        self.fps_limit = sm.get('fps_limit', 0)
        self.ui_scale_preset = normalize_ui_scale_preset(sm.get('ui_scale_preset', 'normal'))
        self.show_ghost = sm.get('show_ghost', True)
        self.background_enabled = sm.get('background_enabled', True)
        self.bg_transparency = sm.get('bg_transparency', 0.3)
        self.effects_opacity = sm.get('effects_opacity', 1.0)
        self.menu_transparency = sm.get('menu_transparency', 1.0)
        self.particle_effects = self._particle_effects_level_to_slider_value(sm.get('particle_effects', 'medium'))
        # Audio
        self.music_enabled = sm.get('music_enabled', True)
        self.music_volume = sm.get('music_volume', 0.3)
        self.menu_music_volume = sm.get('menu_music_volume', 0.3)
        self.sound_enabled = sm.get('sound_enabled', True)
        self.sfx_volume = sm.get('sfx_volume', 0.5)
        self.mute_all = sm.get('mute_all', False)
        # Other
        self.current_language = sm.get('language', 'tr')
        self.debug_mode = sm.get('debug_mode', False)
        self.card_mode_debug = sm.get('card_mode_debug', False)
        self._show_debug_settings = bool(sm.get('show_debug_settings', False))

    def _refresh_fonts(self) -> None:
        title_size = max(24, self._s(getattr(self, '_base_font_title_size', 36), minimum=24))
        tab_size = max(14, self._s(getattr(self, '_base_font_tab_size', 20), minimum=14))
        section_size = max(14, self._s(getattr(self, '_base_font_section_size', 20), minimum=14))
        label_size = max(16, self._s(getattr(self, '_base_font_label_size', 24), minimum=16))
        value_size = max(15, self._s(getattr(self, '_base_font_value_size', 22), minimum=15))
        small_size = max(12, self._s(getattr(self, '_base_font_small_size', 18), minimum=12))
        hint_size = max(11, self._s(getattr(self, '_base_font_hint_size', 16), minimum=11))
        language_signature = getattr(self, 'current_language', None)
        if not language_signature:
            try:
                language_signature = get_language()
            except Exception:
                language_signature = ''
        signature = (title_size, tab_size, section_size, label_size, value_size, small_size, hint_size, str(language_signature))
        if signature == getattr(self, '_font_scale_signature', None):
            return

        self.font_title = retro_style.get_font(title_size)
        self.font_tab = retro_style.get_font(tab_size, bold=True)
        self.font_section = retro_style.get_font(section_size, bold=True)
        self.font_label = retro_style.get_font(label_size, bold=True)
        self.font_value = retro_style.get_font(value_size, bold=True)
        self.font_small = retro_style.get_font(small_size, bold=False)
        self.font_hint = retro_style.get_font(hint_size, bold=False)
        self._font_scale_signature = signature

    def _build_track_options(self) -> list[dict]:
        """Müzik seçici için parça seçeneklerini üret.

        Çıktı formatı: [{'label': str, 'value': str | None}, ...]
        """
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

        options: list[dict] = [{'label': t('track_default_label'), 'value': None}]
        seen_values: set[str] = set()

        for label, value in BUILT_IN_TRACK_CHOICES:
            key = _normalize_name(value or label)
            if key and key in seen_values:
                continue
            options.append({'label': str(label), 'value': value})
            if key:
                seen_values.add(key)

        for rel_path in self._scan_music_files():
            key = _normalize_name(rel_path)
            if key and key in seen_values:
                continue
            display_name = _latinize_track_display_name(Path(rel_path).stem)
            options.append({
                'label': f"{display_name} {t('track_file_suffix')}",
                'value': f"file:{rel_path}",
            })
            if key:
                seen_values.add(key)

        return options

    def _scan_music_files(self) -> list[str]:
        if not self._music_root.exists():
            return []
        files: list[str] = []
        for dirpath, _, filenames in os.walk(self._music_root):
            for filename in filenames:
                if Path(filename).suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS:
                    full_path = Path(dirpath) / filename
                    rel_path = full_path.relative_to(self._music_root).as_posix()
                    files.append(rel_path)
        return sorted(files)

    def _rebuild_tab_content(self) -> None:
        """Aktif sekmenin ayar öğelerini yeniden oluştur."""
        tab_key = TAB_DEFS[self.current_tab]['key']
        self._tab_items = _build_tab_content(
            tab_key, self.settings_manager, self._show_debug_settings,
        )
        # Seçilebilir öğe indeksleri (section hariç)
        self._selectable_indices = [
            i for i, item in enumerate(self._tab_items) if item['type'] != 'section'
        ]
        if self.selected >= len(self._selectable_indices):
            self.selected = max(0, len(self._selectable_indices) - 1)
        self.scroll_offset = 0

    def focus_tab(self, tab_key: str, setting_key: str | None = None) -> None:
        """Dışarıdan sekme/öğe odaklamak için yardımcı API.

        Args:
            tab_key: TAB_DEFS içindeki sekme anahtarı.
            setting_key: Opsiyonel ayar anahtarı (item['key']).
        """
        tab_index = next((i for i, tab in enumerate(TAB_DEFS) if tab.get('key') == tab_key), None)
        if tab_index is None:
            return

        if tab_index != self.current_tab:
            self.current_tab = tab_index
            self.selected = 0
            self._rebuild_tab_content()

        if setting_key:
            target_item_idx = next(
                (i for i, item in enumerate(self._tab_items) if item.get('key') == setting_key),
                None,
            )
            if target_item_idx is not None:
                try:
                    self.selected = self._selectable_indices.index(target_item_idx)
                except ValueError:
                    self.selected = 0

        self._ensure_visible()

    def sync_from_settings_manager(self) -> None:
        """main.py'den çağrılır – runtime değişiklikleri sync et."""
        self._load_all_settings()
        self._control_config = self.settings_manager.get_controls()
        show_debug = bool(self.settings_manager.get('show_debug_settings', False))
        if show_debug != self._show_debug_settings:
            self._show_debug_settings = show_debug
            self._rebuild_tab_content()

    # ------------------------------------------------------------------
    # Değer okuma / yazma
    # ------------------------------------------------------------------

    def _get_value(self, key: str):
        """Ayar değerini döndür."""
        if key == 'ctrl_gp_rumble':
            return self._gamepad_rumble_slider_value()
        return getattr(self, key, self.settings_manager.get(key))

    def _set_value(self, key: str, value) -> None:
        """Ayar değerini güncelle ve kaydet."""
        if key == 'ctrl_gp_rumble':
            slider_value = self._gamepad_rumble_slider_value(value)
            gamepad_cfg = self._control_config.setdefault('gamepad', {})
            gamepad_cfg['rumble'] = self._gamepad_rumble_level_from_slider_value(slider_value)
            self._persist_controls()
            return
        if key == 'particle_effects':
            slider_value = self._particle_effects_level_to_slider_value(value)
            setattr(self, key, slider_value)
            self.settings_manager.set(key, self._particle_effects_level_from_slider_value(slider_value))
            return
        setattr(self, key, value)
        self.settings_manager.set(key, value)

    def _gamepad_rumble_slider_value(self, value=None) -> int:
        raw_value = self._control_config.get('gamepad', {}).get('rumble', 'high') if value is None else value
        helper = getattr(self.settings_manager, 'gamepad_rumble_slider_value', None)
        if callable(helper):
            try:
                return int(helper(raw_value))
            except Exception:
                pass
        if isinstance(raw_value, bool):
            return 3 if raw_value else 0
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            return max(0, min(3, int(round(raw_value))))
        mapping = {
            'off': 0,
            'false': 0,
            '0': 0,
            'yok': 0,
            'kapali': 0,
            'kapalı': 0,
            'low': 1,
            'az': 1,
            '1': 1,
            'medium': 2,
            'orta': 2,
            '2': 2,
            'high': 3,
            'true': 3,
            'on': 3,
            'acik': 3,
            'açık': 3,
            'cok': 3,
            'çok': 3,
            '3': 3,
        }
        return mapping.get(str(raw_value or '').strip().lower(), 3)

    def _gamepad_rumble_level_from_slider_value(self, slider_value: int) -> str:
        helper = getattr(self.settings_manager, 'gamepad_rumble_level_from_slider', None)
        if callable(helper):
            try:
                return str(helper(slider_value))
            except Exception:
                pass
        mapping = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}
        return mapping.get(max(0, min(3, int(round(slider_value)))), 'high')

    def _gamepad_rumble_label(self, slider_value: int | None = None) -> str:
        slider = self._gamepad_rumble_slider_value() if slider_value is None else self._gamepad_rumble_slider_value(slider_value)
        level = self._gamepad_rumble_level_from_slider_value(slider)
        labels = {
            'off': _t('gp_rumble_off', 'Yok'),
            'low': _t('gp_rumble_low', 'Az'),
            'medium': _t('gp_rumble_medium', 'Orta'),
            'high': _t('gp_rumble_high', 'Çok'),
        }
        return labels.get(level, _t('gp_rumble_high', 'Çok'))

    def _particle_effects_level_to_slider_value(self, value) -> int:
        helper = getattr(self.settings_manager, 'particle_effects_slider_value', None)
        if callable(helper):
            try:
                return int(helper(value))
            except Exception:
                pass
        if isinstance(value, bool):
            return 2 if value else 0
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, min(3, int(round(value))))
        mapping = {
            'off': 0,
            'kapali': 0,
            'kapalı': 0,
            'false': 0,
            '0': 0,
            'low': 1,
            'az': 1,
            '1': 1,
            'medium': 2,
            'orta': 2,
            'true': 2,
            'on': 2,
            'acik': 2,
            'açık': 2,
            '2': 2,
            'high': 3,
            'cok': 3,
            'çok': 3,
            '3': 3,
        }
        return mapping.get(str(value or '').strip().lower(), 2)

    def _particle_effects_level_from_slider_value(self, slider_value: int) -> str:
        helper = getattr(self.settings_manager, 'particle_effects_level_from_slider', None)
        if callable(helper):
            try:
                return str(helper(slider_value))
            except Exception:
                pass
        mapping = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}
        return mapping.get(max(0, min(3, int(round(slider_value)))), 'medium')

    def _particle_effects_label(self, slider_value: int | None = None) -> str:
        slider = self.particle_effects if slider_value is None else self._particle_effects_level_to_slider_value(slider_value)
        level = self._particle_effects_level_from_slider_value(slider)
        labels = {
            'off': _t('off', 'Kapalı'),
            'low': _t('particle_effects_low', 'Az'),
            'medium': _t('particle_effects_medium', 'Orta'),
            'high': _t('particle_effects_high', 'Çok'),
        }
        return labels.get(level, _t('particle_effects_medium', 'Orta'))

    def _get_display_value(self, item: dict) -> tuple[str, tuple[int, int, int]]:
        """Bir ayar öğesinin görüntülenecek değerini ve rengini döndür."""
        key = item.get('key', '')
        itype = item['type']
        lang = get_language()
        on_text = _t('on', 'Açık' if lang == 'tr' else 'On')
        off_text = _t('off', 'Kapalı' if lang == 'tr' else 'Off')

        if itype == 'toggle':
            val = self._get_value(key)
            if key == 'mute_all':
                is_on = bool(val)
                text = on_text if is_on else off_text
                color = (255, 100, 100) if is_on else (100, 255, 100)
            else:
                is_on = bool(val)
                text = on_text if is_on else off_text
                color = (100, 255, 100) if is_on else (255, 100, 100)
            return text, color

        elif itype == 'slider':
            val = self._get_value(key)
            if key == 'particle_effects':
                return self._particle_effects_label(int(val)), (140, 220, 255)
            if key == 'ctrl_gp_rumble':
                return self._gamepad_rumble_label(int(val)), (255, 210, 140)
            if item.get('percent'):
                text = f'{int(float(val) * 100)}%'
            else:
                text = f'{int(val)} {item.get("suffix", "")}'.strip()
            return text, (200, 220, 255)

        elif itype == 'selector':
            if key == 'fps_limit':
                limit = int(self._get_value('fps_limit') or 0)
                text = t('automatic') if limit <= 0 else str(limit)
                return text, (200, 220, 255)
            elif key == 'ui_scale_preset':
                return _ui_scale_preset_label(self._get_value('ui_scale_preset')), (100, 255, 200)
            elif key == 'language':
                lang_name = get_language_name(self.current_language)
                return str(lang_name), (100, 255, 200)
            return '', (200, 200, 200)

        elif itype == 'submenu':
            return '', (150, 170, 200)

        elif itype == 'music_selector':
            mode_key = item.get('mode_key')
            if mode_key == 'campaign':
                # Kampanya modunda 5 fazın toplam parça sayısını göster
                total = 0
                configured = 0
                try:
                    from menu import CAMPAIGN_PHASE_WORLDS
                    for mk, _wn, _s, _e in CAMPAIGN_PHASE_WORLDS:
                        pl = self.settings_manager.get_mode_music_playlist(mk)
                        if pl:
                            total += len(pl)
                            configured += 1
                except Exception:
                    pass
                if total > 0:
                    return f"{configured}/5 faz, {total} {_t('track_count_unit', 'parça')}", (150, 220, 255)
                return '▶ ' + _t('track_default_label', 'Varsayılan (Oyun İçi)'), (150, 220, 255)
            try:
                playlist = self.settings_manager.get_mode_music_playlist(mode_key)
                count = len(playlist) if playlist else 0
            except Exception:
                count = 0
            if count > 0:
                return f"{count} {_t('track_count_unit', 'parça')}", (150, 220, 255)
            return _t('track_default_label', 'Varsayılan (Oyun İçi)'), (150, 220, 255)

        elif itype == 'keybind':
            section = item.get('section')
            action_key = item.get('action_key')

            if self._waiting_for_key and self._pending_keybind_item == item:
                if self._is_gamepad_keybind_section(section):
                    return _t('gp_press_button', 'Butona basın'), (255, 210, 120)
                if section == 'single_player':
                    slot = self._pending_keybind_slot if self._pending_keybind_slot in ('primary', 'secondary') else 'primary'
                    slot_text = _t('primary', 'Birincil') if slot == 'primary' else _t('secondary', 'İkincil')
                    return f"{t('press_key')} ({slot_text})", (255, 210, 120)
                return t('press_key'), (255, 210, 120)

            if section == 'single_player':
                row = self._control_config.get('single_player', {}).get(action_key, {})
                if isinstance(row, dict):
                    primary = str(row.get('primary', '') or '').upper() or '—'
                    secondary = str(row.get('secondary', '') or '').upper() or '—'
                    return f'{primary} / {secondary}', (180, 220, 255)
                return (str(row or '').upper() or '—'), (180, 220, 255)

            if section == 'pvp.player1':
                value = self._control_config.get('pvp', {}).get('player1', {}).get(action_key, '')
                return (str(value).upper() or '—'), (180, 220, 255)

            if section == 'pvp.player2':
                value = self._control_config.get('pvp', {}).get('player2', {}).get(action_key, '')
                return (str(value).upper() or '—'), (180, 220, 255)

            if self._is_gamepad_keybind_section(section):
                primary, secondary = self._get_gamepad_binding_slots(action_key)
                gp_type = self._current_gamepad_prompt_type()
                ptxt = self._format_gamepad_button_label(primary, gp_type=gp_type)
                stxt = self._format_gamepad_button_label(secondary, gp_type=gp_type)
                return f'{ptxt} / {stxt}', (255, 210, 140)

            return '—', (180, 220, 255)

        return '', (200, 200, 200)

    def _cycle_mode_music(self, mode_key: str, step: int) -> None:
        if not self._track_options:
            return
        current = self._mode_music_overrides.get(mode_key)
        current_idx = 0
        for idx, option in enumerate(self._track_options):
            if option.get('value') == current:
                current_idx = idx
                break
        new_idx = (current_idx + step) % len(self._track_options)
        chosen = self._track_options[new_idx].get('value')
        self.settings_manager.set_mode_music_override(mode_key, chosen)
        self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()

    def _start_keybind_capture(self, item: dict, slot: str = 'primary', opened_by_gamepad_click: bool = False) -> None:
        self._waiting_for_key = True
        self._pending_keybind_item = item
        self._pending_keybind_slot = slot
        self._capture_started_by_gamepad_click = bool(opened_by_gamepad_click)

    def _normalize_gamepad_prompt_type(self, gp_type) -> str | None:
        if gp_type is None:
            return None
        normalized = str(gp_type).strip().lower()
        if normalized in _KNOWN_GAMEPAD_PROMPT_TYPES:
            return normalized
        return None

    def _remember_gamepad_prompt_type(self, gp_type) -> None:
        normalized = self._normalize_gamepad_prompt_type(gp_type)
        if not normalized or normalized == self._last_known_gamepad_prompt_type:
            return
        self._last_known_gamepad_prompt_type = normalized
        try:
            self.settings_manager.set('last_gamepad_prompt_type', normalized)
        except Exception:
            pass

    def _is_gamepad_keybind_section(self, section: str | None) -> bool:
        return section in ('gamepad', 'gamepad.ingame', 'gamepad.outgame')

    def _should_swallow_post_capture_gamepad_click(self, button_index: int) -> bool:
        try:
            gpm = get_gamepad_manager()
        except Exception:
            return False

        if getattr(gpm, 'get_context', lambda: None)() != getattr(gpm, 'CONTEXT_MENU', 'menu'):
            return False
        if not bool(getattr(gpm, '_menu_pointer_active', False)):
            return False

        try:
            btn_index = int(button_index)
        except Exception:
            return False

        if btn_index == 8:
            return True

        get_indices = getattr(gpm, 'get_action_button_indices', None)
        if not callable(get_indices):
            return False

        try:
            return btn_index in set(get_indices('menu_confirm'))
        except Exception:
            return False

    def _persist_controls(self) -> None:
        self.settings_manager.set('controls', self._control_config)
        self._control_config = self.settings_manager.get_controls()
        try:
            reload_gamepad_settings()
        except Exception:
            pass

    def _format_gamepad_button_label(self, value, gp_type: str | None = None) -> str:
        unbound = _t('gp_unbound', 'Atanmamış')
        if value is None or isinstance(value, bool):
            return unbound
        try:
            btn_index = int(value)
        except Exception:
            return unbound
        if btn_index < 0:
            return unbound

        try:
            gpm = get_gamepad_manager()
            resolved_type = self._normalize_gamepad_prompt_type(gp_type) or self._last_known_gamepad_prompt_type
            return str(gpm.get_button_index_label(btn_index, resolved_type))
        except Exception:
            return f'Btn{btn_index}'

    def _current_gamepad_prompt_type(self) -> str | None:
        try:
            gpm = get_gamepad_manager()
            gp = gpm.get_active_gamepad()
            if gp is None:
                return self._last_known_gamepad_prompt_type
            gp_type = self._normalize_gamepad_prompt_type(getattr(gp, 'gamepad_type', None))
            if gp_type:
                self._remember_gamepad_prompt_type(gp_type)
                return gp_type
        except Exception:
            pass
        return self._last_known_gamepad_prompt_type

    def _get_gamepad_slot_display(self, value, gp_type: str | None) -> dict:
        fallback_text = self._format_gamepad_button_label(value, gp_type=gp_type)
        if value is None or isinstance(value, bool):
            return {'mode': 'text', 'text': fallback_text}

        try:
            btn_index = int(value)
        except Exception:
            return {'mode': 'text', 'text': fallback_text}

        glyph_text = get_gamepad_prompt_glyph(btn_index, gp_type)
        if glyph_text:
            return {'mode': 'glyph', 'glyph': glyph_text, 'text': fallback_text}
        return {'mode': 'text', 'text': fallback_text}

    def _draw_gamepad_binding_slot(self, slot_rect: pygame.Rect, display: dict, active: bool) -> None:
        s = self._s
        bg = (32, 48, 80, 230) if active else (20, 30, 54, 200)
        border = (90, 180, 255) if active else (55, 78, 112)
        pygame.draw.rect(self.screen, bg, slot_rect, border_radius=s(8, minimum=6))
        pygame.draw.rect(self.screen, border, slot_rect, 1, border_radius=s(8, minimum=6))

        txt_color = (235, 245, 255) if active else (180, 205, 235)
        if display.get('mode') == 'glyph':
            glyph_text = str(display.get('glyph', '') or '')
            glyph_surf = fit_promptfont_glyph_surface(
                glyph_text,
                slot_rect.width - s(16, minimum=10),
                slot_rect.height - s(8, minimum=6),
                txt_color,
                preferred_size=max(s(24, minimum=16), slot_rect.height - s(6, minimum=4)),
                minimum_size=s(12, minimum=9),
            )
            if glyph_surf is not None:
                self.screen.blit(glyph_surf, glyph_surf.get_rect(center=slot_rect.center))
                return

        text = str(display.get('text', '—') or '—')
        txt_font = self._fit_font(text, 20, slot_rect.width - s(12, minimum=8), bold=active, minimum=11)
        txt_surf = txt_font.render(text, True, txt_color)
        self.screen.blit(txt_surf, txt_surf.get_rect(center=slot_rect.center))

    def _draw_text_binding_slot(self, slot_rect: pygame.Rect, text: str, active: bool) -> None:
        s = self._s
        bg = (32, 48, 80, 230) if active else (20, 30, 54, 200)
        border = (90, 180, 255) if active else (55, 78, 112)
        pygame.draw.rect(self.screen, bg, slot_rect, border_radius=s(8, minimum=6))
        pygame.draw.rect(self.screen, border, slot_rect, 1, border_radius=s(8, minimum=6))
        txt_color = (235, 245, 255) if active else (180, 205, 235)
        txt_font = self._fit_font(text, 20, slot_rect.width - s(12, minimum=8), bold=active, minimum=11)
        txt_surf = txt_font.render(text, True, txt_color)
        self.screen.blit(txt_surf, txt_surf.get_rect(center=slot_rect.center))

    def _get_gamepad_binding_slots(self, action_key: str) -> tuple[int, int]:
        gamepad_cfg = self._control_config.get('gamepad', {})
        raw = gamepad_cfg.get(action_key, -1)
        primary = -1
        secondary = -1
        if isinstance(raw, dict):
            pval = raw.get('primary', -1)
            sval = raw.get('secondary', -1)
            if isinstance(pval, int):
                primary = pval
            if isinstance(sval, int):
                secondary = sval
        elif isinstance(raw, int):
            primary = raw
        return primary, secondary

    def _apply_captured_key(self, key_code: int) -> None:
        if not self._pending_keybind_item:
            return
        section = self._pending_keybind_item.get('section')
        action_key = self._pending_keybind_item.get('action_key')
        key_name = pygame.key.name(key_code)

        if section == 'single_player':
            single = self._control_config.setdefault('single_player', {})
            row = single.get(action_key)
            if not isinstance(row, dict):
                row = {'primary': str(row or ''), 'secondary': ''}
                single[action_key] = row
            slot = self._pending_keybind_slot if self._pending_keybind_slot in ('primary', 'secondary') else 'primary'
            row[slot] = key_name
        elif section == 'pvp.player1':
            pvp = self._control_config.setdefault('pvp', {})
            player = pvp.setdefault('player1', {})
            player[action_key] = key_name
        elif section == 'pvp.player2':
            pvp = self._control_config.setdefault('pvp', {})
            player = pvp.setdefault('player2', {})
            player[action_key] = key_name

        self._persist_controls()

    def _apply_captured_gamepad_button(self, button_index: int) -> None:
        if not self._pending_keybind_item:
            return
        if not self._is_gamepad_keybind_section(self._pending_keybind_item.get('section')):
            return

        action_key = self._pending_keybind_item.get('action_key')
        if not action_key:
            return

        gamepad_cfg = self._control_config.setdefault('gamepad', {})
        raw = gamepad_cfg.get(action_key)
        if not isinstance(raw, dict):
            raw = {
                'primary': int(raw) if isinstance(raw, int) else -1,
                'secondary': -1,
            }
            gamepad_cfg[action_key] = raw

        slot = self._pending_keybind_slot if self._pending_keybind_slot in ('primary', 'secondary') else 'primary'
        raw[slot] = int(button_index)
        self._persist_controls()

    def _reset_selected_keybind_to_default(self) -> None:
        if not self._selectable_indices or self.selected >= len(self._selectable_indices):
            return
        item_idx = self._selectable_indices[self.selected]
        item = self._tab_items[item_idx]
        if item.get('type') != 'keybind':
            return

        defaults = self.settings_manager.get_default_controls()
        section = item.get('section')
        action_key = item.get('action_key')

        if section == 'single_player':
            value = defaults.get('single_player', {}).get(action_key)
            current = self._control_config.setdefault('single_player', {}).get(action_key)
            if isinstance(value, dict):
                if not isinstance(current, dict):
                    current = {'primary': str(current or ''), 'secondary': ''}
                    self._control_config.setdefault('single_player', {})[action_key] = current
                slot = self._single_player_bind_slot if self._single_player_bind_slot in ('primary', 'secondary') else 'primary'
                current[slot] = value.get(slot, '')
            else:
                self._control_config.setdefault('single_player', {})[action_key] = value
        elif section == 'pvp.player1':
            value = defaults.get('pvp', {}).get('player1', {}).get(action_key)
            self._control_config.setdefault('pvp', {}).setdefault('player1', {})[action_key] = value
        elif section == 'pvp.player2':
            value = defaults.get('pvp', {}).get('player2', {}).get(action_key)
            self._control_config.setdefault('pvp', {}).setdefault('player2', {})[action_key] = value
        elif self._is_gamepad_keybind_section(section):
            value = defaults.get('gamepad', {}).get(action_key, -1)
            if isinstance(value, dict):
                current = self._control_config.setdefault('gamepad', {}).get(action_key)
                if not isinstance(current, dict):
                    current = {'primary': -1, 'secondary': -1}
                    self._control_config.setdefault('gamepad', {})[action_key] = current
                slot = self._gamepad_bind_slot if self._gamepad_bind_slot in ('primary', 'secondary') else 'primary'
                current[slot] = int(value.get(slot, -1))
            else:
                self._control_config.setdefault('gamepad', {})[action_key] = value

        self._persist_controls()

    def _open_music_picker(self, mode_key: str) -> None:
        self._music_picker_open = True
        self._music_picker_mode_key = mode_key
        self._music_picker_scroll = 0
        current = self._mode_music_overrides.get(mode_key)
        idx = 0
        for i, option in enumerate(self._track_options):
            if option.get('value') == current:
                idx = i
                break
        self._music_picker_selected = idx

    def _close_music_picker(self) -> None:
        self._music_picker_open = False
        self._music_picker_mode_key = None
        self._music_picker_item_rects = []

    def open_mode_playlist_editor(self, mode_key: str) -> None:
        self._close_music_picker()
        self._vsync_prompt_active = False
        self._vsync_prompt_buttons = []
        self._playlist_edit_active = True
        self._playlist_edit_mode_key = mode_key
        playlist = self.settings_manager.get_mode_music_playlist(mode_key) if self.settings_manager else []
        self._playlist_edit_items = list(playlist)
        self._playlist_edit_selected = 0
        self._playlist_edit_scroll = 0
        self._playlist_edit_picker_open = False
        self._playlist_edit_picker_selected = 0
        self._playlist_edit_picker_scroll = 0
        self._playlist_edit_item_rects = []
        self._playlist_edit_picker_rects = []

    def _close_mode_playlist_editor(self) -> None:
        self._playlist_edit_active = False
        self._playlist_edit_mode_key = None
        self._playlist_edit_items = []
        self._playlist_edit_picker_open = False
        self._playlist_edit_picker_selected = 0
        self._playlist_edit_picker_scroll = 0
        self._playlist_edit_item_rects = []
        self._playlist_edit_picker_rects = []

    # ------------------------------------------------------------------
    # Kampanya faz seçici overlay
    # ------------------------------------------------------------------

    def _open_campaign_phase_select(self) -> None:
        """Kampanya müzik faz seçici overlay panelini aç."""
        self._campaign_phase_select_active = True
        self._campaign_phase_selected = 0
        self._campaign_phase_item_rects = []

    def _close_campaign_phase_select(self) -> None:
        self._campaign_phase_select_active = False
        self._campaign_phase_selected = 0
        self._campaign_phase_item_rects = []

    def _handle_campaign_phase_select_input(self, event) -> str | None:
        """Kampanya faz seçici overlay girdilerini işle."""
        phases = get_campaign_phase_entries()
        if not phases:
            self._close_campaign_phase_select()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_campaign_phase_select()
                return None
            if event.key == pygame.K_UP:
                self._campaign_phase_selected = (self._campaign_phase_selected - 1) % len(phases)
                return None
            if event.key == pygame.K_DOWN:
                self._campaign_phase_selected = (self._campaign_phase_selected + 1) % len(phases)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                mode_key = phases[self._campaign_phase_selected][0]
                self._close_campaign_phase_select()
                self.open_mode_playlist_editor(mode_key)
                return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self._campaign_phase_item_rects:
                if rect.collidepoint(pos):
                    self._campaign_phase_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self._campaign_phase_item_rects:
                if rect.collidepoint(pos):
                    self._campaign_phase_selected = idx
                    mode_key = phases[idx][0]
                    self._close_campaign_phase_select()
                    self.open_mode_playlist_editor(mode_key)
                    return None
            # Panelin dışına tıklandıysa kapat
            self._close_campaign_phase_select()
            return None

        return None

    def _save_mode_playlist(self) -> str | None:
        if not self.settings_manager or not self._playlist_edit_mode_key:
            return None
        self.settings_manager.set_mode_music_playlist(self._playlist_edit_mode_key, list(self._playlist_edit_items))
        return 'mode_playlist_changed'

    def _playlist_selectable_track_values(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for option in self._track_options:
            value = option.get('value') if isinstance(option, dict) else None
            if not isinstance(value, str) or not value:
                continue
            if value in seen:
                continue
            values.append(value)
            seen.add(value)
        return values

    def _playlist_bulk_action_rects(self, metrics: dict[str, int | pygame.Rect]) -> dict[str, pygame.Rect]:
        list_rect = metrics.get('list_rect')
        if not isinstance(list_rect, pygame.Rect):
            return {}

        try:
            action_h = int(metrics.get('action_h', 0))
            action_gap = int(metrics.get('action_gap', 0))
            action_y = int(metrics.get('action_y', 0))
        except Exception:
            return {}

        if action_h <= 0 or list_rect.width <= 0:
            return {}

        width = max(1, (list_rect.width - (action_gap * 2)) // 3)
        return {
            'clear': pygame.Rect(list_rect.x, action_y, width, action_h),
            'reset_default': pygame.Rect(list_rect.x + width + action_gap, action_y, width, action_h),
            'select_all': pygame.Rect(list_rect.x + (width + action_gap) * 2, action_y, width, action_h),
        }

    def _apply_playlist_bulk_action(self, action_key: str) -> str | None:
        if action_key in ('clear', 'reset_default'):
            if not self._playlist_edit_items:
                return None
            self._playlist_edit_items = []
            self._playlist_edit_selected = 0
            self._playlist_edit_scroll = 0
            return self._save_mode_playlist()

        if action_key == 'select_all':
            all_values = self._playlist_selectable_track_values()
            if not all_values:
                return None
            if self._playlist_edit_items == all_values:
                return None
            self._playlist_edit_items = list(all_values)
            self._playlist_edit_selected = len(self._playlist_edit_items)
            self._playlist_edit_scroll = 0
            self._playlist_ensure_visible()
            return self._save_mode_playlist()

        return None

    def _track_label_for_value(self, value) -> str:
        for option in self._track_options:
            if option.get('value') == value:
                return str(option.get('label', ''))
        if value and isinstance(value, str) and value.startswith('file:'):
            return t('track_file_prefix', path=value[5:])
        if value:
            return str(value)
        return t('track_default_label')

    def _playlist_list_max_scroll(self, total_items: int, item_h: int, gap: int, visible_h: int) -> int:
        total_h = total_items * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _playlist_ensure_visible(self, visible_h: int | None = None, item_h: int | None = None, gap: int | None = None) -> None:
        metrics = self._playlist_overlay_metrics()
        list_rect = metrics['list_rect']
        row_height = int(item_h if item_h is not None else metrics['item_h'])
        row_gap = int(gap if gap is not None else metrics['gap'])
        visible_height = int(visible_h if visible_h is not None else list_rect.height)
        y = self._playlist_edit_selected * (row_height + row_gap)
        if y < self._playlist_edit_scroll:
            self._playlist_edit_scroll = y
        elif y > self._playlist_edit_scroll + visible_height - row_height:
            self._playlist_edit_scroll = y - (visible_height - row_height)
        total_items = len(self._playlist_edit_items) + 1
        max_scroll = self._playlist_list_max_scroll(total_items, row_height, row_gap, visible_height)
        self._playlist_edit_scroll = max(0, min(self._playlist_edit_scroll, max_scroll))

    def _playlist_picker_ensure_visible(self, visible_h: int | None = None, item_h: int | None = None, gap: int | None = None) -> None:
        metrics = self._playlist_overlay_metrics()
        picker_list_rect = metrics['picker_list_rect']
        row_height = int(item_h if item_h is not None else metrics['picker_item_h'])
        row_gap = int(gap if gap is not None else metrics['picker_gap'])
        visible_height = int(visible_h if visible_h is not None else picker_list_rect.height)
        y = self._playlist_edit_picker_selected * (row_height + row_gap)
        if y < self._playlist_edit_picker_scroll:
            self._playlist_edit_picker_scroll = y
        elif y > self._playlist_edit_picker_scroll + visible_height - row_height:
            self._playlist_edit_picker_scroll = y - (visible_height - row_height)
        self._playlist_edit_picker_scroll = max(
            0,
            min(self._playlist_edit_picker_scroll, self._picker_max_scroll(visible_height, row_height, row_gap)),
        )

    def _open_mode_playlist_picker(self) -> None:
        self._playlist_edit_picker_open = True
        self._playlist_edit_picker_scroll = 0
        self._playlist_edit_picker_selected = 0

    def _close_mode_playlist_picker(self) -> None:
        self._playlist_edit_picker_open = False
        self._playlist_edit_picker_rects = []

    def _handle_mode_playlist_edit_input(self, event) -> str | None:
        if self._playlist_edit_picker_open:
            metrics = self._playlist_overlay_metrics()
            picker_list_rect = metrics['picker_list_rect']
            picker_item_h = int(metrics['picker_item_h'])
            picker_gap = int(metrics['picker_gap'])
            if not self._track_options:
                self._close_mode_playlist_picker()
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._close_mode_playlist_picker()
                    return None
                if event.key == pygame.K_UP:
                    self._playlist_edit_picker_selected = (self._playlist_edit_picker_selected - 1) % len(self._track_options)
                    self._playlist_picker_ensure_visible(picker_list_rect.height, picker_item_h, picker_gap)
                    return None
                if event.key == pygame.K_DOWN:
                    self._playlist_edit_picker_selected = (self._playlist_edit_picker_selected + 1) % len(self._track_options)
                    self._playlist_picker_ensure_visible(picker_list_rect.height, picker_item_h, picker_gap)
                    return None
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    chosen = self._track_options[self._playlist_edit_picker_selected].get('value')
                    self._playlist_edit_items.append(chosen)
                    self._playlist_edit_selected = len(self._playlist_edit_items)
                    self._close_mode_playlist_picker()
                    return self._save_mode_playlist()

            elif event.type == pygame.MOUSEWHEEL:
                max_scroll = self._picker_max_scroll(picker_list_rect.height, picker_item_h, picker_gap)
                self._playlist_edit_picker_scroll -= event.y * int(metrics['picker_scroll_step'])
                self._playlist_edit_picker_scroll = max(0, min(self._playlist_edit_picker_scroll, max_scroll))
                return None

            elif event.type == pygame.MOUSEMOTION:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for rect, idx in self._playlist_edit_picker_rects:
                    if rect.collidepoint(pos):
                        self._playlist_edit_picker_selected = idx
                        break
                return None

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for rect, idx in self._playlist_edit_picker_rects:
                    if rect.collidepoint(pos):
                        self._playlist_edit_picker_selected = idx
                        chosen = self._track_options[self._playlist_edit_picker_selected].get('value')
                        self._playlist_edit_items.append(chosen)
                        self._playlist_edit_selected = len(self._playlist_edit_items)
                        self._close_mode_playlist_picker()
                        return self._save_mode_playlist()
                self._close_mode_playlist_picker()
                return None

            return None

        total_items = len(self._playlist_edit_items) + 1
        metrics = self._playlist_overlay_metrics()
        list_rect = metrics['list_rect']
        item_h = int(metrics['item_h'])
        gap = int(metrics['gap'])
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_mode_playlist_editor()
                return None
            if event.key == pygame.K_UP:
                self._playlist_edit_selected = (self._playlist_edit_selected - 1) % max(total_items, 1)
                self._playlist_ensure_visible(list_rect.height, item_h, gap)
                return None
            if event.key == pygame.K_DOWN:
                self._playlist_edit_selected = (self._playlist_edit_selected + 1) % max(total_items, 1)
                self._playlist_ensure_visible(list_rect.height, item_h, gap)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._playlist_edit_selected == 0:
                    self._open_mode_playlist_picker()
                return None
            if event.key == pygame.K_a:
                return self._apply_playlist_bulk_action('select_all')
            if event.key == pygame.K_c:
                return self._apply_playlist_bulk_action('clear')
            if event.key == pygame.K_r:
                return self._apply_playlist_bulk_action('reset_default')
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self._playlist_edit_selected > 0:
                    idx = self._playlist_edit_selected - 1
                    if 0 <= idx < len(self._playlist_edit_items):
                        del self._playlist_edit_items[idx]
                        self._playlist_edit_selected = max(0, min(self._playlist_edit_selected, len(self._playlist_edit_items)))
                        return self._save_mode_playlist()
                return None
            if event.key == pygame.K_LEFT:
                if self._playlist_edit_selected > 1:
                    idx = self._playlist_edit_selected - 1
                    self._playlist_edit_items[idx - 1], self._playlist_edit_items[idx] = self._playlist_edit_items[idx], self._playlist_edit_items[idx - 1]
                    self._playlist_edit_selected -= 1
                    return self._save_mode_playlist()
                return None
            if event.key == pygame.K_RIGHT:
                idx = self._playlist_edit_selected - 1
                if 0 <= idx < len(self._playlist_edit_items) - 1:
                    self._playlist_edit_items[idx + 1], self._playlist_edit_items[idx] = self._playlist_edit_items[idx], self._playlist_edit_items[idx + 1]
                    self._playlist_edit_selected += 1
                    return self._save_mode_playlist()
                return None

        elif event.type == pygame.MOUSEWHEEL:
            max_scroll = self._playlist_list_max_scroll(total_items, item_h, gap, list_rect.height)
            self._playlist_edit_scroll -= event.y * int(metrics['scroll_step'])
            self._playlist_edit_scroll = max(0, min(self._playlist_edit_scroll, max_scroll))
            return None

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self._playlist_edit_item_rects:
                if rect.collidepoint(pos):
                    self._playlist_edit_selected = idx
                    break
            return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for action_key, action_rect in self._playlist_bulk_action_rects(metrics).items():
                if action_rect.collidepoint(pos):
                    return self._apply_playlist_bulk_action(action_key)
            for rect, idx in self._playlist_edit_item_rects:
                if rect.collidepoint(pos):
                    self._playlist_edit_selected = idx
                    if idx == 0:
                        self._open_mode_playlist_picker()
                    return None

        return None

    def _picker_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self._track_options) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _picker_ensure_visible(self, visible_h: int | None = None, item_h: int | None = None, gap: int | None = None) -> None:
        metrics = self._music_picker_metrics()
        list_rect = metrics['list_rect']
        row_height = int(item_h if item_h is not None else metrics['item_h'])
        row_gap = int(gap if gap is not None else metrics['gap'])
        visible_height = int(visible_h if visible_h is not None else list_rect.height)
        y = self._music_picker_selected * (row_height + row_gap)
        if y < self._music_picker_scroll:
            self._music_picker_scroll = y
        elif y > self._music_picker_scroll + visible_height - row_height:
            self._music_picker_scroll = y - (visible_height - row_height)
        self._music_picker_scroll = max(0, min(self._music_picker_scroll, self._picker_max_scroll(visible_height, row_height, row_gap)))

    def _handle_music_picker_input(self, event) -> None:
        metrics = self._music_picker_metrics()
        list_rect = metrics['list_rect']
        item_h = int(metrics['item_h'])
        gap = int(metrics['gap'])
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_music_picker()
                return
            if event.key == pygame.K_UP:
                self._music_picker_selected = (self._music_picker_selected - 1) % len(self._track_options)
                self._picker_ensure_visible(list_rect.height, item_h, gap)
                return
            if event.key == pygame.K_DOWN:
                self._music_picker_selected = (self._music_picker_selected + 1) % len(self._track_options)
                self._picker_ensure_visible(list_rect.height, item_h, gap)
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._music_picker_mode_key is not None:
                    chosen = self._track_options[self._music_picker_selected].get('value')
                    self.settings_manager.set_mode_music_override(self._music_picker_mode_key, chosen)
                    self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()
                self._close_music_picker()
                return

        elif event.type == pygame.MOUSEWHEEL:
            max_scroll = self._picker_max_scroll(list_rect.height, item_h, gap)
            self._music_picker_scroll -= event.y * int(metrics['scroll_step'])
            self._music_picker_scroll = max(0, min(self._music_picker_scroll, max_scroll))
            return

        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self._music_picker_item_rects:
                if rect.collidepoint(pos):
                    self._music_picker_selected = idx
                    break
            return

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for rect, idx in self._music_picker_item_rects:
                if rect.collidepoint(pos):
                    self._music_picker_selected = idx
                    if self._music_picker_mode_key is not None:
                        chosen = self._track_options[self._music_picker_selected].get('value')
                        self.settings_manager.set_mode_music_override(self._music_picker_mode_key, chosen)
                        self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()
                    self._close_music_picker()
                    return
            self._close_music_picker()
            return

    # ------------------------------------------------------------------
    # Ayar değiştirme
    # ------------------------------------------------------------------

    def _toggle_value(self, key: str) -> str | None:
        """Toggle type ayarı tersine çevir. İlgili action string döndür."""
        current = bool(self._get_value(key))
        new_val = not current
        self._set_value(key, new_val)

        action_map = {
            'music_enabled': 'toggle_music',
            'sound_enabled': 'toggle_sound',
            'mute_all': 'toggle_mute',
            'show_ghost': None,
            'background_enabled': 'toggle_background_enabled',
            'particle_effects': None,
            'debug_mode': 'toggle_debug',
            'card_mode_debug': 'toggle_card_mode_debug',
            'vsync': 'vsync_changed',
        }

        # Uyumluluk alanlarını güncelle
        if key == 'music_enabled':
            self.music_enabled = new_val
        elif key == 'sound_enabled':
            self.sound_enabled = new_val
        elif key == 'mute_all':
            self.mute_all = new_val
        elif key == 'background_enabled':
            self.background_enabled = new_val
        elif key == 'debug_mode':
            self.debug_mode = new_val
        elif key == 'card_mode_debug':
            self.card_mode_debug = new_val
        elif key == 'vsync':
            self.vsync = new_val
            self._vsync_prompt_active = True
            self._vsync_prompt_choice = 0

        return action_map.get(key)

    def _adjust_slider(self, key: str, delta: int, item: dict) -> str | None:
        """Slider değerini delta yönünde ayarla."""
        current = float(self._get_value(key))
        step = item.get('step', 1)
        min_val = item.get('min', 0)
        max_val = item.get('max', 1)

        new_val = current + step * delta
        if item.get('percent'):
            new_val = round(max(min_val, min(max_val, new_val)), 2)
        else:
            new_val = int(max(min_val, min(max_val, new_val)))

        self._set_value(key, new_val)

        # Uyumluluk alanları ve action
        if key == 'music_volume':
            self.music_volume = new_val
            return 'change_music_volume'
        elif key == 'menu_music_volume':
            self.menu_music_volume = new_val
            return 'change_menu_music_volume'
        elif key == 'sfx_volume':
            self.sfx_volume = new_val
            return 'change_sfx_volume'
        elif key == 'bg_transparency':
            self.bg_transparency = new_val
            return 'change_bg_transparency'
        elif key == 'effects_opacity':
            self.effects_opacity = new_val
            return 'change_effects_opacity'
        elif key == 'menu_transparency':
            self.menu_transparency = new_val
            return 'change_menu_transparency'
        return None

    def _set_slider_from_x(self, item: dict, x: int, bar_rect: pygame.Rect) -> str | None:
        """Mouse x pozisyonuna göre slider değerini ayarla."""
        key = item.get('key', '')
        min_val = item.get('min', 0)
        max_val = item.get('max', 1)
        step = item.get('step', 1)

        ratio = (x - bar_rect.x) / max(1, bar_rect.width)
        ratio = max(0.0, min(1.0, ratio))
        raw = min_val + ratio * (max_val - min_val)

        # Step snap
        if step > 0:
            snapped = round(raw / step) * step
        else:
            snapped = raw

        if item.get('percent'):
            new_val = round(max(min_val, min(max_val, snapped)), 2)
        else:
            new_val = int(max(min_val, min(max_val, round(snapped))))

        self._set_value(key, new_val)

        if key == 'music_volume':
            self.music_volume = new_val
            return 'change_music_volume'
        elif key == 'menu_music_volume':
            self.menu_music_volume = new_val
            return 'change_menu_music_volume'
        elif key == 'sfx_volume':
            self.sfx_volume = new_val
            return 'change_sfx_volume'
        elif key == 'bg_transparency':
            self.bg_transparency = new_val
            return 'change_bg_transparency'
        elif key == 'effects_opacity':
            self.effects_opacity = new_val
            return 'change_effects_opacity'
        elif key == 'menu_transparency':
            self.menu_transparency = new_val
            return 'change_menu_transparency'
        return None

    def _cycle_selector(self, key: str, delta: int) -> str | None:
        """Selector type ayarı döngüsel değiştir."""
        if key == 'fullscreen':
            prev = bool(getattr(self, 'fullscreen', True))
            target = not prev
            self._display_mode_confirm_prev_fullscreen = prev
            self._display_mode_confirm_target_fullscreen = target
            self._display_mode_confirm_active = True
            self._display_mode_confirm_yes_rect = None
            self._display_mode_confirm_no_rect = None
            return None

        if key == 'fps_limit':
            current = int(self.fps_limit or 0)
            if current not in self.FPS_LIMITS:
                current = 0
            idx = self.FPS_LIMITS.index(current)
            idx = (idx + delta) % len(self.FPS_LIMITS)
            self.fps_limit = self.FPS_LIMITS[idx]
            self._set_value('fps_limit', self.fps_limit)
        elif key == 'ui_scale_preset':
            current = normalize_ui_scale_preset(getattr(self, 'ui_scale_preset', 'normal'))
            idx = UI_SCALE_PRESETS.index(current)
            idx = (idx + delta) % len(UI_SCALE_PRESETS)
            self.ui_scale_preset = UI_SCALE_PRESETS[idx]
            self._set_value('ui_scale_preset', self.ui_scale_preset)
        elif key == 'language':
            lang_idx = (
                SUPPORTED_LANGUAGES.index(self.current_language)
                if self.current_language in SUPPORTED_LANGUAGES
                else 0
            )
            lang_idx = (lang_idx + delta) % len(SUPPORTED_LANGUAGES)
            self.current_language = SUPPORTED_LANGUAGES[lang_idx]
            set_language(self.current_language)
            apply_language_ui_profile(self.current_language)
            self._font_scale_signature = None
            self._refresh_fonts()
            self._set_value('language', self.current_language)
            self._rebuild_tab_content()
            return 'language_changed'
        return None

    # ------------------------------------------------------------------
    # Panel geometrisi
    # ------------------------------------------------------------------

    def _panel_rect(self) -> pygame.Rect:
        return self._layout_metrics()['panel']

    def _tab_bar_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return self._layout_metrics()['tab_bar']

    def _content_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return self._layout_metrics()['content']

    # ------------------------------------------------------------------
    # Kaydırma sınırları
    # ------------------------------------------------------------------

    def _max_scroll(self, content_rect: pygame.Rect) -> int:
        metrics = self._layout_metrics()
        total = self._content_total_height(int(metrics['row_height']), int(metrics['section_height']))
        return max(0, total - content_rect.height)

    # ------------------------------------------------------------------
    # Input işleme
    # ------------------------------------------------------------------

    def handle_input(self, event) -> str | None:
        """Girdileri işle. Uyumlu action string döndür."""
        if self._swallow_next_keydown and event.type == pygame.KEYDOWN:
            self._swallow_next_keydown = False
            return None
        if (
            self._swallow_next_gamepad_click
            and self._swallow_next_gamepad_click_deadline_ms > 0
            and pygame.time.get_ticks() > self._swallow_next_gamepad_click_deadline_ms
        ):
            self._swallow_next_gamepad_click = False
            self._swallow_next_gamepad_click_deadline_ms = 0
        if (
            self._swallow_next_gamepad_click
            and event.type == pygame.MOUSEBUTTONDOWN
            and getattr(event, 'from_gamepad', False)
            and getattr(event, 'button', None) == 1
        ):
            self._swallow_next_gamepad_click = False
            self._swallow_next_gamepad_click_deadline_ms = 0
            return None

        if self._campaign_phase_select_active:
            return self._handle_campaign_phase_select_input(event)

        if self._playlist_edit_active:
            return self._handle_mode_playlist_edit_input(event)

        if self._music_picker_open:
            self._handle_music_picker_input(event)
            return None

        if self._waiting_for_key:
            pending_section = self._pending_keybind_item.get('section') if self._pending_keybind_item else None

            if self._is_gamepad_keybind_section(pending_section):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    self._capture_started_by_gamepad_click = False
                    return None
                button_down_types = (getattr(pygame, 'CONTROLLERBUTTONDOWN', None), getattr(pygame, 'JOYBUTTONDOWN', None))
                button_index = normalize_gamepad_event_button(event)
                if button_index is not None and event.type in button_down_types:
                    should_swallow_click = self._should_swallow_post_capture_gamepad_click(button_index)
                    if self._capture_started_by_gamepad_click and should_swallow_click:
                        should_swallow_click = False
                    self._swallow_next_gamepad_click = bool(should_swallow_click)
                    self._swallow_next_gamepad_click_deadline_ms = (
                        pygame.time.get_ticks() + 180 if should_swallow_click else 0
                    )
                    self._apply_captured_gamepad_button(button_index)
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    self._capture_started_by_gamepad_click = False
                    self._swallow_next_keydown = True
                    return None
                trigger_index = normalize_gamepad_trigger_event(event)
                if trigger_index is not None:
                    self._swallow_next_gamepad_click = False
                    self._swallow_next_gamepad_click_deadline_ms = 0
                    self._apply_captured_gamepad_button(trigger_index)
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    self._capture_started_by_gamepad_click = False
                    self._swallow_next_keydown = True
                    return None
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    self._capture_started_by_gamepad_click = False
                    return None
                self._apply_captured_key(event.key)
                self._waiting_for_key = False
                self._pending_keybind_item = None
                self._pending_keybind_slot = 'primary'
                self._capture_started_by_gamepad_click = False
            return None

        if self._display_mode_confirm_active:
            return self._handle_display_mode_confirm(event)

        # VSync restart prompt
        if self._vsync_prompt_active:
            return self._handle_vsync_prompt(event)

        self._apply_responsive_metrics()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Drag state'leri temizle
                self._settings_sb_drag_active = False
                self._slider_drag_active = False
                self._slider_drag_item = None
                self._slider_drag_bar_rect = None
                self.settings_manager.save_settings()
                return 'back'

            # Sekme değiştirme (Tab / Shift+Tab veya Q/E)
            if event.key == pygame.K_TAB:
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    self._switch_tab(-1)
                else:
                    self._switch_tab(1)
                return None

            # Sekme geçişi: Page Up / Page Down
            if event.key == pygame.K_PAGEUP:
                self._switch_tab(-1)
                return None
            if event.key == pygame.K_PAGEDOWN:
                self._switch_tab(1)
                return None
            if event.key == pygame.K_LEFTBRACKET:
                self._switch_tab(-1)
                return None
            if event.key == pygame.K_RIGHTBRACKET:
                self._switch_tab(1)
                return None

            # Gamepad sol/sağ ok tuşları (d-pad / sol stick) sekme değiştirmesin;
            # sekme geçişi yalnızca LB/RB (K_LEFTBRACKET / K_RIGHTBRACKET) ile yapılır.
            if getattr(event, 'from_gamepad', False) and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                pass  # Yok say — aşağıda ayar değiştirme olarak işlenecek

            # Yukarı / Aşağı - satır seçimi
            if event.key == pygame.K_UP:
                if self._selectable_indices:
                    self.selected = (self.selected - 1) % len(self._selectable_indices)
                    self._ensure_visible()
                return None
            if event.key == pygame.K_DOWN:
                if self._selectable_indices:
                    self.selected = (self.selected + 1) % len(self._selectable_indices)
                    self._ensure_visible()
                return None

            # Sol / Sağ / Enter / Space - ayar değiştir
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                if getattr(event, 'from_gamepad', False) and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    item_idx = self._selectable_indices[self.selected] if self.selected < len(self._selectable_indices) else -1
                    if item_idx >= 0:
                        item = self._tab_items[item_idx]
                        if self._should_ignore_gamepad_direction_for_item(item, event.key):
                            return None
                return self._handle_setting_action(event.key)

            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._reset_selected_keybind_to_default()
                return None

        # Mouse tekerleği
        elif event.type == pygame.MOUSEWHEEL:
            panel = self._panel_rect()
            content = self._content_rect(panel)
            metrics = self._layout_metrics()
            self.scroll_offset -= event.y * int(metrics['scroll_step'])
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll(content)))

        # Mouse hareket
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Settings scrollbar drag
            if self._settings_sb_drag_active and self._settings_sb_container_rect:
                panel = self._panel_rect()
                content = self._content_rect(panel)
                scrollbar = self._settings_scrollbar_layout(panel, content)
                track_y = int(scrollbar['track_y'])
                track_h = int(scrollbar['track_h'])
                thumb_h = self._settings_sb_thumb_rect.height if self._settings_sb_thumb_rect else int(scrollbar['thumb_fallback'])
                max_scroll = self._max_scroll(content)
                new_thumb_top = pos[1] - self._settings_sb_drag_offset_y - track_y
                new_thumb_top = max(0, min(new_thumb_top, track_h - thumb_h))
                ratio = new_thumb_top / max(1, track_h - thumb_h)
                self.scroll_offset = int(ratio * max_scroll)
                return None
            # Slider drag
            if self._slider_drag_active and self._slider_drag_item and self._slider_drag_bar_rect:
                return self._set_slider_from_x(self._slider_drag_item, pos[0], self._slider_drag_bar_rect)
            # Satır hover
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = i

        # Mouse tıklama
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            opened_by_gamepad_click = bool(getattr(event, 'from_gamepad', False) and getattr(event, 'button', None) == 1)

            # Settings scrollbar thumb drag başlatma
            if self._settings_sb_thumb_rect and self._settings_sb_thumb_rect.collidepoint(pos):
                self._settings_sb_drag_active = True
                self._settings_sb_drag_offset_y = pos[1] - self._settings_sb_thumb_rect.y
                return None

            # Settings scrollbar track alanına tıklama → o pozisyona zıpla
            if self._settings_sb_container_rect and self._settings_sb_container_rect.collidepoint(pos):
                panel = self._panel_rect()
                content = self._content_rect(panel)
                scrollbar = self._settings_scrollbar_layout(panel, content)
                up_arrow_rect = scrollbar['up_arrow_rect']
                down_arrow_rect = scrollbar['down_arrow_rect']
                _ty = int(scrollbar['track_y'])
                _th = int(scrollbar['track_h'])
                _tmh = self._settings_sb_thumb_rect.height if self._settings_sb_thumb_rect else int(scrollbar['thumb_fallback'])
                _max = self._max_scroll(content)
                step = int(self._layout_metrics()['scroll_step'])
                if up_arrow_rect.collidepoint(pos):
                    self.scroll_offset = max(0, self.scroll_offset - step)
                    return None
                if down_arrow_rect.collidepoint(pos):
                    self.scroll_offset = min(_max, self.scroll_offset + step)
                    return None
                _rel = pos[1] - _ty - _tmh // 2
                self.scroll_offset = int(max(0.0, min(1.0, _rel / max(1, _th - _tmh))) * _max)
                return None

            # Tab tıklama
            for i, rect in enumerate(self._tab_rects):
                if rect.collidepoint(pos):
                    if i != self.current_tab:
                        self.current_tab = i
                        self.selected = 0
                        self._rebuild_tab_content()
                    return None

            # Satır tıklama
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = i
                    if i < len(self._selectable_indices):
                        item_idx = self._selectable_indices[i]
                        item = self._tab_items[item_idx]
                        if item.get('type') == 'slider':
                            key = item.get('key', '')
                            bar_rect = self._slider_bar_rects.get(key)
                            slider_action_rects = getattr(self, '_slider_action_rects', {})
                            action_rects = slider_action_rects.get(key, {})
                            if bar_rect:
                                if bar_rect.collidepoint(pos):
                                    # Bar içine tıklandı: değer set et + drag başlat
                                    result = self._set_slider_from_x(item, pos[0], bar_rect)
                                    self._slider_drag_active = True
                                    self._slider_drag_key = key
                                    self._slider_drag_item = item
                                    self._slider_drag_bar_rect = bar_rect
                                    return result
                                else:
                                    left_zone = action_rects.get('left_rect')
                                    right_zone = action_rects.get('right_rect')
                                    if left_zone is not None and left_zone.collidepoint(pos):
                                        return self._handle_setting_action(pygame.K_LEFT)
                                    elif right_zone is not None and right_zone.collidepoint(pos):
                                        return self._handle_setting_action(pygame.K_RIGHT)
                                    else:
                                        return None
                            return None
                        if item.get('type') == 'keybind':
                            section = item.get('section')
                            if section == 'single_player':
                                slot_rects = self._keybind_slot_rects[i] if i < len(self._keybind_slot_rects) else None
                                if isinstance(slot_rects, dict):
                                    if slot_rects.get('secondary') and slot_rects['secondary'].collidepoint(pos):
                                        slot = 'secondary'
                                    elif slot_rects.get('primary') and slot_rects['primary'].collidepoint(pos):
                                        slot = 'primary'
                                    else:
                                        slot = 'secondary' if pos[0] >= rect.centerx else 'primary'
                                else:
                                    slot = 'secondary' if pos[0] >= rect.centerx else 'primary'
                                self._single_player_bind_slot = slot
                                self._start_keybind_capture(item, slot=slot, opened_by_gamepad_click=opened_by_gamepad_click)
                                return None
                            if self._is_gamepad_keybind_section(section):
                                slot_rects = self._keybind_slot_rects[i] if i < len(self._keybind_slot_rects) else None
                                if isinstance(slot_rects, dict):
                                    primary_rect = slot_rects.get('primary')
                                    secondary_rect = slot_rects.get('secondary')
                                    if secondary_rect is not None and secondary_rect.collidepoint(pos):
                                        self._gamepad_bind_slot = 'secondary'
                                    elif primary_rect is not None and primary_rect.collidepoint(pos):
                                        self._gamepad_bind_slot = 'primary'
                                    else:
                                        self._gamepad_bind_slot = 'secondary' if pos[0] >= rect.centerx else 'primary'
                                else:
                                    self._gamepad_bind_slot = 'secondary' if pos[0] >= rect.centerx else 'primary'
                                self._start_keybind_capture(item, slot=self._gamepad_bind_slot, opened_by_gamepad_click=opened_by_gamepad_click)
                                return None
                            slot_rects = self._keybind_slot_rects[i] if i < len(self._keybind_slot_rects) else None
                            if isinstance(slot_rects, dict):
                                primary_rect = slot_rects.get('primary')
                                if primary_rect is None or not primary_rect.collidepoint(pos):
                                    return None
                            self._start_keybind_capture(item, slot='primary', opened_by_gamepad_click=opened_by_gamepad_click)
                            return None
                    itype_local = item.get('type', '') if i < len(self._selectable_indices) else ''
                    if itype_local in ('selector', 'music_selector'):
                        srects = self._keybind_slot_rects[i] if i < len(self._keybind_slot_rects) else None
                        if isinstance(srects, dict) and 'left_rect' in srects and 'right_rect' in srects:
                            if srects['left_rect'].collidepoint(pos):
                                return self._handle_setting_action(pygame.K_LEFT)
                            elif srects['right_rect'].collidepoint(pos):
                                return self._handle_setting_action(pygame.K_RIGHT)
                            if itype_local == 'music_selector':
                                return self._handle_setting_action(pygame.K_RETURN)
                        return self._handle_setting_action(pygame.K_RIGHT)
                    return self._handle_setting_action(pygame.K_RETURN)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._settings_sb_drag_active:
                self._settings_sb_drag_active = False
                self._settings_sb_drag_offset_y = 0
            if self._slider_drag_active:
                self._slider_drag_active = False
                self._slider_drag_key = ''
                self._slider_drag_item = None
                self._slider_drag_bar_rect = None

        return None

    def _switch_tab(self, delta: int) -> None:
        self.current_tab = (self.current_tab + delta) % len(TAB_DEFS)
        self.selected = 0
        self._rebuild_tab_content()

    def _handle_setting_action(self, key_code: int) -> str | None:
        """Seçili ayar üzerinde işlem yap."""
        if not self._selectable_indices:
            return None
        if self.selected >= len(self._selectable_indices):
            return None

        item_idx = self._selectable_indices[self.selected]
        item = self._tab_items[item_idx]
        itype = item['type']
        skey = item.get('key', '')

        if itype == 'toggle':
            if key_code in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                return self._toggle_value(skey)

        elif itype == 'slider':
            if key_code == pygame.K_LEFT:
                return self._adjust_slider(skey, -1, item)
            elif key_code == pygame.K_RIGHT:
                return self._adjust_slider(skey, 1, item)

        elif itype == 'selector':
            delta = 1 if key_code in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE) else -1
            return self._cycle_selector(skey, delta)

        elif itype == 'submenu':
            if key_code in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT):
                return skey  # 'controls', 'block_styles', 'piece_workshop', 'mode_music'

        elif itype == 'music_selector':
            mode_key = item.get('mode_key')
            if not mode_key:
                return None
            if mode_key == 'campaign':
                if key_code in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                    self._open_campaign_phase_select()
                    return None
                return None
            if key_code in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                return f'edit_mode_playlist:{mode_key}'
            return None

        elif itype == 'keybind':
            section = item.get('section')

            if section == 'single_player':
                if key_code == pygame.K_LEFT:
                    self._single_player_bind_slot = 'primary'
                    return None
                if key_code == pygame.K_RIGHT:
                    self._single_player_bind_slot = 'secondary'
                    return None
                if key_code in (pygame.K_RETURN, pygame.K_SPACE):
                    self._start_keybind_capture(item, slot=self._single_player_bind_slot)
                return None

            if self._is_gamepad_keybind_section(section):
                if key_code == pygame.K_LEFT:
                    self._gamepad_bind_slot = 'primary'
                    return None
                if key_code == pygame.K_RIGHT:
                    self._gamepad_bind_slot = 'secondary'
                    return None
                if key_code in (pygame.K_RETURN, pygame.K_SPACE):
                    self._start_keybind_capture(item, slot=self._gamepad_bind_slot)
                return None

            if key_code in (pygame.K_RETURN, pygame.K_SPACE):
                self._start_keybind_capture(item, slot='primary')
            return None

        return None

    def _should_ignore_gamepad_direction_for_item(self, item: dict, key_code: int) -> bool:
        if key_code not in (pygame.K_LEFT, pygame.K_RIGHT):
            return False
        if item.get('type') != 'keybind':
            return False
        section = item.get('section')
        return section != 'single_player' and not self._is_gamepad_keybind_section(section)

    def _ensure_visible(self) -> None:
        """Seçili öğenin görünür olmasını sağla."""
        if not self._selectable_indices or self.selected >= len(self._selectable_indices):
            return
        panel = self._panel_rect()
        content = self._content_rect(panel)
        metrics = self._layout_metrics()
        row_h = int(metrics['row_height'])
        section_h = int(metrics['section_height'])

        item_idx = self._selectable_indices[self.selected]
        y_offset = 0
        for i in range(item_idx):
            y_offset += section_h if self._tab_items[i]['type'] == 'section' else row_h

        if y_offset < self.scroll_offset:
            self.scroll_offset = y_offset
        elif y_offset + row_h > self.scroll_offset + content.height:
            self.scroll_offset = y_offset + row_h - content.height

        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll(content)))

    def _handle_vsync_prompt(self, event) -> str | None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_UP):
                self._vsync_prompt_choice = 0
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self._vsync_prompt_choice = 1
            elif event.key == pygame.K_ESCAPE:
                self._vsync_prompt_active = False
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._vsync_prompt_active = False
                if self._vsync_prompt_choice == 0:
                    return 'restart_now'
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if len(self._vsync_prompt_buttons) == 2:
                if self._vsync_prompt_buttons[0].collidepoint(pos):
                    self._vsync_prompt_active = False
                    return 'restart_now'
                if self._vsync_prompt_buttons[1].collidepoint(pos):
                    self._vsync_prompt_active = False
        return None

    def _handle_display_mode_confirm(self, event) -> str | None:
        """Display mode onay modalı girdilerini işle."""
        if not getattr(self, '_display_mode_confirm_active', False):
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.fullscreen = bool(getattr(self, '_display_mode_confirm_prev_fullscreen', True))
                self._display_mode_confirm_active = False
                return None
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                target = bool(getattr(self, '_display_mode_confirm_target_fullscreen', True))
                self.fullscreen = target
                try:
                    self.settings_manager.set('fullscreen', target)
                except Exception:
                    pass
                self._display_mode_confirm_active = False
                return 'quit_game'

        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            raw_pos = getattr(event, 'pos', None)
            pos = normalize_mouse_pos(raw_pos) if raw_pos is not None else raw_pos
            if pos is None:
                pos = raw_pos

            yes_rect = getattr(self, '_display_mode_confirm_yes_rect', None)
            no_rect = getattr(self, '_display_mode_confirm_no_rect', None)

            if yes_rect is not None and yes_rect.collidepoint(pos):
                target = bool(getattr(self, '_display_mode_confirm_target_fullscreen', True))
                self.fullscreen = target
                try:
                    self.settings_manager.set('fullscreen', target)
                except Exception:
                    pass
                self._display_mode_confirm_active = False
                return 'quit_game'

            if no_rect is not None and no_rect.collidepoint(pos):
                self.fullscreen = bool(getattr(self, '_display_mode_confirm_prev_fullscreen', True))
                self._display_mode_confirm_active = False
                return None

        return None

    # ------------------------------------------------------------------
    # Update (animasyonlar)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pass  # draw() içinde dt hesaplanıyor

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------

    def draw(self) -> None:
        self._apply_responsive_metrics()
        width, height = self.screen.get_size()

        # Smooth slider animasyonları
        now_ms = pygame.time.get_ticks()
        dt = (now_ms - self._anim_last_tick) / 1000.0
        self._anim_last_tick = now_ms
        dt = max(0.0, min(0.05, dt))
        speed = 18.0
        self._music_volume_vis += (self.music_volume - self._music_volume_vis) * min(1.0, dt * speed)
        self._menu_music_volume_vis += (self.menu_music_volume - self._menu_music_volume_vis) * min(1.0, dt * speed)
        self._sfx_volume_vis += (self.sfx_volume - self._sfx_volume_vis) * min(1.0, dt * speed)

        # Arka plan
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        # Panel
        panel = self._panel_rect()
        self._draw_panel(panel)

        # Başlık
        self._draw_title(panel)

        # Sekme çubuğu
        tab_bar = self._tab_bar_rect(panel)
        self._draw_tab_bar(tab_bar)

        # İçerik alanı
        content = self._content_rect(panel)
        self._draw_content(content)

        # VSync prompt
        if self._vsync_prompt_active:
            self._draw_vsync_prompt()

        if self._music_picker_open:
            self._draw_music_picker()

        if self._campaign_phase_select_active:
            self._draw_campaign_phase_select_overlay()

        if self._playlist_edit_active:
            self._draw_mode_playlist_edit_overlay()

        if self._display_mode_confirm_active:
            self._draw_display_mode_confirm_panel()

    def _draw_panel(self, rect: pygame.Rect) -> None:
        """Koyu yarı-saydam panel arka planı."""
        metrics = self._layout_metrics()
        shadow_pad = int(metrics['panel_shadow_pad'])
        shadow_offset = int(metrics['panel_shadow_offset'])
        shadow_radius = int(metrics['panel_shadow_radius'])
        border_radius = int(metrics['panel_border_radius'])
        border_width = int(metrics['panel_border_width'])
        _sma = _scale_menu_alpha

        # Gölge
        shadow = pygame.Surface((rect.width + shadow_pad, rect.height + shadow_pad), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, _sma(60)), shadow.get_rect(), border_radius=shadow_radius)
        self.screen.blit(shadow, (rect.x + shadow_offset, rect.y + shadow_offset))

        # Ana panel
        panel_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel_surf.fill((12, 16, 32, _sma(235)))
        # Üst kenar highlight
        highlight_depth = min(self._s(30, minimum=18), rect.height // 4)
        for y in range(highlight_depth):
            alpha = _sma(int(15 * (1 - y / max(1, highlight_depth))))
            pygame.draw.line(panel_surf, (255, 255, 255, alpha), (0, y), (rect.width, y))
        self.screen.blit(panel_surf, rect.topleft)

        # Kenar çizgisi
        pygame.draw.rect(self.screen, (60, 70, 100), rect, border_width, border_radius=border_radius)

        # Üst kenar vurgulu çizgi
        pygame.draw.line(
            self.screen, (80, 140, 220),
            (rect.x + border_width, rect.y + 1), (rect.right - border_width, rect.y + 1), 1,
        )

    def _draw_title(self, panel: pygame.Rect) -> None:
        """Başlık ve kapatma butonu."""
        metrics = self._layout_metrics()
        lang = get_language()
        title_text = _t('panel_settings', 'AYARLAR' if lang == 'tr' else 'SETTINGS')
        title_surf = self.font_title.render(title_text, True, (220, 235, 255))
        self.screen.blit(title_surf, (panel.x + int(metrics['title_pad_x']), panel.y + int(metrics['title_pad_y'])))
        self._close_btn_rect = None

        # Başlık altı çizgi
        line_y = panel.y + int(metrics['title_rule_y'])
        inset = int(metrics['title_rule_inset'])
        pygame.draw.line(self.screen, (50, 60, 90), (panel.x + inset, line_y), (panel.right - inset, line_y), 1)

    def _draw_tab_bar(self, bar_rect: pygame.Rect) -> None:
        """Sekme çubuğunu çiz."""
        metrics = self._layout_metrics()
        self._tab_rects = []
        num_tabs = len(TAB_DEFS)
        tab_gap = int(metrics['tab_gap'])
        total_gap = tab_gap * (num_tabs - 1)
        inner_margin = int(metrics['tab_inner_margin'])
        available_w = bar_rect.width - inner_margin * 2
        tab_w = (available_w - total_gap) // num_tabs

        for i, tab_def in enumerate(TAB_DEFS):
            tx = bar_rect.x + inner_margin + i * (tab_w + tab_gap)
            tab_rect = pygame.Rect(tx, bar_rect.y, tab_w, bar_rect.height)
            self._tab_rects.append(tab_rect)

            is_active = (i == self.current_tab)
            label = _tab_label(tab_def)

            # Tab arka planı
            _sma = _scale_menu_alpha
            tab_surf = pygame.Surface(tab_rect.size, pygame.SRCALPHA)
            if is_active:
                tab_surf.fill((35, 55, 90, _sma(220)))
            else:
                tab_surf.fill((20, 28, 48, _sma(160)))
            self.screen.blit(tab_surf, tab_rect.topleft)

            # Alt çizgi (aktif sekme)
            if is_active:
                indicator_h = int(metrics['tab_indicator_height'])
                indicator_rect = pygame.Rect(tab_rect.x, tab_rect.bottom - indicator_h, tab_rect.width, indicator_h)
                pygame.draw.rect(self.screen, (80, 180, 255), indicator_rect)

            # Tab metni
            color = (255, 255, 255) if is_active else (140, 155, 180)
            tab_font = self._fit_font(label, 18, tab_w - self._s(10, minimum=8), bold=is_active, minimum=12)
            text_surf = tab_font.render(label, True, color)
            text_rect = text_surf.get_rect(center=tab_rect.center)
            self.screen.blit(text_surf, text_rect)

    def _draw_content(self, content_rect: pygame.Rect) -> None:
        """Mevcut sekmenin içeriğini çiz."""
        metrics = self._layout_metrics()
        self.option_rects = []
        self._keybind_slot_rects = []
        self._help_icon_rects = []
        self._slider_bar_rects = {}
        self._slider_action_rects = {}
        row_h = int(metrics['row_height'])
        section_h = int(metrics['section_height'])
        sel_item_index = 0  # seçilebilir öğe sayacı

        # Clip area
        self.screen.set_clip(content_rect)

        y = content_rect.y - self.scroll_offset
        for i, item in enumerate(self._tab_items):
            itype = item['type']

            if itype == 'section':
                # Bölüm başlığı
                if y + section_h > content_rect.y - self._s(20, minimum=14) and y < content_rect.bottom:
                    self._draw_section_header(content_rect.x, y, content_rect.width, section_h, item)
                y += section_h
                continue

            # Ayar satırı – sol/sağ padding artırıldı
            row_rect = pygame.Rect(
                content_rect.x + int(metrics['row_inset_x']),
                y + int(metrics['row_inset_y']),
                content_rect.width - int(metrics['row_inset_x']) * 2,
                row_h - int(metrics['row_inner_height_delta']),
            )

            is_selected = False
            if sel_item_index < len(self._selectable_indices):
                is_selected = (sel_item_index == self.selected)

            if y + row_h > content_rect.y and y < content_rect.bottom:
                self.option_rects.append(row_rect)
                slot_rects = self._draw_setting_item(row_rect, item, is_selected)
                self._keybind_slot_rects.append(slot_rects)
            else:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                self._keybind_slot_rects.append(None)

            sel_item_index += 1
            y += row_h

        self.screen.set_clip(None)

        # Scrollbar – panel'in dışına/sağına konumlandırılmış, sürüklenebilir
        panel = self._panel_rect()
        max_scroll = self._max_scroll(content_rect)
        total_h = self._content_total_height(row_h, section_h)
        if max_scroll > 0:
            scrollbar = self._settings_scrollbar_layout(panel, content_rect)
            sb_container = scrollbar['container']
            self._settings_sb_container_rect = sb_container
            self._settings_sb_thumb_rect = retro_style.draw_scrollbar(
                self.screen, sb_container,
                self.scroll_offset, total_h, content_rect.height,
                bar_width=int(scrollbar['bar_width']),
            )
        else:
            self._settings_sb_thumb_rect = None
            self._settings_sb_container_rect = None

        self._draw_help_tooltip(content_rect)

    def _draw_section_header(
        self, x: int, y: int, w: int, h: int, item: dict,
    ) -> None:
        """Bölüm başlığını çiz (renkli, küçük font)."""
        s = self._s
        label = _item_label(item)
        # Accent renkli metin
        color = (80, 200, 180)  # Teal/Cyan
        surf = self.font_section.render(label, True, color)
        self.screen.blit(surf, (x + s(24, minimum=16), y + h - surf.get_height() - s(4, minimum=2)))
        # Alt çizgi
        line_y = y + h - 1
        pygame.draw.line(self.screen, (40, 55, 75), (x + s(20, minimum=14), line_y), (x + w - s(20, minimum=14), line_y), 1)

    def _draw_setting_item(
        self, rect: pygame.Rect, item: dict, selected: bool,
    ) -> dict | None:
        """Bir ayar satırını çiz."""
        s = self._s
        _sma = _scale_menu_alpha
        itype = item['type']
        label = _item_label(item)

        # Arka plan (alternatif renkler, seçili vurgu)
        bg_alpha = _sma(180) if selected else _sma(130)
        bg_color = (28, 38, 60) if selected else (18, 24, 42)
        row_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        row_surf.fill((*bg_color, bg_alpha))
        if selected:
            # Üst highlight
            highlight_depth = min(s(8, minimum=6), rect.height // 4)
            for yy in range(highlight_depth):
                a = _sma(int(15 * (1 - yy / max(1, highlight_depth))))
                pygame.draw.line(row_surf, (255, 255, 255, a), (0, yy), (rect.width, yy))
        self.screen.blit(row_surf, rect.topleft)

        # Kenar
        if selected:
            pygame.draw.rect(self.screen, (80, 160, 255, _sma(180)), rect, 1, border_radius=s(6, minimum=4))
        else:
            pygame.draw.rect(self.screen, (40, 50, 70), rect, 1, border_radius=s(6, minimum=4))

        # Label – sol padding artırıldı
        label_color = (255, 255, 255) if selected else (190, 200, 215)
        max_label_w = int(rect.width * 0.42)
        label_font = self._fit_font(label, 22, max_label_w, bold=True, minimum=14)
        label_surf = label_font.render(label, True, label_color)
        label_x = rect.x + s(24, minimum=16)
        label_y = rect.centery - label_surf.get_height() // 2
        self.screen.blit(label_surf, (label_x, label_y))

        help_text = self._help_text_for_item(item)
        if help_text:
            self._draw_label_help_icon(rect, label_x, label_surf, help_text, selected)

        # Value
        if itype == 'toggle':
            self._draw_toggle_badge(rect, item, selected)
            return None
        elif itype == 'slider':
            self._draw_inline_slider(rect, item, selected)
            return None
        elif itype in ('selector', 'music_selector', 'keybind'):
            return self._draw_selector_value(rect, item, selected)
        elif itype == 'submenu':
            self._draw_submenu_arrow(rect, selected)
            return None

        return None

    def _help_text_for_item(self, item: dict) -> str | None:
        """Yardım ikonu için hover açıklama metnini döndür."""
        key = str(item.get('key', '') or '')
        if key == 'das_delay':
            value = t('das_delay_desc')
            return value if value != 'das_delay_desc' else 'Sağ/sol tuşunu basılı tutunca otomatik kayma başlamadan önceki bekleme süresi. Düşük değer daha hızlıdır.'
        if key == 'das_repeat':
            value = t('das_repeat_desc')
            return value if value != 'das_repeat_desc' else 'Basılı tutma başladıktan sonra sağ/sol otomatik kaymanın tekrar hızı. Düşük değer daha hızlıdır.'
        if key == 'soft_drop_speed':
            value = t('soft_drop_desc')
            return value if value != 'soft_drop_desc' else 'Aşağı tuşuna basılı tutarken parçanın düşme hızı. Düşük değer daha hızlıdır.'
        if key == 'ui_scale_preset':
            return 'Yalnizca effective UI yolundaki tam ekran panelleri etkiler. Popup ve campaign overlay zinciri ayni kalir.'
        return None

    def _draw_label_help_icon(
        self,
        row_rect: pygame.Rect,
        label_x: int,
        label_surf: pygame.Surface,
        help_text: str,
        selected: bool,
    ) -> None:
        """Etiketin sağına soru işareti ikonu çiz ve hover alanını kaydet."""
        s = self._s
        icon_r = s(9, minimum=6)
        icon_cx = label_x + label_surf.get_width() + s(16, minimum=10) + icon_r
        icon_cx = min(icon_cx, row_rect.x + int(row_rect.width * 0.48))
        icon_cy = row_rect.centery
        icon_rect = pygame.Rect(icon_cx - icon_r, icon_cy - icon_r, icon_r * 2, icon_r * 2)

        base_color = (80, 160, 255) if selected else (100, 120, 150)
        fill_alpha = 120 if selected else 90
        pygame.draw.circle(self.screen, (*base_color, fill_alpha), (icon_cx, icon_cy), icon_r)
        pygame.draw.circle(self.screen, (*base_color, 220), (icon_cx, icon_cy), icon_r, 1)

        q_font = self._font(14, bold=True, minimum=10)
        q_surf = q_font.render('?', True, (235, 245, 255))
        self.screen.blit(q_surf, q_surf.get_rect(center=(icon_cx, icon_cy + 1)))

        self._help_icon_rects.append((icon_rect, help_text))

    def _wrap_help_text(self, text: str, font, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return [text]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f'{current} {word}'
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _draw_help_tooltip(self, content_rect: pygame.Rect) -> None:
        """? ikonuna hover edildiğinde açıklama tooltip'i çiz."""
        s = self._s
        if not self._help_icon_rects:
            return

        mouse_pos = get_mouse_pos()
        hovered_rect = None
        hovered_text = None
        for icon_rect, text in self._help_icon_rects:
            if icon_rect.collidepoint(mouse_pos):
                hovered_rect = icon_rect
                hovered_text = text
                break

        if hovered_rect is None or not hovered_text:
            return

        font = self.font_hint
        max_text_w = min(s(420, minimum=260), max(s(240, minimum=180), int(content_rect.width * 0.45)))
        lines = self._wrap_help_text(hovered_text, font, max_text_w)

        line_h = font.get_height() + s(3, minimum=2)
        tooltip_w = min(s(460, minimum=280), max(s(260, minimum=200), max(font.size(line)[0] for line in lines) + s(24, minimum=18)))
        tooltip_h = max(s(42, minimum=34), len(lines) * line_h + s(16, minimum=12))

        screen_w, screen_h = self.screen.get_size()
        tip_x = hovered_rect.right + s(12, minimum=8)
        if tip_x + tooltip_w > screen_w - s(10, minimum=8):
            tip_x = hovered_rect.left - tooltip_w - s(12, minimum=8)
        tip_y = hovered_rect.centery - tooltip_h // 2
        tip_y = max(s(10, minimum=8), min(screen_h - tooltip_h - s(10, minimum=8), tip_y))

        tip_rect = pygame.Rect(tip_x, tip_y, tooltip_w, tooltip_h)
        retro_style.draw_glass_panel(
            self.screen,
            tip_rect,
            alpha=230,
            border_color=(90, 170, 255),
            glow=True,
        )

        text_y = tip_rect.y + s(8, minimum=6)
        for line in lines:
            line_surf = font.render(line, True, (225, 235, 250))
            self.screen.blit(line_surf, (tip_rect.x + s(12, minimum=8), text_y))
            text_y += line_h

    def _draw_music_picker(self) -> None:
        metrics = self._music_picker_metrics()
        width, height = self.screen.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_rect = metrics['panel']
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = self._font(28, bold=True, minimum=18)
        subtitle_font = self._font(18, minimum=12)
        title = title_font.render(t('tracks'), True, (235, 245, 255))
        self.screen.blit(title, (int(metrics['title_x']), int(metrics['title_y'])))

        mode_name = ''
        mode_key = self._music_picker_mode_key
        for mk, label in get_mode_music_entries():
            if mk == mode_key:
                mode_name = label
                break
        sub = subtitle_font.render(mode_name, True, (170, 190, 220))
        self.screen.blit(sub, (int(metrics['title_x']), int(metrics['subtitle_y'])))

        list_rect = metrics['list_rect']
        item_h = int(metrics['item_h'])
        gap = int(metrics['gap'])

        self._music_picker_scroll = max(0, min(self._music_picker_scroll, self._picker_max_scroll(list_rect.height, item_h, gap)))

        self._music_picker_item_rects = []
        self.screen.set_clip(list_rect)
        for idx, option in enumerate(self._track_options):
            y = list_rect.y + idx * (item_h + gap) - self._music_picker_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue

            rect = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self._music_picker_item_rects.append((rect, idx))

            selected = idx == self._music_picker_selected
            label = str(option.get('label', ''))
            retro_style.draw_uniform_button(
                self.screen,
                rect,
                label,
                color_code=retro_style.primary,
                selected=selected,
            )
        self.screen.set_clip(None)

        total_h = len(self._track_options) * (item_h + gap)
        if total_h > list_rect.height:
            sb_rect = pygame.Rect(int(metrics['scrollbar_x']), list_rect.y, int(metrics['scrollbar_w']), list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self._music_picker_scroll, total_h, list_rect.height)

    def _draw_toggle_badge(self, rect: pygame.Rect, item: dict, selected: bool) -> None:
        """Toggle tipi ayar için < AÇIK/KAPALI > badge."""
        s = self._s
        value_text, value_color = self._get_display_value(item)
        key = item.get('key', '')
        is_on = bool(self._get_value(key))
        if key == 'mute_all':
            is_on = bool(self._get_value(key))
            badge_color = (180, 70, 70) if is_on else (60, 160, 90)
        else:
            badge_color = (60, 160, 90) if is_on else (180, 70, 70)

        badge_font = self._fit_font(value_text, 16, s(100, minimum=72), bold=True, minimum=11)
        badge_surf = badge_font.render(value_text, True, (255, 255, 255))
        bw = badge_surf.get_width() + s(24, minimum=18)
        bh = badge_surf.get_height() + s(10, minimum=8)
        badge_rect = pygame.Rect(rect.right - bw - s(40, minimum=28), rect.centery - bh // 2, bw, bh)
        pygame.draw.rect(self.screen, badge_color, badge_rect, border_radius=bh // 2)
        self.screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))

        # < > okları
        if selected:
            arrow_font = self._font(18, bold=True, minimum=12)
            arrow_color = (80, 160, 255)
            left_arrow = arrow_font.render('<', True, arrow_color)
            right_arrow = arrow_font.render('>', True, arrow_color)
            self.screen.blit(left_arrow, left_arrow.get_rect(midright=(badge_rect.left - s(6, minimum=4), rect.centery)))
            self.screen.blit(right_arrow, right_arrow.get_rect(midleft=(badge_rect.right + s(6, minimum=4), rect.centery)))

    def _draw_inline_slider(self, rect: pygame.Rect, item: dict, selected: bool) -> None:
        """Slider tipi ayar için sürgü çiz."""
        s = self._s
        key = item.get('key', '')
        min_val = item.get('min', 0)
        max_val = item.get('max', 1)
        current = float(self._get_value(key))

        # Smooth animasyon
        if key == 'music_volume':
            current = self._music_volume_vis
        elif key == 'menu_music_volume':
            current = self._menu_music_volume_vis
        elif key == 'sfx_volume':
            current = self._sfx_volume_vis

        ratio = (current - min_val) / max(0.001, max_val - min_val)
        ratio = max(0.0, min(1.0, ratio))

        # Değer metni
        if key == 'particle_effects':
            value_text = self._particle_effects_label(int(current))
        elif key == 'ctrl_gp_rumble':
            value_text = self._gamepad_rumble_label(int(current))
        elif item.get('percent'):
            value_text = f'{int(current * 100)}%'
        else:
            value_text = f'{int(current)} {item.get("suffix", "")}'.strip()

        # Layout
        slider_right = rect.right - s(20, minimum=14)
        value_font = self._font(18, bold=True, minimum=12)
        value_surf = value_font.render(value_text, True, (220, 235, 255))

        # > oku
        arrow_font = self._font(16, bold=True, minimum=11)
        arrow_color = (80, 160, 255) if selected else (100, 120, 150)

        right_arrow = arrow_font.render('>', True, arrow_color)
        right_x = slider_right - right_arrow.get_width()
        right_arrow_rect = right_arrow.get_rect(midleft=(right_x, rect.centery))
        self.screen.blit(right_arrow, right_arrow_rect)

        # Değer metni
        val_x = right_x - value_surf.get_width() - s(8, minimum=6)
        self.screen.blit(value_surf, value_surf.get_rect(midright=(val_x + value_surf.get_width(), rect.centery)))

        # Slider bar – %45 noktasından başla
        bar_right = val_x - s(12, minimum=8)
        bar_left = rect.x + int(rect.width * 0.45)

        # < oku
        left_arrow = arrow_font.render('<', True, arrow_color)
        left_arrow_rect = left_arrow.get_rect(midright=(bar_left - s(4, minimum=3), rect.centery))
        self.screen.blit(left_arrow, left_arrow_rect)
        bar_left += s(2, minimum=1)

        if bar_right > bar_left + s(30, minimum=20):
            bar_h = s(14, minimum=10)
            r = bar_h // 2
            bar_rect = pygame.Rect(bar_left, rect.centery - bar_h // 2, bar_right - bar_left, bar_h)
            self._slider_bar_rects[key] = bar_rect
            left_zone_x = max(rect.x, left_arrow_rect.x - s(10, minimum=6))
            self._slider_action_rects[key] = {
                'left_rect': pygame.Rect(
                    left_zone_x,
                    rect.y,
                    max(0, bar_rect.x - left_zone_x),
                    rect.height,
                ),
                'right_rect': pygame.Rect(
                    bar_rect.right,
                    rect.y,
                    max(0, rect.right - bar_rect.right),
                    rect.height,
                ),
            }

            # Slider rengi (dolgu + knob için ortak) – neon palette
            if key in ('music_volume', 'menu_music_volume'):
                fill_color = (0, 210, 255)    # neon cyan
            elif key == 'sfx_volume':
                fill_color = (255, 185, 0)    # neon gold
            elif key == 'bg_transparency':
                fill_color = (0, 255, 160)    # neon green
            elif key == 'menu_transparency':
                fill_color = (190, 60, 255)   # neon purple
            elif key in ('particle_effects', 'ctrl_gp_rumble'):
                fill_color = (255, 170, 70)   # amber
            elif key in ('das_delay', 'das_repeat', 'soft_drop_speed'):
                fill_color = (255, 80, 160)   # neon pink
            else:
                fill_color = (0, 180, 255)    # neon blue

            # Track – pill şekli, derinlik gölgesi
            _sma = _scale_menu_alpha
            track_surf = pygame.Surface((bar_rect.width, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(track_surf, (20, 28, 48, _sma(200)), track_surf.get_rect(), border_radius=r)
            pygame.draw.rect(track_surf, (60, 80, 120, _sma(130)), track_surf.get_rect(), 1, border_radius=r)
            hl_t = pygame.Surface((max(1, bar_rect.width - s(6, minimum=4)), s(2, minimum=2)), pygame.SRCALPHA)
            hl_t.fill((255, 255, 255, _sma(14)))
            track_surf.blit(hl_t, (s(3, minimum=2), s(3, minimum=2)))
            self.screen.blit(track_surf, bar_rect.topleft)

            # Dolgu – parlak pill + üst vurgu şeridi
            fill_w = int(bar_rect.width * ratio)
            if fill_w > 2:
                fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
                pygame.draw.rect(fill_surf, (*fill_color, _sma(220)), fill_surf.get_rect(), border_radius=r)
                # üst parlak vurgu
                hl_f = pygame.Surface((max(1, fill_w - s(8, minimum=6)), s(3, minimum=2)), pygame.SRCALPHA)
                hl_f.fill((255, 255, 255, _sma(70)))
                fill_surf.blit(hl_f, (s(4, minimum=3), s(2, minimum=1)))
                # hafif glow overlay
                glow_c = tuple(min(255, c + 55) for c in fill_color)
                pygame.draw.rect(fill_surf, (*glow_c, _sma(45)), fill_surf.get_rect(), border_radius=r)
                self.screen.blit(fill_surf, bar_rect.topleft)

            # Knob – glow + dış halka + iç daire + vurgu nokta
            knob_x = bar_rect.x + fill_w
            knob_r = s(9, minimum=6)
            is_active = selected or (self._slider_drag_active and self._slider_drag_key == key)
            if is_active:
                glow_pad = s(6, minimum=4)
                glow_surf = pygame.Surface((knob_r * 2 + glow_pad * 2, knob_r * 2 + glow_pad * 2), pygame.SRCALPHA)
                for gi, ga in enumerate([20, 40, 60]):
                    gr = knob_r + glow_pad - gi * s(2, minimum=1)
                    pygame.draw.circle(glow_surf, (*fill_color, ga), (knob_r + glow_pad, knob_r + glow_pad), gr)
                self.screen.blit(glow_surf, (knob_x - knob_r - glow_pad, rect.centery - knob_r - glow_pad))
            pygame.draw.circle(self.screen, fill_color, (knob_x, rect.centery), knob_r, 2)
            knob_inner = (255, 255, 255) if is_active else (200, 212, 230)
            pygame.draw.circle(self.screen, knob_inner, (knob_x, rect.centery), knob_r - 2)
            pygame.draw.circle(self.screen, (255, 255, 255), (knob_x - 2, rect.centery - 3), max(1, knob_r // 4))

    def _draw_selector_value(self, rect: pygame.Rect, item: dict, selected: bool) -> dict | None:
        """Selector tipi ayar için < değer > göster."""
        s = self._s
        if item.get('type') == 'keybind' and item.get('section') == 'single_player':
            action_key = item.get('action_key')
            row = self._control_config.get('single_player', {}).get(action_key, {})
            if isinstance(row, dict):
                primary_text = str(row.get('primary', '') or '').upper() or '—'
                secondary_text = str(row.get('secondary', '') or '').upper() or '—'
            else:
                primary_text = str(row or '').upper() or '—'
                secondary_text = '—'

            if self._waiting_for_key and self._pending_keybind_item == item:
                waiting_text = t('press_key')
                if self._pending_keybind_slot == 'secondary':
                    secondary_text = waiting_text
                else:
                    primary_text = waiting_text

            panel_h = max(s(30, minimum=24), rect.height - s(18, minimum=12))
            gap = s(10, minimum=6)
            total_w = min(s(340, minimum=240), int(rect.width * 0.46))
            each_w = max(s(90, minimum=72), (total_w - gap) // 2)
            right_margin = s(24, minimum=16)
            right_x = rect.right - right_margin - each_w
            left_x = right_x - gap - each_w

            primary_rect = pygame.Rect(left_x, rect.centery - panel_h // 2, each_w, panel_h)
            secondary_rect = pygame.Rect(right_x, rect.centery - panel_h // 2, each_w, panel_h)

            is_primary_active = selected and self._single_player_bind_slot == 'primary'
            is_secondary_active = selected and self._single_player_bind_slot == 'secondary'
            if self._waiting_for_key and self._pending_keybind_item == item:
                is_primary_active = self._pending_keybind_slot != 'secondary'
                is_secondary_active = self._pending_keybind_slot == 'secondary'

            self._draw_text_binding_slot(primary_rect, primary_text, is_primary_active)
            self._draw_text_binding_slot(secondary_rect, secondary_text, is_secondary_active)

            return {'primary': primary_rect, 'secondary': secondary_rect}

        if item.get('type') == 'keybind' and item.get('section') in ('pvp.player1', 'pvp.player2'):
            action_key = item.get('action_key')
            if item.get('section') == 'pvp.player1':
                value = self._control_config.get('pvp', {}).get('player1', {}).get(action_key, '')
            else:
                value = self._control_config.get('pvp', {}).get('player2', {}).get(action_key, '')

            key_text = str(value or '').upper() or '—'
            if self._waiting_for_key and self._pending_keybind_item == item:
                key_text = t('press_key')

            panel_h = max(s(30, minimum=24), rect.height - s(18, minimum=12))
            slot_w = max(s(90, minimum=72), min(s(165, minimum=118), int(rect.width * 0.23)))
            right_margin = s(24, minimum=16)
            primary_rect = pygame.Rect(rect.right - right_margin - slot_w, rect.centery - panel_h // 2, slot_w, panel_h)

            is_active = selected or (self._waiting_for_key and self._pending_keybind_item == item)
            self._draw_text_binding_slot(primary_rect, key_text, is_active)
            return {'primary': primary_rect}

        if item.get('type') == 'keybind' and self._is_gamepad_keybind_section(item.get('section')):
            action_key = item.get('action_key')
            primary_val, secondary_val = self._get_gamepad_binding_slots(action_key)
            gp_type = self._current_gamepad_prompt_type()
            primary_display = self._get_gamepad_slot_display(primary_val, gp_type)
            secondary_display = self._get_gamepad_slot_display(secondary_val, gp_type)

            if self._waiting_for_key and self._pending_keybind_item == item:
                waiting_text = _t('gp_press_button', 'Butona basın')
                if self._pending_keybind_slot == 'secondary':
                    secondary_display = {'mode': 'text', 'text': waiting_text}
                else:
                    primary_display = {'mode': 'text', 'text': waiting_text}

            panel_h = max(s(30, minimum=24), rect.height - s(18, minimum=12))
            gap = s(10, minimum=6)
            total_w = min(s(340, minimum=240), int(rect.width * 0.46))
            each_w = max(s(90, minimum=72), (total_w - gap) // 2)
            right_margin = s(24, minimum=16)
            right_x = rect.right - right_margin - each_w
            left_x = right_x - gap - each_w

            primary_rect = pygame.Rect(left_x, rect.centery - panel_h // 2, each_w, panel_h)
            secondary_rect = pygame.Rect(right_x, rect.centery - panel_h // 2, each_w, panel_h)

            is_primary_active = selected and self._gamepad_bind_slot == 'primary'
            is_secondary_active = selected and self._gamepad_bind_slot == 'secondary'
            if self._waiting_for_key and self._pending_keybind_item == item:
                is_primary_active = self._pending_keybind_slot != 'secondary'
                is_secondary_active = self._pending_keybind_slot == 'secondary'

            self._draw_gamepad_binding_slot(primary_rect, primary_display, is_primary_active)
            self._draw_gamepad_binding_slot(secondary_rect, secondary_display, is_secondary_active)

            return {'primary': primary_rect, 'secondary': secondary_rect}

        value_text, value_color = self._get_display_value(item)

        arrow_font = self._font(18, bold=True, minimum=12)
        arrow_color = (80, 160, 255) if selected else (100, 120, 150)

        val_font = self._fit_font(value_text, 20, s(180, minimum=120), bold=True, minimum=11)
        val_surf = val_font.render(value_text, True, value_color)

        total_w = val_surf.get_width() + s(50, minimum=34)
        cx = rect.right - s(30, minimum=20) - total_w // 2

        left_arrow = arrow_font.render('<', True, arrow_color)
        right_arrow = arrow_font.render('>', True, arrow_color)

        la_rect = left_arrow.get_rect(center=(cx - val_surf.get_width() // 2 - s(16, minimum=10), rect.centery))
        ra_rect = right_arrow.get_rect(center=(cx + val_surf.get_width() // 2 + s(16, minimum=10), rect.centery))
        self.screen.blit(left_arrow, la_rect)
        self.screen.blit(val_surf, val_surf.get_rect(center=(cx, rect.centery)))
        self.screen.blit(right_arrow, ra_rect)
        # Hit zone'ları büyüt, kolay tıklanabilir olsun
        la_hit = la_rect.inflate(s(20, minimum=14), rect.height)
        ra_hit = ra_rect.inflate(s(20, minimum=14), rect.height)
        return {'left_rect': la_hit, 'right_rect': ra_hit}

    def _draw_submenu_arrow(self, rect: pygame.Rect, selected: bool) -> None:
        """Submenu tipi ayar için > oku."""
        arrow_font = self._font(22, bold=True, minimum=14)
        color = (80, 160, 255) if selected else (100, 120, 150)
        arrow = arrow_font.render('>', True, color)
        self.screen.blit(arrow, arrow.get_rect(center=(rect.right - self._s(28, minimum=20), rect.centery)))

    def _draw_vsync_prompt(self) -> None:
        """VSync restart gerekliliği popup'ı."""
        s = self._s
        self._apply_responsive_metrics()
        width, height = self.screen.get_size()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        panel_w = min(s(580, minimum=420), width - s(120, minimum=84))
        panel_h = s(200, minimum=170)
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        retro_style.draw_panel(self.screen, panel_rect, title=_t('vsync_changed', 'VSync Değişti'))

        lang = get_language()
        msg_lines = [
            _t('vsync_restart_msg1', 'VSync değişikliği yeniden başlatma gerektirir.' if lang == 'tr' else 'VSync change requires restart.'),
            _t('vsync_restart_msg2', 'Şimdi yeniden başlatmak ister misiniz?' if lang == 'tr' else 'Would you like to restart now?'),
        ]
        font = self._font(20, minimum=13)
        y = panel_rect.y + s(60, minimum=44)
        for line in msg_lines:
            surf = font.render(line, True, (220, 230, 245))
            self.screen.blit(surf, surf.get_rect(center=(panel_rect.centerx, y)))
            y += s(28, minimum=20)

        btn_h = s(48, minimum=38)
        btn_gap = s(16, minimum=12)
        side_pad = s(30, minimum=20)
        btn_w = (panel_w - side_pad * 2 - btn_gap) // 2
        btn_y = panel_rect.bottom - btn_h - s(20, minimum=14)
        btn1 = pygame.Rect(panel_rect.x + side_pad, btn_y, btn_w, btn_h)
        btn2 = pygame.Rect(btn1.right + btn_gap, btn_y, btn_w, btn_h)
        self._vsync_prompt_buttons = [btn1, btn2]

        restart_text = _t('restart_now', 'Şimdi Yeniden Başlat' if lang == 'tr' else 'Restart Now')
        later_text = _t('later', 'Sonra' if lang == 'tr' else 'Later')
        retro_style.draw_button(self.screen, btn1, restart_text, selected=self._vsync_prompt_choice == 0)
        retro_style.draw_button(self.screen, btn2, later_text, selected=self._vsync_prompt_choice == 1)

    def _draw_display_mode_confirm_panel(self) -> None:
        s = self._s
        self._apply_responsive_metrics()
        width, height = self.screen.get_size()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_w = min(s(620, minimum=460), max(s(420, minimum=340), width - s(120, minimum=84)))
        panel_h = s(210, minimum=180)
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)

        try:
            retro_style.draw_glass_panel(self.screen, panel_rect, alpha=220)
        except Exception:
            pygame.draw.rect(self.screen, (24, 32, 56), panel_rect, border_radius=s(12, minimum=8))
            pygame.draw.rect(self.screen, (140, 170, 220), panel_rect, s(2, minimum=1), border_radius=s(12, minimum=8))

        btn_h = s(48, minimum=38)
        btn_gap = s(16, minimum=12)
        side_pad = s(30, minimum=20)
        btn_w = (panel_w - side_pad * 2 - btn_gap) // 2
        btn_y = panel_rect.bottom - btn_h - s(20, minimum=14)
        yes_btn = pygame.Rect(panel_rect.x + side_pad, btn_y, btn_w, btn_h)
        no_btn = pygame.Rect(yes_btn.right + btn_gap, btn_y, btn_w, btn_h)

        self._display_mode_confirm_yes_rect = yes_btn
        self._display_mode_confirm_no_rect = no_btn

        try:
            retro_style.draw_button(self.screen, yes_btn, _t('yes', 'Evet'))
            retro_style.draw_button(self.screen, no_btn, _t('no', 'Hayır'))
        except Exception:
            pygame.draw.rect(self.screen, (72, 152, 92), yes_btn, border_radius=s(10, minimum=8))
            pygame.draw.rect(self.screen, (166, 88, 88), no_btn, border_radius=s(10, minimum=8))

    def _draw_campaign_phase_select_overlay(self) -> None:
        """Kampanya faz seçici overlay panelini çiz."""
        metrics = self._campaign_phase_overlay_metrics()
        width, height = self.screen.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 145))
        self.screen.blit(dim, (0, 0))

        panel_rect = metrics['panel']
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=220,
            border_color=(100, 200, 255),
            glow=True,
        )

        title_font = self._font(26, bold=True, minimum=18)
        title_text = _t('campaign_phase_selector_title', 'Görev Modu – Dünya Seçimi')
        title_surf = title_font.render(title_text, True, (235, 245, 255))
        self.screen.blit(title_surf, (int(metrics['title_x']), int(metrics['title_y'])))

        phases = get_campaign_phase_entries()
        item_h = int(metrics['item_h'])
        gap = int(metrics['gap'])
        list_y = int(metrics['list_y'])
        item_x = int(metrics['item_x'])
        item_w = int(metrics['item_w'])
        self._campaign_phase_item_rects = []

        world_colors = {
            1: (80, 200, 120),
            2: (100, 180, 255),
            3: (255, 120, 60),
            4: (180, 130, 255),
            5: (255, 220, 80),
        }

        label_font = self._font(20, bold=True, minimum=13)
        sub_font = self._font(15, minimum=11)
        track_count_font = self._font(14, minimum=10)

        for i, (mode_key, world_num, label, level_range) in enumerate(phases):
            y = list_y + i * (item_h + gap)
            item_rect = pygame.Rect(item_x, y, item_w, item_h)
            self._campaign_phase_item_rects.append((item_rect, i))

            is_selected = i == self._campaign_phase_selected
            color = world_colors.get(world_num, (150, 170, 200))

            bg_surf = pygame.Surface(item_rect.size, pygame.SRCALPHA)
            bg_alpha = 90 if is_selected else 35
            bg_color = (*color, bg_alpha)
            pygame.draw.rect(bg_surf, bg_color, bg_surf.get_rect(), border_radius=self._s(12, minimum=8))
            self.screen.blit(bg_surf, item_rect.topleft)

            border_alpha = 255 if is_selected else 60
            border_color = (*color[:3],)
            if is_selected:
                selected_border = (
                    min(255, border_color[0] + 28),
                    min(255, border_color[1] + 28),
                    min(255, border_color[2] + 28),
                )
                pygame.draw.rect(self.screen, selected_border, item_rect, width=self._s(3, minimum=2), border_radius=self._s(12, minimum=8))
            else:
                border_surf = pygame.Surface(item_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(border_surf, (*border_color, border_alpha), border_surf.get_rect(), width=1, border_radius=self._s(12, minimum=8))
                self.screen.blit(border_surf, item_rect.topleft)

            indicator_rect = pygame.Rect(item_rect.x + self._s(8, minimum=6), item_rect.y + self._s(10, minimum=8), self._s(4, minimum=3), item_rect.height - self._s(20, minimum=16))
            pygame.draw.rect(self.screen, color, indicator_rect, border_radius=max(2, indicator_rect.width // 2))

            text_color = (255, 255, 255) if is_selected else (210, 220, 235)
            label_surf = label_font.render(label, True, text_color)
            self.screen.blit(label_surf, (item_rect.x + self._s(22, minimum=16), item_rect.y + self._s(12, minimum=8)))

            range_surf = sub_font.render(level_range, True, (160, 175, 200))
            self.screen.blit(range_surf, (item_rect.x + self._s(22, minimum=16), item_rect.y + self._s(40, minimum=28)))

            try:
                playlist = self.settings_manager.get_mode_music_playlist(mode_key)
                count = len(playlist) if playlist else 0
            except Exception:
                count = 0
            if count > 0:
                count_text = f"{count} {_t('track_count_unit', 'parça')}"
                count_color = (150, 220, 255)
            else:
                count_text = _t('track_default_label', 'Varsayılan (Oyun İçi)')
                count_color = (120, 140, 170)
            count_surf = track_count_font.render(count_text, True, count_color)
            self.screen.blit(count_surf, (item_rect.right - count_surf.get_width() - self._s(16, minimum=12), item_rect.y + (item_h - count_surf.get_height()) // 2))

    def _draw_mode_playlist_edit_overlay(self) -> None:
        metrics = self._playlist_overlay_metrics()
        width, height = self.screen.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 145))
        self.screen.blit(dim, (0, 0))

        panel_rect = metrics['panel']
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=215,
            border_color=retro_style.primary,
            glow=True,
        )

        title_font = self._font(28, bold=True, minimum=18)
        subtitle_font = self._font(18, minimum=12)
        title = title_font.render(_t('mode_music_playlist_editor', 'Bölüm Müzikleri'), True, (235, 245, 255))
        self.screen.blit(title, (int(metrics['title_x']), int(metrics['title_y'])))

        mode_key = self._playlist_edit_mode_key or ''
        mode_name = str(mode_key)
        for mk, label in get_mode_music_entries():
            if mk == mode_key:
                mode_name = str(label)
                break
        if mode_key.startswith('campaign_world'):
            for mk, _wn, label, _lr in get_campaign_phase_entries():
                if mk == mode_key:
                    mode_name = str(label)
                    break
        subtitle = subtitle_font.render(mode_name, True, (170, 190, 220))
        self.screen.blit(subtitle, (int(metrics['title_x']), int(metrics['subtitle_y'])))

        list_rect = metrics['list_rect']
        item_h = int(metrics['item_h'])
        gap = int(metrics['gap'])
        total_items = len(self._playlist_edit_items) + 1

        max_scroll = self._playlist_list_max_scroll(total_items, item_h, gap, list_rect.height)
        self._playlist_edit_scroll = max(0, min(self._playlist_edit_scroll, max_scroll))

        self._playlist_edit_item_rects = []
        self.screen.set_clip(list_rect)
        for idx in range(total_items):
            y = list_rect.y + idx * (item_h + gap) - self._playlist_edit_scroll
            if y + item_h < list_rect.y or y > list_rect.bottom:
                continue

            rect = pygame.Rect(list_rect.x, y, list_rect.width, item_h)
            self._playlist_edit_item_rects.append((rect, idx))

            if idx == self._playlist_edit_selected:
                glow_pad_x = self._s(6, minimum=4)
                glow_pad_y = self._s(4, minimum=2)
                glow_rect = rect.inflate(glow_pad_x, glow_pad_y)
                glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow, (120, 220, 255, 52), glow.get_rect(), border_radius=self._s(12, minimum=8))
                self.screen.blit(glow, glow_rect.topleft)

            text = '+ Ekle' if idx == 0 else self._track_label_for_value(self._playlist_edit_items[idx - 1])
            retro_style.draw_uniform_button(
                self.screen,
                rect,
                text,
                color_code=retro_style.primary,
                selected=(idx == self._playlist_edit_selected),
            )

            if idx == self._playlist_edit_selected:
                pygame.draw.rect(
                    self.screen,
                    (160, 240, 255),
                    rect,
                    width=self._s(2, minimum=1),
                    border_radius=self._s(12, minimum=8),
                )
        self.screen.set_clip(None)

        total_h = total_items * (item_h + gap)
        if total_h > list_rect.height:
            retro_style.draw_scrollbar(self.screen, metrics['scrollbar_rect'], self._playlist_edit_scroll, total_h, list_rect.height)

        action_rects = self._playlist_bulk_action_rects(metrics)
        selectable_tracks = self._playlist_selectable_track_values()
        action_defs = [
            ('clear', _t('playlist_clear', 'Temizle'), bool(self._playlist_edit_items)),
            ('reset_default', _t('playlist_reset_default', 'Varsayılana Dön'), bool(self._playlist_edit_items)),
            ('select_all', _t('playlist_select_all', 'Tümünü Seç'), bool(selectable_tracks)),
        ]
        for action_key, action_label, enabled in action_defs:
            action_rect = action_rects.get(action_key)
            if action_rect is None:
                continue
            retro_style.draw_uniform_button(
                self.screen,
                action_rect,
                action_label,
                color_code=retro_style.primary,
                selected=False,
            )
            if not enabled:
                disabled_surf = pygame.Surface(action_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(disabled_surf, (10, 18, 34, 155), disabled_surf.get_rect(), border_radius=self._s(12, minimum=8))
                self.screen.blit(disabled_surf, action_rect.topleft)

        if not self._playlist_edit_picker_open:
            return

        picker_dim = pygame.Surface((width, height), pygame.SRCALPHA)
        picker_dim.fill((0, 0, 0, 95))
        self.screen.blit(picker_dim, (0, 0))

        picker_rect = metrics['picker']
        retro_style.draw_glass_panel(
            self.screen,
            picker_rect,
            alpha=220,
            border_color=retro_style.primary,
            glow=True,
        )

        picker_title = title_font.render(t('tracks'), True, (235, 245, 255))
        self.screen.blit(picker_title, (int(metrics['picker_title_x']), int(metrics['picker_title_y'])))

        picker_list_rect = metrics['picker_list_rect']
        p_item_h = int(metrics['picker_item_h'])
        p_gap = int(metrics['picker_gap'])

        self._playlist_edit_picker_scroll = max(0, min(self._playlist_edit_picker_scroll, self._picker_max_scroll(picker_list_rect.height, p_item_h, p_gap)))

        self._playlist_edit_picker_rects = []
        self.screen.set_clip(picker_list_rect)
        for idx, option in enumerate(self._track_options):
            y = picker_list_rect.y + idx * (p_item_h + p_gap) - self._playlist_edit_picker_scroll
            if y + p_item_h < picker_list_rect.y or y > picker_list_rect.bottom:
                continue

            rect = pygame.Rect(picker_list_rect.x, y, picker_list_rect.width, p_item_h)
            self._playlist_edit_picker_rects.append((rect, idx))

            label = str(option.get('label', ''))
            retro_style.draw_uniform_button(
                self.screen,
                rect,
                label,
                color_code=retro_style.primary,
                selected=(idx == self._playlist_edit_picker_selected),
            )
        self.screen.set_clip(None)

        picker_total_h = len(self._track_options) * (p_item_h + p_gap)
        if picker_total_h > picker_list_rect.height:
            retro_style.draw_scrollbar(
                self.screen,
                metrics['picker_scrollbar_rect'],
                self._playlist_edit_picker_scroll,
                picker_total_h,
                picker_list_rect.height,
            )
