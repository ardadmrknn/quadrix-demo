"""Online co-op Hold prompt ve gerçek input eşlemesi regresyonları."""
from __future__ import annotations

import types
from unittest.mock import Mock

import pytest


@pytest.fixture
def coop(monkeypatch):
    import coop_game
    import localization
    import pygame
    from retro_style import retro_style
    # test_coop collection sırasında bu modülün bağımlılıklarını stub'lar.
    # Bu testler gerçek font/key API'sini doğruladığından referansları ayır.
    monkeypatch.setattr(coop_game, 'pygame', pygame)
    monkeypatch.setattr(coop_game, 'retro_style', retro_style)
    pygame.font.init()
    old = localization.get_language()
    localization.set_language('tr')
    monkeypatch.setattr(coop_game, 't', localization.t)
    monkeypatch.setattr(coop_game, 'get_gamepad_manager', lambda: types.SimpleNamespace(enabled=False))
    yield coop_game
    localization.set_language(old)


def _game(coop, role='P1'):
    game = coop.CoopGame.__new__(coop.CoopGame)
    game._is_online_coop = True
    game._local_player_role = role
    game.pvp_controls = {'player1': {'hold': coop.pygame.K_e}, 'player2': {'hold': coop.pygame.K_RSHIFT}}
    settings = {'controls': {'single_player': {'hold': {'primary': coop.pygame.K_c, 'secondary': ''}}}}
    game.settings_manager = types.SimpleNamespace(settings=settings, get_controls=lambda: settings['controls'])
    return game


@pytest.mark.parametrize('role,remote', [('P1', 'P2'), ('P2', 'P1')])
def test_online_roles_show_own_binding_and_no_remote_binding(coop, role, remote):
    game = _game(coop, role)
    assert game._hold_label(role) == 'SEN (C)'
    assert game._hold_label(remote) == f'{remote} ORTAK'


def test_keyboard_rebinding_secondary_and_unbound(coop):
    game = _game(coop)
    binding = game.settings_manager.settings['controls']['single_player']['hold']
    assert game._hold_label('P1') == 'SEN (C)'
    binding.update(primary='', secondary=coop.pygame.K_h)
    assert game._hold_label('P1') == 'SEN (H)'
    binding.update(primary=coop.pygame.K_c)
    assert game._hold_label('P1') == 'SEN (C / H)'
    binding.update(primary='', secondary='')
    assert game._hold_label('P1') == 'SEN (-)'


def test_connected_gamepad_rebind_unbound_and_disconnect(coop, monkeypatch):
    game = _game(coop)
    indices = [9]
    manager = types.SimpleNamespace(enabled=True, is_connected=lambda: True,
        get_action_button_indices=lambda action: indices,
        get_active_gamepad=lambda: types.SimpleNamespace(gamepad_type='playstation'))
    monkeypatch.setattr(coop, 'get_gamepad_manager', lambda: manager)
    assert game._hold_label('P1') == 'SEN (L1)'
    indices[:] = [100]
    assert game._hold_label('P1') == 'SEN (L2)'
    indices.clear()
    assert game._hold_label('P1') == 'SEN (-)'
    manager.is_connected = lambda: False
    assert game._hold_label('P1') == 'SEN (C)'


def test_unchanged_binding_does_not_resolve_key_or_merge_settings_again(coop, monkeypatch):
    game = _game(coop)
    merge = Mock(side_effect=AssertionError('HUD must use settings snapshot'))
    game.settings_manager.get_controls = merge
    key_label = Mock(wraps=game._key_label)
    monkeypatch.setattr(game, '_key_label', key_label)
    first = game._hold_label('P1')
    for _ in range(20):
        assert game._hold_label('P1') is first
    key_label.assert_called_once()
    merge.assert_not_called()


def test_language_change_invalidates_label(coop):
    import localization
    game = _game(coop)
    assert game._hold_label('P1') == 'SEN (C)'
    localization.set_language('en')
    assert game._hold_label('P1') == 'YOU (C)'
    assert game._hold_label('P2') == 'P2 TEAMMATE'


def test_local_coop_preserves_local_bindings(coop):
    game = _game(coop)
    game._is_online_coop = False
    assert game._hold_label('P1') == 'P1 Saklanan (E)'
    assert game._hold_label('P2') == 'P2 Saklanan (RShift)'


def test_panel_surface_is_cached_and_fits_small_width(coop, monkeypatch):
    game = _game(coop)
    render = Mock(wraps=coop.render_text)
    monkeypatch.setattr(coop, 'render_text', render)
    label = game._hold_label('P1')
    first = game._render_panel_label_surface(label, (255, 255, 255), 60, base_size=14)
    second = game._render_panel_label_surface(label, (255, 255, 255), 60, base_size=14)
    assert first is second
    assert first.get_width() <= 60
    render.assert_called_once()


def test_promptfont_composition_only_on_cache_miss(coop, monkeypatch):
    import promptfont_support
    game = _game(coop)
    manager = types.SimpleNamespace(enabled=True, is_connected=lambda: True,
        get_action_button_indices=lambda action: [9],
        get_active_gamepad=lambda: types.SimpleNamespace(gamepad_type='playstation'))
    monkeypatch.setattr(coop, 'get_gamepad_manager', lambda: manager)
    compose = Mock(return_value=coop.pygame.Surface((50, 18)))
    monkeypatch.setattr(promptfont_support, 'render_inline_action_text_surface', compose)
    label = game._hold_label('P1')
    first = game._render_panel_label_surface(label, (255, 255, 255), 180, base_size=14)
    assert game._render_panel_label_surface(label, (255, 255, 255), 180, base_size=14) is first
    compose.assert_called_once()


def test_online_input_agrees_with_single_player_hold(coop):
    from online_coop_game import OnlineCoopGame
    game = OnlineCoopGame.__new__(OnlineCoopGame)
    game.settings_manager = _game(coop).settings_manager
    for role_map in (game._HOST_KEYS, game._GUEST_KEYS):
        assert game._single_player_action_for_event(types.SimpleNamespace(key=coop.pygame.K_c), role_map) == 'hold'
        assert game._single_player_action_for_event(types.SimpleNamespace(key=coop.pygame.K_e), role_map) is None
        event = types.SimpleNamespace(key=coop.pygame.K_LSHIFT, from_gamepad=True, action='hold')
        assert game._single_player_action_for_event(event, role_map) == 'hold'
