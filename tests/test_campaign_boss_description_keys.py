"""Faz 4 — Boss/mini-boss mekanik açıklaması lokalizasyonu.

6 yeni desc key 11 dilde tam, RU/JA/ZH/KO EN ile aynı değil, kısa kalmalı.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import TRANSLATIONS


SUPPORTED_LANGS = ('tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko')

DESC_KEYS = [
    'campaign_boss_rain_desc',
    'campaign_boss_seal_desc',
    'campaign_boss_dark_desc',
    'campaign_boss_final_desc',
    'campaign_miniboss_fast_desc',
    'campaign_miniboss_missing_desc',
]


def test_all_boss_description_keys_exist_in_11_languages():
    """6 desc key 11 dilde dolu olmalı."""
    missing = []
    for key in DESC_KEYS:
        entry = TRANSLATIONS.get(key)
        assert entry is not None, f"'{key}' yok"
        for lang in SUPPORTED_LANGS:
            value = entry.get(lang)
            if not value:
                missing.append((key, lang))
    assert not missing, f"Boss desc eksikleri: {missing}"


def test_boss_description_localized_for_ru_ja_zh_ko():
    """RU/JA/ZH/KO'da EN ile aynı değer olmamalı (gerçek lokalizasyon)."""
    issues = []
    for key in DESC_KEYS:
        entry = TRANSLATIONS[key]
        en_value = entry.get('en')
        for lang in ('ru', 'ja', 'zh', 'ko'):
            if entry.get(lang) == en_value:
                issues.append((key, lang, en_value))
    assert not issues, f"Lokalizasyon eksikleri (EN copy): {issues}"


def test_boss_description_is_short_enough_for_preview():
    """EN açıklaması ≤ 60 karakter (UI sığma için)."""
    over_limit = []
    for key in DESC_KEYS:
        en = TRANSLATIONS[key].get('en', '')
        if len(en) > 60:
            over_limit.append((key, len(en), en))
    assert not over_limit, f"Çok uzun açıklamalar: {over_limit}"
