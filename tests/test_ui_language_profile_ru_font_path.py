"""ui_language_profile.py — Rusça font profili birim testi.

KyrillaSansSerif-Black.ttf Kiril glyphlerini desteklemediğinden (boş piksel
üretiyor), 'ru' artık _PROFILE_BY_LANG'de YER ALMIYOR.  Rusça için sistem
fontları (Segoe UI, Arial) kullanılır; bu testler bu davranışı doğrular.
"""
import os
import sys
import types

# Env izolasyonu
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# pygame stub - gerçek pygame yüklemeden test et
pygame_stub = types.ModuleType("pygame")
pygame_stub.font = types.ModuleType("pygame.font")
pygame_stub.font.get_init = lambda: True
pygame_stub.font.init = lambda: None
pygame_stub.font.Font = lambda path, size: types.SimpleNamespace(
    render=lambda *a, **k: None,
    get_height=lambda: size,
    get_linesize=lambda: size,
)
pygame_stub.font.SysFont = lambda *a, **k: pygame_stub.font.Font(None, 24)
sys.modules.setdefault("pygame", pygame_stub)
sys.modules.setdefault("pygame.font", pygame_stub.font)

# Diğer bağımlılık stub'ları
for mod_name in ["retro_style", "ui_theme", "localization", "background", "constants"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

rs_stub = sys.modules["retro_style"]
rs_stub.retro_style = types.SimpleNamespace(
    set_font_profile=lambda **k: None,
    _get_latin_font=lambda size, bold: pygame_stub.font.Font(None, size),
)
rs_stub.HybridFont = type("HybridFont", (), {"__init__": lambda self, l, c: None})

uit_stub = sys.modules["ui_theme"]
uit_stub.UIFonts = type("UIFonts", (), {"set_font_profile": staticmethod(lambda **k: None)})

if sys.modules.get("ui_language_profile"):
    del sys.modules["ui_language_profile"]

import ui_language_profile


def test_ru_not_in_profile():
    """RU profili _PROFILE_BY_LANG'de OLMAMALI (font Kiril desteklemiyor)."""
    assert "ru" not in ui_language_profile._PROFILE_BY_LANG, (
        "KyrillaSansSerif-Black.ttf Kiril desteklemiyor; 'ru' profilde olmamalı"
    )


def test_cjk_profiles_still_exist():
    """CJK dil profilleri hala mevcut olmalı."""
    for lang in ("ja", "zh", "ko"):
        assert lang in ui_language_profile._PROFILE_BY_LANG, (
            f"CJK profili '{lang}' eksik"
        )


def test_get_font_for_language_ru_returns_none():
    """Profili olmayan RU için get_font_for_language None dönmeli."""
    result = ui_language_profile.get_font_for_language("ru", 20)
    assert result is None, "RU profili yok; None döndürülmeli"


def test_get_font_for_language_unknown_returns_none():
    """Profili olmayan herhangi bir dil için None dönmeli."""
    result = ui_language_profile.get_font_for_language("xx", 18)
    assert result is None, "Profili olmayan dil için None döndürülmeli"


def test_apply_language_ui_profile_ru_resets_defaults():
    """RU profili yok → varsayılanlara sıfırlamalı."""
    calls = []
    ui_language_profile.UIFonts.set_font_profile = staticmethod(lambda **k: calls.append(k))
    ui_language_profile.retro_style.set_font_profile = lambda **k: calls.append(k)

    ui_language_profile.apply_language_ui_profile("ru")

    assert len(calls) >= 1, "set_font_profile çağrılmalı"
    for call in calls:
        assert call.get("font_path") is None, (
            f"RU için font_path None olmalı (varsayılan): {call}"
        )


def test_kyril_font_file_exists_on_disk():
    """font/kyril/KyrillaSansSerif-Black.ttf repo'da hala mevcut (referans)."""
    kyril_path = os.path.join(
        os.path.dirname(__file__), "..", "font", "kyril", "KyrillaSansSerif-Black.ttf"
    )
    assert os.path.exists(kyril_path), (
        f"Kiril font dosyası repoda mevcut olmalı: {kyril_path}"
    )


def test_profile_count_is_three():
    """Sadece CJK dilleri (ja, zh, ko) profilde olmalı."""
    assert len(ui_language_profile._PROFILE_BY_LANG) == 3, (
        f"Profilde 3 dil bekleniyor, bulundu: {len(ui_language_profile._PROFILE_BY_LANG)}"
    )
