"""Steam önkoşulu, constructor, fallback UI ve callback sahipliği regresyonları."""
from __future__ import annotations

import ast
import copy
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

SRC = Path(__file__).resolve().parents[1] / 'src'


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


@pytest.mark.parametrize('steam_ready,bridge_ready,key', [(False, True, 'Steam'), (True, False, 'köprü')])
def test_launch_guard_rejects_missing_dependency(main_functions, monkeypatch, steam_ready, bridge_ready, key):
    monkeypatch.setitem(sys.modules, 'steam_integration', types.SimpleNamespace(is_available=lambda: steam_ready))
    # DUZ-012: _online_pvp_launch_status fonksiyon başında sınıflandırma
    # sabitlerini ve log yardımcısını da import eder — stub bunları taşır.
    monkeypatch.setitem(sys.modules, 'steam_networking', types.SimpleNamespace(
        SteamNetworking=lambda: types.SimpleNamespace(available=bridge_ready),
        ONLINE_PVP_ERR_BRIDGE_IMPORT_FAILED='bridge_import_failed',
        ONLINE_PVP_ERR_STEAM_CLIENT_OFFLINE='steam_client_offline',
        ONLINE_PVP_ERR_STEAM_SDK_MISSING='steam_sdk_missing',
        log_online_pvp_event=lambda *a, **k: None,
    ))
    ok, message = main_functions['_online_pvp_launch_status']()
    assert not ok
    assert key in message


def test_constructor_not_called_when_preflight_fails(main_functions):
    main_functions['_online_pvp_launch_status'] = lambda: (False, 'offline')
    restore = Mock()
    assert main_functions['_create_online_pvp_game'](on_failure=restore) == (None, 'offline')
    restore.assert_not_called()
    main_functions['OnlinePvPGame'].assert_not_called()


def test_constructor_exception_returns_localized_failure(main_functions):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    main_functions['OnlinePvPGame'].side_effect = RuntimeError('constructor failed')
    restore = Mock()
    game, message = main_functions['_create_online_pvp_game'](screen='screen', on_failure=restore)
    restore.assert_called_once()
    assert game is None
    assert message == 'online_pvp_launch_failed'


def test_success_returns_game_and_forwards_options(main_functions):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    result = types.SimpleNamespace(_init_networking=Mock(return_value=True))
    main_functions['OnlinePvPGame'].return_value = result
    assert main_functions['_create_online_pvp_game'](screen='screen') == (result, '')
    main_functions['OnlinePvPGame'].assert_called_once_with(screen='screen')
    result._init_networking.assert_called_once()
    assert result._auto_connect_retry_timer == 0.0


def test_launch_init_failure_keeps_exitable_fallback(main_functions):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    result = types.SimpleNamespace(_init_networking=Mock(return_value=False))
    main_functions['OnlinePvPGame'].return_value = result
    restore = Mock()
    assert main_functions['_create_online_pvp_game'](on_failure=restore) == (result, '')
    assert result._auto_connect_attempted is True
    assert result._auto_connect_retry_timer == 2000.0
    restore.assert_not_called()


def test_launch_init_exception_cleans_up_and_restores_music(main_functions):
    main_functions['_online_pvp_launch_status'] = lambda: (True, '')
    result = types.SimpleNamespace(_init_networking=Mock(side_effect=RuntimeError('network init')), _cleanup=Mock())
    main_functions['OnlinePvPGame'].return_value = result
    restore = Mock()
    assert main_functions['_create_online_pvp_game'](on_failure=restore) == (None, 'online_pvp_launch_failed')
    result._cleanup.assert_called_once()
    restore.assert_called_once()


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


def test_missing_bridge_does_not_pause_or_start_music(pvp):
    game = _game(pvp, available=False)
    assert game._init_networking() is False
    assert game._network_error_key == 'steam_bridge_not_available'
    assert game._bridge_missing is True
    pvp._pause_steam_pump.assert_not_called()
    game.net.init.assert_not_called()
    game._start_pvp_music.assert_not_called()
    game._cleanup()
    pvp._resume_steam_pump.assert_not_called()


@pytest.mark.parametrize('raises', [False, True])
def test_failed_init_balances_owned_pause_and_keeps_music(pvp, raises):
    game = _game(pvp, init=False)
    if raises:
        game.net.init.side_effect = RuntimeError('native init')
    assert game._init_networking() is False
    assert game.online_state == pvp.OnlineState.LOBBY_MENU
    assert game._network_error_key == 'steam_net_init_failed'
    assert not game._owns_steam_pump_pause
    game._start_pvp_music.assert_not_called()
    pvp._pause_steam_pump.assert_called_once()
    pvp._resume_steam_pump.assert_called_once()
    game._cleanup()
    game._cleanup()
    pvp._resume_steam_pump.assert_called_once()


def test_success_init_and_double_cleanup_are_idempotent(pvp):
    game = _game(pvp)
    assert game._init_networking()
    assert game._init_networking()
    game.net.init.assert_called_once()
    game._start_pvp_music.assert_called_once()
    pvp._pause_steam_pump.assert_called_once()
    pvp._resume_steam_pump.assert_not_called()
    game._cleanup()
    game._cleanup()
    game.net.shutdown.assert_called_once()
    pvp._resume_steam_pump.assert_called_once()
    assert not game._init_networking()


def test_transient_init_failure_can_recover(pvp):
    game = _game(pvp, init=False)
    assert not game._init_networking()
    game.net.init.return_value = True
    assert game._init_networking()
    assert game._network_error_key == ''
    assert game._owns_steam_pump_pause
    assert pvp._pause_steam_pump.call_count == 2
    assert pvp._resume_steam_pump.call_count == 1


def test_shutdown_failure_does_not_resume_a_live_native_owner(pvp):
    game = _game(pvp)
    assert game._init_networking()
    game.net.shutdown.side_effect = RuntimeError('native shutdown')
    game._cleanup()
    pvp._resume_steam_pump.assert_not_called()
    assert game._owns_steam_pump_pause
    game.net.shutdown.side_effect = None
    game._cleanup()
    pvp._resume_steam_pump.assert_called_once()


def test_failed_init_and_shutdown_block_reinit_until_cleanup(pvp):
    game = _game(pvp, init=False)
    game.net.shutdown.side_effect = RuntimeError('native shutdown')
    assert game._init_networking() is False
    assert game._network_cleanup_failed
    assert game._owns_steam_pump_pause
    assert game._init_networking() is False
    game.net.init.assert_called_once()
    pvp._pause_steam_pump.assert_called_once()
    pvp._resume_steam_pump.assert_not_called()
    game.net.shutdown.side_effect = None
    game._cleanup()
    assert not game._network_cleanup_failed
    pvp._resume_steam_pump.assert_called_once()
    assert not game._init_networking()


def test_callback_registration_failure_shuts_down_partial_init(pvp):
    game = _game(pvp)
    game.net.on.side_effect = RuntimeError('callback registration')
    assert game._init_networking() is False
    game.net.shutdown.assert_called_once()
    pvp._resume_steam_pump.assert_called_once()
    game._start_pvp_music.assert_not_called()
    assert not game._net_initialized


@pytest.mark.parametrize('key_name', ['K_ESCAPE', 'K_RETURN', 'K_KP_ENTER'])
def test_fallback_back_keys_never_touch_native_lobby(pvp, key_name):
    game = _game(pvp)
    result = game._handle_keydown(types.SimpleNamespace(key=getattr(pvp.pygame, key_name), from_gamepad=True))
    assert result == 'menu'
    game.net.leave_lobby.assert_not_called()


def test_fallback_blocks_keyboard_and_mouse_lobby_actions(pvp):
    game = _game(pvp)
    game._create_lobby = Mock()
    for name in ('K_1', 'K_2', 'K_3', 'K_i', 'K_j'):
        assert game._handle_keydown(types.SimpleNamespace(key=getattr(pvp.pygame, name))) is None
    rect = pvp.pygame.Rect(0, 0, 100, 50)
    game._lobby_buttons = [{'rect': rect, 'action': 'create_private'}]
    assert game._handle_mouse_click(types.SimpleNamespace(pos=(10, 10))) is None
    game._create_lobby.assert_not_called()
    game.net.init.assert_not_called()
    game._lobby_buttons = [{'rect': rect, 'action': 'back'}]
    assert game._handle_mouse_click(types.SimpleNamespace(pos=(10, 10))) == 'menu'


@pytest.mark.parametrize('size', [(640, 480), (1280, 800), (1920, 1080), (3840, 2160)])
def test_fallback_draw_is_cached_bounded_and_has_only_back(pvp, monkeypatch, size):
    import pygame
    game = _game(pvp)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game._ui_scale = lambda: 1.0
    game._network_error_key = 'steam_net_init_failed'
    render = Mock(wraps=pvp.render_text)
    monkeypatch.setattr(pvp, 'render_text', render)
    for _ in range(2):
        game._lobby_buttons.clear()
        game._draw_lobby_menu()
        assert [b['action'] for b in game._lobby_buttons] == ['back']
        assert game.screen.get_rect().contains(game._lobby_buttons[0]['rect'])
    assert render.call_count == 2


@pytest.mark.parametrize('failure', ['input', 'update', 'draw'])
def test_runtime_error_cleans_up_reports_and_restores_music(failure):
    tree = ast.parse((SRC / 'main.py').read_text(encoding='utf-8'))
    node = copy.deepcopy(next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_handle_online_pvp'))
    node.body = [ast.Global(names=n.names) if isinstance(n, ast.Nonlocal) else n for n in node.body]
    game = types.SimpleNamespace(handle_input=Mock(return_value=True), update=Mock(), draw=Mock(), _cleanup=Mock())
    getattr(game, {'input': 'handle_input', 'update': 'update', 'draw': 'draw'}[failure]).side_effect = RuntimeError(failure)
    env = {'running': True, 'state': 'online_pvp', '_restore_online_pvp_menu_music': Mock(),
           'menu': types.SimpleNamespace(show_info=Mock()), 't': lambda key, default=None: key}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), 'main_handler', 'exec'), env)
    env['_handle_online_pvp']._game = game
    assert env['_handle_online_pvp'](16) is False
    assert env['state'] == 'menu'
    game._cleanup.assert_called_once()
    env['_restore_online_pvp_menu_music'].assert_called_once()
    assert env['menu'].show_info.call_count == 1


def test_demo_routes_block_constructor_and_show_correct_lock_screen():
    if not (SRC / 'demo_config.py').exists():
        return
    tree = ast.parse((SRC / 'main.py').read_text(encoding='utf-8'))
    routes = [node for node in ast.walk(tree) if isinstance(node, ast.If) and any(
        isinstance(n, ast.Constant) and n.value in ('online_pvp', 'Online PvP') for n in ast.walk(node.test))
        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_create_online_pvp_game' for statement in node.body for n in ast.walk(statement))]
    assert len(routes) == 2
    for route in routes:
        menu = types.SimpleNamespace(_maybe_handle_demo_main_action=Mock())
        extras = types.SimpleNamespace(_show_demo_lock_prompt_for_mode=Mock())
        create = Mock(side_effect=AssertionError('locked demo entered online mode'))
        env = {'menu': menu, 'extras_screen': extras, '_create_online_pvp_game': create,
               'demo_config': types.SimpleNamespace(is_locked_main_action=lambda action: True, get_extras_lock_kind=lambda action: 'transition')}
        body = copy.deepcopy(route.body)
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()), iter=ast.List(elts=[ast.Constant(0)], ctx=ast.Load()), body=body, orelse=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])), 'demo_route', 'exec'), env)
        create.assert_not_called()
        assert menu._maybe_handle_demo_main_action.call_count + extras._show_demo_lock_prompt_for_mode.call_count == 1
