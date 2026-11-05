"""Shared gameplay layout policy for large displays and HiDPI surfaces.

Policy summary:
- UI readability decisions are derived from effective/logical display size.
- Gameplay occupancy is also decided in logical units so Retina back buffers do
  not artificially shrink the board.
- Final draw geometry is projected back into the active/raw surface size.

This keeps classic fullscreen rendering in raw pixel space while still letting
large logical displays and HiDPI Macs grow the playable area in a controlled
way.
"""

from __future__ import annotations

from dataclasses import dataclass


GAMEPLAY_OCCUPANCY_REFERENCE_SIZE = (1366.0, 768.0)

# I-46 (S-21 v2): Gizli satırlar artık AYRI bir şerit değil — tahtanın kendisi
# `görünür + gizli` satır yüksekliğinde hesaplanır ve gizli satırlar normal
# bloklarla çizilir (TGM/tetr.io buffer bölgesi gibi: bloklar görünür, ızgara
# yok). Bu yüzden ayrı bir bant yüksekliği sabiti YOK; yerleşimin tek kaynağı
# `board_height` argümanıdır.
HIDDEN_ROWS = 2


def total_board_rows(visible_height: int, hidden_rows: int = HIDDEN_ROWS) -> int:
    """Yerleşimin hesaplayacağı toplam satır: görünür + gizli (20 + 2 = 22)."""
    return max(1, int(visible_height)) + max(0, int(hidden_rows))


def _coerce_size(size: tuple[int, int] | list[int]) -> tuple[int, int]:
    width = max(1, int(size[0]))
    height = max(1, int(size[1]))
    return width, height


def _clamp_int(value: float, minimum: int, maximum: int) -> int:
    return max(int(minimum), min(int(maximum), int(round(float(value)))))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def get_display_pixel_ratio(
    active_size: tuple[int, int] | list[int],
    effective_size: tuple[int, int] | list[int],
) -> float:
    active_w, active_h = _coerce_size(active_size)
    effective_w, effective_h = _coerce_size(effective_size)

    if effective_w <= 0 or effective_h <= 0:
        return 1.0

    ratio_x = active_w / float(effective_w)
    ratio_y = active_h / float(effective_h)
    ratio = min(ratio_x, ratio_y)
    if ratio < 0.5 or ratio > 4.0:
        return 1.0
    return float(ratio)


@dataclass(frozen=True)
class SinglePlayerLayoutMetrics:
    cell_size: int
    board_x: int
    board_y: int
    board_width: int
    board_height: int
    panel_x: int
    panel_y: int
    panel_width: int
    panel_height: int
    panel_gap: int
    outer_margin: int
    panel_bottom_margin: int
    hud_scale: float
    hud_px_scale: float
    logical_cell_size: int
    logical_panel_width: int
    pixel_ratio: float
    occupancy_scale: float
    # I-46: Tahtanın kaç satırı gizli buffer. `board_height` görünür satır
    # sayısıdır; çizim/yerleşim `board_height + hidden_rows` satır kullanır.
    hidden_rows: int = 0
    # Görünür alanın tahta içindeki Y pikseli (gizli satırlar bunun üstünde).
    visible_top_y: int = 0


@dataclass(frozen=True)
class CoopLayoutMetrics:
    cell_size: int
    board_x: int
    board_y: int
    board_width: int
    board_height: int
    side_panel_width: int
    top_margin: int
    bottom_margin: int
    logical_cell_size: int
    logical_side_panel_width: int
    pixel_ratio: float
    occupancy_scale: float


def compute_single_player_layout(
    *,
    active_size: tuple[int, int] | list[int],
    effective_size: tuple[int, int] | list[int],
    board_width: int,
    board_height: int,
    info_panel_height: int = 120,
    left_group_reserve_px: int = 0,
    canvas_safe_rect: tuple[int, int, int, int] | None = None,
        hidden_rows: int = HIDDEN_ROWS,
) -> SinglePlayerLayoutMetrics:
    """FAZ A6: board + yan HUD + sol kart aynı parent safe rect'i paylaşır.

    canvas_safe_rect verilirse (A1 RenderGeometry.safe_rect — canvas uzayında
    x, y, w, h) dış marj safe alanla birleştirilir: board/panel koordinat
    clamp'ları tek outer_margin kaynağından türer, merkezleme değişmeden
    P0 içerik güvenli alana sabitlenir. None → eski davranış (yalnızca
    outer_margin) — geriye dönük uyumlu.
    """
    active_w, active_h = _coerce_size(active_size)
    effective_w, effective_h = _coerce_size(effective_size)
    board_cols = max(1, int(board_width))
    board_rows = max(1, int(board_height))

    scale_x = active_w / float(max(1, effective_w))
    scale_y = active_h / float(max(1, effective_h))
    pixel_ratio = get_display_pixel_ratio((active_w, active_h), (effective_w, effective_h))

    # FAZ A6 (S6): safe rect marjı logical uzaya çevrilip outer_margin'a
    # katılır — board/HUD/sol kartın ortak parent'ı safe alan olur.
    safe_margin_x_logical = 0
    safe_margin_y_logical = 0
    if canvas_safe_rect is not None:
        try:
            sx0, sy0, sw, sh = canvas_safe_rect
            if sw > 0 and sh > 0:
                safe_margin_x_logical = int(round(max(sx0, active_w - (sx0 + sw)) / max(scale_x, 0.001)))
                safe_margin_y_logical = int(round(max(sy0, active_h - (sy0 + sh)) / max(scale_y, 0.001)))
        except Exception:
            safe_margin_x_logical = 0
            safe_margin_y_logical = 0
    left_group_reserve_logical = max(
        0,
        int(round(float(left_group_reserve_px) / max(scale_x, 0.001))),
    )
    occupancy_scale = _clamp_float(
        min(
            effective_w / float(GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[0]),
            effective_h / float(GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[1]),
        ),
        1.0,
        2.15,
    )

    max_cell_logical = _clamp_int(40 + ((occupancy_scale - 1.0) * 14.0), 40, 56)
    panel_pref_logical = _clamp_int(220 + ((occupancy_scale - 1.0) * 90.0), 220, 320)
    panel_min_logical = _clamp_int(120 + ((occupancy_scale - 1.0) * 24.0), 120, 150)
    panel_gap_logical = _clamp_int(25 + ((occupancy_scale - 1.0) * 8.0), 25, 40)
    outer_margin_logical = _clamp_int(12 + ((occupancy_scale - 1.0) * 10.0), 12, 28)
    # FAZ A6: safe alan marjı dış marj tabanına katılır (board_x/panel_x
    # clamp'ları bu tek kaynaktan türer).
    outer_margin_logical = max(outer_margin_logical, safe_margin_x_logical)
    # KULLANICI KARARI (2026-11-05, kırmızı çerçeve): oyun alanı ekranın
    # dikey ORTASINA oturur — 22 satırlık blok (gizli bant + görünür alan)
    # eşit üst/alt payla ortalanır. Önceki `+ top_shift` kuralı tahtayı
    # ölçülen hedefin 27 px altına itiyordu (1080p: görünür tepe 180,
    # istenen 152). Taşma güvenliği: ortalanmış blok her zaman sığar.
    top_shift_logical = 0
    panel_top_padding_logical = _clamp_int(10 + ((occupancy_scale - 1.0) * 3.0), 10, 16)
    panel_bottom_margin_logical = _clamp_int(40 + ((occupancy_scale - 1.0) * 8.0), 40, 56)

    board_area_width_logical = max(
        160,
        int(effective_w)
        - (outer_margin_logical * 2)
        - left_group_reserve_logical
        - panel_gap_logical
        - panel_pref_logical,
    )
    board_area_height_logical = max(160, int(effective_h) - int(info_panel_height))

    # I-46: `board_height` GÖRÜNÜR satır sayısıdır; yerleşim gizli buffer'ı da
    # hesaba katar (20 görünür + 2 gizli = 22). Hücre boyu toplam satıra bölünür
    # — aksi halde gizli satırlar tahtanın üstünde ekran dışına taşardı.
    total_rows = total_board_rows(board_rows, hidden_rows)

    cell_by_width = max(14, board_area_width_logical // board_cols)
    cell_by_height = max(14, board_area_height_logical // total_rows)
    logical_cell_size = max(14, min(cell_by_width, cell_by_height, max_cell_logical))

    logical_board_width = board_cols * logical_cell_size
    # Toplam yükseklik gizli satırları içerir: gizli bölge ekranın üstüne
    # taşar gibi davranmaz, gerçek bloklar olarak görünür.
    logical_board_height = total_rows * logical_cell_size
    logical_visible_height = board_rows * logical_cell_size

    logical_panel_width = panel_pref_logical
    if left_group_reserve_logical > 0:
        total_group_width = (
            left_group_reserve_logical + logical_board_width + panel_gap_logical + logical_panel_width
        )
        logical_group_x = max(
            outer_margin_logical,
            (int(effective_w) - total_group_width) // 2,
        )
        max_group_x = max(
            outer_margin_logical,
            int(effective_w) - outer_margin_logical - total_group_width,
        )
        logical_group_x = max(outer_margin_logical, min(logical_group_x, max_group_x))
        logical_board_x = logical_group_x + left_group_reserve_logical
        logical_panel_x = logical_board_x + logical_board_width + panel_gap_logical
        logical_available_right = max(80, int(effective_w) - outer_margin_logical - logical_panel_x)
        logical_panel_width = min(panel_pref_logical, logical_available_right)
        logical_panel_width = max(min(panel_min_logical, logical_available_right), logical_panel_width)

        total_group_width = (
            left_group_reserve_logical + logical_board_width + panel_gap_logical + logical_panel_width
        )
        logical_group_x = max(
            outer_margin_logical,
            (int(effective_w) - total_group_width) // 2,
        )
        max_group_x = max(
            outer_margin_logical,
            int(effective_w) - outer_margin_logical - total_group_width,
        )
        logical_group_x = max(outer_margin_logical, min(logical_group_x, max_group_x))
        logical_board_x = logical_group_x + left_group_reserve_logical
        logical_panel_x = logical_board_x + logical_board_width + panel_gap_logical
    else:
        logical_board_x = max(
            outer_margin_logical,
            (int(effective_w) - logical_board_width) // 2,
        )
        max_board_x = max(
            outer_margin_logical,
            int(effective_w)
            - outer_margin_logical
            - panel_gap_logical
            - panel_min_logical
            - logical_board_width,
        )
        logical_board_x = max(outer_margin_logical, min(logical_board_x, max_board_x))
        logical_panel_x = logical_board_x + logical_board_width + panel_gap_logical
        logical_available_right = max(80, int(effective_w) - outer_margin_logical - logical_panel_x)
        logical_panel_width = min(panel_pref_logical, logical_available_right)
        logical_panel_width = max(min(panel_min_logical, logical_available_right), logical_panel_width)

    # `logical_board_y` tahtanın TOPLAM tepesidir (gizli bant + görünür alan).
    # Hücre boyu yukarıda `total_rows` üzerinden sabitlendiği için tahta ekrana
    # sığar; burada yalnız dikey hizalama uygulanır.
    #
    # KULLANICI KARARI (ekran görüntüsündeki kırmızı çerçeve, 2026-11-05):
    # tahta ekranın dikey ORTASINA yerleşir; `top_shift` sıfırdır. Ölçüm
    # (1080p, kırmızı çerçeve): görünür alan tepesi 152, alt 1016; 22 satırlık
    # blok orta 67'de başlıyor → 67 + 2*43 = 153 görünür tepe. Eski
    # `+ top_shift` kuralı 180 veriyordu (28 px fazla aşağı).
    #
    # TAŞMA GÜVENLİĞİ: ortalanmış blok her çözünürlükte sığar; alt/üst pay
    # eşittir (1080p'de 67+67). tests/feedback_fixes/
    # test_phase6b_hidden_row_visual.py tüm presetlerde doğrular.
    #
    # Tavan hizası tek kaynak: sol panel ve sağ HUD da bu `logical_board_y`'ye
    # hizalanır (bkz. Game._get_right_hud_panel_metrics, SprintMode.draw_mode_info).
    logical_board_y = max(
        max(8, safe_margin_y_logical),
        ((int(effective_h) - logical_board_height) // 2) + top_shift_logical,
    )
    logical_panel_y = logical_board_y + panel_top_padding_logical
    logical_panel_height = min(
        logical_board_height,
        max(80, int(effective_h) - logical_panel_y - panel_bottom_margin_logical),
    )

    cell_size = max(1, int(round(float(logical_cell_size) * pixel_ratio)))
    board_width_px = board_cols * cell_size
    # `board_height` = görünür satır yüksekliği (ör. 20 satır). Gizli buffer
    # bunun ÜSTÜNDE yer alır; `board_y` toplam bloğun (gizli + görünür) tepesidir.
    board_height_px = board_rows * cell_size
    board_total_height_px = total_rows * cell_size
    board_x = max(0, int(round(float(logical_board_x) * scale_x)))
    board_y = max(0, int(round(float(logical_board_y) * scale_y)))
    panel_x = max(0, int(round(float(logical_panel_x) * scale_x)))
    panel_y = max(0, int(round(float(logical_panel_y) * scale_y)))
    panel_width_px = max(1, int(round(float(logical_panel_width) * scale_x)))
    panel_height_px = max(1, int(round(float(logical_panel_height) * scale_y)))
    panel_gap_px = max(1, int(round(float(panel_gap_logical) * scale_x)))
    outer_margin_px = max(1, int(round(float(outer_margin_logical) * scale_x)))
    panel_bottom_margin_px = max(1, int(round(float(panel_bottom_margin_logical) * scale_y)))

    hud_scale = _clamp_float(logical_panel_width / 220.0, 0.72, 1.18)
    hud_px_scale = float(hud_scale) * float(pixel_ratio)

    # I-46 (S-21 v2): Ayrı şerit/kaydırma YOK. Gizli satırlar artık tahtanın
    # kendi yüksekliğine dahil edildi (`total_rows`), bu yüzden hücre boyu
    # hesabı onları zaten karşılıyor. Tahta ekranın üstüne taşarsa hücre
    # küçülür — sabit piksel kaydırma yok.
    #
    # Görünür alan gizli buffer'ın ALTINDA başlar; ızgara/arka plan bu noktadan
    # itibaren çizilir. `board_y` toplam bloğun tepesidir.
    visible_top_y_px = max(0, board_y + (board_total_height_px - board_height_px))

    return SinglePlayerLayoutMetrics(
        cell_size=cell_size,
        board_x=board_x,
        board_y=board_y,
        board_width=board_width_px,
        board_height=board_height_px,
        panel_x=panel_x,
        panel_y=panel_y,
        panel_width=panel_width_px,
        panel_height=panel_height_px,
        panel_gap=panel_gap_px,
        outer_margin=outer_margin_px,
        panel_bottom_margin=panel_bottom_margin_px,
        hud_scale=hud_scale,
        hud_px_scale=hud_px_scale,
        logical_cell_size=logical_cell_size,
        logical_panel_width=logical_panel_width,
        pixel_ratio=pixel_ratio,
        occupancy_scale=occupancy_scale,
        hidden_rows=hidden_rows,
        visible_top_y=visible_top_y_px,
    )


def compute_coop_layout(
    *,
    active_size: tuple[int, int] | list[int],
    effective_size: tuple[int, int] | list[int],
    board_width: int,
    board_height: int,
) -> CoopLayoutMetrics:
    active_w, active_h = _coerce_size(active_size)
    effective_w, effective_h = _coerce_size(effective_size)
    board_cols = max(1, int(board_width))
    board_rows = max(1, int(board_height))

    scale_x = active_w / float(max(1, effective_w))
    scale_y = active_h / float(max(1, effective_h))
    pixel_ratio = get_display_pixel_ratio((active_w, active_h), (effective_w, effective_h))
    occupancy_scale = _clamp_float(
        min(
            effective_w / float(GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[0]),
            effective_h / float(GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[1]),
        ),
        1.0,
        2.15,
    )

    max_cell_logical = _clamp_int(40 + ((occupancy_scale - 1.0) * 14.0), 40, 56)
    side_panel_pref_logical = _clamp_int(120 + ((occupancy_scale - 1.0) * 56.0), 120, 220)
    top_margin_logical = _clamp_int(80 + ((occupancy_scale - 1.0) * 18.0), 80, 112)
    bottom_margin_logical = _clamp_int(40 + ((occupancy_scale - 1.0) * 12.0), 40, 64)

    available_height_logical = max(200, int(effective_h) - top_margin_logical - bottom_margin_logical)
    available_width_logical = max(200, int(effective_w) - (side_panel_pref_logical * 2) - 40)

    cell_by_height = max(16, available_height_logical // board_rows)
    cell_by_width = max(16, available_width_logical // board_cols)
    logical_cell_size = max(16, min(cell_by_height, cell_by_width, max_cell_logical))

    logical_board_width = board_cols * logical_cell_size
    logical_board_height = board_rows * logical_cell_size
    logical_board_x = max(0, (int(effective_w) - logical_board_width) // 2)
    logical_board_y = top_margin_logical + max(0, (available_height_logical - logical_board_height) // 2)
    logical_side_space = max(60, ((int(effective_w) - logical_board_width) // 2) - 10)
    logical_side_panel_width = min(side_panel_pref_logical, logical_side_space)

    cell_size = max(1, int(round(float(logical_cell_size) * pixel_ratio)))
    board_width_px = board_cols * cell_size
    board_height_px = board_rows * cell_size
    board_x = max(0, int(round(float(logical_board_x) * scale_x)))
    board_y = max(0, int(round(float(logical_board_y) * scale_y)))
    side_panel_width = max(1, int(round(float(logical_side_panel_width) * scale_x)))
    top_margin = max(1, int(round(float(top_margin_logical) * scale_y)))
    bottom_margin = max(1, int(round(float(bottom_margin_logical) * scale_y)))

    return CoopLayoutMetrics(
        cell_size=cell_size,
        board_x=board_x,
        board_y=board_y,
        board_width=board_width_px,
        board_height=board_height_px,
        side_panel_width=side_panel_width,
        top_margin=top_margin,
        bottom_margin=bottom_margin,
        logical_cell_size=logical_cell_size,
        logical_side_panel_width=logical_side_panel_width,
        pixel_ratio=pixel_ratio,
        occupancy_scale=occupancy_scale,
    )


__all__ = [
    'CoopLayoutMetrics',
    'GAMEPLAY_OCCUPANCY_REFERENCE_SIZE',
    'HIDDEN_ROWS',
    'SinglePlayerLayoutMetrics',
    'compute_coop_layout',
    'compute_single_player_layout',
    'get_display_pixel_ratio',
    'total_board_rows',
]