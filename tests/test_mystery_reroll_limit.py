import types
import sys

import pygame
import pytest

_platform_utils = sys.modules.get('platform_utils')
if _platform_utils is not None and not hasattr(_platform_utils, 'get_display_scale_factor'):
    _platform_utils.get_display_scale_factor = lambda: 1.0


def _import_game_modes_extra():
    if not hasattr(pygame, 'K_c'):
        pytest.skip("pygame stub environment: MysteryMode import skipped")
    from game_modes_extra import MysteryCardUI, MysteryMode
    return MysteryCardUI, MysteryMode


def test_try_reroll_consumes_one_match_charge_and_resets_ui():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_active = True
    mode.card_selection_reroll_limit = 5
    mode.card_selection_rerolls_remaining = 5

    reset_calls = []
    mode.card_ui = types.SimpleNamespace(reset=lambda: reset_calls.append(True))

    manager = types.SimpleNamespace()
    manager.pending_choices = [{'id': 'old'}]

    def _prepare_selection():
        manager.pending_choices = [{'id': 'new'}]
        return manager.pending_choices

    manager.prepare_selection = _prepare_selection
    mode.card_manager = manager

    assert mode._try_reroll_card_selection() is True
    assert mode.card_selection_rerolls_remaining == 4
    assert manager.pending_choices == [{'id': 'new'}]
    assert reset_calls == [True]


def test_try_reroll_refunds_charge_when_new_selection_is_empty():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_active = True
    mode.card_selection_reroll_limit = 5
    mode.card_selection_rerolls_remaining = 1

    reset_calls = []
    mode.card_ui = types.SimpleNamespace(reset=lambda: reset_calls.append(True))

    manager = types.SimpleNamespace()
    manager.pending_choices = [{'id': 'old'}]

    def _prepare_selection():
        manager.pending_choices = []
        return manager.pending_choices

    manager.prepare_selection = _prepare_selection
    mode.card_manager = manager

    assert mode._try_reroll_card_selection() is False
    assert mode.card_selection_rerolls_remaining == 1
    assert manager.pending_choices == [{'id': 'old'}]
    assert reset_calls == []


def test_card_ui_blocks_disabled_reroll_button_click():
    MysteryCardUI, _ = _import_game_modes_extra()
    ui = MysteryCardUI()
    ui.reroll_button_rect = pygame.Rect(0, 0, 200, 48)

    ui.set_reroll_enabled(False)
    assert ui.handle_mouse_click((10, 10)) is None

    ui.set_reroll_enabled(True)
    assert ui.handle_mouse_click((10, 10)) == 'REROLL'


def test_card_ui_ignores_clicks_when_interaction_locked():
    MysteryCardUI, _ = _import_game_modes_extra()
    ui = MysteryCardUI()
    ui.reroll_button_rect = pygame.Rect(0, 0, 200, 48)
    ui.set_reroll_enabled(True)
    ui.interaction_locked = True

    assert ui.handle_mouse_click((10, 10)) is None


def test_card_ui_arrow_navigation_moves_between_cards_and_actions():
    MysteryCardUI, _ = _import_game_modes_extra()
    ui = MysteryCardUI()
    ui.set_reroll_enabled(True)

    assert ui.get_focus_target(3) == 0

    assert ui.move_focus('right', 3) is True
    assert ui.get_focus_target(3) == 1

    assert ui.move_focus('down', 3) is True
    assert ui.get_focus_target(3) == 'SKIP'

    assert ui.move_focus('right', 3) is True
    assert ui.get_focus_target(3) == 'REROLL'

    assert ui.move_focus('up', 3) is True
    assert ui.get_focus_target(3) == 1


def test_card_ui_navigation_skips_disabled_reroll_action():
    MysteryCardUI, _ = _import_game_modes_extra()
    ui = MysteryCardUI()
    ui.set_reroll_enabled(False)

    ui.move_focus('down', 3)
    assert ui.get_focus_target(3) == 'SKIP'

    assert ui.move_focus('right', 3) is False
    assert ui.get_focus_target(3) == 'SKIP'


def test_card_selection_keydown_routes_arrows_and_enter_to_reroll():
    MysteryCardUI, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.settings_manager = types.SimpleNamespace(get=lambda *_args, **_kwargs: False)
    mode.control_bindings = {
        'move_left': pygame.K_LEFT,
        'move_right': pygame.K_RIGHT,
        'soft_drop': pygame.K_DOWN,
        'rotate': pygame.K_UP,
    }
    mode.alt_control_bindings = {}
    mode.card_manager = types.SimpleNamespace(pending_choices=[{'id': 'a'}, {'id': 'b'}, {'id': 'c'}])
    mode.card_ui = MysteryCardUI()
    mode.card_ui.set_reroll_enabled(True)

    reroll_calls = []
    mode._try_reroll_card_selection = lambda: reroll_calls.append(True)
    mode._close_card_selection = lambda: None
    mode._select_card = lambda _index: pytest.fail('Arrow/enter reroll akisinda kart secilmemeliydi')

    assert mode._handle_card_selection_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)) is True
    assert mode.card_ui.get_focus_target(3) == 1

    assert mode._handle_card_selection_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)) is True
    assert mode.card_ui.get_focus_target(3) == 'SKIP'

    assert mode._handle_card_selection_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)) is True
    assert mode.card_ui.get_focus_target(3) == 'REROLL'

    assert mode._handle_card_selection_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)) is True
    assert reroll_calls == [True]


def test_card_selection_keydown_keeps_space_for_activation_even_if_rotate_is_rebound():
    MysteryCardUI, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.settings_manager = types.SimpleNamespace(get=lambda *_args, **_kwargs: False)
    mode.control_bindings = {
        'move_left': pygame.K_LEFT,
        'move_right': pygame.K_RIGHT,
        'soft_drop': pygame.K_DOWN,
        'rotate': pygame.K_SPACE,
    }
    mode.alt_control_bindings = {}
    mode.card_manager = types.SimpleNamespace(pending_choices=[{'id': 'a'}, {'id': 'b'}, {'id': 'c'}])
    mode.card_ui = MysteryCardUI()
    mode.card_ui.set_reroll_enabled(True)
    mode.card_ui.move_focus('right', 3)
    mode.card_ui.move_focus('down', 3)
    mode.card_ui.move_focus('right', 3)

    reroll_calls = []
    mode._try_reroll_card_selection = lambda: reroll_calls.append(True)
    mode._close_card_selection = lambda: None
    mode._select_card = lambda _index: pytest.fail('Space aktivasyonu navigasyona dusmemeliydi')

    assert mode._handle_card_selection_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)) is True
    assert reroll_calls == [True]


def test_can_reroll_returns_false_while_selection_is_locked():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_active = True
    mode.card_selection_rerolls_remaining = 3
    mode._pending_card_choice_index = None
    mode.card_manager = types.SimpleNamespace(pending_choices=[{'id': 'keep'}])
    mode.card_ui = types.SimpleNamespace(is_interaction_locked=lambda: True)

    assert mode._can_reroll_card_selection() is False


def test_reset_card_selection_rerolls_restores_match_limit():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_reroll_limit = 5
    mode.card_selection_rerolls_remaining = 0

    mode._reset_card_selection_rerolls()

    assert mode.card_selection_rerolls_remaining == 5