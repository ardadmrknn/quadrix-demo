"""Tests for the secure server-side leaderboard write endpoint."""
import json, os, unittest
from unittest.mock import patch, MagicMock

# We'll need to set env vars before importing the app
os.environ.setdefault('STEAM_APP_ID', '4428040')
os.environ.setdefault('STEAM_WEB_API_KEY', 'TESTKEY')
os.environ.setdefault('LEADERBOARD_CLIENT_TOKEN', 'test-client-token')
os.environ.setdefault('LEADERBOARD_TOKEN_SECRET', 'test-token-secret-32-chars-xxxxxx')

from backend.steam_leaderboard_proxy import create_app, SteamDirectGateway


class TestSubmitEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_submit_endpoint_exists(self):
        """POST /api/v1/leaderboards/classic/submit should return 200 or 4xx, not 404/405"""
        resp = self.client.post(
            '/api/v1/leaderboards/classic/submit',
            headers={'X-Client-Token': 'test-client-token', 'Content-Type': 'application/json'},
            data=json.dumps({'ticket': 'aabbccdd', 'score': 12345}),
        )
        self.assertNotEqual(resp.status_code, 404)
        self.assertNotEqual(resp.status_code, 405)

    def test_submit_requires_client_token(self):
        """Missing X-Client-Token should return 401"""
        resp = self.client.post(
            '/api/v1/leaderboards/classic/submit',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'ticket': 'aabb', 'score': 100}),
        )
        self.assertEqual(resp.status_code, 401)

    def test_submit_calls_set_score_with_correct_params(self):
        """On valid ticket+score, should call set_score with correct args and return success"""
        with patch.object(SteamDirectGateway, 'verify_steam_ticket', return_value=(True, '76561198000000001', '')):
            with patch.object(SteamDirectGateway, 'set_score', return_value=True) as mock_set:
                resp = self.client.post(
                    '/api/v1/leaderboards/classic/submit',
                    headers={'X-Client-Token': 'test-client-token', 'Content-Type': 'application/json'},
                    data=json.dumps({'ticket': 'aabbccdd', 'score': 99999}),
                )
                self.assertEqual(resp.status_code, 200)
                mock_set.assert_called_once()
                call_kwargs = mock_set.call_args
                # scoremethod must be "KeepBest" (string)
                args, kwargs = call_kwargs
                scoremethod_val = kwargs.get('scoremethod', args[3] if len(args) > 3 else None)
                self.assertEqual(scoremethod_val, 'KeepBest')

    def test_submit_returns_error_on_ticket_failure(self):
        """Invalid ticket should return 403"""
        with patch.object(SteamDirectGateway, 'verify_steam_ticket', return_value=(False, '', 'bad ticket')):
            resp = self.client.post(
                '/api/v1/leaderboards/classic/submit',
                headers={'X-Client-Token': 'test-client-token', 'Content-Type': 'application/json'},
                data=json.dumps({'ticket': 'deadbeef', 'score': 500}),
            )
            self.assertEqual(resp.status_code, 403)

    def test_submit_scoremethod_is_string_in_web_api_call(self):
        """set_score must accept scoremethod as string and pass it as string to _post_web"""
        gw = SteamDirectGateway(app_id=4428040, publisher_key='TESTKEY')
        with patch.object(gw, '_post_web', return_value={'result': {'result': 1, 'global_rank_new': 42}}) as mock_pw:
            with patch.object(gw, '_resolve_mode_leaderboard_id', return_value=12345):
                result = gw.set_score('classic', '76561198000000001', 99999, scoremethod='KeepBest')
                self.assertTrue(result)
                _, kwargs = mock_pw.call_args
                # scoremethod must be passed as string
                passed_scoremethod = kwargs.get('scoremethod', None)
                self.assertIsInstance(passed_scoremethod, str)
                self.assertEqual(passed_scoremethod, 'KeepBest')

    def test_set_score_returns_false_on_result8(self):
        """set_score returns False when Steam returns result=8 (InvalidParam)"""
        gw = SteamDirectGateway(app_id=4428040, publisher_key='TESTKEY')
        with patch.object(gw, '_post_web', return_value={'result': {'result': 8}}):
            with patch.object(gw, '_resolve_mode_leaderboard_id', return_value=12345):
                result = gw.set_score('classic', '76561198000000001', 99999)
                self.assertFalse(result)

    def test_submit_missing_score_returns_400(self):
        """Missing score field returns 400"""
        with patch.object(SteamDirectGateway, 'verify_steam_ticket', return_value=(True, '76561198000000001', '')):
            resp = self.client.post(
                '/api/v1/leaderboards/classic/submit',
                headers={'X-Client-Token': 'test-client-token', 'Content-Type': 'application/json'},
                data=json.dumps({'ticket': 'aabbccdd'}),
            )
            self.assertEqual(resp.status_code, 400)

    def test_submit_missing_ticket_returns_400(self):
        """Missing ticket field returns 400"""
        with patch.object(SteamDirectGateway, 'verify_steam_ticket', return_value=(True, '76561198000000001', '')):
            resp = self.client.post(
                '/api/v1/leaderboards/classic/submit',
                headers={'X-Client-Token': 'test-client-token', 'Content-Type': 'application/json'},
                data=json.dumps({'score': 999}),
            )
            self.assertEqual(resp.status_code, 400)


if __name__ == '__main__':
    unittest.main()
