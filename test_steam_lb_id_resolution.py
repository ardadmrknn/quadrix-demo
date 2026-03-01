# -*- coding: utf-8 -*-
"""Tests for dynamic leaderboard ID resolution in steam_integration."""
from __future__ import annotations

import json
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, call, patch


def _reset_module():
    for key in list(sys.modules.keys()):
        if 'steam_integration' in key:
            del sys.modules[key]


def _make_find_lb_response(lb_id: int | None) -> MagicMock:
    """FindLeaderboard/v1/ yanıtını simüle eden mock response."""
    if lb_id is not None:
        body = json.dumps({
            "leaderboard": {
                "leaderboardID": lb_id,
                "leaderboardName": "quadrix_classic",
                "leaderboardSortMethod": 2,
                "leaderboardDisplayType": 1,
            }
        }).encode('utf-8')
    else:
        body = json.dumps({}).encode('utf-8')

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_set_score_response(result_code: int) -> MagicMock:
    body = json.dumps({
        "result": {
            "result": result_code,
            "global_rank_new": 1,
            "score_changed": True,
        }
    }).encode('utf-8')
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestResolveLbIdViaWebApi(unittest.TestCase):
    """_resolve_lb_id_via_web_api fonksiyonu testleri."""

    def setUp(self):
        _reset_module()

    def tearDown(self):
        _reset_module()

    def _import_module(self):
        with patch('ctypes.CDLL', return_value=MagicMock()):
            import src.steam_integration as m
        # Testlerin çalışması için Partner API key ve App ID ayarla
        m._PARTNER_API_KEY = 'FAKE_TEST_KEY'
        m._APP_ID_INT = 4428040
        return m

    def test_returns_id_from_web_api(self):
        """_resolve_lb_id_via_web_api, FindLeaderboard/v1/'den gelen ID'yi döndürmeli."""
        m = self._import_module()

        # Cache'i temizle
        m._lb_id_web_cache.clear()

        with patch('urllib.request.urlopen', return_value=_make_find_lb_response(99999)):
            result = m._resolve_lb_id_via_web_api('quadrix_classic')

        self.assertEqual(result, 99999)

    def test_caches_result(self):
        """İkinci çağrı cache'den döndürmeli, yeni HTTP isteği atmamalı."""
        m = self._import_module()
        m._lb_id_web_cache.clear()

        with patch('urllib.request.urlopen', return_value=_make_find_lb_response(88888)) as mock_open:
            first = m._resolve_lb_id_via_web_api('quadrix_sprint')
            second = m._resolve_lb_id_via_web_api('quadrix_sprint')

        self.assertEqual(first, 88888)
        self.assertEqual(second, 88888)
        # urlopen yalnızca 1 kez çağrılmış olmalı
        self.assertEqual(mock_open.call_count, 1)

    def test_falls_back_to_hardcoded_on_api_failure(self):
        """HTTP hatasında _LB_NAME_TO_ID'den gelen sabit değer kullanılmalı."""
        import urllib.error
        m = self._import_module()
        m._lb_id_web_cache.clear()

        hardcoded_id = m._LB_NAME_TO_ID.get('quadrix_mystery')
        self.assertIsNotNone(hardcoded_id)

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("network error")):
            # _resolve_lb_id_via_web_api başarısız olursa None döner
            resolved = m._resolve_lb_id_via_web_api('quadrix_mystery')

        self.assertIsNone(resolved)

        # _submit_score_via_partner_api fallback kullanarak hardcoded ID ile POST atmalı
        captured = []

        def capture_post(req, timeout=None):
            if req.data:
                captured.append(req.data.decode('ascii'))
                return _make_set_score_response(1)
            return _make_set_score_response(1)

        with patch('urllib.request.urlopen', side_effect=capture_post):
            ok = m._submit_score_via_partner_api('quadrix_mystery', 50000, '76561199351154071')

        self.assertTrue(ok)
        self.assertTrue(captured, "POST isteği atılmamış")
        self.assertIn(f'leaderboardid={hardcoded_id}', captured[0])

    def test_submit_uses_dynamic_id(self):
        """_submit_score_via_partner_api, Web API'den gelen dinamik ID'yi kullanmalı."""
        m = self._import_module()
        m._lb_id_web_cache.clear()

        hardcoded_id = m._LB_NAME_TO_ID.get('quadrix_classic')
        dynamic_id = hardcoded_id + 9999  # kasıtlı farklı ID

        captured_get = []
        captured_post = []

        def fake_urlopen(req, timeout=None):
            if req.method == 'GET' or req.data is None:
                # FindLeaderboard GET isteği → dinamik ID döndür
                captured_get.append(req.full_url if hasattr(req, 'full_url') else str(req))
                return _make_find_lb_response(dynamic_id)
            else:
                # SetLeaderboardScore POST isteği
                captured_post.append(req.data.decode('ascii'))
                return _make_set_score_response(1)

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            ok = m._submit_score_via_partner_api('quadrix_classic', 60000, '76561199351154071')

        self.assertTrue(ok, "submit döndürmeli True")
        self.assertTrue(captured_get, "FindLeaderboard GET çağrısı yapılmamış")
        self.assertTrue(captured_post, "SetLeaderboardScore POST çağrısı yapılmamış")
        self.assertIn(f'leaderboardid={dynamic_id}', captured_post[0],
                      f"Dinamik ID ({dynamic_id}) POST payload'ında bekleniyor. "
                      f"Payload: {captured_post[0]}")

    def test_id_stored_in_cache_after_resolution(self):
        """Web API'den çözümlenen ID cache'e yazılmalı."""
        m = self._import_module()
        m._lb_id_web_cache.clear()

        with patch('urllib.request.urlopen', return_value=_make_find_lb_response(77777)):
            m._resolve_lb_id_via_web_api('quadrix_ultra')

        self.assertIn('quadrix_ultra', m._lb_id_web_cache)
        self.assertEqual(m._lb_id_web_cache['quadrix_ultra'], 77777)

    def test_returns_none_when_api_returns_no_id(self):
        """API yanıtı leaderboardID içermiyorsa None dönmeli."""
        m = self._import_module()
        m._lb_id_web_cache.clear()

        with patch('urllib.request.urlopen', return_value=_make_find_lb_response(None)):
            result = m._resolve_lb_id_via_web_api('quadrix_zen')

        self.assertIsNone(result)

    def test_returns_none_when_no_api_key(self):
        """_PARTNER_API_KEY boşsa None dönmeli, HTTP isteği atmamalı."""
        m = self._import_module()
        m._lb_id_web_cache.clear()

        original_key = m._PARTNER_API_KEY
        try:
            m._PARTNER_API_KEY = ''
            with patch('urllib.request.urlopen') as mock_open:
                result = m._resolve_lb_id_via_web_api('quadrix_zen')
                mock_open.assert_not_called()
            self.assertIsNone(result)
        finally:
            m._PARTNER_API_KEY = original_key


if __name__ == '__main__':
    unittest.main()
