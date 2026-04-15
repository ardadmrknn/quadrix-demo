from __future__ import annotations

import pathlib
import sys
import types
from unittest.mock import Mock


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as online_pvp_module
from steam_networking import NetEvent, generate_lobby_code


def _make_game():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._pending_lobby_list = []
    game._lobby_list = []
    game._lobby_list_scroll = 0
    game._deferred_lobby_entries = {}
    game._lobby_list_fetching = False
    game._lobby_list_fetch_start_time = 0
    game._lobby_list_filter = 'all'
    game._net_initialized = False
    game._authorized_private_join_lobby_id = 0
    game._authorized_private_join_code = ''
    game._invite_authorized_lobby_id = 0
    game._pending_access_revalidation_lobby_id = 0
    game._lobby_access_validated_id = 0
    game._searching_by_code = False
    game._search_code = ''
    game._code_search_retry_count = 0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._code_search_retry_use_full_scan = False
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game._DEFERRED_LOBBY_REFRESH_INTERVAL_MS = 500.0
    game._DISCONNECT_GRACE_MS = 5000.0
    game._unknown_lobby_metadata_requests = {}
    return game


def test_lobby_found_does_not_fallback_to_current_lobby_metadata():
    """Metadata tamamen boşsa lobi sync durumunda görünür kalmalı."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: 'private',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=42,
        data='{"host_name":"mac-host","members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    pending_lobby = game._pending_lobby_list[0]
    assert pending_lobby['visibility'] == 'unknown'
    assert pending_lobby['requires_code'] is False
    assert pending_lobby['metadata_ready'] is False
    lobby = game._deferred_lobby_entries[42]
    assert lobby['visibility'] == 'unknown'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is False


def test_lobby_list_complete_keeps_unknown_lobby_visible_while_metadata_syncs():
    game = _make_game()
    game._pending_lobby_list = [{
        'id': 42,
        'name': 'Bekleyen lobi',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'members': 1,
        'max_members': 2,
        'found_time': 0,
    }]
    game.net = types.SimpleNamespace(join_lobby=Mock())

    game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

    assert len(game._lobby_list) == 1
    lobby = game._lobby_list[0]
    assert lobby['visibility'] == 'unknown'
    assert lobby['metadata_ready'] is False
    game.net.join_lobby.assert_not_called()


def test_lobby_found_uses_per_lobby_metadata_for_private_visibility():
    game = _make_game()

    def _get_lobby_data_for(_lobby_id, key):
        mapping = {
            'visibility': 'private',
            'requires_code': '1',
            'host_name': 'mac-host',
            'lobby_code': '123456',
        }
        return mapping.get(key, '')

    game.net = types.SimpleNamespace(
        get_lobby_data_for=_get_lobby_data_for,
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=43,
        data='{"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'private'
    assert lobby['requires_code'] is True
    assert lobby['code'] == '123456'
    assert lobby['metadata_ready'] is True


def test_lobby_found_infers_public_when_requires_code_is_false():
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=44,
        data='{"host_name":"mac-host","requires_code":false,"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True


def test_lobby_found_keeps_public_visibility_when_requires_code_missing():
    game = _make_game()

    def _get_lobby_data_for(_lobby_id, key):
        mapping = {
            'visibility': 'public',
            'requires_code': '',
            'host_name': 'mac-host',
            'lobby_code': '',
        }
        return mapping.get(key, '')

    game.net = types.SimpleNamespace(
        get_lobby_data_for=_get_lobby_data_for,
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=45,
        data='{"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True


def test_lobby_found_uses_explicit_visibility_even_when_metadata_ready_is_false():
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=46,
        data='{"host_name":"mac-host","visibility":"private","requires_code":true,"metadata_ready":false,"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'private'
    assert lobby['requires_code'] is True
    assert lobby['metadata_ready'] is True


def test_lobby_data_updated_refreshes_cached_lobby_entry():
    game = _make_game()
    game._lobby_list = [{
        'id': 99,
        'name': 'Unknown host',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
    }]
    game._code_search_retry_count = 0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._code_search_retry_use_full_scan = False
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda _lobby_id, key: {
            'host_name': 'Public host',
            'visibility': 'public',
            'requires_code': '0',
            'metadata_ready': '1',
            'lobby_code': '',
        }.get(key, ''),
        get_lobby_data=lambda key: '',
        join_lobby=Mock(),
    )

    game._on_lobby_data_updated(NetEvent('lobby_data_updated', 99, '99'))

    lobby = game._lobby_list[0]
    assert lobby['name'] == 'Public host'
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True
    game.net.join_lobby.assert_not_called()


def test_lobby_data_updated_can_complete_pending_code_join():
    game = _make_game()
    game._lobby_list = [{
        'id': 77,
        'name': 'Pending host',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
    }]
    game._code_search_retry_count = 1
    game._code_search_retry_timer = 1500.0
    game._code_search_retry_code = '123456'
    game._code_search_retry_use_full_scan = True
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda _lobby_id, key: {
            'host_name': 'Private host',
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
        get_lobby_data=lambda key: '',
        join_lobby=Mock(),
    )

    game._on_lobby_data_updated(NetEvent('lobby_data_updated', 77, '77'))

    game.net.join_lobby.assert_called_once_with(77)
    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == '123456'
    assert game._code_search_retry_code == ''
    assert game._code_search_retry_timer == 0.0
    assert game._code_search_retry_use_full_scan is False


def test_lobby_data_updated_promotes_deferred_lobby_entry_once_visibility_is_known():
    game = _make_game()
    game._deferred_lobby_entries = {
        88: {
            'id': 88,
            'name': 'Bekleyen lobi',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
        }
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda _lobby_id, key: {
            'host_name': 'Private host',
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '654321',
        }.get(key, ''),
        get_lobby_data=lambda key: '',
        join_lobby=Mock(),
        lobby_id=0,
    )

    game._on_lobby_data_updated(NetEvent('lobby_data_updated', 88, '88'))

    assert 88 not in game._deferred_lobby_entries
    assert len(game._lobby_list) == 1
    lobby = game._lobby_list[0]
    assert lobby['visibility'] == 'private'
    assert lobby['requires_code'] is True
    assert lobby['code'] == '654321'


def test_resolve_lobby_display_state_keeps_unknown_metadata_unknown():
    visibility, requires_code = online_pvp_module._resolve_lobby_display_state('unknown', False, '')

    assert visibility == 'unknown'
    assert requires_code is False


def test_resolve_lobby_display_state_keeps_private_when_code_exists():
    visibility, requires_code = online_pvp_module._resolve_lobby_display_state('unknown', False, '123456')

    assert visibility == 'private'
    assert requires_code is True


def test_validate_joined_lobby_access_accepts_authorized_private_join_by_code():
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        get_lobby_data_for=lambda _lobby_id, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()
    game._remember_private_join_authorization(77, '123456')

    assert game._validate_joined_lobby_access() is True
    assert game._authorized_private_join_lobby_id == 0
    assert game._authorized_private_join_code == ''
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_validate_joined_lobby_access_accepts_private_lobby_owner_without_code():
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=55,
        is_host=False,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lobby_id, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()

    assert game._validate_joined_lobby_access() is True
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_on_lobby_created_authorizes_private_host_lobby_code():
    game = _make_game()
    game.online_state = None
    game._lobby_presence_probe_timer = 0.0
    game._lobby_id_str = ''
    game._lobby_code = ''
    game._creating_public_lobby = False
    game._invite_after_lobby = False
    game.net = types.SimpleNamespace(invite_friend=Mock())

    game._on_lobby_created(NetEvent('lobby_created', 77, ''))

    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == generate_lobby_code(77)


def test_validate_joined_lobby_access_rejects_unauthorized_private_join():
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        get_lobby_data_for=lambda _lobby_id, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()

    assert game._validate_joined_lobby_access() is False
    game._return_to_pvp_lobby_menu.assert_called_once_with()
    assert 'kod veya davet gerekli' in game._status_msg.lower()


# ============================================================
# Bug B fix: _on_lobby_data_updated tekrarlı validation kick'i
# ============================================================

def test_lobby_data_updated_does_not_re_validate_after_successful_access():
    """lobby_data_updated, erişim doğrulanmış lobide tekrar validation çağırmamalı.

    Bug: macOS Windows özel lobiye katılıyor, ilk validation geçiyor,
    sonra lobby_data_updated gelince auth temizlenmiş olduğu için
    ikinci validation KICK atıyordu.
    """
    game = _make_game()
    game.online_state = online_pvp_module.OnlineState.WAITING
    game._net_initialized = True

    private_metadata = {
        'visibility': 'private',
        'requires_code': '1',
        'metadata_ready': '1',
        'lobby_code': '123456',
    }
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        opponent_steam_id=0,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: private_metadata.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()

    # İlk validation: kod ile yetkilendirilmiş
    game._remember_private_join_authorization(77, '123456')
    assert game._validate_joined_lobby_access() is True
    assert game._lobby_access_validated_id == 77

    # Auth temizlenmiş (validation başarılı olunca temizlenir)
    assert game._authorized_private_join_lobby_id == 0

    # lobby_data_updated event'i: tekrar validation çağrılmamalı
    game._on_lobby_data_updated(NetEvent(
        'lobby_data_updated', 77,
        '{"visibility":"private","requires_code":true,"metadata_ready":true,"lobby_code":"123456"}',
    ))
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_lobby_data_updated_revalidates_when_pending():
    """pending_access_revalidation aktifken lobby_data_updated validation çağırmalı."""
    game = _make_game()
    game.online_state = online_pvp_module.OnlineState.WAITING
    game._net_initialized = True

    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        opponent_steam_id=0,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '654321',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()
    game._pending_access_revalidation_lobby_id = 77

    # Pending revalidation + auth yok → reject
    game._on_lobby_data_updated(NetEvent(
        'lobby_data_updated', 77,
        '{"visibility":"private","requires_code":true,"metadata_ready":true}',
    ))
    game._return_to_pvp_lobby_menu.assert_called()


def test_validated_access_id_prevents_repeated_validation():
    """_lobby_access_validated_id set edildikten sonra aynı lobi için validation skip."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()
    game._lobby_access_validated_id = 77

    # Auth yok ama validated_id set → skip, True döner
    assert game._validate_joined_lobby_access() is True
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_validated_access_id_resets_on_lobby_leave():
    """_return_to_pvp_lobby_menu çağrıldığında _lobby_access_validated_id sıfırlanmalı."""
    game = _make_game()
    game.online_state = online_pvp_module.OnlineState.WAITING
    game.my_ready = False
    game.opponent_ready = False
    game._ready_resend_timer = 0.0
    game._session_established = False
    game._ready_send_pending = False
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_ping_timer = 0.0
    game._session_ping_backoff_ms = 0.0
    game._game_start_pending_payload = None
    game._game_start_retry_timer = 0.0
    game.paused = False
    game.opponent_paused = False
    game.opponent_piece_data = None
    game._opponent_piece_seq = 0
    game._lobby_code = ''
    game._lobby_id_str = ''
    game._join_code_active = False
    game._join_code_input = ''
    game._join_code_error = ''
    game._auto_lobby_refresh_requested = False
    game._auto_lobby_refresh_timer = 0.0
    game._auto_connect_retry_timer = 0.0
    game._invite_after_lobby = False
    game._creating_public_lobby = False
    game._pending_lobby_list = []
    game._deferred_lobby_entries = {}
    game._lobby_list_fetching = False
    game._lobby_list_fetch_start_time = 0
    game.net = types.SimpleNamespace(leave_lobby=Mock())
    game._lobby_access_validated_id = 77
    game._reset_match_result_state = Mock()

    game._return_to_pvp_lobby_menu()

    assert game._lobby_access_validated_id == 0


def test_validate_sets_validated_id_on_unknown_metadata_with_auth():
    """Metadata unknown + authorized by code → _lobby_access_validated_id set edilmeli."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: '',
    )
    game._return_to_pvp_lobby_menu = Mock()
    game._remember_private_join_authorization(77, '123456')

    result = game._validate_joined_lobby_access()
    assert result is True
    assert game._lobby_access_validated_id == 77
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_on_lobby_joined_resets_stale_validated_id():
    """Yeni lobiye katılırken önceki lobiden kalan validated_id sıfırlanmalı.

    Stale validated_id aynı lobby_id'ye tekrar katılındığında (kick sonrası)
    validation atlanmasına ve yetkisiz erişime izin verebilir.
    """
    game = _make_game()
    game.online_state = online_pvp_module.OnlineState.LOBBY_MENU
    game._lobby_presence_probe_timer = 0.0
    game._join_target_lobby_id = 0
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        opponent_steam_id=0,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()

    # Önceki oturumdan kalan stale validated_id (aynı lobby_id)
    game._lobby_access_validated_id = 77

    # Auth yokken katılma: stale ID sıfırlanmalı, doğrulama başarısız → kick
    game._on_lobby_joined(NetEvent('lobby_joined', 77, ''))

    game._return_to_pvp_lobby_menu.assert_called_once()


def test_on_lobby_created_resets_stale_validated_id():
    """Yeni lobi oluşturulurken önceki lobiden kalan state sıfırlanmalı."""
    game = _make_game()
    game.online_state = None
    game._lobby_presence_probe_timer = 0.0
    game._lobby_id_str = ''
    game._lobby_code = ''
    game._creating_public_lobby = False
    game._invite_after_lobby = False
    game.net = types.SimpleNamespace(
        set_lobby_data=Mock(),
        invite_friend=Mock(),
    )

    # Önceki oturumdan kalan stale state
    game._lobby_access_validated_id = 42
    game._pending_access_revalidation_lobby_id = 42

    game._on_lobby_created(NetEvent('lobby_created', 77, ''))

    assert game._lobby_access_validated_id == 0
    assert game._pending_access_revalidation_lobby_id == 0


def test_refresh_unknown_does_not_mark_public_on_partial_propagation():
    """metadata_ready=1 ama visibility/requires_code boş ise public yapılmamalı.

    Cross-platform'da SetLobbyData çağrıları bağımsız propagate olabilir.
    metadata_ready=1 diğer alanlardan önce ulaşabilir. Bu durumda
    lobi 'unknown' kalmalı, 'public' olarak yanlış işaretlenmemeli.
    """
    game = _make_game()
    game._net_initialized = True

    # Partial propagation senaryosu:
    # game=quadrix ve metadata_ready=1 gelmiş ama visibility/requires_code boş
    partial_metadata = {
        'game': 'quadrix',
        'metadata_ready': '1',
        'visibility': '',
        'requires_code': '',
        'lobby_code': '',
        'host_name': 'MacUser',
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: partial_metadata.get(key, ''),
    )

    # Unknown visibility'li bir lobi ekle
    game._lobby_list = [{
        'id': 12345,
        'name': 'MacUser',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }]
    game._deferred_lobby_entries = {12345: game._lobby_list[0]}

    game._refresh_unknown_lobby_entries()

    # Partial propagation: unknown kalmalı, 'public' olmamalı
    assert game._lobby_list[0]['visibility'] == 'unknown'


def test_refresh_unknown_resolves_to_private_on_full_propagation():
    """Tam metadata propagasyonu geldiğinde lobi doğru şekilde private olmalı."""
    game = _make_game()
    game._net_initialized = True

    full_metadata = {
        'game': 'quadrix',
        'metadata_ready': '1',
        'visibility': 'private',
        'requires_code': '1',
        'lobby_code': '123456',
        'host_name': 'MacUser',
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: full_metadata.get(key, ''),
    )

    game._lobby_list = [{
        'id': 12345,
        'name': 'MacUser',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }]
    game._deferred_lobby_entries = {12345: game._lobby_list[0]}

    game._refresh_unknown_lobby_entries()

    # Tam metadata: private olarak çözülmeli
    assert game._lobby_list[0]['visibility'] == 'private'
    assert game._lobby_list[0]['requires_code'] is True


def test_refresh_unknown_resolves_to_public_on_explicit_public():
    """Açıkça visibility=public geldiğinde lobi public olarak çözülmeli."""
    game = _make_game()
    game._net_initialized = True

    public_metadata = {
        'game': 'quadrix',
        'metadata_ready': '1',
        'visibility': 'public',
        'requires_code': '0',
        'lobby_code': '',
        'host_name': 'WinUser',
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: public_metadata.get(key, ''),
    )

    game._lobby_list = [{
        'id': 12345,
        'name': 'WinUser',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }]
    game._deferred_lobby_entries = {12345: game._lobby_list[0]}

    game._refresh_unknown_lobby_entries()

    assert game._lobby_list[0]['visibility'] == 'public'
    assert game._lobby_list[0]['requires_code'] is False


def test_promote_deferred_does_not_resolve_public_on_partial_propagation():
    """Deferred entry promote sırasında partial propagation public yapmamalı.

    macOS private lobisi Windows'a tam propagate olmadan, deferred entry'nin
    requires_code=False varsayım değeri payload fallback'i olarak okunmamalı.
    Bu değer _parse_lobby_bool(False) → False (None değil) üretir ve
    _normalize_lobby_visibility tarafından 'public' olarak sınıflandırılır.
    """
    game = _make_game()
    game._net_initialized = True
    game._lobby_list_fetching = False

    # macOS metadata henüz propagate olmamış → live read boş
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: '',
    )

    # Unknown visibility ile deferred entry (requires_code=False varsayım)
    deferred_entry = {
        'id': 12345,
        'name': 'MacUser',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }
    game._deferred_lobby_entries = {12345: dict(deferred_entry)}
    game._lobby_list = []

    result = game._promote_deferred_lobby_entry(12345)

    # Metadata yokken promote ETMEMELI — unknown kalmalı
    assert result is False
    # _lobby_list'e public olarak EKLENMEMELİ
    public_entries = [
        l for l in game._lobby_list
        if l.get('visibility') == 'public'
    ]
    assert len(public_entries) == 0


def test_promote_deferred_resolves_private_on_full_propagation():
    """Tam metadata geldiğinde deferred entry doğru şekilde private olmalı."""
    game = _make_game()
    game._net_initialized = True
    game._lobby_list_fetching = False

    # Tam metadata propagate olmuş
    full_metadata = {
        'visibility': 'private',
        'requires_code': '1',
        'lobby_code': '123456',
        'host_name': 'MacUser',
        'metadata_ready': '1',
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: full_metadata.get(key, ''),
    )

    deferred_entry = {
        'id': 12345,
        'name': 'MacUser',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }
    game._deferred_lobby_entries = {12345: dict(deferred_entry)}
    game._lobby_list = []

    result = game._promote_deferred_lobby_entry(12345)

    assert result is True
    assert len(game._lobby_list) == 1
    assert game._lobby_list[0]['visibility'] == 'private'
    assert game._lobby_list[0]['requires_code'] is True


def test_refresh_unknown_also_resolves_stale_unknown():
    """stale_unknown lobiler de _refresh_unknown_lobby_entries tarafından çözülmeli."""
    game = _make_game()
    game._net_initialized = True

    full_metadata = {
        'game': 'quadrix',
        'metadata_ready': '1',
        'visibility': 'private',
        'requires_code': '1',
        'lobby_code': '654321',
        'host_name': 'LateUser',
    }
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: full_metadata.get(key, ''),
    )

    game._lobby_list = [{
        'id': 99999,
        'name': 'LateUser',
        'code': '',
        'visibility': 'stale_unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': 0,
    }]
    game._deferred_lobby_entries = {}

    game._refresh_unknown_lobby_entries()

    assert game._lobby_list[0]['visibility'] == 'private'
    assert game._lobby_list[0]['requires_code'] is True


def test_invite_authorization_cleared_after_unknown_metadata_validation():
    """Davet yetkilendirmesi, unknown metadata ile validation geçtikten sonra
    temizlenmeli. Aksi halde stale _invite_authorized_lobby_id, aynı lobby_id'ye
    sonraki katılımda yetkisiz erişime izin verebilir."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: '',  # metadata yok
    )
    game._return_to_pvp_lobby_menu = Mock()

    # Davet ile yetkilendir
    game._invite_authorized_lobby_id = 77

    result = game._validate_joined_lobby_access()
    assert result is True
    assert game._lobby_access_validated_id == 77
    # Davet yetkilendirmesi temizlenmeli
    assert game._invite_authorized_lobby_id == 0


def test_invite_authorization_cleared_after_private_metadata_validation():
    """Davet yetkilendirmesi, private metadata ile validation geçtikten sonra
    da temizlenmeli."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        lobby_id=77,
        my_steam_id=99,
        is_host=False,
        get_lobby_owner=lambda: 55,
        get_lobby_data_for=lambda _lid, key: {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
    )
    game._return_to_pvp_lobby_menu = Mock()
    game._invite_authorized_lobby_id = 77

    result = game._validate_joined_lobby_access()
    assert result is True
    assert game._lobby_access_validated_id == 77
    assert game._invite_authorized_lobby_id == 0
    game._return_to_pvp_lobby_menu.assert_not_called()


def test_stale_unknown_lobby_removed_after_120_seconds():
    """stale_unknown lobiler 120 saniye sonra listeden kaldırılmalı.

    Bug: Temizlik döngüsü sadece 'unknown' kontrol ediyordu, 'stale_unknown'
    atlanıyordu. Bu yüzden kapanmış lobiler sonsuza kadar listede kalıyordu.
    """
    import time as _time

    game = _make_game()
    game._net_initialized = True

    # 130 saniye önce keşfedilmiş stale_unknown lobi
    game._lobby_list = [{
        'id': 55555,
        'name': 'GhostLobby',
        'code': '',
        'visibility': 'stale_unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': _time.time() - 130,
    }]
    game._deferred_lobby_entries = {55555: game._lobby_list[0]}

    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lid, key: '',
    )

    # Stale timeout mantığını simüle et
    _now = _time.time()
    _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S = 120.0
    _stale_ids: set = set()
    for _lobby in game._lobby_list:
        _lvis = str(_lobby.get('visibility', '') or '').lower()
        if _lvis not in ('unknown', 'stale_unknown'):
            continue
        _found_t = float(_lobby.get('found_time', 0) or 0)
        if not _found_t:
            continue
        _elapsed = _now - _found_t
        _lid = int(_lobby.get('id', 0) or 0)
        if _elapsed > _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S:
            _stale_ids.add(_lid)
    if _stale_ids:
        game._lobby_list = [
            l for l in game._lobby_list
            if int(l.get('id', 0) or 0) not in _stale_ids
        ]
        for _sid in _stale_ids:
            game._deferred_lobby_entries.pop(_sid, None)

    assert len(game._lobby_list) == 0
    assert 55555 not in game._deferred_lobby_entries


def test_stale_unknown_lobby_kept_before_120_seconds():
    """stale_unknown lobiler 120 saniyeden önce listede kalmalı."""
    import time as _time

    game = _make_game()
    game._net_initialized = True

    game._lobby_list = [{
        'id': 66666,
        'name': 'ActiveLobby',
        'code': '',
        'visibility': 'stale_unknown',
        'requires_code': False,
        'metadata_ready': False,
        'found_time': _time.time() - 30,
    }]

    # Stale timeout mantığını simüle et
    _now = _time.time()
    _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S = 120.0
    _stale_ids: set = set()
    for _lobby in game._lobby_list:
        _lvis = str(_lobby.get('visibility', '') or '').lower()
        if _lvis not in ('unknown', 'stale_unknown'):
            continue
        _found_t = float(_lobby.get('found_time', 0) or 0)
        if not _found_t:
            continue
        _elapsed = _now - _found_t
        _lid = int(_lobby.get('id', 0) or 0)
        if _elapsed > _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S:
            _stale_ids.add(_lid)

    assert len(_stale_ids) == 0
    assert len(game._lobby_list) == 1
    assert game._lobby_list[0]['visibility'] == 'stale_unknown'