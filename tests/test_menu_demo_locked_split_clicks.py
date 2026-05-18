from __future__ import annotations

import ast
from pathlib import Path
import types


ROOT = Path(__file__).resolve().parent.parent
MENU_PY = ROOT / 'src' / 'menu.py'


def _parse_menu() -> ast.Module:
    return ast.parse(MENU_PY.read_text(encoding='utf-8'), filename=str(MENU_PY))


def _get_menu_class() -> ast.ClassDef:
    tree = _parse_menu()
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == 'Menu'
    )


def _get_menu_method(method_name: str) -> ast.FunctionDef:
    menu_class = _get_menu_class()
    return next(
        node for node in menu_class.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def _load_menu_methods(*method_names: str) -> dict[str, object]:
    menu_class = _get_menu_class()
    class_methods = {
        node.name: node
        for node in menu_class.body
        if isinstance(node, ast.FunctionDef)
    }

    namespace = {
        'pygame': types.SimpleNamespace(Rect=object),
    }
    loaded: dict[str, object] = {}
    for method_name in method_names:
        method_node = class_methods.get(method_name)
        assert method_node is not None, f'Menu.{method_name} bulunamadı'
        method_module = ast.Module(body=[method_node], type_ignores=[])
        ast.fix_missing_locations(method_module)
        exec(compile(method_module, filename=str(MENU_PY), mode='exec'), namespace)
        loaded[method_name] = namespace[method_name]
    return loaded


def _has_demo_prompt_draw_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute) or func.attr != 'draw':
            continue
        owner = func.value
        if not isinstance(owner, ast.Attribute) or owner.attr != '_demo_upgrade_prompt':
            continue
        if isinstance(owner.value, ast.Name) and owner.value.id == 'self':
            return True
    return False


class FakeRect:
    def __init__(self, left: int, top: int, width: int, height: int):
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        return (
            self.left <= pos[0] < self.left + self.width
            and self.top <= pos[1] < self.top + self.height
        )


class FakeMenu:
    pass


def _make_fake_menu(*, demo_locked: bool) -> FakeMenu:
    methods = _load_menu_methods(
        '_infer_pvp_option_side_from_rect',
        '_infer_coop_option_side_from_rect',
        '_resolve_main_split_mouse_action',
    )
    menu = FakeMenu()
    menu._pvp_split_selection = 'local'
    menu._coop_split_selection = 'local'
    menu.prompt_calls: list[str] = []
    menu._build_main_dashboard_layout = lambda: {
        'action_rect_map': {
            'pvp_2_players': FakeRect(100, 100, 300, 200),
            'coop_mode': FakeRect(500, 100, 300, 200),
        }
    }

    def _maybe_handle_demo_main_action(action_id: str) -> bool:
        menu.prompt_calls.append(action_id)
        return demo_locked

    menu._maybe_handle_demo_main_action = _maybe_handle_demo_main_action

    for method_name, method in methods.items():
        setattr(menu, method_name, types.MethodType(method, menu))

    return menu


def test_locked_online_pvp_click_uses_live_layout_and_opens_prompt() -> None:
    menu = _make_fake_menu(demo_locked=True)

    handled, action = menu._resolve_main_split_mouse_action((360, 180))

    assert (handled, action) == (True, None)
    assert menu._pvp_split_selection == 'online'
    assert menu.prompt_calls == ['online_pvp']


def test_locked_online_coop_click_uses_live_layout_and_opens_prompt() -> None:
    menu = _make_fake_menu(demo_locked=True)

    handled, action = menu._resolve_main_split_mouse_action((720, 180))

    assert (handled, action) == (True, None)
    assert menu._coop_split_selection == 'online'
    assert menu.prompt_calls == ['online_coop']


def test_local_pvp_click_stays_local() -> None:
    menu = _make_fake_menu(demo_locked=True)

    handled, action = menu._resolve_main_split_mouse_action((140, 260))

    assert (handled, action) == (True, 'pvp_2_players')
    assert menu._pvp_split_selection == 'local'
    assert menu.prompt_calls == []


def test_main_draw_renders_demo_prompt_outside_language_panel() -> None:
    draw_method = _get_menu_method('draw')
    language_panel_method = _get_menu_method('_draw_menu_language_panel')

    assert _has_demo_prompt_draw_call(draw_method), (
        'Menu.draw demo upgrade promptu cizmelidir; ana menude aktif olup gorunmez kalmamali.'
    )
    assert not _has_demo_prompt_draw_call(language_panel_method), (
        'Demo upgrade prompt cizimi dil paneline bagli olmamali; dil paneli kapaliyken de gorunmelidir.'
    )