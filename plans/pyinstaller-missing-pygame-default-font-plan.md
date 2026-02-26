# Plan: Paketli Build’larda Pygame Varsayılan Font Hatası (Fullscreen/Pencere Toggle)

**Created:** 2026-02-26
**Status:** Ready for Atlas Execution

## Summary

Paketli EXE/.app çalıştırmada grafik ayarlarından tam ekran/pencereli geçişi tetikleyince uygulama yeniden başlatılıyor ve UI fontları yeniden yüklenirken `pygame.font.Font(None, size)` çağrısı `pygame/pkgdata.py` üzerinden `freesansbold.ttf` dosyasını arıyor. Bazı paketlerde bu dosya `_MEIPASS/pygame/` altında bulunmadığı için `FileNotFoundError` oluşuyor; ayrıca `src/ui_theme.py` içindeki `except` bloğu aynı hatalı çağrıyı tekrar ettiği için crash kaçınılmaz.

Hedef: Fullscreen/pencere değişimi sonrası (restart + yeniden font yükleme dahil) paketli Windows EXE ve macOS .app build’larında hatasız çalışmak.

## Context & Analysis

**Observed Trace (user):** `ui_theme.py → pygame/pkgdata.py getResource → freesansbold.ttf missing`.

**Repro/Call chain (repo):**
- `src/settings_screen_tabbed.py` ve/veya `src/graphics_menu.py` fullscreen ayarını değiştirince `apply_display_mode` action’ı döner.
- `src/main.py` içinde `action == 'apply_display_mode'`:
  - fullscreen state değiştiyse `_restart_application()` çağrılır; yeni process açıldığında ekranlar yeniden oluşturulur.
  - bazı ekranlar (örn. `ExtrasScreen`) init’te `_refresh_fonts()` çağırır.
- `src/extras_menu.py` → `_refresh_fonts()` → `src/ui_theme.py` → `UIFonts.get()`.
- `src/ui_theme.py` → `pygame.font.Font(None, scaled_size)` → `pygame.pkgdata.getResource('freesansbold.ttf')`.

**Root cause:**
1. `UIFonts.get()` ve `UIFonts._get_latin_font()` TR/EN gibi normal profilde `pygame.font.Font(None, ...)` kullanıyor.
2. Frozen/onefile paketlerde `pygame/freesansbold.ttf` her zaman bundle’a girmeyebiliyor veya bazı makinelerde temp extract altında bulunamıyor.
3. `UIFonts.get()` içindeki `except` bloğu tekrar `pygame.font.Font(None, ...)` çağırarak aynı hatayı yeniden tetikliyor.

**Relevant Files:**
- `src/ui_theme.py`: `UIFonts.get()` ve `_get_latin_font()` (asıl hata ve fix burada)
- `src/extras_menu.py`: `_refresh_fonts()` (crash tetikleyicisi)
- `src/main.py`: `apply_display_mode` handler + restart akışı
- `src/graphics_menu.py`, `src/settings_screen_tabbed.py`: fullscreen/resolution ayar değişimi
- `tetris.spec`, `tetris_en.spec`, `tetris_playtest.spec`, `tetris_macos.spec`, `tetris_macos_allinone.spec`: PyInstaller datas ayarları

## Implementation Phases

### Phase 1: Regresyon Testi (UIFonts Font(None) başarısız olsa bile crash olmamalı)

**Objective:** `pygame.font.Font(None, ...)` arızalandığında `UIFonts.get()` bir system font fallback ile dönebilmeli ve exception fırlatmamalı.

**Files to Create/Modify:**
- Create: `test_ui_theme_font_fallback.py`

**Tests to Write:**
- `test_ui_fonts_get_falls_back_when_default_font_missing`:
  - `pygame.font.Font` fonksiyonunu monkeypatch’le: ilk arg `None` ise `FileNotFoundError` fırlatsın, değilse orijinali çağırsın.
  - `UIFonts.set_font_profile(font_path=None, ...)` sonrası `UIFonts.get(22, bold=True)` çağrısı **exception fırlatmamalı**.
  - Dönen objenin `render` attribute’u beklenir (pygame Font API).
- (Opsiyonel) `test_ui_fonts_latin_font_fallback`:
  - `_get_latin_font()` dolaylı yolunu tetiklemek için CJK profil/Hybrid path simüle edilebilir; asıl amaç Font(None) yokken bile fallback.

**Acceptance Criteria:**
- [ ] Testler Windows CI/yerel ortamda çalışır (headless durumda `pygame.font.init()` yeterli olmalı).
- [ ] Test, hatanın tam kök nedenini kapsar (Font(None) patlayınca crash yok).

---

### Phase 2: `UIFonts.get()` ve `_get_latin_font()` için Sağlam Fallback Zinciri

**Objective:** UI font sistemi hiçbir koşulda `Font(None)` dosya bağımlılığına kilitlenmesin; paketli build’larda font dosyası eksik olsa da menüler ve fullscreen toggle akışı crash etmesin.

**Files to Modify:**
- Modify: `src/ui_theme.py`

**Steps:**
1. `UIFonts` içine küçük bir yardımcı ekle: örn. `_get_system_font(scaled_size, effective_bold)`.
   - `pygame.font.get_init()` değilse `pygame.font.init()` çağır.
   - Önce `pygame.font.match_font()` ile modern sans-serif adayları dene (`Segoe UI`, `Arial`, `Helvetica`, `DejaVu Sans`).
   - Bulunursa `pygame.font.Font(path, scaled_size)` ile yükle, yoksa `pygame.font.SysFont(None, scaled_size, bold=effective_bold)`.
2. `UIFonts._get_latin_font()` içinde:
   - `_default_font_path` başarısızsa **`Font(None)` yerine** `_get_system_font(...)` kullan.
3. `UIFonts.get()` içinde `font_path` yokken:
   - **`pygame.font.Font(None, scaled_size)` yerine** `_get_system_font(...)` kullan.
4. `except Exception:` bloğunda:
   - Tekrar `Font(None)` çağırma; `_get_system_font(...)` ile güvenli fallback’e düş.

**Acceptance Criteria:**
- [ ] Paketli ortamda `freesansbold.ttf` yoksa bile `UIFonts.get()` crash etmez.
- [ ] Bold istenince (effective_bold) SysFont/Font üzerinde uygulanır.
- [ ] Phase 1 testleri geçer.

---

### Phase 3: PyInstaller Spec’lerinde `freesansbold.ttf`’yi Garanti Et (Belt-and-suspenders)

**Objective:** Kod tarafı fallback güvenli olsa bile, repo genelinde hâlâ `pygame.font.Font(None, size)` kullanan yerler olduğu için (game mode HUD’ları vb.) PyInstaller build’larında pygame default font data’sı da garanti edilsin.

**Files to Modify:**
- Modify: `tetris.spec`
- Modify: `tetris_en.spec`
- Modify: `tetris_playtest.spec`
- Modify: `tetris_macos.spec`
- Modify: `tetris_macos_allinone.spec`

**Implementation Options (choose one, recommend A):**

A) **Explicit single-file include (minimal bundle impact):**
- Spec başında `import pygame` / `from pathlib import Path`.
- `pg_dir = Path(pygame.__file__).resolve().parent`.
- `datas.append((str(pg_dir / 'freesansbold.ttf'), 'pygame'))` eğer dosya varsa.

B) **collect_data_files (more comprehensive, potentially bigger):**
- `from PyInstaller.utils.hooks import collect_data_files`
- `datas += collect_data_files('pygame', includes=['*.ttf'])` (gerekirse bmp de eklenir).

**Acceptance Criteria:**
- [ ] Windows onefile EXE’de runtime path `.../_MEI.../pygame/freesansbold.ttf` mevcut.
- [ ] macOS .app içinde `pygame/freesansbold.ttf` paketlenir (PyInstaller layout’una göre `Contents/Frameworks/pygame/` veya eşdeğeri).

---

### Phase 4 (Recommended): Repo Genelindeki `Font(None)` Kullanımlarını Azalt

**Objective:** Oyun modları/campaign/HUD gibi yerlerde de paketli ortamda font çökmesi yaşanmasın.

**Files to Modify (examples):**
- `src/game_modes.py`, `src/game_modes_advanced.py`, `src/game_modes_extra.py`
- `src/campaign/campaign_mode.py`, `src/campaign/power_ups.py`, `src/campaign/special_blocks.py`
- `src/color_picker.py`

**Approach:**
- Basit ve tutarlı yol: `pygame.font.Font(None, size)` yerine `retro_style.get_font(size, bold=...)` kullan.
  - `retro_style` zaten `match_font` + `SysFont` fallback’li ve CJK profilini de destekliyor.
- Alternatif: yeni bir `src/font_utils.py` ekleyip hem `UIFonts` hem oyun modları buradan ortak fonksiyon kullansın.

**Acceptance Criteria:**
- [ ] `grep` ile `pygame.font.Font(None, ...)` kullanım sayısı belirgin azalır veya sıfırlanır.
- [ ] Oyun modları başlatıldığında font kaynaklı exception yok.

## Open Questions

1. Fullscreen toggle’da restart zorunlu mu?
   - **Option A:** Mevcut davranışı koru (fullscreen değişince restart).
   - **Option B:** Restart yerine sadece `create_display()` ile devam et.
   - **Recommendation:** Şimdilik A (risk düşük). Hata font kaynaklı; restart davranışını değiştirmeye gerek yok.

2. Font görünümü “pygame default” ile aynı kalmalı mı?
   - **Option A:** System font fallback (en sağlam, en az bağımlılık; görünüm değişebilir).
   - **Option B:** Projeye Latin font asset’i ekleyip her yerde onu kullan (görünüm deterministik).
   - **Recommendation:** A + Phase 3 (paketleme) kombinasyonu: en hızlı ve en güvenli.

## Risks & Mitigation

- **Risk:** System font fallback bazı cihazlarda farklı metriklerle UI layout’unu az da olsa değiştirir.
  - **Mitigation:** Font size minimum/maximum clamp zaten var; kritik ekranlarda (Extras/Settings) manuel gözle kontrol.

- **Risk:** Spec’te pygame import edilmesi build-time ortam bağımlılığı yaratır.
  - **Mitigation:** Import’u try/except ile sar, dosya yoksa sadece uyarı bas; build’i kırma.

## Success Criteria

- [ ] Paketli Windows EXE’de grafik ayarlarından fullscreen/pencere geçişi crash yapmaz.
- [ ] Paketli macOS .app’de aynı akış crash yapmaz.
- [ ] `UIFonts.get()` default font dosyası yokken bile çalışır (test ile doğrulanır).
- [ ] Pytest suite yeşil.

## Notes for Atlas

- Bu hata yalnızca UI tarafı değil; repo genelinde `pygame.font.Font(None, ...)` kullanımları var. Phase 2 + Phase 3 birlikte uygulanırsa en hızlı stabilizasyon sağlanır.
- `src/ui_language_profile.py` içinde `_resolve_font_path()` pattern’i PyInstaller uyumlu; gerekirse font path çözümlemede aynı yaklaşım kullanılabilir.
