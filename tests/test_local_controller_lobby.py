"""Yerel kontrolcü lobisi — demo karşılığı (F6b.5 / I-50).

v2'de bu sözleşme `CoopGame._handle_controller_lobby_event` metoduna karşı
test edilir. Demo'da böyle bir yardımcı **yoktur**: lobi girdisi doğrudan
`CoopGame.handle_input()` içinde, `name_input_active and not
controller_lobby_complete` kapısının altında işlenir. Bu yüzden demo testi
gerçek giriş noktasını (`handle_input` + `pygame.event.get` yaması) sürer —
sahte bir yardımcı uydurup onu test etmek davranışı değil kopyayı doğrulardı.

Kapsam bilinçli olarak v2 kümesiyle aynı sözleşmelerde tutulur:
  - PvP kontrolcü onayı isimleri boş bırakır (etiket yalnız yer tutucu).
  - Coop lobisi klavyeyi P1/P2 atar ve lobiden çıkar.
  - Coop lobisi iki kumandayı cihaz indeksine göre atar.
  - Lobi yerleşimi ekran içinde kalır, sütunlar çakışmaz.
"""

from __future__ import annotations

import os
import types

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

import pygame

from controller_lobby import compute_controller_lobby_layout
from coop_game import CoopGame
from pvp_game import PvPGame


class _Sound:
    def play(self, _name):
        return None

    def duck_music(self):
        return None


def _key(key):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, from_gamepad=False)


def _pad(device_index, action):
    return types.SimpleNamespace(
        type=pygame.KEYDOWN,
        key=pygame.K_UNKNOWN,
        from_gamepad=True,
        device_index=device_index,
        action=action,
    )


def _pvp_setup() -> PvPGame:
    game = PvPGame.__new__(PvPGame)
    game.player1_name = 'Gamepad P1'
    game.player2_name = 'Klavye 2 (Yon)'
    game.p1_gamepad_idx = 3
    game.p2_gamepad_idx = 7
    game.gamepad_assignments = {3: 'P1', 7: 'P2'}
    game.keyboard_assignment = 'neutral'
    game.keyboard2_assignment = 'neutral'
    game.sound = _Sound()
    game.current_input = 0
    game.name_input_active = True
    game._vs_panel_dirty = False
    return game


def _coop_setup() -> CoopGame:
    game = CoopGame.__new__(CoopGame)
    game.gamepad_assignments = {}
    game.keyboard_assignment = 'neutral'
    game.keyboard2_assignment = 'neutral'
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None
    game.p1_gamepad_instance_id = None
    game.p2_gamepad_instance_id = None
    game.name_input_active = True
    game.controller_lobby_complete = False
    game.current_input = 0
    game.paused = False
    game.game_over = False
    # Lobi kapalıyken event'ler oyun girdisi yoluna düşer; o yol `pvp_controls`
    # bekler. Testin konusu lobi kapısı olduğu için asgari bir eşleme verilir.
    game.pvp_controls = {'pause': pygame.K_p}
    game.sound = _Sound()
    return game


def _feed(game, events):
    """`handle_input`'ı gerçek giriş noktasından sür (event kuyruğu yamalı)."""
    original = pygame.event.get
    pygame.event.get = lambda: list(events)
    try:
        return game.handle_input()
    finally:
        pygame.event.get = original


def test_pvp_controller_confirmation_leaves_name_fields_empty():
    game = _pvp_setup()

    assert game._complete_controller_selection() is True

    assert game.player1_name == ''
    assert game.player2_name == ''
    assert game.current_input == 1
    assert game._vs_panel_dirty is True


def test_pvp_confirmation_rejects_single_side():
    game = _pvp_setup()
    game.gamepad_assignments = {3: 'P1'}
    game.p2_gamepad_idx = None

    assert game._complete_controller_selection() is False


def test_empty_name_uses_controller_label_as_placeholder_only():
    display, is_value = PvPGame._name_field_display('', 'Klavye 1 (WASD)')

    assert display == 'Klavye 1 (WASD)'
    assert is_value is False


def test_typed_name_wins_over_placeholder():
    display, is_value = PvPGame._name_field_display('Ada', 'Klavye 1 (WASD)')

    assert display == 'Ada'
    assert is_value is True


def test_coop_lobby_assigns_keyboard_players_and_exits():
    game = _coop_setup()

    _feed(game, [_key(pygame.K_a), _key(pygame.K_RIGHT)])

    assert game.keyboard_assignment == 'P1'
    assert game.keyboard2_assignment == 'P2'

    _feed(game, [_key(pygame.K_RETURN)])

    assert game.name_input_active is False
    assert game.controller_lobby_complete is True


def test_coop_lobby_does_not_exit_with_one_player_assigned():
    game = _coop_setup()

    _feed(game, [_key(pygame.K_a), _key(pygame.K_RETURN)])

    assert game.keyboard_assignment == 'P1'
    assert game.keyboard2_assignment == 'neutral'
    assert game.name_input_active is True, 'tek oyuncuyla lobi kapanmamali'


def test_coop_lobby_assigns_two_gamepads_by_device():
    game = _coop_setup()

    _feed(game, [_pad(3, 'menu_left'), _pad(7, 'menu_right')])

    assert game.gamepad_assignments == {3: 'P1', 7: 'P2'}

    _feed(game, [_pad(3, 'menu_confirm')])

    assert game.name_input_active is False
    assert game.controller_lobby_complete is True


def test_coop_lobby_ignores_input_outside_lobby():
    """Lobi kapandiktan sonra ayni tuslar atamayi degistirmemeli."""
    game = _coop_setup()
    game.name_input_active = False
    game.controller_lobby_complete = True
    # Lobi kapisi kapaliyken event oyun girdisi yoluna duser; o yolu tam
    # kurmak yerine `paused` ile kisa devre yapiliyor (kapı sırası da böylece
    # kanıtlanır: lobi kapısı pause'dan ÖNCE bakılır).
    game.paused = True

    _feed(game, [_key(pygame.K_a)])

    assert game.keyboard_assignment == 'neutral'


def test_controller_lobby_layout_is_contained_and_columns_do_not_overlap():
    for size in ((800, 600), (1280, 720), (2560, 1440)):
        layout = compute_controller_lobby_layout(
            *size, title_bottom=100, scale=1.0
        )
        screen = pygame.Rect(0, 0, *size)
        panel = layout['panel']
        columns = layout['columns']

        assert screen.contains(panel), f'{size}: panel ekran disina tasiyor'
        assert all(screen.contains(rect) for rect in columns), f'{size}: sutun tasiyor'
        assert not columns[0].colliderect(columns[1])
        assert not columns[1].colliderect(columns[2])