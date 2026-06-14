# Steamworks Leaderboard Kurulum Notları (Güvenli Model)

Bu belge, Quadrix'in Steam leaderboard altyapısını **kurmak** için kanonik kaynaktır. Operasyon, key rotation ve incident playbook'u için: [STEAM_LEADERBOARD_OPERATIONS_TR.md](STEAM_LEADERBOARD_OPERATIONS_TR.md). Bu iki belge birbirini tekrar etmez.

> **Bu dosya nedir?** Mimari özet, mod ↔ Steam leaderboard adı eşleştirmesi, backend ortam değişkenleri, Steam Launch Options ile client tarafı yapılandırma.
> **Bu dosya ne değil?** Çalışan sistemin operasyonu (orası operations belgesinde).

Bu projede güvenli model uygulanmıştır:

- Oyun istemcisi (`src/steam_leaderboards.py`) **Steam Web API key kullanmaz**.
- Steam Publisher key sadece backend proxy'de tutulur.
- Tüm yazma işlemleri SDK üzerinden yapılır; ayrıca opsiyonel olarak backend tarafı Partner API fallback'i destekler.

## 1) Mimari

```
┌──────────────────────┐
│   Oyun İstemcisi     │
│ src/steam_leaderboards│
│       _public        │
└──────────┬───────────┘
           │ HTTPS
           ▼
┌──────────────────────┐
│ backend/steam_lead-  │
│ erboard_proxy.py     │ ← Yalnızca burada STEAM_WEB_API_KEY
└──────────┬───────────┘
           │ HTTPS
           ▼
┌──────────────────────┐
│ Steam Web API        │
│ partner.steam-api.com│
└──────────────────────┘
```

- Friends skoru endpoint'i kısa ömürlü session token ister.
- Global skorlar opsiyonel `LEADERBOARD_CLIENT_TOKEN` ile korunur.

## 2) Mod → Leaderboard Adı Eşleşmesi

Varsayılan eşleşme (`src/steam_leaderboards.py` içindeki `DEFAULT_MODE_TO_LEADERBOARD` ile birebir):

| Mod | Leaderboard adı |
| --- | --- |
| `classic` | `quadrix_classic` |
| `sprint` | `quadrix_sprint` |
| `ultra` | `quadrix_ultra` |
| `zen` | `quadrix_zen` |
| `mystery` | `quadrix_mystery` |
| `survival` | `quadrix_survival` |
| `cascade` | `quadrix_cascade` |
| `wide` | `quadrix_wide` |
| `hardcore` | `quadrix_hardcore` |
| `daily` | `quadrix_daily` |
| `tetris2` | `quadrix_tetris2` |

Steam Partner panelindeki leaderboard isimleri bunlarla **birebir** aynı olmalıdır. Tipik hata: leaderboard adında alt çizgi/aralık farkı.

## 3) Backend Ortam Değişkenleri (Sunucu)

### Zorunlu

- `STEAM_APP_ID` — Oyunun Steam AppID'si (örn. `4428040` playtest, `4414520` ana oyun, `4635310` demo)
- `STEAM_WEB_API_KEY` — Publisher Web API key (sadece backend)
- `LEADERBOARD_TOKEN_SECRET` — Session token imza sırrı (uzun rastgele değer, ≥32 karakter)

### Opsiyonel (önerilen)

- `LEADERBOARD_CLIENT_TOKEN` — İstemci-proxy arası paylaşılan token
- `LEADERBOARD_ALLOWED_ORIGINS` — CORS whitelist
- `LEADERBOARD_ALLOWED_APP_IDS` — Çoklu AppID route'u (`4428040,4414520,4635310`)
- `LEADERBOARD_BIND_HOST` / `LEADERBOARD_BIND_PORT` — Dinleme adresi/portu (varsayılan `127.0.0.1:8787`)

> **Kritik:** `STEAM_WEB_API_KEY` ve `LEADERBOARD_TOKEN_SECRET` istemciye **asla** verilmez ve dağıtım paketinde tutulmaz.

## 4) Client Tarafı Yapılandırma

### 4.1) Steam Playtest / Steam sürümü: Launch Options ile dağıtım

Steam üzerinden oyunu oynayan oyuncuların bilgisayarında ortam değişkeni ayarlamak mümkün olmadığı için en pratik yöntem Steamworks panelinden **Launch Options** ile argüman göndermektir.

`main.py` aşağıdaki argümanları okur ve runtime'da `LEADERBOARD_BACKEND_URL` ve `LEADERBOARD_CLIENT_TOKEN` ortam değişkenlerine yazar:

- `--leaderboard-backend-url=<url>` veya `--leaderboard-backend-url <url>`
- `--leaderboard-client-token=<token>` veya `--leaderboard-client-token <token>`
- `--leaderboard-app-id=<id>` (opsiyonel; çoklu AppID route'u için)

Steamworks → Installation / General Installation → Launch Options örneği:

```
--leaderboard-backend-url=https://leaderboard.example.com --leaderboard-client-token=YOUR_CLIENT_TOKEN
```

Notlar:

- Production için **HTTPS + domain** önerilir. IP + HTTP yalnızca geçici/dev kullanım içindir.
- Nginx reverse proxy varsa `https://leaderboard.example.com`; Flask doğrudan açıksa `http://IP:8787`.
- Aynı argümanlar macOS launch option alanında da kullanılabilir; macOS build giriş noktası `src/main.py` olduğu için `.app` içinde de okunur.

### 4.2) Geliştirme ortamında manuel env

Yerel test için:

```powershell
$env:LEADERBOARD_BACKEND_URL="http://127.0.0.1:8787"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_token"
py main.py
```

```bash
export LEADERBOARD_BACKEND_URL=http://127.0.0.1:8787
export LEADERBOARD_CLIENT_TOKEN=opsiyonel_token
python3 main.py
```

## 5) Backend'i Çalıştırma

### Windows (PowerShell)

```powershell
$env:STEAM_APP_ID="4428040"
$env:STEAM_WEB_API_KEY="YOUR_PUBLISHER_KEY"
$env:LEADERBOARD_TOKEN_SECRET="cok_uzun_rastgele_secret"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_istemci_token"
py backend/steam_leaderboard_proxy.py
```

### macOS / Linux

```bash
export STEAM_APP_ID=4428040
export STEAM_WEB_API_KEY=YOUR_PUBLISHER_KEY
export LEADERBOARD_TOKEN_SECRET=cok_uzun_rastgele_secret
export LEADERBOARD_CLIENT_TOKEN=opsiyonel_istemci_token
python3 backend/steam_leaderboard_proxy.py
```

## 6) Hızlı Smoke Test

```powershell
$env:LEADERBOARD_BACKEND_URL="http://127.0.0.1:8787"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_istemci_token"
py tools/steam_leaderboard_smoke_test.py
```

```bash
export LEADERBOARD_BACKEND_URL=http://127.0.0.1:8787
export LEADERBOARD_CLIENT_TOKEN=opsiyonel_istemci_token
python3 tools/steam_leaderboard_smoke_test.py
```

Beklenen: backend 200 OK, en az bir mod için global skor listesi döner.

## 7) Oyun Entegrasyonu (Özet)

- Ana menü sağ alt panel (`Kart Ustalığı`) backend'den `global` ve `friends` skorlarını çeker.
- Friends için backend session token yoksa yalnızca global görünür; friends sekmesi doğrulama hatası verir.
- Client, `LEADERBOARD_STEAM_TICKET` verilmişse `POST /api/v1/auth/steam-ticket` ile session token almayı dener.

## 8) Çoklu AppID Route'u (Playtest / Ana Oyun / Demo)

Bu repo aynı backend proxy üzerinden üç ayrı Steam AppID'ye route edebilir:

- Playtest: `4428040`
- Ana oyun Quadrix: `4414520`
- Demo: `4635310`

Backend ortam değişkeni:

```powershell
$env:STEAM_APP_ID="4428040"
$env:LEADERBOARD_ALLOWED_APP_IDS="4428040,4414520,4635310"
$env:STEAM_WEB_API_KEY="YOUR_PUBLISHER_KEY"
$env:LEADERBOARD_TOKEN_SECRET="LONG_RANDOM_SECRET"
$env:LEADERBOARD_CLIENT_TOKEN="CLIENT_TOKEN"
py backend/steam_leaderboard_proxy.py
```

Client kendi AppID'sini `X-Quadrix-App-Id` header'ı ile gönderir. AppID şu sırayla çözülür:

1. Paket içindeki `config/runtime/steam_appid.txt`
2. `STEAM_APP_ID` ortam değişkeni
3. `SteamAppId` ortam değişkeni
4. Opsiyonel `LEADERBOARD_APP_ID` ortam değişkeni
5. `--leaderboard-app-id` CLI argümanı

Steam build'lerde `--leaderboard-app-id` kullanmak zorunlu değildir; doğru `steam_appid.txt` paketlendiyse client otomatik doğru header yollar.

## 9) Leaderboard Yazma Başarısızlığı Teşhisi

### `result=8` — `k_EResultInvalidParam` (En Sık Karşılaşılan)

**Anlam:** İstek yapan Steam hesabının AppID 4428040 için **geçerli bir lisansı yok**.

**SDK belirtisi:**

```
m_bSuccess = 0   (UploadLeaderboardScore callback sonucu)
```

**Partner API belirtisi:**

```json
{"result": {"result": 8}}
```

**Çözüm (geliştirici/QA hesabı için):**

```
partner.steamgames.com
  → Apps & Packages → Apps → 4428040
    → Packages & Activations → Packages
      → Quadrix - Developer Comp → Edit Package
        → Add Steam Account → [SteamID64 gir] → Save
```

**Çözüm (playtest oyuncuları için):** Oyuncular oyunu Playtest key veya satın alma ile edindiklerinde lisans otomatik oluşur. Ek işlem gerekmez.

> **Not:** Playtest istek kuyruğuna alınmak ≠ lisans. Onay sonrası bile erişim türüne göre lisans oluşmaması mümkündür.

### `result=27` — `k_EResultInvalidSteamID`

SteamID64 formatı hatalı. `get_steam_id_str()` çıktısını doğrulayın.

### `Init=2` (SteamAPI_InitFlat)

Steam istemcisi çalışmıyor. Steam'i başlatın.

### Debug Araçları

```powershell
# SDK + Partner API yazma durumunu test et (yalnızca Windows)
$env:SteamAppId="4428040"
py tests/test_lb_write.py

# Fallback ile debug (yalnızca geliştirici ortamı!)
$env:STEAM_PARTNER_WRITE_FALLBACK="1"
py tests/test_lb_write.py
```

Tam runbook: [STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md](STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md)

## 10) İlgili Dokümanlar

- Operasyonel runbook (key rotation, incident, release): [STEAM_LEADERBOARD_OPERATIONS_TR.md](STEAM_LEADERBOARD_OPERATIONS_TR.md)
- Steam başarımları ve istatistikler: [STEAM_ACHIEVEMENTS_SETUP.md](STEAM_ACHIEVEMENTS_SETUP.md)
- Steam Partner Web API parametre notları: [STEAM_LEADERBOARD_API_NOTLARI.md](STEAM_LEADERBOARD_API_NOTLARI.md)
- Lisans incident runbook'u: [STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md](STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md)
- Build ve upload (generated): [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md)
