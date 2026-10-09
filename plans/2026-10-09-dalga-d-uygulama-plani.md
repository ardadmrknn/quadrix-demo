# DALGA D Uygulama Planı — Ölçüm-Kapılı Orta Risk

> Tarih: 2026-10-09. Kullanıcı kararıyla DALGA D AÇILDI; smoke kılavuzundaki canlı
> doğrulama kapıları (A-0/A-1/A-3, D, C-2, E) bu dalganın içine taşındı —
> "önce tur, sonra dalga" sırası kaldırıldı, ölçümler dalga akışında toplanır.
> Kaynak bulgu tabanı: `reports/Quadrix_Kapsamli_Performans_Arastirmasi.md` §DALGA D
> (satır 433) + maddelerin kendi bölümleri. Canlı kanıt tabanı:
> `reports/telemetry/quadrix_full_windows/ANALIZ_2026-10-09.md`.
>
> **Depo pratiği:** DALGA B/C her maddede "iki repo, birebir aynı edit" deseniyle
> uygulandı (v2 `main` + demo `release/demo` senkron commit'ler). Rapor §437'deki
> "uygulama yalnız quadrix-demo'da; v2 salt-okunur" satırı bu pratikle ÇELİŞİYOR —
> ground truth hiyerarşisi gereği (CLAUDE.md §3/4) kod pratiği esas alınır ve
> saplama burada kayıt altına alındı. DALGA D de iki repo senkron uygulanır.
>
> **Ölçüm altyapısı sınırı (rapor §8):** tutorial/guide/avatar ekranlarında faz
> metreleri YOK — OP-019/020 kazanım iddiaları metre eklenmeden kanıtlanamaz.
> Metre ekleri opt-in ve ölçüm-kapılı olacak (üretim kare maliyeti OP-051 dersi).

---

## 0. Dallanacak Maddeler (rapor sırasıyla)

| # | Bulgu | Bölge | v2 konum | demo konum | Risk |
|---|-------|-------|----------|------------|------|
| D1 | OP-063 fonksiyon-içi import'lar kare yolunda | çekirdek | game.py:5409, pvp:5070, gme 12058/12156, sweep 820/879, tutorial `_wrap_text` re | birebir muadiller | sıfır (davranış değişimi yok) |
| D2 | OP-013 sweep bandı: 3 SRCALPHA + 160-320 dilim blit/kare | çekirdek | sweep_effects.py:784-839, 1014 | sweep_effects.py:843+ | düşük |
| D3 | OP-014 fall offset hücre-başı lineer tarama | çekirdek | game.py:4037 | game.py:3908 | düşük |
| D4 | OP-015 (+OP-059) milestone panel + MILESTONE_COLORS | çekirdek | game.py:6297-6399 | game.py:6161-6179 | düşük-orta |
| D5 | OP-019 tutorial ders-içi layout fit+wrap her kare | menü | tutorial.py:539-676 | tutorial.py:457+ | orta (metin düzeni) |
| D6 | OP-020 avatar editörü degrade + smoothscale | menü | avatar_editor.py:290-294, 412 | avatar_editor.py:273, 393 | düşük |
| D7 | OP-035 PatchedFont `.copy()` / `render_shared` | altyapı | text_cache.py:82-89 | text_cache.py:89-96, 98-118 | orta (varsayılan yol KORUNMALI) |
| D8 | OP-049 gamepad/connection polling throttle | girdi | her kare | her kare | orta (canlı donanım şartı) |
| D9 | OP-038/039/040 heartbeat'ler | online | online_coop_game.py:3068+, 2975+, online_pvp_game.py:595, 4757+ | muadiller | orta-yüksek (takas açık karar) |
| D10 | OP-018 ghost memoize (board_rev denetimi) | çekirdek | game.py:4544-4552 | game.py:4381 | EN YÜKSEK (bayat ghost = görsel bug) |

Koşullu maddeler (kanıt gelirse eklenir):
- **D11 prtsc kök düzeltme:** A-0 kırık-katman sonucu "kaynak koşumda da log YOK"
  çıkarsa SDL event akışına dayanmayan algı (`GetAsyncKeyState(VK_SNAPSHOT)` yolu,
  odak/hijack'ten bağımsız) D10 sonrasına eklenir. Kaynak koşumda log VARSA maddenin
  kendisi düşer — kırık build demektir, çözüm re-pull/rebuild'dir.

## 1. Uygulama Sırası ve Gerekçesi

Risk artan sırada; her madde kendi doğrulama paketiyle atomik kapanır:

1. **D1 (import'lar):** davranış değişimi yok — en güvenli başlangıç; D2/D5'in
   ön koşulu (sweep/tutorial import'ları aynı dalga).
2. **D2 → D3 → D4 (çekirdek efekt zinciri):** satır temizleme yolu; piksel-parite
   deseni DALGA C'de kanıtlanmış LRU/tampon kalıpları (OP-017/021/022 dersleri).
3. **D5 → D6 (menü ekranları):** layout cache'ler; metin düzeni korunumu test-öncesi.
4. **D7 (render_shared):** ön koşul — demo'nun text_cache ileri sürümü (sys.modules
   alias, idempotent `patch_font`, `render_shared` kancası, `test_text_cache.py`)
   v2'ye taşınır (rapor §7); ardından YALNIZCA profil-probe ile en sıcak salt-okunur
   blit noktalarında benimseme; her noktada "yüzey mutasyon almıyor" lokal test şartı.
   Varsayılan `.copy()` yolu DOKUNULMAZ (savunmacı ve doğru — yüzlerce çağrıcı mutasyon yapıyor).
5. **D8 (throttle):** 250 ms (≤500 ms üst sınır — "geç güncellenen get_count" Deck/macOS
   platform uyarısı); `handle_hotplug_event` gerçek-zamanlı yolu zaten var; girdi okuma
   döngüsü (DAS/d-pad) her kare kalır. Canlı donanım kanıtı kapı 3'te toplanır.
6. **D9 (heartbeat'ler):** KOD ÖNCESİ KANIT ŞARTI — online_coop arşiv bulgusu
   (10×~155 ms tekrarlayan tek kare, 2026-10-07; 10-09 rapor B-A notu aynı bölge)
   + canlı E turu ölçümü. Takas (unreliable kanalda düzeltme gecikmesi) açık karar:
   - OP-038: guest 16 ms `force=True` (~62 JSON/sn durgunken) → ack-durumuna bağla
     (`_guest_piece_unacked_since` zaten var; kayıp-kurtarma korunur).
   - OP-039: signature aynıysa kadans 33→200 ms + config COOP_BOARD_STATE/COOP_GAME_CONFIG
     kanallarına ayrılır (guest `data.get` varsayılan toleranslı — doğrulanmış).
   - OP-040: PvP imza (grid rev, score, lines) değişmedikçe 100 ms → 500-1000 ms;
     kilit anı event-driven gönderimler aynen kalır.
   Hedef kare etkisi 155 ms duraksamasının kaynağıyla eşleşiyorsa madde önceliklenir.
7. **D10 (ghost memoize):** en geniş blast radius (kilit/temizleme yollarının tamamı).
   `(piece.x, y, shape/rot, board_rev)` anahtar; `board_rev` TÜM grid mutasyonlarında
   artan sayaç. Kademeli: önce sayaç altyapısı + denetim testleri, sonra memoize.

## 2. Piksel-Parite Prensipleri (DALGA C dersleri)

- SRCALPHA fill+blit / font.render+blit üretimleri LRU'ya birebir alınır.
- Doğrudan `draw.rect/line` çağrıları ekrana (piksel-alfasız) DOKUNULMAZ —
  OP-017 probe dersi: display yüzeyinde alfa yok sayılır, dönüşüm piksel değiştirir.
- `set_alpha` dönüşümleri PROHİBİT (a² ve karışım farkları — probe ile çürütülmüş).
- Zaman animasyonları `frames_left`/`get_ticks()` kaynaklarından beslenmeye devam
  eder — önbellek anahtarına FAZ girmez, blit konumu girer.
- Anahtar imzalarına `scale_key` dersi: aynı (w,h) farklı ölçekle farklı içerik
  üretebilir (OP-022 dersi — `_content_cache_signature` deseni).

## 3. Her Maddenin Doğrulama Standardı

1. `python -m compileall -q src tests` (iki repo)
2. Maddenin dar paketi (tablo, maddelerin rapor bölümlerinden):
   - D2: v2 `test_country_sweep_effects.py` + `test_country_sweep_localization.py`
     (demo'da yok) + iki repo `test_game_line_clear_fall_animation.py`
   - D3: `test_game_line_clear_fall_animation.py` + v2 `test_flexible_border_lock_and_block_out.py`
   - D4: `test_game_hud_stat_row_clamp.py` + line-clear dar (milestone'a özgü test
     tespit edilemedi — rapor §10/9; kapı 4 verisiyle değerlendirilir)
   - D5: `test_tutorial_runtime.py` + `test_phase8_tutorial_ui_scaling.py`
   - D6: `test_avatar_editor_containment.py`
   - D7: `test_text_cache.py` (v2'ye port) + `test_settings_preset_transition.py`
   - D8: gamepad/hotplug paketi + DAS zamanlama testleri
   - D9: `test_online_coop_network_flow.py`, `test_online_pvp_piece_sync.py`,
     `test_online_pvp_message_validation.py`, v2 `test_online_coop_host_profiler.py`
   - D10: `test_game_polish_das_rotate_ghost.py`, `test_game_ghost_keyboard_guard.py`,
     v2 `test_flexible_border_lock_and_block_out.py`
3. Birleşik koşu (mevcut taban: v2 877+, demo 886+ — DALGA C sonrası gerçek sayı
   koşum anında ölçülür)
4. Ölçüm probe'u (before/after, HEAD worktree vs düzenlenmiş ağaç — C2/C7 deseni;
   `probe_store_draw_perf.py` / `probe_online_c7_hot_paths.py` modellenir)
5. Kapsam kovuğu dersleri (C2/C3): maddenin draw yolu hiçbir testle kapsanmıyorsa
   YENİ smoke test eklenir (demo test eksikliği dersi — 20 geçen test NameError görmedi).

## 4. Canlı Doğrulama Kapıları (smoke turundan taşındı)

Bu kapılar DALGA D değişikliklerinden ÖNCE/KURULUM SIRASINDA toplanır (baseline);
değişiklik sonrası aynı ölçümler maddelerin kabul kıyasları olur:

| Kapı | Ne | Ne zaman | Hangi maddeye girdi |
|------|----|----------|---------------------|
| K-1 | **A-0 prtsc kırık-katman** (kaynak koşumu 2 dk + düz PrtSc) | ilk fırsat | D11 ekleme/düşme kararı |
| K-2 | **A-1/A-3 prtsc + kesişim** (EXE/Steam'de) | D-kapılarıyla aynı turda | C7 canlı kanıt kaydı (DALGA D'yi etkilemez) |
| K-3 | **12 mod girişi** (Faz 6 + 2-3 s ses donması) | D2-D4'ten ÖNCE baseline | D2/D3/D4 kıyas tabanı |
| K-4 | **C-2 mağaza cold-start tekrarı** (kapat-aç, tekrar mağaza) | herhangi | DALGA B sağlamlık kaydı |
| K-5 | **E online PvP + coop ~155 ms tekrar ölçümü** | D9'dan ÖNCE | D9 takas kararı (OP-038/039/040) |
| K-6 | OP-049 canlı donanım (Deck/macOS dahil) | D8 kabul şartı | D8 |

Türkiye-local Windows ana oyun (Full, AppID 4414520) koşusunda telemetri otomatik
açık; JSONL + gl_debug.log kapı ölçümlerini kendiliğinden üretir (kılavuz §1.4).

## 5. Kabul Ölçütleri (DALGA D kapanışı)

1. D1-D10 maddelerinin tamamı (veya koşullu D11) iki repo senkron, atomik Türkçe
   commit zinciriyle kapatılmış; her maddede ölçüm kaydı rapora işlenmiş.
2. Ölçüm-kapısı ihlali yok: hiçbir maddede "çalışıyordur" varsayımı — probe ya da
   canlı kanıt olmayan kazanım iddiası yazılmaz.
3. Birleşik test tabanı en az DALGA C kapanış seviyesinde (v2 877+ / demo 886+).
4. K-1…K-6 kapılarının sonuçları ANALIZ_2026-10-09.md'ye ek kayıt olarak düşülmüş;
   prtsc kırığı (hangi katmansa) kök nedeniyle kapatılmış.
5. DALGA E kapısı (OP-041/042/043/012/061/062) kullanıcı kararıyla ayrı açılır.

---

## 6. Kapanış Günlüğü

- **D1 (OP-063) — KAPANDI 2026-10-09:** v2 `8cd79a0` / demo `0836cdb`. Rapor
  noktalarının büyük bölümü DALGA B'de (b8b829b) zaten kapanmıştı; kalan kare-yolu
  nokta coop_game outer_tint + skin cache import'ları. Koşum sırasında 2 pre-existing
  coop HUD fail'i ayrıca kök-kapatıldı (v2 `4530020` / demo `e4a4ca1`: dar bar katkı
  bütçesi + platform-kırılgan yükseklik pin'leri; 2547a54 worktree koşumuyla
  doğuştan kırmızı olduğu kanıtlandı — A/B-stash iki repoda pre-existing kanıtı).
- **D2 (OP-013) — KAPANDI 2026-10-09 (reçeteden sapma, ölçümle):** v2 `6d50ab0` /
  demo `a2dfa3e`. Raporun buffer/LRU önermesinin **tahsis kısmı ölçümle çürütüldü**:
  taze SRCALPHA 6.3 µs (zero-fill'li), reuse-clear 31-40 µs → buffer-reuse +%25-40
  yavaş ölçüldü, UYGULANMADI; sweep_x = int(progress·travel) kuantası boyut-LRU'yu
  da iskalar. Uygulanan: shimmer profili (band_w, height) LRU'su — içerik saf
  fonksiyon, faz yalnız blit konumu (reçetenin bu kısmı geçerliydi) — + dilim
  döngüsü invariant hoisting + Rect reuse. Kazanım (200 çağrı, 320×60, min-of-5):
  ülke sabit 255→188 ms (−%26, ~−334 µs/kare), büyüyen 153→134 (−%13), rainbow
  sabit 372→275. Parite: 9/9 senaryo digest HEAD ile birebir + demo aynı digest.
  Test: v2 114 / demo 97.
- **D3 (OP-014) — KAPANDI 2026-10-09:** v2 `b865f8d` / demo `c51f30f`. Draw
  başında tek geçişle (row, col)→offset sözlüğü; `_get_block_fall_offset` ve
  ilk-eşleşme semantiği korunur (metot testlerde doğrudan çağrılıyor). Kapsam
  kovuğu: döngüyü süren test YOKTU → `test_game_locked_blocks_fall_offset.py`
  gerçek `_draw_base_scene` yolunu sürer, HEAD worktree'de de yeşil (parite).
  Ölçüm: replika −%78-83 (−174…−247 µs/kare); tam ANIM karesi v2 4.298→4.011 /
  4.192→3.663 ms, demo 3.800→3.566; ANIM-EMPTY delta v2 0.42-0.44→0.19-0.29 ms,
  demo 0.543→0.208. Birleşik A/B: fail kümeleri HEAD ile birebir (v2 20 / demo
  34) → sıfır yeni hata. Pre-existing borç kaydı: v2 kümeleri alt-koşumda yeşil
  (sıra kirliliği); demo store_screen 5 gerçek düşüş da6b9fc'te de kırmızı
  (DALGA D'den eski, ayrı iş). Gözlem (aday D3b): aynı desen coop_game:4158,
  pvp_game:4812, online_pvp_game:7533/7670 çizimlerinde.
- **D4 (OP-015+059) — KAPANDI 2026-10-09:** v2 `e370366` / demo `d2be513`.
  OP-059 iki repoda da DALGA D'den önce uygulanmış çıktı. v2'de panel/glow LRU
  + pulse'sız sabit geometri de zaten modernizasyon içindedir; kalan iş metin
  bloğuydu → (milestone_value, panel_w, panel_h) anahtarlı
  `_milestone_text_block_cache` (LRU 8; hit'te rect + 3 blit, gölge alfası
  üretimde pişirilir). Demo raporun tam hedefiydi: 4 glow →
  `_get_rounded_rect_surface`; gradyan → maskesiz/kare-köşeli
  `_get_milestone_panel_surface` (v2 maskeli paneli taşınmaz — köşe görseli);
  3 render → `_get_milestone_text_surface` (LRU 32). Kapsam kovuğu:
  `test_game_milestone_panel_cache.py` gerçek draw yolunu sürer; soğuk/sıcak
  kare-kare digest birebir (mutasyon kovuğu), demo pulse çevrimi 119→100.
  Ölçüm (interleaved A/B, medyan — sıralı koşum gürültüde yanıltıcı): v2
  0.762→0.614 ms/kare (−148 µs), demo 1.302→0.611 (−691 µs, −%53). Parite
  3/3 digest HEAD ile aynı. Birleşik A/B: fail kümeleri birebir (v2 20/4072,
  demo 34/3496) → sıfır yeni hata.
- **D5 (OP-019) — KAPANDI 2026-10-09 (adres düzeltmesiyle):** v2 `b3369ce` /
  demo `e8d7293`. Raporun işaret ettiği bölge (tutorial.py:539-676, destek
  layout/tip paneli) iki repoda da ÜRETİM-ÖLÜ — tek tüketici bir test. Gerçek
  kare yolu probe'la yeniden haritalandı: `_draw_tutorial_overlay` (2× fit +
  rozet font shrink) + `_draw_inline_howto_hint` (ilk dersler; 3× wrap +
  küçültme döngüsü) — cProfile kare-başı ~56 font.size + 4 wrap. Uygulanan
  (iki repo birebir): tutorial modülünde 3 YERLEŞİM LRU'su (`_wrap_text` 256,
  değer (font, lines) — id kovuğu; `_fit_wrapped_text_block` 96;
  `_get_fitting_font` 32); anahtar `text_cache.cache_generation()` nesli
  (set_font_profile → clear_text_cache kancası; retro_style clear_caches yeni
  Font'lar üretir) + `get_language()` + girdiler. text_cache'e `cache_generation()`
  sayacı eklendi. Render'lar zaten PatchedFont'ta; kalan maliyet blit alanı
  (donanım bağımlı) — kapsam dışı kaydedildi. Kapsam kovuğu:
  `test_tutorial_text_layout_cache.py` (6 test iki repo) gerçek draw yolu +
  soğuk/sıcak digest + sıcakta büyümemesi + invalidasyon. Ölçüm (interleaved
  A/B 6 tur, medyan): v2 −0.902 ms/kare, demo −1.008 ms/kare (ikisi de 6/6
  negatif; ders-içi donma fazı overlay+howto). Parite: edited == HEAD == soğuk
  == sıcak digest (4 ağaç; v2/demo digest'leri de eşit). Birleşik A/B: fail
  kümeleri birebir (v2 20/4078, demo 34/3502) → sıfır yeni hata.

---

*Bağlantılar: rapor §4-6 (madde detayları + öneriler), §8 (metre altyapısı),
§10 (doğrulanamayanlar); kılavuz `plans/2026-10-09-windows-smoke-dalga-bc-faz6-kilavuzu.md`
(A-0 talimatı); analiz `reports/telemetry/quadrix_full_windows/ANALIZ_2026-10-09.md`
(155 ms kümesi, ekran bazlı p95'ler).*
