"""Tutorial localization anahtar denetimi (fallback eşlemeli).

Tutorial kod + veri dosyalarında referans verilen tüm localization anahtarlarını
toplar, localization.py:TRANSLATIONS ile karşılaştırır ve EKSİK olanların yanına
veri dosyasındaki mevcut fallback/kaynak metnini (TR) ekler.

Çıktı: tools/_audit_missing_keys.json  (md üretimi için yapısal veri)
"""
from __future__ import annotations

import ast
import json
import os
import sys

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, SRC)


def load_translation_keys() -> set[str]:
    with open(os.path.join(SRC, "localization.py"), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TRANSLATIONS":
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                keys.add(k.value)
    return keys


def _const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # bitişik string birleştirme ("a" "b") JoinedStr değil BinOp/Constant olabilir
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_str(node.left)
        right = _const_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


# key alanı -> fallback alanı eşleme kuralları (aynı sözlük içinde)
PAIR_SUFFIX = {
    "goal_key": ["goal_text", "goal_fallback"],
    "tip_key": ["tip_text", "tip_fallback"],
    "title_key": ["title_fallback"],
    "description_key": ["description_fallback"],
    "body_key": ["body_fallback"],
}


def collect_data_pairs(filename: str) -> dict[str, str]:
    """key -> fallback metni eşlemesi döndürür."""
    with open(os.path.join(SRC, filename), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    result: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        # bu sözlüğün alanlarını topla
        fields: dict[str, ast.AST] = {}
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                fields[k.value] = v

        for field_name, value in fields.items():
            # 1) _key/_fallback çiftleri
            if field_name in PAIR_SUFFIX:
                key_str = _const_str(value)
                if key_str:
                    fallback = ""
                    for fb_field in PAIR_SUFFIX[field_name]:
                        if fb_field in fields:
                            fb_val = _const_str(fields[fb_field])
                            if fb_val:
                                fallback = fb_val
                                break
                    result[key_str] = fallback
            # 2) genel *_key (yukarıdakiler dışında) — eşsiz fallback yoksa boş
            elif field_name.endswith("_key"):
                key_str = _const_str(value)
                if key_str:
                    result.setdefault(key_str, "")
            # 3) context_keys (liste) <-> context_lines (liste)
            elif field_name == "context_keys" and isinstance(value, (ast.List, ast.Tuple)):
                lines = fields.get("context_lines")
                line_vals = []
                if isinstance(lines, (ast.List, ast.Tuple)):
                    line_vals = [(_const_str(e) or "") for e in lines.elts]
                for idx, elt in enumerate(value.elts):
                    ks = _const_str(elt)
                    if ks:
                        result[ks] = line_vals[idx] if idx < len(line_vals) else ""
            # 4) feedback_keys_by_card (map) <-> feedback_by_card (map)
            elif field_name == "feedback_keys_by_card" and isinstance(value, ast.Dict):
                fb_map = fields.get("feedback_by_card")
                fb_lookup: dict[str, str] = {}
                if isinstance(fb_map, ast.Dict):
                    for fk, fv in zip(fb_map.keys, fb_map.values):
                        ck = _const_str(fk)
                        cv = _const_str(fv)
                        if ck is not None:
                            fb_lookup[ck] = cv or ""
                for ck_node, kv_node in zip(value.keys, value.values):
                    card_id = _const_str(ck_node)
                    key_str = _const_str(kv_node)
                    if key_str:
                        result[key_str] = fb_lookup.get(card_id or "", "")
    return result


def collect_t_call_keys(filename: str) -> dict[str, str]:
    """tutorial.py içindeki t('lit', default='...') -> default eşlemesi."""
    with open(os.path.join(SRC, filename), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("t", "get_text"):
            if not node.args:
                continue
            key_str = _const_str(node.args[0])
            if not key_str:
                continue
            default_val = ""
            if len(node.args) >= 2:
                default_val = _const_str(node.args[1]) or ""
            for kw in node.keywords:
                if kw.arg == "default":
                    default_val = _const_str(kw.value) or default_val
            # aynı anahtar birden çok yerde olabilir; dolu default'u tercih et
            if key_str not in result or (default_val and not result[key_str]):
                result[key_str] = default_val
    return result


def main():
    trans = load_translation_keys()

    tutorial = collect_t_call_keys("tutorial.py")
    lessons = collect_data_pairs("tutorial_lessons.py")
    scenarios = collect_data_pairs("tutorial_scenarios.py")
    cards = collect_data_pairs("tutorial_cards.py")

    sources = {
        "tutorial.py": tutorial,
        "tutorial_lessons.py": lessons,
        "tutorial_scenarios.py": scenarios,
        "tutorial_cards.py": cards,
    }

    # birleşik referans seti
    all_keys: dict[str, dict] = {}
    for src_name, mapping in sources.items():
        for key, fallback in mapping.items():
            entry = all_keys.setdefault(key, {"sources": [], "fallback": ""})
            entry["sources"].append(src_name)
            if fallback and not entry["fallback"]:
                entry["fallback"] = fallback

    missing = {k: v for k, v in all_keys.items() if k not in trans}

    out = {
        "translations_total": len(trans),
        "referenced_total": len(all_keys),
        "missing_total": len(missing),
        "missing": {k: missing[k] for k in sorted(missing)},
    }
    out_path = os.path.join(os.path.dirname(__file__), "_audit_missing_keys.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("WROTE", out_path)
    print("translations_total", len(trans))
    print("referenced_total", len(all_keys))
    print("missing_total", len(missing))


if __name__ == "__main__":
    main()
