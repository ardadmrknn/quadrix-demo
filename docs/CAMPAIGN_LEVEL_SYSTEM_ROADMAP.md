# 🎮 Quadrix Campaign/Bölüm Sistemi - Kapsamlı Yol Haritası

> **Versiyon:** 3.0  
> **Son Güncelleme:** 2026-01-28  
> **Hazırlayan:** AI Game Design Assistant  
> **Durum:** ✅ Faz 1, Faz 2 ve Faz 3 Tamamlandı

---

## ✅ UYGULAMA DURUMU

| Bileşen | Durum | Notlar |
|---------|-------|--------|
| **CampaignMode Sınıfı** | ✅ Tamamlandı | `src/campaign/campaign_mode.py` - 735 satır |
| **Level Data (100 Level)** | ✅ Tamamlandı | `src/campaign/level_data.py` - Dinamik zorluk sistemi |
| **Objective Sistemi** | ✅ Tamamlandı | `src/campaign/objectives.py` - 7 görev türü |
| **Lokalizasyon** | ✅ Tamamlandı | `src/localization.py` - 40+ yeni çeviri |
| **Menü Entegrasyonu** | ✅ Tamamlandı | `src/menu.py` ve `src/main.py` güncellendi |
| **Level Seçim Ekranı** | ✅ Tamamlandı | `src/campaign/level_select.py` - World Map UI |
| **Sonraki Level Geçişi** | ✅ Tamamlandı | ENTER ile sonraki level'a geçiş |
| **Özel Bloklar** | ✅ Tamamlandı | `src/campaign/special_blocks.py` - 6 blok türü |
| **Power-up Sistemi** | ✅ Tamamlandı | `src/campaign/power_ups.py` - 6 güçlendirici |
| **UI Efektleri** | ✅ Tamamlandı | `src/campaign/campaign_ui.py` - 730 satır |

---

## 📚 İçindekiler

1. [Giriş ve Araştırma Özeti](#giriş-ve-araştırma-özeti)
2. [Görev Türleri (Objective Types)](#görev-türleri-objective-types)
3. [Özel Blok Mekanikleri](#özel-blok-mekanikleri)
4. [Zorluk Eğrisi ve Dengeleme](#zorluk-eğrisi-ve-dengeleme)
5. [Yıldız Sistemi](#yıldız-sistemi)
6. [100 Level Taslak Tasarımı](#100-level-taslak-tasarımı)
7. [Dünya/Bölge Sistemi](#dünyabölge-sistemi)
8. [Power-up ve Booster Sistemi](#power-up-ve-booster-sistemi)
9. [İlerleme ve Ödül Sistemi](#ilerleme-ve-ödül-sistemi)
10. [Teknik Uygulama Planı](#teknik-uygulama-planı)

---

## 🔬 Giriş ve Araştırma Özeti

### Mobil Quadrix Oyunlarından Öğrenilenler

Araştırma sonucunda şu önemli bulgular elde edildi:

| Oyun | Özellik | Bizim Oyuna Uygulanabilirliği |
|------|---------|-------------------------------|
| **Quadrix Mobile (N3TWORK)** | Adventure mod, hareket limiti, reklam/satın alma ile ekstra hamle | ✅ Hareket limiti, ❌ Reklam/satın alma (istemiyorsan) |
| **Quadrix Beat** | Ritim tabanlı, günlük/haftalık görevler | ✅ Günlük görev sistemi |
| **Quadrix Blast** | Bomba blokları, zincir reaksiyonları | ✅ Özel bloklar |
| **Quadrix 99** | Battle Royale, "garbage" blokları | ⚠️ Kısmen (hazır blok engeller) |
| **Candy Crush (Referans)** | 3 yıldız sistemi, özel blok türleri, zorluk eğrisi | ✅ Yıldız sistemi, ✅ Özel bloklar |

### Temel Tasarım Prensipleri

1. **Progresif Zorluk**: Her level bir öncekinden biraz daha zor
2. **Yeni Mekanik Tanıtımı**: Yeni mekanik tanıtıldığında zorluk düşer
3. **Dalgalı Zorluk Eğrisi**: Zor levellerden sonra dinlenme levelleri
4. **Her Level Benzersiz**: Her levelin kendine özgü bir "hook"u olmalı
5. **Boostersız Geçilebilir**: Her level normal oynamayla geçilebilmeli

---

## 🎯 Görev Türleri (Objective Types)

### ✅ Uygulanmış Görev Sınıfları (src/campaign/objectives.py)

| Sınıf | Görev Türü | Açıklama | Durum |
|-------|-----------|----------|-------|
| `ClearLinesObjective` | `clear_lines` | Belirtilen sayıda satır temizle | ✅ |
| `ScoreObjective` | `score` | Hedef puana ulaş | ✅ |
| `TetrisObjective` | `tetris` | Quadrix (4 satır birden) yap | ✅ |
| `ComboObjective` | `combo` | Ardışık temizleme yap | ✅ |
| `TimeObjective` | `survive_time` / `complete_time` | Süre bazlı görevler | ✅ |
| `SpecialBlockObjective` | `clear_special` | Özel blokları temizle | ✅ |
| `MoveEfficiencyObjective` | `efficiency` | Hamle verimliliği | ✅ |

### Planlanan Görev Türleri

| Görev ID | Türkçe | İngilizce | Durum |
|----------|--------|-----------|-------|
| `t_spin` | X T-Spin Yap | Make X T-Spins | 🔄 Planlı |
| `perfect_clear` | Mükemmel Temizlik | Perfect Clear | 🔄 Planlı |
| `back_to_back` | X Arka Arkaya | X Back-to-Back | 🔄 Planlı |

---

## 🧊 Özel Blok Mekanikleri

> **✅ Tamamlandı:** Özel bloklar `src/campaign/special_blocks.py` dosyasında implement edildi.

### ✅ Uygulanan Özel Blok Türleri (special_blocks.py)

| Blok Türü | Enum Değeri | Davranış | Durum |
|-----------|-------------|----------|-------|
| Buz Bloğu | `ice` | Komşu satır temizlenince erir | ✅ |
| Kilitli Blok | `locked` | 2 temizleme gerektirir | ✅ |
| Bomba Bloğu | `bomb` | 3x3 alan patlatır | ✅ |
| Zamanlı Blok | `timer` | Süre dolunca büyür | ✅ |
| Yıldız Bloğu | `star` | Bonus puan verir | ✅ |
| Gökkuşağı Bloğu | `rainbow` | Joker renk (animasyonlu) | ✅ |

### Blok Detayları

#### 1. 🧊 Buz Bloğu (Ice Block)
```python
{
    "id": "ice_block",
    "name": {"tr": "Buz Bloğu", "en": "Ice Block"},
    "behavior": "Donmuş blok, komşu satır temizlenince erir",
    "layers": 1,  # Tek katman - bir temizleme yeterli
    "visual": "Mavi parlak, kar tanesi efekti"
}
```

#### 2. 💣 Bomba Bloğu (Bomb Block)
```python
{
    "id": "bomb_block",
    "name": {"tr": "Bomba Bloğu", "en": "Bomb Block"},
    "behavior": "Satır tamamlandığında patlar, 3x3 alan temizler",
    "explosion_radius": 3,
    "chain_reaction": True
}
```

### SpecialBlockManager API

```python
from campaign import SpecialBlockManager, SpecialBlockType

manager = SpecialBlockManager()

# Özel blok ekle
manager.add_special_block(x=5, y=15, block_type=SpecialBlockType.ICE)
manager.add_special_block(x=3, y=14, block_type=SpecialBlockType.BOMB)

# Blok kontrolü
is_special = manager.is_special(5, 15)  # True
block_type = manager.get_block_type(3, 14)  # SpecialBlockType.BOMB

# Güncelleme (her frame)
events = manager.update(dt, board)

# Satır temizlendiğinde
result = manager.on_line_cleared([15, 16], board)
# result: {'points_earned': 500, 'ice_melted': [(5, 14)], ...}

# Blokları aşağı kaydır
manager.shift_blocks_down([15, 16])
```

---

## 📈 Zorluk Eğrisi ve Dengeleme

### ✅ Uygulanan Zorluk Sistemi

Level data'da dinamik zorluk hesaplama:

```python
# Hız hesaplama (level_data.py'den)
def _calculate_speed(level: int) -> int:
    """800ms (L1) → 250ms (L100) arası hız"""
    return max(250, 900 - (level * 7))

# Level 1: 893ms
# Level 50: 550ms  
# Level 100: 250ms
```

### Zorluk Parametreleri

| Parametre | Level 1-20 | Level 21-40 | Level 41-60 | Level 61-80 | Level 81-100 |
|-----------|------------|-------------|-------------|-------------|--------------|
| Düşme Hızı | ~850ms | ~700ms | ~550ms | ~400ms | ~300ms |
| İzin Verilen Bloklar | 3-5 | 5-7 | 7 (Tümü) | 7 (Tümü) | 7 (Tümü) |
| Satır Hedefi | 3-10 | 8-15 | 12-20 | 16-25 | 20-30 |
| Özel Kurallar | Yok | Başlangıç | Orta | Çok | Tümü |

---

## ⭐ Yıldız Sistemi

### ✅ Uygulanan Sistem (campaign_mode.py)

Her level için 3 yıldız kriterleri `level_data.py`'de tanımlı:

```python
# Örnek yıldız koşulları
"star_conditions": {
    1: {"type": "complete"},           # 1★ Level'ı tamamla
    2: {"type": "score", "value": 1000}, # 2★ 1000+ puan
    3: {"type": "score", "value": 2000}  # 3★ 2000+ puan
}
```

---

## 🗺️ 100 Level Taslak Tasarımı

### ✅ 5 Dünya Sistemi (Uygulandı)

| Dünya | İsim | Level Aralığı | Tema |
|-------|------|---------------|------|
| 1 | Başlangıç Vadisi | 1-20 | Yeşil, kolay |
| 2 | Buz Diyarı | 21-40 | Mavi, buz blokları |
| 3 | Lav Mağarası | 41-60 | Kırmızı, bomba blokları |
| 4 | Fırtına Kalesi | 61-80 | Mor, zamanlı bloklar |
| 5 | Yıldız Kulesi | 81-100 | Altın, tüm mekanikler |

### Level Yapısı

Her level şunları içerir:
- **level**: Level numarası (1-100)
- **world**: Hangi dünyada (1-5)
- **name**: İsim (TR/EN lokalize)
- **objectives**: Görev listesi
- **allowed_pieces**: İzin verilen Tetromino'lar
- **speed**: Düşme hızı (ms)
- **time_limit**: Süre limiti (isteğe bağlı)
- **move_limit**: Hamle limiti (isteğe bağlı)
- **special_blocks**: Özel blok türleri
- **special_rules**: Özel kurallar (no_hold, cascade_mode)
- **star_conditions**: Yıldız koşulları
- **xp_reward**: XP ödülü
- **is_boss**: Boss level mi?

---

## ⚡ Power-up ve Booster Sistemi

> **✅ Tamamlandı:** Power-up sistemi `src/campaign/power_ups.py` dosyasında implement edildi.

### ✅ Uygulanan Power-up Türleri (power_ups.py)

| Power-up | Enum Değeri | Açıklama | Süre | Maliyet |
|----------|-------------|----------|------|---------|
| Satır Bombası | `line_bomb` | En alt dolu satırı patlatır | Anlık | 50 XP |
| Zaman Dondurma | `time_freeze` | Zaman sayacını durdurur | 5s | 75 XP |
| Yavaşlatma | `slow_down` | Blok düşüşünü yarıya indirir | 10s | 60 XP |
| Karıştırma | `shuffle` | Blokları yeniden düzenler | Anlık | 100 XP |
| Sütun Temizle | `clear_column` | Seçilen sütunu temizler | Anlık | 80 XP |
| Skor Artışı | `score_boost` | 2x skor çarpanı uygular | 15s | 70 XP |

### Power-up Kullanım Kuralları

```python
# Her level için power-up limitleri
max_per_level = {
    "line_bomb": 2,
    "time_freeze": 1,
    "slow_down": 2,
    "shuffle": 1,
    "clear_column": 1,
    "score_boost": 2,
}
```

### PowerUpManager API

```python
from campaign import PowerUpManager, PowerUpType

manager = PowerUpManager()

# Power-up'ları ayarla
manager.set_available_power_ups([PowerUpType.LINE_BOMB, PowerUpType.SLOW_DOWN])

# Kullanılabilirlik kontrolü
can_use, reason = manager.can_use(PowerUpType.LINE_BOMB)

# Power-up kullan
success = manager.use_power_up(PowerUpType.LINE_BOMB, game)

# Aktif efektleri güncelle
events = manager.update(dt)

# Hız/skor çarpanlarını al
speed_mod = manager.get_speed_modifier()  # 0.5 veya 1.0
score_mod = manager.get_score_modifier()  # 2.0 veya 1.0
```

---

## 💻 Teknik Uygulama Planı

### ✅ Tamamlanan Dosya Yapısı

```
src/campaign/
├── __init__.py           ✅ Public API export (82 satır)
├── campaign_mode.py      ✅ Ana CampaignMode sınıfı (735 satır)
├── campaign_ui.py        ✅ UI Efektleri ve Animasyonlar (730 satır)
├── level_data.py         ✅ 100 level dinamik tanımları (477 satır)
├── level_select.py       ✅ Level seçim ekranı (523 satır)
├── objectives.py         ✅ 7 Görev sınıfı (279 satır)
├── power_ups.py          ✅ 6 Power-up türü (483 satır)
└── special_blocks.py     ✅ 6 Özel blok türü (578 satır)
```

**TOPLAM: ~3900 satır campaign kodu**

### ✅ Entegrasyonlar

| Dosya | Değişiklik | Durum |
|-------|-----------|-------|
| `src/main.py` | CampaignMode, LevelSelect import ve action handler | ✅ |
| `src/menu.py` | Campaign menü seçeneği eklendi | ✅ |
| `src/localization.py` | 40+ campaign çevirisi eklendi | ✅ |

---

## ✅ Tamamlanan Özellikler

### Faz 1: Temel Sistem
- [x] CampaignMode sınıfı
- [x] 100 Level dinamik tanımları
- [x] 7 Görev türü (Objective)
- [x] Menü entegrasyonu

### Faz 2: Level ve Bloklar
- [x] Level seçim ekranı (5 dünya)
- [x] 6 Özel blok türü (Buz, Kilitli, Bomba, Zamanlı, Yıldız, Gökkuşağı)
- [x] 6 Power-up türü (Satır Bombası, Zaman Dondurma, vb.)

### Faz 3: UI/UX İyileştirmeleri ✅ YENİ
- [x] Power-up bar UI (glassmorphism)
- [x] Özel blok overlay'leri (neon efektler)
- [x] Level tamamlandı animasyonu (yıldız reveal)
- [x] Level başarısız animasyonu (shake efekti)
- [x] Patlama parçacık efektleri
- [x] Renk animasyonlu gökkuşağı blokları

---

## 🚀 Sonraki Adımlar (Faz 4)

### Öncelik 1: Dengeleme ve Test
- [ ] Tüm 100 level'ın oynanabilirlik testi
- [ ] Zorluk dengeleme ince ayarları
- [ ] XP/Ödül sistemi fine-tuning

### Öncelik 2: Ekstra Özellikler
- [ ] Başarımlar (Achievement) entegrasyonu
- [ ] Günlük campaign görevleri
- [ ] Seasonal events

### Öncelik 3: Polish
- [ ] Dünya geçiş efektleri (fade/slide)
- [ ] Level önizleme görselleri
- [ ] Ses efektleri entegrasyonu

---

> 📝 **Not**: Bu doküman sürekli güncellenmektedir. Son güncelleme: 2026-01-28
