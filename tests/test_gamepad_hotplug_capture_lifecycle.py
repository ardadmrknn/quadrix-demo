"""Hotplug × capture lifecycle testleri (v2 + demo paritesi).

Gamepad_Iade_Nedeni_Cozum_Proje_Referansi.md 10.4 + 13 ve GP-004/GP-005
sözleşmelerinin hotplug kesişimi:

Kaynak sözleşme (settings_screen_tabbed + gamepad_manager + main.py):
- Settings ekranı JOYDEVICEADDED/JOYDEVICEREMOVED eventlerini İŞLEMEZ;
  hotplug, main.py merkezî dreyninde (gameplay-dışı state'ler) veya oyun
  runtime'larının handle_input'ında işlenir. Capture durumu
  (_waiting_for_key / _pending_keybind_item / _pending_keybind_slot)
  hotplug'dan BAĞIMSIZDIR: cihaz kopsa da capture yeni girdi bekleyerek
  açık kalır.
- Hold-to-clear mid-hold disconnect: imza kurulmuşken cihaz koptuğunda
  is_capture_input_held False döner (manager'da cihaz kalmamıştır) →
  _check_hold_to_clear_progress RESET yolunu çalıştırır: imza + zaman
  damgası sıfırlanır, slot DEĞİŞMEZ (clear YOK), capture AÇIK kalır.
- REMOVED dalı _purge_capture_edges_for_devices ÇAĞIRMAZ (bilinçli):
  SDL cihazları capture kenar kuyruğuna hiç yazılmaz; Steam Input
  fallback cihazlarının ölü kenarları update() senkronunda atılır.
- Capture girdisi cihaz-agnostiktir: hangi cihazdan gelirse gelsin
  CONTROLLERBUTTONDOWN kabul edilir; is_capture_input_held TÜM bağlı
  cihazların canonical butonlarını tarar; get_active_gamepad seçimi
  capture akışında rol oynamaz.

Not: referans doküman 10.6'daki `manager.set_canonical_state(...)` ve
`settings.binding_was_cleared` API'leri KAYNAKTA YOKTUR — karşılıkları
is_capture_input_held / _start_keybind_capture / _clear_keybind_slot'dur;
bu testler yalnızca GERÇEK API'leri kullanır.

Desen referansları: tests/test_gamepad_hold_to_clear_canonical_state.py
(live_screen fixture + hold-to-clear akışı), tests/test_gamepad_hotplug.py
(_make_manager / _fake_gamepad_state / hotplug event fabrikaları).
"""

from __future__ import annotations

import copy
import os
import sys
import types

import pytest

# test_gamepad_hotplug.py deseni: sys.path girdisinin string formu diğer
# testlerle AYNI olmalı; aksi halde gamepad_manager iki kez yüklenir ve
# singleton senkronu kopar.
_SRC_DIR_STR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import gamepad_manager as gpm_module  # noqa: E402
from gamepad_manager import (  # noqa: E402
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


def _make_manager():
    """Minimal GamepadManager (test_gamepad_hotplug.py deseni) — __init__
    yan etkilerini (settings yükleme, ilk tarama) atlar; _check_connections
    stub'lanmaz."""
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager._context = GamepadManager.CONTEXT_GAME
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


def _added_event(device_index: int):
    return types.SimpleNamespace(
        type=gpm_module.pygame.JOYDEVICEADDED,
        device_index=device_index,
    )


def _removed_event(instance_id: int):
    return types.SimpleNamespace(
        type=gpm_module.pygame.JOYDEVICEREMOVED,
        instance_id=instance_id,
    )


def _fake_gamepad_state(instance_id: int, name: str = 'Xbox Wireless'):
    """Disconnect yolunu karşılayan hafif GamepadState (quit/get_init/get_name)."""
    fake_js = types.SimpleNamespace(
        get_init=lambda: True,
        get_name=lambda: name,
        quit=lambda: None,
    )
    return GamepadState(
        joystick=fake_js,
        controller=None,
        gamepad_type='xbox',
        name=name,
        guid='',
        instance_id=instance_id,
    )


@pytest.fixture(scope='module')
def live_screen():
    """Tek display + TabbedSettingsScreen; dönen gamepad_manager modülü,
    settings_screen_tabbed'ın import ettiği AYNI modül kimliğidir
    (test_gamepad_hold_to_clear_canonical_state.py deseni)."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

    for mod in [
        'settings_screen_tabbed', 'constants', 'retro_style',
        'platform_utils', 'background_effects', 'localization',
        'ui_language_profile', 'menu', 'gamepad_manager',
        'promptfont_support', 'ui_scaling', 'settings_manager',
    ]:
        sys.modules.pop(mod, None)

    import pygame
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    pygame.init()
    pygame.display.set_mode((1280, 720))

    import settings_screen_tabbed as sst
    import gamepad_manager as gm_mod
    from settings_manager import SettingsManager

    sm = SettingsManager()
    screen = pygame.display.get_surface()
    inst = sst.TabbedSettingsScreen(screen, None, sm)
    inst.current_tab = 3  # Kontroller
    inst._rebuild_tab_content()
    inst._persist_controls = lambda: None
    return pygame, inst, gm_mod


def _open_capture(inst, action_key='hard_drop', section='gamepad.ingame', slot='primary'):
    """Capture bekleme durumunu kurar (test_gamepad_capture_escape_isolation deseni)."""
    inst._waiting_for_key = True
    inst._pending_keybind_item = {
        'type': 'keybind', 'section': section, 'action_key': action_key,
    }
    inst._pending_keybind_slot = slot
    inst._capture_started_by_gamepad_click = False
    inst._swallow_next_keydown = False
    inst._swallow_next_gamepad_click = False
    inst._reset_hold_to_clear_state()


# ---------------------------------------------------------------------------
# Manager katmanı: hotplug'in capture kenar kuyruğuyla etkileşimi
# ---------------------------------------------------------------------------

def test_removed_event_leaves_capture_edge_queue_untouched():
    """REMOVED dalı _purge_capture_edges_for_devices çağırmaz (bilinçli
    tasarım): SDL cihazları kuyruğa yazılmaz, Steam fallback cihazlarının
    ölü kenarları update() senkronunda atılır. Hotplug kuyruğu değiştirmez."""
    from collections import deque

    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42)
    manager._capture_edges = deque([
        ('steam-pad-1', 3, True, 123.0),
        ('steam-pad-1', 100, False, 124.0),
    ])
    before = list(manager._capture_edges)

    result = manager.handle_hotplug_event(_removed_event(42))

    assert result == 'disconnected'
    assert 0 not in manager.gamepads
    assert list(manager._capture_edges) == before, (
        'JOYDEVICEREMOVED capture kenar kuyruğunu değiştirmemeli'
    )


# ---------------------------------------------------------------------------
# Settings × hotplug: capture durumu hotplug'dan bağımsızdır
# ---------------------------------------------------------------------------

def test_capture_stays_open_when_device_removed_mid_wait(live_screen):
    """Capture açıkken cihaz koparsa: settings durumu değişmez — capture
    iptal olmaz, yeni girdi beklemeye devam eder (iptal yalnız GERÇEK
    klavye Escape ile olur, GP-002)."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    _open_capture(inst)
    pending = dict(inst._pending_keybind_item)

    gpm.gamepads[0] = _fake_gamepad_state(instance_id=42)
    try:
        assert inst._waiting_for_key is True

        result = gm_mod.handle_gamepad_hotplug_event(_removed_event(42))
        assert result == 'disconnected'
        assert 0 not in gpm.gamepads

        # Birkaç frame sür: capture durumu hotplug'dan etkilenmemeli.
        inst.update(16.0)
        inst.update(16.0)

        assert inst._waiting_for_key is True, 'capture kopmada iptal olmamalı'
        assert dict(inst._pending_keybind_item) == pending
        assert inst._hold_to_clear_pressed_signature is None
    finally:
        gpm.gamepads.pop(0, None)


def test_mid_hold_disconnect_resets_progress_without_clearing_slot(live_screen, monkeypatch):
    """Hold-to-clear sürerken cihaz koptuğunda: reset yolu çalışır — imza
    sıfırlanır, slot DEĞİŞMEZ (clear YOK), capture AÇIK kalır. Yanlışlıkla
    slot temizlenirse kullanıcı binding'ini sessizce kaybeder."""
    pygame, inst, gm_mod = live_screen
    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    if not isinstance(gamepad_cfg.get('hard_drop'), dict):
        gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
    gamepad_cfg['hard_drop']['primary'] = 10

    fake_ms = [10000]
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: fake_ms[0])

    _open_capture(inst)
    inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=3))
    assert inst._hold_to_clear_pressed_signature == ('btn', 3)

    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    pad = _fake_gamepad_state(instance_id=42)
    pad.buttons[3] = True  # canonical buton 3 basılı
    gpm.gamepads[0] = pad
    try:
        # Eşik altında: henüz temizlememeli.
        fake_ms[0] = 10000 + 800
        inst.update(16.0)
        assert gamepad_cfg['hard_drop']['primary'] == 10

        # Cihaz basılı tutulurken koptu.
        result = gm_mod.handle_gamepad_hotplug_event(_removed_event(42))
        assert result == 'disconnected'
        assert 0 not in gpm.gamepads

        # Eşik aşıldı ama artık basılı tutan cihaz YOK.
        fake_ms[0] = 10000 + 1600
        inst.update(16.0)

        assert inst._hold_to_clear_pressed_signature is None, (
            'mid-hold disconnect imzayı sıfırlamalı'
        )
        assert inst._hold_to_clear_pressed_at_ms is None
        assert inst._hold_to_clear_consumed is False
        assert inst._waiting_for_key is True, 'capture açık kalmalı (clear YOK)'
        assert gamepad_cfg['hard_drop']['primary'] == 10, (
            'kopan cihaz slotu TEMİZLEMEMELİ (yalnızca gerçek hold temizler)'
        )
    finally:
        gpm.gamepads.pop(0, None)


def test_replug_after_disconnect_restarts_capture_with_new_binding(live_screen, monkeypatch):
    """Kopma → mid-hold reset → yeniden bağlanma zinciri: capture açık
    kalır, yeni cihazın butonu YENİ imza kurar ve bırakışta binding
    normal akışla uygulanır."""
    pygame, inst, gm_mod = live_screen
    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    if not isinstance(gamepad_cfg.get('hard_drop'), dict):
        gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
    gamepad_cfg['hard_drop']['primary'] = 10

    fake_ms = [10000]
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: fake_ms[0])

    _open_capture(inst)
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    old_pad = _fake_gamepad_state(instance_id=42)
    old_pad.buttons[3] = True
    gpm.gamepads[0] = old_pad
    try:
        inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=3))
        assert inst._hold_to_clear_pressed_signature == ('btn', 3)

        # Cihaz koptu → mid-hold reset (capture açık kalır).
        gm_mod.handle_gamepad_hotplug_event(_removed_event(42))
        fake_ms[0] = 10000 + 1600
        inst.update(16.0)
        assert inst._waiting_for_key is True
        assert inst._hold_to_clear_pressed_signature is None

        # YENİ cihaz bağlanır (replug): ADDED → _register_gamepad.
        new_pad = _fake_gamepad_state(instance_id=99, name='Fresh Pad')
        monkeypatch.setattr(
            gpm,
            '_register_gamepad',
            lambda idx: gpm.gamepads.setdefault(idx, new_pad) or True,
        )
        result = gm_mod.handle_gamepad_hotplug_event(_added_event(1))
        assert result == 'connected'
        assert gpm.gamepads[1] is new_pad

        # Yeni cihazdan yeni buton: yeni imza + kısa bırakış → binding.
        fake_ms[0] = 10000 + 2000
        inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=4))
        assert inst._hold_to_clear_pressed_signature == ('btn', 4)
        assert inst._hold_to_clear_pressed_at_ms == 10000 + 2000

        fake_ms[0] = 10000 + 2100  # eşik altı bırakış → apply
        inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONUP, button=4))

        assert gamepad_cfg['hard_drop']['primary'] == 4
        assert inst._waiting_for_key is False
    finally:
        gpm.gamepads.pop(0, None)
        gpm.gamepads.pop(1, None)


def test_settings_handle_input_ignores_hotplug_event_types(live_screen):
    """Settings handle_input JOYDEVICEREMOVED/JOYDEVICEADDED tiplerini
    işlemez (hotplug merkezî dreynindedir) — capture açıkken bu eventler
    gelirse durum değişmez."""
    pygame, inst, gm_mod = live_screen
    _open_capture(inst)
    pending = dict(inst._pending_keybind_item)

    inst.handle_input(pygame.event.Event(pygame.JOYDEVICEREMOVED, which=5, instance_id=5))
    inst.handle_input(pygame.event.Event(pygame.JOYDEVICEADDED, device_index=2))

    assert inst._waiting_for_key is True
    assert dict(inst._pending_keybind_item) == pending
    assert inst._hold_to_clear_pressed_signature is None


def test_capture_reads_buttons_from_any_connected_gamepad(live_screen):
    """Capture girdisi cihaz-agnostiktir: get_active_gamepad İLK cihazı
    seçer ama capture İKİNCİ cihazın butonunu da kabul eder; hold kontrolü
    TÜM bağlı cihazların canonical butonlarını tarar."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    pad_a = _fake_gamepad_state(instance_id=1, name='Pad A')
    pad_b = _fake_gamepad_state(instance_id=2, name='Pad B')
    gpm.gamepads[0] = pad_a
    gpm.gamepads[1] = pad_b
    try:
        # get_active_gamepad ilk init'li cihazı döner (capture bunu KULLANMAZ).
        assert gpm.get_active_gamepad() is pad_a

        _open_capture(inst)

        # İKİNCİ cihazın butonu capture imzası kurar.
        inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=6))
        assert inst._hold_to_clear_pressed_signature == ('btn', 6)

        # Hold kontrolü cihaz-agnostik: pad_b'de 6 basılıysa sürer.
        pad_b.buttons[6] = True
        assert gpm.is_capture_input_held(('btn', 6)) is True
        assert gpm.is_capture_input_held(('btn', 7)) is False
    finally:
        gpm.gamepads.pop(0, None)
        gpm.gamepads.pop(1, None)
