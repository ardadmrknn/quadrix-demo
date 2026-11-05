"""Shared geometry for local controller-selection lobbies."""

from __future__ import annotations

import pygame


def compute_controller_lobby_layout(width: int, height: int, *, title_bottom: int, scale: float = 1.0) -> dict[str, object]:
    """Return a contained panel and three non-overlapping columns."""
    width = max(1, int(width))
    height = max(1, int(height))
    scale = max(0.5, float(scale))
    s = lambda value: max(1, int(round(float(value) * scale)))
    margin = s(50)
    panel_w = min(s(1000), max(s(300), width - margin * 2))
    panel_top = int(title_bottom) + s(28)
    max_panel_h = max(s(280), height - panel_top - s(82))
    panel_h = min(s(500), max_panel_h)
    panel_h = min(panel_h, max(1, height - panel_top))
    panel = pygame.Rect(width // 2 - panel_w // 2, panel_top, panel_w, panel_h)
    gap = s(10)
    side_pad = s(20)
    available = max(3, panel.width - side_pad * 2 - gap * 2)
    col_w = max(1, available // 3)
    col_h = max(1, panel.height - s(60))
    first_x = panel.x + side_pad
    col_y = panel.y + s(40)
    columns = tuple(
        pygame.Rect(first_x + i * (col_w + gap), col_y, col_w, col_h)
        for i in range(3)
    )
    return {"panel": panel, "columns": columns}
