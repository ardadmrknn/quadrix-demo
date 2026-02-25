# Plan: Steam Leaderboards (result=8) Fix + Runtime Order Audit

**Created:** 2026-02-25
**Status:** Ready for Atlas Execution

## Summary

Steam leaderboard’ları iki farklı yolla güncellenir: (1) İstemci SDK (`ISteamUserStats::UploadLeaderboardScore`) veya (2) Publisher Web API (`ISteamLeaderboards/SetLeaderboardScore`). Repoda `result=8` hatası pratikte `k_EResultInvalidParam` olup en kritik kök neden, Web API tarafında `scoremethod` parametresinin dokümana aykırı şekilde **int** gönderilmesidir (doğrusu: `"KeepBest"` / `"ForceUpdate"`).

Bu plan; Steam dokümanlarının beklediği runtime sırasını projedeki akışla eşleyip, (a) build sonrası SDK yazımının güvenilir şekilde çalışmasını ve (b) Web API/proxy yolunun parametre ve güvenlik açısından doğru olmasını sağlar.

## Context & Analysis

### Steam Dokümanı: Leaderboard’lar nasıl çalışır?

**SDK yolu (istemci):**
1. Steam’i başlat: `SteamAPI_Init()` / `SteamAPI_InitFlat()`.
2. (Önerilen/fiilen gerekli) `ISteamUserStats::RequestCurrentStats()` çağır.
3. Leaderboard handle bul: `FindLeaderboard(name)` veya `FindOrCreateLeaderboard`.
4. Skor yaz: `UploadLeaderboardScore(handle, KeepBest|ForceUpdate, score, details)`.
5. Bu async çağrıların sonuçlarını almak için düzenli `SteamAPI_RunCallbacks()` çalıştır.

**Web API yolu (server-side):**
- `ISteamLeaderboards/SetLeaderboardScore/v1/` ile skor yazılır.
- Parametreler kritik:
  - `appid` + `leaderboardid` + `steamid` + `score` + `scoremethod`.
  - `scoremethod` **string**: `KeepBest` veya `ForceUpdate`.
- Publisher key gerektirir ve dokümanda açıkça “asla istemciden çağrılmamalı” denir.

### Projede mevcut durum

**Yazma (SDK + fallback):**
- `src/steam_integration.py`
  - `init()` Steam API + interface pointer’ları alıyor, callback pump thread başlatıyor, `RequestCurrentStats` yolluyor.
  - `submit_score(mode, score)` async worker ile:
    - SDK: `FindLeaderboard` → `UploadLeaderboardScore` → `GetAPICallResult`.
    - Fallback (flag ile): Publisher Web API `SetLeaderboardScore`.

**Skor gönderiminin tetiklendiği yer:**
- `src/game.py` içinde `Game.finalize_run()` → `steam_integration.submit_score(self.game_mode, self.board.score)`.

**Okuma (proxy/direct Web API):**
- `src/steam_leaderboards.py` + `backend/steam_leaderboard_proxy.py` sadece leaderboard okuma ve friends auth için proxy sağlıyor.
- Proxy’de **write endpoint’i yok** (eksik parça).

### Kök sorunlar / eksikler

1. **`result=8` (InvalidParam) yanlış parametre:**
   - `src/steam_integration.py::_submit_score_via_partner_api` `scoremethod`’u `0/1` (int) gönderiyor.
   - Steam Web API dokümanı `scoremethod`’un **string** olmasını şart koşuyor: `KeepBest` / `ForceUpdate`.
   - Bu tek başına `result=8` üretir.

2. **Test/diagnostic script’leri de aynı hatayı pekiştiriyor:**
   - `test_lb_write.py` Web API çağrısında `scoremethod=1` (int) kullanıyor.
   - Bu nedenle “rc=8 = lisans yok” teşhisi yanlış pozitif olabilir.

3. **Proxy (backend) yazma yok:**
   - Güvenli mimari hedeflenmiş (publisher key backend’de), ama `SetLeaderboardScore` endpoint’i implement edilmemiş.

4. **Build sonrası Steam DLL ve AppID riski:**
   - Windows: `tetris.spec` DLL’i embed ediyor; `tetris_playtest.spec` ise `binaries=[]` (Steam DLL yok → init fail).
   - `steam_appid.txt` spec’lerde data olarak ekleniyor; Steam dokümanı upload build’lerinde bunu kaldırmayı öneriyor.

5. **Runtime sırası görünür değil:**
   - Başarısızlık durumunda (handle yok, upload success=0, WebAPI result!=1) hangi adımın kırıldığı net log’lanmıyor.

## Implementation Phases

### Phase 1: `result=8` Web API parametrelerini düzelt

**Objective:** Web API `SetLeaderboardScore` çağrısında InvalidParam (8) üreten parametre hatasını gider.

**Files to Modify:**
- `src/steam_integration.py`
- `test_lb_write.py`
- (Opsiyonel) `docs/STEAM_LEADERBOARD_OPERATIONS_TR.md` (incident açıklamasını düzelt / netleştir)

**Steps:**
1. `src/steam_integration.py::_submit_score_via_partner_api` içinde:
   - `scoremethod` parametresini int yerine string gönder:
     - KeepBest: `"KeepBest"`
     - ForceUpdate: `"ForceUpdate"`
2. Aynı değişikliği `test_lb_write.py` Web API post’unda uygula.
3. Log çıktılarında `result=8` durumunu “InvalidParam” olarak açıkla; ayrıca muhtemel sebepler:
   - Yanlış parametre tipi (bu fix),
   - Yanlış `leaderboardid` (app değişti / id drift),
   - Yanlış `appid`.

**Tests to Update/Add:**
- Mevcut unit testler Web API call’u mock’lamıyor; en azından:
  - `test_partner_fallback_enabled.py` / yeni bir test: Web API payload’ında `scoremethod` string mi kontrol et (requests/urllib mock).

**Acceptance Criteria:**
- [ ] Web API yolunda `result=8` (InvalidParam) parametre hatası nedeniyle alınmıyor.
- [ ] `tools/steam_set_test_score.py` ile aynı parametre formatı kullanılıyor.

---

### Phase 2: Leaderboard ID’yi statik map yerine dinamik çöz (Web API yazım yolu için)

**Objective:** `leaderboardid` drift ettiğinde InvalidParam riskini düşür.

**Files to Modify:**
- `src/steam_integration.py` (fallback yolu kalacaksa)
- Alternatif/tercih: `backend/steam_leaderboard_proxy.py` (write endpoint Phase 4)

**Steps:**
1. Web API ile `GetLeaderboardsForGame/v2` ve/veya `FindLeaderboard/v1` kullanarak `leaderboardid`’yi isimden çöz.
2. Cache’le (name → id), timeout/exception durumunda anlamlı hata ver.
3. `_LB_NAME_TO_ID` hardcode map’i:
   - ya kaldır,
   - ya da “son çare” fallback olarak tut.

**Acceptance Criteria:**
- [ ] Leaderboard yeniden oluşturulsa bile code değişmeden doğru `leaderboardid` bulunabiliyor.

---

### Phase 3: Build (exe/app) sonrası Steam DLL + AppID/steam_appid.txt politikasını netleştir

**Objective:** Steam SDK init ve leaderboard yazımı build’lerde deterministik olsun.

**Files to Modify:**
- `tetris_playtest.spec`
- (Gerekirse) diğer `.spec` dosyaları
- `src/steam_integration.py` (AppID injection davranışı)

**Steps:**
1. Windows Playtest build’i gerçekten Steam feature’larını kullanacaksa:
   - `tetris_playtest.spec` içine `dll/win64/steam_api64.dll` binaries ekle (tetris.spec ile aynı yaklaşım).
2. `steam_appid.txt` için iki mod:
   - **Dev mode:** dosya/env var ile AppID set edilebilir.
   - **Steam dağıtım:** mümkünse `steam_appid.txt` depoya konmasın; Steam client AppID’yi sağlar.
3. `src/steam_integration.py::init()` içinde:
   - `SteamAppId` env set + exe yanına `steam_appid.txt` yazma davranışını “sadece dev” moduna kısıtla.
   - Steam üzerinden çalışıyorsa AppID override etme.

**Acceptance Criteria:**
- [ ] Steam’den kurulu build’de `steam_api64.dll` bulunuyor ve init OK.
- [ ] AppID override edilmediği doğrulanıyor (log: runtime AppID).

---

### Phase 4 (Önerilen Mimari): Güvenli server-side write endpoint ekle (Trusted Writes veya anti-cheat için)

**Objective:** Publisher key istemcide olmadan skor yazabil.

**Files to Modify/Create:**
- `backend/steam_leaderboard_proxy.py`
- `src/steam_leaderboards.py`
- `src/game.py` (veya skor kaydının yapıldığı yer)

**Design:**
- `POST /api/v1/leaderboards/<mode>/submit`
  - Body: `{ "ticket": "<hex>", "score": 12345, "scoremethod": "KeepBest" }`
  - Backend:
    1) `AuthenticateUserTicket` ile ticket doğrula → steamid elde et
    2) mode → leaderboard name → leaderboardid resolve
    3) `SetLeaderboardScore` çağır (`scoremethod` string)
    4) response result=1 ise OK

**Steps:**
1. `SteamDirectGateway` içine `set_score(...)` ekle.
2. Yeni endpoint’i implement et; client token + rate limit zaten var.
3. `SteamLeaderboardService` içine `submit_score(...)` metodu ekle.
4. `Game.finalize_run()` içinde:
   - Steam SDK available ise ticket al
   - backend URL configured ise write’i proxy’ye gönder
   - Aksi halde mevcut SDK upload yolunu kullan (policy’ye göre).

**Tests to Write:**
- `test_lb_write_proxy.py` (yeni): Flask test client ile endpoint’in:
  - Ticket doğrulama OK → SetLeaderboardScore çağrısı doğru params ile yapılmış mı (requests mock)
  - `scoremethod` string mi
  - `result != 1` durumunda hata dönüyor mu

**Acceptance Criteria:**
- [ ] Publisher key istemci build’inde yok.
- [ ] Trusted write açık olsa bile skor yazımı çalışıyor.

## Open Questions

1. Steamworks portal’da ilgili leaderboard’lar `onlytrustedwrites` açık mı?
   - **Option A (false):** SDK client yazımı kullan (kolay, ama cheating riski).
   - **Option B (true):** Phase 4 (proxy write) zorunlu.
   - **Recommendation:** Eğer hile/rekabet önemliyse Option B.

2. Hangi build spec ile Steam’e yükleniyor (Windows için `tetris.spec` mi `tetris_playtest.spec` mi)?
   - `tetris_playtest.spec` şu an Steam DLL’i taşımıyor; bu durumda Steam init ve leaderboard yazımı beklenmez.

## Risks & Mitigation

- **Risk:** `steam_appid.txt`/env override, Steam tarafından sağlanan AppID’yi bozup yanlış AppID’ye yazmaya çalışır.
  - **Mitigation:** Override’ı dev modla sınırla; runtime AppID’yi logla.

- **Risk:** Publisher key’in istemciye sızması.
  - **Mitigation:** Key’i yalnız backend env’de tut; istemci fallback’i kaldır veya sadece dev flag’le aç.

## Success Criteria

- [ ] Steam build (exe + macOS app) oyun içinde run bittiğinde skor Steam leaderboard’a yazılıyor.
- [ ] Web API yolunda `result=8` InvalidParam parametre hatası çözülmüş.
- [ ] Unit/integration testler geçiyor (özellikle yeni write path ve param doğruluğu).

## Notes for Atlas

- Steam Web API dokümanı: `ISteamLeaderboards/SetLeaderboardScore` için `scoremethod` **string** olmak zorunda.
- Repo içi referans: `tools/steam_set_test_score.py` doğru parametre formatını zaten kullanıyor; bunu “altın örnek” kabul edin.
- Projede iki paralel yaklaşım var: `src/steam_integration.py` (SDK) ve `backend/steam_leaderboard_proxy.py` (Web API okuma). Yazma için proxy’nin genişletilmesi en güvenli uzun vadeli çözüm.
