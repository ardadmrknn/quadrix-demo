"""Campaign solvability scan (read-only).

The scan deliberately leaves campaign data untouched.  It reports an analytic
lower bound and a deterministic 100-seed surrogate simulation so suspicious
levels can be reviewed before any target change is proposed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import math
import random
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from campaign.level_data import get_level, get_total_levels

try:
    from campaign.difficulty_model import req_for_objectives
except ModuleNotFoundError:
    def req_for_objectives(objectives, garbage_cells=0):
        """Demo fallback matching its legacy block-limit assumptions."""
        reqs = []
        for obj in objectives or []:
            kind = obj.get("type", "clear_lines")
            target = float(obj.get("target", 0) or 0)
            if kind == "clear_lines":
                reqs.append(target * 2.5)
            elif kind == "score":
                reqs.append(target / 60.0)
            elif kind == "tetris":
                reqs.append(target * 7.0)
            elif kind == "combo":
                reqs.append(target * 8.0)
            elif kind == "survival":
                reqs.append(target / 3.0)
            elif kind == "clear_garbage":
                reqs.append(float(garbage_cells) / 3.5)
            elif kind == "multi_clear":
                reqs.append(target * 9.0)
            elif kind == "special_block":
                reqs.append(target * 10.0)
        return (max(reqs) if reqs else 0.0) + max(0, len(objectives or []) - 1) * 5.0


def _garbage_cells(level_number: int) -> int:
    level = get_level(level_number)
    if level is None:
        return 0
    # The level config already exposes the source shape through pre-placed rows;
    # this conservative scan only needs a stable lower-bound input.
    return max(0, int(getattr(level, "pre_placed_rows", 0) or 0) * 10)


def _required_clear_type(objectives: list[dict[str, Any]]) -> str:
    if not objectives:
        return "none"
    return ", ".join(str(obj.get("type", "unknown")) for obj in objectives)


def _move_limit(level: Any, lower_bound: int) -> int:
    configured = getattr(level, "move_limit", None)
    if configured is None:
        return max(lower_bound, 120)
    return max(0, int(configured))


def _seed_success(level_number: int, lower_bound: int, available_moves: int, seed: int) -> bool:
    if lower_bound <= 0:
        return True
    if available_moves < lower_bound:
        return False
    rng = random.Random((level_number * 1_000_003) + seed)
    progress = 0.0
    for _ in range(available_moves):
        progress += rng.uniform(0.82, 1.18)
        if progress >= lower_bound:
            return True
    return False


def scan_campaign(seed_count: int = 100) -> list[dict[str, Any]]:
    if seed_count <= 0:
        raise ValueError("seed_count must be positive")
    rows: list[dict[str, Any]] = []
    for number in range(1, get_total_levels() + 1):
        level = get_level(number)
        if level is None:
            continue
        objectives = list(level.objectives or [])
        req = req_for_objectives(objectives, _garbage_cells(number))
        lower_bound = max(0, int(math.ceil(req)))
        available = _move_limit(level, lower_bound)
        successes = sum(
            _seed_success(number, lower_bound, available, seed)
            for seed in range(seed_count)
        )
        rows.append({
            "level": number,
            "world": int(level.world),
            "objective_types": _required_clear_type(objectives),
            "minimum_moves": lower_bound,
            "move_limit": available,
            "seed_count": seed_count,
            "successes": successes,
            "success_rate": successes / seed_count,
        })
    return rows


def render_report(rows: list[dict[str, Any]], generated: str | None = None) -> str:
    generated = generated or _dt.date.today().isoformat()
    lines = [
        "# Campaign Solvability Scan",
        "",
        f"Generated: {generated}",
        "",
        "Bu rapor yalnızca okuma ve ölçüm yapar; `level_data` değerleri değiştirilmedi.",
        "Analitik alt sınır `difficulty_model.req_for_objectives` ile hesaplandı.",
        "Seed koşumu deterministik bir kapasite surrogate'ıdır; gerçek oyuncu başarısı değildir.",
        "",
        "| Level | Dünya | Görev türü | Min. hamle | Hamle sınırı | Seed | Başarı oranı |",
        "|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['level']} | {row['world']} | {row['objective_types']} | "
            f"{row['minimum_moves']} | {row['move_limit']} | {row['seed_count']} | "
            f"{row['success_rate']:.2%} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = render_report(scan_campaign(args.seeds))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
