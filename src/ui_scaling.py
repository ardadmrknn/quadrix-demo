from __future__ import annotations

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
    _VIRTUAL_CANVAS_ACTIVE = bool(active)


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
    _UI_SCALE_PRESET = normalize_ui_scale_preset(preset)
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
        return max(float(min_scale), adjusted)

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
    try:
        effective_size = resolve_ui_scale_size(
            screen_or_size,
            use_effective_display_size=True,
            display_surface=display_surface,
        )
    except Exception:
        effective_size = _coerce_size(screen_or_size)

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
    return float(base_scale) * float(pixel_ratio)


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


__all__ = [
    "CONTENT_SCALE_PROFILES",
    "MODAL_SCALE_PROFILES",
    "REFERENCE_SIZE",
    "UI_SCALE_PRESET_MULTIPLIERS",
    "UI_SCALE_PRESET_OFFSETS",
    "UI_SCALE_PRESET_OFFSET_THRESHOLD",
    "UI_SCALE_PRESETS",
    "apply_ui_scale_preset",
    "get_content_scale",
    "get_effective_content_scale",
    "get_effective_modal_scale",
    "get_effective_scale",
    "get_modal_scale",
    "get_projected_effective_scale",
    "get_scale",
    "get_ui_scale_multiplier",
    "get_ui_scale_preset",
    "get_virtual_canvas_ui_scale",
    "is_virtual_canvas_active",
    "normalize_ui_scale_preset",
    "resolve_ui_scale_size",
    "scale_px",
    "set_ui_scale_preset",
    "set_virtual_canvas_active",
]