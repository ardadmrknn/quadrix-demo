import sys, os
sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'
from settings_manager import SettingsManager
sm = SettingsManager()
print(f"Settings file: {sm.filename}")
print(f"Language in settings: {sm.get('language', 'MISSING')}")

# Also check the actual JSON on disk
import json
with open(sm.filename, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"Language on disk: {data.get('language', 'MISSING')}")
print(f"File exists: {os.path.exists(sm.filename)}")
