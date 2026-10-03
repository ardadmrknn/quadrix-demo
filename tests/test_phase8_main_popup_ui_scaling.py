import ast
import math
import pathlib
import sys
import importlib
from types import SimpleNamespace

import pygame
import pytest


ROOT_DIR = pathlib.Path(__file__).parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

main_module = importlib.import_module('src.main')


class _FakeFont:
    def __init__(self, size: int):
        self._size = max(1, int(size))

    def render(self, text, antialias, color):
        width, height = self.size(text)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rgb = tuple(color[:3]) if isinstance(color, tuple) else (255, 255, 255)
        surface.fill((*rgb, 255))
        return surface

    def size(self, text):
        return max(1, int(len(str(text or '')) * self._size * 0.55)), self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


class _SettingsStub:
    def __init__(self):
        self._values = {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


def _install_live_popup_stubs(monkeypatch, recovered_size=(800, 600)):
    recorded = {
        'panel_rects': [],
        'body_rects': [],
        'button_rects': [],
        'backdrop_sizes': [],
    }
    recovered_screen = pygame.Surface(recovered_size, pygame.SRCALPHA)
    events = [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]]

    def draw_glass_panel(screen, rect, alpha=0, border_color=(255, 255, 255), glow=False):
        recorded['panel_rects'].append(rect.copy())
        pygame.draw.rect(screen, border_color[:3], rect, 1)

    retro_style_stub = SimpleNamespace(
        draw_glass_panel=draw_glass_panel,
        draw_wrapped_text=lambda screen, text, font, color, rect, align='center', line_spacing=0: recorded['body_rects'].append(rect.copy()),
        draw_uniform_button=lambda screen, rect, label, sub_text='', color_code=None, selected=False, **kwargs: recorded['button_rects'].append(rect.copy()),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        accent=(100, 200, 255),
        success=(90, 220, 140),
        secondary=(220, 120, 120),
        primary=(110, 160, 255),
    )

    original_ensure = main_module._ensure_popup_backdrop

    def ensure_spy(backdrop, screen, *, dim_alpha):
        refreshed = original_ensure(backdrop, screen, dim_alpha=dim_alpha)
        recorded['backdrop_sizes'].append(refreshed.get_size())
        return refreshed

    monkeypatch.setattr(main_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(main_module, 't', lambda key, *args, **kwargs: kwargs.get('default', key))
    monkeypatch.setattr(main_module, 'get_mouse_pos', lambda: (0, 0))
    monkeypatch.setattr(main_module.pygame.mouse, 'get_focused', lambda: False)
    monkeypatch.setattr(main_module.pygame.display, 'flip', lambda: None)
    monkeypatch.setattr(main_module.pygame.time, 'Clock', lambda: SimpleNamespace(tick=lambda fps: None))
    monkeypatch.setattr(main_module.pygame.event, 'get', lambda: events.pop(0) if events else [])
    monkeypatch.setattr(main_module, '_maybe_recover_windows_display', lambda screen, settings_manager=None: recovered_screen)
    monkeypatch.setattr(main_module, '_ensure_popup_backdrop', ensure_spy)
    return recorded


def _assert_popup_layout_within_recovered_surface(recorded, recovered_size=(800, 600)):
    panel_rect = recorded['panel_rects'][0]
    assert panel_rect.right <= recovered_size[0]
    assert panel_rect.bottom <= recovered_size[1]
    assert panel_rect.x >= 0
    assert panel_rect.y >= 0
    assert recorded['backdrop_sizes'][-1] == recovered_size
    if recorded['body_rects']:
        assert panel_rect.contains(recorded['body_rects'][0])
    assert recorded['button_rects']
    assert all(panel_rect.contains(rect) for rect in recorded['button_rects'])


class _FrameClockProbe:
    def __init__(self):
        self.calls = []
        self.elapsed = [540000, 16]

    def tick(self, cap):
        self.calls.append(('tick', cap))
        return self.elapsed.pop(0)

    def tick_busy_loop(self, cap):
        self.calls.append(('tick_busy_loop', cap))
        return self.elapsed.pop(0)


@pytest.mark.parametrize('platform_name', ['win32', 'darwin'])
def test_modal_popup_time_is_consumed_before_next_game_frame(monkeypatch, platform_name):
    clock = _FrameClockProbe()
    monkeypatch.setattr(main_module.sys, 'platform', platform_name)

    main_module._discard_modal_elapsed_time(clock)
    # Demo ana döngüsü v2'nin _tick_frame_clock sarmalayıcısına sahip
    # değil; döngüdeki satır içi ifadeyle aynı çağrı yapılır.
    if platform_name == 'darwin' and hasattr(clock, 'tick_busy_loop'):
        delta_ms = clock.tick_busy_loop(144)
    else:
        delta_ms = clock.tick(144)

    assert delta_ms == 16
    expected_tick = 'tick_busy_loop' if platform_name == 'darwin' else 'tick'
    assert clock.calls == [('tick', 0), (expected_tick, 144)]


@pytest.mark.parametrize('confirmed', [True, False])
@pytest.mark.parametrize('popup_ms', [540000, 660000])
def test_popup_runner_discards_modal_wait_and_preserves_display_recovery(confirmed, popup_ms):
    source_path = pathlib.Path(main_module.__file__)
    source = ast.parse(source_path.read_text(encoding='utf-8'))
    popup_function = next(
        node for node in ast.walk(source)
        if isinstance(node, ast.FunctionDef) and node.name == '_run_popup_and_sync_screen'
    )
    factory = ast.parse(
        'def make_runner(screen, clock):\n'
        '    def _apply_screen(replacement):\n'
        '        nonlocal screen\n'
        '        screen = replacement\n'
        '    return _run_popup_and_sync_screen, lambda: screen\n'
    ).body[0]
    factory.body.insert(1, popup_function)
    initial_screen = object()
    recovered_screen = object()
    events = []
    namespace = {
        '_discard_modal_elapsed_time': main_module._discard_modal_elapsed_time,
        '_refresh_screen_from_display': lambda screen: recovered_screen,
        'pygame': SimpleNamespace(
            VIDEORESIZE=123,
            event=SimpleNamespace(
                pump=lambda: events.append('pump'),
                clear=lambda event_types: events.append(event_types),
            ),
        ),
    }
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    exec(compile(module, str(source_path), 'exec'), namespace)
    clock = _FrameClockProbe()
    clock.elapsed = [popup_ms, 16]
    runner, get_screen = namespace['make_runner'](initial_screen, clock)
    calls = []

    def popup(screen, mode_key, *, settings_manager):
        calls.append((screen, mode_key, settings_manager))
        return confirmed

    assert runner(popup, 'survival', settings_manager={}) is confirmed
    assert calls == [(initial_screen, 'survival', {})]
    assert get_screen() is recovered_screen
    assert events == ['pump', [123]]
    assert clock.calls == [('tick', 0)]

    def failing_popup(screen):
        raise RuntimeError('popup failed')

    clock.elapsed = [popup_ms, 16]
    with pytest.raises(RuntimeError, match='popup failed'):
        runner(failing_popup)
    # Modal süresi tüketildi; sonraki kare popup_ms değil normal pace döner.
    assert clock.tick(1000) == 16
    assert clock.calls[-2:] == [('tick', 0), ('tick', 1000)]


def test_fullscreen_popup_scale_uses_shared_reference_and_clamps_bounds():
    assert main_module._fullscreen_popup_scale((1920, 1080)) == 1.0
    assert main_module._fullscreen_popup_scale((2560, 1440)) > 1.0
    assert main_module._fullscreen_popup_scale((800, 600)) == 0.65


def test_fullscreen_popup_scale_uses_projected_effective_scale(monkeypatch):
    captured = {}

    def fake_get_projected_scale(screen, *, min_scale, max_scale, reference_size, display_surface=None, apply_preset=True):
        captured['screen'] = screen
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.23

    monkeypatch.setattr(main_module, 'get_projected_effective_scale', fake_get_projected_scale)

    screen = pygame.Surface((2560, 1660), pygame.SRCALPHA)
    assert math.isclose(main_module._fullscreen_popup_scale(screen), 1.23)
    assert captured['screen'] is screen
    assert captured['min_scale'] == 0.65
    assert captured['max_scale'] == 1.35
    assert captured['reference_size'] == (1920.0, 1080.0)
    assert captured['display_surface'] is None


def test_capture_popup_backdrop_matches_surface_size_and_dims_pixels():
    screen = pygame.Surface((120, 80))
    screen.fill((255, 255, 255))

    backdrop = main_module._capture_popup_backdrop(screen, dim_alpha=160)

    assert backdrop.get_size() == (120, 80)
    sample = backdrop.get_at((10, 10))
    assert sample.r < 255
    assert sample.g < 255
    assert sample.b < 255


def test_ensure_popup_backdrop_reuses_existing_surface_when_size_matches():
    screen = pygame.Surface((160, 90))
    screen.fill((20, 30, 40))
    backdrop = main_module._capture_popup_backdrop(screen, dim_alpha=160)

    same_backdrop = main_module._ensure_popup_backdrop(backdrop, screen, dim_alpha=160)

    assert same_backdrop is backdrop


def test_ensure_popup_backdrop_refreshes_when_surface_size_changes():
    old_screen = pygame.Surface((160, 90))
    old_screen.fill((20, 30, 40))
    backdrop = main_module._capture_popup_backdrop(old_screen, dim_alpha=160)

    new_screen = pygame.Surface((200, 120))
    new_screen.fill((255, 255, 255))
    refreshed = main_module._ensure_popup_backdrop(backdrop, new_screen, dim_alpha=220)

    assert refreshed is not backdrop
    assert refreshed.get_size() == (200, 120)
    sample = refreshed.get_at((5, 5))
    assert sample.r < 255


def test_refresh_screen_from_display_uses_latest_display_surface(monkeypatch):
    old_screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    new_screen = pygame.Surface((800, 600), pygame.SRCALPHA)

    monkeypatch.setattr(main_module, '_get_actual_display_surface', lambda: new_screen)

    assert main_module._refresh_screen_from_display(old_screen) is new_screen


def test_refresh_screen_from_display_keeps_current_screen_when_display_missing(monkeypatch):
    current_screen = pygame.Surface((1366, 768), pygame.SRCALPHA)

    monkeypatch.setattr(main_module, '_get_actual_display_surface', lambda: None)

    assert main_module._refresh_screen_from_display(current_screen) is current_screen


def test_apply_screen_to_targets_rebinds_long_lived_screen_owners():
    old_screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    new_screen = pygame.Surface((800, 600), pygame.SRCALPHA)

    settings_screen = SimpleNamespace(screen=old_screen)
    extras_screen = SimpleNamespace(screen=old_screen)
    guide_screen = SimpleNamespace(screen=old_screen)
    coop_level_select = SimpleNamespace(screen=old_screen, window_width=1366, window_height=768)
    leaderboard_trailer_screen = SimpleNamespace(screen=old_screen)
    user_selection_editor = SimpleNamespace(screen=old_screen)
    user_management_editor = SimpleNamespace(screen=old_screen)
    user_selection_screen = SimpleNamespace(screen=old_screen, avatar_editor=user_selection_editor)
    user_management_screen = SimpleNamespace(screen=old_screen, avatar_editor=user_management_editor)
    no_screen = SimpleNamespace(value=123)

    main_module._apply_screen_to_targets(
        new_screen,
        settings_screen,
        extras_screen,
        guide_screen,
        coop_level_select,
        leaderboard_trailer_screen,
        user_selection_screen,
        user_management_screen,
        None,
        no_screen,
    )

    assert settings_screen.screen is new_screen
    assert extras_screen.screen is new_screen
    assert guide_screen.screen is new_screen
    assert coop_level_select.screen is new_screen
    assert (coop_level_select.window_width, coop_level_select.window_height) == (800, 600)
    assert leaderboard_trailer_screen.screen is new_screen
    assert user_selection_screen.screen is new_screen
    assert user_management_screen.screen is new_screen
    assert user_selection_editor.screen is new_screen
    assert user_management_editor.screen is new_screen
    assert no_screen.value == 123


def test_mode_intro_popup_live_loop_reanchors_to_recovered_surface(monkeypatch):
    recorded = _install_live_popup_stubs(monkeypatch)
    settings = _SettingsStub()
    monkeypatch.setattr(
        main_module,
        'GAME_MODE_INFOS',
        {
            'phase8-demo': {
                'title': 'Demo Mod',
                'desc': 'Kisa aciklama',
            }
        },
    )

    result = main_module._show_mode_intro_popup(
        pygame.Surface((1366, 768), pygame.SRCALPHA),
        'phase8-demo',
        settings_manager=settings,
    )

    assert result is False
    _assert_popup_layout_within_recovered_surface(recorded)


def test_zen_start_popup_live_loop_reanchors_to_recovered_surface(monkeypatch):
    recorded = _install_live_popup_stubs(monkeypatch)
    settings = _SettingsStub()

    result = main_module._show_zen_start_popup(
        pygame.Surface((1366, 768), pygame.SRCALPHA),
        board_height=20,
        settings_manager=settings,
    )

    assert result is False
    _assert_popup_layout_within_recovered_surface(recorded)


def test_tutorial_prompt_live_loop_reanchors_to_recovered_surface(monkeypatch):
    recorded = _install_live_popup_stubs(monkeypatch)

    result = main_module._show_tutorial_prompt(
        pygame.Surface((1366, 768), pygame.SRCALPHA),
    )

    # FAZ B: 3 seçenekli popup; ESC artık 'dismiss' döner (falsy uyumlu).
    assert result == 'dismiss'
    _assert_popup_layout_within_recovered_surface(recorded)
    # Üç buton: Hızlı Başlangıç / Akademiyi Aç / Şimdilik Geç
    assert len(recorded['button_rects']) >= 3