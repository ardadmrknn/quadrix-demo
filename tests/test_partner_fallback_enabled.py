# -*- coding: utf-8 -*-
"""Birim testleri: _submit_score_via_partner_api() HTTP mock ile akış doğrulaması.

Gerçek HTTP isteği atmaz; urllib.request.urlopen mock'lanır.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch


def _reset_module():
    for key in list(sys.modules.keys()):
        if 'steam_integration' in key:
            del sys.modules[key]


def _make_mock_response(result_code: int, global_rank_new: int = 1) -> MagicMock:
    body = json.dumps({
        "result": {
            "result": result_code,
            "global_rank_new": global_rank_new,
            "score_changed": True,
        }
    }).encode('utf-8')
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestSubmitScoreViaPartnerApiSuccess(unittest.TestCase):
    """result=1 (k_EResultOK) → True döndürmeli."""

    def setUp(self):
        _reset_module()
        os.environ['STEAM_PARTNER_WRITE_FALLBACK'] = '1'

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        _reset_module()

    def test_returns_true_on_result_ok(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        with patch('urllib.request.urlopen', return_value=_make_mock_response(1, 42)):
            result = m._submit_score_via_partner_api('quadrix_mystery', 55000, '76561199351154071')

        self.assertTrue(result)

    def test_correct_leaderboard_id_used(self):
        """quadrix_mystery için LB ID 19198572 kullanılmalı."""
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        captured_data = []

        def capture_urlopen(req, timeout=None):
            captured_data.append(req.data.decode('ascii'))
            return _make_mock_response(1)

        with patch('urllib.request.urlopen', side_effect=capture_urlopen):
            m._submit_score_via_partner_api('quadrix_mystery', 55000, '76561199351154071')

        self.assertTrue(captured_data)
        self.assertIn('leaderboardid=19198572', captured_data[0])


class TestSubmitScoreViaPartnerApiNoLicense(unittest.TestCase):
    """result=8 (k_EResultInvalidParam / lisans yok) → False döndürmeli."""

    def test_returns_false_on_result_8(self):
        _reset_module()
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        with patch('urllib.request.urlopen', return_value=_make_mock_response(8)):
            result = m._submit_score_via_partner_api('quadrix_mystery', 55000, '76561199351154071')

        self.assertFalse(result)


class TestSubmitScoreViaPartnerApiNetworkError(unittest.TestCase):
    """Network hatasında False döndürmeli, exception fırlatmamalı."""

    def test_returns_false_on_network_error(self):
        _reset_module()
        import urllib.error
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("timeout")):
            result = m._submit_score_via_partner_api('quadrix_mystery', 55000, '76561199351154071')

        self.assertFalse(result)


class TestSubmitScoreViaPartnerApiUnknownLeaderboard(unittest.TestCase):
    """Bilinmeyen leaderboard adında False döndürmeli."""

    def test_returns_false_for_unknown_lb(self):
        _reset_module()
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        result = m._submit_score_via_partner_api('quadrix_does_not_exist', 100, '76561199351154071')
        self.assertFalse(result)


class TestSubmitScoreViaPartnerApiScoremethodIsString(unittest.TestCase):
    """scoremethod parametresi Steam Web API'ye string olarak gönderilmeli (ör. 'KeepBest')."""

    def setUp(self):
        _reset_module()
        os.environ['STEAM_PARTNER_WRITE_FALLBACK'] = '1'

    def tearDown(self):
        os.environ.pop('STEAM_PARTNER_WRITE_FALLBACK', None)
        _reset_module()

    def test_partner_api_scoremethod_is_string(self):
        """POST payload'ında scoremethod=KeepBest (string) olmalı, integer olmamalı."""
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m

        captured_data = []

        def capture_urlopen(req, timeout=None):
            captured_data.append(req.data.decode('ascii'))
            return _make_mock_response(1)

        with patch('urllib.request.urlopen', side_effect=capture_urlopen):
            m._submit_score_via_partner_api('quadrix_mystery', 55000, '76561199351154071')

        self.assertTrue(captured_data, "urlopen hiç çağrılmadı")
        payload = captured_data[0]
        # scoremethod=KeepBest (string) içermeli
        self.assertIn('scoremethod=KeepBest', payload,
                      f"scoremethod string 'KeepBest' bekleniyor, payload: {payload}")
        # Kesinlikle integer değer (0 veya 1) içermemeli
        self.assertNotIn('scoremethod=0', payload,
                         f"scoremethod integer 0 olmamalı, payload: {payload}")
        self.assertNotIn('scoremethod=1', payload,
                         f"scoremethod integer 1 olmamalı, payload: {payload}")


if __name__ == '__main__':
    unittest.main()
