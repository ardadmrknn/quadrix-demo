"""Cross-platform lobi metadata propagasyon testleri.

Bu testler şu senaryoları doğrular:
- macOS'ta açılan özel lobi Windows'ta sağlıklı görünür
- Windows'ta açılan özel lobi macOS'ta sağlıklı görünür
- Herkese açık lobiler çapraz platformda doğru tanınır
- Özel lobi kodları çapraz platformda çalışır
- metadata_ready sinyalizasyonu ve race condition koruması

Testler gerçek C++ bridge veya Steam API gerektirmez; sadece
metadata akışını ve parsing mantığını doğrular.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import types
from unittest.mock import Mock

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as pvp_module
from steam_networking import NetEvent, generate_lobby_code


# ===========================================================================
# Helpers
# ===========================================================================

def _make_pvp_game():
    game = pvp_module.OnlinePvPGame.__new__(pvp_module.OnlinePvPGame)
    game._pending_lobby_list = []
    game._lobby_list = []
    game._lobby_list_scroll = 0
    game._deferred_lobby_entries = {}
    game._lobby_list_fetching = False
    game._lobby_list_fetch_start_time = 0
    game._lobby_list_filter = 'all'
    game._net_initialized = True
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
    return game


def _build_cpp_payload(
    host_name: str = 'TestHost',
    visibility: str | None = None,
    requires_code: bool | None = None,
    lobby_code: str = '',
    metadata_ready: bool | None = None,
    members: int = 1,
    max_members: int = 2,
) -> str:
    """C++ build_lobby_found_payload çıktısını simüle eder.

    None değerler JSON null olarak gönderilir (metadata henüz
    propague olmamış senaryolar).
    """
    def _json_val(val, is_string=False):
        if val is None:
            return 'null'
        if isinstance(val, bool):
            return 'true' if val else 'false'
        if is_string:
            return f'"{val}"'
        return str(val)

    return json.dumps({
        'members': members,
        'max_members': max_members,
        'host_name': host_name,
        'lobby_code': lobby_code,
        'visibility': visibility,
        'requires_code': requires_code,
        'metadata_ready': metadata_ready,
    })


def _make_live_data_reader(metadata: dict[str, str]):
    """get_lobby_data_for mock'u oluşturur — Steam cache'ini simüle eder."""
    def _reader(lobby_id, key):
        return metadata.get(key, '')
    return _reader


# ===========================================================================
# SENARYO 1: macOS'ta özel lobi → Windows'tan listeleme
# ===========================================================================

class TestMacOSPrivateLobbySeenFromWindows:
    """macOS host özel lobi oluşturur → Windows client lobi listesinde görür."""

    LOBBY_ID = 76561199000000001
    CODE = generate_lobby_code(76561199000000001)

    def test_immediate_payload_has_full_metadata(self):
        """macOS metadata hemen propague olursa Windows payload'tan doğru okur."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
        )

        payload = _build_cpp_payload(
            host_name='macOS-Host',
            visibility='private',
            requires_code=True,
            lobby_code=self.CODE,
            metadata_ready=True,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        assert len(game._pending_lobby_list) == 1
        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True
        assert entry['code'] == self.CODE
        assert entry['metadata_ready'] is True
        assert entry['name'] == 'macOS-Host'
        # Private → deferred lisjesine eklenmemeli
        assert self.LOBBY_ID not in game._deferred_lobby_entries

    def test_delayed_payload_metadata_null_live_read_resolves(self):
        """Payload'ta metadata null gelir, live read ile çözülür."""
        game = _make_pvp_game()
        # Steam cache'inde metadata var ama C++ payload'a yetişememiş
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
                'requires_code': '1',
                'lobby_code': self.CODE,
                'metadata_ready': '1',
                'host_name': 'macOS-Host',
            }),
        )

        payload = _build_cpp_payload(
            host_name='macOS-Host',
            visibility=None,  # metadata henüz propague olmamış
            requires_code=None,
            lobby_code='',
            metadata_ready=None,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        assert len(game._pending_lobby_list) == 1
        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True
        assert entry['code'] == self.CODE
        assert entry['metadata_ready'] is True

    def test_fully_delayed_metadata_stays_unknown_then_resolves(self):
        """Tüm metadata gecikmeli — unknown kalır, sonra lobby_data_updated ile çözülür."""
        game = _make_pvp_game()
        # İlk anda hiçbir metadata yok
        empty_reader = _make_live_data_reader({})
        game.net = types.SimpleNamespace(
            get_lobby_data_for=empty_reader,
        )

        payload = _build_cpp_payload(
            host_name='macOS-Host',
            visibility=None,
            requires_code=None,
            lobby_code='',
            metadata_ready=None,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        assert len(game._pending_lobby_list) == 1
        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'unknown'
        assert self.LOBBY_ID in game._deferred_lobby_entries

        # lobby_data_updated geldi — metadata artık hazır
        game.net = types.SimpleNamespace(
            lobby_id=0,
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
                'requires_code': '1',
                'lobby_code': self.CODE,
                'metadata_ready': '1',
                'host_name': 'macOS-Host',
            }),
        )

        update_payload = _build_cpp_payload(
            host_name='macOS-Host',
            visibility='private',
            requires_code=True,
            lobby_code=self.CODE,
            metadata_ready=True,
        )
        game._on_lobby_data_updated(
            NetEvent('lobby_data_updated', self.LOBBY_ID, update_payload))

        # Deferred entry promote edilmiş olmalı
        assert self.LOBBY_ID not in game._deferred_lobby_entries

    def test_code_join_works_with_delayed_metadata(self):
        """Kod ile arama: metadata gecikmeli bile olsa lobby_id derivation ile eşleşir."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
            join_lobby=Mock(),
        )

        # Tam tarama sonucu — metadata yok (None = bilinmiyor)
        game._pending_lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'macOS-Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': None,
            'metadata_ready': None,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game._deferred_lobby_entries = {self.LOBBY_ID: game._pending_lobby_list[0]}
        game._searching_by_code = True
        game._search_code = self.CODE

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        # lobby_id'den derive edilen kod eşleşmeli → join çağrılmalı
        game.net.join_lobby.assert_called_once_with(self.LOBBY_ID)


# ===========================================================================
# SENARYO 2: Windows'ta özel lobi → macOS'tan listeleme
# ===========================================================================

class TestWindowsPrivateLobbySeenFromMacOS:
    """Windows host özel lobi oluşturur → macOS client görmeli."""

    LOBBY_ID = 76561199000000002
    CODE = generate_lobby_code(76561199000000002)

    def test_full_metadata_in_payload(self):
        """Windows metadata hemen propague olursa macOS doğru okur."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
        )

        payload = _build_cpp_payload(
            host_name='Windows-Host',
            visibility='private',
            requires_code=True,
            lobby_code=self.CODE,
            metadata_ready=True,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True
        assert entry['code'] == self.CODE
        assert entry['name'] == 'Windows-Host'

    def test_partial_metadata_visibility_only(self):
        """Sadece visibility propague olmuş, requires_code ve lobby_code henüz yok."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
            }),
        )

        payload = _build_cpp_payload(
            host_name='Windows-Host',
            visibility='private',
            requires_code=None,
            lobby_code='',
            metadata_ready=None,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        # visibility=private → requires_code True olarak türetilmeli
        assert entry['requires_code'] is True

    def test_only_requires_code_propagated(self):
        """Sadece requires_code='1' gelmiş — visibility türetilmeli."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'requires_code': '1',
            }),
        )

        payload = _build_cpp_payload(
            host_name='Host',
            visibility=None,
            requires_code=True,
            lobby_code='',
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True

    def test_only_lobby_code_propagated(self):
        """Sadece lobby_code gelmiş — private olarak türetilmeli."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'lobby_code': self.CODE,
            }),
        )

        payload = _build_cpp_payload(
            host_name='Host',
            visibility=None,
            requires_code=None,
            lobby_code=self.CODE,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True
        assert entry['code'] == self.CODE


# ===========================================================================
# SENARYO 3: Herkese açık lobi çapraz platformda
# ===========================================================================

class TestPublicLobbyCrossPlatform:
    """Public lobi her iki platformda doğru görünmeli."""

    LOBBY_ID = 76561199000000003

    def test_public_lobby_full_metadata(self):
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
        )

        payload = _build_cpp_payload(
            host_name='PublicHost',
            visibility='public',
            requires_code=False,
            lobby_code='',
            metadata_ready=True,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'public'
        assert entry['requires_code'] is False
        assert entry['code'] == ''
        assert entry['metadata_ready'] is True

    def test_public_lobby_delayed_metadata_resolves_via_live_read(self):
        """Public lobi metadata gecikmeli — live read ile çözülür."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'public',
                'requires_code': '0',
                'metadata_ready': '1',
            }),
        )

        payload = _build_cpp_payload(
            host_name='PublicHost',
            visibility=None,
            requires_code=None,
            metadata_ready=None,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'public'
        assert entry['requires_code'] is False

    def test_public_lobby_not_filtered_when_filter_is_public(self):
        """'public' filtre — public lobiler görünür kalmalı."""
        game = _make_pvp_game()
        game._lobby_list_filter = 'public'
        game._pending_lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'PublicHost',
            'code': '',
            'visibility': 'public',
            'requires_code': False,
            'metadata_ready': True,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'public',
                'requires_code': '0',
                'metadata_ready': '1',
            }),
            join_lobby=Mock(),
        )

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        assert len(game._lobby_list) == 1
        assert game._lobby_list[0]['visibility'] == 'public'

    def test_private_lobby_filtered_when_filter_is_public(self):
        """'public' filtre — private lobiler filtrelenmeli."""
        game = _make_pvp_game()
        game._lobby_list_filter = 'public'
        game._pending_lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'PrivateHost',
            'code': '123456',
            'visibility': 'private',
            'requires_code': True,
            'metadata_ready': True,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
                'requires_code': '1',
                'metadata_ready': '1',
            }),
            join_lobby=Mock(),
        )

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        assert len(game._lobby_list) == 0


# ===========================================================================
# SENARYO 4: metadata_ready race condition koruması
# ===========================================================================

class TestMetadataReadyRaceProtection:
    """metadata_ready=0 sinyalizasyonu ile race condition önlenir."""

    LOBBY_ID = 76561199000000004
    CODE = generate_lobby_code(76561199000000004)

    def test_metadata_ready_0_keeps_lobby_as_unknown(self):
        """metadata_ready=0 + başka metadata yok → unknown kalır."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'game': 'quadrix',
                'metadata_ready': '0',
            }),
        )

        payload = _build_cpp_payload(
            host_name='RaceHost',
            visibility=None,
            requires_code=None,
            metadata_ready=False,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        assert entry['visibility'] == 'unknown'
        assert entry['metadata_ready'] is False

    def test_metadata_ready_0_with_visibility_still_resolves(self):
        """metadata_ready=0 ama visibility açıkça gelmiş → resolve et."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
        )

        payload = _build_cpp_payload(
            host_name='RaceHost',
            visibility='private',
            requires_code=True,
            lobby_code=self.CODE,
            metadata_ready=False,
        )
        game._on_lobby_found(NetEvent('lobby_found', self.LOBBY_ID, payload))

        entry = game._pending_lobby_list[0]
        # visibility açıkça 'private' gelmiş → metadata_ready=0 olsa bile güven
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True

    def test_on_lobby_created_writes_metadata_ready_0_then_1(self):
        """Private lobi oluşturulduğunda metadata_ready=0 → alanlar → 1 sırası korunur."""
        game = _make_pvp_game()
        game.online_state = None
        game._lobby_presence_probe_timer = 0.0
        game._lobby_id_str = ''
        game._lobby_code = ''
        game._creating_public_lobby = False
        game._invite_after_lobby = False

        set_calls = []
        game.net = types.SimpleNamespace(
            set_lobby_data=lambda key, value: set_calls.append((key, value)),
            invite_friend=Mock(),
        )

        game._on_lobby_created(NetEvent('lobby_created', self.LOBBY_ID, ''))

        # İlk çağrı metadata_ready=0 olmalı
        assert set_calls[0] == ('metadata_ready', '0')
        # Son çağrı metadata_ready=1 olmalı
        assert set_calls[-1] == ('metadata_ready', '1')
        # Arada visibility ve requires_code yazılmış olmalı
        keys_written = [k for k, v in set_calls]
        assert 'visibility' in keys_written
        assert 'requires_code' in keys_written
        # metadata_ready=0, metadata_ready=1 sırası doğru
        mr_indices = [i for i, (k, v) in enumerate(set_calls) if k == 'metadata_ready']
        assert len(mr_indices) == 2
        assert set_calls[mr_indices[0]][1] == '0'
        assert set_calls[mr_indices[1]][1] == '1'
        # visibility ve requires_code, iki metadata_ready arasında olmalı
        vis_idx = keys_written.index('visibility')
        req_idx = keys_written.index('requires_code')
        assert mr_indices[0] < vis_idx < mr_indices[1]
        assert mr_indices[0] < req_idx < mr_indices[1]

    def test_on_lobby_created_public_writes_metadata_ready_0_then_1(self):
        """Public lobi oluşturulduğunda da aynı metadata_ready sırası."""
        game = _make_pvp_game()
        game.online_state = None
        game._lobby_presence_probe_timer = 0.0
        game._lobby_id_str = ''
        game._lobby_code = ''
        game._creating_public_lobby = True
        game._invite_after_lobby = False

        set_calls = []
        game.net = types.SimpleNamespace(
            set_lobby_data=lambda key, value: set_calls.append((key, value)),
            invite_friend=Mock(),
        )

        game._on_lobby_created(NetEvent('lobby_created', self.LOBBY_ID, ''))

        assert set_calls[0] == ('metadata_ready', '0')
        assert set_calls[-1] == ('metadata_ready', '1')
        vis_val = next(v for k, v in set_calls if k == 'visibility')
        assert vis_val == 'public'
        req_val = next(v for k, v in set_calls if k == 'requires_code')
        assert req_val == '0'


# ===========================================================================
# SENARYO 5: Özel lobi kodu çapraz platform eşleşme
# ===========================================================================

class TestPrivateLobbyCodeCrossPlatform:
    """Özel lobi kodu çapraz platformda doğru çalışır."""

    LOBBY_ID = 76561199000000005
    CODE = generate_lobby_code(76561199000000005)

    def test_code_derived_from_lobby_id_matches_host_code(self):
        """Karşı platform lobby_id'den aynı kodu derive edebilir."""
        # Host tarafı
        host_code = generate_lobby_code(self.LOBBY_ID)
        # Client tarafı — aynı lobby_id'den derive
        client_code = generate_lobby_code(self.LOBBY_ID)
        assert host_code == client_code
        assert len(host_code) == 6
        assert host_code.isdigit()

    def test_code_search_matches_with_only_lobby_code_in_payload(self):
        """Payload sadece lobby_code içerir → kod aramasında eşleşir."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
            join_lobby=Mock(),
        )

        game._pending_lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': self.CODE,
            'visibility': 'private',
            'requires_code': True,
            'metadata_ready': True,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game._searching_by_code = True
        game._search_code = self.CODE

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        game.net.join_lobby.assert_called_once_with(self.LOBBY_ID)

    def test_code_search_derives_code_from_lobby_id_when_metadata_missing(self):
        """Metadata tamamen yok — lobby_id derivation ile eşleşir."""
        game = _make_pvp_game()
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
            join_lobby=Mock(),
        )

        game._pending_lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': None,
            'metadata_ready': None,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game._deferred_lobby_entries = {self.LOBBY_ID: game._pending_lobby_list[0]}
        game._searching_by_code = True
        game._search_code = self.CODE

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        game.net.join_lobby.assert_called_once_with(self.LOBBY_ID)

    def test_code_search_retry_full_scan_on_first_failure(self):
        """İlk kod araması başarısız → retry timer kurulur, full scan flag set edilir."""
        game = _make_pvp_game()
        game._pending_lobby_list = []
        game._searching_by_code = True
        game._search_code = self.CODE
        game._code_search_retry_count = 0
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
            join_lobby=Mock(),
        )

        game._on_lobby_list_complete(NetEvent('lobby_list_complete', 0, ''))

        # Retry kurulmuş olmalı
        assert game._code_search_retry_timer > 0
        assert game._code_search_retry_code == self.CODE
        assert game._code_search_retry_use_full_scan is True
        game.net.join_lobby.assert_not_called()


# ===========================================================================
# SENARYO 6: _refresh_unknown_lobby_entries çapraz platform
# ===========================================================================

class TestRefreshUnknownLobbyEntriesCrossPlatform:
    """Unknown lobiler refresh ile doğru şekilde çözülür."""

    LOBBY_ID = 76561199000000006
    CODE = generate_lobby_code(76561199000000006)

    def test_refresh_resolves_unknown_with_live_visibility(self):
        """Live read'de visibility gelirse unknown → private çözülür."""
        game = _make_pvp_game()
        game._lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
                'requires_code': '1',
                'lobby_code': self.CODE,
                'metadata_ready': '1',
                'host_name': 'Host',
            }),
        )

        game._refresh_unknown_lobby_entries()

        entry = game._lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True
        assert entry['code'] == self.CODE

    def test_refresh_re_requests_lobby_data_while_unknown_persists(self):
        """Canlı metadata hala boşsa bridge üzerinden aktif refresh istemelidir."""
        game = _make_pvp_game()
        game._UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S = 60.0
        game._lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        request_lobby_data = Mock(return_value=True)
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({}),
            request_lobby_data=request_lobby_data,
        )

        game._refresh_unknown_lobby_entries()
        game._refresh_unknown_lobby_entries()

        request_lobby_data.assert_called_once_with(self.LOBBY_ID)
        entry = game._lobby_list[0]
        assert entry['visibility'] == 'unknown'
        assert entry['metadata_ready'] is False

    def test_refresh_resolves_unknown_with_only_lobby_code(self):
        """Sadece lobby_code gelmiş → private türetilir."""
        game = _make_pvp_game()
        game._lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'lobby_code': self.CODE,
                'game': 'quadrix',
            }),
        )

        game._refresh_unknown_lobby_entries()

        entry = game._lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True

    def test_refresh_resolves_with_metadata_ready_1_and_public_visibility(self):
        """metadata_ready=1 + visibility=public → public tanınır."""
        game = _make_pvp_game()
        game._lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'public',
                'requires_code': '0',
                'metadata_ready': '1',
                'game': 'quadrix',
                'host_name': 'PublicHost',
            }),
        )

        game._refresh_unknown_lobby_entries()

        entry = game._lobby_list[0]
        assert entry['visibility'] == 'public'
        assert entry['requires_code'] is False

    def test_refresh_resolves_with_metadata_ready_1_private_no_lobby_code(self):
        """metadata_ready=1 + visibility=private ama lobby_code henüz yok.

        Bu durum cross-platform'da olabilir: Python metadata_ready=1'i
        yazmış ama lobby_code henüz propague olmamış. Visibility private
        olarak tanınmalı, kod lobby_id'den türetilmeli.
        """
        game = _make_pvp_game()
        game._lobby_list = [{
            'id': self.LOBBY_ID,
            'name': 'Host',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
            'members': 1,
            'max_members': 2,
            'found_time': time.time(),
        }]
        game.net = types.SimpleNamespace(
            get_lobby_data_for=_make_live_data_reader({
                'visibility': 'private',
                'requires_code': '1',
                'metadata_ready': '1',
                'game': 'quadrix',
            }),
        )

        game._refresh_unknown_lobby_entries()

        entry = game._lobby_list[0]
        assert entry['visibility'] == 'private'
        assert entry['requires_code'] is True


# ===========================================================================
# SENARYO 7: _normalize_lobby_visibility edge cases
# ===========================================================================

class TestNormalizeLobbyVisibilityEdgeCases:
    """Metadata parsing uç durumları."""

    def test_empty_string_values_all_unknown(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            '', '', '', None)
        assert vis == 'unknown'

    def test_metadata_ready_false_no_explicit_metadata(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            '', '', '', False)
        assert vis == 'unknown'
        assert ready is False

    def test_metadata_ready_false_with_explicit_visibility(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            'private', '', '', False)
        assert vis == 'private'
        assert req is True
        assert ready is True

    def test_requires_code_1_infers_private(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            '', True, '', None)
        assert vis == 'private'
        assert req is True

    def test_requires_code_0_infers_public(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            '', False, '', None)
        assert vis == 'public'
        assert req is False

    def test_lobby_code_present_infers_private(self):
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            '', '', '123456', None)
        assert vis == 'private'
        assert req is True
        assert code == '123456'

    def test_public_visibility_overrides_requires_code_true(self):
        """visibility=public + requires_code=True → hâlâ private (requires_code kazanır)."""
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            'public', True, '', None)
        assert vis == 'private'
        assert req is True

    def test_json_null_parsed_as_none(self):
        """JSON null → Python None → _parse_lobby_bool None → metadata eksik."""
        vis, req, code, ready = pvp_module._normalize_lobby_visibility(
            None, None, '', None)
        assert vis == 'unknown'


# ===========================================================================
# SENARYO 8: Coop metadata format tutarlılığı
# ===========================================================================

class TestCoopMetadataFormatConsistency:
    """online_coop_game.py metadata formatı C++ bridge ile tutarlı."""

    def test_coop_requires_code_uses_numeric_format(self):
        """requires_code '1'/'0' formatında olmalı (C++ uyumu)."""
        src_path = ROOT_DIR / 'src' / 'online_coop_game.py'
        content = src_path.read_text(encoding='utf-8')

        # Coop metadata'da requires_code '1' veya '0' olarak yazılmalı.
        # 'true'/'false' kullanılmamalı — C++ bridge == "1" kontrol eder.
        # Ternary expression: '1' if ... else '0' gibi bir ifade olabilir.
        assert "'requires_code', '1'" in content or "'1' if" in content
        assert "'0'" in content  # '0' ternary else dalında
        # Eski format kullanılmamalı
        assert "requires_code', 'true'" not in content
        assert "requires_code', 'false'" not in content

    def test_coop_metadata_ready_uses_numeric_format(self):
        """metadata_ready '1' formatında olmalı."""
        src_path = ROOT_DIR / 'src' / 'online_coop_game.py'
        content = src_path.read_text(encoding='utf-8')

        assert "'metadata_ready', '1'" in content or '"metadata_ready", "1"' in content
        # Eski format kullanılmamalı
        assert "metadata_ready', 'true'" not in content

    def test_coop_writes_metadata_ready_0_before_sensitive_fields(self):
        """Coop da metadata_ready=0 race protection kullanmalı."""
        src_path = ROOT_DIR / 'src' / 'online_coop_game.py'
        content = src_path.read_text(encoding='utf-8')

        assert "'metadata_ready', '0'" in content or '"metadata_ready", "0"' in content


# ===========================================================================
# SENARYO 9: C++ bridge metadata_ready check tutarlılığı
# ===========================================================================

class TestCppBridgeMetadataConsistency:
    """C++ bridge kaynak kodu metadata kontrollerinin tutarlılığı."""

    CPP_PATH = ROOT_DIR / 'steamworks' / 'steam_net_bridge' / 'steam_net_bridge.cpp'

    def test_cpp_on_lobby_created_writes_metadata_ready_0(self):
        """C++ OnLobbyCreated metadata_ready=0 yazar (Python'a bırakır)."""
        content = self.CPP_PATH.read_text(encoding='utf-8')
        assert 'm_matchmaking->SetLobbyData(m_currentLobby, "metadata_ready", "0")' in content

    def test_cpp_does_not_write_visibility_on_lobby_created(self):
        """C++ OnLobbyCreated visibility/requires_code/lobby_code YAZMAZ."""
        content = self.CPP_PATH.read_text(encoding='utf-8')
        # OnLobbyCreated fonksiyonunun gövdesini bul
        start = content.find('void OnLobbyCreated(LobbyCreated_t')
        end = content.find('void OnLobbyEnter(', start)
        on_created_body = content[start:end]

        # Bu alanlar OnLobbyCreated'da yazılmamalı
        assert 'SetLobbyData(m_currentLobby, "visibility"' not in on_created_body
        assert 'SetLobbyData(m_currentLobby, "requires_code"' not in on_created_body
        assert 'SetLobbyData(m_currentLobby, "lobby_code"' not in on_created_body

    def test_cpp_is_metadata_ready_checks_string_1(self):
        """is_lobby_metadata_ready_for_listing == '1' kontrolü yapar."""
        content = self.CPP_PATH.read_text(encoding='utf-8')
        assert 'std::string(metadataReadyRaw) == "1"' in content

    def test_cpp_build_payload_handles_null_metadata_gracefully(self):
        """build_lobby_found_payload hiçbir metadata yokken null JSON üretir."""
        content = self.CPP_PATH.read_text(encoding='utf-8')
        assert 'visibilityJson = "null"' in content
        assert 'requiresCodeJson = "null"' in content
