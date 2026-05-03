"""High-signal localization semantic guards."""

import os
from pathlib import Path
import string
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("TETRIS_LOCALIZATION_HOT_RELOAD", "0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

if "localization" in sys.modules and not hasattr(sys.modules["localization"], "TRANSLATIONS"):
    del sys.modules["localization"]

from localization import SUPPORTED_LANGUAGES, TRANSLATIONS


def _format_fields(text: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in string.Formatter().parse(str(text)):
        if field_name is None:
            continue
        fields.add(field_name.split(".", 1)[0].split("[", 1)[0] or "__positional__")
    return fields


def test_all_language_placeholders_match_english():
    errors = []
    for key, translations in TRANSLATIONS.items():
        english_fields = _format_fields(translations.get("en", ""))
        for lang in SUPPORTED_LANGUAGES:
            if lang == "en":
                continue
            lang_fields = _format_fields(translations.get(lang, ""))
            if lang_fields != english_fields:
                errors.append(f"{key}[{lang}] EN={english_fields} LANG={lang_fields}")

    assert not errors, "Placeholder drift:\n" + "\n".join(errors)


def test_quadrix_brand_is_not_retranslated_as_legacy_tetris():
    legacy_terms = {
        "ja": "テトリス",
        "zh": "俄罗斯方块",
        "ko": "테트리스",
    }

    errors = []
    for key, translations in TRANSLATIONS.items():
        english = str(translations.get("en", ""))
        turkish = str(translations.get("tr", ""))
        if "Quadrix" not in english and "QUADRIX" not in english and "Quadrix" not in turkish and "QUADRIX" not in turkish:
            continue
        for lang, legacy_term in legacy_terms.items():
            if legacy_term in str(translations.get(lang, "")):
                errors.append(f"{key}[{lang}] still contains {legacy_term!r}")

    assert not errors, "Legacy Tetris brand terms found in Quadrix strings:\n" + "\n".join(errors)


def test_steam_brand_is_not_retranslated():
    forbidden_terms = {
        "es": ("Vapor",),
        "fr": ("Vapeur",),
        "it": ("Vapore",),
        "ja": ("スチーム",),
        "zh": ("蒸汽",),
        "ko": ("스팀",),
    }

    errors = []
    for key, translations in TRANSLATIONS.items():
        english = str(translations.get("en", ""))
        if "Steam" not in english:
            continue
        for lang, terms in forbidden_terms.items():
            text = str(translations.get(lang, ""))
            if any(term in text for term in terms):
                errors.append(f"{key}[{lang}] translates Steam brand as {text!r}")

    assert not errors, "Steam brand must remain untranslated:\n" + "\n".join(errors)


def test_high_visibility_keys_do_not_fall_back_to_english():
    keys = [
        "tutorial_quick_start_title",
        "tutorial_result_feedback_need_hold",
        "mystery_msg_time_capsule_ready",
        "mystery_workshop_open_instruction",
        "guide_faq_1",
    ]

    errors = []
    for key in keys:
        english = str(TRANSLATIONS[key]["en"]).strip()
        for lang in SUPPORTED_LANGUAGES:
            if lang in {"en", "tr"}:
                continue
            if str(TRANSLATIONS[key].get(lang, "")).strip() == english:
                errors.append(f"{key}[{lang}] still equals EN")

    assert not errors, "High-visibility localization fallback remains:\n" + "\n".join(errors)
