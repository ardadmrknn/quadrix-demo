# Steam Leaderboard Operasyon Kılavuzu (TR)

**AppID:** 4428040
**Kapsam:** Bu belge **çalışan sistemin operasyonu** içindir. Yeni kurulum, mod ↔ Steam adı eşleştirmesi ve client launch option ayarları için kanonik kaynak [STEAMWORKS_LEADERBOARD_SETUP_TR.md](STEAMWORKS_LEADERBOARD_SETUP_TR.md). Bu iki belge birbirini tekrar etmez; setup ↔ operations rolleri net ayrılmıştır.

> **Bu dosya nedir?** Backend proxy yönetimi, key rotation, incident playbook'u ve release sırasında doğrulama akışı.
> **Bu dosya ne değil?** Yeni leaderboard tanımlama veya client tarafı kurulum rehberi (orası setup belgesinde).

---

## 1. Rol ve Sorumluluk Matrisi

| Rol | Sorumluluk | Araç/Erişim |
|---|---|---|
| **Steamworks Admin** | Paket yönetimi, Developer Comp lisansları, leaderboard yapılandırması (`onlytrustedwrites` vb.) | partner.steamgames.com (tam erişim) |
| **Backend Ops** | `backend/steam_leaderboard_proxy.py` deploy, env var yönetimi, TLS sertifikaları | Sunucu erişimi + `.env` |
| **QA Owner** | Lisanslı hesap doğrulaması, release checklist onayı, smoke testleri | Steam test hesabı + `tests/test_lb_write.py` |
| **Geliştirici** | Kod değişiklikleri, test yazımı, fallback flag yönetimi | Repo + IDE |

---

## 2. Dış Bağımlılıklar

### 2.1 Steam Partner Portal
- URL: `https://partner.steamgames.com`
- Kullanım: Paket/lisans ataması, leaderboard görünürlük ayarları (`onlytrustedwrites`)
- **Kimin erişimi olmalı:** En az 1 Steamworks Admin + 1 yedek

### 2.2 Steam Partner Web API
- Base URL: `https://partner.steam-api.com`
- Endpoint (debug): `ISteamLeaderboards/SetLeaderboardScore/v1/`
- **Publisher key:** Yalnızca backend `.env` dosyasında. Kaynak kodda VEYA dağıtım paketinde tutulamaz.
- Referans: `backend/steam_leaderboard_proxy.py` → `SteamDirectGateway`

### 2.3 Backend Proxy Servisi (`backend/steam_leaderboard_proxy.py`)
- Çalışma portu: `8787` (varsayılan)
- Zorunlu env var'lar: `STEAM_APP_ID`, `STEAM_WEB_API_KEY`, `LEADERBOARD_TOKEN_SECRET`
- Bağımlılıklar: `flask`, `requests`
- **Üretimde:** Nginx/Cloudflare arkasında, HTTPS zorunlu

### 2.4 Steamworks SDK Native Kütüphaneleri
- Windows: `dll/win64/steam_api64.dll` (SDK 1.62, `SteamAPI_SteamUserStats_v013`)
- macOS: `dll/osx/libsteam_api.dylib`
- **Not:** DLL'de yalnızca `v013` mevcuttur; `v012` çağrısı `AttributeError` üretir.

---

## 3. Ortam Değişkenleri Başvurusu

### İstemci (oyun exe'si)

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `SteamAppId` | AppID (Steam init için) | `4428040` (kod içinde set edilir) |
| `STEAM_PARTNER_WRITE_FALLBACK` | Partner API write fallback | `0` (kapalı) |
| `LEADERBOARD_BACKEND_URL` | Backend proxy adresi | (Launch Options ile gelir) |
| `LEADERBOARD_CLIENT_TOKEN` | Backend istemci token'ı | (Launch Options ile gelir) |

> Steam build'lerde bu değişkenler kullanıcı PC'sinde elle ayarlanmaz; `--leaderboard-backend-url` ve `--leaderboard-client-token` Launch Options'tan gelir. Detay: [STEAMWORKS_LEADERBOARD_SETUP_TR.md](STEAMWORKS_LEADERBOARD_SETUP_TR.md) Bölüm 4.1.

### Backend Proxy

| Değişken | Açıklama | Zorunlu |
|---|---|---|
| `STEAM_APP_ID` | AppID | ✅ |
| `STEAM_WEB_API_KEY` | Publisher key | ✅ |
| `LEADERBOARD_TOKEN_SECRET` | Token imza sırrı (≥32 karakter) | ✅ |
| `LEADERBOARD_CLIENT_TOKEN` | İstemci-proxy paylaşılan token | Önerilen |
| `LEADERBOARD_ALLOWED_ORIGINS` | CORS whitelist | Önerilen (prod) |
| `LEADERBOARD_ALLOWED_APP_IDS` | Çoklu AppID route'u (`4428040,4414520,4635310`) | Çoklu kanal için |
| `LEADERBOARD_BIND_HOST` | Dinleme adresi | `127.0.0.1` |
| `LEADERBOARD_BIND_PORT` | Port | `8787` |

---

## 4. Incident Akışı

### Senaryo: `result=8` (SDK veya Partner API)

```
result=8 alındı
  └─► Hesabın AppID lisansı yok
      └─► Partner Portal → 4428040 → Packages → Developer Comp → Hesap ekle
          └─► Doğrulama: tests/test_lb_write.py → [5] SDK: BASARILI beklenir
```

Detaylı runbook: [STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md](STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md).

### Senaryo: `Init=2` (Steam kapalı)

```
Init!=0 alındı
  └─► Steam istemcisi çalışmıyor
      └─► Steam'i başlat, oyunu yeniden çalıştır
```

### Senaryo: Backend 401 / token hatası

```
HTTP 401 alındı
  └─► LEADERBOARD_CLIENT_TOKEN veya Authorization başlığı hatalı
      └─► .env değerlerini kontrol et, backend'i yeniden başlat
```

### Senaryo: Backend timeout (`requests.exceptions.Timeout`)

```
Timeout alındı
  └─► Steam Web API veya backend erişilemiyor
      └─► partner.steam-api.com erişilebilirliğini kontrol et
      └─► Backend log'larını incele
      └─► Rate-limit aşılmış olabilir (429) → bekleme süresi uygula
```

---

## 5. Release Öncesi Güvenlik Kontrol Listesi

- [ ] `STEAM_WEB_API_KEY` kaynak kodda veya `dist/` altında yok
- [ ] `STEAM_PARTNER_WRITE_FALLBACK` production build'de `0`
- [ ] Backend HTTPS'de çalışıyor (HTTP değil)
- [ ] `LEADERBOARD_TOKEN_SECRET` en az 32 karakter, rastgele oluşturulmuş
- [ ] `.env` dosyaları `.gitignore`'da
- [ ] Leaderboard `onlytrustedwrites=False` (Steam Partner Portal'da ayarlanmış)
- [ ] Developer Comp lisans atamaları QA hesapları için tamamlanmış
- [ ] `tests/test_lb_write.py` lisanslı hesapla başarılı sonuç döndürüyor
- [ ] `tools/steam_leaderboard_smoke_test.py` backend'e karşı 200 OK alıyor

---

## 6. Key Rotation Prosedürü

1. `partner.steamgames.com` → Web API Keys → Yeni key oluştur.
2. Backend `.env` içinde `STEAM_WEB_API_KEY` güncelle.
3. Backend'i yeniden başlat.
4. Smoke test: backend `/api/v1/leaderboard/global?mode=mystery` → 200 OK beklenir.
5. Eski key'i iptal et (isterseniz birkaç dakika geçiş toleransı için bekle).

---

## 7. Faydalı Komutlar

### Windows (PowerShell)

```powershell
# Backend başlat (geliştirme)
$env:STEAM_APP_ID="4428040"
$env:STEAM_WEB_API_KEY="YOUR_KEY"
$env:LEADERBOARD_TOKEN_SECRET="uzun_rastgele_secret_buraya"
py backend/steam_leaderboard_proxy.py

# Leaderboard yazma testi (Steam istemcisi açık olmalı)
$env:SteamAppId="4428040"
py tests/test_lb_write.py

# Fallback ile yazma testi (debug, geliştirici ortamı)
$env:STEAM_PARTNER_WRITE_FALLBACK="1"
py tests/test_lb_write.py

# Birim testleri
py -m pytest tests/test_steam_integration_license_status.py tests/test_steam_submit_diagnostics.py tests/test_partner_fallback_flag.py tests/test_partner_fallback_enabled.py -v

# Backend smoke test
$env:LEADERBOARD_BACKEND_URL="http://127.0.0.1:8787"
$env:LEADERBOARD_CLIENT_TOKEN="opsiyonel_token"
py tools/steam_leaderboard_smoke_test.py
```

### macOS / Linux (bash)

```bash
# Backend başlat (geliştirme)
export STEAM_APP_ID=4428040
export STEAM_WEB_API_KEY=YOUR_KEY
export LEADERBOARD_TOKEN_SECRET=uzun_rastgele_secret_buraya
python3 backend/steam_leaderboard_proxy.py

# tests/test_lb_write.py yalnızca Windows'ta anlamlıdır (Steam SDK init için);
# macOS smoke için tools/steam_leaderboard_smoke_test.py kullanın.
export LEADERBOARD_BACKEND_URL=http://127.0.0.1:8787
python3 tools/steam_leaderboard_smoke_test.py

# Lisanslı backend birim testleri
python3.12 -m pytest tests/test_steam_integration_license_status.py \
                     tests/test_steam_submit_diagnostics.py \
                     tests/test_partner_fallback_flag.py \
                     tests/test_partner_fallback_enabled.py -v
```

> `tests/test_lb_write.py` doğrudan SDK çağrısı yapar ve testler `pytest.skip` ile yalnızca Windows ortamında çalışır.

---

## 8. İlgili Dokümanlar

- Kurulum, mod ↔ Steam leaderboard adı eşleştirmesi, client launch options: [STEAMWORKS_LEADERBOARD_SETUP_TR.md](STEAMWORKS_LEADERBOARD_SETUP_TR.md)
- Lisans incident runbook'u: [STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md](STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md)
- Steam başarımları ve istatistikler: [STEAM_ACHIEVEMENTS_SETUP.md](STEAM_ACHIEVEMENTS_SETUP.md)
- Build ve upload akışı (generated): [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md)
- Steam Partner Web API parametre notları: [STEAM_LEADERBOARD_API_NOTLARI.md](STEAM_LEADERBOARD_API_NOTLARI.md)
