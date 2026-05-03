from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / 'src' / 'main.py'


def _parse_main() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding='utf-8'), filename=str(MAIN_PY))


def _is_action_compare(node: ast.AST, action_name: str) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == 'action'
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == action_name
    )


def _find_action_branch(tree: ast.AST, action_name: str) -> ast.If | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_action_compare(node.test, action_name):
            return node
    return None


def test_online_coop_menu_action_starts_online_coop_state():
    tree = _parse_main()
    branch = _find_action_branch(tree, 'online_coop')

    assert branch is not None, 'online_coop action branch was not found in src/main.py'

    coming_soon_calls = []
    constructor_lines = []
    state_lines = []
    handler_assign_lines = []

    branch_nodes = []
    for statement in branch.body:
        branch_nodes.extend(ast.walk(statement))

    for node in branch_nodes:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if (
                    node.func.attr == 'show_info'
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'menu'
                    and node.args
                    and isinstance(node.args[0], ast.Call)
                    and isinstance(node.args[0].func, ast.Name)
                    and node.args[0].func.id == 't'
                    and node.args[0].args
                    and isinstance(node.args[0].args[0], ast.Constant)
                    and node.args[0].args[0].value == 'menu_dashboard_sub_store'
                ):
                    coming_soon_calls.append(node.lineno)
            elif isinstance(node.func, ast.Name) and node.func.id == 'OnlineCoopGame':
                constructor_lines.append(node.lineno)

        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == 'state' for target in node.targets):
                if isinstance(node.value, ast.Constant) and node.value.value == 'online_coop':
                    state_lines.append(node.lineno)
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == '_game'
                    and isinstance(target.value, ast.Name)
                    and target.value.id == '_handle_online_coop'
                ):
                    handler_assign_lines.append(node.lineno)

    assert not coming_soon_calls, (
        'online_coop action should no longer show the coming-soon store toast: '
        + ', '.join(f'L{line}' for line in coming_soon_calls)
    )
    assert constructor_lines, 'online_coop action should instantiate OnlineCoopGame'
    assert handler_assign_lines, 'online_coop action should assign _handle_online_coop._game'
    assert state_lines, 'online_coop action should transition into the online_coop state'


def test_main_fallback_imports_online_coop_game():
    tree = _parse_main()
    import_lines = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != 'online_coop_game':
            continue
        if any(alias.name == 'OnlineCoopGame' for alias in node.names):
            import_lines.append(node.lineno)

    assert import_lines, 'Fallback import block should import OnlineCoopGame to avoid NameError outside package mode'
