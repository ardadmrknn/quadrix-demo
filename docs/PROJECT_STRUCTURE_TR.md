# Quadrix Proje Yapısı (TR)

Bu belge, repo köküne giren bir geliştiricinin hızlıca yön bulması için klasör yapısını ve ana bileşenlerin sorumluluklarını özetler. Detaylı sistem özeti için [guides/README_FULL.md](guides/README_FULL.md), kurulum/çalıştırma için kök dizindeki [README.md](../README.md) tercih edilmelidir.

> Bu belge **klasör/modül haritasıdır**, kurulum rehberi veya runbook değildir. Komutlar yalnızca yön bulmayı kolaylaştırmak için verilmiştir; build veya leaderboard runbook'u için kanonik dokümanlara gidin.

## Genel Bakış

- Ana oyun: Python 3.12 + Pygame
- Ana giriş noktası: `main.py` (Türkçe)
- İngilizce yedek giriş noktası: `src/main_en.py`
- Kaynak kod: `src/`
- Testler: `tests/`
- Steam backend/proxy: `backend/`
- Dokümantasyon: `docs/`

## Klasörler

```text
quadrix/
├─ main.py                          # Ana giriş noktası (TR)
├─ pyproject.toml                   # Paket ve test yapılandırması (Python 3.12 hedefi)
├─ src/                             # Oyun kaynak kodu
│  ├─ game.py                       # Tek oyunculu ana oyun döngüsü
│  ├─ board.py, pieces.py           # Tahta ve parça mantığı
│  ├─ pvp_game.py                   # Yerel PvP akışı
│  ├─ coop_game.py, coop_board.py   # Yerel co-op (20×20 ortak board)
│  ├─ game_modes.py,                # Klasik mod ailesi
│  │  game_modes_advanced.py,
│  │  game_modes_extra.py           # Mystery, Wide, Cascade vb.
│  ├─ menu.py, extras_menu.py,      # Ana menü ve mod kart ekranları
│  │  guide_screen.py
│  ├─ settings_screen_tabbed.py,    # Ayarlar ve grafik menüleri
│  │  graphics_menu.py
│  ├─ ui_components.py, ui_theme.py # Ortak UI bileşenleri ve tema sistemi
│  ├─ retro_style.py                # `get_font()`, `draw_glass_panel()` vb.
│  ├─ campaign/                     # Kampanya ve co-op kampanya sistemi
│  │  ├─ campaign_mode.py           # In-game loop, görev ve yıldız takibi
│  │  ├─ level_select.py            # Seviye seçim ekranı
│  │  ├─ level_data.py              # 100 seviyelik konfigürasyon
│  │  ├─ objectives.py              # Görev türleri
│  │  ├─ power_ups.py               # Power-up sistemi
│  │  ├─ special_blocks.py          # Özel blok davranışları
│  │  ├─ campaign_ui.py             # Kampanya UI efektleri
│  │  ├─ coop_campaign_mode.py      # Co-op kampanya akışı
│  │  ├─ coop_level_select.py       # Co-op seviye seçim
│  │  ├─ coop_level_data.py         # 20 seviye co-op konfigürasyonu
│  │  └─ coop_objectives.py         # Co-op görev türleri
│  ├─ renderers/                    # Özel render modülleri (jelly vb.)
│  ├─ achievements.py               # Başarım sistemi (kampanya yıldız başarımları dahil)
│  ├─ steam_integration.py          # Steam SDK entegrasyonu
│  ├─ steam_leaderboards.py         # Leaderboard istemci katmanı
│  ├─ user_manager.py,              # Profil, avatar, skor ve istatistik
│  │  user_screens.py,
│  │  avatar_editor.py
│  ├─ score_manager.py              # Skor takibi
│  ├─ sound.py                      # Ses ve müzik (shuffle desteği dahil)
│  ├─ localization.py               # `t()` fonksiyonu ve çeviri tabloları
│  ├─ ui_language_profile.py        # CJK font desteği
│  ├─ gamepad_manager.py            # Gamepad girişi
│  ├─ platform_utils.py             # Platform yardımcıları
│  ├─ asset_manager.py              # Asset yükleme
│  ├─ data_paths.py                 # Kullanıcı veri ve config yolları
│  ├─ settings_manager.py           # Ayar okuma/yazma katmanı
│  └─ version.py, version_base.py   # Sürüm bilgisi
│
├─ tests/                           # Pytest tabanlı otomasyon testleri
│
├─ backend/
│  └─ steam_leaderboard_proxy.py    # Partner API güvenli proxy servisi
│
├─ assets/                          # UI, kart, ikon, efekt görselleri
│  ├─ ui/mode_icons/README.md       # Mod ikonları için beklenen dosya adları
│  └─ gamepad_icon/promptfont/      # PromptFont (üçüncü parti, OFL)
├─ backgrounds/                     # Kullanıcının değiştirebileceği arka planlar
│  └─ README.md                     # Desteklenen dosya adları ve fallback sırası
├─ music/                           # Müzikler
├─ avatars/                         # Avatar varlıkları
├─ font/                            # Font dosyaları
├─ apple_emojis/                    # Emoji arşivi (build'e dahil DEĞİL; assets/ui/emoji/ üzerinden kopya kullanılır)
├─ steamworks/                      # Steamworks SDK ve native köprü kaynakları
│  ├─ sdk/                          # Steamworks SDK (vendor)
│  └─ steam_net_bridge/             # Pybind11 native köprü
│     └─ README_BUILD.md            # Köprü derleme rehberi
│
├─ docs/                            # Teknik notlar, runbook'lar ve kılavuzlar
│  ├─ guides/                       # README_TR.md, README_FULL.md, README_MACOS.md
│  ├─ archive/                      # Eski/manuel test ve geçmiş referans dokümanları
│  └─ steam_icin/                   # Steam mağaza odaklı yazılı içerik
├─ plans/                           # Tarihsel plan ve roadmap belgeleri
├─ reports/                         # Tarihsel rapor ve audit çıktıları
├─ todo/                            # Açık iş listeleri
├─ diary/                           # Günlük geliştirme notları
├─ scripts/                         # Çalıştırma, test ve build scriptleri
│  ├─ build/                        # `build_macos_app.sh`, Steam upload helper'ları
│  ├─ run/                          # `start_game.sh`, `run.sh`, `Tetris.command` vb.
│  └─ test/                         # `run_tests.sh`
├─ packaging/                       # Paketleme yardımcıları
│  ├─ pyinstaller/hooks/            # PyInstaller runtime hook'ları
│  ├─ requirements/                 # Paket bağımlılık listeleri
│  └─ specs/                        # PyInstaller spec dosyaları
├─ config/
│  └─ runtime/                      # Runtime ayar ve layout dosyaları
│                                    # (`settings.txt`, `menu_layout_runtime.json`,
│                                    # `steam_appid.txt`)
├─ local_artifacts/                 # Yerel build artifact'ları
│  ├─ bridge/                       # Derlenmiş Steam köprüsü
├─ dll/                             # Native DLL/dylib yüzeyi
├─ data/
│  └─ legacy/                       # Eski/manuel veri dosyaları
├─ tools/                           # Yardımcı bakım araçları
│  └─ sync_markdown_docs.py         # Generated markdown dokümanlarını üretir
├─ archive/                         # Arşivlenmiş (aktif olmayan) dosyalar
└─ .github/
   └─ workflows/ci.yml              # GitHub Actions: test ve lint
```

## Önemli Dosyalar

- `main.py`: Türkçe ana giriş noktası.
- `src/main_en.py`: İngilizce yedek giriş noktası.
- `src/game.py`: Tek oyunculu ana oyun döngüsü.
- `src/pvp_game.py`, `src/coop_game.py`: Yerel rekabet ve kooperatif akışları.
- `src/campaign/campaign_mode.py`: Kampanya ana döngüsü; başarım tetikleme `_save_progress()` sonunda yapılır.
- `src/game_modes_extra.py`: Mystery (Kart Ustalığı) modu ve kart kataloğu (`MysteryCardManager._build_catalog`).
- `src/achievements.py`: Oyun içi başarımlar ve Steam eşlemesi.
- `src/steam_integration.py`: Steam init, başarımlar, statlar, leaderboard upload.
- `backend/steam_leaderboard_proxy.py`: Partner API için güvenli proxy.
- `tools/sync_markdown_docs.py`: `docs/BUILD_AND_UPLOAD.md`, `docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md` ve `docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md` dosyalarını üretir.

## Test ve Çalıştırma

Önerilen test komutu:

```bash
./scripts/test/run_tests.sh -q
```

Pytest doğrudan kullanmak isterseniz:

```bash
python3.12 -m pytest -q
```

Oyunu başlatma:

- Windows: `py main.py` veya `scripts/run/start_game.bat`
- macOS / Linux: `./scripts/run/start_game.sh` veya `python3 main.py`

## Doküman Haritası

- Hızlı başlangıç: [../README.md](../README.md)
- Türkçe rehber: [guides/README_TR.md](guides/README_TR.md)
- Geniş özellik özeti: [guides/README_FULL.md](guides/README_FULL.md)
- macOS rehberi: [guides/README_MACOS.md](guides/README_MACOS.md)
- Build ve yayın: [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md)
- Steam playtest yayın rehberi: [STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](STEAM_PLAYTEST_YAYIN_REHBERI_TR.md)
- Steam köprüsü derleme: [../steamworks/steam_net_bridge/README_BUILD.md](../steamworks/steam_net_bridge/README_BUILD.md)
- Mystery kart envanteri: [CARD_PERK_INVENTORY_TR.md](CARD_PERK_INVENTORY_TR.md)
- Online PvP mimarisi: [ONLINE_PVP_ARCHITECTURE.md](ONLINE_PVP_ARCHITECTURE.md)
- Steam leaderboard operasyonları: [STEAM_LEADERBOARD_OPERATIONS_TR.md](STEAM_LEADERBOARD_OPERATIONS_TR.md)

## Notlar

- Aktif test dosyaları `tests/` altındadır.
- Kök dizin sade tutulur; geçici analiz/çıktı dosyaları `tools/`, `reports/` veya `local_artifacts/` altına yerleştirilir.
- `docs/archive/`, `plans/`, `reports/` ve `todo/` altındaki dosyalar tarihsel kayıt niteliğindedir; güncel kanonik rehberler kök `README.md` ve `docs/guides/` altındadır.
