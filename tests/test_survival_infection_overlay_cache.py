# -*- coding: utf-8 -*-
"""P0-3 — Survival enfeksiyon overlay cache karakterizasyon testleri.

Uygulama_Denetimi_Iade_4K_Gamepad_Raporu.md P0-3 kabul kriterleri:
- SurvivalMode enfeksiyon overlay'i hücre başına pygame.Surface üretmez;
  _get_survival_infection_overlay (boyut+renk+bar-genişliği anahtarlı,
  160 girişli bounded LRU) aynı parametre için aynı Surface'ı döndürür.
- draw_mode_overlay ikinci karede YENİ Surface tahsis etmez (yalnızca
  ilk karede her anahtar için bir kez üretilir).
- Cache anahtarı bar_width'i boyuta clamp'ler; aşırı değerler güvenli.

v2 referans deseni (src/game_modes_advanced.py::_get_survival_infection_overlay)
quadrix-demo'ya dar kapsamlı taşındı; bu dosya o sözleşmeyi sabitler.
"""

from __future__ import annotations

import pygame

import game_modes_advanced as advanced_modes_module


GREEN = (100, 200, 50, 150)
YELLOW = (200, 200, 50, 180)


def _make_survival_mode(infected_blocks, survival_time=30000):
    """__new__ ile minimal SurvivalMode kurulumi (phase8 testleri kalıbı)."""
    mode = advanced_modes_module.SurvivalMode.__new__(advanced_modes_module.SurvivalMode)
    mode.screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    mode.window_width = 800
    mode.window_height = 600
    mode.game_over = False
    mode.survival_time = survival_time
    mode.antivirus_flash = 0
    mode.infected_blocks = dict(infected_blocks)
    mode.board_width = 10
    mode.board_height = 20
    mode.consume_time = 60000
    mode.get_cell_size = lambda: 32
    mode.get_board_offset = lambda: (50, 50)
    mode._draw_survival_panel = lambda: None
    return mode


def test_infection_overlay_returns_same_surface_for_same_params():
    mode = _make_survival_mode({})

    first = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, GREEN, 16, (100, 255, 100))
    second = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, GREEN, 16, (100, 255, 100))

    assert first is second, "aynı anahtar önbellekten aynı Surface nesnesini döndürmeli"


def test_infection_overlay_different_cell_size_creates_new_surface():
    mode = _make_survival_mode({})

    small = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 24, GREEN, 12, (100, 255, 100))
    large = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 48, GREEN, 24, (100, 255, 100))

    assert small is not large
    assert small.get_size() == (24, 24)
    assert large.get_size() == (48, 48)


def test_infection_overlay_distinguishes_color_and_bar_in_key():
    mode = _make_survival_mode({})

    green = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, GREEN, 16, (100, 255, 100))
    yellow = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, YELLOW, 16, (100, 255, 100))
    other_bar = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, GREEN, 20, (100, 255, 100))

    assert green is not yellow, "renk anahtarın parçası olmalı"
    assert green is not other_bar, "bar genişliği anahtarın parçası olmalı"


def test_infection_overlay_cache_is_bounded_at_160_entries():
    """Not: anahtardaki bar genişliği boyuta clamp'lenir; 160+ farklı
    anahtar üretmek için renk bileşenini değiştiriyoruz (v2 sözleşmesi)."""
    mode = _make_survival_mode({})

    oldest_key = (32, (0, 200, 50, 150), 16, (100, 255, 100))
    newest_key = (32, (160, 200, 50, 150), 16, (100, 255, 100))
    for shade in range(161):
        advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
            mode, 32, (shade, 200, 50, 150), 16, (100, 255, 100))

    cache = mode._survival_infection_overlay_cache
    order = mode._survival_infection_overlay_cache_order
    assert len(cache) <= 160, "LRU üst sınırı 160'ı aşmamalı"
    assert len(order) <= 160
    assert oldest_key not in cache, "en eski anahtar LRU'dan düşmeli"
    assert newest_key in cache, "en yeni anahtar cache'te kalmalı"


def test_infection_overlay_bar_width_is_clamped_into_key():
    mode = _make_survival_mode({})

    overlay = advanced_modes_module.SurvivalMode._get_survival_infection_overlay(
        mode, 32, GREEN, 9999, (100, 255, 100))

    assert overlay.get_size() == (32, 32)
    assert (32, tuple(GREEN), 32, (100, 255, 100)) in mode._survival_infection_overlay_cache


def test_draw_mode_overlay_allocates_no_surface_on_second_frame(monkeypatch):
    """P0-3 çekirdek iddiası: ikinci karede hücre başına tahsis YOK."""
    mode = _make_survival_mode({(0, 0): 0, (1, 1): 10000, (2, 2): 20000})

    surface_sizes = []
    original_surface = advanced_modes_module.pygame.Surface

    def surface_spy(size, *args, **kwargs):
        surface_sizes.append(tuple(size))
        return original_surface(size, *args, **kwargs)

    # P0-4: tam pakette pygame ailesi conftest tarafından düşürülüp yeniden
    # import edildiğinde modül kimlikleri ayrışabiliyor. Spy'ı hem bu
    # modülün (helper'in pygame global'i) hem Game tabanının pygame'ine kur
    # (kimlik-bağımsız gözlem).
    import inspect
    _game_mod = inspect.getmodule(
        next(cls for cls in mode.__class__.__mro__ if cls.__name__ == 'Game'))
    _patch_targets = [advanced_modes_module.pygame]
    if _game_mod is not None and _game_mod.pygame not in _patch_targets:
        _patch_targets.append(_game_mod.pygame)
    for _pg in _patch_targets:
        monkeypatch.setattr(_pg, 'Surface', surface_spy)

    advanced_modes_module.SurvivalMode.draw_mode_overlay(mode)
    first_frame_allocations = len(surface_sizes)

    advanced_modes_module.SurvivalMode.draw_mode_overlay(mode)

    assert first_frame_allocations == 3, (
        "ilk karede yalnızca anahtar başına bir kez üretilmeli "
        f"(3 farklı progress) — üretilen: {surface_sizes}"
    )
    assert surface_sizes[first_frame_allocations:] == [], (
        "ikinci karede yeni Surface tahsisi OLMAMALI (per-frame tahsis yasağı)"
    )
