import json
import os
import unittest
from unittest.mock import patch


os.environ.setdefault("STEAM_APP_ID", "4428040")
os.environ.setdefault("STEAM_WEB_API_KEY", "TESTKEY")
os.environ.setdefault("LEADERBOARD_CLIENT_TOKEN", "test-client-token")
os.environ.setdefault("LEADERBOARD_TOKEN_SECRET", "test-token-secret-32-chars-xxxxxx")
os.environ.setdefault("LEADERBOARD_ALLOWED_APP_IDS", "4428040,4414520,4635310")

from backend.steam_leaderboard_proxy import create_app, SteamDirectGateway
from steam_leaderboards import SteamLeaderboardService


class TestLeaderboardAppIdRouting(unittest.TestCase):
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
