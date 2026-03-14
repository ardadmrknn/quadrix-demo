# -*- coding: utf-8 -*-
"""guide_screen.py veri yapıları için birim testler.

CARD_DATA, GUIDE_SECTIONS, RARITY_COLORS, RARITY_NAME_KEYS ve
GUIDE_TAB_MASCOT_ICONS sabitlerinin bütünlüğünü doğrular.
Yeni kart veya sekme eklendiğinde bu testlerin güncel tutulması gerekir.
"""

from __future__ import annotations

import os
import sys

# conftest.py src'yi zaten ekler; burada güvenlik için tekrar ekliyoruz.
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from guide_screen import (
    CARD_DATA,
    GUIDE_SECTIONS,
    RARITY_COLORS,
    RARITY_NAME_KEYS,
    GUIDE_TAB_MASCOT_ICONS,
    _get_ui_icon_dir,
    _get_maskot_dir,
)

# ---------------------------------------------------------------------------
# CARD_DATA bütünlüğü
# ---------------------------------------------------------------------------

REQUIRED_CARD_FIELDS = {'id', 'name_key', 'desc_key', 'rarity', 'color'}


def test_card_data_is_nonempty():
    assert len(CARD_DATA) > 0, "CARD_DATA boş olmamalı"


def test_card_data_required_fields():
    """Her kart girişinde zorunlu alanlar bulunmalı."""
    for card in CARD_DATA:
        missing = REQUIRED_CARD_FIELDS - card.keys()
        assert not missing, f"Kart '{card.get('id', '?')}' şu alanlara sahip değil: {missing}"


def test_card_data_unique_ids():
    """Kart ID'leri benzersiz olmalı."""
    ids = [card['id'] for card in CARD_DATA]
    duplicates = {cid for cid in ids if ids.count(cid) > 1}
    assert not duplicates, f"Tekrarlayan kart ID'leri: {duplicates}"


def test_card_data_ids_are_nonempty_strings():
    for card in CARD_DATA:
        assert isinstance(card['id'], str) and card['id'].strip(), \
            f"Geçersiz kart ID: {card['id']!r}"


def test_card_data_name_desc_keys_are_strings():
    for card in CARD_DATA:
        assert isinstance(card['name_key'], str) and card['name_key'].strip(), \
            f"Kart '{card['id']}' name_key geçersiz"
        assert isinstance(card['desc_key'], str) and card['desc_key'].strip(), \
            f"Kart '{card['id']}' desc_key geçersiz"


def test_card_data_rarity_values_are_known():
    """Her kartın rarity değeri RARITY_COLORS içinde bulunmalı."""
    known = set(RARITY_COLORS.keys())
    for card in CARD_DATA:
        assert card['rarity'] in known, \
            f"Kart '{card['id']}' bilinmeyen rarity: '{card['rarity']}'"


def test_card_data_color_is_rgb_tuple():
    """color alanı 3 elemanlı ve 0-255 arası int tuple olmalı."""
    for card in CARD_DATA:
        color = card['color']
        assert isinstance(color, tuple) and len(color) == 3, \
            f"Kart '{card['id']}' color format hatası: {color!r}"
        for component in color:
            assert isinstance(component, int) and 0 <= component <= 255, \
                f"Kart '{card['id']}' renk bileşeni sınır dışı: {component}"


def test_card_data_has_expected_rarities():
    """CARD_DATA'da beş temel rarity'nin hepsi bulunmalı."""
    rarities_present = {card['rarity'] for card in CARD_DATA}
    for expected_rarity in ('common', 'uncommon', 'rare', 'epic', 'legendary'):
        assert expected_rarity in rarities_present, \
            f"CARD_DATA'da '{expected_rarity}' rarity eksik"


# ---------------------------------------------------------------------------
# RARITY_COLORS
# ---------------------------------------------------------------------------

def test_rarity_colors_has_all_keys():
    expected = {'common', 'uncommon', 'rare', 'epic', 'legendary', 'perk'}
    assert set(RARITY_COLORS.keys()) == expected


def test_rarity_colors_values_are_rgb_tuples():
    for rarity, color in RARITY_COLORS.items():
        assert isinstance(color, tuple) and len(color) == 3, \
            f"RARITY_COLORS['{rarity}'] RGB tuple değil: {color!r}"
        for c in color:
            assert isinstance(c, int) and 0 <= c <= 255, \
                f"RARITY_COLORS['{rarity}'] bileşen hatalı: {c}"


# ---------------------------------------------------------------------------
# RARITY_NAME_KEYS
# ---------------------------------------------------------------------------

def test_rarity_name_keys_covers_all_rarity_colors():
    """Tüm RARITY_COLORS anahtarları RARITY_NAME_KEYS'te localization key'e sahip olmalı."""
    for rarity in RARITY_COLORS:
        assert rarity in RARITY_NAME_KEYS, \
            f"RARITY_NAME_KEYS'te '{rarity}' eksik"


def test_rarity_name_keys_values_are_nonempty_strings():
    for rarity, key in RARITY_NAME_KEYS.items():
        assert isinstance(key, str) and key.strip(), \
            f"RARITY_NAME_KEYS['{rarity}'] boş veya geçersiz: {key!r}"


# ---------------------------------------------------------------------------
# GUIDE_SECTIONS
# ---------------------------------------------------------------------------

EXPECTED_SECTION_IDS = ['how_to_play', 'game_modes', 'cards', 'tips_faq']


def test_guide_sections_count():
    assert len(GUIDE_SECTIONS) == len(EXPECTED_SECTION_IDS), \
        f"Beklenen {len(EXPECTED_SECTION_IDS)} sekme, bulunan: {len(GUIDE_SECTIONS)}"


def test_guide_sections_ids_match():
    actual_ids = [s['id'] for s in GUIDE_SECTIONS]
    assert actual_ids == EXPECTED_SECTION_IDS, \
        f"Sekme ID listesi beklenenden farklı: {actual_ids}"


def test_guide_sections_have_required_fields():
    for section in GUIDE_SECTIONS:
        assert 'id' in section, f"Sekme ID alanı eksik: {section}"
        assert 'title_key' in section, f"Sekme '{section['id']}' title_key eksik"
        assert isinstance(section['title_key'], str) and section['title_key'].strip(), \
            f"Sekme '{section['id']}' title_key geçersiz"


def test_cards_section_has_card_gallery_flag():
    cards_section = next((s for s in GUIDE_SECTIONS if s['id'] == 'cards'), None)
    assert cards_section is not None
    assert cards_section.get('is_card_gallery') is True


def test_non_card_sections_have_content_keys():
    """Kart galerisi olmayan her bölümde content_keys listesi bulunmalı."""
    for section in GUIDE_SECTIONS:
        if section.get('is_card_gallery'):
            continue
        assert 'content_keys' in section, \
            f"Sekme '{section['id']}' content_keys alanı eksik"


# ---------------------------------------------------------------------------
# GUIDE_TAB_MASCOT_ICONS
# ---------------------------------------------------------------------------

def test_guide_tab_mascot_icons_covers_all_sections():
    """Her sekme ID'si için maskot ikonu tanımlı olmalı."""
    section_ids = {s['id'] for s in GUIDE_SECTIONS}
    for section_id in section_ids:
        assert section_id in GUIDE_TAB_MASCOT_ICONS, \
            f"GUIDE_TAB_MASCOT_ICONS'ta '{section_id}' için ikon eksik"


def test_guide_tab_mascot_icons_values_are_png():
    for section_id, icon_name in GUIDE_TAB_MASCOT_ICONS.items():
        assert isinstance(icon_name, str) and icon_name.endswith('.png'), \
            f"GUIDE_TAB_MASCOT_ICONS['{section_id}'] PNG dosyası değil: {icon_name!r}"


# ---------------------------------------------------------------------------
# Dizin yardımcıları
# ---------------------------------------------------------------------------

def test_get_ui_icon_dir_returns_string():
    result = _get_ui_icon_dir()
    assert isinstance(result, str) and result.strip()


def test_get_maskot_dir_returns_string():
    result = _get_maskot_dir()
    assert isinstance(result, str) and result.strip()


def test_get_ui_icon_dir_contains_assets_ui():
    path = _get_ui_icon_dir().replace('\\', '/')
    assert 'assets' in path and 'ui' in path, \
        f"Beklenen 'assets/ui' içeren yol, bulunan: {path}"


def test_get_maskot_dir_contains_assets_maskot():
    path = _get_maskot_dir().replace('\\', '/')
    assert 'assets' in path and 'maskot' in path, \
        f"Beklenen 'assets/maskot' içeren yol, bulunan: {path}"
