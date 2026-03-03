"""
Generate the list of keys missing for each language (excluding runtime fallback).
Output: JSON mapping lang -> {key: current_english_value}
"""
import json
import sys
import os
sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'

with open('src/localization.py', 'r', encoding='utf-8') as f:
    content = f.read()

SUPPORTED = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']

translations_start = content.index("TRANSLATIONS = {")
translations_end = content.index("\ndef _ensure_language_fallback")
translations_code = content[translations_start:translations_end].rstrip()
ns = {}
exec(translations_code, ns)
raw_translations = ns['TRANSLATIONS']

ru_start = content.index("_RU_TRANSLATIONS = {")
ru_block = content[ru_start:]
ru_end = ru_block.index("\n}")
ru_code = ru_block[:ru_end+2]
ns2 = {}
exec(ru_code, ns2)
ru_trans = ns2['_RU_TRANSLATIONS']

# For each language, list missing keys with their English value
missing_by_lang = {}
for lang in SUPPORTED:
    if lang in ('tr', 'en'):
        continue
    missing = {}
    for key in sorted(raw_translations.keys()):
        if lang not in raw_translations[key]:
            en_val = raw_translations[key].get('en', raw_translations[key].get('tr', key))
            missing[key] = en_val
    # For ru, also check which keys are in _RU_TRANSLATIONS but not in main
    if lang == 'ru':
        # Remove keys that are actually in _RU_TRANSLATIONS
        for k in list(missing.keys()):
            if k in ru_trans:
                missing[k] = f"[HAS_RU] {ru_trans[k]}"
    missing_by_lang[lang] = missing

with open('_missing_by_lang.json', 'w', encoding='utf-8') as f:
    json.dump(missing_by_lang, f, ensure_ascii=False, indent=2)

for lang in SUPPORTED:
    if lang in ('tr', 'en'):
        continue
    m = missing_by_lang[lang]
    print(f"{lang}: {len(m)} missing")
    # Show first 10
    for k in list(m.keys())[:10]:
        print(f"  {k}: {m[k][:80]}")
