import pathlib
import sys
import types


ROOT_DIR = pathlib.Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module


def _make_game_instance():
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.pause_menu_selected = 0
    game.control_bindings = {'pause': game_module.pygame.K_p}
    game.alt_control_bindings = {}
    game._get_fullscreen_toggle_key = lambda: game_module.pygame.K_F12
    game._handle_pause_menu_input = lambda event: 'resume' if getattr(event, 'key', None) == game_module.pygame.K_ESCAPE else None
    game.can_restart = lambda: False
    game.restart = lambda: None
    game.exit_yes_rect = None
    game.exit_no_rect = None
    return game


def _keydown_event(key):
    return types.SimpleNamespace(type=game_module.pygame.KEYDOWN, key=key, mod=0)


def _focus_loss_event(module):
    return types.SimpleNamespace(
        type=module.pygame.ACTIVEEVENT,
        gain=0,
        state=getattr(module.pygame, 'APPINPUTFOCUS', 0) or getattr(module.pygame, 'APPACTIVE', 0),
    )


def test_gameplay_esc_opens_pause_menu_not_exit_prompt(monkeypatch):
    game = _make_game_instance()
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.pause_menu_selected = 3

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown_event(game_module.pygame.K_ESCAPE)])

    game.handle_input()

    assert game.paused is True
    assert game.pause_menu_selected == 0
    assert game.show_exit_prompt is False


def test_paused_esc_resumes_game(monkeypatch):
    game = _make_game_instance()
    game.game_over = False
    game.paused = True
    game.show_exit_prompt = False

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown_event(game_module.pygame.K_ESCAPE)])

    game.handle_input()

    assert game.paused is False


def test_focus_loss_pauses_gameplay(monkeypatch):
    game = _make_game_instance()
    game.pause_menu_selected = 4

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_focus_loss_event(game_module)])

    game.handle_input()

    assert game.paused is True
    assert game.pause_menu_selected == 0


def test_game_over_esc_returns_menu(monkeypatch):
    game = _make_game_instance()
    game.game_over = True
    game.paused = False
    game.show_exit_prompt = False

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown_event(game_module.pygame.K_ESCAPE)])

    result = game.handle_input()

    assert result == 'menu'


def test_game_over_ignores_gamepad_mouse_click(monkeypatch):
    game = _make_game_instance()
    game.game_over = True
    game._game_over_peek_active = False
    game._game_over_peek_rect = None
    restart_calls = []

    class _HitRect:
        def collidepoint(self, pos):
            return True

    game._game_over_click_targets = {'restart': _HitRect(), 'menu': _HitRect()}
    game.restart = lambda: restart_calls.append(True)

    monkeypatch.setattr(game_module, 'normalize_mouse_pos', lambda pos: pos)
    monkeypatch.setattr(
        game_module.pygame.event,
        'get',
        lambda: [types.SimpleNamespace(type=game_module.pygame.MOUSEBUTTONDOWN, button=1, pos=(12, 34), from_gamepad=True)],
    )

    game.handle_input()

    assert restart_calls == []


# ---------------------------------------------------------------------------
# PvP game_over + ESC regression
# ---------------------------------------------------------------------------

import pvp_game as pvp_module


def _make_pvp_instance():
    pvp = pvp_module.PvPGame.__new__(pvp_module.PvPGame)
    pvp.game_over = False
    pvp.paused = False
    pvp.show_exit_prompt = False
    pvp.pause_menu_selected = 0
    pvp.name_input_active = False
    pvp.pvp_controls = {
        'pause': pvp_module.pygame.K_p,
        'player1': {},
        'player2': {},
    }
    pvp._get_fullscreen_toggle_key = lambda: pvp_module.pygame.K_F12
    pvp._handle_pause_menu_input = lambda event: 'resume' if getattr(event, 'key', None) == pvp_module.pygame.K_ESCAPE else None
    return pvp


def test_pvp_game_over_esc_returns_menu(monkeypatch):
    """PvP game_over sırasında ESC → 'menu' döndürmeli, pause açmamalı."""
    pvp = _make_pvp_instance()
    pvp.game_over = True
    pvp.paused = False

    monkeypatch.setattr(pvp_module.pygame.event, 'get', lambda: [_keydown_event(pvp_module.pygame.K_ESCAPE)])

    result = pvp.handle_input()

    assert result == 'menu'
    assert pvp.paused is False


def test_pvp_game_over_ignores_gamepad_mouse_click(monkeypatch):
    pvp = _make_pvp_instance()
    pvp.game_over = True
    pvp._game_over_peek_active = False
    pvp._game_over_peek_rect = None
    restart_calls = []

    class _HitRect:
        def collidepoint(self, pos):
            return True

    pvp._game_over_restart_rect = _HitRect()
    pvp._game_over_menu_rect = _HitRect()
    pvp.restart = lambda preserve_session=True: restart_calls.append(preserve_session)

    monkeypatch.setattr(pvp_module, 'normalize_mouse_pos', lambda pos: pos)
    monkeypatch.setattr(
        pvp_module.pygame.event,
        'get',
        lambda: [types.SimpleNamespace(type=pvp_module.pygame.MOUSEBUTTONDOWN, button=1, pos=(12, 34), from_gamepad=True)],
    )

    pvp.handle_input()

    assert restart_calls == []


def test_pvp_gameplay_esc_opens_pause(monkeypatch):
    """PvP gameplay sırasında ESC → pause menü açılmalı."""
    pvp = _make_pvp_instance()
    pvp.game_over = False
    pvp.paused = False
    pvp.pause_menu_selected = 5

    monkeypatch.setattr(pvp_module.pygame.event, 'get', lambda: [_keydown_event(pvp_module.pygame.K_ESCAPE)])

    pvp.handle_input()

    assert pvp.paused is True
    assert pvp.pause_menu_selected == 0


def test_pvp_focus_loss_pauses_gameplay(monkeypatch):
    pvp = _make_pvp_instance()
    pvp.game_over = False
    pvp.paused = False
    pvp.pause_menu_selected = 2

    monkeypatch.setattr(pvp_module.pygame.event, 'get', lambda: [_focus_loss_event(pvp_module)])

    pvp.handle_input()

    assert pvp.paused is True
    assert pvp.pause_menu_selected == 0


def _make_pvp_layout_instance(size=(1920, 1080), stale_size=(640, 360)):
    pvp = pvp_module.PvPGame.__new__(pvp_module.PvPGame)
    pvp.screen = pvp_module.pygame.Surface(size, pvp_module.pygame.SRCALPHA)
    pvp.window_width, pvp.window_height = stale_size
    pvp._layout_key = None
    pvp._board_grid_cache = {'key': 'stale', 'surface': object()}
    pvp._locked_board_cache = {
        1: {'dirty': False},
        2: {'dirty': False},
    }
    pvp._base_header_height = 64
    pvp._base_header_top = 28
    pvp._base_board_gap = 24
    pvp._base_preview_panel_width = 126
    pvp._base_preview_panel_gap = 12
    pvp._base_center_panel_width = 120
    pvp._base_center_panel_gap = 18
    pvp._ui_scale = lambda min_scale=0.72, max_scale=1.20: 1.0
    return pvp


def test_pvp_layout_uses_active_surface_size_and_invalidates_caches():
    pvp = _make_pvp_layout_instance()

    pvp.calculate_board_positions()

    board_width = pvp_module.BOARD_WIDTH * pvp.cell_size
    assert (pvp.window_width, pvp.window_height) == (1920, 1080)
    assert pvp.p1_offset_x == pvp.p1_preview_x + pvp.preview_panel_width + pvp.preview_panel_gap
    assert pvp.center_panel_x == pvp.p1_offset_x + board_width + pvp.center_panel_gap
    assert pvp.p2_offset_x == pvp.center_panel_x + pvp.center_panel_width + pvp.center_panel_gap
    assert pvp.p2_preview_x == pvp.p2_offset_x + board_width + pvp.preview_panel_gap
    assert pvp._board_grid_cache['key'] is None
    assert pvp._board_grid_cache['surface'] is None
    assert pvp._locked_board_cache[1]['dirty'] is True
    assert pvp._locked_board_cache[2]['dirty'] is True


def test_pvp_layout_keeps_preview_and_boards_inside_small_surface():
    pvp = _make_pvp_layout_instance(size=(800, 600), stale_size=(1600, 900))

    pvp.calculate_board_positions()

    right_edge = pvp.p2_preview_x + pvp.preview_panel_width
    assert right_edge <= 800
    assert pvp.p1_preview_x >= 0
    assert pvp.header_top >= 0
    assert pvp.board_top >= pvp.header_top + pvp.header_height
    assert pvp.cell_size >= 14


# ---------------------------------------------------------------------------
# HardcoreGame K_p → pause_menu_selected sıfırlama
# ---------------------------------------------------------------------------

import game_modes as modes_module


def _make_hardcore_instance():
    hc = modes_module.HardcoreMode.__new__(modes_module.HardcoreMode)
    hc.game_over = False
    hc.paused = False
    hc.show_exit_prompt = False
    hc.pause_menu_selected = 7
    hc.control_bindings = {'pause': modes_module.pygame.K_p}
    hc.alt_control_bindings = {}
    hc._get_fullscreen_toggle_key = lambda: modes_module.pygame.K_F12
    hc._handle_pause_menu_input = lambda event: None
    hc.can_restart = lambda: False
    hc.restart = lambda: None
    hc.exit_yes_rect = None
    hc.exit_no_rect = None
    hc.sound_enabled = False
    hc.sound = None
    hc.settings_manager = None
    return hc


def test_hardcore_k_p_resets_pause_menu_selected(monkeypatch):
    """HardcoreGame K_p ile pause açılınca pause_menu_selected sıfırlanmalı."""
    import collections
    hc = _make_hardcore_instance()
    hc.paused = False
    hc.pause_menu_selected = 7

    monkeypatch.setattr(modes_module.pygame.event, 'get', lambda: [_keydown_event(modes_module.pygame.K_p)])
    # video sistemi başlatılmadığından key.get_pressed mock'lanmalı (defaultdict ile tüm key'ler False)
    monkeypatch.setattr(modes_module.pygame.key, 'get_pressed', lambda: collections.defaultdict(bool))

    hc.handle_input()

    assert hc.paused is True
    assert hc.pause_menu_selected == 0


def test_hardcore_focus_loss_pauses_gameplay(monkeypatch):
    import collections

    hc = _make_hardcore_instance()
    hc.paused = False
    hc.pause_menu_selected = 6

    monkeypatch.setattr(modes_module.pygame.event, 'get', lambda: [_focus_loss_event(modes_module)])
    monkeypatch.setattr(modes_module.pygame.key, 'get_pressed', lambda: collections.defaultdict(bool))

    hc.handle_input()

    assert hc.paused is True
    assert hc.pause_menu_selected == 0