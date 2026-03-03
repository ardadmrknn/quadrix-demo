"""Find all t() keys used in source that are NOT defined in localization.py."""
import re
import os
import glob

# 1. Extract all defined keys from localization.py
with open('src/localization.py', 'r', encoding='utf-8') as f:
    loc_content = f.read()

defined_keys = set(re.findall(r"    '(\w+)':\s*\{", loc_content))
print(f"Defined keys in localization.py: {len(defined_keys)}")

# 2. Extract all t('key') usages from all .py files in src/ and src/campaign/
used_keys = {}  # key -> list of (file, line_number, line_text)
patterns = [
    r"""t\(\s*['"](\w+)['"]\s*[,\)]""",
    r"""t\(\s*['"](\w+)['"]\s*\)""",
]
combined_pattern = r"""t\(\s*['"](\w+)['"]"""

src_files = glob.glob('src/*.py') + glob.glob('src/campaign/*.py') + glob.glob('src/renderers/*.py') + glob.glob('src/splashscreen/*.py')

for fpath in src_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            for m in re.finditer(combined_pattern, line):
                key = m.group(1)
                if key not in used_keys:
                    used_keys[key] = []
                used_keys[key].append((fpath, i, line.strip()))

print(f"Used keys across codebase: {len(used_keys)}")

# 3. Find missing keys
missing = sorted(set(used_keys.keys()) - defined_keys)
print(f"\n{'='*60}")
print(f"MISSING KEYS (used but not defined): {len(missing)}")
print(f"{'='*60}")
for key in missing:
    locs = used_keys[key]
    print(f"\n  '{key}':")
    for fpath, lineno, text in locs[:3]:  # show first 3 usages
        print(f"    {fpath}:{lineno} -> {text[:100]}")

# 4. Also find hardcoded Turkish text patterns in UI drawing
print(f"\n{'='*60}")
print("POTENTIAL HARDCODED STRINGS (not using t())")
print(f"{'='*60}")
hardcoded_patterns = [
    (r'''(?:draw_text|render|blit_text|font\.render)\s*\(\s*['"]([\wşçğüöıİĞÜŞÇÖ ]+)['"]''', "draw/render calls"),
    (r'''(?:text|label|title|msg|message)\s*=\s*['"]([\wşçğüöıİĞÜŞÇÖ ]{4,})['"]''', "text assignments"),
]

for fpath in src_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            # Skip comment lines and import lines
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('import') or stripped.startswith('from'):
                continue
            # Look for Turkish chars in string literals that are not inside t()
            if 't(' not in line:
                # Find string literals with Turkish characters
                for m in re.finditer(r"""['"]([^'"]*[şçğüöıİĞÜŞÇÖ][^'"]*)['""]""", line):
                    text = m.group(1)
                    if len(text) > 3 and not any(x in line for x in ['#', 'encoding', 'comment', 'native_name']):
                        print(f"  {fpath}:{i} -> {text[:80]}")

# 5. Check which keys are missing languages
print(f"\n{'='*60}")
print("KEYS WITH INCOMPLETE LANGUAGE COVERAGE")
print(f"{'='*60}")
SUPPORTED = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']

# Parse each key and its languages
key_pattern = re.compile(r"    '(\w+)':\s*\{([^}]*)\}", re.DOTALL)
lang_pattern = re.compile(r"'(\w+)':")
incomplete_count = 0
for m in key_pattern.finditer(loc_content):
    key = m.group(1)
    body = m.group(2)
    langs_present = set(lang_pattern.findall(body))
    missing_langs = set(SUPPORTED) - langs_present
    if missing_langs:
        incomplete_count += 1

print(f"Keys with missing language entries: {incomplete_count}")
# Show first 50
count = 0
for m in key_pattern.finditer(loc_content):
    key = m.group(1)
    body = m.group(2)
    langs_present = set(lang_pattern.findall(body))
    missing_langs = sorted(set(SUPPORTED) - langs_present)
    if missing_langs:
        if count < 100:
            print(f"  '{key}': missing {missing_langs}")
            count += 1
