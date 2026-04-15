# Plan: Online Co-op V1 Production Hardening ve Akış Tamamlama

**Created:** 2026-04-15
**Status:** Ready for Atlas Execution

## Summary

Bu plan, mevcut yerel co-op temelini (`src/coop_game.py`) ve temeli atılmış online co-op katmanını (`src/online_coop_game.py`) alıp, bunu Online PvP ile aynı güvenilirlik barına taşıyacak sertleştirme ve tamamlama işlerini tanımlar. Hedef, **2 oyunculu endless online co-op akışının** lobi oluşturma/katılma, ready-check, countdown, maç, pause, disconnect, rematch ve menüye dönüş zincirinde takılmadan çalışmasıdır.

Ana yaklaşım şudur:

- Mimari **authoritative host** olarak kalacak.
- İlk yayın hedefi **endless online co-op** olacak; online campaign bu planın dışındadır.
- İlk turda mümkün olduğunca **Python katmanında**, özellikle `src/online_coop_game.py` içinde sertleştirme yapılacak.
- Online PvP'de çözülmüş lobby/session/focus-loss/test desenleri yeniden kullanılacak.
- Ortak base-class refactor'u, online co-op akışı yayın kalitesine gelmeden başlatılmayacak.

## Context & Analysis

**Relevant Files:**

- `src/online_coop_game.py`: Online co-op state machine, lobby shell, host authoritative gameplay köprüsü, guest render, cleanup
- `src/coop_game.py`: Yerel co-op oynanışı, `inject_remote_input()`, freeze/game-over mantığı, event emitter, ayar tabanlı kontrol çözümleme
- `src/coop_board.py`: Ortak 20x20 board ve owner/freeze davranışları
- `src/steam_networking.py`: Steam lobby/P2P wrapper, co-op mesaj tipleri, lobby code üretimi
- `src/online_pvp_game.py`: Kanıtlanmış online akış, lobby metadata sertleştirmesi, session bootstrap, disconnect/focus-loss/test desenleri
- `src/main.py`: Online co-op state handler ve cleanup yolları
- `tests/test_cross_platform_lobby_metadata.py`: Online co-op metadata formatı için mevcut güvence
- `docs/ONLINE_COOP_ANALIZ_VE_MIMARI.md`: Erken mimari analiz
- `docs/ONLINE_COOP_UYGULAMA_SIRASI_VE_FAZLARI.md`: İlk fazlama taslağı

**Mevcut Güçlü Taraflar:**

- `OnlineCoopGame` zaten `LOBBY_MENU -> WAITING -> READY_CHECK -> COUNTDOWN -> PLAYING -> GAME_OVER/DISCONNECTED` state zincirine sahip.
- Host tarafı gerçek `CoopGame` instance'ı çalıştırıyor; guest tarafı input gönderip host state'ini render ediyor.
- `CoopGame.inject_remote_input()` mevcut; bu, online co-op için en kritik local gameplay köprüsünü hazır veriyor.
- Host tarafı board ve piece snapshot yayınlıyor; guest tarafında temel board/piece/HUD görünümü var.
- Lobi metadata yazımı `requires_code='1'/'0'` ve `metadata_ready='0'/'1'` formatıyla mevcut cross-platform testlerle uyumlu.
- Rematch, basic disconnect grace ve cleanup iskeleti zaten atılmış durumda.

**Doğrulanmış Bloklayıcı Boşluklar:**

- `OnlineCoopGame._on_lobby_data_updated()` boş; lobby metadata propagasyonu, unknown/stale lobby güncellemesi ve joined-lobby revalidation yok.
- `OnlineCoopGame._on_session_accepted()` ve `_on_session_rejected()` boş; PvP'deki session bootstrap ve retry zinciri yok.
- Kod ile katılım akışı, lobby listesinde basit `lobby_code` eşleşmesine dayanıyor; ambiguity yönetimi, worldwide fallback, target-lobby doğrulaması ve private access validation yok.
- WAITING -> READY_CHECK geçişi sadece event'e bağlı; PvP'deki `get_lobby_members()` fallback'i yok.
- Board/piece snapshot payload'larında sequence/timestamp yok; guest tarafı gelen state'i sıraya bakmadan overwrite ediyor.
- Guest input için `seq` ve host tarafında `input_ack` alanı var, ama guest bu ack'i kullanmıyor; pending input/backlog/connection-degrade davranışı tamamlanmamış.
- Pause akışı toggle tabanlı; guest `pause_request` gönderiyor ama authoritative pause-state sequence'i yok. Aynı anda iki taraftan pause/resume yarışına açık.
- Online co-op, local co-op'un ayar tabanlı binding sistemini kullanmıyor; `_HOST_KEYS` ve `_GUEST_KEYS` sabit haritalarına gömülü.
- Online co-op'ta focus-loss auto-pause ve gamepad katmanı yok; Online PvP'de ikisi de mevcut.
- Guest render, local co-op parity seviyesinde değil; doğru ama sade bir placeholder çizim katmanı.
- Online co-op için metadata testi dışında özel test suite yok; PvP tarafında bulunan lobby/session/pause/disconnect/message validation test paritesi yok.

**V1 Non-Goals:**

- Online campaign
- Process restart sonrası reconnect
- Spectator
- 3+ oyuncu
- Ortak base-class refactor'u
- İlk turda C++ bridge refactor'u

## Release Target

Bu plan tamamlandığında aşağıdaki davranışlar yayın öncesi zorunlu kabul edilir:

- Oyuncu iki makinede private code join, public lobby join ve Steam invite ile maça girebilir.
- Ready-check yalnızca peer gerçekten erişilebilir ve session bootstrap tamamlanmışsa countdown başlatır.
- Host ve guest bütün maç boyunca takılmadan oynar; eski snapshot, stale lobby data veya yanlış pause toggle nedeniyle softlock oluşmaz.
- Focus loss, disconnect ve reconnect akışları deterministic olur.
- Rematch zinciri çoklu tekrar denemelerinde state sızıntısı üretmez.
- Rebind edilmiş kontroller online co-op'ta da geçerli olur.
- Guest görünümü, local co-op ile davranışsal olarak tutarlı ve bilgi kaybettirmeyen seviyeye gelir.
- Online co-op için PvP'ye benzer otomatik test yüzü oluşur.

## Direct Reuse Targets

Online co-op için sıfırdan yeni desen üretmek yerine, aşağıdaki Online PvP yapılarını hedefli biçimde taşı:

- `src/online_pvp_game.py` içindeki `_normalize_lobby_visibility()`
- `src/online_pvp_game.py` içindeki `_resolve_private_lobby_code()`
- `src/online_pvp_game.py` içindeki `_get_lobby_metadata_snapshot()`
- `src/online_pvp_game.py` içindeki `_validate_joined_lobby_access()`
- `src/online_pvp_game.py` içindeki `_find_lobby_match_by_code()` ve retry/fallback mantığı
- `src/online_pvp_game.py` içindeki `_promote_to_ready_check()` kalıbı
- `src/online_pvp_game.py` içindeki `_send_session_ping()` ve session accepted/rejected akışı
- `src/online_pvp_game.py` içindeki `_is_focus_loss_event()` ve `_pause_for_focus_loss()` kalıbı
- Online PvP test dosyalarının adlandırma ve kapsam deseni

## Implementation Phases

### Phase 0: Scope Kilidi ve Protokol Temizliği

**Objective:** Online co-op V1 için tek bir sözleşme belirlemek ve yarım kalmış protokol parçalarını netleştirmek.

**Files to Modify/Create:**

- `docs/ONLINE_COOP_ANALIZ_VE_MIMARI.md` veya yeni kısa protocol eki
- `src/online_coop_game.py`
- `src/steam_networking.py`

**What to decide/fix first:**

1. V1 kapsamını resmi olarak `endless only` şeklinde kilitle.
2. `GAME_START` ile `COOP_GAME_START` mesaj tiplerinden hangisinin gerçek source of truth olacağını seç; kullanılmayan tip kalmasın.
3. Her mesaj için reliability ve payload sözleşmesini sabitle:
   - lobby/control
   - ready/session
   - board snapshot
   - piece snapshot
   - pause state
   - rematch/game over
4. Guest tarafında local simulation yapılmayacağını, yalnızca host-authoritative state gösterileceğini açıkça koru.

**Acceptance Criteria:**

- [ ] Online co-op mesaj isimleri ve payload alanları tek bir sözleşmeye bağlanmış olur.
- [ ] Kullanılmayan veya belirsiz co-op mesaj tipleri temizlenir ya da gerekçeli biçimde korunur.
- [ ] Online campaign bu plandan açıkça ayrılır.

---

### Phase 1: Lobby Discovery, Code Join ve Access Validation Sertleştirmesi

**Objective:** Online co-op lobby zincirini, Online PvP düzeyinde güvenilir ve cross-platform toleranslı hale getirmek.

**Files to Modify/Create:**

- `src/online_coop_game.py`
- Gerekirse `src/steam_networking.py`
- `tests/test_online_coop_lobby_visibility_metadata.py`
- `tests/test_online_coop_code_search_validation.py`
- `tests/test_online_coop_lobby_presence_fallback.py`

**Work Items:**

1. PvP'deki lobby metadata normalization katmanını co-op'a taşı:
   - unknown visibility
   - stale unknown
   - metadata_ready gecikmesi
   - live-read fallback
2. `_on_lobby_data_updated()` içini gerçek işlevle doldur:
   - cached lobby snapshot refresh
   - deferred entry promotion
   - pending code join çözümü
   - joined lobby access revalidation
3. `_on_lobby_list_complete()` akışını basit exact-match'ten çıkar:
   - ambiguous code match tespiti
   - worldwide full-scan fallback
   - target lobby doğrulaması
   - no-result ve pending-metadata ayrımı
4. Private lobby erişim kontrolü ekle:
   - `remember_private_join_authorization`
   - invite/code auth memo
   - `_validate_joined_lobby_access()`
5. WAITING -> READY_CHECK için sadece event'e güvenme; `get_lobby_members()` tabanlı fallback ekle.
6. Cross-platform propagation gecikmelerinde private lobi kartının tamamen kaybolmasını engelle.

**Acceptance Criteria:**

- [ ] Public browse, private code join ve invite join senaryoları aynı akış içinde çalışır.
- [ ] Metadata gecikmesi lobby'yi yanlışlıkla public göstermez.
- [ ] Aynı koda birden fazla lobby düşerse kullanıcı yanlış lobby'ye otomatik atılmaz.
- [ ] Yetkisiz private join sonradan reject edilir; host kendi lobi akışında self-reject yaşamaz.

---

### Phase 2: Session Bootstrap, Ready-Check ve Countdown Güvenliği

**Objective:** İki oyuncu birbirini gerçekten görene kadar maç başlatılmamasını sağlamak.

**Files to Modify/Create:**

- `src/online_coop_game.py`
- Gerekirse `src/steam_networking.py`
- `tests/test_online_coop_game_start_retry.py`
- `tests/test_online_coop_ready_sender_rebind.py` veya eşdeğer ready/session testi

**Work Items:**

1. PvP'deki session bootstrap alanlarını co-op'a ekle:
   - `_session_established`
   - `_session_ping_timer`
   - `_SESSION_PING_INTERVAL_MS`
   - backoff alanları
2. `_on_session_accepted()` ve `_on_session_rejected()` implement et.
3. READY_CHECK'e geçildiğinde session ping başlat; sırf lobby member event geldi diye maçı başlatma.
4. Countdown başlatma şartını `my_ready && opponent_ready && session_established` haline getir.
5. `game_start` mesajı kaçarsa retry veya pending-payload mantığı kur.
6. Reconnect sonrasında session yeniden kurulmadan pause kaldırma.

**Acceptance Criteria:**

- [ ] Hazır olan iki oyuncu arasında P2P oturumu kurulmadan countdown başlamaz.
- [ ] Session reject veya gecikme durumunda kullanıcı sessiz softlock yerine anlamlı state görür.
- [ ] Oyun başlangıcı, mixed-platform eşleşmelerde tek seferlik şansa bağlı kalmaz.

---

### Phase 3: Gameplay Sync Doğruluğu ve Mesaj Doğrulama

**Objective:** Host-authoritative modeli koruyup guest tarafında stale state, out-of-order snapshot ve yarım input akışını kapatmak.

**Files to Modify/Create:**

- `src/online_coop_game.py`
- `src/steam_networking.py`
- `tests/test_online_coop_message_validation.py`

**Work Items:**

1. `COOP_BOARD_STATE` ve `COOP_PIECE_STATE` payload'larına sequence ve gönderim zamanı ekle.
2. Guest tarafında son kabul edilen sequence'i tut; eski snapshot'ları düş.
3. Mevcut `input_ack` alanını gerçek davranışa bağla:
   - guest pending seq takip etsin
   - ack ilerlemiyorsa connection degradation UI üret
   - rematch/start sırasında ack state sıfırlansın
4. Gelen mesajlarda sender/type/payload doğrulaması ekle:
   - beklenmeyen sender ignore
   - tip dönüşümü ve clamp
   - eksik alanlara güvenli fallback
5. Pause/resume, game_over ve reconnect gibi state geçişlerinde periodic snapshot beklemek yerine zorunlu full snapshot yayınla.
6. Freeze/unfreeze bilgisini sadece periyodik board snapshot'a bırakma; state değişiminde reliable event veya zorunlu full snapshot ile anında taşı.
7. Broadcast interval optimizasyonunu correctness sonrası düşün; ilk hedef mevcut 100ms/50ms akışını güvenilir yapmak.

**Acceptance Criteria:**

- [ ] Guest tarafı eski snapshot nedeniyle geri zıplamaz.
- [ ] Bozuk payload veya yanlış sender oyunu bozmaz.
- [ ] Guest input akışı gözlenebilir hale gelir; ack tıkanması tanı koyulabilir olur.

---

### Phase 4: Pause, Focus Loss, Disconnect ve Reconnect Recovery

**Objective:** Online co-op'un en çok kullanıcıya görünen kırılma alanlarını deterministic hale getirmek.

**Files to Modify/Create:**

- `src/online_coop_game.py`
- `src/main.py`
- `tests/test_online_coop_pause_freezes_input.py`
- `tests/test_online_coop_disconnect_grace.py`
- `tests/test_online_coop_focus_loss_pause.py`

**Work Items:**

1. PvP'deki `_is_focus_loss_event()` ve `_pause_for_focus_loss()` desenini co-op'a taşı.
2. Toggle tabanlı pause davranışını authoritative pause-state mantığına çevir:
   - guest yalnızca request gönderir
   - host pause state'i değiştirir
   - host monotonic pause-state yayınlar
3. Reconnect sırasında `member_joined` gelince sadece grace timer'ı sıfırlama:
   - zorunlu board snapshot
   - zorunlu piece snapshot
   - zorunlu score/freeze/pause durumu senkronu
4. Disconnect grace süresinde host tarafı session ping/recovery denemesi yapsın; süre bitince deterministic fail state'e geçsin.
5. ESC/back_to_lobby/disconnected/game_over cleanup yollarını idempotent hale getir; `main.py` handler ile aynı beklentiye oturt.

**Acceptance Criteria:**

- [ ] Host veya guest alt-tab/minimize yaptığında online co-op güvenli pause davranışı gösterir.
- [ ] Aynı anda iki taraftan pause input'u gelirse yanlış resume oluşmaz.
- [ ] Reconnect eden oyuncu stale ekranla oyuna dönmez.

---

### Phase 5: Kontrol Sistemi, Gamepad ve Guest Görsel Paritesi

**Objective:** Online co-op'u sadece çalışan değil, gerçekten oynanabilir ve ayarlara sadık hale getirmek.

**Files to Modify/Create:**

- `src/online_coop_game.py`
- `src/coop_game.py` gerekiyorsa küçük event/presentation destekleri
- `src/localization.py`
- Gerekirse `src/gamepad_manager.py` entegrasyon noktaları
- `tests/test_online_coop_controls_rebind.py`

**Work Items:**

1. `_HOST_KEYS` ve `_GUEST_KEYS` sabitlerini kaldır ya da runtime binding katmanına bağla.
2. Online co-op input çözümlemesini local co-op ile aynı binding kaynağına bağla:
   - `settings_manager.get_controls()['pvp']['player1'/'player2']`
3. Online co-op için gamepad sentetik event zincirini ekle ya da açıkça scope dışı bırakma kararı al.
4. Guest render tarafını local co-op parity'ye yaklaştır:
   - next/hold bilgisi
   - freeze göstergeleri
   - daha doğru board görselleştirmesi
   - tema/blok stili tutarlılığı
   - status/pause/game-over ekranlarında aynı bilgi seviyesi
5. Lobby kartları ve shell ekranlarında PvP'deki loading/unknown/stale durum dilini yeniden kullan.

**Acceptance Criteria:**

- [ ] Rebind edilmiş kontroller online co-op'ta çalışır.
- [ ] Kullanıcı online co-op'a girince varsayılan tuşlara mecbur kalmaz.
- [ ] Guest görünümü local co-op'a göre bilgi kaybettirmez.

---

### Phase 6: Test Yüzü, Soak, Cross-Platform QA ve Release Gate

**Objective:** Online co-op'u “çalışıyor gibi görünüyor” seviyesinden çıkarıp yayın öncesi doğrulanmış hale getirmek.

**Files to Modify/Create:**

- `tests/test_online_coop_lobby_visibility_metadata.py`
- `tests/test_online_coop_code_search_validation.py`
- `tests/test_online_coop_lobby_presence_fallback.py`
- `tests/test_online_coop_message_validation.py`
- `tests/test_online_coop_game_start_retry.py`
- `tests/test_online_coop_disconnect_grace.py`
- `tests/test_online_coop_pause_freezes_input.py`
- `tests/test_online_coop_focus_loss_pause.py`
- `tests/test_online_coop_controls_rebind.py`
- Kısa QA runbook notu gerekiyorsa `docs/` altında ek belge

**Automated Coverage Target:**

- Lobby metadata propagation
- Code join validation ve ambiguous match
- Lobby presence fallback
- Ready/session bootstrap
- Message validation ve stale snapshot drop
- Pause input freezing
- Disconnect grace ve reconnect resync
- Focus-loss auto-pause
- Control rebind davranışı

**Manual QA Matrix:**

- Windows -> Windows
- Windows -> macOS
- macOS -> Windows
- Mümkünse macOS -> macOS

**Manual QA Scenarios:**

- Private lobby create/join by code
- Public browse/join
- Steam invite ile katılım
- Ready -> unready -> ready zinciri
- Countdown sırasında ayrılma
- Oyun sırasında host pause / guest pause request
- Host alt-tab / guest alt-tab
- Mid-game disconnect ve grace içinde geri gelme
- Grace süresi sonunda fail state
- Arka arkaya en az 10 rematch

**Release Gate:**

- [ ] Yeni online co-op test suite yeşil
- [ ] Mixed-platform özel lobi akışı doğrulandı
- [ ] Mixed-platform public browse akışı doğrulandı
- [ ] Disconnect/reconnect ve focus-loss senaryoları softlock üretmiyor
- [ ] Rematch zinciri state sızıntısı üretmiyor

---

### Phase 7: Conditional Bridge ve Paketleme Sertleştirmesi

**Objective:** Python tarafı parity tamamlandıktan sonra hâlâ mixed-platform veya build kaynaklı sorun varsa, en dar kapsamlı bridge/build düzeltmesini yapmak.

**Files to Modify/Create:**

- `steamworks/steam_net_bridge/steam_net_bridge.cpp` yalnızca veriyle gerekirse
- İlgili build script/spec dosyaları

**Work Items:**

1. Python hardening sonrası hâlâ metadata/session sorunu varsa, bridge-side atomic publication ve request akışını PvP öğrenimleriyle hizala.
2. Build artifact'lerin güncel olduğundan emin ol:
   - Windows bridge artifact
   - macOS bridge artifact
   - packaging tarafındaki stale artifact riskleri
3. C++ değişikliği yapılırsa sadece ölçülmüş soruna dönük minimal diff uygula.

**Acceptance Criteria:**

- [ ] Bridge değişikliği yapılacaksa, bunun Python katmanında çözülemeyen somut bir sebebi vardır.
- [ ] Build/paketleme zinciri mixed-platform QA öncesi güncel artifact kullanır.

## Risks & Mitigation

- **Risk:** Online co-op için PvP kodunu birebir kopyalarken co-op'a özgü akışlar kırılabilir.
  - **Mitigation:** Helper-level port yap; gameplay semantics'i kopyalama, lobby/session/focus-loss desenini kopyala.

- **Risk:** Erken refactor hevesi teslim tarihini uzatır.
  - **Mitigation:** İlk turda shared base çıkarma; parity sağlandıktan sonra refactor düşün.

- **Risk:** Guest render parity işi correctness işlerini gölgeler.
  - **Mitigation:** Önce lobby/session/sync/pause/disconnect doğruluğu, sonra görsel parity.

- **Risk:** Mixed-platform metadata propagation yine sorun çıkarabilir.
  - **Mitigation:** PvP'deki unknown/stale/deferred lobby yaklaşımını aynen taşı; gerekirse conditional bridge phase'e geç.

## Open Questions

1. V1'de online co-op gamepad desteği release-blocking mi?
   - **Recommendation:** Menüde mod açık kaldığı ve local co-op/gamepad desteği mevcut olduğu için evet, en azından temel parity sağlanmalı.

2. Guest tarafında local prediction eklenecek mi?
   - **Recommendation:** Hayır. V1 için host-authoritative + doğru snapshot sıralaması yeterli; hissiyat sorunu kalırsa yalnızca görsel interpolation düşünülmeli.

3. `COOP_GAME_START` mesaj tipi kullanılacak mı?
   - **Recommendation:** Ya tamamen devreye al ya da kaldır. Generic `GAME_START` ile yarım kalmış co-op tipi birlikte yaşamamalı.

## Success Criteria

- [ ] Online co-op endless akışı Online PvP kadar güvenilir hale gelir.
- [ ] Lobi, code join, invite, ready, countdown, maç, pause, disconnect, rematch zincirinde bloklayıcı bug kalmaz.
- [ ] Rebind/focus-loss/gamepad gibi temel UX beklentileri karşılanır.
- [ ] Yeni online co-op test yüzü oluşur ve release gate olarak kullanılır.

## Notes for Atlas

- `src/online_coop_game.py` şu an iyi bir iskelet; en büyük eksik, proven PvP hardening desenlerinin burada henüz uygulanmamış olmasıdır.
- `src/coop_game.py` içindeki `inject_remote_input()` ve event emitter zaten yeterince iyi; local gameplay'i yeniden yazmaya çalışma.
- Pause ve disconnect çözümünde toggle mantığını değil, **authoritative state + sequence** mantığını tercih et.
- Private lobby ve metadata işlerinde Online PvP tarafındaki cross-platform dersleri doğrudan taşı; aynı hataları ikinci kez üretme.
- Online campaign'i bu planın içine çekme; endless akış tamamen stabil olmadan yeni kapsam açma.
