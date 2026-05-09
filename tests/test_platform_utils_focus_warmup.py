import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import platform_utils as platform_utils_module


def test_startup_focus_warmup_retries_until_display_becomes_active(monkeypatch):
    times = iter((1000, 1080, 1125, 1210))
    active = {'value': False}
    focus_calls: list[str] = []

    monkeypatch.setattr(platform_utils_module, 'IS_MACOS', True)
    monkeypatch.setattr(platform_utils_module.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(platform_utils_module.pygame.time, 'get_ticks', lambda: next(times))
    monkeypatch.setattr(platform_utils_module.pygame.display, 'get_active', lambda: active['value'])
    monkeypatch.setattr(platform_utils_module, 'request_window_focus', lambda: focus_calls.append('focus'))

    platform_utils_module._STARTUP_FOCUS_WARMUP_STATE = None
    assert platform_utils_module.arm_startup_focus_warmup(duration_ms=400, retry_interval_ms=100) is True
    assert focus_calls == ['focus']

    assert platform_utils_module.pump_startup_focus_warmup() is False
    assert focus_calls == ['focus']

    assert platform_utils_module.pump_startup_focus_warmup() is True
    assert focus_calls == ['focus', 'focus']

    active['value'] = True
    assert platform_utils_module.pump_startup_focus_warmup() is False
    assert platform_utils_module._STARTUP_FOCUS_WARMUP_STATE is None


def test_startup_focus_warmup_expires_when_window_stays_inactive(monkeypatch):
    times = iter((2000, 2140, 2525))
    focus_calls: list[str] = []

    monkeypatch.setattr(platform_utils_module, 'IS_MACOS', True)
    monkeypatch.setattr(platform_utils_module.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(platform_utils_module.pygame.time, 'get_ticks', lambda: next(times))
    monkeypatch.setattr(platform_utils_module.pygame.display, 'get_active', lambda: False)
    monkeypatch.setattr(platform_utils_module, 'request_window_focus', lambda: focus_calls.append('focus'))

    platform_utils_module._STARTUP_FOCUS_WARMUP_STATE = None
    assert platform_utils_module.arm_startup_focus_warmup(duration_ms=500, retry_interval_ms=100) is True
    assert focus_calls == ['focus']

    assert platform_utils_module.pump_startup_focus_warmup() is True
    assert focus_calls == ['focus', 'focus']

    assert platform_utils_module.pump_startup_focus_warmup() is False
    assert platform_utils_module._STARTUP_FOCUS_WARMUP_STATE is None


def test_startup_focus_warmup_is_disabled_for_non_frozen_runs(monkeypatch):
    focus_calls: list[str] = []

    monkeypatch.setattr(platform_utils_module, 'IS_MACOS', True)
    monkeypatch.setattr(platform_utils_module.sys, 'frozen', False, raising=False)
    monkeypatch.setattr(platform_utils_module, 'request_window_focus', lambda: focus_calls.append('focus'))

    platform_utils_module._STARTUP_FOCUS_WARMUP_STATE = {'stale': True}
    assert platform_utils_module.arm_startup_focus_warmup() is False
    assert focus_calls == []
    assert platform_utils_module._STARTUP_FOCUS_WARMUP_STATE is None
