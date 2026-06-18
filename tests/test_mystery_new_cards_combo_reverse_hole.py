"""Davranış testleri: Combo Sigortası, Ters Borç, Delik Avcısı.

Bu testler üç yeni Mystery kartının runtime davranışını sabitler:

- Combo Sigortası: aktif combo varken satır temizlenmeyen tek hamlede combo
  korunur, sigorta tek kullanımdır ve aktif HUD'dan düşer.
- Ters Borç: anlık 2 satır temizliği XP/queue üretmez; 5 lock için lock_delay=0
  cezası uygular ve sayaç bittiğinde normal davranış geri döner. Time capsule
  round-trip içinde state korunur.
- Delik Avcısı: J ile sütun seçer, sütundaki kapalı boşluklardan rastgele 1
  tanesini doldurur. Geçersiz sütunda hak harcanmaz, valid kullanım sonrası
  oluşan tam satır external/card source clear akışından geçer (reward queue
  açmaz).

Random seçimler test edilebilir olsun diye `random.choice` monkeypatch ile
deterministic hale getirilir.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pygame
import pytest


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

def set_language(lang_code: str) -> bool:
    import sys
    import localization
    loc = sys.modules.get('localization', localization)
    return loc.set_language(lang_code)

def get_language() -> str:
    import sys
    import localization
    loc = sys.modules.get('localization', localization)
    return loc.get_language()


def _import_mystery():
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment: MysteryMode import skipped')
    import game_modes_extra as extra
    from board import Board
    return extra, extra.Game, extra.MysteryMode, Board


# === Combo Sigortası ===

def _make_combo_mode(MysteryMode, Board):
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode._combo_insurance_armed = True
    mode._reverse_debt_remaining = 0
    mode._reverse_debt_total = 5
    mode._active_effect_visuals = {'combo_insurance': {'id': 'combo_insurance', 'title': 'Combo Sigortası', 'color': (255, 220, 140)}}
    mode._sync_active_cards = lambda: None
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    return mode


def test_combo_insurance_preserves_combo_on_dry_lock(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery()
    mode = _make_combo_mode(MysteryMode, Board)
    mode.board.combo = 0  # super().lock_and_new_piece tarafından sıfırlanmış varsay
    previous_combo = 4
    # current_piece ve diğer hooklar minimum
    mode.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(4, 18)])
    mode._armed_nova_clusters = 0
    mode._rewind_available = False
    mode.energy = 0
    mode.energy_max = 100
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._speed_burst_timer = 0.0
    mode._speed_burst_line_mult = 1.0
    mode._freeze_drop_active = False
    mode._freeze_drop_timer = 0.0

    # board.combo super tarafından 0'a sıfırlanır; lock_and_new_piece içinde
    # previous_combo capture edilir. Bunu simüle etmek için board.combo zaten 0,
    # ama kart koduna previous_combo=4 olarak gitmeli; bu yüzden gerçek
    # lock_and_new_piece'ı çağırıyoruz, board.combo'yu önceden 4'e set edelim.
    mode.board.combo = previous_combo

    def fake_super_lock(self):
        # super: hiç satır temizlenmedi -> combo sıfırlanır.
        self.board.combo = 0
        # Yeni parça spawn edildiğini simüle et (early-return tetiklenmesin)
        self.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(0, 0)])

    monkeypatch.setattr(Game, 'lock_and_new_piece', fake_super_lock)
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda *_a, **_kw: False, pending_choices=[])
    mode.perk_manager = SimpleNamespace(
        chrono_freeze_timer=0.0,
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda *_a, **_kw: None,
        on_piece_locked=lambda *_a, **_kw: None,
        maybe_trigger_alchemist=lambda *_a, **_kw: None,
    )

    mode._apply_score_multiplier_to_delta = lambda _d: 0
    mode._apply_line_clear_multiplier_to_delta = lambda *_a, **_kw: 0
    mode._apply_line_bonus_reward = lambda _l: None
    mode._apply_combo_aura_on_lock = lambda *_a, **_kw: None
    mode._apply_echo_drop_on_lock = lambda *_a, **_kw: None

    mode.lock_and_new_piece()

    # Combo sigortası tetiklendi: combo previous_combo'ya geri yüklendi.
    assert mode.board.combo == previous_combo
    # Sigorta tüketildi.
    assert mode._combo_insurance_armed is False
    # Aktif HUD'dan düştü.
    assert 'combo_insurance' not in mode._active_effect_visuals


def test_combo_insurance_does_not_consume_when_no_combo(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery()
    mode = _make_combo_mode(MysteryMode, Board)
    mode.board.combo = 0
    previous_combo = 0
    mode.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(4, 18)])
    mode._armed_nova_clusters = 0
    mode._rewind_available = False
    mode.energy = 0
    mode.energy_max = 100
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._speed_burst_timer = 0.0
    mode._speed_burst_line_mult = 1.0
    mode._freeze_drop_active = False
    mode._freeze_drop_timer = 0.0
    mode.board.combo = previous_combo

    monkeypatch.setattr(Game, 'lock_and_new_piece', lambda self: setattr(self, 'current_piece', SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(0, 0)])))
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda *_a, **_kw: False, pending_choices=[])
    mode.perk_manager = SimpleNamespace(
        chrono_freeze_timer=0.0,
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda *_a, **_kw: None,
        on_piece_locked=lambda *_a, **_kw: None,
        maybe_trigger_alchemist=lambda *_a, **_kw: None,
    )

    mode._apply_score_multiplier_to_delta = lambda _d: 0
    mode._apply_line_clear_multiplier_to_delta = lambda *_a, **_kw: 0
    mode._apply_line_bonus_reward = lambda _l: None
    mode._apply_combo_aura_on_lock = lambda *_a, **_kw: None
    mode._apply_echo_drop_on_lock = lambda *_a, **_kw: None

    mode.lock_and_new_piece()
    # Aktif combo yokken sigorta tüketilmemeli.
    assert mode._combo_insurance_armed is True
    assert 'combo_insurance' in mode._active_effect_visuals


def test_combo_insurance_only_triggers_once(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery()
    mode = _make_combo_mode(MysteryMode, Board)

    def setup_lock_state(prev):
        mode.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(4, 18)])
        mode._armed_nova_clusters = 0
        mode._rewind_available = False
        mode.energy = 0
        mode.energy_max = 100
        mode.sound_enabled = False
        mode.effects_enabled = False
        mode.line_bonus_remaining = 0
        mode.line_bonus_amount = 0
        mode._score_multiplier_timer = 0.0
        mode._score_multiplier_value = 1.0
        mode._line_clear_multiplier_remaining = 0
        mode._line_clear_multiplier_value = 1.0
        mode._speed_burst_timer = 0.0
        mode._speed_burst_line_mult = 1.0
        mode._freeze_drop_active = False
        mode._freeze_drop_timer = 0.0
        mode.board.combo = prev

    def fake_super_lock(self):
        self.board.combo = 0
        self.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(0, 0)])

    monkeypatch.setattr(Game, 'lock_and_new_piece', fake_super_lock)
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda *_a, **_kw: False, pending_choices=[])
    mode.perk_manager = SimpleNamespace(
        chrono_freeze_timer=0.0,
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda *_a, **_kw: None,
        on_piece_locked=lambda *_a, **_kw: None,
        maybe_trigger_alchemist=lambda *_a, **_kw: None,
    )
    mode._apply_score_multiplier_to_delta = lambda _d: 0
    mode._apply_line_clear_multiplier_to_delta = lambda *_a, **_kw: 0
    mode._apply_line_bonus_reward = lambda _l: None
    mode._apply_combo_aura_on_lock = lambda *_a, **_kw: None
    mode._apply_echo_drop_on_lock = lambda *_a, **_kw: None

    setup_lock_state(prev=3)
    mode.lock_and_new_piece()
    assert mode._combo_insurance_armed is False
    assert mode.board.combo == 3

    # 2. dry lock: bu kez sigorta yok, combo gerçekten sıfırlanmalı.
    setup_lock_state(prev=3)
    mode.lock_and_new_piece()
    assert mode.board.combo == 0


# === Ters Borç ===

def test_reverse_debt_apply_does_not_award_card_xp_or_queue(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board(width=4, height=6)
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode._reverse_debt_remaining = 0
    mode._reverse_debt_total = 5
    mode.pending_level_ups = 0
    mode.energy = 0
    mode.energy_max = 100
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._active_effect_visuals = {}
    mode._sync_active_cards = lambda: None
    mode._set_localized_card_message = lambda *_a, **_kw: ''
    mode.lock_delay = 500

    notify_calls = []
    perk_calls = []
    open_calls = []
    mode.card_manager = SimpleNamespace(
        used_card_ids=set(),
        notify_lines_cleared=lambda cleared, source='player', **kw: (notify_calls.append((cleared, source)) or False),
        pending_choices=[{'id': 'reward'}],  # external clear bunu bypass etmeli
    )
    mode.perk_manager = SimpleNamespace(
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda cleared, source='player': perk_calls.append((cleared, source)),
    )
    mode._open_card_selection = lambda: open_calls.append('open')
    mode._apply_score_multiplier_to_delta = lambda _d: 0
    mode._apply_line_clear_multiplier_to_delta = lambda *_a, **_kw: 0
    mode._apply_line_bonus_reward = lambda _l: None
    mode._queue_line_clear_effects = lambda *_a, **_kw: None

    # Tahtanın altındaki son 2 satırı tamamen doldur (clear_rows sonrası clear_lines doğal değil
    # ama _clear_rows zaten satırları kaldırır). Burada sadece state geçişini doğrularız.
    for x in range(mode.board.width):
        mode.board.occupancy[5][x] = True
        mode.board.grid[5][x] = (255, 255, 255)
        mode.board.occupancy[4][x] = True
        mode.board.grid[4][x] = (255, 255, 255)

    card = {
        'id': 'reverse_debt',
        'value': 2,
        'color': (200, 120, 255),
        'tag': 'Common',
        'rarity': 'common',
        'icon': 'RD',
        'title': 'Ters Borç',
    }

    mode._apply_card_effect(card)

    # State: remaining 5, lock_delay 0
    assert mode._reverse_debt_remaining == 5
    assert mode.lock_delay == 0
    # XP/queue üretmemeli (notify_lines_cleared external source ile çağrılmalı, player değil)
    for _, src in notify_calls:
        assert src in ('card', 'ability'), f"unexpected source: {src}"
    assert mode.pending_level_ups == 0
    assert open_calls == []


def test_reverse_debt_lock_counter_decrements_and_restores_lock_delay(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode._combo_insurance_armed = False
    mode._reverse_debt_remaining = 2
    mode._reverse_debt_total = 5
    mode.lock_delay = 0
    mode.current_piece = SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(4, 18)])
    mode._armed_nova_clusters = 0
    mode._rewind_available = False
    mode.energy = 0
    mode.energy_max = 100
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._speed_burst_timer = 0.0
    mode._speed_burst_line_mult = 1.0
    mode._freeze_drop_active = False
    mode._freeze_drop_timer = 0.0
    mode._active_effect_visuals = {'reverse_debt': {'id': 'reverse_debt', 'title': 'Ters Borç', 'color': (200, 120, 255)}}
    mode._sync_active_cards = lambda: None
    mode._set_localized_card_message = lambda *_a, **_kw: ''

    monkeypatch.setattr(Game, 'lock_and_new_piece', lambda self: setattr(self, 'current_piece', SimpleNamespace(name='I', drill=False, is_bomb=False, get_cells=lambda: [(0, 0)])))
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda *_a, **_kw: False, pending_choices=[])
    mode.perk_manager = SimpleNamespace(
        chrono_freeze_timer=0.0,
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda *_a, **_kw: None,
        on_piece_locked=lambda *_a, **_kw: None,
        maybe_trigger_alchemist=lambda *_a, **_kw: None,
    )
    mode._apply_score_multiplier_to_delta = lambda _d: 0
    mode._apply_line_clear_multiplier_to_delta = lambda *_a, **_kw: 0
    mode._apply_line_bonus_reward = lambda _l: None
    mode._apply_combo_aura_on_lock = lambda *_a, **_kw: None
    mode._apply_echo_drop_on_lock = lambda *_a, **_kw: None

    # 1. lock: 2 -> 1, lock_delay hala 0
    mode.lock_and_new_piece()
    assert mode._reverse_debt_remaining == 1
    assert mode.lock_delay == 0
    assert 'reverse_debt' in mode._active_effect_visuals

    # 2. lock: 1 -> 0, lock_delay normale döner
    mode.lock_and_new_piece()
    assert mode._reverse_debt_remaining == 0
    assert mode.lock_delay == 500
    assert 'reverse_debt' not in mode._active_effect_visuals


def test_reverse_debt_state_does_not_change_on_time_capsule_restore():
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = 'CURRENT'
    mode.next_piece_queue = []
    mode.held_piece = None
    mode.can_hold = True
    mode._reverse_debt_remaining = 3
    mode._reverse_debt_total = 5
    mode._combo_insurance_armed = True
    mode._hole_hunter_charges = 1
    mode.card_manager = SimpleNamespace(force_piece_queue=[], progress=0, threshold=5, pending_choices=[], active_cards=[], used_card_ids=set())
    mode.perk_manager = SimpleNamespace(active={}, next_piece_bomb=False, lines_since_chrono=0, chrono_freeze_timer=0.0, rewind_uses=0)

    data = mode._capture_time_capsule_state()
    mode._reverse_debt_remaining = 0
    mode._combo_insurance_armed = False
    mode._hole_hunter_charges = 0
    mode._restore_time_capsule_state(data)

    # Artik bu durumlar zaman kapsülü geri yuklemesiyle eski haline donmez, mevcuttaki hallerini korur.
    assert mode._reverse_debt_remaining == 0
    assert mode._reverse_debt_total == 5
    assert mode._combo_insurance_armed is False
    assert mode._hole_hunter_charges == 0


def test_reverse_debt_restore_does_not_affect_lock_behavior():
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = None
    mode.can_hold = True
    mode._reverse_debt_remaining = 4
    mode._reverse_debt_total = 5
    mode.lock_delay = 0  # Capture anında zaten 0 olsun
    mode.card_manager = SimpleNamespace(force_piece_queue=[], progress=0, threshold=5, pending_choices=[], active_cards=[], used_card_ids=set())
    mode.perk_manager = SimpleNamespace(active={}, next_piece_bomb=False, lines_since_chrono=0, chrono_freeze_timer=0.0, rewind_uses=0)

    data = mode._capture_time_capsule_state()

    # Aradan zaman geçmiş gibi: oyuncu Ters Borç süresini bitirmiş, lock_delay
    # default'a dönmüş.
    mode._reverse_debt_remaining = 0
    mode.lock_delay = 500

    mode._restore_time_capsule_state(data)

    # Artik zaman kapsülü bu degeri geri yuklemez, Ters Borc bitik kalir.
    assert mode._reverse_debt_remaining == 0
    assert mode.lock_delay == 500


def test_reverse_debt_restore_does_not_overwrite_active_lock_delay():
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = None
    mode.can_hold = True
    mode._reverse_debt_remaining = 0
    mode._reverse_debt_total = 5
    mode.lock_delay = 500
    mode.card_manager = SimpleNamespace(force_piece_queue=[], progress=0, threshold=5, pending_choices=[], active_cards=[], used_card_ids=set())
    mode.perk_manager = SimpleNamespace(active={}, next_piece_bomb=False, lines_since_chrono=0, chrono_freeze_timer=0.0, rewind_uses=0)

    data = mode._capture_time_capsule_state()

    # Capture sırasında remaining 0 idi. Şimdi başka bir Ters Borç anına gidiyormuş gibi:
    mode._reverse_debt_remaining = 5
    mode.lock_delay = 0

    mode._restore_time_capsule_state(data)

    # Geri yukleme sonrasinda Ters Borc aktif kalmaya devam eder, ezilmez.
    assert mode._reverse_debt_remaining == 5
    assert mode.lock_delay == 0


def test_apply_reverse_debt_lock_delay_helper_is_pure_derivation():
    """Helper, sayaca göre deterministic olarak lock_delay derive eder."""
    extra, _, MysteryMode, _ = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode._reverse_debt_remaining = 3
    mode.lock_delay = 999  # Yanlış değer
    mode._apply_reverse_debt_lock_delay()
    assert mode.lock_delay == 0

    mode._reverse_debt_remaining = 0
    mode._apply_reverse_debt_lock_delay()
    assert mode.lock_delay == 500


# === Hole Hunter Y-bound düzeltmesi ===

def test_hole_hunter_screen_to_column_rejects_clicks_above_board():
    """Tahtanın YUKARISINA tıklamak aynı sütun-x'e denk gelse bile sütun
    döndürmemeli. Daha önceki kör nokta: yalnız X kontrolü yapılıyordu."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    # Sütun 3'e karşılık gelen X koordinatı
    col_x = 100 + 3 * 30  # = 190
    # Tahtanın üstü
    above_y = 50
    assert mode._hole_hunter_screen_to_column((col_x, above_y)) is None


def test_hole_hunter_screen_to_column_rejects_clicks_below_board():
    """Tahtanın ALTINA tıklamak da reddedilmeli."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    col_x = 100 + 3 * 30
    board_h_px = mode.board.height * 30
    below_y = 200 + board_h_px + 10
    assert mode._hole_hunter_screen_to_column((col_x, below_y)) is None


def test_hole_hunter_screen_to_column_accepts_inside_board():
    """Tahta içindeki tıklama doğru sütunu döndürmeli."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    col_x = 100 + 3 * 30 + 5  # sütun 3'ün ortasına
    inside_y = 200 + 5 * 30 + 5  # 5. satır içinden
    assert mode._hole_hunter_screen_to_column((col_x, inside_y)) == 3


def test_hole_hunter_does_not_consume_charge_on_out_of_board_click(monkeypatch):
    """End-to-end: board üstüne tıklamak hak harcatmamalı, board değişmemeli,
    overlay açık kalmalı."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    # Board'da bir hole kuralım — eğer Y bound bug olsaydı, tahta üstüne tıklayınca
    # bu doldurulurdu.
    mode.board.occupancy[2][1] = True
    mode.board.grid[2][1] = (255, 80, 80)
    # col=1'de y=2 dolu, y=3 boş ama üstü dolu → kapalı hole

    snapshot_occ = [row[:] for row in mode.board.occupancy]
    snapshot_grid = [row[:] for row in mode.board.grid]

    col = mode._hole_hunter_screen_to_column((100 + 1 * 30 + 5, 50))
    assert col is None
    # Hak harcanmamalı:
    assert mode._hole_hunter_charges == 1
    # Overlay açık kalmalı:
    assert mode._hole_hunter_overlay_active is True
    # Board değişmemeli:
    assert mode.board.occupancy == snapshot_occ
    assert mode.board.grid == snapshot_grid


# === Doküman sayaç doğruluğu ===

def test_documentation_card_counts_match_real_catalog():
    """Doküman sayaçları gerçek katalogdan türetilmiş olmalı.

    Bu, "önce 34'tü, +3 olduk, 37 yazalım" gibi tahminleri yakalar. Gerçek
    katalog değiştiğinde bu test aileler ve toplam ID için tek doğruluk
    kaynağıdır.
    """
    extra, _, _, _ = _import_mystery()
    mgr = extra.MysteryCardManager(SimpleNamespace(settings_manager=None))

    total_ids = len(mgr.catalog)
    families = set()
    for card in mgr.catalog:
        families.add(str(card.get('_group_id') or card.get('id') or '').strip())
    family_count = len([f for f in families if f])

    repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

    inventory_path = os.path.join(repo_root, 'docs', 'CARD_PERK_INVENTORY_TR.md')
    list_path = os.path.join(repo_root, 'docs', 'KART_USTALIGI_KART_LISTESI_TR.md')

    with open(inventory_path, encoding='utf-8') as f:
        inventory_text = f.read()
    with open(list_path, encoding='utf-8') as f:
        list_text = f.read()

    expected_inventory_header = f'## Güncel Katalog ({total_ids} ID, {family_count} benzersiz aile)'
    assert expected_inventory_header in inventory_text, (
        f"CARD_PERK_INVENTORY_TR.md başlık katalogla uyumsuz. "
        f"Beklenen: '{expected_inventory_header}'"
    )

    expected_inventory_total = f'**{total_ids} ID**'
    assert expected_inventory_total in inventory_text, (
        f"CARD_PERK_INVENTORY_TR.md sayım özetinde 'Toplam katalog girdisi: "
        f"{expected_inventory_total}' bulunamadı."
    )

    expected_inventory_family = f'**{family_count}**'
    assert expected_inventory_family in inventory_text, (
        f"CARD_PERK_INVENTORY_TR.md sayım özetinde "
        f"'Benzersiz mekanik aile sayısı: {expected_inventory_family}' bulunamadı."
    )

    expected_list_header = (
        f'**{total_ids} kart girdisi** ({family_count} benzersiz mekanik aile,'
    )
    assert expected_list_header in list_text, (
        f"KART_USTALIGI_KART_LISTESI_TR.md başlığı katalogla uyumsuz. "
        f"Beklenen prefix: '{expected_list_header}'"
    )


# === Delik Avcısı ===

def _make_hole_hunter_mode(MysteryMode, Board):
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board(width=4, height=6)
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode._hole_hunter_charges = 1
    mode._hole_hunter_overlay_active = True
    mode._hole_hunter_cursor_col = 0
    mode._active_effect_visuals = {'hole_hunter': {'id': 'hole_hunter', 'title': 'Delik Avcısı', 'color': (140, 230, 200)}}
    mode._set_localized_card_message = lambda *_a, **_kw: ''
    mode._sync_active_cards = lambda: None
    mode._post_external_line_clear = lambda *_a, **_kw: None
    return mode


def test_hole_hunter_fills_one_closed_hole_and_consumes_charge(monkeypatch):
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)

    # col=0 sütununda: y=2 dolu, y=3,4 boş, y=5 dolu
    mode.board.occupancy[2][0] = True
    mode.board.grid[2][0] = (255, 80, 80)
    mode.board.occupancy[5][0] = True
    mode.board.grid[5][0] = (80, 200, 255)

    # Holes: y=3 ve y=4. random.choice y=3 döndürsün.
    monkeypatch.setattr(extra.random, 'choice', lambda seq: seq[0])

    mode._hole_hunter_cursor_col = 0
    ok = mode._hole_hunter_fire_at_cursor()
    assert ok is True
    assert mode.board.occupancy[3][0] is True
    # Diğer hole hala boş.
    assert mode.board.occupancy[4][0] is False
    # Hak harcandı.
    assert mode._hole_hunter_charges == 0
    # HUD'dan düştü.
    assert 'hole_hunter' not in mode._active_effect_visuals
    # Overlay kapandı.
    assert mode._hole_hunter_overlay_active is False


def test_hole_hunter_does_not_spend_on_invalid_column(monkeypatch):
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)

    # col=2: tamamen boş. hole bulunmaz; üstü dolu yok.
    mode._hole_hunter_cursor_col = 2
    ok = mode._hole_hunter_fire_at_cursor()
    assert ok is False
    assert mode._hole_hunter_charges == 1
    # Overlay açık kalmalı (oyuncu başka sütun seçmek isteyebilir).
    assert mode._hole_hunter_overlay_active is True


def test_hole_hunter_invalid_column_when_only_surface_holes(monkeypatch):
    """Yüzey üstü açık boşluklar 'hole' sayılmaz; üstünde dolu yoksa harcanmaz."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)

    # col=1: sadece y=5 dolu. y=0..4 boş ama hiçbiri "kapalı" değil çünkü
    # üstlerinde dolu yok.
    mode.board.occupancy[5][1] = True
    mode.board.grid[5][1] = (200, 200, 200)

    mode._hole_hunter_cursor_col = 1
    holes = mode._hole_hunter_find_holes(1)
    assert holes == []
    ok = mode._hole_hunter_fire_at_cursor()
    assert ok is False
    assert mode._hole_hunter_charges == 1


def test_hole_hunter_routes_resulting_full_row_through_card_source(monkeypatch):
    """Doldurma sonucu tam satır oluşursa external/card source clear olmalı,
    reward queue açılmamalı (notify_lines_cleared source!=player)."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)

    # Capture external clear çağrılarını
    external_calls = []
    mode._post_external_line_clear = (
        lambda cleared, *, award_energy=True, score_delta=None, source='card', **_kw: external_calls.append(
            {'cleared': cleared, 'source': source}
        )
    )

    # En altta 1 hücre eksik tam satır kuralım: y=5, x=0,1,2 dolu; x=3 boş.
    # x=3'ün üstünde y=4 dolu olsun ki x=3 sütununda y=5 "kapalı boşluk" olsun.
    for x in (0, 1, 2):
        mode.board.occupancy[5][x] = True
        mode.board.grid[5][x] = (255, 80, 80)
    mode.board.occupancy[4][3] = True
    mode.board.grid[4][3] = (255, 80, 80)
    # x=3 col'da y=5 tek hole.

    monkeypatch.setattr(extra.random, 'choice', lambda seq: seq[0])

    mode._hole_hunter_cursor_col = 3
    ok = mode._hole_hunter_fire_at_cursor()
    assert ok is True
    # Card-source clear akışı tetiklendi.
    assert any(call['source'] == 'card' for call in external_calls)


# === Localization ===

def test_new_card_titles_and_descriptions_resolve():
    extra, _, _, _ = _import_mystery()

    previous = get_language()
    try:
        assert set_language('en') is True
        assert extra.get_card_title({'id': 'combo_insurance', 'title': 'fallback'}) == 'Combo Insurance'
        assert 'combo' in extra.get_card_description({'id': 'combo_insurance', 'value': 1, 'description': 'fallback'}).lower()
        assert extra.get_card_title({'id': 'reverse_debt', 'title': 'fallback'}) == 'Reverse Debt'
        assert 'bottom 2 rows' in extra.get_card_description({'id': 'reverse_debt', 'value': 2, 'description': 'fallback'}).lower()
        assert extra.get_card_title({'id': 'hole_hunter', 'title': 'fallback'}) == 'Hole Hunter'
        assert 'column' in extra.get_card_description({'id': 'hole_hunter', 'value': 1, 'description': 'fallback'}).lower()

        assert set_language('tr') is True
        assert extra.get_card_title({'id': 'combo_insurance', 'title': 'fallback'}) == 'Combo Sigortası'
        assert extra.get_card_title({'id': 'reverse_debt', 'title': 'fallback'}) == 'Ters Borç'
        assert extra.get_card_title({'id': 'hole_hunter', 'title': 'fallback'}) == 'Delik Avcısı'
    finally:
        set_language(previous)


def test_new_cards_are_in_catalog():
    extra, _, _, _ = _import_mystery()
    mgr = extra.MysteryCardManager(SimpleNamespace(settings_manager=None))
    ids = {c['id'] for c in mgr.catalog}
    assert {'combo_insurance', 'reverse_debt', 'hole_hunter'}.issubset(ids)


# === 'limited' charge kartları seçildikten sonra tekrar sunulabilmeli ===

def _catalog_card(mgr, card_id: str) -> dict:
    card = next((c for c in mgr.catalog if c.get('id') == card_id), None)
    assert card is not None, f'{card_id} katalogda yok'
    return dict(card)


def test_select_limited_charge_card_does_not_permanently_exclude_it():
    """'limited' (tuşla tetiklenen hak veren) kartlar seçilince kalıcı olarak
    used_card_ids'e EKLENMEMELİ; aksi halde hak bitince bir daha seçim
    ekranında çıkmazlar. Delik Avcısı bu sınıftadır."""
    extra, _, _, _ = _import_mystery()
    mgr = extra.MysteryCardManager(SimpleNamespace(settings_manager=None))

    for card_id in ('hole_hunter', 'hammer', 'sniper_shot', 'quantum_tunneling'):
        mgr.used_card_ids.clear()
        mgr.pending_choices = [_catalog_card(mgr, card_id)]
        picked = mgr.select_card(0)
        assert picked is not None and picked['id'] == card_id
        # Kalıcı dışlama OLMAMALI:
        assert card_id not in mgr.used_card_ids
        group = picked.get('_group_id')
        if group:
            assert group not in mgr.used_card_ids


def test_select_instant_single_use_card_is_excluded():
    """Anlık (instant) single_use kartlar (Ters Borç, Alt Süpür) seçilince
    tek seferlik sayılmalı ve tekrar sunulmamalı."""
    extra, _, _, _ = _import_mystery()
    mgr = extra.MysteryCardManager(SimpleNamespace(settings_manager=None))

    for card_id in ('reverse_debt', 'clear_rows', 'gravity_well'):
        mgr.used_card_ids.clear()
        mgr.pending_choices = [_catalog_card(mgr, card_id)]
        picked = mgr.select_card(0)
        assert picked is not None and picked['id'] == card_id
        assert card_id in mgr.used_card_ids


def test_hole_hunter_reappears_in_pool_after_being_selected():
    """End-to-end: Delik Avcısı seçildikten sonra prepare_selection havuzunda
    hâlâ aday olabilmeli (debug modunda tüm katalog gösterilir)."""
    extra, _, _, _ = _import_mystery()
    mode = SimpleNamespace(settings_manager=SimpleNamespace(get=lambda k, d=None: True if k == 'card_mode_debug' else d))
    mgr = extra.MysteryCardManager(mode)
    mgr.card_level = 1

    mgr.pending_choices = [_catalog_card(mgr, 'hole_hunter')]
    mgr.select_card(0)

    choices = mgr.prepare_selection()
    chosen_ids = {c['id'] for c in choices}
    assert 'hole_hunter' in chosen_ids


# === Delik Avcısı mouse hover sütun seçimi ===

def test_hole_hunter_hover_column_tracks_x_even_above_board():
    """Mouse tahtanın ÜSTÜNDE olsa bile yatay hizalı sütun döndürülmeli
    (hover seçim için). Katı screen_to_column'dan farklı davranır."""
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    col_x = 100 + 2 * 30 + 5  # sütun 2
    above_y = 50  # tahtanın üstü
    # Katı helper tahta dışını reddeder:
    assert mode._hole_hunter_screen_to_column((col_x, above_y)) is None
    # Hover helper yalnız X'e bakar:
    assert mode._hole_hunter_hover_column((col_x, above_y)) == 2


def test_hole_hunter_hover_column_rejects_outside_x():
    extra, _, MysteryMode, Board = _import_mystery()
    mode = _make_hole_hunter_mode(MysteryMode, Board)
    mode.get_board_offset = lambda: (100, 200)
    mode.get_cell_size = lambda: 30

    board_w_px = mode.board.width * 30
    assert mode._hole_hunter_hover_column((100 - 5, 250)) is None
    assert mode._hole_hunter_hover_column((100 + board_w_px + 5, 250)) is None
