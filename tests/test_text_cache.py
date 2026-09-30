"""
Birim testleri: src/text_cache.py PatchedFont, render_shared ve kopya güvenliği.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pygame
import text_cache


class TestTextCache(unittest.TestCase):
    """Metin render önbelleği güvenlik ve paylaşımlı yüzey testleri."""

    def setUp(self):
        pygame.init()
        if hasattr(pygame.font, 'init'):
            pygame.font.init()
        text_cache.patch_font()
        text_cache.clear_text_cache()
        self.font = pygame.font.Font(None, 24)

    def tearDown(self):
        text_cache.clear_text_cache()
        pygame.quit()

    def test_default_render_copy_mutation_safety(self):
        """Bir çağrının set_alpha() uygulaması sonraki render() çağrısının Surface'ini bozamaz."""
        surf1 = self.font.render("Skor: 1000", True, (255, 255, 255))
        # Yüzeyin mutasyona uğratılması:
        surf1.set_alpha(80)
        self.assertEqual(surf1.get_alpha(), 80)

        # Aynı anahtarla ikinci render:
        surf2 = self.font.render("Skor: 1000", True, (255, 255, 255))
        # surf2 surf1'in mutasyonundan etkilenmemeli (orijinal alfa korunmalı)
        self.assertNotEqual(surf1, surf2, "Varsayılan render güvenli kopya döndürmeli")
        self.assertNotEqual(surf2.get_alpha(), 80, "Sonraki render'ın alfası önceki mutasyonla bozulmamalı")

    def test_shared_render_returns_same_surface_on_cache_hit(self):
        """render_shared veya render_text_shared salt-okunur durumlarda aynı Surface nesnesini döndürebilir."""
        surf1 = text_cache.render_text_shared(self.font, "Level 5", True, (200, 220, 255))
        surf2 = text_cache.render_text_shared(self.font, "Level 5", True, (200, 220, 255))

        self.assertIs(surf1, surf2, "render_shared cache hit durumunda aynı nesneyi döndürmeli")

    def test_clear_text_cache_invalidates_all(self):
        """clear_text_cache çağrıldığında cache temizlenmeli ve yeni Surface üretilmeli."""
        surf1 = text_cache.render_text_shared(self.font, "Quadrix", True, (0, 255, 200))
        text_cache.clear_text_cache()
        surf2 = text_cache.render_text_shared(self.font, "Quadrix", True, (0, 255, 200))

        self.assertIsNot(surf1, surf2, "Cache temizlendikten sonra yeni Surface üretilmeli")


if __name__ == '__main__':
    unittest.main()
