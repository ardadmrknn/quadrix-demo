# Leaderboard Release Checklist (TR)

**AppID:** 4428040  
**Versiyon:** ___________  
**Tarih:** ___________  
**Onaylayan:** ___________

---

## A. Ön Kontroller (Kod & Yapılandırma)

- [ ] `STEAM_PARTNER_WRITE_FALLBACK` varsayılan `0` (kaynak: `steam_integration.py → _is_partner_fallback_enabled`)
- [ ] Publisher key (`_PARTNER_API_KEY`) yalnızca `steam_integration.py` debug fallback'te; kaynak koda gömülü değil
- [ ] Birim testleri geçiyor:
  ```
  py -m pytest tests/test_steam_integration_license_status.py tests/test_steam_submit_diagnostics.py tests/test_partner_fallback_flag.py tests/test_partner_fallback_enabled.py -v
  ```
- [ ] `src/steam_integration.py` syntax OK: `py -c "import src.steam_integration"`
- [ ] Steam DLL erişilebilir: `dll/win64/steam_api64.dll` (v013)

---

## B. Hesap Senaryoları Test Matrisi

Her senaryoyu **Steam açıkken** işaretle:

### Senaryo A — Lisanslı Geliştirici Hesabı (Developer Comp paketi)
| Adım | Beklenen | Geçti mi? |
|---|---|---|
| `py tests/test_lb_write.py` çalıştır | `[5] SDK: BASARILI rank=XX` | [ ] |
| `[6] Partner API` satırı yok (fallback kapalı) | Partner API çağrılmadı | [ ] |
| Oyun içi oyun → skor gönder | Log: `[Steam] SDK skor OK →` | [ ] |

### Senaryo B — Lisanssız Hesap (Playtest queue'da ama lisans yok)
| Adım | Beklenen | Geçti mi? |
|---|---|---|
| `py tests/test_lb_write.py` çalıştır | `[5] SDK: BASARISIZ` veya `Init=2` | [ ] |
| Oyun içi skor gönder | Log: `lisansi yok` mesajı, crash yok | [ ] |
| Oyun normal çalışmaya devam ediyor | Leaderboard ekranı graceful error gösteriyor | [ ] |

### Senaryo C — Steam Kapalı / Offline
| Adım | Beklenen | Geçti mi? |
|---|---|---|
| Steam kapat, oyunu başlat | Log: `SteamAPI_InitFlat başarısız` | [ ] |
| Oyun menüsü açılıyor | Steam ekranı olmadan çalışıyor | [ ] |
| Skor gönder (oyun içi) | `[Steam] Skor gonderilemedi: SDK yok` log, crash yok | [ ] |

### Senaryo D — Backend Erişilemiyor
| Adım | Beklenen | Geçti mi? |
|---|---|---|
| Backend'i durdur, oyunu başlat | Leaderboard paneli timeout/error mesajı | [ ] |
| Oyun normal çalışıyor | Blokaj yok, UI graceful degradation | [ ] |
| Backend'i yeniden başlat | Bir sonraki skor gönderimine hazır | [ ] |

---

## C. Steam Partner Portal Kontrolleri

- [ ] AppID 4428040 için leaderboard görünürlüğü: **Public** veya **Friends Only** (kasıtlı ise)
- [ ] `onlytrustedwrites` ayarı: **False** (oyuncu skorlarının yazılmasına izin ver)
- [ ] QA hesapları Developer Comp paketine eklendi
- [ ] Tüm 11 leaderboard mevcut: `quadrix_classic`, `sprint`, `ultra`, `zen`, `mystery`, `survival`, `cascade`, `wide`, `hardcore`, `daily`, `tetris2`

---

## D. Backend Güvenlik Kontrolleri

- [ ] `STEAM_WEB_API_KEY` yalnızca backend `.env`'de
- [ ] `.env` dosyası `.gitignore`'da
- [ ] Backend HTTPS üzerinde çalışıyor (prod)
- [ ] Rate-limit aktif (InMemoryRateLimiter)
- [ ] Session token TTL ≤ 1 saat

---

## E. Son Onay

| İmza | Rol | Tarih |
|---|---|---|
| | Steamworks Admin | |
| | QA Owner | |
| | Backend Ops | |

**Yeşil onay koşulu:** Tüm A, B, C senaryoları geçmeli ve D/E kontrolleri tamamlanmalı.

---

## Notlar / Açıklamalar

_Bu sütunu release sırasında doldurun:_

```
Versiyon:
Build ID:
Notlar:
```
