#!/usr/bin/env python3
"""Generate localization overrides for English-identical translations.

This script reads src/localization.py, detects entries where a target language
has the exact same value as English, translates those phrases using the
Google translate web endpoint, and writes src/localization_auto_overrides.json.

The process is resumable per language using cache files under /tmp.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

SUPPORTED_DEFAULT = ["tr", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ko"]
SEP = "__QXSEP123__"
PH_RE = re.compile(r"\{[^{}]+\}")
BRACKET_RE = re.compile(r"\[[^\[\]\n]{1,20}\]")
_PROTECTED_TERMS = [
    "ESC", "ENTER", "TAB", "SPACE", "SHIFT", "LSHIFT", "RSHIFT",
    "CTRL", "CMD", "ALT", "DEL", "BACKSPACE", "WASD", "PVP", "P2P",
    "STEAM", "QUADRIX", "RGB", "HSV", "FPS", "HZ", "LT", "RT",
]
TERM_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(re.escape(t) for t in sorted(_PROTECTED_TERMS, key=len, reverse=True)) + r")(?![A-Za-z0-9])",
)


def parse_localization(path: Path):
    text = path.read_text(encoding="utf-8")
    mod = ast.parse(text)
    supported = None
    translations = None
    for node in mod.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SUPPORTED_LANGUAGES":
                    supported = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id == "TRANSLATIONS":
                    translations = ast.literal_eval(node.value)
    if supported is None or translations is None:
        raise RuntimeError("Could not parse SUPPORTED_LANGUAGES/TRANSLATIONS")
    return supported, translations


def should_translate(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"[A-Za-z]", text))


def protect_tokens(text: str):
    tokens: list[tuple[str, str]] = []

    def _sub(match: re.Match[str]) -> str:
        idx = len(tokens)
        token = f"__QXPH{idx}__"
        tokens.append((token, match.group(0)))
        return token

    out = PH_RE.sub(_sub, text)
    out = BRACKET_RE.sub(_sub, out)
    out = TERM_RE.sub(_sub, out)
    return out, tokens


def restore_tokens(text: str, tokens: list[tuple[str, str]]) -> str:
    out = text
    for token, raw in tokens:
        out = out.replace(token, raw)
    return out


def translate_batch(strings: list[str], target_lang: str) -> list[str]:
    if not strings:
        return []
    query = f"\n{SEP}\n".join(strings)
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": target_lang,
        "dt": "t",
        "q": query,
    }
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    joined = "".join(part[0] for part in data[0])
    return joined.split(f"\n{SEP}\n")


def translate_phrases_for_lang(lang: str, phrases: list[str], batch_size: int, pause_sec: float) -> dict[str, str]:
    cache_path = Path(f"/tmp/quadrix_loc_phrase_cache_{lang}.json")
    cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    pending = [p for p in phrases if p not in cache]
    total = len(phrases)
    print(f"[{lang}] total={total} cached={len(cache)} pending={len(pending)}")

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        protected: list[str] = []
        token_maps: list[list[tuple[str, str]]] = []
        for phrase in batch:
            safe, tokens = protect_tokens(phrase)
            protected.append(safe)
            token_maps.append(tokens)

        translated: list[str] | None = None
        for attempt in range(1, 6):
            try:
                translated = translate_batch(protected, lang)
                if len(translated) != len(batch):
                    raise RuntimeError(
                        f"Batch mismatch for {lang}: in={len(batch)} out={len(translated)}"
                    )
                break
            except Exception as exc:
                if attempt == 5:
                    print(f"[{lang}] batch failed permanently at index {i}: {exc}")
                else:
                    backoff = min(3.0, 0.35 * attempt)
                    time.sleep(backoff)

        if translated is None:
            # Fallback to single requests for this batch.
            translated = []
            for phrase in batch:
                safe, tokens = protect_tokens(phrase)
                single_text = phrase
                for attempt in range(1, 6):
                    try:
                        out = translate_batch([safe], lang)[0]
                        single_text = restore_tokens(out, tokens).strip() or phrase
                        break
                    except Exception:
                        if attempt < 5:
                            time.sleep(min(3.0, 0.4 * attempt))
                translated.append(single_text)
        else:
            translated = [restore_tokens(t, toks).strip() for t, toks in zip(translated, token_maps)]

        for src, dst in zip(batch, translated):
            cache[src] = dst or src

        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        done = min(i + len(batch), len(pending))
        if done % 100 == 0 or done == len(pending):
            print(f"[{lang}] progress {done}/{len(pending)}")

        time.sleep(pause_sec)

    return cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="*", default=SUPPORTED_DEFAULT)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--pause", type=float, default=0.08)
    args = parser.parse_args()

    src_path = Path("src/localization.py")
    supported, translations = parse_localization(src_path)

    for lang in args.langs:
        if lang not in supported:
            raise RuntimeError(f"Unsupported lang: {lang}")
        if lang == "en":
            raise RuntimeError("English cannot be target for overrides")

    overrides_path = Path("src/localization_auto_overrides.json")
    overrides: dict[str, dict[str, str]] = {}
    if overrides_path.exists():
        try:
            loaded = json.loads(overrides_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                overrides = loaded
        except Exception:
            overrides = {}

    for lang in args.langs:
        phrases: list[str] = []
        seen: set[str] = set()
        for key, entry in translations.items():
            en = entry.get("en", "")
            current = entry.get(lang, "")
            if current == en and should_translate(en):
                if en not in seen:
                    seen.add(en)
                    phrases.append(en)

        phrase_map = translate_phrases_for_lang(lang, phrases, args.batch_size, args.pause)

        updated = 0
        for key, entry in translations.items():
            en = entry.get("en", "")
            current = entry.get(lang, "")
            if current == en and should_translate(en):
                new_val = phrase_map.get(en, en)
                if new_val and new_val != current:
                    overrides.setdefault(key, {})[lang] = new_val
                    updated += 1
        print(f"[{lang}] override_updates={updated}")

        overrides_path.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    # Write audit summary
    summary = {
        "total_keys": len(translations),
        "same_as_en_before": {},
        "same_as_en_after": {},
        "overridden_key_count": len(overrides),
        "langs_processed": args.langs,
    }

    for lang in supported:
        if lang == "en":
            continue
        before = 0
        after = 0
        for key, entry in translations.items():
            en = entry.get("en", "")
            cur = entry.get(lang, "")
            if cur == en:
                before += 1
                post = overrides.get(key, {}).get(lang, cur)
                if post == en:
                    after += 1
        summary["same_as_en_before"][lang] = before
        summary["same_as_en_after"][lang] = after

    report_path = Path("reports/localization_audit_2026-04-07.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OVERRIDES={overrides_path}")
    print(f"REPORT={report_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
