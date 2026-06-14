# Plan Complete: Windows Pencere → Tam Ekran Geçiş Stabilizasyonu

Windows'ta `borderless_fullscreen=True` (varsayılan) modu kullanılırken NOFRAME penceresinin
`SDL_VIDEO_CENTERED=1` hint'i tarafından merkezlendiği için (0,0) konumuna oturmaması sorunu
çözüldü. Fiziksel çözünürlük DPI scaling'den bağımsız `ctypes.GetSystemMetrics` ile alınıyor,
boyut uyumsuzluğu tespit edilince exclusive fullscreen fallback devreye giriyor ve mod değişimi
sonrası event kuyruğu temizleniyor.

**Phases Completed:** 1 of 1 (tüm alt adımlar tek fazda uygulandı)
1. ✅ Phase 1: Windows SDL env fix + DPI-doğru çözünürlük + exclusive fallback + event temizliği

## Tüm Değiştirilen/Oluşturulan Dosyalar

- `src/platform_utils.py`
- `src/main.py`
- `test_platform_utils_display_toggle.py` (yeni)

## Fonksiyonlar / Değişiklikler

### `src/platform_utils.py`

**Yeni:** `_get_windows_physical_resolution()`
- `ctypes.windll.user32.GetSystemMetrics(0/1)` ile DPI scaling'den bağımsız fiziksel piksel çözünürlüğü döndürür.
- `ctypes` hata verirse `get_native_resolution()` fallback.

**Değişti:** `create_display()` — Windows/Linux borderless path
- **SDL_VIDEO_CENTERED geçici kaldırma:** `os.environ.pop('SDL_VIDEO_CENTERED', None)` — `set_mode()` çağrısı sırasında centered hint devre dışı; `finally` bloğunda eski değer geri yükleniyor.
- **SDL_VIDEO_WINDOW_POS='0,0':** Borderless pencerenin sol-üst köşeden başlamasını garantiler; sonra da geri yükleniyor.
- **Fiziksel çözünürlük:** Windows'ta `_get_windows_physical_resolution()` kullanılıyor (DPI scaling'li sistemlerde ~%125/%150 scale farkını elimine ediyor).
- **HWSURFACE kaldırıldı:** SDL2'de bu bayrağın etkisi yok; bazı driver kombinasyonlarında belirsiz yan etkileri var.
- **Boyut doğrulama + exclusive fallback:** `surface.get_size()` hedeften >4px sapıyorsa `pygame.FULLSCREEN | pygame.DOUBLEBUF` ile ikinci `set_mode()` denemesi.

**Değişti:** `create_display()` — Windows/Linux exclusive fullscreen path
- `set_mode((0, 0), FULLSCREEN)` çağrısı etrafında da `SDL_VIDEO_CENTERED` geçici kaldırma + geri yükleme eklendi.

### `src/main.py`

**Değişti:** `_rebuild_display()` — `_apply_screen()` çağrısı sonrasına eklendi:
```python
pygame.event.pump()
pygame.event.clear([pygame.VIDEORESIZE])
```
Mod değişimi sonrası biriken resize/video event'lerinin sonraki frame'de ikinci bir geçiş tetiklemesi önlendi.

## Testler

**Dosya:** `test_platform_utils_display_toggle.py` (11 test, tümü geçti)

| Test Sınıfı | Test | Açıklama |
|---|---|---|
| `TestGetWindowsPhysicalResolution` | `test_returns_ctypes_values_when_available` | ctypes başarılıysa fiziksel çözünürlük döner |
| | `test_falls_back_to_display_info_on_ctypes_error` | ctypes hata → pygame.Info fallback |
| | `test_falls_back_when_ctypes_returns_zero` | GetSystemMetrics=0 → pygame.Info fallback |
| `TestCreateDisplayWindowsBorderlessCenteredEnv` | `test_centered_absent_during_set_mode` | set_mode sırasında SDL_VIDEO_CENTERED yok |
| | `test_window_pos_is_zero_during_set_mode` | set_mode sırasında SDL_VIDEO_WINDOW_POS='0,0' |
| `TestCreateDisplayWindowsBorderlessEnvRestore` | `test_centered_restored_after_call` | Çağrı sonrası centered eski değere (1) döner |
| | `test_centered_not_added_if_was_absent` | Önceden yoktu, sonradan eklenmez |
| | `test_window_pos_restored_after_call` | window_pos 'center'e döner |
| | `test_window_pos_removed_if_was_absent` | Önceden yoktu, sonradan temizlenir |
| `TestCreateDisplayWindowsBorderlessFallback` | `test_exclusive_fallback_triggered_on_size_mismatch` | Boyut sapınca 2. deneme FULLSCREEN ile |
| | `test_no_fallback_when_size_matches` | Normal durumda tek set_mode çağrısı |

**Mevcut testler:** 91 passed, 1 skipped — sıfır regresyon.

## Review Status

APPROVED — Tüm testler yeşil, env restore `try/finally` ile güvence altında, macOS kodu dokunulmadı.

## Git Commit Message

```
fix: stabilize Windows windowed→fullscreen toggle via SDL env fix

- Temporarily remove SDL_VIDEO_CENTERED during borderless set_mode
  so NOFRAME window is placed at (0,0) instead of being centered
- Set SDL_VIDEO_WINDOW_POS='0,0' during fullscreen set_mode and
  restore original value in finally block
- Use ctypes GetSystemMetrics for DPI-independent physical resolution
  on Windows (fixes partial coverage on 125%/150% DPI systems)
- Remove legacy HWSURFACE from borderless path (SDL2 ignores it)
- Add exclusive fullscreen fallback when borderless surface size
  mismatches expected native resolution
- Clear VIDEORESIZE event queue in _rebuild_display to prevent a
  second unintended toggle on the next frame
```
