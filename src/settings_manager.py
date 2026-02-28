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
        'fullscreen_toggle': {'primary': 'f12', 'secondary': ''},
    },
    'pvp': {
        'player1': {
            'move_left': 'a',
            'move_right': 'd',
            'soft_drop': 's',
            'hard_drop': 'left shift',
            'rotate': 'w',
        },
        'player2': {
            'move_left': 'left',
            'move_right': 'right',
            'soft_drop': 'down',
            'hard_drop': 'space',
            'rotate': 'up',
        },
    },
    'gamepad': {
        'enabled': True,
        'rumble': True,
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
        'card_phase_shift': {'primary': -1, 'secondary': -1},
        'card_ghost': {'primary': -1, 'secondary': -1},
        'card_hammer': {'primary': -1, 'secondary': -1},
        'card_bomb': {'primary': -1, 'secondary': -1},
        # Menü butonları
        'menu_confirm': {'primary': 0, 'secondary': -1},  # A / Cross - menüde onayla
        'menu_back': {'primary': 1, 'secondary': -1},     # B / Circle - menüde geri
        'menu_tab_next': {'primary': 10, 'secondary': -1}, # RB / R1 - sonraki sekme
        'menu_tab_prev': {'primary': 9, 'secondary': -1},  # LB / L1 - önceki sekme
        'main_menu_prompt': {'primary': -1, 'secondary': -1},
    },
}

MODE_MUSIC_DEFAULTS = {
    'campaign': 'Klasik0',
    'survival': 'Survival',
    'sprint': 'Kartv3',
    'ultra': 'Ultrav3',
    'zen': 'zen1',
    'tetris2': 'tetrisextra1',
    'mystery': 'Kartv2',
    'wide': 'Widev3',
    'cascade': 'Cascadev3',
    'pvp': 'PvPv3',
    'daily': 'dailyv2',
    'hardcore': 'hardcorew0_1',
}


class SettingsManager:
    """Oyun ayarlarını yöneten sınıf"""
    
    def __init__(self, filename='settings.json'):
        """Ayar yöneticisini başlat"""
        # Keep settings location stable regardless of current working directory.
        # Default: store in unified user data directory.
        if isinstance(filename, str) and filename:
            self.filename = resolve_data_path(filename)
            if not os.path.isabs(filename) and os.path.dirname(filename) == '':
                migrate_legacy_file(self.filename, iter_legacy_paths(filename))
        else:
            self.filename = filename
        self.default_settings = {
            'language': 'tr',  # Dil ayarı: 'tr' veya 'en'
            'music_enabled': True,
            'sound_enabled': True,
            'music_volume': 0.3,  # Müzik ses seviyesi (0.0 - 1.0)
            'menu_music_volume': 0.3,  # Ana menü müzik ses seviyesi (0.0 - 1.0)
            'sfx_volume': 0.5,    # Efekt ses seviyesi (0.0 - 1.0)
            'effects_enabled': True,
            'background_enabled': True,
            # Yerleşik (8-bit/sentez) müzikler kaldırıldı: varsayılanlar music/ klasöründeki dosyalardır.
            'menu_music': 'mainv3',
            'game_music': 'klasik0',
            'theme': 'Classic',  # Varsayılan tema Classic
            'debug_mode': False,
            'card_mode_debug': False,
            # Gizli ayarlar: ana menüde "arda" yazınca görünür olur.
            'show_debug_settings': False,
            # Grafik ayarları - Maksimum kalite varsayılan
            'fullscreen': True,  # Varsayılan: çerçevesiz tam ekran
            'borderless_fullscreen': True,  # Borderless/desktop fullscreen (alt+tab uyumlu)
            'resolution': 'auto',  # Otomatik = cihazın maksimum çözünürlüğü
            'vsync': True,  # VSYNC açık - screen tearing önleme
            # FPS limiti: 0 = MAX (sınırsız). Değerler: 30/45/60/90/120/0
            'fps_limit': 0,
            'show_ghost': True,
            'bg_transparency': 0.3,
            # Menü/UI panel şeffaflığı (RetroStyle glass/panel/button yüzeyleri).
            # 0.0 (tamamen saydam) - 1.0 (opak)
            'menu_transparency': 1.0,
            'particle_effects': True,  # Parçacık efektleri varsayılan açık
            'animation_level': 'medium-high',  # Animasyon seviyesi: low, medium, medium-high, high
            'block_styles': {},
            'custom_theme_colors': {},
            'block_workshop_board': [],
            'block_workshop_sets': [],
            'block_workshop_active_set': None,
            'last_texture_dir': None,
            'controls': copy.deepcopy(DEFAULT_CONTROLS),
            'mode_music_overrides': {},
            # Playlist tabanlı müzik seçimi
            'menu_music_playlist': ['mainv3'],
            'game_music_playlist': ['klasik0'],
            'campaign_music_playlist': ['klasik0'],
            'mode_music_playlists': {key: [value] for key, value in MODE_MUSIC_DEFAULTS.items()},
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
        self.settings = self.load_settings()

        # Eski müzik adlarını mevcut track key'lerine migrate et.
        try:
            if self._migrate_music_preferences_inplace(self.settings):
                self.save_settings()
        except Exception:
            pass

        # Gizli debug ayar görünürlüğü runtime-only olmalı.
        # Her uygulama açılışında tekrar gizli başlasın.
        try:
            self.settings['show_debug_settings'] = False
        except Exception:
            pass

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
            'menu_transparency',
            'das_delay',
            'das_repeat',
            'soft_drop_speed',
        }

        # Disk yazımını azaltmak için: bazı ayarlar (slider/tekrarlı input) debounced kaydedilir.
        self._dirty = False
        self._last_change_monotonic = now

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
                cleaned_playlists = {}
                for key, playlist in mode_playlists.items():
                    normalized = self._normalize_playlist(playlist)
                    if normalized:
                        cleaned_playlists[self._normalize_mode_key(key)] = normalized
                if cleaned_playlists:
                    self.default_settings['mode_music_playlists'] = cleaned_playlists
            
            # Ekran ayarlarını da paketlenmiş ayarlardan al (varsa)
            if 'fullscreen' in data:
                self.default_settings['fullscreen'] = bool(data['fullscreen'])
            if 'borderless_fullscreen' in data:
                self.default_settings['borderless_fullscreen'] = bool(data['borderless_fullscreen'])
        except Exception:
            return
    
    def load_settings(self):
        """Ayarları JSON'dan yükle"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Eksik ayarları varsayılanlarla tamamla
                    for key, value in self.default_settings.items():
                        if key not in loaded:
                            loaded[key] = copy.deepcopy(value)
                    loaded['controls'] = self._merge_controls(loaded.get('controls', {}))
                    self._migrate_music_preferences_inplace(loaded)
                    if constants.DEBUG_MODE:
                        print(f"[OK] Ayarlar yuklendi: {self.filename}")
                    return loaded
            except Exception as e:
                print(f"[UYARI] Ayarlar yuklenirken hata: {e}")
                return copy.deepcopy(self.default_settings)
        else:
            if constants.DEBUG_MODE:
                print("[BILGI] Varsayilan ayarlar kullaniliyor")
            defaults = copy.deepcopy(self.default_settings)
            defaults['controls'] = self._merge_controls(defaults.get('controls', {}))
            self._migrate_music_preferences_inplace(defaults)
            return defaults

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
            atomic_write_json(self.filename, self.settings, indent=2, ensure_ascii=False)
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
    
    def set(self, key, value):
        """Ayar değerini güncelle ve kaydet"""
        if key == 'controls':
            self.settings[key] = self._merge_controls(value if isinstance(value, dict) else {})
        else:
            self.settings[key] = value

        # Debounced keys: disk yazımını geciktir.
        if key in getattr(self, '_debounced_keys', set()):
            self._dirty = True
            self._last_change_monotonic = time.monotonic()
            return

        self.save_settings()
    
    def update(self, **kwargs):
        """Birden fazla ayarı güncelle ve kaydet"""
        if 'controls' in kwargs:
            controls_value = kwargs.pop('controls')
            self.settings['controls'] = self._merge_controls(controls_value if isinstance(controls_value, dict) else {})
        self.settings.update(kwargs)

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
        # 'Klasikv1' kodu 'klasik0.mp3' ile eşleşmiyor olabilir, onu da düzeltiyoruz.
        default_music = self.settings.get('game_music', 'klasik0')
        if default_music == 'Klasikv1': 
            return 'klasik0'
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
        return ['klasik0']

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

        if key == 'campaign':
            return self.settings.get('campaign_music_playlist', ['klasik0'])

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
        return merged
