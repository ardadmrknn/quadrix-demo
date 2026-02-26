## Phase 2 Complete: Direct Player Summaries Desteği Eklendi

`SteamLeaderboardService.fetch_player_summaries()` artık backend mevcut olmadığında Steam Web API'ye doğrudan istek yapabiliyor. Yeni `_fetch_player_summaries_direct()` metodu `ISteamUser/GetPlayerSummaries/v2/` endpoint'ini kullanıyor.

**Files created/changed:**
- `src/steam_leaderboards.py`
- `test_steam_leaderboards_player_summaries_direct.py` (new)

**Functions created/changed:**
- `SteamLeaderboardService.fetch_player_summaries()` — backend boş/erişilemez durumunda `_fetch_player_summaries_direct()` fallback'i eklendi
- `SteamLeaderboardService._fetch_player_summaries_direct()` — yeni metod; Steam Web API'ye app_id olmadan chunk halinde istek yapar; `{steamid: {personaname, avatar, ...}}` döner

**Tests created/changed:**
- `test_direct_mode_returns_summaries` — doğru dict döndüğü test edildi
- `test_direct_mode_calls_correct_endpoint` — URL `GetPlayerSummaries/v2/` içeriyor mu
- `test_direct_mode_includes_required_params` — key ve steamids param'ları mevcut
- `test_direct_mode_normalizes_output` — steamid anahtar olarak kullanılıyor
- `test_direct_mode_handles_multiple_ids` — 150+ steamid chunk'lara bölünüyor
- `test_direct_mode_empty_ids` — boş input → boş dict döner
- `test_direct_mode_network_error` — request exception → boş dict döner
- `test_backend_mode_still_uses_backend` — backend varken direct fallback tetiklenmez

**Review Status:** APPROVED

**Git Commit Message:**
```
feat: add direct Steam Web API fallback for player summaries

- SteamLeaderboardService.fetch_player_summaries() falls through to direct mode
  when backend returns empty result or is unavailable
- New _fetch_player_summaries_direct() calls ISteamUser/GetPlayerSummaries/v2/
  without appid param (not required for this endpoint)
- Chunk steamids to stay within URL length limits
```
