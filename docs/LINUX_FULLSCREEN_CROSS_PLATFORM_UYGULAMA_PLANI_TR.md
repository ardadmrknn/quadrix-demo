<!-- DEMO UYARLAMASI (2026-10-05): Bu belge v2'den (quadrix-main, 9ff47e4
+ 466f324 commit zinciri) quadrix-demo'ya taşındı. Demo farkları:
DUZ-013 dummy-fallback sinyali demo'da yoktur (çift başarısızlıkta son-çare
düz pygame.Surface döner); resolve_videoresize_display_params API'si ve
_set_mode_with_vsync'in Windows/macOS yollarındaki kullanımı v2'ye özgüdür
(demo'da adaptör yalnız Linux fullscreen dalında kullanılır); telemetri
veri dizini demo data_paths çözümlemesine göredir. Kök-neden analizi,
algoritma ve vaka listesi aynen geçerlidir. -->

# Quadrix Linux Gerçek Fullscreen Düzeltme Planı

## 1. Amaç ve kapsam

Bu doküman, Linux ELF/Steam build’inde oyun `Fullscreen` seçili olmasına rağmen masaüstü üst panelinin ve arka plandaki pencere/tab çubuğunun görünür kalması sorununu çözmek için hazırlanmıştır.

Hedefler:

- Linux’ta `Fullscreen` seçeneğini gerçek SDL fullscreen olarak uygulamak.
- X11, XWayland ve mümkün olduğu ölçüde native Wayland oturumlarında paneli gizlemek.
- Native ekran boyutunu doğru kullanmak.
- Sanal tuval, mouse koordinatları, resize, Alt+Tab ve Steam akışlarını bozmamak.
- Mevcut Windows borderless/Steam overlay ve macOS AppKit/borderless yollarını değiştirmemek.
- Kaynak çalıştırma ile paketlenmiş Linux ELF’in aynı davranışı vermesini sağlamak.

Bu dosya uygulama planıdır. Uygulayıcı AI, gerçek Linux runtime ve paketli ELF testleri tamamlanmadan işi bitmiş saymamalıdır.

---

## 2. Mevcut bulgu ve kök neden

### 2.1. Kullanıcı ekran görüntüsünün anlamı

Son görüntüde oyun yüzeyi önceki küçük pencere durumuna göre büyümüştür; fakat Linux masaüstü paneli hâlâ üstte görünmektedir. Bu, oyun çiziminin veya sanal tuvalin bozuk olduğundan çok pencerenin compositor tarafından kullanılabilir work-area içine yerleştirildiğini gösterir.

Sorun iki ayrı parçaya ayrılmalıdır:

1. **Native çözünürlük ölçümü:** Önceki güncelleme bunu büyük ölçüde düzeltmiştir.
2. **Gerçek fullscreen window state:** Hâlâ çözülmemiştir; mevcut Linux yolu borderless pencere açmaktadır.

### 2.2. Native çözünürlük değişikliği korunmalı

`src/platform_utils.py:1022-1071` içindeki `get_native_resolution()` Linux’ta `pygame.display.get_desktop_sizes()` kullanmaktadır.

Bu değişiklik korunmalıdır. `pygame.display.Info().current_w/current_h`, ilk `set_mode()` sonrasında eski pencere boyutunu raporlayabildiği için Linux’ta native çözünürlük kaynağı olarak güvenilir değildir. `get_desktop_sizes()` yalnızca boyut ölçümünü düzeltir; fullscreen state’i garanti etmez.

### 2.3. Problemli ortak yol

`src/platform_utils.py:1790-1845` aralığında Windows ve Linux aynı yolu kullanmaktadır:

```python
flags_bl = pygame.NOFRAME | pygame.DOUBLEBUF
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
surface = pygame.display.set_mode((native_w, native_h), flags_bl)
```

Bu gerçek SDL fullscreen değildir. Pencereyi çerçevesiz yapıp native boyutta `(0, 0)` konumuna yerleştirmeyi dener. Linux X11/Wayland compositor’ı bunu tam ekran isteği olarak kabul etmeyip pencereyi panelin altındaki work-area’ya sıkıştırabilir.

### 2.4. Mevcut fallback neden yetmiyor

Mevcut fallback yalnızca `surface.get_size()` değerine bakmaktadır:

```python
actual_w, actual_h = surface.get_size()
if abs(actual_w - native_w) > 4 or abs(actual_h - native_h) > 4:
    surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
```

Linux’ta surface `1920x1080` raporlayıp pencere yine panelin altında kalabilir. Bu nedenle boyut eşleşmesi gerçek fullscreen kanıtı değildir ve `pygame.FULLSCREEN` fallback’i hiç çalışmayabilir.

### 2.5. Ayar akışı

- `src/main.py:255-270`: `_resolve_startup_display()` fullscreen kararını üretir.
- `src/main.py:273-295`: `_resolve_rebuild_geometry()` geçiş geometrisini üretir.
- `src/settings_manager.py`: `borderless_fullscreen` obsolete ayarlar içinde görünmektedir.

Linux çözümü ayar sistemini yeniden tasarlamamalıdır. Fullscreen kararı aynı kalmalı; platforma özgü pencere oluşturma yalnızca `platform_utils.create_display()` içinde ayrıştırılmalıdır.

---

## 3. Platform izolasyonu

### 3.1. Windows sözleşmesi — dokunma

Mevcut Windows yolu şunlara bağlıdır:

- borderless fullscreen,
- DPI-bağımsız fiziksel çözünürlük,
- OpenGL/GL compatibility hazırlığı,
- Windows-only SDL2 Steam overlay,
- tek pencere ve gizli `set_mode` yüzeyi,
- `SDL_VIDEO_WINDOW_POS` / `SDL_VIDEO_CENTERED` geçici yönetimi.

Linux patch’i:

- `IS_WINDOWS` branch’ine girmemeli,
- Windows flag sırasını değiştirmemeli,
- `_GL_WINDOW_REQUEST` mantığına dokunmamalı,
- `src/sdl2_overlay.py` Windows davranışını değiştirmemeli,
- mevcut Windows display testlerini bozmayacak şekilde yazılmalıdır.

### 3.2. macOS sözleşmesi — dokunma

`src/platform_utils.py:1742-1788` macOS’a özel yoldur. `pygame.FULLSCREEN` yerine `NOFRAME`, AppKit presentation options ve `SDL_VIDEO_MAC_FULLSCREEN_SPACES=0` kullanımı macOS crash/Spaces davranışları nedeniyle korunmalıdır.

Linux çözümü macOS branch’ine ortak refactor olarak taşınmamalıdır.

### 3.3. Linux için yeni izole branch

`create_display()` içinde platform davranışı açıkça ayrılmalıdır:

```python
if IS_MACOS:
    # mevcut macOS yolu
elif IS_LINUX and fullscreen:
    # yeni Linux native fullscreen yolu
elif IS_WINDOWS and fullscreen and borderless:
    # mevcut Windows yolu
else:
    # mevcut genel/windowed yol
```

Linux düzeltmesi ortak `flags_bl` üretimine gizlenmemelidir.

---

## 4. Önerilen Linux çözümü

### 4.1. Birincil yöntem

Linux fullscreen isteğinde ilk deneme `pygame.FULLSCREEN` olmalıdır:

```python
linux_flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
surface = _set_mode_with_vsync((0, 0), linux_flags)
```

Amaç:

- SDL’ye açık fullscreen window state göndermek,
- panel dahil masaüstü davranışını compositor’a bırakmak,
- manuel `NOFRAME + WINDOW_POS=0,0` yaklaşımını öncelikli olmaktan çıkarmak,
- native çözünürlüğü manuel pencere boyutu gibi değil display mode olarak seçtirmek.

Uygulayıcı AI, kurulu pygame-ce runtime’ında `(0, 0) + pygame.FULLSCREEN` dönüş surface boyutunu, flag’lerini ve pencere konumunu gerçek probe ile doğrulamalıdır.

### 4.2. Desktop/exclusive ayrımı

İlk çözümde doğrudan ctypes ile SDL sembollerine bağlanılmamalıdır. Bu, ELF’e yeni SDL ABI bağımlılığı ekleyebilir ve PyInstaller paketini kırabilir.

Sıra:

1. Canonical `pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)` denemesi.
2. Bu yol belirli pygame-ce/SDL kombinasyonlarında yetersiz kalırsa, kurulu sürümün `pygame.Window` veya `pygame._sdl2.video.Window.set_fullscreen(desktop=True)` API’si bağımsız probe ile incelenir.
3. API’nin `display.Surface`, `flip()`, virtual canvas ve event queue ile güvenli birlikte çalıştığı kanıtlanmadan ana akışa alınmaz.
4. `Window.from_display_module()` gibi deprecated veya display/Window API’sini karıştırmama uyarısı taşıyan yollar birincil çözüm yapılmaz.

### 4.3. Fallback sırası

Native Linux fullscreen `pygame.error` ile başarısız olursa:

1. Hata loglanır.
2. Linux borderless fallback denenir:

   ```python
   flags_bl = pygame.NOFRAME | pygame.DOUBLEBUF
   surface = _set_mode_with_vsync((native_w, native_h), flags_bl)
   ```

3. Sonuç `selected_mode=linux-borderless-fallback` olarak raporlanır.
4. Fallback’in surface boyutu native olsa bile gerçek fullscreen başarılı varsayılmaz.
5. İkinci yol da başarısızsa mevcut kontrollü dummy/error sinyali korunur.

İlk sürüm için önerilen modlar:

- `linux-native`: `pygame.FULLSCREEN` başarılı.
- `linux-borderless-fallback`: native deneme hata verdi, borderless kullanıldı.
- `windowed`: fullscreen istenmedi.

### 4.4. Environment yönetimi

Linux native fullscreen çağrısından önce:

- `SDL_VIDEO_WINDOW_POS` geçici olarak kaldırılmalı,
- `SDL_VIDEO_CENTERED` geçici olarak kaldırılmalı,
- çağrı sonrası eski değerler `finally` içinde geri yüklenmelidir.

Linux native fullscreen branch’inde `SDL_VIDEO_WINDOW_POS='0,0'` kullanılmamalıdır. Windowed modun mevcut merkezleme/work-area davranışı korunmalıdır.

`SDL_VIDEODRIVER` uygulama içinde zorla `x11` veya `wayland` yapılmamalıdır. Değer loglanmalı, kullanıcı/Steam ortamı korunmalıdır.

---

## 5. Değiştirilecek yüzeyler

### 5.1. Birincil dosya: `src/platform_utils.py`

Dar kapsamlı işler:

1. `_create_linux_fullscreen_display()` benzeri test edilebilir helper eklemek.
2. `create_display()` içinde yalnızca `IS_LINUX and fullscreen` için helper çağırmak.
3. Windows/macOS branch’lerini değiştirmemek.
4. Native/fallback modunu teşhis edilebilir hale getirmek.
5. Mevcut `get_desktop_sizes()` düzeltmesini korumak.
6. `record_platform_display_telemetry()` içine Linux display alanları eklemek.

Helper mevcut `_set_mode_with_vsync()`, `_gl_diag()`, `invalidate_refresh_rate_cache()`, `_display_dummy_fallback_active` ve virtual canvas teardown sözleşmelerine uymalıdır.

### 5.2. Gerekirse `src/main.py`

Sadece şu durumlarda dokunulmalı:

- seçilen Linux display mode startup loguna aktarılacaksa,
- controlled fallback ekranı mevcut sinyalden ayrıştırılacaksa,
- startup display state’in tek noktadan kaydı gerekiyorsa.

`_resolve_startup_display()` ve `_resolve_rebuild_geometry()` gereksiz yere değiştirilmemelidir.

### 5.3. Değiştirilmemesi gereken dosyalar

- `src/sdl2_overlay.py`: Windows-only overlay yolunu Linux için genişletme.
- `src/ui_scaling.py` ve virtual canvas kodu: fullscreen sorununu UI ölçeğiyle çözmeye çalışma.
- `steamworks/steam_net_bridge/`: fullscreen ile ilgisiz native bridge değişikliklerine dokunma.
- macOS build/spec dosyaları.

### 5.4. Ayar ve lokalizasyon

İlk sürümde yeni ayar veya UI metni eklenmemelidir. `Fullscreen` mevcut ayar olarak kalır. `borderless_fullscreen` obsolete olduğundan Linux native seçiminin önüne geçirilmemelidir; Windows/macOS eski kayıt uyumluluğu korunmalıdır.

---

## 6. Önerilen algoritma

Aşağıdaki kod yalnız akış şablonudur; doğrudan kopyalanmadan mevcut `create_display()` istisna ve cache düzenine uyarlanmalıdır:

```python
def _create_linux_fullscreen_display(set_mode_with_vsync):
    native_w, native_h = get_native_resolution()
    old_centered = os.environ.pop('SDL_VIDEO_CENTERED', None)
    old_window_pos = os.environ.pop('SDL_VIDEO_WINDOW_POS', None)

    try:
        try:
            surface = set_mode_with_vsync(
                (0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF
            )
            record_linux_display_result(surface, 'linux-native')
            return surface
        except pygame.error as native_error:
            _gl_diag(f'Linux native fullscreen başarısız: {native_error}')

        surface = set_mode_with_vsync(
            (native_w, native_h), pygame.NOFRAME | pygame.DOUBLEBUF
        )
        record_linux_display_result(surface, 'linux-borderless-fallback')
        return surface
    finally:
        restore_env('SDL_VIDEO_CENTERED', old_centered)
        restore_env('SDL_VIDEO_WINDOW_POS', old_window_pos)
```

Gerçek uygulamada ayrıca şunlar korunmalıdır:

- vsync desteklenmeyen sürüm için TypeError fallback’i,
- `_teardown_virtual_canvas()` sırası,
- display cache invalidation,
- GL diagnostics,
- dummy Surface sinyali,
- mevcut exception/finally düzeni,
- overlay aktifse `set_mode` atlama sözleşmesi.

### 6.1. `borderless` parametresinin Linux yorumu

Kullanıcı arayüzünde `fullscreen=True`, paneli kapatan fullscreen anlamına gelmelidir. Bu nedenle Linux’ta `fullscreen=True` geldiğinde native fullscreen önceliği `borderless` değerinden bağımsız uygulanmalıdır. `borderless` yalnız fallback/diagnostic tercihi olarak ele alınabilir.

Ancak bunun mevcut test sözleşmesine aykırı olup olmadığı önce doğrulanmalıdır. Startup geometry testleri ile gerçek Linux `create_display()` testleri birbirine karıştırılmamalıdır.

---

## 7. Telemetri ve doğrulama

### 7.1. Log alanları

`record_platform_display_telemetry('startup')` veya ayrı display-result logu en az şunları raporlamalıdır:

```text
DISPLAY TELEMETRY [startup]
platform=Linux
session=x11|wayland|unknown
desktop=1920x1080
driver=x11|wayland|...
requested_fullscreen=1
requested_borderless=1
selected_mode=linux-native
surface=1920x1080
window=1920x1080
window_pos=0,0
surface_flags=0x...
display_is_fullscreen=1|0
```

`pygame.display.is_fullscreen()` tek başına karar mekanizması yapılmamalıdır; surface flags, window size/position ve seçilen mode ile birlikte loglanmalıdır.

### 7.2. Linux ortamı

Gerçek test sırasında şu bilgiler kaydedilmelidir:

```bash
printf 'XDG_SESSION_TYPE=%s\n' "${XDG_SESSION_TYPE:-}"
printf 'XDG_CURRENT_DESKTOP=%s\n' "${XDG_CURRENT_DESKTOP:-}"
printf 'DISPLAY=%s\n' "${DISPLAY:-}"
printf 'WAYLAND_DISPLAY=%s\n' "${WAYLAND_DISPLAY:-}"
printf 'SDL_VIDEODRIVER=%s\n' "${SDL_VIDEODRIVER:-}"
xrandr --current 2>/dev/null || true
```

Native Wayland’de `xrandr` çalışmaması beklenebilir; başarısız komut tek başına oyun hatası değildir.

### 7.3. Başarı kriteri

- Üst panel görünmez.
- Oyun masaüstünün tamamını kaplar.
- `selected_mode=linux-native` loglanır.
- Fullscreen surface/window boyutları beklenen display boyutuyla eşleşir.
- Mouse koordinatları doğru çalışır.
- Alt+Tab sonrası siyah ekran veya yanlış ölçek oluşmaz.
- Fullscreen → windowed → fullscreen geçişi çalışır.

---

## 8. Test planı

### 8.1. Yeni Linux birim testleri

Önerilen dosya: `tests/test_linux_fullscreen_display.py`

Test edilmesi gerekenler:

1. Linux fullscreen primary çağrısı `pygame.FULLSCREEN` içerir.
2. Linux primary çağrısı `pygame.NOFRAME` içermez.
3. Primary çağrı `(0, 0)` kullanır.
4. Native `pygame.error` sonrası borderless fallback çağrılır.
5. Native ve fallback birlikte başarısızsa dummy/error sinyali doğru kalır.
6. `SDL_VIDEO_WINDOW_POS` ve `SDL_VIDEO_CENTERED` çağrı sırasında temizlenip sonra restore edilir.
7. Linux windowed çağrısı mevcut `RESIZABLE`/work-area davranışını korur.
8. Windows monkeypatch’i mevcut NOFRAME davranışını korur.
9. macOS monkeypatch’i AppKit/NOFRAME davranışını korur.
10. `get_desktop_sizes()` native çözünürlük kaynağı olarak korunur.
11. Native Linux surface için `resolve_videoresize_display_params()` fullscreen sözleşmesi verir.
12. Seçilen mode, surface size ve flags birbirinden ayrı raporlanır.

Fake pygame nesneleri sabit sayı uydurmak yerine mevcut `pygame` sabitlerinden oluşturulmalıdır.

### 8.2. Mevcut regresyon testleri

Repo kökündeki runner veya Linux Python ortamında en az şu hedefler çalıştırılmalıdır:

```bash
pytest -q \
  tests/test_platform_utils_display_toggle.py \
  tests/_window_work_area_display_impl.py \
  tests/test_window_work_area_clamp.py \
  tests/test_duz004_fullscreen_startup_toggle.py \
  tests/test_display_window_transaction.py \
  tests/test_display_safe_mode.py \
  tests/test_render_geometry_contract.py
```

Dosya bulunamazsa komut sessizce atlanmamalı; repo’daki gerçek eşdeğer test dosyası bulunup rapora yazılmalıdır.

Ek kontrol:

```bash
python3 -m compileall -q src tests
./scripts/test/run_tests.sh -q
```

Tam suite zaman/ortam nedeniyle çalıştırılamazsa hangi testlerin çalışmadığı açıkça raporlanmalıdır.

### 8.3. Gerçek Linux matrisi

#### X11

- Startup fullscreen.
- Windowed → fullscreen.
- Fullscreen → windowed.
- Alt+Tab dönüşü.
- Steam üzerinden açılış.
- Steam overlay kapalı/açık.
- Tek ve çift monitör.
- Panel görünürlüğü.

#### XWayland

- SDL’nin X11 driver’ı ile aynı akış.
- Panelin kapanması.
- Focus dönüşü ve mouse koordinatları.

#### Native Wayland

- Native Wayland SDL driver.
- Fractional scaling.
- Compositor fullscreen gecikmesi.
- Alt+Tab ve suspend/resume.

#### Steam Deck/Linux handheld

- Oyun modu ve Desktop modu.
- 1280x800 benzeri ekranlar.
- Gamepad input.
- Fullscreen geçişi ve suspend/resume.

---

## 9. ELF ve Steam doğrulaması

Kaynak testleri başarılı olsa bile Steam’e yüklenen ELF ayrıca doğrulanmalıdır:

```bash
file dist/Quadrix
ldd dist/Quadrix
readelf -d dist/Quadrix | grep -E 'NEEDED|RPATH|RUNPATH'
./dist/Quadrix
```

Kontroller:

- ELF yeni Linux helper kodunu içeriyor.
- `pygame-ce` runtime sürümü kaynak ortamıyla eşleşiyor.
- `get_desktop_sizes()` değişikliği pakete gömülmüş.
- Yeni helper import edilebiliyor.
- `libsteam_api.so`/native bridge hataları fullscreen sonucu ile karıştırılmıyor.
- Yeni doğrudan sistem SDL ABI bağımlılığı yok.
- Steam’e eski ELF yüklenmiyor.

Linux build sırası:

```bash
./scripts/build/build_linux_elf.sh
file dist/Quadrix
ldd dist/Quadrix
readelf -d dist/Quadrix
```

Fullscreen için doğrudan ctypes SDL çağrıları ilk çözüm olarak eklenmemelidir. Mevcut pygame-ce içindeki SDL runtime kullanılmalıdır.

---

## 10. Geçici debug override ve rollback

Staging testlerinde yalnız Linux’a özel geçici override kullanılabilir:

```text
QUADRIX_LINUX_FULLSCREEN_MODE=auto
```

Önerilen değerler:

- `auto`: native dene, hata halinde borderless fallback.
- `native`: fallback’i kapat, native başarısızlığını görünür kıl.
- `borderless`: yalnız karşılaştırma/rollback testi.

Release varsayılanı `auto` olmalıdır. Bu değer kullanıcı ayarı olarak kalıcılaştırılmamalı ve Windows/macOS branch’lerine uygulanmamalıdır.

Mode state logu rollback kararını mümkün kılmalıdır:

- `selected_mode=linux-native` sonrası mı sorun oluştu?
- `selected_mode=linux-borderless-fallback` mı kullanıldı?

Mevcut dirty worktree değişiklikleri silinmemeli, revert edilmemeli ve `git reset --hard` kullanılmamalıdır. Özellikle `src/platform_utils.py` içindeki mevcut `get_desktop_sizes()` değişikliği korunmalıdır.

---

## 11. Uygulama fazları

### Faz 0 — Baseline

- Git diff’i ve mevcut test durumunu kaydet.
- Kaynak/ELF mevcut fullscreen logunu al.
- `XDG_SESSION_TYPE`, driver ve desktop boyutunu kaydet.
- Windows/macOS display regresyon testlerini çalıştır.

### Faz 1 — Linux helper ve telemetry

- Linux helper ekle.
- Native/fallback mode state üret.
- Pencere/surface/driver loglarını ekle.
- Settings/UI davranışını değiştirme.

### Faz 2 — `create_display()` entegrasyonu

- Yalnız `IS_LINUX and fullscreen` branch’inde helper çağır.
- Environment restore’u `finally` ile garanti et.
- Virtual canvas teardown ve cache invalidation sırasını koru.
- Overlay aktifse mevcut set_mode-atlama sözleşmesini bozma.

### Faz 3 — Testler

- Linux flags/fallback testlerini ekle.
- Windows/macOS izolasyon testlerini ekle.
- Work-area, resize, virtual canvas ve display transaction testlerini çalıştır.

### Faz 4 — Gerçek Linux doğrulaması

- X11.
- XWayland.
- Native Wayland.
- Steam build.
- Mümkünse Steam Deck.

Her koşulda screenshot + log + selected mode birlikte saklanmalıdır.

### Faz 5 — Paketleme ve staging

- Temiz Linux ELF build.
- `file`/`ldd`/`readelf` kontrolü.
- Yerel paketli çalıştırma.
- Steam staging depot.
- Steam launch testi.

---

## 12. Kabul kriterleri

### Kod

- [ ] Linux fullscreen primary path’i `pygame.FULLSCREEN` ile başlıyor.
- [ ] Linux primary path’i `NOFRAME` ile başlamıyor.
- [ ] Borderless yalnız kontrollü fallback.
- [ ] Windows borderless/Steam overlay davranışı korunuyor.
- [ ] macOS AppKit/borderless davranışı korunuyor.
- [ ] Environment değişkenleri restore ediliyor.
- [ ] Virtual canvas ve mouse normalization korunuyor.
- [ ] Linux overlay backend’i yanlışlıkla aktif olmuyor.

### Test

- [ ] Linux helper testleri geçiyor.
- [ ] Display toggle/work-area/resize testleri geçiyor.
- [ ] Windows/macOS izolasyon testleri geçiyor.
- [ ] `compileall` geçiyor.
- [ ] Kaynak Linux runtime testi geçiyor.
- [ ] Paketli ELF testi geçiyor.

### Runtime

- [ ] X11’de üst panel görünmüyor.
- [ ] XWayland’de üst panel görünmüyor.
- [ ] Native Wayland sonucu raporlanıyor.
- [ ] Fullscreen ↔ windowed geçişi çalışıyor.
- [ ] Alt+Tab sonrası siyah/yanlış ölçekli ekran yok.
- [ ] Mouse tıklamaları doğru.
- [ ] Steam üzerinden aynı davranış elde ediliyor.

### Dağıtım

- [ ] ELF yeni helper kodunu içeriyor.
- [ ] Yeni SDL ABI bağımlılığı eklenmedi.
- [ ] Steam’e doğru ve güncel ELF yüklendi.
- [ ] Build commit/timestamp ve test logları saklandı.

---

## 13. Uygulayıcı AI için kesin talimatlar

1. Önce mevcut `git diff`, `src/platform_utils.py`, `src/main.py` ve ilgili display testlerini oku.
2. Dirty worktree değişikliklerini silme veya revert etme.
3. En küçük Linux-only patch’i uygula.
4. Windows/macOS ortak branch’lerini refactor etme.
5. `surface.get_size()` değerini gerçek fullscreen kanıtı sayma.
6. pygame-ce runtime’da bulunmayan API veya SDL constant uydurma.
7. `pygame.Window`/`_sdl2.video.Window` kullanmadan önce kurulu runtime’da probe et.
8. İlk çözüm olarak ctypes SDL entegrasyonu ekleme.
9. Her display rebuild sonrası Surface/virtual canvas/event queue senkronunu doğrula.
10. Kaynak testleri geçmeden ELF build alma.
11. ELF test edilmeden Steam upload yapma.
12. Son raporda değişen dosyaları, test komutlarını, X11/Wayland sonuçlarını ve selected mode değerini yaz.

---

## 14. Sonuç

En güçlü mevcut teşhis şudur: Linux native çözünürlük ölçümü düzelmiştir; fakat fullscreen hâlâ Windows ile paylaşılan `NOFRAME + SDL_VIDEO_WINDOW_POS=0,0` yolunda oluşturulduğu için compositor oyunu gerçek fullscreen kabul etmemektedir.

Doğru çözüm, Linux’ta `pygame.FULLSCREEN` ile başlayan izole bir native fullscreen yolu kurmak, borderless’ı yalnız fallback olarak bırakmak, sonucu surface boyutundan bağımsız telemetry ile doğrulamak ve Windows/macOS altyapısını ayrı branch’lerde korumaktır.
