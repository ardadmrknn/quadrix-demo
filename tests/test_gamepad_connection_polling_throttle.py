"""OP-049 (D8): gamepad bağlantı polling throttle davranış testleri.

`update()` içindeki `_check_connections()` çağrısı
`CONNECTION_POLL_INTERVAL_MS` (250 ms) aralığıyla throttle'lanmıştır.
Sözleşmeler (bkz. plans/2026-10-09-dalga-d-uygulama-plani.md D8):

- İlk `update()` çağrısı polling'i HER ZAMAN çalıştırır (startup taraması
  korunur; `_last_conn_check_ms` float('-inf') ile ilklenir).
- Aralık dolmadan polling tekrar koşmaz.
- Aralık dolduğunda (>= 250 ms) tekrar koşar.
- `handle_hotplug_event` (JOYDEVICEADDED/REMOVED) event yolu throttle'dan
  etkilenmez — gerçek zamanlı kalır.
- Girdi okuma döngüsü (buton/eksen/d-pad) her kare koşar; DAS/d-pad
  zamanlaması etkilenmez.
- `__new__` bypass'lı bare-instance yöneticilerde AttributeError yok
  (alanlar hasattr idyomuyla ilklenir — `_internal_time` düzeniyle aynı).
- Deck/macOS "geç güncellenen get_count" uyarısı nedeniyle aralık üst
  sınırı 500 ms'tir; sabit guard'la denetlenir.
"""

from __future__ import annotations

import os as _os
import sys
import types


# `os.path.join(..., '..', 'src')` formu: test_gamepad_hotplug.py ile AYNI
# sys.path string formu — formlar farklılaşırsa gamepad_manager iki kez
# yüklenebilir (bkz. o dosyanın başındaki açıklama).
_SRC_DIR_STR = _os.path.join(_os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import gamepad_manager as gpm_module  # noqa: E402
from gamepad_manager import GamepadManager, GamepadState  # noqa: E402

# Modül kopyası çatallanması durumunda kanonik kopyaya bağlan.
_canonical = sys.modules.get('gamepad_manager')
if _canonical is not None and _canonical is not gpm_module:
    gpm_module = _canonical


def _make_manager():
    """__new__ bypass'lı minimal yönetici (test_gamepad_hotplug idyomu).

    `_refresh_empty_startup_scan` / `_sync_steam_input_gamepads` stub'lanır:
    bunlar D8 kapsamı DIŞINDADIR (Steam Input koşullu yolları — minimal
    blast radius). `_check_connections` testlerde monkeypatch sayaca
    bağlanır; `_internal_time`/`_last_conn_check_ms` ilkleme idiyomunun
    kendisi test edilir.
    """
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager._context = GamepadManager.CONTEXT_GAME
    manager._refresh_empty_startup_scan = lambda: None
    manager._sync_steam_input_gamepads = lambda: None
    return manager


def _fake_gamepad_state(instance_id: int = 7, name: str = 'Xbox Wireless'):
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


class _CountingJoystick:
    """Girdi döngüsünün her kare registry'yi taradığını get_init çağrı
    sayısıyla kanıtlar (get_init → False: okuma gövdesi continue ile
    atlanır, ancak taramanın kendisi her kare koşmuştur)."""

    def __init__(self):
        self.get_init_calls = 0

    def get_init(self):
        self.get_init_calls += 1
        return False


def test_first_update_always_checks_connections(monkeypatch):
    manager = _make_manager()
    calls = []
    monkeypatch.setattr(manager, '_check_connections', lambda: calls.append(1))

    # Delta ne kadar küçük olursa olsun ilk karede polling koşar.
    manager.update(0.0)

    assert calls == [1]
    assert manager._last_conn_check_ms == 0.0


def test_no_recheck_within_250ms(monkeypatch):
    manager = _make_manager()
    calls = []
    monkeypatch.setattr(manager, '_check_connections', lambda: calls.append(1))

    # 15 kare × 16 ms = 240 ms — ilk çağrı hariç yeniden koşmamalı.
    for _ in range(15):
        manager.update(16.0)

    assert calls == [1]
    # Saat yalnızca polling ÇAĞRILDIĞINDA atanır: ilk karenin anı (t=16)
    # kalır — sonraki kareler çağrı yapılmadıkça güncellemez.
    assert manager._last_conn_check_ms == 16.0


def test_recheck_at_interval_boundary(monkeypatch):
    manager = _make_manager()
    calls = []
    monkeypatch.setattr(manager, '_check_connections', lambda: calls.append(1))

    manager.update(250.0)   # t=250: ilk çağrı
    manager.update(249.0)   # t=499: 249 ms geçti — çağrılmaz
    assert calls == [1]

    manager.update(1.0)     # t=500: 250 ms doldu — tekrar çağrılır
    assert calls == [1, 1]
    assert manager._last_conn_check_ms == 500.0


def test_input_loop_scans_registry_every_frame(monkeypatch):
    manager = _make_manager()
    calls = []
    monkeypatch.setattr(manager, '_check_connections', lambda: calls.append(1))

    joy = _CountingJoystick()
    manager.gamepads[0] = GamepadState(
        joystick=joy,
        controller=None,
        gamepad_type='xbox',
        name='Pad',
        guid='',
        instance_id=1,
    )

    for _ in range(5):
        manager.update(16.0)

    # Girdi yolu her kare en az bir kez registry'yi tarar (ana okuma
    # döngüsü + aktif girdi taraması; get_init başına 2 çağrı), polling
    # yalnız ilk karede koşar. >= kullanımı: get_init çağrı sayısı
    # gelecekteki meşru ek taramalarla artabilir, hiçbir zaman kare
    # başına 1'in altına inmemelidir.
    assert joy.get_init_calls >= 5
    assert calls == [1]


def test_hotplug_event_path_not_throttled(monkeypatch):
    manager = _make_manager()
    # Polling saati "şimdi"ye kilitli: polling yolunun bir sonraki
    # denetimi 250 ms beklemeliydi. Event yolu bu kilide rağmen anında
    # kayıt yapabilmelidir.
    manager._internal_time = 0.0
    manager._last_conn_check_ms = 0.0

    register_calls = []

    def fake_register(device_index):
        register_calls.append(device_index)
        manager.gamepads[device_index] = _fake_gamepad_state()
        return True

    monkeypatch.setattr(manager, '_register_gamepad', fake_register)

    event = types.SimpleNamespace(
        type=gpm_module.pygame.JOYDEVICEADDED,
        device_index=3,
    )
    result = manager.handle_hotplug_event(event)

    assert result == 'connected'
    assert register_calls == [3]


def test_bare_instance_update_is_attribute_error_free(monkeypatch):
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager._context = GamepadManager.CONTEXT_GAME
    manager._refresh_empty_startup_scan = lambda: None
    manager._sync_steam_input_gamepads = lambda: None
    monkeypatch.setattr(manager, '_check_connections', lambda: None)

    # hasattr ilkleme idyomu: __new__ bypass'lı yöneticide exception yok.
    manager.update(16.0)

    assert manager._internal_time == 16.0
    assert manager._last_conn_check_ms == 16.0


def test_poll_interval_respects_platform_upper_bound():
    """Deck/macOS 'geç güncellenen get_count' uyarısı: aralık 500 ms üst
    sınırını aşmamalı (rapor OP-049 / plan D8 madde 5)."""
    assert 0.0 < GamepadManager.CONNECTION_POLL_INTERVAL_MS <= 500.0
