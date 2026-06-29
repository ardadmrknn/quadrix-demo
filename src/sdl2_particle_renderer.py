"""SDL2 post-pass particle renderer for overlay gameplay particles.

This renderer is intentionally limited to foreground particles that may appear
above the CPU-rendered scene. Background effects such as falling blocks stay on
the CPU scene until the renderer pipeline is split into explicit layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import time

import pygame


@dataclass(frozen=True)
class GpuParticleDrawItem:
    x: int
    y: int
    radius: int
    color: tuple[int, int, int]
    alpha: int


_registered = False
_pending_batch: tuple[GpuParticleDrawItem, ...] = ()
_texture_cache: dict[tuple[int, int], object] = {}
_texture_caps_by_renderer: dict[int, dict] = {}
_last_queue_stats: dict[str, int | bool] = {
    'queued': False,
    'source_particles': 0,
    'gpu_items': 0,
}
_MAX_TEXTURE_CACHE = 48


def is_available() -> bool:
    """Return True when the SDL2 overlay backend is active and usable."""
    try:
        import sdl2_overlay
        return bool(sdl2_overlay.is_active())
    except Exception:
        return False


def reset_availability_cache() -> None:
    return None


def get_last_queue_stats() -> dict[str, int | bool]:
    return dict(_last_queue_stats)


def _record_game_phase(name: str, value: float | int) -> None:
    try:
        import perf_telemetry
        perf_telemetry.record_phase('game', name, value)
    except Exception:
        pass


def _record_game_metric(name: str, value: float | int = 1) -> None:
    try:
        import perf_telemetry
        perf_telemetry.record_metric('game', name, value)
    except Exception:
        pass


def _safe_rgb(color) -> tuple[int, int, int]:
    if not color or not isinstance(color, (tuple, list)) or len(color) < 3:
        return (255, 255, 255)
    try:
        return (
            max(0, min(255, int(color[0]))),
            max(0, min(255, int(color[1]))),
            max(0, min(255, int(color[2]))),
        )
    except Exception:
        return (255, 255, 255)


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, c + int(amount)) for c in color)


def _scale_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def build_overlay_particle_batch(
    particles: Iterable[dict],
    screen_size: tuple[int, int],
    *,
    board_left: int | None = None,
    board_right: int | None = None,
    board_bottom: int | None = None,
) -> tuple[GpuParticleDrawItem, ...]:
    """Convert CPU particle dictionaries into GPU draw items for one frame."""
    scr_w, scr_h = int(screen_size[0]), int(screen_size[1])
    items: list[GpuParticleDrawItem] = []

    for particle in particles:
        try:
            px = float(particle.get('x', 0))
            py = float(particle.get('y', 0))
        except Exception:
            continue
        if not (0 <= px <= scr_w and 0 <= py <= scr_h):
            continue
        if board_left is not None and board_right is not None and board_bottom is not None:
            if px < board_left or px > board_right or py > board_bottom:
                continue

        try:
            max_life = max(1.0, float(particle.get('max_life', 1)))
            alpha_ratio = max(0.0, min(1.0, float(particle.get('life', 0)) / max_life))
            alpha = max(0, min(255, int(255 * alpha_ratio)))
            size = max(1, int(float(particle.get('size', 1)) * alpha_ratio))
        except Exception:
            continue
        if alpha <= 0 or size <= 0:
            continue

        x, y = int(px), int(py)
        color = _safe_rgb(particle.get('color'))
        if particle.get('glow', False) and size > 2:
            halo_size = size + 4
            items.append(GpuParticleDrawItem(x, y, halo_size, _scale_color(color, 0.6), int(alpha * 0.3)))
            mid_size = size + 2
            items.append(GpuParticleDrawItem(x, y, mid_size, _scale_color(color, 0.8), int(alpha * 0.5)))

        items.append(GpuParticleDrawItem(x, y, size, color, alpha))
        if size > 2:
            items.append(GpuParticleDrawItem(x, y, max(1, size - 1), _brighten(color, 80), alpha))
            if size > 3:
                items.append(GpuParticleDrawItem(x, y, 1, _brighten(color, 120), alpha))

    return tuple(items)


def queue_overlay_particles(
    particles: Iterable[dict],
    screen_size: tuple[int, int],
    *,
    board_left: int | None = None,
    board_right: int | None = None,
    board_bottom: int | None = None,
) -> bool:
    """Queue one frame of overlay particles for the SDL2 post-pass.

    Returns True when the batch was queued and CPU drawing should be skipped.
    """
    global _pending_batch, _last_queue_stats
    try:
        source_count = len(particles)  # type: ignore[arg-type]
    except Exception:
        source_count = 0
    if not is_available():
        _pending_batch = ()
        _last_queue_stats = {
            'queued': False,
            'source_particles': int(source_count),
            'gpu_items': 0,
        }
        return False
    _ensure_registered()
    if not _registered:
        _pending_batch = ()
        _last_queue_stats = {
            'queued': False,
            'source_particles': int(source_count),
            'gpu_items': 0,
        }
        return False
    batch = build_overlay_particle_batch(
        particles,
        screen_size,
        board_left=board_left,
        board_right=board_right,
        board_bottom=board_bottom,
    )
    if not batch:
        _pending_batch = ()
        _last_queue_stats = {
            'queued': True,
            'source_particles': int(source_count),
            'gpu_items': 0,
        }
        return True
    _pending_batch = batch
    _last_queue_stats = {
        'queued': True,
        'source_particles': int(source_count),
        'gpu_items': len(batch),
    }
    return True


def _ensure_registered() -> None:
    global _registered
    if _registered:
        return
    try:
        import sdl2_overlay
        _registered = bool(sdl2_overlay.register_gpu_overlay_drawer(_draw_pending_batch))
    except Exception:
        _registered = False


def _make_circle_surface(radius: int) -> pygame.Surface:
    diameter = max(2, int(radius) * 2)
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(surface, (255, 255, 255, 255), (radius, radius), radius)
    return surface


def _get_circle_texture(renderer, radius: int):
    radius = max(1, min(128, int(radius)))
    renderer_key = id(renderer)
    key = (renderer_key, radius)
    cached = _texture_cache.get(key)
    if cached is not None:
        return cached

    from pygame._sdl2.video import Texture

    texture = Texture.from_surface(renderer, _make_circle_surface(radius))
    try:
        texture.blend_mode = 1  # SDL_BLENDMODE_BLEND
    except Exception:
        pass

    if len(_texture_cache) > _MAX_TEXTURE_CACHE:
        _texture_cache.clear()
    _texture_cache[key] = texture
    return texture


def _renderer_caps(renderer, texture) -> dict:
    renderer_key = id(renderer)
    caps = _texture_caps_by_renderer.get(renderer_key)
    if caps is not None:
        return caps
    try:
        import sdl2_overlay
        probe = sdl2_overlay.probe_sdl2_texture_properties(texture)
        caps = {
            'color': probe.get('color_mod', {}).get('selected'),
            'alpha': probe.get('alpha_mod', {}).get('selected'),
            'blend_mode': probe.get('blend_mode', {}).get('selected'),
        }
    except Exception:
        caps = {'color': 'color', 'alpha': 'alpha', 'blend_mode': 'blend_mode'}
    _texture_caps_by_renderer[renderer_key] = caps
    return caps


def _draw_item(renderer, item: GpuParticleDrawItem) -> None:
    texture = _get_circle_texture(renderer, item.radius)
    caps = _renderer_caps(renderer, texture)
    color_prop = caps.get('color')
    alpha_prop = caps.get('alpha')
    if color_prop:
        setattr(texture, color_prop, item.color)
    if alpha_prop:
        setattr(texture, alpha_prop, max(0, min(255, int(item.alpha))))
    x = item.x
    y = item.y
    radius = item.radius
    try:
        import sdl2_overlay
        info = sdl2_overlay.get_presentation_info()
        if info.get('active'):
            sx = float(info.get('scale_x', 1.0) or 1.0)
            sy = float(info.get('scale_y', sx) or sx)
            x = int(round(float(info.get('offset_x', 0)) + (item.x * sx)))
            y = int(round(float(info.get('offset_y', 0)) + (item.y * sy)))
            radius = max(1, int(round(item.radius * min(sx, sy))))
    except Exception:
        pass
    dst = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
    renderer.blit(texture, dst)


def _draw_pending_batch(renderer) -> None:
    global _pending_batch
    batch = _pending_batch
    _pending_batch = ()
    if not batch:
        return
    started = time.perf_counter()
    errors = 0
    for item in batch:
        try:
            _draw_item(renderer, item)
        except Exception:
            errors += 1
            continue
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _record_game_phase('game_gpu_particle_postpass_ms', elapsed_ms)
    _record_game_phase('game_gpu_particle_items_drawn', len(batch) - errors)
    if errors:
        _record_game_metric('game_gpu_particle_draw_errors', errors)
