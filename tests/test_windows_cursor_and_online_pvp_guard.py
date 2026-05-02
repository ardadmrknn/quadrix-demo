from __future__ import annotations

import importlib
import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

main_module = importlib.import_module('src.main')
online_pvp_module = importlib.import_module('online_pvp_game')


def test_windows_uses_system_cursor_instead_of_custom_png(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module.sys, 'platform', 'win32')
    monkeypatch.setattr(main_module.pygame.mouse, 'set_cursor', lambda cursor: calls.append(cursor))
    monkeypatch.setattr(
        main_module.pygame.image,
        'load',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('custom cursor image should not load on Windows')),
    )

    assert main_module.setup_custom_cursor() is False
    assert calls == [main_module.pygame.SYSTEM_CURSOR_ARROW]


def test_online_pvp_line_clear_feedback_failure_is_non_fatal():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.my_line_flash_rows = [18]
    game.my_line_flash_timer = 20
    game.my_line_glow_alpha = 255
    game.my_wave_effects = [{'radius': 1}]
    game.my_line_sweep_rows = [18]
    game.my_line_sweep_progress = 0.5
    game.my_line_sweep_active = True
    game.my_falling_block_animations = [{'row': 18, 'col': 0}]

    def boom(*_args, **_kwargs):
        raise RuntimeError('windows effect failure')

    game._trigger_line_clear_feedback = boom

    game._safe_trigger_line_clear_feedback([18], 10, 20, 24, board=None, is_opponent=False)

    assert game.my_line_flash_rows == []
    assert game.my_line_flash_timer == 0
    assert game.my_line_glow_alpha == 0
    assert game.my_wave_effects == []
    assert game.my_line_sweep_rows == []
    assert game.my_line_sweep_progress == 0.0
    assert game.my_line_sweep_active is False
    assert game.my_falling_block_animations == []
