"""
Phase 1 testleri: UIFonts.get() pygame.font.Font(None, ...) başarısız olsa bile crash etmemeli.

Regresyon testi: Paketli EXE/.app'lerde freesansbold.ttf eksik olduğunda
UIFonts.get() ve _get_latin_font() sistem fontu fallback ile devam edebilmeli.
"""
from __future__ import annotations

import sys
import os
import types
import importlib

import pytest

# src/ dizinini import path'ine ekle
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _ensure_clean_imports():
    """Önceki testlerden kalan bozuk stub modülleri temizle ve gerçek modülleri yükle."""
    # constants modülü önceki bir test tarafından stub'lanmış olabilir
    _const = sys.modules.get("constants")
    if _const is not None and not hasattr(_const, "NEON_CYAN"):
        # Bozuk stub — kaldır ve zincirdeki bağımlıları da temizle
        for mod_name in list(sys.modules):
            if mod_name in ("constants", "src.constants",
                            "retro_style", "src.retro_style",
                            "ui_theme", "src.ui_theme",
                            "background", "src.background"):
                sys.modules.pop(mod_name, None)

    # pygame stub kontrol — herhangi bir stub varsa temizle; gerçek pygame zorla yüklensin.
    # Gerçek pygame-ce'nin 'ver' attribute'u vardır; stub'larda bulunmaz.
    _pg = sys.modules.get("pygame")
    if _pg is not None and not hasattr(_pg, "ver"):
        sys.modules.pop("pygame", None)
        for sub in [k for k in sys.modules if k.startswith("pygame.")]:
            sys.modules.pop(sub, None)


_ensure_clean_imports()


def _ensure_pygame_font_init():
    """Headless ortamda pygame font subsystem'ini başlat."""
    import pygame
    # pygame.font submodülü attribute olarak erişilebilir değilse açıkça import et
    if not hasattr(pygame, "font"):
        import pygame.font  # noqa: F401
    if not pygame.font.get_init():
        pygame.font.init()


def test_ui_fonts_get_falls_back_when_default_font_missing(monkeypatch):
    """
    pygame.font.Font(None, size) FileNotFoundError fırlatsa bile
    UIFonts.get() exception fırlatmamalı ve render() destekleyen
    bir font objesi dönmeli.
    """
    import pygame
    _ensure_pygame_font_init()

    # ui_theme modülünü temiz yükle (cache sorunlarını önle)
    for mod in list(sys.modules.keys()):
        if "ui_theme" in mod:
            del sys.modules[mod]

    import ui_theme
    from ui_theme import UIFonts

    original_font_cls = pygame.font.Font

    def patched_font(path, size, *args, **kwargs):
        if path is None:
            raise FileNotFoundError("freesansbold.ttf bulunamadı (simüle)")
        return original_font_cls(path, size, *args, **kwargs)

    # pygame.font.Font'u hem pygame modülünde hem ui_theme'in kullandığı
    # pygame referansında monkeypatch yap
    monkeypatch.setattr(pygame.font, "Font", patched_font)

    # Cache'i temizle ve profili sıfırla
    UIFonts.set_font_profile(font_path=None, size_scale=1.0)

    # Bu çağrı Font(None) başarısız olsa da exception fırlatmamalı
    result = UIFonts.get(22, bold=True)

    # Dönüş değeri pygame Font API'sini desteklemeli
    assert result is not None, "UIFonts.get() None döndürmemeli"
    assert hasattr(result, "render"), "Dönen objenin render() metodu olmalı"


def test_ui_fonts_get_falls_back_when_default_font_missing_no_bold(monkeypatch):
    """
    bold=False durumunda da fallback zinciri çalışmalı.
    """
    import pygame
    _ensure_pygame_font_init()

    for mod in list(sys.modules.keys()):
        if "ui_theme" in mod:
            del sys.modules[mod]

    import ui_theme
    from ui_theme import UIFonts

    original_font_cls = pygame.font.Font

    def patched_font(path, size, *args, **kwargs):
        if path is None:
            raise FileNotFoundError("freesansbold.ttf bulunamadı (simüle)")
        return original_font_cls(path, size, *args, **kwargs)

    monkeypatch.setattr(pygame.font, "Font", patched_font)
    UIFonts.set_font_profile(font_path=None, size_scale=1.0)

    result = UIFonts.get(18, bold=False)

    assert result is not None
    assert hasattr(result, "render")


def test_ui_fonts_get_returns_font_normally():
    """
    Normal koşullarda (Font(None) çalışıyor) UIFonts.get() hâlâ çalışmalı.
    """
    import pygame
    _ensure_pygame_font_init()

    for mod in list(sys.modules.keys()):
        if "ui_theme" in mod:
            del sys.modules[mod]

    import ui_theme
    from ui_theme import UIFonts

    UIFonts.set_font_profile(font_path=None, size_scale=1.0)

    result = UIFonts.get(22)
    assert result is not None
    assert hasattr(result, "render")


def test_ui_fonts_latin_font_fallback_when_default_missing(monkeypatch):
    """
    _get_latin_font() çağrısında da Font(None) başarısız olsa fallback devreye girmeli.
    _default_font_path=None iken _get_latin_font dolaylı olarak test ediliyor.
    """
    import pygame
    _ensure_pygame_font_init()

    for mod in list(sys.modules.keys()):
        if "ui_theme" in mod:
            del sys.modules[mod]

    import ui_theme
    from ui_theme import UIFonts

    original_font_cls = pygame.font.Font

    def patched_font(path, size, *args, **kwargs):
        if path is None:
            raise FileNotFoundError("freesansbold.ttf bulunamadı (simüle)")
        return original_font_cls(path, size, *args, **kwargs)

    monkeypatch.setattr(pygame.font, "Font", patched_font)

    # _default_font_path=None iken _get_latin_font çağrısı
    UIFonts._cache.clear()
    UIFonts._default_font_path = None

    result = UIFonts._get_latin_font(22, True)
    assert result is not None
    assert hasattr(result, "render")
