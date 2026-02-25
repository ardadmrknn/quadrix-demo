from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR_STATE = ROOT / "tools" / "menu_layout_editor_state.json"
RUNTIME_LAYOUT = ROOT / "menu_layout_runtime.json"

KEY_ALIASES = {
    "pvp": "pvp_2_players",
    "daily": "daily_challenge",
    "campaign": "campaign_mode",
}

EXPECTED_KEYS = {
    "hero_panel",
    "sos_button",
    "settings_button",
    "mute_button",
    "switch_user_button",
    "new_gen_tetris",
    "piece_workshop",
    "extras",
    "pvp_2_players",
    "achievements",
    "steam_scores",
    "daily_challenge",
    "campaign_mode",
    "block_styles",
    "guide_button",
    "credits_button",
    "high_scores_button",
    "exit_button",
}


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def main() -> None:
    if not EDITOR_STATE.exists():
        raise SystemExit(f"Editor state bulunamadı: {EDITOR_STATE}")

    payload = json.loads(EDITOR_STATE.read_text(encoding="utf-8"))
    panels = payload.get("panels", [])
    if not isinstance(panels, list) or not panels:
        raise SystemExit("Editor state içinde panel verisi yok.")

    ref_canvas = payload.get("reference_canvas") or [20, 20, 1460, 880]
    if not isinstance(ref_canvas, list) or len(ref_canvas) != 4:
        ref_canvas = [20, 20, 1460, 880]

    cx, cy, cw, ch = [int(v) for v in ref_canvas]
    cw = max(1, cw)
    ch = max(1, ch)

    rects: dict[str, dict] = {}
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        raw_key = str(panel.get("key", "")).strip()
        key = KEY_ALIASES.get(raw_key, raw_key)
        if not key:
            continue

        x = int(panel.get("x", 0))
        y = int(panel.get("y", 0))
        w = max(1, int(panel.get("w", 1)))
        h = max(1, int(panel.get("h", 1)))

        x_pct = (x - cx) / cw
        y_pct = (y - cy) / ch
        w_pct = w / cw
        h_pct = h / ch

        rects[key] = {
            "x_pct": round(_clamp(x_pct, -0.5, 1.5), 6),
            "y_pct": round(_clamp(y_pct, -0.5, 1.5), 6),
            "w_pct": round(_clamp(w_pct, 0.005, 1.5), 6),
            "h_pct": round(_clamp(h_pct, 0.005, 1.5), 6),
            "title": panel.get("title", key),
        }

    output = {
        "version": 1,
        "source": "tools/menu_layout_editor_state.json",
        "reference_canvas": [cx, cy, cw, ch],
        "rects": rects,
    }

    RUNTIME_LAYOUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Runtime layout yazıldı: {RUNTIME_LAYOUT}")
    print(f"[INFO] Aktarılan öğe sayısı: {len(rects)}")
    missing = sorted(EXPECTED_KEYS - set(rects.keys()))
    if missing:
        print(f"[UYARI] Eksik öğeler ({len(missing)}): {', '.join(missing)}")
        print("[İPUCU] Editor'de R (reset) veya L (reload) + S (save) yapıp scripti tekrar çalıştırın.")


if __name__ == "__main__":
    main()
