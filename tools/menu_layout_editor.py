from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

import pygame


# ---------------------------------------------------------------------------
# Sabit referans çözünürlük – panel koordinatları HER ZAMAN bu uzayda tutulur.
# Editör penceresi küçük/büyük olabilir; canvas bu uzayı ölçekleyerek gösterir.
# ---------------------------------------------------------------------------
REFERENCE_W = 1920
REFERENCE_H = 1080

WINDOW_W = 1500
WINDOW_H = 920
FPS = 120
SNAP_DISTANCE = 10
MIN_PANEL_SIZE = 28
HANDLE_SIZE = 12
HISTORY_LIMIT = 400
INDENT_OFFSETS = (8, 10, 12, 16, 20, 24, 30, 40, 48, 60)

ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_LAYOUT_FILE = ROOT_DIR / "menu_layout_runtime.json"
EDITOR_STATE_FILE = Path(__file__).with_name("menu_layout_editor_state.json")
CREDITS_LAYOUT_FILE = ROOT_DIR / "credits_layout.json"
LAYOUT_FILE = RUNTIME_LAYOUT_FILE

BG_COLOR = (10, 16, 28)
GRID_COLOR = (70, 92, 128, 46)
GUIDE_COLOR = (120, 225, 255, 95)
FRAME_COLOR = (150, 205, 255, 120)
TEXT_COLOR = (230, 238, 250)
MUTED_TEXT = (150, 168, 190)
PANEL_FILL_ALPHA = 85
PANEL_BORDER_ALPHA = 210
SELECT_BORDER = (255, 255, 255)

LEGACY_KEY_ALIASES = {
    "pvp": "pvp_2_players",
    "daily": "daily_challenge",
    "campaign": "campaign_mode",
}

PANEL_CHILD_LINKS: dict[str, tuple[str, ...]] = {
    "new_gen_tetris": ("new_gen_tetris_sticker",),
    "tutorial_mode": ("tutorial_mode_sticker",),
}


# ---------------------------------------------------------------------------
# Panel veri yapısı – rect her zaman 1920x1080 referans uzayında
# ---------------------------------------------------------------------------
@dataclass
class Panel:
    key: str
    title: str
    rect: pygame.Rect          # 1920x1080 referans koordinatları
    color: tuple[int, int, int]


def _default_panels() -> list[Panel]:
    """Varsayılan panel düzeni – 1920×1080 koordinat uzayı."""
    return [
        Panel("hero_panel", "QUADRIX Üst Panel", pygame.Rect(590, 28, 870, 140), (0, 220, 255)),
        Panel("sos_button", "SOS Butonu", pygame.Rect(1690, 28, 140, 52), (255, 70, 70)),

        Panel("settings_button", "Ayarlar Butonu", pygame.Rect(30, 28, 56, 56), (0, 240, 255)),
        Panel("language_button", "Dil Butonu", pygame.Rect(30, 98, 56, 56), (255, 90, 90)),
        Panel("mute_button", "Ses Butonu", pygame.Rect(100, 28, 56, 56), (0, 255, 170)),
        Panel("switch_user_button", "Kullanıcı Butonu", pygame.Rect(1840, 94, 56, 56), (255, 0, 180)),

        Panel("new_gen_tetris", "Kart Ustalığı", pygame.Rect(80, 188, 490, 550), (255, 0, 180)),
        Panel("new_gen_tetris_sticker", "Kart Ustalığı Sticker", pygame.Rect(108, 248, 434, 330), (140, 110, 255)),
        Panel("piece_workshop", "Parça Atölyesi", pygame.Rect(595, 188, 300, 290), (255, 0, 180)),
        Panel("extras", "Oyun Modları", pygame.Rect(910, 188, 300, 290), (0, 240, 255)),
        Panel("pvp_2_players", "PvP (Local + Online)", pygame.Rect(595, 500, 615, 200), (255, 155, 0)),
        Panel("tutorial_mode", "Eğitim", pygame.Rect(1215, 188, 230, 290), (120, 225, 255)),
        Panel("tutorial_mode_sticker", "Eğitim Sticker", pygame.Rect(1234, 250, 190, 175), (110, 185, 255)),
        Panel("achievements", "Başarılar", pygame.Rect(1460, 188, 380, 290), (255, 220, 40)),
        Panel("steam_scores", "Steam Skor Tablosu", pygame.Rect(1460, 490, 380, 370), (80, 230, 120)),
        Panel("daily_challenge", "Günlük", pygame.Rect(80, 750, 490, 250), (0, 255, 180)),
        Panel("campaign_mode", "Görev Modu", pygame.Rect(595, 720, 300, 260), (0, 240, 255)),
        Panel("block_styles", "Blok Görünümleri", pygame.Rect(910, 500, 300, 290), (0, 240, 255)),

        Panel("guide_button", "Kılavuz Butonu", pygame.Rect(30, 880, 56, 56), (100, 200, 255)),
        Panel("credits_button", "Emeği Geçenler Butonu", pygame.Rect(30, 950, 56, 56), (255, 220, 40)),
        Panel("high_scores_button", "Yüksek Skor Butonu", pygame.Rect(100, 950, 56, 56), (255, 220, 40)),
        Panel("exit_button", "Çıkış Butonu", pygame.Rect(1690, 990, 170, 64), (255, 80, 80)),
    ]


# ---------------------------------------------------------------------------
# Seri hâle getirme
# ---------------------------------------------------------------------------
def _panel_to_dict(panel: Panel) -> dict:
    return {
        "key": panel.key,
        "title": panel.title,
        "x": int(panel.rect.x),
        "y": int(panel.rect.y),
        "w": int(panel.rect.w),
        "h": int(panel.rect.h),
        "color": list(panel.color),
    }


def _dict_to_panel(data: dict) -> Panel:
    return Panel(
        key=str(data["key"]),
        title=str(data.get("title", data["key"])),
        rect=pygame.Rect(
            int(data["x"]),
            int(data["y"]),
            max(MIN_PANEL_SIZE, int(data["w"])),
            max(MIN_PANEL_SIZE, int(data["h"])),
        ),
        color=tuple(data.get("color", [0, 240, 255]))[:3],
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Editör canvas hesaplaması
# ---------------------------------------------------------------------------
def _compute_canvas_layout(
    win_w: int, win_h: int
) -> tuple[pygame.Rect, pygame.Rect, float]:
    """Editör penceresine sığacak şekilde 1920×1080 canvasının ekran
    koordinatlarını, yan paneli ve ölçek faktörünü döndürür.

    Returns:
        (canvas_screen_rect, sidebar_rect, scale)
    """
    outer_margin = 20
    panel_gap = 18
    min_sidebar_w = 260
    max_sidebar_w = 380

    sidebar_w = int(win_w * 0.22)
    sidebar_w = max(min_sidebar_w, min(max_sidebar_w, sidebar_w))

    avail_w = max(1, win_w - outer_margin * 2 - panel_gap - sidebar_w)
    avail_h = max(1, win_h - outer_margin * 2)

    # 1920×1080 oranını koruyarak mümkün olan en büyük canvas
    scale = min(avail_w / REFERENCE_W, avail_h / REFERENCE_H)
    scale = max(0.1, scale)

    canvas_w = int(REFERENCE_W * scale)
    canvas_h = int(REFERENCE_H * scale)

    canvas_x = outer_margin
    canvas_y = outer_margin + (avail_h - canvas_h) // 2  # dikeyde ortala

    canvas = pygame.Rect(canvas_x, canvas_y, canvas_w, canvas_h)

    sidebar_x = canvas.right + panel_gap
    sidebar = pygame.Rect(sidebar_x, outer_margin, sidebar_w, max(1, win_h - outer_margin * 2))

    return canvas, sidebar, scale


# ---------------------------------------------------------------------------
# Koordinat dönüşüm yardımcıları
# ---------------------------------------------------------------------------
def _ref_to_screen(rx: float, ry: float, canvas: pygame.Rect, scale: float) -> tuple[int, int]:
    """Referans (1920×1080) → ekran pikseli."""
    return int(canvas.x + rx * scale), int(canvas.y + ry * scale)


def _screen_to_ref(sx: int, sy: int, canvas: pygame.Rect, scale: float) -> tuple[float, float]:
    """Ekran pikseli → referans (1920×1080)."""
    return (sx - canvas.x) / scale, (sy - canvas.y) / scale


def _ref_rect_to_screen(r: pygame.Rect, canvas: pygame.Rect, scale: float) -> pygame.Rect:
    """Referans Rect → ekran Rect."""
    x, y = _ref_to_screen(r.x, r.y, canvas, scale)
    return pygame.Rect(x, y, max(1, int(r.w * scale)), max(1, int(r.h * scale)))


# ---------------------------------------------------------------------------
# Kaydet / Yükle
# ---------------------------------------------------------------------------
def save_layout(panels: list[Panel]) -> None:
    """Panel düzenini 1920×1080 referans uzayında kaydet.

    Runtime dosyası ``screen_pct`` koordinat uzayında yüzde değerleri içerir;
    oyun tarafı ekran boyutunu çarparak konumları elde eder.
    """
    # Editör state – ham piksel değerleri (1920×1080)
    state_payload = {
        "version": 3,
        "reference_resolution": [REFERENCE_W, REFERENCE_H],
        "panels": [_panel_to_dict(p) for p in panels],
    }
    EDITOR_STATE_FILE.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Runtime – yüzde tabanlı
    runtime_rects: dict[str, dict[str, Any]] = {}
    for panel in panels:
        key = LEGACY_KEY_ALIASES.get(panel.key, panel.key)
        runtime_rects[key] = {
            "x_pct": round(_clamp(panel.rect.x / REFERENCE_W, -0.1, 1.1), 6),
            "y_pct": round(_clamp(panel.rect.y / REFERENCE_H, -0.1, 1.1), 6),
            "w_pct": round(_clamp(panel.rect.w / REFERENCE_W, 0.005, 1.5), 6),
            "h_pct": round(_clamp(panel.rect.h / REFERENCE_H, 0.005, 1.5), 6),
            "title": panel.title,
        }

    runtime_payload = {
        "version": 3,
        "source": "tools/menu_layout_editor.py",
        "coord_space": "screen_pct",
        "reference_resolution": [REFERENCE_W, REFERENCE_H],
        "rects": runtime_rects,
        "panels": [_panel_to_dict(p) for p in panels],
    }
    RUNTIME_LAYOUT_FILE.write_text(json.dumps(runtime_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_layout() -> list[Panel]:
    """Kaydedilmiş düzeni yükle; bulamazsa varsayılana dön.

    Koordinatlar daima 1920×1080 referans uzayına dönüştürülür.
    """
    defaults = _default_panels()
    default_map = {p.key: p for p in defaults}

    def _merge_missing(loaded: list[Panel]) -> list[Panel]:
        if not loaded:
            return defaults[:]
        existing = {p.key for p in loaded}
        for key, dp in default_map.items():
            if key not in existing:
                loaded.append(Panel(dp.key, dp.title, dp.rect.copy(), dp.color))
        return loaded

    for candidate in (EDITOR_STATE_FILE, RUNTIME_LAYOUT_FILE):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
        except Exception:
            continue

        # --- raw panels dizisinden yükle (editör state veya runtime.panels) ---
        raw_panels = payload.get("panels")
        if isinstance(raw_panels, list) and raw_panels:
            ref_res = payload.get("reference_resolution")
            ref_w, ref_h = REFERENCE_W, REFERENCE_H
            if isinstance(ref_res, list) and len(ref_res) == 2:
                ref_w = max(1, int(ref_res[0]))
                ref_h = max(1, int(ref_res[1]))

            # Eski reference_window desteği (v2 dosyaları)
            ref_win = payload.get("reference_window")
            if ref_res is None and isinstance(ref_win, list) and len(ref_win) == 2:
                ref_w = max(1, int(ref_win[0]))
                ref_h = max(1, int(ref_win[1]))

            sx = REFERENCE_W / ref_w
            sy = REFERENCE_H / ref_h

            loaded: list[Panel] = []
            seen: dict[str, int] = {}
            for item in raw_panels:
                if not isinstance(item, dict):
                    continue
                p = _dict_to_panel(item)
                norm_key = LEGACY_KEY_ALIASES.get(p.key, p.key)
                if norm_key == "piece_workshop_sticker":
                    continue
                p.key = norm_key
                if sx != 1.0 or sy != 1.0:
                    p.rect = pygame.Rect(
                        int(p.rect.x * sx),
                        int(p.rect.y * sy),
                        max(MIN_PANEL_SIZE, int(p.rect.w * sx)),
                        max(MIN_PANEL_SIZE, int(p.rect.h * sy)),
                    )
                dp = default_map.get(norm_key)
                if dp:
                    p.color = dp.color
                    if not p.title:
                        p.title = dp.title
                if norm_key in seen:
                    loaded[seen[norm_key]] = p
                else:
                    seen[norm_key] = len(loaded)
                    loaded.append(p)

            merged = _merge_missing(loaded)
            if merged:
                return merged

        # --- rects (yüzde) üzerinden yükle ---
        rects = payload.get("rects")
        if isinstance(rects, dict) and rects:
            coord_space = str(payload.get("coord_space", "screen_pct")).strip().lower()

            ref_canvas = payload.get("reference_canvas")
            ref_win = payload.get("reference_window")

            loaded2: list[Panel] = []
            for raw_key, data in rects.items():
                if not isinstance(data, dict):
                    continue
                key = LEGACY_KEY_ALIASES.get(str(raw_key), str(raw_key))
                if key == "piece_workshop_sticker":
                    continue
                try:
                    x_pct = float(data["x_pct"])
                    y_pct = float(data["y_pct"])
                    w_pct = float(data["w_pct"])
                    h_pct = float(data["h_pct"])
                except Exception:
                    continue

                if coord_space == "canvas_pct" and isinstance(ref_canvas, list) and len(ref_canvas) == 4:
                    cx, cy, cw, ch = [int(v) for v in ref_canvas]
                    cw, ch = max(1, cw), max(1, ch)
                    abs_x = cx + cw * x_pct
                    abs_y = cy + ch * y_pct
                    abs_w = cw * w_pct
                    abs_h = ch * h_pct
                    if isinstance(ref_win, list) and len(ref_win) == 2:
                        ow, oh = max(1, int(ref_win[0])), max(1, int(ref_win[1]))
                    else:
                        ow, oh = REFERENCE_W, REFERENCE_H
                    sx2 = REFERENCE_W / ow
                    sy2 = REFERENCE_H / oh
                    rx = int(abs_x * sx2)
                    ry = int(abs_y * sy2)
                    rw = max(MIN_PANEL_SIZE, int(abs_w * sx2))
                    rh = max(MIN_PANEL_SIZE, int(abs_h * sy2))
                else:
                    rx = int(REFERENCE_W * x_pct)
                    ry = int(REFERENCE_H * y_pct)
                    rw = max(MIN_PANEL_SIZE, int(REFERENCE_W * w_pct))
                    rh = max(MIN_PANEL_SIZE, int(REFERENCE_H * h_pct))

                dp = default_map.get(key)
                title = str(data.get("title") or (dp.title if dp else key))
                color = dp.color if dp else (0, 240, 255)
                loaded2.append(Panel(key=key, title=title, rect=pygame.Rect(rx, ry, rw, rh), color=color))

            merged2 = _merge_missing(loaded2)
            if merged2:
                return merged2

    return defaults[:]


# ---------------------------------------------------------------------------
# Çizim yardımcıları
# ---------------------------------------------------------------------------
def _draw_text(surface: pygame.Surface, text: str, pos: tuple[int, int], font: pygame.font.Font, color=TEXT_COLOR) -> None:
    surf = font.render(text, True, color)
    surface.blit(surf, pos)


def _draw_grid(surface: pygame.Surface, canvas: pygame.Rect, scale: float) -> None:
    overlay = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
    step_ref = 40
    step_scr = max(4, int(step_ref * scale))
    for x in range(0, canvas.w, step_scr):
        pygame.draw.line(overlay, GRID_COLOR, (x, 0), (x, canvas.h), 1)
    for y in range(0, canvas.h, step_scr):
        pygame.draw.line(overlay, GRID_COLOR, (0, y), (canvas.w, y), 1)
    surface.blit(overlay, canvas.topleft)


def _draw_guides(surface: pygame.Surface, guides: list[tuple[str, int]], canvas: pygame.Rect, scale: float) -> None:
    if not guides:
        return
    overlay = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
    for axis, ref_val in guides:
        if axis == "x":
            sx = int(ref_val * scale)
            pygame.draw.line(overlay, GUIDE_COLOR, (sx, 0), (sx, canvas.h), 1)
        else:
            sy = int(ref_val * scale)
            pygame.draw.line(overlay, GUIDE_COLOR, (0, sy), (canvas.w, sy), 1)
    surface.blit(overlay, canvas.topleft)


def _draw_screen_frame(surface: pygame.Surface, frame_rect: pygame.Rect) -> None:
    overlay = pygame.Surface((frame_rect.w, frame_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(overlay, FRAME_COLOR, overlay.get_rect(), 1, border_radius=10)
    tick = 12
    points = [
        ((0, 0), (tick, 0), (0, tick)),
        ((frame_rect.w - 1, 0), (frame_rect.w - 1 - tick, 0), (frame_rect.w - 1, tick)),
        ((0, frame_rect.h - 1), (tick, frame_rect.h - 1), (0, frame_rect.h - 1 - tick)),
        ((frame_rect.w - 1, frame_rect.h - 1), (frame_rect.w - 1 - tick, frame_rect.h - 1), (frame_rect.w - 1, frame_rect.h - 1 - tick)),
    ]
    for corner, p1, p2 in points:
        pygame.draw.line(overlay, FRAME_COLOR, corner, p1, 2)
        pygame.draw.line(overlay, FRAME_COLOR, corner, p2, 2)
    surface.blit(overlay, frame_rect.topleft)


# ---------------------------------------------------------------------------
# Tutamaçlar (handles) – ekran uzayında
# ---------------------------------------------------------------------------
def _get_handles_screen(screen_rect: pygame.Rect) -> dict[str, pygame.Rect]:
    cx = screen_rect.centerx
    cy = screen_rect.centery
    hs = HANDLE_SIZE
    return {
        "n": pygame.Rect(cx - hs // 2, screen_rect.top - hs // 2, hs, hs),
        "s": pygame.Rect(cx - hs // 2, screen_rect.bottom - hs // 2, hs, hs),
        "w": pygame.Rect(screen_rect.left - hs // 2, cy - hs // 2, hs, hs),
        "e": pygame.Rect(screen_rect.right - hs // 2, cy - hs // 2, hs, hs),
        "nw": pygame.Rect(screen_rect.left - hs // 2, screen_rect.top - hs // 2, hs, hs),
        "ne": pygame.Rect(screen_rect.right - hs // 2, screen_rect.top - hs // 2, hs, hs),
        "sw": pygame.Rect(screen_rect.left - hs // 2, screen_rect.bottom - hs // 2, hs, hs),
        "se": pygame.Rect(screen_rect.right - hs // 2, screen_rect.bottom - hs // 2, hs, hs),
    }


# ---------------------------------------------------------------------------
# Snap – referans uzayda çalışır
# ---------------------------------------------------------------------------
def _collect_snap_candidates(panels: list[Panel], active_idx: int) -> tuple[list[int], list[int]]:
    xs: set[int] = {0, REFERENCE_W // 2, REFERENCE_W}
    ys: set[int] = {0, REFERENCE_H // 2, REFERENCE_H}
    for idx, panel in enumerate(panels):
        if idx == active_idx:
            continue
        r = panel.rect
        xs.update([r.left, r.centerx, r.right])
        ys.update([r.top, r.centery, r.bottom])

        # Girinti/boşluk hizası için ek aday çizgiler
        for off in INDENT_OFFSETS:
            xs.update([r.left - off, r.left + off, r.right - off, r.right + off])
            ys.update([r.top - off, r.top + off, r.bottom - off, r.bottom + off])

    return sorted(xs), sorted(ys)


def _snap_value(value: int, candidates: list[int]) -> tuple[int, Optional[int]]:
    best = None
    best_delta = SNAP_DISTANCE + 1
    for c in candidates:
        delta = abs(value - c)
        if delta < best_delta:
            best_delta = delta
            best = c
    if best is not None and best_delta <= SNAP_DISTANCE:
        return best, best
    return value, None


def _snap_rect(rect: pygame.Rect, x_candidates: list[int], y_candidates: list[int]) -> tuple[pygame.Rect, list[tuple[str, int]]]:
    guides: list[tuple[str, int]] = []

    left_snapped, g = _snap_value(rect.left, x_candidates)
    centerx_snapped, g2 = _snap_value(rect.centerx, x_candidates)
    right_snapped, g3 = _snap_value(rect.right, x_candidates)

    best_x = rect.x
    best_x_dist = SNAP_DISTANCE + 1
    for target, edge_name, guide in (
        (left_snapped, "left", g),
        (centerx_snapped, "centerx", g2),
        (right_snapped, "right", g3),
    ):
        current = getattr(rect, edge_name)
        dist = abs(target - current)
        if dist < best_x_dist and dist <= SNAP_DISTANCE:
            best_x_dist = dist
            if edge_name == "left":
                best_x = target
            elif edge_name == "centerx":
                best_x = target - rect.w // 2
            else:
                best_x = target - rect.w
            if guide is not None:
                guides = [item for item in guides if item[0] != "x"]
                guides.append(("x", guide))

    top_snapped, gy = _snap_value(rect.top, y_candidates)
    centery_snapped, gy2 = _snap_value(rect.centery, y_candidates)
    bottom_snapped, gy3 = _snap_value(rect.bottom, y_candidates)

    best_y = rect.y
    best_y_dist = SNAP_DISTANCE + 1
    for target, edge_name, guide in (
        (top_snapped, "top", gy),
        (centery_snapped, "centery", gy2),
        (bottom_snapped, "bottom", gy3),
    ):
        current = getattr(rect, edge_name)
        dist = abs(target - current)
        if dist < best_y_dist and dist <= SNAP_DISTANCE:
            best_y_dist = dist
            if edge_name == "top":
                best_y = target
            elif edge_name == "centery":
                best_y = target - rect.h // 2
            else:
                best_y = target - rect.h
            if guide is not None:
                guides = [item for item in guides if item[0] != "y"]
                guides.append(("y", guide))

    snapped = rect.copy()
    snapped.x = best_x
    snapped.y = best_y
    return snapped, guides


def _snap_resize_rect(
    rect: pygame.Rect,
    active_handle: str,
    x_candidates: list[int],
    y_candidates: list[int],
) -> tuple[pygame.Rect, list[tuple[str, int]]]:
    """Resize sırasında yalnızca sürüklenen kenarları snap'le.

    Böylece ör. sağ kenarı sürüklerken panelin solu kaymaz; sağ kenar hedef
    kenara oturur. Aynı mantık üst/alt için de uygulanır.
    """
    snapped = rect.copy()
    guides: list[tuple[str, int]] = []

    if "w" in active_handle:
        target, gx = _snap_value(snapped.left, x_candidates)
        if gx is not None:
            fixed_right = snapped.right
            new_left = min(target, fixed_right - MIN_PANEL_SIZE)
            snapped.x = new_left
            snapped.w = max(MIN_PANEL_SIZE, fixed_right - new_left)
            guides.append(("x", gx))
    elif "e" in active_handle:
        target, gx = _snap_value(snapped.right, x_candidates)
        if gx is not None:
            fixed_left = snapped.left
            new_right = max(target, fixed_left + MIN_PANEL_SIZE)
            snapped.w = max(MIN_PANEL_SIZE, new_right - fixed_left)
            guides.append(("x", gx))

    if "n" in active_handle:
        target, gy = _snap_value(snapped.top, y_candidates)
        if gy is not None:
            fixed_bottom = snapped.bottom
            new_top = min(target, fixed_bottom - MIN_PANEL_SIZE)
            snapped.y = new_top
            snapped.h = max(MIN_PANEL_SIZE, fixed_bottom - new_top)
            guides = [g for g in guides if g[0] != "y"]
            guides.append(("y", gy))
    elif "s" in active_handle:
        target, gy = _snap_value(snapped.bottom, y_candidates)
        if gy is not None:
            fixed_top = snapped.top
            new_bottom = max(target, fixed_top + MIN_PANEL_SIZE)
            snapped.h = max(MIN_PANEL_SIZE, new_bottom - fixed_top)
            guides = [g for g in guides if g[0] != "y"]
            guides.append(("y", gy))

    return snapped, guides


def _clamp_to_reference(rect: pygame.Rect) -> pygame.Rect:
    """Panel rect'ini 0..REFERENCE_W × 0..REFERENCE_H sınırlarında tut."""
    out = rect.copy()
    if out.w > REFERENCE_W:
        out.w = REFERENCE_W
    if out.h > REFERENCE_H:
        out.h = REFERENCE_H
    out.x = max(0, min(out.x, REFERENCE_W - out.w))
    out.y = max(0, min(out.y, REFERENCE_H - out.h))
    return out


def _build_panel_index_map(panels: list[Panel]) -> dict[str, int]:
    index_map: dict[str, int] = {}
    for idx, panel in enumerate(panels):
        if panel.key not in index_map:
            index_map[panel.key] = idx
    return index_map


def _capture_linked_child_state(
    panels: list[Panel],
    parent_indices: set[int],
    excluded_indices: set[int] | None = None,
) -> dict[int, tuple[int, float, float, float, float]]:
    """Seçili parent panellerin child'ları için göreli konum/ölçek oranını yakala."""
    if not parent_indices:
        return {}

    excluded = excluded_indices or set()
    idx_map = _build_panel_index_map(panels)
    bindings: dict[int, tuple[int, float, float, float, float]] = {}

    for parent_idx in parent_indices:
        if not (0 <= parent_idx < len(panels)):
            continue
        parent = panels[parent_idx]
        if parent.rect.w <= 0 or parent.rect.h <= 0:
            continue

        for child_key in PANEL_CHILD_LINKS.get(parent.key, ()): 
            child_idx = idx_map.get(child_key)
            if child_idx is None or child_idx in excluded or not (0 <= child_idx < len(panels)):
                continue
            child = panels[child_idx]
            rel_x = (child.rect.x - parent.rect.x) / max(1, parent.rect.w)
            rel_y = (child.rect.y - parent.rect.y) / max(1, parent.rect.h)
            rel_w = child.rect.w / max(1, parent.rect.w)
            rel_h = child.rect.h / max(1, parent.rect.h)
            bindings[child_idx] = (parent_idx, rel_x, rel_y, rel_w, rel_h)

    return bindings


def _apply_linked_child_state(
    panels: list[Panel],
    bindings: dict[int, tuple[int, float, float, float, float]],
) -> bool:
    """Yakalanan oranları kullanarak child panelleri parent ile birlikte güncelle."""
    changed = False
    for child_idx, (parent_idx, rel_x, rel_y, rel_w, rel_h) in bindings.items():
        if not (0 <= parent_idx < len(panels) and 0 <= child_idx < len(panels)):
            continue

        parent = panels[parent_idx]
        child = panels[child_idx]
        if parent.rect.w <= 0 or parent.rect.h <= 0:
            continue

        new_w = max(MIN_PANEL_SIZE, int(round(parent.rect.w * rel_w)))
        new_h = max(MIN_PANEL_SIZE, int(round(parent.rect.h * rel_h)))
        new_w = min(new_w, parent.rect.w)
        new_h = min(new_h, parent.rect.h)

        new_x = int(round(parent.rect.x + parent.rect.w * rel_x))
        new_y = int(round(parent.rect.y + parent.rect.h * rel_y))

        new_x = max(parent.rect.left, min(new_x, parent.rect.right - new_w))
        new_y = max(parent.rect.top, min(new_y, parent.rect.bottom - new_h))

        new_rect = _clamp_to_reference(pygame.Rect(new_x, new_y, new_w, new_h))
        if new_rect != child.rect:
            child.rect = new_rect
            changed = True

    return changed


# ---------------------------------------------------------------------------
# Sidebar boyut girişi yardımcıları
# ---------------------------------------------------------------------------
SELECT_BOX_COLOR = (120, 200, 255, 60)
SELECT_BOX_BORDER = (120, 220, 255, 160)
INPUT_BG = (20, 30, 50)
INPUT_BG_ACTIVE = (30, 50, 80)
INPUT_BORDER = (80, 130, 180)
INPUT_BORDER_ACTIVE = (100, 200, 255)
INPUT_TEXT = (230, 240, 255)
BUTTON_BG = (24, 40, 64)
BUTTON_BG_HOVER = (35, 58, 88)
BUTTON_BORDER = (90, 145, 205)
BUTTON_TEXT = (225, 240, 255)


@dataclass
class InputField:
    """Sidebar'daki tek satırlık sayı giriş alanı."""
    label: str
    attr: str                 # 'x', 'y', 'w', 'h'
    rect: pygame.Rect         # ekran koordinatı (her frame güncellenir)
    text: str = ""
    active: bool = False


@dataclass
class SideButton:
    label: str
    action: str
    rect: pygame.Rect


def _make_input_fields() -> list[InputField]:
    """4 adet boyut giriş alanı oluştur (placeholder rect)."""
    return [
        InputField("X", "x", pygame.Rect(0, 0, 70, 24)),
        InputField("Y", "y", pygame.Rect(0, 0, 70, 24)),
        InputField("W", "w", pygame.Rect(0, 0, 70, 24)),
        InputField("H", "h", pygame.Rect(0, 0, 70, 24)),
    ]


def _clone_panels(panels: list[Panel]) -> list[Panel]:
    return [Panel(p.key, p.title, p.rect.copy(), p.color) for p in panels]


def _panels_signature(panels: list[Panel]) -> tuple:
    return tuple((p.key, p.title, p.rect.x, p.rect.y, p.rect.w, p.rect.h, p.color) for p in panels)


def _push_history_state(history: list[list[Panel]], history_index: int, panels: list[Panel]) -> int:
    if history and _panels_signature(history[history_index]) == _panels_signature(panels):
        return history_index

    del history[history_index + 1 :]
    history.append(_clone_panels(panels))
    if len(history) > HISTORY_LIMIT:
        overflow = len(history) - HISTORY_LIMIT
        del history[:overflow]
        history_index = max(0, history_index - overflow)
    return len(history) - 1


def _sanitize_selection(selected_idx: int, selected_set: set[int], panels: list[Panel]) -> tuple[int, set[int]]:
    max_idx = len(panels) - 1
    selected_set = {i for i in selected_set if 0 <= i <= max_idx}
    if selected_idx > max_idx:
        selected_idx = max_idx
    if selected_idx < 0 and selected_set:
        selected_idx = min(selected_set)
    if selected_idx >= 0 and not selected_set:
        selected_set = {selected_idx}
    return selected_idx, selected_set


def _get_center_delta(panel: Panel) -> tuple[int, int, bool, bool]:
    dx = panel.rect.centerx - (REFERENCE_W // 2)
    dy = panel.rect.centery - (REFERENCE_H // 2)
    return dx, dy, dx == 0, dy == 0


def _make_sidebar_buttons(sidebar: pygame.Rect, top_y: int, width: int) -> list[SideButton]:
    btn_h = 28
    gap = 8
    x = sidebar.x + 14
    y = top_y
    return [
        SideButton("↶ Geri", "undo", pygame.Rect(x, y, width, btn_h)),
        SideButton("↷ İleri", "redo", pygame.Rect(x, y + btn_h + gap, width, btn_h)),
        SideButton("Önizleme", "toggle_preview", pygame.Rect(x, y + (btn_h + gap) * 2, width, btn_h)),
        SideButton("Oyun İçi Çizim", "toggle_ingame_preview", pygame.Rect(x, y + (btn_h + gap) * 3, width, btn_h)),
    ]


def _draw_side_button(
    screen: pygame.Surface,
    button: SideButton,
    font: pygame.font.Font,
    is_hover: bool,
    active: bool = False,
) -> None:
    bg = BUTTON_BG_HOVER if (is_hover or active) else BUTTON_BG
    pygame.draw.rect(screen, bg, button.rect, border_radius=6)
    pygame.draw.rect(screen, BUTTON_BORDER, button.rect, 1, border_radius=6)
    txt = font.render(button.label, True, BUTTON_TEXT)
    txt_rect = txt.get_rect(center=button.rect.center)
    screen.blit(txt, txt_rect)


class _InGameMenuPreviewRenderer:
    """Menu sınıfını editör içinde off-screen render ederek canlı önizleme üretir."""

    def __init__(self) -> None:
        self._initialized = False
        self.available = False
        self.error: str = ""
        self._menu: Any = None
        self._surface: Optional[pygame.Surface] = None

    def _ensure_ready(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        src_dir = ROOT_DIR / "src"
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)

        try:
            from menu import Menu  # type: ignore

            self._surface = pygame.Surface((REFERENCE_W, REFERENCE_H), pygame.SRCALPHA)
            self._menu = Menu(self._surface, user_manager=None, settings_manager=None)
            # Editör önizlemesinde Steam sorgu yenilemesini agresif tetikleme.
            if hasattr(self._menu, "_mystery_lb_refresh_ms"):
                self._menu._mystery_lb_refresh_ms = 10**9
            self.available = True
        except Exception as exc:
            self.available = False
            self.error = f"Canlı önizleme yüklenemedi: {exc.__class__.__name__}"

    def draw(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        panels: list[Panel],
        font: pygame.font.Font,
        font_small: pygame.font.Font,
        scale: float,
    ) -> bool:
        self._ensure_ready()
        if not self.available or self._menu is None or self._surface is None:
            _draw_preview(surface, canvas, panels, font, font_small, scale)
            err = self.error or "Canlı önizleme kullanılamıyor"
            hint = font_small.render(err, True, (255, 170, 170))
            surface.blit(hint, (canvas.x + 14, canvas.bottom - 26))
            return False

        try:
            runtime_rects: dict[str, dict[str, Any]] = {}
            for panel in panels:
                key = LEGACY_KEY_ALIASES.get(panel.key, panel.key)
                runtime_rects[key] = {
                    "x_pct": _clamp(panel.rect.x / REFERENCE_W, -0.1, 1.1),
                    "y_pct": _clamp(panel.rect.y / REFERENCE_H, -0.1, 1.1),
                    "w_pct": _clamp(panel.rect.w / REFERENCE_W, 0.005, 1.5),
                    "h_pct": _clamp(panel.rect.h / REFERENCE_H, 0.005, 1.5),
                    "title": panel.title,
                }

            self._menu._layout_override_cache = runtime_rects
            self._menu._layout_override_coord_space = "screen_pct"
            self._menu._layout_override_reference_window = [REFERENCE_W, REFERENCE_H]
            self._menu._layout_override_reference_canvas = None
            self._menu._load_layout_overrides = lambda: runtime_rects

            self._menu.screen = self._surface
            self._menu.draw()

            scaled = pygame.transform.smoothscale(self._surface, (canvas.w, canvas.h))
            surface.blit(scaled, canvas.topleft)
            pygame.draw.rect(surface, (42, 70, 108), canvas, 1, border_radius=14)
            return True
        except Exception as exc:
            self.error = f"Canlı önizleme hatası: {exc.__class__.__name__}"
            _draw_preview(surface, canvas, panels, font, font_small, scale)
            hint = font_small.render(self.error, True, (255, 170, 170))
            surface.blit(hint, (canvas.x + 14, canvas.bottom - 26))
            return False


def _draw_preview(
    surface: pygame.Surface,
    canvas: pygame.Rect,
    panels: list[Panel],
    font: pygame.font.Font,
    font_small: pygame.font.Font,
    scale: float,
) -> None:
    bg = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
    bg.fill((10, 16, 30, 255))
    surface.blit(bg, canvas.topleft)
    pygame.draw.rect(surface, (42, 70, 108), canvas, 1, border_radius=14)

    title = font.render("Ana Menü Önizleme (Simülasyon)", True, (220, 236, 255))
    surface.blit(title, (canvas.x + 16, canvas.y + 14))

    for panel in panels:
        scr = _ref_rect_to_screen(panel.rect, canvas, scale)
        fill = pygame.Surface(scr.size, pygame.SRCALPHA)
        fill.fill((*panel.color, 145))
        surface.blit(fill, scr.topleft)
        pygame.draw.rect(surface, (245, 250, 255, 200), scr, 2, border_radius=12)

        text = panel.title if scr.w >= 130 else panel.key
        label = font_small.render(text, True, (242, 248, 255))
        surface.blit(label, (scr.x + 10, scr.y + 8))

        if panel.key == "hero_panel":
            subtitle = font_small.render("(Başlık paneli merkezde olmalı)", True, (200, 230, 255))
            surface.blit(subtitle, (scr.x + 10, scr.y + 30))


# ---------------------------------------------------------------------------
# Credits Layout – maskot boyut/konum verileri
# ---------------------------------------------------------------------------
CREDITS_DEFAULTS = {
    "side_panel_w": 340,
    "side_panel_h": 300,
    "side_margin": 24,
    "side_gap": 20,
}

CREDITS_FIELD_LABELS = [
    ("side_panel_w", "Panel Genişliği (side_panel_w)"),
    ("side_panel_h", "Panel Yüksekliği (side_panel_h)"),
    ("side_margin", "Yan Boşluk (side_margin)"),
    ("side_gap", "İç Boşluk (side_gap)"),
]


def load_credits_layout() -> dict:
    if CREDITS_LAYOUT_FILE.exists():
        try:
            data = json.loads(CREDITS_LAYOUT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result = CREDITS_DEFAULTS.copy()
                for k in CREDITS_DEFAULTS:
                    if k in data and isinstance(data[k], (int, float)):
                        result[k] = int(data[k])
                return result
        except Exception:
            pass
    return CREDITS_DEFAULTS.copy()


def save_credits_layout(values: dict) -> None:
    payload = {k: int(values.get(k, CREDITS_DEFAULTS[k])) for k in CREDITS_DEFAULTS}
    CREDITS_LAYOUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class CreditsInputField:
    label: str
    key: str
    rect: pygame.Rect
    text: str = ""
    active: bool = False


def _make_credits_input_fields() -> list[CreditsInputField]:
    return [CreditsInputField(label, key, pygame.Rect(0, 0, 90, 24)) for key, label in CREDITS_FIELD_LABELS]


def _sync_credits_fields(fields: list[CreditsInputField], values: dict) -> None:
    for f in fields:
        if not f.active:
            f.text = str(values.get(f.key, CREDITS_DEFAULTS.get(f.key, 0)))


def _commit_credits_field(field: CreditsInputField, values: dict) -> bool:
    try:
        val = int(field.text.strip())
        if val < 0:
            return False
        values[field.key] = val
        return True
    except ValueError:
        return False


def _draw_credits_preview(
    surface: pygame.Surface,
    canvas: pygame.Rect,
    values: dict,
    font: pygame.font.Font,
    font_small: pygame.font.Font,
    left_img: Optional[pygame.Surface],
    right_img: Optional[pygame.Surface],
) -> None:
    """Credits maskot önizlemesi – 1366×768 referans ekranda simüle et."""
    REF_W, REF_H = 1366, 768
    scale_x = canvas.w / REF_W
    scale_y = canvas.h / REF_H

    bg = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
    bg.fill((8, 12, 25, 255))
    surface.blit(bg, canvas.topleft)
    pygame.draw.rect(surface, (42, 70, 108), canvas, 1, border_radius=14)

    # Başlık simülasyonu
    title = font.render("EMEĞİ GEÇENLER  (Önizleme)", True, (80, 255, 200))
    surface.blit(title, (canvas.x + 16, canvas.y + 10))

    # Değerler (referans 1366×768'e orantılı ölçekleme)
    s_margin = int(values.get("side_margin", 24) * scale_x)
    s_gap = int(values.get("side_gap", 20) * scale_x)
    s_pw = int(values.get("side_panel_w", 340) * scale_x)
    s_ph = int(values.get("side_panel_h", 300) * scale_y)

    content_top = int(120 * scale_y)
    left_rect = pygame.Rect(canvas.x + s_margin, canvas.y + content_top, s_pw, s_ph)
    right_rect = pygame.Rect(canvas.x + canvas.w - s_margin - s_pw, canvas.y + content_top, s_pw, s_ph)

    # Merkez alan
    center_x = left_rect.right + s_gap
    center_w = right_rect.left - s_gap - center_x
    center_rect = pygame.Rect(center_x, canvas.y + content_top, center_w, s_ph)
    center_fill = pygame.Surface((max(1, center_rect.w), max(1, center_rect.h)), pygame.SRCALPHA)
    center_fill.fill((30, 50, 80, 100))
    surface.blit(center_fill, center_rect.topleft)
    pygame.draw.rect(surface, (80, 120, 180, 160), center_rect, 1, border_radius=8)
    lbl = font_small.render("Merkez İçerik Alanı", True, (160, 190, 230))
    surface.blit(lbl, lbl.get_rect(center=center_rect.center))

    for rect, img, label in [(left_rect, left_img, "Sol Maskot"), (right_rect, right_img, "Sağ Maskot")]:
        # Panel arka planı
        panel_bg = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
        panel_bg.fill((20, 35, 60, 130))
        surface.blit(panel_bg, rect.topleft)
        pygame.draw.rect(surface, (0, 200, 255, 180), rect, 2, border_radius=10)

        if img is not None:
            iw, ih = img.get_size()
            if iw > 0 and ih > 0:
                ratio = rect.h / float(ih)
                dw = max(1, int(iw * ratio))
                dh = max(1, int(ih * ratio))
                if dw > rect.w:
                    ratio2 = rect.w / float(dw)
                    dw = rect.w
                    dh = max(1, int(dh * ratio2))
                try:
                    scaled = pygame.transform.smoothscale(img, (dw, dh))
                except Exception:
                    scaled = pygame.transform.scale(img, (dw, dh))
                surface.blit(scaled, scaled.get_rect(center=rect.center))
        else:
            txt = font_small.render(label, True, (180, 200, 230))
            surface.blit(txt, txt.get_rect(center=rect.center))

        # Boyut etiketi
        size_lbl = font_small.render(f"{values.get('side_panel_w', 0)}×{values.get('side_panel_h', 0)}", True, (120, 200, 255))
        surface.blit(size_lbl, (rect.x + 4, rect.bottom - 20))


def _commit_input_field(field: InputField, panel: Panel) -> bool:
    """Input alanındaki değeri panele uygula. Başarılıysa True döner."""
    try:
        val = int(field.text.strip())
    except ValueError:
        return False
    if field.attr == "x":
        panel.rect.x = max(0, min(val, REFERENCE_W - panel.rect.w))
    elif field.attr == "y":
        panel.rect.y = max(0, min(val, REFERENCE_H - panel.rect.h))
    elif field.attr == "w":
        panel.rect.w = max(MIN_PANEL_SIZE, min(val, REFERENCE_W - panel.rect.x))
    elif field.attr == "h":
        panel.rect.h = max(MIN_PANEL_SIZE, min(val, REFERENCE_H - panel.rect.y))
    return True


def _sync_input_fields(fields: list[InputField], panel: Optional[Panel]) -> None:
    """Aktif olmayan alanları panelin güncel değerleriyle doldur."""
    if panel is None:
        for f in fields:
            if not f.active:
                f.text = ""
        return
    mapping = {"x": panel.rect.x, "y": panel.rect.y, "w": panel.rect.w, "h": panel.rect.h}
    for f in fields:
        if not f.active:
            f.text = str(mapping.get(f.attr, 0))


# ---------------------------------------------------------------------------
# Ana editör döngüsü
# ---------------------------------------------------------------------------
def main() -> None:
    pygame.init()
    pygame.display.set_caption("Menu Layout Editor – Referans: 1920×1080")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("segoeui", 20)
    font_small = pygame.font.SysFont("segoeui", 16)
    font_input = pygame.font.SysFont("consolas", 16)

    # Sekme sistemi: 0 = Ana Menü, 1 = Emeği Geçenler
    active_tab = 0
    TAB_LABELS = ["Ana Menü", "Emeği Geçenler"]
    tab_rects: list[pygame.Rect] = []

    panels = load_layout()
    selected_idx = 0 if panels else -1
    selected_set: set[int] = set()          # çoklu seçim indexleri

    # Sürükleme durumu – referans uzayda
    drag_mode: Optional[str] = None         # "move" | "resize" | "lasso"
    active_handle: Optional[str] = None
    guides: list[tuple[str, int]] = []
    status_text = "Hazır"

    # Lasso (çoklu seçim kutusu)
    lasso_start_screen: Optional[tuple[int, int]] = None
    lasso_current_screen: Optional[tuple[int, int]] = None

    # Çoklu sürükleme offset'leri  {panel_index: (dx_ref, dy_ref)}
    multi_drag_offsets: dict[int, tuple[float, float]] = {}
    linked_child_bindings: dict[int, tuple[int, float, float, float, float]] = {}

    # Sidebar input alanları
    input_fields = _make_input_fields()
    sidebar_buttons: list[SideButton] = []

    # Undo/Redo geçmişi
    history: list[list[Panel]] = [_clone_panels(panels)]
    history_index = 0
    drag_changed = False

    # Önizleme modu
    preview_mode = False
    ingame_preview_enabled = False
    ingame_preview_renderer = _InGameMenuPreviewRenderer()

    # ---- Credits Tab State ----
    credits_values = load_credits_layout()
    credits_fields = _make_credits_input_fields()
    credits_status = "Hazır"
    credits_btn_rects: dict[str, pygame.Rect] = {}  # "save", "reset"
    # Maskot görsellerini yükle
    _credits_left_img: Optional[pygame.Surface] = None
    _credits_right_img: Optional[pygame.Surface] = None
    for p in [ROOT_DIR / "assets" / "maskot" / "emegi_gecen_l.png",
              ROOT_DIR / "assets" / "maskot" / "sos_maskot.png"]:
        if p.exists():
            try:
                _credits_left_img = pygame.image.load(str(p)).convert_alpha()
            except Exception:
                pass
            break
    for p in [ROOT_DIR / "assets" / "maskot" / "emegi_gecen_r.png",
              ROOT_DIR / "assets" / "maskot" / "sos_maskotold.png"]:
        if p.exists():
            try:
                _credits_right_img = pygame.image.load(str(p)).convert_alpha()
            except Exception:
                pass
            break

    running = True
    while running:
        win_w, win_h = screen.get_size()
        canvas, sidebar, scale = _compute_canvas_layout(win_w, win_h)

        # Panelleri referans sınıra clamp
        for panel in panels:
            panel.rect = _clamp_to_reference(panel.rect)

        # Input alanlarını seçili panelin değerleriyle senkronla
        sel_panel = panels[selected_idx] if 0 <= selected_idx < len(panels) else None
        _sync_input_fields(input_fields, sel_panel)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ---- Sekme tıklaması ----
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for ti, tr in enumerate(tab_rects):
                    if tr.collidepoint(event.pos):
                        active_tab = ti
                        # Credits alanlarına tıklandıysa input'u kapat
                        for f in credits_fields:
                            f.active = False
                        break

            # ---- Klavye: input alanı aktifse oraya yönlendir ----
            elif event.type == pygame.KEYDOWN:
                # Credits sekmesi input alanları
                active_credits_field = next((f for f in credits_fields if f.active), None)
                if active_tab == 1 and active_credits_field is not None:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        _commit_credits_field(active_credits_field, credits_values)
                        active_credits_field.active = False
                        credits_status = "Değer güncellendi"
                    elif event.key == pygame.K_ESCAPE:
                        active_credits_field.active = False
                    elif event.key == pygame.K_BACKSPACE:
                        active_credits_field.text = active_credits_field.text[:-1]
                    elif event.key == pygame.K_TAB:
                        _commit_credits_field(active_credits_field, credits_values)
                        active_credits_field.active = False
                        ci = credits_fields.index(active_credits_field)
                        next_ci = (ci + 1) % len(credits_fields)
                        credits_fields[next_ci].active = True
                        credits_fields[next_ci].text = ""
                    elif event.key == pygame.K_s:
                        _commit_credits_field(active_credits_field, credits_values)
                        active_credits_field.active = False
                        save_credits_layout(credits_values)
                        credits_status = f"Kaydedildi → {CREDITS_LAYOUT_FILE.name}"
                    else:
                        pass
                    continue

                active_field = next((f for f in input_fields if f.active), None)
                if active_field is not None:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        if sel_panel:
                            if _commit_input_field(active_field, sel_panel):
                                parent_targets = {selected_idx} if selected_idx >= 0 else set()
                                bindings = _capture_linked_child_state(panels, parent_targets, excluded_indices=parent_targets)
                                _apply_linked_child_state(panels, bindings)
                                history_index = _push_history_state(history, history_index, panels)
                        active_field.active = False
                    elif event.key == pygame.K_ESCAPE:
                        active_field.active = False
                    elif event.key == pygame.K_BACKSPACE:
                        active_field.text = active_field.text[:-1]
                    elif event.key == pygame.K_TAB:
                        # Sonraki alana geç
                        if sel_panel:
                            if _commit_input_field(active_field, sel_panel):
                                parent_targets = {selected_idx} if selected_idx >= 0 else set()
                                bindings = _capture_linked_child_state(panels, parent_targets, excluded_indices=parent_targets)
                                _apply_linked_child_state(panels, bindings)
                                history_index = _push_history_state(history, history_index, panels)
                        active_field.active = False
                        idx_in_fields = input_fields.index(active_field)
                        next_idx = (idx_in_fields + 1) % len(input_fields)
                        input_fields[next_idx].active = True
                        input_fields[next_idx].text = ""
                    else:
                        continue  # Diğer tuşları yut (aşağıdaki kısayolları tetiklemesin)
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    preview_mode = not preview_mode
                    status_text = "Önizleme açık" if preview_mode else "Önizleme kapalı"
                elif event.key == pygame.K_i:
                    ingame_preview_enabled = not ingame_preview_enabled
                    if ingame_preview_enabled:
                        preview_mode = True
                    status_text = "Oyun içi çizim açık" if ingame_preview_enabled else "Oyun içi çizim kapalı"
                elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if history_index > 0:
                        history_index -= 1
                        panels = _clone_panels(history[history_index])
                        selected_idx, selected_set = _sanitize_selection(selected_idx, selected_set, panels)
                        status_text = "Geri alındı"
                elif event.key == pygame.K_y and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if history_index < len(history) - 1:
                        history_index += 1
                        panels = _clone_panels(history[history_index])
                        selected_idx, selected_set = _sanitize_selection(selected_idx, selected_set, panels)
                        status_text = "İleri alındı"
                elif event.key == pygame.K_s:
                    save_layout(panels)
                    status_text = f"Kaydedildi → {LAYOUT_FILE.name}"
                elif event.key == pygame.K_l:
                    panels = load_layout()
                    selected_idx = min(selected_idx, len(panels) - 1)
                    selected_set.clear()
                    history_index = _push_history_state(history, history_index, panels)
                    status_text = "Düzen yüklendi"
                elif event.key == pygame.K_r:
                    panels = _default_panels()
                    selected_idx = 0
                    selected_set.clear()
                    history_index = _push_history_state(history, history_index, panels)
                    status_text = "Varsayılan düzen geri yüklendi"
                elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    # Ctrl+A: tümünü seç
                    selected_set = set(range(len(panels)))
                    if panels:
                        selected_idx = 0
                    status_text = f"{len(panels)} panel seçildi"
                elif selected_idx >= 0 and panels:
                    step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                    moved = False
                    dx, dy = 0, 0
                    if event.key == pygame.K_LEFT:
                        dx = -step; moved = True
                    elif event.key == pygame.K_RIGHT:
                        dx = step; moved = True
                    elif event.key == pygame.K_UP:
                        dy = -step; moved = True
                    elif event.key == pygame.K_DOWN:
                        dy = step; moved = True

                    if moved:
                        targets = selected_set if selected_set else {selected_idx}
                        bindings = _capture_linked_child_state(panels, set(targets), excluded_indices=set(targets))
                        for ti in targets:
                            if 0 <= ti < len(panels):
                                panels[ti].rect.x += dx
                                panels[ti].rect.y += dy
                                panels[ti].rect = _clamp_to_reference(panels[ti].rect)
                        _apply_linked_child_state(panels, bindings)
                        history_index = _push_history_state(history, history_index, panels)

            elif event.type == pygame.TEXTINPUT:
                # Credits sekmesi text input
                active_credits_field = next((f for f in credits_fields if f.active), None)
                if active_tab == 1 and active_credits_field is not None:
                    for ch in event.text:
                        if ch.isdigit():
                            active_credits_field.text += ch
                    continue
                active_field = next((f for f in input_fields if f.active), None)
                if active_field is not None:
                    # Sadece rakam ve eksi kabul et
                    for ch in event.text:
                        if ch.isdigit() or (ch == '-' and not active_field.text):
                            active_field.text += ch

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                # ---- Credits sekmesi mouse handling ----
                if active_tab == 1:
                    # Credits input alanlarına tıklama
                    clicked_credits = False
                    for f in credits_fields:
                        if f.rect.collidepoint(pos):
                            for of in credits_fields:
                                if of.active and of is not f:
                                    _commit_credits_field(of, credits_values)
                                of.active = False
                            f.active = True
                            f.text = ""
                            clicked_credits = True
                            credits_status = "Değer gir, Enter ile onayla"
                            break
                    if not clicked_credits:
                        # Aktif alanı kapat + değeri uygula
                        for f in credits_fields:
                            if f.active:
                                _commit_credits_field(f, credits_values)
                                credits_status = "Değer güncellendi"
                            f.active = False
                        # Kaydet / Sıfırla butonlarına tıklama
                        if credits_btn_rects.get("save") and credits_btn_rects["save"].collidepoint(pos):
                            save_credits_layout(credits_values)
                            credits_status = f"Kaydedildi → {CREDITS_LAYOUT_FILE.name}"
                        elif credits_btn_rects.get("reset") and credits_btn_rects["reset"].collidepoint(pos):
                            credits_values.update(CREDITS_DEFAULTS.copy())
                            credits_status = "Varsayılana sıfırlandı"
                    continue

                # Sidebar input alanlarına tıklama
                if sidebar.w > 0 and sidebar.collidepoint(pos):
                    clicked_button = next((b for b in sidebar_buttons if b.rect.collidepoint(pos)), None)
                    if clicked_button is not None:
                        if clicked_button.action == "undo":
                            if history_index > 0:
                                history_index -= 1
                                panels = _clone_panels(history[history_index])
                                selected_idx, selected_set = _sanitize_selection(selected_idx, selected_set, panels)
                                status_text = "Geri alındı"
                        elif clicked_button.action == "redo":
                            if history_index < len(history) - 1:
                                history_index += 1
                                panels = _clone_panels(history[history_index])
                                selected_idx, selected_set = _sanitize_selection(selected_idx, selected_set, panels)
                                status_text = "İleri alındı"
                        elif clicked_button.action == "toggle_preview":
                            preview_mode = not preview_mode
                            status_text = "Önizleme açık" if preview_mode else "Önizleme kapalı"
                        elif clicked_button.action == "toggle_ingame_preview":
                            ingame_preview_enabled = not ingame_preview_enabled
                            if ingame_preview_enabled:
                                preview_mode = True
                            status_text = "Oyun içi çizim açık" if ingame_preview_enabled else "Oyun içi çizim kapalı"
                        continue

                    clicked_field = False
                    for f in input_fields:
                        if f.rect.collidepoint(pos):
                            # Önceki aktif alanı commit et
                            for of in input_fields:
                                if of.active and of is not f and sel_panel:
                                    if _commit_input_field(of, sel_panel):
                                        parent_targets = {selected_idx} if selected_idx >= 0 else set()
                                        bindings = _capture_linked_child_state(panels, parent_targets, excluded_indices=parent_targets)
                                        _apply_linked_child_state(panels, bindings)
                                        history_index = _push_history_state(history, history_index, panels)
                                of.active = False
                            f.active = True
                            f.text = ""  # Temizle, yeni değer girişi için
                            clicked_field = True
                            break
                    if not clicked_field:
                        # Sidebar'da ama input'a değil → commit & deactivate
                        for f in input_fields:
                            if f.active and sel_panel:
                                if _commit_input_field(f, sel_panel):
                                    parent_targets = {selected_idx} if selected_idx >= 0 else set()
                                    bindings = _capture_linked_child_state(panels, parent_targets, excluded_indices=parent_targets)
                                    _apply_linked_child_state(panels, bindings)
                                    history_index = _push_history_state(history, history_index, panels)
                            f.active = False
                    continue

                if preview_mode:
                    continue

                # Input alanlarını deactive et (canvas'a tıklandı)
                for f in input_fields:
                    if f.active and sel_panel:
                        if _commit_input_field(f, sel_panel):
                            parent_targets = {selected_idx} if selected_idx >= 0 else set()
                            bindings = _capture_linked_child_state(panels, parent_targets, excluded_indices=parent_targets)
                            _apply_linked_child_state(panels, bindings)
                            history_index = _push_history_state(history, history_index, panels)
                    f.active = False

                guides.clear()
                drag_mode = None
                active_handle = None
                lasso_start_screen = None
                lasso_current_screen = None
                linked_child_bindings = {}

                # Seçili panelin ekran-tutamaçlarına bak
                if selected_idx >= 0 and 0 <= selected_idx < len(panels):
                    scr_rect = _ref_rect_to_screen(panels[selected_idx].rect, canvas, scale)
                    handles = _get_handles_screen(scr_rect)
                    for hk, hr in handles.items():
                        if hr.collidepoint(pos):
                            drag_mode = "resize"
                            active_handle = hk
                            drag_changed = False
                            parent_targets = {selected_idx}
                            linked_child_bindings = _capture_linked_child_state(
                                panels,
                                parent_targets,
                                excluded_indices=parent_targets,
                            )
                            break

                if drag_mode != "resize":
                    # Panel seçimi (üstten alta)
                    clicked_idx = -1
                    for idx in range(len(panels) - 1, -1, -1):
                        scr_r = _ref_rect_to_screen(panels[idx].rect, canvas, scale)
                        if scr_r.collidepoint(pos):
                            clicked_idx = idx
                            break

                    if clicked_idx >= 0:
                        ctrl_held = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)
                        if ctrl_held:
                            # Ctrl+tıklama: çoklu seçime ekle/çıkar
                            if clicked_idx in selected_set:
                                selected_set.discard(clicked_idx)
                                if selected_idx == clicked_idx:
                                    selected_idx = min(selected_set) if selected_set else -1
                            else:
                                selected_set.add(clicked_idx)
                                selected_idx = clicked_idx
                        else:
                            selected_idx = clicked_idx
                            selected_set = {clicked_idx}

                        drag_mode = "move"
                        drag_changed = False
                        ref_pos = _screen_to_ref(pos[0], pos[1], canvas, scale)

                        # Çoklu seçim için offset'leri hazırla
                        move_targets = selected_set if selected_set else {selected_idx}
                        linked_child_bindings = _capture_linked_child_state(
                            panels,
                            set(move_targets),
                            excluded_indices=set(move_targets),
                        )
                        multi_drag_offsets.clear()
                        for ti in move_targets:
                            if 0 <= ti < len(panels):
                                pr = panels[ti].rect
                                multi_drag_offsets[ti] = (ref_pos[0] - pr.x, ref_pos[1] - pr.y)
                    else:
                        # Boşluğa tıklandı → lasso başlat
                        if not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                            selected_set.clear()
                            selected_idx = -1
                        drag_mode = "lasso"
                        lasso_start_screen = pos
                        lasso_current_screen = pos

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if drag_mode == "lasso" and lasso_start_screen and lasso_current_screen:
                    # Lasso dikdörtgenini referans uzayına çevir ve kesişen panelleri seç
                    sx1, sy1 = lasso_start_screen
                    sx2, sy2 = lasso_current_screen
                    lx = min(sx1, sx2)
                    ly = min(sy1, sy2)
                    lw = abs(sx2 - sx1)
                    lh = abs(sy2 - sy1)
                    if lw > 4 and lh > 4:  # Min 4px sürükleme – kazara tıklama olmasın
                        lasso_screen_rect = pygame.Rect(lx, ly, lw, lh)
                        for idx, panel in enumerate(panels):
                            scr_r = _ref_rect_to_screen(panel.rect, canvas, scale)
                            if lasso_screen_rect.colliderect(scr_r):
                                selected_set.add(idx)
                        if selected_set:
                            selected_idx = min(selected_set)
                            status_text = f"{len(selected_set)} panel seçildi"

                if drag_mode in ("move", "resize") and drag_changed:
                    history_index = _push_history_state(history, history_index, panels)

                drag_mode = None
                active_handle = None
                lasso_start_screen = None
                lasso_current_screen = None
                multi_drag_offsets.clear()
                linked_child_bindings.clear()
                guides.clear()
                drag_changed = False

            elif event.type == pygame.MOUSEMOTION:
                if drag_mode == "lasso":
                    lasso_current_screen = event.pos

                elif drag_mode == "move" and multi_drag_offsets:
                    ref_x, ref_y = _screen_to_ref(event.pos[0], event.pos[1], canvas, scale)
                    guides.clear()

                    for ti, (ox, oy) in multi_drag_offsets.items():
                        if 0 <= ti < len(panels):
                            trial = panels[ti].rect.copy()
                            trial.x = int(ref_x - ox)
                            trial.y = int(ref_y - oy)
                            trial = _clamp_to_reference(trial)
                            # Tek seçimdeyse snap uygula
                            if len(multi_drag_offsets) == 1:
                                x_cands, y_cands = _collect_snap_candidates(panels, ti)
                                snapped, guides = _snap_rect(trial, x_cands, y_cands)
                                new_rect = _clamp_to_reference(snapped)
                                if new_rect != panels[ti].rect:
                                    drag_changed = True
                                panels[ti].rect = new_rect
                            else:
                                if trial != panels[ti].rect:
                                    drag_changed = True
                                panels[ti].rect = trial

                    if _apply_linked_child_state(panels, linked_child_bindings):
                        drag_changed = True

                elif drag_mode == "resize" and active_handle and selected_idx >= 0:
                    ref_x, ref_y = _screen_to_ref(event.pos[0], event.pos[1], canvas, scale)
                    panel = panels[selected_idx]
                    x_cands, y_cands = _collect_snap_candidates(panels, selected_idx)
                    guides.clear()

                    r = panel.rect
                    left, right = r.left, r.right
                    top, bottom = r.top, r.bottom
                    mx, my = int(ref_x), int(ref_y)

                    if "w" in active_handle:
                        left = min(mx, right - MIN_PANEL_SIZE)
                    if "e" in active_handle:
                        right = max(mx, left + MIN_PANEL_SIZE)
                    if "n" in active_handle:
                        top = min(my, bottom - MIN_PANEL_SIZE)
                    if "s" in active_handle:
                        bottom = max(my, top + MIN_PANEL_SIZE)

                    trial = pygame.Rect(left, top, max(MIN_PANEL_SIZE, right - left), max(MIN_PANEL_SIZE, bottom - top))
                    trial = _clamp_to_reference(trial)
                    snapped, guides = _snap_resize_rect(trial, active_handle, x_cands, y_cands)
                    new_rect = _clamp_to_reference(snapped)
                    if new_rect != panel.rect:
                        drag_changed = True
                    panel.rect = new_rect
                    if _apply_linked_child_state(panels, linked_child_bindings):
                        drag_changed = True

        # ====================== ÇİZİM ======================
        screen.fill(BG_COLOR)

        # ---- Sekme çubuğu ----
        tab_bar_h = 36
        tab_w = 180
        tab_bar_y = 6
        tab_rects = []
        for ti, label in enumerate(TAB_LABELS):
            tx = 20 + ti * (tab_w + 6)
            tr = pygame.Rect(tx, tab_bar_y, tab_w, tab_bar_h)
            tab_rects.append(tr)
            is_active = (ti == active_tab)
            bg_col = (30, 55, 95) if is_active else (16, 28, 48)
            border_col = (0, 190, 255) if is_active else (55, 85, 125)
            pygame.draw.rect(screen, bg_col, tr, border_radius=8)
            pygame.draw.rect(screen, border_col, tr, 2 if is_active else 1, border_radius=8)
            lbl = font.render(label, True, (220, 235, 255) if is_active else MUTED_TEXT)
            screen.blit(lbl, lbl.get_rect(center=tr.center))

        # Canvas'ı sekme çubuğunun altına kaydır
        tab_offset_y = tab_bar_h + 10
        canvas = pygame.Rect(canvas.x, canvas.y + tab_offset_y, canvas.w, canvas.h - tab_offset_y)
        sidebar = pygame.Rect(sidebar.x, sidebar.y + tab_offset_y, sidebar.w, sidebar.h - tab_offset_y)

        # ---- Emeği Geçenler Sekmesi ----
        if active_tab == 1:
            _sync_credits_fields(credits_fields, credits_values)
            _draw_credits_preview(screen, canvas, credits_values, font, font_small,
                                  _credits_left_img, _credits_right_img)

            # Sidebar – Credits
            if sidebar.w > 0:
                side_bg = pygame.Surface(sidebar.size, pygame.SRCALPHA)
                side_bg.fill((12, 20, 36, 220))
                screen.blit(side_bg, sidebar.topleft)
                pygame.draw.rect(screen, (55, 90, 135), sidebar, 1, border_radius=12)

                cy = sidebar.y + 12
                _draw_text(screen, "Maskot Boyutları", (sidebar.x + 14, cy), font)
                cy += 28
                _draw_text(screen, "Değerler 1366×768 ekrana", (sidebar.x + 14, cy), font_small, MUTED_TEXT)
                cy += 18
                _draw_text(screen, "göreli ölçeklenir.", (sidebar.x + 14, cy), font_small, MUTED_TEXT)
                cy += 26

                field_w = max(70, sidebar.w - 60)
                for f in credits_fields:
                    lbl_surf = font_small.render(f.label + ":", True, MUTED_TEXT)
                    screen.blit(lbl_surf, (sidebar.x + 14, cy))
                    cy += 18
                    f.rect = pygame.Rect(sidebar.x + 14, cy, field_w, 24)
                    bg = INPUT_BG_ACTIVE if f.active else INPUT_BG
                    border = INPUT_BORDER_ACTIVE if f.active else INPUT_BORDER
                    pygame.draw.rect(screen, bg, f.rect, border_radius=4)
                    pygame.draw.rect(screen, border, f.rect, 1, border_radius=4)
                    txt_surf = font_input.render(f.text, True, INPUT_TEXT)
                    screen.blit(txt_surf, txt_surf.get_rect(midleft=(f.rect.x + 4, f.rect.centery)))
                    if f.active and (pygame.time.get_ticks() // 500) % 2 == 0:
                        cx2 = f.rect.x + 4 + txt_surf.get_width() + 2
                        pygame.draw.line(screen, INPUT_TEXT, (cx2, f.rect.y + 3), (cx2, f.rect.bottom - 3), 1)
                    cy += 30

                cy += 8
                # Kaydet butonu
                save_btn = pygame.Rect(sidebar.x + 14, cy, max(100, sidebar.w - 28), 30)
                credits_btn_rects["save"] = save_btn
                mouse_pos = pygame.mouse.get_pos()
                is_hover_save = save_btn.collidepoint(mouse_pos)
                pygame.draw.rect(screen, BUTTON_BG_HOVER if is_hover_save else BUTTON_BG, save_btn, border_radius=6)
                pygame.draw.rect(screen, (0, 190, 120), save_btn, 1, border_radius=6)
                save_lbl = font_small.render("S – Kaydet (credits_layout.json)", True, BUTTON_TEXT)
                screen.blit(save_lbl, save_lbl.get_rect(center=save_btn.center))
                # Kaydet butonuna tıklama
                if is_hover_save:
                    # Tek frame hover; tıklamayı credits MOUSEBUTTONDOWN ile zaten handle ediyoruz.
                    # Ek olarak direkt click detect:
                    pass
                cy += 38

                # Sıfırla butonu
                reset_btn = pygame.Rect(sidebar.x + 14, cy, max(100, sidebar.w - 28), 28)
                credits_btn_rects["reset"] = reset_btn
                is_hover_reset = reset_btn.collidepoint(mouse_pos)
                pygame.draw.rect(screen, BUTTON_BG_HOVER if is_hover_reset else BUTTON_BG, reset_btn, border_radius=6)
                pygame.draw.rect(screen, BUTTON_BORDER, reset_btn, 1, border_radius=6)
                reset_lbl = font_small.render("Varsayılana Sıfırla", True, BUTTON_TEXT)
                screen.blit(reset_lbl, reset_lbl.get_rect(center=reset_btn.center))
                cy += 36

                cy += 10
                _draw_text(screen, "İpuçları:", (sidebar.x + 14, cy), font_small, MUTED_TEXT)
                cy += 20
                for tip in ["• Alana tıkla → değer gir", "• Enter: onayla", "• Tab: sonraki alan",
                            "• S: kaydet", "• Anlık önizleme solda"]:
                    _draw_text(screen, tip, (sidebar.x + 14, cy), font_small, MUTED_TEXT)
                    cy += 18

                status_surf = font_small.render(credits_status, True, (170, 230, 200))
                screen.blit(status_surf, (sidebar.x + 14, sidebar.bottom - 30))

        else:
            # ---- Ana Menü Sekmesi ----
            if preview_mode:
                if ingame_preview_enabled:
                    _ = ingame_preview_renderer.draw(screen, canvas, panels, font, font_small, scale)
                else:
                    _draw_preview(screen, canvas, panels, font, font_small, scale)
            else:
                # Canvas arka planı
                pygame.draw.rect(screen, (16, 26, 45), canvas, border_radius=14)
                pygame.draw.rect(screen, (40, 75, 115), canvas, 1, border_radius=14)
                _draw_grid(screen, canvas, scale)
                _draw_screen_frame(screen, canvas)
                _draw_guides(screen, guides, canvas, scale)

                # Panelleri çiz
                for idx, panel in enumerate(panels):
                    scr = _ref_rect_to_screen(panel.rect, canvas, scale)
                    is_in_multi = idx in selected_set
                    is_primary = idx == selected_idx

                    fill = pygame.Surface(scr.size, pygame.SRCALPHA)
                    fill_alpha = PANEL_FILL_ALPHA + (30 if is_in_multi else 0)
                    fill.fill((*panel.color, min(255, fill_alpha)))
                    screen.blit(fill, scr.topleft)

                    border_alpha = PANEL_BORDER_ALPHA if (is_primary or is_in_multi) else 160
                    pygame.draw.rect(screen, (*panel.color, border_alpha), scr, 2, border_radius=12)

                    label_text = panel.title if scr.w >= 120 and scr.h >= 54 else panel.key
                    title_surf = font_small.render(label_text, True, TEXT_COLOR)
                    screen.blit(title_surf, (scr.x + 8, scr.y + 6))

                    size_label = font_small.render(f"{panel.rect.w}×{panel.rect.h}", True, MUTED_TEXT)
                    screen.blit(size_label, (scr.x + 10, scr.bottom - 24))

                    if is_primary:
                        pygame.draw.rect(screen, SELECT_BORDER, scr, 1, border_radius=12)
                        handles = _get_handles_screen(scr)
                        for h_rect in handles.values():
                            pygame.draw.rect(screen, (235, 245, 255), h_rect, border_radius=3)
                            pygame.draw.rect(screen, (35, 50, 80), h_rect, 1, border_radius=3)
                    elif is_in_multi:
                        # Çoklu seçimdeki diğer paneller: kesikli beyaz çerçeve
                        pygame.draw.rect(screen, (200, 220, 255, 180), scr, 1, border_radius=12)

        # Lasso seçim kutusu çiz (sadece ana menü sekmesinde)
        if active_tab == 0 and drag_mode == "lasso" and lasso_start_screen and lasso_current_screen:
            sx1, sy1 = lasso_start_screen
            sx2, sy2 = lasso_current_screen
            lx = min(sx1, sx2)
            ly = min(sy1, sy2)
            lw = abs(sx2 - sx1)
            lh = abs(sy2 - sy1)
            if lw > 2 and lh > 2:
                lasso_surf = pygame.Surface((lw, lh), pygame.SRCALPHA)
                lasso_surf.fill(SELECT_BOX_COLOR)
                screen.blit(lasso_surf, (lx, ly))
                pygame.draw.rect(screen, SELECT_BOX_BORDER, (lx, ly, lw, lh), 1)

        # Sidebar – sadece Ana Menü sekmesinde (Credits sekmesi kendi sidebar'ını çiziyor)
        if active_tab == 0:
          if sidebar.w > 0:
            side_bg = pygame.Surface(sidebar.size, pygame.SRCALPHA)
            side_bg.fill((12, 20, 36, 220))
            screen.blit(side_bg, sidebar.topleft)
            pygame.draw.rect(screen, (55, 90, 135), sidebar, 1, border_radius=12)

            _draw_text(screen, "Menu Layout Editor", (sidebar.x + 14, sidebar.y + 12), font)
            _draw_text(screen, f"Referans: {REFERENCE_W}×{REFERENCE_H}", (sidebar.x + 14, sidebar.y + 38), font_small, MUTED_TEXT)
            _draw_text(screen, f"Ölçek: {scale:.2f}x", (sidebar.x + 14, sidebar.y + 58), font_small, MUTED_TEXT)

            y = sidebar.y + 82
            tips = [
                "• Sürükle: taşı",
                "• Beyaz noktalar: boyutlandır",
                "• Boşlukta sürükle: çoklu seç",
                "• Ctrl+tık: seçime ekle/çıkar",
                "• Ctrl+A: tümünü seç",
                "• Ctrl+Z / Ctrl+Y: geri/ileri",
                "• P: önizleme aç/kapat",
                "• I: oyun içi çizim aç/kapat",
                "• S: kaydet   L: yükle",
                f"• Çıktı: {RUNTIME_LAYOUT_FILE.name}",
                "• R: varsayılan   Esc: çık",
            ]
            for tip in tips:
                _draw_text(screen, tip, (sidebar.x + 14, y), font_small, MUTED_TEXT)
                y += 22

            # ---- Hızlı butonlar ----
            y += 4
            btn_w = max(140, sidebar.w - 28)
            sidebar_buttons = _make_sidebar_buttons(sidebar, y, btn_w)
            mouse_pos = pygame.mouse.get_pos()
            for b in sidebar_buttons:
                is_hover = b.rect.collidepoint(mouse_pos)
                is_active = (
                    (b.action == "toggle_preview" and preview_mode)
                    or (b.action == "toggle_ingame_preview" and ingame_preview_enabled)
                )
                _draw_side_button(screen, b, font_small, is_hover, is_active)
            y = sidebar_buttons[-1].rect.bottom + 14

            # ---- Seçili Panel Boyut Girişi ----
            if sel_panel:
                _draw_text(screen, f"Seçili: {sel_panel.key}", (sidebar.x + 14, y), font_small)
                y += 24
                field_w = min(70, (sidebar.w - 90) // 2)
                col2_x = sidebar.x + 14 + 40 + field_w + 16  # ikinci sütun
                for fi, field in enumerate(input_fields):
                    fx = sidebar.x + 54 if fi % 2 == 0 else col2_x + 40
                    fy = y
                    if fi % 2 == 0 and fi > 0:
                        y += 30
                        fy = y
                    field.rect = pygame.Rect(fx, fy, field_w, 22)

                    # Label
                    label_surf = font_input.render(field.label + ":", True, MUTED_TEXT)
                    screen.blit(label_surf, (fx - 26, fy + 2))

                    # Input kutusu
                    bg = INPUT_BG_ACTIVE if field.active else INPUT_BG
                    border = INPUT_BORDER_ACTIVE if field.active else INPUT_BORDER
                    pygame.draw.rect(screen, bg, field.rect, border_radius=4)
                    pygame.draw.rect(screen, border, field.rect, 1, border_radius=4)

                    # Metin
                    txt_surf = font_input.render(field.text, True, INPUT_TEXT)
                    txt_rect = txt_surf.get_rect(midleft=(field.rect.x + 4, field.rect.centery))
                    screen.blit(txt_surf, txt_rect)

                    # Cursor (aktifse)
                    if field.active:
                        cursor_x = txt_rect.right + 2
                        if (pygame.time.get_ticks() // 500) % 2 == 0:
                            pygame.draw.line(screen, INPUT_TEXT, (cursor_x, field.rect.y + 3), (cursor_x, field.rect.bottom - 3), 1)

                y += 32
                dx, dy, centered_x, centered_y = _get_center_delta(sel_panel)
                center_x_text = "Merkez X: ✓" if centered_x else f"Merkez X: {dx:+d}px"
                center_y_text = "Merkez Y: ✓" if centered_y else f"Merkez Y: {dy:+d}px"
                center_col = (140, 240, 190) if centered_x else MUTED_TEXT
                _draw_text(screen, center_x_text, (sidebar.x + 14, y), font_small, center_col)
                y += 20
                _draw_text(screen, center_y_text, (sidebar.x + 14, y), font_small, MUTED_TEXT)
                y += 16
                if len(selected_set) > 1:
                    _draw_text(screen, f"({len(selected_set)} panel seçili)", (sidebar.x + 14, y), font_small, MUTED_TEXT)
                    y += 22
            else:
                _draw_text(screen, "Panel seçili değil", (sidebar.x + 14, y), font_small, MUTED_TEXT)
                y += 24

            # ---- Panel Listesi ----
            y += 10
            _draw_text(screen, "Paneller", (sidebar.x + 14, y), font_small)
            y += 26
            for idx, panel in enumerate(panels):
                is_primary_list = idx == selected_idx
                is_in_set = idx in selected_set
                if is_primary_list:
                    marker = "▶"
                    col = TEXT_COLOR
                elif is_in_set:
                    marker = "●"
                    col = (160, 210, 255)
                else:
                    marker = "•"
                    col = MUTED_TEXT
                label = f"{marker} {panel.key}"
                _draw_text(screen, label, (sidebar.x + 14, y), font_small, col)
                y += 22
                if y > sidebar.bottom - 40:
                    break

            status = font_small.render(status_text, True, (170, 205, 240))
            screen.blit(status, (sidebar.x + 14, sidebar.bottom - 30))
          else:
            status = font_small.render(status_text, True, (170, 205, 240))
            screen.blit(status, (canvas.x + 10, canvas.bottom - 24))

        # Credits sekmesinde kaydet/sıfırla buton tıklamaları (bu frame click detection)
        if active_tab == 1:
            # Kaydet/Sıfırla butonlarının tıklanması için mouse down detect
            # (Butonlar sidebar içinde çizildi; sidebar'ın içinde tıklama için
            #  MOUSEBUTTONDOWN event'i yukarıda credits tab handle'da halledildi.
            #  Burada reset butonunu ek olarak handle ediyoruz.)
            pass

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
