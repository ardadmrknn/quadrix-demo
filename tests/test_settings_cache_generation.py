"""FAZ A4 (v2 paritesi, S3): ayarlar surface cache kuşağı sözleşme testleri.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A4'ün demo karşılığıdır. Demo'da
runtime preset değişimi yok (preset dalı bilinçli no-op); kuşağın demo'daki
sürücüsü draw imza değişimidir (boyut/tema/dil/alfa/ölçek → _clear_ui_caches).
Sözleşme:
1. _bump_ui_cache_generation: üç yüzey cache'ini temizler + kuşağı artırır.
2. Panel/gölge/sekme cache anahtarlarının İLK bileşeni kuşaktır; bump
   sonrası üretilen tüm anahtarlar güncel kuşağı taşır.
3. Aynı görsel parametrelerle (boyut/renk/ölçek aynı) bump sonrası yapılan
   çizim bayat yüzeye değil, taze yüzeye hit eder (kuşak çakışma koruması).
4. _clear_ui_caches (draw imza yolu) kuşağı da artırır — clear + anahtar
   değişimi çifte güvence.
5. Kuşak okumaları tolerant'tır: __init__'siz kurulan minimal instance'lar
   (test __new__ kalıbı) alanı taşımayabilir; bu durumda kuşak 0'dır.

Paket C kalıbını izler: gerçek modüller + dummy sürücüler (canlı pygame).
Modüller module-level import yerine hermetik module-fixture ile yüklenir
(v2 tests/test_settings_preset_transition.py kalıbı): koleksiyon anındaki
sys.modules kirliliği önceki dosyaların stub pygame'ine bağlı kopyalar
yakalayabiliyor — retro_style'ın modül seviyesi font cache'ine stub Font'lar
birikince _draw_tab_bar gerçek Surface'e _Surf blit'lemeye çalışıyor.
Önc-var kırmızı yok: bu dosya FAZ A4 ile birlikte eklendi.
"""
import os
import sys
import types

# Modül seviyesinde (koleksiyon anı = temiz süreç durumu) gerçek pygame'i
# bağla. Tam paket koşusunda önceki test dosyaları pygame'i sys.modules'ten
# sökebiliyor; süit ortasında yapılan gerçek import Windows'ta WinError 206
# (os.add_dll_directory) ile başarısız olabiliyor. Aşağıdaki hermetik
# fixture pygame kaydı yoksa bu koleksiyon-anı nesnesini yeniden kaydeder.
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
    # ve aynı yanlış pozitife düşer. İki girdi aynı fiziksel dizini
    # gösterir; yalnızca yazım farkı vardır.
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)


@pytest.fixture(scope="module", autouse=True)
def live_env():
    """Gerçek modülleri hermetik yükle; pygame'i dummy sürücüyle hazırla.

    Koleksiyon-zamanı module-level import'lar, önceki toplanan dosyaların
    sys.modules'a bıraktığı stub pygame'e / bayat kopyalara bağlanabiliyor.
    İlgili anahtarların bare VE 'src.' varyantlarını temizleyip taze import
    ediyoruz (conftest'in _sync_sys_modules_aliases'ı src.* kalıntısını
    bare anahtarın üzerine geri yazabildiği için ikisi de gerekli).
    text_cache ve retro_style dahil: retro_style'ın modül seviyesi font
    cache'i bayat/stub Font'lar taşıyabiliyor.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    _ensure_src_on_path()

    _module_keys = [
        'settings_screen_tabbed', 'constants', 'retro_style',
        'platform_utils', 'background_effects', 'localization',
        'ui_language_profile', 'menu', 'gamepad_manager',
        'promptfont_support', 'ui_scaling', 'settings_manager',
        'text_cache', 'surface_lru_cache',
    ]
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

    import settings_screen_tabbed as sst
    import surface_lru_cache
    from settings_manager import SettingsManager

    # Hermetiklik sözleşmesi: sst'nin font/render yolu module-level
    # bağlantılarını kullanır (retro_style, text_cache) — bu kayıtların
    # fixture'ın bağladığı taze kopyalara işaret etmesi gerekir; farklı
    # bir kopya, izolasyonun kırıldığını (stub sızıntısı) gösterir.
    assert sys.modules['settings_screen_tabbed'] is sst
    assert sys.modules['surface_lru_cache'] is surface_lru_cache

    yield types.SimpleNamespace(
        pygame=pygame, sst=sst,
        surface_lru_cache=surface_lru_cache,
        SettingsManager=SettingsManager,
    )

    # Sonraki test dosyalarına temiz durum bırak: orijinal kayıtları geri
    # koy (pop edilip yeniden import edilen anahtarlar, bu modülden SONRA
    # koşan dosyaların modül-kimliği tutarlılığını bozmasın).
    for _key, _original in _original_modules.items():
        if _original is not None:
            sys.modules[_key] = _original
        else:
            sys.modules.pop(_key, None)
    if _pygame_leaked is not None and _pygame_leaked is not pygame:
        sys.modules['pygame'] = _pygame_leaked
    elif _pygame_leaked is None:
        sys.modules.pop('pygame', None)


@pytest.fixture()
def tabbed(live_env):
    screen = live_env.pygame.Surface((1280, 720))
    sm = live_env.SettingsManager()
    inst = live_env.sst.TabbedSettingsScreen(screen, None, sm)
    yield types.SimpleNamespace(inst=inst, screen=screen)
    inst._clear_ui_caches()


def _fill_caches(inst) -> None:
    inst._draw_panel(pygame.Rect(100, 80, 1080, 560))
    inst._draw_tab_bar(pygame.Rect(100, 150, 1080, 48))


def _cache_len(cache) -> int:
    return len(getattr(cache, '_cache', cache))


# ---------------------------------------------------------------------------
# 1) Bump: cache'leri temizler + kuşağı artırır
# ---------------------------------------------------------------------------

def test_bump_clears_caches_and_advances_generation(tabbed):
    inst = tabbed.inst
    gen0 = inst._ui_cache_generation

    _fill_caches(inst)
    assert _cache_len(inst._panel_bg_cache) >= 1
    assert _cache_len(inst._panel_shadow_cache) >= 1
    assert _cache_len(inst._tab_surf_cache) >= 2

    inst._bump_ui_cache_generation()

    assert inst._ui_cache_generation == gen0 + 1
    assert _cache_len(inst._panel_bg_cache) == 0
    assert _cache_len(inst._panel_shadow_cache) == 0
    assert _cache_len(inst._tab_surf_cache) == 0


# ---------------------------------------------------------------------------
# 2) Anahtarlar kuşağı taşır (panel/gölge/sekme — hepsi k[0])
# ---------------------------------------------------------------------------

def test_cache_keys_carry_current_generation(tabbed):
    inst = tabbed.inst

    inst._bump_ui_cache_generation()
    gen = inst._ui_cache_generation
    _fill_caches(inst)

    for key in inst._panel_bg_cache._cache:
        assert key[0] == gen, f"panel anahtarı kuşağı {gen} olmalı: {key}"
    for key in inst._panel_shadow_cache._cache:
        assert key[0] == gen, f"gölge anahtarı kuşağı {gen} olmalı: {key}"
    for key in inst._tab_surf_cache._cache:
        assert key[0] == gen, f"sekme anahtarı kuşağı {gen} olmalı: {key}"


# ---------------------------------------------------------------------------
# 3) Kuşak artışından sonra aynı görsel parametreler bayata hit etmez
# ---------------------------------------------------------------------------

def test_same_params_miss_after_generation_bump(tabbed):
    inst = tabbed.inst

    _fill_caches(inst)
    old_panel_key = list(inst._panel_bg_cache._cache.keys())[0]
    old_panel_surf = inst._panel_bg_cache.get(old_panel_key)

    # Kuşak artışı (draw imza değişiminin demo'daki karşılığı)
    inst._bump_ui_cache_generation()

    _fill_caches(inst)
    new_panel_key = list(inst._panel_bg_cache._cache.keys())[0]

    assert new_panel_key != old_panel_key, (
        "aynı görsel parametreler kuşak artışından sonra farklı anahtar "
        "üretmeli (bayat girişe anahtar çakışması)"
    )
    assert inst._panel_bg_cache.get(new_panel_key) is not old_panel_surf


# ---------------------------------------------------------------------------
# 4) _clear_ui_caches (draw imza yolu) kuşağı da artırır
# ---------------------------------------------------------------------------

def test_clear_ui_caches_bumps_generation(tabbed):
    inst = tabbed.inst
    gen0 = inst._ui_cache_generation

    _fill_caches(inst)
    inst._clear_ui_caches()

    assert inst._ui_cache_generation == gen0 + 1
    assert _cache_len(inst._panel_bg_cache) == 0
    assert _cache_len(inst._tab_surf_cache) == 0


# ---------------------------------------------------------------------------
# 5) Tolerant okuma: __init__'siz minimal instance'da bump çalışır
# ---------------------------------------------------------------------------

def test_minimal_instance_bump_works_without_init(live_env):
    sst = live_env.sst
    inst = sst.TabbedSettingsScreen.__new__(sst.TabbedSettingsScreen)
    # Bilinçli: __init__ çağrılmaz — bump getattr ile okumalı (stub/test
    # __new__ kalıbı, test_phase5_settings_ui_scaling.py ile aynı aile).
    inst.screen = live_env.pygame.Surface((800, 600))
    inst._panel_bg_cache = live_env.surface_lru_cache.SurfaceLRUCache(4)
    inst._panel_shadow_cache = live_env.surface_lru_cache.SurfaceLRUCache(4)
    inst._tab_surf_cache = live_env.surface_lru_cache.SurfaceLRUCache(8)

    inst._bump_ui_cache_generation()
    assert inst._ui_cache_generation == 1
