"""
Regresyon Testi: Windows Sistem Font Kaydı (winreg DWORD / TypeError) Fallback Testleri

Bu test, Cince/CJK Windows sistemlerinde (veya bazi font yonetim araclarinda)
SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts anahtarinda metin yerine tamsayi (DWORD)
deger bulundugunda Pygame'in initsysfonts_win32 / match_font fonksiyonlarinin firlattigi
`TypeError: expected str, bytes or os.PathLike object, not int` hatasini simule eder.

Test, retro_style, ui_theme ve ui_language_profile modullerinin bu durumda
crash etmeden guvenli varsayilan fontlara fallback yaptigini dogrular.
"""
from __future__ import annotations

import sys
import os
import pytest

# src/ dizinini import path'ine ekle
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _ensure_clean_imports():
    """Önceki testlerden kalan bozuk stub modülleri temizle ve gerçek modülleri yükle."""
    for mod_name in list(sys.modules):
        if mod_name in ("constants", "src.constants",
                        "retro_style", "src.retro_style",
                        "ui_theme", "src.ui_theme",
                        "background", "src.background",
                        "ui_language_profile", "src.ui_language_profile"):
            sys.modules.pop(mod_name, None)

    _pg = sys.modules.get("pygame")
    if _pg is not None and not hasattr(_pg, "ver"):
        sys.modules.pop("pygame", None)
        for sub in [k for k in sys.modules if k.startswith("pygame.")]:
            sys.modules.pop(sub, None)


_ensure_clean_imports()


def _ensure_pygame_font_init():
    import pygame
    if not hasattr(pygame, "font"):
        import pygame.font  # noqa: F401
    if not pygame.font.get_init():
        pygame.font.init()


def test_retro_style_handles_winreg_match_font_typeerror(monkeypatch):
    """
    retro_style.get_font() pygame.font.match_font TypeError firlatinca
    crash etmemeli ve gecerli bir font nesnesi dondurmeli.
    """
    import pygame
    _ensure_pygame_font_init()

    def broken_match_font(name):
        raise TypeError("expected str, bytes or os.PathLike object, not int")

    monkeypatch.setattr(pygame.font, "match_font", broken_match_font)

    from retro_style import retro_style
    retro_style.font_cache.clear()

    font = retro_style.get_font(22, bold=True)
    assert font is not None
    assert hasattr(font, "render")


def test_ui_fonts_handles_winreg_match_font_typeerror(monkeypatch):
    """
    UIFonts.get() pygame.font.match_font TypeError firlatinca
    crash etmemeli ve gecerli bir font nesnesi dondurmeli.
    """
    import pygame
    _ensure_pygame_font_init()

    def broken_match_font(name):
        raise TypeError("expected str, bytes or os.PathLike object, not int")

    monkeypatch.setattr(pygame.font, "match_font", broken_match_font)

    from ui_theme import UIFonts
    UIFonts.clear_cache()

    font = UIFonts.get(20, bold=False)
    assert font is not None
    assert hasattr(font, "render")


def test_ui_language_profile_zh_handles_winreg_match_font_typeerror(monkeypatch):
    """
    Cince (zh) dil profili yuklenirken match_font TypeError firlatsa dahi
    get_font_for_language('zh', ...) crash etmemeli.
    """
    _ensure_clean_imports()
    import pygame
    _ensure_pygame_font_init()

    def broken_match_font(name):
        raise TypeError("expected str, bytes or os.PathLike object, not int")

    monkeypatch.setattr(pygame.font, "match_font", broken_match_font)

    from ui_language_profile import get_font_for_language, apply_language_ui_profile, _ui_font_cache
    from retro_style import retro_style
    from ui_theme import UIFonts

    _ui_font_cache.clear()
    retro_style.font_cache.clear()
    UIFonts.clear_cache()

    apply_language_ui_profile("zh")
    font = get_font_for_language("zh", 24, bold=True)
    assert font is not None
    assert hasattr(font, "render")


def test_sysfont_initsysfonts_win32_typeerror_global_patch(monkeypatch):
    """
    pygame.sysfont.initsysfonts_win32 TypeError firlattiginda
    global yamanin bunu guvenle yakaladigini ve SysFont / match_font
    cagrilarinin exception firlatmadigini dogrular.
    """
    import pygame
    _ensure_pygame_font_init()

    try:
        import pygame.sysfont
        def broken_initsysfonts_win32():
            raise TypeError("expected str, bytes or os.PathLike object, not int")

        monkeypatch.setattr(pygame.sysfont, "initsysfonts_win32", broken_initsysfonts_win32)
    except Exception:
        pass

    # text_cache import edildiginde yamanin aktif oldugundan emin ol
    import text_cache  # noqa: F401

    res_match = pygame.font.match_font("Arial")
    assert res_match is None or isinstance(res_match, str)

    res_sys = pygame.font.SysFont(None, 24)
    assert res_sys is not None
    assert hasattr(res_sys, "render")
