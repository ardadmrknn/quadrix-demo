# QUADRIX

Quadrix, Python ve Pygame ile geliştirilen çok modlu bir Tetris türevidir. Klasik tek oyunculu deneyimin yanında kampanya, yerel ve Steam tabanlı çok oyunculu yüzeyler, profil sistemi, başarım takibi, özelleştirilebilir arka planlar, kart tabanlı Mystery modu ve Steamworks entegrasyonu içerir.

> Bu belge projenin ana giriş kapısıdır. Kurulum, geliştirme, test ve build için ihtiyaç duyacağın tüm ana yönlendirmeleri burada bulursun. Detay rehberler için sondaki [Doküman Haritası](#doküman-haritası) bölümüne bak.

## Öne Çıkanlar

- Çoklu oyun yapısı: Classic, Sprint, Ultra, Zen, Quadrix 2, Mystery, Wide, Survival, Cascade, Hardcore ve Daily modları
- Yıldız ve görev tabanlı tek oyunculu **Campaign** ile yerel **Co-op Campaign**
- Çok oyunculu içerik: yerel PvP, yerel co-op (20×20 ortak board), Steam P2P üzerinden online PvP
- Mystery (Kart Ustalığı) modu: gerçek katalogla 39 kart ID'si (31 benzersiz aile) ve `card_xp`/`card_level` tabanlı ödül progression hattı
- Oyuncu profilleri: avatar, skor, istatistik, başarım, çok kullanıcılı yerel kayıt
- Tema, blok stili, arka plan, ses, müzik shuffle ve kontrol ayarları
- 11 dil desteği: TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO

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

- Türkçe ana giriş noktası `main.py`, İngilizce yedek `src/main_en.py`.
- macOS başlatıcısı sanal ortam kullanmaz; sistem Python'u ile çalışır ve gerekirse hafif bağımlılıkları kullanıcı düzeyinde yükler.

## Geliştirme Kurulumu

Geliştirme ve test için Python 3.12 zorunludur. `pyproject.toml` `requires-python = ">=3.12"` olarak tanımlıdır.

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

Bu script Python 3.12 ile pytest çalıştırır ve eksik test bağımlılıklarını kullanıcı hesabına kurar. Belirli bir alanı çalıştırmak için:

```bash
# Mystery (Kart Ustalığı) ile ilgili tüm testler
./scripts/test/run_tests.sh -q -k mystery

# Kampanya tarafı
./scripts/test/run_tests.sh -q -k campaign

# Generated markdown senkronu
./scripts/test/run_tests.sh -q tests/test_markdown_doc_sync.py
```

Pytest doğrudan kullanmak isterseniz:

```bash
python3.12 -m pytest -q
```

## Build ve Paketleme

- Tüm build ve Steam upload akışları için kanonik rehber: [docs/BUILD_AND_UPLOAD.md](docs/BUILD_AND_UPLOAD.md) (generated)
- Steam playtest yayın akışı: [docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md) (generated)
- Steam ağ köprüsü derleme: [steamworks/steam_net_bridge/README_BUILD.md](steamworks/steam_net_bridge/README_BUILD.md)
- macOS özel build ve crash notları: [docs/guides/README_MACOS.md](docs/guides/README_MACOS.md)
- PyInstaller spec dosyaları: [packaging/specs/](packaging/specs)

> Generated rehberler `tools/sync_markdown_docs.py` tarafından kaynak script/spec/VDF dosyalarından üretilir. Doğrudan elle düzenlemeyin; gerekirse kaynak scripti güncelleyip `python3 tools/sync_markdown_docs.py` çalıştırın.

## Doküman Haritası

Aşağıdaki tablo, ihtiyacınız olduğunda doğru dokümanı bulmanızı kolaylaştırır.

| Konu | Dosya | Not |
| --- | --- | --- |
| Türkçe hızlı rehber | [docs/guides/README_TR.md](docs/guides/README_TR.md) | İlk açılış için onboarding |
| Geniş özellik ve sistem özeti | [docs/guides/README_FULL.md](docs/guides/README_FULL.md) | Yüksek seviye sistem haritası |
| macOS kurulum ve çalışma | [docs/guides/README_MACOS.md](docs/guides/README_MACOS.md) | Permission, fullscreen, troubleshooting |
| Proje yapısı | [docs/PROJECT_STRUCTURE_TR.md](docs/PROJECT_STRUCTURE_TR.md) | Klasör/modül haritası |
| Mystery kart envanteri | [docs/CARD_PERK_INVENTORY_TR.md](docs/CARD_PERK_INVENTORY_TR.md) | Katalog + `card_xp` sistemi |
| Build ve Steam upload | [docs/BUILD_AND_UPLOAD.md](docs/BUILD_AND_UPLOAD.md) | Generated |
| Steam playtest yayın | [docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md) | Generated |
| Steam köprüsü EXE/.app entegrasyonu | [docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md) | Generated |
| Online PvP mimarisi | [docs/ONLINE_PVP_ARCHITECTURE.md](docs/ONLINE_PVP_ARCHITECTURE.md) | Mimari/derinlik |
| Online PvP akışı | [docs/ONLINE_PVP_FLOW_TR.md](docs/ONLINE_PVP_FLOW_TR.md) | Akış/davranış |
| Steam leaderboard operasyonları | [docs/STEAM_LEADERBOARD_OPERATIONS_TR.md](docs/STEAM_LEADERBOARD_OPERATIONS_TR.md) | Çalışma kılavuzu |
| Steam leaderboard kurulum (mod eşleştirmesi) | [docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md](docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md) | Mod ↔ Steam adı |
| Steam başarımları + statları | [docs/STEAM_ACHIEVEMENTS_SETUP.md](docs/STEAM_ACHIEVEMENTS_SETUP.md) | 40 başarım, 17 stat |
| Stale-check kontrol listesi | [docs/STALE_CHECKLIST_TR.md](docs/STALE_CHECKLIST_TR.md) | Kod ↔ doküman audit |

## Proje Yapısı (Hızlı Bakış)

- `main.py`, `src/main_en.py`: Türkçe / İngilizce giriş noktaları
- `src/`: oyun kodu, modlar, UI, kampanya, Steam entegrasyonu
- `src/campaign/`: kampanya ve co-op kampanya sistemi
- `src/game_modes_extra.py`: Mystery (Kart Ustalığı) modu ve kart kataloğu
- `tests/`: pytest tabanlı otomasyon testleri
- `backend/`: Steam leaderboard proxy servisi
- `docs/`: kanonik rehberler, generated dokümanlar, tarihsel notlar
- `scripts/`: çalıştırma, test ve build scriptleri
- `packaging/`: spec dosyaları ve paketleme yardımcıları
- `steamworks/`: Steamworks SDK ve native köprü kaynakları
- `assets/`, `music/`, `backgrounds/`, `avatars/`, `font/`, `apple_emojis/`: oyun varlıkları
- `local_artifacts/`: yerel build çıktıları (köprü `.pyd`/`.so` dahil)
- `config/runtime/`: `settings.txt`, `menu_layout_runtime.json`, `steam_appid.txt`
- `tools/`: yardımcı bakım araçları (örn. `sync_markdown_docs.py`)
- `plans/`, `reports/`, `todo/`, `docs/archive/`: tarihsel kayıtlar

Daha ayrıntılı yapı için: [docs/PROJECT_STRUCTURE_TR.md](docs/PROJECT_STRUCTURE_TR.md).

## Katkı ve Çalışma Notları

- Mevcut dosya düzenini ve isimlendirme stilini koruyun.
- Kod değişikliklerinde mümkünse ilgili testleri aynı turda çalıştırın.
- Geçici analiz çıktıları için kök dizini kirletmek yerine `reports/`, `tools/` veya `local_artifacts/` kullanın.
- Generated dokümanları elle düzenlemeyin; `tools/sync_markdown_docs.py` üzerinden üretin.
- Tarihsel plan/rapor/arşiv dosyaları (`plans/`, `reports/`, `todo/`, `docs/archive/`) tarihsel kayıt amaçlıdır; kanonik rehberlere atılan referansları kanıt için kullanmayın.

## Üçüncü Parti Notu

- PromptFont by Yukari "Shinmera" Hafner: SIL Open Font License 1.1 (`assets/gamepad_icon/promptfont/`)
- Steamworks SDK ve benzeri vendor içerikleri kendi lisans ve README dosyalarıyla gelir (`steamworks/sdk/`)

## Lisans

Proprietary
