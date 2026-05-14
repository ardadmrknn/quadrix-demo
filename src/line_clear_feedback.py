"""Ortak satır temizleme görsel geri bildirim yardımcıları.

Bu modül `Game` (single-player), `PvPGame`, `CoopGame`, `OnlinePvPGame` ve
`OnlineCoopGame` arasındaki line-clear pipeline'ında ortaklaşan parçacık /
sweep / dalga / kombo geri bildirim sırasını tek noktada toplar. Mod-spesifik
state (kart, enerji, çöp hattı, paylaşılan board) **dokunulmaz**; yalnızca
görsel zincir parity'si için gerekli alt parçaları sağlar.

Sıralama (tüm modlar):
    pending row snapshot → flash → sweep → falling block animation →
    wave effect → particle burst → screen shake → combo / Quadrix burst.

Public API:
    queue_wave_effects(wave_list, ...)     — Game / PvP / OnlinePvP / Coop /
                                              OnlineCoop hepsi kullanır.
    update_wave_effects(wave_list, dt)     — Game / PvP / OnlinePvP / Coop
                                              hepsi kullanır (tek tick eğrisi).
    trigger_combo_burst(game_obj, ...)     — Game / PvP / OnlineCoop kullanır;
                                              renk paleti override edilebilir.
"""

from __future__ import annotations

from typing import Optional, Sequence


# Kombo / Quadrix için ortak ışık paleti (PvP ve Game ile aynı)
_QUADRIX_BURST_COLORS = (
    (255, 215, 0),
    (255, 165, 0),
    (255, 255, 255),
    (0, 255, 255),
)
_MULTI_LINE_BURST_COLORS = (
    (0, 255, 255),
    (100, 200, 255),
    (150, 220, 255),
)


def queue_wave_effects(
    wave_list: list,
    cleared_rows: Sequence[int],
    board_offset_x: int,
    board_offset_y: int,
    cell_size: int,
    board_width_cells: int,
    *,
    color: tuple = (255, 255, 255),
    speed: float = 15.0,
    alpha: int = 200,
) -> None:
    """Her temizlenen satır için yatay dalga efekti ekler."""
    if not cleared_rows or cell_size <= 0 or board_width_cells <= 0:
        return
    board_pixel_width = int(board_width_cells) * int(cell_size)
    half_pixel_width = board_pixel_width // 2
    for row in cleared_rows:
        try:
            row_index = int(row)
        except (TypeError, ValueError):
            continue
        wave_y = int(board_offset_y) + row_index * int(cell_size) + int(cell_size) // 2
        wave_x = int(board_offset_x) + half_pixel_width
        wave_list.append({
            'x': wave_x,
            'y': wave_y,
            'radius': 0,
            'max_radius': board_pixel_width,
            'alpha': int(alpha),
            'color': tuple(color),
            'speed': float(speed),
        })


def update_wave_effects(wave_list: list, dt_frames: float) -> None:
    """Dalga efektlerini bir frame ilerlet; sönen efektleri listeden çıkar."""
    if not wave_list:
        return
    for wave in wave_list[:]:
        try:
            wave['radius'] = float(wave.get('radius', 0)) + float(wave.get('speed', 15.0)) * float(dt_frames)
            max_radius = max(1.0, float(wave.get('max_radius', 1)))
            wave['alpha'] = int(200 * (1 - wave['radius'] / max_radius))
            if wave['radius'] >= max_radius or wave['alpha'] <= 0:
                wave_list.remove(wave)
        except Exception:
            try:
                wave_list.remove(wave)
            except Exception:
                pass


def trigger_combo_burst(
    game_obj,
    cleared_rows: Sequence[int],
    lines_cleared: int,
    board_offset_x: int,
    board_offset_y: int,
    cell_size: int,
    board_width_cells: int,
    board_height_cells: int,
    *,
    multi_line_colors: Optional[Sequence[tuple]] = None,
    quadrix_colors: Optional[Sequence[tuple]] = None,
) -> None:
    """Kombo (2/3 satır) ve Quadrix (4 satır) merkez parçacık patlaması.

    Game / PvP / OnlinePvP ile aynı sayı/hız profili kullanır. Color overrides
    PvP'deki player-spesifik renk farklılığını korumak için sağlanır:
    `multi_line_colors` 2-3 satır kombo için, `quadrix_colors` 4 satır için.
    """
    if lines_cleared <= 1 or not getattr(game_obj, 'effects_enabled', False):
        return
    create_particles = getattr(game_obj, 'create_particles', None)
    if not callable(create_particles):
        return
    if cell_size <= 0 or board_width_cells <= 0 or board_height_cells <= 0:
        return
    center_x = int(board_offset_x) + (int(board_width_cells) * int(cell_size)) // 2
    center_y = int(board_offset_y) + (int(board_height_cells) * int(cell_size)) // 2
    quadrix_palette = list(quadrix_colors) if quadrix_colors else list(_QUADRIX_BURST_COLORS)
    multi_palette = list(multi_line_colors) if multi_line_colors else list(_MULTI_LINE_BURST_COLORS)
    try:
        if lines_cleared >= 4:
            create_particles(
                count=150,
                x=center_x,
                y=center_y,
                colors=quadrix_palette,
                speed=10,
            )
        else:
            create_particles(
                count=50 * int(lines_cleared),
                x=center_x,
                y=center_y,
                colors=multi_palette,
                speed=6,
            )
    except Exception:
        pass


def trigger_line_clear_screen_shake(game_obj, lines_cleared: int) -> None:
    """Standart satır temizleme ekran sallantısı (Game / PvP ile aynı eğri).

    1-3 satır: hafif (3 + lines*2 yoğunluk), 4 satır (Quadrix): güçlü 15.
    Çağıran taraf sweep gibi paralel shake'leri kontrol etmek isterse bunu
    devre dışı bırakabilir.

    NOT: Mevcut Game / PvP / OnlinePvP / Coop bloklarının her biri shake'i
    inline veriyor (bazen Quadrix'i kombo burst ile farklı sırada). Tek bir
    ortak çağrıya geçiş davranış değişikliği yaratacağı için bu yardımcı
    yalnızca yeni call site'lar veya mod-eklemeleri için referans bir helper
    olarak tutuluyor; mevcut çağrılar bilinçli olarak inline kalıyor.
    """
    trigger = getattr(game_obj, 'trigger_screen_shake', None)
    if not callable(trigger):
        return
    try:
        if lines_cleared >= 4:
            trigger(intensity=15, duration=20 / 60.0)
        elif lines_cleared >= 1:
            trigger(intensity=3 + lines_cleared * 2, duration=8 / 60.0)
    except Exception:
        pass
