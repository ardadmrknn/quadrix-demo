"""Tests: Windows os.add_dll_directory() handle'larının module-global listede
saklandığını ve GC sonrasında kaybolmadığını doğrular."""
from __future__ import annotations

import sys
import gc
import importlib
import unittest
from unittest.mock import MagicMock, patch


def _unload_steam_networking():
    to_remove = [k for k in sys.modules if 'steam_networking' in k or k == 'steam_net_bridge']
    for k in to_remove:
        del sys.modules[k]


class _FakeDllHandle:
    """os.add_dll_directory() tarafından döndürülen context benzeri sahte nesne."""
    def __enter__(self): return self
    def __exit__(self, *a): pass


class TestWinDllDirHandlesPersist(unittest.TestCase):
    """Windows DLL handle'larının GC'den korunduğunu doğrular."""

    def setUp(self):
        _unload_steam_networking()

    def tearDown(self):
        _unload_steam_networking()

    @unittest.skipUnless(sys.platform == 'win32', "Yalnızca Windows'ta anlamlı")
    def test_handles_stored_in_module_global(self):
        """os.add_dll_directory mock'u döndürdüğü handle'lar module-global listede olmalı."""
        handles_created: list[_FakeDllHandle] = []

        def fake_add_dll_directory(path: str) -> _FakeDllHandle:
            h = _FakeDllHandle()
            handles_created.append(h)
            return h

        with patch('os.path.isdir', return_value=True), \
             patch('os.add_dll_directory', side_effect=fake_add_dll_directory):
            import src.steam_networking as sn

            # init() üzerinden bridge yüklemesini tetikle
            net = sn.SteamNetworking()
            net.init()

        # Module-global listede en az bir handle saklanmalı
        global_handles = sn._dll_dirs
        self.assertIsInstance(global_handles, list,
                              "sn._dll_dirs bir liste olmalı.")
        self.assertGreater(len(global_handles), 0,
                           "_dll_dirs en az bir handle içermeli.")

        # GC sonrasında hâlâ erişilebilir olmalı
        gc.collect()
        self.assertGreater(len(sn._dll_dirs), 0,
                           "GC sonrasında handle'lar module-global listeden kaybolmamalı.")

    def test_dll_dirs_attribute_exists_on_module(self):
        """_dll_dirs attribute'u her platformda modül üzerinde mevcut olmalı."""
        import src.steam_networking as sn
        self.assertTrue(
            hasattr(sn, '_dll_dirs'),
            "src.steam_networking modülü '_dll_dirs' attribute'una sahip olmalı."
        )
        self.assertIsInstance(sn._dll_dirs, list,
                              "_dll_dirs bir list örneği olmalı.")

    def test_handles_not_in_local_scope_only(self):
        """_dll_dirs'in fonksiyon-local değil module-global olduğunu doğrula.
        
        Bunu dolaylı yoldan: init() sonrasında _dll_dirs listesinin modül
        attribute'u olarak erişilebilir olması ve fonksiyon kapsamından
        bağımsız yaşaması gerektiğini test ederiz.
        """
        collected: list = []

        def fake_add_dll_directory(path: str):
            h = _FakeDllHandle()
            collected.append(h)
            return h

        with patch('sys.platform', 'win32'), \
             patch('os.path.isdir', return_value=True), \
             patch('os.add_dll_directory', side_effect=fake_add_dll_directory):

            _unload_steam_networking()
            import src.steam_networking as sn

            # _try_import_bridge() çağrısını doğrudan test et
            sn._bridge = None
            sn._bridge_available = False
            sn._bridge_import_attempted = False
            sn._try_import_bridge()

        # Fonksiyon döndükten sonra handle'lar modül scope'unda yaşamalı
        self.assertIsInstance(sn._dll_dirs, list)
        # Eğer herhangi bir handle oluşturulduysa modülde saklanmış olmalı
        if collected:
            self.assertGreater(
                len(sn._dll_dirs), 0,
                "Oluşturulan handle'lar _try_import_bridge() döndükten sonra "
                "_dll_dirs listesinde bulunmalı (fonksiyon-local değil)."
            )


if __name__ == '__main__':
    unittest.main()
