# Windows Smoke Test Kılavuzu — DALGA B/C Canlı Doğrulama + Faz 6 Onayı

> Tarih: 2026-10-09. Hedef commit'ler: v2 `main` = `beee5c6`, demo `release/demo` = `95f4eb5` (push edildi).
> Süre tahmini: tam tur ~45-60 dk; hızlı tur (A-D) ~20 dk.
> Amaç: SDL dummy sürücüsünde sınanamayan yolları canlı Windows'ta doğrulamak — DALGA C'in kapanış koşulu ve 2026-03-08 perf/termal planının Faz 6 onayı.
> Bu kılavuz v2 (tam sürüm) için yazılmıştır; demo farkları son bölümde.

---

## 0. Ne Doğruluyoruz (özet tablo)

| # | Odak | Değişiklik | Nasıl sınanır |
|---|------|-----------|---------------|
| A | PrtSc / Alt+Tab / focus-recover | OP-034 + C7 (prtsc canlanması, 900 ms defer) | elle — en kritik |
| B | Steam overlay GL modu | OP-034 (GL mod cache) | elle + ayar değişimi |
| C | Mağaza ilk giriş karesi | DALGA B prewarm (2748 → 19 ms) | elle + [GECIS] log |
| D | Mod girişleri | Faz 6 (paylaşılan SoundManager) | elle — planın onay kapısı |
| E | Online PvP HUD | OP-006 (combo popup/header cache) | elle |
| F | Steam panel istatistik güncelliği | OP-003 (2 s debounce) | elle |
| G | Genel tarama | Faz 1-5 (pacing/texture/efekt/menü/overlay) | elle — kısaltılmış checklist |

---

## 1. Hazırlık

### 1.1 Kodu Windows makinesine çek
Windows'taki repo kopyasında (v2):
```powershell
git pull origin main   # beee5c6'a gelmeli
git log --oneline -1
```

### 1.2 İki koşum modu — ikisini de öner
1. **Kaynak koşusu (ilk tur, hızlı):** telemetri env ile kolay açılır.
   - Ön koşul: Python 3.12 + `py -3.12 -m pip install -e ".[dev]"` (PyInstaller/VS gerekmez).
   - Steam online özellikleri opsiyonel: `steam_net_bridge*.pyd` yoksa oyun açılır, online kapanır.
2. **EXE koşusu (ikinci tur, tam doğrulama):** frozen build davranışı + telemetri otomatik AÇIK.

### 1.3 EXE derlemek (ikinci tur için)
v2 repo kökünden (PowerShell):
```powershell
powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris_playtest.spec'
Get-Item dist\Quadrix.exe
```
Ön koşullar: `py -3.12` çalışıyor; VS2022 (MSVC) + CMake + pybind11; Steamworks SDK `steamworks\sdk\` altında; pip `PyInstaller>=6.20`.
Derleme sonrası logda şu satırları doğrula (yoksa Steam overlay/ekran görüntüsü frozen'da devre dışı kalır — oyun yine çalışır):
- `pygame._sdl2 .pyd eklendi: video.cp312-win_amd64.pyd`
- `steam_net_bridge.cp312-win_amd64.pyd kopyalandi`
- `Derleme basarili`
Loglar: `reports\logs\build_stdout.log` / `build_stderr.log`.

### 1.4 Telemetriyi aç (ölçüm istiyorsan)
- **Kaynak koşusu:** PowerShell'de:
  ```powershell
  $env:QUADRIX_PERF_TELEMETRY = "1"
  $env:QUADRIX_OVERLAY_PERF   = "1"   # gl_debug.log [PERF]/[HITCH]/[GECIS]/[OLAY] satırları (SDL2 overlay aktifken)
  py main.py
  ```
- **EXE / Steam koşusu:** telemetri otomatik AÇIK (frozen + Steam runtime algısı). Steam Launch Options env'i strip etse bile güvenilir yol — **sentinel dosya**: `%APPDATA%\quadrix_full\local\PERF_ON.txt` (boş dosya yeterli).
- Kapatmak istersen: `QUADRIX_PERF_TELEMETRY_DISABLE=1` (en yüksek öncelikli).
- **Nereye yazar:** JSONL olayları `%APPDATA%\quadrix_full\local\perf\` altında; oyun açılışında konsolda/startup kaydında `telemetry_path` olarak kesin yol yazılır — not al. İnsan-okur özet: `gl_debug.log` içinde `[PERF]`, `[HITCH]` (>=70 ms tek kare), `[GECIS]` (ekran geçiş süresi: süre/kare/ilk_kare/en_kötü_kare), `[OLAY]` (Alt+Tab/PrintScreen odak olayları — A odaklarının kanıtı).

---

## 2. Test Odakları (sırayla)

### Odak A — PrtSc / Alt+Tab / focus-recover (en kritik yeni yol)
**Ne değişti:** eski kod PrintScreen algılamayı HER ZAMAN reddediyordu (keycode/scancode guard hatası, 0x40000046); C7 ile prtsc yolu ilk kez canlandı. 900 ms set_mode bütçesi tüketilmişken gelen Alt+Tab kurtarma isteği eskiden sessizce KAYBOLUYORDU; artık ~901 ms'ye ertelenir (defer) ve gerçekten çalışır.

1. Oyunu aç, ana menüde kal. **PrintScreen** tuşuna bas.
   - BEKLENEN: ekran 1 anlık kararma/bozulur gibi olur (set_mode), ~220 ms içinde kendini toparlar; oyun kilitlenmez. `gl_debug.log`'da `[OLAY]` prtsc satırı görünür.
   - KÖTÜ: hiç tepki yok + logda prtsc olayı yok (algı yine ölü) ya da siyah/bozuk ekran kalıcı olur.
2. **Alt+Tab** ile oyundan çık, 2-3 sn sonra geri dön.
   - BEKLENEN: pencere düzgün geri gelir, input çalışır, pacing bozulmaz (tek set_mode + odak isteği, ~220 ms debounce).
   - KÖTÜ: siyah/odaksız pencere kalır, donar, ya da ekran çok geç (1 sn+) ve bozuk gelir.
3. **Kesişim senaryosu (defer düzeltmesinin bizzat testi):** PrintScreen'e bas, ardından HEMEN (~1 sn içinde) Alt+Tab ile başka pencereye geç ve oyuna geri dön.
   - BEKLENEN: dönüş ~1 sn'ye kadar gecikebilir (erteleme bilinçli) ama pencere SONUNDA düzgün toparlanır — hiç kaybolmaz.
   - KÖTÜ: oyuna dönünce siyah/bozuk kalır ve ancak ikinci Alt+Tab ile düzelir (eski drop bug'ı).
4. Aynı akışı oyun İÇİNDE (parça düşerken) tekrarla: 1-2-3.

### Odak B — Steam overlay GL modu
1. Oyunu **Steam üzerinden** başlat (kaynak koşusunda `config\runtime\steam_appid.txt` AppID 4428040; EXE'de zaten).
2. **Shift+Tab** ile overlay'i aç-kapat birkaç kez (menüde ve oyun içinde).
   - BEKLENEN: overlay görünür, oyun donmaz, görüntüde yırtılma/siyah ekran/ters frame yok.
3. Ayarlarda `steam_overlay_gl` (auto/off/force) değerini DEĞİŞTİR, mağaza-oyun arası bir ekran geçişi yap.
   - BEKLENEN: yeni mod ANINDA geçerli (cache otomatik düşer). Örn. `force`'ta overlay hâlâ stabil.
   - KÖTÜ: ayar değişikliğinden sonra overlay eski modda kalır / açılmaz / siyah ekran.
4. Alt+Tab + overlay kombinasyonu: overlay açıkken Alt+Tab, geri dön.
   - BEKLENEN: overlay kaybolmaz, oyun boşa düşmez.

### Odak C — Mağaza ilk giriş karesi (2748 → 19 ms)
1. Oyun açıldıktan sonra menüden **mağazaya ilk kez gir**.
   - BEKLENEN: giriş akıcı; eski ~2,7 s'lik tek karelik donma YOK. [GECIS] log satırında geçiş süresi görünür.
2. **Cold-start tekrarı** (raporun açık önerisi — tek koşu çifti sağlamlaştırma): oyunu kapat, yeniden aç, tekrar mağazaya gir. Donma geri gelmemeli.
3. Mağazada sekmeler/ürünler arasında gez (en kötü beklenen tek kare ~96 ms sınıfı — algılanabilir kısa duraksama kabul edilebilir).
   - KÖTÜ ve ayırt etme kılavuzu:
     - **206-500 ms** tek kare → prewarm/önbellek düşüyor (Bileşen A).
     - **2,4 s+** donma → Bileşen B (AV/disk ilk-erişim, OS seviyesi) — `store_event_poll_ms`/`store_input_ms` faz metreleri ve `slow_handler` olayı logda atfı verir.

### Odak D — Mod girişleri (Faz 6 onayı)
**Ne değişti:** her mod girişinde taze `SoundManager()` kurulması yerine paylaşılan örnek — 2-3 s'lik ses altyapısı donması kalkmalı.

1. Sırayla her mod kartına gir ve menüye dön: Sprint, Ultra, Zen, Hardcore, Survival, Cascade, Daily Challenge, Tetris2/Quadrix Extra, Mystery (Kart Ustalığı), Wide, Campaign, Tutorial.
   - BEKLENEN: hiçbir girişte 2-3 s'lik donma/blokaj yok; müzik kesintisiz akar; giriş anında takılma yok.
   - KÖTÜ: mod seçiminden sonra 2-3 s'lik donma (ses altyapısı), müziğin çift başlaması veya kesilmesi.
2. Mod içinde 30 sn oyna, menüye dön, başka moda gir — tekrar eden geçişlerde de akıcı kalmalı.

### Odak E — Online PvP HUD (OP-006)
1. Playtest'te online PvP maçına gir (tek taraflıysa lobi ekranı + mümkün olan kadar oyun içi görüş).
2. Combo popup'ları ve HUD başlığını (isim/skor/satır sayısı) izle.
   - BEKLENEN: combo mesajı doğru görünür, fade parlaklığı doğru tazelenir (soluk/yanlış alfa kalıntısı yok); skor/satır güncel.
   - KÖTÜ: popup yanlış alfa ile çizilir, header skoru güncellenmez, popup hiç görünmez.
   - Not: oyun genel akıcılık artışı ölçümle kanıtlı (kare µs 78→27 medyan) ama wall-clock hissi bu koşuda değerlendirilir.

### Odak F — Steam panel istatistik güncelliği (OP-003)
1. Oyunda birkaç satır temizle, seviye atla.
2. Steam profilinde/oyun istatistik paneline bak.
   - BEKLENEN: istatistikler ~2 s içinde toplu güncellenir (bilinçli debounce); yeni başarım anında toast açılır.
   - KÖTÜ: panel dakikalarca stale kalır (flush çalışmıyor) veya satır temizleme sırasında takılma hissi.
   - Bilinçli kabul: crash anında son ~2 s'lik sayaç kaybı mümkün (temiz çıkış/restart force flush ile kapatılır) — hata sayılmaz.

### Odak G — Genel tarama (Faz 1-5'in kısaltılmış checklist'i)
Her biri 1-2 dk, "bozulma var mı" gözlemi:
1. **Pacing (Faz 1):** menüde 2-3 dk bekle — titreme/aşırı hız yok; FPS limiti ayarında 0 = "Otomatik" etiketi; sabit 60'a alıp karşılaştır, tekrar Otomatik'e dön (sınırsız gibi davranmamalı, 60'a çakılı his de vermemeli).
2. **Texture (Faz 2):** textured blok stili seç; parçalarda/rotasyonlarda yanlış texture, bulanıklaşma, kırpılma yok; PvP'de iki board eşdeğer.
3. **Efekt (Faz 3):** satır temizleme sweep/particle/glow eski kalite; tekrar eden efektlerde ghosting/kirlenme yok; pause ve menü dönüşünde eski efekt artığı taşınmaz.
4. **Menü kart cache (Faz 4):** statik kartlar (daily/achievements/workshop/block_styles) doğru ve stabil; dinamik kartlarda hover canlı; dil değişince kart metinleri güncellenir; menüye her dönüşte doğru içerik.
5. **Overlay uzun akış (Faz 5):** 5-10 dk oynanış + birkaç overlay aç-kapa + menüye dönüş; çıkışta takılma/siyah pencere/kapanmayan süreç yok.
6. **Pause:** oyun içinde pause 5-10 sn, dönüşte akış bozulmaz (müzik ducking/unducking normal).

---

## 3. Ölçümleri Toplama
Koşu bitince (telemetri açıkken):
- JSONL: `%APPDATA%\quadrix_full\local\perf\` — açılıştaki `telemetry_path` konumu.
- İnsan-okur: `gl_debug.log` — özellikle `[HITCH]`, `[GECIS]`, `[OLAY]` satırları; `slow_handler` JSONL olayı (>=150 ms handler).
- Bana gönderirken: log dosyasının ilgili satırları + hangi odak/adım + gözlemin tarifi yeterli.

## 4. Hata Bulunursa — Rapor Formatı
Bana şunu yaz (kanıt-önce-iddia için):
1. **Odak + adım** (ör. "A-3 kesişim senaryosu").
2. **Gözlem** (ne oldu, ne beklerdin — yukarıdaki BEKLENEN/KÖTÜ ayrımından).
3. **Koşum modu:** kaynak / EXE / Steam; telemetri açık mıydi.
4. **Loglar:** `[HITCH]/[GECIS]/[OLAY]` satırları veya JSONL'den `slow_handler` + `frame_ms.max` değerleri.
5. Varsa ekran kaydı (OBS/Win+G) ve makine bilgisi (GPU, sürücü, Windows sürümü, ekran Hz).
6. Tekrarlanabilir mi: aynı adım ikinci koşuda da mı oldu.

Sonuç temizse: "DALGA B/C Windows smoke TEMİZ, Faz 6 ONAY" demen yeterli — DALGA D'yi açarım. Bulgu varsa: önce o bulgunun kök nedenini indiririz, DALGA D bekler.

## 5. Kabul Özeti (işaretle)
- [ ] A prtsc algılanıyor + toparlanıyor (menü + oyun içi)
- [ ] A Alt+Tab dönüşü tek set_mode ile temiz
- [ ] A kesişim senaryosu: erteleme çalışıyor, kayıp yok
- [ ] B overlay aç-kapa stabil (menü + oyun içi)
- [ ] B GL ayar değişimi anında geçerli
- [ ] C mağaza ilk giriş donmasız + cold-start tekrarı temiz
- [ ] D 12 mod girişinde ses donması yok
- [ ] E online HUD (popup alfa + header) doğru
- [ ] F Steam panel ~2 s içinde güncel
- [ ] G pacing / texture / efekt / menü / overlay taraması temiz
- [ ] Çıkış akışı temiz (siyah pencere / kapanmayan süreç yok)

---

## 6. Demo (quadrix-demo) Farkları
- Kod: `release/demo` dalı, `95f4eb5`; aynı A-G odakları geçerli (DALGA B/C iki repoya da uygulandı).
- EXE derlemesi: `packaging/specs/tetris_demo.spec` (build betiği ve parametreler aynı).
- **Perf telemetri katmanı demo'da yok** (v2-only): JSONL/`[PERF]` ölçümleri toplanamaz — demo turu GÖZLEMSEL; ölçüm isterken v2 tarafını koş.
- Veri klasörü demo'da farklı olabilir (`quadrix_demo`); sentinel gerekmiyor (telemetri zaten yok).
- Demo mod kısıtları (demo_config) nedeniyle bazı modlar kartta görünmeyebilir — görünen modlar için D uygula.

*Kaynaklar: plans/2026-03-08-performance-thermal-optimization-plan.md (Faz 1-5 smoke checklist'leri 7A-7E, Faz 6), reports/Quadrix_Kapsamli_Performans_Arastirmasi.md (DALGA B/C kayıtları + kanıt sınırları), docs/DERLEME_VE_YAYINLAMA_REHBERI.md, src/perf_telemetry.py + src/sdl2_overlay.py (telemetri kapıları).*
