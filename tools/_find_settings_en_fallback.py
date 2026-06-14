"""Find settings keys where RU translation == EN (fallback, not real translation)."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS

content = open(os.path.join(os.path.dirname(__file__), '..', 'src', 'settings_screen_tabbed.py'), 'r', encoding='utf-8').read()
keys = set()
for m in re.finditer(r"'loc_key'\s*:\s*'([^']+)'", content):
    keys.add(m.group(1))
for m in re.finditer(r"_t\('([^']+)'", content):
    keys.add(m.group(1))

en_fallback = []
has_real_ru = []
for k in sorted(keys):
    if k in TRANSLATIONS:
        en_val = TRANSLATIONS[k].get('en', '')
        ru_val = TRANSLATIONS[k].get('ru', '')
        tr_val = TRANSLATIONS[k].get('tr', '')
        if ru_val == en_val and en_val:
            en_fallback.append((k, en_val, tr_val))
        elif ru_val and ru_val != en_val:
            has_real_ru.append((k, ru_val))

print(f"Keys with EN fallback as RU ({len(en_fallback)}):")
for k, en, tr in en_fallback:
    print(f"  {k:45s}  en={en!r:30s}  tr={tr!r}")

print(f"\nKeys with real RU ({len(has_real_ru)}):")
for k, ru in has_real_ru:
    print(f"  {k:45s}  ru={ru!r}")
