"""Tests for the blocking-popup gamepad pump helper.

Bloklayıcı popup/modal döngüleri (mode intro, zen başlangıç, renk seçici,
metin girişi) ana oyun döngüsünün her-frame `GamepadManager.update()` pump'ını
atlar. `pump_gamepad_into_event_queue` bu döngülerin başında çağrılarak
gamepad'i canlı tutar: bağlamı ayarlar, durumu okur ve üretilen sentetik
olayları pygame kuyruğuna post eder.

Bu testler `update()`/`set_context`'i stub'layıp helper'ın:
  1. bağlamı doğru ayarladığını,
  2. üretilen olayları kuyruğa post ettiğini,
  3. singleton yokken/ hata durumunda güvenli (0) döndüğünü
doğrular.
"""

from __future__ import annotations

import os as _os
import sys
import types

import pytest

_SRC_DIR_STR = _os.path.join(_os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import gamepad_manager as gpm_module  # noqa: E402

_canonical = sys.modules.get('gamepad_manager')
if _canonical is not None and _canonical is not gpm_module:
    gpm_module = _canonical

pygame = gpm_module.pygame


class _FakeManager:
    """update()/set_context'i izleyen minimal sahte yönetici."""

    def __init__(self, events):
        self._events = list(events)
        self.context_calls = []
        self.update_calls = []

    def set_context(self, context):
        self.context_calls.append(context)

    def update(self, delta_ms):
        self.update_calls.append(delta_ms)
        return list(self._events)


def _key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0)


@pytest.fixture(autouse=True)
def _restore_singleton():
    original = gpm_module._instance
    yield
    gpm_module._instance = original
    try:
        pygame.event.clear()
    except Exception:
        pass


def test_pump_sets_context_and_posts_events(monkeypatch):
    events = [_key_event(pygame.K_RETURN), _key_event(pygame.K_ESCAPE)]
    fake = _FakeManager(events)
    monkeypatch.setattr(gpm_module, '_instance', fake)
    monkeypatch.setattr(gpm_module, 'get_gamepad_manager', lambda: fake)

    posted = []
    monkeypatch.setattr(pygame.event, 'post', lambda ev: posted.append(ev) or True)

    count = gpm_module.pump_gamepad_into_event_queue(20.0, 'menu')

    assert count == 2
    assert fake.context_calls == ['menu']
    assert fake.update_calls == [20.0]
    assert [getattr(e, 'key', None) for e in posted] == [pygame.K_RETURN, pygame.K_ESCAPE]


def test_pump_without_context_does_not_set_context(monkeypatch):
    fake = _FakeManager([])
    monkeypatch.setattr(gpm_module, '_instance', fake)
    monkeypatch.setattr(gpm_module, 'get_gamepad_manager', lambda: fake)
    monkeypatch.setattr(pygame.event, 'post', lambda ev: True)

    gpm_module.pump_gamepad_into_event_queue(16.0, None)

    assert fake.context_calls == []
    assert fake.update_calls == [16.0]


def test_pump_returns_zero_when_no_singleton(monkeypatch):
    monkeypatch.setattr(gpm_module, '_instance', None)
    monkeypatch.setattr(gpm_module, 'get_gamepad_manager', lambda: None)

    assert gpm_module.pump_gamepad_into_event_queue(16.0, 'menu') == 0


def test_pump_is_safe_when_update_raises(monkeypatch):
    class _Boom(_FakeManager):
        def update(self, delta_ms):
            raise RuntimeError('boom')

    fake = _Boom([])
    monkeypatch.setattr(gpm_module, '_instance', fake)
    monkeypatch.setattr(gpm_module, 'get_gamepad_manager', lambda: fake)

    # Hata yutulmalı, 0 dönmeli.
    assert gpm_module.pump_gamepad_into_event_queue(16.0, 'menu') == 0
