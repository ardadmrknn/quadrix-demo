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


def test_store_menu_action_transitions_into_store_state():
    tree = _parse_main()
    branch = _find_action_branch(tree, 'store')

    assert branch is not None, 'store action branch was not found in src/main.py'

    show_info_calls = []
    state_assignments = []

    for statement in branch.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'menu' and node.func.attr == 'show_info':
                    show_info_calls.append(node.lineno)
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == 'state' for target in node.targets):
                    if isinstance(node.value, ast.Constant) and node.value.value == 'store':
                        state_assignments.append(node.lineno)

    assert not show_info_calls, (
        'store action should no longer show the old placeholder info popup: '
        + ', '.join(f'L{line}' for line in show_info_calls)
    )
    assert state_assignments, 'store action should transition into the store state'


def test_state_handlers_include_store_handler():
    tree = _parse_main()
    found = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == 'STATE_HANDLERS' for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key_node, value_node in zip(node.value.keys, node.value.values):
            if not isinstance(key_node, ast.Constant) or key_node.value != 'store':
                continue
            if isinstance(value_node, ast.Name) and value_node.id == '_handle_store':
                found = True

    assert found, 'STATE_HANDLERS should register the store screen handler'