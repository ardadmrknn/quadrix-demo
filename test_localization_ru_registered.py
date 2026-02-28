"""localization.py — Rusça (ru) dil kaydı birim testi."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Önceki test tarafından stub olarak yerleştirilen localization'ı temizle
if 'localization' in sys.modules and not hasattr(sys.modules['localization'], 'TRANSLATIONS'):
    del sys.modules['localization']

from localization import SUPPORTED_LANGUAGES, LANGUAGE_METADATA, set_language, t


def test_ru_in_supported_languages():
    assert 'ru' in SUPPORTED_LANGUAGES, "RU dili SUPPORTED_LANGUAGES listesinde olmalı"


def test_ru_metadata_exists():
    assert 'ru' in LANGUAGE_METADATA, "RU metadata'sı LANGUAGE_METADATA'da olmalı"


def test_ru_metadata_name():
    assert LANGUAGE_METADATA['ru']['name'] == 'Russian'


def test_ru_metadata_native_name():
    assert LANGUAGE_METADATA['ru']['native_name'] == 'Русский'


def test_ru_metadata_flag():
    assert LANGUAGE_METADATA['ru']['flag_emoji'] == '🇷🇺'


def test_ru_metadata_rtl():
    assert LANGUAGE_METADATA['ru']['rtl'] is False


def test_ru_set_language():
    result = set_language('ru')
    assert result is True, "set_language('ru') True dönmeli"


def test_ru_t_function_returns_string():
    set_language('ru')
    result = t('main_menu_title')
    assert isinstance(result, str), "t() string dönmeli"
    assert len(result) > 0, "t() sonucu boş olmamalı"
