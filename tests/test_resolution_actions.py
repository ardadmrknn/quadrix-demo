# -*- coding: utf-8 -*-
"""FAZ A3 (demo karşılığı): pencere/çözünürlük aksiyon entegrasyonu testleri — canlı.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A3 kabul kriterlerinin demo
karşılığıdır (v2 tests/test_resolution_actions.py uyarlaması). Demo'daki
gerçek farklar v2'ye göre:
- Aksiyon adı 'change_window_resolution' DEĞİL 'apply_display_mode'dır:
  demo'da çözünürlük çeviricisi windowed moddaysa bu aksiyonu üretir ve
  main.py dispatch'i (FAZ A3 ile parse yardımcısına bağlandı) tek rebuild
  transaction'ıyla tüketir.
- Varsayılan pencere çözünürlüğü 1280x720'dir (v2: 1920x1080) ve çevirici
  listesi 4 elemanlıdır: 1920x1080 → 1600x900 → 1366x768 → 1280x720.
- Demo'da çözünürlük çeviricisi fullscreen moddayken aksiyon ÜRETMEZ
  (yalnız kaydeder); rebuild, fullscreen → windowed geçişinde
  apply_display_mode onay akışıyla gelir.

Doğrulanan sözleşmeler (v2 paritesi):
1. patch_event_queue/unpatch_event_queue yaşam döngüsü: temiz kurulum,
   idempotent ikinci kurulum, çift-unpatch no-op, yabancı katman koruması
   (kimlik guard'ı), flag/kurulum desync telafisi (self-capture/çifte
   normalizasyon yok), kısmi başarısızlık rollback'i.
2. RN-001/002 (4K_Sanal_Tuval_Uygulama_Kilavuzu.md Bölüm 5): üç backend
   (software canvas, sdl2-overlay simülasyonu, düz/patch'siz) altında
   get_window_logical_size + get_window_size çağrıları karşılıklı
   recursion ÜRETMEZ (300 çağrı, düşürülmüş recursion limiti).
3. Rebuild transaction: çözünürlük/preset geçişi eski canvas yüzeyini
   söker (yeni kimlik; eskisi geri gelmez), A1 geometri kuşağı her
   geçişte artar ve event patch'leri kurulum dallarında GERİ GELİR
   (125→100→125 ömür gediği düzeltmesi).
4. parse_window_resolution: doğrulama + sanitize (alt pencere tabanı).
5. record_platform_display_telemetry / is_steam_deck (A0 telemetri ucu).
6. Üretici ucu: settings `_cycle_selector('window_resolution', ...)`
   windowed modda 'apply_display_mode' aksiyonu üretir (fullscreen'da
   yalnız kayıt; ana dispatch'teki FAZ A3 parse entegrasyonu bunu tüketir).

Canlı testtir (gerçek pygame, SDL_VIDEODRIVER=dummy; stub pytest
ortamında atlanır — test_settings_cache_generation.py kalıbı). Disk
yazımı olmamalı: _set_value/_get_value instance üzerinde lambda ile
değiştirilir.

Önc-var kırmızı yok: bu dosya FAZ A3 demo portlamasıyla birlikte eklendi.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

# Modül seviyesinde (koleksiyon anı = temiz süreç durumu) gerçek pygame'i
# bağla. Tam paket koşusunda önceki test dosyaları pygame'i sys.modules'ten
# sökebiliyor; süit ortasında yapılan gerçek import Windows'ta WinError 206
# (os.add_dll_directory) ile başarısız olabiliyor (A4 kalıbı).
import pygame


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    # abspath zorunlu: 'tests\..\src' yazımı modül __file__ değerine sızar
    # ve conftest'in _looks_like_test_stub denetimi GERÇEK modülü stub sanıp
    # sys.modules'ten söker (test_settings_cache_generation.py gerekçesi).
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)


@pytest.fixture(scope='module')
def live_env():
    """Gerçek modülleri yükle; pygame'i dummy sürücüyle hazırla (A4 kalıbı)."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    _ensure_src_on_path()

    _module_keys = [
        'settings_screen_tabbed', 'constants', 'retro_style',
        'platform_utils', 'background_effects', 'localization',
        'ui_language_profile', 'menu', 'gamepad_manager',
        'promptfont_support', 'ui_scaling', 'settings_manager',
        'sdl2_overlay',
    ]
    _module_lookup_keys = [
        key
        for mod in _module_keys
        for key in (mod, f'src.{mod}')
    ]
    # Pygame ailesi anlık görüntüsü: teardown'da kök + tüm alt modüller tek
    # transaction'da geri konur. Yalnız kökü (sys.modules['pygame']) sökmek
    # aileyi karışık durumda bırakır; sonraki canlı test dosyasının
    # `import pygame`'i "partially initialized module" hatasıyla çöker.
    # Conftest'in koleksiyon-sınırı aile purge'üyle aynı gerekçe (v2 K4'de
    # 9 ERROR olarak kanıtlandı; ikiz repro A4 kalıbında da üretilebiliyor).
    _pygame_family_leaked = {
        key: mod for key, mod in list(sys.modules.items())
        if key == 'pygame' or key.startswith('pygame.')
    }
    _pygame_leaked = sys.modules.get('pygame')
    if _pygame_leaked is not pygame:
        sys.modules['pygame'] = pygame

    _original_modules = {key: sys.modules.get(key) for key in _module_lookup_keys}
    for key in _module_lookup_keys:
        sys.modules.pop(key, None)

    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.font.get_init():
        pygame.font.init()

    import settings_screen_tabbed as sst
    import platform_utils
    import ui_scaling

    # Hermetiklik sözleşmesi: call-time import'lar canlı kopyaya çözümlenmeli.
    assert sys.modules['platform_utils'] is platform_utils
    assert sys.modules['ui_scaling'] is ui_scaling
    assert sys.modules['settings_screen_tabbed'] is sst

    yield types.SimpleNamespace(
        pygame=pygame, sst=sst, platform_utils=platform_utils,
        ui_scaling=ui_scaling,
    )

    try:
        platform_utils._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        platform_utils.unpatch_event_queue()
    except Exception:
        pass
    try:
        ui_scaling.set_ui_scale_preset('normal')
        ui_scaling._PROJECTED_SCALE_CACHE.clear()
    except Exception:
        pass
    for _key, _original in _original_modules.items():
        if _original is not None:
            sys.modules[_key] = _original
        else:
            sys.modules.pop(_key, None)
    # Aile-tutarlı geri koyma: önce kök + alt modüllerin hepsini sök, sonra
    # kurulum anındaki anlık görüntüyü aynen geri koy. Boş anlık görüntü
    # (conftest purge'ünden sonra) → aile tamamen sıfırlanır; dolu → birebir
    # restore. Her iki durumda da sonraki `import pygame` sağlıklı çalışır.
    for _key in [
        k for k in list(sys.modules)
        if k == 'pygame' or k.startswith('pygame.')
    ]:
        sys.modules.pop(_key, None)
    for _key, _mod in _pygame_family_leaked.items():
        sys.modules[_key] = _mod


@pytest.fixture()
def clean_display(live_env):
    """Her test öncesi/sonrası: gerçek display + sökülmüş tuval + patch'siz slotlar."""
    pygame = live_env.pygame
    pu = live_env.platform_utils
    pygame.display.set_mode((1920, 1080))
    try:
        pu._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        pu.unpatch_event_queue()
    except Exception:
        pass
    try:
        live_env.ui_scaling.set_ui_scale_preset('normal')
        live_env.ui_scaling._PROJECTED_SCALE_CACHE.clear()
    except Exception:
        pass
    yield live_env
    try:
        pu._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        pu.unpatch_event_queue()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1) parse_window_resolution — doğrulama + sanitize
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    ('1920x1080', (1920, 1080)),
    ('1280x720', (1280, 720)),
    ('1366x768', (1366, 768)),
    ('1600X900', (1600, 900)),       # büyük X tolere edilir
    (' 1920x1080 ', (1920, 1080)),   # beyaz boşluklar kırpılır
    ((1600, 900), (1600, 900)),      # tuple girdisi
    ([1600, 900], (1600, 900)),      # liste girdisi
    ('19x10', (320, 200)),           # deforme küçük değer → alt tabana clamp
    ('0x0', (320, 200)),
    ('garbage', (1280, 720)),        # geçersiz → default
    ('', (1280, 720)),
    (None, (1280, 720)),
    ('1920', (1280, 720)),           # eksik boyut → default
    ('1920x1080xextra', (1280, 720)),
    (12, (1280, 720)),               # skaler girdi → default
])
def test_parse_window_resolution_matrix(live_env, value, expected):
    got = live_env.platform_utils.parse_window_resolution(value, default=(1280, 720))
    assert got == expected, f"parse({value!r}) -> {got}, beklenen {expected}"


def test_parse_window_resolution_defaults_are_explicit(live_env):
    pu = live_env.platform_utils
    # Default parametresi çağırıcıya aittir (demo main: 1280x720; genel
    # yardımcı da 1280x720) — yardımcı kendi başına varsayılan dayatmaz.
    assert pu.parse_window_resolution(None) == (1280, 720)
    assert pu.parse_window_resolution(None, default=(1024, 768)) == (1024, 768)


# ---------------------------------------------------------------------------
# 2) Patch yaşam döngüsü (FAZ A3 idempotency)
# ---------------------------------------------------------------------------

def test_patch_unpatch_clean_cycle(clean_display):
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    orig_event_get = pygame.event.get
    orig_get_pos = pygame.mouse.get_pos
    orig_get_rel = pygame.mouse.get_rel
    orig_set_pos = pygame.mouse.set_pos
    orig_gws = pygame.display.get_window_size

    pu.patch_event_queue()
    assert pu._event_patch_active is True
    assert set(pu._event_patch_installed.keys()) == {
        'event_get', 'mouse_get_pos', 'mouse_get_rel',
        'mouse_set_pos', 'display_get_window_size',
    }
    assert pygame.event.get is pu._patched_event_get
    assert pygame.mouse.get_pos is not orig_get_pos
    assert pygame.display.get_window_size is not orig_gws
    # Legacy sözleşme: get_mouse_pos/get_raw_mouse_pos bu öznitelikleri okur.
    assert callable(pu.patch_event_queue._orig_mouse_get_pos)
    assert pu.patch_event_queue._orig_mouse_get_pos is orig_get_pos

    pu.unpatch_event_queue()
    assert pu._event_patch_active is False
    assert not pu._event_patch_installed
    assert pygame.event.get is orig_event_get
    assert pygame.mouse.get_pos is orig_get_pos
    assert pygame.mouse.get_rel is orig_get_rel
    assert pygame.mouse.set_pos is orig_set_pos
    assert pygame.display.get_window_size is orig_gws
    assert not hasattr(pu.patch_event_queue, '_orig_mouse_get_pos')

    # Çift unpatch tam no-op (hızlı yol).
    pu.unpatch_event_queue()
    assert pygame.mouse.get_pos is orig_get_pos
    assert pu._event_patch_active is False


def test_patch_idempotent_when_active(clean_display):
    """Flag açıkken ikinci kurulum yeni closure ÜRETMEZ (sarma yok)."""
    pu = clean_display.platform_utils
    pu.patch_event_queue()
    try:
        assert pu._event_patch_active is True
        entry = pu._event_patch_installed['mouse_get_pos']
        installed_patched = entry[2]
        pu.patch_event_queue()
        assert pu._event_patch_active is True
        assert pu._event_patch_installed['mouse_get_pos'][2] is installed_patched
        assert len(pu._event_patch_installed) == 5
    finally:
        pu.unpatch_event_queue()


def test_unpatch_leaves_foreign_layer_intact(clean_display):
    """Slotu devralan yabancı katman (sdl2_overlay kalıbı) ezilmez."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    orig_get_pos = pygame.mouse.get_pos

    pu.patch_event_queue()
    foreign = lambda: (1, 2)  # noqa: E731
    pygame.mouse.get_pos = foreign
    try:
        pu.unpatch_event_queue()
        assert pygame.mouse.get_pos is foreign, (
            "yabancı katman korunmalı (kimlik guard'ı)"
        )
        # Kayıttan düştü ama diğer slotlar normale döndü.
        assert pu._event_patch_active is False
    finally:
        pygame.mouse.get_pos = orig_get_pos


def test_patch_reconciles_desync_without_self_capture(clean_display):
    """Flag/kurulum desync'i: yeniden kurulum kendi yamasını orig YAKALAMAZ.

    Yapay desync: flag elle düşürülür (üretimde kısmi başarısızlık veya
    flag'i düşüren yabancı yol), yamalar slotlarda kalır. Yeniden kurulum
    eskileri kayıtlı orig'e geri alıp taze kurar; kayıtlı orig HAM
    fonksiyondur (bizim patched closure'ımız değil) → çifte normalizasyon
    üretilemez. Davranışsal kanıt: etkin letterbox'ta tek normalizasyon.
    """
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    orig_get_pos = pygame.mouse.get_pos

    pu.patch_event_queue()
    # Yapay desync (test/üretim sapması simülasyonu)
    pu._event_patch_active = False

    pu.patch_event_queue()
    assert pu._event_patch_active is True
    entry = pu._event_patch_installed['mouse_get_pos']
    assert entry[3] is orig_get_pos, (
        f"orig kaydı ham fonksiyon olmalı (self-capture): {entry[3]}"
    )
    assert pygame.mouse.get_pos is entry[2]

    # Davranışsal kanıt — tek normalizasyon: canvas (960, 540), blit
    # (0, 0, 1920, 1080) iken ham (960, 540) → tek adımda (480, 270).
    # Self-capture'li çifte normalizasyon (240, 135) üretirdi.
    try:
        pu._software_canvas = pygame.Surface((960, 540))
        pu._software_scale_active = True
        pu._virtual_blit_rect = (0, 0, 1920, 1080)
        result = pu._normalize_event_pos((960, 540))
        assert result == (480, 270), (
            f"tek normalizasyon (480, 270) bekleniyordu: {result}"
        )
    finally:
        pu._software_canvas = None
        pu._software_scale_active = False
        pu._virtual_blit_rect = None
        pygame.mouse.get_pos = orig_get_pos
        pu.unpatch_event_queue()
        assert pygame.mouse.get_pos is orig_get_pos
        assert pu._event_patch_active is False


def test_patch_partial_failure_rolls_back_installed_slots(clean_display, monkeypatch):
    """Kurulum ortasında exception: bu çağrıda kurulan slotlar geri alınır.

    Enjeksiyon: pygame.mouse, atamada RuntimeError üreten sahte modülle
    değiştirilir. event.get ATANIR (ilk slot), mouse ataması patlar →
    rollback event.get'i kayıtlı orig'e döndürmeli; flag kapalı, kayıt boş.
    """
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    orig_event_get = pygame.event.get

    class _RaisingMouse:
        def __getattr__(self, name):
            return lambda *a, **k: (0, 0)

        def __setattr__(self, name, value):
            raise RuntimeError('enjekte edilen kısmi başarısızlık')

    monkeypatch.setattr(pygame, 'mouse', _RaisingMouse(), raising=False)
    pu.patch_event_queue()

    assert pu._event_patch_active is False, "kısmi başarısızlık flag'i açık bırakmamalı"
    assert not pu._event_patch_installed, "rollback kurulum kaydını temizlemeli"
    assert pygame.event.get is orig_event_get, (
        "rollback event.get'i kayıtlı orig'e döndürmeli"
    )
    # Tekrar kurulum (gerçek mouse geri geldi) temiz çalışmalı.
    monkeypatch.undo()
    pu.patch_event_queue()
    try:
        assert pu._event_patch_active is True
        assert len(pu._event_patch_installed) == 5
    finally:
        pu.unpatch_event_queue()


# ---------------------------------------------------------------------------
# 3) RN-001/002 — üç backend altında recursion yok
# ---------------------------------------------------------------------------

def _recursion_guard():
    """Düşürülmüş recursion limiti: gizli karşılıklı çağrı hızla patlar."""
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(200)
    return old_limit


def test_gwls_no_recursion_software_canvas_backend(clean_display):
    """Software canvas aktif + event patch'leri kurulu: 300 çağrı, kuşak yok."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    real = pygame.display.get_surface()

    canvas = pu.setup_virtual_canvas(real, 1.25)
    assert canvas.get_size() == (1536, 864)
    assert pu._event_patch_active is True

    old_limit = _recursion_guard()
    try:
        for _ in range(300):
            assert tuple(pu.get_window_logical_size()) == (1536, 864)
            assert tuple(pygame.display.get_window_size()) == (1536, 864)
    finally:
        sys.setrecursionlimit(old_limit)
        pu._teardown_virtual_canvas()
        pu.unpatch_event_queue()


def test_gwls_no_recursion_sdl2_sim_backend(clean_display, monkeypatch):
    """SDL2 overlay simülasyonu + event patch'leri (üretim kurulum sırası)."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    canvas = (1920, 1080)

    monkeypatch.setattr(pu, 'IS_MACOS', False)
    game_surface = pygame.Surface(canvas, getattr(pygame, 'SRCALPHA', 0))
    fake_overlay = types.SimpleNamespace(
        is_active=lambda: True,
        get_canvas_size=lambda: tuple(canvas),
    )
    monkeypatch.setitem(sys.modules, 'sdl2_overlay', fake_overlay)
    monkeypatch.setattr(pygame.display, 'get_surface', lambda: game_surface, raising=False)
    monkeypatch.setattr(
        pygame.display, 'get_window_size',
        lambda: game_surface.get_size(), raising=False,
    )
    # Üretim sırası: overlay display patch'leri ÖNCE, event patch'leri SONRA.
    pu.patch_event_queue()

    old_limit = _recursion_guard()
    try:
        for _ in range(300):
            assert tuple(pu.get_window_logical_size()) == canvas
            assert tuple(pygame.display.get_window_size()) == canvas
    finally:
        sys.setrecursionlimit(old_limit)
        pu.unpatch_event_queue()


def test_gwls_no_recursion_plain_backend(clean_display):
    """Patch'siz düz pygame: gwls gerçek get_window_size'ı okur, döngü yok."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    assert pu._event_patch_active is False

    old_limit = _recursion_guard()
    try:
        for _ in range(300):
            assert tuple(pu.get_window_logical_size()) == (1920, 1080)
            assert tuple(pygame.display.get_window_size()) == (1920, 1080)
    finally:
        sys.setrecursionlimit(old_limit)


# ---------------------------------------------------------------------------
# 4) Rebuild transaction (A1 generation bağlı yüzey değişimi)
# ---------------------------------------------------------------------------

def test_rebuild_transaction_replaces_canvas_and_rearms_patches(clean_display):
    """Teardown → kurulum döngüsü: eski yüzey geri gelmez, kuşak artar,
    patch'ler her terminal dalda yeniden kurulur (ömür gediği düzeltmesi)."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    real = pygame.display.get_surface()

    gen0 = pu.get_geometry_generation()
    canvas_a = pu.setup_virtual_canvas(real, 1.25)
    gen1 = pu.get_geometry_generation()
    assert canvas_a is not real
    assert canvas_a.get_size() == (1536, 864)
    assert gen1 > gen0, "kurulum kuşağı artırmalı"
    assert pu._event_patch_active is True
    assert pygame.display.get_surface() is canvas_a

    # Söküm: canvas gider, patch'ler sökülür (üretim davranışı), kuşak artar.
    pu._teardown_virtual_canvas()
    gen2 = pu.get_geometry_generation()
    assert gen2 > gen1, "söküm kuşağı artırmalı"
    assert pu._event_patch_active is False, "söküm unpatch çalıştırmalı"
    assert pygame.display.get_surface() is not canvas_a, "eski canvas yüzeyi yok"

    # ÖMÜR GEDİĞİ (FAZ A3): pass-through dali bile patch'leri geri getirmeli
    # (125 → 100 geçişi; 100 → 125 dönüşünde normalizasyon ayakta kalmalı).
    real2 = pu.setup_virtual_canvas(real, 1.0)
    assert real2 is real, "1.0 çarpan pass-through gerçek yüzeyi döndürmeli"
    assert pu._event_patch_active is True, (
        "pass-through kurulumu event patch'lerini geri kurmalı (A3 düzeltmesi)"
    )

    # Yeni aktif kurulum: YENİ canvas kimliği — eskisi asla geri gelmez.
    canvas_b = pu.setup_virtual_canvas(real, 1.25)
    assert canvas_b is not canvas_a, "yeni kurulum yeni canvas üretmeli"
    assert pygame.display.get_surface() is canvas_b
    gen3 = pu.get_geometry_generation()
    assert gen3 > gen2, "ikinci kurulum kuşağı artırmalı"


def test_geometry_generation_survives_full_cycle_assertion(clean_display):
    """A1 sözleşmesi: her geçiş katı monotone artar; tüketici bu damgayla
    bayat snapshot'ı tespit eder (A3 kabul: 'oyuna dönüşte eski rect yok')."""
    pu = clean_display.platform_utils
    pygame = clean_display.pygame
    real = pygame.display.get_surface()

    generations = [pu.get_geometry_generation()]
    surfaces = []
    for multiplier in (1.25, 1.0, 1.25):
        surfaces.append(pu.setup_virtual_canvas(real, multiplier))
        generations.append(pu.get_geometry_generation())
    pu._teardown_virtual_canvas()
    generations.append(pu.get_geometry_generation())

    assert all(
        generations[i + 1] > generations[i]
        for i in range(len(generations) - 1)
    ), f"kuşak katı monotone artmalı: {generations}"
    assert surfaces[0] is not surfaces[2], (
        "125 → 100 → 125 döngüsü aynı canvas nesnesini geri vermemeli"
    )
    assert pygame.display.get_surface() is real


# ---------------------------------------------------------------------------
# 5) Telemetri (A0 ucu) + Steam Deck tespiti
# ---------------------------------------------------------------------------

def test_is_steam_deck_env_contract(clean_display, monkeypatch):
    pu = clean_display.platform_utils
    monkeypatch.delenv('STEAMDECK', raising=False)
    assert pu.is_steam_deck() is False
    monkeypatch.setenv('STEAMDECK', '1')
    assert pu.is_steam_deck() is True
    monkeypatch.setenv('STEAMDECK', '0')
    assert pu.is_steam_deck() is False
    monkeypatch.setenv('STEAMDECK', '')
    assert pu.is_steam_deck() is False


def test_record_platform_display_telemetry_line_contents(clean_display, monkeypatch):
    captured = []
    monkeypatch.setattr(
        clean_display.platform_utils, '_gl_diag',
        lambda msg: captured.append(msg),
    )
    monkeypatch.delenv('STEAMDECK', raising=False)

    clean_display.platform_utils.record_platform_display_telemetry(context='test')
    assert len(captured) == 1
    line = captured[0]
    assert 'DISPLAY TELEMETRY [test]' in line
    assert 'platform=' in line
    assert 'window_logical=' in line
    assert 'canvas_active=' in line
    assert 'generation=' in line
    assert 'steam_deck=' not in line  # env yok → bayrak yazılmaz

    monkeypatch.setenv('STEAMDECK', '1')
    clean_display.platform_utils.record_platform_display_telemetry(context='test2')
    assert len(captured) == 2
    assert 'steam_deck=1' in captured[1]


def test_record_platform_display_telemetry_never_raises(clean_display, monkeypatch):
    """Hata yutucu sözleşme: iç bağımlılıklar patlasa bile exception sızmaz."""
    pu = clean_display.platform_utils
    monkeypatch.setattr(
        pu, 'get_window_logical_size',
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    monkeypatch.setattr(
        pu, 'get_render_geometry',
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    pu.record_platform_display_telemetry(context='hata')


# ---------------------------------------------------------------------------
# 6) Üretici ucu: demo settings çevirici aksiyon üretir
# ---------------------------------------------------------------------------

def test_window_resolution_producer_emits_demo_action(live_env):
    """Demo settings `_cycle_selector('window_resolution', ...)` windowed
    modda 'apply_display_mode' aksiyonu üretir ve değeri KAYIT eder; ana
    dispatch'teki FAZ A3 parse entegrasyonu (main.py apply_display_mode
    handler) bu aksiyonu tek rebuild transaction'ıyla tüketir. Demo'da
    4 elemanlı liste döner: 1920x1080 → 1600x900 → 1366x768 → 1280x720."""
    pygame = live_env.pygame
    pu = live_env.platform_utils
    sst = live_env.sst

    pygame.display.set_mode((1920, 1080))
    try:
        pu._teardown_virtual_canvas()
    except Exception:
        pass
    real = pygame.display.get_surface()
    canvas = pu.setup_virtual_canvas(real, 1.0)
    assert canvas is real

    from settings_manager import SettingsManager
    sm = SettingsManager()

    inst = sst.TabbedSettingsScreen(canvas, None, sm)
    stored = {}
    inst._get_value = lambda key, default=None: stored.get(key, '1920x1080')
    inst._set_value = lambda key, value: stored.__setitem__(key, value)

    # Windowed: aksiyon ÜRETİLMELİ (demo sözleşmesi — v2'deki ayrı
    # 'change_window_resolution' adı demo'da yok; rebuild bu aksiyonla gelir).
    inst.fullscreen = False
    action = inst._cycle_selector('window_resolution', +1)
    assert action == 'apply_display_mode'
    assert stored['window_resolution'] == '1600x900'
    assert inst.window_resolution == '1600x900'

    action = inst._cycle_selector('window_resolution', +1)
    assert action == 'apply_display_mode'
    assert stored['window_resolution'] == '1366x768'

    action = inst._cycle_selector('window_resolution', +1)
    assert action == 'apply_display_mode'
    assert stored['window_resolution'] == '1280x720'

    # Döngüsel sarma: son elemandan ileri → başa döner.
    action = inst._cycle_selector('window_resolution', +1)
    assert action == 'apply_display_mode'
    assert stored['window_resolution'] == '1920x1080'

    # Geriye çevirme de simetriktir.
    action = inst._cycle_selector('window_resolution', -1)
    assert action == 'apply_display_mode'
    assert stored['window_resolution'] == '1280x720'

    # Fullscreen: değer YİNE kaydedilir ama aksiyon ÜRETEZ (demo'da rebuild,
    # fullscreen → windowed geçişinde apply_display_mode onay akışından gelir;
    # kayıt o geçişte uygulanmak üzere ayakta kalır).
    inst.fullscreen = True
    action = inst._cycle_selector('window_resolution', +1)
    assert action is None
    assert stored['window_resolution'] == '1920x1080'
    assert inst.window_resolution == '1920x1080'
