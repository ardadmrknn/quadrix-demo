# Plan: Steam Leaderboard UX (Top 10 + Friends + Persona/Avatar) ve Steam’e Özel Yerel Profil

**Created:** 2026-02-25
**Status:** Ready for Atlas Execution

## Summary

Bu iş, "Kart Ustalığı" (mode: `mystery`, leaderboard: `quadrix_mystery`) için ana menü sağ-alt Steam skor panelini istenen hale getirir: Global ilk 10 + Arkadaşlar sekmesi, Steam kullanıcı adı ve avatar önizlemesi ile. Ek olarak Steam’den başlatıldığında SteamID’ye bağlı özel bir yerel profilin otomatik oluşturulup seçilmesini sağlar (şu an `create_user()` imza uyuşmazlığı nedeniyle bu akış try/except içinde TypeError ile düşüyor).

## Context & Analysis

**Relevant Files:**
- `src/main.py`: Steam SDK init sonrası SteamID/persona ile yerel profil seçme/oluşturma akışı var; ancak `user_manager.create_user(..., steam_id=...)` çağrısı mevcut imzayla uyumsuz.
- `src/user_manager.py`: Profillerde `steam_id` alanı şema migrate ile ekleniyor; `get_user_by_steam_id()` ve `set_steam_id()` mevcut. `create_user()` şu an `steam_id` parametresi almıyor.
- `src/menu.py`: Ana menü sağ-alt leaderboard paneli zaten global/friends tab, persona ve avatar çizimini içeriyor; fakat fetch ve render limitleri 5.
- `src/steam_leaderboards.py`: Global/friends entries fetch’ini backend→direct fallback ile yapıyor. `fetch_player_summaries()` sadece backend modda çalışıyor; direct modda boş dönüyor (bu yüzden backend yokken isim “bilinmiyor”).
- `backend/steam_leaderboard_proxy.py`: `/api/v1/players/summaries` endpoint’i `ISteamUser/GetPlayerSummaries/v2/` ile persona/avatar URL sağlayabiliyor.

**Key Functions/Classes:**
- `UserManager.create_user()` in `src/user_manager.py`: steam_id bağlama desteği eklenmeli.
- Steam auto-profile block in `src/main.py` (Steam init bölümünde): yeni kullanıcı oluşturma ve seçim; username çakışması/uzunluk; mevcut kullanıcıya steam_id bağlama.
- `Menu._refresh_mystery_leaderboard_cache()` ve `Menu._draw_mystery_leaderboard_panel()` in `src/menu.py`: limit=10, render 10 satır; mevcut avatar cache ve player summaries cache kullanılacak.
- `SteamLeaderboardService.fetch_player_summaries()` in `src/steam_leaderboards.py`: direct mod fallback eklenecek (opsiyonel ama “bilinmiyor” problemine en direkt çözüm).

**Dependencies:**
- `requests`: Hem istemci hem menü avatar download için zaten kullanılıyor.
- Steam Web API (partner): direct mod kullanılıyorsa `ISteamUser/GetPlayerSummaries/v2/`.

**Patterns & Conventions:**
- Testler root’ta `test_*.py` (unittest) formatında.
- Steam entegrasyonunda try/except ile graceful fallback yaklaşımı var.

## Implementation Phases

### Phase 1: Steam’e Özel Yerel Profil Oluşturma/Seçme Akışını Düzelt

**Objective:** Steam’den başlatılınca TypeError yüzünden devre dışı kalan otomatik Steam profil seçimini çalışır hale getirmek.

**Files to Modify/Create:**
- `src/user_manager.py`: `create_user()` imzasına `steam_id: str | None = None` ekle; profile içine yaz.
- `src/main.py`: Steam init bloğunda kullanıcı oluşturma/bağlama akışını sağlamlaştır (username çakışması, persona değişimi).
- `test_user_manager_steam_profile.py` (new): create_user steam_id + get_user_by_steam_id + set_steam_id regresyon testleri.

**Tests to Write:**
- `test_user_manager_steam_profile.py`:
  - `create_user(..., steam_id='765...')` profile içine `steam_id` yazar.
  - `get_user_by_steam_id()` doğru username döndürür.
  - Username persona truncation çakışırsa fallback üretim (aşağıdaki adımda; uygulanırsa test).

**Steps:**
1. Test: `UserManager.create_user()` steam_id kabul etmeli (RED).
2. Kod: `create_user()` içine `steam_id` parametresi ekle ve `self.users[username]['steam_id']` set et (GREEN).
3. Refactor: steam_id boşsa `None` normalize et; şema migrate ile uyumlu tut.
4. `src/main.py` Steam init kısmında:
   - Yeni user oluştururken ya `create_user(..., steam_id=...)` (Phase 1 sonrası mümkün) ya da `create_user` + `set_steam_id` kullan.
   - Username zaten varsa ve aynı steam_id’ye bağlı değilse, güvenli unique username üret (örn. `persona[:16] + '_' + steam_id[-4:]`).
5. Testleri çalıştır; başarısızsa düzelt.

**Acceptance Criteria:**
- [ ] Steam’den başlatınca `UserManager.create_user(..., steam_id=...)` TypeError üretmez.
- [ ] SteamID’ye bağlı profil otomatik seçilir (mevcutsa seç, yoksa oluştur).
- [ ] Tüm testler geçer.

---

### Phase 2: Player Summaries (Persona/Avatar URL) İçin Direct Mod Fallback

**Objective:** Backend/proxy çalışmıyorsa bile “bilinmiyor” yerine Steam persona adı ve avatar URL’lerinin gelebilmesi.

**Files to Modify/Create:**
- `src/steam_leaderboards.py`: `fetch_player_summaries()` direct mod desteği.
- `test_steam_leaderboards_player_summaries_direct.py` (new): `requests.get` mock ile direct parse testi.

**Tests to Write:**
- Direct modda `fetch_player_summaries(['765...'])` → `{steamid: {personaname, avatarmedium, ...}}` döndürür.

**Steps:**
1. Test: Direct modda `fetch_player_summaries()` boş dönmemeli (RED).
2. Kod: `ISteamUser/GetPlayerSummaries/v2/` endpoint’ine `_direct_get(...)` ile istek at, `response.players` listesini parse et.
3. Çıktıyı backend ile aynı shape’e normalize et: `steam_id -> {personaname, avatar, avatarmedium, avatarfull, profileurl}`.
4. Hata durumlarında `last_error` set et; crash etme.

**Acceptance Criteria:**
- [ ] Backend yokken de persona/avatarmedium alınabilir.
- [ ] Testler geçer.

---

### Phase 3: Ana Menü Leaderboard Panelini Global İlk 10 + Friends İlk 10 Şeklinde Göster

**Objective:** `mystery` leaderboard paneli her iki sekmede de ilk 10 girdiyi gösterir; isim+avatar render eder.

**Files to Modify/Create:**
- `src/menu.py`:
  - `Menu._refresh_mystery_leaderboard_cache()`: limit=10.
  - `Menu._draw_mystery_leaderboard_panel()`: 10 satır gösterecek layout (panel yüksekliği/row height ayarı).

**Steps:**
1. Fetch worker’da `service.fetch_mode_highscores('mystery', limit=10)` ve `fetch_mode_friend_highscores(..., limit=10)` yap.
2. Render’da `max_rows = min(10, len(active_entries))` olacak şekilde ayarla.
3. Panelin minimum yüksekliğini 10 satır için yeterli yap (örn. `panel_h` min artırımı) veya satır yüksekliğini liste alanına göre dinamik hesapla.
4. Mevcut persona/avatar cache akışını koru; yeni ids → summaries → avatar bytes download.
5. Opsiyonel ama UX için değerli: Aktif Steam kullanıcısını (service.current_steam_id) satır arka planında hafif vurgula.

**Acceptance Criteria:**
- [ ] Global sekmede ilk 10 gösterilir.
- [ ] Friends sekmede ilk 10 gösterilir (mümkün değilse anlaşılır hata/boş durum mesajı aynı kalır).
- [ ] Steam isim ve avatarlar (varsa) görünür; yoksa placeholder + kısa steam_id fallback.

---

### Phase 4: Güvenlik/Dağıtım Tutarlılığı (Opsiyonel ama Önerilen)

**Objective:** Client içinde hard-coded Steam Web API key riskini azaltmak; üretimde proxy kullanımını teşvik etmek.

**Files to Modify/Create:**
- `src/menu.py`: `SteamLeaderboardService(... publisher_key=os.getenv('STEAM_WEB_API_KEY', 'HARDCODED') ...)` fallback’ini kaldır; sadece env ile direct mod aç.
- (Opsiyonel) `src/main.py`: Tek bir `SteamLeaderboardService` örneğini menu’ye enjekte ederek tek noktadan konfigürasyon.

**Steps:**
1. Hard-coded key’i kaldır; direct fallback ancak env ile aktif olsun.
2. Backend URL yoksa/erişilemiyorsa mevcut hata metinleriyle kullanıcıyı yönlendir.

**Acceptance Criteria:**
- [ ] Repo’da hard-coded `STEAM_WEB_API_KEY` literal’ı kalmaz.
- [ ] Proxy/back-end ile persona+avatar ve entries sorunsuz çalışır.

## Open Questions

1. Global ilk 10 nerede gösterilmeli?
   - **Option A (minimal):** Mevcut sağ-alt panelde 10 satırı sığdır (panel min-height/row height dinamik).
   - **Option B:** `HighScoreScreen` içinde yalnızca `mystery` için yeni “Steam Global/Friends” görünümü ekle.
   - **Recommendation:** Option A (mevcut UX’e en az müdahale, yeni sayfa yok).

2. Steam’den başlatınca kullanıcı değiştirme (Switch User) engellensin mi?
   - **Option A:** Serbest bırak (şu anki gibi), ama Steam rozetini ve aktif Steam profilini belirt.
   - **Option B:** Steam aktifken Switch User butonunu devre dışı bırak.
   - **Recommendation:** Option A (istek açıkça “yasakla” demiyor).

## Risks & Mitigation

- **Risk:** `GetPlayerSummaries` direct modda ek parametre (`appid`) nedeniyle beklenmedik hata.
  - **Mitigation:** Gerekirse `_direct_get` içinde endpoint bazlı parametre filtreleme veya ayrı `_direct_get_no_appid` helper.

- **Risk:** 10 satır panelde küçük ekranlarda okunabilirlik.
  - **Mitigation:** Satır yüksekliğini liste alanına göre dinamik hesapla; çok küçükse paneli mevcut logic gibi gizle.

- **Risk:** Persona adı ile username çakışmaları.
  - **Mitigation:** SteamID son 4 hanesi ile unique suffix.

## Success Criteria

- [ ] Steam’den başlatınca SteamID’ye bağlı yerel profil otomatik seçilir/oluşturulur.
- [ ] Kart Ustalığı leaderboard paneli global+friends ilk 10’u gösterir.
- [ ] Steam persona ve avatarlar görünür (backend veya direct fallback ile).
- [ ] Tüm testler geçer.

## Notes for Atlas

- `src/main.py` içindeki Steam init bloğunda zaten doğru niyet var; öncelik `UserManager.create_user` imza uyuşmazlığını çözmek.
- “bilinmiyor” genellikle backend olmadan direct entries okunup player summaries boş kaldığında oluşuyor; Phase 2 bunu düzeltir.
- UI için en risksiz yol: var olan paneli genişletmek/daha kompakt satırlarla 10’u görünür kılmak; yeni ekran eklememek.
