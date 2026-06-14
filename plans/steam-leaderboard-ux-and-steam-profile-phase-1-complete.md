## Phase 1 Complete: Steam Profil Oluşturma/Seçme Akışı Düzeltildi

`UserManager.create_user()` artık `steam_id` parametresini kabul ediyor; Steam'den başlatılınca yerel profil otomatik olarak oluşturulup seçiliyor. Persona adı çakışması durumunda SteamID son 4 hanesiyle unique username üretiliyor.

**Files created/changed:**
- `src/user_manager.py`
- `src/main.py`
- `test_user_manager_steam_profile.py` (new)

**Functions created/changed:**
- `UserManager.create_user()` — `steam_id: str | None = None` parametresi eklendi; profile içine normalize edilip yazılıyor
- Steam init block in `main.py` (lines ~877-907) — persona çakışması ve unique username üretimi eklendi

**Tests created/changed:**
- `TestCreateUserWithSteamId` (4 test) — steam_id with create_user
- `TestGetUserBySteamId` (5 test) — lookup by SteamID
- `TestSetSteamId` (3 test) — bind steam_id to existing profile
- `TestSteamAutoProfileScenario` (3 test) — full first-run + reload + persona collision flow

**Review Status:** APPROVED

**Git Commit Message:**
```
feat: add steam_id param to UserManager.create_user() and fix auto-profile

- UserManager.create_user() now accepts steam_id kwarg and stores it in profile
- Normalize steam_id: empty/whitespace strings stored as None
- main.py Steam init block: handle persona collision with steamid-suffix unique name
- Existing profile with same persona but different steam_id no longer overwritten
```
