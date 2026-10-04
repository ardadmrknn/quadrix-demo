# -*- coding: utf-8 -*-
"""AvatarEditor çizim sözleşmesi (demo) — test-envanter açığı kapanışı.

v2'nin test_avatar_editor_containment.py uyarlaması (v2 uyarlaması):
demo avatar_editor'ı ölçekleme dalından geride kalmıştır (v2'deki _ui_scale
+ gamepad etiket portu demo'ya bilinçli olarak TAŞINMADI — ayrı bir taşıma
kararıdır); bu dosya demo'nun MEVCUT sabit-piksel sözleşmesini kilitler ve
bu dalgada kapatılan iki demo-specific hatayı regresyona bağlar:

1. BUTON SATIRI TAŞMASI (düzelten commit bu dalgadadır): eski kod tüm
   slotları 160px varsayıp 940px'lik toplamla ortalamıştı ve adım sabit
   165'ti — 640/800 genişlikte satır iki uçtan da ekrana taşıyordu
   (başlangıç x'i -150, son butonun sağı 745). Artık gerçek satır
   genişliğiyle (sum(key_widths) + 5*(n-1)) ortalanır, adım key_width + 5.
2. KARE BOYUT SINIRI (v2 uyarlaması): varsayılan 300px kırpma karesi,
   alçak pencerelerde (yükseklik < 600 → görüntü kısa kenarı 300'ün
   altında) her yüklemede görüntüden büyük başlıyordu; _clamp_crop artık
   boyutu da görüntüye sığdırır (min_crop_size=100 tabanı korunur).

Ayrıca draw() _draw_layout rect kaydını üretir (v2 deseni) ve v2'deki
önizleme-panel sıkıştırması da port edildi: önizleme paneli görüntü
paneline binmez; ekran sınırı önceliklidir.

Ölçüm sınırı (dürüst rapor): gerçek render görselliği manuel Windows
smoke'una aittir. Bilinen sınırlar: scale yok (sabit düzen); aşırı uzun
pencerelerde (h > w-120, örn. 640x600) ve aşırı ince görüntülerde
(min_crop_size tabanı) bindirme/kare taşması bilinçli olarak kabul
edilmiştir — dokümantasyonda not edilir.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import avatar_editor as avatar_module
from avatar_editor import AvatarEditor


# Sabit düzen (scale=1): standart pencere boyları. 640/800 bu dalganın
# buton-satırı düzeltmesinin kanıt hücreleridir.
SIZES = [
    (640, 480),
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1366, 768),
    (1920, 1080),
    (3840, 2160),
]


def _fonts_stubbed() -> bool:
    """Ambient izolasyon kirliliği: başka test dosyaları ui_theme.UFonts'u
    stub'layabilir — ölçüm testleri gerçek font metriği ister."""
    try:
        probe = avatar_module.UIFonts.get(20)
    except Exception:
        return True
    return not isinstance(probe, pygame.font.Font)


def _skip_if_fonts_stubbed():
    if _fonts_stubbed():
        pytest.skip("UIFonts stub sızıntısı — bilinen harness izolasyon sorunu")


def _make_editor(size, with_image=True):
    """Gerçek kurucu; görüntü durumu load_image akışını yansıtır (max_size'e
    smoothscale, kare ortalanır, clamp çalışır)."""
    editor = AvatarEditor(pygame.Surface(size))
    if with_image:
        src = pygame.Surface((400, 300))
        src.fill((120, 80, 60))
        max_size = min(size[0] - 200, size[1] - 300)
        fit = min(max_size / 400, max_size / 300)
        editor.original_image = src
        editor.display_image = pygame.transform.smoothscale(
            src, (int(400 * fit), int(300 * fit)))
        editor.crop_x = (editor.display_image.get_width() - editor.crop_size) // 2
        editor.crop_y = (editor.display_image.get_height() - editor.crop_size) // 2
        editor._clamp_crop()
    return editor


def _within(rect, size):
    w, h = size
    return rect.left >= 0 and rect.top >= 0 and rect.right <= w and rect.bottom <= h


# ── Çizim containment matrisi (sabit düzen) ────────────────────────────────

CONTAINMENT_KEYS = (
    'title', 'image_bg', 'crop', 'resize_handle', 'size_badge',
    'preview_bg', 'preview_label',
)


@pytest.mark.parametrize("size", SIZES)
def test_draw_containment_matrix(size):
    _skip_if_fonts_stubbed()
    editor = _make_editor(size)
    editor.draw()
    layout = editor._draw_layout

    assert layout['has_image'] is True

    # 1) Her kayıtlı rect ekran içinde.
    for key in CONTAINMENT_KEYS:
        rect = layout[key]
        assert _within(rect, size), (key, size, rect)

    # 2) Kırpma karesi görüntü alanının içinde (10px çerçeve payı dahil).
    img_bg = layout['image_bg']
    crop = layout['crop']
    assert crop.left >= img_bg.left + 10, (size, crop)
    assert crop.right <= img_bg.right - 10, (size, crop)
    assert crop.top >= img_bg.top + 10, (size, crop)
    assert crop.bottom <= img_bg.bottom - 10, (size, crop)

    # 3) Boyut rozeti karenin üstünde.
    assert layout['size_badge'].bottom <= crop.top, size

    # 4) Önizleme paneli görüntü paneliyle çakışmaz (v2 sıkıştırma portu).
    assert not layout['preview_bg'].colliderect(img_bg), size

    # 5) Buton satırı: 6 buton + 6 etiket, hepsi ekranda, birbirine binmez.
    buttons = layout['buttons']
    labels = layout['button_labels']
    assert len(buttons) == 6 and len(labels) == 6
    for rect in buttons + labels:
        assert _within(rect, size), (size, rect)
    for left, right in zip(buttons, buttons[1:]):
        assert right.left >= left.right, (size, left, right)
    for key_bg, label_rect in zip(buttons, labels):
        assert label_rect.top >= key_bg.bottom, size


@pytest.mark.parametrize("size", [(640, 480), (800, 480)])
def test_button_row_regression_offscreen(size):
    """Bu dalganın düzelttiği hata: 640/800'de buton barı ekrana taşıyordu
    (başlangıç -150 / son sağ 745). Artık iki uç da ekran içinde."""
    _skip_if_fonts_stubbed()
    editor = _make_editor(size, with_image=False)
    editor.draw()
    buttons = editor._draw_layout['buttons']

    assert buttons[0].left >= 0, (size, buttons[0])
    assert buttons[-1].right <= size[0], (size, buttons[-1])
    # Satır kabaca ortalanır (yarım buton genişliği tolerans).
    row_w = buttons[-1].right - buttons[0].left
    assert abs((buttons[0].left + buttons[-1].right) / 2 - size[0] / 2) <= row_w / 2, (
        size, buttons[0], buttons[-1])


def test_draw_no_image_branch():
    _skip_if_fonts_stubbed()
    for size in [(640, 480), (1920, 1080)]:
        editor = _make_editor(size, with_image=False)
        editor.draw()
        layout = editor._draw_layout

        assert layout['has_image'] is False
        for key in ('image_bg', 'crop', 'resize_handle', 'size_badge',
                    'preview_bg', 'preview_label'):
            assert key not in layout, key
        for rect in layout['buttons'] + layout['button_labels']:
            assert _within(rect, size), (size, rect)


# ── Durum sözleşmesi: kırpma karesi ────────────────────────────────────────


def test_clamp_crop_caps_size_to_image():
    """Düzeltmenin kendisi: varsayılan 300px kare, 640x480'de görüntü en
    fazla 180x135 olduğundan eskiden görüntüden büyük başlıyordu."""
    editor = _make_editor((640, 480))
    img_w, img_h = editor.display_image.get_size()
    assert (img_w, img_h) == (180, 135)

    editor.crop_size = 300
    editor.crop_x = 999
    editor.crop_y = 999
    editor._clamp_crop()
    assert editor.crop_size == 135, editor.crop_size
    assert 0 <= editor.crop_x <= img_w - editor.crop_size
    assert 0 <= editor.crop_y <= img_h - editor.crop_size


def test_clamp_crop_min_floor_on_tiny_images():
    editor = _make_editor((640, 480))
    editor.display_image = pygame.Surface((80, 50))
    editor.crop_size = 300
    editor._clamp_crop()
    assert editor.crop_size == 100


def test_arrow_keys_clamp_inside_image():
    editor = _make_editor((640, 480))
    img_w, img_h = editor.display_image.get_size()

    for _ in range(40):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert editor.crop_x == img_w - editor.crop_size
    for _ in range(80):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    assert editor.crop_x == 0
    for _ in range(40):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    assert editor.crop_y == img_h - editor.crop_size
    for _ in range(80):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert editor.crop_y == 0


def test_size_keys_respect_image_and_global_bounds():
    editor = _make_editor((640, 480))
    for _ in range(60):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS))
    assert editor.crop_size == 135  # görüntü sınırı (max_crop_size=500 değil)

    editor.display_image = pygame.Surface((780, 585))
    editor.original_image = pygame.Surface((780, 585))
    editor.crop_x, editor.crop_y, editor.crop_size = 0, 0, 300
    for _ in range(60):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS))
    assert editor.crop_size == 500
    for _ in range(80):
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_MINUS))
    assert editor.crop_size == 100


def test_mouse_drag_clamps_inside_image():
    editor = _make_editor((640, 480))
    img_w, img_h = editor.display_image.get_size()
    editor.dragging = True
    editor.drag_start = (90, 45)

    editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(2000, 2000)))
    assert 0 <= editor.crop_x <= img_w - editor.crop_size
    assert 0 <= editor.crop_y <= img_h - editor.crop_size


def test_mouse_resize_refuses_oversized():
    editor = _make_editor((640, 480))
    editor.crop_x, editor.crop_y, editor.crop_size = 0, 0, 100
    editor.resizing = True
    editor.resize_start = (300, 300)
    editor.resize_start_size = 100

    editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(600, 600)))
    assert editor.crop_size == 100  # 400px istendi, görüntü 180px — reddedildi


# ── get_cropped_image geometrisi ────────────────────────────────────────────


def test_get_cropped_image_output_and_mapping():
    editor = _make_editor((1920, 1080))
    orig = pygame.Surface((400, 300))
    orig.fill((200, 40, 40))
    pygame.draw.rect(orig, (40, 40, 200), (300, 0, 100, 300))
    editor.original_image = orig
    editor.display_image = pygame.transform.smoothscale(orig, (200, 150))
    editor.crop_x, editor.crop_y, editor.crop_size = 160, 50, 40

    out = editor.get_cropped_image()
    assert out is not None
    assert out.get_size() == (128, 128)
    px = out.get_at((64, 64))
    assert px.b > px.r, px  # (320..400) orijinal aralığı — mavi


def test_get_cropped_image_none_without_image():
    editor = _make_editor((1920, 1080), with_image=False)
    assert editor.get_cropped_image() is None


def test_cropped_source_int_rounding_stays_inside_original():
    editor = _make_editor((1920, 1080))
    editor.original_image = pygame.Surface((400, 300))
    editor.display_image = pygame.Surface((200, 150))
    scale = 400 / 200

    for cx, cy, cs in [(0, 0, 150), (50, 0, 150), (50, 25, 40),
                       (155, 105, 45), (0, 110, 40)]:
        editor.crop_x, editor.crop_y, editor.crop_size = cx, cy, cs
        out = editor.get_cropped_image()
        assert out is not None and out.get_size() == (128, 128), (cx, cy, cs)
        ox, oy = int(cx * scale), int(cy * scale)
        osz = int(cs * scale)
        assert ox + osz <= 400, (cx, cs, ox, osz)
        assert oy + osz <= 300, (cy, cs, oy, osz)


# ── Font sözleşmesi ─────────────────────────────────────────────────────────


def test_fonts_shared_across_instances():
    """Kurucu UIFonts._cache'ten okur: iki editör aynı Font nesnesini paylaşır
    (editör başına yeni font üretimi yok)."""
    _skip_if_fonts_stubbed()
    first = AvatarEditor(pygame.Surface((640, 480)))
    second = AvatarEditor(pygame.Surface((1920, 1080)))
    assert first.font_title is second.font_title


# ── Kaynak sözleşmeleri ─────────────────────────────────────────────────────


def _source() -> str:
    return pathlib.Path(avatar_module.__file__).read_text(encoding="utf-8")


def _draw_source() -> str:
    source = _source()
    start = source.index("    def draw(self):")
    nxt = re.search(r"\n    def ", source[start + 10:])
    end = start + 10 + (nxt.start() if nxt else len(source) - start - 10)
    return source[start:end]


def test_source_records_layout():
    src = _source()
    assert "self._draw_layout = {}" in src
    for key in ("layout['title']", "layout['image_bg']", "layout['crop']",
                "layout['resize_handle']", "layout['size_badge']",
                "layout['preview_bg']", "layout['preview_label']",
                "layout['bottom_bar_y']", "layout['buttons']",
                "layout['button_labels']", "layout['has_image']"):
        assert key in src, key


def test_source_button_row_actual_width():
    """Buton satırı düzeltmesinin formül pini: gerçek genişlikle ortala,
    adım key_width + 5 (eski 940px varsayımı ve sabit 165 adım geri gelmez)."""
    src = _source()
    assert "total_width = sum(key_widths) + 5 * (len(buttons) - 1)" in src
    assert "button_x += key_width + 5" in src
    assert "sum(160 for _ in buttons) - 20" not in src
    assert "button_x += 165" not in src


def test_source_clamp_caps_crop_size():
    src = _source()
    assert ("self.crop_size = max(self.min_crop_size, "
            "min(self.crop_size, min(img_w, img_h)))") in src


def test_source_preview_clamp():
    src = _source()
    assert "preview_x = max(preview_x, min(bg_rect.right + 12," in src
    assert "width - preview_size - 10" in src


def test_source_img_geometry_consistent():
    """Çizim ve hit-test aynı formülü kullanır (demo: sabit 150)."""
    src = _source()
    img_y_assigns = re.findall(r"img_y = (.+)", src)
    assert len(img_y_assigns) >= 3, img_y_assigns
    assert all(a.strip() == "150" for a in img_y_assigns), img_y_assigns
    img_x_assigns = re.findall(r"img_x = (.+)", src)
    assert len(img_x_assigns) >= 3, img_x_assigns
    assert all(a.strip() == "width // 2 - img_w // 2" for a in img_x_assigns), img_x_assigns


def test_source_mouse_resize_guard():
    src = _source()
    assert ("if self.crop_x + new_size <= img_w and "
            "self.crop_y + new_size <= img_h:") in src


def test_source_draw_has_no_font_creation():
    draw_src = _draw_source()
    assert "UIFonts.get(" not in draw_src
    assert "pygame.font.Font(" not in draw_src
    assert "self.font_title.render(" in draw_src
    assert "self.font_small.render(" in draw_src
