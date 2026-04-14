from __future__ import annotations

import pathlib
import re


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
CPP_PATH = ROOT_DIR / 'steamworks' / 'steam_net_bridge' / 'steam_net_bridge.cpp'


def test_bridge_sets_visibility_metadata_on_lobby_created():
    """C++ OnLobbyCreated yalnızca temel keşif metadata'sı yazar.

    Hassas alanlar (visibility, requires_code, lobby_code) Python
    tarafından yazılır; böylece C++ public yazar → diğer platform
    okur → Python private override yapar şeklinde bir race window
    önlenir.  metadata_ready=0 olarak işaretlenir, Python tüm
    alanları doğru yazdıktan sonra 1 yapar.
    """
    content = CPP_PATH.read_text(encoding='utf-8')

    # Hata durumunda error data hâlâ pending visibility bilgisini içerir
    assert 'std::string errorData = std::string("result=") + std::to_string((int)pResult->m_eResult) +' in content
    assert '",visibility=" + m_pendingLobbyVisibility +' in content
    assert '",requires_code=" + (m_pendingLobbyRequiresCode ? std::string("1") : std::string("0"));' in content

    # Başarı yolunda C++ yalnızca game/version/host_name/metadata_ready=0 yazar
    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "game", "quadrix")' in content
    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "version", "1.0")' in content
    assert 'm_matchmaking->SetLobbyData(m_currentLobby, "metadata_ready", "0")' in content
    assert 'm_matchmaking->SetLobbyJoinable(m_currentLobby, true);' in content

    # set_pending_lobby_metadata hâlâ create_public_lobby tarafından çağrılır
    assert 'set_pending_lobby_metadata(k_ELobbyTypePublic);' in content


def test_bridge_uses_invisible_lobby_type_for_searchable_private_code_lobbies():
    content = CPP_PATH.read_text(encoding='utf-8')

    assert 'set_pending_lobby_metadata(k_ELobbyTypeInvisible);' in content
    assert 'CreateLobby(k_ELobbyTypeInvisible, max_members);' in content


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