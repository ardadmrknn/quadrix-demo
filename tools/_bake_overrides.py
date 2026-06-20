"""Tek seferlik migrasyon: localization_auto_overrides.json -> localization.py bake.

A yontemi (hedefli byte-range degisimi):
  - AST ile module-level TRANSLATIONS sozlugunu oku.
  - Her anahtarin SON tanimini (Python dict: son kazanir) baz al.
  - Override'daki her (lang, text) icin: dil zaten varsa ve deger FARKLIYSA,
    yalnizca o deger literalini yeni metnin tek-tirnakli literaliyle degistir.
  - insert (yeni dil) gerekmiyor (olculdu: 0). noop (ayni deger) atlanir.
  - Yetim anahtarlar (TRANSLATIONS'da yok) override JSON'da birakilir.

Self-guard: her hedef literalin byte araligi cikarilip literal_eval ile
node degerine esit mi diye dogrulanir; uyusmazlik varsa abort.
"""
import ast
import json
import os

SRC = 'src/localization.py'
OVR = 'src/localization_auto_overrides.json'

# Yetim anahtarlar (override'da var, TRANSLATIONS'da yok) bake sirasinda
# veriden DINAMIK olarak hesaplanir; repo'ya gore degisir (v2: 11, demo: 1).


def py_single_quote(s: str) -> str:
    s = s.replace('\\', '\\\\').replace("'", "\\'")
    s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return "'" + s + "'"


def main():
    raw = open(SRC, 'rb').read()
    text = raw.decode('utf-8')
    tree = ast.parse(text)

    # module-level TRANSLATIONS = {...}
    dict_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'TRANSLATIONS':
                    dict_node = node.value
    if not isinstance(dict_node, ast.Dict):
        raise SystemExit('TRANSLATIONS dict not found')

    # SON tanim kazanir: key -> value dict node
    last_entry = {}
    for k_node, v_node in zip(dict_node.keys, dict_node.values):
        if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str):
            last_entry[k_node.value] = v_node

    # line byte-start tablosu (utf-8 byte offsetleri icin)
    lines = text.splitlines(keepends=True)
    line_byte_start = [0] * (len(lines) + 2)
    acc = 0
    for i, ln in enumerate(lines, start=1):
        line_byte_start[i] = acc
        acc += len(ln.encode('utf-8'))

    def node_byte_range(n):
        assert n.lineno == n.end_lineno, 'multiline literal beklenmiyor'
        start = line_byte_start[n.lineno] + n.col_offset
        end = line_byte_start[n.lineno] + n.end_col_offset
        return start, end

    ovr = json.load(open(OVR, encoding='utf-8'))

    edits = []  # (start, end, new_bytes)
    orphan_keys = set()
    replace = insert = noop = orphan = 0
    for key, langmap in ovr.items():
        v_node = last_entry.get(key)
        if v_node is None:
            orphan += 1
            orphan_keys.add(key)
            continue
        lm = {}
        for lk, lv in zip(v_node.keys, v_node.values):
            if isinstance(lk, ast.Constant) and isinstance(lv, ast.Constant):
                lm[lk.value] = lv
        for lang, new_text in langmap.items():
            cur = lm.get(lang)
            if cur is None:
                insert += 1  # olculdu: 0; olusursa asagida raise
                raise SystemExit(f'beklenmeyen insert: {key}/{lang}')
            if cur.value == new_text:
                noop += 1
                continue
            start, end = node_byte_range(cur)
            # self-guard: araligin gercekten bu literal oldugunu dogrula
            seg = raw[start:end].decode('utf-8')
            if ast.literal_eval(seg) != cur.value:
                raise SystemExit(
                    f'offset uyusmazligi: {key}/{lang}: {seg!r}')
            edits.append((start, end, py_single_quote(new_text).encode('utf-8')))
            replace += 1

    print(f'replace={replace} insert={insert} noop={noop} orphan={orphan}')

    # cakisma kontrolu + descending splice
    edits.sort(key=lambda e: e[0])
    for a, b in zip(edits, edits[1:]):
        if a[1] > b[0]:
            raise SystemExit('overlapping edit ranges')

    new_raw = raw
    for start, end, rep in sorted(edits, key=lambda e: e[0], reverse=True):
        new_raw = new_raw[:start] + rep + new_raw[end:]

    # son kontrol: yeni dosya gecerli Python mi
    ast.parse(new_raw.decode('utf-8'))

    open(SRC, 'wb').write(new_raw)
    print(f'WROTE {SRC} ({len(raw)} -> {len(new_raw)} bytes)')

    # JSON'u yalnizca yetim anahtarlara indir (icerigi aynen koru)
    reduced = {k: ovr[k] for k in ovr if k in orphan_keys}
    if set(reduced) != orphan_keys:
        raise SystemExit(f'orphan tutarsiz: {set(reduced) ^ orphan_keys}')
    json.dump(reduced, open(OVR, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=4, sort_keys=True)
    print(f'WROTE {OVR} (kept {len(reduced)} orphan keys: {sorted(orphan_keys)})')


if __name__ == '__main__':
    main()
