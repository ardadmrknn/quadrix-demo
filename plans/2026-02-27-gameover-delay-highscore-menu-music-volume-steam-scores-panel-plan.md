# Plan: Game Over Gecikmesi, Yüksek Skor Güncelleme, Menü Müzik Ses Seviyesi, Skor Paneli Daraltma

**Created:** 2026-02-27
**Status:** Ready for Atlas Execution

> **ÖNEMLİ:** Tüm kodlamaları Sisyphus subagent yapacaktır. Atlas sadece fazları sıralayıp Sisyphus'a delege edecektir.

## Summary

Bu plan dört bağımsız sorunu çözer:

1. **Game Over Ekranı Gecikme (EXE):** Paketli EXE'de game over ekranı aşırı yavaş — olası nedenler ve çözüm.
2. **Yüksek Skor Tablosu Canlı Güncelleme:** Oyuncu yeni rekor kırdığında oyun içi skor tablosu hemen güncellenmiyor.
3. **Ana Menü Müzik Ses Seviyesi Barı:** Ayarlarda menü müziğine özel ayrı bir ses düzey barı eksik.
4. **Skor Paneli Çerçeve Boyutu:** Ana menüdeki Steam skor panelindeki satır/çerçeveler paneli tamamen kaplamış, daraltılmalı.

## Kullanılan Latin Fontu Bilgisi

Latin alfabesi olan diller (Türkçe, İngilizce, Almanca, Fransızca, İspanyolca, İtalyanca, Portekizce) için proje kendi bünyesinde özel bir font dosyası **KULLANMIYOR**. Bunun yerine sistem fontlarına fallback yapılıyor:

- **Birincil tercih:** `Segoe UI` (Windows'ta genelde mevcut)
- **Alternatifler:** `Arial` → `Helvetica` → `DejaVu Sans` → `Consolas`
- **Son çare:** `pygame.font.SysFont(None, ...)` (pygame default)

Bu fallback zinciri hem `src/retro_style.py` → `get_font()` → `_get_latin_font()` hem de `src/ui_theme.py` → `UIFonts.get()` → `_get_system_font()` içinde uygulanıyor.

CJK dilleri için özel fontlar var:
- Japonca: `font/ki-cho-jis_0310/KikaiChokokuJIS-Md.otf`
- Çince: `font/cinecaption Regular/ChildFunSans-CHS.ttf`
- Korece: `font/paperlogy/Paperlogy-4Regular.ttf`

---

## Sorun 1: Game Over Ekranı Gecikmesi (EXE Build)

### Kök Neden Analizi

Paketli EXE'de game over ekranı gecikmesinin **ana nedeni**, `_draw_game_over_overlay()` içindeki **per-pixel gradient overlay** oluşturma kodudur:

```python
# src/game.py, satır ~4224-4228
overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
for y in range(self.window_height):
    gradient_alpha = int(self._game_over_fade_alpha * 0.8 + 40 * (y / self.window_height))
    pygame.draw.line(overlay, (5, 8, 18, min(gradient_alpha, self._game_over_fade_alpha)), (0, y), (self.window_width, y))
self.screen.blit(overlay, (0, 0))
```

Bu kod **her frame'de** ekran yüksekliği kadar (ör. 1080) `pygame.draw.line()` çağrısı yapıyor. Her çağrı yeni bir RGBA line çizimi → **1080 draw call/frame**. PyInstaller ile paketlenmiş ortamda pygame'in software renderer'ı daha yavaş çalıştığından bu döngü dramatik gecikme yaratıyor.

### Ek Olası Nedenler

1. **Konfeti parçacıkları:** `_draw_confetti()` her frame'de 200'e kadar parçacık için ayrı `pygame.Surface` oluşturup `rotate` yapıyor → yoğun CPU kullanımı.
2. **Peek icon yükleme (`load_image`):** `_draw_game_over_overlay()` her frame'de `os.path.join()` + `load_image()` + `smoothscale()` çağırıyor; cache yoksa her seferinde diskten okuma yapıyor.
3. **`_draw_game_over_overlay()` fonksiyonundaki `_achievement_notif_surface_cache`:** supersample render (2x scale) her benzersiz boyut için ilk frame'de yoğun işlem yapıyor.
4. **Star glow efektleri:** Yıldız çiziminde per-star SRCALPHA surface oluşturma.

### Çözüm Yaklaşımı

Gradient overlay'ı **bir kez oluşturup cache'le**; sonraki frame'lerde sadece alpha değiştirip blit et. Konfeti ve peek icon'u da cache'le.

---

## Sorun 2: Yüksek Skor Tablosu Güncellenmemesi

### Kök Neden

`finalize_run()` → `score_manager.add_score()` çağrılıyor ve skor JSON'a kaydediliyor. Ancak **game over ekranında skor tablosu yeniden okunmuyor**. `_draw_game_over_overlay()` sadece mevcut oyunun skorunu gösteriyor; oyuncu "yeni rekor" bilgisini `_is_new_record` flag'i ile görüyor ama **tablo içeriği güncellenmiyor**.

Ana menüdeki `HighScoreScreen` ise `__init__` sırasında `score_manager` referansı alıyor, dolayısıyla tekrar açılınca güncel verileri gösteriyor. Sorun büyük olasılıkla **ana menüdeki Steam skor panelinin** (`_draw_mystery_leaderboard_panel`) oyun sonrası yenilenmemesi.

### Çözüm

- Oyun bitip ana menüye dönüldüğünde `_load_steam_mode_scores(force=True)` çağrılmalı.
- Ayrıca `HighScoreScreen`'e `score_manager`'ın güncel verisi her `draw()` çağrısında dinamik olarak okunmalı (şu anda `__init__`'te alınan `steam_mode_scores` dict referansı statik kalabiliyor).

---

## Sorun 3: Ana Menü Müzik Ses Seviyesi

### Mevcut Durum

Ayarlarda tek bir `music_volume` slider'ı var (`settings_screen_tabbed.py`, satır 168). Bu slider **hem** oyun içi müziği **hem** menü müziğini kontrol ediyor (ikisi aynı `SoundManager.music_volume` değerini kullanıyor).

Şu anda `menu_music_volume` diye ayrı bir ayar yok. `sound.py` içinde `track_volumes` sistemi var ama boş (`_default_track_volumes()` → `{}`).

### Çözüm

`menu_music_volume` adında yeni bir setting ekleyip ayarlar ekranındaki "MÜZİK" bölümüne "Ana Menü Müzik Seviyesi" barı koymak. `menu_sound` oluşturulurken bu değeri `set_music_volume()` ile uygulamak.

---

## Sorun 4: Steam Skor Paneli Çerçeve Boyutu

### Kök Neden

`menu_layout_runtime.json` içindeki `steam_scores` paneli override'ı çok geniş:

```json
"steam_scores": {
  "x_pct": 0.601042,
  "y_pct": 0.464815,
  "w_pct": 0.251563,
  "h_pct": 0.434259,
}
```

Bu da 1920×1080'de yaklaşık **483×469 px** boyutunda bir panel oluşturuyor. Bunun yanı sıra `_draw_mystery_leaderboard_panel()` içindeki dinamik boyutlandırma kodu (`panel_w`, `panel_h`) da geniş hesaplıyor.

### Çözüm

`menu_layout_runtime.json` içindeki `steam_scores` boyutlarını eski hallerine küçültmek + `_draw_mystery_leaderboard_panel()` fallback boyutlarını daraltmak.

---

## Implementation Phases

### Phase 1: Game Over Overlay Performans Optimizasyonu

**Objective:** Game over ekranı gecikmesini ortadan kaldır. Gradient overlay her frame yerine cache'lensin.

**Sisyphus Talimatları:**

**Files to Modify:**
- `src/game.py`: `_draw_game_over_overlay()` metodu

**Tests to Write (TDD - Test First):**
- Create: `test_gameover_overlay_performance.py`
  - `test_gradient_overlay_cached`: `_draw_game_over_overlay()` üst üste iki kez çağrıldığında gradient Surface'inin yeni bir allocation yapmadığını doğrula (`id()` veya cache key kontrolü).
  - `test_peek_icon_cached`: Peek icon'un her frame yüklenmediğini doğrula (mock `load_image`, sadece 1 kez çağrıldığını assert et).
  - `test_confetti_no_per_particle_surface_for_opaque_circles`: Opak dairelerin doğrudan `pygame.draw.circle()` ile çizildiğini doğrula.

**Uygulama Adımları:**

1. **Gradient Overlay Cache:** `_draw_game_over_overlay()` başında bir kez `_go_gradient_cache` oluştur:
   ```python
   cache_key = (self.window_width, self.window_height)
   if getattr(self, '_go_gradient_cache_key', None) != cache_key:
       overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
       for y in range(self.window_height):
           alpha = int(240 * 0.8 + 40 * (y / self.window_height))
           alpha = min(alpha, 240)
           pygame.draw.line(overlay, (5, 8, 18, alpha), (0, y), (self.window_width, y))
       self._go_gradient_cache = overlay
       self._go_gradient_cache_key = cache_key
   # Her frame'de sadece alpha ayarla ve blit et
   self._go_gradient_cache.set_alpha(self._game_over_fade_alpha)
   self.screen.blit(self._go_gradient_cache, (0, 0))
   ```

2. **Peek Icon Cache:** `__init__` veya ilk erişimde bir kez yükle, `_go_peek_icon_surf` attribute'unda tut.

3. **Konfeti Optimizasyon:** Opak dairelerde `pygame.Surface` oluşturma yerine doğrudan `pygame.draw.circle()` kullan. Dikdörtgenler için rotate cache kullan.

**Acceptance Criteria:**
- [ ] Game over overlay ilk açılışı < 50ms
- [ ] Testler geçer
- [ ] FPS > 55 game over ekranında (düşük özellikli makine simülasyonu)

---

### Phase 2: Yüksek Skor Tablosu Canlı Güncelleme

**Objective:** Oyuncu yeni rekor kırdığında hem oyun içi skor tablosu hem ana menü skor paneli güncellensin.

**Sisyphus Talimatları:**

**Files to Modify:**
- `src/main.py`: Oyun döngüsü sonrası menüye dönüşte skor yenileme
- `src/menu.py`: `HighScoreScreen.__init__` ve/veya `draw()` metodunda veri yenileme

**Tests to Write (TDD - Test First):**
- Create: `test_highscore_refresh_after_game.py`
  - `test_score_manager_reflects_new_score`: `score_manager.add_score()` sonrası `get_top_scores()` hemen yeni skoru döndürür.
  - `test_high_score_screen_uses_latest_data`: `HighScoreScreen.draw()` çağrıldığında `user_manager.get_mode_highscores()` ile güncel veri çekilir.
  - `test_steam_mode_scores_force_refresh_after_game`: Oyun sonrası `_load_steam_mode_scores(force=True)` tetiklenir.

**Uygulama Adımları:**

1. `src/main.py`'de oyun (*herhangi bir mod*) bitip `'menu'` action'ı dönünce:
   - `_load_steam_mode_scores(force=True)` çağır.
   - `menu.steam_mode_scores = steam_mode_scores_cache` ata.
   - High score screen'e de güncel `score_manager` referansı geçer (zaten geçiyor, doğrula).

2. `src/menu.py` → `HighScoreScreen.draw()`: Her `draw()` çağrısında `self.score_manager.get_top_scores()` çağırarak güncel veriyi al (performans kaygısı yok — JSON bellekte).

**Acceptance Criteria:**
- [ ] Oyun bitip ana menüye dönüldüğünde skor tablosu güncel.
- [ ] HighScoreScreen her açılışta en son skorları gösteriyor.
- [ ] Testler geçer.

---

### Phase 3: Ana Menü Müzik Ses Seviyesi Barı

**Objective:** Ayarlara "Ana Menü Müzik Seviyesi" slider'ı ekle; menü müziği ayrı ses seviyesiyle çalabilsin.

**Sisyphus Talimatları:**

**Files to Modify:**
- `src/settings_manager.py`: Yeni `menu_music_volume` default ayarı
- `src/settings_screen_tabbed.py`: Yeni slider UI öğesi + change handler
- `src/sound.py`: `set_menu_music_volume()` veya `track_volumes` ile menü müziği ses düzeyi ayrımı
- `src/main.py`: `menu_sound` oluşturulurken `menu_music_volume` uygulaması
- `src/localization.py`: `menu_music_volume` translation key'leri

**Tests to Write (TDD - Test First):**
- Create: `test_menu_music_volume_setting.py`
  - `test_settings_manager_has_menu_music_volume_default`: `settings_manager.default_settings` içinde `menu_music_volume` key'i 0.3 değeriyle mevcut.
  - `test_settings_tabbed_has_menu_music_volume_slider`: Ayar ekranı build edildiğinde müzik bölümünde `menu_music_volume` slider'ı var.
  - `test_menu_music_volume_applied_to_sound_manager`: `menu_music_volume` değiştirildiğinde `menu_sound.set_music_volume()` ilgili değerle çağrılır.

**Uygulama Adımları:**

1. **`src/settings_manager.py`:**
   - `default_settings` dict'ine `'menu_music_volume': 0.3` ekle.
   - `FLOAT_KEYS` listesine `'menu_music_volume'` ekle.

2. **`src/localization.py`:**
   - `menu_music_volume` key'i ekle:
     ```python
     'menu_music_volume': {
         'tr': 'Ana Menü Müzik Seviyesi',
         'en': 'Menu Music Volume',
         'de': 'Menümusik-Lautstärke',
         'fr': 'Volume Musique Menu',
         'es': 'Volumen Música Menú',
         'it': 'Volume Musica Menu',
         'pt': 'Volume Música Menu',
         'ja': 'メニュー音楽音量',
         'zh': '菜单音乐音量',
         'ko': '메뉴 음악 볼륨',
     },
     ```

3. **`src/settings_screen_tabbed.py`:**
   - `_build_sound_items()` içinde mevcut `music_volume` slider'ının hemen altına yeni slider ekle:
     ```python
     items.append({
         'type': 'slider', 'key': 'menu_music_volume',
         'loc_key': 'menu_music_volume',
         'label_tr': 'Ana Menü Müzik Seviyesi', 'label_en': 'Menu Music Volume',
         'min': 0.0, 'max': 1.0, 'step': 0.05, 'suffix': '%', 'percent': True,
     })
     ```
   - `_reload_values_from_settings()` içinde `self.menu_music_volume = sm.get('menu_music_volume', 0.3)` ekle.
   - Slider change handler'da (`_handle_slider_change`) `'menu_music_volume'` key'ini `'change_menu_music_volume'` action döndürecek şekilde ekle.
   - `_music_volume_vis` benzeri `_menu_music_volume_vis` animasyon değişkeni ekle.

4. **`src/main.py`:**
   - `menu_sound` oluşturulduktan sonra `menu_music_volume` ayarını `menu_sound.set_music_volume()` ile uygula (menü müziği çalarken).
   - `'change_menu_music_volume'` action'ı geldiğinde `menu_sound.set_music_volume(settings_screen.menu_music_volume)` çağır.
   - Oyun içi müzik hâlâ `music_volume` ile kontrol edilsin.

**Acceptance Criteria:**
- [ ] Ayarlar ekranında "Ana Menü Müzik Seviyesi" barı görünür.
- [ ] Bar kaydırıldığında menü müziği ses seviyesi değişir.
- [ ] Oyun içi müzik ses seviyesi bu bardan etkilenmez.
- [ ] Testler geçer.

---

### Phase 4: Steam Skor Paneli Çerçeve Daraltma

**Objective:** Ana menüdeki Steam skor panelindeki çerçeveyi daralt ve eski boyutuna getir.

**Sisyphus Talimatları:**

**Files to Modify:**
- `menu_layout_runtime.json`: `steam_scores` rect boyutları
- `src/menu.py`: `_draw_mystery_leaderboard_panel()` fallback boyutları (opsiyonel)

**Tests to Write (TDD - Test First):**
- Create: `test_steam_scores_panel_size.py`
  - `test_steam_scores_panel_width_reasonable`: `menu_layout_runtime.json` içindeki `steam_scores.w_pct` değeri `0.22`'den küçük (eski boyut ~0.198).
  - `test_steam_scores_panel_not_overlap_actions`: Panel rektangelinin diğer aksiyon kartlarıyla çakışmadığını doğrula.

**Uygulama Adımları:**

1. **`menu_layout_runtime.json`:** `steam_scores` rect'ini daralt:
   ```json
   "steam_scores": {
     "x_pct": 0.760417,
     "y_pct": 0.453704,
     "w_pct": 0.197917,
     "h_pct": 0.342593,
     "title": "Steam Skor Tablosu"
   }
   ```
   > Bu değerler ~380×370 px'e denk gelir (1920×1080 referans). Orijinal `tools/menu_layout_editor.py` satır 86'daki değerlerle uyumlu: `pygame.Rect(1460, 490, 380, 370)`.

2. **`src/menu.py` → `_draw_mystery_leaderboard_panel()` (opsiyonel):** Fallback boyutlarını güncelle:
   - `panel_w = max(300, min(int(380 * scale), width // 3))` → zaten uygun, dokunma.
   - `row_h` hesaplamasında satır arası boşluğu azalt: `row_h = max(s(26), ...)` yerine isteğe bağlı `max(s(24), ...)`.

**Acceptance Criteria:**
- [ ] Skor paneli önceki dar boyutunda görünür.
- [ ] Paneldeki tek kişi çerçevesi paneli tamamen kaplamamalı.
- [ ] Testler geçer.

---

## Phase Execution Order

| Sıra | Phase | Bağımlılık | Tahmini Süre |
|------|-------|------------|-------------|
| 1 | Phase 1 - Game Over Performans | Yok | Orta |
| 2 | Phase 4 - Panel Daraltma | Yok | Küçük |
| 3 | Phase 2 - Skor Güncelleme | Yok | Orta |
| 4 | Phase 3 - Menü Müzik Volume | Yok | Orta |

Phase 1 ve Phase 4 birbirinden bağımsız olduğu için paralel çalıştırılabilir. Phase 2 ve Phase 3 de bağımsızdır.

## Risks & Mitigation

- **Risk:** Gradient cache alpha geçişi kaybolabilir → `set_alpha()` ile geçiş animasyonu korunur.
- **Risk:** `menu_music_volume` eklenmesi mevcut `music_volume` davranışını bozabilir → oyun içi müzik hâlâ orijinal `music_volume` kullanır; sadece menü müziği farklılaşır.
- **Risk:** Panel boyutları bazı çözünürlüklerde uyumsuz olabilir → min/max clamp zaten var; test ile doğrulanır.

## Success Criteria

- [ ] Paketli EXE'de game over ekranı < 1 saniyede açılır (gecikme hissedilmez).
- [ ] Yeni rekor kırıldığında ana menüye dönüldüğünde skor tablosu güncel.
- [ ] Ayarlarda "Ana Menü Müzik Seviyesi" barı çalışır.
- [ ] Steam skor paneli dar boyutta, taşma yok.
- [ ] Tüm pytest testleri yeşil.

## Notes for Atlas

- **Tüm kodlamaları Sisyphus yapacak.** Atlas her Phase'i tek tek Sisyphus'a delege etmeli.
- Phase 1 en kritik: EXE kullanıcıları doğrudan etkiliyor.
- Phase 4 en hızlı: sadece JSON değişikliği + isteğe bağlı kod düzenlemesi.
- Her Phase için Sisyphus'a: "önce test yaz, fail gör, sonra implement et, testleri geçir" TDD döngüsünü hatırlat.
