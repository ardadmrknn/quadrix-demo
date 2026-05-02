import pathlib
import sys
import importlib


ROOT_DIR = pathlib.Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

main_module = importlib.import_module('src.main')


class _UserManagerStub:
    def __init__(self, users, current_user=None):
        self._users = users
        self._current_user = current_user

    def get_current_user(self):
        return self._current_user

    def get_all_users(self):
        return self._users

    def get_achievements_file(self):
        return '/tmp/profile-achievements.json'

    def get_highscores_file(self):
        return '/tmp/profile-highscores.json'


def test_has_active_profile_session_requires_current_user_when_not_steam():
    user_manager = _UserManagerStub({'Ada': {}}, current_user=None)

    assert main_module._has_active_profile_session(user_manager, False) is False


def test_has_active_profile_session_accepts_valid_current_user_or_steam():
    user_manager = _UserManagerStub({'Ada': {}}, current_user='Ada')

    assert main_module._has_active_profile_session(user_manager, False) is True
    assert main_module._has_active_profile_session(_UserManagerStub({}, current_user=None), True) is True


def test_build_user_bound_views_uses_profile_scoped_files(monkeypatch):
    calls = {}

    class _ScoreManager:
        def __init__(self, path):
            calls['score_path'] = path

    class _AchievementManager:
        def __init__(self, path):
            calls['achievement_path'] = path

    class _HighScoreScreen:
        def __init__(self, screen, score_manager, user_manager, steam_mode_scores=None):
            calls['highscore_screen'] = {
                'screen': screen,
                'score_manager': score_manager,
                'user_manager': user_manager,
                'steam_mode_scores': steam_mode_scores,
            }

    class _AchievementScreen:
        def __init__(self, screen, achievement_manager):
            calls['achievement_screen'] = {
                'screen': screen,
                'achievement_manager': achievement_manager,
            }

    monkeypatch.setattr(main_module, 'ScoreManager', _ScoreManager)
    monkeypatch.setattr(main_module, 'AchievementManager', _AchievementManager)
    monkeypatch.setattr(main_module, 'HighScoreScreen', _HighScoreScreen)
    monkeypatch.setattr(main_module, 'AchievementScreen', _AchievementScreen)

    screen = object()
    user_manager = _UserManagerStub({'Ada': {}}, current_user='Ada')

    result = main_module._build_user_bound_views(
        screen,
        user_manager,
        lambda limit=3: {'mystery': [{'score': 123}]},
    )

    assert calls['score_path'] == '/tmp/profile-highscores.json'
    assert calls['achievement_path'] == '/tmp/profile-achievements.json'
    assert calls['highscore_screen']['screen'] is screen
    assert calls['highscore_screen']['user_manager'] is user_manager
    assert calls['highscore_screen']['steam_mode_scores'] == {'mystery': [{'score': 123}]}
    assert calls['achievement_screen']['screen'] is screen
    assert len(result) == 4