# Quadrix Türkçe Hızlı Rehber

Bu belge, Quadrix'i ilk kez çalıştıracak veya repoda hızlıca yön bulmak isteyen kullanıcılar için Türkçe onboarding rehberidir. Yüksek seviyeli sistem özeti yerine **kurulum, çalıştırma, temel modlar ve sık görülen sorunlara** odaklanır. Mimari ya da derinlemesine teknik bilgi için sondaki [Daha Fazla Doküman](#daha-fazla-doküman) bölümünü kullanın.

> Bu rehber ana giriş noktası değildir. Repo kökündeki [../../README.md](../../README.md) projenin kanonik giriş kapısıdır; burası onun Türkçe açılış cüzdanıdır.

## Quadrix Nedir?

Quadrix; Python 3.12 ve Pygame ile geliştirilen, klasik Tetris oynanışını çok modlu bir paket etrafında sunan bir oyundur.

İçerdiği başlıca alanlar:

- Tek oyunculu klasik ve skor odaklı modlar
- Yıldız/görev tabanlı tek oyunculu **Campaign** ve yerel **Co-op Campaign**
- Yerel PvP ve yerel co-op (20×20 ortak board)
- **Mystery (Kart Ustalığı)** modu: kart kataloğu ve `card_xp`/`card_level` ödül progression hattı
- Profil, avatar, istatistik, başarı ve skor takibi
- Steam entegrasyonu, leaderboard ve Steam P2P üzerinden online PvP
- Tema, blok stili, arka plan, ses, müzik shuffle ve kontrol özelleştirmeleri

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

> macOS'a özel kurulum, Tk eksikliği, fullscreen ve crash konularında ayrıntılı rehber: [README_MACOS.md](README_MACOS.md).

### Geliştirme Ortamı

Geliştirme ve test için Python 3.12 zorunludur (`pyproject.toml`'da `requires-python = ">=3.12"`):

```bash
python3.12 -m pip install --user -e ".[dev]"
```

Test çalıştırma:

```bash
./scripts/test/run_tests.sh -q
```

Belirli bir alanı denemek için `-k` filtresi kullanılabilir:

```bash
./scripts/test/run_tests.sh -q -k mystery
./scripts/test/run_tests.sh -q tests/test_markdown_doc_sync.py
```

## Temel Kontroller

| Tuş | İşlev |
| --- | --- |
| Sol / Sağ ya da A / D | Parçayı yatay hareket ettir |
| Yukarı ya da W | Döndür |
| Aşağı ya da S | Soft drop |
| Space | Hard drop |
| C | Hold (parçayı sakla) |
| P | Duraklat / devam et |
| ESC | Menüye dön ya da çık |
| F12 | Tam ekran / pencere modu |

Notlar:

- Mod bazlı ek tuşlar (Mystery modunda kart aktivasyon kısayolları, Co-op'ta ikinci hold vs.) oyun içi rehber ekranlarında listelenir.
- Gamepad desteklenir; tuş eşlemeleri Ayarlar ekranından özelleştirilebilir.

## Mod Aileleri (Kısa Özet)

- **Classic**: standart Quadrix döngüsü, satır temizliği ve seviye ilerleyişi
- **Sprint** ve **Ultra**: süre veya satır hedefli skor koşuları
- **Zen**: baskısız serbest oynanış
- **Quadrix 2**: ekstra parçalarla genişletilmiş klasik
- **Mystery (Kart Ustalığı)**: kart-perk sinerjisi, `card_xp`/`card_level` ödül hattı, anti-farm korumalı reward queue
- **Wide / Survival / Cascade / Hardcore / Daily**: farklı kural setleriyle ekstra modlar
- **Campaign**: 100 seviyelik tek oyunculu görev/yıldız sistemi
- **Co-op** ve **Co-op Campaign**: ortak tahtada iki oyunculu deneyim
- **PvP** ve **Online PvP**: rekabet odaklı çok oyunculu akışlar (Online PvP Steam P2P üzerinde çalışır)

Mystery kart kataloğu ve XP sistemi için: [../CARD_PERK_INVENTORY_TR.md](../CARD_PERK_INVENTORY_TR.md).

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

- `python3.12` komutunun PATH içinde olduğundan emin olun.
- Homebrew ile: `brew install python@3.12`.

### macOS'ta venv kullanmak istiyorum

- Bu repo macOS başlatıcısında venv kullanmaz. `scripts/run/start_game.sh` yanlışlıkla oluşan `.venv` klasörünü otomatik siler.
- Manuel venv kurmak isterseniz `python3.12 -m venv .venv` çalışır ama başlatıcı script'inin bunu temizleyebileceğini unutmayın.

### Online PvP açılmıyor / "Steam ağ köprüsü yüklenemedi"

- Steam istemcisinin açık olduğundan ve oyun hesabının AppID için lisanslı olduğundan emin olun.
- `steam_net_bridge` köprüsü hedef Python sürümünüzle uyumlu derlenmiş olmalı; rehber: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md).

### Steam leaderboard `result=8` hatası

- Hesabın AppID için Developer Comp lisansı yok. Detaylı runbook: [../STEAM_LEADERBOARD_OPERATIONS_TR.md](../STEAM_LEADERBOARD_OPERATIONS_TR.md).

## Daha Fazla Doküman

- Ana proje özeti: [../../README.md](../../README.md)
- Geniş özellik ve sistem özeti: [README_FULL.md](README_FULL.md)
- macOS özel rehberi: [README_MACOS.md](README_MACOS.md)
- Proje yapısı: [../PROJECT_STRUCTURE_TR.md](../PROJECT_STRUCTURE_TR.md)
- Build ve dağıtım: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)
- Steam playtest yayın rehberi: [../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md)
- Online PvP mimarisi: [../ONLINE_PVP_ARCHITECTURE.md](../ONLINE_PVP_ARCHITECTURE.md)
- Online PvP akışı: [../ONLINE_PVP_FLOW_TR.md](../ONLINE_PVP_FLOW_TR.md)
- Mystery kart kataloğu: [../CARD_PERK_INVENTORY_TR.md](../CARD_PERK_INVENTORY_TR.md)

## Lisans

Proprietary
