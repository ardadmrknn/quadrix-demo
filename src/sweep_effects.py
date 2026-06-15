"""Rainbow cat sweep efekti — satır temizleme sırasında soldan sağa ışık süpürmesi.

Hem Game hem PvPGame tarafından kullanılır.
"""

from __future__ import annotations

import math
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
        self.pet_surface_cache: dict = {}

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
        """Detect 2–4 leg/paw x-positions from the sprite's bottom-edge silhouette.

        The previous implementation looked for *dark* (RGB<=95) vertical
        columns, which the real Luna-Cat sprite doesn't have — its paws aren't
        notably darker than the body, so detection always failed and the
        articulated walk cycle never engaged.

        The reliable signal is the **bottom-edge silhouette**: a walking cat's
        paws are the lowest-reaching parts of the figure, separated by valleys
        where the silhouette pulls up between the legs. We:

        1. Compute, for each x column in the lower band, the lowest visible
           (alpha>=cutoff) pixel y → the bottom-edge profile.
        2. Pick a "contact" threshold partway between the typical underside
           level (20th percentile of bottom-edge) and the deepest point
           (baseline). Columns at/below it are paw contacts.
        3. Group contiguous contact columns (tolerating 2px gaps) into clusters,
           filter by plausible leg width, and take their depth-weighted centres.

        Returns ``None`` (so the safe fallback stays in charge) when fewer than
        2 genuine, alpha-separated leg clusters exist — we never fabricate paw
        positions on a sprite that doesn't actually show separated legs.
        """
        try:
            width, height = src.get_size()
        except Exception:
            return None
        if width <= 8 or height <= 8:
            return None

        # Only look at the lower half — legs/paws live here. Starting at 50%
        # keeps the hip line and the full leg travel inside the scan window.
        band_top = max(0, int(height * 0.50))
        cutoff = 40

        bottom: list[int] = [-1] * width

        if _NUMPY_AVAILABLE:
            try:
                alpha = pygame.surfarray.array_alpha(src)  # (w, h)
                band = alpha[:, band_top:]
                visible = band >= cutoff
                # Lowest visible row per column: reverse-search the band.
                has = visible.any(axis=1)
                # argmax on reversed gives distance from the bottom of the band.
                rev = visible[:, ::-1]
                from_bottom = rev.argmax(axis=1)
                band_h = band.shape[1]
                for x in range(width):
                    if has[x]:
                        bottom[x] = band_top + (band_h - 1 - int(from_bottom[x]))
            except Exception:
                bottom = [-1] * width

        if all(v < 0 for v in bottom):
            # Pure-pygame fallback: scan each column bottom-up.
            try:
                for x in range(width):
                    for y in range(height - 1, band_top - 1, -1):
                        if src.get_at((x, y))[3] >= cutoff:
                            bottom[x] = y
                            break
            except Exception:
                return None

        valid_vals = [v for v in bottom if v >= 0]
        if len(valid_vals) < 8:
            return None

        baseline_y = max(valid_vals)
        # 20th-percentile bottom-edge ~ the underside/gap level between legs.
        sorted_vals = sorted(valid_vals)
        shallow_y = sorted_vals[max(0, int(len(sorted_vals) * 0.20) - 1)]
        leg_span = max(1, baseline_y - shallow_y)
        if leg_span < max(3, int(height * 0.04)):
            # No meaningful depth variation → no separated legs to detect.
            return None
        contact_thr = baseline_y - int(leg_span * 0.45)

        # Group contiguous contact columns (tolerate small 2px gaps).
        clusters: list[list[int]] = []
        current: list[int] = []
        last_x: int | None = None
        for x in range(width):
            if bottom[x] >= contact_thr:
                if last_x is None or x - last_x <= 2:
                    current.append(x)
                else:
                    clusters.append(current)
                    current = [x]
                last_x = x
        if current:
            clusters.append(current)

        min_leg_w = max(3, width // 60)
        max_leg_w = max(min_leg_w + 1, width // 3)
        legs: list[dict] = []
        for cluster in clusters:
            c_start, c_end = cluster[0], cluster[-1]
            c_width = c_end - c_start + 1
            if c_width < min_leg_w or c_width > max_leg_w:
                continue
            # Depth-weighted centre so the paw tip (deepest part) anchors x.
            weight_sum = 0.0
            weighted_x = 0.0
            top_y = baseline_y
            for x in cluster:
                depth = max(0, bottom[x] - shallow_y)
                weight_sum += depth
                weighted_x += x * depth
                if bottom[x] < top_y:
                    top_y = bottom[x]
            if weight_sum <= 0:
                center_x = (c_start + c_end) / 2.0
            else:
                center_x = weighted_x / weight_sum
            legs.append({'center_x': center_x, 'max_y': max(bottom[x] for x in cluster)})

        if len(legs) < 2:
            # Genuine leg separation not found — keep the safe fallback.
            return None

        # Keep at most 4 strongest (deepest-reaching) legs, ordered L→R.
        legs.sort(key=lambda lg: lg['max_y'], reverse=True)
        legs = legs[:4]
        legs.sort(key=lambda lg: lg['center_x'])

        denom_w = float(max(1, width - 1))
        denom_h = float(max(1, height - 1))
        x_norms = [max(0.0, min(1.0, lg['center_x'] / denom_w)) for lg in legs]
        # Hip/leg-top line sits at the underside level where legs detach from
        # the body; baseline is the deepest paw contact.
        return {
            'x_norms': x_norms,
            'leg_top_norm': max(0.0, min(1.0, shallow_y / denom_h)),
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

        # Articulated procedural walk cycle. Decomposes the static sprite into
        # body + per-leg sub-surfaces and re-poses the legs through an 8-phase
        # gait (lift → forward swing → plant) with a synced body bob. Falls
        # back to a safe static/strip pose on any failure so this stays robust
        # on the gameplay hot path. Result is cached per (target_h, phase).
        paw_profile = self.paw_profile
        try:
            if paw_profile and len(paw_profile.get('x_norms') or []) >= 2:
                surface = self._compose_walk_frame(scaled, sw, sh, paw_profile, phase_index)
            else:
                surface = self._compose_fallback_walk(scaled, sw, sh, phase_index)
        except Exception:
            # Never raise from the sweep hot path — worst case is a static cat.
            surface = scaled.copy()

        self.surface_cache[key] = surface
        return surface

    def get_companion_surface(
        self,
        target_w: int,
        target_h: int,
        phase: int = 0,
        pet: str | None = None,
    ) -> pygame.Surface | None:
        """Surface for the sweep companion at ``phase``.

        When ``pet`` resolves to a registered, frame-backed pet (e.g. the
        sheep) its pre-registered frames are cycled and scaled by height. The
        frames share one canvas, so we scale them uniformly and never trim —
        that keeps the authored bounce/squash steady instead of jittering.

        For the default Luna-Cat (or any unknown/missing pet) this delegates to
        :meth:`get_cat_surface`, preserving the original sprite + procedural
        walk-cycle behaviour and full backward compatibility.
        """
        pet_surface = self._get_pet_surface(target_h, phase, pet)
        if pet_surface is not None:
            return pet_surface
        return self.get_cat_surface(target_w, target_h, phase)

    def _get_pet_surface(self, target_h: int, phase: int, pet: str | None):
        if pet is None:
            return None
        try:
            if _is_default_pet(pet):
                return None
            frames = _load_pet_frames(pet)
        except Exception:
            return None
        if not frames:
            return None

        target_h = max(1, int(target_h))
        frame_index = int(phase) % len(frames)
        normalized = _normalize_pet(pet)
        cache_key = (normalized, target_h, frame_index)
        cached = self.pet_surface_cache.get(cache_key)
        if cached is not None:
            return cached

        base = frames[frame_index]
        bw, bh = base.get_size()
        if bw <= 0 or bh <= 0:
            return None
        scale = target_h / float(bh)
        sw = max(1, int(round(bw * scale)))
        sh = max(1, int(round(target_h)))
        try:
            scaled = pygame.transform.smoothscale(base, (sw, sh))
        except Exception:
            scaled = pygame.transform.scale(base, (sw, sh))
        self.pet_surface_cache[cache_key] = scaled
        return scaled

    # ------------------------------------------------------------------
    # Procedural walk-cycle composition
    # ------------------------------------------------------------------

    @staticmethod
    def _walk_leg_pose(leg_phase: int) -> tuple[float, float, float]:
        """Return (lift_ratio, forward_ratio, angle_deg) for an 8-step gait.

        The cycle splits into a swing half (paw lifts, swings forward) and a
        stance half (paw planted, drifts backward as the body advances). Values
        are normalised; callers scale them to pixels by sprite height.
        """
        import math

        t = (int(leg_phase) % 8) / 8.0
        if t < 0.5:
            # Swing: lift follows a sine arch; forward goes from back→front.
            swing_t = t / 0.5
            lift = math.sin(math.pi * swing_t)
            forward = (swing_t * 2.0) - 1.0  # -1 (back) → +1 (front)
            angle = math.sin(math.pi * swing_t) * 1.0  # subtle knee swing
        else:
            # Stance: planted, drifting backward as the body moves forward.
            stance_t = (t - 0.5) / 0.5
            lift = 0.0
            forward = 1.0 - (stance_t * 2.0)  # +1 (front) → -1 (back)
            angle = -0.3 * stance_t
        return lift, forward, angle

    def _compose_walk_frame(
        self,
        scaled: pygame.Surface,
        sw: int,
        sh: int,
        profile: dict,
        phase_index: int,
    ) -> pygame.Surface:
        """Compose one articulated walk frame from the scaled static sprite."""
        import math

        x_norms = list(profile.get('x_norms') or [])
        hip_y = int(max(0.0, min(1.0, profile.get('leg_top_norm', 0.70))) * sh)
        hip_y = max(1, min(sh - 2, hip_y))
        leg_h = max(2, sh - hip_y)

        # Motion amplitudes scale with sprite height so the gait reads the same
        # at store-card and in-game sizes.
        lift_px = max(1.0, sh * 0.07)
        swing_px = max(1.0, sw * 0.018)
        bob_px = max(1.0, sh * 0.018)
        sway_px = max(0.0, sw * 0.004)
        max_angle = 7.0

        # Body vertical bob: dips twice per stride (once per diagonal contact).
        bob = int(round(math.sin(2.0 * math.pi * (phase_index / 8.0) * 2.0) * bob_px))
        # Gentle horizontal sway in counter-phase, for a touch of life.
        sway = int(round(math.cos(2.0 * math.pi * (phase_index / 8.0)) * sway_px))

        out = pygame.Surface((sw, sh), pygame.SRCALPHA)

        # Build a body layer with the lower paw footprints cleared so re-posed
        # legs don't smear over their old position. We clear only the lower
        # ~65% of each leg strip; the upper attachment (and the belly) stay
        # intact so the legs remain visually connected to the body.
        body_layer = scaled.copy()
        patch_w = max(3, sw // 9)
        clear_top = hip_y + int(leg_h * 0.32)
        clear_h = max(1, sh - clear_top)

        legs: list[tuple[int, pygame.Surface, float, float]] = []
        for idx, x_norm in enumerate(x_norms[:4]):
            center_x = int(max(0.0, min(1.0, x_norm)) * (sw - 1))
            patch_x = max(0, min(sw - patch_w, center_x - patch_w // 2))

            # Clear the lower footprint of this leg from the body layer.
            body_layer.fill((0, 0, 0, 0), pygame.Rect(patch_x, clear_top, patch_w, clear_h))

            # Extract the full leg strip (from the hip down) to re-pose.
            leg_rect = pygame.Rect(patch_x, hip_y, patch_w, leg_h)
            leg_rect = leg_rect.clip(scaled.get_rect())
            if leg_rect.width <= 0 or leg_rect.height <= 0:
                continue
            leg_img = scaled.subsurface(leg_rect).copy()

            # Diagonal gait: alternate legs are a half-cycle out of phase.
            leg_phase = (phase_index + (4 if idx % 2 else 0)) % 8
            lift_r, forward_r, angle_r = self._walk_leg_pose(leg_phase)

            posed = leg_img
            angle = angle_r * max_angle
            if abs(angle) > 0.5:
                try:
                    posed = pygame.transform.rotozoom(leg_img, angle, 1.0)
                except Exception:
                    posed = leg_img

            legs.append((patch_x, posed, lift_r * lift_px, forward_r * swing_px))

        # Draw the body (bob + sway) first, then the posed legs on top.
        out.blit(body_layer, (sway, bob))
        for patch_x, posed, lift, forward in legs:
            # Re-centre rotated leg horizontally on its original strip, anchor
            # its top at the hip, then apply swing (x) and lift (-y) + body bob.
            extra_w = posed.get_width() - patch_w
            draw_x = int(round(patch_x - extra_w / 2.0 + forward + sway))
            draw_y = int(round(hip_y - lift + bob))
            out.blit(posed, (draw_x, draw_y))

        return out

    def _compose_fallback_walk(
        self,
        scaled: pygame.Surface,
        sw: int,
        sh: int,
        phase_index: int,
    ) -> pygame.Surface:
        """Leg-detection-free fallback: body bob + two-leg alternating step.

        Used when paw detection fails. Cleaner than the old single-strip shift
        because it clears the lower footprint before re-blitting, avoiding the
        vertical-smear artefact, while still selling a basic stride.
        """
        import math

        out = pygame.Surface((sw, sh), pygame.SRCALPHA)
        body_cut = max(1, int(sh * 0.66))
        leg_h = max(1, sh - body_cut)
        bob_px = max(1.0, sh * 0.016)
        step_px = max(1.0, sh * 0.05)
        bob = int(round(math.sin(2.0 * math.pi * (phase_index / 8.0) * 2.0) * bob_px))

        body_layer = scaled.copy()
        clear_top = body_cut + int(leg_h * 0.30)
        body_layer.fill((0, 0, 0, 0), pygame.Rect(0, clear_top, sw, max(1, sh - clear_top)))

        left_w = max(1, sw // 2)
        right_w = max(1, sw - left_w)
        left_src = pygame.Rect(0, body_cut, left_w, leg_h)
        right_src = pygame.Rect(left_w, body_cut, right_w, leg_h)
        # Two legs in anti-phase using a sine lift so they arc rather than jitter.
        left_lift = int(round(math.sin(math.pi * (phase_index / 4.0)) * step_px))
        right_lift = int(round(math.sin(math.pi * ((phase_index / 4.0) + 1.0)) * step_px))

        out.blit(body_layer, (0, bob))
        out.blit(scaled, (0, body_cut - max(0, left_lift) + bob), left_src)
        out.blit(scaled, (left_w, body_cut - max(0, right_lift) + bob), right_src)
        return out


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

_CAT_HEAD_ANCHOR_X = 0.86
_SWEEP_LEVEL_DURATION_DECAY = 0.965
_SWEEP_LEVEL_MIN_DURATION_RATIO = 0.42

_LINE_SWEEP_SLOT = 'line_sweep_skin'

# Horizontal scroll speed (px/sec) for the tiled country-flag sweep. A single
# un-stretched flag tile slides to the right and repeats behind itself, the
# same scrolling-art motif used by the mystery-card selection screen.
_FLAG_SCROLL_SPEED_PX_PER_SEC = 60.0

# Registry-backed alias map. The country theme registry owns historical
# cosmetic values (`luna_usa`, etc.) and modern aliases (`tr`, `de`,
# `birlesik_krallik`, ...). Keeping it at import time keeps lookup O(1)
# without a global init dance later.
try:
    try:
        from .country_sweep_assets import (  # type: ignore
            country_theme_aliases as _country_theme_aliases,
            get_country_theme as _get_country_theme,
            get_flag_surface as _get_country_flag_surface,
            get_flag_aspect_ratio as _get_country_flag_aspect_ratio,
            list_country_themes as _list_country_themes,
        )
    except ImportError:
        from country_sweep_assets import (  # type: ignore
            country_theme_aliases as _country_theme_aliases,
            get_country_theme as _get_country_theme,
            get_flag_surface as _get_country_flag_surface,
            get_flag_aspect_ratio as _get_country_flag_aspect_ratio,
            list_country_themes as _list_country_themes,
        )
except Exception:
    _country_theme_aliases = {}
    def _get_country_theme(theme_id): return None
    def _get_country_flag_surface(*args): return None
    def _get_country_flag_aspect_ratio(*args): return None
    def _list_country_themes(): return []

try:
    try:
        from .pet_assets import (  # type: ignore
            PET_SLOT as _PET_SLOT,
            is_default_pet as _is_default_pet,
            load_pet_frames as _load_pet_frames,
            normalize_pet as _normalize_pet,
        )
    except ImportError:
        from pet_assets import (  # type: ignore
            PET_SLOT as _PET_SLOT,
            is_default_pet as _is_default_pet,
            load_pet_frames as _load_pet_frames,
            normalize_pet as _normalize_pet,
        )
except Exception:
    _PET_SLOT = 'line_sweep_pet'
    def _is_default_pet(pet): return True
    def _load_pet_frames(*args): return []
    def _normalize_pet(pet): return 'luna_cat'

_LINE_SWEEP_THEME_ALIASES: dict[str, str] = {
    'rainbow': 'rainbow',
    'luna_rainbow': 'rainbow',
    'luna_sweep_rainbow': 'rainbow',
    'usa': 'usa',
    'abd': 'usa',
    'luna_usa': 'usa',
    'luna_sweep_usa': 'usa',
    'turkiye': 'turkiye',
    'turkey': 'turkiye',
    'tr': 'turkiye',
    'luna_turkiye': 'turkiye',
    'luna_sweep_turkiye': 'turkiye',
    'russia': 'russia',
    'rusya': 'russia',
    'luna_russia': 'russia',
    'luna_sweep_russia': 'russia',
    'japan': 'japan',
    'japonya': 'japan',
    'luna_japan': 'japan',
    'luna_sweep_japan': 'japan',
}


def normalize_line_sweep_theme(value: str | None) -> str:
    key = str(value or '').strip().lower()
    return _LINE_SWEEP_THEME_ALIASES.get(key, 'rainbow')


def get_equipped_line_sweep_theme(user_manager=None, profile: dict | None = None) -> str:
    # Basit, tests sırasında eksik olan çağrıyı karşılamak için mevcut profil/veri yapılarını destekler.
    if profile is None and user_manager is not None:
        getter = getattr(user_manager, 'get_equipped_cosmetic', None)
        if callable(getter):
            try:
                equipped = getter(_LINE_SWEEP_SLOT)
            except Exception:
                equipped = None
            else:
                return normalize_line_sweep_theme(equipped)

        profile_getter = getattr(user_manager, 'get_user_data', None)
        if callable(profile_getter):
            try:
                profile = profile_getter()
            except Exception:
                profile = None

    if isinstance(profile, dict):
        equipped_map = profile.get('equipped_cosmetics', {})
        if isinstance(equipped_map, dict):
            return normalize_line_sweep_theme(equipped_map.get(_LINE_SWEEP_SLOT))
    return 'rainbow'


def _resolve_profile(user_manager, profile: dict | None) -> dict | None:
    """Best-effort fetch of the active user's profile dict from a manager.

    Mirrors the defensive lookup used by ``get_equipped_line_sweep_theme`` so
    pet resolution behaves the same across the (loosely typed) user-manager
    variants used in tests and at runtime.
    """
    if profile is not None or user_manager is None:
        return profile
    profile_getter = getattr(user_manager, 'get_user_data', None)
    if not callable(profile_getter):
        return None
    try:
        return profile_getter()
    except TypeError:
        current_getter = getattr(user_manager, 'get_current_user', None)
        try:
            current_user = current_getter() if callable(current_getter) else getattr(user_manager, 'current_user', None)
        except Exception:
            current_user = None
        try:
            return profile_getter(current_user)
        except Exception:
            return None
    except Exception:
        return None


def get_equipped_pet(user_manager=None, profile: dict | None = None) -> str:
    """Resolve the equipped sweep companion (pet) cosmetic value.

    Reads the ``line_sweep_pet`` slot. Falls back to the default Luna-Cat when
    nothing is equipped (the case for every pre-pets profile) or on any error,
    so the sweep always has a valid companion to draw.
    """
    if profile is None and user_manager is not None:
        getter = getattr(user_manager, 'get_equipped_cosmetic', None)
        if callable(getter):
            try:
                equipped = getter(_PET_SLOT)
            except Exception:
                equipped = None
            else:
                return _normalize_pet(equipped)

    profile = _resolve_profile(user_manager, profile)
    if isinstance(profile, dict):
        equipped_map = profile.get('equipped_cosmetics', {})
        if isinstance(equipped_map, dict):
            return _normalize_pet(equipped_map.get(_PET_SLOT))
    return _normalize_pet(None)


def _get_line_sweep_palette(theme: str) -> list[tuple[int, int, int]]:
    """Return a small fallback palette for legacy callers (e.g. preview
    swatches that pre-date the asset pipeline).

    Country themes are now drawn from raster flag assets, but a few
    callers still ask for a colour list to seed surrounding chrome (chip
    backgrounds, the "preview palette" sampler in the store). We hand
    them a flag-accurate sample so the chrome harmonises with the asset.
    """
    normalized = normalize_line_sweep_theme(theme)
    if normalized == 'usa':
        return [
            (191, 13, 62),
            (245, 245, 245),
            (191, 13, 62),
            (245, 245, 245),
            (24, 48, 122),
        ]
    if normalized == 'turkiye':
        return [(227, 10, 23)] * 4 + [(245, 245, 245)]
    if normalized == 'russia':
        return [(245, 245, 245), (40, 80, 200), (210, 40, 50)]
    if normalized == 'japan':
        return [(248, 248, 248)] * 3 + [(220, 50, 60)]
    if normalized == 'china':
        return [(238, 28, 37)] * 4 + [(255, 222, 0)]
    if normalized == 'germany':
        return [(20, 20, 20), (220, 20, 30), (255, 206, 0)]
    if normalized == 'france':
        return [(0, 85, 164), (245, 245, 245), (239, 65, 53)]
    if normalized == 'spain':
        return [(170, 21, 27), (255, 196, 0), (170, 21, 27)]
    if normalized == 'italy':
        return [(0, 146, 70), (245, 245, 245), (206, 43, 55)]
    if normalized == 'brazil':
        return [(0, 156, 59), (255, 223, 0), (0, 39, 118)]
    if normalized == 'south_korea':
        return [(245, 245, 245), (200, 36, 53), (0, 71, 160)]
    if normalized == 'united_kingdom':
        return [(0, 36, 125), (245, 245, 245), (200, 16, 46)]
    return list(_RAINBOW)


def _draw_star(surface: pygame.Surface, center: tuple[int, int], radius: int, color: tuple[int, int, int]) -> None:
    cx, cy = center
    points = []
    outer = max(2, int(radius))
    inner = max(1, int(radius * 0.45))
    for index in range(10):
        angle = -90 + index * 36
        current_radius = outer if index % 2 == 0 else inner
        vector = pygame.math.Vector2(current_radius, 0).rotate(angle)
        points.append((cx + vector.x, cy + vector.y))
    if len(points) >= 3:
        pygame.draw.polygon(surface, color, points)


def draw_line_sweep_band(
    surface: pygame.Surface,
    rect: pygame.Rect,
    theme: str = 'rainbow',
    *,
    stripe_highlight_enabled: bool = True,
    border_radius: int = 0,
    border_color: tuple[int, int, int] | None = None,
    border_alpha: int = 72,
    phase: int = 0,
) -> None:
    if rect.width <= 0 or rect.height <= 0:
        return

    normalized = normalize_line_sweep_theme(theme)

    # Merkezi dikey dalgalanma genliği (yüksekliğin %6'sı veya en az 2 piksel)
    wave_amplitude = max(2.0, rect.height * 0.06)
    draw_h = max(1, int(rect.height - 2 * wave_amplitude))

    # Çizimlerin yapılacağı geçici bir yüzey oluştur
    draw_band = pygame.Surface((rect.width, draw_h), pygame.SRCALPHA)

    # Rainbow keeps its striped palette (the rainbow trail itself is the
    # motif). Country themes go through the unified asset pipeline so we
    # never stack palette stripes underneath the flag — that's what
    # produced the chaotic look on small previews and the cheap, hand-drawn
    # feel on every newly-added country.
    country_spec = _get_country_theme(normalized)
    if normalized == 'rainbow':
        colors = _get_line_sweep_palette(normalized)
        stripe_height = max(1, draw_h // max(1, len(colors)))
        for index, color in enumerate(colors):
            stripe_rect = pygame.Rect(0, index * stripe_height, rect.width, stripe_height + 1)
            # Tam opak yapmak için alpha değerini 255 yapıyoruz
            pygame.draw.rect(draw_band, (*color, 255), stripe_rect)
            if stripe_highlight_enabled and index % 2 == 0 and stripe_rect.width > 4:
                pygame.draw.line(
                    draw_band,
                    (255, 255, 255, 108),
                    (1, stripe_rect.y),
                    (stripe_rect.width - 2, stripe_rect.y),
                    1,
                )
    elif country_spec is not None:
        _draw_country_flag_band(draw_band, draw_band.get_rect(), country_spec.theme_id, phase)
    else:
        # Unknown theme — fall back to the palette path so we never render an
        # empty band.
        colors = _get_line_sweep_palette(normalized)
        stripe_height = max(1, draw_h // max(1, len(colors)))
        for index, color in enumerate(colors):
            stripe_rect = pygame.Rect(0, index * stripe_height, rect.width, stripe_height + 1)
            pygame.draw.rect(draw_band, (*color, 255), stripe_rect)

    # Dikey Dilimleme (Vertical Slicing) ile Dalgalandırma
    band = pygame.Surface(rect.size, pygame.SRCALPHA)
    import math
    elapsed = pygame.time.get_ticks() / 1000.0
    slice_w = 2
    for sx in range(0, rect.width, slice_w):
        angle = (sx * (2.0 * math.pi / 120.0)) - (elapsed * 5.0)
        dy = int(math.sin(angle) * wave_amplitude) + int(wave_amplitude)

        # Dilim sınırlarını taşmayacak şekilde clip edelim
        curr_w = min(slice_w, rect.width - sx)
        slice_rect = pygame.Rect(sx, 0, curr_w, draw_h)
        band.blit(draw_band, (sx, dy), slice_rect)

    # Animated wind-shimmer pass — a soft diagonal highlight that sweeps across
    # the flag in sync with `phase`. Skipped on previews that are too short
    # for the highlight to read as anything but a stray vertical glitch.
    if rect.height >= 24 and rect.width >= 60:
        _apply_wind_shimmer(band, rect, phase, normalized)

    if border_radius > 0:
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=border_radius)
        band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    if border_color is not None and border_alpha > 0:
        pygame.draw.rect(band, (*border_color, border_alpha), band.get_rect(), 1, border_radius=border_radius)

    surface.blit(band, rect.topleft)


# ------------------------------------------------------------------
# Per-theme overlays
# ------------------------------------------------------------------


def _draw_country_flag_band(
    band: pygame.Surface,
    rect: pygame.Rect,
    theme_id: str,
    phase: int,
) -> None:
    """Asset-backed country flag tiled into the sweep band.

    Instead of stretching a single flag across the whole band (which
    distorted the proportions on wide sweeps), we size *one* flag to the
    band height at its natural aspect ratio and tile it horizontally,
    scrolling the tiles to the right. The same flag repeats behind the
    leading copy — mirroring the scrolling card-art animation used on the
    mystery-card selection screen. If the asset isn't available we fall
    back to the colour palette so the band stays drawn.
    """
    width, height = band.get_size()
    if width <= 0 or height <= 0:
        return

    aspect = _get_country_flag_aspect_ratio(theme_id)
    if aspect and aspect > 0:
        # One un-stretched flag tile, sized to the band height.
        tile_w = max(1, int(round(height * aspect)))
        flag = _get_country_flag_surface(theme_id, tile_w, height)
    else:
        flag = None
        tile_w = 0

    if flag is None:
        # Asset missing on disk — last-resort palette so we never ship an
        # invisible band. Logged once via the cache; no spam per frame.
        colors = _get_line_sweep_palette(theme_id)
        stripe_height = max(1, height // max(1, len(colors)))
        for index, color in enumerate(colors):
            pygame.draw.rect(
                band,
                (*color, 232),
                pygame.Rect(0, index * stripe_height, width, stripe_height + 1),
            )
        return

    tile_w = flag.get_width()
    if tile_w <= 0:
        band.blit(flag, (0, 0))
        return

    # Continuous, time-driven scroll so the motion stays smooth regardless
    # of the discrete `phase` value. Loops every tile so the repeat is
    # seamless. Scrolls to the right (image enters from the left).
    elapsed = pygame.time.get_ticks() / 1000.0
    offset = int((elapsed * _FLAG_SCROLL_SPEED_PX_PER_SEC) % tile_w)
    x = offset - tile_w
    while x < width:
        band.blit(flag, (x, 0))
        # Separatör çizgisi tamamen kaldırıldı. Bayraklar doğrudan birleştiriliyor.
        x += tile_w


def _apply_wind_shimmer(band: pygame.Surface, rect: pygame.Rect, phase: int, theme: str) -> None:
    """Soft diagonal highlight that scrolls with phase. Sells the 'wind' feel.

    Rainbow already animates via stripe rotation, so we skip it for that theme
    to avoid double-animation. For flags the shimmer is what makes them read
    as moving instead of static rectangles.
    """
    if theme == 'rainbow':
        return
    width, height = band.get_size()
    if width <= 0 or height <= 0:
        return
    # Highlight is a soft vertical column that travels across the flag.
    # Width scales with the band so previews don't get a knife-thin glitch.
    band_w = max(6, int(width * 0.18))
    cycle = 8
    progress = (phase % cycle) / float(cycle)
    center_x = int(-band_w + (width + band_w * 2) * progress)
    if center_x + band_w < 0 or center_x - band_w >= width:
        return
    shimmer = pygame.Surface((band_w * 2 + 1, height), pygame.SRCALPHA)
    for dx in range(-band_w, band_w + 1):
        falloff = 1.0 - abs(dx) / float(band_w)
        alpha = int(22 * (falloff ** 2))
        if alpha > 0:
            pygame.draw.line(shimmer, (255, 255, 255, alpha), (dx + band_w, 0), (dx + band_w, height), 1)
    band.blit(shimmer, (center_x - band_w, 0))


def compute_line_sweep_progress_speed(
    base_block_speed: float,
    sweep_travel_px: float,
    level: int | float = 1,
) -> float:
    """Satır sweep progress hızını (progress/s) seviye ölçekli hesapla.

    Seviye 1'de mevcut hız korunur, seviye arttıkça sweep süresi kısalır.
    """
    travel_px = max(1.0, float(sweep_travel_px))
    block_speed = max(0.001, float(base_block_speed))

    try:
        level_i = max(1, int(level))
    except Exception:
        level_i = 1

    base_duration = travel_px / (block_speed * 3600.0)
    duration_ratio = _SWEEP_LEVEL_DURATION_DECAY ** max(0, level_i - 1)
    duration_ratio = max(_SWEEP_LEVEL_MIN_DURATION_RATIO, duration_ratio)
    sweep_duration = max(0.0001, base_duration * duration_ratio)
    return 1.0 / sweep_duration


def draw_rainbow_cat_sweep(
    screen: pygame.Surface,
    state: SweepCatState,
    board_rect: pygame.Rect,
    sweep_x: int,
    sweep_width: int,
    phase: int,
    board_width_cells: int,
    stripe_highlight_enabled: bool = True,
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
        # Rainbow, LunaCat'in baş noktasına kadar uzatılır.
        head_attach_x = cat_x + max(1, int(cat_w * _CAT_HEAD_ANCHOR_X))
        trail_x = board_rect.x
        trail_right = max(trail_x + one_col_w, head_attach_x)
        trail_width = max(1, trail_right - trail_x)
    else:
        trail_x = sweep_x
        trail_width = sweep_width

    stripe_h = max(1, sweep_height // 6)
    for i in range(6):
        color = _RAINBOW[(i + phase) % 6]
        stripe_y = sweep_y + i * stripe_h
        stripe_h_i = max(1, (sweep_y + sweep_height) - stripe_y) if i == 5 else stripe_h

        stripe_rect = pygame.Rect(trail_x, stripe_y, trail_width, stripe_h_i)
        clip = stripe_rect.clip(board_rect)
        if clip.width <= 0 or clip.height <= 0:
            continue

        pygame.draw.rect(screen, color, clip)
        if stripe_highlight_enabled and (i + phase) % 2 == 0 and clip.width > 4:
            pygame.draw.line(screen, (255, 255, 255), (clip.x + 1, clip.y), (clip.x + clip.width - 2, clip.y), 1)

    if custom_cat is not None:
        custom_rect = custom_cat.get_rect()
        custom_rect.x = cat_x
        custom_rect.y = cat_y
        clip = custom_rect.clip(board_rect)
        if clip.width > 0 and clip.height > 0:
            src = pygame.Rect(clip.x - custom_rect.x, clip.y - custom_rect.y, clip.width, clip.height)
            screen.blit(custom_cat, clip.topleft, src)
