# Steam Leaderboard Güvenlik Değerlendirmesi (Uygulanan Model)

Tarih: 2026-02-12
Kapsam: `src/steam_leaderboards.py`, `src/menu.py`, `backend/steam_leaderboard_proxy.py`

## 1) Tehdit modeli özeti

- İstemci binary'sinden gizli key çıkarılması
- Yetkisiz kullanıcıların leaderboard endpoint'lerini suistimal etmesi
- Friends skorunda kimlik taklidi (`steamid` spoofing)
- Brute force / flood istekleri
- Hata mesajlarından gizli bilgi sızıntısı

## 2) Uygulanan kontroller

- **Key izolasyonu:** `STEAM_WEB_API_KEY` artık sadece backend'de kullanılıyor.
- **Proxy mimarisi:** İstemci Steam'e doğrudan gitmiyor, sadece backend'e gidiyor.
- **Session token:** Friends endpoint'i için imzalı, kısa ömürlü token zorunlu.
- **Kimlik doğrulama:** Steam ticket doğrulama endpoint'i eklendi (`AuthenticateUserTicket`).
- **Rate limiting:** IP+path bazlı in-memory token bucket.
- **Input hardening:** Mod whitelist, limit clamp, body size limiti, JSON content-type kontrolü.
- **Response hardening:** `nosniff`, `DENY`, `no-referrer`, `no-store` başlıkları.
- **Secret hygiene:** `.env` dosyaları `.gitignore` içine alındı.

## 3) Kapatılan açık sınıfları

- Client-side secret exposure (kritik)
- Friends verisinde client tarafından verilen steamid'ye kör güvenme (yüksek)
- Temel API abuse (orta)

## 4) Kalan riskler (residual)

- In-memory rate limiter çoklu instance ortamında global değil.
- Geliştirme sırasında HTTP kullanılabilir; üretimde TLS zorunlu olmalı.
- Session token storage client tarafında hâlâ ele geçirilebilir olabilir (kısa ömür bu riski azaltır).

## 5) Önerilen sonraki adımlar

- Prod'da reverse proxy (Nginx/Cloudflare) + global rate limit + WAF
- Token secret rotasyonu ve key rotation prosedürü
- Backend audit logging + SIEM entegrasyonu
- Session token replay azaltımı için nonce/jti blacklist veya very short TTL
- CI'da secret scanning (gitleaks/trufflehog) ve dependency scanning
