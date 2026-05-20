from __future__ import annotations

import pygame

import menu
import extras_menu
from campaign import level_select as solo_level_select


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)

    def get_size(self) -> tuple[int, int]:
        return self._size

    def get_width(self) -> int:
        return self._size[0]

    def get_height(self) -> int:
        return self._size[1]


class _ActivePrompt:
    def __init__(self):
        self.screen = None
        self.draw_calls = 0

    def is_active(self) -> bool:
        return True

    def draw(self) -> None:
        self.draw_calls += 1


class _BackgroundFxSpy:
    def __init__(self):
        self.called = False

    def update(self, _screen) -> None:
        self.called = True

    def draw(self, _screen) -> None:
        self.called = True


def test_menu_demo_online_actions_open_transition_prompt(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(menu.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(menu, 'show_demo_transition_lock_prompt', lambda prompt: calls.append(prompt))

    menu_screen = menu.Menu.__new__(menu.Menu)
    menu_screen._demo_upgrade_prompt = object()

    assert menu_screen._maybe_handle_demo_main_action('online_pvp') is True
    assert calls == [menu_screen._demo_upgrade_prompt]

    calls.clear()
    assert menu_screen._maybe_handle_demo_main_action('pvp_2_players') is False
    assert calls == []


def test_menu_demo_locked_split_actions_report_locked_state(monkeypatch) -> None:
    monkeypatch.setattr(menu.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(
        menu.demo_config,
        'is_locked_main_action',
        lambda action: action in {'online_pvp', 'online_coop'},
    )

    menu_screen = menu.Menu.__new__(menu.Menu)

    assert menu_screen._is_demo_locked_main_action('online_pvp') is True
    assert menu_screen._is_demo_locked_main_action('online_coop') is True
    assert menu_screen._is_demo_locked_main_action('pvp_2_players') is False


def test_extras_demo_locked_modes_route_to_expected_prompt(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(extras_menu.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(extras_menu, 'show_demo_full_lock_prompt', lambda _prompt: calls.append('full'))
    monkeypatch.setattr(extras_menu, 'show_demo_transition_lock_prompt', lambda _prompt: calls.append('transition'))
    monkeypatch.setattr(extras_menu, 'show_demo_partial_lock_prompt', lambda _prompt: calls.append('partial'))

    screen = extras_menu.ExtrasScreen.__new__(extras_menu.ExtrasScreen)
    screen._demo_upgrade_prompt = object()

    assert screen._show_demo_lock_prompt_for_mode('Quadrix Extra') is True
    assert calls == ['full']

    calls.clear()
    assert screen._show_demo_lock_prompt_for_mode('Online PvP') is True
    assert calls == ['transition']

    calls.clear()
    assert screen._show_demo_lock_prompt_for_mode('Classic Mode') is False
    assert calls == []


def test_menu_draw_freezes_background_when_demo_prompt_active() -> None:
    menu_screen = menu.Menu.__new__(menu.Menu)
    menu_screen.screen = _FakeScreen(1366, 768)
    menu_screen._demo_upgrade_prompt = _ActivePrompt()
    menu_screen.background_fx = _BackgroundFxSpy()
    menu_screen.selected = 3

    menu_screen.draw()

    assert menu_screen._demo_upgrade_prompt.draw_calls == 1
    assert menu_screen.background_fx.called is False
    assert menu_screen.selected == 3


def test_extras_draw_freezes_background_when_demo_prompt_active() -> None:
    extras_screen = extras_menu.ExtrasScreen.__new__(extras_menu.ExtrasScreen)
    extras_screen.screen = _FakeScreen(1366, 768)
    extras_screen._demo_upgrade_prompt = _ActivePrompt()
    extras_screen.background_fx = _BackgroundFxSpy()
    extras_screen.selected = 2

    extras_screen.draw()

    assert extras_screen._demo_upgrade_prompt.draw_calls == 1
    assert extras_screen.background_fx.called is False
    assert extras_screen.selected == 2


def test_campaign_draw_keeps_hover_state_frozen_when_demo_prompt_active() -> None:
    level_select = solo_level_select.CampaignLevelSelect.__new__(solo_level_select.CampaignLevelSelect)
    level_select.screen = _FakeScreen(1366, 768)
    level_select._demo_upgrade_prompt = _ActivePrompt()
    level_select.hovered_level = 9
    level_select.level_buttons = [(pygame.Rect(0, 0, 80, 80), 1)]

    level_select.draw()

    assert level_select._demo_upgrade_prompt.draw_calls == 1
    assert level_select.hovered_level == 9