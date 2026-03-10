"""Tutorial senaryo verisi ve evaluator yardimcilari.

Bu modul pygame runtime'ina bagimli olmadan tutorial board dersleri icin
senaryo tanimlarini ve board metrik hesaplamalarini sunar.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

try:
    from .localization import t  # type: ignore
except Exception:
    from localization import t


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "gap_fill_double": {
        "goal_key": "tutorial_board_gap_fill_goal",
        "board_rows": [
            "XXXX..XXXX",
            "XXXX..XXXX",
        ],
        "current_piece": {"name": "O", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["T", "L", "I"],
        "allow_hold": False,
        "goal_text": "Hedef: Iki satiri ayni anda temizle.",
        "tip_key": "tutorial_board_gap_fill_tip",
        "tip_text": "Genis bosluklari okuyup uygun parcayi secmek kart modundaki kararlarin temelidir.",
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },
    "keep_stack_low": {
        "goal_key": "tutorial_board_keep_low_goal",
        "board_rows": [
            "X.........",
            "XX........",
            "XXX.......",
            "XXXX......",
        ],
        "current_piece": {"name": "O", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["T", "I", "L"],
        "allow_hold": False,
        "goal_text": "Hedef: Yeni delik acmadan yuksekligi arttirma.",
        "tip_key": "tutorial_board_keep_low_tip",
        "tip_text": "Her temizleme hemen gerekmez; bazen en iyi hamle kuleyi buyutmemektir.",
        "evaluation": {
            "required_line_clears": 0,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },
    "vertical_well_quadrix": {
        "goal_key": "tutorial_board_vertical_well_goal",
        "board_rows": [
            "XXXX.XXXXX",
            "XXXX.XXXXX",
            "XXXX.XXXXX",
            "XXXX.XXXXX",
        ],
        "current_piece": {"name": "I", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["O", "T", "L"],
        "allow_hold": False,
        "goal_text": "Hedef: Kuyuyu okuyup I parcasi ile Quadrix yap.",
        "tip_key": "tutorial_board_vertical_well_tip",
        "tip_text": "Kart modunda da en guclu kararlar once kuyuyu hazirlayip sonra dogru parcayi beklemektir.",
        "evaluation": {
            "required_line_clears": 4,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -1,
        },
    },
}


def get_scenario(scenario_id: str | None) -> Dict[str, Any] | None:
    if not scenario_id:
        return None
    scenario = SCENARIOS.get(str(scenario_id))
    if not scenario:
        return None

    hydrated = deepcopy(scenario)
    hydrated["id"] = str(scenario_id)
    goal_key = hydrated.get("goal_key")
    if goal_key:
        hydrated["goal_text"] = t(str(goal_key), default=str(hydrated.get("goal_text") or ""))
    tip_key = hydrated.get("tip_key")
    if tip_key:
        hydrated["tip_text"] = t(str(tip_key), default=str(hydrated.get("tip_text") or ""))
    return hydrated


def _empty_occupancy(width: int, height: int) -> List[List[bool]]:
    return [[False for _ in range(width)] for _ in range(height)]


def build_occupancy_from_rows(
    board_rows: Iterable[str] | None,
    *,
    width: int = 10,
    height: int = 20,
    fill_chars: str = "X#1@",
) -> List[List[bool]]:
    occupancy = _empty_occupancy(width, height)
    rows = [str(row) for row in (board_rows or []) if row is not None]
    for source_index, row in enumerate(reversed(rows[-height:])):
        y = height - 1 - source_index
        normalized = row[:width].ljust(width, ".")
        for x, cell in enumerate(normalized):
            occupancy[y][x] = cell in fill_chars
    return occupancy


def count_holes(occupancy: List[List[bool]]) -> int:
    if not occupancy:
        return 0
    height = len(occupancy)
    width = len(occupancy[0]) if occupancy[0] else 0
    holes = 0
    for x in range(width):
        seen_block = False
        for y in range(height):
            filled = bool(occupancy[y][x])
            if filled:
                seen_block = True
            elif seen_block:
                holes += 1
    return holes


def get_column_heights(occupancy: List[List[bool]]) -> List[int]:
    if not occupancy:
        return []
    height = len(occupancy)
    width = len(occupancy[0]) if occupancy[0] else 0
    column_heights: List[int] = []
    for x in range(width):
        column_height = 0
        for y in range(height):
            if occupancy[y][x]:
                column_height = height - y
                break
        column_heights.append(column_height)
    return column_heights


def max_height(occupancy: List[List[bool]]) -> int:
    heights = get_column_heights(occupancy)
    return max(heights) if heights else 0


def count_filled_cells(occupancy: List[List[bool]]) -> int:
    return sum(1 for row in occupancy for cell in row if cell)


def capture_board_metrics(board: Any) -> Dict[str, Any]:
    occupancy = [list(map(bool, row)) for row in getattr(board, "occupancy", [])]
    return {
        "holes": count_holes(occupancy),
        "column_heights": get_column_heights(occupancy),
        "max_height": max_height(occupancy),
        "filled_cells": count_filled_cells(occupancy),
        "lines_cleared": int(getattr(board, "lines_cleared", 0) or 0),
    }


def evaluate_scenario(
    initial_metrics: Dict[str, Any] | None,
    current_metrics: Dict[str, Any] | None,
    evaluation: Dict[str, Any] | None,
) -> Dict[str, Any]:
    initial = deepcopy(initial_metrics) if isinstance(initial_metrics, dict) else {}
    current = deepcopy(current_metrics) if isinstance(current_metrics, dict) else {}
    rules = deepcopy(evaluation) if isinstance(evaluation, dict) else {}

    line_delta = int(current.get("lines_cleared", 0) or 0) - int(initial.get("lines_cleared", 0) or 0)
    hole_delta = int(current.get("holes", 0) or 0) - int(initial.get("holes", 0) or 0)
    height_delta = int(current.get("max_height", 0) or 0) - int(initial.get("max_height", 0) or 0)

    required_line_clears = max(0, int(rules.get("required_line_clears", 0) or 0))
    max_new_holes = int(rules.get("max_new_holes", 999) or 0)
    max_height_increase = int(rules.get("max_height_increase", 999) or 0)
    preferred_height_increase = int(rules.get("preferred_max_height_increase", max_height_increase) or 0)

    success = (
        line_delta >= required_line_clears
        and hole_delta <= max_new_holes
        and height_delta <= max_height_increase
    )

    stars = 0
    if success:
        stars = 1
        if hole_delta <= 0:
            stars += 1
        if height_delta <= preferred_height_increase:
            stars += 1
        stars = max(1, min(3, stars))

    feedback_key = "clean"
    if line_delta < required_line_clears:
        feedback_key = "need_more_lines"
    elif hole_delta > max_new_holes:
        feedback_key = "created_holes"
    elif height_delta > max_height_increase:
        feedback_key = "stack_too_high"

    return {
        "success": bool(success),
        "stars": int(stars),
        "feedback_key": feedback_key,
        "line_delta": line_delta,
        "hole_delta": hole_delta,
        "height_delta": height_delta,
        "required_line_clears": required_line_clears,
    }