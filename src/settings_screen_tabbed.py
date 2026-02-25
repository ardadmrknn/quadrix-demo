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
from platform_utils import is_fullscreen_toggle, normalize_mouse_pos
from background_effects import get_shared_falling_blocks_layer
from localization import (
    t, get_text, get_language, set_language, get_language_name,
    SUPPORTED_LANGUAGES, get_all_languages,
)
from ui_language_profile import apply_language_ui_profile, get_font_for_language
from menu import get_control_actions, get_mode_music_entries, BUILT_IN_TRACK_CHOICES, SUPPORTED_MUSIC_EXTENSIONS
from gamepad_manager import get_gamepad_manager, reload_gamepad_settings


# ---------------------------------------------------------------------------
# Yardımcı: Lokalizasyon kısa yolu – key yoksa fallback döndürür
# ---------------------------------------------------------------------------
def _t(key: str, fallback: str = '') -> str:
    """t() wrapper – çeviri bulunamazsa fallback döndürür."""
    val = t(key)
    if val == key and fallback:
        return fallback
    return val


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
            'label_tr': 'DAS Gecikmesi', 'label_en': 'DAS Delay',
            'min': 50, 'max': 300, 'step': 10, 'suffix': 'ms',
        })
        items.append({
            'type': 'slider', 'key': 'das_repeat',
            'loc_key': 'settings_das_repeat',
            'label_tr': 'DAS Tekrar', 'label_en': 'DAS Repeat',
            'min': 10, 'max': 500, 'step': 5, 'suffix': 'ms',
        })
        items.append({
            'type': 'slider', 'key': 'soft_drop_speed',
            'loc_key': 'settings_soft_drop_speed',
            'label_tr': 'Yumuşak Düşme Hızı', 'label_en': 'Soft Drop Speed',
            'min': 20, 'max': 100, 'step': 5, 'suffix': 'ms',
        })

    elif tab_key == 'display':
        items.append({'type': 'section', 'loc_key': 'settings_section_screen', 'label_tr': 'EKRAN', 'label_en': 'SCREEN'})
        items.append({
            'type': 'selector', 'key': 'fullscreen',
            'loc_key': 'window_mode',
            'label_tr': 'Pencere Modu', 'label_en': 'Window Mode',
        })
        items.append({
            'type': 'selector', 'key': 'resolution',
            'loc_key': 'resolution',
            'label_tr': 'Çözünürlük', 'label_en': 'Resolution',
        })
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

        items.append({'type': 'section', 'loc_key': 'settings_section_visual', 'label_tr': 'GÖRSEL', 'label_en': 'VISUAL'})
        items.append({
            'type': 'toggle', 'key': 'show_fps',
            'loc_key': 'show_fps',
            'label_tr': 'FPS Göster', 'label_en': 'Show FPS',
        })
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
            'type': 'slider', 'key': 'menu_transparency',
            'loc_key': 'menu_transparency',
            'label_tr': 'Menü Şeffaflığı', 'label_en': 'Menu Transparency',
            'min': 0.0, 'max': 1.0, 'step': 0.1, 'suffix': '%', 'percent': True,
        })
        items.append({
            'type': 'toggle', 'key': 'particle_effects',
            'loc_key': 'particle_effects',
            'label_tr': 'Parçacık Efektleri', 'label_en': 'Particle Effects',
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

        gamepad_actions = [
            ('hard_drop', _t('gp_hard_drop', 'Anında bırak')),
            ('hold', _t('gp_hold', 'Hold / Değiştir')),
            ('hold2', _t('gp_hold2', 'İkincil Hold')),
            ('pause', _t('gp_pause', 'Duraklat')),
            ('main_menu_prompt', _t('gp_main_menu_prompt', 'Ana Menü Onayı')),
            ('discard_held', _t('gp_discard_held', 'Tutulanı At')),
            ('lt', _t('gp_lt', 'Sol Tetik')),
            ('rt', _t('gp_rt', 'Sağ Tetik')),
            ('menu_confirm', _t('gp_menu_confirm', 'Menü Onay')),
            ('menu_back', _t('gp_menu_back', 'Menü Geri')),
            ('menu_tab_next', _t('gp_menu_tab_next', 'Sekme Sonraki')),
            ('menu_tab_prev', _t('gp_menu_tab_prev', 'Sekme Önceki')),
            ('card_rewind', _t('gp_card_rewind', 'Kart: Rewind')),
            ('card_sniper', _t('gp_card_sniper', 'Kart: Sniper')),
            ('card_time_capsule_save', _t('gp_card_time_capsule_save', 'Kart: Time Capsule Kaydet')),
            ('card_time_capsule_restore', _t('gp_card_time_capsule_restore', 'Kart: Time Capsule Yükle')),
            ('card_phase_shift', _t('gp_card_phase_shift', 'Kart: Phase Shift')),
            ('card_ghost', _t('gp_card_ghost', 'Kart: Ghost')),
            ('card_hammer', _t('gp_card_hammer', 'Kart: Hammer')),
            ('card_bomb', _t('gp_card_bomb', 'Kart: Bomb')),
        ]
        items.append({'type': 'section', 'loc_key': 'tab_gamepad', 'label_tr': 'GAMEPAD', 'label_en': 'GAMEPAD'})
        for action_key, label in gamepad_actions:
            items.append({
                'type': 'keybind', 'key': f'ctrl_gp_{action_key}',
                'action_key': action_key, 'section': 'gamepad',
                'label_tr': label, 'label_en': label,
            })

    elif tab_key == 'customize':
        items.append({'type': 'section', 'loc_key': 'theme', 'label_tr': 'TEMA', 'label_en': 'THEME'})
        items.append({
            'type': 'selector', 'key': 'theme',
            'loc_key': 'theme',
            'label_tr': 'Tema Seçimi', 'label_en': 'Theme',
        })
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

    RESOLUTIONS = ['auto', '800x600', '1024x768', '1280x720', '1366x768', '1920x1080']
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

        # Font'lar
        self._refresh_fonts()

        # Tüm ayar değerlerini settings_manager'dan yükle
        self._load_all_settings()

        # Sekme içeriklerini oluştur
        self._rebuild_tab_content()

        # Smooth slider animasyonları
        self._anim_last_tick = pygame.time.get_ticks()
        self._music_volume_vis = float(self.music_volume)
        self._sfx_volume_vis = float(self.sfx_volume)

        # Tab rect'leri (mouse için)
        self._tab_rects: list[pygame.Rect] = []

        # VSync restart prompt
        self._vsync_prompt_active = False
        self._vsync_prompt_choice = 0
        self._vsync_prompt_buttons: list[pygame.Rect] = []

        # Grafik ayarları – ilk değerleri hatırla
        self._initial_fullscreen = self.fullscreen
        self._initial_resolution = self.resolution

        # SettingsScreen uyumluluk alanları (main.py bunlara erişiyor)
        self.music_enabled = self.settings_manager.get('music_enabled', True)
        self.sound_enabled = self.settings_manager.get('sound_enabled', True)
        self.effects_enabled = self.settings_manager.get('effects_enabled', True)
        self.background_enabled = self.settings_manager.get('background_enabled', True)
        self.menu_music = self.settings_manager.get('menu_music', 'Mainv3')
        self.game_music = self.settings_manager.get('game_music', 'klasik0')
        self.mute_all = self.settings_manager.get('mute_all', False)
        self.debug_mode = self.settings_manager.get('debug_mode', False)
        self.card_mode_debug = self.settings_manager.get('card_mode_debug', False)
        self.difficulty = 'Normal'
        self.custom_background = self.settings_manager.get('custom_background', None)
        self._show_debug_settings = bool(self.settings_manager.get('show_debug_settings', False))
        self.current_language = self.settings_manager.get('language', 'tr')

        # ── Kontrol tuş bağlama (keybind) durumu ──
        self._control_config = self.settings_manager.get_controls()
        self._waiting_for_key = False
        self._pending_keybind_item = None  # keybind item dict'i
        self._pending_keybind_slot = 'primary'
        self._single_player_bind_slot = 'primary'
        self._gamepad_bind_slot = 'primary'
        self._swallow_next_keydown = False
        self._keybind_slot_rects: list[dict | None] = []

        # ── Müzik modu seçicileri (music_selector) ──
        self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()
        self._music_root = Path(__file__).resolve().parent.parent / 'music'
        self._track_options = self._build_track_options()
        self._music_picker_open = False
        self._music_picker_mode_key = None
        self._music_picker_selected = 0
        self._music_picker_scroll = 0
        self._music_picker_item_rects: list[tuple[pygame.Rect, int]] = []

        # Close button rect
        self._close_btn_rect: pygame.Rect | None = None

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
        self.fullscreen = sm.get('fullscreen', True)
        self.resolution = sm.get('resolution', 'auto')
        self.vsync = sm.get('vsync', True)
        self.fps_limit = sm.get('fps_limit', 0)
        self.show_fps = sm.get('show_fps', False)
        self.show_ghost = sm.get('show_ghost', True)
        self.background_enabled = sm.get('background_enabled', True)
        self.bg_transparency = sm.get('bg_transparency', 0.3)
        self.menu_transparency = sm.get('menu_transparency', 1.0)
        self.particle_effects = sm.get('particle_effects', True)
        # Audio
        self.music_enabled = sm.get('music_enabled', True)
        self.music_volume = sm.get('music_volume', 0.3)
        self.sound_enabled = sm.get('sound_enabled', True)
        self.sfx_volume = sm.get('sfx_volume', 0.5)
        self.mute_all = sm.get('mute_all', False)
        # Other
        self.current_language = sm.get('language', 'tr')
        self.debug_mode = sm.get('debug_mode', False)
        self.card_mode_debug = sm.get('card_mode_debug', False)
        self._show_debug_settings = bool(sm.get('show_debug_settings', False))

    def _refresh_fonts(self) -> None:
        self.font_title = retro_style.get_font(36)
        self.font_tab = retro_style.get_font(20, bold=True)
        self.font_section = retro_style.get_font(20, bold=True)
        self.font_label = retro_style.get_font(24, bold=True)
        self.font_value = retro_style.get_font(22, bold=True)
        self.font_small = retro_style.get_font(18, bold=False)
        self.font_hint = retro_style.get_font(16, bold=False)

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
        show_debug = bool(self.settings_manager.get('show_debug_settings', False))
        if show_debug != self._show_debug_settings:
            self._show_debug_settings = show_debug
            self._rebuild_tab_content()

    # ------------------------------------------------------------------
    # Değer okuma / yazma
    # ------------------------------------------------------------------

    def _get_value(self, key: str):
        """Ayar değerini döndür."""
        return getattr(self, key, self.settings_manager.get(key))

    def _set_value(self, key: str, value) -> None:
        """Ayar değerini güncelle ve kaydet."""
        setattr(self, key, value)
        self.settings_manager.set(key, value)

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
            if item.get('percent'):
                text = f'{int(float(val) * 100)}%'
            else:
                text = f'{int(val)} {item.get("suffix", "")}'.strip()
            return text, (200, 220, 255)

        elif itype == 'selector':
            if key == 'fullscreen':
                fs = self._get_value('fullscreen')
                if fs:
                    text = _t('fullscreen', 'Tam Ekran' if lang == 'tr' else 'Fullscreen')
                else:
                    text = _t('windowed', 'Pencereli' if lang == 'tr' else 'Windowed')
                return text, (200, 220, 255)
            elif key == 'resolution':
                if self.fullscreen:
                    na = _t('not_available_short', 'N/A')
                    return na, (120, 120, 140)
                res = self._get_value('resolution')
                if res == 'auto':
                    return _t('automatic', 'Otomatik' if lang == 'tr' else 'Auto'), (200, 220, 255)
                return str(res), (200, 220, 255)
            elif key == 'fps_limit':
                limit = int(self._get_value('fps_limit') or 0)
                text = 'MAX' if limit <= 0 else str(limit)
                return text, (200, 220, 255)
            elif key == 'theme':
                name = getattr(self.theme_manager, 'theme_name', '') if self.theme_manager else ''
                return str(name), (255, 200, 100)
            elif key == 'language':
                lang_name = get_language_name(self.current_language)
                return str(lang_name), (100, 255, 200)
            return '', (200, 200, 200)

        elif itype == 'submenu':
            return '', (150, 170, 200)

        elif itype == 'music_selector':
            mode_key = item.get('mode_key')
            current = self._mode_music_overrides.get(mode_key)
            for option in self._track_options:
                if option.get('value') == current:
                    return str(option.get('label', '')), (150, 220, 255)
            if current:
                if str(current).startswith('file:'):
                    raw_path = str(current)[5:]
                    stem = Path(raw_path).stem
                    display_name = _latinize_track_display_name(stem)
                    return f"{display_name} {t('track_file_suffix')}", (150, 220, 255)
                return str(current), (150, 220, 255)
            return t('track_default_label'), (150, 220, 255)

        elif itype == 'keybind':
            section = item.get('section')
            action_key = item.get('action_key')

            if self._waiting_for_key and self._pending_keybind_item == item:
                if section == 'gamepad':
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

            if section == 'gamepad':
                primary, secondary = self._get_gamepad_binding_slots(action_key)
                ptxt = self._format_gamepad_button_label(primary)
                stxt = self._format_gamepad_button_label(secondary)
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

    def _start_keybind_capture(self, item: dict, slot: str = 'primary') -> None:
        self._waiting_for_key = True
        self._pending_keybind_item = item
        self._pending_keybind_slot = slot

    def _persist_controls(self) -> None:
        self.settings_manager.set('controls', self._control_config)
        self._control_config = self.settings_manager.get_controls()
        try:
            reload_gamepad_settings()
        except Exception:
            pass

    def _format_gamepad_button_label(self, value) -> str:
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
            return str(gpm.get_button_index_label(btn_index))
        except Exception:
            return f'Btn{btn_index}'

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
        if self._pending_keybind_item.get('section') != 'gamepad':
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
        elif section == 'gamepad':
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

    def _picker_max_scroll(self, visible_h: int, item_h: int, gap: int) -> int:
        total_h = len(self._track_options) * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _picker_ensure_visible(self, visible_h: int, item_h: int, gap: int) -> None:
        y = self._music_picker_selected * (item_h + gap)
        if y < self._music_picker_scroll:
            self._music_picker_scroll = y
        elif y > self._music_picker_scroll + visible_h - item_h:
            self._music_picker_scroll = y - (visible_h - item_h)
        self._music_picker_scroll = max(0, min(self._music_picker_scroll, self._picker_max_scroll(visible_h, item_h, gap)))

    def _handle_music_picker_input(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_music_picker()
                return
            if event.key == pygame.K_UP:
                self._music_picker_selected = (self._music_picker_selected - 1) % len(self._track_options)
                return
            if event.key == pygame.K_DOWN:
                self._music_picker_selected = (self._music_picker_selected + 1) % len(self._track_options)
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._music_picker_mode_key is not None:
                    chosen = self._track_options[self._music_picker_selected].get('value')
                    self.settings_manager.set_mode_music_override(self._music_picker_mode_key, chosen)
                    self._mode_music_overrides = self.settings_manager.get_mode_music_overrides()
                self._close_music_picker()
                return

        elif event.type == pygame.MOUSEWHEEL:
            self._music_picker_scroll -= event.y * 36
            self._music_picker_scroll = max(0, self._music_picker_scroll)
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
            'show_fps': None,
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
        elif key == 'sfx_volume':
            self.sfx_volume = new_val
            return 'change_sfx_volume'
        elif key == 'bg_transparency':
            self.bg_transparency = new_val
            return 'change_bg_transparency'
        elif key == 'menu_transparency':
            self.menu_transparency = new_val
            return 'change_menu_transparency'
        return None

    def _cycle_selector(self, key: str, delta: int) -> str | None:
        """Selector type ayarı döngüsel değiştir."""
        if key == 'fullscreen':
            self.fullscreen = not self.fullscreen
            self._set_value('fullscreen', self.fullscreen)
            return 'apply_display_mode'
        elif key == 'resolution':
            if self.fullscreen:
                return None
            idx = 0
            if self.resolution in self.RESOLUTIONS:
                idx = self.RESOLUTIONS.index(self.resolution)
            idx = (idx + delta) % len(self.RESOLUTIONS)
            self.resolution = self.RESOLUTIONS[idx]
            self._set_value('resolution', self.resolution)
            if not self.fullscreen:
                return 'apply_display_mode'
        elif key == 'fps_limit':
            current = int(self.fps_limit or 0)
            if current not in self.FPS_LIMITS:
                current = 0
            idx = self.FPS_LIMITS.index(current)
            idx = (idx + delta) % len(self.FPS_LIMITS)
            self.fps_limit = self.FPS_LIMITS[idx]
            self._set_value('fps_limit', self.fps_limit)
        elif key == 'theme':
            if self.theme_manager is None:
                return None
            try:
                names = list(self.theme_manager.get_all_theme_names())
            except Exception:
                names = []
            if not names:
                return None
            current_name = getattr(self.theme_manager, 'theme_name', '')
            try:
                idx = names.index(current_name)
            except ValueError:
                idx = 0
            idx = (idx + delta) % len(names)
            self.theme_manager.set_theme(names[idx])
            self.settings_manager.set('theme', names[idx])
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
            self._refresh_fonts()
            self._set_value('language', self.current_language)
            self._rebuild_tab_content()
            return 'language_changed'
        return None

    # ------------------------------------------------------------------
    # Panel geometrisi
    # ------------------------------------------------------------------

    def _panel_rect(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        pw = min(1200, max(700, int(w * 0.88)))
        ph = min(850, max(500, int(h * 0.88)))
        px = (w - pw) // 2
        py = (h - ph) // 2
        return pygame.Rect(px, py, pw, ph)

    def _tab_bar_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.x, panel.y + 56, panel.width, 44)

    def _content_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            panel.x + 18, panel.y + 110,
            panel.width - 36, panel.height - 124,
        )

    # ------------------------------------------------------------------
    # Kaydırma sınırları
    # ------------------------------------------------------------------

    def _max_scroll(self, content_rect: pygame.Rect) -> int:
        row_h = 58
        section_h = 40
        total = 0
        for item in self._tab_items:
            total += section_h if item['type'] == 'section' else row_h
        return max(0, total - content_rect.height)

    # ------------------------------------------------------------------
    # Input işleme
    # ------------------------------------------------------------------

    def handle_input(self, event) -> str | None:
        """Girdileri işle. Uyumlu action string döndür."""
        if self._swallow_next_keydown and event.type == pygame.KEYDOWN:
            self._swallow_next_keydown = False
            return None

        if self._music_picker_open:
            self._handle_music_picker_input(event)
            return None

        if self._waiting_for_key:
            pending_section = self._pending_keybind_item.get('section') if self._pending_keybind_item else None

            if pending_section == 'gamepad':
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    return None
                if event.type == pygame.JOYBUTTONDOWN:
                    self._apply_captured_gamepad_button(event.button)
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    self._swallow_next_keydown = True
                    return None
                if event.type == pygame.JOYAXISMOTION and event.axis in (4, 5):
                    trigger_val = (event.value + 1.0) / 2.0
                    if trigger_val >= 0.5:
                        trigger_index = 100 if event.axis == 4 else 101
                        self._apply_captured_gamepad_button(trigger_index)
                        self._waiting_for_key = False
                        self._pending_keybind_item = None
                        self._pending_keybind_slot = 'primary'
                        self._swallow_next_keydown = True
                    return None
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._waiting_for_key = False
                    self._pending_keybind_item = None
                    self._pending_keybind_slot = 'primary'
                    return None
                self._apply_captured_key(event.key)
                self._waiting_for_key = False
                self._pending_keybind_item = None
                self._pending_keybind_slot = 'primary'
            return None

        # VSync restart prompt
        if self._vsync_prompt_active:
            return self._handle_vsync_prompt(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
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

            if getattr(event, 'from_gamepad', False) and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._switch_tab(-1 if event.key == pygame.K_LEFT else 1)
                return None

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
                return self._handle_setting_action(event.key)

            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._reset_selected_keybind_to_default()
                return None

            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

        # Mouse tekerleği
        elif event.type == pygame.MOUSEWHEEL:
            panel = self._panel_rect()
            content = self._content_rect(panel)
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll(content)))

        # Mouse hareket
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Tab hover
            for i, rect in enumerate(self._tab_rects):
                if rect.collidepoint(pos):
                    pass  # Tab'a tıklama gerekiyor, hover yok
            # Satır hover
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(pos):
                    self.selected = i

        # Mouse tıklama
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos

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
                                self._start_keybind_capture(item, slot=slot)
                                return None
                            if section == 'gamepad':
                                slot_rects = self._keybind_slot_rects[i] if i < len(self._keybind_slot_rects) else None
                                if isinstance(slot_rects, dict):
                                    primary_rect = slot_rects.get('primary')
                                    secondary_rect = slot_rects.get('secondary')
                                    if secondary_rect is not None and secondary_rect.collidepoint(pos):
                                        self._gamepad_bind_slot = 'secondary'
                                    elif primary_rect is not None and primary_rect.collidepoint(pos):
                                        self._gamepad_bind_slot = 'primary'
                                    else:
                                        return None
                                self._start_keybind_capture(item, slot=self._gamepad_bind_slot)
                                return None
                    return self._handle_setting_action(pygame.K_RETURN)

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
            if key_code == pygame.K_LEFT:
                self._cycle_mode_music(mode_key, -1)
            elif key_code == pygame.K_RIGHT:
                self._cycle_mode_music(mode_key, 1)
            elif key_code in (pygame.K_RETURN, pygame.K_SPACE):
                self._open_music_picker(mode_key)
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

            if section == 'gamepad':
                if key_code == pygame.K_LEFT:
                    self._gamepad_bind_slot = 'primary'
                    return None
                if key_code == pygame.K_RIGHT:
                    self._gamepad_bind_slot = 'secondary'
                    return None
                if key_code in (pygame.K_RETURN, pygame.K_SPACE):
                    self._start_keybind_capture(item, slot=self._gamepad_bind_slot)
                return None

            if key_code in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                self._start_keybind_capture(item, slot='primary')
            return None

        return None

    def _ensure_visible(self) -> None:
        """Seçili öğenin görünür olmasını sağla."""
        if not self._selectable_indices or self.selected >= len(self._selectable_indices):
            return
        panel = self._panel_rect()
        content = self._content_rect(panel)
        row_h = 58
        section_h = 40

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

    # ------------------------------------------------------------------
    # Update (animasyonlar)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        pass  # draw() içinde dt hesaplanıyor

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------

    def draw(self) -> None:
        width, height = self.screen.get_size()

        # Smooth slider animasyonları
        now_ms = pygame.time.get_ticks()
        dt = (now_ms - self._anim_last_tick) / 1000.0
        self._anim_last_tick = now_ms
        dt = max(0.0, min(0.05, dt))
        speed = 18.0
        self._music_volume_vis += (self.music_volume - self._music_volume_vis) * min(1.0, dt * speed)
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

    def _draw_panel(self, rect: pygame.Rect) -> None:
        """Koyu yarı-saydam panel arka planı."""
        # Gölge
        shadow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 60), shadow.get_rect(), border_radius=16)
        self.screen.blit(shadow, (rect.x + 5, rect.y + 5))

        # Ana panel
        panel_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel_surf.fill((12, 16, 32, 235))
        # Üst kenar highlight
        for y in range(min(30, rect.height // 4)):
            alpha = int(15 * (1 - y / 30))
            pygame.draw.line(panel_surf, (255, 255, 255, alpha), (0, y), (rect.width, y))
        self.screen.blit(panel_surf, rect.topleft)

        # Kenar çizgisi
        pygame.draw.rect(self.screen, (60, 70, 100), rect, 2, border_radius=14)

        # Üst kenar vurgulu çizgi
        pygame.draw.line(
            self.screen, (80, 140, 220),
            (rect.x + 2, rect.y + 1), (rect.right - 2, rect.y + 1), 1,
        )

    def _draw_title(self, panel: pygame.Rect) -> None:
        """Başlık ve kapatma butonu."""
        lang = get_language()
        title_text = _t('panel_settings', 'AYARLAR' if lang == 'tr' else 'SETTINGS')
        title_surf = self.font_title.render(title_text, True, (220, 235, 255))
        self.screen.blit(title_surf, (panel.x + 20, panel.y + 10))
        self._close_btn_rect = None

        # Başlık altı çizgi
        line_y = panel.y + 48
        pygame.draw.line(self.screen, (50, 60, 90), (panel.x + 10, line_y), (panel.right - 10, line_y), 1)

    def _draw_tab_bar(self, bar_rect: pygame.Rect) -> None:
        """Sekme çubuğunu çiz."""
        self._tab_rects = []
        num_tabs = len(TAB_DEFS)
        tab_gap = 6
        total_gap = tab_gap * (num_tabs - 1)
        available_w = bar_rect.width - 20
        tab_w = (available_w - total_gap) // num_tabs

        for i, tab_def in enumerate(TAB_DEFS):
            tx = bar_rect.x + 10 + i * (tab_w + tab_gap)
            tab_rect = pygame.Rect(tx, bar_rect.y, tab_w, bar_rect.height)
            self._tab_rects.append(tab_rect)

            is_active = (i == self.current_tab)
            label = _tab_label(tab_def)

            # Tab arka planı
            tab_surf = pygame.Surface(tab_rect.size, pygame.SRCALPHA)
            if is_active:
                tab_surf.fill((35, 55, 90, 220))
            else:
                tab_surf.fill((20, 28, 48, 160))
            self.screen.blit(tab_surf, tab_rect.topleft)

            # Alt çizgi (aktif sekme)
            if is_active:
                indicator_rect = pygame.Rect(tab_rect.x, tab_rect.bottom - 3, tab_rect.width, 3)
                pygame.draw.rect(self.screen, (80, 180, 255), indicator_rect)

            # Tab metni
            color = (255, 255, 255) if is_active else (140, 155, 180)
            tab_font = retro_style.get_fitting_font(label, 18, tab_w - 10, bold=is_active)
            text_surf = tab_font.render(label, True, color)
            text_rect = text_surf.get_rect(center=tab_rect.center)
            self.screen.blit(text_surf, text_rect)

    def _draw_content(self, content_rect: pygame.Rect) -> None:
        """Mevcut sekmenin içeriğini çiz."""
        self.option_rects = []
        self._keybind_slot_rects = []
        row_h = 58
        section_h = 40
        sel_item_index = 0  # seçilebilir öğe sayacı

        # Clip area
        self.screen.set_clip(content_rect)

        y = content_rect.y - self.scroll_offset
        for i, item in enumerate(self._tab_items):
            itype = item['type']

            if itype == 'section':
                # Bölüm başlığı
                if y + section_h > content_rect.y - 20 and y < content_rect.bottom:
                    self._draw_section_header(content_rect.x, y, content_rect.width, section_h, item)
                y += section_h
                continue

            # Ayar satırı – sol/sağ padding artırıldı
            row_rect = pygame.Rect(content_rect.x + 8, y + 2, content_rect.width - 16, row_h - 6)

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

        # Scrollbar
        max_scroll = self._max_scroll(content_rect)
        if max_scroll > 0:
            total_h = 0
            for item in self._tab_items:
                total_h += section_h if item['type'] == 'section' else row_h
            sb_rect = pygame.Rect(
                content_rect.right - 6, content_rect.y,
                5, content_rect.height,
            )
            retro_style.draw_scrollbar(
                self.screen, sb_rect,
                self.scroll_offset, total_h, content_rect.height,
            )

    def _draw_section_header(
        self, x: int, y: int, w: int, h: int, item: dict,
    ) -> None:
        """Bölüm başlığını çiz (renkli, küçük font)."""
        label = _item_label(item)
        # Accent renkli metin
        color = (80, 200, 180)  # Teal/Cyan
        surf = self.font_section.render(label, True, color)
        self.screen.blit(surf, (x + 24, y + h - surf.get_height() - 4))
        # Alt çizgi
        line_y = y + h - 1
        pygame.draw.line(self.screen, (40, 55, 75), (x + 20, line_y), (x + w - 20, line_y), 1)

    def _draw_setting_item(
        self, rect: pygame.Rect, item: dict, selected: bool,
    ) -> dict | None:
        """Bir ayar satırını çiz."""
        itype = item['type']
        label = _item_label(item)

        # Arka plan (alternatif renkler, seçili vurgu)
        bg_alpha = 180 if selected else 130
        bg_color = (28, 38, 60) if selected else (18, 24, 42)
        row_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        row_surf.fill((*bg_color, bg_alpha))
        if selected:
            # Üst highlight
            for yy in range(min(8, rect.height // 4)):
                a = int(15 * (1 - yy / 8))
                pygame.draw.line(row_surf, (255, 255, 255, a), (0, yy), (rect.width, yy))
        self.screen.blit(row_surf, rect.topleft)

        # Kenar
        if selected:
            pygame.draw.rect(self.screen, (80, 160, 255, 180), rect, 1, border_radius=6)
        else:
            pygame.draw.rect(self.screen, (40, 50, 70), rect, 1, border_radius=6)

        # Label – sol padding artırıldı
        label_color = (255, 255, 255) if selected else (190, 200, 215)
        max_label_w = int(rect.width * 0.42)
        label_font = retro_style.get_fitting_font(label, 22, max_label_w, bold=True)
        label_surf = label_font.render(label, True, label_color)
        self.screen.blit(label_surf, (rect.x + 24, rect.centery - label_surf.get_height() // 2))

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

    def _draw_music_picker(self) -> None:
        width, height = self.screen.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))

        panel_w = min(880, width - 140)
        panel_h = min(680, height - 120)
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        title_font = retro_style.get_font(28, bold=True)
        subtitle_font = retro_style.get_font(18)
        title = title_font.render(t('tracks'), True, (235, 245, 255))
        self.screen.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        mode_name = ''
        mode_key = self._music_picker_mode_key
        for mk, label in get_mode_music_entries():
            if mk == mode_key:
                mode_name = label
                break
        sub = subtitle_font.render(mode_name, True, (170, 190, 220))
        self.screen.blit(sub, (panel_rect.x + 20, panel_rect.y + 52))

        list_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 90, panel_rect.width - 40, panel_rect.height - 130)
        item_h = 52
        gap = 8

        self._music_picker_scroll = max(0, min(self._music_picker_scroll, self._picker_max_scroll(list_rect.height, item_h, gap)))
        self._picker_ensure_visible(list_rect.height, item_h, gap)

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
            sb_rect = pygame.Rect(panel_rect.right - 12, list_rect.y, 6, list_rect.height)
            retro_style.draw_scrollbar(self.screen, sb_rect, self._music_picker_scroll, total_h, list_rect.height)

    def _draw_toggle_badge(self, rect: pygame.Rect, item: dict, selected: bool) -> None:
        """Toggle tipi ayar için < AÇIK/KAPALI > badge."""
        value_text, value_color = self._get_display_value(item)
        key = item.get('key', '')
        is_on = bool(self._get_value(key))
        if key == 'mute_all':
            is_on = bool(self._get_value(key))
            badge_color = (180, 70, 70) if is_on else (60, 160, 90)
        else:
            badge_color = (60, 160, 90) if is_on else (180, 70, 70)

        badge_font = retro_style.get_fitting_font(value_text, 16, 100, bold=True)
        badge_surf = badge_font.render(value_text, True, (255, 255, 255))
        bw = badge_surf.get_width() + 24
        bh = badge_surf.get_height() + 10
        badge_rect = pygame.Rect(rect.right - bw - 40, rect.centery - bh // 2, bw, bh)
        pygame.draw.rect(self.screen, badge_color, badge_rect, border_radius=bh // 2)
        self.screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))

        # < > okları
        if selected:
            arrow_font = retro_style.get_font(18, bold=True)
            arrow_color = (80, 160, 255)
            left_arrow = arrow_font.render('<', True, arrow_color)
            right_arrow = arrow_font.render('>', True, arrow_color)
            self.screen.blit(left_arrow, left_arrow.get_rect(midright=(badge_rect.left - 6, rect.centery)))
            self.screen.blit(right_arrow, right_arrow.get_rect(midleft=(badge_rect.right + 6, rect.centery)))

    def _draw_inline_slider(self, rect: pygame.Rect, item: dict, selected: bool) -> None:
        """Slider tipi ayar için sürgü çiz."""
        key = item.get('key', '')
        min_val = item.get('min', 0)
        max_val = item.get('max', 1)
        current = float(self._get_value(key))

        # Smooth animasyon
        if key == 'music_volume':
            current = self._music_volume_vis
        elif key == 'sfx_volume':
            current = self._sfx_volume_vis

        ratio = (current - min_val) / max(0.001, max_val - min_val)
        ratio = max(0.0, min(1.0, ratio))

        # Değer metni
        if item.get('percent'):
            value_text = f'{int(current * 100)}%'
        else:
            value_text = f'{int(current)} {item.get("suffix", "")}'.strip()

        # Layout
        slider_right = rect.right - 20
        value_font = retro_style.get_font(18, bold=True)
        value_surf = value_font.render(value_text, True, (220, 235, 255))

        # > oku
        arrow_font = retro_style.get_font(16, bold=True)
        arrow_color = (80, 160, 255) if selected else (100, 120, 150)

        right_arrow = arrow_font.render('>', True, arrow_color)
        right_x = slider_right - right_arrow.get_width()
        self.screen.blit(right_arrow, right_arrow.get_rect(midleft=(right_x, rect.centery)))

        # Değer metni
        val_x = right_x - value_surf.get_width() - 8
        self.screen.blit(value_surf, value_surf.get_rect(midright=(val_x + value_surf.get_width(), rect.centery)))

        # Slider bar – %45 noktasından başla
        bar_right = val_x - 12
        bar_left = rect.x + int(rect.width * 0.45)

        # < oku
        left_arrow = arrow_font.render('<', True, arrow_color)
        self.screen.blit(left_arrow, left_arrow.get_rect(midright=(bar_left - 4, rect.centery)))
        bar_left += 2

        if bar_right > bar_left + 30:
            bar_h = 10
            bar_rect = pygame.Rect(bar_left, rect.centery - bar_h // 2, bar_right - bar_left, bar_h)

            # Track arka planı
            pygame.draw.rect(self.screen, (30, 38, 58), bar_rect, border_radius=4)
            pygame.draw.rect(self.screen, (50, 60, 85), bar_rect, 1, border_radius=4)

            # Dolgu
            fill_w = int(bar_rect.width * ratio)
            if fill_w > 0:
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.height)
                # Gradient renk
                if key == 'music_volume':
                    fill_color = (80, 180, 255)
                elif key == 'sfx_volume':
                    fill_color = (255, 180, 80)
                elif key == 'bg_transparency':
                    fill_color = (100, 200, 150)
                elif key == 'menu_transparency':
                    fill_color = (180, 140, 255)
                else:
                    fill_color = (100, 180, 255)
                pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=4)

            # Knob
            knob_x = bar_rect.x + fill_w
            knob_r = 7
            knob_color = (255, 255, 255) if selected else (180, 190, 210)
            pygame.draw.circle(self.screen, knob_color, (knob_x, rect.centery), knob_r)
            if selected:
                pygame.draw.circle(self.screen, (80, 160, 255), (knob_x, rect.centery), knob_r, 2)

    def _draw_selector_value(self, rect: pygame.Rect, item: dict, selected: bool) -> dict | None:
        """Selector tipi ayar için < değer > göster."""
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

            panel_h = max(30, rect.height - 18)
            gap = 10
            total_w = min(340, int(rect.width * 0.46))
            each_w = max(90, (total_w - gap) // 2)
            right_margin = 24
            right_x = rect.right - right_margin - each_w
            left_x = right_x - gap - each_w

            primary_rect = pygame.Rect(left_x, rect.centery - panel_h // 2, each_w, panel_h)
            secondary_rect = pygame.Rect(right_x, rect.centery - panel_h // 2, each_w, panel_h)

            is_primary_active = selected and self._single_player_bind_slot == 'primary'
            is_secondary_active = selected and self._single_player_bind_slot == 'secondary'
            if self._waiting_for_key and self._pending_keybind_item == item:
                is_primary_active = self._pending_keybind_slot != 'secondary'
                is_secondary_active = self._pending_keybind_slot == 'secondary'

            def _draw_slot(slot_rect: pygame.Rect, text: str, active: bool) -> None:
                bg = (32, 48, 80, 230) if active else (20, 30, 54, 200)
                border = (90, 180, 255) if active else (55, 78, 112)
                pygame.draw.rect(self.screen, bg, slot_rect, border_radius=8)
                pygame.draw.rect(self.screen, border, slot_rect, 1, border_radius=8)
                txt_color = (235, 245, 255) if active else (180, 205, 235)
                txt_font = retro_style.get_fitting_font(text, 20, slot_rect.width - 12, bold=active)
                txt_surf = txt_font.render(text, True, txt_color)
                self.screen.blit(txt_surf, txt_surf.get_rect(center=slot_rect.center))

            _draw_slot(primary_rect, primary_text, is_primary_active)
            _draw_slot(secondary_rect, secondary_text, is_secondary_active)

            return {'primary': primary_rect, 'secondary': secondary_rect}

        if item.get('type') == 'keybind' and item.get('section') == 'gamepad':
            action_key = item.get('action_key')
            primary_val, secondary_val = self._get_gamepad_binding_slots(action_key)
            primary_text = self._format_gamepad_button_label(primary_val)
            secondary_text = self._format_gamepad_button_label(secondary_val)

            if self._waiting_for_key and self._pending_keybind_item == item:
                waiting_text = _t('gp_press_button', 'Butona basın')
                if self._pending_keybind_slot == 'secondary':
                    secondary_text = waiting_text
                else:
                    primary_text = waiting_text

            panel_h = max(30, rect.height - 18)
            gap = 10
            total_w = min(340, int(rect.width * 0.46))
            each_w = max(90, (total_w - gap) // 2)
            right_margin = 24
            right_x = rect.right - right_margin - each_w
            left_x = right_x - gap - each_w

            primary_rect = pygame.Rect(left_x, rect.centery - panel_h // 2, each_w, panel_h)
            secondary_rect = pygame.Rect(right_x, rect.centery - panel_h // 2, each_w, panel_h)

            is_primary_active = selected and self._gamepad_bind_slot == 'primary'
            is_secondary_active = selected and self._gamepad_bind_slot == 'secondary'
            if self._waiting_for_key and self._pending_keybind_item == item:
                is_primary_active = self._pending_keybind_slot != 'secondary'
                is_secondary_active = self._pending_keybind_slot == 'secondary'

            def _draw_slot(slot_rect: pygame.Rect, text: str, active: bool) -> None:
                bg = (32, 48, 80, 230) if active else (20, 30, 54, 200)
                border = (90, 180, 255) if active else (55, 78, 112)
                pygame.draw.rect(self.screen, bg, slot_rect, border_radius=8)
                pygame.draw.rect(self.screen, border, slot_rect, 1, border_radius=8)
                txt_color = (235, 245, 255) if active else (180, 205, 235)
                txt_font = retro_style.get_fitting_font(text, 20, slot_rect.width - 12, bold=active)
                txt_surf = txt_font.render(text, True, txt_color)
                self.screen.blit(txt_surf, txt_surf.get_rect(center=slot_rect.center))

            _draw_slot(primary_rect, primary_text, is_primary_active)
            _draw_slot(secondary_rect, secondary_text, is_secondary_active)

            return {'primary': primary_rect, 'secondary': secondary_rect}

        value_text, value_color = self._get_display_value(item)

        arrow_font = retro_style.get_font(18, bold=True)
        arrow_color = (80, 160, 255) if selected else (100, 120, 150)

        val_font = retro_style.get_fitting_font(value_text, 20, 180, bold=True)
        val_surf = val_font.render(value_text, True, value_color)

        total_w = val_surf.get_width() + 50
        cx = rect.right - 30 - total_w // 2

        left_arrow = arrow_font.render('<', True, arrow_color)
        right_arrow = arrow_font.render('>', True, arrow_color)

        self.screen.blit(left_arrow, left_arrow.get_rect(center=(cx - val_surf.get_width() // 2 - 16, rect.centery)))
        self.screen.blit(val_surf, val_surf.get_rect(center=(cx, rect.centery)))
        self.screen.blit(right_arrow, right_arrow.get_rect(center=(cx + val_surf.get_width() // 2 + 16, rect.centery)))
        return None

    def _draw_submenu_arrow(self, rect: pygame.Rect, selected: bool) -> None:
        """Submenu tipi ayar için > oku."""
        arrow_font = retro_style.get_font(22, bold=True)
        color = (80, 160, 255) if selected else (100, 120, 150)
        arrow = arrow_font.render('>', True, color)
        self.screen.blit(arrow, arrow.get_rect(center=(rect.right - 28, rect.centery)))

    def _draw_vsync_prompt(self) -> None:
        """VSync restart gerekliliği popup'ı."""
        width, height = self.screen.get_size()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        panel_w = min(580, width - 120)
        panel_h = 200
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        retro_style.draw_panel(self.screen, panel_rect, title=_t('vsync_changed', 'VSync Değişti'))

        lang = get_language()
        msg_lines = [
            _t('vsync_restart_msg1', 'VSync değişikliği yeniden başlatma gerektirir.' if lang == 'tr' else 'VSync change requires restart.'),
            _t('vsync_restart_msg2', 'Şimdi yeniden başlatmak ister misiniz?' if lang == 'tr' else 'Would you like to restart now?'),
        ]
        font = retro_style.get_font(20, bold=False)
        y = panel_rect.y + 60
        for line in msg_lines:
            surf = font.render(line, True, (220, 230, 245))
            self.screen.blit(surf, surf.get_rect(center=(panel_rect.centerx, y)))
            y += 28

        btn_h = 48
        btn_gap = 16
        btn_w = (panel_w - 60 - btn_gap) // 2
        btn_y = panel_rect.bottom - btn_h - 20
        btn1 = pygame.Rect(panel_rect.x + 30, btn_y, btn_w, btn_h)
        btn2 = pygame.Rect(btn1.right + btn_gap, btn_y, btn_w, btn_h)
        self._vsync_prompt_buttons = [btn1, btn2]

        restart_text = _t('restart_now', 'Şimdi Yeniden Başlat' if lang == 'tr' else 'Restart Now')
        later_text = _t('later', 'Sonra' if lang == 'tr' else 'Later')
        retro_style.draw_button(self.screen, btn1, restart_text, selected=self._vsync_prompt_choice == 0)
        retro_style.draw_button(self.screen, btn2, later_text, selected=self._vsync_prompt_choice == 1)
