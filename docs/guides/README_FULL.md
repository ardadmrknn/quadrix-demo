# Quadrix Özellik ve Sistem Özeti

Bu belge, projenin ürün kapsamını ve ana teknik yüzeylerini tek yerde özetler. Yeni gelen bir geliştiricinin "ne nerede, hangi katman ne yapıyor" sorularını üst seviyede cevaplaması için tasarlanmıştır.

> Hızlı kurulum için kök [../../README.md](../../README.md), platform ayrıntıları için [README_MACOS.md](README_MACOS.md), klasör/modül haritası için [../PROJECT_STRUCTURE_TR.md](../PROJECT_STRUCTURE_TR.md) kullanın. Bu doküman bir özet katmandır; alt sistemlerin operasyonel detayları kanonik runbook'larındadır.

## Oyun Paketi

### Ana oynanış katmanı

- Klasik tetromino döngüsü, skor, kombo ve seviye ilerleyişi (`src/game.py`, `src/board.py`, `src/pieces.py`)
- Ghost piece, next preview, hold, hard drop ve back-to-back Quadrix bonusları
- Farklı hız, genişlik veya kural kümeleriyle çalışan ekstra modlar (`src/game_modes.py`, `src/game_modes_advanced.py`, `src/game_modes_extra.py`)

### Mod ailesi

- **Classic, Sprint, Ultra, Zen** — temel skor ve süre odaklı modlar
- **Quadrix 2, Mystery, Wide, Survival, Cascade, Hardcore, Daily** — genişletilmiş kural setleri
- **Mystery (Kart Ustalığı)**: 39 ID'lik (31 benzersiz aile) gerçek kart kataloğu + `card_xp` / `card_level` ödül progression hattı (board.level'den bağımsız), anti-farm kuralı, taşmalı reward queue
- **Campaign**: 100 seviyelik tek oyunculu görev/yıldız sistemi
- **Co-op** ve **Co-op Campaign**: yerel ortak board (20×20) ve özel görev tipleri
- **Local PvP** ve **Online PvP**: 1v1 rekabet; Online PvP Steam P2P (ISteamNetworkingMessages) üzerinde çalışır

### Oyuncu sistemleri

- Kullanıcı profilleri ve avatar yönetimi (`src/user_manager.py`, `src/user_screens.py`, `src/avatar_editor.py`)
- Mod bazlı skor, istatistik ve kullanıcı kayıtları (`src/score_manager.py`)
- Başarım sistemi ve Steam başarımları/stat eşlemesi (`src/achievements.py`, `src/steam_integration.py`)
- Steam leaderboard ve backend proxy desteği (`src/steam_leaderboards.py`, `backend/steam_leaderboard_proxy.py`)

### Sunum ve özelleştirme

- Tema, blok stili ve arka plan özelleştirmeleri (`src/themes.py`, `src/block_styles.py`, `src/background.py`)
- Dashboard tabanlı ana menü ve rehber ekranları (`src/menu.py`, `src/extras_menu.py`, `src/guide_screen.py`)
- Ses ve müzik sistemi, oynatma listesi ve shuffle desteği (`src/sound.py`)
- 11 dil profili ve CJK font desteği (`src/localization.py`, `src/ui_language_profile.py`)

## Ana Teknik Yüzeyler

| Sorumluluk | Dosya |
| --- | --- |
| Türkçe ana giriş noktası | [../../main.py](../../main.py) |
| İngilizce yedek giriş noktası | [../../src/main_en.py](../../src/main_en.py) |
| Tek oyunculu ana döngü | [../../src/game.py](../../src/game.py) |
| Yerel PvP | [../../src/pvp_game.py](../../src/pvp_game.py) |
| Yerel co-op (ortak board) | [../../src/coop_game.py](../../src/coop_game.py), [../../src/coop_board.py](../../src/coop_board.py) |
| Online PvP | [../../src/online_pvp_game.py](../../src/online_pvp_game.py) |
| Steam networking (Python) | [../../src/steam_networking.py](../../src/steam_networking.py) |
| Steam SDK entegrasyonu | [../../src/steam_integration.py](../../src/steam_integration.py) |
| Steam leaderboard istemcisi | [../../src/steam_leaderboards.py](../../src/steam_leaderboards.py) |
| Backend leaderboard proxy | [../../backend/steam_leaderboard_proxy.py](../../backend/steam_leaderboard_proxy.py) |
| Native Steam köprüsü (C++) | [../../steamworks/steam_net_bridge/](../../steamworks/steam_net_bridge/) |
| Ana menü / dashboard | [../../src/menu.py](../../src/menu.py) |
| Mod kart ekranı | [../../src/extras_menu.py](../../src/extras_menu.py) |
| Mystery (Kart Ustalığı) modu | [../../src/game_modes_extra.py](../../src/game_modes_extra.py) |
| Kampanya sistemi | [../../src/campaign/](../../src/campaign/) |
| Profil ve avatar | [../../src/user_manager.py](../../src/user_manager.py), [../../src/avatar_editor.py](../../src/avatar_editor.py) |
| Başarımlar | [../../src/achievements.py](../../src/achievements.py) |
| Lokalizasyon | [../../src/localization.py](../../src/localization.py) |
| Ses ve müzik | [../../src/sound.py](../../src/sound.py) |
| UI tema/font sistemi | [../../src/ui_theme.py](../../src/ui_theme.py), [../../src/retro_style.py](../../src/retro_style.py) |
| Generated doküman üreticisi | [../../tools/sync_markdown_docs.py](../../tools/sync_markdown_docs.py) |

## Varlık ve İçerik Klasörleri

- [../../assets](../../assets): UI, kart, efekt, ikon ve diğer sanat varlıkları
- [../../assets/ui/mode_icons/README.md](../../assets/ui/mode_icons/README.md): mod ikonları için beklenen dosya adları
- [../../backgrounds](../../backgrounds): kullanıcı tarafından değiştirilebilir arka plan resimleri
- [../../backgrounds/README.md](../../backgrounds/README.md): arka plan dosya adları ve fallback sırası
- [../../music](../../music): müzik içerikleri
- [../../avatars](../../avatars): avatar görselleri
- [../../font](../../font): font dosyaları
- [../../apple_emojis](../../apple_emojis): emoji görselleri

## Geliştirici İş Akışı

Oyunu çalıştırma:

```bash
python3 main.py
```

macOS/Linux önerilen başlatıcı:

```bash
./scripts/run/start_game.sh
```

Geliştirme bağımlılıkları (Python 3.12 zorunlu):

```bash
python3.12 -m pip install --user -e ".[dev,build]"
```

Test:

```bash
./scripts/test/run_tests.sh -q
```

Generated dokümanları senkronlama:

```bash
python3 tools/sync_markdown_docs.py
```

## Steam Köprüsü ve Online PvP

- Köprü artefactleri `local_artifacts/bridge/` altında tutulur ve PyInstaller spec'leri buradan toplar.
- Build notları: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md)
- Mimari arka plan: [../ONLINE_PVP_ARCHITECTURE.md](../ONLINE_PVP_ARCHITECTURE.md)
- Akış/davranış: [../ONLINE_PVP_FLOW_TR.md](../ONLINE_PVP_FLOW_TR.md)
- Köprü EXE/.app paketleme zorunlulukları (generated): [../EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](../EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md)

## Doküman Haritası

- Hızlı başlangıç: [../../README.md](../../README.md)
- Türkçe kısa rehber: [README_TR.md](README_TR.md)
- macOS platform notları: [README_MACOS.md](README_MACOS.md)
- Proje yapısı: [../PROJECT_STRUCTURE_TR.md](../PROJECT_STRUCTURE_TR.md)
- Mystery kart envanteri: [../CARD_PERK_INVENTORY_TR.md](../CARD_PERK_INVENTORY_TR.md)
- Build ve yayın: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)
- Steam playtest yayın: [../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](../STEAM_PLAYTEST_YAYIN_REHBERI_TR.md)
- Steam köprüsü EXE/.app entegrasyonu: [../EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md](../EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md)
- Steam leaderboard operasyonları: [../STEAM_LEADERBOARD_OPERATIONS_TR.md](../STEAM_LEADERBOARD_OPERATIONS_TR.md)
- Steam leaderboard kurulum: [../STEAMWORKS_LEADERBOARD_SETUP_TR.md](../STEAMWORKS_LEADERBOARD_SETUP_TR.md)
- Steam başarımları + statları: [../STEAM_ACHIEVEMENTS_SETUP.md](../STEAM_ACHIEVEMENTS_SETUP.md)
- Stale-check kontrol listesi: [../STALE_CHECKLIST_TR.md](../STALE_CHECKLIST_TR.md)

## Bu Belgeyi Ne İçin Kullanmalı?

- Oyunun hangi sistemlerden oluştuğunu hızlı görmek için
- Yeni bir klasöre veya mod dosyasına dalmadan önce yön bulmak için
- Teknik bir işe başlamadan önce ilgili modül ve dokümana atlamak için

Operasyonel detay (build komutları, Steam playtest, leaderboard runbook'u) gerektiğinde her zaman ilgili kanonik runbook'a yönlendirin; bu belge bir kapsayıcı değil, bir indekstir.

## Lisans

Proprietary
