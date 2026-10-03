"""Steam Achievement senkronizasyonu testleri.

Gerçek Steam SDK olmadan çalışır — steam_integration mock'lanır.
"""
import ast
import ctypes
import importlib
import json
import sys
import threading
import types
from pathlib import Path
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


def test_removed_achievements_are_no_longer_defined():
    """Kaldırılan başarım ID'leri runtime tanımlarında yer almamalı."""
    import achievements
    importlib.reload(achievements)

    assert "perfect_clear" not in achievements.ACHIEVEMENTS
    assert "no_mistakes" not in achievements.ACHIEVEMENTS
    assert "perfect_clear" not in achievements.STEAM_ACHIEVEMENT_MAP
    assert "no_mistakes" not in achievements.STEAM_ACHIEVEMENT_MAP


def test_sprint_targets_use_new_thresholds():
    """Sprint başarımları yeni 240/200 saniye eşiklerini kullanmalı."""
    import achievements
    importlib.reload(achievements)

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)

    assert mgr._progress_spec_for("sprint_sub60") == ("sprint_best_time", 240, False)
    assert mgr._progress_spec_for("sprint_sub45") == ("sprint_best_time", 200, False)


def test_ultra_targets_use_new_thresholds():
    """Ultra başarımları yeni 10k/15k skor eşiklerini kullanmalı."""
    import achievements
    importlib.reload(achievements)

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)

    assert mgr._progress_spec_for("ultra_50k") == ("ultra_max_score", 10000, False)
    assert mgr._progress_spec_for("ultra_100k") == ("ultra_max_score", 15000, False)


def test_achievement_names_are_unique():
    """Varsayılan başarım adları çakışmamalı."""
    import achievements
    importlib.reload(achievements)

    names = [data["name"] for data in achievements.ACHIEVEMENTS.values()]
    assert len(names) == len(set(names))


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


def test_sync_to_steam_can_retry_achievements_without_resending_stats():
    import achievements
    importlib.reload(achievements)

    mock_steam = MagicMock()
    mock_steam.sync_all_achievements = MagicMock(return_value=1)
    mock_steam.sync_stats_to_steam = MagicMock(return_value=9)
    sys.modules["steam_integration"] = mock_steam

    mgr = achievements.AchievementManager.__new__(achievements.AchievementManager)
    mgr.unlocked = {"survival_10min": "2026-10-03 12:00"}
    mgr.stats = {"survival_max_time": 600}

    assert mgr.sync_to_steam(include_stats=False) == 1
    mock_steam.sync_all_achievements.assert_called_once_with(
        mgr.unlocked, achievements.STEAM_ACHIEVEMENT_MAP
    )
    mock_steam.sync_stats_to_steam.assert_not_called()

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


def _configure_available_steam(monkeypatch):
    import steam_integration
    importlib.reload(steam_integration)
    dll = MagicMock()
    dll.SteamAPI_ISteamUserStats_SetAchievement.return_value = True
    dll.SteamAPI_ISteamUserStats_StoreStats.return_value = True
    monkeypatch.setattr(steam_integration, '_dll', dll)
    monkeypatch.setattr(steam_integration, '_init_ok', True)
    monkeypatch.setattr(steam_integration, '_isteam_user_stats', object())
    monkeypatch.setattr(steam_integration, '_shutdown_requested', False)
    monkeypatch.setattr(steam_integration, '_exit_requested', False)
    monkeypatch.setattr(steam_integration, '_pump_lock', threading.Lock())
    return steam_integration, dll


def test_unlock_requires_store_stats_success(monkeypatch):
    steam, dll = _configure_available_steam(monkeypatch)
    dll.SteamAPI_ISteamUserStats_StoreStats.return_value = False

    assert steam.unlock_steam_achievement('ACH_SURVIVAL_10MIN') is False
    dll.SteamAPI_ISteamUserStats_SetAchievement.assert_called_once()
    dll.SteamAPI_ISteamUserStats_StoreStats.assert_called_once()


def test_bulk_sync_retries_after_store_stats_failure(monkeypatch):
    steam, dll = _configure_available_steam(monkeypatch)
    dll.SteamAPI_ISteamUserStats_StoreStats.side_effect = [False, True]
    dll.SteamAPI_ISteamUserStats_GetAchievement.return_value = False

    unlocked = {'survival_10min': '2026-10-03 12:00'}
    mapping = {'survival_10min': 'ACH_SURVIVAL_10MIN'}

    assert steam.sync_all_achievements(unlocked, mapping) == 0
    assert steam.sync_all_achievements(unlocked, mapping) == 1
    assert dll.SteamAPI_ISteamUserStats_SetAchievement.call_count == 2
    assert dll.SteamAPI_ISteamUserStats_StoreStats.call_count == 2


@pytest.mark.parametrize('store_result', [False, RuntimeError('store failed')])
def test_cached_unlock_does_not_hide_failed_steam_store(monkeypatch, store_result):
    steam, dll = _configure_available_steam(monkeypatch)
    dll.SteamAPI_ISteamUserStats_StoreStats.side_effect = [store_result, True]

    def get_achievement(handle, name, output):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_bool)).contents.value = True
        return True

    dll.SteamAPI_ISteamUserStats_GetAchievement.side_effect = get_achievement
    assert steam.unlock_steam_achievement('ACH_SURVIVAL_10MIN') is False
    assert steam.is_steam_achievement_unlocked('ACH_SURVIVAL_10MIN') is True
    assert steam.sync_all_achievements(
        {'survival_10min': '2026-10-03 12:00'}, {'survival_10min': 'ACH_SURVIVAL_10MIN'}
    ) == 0
    assert dll.SteamAPI_ISteamUserStats_StoreStats.call_count == 2


@pytest.mark.parametrize('platform_name', ['win32', 'darwin'])
@pytest.mark.parametrize('set_result,store_result,expected', [
    (True, True, True), (True, False, False), (False, True, False),
])
def test_achievement_set_and_store_share_callback_lock(
    monkeypatch, platform_name, set_result, store_result, expected,
):
    steam, dll = _configure_available_steam(monkeypatch)
    monkeypatch.setattr(steam, 'sys', types.SimpleNamespace(platform=platform_name))

    def set_achievement(*args):
        assert steam._pump_lock.locked()
        return set_result

    def store_stats(*args):
        assert steam._pump_lock.locked()
        return store_result

    dll.SteamAPI_ISteamUserStats_SetAchievement.side_effect = set_achievement
    dll.SteamAPI_ISteamUserStats_StoreStats.side_effect = store_stats
    assert steam.unlock_steam_achievement('ACH_SURVIVAL_10MIN') is expected
    assert dll.SteamAPI_ISteamUserStats_StoreStats.call_count == int(set_result)
    assert steam.sync_all_achievements(
        {'survival_10min': '2026-10-03 12:00'}, {'survival_10min': 'ACH_SURVIVAL_10MIN'}
    ) == int(expected)
    assert not steam._pump_lock.locked()


def test_shutdown_while_waiting_for_lock_prevents_native_achievement_calls(monkeypatch):
    steam, dll = _configure_available_steam(monkeypatch)

    class ShutdownLock:
        def __enter__(self):
            steam._shutdown_requested = True

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(steam, '_pump_lock', ShutdownLock())
    assert steam.unlock_steam_achievement('ACH_SURVIVAL_10MIN') is False
    dll.SteamAPI_ISteamUserStats_SetAchievement.assert_not_called()
    dll.SteamAPI_ISteamUserStats_StoreStats.assert_not_called()


def test_macos_early_exit_prevents_new_achievement_work(monkeypatch):
    steam, dll = _configure_available_steam(monkeypatch)
    monkeypatch.setattr(steam, 'sys', types.SimpleNamespace(platform='darwin'))
    steam.request_shutdown()
    assert steam.is_available()
    assert steam.unlock_steam_achievement('ACH_SURVIVAL_10MIN') is False
    assert steam.sync_all_achievements(
        {'survival_10min': '2026-10-03 12:00'}, {'survival_10min': 'ACH_SURVIVAL_10MIN'}
    ) == 0
    dll.SteamAPI_ISteamUserStats_SetAchievement.assert_not_called()


def test_stat_sync_does_not_report_success_when_store_fails(monkeypatch):
    steam, dll = _configure_available_steam(monkeypatch)
    dll.SteamAPI_ISteamUserStats_StoreStats.return_value = False
    assert steam.sync_stats_to_steam({'total_games': 1, 'survival_max_time': 600}) == 0


@pytest.mark.parametrize('platform_name', ['win32', 'darwin'])
def test_second_survival_run_retries_local_unlock_without_duplicate_reward(
    monkeypatch, tmp_path, platform_name,
):
    steam, dll = _configure_available_steam(monkeypatch)
    monkeypatch.setattr(steam, 'sys', types.SimpleNamespace(platform=platform_name))
    import achievements
    importlib.reload(achievements)
    # Tek-dosya koşumunda autouse _stub_modules, atomic_io'yu (henüz
    # yüklenmemişse) MagicMock'lu stub'la kurar ve save() dosya yazmaz;
    # reload'dan SONRA gerçek yazan sarmalayıcı bağla (reload önceki yamayı ezer).
    monkeypatch.setattr(
        achievements, 'atomic_write_json',
        lambda path, data, **kwargs: Path(path).write_text(
            json.dumps(data, indent=kwargs.get('indent', 2),
                       ensure_ascii=kwargs.get('ensure_ascii', False)),
            encoding='utf-8',
        ),
    )
    manager = achievements.AchievementManager(str(tmp_path / 'survival_achievements.json'))
    manager.unlocked = {
        achievement_id: '2026-10-03 11:00'
        for achievement_id in achievements.ACHIEVEMENTS if achievement_id != 'survival_10min'
    }
    manager.user_manager = MagicMock()
    manager.claimed_rewards = set(manager.unlocked)
    monkeypatch.setattr(threading, 'Thread', MagicMock())
    game_path = Path(__file__).resolve().parents[1] / 'src' / 'game.py'
    game_class = next(
        node for node in ast.parse(game_path.read_text(encoding='utf-8')).body
        if isinstance(node, ast.ClassDef) and node.name == 'Game'
    )
    finalize_method = next(
        node for node in game_class.body
        if isinstance(node, ast.FunctionDef) and node.name == 'finalize_run'
    )
    namespace = {'pygame': types.SimpleNamespace(time=types.SimpleNamespace(get_ticks=lambda: 0))}
    module = ast.fix_missing_locations(ast.Module(body=[finalize_method], type_ignores=[]))
    exec(compile(module, str(game_path), 'exec'), namespace)

    def make_game():
        return types.SimpleNamespace(
            _score_recorded=False, game_time=600000, game_mode='survival',
            score_manager=None, user_manager=None, achievement_manager=manager,
            achievement_notifications=[],
            board=types.SimpleNamespace(score=0, lines_cleared=0, level=1, tetrises=0, combo=0),
        )

    first_game = make_game()
    dll.SteamAPI_ISteamUserStats_StoreStats.return_value = False
    namespace['finalize_run'](first_game, playtime=600)
    assert 'survival_10min' in manager.unlocked
    assert manager.stats['survival_max_time'] == 600
    assert len(first_game.achievement_notifications) == 1
    saved = json.loads(Path(manager.filename).read_text(encoding='utf-8'))
    assert 'survival_10min' in saved['unlocked']
    assert manager.claim_reward('survival_10min') == achievements.ACHIEVEMENT_REWARDS['survival_10min']
    unlock_date = manager.unlocked['survival_10min']
    dll.SteamAPI_ISteamUserStats_SetAchievement.reset_mock()

    second_game = make_game()
    dll.SteamAPI_ISteamUserStats_StoreStats.return_value = True
    namespace['finalize_run'](second_game, playtime=600)
    assert any(
        native_call.args[1] == b'ACH_SURVIVAL_10MIN'
        for native_call in dll.SteamAPI_ISteamUserStats_SetAchievement.call_args_list
    )
    assert second_game.achievement_notifications == []
    assert manager.unlocked['survival_10min'] == unlock_date
    assert manager.claim_reward('survival_10min') == 0
    manager.user_manager.add_fragments.assert_called_once()
    assert manager.stats['total_games'] == 2
    call_count = dll.SteamAPI_ISteamUserStats_SetAchievement.call_count
    namespace['finalize_run'](second_game, playtime=600)
    assert dll.SteamAPI_ISteamUserStats_SetAchievement.call_count == call_count


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
