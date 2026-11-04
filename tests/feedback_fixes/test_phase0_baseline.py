"""Faz 0 baseline snapshot ve test seçim sözleşmesi.

Bu dosya baseline üretmez; yalnızca değişmez başlangıç kaydını okur ve
çalışan kaynak davranışını o kayda karşı doğrular. Baseline yenilemek test
koşusunun yan etkisi değildir; ayrı, incelenebilir bir bakım işlemidir.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pieces import (
    SHAPE_NAMES,
    SRS_KICKS_180_I,
    SRS_KICKS_180_NORMAL,
    SRS_KICKS_I,
    SRS_KICKS_NORMAL,
    Piece,
    get_piece_top_filled_row,
    skip_hidden_rows,
)


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase0]

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "tests" / "baseline" / "phase0_baseline.json"
MANIFEST_PATH = ROOT / "tests" / "baseline" / "MANIFEST.json"
PHASE1_EXPECTED_PATH = ROOT / "tests" / "baseline" / "phase1_expected.json"


def _load_baseline() -> dict:
    assert BASELINE_PATH.is_file(), f"Eksik immutable baseline: {BASELINE_PATH}"
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _phase1_expected() -> dict:
    if not PHASE1_EXPECTED_PATH.is_file():
        return {}
    return json.loads(PHASE1_EXPECTED_PATH.read_text(encoding="utf-8"))


def _jsonable_vectors(table: dict) -> dict:
    return {
        f"{source}>{target}": {
            "all": [list(vector) for vector in vectors],
            "first_five": [list(vector) for vector in vectors[:5]],
            "count": len(vectors),
        }
        for (source, target), vectors in sorted(table.items())
    }


def _spawn_snapshot(game_factory) -> dict:
    game = game_factory({})
    snapshot = {}
    for name in SHAPE_NAMES:
        piece = game._create_named_piece(name)
        raw_y = piece.y
        raw_x = piece.x
        skip_hidden_rows(piece, game.board)
        snapshot[name] = {
            "x": raw_x,
            "raw_y": raw_y,
            "visible_y": piece.y,
            "top_filled_row": get_piece_top_filled_row(piece),
        }
    return snapshot


def _scoring_snapshot(filled_board) -> dict:
    scores = {}
    for count, label in ((1, "single"), (2, "double"), (3, "triple"), (4, "quadrix")):
        board = filled_board(rows=count, holes=[])
        board.occupancy[0][0] = True
        board.grid[0][0] = (1, 1, 1)
        board.clear_lines()
        scores[label] = board.score
    return scores


def _bag_snapshot(seeded_game) -> dict:
    game = seeded_game(1234)
    sequence = [game.spawn_new_piece().name for _ in range(100)]
    counts = {name: sequence.count(name) for name in SHAPE_NAMES}
    return {"seed": 1234, "length": len(sequence), "counts": counts, "sequence": sequence}


def _sweep_snapshot(game_factory) -> dict:
    game = game_factory({})
    game.board = game.board.__class__(width=10, height=20)
    game.board_width = 10
    game.board_height = 20
    game.line_clear_sweep_active = True
    game.line_clear_sweep_progress = 0.0
    game.line_clear_sweep_rows = [19]
    game.falling_block_animations = [{
        "row": 18, "col": 0, "current_offset": -32.0,
        "target_offset": 0, "sweep_trigger": 1.0, "started": False,
    }]
    game.line_clear_animation = 0.0
    game.line_clear_wave_effects = []
    game.block_fall_speed = 1.0
    game.current_piece = None
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.game_over_warning_timer = 0.0
    game.game_over_warning = ""
    game.dcd_timer = 0.0
    game.hard_drop_lockout_timer = 0.0
    game.control_bindings = {}
    game._soft_drop_held = False
    game._update_das = lambda _dt: None
    game.game_time = 0.0
    game._shape_mutation_cooldown = 0.0
    game.last_milestone_score = 0
    game.firework_active = False
    game.board.score = 0
    game.get_cell_size = lambda: 32
    game.update(16.666)
    first_progress = game.line_clear_sweep_progress
    first_active = game.line_clear_sweep_active
    ticks = 1
    while game.line_clear_sweep_active or game.falling_block_animations:
        assert ticks < 1000, "Sweep/fall update never completed"
        game.update(16.666)
        ticks += 1
    return {
        "dt_ms": 16.666,
        "resolution": [320, 640],
        "board_cells": [10, 20],
        "cell_size": 32,
        "level": 1,
        "progress_after_update": first_progress,
        "active_after_update": first_active,
        "clear_fall_duration_ms": round(ticks * 16.666, 6),
        "ticks_to_completion": ticks,
    }


def test_spawn_snapshot(seeded_game, game_factory):
    expected = dict(_load_baseline()["spawn"])
    expected.update(_phase1_expected().get("spawn", {}))
    assert _spawn_snapshot(game_factory) == expected


def test_srs_snapshot():
    expected = dict(_load_baseline()["srs"])
    phase1_srs = _phase1_expected().get("srs", {})
    for table_name, table_values in phase1_srs.items():
        expected[table_name] = table_values
    actual = {
        "normal": _jsonable_vectors(SRS_KICKS_NORMAL),
        "i": _jsonable_vectors(SRS_KICKS_I),
        "normal_180": _jsonable_vectors(SRS_KICKS_180_NORMAL),
        "i_180": _jsonable_vectors(SRS_KICKS_180_I),
    }
    assert actual == expected


def test_scoring_snapshot(filled_board):
    assert _scoring_snapshot(filled_board) == _load_baseline()["scoring"]


def test_bag_snapshot(seeded_game):
    assert _bag_snapshot(seeded_game) == _load_baseline()["bag"]


def test_sweep_snapshot(game_factory):
    assert _sweep_snapshot(game_factory) == _load_baseline()["sweep"]


def test_fixture_determinism(seeded_game, filled_board):
    first = _bag_snapshot(seeded_game)
    second = _bag_snapshot(seeded_game)
    assert first == second
    assert _scoring_snapshot(filled_board) == _scoring_snapshot(filled_board)
    changed_seed = seeded_game(4321)
    assert [changed_seed.spawn_new_piece().name for _ in range(100)] != first["sequence"]
    normal = filled_board(rows=1, holes=[])
    broken = filled_board(rows=1, holes=[(0, 19)])
    assert normal.clear_lines() == 1
    assert broken.clear_lines() == 0


def test_snapshot_manifest():
    baseline = _load_baseline()
    assert MANIFEST_PATH.is_file(), f"Eksik baseline manifest: {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(BASELINE_PATH.read_bytes()).hexdigest()
    assert manifest["phase"] == 0
    assert manifest["baseline_sha256"] == digest
    assert manifest["schema_version"] == baseline["schema_version"]
    assert manifest["python_major_minor"] == ["3", "12"]
    damaged = bytearray(BASELINE_PATH.read_bytes())
    damaged[-1] ^= 1
    assert hashlib.sha256(damaged).hexdigest() != manifest["baseline_sha256"]


def test_phase_selection_manifest(request):
    markers = {mark.name for mark in request.node.iter_markers()}
    assert {"quadrix_feedback", "quadrix_phase0"}.issubset(markers)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    selected = sorted(
        item.nodeid.replace("\\", "/")
        for item in request.session.items
        if item.get_closest_marker("quadrix_phase0")
    )
    assert selected == manifest["phase0_node_ids"]
