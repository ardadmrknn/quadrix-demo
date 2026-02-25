# Mystery Mode – Kart/Perk Envanteri (TR)

Bu dosya, **gerçek katalog** (`src/game_modes_extra.py` içindeki `MysteryCardManager._build_catalog`) ile hizalı güncel envanteri listeler.

## Kapsam
- Kaynak kod: `src/game_modes_extra.py`
- Katalog kaynağı: `MysteryCardManager._build_catalog()`
- Uygulama noktası: `MysteryMode._apply_card_effect()`

## Güncel Durum Özeti
- Toplam katalog girdisi: **30 ID**
- Bunun **5 tanesi** `hold_destroyer` ailesinin seviye varyantı (`hold_destroyer_1..5` davranışı)
- Benzersiz kart/perk ailesi: **26**

## Güncel Katalog ID’leri

### Core kartlar
- `clear_rows`
- `peak_sculpt`
- `row_shuffle`
- `speed_burst`
- `mini_bomb`
- `quantum_tunneling`
- `hammer`
- `nova_burst`
- `gravity_well`
- `block_magnet`
- `ghost_echo`
- `laser_drill`
- `sniper_shot`
- `time_capsule`
- `future_changer`

### Perk / ability kartları (katalogdaki mevcut ID)
- `bomb_master`
- `rewind_power`
- `perk_phase`
- `perk_synergy`
- `perk_second_pocket`
- `perk_flexible_border`

### Yeni/özel kartlar
- `block_workshop_card`
- `gambler_dice`
- `color_cleanse`

### Hold Destroyer ailesi (aynı mekanik, farklı hak)
- `hold_destroyer`
- `hold_destroyer_2`
- `hold_destroyer_3`
- `hold_destroyer_4`
- `hold_destroyer_5`

## Notlar
- Bu katalog, eski dokümanlarda geçen bazı ID’lerin (`perk_explosive`, `perk_rewind`, `score`, `column_cleanse`, `combo_boost`, `time_slow`, `line_bonus`, `force_piece` vb.) artık **teklif edilen kart havuzunda olmadığını** gösterir.
- Kod içinde bazı eski branch’ler geriye dönük uyumluluk/test senaryoları için durabilir; envanter doğrulamasında esas alınan kaynak `._build_catalog()` olmalıdır.
