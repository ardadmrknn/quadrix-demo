from __future__ import annotations

import math
import pathlib
import sys
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tutorial as tutorial_module
from game_modes_extra import MysteryCardUI


TutorialMode = tutorial_module.TutorialMode


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
        return max(1, int(len(str(text or '')) * self._size * 0.55)), self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


def _build_tutorial(size: tuple[int, int], *, window_size: tuple[int, int] | None = None):
    tutorial = TutorialMode.__new__(TutorialMode)
    tutorial.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    tutorial.window_width, tutorial.window_height = window_size
    tutorial.board_height = 20
    tutorial.card_ui = MysteryCardUI()
    tutorial._tutorial_star_icon_base = None
    tutorial._tutorial_star_icon_cache = {}
    tutorial._tutorial_arrow_icon_left_base = None
    tutorial._tutorial_arrow_icon_right_base = None
    tutorial._tutorial_arrow_icon_cache = {}
    tutorial.get_board_offset = lambda: (420, 108)
    tutorial.get_cell_size = lambda: 24
    return tutorial


def _install_tutorial_draw_stubs(monkeypatch):
    captured_rects = []

    def draw_glass_panel(surface, rect, alpha=0, border_color=(255, 255, 255), glow=False, **kwargs):
        captured_rects.append(rect.copy())
        pygame.draw.rect(surface, border_color[:3], rect, 1)

    retro_style_stub = SimpleNamespace(
        draw_glass_panel=draw_glass_panel,
        draw_uniform_button=lambda surface, rect, label, sub_text='', color_code=None, selected=False, **kwargs: captured_rects.append(rect.copy()),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        secondary=(220, 120, 120),
        success=(90, 220, 140),
        primary=(110, 160, 255),
        accent=(255, 180, 90),
        text_secondary=(200, 208, 220),
        text_muted=(130, 138, 150),
        render_fit_text=lambda text, color, max_width, size, bold=False: _make_fake_font(size, bold=bold).render(text, True, color),
    )

    monkeypatch.setattr(tutorial_module, 'retro_style', retro_style_stub)
    monkeypatch.setattr(tutorial_module, 't', lambda key, *args, **kwargs: kwargs.get('default', key))
    monkeypatch.setattr(tutorial_module, 'get_mouse_pos', lambda: (0, 0))
    monkeypatch.setattr(tutorial_module.pygame.mouse, 'get_focused', lambda: False)
    monkeypatch.setattr(tutorial_module, 'get_tutorial_card_title', lambda card: str(card.get('title') or 'Kart'))
    monkeypatch.setattr(tutorial_module, 'get_tutorial_card_rarity_label', lambda card: 'Nadir')
    monkeypatch.setattr(tutorial_module, 'get_tutorial_card_type_label', lambda card: 'Tip')
    monkeypatch.setattr(tutorial_module, 'get_tutorial_card_description', lambda card: str(card.get('description') or 'Aciklama'))
    return captured_rects


def _assert_rects_within_surface(rects, size=(800, 600)):
    assert rects
    for rect in rects:
        assert rect.x >= 0
        assert rect.y >= 0
        assert rect.right <= size[0]
        assert rect.bottom <= size[1]


def test_tutorial_modal_scale_uses_active_canvas_and_preserves_1366_baseline():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    assert math.isclose(tutorial._tutorial_modal_scale(), 1.0)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    assert math.isclose(tutorial._tutorial_modal_scale(), 1.18)


def test_tutorial_card_font_pack_can_grow_above_one(monkeypatch):
    monkeypatch.setattr(tutorial_module, '_tutorial_make_card_ui_font', lambda size, bold=False: size)
    tutorial = _build_tutorial((1366, 768))

    baseline_fonts = tutorial._build_tutorial_card_ui_font_pack()
    assert baseline_fonts['heading'] == 44
    assert baseline_fonts['value'] == 52

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    tutorial.window_width = 2560
    tutorial.window_height = 1440

    grown_fonts = tutorial._build_tutorial_card_ui_font_pack()
    assert grown_fonts['heading'] > baseline_fonts['heading']
    assert grown_fonts['value'] > baseline_fonts['value']


def test_tutorial_overlay_rect_grows_with_modal_scale():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    baseline_rect = tutorial._tutorial_overlay_rect()
    assert baseline_rect.size == (260, 320)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    grown_rect = tutorial._tutorial_overlay_rect()
    assert grown_rect.width > baseline_rect.width
    assert grown_rect.height > baseline_rect.height


def test_tutorial_hub_panel_rect_grows_and_stays_centered():
    tutorial = _build_tutorial((1366, 768), window_size=(800, 600))

    baseline_rect = tutorial._tutorial_hub_panel_rect()
    assert baseline_rect.size == (1180, 720)

    tutorial.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)

    grown_rect = tutorial._tutorial_hub_panel_rect()
    assert grown_rect.width > baseline_rect.width
    assert grown_rect.height > baseline_rect.height
    assert grown_rect.center == (1280, 720)


def test_tutorial_card_overlay_reference_stays_on_phase8_baseline():
    tutorial = _build_tutorial((2560, 1440))

    tutorial._sync_tutorial_card_overlay_reference()

    assert tutorial.card_ui._overlay_base_size == (
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[0]),
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[1]),
    )
    assert math.isclose(tutorial.card_ui._get_overlay_scale(2560, 1440), 1.12)


def test_tutorial_resize_syncs_window_metrics_to_created_surface(monkeypatch):
    tutorial = _build_tutorial((1366, 768), window_size=(1366, 768))
    updated = {'called': False}

    monkeypatch.setattr(
        tutorial_module,
        'create_display',
        lambda width, height, fullscreen=False, resizable=True: pygame.Surface((2560, 1440), pygame.SRCALPHA),
    )
    tutorial.update_fonts = lambda: updated.__setitem__('called', True)

    tutorial._apply_tutorial_resize(1920, 1080)

    assert updated['called'] is True
    assert (tutorial.window_width, tutorial.window_height) == (2560, 1440)
    assert tutorial.card_ui._overlay_base_size == (
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[0]),
        int(tutorial_module.TUTORIAL_MODAL_REFERENCE_SIZE[1]),
    )


def test_tutorial_success_effects_use_active_canvas_center():
    tutorial = _build_tutorial((2560, 1440), window_size=(1366, 768))

    tutorial._create_success_effects()

    assert len(tutorial.success_particles) == 20
    assert all(1230 <= particle['x'] <= 1330 for particle in tutorial.success_particles)
    assert all(670 <= particle['y'] <= 770 for particle in tutorial.success_particles)


def test_tutorial_overlay_and_tip_panel_live_draw_use_active_canvas(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.lesson_catalog = [{'id': 'lesson-1'}]
    tutorial._lesson_index = lambda: 1
    tutorial.lesson_result_active = False
    tutorial.next_lesson_id = 'lesson-2'
    tutorial.in_transition = False
    tutorial.overlay_message = 'Aktif canvas test mesaji'
    tutorial.sub_message = 'Ilerleme bilgisi'
    tutorial.tip_message = 'Parcayi bosluk olusturmadan yerlestir.'
    tutorial.step = 1
    tutorial.step_move_left_count = 2
    tutorial.step_move_right_count = 1
    tutorial.step_rotate_count = 0
    tutorial.soft_drop_counter = 0
    tutorial.step_target = 3
    tutorial._get_board_lesson_objectives = lambda: [{'text': 'Satir acilimini koru'}]

    tutorial._draw_tutorial_overlay()

    assert len(captured_rects) >= 2
    _assert_rects_within_surface(captured_rects[:2])


def test_tutorial_tip_panel_shifted_above_does_not_overlap_main_rect(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 320), window_size=(1366, 768))
    tutorial.tip_message = 'Parcayi sola tasi ve boslugu T ile kapat.'
    tutorial._get_board_lesson_objectives = lambda: [
        {'text': 'En az 1 satir temizle'},
        {'text': 'Yeni delik olusturma'},
    ]

    main_rect = pygame.Rect(180, 170, 250, 105)
    tutorial._draw_tutorial_tip_panel(main_rect)

    rects = captured_rects[-2:]
    assert len(rects) == 2
    _assert_rects_within_surface(rects, size=(800, 320))
    assert all(not rect.colliderect(main_rect) for rect in rects)
    assert not rects[0].colliderect(rects[1])


def test_tutorial_overlay_shifts_up_to_preserve_support_block_positions(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 768), window_size=(1366, 768))
    tutorial.lesson_catalog = [{'id': 'lesson-1'}]
    tutorial._lesson_index = lambda: 1
    tutorial.lesson_result_active = False
    tutorial.next_lesson_id = 'lesson-2'
    tutorial.in_transition = False
    tutorial.overlay_message = 'Genis boslugu kapat'
    tutorial.sub_message = 'Hedef: Iki satiri ayni anda temizle.'
    tutorial.tip_message = 'Genis bosluklari okuyup dogru parcayi secmek kart modundaki kararlarin temelidir.'
    tutorial._get_board_lesson_objectives = lambda: [
        {'text': '2 satiri temizle'},
        {'text': 'Yeni delik olusturma'},
        {'text': 'Ideal yuksekligi artirma'},
    ]
    tutorial.step = 4
    tutorial.step_move_left_count = 0
    tutorial.step_move_right_count = 0
    tutorial.step_rotate_count = 0
    tutorial.soft_drop_counter = 0
    tutorial.step_target = 1
    tutorial.get_board_offset = lambda: (420, 315)

    tutorial._draw_tutorial_overlay()

    assert len(captured_rects) >= 3
    overlay_rect, obj_rect, tip_rect = captured_rects[-3:]
    _assert_rects_within_surface([overlay_rect, obj_rect, tip_rect], size=(800, 768))
    assert obj_rect.top >= overlay_rect.bottom
    assert tip_rect.top >= obj_rect.bottom


def test_tutorial_hub_live_draw_rects_stay_within_active_canvas(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.hub_selected_chapter_id = 'chapter-1'
    tutorial.hub_selected_lesson_id = 'lesson-1'
    tutorial._get_total_tutorial_stars = lambda: 4
    tutorial._get_hub_chapter_entries = lambda: [
        {
            'chapter': {
                'id': 'chapter-1',
                'title': 'Baslangic',
                'description_fallback': 'Temel hareketleri ogren.',
            },
            'unlocked': True,
            'completed_lessons': 1,
            'total_lessons': 1,
            'stars': 3,
            'completed': True,
        }
    ]
    tutorial._get_hub_lesson_entries = lambda chapter_id: [
        {
            'lesson': {
                'id': 'lesson-1',
                'title': 'Saga Kaydir',
                'description': 'Parcayi guvenli sekilde saga tasi.',
            },
            'stars': 2,
            'completed': False,
        }
    ]
    tutorial._lesson_title = lambda item=None: str((item or {}).get('title') or 'Ders')
    tutorial._lesson_description = lambda item: str(item.get('description') or '')

    tutorial._draw_tutorial_hub()

    _assert_rects_within_surface(captured_rects)
    assert tutorial.hub_back_rect.right <= 800
    assert tutorial.hub_start_rect.bottom <= 600


def test_tutorial_card_choice_overlay_fallback_live_draw_uses_active_canvas(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.card_ui = None
    tutorial.card_choice_state = {
        'scenario': {
            'context_lines': ['Durumu incele', 'En guvenli karti sec'],
            'choices': [
                {'title': 'Kart A', 'description': 'Tetikleme aciklamasi'},
                {'title': 'Kart B', 'description': 'Dengeleyici etki'},
            ],
        },
        'selected_index': 1,
    }
    tutorial._lesson_title = lambda lesson=None: 'Kart Secimi'

    tutorial._draw_card_choice_overlay()

    assert len(captured_rects) >= 3
    _assert_rects_within_surface(captured_rects)


def test_tutorial_card_choice_overlay_uses_plain_header_title(monkeypatch):
    recorded = {}

    monkeypatch.setattr(tutorial_module, '_tutorial_make_card_ui_font', lambda size, bold=False: _make_fake_font(size, bold=bold))

    class CardUIStub:
        card_rects = []

        def draw_selection_overlay(self, screen, width, height, fonts, choices, hint, debug_enabled, **kwargs):
            recorded['header_title'] = kwargs.get('header_title')
            recorded['center_header'] = kwargs.get('center_header')
            recorded['width'] = width
            recorded['height'] = height

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.card_ui = CardUIStub()
    tutorial.card_choice_state = {
        'scenario': {
            'context_lines': ['Durumu incele', 'En iyi uzun vadeli karti sec'],
            'choices': [
                {'title': 'Kart A', 'description': 'Tetikleme aciklamasi'},
                {'title': 'Kart B', 'description': 'Dengeleyici etki'},
            ],
        },
        'selected_index': 0,
    }
    tutorial._lesson_title = lambda lesson=None: 'Uzun vadeli deger'

    monkeypatch.setattr(tutorial_module.pygame.mouse, 'get_focused', lambda: False)

    tutorial._draw_card_choice_overlay()

    assert recorded['header_title'] == 'Uzun vadeli deger'
    assert '❗' not in recorded['header_title']
    assert recorded['center_header'] is True
    assert recorded['width'] == 800
    assert recorded['height'] == 600


def test_tutorial_card_choice_keyboard_is_blocked_while_peek_active(monkeypatch):
    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.game_over = False
    tutorial.show_exit_prompt = False
    tutorial.hub_active = False
    tutorial.lesson_result_active = False
    tutorial.waiting_for_enter = False
    tutorial.in_transition = False
    tutorial.user_manager = None
    tutorial.control_bindings = {}
    tutorial.card_choice_state = {'selected_index': 1}
    tutorial._is_card_choice_lesson_active = lambda: True
    tutorial._is_scenario_lesson_active = lambda: False
    tutorial._action_keys = lambda _bindings, _action: ()
    tutorial._queue_card_choice_selection = lambda _index: (_ for _ in ()).throw(AssertionError('Peek acikken secim kuyuga alinmamali'))
    tutorial._move_card_choice_selection = lambda _delta: (_ for _ in ()).throw(AssertionError('Peek acikken gezinme olmamali'))
    tutorial.card_ui = MysteryCardUI()
    tutorial.card_ui.peek_mode_active = True

    monkeypatch.setattr(tutorial_module.pygame.event, 'get', lambda: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)])

    result = tutorial.handle_input()

    assert result is True


def test_tutorial_lesson_result_panel_live_draw_uses_active_canvas(monkeypatch):
    captured_rects = _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.lesson_result = {
        'success': True,
        'title': 'Ders Sonucu',
        'stars': 2,
        'feedback': 'Hamle akisi guclendi.',
        'objective_results': [
            {'text': 'Tek bosluk birakma', 'passed': True},
            {'text': 'Satir yuksekligini kontrol et', 'passed': False},
        ],
        'coach_text': 'Bir sonraki denemede delik sayisini azalt.',
        'line_delta': 1,
        'hole_delta': -1,
        'height_delta': 0,
        'action_text': 'ENTER',
    }

    tutorial._draw_lesson_result_panel()

    assert len(captured_rects) == 1
    _assert_rects_within_surface(captured_rects)