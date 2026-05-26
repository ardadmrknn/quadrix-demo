"""Faz 2 — UI boss/mini-boss sözel etiket lokalizasyonu.

Boss tipi belirleme + label key'leri 11 dilde mevcut.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import TRANSLATIONS
from campaign.campaign_mode import CampaignMode


SUPPORTED_LANGS = ('tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko')

BOSS_LABEL_KEYS = [
    'campaign_boss_rain',
    'campaign_boss_seal',
    'campaign_boss_dark',
    'campaign_boss_final',
    'campaign_miniboss_fast',
    'campaign_miniboss_missing',
    'campaign_star_not_yet',
    'campaign_fail_boss_overflow',
]


def test_all_boss_label_keys_exist_in_11_languages():
    missing = []
    for key in BOSS_LABEL_KEYS:
        entry = TRANSLATIONS.get(key)
        assert entry is not None, f"TRANSLATIONS'da '{key}' yok"
        for lang in SUPPORTED_LANGS:
            if not entry.get(lang):
                missing.append((key, lang))
    assert not missing, f"Boss label eksikleri: {missing}"


def test_boss_label_keys_have_unique_values_per_language():
    """RU/JA/ZH/KO için boss tipleri birbirinden farklı olmalı (kopya değil)."""
    for lang in ('ru', 'ja', 'zh', 'ko'):
        values = []
        for key in ['campaign_boss_rain', 'campaign_boss_seal', 'campaign_boss_dark',
                    'campaign_miniboss_fast', 'campaign_miniboss_missing']:
            v = TRANSLATIONS[key].get(lang, '')
            values.append(v)
        unique = set(values)
        assert len(unique) == len(values), (
            f"Lang {lang}: boss label'leri benzersiz olmalı. Got: {values}"
        )


def _make_boss_mode(level_num):
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    last_digit = level_num % 10
    mode.is_mini_boss = (last_digit == 5)
    mode.is_boss = (last_digit == 0 and level_num > 0)
    return mode


def test_boss_get_type_returns_correct_label_key_indirectly():
    """Boss type → label key haritası tutarlı."""
    mappings = [
        (10, 'rain'),
        (20, 'seal'),
        (30, 'dark'),
        (100, 'final'),
        (5, 'fast'),
        (15, 'missing'),
    ]
    for lv, expected in mappings:
        mode = _make_boss_mode(lv)
        boss_type = CampaignMode._boss_get_type(mode)
        assert boss_type == expected, f"L{lv}: {boss_type} != {expected}"
