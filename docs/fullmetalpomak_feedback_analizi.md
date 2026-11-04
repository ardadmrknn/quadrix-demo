# FullMetalPomak Geri Bildirim (Feedback) ve Kod Tabanı Analizi

> **Bu belgenin kaynağı `v2` deposudur.** `quadrix-demo`'ya kopyalanma nedeni: aşağıdaki **üç oynanış hatası demo kodunda da birebir mevcuttur.** Belgedeki `file:///` bağlantıları ve satır numaraları **v2** ağacına aittir; demo karşılıkları aşağıdaki tablodadır.
>
> ### Demo'da Doğrulanan Ortak Hatalar (2026-11-04)
>
> | Hata | v2 konumu | Demo konumu | Belge bölümü |
> | :--- | :--- | :--- | :--- |
> | I parçası kick tablosu (Guideline/SRS+ ile eşleşmiyor) | `src/pieces.py:69-95` | [`src/pieces.py:72-80`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/pieces.py#L72-L80) | #12 |
> | 21-Bag randomizer (`_bag_copies = 3`) | `src/game.py:1459` | [`src/game.py:1365`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/game.py#L1365) | #10 |
> | Satır temizleme donması (`block_fall_speed = 0.12`) | `src/game.py:1530` | [`src/game.py:1436`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/game.py#L1436), [`src/pvp_game.py:483`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/pvp_game.py#L483) | #7 |
>
> Ölçüm betikleri demo ağacında yoktur; ölçümler `v2/scratch/` altındadır ve demo kodunda aynı sonuçları verir (formüller ve tablolar özdeş).

`fullmetalpomak_1121577290262586` klasöründeki tüm mesaj kayıtları ([messages_extracted.csv](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/messages_extracted.csv), [message_1.html](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/message_1.html)), **4 fotoğraf**, **2 video**, devam sohbet ekran görüntüleri ([Screenshot_2026-11-04-14-51-08-313_com.instagram.android.jpg.jpeg](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/Screenshot_2026-11-04-14-51-08-313_com.instagram.android.jpg.jpeg) ve [Screenshot_2026-11-04-14-51-51-265_com.instagram.android.jpg.jpeg](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/Screenshot_2026-11-04-14-51-51-265_com.instagram.android.jpg.jpeg)) ile oyunun mevcut kod tabanı (`v2/src/`) uçtan uca incelenmiştir. Kod tabanında hiçbir değişiklik yapılmamıştır.

Aşağıda **FullMetalPomak** adlı kullanıcının (deneyimli bir Tetris oyuncusu/yayıncısı; **24" 1080p monitör** ve **8BitDo Xbox Arcade Stick [XInput / D-Pad modu]** ile testi gerçekleştirmiştir) verdiği tüm geri bildirimlerin dökümü (toplam **13 ana başlık**) ve kod tabanı referanslı teknik kök neden analizleri yer almaktadır.

> **Ek — 2026-11-04 Ampirlik Doğrulama Turu:** Bu belgedeki niteliksel tespitler (özellikle **#7 Satır Silme/Düşüş Senkronu** ve **#10 21-Bag**) gerçek `Game` nesnesi kurulup `update()` döngüsü simüle edilerek **ölçümle** doğrulanmıştır. Ayrıca belgede yer almayan **iki yeni konu** eklenmiştir: **#12 SRS/SRS+ rotasyon sistemi** (ayrı bir kullanıcı geri bildirimi: *"kick sistemi çalışmıyor"*) ve **#13 Speedrun/Pro oyuncu yeterlilik denetimi**. Ölçüm betikleri `v2/scratch/` altındadır (`srs_probe*.py`, `srs_diff.py`, `srs_realistic.py`, `srs_reversible.py`, `sweep_real*.py`, `sweep_resolution.py`, `sweep_settings.py`, `sweep_impact.py`, `sweep_timing.py`) ve `cd v2/scratch && python <betik>` ile çalışırlar. Kod tabanında **hiçbir değişiklik yapılmamıştır**.

---

# 1. Geri Bildirimlerin Özet Tablosu (#1 – #13)

| # | Kategori | Geri Bildirim (Feedback) Özeti | İlgili Medya / Mesaj | Kod Tabanındaki Ana Karşılığı | Öncelik |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Görsel Netlik (Clarity)** | T taşının rengi mor/neon arka plan ve ızgara ile karışıyor; hızlı oynarken taşın yeri ve **outline / ghost** seçilemiyor. | Mesaj #119–124 (12:17–12:18) | [`CLASSIC_THEME`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/themes.py#L19-L40), [`_SKINS`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/mode_skins.py#L94-L200), [`Game._draw_base_scene`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5926-L5973) | **Kritik (P0)** |
| **2** | **HUD & Ergonomi** | **Next Piece** çok küçük (periferik görüşte okunmuyor); **Hold** kutusu solda olmak yerine sağda 2 Next kutusunun altında durduğu için **"3. taşmış gibi"** algılanıyor; **HOLD** yazısında hizalama/kayma var. | Mesaj #88–114 (12:19–12:27) | [`compute_single_player_layout`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/gameplay_layout.py#L92-L272), [`Game._draw_right_hud_panel_core`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6102-L6359) | **Kritik (P0)** |
| **3** | **Özelleştirme & Ekonomi** | `BLOCK STYLES` ekranında sadece `Default`/`Custom` var, **3–5 adet hazır (premade) stil** olmalıydı; Mağaza ve Atölye içeriklerini denemek için başlangıçta **Lunar yetmiyor**. | Mesaj #67–76 (12:35–12:37), Fotoğraf [`28959238020385411`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/28959238020385411) | [`BlockStyleManager`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/block_styles.py#L121-L200), [`BLOCK_SKINS`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/block_skin_assets.py#L33-L67), [`StoreScreen`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/store_screen.py#L162-L200) | **Yüksek (P1)** |
| **4** | **Campaign & RNG / Denge** | Görev şartları ilk bakışta fark edilmiyor (blind oynarken kaçırılıyor); **Level 17**'de 17–18 hamlede 2 Quadrix istemesi boş/kapalı tahtada çok zor; taş gelişi standart 7-bag gibi hissettirmiyor (**21-bag RNG**); hamle sınırı yerine **süreli mod + açılışta PPS bazlı seviye tespit** önerisi. | Mesaj #28–42, #61–66 (12:38–12:53) | [`_LEVEL_OVERRIDES`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L539), [`get_level_shape`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L1281-L1286), [`req_for_objectives`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L216-L218), [`Game._refill_piece_bag`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2145-L2166) | **Kritik (P0)** |
| **5** | **Kontrolcü / Game Modes Bug'ı** | `GAME MODES` ekranında D-Pad ile `QUADRIX EXTRA`'dan aşağı (`Cascade`) inilmiyor; aşağı basınca **sağdaki scrollbar oynuyor ama seçim yukarıda takılı kalıyor**, fareye dokunmak zorunda bırakıyor. | Mesaj #49–59 (12:44–12:48), Video [`1188212720355106.mp4`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/videos/1188212720355106.mp4), Fotoğraf [`4130128133957162`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/4130128133957162), [`1499723578885740`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/1499723578885740) | [`ExtrasScreen.draw`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L554-L568), [`ExtrasScreen.handle_input`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L408-L435) | **Kritik Bug (P0)** |
| **6** | **Ana Menü UX & Navigasyon Bug'ı** | Oyunda çok fazla şey var ama oyuncuyu yönlendiremiyor (*"Ana mod ne, hedef ne?"*); Bento Grid kartlarının **asimetrik boyutları** yüzünden `Piece Workshop`'tan sağa basınca `Store` yerine aşağıdaki `Local Co-op`'a atlıyor. | Mesaj #14–27 (12:54–12:56), Fotoğraf [`4080059668792265`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/4080059668792265), Video [`1661597162339016.mp4`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/videos/1661597162339016.mp4) | [`Menu._find_spatial_neighbor`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py#L955-L1030), [`EMBEDDED_MENU_LAYOUT`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu_layout_embedded.py#L5-L6) | **Kritik Bug (P0)** |
| **7** | **Oynanış Akışı / Clear & Fall Senkronu** | Satır silme (`clear`) ve blokların aşağı iniş (`fall`) animasyonu hızlı oynarken akışı bozuyor: **"Bazı elementler donuyor, bazıları oynamaya devam ediyor."** Ya TGM gibi ARE (spawn gecikmesi) ile her şey dondurulmalı ya da TETR.IO gibi gecikmesiz akmalı. **Ölçüm (2026-11-04): 768–880 ms (720p), 4K'da 1568 ms; çözünürlüğe bağlı (1.8x fark); `particle_effects` ayarı etkisiz, yalnız `effects_enabled` kesiyor.** | Ek Görsel 1 (Üst–Orta) | [`Game._queue_line_clear_effects`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L3780-L3836), [`Game._start_block_fall_animation`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L3838-L3873), [`Game._automatic_gravity_paused`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280), [`Game.update`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5431-L5476) | **Kritik (P0)** |
| **8** | **Görsel Geri Bildirim / Kör Eden Bildirimler** | **"Puan bildirimleri kör edebiliyor."** Tahtanın tam ortasında/üstünde çıkan büyük `QUADRIX!` / `DOUBLE!` / `Combo` yazıları, milestone (1000, 2000...) havai fişek panelleri ve 150 parçacıklı patlamalar hızlı oynarken tahtayı kapatıyor. | Ek Görsel 1 (Üst) | [`Game._draw_base_scene_effects`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6541-L6723), [`Game.lock_and_new_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5049-L5106), [`Game.update`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5384-L5410) | **Kritik (P0)** |
| **9** | **Tahta Geometrisi & Spawn Yüksekliği (20×10 vs Buffer Zone)** | **"Şimdi fark ettim taşı yanlış yerde spawnlıyorsunuz... 20×10 görünüyor ama 22/23×10 oluyor tahtalar."** Tahta üstte dolu olduğunda (satır 18–20 doluyken) taş tahtanın dışında (buffer/vanish zone) doğmak yerine hemen görünür satırlara (`skip_hidden_rows`) indirildiği ve `row 0` kilitlenmesinde anında Game Over verildiği için üst satırlarda yüksek kule *comeback* (kurtarma) hamleleri yapılamıyor. | Ek Görsel 1 (Orta–Alt) | [`BOARD_HEIGHT`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/constants.py#L14), [`HIDDEN_SPAWN_ROWS`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L99), [`skip_hidden_rows`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L138-L154), [`Board.lock_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L143-L152), [`Game._draw_base_scene`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5987-L5988) | **Kritik (P0)** |
| **10** | **Torba (Randomizer) Mimarisi Detayı (21-Bag vs 7-Bag)** | 3'lü torba (`_bag_copies = 3`, 21 taş) kullanıldığında iki `I` çubuğu arasındaki maksimum kuraklık 12 taştan **36 taşa** çıkıyor; modern Guideline beklentisi varsayılan olarak **tekli torba (7-bag)** olması ve çoklu torbanın opsiyonel/sandbox ayarı olarak sunulması. **Doğrulama (2026-11-04):** `_bag_copies = 3` teyit edildi ([`game.py:1459`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1459)); torba dolum mantığı [`_refill_piece_bag`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2145-L2166) önce her tipten 3 kopya atıp karıştırıyor. | Ek Görsel 1 (En Alt) & Ek Görsel 2 (Üst) | [`Game._refill_piece_bag`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2145-L2166), [`Game._choose_piece_from_factories`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2168-L2215) | **Yüksek (P1)** |
| **11** | **Ses Tasarımı (TGM Tarzı Unique Spawn SFX & Announcer) + Mağaza Kozmetikleri (Lazer / Kamehameha Sweep & Arka Plan)** | TGM'deki gibi **her taşın kendine özgü bir spawn sesinin** olması (işitsel reaksiyon hızı için), satır temizlemelerde **sesli anons (announcer)** bulunması, Mağaza'ya **lazer/Kamehameha atan pet satır silme efektleri** ve **Cyber/Synth arka planlar** eklenmesi. | Ek Görsel 1 (Alt) & Ek Görsel 2 (Orta–Alt) | [`SoundManager.create_sounds`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sound.py#L268-L323), [`draw_rainbow_cat_sweep`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sweep_effects.py#L996-L1062), [`StoreScreen`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/store_screen.py#L162-L220) | **Orta / Özellik (P2)** |
| **12** | **Rotasyon Sistemi (SRS / SRS+)** ⚠️ *ayrı geri bildirim: "kick sistemi çalışmıyor"* | J/L/S/T/Z rotasyonları Guideline SRS ile **8/8 kusursuz**; ancak **I parçası 8 geçişin hiçbirinde** Guideline veya SRS+ ile eşleşmiyor. Gerçekçi tahtalarda I dönüşlerinin **%94.9'u farklı hücreye** oturuyor, tersine çevrilebilirlik **%43.1 ihlal**. 180° tablosunda `(0,0)` yok → boş tahtada bile kayma. Mevcut parity testi tautolojik olduğu için hatayı yakalamıyor. | 2026-11-04 araştırma turu (tetris.wiki, harddrop.com + ampirik ölçüm) | [`pieces.py:52-95`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L52-L95), [`Piece.try_rotate_srs`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L201-L258), [`test_tetrio_srs_plus_parity.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/tests/test_tetrio_srs_plus_parity.py) | **Kritik (P0)** |
| **13** | **Pro / Speedrun Yeterliliği** ⚠️ *ayrı araştırma* | Temel mekanik güçlü (SRS J/L/S/T/Z, T-spin, B2B, lock delay, DAS/ARR/SDF/DCD, Sprint/Ultra). Ancak speedrun için adil değil: **I tablosu** (#12), **satır temizleme donması 0.8–1.6 sn ve çözünürlüğe bağlı** (#7), **21-bag** (#10). Preview 3 parça; finesse/replay yok. | 2026-11-04 araştırma turu | [`game.py:5495-5530`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5495-L5530), [`board.py:252-280`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L252-L280), [`game.py:2010-2074`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2010-L2074) | **Yüksek (P1)** |

---

# 2. Detaylı Geri Bildirim Analizi ve Kod Tabanı İncelemesi

## Feedback #1: Görsel Netlik (Clarity) — T-Taşı / Mor Arka Plan Çakışması ve Ghost/Outline Görünürlüğü

### Kullanıcı İfadeleri
> - *"2 tane takıldığım şey oldu"*
> - *"Neon estetik çok iyi ama, arkaplan mor t taş da benzer renkte ya, hızlı oynucam dersem clarity sorun oluyor"*
> - *"Zor seçiyorum t nin nerede olduğunu"*
> - *"Görünmüyo outline"*

### Kod Tabanı Analizi ve Kök Neden
1. **T-Taşı Rengi ile Mod Arka Plan / Izgara Tonlarının Çakışması:**
   - [`CLASSIC_THEME`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/themes.py#L25-L37) içinde `T` parçası `(180, 88, 196)` (orta doygunlukta mor/eflatun), [`constants.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/constants.py#L45) içinde ise `PURPLE = (190, 80, 255)` olarak tanımlanmıştır.
   - Kullanıcının ilk oynadığı ana mod olan **Kart Ustalığı (`mystery`)** ve **Quadrix Extra (`tetris2`)** temalarında ([`mode_skins.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/mode_skins.py#L175-L200)):
     - `mystery`: `outer_tint=(80, 20, 80, 70)`, `board_tint=(30, 6, 40, 90)`, **`grid_color=(220, 160, 255)` (parlak mor ızgara)** ve `accent=NEON_MAGENTA`.
     - `tetris2`: `outer_tint=(60, 10, 80, 60)`, `board_tint=(50, 10, 70, 80)`, **`grid_color=(200, 150, 255)` (parlak mor ızgara)**.
   - Ayrıca varsayılan tahta arka plan görseli (`single_background`) [`settings_manager.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/settings_manager.py#L370) ve [`BackgroundManager`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/background.py#L64) içinde `bg_transparency = 0.3` (30% opaklık) ile çizilmektedir. Mor ağırlıklı arka plan görseli + mor `board_tint` + mor `grid_color` birleştiğinde `(180, 88, 196)` rengindeki `T` taşı arka planla neredeyse aynı renk uzayına düşmektedir.
   - [`ThemeManager.get_piece_color`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/themes.py#L63-L91) içindeki kontrast kontrolü yalnızca düz `bg_color = (10, 10, 15)` ile luminance farkına (`abs(lum_bg - lum_col) < 40`) baktığı için tahta üzerindeki gerçek arka plan görselini, `board_tint`'i ve `grid_color`'ı hesaba katmamaktadır.
2. **Ghost Piece ve Blok Outline (Kontur) Sorunu:**
   - [`Game._draw_base_scene`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5926-L5973) içinde ghost piece (gölge parça) çizilirken:
     ```python
     s = self._get_solid_alpha_surface((block_size, block_size), (*ghost_color, 50))
     self.screen.blit(s, (block_x, block_y))
     pygame.draw.rect(self.screen, ghost_color, (block_x, block_y, block_size, block_size), 2)
     ```
   - Gölge parçanın kenarlığı (`outline`) yalnızca taşın kendi rengiyle (`ghost_color`) 2px olarak çizilmekte, dışına veya içine yüksek görünürlüklü beyaz/açık renk bir kontrast konturu atılmamaktadır. Mor ızgara (`(220, 160, 255)`) üzerinde `(180, 88, 196)` rengindeki 2px çerçeve tamamen kaybolmaktadır (*"Görünmüyo outline"*).

---

## Feedback #2: HUD Ergonomisi — Next Piece Küçüklüğü, Hold Konumu ve "HOLD" Yazısı Kayması

### Kullanıcı İfadeleri
> - *"Bir de next piece Küçük"*
> - *"Kral idealinde bana kalırsa Vizyonumun odaksız kısmında Rengi gözümün ısırıp Ne taş gelceğini anlamam lazım Bakmaya gerek olmadan"*
> - *"Holdun solda, direkt sonraki next piecein sağda büyük olmasını"*
> - *"Hold garip yerde sizde / Sanki 3. Taşımmış gibi"*
> - (`burak_ysyn`: *"Anladim hocam zaten nedense sizde hold yazisi yanlış yerde durmus kayma olmuş"*)

### Kod Tabanı Analizi ve Kök Neden
1. **Next Piece Boyutunun Küçüklüğü ve Hiyerarşi Eksikliği:**
   - [`Game._draw_right_hud_panel_core`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6102-L6170) ve [`CampaignMode._draw_right_hud_panel`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/campaign_mode.py#L2444-L2508) içinde sonraki 2 parça (`for i in range(2)`) yan yana **birebir aynı küçük kutu boyutunda** çizilmektedir:
     - `target_box_size = max(44, min(int(round(96 * pixel_ratio)), int(66 * hud_scale)))` ([`game.py:6112`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6112))
     - Kutu içindeki taşların hücre boyutu `mini_cell = max(4, min(int(13 * hud_scale), piece_budget // max(1, pw), piece_budget // max(1, ph)))` ([`game.py:6140-6147`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6140-L6147)) ile sınırlandırılmıştır.
     - 1080p ekranda oyun tahtasındaki `cell_size` **~40–45px** iken, Next kutusundaki taşların hücre boyutu (`mini_cell`) yalnızca **~13–15px** (tahta bloğunun 1/3'ü kadar) kalmaktadır. Rekabetçi Tetris'te periferik görüşle (gözü tahtadan ayırmadan) okunabilmesi gereken **1. Next Piece**, 2. Next Piece ile aynı küçük boyutta olduğu için oyuncu sağ panele odaklanmak zorunda kalmaktadır.
2. **Hold Kutusunun Sağ Panelde Next'in Altında Durması ("3. Taş Gibi Algılanması"):**
   - Modern Guideline Tetris standartlarında (TETR.IO, Tetris Effect, Puyo Puyo Tetris) **Hold** kutusu tahtanın **sol üstünde**, **Next** kuyruğu ise tahtanın **sağ üstünde** yer alır.
   - Ancak [`compute_single_player_layout`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/gameplay_layout.py#L92-L272) ve [`Game._draw_right_hud_panel_core`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6172-L6359) içinde Hold kutusu için sol tarafta bir alan ayrılmamış; Hold kutusu sağ panelde **2 Next kutusunun hemen altına** (`content_x` hizasında, `box_size` yüksekliğinde) yerleştirilmiştir. Bu yerleşim yüzünden oyuncu sağ panele göz ucuyla baktığında Hold kutusunu **sıradaki 3. taş** sanmaktadır.
3. **"HOLD" Yazısının Kayması ve Çifte Rozet Çizimi:**
   - [`game.py:6105-6106`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6105-L6106)'da `NEXT` etiketi sola hizalı (`(content_x, curr_y)`) çizilirken, [`game.py:6230-6236`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6230-L6236)'da `hold_label` (içinde hem `HOLD` metni hem de aksiyon ikonu barındıran yüzey) `hold_label_center_x = content_x + (content_w // 2)` ile **tüm sağ panelin yatay ortasına** hizalanmış, `hold_label_vertical_nudge` ile aşağı kaydırılmış, sağ yanına `B: 5` (`hud_key_uses`, [`game.py:6240-6245`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6240-L6245)) yazılmış ve hemen altında sola hizalı duran `hold_box_rect`'in üst kenar ortasına ([`game.py:6268-6274`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6268-L6274)) ikinci kez `hold_key_badge` basılmıştır. Bu durum tekli Hold kutusu aktifken "HOLD" başlığının kutunun sağ-üst boşluğuna doğru kaymış görünmesine neden olmaktadır.

---

## Feedback #3: Blok Stilleri (Premade Styles), Özelleştirme UX Kopukluğu ve Lunar Ekonomisi

### Kullanıcı İfadeleri ve Görsel Kanıt
> - Fotoğraf [`28959238020385411`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/28959238020385411): `BLOCK STYLES` menüsünü çekip gönderiyor (her parça için yalnızca `Default` ve `Custom` butonları var).
> - *"Ayarlasaydınız ya 3-5 tane premade stil"*
> - *"Lunarım yetmedi mfmffkfk / Türk kedi olduğunu bilsem vidyoyu onla çekerdim :D"*

### Kod Tabanı Analizi ve Kök Neden
1. **Ayarlar -> `BLOCK STYLES` Ekranında Hazır (Premade) Palet/Stil Bulunmaması:**
   - [`settings_screen_tabbed.py:498-509`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/settings_screen_tabbed.py#L498-L509) altındaki `Block Styles` alt ekranı ([`block_styles.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/block_styles.py#L121-L200)), oyuncudan her bir parçayı (`I, O, T, S, Z, J, L`) tek tek elle renklendirmesini veya dışarıdan doku (PNG) yüklemesini beklemektedir.
   - Oyuncu `BLOCK STYLES` başlığına girdiğinde tek tıkla seçebileceği **3–5 adet hazır (premade) blok stili / renk paleti** (ör. *Yüksek Kontrast / Rekabetçi Guideline*, *Neon Cyberpunk*, *Retro Pixel*, *Cam/Kristal* vb.) bulamamaktadır.
2. **Mağazadaki Blok Görünümlerinin (`BLOCK_SKINS`) Azlığı ve Kopukluğu:**
   - [`block_skin_assets.py:33-67`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/block_skin_assets.py#L33-L67) içinde yalnızca 2 adet blok görünümü (`block_modern` ve 5400 Lunar fiyatlı `block_legacy_jelly`) bulunmaktadır ve bunlar `BLOCK STYLES` menüsünde değil, Mağaza (`StoreScreen`) altında ayrı bir yerde tutulmaktadır.
3. **Erken Oyunda (İlk 15–30 Dakika) Lunar Ekonomisi Bariyeri:**
   - [`store_screen.py:199`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/store_screen.py#L199) (`CATALOG_LINE_SWEEP_PRICE = 4200`), [`block_skin_assets.py:59`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/block_skin_assets.py#L59) (`price=5400`) ve [`pet_assets.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pet_assets.py) fiyatlandırmaları, yeni bir oyuncunun ilk oturumda mağazadan herhangi bir öğe (ör. Türk kedisi / Van kedisi pet'i veya blok görünümü) ya da Parça Atölyesi ([`piece_workshop.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/piece_workshop.py)) içeriği açmasına izin vermeyecek kadar yüksektir.

---

## Feedback #4: Campaign Görev Farkındalığı, Level 17 Matematiksel/RNG Darboğazı ve Dinamik Zorluk Önerisi

### Kullanıcı İfadeleri
> - (`burak_ysyn`: *"HOCAM ORDA GOREVLER VARDI / Gorevlerden dolayı gecemediniz ikili satır temizleme istiyordu"*)
> - *"Evet sonradan anladım fnffkfkf / Keşfediyorum / Blind kere blind"*
> - *"17de takıldım demin / 2 quadrix istiyor 17 hamlede / Burda ayrı bi algoritmanız var mı / Normal taş mantığı ile mi geliyor / Görece boş tahtada 17 18 taşla 2 quadrix kolay değil"*
> - *"Hamle sayısı yerine bana kalırsa süreli yapın :d Tertemiz olur. Oyunun açılış ekranına bi seviye tespit sınavı gibisinden bişeyler koyarsınız, easy normal hard insanlar belli eder zaten kendini / Pieces per second ölçerseniz"*

### Kod Tabanı Analizi ve Kök Neden
1. **Görev Farkındalığı (UX) Sorunu:**
   - [`CampaignMode.draw_mode_info`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/campaign_mode.py#L1694-L1960) içinde sol panelde hem **Görevler** (`self.objectives`, 14px font) hem de **Yıldız Koşulları** (`self.level_config.stars`, 13px font) aynı görsel ağırlıkta alt alta listelenmektedir. Seviye başlarken tahtanın ortasında büyük/kısa süreli bir **"Hedef: 2 Quadrix Yap"** açılış bildirimi (toast/banner) gösterilmediği için, doğrudan tahtaya odaklanan oyuncu görevi fark etmeden normal satır temizlemeleri yapıp hamle sınırını (`move_limit`) tüketmektedir.
2. **Level 17 ("Vadi 17") Zorluk Modeli ve Çöp Geometrisi Hatası:**
   - [`level_data.py:999-1000`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L999-L1000)'de Level 17 için görev tipi `tetris_count` seçilir ve [`difficulty_model.py:149-152`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L149-L152) üzerinden `T(17) = 0.185` ile hedef `1 + floor(7 * 0.185) = 2 Quadrix` (toplam 8 satır = **80 hücre**) olarak belirlenir.
   - **Formüldeki Hata ([`difficulty_model.py:216-218`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L216-L218)):**
     ```python
     elif obj_type == 'tetris':
         cell_req = math.ceil((REQ_TETRIS_CELLS * target - garbage_cells) / REQ_CELLS_PER_BLOCK)
         tip_reqs.append(float(max(REQ_BLOCKS_PER_TETRIS * target, cell_req)))
     ```
     Formül, başlangıçtaki tüm çöp hücrelerinin (`garbage_cells = 22`) Quadrix satırlarına doğrudan katkı sağladığını varsayarak `(80 - 22) / 4 = 15` taş (`req = 15`) hesaplamakta ve [`_LEVEL_OVERRIDES[17]`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L539) içinde `move_limit: 23` ve 2. yıldız için `_mv(18)` (**18 hamle**) vermektedir!
   - **Geometrik Gerçek ([`level_data.py:1281-1286`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L1281-L1286)):** Level 17'nin çöp deseni (`SHAPES[11]` — "Kare çerçeve") şöyledir:
     ```text
     Üst satır : XXXXX.XXXX  (Sadece 5. sütun boş)
     Orta satır: XX......XX  (Ortadaki 6 boş hücre üst satırın çatısı altında kapalı!)
     Alt satır : XXXX.XXXXX  (Sadece 4. sütun boş - üst satırla farklı hizada!)
     ```
     Orta satırın üstü kapalı olduğu ve alt/üst delikler farklı sütunlarda olduğu için **bu 3 çöp satırı Quadrix yapmakta kullanılamaz**. Oyuncu ya önce 5–6 taş harcayıp çöpün üstünü açmak (geriye 17–18 taş kalır!) ya da çöpün üstündeki boş tahtada sıfırdan 8 satır (80 hücre = **minimum 20 taş**) inşa etmek zorundadır. Boş tahtada 17–18 taşla (toplam 68–72 hücre) 80 hücrelik 2 Quadrix yapmak **matematiksel olarak imkânsızdır**; 23 taşla bile sıfır fire ve kusursuz taş sırası gerektirir.

---

## Feedback #5: Kontrolcü / Arcade Stick — `GAME MODES` Ekranında Aşağı İnmeme ve Scrollbar Bug'ı (Video 1)

### Kullanıcı İfadeleri ve Medya Kanıtı
> - Video [`1188212720355106.mp4`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/videos/1188212720355106.mp4): *"Bak şimdi, bug'a bak. Gördün mü? Bunlar arasında kıpırdayacağıma, şu sağ tarafta bar var ya, onu kıpırdatıyor. Bak, aşağı çekeceğim, şu Cascade moduna geçmem lazım, Cascade moduna geçmiyor, yukarıda kalıyor. Sol yapayım... İnemiyorum yani. Mouse'la müdahale etmem gerekiyor. Bu aşırı büyük problem, yani sallıyorum ben şöyle TV'nin karşısında oturacağım... kucağımda arcade stick'le, yok, yapamayacağım, mouse'a ihtiyacım olacak."*
> - Fotoğraflar [`4130128133957162`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/4130128133957162) & [`1499723578885740`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/1499723578885740): 8BitDo Xbox Arcade Stick'in `DP` (D-Pad) modunda ve düz XInput olduğunu gösteriyor.

### Kod Tabanı Analizi ve Kök Neden (%100 Kanıtlı Bug Tespiti)
Sohbette bu sorunun "Arcade Stick'e özel bir durum" olduğu düşünülmüş olsa da, **bu hata Arcade Stick'ten değil, doğrudan [`ExtrasScreen.draw`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L554-L568) içerisindeki koşulsuz fare taramasından (mouse hover polling) kaynaklanmaktadır:**

1. [`ExtrasScreen.handle_input`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L417-L420) içinde oyuncu `QUADRIX EXTRA` (`self.selected = 6`, 2. satır) üzerindeyken D-Pad ile **Aşağı (`K_DOWN`)** bastığında:
   - `self.selected += self.cols` çalışır ve `self.selected = 10` (`Cascade Mode`, 3. satır) olur.
   - Hemen ardından [`self._ensure_visible()`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L506-L527) çağrılır; 3. satır ekranın alt sınırına yakın olduğu için `self.scroll_offset` artırılır (**videoda sağdaki scrollbar'ın aşağı oynamasının sebebi budur!**).
2. Ancak hemen aynı karenin [`ExtrasScreen.draw()`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L554-L568) çağrısında şu kod çalışmaktadır:
   ```python
   # Her frame'de mouse pozisyonunu kontrol et (MOUSEMOTION event'i gelmese bile)
   mouse_pos = get_mouse_pos()
   for i, rect in enumerate(self.option_rects):
       if rect and rect.width > 0 and rect.collidepoint(mouse_pos):
           if self.selected != i:
               self.selected = i
           break
   ```
3. Videonun `00:01–00:25` saniyeleri dikkatle incelendiğinde, **kullanıcının sabit bıraktığı beyaz fare imlecinin tam olarak `QUADRIX EXTRA` kartının sol üst köşesinin üzerinde durduğu görülmektedir!**
4. [`Menu.handle_input`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py#L1316-L1317)'ta bulunan `if getattr(self, '_nav_source', 'mouse') != 'keyboard':` korumasının aksine, `ExtrasScreen.draw()` fare hiç hareket etmese bile **her karede (saniyede 60 kez)** sabit fare imlecinin altındaki kartı (`QUADRIX EXTRA`, `i = 6`) bulup `self.selected` değerini `10`'dan (`Cascade`) tekrar `6`'ya (`QUADRIX EXTRA`) geri yazmaktadır!
5. Ayrıca Fotoğraf [`4130128133957162`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/4130128133957162)'de görüldüğü üzere, [`settings_screen_tabbed.py:438-443`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/settings_screen_tabbed.py#L438-L443) içindeki *"Note: If your PlayStation (DualSense/DualShock) controller is not detected, please enable Steam Input or use DS4Windows."* bilgi satırı, XInput bir kontrolcü sorunsuz bağlıyken bile en üstte sabit gösterildiği için kullanıcıda "kontrolcüm algılanmadı mı?" algısı yaratmaktadır.

---

## Feedback #6: Ana Menü Tasarımı — Yönlendirme Eksikliği (Onboarding) ve Asimetrik Bento Grid Navigasyon Bug'ı (Video 2 & Fotoğraf)

### Kullanıcı İfadeleri ve Medya Kanıtı
> - *"Oyunda bi tık şey sıkıntısı var ya aslına bakarsan / Çok şey var ama oyun yönlendiremiyor / Ana mod ne / Hedef ne"*
> - Fotoğraf [`4080059668792265`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/photos/4080059668792265): *"Şu menüleri asimetrik yapma fikri kimin fnfmfk / Niye farklı boylardalar"*
> - Video [`1661597162339016.mp4`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/fullmetalpomak_1121577290262586/videos/1661597162339016.mp4): *"Bak, sol tıklıyom... Bak buradayken [Piece Workshop] sağ tıklayacağım. Görüyor musun Piece Workshop'tan yani Store'a geçmesi lazım gibi hissediyor ama aşağı [Local Co-op] geçiyor. Bunları acaba kabaca aynı boyda mı yapsanız?"*

### Kod Tabanı Analizi ve Kök Neden (%100 Matematiksel Kanıtlı Bug Tespiti)
1. **Bilgi Mimarisi ve Yönlendirme (Onboarding) Karmaşası:**
   - Ana menüde ([`menu.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py), [`EMBEDDED_MENU_LAYOUT`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu_layout_embedded.py#L5-L6)) aynı ekranda 10 farklı panel ve 7 köşe butonu yer almaktadır.
   - En büyük görsel ağırlık soldaki `Card Mastery` (`new_gen_tetris`: `w_pct=0.182, h_pct=0.439`) kartına verilmiş, `Campaign Mode` ortada daha dar bir karta (`w_pct=0.125, h_pct=0.283`) konmuş, `Classic` mod ise `Game Modes` (`extras`) alt ekranının içine gizlenmiştir. İlk kez giren bir oyuncu için "oyunun ana ilerleme yolu (core loop) hangisi?" sorusu belirsiz kalmaktadır.
2. **Asimetrik Bento Grid'de `Piece Workshop` -> Sağa Basınca `Store` Yerine `Local Co-op`'a Atlama Hatası:**
   - [`Menu._find_spatial_neighbor`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py#L955-L1030) fonksiyonu, seçili karttan basılan yöndeki en yakın kartı merkez koordinatlarına (`cx, cy` -> `rx, ry`) göre arar.
   - [`menu_layout_embedded.py:5`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu_layout_embedded.py#L5) içindeki 1920×1080 piksel karşılıklarına bakalım:
     - **`piece_workshop` (Parça Atölyesi):** `x_pct=0.339, y_pct=0.550, w_pct=0.126, h_pct=0.215` -> Merkez: **`(771, 710)`**
     - **`store` (Mağaza):** `x_pct=0.480, y_pct=0.524, w_pct=0.107, h_pct=0.242` -> Merkez: **`(1024, 696)`**
     - **`coop_mode` (Local / Online Co-op):** `x_pct=0.339, y_pct=0.789, w_pct=0.248, h_pct=0.112` -> Merkez: **`(889, 912)`**
   - Dikkat edilirse `coop_mode` kartı, hem `piece_workshop` hem de `store` sütunlarının altını boydan boya kaplayan geniş bir yatay kutu (`w_pct=0.248`) olduğu için yatay merkezi (`rx = 889`), `piece_workshop`'un yatay merkezinin (`cx = 771`) **118 piksel sağında** (`889 > 771`) kalmaktadır!
   - [`menu.py:1004-1025`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py#L1004-L1025) satırlarında:
     - `up` / `down` yönlerinde yatay örtüşme (`has_overlap = overlap_left < overlap_right`) kontrol edilirken,
     - **`left` / `right` yönlerinde dikey örtüşme (`overlap_top < overlap_bottom`) HİÇ KONTROL EDİLMEMEKTEDİR!** Sadece şu skor hesaplanmaktadır:
       ```python
       main_dist = abs(rx - cx)
       cross_dist = abs(ry - cy)
       score = main_dist + cross_dist * 0.5
       ```
   - `piece_workshop` `(771, 710)` üzerindeyken **SAĞ (`right`)** tuşuna basıldığında:
     - **`coop_mode` skoru:** `|889 - 771| + |912 - 710| * 0.5 = 118 + 101 = 219.0`
     - **`store` skoru:** `|1024 - 771| + |696 - 710| * 0.5 = 253 + 7 = 260.0`
   - `219.0 < 260.0` olduğu için algoritma, hemen sağdaki `Store` kartı yerine **aşağıdaki `coop_mode` (Local Co-op) kartını seçmektedir!**
   - Aynı hatanın tersi `Store` `(1024, 696)` üzerindeyken **SOL (`left`)** tuşuna basıldığında da yaşanmaktadır (`coop_mode` skoru `135 + 108 = 243.0 < piece_workshop` skoru `253 + 7 = 260.0`), yani `Store`'dan sola basınca da `Piece Workshop` yerine aşağıdaki `Online Co-op`'a düşmektedir (Video 2'nin ilk saniyelerinde görülen davranış).

---

## Feedback #7: Satır Silme (`Clear`) ve Düşüş (`Fall`) Animasyonlarındaki "Yarı-Donuk" (Hybrid) Durum Çelişkisi

### Kullanıcı İfadeleri (Ek Görsel 1)
> - *"Bi iki sıkıntı var / Clear animasyonuyla taşların aşağı inişinde / Sıkıntı çıkarıyor hızlı oynamaya çalışınca"*
> - *"Max potansiyelimde oynamaya çalıştım, next ve hold sıkıntı. Clear ve fall animasyonu problematik... Genel olarak gameplayin akışkanlığını bozmamak lazım."*
> - *"Quadrixte sıkıntı şey: Bazı elementler donuyor bazıları oynamaya devam ediyor"*
> - *"TGM illa duymuşsundur... Bak line clearlarda güzel animasyonları var. Ama her şey donuyor. Animasyonun keyfine varıyon."*
> - *"Ya böyle bi perspektifiniz olsun ya da tetrio gibi Allah yarattı demeden aksın oyun. Sizin petlerle metlerle tgm tarzı daha iyi olur. Animasyon bitene kadar oyunu dondurabilirsen, düşen taş dahil, animasyon da bi tıkçık daha hızlı olursa, çözülür senin iş."*
> - *"Spawnlamayadabilirsin animasyon bitmeden. Tgmde dikkat ettim, zaten clear taşın düşüşü ile ya, spawnlamıyor, yoketme animasyonu oynuyor, oyuncu da mikro nefes alıyor :D"*

### Kod Tabanı Analizi ve Kök Neden
Kullanıcının **"Bazı elementler donuyor, bazıları oynamaya devam ediyor"** tespiti, [`game.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py) içindeki mevcut satır silme mimarisini **birebir** tarif etmektedir:

1. **Mantıksal Tahta Anında Güncellenirken Görsel Tahtanın Geriden Gelmesi (Desync):**
   - [`Game.lock_and_new_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L4983-L5143) çağrıldığında:
     1. `self.board.lock_piece(...)` ([`board.py:141-241`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L141-L241)) içinde dolu satırlar **anında (`0 ms` gecikmeyle)** mantıksal matristen (`self.board.grid`, `self.board.occupancy`) silinir ve üstteki bloklar mantıksal olarak aşağı kaydırılır.
     2. Hemen aynı karede ([`game.py:5139-5142`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5139-L5142)) **yeni parça (`self.current_piece`) anında spawn edilir** ve oyuncu bu yeni parçayı sağa/sola hareket ettirebilir, döndürebilir ve **Hard Drop / Soft Drop** yapabilir!
     3. Ancak görsel tarafta [`_start_block_fall_animation`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L3838-L3873) üstteki bloklara negatif `current_offset = -drop_rows * cell_size` verir ve `sweep_trigger = 1.0` atar. Yani **Luna-Cat / Pet soldan sağa tüm tahtayı süpürüp bitirene kadar (`line_clear_sweep_progress < 1.0`) üstteki bloklar görsel olarak havada (eski yerlerinde) asılı bekler!**
     4. Sweep bittikten sonra bile (`sweep_progress >= 1.0`) bloklar `self.block_fall_speed = 0.12` ([`game.py:1530`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1530), [`game.py:5456`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5456)) hızıyla (60 FPS'te kare başına sadece `7.2 piksel`) yavaşça aşağı iner.
2. **Yarı-Donuk Gravity ve Ghost Piece Kayması:**
   - [`Game._automatic_gravity_paused`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280) fonksiyonu:
     ```python
     def _automatic_gravity_paused(self) -> bool:
         """Modlar gravity'yi durdurabilir; normal animasyonda soft drop çalışır."""
         return self._line_clear_animation_active() and not bool(
             getattr(self, '_soft_drop_held', False)
         )
     ```
     ile **yeni doğan parçanın otomatik düşüşünü (gravity) dondurmakta**, fakat oyuncunun yatay hareketine, döndürmesine ve hard drop yapmasına izin vermektedir.
   - Üstelik [`Game._get_ghost_visual_offset`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L4771-L4813) fonksiyonu, ghost piece'i mantıksal yerine çizmek yerine **havada asılı duran (henüz düşmemiş) blokların görsel offset'ine göre yukarı kaydırarak** çizmektedir!
   - **Sonuç:** Hızlı (2–3+ PPS) oynayan bir oyuncu satır sildiğinde; yeni taş tepede doğup donmuş gibi beklerken oyuncu taşı hareket ettiriyor, aşağıda kedi/pet koşuyor, silinen satırın üstündeki bloklar hâlâ havada duruyor, ghost piece havadaki blokların üstünde görünüyor ve oyuncu bu sırada Hard Drop'a basarsa taş görsel olarak henüz düşmemiş blokların **içinden geçip** gerçek (mantıksal) zemine çarpıyor!
   - Kullanıcının önerdiği iki temiz mimari seçenekten biri seçilmelidir:
     - **Seçenek A (TGM Tarzı Line Clear Delay / ARE):** Satır silindiğinde `line_clear_sweep` + `falling_block_animations` tamamlanana kadar yeni taş **hiç spawn edilmez** (`current_piece = None` beklenir) ve animasyon hızı biraz artırılır (~150–250 ms toplam süre). Böylece pet/lazer animasyonu net izlenir ve oyuncu mikro nefes alır.
     - **Seçenek B (TETR.IO / Rekabetçi Anlık Mod):** Ayarlardaki "Profesyonel / Hızlı Mod" açıldığında sweep beklemesi (`sweep_trigger`) kaldırılır, bloklar anında (`0 ms`) yerine oturur ve oyun hiç duraksamadan akar.

#### Ampirik Ölçüm Sonuçları (2026-11-04)

Yukarıdaki niteliksel analiz gerçek `Game` nesnesi + `update(16.0)` döngüsü ile **ölçülerek** doğrulanmıştır. Ölçüm betiği: `scratch/sweep_real4.py`.

**A) Satır temizleme (sweep) gerçek süreleri — 720p pencere, `cell_size=30`:**

| Temizleme türü | Ölçülen süre | Guideline ARE (~100 ms) |
| :--- | ---: | ---: |
| Single | **768 ms** | 7.7x |
| Double | **848 ms** | 8.5x |
| Triple | **880 ms** | 8.8x |
| Quadrix (4 satır) | **784 ms** | 7.8x |

**B) Kök neden birim hatası — süre piksele bağlı, zamana değil:**

[`game.py:5436-5440`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5436-L5440) ve [`sweep_effects.py:981-993`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sweep_effects.py#L981-L993):

```python
sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))   # PİKSEL
sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, level)
# -> duration = travel_px / (block_fall_speed * 3600) * max(0.42, 0.965**(level-1))
```

Süre, *"tahta kaç piksel geniş ve ışık oradan kaç piksel/saniye hızla geçiyor"* üzerinden hesaplanmaktadır. Oyun mantığına girmemesi gereken bir birimdir ve **çözünürlüğe bağımlılık** yaratır. Aynı bilgisayarda, aynı hamlede, yalnızca pencere büyütülerek yapılan **gerçek ölçüm** (`scratch/sweep_resolution.py`, 4 satır temizleme):

| Pencere | Ölçülen `cell_size` | Sweep süresi | vs Guideline |
| :--- | ---: | ---: | ---: |
| 720p | 30 px | **848 ms** | 8.5x |
| 1080p | 46 px | **1280 ms** | 12.8x |
| 1440p | 52 px | **1456 ms** | 14.6x |
| 4K | 56 px | **1568 ms** | 15.7x |

**Aynı oyun, aynı hareket, yalnızca pencere büyüdü → 720 ms daha fazla bekleme (1.8 kat).** Bu bir zorluk/denge tercihi değil, birim karışıklığıdır. Sonucu: *aynı oyuncu 720p'de 4K'dan belirgin şekilde daha hızlı süre üretir*; hiçbir leaderboard bunu telafi edemez.

**C) Gravity gerçekten duruyor mu? (fonksiyon yanıltıcı):**

`scratch/sweep_impact.py` ölçümü, 4 satır temizleme sonrası:

```
Sweep: 848 ms
Parça Y: 0 -> 0                        <-- hiç düşmedi
_automatic_gravity_paused() = False    <-- ama fonksiyon "durmadı" diyor
```

[`Game._automatic_gravity_paused`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280) yalnızca `_soft_drop_held` durumuna bakmaktadır; `update()` içindeki satır temizleme dalı ise gravity adımını **ayrıca** atlamaktadır. Docstring'deki *"normal animasyonda soft drop çalışır"* ifadesi **kodla çelişmektedir** (bkz. `CLAUDE.md` §3 Gerçeklik Hiyerarşisi: kod, yorumdan üstündür).

Ayrıca ölçülen davranışlar:
- **Yatay hareket:** ÇALIŞIYOR (parça konumlandırılabilir)
- **Rotasyon:** ÇALIŞIYOR
- **Otomatik düşüş:** DURUYOR (sweep boyunca parça havada asılı)
- **Hard drop:** Doğumda `hard_drop_lockout_timer = 100 ms` kilidi var; sonrasında çalışıyor

Yani hem **"yarı-donuk" durum** hem de **"tam dondurma yok"** aynı anda doğrudur — kullanıcının *"bazı elementler donuyor bazıları oynamaya devam ediyor"* tespiti ölçümle birebir örtüşmektedir.

**D) Efekt ayarları çözüm üretmiyor:**

1080p, 4 satır temizleme (`scratch/sweep_settings.py`):

| Ayar | Sweep süresi |
| :--- | ---: |
| `effects_enabled = True` | 1280 ms |
| `effects_enabled = False` | **0 ms** |
| Efekt açık + `particle_effects = high/medium/low/off` | **1280 ms (hiç fark etmiyor)** |

`particle_effects` ayarı bu donmayı hiç etkilememektedir; yalnızca ana `effects_enabled` anahtarı kesmektedir. Oyuncunun önündeki tercih: *ya tüm görsel kimliği kapat, ya yavaş oyna.*

**E) Sistemik yayılım — yalnızca Classic değil:**

`block_fall_speed = 0.12` beş yerde aynı değerle tanımlıdır ve aynı formül kullanılmaktadır:

- [`game.py:1530`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1530) — Classic / Sprint / Ultra / Zen
- [`pvp_game.py:507`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pvp_game.py#L507) — yerel PvP (iki oyuncu için ayrı hesap: satır 4546/4560)
- [`online_pvp_game.py:735`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/online_pvp_game.py#L735) — online PvP (satır 5193/5206)
- [`tutorial.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/tutorial.py) — eğitim

Donma **tüm modlarda** mevcuttur.

#### Önerilen Çözüm Sırası (Feedback #7 için)

| # | Çözüm | Dosya | Efor | Etki |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Sweep süresini **sabit ms**'ye çevir (`travel_px/px_per_sec` yerine doğrudan `SWEEP_DURATION_MS ≈ 180`) | `sweep_effects.py:973-993`, `game.py:5436-5440` | ~5 satır | Donma %85 azalır, çözünürlük bağımsızlaşır |
| 2 | Sprite çizimini süreden ayır: sweep görsel olarak sürsün, **oyun mantığı beklemesin** | `game.py:5431-5446` | Orta | En doğru mimari çözüm |
| 3 | Yarışma modlarında (Sprint, PvP) sweep'i anında bitir / hiç oynatma | `game_modes.py`, `pvp_game.py` | Küçük | Speedrun adaleti |
| 4 | "Speedrun/Pro Modu" ayarı: ARE = 0, efektler oyun mantığını etkilemez | `settings_manager.py` + `game.py` | Orta | Kalıcı çözüm |
| 5 | `_automatic_gravity_paused()` fonksiyonunu gerçek durumla hizala (yanıltıcı API) | `game.py:5276-5280` | 3 satır | Tutarlılık |

**Öneri:** #1 + #3 birlikte. #1 herkes için donmayı düzeltir, #3 speedrun'ı adil kılar (~30 satır toplam). Bu bölüm, yukarıdaki *Seçenek A / Seçenek B* ayrımıyla çelişmez; #1+#3 fiilen "her modda hızlı + yarışma modunda sıfır bekleme" karma stratejisidir.

---

## Feedback #8: Puan, Combo ve Milestone Bildirimlerinin Tahtayı Kapatması ("Puan Bildirimleri Kör Edebiliyor")

### Kullanıcı İfadeleri (Ek Görsel 1)
> - *"Puan bildirimleri kör edebiliyor. Genel olarak gameplayin akışkanlığını bozmamak lazım."*

### Kod Tabanı Analizi ve Kök Neden
1. **Tahtanın Tam Ortasında Çıkan `QUADRIX!` / `DOUBLE!` / `Combo` Yazıları:**
   - [`Game._draw_base_scene_effects`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6548-L6588) içinde `self.combo_message`:
     ```python
     msg_cx = board_x + shake_x + board_w // 2
     msg_cy = board_y + shake_y + board_h // 3
     ```
     koordinatlarına, yani **oyun tahtasının tam yatay ortasına ve üstten 1/3 yüksekliğine (yaklaşık 6.–7. satırların üzerine)** `self.font_large` ile `120 frame` (**2 tam saniye**, [`game.py:5082-5096`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5082-L5096)) boyunca opak (`alpha=255` -> fade) olarak çizilmektedir.
2. **Tahtanın Üst Kısmını Kapatan Milestone (1.000 / 2.000 / 4.000 Puan) Panelleri ve Havai Fişekler:**
   - [`Game.update`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5385-L5410) içinde çok sık aralıklarla (`1000, 2000, 4000, 8000, 10000, 15000...`) milestone tetiklenmekte, `self.create_multiple_fireworks()` ile ekran patlamalarla doldurulmakta ve [`Game._draw_base_scene_effects`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6644-L6681) içinde:
     ```python
     panel_center = (
         board_x + board_w // 2,
         board_y + int(round(cell_size * 4.0)),
     )
     ```
     ile **tahtanın 4. satırının tam ortasına** 1.5 saniye boyunca çerçeveli/glow'lu bir Glassmorphism paneli (`panel_rect`) yerleştirilmektedir!
3. **Merkezde 150 Parçacıklı Patlama (`create_particles`):**
   - [`Game.lock_and_new_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5050-L5077) içinde her Quadrix veya çoklu satır silmede ekranın/tahtanın tam ortasında `50 * lines_cleared` ila `150` adet parlak parçacık patlatılmaktadır.
   - Hızlı oynayan bir oyuncu üst satırlarda (satır 3–8 arası) kuleyi yönetirken tam o bölgenin üstüne binen `QUADRIX!` yazısı + `Milestone` kutusu + havai fişek/parçacık patlaması yüzünden taşları göremez hale gelmektedir (**"kör edebiliyor"**). Bu bildirimlerin tahtanın **içine** değil, tahtanın **sol/sağ dış kenar boşluğuna (HUD yanına)** taşınması kritik önemdedir.

---

## Feedback #9: Tahta Boyutu (20×10 vs 22/24×10 Buffer Zone), `skip_hidden_rows` ve Yüksek Kulede "Comeback" İmkânsızlığı

### Kullanıcı İfadeleri (Ek Görsel 1)
> - *"Şimdi farkettim taşı yanlış yerde spawnlıyonuz / 20x10 görünüyo genelde tetris oyunları / Ama 22/23x10 oluyo tahtalar"*
> - (`burak_ysyn`: *"Aslında tam taşın merkez noktasına göre tahtanın ortasında spamliyoruz / Bizim tetris alanı da 20x10"*)
> - *"Olmaz / Tam 20 mi gerçekten"*
> - *"Benim bazı vidyolarımda 'Oha o nasıl comeback' falan diyolar. Dur bak [TETR.IO klibi paylaşıyor] / Şu, Quadrixte mümkün değil / Çünkü taşın dibi 18de / Bak nerde spawn oluyor taşlar: Tahtanın 'dışında' / Çünkü 22/23x10 aslında / TGMde mesela taşı spawnlanmadan döndürme mekaniği var, döndürülmüş halde doğuyor, bi I taşı dik doğurduğunu düşün, 24x10 yani adamların boardları"*

### Kod Tabanı Analizi ve Kök Neden (%100 Teknik Doğrulama)
FullMetalPomak burada rekabetçi Guideline Tetris fiziğinin en temel kurallarından birine parmak basmıştır. Kod tabanında bunun neden çalışmadığını incelediğimizde **3 katmanlı bir kısıtlama** görüyoruz:

1. **`skip_hidden_rows` Fonksiyonu Taşı Gizli Satırlardan (Buffer Zone) Zorla İçeri İndiriyor:**
   - [`pieces.py:99-154`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L99-L154) içinde `HIDDEN_SPAWN_ROWS = 2` tanımlanmış ve `get_piece_spawn_y` taşı `y = -2` veya `y = -3`'te (görünür tahtanın 2 satır üstünde) doğurmaktadır.
   - **Ancak** taş doğar doğmaz [`game.py:5141`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5141)'de çağrılan [`skip_hidden_rows(piece, board)`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L138-L154):
     ```python
     while piece.y < 0 and board.is_valid_position(piece, dy=1):
         piece.y += 1
     ```
     döngüsüyle taşı `y < 0` (tahta üstü buffer alanı) bölgesinden **anında `y = 0` (görünür 19.–20. satırların içi) konumuna indirmektedir!**
2. **`y < 0` Bölgesindeki Hücreler Hiç Çizilmiyor (Görünmez Duvar) ve Kilitlenemiyor:**
   - [`Game._draw_base_scene`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5987-L5988) içinde aktif parça çizilirken:
     ```python
     if y < 0:
         continue
     ```
     denildiği için, tahta tepesine kadar yükseldiğinde (`row 1` veya `row 2` doluyken) `y < 0`'da kalan parça hücreleri oyuncuya **hiç gösterilmemektedir** (TETR.IO'da ise 20 satırlık çerçevenin üstü açıktır ve 21.–22. satırda doğan taş çerçevenin üstünde görünür).
   - Daha da önemlisi [`Board.__init__`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L22-L28) matrisi yalnızca `20` satırdır (`0..19`). `y < 0` için matriste satır yoktur!
3. **`Board.lock_piece` İçindeki Katı `row 0` ve `_overflow_top` Game-Over Kuralı:**
   - [`Board.lock_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L111-L152) satırlarında:
     ```python
     if y < 0:
         _overflow_top = True
         continue
     ...
     if _overflow_top or any(self._cell_filled(x, 0) for x in range(self.width)):
         self._last_lock_out = True
         if track_game_over:
             self._locked_out = True
     ```
   - Standart Guideline Tetris'te (ve TETR.IO'da) tahta `10×20` görünür satır + üstte **4–20 gizli/buffer satırdan (`10×24` veya `10×40` matris)** oluşur. Bir parça 19. veya 20. görünür satırda (`row 0`) kilitlendiğinde **oyun bitmez**; hatta parçanın yarısı 21.–22. satıra taşsa bile oyun devam eder (yalnızca yeni doğacak taş mevcut bloklarla çakışırsa — *Block Out* — veya parça tamamen 20 görünür satırın üstünde kilitlenirse — *Lock Out* — oyun biter).
   - Quadrix'te ise `row 0`'a (en üst görünür satıra) tek bir blok bile değdiğinde veya `y < 0`'a tek bir hücre taştığında (`_overflow_top`) **anında Game Over** verilmektedir! Bu yüzden FullMetalPomak'ın videosundaki gibi tahta 18.–19. satıra kadar doluyken üstte taş çevirip kuleyi eritmek (*top-out comeback*) Quadrix'te matematiksel olarak imkânsızdır.

---

## Feedback #10: Torba (Randomizer) İstatistiği — Neden 3'lü Torba (21-Bag) "Off" Hissettiriyor?

### Kullanıcı İfadeleri (Ek Görsel 1 En Alt & Ek Görsel 2 Üst)
> - *"Randomda ne kullanıyonuz taş jenere ederken? Gerçek random mu oyun?"*
> - *"Allah Allah bugün oynarken bi noktada sorguladım / Nedense off hissettirdi bir şey"*
> - *"Neden 7li torba değil btw / Baktın mı hiç tetrioda torba seçeneklerine? Tek torba şuan modern tetrisler. Bi torba jenere ediyor, hepsini kullanıyon, bi torba daha jenere ediyor. 2 I çubuk arasına max 12 taş girebiliyor en şanssız olasılıkta."*
> - *"Bu arada ben tek torba taraftarı değilim, ama genel beklenti o yönde. 'Default' ayarlar Guideline tetriste de öyle. 3lü torba belki 10 sene önce falandı."*
> - (`burak_ysyn`: *"1 default yaparım isteyen değiştirir"*) -> *"Olur aslında, senin oyunda bi sandbox havası yok değil"*

### Kod Tabanı Analizi ve Kök Neden
1. **İki `I` Taşı Arasındaki Maksimum Kuraklık (Drought) Hesabı:**
   - **Standart 7-Bag (`_bag_copies = 1`):** 1. torbanın ilk taşı `I` (`#1`), 2. torbanın son taşı `I` (`#14`) olursa, iki `I` taşı arasına en kötü ihtimalle **maksimum 12 taş** girebilir.
   - **Quadrix Mevcut 21-Bag ([`game.py:2159`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2159), `_bag_copies = 3`):** 1. torbanın ilk 3 taşı `I` (`#1, #2, #3`) olur ve 2. torbanın son 3 taşı `I` (`#40, #41, #42`) olursa, iki `I` taşı arasına **maksimum 36 taş (`18 + 18`)** girebilir!
2. **`_would_exceed_max_consecutive` Seçiminin Torba Sonunda Yığılma Yaratması:**
   - [`Game._choose_piece_from_factories`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2187-L2212) içinde `_max_consecutive_same_piece = 3` kontrolü vardır; ancak bir 21'lik torbanın son 3 taşı ile yeni açılan 21'lik torbanın ilk 3 taşı aynı tip denk geldiğinde (veya bir tip torba sonuna sıkıştığında) art arda 3 adet `S`/`Z`/`O` gelmesi ya da 25–30 taş boyunca `I` gelmemesi çok sık yaşanmaktadır.
   - **Çözüm:** [`game.py:2159`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2159)'da varsayılan `_bag_copies = 1` (**7-Bag**) yapılmalı ve Oynanış Ayarlarına (`gameplay_settings.py`) **Torba Boyutu: `7-Bag (Standart)` / `14-Bag` / `21-Bag` / `Tam Rastgele (Classic)`** seçeneği eklenmelidir.

---

## Feedback #11: İşitsel Geri Bildirim (TGM Tarzı Her Taşa Özel Spawn Sesi & Announcer) ve Mağaza Kozmetik Fikirleri (Lazer / Kamehameha Sweep & Arka Planlar)

### Kullanıcı İfadeleri (Ek Görsel 1 Alt & Ek Görsel 2 Orta–Alt)
> - *"TGM demişken, patentini alcak halleri yok fkfkfkf. O oyunda her taşın kendine unique bi spawn sesi var, insan beyni sese daha hızlı reaksiyon veriyor görüntüye kıyasla. Bi değerlendirirsiniz arkadaşınla."*
> - *"Clearlarda da announce konuşması/ses efekti olmalı. Hatta storeda satadabilirsin."*
> - *"Storea backgroundlar falan da eklemeyi düşünebilirsin / Synth cyber vibeı akar fjjffjfj"*
> - *"LAZER ekleyebilirsin clear animasyonuna / Iron man gibi ciuvvvv / Neon / Sıra yoketmece / Kamehameha"*
> - *"Pet işte: Chibi goku, Chibi telif yemeyecek iron man. Kedi koşuyo gökkuşağı takip ediyo ya; pet gelecek lazer atacak, aynı şey."*
> - *"Tamam işte basıcan peti, basıcan backgroundu, basıcan ses paketini."*
> - *"Evet önce gameplayi çöz, o ilk saydıklarım büyük sorun."*

### Kod Tabanı Analizi ve Mevcut Altyapı Karşılığı
1. **Her Taşa Özel Spawn Sesi (TGM Audio Cue Sistemi):**
   - Şu anda [`SoundManager.create_sounds`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sound.py#L268-L283) içinde yalnızca genel hareket/döndürme/kilitlenme sesleri (`move`, `rotate`, `drop`, `lock`, `hold`, `line`, `tetris`) sentezlenmektedir; **yeni taş kuyruktan çıkarken veya sıradaki taş (`next_piece_queue[0]`) belirlenirken taşa özgü (`I, O, T, S, Z, J, L`) hiçbir nota/ses çalınmamaktadır.**
   - `SoundManager.create_gameplay_sfx` ([`sound.py:324`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sound.py#L324)) zaten prosedürel synth katmanlarıyla (`sine`/`triangle` dalga sentezleyici) çalıştığı için, her taşın rengine/karakterine özel 7 farklı kısa nota (`spawn_I`, `spawn_T`, `spawn_O` vb. — TGM'de olduğu gibi *sıradaki taş* için 40–60 ms'lik karakteristik melodik tınılar) hiçbir harici ses dosyasına ihtiyaç duymadan doğrudan `sound.py` içinde üretilebilir ve Ayarlar'da açılıp kapatılabilir.
2. **Satır Silme Sesli Anonsları (Clear Announcer) ve Ses Paketleri:**
   - [`Game.lock_and_new_piece`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5039-L5106) içinde 1, 2 ve 3 satır silmelerin tamamında aynı tekdüze `self.sound.play('line')` sesi çalınmakta, yalnızca 4 satırda `self.sound.play('tetris')` çalmaktadır (`DOUBLE`, `TRIPLE`, `QUADRIX`, `B2B`, `COMBO` için ayrı ses/vokal anonsu yoktur).
3. **Lazer / Kamehameha Atan Pet Satır Silme Efektleri (`sweep_effects.py`):**
   - Mevcut [`draw_rainbow_cat_sweep`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/sweep_effects.py#L996-L1062) mimarisi zaten `pet` (sağda/önde giden karakter) + `band_surface` (soldan uzayan `trail` şeridi) yapısıyla çalışmaktadır!
   - Bu mimariye çok küçük bir eklemeyle **"Sabit Duran ve Lazer Ateşleyen Pet"** (`mode='beam'`): Pet tahtanın sol kenarında (`board_rect.x`) sabit durup elini/ağzını uzatırken, `trail_width` soldan sağa doğru parlak çekirdekli bir **Neon Lazer / Plazma Işını (`ciuvvv` ses efektiyle)** olarak uzayabilir.
4. **Mağaza (`StoreScreen`) Arka Plan ve Ses Paketi Kategorisi:**
   - [`StoreScreen`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/store_screen.py#L162-L220) şu anda `line_sweep` (bayraklar/izler), `pets` ve `block_skins` sekmelerine sahiptir; buraya `backgrounds` (Synthwave / Cyberpunk arka planlar) ve `voice_packs` (Announcer / TGM ses paketleri) sekmeleri doğrudan entegre edilebilir.

---

## Feedback #12: Rotasyon Sistemi — SRS / SRS+ Uyumu ve "Kick Sistemi Çalışmıyor" Geri Bildirimi

> **Kaynak notu:** Bu başlık FullMetalPomak sohbetinden **değil**, ana oyun hakkında ayrıca gelen bir geri bildirimden (*"kick sistemi çalışmıyor"*) doğmuştur. 2026-11-04 tarihli araştırmada SRS/SRS+ tanımları resmî kaynaklardan (tetris.wiki `SRS`, harddrop.com `SRS`, tetris.wiki `TETR.IO`) doğrulanmış, ardından kod tabanı ampirik olarak test edilmiştir.

### Kavram Özeti

- **SRS (Super Rotation System):** Tetris Guideline'ın zorunlu rotasyon standardı (2001, Tetris Worlds). Döndürme engellenirse **5 pozisyon sırayla** denenir (temel rotasyon + 4 wall-kick). J/L/S/T/Z aynı tabloyu paylaşır, **I ayrı tablo** kullanır, **O hiç kick yapmaz**. Guideline'ın sert kuralı: *"tüm rotasyonlar tersine çevrilebilir olmalı"* (T-Spin Triple'lar bu yüzden var olabilir).
- **SRS+:** TETR.IO'nun (Alpha 5.0.0) türevi. J/L/S/T/Z tablosu Guideline ile **birebir aynıdır**; farkı **yalnızca I parçasındadır** — I kick'leri y-eksenine göre simetrikleştirilmiştir (sağ taraf aynalanır).

### Kod Tabanı Mevcut Durumu

Rotasyon altyapısı mevcuttur ve temiz bağlanmıştır:

- [`pieces.py:52-95`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L52-L95) — `SRS_KICKS_NORMAL`, `SRS_KICKS_I`, `SRS_KICKS_180_NORMAL`, `SRS_KICKS_180_I` tabloları
- [`Piece.try_rotate_srs`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L201-L258) ve [`Piece.try_rotate_180`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L260-L310)
- Çağrı yolları: `game.py` (CW/CCW/180), `coop_game.py`, `pvp_game.py`, `online_pvp_game.py`, `game_modes.py`, `tutorial.py` — **12 çağrı noktası**
- SRS'i atlayan çıplak `.rotate()` kullanımı tespit edilmemiştir.

### Ölçülen Sonuçlar (`scratch/srs_probe2.py`, `srs_probe5.py`, `srs_diff.py`)

| Parça | Guideline SRS uyumu | SRS+ uyumu |
| :--- | :--- | :--- |
| **J, L, S, T, Z** | **8/8 geçiş birebir** | 8/8 (aynı tablo) |
| **O** | Kick yok — doğru | Doğru |
| **I** | **0/8** | **0/8** |

**Kritik bulgu:** I parçası tablosu hiçbir standarda uymamaktadır. TTC'nin resmî offset verisinden türetilen referansla karşılaştırıldığında 8 geçişin **hiçbiri** tam eşleşmemekte, yalnızca 3'ü küme olarak tutmakta ve o 3'ünde bile **sıra** yanlıştır:

```
(0→1)  Quadrix : [(1,0), (2,0), (-1,0), (-1,1), (2,-2)]
       Guideline: [(1,0), (-1,0), (2,0), (-1,1), (2,-2)]   <- yalnız sıra farklı
(1→0)  Quadrix : [(-1,0), (-2,0), (1,0), (-2,-2), (1,1)]
       Guideline: [(-1,0), (1,0), (-2,0), (1,-1), (-2,2)]   <- küme farklı (dy işareti ters)
```

Ayrıca **180° tablolarında `(0,0)` yoktur** ([`pieces.py:90-95`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L90-L95)); bu nedenle boş tahtada bile I parçası 180° dönüşte kaymaktadır.

**Gerçek oynanış etkisi** (`scratch/srs_realistic.py`, 20.000 senaryo, zemin+duvar içeren tahtalar):

| Sonuç | Oran |
| :--- | ---: |
| Guideline ile hücre hücre aynı | **%1.8** |
| İkisi de başarılı ama **farklı hücreye oturuyor** | **%94.9** |
| Quadrix başarılı, Guideline başarısız (imkânsız yer) | %0.2 |
| Quadrix başarısız, Guideline başarılı (spin kaçırma) | %3.1 |

**Tersine çevrilebilirlik** (`scratch/srs_reversible.py`) — Guideline'ın zorunlu kuralı; CW→CCW sonrası başlangıç konumuna dönmeme oranı:

| Parça | Quadrix | Guideline referansı |
| :--- | ---: | ---: |
| **I** | **%43.1** | %23.0 |
| T / J / L / S / Z | %6.8 / %8.0 / %7.9 / %7.5 / %7.9 | **aynı değerler** (Guideline'ın kendi davranışı) |

I dışındaki tüm parçalar referansla **%100 örtüşmektedir** — yani sorun izole olarak I tablosundadır.

### Test Neden Bunu Yakalamıyor?

[`tests/test_tetrio_srs_plus_parity.py:48-55`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/tests/test_tetrio_srs_plus_parity.py#L48-L55) tabloyu **kendi kopyasıyla** karşılaştırmaktadır:

```python
assert SRS_KICKS_I == EXPECTED_I   # EXPECTED_I = aynı yanlış tablo
```

Test kodu resmî kaynakla değil kendi kopyasıyla doğruladığı için **tautolojidir**; hatayı yakalayamaz. Mevcut durumda 2 test "passed" görünmektedir.

### "Kick Sistemi Çalışmıyor" Geri Bildiriminin İki Olası Anlamı

1. **Rotasyon wall-kick'i:** J/L/S/T/Z için kusursuz. **I için bozuk** — oyuncu I-spin/tuck planlayıp beklediği yere oturmayınca "kick çalışmıyor" hissi doğar (ölçülen %94.9 konum farkı + %43 tersine dönmeme tam bu senaryodur).
2. **Garbage ("çöp") gönderme:** [`online_pvp_game.py:119`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/online_pvp_game.py#L119) içinde `ONLINE_PVP_GARBAGE_ENABLED = False` — PvP'de satır temizlemek rakibe **hiçbir şey göndermiyor**. Atak tablosu (`1:0, 2:1, 3:2, 4:4`) doğru yazılmış ama flag kapalı olduğu için ölü koddur (sayaç göstergesi ve counter-attack iptali de devre dışı).

**Aksiyon:** Geri bildirimin hangi anlamda söylendiği teyit edilmelidir. Olası işler: (a) `pieces.py` I tablosunu Guideline veya SRS+ ile değiştirmek, (b) `_choose_piece_from_factories`/garbage flag'ini gözden geçirmek.

### Önerilen Düzeltme Sırası (Feedback #12)

| # | İş | Dosya | Etki |
| :--- | :--- | :--- | :--- |
| 1 | I kick tablosunu Guideline (veya SRS+) ile değiştir; 180° I tablosunu düzelt | `pieces.py:69-95` | "Kick çalışmıyor" şikayetinin ana nedeni |
| 2 | Parity testini **resmî tablolara** karşı yaz (tautolojiyi kaldır) + diferansiyel testi kalıcı test olarak ekle | `tests/test_tetrio_srs_plus_parity.py` | Regresyonu kilitler |
| 3 | I parçası için tersine çevrilebilirlik testi ekle | `tests/` | Guideline zorunlu kuralı |
| 4 | `ONLINE_PVP_GARBAGE_ENABLED` kararını netleştir (aç / dokümante et) | `online_pvp_game.py:119` | "Kick" ikinci anlamı |

---

## Feedback #13: Pro / Speedrun Oyuncusu İçin Yeterlilik Denetimi

> **Kaynak notu:** FullMetalPomak sohbeti dışında, "oyunu pro Tetris olarak oynayan / speedrun yapan kişiler için temel ne kadar yeterli?" sorusu üzerine yapılan 2026-11-04 denetimi.

### Yeterli Olan Temel

- **SRS (J/L/S/T/Z):** 8/8 birebir — en sık kullanılan rotasyonlar standarda uygun.
- **T-spin algılama:** 3-köşe yöntemi + ön-köşe mini ayrımı ([`game.py:2010-2074`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2010-L2074)).
- **B2B / Combo:** 1.5x B2B + combo bonusu ([`board.py:252-280`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L252-L280)).
- **Lock delay:** 500 ms + 15 reset + 3 sn stall limiti — Guideline ile uyumlu ([`game.py:5495-5530`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5495-L5530)).
- **Handling:** DAS 167 ms / ARR 33 ms varsayılan (Guideline önerisiyle aynı), ARR=0 = anında ışınlanma destekleniyor; SDF ve DCD (DAS Cut Delay) ayarları mevcut.
- **Modlar:** Sprint (40 satır), Ultra, Zen mevcut; Sprint hedefi `target_lines = 40` ([`game_modes.py:55`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes.py#L55)).

### Speedrun'ı Doğrudan Baltalayan Üç Sorun

1. **Satır temizleme animasyonunun gravity'yi dondurması** — ayrıntı ve ölçümler **Feedback #7** altında. Özet: 768–1568 ms, çözünürlüğe bağlı, Guideline'ın 7.7–15.7 katı.
2. **21-Bag randomizer** (`_bag_copies = 3`) — ayrıntı **Feedback #10** altında. 7-bag değil; parça akışı öngörülemez.
3. **I parçası kick tablosu** — ayrıntı **Feedback #12** altında. I-spin ağırlıklı hatlar ve finesse optimizasyonları güvenilmez.

**Leaderboard açısından en kritik sonuç:** Satır temizleme süresi pencere boyutuna bağlı olduğundan, *aynı oyuncu 720p'de 4K'dan belirgin şekilde daha hızlı süre üretir.* Hiçbir skor tablosu bunu telafi edemez.

### Eksik / Sınırlı Olanlar (blocker değil)

| Konu | Quadrix | Guideline / TETR.IO | Not |
| :--- | :--- | :--- | :--- |
| Preview sayısı | 3 parça ([`game.py:1469`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1469)) | 5 (TETR.IO varsayılan) | Planlama derinliği düşük |
| IRS / IHS | Yok | İsteğe bağlı | **Bu oyunda gerçek eksik değil** — aşağıya bakınız |
| Finesse sayacı | Yok | TETR.IO Pro Mode'da var | Antrenman aracı |
| Replay / ghost | Yok | TETR.IO'da var | Analiz aracı |
| 20G modu | Yok | Bazı oyunlarda var | Ek zorluk |

**IRS/IHS hakkında düzeltme:** *Initial Rotation System* (yeni parça gelirken rotasyon tuşunu basılı tutup doğmazdan önce döndürme) ve *Initial Hold System* (aynı şekilde hold) yalnızca **ARE beklemesi olan** oyunlarda anlamlıdır. Quadrix'te yeni parça kilitlenmeyle **aynı karede** aktif olmaktadır ([`game.py:5139-5142`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5139-L5142)) — yani oyuncu zaten parça ekrandayken döndürüp hold yapabilmektedir. Bu bir eksiklik değil, farklı (ve geçerli) bir tasarım kararıdır.

### Hüküm

Pro bir oyuncu oyunu oynayabilir ve eğlenebilir; çekirdek mekanik temeli sağlamdır. Ancak **mevcut haliyle speedrun / leaderboard için adil değildir**: (a) I parçası standart dışı davrandığı için karşılaştırma geçersiz, (b) satır temizleme animasyonu süreleri sistematik olarak şişiriyor ve çözünürlüğe göre değiştiriyor, (c) 21-bag öngörülemezlik katıyor. Üçü de düzeltilebilir; hiçbiri mimari yeniden yazım gerektirmez.

---

# 3. Özet Eylem Planı ve Öncelik Sırası ("Önce Gameplay'i Çöz")

FullMetalPomak sohbetin sonunda öncelik sırasını çok net özetlemiştir:
> *"Evet önce gameplayi çöz. O ilk saydıklarım büyük sorun."*

Bu doğrultuda tüm sohbetin (**toplam 11 madde**) kesin mimari yol haritası şöyledir:

> **Not:** Aşağıdaki liste FullMetalPomak sohbetinin orijinal 11 maddesini kapsar. 2026-11-04 turunda eklenen **#12 (SRS/kick)** ve **#13 (Speedrun denetimi)** maddelerine ait iş kalemleri kendi bölümlerinin sonundaki "Önerilen Düzeltme Sırası" tablolarında verilmiştir; P0 öncelikli olanlar #12 → 1 ve #7 → 1/3'tür.

1. **Oynanış Çekirdeği & Fizik (P0):**
   - **Satır Silme (`Clear`) & Blok Düşüş (`Fall`) Senkronu ([`game.py:3838-3873`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L3838-L3873), [`game.py:5139-5143`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5139-L5143), [`game.py:5276-5280`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280)):** Yarı-donuk (hybrid) durum giderilmeli; normal modda TGM tarzı tam ARE dondurması (sweep + fall bitene kadar yeni taşın spawn olmaması ve animasyonun hızlandırılması), "Profesyonel Mod" açıldığında ise TETR.IO tarzı `0 ms` anlık düşüş uygulanmalıdır.
   - **Tahta Üstü Buffer Zone (`22/24×10`) ve Spawn/Lock-Out Kuralları ([`board.py:22-28`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L22-L28), [`board.py:143-152`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L143-L152), [`pieces.py:138-154`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L138-L154), [`game.py:5987`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5987)):** Tahtanın üstünde 4 satırlık gerçek bir buffer/vanish zone tanımlanmalı, `row 0`'da kilitlenince anında ölüm kuralı Guideline standardına (Block-Out / tam Lock-Out) çekilmeli ve üst satırlarda yüksek kule kurtarma (*comeback*) hamlelerine izin verilmelidir.
   - **Standart 7-Bag (`_bag_copies = 1`) Varsayılanı ([`game.py:2159`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2159)):** Varsayılan torba boyutu `1` (7-bag) yapılmalı, `3` (21-bag) ise Ayarlar altında opsiyonel bir sandbox seçeneği olarak sunulmalıdır.
   - **Campaign Level 17 Dengelemesi ([`difficulty_model.py:216-218`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L216-L218), [`level_data.py:539`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L539)):** `tetris` görevlerinde kapalı çöp hücreleri `REQ_TETRIS_CELLS` hesabından düşülmemeli ve görev başlangıcında tahta ortasında kısa bir hedef bildirimi gösterilmelidir.
2. **Görsel Netlik, Bildirimler ve HUD Ergonomisi (P0):**
   - **Görsel Kontrast & Ghost Outline ([`game.py:5926-5973`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5926-L5973), [`themes.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/themes.py), [`mode_skins.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/mode_skins.py)):** Ghost piece çerçevesine 1px beyaz/parlak iç kontur eklenmeli, `mystery` / `tetris2` modlarındaki mor `grid_color` doygunluğu düşürülmelidir.
   - **Kör Eden Bildirimlerin Tahta Dışına Alınması ([`game.py:6548-6723`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6548-L6723)):** `QUADRIX!`, `DOUBLE!`, `Combo` ve `Milestone` kutuları oyun tahtasının ortasından kaldırılıp tahtanın sol/sağ dış kenarına taşınmalıdır.
   - **HUD Yerleşimi ve Next/Hold Ayrımı ([`gameplay_layout.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/gameplay_layout.py), [`game.py:6102-6359`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6102-L6359)):** Hold kutusu tahtanın sol üstüne taşınmalı, **1. Next Piece** kutusu ve `mini_cell` boyutu periferik görüşte anında seçilecek şekilde büyütülmelidir.
3. **Kontrolcü / Menü Navigasyon Bug'ları (P0):**
   - **`ExtrasScreen` Gamepad/Stick Kilitlenmesi Fix'i ([`extras_menu.py:554-568`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/extras_menu.py#L554-L568)):** `draw()` içindeki her-kare `get_mouse_pos()` taraması kaldırılmalı veya `_nav_source` bayrağına bağlanarak yalnızca gerçek `MOUSEMOTION` olduğunda çalışmalıdır.
   - **Ana Menü `_find_spatial_neighbor` Fix'i ([`menu.py:1004-1008`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/menu.py#L1004-L1008)):** `left`/`right` yönlerinde de tıpkı `up`/`down` yönlerinde olduğu gibi dikey projeksiyon örtüşmesi (`overlap_top < overlap_bottom`) önceliklendirilmelidir.
4. **İçerik, Ses ve Mağaza Genişletmeleri (P1–P2):**
   - `BLOCK STYLES` menüsüne 3–5 adet ücretsiz hazır (premade) renk/kontrast paleti eklenmesi.
   - `sound.py` içine TGM tarzı her taşa özgü (`I, O, T, S, Z, J, L`) spawn nota ipuçları ve satır silme sesli anonslarının (Announcer) eklenmesi.
   - Mağazaya (`StoreScreen`) Lazer/Kamehameha satır silme efektleri (`sweep_effects.py`) ve Synth/Cyber arka planların eklenmesi.

5. **Rotasyon Sistemi Düzeltmesi (P0 — 2026-11-04 turu, bkz. Feedback #12):**
   - **I parçası kick tablosunu düzelt ([`pieces.py:69-95`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L69-L95)):** Guideline SRS veya SRS+ tablosuyla değiştir; 180° I tablosuna `(0,0)` ekle. J/L/S/T/Z'ye **dokunma** — 8/8 birebir doğru.
   - **Parity testini gerçek kaynakla değiştir ([`test_tetrio_srs_plus_parity.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/tests/test_tetrio_srs_plus_parity.py)):** Kendi tablosuna karşı `assert` eden tautoloji kaldırılmalı; resmî tablolara karşı diferansiyel test + tersine çevrilebilirlik testi eklenmeli.
   - **`ONLINE_PVP_GARBAGE_ENABLED` kararı ([`online_pvp_game.py:119`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/online_pvp_game.py#L119)):** Şu anda `False`; PvP'de satır temizlemek rakibe hiçbir şey göndermiyor. Açılacaksa atak tablosu hazır (`1:0, 2:1, 3:2, 4:4`); bilinçli kapalıysa dokümante edilmeli.

6. **Speedrun / Rekabetçi Mod (P1 — 2026-11-04 turu, bkz. Feedback #13):**
   - Satır temizleme süresini **sabit ms**'ye çevir (piksel yerine zaman) — çözünürlük bağımlılığını kaldırır.
   - Sprint ve PvP'de sweep beklemesini sıfırla (TETR.IO 40 LINES davranışı).
   - Preview sayısını 3 → 5'e çıkarma ve opsiyonel finesse sayacı değerlendirilebilir.
