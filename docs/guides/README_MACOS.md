# Quadrix macOS Kurulum ve Çalıştırma Rehberi

Bu belge, Quadrix'i macOS üzerinde çalıştırmak ve gerekirse geliştirme/test/build ortamını hazırlamak için kanonik macOS başvurusudur. Genel bilgi için kök [../../README.md](../../README.md) ve [README_TR.md](README_TR.md) kullanılmalıdır.

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

> İlk açılışta `start_game.sh` Python sürümü kontrolü ve bağımlılık kurulumu yapar. Sonraki açılışlarda `run.sh` daha hızlıdır.

## Venv Politikası

Bu repo macOS başlatma akışında sanal ortam kullanmaz.

- `scripts/run/start_game.sh` ve `scripts/run/run.sh` yanlışlıkla oluşmuş `.venv` klasörünü otomatik siler.
- Paketler kullanıcı hesabına `--user` ile yüklenir.
- VS Code ve script akışı sistem Python'unu hedefler.

Eğer manuel olarak venv kullanmak isterseniz `python3.12 -m venv .venv` çalışır, ancak başlatıcı script'lerin temizleyebileceğini unutmayın. Bu durumda doğrudan `python3 main.py` ile çalıştırın.

## Başlatıcı Ne Yapar?

`scripts/run/start_game.sh` şu sırayla çalışır:

1. `python3.12`, ardından `python3`, ardından `python` arar
2. Python 3.10 altı sürümleri reddeder
3. Eksikse `packaging/requirements/requirements-macos.txt` içindeki hafif bağımlılıkları `pip install --user` ile kurar
4. macOS için SDL odak, pencere ve ses değişkenlerini ayarlar
5. Oyunu `main.py` üzerinden başlatır

> Repodaki **geliştirme ve test hedefi Python 3.12'dir** (`pyproject.toml` `requires-python = ">=3.12"`). Başlatıcı, oyunun çalışması için 3.10+ sürümlere geri düşebilir; ancak test ve geliştirme yapacaksanız 3.12 kurulu olmalıdır.

## Geliştirme ve Test

Geliştirme bağımlılıkları:

```bash
python3.12 -m pip install --user -e ".[dev,build]"
```

Test:

```bash
./scripts/test/run_tests.sh -q
```

Hedefli test çalıştırma:

```bash
./scripts/test/run_tests.sh -q -k mystery
./scripts/test/run_tests.sh -q tests/test_markdown_doc_sync.py
```

Pytest doğrudan kullanmak isterseniz:

```bash
python3.12 -m pytest -q
```

## macOS .app Build

Kanonik macOS build ve Steam upload akışı:

```bash
./scripts/build/build_macos_app.sh --clean
./scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"
```

Detay rehber (generated): [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md) ve [../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md).

Steam köprüsü `.app` paketine dahil edilirken bridge artefactının `local_artifacts/bridge/` altında olması gerekir. Köprü derleme: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md).

## Sık Görülen Sorunlar

### Permission denied

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
```

### `env: bash\r: No such file or directory`

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

Hata alıyorsanız python.org kurulumunu veya Tk desteği içeren bir Python dağıtımını tercih edin. Homebrew ile tkinter genellikle ayrı paket olarak gelir; gerekirse `brew install python-tk@3.12`.

### Pencere görünür ama ilk tıklama sadece aktive ediyor

- Bu durum özellikle eski macOS paketlerinde Steam veya uygulama aktivasyon yarışıyla görülebilir.
- Güncel build'lerde başlangıç focus warmup uygulanır.
- Sorun sürüyorsa en güncel pakete geçin ve oyunu yeniden başlatın.

### Çerçevesiz fullscreen sorunları

macOS'ta `pygame.FULLSCREEN` flag'i SDL crash'ine neden olabilir. Quadrix bunun yerine borderless fullscreen kullanır. Tarihsel arka plan ve teknik detay: [../macos_borderless_fullscreen.md](../macos_borderless_fullscreen.md) (tarihsel/derin teknik notlar).

### Online PvP'den çıkışta crash

macOS'ta Online PvP sonrası uygulama kapanışında oluşabilen crash için tarihsel kök neden ve uygulanan düzeltme: [../MACOS_EXIT_CRASH_AFTER_PVP_TR.md](../MACOS_EXIT_CRASH_AFTER_PVP_TR.md).

### `pygame` veya `numpy` yüklenemiyor

Elle kurulum:

```bash
python3.12 -m pip install --user -r packaging/requirements/requirements-macos.txt
```

### macOS Co-op açılışında 30 FPS hissi / Co-op arka plan opaklığı / müzik kısık başlama

Bu üç sorun için kök neden ve uygulanan düzeltmeler tarihsel notlarda kayıtlıdır:

- [../MACOS_COOP_ACILIS_30FPS_KOK_NEDENI_TR.md](../MACOS_COOP_ACILIS_30FPS_KOK_NEDENI_TR.md)
- [../MACOS_COOP_ARKA_PLAN_OPAKLIK_KOK_NEDENI_TR.md](../MACOS_COOP_ARKA_PLAN_OPAKLIK_KOK_NEDENI_TR.md)
- [../MACOS_MUZIK_KISIK_BASLAMA_VE_PAUSE_DUCK_KOK_NEDENI_TR.md](../MACOS_MUZIK_KISIK_BASLAMA_VE_PAUSE_DUCK_KOK_NEDENI_TR.md)

## Doğrudan Çalıştırma Seçenekleri

Script kullanmak istemezseniz:

```bash
python3 main.py
```

İngilizce yedek giriş noktası gerekiyorsa:

```bash
python3 src/main_en.py
```

## Steam Köprüsü Notu

macOS `.app` build'inde Online PvP, `local_artifacts/bridge/` altındaki köprüye bağlıdır. Köprü artefacti yoksa veya kaynaktan eskiyse `scripts/build/build_macos_app.sh` köprüyü yeniden derler. Manuel derleme:

```bash
cd steamworks/steam_net_bridge
chmod +x build.sh
./build.sh
```

Detay: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md).

## İlgili Dokümanlar

- Ana proje özeti: [../../README.md](../../README.md)
- Türkçe hızlı rehber: [README_TR.md](README_TR.md)
- Geniş sistem özeti: [README_FULL.md](README_FULL.md)
- Build ve yayın: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)
- Steam playtest yayın: [../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md)
- Steam köprüsü derleme rehberi: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md)
- Online PvP mimarisi: [../ONLINE_PVP_ARCHITECTURE.md](../ONLINE_PVP_ARCHITECTURE.md)

## Lisans

Proprietary
