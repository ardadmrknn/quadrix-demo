# Quadrix macOS Kurulum ve Çalıştırma Rehberi

Bu belge, Quadrix'i macOS üzerinde çalıştırmak ve gerekirse geliştirme/test ortamını hazırlamak için güncel başvuru rehberidir.

## Hızlı Başlangıç

Homebrew kullanıyorsanız önerilen temel kurulum:

```bash
brew install python@3.12
```

Repoda ilk çalıştırma:

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
./scripts/run/start_game.sh
```

Sonraki açılışlarda daha hızlı başlangıç için:

```bash
./scripts/run/run.sh
```

Finder ile açmak isterseniz `scripts/run/Tetris.command` dosyasını çift tıklayabilirsiniz. İlk açılışta macOS güvenlik onayı isteyebilir.

## Venv Politikası

Bu repo macOS başlatma akışında sanal ortam kullanmaz.

- `scripts/run/start_game.sh` ve `scripts/run/run.sh` yanlışlıkla oluşmuş `.venv` klasörünü otomatik siler
- Paketler kullanıcı hesabına `--user` ile yüklenir
- VS Code ve script akışı sistem Python'u hedefler

## Başlatıcı Ne Yapar?

`scripts/run/start_game.sh` şu sırayla çalışır:

1. `python3.12`, ardından `python3`, ardından `python` arar
2. Python 3.10 altı sürümleri reddeder
3. Eksikse `packaging/requirements/requirements-macos.txt` içindeki hafif bağımlılıkları kurar
4. macOS için SDL odak, pencere ve ses değişkenlerini ayarlar
5. Oyunu `main.py` üzerinden başlatır

Not:

- Repodaki geliştirme ve test hedefi Python 3.12'dir
- Başlatıcı ise çalışma kolaylığı için 3.10+ sürümlere geri düşebilir

## Geliştirme ve Test

Geliştirme bağımlılıkları:

```bash
python3.12 -m pip install --user -e ".[dev,build]"
```

Test:

```bash
./scripts/test/run_tests.sh -q
```

Elle pytest çalıştırmak isterseniz:

```bash
python3.12 -m pytest -q
```

## Sık Görülen Sorunlar

### Permission denied

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
```

### env: bash\r: No such file or directory

Script CRLF satır sonlarıyla kaydedildiyse düzeltin:

```bash
python3 -c "from pathlib import Path; p=Path('scripts/run/start_game.sh'); p.write_text(p.read_text().replace('\r\n', '\n'))"
```

Alternatif olarak `dos2unix scripts/run/start_game.sh` kullanılabilir.

### Python 3.12 bulunamıyor

```bash
brew install python@3.12
```

Test scripti özellikle Python 3.12 arar. Geliştirme yapacaksanız PATH içinde göründüğünü doğrulayın:

```bash
python3.12 --version
```

### tkinter yok, dosya seçici açılmıyor

Önce doğrulayın:

```bash
python3 -c "import tkinter"
```

Hata alıyorsanız python.org kurulumunu veya Tk desteği içeren bir Python dağıtımını tercih edin.

### Pencere görünür ama ilk tıklama sadece aktive ediyor

- Bu durum özellikle eski macOS paketlerinde Steam veya uygulama aktivasyon yarışıyla görülebilir
- Güncel build'lerde başlangıç focus warmup uygulanır
- Sorun sürüyorsa en güncel pakete geçin ve oyunu yeniden başlatın

### pygame veya numpy yüklenemiyor

Elle kurulum:

```bash
python3.12 -m pip install --user -r packaging/requirements/requirements-macos.txt
```

## Doğrudan Çalıştırma Seçenekleri

Script kullanmak istemezseniz:

```bash
python3 main.py
```

İngilizce yedek giriş noktası gerekiyorsa:

```bash
python3 src/main_en.py
```

## İlgili Dokümanlar

- Ana proje özeti: [../../README.md](../../README.md)
- Türkçe hızlı rehber: [README_TR.md](README_TR.md)
- Geniş sistem özeti: [README_FULL.md](README_FULL.md)
- Build ve yayın: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)
- Steam köprüsü derleme rehberi: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md)

## Lisans

Proprietary
