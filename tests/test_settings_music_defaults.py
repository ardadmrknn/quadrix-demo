"""settings_manager.py — bölüm müziği varsayılanlarının build fallback testi."""

import copy

from settings_manager import (
    DEFAULT_CAMPAIGN_MUSIC_PLAYLIST,
    DEFAULT_GAME_MUSIC_PLAYLIST,
    DEFAULT_MENU_MUSIC_PLAYLIST,
    DEFAULT_MODE_MUSIC_PLAYLISTS,
    MODE_MUSIC_DEFAULTS,
    SettingsManager,
)


def test_mode_music_defaults_match_selected_playlists(tmp_path):
    settings_file = tmp_path / 'settings.json'
    sm = SettingsManager(filename=str(settings_file))

    assert sm.default_settings['menu_music_playlist'] == DEFAULT_MENU_MUSIC_PLAYLIST
    assert sm.default_settings['game_music_playlist'] == DEFAULT_GAME_MUSIC_PLAYLIST
    assert sm.default_settings['campaign_music_playlist'] == DEFAULT_CAMPAIGN_MUSIC_PLAYLIST
    assert sm.default_settings['mode_music_playlists'] == DEFAULT_MODE_MUSIC_PLAYLISTS

    assert sm.get_music_playlist_for_mode('classic') == ['file:klasik_1.mp3']
    assert sm.get_music_playlist_for_mode('survival') == ['file:survival_2.mp3', 'file:survival_1.mp3']
    assert sm.get_music_playlist_for_mode('campaign_world4') == ['file:d4_1.mp3', 'file:d4_2.mp3', 'file:d4_3.mp3']
    assert sm.get_music_preference_for_mode('classic') == 'file:klasik_1.mp3'
    assert sm.get_music_preference_for_mode('campaign') == DEFAULT_CAMPAIGN_MUSIC_PLAYLIST[0]


def test_merge_mode_music_playlists_preserves_defaults_and_overrides():
    sm = SettingsManager.__new__(SettingsManager)

    merged = sm._merge_mode_music_playlists_with_defaults({
        'classic': ['file:custom_classic.mp3'],
        'daily': ['file:daily_alt.mp3'],
        'wide': [],
        'ignored': None,
    })

    expected = copy.deepcopy(DEFAULT_MODE_MUSIC_PLAYLISTS)
    expected['classic'] = ['file:custom_classic.mp3']
    expected['daily'] = ['file:daily_alt.mp3']

    assert merged == expected
    assert MODE_MUSIC_DEFAULTS['classic'] == 'file:klasik_1.mp3'