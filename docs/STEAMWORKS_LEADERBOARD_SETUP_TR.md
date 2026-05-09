# Steamworks Leaderboard Kurulum Notları (Güvenli Model)

Bu projede güvenli model uygulanmıştır:

- Oyun istemcisi (`src/steam_leaderboards.py`) **Steam key kullanmaz**.
- Steam Publisher key sadece backend proxy'de tutulur.

## 1) Mimari

- Client -> `backend/steam_leaderboard_proxy.py` -> Steam Web API
- Friends skoru endpoint'i kısa ömürlü session token ister.

## 2) Backend ortam değişkenleri (sunucu)

- `STEAM_APP_ID` : Oyunun Steam AppID'si
- `STEAM_WEB_API_KEY` : Publisher Web API key (sadece backend)
- `LEADERBOARD_TOKEN_SECRET` : Session token imza sırrı (uzun rastgele değer)

Opsiyonel (ek koruma):

- `LEADERBOARD_CLIENT_TOKEN` : İstemci-proxy arası paylaşılan token
- `LEADERBOARD_ALLOWED_ORIGINS` : CORS whitelist
- `LEADERBOARD_BIND_HOST` / `LEADERBOARD_BIND_PORT`

> Kritik: `STEAM_WEB_API_KEY` ve `LEADERBOARD_TOKEN_SECRET` istemciye asla verilmez.

## 2) Mod -> Leaderboard adı eşleşmesi

Varsayılan eşleşme:

- `classic` -> `quadrix_classic`
- `sprint` -> `quadrix_sprint`
- `ultra` -> `quadrix_ultra`
- `zen` -> `quadrix_zen`
- `mystery` -> `quadrix_mystery`
- `survival` -> `quadrix_survival`
- `cascade` -> `quadrix_cascade`
- `wide` -> `quadrix_wide`
- `hardcore` -> `quadrix_hardcore`
- `daily` -> `quadrix_daily`
- `tetris2` -> `quadrix_tetris2`

Steam Partner panelindeki leaderboard isimleri bunlarla aynı olmalıdır.

## 3) Client ortam değişkenleri

- `LEADERBOARD_BACKEND_URL` : Örn. `http://127.0.0.1:8787`

Opsiyonel:

- `LEADERBOARD_CLIENT_TOKEN` (backend'de aktifse)
- `LEADERBOARD_SESSION_TOKEN` (friends endpoint için, auth sonrası)
- `LEADERBOARD_STEAM_TICKET` (client ticket -> backend auth endpoint ile session almak için)

## 4) Backend çalıştırma

Windows PowerShell:

```powershell
$env:STEAM_APP_ID="123456"
$env:STEAM_WEB_API_KEY="YOUR_PUBLISHER_KEY"
$env:LEADERBOARD_TOKEN_SECRET="cok_uzun_rastgele_secret"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_istemci_token"
py backend/steam_leaderboard_proxy.py
```

## 4.1) Steam Playtest / Steam sürümü: herkes için proxy adresini otomatik verme

Steam üzerinden oyunu oynayan oyuncuların bilgisayarında ortam değişkeni ayarlamak mümkün olmayacağı için
en pratik ve sürdürülebilir yöntem Steamworks panelinden **Launch Options** ile argüman göndermektir.

Bu repo giriş noktası `main.py`, aşağıdaki argümanları okuyup runtime’da `LEADERBOARD_BACKEND_URL` ve `LEADERBOARD_CLIENT_TOKEN`
ortam değişkenlerine yazar:

- `--leaderboard-backend-url=<url>`
- `--leaderboard-backend-url <url>`
- `--leaderboard-client-token=<token>`
- `--leaderboard-client-token <token>`

Steamworks → Installation / General Installation → Launch Options (Windows) örneği:

```
--leaderboard-backend-url=http://88.209.248.66 --leaderboard-client-token=YOUR_CLIENT_TOKEN
```

macOS notu:
- Aynı argümanlar macOS launch option alanında da kullanılabilir.
- Bu repoda macOS build giriş noktası `src/main.py` olduğu için argümanlar macOS `.app` içinde de okunur.

URL notu:
- Eğer VPS’te Nginx reverse proxy (80/443) kullanıyorsanız `http://88.209.248.66` / `https://domain` yazın.
- Eğer Nginx yok ve Flask doğrudan dışarı açıldıysa `:8787` eklemeniz gerekir.

Notlar:
- Production için HTTPS + domain önerilir (IP + HTTP geçici kullanım).
- `STEAM_WEB_API_KEY` hiçbir zaman istemciye verilmez; sadece VPS backend’de kalır.

## 5) Hızlı smoke test

Windows PowerShell örneği:

```powershell
$env:LEADERBOARD_BACKEND_URL="http://127.0.0.1:8787"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_istemci_token"
python tools/steam_leaderboard_smoke_test.py
```

## 6) Oyun entegrasyonu

- Ana menü sağ alt panel (`Kart Ustalığı`) backend'den `global` ve `friends` skorlarını çeker.
- Friends için backend session token yoksa yalnızca global görünür; friends sekmesi doğrulama hatası verir.

---

## 7) Leaderboard Yazma Başarısızlığı Teşhisi

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

**Çözüm (playtest oyuncuları için):**  
Oyuncular oyunu Playtest key veya satın alma ile edindiklerinde lisans otomatik oluşur. Ek işlem gerekmez.

> **Not:** Playtest istek kuyruğuna alınmak ≠ lisans. Onay sonrası bile erişim türüne göre lisans oluşmaması mümkündür.

### `result=27` — `k_EResultInvalidSteamID`
SteamID64 formatı hatalı. `get_steam_id_str()` çıktısını doğrulayın.

### `Init=2` (SteamAPI_InitFlat)
Steam istemcisi çalışmıyor. Steam'i başlatın.

### Debug Araçları
```powershell
# SDK + Partner API yazma durumunu an be an test et
$env:SteamAppId="4428040"
py test_lb_write.py

# Fallback ile debug (sadece geliştirici ortamı!)
$env:STEAM_PARTNER_WRITE_FALLBACK="1"
py test_lb_write.py
```

Tam runbook: [`docs/STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md`](STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md)

- Client, `LEADERBOARD_STEAM_TICKET` verilmişse `POST /api/v1/auth/steam-ticket` ile session token almayı dener.

## 8) Playtest / Ana Oyun / Demo Ayrı Leaderboard Temeli

Bu repo artık aynı leaderboard backend proxy üzerinden üç ayrı Steam AppID'ye route edebilir:

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

Client kendi AppID'sini `X-Quadrix-App-Id` header'ı ile gönderir. AppID paket içindeki `steam_appid.txt`,
`STEAM_APP_ID`, `SteamAppId` veya opsiyonel `LEADERBOARD_APP_ID` üzerinden çözülür. Steam Launch Options ile manuel
override gerekirse:

```text
--leaderboard-backend-url=https://leaderboard.example.com --leaderboard-client-token=CLIENT_TOKEN --leaderboard-app-id=4428040
```

Normal Steam build'lerinde `--leaderboard-app-id` kullanmak zorunlu değildir; doğru `steam_appid.txt` paketlendiyse
client otomatik doğru AppID header'ını yollar.

Steamworks'te her AppID altında aynı leaderboard adlarını oluşturun. AppID'ler farklı olduğu için aynı adlar birbirine
karışmaz:

- `quadrix_classic`
- `quadrix_sprint`
- `quadrix_ultra`
- `quadrix_zen`
- `quadrix_mystery`
- `quadrix_survival`
- `quadrix_cascade`
- `quadrix_wide`
- `quadrix_hardcore`
- `quadrix_daily`
- `quadrix_tetris2`
