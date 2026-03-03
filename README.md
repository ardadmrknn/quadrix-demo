# 🎮 QUADRIX (Python/Pygame)

Quadrix; Pygame tabanlı, çok modlu bir Tetris türevi oyundur.
Projede kampanya, PvP, geniş ayar menüleri, başarım sistemi ve Steam entegrasyonu bulunur.

## Hızlı Başlangıç

### Windows

```powershell
py main.py
```

Alternatif:
- `start_game.bat`
- `run_game.ps1`

### macOS / Linux

```bash
python3 main.py
```

## Gereksinimler

- Python 3.12 önerilir
- Pygame (ve diğer bağımlılıklar)

Kurulum:

```powershell
pip install -r requirements.txt
```

macOS için:

```bash
pip3 install -r requirements-macos.txt
```

## Proje Yapısı

Kısa özet:

- `src/` → ana oyun kaynak kodu
- `tests/` → pytest testleri
- `backend/` → Steam leaderboard proxy
- `docs/` → teknik dokümantasyon
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

- Tam oyun/özellik notları: [README_FULL.md](README_FULL.md)
- Türkçe rehber (eski/sade): [README_TR.md](README_TR.md)
- Platform desteği: [PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md)

## Katkı

- Kod stilini mevcut yapıyla uyumlu tutun.
- Yeni test eklerken `tests/` klasörünü kullanın.
- Geçici analiz/script çıktıları için kök dizin yerine `tools/` ve `reports/` kullanın.
