"""localization.py — tüm dillerde tüm anahtarlar mevcut mu? Tamamlama testi."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Önceki test tarafından stub olarak yerleştirilen localization'ı temizle
if 'localization' in sys.modules and not hasattr(sys.modules['localization'], 'TRANSLATIONS'):
    del sys.modules['localization']

from localization import TRANSLATIONS, SUPPORTED_LANGUAGES, get_missing_translations


def test_no_missing_translations_for_any_language():
    """Tüm desteklenen diller için tüm anahtarlar mevcut olmalı (fallback dahil)."""
    all_missing = {}
    for lang in SUPPORTED_LANGUAGES:
        missing = get_missing_translations(lang)
        if missing:
            all_missing[lang] = missing

    assert not all_missing, (
        f"Eksik çeviriler bulundu:\n" +
        "\n".join(f"  [{lang}]: {len(keys)} eksik — ilk 5: {keys[:5]}"
                  for lang, keys in all_missing.items())
    )


def test_tr_en_always_present():
    """TR ve EN her anahtarda mutlaka olmalı."""
    for key, trans in TRANSLATIONS.items():
        assert 'tr' in trans, f"'{key}' anahtarında TR eksik"
        assert 'en' in trans, f"'{key}' anahtarında EN eksik"
