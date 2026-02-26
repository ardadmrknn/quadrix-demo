# Plan: 5 İstek (Burak hilesi + Sniper efekt + Menü hover + Mod müzik playlist + Extras Classic)

**Created:** 2026-02-26
**Status:** Ready for Atlas Execution

## Summary

Bu plan, tek bir sprint içinde 5 ayrı isteği (1 yeni cheat/hile, 2 bug fix, 2 UX/menü düzeni) kapatmak için adım adım uygulanabilir değişiklikleri listeler. Öncelik: kullanıcıya görünen hataları (macOS .app Sniper patlama efekti, ana menü hover/Enter tetikleme) düzeltmek; ardından istenen erişim kolaylığı ("burak" ile campaign unlock) ve ayar/menü düzenlemelerini (playlist tabanlı mod müziği, Extras’a Klasik) tamamlamak.

## Context & Analysis

**Relevant Files:**
- `src/main.py`: Ana menü event loop’u, mevcut `arda` cheat buffer’ı, campaign seçime geçiş ve state handler’lar.
- `src/campaign/level_select.py`: `CampaignLevelSelect._is_level_unlocked()` kilit kontrolü.
- `tetris_macos_allinone.spec`: macOS .app build; şu an `excludes` içinde `PIL`/`Pillow` var (Sniper GIF yüklemeyi kırıyor).
- `src/game_modes_extra.py`: Sniper patlama efektinin GIF + Pillow ile yüklenmesi (`_ensure_sniper_explosion_assets`).
- `src/menu.py`: `Menu.handle_input()` hover seçimi + Enter tetikleme; panel dışına çıkınca seçimin “donması” bug’ı.
- `src/settings_screen_tabbed.py`: Audio tab’ında `music_selector` ile tek-parça `mode_music_overrides` yönetimi (playlist yerine).
- `src/settings_manager.py`: `mode_music_playlists` altyapısı zaten var (`get_mode_music_playlist`, `set_mode_music_playlist`, `get_music_playlist_for_mode`).
- `src/menu.py`: `MusicSettingsScreen` playlist tabanlı ekran zaten var ve `set_mode_music_playlist` kullanıyor.
- `src/extras_menu.py`: Extras grid listesi (`_items_base`) ve action return modeli; Classic yok.
- `src/localization.py`: Mod isimleri mevcut (`mode_label_classic` var), Extras açıklamasına yeni key gerekebilir.

**Key Functions/Classes:**
- Cheat yakalama: `main._handle_menu()` içinde `cheat_buffer/cheat_sequence` ("arda").
- Campaign unlock: `CampaignLevelSelect._is_level_unlocked()`.
- Sniper assets: `game_modes_extra._ensure_sniper_explosion_assets()`.
- Menü input: `Menu.handle_input()`.
- Tabbed settings: `TabbedSettingsScreen` item builder (audio tab) + `music_selector` action handling.
- Playlist ekranı: `MusicSettingsScreen` (`menu.py`).
- Extras dispatch: `main._handle_extras()`.

**Dependencies:**
- macOS build: PyInstaller spec (özellikle `excludes`).
- Sniper efekt: Pillow (PIL) runtime import’u.

**Patterns & Conventions:**
- Runtime-only cheat ayarı: `arda` cheat’i `settings_manager.settings[...] = True` ile diske yazmadan açılıyor.
- Testlerde pygame bağımlılığı genelde `sys.modules` stublarıyla izole ediliyor.

## Implementation Phases

### Phase 1: “burak” cheat ile Campaign tüm levelleri aç

**Objective:** Ana menüde "burak" yazıldığında Campaign level seçim ekranında tüm levellerin kilidi kalksın (runtime-only).

**Files to Modify/Create:**
- `src/main.py`
  - Mevcut cheat sistemini çoklu sekansa genişlet ("arda" + "burak").
  - "burak" tetiklenince campaign seçime etki edecek bir runtime flag set et.
- `src/campaign/level_select.py`
  - `_is_level_unlocked()` içine debug bypass ekle.

**Implementation Notes (önerilen yaklaşım):**
- `src/main.py` içindeki mevcut yapı:
  - `cheat_sequence = 'arda'` sabit.
  - Buffer güncelleme + timeout mantığı zaten var.
- Bunu küçük bir sözlüğe genişlet:
  - `cheat_sequences = {'arda': 'show_debug_settings', 'burak': 'campaign_unlock_all'}` gibi.
  - Buffer’ı en uzun sekans uzunluğuna göre kırp.
  - Eşleşen sekans bulununca ilgili aksiyonu uygula.
- Runtime flag önerisi:
  - `campaign_level_select.debug_unlock_all = True` gibi bir attribute (persist etme).
  - Alternatif: `settings_manager.settings['campaign_debug_unlock_all'] = True` (ama `CampaignLevelSelect` her çağrıda settings’ten okumuyorsa ek iş çıkarır).
- `CampaignLevelSelect._is_level_unlocked(level_num)` başına:
  - `if getattr(self, 'debug_unlock_all', False): return True`

**Tests to Write:**
- `test_campaign_debug_unlock_all.py`
  - `campaign.level_select.CampaignLevelSelect` importunu stub’layarak (pygame + ui_theme + localization + level_data), `__new__` ile instance üret.
  - `debug_unlock_all=True` iken `_is_level_unlocked(100)` → `True`.
  - `debug_unlock_all=False` ve progress boş iken `_is_level_unlocked(2)` → `False`.

**Steps:**
1. (TDD) `_is_level_unlocked` debug bypass testini yaz.
2. Test fail.
3. `CampaignLevelSelect._is_level_unlocked` içine bypass ekle.
4. Test pass.
5. `main.py` cheat yakalamayı "burak" destekleyecek şekilde genişlet ve `campaign_level_select.debug_unlock_all=True` set et.

**Acceptance Criteria:**
- [ ] Ana menüde "burak" yazınca Campaign seçime girildiğinde tüm leveller oynanabilir.
- [ ] Bu değişiklik kalıcı ayarlara yazılmaz (oyun kapanınca sıfırlanır).

---

### Phase 2: macOS .app’de “Keskin Nişancı” patlama efektini geri getir

**Objective:** PyInstaller macOS .app build’inde Sniper patlama efektinin devre dışı kalma sebebini kaldırmak.

**Root Cause (tespit):** `tetris_macos_allinone.spec` içinde `excludes` listesi `PIL` ve `Pillow`’ı hariç tutuyor. `game_modes_extra.py` GIF frame’lerini `PIL.Image` ile yüklüyor; bu yüzden .app’de efekt sessizce kapanıyor.

**Files to Modify/Create:**
- `tetris_macos_allinone.spec`
  - `excludes` listesinden `'PIL'` ve `'Pillow'` öğelerini kaldır.
  - (Opsiyonel ama önerilir) `hiddenimports` listesine şu modülleri ekle:
    - `PIL`, `PIL.Image`, `PIL.ImageSequence`, `PIL.GifImagePlugin`, `PIL.PngImagePlugin`
- `requirements-macos.txt`
  - Pillow’ın macOS build ortamında kurulu olduğundan emin olmak için `Pillow` ekli değilse ekle.

**Tests to Write:**
- `test_macos_spec_includes_pillow.py`
  - `tetris_macos_allinone.spec` dosyasını metin olarak oku.
  - `excludes` içinde `PIL`/`Pillow` olmadığını assert et.

**Steps:**
1. (TDD) Spec testini yaz, önce fail ettir (mevcut durumda `PIL` exclude var).
2. `tetris_macos_allinone.spec`’ten `PIL`/`Pillow` excludes kaldır.
3. Test pass.
4. (Opsiyonel) hiddenimports’a Pillow alt modüllerini ekle.

**Acceptance Criteria:**
- [ ] macOS .app build’de Sniper patlama efekti tekrar görünür.
- [ ] `tetris_macos_allinone.spec` artık `PIL`’i dışlamaz.

---

### Phase 3: Ana menüde panel dışına çıkınca hover kalksın, Enter tetiklemesin

**Objective:** Mouse ile bir buton hover olmuşken imleç panel dışına çıkınca hover/selection “donmasın”; Enter/Space o butonu tetiklemesin.

**Files to Modify/Create:**
- `src/menu.py`
  - `Menu.handle_input()` ve (varsa) `Menu.draw()` içindeki mouse-hover seçme logic’i.

**Implementation Notes (önerilen minimal değişiklik):**
- `Menu` içine yeni bir flag ekle: `self._mouse_in_panel: bool`.
- `MOUSEMOTION` sırasında option_rects üzerinde collision bulunursa `True`, bulunmazsa `False` yap.
- Enter/Space branch’inde guard:
  - Eğer `_nav_source == 'mouse'` ve `_mouse_in_panel == False` ise `None` döndür (tetikleme yok).
  - `_nav_source == 'keyboard'` ise mevcut davranış korunur.
- (Opsiyonel görsel) draw sırasında seçili görünümü de `_mouse_in_panel` ile kısıtla.

**Tests to Write:**
- `test_menu_hover_enter_guard.py`
  - Test stublarıyla `menu.Menu` import et (pygame/retro_style/platform_utils/localization/background_effects vb. stub).
  - `Menu.__new__` ile minimal instance oluştur, `option_rects` ve `options` ayarla.
  - `_nav_source='mouse'`, `_mouse_in_panel=False`, `selected=0` iken Enter event → `None`.
  - `_nav_source='keyboard'` iken Enter event → `options[selected]`.

**Steps:**
1. (TDD) Enter guard testini yaz.
2. Test fail.
3. `Menu.handle_input` içine `_mouse_in_panel` update + Enter guard ekle.
4. Test pass.

**Acceptance Criteria:**
- [ ] Mouse panel dışındayken hover highlight kalkar.
- [ ] Mouse panel dışındayken Enter/Space hiçbir menü aksiyonu tetiklemez.
- [ ] Klavye ile gezinti (oklar) + Enter mevcut şekilde çalışır.

---

### Phase 4: Ayarlarda “mod/bölüm müzikleri” için playlist mantığını geri getir

**Objective:** Audio tab’ındaki mod müzikleri kısmı tek parça override seçimi yerine playlist düzenleme akışına dönsün.

**Constraints:** Yeni UX eklemeden, mümkünse mevcut `MusicSettingsScreen` (playlist yöneticisi) yeniden kullanılsın.

**Recommended Approach (düşük risk):**
- TabbedSettings audio tab’ında mod müzikleri satırlarını koru ama:
  - Satırın değeri olarak “N parça” (playlist uzunluğu) göster.
  - Enter/Space ile inline picker açmak yerine `main.py`’ye bir action döndür: `edit_mode_playlist:{mode_key}`.
- `main.py`’de bu action’ı yakala:
  - `mode_music_screen._load_playlist('mode', mode_key)` çağır.
  - `mode_music_screen.view = 'playlist'` (direkt edit ekranı).
  - State’i `mode_music` yap.
- `main._handle_mode_music` handler’ını **gerçekten** `MusicSettingsScreen`’i çalıştıracak şekilde güncelle:
  - Event’leri `mode_music_screen.handle_input`’a ilet.
  - `back` dönerse state’i `settings` yap.

**Files to Modify/Create:**
- `src/settings_screen_tabbed.py`
  - Audio tab item builder: `music_selector` satırlarında display logic’i playlist sayısına göre güncelle.
  - `music_selector` Enter branch’inde `_open_music_picker()` yerine action string döndür.
  - (İsteğe bağlı) Sol/sağ ile parça cycling’i devre dışı bırak (playlist modelinde anlamlı değil).
- `src/main.py`
  - `_handle_settings` içinde `action.startswith('edit_mode_playlist:')` yakala ve state geçişi yap.
  - `_handle_mode_music`’i `MusicSettingsScreen` bazlı gerçek sub-screen olarak implemente et.
- `src/menu.py`
  - Gerekirse `MusicSettingsScreen`’e “mode_select’a git” veya “mode_key ile direkt playlist aç” helper’ı ekle (şu an `_load_playlist` var, yeterli olabilir).

**Tests to Write:**
- `test_settings_tabbed_mode_music_playlist_action.py`
  - `TabbedSettingsScreen` importunu stub’larla yap.
  - Audio tab’da seçili bir mode satırında Enter’a basınca `edit_mode_playlist:<mode_key>` döndüğünü assert et.

**Acceptance Criteria:**
- [ ] Audio tab’daki “MOD MÜZİKLERİ” artık playlist tabanlıdır (tek parça override değil).
- [ ] Her mod için playlist düzenlenebilir ve `settings_manager.mode_music_playlists` içine kaydolur.
- [ ] Oyun içinde müzik seçiminde `get_music_playlist_for_mode` playlist’i kullanır.

---

### Phase 5: “Oyun Modları/Extras” ekranına Klasik’i ekle

**Objective:** Extras grid’inde Klasik (Classic) kartı görünsün ve seçilince Classic oyun başlasın.

**Files to Modify/Create:**
- `src/extras_menu.py`
  - `_items_base` listesine `Classic Mode` kartı ekle.
  - `MODE_ID_TO_STATS_KEY` mapping’e `Classic Mode: classic` ekle.
  - (Opsiyonel) `MODE_IMAGE_PROMPTS`’a Classic ikon prompt’u ekle.
- `src/main.py`
  - `_handle_extras()` dispatch içine `elif action == 'Classic Mode':` branch’i ekle.
  - Classic oyun başlatma mevcut menü akışına benzer şekilde `Game(..., 'classic', ...)` oluşturmalı.
- `src/localization.py`
  - `extras_classic_desc` gibi kısa açıklama key’i ekle (TR/EN ve mevcut diğer diller için minimum TR/EN; proje standardına göre diğer diller de doldurulmalı).

**Tests to Write:**
- `test_extras_includes_classic.py`
  - `extras_menu.ExtrasScreen` importunu stub’larla yap.
  - `_items_base` içinde `id == 'Classic Mode'` olduğunu assert et.
  - `MODE_ID_TO_STATS_KEY['Classic Mode'] == 'classic'`.

**Acceptance Criteria:**
- [ ] Extras grid’inde Klasik kartı görünür.
- [ ] Klasik seçilince Classic oyun modu başlar.

## Open Questions

1. “burak” cheat’i sadece unlock mu yapmalı, yoksa ayrıca `constants.DEBUG_MODE`’u da açmalı mı?
   - **Option A:** Sadece campaign unlock (önerilen; scope küçük, yan etki yok).
   - **Option B:** Debug mode’u da runtime aç (daha fazla yan etki; log/feature toggles devreye girebilir).
   - **Recommendation:** Option A.

2. TabbedSettings audio tab’ında eski `mode_music_overrides` verisi ne olacak?
   - **Option A:** UI’dan kaldır ama SettingsManager’da backward uyumluluk için bırak.
   - **Option B:** Eski overrides’ı migrate edip playlist’e çevir.
   - **Recommendation:** Option A (minimum risk).

## Risks & Mitigation

- **Risk:** Spec değişikliği sonrası macOS bundle boyutu artabilir (Pillow dahil olur).
  - **Mitigation:** Sadece Pillow’ı geri al; gereksiz diğer excludes değişmesin.

- **Risk:** Menü hover guard yanlışlıkla klavye Enter’ı da engeller.
  - **Mitigation:** Guard koşulunu `_nav_source == 'mouse'` ile sınırla ve test ekle.

- **Risk:** TabbedSettings → MusicSettingsScreen geçişi state makinesini etkileyebilir.
  - **Mitigation:** State geçişini minimal tut; `back` ile settings’e dönüşü netleştir; testle doğrula.

## Success Criteria

- [ ] "burak" cheat’i ile campaign tüm leveller açılır.
- [ ] macOS .app’de Sniper patlama efekti çalışır.
- [ ] Ana menüde panel dışına çıkınca hover kalkar ve Enter tetiklemez.
- [ ] Mod müzikleri playlist tabanlı ayarlanabilir.
- [ ] Extras ekranında Klasik görünür ve çalışır.
- [ ] İlgili testler geçer.

## Notes for Atlas

- macOS Sniper sorununun ana sebebi `tetris_macos_allinone.spec` içindeki `excludes` satırlarıdır (`PIL`/`Pillow`). Önce bunu düzelt.
- Menu hover fix için en düşük riskli çözüm: `_mouse_in_panel` flag + Enter guard.
- Playlist işi için `MusicSettingsScreen` zaten var; mümkünse yeni UI yazmadan state routing ile geri getir.
