# -*- coding: utf-8 -*-
"""AvatarEditor yüzey önbellekleri (OP-020 / DALGA D6) — duman testi.

Editör açıkken her kare ~height adet draw.line + alt bar 100 satırı +
kırpma overlay Surface'i + 2 smoothscale + resize ikonu üretiyordu
(v2 probe: 18.0 ms/kare, SDL dummy — draw.line yalnız %65; ikonun kare-başı
DISK yüklemesi YALNIZ set_mode'suz probe ortamında görülüyordu: üretimde
(set_mode aktif) emoji LRU'su ilk karede hit'ti). D6, arka plan/alt
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
- ikon fallback: emoji kısayolu koptuğunda diskten 16×16 YİNE yalnız
  bir kez yüklenir (başarı yolu; üretimde erişilmez — emoji LRU hit).
- LRU canlılık: hit verilen anahtar recency'de sona taşınır (FIFO
  değil); 14 farklı kırpma geometrisi örnek cache'lerini 8 girişte
  tutar (sürükleme churn'u altında sınırlı bellek).
- save_avatar tazelik: kayıt yolu önizleme cache'ini değil taze
  get_cropped_image'i kullanır (çağrı sayacı + piksel özdeşliği).
- çıkış release: save/cancel sonrası örnek + modül gradyan cache'leri
  ve görüntü referansları bırakılır (oturum-ömrü iki örnek — 4K
  doğrudan çizimde ~106 MiB/örnek kalıcı tutulum).
- overlay içerik: (0,0,0,120) dolgu + kırpma rect (0,0,0,0) — formül
  referans üretimiyle bayt-bayt RGBA eşit (alfa değeri/dikdörtgen
  semantiği sessiz değişemez).

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


def test_resize_icon_none_sentinel_locks_retry(monkeypatch):
    """None-sentinel sözleşmesi GERÇEK None yoluyla sürülür.

    emoji_surface None döner + fallback dosyası yok sayılır: sonuç None
    önbelleklenir ve kare-döngüsünde emoji/disk denemesi TEKRAR ETMEZ.
    '.get()' truthiness regresyonunda 3 çağrı yapılırdı — sayaç düşer."""
    _clear_module_caches()
    import emoji_renderer

    calls = {'emoji': 0}

    def _fake_emoji(*a, **kw):
        calls['emoji'] += 1
        return None

    monkeypatch.setattr(emoji_renderer, 'emoji_surface', _fake_emoji)
    # Fallback dosyasının varlığı ortam bağımlı — yok sayılır.
    monkeypatch.setattr(pathlib.Path, 'exists', lambda self: False)

    first = avatar_module._get_resize_icon()
    second = avatar_module._get_resize_icon()
    third = avatar_module._get_resize_icon()
    assert first is None and second is None and third is None
    assert calls['emoji'] == 1
    assert 'resize_arrow_16' in avatar_module._RESIZE_ICON_CACHE
    assert avatar_module._RESIZE_ICON_CACHE['resize_arrow_16'] is None


def test_resize_icon_disk_fallback_loads_when_emoji_unavailable(monkeypatch):
    """Fallback'in dosyadan-yükleme başarı yolu en az bir kez koşar.

    emoji_surface None + gerçek asset VAR → ikon diskten yüklenip 16×16
    smoothscale edilir ve süreç-ömrü girişine alınır. Bu yol üretimde
    erişilmez (emoji LRU hit) ama dokümante kilit sözleşmeydi ve D6
    öncesi testte HİÇ koşmuyordu (inceleme bulgusu)."""
    _clear_module_caches()
    import emoji_renderer
    monkeypatch.setattr(emoji_renderer, 'emoji_surface', lambda *a, **kw: None)
    icon = avatar_module._get_resize_icon()
    assert icon is not None
    assert icon.get_size() == (16, 16)
    assert avatar_module._get_resize_icon() is icon


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

    # Sürükleme (churn) karesi: yeni (crop_x, crop_y) anahtarı digest
    # DEĞİŞTİRİR (overlay/preview içerikleri crop'a bağımlı — kaydırma
    # gerçekten çizime yansır) ve kaydırma sonrası kareler yeni digest
    # etrafında kararlı kalır (probe kanıtını düzenli pakete taşır).
    editor.crop_x += 30
    editor.crop_y += 20
    editor.draw()
    drag = _digest(editor.screen)
    assert drag != cold
    for _ in range(5):
        editor.draw()
        assert _digest(editor.screen) == drag


# ── D6 inceleme kapaları: LRU canlılık / save tazeliği / çıkış release ─────

def test_instance_lru_recency_and_cap_8():
    """Recency tazelemesi (FIFO değil) + örnek LRU'larının 8 sınırı.

    8 dolu cache'te en eski anahtara hit + 9. ekleme → en eski DOKUNMA
    (2. girilen) düşer; FIFO regresyonunda 1. girilen düşerdi ve ilk
    assert düşer. 14 farklı kırpma geometrisi her iki örnek cache'ini de
    8 girişte tutar — sürükleme churn'u altında sınırlı bellek
    (digest testindeki 'büyümüyor' iddiası churn üretmediğinden sınırı
    hiç ölçmüyordu)."""
    _clear_module_caches()
    editor = _make_editor((800, 480))
    base_x = editor.crop_x

    for i in range(8):
        editor.crop_x = base_x + i
        editor._get_crop_overlay_surface()
        editor._get_preview_surface(150)
    assert len(editor._crop_overlay_cache) == 8
    assert len(editor._preview_cache) == 8
    assert len(editor._crop_overlay_cache) == len(editor._crop_overlay_cache_order)
    assert len(editor._preview_cache) == len(editor._preview_cache_order)

    first_key = editor._crop_overlay_cache_order[0]
    second_key = editor._crop_overlay_cache_order[1]
    # En eski anahtara hit → recency sonuna taşınır (FIFO'da hareketsiz).
    editor.crop_x = base_x
    editor._get_crop_overlay_surface()
    assert editor._crop_overlay_cache_order[-1] == first_key
    # 9. geometri: LRU'da 2. girilen (en eski dokunma) düşer.
    editor.crop_x = base_x + 8
    editor._get_crop_overlay_surface()
    assert len(editor._crop_overlay_cache) == 8
    assert first_key in editor._crop_overlay_cache
    assert second_key not in editor._crop_overlay_cache
    # 10+ geometri: her iki cache 8'de sabit (sınır doğrudan ölçülür).
    for i in range(9, 14):
        editor.crop_x = base_x + i
        editor._get_crop_overlay_surface()
        editor._get_preview_surface(150)
    assert len(editor._crop_overlay_cache) == 8
    assert len(editor._preview_cache) == 8
    assert len(editor._crop_overlay_cache) == len(editor._crop_overlay_cache_order)
    assert len(editor._preview_cache) == len(editor._preview_cache_order)


def test_save_avatar_uses_fresh_crop_path(tmp_path, monkeypatch):
    """save_avatar taze get_cropped_image yolunu kullanır (sözleşme).

    draw() önizleme cache'ini doldurduktan sonra bile kayıt yolu kırpma
    metadunu BİR KEZ koşar ve kaydedilen yüzey taze 128×128 üretimin
    kendisidir. Önizleme cache'ine redirect edilen bir refactor sayaçta
    0 verir ve bu test düşer (piksel bacığı ayrıca 128'e geri ölçeklenen
    bir zincirin ürünüyle ayrışır)."""
    _clear_module_caches()
    editor = _make_editor((800, 480))
    editor.draw()  # önizleme cache'i 150 anahtarıyla dolar
    assert editor._preview_cache

    calls = {'n': 0}
    orig = editor.get_cropped_image

    def _counted(*a, **kw):
        calls['n'] += 1
        return orig(*a, **kw)

    monkeypatch.setattr(editor, 'get_cropped_image', _counted)

    saved = {'surf': None}

    def _capture(surface, filename):
        saved['surf'] = surface

    # Her iki pygame görünümünü de patch'le: conftest'in pygame-purge'u
    # testler arasında avatar_editor'ü yeniden import ettirebilir —
    # modülün pygame'i dosya-global pygame'ten ayrışır ve save_avatar
    # KENDİ pygame'inden çağırır (tek görünümü patch'lemek koşum
    # sırasına göre yakalamayı kaçırıyordu).
    monkeypatch.setattr(pygame.image, 'save', _capture)
    monkeypatch.setattr(avatar_module.pygame.image, 'save', _capture)

    out = editor.save_avatar('probe', str(tmp_path / 'probe_avatar.png'))
    assert out == str(tmp_path / 'probe_avatar.png')
    assert calls['n'] == 1
    assert saved['surf'] is not None and saved['surf'].get_size() == (128, 128)
    # Kaydedilen yüzey, taze kırpmanın kendisidir (aynı üretim yolu).
    monkeypatch.setattr(editor, 'get_cropped_image', orig)
    fresh = editor.get_cropped_image()
    assert pygame.image.tobytes(saved['surf'], "RGBA") == pygame.image.tobytes(fresh, "RGBA")


def test_release_session_resources():
    """save/cancel çıkışında cache'ler ve görüntü referansları bırakılır.

    İki AvatarEditor örneği oturum ömrü yaşadığından bırakılmayan
    cache'ler 4K doğrudan çizim (macOS) yolunda ~106 MiB/örnek kalıcı
    RAM tutuyordu. Release sonrası editör çizilebilir kalır (no-image
    dalı) ve yeni oturum cache'leri taze üretir."""
    _clear_module_caches()
    editor = _make_editor((800, 480))
    editor.draw()
    assert editor._crop_overlay_cache
    assert editor._preview_cache
    assert avatar_module._BG_GRADIENT_CACHE
    assert editor.display_image is not None

    editor.release_session_resources()

    assert editor._crop_overlay_cache == {}
    assert editor._crop_overlay_cache_order == []
    assert editor._preview_cache == {}
    assert editor._preview_cache_order == []
    assert avatar_module._BG_GRADIENT_CACHE == {}
    assert avatar_module._BOTTOM_BAR_GRADIENT_CACHE == {}
    assert editor.display_image is None
    assert editor.original_image is None

    # Release sonrası draw çalışır (görüntüsüz istem dalı) — release
    # draw yolunu kırmaz; görüntü geri YÜKLENMEZ (yalnız load_image).
    editor.draw()
    assert editor.display_image is None
    # Yeni oturum (kullanıcı yeniden resim seçer): cache'ler taze dolar.
    editor2 = _make_editor((800, 480))
    editor2.draw()
    assert editor2._crop_overlay_cache
    assert editor2._preview_cache


def test_crop_overlay_pixel_content_matches_reference_formula():
    """Overlay içerik sözleşmesi — bg/alt bar referans deseni.

    Formül: SRCALPHA (0,0,0,120) dolgu + kırpma dikdörtgeninin (0,0,0,0)
    ile temizlenmesi. Referans üretimiyle bayt-bayt RGBA eşitliği; alfa
    değerinin (örn. 120→115) veya dikdörtgen semantiğinin sessiz
    değişimi düşer (inceleme bulgusu: overlay'in piksel-içerik
    referansı yoktu)."""
    _clear_module_caches()
    editor = _make_editor((800, 480))
    surf = editor._get_crop_overlay_surface()
    ref = pygame.Surface(editor.display_image.get_size(), pygame.SRCALPHA)
    ref.fill((0, 0, 0, 120))
    pygame.draw.rect(
        ref, (0, 0, 0, 0),
        pygame.Rect(editor.crop_x, editor.crop_y,
                    editor.crop_size, editor.crop_size))
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(ref, "RGBA")
