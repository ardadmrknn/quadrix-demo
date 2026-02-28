import json
with open('_missing_by_lang.json','r',encoding='utf-8') as f:
    d=json.load(f)
eu_keys = set()
for lang in ['de','fr','es','it','pt']:
    eu_keys.update(d[lang].keys())
print(f'Unique EU missing keys: {len(eu_keys)}')
for k in sorted(eu_keys):
    v = d.get('de',{}).get(k, d.get('it',{}).get(k, ''))
    print(f'  {k}: {v[:80]}')
