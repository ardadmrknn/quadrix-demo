# 🖥️ Platform Uyumluluk Notları

## ✅ Desteklenen Platformlar

### Windows (Tam Destek)
- ✅ Windows 10/11
- ✅ Python 3.8+
- ✅ Pygame 2.0+
- ✅ Tam özellik desteği

**Başlatma:**
- `OYUNU_BASLAT.bat` (çift tıklama)
- Veya: `python src/main.py`

### macOS (Tam Destek)
- ✅ macOS 10.13+
- ✅ Python 3.8+
- ✅ Pygame 2.0+
- ✅ Tam özellik desteği

**Başlatma:**
```bash
chmod +x oyunu_baslat.sh
./oyunu_baslat.sh
```

**Notlar:**
- Tkinter için `brew install python-tk` gerekebilir
- Pygame ses için `pip3 install pygame --no-cache-dir`

### Linux (Tam Destek)
- ✅ Ubuntu 20.04+
- ✅ Debian 10+
- ✅ Fedora 33+
- ✅ Python 3.8+
- ✅ Pygame 2.0+

**Başlatma:**
```bash
chmod +x oyunu_baslat.sh
./oyunu_baslat.sh
```

## 🔧 Platform-Spesifik Özellikler

### Dosya Yolları
- ✅ Cross-platform: `os.path` kullanımı
- ✅ Otomatik klasör oluşturma
- ✅ Relatif yol desteği

### Ses Sistemi
- ✅ Pygame mixer cross-platform
- ✅ Otomatik fallback (ses yoksa devam eder)
- ✅ 22050 Hz evrensel uyumluluk

### Avatar Editör
- ✅ Tkinter dosya dialogu (Windows/macOS/Linux)
- ✅ Otomatik pencere gizleme
- ✅ Exception handling
- ✅ PNG, JPG, JPEG, BMP, GIF desteği

### Kullanıcı Verileri
- ✅ JSON formatı (evrensel)
- ✅ UTF-8 encoding
- ✅ Platform-independent dosya sistemi

## 🧪 Test Etme

### Windows
```cmd
python src/main.py
```

### macOS/Linux
```bash
# Test scripti
python3 test_macos.py

# Oyunu başlat
./oyunu_baslat.sh
```

## 📝 Bilinen Sorunlar ve Çözümleri

### macOS

**Sorun 1: "pygame.error: windows not available"**
```
Sebep: Terminal.app'in ekran kayıt yetkisi yok
Çözüm: System Preferences → Security & Privacy → Screen Recording
       Terminal.app'i ekleyin ve Terminal'i yeniden başlatın
```

**Sorun 2: Tkinter bulunamıyor**
```bash
# Çözüm
brew install python-tk@3.11  # Versiyonunuza göre
```

**Sorun 3: Pygame ses hatası**
```bash
# Çözüm
pip3 uninstall pygame
pip3 install pygame --no-cache-dir
```

**Sorun 4: "Permission Denied" (.sh dosyası)**
```bash
# Çözüm
chmod +x oyunu_baslat.sh
```

**Sorun 5: HWSURFACE bayrağı desteklenmiyor**
```
Sebep: macOS donanım yüzeyi modunu desteklemez
Çözüm: Kod otomatik olarak platform algılayıp uyumlu mod kullanır
       (main.py içinde platform.system() kontrolü var)
```

### Linux

**Sorun 1: Pygame kurulumu başarısız**
```bash
# Ubuntu/Debian
sudo apt-get install python3-pygame

# Fedora
sudo dnf install python3-pygame
```

**Sorun 2: Ses çıkmıyor**
```bash
# PulseAudio kontrolü
pulseaudio --check
```

### Windows

**Sorun 1: Python bulunamadı**
- Python'u PATH'e ekleyin
- Veya Microsoft Store'dan Python yükleyin

**Sorun 2: Pygame yükleme hatası**
```cmd
python -m pip install --upgrade pip
pip install pygame
```

## 🎯 Performans İpuçları

### Tüm Platformlar
- 1920x1080 veya daha düşük çözünürlük önerilir
- Tema: Classic en performanslı
- Parçacık efektleri ayardan kapatılabilir

### macOS Özel
- Grafik geçişini devre dışı bırakın (daha iyi FPS)
- Tam ekran modu (F12) önerilir

### Linux Özel
- Nvidia kullanıcıları: Proprietary driver kullanın
- X11 yerine Wayland daha iyi performans verebilir

## 📦 Bağımlılıklar

### Zorunlu
- Python 3.8+
- Pygame 2.0+

### Opsiyonel
- Tkinter (avatar editör için)
- NumPy (ses efektleri için - pygame ile gelir)

### Yükleme
```bash
# Tüm bağımlılıklar
pip3 install -r requirements.txt

# Sadece pygame
pip3 install pygame
```

## 🔄 Versiyon Geçmişi

### v3.0 (Mevcut)
- ✅ Windows tam destek
- ✅ macOS tam destek
- ✅ Linux tam destek
- ✅ Kullanıcı profil sistemi
- ✅ Avatar editör
- ✅ 8 oyun modu
- ✅ 5 tema

### v2.6
- Windows öncelikli
- Linux kısmi destek
- macOS test edilmemiş

## 🌐 Uluslararasılaşma

### Karakter Desteği
- ✅ UTF-8 tüm metinler
- ✅ Türkçe karakter desteği
- ✅ Emoji desteği

### Dosya Adları
- ✅ ASCII-uyumlu kullanıcı adları
- ✅ Unicode bio metinleri
- ✅ Platform-independent dosya isimlendirme

## 🔐 Güvenlik

### Dosya İzinleri
- JSON dosyaları: 644 (rw-r--r--)
- Script dosyaları: 755 (rwxr-xr-x)
- Avatar görselleri: 644 (rw-r--r--)

### Veri Güvenliği
- Yerel veri depolama
- Ağ bağlantısı yok
- Hassas veri yok

## 📊 Test Durumu

| Platform | Python 3.8 | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 |
|----------|-----------|-----------|------------|------------|------------|
| Windows 10 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Windows 11 | ✅ | ✅ | ✅ | ✅ | ✅ |
| macOS 11 | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| macOS 12+ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ubuntu 20.04 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ubuntu 22.04 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Debian 11 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fedora 38 | ✅ | ✅ | ✅ | ✅ | ✅ |

✅ = Tam çalışıyor
⚠️ = Küçük sorunlar olabilir
❌ = Test edilmedi

## 🆘 Destek

Sorun yaşıyorsanız:

1. **Test scripti çalıştırın:**
   ```bash
   python3 test_macos.py
   ```

2. **Python ve Pygame versiyonlarını kontrol edin:**
   ```bash
   python3 --version
   python3 -c "import pygame; print(pygame.version.ver)"
   ```

3. **Terminal'den direkt çalıştırın:**
   ```bash
   cd oyun/klasoru
   python3 src/main.py
   ```

4. **Hata mesajlarını kaydedin ve geliştiricilere bildirin**

---

**Son Güncelleme:** 2025
**Platform Desteği:** Windows, macOS, Linux
