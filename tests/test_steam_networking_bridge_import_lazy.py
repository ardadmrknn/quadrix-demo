"""Tests: steam_net_bridge import'u YALNIZCA SteamNetworking.init() çağrıldığında
tetiklenmeli; modül import edildiğinde otomatik tetiklenmemeli (lazy loading)."""
from __future__ import annotations

import sys
import importlib
import types
import unittest


def _unload_steam_networking():
    """steam_networking ve steam_net_bridge modüllerini cache'den temizle."""
    to_remove = [k for k in sys.modules if 'steam_networking' in k or k == 'steam_net_bridge']
    for k in to_remove:
        del sys.modules[k]


class TestBridgeImportIsLazy(unittest.TestCase):
    """Bridge import'u lazy olduğunu doğrular."""

    def setUp(self):
        _unload_steam_networking()

    def tearDown(self):
        _unload_steam_networking()

    def test_import_module_does_not_call_bridge(self):
        """src.steam_networking import edildiğinde steam_net_bridge import edilmemeli."""
        call_log: list[str] = []

        sentinel = types.ModuleType('steam_net_bridge')
        sentinel._loaded_by_lazy = True

        import builtins
        original_import = builtins.__import__

        def tracking_import(name, *args, **kwargs):
            if name == 'steam_net_bridge':
                call_log.append('bridge_imported')
                return sentinel
            return original_import(name, *args, **kwargs)

        builtins.__import__ = tracking_import
        try:
            import src.steam_networking  # noqa: F401
        finally:
            builtins.__import__ = original_import

        self.assertEqual(
            call_log, [],
            "steam_net_bridge modülü import zamanında yüklenmemeli (lazy olmalı); "
            f"ancak şu çağrılar tespit edildi: {call_log}"
        )

    def test_init_triggers_bridge_import(self):
        """SteamNetworking.init() çağrıldığında bridge import denemesi yapılmalı."""
        call_log: list[str] = []

        sentinel = types.ModuleType('steam_net_bridge')

        class FakeBridge:
            def init(self): return False
            def get_my_steam_id(self): return 0

        sentinel.SteamNetBridge = FakeBridge

        import builtins
        original = builtins.__import__

        def tracking_import(name, *args, **kwargs):
            if name == 'steam_net_bridge':
                call_log.append('bridge_imported')
                sys.modules['steam_net_bridge'] = sentinel
                return sentinel
            return original(name, *args, **kwargs)

        _unload_steam_networking()
        builtins.__import__ = tracking_import
        try:
            import src.steam_networking as sn
            importlib.reload(sn)
            net = sn.SteamNetworking()
            net.init()
        finally:
            builtins.__import__ = original

        self.assertIn(
            'bridge_imported', call_log,
            "SteamNetworking.init() çağrıldığında steam_net_bridge import edilmeli."
        )

    def test_bridge_not_available_before_init(self):
        """Modül import edildikten hemen sonra bridge yüklenmemiş olmalı."""
        _unload_steam_networking()

        import builtins
        original = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == 'steam_net_bridge':
                raise ImportError("test: bridge blocked")
            return original(name, *args, **kwargs)

        builtins.__import__ = blocking_import
        try:
            import src.steam_networking as sn
            # bridge_import_attempted flag'ı False olmalı (henüz init çağrılmadı)
            self.assertFalse(
                sn._bridge_import_attempted,
                "_bridge_import_attempted, init() çağrılmadan True olmamalı."
            )
        finally:
            builtins.__import__ = original


if __name__ == '__main__':
    unittest.main()
