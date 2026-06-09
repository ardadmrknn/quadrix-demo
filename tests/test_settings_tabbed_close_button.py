"""TabbedSettingsScreen — sağ üst close (×) butonu birim testleri.

Davranış kontratı:
- Normal settings yüzeyinde × butonuna tıklamak ESC ile aynı 'back' aksiyonunu
  döndürmeli.
- _close_button_rect() bir modal/capture aktifken None dönmeli; click bu
  durumda modal'ı bypass edemez.
- Reset butonu (varsa) close butonunun soluna iter; modal aktifken close
  görünmez ve reset eski sağ kenar konumunda kalır.

Bu testler `test_settings_fullscreen_restart_confirm.py` ile aynı stub kalıbını
kullanır; gerçek pygame import etmez.
"""
from __future__ import annotations

import importlib
import sys
import types


def _install_stubs(monkeypatch):
    pygame_stub = types.ModuleType("pygame")

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x, self.y, self.width, self.height = x, y, width, height
            self.left, self.right, self.top, self.bottom = x, x + width, y, y + height
            self.centerx = x + width // 2
            self.centery = y + height // 2
            self.center = (self.centerx, self.centery)
            self.size = (width, height)
            self.topleft = (x, y)

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

    pygame_stub.Rect = Rect
    class Surface:
        last_fill = None

        def __init__(self, size=(0, 0), *args, **kwargs):
            self.size = size if isinstance(size, tuple) else (0, 0)

        def fill(self, color):
            type(self).last_fill = color

        def blit(self, *args, **kwargs):
            return None

        def get_rect(self, **kwargs):
            width, height = self.size if isinstance(self.size, tuple) else (0, 0)
            rect = Rect(0, 0, width, height)
            for key, value in kwargs.items():
                setattr(rect, key, value)
            return rect

    pygame_stub.Surface = Surface
    pygame_stub.SRCALPHA = 65536
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
    pygame_stub.mouse = types.SimpleNamespace(get_pos=lambda: (-1, -1))
    pygame_stub.draw = types.SimpleNamespace(rect=lambda *a, **k: None)

    class FakeEvent:
        def __init__(self, etype, **attrs):
            self.type = etype
            for k, v in attrs.items():
                setattr(self, k, v)

    pygame_stub.Event = FakeEvent
    monkeypatch.setitem(sys.modules, "pygame", pygame_stub)

    constants_stub = types.ModuleType("constants")
    constants_stub.DEBUG_MODE = False
    monkeypatch.setitem(sys.modules, "constants", constants_stub)

    retro_style_obj = types.SimpleNamespace(
        accent=(80, 180, 255),
        primary=(80, 180, 255),
        success=(60, 200, 100),
        secondary=(150, 150, 200),
        get_font=lambda *a, **k: types.SimpleNamespace(
            render=lambda *a, **k: types.SimpleNamespace(
                get_height=lambda: 20, get_width=lambda: 80,
                get_rect=lambda **kw: pygame_stub.Rect(),
            )
        ),
        get_fitting_font=lambda *a, **k: types.SimpleNamespace(
            render=lambda *a, **k: types.SimpleNamespace(
                get_height=lambda: 20, get_width=lambda: 80,
                get_rect=lambda **kw: pygame_stub.Rect(),
            )
        ),
        draw_glass_panel=lambda *a, **k: None,
        draw_wrapped_text=lambda *a, **k: None,
        _scale_menu_alpha=lambda v: v,
    )
    retro_style_stub = types.ModuleType("retro_style")
    retro_style_stub.retro_style = retro_style_obj
    monkeypatch.setitem(sys.modules, "retro_style", retro_style_stub)

    platform_stub = types.ModuleType("platform_utils")
    platform_stub.is_fullscreen_toggle = lambda *a, **k: False
    platform_stub.normalize_mouse_pos = lambda pos=None, *a: pos
    platform_stub.get_mouse_pos = lambda: (0, 0)
    monkeypatch.setitem(sys.modules, "platform_utils", platform_stub)

    bg_stub = types.ModuleType("background_effects")
    bg_stub.get_shared_falling_blocks_layer = lambda *a, **k: types.SimpleNamespace(
        update=lambda *a, **k: None, draw=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "background_effects", bg_stub)

    loc_stub = types.ModuleType("localization")
    loc_stub.t = lambda key: key
    loc_stub.get_text = lambda key: key
    loc_stub.get_language = lambda: "tr"
    loc_stub.set_language = lambda lang: None
    loc_stub.get_language_name = lambda lang: lang
    loc_stub.SUPPORTED_LANGUAGES = ["tr", "en"]
    loc_stub.get_all_languages = lambda: ["tr", "en"]
    monkeypatch.setitem(sys.modules, "localization", loc_stub)

    ui_lang_stub = types.ModuleType("ui_language_profile")
    ui_lang_stub.apply_language_ui_profile = lambda *a, **k: None
    ui_lang_stub.get_font_for_language = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "ui_language_profile", ui_lang_stub)

    menu_stub = types.ModuleType("menu")
    menu_stub.get_control_actions = lambda: {}
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.get_campaign_phase_entries = lambda: []
    menu_stub.CAMPAIGN_PHASE_WORLDS = []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    monkeypatch.setitem(sys.modules, "menu", menu_stub)

    gamepad_stub = types.ModuleType("gamepad_manager")
    gamepad_stub.GamepadType = types.SimpleNamespace(
        XBOX="xbox", PLAYSTATION="playstation",
        NINTENDO="nintendo", UNKNOWN="unknown",
    )
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(
        get_button_index_label=lambda idx: f"Btn{idx}"
    )
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, "gamepad_manager", gamepad_stub)

    promptfont_stub = types.ModuleType("promptfont_support")
    promptfont_stub.get_gamepad_prompt_glyph = lambda *args, **kwargs: None
    promptfont_stub.fit_promptfont_glyph_surface = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "promptfont_support", promptfont_stub)


def _import_mod(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop("settings_screen_tabbed", None)
    import os
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    return importlib.import_module("settings_screen_tabbed")


def _make_screen(mod):
    """TabbedSettingsScreen.__new__ ile minimal instance."""
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)

    class FakeSM:
        def __init__(self):
            self.saves = 0
            self.set_calls = []

        def get(self, key, default=None):
            return default

        def set(self, key, value):
            self.set_calls.append((key, value))

        def save_settings(self):
            self.saves += 1

    screen.settings_manager = FakeSM()

    # _layout_metrics çağrısı için gerekli alanlar
    class FakeScreen:
        def get_size(self):
            return (1366, 768)

        def get_width(self):
            return 1366

        def get_height(self):
            return 768

        def blit(self, *args, **kwargs):
            return None

    screen.screen = FakeScreen()
    screen._ui_reference_size = (1920.0, 1080.0)
    screen._ui_scale_current = 1.0

    # Modal flags — hepsi default kapalı
    screen._waiting_for_key = False
    screen._music_picker_open = False
    screen._playlist_edit_active = False
    screen._campaign_phase_select_active = False
    screen._display_mode_confirm_active = False
    screen._vsync_prompt_active = False

    # _can_reset_tab_defaults için
    screen.current_tab = 0  # game tab → reset visible

    # Drag state'leri sıfırla (close button click handler bunları temizliyor)
    screen._settings_sb_drag_active = False
    screen._slider_drag_active = False
    screen._slider_drag_key = ''
    screen._slider_drag_item = None
    screen._slider_drag_bar_rect = None

    # handle_input girişi için ek state alanları
    screen._swallow_next_keydown = False
    screen._swallow_next_gamepad_click = False
    screen._swallow_next_gamepad_click_deadline_ms = 0

    return screen


def _mouse_click(pos):
    ev = types.SimpleNamespace()
    ev.type = sys.modules["pygame"].MOUSEBUTTONDOWN
    ev.button = 1
    ev.pos = pos
    return ev


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_close_button_rect_visible_when_no_modal(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)

    rect = screen._close_button_rect()
    assert rect is not None
    assert rect.width > 0 and rect.height > 0
    # Panel sağ üstüne yakın olmalı; sol kenar yakın olmaz.
    panel = screen._panel_rect()
    assert rect.x > panel.x + panel.width // 2


def test_close_button_rect_hidden_when_modal_active(monkeypatch):
    """Capture/picker/onay overlay'leri sırasında close butonu görünmemeli."""
    mod = _import_mod(monkeypatch)

    # Her bir modal flag'i tek tek dene — close hep None dönmeli.
    for flag in [
        '_waiting_for_key',
        '_music_picker_open',
        '_playlist_edit_active',
        '_campaign_phase_select_active',
        '_display_mode_confirm_active',
        '_vsync_prompt_active',
    ]:
        screen = _make_screen(mod)
        setattr(screen, flag, True)
        assert screen._close_button_rect() is None, (
            f"Modal '{flag}' aktifken close butonu görünmemeli."
        )


def test_close_button_click_returns_back_in_normal_state(monkeypatch):
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)

    rect = screen._close_button_rect()
    assert rect is not None

    result = screen.handle_input(_mouse_click((rect.centerx, rect.centery)))

    assert result == 'back'
    assert screen.settings_manager.saves >= 1, (
        'Close click should persist settings (matches ESC behaviour)'
    )


def test_close_button_click_inside_modal_does_not_return_back(monkeypatch):
    """vsync prompt aktifken close rect None döner; gerçek mouse klikle modal
    handler'ı (own routing) önceliği alır."""
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)
    screen._vsync_prompt_active = True
    screen._vsync_prompt_choice = 0
    screen._vsync_prompt_buttons = []

    # Close rect bu durumda None
    assert screen._close_button_rect() is None

    # Modal handler'a dispatch edileceği için 'back' dönmemeli; vsync handler
    # iki butonun da rect'i olmadığında None döner — bu kabul.
    result = screen.handle_input(_mouse_click((10, 10)))
    assert result != 'back'


def test_reset_button_shifts_left_when_close_visible(monkeypatch):
    """Reset butonu close butonunun soluna oturmalı; üst üste binmemeli."""
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)

    close_rect = screen._close_button_rect()
    reset_rect = screen._tab_reset_button_rect()

    assert close_rect is not None
    assert reset_rect is not None
    # Reset close'un sol kenarından önce bitmeli (boşluk dahil).
    assert reset_rect.x + reset_rect.width <= close_rect.x


def test_reset_button_uses_full_right_when_close_hidden(monkeypatch):
    """Modal aktifken close görünmez ve reset eski sağ kenar konumunda kalır."""
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)

    # Önce modal yokken reset konumu
    reset_normal = screen._tab_reset_button_rect()
    assert reset_normal is not None

    # Şimdi modal aktif et — close gizli; reset sağa kayar
    screen._music_picker_open = True
    reset_modal = screen._tab_reset_button_rect()
    assert reset_modal is not None
    assert reset_modal.x > reset_normal.x, (
        'Modal aktifken reset close olmadığı için sağa kaymalı.'
    )


def test_reset_button_hover_uses_normalized_mouse(monkeypatch):
    """Reset hover hesabı ham pygame.mouse yerine get_mouse_pos kullanmalı."""
    mod = _import_mod(monkeypatch)
    screen = _make_screen(mod)

    panel = screen._panel_rect()
    rect = screen._tab_reset_button_rect(panel)
    assert rect is not None

    # Ham pygame mouse ekran dışında; normalize helper rect içinde.
    mod.pygame.mouse.get_pos = lambda: (-999, -999)
    monkeypatch.setattr(mod, 'get_mouse_pos', lambda: (rect.centerx, rect.centery))
    mod.pygame.Surface.last_fill = None

    screen._draw_tab_reset_button(panel)

    assert mod.pygame.Surface.last_fill == (30, 38, 58, 200), (
        'Reset hover görseli normalize get_mouse_pos akışına göre aktif olmalı.'
    )
