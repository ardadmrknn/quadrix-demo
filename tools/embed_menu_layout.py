from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PAYLOAD: dict[str, Any] = {
    "version": 1,
    "coord_space": "screen_pct",
    "reference_resolution": [1920, 1080],
    "rects": {},
}


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_PAYLOAD)

    rects_in = raw.get("rects")
    rects_out: dict[str, dict[str, Any]] = {}
    if isinstance(rects_in, dict):
        for key, value in rects_in.items():
            if not isinstance(value, dict):
                continue
            x_pct = _safe_float(value.get("x_pct"))
            y_pct = _safe_float(value.get("y_pct"))
            w_pct = _safe_float(value.get("w_pct"))
            h_pct = _safe_float(value.get("h_pct"))
            if None in (x_pct, y_pct, w_pct, h_pct):
                continue
            rect_entry = {
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct,
            }
            if "title" in value:
                rect_entry["title"] = str(value.get("title", ""))
            rects_out[str(key)] = rect_entry

    payload: dict[str, Any] = {
        "version": int(raw.get("version", DEFAULT_PAYLOAD["version"])),
        "coord_space": str(raw.get("coord_space", "screen_pct") or "screen_pct").strip().lower(),
        "reference_resolution": raw.get("reference_resolution", [1920, 1080]),
        "reference_window": raw.get("reference_window"),
        "reference_canvas": raw.get("reference_canvas"),
        "rects": rects_out,
    }

    if payload["coord_space"] not in {"screen_pct", "canvas_pct"}:
        payload["coord_space"] = "screen_pct"

    return payload


def write_embedded_layout_module(repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
    source_json = root / "menu_layout_runtime.json"
    target_py = root / "src" / "menu_layout_embedded.py"

    payload: dict[str, Any]
    if source_json.exists():
        try:
            raw = json.loads(source_json.read_text(encoding="utf-8"))
            payload = _normalize_payload(raw)
        except Exception:
            payload = dict(DEFAULT_PAYLOAD)
    else:
        payload = dict(DEFAULT_PAYLOAD)

    payload["source"] = "menu_layout_runtime.json"

    embedded_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    module_content = (
        "\"\"\"Build-time embedded main menu layout payload.\"\"\"\n\n"
        "import json as _json\n\n"
        f"_EMBEDDED_MENU_LAYOUT_JSON = {embedded_json!r}\n"
        "EMBEDDED_MENU_LAYOUT = _json.loads(_EMBEDDED_MENU_LAYOUT_JSON)\n"
    )
    target_py.write_text(module_content, encoding="utf-8")
    return target_py


if __name__ == "__main__":
    out = write_embedded_layout_module()
    print(f"Embedded menu layout written: {out}")
