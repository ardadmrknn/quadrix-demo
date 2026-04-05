from __future__ import annotations

import math
import pathlib
import sys

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tutorial as tutorial_module
from game_modes_extra import MysteryCardUI


TutorialMode = tutorial_module.TutorialMode


def _build_tutorial(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    tutorial = TutorialMode.__new__(TutorialMode)
    tutorial.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    tutorial.window_width, tutorial.window_height = window_size
    tutorial.board_height = 20
    tutorial.card_ui = MysteryCardUI()
    tutorial.get_board_offset = lambda: (420, 108)
    tutorial.get_cell_size = lambda: 24
    return tutorial


def test_tutorial_modal_scale_uses_active_canvas_and_preserves_1366_baseline():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    assert math.isclose(tutorial._tutorial_modal_scale(), 1.0)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(tutorial._tutorial_modal_scale(), 1.18)


def test_tutorial_card_font_pack_can_grow_above_one(monkeypatch):
    monkeypatch.setattr(tutorial_module, '_tutorial_make_card_ui_font', lambda size, bold=False: size)
    tutorial = _build_tutorial((1366, 768))

    baseline_fonts = tutorial._build_tutorial_card_ui_font_pack()
    assert baseline_fonts['heading'] == 44
    assert baseline_fonts['value'] == 52

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    tutorial.window_width = 2560
    tutorial.window_height = 1440

    grown_fonts = tutorial._build_tutorial_card_ui_font_pack()
    assert grown_fonts['heading'] > baseline_fonts['heading']
    assert grown_fonts['value'] > baseline_fonts['value']


def test_tutorial_overlay_rect_grows_with_modal_scale():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    baseline_rect = tutorial._tutorial_overlay_rect()
    assert baseline_rect.size == (260, 320)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    grown_rect = tutorial._tutorial_overlay_rect()
    assert grown_rect.width > baseline_rect.width
    assert grown_rect.height > baseline_rect.height


def test_tutorial_hub_panel_rect_grows_and_stays_centered():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    baseline_rect = tutorial._tutorial_hub_panel_rect()
    assert baseline_rect.size == (1180, 720)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    grown_rect = tutorial._tutorial_hub_panel_rect()
    assert grown_rect.width > baseline_rect.width
    assert grown_rect.height > baseline_rect.height
    assert grown_rect.center == (1280, 720)


def test_tutorial_card_overlay_reference_stays_on_phase8_baseline():
    tutorial = _build_tutorial((2560, 1440))

    tutorial._sync_tutorial_card_overlay_reference()

    assert tutorial.card_ui._overlay_base_size == (
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[0]),
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[1]),
    )
    assert math.isclose(tutorial.card_ui._get_overlay_scale(2560, 1440), 1.12)


def test_tutorial_resize_syncs_window_metrics_to_created_surface(monkeypatch):
    tutorial = _build_tutorial((1366, 768), window_size=(1366, 768))
    updated = {'called': False}

    monkeypatch.setattr(
        tutorial_module,
        'create_display',
        lambda width, height, fullscreen=False, resizable=True: pygame.Surface((2560, 1440), pygame.SRCALPHA),
    )
    tutorial.update_fonts = lambda: updated.__setitem__('called', True)

    tutorial._apply_tutorial_resize(1920, 1080)

    assert updated['called'] is True
    assert (tutorial.window_width, tutorial.window_height) == (2560, 1440)
    assert tutorial.card_ui._overlay_base_size == (
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[0]),
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[1]),
    )