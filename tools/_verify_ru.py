"""Verify new translation keys and Russian translations."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS, set_language, t

keys = ['music_shuffle', 'track_count_unit', 'mode_music_playlist_editor']
for k in keys:
    d = TRANSLATIONS.get(k, {})
    ru_val = d.get('ru', 'MISSING')
    langs = list(d.keys())
    print(f"{k}: ru={ru_val!r} | langs={langs}")

set_language('ru')
print("\nRussian t() tests:")
test_keys = keys + ['on', 'off', 'settings_tab_game', 'settings_tab_audio',
                     'fullscreen', 'windowed', 'mute_all', 'language',
                     'panel_settings', 'campaign_mode', 'single_player']
for k in test_keys:
    print(f"  {k:40s} = {t(k)}")
