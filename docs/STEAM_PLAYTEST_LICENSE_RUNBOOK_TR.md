# Steam Playtest Lisans Runbook (TR)

**AppID:** 4428040  
**Oluşturma:** 25 Şubat 2026  
**Bakıcı:** Steamworks Admin (geliştirici ekibi)

---

## Sorun Tanımı

Steam Leaderboard yazma çağrıları (`UploadLeaderboardScore` / `SetLeaderboardScore`), ilgili Steam hesabının AppID için **geçerli bir Steam lisansı** yoksa başarısız olur:

- SDK yanıtı: `m_bSuccess = 0`
- Partner Web API yanıtı: `result = 8` (`k_EResultInvalidParam`)

> **Kritik Ayrım:** Steam Playtest **istek kuyruğuna alınmak** ≠ Steam lisansı edinmek.  
> Bir hesap playtesti isteyip kabul edilse bile leaderboard yazmak için AppID lisansına sahip olması gerekir.

---

## Çözüm: Geliştirici / QA Hesabı İçin

### Adım 1 — Partner Portal'a Giriş
```
https://partner.steamgames.com/
```

### Adım 2 — Uygulama Seç
`Apps & Packages → Apps → 4428040 (Quadrix)`

### Adım 3 — Packages & Activations
Sol menüde: **Packages & Activations → Packages**

### Adım 4 — Developer Comp Paketi Bul
`Quadrix - Developer Comp` isimli paket için **"Edit Package"** tıkla.

### Adım 5 — Hesap Ekle
- **"Add Steam Account"** yanına SteamID64 veya Steam kullanıcı adını gir.
- SteamID64 formatı (örnek): `76561199351154071`
- Onay için **"Save"** tıkla.

### Adım 6 — Doğrulama
```powershell
# Steam açıkken çalıştır
$env:SteamAppId="4428040"
py test_lb_write.py
```
Beklenen çıktı:
```
[5] SDK: BASARILI rank=XX
```

---

## Çözüm: Playtest Oyuncuları İçin

**Kalıcı çözüm:** Oyuncular oyunu bir Steam Playtest key veya satın alma ile edindiklerinde lisans otomatik oluşur. SDK bu lisansı tanır ve yazmaya izin verir; özel işlem gerekmez.

**Playtest erişim kanalları:**
| Kanal | Lisans oluşur mu? |
|---|---|
| Playtest istek kuyruğu onayı | ✅ Evet (oyuncuya lisans tanımlanır) |
| Steamworks'te manuel "Activate Key" | ✅ Evet |
| Developer Comp paketi | ✅ Evet (dev/staff için) |
| Sadece istek kuyruğuna girme (onaylanmamış) | ❌ Hayır |

---

## Hata Kodu Başvurusu

| Hata Kodu | Anlam | Çözüm |
|---|---|---|
| `result=8` (`k_EResultInvalidParam`) | Hesapta AppID lisansı yok | Developer Comp veya playtest key ver |
| `result=27` (`k_EResultInvalidSteamID`) | Geçersiz SteamID64 | SteamID formatını kontrol et |
| `SDK success=0` | Genel yazma başarısızlığı | `result=8` mi diye Partner API ile kontrol et |
| `Init=2` (SteamAPI_InitFlat) | Steam kapalı | Steam istemcisini başlat |

---

## Ortam Değişkenleri (Debug)

```powershell
# Partner API fallback'i geçici olarak aç (sadece debug/staff için)
$env:STEAM_PARTNER_WRITE_FALLBACK = "1"    # Açık
$env:STEAM_PARTNER_WRITE_FALLBACK = "0"    # Kapalı (varsayılan, üretim)
```

> **Güvenlik Notu:** `STEAM_PARTNER_WRITE_FALLBACK=1` production build'lerde **asla** açık bırakılmamalıdır. Publisher key içerdiğinden yalnızca geliştirici ortamında kullanın.

---

## Sık Sorulan Sorular

**S: Playtest oyuncuları skorlarını görebiliyor ama yazamıyor — neden?**  
C: Leaderboard okuma (GET) her hesaba açıktır. Yazma için lisans gerekir. Oyuncuya key/paketi verify et.

**S: Birden fazla test hesabı eklememiz gerekiyor mu?**  
C: Evet. Her QA/developer hesabı için ayrı ayrı Developer Comp paketi üzerinden yetkilendirme gerekir.

**S: Yeni build çıkardık ama hâlâ `result=8` alıyoruz?**  
C: Lisans sorunu kod kaynaklı değildir. Hesap→paket ataması kontrol edin.
