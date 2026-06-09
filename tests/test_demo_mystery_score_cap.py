import sys
import types

import pygame
import pytest

_platform_utils = sys.modules.get('platform_utils')
if _platform_utils is not None and not hasattr(_platform_utils, 'get_display_scale_factor'):
    _platform_utils.get_display_scale_factor = lambda: 1.0


def _import_modules():
    if not hasattr(pygame, 'K_c'):
        pytest.skip('pygame stub environment: MysteryMode import skipped')
    import game_modes_extra as extra_modes_module
    import demo_upgrade_prompt as prompt_module
    return extra_modes_module, prompt_module


def test_demo_mystery_score_cap_only_triggers_in_demo(monkeypatch):
    extra_modes_module, _ = _import_modules()
    score_cap = getattr(extra_modes_module.demo_config, 'DEMO_MYSTERY_SCORE_CAP', 100000)
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.board = types.SimpleNamespace(score=score_cap)
    mode.game_over = False
    mode._demo_score_cap_active = False
    mode._demo_score_cap_reached = False
    mode._demo_score_cap_value = score_cap

    monkeypatch.setattr(extra_modes_module.demo_config, 'IS_DEMO', True)
    assert mode._should_trigger_demo_score_cap() is True

    monkeypatch.setattr(extra_modes_module.demo_config, 'IS_DEMO', False)
    assert mode._should_trigger_demo_score_cap() is False


def test_demo_mystery_score_cap_activation_opens_prompt_and_freezes_overlays():
    extra_modes_module, prompt_module = _import_modules()
    score_cap = getattr(extra_modes_module.demo_config, 'DEMO_MYSTERY_SCORE_CAP', 100000)
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.screen = pygame.Surface((640, 480))
    mode.board = types.SimpleNamespace(score=score_cap)
    mode.card_manager = types.SimpleNamespace(pending_choices=[{'id': 'old'}])
    mode.card_selection_active = True
    mode.card_selection_rects = [pygame.Rect(0, 0, 10, 10)]
    mode._pending_card_choice_index = 2
    mode.pending_level_ups = 3
    mode.card_message = 'test'
    mode.card_message_timer = 1.0
    mode._piece_selection_active = True
    mode._sniper_overlay_active = True
    mode._card_workshop_active = True
    mode._demo_score_cap_active = False
    mode._demo_score_cap_reached = False
    mode._demo_score_cap_value = score_cap
    mode._demo_score_cap_prompt = prompt_module.DemoUpgradePrompt(mode.screen)

    mode._activate_demo_score_cap_prompt()

    assert mode._demo_score_cap_reached is True
    assert mode._demo_score_cap_active is True
    assert mode.card_selection_active is False
    assert mode.card_selection_rects == []
    assert mode._pending_card_choice_index is None
    assert mode.pending_level_ups == 0
    assert mode.card_manager.pending_choices == []
    assert mode._piece_selection_active is False
    assert mode._sniper_overlay_active is False
    assert mode._card_workshop_active is False
    assert mode._demo_score_cap_prompt.is_active() is True


def test_demo_score_cap_prompt_tracks_confirm_and_cancel(monkeypatch):
    _, prompt_module = _import_modules()
    prompt = prompt_module.DemoUpgradePrompt(pygame.Surface((640, 480)))

    prompt_module.show_demo_score_cap_prompt(prompt)
    assert prompt.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)) is True
    assert prompt.consume_last_action() == 'cancel'

    opened_urls: list[str] = []
    monkeypatch.setattr(prompt_module.webbrowser, 'open', lambda url, new=0: opened_urls.append(url))

    prompt_module.show_demo_score_cap_prompt(prompt)
    assert prompt.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)) is True
    assert opened_urls == [prompt_module.demo_config.DEMO_STEAM_STORE_URL]
    assert prompt.consume_last_action() == 'confirm'


def test_demo_score_cap_prompt_outside_click_is_swallowed_without_dismiss() -> None:
    _, prompt_module = _import_modules()
    prompt = prompt_module.DemoUpgradePrompt(pygame.Surface((640, 480)))
    prompt_module.show_demo_score_cap_prompt(prompt)
    prompt.confirm_rect = pygame.Rect(220, 320, 200, 44)
    prompt.cancel_rect = pygame.Rect(220, 372, 200, 44)

    handled = prompt.handle_input(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(32, 32)))

    assert handled is True
    assert prompt.is_active() is True
    assert prompt.consume_last_action() is None


def test_demo_score_cap_prompt_mouse_confirm_waits_for_release(monkeypatch) -> None:
    _, prompt_module = _import_modules()
    prompt = prompt_module.DemoUpgradePrompt(pygame.Surface((640, 480)))
    prompt_module.show_demo_score_cap_prompt(prompt)
    prompt.confirm_rect = pygame.Rect(220, 320, 200, 44)
    prompt.cancel_rect = pygame.Rect(220, 372, 200, 44)

    opened_urls: list[str] = []
    monkeypatch.setattr(prompt_module.webbrowser, 'open', lambda url, new=0: opened_urls.append(url))

    assert prompt.handle_input(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=prompt.confirm_rect.center)) is True
    assert opened_urls == []
    assert prompt.is_active() is True

    assert prompt.handle_input(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=prompt.confirm_rect.center)) is True
    assert opened_urls == [prompt_module.demo_config.DEMO_STEAM_STORE_URL]
    assert prompt.consume_last_action() == 'confirm'


def _make_capped_mode(extra_modes_module, prompt_module):
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.screen = pygame.Surface((640, 480))
    mode.board = types.SimpleNamespace(score=150000)
    mode.card_manager = types.SimpleNamespace(pending_choices=[])
    mode.card_selection_active = False
    mode.card_selection_rects = []
    mode._pending_card_choice_index = None
    mode.pending_level_ups = 0
    mode.card_message = ''
    mode.card_message_timer = 0.0
    mode._piece_selection_active = False
    mode._sniper_overlay_active = False
    mode._card_workshop_active = False
    mode._demo_score_cap_active = False
    mode._demo_score_cap_reached = False
    mode._demo_score_cap_value = 150000
    mode._demo_score_cap_prompt = prompt_module.DemoUpgradePrompt(mode.screen)
    return mode


def test_demo_score_cap_threshold_is_150k(monkeypatch):
    extra_modes_module, prompt_module = _import_modules()
    monkeypatch.setattr(extra_modes_module.demo_config, 'IS_DEMO', True)
    mode = _make_capped_mode(extra_modes_module, prompt_module)

    assert mode._get_demo_score_cap() == 150000

    mode.board.score = 149999
    assert mode._should_trigger_demo_score_cap() is False

    mode.board.score = 150000
    assert mode._should_trigger_demo_score_cap() is True


def test_demo_score_cap_esc_returns_to_menu(monkeypatch):
    extra_modes_module, prompt_module = _import_modules()
    monkeypatch.setattr(extra_modes_module.demo_config, 'IS_DEMO', True)
    mode = _make_capped_mode(extra_modes_module, prompt_module)
    mode._activate_demo_score_cap_prompt()

    esc_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    monkeypatch.setattr(extra_modes_module.pygame.event, 'get', lambda *a, **k: [esc_event])

    result = mode.handle_input()

    assert result == 'menu'
    assert mode._demo_score_cap_active is False
    assert mode._demo_score_cap_prompt.is_active() is False


def test_demo_score_cap_esc_recovers_from_inactive_prompt_desync(monkeypatch):
    # Panel bayrağı açık ama prompt pasif kaldığında ESC yine de menüye dönmeli.
    extra_modes_module, prompt_module = _import_modules()
    monkeypatch.setattr(extra_modes_module.demo_config, 'IS_DEMO', True)
    mode = _make_capped_mode(extra_modes_module, prompt_module)
    mode._activate_demo_score_cap_prompt()
    mode._demo_score_cap_prompt.active = False  # state desync

    esc_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    monkeypatch.setattr(extra_modes_module.pygame.event, 'get', lambda *a, **k: [esc_event])

    result = mode.handle_input()

    assert result == 'menu'
    assert mode._demo_score_cap_active is False
