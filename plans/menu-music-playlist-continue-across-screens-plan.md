# Plan: Menü Müzik Playlist’inin UI Ekranlarında Kesintisiz Devam Etmesi

**Created:** 26 Şubat 2026
**Status:** Ready for Atlas Execution

## Summary

Menü müziği playlist (çoklu parça) modu açıkken, bazı UI ekranlarında (yeni kullanıcı, emeği geçenler, başarımlar, kılavuz vb.) parça bitince müzik devam etmiyor; ancak ana menüye dönünce tekrar başlıyor. Bunun nedeni `SoundManager.update_music_playlist()` çağrısının yalnızca bazı state handler’larında (örn. `menu`, `settings`) yapılması. Çözüm: `main.py` ana döngüsünde, her frame’de `menu_sound.update_music_playlist()` çağırarak playlist’in tüm UI state’lerde ilerlemesini sağlamak.

## Context & Analysis

**Relevant Files:**
- `src/sound.py`: `SoundManager` playlist mantığı (`set_music_playlist`, `update_music_playlist`, `_playlist_is_busy`, `play_next_in_playlist`).
- `src/main.py`: state-machine ana döngü (`while running:`) ve state handler’ları; şu an playlist tick’i sadece bazı handler’larda.
- (Bağlam) `src/menu.py`, `src/user_screens.py`, `src/guide_screen.py`: Etkilenen ekranlar; müzikle doğrudan etkileşimleri yok.

**Key Functions/Classes:**
- `SoundManager.update_music_playlist()` in `src/sound.py`: Playlist aktifken “parça bitti mi?” kontrol edip sıradakini başlatır; ancak bu fonksiyon frame bazında çağrılmazsa playlist ilerlemez.
- `while running:` ana döngüsü in `src/main.py`: Tüm state’ler için ortak frame döngüsü; burada tek noktadan playlist tick etmek en düşük riskli çözümdür.

**Current Behavior (Root Cause):**
- `src/main.py` içinde `menu_sound.update_music_playlist()` çağrısı **menü** state’inde ve **ayarlar** state’inde var.
- `credits`, `achievements`, `guide`, `user_selection`, `user_management` gibi state’lerde bu çağrı yok.
- Menü müziği **playlist** modunda her parça `loop=False` çalındığı için (playlist mantığı sıradaki parçayı `update_music_playlist()` ile başlatıyor), bu ekranlarda parça bitince müzik susuyor.
- Ayarlarda yeniden başlamasının nedeni: settings handler’ı zaten `update_music_playlist()` çağırıyor.

**Patterns & Conventions:**
- `main.py` handler’lar içinde “güvenli” müzik tick’i `try/except` ile sarılıyor.
- Oyun state’lerinde ayrı sound manager (örn. `game.sound`, `pvp_game.sound`) playlist tick’i zaten mevcut.

## Implementation Phases

### Phase 1: Reprodüksiyon + Kabul Senaryosu Netleştirme

**Objective:** Sorunun playlist modunda olduğunu kesinleştirip kabul kriterlerini yazmak.

**Files to Modify/Create:**
- (Yok)

**Steps:**
1. Uygulamada menü müzik playlist’ini açık konuma getir (ayarlar → menü playlist).
2. Ana menüde müziğin parça bitince sıradakine geçtiğini doğrula.
3. Credits / Achievements / Guide / User ekranlarında parça bitince müziğin sustuğunu doğrula.
4. Ana menüye dönünce müziğin tekrar başladığını doğrula.

**Acceptance Criteria:**
- [ ] Playlist açıkken, ana menü dışındaki UI ekranlarında parça bitince müzik susuyor (mevcut bug doğrulandı).

---

### Phase 2: Global Playlist Tick (Tek Noktadan Çözüm)

**Objective:** `menu_sound.update_music_playlist()` çağrısını tüm state’ler için garanti etmek.

**Files to Modify/Create:**
- `src/main.py`: Ana `while running:` döngüsüne `menu_sound.update_music_playlist()` çağrısı ekle.

**Steps (TDD odaklı, pratik uyarlama):**
1. (Opsiyonel) Basit bir regression test yaklaşımı seç (bkz. Phase 3).
2. `src/main.py` içinde `while running:` döngüsünde, handler çağrısından önce veya sonra:
   - `try: menu_sound.update_music_playlist() except Exception: pass` ekle.
   - Bu çağrı **state’den bağımsız** olmalı.
3. Mevcut handler içindeki `update_music_playlist()` çağrılarını kaldırma (şimdilik) — minimal risk. (İstersen Phase 4’te sadeleştir.)

**Acceptance Criteria:**
- [ ] Playlist açıkken credits/achievements/guide/user ekranlarında parça bitince otomatik olarak sıradakine geçer.
- [ ] Oyun state’lerinde menü müziği “kendiliğinden” başlamaz (zaten `stop_music()` ile playlist inactive olmalı).

---

### Phase 3: Test (Mümkün Olan En Dayanıklı Regression)

**Objective:** Bu bug’ın geri gelmesini yakalayacak hafif bir test eklemek (opsiyonel ama önerilir).

**Option A (Önerilen: saf Python, pygame’siz):**
- Yeni test: `test_menu_music_playlist_tick_is_global.py`
- Test yaklaşımı: `src/main.py` dosyasını metin olarak oku ve `while running:` ana döngüsünde `menu_sound.update_music_playlist()` çağrısının varlığını doğrula.
  - Artı: pygame init gerekmez.
  - Eksi: Metin/AST bazlı test kırılgan olabilir (refactor’da update gerekir).

**Option B (Daha “doğru”, pygame monkeypatch):**
- `SoundManager` playlist’i için unit test yaz.
- `pygame.mixer.music.get_busy/load/play` monkeypatch ile taklit edilir.
- Amaç: `update_music_playlist()` busy=False iken `play_next_in_playlist()` tetikliyor mu?
  - Artı: SoundManager mantığı doğrulanır.
  - Eksi: Asıl bug “çağrılmaması” olduğundan tek başına yeterli değil.

**Recommendation:** Option A (çok düşük bağımlılık) + (istersen) Option B.

**Acceptance Criteria:**
- [ ] En az bir regression test, “global tick” mekanizmasını güvence altına alır.

---

### Phase 4: Temizlik (Opsiyonel)

**Objective:** Aynı tick’in iki yerde çağrılmasını önleyip kodu sadeleştirmek.

**Files to Modify/Create:**
- `src/main.py`: Menü ve settings handler’larındaki local `update_music_playlist()` çağrılarını kaldır veya tek yardımcı fonksiyona topla.

**Steps:**
1. Global tick eklendikten sonra, `_handle_menu` ve `_handle_settings` içindeki duplicate tick’i kaldır.
2. Davranış değişmediğini manuel doğrula.

**Acceptance Criteria:**
- [ ] `menu_sound.update_music_playlist()` yalnızca tek yerden (global loop) çağrılır.

## Open Questions

1. Menü müzik playlist’i bazı ekranlarda **bilerek** durmalı mı?
   - **Option A:** Her UI ekranında devam etsin (bu plan).
   - **Option B:** Belirli ekranlarda (örn. credits) sessiz olsun.
   - **Recommendation:** A — kullanıcı beklentisi “ana menüye dönmeden de devam etsin”.

2. Playlist “loop” bayrağı (`music_playlist_loop`) kullanılmalı mı?
   - **Option A:** Mevcut davranış (her zaman wrap) kalsın.
   - **Option B:** Loop=False ise playlist sonuna gelince dur.
   - **Recommendation:** Bu bug kapsamında dokunma; ayrı bir değişiklik olarak ele alın.

## Risks & Mitigation

- **Risk:** Global tick, oyun sırasında menü müziğini yanlışlıkla başlatır.
  - **Mitigation:** Menü müziği oyun girişinde `menu_sound.stop_music()` ile playlist inactive yapılıyor; ayrıca `update_music_playlist()` `music_playlist_active` kontrolü yapıyor. Yine de manuel doğrulama ekle.

- **Risk:** Mixer init edilmemişse exception.
  - **Mitigation:** Zaten kod tabanında kullanılan `try/except` kalıbını global tick’te de kullan.

## Success Criteria

- [ ] Playlist açıkken, yeni kullanıcı / credits / başarımlar / kılavuz ekranlarında müzik parça bitince otomatik devam eder.
- [ ] Ana menüye dönmeye gerek kalmadan müzik yeniden başlar.
- [ ] Mevcut ayarlar ekranı davranışı bozulmaz.
- [ ] Tüm testler geçer (`pytest`).

## Notes for Atlas

- En düşük riskli yer: `src/main.py` ana `while running:` döngüsü; handler çağrısından hemen önce/sonra global tick eklemek.
- Bu bug özellikle `set_music_playlist(... autoplay=True ...)` aktifken görülür; çünkü her parça `loop=False` çalınıyor ve “devam” tick ile sağlanıyor.
- İstersen bu değişiklikten sonra `_handle_menu` ve `_handle_settings` içindeki tick’leri temizleyebilirsin ama önce davranışı stabilize et.