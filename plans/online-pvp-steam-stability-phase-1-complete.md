## Phase 1 Complete: Bridge Import ve Windows DLL Search Path Stabilizasyonu

`steam_networking` modülü artık import zamanında bridge yüklemeye çalışmıyor; yükleme yalnızca `SteamNetworking.init()` çağrısında gerçekleşiyor. Windows'ta `os.add_dll_directory()` handle'ları module-global `_dll_dirs` listesinde tutularak GC'ye karşı korumalı hale getirildi. Ayrıca `tests/conftest.py`'deki tüm testleri skip eden hook temizlendi.

**Files created/changed:**
- src/steam_networking.py
- tests/test_steam_networking_bridge_import_lazy.py (yeni)
- tests/test_steam_networking_win_dll_dir_handles_persist.py (yeni)
- tests/conftest.py

**Functions created/changed:**
- `SteamNetworking.init()` — `global _bridge_available, _bridge_import_attempted` bildirimi eklendi; lazy import tetiklemesi
- `_try_import_bridge()` — module-global `_dll_dirs` listesine header'lar ekleniyor; denenen yollar loglara basılıyor; macOS deterministik `sys.path` eklentileri
- `_dll_dirs` — yeni module-global list (GC koruması)
- `_bridge_import_attempted` — yeni module-level flag (lazy import kontrolü)

**Tests created/changed:**
- `test_import_does_not_trigger_bridge_import` — modül import'u bridge'i tetiklemiyor
- `test_init_triggers_bridge_import` — `init()` çağrısı bridge import'u tetikliyor
- `test_import_module_does_not_call_bridge` — `builtins.__import__` ile doğrulama
- `test_dll_dir_handles_stored_in_global_list` — handle'lar global listede
- `test_dll_dir_handles_not_just_in_local_scope` — local scope'ta kaybolmuyor
- `test_dll_dir_multiple_paths_all_stored` — birden fazla path hepsi saklanıyor

**Review Status:** APPROVED

**Git Commit Message:**
```
fix: lazy bridge import and persist DLL dir handles in steam_networking

- Move os.add_dll_directory() handles to module-global _dll_dirs list
- Bridge import now only attempted on SteamNetworking.init() call
- Add _bridge_import_attempted flag to prevent redundant import attempts
- Use deterministic sys.path injection for macOS PyInstaller bundles
- Log all tried paths on bridge import failure for easier debugging
- Add global declaration for _bridge_import_attempted in init()
- Fix fragile __builtins__ access in test; use builtins module directly
- Remove conftest.py hook that was skipping all tests
```
