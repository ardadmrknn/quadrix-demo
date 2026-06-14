"""Check which loc_keys from settings_screen_tabbed.py are missing in TRANSLATIONS."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS

content = open(os.path.join(os.path.dirname(__file__), '..', 'src', 'settings_screen_tabbed.py'), 'r', encoding='utf-8').read()

keys = set()
# loc_key values
for m in re.finditer(r"'loc_key'\s*:\s*'([^']+)'", content):
    keys.add(m.group(1))
# _t('key') calls
for m in re.finditer(r"_t\('([^']+)'", content):
    keys.add(m.group(1))
# t('key') calls (not _t)
for m in re.finditer(r"(?<!_)t\('([^']+)'", content):
    keys.add(m.group(1))

missing = sorted(k for k in keys if k not in TRANSLATIONS)
print(f"Total unique keys: {len(keys)}")
print(f"Missing from TRANSLATIONS: {len(missing)}")
for k in missing:
    print(f"  MISSING: {k}")

# Also check music_shuffle specifically
print(f"\nmusic_shuffle in TRANSLATIONS: {'music_shuffle' in TRANSLATIONS}")

# Check all gamepad gp_ keys
gp_keys = sorted(k for k in keys if k.startswith('gp_'))
print(f"\nGamepad keys ({len(gp_keys)}):")
for k in gp_keys:
    print(f"  {k:45s} exists={k in TRANSLATIONS}")
