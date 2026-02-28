import sys, os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from localization import TRANSLATIONS
with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'localization.py'), 'r', encoding='utf-8') as f:
    content = f.read()
ru_count = content.count("'ru':")
total = len(TRANSLATIONS)
print(f"Toplam anahtar: {total}")
print(f"Kaynak dosyada 'ru' girdisi: {ru_count}")
print(f"Sadece runtime fallback ile dolu: {total - ru_count}")
# Print first 20 keys that lack 'ru' in source
missing_in_source = []
for key in TRANSLATIONS:
    marker = f"'{key}'"
    idx = content.find(f"'{key}':")
    if idx == -1:
        idx = content.find(f'"{key}":')
    if idx == -1:
        continue
    # Find the block for this key
    block_start = idx
    block_end = content.find("    },", block_start)
    if block_end == -1:
        block_end = block_start + 200
    block = content[block_start:block_end]
    if "'ru'" not in block:
        missing_in_source.append(key)
print(f"\nSource'da 'ru' girdisi olmayan ilk 20 anahtar:")
for k in missing_in_source[:20]:
    en = TRANSLATIONS[k].get('en', '')[:50]
    print(f"  {k}: {en}")
