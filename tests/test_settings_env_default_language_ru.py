"""settings_manager.py — TETRIS_DEFAULT_LANGUAGE ortam değişkeni ile RU varsayılan dil testi."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# Bağımlılıkları stub'la
for mod in ["pygame", "pygame.mixer", "pygame.font", "pygame.image",
            "localization", "constants", "sound", "retro_style", "ui_theme",
            "ui_language_profile", "background", "background_effects",
            "platform_utils", "user_manager", "achievements", "steam_integration"]:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

loc_stub = sys.modules["localization"]
loc_stub.SUPPORTED_LANGUAGES = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']
loc_stub.DEFAULT_LANGUAGE = 'tr'
loc_stub.set_language = lambda l: None
loc_stub.t = lambda k, *a, **kw: k

const_stub = sys.modules["constants"]
const_stub.DEBUG_MODE = False

pygame_stub = sys.modules["pygame"]
pygame_stub.mixer = types.SimpleNamespace(init=lambda *a, **k: None, music=types.SimpleNamespace(
    load=lambda *a, **k: None, play=lambda *a, **k: None, set_volume=lambda *a, **k: None))
pygame_stub.font = types.SimpleNamespace(init=lambda: None, Font=lambda *a, **k: None, SysFont=lambda *a, **k: None)
pygame_stub.init = lambda: (0, 0)
pygame_stub.display = types.SimpleNamespace(set_caption=lambda *a: None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import importlib
if "settings_manager" in sys.modules:
    del sys.modules["settings_manager"]
import settings_manager


def test_env_language_ru():
    """TETRIS_DEFAULT_LANGUAGE=ru ile settings manager ru'ya ayarlanmalı."""
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "ru"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "ru", (
            f"language 'ru' olmalıydı, '{sm.default_settings['language']}' bulundu"
        )
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]


def test_env_language_de():
    """TETRIS_DEFAULT_LANGUAGE=de çalışmalı."""
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
    os.environ["TETRIS_DEFAULT_LANGUAGE"] = "en"
    try:
        sm = settings_manager.SettingsManager.__new__(settings_manager.SettingsManager)
        sm.default_settings = {'language': 'tr'}
        sm._apply_env_default_language()
        assert sm.default_settings["language"] == "en"
    finally:
        del os.environ["TETRIS_DEFAULT_LANGUAGE"]
