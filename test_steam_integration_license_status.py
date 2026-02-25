# -*- coding: utf-8 -*-
"""Birim testleri: is_app_owned() ve SteamApps lisans kontrol akışı.

Gerçek Steam DLL'i gerektirmez; ctypes çağrıları mock'lanır.
"""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _fresh_module():
    """steam_integration modülünü temizleyip yeniden içe aktar."""
    # Önce varsa cache'den sil
    for key in list(sys.modules.keys()):
        if 'steam_integration' in key:
            del sys.modules[key]
    # DLL yükleme tarafını bypass et
    with patch('ctypes.CDLL', return_value=MagicMock()):
        import src.steam_integration as m
    return m


class TestIsAppOwnedSteamUnavailable(unittest.TestCase):
    """Steam SDK kapalıyken is_app_owned() None döndürmeli."""

    def test_returns_none_when_not_available(self):
        mod = _fresh_module()
        # _init_ok = False simüle et
        mod._init_ok = False
        mod._dll = None
        mod._isteam_apps = None
        result = mod.is_app_owned()
        self.assertIsNone(result)

    def test_returns_none_when_dll_none(self):
        mod = _fresh_module()
        mod._init_ok = True
        mod._dll = None
        mod._isteam_apps = MagicMock()
        result = mod.is_app_owned()
        self.assertIsNone(result)

    def test_returns_none_when_apps_interface_none(self):
        mod = _fresh_module()
        mod._init_ok = True
        mod._dll = MagicMock()
        mod._isteam_apps = None
        result = mod.is_app_owned()
        self.assertIsNone(result)


class TestIsAppOwnedLicensed(unittest.TestCase):
    """Lisanslı hesapta is_app_owned() True döndürmeli."""

    def test_returns_true_when_subscribed(self):
        mod = _fresh_module()
        dll_mock = MagicMock()
        dll_mock.SteamAPI_ISteamApps_BIsSubscribed.return_value = True
        mod._init_ok = True
        mod._dll = dll_mock
        mod._isteam_apps = object()  # non-None pointer simülasyonu
        result = mod.is_app_owned()
        self.assertTrue(result)


class TestIsAppOwnedUnlicensed(unittest.TestCase):
    """Lisanssız hesapta (result=8 senaryosu) is_app_owned() False döndürmeli."""

    def test_returns_false_when_not_subscribed(self):
        mod = _fresh_module()
        dll_mock = MagicMock()
        dll_mock.SteamAPI_ISteamApps_BIsSubscribed.return_value = False
        mod._init_ok = True
        mod._dll = dll_mock
        mod._isteam_apps = object()
        result = mod.is_app_owned()
        self.assertFalse(result)


class TestIsAppOwnedExceptionHandling(unittest.TestCase):
    """DLL exception fırlattığında is_app_owned() None döndürmeli, crash yok."""

    def test_returns_none_on_exception(self):
        mod = _fresh_module()
        dll_mock = MagicMock()
        dll_mock.SteamAPI_ISteamApps_BIsSubscribed.side_effect = OSError("dll crash")
        mod._init_ok = True
        mod._dll = dll_mock
        mod._isteam_apps = object()
        result = mod.is_app_owned()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
