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
- Client, `LEADERBOARD_STEAM_TICKET` verilmişse `POST /api/v1/auth/steam-ticket` ile session token almayı dener.
