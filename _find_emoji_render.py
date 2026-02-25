#!/usr/bin/env python3
"""Find all emoji characters rendered via font.render() or stored in icon dicts."""
import os
import re
from collections import defaultdict

src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')

emoji_pattern = re.compile(
    '['
    '\U0001F300-\U0001F9FF'
    '\U0001FA00-\U0001FAFF'
    '\u2600-\u27BF'
    '\u2300-\u23FF'
    '\u2190-\u21FF'
    '\u25A0-\u25FF'
    '\u2B00-\u2BFF'
    '\u2900-\u297F'
    '\u203C\u2049'
    '\u2122\u2139'
    '\uFE00-\uFE0F'
    '\u200D'
    '\u20E3'
    '\u00A9\u00AE'
    '\u3030\u303D\u3297\u3299'
    '\U0001F004\U0001F0CF'
    '\U0001F170-\U0001F19A'
    '\U0001F1E0-\U0001F1FF'
    '\U0001F200-\U0001F251'
    '\U0001F600-\U0001F64F'
    '\U0001F680-\U0001F6FF'
    '\U0001F700-\U0001F77F'
    '\U0001F900-\U0001F9FF'
    '\uE000-\uF8FF'
    '\u21B2'
    ']'
)

render_pat = re.compile(r'\.render\s*\(')
icon_dict_pat = re.compile(r"""['"]icon['"]\s*:\s*['"](.+?)['"]""")
skip_pat = re.compile(r'emoji_surface|emoji_renderer|get_emoji')
comment_pat = re.compile(r'^\s*#')
print_only_pat = re.compile(r'^\s*print\s*\(')

results = []

for root, dirs, files in os.walk(src_dir):
    for f in files:
        if not f.endswith('.py') or f == 'emoji_renderer.py':
            continue
        fpath = os.path.join(root, f)
        try:
            with open(fpath, 'r', encoding='utf-8') as fh:
                lines = fh.readlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if comment_pat.match(line):
                continue
            emojis = emoji_pattern.findall(line)
            display = [e for e in emojis if ord(e) not in (0xFE0E, 0xFE0F, 0x200D, 0x20E3)]
            if not display:
                continue
            if skip_pat.search(line):
                continue
            if print_only_pat.match(line) and not render_pat.search(line):
                continue
            has_render = bool(render_pat.search(line))
            has_icon = bool(icon_dict_pat.search(line))
            if not has_render and not has_icon:
                continue
            unique = list(dict.fromkeys(display))
            emoji_str = ' '.join(unique)
            ctx = []
            for j in range(max(0, i-3), min(len(lines), i+2)):
                pfx = ">>>" if j == i-1 else "   "
                ctx.append(f"  {pfx} {j+1}: {lines[j].rstrip()}")
            rtype = "DIRECT (.render())" if has_render else "INDIRECT (icon dict)"
            results.append({'file': fpath, 'line': i, 'emojis': emoji_str, 'type': rtype, 'context': '\n'.join(ctx)})

grouped = defaultdict(list)
for r in results:
    grouped[r['file']].append(r)

print(f"\nTOTAL: {len(results)} findings\n")
for fpath in sorted(grouped.keys()):
    rel = os.path.relpath(fpath, os.path.dirname(src_dir))
    print(f"\n--- {rel} ({len(grouped[fpath])} findings) ---")
    for r in grouped[fpath]:
        print(f"\n  Line {r['line']} | Emoji: {r['emojis']} | {r['type']}")
        print(r['context'])
    print()
