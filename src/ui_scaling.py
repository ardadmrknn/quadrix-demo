from __future__ import annotations

from collections.abc import Sequence
from typing import Any


REFERENCE_SIZE = (1920.0, 1080.0)

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


def scale_px(value: int | float, scale: float, minimum: int = 1) -> int:
    return max(int(minimum), int(round(float(value) * float(scale))))


__all__ = [
    "CONTENT_SCALE_PROFILES",
    "MODAL_SCALE_PROFILES",
    "REFERENCE_SIZE",
    "get_content_scale",
    "get_modal_scale",
    "get_scale",
    "scale_px",
]