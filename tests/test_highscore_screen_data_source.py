import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from menu import HighScoreScreen


class _UserManagerStub:
    def __init__(self, scores):
        self._scores = scores

    def get_mode_highscores(self, mode_key, limit=3):
        return list(self._scores.get(mode_key, []))[:limit]


def _make_screen(user_manager=None, steam_mode_scores=None):
    screen = HighScoreScreen.__new__(HighScoreScreen)
    screen.user_manager = user_manager
    screen.steam_mode_scores = steam_mode_scores or {}
    return screen


def test_highscore_screen_prefers_local_user_scores_over_steam_scores():
    local_scores = {
        'mystery': [
            {'score': 197502},
            {'score': 122239},
            {'score': 103751},
        ]
    }
    steam_scores = {
        'mystery': [
            {'score': 3133731},
            {'score': 197502},
            {'score': 94688},
        ]
    }
    screen = _make_screen(user_manager=_UserManagerStub(local_scores), steam_mode_scores=steam_scores)

    scores = screen._get_mode_scores('mystery')

    assert [entry['score'] for entry in scores] == [197502, 122239, 103751]


def test_highscore_screen_falls_back_to_steam_scores_without_user_manager():
    steam_scores = {
        'mystery': [
            {'score': 3133731},
            {'score': 197502},
            {'score': 94688},
            {'score': 1000},
        ]
    }
    screen = _make_screen(user_manager=None, steam_mode_scores=steam_scores)

    scores = screen._get_mode_scores('mystery')

    assert [entry['score'] for entry in scores] == [3133731, 197502, 94688]