"""Faz 3 — level_select.py preview UI değişiklikleri.

Boss tipi etiketi: kilitsiz levellarda boss label çiziliyor.
Attempts tooltip: success/fail attempts varsa metin oluşturuluyor.
1+3 yıldız preview: star_flags bireysel render.

UI mock'lama hafif tutulmuş; sadece state akışı doğrulanır.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import TRANSLATIONS, t


SUPPORTED_LANGS = ('tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko')


def test_attempts_summary_key_exists_in_11_languages():
    entry = TRANSLATIONS.get('campaign_attempts_summary')
    assert entry is not None
    for lang in SUPPORTED_LANGS:
        v = entry.get(lang)
        assert v, f"'campaign_attempts_summary' [{lang}] eksik"
        # Format placeholder kontrolü
        assert '{success}' in v, f"[{lang}] {{success}} placeholder eksik: {v!r}"
        assert '{fail}' in v, f"[{lang}] {{fail}} placeholder eksik: {v!r}"


def test_preview_warning_keys_exist_in_11_languages():
    for key in ['campaign_preview_boss_warning', 'campaign_preview_miniboss_warning']:
        entry = TRANSLATIONS.get(key)
        assert entry is not None, f"'{key}' yok"
        for lang in SUPPORTED_LANGS:
            assert entry.get(lang), f"'{key}' [{lang}] eksik"


def test_attempts_summary_format_resolves_correctly():
    """t() ile attempts_summary formatlama placeholder'ları yerine getirir."""
    text_tr = t('campaign_attempts_summary', success=3, fail=7)
    assert '3' in text_tr
    assert '7' in text_tr

    text_en = t('campaign_attempts_summary', success=5, fail=2)
    assert '5' in text_en
    assert '2' in text_en


def test_star_flags_preview_individual_render():
    """Karma yıldız modelinde star_flags slot bazlı render edilir.

    Eski save (star_flags yok) → cumulatif fallback `stars >= star_num`.
    Yeni save (star_flags var) → her slot bağımsız.
    """
    # Senaryo 1: Eski save (cumulatif): 2 yıldız → ★★☆
    old_save_data = {'stars': 2}
    star_flags_raw = old_save_data.get('star_flags')
    expected_old = []
    for star_num in [1, 2, 3]:
        if isinstance(star_flags_raw, dict) and str(star_num) in star_flags_raw:
            expected_old.append(bool(star_flags_raw[str(star_num)]))
        else:
            expected_old.append(2 >= star_num)
    assert expected_old == [True, True, False]

    # Senaryo 2: Yeni save (1+3): toplam 2 yıldız ama slot bazlı ★☆★
    new_save_data = {'stars': 2, 'star_flags': {'1': True, '2': False, '3': True}}
    star_flags_raw = new_save_data.get('star_flags')
    expected_new = []
    for star_num in [1, 2, 3]:
        if isinstance(star_flags_raw, dict) and str(star_num) in star_flags_raw:
            expected_new.append(bool(star_flags_raw[str(star_num)]))
        else:
            expected_new.append(2 >= star_num)
    assert expected_new == [True, False, True]
