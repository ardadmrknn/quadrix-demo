import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from game_modes_extra import MysteryCardManager, MysteryMode, get_card_description, get_card_title
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


def test_mystery_popup_text_helpers_return_localized_english_strings():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        mode = MysteryMode.__new__(MysteryMode)

        assert mode._localized_card_text(
            'mystery_workshop_open_instruction',
            'Blok atolyesi! Maks 7 blok. ENTER ile tamamla.',
        ) == 'Block workshop! Max 7 blocks. Press ENTER to finish.'
        assert mode._localized_card_text(
            'mystery_sniper_instruction_main_valid',
            'SOL TIKLAYARAK BLOGU PATLAT',
        ) == 'LEFT CLICK TO DESTROY THE BLOCK'
        assert mode._localized_card_text(
            'mystery_future_popup_title',
            '{order}. Sıradaki Parçayı Seç',
            order=2,
        ) == 'Choose Upcoming Piece #2'
    finally:
        set_language(previous_language)


def test_mystery_localized_message_helpers_format_banner_and_workshop_text():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        mode = MysteryMode.__new__(MysteryMode)
        mode.card_message = ''
        mode.card_message_timer = 0.0
        mode._card_workshop_message = ''
        mode._card_workshop_message_timer = 0.0

        mode._set_localized_card_message(
            'mystery_msg_speed_burst',
            1.5,
            'Hız Patlaması! {duration}s boyunca hızlı düşüş + {line_mult}x puan!',
            duration=30,
            line_mult=1.5,
        )
        mode._set_localized_workshop_message(
            'mystery_workshop_block_added',
            1.0,
            'Blok eklendi. Kalan: {remaining}',
            remaining=4,
        )

        assert mode.card_message == 'Speed Burst! Fast drop for 30s + 1.5x points!'
        assert mode.card_message_timer == 1.5
        assert mode._card_workshop_message == 'Block added. Remaining: 4'
        assert mode._card_workshop_message_timer == 1.0
    finally:
        set_language(previous_language)