import sys, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# Hot-reload kapat: deterministik dump
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'
from localization import TRANSLATIONS
json.dump(TRANSLATIONS, open(sys.argv[1], 'w', encoding='utf-8'),
          ensure_ascii=False, sort_keys=True, indent=2)
print('dumped', len(TRANSLATIONS), 'keys ->', sys.argv[1])
