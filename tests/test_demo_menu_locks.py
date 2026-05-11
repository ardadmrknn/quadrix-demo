from __future__ import annotations

import menu
import extras_menu


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