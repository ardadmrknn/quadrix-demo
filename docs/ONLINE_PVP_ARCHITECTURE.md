# Online PvP Mimari Rehberi

> **Hedef kitle:** Bu projeyi düzenleyecek AI agentlar ve geliştiriciler.
> **Son güncelleme:** 5 Mart 2026 — Windows bridge derlemesi ve stability hardening sonrası.

---

## 1. Genel Bakış

Online PvP, Steam P2P (ISteamNetworkingMessages) üzerinden 1v1 Tetris maçı sağlar.
Hiçbir özel sunucu (dedicated server) gerekmez; tüm iletişim Steam relay üzerinden doğrudan
iki oyuncu arasında gerçekleşir.

```
┌──────────────────────┐        Steam Relay        ┌──────────────────────┐
│  Oyuncu A (Host)     │◄──── P2P Messages ────►   │  Oyuncu B (Guest)    │
│  OnlinePvPGame       │                            │  OnlinePvPGame       │
│  SteamNetworking     │                            │  SteamNetworking     │
│  steam_net_bridge    │                            │  steam_net_bridge    │
│  (C++ Pybind11)      │                            │  (C++ Pybind11)      │
└──────────────────────┘                            └──────────────────────┘
          │                                                    │
          └─── Steam Matchmaking Lobby (ISteamMatchmaking) ────┘
```

### Katman Hiyerarşisi

| Katman | Dosya | Sorumluluk |
|--------|-------|------------|
| **UI / Oyun Mantığı** | `src/online_pvp_game.py` | Lobi ekranı, durum makinesi, tahta yönetimi, çizim |
| **Python Networking** | `src/steam_networking.py` | Event/message kuyruğu, JSON serialization, high-level API |
| **C++ Bridge** | `steamworks/steam_net_bridge/steam_net_bridge.cpp` | Steamworks SDK çağrıları, callback yakalama, polling mimarisi |
| **Steam Pump** | `src/steam_integration.py` | Arka plan callback pump thread'i, pause/resume ref-count |
| **Ana Döngü** | `src/main.py` — `_handle_online_pvp()` | OnlinePvPGame yaşam döngüsü yönetimi |

---

## 2. Kritik Dosyalar ve Sorumlulukları

### 2.1 `src/online_pvp_game.py` (2450 satır)

Ana Online PvP modülü. **Tüm oyun mantığı burada.**

- **Sınıf:** `OnlinePvPGame`
- **Durum makinesi:** `OnlineState` → `LOBBY_MENU` → `WAITING` → `READY_CHECK` → `COUNTDOWN` → `PLAYING` → `GAME_OVER` / `DISCONNECTED`
- **Kilit metodlar:**
  - `_init_networking()` — Bridge'i başlatır, pump thread'i duraklatır, event handler'ları kaydeder
  - `_check_both_ready()` — İki oyuncu hazır olunca host `GAME_START` mesajı gönderir
  - `_start_countdown()` / `_start_game()` — 3-2-1 geri sayım, ardından oyun başlatma
  - `update(delta_time)` — Her frame: `net.tick()`, mesaj işleme, düşüş/kilitleme fiziği
  - `_process_messages()` — Gelen mesajları türe göre işler (READY, GAME_START, GARBAGE, BOARD_STATE, vb.)
  - `_lock_piece()` — Parça kilitleme, satır temizleme, çöp gönderme/uygulama
  - `_cleanup()` — `net.shutdown()` + `resume_pump()`
  - `handle_input()` — Pygame event işleme (hareket, döndürme, hold, hard drop, ESC)
  - `draw()` — Tüm UI çizimi (lobi ekranı, oyun tahtaları, skor paneli)

### 2.2 `src/steam_networking.py` (644 satır)

Python seviyesi networking wrapper.

- **Sınıf:** `SteamNetworking`
- **Lazy import:** Modül import zamanında bridge yüklenmez. `available` property veya `init()` çağrıldığında `_try_import_bridge()` tetiklenir.
- **Kilit metodlar:**
  - `init()` → `SteamNetBridge()` instance oluşturur, `init()` çağırır
  - `tick()` → `run_callbacks()` + `poll_events()` + `poll_messages()` — ardışık 5 hata → networking devre dışı
  - `send()` → JSON serialize + `send_message()` veya `send_message_to_lobby()`
  - `on(event_type, handler)` → Event dinleyicisi kaydı
  - `shutdown()` → `leave_lobby()` + instance temizliği
- **Önemli global'ler:**
  - `_bridge` — C++ modül referansı
  - `_bridge_available` — Bridge yüklendi mi?
  - `_bridge_import_attempted` — Deneme yapıldı mı? (tekrar denememeyi sağlar)
  - `_dll_dirs` — Windows DLL handle'ları (GC'den korunur — **bu kritik**)

### 2.3 `steamworks/steam_net_bridge/steam_net_bridge.cpp` (502 satır)

Pybind11 C++ modülü — Steam SDK ile doğrudan konuşan tek katman.

- **Sınıf:** `SteamNetBridge`
- **Polling mimarisi:** Python GIL ile çakışma olmaz. C++ callback'ler `std::deque` kuyruğuna yazar, Python `poll_events()` / `poll_messages()` ile okur.
- **Lobby işlemleri:** `create_lobby()`, `join_lobby()`, `leave_lobby()`, `invite_friend()`, `request_lobby_list()`
- **P2P mesajlaşma:** `send_message()`, `send_message_to_lobby()`, `_poll_incoming_messages()`
- **Güvenlik — OnSessionRequest:**
  - Lobby varsa: yalnızca lobby üyelerinden gelen session kabul edilir (`GetLobbyMemberByIndex` loop)
  - Lobby yoksa: `OnGameLobbyJoinRequested` sonrası 30 saniye pencere içindeyse kabul edilir
  - Aksi halde: `session_rejected` event push edilir, session reddedilir

### 2.4 `src/steam_integration.py` — Pump Thread

- Steam SDK, `SteamAPI_RunCallbacks()` periyodik çağrısı gerektirir
- `steam_integration.py` bunu arka plan daemon thread'inde yapar (~15ms aralıkla)
- **Online PvP aktifken:** Bridge kendi `tick()` → `run_callbacks()` çağırdığı için pump thread **duraklatılmalıdır** — iki thread'den aynı anda `RunCallbacks()` çağırmak **segfault** oluşturur
- **Ref-count mekanizması:** `pause_pump()` / `resume_pump()` — nested çağrılara karşı güvenli

```python
# Basitleştirilmiş akış:
_init_networking():
    pause_pump()       # ← pump thread durur
    net.init()         # ← bridge RunCallbacks devralır
    ...

_cleanup():
    net.shutdown()
    resume_pump()      # ← pump thread devam eder
```

### 2.5 `src/main.py` — `_handle_online_pvp()`

Ana oyun döngüsü Online PvP'yi bu fonksiyonla yönetir:

```
handle_input() → sonuç: False (çık), 'menu' (ana menü), 'toggle_fullscreen', None (devam)
update(delta_ms) → net.tick(), mesaj işleme, fizik
draw() → pygame ekrana çizim
```

Hata durumunda `_cleanup()` çağrılır ve `state = 'menu'` yapılır.

---

## 3. Oyun Akışı (State Machine)

```
LOBBY_MENU ──► "Özel Lobi Oluştur" ──► WAITING (rakip bekleniyor)
    │                                       │
    │  "Kod ile Katıl" / "Lobi Listesi"     │ Rakip katıldı
    │         ▼                              ▼
    └──────► WAITING ──────────────────► READY_CHECK
                                            │
                                     İki taraf READY
                                            │
                                    Host → GAME_START msg
                                            │
                                            ▼
                                        COUNTDOWN (3-2-1)
                                            │
                                            ▼
                                         PLAYING
                                          │   │
                              Biri elenirse   Rakip çıkarsa
                                  ▼               ▼
                              GAME_OVER      DISCONNECTED
```

### Lobi Katılım Yöntemleri

1. **Steam Davet:** `invite_friend()` → Steam overlay açılır
2. **Lobi Kodu:** Host, lobby_id'den 6 haneli kod üretir (`generate_lobby_code()`), metadata'ya yazar. Guest kodu girer → `search_lobby_by_code()` → lobby list filtresi + otomatik katılım
3. **Tam Lobby ID:** Köprü üzerinden doğrudan `join_lobby(id)` 
4. **Public Lobi Listesi:** `request_lobby_list()` → "quadrix" oyun filtreli liste

---

## 4. Mesaj Protokolü

Tüm mesajlar **JSON** formatında, **CHANNEL_GAME (0)** üzerinden gönderilir.
(C++ bridge şu an tek kanal polluyor; çoklu kanal desteği gelecek düzenleme.)

| Mesaj Tipi | Yön | Güvenilirlik | Açıklama |
|------------|-----|--------------|----------|
| `ready` | ↔ | Reliable | Oyuncu hazır sinyali |
| `game_start` | Host → Guest | Reliable | `{seed, timestamp, pieces[0:200]}` |
| `garbage` | ↔ | Reliable | `{lines, gap}` — çöp satır saldırısı |
| `board_state` | ↔ | **Unreliable** | `{grid, score, lines, level}` — her 500ms |
| `score_update` | ↔ | Unreliable | `{score, lines, level}` |
| `game_over` | ↔ | Reliable | Oyuncu elendi bildirimi |
| `eliminated` | ↔ | Reliable | Oyuncu elendi (alternatif) |
| `pause_request` | ↔ | Reliable | Duraklama isteği |
| `resume` | ↔ | Reliable | Devam et sinyali |
| `rematch` | ↔ | Reliable | Tekrar oyna isteği |

### Mesaj Doğrulama (Güvenlik)

- **Gönderici doğrulaması:** `_process_messages()` — yalnızca `opponent_steam_id` eşleşen mesajlar işlenir
- **Alan clamping:** `_clamp_int()` ile: lines [0,20], score [0,999999], level [0,30], gap [0,BOARD_WIDTH-1]
- **Grid doğrulama:** `_validate_grid()` — BOARD_HEIGHT × BOARD_WIDTH boyut kontrolü
- **Piece sequence limiti:** GAME_START pieces max 500 eleman
- **C++ session filtering:** OnSessionRequest lobby üyeliği kontrolü

---

## 5. Çöp Satır (Garbage) Mekanizması

```python
GARBAGE_TABLE = {1: 0, 2: 1, 3: 2, 4: 4}  # lines_cleared → garbage_sent
```

1. Oyuncu satır temizler → `_send_garbage(lines_cleared)` → `GARBAGE_TABLE` lookup → rakibe `garbage` mesajı
2. Rakipten gelen çöp → `_receive_garbage(lines, gap_col)` → `pending_garbage` kuyruğuna eklenir
3. **Savunma:** Temizlenen satırlar `pending_garbage`'ı azaltır (iptal mekanizması)
4. Parça kilitlendiğinde (`_lock_piece()`) kalan `pending_garbage` uygulanır: `_apply_pending_garbage()` tahtayı yukarı iter, gri satırlar eklenir
5. Garbage sonrası aktif parça çakışma kontrolü yapılır — kurtarılamazsa oyun biter

---

## 6. Deterministik Parça Sırası

Host oyun başlatırken rastgele `game_seed` üretir ve `GAME_START` mesajıyla gönderir.
İki taraf aynı seed'den aynı parça sırasını üretir (`_generate_pieces(seed, count)`):
- 7-bag × 3 kopya → shuffle → sıra
- Bu sayede iki oyuncu **aynı parçaları aynı sırayla** alır (adil maç)

---

## 7. Windows'ta Online PvP'yi Çalıştıran Kritik Değişiklikler

Online PvP başlangıçta yalnızca macOS'ta çalışıyordu. Windows desteği için yapılan kritik değişiklikler:

### 7.1 Bridge Derleme (En Kritik Adım)

`steam_net_bridge.pyd` Windows için **hiç derlenmemişti**. Sadece macOS `.so` dosyası mevcuttu.

**Derleme ortamı:**
- MSVC (Visual Studio 2022 Community)
- CMake
- Python 3.11 + 3.12 (iki sürüm için ayrı `.pyd`)
- Steamworks SDK header'ları: `steamworks/sdk/public/steam/`
- Link kütüphanesi: `steamworks/sdk/redistributable_bin/win64/steam_api64.lib`

**Çıktılar (proje kökünde):**
- `steam_net_bridge.cp311-win_amd64.pyd` (Python 3.11)
- `steam_net_bridge.cp312-win_amd64.pyd` (Python 3.12)

> ⚠️ Bu `.pyd` dosyaları `.gitignore`'dadır. Yeni bir makinede **tekrar derlenmesi** gerekir.

### 7.2 Bridge Lazy Import + `available` Property Fix

**Sorun:** `available` property yalnızca `_bridge_available` değişkenini okuyordu. Lazy import henüz tetiklenmediği için her zaman `False` dönüyordu → "Steam ağ köprüsü yüklenemedi" hatası.

**Çözüm:** `available` property artık `_bridge_import_attempted` kontrolü yapıyor ve gerekirse `_try_import_bridge()` çağırıyor:

```python
@property
def available(self) -> bool:
    if not _bridge_import_attempted:
        _try_import_bridge()
    return _bridge_available
```

### 7.3 DLL Handle Persistence

**Sorun:** `os.add_dll_directory()` handle'ları fonksiyon-lokal değişkende tutuluyordu → GC tarafından alınıp DLL arama yolu kayboluyordu.

**Çözüm:** Module-global `_dll_dirs: list[Any] = []` listesinde saklanıyor.

### 7.4 PyInstaller Paketleme (tetris.spec)

- `steam_net_bridge*.pyd` pattern'i ile tüm bridge dosyaları dahil edilir
- `steam_api64.dll` root'a binary olarak eklenir
- EXE build: `pyinstaller tetris.spec`

---

## 8. Thread Güvenliği

### Race Condition Önleme

```
[Ana Thread]                          [Pump Thread]
    │                                      │
    ├── pause_pump()                       │
    │   ├── _pump_pause_count += 1         │
    │   ├── _pump_paused = True            │
    │   └── with _pump_lock: pass ◄────── RunCallbacks() tamamlanınca
    │                                      │ (artık döngü duraklatıldı)
    ├── net.init()                         │
    ├── net.tick() [RunCallbacks]          │ (bekliyor)
    │     ...                              │
    ├── net.shutdown()                     │
    ├── resume_pump()                      │
    │   ├── _pump_pause_count -= 1         │
    │   └── _pump_paused = False           │
    │                                      ├── RunCallbacks() devam
```

- `_pump_lock` mutex → pump döngüsü `RunCallbacks()` sırasında pause bekletir
- Ref-count → nested pause/resume güvenli
- `atexit.register(_atexit_cleanup)` → program çıkışında pump thread temizlenir

### Tick Error Threshold

`SteamNetworking.tick()` içinde ardışık 5 exception → networking otomatik devre dışı bırakılır.
Bu, bozuk bir state'te sonsuz hata döngüsünü önler.

---

## 9. Derleme ve Dağıtım

### Bridge Derleme (Windows)

```powershell
# Gereksinimler: VS2022, Python 3.11/3.12, pybind11
cd steamworks/steam_net_bridge

# CMakeLists.txt veya doğrudan cl.exe ile:
cmake -B build -G "Visual Studio 17 2022" -A x64 ^
  -DPython3_EXECUTABLE="C:\Python311\python.exe" ^
  -Dpybind11_DIR="<pybind11_cmake_dir>"
cmake --build build --config Release

# Çıktıyı proje köküne kopyala:
copy build\Release\steam_net_bridge.cp311-win_amd64.pyd ..\..\
```

### EXE Build

```powershell
pyinstaller tetris.spec
# Çıktı: dist/Quadrix.exe (~300 MB, onefile)
```

### Steam Upload

```powershell
steamworks\sdk\tools\ContentBuilder\builder\steamcmd.exe ^
  +login vibecode_production ^
  +run_app_build "..\scripts\app_build_4428040.vdf" ^
  +quit
```

---

## 10. Sık Karşılaşılan Sorunlar & Hata Ayıklama

| Belirti | Muhtemel Neden | Çözüm |
|---------|----------------|-------|
| "Steam ağ köprüsü yüklenemedi" | `.pyd` dosyası yok veya `steam_api64.dll` bulunamıyor | Bridge'i derle, DLL'i doğru yere koy |
| `ImportError: steam_net_bridge` | Python sürüm uyumsuzluğu (cp311 vs cp312) | Doğru Python sürümü için `.pyd` derle |
| Segfault oyun sırasında | Pump thread ve bridge aynı anda `RunCallbacks()` çağırıyor | `pause_pump()` / `resume_pump()` akışını kontrol et |
| Mesajlar ulaşmıyor | Session request reddediliyor | OnSessionRequest filtreleme: lobby üyeliği veya 30s allowlist kontrolü |
| "Lobi oluşturulamadı" | `SteamAPI_Init()` başarısız | Steam istemcisinin açık olduğundan ve `steam_appid.txt` dosyasının doğru olduğundan emin ol |
| EXE'de bridge çalışmıyor | PyInstaller'a `.pyd` ve `steam_api64.dll` eklenmemiş | `tetris.spec` datas/binaries bölümünü kontrol et |
| Clipboard yapıştır timeout | macOS `pbpaste` / Linux `xclip` yanıt vermiyor | `subprocess.run(timeout=1)` + `TimeoutExpired` → `process.kill()` |

---

## 11. Dosya Bağımlılık Haritası

```
main.py
  └── _handle_online_pvp()
        └── OnlinePvPGame  (src/online_pvp_game.py)
              ├── SteamNetworking  (src/steam_networking.py)
              │     └── steam_net_bridge  (C++ .pyd/.so)
              │           └── Steamworks SDK (steam_api64.dll / libsteam_api.dylib)
              ├── pause_pump() / resume_pump()  (src/steam_integration.py)
              ├── Board  (src/board.py)
              ├── Piece  (src/pieces.py)
              ├── SoundManager  (src/sound.py)
              ├── ThemeManager  (src/themes.py)
              ├── BackgroundManager  (src/background.py)
              ├── retro_style  (src/retro_style.py)
              └── UIFonts / UIColors  (src/ui_theme.py)
```

---

## 12. AI Agent Geliştirme Rehberi

### Yeni Özellik Eklerken

1. **Mesaj tipi ekleme:** `MsgType` sınıfına sabit ekle → `_process_messages()` içinde handler yaz → `SteamNetworking`'e convenience metod ekle
2. **UI değişikliği:** `draw()` metodu içindeki ilgili `OnlineState` bloğunda çiz
3. **Yeni lobi özelliği:** C++ `SteamNetBridge`'e metod ekle → Python wrapper'a ekle → `online_pvp_game.py`'den çağır

### Dikkat Edilmesi Gerekenler

- **Tek thread RunCallbacks:** Bridge aktifken pump thread **mutlaka** duraklatılmalı
- **Lazy import:** Bridge import'u `SteamNetworking.available` veya `init()` üzerinden tetiklenir, modül seviyesinde değil
- **.pyd dosyaları gitignore'da:** Yeni bir ortamda bridge'in yeniden derlenmesi gerekir
- **Kanal kısıtlaması:** Tüm mesajlar kanal 0 üzerinden gider (C++ `_poll_incoming_messages` tek kanal polluyor)
- **Unreliable mesajlar:** `BOARD_STATE` ve `SCORE_UPDATE` unreliable gönderilir — paket kaybı normaldir
- **Test:** Bridge olmadan çalıştırılabilir testler `tests/` altında. Bridge testleri Steam istemcisi gerektirir.
- **Graceful fallback:** Steam yoksa veya bridge yüklenemezse oyun çökmez, sadece Online PvP devre dışı kalır

### Derleme Kontrol Listesi (Yeni Makine)

1. `pip install pygame-ce pybind11` (pygame değil, **pygame-ce**)
2. Steamworks SDK: `steamworks/sdk/` altında header ve lib dosyaları
3. Visual Studio 2022 (MSVC) veya uygun C++ derleyici
4. Bridge derle → `.pyd` dosyalarını proje köküne koy
5. `steam_api64.dll` → proje kökü veya `dll/win64/`
6. `steam_appid.txt` → proje kökü (içeriği: `4428040`)
7. `pyinstaller tetris.spec` → `dist/Quadrix.exe`
