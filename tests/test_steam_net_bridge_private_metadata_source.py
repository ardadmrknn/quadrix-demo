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
    assert 'generate_lobby_code(lobbyIdValue)' in content
    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "lobby_code", lobbyCode.c_str())' in content
    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "metadata_ready", "1")' in content
    assert 'm_matchmaking->SetLobbyJoinable(m_currentLobby, true);' in content


def test_bridge_retries_incomplete_lobby_metadata_without_blocking_list_completion():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'emit_lobby_found(lobbyId);' in content
    assert 'push_event("lobby_list_complete", 0, "");' in content
    assert 'remember_pending_lobby_data_request(lobbyId.ConvertToUint64())' in content
    assert 'bool retry_pending_lobby_data_request(CSteamID lobbyId)' in content
    assert 'bool is_lobby_metadata_ready_for_listing(CSteamID lobbyId) const' in content
    assert 'push_event("lobby_data_updated",' in content


def test_bridge_infers_public_visibility_from_explicit_requires_code():
    content = CPP_PATH.read_text(encoding='utf-8')

    # hasRequiresCode dalında requires_code boolean'dan visibility türetiliyor
    assert re.search(
        r'else\s+if\s*\(hasRequiresCode\)',
        content,
    )
    assert r'visibilityJson = rc ? "\"private\"" : "\"public\"";' in content


def test_bridge_exports_distance_filter_for_worldwide_code_search():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'void add_request_lobby_list_distance_filter(int distance_filter)' in content
    assert 'AddRequestLobbyListDistanceFilter(' in content