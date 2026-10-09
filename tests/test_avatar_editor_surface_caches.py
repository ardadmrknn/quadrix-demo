# -*- coding: utf-8 -*-
"""AvatarEditor yüzey önbellekleri (OP-020 / DALGA D6) — duman testi.

Editör açıkken her kare ~height adet draw.line + alt bar 100 satırı +
kırpma overlay Surface'i + 2 smoothscale + resize ikonu üretiyordu
(v2 probe: 18.0 ms/kare, SDL dummy — draw.line yalnız %65; ikon yolu
emoji_surface None döndüğünde her kare DISK yükleme). D6, arka plan/alt
bar için (width, boyut) anahtarlı modül LRU'su (4), kırpma overlay ve
önizleme için örnek LRU'su (8) ve ikon için süreç-ömrü tekil girişi
getirdi; görüntü değişimi load_image'te örnek cache'leri düşürür.

Kilitlenen sözleşmeler:
- kimlik: sıcak kare cache'teki NESNEYİ döndürür (aynı Surface — kare
  başına tahsis yok); anahtar değişince yeni nesne üretilir.
- anahtar duyarlılığı: arka plan (width, height); alt bar (width, float
  payda — v2 kesirli ölçekle payda farkı piksel değiştirir; demo sabit
  100 çağırır); overlay/önizleme (görüntü boyutu, crop_x, crop_y,
  crop_size[, preview]).
- LRU sınırı: modül cache'leri 4 girişte en eski anahtarı düşürür.
- invalidasyon: load_image yeni görüntüde kırpma-bağımlı cache'leri boş
  bırakır (overlay/önizleme eski görüntü piksellerini gösteremez).
- piksel paritesi: soğuk (miss) ve sıcak (hit) kareler + sıcak kareler
  arasında ekran digest'i birebir (draw deterministik); sıcak kareler
  cache'leri BÜYÜTMEZ (kare-başı tahsis kovuğu).
- ikon: 'resize_arrow_16' bir kez çözümlenir ve None da önbelleklenir
  ('in' denetimi — miss'ten ayırt edilir; kare döngüsünde disk yok).

Kalıp: test_avatar_editor_containment (gerçek kurucu; demo düzeni
ölçeksiz — sabit 640..4K boylar). Font metrikleri bu dosyada assert
konusu olmadığından stub sızıntısında skip gerekmez — digest/identity
yalıtımı font gerçekliğine bağlı değildir.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
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

import avatar_editor as avatar_module
from avatar_editor import AvatarEditor


def _clear_module_caches():
    """Modül cache'leri süreç-genelidir — önceki test dosyaları doldurmuş
    olabilir; her test kendi soğuk durumunu kurar."""
    avatar_module._BG_GRADIENT_CACHE.clear()
    avatar_module._BG_GRADIENT_CACHE_ORDER.clear()
    avatar_module._BOTTOM_BAR_GRADIENT_CACHE.clear()
    avatar_module._BOTTOM_BAR_GRADIENT_CACHE_ORDER.clear()
    avatar_module._RESIZE_ICON_CACHE.clear()


def _digest(screen):
    return hashlib.sha256(pygame.image.tobytes(screen, "RGB")).hexdigest()


def _make_editor(size, with_image=True):
    """Containment dosyasının kurucusu (demo — ölçeksiz)."""
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


# ── Modül LRU'ları: arka plan / alt bar / ikon ─────────────────────────────

def test_bg_gradient_identity_key_sensitivity_and_eviction():
    _clear_module_caches()
    a = avatar_module._get_bg_gradient_surface(800, 480)
    a2 = avatar_module._get_bg_gradient_surface(800, 480)
    assert a2 is a  # sıcak çağrı aynı nesne

    b = avatar_module._get_bg_gradient_surface(640, 480)
    assert b is not a and b.get_size() == (640, 480)
    assert len(avatar_module._BG_GRADIENT_CACHE) == 2

    # LRU sınırı 4: 5. ayrı anahtar en eski (800x480) düşer.
    for w in (1024, 1280, 1366):
        avatar_module._get_bg_gradient_surface(w, 480)
    assert len(avatar_module._BG_GRADIENT_CACHE) == 4
    avatar_module._get_bg_gradient_surface(1920, 480)
    assert len(avatar_module._BG_GRADIENT_CACHE) == 4
    assert (800, 480) not in avatar_module._BG_GRADIENT_CACHE

    # Piksel içerik sözleşmesi: formül satır bazlı — örnekle doğrulanır.
    surf = avatar_module._get_bg_gradient_surface(64, 8)
    ref = pygame.Surface((64, 8))
    for i in range(8):
        color_r = int(10 + (i / 8) * 15)
        color_g = int(15 + (i / 8) * 20)
        color_b = int(30 + (i / 8) * 25)
        pygame.draw.line(ref, (color_r, color_g, color_b), (0, i), (64, i))
    assert pygame.image.tobytes(surf, "RGB") == pygame.image.tobytes(ref, "RGB")


def test_bottom_bar_gradient_identity_and_denom_key():
    _clear_module_caches()
    a = avatar_module._get_bottom_bar_gradient_surface(800, 100.0)
    a2 = avatar_module._get_bottom_bar_gradient_surface(800, 100)
    assert a2 is a  # int/float 100 aynı anahtara iner (float(denom))
    assert a.get_size() == (800, 100)

    # Kesirli payda farklı piksel katarı → farklı giriş (v2 ölçekli
    # çağrının kovuğu; demo sabit 100 çağırır).
    b = avatar_module._get_bottom_bar_gradient_surface(800, 125.0)
    assert b is not a and b.get_size() == (800, 125)
    assert len(avatar_module._BOTTOM_BAR_GRADIENT_CACHE) == 2

    # Alfa eğrisi i/denom — int(denom) satır sayısı, payda birebir.
    surf = avatar_module._get_bottom_bar_gradient_surface(64, 8.0)
    ref = pygame.Surface((64, 8))
    for i in range(8):
        alpha = 1 - (i / 8.0)
        color = (int(20 * alpha), int(25 * alpha), int(40 * alpha))
        pygame.draw.line(ref, color, (0, i), (64, i))
    assert pygame.image.tobytes(surf, "RGB") == pygame.image.tobytes(ref, "RGB")


def test_resize_icon_resolved_once():
    _clear_module_caches()
    first = avatar_module._get_resize_icon()
    assert 'resize_arrow_16' in avatar_module._RESIZE_ICON_CACHE
    # İkinci çağrı KİMLİKLE döner (None dahil — disk denemesi tekrar etmez).
    assert avatar_module._get_resize_icon() is first
    # draw() aynı nesneyi kullanır; oyun döngüsünde I/O kalmaz.
    editor = _make_editor((800, 480))
    editor.draw()
    assert avatar_module._get_resize_icon() is first


# ── Örnek LRU'ları: kırpma overlay / önizleme + invalidasyon ───────────────

def test_crop_overlay_and_preview_identity_and_crop_key():
    _clear_module_caches()
    editor = _make_editor((800, 480))

    overlay_a = editor._get_crop_overlay_surface()
    assert editor._get_crop_overlay_surface() is overlay_a  # hit kimliği

    preview_a = editor._get_preview_surface(150)
    assert editor._get_preview_surface(150) is preview_a
    assert preview_a.get_size() == (150, 150)

    # Kırpma konumu anahtarın parçası: kaydırınca yeni nesneler üretilir.
    editor.crop_x += 20
    editor.crop_y += 10
    overlay_b = editor._get_crop_overlay_surface()
    preview_b = editor._get_preview_surface(150)
    assert overlay_b is not overlay_a
    assert preview_b is not preview_a

    # Önizleme boyutu da anahtarın parçası (fonksiyon sözleşmesi).
    preview_s = editor._get_preview_surface(120)
    assert preview_s is not None and preview_s.get_size() == (120, 120)


def test_load_image_clears_instance_caches(monkeypatch):
    _clear_module_caches()
    editor = _make_editor((800, 480))
    editor.draw()
    assert editor._crop_overlay_cache  # draw doldurdu

    # asset_manager.load_image yerine taze görüntü döndüren stub —
    # load_image akışı (smoothscale + clamp + invalidasyon) gerçek koşar.
    def _fake_load_image(path, convert_alpha=False):
        surf = pygame.Surface((300, 300))
        surf.fill((90, 90, 130))
        return surf

    monkeypatch.setattr(avatar_module, 'load_image', _fake_load_image)
    assert editor.load_image('/tmp/probe_avatar_stub.png') is True

    assert editor._crop_overlay_cache == {}
    assert editor._crop_overlay_cache_order == []
    assert editor._preview_cache == {}
    assert editor._preview_cache_order == []
    # Yeni görüntüyle ilk kare cache'leri yeniden doldurur.
    editor.draw()
    assert editor._crop_overlay_cache


# ── Kare piksel paritesi + kare-başı tahsis kovuğu ─────────────────────────

def test_draw_digest_parity_and_cache_stability():
    _clear_module_caches()
    editor = _make_editor((1280, 720))

    editor.draw()  # soğuk: modül + örnek cache'ler boş (miss yolu)
    cold = _digest(editor.screen)
    cache_lens = (
        len(avatar_module._BG_GRADIENT_CACHE),
        len(avatar_module._BOTTOM_BAR_GRADIENT_CACHE),
        len(editor._crop_overlay_cache),
        len(editor._preview_cache),
    )

    # Sıcak kareler: digest sabit, cache'ler BÜYÜMEZ (kare-başı tahsis yok).
    for _ in range(40):
        editor.draw()
        assert _digest(editor.screen) == cold
        assert (
            len(avatar_module._BG_GRADIENT_CACHE),
            len(avatar_module._BOTTOM_BAR_GRADIENT_CACHE),
            len(editor._crop_overlay_cache),
            len(editor._preview_cache),
        ) == cache_lens
