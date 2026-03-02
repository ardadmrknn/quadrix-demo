# -*- coding: utf-8 -*-
"""Birim testleri: Partner API fallback feature flag (STEAM_PARTNER_WRITE_FALLBACK).

Flag kapalıyken _submit_score_via_partner_api çağrılmamalı.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call


def _reset_module():
    for key in list(sys.modules.keys()):
        if 'steam_integration' in key:
            del sys.modules[key]


class TestPartnerFallbackFlagOff(unittest.TestCase):
    """STEAM_PARTNER_WRITE_FALLBACK=0 (default) → fallback çağrılmamalı."""

    def setUp(self):
        _reset_module()
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ.pop('STEAM_WEB_API_KEY', None)

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ.pop('STEAM_WEB_API_KEY', None)

    def test_partner_api_not_called_when_flag_off(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        m._init_ok = True
        m._dll = MagicMock()
        m._isteam_user_stats = object()
        m._lb_handle_cache = {'quadrix_mystery': 12345}

        fake_result = MagicMock()
        fake_result.m_bSuccess = 0

        # Partner API key de temiz olmalı (auto-enable olmasın)
        original_key = m._PARTNER_API_KEY_CACHED
        m._PARTNER_API_KEY_CACHED = ''

        try:
            with patch.object(m, '_get_api_call_result', return_value=fake_result), \
                 patch.object(m, 'get_steam_id_str', return_value='76561199351154071'), \
                 patch.object(m, 'is_app_owned', return_value=True), \
                 patch.object(m, '_submit_score_via_partner_api') as mock_partner:
                m.submit_score('mystery', 99999)
                import time; time.sleep(0.3)
        finally:
            m._PARTNER_API_KEY_CACHED = original_key
        mock_partner.assert_not_called()

    def test_is_partner_fallback_enabled_default_false(self):
        _reset_module()
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ.pop('STEAM_WEB_API_KEY', None)
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        self.assertFalse(m._is_partner_fallback_enabled())

    def test_is_partner_fallback_enabled_zero_false(self):
        _reset_module()
        os.environ['STEAM_PARTNER_WRITE_FALLBACK'] = '0'
        os.environ.pop('STEAM_WEB_API_KEY', None)
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        self.assertFalse(m._is_partner_fallback_enabled())

    def test_is_partner_fallback_enabled_false_string(self):
        _reset_module()
        os.environ['STEAM_PARTNER_WRITE_FALLBACK'] = 'false'
        os.environ.pop('STEAM_WEB_API_KEY', None)
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        self.assertFalse(m._is_partner_fallback_enabled())


class TestPartnerFallbackFlagOn(unittest.TestCase):
    """STEAM_PARTNER_WRITE_FALLBACK=1 → fallback çağrılmalı."""

    def setUp(self):
        _reset_module()
        os.environ['STEAM_PARTNER_WRITE_FALLBACK'] = '1'

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ.pop('STEAM_WEB_API_KEY', None)
        _reset_module()

    def test_is_partner_fallback_enabled_true(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        self.assertTrue(m._is_partner_fallback_enabled())

    def test_partner_api_called_when_flag_on_and_sdk_fails(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        m._init_ok = True
        m._dll = MagicMock()
        m._isteam_user_stats = object()
        m._lb_handle_cache = {'quadrix_mystery': 12345}

        fake_result = MagicMock()
        fake_result.m_bSuccess = 0

        mock_partner = MagicMock(return_value=True)

        with patch.object(m, '_get_api_call_result', return_value=fake_result), \
             patch.object(m, 'get_steam_id_str', return_value='76561199351154071'), \
             patch.object(m, '_submit_score_via_partner_api', mock_partner):
            m.submit_score('mystery', 99999)
            import time; time.sleep(0.4)

        mock_partner.assert_called_once_with('quadrix_mystery', 99999, '76561199351154071')


class TestPartnerFallbackAutoEnableWithApiKey(unittest.TestCase):
    """STEAM_WEB_API_KEY set edildiğinde fallback otomatik aktif olmalı."""

    def setUp(self):
        _reset_module()
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ['STEAM_WEB_API_KEY'] = 'TESTKEY123'

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        os.environ.pop('STEAM_WEB_API_KEY', None)
        _reset_module()

    def test_is_partner_fallback_enabled_true_when_api_key_set(self):
        """STEAM_WEB_API_KEY varsa _is_partner_fallback_enabled() True döndürmeli."""
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        self.assertTrue(m._is_partner_fallback_enabled())

    def test_partner_api_called_when_api_key_set_and_sdk_fails(self):
        """API key varken SDK başarısız olursa partner API çağrılmalı."""
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        m._init_ok = True
        m._dll = MagicMock()
        m._isteam_user_stats = object()
        m._lb_handle_cache = {'quadrix_mystery': 12345}

        fake_result = MagicMock()
        fake_result.m_bSuccess = 0

        mock_partner = MagicMock(return_value=True)

        with patch.object(m, '_get_api_call_result', return_value=fake_result), \
             patch.object(m, 'get_steam_id_str', return_value='76561199351154071'), \
             patch.object(m, '_submit_score_via_partner_api', mock_partner):
            m.submit_score('mystery', 88888)
            import time; time.sleep(0.4)

        mock_partner.assert_called_once_with('quadrix_mystery', 88888, '76561199351154071')


if __name__ == '__main__':
    unittest.main()
