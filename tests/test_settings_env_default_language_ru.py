"""settings_manager.py — TETRIS_DEFAULT_LANGUAGE ortam değişkeni ile RU varsayılan dil testi."""
import os
import sys
import types
import importlib
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

@pytest.fixture(autouse=True)
def setup_stubs(monkeypatch):
    # Gerekli bağımlılıkları güvenli bir şekilde monkeypatch ile stub'la
    for mod in ["pygame", "pygame.mixer", "pygame.font", "pygame.image",
                "localization", "constants", "sound", "retro_style", "ui_theme",
                "ui_language_profile", "background", "background_effects",
                "platform_utils", "user_manager", "achievements", "steam_integration"]:
        if mod not in sys.modules:
            stub = types.ModuleType(mod)
            monkeypatch.setitem(sys.modules, mod, stub)
            
    if "localization" in sys.modules:
        loc = sys.modules["localization"]
        monkeypatch.setattr(loc, "SUPPORTED_LANGUAGES", ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko'], raising=False)
        monkeypatch.setattr(loc, "DEFAULT_LANGUAGE", 'tr', raising=False)
        monkeypatch.setattr(loc, "set_language", lambda l: None, raising=False)
        monkeypatch.setattr(loc, "t", lambda k, *a, **kw: k, raising=False)
        
    if "constants" in sys.modules:
        sys.modules["constants"].DEBUG_MODE = False
        
    if "pygame" in sys.modules:
        # FAZ A3 (K4): pg burada GERÇEK pygame olabilir (süitte önceki canlı
        # dosyalar aileyi sys.modules'te bırakınca). Düz atamalar (pg.display =
        # ...) gerçek modülün attribute'larını ezer ve teardown geri koymaz —
        # sonraki canlı testlerde 'SimpleNamespace' object has no attribute
        # 'get_init'/'set_mode' hatası üretir. monkeypatch.setattr hem stub
        # hem gerçek modülde çalışır ve teardown'da orijinali geri koyar;
        # raising=False stub'ta bulunmayan attribute'lar için gereklidir.
        # (DUZ-011: v2'nin K4 düzeltmesi demo'ya port edildi — kalıcı ezme,
        # test_ui_theme_font_fallback 4 testini ve win32 font registry
        # testlerini tam pakette düşürüyordu.)
        pg = sys.modules["pygame"]
        monkeypatch.setattr(pg, "mixer", types.SimpleNamespace(
            init=lambda *a, **k: None,
            music=types.SimpleNamespace(
                load=lambda *a, **k: None,
                play=lambda *a, **k: None,
                set_volume=lambda *a, **k: None
            )
        ), raising=False)
        monkeypatch.setattr(pg, "font", types.SimpleNamespace(
            init=lambda: None,
            Font=lambda *a, **k: None,
            SysFont=lambda *a, **k: None
        ), raising=False)
        monkeypatch.setattr(pg, "init", lambda: (0, 0), raising=False)
        monkeypatch.setattr(pg, "display", types.SimpleNamespace(set_caption=lambda *a: None), raising=False)

def _get_settings_manager():
    if "settings_manager" in sys.modules:
        del sys.modules["settings_manager"]
    return importlib.import_module("settings_manager")

def test_env_language_ru():
    """TETRIS_DEFAULT_LANGUAGE=ru ile settings manager ru'ya ayarlanmalı."""
    settings_manager = _get_settings_manager()
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "ru"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "ru"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]

def test_env_language_de():
    """TETRIS_DEFAULT_LANGUAGE=de çalışmalı."""
    settings_manager = _get_settings_manager()
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "de"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "de"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]

def test_env_language_invalid_unchanged():
    """Geçersiz dil kodu ayarı değiştirmemeli."""
    settings_manager = _get_settings_manager()
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "xx"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "tr"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]

def test_env_language_tr_still_works():
    """TR hâlâ çalışmalı."""
    settings_manager = _get_settings_manager()
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "tr"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'en'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "tr"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]

def test_env_language_en_still_works():
    """EN hâlâ çalışmalı."""
    settings_manager = _get_settings_manager()
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "en"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "en"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]
