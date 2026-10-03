"""DUZ-007 — Gamepad action metadata sözleşmesi testleri (demo).

Iade_Duzeltme_Plani.md DUZ-007: klavye binding remap'i sonrasında gamepad
eylemleri kaybolur. İki katmanlı kök neden:
1) Game.handle_input'taki pause/move_left/move_right/soft_drop/hold2/
   hard_drop/hold KEYDOWN yolları ve soft_drop/move_left/move_right
   KEYUP yolları yalnız klavye anahtar kümesiyle eşleşiyordu; sentetik
   gamepad event'lerinin canonical action metadata'sı yok sayılıyordu.
2) GamepadManager._generate_dpad_events ve _generate_repeat_pulses
   action metadata'yı HİÇ yazmıyordu → D-pad UP (varsayılan layout'un
   tek rotate kaynağı, button 11) rotasyonu remap'ten BAĞIMSIZ olarak
   hiç tetiklenmiyordu (ampirik: demo 0→0, v2 0→1 + rotate sesi).
   Fix: v2'nin action_map doldurması + _generate_repeat_pulses'ın
   gp_device_index/action_map imzası demo'ya port edildi (stick
   bölümündeki GP-007 deseninin D-pad'a uygulanması).

Kabul kriterleri (Iade_Duzeltme_Plani.md DUZ-007):
(a) 7 eylem yolu (pause, move_left, move_right, soft_drop, hold2,
    hard_drop, hold) ayrı testlerle sözleşmeye bağlanır.
(b) Sentetik gamepad event'in action metadata'sı yanlış klavye
    binding'iyle ÇAKIŞMAZ (metadata her zaman kazanır).
(c) KEYDOWN ve KEYUP aynı action sözleşmesini kullanır.
(d) KEYUP DAS/soft-drop kilitlerini temizler.
(e) ACTION_TO_KEY yalnızca sentetik event üretimi için kalır; sabit
    tablo klavye/gamepad binding değişimlerinden etkilenmez.

Teknik sınırlar (kart): is_direction_held poll yolu KALDIRILMAZ; Hold
ve hard drop tek vuruş kalır; inline DAS mantığına dokunulmaz.
Klavye primary davranışı birebir korunur (hard_drop/hold/hold2/pause
secondary'leri default olarak None çözümlenir → `in` kümesi tek üyelidir).

Desen referansı: tests/test_gamepad_remap_and_diagonal_dpad.py
(manager) + v2 tests/test_counter_clockwise_controls.py (gameplay).
"""

from __future__ import annotations

import copy
import pathlib
import sys
import types

import pygame

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import game as game_module  # noqa: E402
from board import Board  # noqa: E402
from game import FAST_FALL_SPEED  # noqa: E402
from gamepad_manager import (  # noqa: E402
    ACTION_TO_KEY,
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)
from pieces import create_piece_by_name  # noqa: E402
from settings_manager import DEFAULT_CONTROLS  # noqa: E402


class _Settings:
    def __init__(self, controls=None, dcd=17):
        self.controls = controls or copy.deepcopy(DEFAULT_CONTROLS)
        self.dcd = dcd

    def get_controls(self):
        return self.controls

    def get(self, key, default=None):
        if key == 'dcd':
            return self.dcd
        if key == 'controls':
            return self.controls
        return default


class _Sound:
    def __init__(self):
        self.calls = []

    def play(self, name):
        self.calls.append(name)

    def duck_music(self):
        self.calls.append('duck_music')

    def unduck_music(self):
        self.calls.append('unduck_music')


def _keydown(key, **metadata):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, mod=0, **metadata)


def _keyup(key, **metadata):
    return types.SimpleNamespace(type=pygame.KEYUP, key=key, mod=0, **metadata)


def _remapped(remaps):
    """DEFAULT_CONTROLS kopyası üzerinde single_player remap'i uygular."""
    controls = copy.deepcopy(DEFAULT_CONTROLS)
    for action, primary in remaps.items():
        controls['single_player'][action] = {'primary': primary, 'secondary': ''}
    return controls


def _remap_single_action(action, primary='f'):
    """Bir eylemi 'f' tuşuna remap'ler — gamepad kanonik anahtarı ile çakışmaz."""
    return _remapped({action: primary})


def _make_game(controls=None):
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game._pause_settings_active = False
    game.settings_manager = _Settings(controls)
    game.control_bindings = game._resolve_single_player_controls()
    game.alt_control_bindings = game._resolve_single_player_secondary_controls(game.control_bindings)
    game.current_piece = create_piece_by_name('T', x=3, y=5)
    game.board = Board(width=10, height=20)
    game.sound = _Sound()
    # DUZ-007 gameplay yollarının gerektirdiği ilave durum (stub'lar yalnızca
    # test odağı dışı yan etkileri keser; dispatch davranışı gerçektir).
    game.next_piece_queue = [create_piece_by_name('I', x=3, y=0)]
    game.held_piece = None
    game.can_hold = True
    game.can_hold2 = True
    game.second_held_piece = None
    game.user_manager = None
    game.perk_manager = types.SimpleNamespace(is_active=lambda name: name == 'second_pocket')
    game.effects_enabled = False
    game.fall_speed = 777.0
    game.das_direction = 0
    game.das_timer = 0.0
    game.das_repeat_timer = 0.0
    game.das_charged = False
    game.dcd_timer = 0.0
    game.lock_reset_count = 0
    game.lock_timer = 0.0
    game.last_move_was_rotate = False
    game.last_rotate_kick_index = -1
    game._update_grounded_after_action = lambda: None
    game._reset_piece_state = lambda: None
    game._position_piece_at_spawn = lambda piece: None
    game._skip_hidden_rows = lambda piece: None
    game.spawn_new_piece = lambda: create_piece_by_name('O', x=3, y=0)
    game.apply_theme_to_pieces = lambda: None
    return game


def _dpad_state(hat, device_index=0):
    """D-pad testi için GamepadState (test_gamepad_remap_and_diagonal_dpad deseni)."""
    gp = GamepadState(device_index=device_index)
    gp.dpad = hat
    gp.prev_dpad = (0, 0)
    gp.connected = True
    gp.is_gamepad = True
    return gp


# ─── (a) 7 gameplay yolu — gamepad metadata + klavye remap birlikte ──────


def test_pause_path_uses_action_metadata_contract(monkeypatch):
    game = _make_game(_remap_single_action('pause'))
    assert game.control_bindings['pause'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_p, from_gamepad=True, action='pause', device_index=0)],
    )
    game.handle_input()

    assert game.paused is True
    assert game.sound.calls == ['duck_music']


def test_move_left_gamepad_metadata_moves_piece(monkeypatch):
    game = _make_game(_remap_single_action('move_left'))
    assert game.control_bindings['move_left'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_LEFT, from_gamepad=True, action='move_left', device_index=0)],
    )
    game.handle_input()

    assert game.current_piece.x == 2
    assert game.sound.calls == ['move']
    assert game.das_direction == -1


def test_move_right_gamepad_metadata_moves_piece(monkeypatch):
    game = _make_game(_remap_single_action('move_right'))
    assert game.control_bindings['move_right'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_RIGHT, from_gamepad=True, action='move_right', device_index=0)],
    )
    game.handle_input()

    assert game.current_piece.x == 4
    assert game.sound.calls == ['move']
    assert game.das_direction == 1


def test_soft_drop_keydown_gamepad_metadata(monkeypatch):
    game = _make_game(_remap_single_action('soft_drop'))
    assert game.control_bindings['soft_drop'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_DOWN, from_gamepad=True, action='soft_drop', device_index=0)],
    )
    game.handle_input()

    assert game.fall_speed == FAST_FALL_SPEED


def test_hard_drop_gamepad_metadata_locks_piece(monkeypatch):
    game = _make_game(_remap_single_action('hard_drop'))
    assert game.control_bindings['hard_drop'] == pygame.K_f
    locked = []
    game.lock_and_new_piece = lambda: locked.append(True)
    score_before = game.board.score

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_SPACE, from_gamepad=True, action='hard_drop', device_index=0)],
    )
    game.handle_input()

    assert locked == [True]
    assert game.current_piece.y > 5
    assert game.board.score > score_before


def test_hold_gamepad_metadata_stores_piece(monkeypatch):
    game = _make_game(_remap_single_action('hold'))
    assert game.control_bindings['hold'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_c, from_gamepad=True, action='hold', device_index=0)],
    )
    game.handle_input()

    assert game.held_piece is not None
    assert game.held_piece.name == 'T'
    assert game.current_piece.name == 'I'
    assert game.can_hold is False
    assert game.sound.calls == ['move']


def test_hold2_gamepad_metadata_uses_second_pocket(monkeypatch):
    game = _make_game(_remap_single_action('hold2'))
    assert game.control_bindings['hold2'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_v, from_gamepad=True, action='hold2', device_index=0)],
    )
    game.handle_input()

    assert game.second_held_piece is not None
    assert game.second_held_piece.name == 'T'
    assert game.current_piece.name == 'I'
    assert game.can_hold2 is False
    assert game.sound.calls == ['move']


# ─── (b) metadata, remap'li klavye binding'iyle ÇAKIŞMAZ ─────────────────


def test_gamepad_metadata_does_not_collide_with_rebound_keyboard_key(monkeypatch):
    """K_z klavyede move_left'e remap edilmiş olsa da, K_z taşıyan gamepad
    rotate_ccw event'i MOVE değil ROTATE tetikler: action metadata kazanır."""
    controls = _remapped({'move_left': 'z', 'rotate_ccw': 'f'})
    game = _make_game(controls)
    assert game.control_bindings['move_left'] == pygame.K_z
    assert game.control_bindings['rotate_ccw'] == pygame.K_f

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_z, from_gamepad=True, action='rotate_ccw', device_index=0)],
    )
    game.handle_input()

    assert game.current_piece.x == 3  # hareket tetiklenmedi
    assert game.current_piece.rotation_state == 3  # CCW döndü
    assert game.sound.calls == ['rotate']


# ─── klavye yolu korunumu (davranış-nötr regresyon) ───────────────────────


def test_keyboard_rebind_still_triggers_hard_drop(monkeypatch):
    game = _make_game(_remap_single_action('hard_drop'))
    locked = []
    game.lock_and_new_piece = lambda: locked.append(True)

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_f)],
    )
    game.handle_input()

    assert locked == [True]


def test_keyboard_pause_primary_still_pauses(monkeypatch):
    game = _make_game(_remap_single_action('pause'))

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown(pygame.K_f)])
    game.handle_input()

    assert game.paused is True
    assert game.sound.calls == ['duck_music']


# ─── (c)+(d) KEYUP aynı sözleşme — DAS/soft-drop kilitleri temizlenir ─────


def test_soft_drop_keyup_gamepad_metadata_restores_speed(monkeypatch):
    game = _make_game(_remap_single_action('soft_drop'))
    game.get_current_speed = lambda: 55.0
    assert game.fall_speed == 777.0

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keyup(pygame.K_DOWN, from_gamepad=True, action='soft_drop', device_index=0)],
    )
    game.handle_input()

    assert game.fall_speed == 55.0


def test_keyup_move_left_gamepad_metadata_stops_inline_das(monkeypatch):
    """Demo'nun inline DAS mantığı: gamepad move_left bırakışı
    das_direction'ı 0'a çeker (klavye remap'i bu temizliği düşürmez)."""
    game = _make_game(_remap_single_action('move_left'))
    game.das_direction = -1
    monkeypatch.setattr(game_module.pygame.key, 'get_pressed', lambda: [False] * 512)

    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keyup(pygame.K_LEFT, from_gamepad=True, action='move_left', device_index=0)],
    )
    game.handle_input()

    assert game.das_direction == 0
    assert game.das_charged is False


# ─── D-pad producer katmanı — demo kırığının regresyonu ──────────────────


def test_dpad_all_directions_carry_action_metadata():
    """_generate_dpad_events artık stick ile AYNI canonical sözleşmeyi
    üretir: her KEYDOWN/KEYUP event'i from_gamepad + action + device_index
    taşır (DUZ-007 demo katman 2 — v2 paritesi)."""
    pygame.init()
    try:
        gpm = GamepadManager()
        gpm.set_context('game')
        expected = {
            (-1, 0): (pygame.K_LEFT, 'move_left'),
            (1, 0): (pygame.K_RIGHT, 'move_right'),
            (0, 1): (pygame.K_UP, 'rotate'),      # SDL hattı: yukarı = +1
            (0, -1): (pygame.K_DOWN, 'soft_drop'),
        }
        for hat, (expected_key, expected_action) in expected.items():
            gp = _dpad_state(hat, device_index=3)
            events = gpm._generate_dpad_events(gp, delta_ms=16.6)
            downs = [event for event in events if event.type == pygame.KEYDOWN]
            assert downs, f"D-pad {hat} KEYDOWN üretmeli"
            for event in downs:
                assert event.key == expected_key, f"D-pad {hat} -> {event.key}"
                assert event.from_gamepad is True
                assert event.action == expected_action, f"D-pad {hat} action={event.action!r}"
                assert event.device_index == 3
    finally:
        pygame.quit()


def test_dpad_up_rotate_survives_keyboard_rebind_end_to_end(monkeypatch):
    """DUZ-007 demo ana regresyonu: D-pad UP (varsayılan layout'un tek rotate
    kaynağı) gerçek Game.handle_input zincirinde, klavye rotate binding'i
    remap edilmiş olsa bile rotasyonu tetikler."""
    pygame.init()
    try:
        gpm = GamepadManager()
        gpm.set_context('game')
        gp = _dpad_state((0, 1))
        events = gpm._generate_dpad_events(gp, delta_ms=16.6)
    finally:
        pygame.quit()

    controls = _remap_single_action('rotate')
    game = _make_game(controls)
    assert game.control_bindings['rotate'] == pygame.K_f

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: list(events))
    game.handle_input()

    assert game.current_piece.rotation_state == 1
    assert game.sound.calls == ['rotate']


def test_menu_dpad_repeat_pulses_carry_action_metadata():
    """_generate_repeat_pulses (menü DAS tekrarı) artık gp_device_index +
    action_map alır: pulse'lar da canonical metadata taşır (v2 paritesi)."""
    pygame.init()
    try:
        gpm = GamepadManager()
        gpm.set_context('menu')
        gp = _dpad_state((0, 1), device_index=2)
        gp.prev_dpad = (0, 1)  # önceki frame de basılı → edge değil repeat yolu
        events = gpm._generate_dpad_events(gp, delta_ms=10000.0)

        pulses = [event for event in events if event.type in (pygame.KEYDOWN, pygame.KEYUP)]
        assert pulses, "Menü tekrar pulse'ı üretilmeli (delta_ms >> STICK_INITIAL_DELAY)"
        for event in pulses:
            assert event.key == pygame.K_UP
            assert event.from_gamepad is True
            assert event.action == 'menu_up'
            assert event.device_index == 2
    finally:
        pygame.quit()


# ─── (e) ACTION_TO_KEY sabit tablo ───────────────────────────────────────


def test_action_to_key_is_static_across_bindings():
    """ACTION_TO_KEY modül-düzeyi sabittir; gamepad/gameplay binding
    değişimleri tabloyu değiştirmez — sentetik event'ler her zaman
    kanonik key üretir (klavye remap'ten bağımsız)."""
    before = dict(ACTION_TO_KEY)

    manager = GamepadManager.__new__(GamepadManager)
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager._bindings['hard_drop'] = {'button': 3}
    manager._bindings['rotate'] = {'button': 11}

    assert dict(ACTION_TO_KEY) == before
    assert ACTION_TO_KEY['hard_drop'] == pygame.K_SPACE
    assert ACTION_TO_KEY['rotate'] == pygame.K_UP
    assert ACTION_TO_KEY['rotate_ccw'] == pygame.K_z
    assert ACTION_TO_KEY['move_left'] == pygame.K_LEFT
