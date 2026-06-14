"""Cross-repo localization parity checks for shared high-visibility slices."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


os.environ.setdefault("TETRIS_LOCALIZATION_HOT_RELOAD", "0")


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEMO_LOCALIZATION_PATH = WORKSPACE_ROOT / "quadrix-demo" / "src" / "localization.py"
MAIN_LOCALIZATION_PATH = WORKSPACE_ROOT / "v2" / "src" / "localization.py"

FAMILY_PREFIXES = (
    "daily_prompt_",
    "guide_card_",
    "guide_mode_",
    "guide_perk_",
    "settings_section_",
    "settings_tab_",
    "tutorial_hub_",
    "tutorial_result_",
    "user_field_",
    "menu_hint_",
    "menu_lb_",
    "menu_dashboard_",
)

EXACT_KEYS = {
    "single_player",
    "new_gen_tetris",
    "pvp_2_players",
    "extras",
    "switch_user",
    "loading",
    "please_wait",
    "error",
    "success",
    "warning",
    "confirm",
    "cancel",
    "save",
    "delete",
    "select",
    "arrows",
    "space",
    "username",
    "guest",
    "login",
    "logout",
    "profile",
    "total_games",
    "total_score",
    "best_score",
    "total_lines",
    "highest_level",
    "favorite_mode",
    "daily_no_user",
    "daily_no_attempts",
    "main_menu_title",
    "tetris_label",
}


def _load_translations(module_name: str, file_path: Path) -> dict[str, dict[str, str]]:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    spec.loader.exec_module(module)
    return dict(module.TRANSLATIONS)


def _selected_keys(demo: dict[str, dict[str, str]], main: dict[str, dict[str, str]]) -> list[str]:
    common = set(demo) & set(main)
    selected = set(EXACT_KEYS)
    selected.update(
        key
        for key in common
        if any(key.startswith(prefix) for prefix in FAMILY_PREFIXES)
    )
    return sorted(selected & common)


def test_shared_high_visibility_localization_stays_in_parity_with_main():
    demo_translations = _load_translations("quadrix_demo_localization_parity", DEMO_LOCALIZATION_PATH)
    main_translations = _load_translations("quadrix_main_localization_parity", MAIN_LOCALIZATION_PATH)

    keys = _selected_keys(demo_translations, main_translations)
    assert keys, "Expected at least one shared localization key in parity scope"

    mismatches = []
    for key in keys:
        if demo_translations[key] != main_translations[key]:
            mismatches.append(key)

    assert not mismatches, "Shared localization parity drift detected:\n" + "\n".join(mismatches[:40])