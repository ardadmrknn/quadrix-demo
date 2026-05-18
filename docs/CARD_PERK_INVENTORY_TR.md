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

## Güncel Katalog (34 ID, 26 benzersiz aile)

Aşağıdaki liste `_build_catalog()` çıktısı ile birebir hizalıdır. `_group_id` ile gruplanmış varyantlar (rare/epic/legendary veya seviye sayısı) tek bir aile olarak sayılır.

### Çekirdek aksiyon kartları

- `clear_rows` — Alt Süpür
- `peak_sculpt` — Tepe Kesici
- `nova_burst` — Nova Patlaması
- `mini_bomb` — Mini Bomba
- `quantum_tunneling` — Hayalet Parça
- `hammer` — Çekiç
- `gravity_well` — Yerçekimi Dalgası
- `block_magnet` — Blok Manyetiği
- `row_shuffle` — Blok Karıştırıcı
- `laser_drill` — Delici Parça
- `sniper_shot` — Keskin Nişancı
- `time_capsule` — Zaman Kapsülü
- `future_changer` — Geleceği Değiştiren
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

- `bomb_master` — Bomba Ustası
- `rewind_power` — Geri Sarma
- `perk_phase` — Şekil Değiştirici
- `perk_synergy` — Sinerji Bonus
- `perk_second_pocket` — Ekstra Cep
- `perk_flexible_border` — Esnek Sınır

### Yeni/özel kartlar

- `block_workshop_card` — Blok Atölyesi
- `gambler_dice` — Kumarbazın Zarı
- `color_cleanse` — Renk Temizleme

## Sayım Özeti

- Toplam katalog girdisi: **34 ID**
- Aileler:
  - Hold Destroyer ailesi: 5 varyant
  - Speed Burst ailesi: 3 varyant
  - Freeze Drop ailesi: 3 varyant
  - Geri kalan kartlar: 23
- Benzersiz mekanik aile sayısı: **26**

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
