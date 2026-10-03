"""DUZ-012: Online PvP hata sınıflandırması ve yapılandırılmış log regresyonları.

Iade kartı (Iade_Duzeltme_Plani.md DUZ-012) kapsamı: yedi hata sınıfının her
biri tek satır, makine-taranabilir olay loguyla ayrıştırılır; kullanıcı
home/dizin yapısı loglanmaz; pending_flush READY başarısızlığı edge-triggered
loglanır (per-frame yasağı); pump pause/resume ve native cleanup sırası ile
dönüş/mesaj sözleşmeleri DEĞİŞMEZ.

Sınıf kapsamı:
  steam_client_offline    -> test_launch_status_logs_steam_client_offline
  steam_sdk_missing       -> test_launch_status_logs_sdk_import_failure
  bridge_import_failed    -> launch_status modül/kullanılamıyor + köprü arama
  bridge_init_failed      -> native ret/istisna + oyun içi retry toparlanması
  tick_transient_error    -> 5 ardışık hata eşiği ve networking_disabled
  native_cleanup_failed   -> shutdown/leave_lobby/init-cleanup yolları
  unexpected_error        -> beklenmeyen programlama istisnaları
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import steam_networking  # noqa: E402  (modül importu yan etkisiz — köprü lazy)


@pytest.fixture
def main_functions():
    # Main importu ekran/profil/Steam yan etkileri taşır. Gerçek fonksiyonların
    # AST'sini bağımsız namespace'te çalıştır; algoritmayı yeniden yazma.
    tree = ast.parse((SRC / 'main.py').read_text(encoding='utf-8'))
    names = {'_online_pvp_launch_status', '_create_online_pvp_game'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {'t': lambda key, default=None, **kw: default or key, 'OnlinePvPGame': Mock()}
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SRC / 'main.py'), 'exec'), namespace)
    return namespace


def _steam_stub(ready: bool):
    return types.SimpleNamespace(is_available=lambda: ready)


# ---------------------------------------------------------------------------
#  A) _online_pvp_launch_status — başlatma güvenliği sınıfları
# ---------------------------------------------------------------------------

def test_launch_status_logs_steam_client_offline(main_functions, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'steam_integration', _steam_stub(False))
    ok, message = main_functions['_online_pvp_launch_status']()
    assert not ok
    assert 'Steam' in message
    assert '[OnlinePvP][WARN] event=steam_client_offline detail=is_available=False' in capsys.readouterr().out


def test_launch_status_logs_sdk_import_failure(main_functions, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'steam_integration', None)
    ok, message = main_functions['_online_pvp_launch_status']()
    assert not ok
    assert 'Steam' in message
    assert '[OnlinePvP][WARN] event=steam_sdk_missing' in capsys.readouterr().out


def test_launch_status_survives_missing_networking_module(main_functions, monkeypatch, capsys):
    # steam_networking'in kendisi yüklenemiyorsa fonksiyon PATLAMAMALI:
    # sınıflandırma yardımcıları pasifleşir, köprü sınıfı ikinci önkoşul
    # bloğunda yakalanır, dönüş sözleşmesi eski kodla aynı kalır.
    monkeypatch.setitem(sys.modules, 'steam_integration', _steam_stub(True))
    monkeypatch.setitem(sys.modules, 'steam_networking', None)
    ok, message = main_functions['_online_pvp_launch_status']()
    assert not ok
    assert 'köprü' in message
    assert '[OnlinePvP][WARN] event=bridge_import_failed' in capsys.readouterr().out


def test_launch_status_logs_bridge_unavailable_with_fallback_constants(main_functions, monkeypatch, capsys):
    # Stub sabit taşımadığında fonksiyon try/except fallback değerlerine
    # düşer — sınıflandırma logu yine yazılır (regresyon: fonksiyon-başı
    # import'un korumasız olduğu düzene dönüş).
    monkeypatch.setitem(sys.modules, 'steam_integration', _steam_stub(True))
    monkeypatch.setitem(sys.modules, 'steam_networking', types.SimpleNamespace(
        SteamNetworking=lambda: types.SimpleNamespace(available=False)))
    ok, message = main_functions['_online_pvp_launch_status']()
    assert not ok
    assert 'köprü' in message
    out = capsys.readouterr().out
    assert '[OnlinePvP][WARN] event=bridge_import_failed detail=available=False' in out
    assert 'C:\\' not in out and '/Users/' not in out


def test_launch_status_silent_when_all_prerequisites_ready(main_functions, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'steam_integration', _steam_stub(True))
    monkeypatch.setitem(sys.modules, 'steam_networking', types.SimpleNamespace(
        SteamNetworking=lambda: types.SimpleNamespace(available=True),
        log_online_pvp_event=steam_networking.log_online_pvp_event,
        ONLINE_PVP_ERR_BRIDGE_IMPORT_FAILED=steam_networking.ONLINE_PVP_ERR_BRIDGE_IMPORT_FAILED,
        ONLINE_PVP_ERR_STEAM_CLIENT_OFFLINE=steam_networking.ONLINE_PVP_ERR_STEAM_CLIENT_OFFLINE,
        ONLINE_PVP_ERR_STEAM_SDK_MISSING=steam_networking.ONLINE_PVP_ERR_STEAM_SDK_MISSING,
    ))
    assert main_functions['_online_pvp_launch_status']() == (True, '')
    assert capsys.readouterr().out == ''


# ---------------------------------------------------------------------------
#  B) _create_online_pvp_game — exception yolları
# ---------------------------------------------------------------------------

def test_create_game_logs_unexpected_on_constructor_failure(main_functions, capsys):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    main_functions['OnlinePvPGame'].side_effect = RuntimeError('constructor failed')
    on_failure = Mock()
    game, message = main_functions['_create_online_pvp_game'](on_failure=on_failure)
    assert game is None
    assert message == 'online_pvp_launch_failed'
    on_failure.assert_called_once()
    assert '[OnlinePvP][ERROR] event=unexpected_error detail=RuntimeError' in capsys.readouterr().out


def test_create_game_logs_native_cleanup_failure_separately(main_functions, capsys):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    result = types.SimpleNamespace(
        _init_networking=Mock(side_effect=RuntimeError('network init')),
        _cleanup=Mock(side_effect=RuntimeError('cleanup failed')))
    main_functions['OnlinePvPGame'].return_value = result
    on_failure = Mock()
    game, message = main_functions['_create_online_pvp_game'](on_failure=on_failure)
    assert game is None
    assert message == 'online_pvp_launch_failed'
    on_failure.assert_called_once()
    out = capsys.readouterr().out
    assert '[OnlinePvP][ERROR] event=unexpected_error detail=RuntimeError' in out
    assert '[OnlinePvP][ERROR] event=native_cleanup_failed detail=create cleanup' in out


def test_create_game_transient_init_false_returns_game_and_skips_on_failure(main_functions, capsys):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    result = types.SimpleNamespace(_init_networking=Mock(return_value=False))
    main_functions['OnlinePvPGame'].return_value = result
    on_failure = Mock()
    game, message = main_functions['_create_online_pvp_game'](on_failure=on_failure)
    assert game is result
    assert message == ''
    on_failure.assert_not_called()
    assert '[OnlinePvP][INFO] event=bridge_init_failed' in capsys.readouterr().out


def test_create_game_needs_no_networking_import_when_preflight_fails(main_functions, monkeypatch):
    # Preflight başarısızsa steam_networking sabitleri HİÇ çözülmemelidir
    # (regresyon: fonksiyon-başı korumasız import patlayıp menü aksiyonunu
    # bozabilirdi).
    main_functions['_online_pvp_launch_status'] = lambda: (False, 'offline')
    monkeypatch.setitem(sys.modules, 'steam_networking', None)
    assert main_functions['_create_online_pvp_game'](on_failure=Mock()) == (None, 'offline')


# ---------------------------------------------------------------------------
#  C) steam_networking — gerçek modülün sınıflı logları
# ---------------------------------------------------------------------------

def test_bridge_import_failure_logs_without_user_paths(monkeypatch, tmp_path, capsys):
    fake_root = tmp_path / 'fake_root'
    (fake_root / 'local_artifacts' / 'bridge').mkdir(parents=True)
    # _try_import_bridge modül-global köprü durumunu yazar — teardown restore
    # edilsin diye monkeypatch üzerinden snapshot'lanır.
    monkeypatch.setattr(steam_networking, '_bridge', None)
    monkeypatch.setattr(steam_networking, '_bridge_available', False)
    monkeypatch.setattr(steam_networking, '_bridge_import_attempted', False)
    monkeypatch.setattr(steam_networking, '_get_bridge_search_roots', lambda: [str(fake_root)])
    monkeypatch.setattr(steam_networking, '_get_bridge_candidate_dirs',
                        lambda: [str(fake_root / 'local_artifacts' / 'bridge')])
    monkeypatch.setattr(steam_networking, '_get_bridge_dll_search_dirs',
                        lambda: [str(fake_root / 'dll' / 'win64')])
    monkeypatch.setitem(sys.modules, 'steam_net_bridge', None)
    sys_path_snapshot = sys.path[:]
    dll_dirs_snapshot = list(steam_networking._dll_dirs)
    try:
        assert steam_networking._try_import_bridge() is False
    finally:
        sys.path[:] = sys_path_snapshot
        steam_networking._dll_dirs[:] = dll_dirs_snapshot
    out = capsys.readouterr().out
    assert '[OnlinePvP][ERROR] event=bridge_import_failed' in out
    assert 'Denenen dizinler' in out
    # Teşhis bağlamı tail bileşenleriyle korunur, home/dizin yapısı ifşa olmaz.
    assert 'local_artifacts/bridge' in out
    for forbidden in (str(tmp_path), 'arda demirkan', 'Desktop', 'AppData', 'C:\\', 'C:/'):
        assert forbidden not in out


def test_init_logs_bridge_missing_when_import_never_succeeded(monkeypatch, capsys):
    monkeypatch.setattr(steam_networking, '_bridge_available', False)
    monkeypatch.setattr(steam_networking, '_bridge_import_attempted', True)
    net = steam_networking.SteamNetworking()
    assert net.init() is False
    assert '[OnlinePvP][WARN] event=bridge_import_failed detail=init oncesi bridge yok' in capsys.readouterr().out


def test_init_logs_native_reject_class(monkeypatch, capsys):
    fake_bridge = types.SimpleNamespace(
        SteamNetBridge=lambda: types.SimpleNamespace(init=lambda: False, get_my_steam_id=lambda: 0))
    monkeypatch.setattr(steam_networking, '_bridge', fake_bridge)
    monkeypatch.setattr(steam_networking, '_bridge_available', True)
    monkeypatch.setattr(steam_networking, '_bridge_import_attempted', True)
    net = steam_networking.SteamNetworking()
    assert net.init() is False
    assert net._bridge_instance is None
    assert '[OnlinePvP][WARN] event=bridge_init_failed detail=native init False' in capsys.readouterr().out


def test_init_logs_ctor_exception_class(monkeypatch, capsys):
    def _raising_ctor():
        raise ValueError('ctor boom')

    monkeypatch.setattr(steam_networking, '_bridge', types.SimpleNamespace(SteamNetBridge=_raising_ctor))
    monkeypatch.setattr(steam_networking, '_bridge_available', True)
    monkeypatch.setattr(steam_networking, '_bridge_import_attempted', True)
    net = steam_networking.SteamNetworking()
    assert net.init() is False
    assert net._bridge_instance is None
    assert '[OnlinePvP][ERROR] event=bridge_init_failed detail=ValueError' in capsys.readouterr().out


def test_tick_transient_errors_log_each_and_disable_at_threshold(capsys):
    net = steam_networking.SteamNetworking()
    net._initialized = True
    net._bridge_instance = types.SimpleNamespace(
        run_callbacks=Mock(side_effect=ValueError('native tick')),
        poll_events=[], poll_messages=[])
    threshold = steam_networking.SteamNetworking._TICK_ERROR_THRESHOLD
    for _ in range(threshold - 1):
        net.tick()
    assert net._initialized  # eşik altında networking kapatılmaz
    net.tick()
    assert not net._initialized  # 5. ardışık hata devre dışı bırakır
    events = net.get_events()
    assert events and events[-1].type == 'error'
    assert events[-1].data == 'networking_disabled'
    out = capsys.readouterr().out
    # Eşik tick'i hem kendi WARN'unu hem eşik ERROR'unu yazar.
    assert out.count('event=tick_transient_error') == threshold + 1
    assert '[OnlinePvP][WARN] event=tick_transient_error detail=ValueError' in out
    assert '[OnlinePvP][ERROR] event=tick_transient_error' in out
    assert 'networking devre disi' in out


def test_shutdown_failure_logs_and_still_resets_state(capsys):
    net = steam_networking.SteamNetworking()
    net._bridge_instance = types.SimpleNamespace(shutdown=Mock(side_effect=RuntimeError('native shutdown')))
    net._initialized = True
    net._state = 'playing'
    net.shutdown()
    assert '[OnlinePvP][ERROR] event=native_cleanup_failed detail=RuntimeError' in capsys.readouterr().out
    # Sözleşme: native hata state-reset bloğunu engellemez.
    assert net._bridge_instance is None
    assert net._initialized is False
    assert net._state == 'idle'


def test_shutdown_legacy_bridge_fallback_failure_is_not_silently_swallowed(capsys):
    net = steam_networking.SteamNetworking()
    net._bridge_instance = types.SimpleNamespace(leave_lobby=Mock(side_effect=OSError('lobby')))
    net.shutdown()
    out = capsys.readouterr().out
    assert "[OnlinePvP][WARN] event=native_cleanup_failed detail=eski-bridge leave_lobby: OSError" in out


# ---------------------------------------------------------------------------
#  D) Log yardımcıları — biçim ve path maskeleme birimleri
# ---------------------------------------------------------------------------

def test_log_event_format_is_single_scannable_line(capsys):
    steam_networking.log_online_pvp_event('WARN', 'x_event', 'det')
    assert capsys.readouterr().out == '[OnlinePvP][WARN] event=x_event detail=det\n'
    steam_networking.log_online_pvp_event('INFO', 'y_event')
    assert capsys.readouterr().out == '[OnlinePvP][INFO] event=y_event\n'


def test_path_tail_keeps_only_trailing_components():
    assert steam_networking._path_tail('C:\\Users\\arda\\Desktop\\repo\\local_artifacts\\bridge', 2) == 'local_artifacts/bridge'
    assert steam_networking._path_tail('C:\\a\\b\\c\\steam_net_bridge.py', 1) == 'steam_net_bridge.py'
    assert steam_networking._path_tail('plain.py') == 'plain.py'
    tail = steam_networking._path_tail('C:\\Users\\x\\y\\z', 2)
    assert tail == 'y/z'
    assert 'Users' not in tail


# ---------------------------------------------------------------------------
#  E) online_pvp_game — oyun içi init/cleanup yolları ve edge-trigger
# ---------------------------------------------------------------------------

@pytest.fixture
def pvp(monkeypatch):
    import online_pvp_game
    import pygame
    pygame.font.init()
    monkeypatch.setattr(online_pvp_game, '_pause_steam_pump', Mock())
    monkeypatch.setattr(online_pvp_game, '_resume_steam_pump', Mock())
    return online_pvp_game


def _game(pvp, available=True, init=True):
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.online_state = pvp.OnlineState.LOBBY_MENU
    game._net_initialized = False
    game._owns_steam_pump_pause = False
    game._closed = False
    game._bridge_missing = False
    game._network_error_key = ''
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(available=available, init=Mock(return_value=init), on=Mock(), shutdown=Mock(), leave_lobby=Mock())
    game._start_pvp_music = Mock()
    game._join_code_active = False
    game._lobby_buttons = []
    game.gamepad = None
    game.sound = types.SimpleNamespace(play=Mock())
    return game


def test_missing_bridge_log_is_edge_triggered(pvp, capsys):
    game = _game(pvp, available=False)
    assert game._init_networking() is False
    # Auto-reconnect 2sn'de bir burayı yeniden çağırır; sınıf DEĞİŞMEDİKÇE
    # tekrar log yazılmaz (per-frame/retry log yasağı).
    assert game._init_networking() is False
    out = capsys.readouterr().out
    assert out.count('event=bridge_import_failed') == 1
    assert game._bridge_missing is True


def test_init_retry_success_logs_recovery(pvp, capsys):
    game = _game(pvp, init=False)
    assert game._init_networking() is False
    capsys.readouterr()  # ilk başarısızlığın logunu ayır
    game.net.init.return_value = True
    assert game._init_networking()
    assert '[OnlinePvP][INFO] event=bridge_init_failed detail=init retry basarili' in capsys.readouterr().out


def test_init_exception_logs_unexpected_class(pvp, capsys):
    game = _game(pvp)
    game.net.init.side_effect = RuntimeError('native init')
    assert game._init_networking() is False
    assert '[OnlinePvP][ERROR] event=unexpected_error detail=RuntimeError' in capsys.readouterr().out


def test_init_cleanup_failure_logs_and_keeps_pump_safety(pvp, capsys):
    game = _game(pvp, init=False)
    game.net.shutdown.side_effect = RuntimeError('native shutdown')
    assert game._init_networking() is False
    out = capsys.readouterr().out
    assert '[OnlinePvP][ERROR] event=native_cleanup_failed detail=init cleanup' in out
    # Sözleşme (invariant): belirsiz native durumda pump referansı bırakılmaz
    # ve yeniden init engellenir.
    assert game._network_cleanup_failed is True
    assert game._bridge_missing is True
    assert game._owns_steam_pump_pause is True
    pvp._resume_steam_pump.assert_not_called()


def test_cleanup_shutdown_failure_logs_and_keeps_pump_safety(pvp, capsys):
    game = _game(pvp)
    assert game._init_networking()
    game.net.shutdown.side_effect = RuntimeError('native shutdown')
    game._cleanup()
    assert '[OnlinePvP][ERROR] event=native_cleanup_failed detail=cleanup' in capsys.readouterr().out
    assert game._owns_steam_pump_pause is True
    pvp._resume_steam_pump.assert_not_called()


def test_ready_pending_flush_failure_log_is_edge_triggered(pvp, capsys):
    game = _game(pvp)
    game._ready_flush_fail_logged = False
    game._log_ready_failure('READY ping A', pending_flush=True)
    game._log_ready_failure('READY ping B', pending_flush=True)  # sessiz: aynı pending dönemi
    game._log_ready_failure('READY ping C', pending_flush=False)  # tek seferlik yol her zaman loglanır
    game._log_ready_failure('READY ping D', pending_flush=True)  # bayrak hâlâ set: sessiz
    out = capsys.readouterr().out
    assert 'READY ping A' in out
    assert 'READY ping C' in out
    assert 'READY ping B' not in out
    assert 'READY ping D' not in out
    assert game._ready_flush_fail_logged is True
    # Başarı noktası bayrağı sıfırlar — yeni pending dönemi tekrar loglar.
    game._ready_flush_fail_logged = False
    game._log_ready_failure('READY ping E', pending_flush=True)
    assert 'READY ping E' in capsys.readouterr().out
