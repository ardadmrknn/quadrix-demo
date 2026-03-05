"""Minimal override dict üret - sadece auto-gen'den farklı olan alanları yazar."""
import sys, importlib.util, pprint

spec = importlib.util.spec_from_file_location('level_data', 'src/campaign/level_data.py')
m = importlib.util.module_from_spec(spec)
sys.modules['level_data'] = m
spec.loader.exec_module(m)

ov = m._LEVEL_OVERRIDES
minimal = {}

for lv in range(1, 101):
    is_boss = lv % 10 == 0
    world = m._get_world(lv)
    objectives = m._generate_objectives(lv, world, is_boss)
    stars = m._generate_star_conditions(lv, objectives)
    garbage_rows = m._calculate_garbage_rows(lv, is_boss)
    garbage_pattern = m._get_garbage_pattern(lv)
    no_hold = lv >= 70 and (lv % 7 == 0)
    cascade_mode = lv >= 50 and (lv % 5 == 0)
    time_limit = None
    if lv >= 30 and lv % 6 == 0:
        time_limit = max(60, 180 - (lv - 30) * 2)
    move_limit = m._calculate_block_limit(lv, objectives, is_boss)

    o = ov.get(lv, {})
    if not o:
        continue

    entry = {}
    if 'objectives' in o and o['objectives'] != objectives:
        entry['objectives'] = o['objectives']
    if 'move_limit' in o and o['move_limit'] != move_limit:
        entry['move_limit'] = o['move_limit']
    if 'time_limit' in o and o['time_limit'] != time_limit:
        entry['time_limit'] = o['time_limit']
    if 'garbage_rows' in o and o['garbage_rows'] != garbage_rows:
        entry['garbage_rows'] = o['garbage_rows']
    if 'garbage_pattern' in o and o['garbage_pattern'] != garbage_pattern:
        entry['garbage_pattern'] = o['garbage_pattern']
    if 'no_hold' in o and o['no_hold'] != no_hold:
        entry['no_hold'] = o['no_hold']
    if 'cascade_mode' in o and o['cascade_mode'] != cascade_mode:
        entry['cascade_mode'] = o['cascade_mode']
    if 'stars' in o and o['stars'] != stars:
        entry['stars'] = o['stars']

    if entry:
        minimal[lv] = entry

# Özet
total_keys = sum(len(v) for v in minimal.values())
full_keys = sum(len(v) for v in ov.values())
print(f"Tam override: {sum(1 for v in ov.values() if v)} level, ~{full_keys} alan")
print(f"Minimal override: {len(minimal)} level, ~{total_keys} alan")
print(f"Tasarruf: {full_keys - total_keys} alan ({100*(full_keys-total_keys)//full_keys}%)")

# Hangi levellar tamamen kaldırılabilir?
removed = [lv for lv in ov if lv not in minimal]
print(f"Override'dan tamamen çıkan levellar: {removed}")
