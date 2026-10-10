# Windows Smoke Test Kılavuzu — DALGA B/C Canlı Doğrulama + Faz 6 Onayı

> Tarih: 2026-10-09 (10 Ekim tur kaydı için bkz. ANALIZ §9). Hedef commit'ler: v2 `main` = `a48150e`, demo `release/demo` = `42afa05` (push edildi).
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
git pull origin main   # a48150e'a gelmeli
git log --oneline -1
```

### 1.2 İki koşum modu — ikisini de öner
1. **Kaynak koşusu (ilk tur, hızlı):** telemetri env ile kolay açılır.
   - Ön koşul: Python 3.12 + `py -3.12 -m pip install -e ".[dev]"` (PyInstaller/VS gerekmez).
   - Steam online özellikleri opsiyonel: `steam_net_bridge*.pyd` yoksa oyun açılır, online kapanır.
2. **EXE koşusu (ikinci tur, tam doğrulama):** frozen build davranışı + telemetri otomatik AÇIK. EXE'yi Steam'den başlatmanın yolları:
   - **Tam tur (önerilen — normal yayın akışın):** derlenen yeni build'i ContentBuilder/steamcmd akışınla Steam'e yükle (ör. `steamworks/scripts/app_build_full.vdf`) ve Steam'den **ana oyunu** başlat. Gerçek launch ortamı: overlay + Steamworks + Launch Options birebir. Koşumdan önce `git pull` (hedef commit) yapıldığından emin ol. Not: ana oyun yayında olduğundan, her smoke turunda canlı (default) dalın build'ini değiştirmek istemiyorsan build'i bir **beta dalına** yükleyip o daldan oyna — canlı oyuncular etkilenmez.
   - **Upload'sız hızlı tur:** `dist\Quadrix.exe`'yi Steam'de "Oyun Ekle → Harici Oyun Ekle" ile kütüphaneye ekle ve Steam'den başlat. Overlay (Steam launch ettiği süreci hook eder) ve Steamworks (build `steam_appid.txt`'yi AppID 4428040 ile EXE yanına gömer) yine aktiftir.
   - **Direkt çift tıklama:** overlay hook edilmez — yalnız Odak A/C/D/G için geçerli; Odak B (overlay) ve E/F (Steam yolları) sınamaz.

### 1.3 EXE derlemek (ikinci tur için)
v2 repo kökünden (PowerShell) — **ana oyun (Full) için `tetris.spec`**:
```powershell
powershell -File .\scripts\build\build_windows_exe.ps1 -Clean -SpecFile 'packaging/specs/tetris.spec'
Get-Item dist\Quadrix.exe
```
(Playtest turu istersen `packaging/specs/tetris_playtest.spec` — AppID ve veri klasörü farklı olur; bu kılavuz ana oyunu esas alır.)
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
- **EXE / Steam koşusu: telemetri için elle bir şey yapmana gerek yok — otomatik AÇIK** (frozen + Steam runtime algısı; `src/perf_telemetry.py` `is_enabled`). Launch Options env'i strip etse bile `sys.frozen` bayrağı env'e bağlı değildir, kapatamaz. Ekstra garanti istersen **sentinel dosya**: `%APPDATA%\quadrix_full\local\PERF_ON.txt` (boş dosya yeterli; gl_debug.log ile aynı klasör).
- Kapatmak istersen: `QUADRIX_PERF_TELEMETRY_DISABLE=1` (en yüksek öncelikli — smoke turunda set ETME).
- **Veri klasörü AppID'ye göre** (src/data_paths.py `_APP_NAME_BY_STEAM_APPID`): ana oyun/mağaza 4414520 → `%APPDATA%\quadrix_full` — algılanamayan durumda fallback de `quadrix_full`, yani **ana oyun turunda klasör her halükârda budur** (playtest 4428040 → `quadrix_playtest`; bu kılavuzda kullanılmıyor).
- **Kendini anında doğrula:** oyunu bir kez başlat ve `%APPDATA%\quadrix_full\local\gl_debug.log` başındaki `PERF telemetrisi AÇIK — [PERF]/[GECIS]/[HITCH]/[OLAY] satırları toplanacak` satırına bak (oyun durumu kendisi loglar; sdl2_overlay açılışta yazar). Sentinel/env yalnızca kaynak koşumunda (`py main.py`) gerekir — Steam/frozen turunda otomatiktir.
- **Nereye yazar:** JSONL: `%APPDATA%\quadrix_full\local\perf\perf_telemetry_<oturum>.jsonl` — oyun açılışında konsolda/startup kaydında `telemetry_path` olarak kesin yol yazılır; şüphede kalırsan oyunu aç ve o satırı not al. İnsan-okur özet: `%APPDATA%\quadrix_full\local\gl_debug.log` içinde `[PERF]`, `[HITCH]` (>=70 ms tek kare), `[GECIS]` (ekran geçiş süresi: süre/kare/ilk_kare/en_kötü_kare), `[OLAY]` (Alt+Tab/PrintScreen odak olayları — A odaklarının kanıtı).

---

## 2. Test Odakları (sırayla)

### Odak A — PrtSc / Alt+Tab / focus-recover (en kritik yeni yol)
**Ne değişti:** eski kod PrintScreen algılamayı HER ZAMAN reddediyordu (keycode/scancode guard hatası, 0x40000046); C7 ile prtsc yolu ilk kez canlandı. 900 ms set_mode bütçesi tüketilmişken gelen Alt+Tab kurtarma isteği eskiden sessizce KAYBOLUYORDU; artık ~901 ms'ye ertelenir (defer) ve gerçekten çalışır.

> **PrtSc kanıt durumu (2026-10-09, 13:42 TR koşumu):** PrtSc'ye basıldı, gl_debug.log'da
> `[OLAY] PrintScreen yakalama` satırı GELMEDİ. Kod mantığı testte sağlam (VDS 6/6) ve
> guard düzeltmesi (05af5b3, 10-08 22:33 UTC) DALGA B prewarm'ından 82 dk SONRA push
> edildiğinden, Steam build'inin prtsc düzeltmesini içermemiş olması mümkün. Telemetri
> kaydına git/commit bilgisi işlenmediğinden build'in kod seviyesi veriden okunamıyor.
> Ayrım testi için **önce A-0'yı koş** (kaynak koşumu, 2 dakika), sonra EXE turu.

**A-0 (yeni — prtsc kırık-katman ayrımı, kaynak koşumu):** Build'den bağımsız, güncel kodla:
```powershell
$env:QUADRIX_PERF_TELEMETRY = "1"; $env:QUADRIX_OVERLAY_PERF = "1"
py main.py
```
Ana menüde 2-3 sn bekle, **PrintScreen**'e bas (düz PrtSc — Win+PrtSc değil), 1 sn bekle, kapat.
`%APPDATA%\quadrix_full\local\gl_debug.log`'da `[OLAY] PrintScreen yakalama` ara:
- **VARSA:** kod + ortam sağlam → kırık = Steam'deki build eski kod → `git pull` + EXE'yi yeniden derle/yükle, Odak A'yı EXE ile tekrarla.
- **YOKSA:** kırık = ortam → sırayla kontrol et:
  1. Windows 11: Ayarlar → Erişilebilirlik → Klavye → **"Print screen tuşuyla ekran yakalamayı aç" KAPALI olmalı** (açıkken Windows tuşu yakalar, SDL'ye keydown hiç gitmez — algı yapısal olarak ölür).
  2. Dizüstüysen Fn kilidi: bazı klavyelerde PrtSc ancak Fn+PrtSc ile gerçek tuşa düşer.
  3. Menüde, oyun penceresi ODAKLIYKEN bas (Alt+Tab değil).

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
1. Oyunu **Steam üzerinden** başlat (kaynak koşusunda `config\runtime\steam_appid.txt` AppID 4414520; EXE'de zaten).
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
1. Steam'de online PvP maçına gir (tek taraflıysa lobi ekranı + mümkün olan kadar oyun içi görüş).
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

### Odak H — Kalan Kanıt Kapıları (DALGA D §4; 10 Ekim turu sonrası açık olanlar)
10 Ekim turu K-3 (12 mod girişi, temiz) ve K-4 (mağaza cold-start PASS) ölçümlerini topladı; K-2/K-5/K-6 hâlâ açık, K-1 tek bir netleştirmeye muğlak (ANALIZ §9.9). Sonraki turlarda:

1. **K-1 netleştirme (kaynak koşum, 2 dk):** oyunu kaynak koşumda aç ve menüde kal; Windows "Print screen tuşuyla ekran yakalamayı aç" (Ayarlar → Erişilebilirlik → Klavye) KAPALI olduğunu doğrula; oyun penceresi odaklıyken PrtSc'ye DÜZ bir kez bas, 2-3 sn bekle, kapat.
   - BEKLENEN: `gl_debug.log`'da `[OLAY] 'PrintScreen yakalama'` satırı. Satır VARSA algı kanalı kaynak koşumda sağlam → K-1 kırık = EXE/derleme katmanı (D11 gerekçesi güçlenir). Satır YOKSA ortam katmanı (Win11 hotkey yakalaması) → aynı turu toggle'ı KAPALI yapıp + odak teyidiyle tekrarla.
2. **K-2 (EXE'de C7 canlı kanıt):** güncel koddan EXE derle (§1.3, pin `a48150e`+); EXE'de A-1 prtsc (menü + oyun içi) ve A-3 kesişim senaryosunu koş.
   - BEKLENEN: prtsc algılanıyor + toparlanıyor; kesişimde erteleme, kayıp yok. Pre-C7 EXE'de bu kanal yapısal ölüydü (scancode guard) — bu tur C7'nin EXE-düzeyi canlı kanıtı olur (ANALIZ §9.3: 10-10 turunda toplanamadı).
3. **K-5 (online ~155 ms, D9 kapısı):** telemetri açıkken Steam'de online PvP'ye ve (mümkünse) online coop'a gir; maçta 1-2 dk oyna, lobiden çık.
   - BEKLENEN: JSONL'de online PvP/coop durum pencereleri toplanır; ~155 ms giriş penceresi tekrar ölçülür → D9 (OP-038/039/040 takas) kıyas tabanı. 10-10 turunda online state hiç toplanmadı (ANALIZ §9.6) — D9 kanıt-gated, bu tur onu açar.
4. **K-6 (OP-049 canlı donanım, D8 kabul şartı):** gamepad'le (XInput / Deck) 3-5 dk oyna: DAS/ARR tepkisi, menü navigasyonu, Deck'te odak yönetimi.
   - BEKLENEN: gecikme hissi/yanıtsız girdi yok. Not: kantitatif gamepad kanalı telemetride YOK — buradaki gözlem niteldir; ölçüm kanalı eklemek ayrı iş olarak D-plan'da kayıtlı.

---

## 3. Ölçümleri Toplama
Koşu bitince (telemetri açıkken):
- JSONL: `%APPDATA%\quadrix_full\local\perf\` (ana oyun 4414520; playtest koşumunda `quadrix_playtest`) — açılıştaki `telemetry_path` konumu.
- İnsan-okur: `%APPDATA%\quadrix_full\local\gl_debug.log` — özellikle `[HITCH]`, `[GECIS]`, `[OLAY]` satırları; `slow_handler` JSONL olayı (>=150 ms handler).
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

Kapı turları (Odak H; DALGA D §4):
- [ ] H K-1 prtsc [OLAY] satırı toplandı (veya toggle/odak netleştirildi)
- [ ] H K-2 EXE prtsc + kesişim canlı kanıtı (C7)
- [ ] H K-5 online PvP/coop ölçümü toplandı
- [ ] H K-6 gamepad canlı gözlem yapıldı

---

## 6. Demo (quadrix-demo) Farkları
- Kod: `release/demo` dalı, `42afa05`; aynı A-G odakları geçerli (DALGA B/C iki repoya da uygulandı).
- EXE derlemesi: `packaging/specs/tetris_demo.spec` (build betiği ve parametreler aynı).
- **Perf telemetri (çekirdek döngü) demo'da da VAR** (perf_telemetry.py + main.py begin_frame/end_frame/record_startup — 10-10 kaynak taramasıyla doğrulandı): durum-seviyesi JSONL frame/handler/present ölçümleri toplanır; yalnız FAZ-seviyesi kırılımı (`_game_perf_phase_*`/`_store_*`/`_settings_*`/`_menu_*`) v2-only'dir (bkz. rapor §8).
- Veri klasörü demo'da farklı olabilir (`quadrix_demo`); EXE/Steam koşusunda telemetri yine otomatik açıktır.
- Demo mod kısıtları (demo_config) nedeniyle bazı modlar kartta görünmeyebilir — görünen modlar için D uygula.

*Kaynaklar: plans/2026-03-08-performance-thermal-optimization-plan.md (Faz 1-5 smoke checklist'leri 7A-7E, Faz 6), reports/Quadrix_Kapsamli_Performans_Arastirmasi.md (DALGA B/C kayıtları + kanıt sınırları), docs/DERLEME_VE_YAYINLAMA_REHBERI.md, src/perf_telemetry.py + src/sdl2_overlay.py (telemetri kapıları).*
