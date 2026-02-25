# Python Quadrix Oyunu

Pygame kullanılarak geliştirilmiş klasik Quadrix oyunu.

## Kurulum Adımları

### 1. Python Kurulumu
- Python 3.8 veya üstü yüklü olmalı
- İndirmek için: [Python İndir](https://www.python.org/downloads/)
- Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin

### 2. Gerekli Kütüphaneyi Yükleyin

PowerShell veya komut satırında proje klasörüne gidin:
```powershell
cd "c:\Users\arda demirkan\Desktop\tetris\tetris-game"
```

Pygame kütüphanesini yükleyin:
```powershell
pip install -r requirements.txt
```

veya doğrudan:
```powershell
pip install pygame
```

## Oyunu Başlatma

```powershell
python src/main.py
```

## Nasıl Oynanır

### Kontroller
- **Sol Ok (←)**: Parçayı sola hareket ettir
- **Sağ Ok (→)**: Parçayı sağa hareket ettir
- **Aşağı Ok (↓)**: Parçayı hızlı düşür (soft drop)
- **Yukarı Ok (↑)**: Parçayı döndür
- **Boşluk (Space)**: Anında düşür (hard drop)
- **P**: Oyunu duraklat/devam ettir
- **ESC**: Oyundan çık
- **R**: Yeniden Başlat (oyun bitince)
- **F**: FPS göstergesi (aç/kapat)
- **F12**: Tam ekran / Pencere modu

### Oyun Kuralları
1. Üstten düşen Quadrix parçalarını kontrol edin
2. Parçaları döndürüp yerleştirerek yatay satırlar oluşturun
3. Tam dolu satırlar otomatik olarak temizlenir ve puan kazanırsınız
4. Parçalar ekranın üstüne kadar birikirse oyun biter

### Puanlama Sistemi
- **1 satır temizleme**: 100 puan
- **2 satır temizleme**: 300 puan
- **3 satır temizleme**: 500 puan
- **4 satır temizleme (Quadrix)**: 800 puan

## Quadrix Parçaları

Oyunda 7 farklı Tetromino parçası vardır:
- **I**: Düz çubuk (Mavi)
- **O**: Kare (Sarı)
- **T**: T şekli (Mor)
- **S**: S şekli (Yeşil)
- **Z**: Z şekli (Kırmızı)
- **J**: J şekli (Mavi)
- **L**: L şekli (Turuncu)

## Sorun Giderme

### "pip" komutu tanınmıyor hatası
```powershell
python -m pip install pygame
```

### ModuleNotFoundError: No module named 'pygame'
```powershell
pip install --upgrade pygame
```

### Oyun açılmıyor
- Python'un doğru kurulu olduğundan emin olun: `python --version`
- Pygame'in yüklü olduğunu kontrol edin: `pip list | Select-String pygame`

## İpuçları

1. **Quadrix Well Stratejisi**: Bir sütunu boş bırakıp I parçasıyla 4 satır birden temizleyin
2. **Düzenli İstifleyin**: Gereksiz boşluklar bırakmayın
3. **Hızlı Düşüş**: Aşağı ok ile hızlıca yerleştirin
4. **Döndürme**: Dar alanlara sığdırmak için parçaları döndürün

## Lisans

MIT License - Açık kaynak, özgürce kullanabilirsiniz.
