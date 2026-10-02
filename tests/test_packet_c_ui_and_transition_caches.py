"""Paket C test paketi:
- Retro başlık alt çizgisi cache'i ve dar ekran koruması
- Ayarlar paneli arka plan / gölge cache hit ve invalidation
- Sekme (tab) yüzey cache'i (aktif/pasif ayrımı)
- ScreenTransition wipe efekti yeniden kullanılabilir tampon ve ghosting koruması

Modüller module-level import yerine hermetik module-fixture ile yüklenir
(v2 tests/test_settings_preset_transition.py kalıbı, FAZ A4): koleksiyon
anında önceki dosyalar GERÇEK retro_style modülünün `retro_style`
nititeliğini kalıcı stub'la değiştirebiliyor (ör.
test_campaign_debug_unlock_all modül seviyesinde
`sys.modules['retro_style'].retro_style = SimpleNamespace(get_font=FakeFont)`
yazar) — sonradan import edilen settings_screen_tabbed bu stub'ı bağlayınca
_draw_tab_bar stub Font'tan dönen _Surf'ü gerçek Surface'e blit'lemeye
çalışıp TypeError veriyor. Hermetik pop + taze import bu sızıntıyı keser.
"""
import os
import sys

import pygame
import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    # abspath zorunlu: 'tests\..\src' yazımı modül __file__ değerine sızar
    # ve conftest'in _looks_like_test_stub denetimi ('/tests/' alt dizin
    # araması) GERÇEK modülü stub sanıp sys.modules'ten söker. Girdiyi
    # ayrıca koşulsuz ÖNE al: başka test dosyalarının bıraktığı normalize
    # edilmemiş 'tests\..\src' girdisi öndeyse importlar ondan çözümlenir
    # ve aynı yanlış pozitife düşer.
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)


@pytest.fixture(scope="module", autouse=True)
def live_env():
    """Gerçek modülleri hermetik yükle; pygame'i dummy sürücüyle hazırla.

    Test gövdeleri değişmeden kalsın diye yüklenen gerçek nesneler modül
    global'lerine yazılır (retro_style, TabbedSettingsScreen,
    SettingsManager, ScreenTransition). Koleksiyon anında bu adlar
    kirletici dosyaların sys.modules'a bıraktığı stub kopyalara
    bağlanabiliyordu; live_env bu adları her testten önce taze bağlar.
    """
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    _ensure_src_on_path()

    _module_keys = [
        'settings_screen_tabbed', 'constants', 'retro_style',
        'platform_utils', 'background_effects', 'localization',
        'ui_language_profile', 'menu', 'gamepad_manager',
        'promptfont_support', 'ui_scaling', 'settings_manager',
        'text_cache', 'surface_lru_cache', 'ui_theme',
    ]
    # bare VE 'src.' anahtarlarını birlikte temizle: conftest'in
    # _sync_sys_modules_aliases'ı src.* kalıntısını bare anahtarın
    # üzerine geri yazabilir (conftest.py:36-40).
    _module_lookup_keys = [
        key
        for mod in _module_keys
        for key in (mod, f'src.{mod}')
    ]
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

    import retro_style as rs_mod
    import settings_screen_tabbed as sst_mod
    from settings_manager import SettingsManager
    from background_effects import ScreenTransition

    # Hermetiklik sözleşmesi: sst module seviyesinde `from retro_style
    # import retro_style` bağlar — retro_style kaydı bu fixture'ın taze
    # import ettiği modüle işaret etmeli (kirleticinin singleton'u
    # FakeFont stub'ıyla değiştirdiği eski kopya OLMAZ).
    assert sys.modules['settings_screen_tabbed'] is sst_mod
    assert sys.modules['retro_style'] is rs_mod

    # Font zinciri sözleşmesi: _fit_font → get_fitting_font → render
    # gerçek pygame Surface üretmeli (stub zincir _Surf üretir).
    _probe_font = rs_mod.retro_style.get_fitting_font('SÖZLEŞME', 18, 200)
    _probe_surf = _probe_font.render('SÖZLEŞME', True, (255, 255, 255))
    assert isinstance(_probe_surf, pygame.Surface)

    _g = globals()
    _g['retro_style'] = rs_mod.retro_style
    _g['TabbedSettingsScreen'] = sst_mod.TabbedSettingsScreen
    _g['SettingsManager'] = SettingsManager
    _g['ScreenTransition'] = ScreenTransition

    yield

    # Orijinal init_pygame teardown davranışı: modül bittiğinde pygame'i
    # kapat (sonraki dosyalar kendi init'lerini çağırır).
    pygame.quit()

    # Sonraki test dosyalarına temiz durum bırak: orijinal kayıtları geri koy.
    for _key, _original in _original_modules.items():
        if _original is not None:
            sys.modules[_key] = _original
        else:
            sys.modules.pop(_key, None)
    if _pygame_leaked is not None and _pygame_leaked is not pygame:
        sys.modules['pygame'] = _pygame_leaked
    elif _pygame_leaked is None:
        sys.modules.pop('pygame', None)


def test_retro_title_underline_cache_hit():
    """Aynı başlık alt çizgisi parametrelerinde aynı Surface nesnesinin döndüğünü doğrula."""
    screen = pygame.Surface((800, 600))
    retro_style._title_underline_cache.clear()
    retro_style._title_underline_cache_order.clear()

    # İlk çizim (cache miss)
    rect1 = retro_style.draw_title(screen, "AYARLAR", (400, 80))
    assert len(retro_style._title_underline_cache) == 1

    first_key = list(retro_style._title_underline_cache.keys())[0]
    surf1 = retro_style._title_underline_cache[first_key]
    assert isinstance(surf1, pygame.Surface)

    # İkinci çizim aynı parametrelerle (cache hit)
    rect2 = retro_style.draw_title(screen, "AYARLAR", (400, 80))
    assert len(retro_style._title_underline_cache) == 1
    assert retro_style._title_underline_cache[first_key] is surf1
    assert rect1 == rect2


def test_retro_title_underline_color_and_width_change():
    """Tema rengi veya genişlik değişiminde yeni Surface üretildiğini ve dar ekran korumasını test et."""
    screen = pygame.Surface((800, 600))
    retro_style._title_underline_cache.clear()
    retro_style._title_underline_cache_order.clear()

    # Normal başlık
    retro_style.draw_title(screen, "KISA", (400, 80))
    count_before = len(retro_style._title_underline_cache)
    assert count_before == 1

    # Daha uzun başlık (farklı genişlik -> yeni cache girdisi)
    retro_style.draw_title(screen, "COK DAHA UZUN BIR BASLIK METNI BURADA", (400, 80))
    assert len(retro_style._title_underline_cache) == 2

    # Renk değişimi
    old_primary = retro_style.primary
    try:
        retro_style.primary = (255, 100, 50)
        retro_style.draw_title(screen, "KISA", (400, 80))
        assert len(retro_style._title_underline_cache) == 3
    finally:
        retro_style.primary = old_primary

    # Şeffaflık değişimi invalidation testi
    retro_style.set_menu_transparency(0.5)
    assert len(retro_style._title_underline_cache) == 0
    retro_style.set_menu_transparency(1.0)

    # Dar ekran koruması: çok dar bir ekranda line_width <= 0 durumu
    tiny_screen = pygame.Surface((50, 50))
    retro_style._title_underline_cache.clear()
    # 50 piksel genişlikte width - 100 negatif olur, line_width <= 0 olmalı ve crash etmemeli
    rect_tiny = retro_style.draw_title(tiny_screen, "TEST", (25, 25))
    assert rect_tiny is not None
    assert len(retro_style._title_underline_cache) == 0


def test_settings_panel_cache_hit_and_invalidation():
    """Ayarlar paneli cache hit ve invalidation davranışını test et."""
    screen = pygame.Surface((1280, 720))
    sm = SettingsManager()
    tabbed = TabbedSettingsScreen(screen, None, sm)

    panel_rect = pygame.Rect(100, 80, 1080, 560)
    tabbed._panel_bg_cache.clear()
    tabbed._panel_shadow_cache.clear()

    # İlk panel çizimi (miss)
    tabbed._draw_panel(panel_rect)
    assert len(tabbed._panel_bg_cache._cache) == 1
    assert len(tabbed._panel_shadow_cache._cache) == 1

    panel_key = list(tabbed._panel_bg_cache._cache.keys())[0]
    shadow_key = list(tabbed._panel_shadow_cache._cache.keys())[0]
    bg_surf1 = tabbed._panel_bg_cache.get(panel_key)
    sh_surf1 = tabbed._panel_shadow_cache.get(shadow_key)

    # İkinci panel çizimi (hit)
    tabbed._draw_panel(panel_rect)
    assert tabbed._panel_bg_cache.get(panel_key) is bg_surf1
    assert tabbed._panel_shadow_cache.get(shadow_key) is sh_surf1

    # Invalidation kontrolü
    tabbed._clear_ui_caches()
    assert len(tabbed._panel_bg_cache._cache) == 0
    assert len(tabbed._panel_shadow_cache._cache) == 0


def test_settings_tab_active_vs_inactive_cache():
    """Aktif ve pasif sekmelerin farklı yüzeyler kullandığını ve cache'lendiğini test et."""
    screen = pygame.Surface((1280, 720))
    sm = SettingsManager()
    tabbed = TabbedSettingsScreen(screen, None, sm)

    tabbed._tab_surf_cache.clear()
    bar_rect = pygame.Rect(100, 150, 1080, 48)
    tabbed.current_tab = 0
    tabbed._draw_tab_bar(bar_rect)

    # En az 1 aktif ve 1 pasif sekme cache'lenmiş olmalı
    assert len(tabbed._tab_surf_cache._cache) >= 2

    # Aktif ve pasif yüzeylerin birbirinden farklı olduğunu doğrula
    active_surfaces = []
    inactive_surfaces = []
    for key, surf in tabbed._tab_surf_cache._cache.items():
        # key: (kuşak, tab_rect.size, is_active, fill_color, scale_val)
        # FAZ A4: kuşak bileşeni öne eklendi — is_active artık key[2].
        is_active = key[2]
        if is_active:
            active_surfaces.append(surf)
        else:
            inactive_surfaces.append(surf)

    assert len(active_surfaces) >= 1
    assert len(inactive_surfaces) >= 1
    assert active_surfaces[0] is not inactive_surfaces[0]


def test_wipe_transition_buffer_reuse_and_ghosting_guard():
    """Wipe efektinin tamponları yeniden kullandığını ve ekran boyutu değişimini yönettiğini test et."""
    screen = pygame.Surface((800, 600))
    st = ScreenTransition(duration_ms=500, transition_type=ScreenTransition.WIPE)
    st.start(screen)

    # Yarım aşamada (perde kapanırken) çizim
    st.phase = 'out'
    st.progress = 0.5
    st.draw(screen)

    assert st._wipe_left_surf is not None
    assert st._wipe_right_surf is not None
    buf_size = st._wipe_buffer_size
    assert buf_size == ((800 + 1) // 2, 600)
    left_buf_1 = st._wipe_left_surf
    right_buf_1 = st._wipe_right_surf

    # İkinci karede çizim: aynı tampon nesneleri korunmalı (her kare yeni tahsis yok)
    st.progress = 0.6
    st.draw(screen)
    assert st._wipe_left_surf is left_buf_1
    assert st._wipe_right_surf is right_buf_1

    # Ekran boyutu değiştiğinde tamponların güvenle yenilenmesi
    screen_large = pygame.Surface((1920, 1080))
    st.draw(screen_large)
    assert st._wipe_buffer_size == ((1920 + 1) // 2, 1080)
    assert st._wipe_left_surf is not left_buf_1
