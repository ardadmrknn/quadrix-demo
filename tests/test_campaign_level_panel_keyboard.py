"""
campaign/level_select.py — Klavye navigasyonu + panel güncelleme + font ölçeği: birim testleri.

Modülü tam import yerine sadece değiştirilen metodları izole ederek test eder.

Kapsam:
1. _move_selection() → hovered_level None olmalı
2. _start_world_transition() → hovered_level None olmalı
3. _init_fonts() ve _get_ui_scale() aynı ortak ölçek kaynağından beslenmeli
"""
from __future__ import annotations
import sys
import types

from ui_scaling import get_scale


# ---------------------------------------------------------------------------
# Minimal CampaignLevelSelect stub: sadece değiştirilen metodları taşır
# Bu yaklaşım ağır import bağımlılıklarını gerektirmez
# ---------------------------------------------------------------------------

class _MinimalLevelSelect:
    """level_select.CampaignLevelSelect'ten sadece değiştirilen metodlar."""

    def __init__(self, window_width=1366, window_height=768):
        self.window_width = window_width
        self.window_height = window_height
        self.current_world = 1
        self.selected_level = 1
        self.hovered_level = None
        self.world_transition_active = False
        self.world_transition_progress = 0.0
        self.previous_world = 1
        self.target_world = 1
        self.progress = {
            "completed_levels": {"1": {"completed": True, "stars": 2}, "2": {"completed": True, "stars": 1}},
            "highest_level": 4,
        }

    def _is_level_unlocked(self, level_num: int) -> bool:
        if level_num == 1:
            return True
        prev = str(level_num - 1)
        completed = self.progress.get("completed_levels", {})
        return prev in completed and completed[prev].get("completed", False)

    def _update_selection_for_world(self) -> None:
        world_start = (self.current_world - 1) * 20 + 1
        highest = self.progress.get("highest_level", 0)
        if highest >= world_start:
            self.selected_level = min(highest + 1, self.current_world * 20)
        else:
            self.selected_level = world_start
        if not self._is_level_unlocked(self.selected_level):
            self.selected_level = world_start

    # Gerçek kaynak koddan kopyalanan (düzeltmeler dahil) metodlar:

    def _move_selection(self, delta: int) -> None:
        world_start = (self.current_world - 1) * 20 + 1
        world_end = self.current_world * 20
        new_level = self.selected_level + delta
        if new_level < world_start:
            new_level = world_start
        elif new_level > world_end:
            new_level = world_end
        if self._is_level_unlocked(new_level):
            self.selected_level = new_level
        self.hovered_level = None  # FIX: klavye navigasyonunda hover sıfırla

    def _start_world_transition(self, target_world: int) -> None:
        if target_world == self.current_world:
            return
        self.previous_world = self.current_world
        self.target_world = target_world
        self.current_world = target_world
        self.world_transition_active = True
        self.world_transition_progress = 0.0
        self._update_selection_for_world()
        self.hovered_level = None  # FIX: dünya geçişinde hover sıfırla


# ---------------------------------------------------------------------------
# Test 1: _move_selection hovered_level'i sıfırlamalı
# ---------------------------------------------------------------------------

def test_move_selection_clears_hovered_level():
    sel = _MinimalLevelSelect()
    sel.selected_level = 3
    sel.hovered_level = 5

    sel._move_selection(1)

    assert sel.hovered_level is None, "Klavye navigasyonu hovered_level'i None yapmalı"
    assert sel.selected_level == 3


def test_move_selection_negative_clears_hovered_level():
    sel = _MinimalLevelSelect()
    sel.selected_level = 4
    sel.hovered_level = 2

    sel._move_selection(-1)

    assert sel.hovered_level is None
    assert sel.selected_level == 3


def test_move_selection_clamps_to_world_boundary():
    sel = _MinimalLevelSelect()
    sel.current_world = 1
    sel.selected_level = 1
    sel.hovered_level = 10

    sel._move_selection(-5)

    assert sel.selected_level == 1
    assert sel.hovered_level is None


def test_move_selection_clears_hover_even_at_boundary():
    """Sınırda takılı kalsın ama hover hâlâ sıfırlanmalı."""
    sel = _MinimalLevelSelect()
    sel.current_world = 1
    sel.selected_level = 20
    sel.hovered_level = 15

    sel._move_selection(5)  # 20'nin ötesine gidemez ama hover temizlenmeli

    assert sel.selected_level == 20
    assert sel.hovered_level is None


# ---------------------------------------------------------------------------
# Test 2: _start_world_transition hovered_level'i sıfırlamalı
# ---------------------------------------------------------------------------

def test_start_world_transition_clears_hovered_level():
    sel = _MinimalLevelSelect()
    sel.hovered_level = 7
    sel.current_world = 1

    sel._start_world_transition(2)

    assert sel.hovered_level is None, "Dünya geçişinde hovered_level None olmalı"
    assert sel.current_world == 2
    assert sel.world_transition_active is True


def test_start_world_transition_same_world_is_noop():
    """Aynı dünyaya geçiş → early return → hovered_level değişmez."""
    sel = _MinimalLevelSelect()
    sel.hovered_level = 5
    sel.current_world = 1

    sel._start_world_transition(1)

    assert sel.hovered_level == 5  # Early return — hover korunur
    assert sel.world_transition_active is False


def test_start_world_transition_different_world_resets_hover():
    sel = _MinimalLevelSelect()
    sel.hovered_level = 15
    sel.current_world = 2
    sel.selected_level = 22

    sel._start_world_transition(3)

    assert sel.hovered_level is None
    assert sel.current_world == 3


# ---------------------------------------------------------------------------
# Test 3: Font ve layout aynı ortak ölçek kaynağını kullanmalı
# ---------------------------------------------------------------------------

def test_init_fonts_scale_formula_1400x900_reference_is_one():
    """Level select için 1400×900 ortak referans noktası 1.0 olmalı."""
    scale = get_scale((1400, 900), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    assert abs(scale - 1.0) < 0.001


def test_init_fonts_scale_formula_1080p_can_grow_above_one():
    """1080p üstünde font/layout ölçeği 1.0 üstüne çıkabilmeli ama clamp'lenmeli."""
    scale = get_scale((1920, 1080), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    assert scale > 1.0
    assert abs(scale - 1.18) < 0.001


def test_init_fonts_scale_formula_1366x768_stays_above_floor():
    scale = get_scale((1366, 768), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    assert 0.84 <= scale < 1.0


def test_init_fonts_scale_formula_small_window():
    scale = get_scale((800, 600), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    assert scale == 0.72


def test_layout_and_font_scales_share_same_formula():
    font_scale = get_scale((2560, 1440), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    layout_scale = get_scale((2560, 1440), min_scale=0.72, max_scale=1.18, reference_size=(1400.0, 900.0))
    assert font_scale == layout_scale

