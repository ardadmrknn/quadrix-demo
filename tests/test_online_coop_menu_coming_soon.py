from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
MAIN_PY = ROOT / 'src' / 'main.py'
ONLINE_COOP_PY = ROOT / 'src' / 'online_coop_game.py'


def _parse_main() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding='utf-8'), filename=str(MAIN_PY))


def _parse_online_coop() -> ast.Module:
    return ast.parse(ONLINE_COOP_PY.read_text(encoding='utf-8'), filename=str(ONLINE_COOP_PY))


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


def _is_pygame_display_flip_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'flip'
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == 'display'
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == 'pygame'
    )


def _load_localization_module():
    os.environ.setdefault('TETRIS_LOCALIZATION_HOT_RELOAD', '0')
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    if 'localization' in sys.modules and not hasattr(sys.modules['localization'], 'TRANSLATIONS'):
        del sys.modules['localization']
    return importlib.import_module('localization')


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


def test_online_coop_uses_main_loop_flip_for_transitions_like_online_pvp():
    coop_tree = _parse_online_coop()
    flip_calls = [
        node.lineno
        for node in ast.walk(coop_tree)
        if _is_pygame_display_flip_call(node)
    ]

    assert not flip_calls, (
        'OnlineCoopGame should not flip inside its draw path; main.py must draw '
        'the transition overlay and flip once, like OnlinePvPGame. Calls at: '
        + ', '.join(f'L{line}' for line in flip_calls)
    )

    main_tree = _parse_main()
    handler_flip_states = []
    for node in ast.walk(main_tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == 'handler_flips_display' for target in node.targets):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Compare)
            and len(value.comparators) == 1
            and isinstance(value.comparators[0], ast.Tuple)
        ):
            continue
        handler_flip_states.extend(
            element.value
            for element in value.comparators[0].elts
            if isinstance(element, ast.Constant)
        )

    assert 'online_coop' not in handler_flip_states
    assert 'online_pvp' not in handler_flip_states


def test_online_coop_lobby_menu_does_not_show_fixed_endless_mode():
    source = ONLINE_COOP_PY.read_text(encoding='utf-8')

    assert 'selected_submode.capitalize()' not in source
    assert 'sub_mode.capitalize()' not in source


def test_online_coop_high_visibility_labels_keep_coop_term_and_translate_online_tr():
    localization = _load_localization_module()
    translations = localization.TRANSLATIONS
    languages = localization.SUPPORTED_LANGUAGES

    keys = [
        'mode_online_coop',
        'online_coop_title',
        'online_coop_subtitle',
        'menu_dashboard_coop_online_label',
        'menu_dashboard_sub_online_coop',
        'mode_intro_online_coop_desc',
    ]
    for key in keys:
        for lang in languages:
            assert 'co-op' in translations[key][lang].lower(), f'{key}[{lang}] should keep Co-op literal'

    for key in keys:
        assert 'online' not in translations[key]['tr'].lower(), f'{key}[tr] should translate Online'
        assert 'çevr' in translations[key]['tr'].lower(), f'{key}[tr] should say Çevrim İçi'

    for key in ('create_private_coop', 'create_public_coop'):
        for lang in languages:
            assert 'endless' not in translations[key][lang].lower(), f'{key}[{lang}] should not show fixed Endless mode'
