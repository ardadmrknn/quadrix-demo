# Plan: Steam Leaderboard Yazma Yetkisi ve Playtest Lisans Rollout

**Created:** 25 Şubat 2026
**Status:** Ready for Atlas Execution

## Summary

Ana sorun teknik olarak koddan çok Steam lisans sahipliği: leaderboard yazma çağrıları, hesabın AppID için geçerli lisansı yoksa başarısız oluyor (`result=8`). Mevcut projede `src/steam_integration.py` içinde SDK + Partner API fallback var; bu sadece geliştirici doğrulaması için yardımcı, üretimde tüm oyuncular için kalıcı çözüm değil. Kalıcı çözüm, playtest/paket dağıtımıyla oyunculara gerçek AppID lisansı verilmesi ve istemci tarafında lisans durumunu doğru teşhis eden bir akış kurulmasıdır. Plan; Steamworks operasyonlarını, istemci teşhislerini, backend güvenlik sınırlarını ve doğrulama matrisini birlikte uygular.

## Context & Analysis

**Relevant Files:**
- `src/steam_integration.py`: SDK init, leaderboard submit, Partner API fallback; lisans hatası teşhis mesajları burada.
- `src/steam_leaderboards.py`: İstemci-proxy katmanı; doğrudan Steam Web API ve backend modları birlikte var.
- `backend/steam_leaderboard_proxy.py`: Publisher key’i backend’de tutan güvenli proxy; auth/rate-limit kalıpları mevcut.
- `docs/SECURITY_REVIEW_STEAM_LEADERBOARD_TR.md`: Güvenlik modeli ve üretim önerileri (key izolasyonu, token, rate-limit).
- `steamworks/scripts/app_build_playtest.vdf`: Build dağıtım kanalının operasyonel metadata noktası.
- `test_lb_write.py`: SDK/Partner API davranışını hızlı doğrulayan tanı scripti.

**Key Functions/Classes:**
- `submit_score` in `src/steam_integration.py`: Önce SDK, sonra Partner API fallback deniyor.
- `_submit_score_via_partner_api` in `src/steam_integration.py`: Publisher key ile `SetLeaderboardScore` çağrısı.
- `SteamLeaderboardService` in `src/steam_leaderboards.py`: Oyun içi leaderboard servis katmanı.
- `SteamDirectGateway` in `backend/steam_leaderboard_proxy.py`: Server-side Steam Web API erişimi.

**Dependencies:**
- Steamworks SDK (DLL/flat API): client-side leaderboard upload/read.
- Steam Partner Portal (Packages/Playtest/Keys): lisans dağıtımı ve leaderboard yapılandırması.
- Steam Partner Web API: backend/proxy veya debug amaçlı yönetim çağrıları.
- Flask + requests (backend proxy): güvenli aracılık.

**Patterns & Conventions:**
- Projede “graceful fallback” yaklaşımı var; Steam yoksa oyun çalışmaya devam ediyor.
- Güvenlikte key izolasyonu prensibi benimsenmiş (publisher key backend’de kalmalı).
- Mod→leaderboard adı eşlemeleri hem istemci hem backend’de merkezi sözlüklerle yönetiliyor.

## Implementation Phases

### Phase 1: Steamworks Lisans Modelini Düzelt (Operasyonel Kök Neden)

**Objective:** Playtest oyuncularının AppID lisansı almasını sağlayıp leaderboard yazma engelini kaynaktan kaldırmak.

**Files to Modify/Create:**
- `docs/STEAM_PLAYTEST_LICENSE_RUNBOOK_TR.md` (create): Paket/erişim adımlarının operasyonel runbook’u.
- `docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md` (update): “write fail result=8” için lisans teşhis bölümü.

**Tests to Write:**
- `test_lb_write.py` kullanım senaryosu dokümante edilir (kod testi değil, runbook doğrulaması).
- QA checklist: “lisanslı hesapta SDK upload success=1” kabul testi.

**Steps:**
1. Runbook’a test senaryolarını yaz (lisanslı hesap / lisanssız hesap).
2. Lisanssız hesapla `test_lb_write.py` çalıştır; başarısızlık beklenir (red).
3. Steam Partner Portal’da Playtest key/Developer Comp ile lisans ata.
4. Aynı hesapla tekrar çalıştır; SDK başarı beklenir (green).
5. Dokümantasyonu net hata kodlarıyla finalize et.

**Acceptance Criteria:**
- [ ] Playtest erişimi olan QA hesabı AppID lisansı aldıktan sonra SDK yazımı başarılı.
- [ ] `result=8` için operasyonel çözüm adımı dokümante edildi.
- [ ] Geliştirici ve QA ekipleri aynı runbook ile problemi yeniden üretebiliyor/çözebiliyor.
- [ ] All tests pass
- [ ] Code follows project conventions

---

### Phase 2: İstemciye Lisans/Yetki Teşhis Katmanı Ekle

**Objective:** Oyuncuya ve loglara “neden yazılamadı” bilgisini net vermek; sessiz başarısızlıkları azaltmak.

**Files to Modify/Create:**
- `src/steam_integration.py`: SteamApps arayüzü eklenerek lisans kontrol yardımcıları (`is_app_owned`/benzeri) ve hataya göre sınıflandırma.
- `src/localization.py`: Yeni kullanıcı mesaj anahtarları (lisans yok, Steam kapalı, servis geçici hata).
- `src/menu.py` (veya leaderboard UI’nin tetiklendiği ekran): kullanıcıya kısa, aksiyonlu mesaj gösterimi.

**Tests to Write:**
- `test_steam_integration_license_status.py` (new): lisans kontrol fonksiyonlarının mocked DLL ile davranışı.
- `test_steam_submit_diagnostics.py` (new): `submit_score` sonucu için hata sınıflandırma/log metni.

**Steps:**
1. Mock testlerle lisanslı/lisanssız/Steam-yok durumlarını tanımla (red).
2. `steam_integration` içinde SteamApps accessor + ownership helper ekle.
3. `submit_score` içinde başarısızlıkta tanı çıktısını standardize et.
4. Testleri çalıştır; tüm branch’ler geçsin (green).
5. UI mesaj anahtarlarını localization ile bağla.

**Acceptance Criteria:**
- [ ] İstemci logunda başarısızlığın kaynağı (lisans/bağlantı/SDK) ayrışıyor.
- [ ] Kullanıcıya “Steam hesabında oyunun lisansı yok” mesajı gösterilebiliyor.
- [ ] Yeni birim testleri geçiyor.
- [ ] All tests pass
- [ ] Code follows project conventions

---

### Phase 3: Partner API Fallback’i Üretim Politikasıyla Sınırla

**Objective:** Publisher key tabanlı yazma yolunun üretimde yanlış kullanımını engellemek, sadece debug/operasyonel kurtarma amacıyla tutmak.

**Files to Modify/Create:**
- `src/steam_integration.py`: Partner API fallback’i feature flag ile koşullandır (`STEAM_PARTNER_WRITE_FALLBACK=1` gibi).
- `src/settings_manager.py` veya mevcut config noktası: fallback’in default kapalı olması.
- `docs/guides/README_TR.md` (update): fallback’in yalnızca debug/staff hesapları için olduğu notu.

**Tests to Write:**
- `test_partner_fallback_flag.py` (new): flag kapalıyken fallback çağrılmamalı.
- `test_partner_fallback_enabled.py` (new): flag açıkken beklenen akış çalışmalı (mock HTTP).

**Steps:**
1. Flag davranışını testlerle tanımla (red).
2. `submit_score` içinde fallback kararını config tabanlı hale getir.
3. Varsayılanı kapalı yap; mevcut debug script uyumluluğunu koru.
4. Testleri çalıştır; regressions yok (green).
5. README’ye üretim politikası ekle.

**Acceptance Criteria:**
- [ ] Üretim build’lerinde Partner API write fallback default kapalı.
- [ ] Debug build’de explicit flag ile fallback aktif edilebiliyor.
- [ ] Publisher key’in istemci kullanım alanı daraltıldı.
- [ ] All tests pass
- [ ] Code follows project conventions

---

### Phase 4: Backend Yardımcı Servisleri ve Dış Etkenler Entegrasyonu

**Objective:** Dış bağımlılıkları (Steamworks panel, backend, QA hesapları) proses haline getirip sürdürülebilir işletim sağlamak.

**Files to Modify/Create:**
- `docs/STEAM_LEADERBOARD_OPERATIONS_TR.md` (create): rol bazlı sorumluluk matrisi.
- `backend/steam_leaderboard_proxy.py` (optional update): write endpoint gerekiyorsa sadece servis-account whitelist + audit log ile.
- `.env.example` (backend varsa): gerekli env değişkenleri (app id, key, session secret).

**Tests to Write:**
- Backend integration smoke test (script/tabanlı): auth + read endpoint.
- Rate-limit doğrulama testi (tekrarlı çağrıda 429 benzeri beklenen davranış).

**Steps:**
1. Ekip rollerini netleştir: Steamworks admin, backend ops, QA owner.
2. Proxy konfigürasyonlarını prod/stage için ayır.
3. Gerekirse write endpoint’e sıkı yetki politikası ekle.
4. Operasyon dokümanına incident akışı (result=8, 401, timeout) ekle.
5. Smoke test prosedürünü release checklist’e bağla.

**Acceptance Criteria:**
- [ ] Dış bağımlılıklar kişi-bağımlı olmaktan çıktı; dokümante süreç oluştu.
- [ ] Backend güvenlik kontrolleri (token, rate-limit, secret hygiene) üretimde uygulanıyor.
- [ ] Release öncesi leaderboard smoke checklist’i çalıştırılıyor.
- [ ] All tests pass
- [ ] Code follows project conventions

---

### Phase 5: Release Doğrulama Matrisi ve Canlı Geçiş

**Objective:** “her oyuncu için çalışır” seviyesinde canlı geçiş güveni oluşturmak.

**Files to Modify/Create:**
- `docs/LEADERBOARD_RELEASE_CHECKLIST_TR.md` (create): hesap/kanal bazlı test matrisi.
- `plans/` altındaki bu planın yanına kısa execution log dosyası (Atlas tarafından).

**Tests to Write:**
- Senaryo A: Lisanslı playtest oyuncusu → SDK write başarılı.
- Senaryo B: Lisanssız hesap → kullanıcıya net lisans mesajı, crash yok.
- Senaryo C: Steam kapalı/offline → graceful degradation.
- Senaryo D: Backend geçici erişilemiyor → retry/log, oyunda blokaj yok.

**Steps:**
1. Test matrisini hesap tiplerine göre oluştur (dev, QA, gerçek playtester).
2. Her senaryoyu canlı build’de uygula ve logları topla.
3. Hata sınıflandırmalarını release note’a işle.
4. Gerekirse hotfix adımı için rollback koşulunu tanımla.
5. Canlıya geçiş onayı ver.

**Acceptance Criteria:**
- [ ] Lisanslı oyuncu akışında leaderboard yazımı stabil.
- [ ] Lisanssız oyuncuda anlaşılır hata/rehber mesajı var.
- [ ] Crash veya sessiz veri kaybı yok.
- [ ] All tests pass
- [ ] Code follows project conventions

## Open Questions

1. Partner API write fallback üretimde açık kalmalı mı?
   - **Option A:** Tamamen kapat (sadece SDK write).
     - Artı: Güvenlik ve veri bütünlüğü daha temiz.
     - Eksi: Lisans/SDK edge-case’lerinde kurtarma yolu azalır.
   - **Option B:** Feature flag ile yalnızca debug/staff build’de açık tut.
     - Artı: Sorun anında kontrollü teşhis ve geçici telafi sağlar.
     - Eksi: Yanlış konfigürasyon riski yönetilmezse üretime sızabilir.
   - **Recommendation:** Option B (default OFF, sadece kontrollü ortamlarda ON).

2. Playtest erişimi nasıl dağıtılmalı?
   - **Option A:** Sadece request queue onayı.
     - Eksi: Bazı hesaplarda lisansın fiilen oluşmaması/denetlenememesi.
   - **Option B:** QA ve kritik tester’lara doğrudan key/package ataması.
     - Artı: Lisans deterministik, test tekrar edilebilir.
   - **Recommendation:** Option B’yi çekirdek test grubu için zorunlu, A’yı geniş topluluk için ikincil kullan.

3. Leaderboard write yetkisi backend’e taşınmalı mı?
   - **Option A:** Client SDK write tek kaynak.
     - Artı: Steam’in doğal sahiplik modeline en uygun.
   - **Option B:** Backend write endpoint (strict auth + audit) ekle.
     - Artı: Operasyonel kurtarma güçlü.
     - Eksi: Güvenlik yüzeyi ve kötüye kullanım riski artar.
   - **Recommendation:** Varsayılan Option A; Option B sadece operasyonel acil durum için sınırlı.

## Risks & Mitigation

- **Risk:** Steamworks panelinde yanlış package/branch ayarı nedeniyle lisanssız kullanıcılar devam eder.
  - **Mitigation:** Release öncesi package-owner kontrol checklist’i ve 2 kişi onayı.

- **Risk:** Publisher key’in istemciye sızması.
  - **Mitigation:** Key yalnız backend `.env` içinde; istemci fallback varsayılan kapalı.

- **Risk:** Hata kodları kullanıcıya anlaşılmaz yansır, destek yükü artar.
  - **Mitigation:** Lokalize, aksiyon odaklı hata mesajları + tek satır çözüm yönlendirmesi.

- **Risk:** Çoklu ortamda rate-limit yetersiz kalır.
  - **Mitigation:** Reverse proxy/WAF ile global limit ve merkezi logging.

## Success Criteria

- [ ] Playtest lisanslı hesaplarda SDK üzerinden leaderboard yazımı sürekli başarılı.
- [ ] Lisanssız hesaplarda deterministik hata teşhisi ve kullanıcı yönlendirmesi mevcut.
- [ ] Partner API write fallback üretimde default kapalı ve kontrollü.
- [ ] Operasyon runbook’ları (lisans dağıtımı, incident, release checklist) tamamlandı.
- [ ] All phases complete with passing tests
- [ ] Code reviewed and approved

## Notes for Atlas

- Bu görevde kök neden koddan ziyade Steam lisans dağıtımı; Phase 1 operasyonel adımlar olmadan yalnız kod değişikliği yeterli olmaz.
- `result=8` durumu “parametre hatası” gibi görünse de pratikte sahiplik/lisans eksikliği olarak ele alınmalı.
- Kod değişikliklerinde minimum invaziv yaklaşım tercih et: mevcut `submit_score` akışını bozma, yalnız tanı ve policy gate ekle.
- Testleri önce dar kapsamda (`steam_integration` unit/mock), sonra canlı smoke (`test_lb_write.py`) ile genişlet.
