from __future__ import annotations

import math
import pathlib
import sys
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
from game_modes_extra import MysteryCardUI


def _build_game(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    instance = game_module.Game.__new__(game_module.Game)
    instance.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    instance.window_width, instance.window_height = window_size
    return instance


def _install_game_ui_test_stubs(monkeypatch):
    pygame.font.init()

    retro_style_stub = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: pygame.font.Font(None, max(1, int(size))),
        get_fitting_font=lambda text, size, max_width, bold=False: pygame.font.Font(None, max(1, int(size))),
        render_fit_text=lambda text, color, max_width, size, bold=False: pygame.font.Font(None, max(1, int(size))).render(text, True, color),
        accent=(100, 200, 255),
        success=(90, 220, 140),
        secondary=(220, 120, 120),
        primary=(110, 160, 255),
    )
    monkeypatch.setattr(game_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(game_module, 't', lambda key, *args, **kwargs: kwargs.get('default', key))
    monkeypatch.setattr(game_module, 'get_localized_skin_title', lambda skin: '')
    monkeypatch.setattr(game_module, 'get_localized_skin_subtitle', lambda skin: '')


def _build_mystery_mode(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    mode.window_width, mode.window_height = window_size
    mode._card_ui_reference_size = extra_modes_module.MYSTERY_OVERLAY_REFERENCE_SIZE
    mode._card_ui_readable_min_size = (1180, 760)
    return mode


def test_game_ui_scale_uses_active_canvas_and_preserves_1366_baseline():
    game = _build_game((1366, 768), window_size=(800, 600))

    assert math.isclose(game._ui_scale(), 1.0)

    game.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(game._ui_scale(), 1.2)


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


def test_mystery_overlay_scale_can_grow_above_one_without_largest_seen_state():
    ui = MysteryCardUI()

    assert math.isclose(ui._get_overlay_scale(1366, 768), 1.0)
    assert math.isclose(ui._get_overlay_scale(2560, 1440), 1.12)

    another_ui = MysteryCardUI()
    assert math.isclose(another_ui._get_overlay_scale(2560, 1440), 1.12)
    assert math.isclose(another_ui._get_overlay_scale(1366, 768), 1.0)


def test_mystery_mode_card_ui_scale_uses_active_canvas_and_phase8_baseline():
    mode = _build_mystery_mode((1366, 768), window_size=(800, 600))

    assert math.isclose(mode._card_ui_scale(), 1.0)

    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(mode._card_ui_scale(), 1.12)


def test_mystery_mode_live_overlay_uses_active_canvas(monkeypatch):
    recorded = {}

    class CardUIStub:
        def draw_selection_overlay(self, screen, width, height, fonts, choices, hint, debug_enabled, **kwargs):
            recorded['width'] = width
            recorded['height'] = height

    mode = _build_mystery_mode((2560, 1440), window_size=(1366, 768))
    mode._ensure_card_ui_fonts = lambda: None
    mode._build_card_ui_font_pack = lambda: {}
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

    assert recorded == {'width': 2560, 'height': 1440}


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