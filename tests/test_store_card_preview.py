"""Kart ürünü önizleme çizim yolu için regresyon kapsamı.

OP-010 kart önizleme önbelleği (ve onun import/anahtar hesapları)
demo test paketinde hiçbir testle çalıştırılmıyordu; ölçüm probe'u
(probe_store_draw_perf.py) bunu NameError olarak yakaladı. Bu dosya
o boşluğu kapatır: hero ve ray yolları bir offscreen Surface üzerinde
hatasız çizilmeli. Kurulum deseni test_store_block_products.py ile
aynı (runtime import + dummy sürücü + retro_style önbellek temizliği).
"""
from __future__ import annotations

import os

import pygame

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')


def _reset_retro_style_cache() -> None:
    from retro_style import retro_style

    retro_style.font_cache.clear()
    retro_style._render_cache.clear()
    retro_style._render_cache_order.clear()


class _DummyUserManager:
    def __init__(self):
        self.profile = {
            'neural_fragments': 700,
            'owned_cosmetics': [],
            'equipped_cosmetics': {},
        }

    def get_current_user(self):
        return 'Arda'

    def get_user_data(self, username=None):
        return self.profile


def test_card_product_preview_renders_without_exception():
    """Kart ürünü önizlemesi hero ve ray yollarında hatasız çizilmeli."""
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(
            pygame.Surface((1280, 720), pygame.SRCALPHA),
            user_manager=_DummyUserManager(),
        )

        card_idx = next(
            (i for i, product in enumerate(screen.products) if screen._is_card_product(product)),
            None,
        )
        assert card_idx is not None, 'katalogda kart urunu yok'

        product = screen.products[card_idx]
        rect = pygame.Rect(0, 0, 220, 260)
        # hero=True (seçili ürün bandı) ve hero=False (koleksiyon rayı)
        # iki yol da calismali; OP-010 onbellek sarmasi bu cagrilarda
        # anahtar hesabi ve blit yolunu tam calistirir.
        screen._draw_product_preview(product, rect, hero=True)
        screen._draw_product_preview(product, rect, hero=False)
    finally:
        pygame.quit()


def test_card_preview_cache_hit_returns_same_surface():
    """Aynı anahtar art arda çağrıldığında önbellekten aynı yüzey dönmeli."""
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(
            pygame.Surface((1280, 720), pygame.SRCALPHA),
            user_manager=_DummyUserManager(),
        )

        card_idx = next(
            (i for i, product in enumerate(screen.products) if screen._is_card_product(product)),
            None,
        )
        assert card_idx is not None, 'katalogda kart urunu yok'
        product = screen.products[card_idx]
        rect = pygame.Rect(0, 0, 220, 260)

        screen._draw_product_preview(product, rect, hero=True)
        cache = getattr(screen, '_card_preview_cache', None)
        assert cache, 'kart onizleme onbellegi kurulmali'
        first_key = next(iter(cache))
        assert cache[first_key].get_size() == (220, 260)
        screen._draw_product_preview(product, rect, hero=True)
        # Ikinci cagri ayni anahtari kullanmali (yeni anahtar eklenmemeli).
        assert set(cache.keys()) == {first_key}
    finally:
        pygame.quit()
