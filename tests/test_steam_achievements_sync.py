"""Steam Achievement senkronizasyonu testleri.

Gerçek Steam SDK olmadan çalışır — steam_integration mock'lanır.
"""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ── helpers ────────────────────────────────────────────────────────────────

def _ensure_src():
    """src/ dizinini sys.path'e ekle."""
    import os
    src = os.path.join(os.path.dirname(__file__), "src")
    if src not in sys.path:
        sys.path.insert(0, src)


_ensure_src()


# ── stub / mock modüller ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _stub_modules(monkeypatch, tmp_path):
    """Test ortamında pygame ve diğer bağımlılıkları stub'la."""
    stubs = {}
    for mod_name in ("pygame", "pygame.font", "pygame.mixer", "pygame.image",
                     "pygame.transform", "pygame.draw", "pygame.display",
                     "pygame.surface", "pygame.time"):
        if mod_name not in sys.modules:
            stubs[mod_name] = types.ModuleType(mod_name)
            sys.modules[mod_name] = stubs[mod_name]

    # constants stub
    if "constants" not in sys.modules:
        const = types.ModuleType("constants")
        const.DEBUG_MODE = False
        sys.modules["constants"] = const
    else:
        sys.modules["constants"].DEBUG_MODE = False

    # atomic_io stub
    if "atomic_io" not in sys.modules:
        aio = types.ModuleType("atomic_io")
        aio.atomic_write_json = MagicMock()
        sys.modules["atomic_io"] = aio

    # data_paths stub
    if "data_paths" not in sys.modules:
        dp = types.ModuleType("data_paths")
        dp.iter_legacy_paths = lambda *a, **k: iter([])
        dp.migrate_legacy_file = lambda *a, **k: None
        dp.resolve_data_path = lambda *a, **k: str(tmp_path / "test_ach.json")
        sys.modules["data_paths"] = dp

    # localization stub
    if "localization" not in sys.modules:
        loc = types.ModuleType("localization")
        loc.t = lambda key, **kw: key
        sys.modules["localization"] = loc

    yield

    for mod_name in stubs:
        sys.modules.pop(mod_name, None)


# ── STEAM_ACHIEVEMENT_MAP ─────────────────────────────────────────────────

def test_steam_achievement_map_exists():
    """STEAM_ACHIEVEMENT_MAP dict'i tanımlı ve boş değil."""
    import achievements
    importlib.reload(achievements)
    assert hasattr(achievements, "STEAM_ACHIEVEMENT_MAP")
    assert len(achievements.STEAM_ACHIEVEMENT_MAP) > 0


def test_steam_achievement_map_values_start_with_ach():
    """Her Steam API name ACH_ ile başlamalı."""
    import achievements
    importlib.reload(achievements)
    for game_id, steam_name in achievements.STEAM_ACHIEVEMENT_MAP.items():
        assert steam_name.startswith("ACH_"), f"{game_id} -> {steam_name} ACH_ ile başlamıyor"


def test_steam_achievement_map_keys_are_valid():
    """Map'teki tüm game ID'ler ACHIEVEMENTS dict'inde tanımlı olmalı."""
    import achievements
    importlib.reload(achievements)
    for game_id in achievements.STEAM_ACHIEVEMENT_MAP:
        assert game_id in achievements.ACHIEVEMENTS, f"{game_id} ACHIEVEMENTS'ta yok"


# ── unlock() Steam entegrasyonu ──────────────────────────────────────────

def test_unlock_calls_steam_on_new_achievement():
    """Yeni başarım açıldığında steam_integration.unlock_steam_achievement çağrılmalı."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    mock_steam.unlock_steam_achievement = MagicMock(return_value=True)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {}
    mgr.new_achievements = []
    mgr.stats = {}

    result = mgr.unlock("first_game")

    assert result is True
    mock_steam.unlock_steam_achievement.assert_called_once_with("ACH_FIRST_GAME")

    sys.modules.pop("steam_integration", None)


def test_unlock_skips_steam_for_unknown_achievement():
    """STEAM_ACHIEVEMENT_MAP'te olmayan ID için Steam çağrısı yapılmamalı."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {}
    mgr.new_achievements = []
    mgr.stats = {}

    # Map'te olmayan bir key
    mgr.unlock("totally_custom_achievement_xyz")

    mock_steam.unlock_steam_achievement.assert_not_called()

    sys.modules.pop("steam_integration", None)


def test_unlock_does_not_crash_without_steam():
    """Steam modülü import edilemezse unlock yine de çalışmalı."""
    import achievements
    importlib.reload(achievements)

    # steam_integration'ı kaldır
    sys.modules.pop("steam_integration", None)

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {}
    mgr.new_achievements = []
    mgr.stats = {}

    result = mgr.unlock("first_game")
    assert result is True
    assert "first_game" in mgr.unlocked


def test_unlock_duplicate_does_not_call_steam():
    """Zaten açılmış başarım tekrar Steam'e gönderilmemeli."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {"first_game": "2026-03-01 00:00"}
    mgr.new_achievements = []
    mgr.stats = {}

    result = mgr.unlock("first_game")
    assert result is False
    mock_steam.unlock_steam_achievement.assert_not_called()

    sys.modules.pop("steam_integration", None)


# ── sync_to_steam() ─────────────────────────────────────────────────────

def test_sync_to_steam_calls_sync_all():
    """sync_to_steam() doğru parametrelerle sync_all_achievements çağırmalı."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    mock_steam.sync_all_achievements = MagicMock(return_value=3)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {"first_game": "2026-01-01 00:00", "first_line": "2026-01-01 00:01"}
    mgr.new_achievements = []
    mgr.stats = {}

    result = mgr.sync_to_steam()

    assert result == 3
    mock_steam.sync_all_achievements.assert_called_once_with(
        mgr.unlocked, achievements.STEAM_ACHIEVEMENT_MAP
    )

    sys.modules.pop("steam_integration", None)


# ── steam_integration fonksiyonları ──────────────────────────────────────

def test_unlock_steam_achievement_when_not_available():
    """Steam müsait değilken False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    # init çağrılmamış → is_available() == False
    result = steam_integration.unlock_steam_achievement("ACH_FIRST_GAME")
    assert result is False


def test_is_steam_achievement_unlocked_when_not_available():
    """Steam müsait değilken None dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.is_steam_achievement_unlocked("ACH_FIRST_GAME")
    assert result is None
