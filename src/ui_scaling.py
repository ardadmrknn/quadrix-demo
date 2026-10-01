from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from typing import Any


REFERENCE_SIZE = (1920.0, 1080.0)

UI_SCALE_PRESET_MULTIPLIERS = {
    "compact": 0.94,
    "normal": 1.0,
    "large": 1.25,
    "huge": 1.50,
    "massive": 1.75,
    "double": 2.0,
}

UI_SCALE_PRESET_OFFSETS = {
    "compact": -0.10,
    "normal": 0.0,
    "large": 0.25,
    "huge": 0.50,
    "massive": 0.75,
    "double": 1.0,
}

UI_SCALE_PRESET_OFFSET_THRESHOLD = 1.10

UI_SCALE_PRESETS = tuple(UI_SCALE_PRESET_MULTIPLIERS.keys())

_UI_SCALE_PRESET = "normal"

# Projected scale cache'i çözünürlük ve sanal tuval bağlamları arasında
# sınırsız büyümemesi için bounded LRU olarak tutulur.
_PROJECTED_SCALE_CACHE: OrderedDict[tuple, float] = OrderedDict()
_PROJECTED_SCALE_CACHE_MAX = 256

# ---------------------------------------------------------------------------
# Virtual Canvas çift ölçekleme koruması
# ---------------------------------------------------------------------------
# Virtual canvas aktifken (setup_virtual_canvas kurulumu sonrası) bu bayrak
# True olur. Bu durumda _ui_scale() / _sx() metodları 1.0 döndürür —
# canvas zaten küçültüldüğü için ek pers-element ölçekleme çift etkiye yol açar.
_VIRTUAL_CANVAS_ACTIVE: bool = False


def set_virtual_canvas_active(active: bool) -> None:
    """Virtual canvas pipeline aktifliğini kaydet.

    setup_virtual_canvas() tarafından çağrılır; doğrudan kullanmayın.
    """
    global _VIRTUAL_CANVAS_ACTIVE
    normalized = bool(active)
    if normalized != _VIRTUAL_CANVAS_ACTIVE:
        _VIRTUAL_CANVAS_ACTIVE = normalized
        _PROJECTED_SCALE_CACHE.clear()


def is_virtual_canvas_active() -> bool:
    """Virtual canvas pipeline aktif mi?"""
    return _VIRTUAL_CANVAS_ACTIVE


def get_virtual_canvas_ui_scale() -> float:
    """Virtual canvas aktifken kullanılacak per-element ölçek değeri.

    Virtual canvas aktif = canvas zaten uygun boyuta küçültüldü, ek ölçekleme
    yapılmasın → 1.0 dönür.
    Virtual canvas pasif = eski davranış (None) → çağıran kendi hesaplar.

    Returns:
        1.0 (virtual canvas aktif) veya None (pasif, kendi hesapla).
    """
    if _VIRTUAL_CANVAS_ACTIVE:
        return 1.0
    return None


CONTENT_SCALE_PROFILES = {
    "standard": (0.72, 1.18),
    "content": (0.72, 1.18),
    "dense": (0.74, 1.12),
    "dense_content": (0.74, 1.12),
    "roomy": (0.72, 1.22),
    "large": (0.72, 1.22),
}

MODAL_SCALE_PROFILES = {
    "standard": (0.68, 1.20),
    "modal": (0.68, 1.20),
    "roomy": (0.68, 1.24),
    "large": (0.68, 1.24),
}


def normalize_ui_scale_preset(preset: str | None) -> str:
    normalized = str(preset or "").strip().lower()
    if normalized not in UI_SCALE_PRESET_MULTIPLIERS:
        return "normal"
    return normalized


def set_ui_scale_preset(preset: str | None) -> str:
    global _UI_SCALE_PRESET
    previous = _UI_SCALE_PRESET
    _UI_SCALE_PRESET = normalize_ui_scale_preset(preset)
    if _UI_SCALE_PRESET != previous:
        cache = globals().get('_PROJECTED_SCALE_CACHE')
        if hasattr(cache, 'clear'):
            cache.clear()
        try:
            from ui_theme import UIFonts
            UIFonts.clear_cache()
        except Exception:
            pass
        try:
            from text_cache import clear_text_cache
            clear_text_cache()
        except Exception:
            pass
    # Diğer ui_scaling alias'ının da preset değerini senkronize et
    try:
        import sys
        for key in ('ui_scaling', 'src.ui_scaling'):
            mod = sys.modules.get(key)
            if mod and mod is not sys.modules.get(__name__) and hasattr(mod, '_UI_SCALE_PRESET'):
                mod._UI_SCALE_PRESET = _UI_SCALE_PRESET
    except Exception:
        pass
    return _UI_SCALE_PRESET


def get_ui_scale_preset() -> str:
    return _UI_SCALE_PRESET


def get_ui_scale_multiplier(preset: str | None = None) -> float:
    normalized = normalize_ui_scale_preset(_UI_SCALE_PRESET if preset is None else preset)
    return float(UI_SCALE_PRESET_MULTIPLIERS[normalized])


def get_ui_scale_readability_floor(
    *,
    normal_floor: float = 0.72,
    max_floor: float = 1.16,
    preset: str | None = None,
) -> float:
    """Minimum readable scale for dense HUD/panel content."""
    multiplier = get_ui_scale_multiplier(preset)
    if multiplier <= 1.0:
        return float(normal_floor)
    floor = float(normal_floor) + ((float(multiplier) - 1.0) * 0.40)
    return min(float(max_floor), floor)


def apply_ui_scale_preset(
    scale: float,
    *,
    min_scale: float,
    max_scale: float,
    preset: str | None = None,
) -> float:
    if min_scale > max_scale:
        raise ValueError("min_scale max_scale degerinden buyuk olamaz")

    normalized = normalize_ui_scale_preset(_UI_SCALE_PRESET if preset is None else preset)
    multiplier = float(UI_SCALE_PRESET_MULTIPLIERS[normalized])
    if multiplier == 1.0:
        return float(scale)

    if float(scale) <= float(UI_SCALE_PRESET_OFFSET_THRESHOLD):
        adjusted = float(scale) + float(UI_SCALE_PRESET_OFFSETS[normalized])
    else:
        adjusted = float(scale) * multiplier

    if multiplier < 1.0:
        if float(min_scale) <= float(UI_SCALE_PRESET_OFFSET_THRESHOLD):
            adjusted_min = float(min_scale) + float(UI_SCALE_PRESET_OFFSETS[normalized])
        else:
            adjusted_min = float(min_scale) * multiplier
        return max(adjusted_min, adjusted)

    return min(float(max_scale) * multiplier, adjusted)


def _coerce_size(screen_or_size: Any) -> tuple[int, int]:
    if hasattr(screen_or_size, "get_size"):
        width, height = screen_or_size.get_size()
    elif hasattr(screen_or_size, "size"):
        width, height = screen_or_size.size
    elif hasattr(screen_or_size, "width") and hasattr(screen_or_size, "height"):
        width = screen_or_size.width
        height = screen_or_size.height
    elif hasattr(screen_or_size, "get_width") and hasattr(screen_or_size, "get_height"):
        width = screen_or_size.get_width()
        height = screen_or_size.get_height()
    elif isinstance(screen_or_size, Sequence) and not isinstance(screen_or_size, (str, bytes, bytearray)):
        if len(screen_or_size) < 2:
            raise TypeError("screen_or_size en az iki boyut degeri icermelidir")
        width, height = screen_or_size[0], screen_or_size[1]
    else:
        raise TypeError("screen_or_size ekran benzeri nesne veya (width, height) ikilisi olmalidir")

    return max(1, int(width)), max(1, int(height))


def _resolve_profile(profile: str, profiles: dict[str, tuple[float, float]]) -> tuple[float, float]:
    bounds = profiles.get(str(profile or "standard"))
    if bounds is None:
        valid_profiles = ", ".join(sorted(profiles))
        raise ValueError(f"Bilinmeyen scale profile '{profile}'. Gecerli profiller: {valid_profiles}")
    return bounds


def _get_effective_display_size(
    screen_or_size: Any,
    *,
    display_surface: bool | None = None,
) -> tuple[int, int] | None:
    if not hasattr(screen_or_size, "get_size"):
        return None

    try:
        try:
            from .platform_utils import get_effective_ui_size  # type: ignore
        except Exception:
            from platform_utils import get_effective_ui_size  # type: ignore

        width, height = get_effective_ui_size(
            screen_or_size,
            display_surface=display_surface,
        )
        return max(1, int(width)), max(1, int(height))
    except Exception:
        return None


def resolve_ui_scale_size(
    screen_or_size: Any,
    *,
    use_effective_display_size: bool = False,
    display_surface: bool | None = None,
) -> tuple[int, int]:
    if use_effective_display_size:
        if not hasattr(screen_or_size, "get_size"):
            raise TypeError(
                "effective UI size yalnizca get_size() destekleyen ekran benzeri nesnelerle kullanilabilir"
            )
        effective_size = _get_effective_display_size(
            screen_or_size,
            display_surface=display_surface,
        )
        if effective_size is not None:
            return effective_size

    return _coerce_size(screen_or_size)


def get_scale(
    screen_or_size: Any,
    *,
    min_scale: float,
    max_scale: float,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
) -> float:
    width, height = _coerce_size(screen_or_size)
    ref_w, ref_h = reference_size
    if ref_w <= 0 or ref_h <= 0:
        raise ValueError("reference_size pozitif degerler icermelidir")
    if min_scale > max_scale:
        raise ValueError("min_scale max_scale degerinden buyuk olamaz")

    scale = min(width / float(ref_w), height / float(ref_h))
    return max(min_scale, min(max_scale, scale))


def get_effective_scale(
    screen_or_size: Any,
    *,
    min_scale: float,
    max_scale: float,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
    display_surface: bool | None = None,
) -> float:
    base_scale = get_scale(
        resolve_ui_scale_size(
            screen_or_size,
            use_effective_display_size=True,
            display_surface=display_surface,
        ),
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
    )
    return apply_ui_scale_preset(
        base_scale,
        min_scale=min_scale,
        max_scale=max_scale,
    )


def _get_effective_projection_ratio(
    screen_or_size: Any,
    *,
    display_surface: bool | None = None,
) -> float:
    active_w, active_h = _coerce_size(screen_or_size)

    try:
        effective_w, effective_h = resolve_ui_scale_size(
            screen_or_size,
            use_effective_display_size=True,
            display_surface=display_surface,
        )
    except Exception:
        effective_w, effective_h = active_w, active_h

    effective_w = max(1, int(effective_w))
    effective_h = max(1, int(effective_h))

    ratio_x = active_w / float(effective_w)
    ratio_y = active_h / float(effective_h)
    ratio = min(ratio_x, ratio_y)
    if ratio < 0.5 or ratio > 4.0:
        return 1.0
    return float(ratio)


def get_projected_effective_scale(
    screen_or_size: Any,
    *,
    min_scale: float,
    max_scale: float,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
    display_surface: bool | None = None,
    apply_preset: bool = True,
) -> float:
    """Resolve scale from effective UI size, then project it into raw pixels."""
    raw_size = _coerce_size(screen_or_size)
    try:
        effective_size = resolve_ui_scale_size(
            screen_or_size,
            use_effective_display_size=True,
            display_surface=display_surface,
        )
    except Exception:
        effective_size = raw_size

    cache_key = (
        raw_size,
        tuple(int(v) for v in effective_size),
        float(min_scale),
        float(max_scale),
        tuple(float(v) for v in reference_size),
        display_surface,
        bool(apply_preset),
        _UI_SCALE_PRESET,
        _VIRTUAL_CANVAS_ACTIVE,
    )
    cached = _PROJECTED_SCALE_CACHE.get(cache_key)
    if cached is not None:
        _PROJECTED_SCALE_CACHE.move_to_end(cache_key)
        return float(cached)

    base_scale = get_scale(
        effective_size,
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
    )
    if apply_preset:
        base_scale = apply_ui_scale_preset(
            base_scale,
            min_scale=min_scale,
            max_scale=max_scale,
        )
    pixel_ratio = _get_effective_projection_ratio(
        screen_or_size,
        display_surface=display_surface,
    )
    result = float(base_scale) * float(pixel_ratio)
    _PROJECTED_SCALE_CACHE[cache_key] = result
    _PROJECTED_SCALE_CACHE.move_to_end(cache_key)
    while len(_PROJECTED_SCALE_CACHE) > _PROJECTED_SCALE_CACHE_MAX:
        _PROJECTED_SCALE_CACHE.popitem(last=False)
    return result


def get_content_scale(
    screen_or_size: Any,
    profile: str = "standard",
    *,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
) -> float:
    min_scale, max_scale = _resolve_profile(profile, CONTENT_SCALE_PROFILES)
    return get_scale(
        screen_or_size,
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
    )


def get_effective_content_scale(
    screen_or_size: Any,
    profile: str = "standard",
    *,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
    display_surface: bool | None = None,
) -> float:
    min_scale, max_scale = _resolve_profile(profile, CONTENT_SCALE_PROFILES)
    return get_effective_scale(
        screen_or_size,
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
        display_surface=display_surface,
    )


def get_modal_scale(
    screen_or_size: Any,
    profile: str = "standard",
    *,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
) -> float:
    min_scale, max_scale = _resolve_profile(profile, MODAL_SCALE_PROFILES)
    return get_scale(
        screen_or_size,
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
    )


def get_effective_modal_scale(
    screen_or_size: Any,
    profile: str = "standard",
    *,
    reference_size: tuple[float, float] = REFERENCE_SIZE,
    display_surface: bool | None = None,
) -> float:
    min_scale, max_scale = _resolve_profile(profile, MODAL_SCALE_PROFILES)
    return get_effective_scale(
        screen_or_size,
        min_scale=min_scale,
        max_scale=max_scale,
        reference_size=reference_size,
        display_surface=display_surface,
    )


def scale_px(value: int | float, scale: float, minimum: int = 1) -> int:
    return max(int(minimum), int(round(float(value) * float(scale))))


def calculate_overlay_metrics(
    active_size: tuple[int, int],
    ui_scale: float,
    option_count: int,
    *,
    base_panel_width: float = 520.0,
    base_item_height: float = 56.0,
    base_gap: float = 10.0,
    base_top_pad: float = 78.0,
    base_bottom_pad: float = 64.0,
    max_height_ratio: float = 0.85,
) -> dict[str, Any]:
    """Pause/overlay panel geometrisini ekran yüksekliğine sığdırır.

    Dönen ``panel_rect`` ve ``button_rects`` hem çizim hem hit-test için
    kullanılmalıdır. Böylece düşük çözünürlükte çizilen düğme ile tıklanabilir
    alanın birbirinden ayrılması önlenir.
    """
    import pygame

    width, height = max(1, int(active_size[0])), max(1, int(active_size[1]))
    safe_count = max(0, int(option_count or 0))
    safe_scale = max(0.01, float(ui_scale))
    safe_ratio = max(0.50, min(0.95, float(max_height_ratio)))

    preferred_width = scale_px(base_panel_width, safe_scale)
    total_margin = min(scale_px(100, safe_scale), max(0, width - 160))
    max_panel_width = max(1, width - total_margin)
    min_panel_width = min(width, max(160, scale_px(320, min(safe_scale, 1.5))))
    panel_width = min(width, max(min_panel_width, min(preferred_width, max_panel_width)))

    item_h = scale_px(base_item_height, safe_scale)
    gap = scale_px(base_gap, safe_scale)
    top_pad = scale_px(base_top_pad, safe_scale)
    bottom_pad = scale_px(base_bottom_pad, safe_scale)
    gap_count = max(0, safe_count - 1)
    panel_height = top_pad + safe_count * item_h + gap_count * gap + bottom_pad
    max_panel_h = max(1, int(height * safe_ratio))
    compression_ratio = 1.0

    if panel_height > max_panel_h:
        compression_ratio = max_panel_h / float(max(1, panel_height))
        gap = max(2, int(gap * compression_ratio)) if gap_count else 0
        top_pad = max(36, int(top_pad * compression_ratio))
        bottom_pad = max(28, int(bottom_pad * compression_ratio))
        available = max_panel_h - top_pad - bottom_pad - gap_count * gap
        if safe_count:
            compressed_item_h = int(item_h * compression_ratio)
            if available < safe_count * 24:
                compressed_item_h = max(12, available // safe_count)
            item_h = max(12, min(item_h, compressed_item_h))
        else:
            item_h = max(12, int(item_h * compression_ratio))

        panel_height = top_pad + safe_count * item_h + gap_count * gap + bottom_pad
        if panel_height > max_panel_h:
            overflow = panel_height - max_panel_h
            reducible = max(0, top_pad - 24) + max(0, bottom_pad - 20)
            if reducible:
                top_reduce = min(top_pad - 24, (overflow + 1) // 2)
                top_pad -= max(0, top_reduce)
                overflow -= max(0, top_reduce)
                bottom_reduce = min(bottom_pad - 20, overflow)
                bottom_pad -= max(0, bottom_reduce)
                overflow -= max(0, bottom_reduce)
            if overflow > 0 and safe_count:
                item_h = max(10, item_h - ((overflow + safe_count - 1) // safe_count))
            panel_height = top_pad + safe_count * item_h + gap_count * gap + bottom_pad

    panel_height = max(1, min(height, panel_height, max_panel_h))

    # Çok küçük yüzeylerde (ör. Steam Deck benzeri düşük pencere yüksekliği
    # veya otomatik test yüzeyleri) yukarıdaki minimum pad/item değerleri toplam
    # yüksekliği yeniden aşabilir. Nihai yerleşimi burada tekrar çözüyoruz;
    # böylece her düğme rect'i panel içinde kalır ve çizim/hit-test ayrışmaz.
    if safe_count:
        usable_h = max(1, panel_height)
        gap = max(0, min(gap, usable_h // max(1, safe_count)))
        gap_total = gap * gap_count
        if top_pad + bottom_pad + gap_total >= usable_h:
            pad_budget = max(0, usable_h - gap_total - safe_count)
            top_pad = min(top_pad, pad_budget // 2)
            bottom_pad = min(bottom_pad, pad_budget - top_pad)
            remaining = max(0, usable_h - top_pad - bottom_pad - gap_total)
            item_h = max(1, remaining // safe_count)
        else:
            remaining = usable_h - top_pad - bottom_pad - gap_total
            item_h = max(1, min(item_h, remaining // safe_count))
        panel_height = max(1, min(height, max_panel_h, top_pad + bottom_pad + gap_total + safe_count * item_h))
    panel_rect = pygame.Rect(
        max(0, (width - panel_width) // 2),
        max(0, (height - panel_height) // 2),
        max(1, panel_width),
        panel_height,
    )

    min_button_width = min(panel_rect.width, max(96, scale_px(180, min(safe_scale, 1.25))))
    inner_pad_x = scale_px(22, safe_scale)
    if panel_rect.width - inner_pad_x * 2 < min_button_width:
        inner_pad_x = max(6, (panel_rect.width - min_button_width) // 2)
    inner_pad_x = max(0, min(inner_pad_x, max(0, (panel_rect.width - 1) // 2)))

    button_rects: list[Any] = []
    start_y = panel_rect.y + top_pad
    for index in range(safe_count):
        button_y = max(panel_rect.y, start_y + index * (item_h + gap))
        button_y = min(button_y, max(panel_rect.y, panel_rect.bottom - 1))
        remaining_buttons = safe_count - index
        max_height_for_slot = max(
            1,
            panel_rect.bottom - button_y - max(0, remaining_buttons - 1) * (item_h + gap),
        )
        button_height = max(1, min(item_h, max_height_for_slot, panel_rect.bottom - button_y))
        rect = pygame.Rect(
            panel_rect.x + inner_pad_x,
            button_y,
            max(1, panel_rect.width - inner_pad_x * 2),
            button_height,
        )
        button_rects.append(rect)

    title_font_size = scale_px(30, safe_scale, minimum=16)
    if compression_ratio < 1.0:
        title_font_size = max(14, int(title_font_size * compression_ratio))
    title_font_size = max(14, min(title_font_size, max(14, int(top_pad * 0.52)), max(14, int(panel_rect.width * 0.075))))
    return {
        "panel_rect": panel_rect,
        "item_h": item_h,
        "gap": gap,
        "top_pad": top_pad,
        "bottom_pad": bottom_pad,
        "button_rects": button_rects,
        "title_font_size": title_font_size,
        "item_font_size": max(12, min(24, int(item_h * 0.42))),
        "sub_font_size": max(9, min(16, int(item_h * 0.26))),
        "volume_bar_h": max(8, min(scale_px(18, safe_scale), max(8, int(item_h * 0.55)))),
        "volume_bar_max_w": max(24, min(scale_px(120, safe_scale), max(24, int(panel_rect.width * 0.35)))),
        "inner_pad_x": inner_pad_x,
        "title_top": max(4, min(scale_px(18, safe_scale), max(4, top_pad // 3))),
        "max_height_ratio": safe_ratio,
    }


__all__ = [
    "CONTENT_SCALE_PROFILES",
    "MODAL_SCALE_PROFILES",
    "REFERENCE_SIZE",
    "UI_SCALE_PRESET_MULTIPLIERS",
    "UI_SCALE_PRESET_OFFSETS",
    "UI_SCALE_PRESET_OFFSET_THRESHOLD",
    "UI_SCALE_PRESETS",
    "apply_ui_scale_preset",
    "calculate_overlay_metrics",
    "get_content_scale",
    "get_effective_content_scale",
    "get_effective_modal_scale",
    "get_effective_scale",
    "get_modal_scale",
    "get_projected_effective_scale",
    "get_scale",
    "get_ui_scale_multiplier",
    "get_ui_scale_preset",
    "get_ui_scale_readability_floor",
    "get_virtual_canvas_ui_scale",
    "is_virtual_canvas_active",
    "normalize_ui_scale_preset",
    "resolve_ui_scale_size",
    "scale_px",
    "set_ui_scale_preset",
    "set_virtual_canvas_active",
]
