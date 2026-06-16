# Kart Ustalığı – Kart Seçim Ekranı Kart Listesi (TR)

Bu belge, **Mystery (Kart Ustalığı) modu** kart seçim ekranında oyuncuya sunulan tüm kartların oyun içindeki **başlık** ve **açıklamalarını** birebir kaynak koddan derler.

- Kanonik kaynak (başlık/açıklama): `src/localization.py` → `card_*_title` / `card_*_desc`
- Katalog (id, enderlik, hak sayısı, ikon): `src/game_modes_extra.py` → `MysteryCardManager._build_catalog()`
- Genel envanter ve XP/progression dokümanı: [`CARD_PERK_INVENTORY_TR.md`](CARD_PERK_INVENTORY_TR.md)
- Toplam: **65 kart girdisi** (31 benzersiz mekanik aile, bazı kartlar enderliğe göre çoklu varyant)

> **Mağaza/geliştirme:** Geliştirilebilir aileler enderlik kademelerine (tier) ayrılır. Üst kademe varyantları (örn. `clear_rows_rare`, `bomb_master_epic`) K1 ile **aynı başlık/açıklamayı** paylaşır (`_group_id` üzerinden); fark yalnızca enderlik ve etki değerindedir. Tam aile/kademe dökümü için aşağıdaki "Aile Özeti" tablosuna bakın.

## Yazım Kuralları

- **Anlık etkili kartlar** açıklama tek başına etkide olur, tuş prefix'i yoktur.
- **Tuş veya mouse ile aktif edilen kartlar** açıklamasının başında "X tuşu ile kullan: ..." prefix'i bulunur.
- Hak sayısı (3 hak, 5 kullanım vb.) açıklamada yer almaz; UI'da kart başlığının altında ayrıca gösterilir.

## Açıklamalardaki Placeholder Sözlüğü

| Placeholder | Anlamı |
| --- | --- |
| `{value}` | Kartın `value_range` aralığından çekilen anlık sayısal etki (örn. silinecek satır sayısı, süre). |
| `{echo_cells}` | Yankı Düşüşü kartının bırakacağı gölge blok sayısı. |
| `{freeze_duration}` | Son Düşüş kartının dondurma süresi (saniye). |
| `{line_multiplier}` | Hız Patlaması kartının satır puan çarpanı. |
| `{button}` | Kartın bağlı olduğu kontrol tuşu adı (örn. F, V, X, M). |

---

## Common (Sık çıkan, basit, anında etkili)

### Mini Bomba
- **ID:** `mini_bomb`
- **Açıklama:** Düşen parça yere değdiğinde yanındaki blokları da patlatır.

### Ayna Cep
- **ID:** `mirror_hold`
- **Açıklama:** Saklanan parçayı ayna görüntüsüne çevirir.

### Yankı Düşüşü
- **ID:** `echo_drop`
- **Açıklama:** Parça yere düştüğünde altındaki boş karelere `{echo_cells}` gölge blok bırakır.

### Blok Karıştırıcı
- **ID:** `row_shuffle`
- **Açıklama:** En alttaki `{value}` satırdaki blokların yerlerini karıştırır.

### Tuttuğunu Koparan (Common varyant)
- **ID:** `hold_destroyer`
- **Açıklama:** `{button}` tuşu ile kullan: Sakladığın parçayı silersin.

### Ters Borç
- **ID:** `reverse_debt`
- **Açıklama:** En alttaki 2 satırı siler. Sonraki 5 parça yere değer değmez kilitlenir.

---

## Uncommon (Orta güçte, koşullu etkili)

### Alt Süpür
- **ID:** `clear_rows`
- **Açıklama:** En alttaki `{value}` satırı siler. Üstteki bloklar aşağıya düşer.

### Tepe Kesici
- **ID:** `peak_sculpt`
- **Açıklama:** En yüksek `{value}` bloğu siler ve tahta düzleşir.

### Keskin Nişancı
- **ID:** `sniper_shot`
- **Açıklama:** N tuşu ile kullan: Açılan ekranda istediğin bloğa tıkla, o blok patlar.

### Tuttuğunu Koparan (Uncommon varyant)
- **ID:** `hold_destroyer_2`
- **Açıklama:** `{button}` tuşu ile kullan: Sakladığın parçayı silersin.

---

## Rare (Güçlü, stratejik)

### Çekiç
- **ID:** `hammer`
- **Açıklama:** H tuşu ile kullan: Düşen parça tek bloğa dönüşür.

### Bomba Ustası
- **ID:** `bomb_master`
- **Açıklama:** M tuşu ile kullan: Parça bombaya dönüşür ve yere değdiğinde etrafı patlar.

### Geri Sarma
- **ID:** `rewind_power`
- **Açıklama:** U tuşu ile kullan: Son koyduğun parçayı geri al.

### Sinerji Bonus
- **ID:** `perk_synergy`
- **Açıklama:** Sahip olduğun her özel kart için %10 ekstra puan kazanırsın.

### Delici Parça
- **ID:** `laser_drill`
- **Açıklama:** Düşen parça önündeki blokları eriterek geçer.

### Hız Patlaması (Rare varyant)
- **ID:** `speed_burst_rare`
- **Açıklama:** `{value}` saniye boyunca parçalar daha hızlı düşer. Her sildiğin satır `{line_multiplier}` katı puan kazandırır.

### Son Düşüş (Rare varyant)
- **ID:** `freeze_drop_rare`
- **Açıklama:** F tuşu ile kullan: Düşen parça `{freeze_duration}` saniye havada durur. Bu sürede sadece sağa-sola gidebilir veya sert düşüş yapabilir.

### Tuttuğunu Koparan (Rare varyant)
- **ID:** `hold_destroyer_3`
- **Açıklama:** `{button}` tuşu ile kullan: Sakladığın parçayı silersin.

### Combo Sigortası
- **ID:** `combo_insurance`
- **Açıklama:** Bir kez, satır temizleyemediğin hamlede combo bozulmaz.

### Delik Avcısı
- **ID:** `hole_hunter`
- **Açıklama:** J tuşu ile kullan: Bir sütun seçersin. O sütundaki rastgele kapalı boşluklardan 1 tanesi dolar.

---

## Epic (Çok güçlü, oyun değiştirici)

### Nova Patlaması
- **ID:** `nova_burst`
- **Açıklama:** Sonraki `{value}` parça yere düştüğünde etrafındaki bloklar patlar.

### Hayalet Parça
- **ID:** `quantum_tunneling`
- **Açıklama:** G tuşu ile kullan: Parça hayalet olur ve blokların içinden geçer.

### Şekil Değiştirici
- **ID:** `perk_phase`
- **Açıklama:** LSHIFT tuşu ile kullan: Parçayı ayna görüntüsüne çevirir (L↔J, Z↔S).

### Yerçekimi Dalgası
- **ID:** `gravity_well`
- **Açıklama:** Tüm bloklar aşağıya düşer ve dolan satırlar silinir.

### Geleceği Değiştiren
- **ID:** `future_changer`
- **Açıklama:** Bir pencere açılır ve sonraki 2 parçayı sen seçersin.

### Renk Temizleme
- **ID:** `color_cleanse`
- **Açıklama:** Rastgele bir renkteki tüm bloklar silinir ve üstteki bloklar aşağıya düşer.

### Hız Patlaması (Epic varyant)
- **ID:** `speed_burst_epic`
- **Açıklama:** `{value}` saniye boyunca parçalar daha hızlı düşer. Her sildiğin satır `{line_multiplier}` katı puan kazandırır.

### Son Düşüş (Epic varyant)
- **ID:** `freeze_drop_epic`
- **Açıklama:** F tuşu ile kullan: Düşen parça `{freeze_duration}` saniye havada durur. Bu sürede sadece sağa-sola gidebilir veya sert düşüş yapabilir.

### Tuttuğunu Koparan (Epic varyant)
- **ID:** `hold_destroyer_4`
- **Açıklama:** `{button}` tuşu ile kullan: Sakladığın parçayı silersin.

---

## Legendary (En nadir, en güçlü)

### Blok Manyetiği
- **ID:** `block_magnet`
- **Açıklama:** Tüm bloklar sol kenara yapışır ve aralardaki boşluklar kapanır.

### Ekstra Cep
- **ID:** `perk_second_pocket`
- **Açıklama:** `{button}` tuşu ile kullan: İkinci bir parça saklayabilirsin.

### Esnek Sınır
- **ID:** `perk_flexible_border`
- **Açıklama:** Parçalar tahtanın kenarından 1 blok dışarı çıkabilir.

### İkinci Şans
- **ID:** `ghost_echo`
- **Açıklama:** Oyun bitecekken tahtanın üst yarısı silinir ve oyuna devam edersin.

### Zaman Kapsülü
- **ID:** `time_capsule`
- **Açıklama:** T tuşu ile kullan: Tahtayı kaydedersin. R tuşuna basınca o ana geri dönersin.

### Blok Atölyesi
- **ID:** `block_workshop_card`
- **Açıklama:** Bir atölye açılır ve en fazla 7 bloklu kendi özel parçanı yapabilirsin.

### Kumarbazın Zarı
- **ID:** `gambler_dice`
- **Açıklama:** Zar atılır. Yarı yarıya bir ihtimalle tahta tamamen silinir ya da yarısı bloklarla dolar.

### Hız Patlaması (Legendary varyant)
- **ID:** `speed_burst_legendary`
- **Açıklama:** `{value}` saniye boyunca parçalar daha hızlı düşer. Her sildiğin satır `{line_multiplier}` katı puan kazandırır.

### Son Düşüş (Legendary varyant)
- **ID:** `freeze_drop_legendary`
- **Açıklama:** F tuşu ile kullan: Düşen parça `{freeze_duration}` saniye havada durur. Bu sürede sadece sağa-sola gidebilir veya sert düşüş yapabilir.

### Tuttuğunu Koparan (Legendary varyant)
- **ID:** `hold_destroyer_5`
- **Açıklama:** `{button}` tuşu ile kullan: Sakladığın parçayı silersin.

---

## Aile Özeti (Çoklu Varyantlı Kartlar)

| Aile (`_group_id`) | Varyantlar | Enderlik kademesi |
| --- | --- | --- |
| `clear_rows` | `clear_rows`, `clear_rows_rare`, `clear_rows_epic`, `clear_rows_leg` | Unc 2 → Rare 2-3 → Epic 3-5 → Leg 5 satır |
| `peak_sculpt` | `peak_sculpt`, `peak_sculpt_rare`, `peak_sculpt_epic`, `peak_sculpt_leg` | Unc 2-4 → Rare 3-5 → Epic 8-10 → Leg 10-15 blok |
| `sniper_shot` | `sniper_shot`, `sniper_shot_rare`, `sniper_shot_epic`, `sniper_shot_leg` | Unc 3 → Rare 4 → Epic 5 → Leg 6 hak |
| `bomb_master` | `bomb_master`, `bomb_master_epic`, `bomb_master_leg` | Rare 3 → Epic 4 → Leg 5 hak |
| `combo_insurance` | `combo_insurance`, `combo_insurance_epic`, `combo_insurance_leg` | Rare 2 → Epic 3 → Leg 4 koruma |
| `hole_hunter` | `hole_hunter`, `hole_hunter_epic`, `hole_hunter_leg` | Rare 1 → Epic 2 → Leg 3 boşluk |
| `rewind_power` | `rewind_power`, `rewind_power_epic`, `rewind_power_leg` | Rare 3 → Epic 4 → Leg 5 hak |
| `hammer` | `hammer`, `hammer_epic`, `hammer_leg` | Rare 3 → Epic 4 → Leg 5 hak |
| `perk_synergy` | `perk_synergy`, `perk_synergy_epic`, `perk_synergy_leg` | Rare %10 → Epic %15 → Leg %20 |
| `speed_burst` | `speed_burst_rare`, `speed_burst_epic`, `speed_burst_legendary` | 1.3x → 1.5x → 2.0x puan çarpanı |
| `freeze_drop` | `freeze_drop_rare`, `freeze_drop_epic`, `freeze_drop_legendary` | 6sn/3hak → 10sn/5hak → 15sn/7hak |
| `nova_burst` | `nova_burst`, `nova_burst_epic`, `nova_burst_leg` | Rare 3hak/3x3 → Epic 4hak/4x4 → Leg 5hak/5x5 |
| `future_changer` | `future_changer`, `future_changer_leg` | Epic 2 → Leg 3 parça |
| `quantum_tunneling` | `quantum_tunneling`, `quantum_tunneling_leg` | Epic 3 → Leg 5 hak |
| `color_cleanse` | `color_cleanse`, `color_cleanse_leg` | Epic 1 → Leg 2 renk |
| `hold_destroyer` | `hold_destroyer`, `hold_destroyer_2`, `hold_destroyer_3`, `hold_destroyer_4`, `hold_destroyer_5` | 1 → 2 → 3 → 4 → 5 hak |

Aynı ailenin sadece bir varyantı seçim ekranında belirir; oyuncu bir varyantı aldıktan sonra aile, o koşu için kilitlenir.

## Sayım

- Toplam katalog girdisi: **65 ID**
- Benzersiz mekanik aile: **31**

> Çoklu varyantlı 16 aile (Alt Süpür/Tepe Kesici/Keskin Nişancı 4'er; Nova/Hız Patlaması/Son Düşüş/Çekiç/Bomba Ustası/Geri Sarma/Sinerji/Combo Sigortası/Delik Avcısı 3'er; Hayalet Parça/Geleceği Değiştiren/Renk Temizleme 2'şer; Tuttuğunu Koparan 5) tek aile sayılır. Aile/varyant ayrımı için yukarıdaki "Aile Özeti" tablosuna ve [`CARD_PERK_INVENTORY_TR.md`](CARD_PERK_INVENTORY_TR.md) dosyasındaki sayım özetine bakın.

## Çoklu Dil Desteği

Açıklamaların tamamı 11 dilde tutarlı sade dil ile çevrilmiştir: `tr`, `en`, `de`, `fr`, `es`, `it`, `pt`, `ru`, `ja`, `zh`, `ko`. Çeviriler `src/localization.py` içindeki `card_*_desc` anahtarlarından okunur; her dilde aynı tuş prefix'i ve aynı sade etki cümlesi korunur.

## Doğrulama

Yeni bir kart eklendiğinde veya başlık/açıklama düzenlendiğinde bu belge yeniden senkronize edilmelidir. Doğru kaynak her zaman lokalizasyon tarafıdır:

```
src/localization.py → card_<id>_title / card_<id>_desc
```

Mekanik / XP davranış sözleşmesi için: [`CARD_PERK_INVENTORY_TR.md`](CARD_PERK_INVENTORY_TR.md).
