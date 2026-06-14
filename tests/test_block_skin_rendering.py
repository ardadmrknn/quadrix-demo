from __future__ import annotations

import os

import pygame

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')


def test_block_appearance_variants_have_distinct_legacy_shine_profile():
    pygame.init()
    try:
        from block_skin_assets import LEGACY_BLOCK_APPEARANCE, MODERN_BLOCK_APPEARANCE
        from renderers.jelly_renderer import draw_jelly_block

        modern = pygame.Surface((32, 32), pygame.SRCALPHA)
        legacy = pygame.Surface((32, 32), pygame.SRCALPHA)

        draw_jelly_block(modern, 4, 4, 24, (90, 180, 255), appearance=MODERN_BLOCK_APPEARANCE)
        draw_jelly_block(legacy, 4, 4, 24, (90, 180, 255), appearance=LEGACY_BLOCK_APPEARANCE)

        modern_corner = modern.get_at((4, 4)).a
        legacy_corner = legacy.get_at((4, 4)).a
        modern_shine = sum(modern.get_at((10, 10))[:3])
        legacy_shine = sum(legacy.get_at((10, 10))[:3])
        modern_center = sum(modern.get_at((16, 16))[:3])
        legacy_center = sum(legacy.get_at((16, 16))[:3])

        assert modern_corner > 0
        assert legacy_corner > 0
        assert legacy_shine > modern_shine
        assert legacy_shine > legacy_center
        assert modern_center > 0
    finally:
        pygame.quit()


def test_gameplay_classes_forward_selected_appearance_to_block_renderer():
    pygame.init()
    try:
        from block_skin_assets import LEGACY_BLOCK_APPEARANCE
        import game as game_module
        import coop_game as coop_module
        import pvp_game as pvp_module
        import online_pvp_game as online_pvp_module

        cases = (
            (game_module, game_module.Game),
            (coop_module, coop_module.CoopGame),
            (pvp_module, pvp_module.PvPGame),
            (online_pvp_module, online_pvp_module.OnlinePvPGame),
        )

        for module, cls in cases:
            draw_calls = []
            border_calls = []
            original_draw = module.draw_jelly_block
            original_border = module.draw_jelly_border
            try:
                module.draw_jelly_block = (
                    lambda surface, x, y, size, color, *, appearance=None: draw_calls.append(appearance)
                )
                module.draw_jelly_border = (
                    lambda surface, x, y, size, color, *, appearance=None: border_calls.append(appearance)
                )
                inst = cls.__new__(cls)
                inst.screen = pygame.Surface((40, 40), pygame.SRCALPHA)
                inst.block_appearance = LEGACY_BLOCK_APPEARANCE
                inst._draw_texture_cell = lambda *args, **kwargs: None

                cls.draw_textured_block(inst, 1, 2, 18, (255, 120, 80))
                cls.draw_textured_block(inst, 1, 2, 18, (255, 120, 80), texture_surface=object(), texture_slice=object())

                assert draw_calls == [LEGACY_BLOCK_APPEARANCE]
                assert border_calls == [LEGACY_BLOCK_APPEARANCE]
            finally:
                module.draw_jelly_block = original_draw
                module.draw_jelly_border = original_border
    finally:
        pygame.quit()