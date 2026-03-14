# -*- coding: utf-8 -*-
"""game_modes_extra.py saf yardımcı fonksiyonları için birim testler.

Pygame veya oyun döngüsü gerektirmeyen, deterministik utility fonksiyonlarını
kapsayan testler burada yer alır. Oyun modları (MysteryMode, WideMode vb.)
entegrasyon düzeyinde test edileceğinden bu dosyaya dahil edilmemiştir.

Yeni kart ekleme veya helper mantığı güncelleme durumunda bu testlerin
gözden geçirilmesi gerekir.
"""

from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from game_modes_extra import (
    CARD_LOCALIZATION_ALIASES,
    _SafeCardFormatDict,
    _build_card_format_context,
    _card_type_label_key,
    _dt_to_seconds,
    _format_card_text,
    _resolve_card_localization_id,
    _ui_safe_icon_text,
    get_card_description,
    get_card_title,
)

# ---------------------------------------------------------------------------
# _dt_to_seconds
# ---------------------------------------------------------------------------

def test_dt_to_seconds_converts_milliseconds():
    """pygame.Clock.tick() milisaniye değeri → saniyeye çevrilmeli."""
    result = _dt_to_seconds(16.67)
    assert abs(result - 0.01667) < 1e-5


def test_dt_to_seconds_passes_through_seconds():
    """1.0'dan küçük değer zaten saniye kabul edilmeli."""
    assert _dt_to_seconds(0.016) == 0.016


def test_dt_to_seconds_exact_boundary():
    """Tam 1.0 değeri saniye sayılmalı (> ile kıyaslanıyor)."""
    assert _dt_to_seconds(1.0) == 1.0


def test_dt_to_seconds_zero():
    assert _dt_to_seconds(0.0) == 0.0


def test_dt_to_seconds_typical_60fps():
    result = _dt_to_seconds(16.0)
    assert abs(result - 0.016) < 1e-6


def test_dt_to_seconds_typical_30fps():
    result = _dt_to_seconds(33.0)
    assert abs(result - 0.033) < 1e-6


# ---------------------------------------------------------------------------
# _SafeCardFormatDict
# ---------------------------------------------------------------------------

def test_safe_card_format_dict_returns_existing_value():
    d = _SafeCardFormatDict({'key': 'val'})
    assert d['key'] == 'val'


def test_safe_card_format_dict_missing_key_returns_placeholder():
    d = _SafeCardFormatDict({})
    assert d['missing'] == '{missing}'


def test_safe_card_format_dict_missing_nested_key():
    d = _SafeCardFormatDict({'a': 1})
    assert d['z'] == '{z}'


# ---------------------------------------------------------------------------
# CARD_LOCALIZATION_ALIASES
# ---------------------------------------------------------------------------

def test_aliases_speed_burst_variants_map_to_base():
    for variant in ('speed_burst_rare', 'speed_burst_epic', 'speed_burst_legendary'):
        assert CARD_LOCALIZATION_ALIASES[variant] == 'speed_burst', \
            f"Alias '{variant}' base 'speed_burst'e eşlenmeli"


def test_aliases_freeze_drop_variants_map_to_base():
    for variant in ('freeze_drop_rare', 'freeze_drop_epic', 'freeze_drop_legendary'):
        assert CARD_LOCALIZATION_ALIASES[variant] == 'freeze_drop', \
            f"Alias '{variant}' base 'freeze_drop'a eşlenmeli"


def test_aliases_hold_destroyer_variants_map_to_base():
    for variant in ('hold_destroyer_2', 'hold_destroyer_3', 'hold_destroyer_4', 'hold_destroyer_5'):
        assert CARD_LOCALIZATION_ALIASES[variant] == 'hold_destroyer', \
            f"Alias '{variant}' base 'hold_destroyer'a eşlenmeli"


def test_aliases_values_are_strings():
    for alias, base in CARD_LOCALIZATION_ALIASES.items():
        assert isinstance(base, str) and base.strip(), \
            f"Alias '{alias}' → boş/geçersiz base: {base!r}"


# ---------------------------------------------------------------------------
# _resolve_card_localization_id
# ---------------------------------------------------------------------------

def test_resolve_uses_group_id_from_dict():
    card = {'id': 'speed_burst_epic', '_group_id': 'speed_burst'}
    assert _resolve_card_localization_id(card) == 'speed_burst'


def test_resolve_dict_with_alias_id_no_group():
    card = {'id': 'speed_burst_rare'}
    assert _resolve_card_localization_id(card) == 'speed_burst'


def test_resolve_string_alias():
    assert _resolve_card_localization_id('speed_burst_rare') == 'speed_burst'


def test_resolve_string_base_id_unchanged():
    assert _resolve_card_localization_id('speed_burst') == 'speed_burst'


def test_resolve_unknown_id_returns_as_is():
    assert _resolve_card_localization_id('my_custom_card') == 'my_custom_card'


def test_resolve_empty_string():
    # Boş string için yine boş string döndürmeli (alias tablosunda yok)
    assert _resolve_card_localization_id('') == ''


def test_resolve_group_id_overrides_alias():
    """_group_id varsa normal alias lookup'tan önce gelir."""
    card = {'id': 'freeze_drop_epic', '_group_id': 'my_override'}
    assert _resolve_card_localization_id(card) == 'my_override'


# ---------------------------------------------------------------------------
# _build_card_format_context
# ---------------------------------------------------------------------------

def test_build_context_extracts_scalar_fields():
    card = {'id': 'test', 'value': 5, 'label': 'hi'}
    ctx = _build_card_format_context(card)
    assert ctx['value'] == 5
    assert ctx['label'] == 'hi'


def test_build_context_extracts_payload_fields():
    card = {'id': 'test', 'payload': {'amount': 10}}
    ctx = _build_card_format_context(card)
    assert ctx['amount'] == 10


def test_build_context_computes_speed_percent_from_multiplier():
    card = {'speed_multiplier': 1.4}
    ctx = _build_card_format_context(card)
    assert ctx['speed_percent'] == 40


def test_build_context_speed_percent_20():
    card = {'speed_multiplier': 1.2}
    ctx = _build_card_format_context(card)
    assert ctx['speed_percent'] == 20


def test_build_context_converts_whole_freeze_duration_to_int():
    card = {'freeze_duration': 15.0}
    ctx = _build_card_format_context(card)
    assert ctx['freeze_duration'] == 15
    assert isinstance(ctx['freeze_duration'], int)


def test_build_context_non_whole_freeze_duration_stays_float():
    card = {'freeze_duration': 15.5}
    ctx = _build_card_format_context(card)
    assert ctx['freeze_duration'] == 15.5


def test_build_context_value_override_from_argument():
    card = {'value': 5}
    ctx = _build_card_format_context(card, value=99)
    assert ctx['value'] == 99


def test_build_context_formats_line_multiplier_as_string():
    """line_multiplier float → ':g' formatıyla string'e dönüştürülmeli."""
    ctx = _build_card_format_context({'line_multiplier': 1.5})
    assert ctx['line_multiplier'] == '1.5'
    assert isinstance(ctx['line_multiplier'], str)


def test_build_context_formats_whole_line_multiplier():
    """Tam sayı line_multiplier'ı gereksiz ondalık olmadan yazılmalı (2.0 → '2')."""
    ctx = _build_card_format_context({'line_multiplier': 2.0})
    assert ctx['line_multiplier'] == '2'


def test_build_context_string_input_returns_empty():
    """String kart ID geçildiğinde içerik dict'i boş olmalı."""
    ctx = _build_card_format_context('my_card_id')
    assert isinstance(ctx, dict)
    assert ctx == {}, f"String girişi boş context bekleniyor, alınan: {ctx}"


# ---------------------------------------------------------------------------
# _format_card_text
# ---------------------------------------------------------------------------

def test_format_card_text_no_braces_passthrough():
    assert _format_card_text('hello world', {}) == 'hello world'


def test_format_card_text_fills_value_placeholder():
    result = _format_card_text('{value} sn', {'value': 30})
    assert result == '30 sn'


def test_format_card_text_unknown_placeholder_kept():
    result = _format_card_text('{missing} text', {})
    assert '{missing}' in result


def test_format_card_text_empty_string():
    assert _format_card_text('', {}) == ''


def test_format_card_text_multiple_placeholders():
    card = {'value': 3, 'freeze_duration': 15}
    result = _format_card_text('{value} hak - {freeze_duration}sn', card)
    assert result == '3 hak - 15sn'


def test_format_card_text_with_dict_card():
    card = {'id': 'test', 'value': 7}
    result = _format_card_text('{value}x puan', card)
    assert result == '7x puan'


# ---------------------------------------------------------------------------
# _ui_safe_icon_text
# ---------------------------------------------------------------------------

def test_ui_safe_icon_text_ascii_returned_as_is():
    assert _ui_safe_icon_text('hello') == 'hello'


def test_ui_safe_icon_text_emoji_returns_default_fallback():
    assert _ui_safe_icon_text('\U0001f3ae') == '*'


def test_ui_safe_icon_text_none_returns_empty():
    assert _ui_safe_icon_text(None) == ''


def test_ui_safe_icon_text_empty_string_returns_empty():
    assert _ui_safe_icon_text('') == ''


def test_ui_safe_icon_text_custom_fallback():
    assert _ui_safe_icon_text('\u2665', fallback='X') == 'X'


def test_ui_safe_icon_text_numbers_pass():
    assert _ui_safe_icon_text(42) == '42'


def test_ui_safe_icon_text_asterisk_is_ascii():
    assert _ui_safe_icon_text('*') == '*'


# ---------------------------------------------------------------------------
# _card_type_label_key
# ---------------------------------------------------------------------------

def test_card_type_persistent_flag():
    assert _card_type_label_key({'persistent': True}) == 'card_type_persistent'


def test_card_type_persistent_false_not_selected():
    result = _card_type_label_key({'id': 'other', 'persistent': False})
    assert result != 'card_type_persistent'


def test_card_type_known_limited_id_quantum():
    assert _card_type_label_key({'id': 'quantum_tunneling'}) == 'card_type_limited'


def test_card_type_known_limited_id_hammer():
    assert _card_type_label_key({'id': 'hammer'}) == 'card_type_limited'


def test_card_type_known_limited_id_freeze_drop_rare():
    assert _card_type_label_key({'id': 'freeze_drop_rare'}) == 'card_type_limited'


def test_card_type_limited_flag():
    assert _card_type_label_key({'id': 'other', 'limited': True}) == 'card_type_limited'


def test_card_type_timed_buff_flag():
    assert _card_type_label_key({'id': 'other', 'timed_buff': True}) == 'card_type_limited'


def test_card_type_charges_flag():
    assert _card_type_label_key({'id': 'other', 'charges': True}) == 'card_type_limited'


def test_card_type_single_use():
    assert _card_type_label_key({'id': 'other', 'single_use': True}) == 'card_type_single_use'


def test_card_type_default_falls_back_to_limited():
    """ID tanımsız ve hiçbir flag yok → fallback limited."""
    result = _card_type_label_key({'id': 'completely_unknown_card'})
    assert result == 'card_type_limited'


# ---------------------------------------------------------------------------
# get_card_title / get_card_description (fallback davranışı)
# ---------------------------------------------------------------------------

def test_get_card_title_uses_title_field_as_fallback():
    """Localization'da karşılığı olmayan ID → title field'ından fallback."""
    card = {
        'id': '__nonexistent_test_card_xyz__',
        'title': 'Test Kartı',
    }
    result = get_card_title(card)
    assert result == 'Test Kartı'


def test_get_card_title_explicit_fallback_parameter():
    result = get_card_title('__nonexistent_xyz__', fallback='Fallback Başlık')
    assert result == 'Fallback Başlık'


def test_get_card_title_empty_id_uses_fallback():
    result = get_card_title({'id': ''}, fallback='Varsayılan')
    assert result == 'Varsayılan'


def test_get_card_description_uses_description_field_as_fallback():
    card = {
        'id': '__nonexistent_test_card_xyz__',
        'description': 'Test açıklaması',
    }
    result = get_card_description(card)
    assert result == 'Test açıklaması'


def test_get_card_description_fills_value_placeholder_in_fallback():
    """Fallback metin {value} içerse, value alanından doldurulmalı."""
    card = {
        'id': '__nonexistent_test_card_xyz__',
        'value': 10,
        'description': '{value} saniye etkili',
    }
    result = get_card_description(card)
    assert result == '10 saniye etkili'


def test_get_card_description_value_override():
    card = {
        'id': '__nonexistent_test_card_xyz__',
        'value': 5,
        'description': '{value} hak',
    }
    # value argümanı description'daki field'ı ezmeli
    result = get_card_description(card, value=20)
    assert result == '20 hak'


def test_get_card_description_explicit_fallback_parameter():
    result = get_card_description('__nonexistent_xyz__', fallback='Açıklama yok')
    assert result == 'Açıklama yok'
