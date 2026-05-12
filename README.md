# QUADRIX

Quadrix, Python ve Pygame ile geliştirilen çok modlu bir Tetris türevidir. Proje; klasik tek oyunculu deneyimin yanında kampanya, co-op, PvP, profil sistemi, başarım takibi, özelleştirilebilir arka planlar ve Steam entegrasyonu gibi katmanlar içerir.

## Öne Çıkanlar

- Çoklu oyun yapısı: Classic, Sprint, Ultra, Zen, Quadrix 2, Mystery, Wide, Survival, Cascade ve ek mod ekranları
- İlerleme katmanı: tek oyunculu kampanya ve yerel co-op kampanya
- Çok oyunculu içerik: yerel PvP, yerel co-op, Steam tabanlı online PvP altyapısı
- Oyuncu profilleri: avatar, skor, istatistik, başarım ve kullanıcı kayıtları
- Özelleştirme: tema, arka plan, ses, grafik ve kontrol ayarları
- Yerelleştirme: TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO

## Hızlı Başlangıç

### Windows

Oyunu doğrudan başlatmak için:

```powershell
py main.py
```

Alternatif başlatıcılar:

- `scripts/run/start_game.bat`
- `scripts/run/run_game.ps1`

### macOS / Linux

Önerilen başlatma yöntemi:

```bash
./scripts/run/start_game.sh
```

İlk kullanımda çalıştırma izni gerekirse:

```bash
chmod +x scripts/run/start_game.sh scripts/run/run.sh scripts/run/Tetris.command
```

Doğrudan Python ile başlatmak isterseniz:

```bash
python3 main.py
```

Notlar:

- Ana giriş noktası `main.py` dosyasıdır.
- İngilizce yedek giriş noktası `src/main_en.py` dosyasında bulunur.
- macOS başlatıcısı sanal ortam kullanmaz; sistem Python'u ile çalışır ve gerekirse hafif bağımlılıkları kullanıcı düzeyinde yükler.

## Geliştirme Kurulumu

Geliştirme ve test için Python 3.12 kullanılması önerilir. Proje metadatası da 3.12 hedefiyle tanımlıdır.

```bash
python3.12 -m pip install --user -e ".[dev]"
```

Build araçları da gerekiyorsa:

```bash
python3.12 -m pip install --user -e ".[dev,build]"
```

Windows tarafında eşdeğer komut:

```powershell
py -3.12 -m pip install -e ".[dev,build]"
```

## Test

Repodaki önerilen test komutu:

```bash
./scripts/test/run_tests.sh -q
```

Bu script Python 3.12 ile pytest çalıştırır ve eksik test bağımlılıklarını kullanıcı hesabına kurar.

Elle çalıştırmak isterseniz:

```bash
python3.12 -m pytest -q
```

Belirli bir test dosyası örneği:

```bash
python3.12 -m pytest tests/test_steam_achievements_sync.py -v
```

## Build ve Paketleme

- Paketleme ve yayın akışı için ana rehber: [docs/BUILD_AND_UPLOAD.md](docs/BUILD_AND_UPLOAD.md)
- PyInstaller spec dosyaları kök dizinde ve [packaging/specs](packaging/specs) altında bulunur
- Steam ağ köprüsü derleme notları: [steamworks/steam_net_bridge/README_BUILD.md](steamworks/steam_net_bridge/README_BUILD.md)

## Doküman Haritası

- Genel Türkçe hızlı rehber: [docs/guides/README_TR.md](docs/guides/README_TR.md)
- Geniş özellik ve sistem özeti: [docs/guides/README_FULL.md](docs/guides/README_FULL.md)
- macOS kurulum ve çalışma notları: [docs/guides/README_MACOS.md](docs/guides/README_MACOS.md)
- Proje yapısı özeti: [docs/PROJECT_STRUCTURE_TR.md](docs/PROJECT_STRUCTURE_TR.md)
- Online PvP mimarisi: [docs/ONLINE_PVP_ARCHITECTURE.md](docs/ONLINE_PVP_ARCHITECTURE.md)
- Steam leaderboard operasyonları: [docs/STEAM_LEADERBOARD_OPERATIONS_TR.md](docs/STEAM_LEADERBOARD_OPERATIONS_TR.md)

## Proje Yapısı

- `src/`: ana oyun kodu, modlar, UI, kampanya ve entegrasyonlar
- `tests/`: pytest tabanlı otomasyon testleri
- `backend/`: Steam leaderboard proxy servisi
- `docs/`: teknik notlar, runbook'lar ve kılavuzlar
- `scripts/`: çalıştırma, test ve build scriptleri
- `packaging/`: spec dosyaları ve paketleme yardımcıları
- `assets/`, `music/`, `backgrounds/`, `avatars/`, `font/`: oyun varlıkları
- `local_artifacts/`: yerel build çıktıları ve runtime artifact'ları

## Katkı ve Çalışma Notları

- Mevcut dosya düzenini ve isimlendirme stilini koruyun.
- Kod değişikliklerinde mümkünse ilgili testleri aynı turda çalıştırın.
- Geçici analiz çıktıları için kök dizini kirletmek yerine `reports/`, `tools/` veya `local_artifacts/` kullanın.
- Oyuna ait README dosyaları bu repoda tutulur; üçüncü parti klasörlerdeki upstream README ve lisans dosyaları ayrı değerlendirilmelidir.

## Üçüncü Parti Notu

- PromptFont by Yukari "Shinmera" Hafner: SIL Open Font License 1.1
- Steamworks SDK ve benzeri vendor içerikleri kendi lisans ve README dosyalarıyla gelir

## Lisans

Proprietary
