# Steam Leaderboard Operasyon Kılavuzu (TR)

**AppID:** 4428040  
**Oluşturma:** 25 Şubat 2026

---

## 1. Rol ve Sorumluluk Matrisi

| Rol | Sorumluluk | Araç/Erişim |
|---|---|---|
| **Steamworks Admin** | Paket yönetimi, Developer Comp lisansları, leaderboard yapılandırması | partner.steamgames.com (tam erişim) |
| **Backend Ops** | `steam_leaderboard_proxy.py` deploy, env var yönetimi, TLS sertifikaları | Sunucu erişimi + `.env` |
| **QA Owner** | Lisanslı hesap doğrulaması, release checklist onayı, smoke testleri | Steam test hesabı + `test_lb_write.py` |
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
- **Publisher key:** Yalnızca backend `.env` dosyasında, kaynak kodda SAKLANAMAZINIZ
- Referans: `backend/steam_leaderboard_proxy.py` → `SteamDirectGateway`

### 2.3 Backend Proxy Servisi (`steam_leaderboard_proxy.py`)
- Çalışma portu: `8787` (varsayılan)
- Zorunlu env var'lar: `STEAM_APP_ID`, `STEAM_WEB_API_KEY`, `LEADERBOARD_TOKEN_SECRET`
- Bağımlılıklar: `flask`, `requests`
- **Üretimde:** Nginx/Cloudflare arkasında, HTTPS zorunlu

### 2.4 Steamworks SDK DLL
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

### Backend Proxy
| Değişken | Açıklama | Zorunlu |
|---|---|---|
| `STEAM_APP_ID` | AppID | ✅ |
| `STEAM_WEB_API_KEY` | Publisher key | ✅ |
| `LEADERBOARD_TOKEN_SECRET` | Token imza sırrı (≥32 karakter) | ✅ |
| `LEADERBOARD_CLIENT_TOKEN` | İstemci-proxy paylaşılan token | Önerilen |
| `LEADERBOARD_ALLOWED_ORIGINS` | CORS whitelist | Önerilen (prod) |
| `LEADERBOARD_BIND_HOST` | Dinleme adresi | `127.0.0.1` |
| `LEADERBOARD_BIND_PORT` | Port | `8787` |

---

## 4. Incident Akışı

### Senaryo: `result=8` (SDK veya Partner API)
```
result=8 alındı
  └─► Hesabın AppID lisansı yok
      └─► Partner Portal → 4428040 → Packages → Developer Comp → Hesap ekle
          └─► Doğrulama: py test_lb_write.py → [5] SDK: BASARILI beklenir
```

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

### Senaryo: Backend timeout (requests.exceptions.Timeout)
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
- [ ] `test_lb_write.py` lisanslı hesapla başarılı sonuç döndürüyor

---

## 6. Key Rotation Prosedürü

1. `partner.steamgames.com` → Web API Keys → Yeni key oluştur.
2. Backend `.env` içinde `STEAM_WEB_API_KEY` güncelle.
3. Backend'i yeniden başlat.
4. Smoke test: backend `/api/v1/leaderboard/global?mode=mystery` → 200 OK beklenir.
5. Eski key'i iptal et (isterseniz birkaç dakika geçiş toleransı için bekle).

---

## 7. Faydalı Komutlar

```powershell
# Backend başlat (geliştirme)
$env:STEAM_APP_ID="4428040"
$env:STEAM_WEB_API_KEY="YOUR_KEY"
$env:LEADERBOARD_TOKEN_SECRET="uzun_rastgele_secret_buraya"
py backend/steam_leaderboard_proxy.py

# Leaderboard yazma testi
$env:SteamAppId="4428040"
py tests/test_lb_write.py

# Fallback ile yazma testi (debug, geliştirici ortamı)
$env:STEAM_PARTNER_WRITE_FALLBACK="1"
py tests/test_lb_write.py

# Tüm birim testleri
py -m pytest tests/test_steam_integration_license_status.py tests/test_steam_submit_diagnostics.py tests/test_partner_fallback_flag.py tests/test_partner_fallback_enabled.py -v
```
