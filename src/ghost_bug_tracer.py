from __future__ import annotations

import json
import os
import time
from collections import deque
from typing import Any


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


class GhostBugTracer:
    """Lightweight ring-buffer tracer to capture rare ghost/tunnel-related clears.

    Usage pattern:
    - call `event(...)` for key actions
    - call `record_clear(...)` when cells are cleared outside normal line clears
    - call `maybe_dump(...)` to write a JSON bundle when a suspicious condition occurs
    """

    def __init__(self, *, enabled: bool, dump_dir: str, max_events: int = 240) -> None:
        self.enabled = bool(enabled)
        self.dump_dir = str(dump_dir)
        self._events: deque[dict[str, Any]] = deque(maxlen=max(20, int(max_events)))
        self._last_g_ms: int | None = None

        if self.enabled:
            try:
                os.makedirs(self.dump_dir, exist_ok=True)
            except Exception:
                # If we can't create the directory, disable to avoid runtime issues.
                self.enabled = False

    def mark_g_pressed(self, now_ms: int) -> None:
        if not self.enabled:
            return
        self._last_g_ms = _safe_int(now_ms, 0)

    def ms_since_g(self, now_ms: int) -> int | None:
        if not self.enabled or self._last_g_ms is None:
            return None
        return max(0, _safe_int(now_ms, 0) - _safe_int(self._last_g_ms, 0))

    def event(self, kind: str, *, now_ms: int | None = None, **data: Any) -> None:
        if not self.enabled:
            return
        ev = {
            "t_ms": _safe_int(now_ms, -1) if now_ms is not None else -1,
            "kind": str(kind),
            "data": data,
        }
        self._events.append(ev)

    def snapshot_piece(self, piece: Any) -> dict[str, Any]:
        if piece is None:
            return {"present": False}
        out: dict[str, Any] = {
            "present": True,
            "name": getattr(piece, "name", None),
            "x": getattr(piece, "x", None),
            "y": getattr(piece, "y", None),
            "rotation": getattr(piece, "rotation", None),
            "tunnel": bool(getattr(piece, "tunnel", False)),
            "is_bomb": bool(getattr(piece, "is_bomb", False)),
            "bomb_contact": bool(getattr(piece, "_bomb_contact", False)),
            "drill": bool(getattr(piece, "drill", False)),
        }
        try:
            cells = list(getattr(piece, "get_cells")())
            out["cells"] = [(int(x), int(y)) for x, y in cells]
        except Exception:
            out["cells"] = None
        return out

    def snapshot_board(self, board: Any, *, max_rows: int = 40, max_cols: int = 40) -> dict[str, Any]:
        if board is None:
            return {"present": False}
        occ = getattr(board, "occupancy", None)
        if occ is None:
            return {"present": False}

        try:
            height = min(len(occ), max_rows)
            width = min(len(occ[0]) if height else 0, max_cols)
        except Exception:
            return {"present": False}

        rows: list[str] = []
        for y in range(height):
            try:
                row = occ[y]
                rows.append("".join("#" if row[x] else "." for x in range(width)))
            except Exception:
                rows.append("".join("?" for _ in range(width)))

        return {
            "present": True,
            "width": width,
            "height": height,
            "rows": rows,
        }

    def record_clear(
        self,
        *,
        now_ms: int | None,
        clear_kind: str,
        cleared_cells: int,
        coords: list[tuple[int, int]] | None = None,
        piece: Any = None,
        note: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        self.event(
            "clear",
            now_ms=now_ms,
            clear_kind=str(clear_kind),
            cleared_cells=_safe_int(cleared_cells, 0),
            coords=[(int(x), int(y)) for x, y in (coords or [])][:250],
            piece=self.snapshot_piece(piece),
            note=note,
        )

    def maybe_dump(
        self,
        *,
        now_ms: int | None,
        trigger: str,
        board: Any = None,
        current_piece: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None

        payload = {
            "version": 1,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trigger": str(trigger),
            "now_ms": _safe_int(now_ms, -1) if now_ms is not None else -1,
            "ms_since_g": self.ms_since_g(_safe_int(now_ms, 0)) if now_ms is not None else None,
            "events": list(self._events),
            "board": self.snapshot_board(board),
            "current_piece": self.snapshot_piece(current_piece),
            "extra": extra or {},
        }

        fname = f"ghost_bug_{int(time.time())}_{os.getpid()}.json"
        path = os.path.join(self.dump_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return path
        except Exception:
            return None
