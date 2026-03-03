"""
Analyze which keys have real translations vs English fallback for each language.
"""
import json
import sys
import os
import re
sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'

# Read raw TRANSLATIONS before fallback by parsing the file
with open('src/localization.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract TRANSLATIONS block (line 101 to ~9927)
# We need to parse it structurally
SUPPORTED = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']

# Use a modified approach - exec just the TRANSLATIONS dict
translations_start = content.index("TRANSLATIONS = {")
translations_end = content.index("\ndef _ensure_language_fallback")
translations_code = content[translations_start:translations_end].rstrip()

# Execute to get the raw dict (before any fallback)
ns = {}
exec(translations_code, ns)
raw_translations = ns['TRANSLATIONS']

print(f"Raw keys (before fallback): {len(raw_translations)}")

# For each language, count keys with explicit entries
for lang in SUPPORTED:
    explicit_count = sum(1 for key in raw_translations if lang in raw_translations[key])
    print(f"  {lang}: {explicit_count}/{len(raw_translations)} explicit")

# Also parse _RU_TRANSLATIONS
ru_start = content.index("_RU_TRANSLATIONS = {")
ru_block = content[ru_start:]
ru_end = ru_block.index("\n}")
ru_code = ru_block[:ru_end+2]
ns2 = {}
exec(ru_code, ns2)
ru_trans = ns2['_RU_TRANSLATIONS']
print(f"\n_RU_TRANSLATIONS entries: {len(ru_trans)}")

# Check how many RU entries are NOT in main dict
ru_not_in_main = sum(1 for k in ru_trans if k in raw_translations and 'ru' not in raw_translations[k])
print(f"  RU entries that would be added to main dict: {ru_not_in_main}")

# Keys that de,fr,es,it,pt are using English fallback
for lang in ['de', 'fr', 'es', 'it', 'pt']:
    fallback_count = sum(1 for key in raw_translations if lang not in raw_translations[key])
    print(f"  {lang} using fallback: {fallback_count}/{len(raw_translations)}")

# Find keys where de/fr/es/it/pt have real (non-English) entries
print("\nKeys where de/fr/es/it/pt have real entries:")
for lang in ['de', 'fr', 'es', 'it', 'pt']:
    real = [key for key in raw_translations if lang in raw_translations[key]]
    print(f"  {lang}: {len(real)} keys with explicit entries")
    if real[:5]:
        for k in real[:5]:
            print(f"    {k}: {raw_translations[k][lang][:60]}")
