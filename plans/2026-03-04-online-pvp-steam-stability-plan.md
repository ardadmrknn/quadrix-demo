# Plan: Online PvP + Steam Entegrasyonu (Windows/macOS) Stabilite Sertleştirme

**Created:** 2026-03-04
**Status:** Ready for Atlas Execution

## Summary

Bu plan, Online PvP modunun (`OnlinePvPGame` + `SteamNetworking` + C++ `steam_net_bridge`) Windows ve macOS’ta çökme/hang/“sessiz çalışmama” risklerini azaltmak için hedefli sertleştirmeler ve regresyon testleri önerir. En yüksek riskli alanlar: Steam callback pump’ının tek-thread garantisi, Windows DLL arama yolu handle ömrü, macOS dylib/extension yükleme ve C++ tarafında kontrolsüz P2P session kabulüdür. Plan; minimal davranış değişikliğiyle (UX eklemeden) daha güvenli başlatma/temizleme, daha deterministik kütüphane yükleme, mesaj doğrulama ve build paketleme doğrulaması sağlar.

## Context & Analysis

**Relevant Files:**
- src/online_pvp_game.py: Online PvP UI + state machine + mesaj işleme + cleanup/pump resume
- src/main.py: Online PvP state handler `_handle_online_pvp` ve exception/cleanup yolları
- src/steam_networking.py: Python wrapper; bridge import (win/mac), tick/event/message akışı
- steamworks/steam_net_bridge/steam_net_bridge.cpp: Pybind11 köprüsü; SteamAPI_RunCallbacks + polling; callback’ler; session accept
- src/steam_integration.py: ctypes Steam SDK init + background callback pump + pause/resume protokolü
- *.spec (tetris_macos*.spec, tetris*.spec): PyInstaller paketleme; macOS dylib/extension dahil edilmesi
- backend/steam_leaderboard_proxy.py + src/steam_leaderboards.py: Online PvP’ye dolaylı (Steam init/availability) etkisi; prod/dev koşulları

**Key Functions/Classes:**
- OnlinePvPGame._init_networking(), OnlinePvPGame._cleanup(), OnlinePvPGame._process_messages() in src/online_pvp_game.py
- _handle_online_pvp() in src/main.py
- SteamNetworking._try_import_bridge(), SteamNetworking.init(), SteamNetworking.tick(), SteamNetworking.shutdown() in src/steam_networking.py
- SteamNetBridge::init(), SteamNetBridge::run_callbacks(), SteamNetBridge::OnSessionRequest() in steam_net_bridge.cpp
- steam_integration.init(), steam_integration._callback_pump_loop(), steam_integration.pause_pump(), steam_integration.resume_pump() in src/steam_integration.py

**Dependencies:**
- Steamworks SDK (steam_api64.dll / libsteam_api.dylib) ve Pybind11 extension (`steam_net_bridge`)
- Pygame event loop (tek thread) + background daemon threads (Steam pump, leaderboard fetch worker’ları)

**Patterns & Conventions:**
- “Graceful fallback”: Steam yoksa oyun çalışmaya devam eder (is_available gating)
- `try/except` ile güvenli degrade; Online PvP’de `_cleanup()` idempotent ve exception-safe
- Testler ağırlıkla `unittest` + `unittest.mock` ile; gerçek Steam DLL’i gerektirmeyecek şekilde mock’lanıyor

## Implementation Phases

### Phase 1: Bridge Import ve Windows DLL Search Path Stabilizasyonu

**Objective:** Windows’ta rastgele import/çalıştırma sorunlarını azaltmak, macOS’ta import yan etkilerini kontrol altına almak.

**Files to Modify/Create:**
- src/steam_networking.py: Windows `os.add_dll_directory()` handle’larını globalde tut; bridge import’u “lazy” hale getir.

**What to change (core):**
1. Windows: `os.add_dll_directory()` dönüş değerlerini (handle/context objeleri) fonksiyon-local listede değil, module-global bir listede sakla (GC ile path’in geri alınmasını önlemek için).
2. `_try_import_bridge()` çağrısını import-time’da otomatik çalıştırma (`_try_import_bridge()` → `SteamNetworking.init()` içinde çağrılacak şekilde).
3. Import hata mesajını, denenmiş yolları da loglayacak şekilde iyileştir (yalnızca crash/debug amaçlı; UX değişikliği yok).
4. macOS: `DYLD_LIBRARY_PATH` mutasyonu yerine (veya yanında) PyInstaller frozen bundle için açık aday yolları üret (örn. `Contents/Frameworks`, `Contents/MacOS`, `_MEIPASS` parent) ve import öncesi `sys.path`/env ayarlarını deterministik yap.

**Tests to Write:**
- tests/test_steam_networking_bridge_import_lazy.py: `import src.steam_networking`’in Steam bridge import’u zorlamadığını ve exception fırlatmadığını doğrula (monkeypatch ile `import steam_net_bridge` çağrısını sentinel’e bağla).
- tests/test_steam_networking_win_dll_dir_handles_persist.py: `os.add_dll_directory` mock’lanıp objelerin global listede tutulduğunu doğrula.

**Steps (TDD):**
1. Testleri yaz (lazy import + handle persist) → fail.
2. src/steam_networking.py refactor → pass.
3. Var olan test suite çalıştır (özellikle Steam testleri).

**Acceptance Criteria:**
- [ ] `steam_networking` import’u Steam DLL/bridge yokken crash etmez.
- [ ] Windows’ta DLL search path handle’ları süreç boyunca yaşamaya devam eder.
- [ ] Online PvP başlatılmadıkça bridge import denenmez.

---

### Phase 2: Steam Callback Pump Tek-Thread Garantisi (Ref-count + Atexit Güvencesi)

**Objective:** SteamAPI_RunCallbacks’ın aynı anda birden fazla thread’den çağrılması riskini daha da düşürmek ve “unutulan resume” yüzünden Steam’in session boyunca bozulmasını engellemek.

**Files to Modify/Create:**
- src/steam_integration.py: pause/resume protokolünü ref-count’lı (sayaca dayalı) hale getir; opsiyonel `atexit` güvence mekanizması.
- src/online_pvp_game.py: mevcut `_pause_steam_pump()` / `_resume_steam_pump()` çağrılarını yeni API’ye uyumlu tut (davranış aynı).

**What to change (core):**
1. `pause_pump()` / `resume_pump()` için `_pump_pause_count` ekle:
   - `pause_pump()` count++ ve `_pump_paused=True`.
   - `resume_pump()` count-- ve count==0 ise `_pump_paused=False`.
   - Negatif count olamaz; güvenli guard.
2. `pause_pump()` ack beklemesini daha deterministik yap:
   - Lock ile mevcut RunCallbacks iterasyonu bitişini beklemek zaten doğru; `Event.wait()` timeout’unda proses bırakma riskine karşı log + “best-effort” devam.
3. (Opsiyonel) `atexit.register(resume_pump)` veya `atexit.register(shutdown)` gibi güvence: process exit sırasında pump state’in tutarlı kapanmasını sağlamaya çalış.

**Tests to Write:**
- tests/test_steam_pump_pause_refcount.py: pause×2 → resume×1 (hala paused) → resume×1 (unpaused) davranışını doğrula.
- tests/test_steam_pump_pause_does_not_run_callbacks.py: `_dll.SteamAPI_RunCallbacks` mock ile paused iken çağrılmadığını doğrula.

**Acceptance Criteria:**
- [ ] Online PvP sırasında Steam callback’leri yalnızca bridge tarafından sürülür.
- [ ] Nested pause/resume (ileride başka feature eklenirse) güvenli çalışır.

---

### Phase 3: C++ Bridge Session Request Sertleştirme (Lobby üyeleri ile sınırla)

**Objective:** Beklenmeyen/istenmeyen remote session request’lerin spam/edge-case davranış üretmesini engellemek; potansiyel hang/performans sorunlarını azaltmak.

**Files to Modify/Create:**
- steamworks/steam_net_bridge/steam_net_bridge.cpp

**What to change (core):**
1. `OnSessionRequest` içinde otomatik `AcceptSessionWithUser` yerine:
   - Eğer lobby içindeysek: remote SteamID’nin lobby üyeleri listesinde olup olmadığını kontrol et; değilse accept etme.
   - Lobby yoksa: accept etme (veya yalnızca “join_requested” akışından sonra kısa bir pencere tanı).
2. Kabul edilmeyen istekler için debug event push edilebilir (örn. `session_rejected`) ama UI/UX eklenmeyecek.

**Tests to Write:**
- Not: C++ unit test altyapısı yoksa, bu faz için Python seviyesinde doğrudan test yazmak zor olabilir.
- Alternatif: Bridge’e küçük bir “inject/test hook” eklemek yerine, bu fazda sadece kod review + manual QA checklist ile ilerle (Atlas için not).

**Acceptance Criteria:**
- [ ] Lobby dışından gelen session request otomatik kabul edilmez.
- [ ] Online PvP normal akışında bağlantı hala çalışır.

---

### Phase 4: Online PvP Mesaj Doğrulama ve Dayanıklılık

**Objective:** Bozuk/eksik payload’ların oyun state’ini bozmasını veya exception doğurmasını engellemek; “sessiz takılma” riskini azaltmak.

**Files to Modify/Create:**
- src/online_pvp_game.py
- src/steam_networking.py (gerekirse)

**What to change (core):**
1. `_process_messages()` içinde gönderici doğrulaması:
   - `msg.sender` rakip değilse (ve lobby 2 kişilik değilse) ignore.
2. Mesaj alanlarını tip/limit doğrulaması:
   - `lines`, `gap`, `score`, `level` için int cast + clamp.
   - `grid` boyut kontrolü (BOARD_HEIGHT×BOARD_WIDTH veya “None/3-int list” beklenen format).
3. `GAME_START` mesajında seed/pieces doğrulaması (pieces list uzunluğu sınırı).
4. `SteamNetworking.tick()` exception durumunda “disable networking” opsiyonu:
   - Sürekli exception spam yerine `_initialized=False` + olay kuyruğuna bir `error` event.

**Tests to Write:**
- tests/test_online_pvp_message_validation.py: `_process_messages()` için sahte `NetMessage` listesiyle invalid payload’ların exception üretmeden ignore edildiğini doğrula.
- tests/test_steam_networking_tick_disables_on_exception.py: bridge_instance.run_callbacks exception fırlatınca `_initialized` düşüyor mu doğrula.

**Acceptance Criteria:**
- [ ] Bozuk JSON / beklenmeyen tipte değerler crash/hang oluşturmaz.
- [ ] Network katmanı tekrar tekrar exception fırlatırsa kendini devre dışı bırakıp oyunun menüye dönmesine izin verir.

---

### Phase 5: Clipboard Subprocess Timeout Temizliği (Windows/macOS)

**Objective:** Clipboard işlemlerinde timeout olduğunda “asılı child process” riskini azaltmak.

**Files to Modify/Create:**
- src/online_pvp_game.py

**What to change (core):**
1. Windows `_copy_to_clipboard()`:
   - `Popen` + `wait(timeout=2)` timeout olursa `process.kill()` / `terminate()` + `return False`.
2. macOS/Linux `communicate(timeout=2)` timeout olursa aynı şekilde kill.
3. (Opsiyonel) `subprocess.run(..., check=False)` ile daha basit/temiz akış.

**Tests to Write:**
- tests/test_online_pvp_clipboard_timeout_kills_process.py: subprocess mock ile TimeoutExpired simüle edip kill çağrıldığını doğrula.

**Acceptance Criteria:**
- [ ] Clipboard timeout’ları süreç sızıntısı bırakmaz.

---

### Phase 6: Paketleme (macOS/Windows) Doğrulaması ve Regresyon Kontrolü

**Objective:** macOS `.app` içinde `libsteam_api.dylib` ve `steam_net_bridge` extension’ın doğru konumda bulunmasını ve runtime’da yüklenebilmesini güvence altına almak.

**Files to Modify/Create:**
- tetris_macos.spec / tetris_macos_allinone.spec / tetris_playtest.spec (hangisi aktifse)
- docs/BUILD_AND_UPLOAD.md veya BUILD_README.md (gerekirse küçük not)

**What to change (core):**
1. Spec’lerde `binaries` / `datas` içine:
   - `dll/osx/libsteam_api.dylib`
   - `steam_net_bridge` compiled artifact (örn. `.so` / `.dylib` / `.pyd`) ve bağımlılıkları
2. macOS için extension’ın `@rpath`/`@loader_path` ile `libsteam_api.dylib` bulmasını sağlayacak yaklaşımı seç:
   - Seçenek A: Spec ile Frameworks’e koy + extension’ın install name/rpath ayarı
   - Seçenek B: `DYLD_LIBRARY_PATH`/fallback path (hardened runtime’da riskli)

**Tests to Write:**
- Eğer mevcutsa: tests/test_macos_spec_includes_steam_dylib.py (yoksa yaz): spec içinde ilgili dylib path’inin bulunduğunu doğrula (string search).

**Acceptance Criteria:**
- [ ] macOS build’de Steam entegrasyonu “sessizce devre dışı” kalmaz (kütüphane bulunur).
- [ ] Windows build’de `steam_api64.dll` ve bridge bağımlılıkları yanında paketlenir.

## Open Questions

1. Online PvP’nin “Steam yokken” davranışı ne olmalı?
   - **Option A:** Şu anki gibi sadece uyarı + mod kullanılamıyor.
   - **Option B:** Online PvP kartını tamamen gizle/disable et (UX değişikliği).
   - **Recommendation:** Option A (UX değiştirmeden) + daha açıklayıcı status_msg.

2. macOS hardened runtime / notarization hedefi var mı?
   - **Option A:** Yok → DYLD fallback ile idare edilebilir.
   - **Option B:** Var → kesinlikle Frameworks + doğru rpath/install_name gerekir.
   - **Recommendation:** Hedef varsa Option B’yi seçip build script/spec’i buna göre sabitle.

3. SessionRequest filtering, arkadaş üzerinden join akışını etkiler mi?
   - **Option A:** Sadece lobby üyelerine izin ver; join akışı lobbyye girmeden message gönderirse kırabilir.
   - **Option B:** “join_requested” sonrası kısa süreli allowlist penceresi.
   - **Recommendation:** Option B (kısa allowlist) daha güvenli.

## Risks & Mitigation

- **Risk:** steam_networking lazy-import refactor bazı import yollarını etkileyebilir.
  - **Mitigation:** İçe aktarım noktalarını grep ile bulup (Online PvP dışında) etkileri testlerle kilitle.

- **Risk:** C++ bridge değişikliği macOS/Windows build’lerini etkiler.
  - **Mitigation:** Minimum diff; build dokümanına göre iki platformda da derleme smoke test.

- **Risk:** Paketleme/rpath işi ortamdan ortama değişir.
  - **Mitigation:** Spec’leri tek bir “source of truth” haline getir; test ile spec doğrulaması ekle.

## Success Criteria

- [ ] Windows ve macOS’ta Online PvP’ye giriş/çıkış crash etmez; Steam yokken graceful fallback verir.
- [ ] Steam callback pump tek-thread garantisi güçlendirilmiş ve testlerle doğrulanmış.
- [ ] Bridge import/dylib çözümlemesi deterministik; random “bridge yüklenemedi” azalır.
- [ ] Regresyon testleri yeşil (`pytest`).

## Notes for Atlas

- Online PvP ana döngüsü uygulamada `OnlinePvPGame.run()` değil, src/main.py içindeki `_handle_online_pvp()` ile sürülüyor; cleanup/pump resume yollarını bu akış üzerinden güvenceye al.
- Windows’ta `os.add_dll_directory()` handle ömrü kritik: handle’ları globalde tutmadan yapılan eklemeler GC ile geri alınabilir.
- macOS’ta `DYLD_LIBRARY_PATH` her zaman güvenilir değildir (özellikle hardened runtime); mümkünse Frameworks + rpath yaklaşımını tercih et.
