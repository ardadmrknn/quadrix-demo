## Phase 4 Complete: Hardcoded Steam API Anahtarları Kaldırıldı

`menu.py` ve `steam_integration.py` içindeki gömülü Steam Web API anahtarları kaldırıldı; `os.getenv()` çağrılarıyla ortam değişkeninden okunacak şekilde düzeltildi.

**Files created/changed:**
- `src/menu.py`
- `src/steam_integration.py`

**Functions created/changed:**
- `Menu.__init__()` / `SteamLeaderboardService` init bloğu — publisher_key ve app_id artık `os.getenv('STEAM_WEB_API_KEY', '')` ve `os.getenv('STEAM_APP_ID', '0')` ile alınıyor
- `_PARTNER_API_KEY` in `src/steam_integration.py` — hardcoded string yerine `os.environ.get('STEAM_WEB_API_KEY', '').strip()`

**Tests created/changed:**
- Mevcut testler geçmeye devam ediyor; key kaldırımı security fix niteliğinde

**Review Status:** APPROVED

**Git Commit Message:**
```
security: remove hardcoded Steam Web API key from source files

- steam_integration.py: _PARTNER_API_KEY now reads from STEAM_WEB_API_KEY env var
- menu.py: SteamLeaderboardService init uses os.getenv for publisher_key and app_id
- No functional change; key must be provided via environment variable at runtime
```
