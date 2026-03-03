# Steam Başarımlar ve İstatistikler — Kurulum Rehberi

Bu belge, Quadrix oyununun Steam başarımlarını ve istatistiklerini
Steamworks Partner sitesinde yapılandırmak için gerekli bilgileri içerir.

**Steamworks Partner Console:** https://partner.steamgames.com/apps/achievements/4428040

---

## Başarım Listesi (Achievements)

Aşağıdaki başarımları Steamworks konsolunda tanımlayın.
Her başarım için 64×64 px simge (açık) ve gri simge (kilitli) gereklidir.

| # | API Name | Görünen Ad (TR) | Açıklama (TR) | Gizli? |
|---|----------|------------------|--------------|--------|
| 1 | `ACH_FIRST_GAME` | İlk Adım | İlk oyununu tamamla | Hayır |
| 2 | `ACH_FIRST_LINE` | İlk Satır | İlk satırını temizle | Hayır |
| 3 | `ACH_FIRST_TETRIS` | İlk Quadrix | İlk 4 satırlık Quadrix'ini yap | Hayır |
| 4 | `ACH_PERFECT_CLEAR` | Mükemmel Temizlik | Tahtayı tamamen temizle | Hayır |
| 5 | `ACH_NO_MISTAKES` | Kusursuz | Daily Challenge: No Mistakes görevini tamamla | Evet |
| 6 | `ACH_SCORE_1K` | Başlangıç | Bir oyunda 1,000 puana ulaş | Hayır |
| 7 | `ACH_SCORE_10K` | Deneyimli | Bir oyunda 10,000 puana ulaş | Hayır |
| 8 | `ACH_SCORE_50K` | Usta | Bir oyunda 50,000 puana ulaş | Hayır |
| 9 | `ACH_SCORE_100K` | Efsane | Bir oyunda 100,000 puana ulaş | Evet |
| 10 | `ACH_LINES_10` | Temizlikçi | Bir oyunda 10 satır temizle | Hayır |
| 11 | `ACH_LINES_50` | Süpürge | Bir oyunda 50 satır temizle | Hayır |
| 12 | `ACH_LINES_100` | Temizlik Robotu | Bir oyunda 100 satır temizle | Hayır |
| 13 | `ACH_LINES_200` | Temizlik Makinesi | Bir oyunda 200 satır temizle | Evet |
| 14 | `ACH_TETRIS_5` | Quadrix Ustası | 5 Quadrix yap | Hayır |
| 15 | `ACH_TETRIS_10` | Quadrix Tanrısı | 10 Quadrix yap | Hayır |
| 16 | `ACH_LEVEL_5` | Hızlanıyor | Bir oyunda seviye 5'e ulaş | Hayır |
| 17 | `ACH_LEVEL_10` | Hız Canavarı | Bir oyunda seviye 10'a ulaş | Hayır |
| 18 | `ACH_LEVEL_15` | Süpersonik | Bir oyunda seviye 15'e ulaş | Hayır |
| 19 | `ACH_LEVEL_20` | Işık Hızı | Bir oyunda seviye 20'ye ulaş | Evet |
| 20 | `ACH_GAMES_10` | Sadık Oyuncu | 10 oyun oyna | Hayır |
| 21 | `ACH_GAMES_50` | Müdavim | 50 oyun oyna | Hayır |
| 22 | `ACH_GAMES_100` | Profesyonel | 100 oyun oyna | Hayır |
| 23 | `ACH_COMBO_5` | Kombo Ustası | Bir oyunda 5x kombo yap | Hayır |
| 24 | `ACH_PVP_FIRST_WIN` | İlk Zafer | PvP'de ilk galibiyetini al | Hayır |
| 25 | `ACH_PVP_10_WINS` | Savaşçı | PvP'de 10 galibiyet | Hayır |
| 26 | `ACH_CAMPAIGN_STARS_10` | Yıldız Toplayıcı | Görev modunda toplam 10 yıldız kazan | Hayır |
| 27 | `ACH_CAMPAIGN_STARS_30` | Yıldız Avcısı | Görev modunda toplam 30 yıldız kazan | Hayır |
| 28 | `ACH_CAMPAIGN_STARS_50` | Yıldız Ustası | Görev modunda toplam 50 yıldız kazan | Hayır |
| 29 | `ACH_CAMPAIGN_STARS_100` | Yıldız Tanrısı | Görev modunda toplam 100 yıldız kazan | Evet |
| 30 | `ACH_CAMPAIGN_LVL50_3STAR` | Yarı Mükemmel | 50. bölümü 3 yıldızla tamamla | Evet |
| 31 | `ACH_CAMPAIGN_LVL100_3STAR` | Efsane Kahraman | 100. bölümü 3 yıldızla tamamla | Evet |
| 32 | `ACH_SPRINT_SUB60` | Hızlı Parmaklar | Sprint modunda 40 satırı 60 saniyeden kısa sürede bitir | Hayır |
| 33 | `ACH_SPRINT_SUB45` | Işık Hızı | Sprint modunda 40 satırı 45 saniyeden kısa sürede bitir | Evet |
| 34 | `ACH_ULTRA_50K` | Ultra Usta | Ultra modunda 50.000+ puan yap | Hayır |
| 35 | `ACH_ULTRA_100K` | Ultra Efsane | Ultra modunda 100.000+ puan yap | Evet |
| 36 | `ACH_SURVIVAL_5MIN` | Hayatta Kalan | Survival modunda 5 dakika hayatta kal | Hayır |
| 37 | `ACH_SURVIVAL_10MIN` | Sağ Kalan | Survival modunda 10 dakika hayatta kal | Hayır |
| 38 | `ACH_CASCADE_CHAIN_10` | Zincir Reaksiyonu | Cascade modunda 10x+ zincir combo yap | Hayır |
| 39 | `ACH_HARDCORE_LEVEL10` | Hardcore Savaşçı | Hardcore modunda seviye 10'a ulaş | Evet |
| 40 | `ACH_DAILY_7_STREAK` | Haftalık Rutin | Günlük Challenge'da 7 gün üst üste oyna | Hayır |
| 41 | `ACH_DAILY_30_STREAK` | Disiplin Ustası | Günlük Challenge'da 30 gün üst üste oyna | Evet |
| 42 | `ACH_WIDE_200_LINES` | Geniş Açı | Wide modunda tek oyunda 200 satır temizle | Hayır |

### Yerelleştirme (Localization)

Her başarım için Steamworks konsolunda şu diller eklenmelidir:
- **Turkish (TR)** — Yukarıdaki isim ve açıklamalar
- **English (EN)** — İngilizce çeviriler (aşağıda)
- DE, FR, ES, IT, PT, JA, ZH, KO — İsteğe bağlı

#### English Translations

| API Name | Display Name (EN) | Description (EN) |
|----------|-------------------|-------------------|
| `ACH_FIRST_GAME` | First Step | Complete your first game |
| `ACH_FIRST_LINE` | First Line | Clear your first line |
| `ACH_FIRST_TETRIS` | First Quadrix | Make your first 4-line Quadrix |
| `ACH_PERFECT_CLEAR` | Perfect Clear | Clear the entire board |
| `ACH_NO_MISTAKES` | Flawless | Complete a Daily Challenge: No Mistakes |
| `ACH_SCORE_1K` | Beginner | Reach 1,000 points in a single game |
| `ACH_SCORE_10K` | Experienced | Reach 10,000 points in a single game |
| `ACH_SCORE_50K` | Master | Reach 50,000 points in a single game |
| `ACH_SCORE_100K` | Legend | Reach 100,000 points in a single game |
| `ACH_LINES_10` | Cleaner | Clear 10 lines in a single game |
| `ACH_LINES_50` | Sweeper | Clear 50 lines in a single game |
| `ACH_LINES_100` | Cleaning Robot | Clear 100 lines in a single game |
| `ACH_LINES_200` | Cleaning Machine | Clear 200 lines in a single game |
| `ACH_TETRIS_5` | Quadrix Master | Perform 5 Quadrixes |
| `ACH_TETRIS_10` | Quadrix God | Perform 10 Quadrixes |
| `ACH_LEVEL_5` | Speeding Up | Reach level 5 in a single game |
| `ACH_LEVEL_10` | Speed Demon | Reach level 10 in a single game |
| `ACH_LEVEL_15` | Supersonic | Reach level 15 in a single game |
| `ACH_LEVEL_20` | Light Speed | Reach level 20 in a single game |
| `ACH_GAMES_10` | Loyal Player | Play 10 games |
| `ACH_GAMES_50` | Regular | Play 50 games |
| `ACH_GAMES_100` | Professional | Play 100 games |
| `ACH_COMBO_5` | Combo Master | Perform a 5x combo in a single game |
| `ACH_PVP_FIRST_WIN` | First Victory | Win your first PvP match |
| `ACH_PVP_10_WINS` | Warrior | Win 10 PvP matches |
| `ACH_CAMPAIGN_STARS_10` | Star Collector | Earn 10 stars in Campaign mode |
| `ACH_CAMPAIGN_STARS_30` | Star Hunter | Earn 30 stars in Campaign mode |
| `ACH_CAMPAIGN_STARS_50` | Star Master | Earn 50 stars in Campaign mode |
| `ACH_CAMPAIGN_STARS_100` | Star God | Earn 100 stars in Campaign mode |
| `ACH_CAMPAIGN_LVL50_3STAR` | Half Perfect | Complete level 50 with 3 stars |
| `ACH_CAMPAIGN_LVL100_3STAR` | Legendary Hero | Complete level 100 with 3 stars |
| `ACH_SPRINT_SUB60` | Fast Fingers | Finish Sprint in under 60 seconds |
| `ACH_SPRINT_SUB45` | Light Speed | Finish Sprint in under 45 seconds |
| `ACH_ULTRA_50K` | Ultra Master | Score 50,000+ in Ultra mode |
| `ACH_ULTRA_100K` | Ultra Legend | Score 100,000+ in Ultra mode |
| `ACH_SURVIVAL_5MIN` | Survivor | Stay alive 5 minutes in Survival mode |
| `ACH_SURVIVAL_10MIN` | Last Standing | Stay alive 10 minutes in Survival mode |
| `ACH_CASCADE_CHAIN_10` | Chain Reaction | Perform a 10x+ chain combo in Cascade mode |
| `ACH_HARDCORE_LEVEL10` | Hardcore Warrior | Reach level 10 in Hardcore mode |
| `ACH_DAILY_7_STREAK` | Weekly Routine | Play 7 consecutive days of Daily Challenge |
| `ACH_DAILY_30_STREAK` | Discipline Master | Play 30 consecutive days of Daily Challenge |
| `ACH_WIDE_200_LINES` | Wide Angle | Clear 200 lines in a single Wide mode game |

### Simge Gereksinimleri

- **Boyut:** 64×64 piksel (JPG veya PNG)
- **Kazanılmış simge:** Renkli, parlak
- **Kazanılmamış simge:** Gri tonlama, soluk
- Simgeler `assets/achievements/` klasörüne yerleştirilebilir

---

## İstatistik Listesi (Stats)

Aşağıdaki istatistikleri Steamworks konsolunda **İstatistikler** sekmesinde tanımlayın.

| # | API Name | Tür | Görünen Ad | Varsayılan | Sadece Artış | Azami Değer |
|---|----------|-----|------------|------------|-------------|-------------|
| 1 | `STAT_TOTAL_GAMES` | INT | Toplam Oyun | 0 | Evet | — |
| 2 | `STAT_TOTAL_LINES` | INT | Toplam Temizlenen Satır | 0 | Evet | — |
| 3 | `STAT_TOTAL_TETRISES` | INT | Toplam Quadrix | 0 | Evet | — |
| 4 | `STAT_MAX_SCORE` | INT | En Yüksek Skor | 0 | Evet | — |
| 5 | `STAT_MAX_LINES` | INT | En Fazla Satır (tek oyun) | 0 | Evet | — |
| 6 | `STAT_MAX_LEVEL` | INT | En Yüksek Seviye | 0 | Evet | 30 |
| 7 | `STAT_MAX_COMBO` | INT | En Yüksek Kombo | 0 | Evet | — |
| 8 | `STAT_PERFECT_CLEARS` | INT | Mükemmel Temizlik Sayısı | 0 | Evet | — |
| 9 | `STAT_PVP_WINS` | INT | PvP Galibiyet | 0 | Evet | — |
| 10 | `STAT_CAMPAIGN_STARS` | INT | Toplam Kampanya Yıldızı | 0 | Evet | 300 |
| 11 | `STAT_SPRINT_BEST_TIME` | FLOAT | Sprint En İyi Süre (sn) | 999 | Hayır | — |
| 12 | `STAT_ULTRA_MAX_SCORE` | INT | Ultra En Yüksek Skor | 0 | Evet | — |
| 13 | `STAT_SURVIVAL_MAX_TIME` | FLOAT | Survival En Uzun Süre (sn) | 0 | Hayır | — |
| 14 | `STAT_CASCADE_MAX_CHAIN` | INT | Cascade En Uzun Zincir | 0 | Evet | — |
| 15 | `STAT_HARDCORE_MAX_LEVEL` | INT | Hardcore En Yüksek Seviye | 0 | Evet | 30 |
| 16 | `STAT_WIDE_MAX_LINES` | INT | Wide En Fazla Satır | 0 | Evet | — |
| 17 | `STAT_DAILY_MAX_STREAK` | INT | Günlük Challenge En Uzun Seri | 0 | Evet | — |

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
7. 42 başarımın tamamı girildikten sonra **"Publish Changes"**

İstatistikler de aynı sayfanın "Stats" sekmesinden tek tek girilir (17 adet).
