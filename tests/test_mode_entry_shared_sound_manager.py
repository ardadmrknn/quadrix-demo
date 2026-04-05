from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "src" / "main.py"

TARGET_MODE_CALLS = {
    "Game",
    "TutorialMode",
    "PvPGame",
    "OnlinePvPGame",
    "SprintMode",
    "UltraMode",
    "ZenMode",
    "HardcoreMode",
    "DailyChallengeMode",
    "CampaignMode",
    "Tetris2Mode",
    "MysteryMode",
    "WideMode",
    "SurvivalMode",
    "CascadeMode",
}

CONSTRUCTOR_TARGETS = {
    "src/game_modes.py": (
        "SprintMode",
        "UltraMode",
        "ZenMode",
        "HardcoreMode",
    ),
    "src/game_modes_advanced.py": (
        "SurvivalMode",
        "CascadeMode",
        "DailyChallengeMode",
    ),
    "src/game_modes_extra.py": (
        "Tetris2Mode",
        "MysteryMode",
        "WideMode",
    ),
    "src/campaign/campaign_mode.py": ("CampaignMode",),
}


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_target_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in TARGET_MODE_CALLS:
            yield node.func.id, node


def _keyword_value(call: ast.Call, keyword_name: str):
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value
    return None


def _find_class_init(path: Path, class_name: str) -> ast.FunctionDef | None:
    tree = _parse(path)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                return child
    return None


def _find_super_init_sound_keyword(init_node: ast.FunctionDef):
    for node in ast.walk(init_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "__init__":
            continue
        if not isinstance(func.value, ast.Call):
            continue
        super_call = func.value
        if not isinstance(super_call.func, ast.Name) or super_call.func.id != "super":
            continue
        return _keyword_value(node, "sound_manager")
    return None


def test_main_mode_entries_reuse_shared_menu_sound():
    tree = _parse(MAIN_PY)
    seen = {name: 0 for name in TARGET_MODE_CALLS}
    missing_sound_manager = []

    for name, call in _iter_target_calls(tree):
        seen[name] += 1
        sound_manager_value = _keyword_value(call, "sound_manager")
        if not isinstance(sound_manager_value, ast.Name) or sound_manager_value.id != "menu_sound":
            missing_sound_manager.append(f"{name}@L{call.lineno}")

    unseen = sorted(name for name, count in seen.items() if count == 0)
    assert not unseen, f"Expected mode entry call sites were not found in src/main.py: {unseen}"
    assert not missing_sound_manager, (
        "Some mode entry call sites do not reuse shared menu_sound: "
        + ", ".join(missing_sound_manager)
    )


def test_changed_mode_constructors_forward_sound_manager():
    missing_param = []
    missing_forward = []

    for relative_path, class_names in CONSTRUCTOR_TARGETS.items():
        path = ROOT / relative_path
        for class_name in class_names:
            init_node = _find_class_init(path, class_name)
            assert init_node is not None, f"{class_name}.__init__ not found in {relative_path}"

            arg_names = [argument.arg for argument in init_node.args.args]
            if "sound_manager" not in arg_names:
                missing_param.append(f"{class_name}@{relative_path}")

            forwarded_value = _find_super_init_sound_keyword(init_node)
            if not isinstance(forwarded_value, ast.Name) or forwarded_value.id != "sound_manager":
                missing_forward.append(f"{class_name}@{relative_path}")

    assert not missing_param, "sound_manager parameter missing: " + ", ".join(missing_param)
    assert not missing_forward, (
        "sound_manager is not forwarded to Game.__init__: "
        + ", ".join(missing_forward)
    )