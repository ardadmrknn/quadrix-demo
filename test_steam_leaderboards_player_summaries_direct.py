# -*- coding: utf-8 -*-
"""Birim testleri: SteamLeaderboardService direct mod player summaries fallback.

fetch_player_summaries() backend kapalıyken de persona/avatar verisi döndürmeli.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

FAKE_KEY = 'FAKEPUBLISHERKEY'
FAKE_APP_ID = 4428040
FAKE_SID = '76561199351154071'


def _make_direct_only_service():
    """Backend URL olmayan (direct-only) bir SteamLeaderboardService oluştur."""
    from steam_leaderboards import SteamLeaderboardService
    return SteamLeaderboardService(
        backend_base_url='',           # backend yok
        publisher_key=FAKE_KEY,
        app_id=FAKE_APP_ID,
    )


FAKE_SUMMARIES_RESP = {
    "response": {
        "players": [
            {
                "steamid": FAKE_SID,
                "personaname": "TestPersona",
                "avatar": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/avatars/ab/ab_small.jpg",
                "avatarmedium": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/avatars/ab/ab_medium.jpg",
                "avatarfull": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/avatars/ab/ab_full.jpg",
                "profileurl": "https://steamcommunity.com/id/test/",
            }
        ]
    }
}


class TestFetchPlayerSummariesDirectMode(unittest.TestCase):
    """Direct modda fetch_player_summaries() Steam API'ye istek atmalı."""

    def _mock_get(self, json_resp):
        """requests.get mockunu hazırla."""
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'ok'
        resp.json.return_value = json_resp
        resp.raise_for_status = MagicMock()
        return resp

    def test_direct_mode_returns_summaries(self):
        """Backend yokken direct modda persona ve avatarmedium URL döner."""
        svc = _make_direct_only_service()

        with patch('requests.get', return_value=self._mock_get(FAKE_SUMMARIES_RESP)) as mock_get:
            result = svc.fetch_player_summaries([FAKE_SID])

        self.assertIn(FAKE_SID, result, f"Expected {FAKE_SID!r} in result, got: {result}")
        info = result[FAKE_SID]
        self.assertEqual(info['personaname'], 'TestPersona')
        self.assertIn('avatarmedium', info)
        self.assertTrue(info['avatarmedium'])

    def test_direct_mode_calls_get_player_summaries_endpoint(self):
        """ISteamUser/GetPlayerSummaries/v2/ endpoint'i çağrılmalı."""
        svc = _make_direct_only_service()

        with patch('requests.get', return_value=self._mock_get(FAKE_SUMMARIES_RESP)) as mock_get:
            svc.fetch_player_summaries([FAKE_SID])

        self.assertTrue(mock_get.called)
        called_url = str(mock_get.call_args[0][0] if mock_get.call_args[0] else mock_get.call_args)
        self.assertIn('GetPlayerSummaries', called_url)

    def test_direct_mode_includes_required_params(self):
        """İstek key, steamids parametrelerini içermeli."""
        svc = _make_direct_only_service()

        with patch('requests.get', return_value=self._mock_get(FAKE_SUMMARIES_RESP)) as mock_get:
            svc.fetch_player_summaries([FAKE_SID])

        params = mock_get.call_args[1].get('params', {}) if mock_get.call_args else {}
        self.assertEqual(params.get('key'), FAKE_KEY)
        self.assertIn(FAKE_SID, str(params.get('steamids', '')))

    def test_direct_mode_normalizes_output_shape(self):
        """Çıktı shape'i backend-mode sonucuyla aynı olmalı: steam_id -> dict keksi."""
        svc = _make_direct_only_service()

        with patch('requests.get', return_value=self._mock_get(FAKE_SUMMARIES_RESP)):
            result = svc.fetch_player_summaries([FAKE_SID])

        info = result.get(FAKE_SID, {})
        for key in ('personaname', 'avatar', 'avatarmedium', 'avatarfull', 'profileurl'):
            self.assertIn(key, info, f"Beklenen alan eksik: {key!r}")

    def test_direct_mode_multiple_ids(self):
        """Birden fazla steamid desteklenmeli; sonuçlar doğru map'lenmeli."""
        sid2 = '76561199351154072'
        multi_resp = {
            "response": {
                "players": [
                    {"steamid": FAKE_SID, "personaname": "Alice", "avatar": "a", "avatarmedium": "am", "avatarfull": "af", "profileurl": "pu"},
                    {"steamid": sid2, "personaname": "Bob", "avatar": "b", "avatarmedium": "bm", "avatarfull": "bf", "profileurl": "pu2"},
                ]
            }
        }
        svc = _make_direct_only_service()

        with patch('requests.get', return_value=self._mock_get(multi_resp)):
            result = svc.fetch_player_summaries([FAKE_SID, sid2])

        self.assertEqual(result[FAKE_SID]['personaname'], 'Alice')
        self.assertEqual(result[sid2]['personaname'], 'Bob')

    def test_direct_mode_empty_ids_returns_empty(self):
        """Boş liste verilince hata çıkmamalı, boş dict dönmeli."""
        svc = _make_direct_only_service()
        result = svc.fetch_player_summaries([])
        self.assertEqual(result, {})

    def test_direct_mode_network_error_returns_empty(self):
        """Ağ hatası durumunda crash olmadan boş dict dönmeli."""
        svc = _make_direct_only_service()

        import requests as _req
        with patch('requests.get', side_effect=_req.exceptions.ConnectionError("refused")):
            result = svc.fetch_player_summaries([FAKE_SID])

        self.assertEqual(result, {})
        self.assertTrue(bool(svc.last_error))

    def test_backend_mode_still_uses_backend_endpoint(self):
        """Backend URL varsa backend endpoint kullanılmaya devam etmeli (fallback devreye girmemeli)."""
        from steam_leaderboards import SteamLeaderboardService
        svc = SteamLeaderboardService(
            backend_base_url='http://127.0.0.1:8787',
            publisher_key=FAKE_KEY,
            app_id=FAKE_APP_ID,
        )
        # Backend endpoint: /api/v1/players/summaries (GET)
        # Direct Steam endpoint: partner.steam-api.com (GET)
        backend_resp = {"players": {FAKE_SID: {"personaname": "BackendUser", "avatar": "", "avatarmedium": "", "avatarfull": "", "profileurl": ""}}}
        with patch('requests.get', return_value=self._mock_get(backend_resp)) as mock_get:
            result = svc.fetch_player_summaries([FAKE_SID])

        # Check the URL used: should be backend, not Steam Web API
        called_url = ''
        if mock_get.called:
            args = mock_get.call_args
            called_url = str(args[0][0] if args[0] else args)
        self.assertNotIn('partner.steam-api.com', called_url, "Backend modda Steam Web API'ye gidilmemeli")


if __name__ == '__main__':
    unittest.main()
