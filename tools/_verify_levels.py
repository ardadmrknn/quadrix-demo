import sys, importlib.util
sys.path.insert(0, 'src/campaign')
spec = importlib.util.spec_from_file_location('level_data', 'src/campaign/level_data.py')
m = importlib.util.module_from_spec(spec)
sys.modules['level_data'] = m
spec.loader.exec_module(m)
lvls = m.get_levels()

checks = [
    (1,  'move_limit', None),
    (2,  'move_limit', 19),
    (7,  'objectives', [{'type':'score','target':2100}]),
    (9,  'time_limit', 120),
    (10, 'move_limit', 39),
    (13, 'pre_placed_rows', 2),
    (17, 'move_limit', None),
    (19, 'time_limit', 75),
    (20, 'time_limit', 90),
    (28, 'pre_placed_rows', 0),
    (30, 'move_limit', 80),
    (31, 'pre_placed_rows', 4),
    (70, 'no_hold', True),
    (70, 'cascade_mode', True),
    (100,'pre_placed_rows', 9),
    (100,'cascade_mode', True),
]
ok = True
for lv, field, expected in checks:
    got = getattr(lvls[lv], field)
    status = 'OK' if got == expected else 'FAIL'
    if status == 'FAIL':
        ok = False
        print(f'  {status} L{lv}.{field}: expected={expected}, got={got}')
if ok:
    print(f'Tum {len(checks)} kontrol PASS')
print(f'L44 stars: {lvls[44].stars}')
print(f'L52 stars: {lvls[52].stars}')
print(f'L65 stars: {lvls[65].stars}')
print(f'Toplam level: {len(lvls)}')
