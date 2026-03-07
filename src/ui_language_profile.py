"""Language-specific UI profile switching.

This module centralizes bundled UI font selection for both CJK and
Latin-script languages.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import pygame

from retro_style import retro_style, HybridFont
from ui_theme import UIFonts


_CJK_LANGS = {"ja", "zh", "ko"}
_LATIN_SCRIPT_LANGS = {"tr", "en", "de", "fr", "es", "it", "pt"}
_LATIN_DEFAULT_FONT_PATH = os.path.join("font", "latin_deneme", "PixeloidSans.ttf")

_PROFILE_BY_LANG = {
    "ja": {
        "font_path": os.path.join("font", "ki-cho-jis_0310", "KikaiChokokuJIS-Md.otf"),
        "size_scale": 1.0,
        "force_no_bold": True,
    },
    "zh": {
        "font_path": os.path.join("font", "cinecaption Regular", "ChildFunSans-CHS.ttf"),
        "size_scale": 1.0,
        "force_no_bold": True,
    },
    "ko": {
        "font_path": os.path.join("font", "paperlogy", "Paperlogy-4Regular.ttf"),
        "size_scale": 1.0,
        "force_no_bold": True,
    },
    # NOT: KyrillaSansSerif-Black.ttf Kiril glyphlerini desteklemiyor
    # (boş/şeffaf piksel üretiyor). Rusça için sistem fontları (Segoe UI,
    # Arial, DejaVu Sans) Kiril'i native olarak destekler; ayrı profil
    # gerekmez. İleride uygun bir Kiril fontu bulunursa buraya eklenebilir.
}

# Dil bazlı önceden yüklenmiş font cache'i (dil paneli vb. için)
_ui_font_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}


def _normalize_lang_code(lang_code: Optional[str]) -> str:
    normalized = (lang_code or "").lower()
    if normalized == "jp":
        return "ja"
    return normalized


def is_latin_script_language(lang_code: Optional[str]) -> bool:
    return _normalize_lang_code(lang_code) in _LATIN_SCRIPT_LANGS


def _resolve_font_path(rel_path: Optional[str]) -> Optional[str]:
    if not rel_path:
        return None

    candidates: list[str] = []

    # 1) Kaynak koddan çalışırken proje kökü (../src -> ..)
    try:
        src_based_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        candidates.append(os.path.join(src_based_root, rel_path))
    except Exception:
        pass

    # 2) PyInstaller onefile/onedir extraction root
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(os.path.abspath(meipass), rel_path))
    except Exception:
        pass

    # 3) Frozen exe yanında dağıtım klasörü
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidates.append(os.path.join(exe_dir, rel_path))
    except Exception:
        pass

    # 4) Çalışma dizini fallback
    try:
        candidates.append(os.path.join(os.path.abspath(os.getcwd()), rel_path))
    except Exception:
        pass

    # Sırayı koruyarak tekrarları temizle
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return None


def get_font_for_language(lang_code: str, size: int, bold: bool = False) -> Optional[pygame.font.Font]:
    """Belirli bir dil kodu için uygun fontu döndür.

    CJK dilleri için HybridFont (Latin+CJK), profili olan diğer diller için
    pygame.font.Font döndürür. Profil yoksa None döner.
    """
    lang_code = _normalize_lang_code(lang_code)
    key = (lang_code, size, bool(bold))
    if key in _ui_font_cache:
        return _ui_font_cache[key]

    profile = _PROFILE_BY_LANG.get(lang_code)
    font_path = None
    if lang_code in _LATIN_SCRIPT_LANGS:
        font_path = _resolve_font_path(_LATIN_DEFAULT_FONT_PATH)
    elif profile:
        font_path = _resolve_font_path(profile.get("font_path"))

    if not font_path:
        return None

    try:
        if not pygame.font.get_init():
            pygame.font.init()
        if lang_code in _CJK_LANGS:
            cjk_font = pygame.font.Font(font_path, size)
            if bold:
                cjk_font.set_bold(True)
            latin_font = retro_style._get_latin_font(size, False)
            loaded = HybridFont(latin_font, cjk_font)
        else:
            loaded = pygame.font.Font(font_path, size)
            if bold:
                loaded.set_bold(True)
        _ui_font_cache[key] = loaded
        return loaded
    except Exception:
        return None
def apply_language_ui_profile(lang_code: str) -> None:
    """Apply language-specific UI font profile.

    CJK languages use a HybridFont profile. Other languages with a profile
    (e.g. 'ru') use a plain bundled font. All others reset to defaults.
    """
    normalized_lang = _normalize_lang_code(lang_code)
    latin_font_path = _resolve_font_path(_LATIN_DEFAULT_FONT_PATH)

    if normalized_lang in _LATIN_SCRIPT_LANGS and latin_font_path:
        UIFonts.set_font_profile(
            font_path=None,
            default_font_path=latin_font_path,
            size_scale=1.0,
            force_no_bold=False,
        )
        retro_style.set_font_profile(
            font_path=None,
            default_font_path=latin_font_path,
            size_scale=1.0,
            force_no_bold=False,
        )
    else:
        profile = _PROFILE_BY_LANG.get(normalized_lang)
        if profile:
            font_path = _resolve_font_path(profile.get("font_path"))
            size_scale = profile.get("size_scale", 1.0)
            force_no_bold = profile.get("force_no_bold", False)
            UIFonts.set_font_profile(
                font_path=font_path,
                default_font_path=None,
                size_scale=size_scale,
                force_no_bold=force_no_bold,
            )
            retro_style.set_font_profile(
                font_path=font_path,
                default_font_path=None,
                size_scale=size_scale,
                force_no_bold=force_no_bold,
            )
        else:
            UIFonts.set_font_profile(font_path=None, default_font_path=None, size_scale=1.0, force_no_bold=False)
            retro_style.set_font_profile(font_path=None, default_font_path=None, size_scale=1.0, force_no_bold=False)

    try:
        _ui_font_cache.clear()
    except Exception:
        pass

    # Font profili değiştiğinde eski render cache'lerini temizle
    try:
        from text_cache import clear_text_cache
        clear_text_cache()
    except Exception:
        pass
