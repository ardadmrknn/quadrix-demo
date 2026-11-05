# -*- coding: utf-8 -*-
"""I-56 devamı — Tüm panellerin tavan çizgisi tahtanın TOPLAM tepesine hizalı.

Sözleşme (kullanıcı kararı, kırmızı çerçeve — 2026-11-05):

    board_top = (H - 22*cell) // 2          # dikey orta, top_shift = 0
    sol_panel_top = sag_HUD_top ~= board_top

Kırmızı çerçeve ölçümü (1080p): görünür alan 152–1016, genişlik 10*43=430,
yükseklik 20*43=860. Ortalanmış 22 satırlık blok 67'de başlar; görünür tepe
67 + 2*43 = 153 ve alt 1013 — ölçülen çerçeveyle birebir.

`Game.get_board_offset()` I-46'dan sonra GÖRÜNÜR alanın tepesini döndürür
(`layout.visible_top_y`), gizli bant bunun üstündedir. Bir tüketici gizli bant
yüksekliğini çıkarmayı unutursa panel tam `hidden_rows * cell` piksel aşağı
kayar — 1080p'de 86 px. Bu testler o hatanın geri gelmesini engeller.

Regresyon kaynağı: `get_board_offset` sözleşmesi görünür tepeye döndüğünde,
onu doğrudan panel Y'si olarak kullanan üç site (canlılık paneli, günlük
paneli, Mystery sol paneli) sessizce 2 satır aşağı kaydı.
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gameplay_layout import (  # noqa: E402
    HIDDEN_ROWS,
    compute_single_player_layout,
)

pytestmark = pytest.mark.quadrix_feedback

RESOLUTIONS = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
]


def _layout(width, height):
    return compute_single_player_layout(
        active_size=(width, height),
        effective_size=(width, height),
        board_width=10,
        board_height=20,
    )


@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_visible_top_minus_hidden_band_is_total_board_top(width, height):
    """`visible_top_y - hidden*cell == board_y` — panel tavanı buradan türer."""
    m = _layout(width, height)
    hidden_px = m.hidden_rows * m.cell_size
    assert hidden_px > 0, 'gizli bant yüksekliği sıfır olamaz'
    assert m.visible_top_y - hidden_px == m.board_y
    assert m.hidden_rows == HIDDEN_ROWS


@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_board_block_is_vertically_centered(width, height):
    """Kullanıcının kırmızı çerçevesi: 22 satırlık blok eşit üst/alt payla ortada.

    Ölçüm (1080p): hedef görünür tepe 152, alt 1016; `(H - 22*cell)//2 = 67`
    → görünür tepe 67 + 2*43 = 153. Tahta ekranın dikey ortasına oturur.
    """
    m = _layout(width, height)
    total_rows = m.hidden_rows + 20
    centered = (height - total_rows * m.cell_size) // 2
    assert m.board_y == centered, (
        f'{width}x{height}: blok tepesi {m.board_y}, ortalanmış olması gereken '
        f'{centered} — oyun alanı dikey ortada olmalı'
    )
    # Üst ve alt pay eşit: tahta ne yukarı ne aşağı kaymış.
    bottom_pad = height - (m.board_y + total_rows * m.cell_size)
    assert bottom_pad == m.board_y, (
        f'{width}x{height}: üst pay {m.board_y} != alt pay {bottom_pad}'
    )
    # Tahta alt kenarı ekrandan taşmamalı.
    assert m.board_y + total_rows * m.cell_size <= height


@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_right_hud_ceiling_equals_board_ceiling(width, height):
    """Sağ HUD, tahtanın toplam tepesinden türer (I-54 düzeltmesinin kilidi)."""
    m = _layout(width, height)
    assert m.panel_y == m.board_y + 10 or 0 < m.panel_y - m.board_y <= 16


def _source(name):
    return (SRC_DIR / name).read_text(encoding='utf-8')


BOARD_TOP_NAMES = {'board_y', 'board_offset_y'}


def _calls_hidden_rows_px(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if (isinstance(func, ast.Attribute)
                    and func.attr == '_hidden_rows_px'):
                return True
    return False


def _names_read(node):
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}


def _refs_read(node):
    """Adlar + `metrics['panel_y']` gibi abonelik anahtarları."""
    refs = _names_read(node)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
            if isinstance(sub.slice.value, str):
                refs.add(sub.slice.value)
    return refs


def _panel_assignments(module):
    """`panel_y`'ye atama yapan düğümler (satır, hedef_adlar, okunan_adlar)."""
    tree = ast.parse(_source(module))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        out.append((node.lineno, targets, _names_read(node.value), node.value))
    return out


def _ceiling_names(module):
    """Gizli bandı çıkaran ara değişkenler (ör. `panel_ceiling_y`, `ceiling_y`)."""
    return {
        name
        for _, targets, _, value in _panel_assignments(module)
        if _calls_hidden_rows_px(value)
        for name in targets
    } - {'panel_y'}


@pytest.mark.parametrize('module', ['game_modes.py', 'game_modes_advanced.py'])
def test_board_relative_panel_ys_subtract_hidden_band(module):
    """`board_offset_y` / `board_y` doğrudan kullanan panel Y'leri bandı çıkarır.

    `get_board_offset()` GÖRÜNÜR alanın tepesini döndürür; doğrudan panel Y'si
    yapılırsa panel tam `hidden_rows * cell` piksel aşağı kayar. Çıkarma ya
    çağrının kendisinde ya da `ceiling_y` gibi bir ara değişkende olmalı.
    Kendini clamp'leyen (`panel_y = min(panel_y, ...)`) satırlar atlanır.
    """
    aligned_names = _ceiling_names(module)
    violations = []
    for line, targets, read, value in _panel_assignments(module):
        if 'panel_y' not in targets:
            continue
        if 'panel_y' in read:  # clamp satırı, yeniden türetmiyor
            continue
        if not (read & BOARD_TOP_NAMES):  # tahtaya doğrudan bağlı değil
            continue
        if _calls_hidden_rows_px(value) or (read & aligned_names):
            continue
        violations.append(line)

    assert not violations, (
        f'{module}: satır {violations} tahtanın görünür tepesini doğrudan '
        'kullanıyor — gizli bant çıkarılmalı (`- self._hidden_rows_px(...)`)'
    )


def test_mystery_left_panel_ceiling_subtracts_hidden_band():
    """Mystery sol paneli tavanı: `get_board_offset()` - gizli bant."""
    source = _source('game_modes_extra.py')
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_get_left_panel_frame':
            target = node
            break
    assert target is not None, 'MysteryMode._get_left_panel_frame bulunamadı'

    subtracts = False
    for node in ast.walk(target):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if 'ceiling_y' in names and _calls_hidden_rows_px(node.value):
                subtracts = True
    assert subtracts, (
        'Mystery sol paneli gizli bandı çıkarmıyor — panel 2 satır aşağı kayar'
    )


def _left_panel_frame_tree(module='game_modes_extra.py'):
    tree = ast.parse(_source(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_get_left_panel_frame':
            return node
    raise AssertionError('MysteryMode._get_left_panel_frame bulunamadı')


def test_mystery_left_panel_hud_fallback_uses_layout_inset():
    """HUD henüz çizilmediğinde de tavan HUD çizgisine oturmalı.

    Fallback dalı bir zamanlar `ceiling_y - 20*ui_scale` idi; bu, paneli sağ
    HUD'un 33 px üstüne çıkarıp tavan hizasını bozuyordu. İç boşluk artık
    yerleşimin kendi `panel_y - board_y` farkından türetilir (sabit piksel yok).
    """
    func = _left_panel_frame_tree()
    else_branches = [
        node.orelse
        for node in ast.walk(func)
        if isinstance(node, ast.If) and node.orelse
    ]
    assert else_branches, 'fallback dalı (else) bulunamadı'

    derived = False
    for body in else_branches:
        for stmt in body:
            if not isinstance(stmt, ast.Assign):
                continue
            if 'hud_inset' not in {t.id for t in stmt.targets if isinstance(t, ast.Name)}:
                continue
            if {'panel_y', 'board_y'} <= _refs_read(stmt.value):
                derived = True
    assert derived, (
        'fallback dalı yerleşim iç boşluğundan (panel_y - board_y) türetmiyor; '
        'sabit piksel/ofset tavanı HUD çizgisinden ayırır'
    )