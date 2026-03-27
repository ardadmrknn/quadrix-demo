"""Rainbow cat sweep efekti — satır temizleme sırasında soldan sağa ışık süpürmesi.

Hem Game hem PvPGame tarafından kullanılır.
"""

from __future__ import annotations

import os
import pygame

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _np = None
    _NUMPY_AVAILABLE = False


def _resource_path(relative_path: str) -> str:
    import sys
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return os.path.join(base_path, relative_path)


class SweepCatState:
    """Cat sprite varlık yükleme ve önbellekleme durumu."""

    def __init__(self) -> None:
        self.asset_checked: bool = False
        self.base_surface: pygame.Surface | None = None
        self.surface_cache: dict = {}
        self.frame_base_surfaces: list[pygame.Surface] = []
        self.frame_surface_cache: dict = {}
        self.paw_profile: dict | None = None

    # ------------------------------------------------------------------
    # Sprite yardımcıları
    # ------------------------------------------------------------------

    @staticmethod
    def _trim_transparent(src: pygame.Surface) -> pygame.Surface:
        try:
            trim_rect = src.get_bounding_rect(min_alpha=8)
        except Exception:
            return src
        if trim_rect.width <= 0 or trim_rect.height <= 0:
            return src
        if trim_rect.width == src.get_width() and trim_rect.height == src.get_height():
            return src
        return src.subsurface(trim_rect).copy()

    @staticmethod
    def _sanitize_alpha(src: pygame.Surface, alpha_cutoff: int = 140) -> pygame.Surface:
        try:
            surface = src.copy()
            cutoff = max(1, min(254, int(alpha_cutoff)))
            if _NUMPY_AVAILABLE:
                try:
                    alpha_view = pygame.surfarray.pixels_alpha(surface)
                    alpha_view[:] = _np.where(alpha_view < cutoff, 0, 255)
                    del alpha_view
                    return surface
                except Exception:
                    pass
            width, height = surface.get_size()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = surface.get_at((x, y))
                    if a < cutoff:
                        surface.set_at((x, y), (r, g, b, 0))
                    else:
                        surface.set_at((x, y), (r, g, b, 255))
            return surface
        except Exception:
            return src

    @staticmethod
    def _detect_paw_profile(src: pygame.Surface) -> dict | None:
        try:
            width, height = src.get_size()
        except Exception:
            return None
        if width <= 4 or height <= 4:
            return None

        scan_start = max(0, int(height * 0.65))
        min_alpha = 40
        dark_limit = 95
        columns: list[tuple] = []

        if _NUMPY_AVAILABLE:
            try:
                rgb_arr = pygame.surfarray.array3d(src)
                alpha_arr = pygame.surfarray.array_alpha(src)
                rgb_scan = rgb_arr[:, scan_start:, :]
                alpha_scan = alpha_arr[:, scan_start:]
                visible = alpha_scan >= min_alpha
                dark = _np.all(rgb_scan <= dark_limit, axis=2)
                dark_visible = visible & dark
                dark_counts = dark_visible.sum(axis=1)
                valid_x = _np.where(dark_counts > 0)[0]
                for x in valid_x:
                    col = dark_visible[x]
                    dark_ys = _np.where(col)[0]
                    columns.append((int(x), int(dark_counts[x]), int(dark_ys[0]) + scan_start, int(dark_ys[-1]) + scan_start))
            except Exception:
                columns = []

        if not columns:
            for x in range(width):
                dark_count = 0
                min_dark_y = None
                max_dark_y = -1
                for y in range(scan_start, height):
                    r, g, b, a = src.get_at((x, y))
                    if a < min_alpha:
                        continue
                    if r <= dark_limit and g <= dark_limit and b <= dark_limit:
                        dark_count += 1
                        if min_dark_y is None:
                            min_dark_y = y
                        if y > max_dark_y:
                            max_dark_y = y
                if dark_count > 0 and min_dark_y is not None:
                    columns.append((x, dark_count, min_dark_y, max_dark_y))

        if not columns:
            return None

        clusters: list[list] = []
        current = [columns[0]]
        for item in columns[1:]:
            if item[0] - current[-1][0] <= 1:
                current.append(item)
            else:
                clusters.append(current)
                current = [item]
        if current:
            clusters.append(current)

        cluster_info = []
        for cluster in clusters:
            c_start = cluster[0][0]
            c_end = cluster[-1][0]
            c_width = c_end - c_start + 1
            if c_width > max(3, width // 5):
                continue
            total_dark = sum(v[1] for v in cluster)
            max_dark_y = max(v[3] for v in cluster)
            min_dark_y = min(v[2] for v in cluster)
            weighted_center = int(round(sum(v[0] * v[1] for v in cluster) / float(max(1, total_dark))))
            bottom_bonus = max(0, max_dark_y - scan_start)
            score = (total_dark * 2) + (bottom_bonus * 3) - c_width
            if max_dark_y < height - 3:
                score -= 8
            cluster_info.append({'center_x': weighted_center, 'score': score, 'min_y': min_dark_y, 'max_y': max_dark_y})

        if len(cluster_info) < 2:
            return None

        cluster_info.sort(key=lambda c: c['score'], reverse=True)
        selected = cluster_info[:4]
        selected.sort(key=lambda c: c['center_x'])

        leg_top_y = min(c['min_y'] for c in selected)
        baseline_y = max(c['max_y'] for c in selected)
        denom_w = float(max(1, width - 1))
        denom_h = float(max(1, height - 1))
        x_norms = [max(0.0, min(1.0, c['center_x'] / denom_w)) for c in selected]
        return {
            'x_norms': x_norms,
            'leg_top_norm': max(0.0, min(1.0, leg_top_y / denom_h)),
            'baseline_norm': max(0.0, min(1.0, baseline_y / denom_h)),
        }

    # ------------------------------------------------------------------
    # Sprite yükleme / cache
    # ------------------------------------------------------------------

    def get_cat_surface(self, target_w: int, target_h: int, phase: int = 0) -> pygame.Surface | None:
        target_w = max(1, int(target_w))
        target_h = max(1, int(target_h))
        phase_index = int(phase) % 8

        if not self.asset_checked:
            self.asset_checked = True
            self.surface_cache = {}
            self.frame_surface_cache = {}
            self.frame_base_surfaces = []
            self.paw_profile = None
            try:
                custom_path = _resource_path(os.path.join('assets', 'ui', 'line_sweep_cat.png'))
                if os.path.exists(custom_path):
                    self.base_surface = pygame.image.load(custom_path).convert_alpha()
                    self.base_surface = self._trim_transparent(self.base_surface)
                    self.base_surface = self._sanitize_alpha(self.base_surface)
                    self.paw_profile = self._detect_paw_profile(self.base_surface)
            except Exception:
                self.base_surface = None
                self.paw_profile = None

            try:
                frame_dir = _resource_path(os.path.join('assets', 'ui', 'line_sweep_cat_frames'))
                if os.path.isdir(frame_dir):
                    frame_files = sorted(
                        name for name in os.listdir(frame_dir) if name.lower().endswith('.png')
                    )
                    for frame_name in frame_files:
                        try:
                            frame_surface = pygame.image.load(os.path.join(frame_dir, frame_name)).convert_alpha()
                        except Exception:
                            continue
                        if frame_surface.get_width() > 0 and frame_surface.get_height() > 0:
                            frame_surface = self._trim_transparent(frame_surface)
                            frame_surface = self._sanitize_alpha(frame_surface)
                            self.frame_base_surfaces.append(frame_surface)
                            if self.paw_profile is None:
                                self.paw_profile = self._detect_paw_profile(frame_surface)
            except Exception:
                self.frame_base_surfaces = []

        frame_bases = self.frame_base_surfaces
        if frame_bases:
            frame_index = int(phase) % len(frame_bases)
            frame_key = (target_h, frame_index)
            cached = self.frame_surface_cache.get(frame_key)
            if cached is not None:
                return cached
            frame_base = frame_bases[frame_index]
            bw, bh = frame_base.get_size()
            if bw <= 0 or bh <= 0:
                return None
            scale = target_h / float(bh)
            sw = max(1, int(round(bw * scale)))
            sh = max(1, int(round(target_h)))
            frame_surface = pygame.transform.scale(frame_base, (sw, sh))
            self.frame_surface_cache[frame_key] = frame_surface
            return frame_surface

        base = self.base_surface
        if base is None:
            return None

        key = (target_h, phase_index)
        cached = self.surface_cache.get(key)
        if cached is not None:
            return cached

        bw, bh = base.get_size()
        if bw <= 0 or bh <= 0:
            return None

        scale = target_h / float(bh)
        sw = max(1, int(round(bw * scale)))
        sh = max(1, int(round(target_h)))
        scaled = pygame.transform.scale(base, (sw, sh))

        surface = scaled.copy()
        paw_profile = self.paw_profile
        if paw_profile and paw_profile.get('x_norms'):
            leg_top = int(paw_profile.get('leg_top_norm', 0.72) * sh)
            leg_top = max(0, min(sh - 1, leg_top))
            leg_h = max(1, sh - leg_top)
            step_pattern = (0, 1, 2, 1, 0, -1, -2, -1)
            for idx, x_norm in enumerate(paw_profile['x_norms'][:4]):
                center_x = int(max(0.0, min(1.0, x_norm)) * (sw - 1))
                patch_w = max(2, sw // 11)
                patch_x = max(0, min(sw - patch_w, center_x - patch_w // 2))
                src_rect = pygame.Rect(patch_x, leg_top, patch_w, leg_h)
                step = step_pattern[(phase_index + idx) % 8]
                surface.blit(scaled, (patch_x, leg_top + step), src_rect)
        else:
            body_cut = max(1, int(sh * 0.70))
            leg_h = max(1, sh - body_cut)
            left_w = max(1, sw // 2)
            right_w = max(1, sw - left_w)
            step_pattern = (0, 1, 2, 1, 0, -1, -2, -1)
            step = step_pattern[phase_index]
            left_src = pygame.Rect(0, body_cut, left_w, leg_h)
            right_src = pygame.Rect(left_w, body_cut, right_w, leg_h)
            surface.blit(scaled, (0, body_cut + step), left_src)
            surface.blit(scaled, (left_w, body_cut - step), right_src)

        self.surface_cache[key] = surface
        return surface


# ------------------------------------------------------------------
# Ana çizim fonksiyonu
# ------------------------------------------------------------------

_RAINBOW = [
    (255, 0, 0),
    (255, 128, 0),
    (255, 230, 0),
    (0, 220, 0),
    (0, 150, 255),
    (130, 80, 255),
]


def draw_rainbow_cat_sweep(
    screen: pygame.Surface,
    state: SweepCatState,
    board_rect: pygame.Rect,
    sweep_x: int,
    sweep_width: int,
    phase: int,
    board_width_cells: int,
) -> None:
    """Rainbow + opsiyonel kedi sprite sweep efektini çiz."""
    sweep_height = max(1, int(board_rect.height))
    sweep_y = board_rect.y

    custom_target_w = max(sweep_width, int(sweep_height * 1.65))
    custom_cat = state.get_cat_surface(custom_target_w, sweep_height, phase)
    one_col_w = max(1, int(round(board_rect.width / float(max(1, board_width_cells)))))

    if custom_cat is not None:
        cat_w = custom_cat.get_width()
        cat_h = custom_cat.get_height()
        cat_x = sweep_x
        cat_y = sweep_y + max(0, (sweep_height - cat_h) // 2)
        tail_attach_x = cat_x + max(1, int(cat_w * 0.14))
        trail_x = board_rect.x
        trail_right = max(trail_x + one_col_w, tail_attach_x)
        tail_width = max(1, trail_right - trail_x)
    else:
        trail_x = sweep_x
        tail_width = sweep_width

    stripe_h = max(1, sweep_height // 6)
    for i in range(6):
        color = _RAINBOW[(i + phase) % 6]
        stripe_y = sweep_y + i * stripe_h
        stripe_h_i = max(1, (sweep_y + sweep_height) - stripe_y) if i == 5 else stripe_h

        stripe_rect = pygame.Rect(trail_x, stripe_y, tail_width, stripe_h_i)
        clip = stripe_rect.clip(board_rect)
        if clip.width <= 0 or clip.height <= 0:
            continue

        pygame.draw.rect(screen, color, clip)
        if (i + phase) % 2 == 0 and clip.width > 4:
            pygame.draw.line(screen, (255, 255, 255), (clip.x + 1, clip.y), (clip.x + clip.width - 2, clip.y), 1)

    if custom_cat is not None:
        custom_rect = custom_cat.get_rect()
        custom_rect.x = cat_x
        custom_rect.y = cat_y
        clip = custom_rect.clip(board_rect)
        if clip.width > 0 and clip.height > 0:
            src = pygame.Rect(clip.x - custom_rect.x, clip.y - custom_rect.y, clip.width, clip.height)
            screen.blit(custom_cat, clip.topleft, src)
