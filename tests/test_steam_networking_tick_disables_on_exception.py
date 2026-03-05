"""Phase 4: SteamNetworking.tick() sürekli exception fırlatırsa networking'i devre dışı bır.

tick() içinde ardışık N exception sayacı var; N'ye ulaşınca:
  - self._initialized = False yapılmalı
  - event kuyruğuna {"type": "error", "message": "networking_disabled"} push edilmeli
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock

# --- sys.path ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

import steam_networking as _sn
from steam_networking import SteamNetworking, NetEvent


def _make_net_with_failing_callbacks(fail_limit: int = 999) -> SteamNetworking:
    """Her run_callbacks() çağrısında RuntimeError fırlatan bridge ile SteamNetworking döndürür."""
    net = SteamNetworking()
    mock_bridge = MagicMock()
    mock_bridge.run_callbacks.side_effect = RuntimeError("simulated bridge crash")
    # poll_events / poll_messages boş dönsün
    mock_bridge.poll_events.return_value = []
    mock_bridge.poll_messages.return_value = []
    net._bridge_instance = mock_bridge
    net._initialized = True
    return net


class TestTickDisablesAfterRepeatedExceptions(unittest.TestCase):
    """run_callbacks N kez exception fırlattığında _initialized False olmalı."""

    def test_tick_disables_after_repeated_exceptions(self):
        net = _make_net_with_failing_callbacks()
        self.assertTrue(net._initialized, "Başlangıçta initialized True olmalı")

        # 5 kez tick() çağır — her birinde run_callbacks exception fırlatır
        for _ in range(5):
            net.tick()

        self.assertFalse(
            net._initialized,
            "_initialized hâlâ True — 5 ardışık exception sonrası False olmalıydı"
        )

    def test_tick_does_not_disable_before_threshold(self):
        """Eşik sayısının altında (örn. 4) exception → hâlâ initialized olmalı."""
        net = _make_net_with_failing_callbacks()

        # 4 kez çağır (eşik 5 kabul ediyoruz)
        for _ in range(4):
            net.tick()

        self.assertTrue(
            net._initialized,
            "4 exception sonrası henüz disable olmamalıydı (eşik 5)"
        )

    def test_tick_counter_resets_on_success(self):
        """Başarılı bir tick() sayacı sıfırlamalı."""
        net = SteamNetworking()
        mock_bridge = MagicMock()
        call_count = {'n': 0}

        def run_cb():
            call_count['n'] += 1
            if call_count['n'] <= 3:
                raise RuntimeError("crash")
            # 4. çağrıda başarılı

        mock_bridge.run_callbacks.side_effect = run_cb
        mock_bridge.poll_events.return_value = []
        mock_bridge.poll_messages.return_value = []
        net._bridge_instance = mock_bridge
        net._initialized = True

        for _ in range(4):  # 3 hata, 1 başarı
            net.tick()

        self.assertTrue(net._initialized,
                        "Başarılı tick() sonrası initialized False olmamalı")

        # Şimdi sayaç sıfırlandıysa, 5 hata daha ile disable olmalı
        mock_bridge.run_callbacks.side_effect = RuntimeError("crash again")
        for _ in range(5):
            net.tick()

        self.assertFalse(net._initialized,
                         "Sayaç sıfırlandıktan sonra 5 hata daha disable etmeli")


class TestTickPushesErrorEventOnDisable(unittest.TestCase):
    """Disable sonrası event kuyruğunda type='error' với message='networking_disabled' olmalı."""

    def test_tick_pushes_error_event_on_disable(self):
        net = _make_net_with_failing_callbacks()

        for _ in range(5):
            net.tick()

        events = net.get_events()
        error_events = [e for e in events if e.type == 'error']
        self.assertTrue(len(error_events) > 0,
                        f"Disable sonrası event kuyruğunda 'error' eventi yok. events={events}")

        # En az birinde networking_disabled mesajı olmalı
        disabled_events = [e for e in error_events if 'networking_disabled' in (e.data or '')]
        self.assertTrue(
            len(disabled_events) > 0,
            f"'networking_disabled' içeren event bulunamadı. error_events={error_events}"
        )

    def test_no_error_event_when_not_disabled(self):
        """Eşik aşılmadıysa error event olmamalı."""
        net = _make_net_with_failing_callbacks()

        for _ in range(3):
            net.tick()

        events = net.get_events()
        error_events = [e for e in events if e.type == 'error'
                        and 'networking_disabled' in (e.data or '')]
        self.assertEqual(len(error_events), 0,
                         "Eşik aşılmadan networking_disabled eventi olmamalı")


if __name__ == '__main__':
    unittest.main()
