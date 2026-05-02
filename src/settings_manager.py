"""Ayarları yöneten sınıf - JSON'a kaydet/yükle"""
import copy
import json
import os
import re
import sys
import time
from pathlib import Path

import constants
from atomic_io import atomic_write_json
from data_paths import iter_legacy_paths, migrate_legacy_file, resolve_data_path
from storage_layout import (
    get_campaign_progress_path,
    get_settings_cloud_path,
    get_settings_local_path,
    merge_settings_payload,
    migrate_legacy_settings_file,
    read_json_file,
    split_settings_payload,
    write_json_file,
)

DEFAULT_CONTROLS = {
    'single_player': {
        # Tek oyuncu: her aksiyon için birincil/ikincil tuş.
        # Varsayılan: birincil = oklar, ikincil = WASD (hareket + döndürme).
        'move_left': {'primary': 'left', 'secondary': 'a'},
        'move_right': {'primary': 'right', 'secondary': 'd'},
        'soft_drop': {'primary': 'down', 'secondary': 's'},
        'hard_drop': {'primary': 'space', 'secondary': ''},
        'rotate': {'primary': 'up', 'secondary': 'w'},
        'hold': {'primary': 'c', 'secondary': ''},
        'pause': {'primary': 'p', 'secondary': ''},
    },
    'pvp': {
        'player1': {
            'move_left': 'a',
            'move_right': 'd',
            'soft_drop': 's',
            'hard_drop': 'left shift',
            'rotate': 'w',
            'hold': 'e',
        },
        'player2': {
            'move_left': 'left',
            'move_right': 'right',
            'soft_drop': 'down',
            'hard_drop': 'space',
            'rotate': 'up',
            'hold': 'right shift',
        },
    },
    'gamepad': {
        'enabled': True,
        'rumble': 'high',
        'deadzone': 0.35,
        'mouse_sensitivity': 1.0,
        # Oyun içi butonlar
        'hard_drop': {'primary': 0, 'secondary': -1},     # A (Xbox) / Cross (PS)
        'rotate': {'primary': 1, 'secondary': -1},        # B (Xbox) / Circle (PS)
        'rotate_alt': {'primary': 10, 'secondary': -1},   # RB / R1
        'hold': {'primary': 9, 'secondary': -1},          # LB / L1
        'hold2': {'primary': 2, 'secondary': -1},         # X (Xbox) / Square (PS)
        'pause': {'primary': 6, 'secondary': -1},         # Start / Options / +
        'restart': {'primary': 3, 'secondary': -1},       # Y (Xbox) / Triangle (PS)
        'discard_held': {'primary': 7, 'secondary': -1},  # L3 (Left Stick Click)
        'lt': {'primary': 100, 'secondary': -1},          # LT / L2 (trigger pseudo-index)
        'rt': {'primary': 101, 'secondary': -1},          # RT / R2 (trigger pseudo-index)
        # Kart modu butonlari (varsayilan: atanmis degil)
        'card_rewind': {'primary': -1, 'secondary': -1},
        'card_sniper': {'primary': -1, 'secondary': -1},
        'card_time_capsule_save': {'primary': -1, 'secondary': -1},
        'card_time_capsule_restore': {'primary': -1, 'secondary': -1},
        'card_freeze': {'primary': 1, 'secondary': -1},
        'card_phase_shift': {'primary': -1, 'secondary': -1},
        'card_ghost': {'primary': -1, 'secondary': -1},
        'card_hammer': {'primary': -1, 'secondary': -1},
        'card_bomb': {'primary': -1, 'secondary': -1},
        # Menü butonları
        'menu_confirm': {'primary': 0, 'secondary': -1},  # A / Cross - menüde onayla
        'menu_back': {'primary': 1, 'secondary': -1},     # B / Circle - menüde geri
        'menu_tab_next': {'primary': 10, 'secondary': -1}, # RB / R1 - sonraki sekme
        'menu_tab_prev': {'primary': 9, 'secondary': -1},  # LB / L1 - önceki sekme
    },
    'debug': {
        'coop_spawner_left': '',
        'coop_spawner_right': '',
        'mystery_block_workshop': '',
    },
}

PARTICLE_EFFECT_LEVELS = ('off', 'low', 'medium', 'high')
PARTICLE_EFFECT_SLIDER_TO_LEVEL = {
    0: 'off',
    1: 'low',
    2: 'medium',
    3: 'high',
}
PARTICLE_EFFECT_LEVEL_TO_SLIDER = {
    level: slider for slider, level in PARTICLE_EFFECT_SLIDER_TO_LEVEL.items()
}
PARTICLE_EFFECT_MULTIPLIERS = {
    'off': 0.0,
    'low': 0.55,
    'medium': 1.0,
    'high': 1.7,
}

GAMEPAD_RUMBLE_LEVELS = ('off', 'low', 'medium', 'high')
GAMEPAD_RUMBLE_SLIDER_TO_LEVEL = {
    0: 'off',
    1: 'low',
    2: 'medium',
    3: 'high',
}
GAMEPAD_RUMBLE_LEVEL_TO_SLIDER = {
    level: slider for slider, level in GAMEPAD_RUMBLE_SLIDER_TO_LEVEL.items()
}
GAMEPAD_RUMBLE_MULTIPLIERS = {
    'off': 0.0,
    'low': 0.45,
    'medium': 0.75,
    'high': 1.0,
}

DEFAULT_MENU_MUSIC_PLAYLIST = ['main_1']
DEFAULT_GAME_MUSIC_PLAYLIST = ['klasik_1']
DEFAULT_CAMPAIGN_MUSIC_PLAYLIST = ['klasik_1']
DEFAULT_SETTINGS_OVERRIDE_FILENAME = 'settings_defaults.json'

DEFAULT_MODE_MUSIC_PLAYLISTS = {
    'survival': ['file:survival_2.mp3', 'file:survival_1.mp3'],
    'campaign_world1': ['file:d1.mp3', 'file:d1_1.mp3'],
    'campaign_world2': ['file:d2.mp3', 'file:d2_1.mp3', 'file:d2_3.mp3', 'file:d2_4.mp3'],
    'campaign_world3': ['file:d3.mp3', 'file:d3_1.mp3', 'file:d3_2.mp3'],
    'campaign_world4': ['file:d4_1.mp3', 'file:d4_2.mp3', 'file:d4_3.mp3'],
    'campaign_world5': ['file:d5.mp3', 'file:d5_1.mp3', 'file:d5_2.mp3'],
    'classic': ['file:klasik_1.mp3'],
    'sprint': ['file:sprint_1.mp3'],
    'ultra': ['file:ultra_1.mp3', 'file:ultra_2.mp3'],
    'tetris2': ['file:quadrixextra_1.mp3'],
    'mystery': ['file:kart_1.mp3', 'file:kart_2.mp3', 'file:kart_3.mp3'],
    'cascade': ['file:cascade_1.mp3', 'file:cascade_2.mp3'],
    'pvp': ['file:pvp_1.mp3'],
    'coop': ['file:pvp_1.mp3'],
    'hardcore': ['file:hardcore_1.mp3', 'file:hardcore_2.mp3'],
    'wide': ['file:wide_1.mp3', 'file:wide_2.mp3'],
    'zen': ['file:zen_1.mp3'],
    'daily': ['file:daily_1.mp3'],
}

MODE_MUSIC_DEFAULTS = {
    'campaign': DEFAULT_CAMPAIGN_MUSIC_PLAYLIST[0],
    **{
        mode_key: playlist[0]
        for mode_key, playlist in DEFAULT_MODE_MUSIC_PLAYLISTS.items()
        if playlist
    },
}

OBSOLETE_SETTINGS_KEYS = {
    'theme',
    'custom_theme_colors',
    'borderless_fullscreen',
    'resolution',
    'show_fps',
    'background_enabled',
}

FORCED_UI_SCALE_PRESET = 'compact'
VALID_UI_SCALE_PRESETS = {FORCED_UI_SCALE_PRESET}


class SettingsManager:
    """Oyun ayarlarını yöneten sınıf"""
    
    def __init__(self, filename='settings.json'):
        """Ayar yöneticisini başlat"""
        self._single_file_mode = False
        self.filename = None
        self.cloud_filename = None
        self.local_filename = None
        self.campaign_progress_filename = None

        if isinstance(filename, str) and filename:
            use_split_storage = (
                not os.path.isabs(filename)
                and os.path.dirname(filename) == ''
                and filename in {'settings.json', 'settings_cloud.json'}
            )
            if use_split_storage:
                self.cloud_filename = get_settings_cloud_path()
                self.local_filename = get_settings_local_path()
                self.campaign_progress_filename = get_campaign_progress_path()
                self.filename = self.cloud_filename
                migrate_legacy_settings_file(self.cloud_filename, legacy_filename='settings.json')
            else:
                self._single_file_mode = True
                self.filename = filename
        else:
            self._single_file_mode = True
            self.filename = filename

        self.cloud_settings = {}
        self.local_settings = {}
        self.campaign_progress = {}
        self.default_settings = {
            'language': 'tr',  # Dil ayarı: 'tr' veya 'en'
            'music_enabled': True,
            'sound_enabled': True,
            'music_volume': 0.3,  # Müzik ses seviyesi (0.0 - 1.0)
            'menu_music_volume': 0.3,  # Ana menü müzik ses seviyesi (0.0 - 1.0)
            'sfx_volume': 0.5,    # Efekt ses seviyesi (0.0 - 1.0)
            'effects_enabled': True,
            # Yerleşik (8-bit/sentez) müzikler kaldırıldı: varsayılanlar music/ klasöründeki dosyalardır.
            'menu_music': DEFAULT_MENU_MUSIC_PLAYLIST[0],
            'game_music': DEFAULT_GAME_MUSIC_PLAYLIST[0],
            'debug_mode': False,
            'card_mode_debug': False,
            'leaderboard_trailer_debug': False,
            'online_pvp_trailer_debug': False,
            'local_pvp_demobot_debug': False,
            'coop_debug_halt_blocks': False,
            'mystery_debug_block_workshop': False,
            # Gizli ayarlar: ana menüde "arda" yazınca görünür olur.
            'show_debug_settings': False,
            # Grafik ayarları - Maksimum kalite varsayılan
            'fullscreen': True,  # Oyun yalnızca tam ekran çalışır
            'steam_overlay_gl': 'auto',  # Mevcut konfigürasyon uyumluluğu için korunur
            'vsync': True,  # VSYNC açık - screen tearing önleme
            # FPS limiti: 0 = otomatik ekran yenileme hızı. Değerler: 30/45/60/90/120/0
            'fps_limit': 0,
            # Effective UI zinciri kompakt preset'e sabitli.
            'ui_scale_preset': FORCED_UI_SCALE_PRESET,
            'show_ghost': True,
            'bg_transparency': 0.3,
            # Düşen bloklar ve yıldız efektlerinin opaklığı.
            # 0.0 (görünmez) - 1.0 (tam opak)
            'effects_opacity': 1.0,
            # Menü/UI panel şeffaflığı (RetroStyle glass/panel/button yüzeyleri).
            # 0.0 (tamamen saydam) - 1.0 (opak)
            'menu_transparency': 1.0,
            'particle_effects': 'medium',  # off, low, medium, high
            'animation_level': 'medium-high',  # Animasyon seviyesi: low, medium, medium-high, high
            'block_styles': {},
            'block_workshop_board': [],
            'block_workshop_sets': [],
            'block_workshop_active_set': None,
            'last_texture_dir': None,
            'controls': copy.deepcopy(DEFAULT_CONTROLS),
            'mode_music_overrides': {},
            # Playlist tabanlı müzik seçimi
            'menu_music_playlist': copy.deepcopy(DEFAULT_MENU_MUSIC_PLAYLIST),
            'game_music_playlist': copy.deepcopy(DEFAULT_GAME_MUSIC_PLAYLIST),
            'campaign_music_playlist': copy.deepcopy(DEFAULT_CAMPAIGN_MUSIC_PLAYLIST),
            'mode_music_playlists': copy.deepcopy(DEFAULT_MODE_MUSIC_PLAYLISTS),
            # Müzik karıştırma modu: playlist sırası karıştırılır
            'music_shuffle': False,
            # Oynanış ayarları (FAZ 2)
            'das_delay': 170,         # İlk hareket gecikmesi (ms) - 100-300 arası
            'das_repeat': 50,         # Tekrar hızı (ms) - 10-500 arası
            'soft_drop_speed': 50,    # Yumuşak düşme hızı (ms) - 20-100 arası
        }

        # Ortam değişkeni ile varsayılan dili override et (kullanıcı ayarlarını etkilemez).
        self._apply_env_default_language()

        # Build ile beraber gelen "fabrika" müzik ayarları (seçili özel müzikler)
        # Sadece müzik seçimlerini uygular; diğer ayarlara dokunmaz.
        self._apply_bundled_music_defaults()
        # Kullanıcının elle belirlediği varsayılan override dosyası (opsiyonel)
        self._apply_user_default_settings_override()
        self.settings = self.load_settings()
        normalized_display_settings = self._normalize_display_settings_inplace(self.settings)
        removed_obsolete_settings = self._remove_obsolete_settings_inplace(self.settings)

        # Eski müzik adlarını mevcut track key'lerine migrate et.
        migrated_music_preferences = False
        try:
            migrated_music_preferences = self._migrate_music_preferences_inplace(self.settings)
        except Exception:
            pass

        if normalized_display_settings or removed_obsolete_settings or migrated_music_preferences:
            self.save_settings()

        # Gizli debug ayar görünürlüğü runtime-only olmalı.
        # Her uygulama açılışında tekrar gizli başlasın.
        try:
            self.settings['show_debug_settings'] = False
        except Exception:
            pass

        self._sync_ui_scale_preset()

        now = time.monotonic()
        self._last_save_monotonic = now
        # Kullanıcı slider'ı bırakınca kaydet: ~0.5s yeterli, UX'i bozmaz.
        self._save_debounce_seconds = 0.5

        # Sık değişen ayarlar (slider, repeat input) - diske yazımı toplu yap.
        self._debounced_keys = {
            'music_volume',
            'menu_music_volume',
            'sfx_volume',
            'bg_transparency',
            'effects_opacity',
            'menu_transparency',
            'das_delay',
            'das_repeat',
            'soft_drop_speed',
        }

        # Disk yazımını azaltmak için: bazı ayarlar (slider/tekrarlı input) debounced kaydedilir.
        self._dirty = False
        self._last_change_monotonic = now

    def _get_default_settings_override_path(self) -> str | None:
        """Varsayılan ayar override dosya yolunu döndür."""
        try:
            if self._single_file_mode:
                if isinstance(self.filename, str) and self.filename:
                    base_dir = os.path.dirname(self.filename)
                    if not base_dir:
                        base_dir = os.getcwd()
                    return os.path.join(base_dir, DEFAULT_SETTINGS_OVERRIDE_FILENAME)
                return None
            return resolve_data_path(DEFAULT_SETTINGS_OVERRIDE_FILENAME)
        except Exception:
            return None

    def _apply_user_default_settings_override(self) -> None:
        """Kullanıcıya özel varsayılan ayar override dosyasını uygula.

        Dosya varsa yalnızca bilinen ayar anahtarları override edilir.
        """
        path = self._get_default_settings_override_path()
        if not path or not os.path.exists(path):
            return

        payload = read_json_file(path, default={})
        if not isinstance(payload, dict):
            return

        for key, value in payload.items():
            if key in OBSOLETE_SETTINGS_KEYS or key == 'campaign_progress':
                continue
            if key == 'controls':
                self.default_settings['controls'] = self._merge_controls(value)
                continue
            if key == 'mode_music_playlists' and isinstance(value, dict):
                self.default_settings['mode_music_playlists'] = self._merge_mode_music_playlists_with_defaults(value)
                continue
            if key in self.default_settings:
                self.default_settings[key] = copy.deepcopy(value)

        # Override sonrası normalize et
        self._normalize_display_settings_inplace(self.default_settings)
        self.default_settings['controls'] = self._merge_controls(self.default_settings.get('controls', {}))
        try:
            self._migrate_music_preferences_inplace(self.default_settings)
        except Exception:
            pass

    def save_current_as_defaults(self) -> str | None:
        """Mevcut aktif ayarları varsayılan override dosyasına kaydet."""
        path = self._get_default_settings_override_path()
        if not path:
            return None

        payload = copy.deepcopy(self.settings if isinstance(self.settings, dict) else {})
        payload.pop('campaign_progress', None)
        payload.pop('show_debug_settings', None)

        try:
            write_json_file(path, payload, indent=2)
        except Exception:
            return None

        # Aynı instance içinde de hemen etkili olsun.
        self._apply_user_default_settings_override()
        return path

    def _load_single_file_settings(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    for key, value in self.default_settings.items():
                        if key not in loaded:
                            loaded[key] = copy.deepcopy(value)
                    self._normalize_display_settings_inplace(loaded)
                    loaded['controls'] = self._merge_controls(loaded.get('controls', {}))
                    self._migrate_music_preferences_inplace(loaded)
                    if constants.DEBUG_MODE:
                        print(f"[OK] Ayarlar yuklendi: {self.filename}")
                    return loaded
            except Exception as e:
                print(f"[UYARI] Ayarlar yuklenirken hata: {e}")
                return copy.deepcopy(self.default_settings)

        if constants.DEBUG_MODE:
            print("[BILGI] Varsayilan ayarlar kullaniliyor")
        defaults = copy.deepcopy(self.default_settings)
        self._normalize_display_settings_inplace(defaults)
        defaults['controls'] = self._merge_controls(defaults.get('controls', {}))
        self._migrate_music_preferences_inplace(defaults)
        return defaults

    def _save_split_payloads(self, cloud_settings, local_settings, campaign_progress):
        write_json_file(self.cloud_filename, cloud_settings, indent=2)
        write_json_file(self.local_filename, local_settings, indent=2)
        write_json_file(self.campaign_progress_filename, campaign_progress, indent=2)

    def _load_split_settings(self):
        cloud_payload = read_json_file(self.cloud_filename, default={})
        local_payload = read_json_file(self.local_filename, default={})
        campaign_payload = read_json_file(self.campaign_progress_filename, default={})

        rewrite_split_files = False
        if isinstance(cloud_payload, dict):
            original_cloud_payload = copy.deepcopy(cloud_payload)
            split_cloud, split_local_from_cloud, split_campaign_from_cloud = split_settings_payload(cloud_payload)
            cloud_payload = split_cloud
            if split_local_from_cloud:
                local_payload = {**split_local_from_cloud, **(local_payload if isinstance(local_payload, dict) else {})}
                rewrite_split_files = True
            if split_campaign_from_cloud and not campaign_payload:
                campaign_payload = split_campaign_from_cloud
                rewrite_split_files = True
            if split_cloud != original_cloud_payload:
                rewrite_split_files = True

        if not isinstance(local_payload, dict):
            local_payload = {}
        if not isinstance(campaign_payload, dict):
            campaign_payload = {}

        merged = merge_settings_payload(
            self.default_settings,
            cloud_payload if isinstance(cloud_payload, dict) else {},
            local_payload,
            campaign_payload,
        )
        self._normalize_display_settings_inplace(merged)
        merged['controls'] = self._merge_controls(merged.get('controls', {}))
        self._migrate_music_preferences_inplace(merged)

        self.cloud_settings = cloud_payload if isinstance(cloud_payload, dict) else {}
        self.local_settings = local_payload
        self.campaign_progress = campaign_payload

        if (
            rewrite_split_files
            or not os.path.exists(self.cloud_filename)
            or not os.path.exists(self.local_filename)
            or not os.path.exists(self.campaign_progress_filename)
        ):
            cloud_payload, local_payload, campaign_payload = split_settings_payload(merged)
            self.cloud_settings = cloud_payload
            self.local_settings = local_payload
            self.campaign_progress = campaign_payload
            self._save_split_payloads(cloud_payload, local_payload, campaign_payload)

        if constants.DEBUG_MODE:
            print(f"[OK] Ayarlar yuklendi: cloud={self.cloud_filename} local={self.local_filename}")
        return merged

    def _get_bundled_defaults_path(self) -> str | None:
        """Return bundled defaults JSON path if present.

        Source run: <repo>/src/settings.json
        PyInstaller onefile: <_MEIPASS>/src/settings.json (datas ile eklenir)
        """
        try:
            if getattr(sys, 'frozen', False):
                base = getattr(sys, '_MEIPASS', None)
                if not base:
                    return None
                return os.path.join(base, 'src', 'settings.json')

            # Running from source: project root is parent of this file's directory.
            here = os.path.dirname(__file__)
            project_root = os.path.abspath(os.path.join(here, os.pardir))
            return os.path.join(project_root, 'src', 'settings.json')
        except Exception:
            return None

    def _apply_env_default_language(self) -> None:
        """TETRIS_DEFAULT_LANGUAGE ile varsayılan dili ayarla.

        Geçerli değerler: 'tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko'
        """
        try:
            lang = os.environ.get('TETRIS_DEFAULT_LANGUAGE', '')
            if not isinstance(lang, str):
                return
            lang = lang.strip().lower()
            _VALID_LANGUAGES = {'tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko'}
            if lang in _VALID_LANGUAGES:
                self.default_settings['language'] = lang
        except Exception:
            pass

    def _apply_bundled_music_defaults(self) -> None:
        path = self._get_bundled_defaults_path()
        if not path or not os.path.exists(path):
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        # Sadece müzik seçimlerini al (diğer ayarları override etme)
        try:
            menu_music = data.get('menu_music')
            if isinstance(menu_music, str) and menu_music.strip():
                self.default_settings['menu_music'] = menu_music.strip()

            game_music = data.get('game_music')
            if isinstance(game_music, str) and game_music.strip():
                self.default_settings['game_music'] = game_music.strip()

            overrides = data.get('mode_music_overrides')
            if isinstance(overrides, dict):
                self.default_settings['mode_music_overrides'] = overrides

            menu_playlist = data.get('menu_music_playlist')
            if isinstance(menu_playlist, list):
                cleaned = self._normalize_playlist(menu_playlist)
                if cleaned:
                    self.default_settings['menu_music_playlist'] = cleaned
                    self.default_settings['menu_music'] = cleaned[0]

            game_playlist = data.get('game_music_playlist')
            if isinstance(game_playlist, list):
                cleaned = self._normalize_playlist(game_playlist)
                if cleaned:
                    self.default_settings['game_music_playlist'] = cleaned
                    self.default_settings['game_music'] = cleaned[0]

            mode_playlists = data.get('mode_music_playlists')
            if isinstance(mode_playlists, dict):
                self.default_settings['mode_music_playlists'] = self._merge_mode_music_playlists_with_defaults(mode_playlists)
            
        except Exception:
            return
    
    def load_settings(self):
        """Ayarları JSON'dan yükle"""
        if self._single_file_mode:
            return self._load_single_file_settings()
        return self._load_split_settings()

    def _remove_obsolete_settings_inplace(self, data):
        if not isinstance(data, dict):
            return False

        changed = False
        for key in OBSOLETE_SETTINGS_KEYS:
            if key in data:
                del data[key]
                changed = True
        return changed

    @staticmethod
    def _normalize_ui_scale_preset_value(value):
        preset = str(value or '').strip().lower()
        if preset not in VALID_UI_SCALE_PRESETS:
            return FORCED_UI_SCALE_PRESET
        return preset

    @classmethod
    def normalize_particle_effects_value(cls, value):
        if isinstance(value, bool):
            return 'medium' if value else 'off'

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            slider = max(0, min(3, int(round(value))))
            return PARTICLE_EFFECT_SLIDER_TO_LEVEL.get(slider, 'medium')

        text = str(value or '').strip().lower()
        if not text:
            return 'medium'

        aliases = {
            'false': 'off',
            '0': 'off',
            'off': 'off',
            'kapali': 'off',
            'kapalı': 'off',
            'true': 'medium',
            'on': 'medium',
            'acik': 'medium',
            'açık': 'medium',
            '1': 'low',
            '2': 'medium',
            '3': 'high',
            'low': 'low',
            'az': 'low',
            'medium': 'medium',
            'orta': 'medium',
            'high': 'high',
            'cok': 'high',
            'çok': 'high',
        }
        normalized = aliases.get(text, text)
        if normalized not in PARTICLE_EFFECT_LEVELS:
            return 'medium'
        return normalized

    @classmethod
    def particle_effects_slider_value(cls, value) -> int:
        level = cls.normalize_particle_effects_value(value)
        return PARTICLE_EFFECT_LEVEL_TO_SLIDER.get(level, 2)

    @classmethod
    def particle_effects_level_from_slider(cls, slider_value: int) -> str:
        slider = max(0, min(3, int(round(slider_value))))
        return PARTICLE_EFFECT_SLIDER_TO_LEVEL.get(slider, 'medium')

    @classmethod
    def particle_effects_multiplier_for_value(cls, value) -> float:
        level = cls.normalize_particle_effects_value(value)
        return float(PARTICLE_EFFECT_MULTIPLIERS.get(level, 1.0))

    @classmethod
    def particle_effects_enabled_for_value(cls, value) -> bool:
        return cls.normalize_particle_effects_value(value) != 'off'

    @classmethod
    def normalize_gamepad_rumble_value(cls, value):
        if isinstance(value, bool):
            return 'high' if value else 'off'

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            slider = max(0, min(3, int(round(value))))
            return GAMEPAD_RUMBLE_SLIDER_TO_LEVEL.get(slider, 'high')

        text = str(value or '').strip().lower()
        if not text:
            return 'high'

        aliases = {
            'false': 'off',
            '0': 'off',
            'off': 'off',
            'yok': 'off',
            'none': 'off',
            'kapali': 'off',
            'kapalı': 'off',
            'true': 'high',
            'on': 'high',
            'acik': 'high',
            'açık': 'high',
            '1': 'low',
            '2': 'medium',
            '3': 'high',
            'low': 'low',
            'az': 'low',
            'medium': 'medium',
            'orta': 'medium',
            'high': 'high',
            'cok': 'high',
            'çok': 'high',
        }
        normalized = aliases.get(text, text)
        if normalized not in GAMEPAD_RUMBLE_LEVELS:
            return 'high'
        return normalized

    @classmethod
    def gamepad_rumble_slider_value(cls, value) -> int:
        level = cls.normalize_gamepad_rumble_value(value)
        return GAMEPAD_RUMBLE_LEVEL_TO_SLIDER.get(level, 3)

    @classmethod
    def gamepad_rumble_level_from_slider(cls, slider_value: int) -> str:
        slider = max(0, min(3, int(round(slider_value))))
        return GAMEPAD_RUMBLE_SLIDER_TO_LEVEL.get(slider, 'high')

    @classmethod
    def gamepad_rumble_multiplier_for_value(cls, value) -> float:
        level = cls.normalize_gamepad_rumble_value(value)
        return float(GAMEPAD_RUMBLE_MULTIPLIERS.get(level, 1.0))

    @classmethod
    def gamepad_rumble_enabled_for_value(cls, value) -> bool:
        return cls.normalize_gamepad_rumble_value(value) != 'off'

    def _normalize_display_settings_inplace(self, data):
        if not isinstance(data, dict):
            return False

        changed = False

        for key in ('borderless_fullscreen', 'resolution'):
            if key in data:
                del data[key]
                changed = True

        normalized_preset = self._normalize_ui_scale_preset_value(
            data.get('ui_scale_preset', self.default_settings.get('ui_scale_preset', FORCED_UI_SCALE_PRESET))
        )
        if data.get('ui_scale_preset') != normalized_preset:
            data['ui_scale_preset'] = normalized_preset
            changed = True

        normalized_particle_effects = self.normalize_particle_effects_value(
            data.get('particle_effects', self.default_settings.get('particle_effects', 'medium'))
        )
        if data.get('particle_effects') != normalized_particle_effects:
            data['particle_effects'] = normalized_particle_effects
            changed = True

        return changed

    def _sync_ui_scale_preset(self):
        if not isinstance(getattr(self, 'settings', None), dict):
            return

        preset = self._normalize_ui_scale_preset_value(
            self.settings.get('ui_scale_preset', self.default_settings.get('ui_scale_preset', FORCED_UI_SCALE_PRESET))
        )
        self.settings['ui_scale_preset'] = preset

        try:
            try:
                from .ui_scaling import set_ui_scale_preset  # type: ignore
            except Exception:
                from ui_scaling import set_ui_scale_preset

            set_ui_scale_preset(preset)
        except Exception:
            pass

    def _slug_track_name(self, value):
        if value is None:
            return ''
        raw = str(value).strip().lower()
        if raw.startswith('file:'):
            raw = raw[5:]
        try:
            raw = Path(raw).stem
        except Exception:
            pass
        raw = raw.replace('-', '_').replace(' ', '_')
        raw = re.sub(r'[^a-z0-9_]', '', raw)
        raw = re.sub(r'_+', '_', raw).strip('_')
        return raw

    def _strip_version_suffix(self, slug):
        if not slug:
            return ''
        base = re.sub(r'(?:_?v?\d+)$', '', slug)
        return re.sub(r'_+', '_', base).strip('_')

    def _collect_available_music_keys(self):
        keys = set()
        try:
            # settings_manager.py -> src/ ; project root = parent
            project_root = Path(__file__).resolve().parents[1]
            music_dir = (project_root / 'music').resolve()
            if music_dir.exists():
                for f in music_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {'.mp3', '.wav', '.ogg', '.flac', '.mid', '.midi'}:
                        keys.add(self._slug_track_name(f.stem))
        except Exception:
            pass
        return keys

    def _resolve_music_preference(self, pref, available_keys):
        if not isinstance(pref, str):
            return pref
        raw = pref.strip()
        if not raw:
            return pref
        if raw.lower().startswith('file:'):
            return raw

        slug = self._slug_track_name(raw)
        if not slug:
            return pref
        if slug in available_keys:
            return slug

        base = self._strip_version_suffix(slug)
        if base:
            pattern = re.compile(rf"^{re.escape(base)}(?:[_v]?\d+)?$")
            candidates = [k for k in available_keys if k == base or pattern.match(k)]
            if candidates:
                candidates.sort(key=lambda item: (len(item), item))
                return candidates[0]

        return pref

    def _migrate_music_preferences_inplace(self, data):
        """Eski müzik adlarını mevcut key'lere dönüştür.

        True dönerse data üzerinde değişiklik yapılmıştır.
        """
        if not isinstance(data, dict):
            return False

        available_keys = self._collect_available_music_keys()
        if not available_keys:
            return False

        changed = False

        # Tekli tercihler
        for key in ('menu_music', 'game_music'):
            cur = data.get(key)
            resolved = self._resolve_music_preference(cur, available_keys)
            if isinstance(resolved, str) and resolved != cur:
                data[key] = resolved
                changed = True

        # Playlist listeleri
        for key in ('menu_music_playlist', 'game_music_playlist', 'campaign_music_playlist'):
            playlist = data.get(key)
            if not isinstance(playlist, list):
                continue
            new_list = []
            local_changed = False
            for item in playlist:
                resolved = self._resolve_music_preference(item, available_keys)
                if isinstance(resolved, str) and resolved:
                    new_list.append(resolved)
                elif isinstance(item, str) and item:
                    new_list.append(item)
                if resolved != item:
                    local_changed = True
            if local_changed:
                data[key] = new_list
                changed = True

        # Mod playlistleri
        mode_playlists = data.get('mode_music_playlists')
        if isinstance(mode_playlists, dict):
            for mode_key, playlist in list(mode_playlists.items()):
                if not isinstance(playlist, list):
                    continue
                new_list = []
                local_changed = False
                for item in playlist:
                    resolved = self._resolve_music_preference(item, available_keys)
                    if isinstance(resolved, str) and resolved:
                        new_list.append(resolved)
                    elif isinstance(item, str) and item:
                        new_list.append(item)
                    if resolved != item:
                        local_changed = True
                if local_changed:
                    mode_playlists[mode_key] = new_list
                    changed = True

        # Mod override tekli tercihler
        overrides = data.get('mode_music_overrides')
        if isinstance(overrides, dict):
            for mode_key, value in list(overrides.items()):
                resolved = self._resolve_music_preference(value, available_keys)
                if resolved != value:
                    overrides[mode_key] = resolved
                    changed = True

        return changed
    
    def save_settings(self):
        """Ayarları JSON'a kaydet"""
        try:
            self._normalize_display_settings_inplace(self.settings)
            self._remove_obsolete_settings_inplace(self.settings)
            self._sync_ui_scale_preset()
            if self._single_file_mode:
                atomic_write_json(self.filename, self.settings, indent=2, ensure_ascii=False)
            else:
                cloud_payload, local_payload, campaign_payload = split_settings_payload(self.settings)
                self.cloud_settings = cloud_payload
                self.local_settings = local_payload
                self.campaign_progress = campaign_payload
                self._save_split_payloads(cloud_payload, local_payload, campaign_payload)
            if constants.DEBUG_MODE:
                print(f"[KAYIT] Ayarlar kaydedildi: {self.filename}")
            self._dirty = False
            self._last_save_monotonic = time.monotonic()
            return True
        except Exception as e:
            print(f"[HATA] Ayarlar kaydedilirken hata: {e}")
            return False

    # Backwards-compatible alias for older code expecting `save()`
    def save(self) -> bool:
        """Alias for save_settings() to preserve backward compatibility."""
        return self.save_settings()

    def flush_if_due(self):
        """Debounced ayarları, uygun zamanda diske yaz."""
        if not getattr(self, '_dirty', False):
            return False
        now = time.monotonic()
        last_change = getattr(self, '_last_change_monotonic', now)
        debounce = getattr(self, '_save_debounce_seconds', 0.0) or 0.0
        if (now - last_change) >= debounce:
            return self.save_settings()
        return False
    
    def get(self, key, default=None):
        """Ayar değerini al"""
        return self.settings.get(key, default)

    def get_particle_effects_level(self) -> str:
        return self.normalize_particle_effects_value(
            self.get('particle_effects', self.default_settings.get('particle_effects', 'medium'))
        )

    def get_particle_effects_multiplier(self) -> float:
        return self.particle_effects_multiplier_for_value(self.get_particle_effects_level())

    def particle_effects_enabled(self) -> bool:
        return self.get_particle_effects_level() != 'off'

    def get_gamepad_rumble_level(self) -> str:
        controls = self.get_controls()
        gamepad_cfg = controls.get('gamepad', {})
        return self.normalize_gamepad_rumble_value(
            gamepad_cfg.get('rumble', DEFAULT_CONTROLS.get('gamepad', {}).get('rumble', 'high'))
        )

    def get_gamepad_rumble_multiplier(self) -> float:
        return self.gamepad_rumble_multiplier_for_value(self.get_gamepad_rumble_level())

    def gamepad_rumble_enabled(self) -> bool:
        return self.get_gamepad_rumble_level() != 'off'
    
    def set(self, key, value):
        """Ayar değerini güncelle ve kaydet"""
        if key in OBSOLETE_SETTINGS_KEYS:
            return

        if key == 'controls':
            self.settings[key] = self._merge_controls(value if isinstance(value, dict) else {})
        else:
            self.settings[key] = value

        self._normalize_display_settings_inplace(self.settings)
        self._sync_ui_scale_preset()

        # Debounced keys: disk yazımını geciktir.
        if key in getattr(self, '_debounced_keys', set()):
            self._dirty = True
            self._last_change_monotonic = time.monotonic()
            return

        self.save_settings()
    
    def update(self, **kwargs):
        """Birden fazla ayarı güncelle ve kaydet"""
        for key in OBSOLETE_SETTINGS_KEYS:
            kwargs.pop(key, None)

        if not kwargs:
            return

        if 'controls' in kwargs:
            controls_value = kwargs.pop('controls')
            self.settings['controls'] = self._merge_controls(controls_value if isinstance(controls_value, dict) else {})
        self.settings.update(kwargs)
        self._normalize_display_settings_inplace(self.settings)
        self._sync_ui_scale_preset()

        debounced_keys = getattr(self, '_debounced_keys', set())
        should_debounce = any(k in debounced_keys for k in kwargs.keys())
        if should_debounce and not any(k not in debounced_keys for k in kwargs.keys()):
            self._dirty = True
            self._last_change_monotonic = time.monotonic()
            return

        self.save_settings()
    
    def reset_to_defaults(self):
        """Ayarları varsayılana sıfırla"""
        self.settings = copy.deepcopy(self.default_settings)
        self.settings['campaign_progress'] = {}
        self._normalize_display_settings_inplace(self.settings)
        self._sync_ui_scale_preset()
        self.settings['controls'] = self._merge_controls(self.settings.get('controls', {}))
        self.save_settings()
        if constants.DEBUG_MODE:
            print("[SIFIRLANDI] Ayarlar varsayilana sifirlandi")

    @staticmethod
    def _normalize_mode_key(mode_key):
        if not mode_key:
            return ''
        return str(mode_key).strip().lower()

    def get_mode_music_overrides(self):
        overrides = self.settings.get('mode_music_overrides')
        if not isinstance(overrides, dict):
            overrides = {}
            self.settings['mode_music_overrides'] = overrides
        return dict(overrides)

    def set_mode_music_override(self, mode_key, value):
        key = self._normalize_mode_key(mode_key)
        overrides = self.settings.get('mode_music_overrides')
        if not isinstance(overrides, dict):
            overrides = {}
            self.settings['mode_music_overrides'] = overrides
        if value:
            overrides[key] = value
        elif key in overrides:
            del overrides[key]
        self.save_settings()

    def get_music_preference_for_mode(self, mode_key):
        key = self._normalize_mode_key(mode_key)
        overrides = self.settings.get('mode_music_overrides')
        if isinstance(overrides, dict):
            pref = overrides.get(key)
            if pref:
                return pref
        # Mod bazlı varsayılan müzikler (kullanıcı override yoksa)
        if key in MODE_MUSIC_DEFAULTS:
            return MODE_MUSIC_DEFAULTS[key]
        
        # Klasik mod (varsayılan oyun müziği) için dosya adı kontrolü
        # Eski müzik adlarını yeni adlara yönlendir
        default_music = self.settings.get('game_music', 'klasik_1')
        if default_music in ('Klasikv1', 'klasik0', 'Klasik0'):
            return 'klasik_1'
        return default_music

    def _normalize_playlist(self, playlist):
        if not isinstance(playlist, list):
            return []
        cleaned = []
        for item in playlist:
            if not item:
                continue
            if isinstance(item, str):
                value = item.strip()
                if value:
                    cleaned.append(value)
        return cleaned

    def _merge_mode_music_playlists_with_defaults(self, playlists):
        merged = copy.deepcopy(DEFAULT_MODE_MUSIC_PLAYLISTS)
        if not isinstance(playlists, dict):
            return merged

        for key, playlist in playlists.items():
            normalized_key = self._normalize_mode_key(key)
            normalized_playlist = self._normalize_playlist(playlist)
            if normalized_key and normalized_playlist:
                merged[normalized_key] = normalized_playlist
        return merged

    def get_menu_music_playlist(self):
        playlist = self.settings.get('menu_music_playlist')
        playlist = self._normalize_playlist(playlist)
        if playlist:
            return playlist
        fallback = self.settings.get('menu_music')
        return [fallback] if fallback else []

    def set_menu_music_playlist(self, playlist):
        normalized = self._normalize_playlist(playlist)
        self.settings['menu_music_playlist'] = normalized
        if normalized:
            self.settings['menu_music'] = normalized[0]
        self.save_settings()

    def get_game_music_playlist(self):
        playlist = self.settings.get('game_music_playlist')
        playlist = self._normalize_playlist(playlist)
        if playlist:
            return playlist
        fallback = self.settings.get('game_music')
        return [fallback] if fallback else []

    def set_game_music_playlist(self, playlist):
        normalized = self._normalize_playlist(playlist)
        self.settings['game_music_playlist'] = normalized
        if normalized:
            self.settings['game_music'] = normalized[0]
        self.save_settings()

    def get_campaign_music_playlist(self):
        playlist = self.settings.get('campaign_music_playlist')
        playlist = self._normalize_playlist(playlist)
        if playlist:
            return playlist
        return ['klasik_1']

    def set_campaign_music_playlist(self, playlist):
        normalized = self._normalize_playlist(playlist)
        self.settings['campaign_music_playlist'] = normalized
        self.save_settings()

    def get_mode_music_playlists(self):
        playlists = self.settings.get('mode_music_playlists')
        if not isinstance(playlists, dict):
            playlists = {}
            self.settings['mode_music_playlists'] = playlists
        return dict(playlists)

    def get_mode_music_playlist(self, mode_key):
        key = self._normalize_mode_key(mode_key)
        playlists = self.settings.get('mode_music_playlists')
        if not isinstance(playlists, dict):
            playlists = {}
            self.settings['mode_music_playlists'] = playlists
        playlist = playlists.get(key)
        return self._normalize_playlist(playlist)

    def set_mode_music_playlist(self, mode_key, playlist):
        key = self._normalize_mode_key(mode_key)
        playlists = self.settings.get('mode_music_playlists')
        if not isinstance(playlists, dict):
            playlists = {}
            self.settings['mode_music_playlists'] = playlists
        normalized = self._normalize_playlist(playlist)
        if normalized:
            playlists[key] = normalized
        elif key in playlists:
            del playlists[key]
        self.save_settings()

    def get_music_playlist_for_mode(self, mode_key):
        key = self._normalize_mode_key(mode_key)
        playlist = self.get_mode_music_playlist(key)
        if playlist:
            return playlist

        overrides = self.settings.get('mode_music_overrides')
        if isinstance(overrides, dict):
            pref = overrides.get(key)
            if pref:
                return [pref]

        # Kampanya dünya anahtarları (campaign_world1 - campaign_world5)
        # için genel campaign playlist'ine düş
        if key.startswith('campaign_world'):
            campaign_playlist = self.get_mode_music_playlist('campaign')
            if campaign_playlist:
                return campaign_playlist
            return self.settings.get('campaign_music_playlist', ['klasik_1'])

        if key == 'campaign':
            return self.settings.get('campaign_music_playlist', ['klasik_1'])

        default_playlist = DEFAULT_MODE_MUSIC_PLAYLISTS.get(key)
        if default_playlist:
            return list(default_playlist)

        return self.get_game_music_playlist()

    def get_controls(self):
        """Kontrol şemasını normalize ederek döndür."""
        controls = self._merge_controls(self.settings.get('controls', {}))
        self.settings['controls'] = controls
        return copy.deepcopy(controls)

    def get_default_controls(self):
        """Varsayılan kontrol şemasının bir kopyasını döndür."""
        return copy.deepcopy(DEFAULT_CONTROLS)

    def _merge_controls(self, existing):
        merged = self.get_default_controls()
        if not isinstance(existing, dict):
            merged['gamepad']['rumble'] = self.normalize_gamepad_rumble_value(
                merged['gamepad'].get('rumble', 'high')
            )
            return merged
        single = existing.get('single_player')
        if isinstance(single, dict):
            # Tek oyuncu kontrolleri (primary/secondary)
            for action, value in single.items():
                if action not in merged.get('single_player', {}):
                    continue
                default_value = merged['single_player'][action]

                # Legacy: tek string/int değeri -> primary override, secondary default kalsın.
                if isinstance(value, (str, int)):
                    if isinstance(default_value, dict):
                        merged['single_player'][action]['primary'] = value
                    else:
                        merged['single_player'][action] = value
                    continue

                # New: {'primary': ..., 'secondary': ...}
                if isinstance(value, dict) and isinstance(default_value, dict):
                    for slot in ('primary', 'secondary'):
                        slot_value = value.get(slot)
                        if isinstance(slot_value, (str, int)):
                            merged['single_player'][action][slot] = slot_value
        pvp_existing = existing.get('pvp')
        if isinstance(pvp_existing, dict):
            for player in ('player1', 'player2'):
                player_data = pvp_existing.get(player)
                if isinstance(player_data, dict):
                    merged['pvp'][player].update({k: v for k, v in player_data.items() if isinstance(v, (str, int))})
        # Gamepad ayarlarını birleştir
        gp_existing = existing.get('gamepad')
        if isinstance(gp_existing, dict):
            for key, value in gp_existing.items():
                if key in merged.get('gamepad', {}):
                    default_value = merged['gamepad'][key]
                    if isinstance(default_value, dict):
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            merged['gamepad'][key]['primary'] = int(value)
                        elif isinstance(value, dict):
                            for slot in ('primary', 'secondary'):
                                slot_value = value.get(slot)
                                if isinstance(slot_value, (int, float)) and not isinstance(slot_value, bool):
                                    merged['gamepad'][key][slot] = int(slot_value)
                    elif isinstance(value, (str, int, float, bool)):
                        merged['gamepad'][key] = value

        merged['gamepad']['rumble'] = self.normalize_gamepad_rumble_value(
            merged['gamepad'].get('rumble', 'high')
        )

        debug_existing = existing.get('debug')
        if isinstance(debug_existing, dict):
            for action, value in debug_existing.items():
                if action in merged.get('debug', {}) and isinstance(value, (str, int)):
                    merged['debug'][action] = value

        return merged
