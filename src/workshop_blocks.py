"""Utility helpers for parsing and sharing Block Workshop data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from constants import BOARD_HEIGHT, BOARD_WIDTH, COLORS
from localization import t
from pieces import EXTRA_COLORS, EXTRA_SHAPE_NAMES, SHAPE_NAMES


# Workshop mode catalog (shared between UI and gameplay)
WORKSHOP_MODES: List[Tuple[str, str]] = [
    ("classic", "mode_label_classic"),
    ("sprint", "mode_label_sprint"),
    ("ultra", "mode_label_ultra"),
    ("zen", "mode_label_zen"),
    ("tetris2", "guide_mode_name_tetris2"),
    ("mystery", "mode_label_card_mastery"),
    ("wide", "mode_label_wide"),
    ("survival", "mode_label_survival"),
    ("cascade", "mode_label_cascade"),
    ("daily", "guide_mode_name_daily"),
]
WORKSHOP_MODE_KEYS: List[str] = [mode for mode, _ in WORKSHOP_MODES]

DEFAULT_PIECE_COLORS: Dict[str, Tuple[int, int, int]] = {
    name: COLORS[idx % len(COLORS)] for idx, name in enumerate(SHAPE_NAMES)
}
DEFAULT_PIECE_COLORS.update({
    name: EXTRA_COLORS[idx % len(EXTRA_COLORS)] for idx, name in enumerate(EXTRA_SHAPE_NAMES)
})


@dataclass(slots=True)
class WorkshopBlockDefinition:
    """Normalized representation of a custom workshop block."""

    identifier: str
    name: str
    shape: List[List[int]]
    color: Tuple[int, int, int]
    modes: List[str]
    cell_count: int
    # Optional per-cell colors for Piece Workshop creations.
    # Keys are local (x,y) coordinates inside the shape matrix.
    cell_colors: Optional[Dict[Tuple[int, int], Tuple[int, int, int]]] = None


def load_workshop_blocks(
    settings_manager,
    *,
    board_width: int = BOARD_WIDTH,
    board_height: int = BOARD_HEIGHT,
) -> List[WorkshopBlockDefinition]:
    """Read workshop board data from settings and convert to block definitions."""

    if not settings_manager:
        return []

    definitions: List[WorkshopBlockDefinition] = []
    saved_sets = settings_manager.get("block_workshop_sets", [])
    if isinstance(saved_sets, list) and saved_sets:
        for idx, entry in enumerate(saved_sets, 1):
            board_data = entry.get("board", []) if isinstance(entry, dict) else []
            board = _deserialize_board(board_data, board_width, board_height)
            modes = _normalize_mode_list(entry.get("modes"))
            default_label = t('block_workshop_set_number', index=idx)
            label = str(entry.get("name", default_label)).strip() or default_label
            prefix = _sanitize_identifier(str(entry.get("id", f"set{idx}")))
            chunk = _extract_definitions(
                board,
                set_prefix=f"{prefix}_" if prefix else "",
                set_label=label,
                allowed_modes=modes,
            )
            definitions.extend(chunk)
    else:
        saved = settings_manager.get("block_workshop_board", [])
        board = _deserialize_board(saved, board_width, board_height)
        definitions = _extract_definitions(board)

    # Also load Piece Workshop custom pieces (if present)
    try:
        definitions.extend(_load_piece_workshop_definitions(settings_manager))
    except Exception as exc:  # pragma: no cover - defensive logging
        print(t('piece_workshop_load_failed', error=exc))
    return definitions


def _load_piece_workshop_definitions(settings_manager) -> List[WorkshopBlockDefinition]:
    raw = settings_manager.get("custom_workshop_pieces", []) if settings_manager else []
    if not isinstance(raw, list) or not raw:
        return []

    definitions: List[WorkshopBlockDefinition] = []
    for idx, entry in enumerate(raw, 1):
        if not isinstance(entry, dict):
            continue
        piece_id = str(entry.get("id", "")).strip()
        shape_cells = entry.get("shape")
        cells = entry.get("cells")
        if not piece_id or not isinstance(shape_cells, list) or not shape_cells:
            continue

        coords: List[Tuple[int, int]] = []
        for item in shape_cells:
            if (
                isinstance(item, (list, tuple))
                and len(item) >= 2
                and isinstance(item[0], int)
                and isinstance(item[1], int)
            ):
                coords.append((int(item[0]), int(item[1])))
        if not coords:
            continue

        max_x = max(x for x, _ in coords)
        max_y = max(y for _, y in coords)
        width = max_x + 1
        height = max_y + 1
        if width <= 0 or height <= 0:
            continue
        matrix = [[0 for _ in range(width)] for _ in range(height)]
        for x, y in coords:
            if 0 <= x < width and 0 <= y < height:
                matrix[y][x] = 1

        # Resolve per-cell colors (Piece Workshop supports multi-color cells).
        # Keep a representative color for fallbacks/effects.
        color = (200, 200, 200)
        cell_colors: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
        if isinstance(cells, list) and cells:
            for item in cells:
                if not isinstance(item, dict):
                    continue
                pos = item.get('pos')
                c = item.get('color')
                if (
                    isinstance(pos, (list, tuple))
                    and len(pos) >= 2
                    and isinstance(pos[0], int)
                    and isinstance(pos[1], int)
                    and isinstance(c, Sequence)
                    and len(c) >= 3
                ):
                    px = int(pos[0])
                    py = int(pos[1])
                    if 0 <= px < width and 0 <= py < height:
                        cell_colors[(px, py)] = tuple(int(max(0, min(255, v))) for v in c[:3])
            if cell_colors:
                # Choose a stable representative color (first in iteration order)
                color = next(iter(cell_colors.values()))

        modes = _normalize_mode_list(entry.get("modes"))
        default_name = t('piece_workshop_custom_name', index=idx)
        name = str(entry.get("name", default_name)).strip() or default_name
        identifier = f"piece_{_sanitize_identifier(piece_id)}"
        definitions.append(
            WorkshopBlockDefinition(
                identifier=identifier,
                name=name,
                shape=matrix,
                color=color,
                cell_colors=cell_colors or None,
                modes=modes,
                cell_count=len(coords),
            )
        )
    return definitions


def _deserialize_board(data: Any, width: int, height: int) -> List[List[Optional[Dict[str, Any]]]]:
    board: List[List[Optional[Dict[str, Any]]]] = [[None for _ in range(width)] for _ in range(height)]
    if not isinstance(data, list):
        return board
    for y, row in enumerate(data):
        if y >= height or not isinstance(row, list):
            continue
        for x, value in enumerate(row):
            if x >= width:
                break
            cell = _parse_cell(value)
            if cell:
                board[y][x] = cell
    return board


def _parse_cell(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, str):
        return {
            "piece": value,
            "color": None,
            "modes": WORKSHOP_MODE_KEYS[:],
        }
    if not isinstance(value, dict):
        return None
    piece = value.get("piece")
    if not isinstance(piece, str):
        return None
    color = value.get("color")
    if isinstance(color, Sequence) and len(color) >= 3:
        sanitized = tuple(int(max(0, min(255, c))) for c in color[:3])
    else:
        sanitized = None
    modes_raw = value.get("modes")
    if isinstance(modes_raw, list):
        filtered = [m for m in WORKSHOP_MODE_KEYS if m in modes_raw]
        modes = filtered if filtered else WORKSHOP_MODE_KEYS[:]
    else:
        modes = WORKSHOP_MODE_KEYS[:]
    return {
        "piece": piece,
        "color": sanitized,
        "modes": modes,
    }


def _extract_definitions(
    board: List[List[Optional[Dict[str, Any]]]],
    *,
    set_prefix: str = "",
    set_label: Optional[str] = None,
    allowed_modes: Optional[List[str]] = None,
) -> List[WorkshopBlockDefinition]:
    height = len(board)
    width = len(board[0]) if height else 0
    visited = [[False for _ in range(width)] for _ in range(height)]
    definitions: List[WorkshopBlockDefinition] = []
    for y in range(height):
        for x in range(width):
            if visited[y][x] or not board[y][x]:
                continue
            cells, bounds = _collect_component(board, x, y, visited)
            if not cells:
                continue
            definition = _build_definition(
                len(definitions) + 1,
                cells,
                bounds,
                set_prefix=set_prefix,
                set_label=set_label,
                allowed_modes=allowed_modes,
            )
            if definition:
                definitions.append(definition)
    return definitions


def _collect_component(
    board: List[List[Optional[Dict[str, Any]]]],
    start_x: int,
    start_y: int,
    visited: List[List[bool]],
):
    stack = [(start_x, start_y)]
    cells: List[Dict[str, Any]] = []
    min_x = max_x = start_x
    min_y = max_y = start_y
    width = len(board[0]) if board else 0
    height = len(board)
    while stack:
        x, y = stack.pop()
        if not (0 <= x < width and 0 <= y < height):
            continue
        if visited[y][x]:
            continue
        visited[y][x] = True
        cell = board[y][x]
        if not cell:
            continue
        record = {"x": x, "y": y, "cell": cell}
        cells.append(record)
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                stack.append((nx, ny))
    bounds = {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
    }
    return cells, bounds


def _build_definition(
    index: int,
    cells: List[Dict[str, Any]],
    bounds: Dict[str, int],
    *,
    set_prefix: str = "",
    set_label: str = "Workshop",
    allowed_modes: Optional[List[str]] = None,
):
    width = bounds["max_x"] - bounds["min_x"] + 1
    height = bounds["max_y"] - bounds["min_y"] + 1
    if width <= 0 or height <= 0:
        return None
    shape = [[0 for _ in range(width)] for _ in range(height)]
    mode_flags = set()
    color = _resolve_color(cells)
    for info in cells:
        rel_x = info["x"] - bounds["min_x"]
        rel_y = info["y"] - bounds["min_y"]
        if 0 <= rel_x < width and 0 <= rel_y < height:
            shape[rel_y][rel_x] = 1
        mode_flags.update(info["cell"].get("modes", []))
    ordered_modes = [mode for mode in WORKSHOP_MODE_KEYS if mode in mode_flags]
    if not ordered_modes:
        ordered_modes = WORKSHOP_MODE_KEYS[:]
    if allowed_modes is not None:
        ordered_modes = [mode for mode in ordered_modes if mode in allowed_modes]
        if not ordered_modes:
            return None
    identifier_prefix = set_prefix if set_prefix else ""
    identifier = f"{identifier_prefix}workshop_{index}"
    pretty_label = set_label or t('block_workshop_default_set')
    name = t('block_workshop_block_name', label=pretty_label, index=index)
    return WorkshopBlockDefinition(
        identifier=identifier,
        name=name,
        shape=shape,
        color=color,
        modes=ordered_modes,
        cell_count=len(cells),
    )


def _resolve_color(cells: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    for info in cells:
        custom = info["cell"].get("color")
        if isinstance(custom, Sequence) and len(custom) >= 3:
            return tuple(int(max(0, min(255, c))) for c in custom[:3])
    piece_name = cells[0]["cell"].get("piece") if cells else None
    return DEFAULT_PIECE_COLORS.get(piece_name, (200, 200, 200))


def _normalize_mode_list(raw: Any) -> List[str]:
    """Mod listesini normalize et. Boş liste = hiçbir modda çıkmaz."""
    if isinstance(raw, list):
        return [mode for mode in WORKSHOP_MODE_KEYS if mode in raw]
    # Geriye dönük uyumluluk: modes tanımlı değilse (eski parçalar) tüm modlar
    return WORKSHOP_MODE_KEYS[:]


def _sanitize_identifier(raw: str) -> str:
    cleaned = [ch for ch in raw.lower() if ch.isalnum() or ch in ("_", "-")]
    return "".join(cleaned)[:32]
