# Plan: Playlist Editörünü Ayarlara Gömme + “burak” Toggle + ESC Pause

**Created:** 2026-02-26
**Status:** Ready for Atlas Execution

## Summary

Bu çalışma 3 davranış değişikliği ve 1 doğrulama içerir: (1) Bölüm (mode) müzik playlist editörü artık ayrı ekran/state açmadan, mevcut Ayarlar penceresi içinde overlay/panel olarak çalışacak. (2) “burak” hile kodu tüm görevleri açmayı toggle edecek; tekrar girilince kilitleyip oyuncuyu gerçek ilerlemesine (kaldığı bölüme) geri döndürecek. (3) Oyun içinde ESC, mevcut “çıkış onayı” penceresi yerine pause menüyü açacak (P ile açılan menü). (4) Nişancı patlama efekti/app paketleme bağlantısı kontrol edilecek; gerekirse yalnızca eksik bağımlılık/asset durumunda düzeltme yapılacak.

## Context & Analysis

**Relevant Files:**
- src/settings_screen_tabbed.py: Audio sekmesindeki mode-music playlist giriş noktası ve ayarlar ekranı çizim/input altyapısı.
- src/main.py: Ayarlar state machine; mevcutta edit_mode_playlist aksiyonunu ayrı state (mode_music) ile MusicSettingsScreen’e yönlendiriyor. Ayrıca cheat buffer/cheat mapping burada.
- src/menu.py: MusicSettingsScreen (ayrı ekran) ve playlist edit kontrol mantığı (Ekle/Delete/taşıma/picker).
- src/settings_manager.py: Mode playlist storage API (get_mode_music_playlist / set_mode_music_playlist).
- src/campaign/level_select.py: CampaignLevelSelect unlock logic ve seçim/scroll state; debug_unlock_all bypass.
- src/campaign/campaign_mode.py: Progress kaydı (highest_level, completed_levels, current_world).
- src/game.py: Base gameplay input; şu an ESC exit prompt, P pause.
- src/game_modes.py: HardcoreGame gibi override’larda ESC/P tekrar implement edilmiş.
- src/pvp_game.py: PvP’de ESC exit prompt.
- assets/animate_effect/sniper_effect.gif: Nişancı patlama GIF’i.
- tetris.spec, tetris_playtest.spec, tetris_macos.spec: PyInstaller datas listesi (assets dizini tamamen paketleniyor).

**Key Functions/Classes:**
- TabbedSettingsScreen (src/settings_screen_tabbed.py): modal guard pattern (ör. _music_picker_open) ve overlay çizim pattern’i.
- MusicSettingsScreen._load_playlist / _save_playlist / _handle_playlist_input / _handle_picker_input (src/menu.py): playlist edit davranışının referans implementasyonu.
- CampaignLevelSelect._is_level_unlocked ve _update_selection_for_world (src/campaign/level_select.py): toggle OFF restore için kullanılacak.
- Game.handle_input + _handle_pause_menu_input (src/game.py): ESC davranışını pause’a çevirmek için ana nokta.

**Dependencies:**
- pygame: input/draw.
- Pillow: sniper_effect.gif frame extraction (sniper explosion efektinde kullanılıyor).

**Patterns & Conventions:**
- Screen handle_input metotları string action döndürür; main.py bu aksiyonla state/sound günceller.
- TabbedSettingsScreen içinde “modal guard” yaklaşımı var: bir overlay açıkken normal input devre dışı.
- PyInstaller spec’lerde (REPO_ROOT / 'assets') komple data olarak paketleniyor; animate_effect dahil.

## Implementation Phases

### Phase 1: Bölüm (Mode) Playlist Editörünü Ayarlar İçine Göm

**Objective:** Mode müzik playlist düzenleme artık ayrı pencere/state açmadan Ayarlar penceresi içinde çalışsın.

**Approach (minimal ve spec’e uygun):**
- TabbedSettingsScreen içine “playlist edit overlay” (modal panel) ekle.
- Mevcut giriş noktası korunabilir: Audio tab’daki music_selector item’ına Enter ile edit_mode_playlist:{mode_key} aksiyonu üretmeye devam edilebilir.
- main.py bu aksiyonu artık state değiştirerek ayrı ekrana geçmek yerine, settings_screen üzerinde yeni bir API çağrısı ile aynı ayarlar ekranında overlay’i açacak.

**Files to Modify/Create:**
- src/settings_screen_tabbed.py:
  - Playlist edit overlay state alanları ekle.
  - open/close API (örn. open_mode_playlist_editor(mode_key)) ekle.
  - handle_input içine guard ekle (overlay açıkken input’u playlist editor’e yönlendir).
  - draw içine overlay çizimi ekle.
  - Playlist edit input davranışını MusicSettingsScreen referansına paralel uygula: ESC kapat, UP/DOWN seçim, ENTER/SPACE “Ekle” → picker, DEL/BACKSPACE sil, LEFT/RIGHT reorder, mouse wheel scroll.
  - Track picker için mevcut track options builder’ı ve mevcut picker çizim pattern’i (glass panel) reuse et.
- src/main.py:
  - _handle_settings içinde edit_mode_playlist:{mode_key} yakalayan kısım: state='mode_music' yerine settings screen overlay aç.
  - mode_music_screen init/state dispatch (mode_music) artık kullanılmıyorsa kaldır veya backward-compat için bırak ama normal akışta tetiklenmeyecek şekilde güncelle.
- src/menu.py:
  - Zorunlu değil. MusicSettingsScreen şimdilik bırakılabilir (kullanılmayan dead code olabilir). Temizlik ayrı PR olarak düşünülebilir.

**Tests to Write/Update:**
- test_settings_tabbed_mode_music_playlist_action.py:
  - Mevcut test “edit_mode_playlist:*” aksiyonunu doğruluyor. Bu aksiyon üretimi korunuyorsa test aynı kalabilir.
  - Eğer aksiyon üretimi değiştirilirse (doğrudan overlay açılacaksa), test overlay state’in açıldığını assert edecek şekilde güncellenir.
- Yeni test: test_settings_tabbed_inline_mode_playlist_editor.py
  - TabbedSettingsScreen örneğini (testlerde kullanılan __new__ pattern ile) oluştur, gerekli minimal alanları enjekte et.
  - open_mode_playlist_editor('classic') çağrısı ile overlay’in açıldığını doğrula.
  - DELETE ile bir öğe silinince settings_manager.set_mode_music_playlist çağrıldığını ve action (mode_playlist_changed) döndüğünü doğrula.
  - Picker aç/kapat ve ESC ile overlay kapanma senaryolarını doğrula.

**Steps (TDD):**
1. Yeni test dosyasında inline editor açılıp kapanma senaryosu için failing test yaz.
2. src/settings_screen_tabbed.py içine minimal state + open/close API ekle.
3. Overlay input/draw iskeletini ekle; testi geçir.
4. Silme / reorder / picker ekleme davranışları için ek failing testler yaz.
5. MusicSettingsScreen davranışına paralel şekilde implement et; testleri geçir.
6. src/main.py edit_mode_playlist handler’ını değiştir; entegrasyon testi ekle veya mevcut testi güncelle.

**Acceptance Criteria:**
- [ ] Audio tab’da “bölüm müzikleri” playlist edit açıldığında state değişmeden (ayarlar ekranında) bir overlay/panel görünür.
- [ ] Ayrı “mode_music” ekranı/penceresi açılmaz.
- [ ] Playlist ekleme/silme/yer değiştirme ayarlar içine kaydedilir (settings_manager.set_mode_music_playlist).
- [ ] İlgili testler geçer.

---

### Phase 2: “burak” Cheat Toggle ve Restore

**Objective:** “burak” cheat ON iken tekrar girilirse OFF’a dönüp bölümler kilitlensin ve oyuncu gerçek ilerlemesine geri dönsün.

**Files to Modify/Create:**
- src/main.py:
  - Cheat handler’da campaign_unlock_all davranışını toggle yap.
  - Toggle OFF olduğunda CampaignLevelSelect’i progress’e göre restore et (current_world, selected_level, scroll_offset, hovered_level).
- src/campaign/level_select.py:
  - __init__ içine self.debug_unlock_all = False ekle (explicit state).
  - Restore için kullanılacak yardımcı metot zaten var: _update_selection_for_world.
- test_campaign_debug_unlock_all.py:
  - Toggle OFF senaryosu ekle.

**Steps (TDD):**
1. test_campaign_debug_unlock_all.py içine failing test ekle:
   - debug_unlock_all True iken “burak” tekrar → debug_unlock_all False olmalı.
   - highest_level=25 gibi progress ile current_world ve selected_level restore olmalı.
2. src/campaign/level_select.py __init__’e debug_unlock_all default ekle.
3. src/main.py cheat handler’ında:
   - currently_on = getattr(campaign_level_select, 'debug_unlock_all', False)
   - ON→OFF: progress.highest_level’den current_world hesapla, _update_selection_for_world çağır, scroll_offset=0, hovered_level=None.
   - OFF→ON: debug_unlock_all=True.
4. Testleri geçir.

**Acceptance Criteria:**
- [ ] “burak” ilk girildiğinde tüm level’lar açık görünür.
- [ ] Tüm level’lar açıkken tekrar “burak” girilince debug_unlock_all kapanır ve seçim oyuncunun gerçek ilerlemesine döner.
- [ ] Kampanya ekranı scroll/hover state’i stale kalmaz.

---

### Phase 3: ESC ile Pause Menüyü Aç (Exit Prompt Yerine)

**Objective:** Oyun içinde ESC basınca, mevcut “çıkış onayı” penceresi yerine pause menü açılsın (P ile açılan menü).

**Design Decision (öneri):**
- Exit prompt kodu silinmez (risk azaltma); sadece gameplay ESC artık show_exit_prompt tetiklemez.
- Pause menü zaten “Ana Menü” seçeneği ile oyundan çıkışı sağlıyor; ekstra onay UX’i bu değişiklikle kalkmış olur.

**Files to Modify/Create:**
- src/game.py:
  - gameplay KEYDOWN ESC branch: show_exit_prompt=True yerine paused=True + pause_menu_selected=0.
  - game_over ESC davranışı korunur (direkt menu).
  - pause menü içindeyken ESC=resume davranışı zaten doğru.
- src/game_modes.py:
  - HardcoreGame gibi override’larda aynı ESC değişikliği uygulanır.
  - P branch’inde pause_menu_selected=0 set edilerek menü selection düzgün resetlenir.
- src/pvp_game.py:
  - gameplay ESC branch: show_exit_prompt yerine paused.
  - HUD hint metni güncellenir (ESC’nin artık “menu” değil “pause” olduğu).

**Tests to Write:**
- Yeni test: test_ingame_esc_opens_pause_menu.py (veya mevcut uygun test dosyasına ek)
  - Base Game: ESC sonrası paused True, show_exit_prompt False.
  - paused iken ESC: resume (paused False).
  - game_over True iken ESC: yine menu (değişmemeli).
- HardcoreGame için benzer test.
- PvPGame için gameplay ESC test.

**Steps (TDD):**
1. Base Game için ESC→pause davranışını doğrulayan failing test yaz.
2. src/game.py ESC branch’ini değiştir; testleri geçir.
3. HardcoreGame ve PvP’de override branch’leri için failing testler yaz.
4. src/game_modes.py ve src/pvp_game.py değişikliklerini yap; testleri geçir.
5. HUD hint/metin güncellemesini doğrula.

**Acceptance Criteria:**
- [ ] Gameplay sırasında ESC, çıkış onayı yerine pause menüyü açar.
- [ ] Pause menü açıkken ESC, menüyü kapatır (resume).
- [ ] Game over ekranında ESC davranışı değişmez.
- [ ] Hardcore ve PvP modlarında da aynı davranış geçerlidir.

---

### Phase 4: Nişancı Patlama Efekti Bağlantı ve Paketleme Kontrolü

**Objective:** “App dosyasında nişancı patlama efekti var mı/bağlı mı” kontrolünü kanıtla; eksik durum yoksa değişiklik yapma.

**Current Findings (doğrulandı):**
- assets/animate_effect/sniper_effect.gif mevcut.
- src/game_modes_extra.py içinde GIF yükleme (Pillow ile) ve spawn/draw zinciri mevcut.
- PyInstaller spec’lerde assets komple paketleniyor; animate_effect klasörü dahil.

**Actions (yalnızca gerekiyorsa):**
- requirements.txt / requirements-macos.txt içinde Pillow mevcut mu kontrol et; yoksa ekle.
- Eğer patlama asset’i eksik/bulunamazsa: dosya yolu veya datas mapping düzeltilir.

**Acceptance Criteria:**
- [ ] Sniper patlama GIF’i paketleme datas içinde kapsanır (assets dahil).
- [ ] Pillow bağımlılığı build ortamında mevcut.

## Open Questions

1. ESC ile eski çıkış onayı tamamen kalkacak mı?
   - Option A (öneri): ESC sadece pause açar; çıkış onayı artık kullanılmaz.
   - Option B: Pause menüde “Ana Menü” seçilince çıkış onayı overlay’i açılır.
   - Recommendation: Option A, en az müdahale ve en düşük regression riski.

2. P tuşu ne olacak?
   - Option A (öneri): P çalışmaya devam eder; ESC de aynı menüyü açar.
   - Option B: P devre dışı bırakılır, sadece ESC.
   - Recommendation: Option A (geri uyumluluk, spec’i bozmaz).

## Risks & Mitigation

- **Risk:** TabbedSettingsScreen’e yeni overlay eklenince input guard sırası başka modallarla çakışabilir.
  - **Mitigation:** Guard öncelik sırası net olsun: playlist picker > playlist editor > mevcut music picker > keybind capture vb.

- **Risk:** main.py’de mode_music state kaldırılırsa başka gizli akışlar kırılabilir.
  - **Mitigation:** İlk etapta state kodu bırakılabilir ama normal akışta tetiklenmez; sonraki refactor’da temizlenir.

- **Risk:** ESC değişikliği bazı modlarda (finished screens, overlays) farklı davranışlar yaratabilir.
  - **Mitigation:** Sprint/Ultra finished ESC→menu gibi özel branch’ler korunur; test kapsamı artırılır.

## Success Criteria

- [ ] Mode playlist editörü Ayarlar içinde çalışır; ayrı pencere/state açılmaz.
- [ ] “burak” cheat toggle edilir ve OFF’ta gerçek ilerleme restore olur.
- [ ] ESC gameplay’de pause menüyü açar ve çıkış onayı penceresi yerine geçer.
- [ ] Nişancı patlama efektinin bağlı/paketlenmiş olduğu doğrulanır.
- [ ] İlgili testler başarılıdır.

## Notes for Atlas

- Playlist edit overlay’i implement ederken MusicSettingsScreen’teki playlist davranışını birebir kopyalamak yerine, aynı davranışı TabbedSettingsScreen pattern’lerine uyarlayın.
- ESC değişikliğinde show_exit_prompt render/input kodunu silmek zorunlu değil; minimal risk için sadece trigger noktalarını değiştirin.
- “burak” toggle OFF restore için CampaignLevelSelect._update_selection_for_world mevcut; bunu kullanmak en tutarlı yol.
