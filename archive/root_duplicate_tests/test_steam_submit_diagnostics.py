# -*- coding: utf-8 -*-
"""Birim testleri: submit_score() başarısızlık teşhis mesajları.

SDK success=0 döndüğünde + fallback kapalıyken beklenen log mesajları doğrulanır.
Gerçek Steam DLL'i gerektirmez.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch


def _reset_module():
    for key in list(sys.modules.keys()):
        if 'steam_integration' in key:
            del sys.modules[key]


class TestSubmitScoreDiagnostics(unittest.TestCase):

    def setUp(self):
        _reset_module()
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        _reset_module()

    def _import_module(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        return m

    def test_no_license_message_logged(self):
        """SDK başarısız + fallback kapalı ise uygun uyarı mesajı loglanmalı."""
        m = self._import_module()

        # SDK ortamını hazırla
        fake_result = MagicMock()
        fake_result.m_bSuccess = 0
        m._init_ok = True
        m._dll = MagicMock()
        m._isteam_user_stats = object()
        m._lb_handle_cache = {'quadrix_mystery': 12345}

        logged = []

        # Partner API key temizle (fallback auto-enable olmasın)
        original_key = m._PARTNER_API_KEY_CACHED
        m._PARTNER_API_KEY_CACHED = ''

        # Tüm patch'ler test bloğu boyunca aktif kalıyor
        try:
            with patch.object(m, '_get_api_call_result', return_value=fake_result), \
                 patch.object(m, 'get_steam_id_str', return_value='76561199351154071'), \
                 patch.object(m, 'is_app_owned', return_value=False), \
                 patch('builtins.print', side_effect=lambda *a, **kw: logged.append(' '.join(str(x) for x in a))):
                m.submit_score('mystery', 50000)
                time.sleep(0.4)  # worker thread'in bitmesini bekle
        finally:
            m._PARTNER_API_KEY_CACHED = original_key

        sdk_fail_warn = any('basarisiz' in msg or 'STEAM_WEB_API_KEY' in msg for msg in logged)
        self.assertTrue(sdk_fail_warn, f"SDK başarısız uyarı mesajı bulunamadı. Loglar: {logged}")

    def test_fallback_disabled_message_when_sdk_fails_but_might_be_owned(self):
        """Fallback kapalı + is_app_owned=None ise 'STEAM_WEB_API_KEY' mesajı loglanmalı."""
        m = self._import_module()

        fake_result = MagicMock()
        fake_result.m_bSuccess = 0
        m._init_ok = True
        m._dll = MagicMock()
        m._isteam_user_stats = object()
        m._isteam_apps = None  # apps ptr yok → is_app_owned None döner
        m._lb_handle_cache = {'quadrix_mystery': 12345}

        # Partner API key temizle (fallback auto-enable olmasın)
        original_key = m._PARTNER_API_KEY_CACHED
        m._PARTNER_API_KEY_CACHED = ''

        logged = []

        try:
            with patch.object(m, '_get_api_call_result', return_value=fake_result), \
                 patch.object(m, 'get_steam_id_str', return_value='76561199351154071'), \
                 patch.object(m, 'is_app_owned', return_value=None), \
                 patch('builtins.print', side_effect=lambda *a, **kw: logged.append(' '.join(str(x) for x in a))):
                m.submit_score('mystery', 50000)
                time.sleep(0.4)
        finally:
            m._PARTNER_API_KEY_CACHED = original_key

        fallback_warn = any('STEAM_WEB_API_KEY' in msg or 'basarisiz' in msg for msg in logged)
        self.assertTrue(fallback_warn, f"Fallback uyarı mesajı bulunamadı. Loglar: {logged}")

    def test_unrecognized_mode_returns_false(self):
        """Tanınmayan modda submit_score False döndürmeli."""
        m = self._import_module()
        m._init_ok = True
        result = m.submit_score('nonexistent_mode', 100)
        self.assertFalse(result)

