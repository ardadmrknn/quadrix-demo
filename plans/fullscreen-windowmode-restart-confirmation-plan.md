# Plan: Görüntü Ayarlarında Tam Ekran/Pencere Değişimi İçin “Yeniden Başlatma” Onayı

**Created:** 2026-02-26  
**Status:** Ready for Atlas Execution

## Summary

Kullanıcı Görüntü sekmesinde `Pencere Modu (fullscreen)` değerini değiştirdiğinde oyun şu an anında ekran modunu değiştirmeye çalışıyor (`apply_display_mode`) ve bazı durumlarda otomatik restart’a kadar giden bir fallback zinciri var. İstenen UX: fullscreen↔windowed değişimi denendiği anda **anında uygulamak yerine** ana menü ESC çıkış kutusunun temel stilini kullanan bir **onay kutusu** gösterilecek; kutuda “bu değişiklik için oyunu kapatıp yeniden açmanız gerekecektir” yazacak; **Evet** seçilirse oyun kapanacak (otomatik yeniden açılmayacak), **Hayır** seçilirse değişiklik iptal edilecek.

## Context & Analysis

**Relevant Files:**
- `src/settings_screen_tabbed.py`: Görüntü sekmesi UI’si ve `fullscreen` selector davranışı; yeni modal state + çizim + input intercept burada yapılacak.
- `src/main.py`: `state == 'settings'` event loop dispatcher (`_handle_settings`); yeni action ile “oyunu kapat” davranışı burada yapılacak.
- `src/menu.py`: `Menu._draw_exit_prompt_panel()`; istenen onay kutusunun temel stil referansı (overlay + glass panel + buton stili/hover).
- `src/localization.py`: Yeni onay kutusu metinleri için localization key’leri eklenecek.

**Key Functions/Flows:**
- `TabbedSettingsScreen._cycle_selector('fullscreen')` (settings_screen_tabbed): Şu an `self._set_value('fullscreen', ...)` çağırıyor ve `apply_display_mode` döndürüyor.
- `main._handle_settings`: `action == 'apply_display_mode'` yakalayınca fullscreen değişimini anında uygulamaya çalışıyor; başarısızsa `_restart_application()` ile otomatik restart tetikleyebiliyor.
- `Menu._draw_exit_prompt_panel`: İstenen modal stilinin en “kanonik” implementasyonu.

**Önemli Davranış Notu (Disk Kaydı):**
- `SettingsManager.set()` fullscreen gibi debounced olmayan key’lerde **hemen diske yazar**. Bu yüzden “Hayır” durumunda yanlışlıkla kalıcı ayar yazılmaması için fullscreen değişimini **confirm’e kadar `settings_manager.set()` yapmadan** bekletmek ideal.

## Implementation Phases

### Phase 1: Settings ekranına “restart gerekiyor” fullscreen confirm modali ekle

**Objective:** Fullscreen/windowed seçimi yapıldığında anında ekran modu değişmesin; bunun yerine modal confirm açılsın ve değişiklik pending kalsın.

**Files to Modify:**
- `src/settings_screen_tabbed.py`

**Steps (TDD odaklı):**
1. Yeni state alanlarını `TabbedSettingsScreen.__init__`’e ekle:
   - `self._display_mode_confirm_active: bool = False`
   - `self._display_mode_confirm_prev_fullscreen: bool | None`
   - `self._display_mode_confirm_target_fullscreen: bool | None`
   - `self._display_mode_confirm_yes_rect: pygame.Rect | None`
   - `self._display_mode_confirm_no_rect: pygame.Rect | None`
2. `TabbedSettingsScreen.handle_input()` başına (music picker/keybind/vsync kontrollerinden önce) modal guard ekle:
   - `if self._display_mode_confirm_active: return self._handle_display_mode_confirm(event)`
   - Bu handler ESC/Enter/mouse click ile sonucu belirlemeli.
3. `TabbedSettingsScreen._cycle_selector()` içinde `key == 'fullscreen'` branch’ini değiştir:
   - `prev = self.fullscreen`
   - `target = not prev`
   - UI preview için `self.fullscreen = target` (yalnızca ekranda gösterim)
   - **`self._set_value('fullscreen', ...)` çağırma** (disk yazma yok)
   - modal state’leri doldur: `prev/target`, `active=True`
   - `return None` (veya yeni bir action string; ana fikir: `apply_display_mode` dönmemeli)
4. Modal çizimi ekle: `TabbedSettingsScreen.draw()` sonunda (content çiziminden sonra) 
   - `if self._display_mode_confirm_active: self._draw_display_mode_confirm_panel()`
   - Bu çizim metodu, `Menu._draw_exit_prompt_panel()` stilini baz almalı:
     - koyu dim overlay (0,0,0,~220)
     - `retro_style.draw_glass_panel(... glow=True ...)`
     - title + wrapped body text
     - iki buton: success (Evet) + secondary (Hayır)
     - hover büyüme/glow/border mantığı (minimum kopya; birebir görünüm için menu kodundan uyarlanabilir)
   - Buton rect’leri `self._display_mode_confirm_yes_rect/no_rect` olarak set edilmeli.
5. Input handler: `_handle_display_mode_confirm(event)`
   - **Hayır** (ESC veya mouse ile Hayır):
     - `self.fullscreen = self._display_mode_confirm_prev_fullscreen`
     - pending state temizle, `active=False`
     - `return None`
   - **Evet** (Enter veya mouse ile Evet):
     - `self.settings_manager.set('fullscreen', self._display_mode_confirm_target_fullscreen)` (disk kaydı olur)
     - pending state temizle
     - `return 'quit_game'` (main tarafından yakalanacak)

**Acceptance Criteria:**
- [ ] Görüntü > Pencere Modu değişince modal çıkıyor, ekran modu anında değişmiyor.
- [ ] Modal metni (TR): **“bu değişiklik için oyunu kapatıp yeniden açmanız gerekecektir”** görünüyor.
- [ ] Hayır seçilince selector eski haline dönüyor ve settings dosyası değişmiyor.
- [ ] Evet seçilince settings dosyasına yeni fullscreen değeri yazılıyor ve `quit_game` action üretiliyor.

---

### Phase 2: Main loop’ta “Evet” ile oyunu kapat (restart yok)

**Objective:** Onay kutusunda Evet’e basılınca oyun kapanmalı; otomatik restart/spawn yapılmamalı.

**Files to Modify:**
- `src/main.py`

**Steps:**
1. `_handle_settings()` içinde action dispatch’e yeni branch ekle:
   - `elif action == 'quit_game': running = False`
2. Bu branch’in `_restart_application()` çağırmadığını doğrula.

**Acceptance Criteria:**
- [ ] Evet’e basılınca oyun süreçten çıkıyor ve kendini tekrar açmıyor.

---

### Phase 3: Localization key’leri ekle (TR + EN)

**Objective:** Yeni modal metinleri localization sistemiyle uyumlu olsun.

**Files to Modify:**
- `src/localization.py`

**Steps:**
1. Yeni key’ler ekle (isimler örnek; Atlas uygularken mevcut naming’e göre ayarlayabilir):
   - `display_mode_restart_title`: TR ör. `YENİDEN BAŞLATMA GEREKİYOR` / EN `RESTART REQUIRED`
   - `display_mode_restart_message`: TR **tam cümle** / EN çeviri
   - `yes_plain`: TR `Evet` / EN `Yes`
   - `no_plain`: TR `Hayır` / EN `No`
2. `settings_screen_tabbed.py` çizimde bu key’leri kullan.

**Acceptance Criteria:**
- [ ] TR/EN’de key’ler fallback olmadan doğru metin gösteriyor.

---

### Phase 4: Unit test ekle (pending + confirm akışı)

**Objective:** Fullscreen selector’ın artık `apply_display_mode` tetiklemediğini ve confirm akışının doğru commit/revert yaptığını otomatik testle sabitlemek.

**Files to Create/Modify:**
- Yeni test dosyası (öneri): `test_settings_fullscreen_restart_confirm.py`

**Test Strategy (mevcut stub desenini takip et):**
1. `test_ui_mouse_slider.py` benzeri şekilde `settings_screen_tabbed` import’u için minimal stub modüller kur:
   - `pygame` stub: `Rect`, `KEYDOWN`, `MOUSEBUTTONDOWN`, `K_ESCAPE`, `K_RETURN` (gerekirse `K_KP_ENTER`), basit event objeleri.
   - `localization.t`: key’i döndürebilir.
   - `retro_style`: sadece attribute placeholder yeter.
2. `TabbedSettingsScreen.__new__` ile instance oluştur; gerekli alanları manuel set et:
   - `fullscreen`, `settings_manager` (set çağrılarını yakalayan stub), `_display_mode_confirm_*` alanları.
3. Testler:
   - `_cycle_selector('fullscreen', 1)` çağrısı:
     - `_display_mode_confirm_active` True olmalı
     - `settings_manager.set` **çağrılmamalı**
   - “Hayır” input’u (ESC KEYDOWN):
     - `fullscreen` eski değere dönmeli
     - `settings_manager.set` çağrılmamalı
   - “Evet” input’u (RETURN KEYDOWN):
     - `settings_manager.set('fullscreen', target)` çağrılmalı
     - handler `quit_game` döndürmeli

**Acceptance Criteria:**
- [ ] Yeni testler yeşil.
- [ ] Fullscreen selector değişimi disk kaydı yapmadan pending kalıyor.

---

### Phase 5: Manuel smoke (oyun içi doğrulama)

**Objective:** Gerçek UI’de görünüm ve kapanış davranışı doğru.

**Steps:**
1. Oyun → Ayarlar → Görüntü → Pencere Modu satırında değiştir.
2. Modal görünmeli; metin doğru.
3. Hayır: modal kapanır, değer geri döner.
4. Evet: oyun kapanır.
5. Oyunu manuel tekrar aç; ayarın gerçekten yeni moda geçtiğini doğrula.

## Risks & Mitigation

- **Risk:** Fullscreen selector UI preview değişirken başka ayarlar (ör. resolution enable/disable) beklenmedik değişebilir.
  - **Mitigation:** Modal açıkken tüm event’leri intercept et; kullanıcı başka ayara etkileşemesin.
- **Risk:** `settings_manager.set()` çağrısı “Evet” anında diske yazar; oyun kapanmadan hemen önce IO gecikmesi olabilir.
  - **Mitigation:** `SettingsManager.set` zaten atomic yazıyor; yine de handler akışını kısa tut.
- **Risk:** Stil birebir tutmayabilir.
  - **Mitigation:** `Menu._draw_exit_prompt_panel()` kodunu temel alıp aynı overlay/panel/button hesaplarını kullan.

## Success Criteria

- [ ] Görüntü ayarlarında fullscreen/windowed değişimi anında uygulanmıyor; confirm modal çıkıyor.
- [ ] Modal mesajı istenen Türkçe cümleyi içeriyor.
- [ ] Evet → oyun kapanıyor, otomatik yeniden açılmıyor.
- [ ] Hayır → değişiklik iptal ediliyor (UI + disk ayarı korunuyor).
- [ ] Tüm testler geçiyor.

## Notes for Atlas

- Bu değişiklik sadece Görüntü sekmesindeki `fullscreen` selector’ı için isteniyor; mevcut F12/Alt+Enter gibi runtime toggle davranışlarına dokunmadan başlamak en güvenlisi.
- `apply_display_mode` akışı çözünürlük değişimleri için çalışmaya devam etmeli; fullscreen selector artık bu action’ı döndürmemeli.
