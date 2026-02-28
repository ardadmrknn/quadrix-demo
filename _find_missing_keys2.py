"""Find all t() keys used in source that are NOT defined in localization.py.
Only matches standalone t('key') or localization.t('key') calls."""
import re
import os
import glob
import sys

# 1. Extract all defined keys from localization.py
with open('src/localization.py', 'r', encoding='utf-8') as f:
    loc_content = f.read()

defined_keys = set(re.findall(r"    '(\w+)':\s*\{", loc_content))
print(f"Defined keys in localization.py: {len(defined_keys)}")

# 2. Extract all t('key') usages - only standalone t() function or localization.t()
# Pattern: either line starts context showing it's a t() call, or word boundary before t(
combined_pattern = r"""(?<![.\w])t\(\s*['"](\w+)['"]"""
# Also match localization.t()
alt_pattern = r"""localization\.t\(\s*['"](\w+)['"]"""

src_files = glob.glob('src/*.py') + glob.glob('src/campaign/*.py') + glob.glob('src/renderers/*.py') + glob.glob('src/splashscreen/*.py')

used_keys = {}  # key -> list of (file, line_number, line_text)

for fpath in src_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            for pat in [combined_pattern, alt_pattern]:
                for m in re.finditer(pat, line):
                    key = m.group(1)
                    if key not in used_keys:
                        used_keys[key] = []
                    used_keys[key].append((fpath, i, line.strip()))

print(f"Used t() keys across codebase: {len(used_keys)}")

# 3. Find missing keys
missing = sorted(set(used_keys.keys()) - defined_keys)
print(f"\nMISSING KEYS (used in t() but not defined): {len(missing)}")
for key in missing:
    locs = used_keys[key]
    print(f"\n  '{key}':")
    for fpath, lineno, text in locs[:3]:
        print(f"    {fpath}:{lineno} -> {text[:120]}")

# 4. Check which keys have incomplete language coverage
print(f"\n{'='*60}")
print("KEYS WITH INCOMPLETE LANGUAGE COVERAGE (first 200)")
print(f"{'='*60}")
SUPPORTED = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']

key_blocks = re.findall(r"    '(\w+)':\s*\{([^}]*)\}", loc_content)
incomplete_count = 0
incomplete_keys = []
for key, body in key_blocks:
    langs_present = set(re.findall(r"'(\w+)':", body))
    missing_langs = sorted(set(SUPPORTED) - langs_present)
    if missing_langs:
        incomplete_count += 1
        incomplete_keys.append((key, missing_langs, langs_present))

print(f"Total keys with missing languages: {incomplete_count}")
for key, miss, present in incomplete_keys[:200]:
    print(f"  '{key}': missing {miss}")

sys.exit(0)
