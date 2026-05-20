import ast
import re

def get_translations_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'TRANSLATIONS':
                    return ast.literal_eval(node.value)
    return {}

repo1_path = 'src/localization.py'
repo2_path = '../v2/src/localization.py'

trans1 = get_translations_from_file(repo1_path)
trans2 = get_translations_from_file(repo2_path)

keywords = ['tutorial', 'guide', 'daily', 'profile', 'user', 'menu', 'settings', 'loading', 'warning', 'success', 'error', 'confirm', 'cancel', 'select', 'lesson', 'chapter', 'start', 'quick', 'result', 'faq']

results = {}

all_keys = set(trans1.keys()) & set(trans2.keys())

for key in all_keys:
    if not any(kw in key.lower() for kw in keywords):
        continue
    
    t1 = trans1[key]
    t2 = trans2[key]
    
    if 'en' not in t1 or 'en' not in t2:
        continue
        
    en_val1 = t1['en']
    en_val2 = t2['en']
    
    langs1 = {l for l, v in t1.items() if l not in ['en', 'tr'] and v == en_val1}
    langs2 = {l for l, v in t2.items() if l not in ['en', 'tr'] and v == en_val2}
    
    common_langs = langs1 & langs2
    if common_langs:
        results[key] = sorted(list(common_langs))

# Grouping by languages for concise output
grouped = {}
for key, langs in results.items():
    lang_tuple = tuple(langs)
    if lang_tuple not in grouped:
        grouped[lang_tuple] = []
    grouped[lang_tuple].append(key)

for langs, keys in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"Languages: {', '.join(langs)}")
    for k in sorted(keys):
        print(f"  - {k}")
