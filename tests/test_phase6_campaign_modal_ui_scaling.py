from __future__ import annotations

import math
import pathlib
import sys
import types

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign import campaign_ui


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


def _install_modal_test_stubs(monkeypatch, *, with_retro: bool = True):
    monkeypatch.setattr(campaign_ui.UIFonts, 'get', lambda size: _make_fake_font(size))
    monkeypatch.setattr(campaign_ui, 't', lambda key, *args, **kwargs: key)
    monkeypatch.setattr(campaign_ui, 'get_mouse_pos', lambda: (0, 0))

    retro_style_stub = types.ModuleType('retro_style')
    if with_retro:
        retro_style_stub.retro_style = types.SimpleNamespace(
            primary=(80, 180, 255),
            success=(90, 220, 120),
            secondary=(180, 180, 220),
            draw_glass_panel=lambda surface, rect, alpha=200, border_color=(255, 255, 255), glow=False: pygame.draw.rect(
                surface,
                border_color,
                rect,
                1,
                border_radius=12,
            ),
            draw_uniform_button=lambda surface, rect, text, sub_text=None, color_code=(255, 255, 255), state='normal': pygame.draw.rect(
                surface,
                color_code,
                rect,
                1,
                border_radius=8,
            ),
            get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        )
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)


def _complete_surface_metrics(size: tuple[int, int]) -> pygame.Rect:
    surface = pygame.Surface(size, pygame.SRCALPHA)
    effects = campaign_ui.CampaignUIEffects()
    effects.level_complete_animation = {'time': 1.2}
    effects.draw_level_complete_overlay(
        surface,
        stars=3,
        score=123456,
        level_name='Test Level',
        objectives=[{'text': 'Clear 10 lines', 'progress': '10/10', 'completed': True}],
        stats=[('Lines', '10')],
        rewards=[('Coin', '100')],
        next_level={'title': 'Next', 'lines': ['Harder gravity']},
        star_conditions=[{'star': 1, 'text': 'Finish', 'met': True}],
    )
    return effects._complete_buttons['retry']


def _failed_surface_metrics(size: tuple[int, int]) -> tuple[pygame.Rect, pygame.Rect]:
    surface = pygame.Surface(size, pygame.SRCALPHA)
    effects = campaign_ui.CampaignUIEffects()
    effects.level_failed_animation = {'time': 1.0}
    effects.draw_level_failed_overlay(surface, reason='board overflow')
    return effects._failed_buttons['retry'], effects._failed_buttons['menu']


def test_campaign_modal_scale_preserves_1366_baseline_and_caps_large_display(monkeypatch):
    _install_modal_test_stubs(monkeypatch)

    effects = campaign_ui.CampaignUIEffects()

    assert math.isclose(effects._get_modal_ui_scale((1366, 768)), 1.0)
    assert math.isclose(effects._get_modal_ui_scale((2560, 1440)), 1.2)


def test_level_complete_retry_button_grows_from_1366_baseline(monkeypatch):
    _install_modal_test_stubs(monkeypatch)

    retry_1366 = _complete_surface_metrics((1366, 768))
    retry_2560 = _complete_surface_metrics((2560, 1440))

    assert retry_1366.width == 160
    assert retry_1366.height == 32
    assert retry_2560.width > retry_1366.width
    assert retry_2560.height > retry_1366.height
    assert retry_2560.right <= 2560
    assert retry_2560.bottom <= 1440


def test_level_complete_retry_button_exists_without_retro_style(monkeypatch):
    _install_modal_test_stubs(monkeypatch, with_retro=False)

    retry_rect = _complete_surface_metrics((1366, 768))

    assert retry_rect.width == 160
    assert retry_rect.height == 32
    assert retry_rect.left >= 0
    assert retry_rect.bottom <= 768


def test_level_failed_buttons_scale_up_and_stay_on_screen(monkeypatch):
    _install_modal_test_stubs(monkeypatch)

    retry_1366, menu_1366 = _failed_surface_metrics((1366, 768))
    retry_2560, menu_2560 = _failed_surface_metrics((2560, 1440))

    assert retry_1366.height == 40
    assert menu_1366.height == 40
    assert retry_2560.width > retry_1366.width
    assert retry_2560.height > retry_1366.height
    assert menu_2560.width > menu_1366.width
    assert retry_2560.left >= 0
    assert menu_2560.right <= 2560
    assert retry_2560.bottom <= 1440
    assert menu_2560.bottom <= 1440