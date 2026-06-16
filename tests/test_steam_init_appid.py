"""Tests for steam_integration init() AppID override gating."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call


def _make_mock_dll():
    """Create a minimal DLL mock that simulates successful SteamAPI_InitFlat."""
    dll = MagicMock()
    dll._quadrix_has_init_flat = True
    dll._quadrix_has_init_legacy = False
    errmsg_buf = MagicMock()
    errmsg_buf.value = b""
    # SteamAPI_InitFlat returns 0 (OK)
    dll.SteamAPI_InitFlat.return_value = 0
    # Interface accessors return non-null
    dll.SteamAPI_SteamFriends_v018.return_value = 0x1000
    dll.SteamAPI_SteamUser_v023.return_value = 0x2000
    dll.SteamAPI_SteamUserStats_v013.return_value = 0x3000
    dll.SteamAPI_SteamUtils_v010.return_value = 0x4000
    dll.SteamAPI_SteamApps_v008.return_value = 0x5000
    dll.SteamAPI_ISteamUserStats_RequestCurrentStats.return_value = True
    dll.SteamAPI_RunCallbacks.return_value = None
    return dll


class TestInitAppIdGating(unittest.TestCase):

    def setUp(self):
        """Remove any cached steam_integration module and reset env."""
        import importlib
        # Remove cached module so we get a fresh state each test
        for mod_name in list(sys.modules.keys()):
            if 'steam_integration' in mod_name:
                del sys.modules[mod_name]
        # Remove env vars that might leak between tests
        for key in ('SteamAppId', 'SteamGameId', 'STEAM_DEV_OVERRIDE', 'STEAM_APP_ID'):
            os.environ.pop(key, None)

    def tearDown(self):
        for mod_name in list(sys.modules.keys()):
            if 'steam_integration' in mod_name:
                del sys.modules[mod_name]
        for key in ('SteamAppId', 'SteamGameId', 'STEAM_DEV_OVERRIDE', 'STEAM_APP_ID'):
            os.environ.pop(key, None)
        # Remove sys.frozen if we set it
        if hasattr(sys, 'frozen'):
            try:
                del sys.frozen
            except AttributeError:
                pass

    def _run_init(self, mock_dll_obj):
        """Import steam_integration and call init() with a mocked DLL."""
        import ctypes
        import sys as _sys
        import importlib

        with patch('ctypes.CDLL', return_value=mock_dll_obj), \
             patch('threading.Thread') as mock_thread, \
             patch('time.sleep', return_value=None):
            mock_thread.return_value = MagicMock()
            # Patch _find_dll to return a fake path so loading is attempted
            import steam_integration as si
            # Patch internals after import
            si._dll_loaded = False
            si._init_ok = False
            with patch.object(si, '_find_dll', return_value='/fake/steam_api64.dll'), \
                 patch.object(si, '_setup_dll_functions', return_value=None), \
                 patch('builtins.print', side_effect=lambda *a, **k: None):
                result = si.init()
        return si

    def test_dev_mode_sets_env(self):
        """In dev mode (not frozen), SteamAppId env should be set by init()."""
        # Ensure not frozen
        if hasattr(sys, 'frozen'):
            del sys.frozen
        os.environ.pop('SteamAppId', None)
        os.environ.pop('STEAM_DEV_OVERRIDE', None)

        mock_dll = _make_mock_dll()
        si = self._run_init(mock_dll)

        self.assertEqual(
            os.environ.get('SteamAppId'),
            '4635310',
            "Dev mode: SteamAppId should be set to '4635310'"
        )

    def test_frozen_mode_skips_env(self):
        """In frozen mode (sys.frozen=True, no override), SteamAppId must NOT be set."""
        os.environ.pop('SteamAppId', None)
        os.environ.pop('STEAM_DEV_OVERRIDE', None)

        with patch.object(sys, 'frozen', True, create=True):
            mock_dll = _make_mock_dll()
            si = self._run_init(mock_dll)

        self.assertNotIn(
            'SteamAppId',
            os.environ,
            "Frozen/production mode: SteamAppId must NOT be injected into env"
        )

    def test_dev_override_env_forces_dev_mode(self):
        """STEAM_DEV_OVERRIDE=1 triggers env set even when frozen."""
        os.environ['STEAM_DEV_OVERRIDE'] = '1'
        os.environ.pop('SteamAppId', None)

        with patch.object(sys, 'frozen', True, create=True):
            mock_dll = _make_mock_dll()
            si = self._run_init(mock_dll)

        self.assertEqual(
            os.environ.get('SteamAppId'),
            '4635310',
            "STEAM_DEV_OVERRIDE=1 should force dev mode even when frozen"
        )


if __name__ == '__main__':
    unittest.main()
