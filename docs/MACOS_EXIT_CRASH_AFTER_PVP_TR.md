# macOS — Online PvP Sonrası Çıkışta Crash / Donma

## Belirti

1. Online PvP oynandı.
2. Ana menüye dönüldü.
3. ESC → "Oyundan Çık" onaylandı.
4. Uygulama **donuyor** (macOS "Yanıt Vermiyor") veya **çöküyor** (SIGSEGV).

## Güncel Kod Notu

Bu dosyadaki analiz katmanları korunmuştur; ancak **güncel implementasyon** artık
platform-genel bir `shutdown_barrier` refactor'ı kullanmaz.

Aktif çözüm bilinçli olarak **yalnızca macOS'a özeldir**:

1. Çıkış onayında macOS için erken `request_shutdown()` sinyali verilir.
2. Menü leaderboard/avatar işleri bu sinyali görürse erken döner.
3. `steam_integration.shutdown()` macOS'ta kısa bir global worker deadline uygular.
4. Deadline sonunda worker hâlâ yaşıyorsa `SteamAPI_Shutdown()` macOS'ta atlanır.
5. Windows/Linux mevcut genel shutdown akışında bırakılmıştır.

## Kök Neden (5 katman)

### 1. İzlenmeyen daemon thread'ler (`menu.py`)

`menu.notify_menu_activated()` çağrıldığında iki ayrı daemon thread başlatılıyordu:

| Thread | Kaynak fonksiyon | Steam API çağrıları |
|---|---|---|
| `_fetch_worker` | `_refresh_mystery_leaderboard_cache` | `get_auth_session_ticket()`, `get_steam_id_str()`, `fetch_global_scores()`, `fetch_friend_scores()` |
| `_worker` (avatar) | `_ensure_steam_header_avatar_async` | `is_available()`, `get_steam_id_str()` |

Bu thread'ler `threading.Thread(daemon=True).start()` ile başlatılıp
`steam_integration._worker_threads` kümesine **eklenmiyordu**.
`steam_integration.shutdown()` bu thread'leri tanımadığı için `SteamAPI_Shutdown()` çağrılmadan önce **join etmiyordu**.

### 2. `shutdown()` ana thread'i 3-6s bloke ediyordu

`shutdown()` tamamen `_init_lock` içinde çalışıyor:
- pump_thread.join(0.35s)
- precache_thread.join(0.35s)
- N × worker_thread.join(0.6s)  ← her worker için ayrı ayrı
- _pump_lock.acquire(1.5s)

Toplam: **3-6 saniye ana thread tamamen bloke** → macOS "Yanıt Vermiyor"

### 3. Nested worker deadlock (`fetch_leaderboard_entries`)

`_fetch_worker` içinden `fetch_leaderboard_entries()` çağrıldığında:
- Yeni bir tracked worker başlatılıyor
- `result_event.wait(timeout=9s)` ile **çağıran thread bloklanıyor**
- Sıralı olarak global + friends = **toplam 18s** bloklanma potansiyeli
- `shutdown()` bunu 0.6s join timeout ile bekliyor → worker hayatta kalıyor

### 4. Worker hayatta kalırken `SteamAPI_Shutdown()` çağrılıyordu

Join timeout'u aşan worker'lar hâlâ Steam DLL fonksiyonları çağırıyordu.
`SteamAPI_Shutdown()` sonrası bu çağrılar freed memory'e erişim → **crash**.

### 5. Erken shutdown sinyali yoktu

`running = False` ile `shutdown()` çağrısı arasında worker'lara "kapanıyoruz"
sinyali verilmiyordu. Worker'lar gereksiz yere uzun süre yaşıyordu.

```python
# ESKİ (hatalı)
def _atexit_cleanup() -> None:
    global _pump_pause_count, _pump_paused
    _pump_pause_count = 0
    _pump_paused = False   # ← TEHLİKELİ
    shutdown()
```

`_pump_paused = False` satırı, `shutdown()` çağrılmadan ÖNCE
pump thread'ini kısa süreli olarak uyandırıyordu. Pump thread
`SteamAPI_RunCallbacks()` çağırırken `shutdown()` aynı anda
`SteamAPI_Shutdown()` çağırabiliyordu → race condition.

### 3. `get_auth_session_ticket()` callback döngüsü

```python
for _ in range(5):
    run_callbacks()    # ← _shutdown_requested kontrol edilmiyordu
    time.sleep(0.05)   # ← toplam 250ms
```

Shutdown devam ederken bu döngü `SteamAPI_RunCallbacks()` çağırmaya
devam ediyordu.

## Uygulanan Düzeltmeler

### Düzeltme 1: Thread'leri `_start_tracked_worker` ile başlat

**Dosya:** `src/menu.py`

```python
# YENİ — _refresh_mystery_leaderboard_cache
try:
    import steam_integration as _si_track
    if _si_track._start_tracked_worker(_fetch_worker, name="menu-lb-fetch") is None:
        self._mystery_lb_loading = False
        return
except Exception:
    threading.Thread(target=_fetch_worker, daemon=True).start()

# YENİ — _ensure_steam_header_avatar_async
try:
    import steam_integration as _si_track
    if _si_track._start_tracked_worker(_worker, name="menu-avatar-fetch") is None:
        self._steam_header_avatar_loading = False
        return
except Exception:
    threading.Thread(target=_worker, daemon=True).start()
```

`_start_tracked_worker`:
- Thread'i `_worker_threads` kümesine ekler.
- `shutdown()` sırasında thread 0.6s timeout ile join edilir.
- `_shutdown_requested` zaten True ise `None` döner → worker başlatılmaz.

### Düzeltme 2: `_atexit_cleanup` basitleştirildi

**Dosya:** `src/steam_integration.py`

```python
# YENİ
def _atexit_cleanup() -> None:
    shutdown()
```

`shutdown()` kendi içinde `_pump_paused = True` ve `_pump_running = False`
ayarladığı için `_atexit_cleanup`'ın pump flag'lerini değiştirmesine gerek yoktur.

### Düzeltme 3: `get_auth_session_ticket()` döngüsüne guard eklendi

**Dosya:** `src/steam_integration.py`

```python
for _ in range(5):
    if _shutdown_requested:
        break
    run_callbacks()
    time.sleep(0.05)
```

### Düzeltme 4: Erken shutdown sinyali (`request_shutdown()`)

**Dosya:** `src/main.py` + `src/steam_integration.py`

"Evet, çık" basıldığında `running = False` ÖNCE `request_shutdown()` çağrılır:

```python
# main.py — confirm_exit handler
try:
    import steam_integration as _si_early
    _si_early.request_shutdown()
except Exception:
    pass
running = False
```

```python
# steam_integration.py
def request_shutdown() -> None:
    global _shutdown_requested
    _shutdown_requested = True
```

Bu sayede `running = False` → ana döngüden çıkış → cleanup bloğu
arasındaki birkaç frame boyunca worker thread'ler **kapanıyoruz** sinyalini
alır ve `_shutdown_requested` kontrolü ile kendilerini kapatır.

### Düzeltme 5: Worker join — global deadline + güvenli SteamAPI_Shutdown

**Dosya:** `src/steam_integration.py`

```python
# Global deadline ile worker'ları bekle (toplamda max 2s)
_global_deadline = time.monotonic() + 2.0
for worker_thread in worker_threads:
    remaining = _global_deadline - time.monotonic()
    if remaining <= 0:
        break
    worker_thread.join(timeout=max(0.05, remaining))

# Hâlâ yaşayan worker varsa SteamAPI_Shutdown() ÇAĞIRMA
any_alive = any(t.is_alive() for t in worker_threads)
if any_alive:
    print("[Steam] Worker hâlâ aktif, SteamAPI_Shutdown atlanıyor")
else:
    # Güvenli — tüm worker'lar bitti
    _dll.SteamAPI_Shutdown()
```

### Düzeltme 6: `fetch_leaderboard_entries` shutdown-aware bekleme

**Dosya:** `src/steam_integration.py`

```python
# ESKİ
result_event.wait(timeout=timeout + 1)  # ← 9s blok

# YENİ — 0.25s aralıklarla _shutdown_requested kontrol et
while not result_event.is_set():
    if _shutdown_requested:
        break
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        break
    result_event.wait(timeout=min(0.25, remaining))
```

### Düzeltme 7: `_fetch_worker` içine shutdown kontrolleri

**Dosya:** `src/menu.py`

`_fetch_worker` içinde her Steam API çağrısı arasına `_shutdown_requested`
kontrolü eklendi:
- Worker başlangıcında
- `fetch_global_scores()` öncesinde
- `fetch_friend_scores()` öncesinde

## Shutdown Sıralaması (Düzeltme Sonrası)

```
PvP biter → _cleanup() → net.shutdown() → _resume_steam_pump()
         → state = 'menu'
         → menu.notify_menu_activated()
            → _start_tracked_worker(_fetch_worker)   ← İZLENEN
            → _start_tracked_worker(_worker)         ← İZLENEN

ESC → confirm_exit
         → request_shutdown()                        ← ERKEN SİNYAL
            _shutdown_requested = True
            worker'lar _shutdown_requested kontrol eder ve çıkar
         → running = False
         → (birkaç frame geçer — worker'lar kapanır)
         → shutdown_all_instances()                  (networking bridge'leri kapat)
         → steam_integration.shutdown()
            1. _shutdown_requested = True (zaten)
            2. _pump_running = False, _pump_paused = True
            3. pump_thread.join(0.35s)
            4. precache_thread.join(0.35s)
            5. worker_threads join (global deadline 2s)
            6. any_alive kontrolü:
               - Tüm worker'lar bitti → SteamAPI_Shutdown() ✓
               - Yaşayan var → SteamAPI_Shutdown() ATLANIR (OS temizler)
            7. _dll = None, _init_ok = False
         → pygame.quit()
```

## Test Sonuçları

615 test geçti, 7 atlandı (Steam SDK ve platform-özel testler).
