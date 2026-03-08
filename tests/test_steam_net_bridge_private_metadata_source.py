from __future__ import annotations

import pathlib


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
CPP_PATH = ROOT_DIR / 'steamworks' / 'steam_net_bridge' / 'steam_net_bridge.cpp'


def test_bridge_sets_visibility_metadata_on_lobby_created():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "visibility", m_pendingLobbyVisibility.c_str())' in content
    assert '"requires_code"' in content
    assert 'set_pending_lobby_metadata(k_ELobbyTypePublic);' in content