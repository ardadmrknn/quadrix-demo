"""Tutorial hub çizim yolu için regresyon kapsamı (OP-024).

Ok butonu kompozit önbelleği, ders açıklaması memo'su ve (demo'da v2'den
taşınan) dot-glow helper'ı mevcut testlerle kurulup isabet alınması
gerekiyordu; phase8 testi tek kare çiziyor ve cache kurulumunu assert
etmiyor. Bu dosya çok kare draw + ders seçimi değişimi ile yolu çalıştırır.
Kurulum deseni test_phase8_tutorial_ui_scaling.py ile aynı.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tutorial as tutorial_module


def _get_tutorial_mode_class():
    for t_mod_name in ('tutorial', 'src.tutorial'):
        t_mod = sys.modules.get(t_mod_name)
        if t_mod is not None and hasattr(t_mod, 'TutorialMode'):
            return t_mod.TutorialMode
    return tutorial_module.TutorialMode


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
    cls = _get_tutorial_mode_class()
    tutorial = cls.__new__(cls)
    tutorial.screen = pygame.Surface(size, pygame.SRCALPHA)
    if window_size is None:
        window_size = size
    tutorial.window_width, tutorial.window_height = window_size
    tutorial.board_height = 20
    tutorial.get_board_offset = lambda: (420, 108)
    tutorial.get_cell_size = lambda: 24
    tutorial._tutorial_star_icon_base = None
    tutorial._tutorial_star_icon_cache = {}
    tutorial._tutorial_arrow_icon_left_base = None
    tutorial._tutorial_arrow_icon_right_base = None
    tutorial._tutorial_arrow_icon_cache = {}
    return tutorial


def _install_tutorial_draw_stubs(monkeypatch):
    def draw_glass_panel(surface, rect, alpha=0, border_color=(255, 255, 255), glow=False, **kwargs):
        pygame.draw.rect(surface, border_color[:3], rect, 1)

    # Gerçek retro_style.get_font gibi: aynı (size, bold) için ÖNBELLEKLİ
    # font döndür — aksi halde id(font) kare başına değişir ve memo testi
    # yapay olarak isabet alamaz.
    font_cache: dict = {}
    def _cached_get_font(size, bold=False):
        key = (int(size), bool(bold))
        font = font_cache.get(key)
        if font is None:
            font = _make_fake_font(size, bold=bold)
            font_cache[key] = font
        return font

    retro_style_stub = SimpleNamespace(
        draw_glass_panel=draw_glass_panel,
        draw_uniform_button=lambda surface, rect, label, sub_text='', color_code=None, selected=False, **kwargs: None,
        get_font=_cached_get_font,
        secondary=(220, 120, 120),
        success=(90, 220, 140),
        primary=(110, 160, 255),
        accent=(255, 180, 90),
        text_secondary=(200, 208, 220),
        text_muted=(130, 138, 150),
        render_fit_text=lambda text, color, max_width, size, bold=False: _make_fake_font(size, bold=bold).render(text, True, color),
    )

    for t_mod_name in ('tutorial', 'src.tutorial'):
        t_mod = sys.modules.get(t_mod_name)
        if t_mod is not None:
            monkeypatch.setattr(t_mod, 'retro_style', retro_style_stub)
            monkeypatch.setattr(t_mod, 't', lambda key, *args, **kwargs: kwargs.get('default', key))
            monkeypatch.setattr(t_mod, 'get_mouse_pos', lambda: (0, 0))
    return retro_style_stub


def _make_chapter_entries():
    return [
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
        },
        {
            'chapter': {
                'id': 'chapter-2',
                'title': 'Ileri',
                'description_fallback': 'Kart stratejisi.',
            },
            'unlocked': True,
            'completed_lessons': 0,
            'total_lessons': 1,
            'stars': 0,
            'completed': False,
        },
    ]


def _make_lesson_entries():
    return [
        {
            'lesson': {
                'id': 'lesson-1',
                'title': 'Saga Kaydir',
                'description': 'Parcayi guvenli sekilde saga tasi ve kenara yapis.',
            },
            'stars': 2,
            'completed': False,
            'duration_seconds': 45,
        },
        {
            'lesson': {
                'id': 'lesson-2',
                'title': 'Sola Kaydir',
                'description': 'Parcayi guvenli sekilde sola tasi.',
            },
            'stars': 0,
            'completed': False,
            'duration_seconds': 30,
        },
    ]


def test_tutorial_hub_draw_caches_and_desc_memo_hit(monkeypatch):
    _install_tutorial_draw_stubs(monkeypatch)

    tutorial = _build_tutorial((800, 600), window_size=(1366, 768))
    tutorial.hub_selected_chapter_id = 'chapter-1'
    tutorial.hub_selected_lesson_id = 'lesson-1'
    tutorial._get_total_tutorial_stars = lambda: 4
    tutorial._get_hub_chapter_entries = lambda: _make_chapter_entries()
    tutorial._get_hub_lesson_entries = lambda chapter_id: _make_lesson_entries()
    tutorial._lesson_title = lambda item=None: str((item or {}).get('title') or 'Ders')
    tutorial._lesson_description = lambda item: str(item.get('description') or '')
    tutorial._get_selected_hub_lesson_entry = lambda: _make_lesson_entries()[0]
    tutorial._lesson_index = lambda lesson_id: 1
    tutorial._lesson_type_label = lambda lesson_type: 'Temel'

    # Isınma kareleri: önbellekler kurulmalı. İlk karede modal ölçek bir
    # kez settle olabilir (ilk çağrıda farklı efektif ölçek) — anahtar iç
    # radius içerdiğinden settle yeni bir girdi üretir, sonra sabit kalır.
    tutorial._draw_tutorial_hub()
    tutorial._draw_tutorial_hub()
    arrow_cache = getattr(tutorial, '_hub_arrow_btn_cache', None)
    assert arrow_cache, 'ok butonu kompozit onbellegi kurulmali'
    desc_memo = getattr(tutorial, '_hub_desc_memo', None)
    assert desc_memo, 'ders aciklamasi memo su kurulmali'

    # Sıcak kareler: yeni anahtar eklenmemeli (isabet).
    arrow_count = len(arrow_cache)
    memo_count = len(desc_memo)
    for _ in range(3):
        tutorial._draw_tutorial_hub()
    assert len(arrow_cache) == arrow_count
    assert len(desc_memo) == memo_count

    # Ders seçimi değişimi: draw hatasız koşmalı ve ders listesi (her karede
    # tüm dersleri çizdiği için) lesson-2 açıklaması için memo girdisi
    # bulunmalı.
    tutorial.hub_selected_lesson_id = 'lesson-2'
    tutorial._get_selected_hub_lesson_entry = lambda: _make_lesson_entries()[1]
    tutorial._draw_tutorial_hub()
    assert any(key[0] == 'lesson-2' for key in desc_memo)

    # Dot glow helper'ı (demo'da v2'den taşındı) kurulmalı.
    dot_cache = getattr(tutorial, '_tutorial_dot_glow_cache', None)
    assert dot_cache, 'dot glow onbellegi kurulmali'
