# 🎮 Quadrix - Tek EXE Dağıtım Paketi

## 📦 Nasıl Kullanılır?

### Oyunu Çalıştırmak İçin:
Sadece `dist\Quadrix.exe` dosyasını çift tıklayarak çalıştırın!

### Arkadaşlarınıza Göndermek İçin:
`dist\Quadrix.exe` dosyasını paylaşmanız yeterli. Karşı tarafın Python kurmasına gerek yok!

---

## 🔧 EXE Dosyasını Yeniden Oluşturmak İçin

### Yöntem 1: Build Script (Önerilen)
```
build_exe.bat
```
dosyasını çift tıklayarak çalıştırın.

### Yöntem 2: Manuel Komut
```powershell
python -m PyInstaller packaging/specs/tetris.spec --noconfirm
```

### Yöntem 3: Sıfırdan (spec dosyası olmadan)
```powershell
pyinstaller --onefile --noconsole --name Quadrix ^
    --add-data "music;music" ^
    --add-data "backgrounds;backgrounds" ^
    --add-data "avatars;avatars" ^
    --add-data "assets/ui;assets/ui" ^
    --add-data "src/splashscreen;src/splashscreen" ^
    src/main.py
```

---

## 📂 Dosya Yapısı

```
tetris_macos/
├── build_exe.bat      # Windows build script
├── packaging/specs/   # PyInstaller yapılandırma dosyaları
├── dist/
│   └── Quadrix.exe     # ✨ Paylaşılacak oyun dosyası (82+ MB)
└── build/             # (geçici build dosyaları)
```

---

## ⚠️ Önemli Notlar

1. **İlk çalıştırma yavaş olabilir**: EXE dosyası ilk çalıştırıldığında geçici dosyaları çıkartması gerektiği için birkaç saniye bekleyebilirsiniz.

2. **Antivirus Uyarıları**: Bazı antivirüs programları PyInstaller ile oluşturulan EXE dosyalarını yanlış pozitif olarak işaretleyebilir. Bu normaldir ve güvenle görmezden gelebilirsiniz.

3. **Windows SmartScreen**: İlk çalıştırmada "Windows korunan PC'nizi korudu" uyarısı çıkabilir. "Daha fazla bilgi" → "Yine de çalıştır" seçenekleriyle devam edebilirsiniz.

4. **Minimum Gereksinimler**:
   - Windows 10/11 (64-bit)
   - 200+ MB boş disk alanı (geçici dosyalar için)
   - Ses kartı (müzik için)

---

## 🎯 Sıkıştırılmış Dağıtım İçin

EXE dosyasını daha küçük boyutta paylaşmak için ZIP/RAR ile sıkıştırabilirsiniz:

```powershell
Compress-Archive -Path "dist\Quadrix.exe" -DestinationPath "Tetris_Game.zip"
```

---

## 🐛 Sorun Giderme

### Oyun açılmıyor
- Windows Defender/Antivirus geçici olarak devre dışı bırakın
- Dosyayı sağ tık → "Yönetici olarak çalıştır" deneyin

### Ses/Müzik çalmıyor
- Ses kartı sürücülerinizi güncelleyin
- Windows ses ayarlarını kontrol edin

### Grafikler bozuk görünüyor
- Ekran kartı sürücülerini güncelleyin
- Farklı bir ekran çözünürlüğü deneyin

---

*Bu paket PyInstaller 6.16.0 ile oluşturulmuştur.*
