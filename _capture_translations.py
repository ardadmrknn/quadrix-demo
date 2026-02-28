"""
Capture the runtime-resolved TRANSLATIONS (after all fallbacks + RU merge)
and output a JSON file for analysis.
"""
import json
import sys
import os
sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'

from localization import TRANSLATIONS, SUPPORTED_LANGUAGES

# Capture full state
result = {}
for key in sorted(TRANSLATIONS.keys()):
    entry = TRANSLATIONS[key]
    result[key] = {}
    for lang in SUPPORTED_LANGUAGES:
        result[key][lang] = entry.get(lang, '')

with open('_translations_full.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Stats
total = len(result)
print(f"Total keys: {total}")
for lang in SUPPORTED_LANGUAGES:
    count = sum(1 for k in result if result[k].get(lang))
    print(f"  {lang}: {count}/{total}")
