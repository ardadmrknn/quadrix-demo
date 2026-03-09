# 🎮 Quadrix Full Edition - macOS Kurulum Rehberi

## 🚀 Hızlı Başlangıç

## ⛔️ Venv Politikası (ÖNEMLİ)

Bu projede **venv kesinlikle kullanılmaz**.

- `start_game.sh` ve `run.sh` çalışırken yanlışlıkla oluşmuş bir `.venv/` klasörü görürse **otomatik siler**.
- VS Code workspace ayarları sistem Python'u kullanacak şekilde ayarlanmıştır.

### 1. Python Kurulumu
macOS'ta Python genellikle önceden yüklüdür. Kontrol etmek için:
```bash
python3 --version
```

Eğer Python yüklü değilse:
- [Python.org](https://www.python.org/downloads/) üzerinden indirin
- Veya Homebrew ile: `brew install python3`

### 2. Gerekli Kütüphaneler
`start_game.sh` ilk çalıştırıldığında gerekli paketler eksikse `pygame` ve `numpy` paketlerini otomatik yüklemeyi dener (venv kullanmaz). Elle kurmak isterseniz:
```bash
pip3 install pygame numpy
```
> **Not:** Eski macOS sürümlerinde SDL kütüphanelerine ihtiyaç duyabilirsiniz:
> ```bash
> brew install sdl2 sdl2_image sdl2_mixer sdl2_ttf
> ```

### 3. Oyunu Başlatma

**Yöntem 1: Shell Script ile (Önerilen)**
```bash
# Terminal'de oyun klasörüne gidin
cd ~/Desktop/tetris_macos  # veya oyunun bulunduğu konum

# Script'leri çalıştırılabilir yapın (sadece ilk seferde)
chmod +x start_game.sh run.sh Quadrix.command

# Oyunu başlatın (ilk seferinde paketleri yükler)
./start_game.sh

# Sonraki başlatmalar için hızlı versiyon:
./run.sh
```

**Yöntem 2: Çift Tıklama ile (Finder) ⭐ En Kolay**
1. Finder'da `Quadrix.command` dosyasını bulun
2. Çift tıklayın - Terminal otomatik açılır ve oyun başlar
3. (İlk seferde: Sağ tık → "Aç" → "Aç" onayı gerekebilir)

**Yöntem 3: Direkt Python ile**
```bash
cd ~/Desktop/tetris_macos
python3 src/main.py
```

> `start_game.sh` venv oluşturmaz. Seçilen Python (tercihen `python3.12`) ile çalışır ve sadece macOS'ta gereken paketleri (`pygame`, `numpy`) `requirements-macos.txt` içinden yüklemeyi dener.

**Script tam olarak ne yapar?**
1. macOS/Linux ortamında çalıştığınızı doğrular.
2. Python 3.10+ sürümünü algılar (mümkünse `python3.12`).
3. Gerekliyse `requirements-macos.txt` içindeki hafif bağımlılıkları yükler (yalnızca `pygame` + `numpy`).
4. Oyunu `python3.12 src/main.py` (veya bulduğu en uygun Python) ile başlatır.

## 🎨 Özellikler

### Kullanıcı Profil Sistemi
- **Özel Avatar Yükleme**: PNG, JPG, JPEG destekli
- **Avatar Editör**: Kare kırpma, boyutlandırma
- **İstatistikler**: Mod bazlı performans takibi

### 8 Oyun Modu
1. **Classic** - Klasik Quadrix deneyimi
2. **Sprint** - 40 satırı en hızlı temizle
3. **Ultra** - 3 dakikada en yüksek skoru yap
4. **Zen** - Süresiz rahatlatıcı mod
5. **Quadrix 2** - 11 farklı parça (Plus, Y, Domino, BigSquare ekstra)
6. **Mystery** - Özel güçler (Lazer, Bomba, Sil, Yavaşlat, Hızlandır)
7. **Wide** - 15 blok genişliğinde tahta
8. **PvP** - 2 oyunculu rekabet modu

### 5 Görsel Tema
- **Classic** - Geleneksel renkler
- **Cyberpunk** - Neon mor/mavi tonları
- **Ocean** - Deniz temalı mavi/yeşil
- **Sunset** - Turuncu/pembe gradient
- **Forest** - Doğa yeşilleri

### Müzik Sistemi
11 farklı müzik (Crazy Frog dahil!)

## 🔧 macOS Özel Notlar

### "windows not available" Hatası
Bu hata pygame'in pencere açamaması demektir. Çözümler:

**1. Terminal Yetkisi (En yaygın sebep):**
```
System Preferences → Security & Privacy → Privacy → Screen Recording
Terminal.app'e izin verin ve Terminal'i yeniden başlatın
```

**2. XQuartz Kurulumu (Eski macOS versiyonları):**
```bash
brew install --cask xquartz
# Kurulumdan sonra sistemi yeniden başlatın
```

**3. Pygame Yeniden Kurulumu:**
```bash
pip3 uninstall pygame
pip3 install pygame --upgrade
```

### Tkinter Sorunları
Eğer avatar editörde dosya seçme penceresi açılmazsa:
```bash
# Tkinter'i yeniden yükleyin
brew install python-tk@3.11  # Python versiyonunuza göre
```

### Ses Sorunları
macOS'ta Pygame ses hatası alırsanız:
```bash
# Pygame'i yeniden yükleyin
pip3 uninstall pygame
pip3 install pygame --no-cache-dir
```

### Performans İyileştirme
macOS'ta daha iyi performans için:
1. Sistem Tercihleri → Enerji → "Grafik Geçişini Otomatik Yap" kapatın
2. Oyunu tam ekranda çalıştırın (F12)

## 🎮 Kontroller

### Temel Kontroller
- **Yön Tuşları**: Parça hareketi
- **Yukarı Ok**: Döndür
- **Aşağı Ok**: Hızlı düşür
- **Boşluk**: Hard drop (anında düşür)
- **ESC**: Menüye dön
- **P**: Duraklat

### Mouse Desteği
- Ana menüde tüm seçenekler tıklanabilir
- Avatar editöründe sürükle-bırak

### PvP Modu (2 Oyuncu)
**Oyuncu 1:**
- WASD: Hareket
- Q: Döndür
- S: Hızlı düşür

**Oyuncu 2:**
- Yön Tuşları: Hareket
- Yukarı: Döndür
- Aşağı: Hızlı düşür

## 📁 Dosya Yapısı

```
Tetris_Python_Final/
├── src/                    # Kaynak kodlar
├── music/                  # Müzik dosyaları
├── backgrounds/            # Arka plan görselleri
├── avatars/                # Varsayılan avatarlar
├── users.json              # Kullanıcı veritabanı (boş gönderiliyor)
├── achievements_*.json     # Kullanıcı başarı kayıtları (kullanıcı oluştukça)
├── highscores_*.json       # Kullanıcı skor kayıtları
├── settings.json           # Varsayılan ayarlar
├── start_game.sh           # macOS / Linux başlatıcısı
├── start_game.bat          # Windows başlatıcısı
├── requirements-macos.txt  # Hafif macOS bağımlılık listesi
└── requirements.txt        # Tam Windows geliştirme bağımlılıkları
```

## 🐛 Sorun Giderme

### "Permission Denied" Hatası
```bash
chmod +x start_game.sh
```

### "env: bash\r: No such file or directory" Hatası
Dosya Windows ortamında düzenlendiğinde satır sonları CRLF olabilir. macOS'ta düzeltmek için:
```bash
cd ~/Desktop/Tetris_Python_Final
python3 -c "from pathlib import Path; p=Path('start_game.sh'); p.write_text(p.read_text().replace('\r\n','\n'))"
```
veya Homebrew ile `dos2unix start_game.sh` komutunu kullanın.

### "Module not found: pygame"
```bash
pip3 install pygame
# veya
python3 -m pip install pygame
```

### Avatar Editör Açılmıyor
1. Tkinter kurulu mu kontrol edin:
```bash
python3 -c "import tkinter"
```

2. Hata alırsanız:
```bash
brew install python-tk
```

### Müzik Çalmıyor
1. Pygame mixer kontrolü:
```bash
python3 -c "import pygame; pygame.mixer.init()"
```

2. `music/` klasörünün varlığını kontrol edin

## 🎯 İpuçları

1. **İlk Kez Kullanım**: Kullanıcı profili oluşturun ve avatar seçin
2. **Avatar Editör**: Sağ alt köşedeki sarı tutamakla kareyi boyutlandırın
3. **Çift Tıklama**: Kullanıcı listesinde profilinize çift tıklayarak düzenleyin
4. **Başarılar**: Her modda farklı başarılar kazanabilirsiniz
5. **Temalar**: Ayarlar menüsünden tema değiştirin

## 💻 Sistem Gereksinimleri

- **İşletim Sistemi**: macOS 10.15 (Catalina) veya üzeri
- **Python**: **3.10 veya üzeri** (⚠️ Önemli!)
  - Modern Python sözdizimi kullanılıyor (`X | None`, `@dataclass(slots=True)`)
  - Python 3.9 veya altı çalışmaz
- **RAM**: Minimum 2GB
- **Disk**: ~50MB boş alan
- **Ekran**: Minimum 1024x768 çözünürlük
- **İşlemci**: Intel veya Apple Silicon (M1/M2/M3) desteklenir

### Python Sürümü Kontrolü
```bash
python3 --version
# Python 3.10.0 veya üzeri olmalı
```

### Python Güncelleme (Gerekirse)
```bash
# Homebrew ile
brew install python@3.12

# Veya python.org'dan indirin
# https://www.python.org/downloads/
```

## 🔄 Güncelleme

Yeni sürümler için:
1. Eski `users.json`, `achievements_*.json`, `highscores_*.json` dosyalarını yedekleyin
2. Yeni dosyaları klasöre kopyalayın
3. Yedeklenen dosyaları geri koyun

## 👥 İletişim

**Geliştiriciler:**
- Arda Demirkan
- Burak Yaşayan

**Versiyon**: 3.0
**Tarih**: 2025

---

🎮 **İyi Oyunlar!** 🎮
