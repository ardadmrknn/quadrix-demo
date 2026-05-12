# Quadrix Türkçe Hızlı Rehber

Bu belge, Quadrix'i ilk kez çalıştıracak veya repoda hızlıca yön bulmak isteyen kullanıcılar için kısa başlangıç kılavuzudur.

## Quadrix Nedir?

Quadrix; Python ve Pygame ile geliştirilen, klasik Tetris oynanışını daha geniş bir sistem paketiyle sunan çok modlu bir oyundur.

İçerdiği başlıca alanlar:

- Tek oyunculu klasik ve skor odaklı modlar
- Tek oyunculu kampanya ve yerel co-op kampanya
- Yerel PvP ve yerel co-op oyun akışları
- Profil, avatar, istatistik, başarı ve skor takibi
- Steam entegrasyonu, leaderboard ve online PvP altyapısı
- Tema, arka plan, ses, grafik ve kontrol özelleştirmeleri

## Kurulum ve Çalıştırma

### Windows

En kısa başlatma komutu:

```powershell
py main.py
```

Alternatif başlatıcılar:

- `scripts/run/start_game.bat`
- `scripts/run/run_game.ps1`

### macOS / Linux

Önerilen komut:

```bash
./scripts/run/start_game.sh
```

İlk kullanımda çalıştırma izni vermek gerekebilir:

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
```

Doğrudan Python ile de açabilirsiniz:

```bash
python3 main.py
```

### Geliştirme Ortamı

Geliştirme ve test için Python 3.12 önerilir:

```bash
python3.12 -m pip install --user -e ".[dev]"
```

Test çalıştırma:

```bash
./scripts/test/run_tests.sh -q
```

## Temel Kontroller

| Tuş | İşlev |
| --- | --- |
| Sol / Sağ | Parçayı yatay hareket ettir |
| Yukarı | Döndür |
| Aşağı | Soft drop |
| Space | Hard drop |
| C | Hold sistemi olan modlarda parçayı sakla |
| P | Duraklat / devam et |
| ESC | Menüye dön veya çık |
| F12 | Tam ekran / pencere modu |

Notlar:

- Kontrollerin bir kısmı modlara göre değişebilir.
- Oyun gamepad desteği ve ayar ekranından kontrol özelleştirmesi içerir.

## Mod Aileleri

- Classic: standart Quadrix döngüsü
- Sprint ve Ultra: süre veya satır hedefli skor koşuları
- Zen: baskısız serbest oynanış
- Quadrix 2 ve Mystery: yeni parça veya yetenek katmanları olan deneysel modlar
- Wide, Survival, Cascade, Hardcore ve Daily: farklı kural setleriyle ekstra modlar
- Campaign: görev ve yıldız sistemiyle tek oyunculu ilerleme
- Co-op ve Co-op Campaign: ortak tahtada iki oyunculu deneyim
- PvP ve Online PvP: rekabet odaklı çok oyunculu akışlar

## Sık Görülen Sorunlar

### pygame veya diğer bağımlılıklar bulunamıyor

```bash
python3.12 -m pip install --user -e ".[dev]"
```

Windows için:

```powershell
py -3.12 -m pip install -e ".[dev]"
```

### macOS'ta script çalışmıyor

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
```

### Test scripti Python 3.12 bulamıyor

- `python3.12` komutunun PATH içinde olduğundan emin olun
- Homebrew kullanıyorsanız gerekirse `brew install python@3.12` çalıştırın

### macOS'ta venv kullanmak istiyorum

- Bu repo macOS başlatıcısında venv kullanmaz
- `scripts/run/start_game.sh` yanlışlıkla oluşan `.venv` klasörünü otomatik siler

## Daha Fazla Doküman

- Ana proje özeti: [../../README.md](../../README.md)
- Geniş özellik ve sistem özeti: [README_FULL.md](README_FULL.md)
- macOS özel rehberi: [README_MACOS.md](README_MACOS.md)
- Proje yapısı: [../PROJECT_STRUCTURE_TR.md](../PROJECT_STRUCTURE_TR.md)
- Build ve dağıtım: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)

## Lisans

Proprietary
