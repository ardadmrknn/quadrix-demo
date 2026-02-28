"""Find ALL keys in the game where RU == EN (fallback, not real translation)."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS

# Scan all py files in src/ for t() and _t() calls
src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
all_keys = set()
for root, dirs, files in os.walk(src_dir):
    for f in files:
        if not f.endswith('.py'):
            continue
        fpath = os.path.join(root, f)
        content = open(fpath, 'r', encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r"(?:_t|(?<!_)t)\(\s*['\"]([^'\"]+)['\"]", content):
            all_keys.add(m.group(1))
        for m in re.finditer(r"'loc_key'\s*:\s*'([^']+)'", content):
            all_keys.add(m.group(1))

# Filter: in TRANSLATIONS, RU == EN
en_fallback = {}
for k in sorted(all_keys):
    if k in TRANSLATIONS:
        en_val = TRANSLATIONS[k].get('en', '')
        ru_val = TRANSLATIONS[k].get('ru', '')
        if en_val and ru_val == en_val:
            en_fallback[k] = en_val

print(f"Total keys referenced in src/**/*.py: {len(all_keys)}")
print(f"Keys where RU == EN (needs real translation): {len(en_fallback)}")
print()
for k, en in en_fallback.items():
    print(f"    '{k}': '',  # EN: {en}")
