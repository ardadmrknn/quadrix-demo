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
    mock_steam.sync_stats_to_steam = MagicMock(return_value=2)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {"first_game": "2026-01-01 00:00", "first_line": "2026-01-01 00:01"}
    mgr.new_achievements = []
    mgr.stats = {}

    result = mgr.sync_to_steam()

    assert result == 5  # 3 achievement + 2 stat
    mock_steam.sync_all_achievements.assert_called_once_with(
        mgr.unlocked, achievements.STEAM_ACHIEVEMENT_MAP
    )
    mock_steam.sync_stats_to_steam.assert_called_once_with(mgr.stats)

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


# ── Yeni Steam API fonksiyonları ─────────────────────────────────────────

def test_clear_steam_achievement_when_not_available():
    """Steam müsait değilken clear_steam_achievement False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.clear_steam_achievement("ACH_FIRST_GAME")
    assert result is False


def test_indicate_achievement_progress_when_not_available():
    """Steam müsait değilken indicate_achievement_progress False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.indicate_achievement_progress("ACH_LINES_100", 50, 100)
    assert result is False


def test_set_steam_stat_int_when_not_available():
    """Steam müsait değilken set_steam_stat_int False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.set_steam_stat_int("STAT_TOTAL_GAMES", 42)
    assert result is False


def test_set_steam_stat_float_when_not_available():
    """Steam müsait değilken set_steam_stat_float False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.set_steam_stat_float("STAT_SPRINT_BEST_TIME", 55.3)
    assert result is False


def test_get_steam_stat_int_when_not_available():
    """Steam müsait değilken get_steam_stat_int None dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.get_steam_stat_int("STAT_TOTAL_GAMES")
    assert result is None


def test_get_steam_stat_float_when_not_available():
    """Steam müsait değilken get_steam_stat_float None dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.get_steam_stat_float("STAT_SPRINT_BEST_TIME")
    assert result is None


def test_store_steam_stats_when_not_available():
    """Steam müsait değilken store_steam_stats False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.store_steam_stats()
    assert result is False


def test_sync_stats_to_steam_when_not_available():
    """Steam müsait değilken sync_stats_to_steam 0 dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.sync_stats_to_steam({"total_games": 10})
    assert result == 0


def test_reset_all_steam_stats_when_not_available():
    """Steam müsait değilken reset_all_steam_stats False dönmeli."""
    import steam_integration
    importlib.reload(steam_integration)

    result = steam_integration.reset_all_steam_stats(achievements_too=True)
    assert result is False


def test_steam_stat_map_exists():
    """STEAM_STAT_MAP dict'i tanımlı ve boş değil."""
    import steam_integration
    importlib.reload(steam_integration)

    assert hasattr(steam_integration, "STEAM_STAT_MAP")
    assert len(steam_integration.STEAM_STAT_MAP) > 0


def test_steam_stat_map_values_are_tuples():
    """STEAM_STAT_MAP değerleri (api_name, type) tuple olmalı."""
    import steam_integration
    importlib.reload(steam_integration)

    for game_key, val in steam_integration.STEAM_STAT_MAP.items():
        assert isinstance(val, tuple), f"{game_key} tuple değil: {val}"
        assert len(val) == 2, f"{game_key} uzunluk 2 değil: {val}"
        api_name, stat_type = val
        assert api_name.startswith("STAT_"), f"{game_key} → {api_name} STAT_ ile başlamıyor"
        assert stat_type in ("int", "float"), f"{game_key} → {stat_type} geçersiz tür"


def test_sync_stats_calls_steam_functions():
    """sync_stats_to_steam() istatistikleri doğru fonksiyonlarla yazmalı."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    mock_steam.sync_stats_to_steam = MagicMock(return_value=5)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {}
    mgr.new_achievements = []
    mgr.stats = {"total_games": 10, "max_score": 5000}

    result = mgr.sync_stats_to_steam()

    assert result == 5
    mock_steam.sync_stats_to_steam.assert_called_once_with(mgr.stats)

    sys.modules.pop("steam_integration", None)


def test_indicate_steam_progress_called_on_milestone():
    """Kademeli başarımlarda ilerleme bildirimi gönderilmeli."""
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    mock_steam.indicate_achievement_progress = MagicMock(return_value=True)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {}
    mgr.new_achievements = []
    mgr.stats = {"total_games": 25}  # games_50 → %50 milestone

    # indicate_steam_progress'i çağır
    mgr.indicate_steam_progress("games_50")

    # %50'de bildirim gönderilmeli
    mock_steam.indicate_achievement_progress.assert_called_once_with(
        "ACH_GAMES_50", 25, 50
    )

    sys.modules.pop("steam_integration", None)