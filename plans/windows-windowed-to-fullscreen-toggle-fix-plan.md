# Plan: Windows’ta Pencere → Tam Ekran Geçişinin Düzeltmesi (Pygame/SDL2)

**Created:** 2026-02-26  
**Status:** Ready for Atlas Execution

## Summary

Windows build’da (özellikle DPI scaling açıkken) pencere modundan “Tam Ekran”a geçişin bazen hiç gerçekleşmemesi veya ekranı tam kaplamaması, mevcut `create_display()` implementasyonunun “borderless fullscreen (NOFRAME)” yolunda **logical/native çözünürlük karışması** ve `SDL_VIDEO_CENTERED` gibi SDL hint/env etkileşimleriyle ilişkilendiriliyor. Bu plan; Windows’ta borderless fullscreen için **fiziksel piksel çözünürlüğünü** kullanmayı, fullscreen geçişi sırasında `SDL_VIDEO_CENTERED` etkisini **geçici olarak devre dışı** bırakmayı ve gerektiğinde **exclusive fullscreen fallback** uygulamayı hedefler. Ek olarak, mod değişimi sonrası event kuyruğu temizliğiyle “sessizce eski moda dönme” riskini azaltır.

## Context & Analysis

### Yapılan önceki değişiklik (regresyon bağlamı)

- Daha önce `apply_display_mode` akışında fullscreen değişiminde Windows/Linux’ta da restart yapılıyordu.
- Bu restart, Windows’ta yeniden açılışta geçici “yanlış boyut/layout” problemini tetiklediği için restart davranışı yalnızca macOS’a sınırlandı.
- Sonuç: Windows’ta artık pencere↔tam ekran geçişi *aynı process içinde* `create_display()` ile yapılmak zorunda. Bu da SDL/flag/DPI edge-case’lerini daha görünür hale getiriyor.

### Relevant Files

- `src/platform_utils.py`: `create_display()`, `get_display_flags()`, `get_native_resolution()`
- `src/main.py`: `_rebuild_display()`, `_toggle_fullscreen()`, `apply_display_mode` action handler
- `src/settings_manager.py`: `fullscreen`, `borderless_fullscreen`, `resolution` değerleri

### Key Findings (muhtemel kök nedenler)

- **DPI scaling:** `pygame.display.Info().current_w/h` bazı durumlarda **logical** boyut döndürebilir; borderless fullscreen için bu değer kullanılırsa ekran tam dolmaz.
- **`SDL_VIDEO_CENTERED=1`:** Windowed başlangıç için faydalı olsa da fullscreen geçişinde borderless pencereyi (NOFRAME) merkezlemeye çalışıp `0,0` konumlandırmayı bozabilir; çoklu monitörde yanlış davranış ihtimali artar.
- **Flag karmaşası:** SDL2/Pygame 2’de `HWSURFACE` pratikte etkisiz/legacy; bazı sürücü kombinasyonlarında fullscreen geçişini kararsızlaştırabilir.
- **Fallback eksikliği:** Borderless fullscreen set_mode sonucu hedef boyuta ulaşamazsa otomatik olarak exclusive fullscreen’e düşen bir mekanizma yok.
- **Event kuyruğu:** `set_mode()` sonrası biriken WINDOW/RESIZE event’leri sonraki frame’lerde beklenmedik davranışlara yol açabilir.

## Implementation Phases

### Phase 1: Repro + Minimal Diagnostics (sadece log)

**Objective:** Kullanıcı makinesinde hangi path’in (borderless/exclusive) kullanıldığını ve set_mode sonucunu netleştirmek.

**Files to Modify:**
- `src/main.py` veya `src/platform_utils.py` (mevcut logging yaklaşımına göre)

**Steps:**
1. `DEBUG_DISPLAY_MODE=1` (env var) veya mevcut bir debug flag ile, sadece toggle anında şunları logla:
   - requested: fullscreen/borderless/resolution
   - driver: `pygame.display.get_driver()`
   - requested flags + actual surface size (`pygame.display.get_surface().get_size()`)
   - Windows’ta DPI ölçeği (varsa mevcut helper) ve “physical” ekran ölçüsü
2. Loglar default kapalı olmalı; UX’e yeni menü eklenmemeli.

**Acceptance Criteria:**
- [ ] Windowed→Fullscreen denemesinde logdan hangi branch’e girildiği okunabiliyor
- [ ] set_mode sonrası surface boyutu ve driver net

---

### Phase 2: Windows Borderless Fullscreen’i DPI-doğru hale getir

**Objective:** Windows’ta borderless fullscreen için “native çözünürlük” değerini DPI’dan bağımsız, fiziksel piksel olarak almak.

**Files to Modify:**
- `src/platform_utils.py`

**Implementation Details:**
1. Windows’a özel helper ekle (ör. `_get_windows_physical_resolution()`):
   - `ctypes.windll.user32.GetSystemMetrics(0/1)` (SM_CXSCREEN/SM_CYSCREEN)
   - Hata olursa mevcut `get_native_resolution()` fallback
2. `create_display()` içinde `fullscreen and borderless and IS_WINDOWS` branch’inde `native_w/h` olarak bu physical değerleri kullan.

**Tests to Write:**
- Yeni root testi (örn. `test_platform_utils_display_resolution.py`):
  - `IS_WINDOWS=True` olacak şekilde monkeypatch
  - `ctypes` çağrısını monkeypatch edip (1920,1080) döndür
  - `pygame.display.set_mode` mock’lanıp çağrılan boyutların physical olduğunu doğrula

**Acceptance Criteria:**
- [ ] Windows’ta borderless fullscreen set_mode boyutu DPI’dan bağımsız
- [ ] Testler geçiyor

---

### Phase 3: Fullscreen geçişinde SDL centered etkisini güvenli şekilde devre dışı bırak

**Objective:** Fullscreen/borderless geçişinde pencerenin merkezlenmesini önleyip `0,0` konumlandırma ile tam kaplamayı stabilize etmek.

**Files to Modify:**
- `src/platform_utils.py`

**Implementation Details:**
1. `create_display()` içinde fullscreen set_mode çağrısı etrafında:
   - `SDL_VIDEO_CENTERED`’ı geçici olarak `pop` et
   - Borderless fullscreen path’inde `SDL_VIDEO_WINDOW_POS='0,0'` ayarla (önceden set edilmişse eski değeri saklayıp geri koy)
2. İş bitince env değerlerini geri yükle.

**Tests to Write:**
- `test_platform_utils_display_env_hints.py`:
  - `os.environ['SDL_VIDEO_CENTERED']='1'` varken fullscreen çağrısı yap
  - `pygame.display.set_mode` mock’u içinde çağrı anında env’de centered olmadığını doğrula
  - Çağrı sonrası env’in eski haline döndüğünü doğrula

**Acceptance Criteria:**
- [ ] Fullscreen set_mode sırasında `SDL_VIDEO_CENTERED` etkisi yok
- [ ] Testler geçiyor

---

### Phase 4: Flag temizliği + Fallback (Borderless başarısızsa Exclusive)

**Objective:** Borderless fullscreen set_mode hedef boyuta ulaşamazsa otomatik olarak exclusive fullscreen’e düşmek; legacy flag’leri sadeleştirmek.

**Files to Modify:**
- `src/platform_utils.py`

**Implementation Details:**
1. SDL2/Pygame2 için `HWSURFACE` kullanımını kaldır (en azından fullscreen/borderless branch’lerinden).
2. Borderless fullscreen set_mode sonrası:
   - `surface = pygame.display.get_surface()`
   - `surface.get_size()` hedef boyuttan küçük/uyumsuzsa:
     - ikinci deneme: `pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)` (exclusive fallback)
3. Fallback yalnızca başarısızlık tespit edilirse devreye girmeli (normal durumda davranış değişmesin).

**Tests to Write:**
- `test_platform_utils_display_fallback.py`:
  - `pygame.display.set_mode` mock: ilk çağrıda küçük surface döndürsün; ikinci çağrının FULLSCREEN flag’iyle yapıldığını doğrula

**Acceptance Criteria:**
- [ ] Borderless başarısızsa exclusive fullscreen ile toparlıyor
- [ ] Normal koşulda tek çağrı ile devam

---

### Phase 5: Mod değişimi sonrası event kuyruğu temizliği (minimum)

**Objective:** set_mode sonrası biriken WINDOW/RESIZE event’lerinin sonraki frame’lerde ikinci bir değişimi tetiklemesini önlemek.

**Files to Modify:**
- `src/main.py` (`_rebuild_display()` sonrası) veya `src/platform_utils.py` (create_display sonrası)

**Implementation Details:**
- Mod değişimi bittiğinde:
  - `pygame.event.pump()`
  - `pygame.event.clear([pygame.VIDEORESIZE, pygame.WINDOWRESIZED])` (pygame sürümüne göre uygun sabitler)
  - Gerekirse tek bir `pygame.display.flip()`

**Tests:**
- Bu bölüm için unit test sınırlı; en azından çağrıların yapıldığını doğrulayan mock tabanlı test eklenebilir.

**Acceptance Criteria:**
- [ ] Hızlı ardışık geçişlerde modun “geri dönmesi” azalıyor

---

### Phase 6: Frozen (PyInstaller) smoke doğrulaması

**Objective:** EXE’de gerçek koşullarda pencere→tam ekran ve tam ekran→pencere geçişi sorunsuz.

**Steps:**
1. Windows’ta DPI scaling: %100, %125, %150 ile ayrı ayrı dene.
2. Menüden `Ayarlar > Görüntü > Pencere Modu`:
   - Pencere → Tam Ekran
   - Tam Ekran → Pencere
   - 10 kez tekrarla
3. Çoklu monitör varsa: hangi ekrana geçtiğini doğrula.
4. `DEBUG_DISPLAY_MODE=1` ile log al; fallback devreye giriyor mu bak.

**Acceptance Criteria:**
- [ ] Pencere → Tam Ekran geçişi her seferinde çalışıyor
- [ ] Tam Ekran → Pencere geçişi bozulmuyor
- [ ] Önceki Windows “restart sonrası bozuk layout” regresyonu geri gelmiyor

## Open Questions

1. Varsayılan olarak `borderless_fullscreen=True` kalmalı mı?
   - **Option A:** Aynen bırak (yalnızca failure’da exclusive fallback). Değişiklik minimum.
   - **Option B:** Windows’ta varsayılanı exclusive yap. Daha deterministik olabilir ama UX/ayar davranışı değişir.
   - **Recommendation:** Option A (davranış değişikliği olmadan sağlamlaştırma).

2. `HWSURFACE` tamamen kaldırılmalı mı?
   - **Option A:** Fullscreen/borderless branch’lerinden kaldır. Risk düşük.
   - **Option B:** Her yerden kaldır. Daha temiz ama beklenmedik legacy etkiler olabilir.
   - **Recommendation:** Option A ile başla; gerekirse genişlet.

## Risks & Mitigation

- **Risk:** Env var restore edilmezse windowed başlangıç davranışı değişebilir.
  - **Mitigation:** `try/finally` ile geri yükleme + unit test.
- **Risk:** Exclusive fallback bazı sistemlerde alt-tab davranışını etkileyebilir.
  - **Mitigation:** Fallback’i sadece “borderless gerçekten başarısız” tespitinde çalıştır.
- **Risk:** DPI physical çözünürlük helper’ı bazı sistemlerde farklı monitor’ı raporlayabilir.
  - **Mitigation:** İlk etapta primary monitor için; multi-monitor için log + gerekirse SDL display index araştırması.

## Success Criteria

- [ ] Windows’ta pencere→tam ekran geçişi güvenilir
- [ ] DPI scaling açıkken borderless fullscreen ekranı tam kaplıyor
- [ ] Tam ekran→pencere geçişi ve menü layout stabil
- [ ] Tüm mevcut testler + yeni testler yeşil

## Notes for Atlas

- Bu plan yeni UI eklemeyi amaçlamaz; sadece display mode geçişinin altyapısını sağlamlaştırır.
- Önce Phase 1 ile log toplayıp gerçek failure modunu doğrula; sonra Phase 2–4 ile kalıcı düzeltmeyi uygula.
- Eğer pygame sürümünde `pygame.WINDOWRESIZED` yoksa, event sabitleri sürüme göre koşullu kullanılmalı.
