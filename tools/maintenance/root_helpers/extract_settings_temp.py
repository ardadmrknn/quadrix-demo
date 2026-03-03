
import sys
import os
import json

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from settings_manager import SettingsManager
    # Initialize settings manager
    # It will automatically find the correct settings file based on its logic
    manager = SettingsManager()
    
    # We only care about music and relevant settings to be default
    relevant_settings = {
        'menu_music': manager.get('menu_music'),
        'game_music': manager.get('game_music'),
        'mode_music_overrides': manager.get('mode_music_overrides'),
        'fullscreen': manager.get('fullscreen'),
        'borderless_fullscreen': manager.get('borderless_fullscreen'),
        'music_volume': manager.get('music_volume'),
        'sfx_volume': manager.get('sfx_volume')
    }
    
    print("---SETTINGS_START---")
    print(json.dumps(relevant_settings, indent=4, ensure_ascii=False))
    print("---SETTINGS_END---")
    print(f"Read from: {manager.filename}")
    
except Exception as e:
    print(f"Error: {e}")
