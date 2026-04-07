from __future__ import annotations

import pathlib
import re


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
CPP_PATH = ROOT_DIR / 'steamworks' / 'steam_net_bridge' / 'steam_net_bridge.cpp'


def test_bridge_sets_visibility_metadata_on_lobby_created():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "visibility", m_pendingLobbyVisibility.c_str())' in content
    assert '"requires_code"' in content
    assert 'set_pending_lobby_metadata(k_ELobbyTypePublic);' in content


def test_bridge_retries_incomplete_lobby_metadata_before_emitting():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'remember_pending_lobby_data_request(lobbyId.ConvertToUint64())' in content
    assert 'bool retry_pending_lobby_data_request(CSteamID lobbyId)' in content
    assert 'bool is_lobby_metadata_ready_for_listing(CSteamID lobbyId) const' in content


def test_bridge_infers_public_visibility_from_explicit_requires_code():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert re.search(
        r'if\s*\(hasRequiresCode\)\s*\{?\s*visibility = requiresCodeBool \? "private" : "public";',
        content,
    )
    assert 'visibility = requiresCodeBool ? "private" : "public";' in content