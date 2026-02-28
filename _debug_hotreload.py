"""Test: hot reload sırasında _current_language sıfırlanıyor mu?"""
import sys, os
sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '1'

import localization
from localization import set_language, get_language, refresh_localization_if_changed

print(f"1. Initial language: {get_language()}")

set_language('ko')
print(f"2. After set_language('ko'): {get_language()}")

# Simulate hot reload by forcing it
result = refresh_localization_if_changed(force=True)
print(f"3. After forced hot reload (result={result}): {get_language()}")

# Check internal state
print(f"4. _current_language: {localization._current_language}")
print(f"5. DEFAULT_LANGUAGE: {localization.DEFAULT_LANGUAGE}")
