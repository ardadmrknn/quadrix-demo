"""
settings_screen_tabbed.py – Tam ekran / pencere onay modalı: birim testleri.

Kapsam:
1. _cycle_selector('fullscreen', ...) çağrısında:
   - settings_manager.set() ÇAĞRILMAMALI (disk yazma yok)
   - _display_mode_confirm_active = True olmalı
   - 'apply_display_mode' action'ı DÖNMEMELI (None dönmeli)
2. Onay modalı açıkken ESC (Hayır):
   - fullscreen eski değerine dönmeli
   - settings_manager.set() çağrılmamalı
   - _display_mode_confirm_active = False olmalı
3. Onay modalı açıkken ENTER (Evet):
   - settings_manager.set('fullscreen', target) çağrılmalı
   - _display_mode_confirm_active = False olmalı
   - handler 'quit_game' döndürmeli
4. Onay modalı açıkken mouse click – Evet butonuna:
   - settings_manager.set çağrılmalı, 'quit_game' dönmeli
5. Onay modalı açıkken mouse click – Hayır butonuna:
   - settings_manager.set çağrılmamalı, None dönmeli
"""

from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# pygame + bağımlılık stub'ları
# ---------------------------------------------------------------------------

def _install_stubs(monkeypatch):
    # pygame
    pygame_stub = types.ModuleType("pygame")

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x, self.y, self.width, self.height = x, y, width, height
            self.left, self.right, self.top, self.bottom = x, x + width, y, y + height
            self.centerx = x + width // 2
            self.centery = y + height // 2
        def collidepoint(self, pos):
            x, y = pos
            return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height
        def inflate(self, dx, dy):
            return Rect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)
        def get_rect(self, **kwargs):
            r = Rect(self.x, self.y, self.width, self.height)
            for k, v in kwargs.items():
                setattr(r, k, v)
            return r

    class FakeEvent:
        def __init__(self, etype, **attrs):
            self.type = etype
            for k, v in attrs.items():
                setattr(self, k, v)

    pygame_stub.Rect = Rect
    pygame_stub.Surface = type("Surface", (), {"__init__": lambda s, *a, **k: None})
    pygame_stub.KEYDOWN = 768
    pygame_stub.MOUSEBUTTONDOWN = 1025
    pygame_stub.K_ESCAPE = 27
    pygame_stub.K_RETURN = 13
    pygame_stub.K_KP_ENTER = 271
    pygame_stub.K_LEFT = 276
    pygame_stub.K_RIGHT = 275
    pygame_stub.K_UP = 273
    pygame_stub.K_DOWN = 274
    pygame_stub.K_SPACE = 32
    pygame_stub.K_TAB = 9
    pygame_stub.K_PAGEUP = 280
    pygame_stub.K_PAGEDOWN = 281
    pygame_stub.K_LEFTBRACKET = 91
    pygame_stub.K_RIGHTBRACKET = 93
    pygame_stub.K_DELETE = 127
    pygame_stub.K_BACKSPACE = 8
    pygame_stub.KMOD_SHIFT = 1
    pygame_stub.MOUSEWHEEL = 1027
    pygame_stub.MOUSEMOTION = 1024
    pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
    pygame_stub.Event = FakeEvent
    monkeypatch.setitem(sys.modules, "pygame", pygame_stub)

    # constants
    constants_stub = types.ModuleType("constants")
    constants_stub.DEBUG_MODE = False
    monkeypatch.setitem(sys.modules, "constants", constants_stub)

    # retro_style
    retro_style_obj = types.SimpleNamespace(
        accent=(80, 180, 255),
        success=(60, 200, 100),
        secondary=(150, 150, 200),
        get_font=lambda *a, **k: types.SimpleNamespace(render=lambda *a, **k: types.SimpleNamespace(get_height=lambda: 20, get_width=lambda: 80, get_rect=lambda **kw: pygame_stub.Rect())),
        get_fitting_font=lambda *a, **k: types.SimpleNamespace(render=lambda *a, **k: types.SimpleNamespace(get_height=lambda: 20, get_width=lambda: 80, get_rect=lambda **kw: pygame_stub.Rect())),
        draw_glass_panel=lambda *a, **k: None,
        draw_wrapped_text=lambda *a, **k: None,
    )
    retro_style_stub = types.ModuleType("retro_style")
    retro_style_stub.retro_style = retro_style_obj
    monkeypatch.setitem(sys.modules, "retro_style", retro_style_stub)

    # platform_utils
    platform_stub = types.ModuleType("platform_utils")
    platform_stub.is_fullscreen_toggle = lambda *a, **k: False
    platform_stub.normalize_mouse_pos = lambda pos=None, *a: pos
    platform_stub.get_mouse_pos = lambda: (0, 0)
    monkeypatch.setitem(sys.modules, "platform_utils", platform_stub)

    # background_effects
    bg_stub = types.ModuleType("background_effects")
    bg_stub.get_shared_falling_blocks_layer = lambda *a, **k: types.SimpleNamespace(update=lambda *a, **k: None, draw=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "background_effects", bg_stub)

    # localization
    loc_stub = types.ModuleType("localization")
    loc_stub.t = lambda key: key
    loc_stub.get_text = lambda key: key
    loc_stub.get_language = lambda: "tr"
    loc_stub.set_language = lambda lang: None
    loc_stub.get_language_name = lambda lang: lang
    loc_stub.SUPPORTED_LANGUAGES = ["tr", "en"]
    loc_stub.get_all_languages = lambda: ["tr", "en"]
    monkeypatch.setitem(sys.modules, "localization", loc_stub)

    # ui_language_profile
    ui_lang_stub = types.ModuleType("ui_language_profile")
    ui_lang_stub.apply_language_ui_profile = lambda *a, **k: None
    ui_lang_stub.get_font_for_language = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "ui_language_profile", ui_lang_stub)

    # menu
    menu_stub = types.ModuleType("menu")
    menu_stub.get_control_actions = lambda: {}
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    monkeypatch.setitem(sys.modules, "menu", menu_stub)

    # gamepad_manager
    gamepad_stub = types.ModuleType("gamepad_manager")
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx: f"Btn{idx}")
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, "gamepad_manager", gamepad_stub)


def _import_mod(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop("settings_screen_tabbed", None)
    import sys as _sys
    import os
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    if src_dir not in _sys.path:
        _sys.path.insert(0, src_dir)
    return importlib.import_module("settings_screen_tabbed")


# ---------------------------------------------------------------------------
# Yardımcı: minimal TabbedSettingsScreen instance'ı oluştur
# ---------------------------------------------------------------------------

def _make_screen(mod, initial_fullscreen=True):
    """TabbedSettingsScreen.__new__ ile instance oluştur ve gerekli alanları manuel set et."""
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)

    # settings_manager stub
    calls = []

    class FakeSM:
        def get(self, key, default=None):
            if key == 'fullscreen':
                return initial_fullscreen
            return default
        def set(self, key, value):
            calls.append((key, value))
        def save_settings(self):
            pass

    screen.settings_manager = FakeSM()

    # confirm state (normalde __init__ içinde set edilir)
    screen._display_mode_confirm_active = False
    screen._display_mode_confirm_prev_fullscreen = initial_fullscreen
    screen._display_mode_confirm_target_fullscreen = not initial_fullscreen
    screen._display_mode_confirm_yes_rect = None
    screen._display_mode_confirm_no_rect = None

    # fullscreen selector değeri
    screen.fullscreen = initial_fullscreen

    # diğer _cycle_selector'ın ihtiyaç duyduğu alanlar
    screen.RESOLUTIONS = ['1280x720', '1920x1080']
    screen.resolution = 'auto'
    screen.fps_limit = 0
    screen.FPS_LIMITS = [0, 30, 60, 120]
    screen.theme_manager = None
    screen.current_language = 'tr'
    screen._mode_music_overrides = {}

    # _set_value stub (kaydediyoruz çağrıları)
    def fake_set_value(key, value):
        calls.append(('_set_value_' + key, value))
    screen._set_value = fake_set_value

    return screen, calls


# ---------------------------------------------------------------------------
# Test 1: _cycle_selector('fullscreen') – disk yazma yok, modal açılıyor
# ---------------------------------------------------------------------------

def test_cycle_selector_fullscreen_opens_confirm_modal(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)

    result = screen._cycle_selector('fullscreen', 1)

    assert screen._display_mode_confirm_active is True, "Modal aktif olmalı"
    assert screen._display_mode_confirm_prev_fullscreen is True, "Önceki değer saklanmalı"
    assert screen._display_mode_confirm_target_fullscreen is False, "Hedef değer set edilmeli"
    # settings_manager.set() çağrılmamalı
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert len(sm_calls) == 0, f"settings_manager.set() çağrılmamalı; calls={calls}"
    # apply_display_mode dönmemeli
    assert result != 'apply_display_mode', "apply_display_mode dönmemeli"
    assert result is None, "None dönmeli"


def test_cycle_selector_fullscreen_false_to_true(monkeypatch):
    """Pencere → Tam ekran geçişi de aynı davranışı göstermeli."""
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=False)

    result = screen._cycle_selector('fullscreen', 1)

    assert screen._display_mode_confirm_active is True
    assert screen._display_mode_confirm_prev_fullscreen is False
    assert screen._display_mode_confirm_target_fullscreen is True
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert len(sm_calls) == 0
    assert result is None


# ---------------------------------------------------------------------------
# Test 2: _handle_display_mode_confirm – ESC (Hayır)
# ---------------------------------------------------------------------------

def _esc_event(mod):
    import pygame
    ev = types.SimpleNamespace()
    ev.type = pygame.KEYDOWN
    ev.key = pygame.K_ESCAPE
    return ev


def _enter_event(mod):
    import pygame
    ev = types.SimpleNamespace()
    ev.type = pygame.KEYDOWN
    ev.key = pygame.K_RETURN
    return ev


def _mouse_click(mod, pos):
    import pygame
    ev = types.SimpleNamespace()
    ev.type = pygame.MOUSEBUTTONDOWN
    ev.button = 1
    ev.pos = pos
    return ev


def test_confirm_input_esc_cancels(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)

    # Modal aktif et
    screen._display_mode_confirm_active = True
    screen._display_mode_confirm_prev_fullscreen = True
    screen._display_mode_confirm_target_fullscreen = False

    result = screen._handle_display_mode_confirm(_esc_event(mod))

    assert screen._display_mode_confirm_active is False, "Modal kapanmalı"
    assert screen.fullscreen is True, "fullscreen değeri eski halinde kalmalı"
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert len(sm_calls) == 0, "settings_manager.set() çağrılmamalı"
    assert result is None


# ---------------------------------------------------------------------------
# Test 3: _handle_display_mode_confirm – ENTER (Evet)
# ---------------------------------------------------------------------------

def test_confirm_input_enter_commits_and_returns_quit(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)

    screen._display_mode_confirm_active = True
    screen._display_mode_confirm_prev_fullscreen = True
    screen._display_mode_confirm_target_fullscreen = False

    result = screen._handle_display_mode_confirm(_enter_event(mod))

    assert result == 'quit_game', "quit_game dönmeli"
    assert screen._display_mode_confirm_active is False
    assert screen.fullscreen is False, "fullscreen güncellenmeli"
    # settings_manager.set('fullscreen', False) çağrılmalı
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert ('fullscreen', False) in sm_calls, f"settings_manager.set('fullscreen', False) çağrılmalı; calls={calls}"


# ---------------------------------------------------------------------------
# Test 4: Mouse click – Evet butonu
# ---------------------------------------------------------------------------

def test_confirm_mouse_yes_rect(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)
    import pygame

    screen._display_mode_confirm_active = True
    screen._display_mode_confirm_prev_fullscreen = True
    screen._display_mode_confirm_target_fullscreen = False
    # Evet rect'ini manuel set et
    screen._display_mode_confirm_yes_rect = pygame.Rect(100, 200, 150, 50)
    screen._display_mode_confirm_no_rect = pygame.Rect(270, 200, 150, 50)

    result = screen._handle_display_mode_confirm(_mouse_click(mod, (150, 220)))

    assert result == 'quit_game'
    assert screen._display_mode_confirm_active is False
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert ('fullscreen', False) in sm_calls


# ---------------------------------------------------------------------------
# Test 5: Mouse click – Hayır butonu
# ---------------------------------------------------------------------------

def test_confirm_mouse_no_rect(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)
    import pygame

    screen._display_mode_confirm_active = True
    screen._display_mode_confirm_prev_fullscreen = True
    screen._display_mode_confirm_target_fullscreen = False
    screen._display_mode_confirm_yes_rect = pygame.Rect(100, 200, 150, 50)
    screen._display_mode_confirm_no_rect = pygame.Rect(270, 200, 150, 50)

    result = screen._handle_display_mode_confirm(_mouse_click(mod, (320, 220)))

    assert result is None
    assert screen._display_mode_confirm_active is False
    sm_calls = [c for c in calls if not c[0].startswith('_set_value_')]
    assert len(sm_calls) == 0, "Hayır seçilince settings_manager.set() çağrılmamalı"


# ---------------------------------------------------------------------------
# Test 6: handle_input() – modal açıkken event intercept
# ---------------------------------------------------------------------------

def test_handle_input_intercepts_all_events_when_modal_active(monkeypatch):
    """Modal aktifken handle_input tüm event'leri _handle_display_mode_confirm'e yönlendirmeli."""
    mod = _import_mod(monkeypatch)
    screen, calls = _make_screen(mod, initial_fullscreen=True)

    # Modal aktif et; waiting_for_key ve müzik picker kapalı
    screen._display_mode_confirm_active = True
    screen._display_mode_confirm_prev_fullscreen = True
    screen._display_mode_confirm_target_fullscreen = False
    screen._waiting_for_key = False
    screen._music_picker_open = False
    screen._vsync_prompt_active = False
    screen._swallow_next_keydown = False

    # ESC input'u → iptal (None dönmeli)
    result = screen.handle_input(_esc_event(mod))
    assert result is None
    assert screen._display_mode_confirm_active is False
