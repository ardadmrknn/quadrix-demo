from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _import_real_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_settings_manager_splits_legacy_settings_into_cloud_and_local(tmp_path, monkeypatch):
    SettingsManager = _import_real_module('settings_manager').SettingsManager
    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    legacy_settings_path = data_dir / 'settings.json'
    legacy_settings_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_settings_path.write_text(
        json.dumps(
            {
                'language': 'en',
                'fullscreen': False,
                'campaign_progress': {'level_1': {'stars': 3}},
                'controls': {
                    'single_player': {
                        'move_left': {'primary': 'j', 'secondary': 'a'},
                    },
                    'gamepad': {
                        'enabled': False,
                        'deadzone': 0.22,
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    sm = SettingsManager()

    cloud_path = data_dir / 'cloud' / 'settings_cloud.json'
    local_path = data_dir / 'local' / 'settings_local.json'
    campaign_path = data_dir / 'cloud' / 'campaign_progress.json'

    assert cloud_path.exists()
    assert local_path.exists()
    assert campaign_path.exists()
    assert sm.get('language') == 'en'
    assert sm.get('fullscreen') is False
    assert sm.get('campaign_progress') == {'level_1': {'stars': 3}}
    assert sm.get_controls()['single_player']['move_left']['primary'] == 'j'
    assert sm.get_controls()['gamepad']['enabled'] is False

    cloud_payload = json.loads(cloud_path.read_text(encoding='utf-8'))
    local_payload = json.loads(local_path.read_text(encoding='utf-8'))
    campaign_payload = json.loads(campaign_path.read_text(encoding='utf-8'))

    assert cloud_payload['language'] == 'en'
    assert 'fullscreen' not in cloud_payload
    assert 'campaign_progress' not in cloud_payload
    assert cloud_payload['controls']['single_player']['move_left']['primary'] == 'j'
    assert 'gamepad' not in cloud_payload['controls']

    assert local_payload['fullscreen'] is False
    assert local_payload['controls']['gamepad']['enabled'] is False
    assert campaign_payload == {'level_1': {'stars': 3}}


def test_settings_manager_preserves_debug_controls(tmp_path, monkeypatch):
    SettingsManager = _import_real_module('settings_manager').SettingsManager
    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    sm = SettingsManager()
    controls = sm.get_controls()
    controls['debug']['coop_spawner_left'] = 'h'
    sm.set('controls', controls)

    sm_reloaded = SettingsManager()

    assert sm_reloaded.get_controls()['debug']['coop_spawner_left'] == 'h'
    assert sm_reloaded.get_default_controls()['debug']['coop_spawner_right'] == ''


def test_user_manager_migrates_profiles_into_cloud_layout(tmp_path, monkeypatch):
    UserManager = _import_real_module('user_manager').UserManager
    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    legacy_users_path = data_dir / 'users.json'
    legacy_ach_path = data_dir / 'achievements_Alice.json'
    legacy_high_path = data_dir / 'highscores_Alice.json'
    legacy_avatar_dir = data_dir / 'avatars'
    legacy_avatar_dir.mkdir(parents=True, exist_ok=True)
    legacy_avatar_path = legacy_avatar_dir / 'Alice_avatar.png'

    legacy_ach_path.write_text(json.dumps({'unlocked': {'first_game': '2026-03-06'}}), encoding='utf-8')
    legacy_high_path.write_text(json.dumps({'highscores': [{'score': 12345}], 'stats': {}}), encoding='utf-8')
    legacy_avatar_path.write_bytes(b'avatar-bytes')
    legacy_users_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_users_path.write_text(
        json.dumps(
            {
                'users': {
                    'Alice': {
                        'created_at': '2026-03-06 12:00:00',
                        'avatar': 'avatars/Alice_avatar.png',
                        'avatar_color': [100, 150, 255],
                        'bio': '',
                        'favorite_mode': 'Classic',
                        'total_games': 0,
                        'total_score': 0,
                        'total_lines': 0,
                        'total_tetrises': 0,
                        'total_combos': 0,
                        'highest_combo': 0,
                        'highest_level': 1,
                        'total_playtime': 0,
                        'last_played': None,
                        'neural_fragments': 0,
                        'hold_piece_counts': {},
                        'achievements_file': 'achievements_Alice.json',
                        'highscores_file': 'highscores_Alice.json',
                        'game_stats': {'classic': {'games': 0, 'score': 0, 'lines': 0}},
                        'tutorial_completed': False,
                        'steam_id': '76561190000000001',
                    }
                },
                'current_user': 'Alice',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    um = UserManager()

    assert um.get_current_user() == 'Alice'
    profile = um.get_user_data('Alice')
    assert profile is not None
    assert profile['profile_id']

    profile_dir = Path(profile['achievements_file']).parent
    assert profile_dir.name == profile['profile_id']
    assert Path(profile['achievements_file']).exists()
    assert Path(profile['highscores_file']).exists()
    assert Path(profile['avatar']).exists()
    assert Path(profile['avatar']).name == 'avatar.png'

    assert not legacy_ach_path.exists()
    assert not legacy_high_path.exists()
    assert not legacy_avatar_path.exists()

    users_payload = json.loads((data_dir / 'cloud' / 'users.json').read_text(encoding='utf-8'))
    current_user_payload = json.loads((data_dir / 'local' / 'current_user.json').read_text(encoding='utf-8'))

    assert users_payload['schema_version'] >= 2
    assert current_user_payload['current_user'] == 'Alice'


def test_data_paths_migrates_legacy_app_root_to_quadrix_full(tmp_path, monkeypatch):
    dp = _import_real_module('data_paths')

    monkeypatch.delenv('QUADRIX_DATA_DIR', raising=False)
    monkeypatch.delenv('TETRIS_DATA_DIR', raising=False)
    monkeypatch.delenv('QUADRIX_APP_NAME', raising=False)
    monkeypatch.delenv('TETRIS_APP_NAME', raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg'))
    monkeypatch.setattr(dp.sys, 'platform', 'linux')

    legacy_root = tmp_path / 'xdg' / 'tetris_full_edition'
    legacy_cloud = legacy_root / 'cloud'
    legacy_local = legacy_root / 'local'
    legacy_cloud.mkdir(parents=True, exist_ok=True)
    legacy_local.mkdir(parents=True, exist_ok=True)
    (legacy_cloud / 'settings_cloud.json').write_text('{"language": "tr"}', encoding='utf-8')
    (legacy_local / 'current_user.json').write_text('{"current_user": "Alice"}', encoding='utf-8')

    resolved = Path(dp.get_user_data_dir())

    assert resolved == tmp_path / 'xdg' / 'quadrix_full'
    assert (resolved / 'cloud' / 'settings_cloud.json').exists()
    assert (resolved / 'local' / 'current_user.json').exists()
    assert not legacy_root.exists()


def test_quadrix_env_names_override_legacy_env_names(tmp_path, monkeypatch):
    dp = _import_real_module('data_paths')

    legacy_override = tmp_path / 'legacy_override'
    new_override = tmp_path / 'new_override'
    monkeypatch.setenv('TETRIS_DATA_DIR', str(legacy_override))
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(new_override))

    assert Path(dp.get_user_data_dir()) == new_override


def test_quadrix_app_name_env_override_is_respected(tmp_path, monkeypatch):
    dp = _import_real_module('data_paths')

    monkeypatch.delenv('QUADRIX_DATA_DIR', raising=False)
    monkeypatch.delenv('TETRIS_DATA_DIR', raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg'))
    monkeypatch.setenv('QUADRIX_APP_NAME', 'quadrix_playtest_shared')
    monkeypatch.setattr(dp.sys, 'platform', 'linux')

    assert Path(dp.get_user_data_dir()) == tmp_path / 'xdg' / 'quadrix_playtest_shared'