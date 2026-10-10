# -*- coding: utf-8 -*-
"""OP-035 faz 2: online_pvp_game paylaşımlı render noktalarının sözleşmeleri.

Benimsenen noktalar (salt-okunur blit kümesi — `.copy()` varsayılan yolu
her yerde korunur):
- ``_draw_player_header``: isim / skor / satır / kontrol etiketi (7 render/kare:
  2 başlık çağrısı — rakipte controls_label='' boş bırakır);
- ``_draw_game`` VS etiketi;
- ``_draw_side_panel``: Hold/Next panel etiketleri + hold-used 'X'.

Sözleşmeler:
- draw yolları render_text_shared'ten gelir; render_text (kopyalı varsayılan
  yol) bu fonksiyonlarda ÇAĞRILMAZ;
- paylaşımlı yüzeye set_alpha/fill gibi mutasyon UYGULANMAZ (kirli alfa tüm
  LRU tüketicilerine yayılır — OP-025 mayını sınıfı);
- iki ardışık karede aynı (font, metin, renk) AYNI Surface objesini döndürür
  (LRU isabet kimliği);
- clear_text_cache sonrası yol yeniden ısınır, çizim bozulmaz.

Kalıp: test_online_pvp_combo_popup_cache draw idyomu (dummy sürücüler +
``__new__`` bare instance + blit kaydeden ekran stub'ı).
"""
from __future__ import annotations

import os
import pathlib
import sys
import types

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as pvp  # noqa: E402


class _Screen(pygame.Surface):
    """Gerçek çizim yüzeyi + blit kaydı — draw_glass_panel ve pygame.draw
    gerçek Surface gerektirdiğinden stub ekran bu dosyada kullanılamaz."""

    def __init__(self, size=(640, 480)):
        super().__init__(size, pygame.SRCALPHA)
        self.blit_calls = []

    def blit(self, source, dest, *args, **kwargs):
        try:
            pos = tuple(dest)
        except TypeError:
            pos = (dest.x, dest.y)
        self.blit_calls.append((source, pos))
        return super().blit(source, dest, *args, **kwargs)


class _RecordingSurface(pygame.Surface):
    """Mutasyon çağrılarını kaydeden yüzey — sentinel sözleşme denetimi."""

    def __init__(self, size):
        super().__init__(size, pygame.SRCALPHA)
        self.mutations = []

    def set_alpha(self, *a, **k):
        self.mutations.append('set_alpha')
        return super().set_alpha(*a, **k)

    def fill(self, *a, **k):
        self.mutations.append('fill')
        return super().fill(*a, **k)

    def set_at(self, *a, **k):
        self.mutations.append('set_at')
        return super().set_at(*a, **k)

    def scroll(self, *a, **k):
        self.mutations.append('scroll')
        return super().scroll(*a, **k)


def _make_game(screen):
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.screen = screen
    game._ui_scale = lambda *a, **k: 1.0
    game._sx = lambda *a, **k: (a[0] if a else 1)
    return game


def _draw_my_header(game):
    game._draw_player_header(pygame.Rect(40, 40, 300, 56), 'Kadir',
                             pvp.UIColors.NEON_CYAN, 12450, 37, 'WASD')


def _wrap_shared(monkeypatch):
    calls = []
    real = pvp.render_text_shared

    def counting_shared(font, text, aa, color, background=None):
        calls.append((str(text), aa, color))
        return real(font, text, aa, color, background)

    monkeypatch.setattr(pvp, 'render_text_shared', counting_shared)
    return calls


def _wrap_default(monkeypatch):
    calls = []

    def failing_default(font, text, aa, color, background=None):
        calls.append(str(text))
        return pvp.render_text(font, text, aa, color, background)

    monkeypatch.setattr(pvp, 'render_text', failing_default)
    return calls


def test_player_header_uses_shared_path(monkeypatch):
    shared = _wrap_shared(monkeypatch)
    default = _wrap_default(monkeypatch)

    screen = _Screen()
    game = _make_game(screen)
    _draw_my_header(game)
    game._draw_player_header(pygame.Rect(360, 40, 300, 56), 'Rakip',
                             pvp.UIColors.NEON_MAGENTA, 9840, 31, '')

    # my: isim + skor + satır + kontrol = 4; rakip: boş etiket 3 çağrı.
    assert len(shared) == 7, 'baslik kumesi tamamen shared yoldan gelmeli'
    texts = [c[0] for c in shared]
    assert 'Kadir' in texts and 'Rakip' in texts
    assert default == [], 'varsayilan (kopyali) yol bu fonksiyonda kalmamali'
    assert len(screen.blit_calls) >= 7, 'tum metinler blit edilmeli'


def test_player_header_never_mutates_shared_surface(monkeypatch):
    sentinel = _RecordingSurface((80, 24))
    monkeypatch.setattr(
        pvp, 'render_text_shared',
        lambda font, text, aa, color, background=None: sentinel)

    screen = _Screen()
    game = _make_game(screen)
    _draw_my_header(game)

    assert sentinel.mutations == [], (
        'paylasimli yuzeye mutasyon uygulanmamali (OP-025 mayini)'
    )
    assert len(screen.blit_calls) >= 4, 'sentinel blit kaynak olarak kullanilmali'


def test_shared_surfaces_identity_across_frames():
    screen = _Screen()
    game = _make_game(screen)
    _draw_my_header(game)
    first = [id(src) for src, _ in screen.blit_calls]

    screen.blit_calls.clear()
    _draw_my_header(game)
    second = [id(src) for src, _ in screen.blit_calls]

    assert first == second, (
        'ayni (font, metin, renk) iki karede AYNI yuzey objesini dondurmeli'
    )


def test_side_panel_labels_use_shared_path(monkeypatch):
    shared = _wrap_shared(monkeypatch)
    default = _wrap_default(monkeypatch)

    screen = _Screen()
    game = _make_game(screen)
    game.hold_piece = None
    game.hold_used = True
    game.next_piece = None
    game._draw_side_panel(40, 120, 28)

    texts = [c[0] for c in shared]
    assert len(shared) == 3, 'Hold + Next etiketleri + hold-used X'
    assert 'X' in texts, "hold-used 'X' etiketi shared yoldan gelmeli"
    assert default == [], 'panel etiketleri kopyali yolu kullanmamali'


def test_draw_game_vs_label_uses_shared_path(monkeypatch):
    shared = _wrap_shared(monkeypatch)
    default = _wrap_default(monkeypatch)

    # Agir alt-cizimleri stub'la: geriye layout + basliklar + VS kalir.
    for name in ('_draw_side_panel', '_draw_board', '_draw_opponent_board',
                 '_draw_combo_message_overlay', '_draw_pending_garbage_indicator',
                 '_draw_pause_overlay'):
        monkeypatch.setattr(pvp.OnlinePvPGame, name, lambda *a, **k: None)
    monkeypatch.setattr(pvp, 'draw_glass_panel', lambda *a, **k: None)

    screen = _Screen()
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.screen = screen
    game.window_width = 960
    game.window_height = 540
    game._ui_scale = lambda *a, **k: 1.0
    game._sx = lambda *a, **k: (a[0] if a else 1)
    game.get_shake_offset = lambda: (0, 0)
    game.net = types.SimpleNamespace(opponent_name='Rakip')
    game.my_board = types.SimpleNamespace(score=100, lines_cleared=5)
    game.my_piece = None
    game.game_over = False
    game._resolve_my_display_name = lambda: 'Ben'
    game.opponent_score = 0
    game.opponent_lines = 0
    game.paused = False
    game.opponent_paused = False
    game._draw_game()

    texts = [c[0] for c in shared]
    assert 'VS' in texts, 'VS etiketi render_text_shared yolundan gelmeli'
    assert 'Ben' in texts and 'Rakip' in texts, 'basliklar VS ile ayni yoldan'
    assert default == [], 'draw game metinleri kopyali yolu kullanmamali'


def test_shared_path_survives_cache_clear():
    screen = _Screen()
    game = _make_game(screen)
    _draw_my_header(game)
    n_before = len(screen.blit_calls)

    import text_cache
    text_cache.clear_text_cache()
    screen.blit_calls.clear()
    _draw_my_header(game)

    assert len(screen.blit_calls) == n_before, (
        'cache temizligi sonrasi yeniden isinma ayni cizimi uretmeli'
    )
