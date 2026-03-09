from __future__ import annotations

import unittest
from unittest.mock import patch

from leaderboard_rank_utils import rerank_entries_for_local_subset
from steam_leaderboards import SteamLeaderboardService


class TestLeaderboardFriendRanks(unittest.TestCase):
    def test_rerank_entries_for_local_subset_preserves_order(self):
        source = [
            {"rank": 14, "score": 9800, "steam_id": "friend-b"},
            {"rank": 22, "score": 8700, "steam_id": "friend-c"},
            {"rank": 31, "score": 8200, "steam_id": "friend-d"},
        ]

        result = rerank_entries_for_local_subset(source)

        self.assertEqual([entry["rank"] for entry in result], [1, 2, 3])
        self.assertEqual([entry["steam_id"] for entry in result], ["friend-b", "friend-c", "friend-d"])
        self.assertEqual(source[0]["rank"], 14)

    def test_fetch_mode_friend_highscores_reranks_backend_entries(self):
        service = SteamLeaderboardService(
            backend_base_url="http://127.0.0.1:8787",
            session_token="test-session-token",
        )
        payload = {
            "entries": [
                {"rank": 19, "score": 9100, "steam_id": "friend-a"},
                {"rank": 47, "score": 7800, "steam_id": "friend-b"},
            ]
        }

        with patch.object(service, "_get_json", return_value=payload):
            result = service.fetch_mode_friend_highscores("mystery", limit=10)

        self.assertEqual([entry["rank"] for entry in result], [1, 2])
        self.assertEqual([entry["steam_id"] for entry in result], ["friend-a", "friend-b"])

    def test_fetch_mode_friend_highscores_reranks_direct_entries(self):
        service = SteamLeaderboardService(backend_base_url="", publisher_key="KEY", app_id=4428040)

        with patch.object(
            service,
            "_fetch_direct_entries",
            return_value=[
                {"rank": 8, "score": 12500, "steam_id": "friend-a"},
                {"rank": 15, "score": 9200, "steam_id": "friend-b"},
            ],
        ):
            result = service.fetch_mode_friend_highscores("mystery", limit=10)

        self.assertEqual([entry["rank"] for entry in result], [1, 2])
        self.assertEqual([entry["steam_id"] for entry in result], ["friend-a", "friend-b"])


if __name__ == "__main__":
    unittest.main()