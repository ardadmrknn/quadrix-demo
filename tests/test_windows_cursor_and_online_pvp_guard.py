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


def test_windows_loads_custom_cursor_png(monkeypatch):
    calls = []
    loaded_paths = []
    scaled_sizes = []
    cursor_objects = []

    class _Surface:
        def convert_alpha(self):
            return self

    def _load(path):
        loaded_paths.append(path)
        return _Surface()

    def _smoothscale(surface, size):
        scaled_sizes.append(size)
        return surface

    def _cursor(hotspot, surface):
        cursor = {'hotspot': hotspot, 'surface': surface}
        cursor_objects.append(cursor)
        return cursor

    monkeypatch.setattr(main_module.sys, 'platform', 'win32')
    monkeypatch.setattr(main_module.pygame.mouse, 'set_cursor', lambda cursor: calls.append(cursor))
    monkeypatch.setattr(main_module.pygame.image, 'load', _load)
    monkeypatch.setattr(main_module.pygame.transform, 'smoothscale', _smoothscale)
    monkeypatch.setattr(main_module.pygame.cursors, 'Cursor', _cursor)

    assert main_module.setup_custom_cursor() is True
    assert loaded_paths
    assert pathlib.PurePath(loaded_paths[0]).as_posix().endswith('assets/ui/cursor.png')
    assert scaled_sizes == [(32, 32)]
    assert cursor_objects
    assert cursor_objects[0]['hotspot'] == (4, 4)
    assert calls == [cursor_objects[0]]


def test_windows_cursor_load_failure_falls_back_to_system_cursor(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module.sys, 'platform', 'win32')
    monkeypatch.setattr(main_module.pygame.mouse, 'set_cursor', lambda cursor: calls.append(cursor))
    monkeypatch.setattr(
        main_module.pygame.image,
        'load',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('cursor asset unavailable')),
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
