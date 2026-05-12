# Steam Başarımlar ve İstatistikler — Kurulum Rehberi

Bu belge, Quadrix oyununun Steam başarımlarını ve istatistiklerini
Steamworks Partner sitesinde yapılandırmak için gerekli bilgileri içerir.

**Steamworks Partner Console:** https://partner.steamgames.com/apps/achievements/4428040

---

## Başarım Listesi (Achievements)

Aşağıdaki başarımları Steamworks konsolunda tanımlayın.
Her başarım için 64×64 px simge (açık) ve gri simge (kilitli) gereklidir.

| #   | API Name                    | Görünen Ad (TR)   | Açıklama (TR)                                            | Gizli? |
| --- | --------------------------- | ----------------- | -------------------------------------------------------- | ------ |
| 1   | `ACH_FIRST_GAME`            | İlk Adım          | İlk oyununu tamamla                                      | Hayır  |
| 2   | `ACH_FIRST_LINE`            | İlk Satır         | İlk satırını temizle                                     | Hayır  |
| 3   | `ACH_FIRST_TETRIS`          | İlk Quadrix       | İlk 4 satırlık Quadrix'ini yap                           | Hayır  |
| 4   | `ACH_SCORE_1K`              | Başlangıç         | Bir oyunda 1,000 puana ulaş                              | Hayır  |
| 5   | `ACH_SCORE_10K`             | Deneyimli         | Bir oyunda 10,000 puana ulaş                             | Hayır  |
| 6   | `ACH_SCORE_50K`             | Usta              | Bir oyunda 50,000 puana ulaş                             | Hayır  |
| 7   | `ACH_SCORE_100K`            | Efsane            | Bir oyunda 100,000 puana ulaş                            | Evet   |
| 8   | `ACH_LINES_10`              | Temizlikçi        | Bir oyunda 10 satır temizle                              | Hayır  |
| 9   | `ACH_LINES_50`              | Süpürge           | Bir oyunda 50 satır temizle                              | Hayır  |
| 10  | `ACH_LINES_100`             | Temizlik Robotu   | Bir oyunda 100 satır temizle                             | Hayır  |
| 11  | `ACH_LINES_200`             | Temizlik Makinesi | Bir oyunda 200 satır temizle                             | Evet   |
| 12  | `ACH_TETRIS_5`              | Quadrix Ustası    | 5 Quadrix yap                                            | Hayır  |
| 13  | `ACH_TETRIS_10`             | Quadrix Tanrısı   | 10 Quadrix yap                                           | Hayır  |
| 14  | `ACH_LEVEL_5`               | Hızlanıyor        | Bir oyunda seviye 5'e ulaş                               | Hayır  |
| 15  | `ACH_LEVEL_10`              | Hız Canavarı      | Bir oyunda seviye 10'a ulaş                              | Hayır  |
| 16  | `ACH_LEVEL_15`              | Süpersonik        | Bir oyunda seviye 15'e ulaş                              | Hayır  |
| 17  | `ACH_LEVEL_20`              | Işık Hızı         | Bir oyunda seviye 20'ye ulaş                             | Evet   |
| 18  | `ACH_GAMES_10`              | Sadık Oyuncu      | 10 oyun oyna                                             | Hayır  |
| 19  | `ACH_GAMES_50`              | Müdavim           | 50 oyun oyna                                             | Hayır  |
| 20  | `ACH_GAMES_100`             | Profesyonel       | 100 oyun oyna                                            | Hayır  |
| 21  | `ACH_COMBO_5`               | Kombo Ustası      | Bir oyunda 5x kombo yap                                  | Hayır  |
| 22  | `ACH_PVP_FIRST_WIN`         | İlk Zafer         | Online PvP'de ilk galibiyetini al                        | Hayır  |
| 23  | `ACH_PVP_10_WINS`           | Savaşçı           | Online PvP'de 10 galibiyet                               | Hayır  |
| 24  | `ACH_CAMPAIGN_STARS_10`     | Yıldız Toplayıcı  | Görev modunda toplam 10 yıldız kazan                     | Hayır  |
| 25  | `ACH_CAMPAIGN_STARS_30`     | Yıldız Avcısı     | Görev modunda toplam 30 yıldız kazan                     | Hayır  |
| 26  | `ACH_CAMPAIGN_STARS_50`     | Yıldız Ustası     | Görev modunda toplam 50 yıldız kazan                     | Hayır  |
| 27  | `ACH_CAMPAIGN_STARS_100`    | Yıldız Tanrısı    | Görev modunda toplam 100 yıldız kazan                    | Evet   |
| 28  | `ACH_CAMPAIGN_LVL50_3STAR`  | Yarı Mükemmel     | 50. bölümü 3 yıldızla tamamla                            | Evet   |
| 29  | `ACH_CAMPAIGN_LVL100_3STAR` | Efsane Kahraman   | 100. bölümü 3 yıldızla tamamla                           | Evet   |
| 30  | `ACH_SPRINT_SUB60`          | Hızlı Parmaklar   | Sprint modunda 40 satırı 240 saniyeden kısa sürede bitir | Hayır  |
| 31  | `ACH_SPRINT_SUB45`          | Sprint Uzmanı     | Sprint modunda 40 satırı 200 saniyeden kısa sürede bitir | Evet   |
| 32  | `ACH_ULTRA_50K`             | Ultra Usta        | Ultra modunda 10.000+ puan yap                           | Hayır  |
| 33  | `ACH_ULTRA_100K`            | Ultra Efsane      | Ultra modunda 15.000+ puan yap                           | Evet   |
| 34  | `ACH_SURVIVAL_5MIN`         | Hayatta Kalan     | Survival modunda 5 dakika hayatta kal                    | Hayır  |
| 35  | `ACH_SURVIVAL_10MIN`        | Sağ Kalan         | Survival modunda 10 dakika hayatta kal                   | Hayır  |
| 36  | `ACH_CASCADE_CHAIN_10`      | Zincir Reaksiyonu | Cascade modunda 10x+ zincir combo yap                    | Hayır  |
| 37  | `ACH_HARDCORE_LEVEL10`      | Hardcore Savaşçı  | Hardcore modunda seviye 10'a ulaş                        | Evet   |
| 38  | `ACH_DAILY_7_STREAK`        | Haftalık Rutin    | Günlük Challenge'da 7 gün üst üste oyna                  | Hayır  |
| 39  | `ACH_DAILY_30_STREAK`       | Disiplin Ustası   | Günlük Challenge'da 30 gün üst üste oyna                 | Evet   |
| 40  | `ACH_WIDE_200_LINES`        | Geniş Açı         | Wide modunda tek oyunda 200 satır temizle                | Hayır  |

### Yerelleştirme (Localization)

Her başarım için Steamworks konsolunda şu diller eklenmelidir:

- **Turkish (TR)** — Yukarıdaki isim ve açıklamalar
- **English (EN)** — İngilizce çeviriler (aşağıda)
- DE, FR, ES, IT, PT, JA, ZH, KO — İsteğe bağlı

#### English Translations

| API Name                    | Display Name (EN) | Description (EN)                            |
| --------------------------- | ----------------- | ------------------------------------------- |
| `ACH_FIRST_GAME`            | First Step        | Complete your first game                    |
| `ACH_FIRST_LINE`            | First Line        | Clear your first line                       |
| `ACH_FIRST_TETRIS`          | First Quadrix     | Make your first 4-line Quadrix              |
| `ACH_SCORE_1K`              | Beginner          | Reach 1,000 points in a single game         |
| `ACH_SCORE_10K`             | Experienced       | Reach 10,000 points in a single game        |
| `ACH_SCORE_50K`             | Master            | Reach 50,000 points in a single game        |
| `ACH_SCORE_100K`            | Legend            | Reach 100,000 points in a single game       |
| `ACH_LINES_10`              | Cleaner           | Clear 10 lines in a single game             |
| `ACH_LINES_50`              | Sweeper           | Clear 50 lines in a single game             |
| `ACH_LINES_100`             | Cleaning Robot    | Clear 100 lines in a single game            |
| `ACH_LINES_200`             | Cleaning Machine  | Clear 200 lines in a single game            |
| `ACH_TETRIS_5`              | Quadrix Master    | Perform 5 Quadrixes                         |
| `ACH_TETRIS_10`             | Quadrix God       | Perform 10 Quadrixes                        |
| `ACH_LEVEL_5`               | Speeding Up       | Reach level 5 in a single game              |
| `ACH_LEVEL_10`              | Speed Demon       | Reach level 10 in a single game             |
| `ACH_LEVEL_15`              | Supersonic        | Reach level 15 in a single game             |
| `ACH_LEVEL_20`              | Light Speed       | Reach level 20 in a single game             |
| `ACH_GAMES_10`              | Loyal Player      | Play 10 games                               |
| `ACH_GAMES_50`              | Regular           | Play 50 games                               |
| `ACH_GAMES_100`             | Professional      | Play 100 games                              |
| `ACH_COMBO_5`               | Combo Master      | Perform a 5x combo in a single game         |
| `ACH_PVP_FIRST_WIN`         | First Victory     | Win your first online PvP match             |
| `ACH_PVP_10_WINS`           | Warrior           | Win 10 online PvP matches                   |
| `ACH_CAMPAIGN_STARS_10`     | Star Collector    | Earn 10 stars in Campaign mode              |
| `ACH_CAMPAIGN_STARS_30`     | Star Hunter       | Earn 30 stars in Campaign mode              |
| `ACH_CAMPAIGN_STARS_50`     | Star Master       | Earn 50 stars in Campaign mode              |
| `ACH_CAMPAIGN_STARS_100`    | Star God          | Earn 100 stars in Campaign mode             |
| `ACH_CAMPAIGN_LVL50_3STAR`  | Half Perfect      | Complete level 50 with 3 stars              |
| `ACH_CAMPAIGN_LVL100_3STAR` | Legendary Hero    | Complete level 100 with 3 stars             |
| `ACH_SPRINT_SUB60`          | Fast Fingers      | Finish Sprint in under 240 seconds          |
| `ACH_SPRINT_SUB45`          | Sprint Specialist | Finish Sprint in under 200 seconds          |
| `ACH_ULTRA_50K`             | Ultra Master      | Score 10,000+ in Ultra mode                 |
| `ACH_ULTRA_100K`            | Ultra Legend      | Score 15,000+ in Ultra mode                 |
| `ACH_SURVIVAL_5MIN`         | Survivor          | Stay alive 5 minutes in Survival mode       |
| `ACH_SURVIVAL_10MIN`        | Last Standing     | Stay alive 10 minutes in Survival mode      |
| `ACH_CASCADE_CHAIN_10`      | Chain Reaction    | Perform a 10x+ chain combo in Cascade mode  |
| `ACH_HARDCORE_LEVEL10`      | Hardcore Warrior  | Reach level 10 in Hardcore mode             |
| `ACH_DAILY_7_STREAK`        | Weekly Routine    | Play 7 consecutive days of Daily Challenge  |
| `ACH_DAILY_30_STREAK`       | Discipline Master | Play 30 consecutive days of Daily Challenge |
| `ACH_WIDE_200_LINES`        | Wide Angle        | Clear 200 lines in a single Wide mode game  |

### Simge Gereksinimleri

- **Boyut:** 64×64 piksel (JPG veya PNG)
- **Kazanılmış simge:** Renkli, parlak
- **Kazanılmamış simge:** Gri tonlama, soluk
- Simgeler `assets/achievements/` klasörüne yerleştirilebilir

---

## İstatistik Listesi (Stats)

Aşağıdaki istatistikleri Steamworks konsolunda **İstatistikler** sekmesinde tanımlayın.

| #   | API Name                  | Tür   | Görünen Ad                    | Varsayılan | Sadece Artış | Azami Değer |
| --- | ------------------------- | ----- | ----------------------------- | ---------- | ------------ | ----------- |
| 1   | `STAT_TOTAL_GAMES`        | INT   | Toplam Oyun                   | 0          | Evet         | —           |
| 2   | `STAT_TOTAL_LINES`        | INT   | Toplam Temizlenen Satır       | 0          | Evet         | —           |
| 3   | `STAT_TOTAL_TETRISES`     | INT   | Toplam Quadrix                | 0          | Evet         | —           |
| 4   | `STAT_MAX_SCORE`          | INT   | En Yüksek Skor                | 0          | Evet         | —           |
| 5   | `STAT_MAX_LINES`          | INT   | En Fazla Satır (tek oyun)     | 0          | Evet         | —           |
| 6   | `STAT_MAX_LEVEL`          | INT   | En Yüksek Seviye              | 0          | Evet         | 30          |
| 7   | `STAT_MAX_COMBO`          | INT   | En Yüksek Kombo               | 0          | Evet         | —           |
| 8   | `STAT_PERFECT_CLEARS`     | INT   | Mükemmel Temizlik Sayısı      | 0          | Evet         | —           |
| 9   | `STAT_PVP_WINS`           | INT   | PvP Galibiyet                 | 0          | Evet         | —           |
| 10  | `STAT_CAMPAIGN_STARS`     | INT   | Toplam Kampanya Yıldızı       | 0          | Evet         | 300         |
| 11  | `STAT_SPRINT_BEST_TIME`   | FLOAT | Sprint En İyi Süre (sn)       | 999        | Hayır        | —           |
| 12  | `STAT_ULTRA_MAX_SCORE`    | INT   | Ultra En Yüksek Skor          | 0          | Evet         | —           |
| 13  | `STAT_SURVIVAL_MAX_TIME`  | FLOAT | Survival En Uzun Süre (sn)    | 0          | Hayır        | —           |
| 14  | `STAT_CASCADE_MAX_CHAIN`  | INT   | Cascade En Uzun Zincir        | 0          | Evet         | —           |
| 15  | `STAT_HARDCORE_MAX_LEVEL` | INT   | Hardcore En Yüksek Seviye     | 0          | Evet         | 30          |
| 16  | `STAT_WIDE_MAX_LINES`     | INT   | Wide En Fazla Satır           | 0          | Evet         | —           |
| 17  | `STAT_DAILY_MAX_STREAK`   | INT   | Günlük Challenge En Uzun Seri | 0          | Evet         | —           |

---

## Teknik Uygulama Özeti

### Kod Akışı

```
Oyun Başlangıcı
  └─> steam_integration.init()
       └─> RequestCurrentStats()    // Stats ve başarım verisi çekilir

Oyun Sonu / Seviye Tamamlama
  └─> AchievementManager.update_stats(score=..., lines=..., ...)
       ├─> check_achievements()
       │    ├─> unlock() → SetAchievement() + StoreStats()
       │    └─> indicate_steam_progress() → IndicateAchievementProgress()
       └─> sync_stats_to_steam()
            └─> SetStat() × N + StoreStats()

Profil Yükleme / Oyun Açılışı
  └─> AchievementManager.sync_to_steam()
       ├─> sync_all_achievements()   // Geriye dönük başarım sync
       └─> sync_stats_to_steam()     // Geriye dönük stat sync
```

### Dosya Yapısı

- `src/achievements.py` — Başarım tanımları, `STEAM_ACHIEVEMENT_MAP`, `AchievementManager`
- `src/steam_integration.py` — ctypes tabanlı Steamworks API sarmalayıcı
  - `unlock_steam_achievement()` — Tek başarım aç
  - `clear_steam_achievement()` — Başarım kilidini geri al (test)
  - `sync_all_achievements()` — Toplu başarım sync
  - `indicate_achievement_progress()` — İlerleme bildirimi
  - `set_steam_stat_int()` / `set_steam_stat_float()` — Stat yaz
  - `get_steam_stat_int()` / `get_steam_stat_float()` — Stat oku
  - `sync_stats_to_steam()` — Toplu stat sync
  - `store_steam_stats()` — Değişiklikleri kalıcı yaz
  - `reset_all_steam_stats()` — Test amaçlı sıfırlama

---

## Test

### Geliştirme Sırasında

```bash
# Steam client konsolunu aç: steam.exe -console
# Sonra konsol sekmesinde:
achievement_clear 4428040 ACH_FIRST_GAME
reset_all_stats 4428040
```

### Python ile Test

```python
import steam_integration

# Başarım aç/kapat
steam_integration.unlock_steam_achievement("ACH_FIRST_GAME")
steam_integration.clear_steam_achievement("ACH_FIRST_GAME")

# İstatistik güncelle
steam_integration.set_steam_stat_int("STAT_TOTAL_GAMES", 42)
steam_integration.store_steam_stats()

# Tümünü sıfırla (DİKKAT!)
steam_integration.reset_all_steam_stats(achievements_too=True)
```

---

## Başarımları Girme

Steamworks Partner konsolunda başarımlar için toplu içe aktarma (VDF import) yoktur.
Her başarım web arayüzünden tek tek girilmelidir.

Hızlı kopyala-yapıştır için: `tools/steam_achievements_copypaste.txt`
Referans VDF (makine tarafından okunabilir): `tools/steam_achievements.vdf`

### Giriş Adımları

1. https://partner.steamgames.com → Quadrix (4428040) → İstatistikler ve Başarımlar → Başarımlar
2. **"New Achievement"** tıkla
3. `tools/steam_achievements_copypaste.txt` dosyasından API Name, Name, Description kopyala-yapıştır
4. Hidden olanları işaretle
5. 64×64 px simgeleri yükle (kazanılmış: renkli, kazanılmamış: gri)
6. Kaydet → sonraki başarıma geç
7. 40 başarımın tamamı girildikten sonra **"Publish Changes"**

İstatistikler de aynı sayfanın "Stats" sekmesinden tek tek girilir (17 adet).

---

## Başarım Görsel Promptları

Aşağıdaki promptlar, Steam başarımlarının görsellerini üretmek için hazırlanmıştır. Hedef stil, ekteki örneğe uygun tek tip bir pixel-art ikon setidir:

- Her görsel kare formatta olsun.
- Her görselde aynı çerçeve, aynı mavi arka plan, aynı kalın siyah kontur ve aynı piksel-art dili korunsun.
- Her görselde tek bir başarım ikonu olsun; yazı, numara, etiket, watermark, ekstra obje ve sahne kalabalığı olmasın.
- Grayscale ve renkli sürüm aynı kompozisyonu paylaşsın; sadece renk paleti değişsin.
- Her ikon merkezde, okunaklı, yüksek kontrastlı ve Steam achievement thumbnail olarak net seçilebilir olsun.
- Dış çerçeve ve iç kart düzeni bütün set boyunca sabit kalsın.

### Ortak Stil Şablonu

Use a consistent 8-bit pixel art achievement icon style for Quadrix. Square icon, light-blue beveled tile, thick black outline, subtle inner shadow, slight glossy highlight, centered composition, clean game UI thumbnail look, no text, no extra labels, no collage, no clutter, no perspective distortion, crisp edges, readable at 64x64, same framing for every icon. For each achievement, generate a 2x5 matrix: top row grayscale locked versions, bottom row full-color unlocked versions. Each column is one achievement. The grayscale and colored version of each icon must be the exact same pose/composition.

### Prompt 1: Başarımlar 1-5 — detaylı ve farklılaştırılmış

Use the common style template above. Create a 2x5 matrix (top row: grayscale locked icons; bottom row: color unlocked icons). Keep framing, border and lighting identical for every tile. For each column, include unique motif, shape and palette to make icons visually distinct even at small sizes.

1. ACH_FIRST_GAME — "İlk Adım": motif: small handheld gamepad + confetti spark; shape: rounded badge with a tiny Tetris block silhouette at center; palette (unlocked): warm orange + cream highlights. Locked: desaturated warm grays with single glossy pixel highlight.

2. ACH_FIRST_LINE — "İlk Satır": motif: an erased horizontal row with a single sweeping broom stroke and three tiny star-sparkles; shape: long horizontal accent inside square to emphasize "line"; palette (unlocked): teal + white burst. Locked: neutral slate grays keeping the horizontal visual cue.

3. ACH_FIRST_TETRIS — "İlk Quadrix": motif: stacked 4-line clear silhouette (four filled rows) with a glowing frame and small burst rings; shape: compact 4x1 bar emblem; palette (unlocked): electric cyan + gold rim. Locked: cold gray with slightly brighter center to preserve readability.

4. ACH_SCORE_1K — "Başlangıç": motif: small circular medal with tiny "1k" glyph as ornament (not literal text, use chip/gem denoting small milestone), subtle ribbon; palette: soft bronze + cream. Locked: matte gray bronze.

5. ACH_SCORE_10K — "Deneyimli": motif: larger shield-shaped badge with a single upward chevron and small sparkles; palette: bright silver-blue with subtle glow. Locked: cooler desaturated silver-gray.

### Prompt 2: Başarımlar 6-10 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix; design each column to visually differentiate score vs lines achievements.

1. ACH_SCORE_50K — "Usta": motif: ornate laurel-wreathed medallion with a faceted gem center (no numbers); palette: warm gold + deep amber. Locked: gray metal with etched laurel silhouette.

2. ACH_SCORE_100K — "Efsane": motif: crown-like crest sitting on a trophy base, tiny star glints; palette: rich gold + purple accent (legendary feel). Locked: stone-gray crest with faint polish.

3. ACH_LINES_10 — "Temizlikçi": motif: a neat broom icon crossing a single cleared row with small dust particles; shape emphasizes horizontal motion; palette: mint green + white. Locked: mid-gray broom silhouette on lighter gray background.

4. ACH_LINES_50 — "Süpürge": motif: dynamic sweeping arc made of stacked tiny blocks being pushed out; include a small swoosh trail to show stronger action than 10-lines; palette: aqua-teal + pale cyan highlights. Locked: desaturated teal-gray.

5. ACH_LINES_100 — "Temizlik Robotu": motif: small friendly robot vacuum built from blocky parts (square body, tiny wheels) with visible suction ring clearing a row; palette: steel-blue + lime accents. Locked: neutral robot gray.

### Prompt 3: Başarımlar 11-15 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_LINES_200 — "Temizlik Makinesi": motif: industrial block-sweeper machine silhouette with multiple sweep arms; strong motion lines and power bolts; palette: diesel blue + bright yellow caution accents. Locked: gunmetal gray.

2. ACH_TETRIS_5 — "Quadrix Ustası": motif: ring of five tiny stacked Quadrix icons circling a central star; composition circular to contrast row/line icons; palette: violet + silver highlights. Locked: cool gray ring.

3. ACH_TETRIS_10 — "Quadrix Tanrısı": motif: elevated pedestal with ten tiny quad markers forming a halo; include subtle crown elements; palette: royal purple + gold. Locked: deep gray with faint halo.

4. ACH_LEVEL_5 — "Hızlanıyor": motif: cheery speedometer dial pointing to 5 with small motion ticks; palette: lime green + white. Locked: desaturated green-gray.

5. ACH_LEVEL_10 — "Hız Canavarı": motif: aggressive speed burst icon with multiple streaks and sharp triangular accents; palette: orange-red + bright white. Locked: dark gray with faint streaks.

### Prompt 4: Başarımlar 16-20 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_LEVEL_15 — "Süpersonik": motif: stylized sonic wave with three concentric streaks and faint sparkles; palette: cyan-blue gradient + neon trim. Locked: pale cool gray.

2. ACH_LEVEL_20 — "Işık Hızı": motif: comet-style streak crossing the tile diagonally with a bright core; palette: electric blue + white flare. Locked: muted stone gray with subtle core.

3. ACH_GAMES_10 — "Sadık Oyuncu": motif: small stack of ten tiny gamepads/cards in a neat pile with ribbon; palette: pastel blue + gold ribbon. Locked: gray stack.

4. ACH_GAMES_50 — "Müdavim": motif: a deeper pile with a small badge overlay (five-dot indicator) to show larger count; palette: teal-blue + silver. Locked: slate gray.

5. ACH_GAMES_100 — "Profesyonel": motif: full trophy silhouette with subtle pixel confetti; palette: polished chrome + royal blue. Locked: dull gray trophy.

### Prompt 5: Başarımlar 21-25 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_COMBO_5 — "Kombo Ustası": motif: interlocked flame icons (5 small flames chained) showing combo chain; palette: fire orange -> magenta gradient. Locked: gray flame links.

2. ACH_PVP_FIRST_WIN — "İlk Zafer": motif: crossed swords behind a small shield badge with a single star; palette: bronze + red accent. Locked: pewter-gray.

3. ACH_PVP_10_WINS — "Savaşçı": motif: heavier shield with laurel and three small crown marks to convey multiple wins; palette: deep red + bronze. Locked: dark iron-gray.

4. ACH_CAMPAIGN_STARS_10 — "Yıldız Toplayıcı": motif: small pouch spilling ten tiny stars with a soft glow; palette: gold + warm yellow. Locked: gray stars.

5. ACH_CAMPAIGN_STARS_30 — "Yıldız Avcısı": motif: net-catching cluster of stars with dynamic motion lines; palette: bright gold + amber. Locked: dim gray cluster.

### Prompt 6: Başarımlar 26-30 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_CAMPAIGN_STARS_50 — "Yıldız Ustası": motif: medallion made of interlocked stars (50 implied by density) with radiant core; palette: sun-gold + white. Locked: matte gray medallion.

2. ACH_CAMPAIGN_STARS_100 — "Yıldız Tanrısı": motif: divine star halo with multiple layers and a central gem; palette: luminous gold + soft purple halo. Locked: stone gray halo.

3. ACH_CAMPAIGN_LVL50_3STAR — "Yarı Mükemmel": motif: level plaque showing "50" shape as small pixel blocks (do not use literal numbers—use level-marker glyph) with three prominent stars above; palette: bronze + sky-blue stars. Locked: gray plaque.

4. ACH_CAMPAIGN_LVL100_3STAR — "Efsane Kahraman": motif: grand stage crest with three large stars and tiny crown motif; palette: platinum + deep gold. Locked: dark pewter crest.

5. ACH_SPRINT_SUB60 — "Hızlı Parmaklar": motif: stopwatch with a single feather-light trail and a small 40-row bar silhouette; palette: cyan + neon green. Locked: gray stopwatch.

### Prompt 7: Başarımlar 31-35 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_SPRINT_SUB45 — "Sprint Uzmanı": motif: high-precision stopwatch with double trails and a small podium flourish; palette: electric cyan + gold trim. Locked: muted gray.

2. ACH_ULTRA_50K — "Ultra Usta": motif: Ultra-mode energy orb with radial spikes and small numeric-ornament gem (non-text); palette: neon magenta + electric blue. Locked: subdued gray orb.

3. ACH_ULTRA_100K — "Ultra Efsane": motif: amplified Ultra orb with crown-like spikes and intense glow; palette: magenta -> gold gradient. Locked: dark gray with faint glow.

4. ACH_SURVIVAL_5MIN — "Hayatta Kalan": motif: heart-shaped stamina meter with 5 small ticks around the rim; palette: green + white. Locked: gray heart meter.

5. ACH_SURVIVAL_10MIN — "Sağ Kalan": motif: reinforced shield with embedded clock ring showing endurance; palette: emerald + gold. Locked: stone-gray shield.

### Prompt 8: Başarımlar 36-40 — detaylı ve farklılaştırılmış

Use the common style template. 2x5 matrix.

1. ACH_CASCADE_CHAIN_10 — "Zincir Reaksiyonu": motif: cascading chain of ten linked pixels forming a waterfall shape; palette: multicolor cascade (blue->purple->teal). Locked: monotone chain gray.

2. ACH_HARDCORE_LEVEL10 — "Hardcore Savaşçı": motif: spiked helmet/crest with blood-red accents and grit texture (stylized, not gory); palette: dark crimson + gunmetal. Locked: dark steel-gray.

3. ACH_DAILY_7_STREAK — "Haftalık Rutin": motif: calendar tile with seven small dots in a row and a checkmark ribbon; palette: pastel blue + sunny yellow. Locked: pale gray calendar.

4. ACH_DAILY_30_STREAK — "Disiplin Ustası": motif: long calendar chain wrapped around a medal, small chain-links show 30 strength; palette: royal blue + gold. Locked: desaturated navy-gray.

5. ACH_WIDE_200_LINES — "Geniş Açı": motif: wide board silhouette with a broad sweeping multi-line clear burst across the tile; palette: sea-green + bright teal. Locked: slate gray wide burst.

---

Notes for artist/renderer: keep icons readable at 64x64 by simplifying silhouettes, using strong contrast and limiting palette to 3-4 colors per icon. Grayscale locked versions should remain visually identical in shape and composition; only desaturate and reduce saturation/contrast while keeping a single small glossy pixel highlight to communicate depth.
