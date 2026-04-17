# Pygame-CE Geçiş Araştırma Raporu

**Tarih:** 2025-07  
**Proje:** Quadrix (Pygame Tabanlı Tetris)  
**Mevcut:** pygame 2.6.1, SDL 2.28.4, Python 3.12  
**Hedef:** pygame-ce 2.5.7, SDL 2.32.10

---

## İçindekiler

1. [HiDPI / Retina Desteği](#1-hidpi--retina-desteği)
2. [API Uyumluluğu ve Farklar](#2-api-uyumluluğu-ve-farklar)
3. [PyInstaller Uyumluluğu](#3-pyinstaller-uyumluluğu)
4. [Steam Entegrasyonu Uyumluluğu](#4-steam-entegrasyonu-uyumluluğu)
5. [Performans Karşılaştırması](#5-performans-karşılaştırması)
6. [Topluluk Deneyimleri ve Riskler](#6-topluluk-deneyimleri-ve-riskler)
7. [Olası Geçiş Stratejileri](#7-olası-geçiş-stratejileri)
8. [Sonuç ve Öneriler](#8-sonuç-ve-öneriler)

---

## 1. HiDPI / Retina Desteği

### Mevcut Sorun

pygame 2.6.1'in **software renderer**'ı macOS Retina ekranlarda HiDPI desteklemiyor. `SDL_WINDOW_ALLOW_HIGHDPI` bayrağı sadece OpenGL/Metal renderer bağlamlarında çalışıyor. Software renderer'da `display.set_mode()` ile oluşturulan Surface her zaman pencere boyutuna eşit — yani 1.0x scale factor döndürüyor.

**Test sonuçları** (`_test_hidpi.py` ile doğrulandı):
- `SCALED | RESIZABLE` → scale = 1.0
- `RESIZABLE` → scale = 1.0
- `NOFRAME` → scale = 1.0
- `NOFRAME | DOUBLEBUF` → scale = 1.0

### pygame-ce'de Durum

pygame-ce de **aynı temel soruna** sahip. İşte kaynaklar:

- **GitHub #1456** (pygame-ce): "Enable High DPI rendering on macOS (rendering is blurry)" — Hâlâ **AÇIK**, çözülmemiş.
- **GitHub #2853** (pygame orijinal): Detaylı araştırma (williamhCode, Mayıs 2022):
  - Software renderer'da macOS HiDPI rendering zaten gerçekleşiyor (SDL seviyesinde) ama pygame Surface boyutu buna uymuyor.
  - `SDL_WINDOW_ALLOW_HIGHDPI` bayrağı software pencereler için hiçbir fark yaratmıyor.
  - OpenGL pencerelerde de SDL2 ile HiDPI işlevi doğru çalışmıyor (SDL2 sınırlaması).
- **GitHub #1059** (pygame-ce): Windows'ta scaled desktop ile `display.Info()` yanlış çözünürlük raporluyor — **AÇIK**.
- **GitHub #931** (pygame-ce): Windows high DPI fullscreen sorunu — **AÇIK**.

### pygame-ce'nin Sunduğu Yeni Yaklaşımlar

1. **`Window(allow_high_dpi=True)`**: pygame-ce 2.4.0+ ile `pygame.Window` sınıfı `allow_high_dpi` parametresi sunuyor. SDL2'nin `SDL_WINDOW_ALLOW_HIGHDPI` bayrağını geçiriyor. Ancak bu **sadece OpenGL renderer** ile anlamlı (software çizimde etkisiz).

2. **Renderer + logical_size**: pygame-ce'nin `Renderer` sınıfı `logical_size` özelliği ile cihazdan bağımsız çözünürlük ayarlayabilir. Bu, GPU hızlandırmalı render kullanarak Retina çözünürlükte çizim yapabilir. Ama bu, **tüm çizim mantığının yeniden yazılmasını** gerektirir (Surface → Texture geçişi).

3. **SDL3 portu (devam ediyor)**: pygame-ce ekibi aktif olarak SDL3'e port çalışması yapıyor (2.5.3-2.5.7 release notlarında büyük porting çalışmaları:  display.c, surface.c, font, joystick, transform, draw, mask vb.). SDL3, HiDPI'yı daha iyi ele alıyor ama bu port henüz tamamlanmadı ve bir `pygame-ce 3.0` sürümü olarak planlanıyor.

4. **Metal overlay çözümü** (taiyo66666-hash, Aralık 2025): Pygame penceresinin üzerine Metal view yerleştirip 1:1 pixel rendering yapan bir 3. parti çözüm var. Ama bu maintstream değil, sürdürülebilirliği tartışmalı.

### HiDPI Sonuç

| Özellik | pygame 2.6.1 | pygame-ce 2.5.7 | pygame-ce 3.0 (gelecek) |
|---------|-------------|-----------------|------------------------|
| Software renderer HiDPI | ❌ | ❌ | SDL3 ile ❓ muhtemelen |
| OpenGL HiDPI (ALLOW_HIGHDPI) | ❌ (SDL2 sorunu) | ❌ (aynı SDL2 sorunu) | SDL3 ile ✅ muhtemelen |
| Window(allow_high_dpi) | ❌ yok | ✅ parametre var | ✅ |
| Renderer + logical_size | ❌ yok | ✅ var (GPU render) | ✅ |
| Koordinat dönüşümü | ❌ yok | ✅ coordinates_to/from_window | ✅ |

**Önemli:** pygame-ce'ye geçiş **otomatik olarak HiDPI çözmez**. Software renderer ile yapılan Surface-tabanlı render'da pygame-ce da aynı sınırlamaya sahip. Gerçek HiDPI için ya:
- Tüm rendering'i Renderer/Texture API'ya taşımak gerekir (büyük refactor)
- Ya da SDL3 portunun tamamlanmasını beklemek gerekir

---

## 2. API Uyumluluğu ve Farklar

### Drop-in Uyumluluk

pygame-ce, pygame'in **fork**'udur ve aynı `import pygame` namespace'ini kullanır. Kurulum:

```bash
pip uninstall pygame
pip install pygame-ce
```

Kod tarafında **hiçbir import değişikliğine gerek yok**. pygame-ce, pygame'in tüm mevcut API'sını korur.

### pygame-ce'de Eklenen Yeni API'ler (Quadrix'i etkileyebilecek)

| API | Versiyon | Açıklama | Quadrix Etkisi |
|-----|----------|----------|----------------|
| `pygame.Window` (public) | 2.5.2 | Çoklu pencere, HiDPI parametreli | Gelecekte kullanılabilir |
| `pygame.typing` modülü | 2.5.2 | Type hint'ler | İsteğe bağlı |
| `Renderer.logical_size` | mevcut | GPU render device-independent resolution | HiDPI için potansiyel |
| `Renderer.coordinates_to/from_window` | 2.5.6 | Koordinat dönüşümü | HiDPI mouse için |
| `Color.from_hex()` / `Color.hex` | 2.5.4-2.5.6 | Renk yardımcıları | Kolaylık |
| `image.load_animation` | 2.5.4 | GIF/WEBP animasyon | İsteğe bağlı |
| `transform.pixelate` | 2.5.6 | Pikselleştirme efekti | Görsel efekt |
| `draw.flood_fill` | 2.5.6 | Paint bucket | Yok |
| `draw.aaline` width parametresi | 2.5.6 | Kalın anti-aliased çizgi | Görsel iyileştirme |
| `Font.set_linesize()` | 2.5.4 | Satır aralığı kontrolü | Menu metinleri |
| `display.message_box()` | 2.4.0 | Native dialog | Hata gösterimi |

### Kaldırılan / Değişen API'ler

- `set_gamma` / `set_gamma_ramp` → **Deprecated** (SDL3'te kalkacak), Quadrix kullanmıyor ✅
- `SurfaceType` / `RectType` → **Deprecated**, kullanılmamalı (sadece `Surface`, `Rect` kullanın)
- `Window.from_display_module()` → **Deprecated** (2.4.0+)
- `freetype.was_init`, `scrap.lost` → **Deprecated**

### Uyumsuzluk Riski: DÜŞÜK

Quadrix'in kullandığı tüm API'ler (`display.set_mode`, `Surface.blit`, `draw.*`, `font.Font`, `mixer.*`, `event.*`, `mouse.*`, `key.*`, `transform.*`, `image.*`) pygame-ce'de **tam uyumlu**. pygame-ce sadece ekleme yapar, mevcut API'leri bozmaz.

**Potansiyel dikkat noktaları:**
- `display.set_mode` depth argümanı 2.4.0'dan beri deprecated uyarı veriyor (0 ou otomatik seçim önerilir) — Quadrix bunu geçiriyorsa kontrol et
- `vsync=1` davranışı biraz farklı olabilir (2.2.0 değişiklikleri)
- `event.peek` davranışı 2.5.3'te düzeltildi (bool dönüş)

---

## 3. PyInstaller Uyumluluğu

### Mevcut Durum

Quadrix, PyInstaller ile macOS .app olarak paketleniyor (`tetris_macos.spec`). Spesifikasyonda:
- `pygame` modülleri hidden import olarak ekleniyor
- `freesansbold.ttf` font dosyası kopyalanıyor
- `src/` altındaki tüm modüller taranıyor

### pygame-ce + PyInstaller

**İyi haber:** pygame-ce, PyInstaller ile çalışacak şekilde aktif olarak bakılıyor:

1. **Hidden import düzeltmesi**: PR #2287 ile `_sdl2.video` (Window) için hidden import eklendi.
2. **pkgdata rework**: `importlib` kullanımına geçildi (pygame-ce #3061), `pkg_resources` deprecation uyarısı düzeltildi.
3. **Briefcase template**: PR #2862 ile Briefcase (bir diğer paketleme aracı) desteği eklendi.
4. **macOS Notarization**: 2.5.5'te macOS code notarization sorunu düzeltildi (#3478).
5. **Universal2 wheels**: PR #3625 (2.5.7) ile macOS arm64+x86_64 universal wheel'ler oluşturuldu.

### Geçiş İçin Gerekli Değişiklikler

`tetris_macos.spec` dosyasında:
1. `pip install pygame-ce` ile paket değiştirilmeli
2. `freesansbold.ttf` yolu: pygame-ce de aynı konumda tutuyor (uyumlu)
3. Hidden imports: `pygame._sdl2.video` eklenebilir (gerekirse)
4. SDL kütüphane dosyaları: pygame-ce kendi SDL2 bundle'ını içeriyor, ek işlem gerektirmez
5. `requirements-macos.txt` ve `requirements.txt` güncellenmeli: `pygame==2.6.1` → `pygame-ce>=2.5.7`

### PyInstaller Risk: DÜŞÜK

pygame-ce, `pygame` ile aynı paket adını kullanıyor (sadece pip adı `pygame-ce`). PyInstaller açısından `import pygame` aynı şekilde çalışır. Bilinen büyük sorun yok.

---

## 4. Steam Entegrasyonu Uyumluluğu

### Quadrix'in Steam Entegrasyonu

Quadrix, Steam SDK'yı **ctypes** ile yükleyen özel bir `steam_integration.py` modülü kullanıyor. Bu modül doğrudan `libsteam_api.dylib` (macOS) veya `steam_api64.dll` (Windows) ile konuşuyor.

### pygame-ce Etkisi: YOK

Steam entegrasyonu pygame'den **tamamen bağımsız**. `steam_integration.py` ctypes ile native SDK'yı çağırıyor, pygame'in hangi sürümü olduğu farketmez.

**Detaylar:**
- Steam Overlay: SDL penceresi üzerinde çalışır. pygame → pygame-ce geçişi SDL pencere yapısını değiştirmez (aynı SDL2 pencere).
- Steam Input/Controller: `gamepad_manager.py` → `pygame.joystick` kullanıyor. pygame-ce'de joystick API uyumlu (sadece SDL3'te port edildi ama SDL2'de aynı).
- Leaderboards: HTTP/ctypes tabanlı, pygame'le ilgisiz.

### Steam Risk: ÇOK DÜŞÜK

Hiçbir değişiklik gerekmez. ctypes wrapper'lar pygame sürümünden bağımsız çalışır.

---

## 5. Performans Karşılaştırması

### pygame-ce Optimizasyonları

pygame-ce, pygame fork'undan beri sürekli performans iyileştirmeleri yapıyor:

| Optimizasyon | Versiyon | İyileştirme |
|-------------|----------|-------------|
| `Rect` accessor'lar | 2.5.2 | FASTCALL ile %15-22 hızlanma |
| `Rect.collidepoint`, `Rect.move_ip` | 2.5.3 | %17-19 hızlanma |
| `Rect.clipline()` | 2.5.2 | %50'ye kadar hızlanma |
| `Rect.inflate(_ip)` | 2.5.6 | FASTCALL ile %25-30 hızlanma |
| `Surface.fblits` | 2.5.1 | Regresyon düzeltmesi + iyileştirme |
| `draw.aacircle` | 2.5.1 | %5-6 hızlanma |
| 24-bit surface line drawing | 2.5.1 | %20 hızlanma |
| `mask.from_surface` | 2.5.1 | Optimizasyon |
| `transform.scale2x` | 2.5.1 | Optimizasyon |
| Color parsing (name/hex) | 2.5.3 | 2x+ hızlanma |
| Vector optimizasyonları | 2.5.6 | RealNumber_Check eliminasyonu |
| `PixelArray.make_surface` | 2.5.1 | Optimizasyon |
| Sprite collision fonksiyonları | 2.5.6 | C'ye yeniden yazıldı |

### Quadrix İçin Anlamlı Olanlar

Quadrix bir Tetris oyunu olduğundan, en çok etkilenecek alanlar:
- **Rect işlemleri** (collision, position): Tetris bloklarının çarpışma kontrolünde yoğun kullanım → **anlamlı iyileşme**
- **Surface.blit / fblits**: Her frame'de tüm blokları çizmek → **iyileşme**
- **Color parsing**: Theme sistemi renk isimleri kullanıyorsa → **iyileşme**
- **draw.* fonksiyonları**: Grid çizimi → **küçük iyileşme**

### SDL Sürüm Farkı

| | pygame 2.6.1 | pygame-ce 2.5.7 |
|---|---|---|
| SDL | 2.28.4 | 2.32.10 |
| SDL_image | ? | 2.8.8 |
| SDL_mixer | ? | 2.8.1 |
| SDL_ttf | ? | 2.24.0 |

Daha yeni SDL sürümleri: daha az bug, daha iyi platform desteği, güvenlik düzeltmeleri.

### Performans Risk: ÇOK DÜŞÜK (sadece olumlu etki beklenir)

---

## 6. Topluluk Deneyimleri ve Riskler

### pygame-ce Profilil

- **GitHub stars:** ~1,000+ (hızla büyüyor)
- **Son release:** 2.5.7 (Mart 2026)
- **Active maintainers:** @Starbuck5, @ankith26, @oddbookworm, @damusss, @Matiiss, @aatle, @zoldalma999, @bilhox, @MightyJosip
- **Release sıklığı:** ~2-3 ayda bir major release
- **Python desteği:** 3.10-3.14, PyPy 3.11
- **Platform desteği:** Windows, macOS (x86_64 + ARM64), Linux (x86_64 + ARM64), WASM (pyscript/pyodide)

### pygame (orijinal) Durumu

pygame orijinal proje **fiilen bakımsızdır**:
- Son release: 2.6.1 (Kasım 2024)
- Aktif contributor sayısı çok düşük
- 600+ açık issue
- SDL2 sürümü eski (2.28.x)
- Python 3.13/3.14 desteği belirsiz

### Geçiş Riskleri

| Risk | Seviye | Açıklama | Mitigasyon |
|------|--------|----------|-----------|
| API kırılması | DÜŞÜK | pygame-ce geriye dönük uyumlu | Test suite'i çalıştır |
| PyInstaller sorunu | DÜŞÜK | Aktif olarak destekleniyor | Test build yap |
| Performans regresyonu | ÇOK DÜŞÜK | Sadece iyileştirmeler var | Benchmark |
| Steam overlay bozulması | ÇOK DÜŞÜK | SDL pencere yapısı aynı | Aynı SDL2 backend |
| HiDPI beklenti boşluğu | YÜKSEK | Software renderer'da HiDPI yine çalışmaz | Beklentiyi ayarla |
| Gelecekteki SDL3 kırılmaları | ORTA | pygame-ce 3.0'da API değişiklikleri olabilir | 2.x serisinde kal |
| İki paket çakışması | DÜŞÜK | pip install sırası önemli | uninstall pygame önce |

### Topluluk Görüşleri

- pygame-ce, pygame'in "ruhani halefi" olarak görülüyor
- pygame Discord'unda pygame-ce aktif olarak öneriliyor
- Birçok oyun ve kütüphane pygame-ce'ye geçiyor
- pygame orijinalinin geleceği belirsiz, bakımı neredeyse durmuş

---

## 7. Olası Geçiş Stratejileri

### Strateji A: Basit Drop-in Geçiş (ÖNERİLEN)

**Ne:** Sadece `pygame==2.6.1` → `pygame-ce>=2.5.7` değiştir.  
**Etki:** Performans iyileştirmeleri + daha yeni SDL + aktif bakım.  
**HiDPI etkisi:** YOK (software renderer aynı).  
**Çaba:** Minimal (requirements + test).  
**Risk:** ÇOK DÜŞÜK.

```
1. pip uninstall pygame && pip install pygame-ce
2. requirements.txt güncelle
3. Test suite çalıştır
4. macOS .app build test et
5. Windows build test et
```

### Strateji B: pygame-ce + Window API ile HiDPI (BÜYÜK REFACTOR)

**Ne:** `display.set_mode()` → `pygame.Window(allow_high_dpi=True)` + `Renderer` + `Texture` geçişi.  
**Etki:** GPU hızlandırmalı render, Retina desteği potansiyeli.  
**HiDPI etkisi:** MUHTEMELEN (Renderer.logical_size ile).  
**Çaba:** ÇOK BÜYÜK — tüm render pipeline'ını yeniden yazmak gerekir.  
**Risk:** YÜKSEK.

Bu strateji Quadrix için **önerilmez** çünkü:
- Tüm `Surface.blit()` çağrıları → `Texture.draw()` olmalı
- `pygame.draw.*` → `Renderer.draw_*` / `Renderer.fill_*` olmalı
- `pygame.font` render → Texture'a dönüştürülmeli
- Mouse koordinat dönüşümü → `coordinates_from_window()` kullanılmalı
- Yüzlerce kaynak dosya değişikliği gerekir

### Strateji C: SDL3 Portunu Bekle

**Ne:** pygame-ce 3.0 (SDL3 tabanlı) çıkana kadar bekle.  
**Etki:** Potansiyel olarak tam HiDPI desteği.  
**HiDPI etkisi:** MUHTEMELEN EVET.  
**Çaba:** Bekleme + gelecekte geçiş.  
**Risk:** Belirsiz timeline (2026?), API kırılmaları olabilir.

### Strateji D: Drop-in Geçiş + Yüksek Çözünürlük Asset'ler

**Ne:** pygame-ce'ye geç + daha büyük pencere boyutu + 2x asset'ler.  
**Etki:** Software renderer'da bile daha keskin görüntü.  
**HiDPI etkisi:** KISMEN (doğal piksel artışı).  
**Çaba:** ORTA (asset'ler + boyutlandırma kodu).  
**Risk:** DÜŞÜK, performans etkisi test edilmeli.

---

## 8. Sonuç ve Öneriler

### Kesin Bulgular

1. **pygame-ce, HiDPI sorununu otomatik olarak ÇÖZMEZ.** Software renderer ile yapılan Surface tabanlı render'da SDL2 sınırlaması hem pygame hem pygame-ce için aynıdır.

2. **pygame-ce'ye geçiş güvenlidir.** API tam uyumlu, PyInstaller çalışıyor, Steam entegrasyonu etkilenmiyor. Drop-in replacement olarak çalışır.

3. **pygame-ce performans ve bakım açısından kesinlikle üstündür.** Rect'te %15-50, color parsing'te 2x+, daha yeni SDL (2.32.10 vs 2.28.4), aktif geliştirme.

4. **Gerçek HiDPI için alternatifler:**
   - Renderer/Texture API'ya geçiş (büyük refactor)
   - SDL3 portu çıkana kadar bekleme
   - Yüksek çözünürlük pencere + 2x asset'ler (kısmi çözüm)

5. **pygame orijinal projesi fiilen ölüdür.** pygame-ce'ye geçiş uzun vadeli sürdürülebilirlik için anlamlıdır.

### Önerilen Aksiyon Planı

```
Aşama 1 (Hemen):  Drop-in geçiş (Strateji A)
                   - pygame → pygame-ce değiştir
                   - Test suite çalıştır
                   - Build test et (macOS + Windows)

Aşama 2 (Kısa):   Mevcut HiDPI değişikliklerini koru
                   - get_mouse_pos(), normalize_mouse_pos() vb. fonksiyonlar
                   - Scale factor 1.0 döndüğünde zararsız ama gelecek için hazır

Aşama 3 (Orta):   Yüksek çözünürlük asset'ler + pencere boyutu optimizasyonu
                   - Retina ekranlarda daha büyük pencere (native çözünürlüğe yakın)
                   - 2x çözünürlüklü sprite/font asset'ler

Aşama 4 (Uzun):   pygame-ce 3.0 (SDL3) çıktığında HiDPI'yı tam aktifleştir
                   - Window(allow_high_dpi=True) + doğal HiDPI desteği
                   - Mevcut get_display_scale_factor() altyapısı hazır
```

### Karar Matrisi

| Kriter | Strateji A (Drop-in) | Strateji B (Renderer) | Strateji C (Bekle) | Strateji D (Drop-in+2x) |
|--------|---------------------|----------------------|--------------------|-----------------------|
| HiDPI çözümü | ❌ | ✅ (muhtemelen) | ✅ (gelecekte) | 🟡 kısmen |
| Çaba | Minimal | Çok büyük | Sıfır | Orta |
| Risk | Çok düşük | Yüksek | Yok | Düşük |
| Performans | ✅ iyileşme | ✅ GPU hızlandırma | - | ✅ iyileşme |
| Bakım | ✅ aktif | ✅ aktif | ❌ pygame ölü | ✅ aktif |
| Timeline | Hemen | Aylar | Belirsiz | 1-2 hafta |

**Sonuç:** **Strateji A, şimdi yapılacak en mantıklı adımdır.** Risk çok düşük, fayda kesin. HiDPI çözümü SDL3 portuna bırakılmalı.

---

## Referanslar

- [pygame-ce GitHub](https://github.com/pygame-community/pygame-ce)
- [pygame-ce releases](https://github.com/pygame-community/pygame-ce/releases)
- [pygame-ce docs](https://pyga.me/docs/)
- [HiDPI issue #2853 (pygame)](https://github.com/pygame/pygame/issues/2853)
- [HiDPI issue #1456 (pygame-ce)](https://github.com/pygame-community/pygame-ce/issues/1456)
- [Windows DPI #1059 (pygame-ce)](https://github.com/pygame-community/pygame-ce/issues/1059)
- [Window API docs](https://pyga.me/docs/ref/window.html)
- [Renderer API docs](https://pyga.me/docs/ref/sdl2_video.html)
- [PyInstaller hidden import fix #2287](https://github.com/pygame-community/pygame-ce/pull/2287)
- [macOS notarization fix #3478](https://github.com/pygame-community/pygame-ce/pull/3478)
- [Metal overlay workaround](https://github.com/taiyo66666-hash/MetalPygameDistribution)
