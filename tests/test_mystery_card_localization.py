import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from game_modes_extra import MysteryCardManager, get_card_description, get_card_title
from localization import get_language, set_language


def test_card_variants_resolve_localization_group_and_placeholders():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        speed_burst_card = {
            'id': 'speed_burst_epic',
            '_group_id': 'speed_burst',
            'value': 30,
            'payload': {
                'speed_multiplier': 1.4,
                'line_multiplier': 1.5,
            },
            'title': 'Hız Patlaması',
            'description': '{value} saniye boyunca %40 hızlı düşüş + temizlenen her satır için 1.5x puan!',
        }
        freeze_drop_card = {
            'id': 'freeze_drop_legendary',
            '_group_id': 'freeze_drop',
            'value': 3,
            'freeze_duration': 15,
            'title': 'Son Düşüş',
            'description': '3 hak: F ile bloğu {freeze_duration}sn dondur! Sadece sağ-sol ve sert düşüş çalışır.',
        }

        assert get_card_title(speed_burst_card) == 'Speed Burst'
        assert get_card_description(speed_burst_card) == '40% faster drop for 30 seconds + 1.5x points for every cleared line!'

        assert get_card_title(freeze_drop_card) == 'Final Drop'
        assert get_card_description(freeze_drop_card) == '3 uses: Press F to freeze the piece for 15s. Only left-right movement and hard drop remain active.'
    finally:
        set_language(previous_language)


def test_pending_choices_keep_freeze_duration_for_localized_overlay_text():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        mode = SimpleNamespace(
            settings_manager=SimpleNamespace(get=lambda _key, default=False: default)
        )
        manager = MysteryCardManager(mode)
        manager.catalog = [
            {
                'id': 'freeze_drop_legendary',
                '_group_id': 'freeze_drop',
                'base': 3,
                'freeze_duration': 15,
                'title': 'Son Düşüş',
                'description': '3 hak: F ile bloğu {freeze_duration}sn dondur! Sadece sağ-sol ve sert düşüş çalışır.',
                'color': (60, 150, 255),
                'bg': (5, 12, 38),
                'tag': 'Legendary',
                'rarity': 'legendary',
                'weight': 8,
                'icon': '*',
            }
        ]

        choices = manager.prepare_selection()

        assert len(choices) == 1
        assert choices[0]['freeze_duration'] == 15
        assert get_card_description(choices[0]) == '3 uses: Press F to freeze the piece for 15s. Only left-right movement and hard drop remain active.'
    finally:
        set_language(previous_language)