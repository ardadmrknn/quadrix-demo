# Python Quadrix Oyunu - FULL EDITION 🎮

**Pygame** kullanılarak geliştirilmiş, tam özellikli profesyonel Quadrix oyunu.

## 🌍 Dil Desteği

Desteklenen diller: TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO

## 🌟 Özellikler

### Oynanış
- ✅ **Ghost Piece (Gölge Parça)**: Parçanın nereye düşeceğini gösterir
- ✅ **Next Piece Preview**: Sonraki gelecek parçayı önizle
- ✅ **Hold System**: Parçayı sakla ve daha sonra kullan (C tuşu)
- ✅ **Hard Drop Bonusu**: Anında düşürme için ekstra puan
- ✅ **Combo Sistemi**: Arka arkaya satır temizleyerek bonus kazan
- ✅ **Quadrix Bonusu**: 4 satır birden temizle, büyük puan kazan

### Görsel
- ✅ **Animasyonlu Satır Temizleme**: Yanıp sönen efektler
- ✅ **Partiküller**: Quadrix yaptığınızda havai fişek efekti
- ✅ **Modern UI**: Temiz ve şık arayüz
- ✅ **Yeniden Boyutlandırılabilir Pencere**: Mouse ile boyutlandır
- ✅ **Renkli Parçalar**: 7 farklı tetromino, her biri farklı renk
- ✅ **FPS Göstergesi**: Performans takibi (F tuşu)

### Ses
- ✅ **Ses Efektleri**: Hareket, döndürme, satır temizleme, Quadrix sesleri
- ✅ **Açma/Kapama**: Ayarlardan sesi kontrol et

### Skor ve İstatistik
- ✅ **High Score Sistemi**: En yüksek 10 skor JSON'a kaydedilir
- ✅ **Liderlik Tablosu**: Geçmiş skorlarını gör
- ✅ **İstatistikler**: Toplam oyun, skor, satır, Quadrix sayıları
- ✅ **Otomatik Kaydetme**: Oyun bitince skor otomatik kaydedilir

### Menü ve Ayarlar
- ✅ **Ana Menü**: Profesyonel başlangıç ekranı
- ✅ **Ayarlar**: Ses, görsel efektler, zorluk ayarları
- ✅ **Zorluk Seviyeleri**: Kolay, Normal, Zor, Uzman
- ✅ **High Scores Ekranı**: Skorları ve istatistikleri görüntüle

### Diğer
- ✅ **Tam Klavye Desteği**: Tüm kontroller ayarlanabilir
- ✅ **Duraklat Sistemi**: İstediğin zaman duraklat
- ✅ **Yeniden Başlat**: Oyun bitince R ile hızlıca başlat

---

## 📦 Kurulum

### 1. Gereksinimler
- **Python 3.12** önerilir
- İndirmek için: [Python İndir](https://www.python.org/downloads/)

### 2. Kütüphaneleri Yükle

```powershell
cd "<repo-klasor-yolu>"
pip install -r packaging/requirements/requirements.txt
```

veya tek tek:
```powershell
pip install pygame-ce numpy Pillow
```

### 3. Oyunu Başlat

```powershell
py main.py
```

macOS/Linux:
```bash
python3 main.py
```

---

## 🎮 Nasıl Oynanır

### Temel Kontroller
| Tuş | İşlev |
|-----|-------|
| **← →** | Parçayı sola/sağa hareket ettir |
| **↑** | Parçayı döndür (saat yönünde 90°) |
| **↓** | Soft drop (hızlı düşüş) |
| **Space** | Hard drop (anında düşür) + Bonus puan |
| **C** | Hold (parçayı sakla/değiştir) |
| **P** | Oyunu duraklat/devam ettir |
| **F** | FPS göstergeyi aç/kapat |
| **F12** | Tam ekran / Pencere modu |
| **ESC** | Menüye dön / Çıkış |
| **R** | Yeniden başlat (oyun bitince) |

### İleri Teknikler

#### Ghost Piece (Gölge)
- Mevcut parçanın yarı saydam gölgesi, parçanın nereye düşeceğini gösterir
- Daha hassas yerleştirme yapmanızı sağlar

#### Hold System
- **C** tuşuna basarak mevcut parçayı saklayabilirsin
- Saklanan parça ile mevcut parçayı değiştirebilirsin
- Her parça düştükten sonra tekrar kullanılabilir
- Strateji için çok önemli!

#### Combo Sistemi
- Arka arkaya satır temizlediğinde combo artar
- Her combo seviyesi ekstra puan kazandırır
- Satır temizlemeden parça düşerse combo sıfırlanır

#### Puanlama
| Eylem | Puan |
|-------|------|
| 1 Satır | 100 × Seviye |
| 2 Satır | 300 × Seviye |
| 3 Satır | 500 × Seviye |
| **4 Satır (Quadrix)** | **800 × Seviye + 200 Bonus** |
| Combo Bonusu | +(Combo-1) × 50 |
| Hard Drop | +2 puan per hücre |

---

## 🎯 Oyun Modları

### Zorluk Seviyeleri
- **Kolay**: Yavaş başlangıç (1000ms), yeni başlayanlar için
- **Normal**: Dengeli hız (800ms), standart oyun
- **Zor**: Hızlı başlangıç (500ms), deneyimli oyuncular için
- **Uzman**: Çok hızlı (300ms), profesyoneller için

Seviye arttıkça oyun hızlanır!

---

## 📊 İstatistikler

Oyun otomatik olarak şunları kaydeder:
- **Toplam Oyun Sayısı**
- **Toplam Skor**
- **Toplam Temizlenen Satır**
- **En Yüksek Seviye**
- **Toplam Quadrix Sayısı**
- **Toplam Oyun Süresi**

Tüm veriler `highscores.json` dosyasında saklanır.

---

## 💡 İpuçları ve Stratejiler

1. **Quadrix Well (Kuyu) Stratejisi**
   - En sağdaki veya soldaki sütunu boş bırak
   - I parçası ile 4 satır birden temizle
   - Maksimum puan için!

2. **Hold Sistemini Kullan**
   - I parçasını sakla, Quadrix için beklet
   - O parçası daralı boşluklar için saklanabilir

3. **Combo'yu Koru**
   - Sürekli satır temizlemeye çalış
   - Combo bonusu çok değerli

4. **Ghost Piece'i Takip Et**
   - Gölgeye bakarak tam yerleştir
   - Hard drop ile hızlıca yerleştir

5. **Düz İstifle**
   - Gereksiz boşluklar bırakma
   - Düz yüzey daha kolay yönetilir

6. **Hızlı Karar Ver**
   - Next piece'e bakarak planla
   - Seviye arttıkça hız önemli

---

## 🐛 Sorun Giderme

### "pip komutu tanınmıyor"
```powershell
python -m pip install -r packaging/requirements/requirements.txt
```

### "ModuleNotFoundError: No module named 'pygame'"
```powershell
pip install --upgrade pygame-ce
```

### "ModuleNotFoundError: No module named 'numpy'"
```powershell
pip install numpy
```

### Ses çalışmıyor
- Ayarlardan "Ses Efektleri" açık olduğundan emin olun
- Bilgisayar ses seviyesini kontrol edin

### Oyun yavaş çalışıyor
- F tuşu ile FPS'i kontrol edin
- Ayarlardan "Görsel Efektler"i kapatın
- Pencere boyutunu küçültün

### Highscores görünmüyor
- İlk oyununuzu tamamlayın
- `highscores.json` dosyası otomatik oluşturulacak

---

## 🎨 Ekran Görüntüleri

### Ana Menü
- Modern animasyonlu arka plan
- 4 ana seçenek: Oyna, High Scores, Ayarlar, Çıkış

### Oyun Ekranı
- Sol: Oyun tahtası (10×20)
- Sağ Panel:
  - Sonraki parça önizlemesi
  - Saklanan parça
  - Skor, Satır, Seviye
  - Combo ve Quadrix sayacı
  - Kontrol bilgileri

### High Score Ekranı
- Top 10 skor listesi
- Altın, gümüş, bronz renk kodları
- Genel istatistikler

### Ayarlar
- Ses efektleri (Açık/Kapalı)
- Görsel efektler (Açık/Kapalı)
- Zorluk seviyesi (4 seçenek)

---

## 📝 Dosya Yapısı

```
quadrix-main/
├── src/
│   ├── main.py              # Ana giriş noktası + menü sistemi
│   ├── game.py              # Oyun mantığı (700+ satır)
│   ├── board.py             # Oyun tahtası ve puanlama
│   ├── pieces.py            # Tetromino tanımları
│   ├── constants.py         # Sabitler ve renkler
│   ├── sound.py             # Ses yönetimi
│   ├── score_manager.py     # High score sistemi
│   └── menu.py              # Menü UI bileşenleri
├── packaging/requirements/  # Python bağımlılıkları
├── highscores.json          # Skorlar (otomatik oluşur)
└── docs/guides/README_TR.md # Bu dosya
```

---

## 🏆 Başarılar (Achievement Ideas)

Gelecek güncellemelerde eklenebilir:
- 🥇 İlk Quadrix: İlk 4 satırlık temizleme
- 🔥 Combo Master: 5x combo yap
- ⚡ Hız Şampiyonu: Seviye 20'ye ulaş
- 🎯 Mükemmel: 100 satır temizle
- 💎 Zengin: 100,000 puan kazan

---

## 📄 Lisans

Proprietary - Ayrıntı için proje sahibi lisans politikasına bakın.

---

## 🙏 Teşekkürler

Bu oyunu oynadığınız için teşekkürler! 

Eğlenceli oyunlar! 🎮✨

---

**Versiyon**: 1.0.26  
**Tarih**: 2026  
**Geliştirici**: Python & Pygame ile yapıldı ❤️
