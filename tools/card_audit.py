from __future__ import annotations

import re
from pathlib import Path


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _extract_catalog_ids(text: str) -> list[str]:
    head = text.split("class MysteryCardUI", 1)[0]
    # Catalog is a list of dict literals with "id": "...",
    ids = re.findall(r'"id"\s*:\s*"([a-zA-Z0-9_]+)"\s*,', head)
    return _unique_preserve_order(ids)


def _extract_apply_ids(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("if ") or s.startswith("elif ")):
            continue
        if "cid ==" not in s:
            continue
        after = s.split("cid ==", 1)[1].strip()
        if not after:
            continue
        quote = after[0]
        if quote not in ("\"", "'"):
            continue
        try:
            val = after[1:].split(quote, 1)[0]
        except Exception:
            continue
        if val:
            ids.append(val)
    return _unique_preserve_order(ids)


def main() -> None:
    p = Path("src/game_modes_extra.py")
    text = p.read_text(encoding="utf-8", errors="ignore")

    catalog = _extract_catalog_ids(text)
    apply_ids = _extract_apply_ids(text)

    # score is handled by `if cid == "score"` (not an elif match sometimes), but we keep it in both for reporting.
    if "score" not in apply_ids and 'if cid == "score"' in text:
        apply_ids = ["score", *apply_ids]

    missing = [cid for cid in catalog if cid not in apply_ids]
    extra = [cid for cid in apply_ids if cid not in catalog]

    print(f"catalog_count {len(catalog)}")
    print(f"apply_count {len(apply_ids)}")
    print(f"missing {missing}")
    print(f"extra {extra}")


if __name__ == "__main__":
    main()
