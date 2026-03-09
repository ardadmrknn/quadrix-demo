# Quadrix Proje Yapısı (TR)

Bu belge, proje klasör yapısını ve ana bileşenlerin sorumluluklarını özetler.

## Genel Bakış

- Ana oyun: Python + Pygame
- Kaynak kod: `src/`
- Testler: `tests/`
- Steam backend/proxy: `backend/`
- Dokümantasyon: `docs/`

## Klasörler

```text
v2/
├─ main.py                          # Ana giriş noktası (TR)
├─ src/                             # Oyun kaynak kodu
│  ├─ game.py                       # Ana oyun döngüsü
│  ├─ menu.py                       # Ana menü
│  ├─ achievements.py               # Başarım sistemi
│  ├─ steam_integration.py          # Steam SDK entegrasyonu
│  ├─ steam_leaderboards.py         # Leaderboard istemci katmanı
│  ├─ campaign/                     # Görev/Kampanya sistemi
│  └─ renderers/                    # Özel render modülleri
│
├─ tests/                           # Otomatik testler (pytest)
│
├─ backend/
│  └─ steam_leaderboard_proxy.py    # Steam leaderboard proxy servisi
│
├─ assets/                          # Oyun görselleri ve UI varlıkları
├─ music/                           # Müzikler
├─ backgrounds/                     # Arkaplanlar
├─ font/                            # Font dosyaları
├─ avatars/                         # Avatar varlıkları
│
├─ docs/                            # Teknik ve operasyonel dokümanlar
│  ├─ guides/                       # Kullanım rehberleri ve README varyantları
│  └─ archive/                      # Eski/manuel test ve referans dokümanları
├─ diary/                           # Günlük/değişiklik notları
├─ reports/                         # Üretilen raporlar/loglar
│  ├─ localization_audit/
│  └─ logs/
├─ scripts/                         # Çalıştırma, build ve yayın scriptleri
│  ├─ build/
│  └─ run/
├─ packaging/                       # Paketleme yardımcıları
│  ├─ pyinstaller/hooks/            # PyInstaller runtime hook'ları
│  ├─ requirements/                 # Paket bağımlılık listeleri
│  └─ specs/                        # PyInstaller spec dosyaları
├─ config/
│  └─ runtime/                      # Runtime ayar ve layout dosyalari
├─ local_artifacts/                 # Lokal build artifactleri
│  ├─ bridge/
│  └─ dll/
├─ data/
│  └─ legacy/                       # Eski/manuel veri artifaktlari
├─ tools/                           # Yardımcı araçlar
│  └─ maintenance/root_helpers/     # Tek-seferlik bakım scriptleri
├─ plans/                           # Plan ve roadmap belgeleri
├─ archive/                         # Arşivlenen (aktif olmayan) dosyalar
│
└─ pyproject.toml                   # Proje ve test yapılandırması
```

## Önemli Dosyalar

- `main.py`: Oyunun ana başlatıcısı.
- `src/main_en.py`: İngilizce fallback giriş noktası.
- `src/achievements.py`: Oyun içi başarımlar ve Steam eşlemesi.
- `src/steam_integration.py`: Steam init, başarımlar, statlar, leaderboard upload.
- `backend/steam_leaderboard_proxy.py`: Partner API için güvenli proxy.

## Test ve Çalıştırma

- Oyunu başlatma (Windows):
  - `py main.py`
  - veya `scripts/run/start_game.bat`
- Test çalıştırma:
  - `py -m pytest -q`
  - veya `./scripts/test/run_tests.sh -q`

## Notlar

- Aktif test dosyaları `tests/` altındadır.
- Kök dizin sade tutulur; geçici analiz/çıktı dosyaları `tools/`, `reports/` veya `archive/` altında konumlandırılır.
