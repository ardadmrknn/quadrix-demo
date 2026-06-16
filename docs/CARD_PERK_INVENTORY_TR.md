# Mystery Mode – Kart/Perk Envanteri (TR)

Bu dosya, Mystery (Kart Ustalığı) modundaki gerçek kart kataloğunu ve ödül progression sistemini özetler. Kanonik kaynak `src/game_modes_extra.py` içindedir.

## Kapsam

- Kaynak kod: `src/game_modes_extra.py`
- Katalog kaynağı: `MysteryCardManager._build_catalog()`
- Uygulama noktası: `MysteryMode._apply_card_effect()`
- Ödül progression hattı: `MysteryCardManager` içindeki `card_xp` / `card_level` alanları

## Ödül Progression Sistemi (card_xp / card_level)

Kart ödül ekonomisi `board.level` (düşüş hızı) hattından **bağımsızdır**. Mystery modunda iki ayrı progression vardır:

- **Board level** → oyun temposu / düşüş hızını yönetir (5 satır = 1 board level)
- **Card level** → kart ödül ekranının ne zaman açılacağını yönetir

### XP kazancı (yalnızca player kaynaklı clear'lar)

| Player satır temizleme | XP |
| --- | --- |
| 1 satır | 1 |
| 2 satır | 3 |
| 3 satır | 5 |
| 4 satır (Quadrix) | 8 |

Ek bonuslar:

- Combo 3+ → +1 XP
- Back-to-back Quadrix → +2 XP
- Perfect clear → +3 XP

### XP eğrisi

`xp_to_next(level) = 4 + (level − 1) × 2`

- Card Level 1 → 4 XP
- Card Level 2 → 6 XP
- Card Level 3 → 8 XP
- ... ve her seviye +2 XP daha

XP taşması durumunda aynı çağrıda birden fazla level kazanılabilir; reward queue'ya eklenir ve overlay'ler sırayla açılır.

### Anti-farm kuralı

Yalnızca `source='player'` clear'lar XP üretir. Sweep, Alt Süpür, patlama, gravity collapse, workshop, ability ve diğer dış kaynaklı temizleme yolları XP veya reward queue üretmez. `card_mode_debug` kısayolu da bu kurala uyar.

## Güncel Katalog (65 ID, 31 benzersiz aile)

Aşağıdaki liste `_build_catalog()` çıktısı ile birebir hizalıdır. `_group_id` ile gruplanmış varyantlar (rare/epic/legendary veya seviye sayısı) tek bir aile olarak sayılır.

> **Mağaza/geliştirme sistemi:** Geliştirilebilir kart aileleri artık enderlik kademelerine (tier) ayrılmıştır. Her kademe ayrı bir katalog girdisidir ama ortak `_group_id` taşır. Aile/kademe/fiyat tek kaynağı `CARD_UPGRADE_FAMILIES`, `CARD_SINGLE_TIER_LOCKED` ve `CARD_FREE_COMMON_FAMILIES` (hepsi `src/game_modes_extra.py`). Detay: [`KART_MAGAZA_SISTEMI_TASARIM_TR.md`](KART_MAGAZA_SISTEMI_TASARIM_TR.md).

### Çekirdek aksiyon kartları

- `clear_rows` — Alt Süpür (`_group_id="clear_rows"`, 4 kademe: `clear_rows`, `clear_rows_rare`, `clear_rows_epic`, `clear_rows_leg`)
- `peak_sculpt` — Tepe Kesici (`_group_id="peak_sculpt"`, 4 kademe: `peak_sculpt`, `peak_sculpt_rare`, `peak_sculpt_epic`, `peak_sculpt_leg`)
- `nova_burst` — Nova Patlaması (`_group_id="nova_burst"`, 3 kademe: `nova_burst`, `nova_burst_epic`, `nova_burst_leg`)
- `mini_bomb` — Mini Bomba
- `quantum_tunneling` — Hayalet Parça (`_group_id="quantum_tunneling"`, 2 kademe: `quantum_tunneling`, `quantum_tunneling_leg`)
- `hammer` — Çekiç (`_group_id="hammer"`, 3 kademe: `hammer`, `hammer_epic`, `hammer_leg`)
- `gravity_well` — Yerçekimi Dalgası
- `block_magnet` — Blok Manyetiği
- `row_shuffle` — Blok Karıştırıcı
- `laser_drill` — Delici Parça
- `sniper_shot` — Keskin Nişancı (`_group_id="sniper_shot"`, 4 kademe: `sniper_shot`, `sniper_shot_rare`, `sniper_shot_epic`, `sniper_shot_leg`)
- `time_capsule` — Zaman Kapsülü
- `future_changer` — Geleceği Değiştiren (`_group_id="future_changer"`, 2 kademe: `future_changer`, `future_changer_leg`)
- `ghost_echo` — İkinci Şans

### Hız Patlaması ailesi (`_group_id="speed_burst"`)

- `speed_burst_rare`
- `speed_burst_epic`
- `speed_burst_legendary`

### Son Düşüş ailesi (`_group_id="freeze_drop"`)

- `freeze_drop_rare`
- `freeze_drop_epic`
- `freeze_drop_legendary`

### Tuttuğunu Koparan ailesi (`_group_id="hold_destroyer"`)

- `hold_destroyer`
- `hold_destroyer_2`
- `hold_destroyer_3`
- `hold_destroyer_4`
- `hold_destroyer_5`

### Kalıcı perkler

- `bomb_master` — Bomba Ustası (`_group_id="bomb_master"`, 3 kademe: `bomb_master`, `bomb_master_epic`, `bomb_master_leg`)
- `rewind_power` — Geri Sarma (`_group_id="rewind_power"`, 3 kademe: `rewind_power`, `rewind_power_epic`, `rewind_power_leg`)
- `perk_phase` — Şekil Değiştirici
- `perk_synergy` — Sinerji Bonus (`_group_id="perk_synergy"`, 3 kademe: `perk_synergy`, `perk_synergy_epic`, `perk_synergy_leg`)
- `perk_second_pocket` — Ekstra Cep
- `perk_flexible_border` — Esnek Sınır

### Yeni/özel kartlar

- `block_workshop_card` — Blok Atölyesi
- `gambler_dice` — Kumarbazın Zarı
- `color_cleanse` — Renk Temizleme (`_group_id="color_cleanse"`, 2 kademe: `color_cleanse`, `color_cleanse_leg`)
- `combo_insurance` — Combo Sigortası (`_group_id="combo_insurance"`, 3 kademe: `combo_insurance`, `combo_insurance_epic`, `combo_insurance_leg`)
- `reverse_debt` — Ters Borç
- `hole_hunter` — Delik Avcısı (`_group_id="hole_hunter"`, 3 kademe: `hole_hunter`, `hole_hunter_epic`, `hole_hunter_leg`)

## Sayım Özeti

- Toplam katalog girdisi: **65 ID**
- Aileler:
  - Hold Destroyer ailesi: 5 varyant
  - Alt Süpür / Tepe Kesici / Keskin Nişancı aileleri: 4'er varyant
  - Nova / Hız Patlaması / Son Düşüş / Çekiç / Bomba Ustası / Geri Sarma / Sinerji / Combo Sigortası / Delik Avcısı aileleri: 3'er varyant
  - Hayalet Parça / Geleceği Değiştiren / Renk Temizleme aileleri: 2'şer varyant
  - Tek varyantlı kalan kartlar: 15
- Benzersiz mekanik aile sayısı: **31**

## Notlar

- Eski dokümanlarda geçen bazı ID'ler (`perk_explosive`, `perk_rewind`, `score`, `column_cleanse`, `combo_boost`, `time_slow`, `line_bonus`, `force_piece` vb.) artık katalogda yer almaz. Doğrulama yaparken kanonik kaynak `MysteryCardManager._build_catalog()` olmalıdır.
- Kart seçim overlay'i, prepare/show ownership tek bir akıştadır: `notify_lines_cleared` level-up tetiklediğinde bir kez `prepare_selection` çağrılır; `update()` döngüsü `pending_choices` doluysa yeniden hazırlık yapmaz.
- Time Capsule restore, `card_xp`, `card_level`, `card_xp_to_next`, `pending_level_ups` ve `pending_choices` alanlarını korur. Restore sonrası bekleyen ödül queue'su sessizce kaybolmaz.

## API Hızlı Referansı

```python
MysteryCardManager.notify_lines_cleared(
    cleared: int,
    *,
    source: str = 'player',          # 'player'/'normal' XP verir; diğerleri vermez
    combo: int = 0,                  # 3+ ise +1 XP bonus
    back_to_back: bool = False,      # Quadrix + B2B ise +2 XP
    perfect_clear: bool = False,     # +3 XP
) -> bool                            # En az bir card_level artışı oluştuysa True
```

`MysteryMode.update()` her tick'te şu kontrolü yapar:

```python
if not self.card_selection_active and self.pending_level_ups > 0:
    if not self.card_manager.pending_choices:
        self.card_manager.prepare_selection()
    if self.card_manager.pending_choices:
        self._open_card_selection()
```

Yani `pending_choices` doluysa update tekrar hazırlık yapmaz; bu, aynı reward için RNG'nin iki kez tüketilmesini engeller.

## İlgili Testler

- `tests/test_mystery_card_xp_progression.py` — XP formülü, eğri ve overflow queue
- `tests/test_mystery_external_line_clear_reward.py` — Anti-farm davranışı
- `tests/test_mystery_card_quality_gaps.py` — Restore queue koruması, debug anti-farm, tek hazırlık kuralı
- `tests/test_mystery_card_effect_behavior.py` — Kart efektlerinin tahta üzerindeki davranışı
- `tests/test_mystery_time_capsule_score_restore.py` — Time capsule akışı
