import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import main as main_module


class _FakeGame:
    def __init__(self, game_time=0):
        self.game_time = game_time
        self.calls = []

    def finalize_run(self, playtime=None):
        self.calls.append(playtime)


def test_persist_active_game_run_uses_seconds_from_game_time():
    game = _FakeGame(game_time=9876)

    main_module._persist_active_game_run(game)

    assert game.calls == [9]


def test_persist_active_game_run_ignores_missing_finalize_run():
    class _NoFinalize:
        game_time = 4321

    main_module._persist_active_game_run(_NoFinalize())


def test_persist_active_game_run_falls_back_when_game_time_is_invalid():
    game = _FakeGame(game_time='not-a-number')

    main_module._persist_active_game_run(game)

    assert game.calls == [None]