# 🎮 QUADRIX (Python/Pygame)

Quadrix; Pygame tabanlı, çok modlu bir Tetris türevi oyundur.
Projede kampanya, PvP, geniş ayar menüleri, başarım sistemi ve Steam entegrasyonu bulunur.

## Dil Desteği

Desteklenen diller:
- Türkçe (TR)
- English (EN)
- Deutsch (DE)
- Français (FR)
- Español (ES)
- Italiano (IT)
- Português (PT)
- Русский (RU)
- 日本語 (JA)
- 中文 (ZH)
- 한국어 (KO)

## Hızlı Başlangıç

### Windows

```powershell
py main.py
```

Alternatif:
- `scripts/run/start_game.bat`
- `scripts/run/run_game.ps1`

### macOS / Linux

```bash
python3 main.py
```

## Gereksinimler

- Python 3.12 önerilir
- Pygame (ve diğer bağımlılıklar)

Kurulum:

```powershell
pip install -r packaging/requirements/requirements.txt
```

macOS için:

```bash
pip3 install -r packaging/requirements/requirements-macos.txt
```

## Proje Yapısı

Kısa özet:

- `src/` → ana oyun kaynak kodu
- `tests/` → pytest testleri
- `backend/` → Steam leaderboard proxy
- `docs/` → teknik dokümantasyon
- `scripts/` → çalıştırma, build ve yayın scriptleri
- `packaging/` → PyInstaller hook ve paketleme yardımcıları
- `assets/`, `music/`, `backgrounds/`, `font/` → içerik varlıkları
- `diary/` → değişiklik günlükleri
- `reports/` → raporlar ve loglar
- `tools/` → yardımcı araçlar

Detaylı yapı dokümanı: [docs/PROJECT_STRUCTURE_TR.md](docs/PROJECT_STRUCTURE_TR.md)

## Öne Çıkan Özellikler

- Tek oyunculu ve PvP modları
- Kampanya/görev sistemi
- Geniş ayar ekranları (ses, grafik, kontrol vb.)
- Başarım sistemi + Steam başarımları/stat senkronizasyonu
- Steam leaderboard entegrasyonu (SDK + proxy altyapısı)

## Test

Tüm testler:

```powershell
./scripts/test/run_tests.sh -q
```

Alternatif:

```powershell
py -m pytest -q
```

Belirli test dosyaları:

```powershell
py -m pytest tests/test_steam_achievements_sync.py -v
```

## Build / Dağıtım

- Windows/macOS spec dosyaları kök dizindedir (`tetris*.spec`)
- Build rehberi: [docs/BUILD_AND_UPLOAD.md](docs/BUILD_AND_UPLOAD.md)
- Steam operasyon dokümanları: `docs/STEAM_*`

## Dokümanlar

- Tam oyun/özellik notları: [docs/guides/README_FULL.md](docs/guides/README_FULL.md)
- Türkçe rehber (eski/sade): [docs/guides/README_TR.md](docs/guides/README_TR.md)
- macOS rehberi: [docs/guides/README_MACOS.md](docs/guides/README_MACOS.md)
- Arşiv platform notları: [docs/archive/PLATFORM_SUPPORT.md](docs/archive/PLATFORM_SUPPORT.md)

## Katkı

- Kod stilini mevcut yapıyla uyumlu tutun.
- Yeni test eklerken `tests/` klasörünü kullanın.
- Geçici analiz/script çıktıları için kök dizin yerine `tools/` ve `reports/` kullanın.

## Third-Party Assets

- PromptFont by Yukari "Shinmera" Hafner, https://shinmera.com/promptfont
- Lisans: SIL Open Font License 1.1

## Lisans

Proprietary
