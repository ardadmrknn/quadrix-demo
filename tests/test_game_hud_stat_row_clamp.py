# -*- coding: utf-8 -*-
"""P2: game.py sağ HUD draw_stat_row dikey etiket slot-clamp guard'ı.

Kılavuz: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md P2 (ölçekleme
dalgasının ertelenenler notu): paylaşılan Game._fit_hud_stat_row YATAY
modda value_floor ile oransal küçültme yapar ve dikey fallback'te yalnız
DEĞERİ ellipsis'ler; aşırı dar içerik bütçesinde (640x360 + büyük preset)
ETİKET satır genişliğini aşabiliyordu. Hardcore sağ paneli (P1-1) bu kenar
durumu draw-zamanı guard'ıyla kapatmıştı ("game.py dokunulmaz" bilinçli
erteleme notuyla); bu dosya game.py'nin aynı desene kavuştuğunu kilitler
(P2 dikey slot-clamp): draw_stat_row etiketi avail_w'yi aşarsa önbellekli
_ellipsis_text ile kısaltır — plan sözleşmesi değişmez.

Üç katman:
- plan sözleşmesi: DEĞER daima avail_w içinde (dikey ve yatay modda);
  yatay fitted modda etiket+değer+gap toplamı bütçede;
- ihlal ÜRETİLEBİLİRLİĞİ: etiketin avail_w'yi aştığı gerçek girdi mevcut
  (guard'ın neden var olduğunun kanıtı — vaküoz değil);
- kaynak sözleşmesi: guard draw_stat_row gövdesinde; etiket render_text
  LRU'sundan (ham font.render değil — kare-başı tahsis yasağı).

Ölçüm sınırı (dürüst rapor): draw_stat_row closure olduğundan doğrudan
çağrılamaz; davranış guard ile aynı _ellipsis_text yoluyla ölçülür,
draw-zamanı varlık kaynak piniyle kanıtlanır. Gerçek görsel doğrulama
rapor §11'deki manuel Windows smoke'a aittir.

Kalıp: test_hardcore_hud_stat_containment.py (plan-düzeyi parametrize +
kaynak pin + stub-sızıntı dayanıklılığı).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import game as game_module
from game import Game

if not pygame.font.get_init():
    pygame.font.init()


def _retro_style_stub_leaked() -> bool:
    """Bilinen harness izolasyon kirliliği (rapor §10): önceki test dosyaları
    game.py global `retro_style`'ını veya sys.modules['retro_style']'ı
    _FakeFont tabanlı stub'la değiştirebiliyor. Ölçüm testleri gerçek font
    metriği ister; sızıntı varsa gerekçeli skip edilir, kaynak pin koşar."""
    candidates = []
    game_rs = getattr(game_module, 'retro_style', None)
    if game_rs is not None:
        candidates.append(game_rs)
    rs_module = sys.modules.get('retro_style')
    if rs_module is not None:
        candidates.append(getattr(rs_module, 'retro_style', rs_module))
    for rs in candidates:
        try:
            probe = rs.get_font(16)
        except Exception:
            return True
        if not isinstance(probe, pygame.font.Font):
            return True
    return False


def _skip_if_stub_leaked():
    if _retro_style_stub_leaked():
        pytest.skip("retro_style stub sızıntısı — bilinen harness izolasyon sorunu (rapor §10)")


def _make_game() -> Game:
    """Bare Game: _fit_hud_stat_row/_ellipsis_text yalnız statik
    yardımcıları ve global retro_style'ı kullanır."""
    return Game.__new__(Game)


# ── Plan sözleşmesi: değer daima bütçede ────────────────────────────────────

PLAN_CASES = [
    # (content_w, hud, label, value) — gerçekçi HUD bütçeleri + uçlar
    (240, 1.0, "SKOR", "9.999.999"),
    (240, 1.16, "SCORE", "12.345.678"),
    (160, 1.0, "SATIR", "999999"),
    (133, 0.72, "SATIR", "999999"),
    (96, 1.0, "SEVİYE", "99"),
    (64, 1.0, "LEVEL", "9.999.999"),
    (64, 2.065, "SEVİYE", "123.456.789"),
    (56, 1.16, "LINES CLEARED", "9999999"),
    (48, 1.0, "PUNKTE", "12.345.678"),
]


@pytest.mark.parametrize("content_w,hud,label,value", PLAN_CASES)
def test_plan_value_always_within_budget(content_w, hud, label, value):
    _skip_if_stub_leaked()
    game = _make_game()
    plan = game._fit_hud_stat_row(label, value, content_w, hud)

    # Dikey modda değer ellipsis'lenir; yatay fitted modda toplam sığar —
    # iki durumda da DEĞER satır bütçesinin dışına çıkmaz.
    assert plan['value_w'] <= plan['avail_w'], (plan['value_w'], plan['avail_w'])
    if not plan['vertical']:
        assert plan['label_w'] + plan['row_gap'] + plan['value_w'] <= plan['avail_w']


# ── İhlal üretilebilirliği: guard'ın varlık nedenı ──────────────────────────


def test_label_overflow_case_exists():
    """Plan dikey moda düştüğünde ETİKET tek başına avail_w'yi aşabiliyor
    (değer ellipsis'lenir, etiket plan tarafından sınırlanmaz). Bu girdi
    mevcut olmalı — aksi halde guard vaküoz olurdu."""
    _skip_if_stub_leaked()
    game = _make_game()
    plan = game._fit_hud_stat_row("LINES CLEARED", "9", 48, 1.0)

    assert plan['vertical'] is True
    assert plan['label_w'] > plan['avail_w'], (
        plan['label_w'], plan['avail_w'],
        'etiket taşması üretilemiyor — guard testi vaküozleşir')


def test_guard_path_clamps_label_to_budget():
    """Guard'ın kapattığı ihlali kapattığı yol: _ellipsis_text ile kısaltılan
    etiket, planın etiket fontuyla ölçüldüğünde avail_w içinde kalır."""
    _skip_if_stub_leaked()
    game = _make_game()
    plan = game._fit_hud_stat_row("LINES CLEARED", "9", 48, 1.0)
    clamped = game._ellipsis_text(plan['label_text'], plan['label_font'], plan['avail_w'])

    assert clamped.endswith('...') or len(clamped) < len(plan['label_text'])
    assert plan['label_font'].size(clamped)[0] <= plan['avail_w']


# ── Kaynak sözleşmesi: guard draw_stat_row gövdesinde ───────────────────────


def _draw_stat_row_source() -> str:
    source = pathlib.Path(game_module.__file__).read_text(encoding="utf-8")
    start = source.index("        def draw_stat_row(")
    nxt = re.search(r"\n        def ", source[start + 10:])
    end = start + 10 + (nxt.start() if nxt else len(source) - start - 10)
    return source[start:end]


def test_source_guard_present():
    src = _draw_stat_row_source()
    assert "plan['label_w'] > plan['avail_w']" in src
    assert "_ellipsis_text(label_text, plan['label_font'], plan['avail_w'])" in src


def test_source_label_uses_cached_render():
    """Etiket LRU yolundan (kare-başı tahsis yasağı); değer bilinçli ham
    render (skor sık değişir — cache churn gerekçesi korunur)."""
    src = _draw_stat_row_source()
    assert "render_text(plan['label_font']" in src
    assert "plan['label_font'].render(" not in src
    # Guard ellipsis'ten SONRA ölçülür: kısaltılmış metin render edilir.
    assert src.index("_ellipsis_text(label_text") < src.index("render_text(plan['label_font']")
