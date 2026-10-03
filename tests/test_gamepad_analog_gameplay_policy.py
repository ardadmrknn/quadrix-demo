"""GP-007 — Sol analog stick oyun içi hareket politikası (ÜRÜN KARARI: Politika 1).

İade nedeni: oyun context'inde sol stick tamamen kapalıydı
(`_generate_stick_events` doğrudan `return []`) ve `is_direction_held`
stick'i oyun bağlamında yok sayıyordu — "gamepad optimize değil"
iadesinin bir bileşeni. Varsayılan bağlama tablosu move_left/move_right/
soft_drop için 'axis' tanımlayıcısı taşıdığı hâlde runtime bunu
hiçbir şekilde kullanamıyordu.

Ürün kararı (Politika 1 — analog destekli): oyun içinde sol stick,
D-pad ile AYNI canonical sözleşmeyle çalışır:
- sapma → KEYDOWN (action: move_left/move_right/soft_drop/rotate),
- bırakış → KEYUP,
- yalnızca KENAR olayları: menü tipi DAS/tekrar pulse'ları oyun
  bağlamına taşınmaz (oyunun kendi DAS/ARR'i bu edge'leri tüketir;
  sentetik tekrar pulse'u DAS'ı çift tetikler),
- hysteresis: dijitalleşme giriş eşiği DIGITAL_THRESHOLD, çıkış eşiği
  STICK_RELEASE_THRESHOLD → eşik bandındaki salınımlar event spam üretmez,
- override edilmiş (bastırılmış) yönler D-pad ile aynı conflict
  resolver kararıyla bastırılır,
- `is_direction_held` oyun bağlamında stick'i de sayar (soft drop
  polling dahil); sağ stick pointer emülasyonu etkilenmez.
"""

from __future__ import annotations

import copy
import os
import sys
from types import SimpleNamespace

import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import gamepad_manager as gamepad_manager_module  # noqa: E402
from gamepad_manager import (  # noqa: E402
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


class _DummyJoystick:
    """Eksen degerleri frame'ler arasi degistirilebilen sahte joystick.

    Eksen duzeni (SDL GameController): (LX, LY, RX, RY, LT, RT) → 6 eksen.
    """

    def __init__(self, axes):
        self.axes = list(axes)
        self.buttons: dict[int, bool] = {}
        self.hats: tuple = ()

    def get_init(self) -> bool:
        return True

    def get_numaxes(self) -> int:
        return len(self.axes)

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def get_numbuttons(self) -> int:
        return 0

    def get_button(self, index: int) -> int:
        return 0

    def get_numhats(self) -> int:
        return len(self.hats)

    def get_hat(self, index: int):
        return self.hats[index]


def _neutral_axes():
    return [0.0, 0.0, 0.0, 0.0, -1.0, -1.0]


def _make_manager(context=GamepadManager.CONTEXT_GAME):
    manager = GamepadManager.__new__(GamepadManager)
    manager.enabled = True
    manager.gamepads = {}
    manager.rumble_enabled = False
    manager.rumble_level = 'off'
    manager.rumble_multiplier = 0.0
    manager.MOUSE_SPEED = 20.0
    manager.MOUSE_SENSITIVITY = 1.0
    manager.MOUSE_DEADZONE = 0.12
    manager.MOUSE_ACCEL_EXPONENT = 2.0
    manager.MOUSE_ACTIVATE_THRESHOLD = 0.30
    manager.MOUSE_RELEASE_THRESHOLD = 0.14
    manager.MOUSE_NEUTRAL_TRACK_THRESHOLD = 0.24
    manager.MOUSE_NEUTRAL_FOLLOW_RATE = 0.08
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    manager._context = context
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager._check_connections = lambda: None
    return manager


@pytest.fixture(autouse=True)
def _patch_pygame_event(monkeypatch):
    """update() icindeki sentetik event uretimi pygame.event.Event'e ihtiyac duyar."""
    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )
    if not hasattr(gp_pygame, 'display'):
        monkeypatch.setattr(gp_pygame, 'display', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.display, 'get_window_size', lambda: (1280, 720), raising=False
    )
    monkeypatch.setattr(
        gp_pygame.display, 'get_surface', lambda: None, raising=False
    )


def _key_events(events, key):
    """Sadece belirtilen tuşa ait KEYDOWN/KEYUP event'lerini süz."""
    return [e for e in events if getattr(e, 'key', None) == key]


def test_game_context_stick_right_edge_events_only():
    """Oyun içinde stick sağ: KEYDOWN bir kez, tekrar pulse YOK, bırakışta KEYUP."""
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp

    # Frame 1: kalibrasyon (nötr)
    manager.update(16.0)

    # Frame 2: stick sağa tam sapma → KEYDOWN K_RIGHT (action: move_right)
    gp.joystick.axes = [0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    downs = [e for e in _key_events(events, gamepad_manager_module.pygame.K_RIGHT)
             if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert len(downs) == 1, 'stick sağ sapması tam bir KEYDOWN üretmeli'
    assert getattr(downs[0], 'action', None) == 'move_right'
    assert getattr(downs[0], 'from_gamepad', False) is True

    # Frame 3-5: aynı yönde tutulmaya devam → tekrar pulse YOK (oyun bağlamı)
    for _ in range(3):
        events = manager.update(400.0)
        assert _key_events(events, gamepad_manager_module.pygame.K_RIGHT) == [], \
            'oyun bağlamında stick tekrar pulse üretmemeli (DAS oyunun kendisinde)'

    # Frame 6: bırakış → KEYUP K_RIGHT (action: move_right)
    gp.joystick.axes = _neutral_axes()
    events = manager.update(16.0)
    ups = [e for e in _key_events(events, gamepad_manager_module.pygame.K_RIGHT)
           if e.type == gamepad_manager_module.pygame.KEYUP]
    assert len(ups) == 1, 'stick bırakışı tam bir KEYUP üretmeli'
    assert getattr(ups[0], 'action', None) == 'move_right'


def test_game_context_stick_left_maps_move_left():
    """Oyun içinde stick sol: KEYDOWN K_LEFT (action: move_left)."""
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp

    manager.update(16.0)
    gp.joystick.axes = [-0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    downs = [e for e in _key_events(events, gamepad_manager_module.pygame.K_LEFT)
             if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert len(downs) == 1
    assert getattr(downs[0], 'action', None) == 'move_left'


def test_game_context_stick_down_soft_drop_edge_and_held():
    """Oyun içinde stick aşağı: KEYDOWN K_DOWN (action: soft_drop) VE held polling.

    game.py soft drop'u `is_direction_held('down')` ile poll eder; stick
    aşağı bu sorguda da True dönmeli (yalnızca event değil).
    """
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp

    manager.update(16.0)
    assert manager.is_direction_held('down') is False

    gp.joystick.axes = [0.0, 0.9, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    downs = [e for e in _key_events(events, gamepad_manager_module.pygame.K_DOWN)
             if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert len(downs) == 1
    assert getattr(downs[0], 'action', None) == 'soft_drop'
    assert manager.is_direction_held('down') is True, \
        'oyun bağlamında stick aşağı is_direction_held("down") True dönmeli'

    # Basılı tutma sırasında ek event YOK (tekrar pulse yok)
    events = manager.update(400.0)
    assert _key_events(events, gamepad_manager_module.pygame.K_DOWN) == []

    # Bırakış → KEYUP + polling False
    gp.joystick.axes = _neutral_axes()
    events = manager.update(16.0)
    ups = [e for e in _key_events(events, gamepad_manager_module.pygame.K_DOWN)
           if e.type == gamepad_manager_module.pygame.KEYUP]
    assert len(ups) == 1
    assert manager.is_direction_held('down') is False


def test_game_context_stick_up_maps_rotate():
    """Oyun içinde stick yukarı: KEYDOWN K_UP (action: rotate) — D-pad up ile aynı."""
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp

    manager.update(16.0)
    gp.joystick.axes = [0.0, -0.9, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    downs = [e for e in _key_events(events, gamepad_manager_module.pygame.K_UP)
             if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert len(downs) == 1
    assert getattr(downs[0], 'action', None) == 'rotate'


def test_stick_hysteresis_no_flap_near_threshold():
    """Dijitalleşme hysteresis: eşik bandındaki salınım event spam üretmez.

    Giriş eşiği DIGITAL_THRESHOLD=0.6 (deadzone sonrası değer), çıkış eşiği
    STICK_RELEASE_THRESHOLD. Ham eksen 0.72 → normalize ~0.57 (band içinde,
    yön KORUNUR); ham 0.5 → normalize ~0.23 (çıkış eşiği altı → KEYUP).
    """
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp
    K_R = gamepad_manager_module.pygame.K_RIGHT

    manager.update(16.0)

    # Tam sapma → KEYDOWN
    gp.joystick.axes = [0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    assert len([e for e in _key_events(events, K_R) if e.type == gamepad_manager_module.pygame.KEYDOWN]) == 1

    # Band içi değerler (normalize 0.57 ve 0.46): yön korunmalı, event YOK
    for raw_lx in (0.72, 0.65):
        gp.joystick.axes = [raw_lx, 0.0, 0.0, 0.0, -1.0, -1.0]
        events = manager.update(16.0)
        assert _key_events(events, K_R) == [], \
            f'ham {raw_lx} eşik bandı içinde: KEYUP/KEYDOWN üretilmemeli (hysteresis)'

    # Çıkış eşiği altı (normalize ~0.23) → KEYUP
    gp.joystick.axes = [0.5, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    ups = [e for e in _key_events(events, K_R) if e.type == gamepad_manager_module.pygame.KEYUP]
    assert len(ups) == 1, 'çıkış eşiği altına inince tam bir KEYUP üretilmeli'


def test_menu_context_stick_repeat_preserved():
    """Menü bağlamında mevcut davranış korunur: navigasyon + DAS tekrar pulse."""
    manager = _make_manager(context=GamepadManager.CONTEXT_MENU)
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp
    K_R = gamepad_manager_module.pygame.K_RIGHT

    manager.update(16.0)

    # Edge: KEYDOWN K_RIGHT (action: menu_right)
    gp.joystick.axes = [0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    downs = [e for e in _key_events(events, K_R) if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert len(downs) == 1
    assert getattr(downs[0], 'action', None) == 'menu_right'

    # Basılı tutma + STICK_INITIAL_DELAY aşımı → tekrar pulse gelmeli
    events = manager.update(400.0)
    repeat_downs = [e for e in _key_events(events, K_R)
                    if e.type == gamepad_manager_module.pygame.KEYDOWN]
    assert repeat_downs, 'menü bağlamında stick tekrar pulse üretmeli (mevcut davranış)'


def test_suppressed_direction_not_emitted_by_stick_in_game():
    """Override edilmiş yön D-pad ile AYNI kararla stick tarafından da bastırılır.

    move_left başka bir butona (LB=9) bağlanınca 'left' override edilir:
    D-pad'in doğal emülasyonu bastırıldığı gibi stick'in sol sapması da
    move_left KEYDOWN üretmemeli; is_direction_held de False dönmeli.
    """
    manager = _make_manager()
    manager._bindings['move_left'] = {'button': 9}
    gp = GamepadState(joystick=_DummyJoystick(_neutral_axes()), gamepad_type='xbox')
    manager.gamepads[0] = gp
    K_L = gamepad_manager_module.pygame.K_LEFT

    manager.update(16.0)
    assert manager._get_overridden_dpad_dirs() == {'left'}

    gp.joystick.axes = [-0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    events = manager.update(16.0)
    assert _key_events(events, K_L) == [], \
        'bastırılmış yön için stick KEYDOWN üretmemeli (D-pad politikasıyla aynı)'

    # Bırakışta da KEYUP üretilmemeli (hiç basılmamış sayılır)
    gp.joystick.axes = _neutral_axes()
    events = manager.update(16.0)
    assert _key_events(events, K_L) == []

    # Held polling de bastırılmış yön için False
    gp.joystick.axes = [-0.9, 0.0, 0.0, 0.0, -1.0, -1.0]
    manager.update(16.0)
    assert manager.is_direction_held('left') is False
