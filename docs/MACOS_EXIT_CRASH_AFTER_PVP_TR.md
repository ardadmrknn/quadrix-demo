# macOS — Online PvP Sonrası Çıkışta Crash

## Belirti

1. Online PvP oynandı.
2. Ana menüye dönüldü.
3. ESC → "Oyundan Çık" onaylandı.
4. Uygulama **SIGSEGV** ile çöktü (macOS).

## Kök Neden (3 katman)

### 1. İzlenmeyen daemon thread'ler (`menu.py`)

`menu.notify_menu_activated()` çağrıldığında iki ayrı daemon thread başlatılıyordu:

| Thread | Kaynak fonksiyon | Steam API çağrıları |
|---|---|---|
| `_fetch_worker` | `_refresh_mystery_leaderboard_cache` | `get_auth_session_ticket()`, `get_steam_id_str()`, `fetch_global_scores()`, `fetch_friend_scores()` |
| `_worker` (avatar) | `_ensure_steam_header_avatar_async` | `is_available()`, `get_steam_id_str()` |

Bu thread'ler `threading.Thread(daemon=True).start()` ile başlatılıp
`steam_integration._worker_threads` kümesine **eklenmiyordu**.
`steam_integration.shutdown()` bu thread'leri tanımadığı için `SteamAPI_Shutdown()` çağrılmadan önce **join etmiyordu**.

Kullanıcı hızlıca ESC → çıkış yaptığında, leaderboard thread'i hâlâ
`_dll.SteamAPI_ISteamUser_GetAuthSessionTicket()` gibi ctypes çağrıları
yapıyordu. `SteamAPI_Shutdown()` tamamlandıktan sonra bu çağrılar
serbest bırakılmış belleğe erişim (use-after-free) → **SIGSEGV**.

### 2. `_atexit_cleanup` race condition (`steam_integration.py`)

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

## Shutdown Sıralaması (Düzeltme Sonrası)

```
PvP biter → _cleanup() → net.shutdown() → _resume_steam_pump()
         → state = 'menu'
         → menu.notify_menu_activated()
            → _start_tracked_worker(_fetch_worker)   ← İZLENEN
            → _start_tracked_worker(_worker)         ← İZLENEN

ESC → confirm_exit → running = False
         → shutdown_all_instances()                  (networking bridge'leri kapat)
         → steam_integration.shutdown()
            1. _shutdown_requested = True
            2. _pump_running = False, _pump_paused = True
            3. pump_thread.join(0.35s)
            4. precache_thread.join(0.35s)
            5. _worker_threads join (0.6s each)      ← leaderboard/avatar dahil
            6. _pump_lock acquire → SteamAPI_Shutdown()
            7. _dll = None
         → pygame.quit()
```

## Test Sonuçları

621 test geçti, 7 atlandı (Steam SDK ve platform-özel testler).
