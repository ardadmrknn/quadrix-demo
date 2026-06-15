from __future__ import annotations

import importlib
import math
import pathlib
import sys
import types
from types import SimpleNamespace

import pygame
import pytest


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module
import game_modes as modes_module
import game_modes_advanced as advanced_modes_module
import game_modes_extra as extra_modes_module
import retro_style as retro_style_module
from game_modes_extra import MysteryCardUI


def test_src_game_modes_extra_package_import_exposes_projected_scale_helper():
    package_module = importlib.import_module('src.game_modes_extra')

    assert hasattr(package_module, 'get_projected_effective_scale')


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
        text_width = max(1, int(len(str(text or '')) * self._size * 0.55))
        return text_width, self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


def _get_game_module():
    import sys
    for name in ('src.game', 'game'):
        m = sys.modules.get(name)
        if m is not None:
            return m
    return game_module


def _get_extra_modes_module():
    import sys
    for name in ('src.game_modes_extra', 'game_modes_extra'):
        m = sys.modules.get(name)
        if m is not None:
            return m
    return extra_modes_module


def _get_game_class():
    return _get_game_module().Game


def _build_game(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    cls = _get_game_class()
    instance = cls.__new__(cls)
    instance.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    instance.window_width, instance.window_height = window_size
    return instance


def _patch_ui_scale_helpers(monkeypatch, attr_name, value):
    import sys
    targets = []
    targets.append(game_module)
    targets.append(extra_modes_module)
    targets.append(_get_game_module())
    targets.append(_get_extra_modes_module())
    for name in ('game', 'src.game', 'game_modes_extra', 'src.game_modes_extra', 'game_modes', 'src.game_modes', 'game_modes_advanced', 'src.game_modes_advanced'):
        m = sys.modules.get(name)
        if m is not None:
            targets.append(m)
    for target in set(targets):
        monkeypatch.setattr(target, attr_name, value, raising=False)


def _install_game_ui_test_stubs(monkeypatch):
    retro_style_stub = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        get_fitting_font=lambda text, size, max_width, bold=False, min_size=None, **kwargs: _make_fake_font(size, bold=bold),
        render_fit_text=lambda text, color, max_width, size, bold=False: _make_fake_font(size, bold=bold).render(text, True, color),
        accent=(100, 200, 255),
        success=(90, 220, 140),
        secondary=(220, 120, 120),
        primary=(110, 160, 255),
    )
    monkeypatch.setattr(game_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(game_module, 't', lambda key, *args, **kwargs: kwargs.get('default', key))
    monkeypatch.setattr(game_module, 'get_localized_skin_title', lambda skin: '')
    monkeypatch.setattr(game_module, 'get_localized_skin_subtitle', lambda skin: '')


def _install_mode_ui_test_stubs(monkeypatch):
    retro_style_stub = SimpleNamespace(
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
    )
    retro_style_module_stub = types.ModuleType('retro_style')
    retro_style_module_stub.retro_style = retro_style_stub
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_module_stub)
    monkeypatch.setattr(retro_style_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(modes_module, 't', lambda key, *args, **kwargs: kwargs.get('default', key))


def _install_extra_mode_ui_test_stubs(monkeypatch):
    retro_style_stub = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        primary=(110, 160, 255),
        secondary=(220, 120, 120),
        accent=(100, 200, 255),
        success=(90, 220, 140),
        text_primary=(255, 255, 255),
        text_secondary=(190, 190, 210),
        text_muted=(130, 130, 150),
        glass_border=(255, 255, 255, 255),
        grid_color=(80, 80, 100),
        bg_color=(12, 16, 24),
    )
    monkeypatch.setattr(extra_modes_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(extra_modes_module, 'get_language', lambda: 'xx')
    monkeypatch.setattr(extra_modes_module, 't', lambda key, *args, **kwargs: kwargs.get('default', str(key).replace('_', ' ')))
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'get_focused', lambda: False)
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'set_visible', lambda *args, **kwargs: None)
    monkeypatch.setattr(extra_modes_module, 'get_mouse_pos', lambda: (0, 0))


def _install_advanced_mode_ui_test_stubs(monkeypatch):
    retro_style_stub = SimpleNamespace(
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
    )
    retro_style_module_stub = types.ModuleType('retro_style')
    retro_style_module_stub.retro_style = retro_style_stub
    localization_stub = types.ModuleType('localization')
    localization_stub.t = lambda key, *args, **kwargs: kwargs.get('default', key)
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_module_stub)
    monkeypatch.setitem(sys.modules, 'localization', localization_stub)


def _get_mystery_mode_class():
    import sys
    for mod in ('game_modes_extra', 'src.game_modes_extra'):
        m = sys.modules.get(mod)
        if m is not None and hasattr(m, 'MysteryMode'):
            return m.MysteryMode
    return extra_modes_module.MysteryMode


def _build_mystery_mode(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    cls = _get_mystery_mode_class()
    mode = cls.__new__(cls)
    mode.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    mode.window_width, mode.window_height = window_size
    
    import sys
    ref_val = None
    for mod in ('game_modes_extra', 'src.game_modes_extra'):
        m = sys.modules.get(mod)
        if m is not None and hasattr(m, 'MYSTERY_OVERLAY_REFERENCE_SIZE'):
            ref_val = m.MYSTERY_OVERLAY_REFERENCE_SIZE
            break
    if ref_val is None:
        ref_val = extra_modes_module.MYSTERY_OVERLAY_REFERENCE_SIZE
        
    mode._card_ui_reference_size = ref_val
    mode._card_ui_readable_min_size = (1180, 760)
    return mode


def test_game_ui_scale_uses_active_canvas_and_preserves_1366_baseline():
    game = _build_game((1366, 768), window_size=(800, 600))

    assert math.isclose(game._ui_scale(), 1.0)

    game.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(game._ui_scale(), 1.24)


def test_game_ui_scale_uses_effective_ui_size_when_available(monkeypatch):
    game = _build_game((2560, 1660), window_size=(1366, 768))
    captured = {}

    def fake_resolve(screen_or_size, *, use_effective_display_size=False, display_surface=None):
        captured['screen'] = screen_or_size
        captured['use_effective_display_size'] = use_effective_display_size
        captured['display_surface'] = display_surface
        return (1200, 700)

    _patch_ui_scale_helpers(monkeypatch, 'resolve_ui_scale_size', fake_resolve)

    expected = min(1200 / 1366.0, 700 / 768.0)
    expected = max(0.72, min(1.24, expected))

    assert math.isclose(game._ui_scale(), expected)
    assert captured['screen'] is game.screen
    assert captured['use_effective_display_size'] is True
    assert captured['display_surface'] is None


def test_game_overlay_ui_scale_uses_projected_effective_scale(monkeypatch):
    game = _build_game((2560, 1660), window_size=(1366, 768))
    captured = {}

    def fake_get_projected_scale(screen_or_size, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['screen_or_size'] = screen_or_size
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.87

    _patch_ui_scale_helpers(monkeypatch, 'get_projected_effective_scale', fake_get_projected_scale)

    assert math.isclose(game._overlay_ui_scale(min_scale=0.68, max_scale=1.16), 1.87)
    assert captured['screen_or_size'] is game.screen
    assert captured['min_scale'] == 0.68
    assert captured['max_scale'] == 1.16
    assert captured['reference_size'] == game_module.GAMEPLAY_UI_REFERENCE_SIZE
    assert captured['display_surface'] is None


@pytest.mark.parametrize('mode_cls', [modes_module.SprintMode, modes_module.UltraMode])
def test_counter_scale_wrappers_can_grow_above_one(mode_cls):
    mode = mode_cls.__new__(mode_cls)
    mode.screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768

    assert math.isclose(mode._counter_scale_from_base(), 1.0)

    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 2560
    mode.window_height = 1440

    assert math.isclose(mode._counter_scale_from_base(), 1.12)


def test_survival_panel_scale_can_grow_above_one():
    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768

    assert math.isclose(mode._survival_panel_scale(), 1.0)

    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 2560
    mode.window_height = 1440

    assert math.isclose(mode._survival_panel_scale(), 1.12)


def test_survival_panel_and_flash_use_active_canvas_when_window_size_is_stale(monkeypatch):
    created_sizes = []
    original_surface = advanced_modes_module.pygame.Surface

    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = original_surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.game_over = False
    mode.survival_time = 1000
    mode.antivirus_flash = 250
    mode.infected_blocks = {}
    mode.board_width = 10
    mode.board_height = 20
    mode.virus_level = 1
    mode.consumed_count = 2
    mode.MAX_CONSUMED = 20
    mode.consume_time = 60000
    mode.last_antivirus_score = 0
    mode.max_infected = 15
    mode.fog_overlay = False
    mode.board = SimpleNamespace(score=2000, lines_cleared=4, level=2)
    mode.get_cell_size = lambda: 24
    mode.get_board_offset = lambda: (430, 70)
    mode._draw_survival_panel = lambda: None

    def surface_spy(size, *args, **kwargs):
        created_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    monkeypatch.setattr(advanced_modes_module.pygame, 'Surface', surface_spy)

    advanced_modes_module.SurvivalMode.draw_mode_overlay(mode)

    assert created_sizes[0] == (2560, 1440)


def test_survival_panel_rect_stays_within_active_canvas(monkeypatch):
    _install_advanced_mode_ui_test_stubs(monkeypatch)
    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.board = SimpleNamespace(score=4000, lines_cleared=12)
    mode.survival_time = 120000
    mode.MAX_CONSUMED = 20
    mode.consumed_count = 5
    mode.virus_level = 3
    mode.infected_blocks = {(1, 1): 0, (2, 2): 1000}
    mode.max_infected = 15
    mode.last_antivirus_score = 0
    mode.ANTIVIRUS_SCORE = 5000
    mode.get_board_offset = lambda: (430, 70)

    advanced_modes_module.SurvivalMode._draw_survival_panel(mode)

    assert mode._survival_panel_rect.right <= 2560
    assert mode._survival_panel_rect.bottom <= 1440
    assert mode._survival_panel_rect.x >= 0
    assert mode._survival_panel_rect.y >= 0


def test_survival_victory_particles_use_active_canvas_center():
    recorded = {}
    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.effects_enabled = True
    mode.MAX_CONSUMED = 20
    mode.consumed_count = 3
    mode.board = SimpleNamespace(score=1000, lines_cleared=5)
    mode.sound = SimpleNamespace(play=lambda name: None)
    mode.trigger_screen_shake = lambda intensity, duration: None
    mode.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y))
    mode.finalize_run = lambda playtime=None: recorded.setdefault('playtime', playtime)
    mode.survival_time = 42000

    advanced_modes_module.SurvivalMode._handle_survival_victory(mode)

    assert recorded['particles'] == [(1280, 720)]
    assert recorded['playtime'] == 42


def test_survival_virus_game_over_particles_use_active_canvas_center():
    recorded = {}
    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.effects_enabled = True
    mode.consumed_count = 20
    mode.board = SimpleNamespace(score=1000, lines_cleared=5)
    mode.sound = SimpleNamespace(play_game_over_sequence=lambda: None)
    mode.trigger_screen_shake = lambda intensity, duration: None
    mode.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y))
    mode.finalize_run = lambda playtime=None: recorded.setdefault('playtime', playtime)
    mode.survival_time = 31000

    advanced_modes_module.SurvivalMode._handle_virus_game_over(mode)

    assert recorded['particles'] == [(1280, 720)]
    assert recorded['playtime'] == 31


def test_daily_fog_overlay_uses_active_canvas(monkeypatch):
    created_sizes = []
    original_surface = advanced_modes_module.pygame.Surface

    mode = advanced_modes_module.DailyChallengeMode.__new__(advanced_modes_module.DailyChallengeMode)
    mode.screen = original_surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.fog_overlay = True
    mode.game_over = False
    mode._daily_failed = False
    mode.draw_mode_info = lambda *args, **kwargs: None

    def surface_spy(size, *args, **kwargs):
        created_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    monkeypatch.setattr(advanced_modes_module.pygame, 'Surface', surface_spy)

    original_super = advanced_modes_module.SurvivalMode.draw_mode_overlay
    monkeypatch.setattr(advanced_modes_module.SurvivalMode, 'draw_mode_overlay', lambda self: None)
    try:
        advanced_modes_module.DailyChallengeMode.draw_mode_overlay(mode)
    finally:
        monkeypatch.setattr(advanced_modes_module.SurvivalMode, 'draw_mode_overlay', original_super)

    assert created_sizes[0] == (2560, 1440)


def test_mystery_overlay_scale_can_grow_above_one_without_largest_seen_state():
    ui = MysteryCardUI()

    assert math.isclose(ui._get_overlay_scale(1366, 768), 1.0)
    assert math.isclose(ui._get_overlay_scale(2560, 1440), 1.12)

    another_ui = MysteryCardUI()
    assert math.isclose(another_ui._get_overlay_scale(2560, 1440), 1.12)
    assert math.isclose(another_ui._get_overlay_scale(1366, 768), 1.0)


def test_mystery_overlay_scale_uses_projected_effective_scale_when_screen_passed(monkeypatch):
    ui = MysteryCardUI()
    screen = pygame.Surface((2560, 1660), pygame.SRCALPHA)
    captured = {}

    def fake_get_projected_scale(target, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['target'] = target
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.64

    monkeypatch.setattr(extra_modes_module, 'get_projected_effective_scale', fake_get_projected_scale)

    assert math.isclose(ui._get_overlay_scale(screen), 1.64)
    assert captured['target'] is screen
    assert captured['min_scale'] >= 0.62
    assert captured['max_scale'] == 1.12
    assert captured['reference_size'] == tuple(float(v) for v in extra_modes_module.MYSTERY_OVERLAY_REFERENCE_SIZE)
    assert captured['display_surface'] is None


def test_mystery_mode_card_ui_scale_uses_active_canvas_and_phase8_baseline():
    mode = _build_mystery_mode((1366, 768), window_size=(800, 600))

    assert math.isclose(mode._card_ui_scale(), 1.0)

    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(mode._card_ui_scale(), 1.12)


def test_mystery_mode_card_ui_scale_uses_projected_effective_scale(monkeypatch):
    mode = _build_mystery_mode((2560, 1660), window_size=(1366, 768))
    captured = {}

    def fake_get_projected_scale(target, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['target'] = target
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.58

    monkeypatch.setattr(extra_modes_module, 'get_projected_effective_scale', fake_get_projected_scale)

    assert math.isclose(mode._card_ui_scale(), 1.58)
    assert captured['target'] is mode.screen
    assert captured['min_scale'] >= 0.62
    assert captured['max_scale'] == 1.12
    assert captured['reference_size'] == tuple(float(v) for v in extra_modes_module.MYSTERY_OVERLAY_REFERENCE_SIZE)
    assert captured['display_surface'] is None


def test_mystery_gameplay_layout_can_grow_beyond_legacy_40px_cap():
    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode.board_width = 10
    mode.board_height = 20
    mode.left_panel_max_width = 420

    left_panel_width, right_panel_width = mode._get_side_panel_widths()

    assert mode.get_cell_size() > 40
    assert left_panel_width > 320
    assert right_panel_width > 220


def test_mystery_gameplay_layout_centers_board_between_side_panels():
    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode.board_width = 10
    mode.board_height = 20
    mode.left_panel_max_width = 420

    metrics = mode._get_mystery_layout_metrics()

    left_margin = int(metrics['board_x']) - int(metrics['left_panel_width']) - int(metrics['panel_gap'])
    right_margin = 2560 - (int(metrics['panel_x']) + int(metrics['panel_width']))

    assert abs(left_margin - right_margin) <= 2


def test_mystery_gameplay_layout_projects_effective_metrics_back_to_raw_pixels(monkeypatch):
    mode = _build_mystery_mode((2940, 1912), window_size=(1470, 956))
    mode.board_width = 10
    mode.board_height = 20
    mode.left_panel_max_width = 420

    monkeypatch.setattr(mode, '_effective_ui_size', lambda: (1470, 956))

    metrics = mode._get_mystery_layout_metrics()

    assert mode.get_cell_size() >= 80
    assert int(metrics['panel_width']) >= 380
    assert int(metrics['left_panel_width']) >= 640


def test_mystery_mode_live_overlay_uses_active_canvas(monkeypatch):
    recorded = {}

    class CardUIStub:
        def _get_overlay_scale(self, screen):
            recorded['screen_size'] = screen.get_size()
            return 1.0

        def draw_selection_overlay(self, screen, width, height, fonts, choices, hint, debug_enabled, **kwargs):
            recorded['width'] = width
            recorded['height'] = height

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode._ensure_card_ui_fonts = lambda: None
    mode._build_card_ui_font_pack = lambda *args, **kwargs: {}
    mode.card_ui = CardUIStub()
    mode.card_selection_active = True
    mode.card_message = ''
    mode.card_message_timer = 0
    mode.card_manager = SimpleNamespace(pending_choices=[{'id': 'demo'}], get_selection_hint=lambda: '')
    mode.settings_manager = SimpleNamespace(get=lambda key, default=None: default)
    mode._draw_status_panel = lambda: None
    mode.draw_mode_info = lambda *args, **kwargs: None
    mode._draw_persistent_cards_icon_panel = lambda: None
    mode._draw_sniper_explosion_effects = lambda: None
    mode._sniper_overlay_active = False
    mode._piece_selection_active = False
    mode._card_workshop_active = False

    extra_modes_module.MysteryMode.draw_mode_overlay(mode)

    assert recorded == {'screen_size': (2560, 1440), 'width': 2560, 'height': 1440}


@pytest.mark.parametrize('size', [(2560, 1600), (1600, 900)])
def test_mystery_card_selection_overlay_keeps_text_blocks_inside_cards(monkeypatch, size):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    ui = MysteryCardUI()
    ui.fade_alpha = 220
    ui._last_dt = 1500.0

    mode = _build_mystery_mode(size, window_size=(1366, 768))
    screen = pygame.Surface(size, pygame.SRCALPHA)
    fonts = mode._build_card_ui_font_pack(ui._get_overlay_scale(screen))

    cards = [
        {
            'id': f'demo-{index}',
            'title': 'Sonsuz Blok Karistirici Protokolu',
            'description': 'Uzun aciklama satirlari kart icinde kalmali ve farkli ekran oranlarinda buton alanina tasmamali.',
            'value': 3,
            'icon': '*',
            'icon_image': None,
            'tag': 'Tek Kullanim',
            'style': {},
            'rarity': 'common',
        }
        for index in range(3)
    ]

    ui.draw_selection_overlay(screen, size[0], size[1], fonts, cards, '', False)

    assert ui.selection_panel_rect is not None
    assert ui.selection_panel_rect.right <= size[0]
    assert ui.selection_panel_rect.bottom <= size[1]
    assert ui.skip_button_rect is not None
    assert ui.reroll_button_rect is not None
    assert max(rect.bottom for rect in ui.card_rects) < ui.skip_button_rect.top

    for rect, widget in zip(ui.card_rects, ui.card_widgets):
        snapshot = widget._face_layout_snapshot

        assert snapshot
        assert snapshot['card_size'] == (rect.width, rect.height)

        icon_rect = snapshot['icon_rect']
        title_rect = snapshot['title_rect']
        type_rect = snapshot['type_rect']
        hotkey_rect = snapshot['hotkey_rect']
        desc_bg_rect = snapshot['desc_bg_rect']

        assert 0 <= icon_rect.left < icon_rect.right <= rect.width
        assert 0 <= title_rect.left < title_rect.right <= rect.width
        assert 0 <= type_rect.left < type_rect.right <= rect.width
        assert 0 <= hotkey_rect.left < hotkey_rect.right <= rect.width
        assert title_rect.top >= icon_rect.bottom
        assert type_rect.top >= title_rect.bottom
        assert desc_bg_rect is not None
        assert 0 <= desc_bg_rect.left < desc_bg_rect.right <= rect.width
        assert 0 <= desc_bg_rect.top < desc_bg_rect.bottom <= rect.height
        assert desc_bg_rect.top >= type_rect.bottom
        assert desc_bg_rect.bottom <= hotkey_rect.top
        assert snapshot['desc_line_count'] >= 1
        assert fonts['card_title'].size(snapshot['title_text'])[0] <= rect.width - max(20, int(rect.width * 0.12))


def test_mystery_card_selection_description_shrinks_instead_of_ellipsis(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)
    monkeypatch.setattr(
        extra_modes_module,
        't',
        lambda key, *args, **kwargs: key
        if str(key).startswith('card_') and str(key).endswith(('_title', '_desc'))
        else kwargs.get('default', str(key).replace('_', ' ')),
    )

    ui = MysteryCardUI()
    ui.fade_alpha = 220
    ui._last_dt = 1500.0

    size = (1366, 768)
    mode = _build_mystery_mode(size)
    screen = pygame.Surface(size, pygame.SRCALPHA)
    fonts = mode._build_card_ui_font_pack(ui._get_overlay_scale(screen))

    long_description = (
        'Ölümden Dönüş: Oyun bitecekken üst yarıyı temizler ve sana güvenli '
        'bir devam alanı açar; kalan bloklar dengelenir, kombo fırsatı korunur, '
        'hamle ritmi bozulmadan devam edersin.'
    )
    cards = [
        {
            'id': 'long_desc_demo',
            'title': 'İkinci Şans',
            'description': long_description,
            'value': 3,
            'icon': '*',
            'icon_image': None,
            'tag': 'Tek Kullanim',
            'style': {},
            'rarity': 'common',
        }
    ]

    ui.draw_selection_overlay(screen, size[0], size[1], fonts, cards, '', False)

    snapshot = ui.card_widgets[0]._face_layout_snapshot
    desc_lines = snapshot['desc_lines']
    desc_bg_rect = snapshot['desc_bg_rect']
    hotkey_rect = snapshot['hotkey_rect']

    assert desc_lines
    assert all('...' not in line for line in desc_lines)
    assert 'devam edersin' in ' '.join(desc_lines)
    assert snapshot['desc_font_height'] < fonts['desc'].get_height()
    assert desc_bg_rect.bottom <= hotkey_rect.top


def test_mystery_card_workshop_popup_uses_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    created_sizes = []
    original_surface = extra_modes_module.pygame.Surface

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode._card_workshop_active = True
    mode._card_workshop_peek_active = False
    mode.mystery_font_large = _make_fake_font(40)
    mode.mystery_font_small = _make_fake_font(26)
    mode._get_cached_peek_icon = lambda size: None
    mode._card_workshop_grid = [[None for _ in range(7)] for _ in range(7)]
    mode._card_workshop_cursor_x = 0
    mode._card_workshop_cursor_y = 0
    mode._card_workshop_count_blocks = lambda: 0

    def surface_spy(size, *args, **kwargs):
        created_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    monkeypatch.setattr(extra_modes_module.pygame, 'Surface', surface_spy)

    extra_modes_module.MysteryMode._draw_card_workshop_popup(mode)

    assert created_sizes[0] == (2560, 1440)
    assert mode._card_workshop_popup_rect.right <= 2560
    assert mode._card_workshop_popup_rect.bottom <= 1440
    assert mode._card_workshop_grid_rect.right <= mode._card_workshop_popup_rect.right
    assert mode._card_workshop_grid_rect.bottom <= mode._card_workshop_popup_rect.bottom
    assert mode._card_workshop_info_rect.bottom <= mode._card_workshop_popup_rect.bottom
    assert mode._card_workshop_controls_rect.bottom <= mode._card_workshop_popup_rect.bottom


def test_mystery_card_workshop_popup_compacts_content_to_fit_min_window(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    mode = _build_mystery_mode((800, 600), window_size=(1366, 768))
    mode._card_workshop_active = True
    mode._card_workshop_peek_active = False
    mode.mystery_font_large = _make_fake_font(40)
    mode.mystery_font_small = _make_fake_font(26)
    mode._get_cached_peek_icon = lambda size: None
    mode._card_workshop_grid = [[None for _ in range(7)] for _ in range(7)]
    mode._card_workshop_cursor_x = 3
    mode._card_workshop_cursor_y = 3
    mode._card_workshop_message = 'Baglanti gerekli'
    mode._card_workshop_message_timer = 1.0
    mode._card_workshop_count_blocks = lambda: 5

    extra_modes_module.MysteryMode._draw_card_workshop_popup(mode)

    popup_rect = mode._card_workshop_popup_rect
    assert popup_rect.right <= 800
    assert popup_rect.bottom <= 600
    assert mode._card_workshop_grid_rect.bottom <= mode._card_workshop_info_rect.top
    assert mode._card_workshop_info_rect.bottom < mode._card_workshop_controls_rect.top
    assert mode._card_workshop_controls_rect.bottom <= popup_rect.bottom


def test_mystery_piece_selection_popup_uses_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    created_sizes = []
    original_surface = extra_modes_module.pygame.Surface

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode._piece_selection_active = True
    mode._future_changer_target_index = 1
    mode.mystery_font_large = _make_fake_font(40)
    mode.mystery_font_small = _make_fake_font(26)
    mode._draw_game_piece_preview = lambda rect, name, hovered=False: None

    def surface_spy(size, *args, **kwargs):
        created_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    monkeypatch.setattr(extra_modes_module.pygame, 'Surface', surface_spy)

    extra_modes_module.MysteryMode._draw_piece_selection_popup(mode)

    assert created_sizes[0] == (2560, 1440)
    assert mode._piece_selection_popup_rect.right <= 2560
    assert mode._piece_selection_popup_rect.bottom <= 1440
    assert len(mode._piece_selection_rects) == 7
    assert all(rect.right <= mode._piece_selection_popup_rect.right for rect, _ in mode._piece_selection_rects)


def test_mystery_sniper_overlay_and_instruction_panel_use_active_canvas(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    created_sizes = []
    original_surface = extra_modes_module.pygame.Surface

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode.board = SimpleNamespace(
        width=10,
        height=20,
        occupancy=[[False for _ in range(10)] for _ in range(20)],
    )
    mode._hud_mode_info_area = (2200, 120, 240, 400)
    mode.get_board_offset = lambda: (430, 70)
    mode.get_cell_size = lambda: 24
    mode._sniper_screen_to_cell = lambda pos: None

    def surface_spy(size, *args, **kwargs):
        created_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    monkeypatch.setattr(extra_modes_module, 'get_mouse_pos', lambda: (450, 120))
    monkeypatch.setattr(extra_modes_module, 'get_display_scale_factor', lambda: 1.0)
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'set_pos', lambda *args, **kwargs: None)
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'set_visible', lambda *args, **kwargs: None)
    monkeypatch.setattr(extra_modes_module.pygame, 'Surface', surface_spy)

    extra_modes_module.MysteryMode._draw_sniper_board_overlay(mode)

    assert created_sizes[0] == (2560, 1440)
    assert mode._sniper_instruction_panel_rect.right <= 2560
    assert mode._sniper_instruction_panel_rect.bottom <= 1440
    assert mode._sniper_instruction_panel_rect.width >= 220


def test_mystery_card_particles_use_active_canvas_center():
    recorded = {}

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode.effects_enabled = True
    mode.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y, count, tuple(colors[0])))

    extra_modes_module.MysteryMode._spawn_card_particles(mode, (10, 20, 30))

    assert recorded['particles'] == [(1280, 720, 30, (10, 20, 30))]


def test_base_game_right_hud_uses_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_game_ui_test_stubs(monkeypatch)

    game = _build_game((2560, 1440), window_size=(1366, 768))
    game.next_piece_queue = []
    game.held_piece = None
    game.can_hold = True
    game.board = SimpleNamespace(score=12000, lines_cleared=8, level=5, combo=1, tetrises=0)
    game._draw_hud_glass_panel = lambda rect: None
    game._draw_custom_frame = lambda rect, asset_name, padding=0, hole_punch=False: False
    game.draw_textured_block = lambda *args, **kwargs: None
    game._make_texture_slice = lambda *args, **kwargs: None
    game.control_bindings = {}
    game.perk_manager = None

    game_module.Game._draw_right_hud_panel(game, 430, 70, 300, 620, None, None, (255, 255, 255), (0, 255, 255), (180, 180, 180))

    assert game._hud_panel_rect.width > 220
    assert game._hud_panel_rect.right <= 2560
    assert game._hud_mode_info_area[3] > 500


def test_game_over_overlay_uses_active_canvas_for_gradient_cache(monkeypatch):
    _install_game_ui_test_stubs(monkeypatch)
    monkeypatch.setattr(game_module, 'get_mouse_pos', lambda: (0, 0))
    monkeypatch.setattr(game_module.pygame.mouse, 'get_focused', lambda: False)

    game = _build_game((2560, 1440), window_size=(1366, 768))
    game.board = SimpleNamespace(score=42000, lines_cleared=40, level=9, tetrises=12, max_combo=4)
    game.game_time = 125000
    game.game_mode = 'classic'
    game.user_manager = None
    game.sound_enabled = False
    game._game_over_peek_active = False
    game._draw_confetti = lambda: None
    game._update_confetti = lambda current_time: None
    game._calculate_stars = lambda: 0.0
    game._check_new_record = lambda: False
    game._draw_star = lambda *args, **kwargs: None
    game._get_cached_peek_icon = lambda size: None
    game.can_restart = lambda: True
    game.game_over_warning = ''
    game.game_over_warning_timer = 0

    game_module.Game._draw_game_over_overlay(game, None)

    assert getattr(game, '_go_gradient_cache_key') == (2560, 1440)


def test_hardcore_right_hud_uses_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_mode_ui_test_stubs(monkeypatch)

    mode = modes_module.HardcoreMode.__new__(modes_module.HardcoreMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 960
    mode.window_height = 700
    mode.board = SimpleNamespace(score=12000, lines_cleared=8, level=5)
    mode._draw_hud_glass_panel = lambda rect: None

    modes_module.HardcoreMode._draw_right_hud_panel(
        mode,
        430,
        70,
        300,
        620,
        None,
        None,
        (255, 255, 255),
        (0, 255, 255),
        (180, 180, 180),
    )

    assert mode._hud_panel_rect.width > 240
    assert mode._hud_panel_rect.right <= 2560
    assert mode._hud_mode_info_area[3] > 500


@pytest.mark.parametrize('size', [(1366, 768), (1600, 900), (2560, 1600)])
def test_mystery_second_pocket_hud_stays_on_primary_hold_row(monkeypatch, size):
    _install_game_ui_test_stubs(monkeypatch)

    mode = _build_mystery_mode(size, window_size=(1366, 768))
    mode.next_piece_queue = [
        SimpleNamespace(shape=[[1, 1], [1, 1]], color=(120, 220, 255), texture_surface=None, color_matrix=None),
        SimpleNamespace(shape=[[1, 1, 1, 1]], color=(255, 200, 120), texture_surface=None, color_matrix=None),
    ]
    mode.held_piece = SimpleNamespace(shape=[[1, 1], [1, 1]], color=(120, 255, 180), texture_surface=None, color_matrix=None)
    mode.second_held_piece = SimpleNamespace(shape=[[1, 1, 1], [0, 1, 0]], color=(255, 140, 180), texture_surface=None, color_matrix=None)
    mode.can_hold = True
    mode.can_hold2 = True
    mode.board = SimpleNamespace(score=12000, lines_cleared=8, level=5, combo=1, tetrises=0)
    mode._draw_hud_glass_panel = lambda rect: None
    mode._draw_custom_frame = lambda rect, asset_name, padding=0, hole_punch=False: False
    mode.draw_textured_block = lambda *args, **kwargs: None
    mode._make_texture_slice = lambda *args, **kwargs: None
    mode.control_bindings = {'hold2': pygame.K_v}
    mode.perk_manager = SimpleNamespace(is_active=lambda perk: perk == 'second_pocket')

    metrics = mode._get_mystery_layout_metrics()
    game_module.Game._draw_right_hud_panel(
        mode,
        metrics['board_x'],
        metrics['board_y'],
        metrics['board_width'],
        metrics['board_height'],
        None,
        None,
        (255, 255, 255),
        (0, 255, 255),
        (180, 180, 180),
    )

    assert len(mode._hud_next_piece_rects) == 2
    assert mode._hud_next_piece_rects[0].top == mode._hud_next_piece_rects[1].top
    assert mode._hud_next_piece_rects[1].left > mode._hud_next_piece_rects[0].right

    assert mode._hud_hold_box_rect is not None
    assert mode._hud_second_hold_box_rect is not None
    assert mode._hud_second_hold_box_rect.top == mode._hud_hold_box_rect.top
    assert mode._hud_second_hold_box_rect.left > mode._hud_hold_box_rect.right
    assert mode._hud_hold_label_rect is not None
    assert mode._hud_second_hold_label_rect is not None
    assert mode._hud_hold_label_rect.left > mode._hud_content_x
    assert mode._hud_second_hold_label_rect.left > mode._hud_second_hold_box_rect.left
    assert mode._hud_hold_label_rect.top < mode._hud_hold_box_rect.top
    assert mode._hud_second_hold_label_rect.top < mode._hud_second_hold_box_rect.top

    assert mode._hud_panel_rect.contains(mode._hud_next_piece_rects[0])
    assert mode._hud_panel_rect.contains(mode._hud_next_piece_rects[1])
    assert mode._hud_panel_rect.contains(mode._hud_hold_label_rect)
    assert mode._hud_panel_rect.contains(mode._hud_hold_box_rect)
    assert mode._hud_panel_rect.contains(mode._hud_second_hold_label_rect)
    assert mode._hud_panel_rect.contains(mode._hud_second_hold_box_rect)


@pytest.mark.parametrize('lines_cleared', [2, 4])
def test_zen_line_clear_particles_use_active_canvas_center(lines_cleared):
    recorded = {}

    mode = modes_module.ZenMode.__new__(modes_module.ZenMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.effects_enabled = True
    mode.sound = SimpleNamespace(play=lambda name: None)
    mode.trigger_screen_shake = lambda intensity, duration: None
    mode.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y, count))
    mode.create_line_clear_particles = lambda *args, **kwargs: None
    mode._start_block_fall_animation = lambda *args, **kwargs: None
    mode.line_clear_wave_effects = []
    mode.relaxation_bonus = 0
    mode.achievement_manager = None
    mode.achievement_notifications = []
    mode.game_mode = 'zen'
    mode.next_piece_queue = [SimpleNamespace()]
    mode.spawn_new_piece = lambda: SimpleNamespace()
    mode.apply_theme_to_pieces = lambda: None
    mode._ensure_relaxed_space = lambda: None
    mode.board_width = 10
    mode.board_height = 20
    mode.current_piece = SimpleNamespace(get_cells=lambda: [], color=(255, 255, 255), x=0, y=0)
    mode.get_cell_size = lambda: 24
    mode.get_board_offset = lambda: (430, 70)
    mode.board = SimpleNamespace(
        lock_piece=lambda piece: lines_cleared,
        last_cleared_lines=[0, 1, 2, 3][:lines_cleared],
        last_cleared_colors={},
        score=1000,
        lines_cleared=10,
        level=3,
        tetrises=1,
        combo=2,
        is_valid_position=lambda piece: True,
        _locked_out=False,
        clear_lock_out=lambda: None,
        is_game_over=lambda: False,
    )

    modes_module.ZenMode.lock_and_new_piece(mode)

    expected_count = 150 if lines_cleared == 4 else 50 * lines_cleared
    assert recorded['particles'] == [(1280, 720, expected_count)]


def test_zen_auto_clear_particles_use_active_canvas_center():
    recorded = {}

    mode = modes_module.ZenMode.__new__(modes_module.ZenMode)
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 1366
    mode.window_height = 768
    mode.effects_enabled = True
    mode.sound_enabled = False
    mode.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y, count))
    mode.auto_clear_rows = 2
    mode.auto_clears = 0
    mode.auto_clear_penalty = 0
    mode.current_piece = SimpleNamespace(x=0, y=0)
    mode.board = SimpleNamespace(
        width=10,
        height=20,
        grid=[[extra_modes_module.BLACK for _ in range(10)] for _ in range(20)],
        texture_grid=[[None for _ in range(10)] for _ in range(20)],
        occupancy=[[False for _ in range(10)] for _ in range(20)],
        is_valid_position=lambda piece: True,
    )

    modes_module.ZenMode.auto_clear_board(mode, clear_entire_board=False)

    assert recorded['particles'] == [(1280, 360, 50)]


def test_zen_auto_clear_triggers_on_top_boundary_lock_out():
    recorded = []

    mode = modes_module.ZenMode.__new__(modes_module.ZenMode)
    mode.effects_enabled = False
    mode.sound = SimpleNamespace(play=lambda name: recorded.append(name))
    mode.auto_clear_triggered = False
    mode.auto_clear_board = lambda clear_entire_board=False: recorded.append(('clear', clear_entire_board))
    mode.apply_theme_to_pieces = lambda: None
    mode.next_piece_queue = [SimpleNamespace(x=0, y=0)]
    mode.spawn_new_piece = lambda: SimpleNamespace(x=0, y=0)
    mode.current_piece = SimpleNamespace(get_cells=lambda: [], color=(255, 255, 255), x=0, y=0)
    mode.board = SimpleNamespace(
        lock_piece=lambda piece: 0,
        consume_last_lock_out=lambda: True,
        clear_lock_out=lambda: None,
        is_valid_position=lambda piece: True,
    )

    modes_module.ZenMode.lock_and_new_piece(mode)

    assert ('clear', False) in recorded
    assert mode.auto_clear_triggered is True


def test_zen_auto_clear_ignores_dense_top_without_boundary_overflow():
    recorded = []

    mode = modes_module.ZenMode.__new__(modes_module.ZenMode)
    mode._pending_top_out_auto_clear = False
    mode.auto_clear_triggered = False
    mode.auto_clear_board = lambda clear_entire_board=False: recorded.append(clear_entire_board)
    mode.current_piece = SimpleNamespace(x=0, y=0)
    mode.board = SimpleNamespace(
        width=10,
        height=20,
        occupancy=[[True] * 9 + [False] for _ in range(4)] + [[False] * 10 for _ in range(16)],
        is_valid_position=lambda piece: True,
    )

    modes_module.ZenMode._ensure_relaxed_space(mode)

    assert recorded == []
    assert mode.auto_clear_triggered is False


def test_base_game_geometry_uses_active_canvas_when_window_size_is_stale():
    game = _build_game((2560, 1440), window_size=(1366, 768))
    game.board_width = 20
    game.board_height = 40

    cell_size = game.get_cell_size()
    offset_x, offset_y = game.get_board_offset()

    assert cell_size == (1440 - game_module.INFO_PANEL_HEIGHT) // game.board_height
    assert offset_x > 600
    assert offset_x + (game.board_width * cell_size) < 2560
    assert offset_y >= 0
    assert offset_y + (game.board_height * cell_size) < 1440


def test_base_game_large_display_layout_can_grow_beyond_legacy_40px_cap():
    game = _build_game((2560, 1440), window_size=(1366, 768))
    game.board_width = 10
    game.board_height = 20

    layout = game._get_gameplay_layout_metrics()

    assert game.get_cell_size() > 40
    assert layout.panel_width > 220
    assert layout.board_x + layout.board_width < 2560
    assert layout.board_y + layout.board_height < 1440


def test_base_game_layout_centers_board_when_no_left_panel_reserve():
    game = _build_game((1366, 768))
    game.board_width = 10
    game.board_height = 20

    layout = game._get_gameplay_layout_metrics()

    expected_board_x = (1366 - layout.board_width) // 2
    assert abs(layout.board_x - expected_board_x) <= 2


def test_base_game_layout_respects_left_panel_reserve_hook():
    game = _build_game((1366, 768))
    game.board_width = 10
    game.board_height = 20
    game._get_left_gameplay_reserve_width = lambda: 260

    layout = game._get_gameplay_layout_metrics()

    left_margin = layout.board_x - 260
    right_margin = 1366 - (layout.panel_x + layout.panel_width)

    assert abs(left_margin - right_margin) <= 2


def test_base_game_layout_cache_tracks_left_panel_reserve_width():
    game = _build_game((1366, 768))
    game.board_width = 10
    game.board_height = 20
    game._get_left_gameplay_reserve_width = lambda: 260

    layout_with_left_panel = game._get_gameplay_layout_metrics()

    game._get_left_gameplay_reserve_width = lambda: 0
    layout_without_left_panel = game._get_gameplay_layout_metrics()

    assert layout_without_left_panel.board_x < layout_with_left_panel.board_x


def test_base_game_layout_projects_effective_retina_metrics_back_to_raw_pixels(monkeypatch):
    game = _build_game((2940, 1912), window_size=(1470, 956))
    game.board_width = 10
    game.board_height = 20

    monkeypatch.setattr(game, '_effective_ui_size', lambda: (1470, 956))

    layout = game._get_gameplay_layout_metrics()

    assert layout.logical_cell_size > 40
    assert layout.cell_size >= 80
    assert layout.panel_width >= 440


@pytest.mark.parametrize('lines_cleared', [2, 4])
def test_base_game_line_clear_particles_use_active_canvas_center(monkeypatch, lines_cleared):
    recorded = {}

    monkeypatch.setattr(game_module, 'get_gamepad_manager', lambda: SimpleNamespace(rumble=lambda *args, **kwargs: None))

    game = _build_game((2560, 1440), window_size=(1366, 768))
    game.effects_enabled = True
    game.sound = SimpleNamespace(play=lambda name: None, play_game_over_sequence=lambda: None)
    game.trigger_screen_shake = lambda intensity, duration: None
    game.create_particles = lambda count, x, y, colors, speed=0: recorded.setdefault('particles', []).append((x, y, count))
    game.create_line_clear_particles = lambda *args, **kwargs: None
    game._start_block_fall_animation = lambda *args, **kwargs: None
    game.line_clear_wave_effects = []
    game.get_cell_size = lambda: 24
    game.get_board_offset = lambda: (430, 70)
    game.next_piece_queue = [SimpleNamespace()]
    game.spawn_new_piece = lambda: SimpleNamespace()
    game.apply_theme_to_pieces = lambda: None
    game.get_current_speed = lambda: 1000
    game.board_width = 10
    game.board_height = 20
    game.current_piece = SimpleNamespace(get_cells=lambda: [], color=(255, 255, 255), x=0, y=0)
    game.board = SimpleNamespace(
        lock_piece=lambda piece: lines_cleared,
        last_cleared_lines=[0, 1, 2, 3][:lines_cleared],
        last_cleared_colors={},
        width=10,
        height=20,
        score=1000,
        lines_cleared=10,
        level=3,
        tetrises=1,
        combo=2,
        is_valid_position=lambda piece: True,
        is_game_over=lambda: False,
    )
    game.achievement_manager = None
    game.achievement_notifications = []
    game.game_mode = 'classic'

    game_module.Game.lock_and_new_piece(game)

    expected_count = 150 if lines_cleared == 4 else 50 * lines_cleared
    assert recorded['particles'] == [(1280, 720, expected_count)]


def test_mystery_geometry_and_panels_use_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode.board_width = 10
    mode.board_height = 20
    mode.left_panel_max_width = 420
    mode._left_panel_frame = (20, 20, 400)
    mode._left_panel_cards_y = 120
    mode._draw_hud_glass_panel = lambda rect: None
    mode._sync_active_cards = lambda: None
    mode.card_manager = SimpleNamespace(active_cards=[])
    mode.card_ui = SimpleNamespace(draw_active_cards_panel=lambda *args, **kwargs: 0)
    mode.selected_cards_log = []
    mode._fit_text_to_width = lambda font, text, max_width: text
    mode._build_card_ui_font_pack = lambda ui_scale=None: {
        'panel_header': _make_fake_font(17),
        'small': _make_fake_font(11),
    }
    mode._hud_panel_rect = pygame.Rect(2140, 110, 300, 520)

    metrics = mode._get_mystery_layout_metrics()
    cell_size = mode.get_cell_size()
    board_x, board_y = mode.get_board_offset()
    left_w, right_w = mode._get_side_panel_widths(mode.board_width * cell_size)

    assert cell_size == int(metrics['cell_size'])
    assert (board_x, board_y) == (int(metrics['board_x']), int(metrics['board_y']))
    assert left_w == int(metrics['left_panel_width'])
    assert right_w == int(metrics['right_panel_width'])
    assert cell_size > 40

    extra_modes_module.MysteryMode.draw_mode_info(mode, 0, 0)
    extra_modes_module.MysteryMode._draw_persistent_cards_icon_panel(mode)

    assert mode._active_cards_panel_rect.bottom <= 1440
    assert mode._persistent_cards_panel_rect.right <= 2560
    assert mode._persistent_cards_panel_rect.bottom <= 1440
