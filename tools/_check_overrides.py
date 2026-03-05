"""Override vs auto-gen fark analizi"""
import sys
sys.path.insert(0, 'src/campaign')
import importlib.util

spec = importlib.util.spec_from_file_location('level_data', 'src/campaign/level_data.py')
m = importlib.util.module_from_spec(spec)
sys.modules['level_data'] = m
spec.loader.exec_module(m)

ov = m._LEVEL_OVERRIDES

diffs_per_level = {}
redundant = []

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
    diffs = {}

    if 'objectives' in o and o['objectives'] != objectives:
        diffs['objectives'] = True
    if 'move_limit' in o and o['move_limit'] != move_limit:
        diffs['move_limit'] = (move_limit, o['move_limit'])
    elif 'move_limit' in o and o['move_limit'] == move_limit:
        redundant.append(f'L{lv} move_limit={move_limit} (aynı)')
    if 'time_limit' in o and o['time_limit'] != time_limit:
        diffs['time_limit'] = (time_limit, o['time_limit'])
    elif 'time_limit' in o and o['time_limit'] == time_limit:
        redundant.append(f'L{lv} time_limit={time_limit} (aynı)')
    if 'garbage_rows' in o and o['garbage_rows'] != garbage_rows:
        diffs['garbage_rows'] = (garbage_rows, o['garbage_rows'])
    elif 'garbage_rows' in o and o['garbage_rows'] == garbage_rows:
        redundant.append(f'L{lv} garbage_rows={garbage_rows} (aynı)')
    if 'garbage_pattern' in o and o['garbage_pattern'] != garbage_pattern:
        diffs['garbage_pattern'] = (garbage_pattern, o['garbage_pattern'])
    elif 'garbage_pattern' in o and o['garbage_pattern'] == garbage_pattern:
        redundant.append(f'L{lv} garbage_pattern={garbage_pattern} (aynı)')
    if 'no_hold' in o and o['no_hold'] != no_hold:
        diffs['no_hold'] = (no_hold, o['no_hold'])
    elif 'no_hold' in o and o['no_hold'] == no_hold:
        redundant.append(f'L{lv} no_hold={no_hold} (aynı)')
    if 'cascade_mode' in o and o['cascade_mode'] != cascade_mode:
        diffs['cascade_mode'] = (cascade_mode, o['cascade_mode'])
    elif 'cascade_mode' in o and o['cascade_mode'] == cascade_mode:
        redundant.append(f'L{lv} cascade_mode={cascade_mode} (aynı)')
    if 'stars' in o and o['stars'] != stars:
        diffs['stars'] = True

    if diffs:
        diffs_per_level[lv] = list(diffs.keys())

print("=== GERÇEKTEN FARKLI OLAN ALANLAR ===")
for lv, fields in sorted(diffs_per_level.items()):
    print(f"  L{lv:3d}: {', '.join(fields)}")

print(f"\nToplam farklı level: {len(diffs_per_level)}")
print(f"Toplam override satır sayısı (gereksiz): {len(redundant)}")
if redundant:
    print("\n=== GEREKSİZ (aynı değer) OVERRIDES (ilk 30) ===")
    for r in redundant[:30]:
        print(f"  {r}")
