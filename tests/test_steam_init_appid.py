"""Tests for steam_integration init() AppID override gating."""
import sys
import os
import tempfile
import unittest
from pathlib import Path
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

    def test_dev_mode_overwrites_foreign_steam_appid_env(self):
        """init() dev modunda YABANCI SteamAppId env değerini EZMELİ.

        setdefault mevcut anahtarın değerini değiştirmez: sürece sızmış
        yabancı SteamAppId (ör. Playtest 4428040) yerinde kalır ve DLL
        bunu görür — çözümleyicinin 'yok sayılıyor' reddi dev modunda
        uygulanmış olmazdı. Açık atama kimliği proje AppID'sine sabitler.
        """
        os.environ['SteamAppId'] = '4428040'  # demo'ya yabancı (Playtest)
        os.environ['SteamGameId'] = '4428040'

        mock_dll = _make_mock_dll()
        si = self._run_init(mock_dll)

        self.assertEqual(
            os.environ.get('SteamAppId'),
            '4635310',
            "Dev mode: yabancı SteamAppId ezilip '4635310' yazılmalı"
        )
        self.assertEqual(
            os.environ.get('SteamGameId'),
            '4635310',
            "Dev mode: yabancı SteamGameId ezilip '4635310' yazılmalı"
        )


_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_APPID_FILE = _REPO_ROOT / 'config' / 'runtime' / 'steam_appid.txt'


class TestAppIdResolutionContract(unittest.TestCase):
    """AppID/Cloud cakisma cozumu — Faz 2 cozumleme sozlesmesi (demo deposu).

    Beklenen kimlikler:
    - Demo kaynak/paket calistirma: 4635310 (Demo)
    - Full (4414520) ve Playtest (4428040) bu depoya YABANCI: uyariyla
      reddedilir, proje varsayilanina dusulur.
    - CWD ve sys.executable klasoru (Python kurulumu) AppID kaynagi DEGILDIR.
    """

    def setUp(self):
        for mod_name in list(sys.modules.keys()):
            if 'steam_integration' in mod_name:
                del sys.modules[mod_name]
        for key in ('SteamAppId', 'SteamGameId', 'STEAM_DEV_OVERRIDE', 'STEAM_APP_ID'):
            os.environ.pop(key, None)
        import steam_integration as si
        self.si = si

    def tearDown(self):
        for mod_name in list(sys.modules.keys()):
            if 'steam_integration' in mod_name:
                del sys.modules[mod_name]
        for key in ('SteamAppId', 'SteamGameId', 'STEAM_DEV_OVERRIDE', 'STEAM_APP_ID'):
            os.environ.pop(key, None)

    def test_project_default_app_id_is_demo(self):
        """Demo deposunun proje varsayilani Demo AppID 4635310 olmali."""
        self.assertEqual(self.si._PROJECT_DEFAULT_APP_ID, '4635310')
        self.assertIn('4635310', self.si._ALLOWED_APP_IDS)
        self.assertNotIn('4414520', self.si._ALLOWED_APP_IDS)  # Full kimliği demo'ya yabancı
        self.assertNotIn('4428040', self.si._ALLOWED_APP_IDS)  # Playtest kimliği demo'ya yabancı

    def test_runtime_appid_file_contains_demo_appid(self):
        """config/runtime/steam_appid.txt Demo kimligini (4635310) tasimali."""
        self.assertTrue(_RUNTIME_APPID_FILE.exists(),
                        'config/runtime/steam_appid.txt mevcut olmali')
        self.assertEqual(_RUNTIME_APPID_FILE.read_text(encoding='utf-8').strip(),
                         '4635310')

    def test_env_app_id_foreign_playtest_rejected(self):
        """Yabanci env AppID (Playtest 4428040) reddedilip proje degerine dusmeli."""
        os.environ['STEAM_APP_ID'] = '4428040'
        self.assertEqual(self.si._read_app_id_from_runtime_sources(), '4635310')

    def test_env_app_id_foreign_full_rejected(self):
        """Yabanci env AppID (Full 4414520) reddedilip proje degerine dusmeli."""
        os.environ['STEAM_APP_ID'] = '4414520'
        self.assertEqual(self.si._read_app_id_from_runtime_sources(), '4635310')

    def test_env_app_id_unknown_value_rejected(self):
        """Taninmayan env AppID reddedilmeli; guvenli Demo varsayilani kullanilmali."""
        os.environ['SteamAppId'] = '9999999'
        self.assertEqual(self.si._read_app_id_from_runtime_sources(), '4635310')

    def test_executable_dir_appid_file_not_read(self):
        """sys.executable klasorundeki (Python kurulumu) steam_appid.txt OKUNMAMALI."""
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp)
            (exe_dir / 'steam_appid.txt').write_text('4428040', encoding='utf-8')
            with patch.object(sys, 'executable', str(exe_dir / 'python.exe')):
                self.assertEqual(self.si._read_app_id_from_runtime_sources(), '4635310')

    def test_cwd_appid_file_not_read(self):
        """CWD'deki yabanci steam_appid.txt OKUNMAMALI."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd_dir = Path(tmp)
            (cwd_dir / 'steam_appid.txt').write_text('4414520', encoding='utf-8')
            with patch.object(Path, 'cwd', classmethod(lambda cls: cwd_dir)):
                self.assertEqual(self.si._read_app_id_from_runtime_sources(), '4635310')

    def test_candidate_paths_are_project_or_bundle_only(self):
        """Aday listesi yalnizca _MEIPASS ve proje dosyalarini icermeli."""
        candidates = self.si._collect_app_id_candidate_paths()
        self.assertTrue(candidates, 'en az bir proje adayi beklenir')
        project_root = Path(self.si.__file__).resolve().parent.parent
        meipass = getattr(sys, '_MEIPASS', None)
        for candidate in candidates:
            resolved = Path(candidate).resolve()
            in_project = project_root in resolved.parents
            in_bundle = bool(meipass) and Path(str(meipass)) in resolved.parents
            self.assertTrue(in_project or in_bundle,
                            f'aday proje/bundle disinda olmamali: {resolved}')

    def test_init_dev_mode_does_not_write_appid_file_next_to_executable(self):
        """init() kaynak modda sys.executable klasorune steam_appid.txt YAZMAMALI."""
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp)
            fake_exe = exe_dir / 'python.exe'
            fake_exe.write_text('', encoding='utf-8')
            with patch.object(sys, 'executable', str(fake_exe)):
                mock_dll = _make_mock_dll()
                with patch('ctypes.CDLL', return_value=mock_dll), \
                     patch('threading.Thread') as mock_thread, \
                     patch('time.sleep', return_value=None):
                    mock_thread.return_value = MagicMock()
                    import steam_integration as si_mod
                    si_mod._dll_loaded = False
                    si_mod._init_ok = False
                    with patch.object(si_mod, '_find_dll', return_value='/fake/steam_api64.dll'), \
                         patch.object(si_mod, '_setup_dll_functions', return_value=None), \
                         patch.object(si_mod, '_read_app_id_from_runtime_sources', return_value='4635310'), \
                         patch('builtins.print', side_effect=lambda *a, **k: None):
                        si_mod.init()
                self.assertFalse((exe_dir / 'steam_appid.txt').exists(),
                                 'Python kurulum klasorune steam_appid.txt yazilmamali')


if __name__ == '__main__':
    unittest.main()
