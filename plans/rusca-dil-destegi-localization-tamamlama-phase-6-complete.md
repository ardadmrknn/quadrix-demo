## Phase 6 Complete: Regresyon Testleri ve Test İzolasyon Düzeltmesi

Full test suite koşturuldu. Localization test dosyalarında `sys.modules` stub kontaminasyonundan kaynaklanan collection hataları tespit edildi ve üç test dosyasına stub-temizleme guard'ı eklenerek düzeltildi. 120 test geçti; kalan 18 hata Rusça desteğiyle ilgisiz, önceden var olan sorunlardır.

**Files created/changed:**
- `test_localization_ru_registered.py` — sys.modules guard eklendi
- `test_localization_no_missing_keys_any_language.py` — sys.modules guard eklendi
- `test_localization_ru_placeholders_match_en.py` — sys.modules guard eklendi

**Functions created/changed:**
- Modül düzeyinde stub-temizleme guard (her üç dosyada): `if 'localization' in sys.modules and not hasattr(..., 'TRANSLATIONS'): del sys.modules['localization']`

**Tests created/changed:**
- `test_localization_ru_registered.py` — 8 test, hepsi geçiyor
- `test_localization_no_missing_keys_any_language.py` — 2 test, hepsi geçiyor
- `test_localization_ru_placeholders_match_en.py` — 1 test, geçiyor

**Review Status:** APPROVED — 120 passed, 1 skipped; 18 pre-existing failures (SoundManager, pygame.NOFRAME, TabbedSettingsScreen attrs) bizimle ilgisiz

**Git Commit Message:**
```
test: fix localization test isolation in full pytest suite

- Add sys.modules stub-clearing guard to 3 localization test files
- Guard removes thin stubs left by earlier tests before importing
- All 23 Russian language tests now pass in full suite context
- 120 tests pass overall; 18 pre-existing failures unrelated to ru support
```
