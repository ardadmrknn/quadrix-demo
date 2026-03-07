# Plan: Steam Overlay Sonrası Windows PrintScreen / Alt+Tab Stabilite Düzeltmesi

**Created:** 2026-03-07  
**Status:** Ready for Atlas Execution

## Summary

Steam overlay görünürlüğü için eklenen OpenGL uyumluluk katmanı (`gl_compat.py`) sonrasında Windows'ta iki belirti raporlanıyor:

1. **PrintScreen / ekran alıntısı paneli yanlış frame gösteriyor**
   - Ana menüde PrintScreen basıldığında bazen mevcut panel yerine bir önceki panel görünüyor.
   - İkinci PrintScreen'de düzeliyor.
2. **Alt+Tab geçişi pürüzsüz değil**
   - Özellikle Steam üzerinden açılmış EXE'de oyuna geri dönerken 1-2 saniyelik siyah ekran görülebiliyor.

Kod analizi, iki sorunun da büyük olasılıkla aynı aileden geldiğini gösteriyor:
- `src/main.py` içindeki Windows display recovery mantığı (`_maybe_recover_windows_display`)
- `src/gl_compat.py` içindeki OpenGL present/reapply zinciri
- focus / PrintScreen sonrası `set_mode` ve front-buffer/present sıralaması

Bu plan, hangi çözümlerin uygulanması gerektiğini ve hangilerinden kaçınılması gerektiğini netleştirir.

## Root Cause Snapshot

**İlgili dosyalar:**
- `src/main.py`
- `src/gl_compat.py`
- `src/platform_utils.py`

**Ana teknik gözlemler:**
- Oyun hâlâ `pygame.Surface` + `blit` tabanlı çiziyor; native renderer-first mimari yok.
- Steam overlay için sonradan OpenGL pencere/context oluşturuluyor.
- `gl_compat` mevcut Surface'i her frame texture olarak GL'e upload edip swap ediyor.
- Windows recovery mantığı PrintScreen/focus-loss sonrası display'i toparlamak için `create_display()` / `request_window_focus()` zincirine girebiliyor.
- GL aktifken display rebuild/reapply, PrintScreen ve Alt+Tab semptomlarını büyütebiliyor.

## Decision Matrix

### Plan A: Windows recovery mantığını daralt ve GL varken agresif toparlamayı kapat

**Ne yapılır:**
- `src/main.py::_maybe_recover_windows_display()` içinde PrintScreen ve focus-loss recovery koşulları daha konservatif yapılır.
- GL aktifken focus kaynaklı recovery tamamen kapatılır.
- GL aktifken PrintScreen kaynaklı recovery de varsayılan olarak kapatılır veya sadece gerçekten display bozulması kanıtlanırsa çalışır.
- Recovery sonunda `request_window_focus()` her durumda çağrılmaz; yalnızca gerçekten yeni pencere oluşturulduysa çağrılır.

**Beklenen etki:**
- Alt+Tab siyah ekran süresi azalır.
- PrintScreen sırasında yanlış panel/frame yakalanma ihtimali düşer.
- Kod değişikliği sınırlıdır.

**Risk:** Düşük-Orta  
**Maliyet:** Düşük  
**Öneri:** **YAPILMALI**

### Plan B: `gl_compat` katmanını focus / PrintScreen açısından deterministik hale getir

**Ne yapılır:**
- `src/gl_compat.py` içinde focus geri gelince otomatik `set_mode` / `_reapply_gl()` zinciri kısıtlanır.
- `create_display` monkey-patch kapsamı daraltılır; her display değişiminde zorunlu reapply yapılmaz.
- `gl_overlay_resize()` path'i gerçek resize için kullanılır; focus-loss için kullanılmaz.
- Gerekirse “front buffer stale frame” riskini azaltmak için GL tarafında explicit clear/present sırası sıkılaştırılır.

**Beklenen etki:**
- PrintScreen'in bir önceki paneli göstermesi azalır.
- Alt+Tab dönüşü daha stabil olur.
- Steam overlay korunur.

**Risk:** Orta  
**Maliyet:** Orta  
**Öneri:** **YAPILMALI**, ancak Plan A'dan sonra.

### Plan C: Steam overlay GL katmanını aç/kapa yapılabilir hale getir

**Ne yapılır:**
- Ayar veya env üzerinden `gl_compat` devre dışı bırakılabilir.
- Sorun yaşayan Windows makinelerinde overlay uyumluluğu ile sistem stabilitesi arasında seçim yapılabilir.
- Destek / QA için hızlı A/B testi mümkün olur.

**Beklenen etki:**
- Sorunun gerçekten GL uyumluluk katmanından kaynaklandığı saha ortamında hızla doğrulanır.
- Kullanıcıya fallback sağlanır.

**Risk:** Düşük  
**Maliyet:** Düşük-Orta  
**Öneri:** **YAPILMALI**, ama ana düzeltme olarak değil; güvenlik valfi olarak.

### Plan D: Windows build'de Steam overlay için mevcut GL yaklaşımını tamamen kaldır

**Ne yapılır:**
- `gl_compat` tamamen devre dışı bırakılır.
- Oyun tekrar klasik software-surface sunum yoluna döner.

**Beklenen etki:**
- PrintScreen / Alt+Tab sorunlarının büyük kısmı muhtemelen kaybolur.
- Ancak Steam overlay görünürlüğü veya overlay içi bazı fonksiyonlar tekrar bozulabilir.

**Risk:** Orta-Yüksek  
**Maliyet:** Düşük  
**Öneri:** **YAPILMAMALI** (yalnızca acil fallback veya geçici hotfix olarak düşünülmeli).

### Plan E: Uzun vadede renderer mimarisini renderer-first backend'e taşı

**Ne yapılır:**
- Surface-first çizim mimarisi bırakılır.
- Daha doğal GPU backend (ör. pygame-ce renderer / SDL renderer tabanlı yaklaşım) prototiplenir.
- Steam overlay desteği GL monkey-patch yerine daha doğal bir render yoluna alınır.

**Beklenen etki:**
- Uzun vadede Windows render zinciri sadeleşebilir.
- Steam overlay tarafında hack yerine daha temiz mimari oluşabilir.

**Risk:** Çok Yüksek  
**Maliyet:** Çok Yüksek  
**Öneri:** **ŞİMDİ YAPILMAMALI**. Ayrı prototip dalında araştırma işi olarak ele alınmalı.

## Recommended Execution Order

### Phase 1: Recovery davranışını güvenli minimuma çek

**Objective:** Windows PrintScreen / focus-loss sonrası gereksiz display churn'i azalt.

**Files to Modify:**
- `src/main.py`

**Steps:**
1. `_maybe_recover_windows_display()` içinde PrintScreen recovery'yi yalnızca gerçek bozulma kanıtına bağla.
2. GL aktifken focus recovery'yi kapat.
3. GL aktifken PrintScreen recovery'yi de varsayılan olarak kapat veya ek guard ekle.
4. `request_window_focus()` çağrısını her recovery'de değil, sadece yeni pencere gerçekten kurulduysa kullan.
5. Recovery'nin gerçekten devreye girip girmediğini debug log ile ayırt edilebilir yap.

**Acceptance Criteria:**
- [ ] PrintScreen sonrası ekran alıntısı panelinde eski frame görünme sıklığı düşer.
- [ ] Alt+Tab dönüşünde siyah ekran süresi azalır.
- [ ] Normal kullanıcı akışlarında yeni odak/focus regresyonu oluşmaz.

### Phase 2: `gl_compat` reapply zincirini sadeleştir

**Objective:** GL wrapper'ın focus ve display rebuild ile gereksiz etkileşimini azalt.

**Files to Modify:**
- `src/gl_compat.py`
- `src/main.py`

**Steps:**
1. `_patch_create_display()` kapsamını gözden geçir; otomatik reapply her path için zorunlu olmasın.
2. `_reapply_gl()` sadece gerçek fullscreen/resolution rebuild sonrası çağrılsın.
3. Focus-loss / PrintScreen sonrası `_reapply_gl()` çağrı zincirini kes.
4. GL flip/present akışında stale frame ihtimalini azaltacak açık clear/draw sırasını doğrula.

**Acceptance Criteria:**
- [ ] PrintScreen paneli önceki paneli göstermiyor veya belirti dramatik azalıyor.
- [ ] Alt+Tab geri dönüşünde ikinci `set_mode` zinciri kayboluyor.

### Phase 3: Runtime güvenlik valfi ekle

**Objective:** Sorun yaşayan makinelerde overlay uyumluluğunu gerektiğinde kapatabilmek.

**Files to Modify:**
- `src/main.py`
- `src/settings_manager.py` veya env-temelli config noktası
- Gerekirse ilgili UI ayar ekranı

**Steps:**
1. `steam_overlay_render_mode = auto|gl|off` benzeri bir config ekle.
2. `auto` varsayılanı kısa vadede mevcut güvenli davranış olsun.
3. `off` modunda `gl_compat` hiç devreye girmesin.
4. Gerekirse yalnızca debug/advanced ayarlar altında göster.

**Acceptance Criteria:**
- [ ] Sorun yaşayan makinelerde GL katmanı kapatılarak saha teyidi alınabiliyor.
- [ ] QA aynı build içinde A/B test yapabiliyor.

### Phase 4: Windows QA matrisi oluştur

**Objective:** Sorunun hangi kombinasyonlarda tekrarlandığını düzenli ölçmek.

**Manual Test Matrix:**
1. Steam üzerinden açılmış EXE
2. Steam kapalı / Steam açık karşılaştırması
3. Borderless fullscreen / windowed
4. Tek monitör / çoklu monitör
5. Farklı refresh rate kombinasyonları
6. NVIDIA / AMD / Intel sistemler
7. PrintScreen / Win+Shift+S / Alt+Tab ayrı ayrı

**Acceptance Criteria:**
- [ ] En az 3 farklı Windows makinede tekrar edilebilir sonuç tablosu var.
- [ ] Her testte GL on/off farkı not edildi.

## What Should NOT Be Done

### 1. Kısa vadede tüm render backend'i değiştirme

**Yapılmamalı çünkü:**
- Proje çok yoğun `Surface`, `SRCALPHA`, `BLEND_RGBA_ADD`, `BLEND_RGBA_MULT`, `smoothscale`, geçici overlay surface üretimi kullanıyor.
- Bu geçiş performans iyileştirmesinden önce görsel regresyon üretir.
- Mevcut bug için hedefli çözüm değil.

### 2. Sorunu gizlemek için rastgele `sleep`, ekstra debounce veya ikinci `flip` ekleme

**Yapılmamalı çünkü:**
- Bu tip yamalar belirtileri bazen azaltır ama root cause'u çözmez.
- Özellikle düşük/orta donanımlı makinelerde yeni timing bug'ları yaratır.

### 3. `gl_compat`i tamamen hemen kaldırma

**Yapılmamalı çünkü:**
- Steam overlay görünürlüğünü veya davet/overlay UI akışını tekrar bozabilir.
- Önce Plan A/B ile daha düşük maliyetli stabilizasyon denenmeli.

### 4. Fullscreen davranışını şimdi kökten değiştirme

**Yapılmamalı çünkü:**
- Mevcut raporun asıl tetikleyicisi fullscreen tek başına değil; recovery + GL etkileşimi.
- Fullscreen mantığını bir anda değiştirmek ayrı regresyon alanı açar.

## Final Recommendation

**Uygulanmalı:**
1. Plan A
2. Plan B
3. Plan C

**Şimdilik uygulanmamalı:**
1. Plan D
2. Plan E

## Expected Outcome

Doğru uygulama sırası ile:
- PrintScreen yanlış panel/frame sorunu büyük ölçüde azalmalı.
- Alt+Tab dönüşündeki 1-2 saniyelik siyah ekran veya donma hissi belirgin biçimde düşmeli.
- Steam overlay işlevselliği korunmalı.
- Sorun yaşayan sistemler için kontrollü fallback mevcut olmalı.
