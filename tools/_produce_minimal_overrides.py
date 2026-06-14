"""Minimal _LEVEL_OVERRIDES Python kodunu üret."""
import sys, importlib.util, textwrap

spec = importlib.util.spec_from_file_location('level_data', 'src/campaign/level_data.py')
m = importlib.util.module_from_spec(spec)
sys.modules['level_data'] = m
spec.loader.exec_module(m)

ov = m._LEVEL_OVERRIDES

def repr_star(s):
    t = s['type']
    v = s.get('value')
    d = s.get('description', {})
    tr = d.get('tr', '')
    en = d.get('en', '')
    if t == 'complete':
        return '_cs()'
    if t == 'time_limit':
        return f'_ct({v})'
    if t == 'combo' and 'value' in s:
        return f'_cm({v})'
    if t == 'multi_clear':
        return f'_mc({v})'
    if t == 'tetris' and 'value' in s:
        return f'_qx({v})' if v > 1 else '_qx()'
    if t == 'move_limit':
        return f'_mv({v})'
    return repr(s)

def repr_stars(stars):
    parts = []
    for k in sorted(stars):
        parts.append(f'{k}: {repr_star(stars[k])}')
    return '{' + ', '.join(parts) + '}'

def repr_obj(o):
    t = o['type']
    tgt = o.get('target')
    if t == 'clear_lines': return f'_obj_lines({tgt})'
    if t == 'score': return f'_obj_score({tgt})'
    if t == 'tetris': return f'_obj_tetris({tgt})'
    if t == 'combo': return f'_obj_combo({tgt})'
    if t == 'clear_garbage': return '_obj_garbage()'
    if t == 'survival': return f'_obj_survival({tgt})'
    if t == 'multi_clear': return f'_obj_multi_clear({tgt})'
    if t == 'time_challenge': return f'_obj_time_challenge({tgt})'
    if t == 'special_block': return f'_obj_special_block({tgt})'
    return repr(o)

def repr_objs(objs):
    return '[' + ', '.join(repr_obj(o) for o in objs) + ']'

lines = []
lines.append('_LEVEL_OVERRIDES: Dict[int, Dict[str, Any]] = {')

# Dünya başlıkları
world_starts = {1: 'DÜNYA 1: BAŞLANGIÇ VADİSİ', 21: 'DÜNYA 2: BUZ DİYARI',
                41: 'DÜNYA 3: LAV MAĞARASI', 61: 'DÜNYA 4: FIRTINA KALESİ', 81: 'DÜNYA 5: YILDIZ KULESİ'}

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

    # Gerçek garbage_rows (override varsa onu al, yoksa auto)
    eff_garbage_rows = o.get('garbage_rows', garbage_rows)

    entry_parts = []
    if 'objectives' in o and o['objectives'] != objectives:
        entry_parts.append(f"'objectives': {repr_objs(o['objectives'])}")
    if 'move_limit' in o and o['move_limit'] != move_limit:
        ml = o['move_limit']
        entry_parts.append(f"'move_limit': {ml}")
    if 'time_limit' in o and o['time_limit'] != time_limit:
        tl = o['time_limit']
        entry_parts.append(f"'time_limit': {tl}")
    if 'garbage_rows' in o and o['garbage_rows'] != garbage_rows:
        entry_parts.append(f"'garbage_rows': {o['garbage_rows']}")
    # garbage_pattern sadece anlamlı garbage var (>0) ise yaz
    if 'garbage_pattern' in o and o['garbage_pattern'] != garbage_pattern and eff_garbage_rows > 0:
        entry_parts.append(f"'garbage_pattern': '{o['garbage_pattern']}'")
    if 'no_hold' in o and o['no_hold'] != no_hold:
        entry_parts.append(f"'no_hold': {o['no_hold']}")
    if 'cascade_mode' in o and o['cascade_mode'] != cascade_mode:
        entry_parts.append(f"'cascade_mode': {o['cascade_mode']}")
    if 'stars' in o and o['stars'] != stars:
        entry_parts.append(f"'stars': {repr_stars(o['stars'])}")

    if not entry_parts:
        continue  # tamamen gereksiz

    if lv in world_starts:
        lines.append(f'    # ─── {world_starts[lv]} ' + '─' * (45 - len(world_starts[lv])))
    
    boss_tag = '  # BOSS' if is_boss else ''
    lines.append(f'    {lv}: {{{", ".join(entry_parts)}}},{boss_tag}')

lines.append('}')

print('\n'.join(lines))
