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


def test_hammer_card_title_matches_runtime_effect():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        assert get_card_title({'id': 'hammer', 'title': 'Çekiç'}) == 'Hammer'
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


def test_mirror_hold_localizes_in_english():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        mirror_hold = {
            'id': 'mirror_hold',
            'title': 'Ayna Cep',
            'description': 'Sıradaki saklanan parça aynalanır. Simetrik parçalar aynı kalır.',
        }

        assert get_card_title(mirror_hold) == 'Mirror Hold'
        assert get_card_description(mirror_hold) == 'The next stored piece is mirrored. Symmetric pieces stay the same.'
    finally:
        set_language(previous_language)


def test_echo_drop_localizes_in_english():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        echo_drop = {
            'id': 'echo_drop',
            'title': 'Yankı Düşüşü',
            'description': 'Parça kilitlenince altındaki uygun {echo_cells} boş kareye gölge blok bırakır. Dolu yerlere yerleşmez.',
            'payload': {'echo_cells': 2},
        }

        assert get_card_title(echo_drop) == 'Echo Drop'
        assert get_card_description(echo_drop) == 'On a fitting lock, it leaves 2 shadow blocks under the piece. They only land in empty cells.'
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


def test_mystery_active_card_status_helpers_return_localized_english_strings():
    previous_language = get_language()
    try:
        assert set_language('en') is True

        mode = MysteryMode.__new__(MysteryMode)

        assert mode._localized_active_card_uses_status('F', 3) == 'F: 3 Uses'
        assert mode._localized_active_card_timed_uses_status(2.5, 3) == '2.5s | 3 Uses'
    finally:
        set_language(previous_language)


def test_mystery_sync_active_cards_localizes_freeze_drop_status_and_marks_ready(monkeypatch):
    previous_language = get_language()
    try:
        assert set_language('en') is True
        monkeypatch.setattr('game_modes_extra.get_gamepad_manager', lambda: SimpleNamespace(is_connected=lambda: False))

        mode = MysteryMode.__new__(MysteryMode)
        mode._active_effect_visuals = {
            'freeze_drop': {
                'title': 'Son Düşüş',
                'color': (60, 150, 255),
                'icon': '*',
                'tag': 'Legendary',
                'rarity': 'legendary',
                'style': {},
                'icon_image': None,
            }
        }
        mode.card_manager = SimpleNamespace(catalog=[], force_piece_queue=[], active_cards=[])
        mode.perk_manager = SimpleNamespace(
            is_active=lambda _key: False,
            get_multiplier=lambda: 1.0,
            rewind_uses=0,
        )
        mode._remember_effect_visual = lambda *args, **kwargs: None
        mode.current_piece = SimpleNamespace(tunnel=False, drill=False)
        mode.speed_effect_timer = 0
        mode._speed_burst_timer = 0
        mode._speed_burst_line_mult = 1.5
        mode._line_clear_multiplier_remaining = 0
        mode._line_clear_multiplier_value = 1.0
        mode.line_bonus_remaining = 0
        mode.line_bonus_amount = 0
        mode.combo_aura_timer = 0
        mode.combo_aura_bonus = 0
        mode._score_multiplier_timer = 0.0
        mode._score_multiplier_value = 1.0
        mode._armed_nova_clusters = 0
        mode.tunnel_charges_remaining = 0
        mode.hammer_charges_remaining = 0
        mode.bomb_master_charges = 0
        mode._hold_destroyer_charges = 0
        mode._freeze_drop_charges = 3
        mode._freeze_drop_active = False
        mode._freeze_drop_timer = 0.0
        mode._freeze_drop_duration = 15
        mode._sniper_charges = 0
        mode.time_capsule_available = False
        mode.time_capsule_saved = False
        mode.gravity_freeze_timer = 0
        mode.phase_shift_uses_remaining = 0

        mode._sync_active_cards()

        freeze_card = next(card for card in mode.card_manager.active_cards if card['id'] == 'freeze_drop')
        assert freeze_card['title'] == 'Final Drop'
        assert freeze_card['description'] == '3 uses: Press F to freeze the piece for 15s. Only left-right movement and hard drop remain active.'
        assert freeze_card['status'] == 'F: 3 Uses'
        assert freeze_card['status_state'] == 'hazir'
    finally:
        set_language(previous_language)


def test_mystery_sync_active_cards_localizes_time_capsule_and_perk_panel_copy(monkeypatch):
    previous_language = get_language()
    try:
        assert set_language('en') is True
        monkeypatch.setattr('game_modes_extra.get_gamepad_manager', lambda: SimpleNamespace(is_connected=lambda: False))

        mode = MysteryMode.__new__(MysteryMode)
        mode._active_effect_visuals = {
            'time_capsule': {
                'title': 'Zaman Kapsülü',
                'color': (180, 220, 255),
                'icon': '*',
                'tag': 'Legendary',
                'rarity': 'legendary',
                'style': {},
                'icon_image': None,
            }
        }
        mode.card_manager = SimpleNamespace(catalog=[], force_piece_queue=[], active_cards=[])
        mode.perk_manager = SimpleNamespace(
            is_active=lambda key: key == 'second_pocket',
            get_multiplier=lambda: 1.0,
            rewind_uses=0,
        )
        mode._remember_effect_visual = lambda *args, **kwargs: None
        mode.current_piece = SimpleNamespace(tunnel=False, drill=False)
        mode.speed_effect_timer = 0
        mode._speed_burst_timer = 0
        mode._speed_burst_line_mult = 1.5
        mode._line_clear_multiplier_remaining = 0
        mode._line_clear_multiplier_value = 1.0
        mode.line_bonus_remaining = 0
        mode.line_bonus_amount = 0
        mode.combo_aura_timer = 0
        mode.combo_aura_bonus = 0
        mode._score_multiplier_timer = 0.0
        mode._score_multiplier_value = 1.0
        mode._armed_nova_clusters = 0
        mode.tunnel_charges_remaining = 0
        mode.hammer_charges_remaining = 0
        mode.bomb_master_charges = 0
        mode._hold_destroyer_charges = 0
        mode._freeze_drop_charges = 0
        mode._freeze_drop_active = False
        mode._freeze_drop_timer = 0.0
        mode._freeze_drop_duration = 6
        mode._sniper_charges = 0
        mode.time_capsule_available = True
        mode.time_capsule_saved = False
        mode.gravity_freeze_timer = 0
        mode.phase_shift_uses_remaining = 0

        mode._sync_active_cards()

        time_capsule = next(card for card in mode.card_manager.active_cards if card['id'] == 'time_capsule')
        second_pocket = next(card for card in mode.card_manager.active_cards if card['id'] == 'perk_second_pocket')

        assert time_capsule['title'] == 'Time Capsule'
        assert time_capsule['description'] == 'T: Save the current board state.'
        assert time_capsule['status'] == 'T'
        assert second_pocket['title'] == 'Extra Pocket'
        assert second_pocket['description'] == 'PERK: Press V to store a second piece.'
        assert second_pocket['tag'] == 'Perk'
    finally:
        set_language(previous_language)
