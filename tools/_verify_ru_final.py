"""Comprehensive verification of Russian translations."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS, set_language, t

set_language('ru')

# 1. Critical settings keys
print("=== SETTINGS TAB LABELS ===")
tabs = ['settings_tab_game', 'settings_tab_display', 'settings_tab_audio',
        'settings_tab_controls', 'settings_tab_customize', 'settings_tab_other']
for k in tabs:
    v = t(k)
    ok = v != TRANSLATIONS[k].get('en', '')
    print(f"  {k:35s} = {v:20s} {'OK' if ok else 'STILL EN!'}")

print("\n=== SETTINGS ITEMS ===")
items = ['language', 'fullscreen', 'windowed', 'resolution', 'automatic',
         'show_fps', 'show_ghost', 'bg_transparency',
         'music', 'music_volume', 'menu_music_volume', 'music_shuffle',
         'sound_effects', 'sfx_volume', 'mute_all', 'on', 'off',
         'panel_settings', 'window_mode', 'track_count_unit',
         'particle_effects', 'piece_workshop', 'block_styles', 'theme']
for k in items:
    v = t(k)
    en_v = TRANSLATIONS.get(k, {}).get('en', '')
    ok = v != en_v or v == en_v == ''
    print(f"  {k:35s} = {v:30s} {'OK' if ok else 'STILL EN!'}")

print("\n=== COMMON UI ===")
ui = ['back', 'cancel', 'confirm', 'save', 'yes', 'no', 'ok',
      'loading', 'error', 'restart_now', 'later',
      'campaign_mode', 'single_player', 'settings', 'exit', 'quit']
for k in ui:
    v = t(k)
    en_v = TRANSLATIONS.get(k, {}).get('en', '')
    ok = v != en_v
    print(f"  {k:35s} = {v:30s} {'OK' if ok else 'STILL EN!'}")

# 2. Count remaining EN fallbacks
total = 0
missing = 0
for k, d in TRANSLATIONS.items():
    if 'ru' in d and 'en' in d:
        total += 1
        if d['ru'] == d['en']:
            missing += 1

print(f"\n=== COVERAGE ===")
print(f"Total keys with both RU and EN: {total}")
print(f"Keys where RU still == EN: {missing}")
print(f"Real Russian translations: {total - missing}")
print(f"Coverage: {(total - missing) / total * 100:.1f}%")
