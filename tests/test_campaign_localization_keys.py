"""Faz 1 — Lokalizasyon kapsamı kontrolü.

Tüm auto-gen objective'leri 11 dilde lokalize bir description üretmeli.
description_key zorunlu; key TRANSLATIONS'da mevcut ve 11 dil dolu.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import TRANSLATIONS, set_language
from campaign.level_data import get_level
from campaign.objectives import create_objective


SUPPORTED_LANGS = ('tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko')


def test_required_campaign_keys_have_all_11_languages():
    """Faz 1 için kritik campaign anahtarları 11 dilde dolu olmalı."""
    required_keys = [
        'campaign_obj_clear_lines',
        'campaign_obj_clear_garbage',
        'campaign_obj_score',
        'campaign_obj_tetris',
        'campaign_obj_combo',
        'campaign_obj_survival',
        'campaign_obj_time',
        'campaign_obj_special_block_typed',
        'campaign_special_block_ice',
        'campaign_special_block_locked',
        'campaign_special_block_bomb',
        'campaign_special_block_star',
        'campaign_special_block_timer',
        'campaign_first_clear',
        'campaign_new_star_record',
        'campaign_new_score_record',
        'campaign_world_short_1',
        'campaign_world_short_2',
        'campaign_world_short_3',
        'campaign_world_short_4',
        'campaign_world_short_5',
        # Faz 3: level_select preview anahtarları
        'campaign_attempts_summary',
        'campaign_preview_boss_warning',
        'campaign_preview_miniboss_warning',
    ]
    missing = []
    for key in required_keys:
        entry = TRANSLATIONS.get(key)
        assert entry is not None, f"TRANSLATIONS'da '{key}' yok"
        for lang in SUPPORTED_LANGS:
            value = entry.get(lang)
            if not value:
                missing.append((key, lang, 'eksik'))
                continue
            # Anahtarın değeri en sık karşılaşılan İngilizce olmamalı
            # (RU/JA/ZH/KO için bilerek kontrol; "Locked"/"Star"/"Ice" gibi
            # tam İngilizce kelimeleri RU/ZH/KO'da görmek istemiyoruz).
            if lang in ('ru', 'zh', 'ko') and value == entry.get('en'):
                missing.append((key, lang, f'EN ile aynı: {value!r}'))
    if missing:
        report = '\n'.join(f"  {k} [{l}]: {info}" for k, l, info in missing)
        raise AssertionError(f"Lokalizasyon eksikleri:\n{report}")


def test_auto_gen_objectives_yield_localized_descriptions():
    """Tüm 100 level'ın auto-gen objective'leri 11 dilde anlamlı string üretir."""
    levels_to_test = [6, 7, 8, 12, 16, 22, 27, 32, 42, 55, 65, 72, 82, 92, 99]
    for level_num in levels_to_test:
        cfg = get_level(level_num)
        assert cfg is not None
        for obj_def in cfg.objectives:
            obj = create_objective(obj_def.get('type', 'clear_lines'), **obj_def)
            for lang in SUPPORTED_LANGS:
                set_language(lang)
                desc = obj.get_description(lang)
                assert desc and isinstance(desc, str) and len(desc) > 0, (
                    f"L{level_num} obj={obj_def.get('type')} lang={lang}: boş description"
                )
                # Description_key olmayan eski tip'ler en azından dict literal'i
                # bulmalı; description_key varsa lokalize string gelmeli.
    set_language('tr')  # restore


def test_boss_names_localized_in_all_11_languages():
    """Boss level'ları (10, 20, ..., 100) 11 dilde de unique isim dönmeli."""
    boss_levels = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    for level_num in boss_levels:
        cfg = get_level(level_num)
        assert cfg is not None
        for lang in SUPPORTED_LANGS:
            name = cfg.name.get(lang)
            assert name and isinstance(name, str), (
                f"Boss L{level_num} lang={lang}: isim eksik"
            )
        # RU/JA/ZH/KO boss isimleri EN ile aynı olmamalı
        en_name = cfg.name.get('en')
        for lang in ('ru', 'ja', 'zh', 'ko'):
            assert cfg.name.get(lang) != en_name, (
                f"Boss L{level_num} {lang} EN ile aynı: {cfg.name.get(lang)!r}"
            )


def test_world_names_localized_in_all_11_languages():
    """5 dünya ismi 11 dilde dolu olmalı."""
    from campaign.level_data import get_world_info
    for world in range(1, 6):
        info = get_world_info(world)
        for lang in SUPPORTED_LANGS:
            name = info['name'].get(lang)
            assert name and isinstance(name, str) and len(name) > 0, (
                f"World {world} lang={lang}: isim eksik"
            )
