# -*- coding: utf-8 -*-
"""DUZ-011: Mystery layout cell_size ölçek zinciri (scale_x) regresyon testleri.

Kök neden (kör kopya kanıtı): quadrix-demo, v2'nin 'sifirdan' (bc98f4b)
anlık görüntüsünden türedi; v2'de 220c937 ('çince ve 1600*900 sorunu
çözüldü herhalde', 10 Ağustos 2026) cell_size çarpanını pixel_ratio'dan
scale_x'e taşıdı, demo bu düzeltmeyi hiç almadı. pixel_ratio
(gameplay_layout.get_display_pixel_ratio) = min(sx, sy) + [0.5, 4.0]
clamp'tir; clamp dışında 1.0'a snap eder, asimetrik oranlarda daraltan
ekseni seçer ve board_x/board_width/panel ölçülerinin scale_x zinciriyle
ayrışır — hücreler tahtayı doldurmaz ya da taşırırdı.

Kabul ölçütleri (Iade_Duzeltme_Plani.md DUZ-011):
- Logical/UI scale ile pixel ratio iki kez çarpılmaz; cell_size daima
  scale_x zincirinde tek çarpımla projekte edilir.
- Clamp senaryolarında (küçük pencere / enli pencere) cell_size board
  alanıyla tutarlı kalır.
- Sol kart paneli genişliği layout hesaplayıcısına rezerve bildirilir
  (v2 220c937'nin ikinci yarısı; 1600x900 sol panel çakışması).

Bilinçli dokunulmayanlar (v2 ile birebir): metrics['pixel_ratio'] rapor
alanı ve hud_px_scale = hud_scale * pixel_ratio pixel_ratio'da kalır.
"""
from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.game_modes_extra import MysteryMode
from src.gameplay_layout import get_display_pixel_ratio


class _FakeMysterySelf:
    """MysteryMode._get_mystery_layout_metrics için minimal sahte self.

    Yalnız fonksiyonun dokunduğu üyelere sahiplik eder: _active_ui_size,
    _effective_ui_size, _display_pixel_ratio, board_width/board_height/
    left_panel_max_width ve layout cache alanları.
    """

    def __init__(self, active: tuple[int, int], effective: tuple[int, int]) -> None:
        self._active_size = active
        self._effective_size = effective
        self.board_width = 10
        self.board_height = 20
        self.left_panel_max_width = 420
        self._mystery_layout_cache_key = None

    def _active_ui_size(self) -> tuple[int, int]:
        return self._active_size

    def _effective_ui_size(self) -> tuple[int, int]:
        return self._effective_size

    def _display_pixel_ratio(self) -> float:
        # Game._display_pixel_ratio ile birebir davranış (demo game.py).
        return get_display_pixel_ratio(self._active_size, self._effective_size)


# Gerçek layout hesaplayıcısını sahte self'e bağla: get_cell_size ve
# _get_left_gameplay_reserve_width içindeki self._get_mystery_layout_metrics()
# çağrıları böylece gerçek fonksiyona çözülür.
_FakeMysterySelf._get_mystery_layout_metrics = MysteryMode._get_mystery_layout_metrics


def _metrics_for(active: tuple[int, int], effective: tuple[int, int]):
    fake = _FakeMysterySelf(active, effective)
    metrics = MysteryMode._get_mystery_layout_metrics(fake)
    return fake, metrics


# SDL2 FAZ 1 sonrası effective (logical) boyut daima 1920x1080'dir;
# senaryolar bu varsayım üzerindeki gerçek pencere boyutlarını örnekler.
EFFECTIVE_SIZE = (1920, 1080)

# active 900x506 → scale_x ≈ 0.469 < 0.5 → get_display_pixel_ratio 1.0'a
# snap eder. Eski (buglı) cell_size = logical * pixel_ratio burada
# ölçeklenmeden kalır ve board_x/board_width (scale_x) ile ayrışır.
CLAMP_ACTIVE_SIZE = (900, 506)

# active 1920x824 → scale_x = 1.0, scale_y ≈ 0.763 → pixel_ratio = 0.763
# (min eksen y). cell_size x-ekseni board ölçüleriyle aynı zincirde
# kalmalıdır; pixel_ratio'yla çarpılsaydı %24 küçülürdü.
WIDE_ACTIVE_SIZE = (1920, 824)

# Kartın adı geçen çözünürlüğü: 1600x900 → scale_x = scale_y ≈ 0.833,
# pixel_ratio = 0.833 (clamp içi, simetrik).
SYMMETRIC_SMALL_SIZE = (1600, 900)


def test_cell_size_projects_with_scale_x_under_pixel_ratio_clamp():
    """Küçük pencere (clamp dışı) — pixel_ratio 1.0'a snap etse de cell_size
    scale_x ile ölçeklenmelidir; logical boyutta donup kalmamalıdır."""
    _fake, metrics = _metrics_for(CLAMP_ACTIVE_SIZE, EFFECTIVE_SIZE)

    scale_x = CLAMP_ACTIVE_SIZE[0] / EFFECTIVE_SIZE[0]
    assert metrics['pixel_ratio'] == 1.0  # clamp dışı → snap kanıtı
    assert scale_x < 0.5
    expected = max(1, int(round(float(metrics['logical_cell_size']) * scale_x)))
    assert metrics['cell_size'] == expected
    assert metrics['cell_size'] < metrics['logical_cell_size']


def test_cell_size_uses_scale_x_when_min_axis_differs():
    """Enli pencere — pixel_ratio daraltan y eksenini seçtiğinde dahi
    cell_size scale_x'i izlemelidir (x-ekseni board zinciri)."""
    _fake, metrics = _metrics_for(WIDE_ACTIVE_SIZE, EFFECTIVE_SIZE)

    scale_x = WIDE_ACTIVE_SIZE[0] / EFFECTIVE_SIZE[0]
    scale_y = WIDE_ACTIVE_SIZE[1] / EFFECTIVE_SIZE[1]
    assert abs(metrics['pixel_ratio'] - scale_y) < 1e-6
    assert scale_x == 1.0
    assert metrics['cell_size'] == metrics['logical_cell_size']


def test_cell_grid_fills_board_width_across_scale_scenarios():
    """cell_size * board_cols, metrics['board_width'] ile tutarlı olmalıdır
    (yuvarlama birikimi toleransıyla) — ölçek ne olursa olsun."""
    scenarios = [
        (3840, 2160),  # 4K simetrik (scale = 2.0)
        CLAMP_ACTIVE_SIZE,
        WIDE_ACTIVE_SIZE,
        SYMMETRIC_SMALL_SIZE,
    ]
    for active in scenarios:
        _fake, metrics = _metrics_for(active, EFFECTIVE_SIZE)
        cols = _fake.board_width
        grid_width = metrics['cell_size'] * cols
        assert abs(metrics['board_width'] - grid_width) <= cols, (
            f"active={active}: board_width={metrics['board_width']} "
            f"cell*cols={grid_width}"
        )


def test_cell_grid_fills_board_height_on_symmetric_scales():
    """Simetrik oranlarda (scale_x == scale_y) dikey ızgara da board_height
    ile tutarlı kalır; asimetrik senaryoda y ekseni v2 ile aynı biçimde
    scale_y zincirindedir (bilinçli davranış, ayrı test konusu değil)."""
    for active in [(3840, 2160), SYMMETRIC_SMALL_SIZE]:
        _fake, metrics = _metrics_for(active, EFFECTIVE_SIZE)
        rows = _fake.board_height
        grid_height = metrics['cell_size'] * rows
        assert abs(metrics['board_height'] - grid_height) <= rows


def test_get_cell_size_is_passthrough_no_double_scaling():
    """get_cell_size yalnız int() cast'i yapar — cell_size üzerinde ikinci
    bir ölçek çarpanı (logical/UI scale veya pixel ratio) uygulanmaz."""
    fake, metrics = _metrics_for((3840, 2160), EFFECTIVE_SIZE)

    assert MysteryMode.get_cell_size(fake) == int(metrics['cell_size'])
    assert MysteryMode.get_cell_size(fake) == metrics['cell_size']


def test_left_panel_reserve_reported_for_1600x900():
    """v2 220c937'nin ikinci yarısı: MysteryMode sol kart panel genişliğini
    layout hesaplayıcısına bildirir (base Game stub'ı 0 döndürür)."""
    fake, metrics = _metrics_for(SYMMETRIC_SMALL_SIZE, EFFECTIVE_SIZE)

    reserve = MysteryMode._get_left_gameplay_reserve_width(fake)
    assert reserve == int(metrics['left_panel_width'])
    assert reserve > 0


def test_mystery_layout_metrics_cache_roundtrip():
    """Aynı boyut anahtarıyla ikinci çağrı cache'ten aynı sözlüğü döndürür
    (ana döngüde yeniden hesap/yüzey churn'ü oluşmaz)."""
    fake, first = _metrics_for((3840, 2160), EFFECTIVE_SIZE)
    assert fake._mystery_layout_cache_key is not None

    second = MysteryMode._get_mystery_layout_metrics(fake)
    assert second is first


def test_pixel_ratio_report_and_hud_px_scale_unchanged():
    """v2 ile birebir senkron kalan alanlar: metrics['pixel_ratio'] rapor
    edilir ve hud_px_scale = hud_scale * pixel_ratio formülü korunur."""
    _fake, metrics = _metrics_for((3840, 2160), EFFECTIVE_SIZE)

    assert 'pixel_ratio' in metrics
    assert metrics['hud_px_scale'] == metrics['hud_scale'] * metrics['pixel_ratio']
