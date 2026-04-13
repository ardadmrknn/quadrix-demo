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
        'toggle_fps': pvp_module.pygame.K_f,
        'player1': {},
        'player2': {},
    }
    pvp._get_fullscreen_toggle_key = lambda: pvp_module.pygame.K_F12
    pvp._handle_pause_menu_input = lambda event: 'resume' if getattr(event, 'key', None) == pvp_module.pygame.K_ESCAPE else None
    pvp.show_fps = False
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