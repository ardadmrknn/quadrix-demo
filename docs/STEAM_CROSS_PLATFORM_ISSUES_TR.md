# Steam Çapraz Platform Sorunları — Kök Neden Analizi ve Çözümler

> **Tarih:** 3 Nisan 2026  
> **İlgili dosyalar:**  
> - `steamworks/steam_net_bridge/steam_net_bridge.cpp`  
> - `src/steam_networking.py`  
> - `src/online_pvp_game.py`  
> - `src/steam_integration.py`  
> - `src/main.py`

---

## Sorun 1: macOS → Windows "Hazır" Sinyali Görünmüyor

### Belirtiler
- macOS tarafı "Hazır" butonuna bastığında Windows tarafında hazır durumu güncellenmiyor.
- session_ping (kanal 0) çalışıyor ama READY mesajı (eski: kanal 2) ulaşmıyor.

### Kök Neden
**Kanal uyumsuzluğu (C++ ikili dosya / Python kaynak senkronu bozuk)**

Python kodu `steam_networking.py` dosyasındaki yorum zaten uyarıyordu:

```python
# NOT: C++ bridge şu an yalnızca kanal 0'ı polluyor (_poll_incoming_messages).
# Tüm mesajlar CHANNEL_GAME (0) üzerinden gönderilmelidir.
```

Ancak aynı dosyada `send_ready()` → `channel=CHANNEL_CONTROL (2)` üzerinden gönderiliyordu. C++ kaynak kodu (`run_callbacks()`) üç kanalı da yoklamasına rağmen, **macOS ve Windows ikili dosyaları (.so / .pyd) farklı zamanlarda derleniyor**. Windows makinede eski bir derleme kullanılıyorsa, yalnızca kanal 0 yoklanır ve kanal 2'deki mesajlar kaybolur.

### Tekrar Etme Nedeni
Her platform kendi C++ derlemesini kullanır:
- macOS: `steam_net_bridge.cpython-312-darwin.so`
- Windows: `steam_net_bridge.cpython-312-win_amd64.pyd`

Bu ikili dosyalar GitHub'a işlenmez (`.gitignore` veya boyut kısıtlaması). Python kodu güncellenip C++ derlemesi yapılmazsa veya sadece bir platformda yapılırsa, senkron bozulur.

### Çözüm
**Tüm mesajlar `CHANNEL_GAME (0)` üzerinden gönderilir.**

```python
CHANNEL_GAME = 0       # TÜM mesajlar bu kanal üzerinden gönderilir
CHANNEL_STATE = 0      # (eski: 1) — artık CHANNEL_GAME ile aynı
CHANNEL_CONTROL = 0    # (eski: 2) — artık CHANNEL_GAME ile aynı
```

Bu sayede hangi C++ derlemesi olursa olsun (kanal 0 her versiyonda yoklanır) mesajlar ulaşır. C++ tarafı zaten üç kanalı da yoklar ama Python tarafının dayanıklılığı artırılmıştır.

### Etkilenen Mesajlar
| Mesaj Tipi | Eski Kanal | Yeni Kanal |
|---|---|---|
| READY | 2 (CONTROL) | 0 (GAME) |
| GAME_START | 2 (CONTROL) | 0 (GAME) |
| GAME_OVER | 2 (CONTROL) | 0 (GAME) |
| BOARD_STATE | 1 (STATE) | 0 (GAME) |
| PIECE_POSITION | 1 (STATE) | 0 (GAME) |
| SCORE_UPDATE | 1 (STATE) | 0 (GAME) |
| GARBAGE | 0 (GAME) | 0 (GAME) — değişmedi |

---

## Sorun 2: Özel Lobi, Windows'ta Herkese Açık Görünüyor

### Belirtiler
- macOS'ta özel lobi oluşturuluyor (davet + kod gerekli).
- Windows'ta lobi tarayıcısında "Açık lobi" olarak görünüyor.
- Kod girmeden doğrudan katılınabiliyor.

### Kök Neden
**Metadata propagasyon yarış koşulu + güvensiz fallback**

1. macOS `CreateLobby(k_ELobbyTypeInvisible)` çağırır.
2. Steam sunucusu lobiyi oluşturur.
3. macOS `OnLobbyCreated` callback'inde metadata ayarlar:
   - `visibility=private`, `requires_code=1`
4. Windows `RequestLobbyList()` ile lobi listesini sorgular.
5. C++ `OnLobbyListReceived` → her lobi için `RequestLobbyData()` çağırır.
6. `OnLobbyDataUpdate` → `build_lobby_found_payload()` çağrılır.
7. **Eğer metadata henüz propagasyon yapmamışsa**, `GetLobbyData("visibility")` boş döner.

Eski fallback mantığı:
```cpp
if (visibility.empty()) {
    visibility = (requiresCodeBool || !lobbyCode.empty()) ? "private" : "public";
}
```
`requiresCode` da boş → `"0"` → `false`, `lobbyCode` da boş → sonuç: **"public"**.

Python tarafında da aynı sorun:
```python
visibility = (_read_lobby_data('visibility', 'public') or 'public')  # Eski: public fallback
```

### Çözüm

**C++ (`build_lobby_found_payload`):** Varsayılan fallback `"private"` yapıldı:
```cpp
if (visibility.empty()) {
    visibility = "private";
    requiresCodeBool = true;
}
```
Mantık: Yanlış "private" (kod gir ekranı gösterir) ≫ Yanlış "public" (doğrudan katılım).

**Python (`_on_lobby_found`):** Varsayılan `'private'` yapıldı:
```python
visibility = (_read_lobby_data('visibility', 'private') or 'private')
requires_code = (_read_lobby_data('requires_code', '1') or '1') in ('1', 'true', 'yes')
```

**C++ (`OnLobbyDataUpdate`):** `m_bSuccess` kontrolü eklendi — başarısız veri istekleri için lobby_found yayınlanmaz:
```cpp
if (!pParam->m_bSuccess) {
    consume_pending_lobby_data_request(pParam->m_ulSteamIDLobby);
    complete_lobby_list_if_ready();
    return;  // lobby_found yayınlama — veri güvenilir değil
}
```

---

## Sorun 3: macOS'ta Steam'den Çıkışta Donma

### Belirtiler
- Oyun Steam üzerinden başlatılıyor.
- Oyundan çıkılmak istendiğinde uygulama donuyor.
- Zorla kapatma gerekiyor (Force Quit).
- Daha önce düzeltildi ama tekrar etti.

### Kök Neden
**C++ destructor → SteamAPI_Shutdown() sonrası Steam çağrısı**

Çıkış sırası:
1. `main.py` → `running = False`
2. `steam_integration.shutdown()` çağrılır:
   - Pump thread durur
   - `SteamAPI_Shutdown()` çağrılır
   - **Tüm Steam interface pointer'ları geçersiz olur**
3. Python GC, `SteamNetBridge` C++ nesnesini toplar.
4. C++ destructor çalışır: `~SteamNetBridge() { leave_lobby(); }`
5. `leave_lobby()` → `m_matchmaking->LeaveLobby()` → **CRASH / HANG**
   - macOS'ta geçersiz pointer'a erişim donmaya neden olur.

### Tekrar Etme Nedeni
Bu sorun şu hallerde tekrar eder:
1. `main.py`'da bridge temizliği `steam_integration.shutdown()` öncesinde yapılmazsa.
2. Online PvP oynandıktan sonra menüye dönülüp oyundan çıkılırsa (bridge nesnesi hâlâ canlı).
3. C++ destructor'da Steam API çağrısı varsa.

### Çözüm (3 katmanlı savunma)

**Katman 1 — C++ destructor güvenliği:**
```cpp
~SteamNetBridge() {
    // Steam API çağrısı YAPMA! SteamAPI_Shutdown() sonrası pointer geçersiz.
}
```

**Katman 2 — C++ `shutdown()` metodu:**
```cpp
void shutdown() {
    if (m_isShutdown) return;
    m_isShutdown = true;
    // SteamAPI_Shutdown() ÖNCESİNDE çağrılmalı
    if (m_matchmaking && m_currentLobby.IsValid()) {
        m_matchmaking->LeaveLobby(m_currentLobby);
    }
    m_matchmaking = nullptr;
    m_messages = nullptr;
    m_friends = nullptr;
}
```

Tüm public metodlara `m_isShutdown` kontrolü eklendi.

**Katman 3 — Python tarafı sıralama:**

`main.py` çıkış sırası:
```python
# 1. Önce C++ bridge'i temizle
from steam_networking import shutdown_all_instances
shutdown_all_instances()

# 2. Sonra Steam API'yı kapat
steam_integration.shutdown()
```

`steam_networking.py`'da aktif instance takibi:
```python
_active_instances: list[SteamNetworking] = []

def shutdown_all_instances():
    for inst in list(_active_instances):
        inst.shutdown()
    _active_instances.clear()
```

---

## Genel Önleme Kuralları

### C++ Derleme Senkronizasyonu
1. C++ kaynağı (`steam_net_bridge.cpp`) değiştirildiğinde **HER İKİ platform** da yeniden derlenmelidir.
2. macOS: `steamworks/steam_net_bridge/build.sh`
3. Windows: `steamworks/steam_net_bridge/build.bat`
4. Python kodu, C++ binary uyumsuzluğuna dayanıklı yazılmalıdır (kanal 0 kullanımı gibi).

### Steam API Yaşam Döngüsü
1. `SteamAPI_Init()` → en başta çağrılır.
2. C++ bridge oluşturulur → `bridge.init()`
3. Online PvP sırasında bridge `run_callbacks()` çağırır (pump thread duraklatılır).
4. Çıkışta: `bridge.shutdown()` → `resume_pump()` → `steam_integration.shutdown()`
5. **Hiçbir zaman** `SteamAPI_Shutdown()` sonrası Steam fonksiyonu çağırma.

### Lobi Metadata Güvenliği
1. Metadata fallback'i her zaman "private" olmalı (güvenli taraf).
2. `OnLobbyDataUpdate` içinde `m_bSuccess` kontrol edilmeli.
3. Lobi tipi INVISIBLE (3) her zaman `requires_code=true` olarak ele alınmalı.
