"""Opt-in, local ve bounded performans telemetrisi.

Normal kullanıcı çalıştırmasında kapalıdır. Yalnızca
``QUADRIX_PERF_TELEMETRY=1`` ile etkinleşir. Telemetri dosyaları
``data_paths.get_local_data_dir()/perf`` altında tutulur; Steam Cloud alanına
yazılmaz. Kapalı yolda per-frame dosya veya JSON işlemi yapılmaz.
"""

from __future__ import annotations

import atexit
import json
import os
import platform
import sys
import time
from collections import defaultdict
from typing import Any


_ENABLE_ENV = "QUADRIX_PERF_TELEMETRY"
_WINDOW_ENV = "QUADRIX_PERF_WINDOW_FRAMES"
_DEFAULT_WINDOW_FRAMES = 180
_MAX_EVENTS_PER_SESSION = 256

_enabled_cache: bool | None = None
_path_cache: str | None = None
_session_id = time.strftime("%Y%m%d_%H%M%S") + f"_{os.getpid()}"
_last_frame_start: float | None = None
_active_state: str | None = None
_events_written = 0
_agg: dict[str, dict[str, Any]] = defaultdict(lambda: _new_state_agg())


def _new_state_agg() -> dict[str, Any]:
    return {
        "frames": 0,
        "drawn": 0,
        "clock_ms": [],
        "frame_ms": [],
        "phases_ms": defaultdict(list),
        "metrics": defaultdict(float),
    }


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes", "enable", "enabled")


def is_enabled() -> bool:
    global _enabled_cache
    if _enabled_cache is None:
        _enabled_cache = _truthy(os.getenv(_ENABLE_ENV))
        if "pytest" in sys.modules or any("pytest" in str(arg) for arg in sys.argv):
            _enabled_cache = _truthy(os.getenv(_ENABLE_ENV))
    return bool(_enabled_cache)


def _window_frames() -> int:
    try:
        return max(30, min(600, int(os.getenv(_WINDOW_ENV, str(_DEFAULT_WINDOW_FRAMES)))))
    except Exception:
        return _DEFAULT_WINDOW_FRAMES


def _local_perf_dir() -> str:
    try:
        import data_paths
        base = data_paths.get_local_data_dir()
    except Exception:
        base = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "Quadrix", "local")
    path = os.path.join(base, "perf")
    os.makedirs(path, exist_ok=True)
    return path


def telemetry_path() -> str:
    global _path_cache
    if _path_cache is None:
        _path_cache = os.path.join(_local_perf_dir(), f"perf_telemetry_{_session_id}.jsonl")
    return _path_cache


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(len(ordered) - 1, index))]


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
    vals = [float(value) for value in values]
    return {
        "avg": sum(vals) / len(vals),
        "p50": _percentile(vals, 50),
        "p95": _percentile(vals, 95),
        "p99": _percentile(vals, 99),
        "min": min(vals),
        "max": max(vals),
    }


def _write_event(event: dict[str, Any]) -> None:
    global _events_written
    if not is_enabled() or _events_written >= _MAX_EVENTS_PER_SESSION:
        return
    try:
        payload = dict(event)
        payload.setdefault("type", "event")
        payload.setdefault("session", _session_id)
        payload.setdefault("t", round(time.time(), 3))
        with open(telemetry_path(), "a", encoding="utf-8", errors="ignore") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        _events_written += 1
    except Exception:
        pass


def record_event(kind: str, **data: Any) -> None:
    if not is_enabled():
        return
    payload = {"type": str(kind)}
    payload.update(data)
    _write_event(payload)


def record_startup(**data: Any) -> None:
    if not is_enabled():
        return
    payload = {
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    payload.update(data)
    record_event("startup", **payload)


def begin_frame(state: str, *, clock_ms: float | int | None = None, fps_limit: int | None = None) -> None:
    if not is_enabled():
        return
    global _last_frame_start, _active_state
    now = time.perf_counter()
    state_key = str(state or "unknown")
    if _active_state is not None and _active_state != state_key:
        _flush_state(_active_state, reason="state_change")
        _last_frame_start = now
    agg = _agg[state_key]
    agg["frames"] += 1
    if clock_ms is not None:
        try:
            agg["clock_ms"].append(float(clock_ms))
        except Exception:
            pass
    if _last_frame_start is not None:
        agg["frame_ms"].append((now - _last_frame_start) * 1000.0)
    agg["fps_limit"] = int(fps_limit or 0)
    _last_frame_start = now
    _active_state = state_key


def record_phase(state: str, phase: str, ms: float | int | None) -> None:
    if not is_enabled() or ms is None:
        return
    try:
        value = float(ms)
    except Exception:
        return
    if value < 0.0 or value > 60000.0:
        return
    _agg[str(state or "unknown")]["phases_ms"][str(phase or "")].append(value)


def record_metric(state: str, name: str, value: float | int = 1) -> None:
    if not is_enabled() or not str(name or ""):
        return
    try:
        _agg[str(state or "unknown")]["metrics"][str(name)] += float(value)
    except Exception:
        pass


def _flush_state(state: str, *, reason: str) -> None:
    agg = _agg.get(state)
    if not agg or int(agg.get("frames", 0) or 0) <= 0:
        return
    frame_values = list(agg.get("frame_ms", []) or [])
    wall_ms = sum(frame_values)
    event = {
        "type": "main_loop_window",
        "reason": reason,
        "state": state,
        "frames": int(agg.get("frames", 0) or 0),
        "drawn": int(agg.get("drawn", 0) or 0),
        "fps_est": (1000.0 * len(frame_values) / wall_ms) if wall_ms > 0 else 0.0,
        "clock_ms": _stats(list(agg.get("clock_ms", []) or [])),
        "frame_ms": _stats(frame_values),
        "phases_ms": {name: _stats(list(values or [])) for name, values in dict(agg.get("phases_ms", {}) or {}).items() if name},
        "metrics": dict(agg.get("metrics", {}) or {}),
        "fps_limit": int(agg.get("fps_limit", 0) or 0),
    }
    _agg[state] = _new_state_agg()
    _write_event(event)


def end_frame(state: str, *, did_draw: bool = False) -> None:
    if not is_enabled():
        return
    state_key = str(state or "unknown")
    agg = _agg[state_key]
    if did_draw:
        agg["drawn"] += 1
    # Son karenin phase/drawn ölçümlerini de aynı pencereye dahil et.
    if int(agg["frames"]) >= _window_frames():
        _flush_state(state_key, reason="window")


def flush_all(reason: str = "manual") -> None:
    if not is_enabled():
        return
    for state in list(_agg):
        _flush_state(state, reason=reason)


@atexit.register
def _flush_at_exit() -> None:
    try:
        flush_all("exit")
    except Exception:
        pass
