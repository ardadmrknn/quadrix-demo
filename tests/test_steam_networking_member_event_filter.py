from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from steam_networking import SteamNetworking, NetEvent


class TestSteamNetworkingMemberEventFilter(unittest.TestCase):
    def test_disconnected_event_ignored_when_member_still_in_lobby(self):
        net = SteamNetworking()
        net._opponent_steam_id = 42
        net._opponent_name = 'Opponent'
        net._state = 'playing'

        net.get_lobby_members = lambda: [1, 42]

        net._handle_internal_event(NetEvent('lobby_member_disconnected', 42, '18'))

        self.assertEqual(net._opponent_steam_id, 42)
        self.assertEqual(net._opponent_name, 'Opponent')
        self.assertEqual(net._state, 'playing')

    def test_left_event_clears_opponent_when_not_in_member_list(self):
        net = SteamNetworking()
        net._opponent_steam_id = 42
        net._opponent_name = 'Opponent'
        net._state = 'playing'

        net.get_lobby_members = lambda: [1]

        net._handle_internal_event(NetEvent('lobby_member_left', 42, '2'))

        self.assertEqual(net._opponent_steam_id, 0)
        self.assertEqual(net._opponent_name, '')
        self.assertEqual(net._state, 'waiting')


if __name__ == '__main__':
    unittest.main()
