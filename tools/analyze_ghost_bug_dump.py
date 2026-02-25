from __future__ import annotations

import argparse
import json
from pathlib import Path


def _print_events(events: list[dict], limit: int = 40) -> None:
    tail = events[-limit:] if len(events) > limit else events
    for ev in tail:
        t = ev.get("t_ms")
        kind = ev.get("kind")
        data = ev.get("data", {})
        if kind == "clear":
            print(f"[{t}] CLEAR {data.get('clear_kind')} cells={data.get('cleared_cells')} note={data.get('note')}")
        else:
            print(f"[{t}] {kind}: {data}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze a ghost bug dump JSON")
    ap.add_argument("path", type=Path, help="Path to ghost_bug_*.json")
    ap.add_argument("--events", type=int, default=60, help="How many tail events to print")
    args = ap.parse_args()

    data = json.loads(args.path.read_text(encoding="utf-8"))
    print(f"Trigger: {data.get('trigger')}  ms_since_g={data.get('ms_since_g')}  created_at={data.get('created_at')}")

    cp = data.get("current_piece", {})
    if cp.get("present"):
        print("Current piece:", {k: cp.get(k) for k in ("name", "x", "y", "rotation", "tunnel", "is_bomb", "drill", "bomb_contact")})

    print("\nRecent events:")
    _print_events(list(data.get("events", []) or []), limit=args.events)

    board = data.get("board", {})
    if board.get("present"):
        print("\nBoard snapshot (top->bottom):")
        for row in board.get("rows", [])[:]:
            print(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
