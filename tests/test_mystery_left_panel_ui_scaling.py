from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game_modes_extra as extra_modes_module


class _FakeFont:
    def __init__(self, size: int):
        self._size = max(1, int(size))

    def render(self, text, antialias, color):
        width, height = self.size(text)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rgb = tuple(color[:3]) if isinstance(color, tuple) else (255, 255, 255)
        surface.fill((*rgb, 255))
        return surface

    def size(self, text):
        text_width = max(1, int(len(str(text or '')) * self._size * 0.55))
        return text_width, self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


def _install_extra_mode_ui_test_stubs(monkeypatch):
    retro_style_stub = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        primary=(110, 160, 255),
        secondary=(220, 120, 120),
        accent=(100, 200, 255),
        success=(90, 220, 140),
        text_primary=(255, 255, 255),
        text_secondary=(190, 190, 210),
        text_muted=(130, 130, 150),
        glass_border=(255, 255, 255, 255),
        grid_color=(80, 80, 100),
        bg_color=(12, 16, 24),
    )
    monkeypatch.setattr(extra_modes_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(extra_modes_module, 'get_language', lambda: 'xx')
    monkeypatch.setattr(extra_modes_module, 't', lambda key, *args, **kwargs: kwargs.get('default', str(key).replace('_', ' ')))
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'get_focused', lambda: False)
    monkeypatch.setattr(extra_modes_module.pygame.mouse, 'set_visible', lambda *args, **kwargs: None)
    monkeypatch.setattr(extra_modes_module, 'get_mouse_pos', lambda: (0, 0))


def _build_mystery_mode(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    mode.window_width, mode.window_height = window_size
    mode._card_ui_reference_size = extra_modes_module.MYSTERY_OVERLAY_REFERENCE_SIZE
    mode._card_ui_readable_min_size = (1180, 760)
    return mode


def test_mystery_active_card_rows_scale_with_canvas_and_stay_inside_panel(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    cards = [
        {
            'id': 'time_capsule',
            'title': 'Sekil Degistirici',
            'status': 'R: Kaydet',
            'color': (120, 220, 255),
            'icon': 'R',
            'icon_image': None,
            'tag': 'limited',
            'rarity': 'rare',
        },
        {
            'id': 'hold_destroyer',
            'title': 'Tuttugunu Koparan',
            'status': 'B: 3 Hak',
            'color': (255, 210, 120),
            'icon': 'B',
            'icon_image': None,
            'tag': 'limited',
            'rarity': 'epic',
        },
    ]

    snapshots_by_size = {}
    for size in ((800, 600), (2560, 1600)):
        mode = _build_mystery_mode(size, window_size=(1366, 768))
        mode.board_width = 10
        mode.board_height = 20
        mode.left_panel_max_width = 420
        mode.board = SimpleNamespace(level=1, lines_cleared=0)
        mode._draw_hud_glass_panel = lambda rect: None
        mode._sync_active_cards = lambda: None
        mode.card_manager = SimpleNamespace(
            active_cards=cards,
            threshold=5,
            get_status=lambda: {'hint': 'Kartlar eslesir'},
        )
        mode.card_ui = extra_modes_module.MysteryCardUI()

        metrics = mode._get_mystery_layout_metrics()
        mode._hud_panel_rect = pygame.Rect(
            int(metrics['panel_x']),
            int(metrics['panel_y']),
            int(metrics['panel_width']),
            int(metrics['panel_height']),
        )

        extra_modes_module.MysteryMode._draw_status_panel(mode)
        extra_modes_module.MysteryMode.draw_mode_info(mode, 0, 0)

        snapshots = mode.card_ui.active_card_row_snapshots
        snapshots_by_size[size] = snapshots

        assert len(snapshots) == len(cards)
        for snapshot in snapshots:
            row_rect = snapshot['row_rect']
            icon_rect = snapshot['icon_rect']
            title_rect = snapshot['title_rect']
            badge_rect = snapshot['badge_rect']

            assert mode._active_cards_panel_rect.contains(row_rect)
            assert title_rect is not None
            assert badge_rect is not None
            assert row_rect.height > icon_rect.height
            assert title_rect.left >= icon_rect.right
            assert title_rect.right <= badge_rect.left
            assert badge_rect.right <= row_rect.right - snapshot['content_padding'] + 1
            assert row_rect.top <= badge_rect.top < badge_rect.bottom <= row_rect.bottom

    assert snapshots_by_size[(2560, 1600)][0]['row_rect'].height > snapshots_by_size[(800, 600)][0]['row_rect'].height
    assert snapshots_by_size[(2560, 1600)][0]['icon_rect'].height > snapshots_by_size[(800, 600)][0]['icon_rect'].height
    assert snapshots_by_size[(2560, 1600)][0]['badge_rect'].height > snapshots_by_size[(800, 600)][0]['badge_rect'].height


def test_mystery_left_panels_extend_left_and_use_smaller_fonts(monkeypatch):
    _install_extra_mode_ui_test_stubs(monkeypatch)

    mode = _build_mystery_mode((2560, 1600), window_size=(1366, 768))
    mode._make_card_ui_font = lambda size, bold=False: _make_fake_font(size, bold=bold)
    mode.board_width = 10
    mode.board_height = 20
    mode.left_panel_max_width = 420
    mode.board = SimpleNamespace(level=1, lines_cleared=0)
    mode.card_manager = SimpleNamespace(threshold=5, get_status=lambda: {'hint': 'Kartlar eslesir'})

    metrics = mode._get_mystery_layout_metrics()
    board_x, _ = mode.get_board_offset()
    panel_gap = int(metrics['panel_gap'])
    panel_x, panel_y, panel_width = mode._get_left_panel_frame()

    assert panel_width > int(metrics['left_panel_width'])
    assert abs((panel_x + panel_width) - (board_x - panel_gap)) <= 1

    ui_scale = mode._card_ui_scale()
    base_fonts = mode._build_card_ui_font_pack(ui_scale)
    left_fonts = mode._build_left_panel_font_pack(ui_scale)

    assert left_fonts['heading'].get_height() == base_fonts['heading'].get_height() - 1
    assert left_fonts['panel_header'].get_height() == base_fonts['panel_header'].get_height() - 1
    assert left_fonts['small'].get_height() == base_fonts['small'].get_height() - 1
    assert left_fonts['card_title'].get_height() == base_fonts['card_title'].get_height() - 1
    assert left_fonts['tag'].get_height() == base_fonts['tag'].get_height() - 1