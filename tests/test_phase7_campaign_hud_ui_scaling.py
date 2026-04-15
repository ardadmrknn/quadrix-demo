from __future__ import annotations

import math
import pathlib
import sys
import types
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign import campaign_mode as campaign_mode_module


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


def _build_mode(size: tuple[int, int]) -> campaign_mode_module.CampaignMode:
    mode = campaign_mode_module.CampaignMode.__new__(campaign_mode_module.CampaignMode)
    mode.screen = pygame.Surface(size, pygame.SRCALPHA)
    mode.window_width, mode.window_height = size
    return mode


def _install_right_hud_test_stubs(monkeypatch) -> None:
    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
    )
    localization_stub = types.ModuleType('localization')
    localization_stub.t = lambda key, *args, **kwargs: key

    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)
    monkeypatch.setitem(sys.modules, 'localization', localization_stub)


def _prepare_right_hud_mode(size: tuple[int, int]) -> campaign_mode_module.CampaignMode:
    mode = _build_mode(size)
    mode.current_level_num = 7
    mode.is_boss = False
    mode.is_mini_boss = False
    mode._hide_next_pieces = False
    mode._show_hold_x = False
    mode.held_piece = None
    mode.can_hold = True
    mode.next_piece_queue = []
    mode.board = SimpleNamespace(score=12345, lines_cleared=9, level=7, combo=1, tetrises=0)
    mode._draw_hud_glass_panel = lambda rect: None
    mode._draw_custom_frame = lambda rect, asset_name, padding=0, hole_punch=False: False
    mode.draw_textured_block = lambda *args, **kwargs: None
    mode._make_texture_slice = lambda *args, **kwargs: None
    return mode


def test_campaign_hud_scale_preserves_1366_baseline_and_caps_large_display():
    mode = _build_mode((1366, 768))

    assert math.isclose(mode._get_campaign_hud_scale(), 1.0)

    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width = 2560
    mode.window_height = 1440

    assert math.isclose(mode._get_campaign_hud_scale(), 1.12)


def test_campaign_hud_scale_uses_projected_effective_scale(monkeypatch):
    mode = _build_mode((2560, 1660))
    captured = {}

    def fake_get_projected_scale(target, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['target'] = target
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.44

    monkeypatch.setattr(campaign_mode_module, 'get_projected_effective_scale', fake_get_projected_scale)

    assert math.isclose(mode._get_campaign_hud_scale(), 1.44)
    assert captured['target'] is mode.screen
    assert captured['min_scale'] == 0.74
    assert captured['max_scale'] == 1.12
    assert captured['reference_size'] == campaign_mode_module.CAMPAIGN_HUD_REFERENCE_SIZE
    assert captured['display_surface'] is None


def test_campaign_hud_icon_helpers_follow_scaled_target_size():
    mode = _build_mode((800, 600))
    mode.star_icon_small = pygame.Surface((16, 16), pygame.SRCALPHA)
    mode.star_icon_medium = pygame.Surface((20, 20), pygame.SRCALPHA)
    mode.star_icon_large = pygame.Surface((26, 26), pygame.SRCALPHA)
    mode.tick_icon = pygame.Surface((18, 18), pygame.SRCALPHA)

    ui_scale = mode._get_campaign_hud_scale()
    star_icon = mode._get_campaign_star_icon(mode._scale_campaign_hud_px(20, ui_scale, minimum=14))
    tick_icon = mode._get_campaign_tick_icon(mode._scale_campaign_hud_px(18, ui_scale, minimum=14))

    assert star_icon is not None
    assert tick_icon is not None
    assert star_icon.get_width() == 15
    assert tick_icon.get_width() == 14


def test_left_panel_rect_grows_and_keeps_board_gap():
    mode_1366 = _build_mode((1366, 768))
    mode_2560 = _build_mode((2560, 1440))

    rect_1366 = mode_1366._get_campaign_left_panel_rect(520, 80)
    rect_2560 = mode_2560._get_campaign_left_panel_rect(520, 80)

    scale_1366 = mode_1366._get_campaign_hud_scale()
    scale_2560 = mode_2560._get_campaign_hud_scale()
    gap_1366 = mode_1366._scale_campaign_hud_px(20, scale_1366, minimum=0)
    gap_2560 = mode_2560._scale_campaign_hud_px(20, scale_2560, minimum=0)

    assert rect_1366.width == 340
    assert rect_1366.height == 620
    assert rect_2560.width > rect_1366.width
    assert rect_2560.height > rect_1366.height
    assert 520 - rect_1366.right == gap_1366
    assert 520 - rect_2560.right == gap_2560


def test_right_hud_panel_rect_grows_with_scale():
    mode_1366 = _build_mode((1366, 768))
    mode_2560 = _build_mode((2560, 1440))

    rect_1366 = mode_1366._get_campaign_right_hud_panel_rect(430, 70, 300, 620)
    rect_2560 = mode_2560._get_campaign_right_hud_panel_rect(430, 70, 300, 620)

    scale_1366 = mode_1366._get_campaign_hud_scale()
    scale_2560 = mode_2560._get_campaign_hud_scale()

    assert rect_1366.width == 220
    assert rect_2560.width > rect_1366.width
    assert rect_1366.left == 430 + 300 + mode_1366._scale_campaign_hud_px(25, scale_1366, minimum=0)
    assert rect_2560.left == 430 + 300 + mode_2560._scale_campaign_hud_px(25, scale_2560, minimum=0)
    assert rect_2560.right <= 2560


def test_right_hud_draw_updates_scaled_anchor_area(monkeypatch):
    _install_right_hud_test_stubs(monkeypatch)

    mode_1366 = _prepare_right_hud_mode((1366, 768))
    mode_2560 = _prepare_right_hud_mode((2560, 1440))

    mode_1366._draw_right_hud_panel(430, 70, 300, 620, None, None, (255, 255, 255), (0, 255, 255), (180, 180, 180))
    mode_2560._draw_right_hud_panel(430, 70, 300, 620, None, None, (255, 255, 255), (0, 255, 255), (180, 180, 180))

    assert mode_2560._hud_panel_rect.width > mode_1366._hud_panel_rect.width
    assert mode_2560._hud_content_w > mode_1366._hud_content_w
    assert mode_2560._hud_mode_info_area[2] == mode_2560._hud_content_w


def test_right_hud_uses_active_canvas_when_window_size_is_stale(monkeypatch):
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((2560, 1440))
    mode.window_width = 1366
    mode.window_height = 768

    mode._draw_right_hud_panel(430, 70, 300, 620, None, None, (255, 255, 255), (0, 255, 255), (180, 180, 180))

    assert mode._hud_panel_rect.width > 220
    assert mode._hud_mode_info_area[3] > 500