"""D-pad custom dispatch + collision winner testleri (v2 + demo paritesi).

Gamepad_Iade_Nedeni_Cozum_Proje_Referansi.md 10.2 + 10.3 — aynı butona
düşen aksiyonlar arasında deterministik öncelik seçimi (GP-001) ve D-pad
yön butonlarının (11-14) custom aksiyon bağlanması:

- Çakışma çözümü: GAME_ACTION_PRIORITY / MENU_ACTION_PRIORITY önceliğine
  göre kazanan TEK aksiyon event üretir (hard_drop 100 > rotate 95 >
  rotate_ccw 94 > ... > card_* 50; menü: menu_confirm 100 > menu_back
  90 > ...). Duplicate KEYDOWN yok.
- Kazanan aksiyon D-pad butonuna custom bağlanmışsa buton yolu o
  aksiyonun KANONİK tuşunu üretir (örn. buton 11 → hard_drop → K_SPACE),
  event from_gamepad + action + device_index taşır; KEYUP da AYNI
  action damgasını taşır (DUZ-007 sözleşmesi).
- Bastırma (Kural 1): D-pad yön butonu kendi doğal aksiyonu DIŞINDA bir
  aksiyona bağlanınca o yönün doğal ok-tuşu HİÇ üretilmez — ne basışta
  KEYDOWN ne bırakışta KEYUP ("hiç basılmamış sayılır"); çapraz girdide
  yalnızca bastırılan yön kaybolur.
- SDL hat Y işareti: yukarı = +1 → K_UP; aşağı = -1 → K_DOWN. Yön
  ters çevirmesi Up→Down geçişinde KEYUP-önce sırasıyla düzgün işlenir.
- GP-007: oyun bağlamında D-pad HOLD repeat ÜRETMEZ (yalnız edge; oyunun
  DAS'ı kenarları tüketir); menü bağlamında STICK_INITIAL_DELAY (300ms)
  sonrası ilk KEYDOWN+KEYUP pulse çifti, sonra her STICK_REPEAT_INTERVAL
  (120ms)'te bir çift.

Repo notu (v2 ↔ demo): v2'de D-pad edge karşılaştırması debounce'lu
`prev_dpad_debounced_*` alanlarından, demo'da ham `prev_dpad`'dan yapılır
(v2 debounce_time<=0 → anında geçerli). `_set_prev_dpad` yardımcısı her
iki prev sözleşmesini birlikte ayarlar; öncelik tabloları v2'de modül
seviyesinde, demo'da metot içindedir — bu yüzden tablolar import
EDİLMEZ, davranış event çıktısından doğrulanır.

Desen referansı: tests/test_gamepad_hotplug.py (_make_manager),
tests/test_gamepad_remap_and_diagonal_dpad.py (GamepadState + hat set).
"""

from __future__ import annotations

import copy
import os
import sys
import types

import pytest

_SRC_DIR_STR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import pygame  # noqa: E402

from gamepad_manager import (  # noqa: E402
    ACTION_TO_KEY,
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


@pytest.fixture(scope='module', autouse=True)
def _pygame_init():
    pygame.init()
    yield


def _make_manager(context):
    """Minimal GamepadManager (test_gamepad_hotplug.py deseni)."""
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager._context = (
        GamepadManager.CONTEXT_GAME if context == 'game'
        else GamepadManager.CONTEXT_MENU
    )
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


def _set_prev_dpad(gp, dx, dy):
    """Önceki karenin D-pad durumunu ayarlar — v2: debounce'lu prev
    alanları (edge karşılaştırması prev_dpad_debounced_* üzerinden),
    demo: ham prev_dpad."""
    gp.prev_dpad = (dx, dy)
    if hasattr(gp, 'prev_dpad_debounced_dx'):
        gp.prev_dpad_debounced_dx = dx
        gp.prev_dpad_debounced_dy = dy


def _fake_joystick():
    return types.SimpleNamespace(get_init=lambda: True, get_name=lambda: 'Pad', quit=lambda: None)


def _press_button(manager, button, pressed=True, device_index=2):
    """Buton edge'i: prev_buttons boş → pressed_now geçişi."""
    gp = GamepadState(device_index=device_index)
    gp.connected = True
    gp.is_gamepad = True
    if pressed:
        gp.buttons[button] = True
    else:
        gp.prev_buttons[button] = True
    return gp, manager._generate_button_events(gp)


# ---------------------------------------------------------------------------
# 10.2 — collision winner deterministik seçim + metadata sözleşmesi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('context,overrides,button,expected_action,expected_key', [
    # Oyun: hard_drop (100) > rotate (95) — GP-001'nin belgelediği senaryo.
    ('game', {'hard_drop': 11, 'rotate': 11}, 11, 'hard_drop', pygame.K_SPACE),
    # Oyun: rotate (95) > card_bomb (50) — D-pad DIŞI buton çakışması.
    ('game', {'rotate': 5, 'card_bomb': 5}, 5, 'rotate', pygame.K_UP),
    # Oyun: hold (90) > soft_drop (85) — D-pad DIŞI buton çakışması.
    ('game', {'hold': 5, 'soft_drop': 5}, 5, 'hold', pygame.K_c),
    # Menü: menu_confirm (100) > menu_back (90).
    ('menu', {'menu_confirm': 1, 'menu_back': 1}, 1, 'menu_confirm', pygame.K_RETURN),
])
def test_collision_winner_dispatches_single_event_with_metadata(
    context, overrides, button, expected_action, expected_key,
):
    manager = _make_manager(context)
    for action, btn in overrides.items():
        manager._bindings[action] = {'button': btn}

    gp, events = _press_button(manager, button)

    downs = [e for e in events if e.type == pygame.KEYDOWN]
    assert len(downs) == 1, 'kazanan tek KEYDOWN üretmeli (duplicate yok)'
    event = downs[0]
    assert event.key == expected_key
    assert event.action == expected_action
    assert event.from_gamepad is True
    assert event.device_index == 2
    # Kaybeden aksiyon için hiçbir event üretilmez.
    assert all(e.key == expected_key for e in events)


def test_custom_dpad_button_keyup_carries_same_winner_action():
    """Kazananın KEYUP'ı da AYNI action damgasını taşır: bırakışta K_SPACE
    KEYUP action='hard_drop' gelir (DUZ-007 metadata sözleşmesi)."""
    manager = _make_manager('game')
    manager._bindings['hard_drop'] = {'button': 11}
    manager._bindings['rotate'] = {'button': 11}

    _, down_events = _press_button(manager, 11, pressed=True)
    assert [e.type for e in down_events] == [pygame.KEYDOWN]
    assert down_events[0].action == 'hard_drop'

    _, up_events = _press_button(manager, 11, pressed=False)
    ups = [e for e in up_events if e.type == pygame.KEYUP]
    assert len(ups) == 1
    assert ups[0].key == ACTION_TO_KEY['hard_drop']
    assert ups[0].action == 'hard_drop', 'KEYUP aynı kazanan action damgasını taşımali'
    assert ups[0].from_gamepad is True


def test_natural_dpad_action_binding_skips_button_path():
    """Doğal eşleşme kuralı (çift tetikleme önleme): D-pad yön butonu kendi
    DOĞAL aksiyonuna bağlıysa buton yolu o aksiyonu SKIP eder — buton 11 =
    rotate (doğal) → buton basışı 0 event üretir; K_UP yalnızca D-pad hat
    yolundan, tek kez gelir."""
    manager = _make_manager('game')
    manager._bindings['rotate'] = {'button': 11}

    # Buton yolu: doğal eşleşme → skip.
    _, events = _press_button(manager, 11)
    assert events == []

    # Hat yolu: Up yönü → tek K_UP KEYDOWN.
    gp = GamepadState(device_index=0)
    gp.connected = True
    gp.is_gamepad = True
    gp.dpad = (0, 1)
    _set_prev_dpad(gp, 0, 0)
    hat_events = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert [(e.key, e.type) for e in hat_events] == [
        (pygame.K_UP, pygame.KEYDOWN),
    ]


# ---------------------------------------------------------------------------
# 10.3 — bastırma: doğal yön event'i açılmaz (ne KEYDOWN ne KEYUP)
# ---------------------------------------------------------------------------

def test_suppressed_dpad_up_produces_neither_keydown_nor_keyup():
    """Buton 11 hard_drop'a bağlanınca (rotate değil) 'up' yönü bastırılır:
    D-pad Up basılı/bırakılı doğal K_UP ÜRETMEZ; çapraz girdide yalnızca
    bastırılan yön kaybolur; polling (is_direction_held) da False'tur."""
    manager = _make_manager('game')
    manager._bindings['hard_drop'] = {'button': 11}
    manager._bindings['rotate'] = {'button': 11}

    gp = GamepadState(device_index=0, joystick=_fake_joystick())
    gp.connected = True
    gp.is_gamepad = True
    manager.gamepads[0] = gp
    try:
        # Basış: hat (0,1), önceki (0,0) → doğal K_UP KEYDOWN üretilMEZ.
        gp.dpad = (0, 1)
        _set_prev_dpad(gp, 0, 0)
        events = manager._generate_dpad_events(gp, delta_ms=16.6)
        assert not [e for e in events if e.key == pygame.K_UP], (
            'bastırılan yön doğal KEYDOWN üretmemeli'
        )
        assert events == [], 'bu karede başka yön de yok'

        # Bırakış: hat (0,0), önceki (0,1) → doğal K_UP KEYUP üretilMEZ.
        gp.dpad = (0, 0)
        _set_prev_dpad(gp, 0, 1)
        events = manager._generate_dpad_events(gp, delta_ms=16.6)
        assert events == [], 'bastırılan yönün KEYUP\'ı da üretilmemeli'

        # Çapraz: hat (1,1) → K_RIGHT üretilmeye DEVAM eder, K_UP yine yok.
        gp.dpad = (1, 1)
        _set_prev_dpad(gp, 0, 0)
        events = manager._generate_dpad_events(gp, delta_ms=16.6)
        keys = [(e.key, e.type) for e in events]
        assert (pygame.K_RIGHT, pygame.KEYDOWN) in keys
        assert all(e.key != pygame.K_UP for e in events)

        # Held polling: bastırılan 'up' yönü basılı DEĞİL sayılır.
        assert manager.is_direction_held('up') is False
    finally:
        manager.gamepads.pop(0, None)


# ---------------------------------------------------------------------------
# 10.3 — Up→Down→release dizisi (SDL hat Y işareti) duplicatesiz
# ---------------------------------------------------------------------------

def test_up_down_release_sequence_without_duplicates():
    """Doğal D-pad: (0,1)→K_UP down; (0,-1)→K_UP UP + K_DOWN DOWN (Y
    işareti: yukarı=+1, aşağı=-1); (0,0)→K_DOWN up. Hiçbir tuş için
    çift KEYDOWN yok; tüm event'ler action metadata taşır."""
    manager = _make_manager('game')
    gp = GamepadState(device_index=7)
    gp.connected = True
    gp.is_gamepad = True

    # Kare 1: Up basış.
    gp.dpad = (0, 1)
    _set_prev_dpad(gp, 0, 0)
    frame1 = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert [(e.key, e.type, e.action) for e in frame1] == [
        (pygame.K_UP, pygame.KEYDOWN, 'rotate'),
    ]

    # Kare 2: Up → Down (Y ekseni ters çevirme; KEYUP ÖNCE gelir).
    gp.dpad = (0, -1)
    _set_prev_dpad(gp, 0, 1)
    frame2 = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert [(e.key, e.type, e.action) for e in frame2] == [
        (pygame.K_UP, pygame.KEYUP, 'rotate'),
        (pygame.K_DOWN, pygame.KEYDOWN, 'soft_drop'),
    ]

    # Kare 3: Down bırakılış.
    gp.dpad = (0, 0)
    _set_prev_dpad(gp, 0, -1)
    frame3 = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert [(e.key, e.type, e.action) for e in frame3] == [
        (pygame.K_DOWN, pygame.KEYUP, 'soft_drop'),
    ]

    for events in (frame1, frame2, frame3):
        for event in events:
            assert event.from_gamepad is True
            assert event.device_index == 7


# ---------------------------------------------------------------------------
# GP-007 — oyun: edge-only; menü: initial delay + repeat cadence
# ---------------------------------------------------------------------------

def test_game_context_dpad_hold_generates_no_repeat():
    """Oyun bağlamında D-pad basılı tutulup delta_ms tekrar eşiklerini
    aştığında HİÇ repeat pulse üretilmez (oyunun DAS'ı kenarları tüketir)."""
    manager = _make_manager('game')
    gp = GamepadState(device_index=0)
    gp.connected = True
    gp.is_gamepad = True

    gp.dpad = (0, 1)
    _set_prev_dpad(gp, 0, 0)
    first = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert len(first) == 1  # yalnız edge KEYDOWN

    _set_prev_dpad(gp, 0, 1)
    for _ in range(3):
        events = manager._generate_dpad_events(gp, delta_ms=400.0)
        assert events == [], 'oyun bağlamında D-pad repeat pulse üretmemeli'


def test_menu_dpad_repeat_initial_delay_threshold_and_cadence():
    """Menü bağlamında D-pad DAS tekrarı: STICK_INITIAL_DELAY (300ms)
    aşılmadan pulse YOK; aşılınca ilk KEYDOWN+KEYUP çifti; ardından her
    STICK_REPEAT_INTERVAL (120ms)'te tam bir çift."""
    manager = _make_manager('menu')
    gp = GamepadState(device_index=3)
    gp.connected = True
    gp.is_gamepad = True

    # Edge karesi: ilk basış KEYDOWN.
    gp.dpad = (0, 1)
    _set_prev_dpad(gp, 0, 0)
    edge_events = manager._generate_dpad_events(gp, delta_ms=16.6)
    assert [e.type for e in edge_events] == [pygame.KEYDOWN]

    _set_prev_dpad(gp, 0, 1)

    # 299ms: initial delay altı → pulse yok.
    events = manager._generate_dpad_events(gp, delta_ms=299.0)
    assert events == [], '300ms altında repeat pulse üretmemeli'

    # +10ms (toplam 309): ilk pulse ÇİFTİ.
    events = manager._generate_dpad_events(gp, delta_ms=10.0)
    assert [(e.key, e.type, e.action) for e in events] == [
        (pygame.K_UP, pygame.KEYDOWN, 'menu_up'),
        (pygame.K_UP, pygame.KEYUP, 'menu_up'),
    ]
    assert all(e.device_index == 3 and e.from_gamepad is True for e in events)

    # 119ms: interval altı → pulse yok.
    events = manager._generate_dpad_events(gp, delta_ms=119.0)
    assert events == [], '120ms altında yeni pulse üretmemeli'

    # +10ms (toplam 129): tam bir çift daha.
    events = manager._generate_dpad_events(gp, delta_ms=10.0)
    assert [(e.key, e.type) for e in events] == [
        (pygame.K_UP, pygame.KEYDOWN),
        (pygame.K_UP, pygame.KEYUP),
    ]
