from __future__ import annotations

import types

import pygame

import user_screens


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)

    def get_size(self) -> tuple[int, int]:
        return self._size

    def set_size(self, width: int, height: int) -> None:
        self._size = (width, height)

    def get_width(self) -> int:
        return self._size[0]

    def get_height(self) -> int:
        return self._size[1]


class _DummyFx:
    def update(self, *args, **kwargs):
        return None

    def draw(self, *args, **kwargs):
        return None


class _DummyAvatarEditor:
    def __init__(self, screen):
        self.screen = screen

    def handle_event(self, event):
        return None

    def open_file_dialog(self):
        return None

    def save_avatar(self, target_name):
        return None

    def draw(self):
        return None


class _DummyFont:
    def __init__(self, size: int):
        self.size = size

    def render(self, *args, **kwargs):
        return types.SimpleNamespace(get_rect=lambda **kw: types.SimpleNamespace(**kw))


class _DummySteamService:
    def __init__(self, *args, **kwargs):
        return None

    def is_configured(self) -> bool:
        return False


class _DummyUserManager:
    def __init__(self):
        self.users = {
            'Ada': {
                'avatar': '__default__',
                'avatar_color': (100, 150, 255),
                'total_games': 12,
                'total_score': 34567,
                'total_lines': 789,
            },
            'Bora': {
                'avatar': '__default__',
                'avatar_color': (255, 120, 120),
                'total_games': 4,
                'total_score': 1234,
                'total_lines': 88,
            },
        }
        self.current_user = 'Ada'

    def get_all_users(self):
        return self.users

    def get_user_data(self, username):
        return dict(self.users.get(username, {}))

    def get_current_user(self):
        return self.current_user

    def select_user(self, username):
        self.current_user = username

    def get_favorite_card(self, username=None):
        return None

    def create_user(self, username, avatar):
        if username in self.users:
            return False, 'exists'
        self.users[username] = {
            'avatar': avatar,
            'avatar_color': (100, 150, 255),
            'total_games': 0,
            'total_score': 0,
            'total_lines': 0,
        }
        return True, 'created'

    def update_user_profile(self, username, avatar=None, avatar_color=None, bio=None, favorite_mode=None):
        if username not in self.users:
            return False, 'missing'
        data = self.users[username]
        if avatar is not None:
            data['avatar'] = avatar
        if avatar_color is not None:
            data['avatar_color'] = avatar_color
        if bio is not None:
            data['bio'] = bio
        if favorite_mode is not None:
            data['favorite_mode'] = favorite_mode
        return True, 'updated'

    def delete_user(self, username):
        if username not in self.users:
            return False, 'missing'
        del self.users[username]
        if self.current_user == username:
            self.current_user = next(iter(self.users), None)
        return True, 'deleted'


def _patch_user_screens(monkeypatch):
    monkeypatch.setattr(user_screens, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(user_screens, 'AvatarEditor', _DummyAvatarEditor)
    monkeypatch.setattr(user_screens, 'SteamLeaderboardService', _DummySteamService)
    monkeypatch.setattr(user_screens, 'get_avatar_entries', lambda: [{'value': '__default__'}])
    monkeypatch.setattr(user_screens.UserSelectionScreen, '_ensure_steam_avatar_async', lambda self: None)
    monkeypatch.setattr(user_screens.retro_style, 'get_font', lambda size, bold=True: _DummyFont(size))
    monkeypatch.setattr(user_screens.UIFonts, 'get', lambda size: _DummyFont(size))


def test_user_selection_ui_scale_preserves_1366_baseline(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserSelectionScreen(_FakeScreen(1366, 768), _DummyUserManager())

    assert abs(screen._ui_scale() - 1.0) < 0.001


def test_user_selection_responsive_metrics_grow_on_large_displays(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserSelectionScreen(_FakeScreen(2560, 1440), _DummyUserManager())
    screen._apply_responsive_metrics()

    assert screen._ui_scale() > 1.0
    assert screen.font_title_size > screen._base_font_title_size
    assert screen._sx(220) > 220


def test_user_selection_begin_edit_existing_keeps_entry_index_in_sync(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserSelectionScreen(_FakeScreen(1366, 768), _DummyUserManager())
    screen._begin_edit_existing('Bora')

    assert screen.selected_user == 2
    assert screen.get_selected_username() == 'Bora'


def test_user_selection_create_user_selects_created_entry(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserSelectionScreen(_FakeScreen(1366, 768), _DummyUserManager())
    screen.new_username = 'Cem'

    result = screen._attempt_create_user()

    assert result == 'new_user_created'
    assert screen.selected_user == 3
    assert screen.get_selected_username() == 'Cem'


def test_user_selection_delete_clamps_to_last_real_user(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserSelectionScreen(_FakeScreen(1366, 768), _DummyUserManager())
    screen.selected_user = 2

    screen._perform_delete_selected()

    assert screen.selected_user == 1
    assert screen.get_selected_username() == 'Ada'


def test_user_management_ui_scale_preserves_1366_baseline(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserManagementScreen(_FakeScreen(1366, 768), _DummyUserManager())

    assert abs(screen._ui_scale() - 1.0) < 0.001
    assert screen._list_layout_metrics()['card_height'] == 100


def test_user_management_list_metrics_grow_on_large_displays(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserManagementScreen(_FakeScreen(2560, 1440), _DummyUserManager())
    metrics = screen._list_layout_metrics()

    assert screen._ui_scale() > 1.0
    assert screen.font_title_size > screen._base_font_title_size
    assert metrics['header_height'] > 120
    assert metrics['card_height'] > 100
    assert metrics['card_width'] > 700


def test_user_management_list_click_uses_scaled_metrics(monkeypatch):
    _patch_user_screens(monkeypatch)

    screen = user_screens.UserManagementScreen(_FakeScreen(2560, 1440), _DummyUserManager())
    metrics = screen._list_layout_metrics()
    second_card_center = (
        metrics['card_x'] + metrics['card_width'] // 2,
        metrics['cards_start_y'] + metrics['card_height'] + metrics['gap'] + metrics['card_height'] // 2,
    )
    screen.selected_user = 0

    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=second_card_center)
    screen._handle_list_input(event)

    assert screen.selected_user == 1


def test_user_management_keyboard_navigation_keeps_selected_row_visible(monkeypatch):
    _patch_user_screens(monkeypatch)

    manager = _DummyUserManager()
    for username in ['Cem', 'Deniz', 'Ece', 'Fikret', 'Gizem', 'Hakan']:
        manager.users[username] = {
            'avatar': '__default__',
            'avatar_color': (100, 150, 255),
            'total_games': 0,
            'total_score': 0,
            'total_lines': 0,
        }

    screen = user_screens.UserManagementScreen(_FakeScreen(1366, 768), manager)

    for _ in range(6):
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        screen._handle_list_input(event)

    assert screen.selected_user == 6
    assert screen.scroll_offset == 1
    assert screen._visible_users()[0] == 'Bora'
