## Phase 1 Complete: result=8 Web API Parameter Fix

`scoremethod` parametresi Steam Web API'nin beklediği şekilde integer'dan string'e (`'KeepBest'`) dönüştürüldü. Yeni bir regresyon testi eklendi ve tüm 21 mevcut test başarıyla geçiyor.

**Files created/changed:**
- src/steam_integration.py
- test_lb_write.py
- test_partner_fallback_enabled.py

**Functions created/changed:**
- `src/steam_integration._submit_score_via_partner_api` — `scoremethod: 0` → `scoremethod: 'KeepBest'` (string); result=8 için açıklayıcı hint log eklendi

**Tests created/changed:**
- `test_partner_fallback_enabled.TestSubmitScoreViaPartnerApiScoremethodIsString.test_partner_api_scoremethod_is_string` — POST payload'ında `scoremethod=KeepBest` (string) doğrulanıyor; `scoremethod=0` ve `scoremethod=1` integer değerlerinin gönderilmediği assert ediliyor

**Review Status:** APPROVED

**Git Commit Message:**
```
fix: send scoremethod as string in Steam Web API calls

- Change scoremethod param from int 0 to string 'KeepBest' in
  _submit_score_via_partner_api (fixes result=8 InvalidParam)
- Fix scoremethod in test_lb_write.py standalone script
- Add test_partner_api_scoremethod_is_string regression test
- Enhance result=8 error log with actionable hint message
```
