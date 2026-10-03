import json
import os
import unittest
from unittest.mock import patch


# AppID/Cloud cakisma cozumu: env degiskenleri artik modul seviyesinde
# setdefault ile set edilmiyor. Modul seviyesindeki STEAM_WEB_API_KEY=TESTKEY
# degeri tum pytest surecine siziyor, test_lb_write'in donanim-test atlama
# korumasini etkisiz birakiyordu (gercek steam_api64.dll yuklenmesi ->
# python.exe AppID 4428040 altinda takip -> Playtest AutoCloud senkronu).
# create_app() ve SteamLeaderboardService env degiskenlerini cagri aninda
# okur; import sirasinda env setine gerek yoktur.
from backend.steam_leaderboard_proxy import create_app, SteamDirectGateway
from steam_leaderboards import SteamLeaderboardService


class TestLeaderboardAppIdRouting(unittest.TestCase):
    _TEST_ENV = {
        "STEAM_APP_ID": "4428040",
        "STEAM_WEB_API_KEY": "TESTKEY",
        "LEADERBOARD_CLIENT_TOKEN": "test-client-token",
        "LEADERBOARD_TOKEN_SECRET": "test-token-secret-32-chars-xxxxxx",
        "LEADERBOARD_ALLOWED_APP_IDS": "4428040,4414520,4635310",
    }

    def setUp(self):
        self._saved_env = {name: os.environ.get(name) for name in self._TEST_ENV}
        os.environ.update(self._TEST_ENV)
        self.addCleanup(self._restore_test_env)

    def _restore_test_env(self):
        for name, old_value in self._saved_env.items():
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value
    def test_client_sends_app_id_header(self):
        service = SteamLeaderboardService(
            backend_base_url="http://leaderboard.test",
            client_token="client-token",
            app_id=4635310,
        )

        headers = service._build_headers()

        self.assertEqual(headers["X-Quadrix-App-Id"], "4635310")
        self.assertEqual(headers["X-Client-Token"], "client-token")

    def test_backend_routes_submit_to_requested_app_id(self):
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch.object(
            SteamDirectGateway,
            "verify_steam_ticket",
            autospec=True,
            return_value=(True, "76561198000000001", ""),
        ):
            with patch.object(
                SteamDirectGateway,
                "set_score",
                autospec=True,
                return_value=True,
            ) as mock_set_score:
                response = client.post(
                    "/api/v1/leaderboards/classic/submit",
                    headers={
                        "X-Client-Token": "test-client-token",
                        "X-Quadrix-App-Id": "4635310",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps({"ticket": "aabbccdd", "score": 1000}),
                )

        self.assertEqual(response.status_code, 200)
        routed_gateway = mock_set_score.call_args.args[0]
        self.assertEqual(routed_gateway.app_id, 4635310)
        self.assertEqual(response.get_json()["app_id"], 4635310)


if __name__ == "__main__":
    unittest.main()
