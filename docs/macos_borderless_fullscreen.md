# macOS'ta Çerçevesiz Tam Ekran (Borderless Fullscreen) — Pygame/SDL2

> **Tarih:** Şubat 2026  
> **Proje:** Quadrix  
> **Pygame:** 2.x (SDL2 backend)  
> **macOS:** 26.2+  
> **Python:** 3.12+

---

## Problem

macOS'ta `pygame.FULLSCREEN` flag'i SDL2'nin `Cocoa_SetWindowFullscreen` fonksiyonunu çağırır.
Bu fonksiyon, mevcut bir pencere üzerinde `[NSWindow setStyleMask:]` kullanarak pencereyi
native fullscreen moduna geçirmeye çalışır. **macOS 26+** sürümlerinde bu çağrı crash veriyor:

```
Terminating app due to uncaught exception 'NSInternalInconsistencyException'
reason: 'NSWindowStyleMaskFullScreen cannot be changed when -toggleFullScreen:
 is called or fullscreen is being entered/exited'
```

### Crash Detayları

```
Thread 0 Crashed:
  libsystem_kernel.dylib      __pthread_kill + 8
  CoreFoundation              __handleUncaughtException + 644
  libobjc.A.dylib             objc_exception_throw + 72
  AppKit                      -[NSWindow _setStyleMask:] + 120
  SDL2                        Cocoa_SetWindowFullscreen + 224
  SDL2                        SDL_SetWindowFullscreen_REAL + 152
  _pygame.cpython-312-darwin  pg_set_mode + 1592
```

### Ne Zaman Crash Olur?

| Durum | Crash? |
|-------|--------|
| İlk açılışta `set_mode(FULLSCREEN)` (henüz pencere yok) | ❌ Hayır |
| Mevcut pencere varken `set_mode(FULLSCREEN)` (F12 toggle) | ✅ **EVET** |
| `pygame.display.toggle_fullscreen()` çağrısı | ✅ **EVET** |

Crash, yalnızca **mevcut bir pencere üzerinde** fullscreen geçişi yapılmaya çalışıldığında oluşur.

---

## Denenen Yaklaşımlar

### ❌ 1. Exclusive Fullscreen (`SDL_VIDEO_MAC_FULLSCREEN_SPACES=0`)

```python
os.environ['SDL_VIDEO_MAC_FULLSCREEN_SPACES'] = '0'
pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
```

**Sonuç:** İlk açılışta çalışıyor ama F12 toggle'da crash. macOS 26+'da `setStyleMask`
exception fırlatıyor.

### ❌ 2. Spaces Fullscreen (`SDL_VIDEO_MAC_FULLSCREEN_SPACES=1`)

```python
os.environ['SDL_VIDEO_MAC_FULLSCREEN_SPACES'] = '1'
pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
```

**Sonuç:** macOS native Spaces fullscreen açılıyor. Menu bar ve title bar görünür kalıyor,
pencere ayrı bir Space'e geçiyor. "Diğer oyunlardaki gibi" hissi vermiyor.

### ✅ 3. NOFRAME Borderless Fullscreen + PyObjC (ÇÖZÜM)

```python
# FULLSCREEN flag'i KULLANILMIYOR → crash yok!
pygame.display.set_mode((native_w, native_h), pygame.NOFRAME | pygame.DOUBLEBUF)
```

**Sonuç:** Pencere çerçevesiz ve tam ekran boyutunda. Menu bar ve dock PyObjC ile gizleniyor.
Crash yok, Cmd+Tab çalışıyor.

---

## Çözüm: 3 Katmanlı Yaklaşım

### Katman 1 — `pygame.NOFRAME` + Native Çözünürlük (SDL Katmanı)

`FULLSCREEN` flag'i yerine `NOFRAME` kullanılır. Bu, SDL'nin `Cocoa_SetWindowFullscreen`
fonksiyonunu çağırmasını engeller → crash olmaz.

```python
import os
import pygame

def get_native_resolution():
    """Ekranın native çözünürlüğünü döndür."""
    info = pygame.display.Info()
    return (info.current_w, info.current_h)

# Pencereyi tam ekran boyutunda, çerçevesiz aç
native_w, native_h = get_native_resolution()
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'  # Sol üst köşeye yerleştir
flags = pygame.NOFRAME | pygame.DOUBLEBUF
surface = pygame.display.set_mode((native_w, native_h), flags)
```

**Neden çalışıyor:**
- `NOFRAME` sadece pencere çerçevesini (title bar, butonlar) kaldırır
- SDL'nin `Cocoa_SetWindowFullscreen` fonksiyonunu tetiklemez
- Pencere native çözünürlükte açılınca tüm ekranı kaplar

### Katman 2 — PyObjC ile Menu Bar + Dock Gizleme (macOS Katmanı)

Sadece `NOFRAME` kullanıldığında macOS'un menu bar'ı ve dock'u hâlâ görünür kalır.
Bunları gizlemek için macOS'un **AppKit** framework'ü kullanılır:

```python
from AppKit import NSApplication

app = NSApplication.sharedApplication()

# ── Tam ekrana geçerken ──
# NSApplicationPresentationHideMenuBar = 8
# NSApplicationPresentationHideDock     = 2
app.setPresentationOptions_(8 | 2)

# ── Pencere moduna dönerken ──
app.setPresentationOptions_(0)  # Her şey normal
```

#### Presentation Options Sabitleri

| Sabit | Değer | Bit | Açıklama |
|-------|-------|-----|----------|
| `AutoHideDock` | 1 | `1 << 0` | Dock, fare alt kenara gidince otomatik gösterilir |
| `HideDock` | 2 | `1 << 1` | Dock tamamen gizlenir |
| `AutoHideMenuBar` | 4 | `1 << 2` | Menu bar, fare üst kenara gidince otomatik gösterilir |
| `HideMenuBar` | 8 | `1 << 3` | Menu bar tamamen gizlenir |

> **⚠️ Apple Kısıtlaması:** `HideMenuBar` kullanabilmek için `HideDock` veya `AutoHideDock`
> da set edilmeli. Aynı şekilde `AutoHideMenuBar` için de dock seçeneklerinden biri gerekli.

#### Sık Kullanılan Kombinasyonlar

```python
# Tam gizle (oyun için ideal):
app.setPresentationOptions_(8 | 2)   # HideMenuBar + HideDock = 10

# Auto-hide (fare ile gösterilir):
app.setPresentationOptions_(4 | 1)   # AutoHideMenuBar + AutoHideDock = 5

# Sadece dock gizle:
app.setPresentationOptions_(2)       # HideDock = 2

# Normal moda dön:
app.setPresentationOptions_(0)       # Default = 0
```

#### PyObjC Bağımlılığı

PyObjC, macOS'ta Python ile Objective-C API'lerine erişim sağlar. Çoğu macOS sistemde
Homebrew Python veya sistem Python ile birlikte gelir. Yüklü değilse:

```bash
pip install pyobjc-framework-Cocoa
```

> **İpucu:** PyObjC yoksa `try-except` ile handle edilir. Menu bar görünür kalır ama
> oyun yine çalışır. Kritik bir bağımlılık değil, sadece görsel iyileştirme.

### Katman 3 — Restart ile Güvenli Toggle

Tam ekran ↔ pencere geçişlerinde `set_mode` çağrısı macOS'ta sorunlu olabileceğinden,
ayar kaydedilip uygulama restart edilir:

```python
import subprocess
import sys
import os

def restart_application(settings_manager):
    """Uygulamayı yeniden başlat."""
    # 1. Ayarları kaydet
    settings_manager.save_settings()
    
    # 2. Yeni process başlat
    exe = sys.executable
    if getattr(sys, 'frozen', False):  # PyInstaller
        args = [exe] + (sys.argv[1:] if len(sys.argv) > 1 else [])
    else:
        args = [exe] + sys.argv
    subprocess.Popen(args, close_fds=True)
    
    # 3. Eski process'i temiz kapat
    pygame.quit()
    os._exit(0)  # ← ÖNEMLİ!
```

#### Neden `os._exit(0)` Gerekli?

`pygame.quit()` çağrıldıktan sonra Python kodu çalışmaya devam eder. Bu durumda:

```python
# Bu satırlar pygame.quit() SONRASI çalışır!
menu.draw()  # → self.screen.get_size() çağırır
             # → pygame.error: display Surface quit  💥
```

`sys.exit(0)` kullanılabilir ama `SystemExit` exception'ı `try-except Exception` blokları
tarafından yakalanabilir. `os._exit(0)` ise process'i **anında** sonlandırır, hiçbir
exception fırlatmaz, hiçbir cleanup çalışmaz.

| Yöntem | Davranış | Risk |
|--------|----------|------|
| `return True` | Kod devam eder | `display Surface quit` hatası |
| `sys.exit(0)` | `SystemExit` fırlatır | `except Exception` yakalayabilir |
| `os._exit(0)` | Process anında biter | ✅ Güvenli, cleanup yapılmaz |

> **Not:** `pygame.quit()` zaten gerekli cleanup'ı yapıyor. `os._exit(0)` sonrası
> `atexit` handler'lar çalışmaz ama bu sorun değil çünkü ayarlar zaten kaydedildi.

---

## Tam Kullanım Şablonu

İlerideki Pygame projelerinde doğrudan kullanılabilecek tam şablon:

```python
"""
macOS Borderless Fullscreen - Pygame/SDL2
Kullanım: create_display() fonksiyonunu çağır.
"""

import os
import sys
import subprocess
import pygame

IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'


def get_native_resolution() -> tuple[int, int]:
    """Ekranın native çözünürlüğünü döndür."""
    try:
        info = pygame.display.Info()
        w, h = info.current_w, info.current_h
        if w > 0 and h > 0:
            return (w, h)
    except Exception:
        pass
    return (1920, 1080)


def _set_macos_presentation(fullscreen: bool) -> None:
    """macOS'ta menu bar ve dock'u gizle/göster."""
    try:
        from AppKit import NSApplication
        app = NSApplication.sharedApplication()
        if fullscreen:
            app.setPresentationOptions_(8 | 2)  # HideMenuBar + HideDock
        else:
            app.setPresentationOptions_(0)       # Normal
    except Exception:
        pass  # PyObjC yoksa sessizce devam et


def create_display(
    width: int,
    height: int,
    fullscreen: bool = False,
    resizable: bool = True,
) -> pygame.Surface:
    """Platform uyumlu display oluştur."""
    
    if IS_MACOS:
        if fullscreen:
            _set_macos_presentation(True)
            native_w, native_h = get_native_resolution()
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            return pygame.display.set_mode((native_w, native_h), flags)
        else:
            _set_macos_presentation(False)
            os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'
            flags = pygame.RESIZABLE if resizable else 0
            return pygame.display.set_mode((width, height), flags)
    
    # Windows/Linux
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    else:
        flags = pygame.RESIZABLE if resizable else 0
        return pygame.display.set_mode((width, height), flags | pygame.DOUBLEBUF)


def restart_application() -> None:
    """Uygulamayı yeniden başlat ve eski process'i kapat."""
    exe = sys.executable
    if getattr(sys, 'frozen', False):
        args = [exe] + (sys.argv[1:] if len(sys.argv) > 1 else [])
    else:
        args = [exe] + sys.argv
    subprocess.Popen(args, close_fds=True)
    
    try:
        pygame.quit()
    except Exception:
        pass
    os._exit(0)


def toggle_fullscreen(current_fullscreen: bool, settings_manager) -> None:
    """Tam ekran modunu toggle et."""
    new_fullscreen = not current_fullscreen
    settings_manager.set('fullscreen', new_fullscreen)
    settings_manager.save_settings()
    
    if IS_MACOS:
        # macOS: Restart ile toggle (set_mode crash'ini önler)
        restart_application()
    else:
        # Windows/Linux: Doğrudan geçiş
        if new_fullscreen:
            create_display(0, 0, fullscreen=True)
        else:
            w = settings_manager.get('window_width', 1024)
            h = settings_manager.get('window_height', 768)
            create_display(w, h, fullscreen=False)
```

---

## Akış Diyagramı

```
┌─────────────────────────────────────────────────────────┐
│                    UYGULAMA BAŞLATMA                     │
│                                                         │
│  config/runtime/settings.txt → fullscreen = 1?          │
│    ├── EVET → create_display(fullscreen=True)            │
│    │   ├── [macOS] NOFRAME + native resolution           │
│    │   │   └── PyObjC → HideMenuBar + HideDock           │
│    │   └── [Win/Linux] pygame.FULLSCREEN                 │
│    └── HAYIR → create_display(fullscreen=False)          │
│        ├── [macOS] RESIZABLE + center                    │
│        │   └── PyObjC → Normal presentation              │
│        └── [Win/Linux] pygame.RESIZABLE                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    F12 TOGGLE                            │
│                                                         │
│  [macOS]                                                │
│    1. fullscreen = !fullscreen                           │
│    2. settings_manager.save()                            │
│    3. subprocess.Popen(yeni_process)                     │
│    4. pygame.quit()                                      │
│    5. os._exit(0)  ← Eski process BURADA biter           │
│    6. Yeni process başlar → create_display()             │
│                                                         │
│  [Windows/Linux]                                        │
│    1. fullscreen = !fullscreen                           │
│    2. create_display(fullscreen=yeni_değer)              │
│    3. Devam et (restart yok)                             │
└─────────────────────────────────────────────────────────┘
```

---

## Kontrol Listesi (Yeni Projelerde)

- [ ] `SDL_VIDEO_WINDOW_POS = '0,0'` fullscreen'de, `'center'` pencere modunda
- [ ] `pygame.NOFRAME | pygame.DOUBLEBUF` flag'leri (macOS fullscreen)
- [ ] `pygame.RESIZABLE` flag'i (macOS pencere modu)
- [ ] PyObjC `setPresentationOptions_` çağrısı (`try-except` ile)
- [ ] Toggle'da `restart_application()` (macOS)
- [ ] `os._exit(0)` restart sonrası (display Surface quit önleme)
- [ ] `SDL_VIDEO_HIGHDPI_DISABLED = '1'` (Retina çözünürlük sorunlarını önler)
- [ ] `SDL_AUDIODRIVER = 'coreaudio'` (macOS ses)
- [ ] Windows/Linux koduna dokunma — orada `FULLSCREEN` sorunsuz çalışır

---

## Kaynaklar

- [SDL2 macOS Fullscreen Kaynak Kodu](https://github.com/libsdl-org/SDL/blob/main/src/video/cocoa/SDL_cocoawindow.m)
- [Apple NSApplicationPresentationOptions Docs](https://developer.apple.com/documentation/appkit/nsapplication/presentationoptions)
- [PyObjC Documentation](https://pyobjc.readthedocs.io/)
- [Pygame display.set_mode](https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode)
