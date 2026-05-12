# Quadrix Özellik ve Sistem Özeti

Bu belge, projenin ürün kapsamını ve ana teknik yüzeylerini tek yerde özetler. Hızlı kurulum için [../../README.md](../../README.md), platform ayrıntıları için [README_MACOS.md](README_MACOS.md) kullanılmalıdır.

## Oyun Paketi

### Ana oynanış katmanı

- Klasik tetromino döngüsü, skor ve seviye ilerleyişi
- Ghost piece, next preview, hold, combo ve hard drop gibi temel rahatlatıcılar
- Farklı hız, genişlik veya kural kümeleriyle çalışan ekstra modlar

### Mod ailesi

- Classic, Sprint, Ultra, Zen
- Quadrix 2, Mystery, Wide, Survival, Cascade, Hardcore, Daily
- Campaign ve yıldız/görev odaklı ilerleme akışı
- Local PvP, local co-op ve co-op campaign
- Steam tabanlı online PvP için yerel/native köprü altyapısı

### Oyuncu sistemleri

- Kullanıcı profilleri ve avatar yönetimi
- Mod bazlı skor, istatistik ve kullanıcı kayıtları
- Başarım sistemi ve Steam başarımları/stat eşlemesi
- Leaderboard ve backend proxy desteği

### Sunum ve özelleştirme

- Tema, blok stili ve arka plan özelleştirmeleri
- Dashboard tabanlı ana menü ve rehber ekranları
- Ses ve müzik sistemi, oynatma listesi ve shuffle desteği
- Dil profilleri ve CJK dahil çoklu font desteği

## Ana Teknik Yüzeyler

- [../../main.py](../../main.py): Türkçe ana giriş noktası
- [../../src/main_en.py](../../src/main_en.py): İngilizce yedek giriş noktası
- [../../src/game.py](../../src/game.py): tek oyunculu oyun döngüsü
- [../../src/pvp_game.py](../../src/pvp_game.py): yerel PvP akışı
- [../../src/coop_game.py](../../src/coop_game.py): ortak tahtalı co-op akışı
- [../../src/campaign](../../src/campaign): kampanya, objective ve seviye sistemleri
- [../../src/menu.py](../../src/menu.py): ana menü ve dashboard
- [../../src/extras_menu.py](../../src/extras_menu.py): mod kartları ve ikon akışı
- [../../src/guide_screen.py](../../src/guide_screen.py): mod rehberi ve ikon galerisi
- [../../src/user_manager.py](../../src/user_manager.py) ve [../../src/avatar_editor.py](../../src/avatar_editor.py): profil ve avatar yönetimi
- [../../src/steam_integration.py](../../src/steam_integration.py), [../../src/steam_leaderboards.py](../../src/steam_leaderboards.py) ve [../../backend/steam_leaderboard_proxy.py](../../backend/steam_leaderboard_proxy.py): Steam ve leaderboard katmanı

## Varlık ve İçerik Klasörleri

- [../../assets](../../assets): UI, kart, efekt, ikon ve diğer sanat varlıkları
- [../../backgrounds](../../backgrounds): kullanıcı tarafından değiştirilebilir arka plan resimleri
- [../../music](../../music): müzik içerikleri
- [../../avatars](../../avatars): avatar görselleri
- [../../assets/ui/mode_icons/README.md](../../assets/ui/mode_icons/README.md): mod ikonlarının beklenen dosya adları
- [../../backgrounds/README.md](../../backgrounds/README.md): arka plan dosya adları ve yükleme öncelikleri

## Geliştirici İş Akışı

Oyunu çalıştırma:

```bash
python3 main.py
```

macOS/Linux önerilen başlatıcı:

```bash
./scripts/run/start_game.sh
```

Geliştirme bağımlılıkları:

```bash
python3.12 -m pip install --user -e ".[dev,build]"
```

Test:

```bash
./scripts/test/run_tests.sh -q
```

Steam ağ köprüsü:

- Build notları: [../../steamworks/steam_net_bridge/README_BUILD.md](../../steamworks/steam_net_bridge/README_BUILD.md)
- Mimari arka plan: [../ONLINE_PVP_ARCHITECTURE.md](../ONLINE_PVP_ARCHITECTURE.md)

## Doküman Haritası

- Hızlı başlangıç: [../../README.md](../../README.md)
- Türkçe kısa rehber: [README_TR.md](README_TR.md)
- macOS platform notları: [README_MACOS.md](README_MACOS.md)
- Proje yapısı: [../PROJECT_STRUCTURE_TR.md](../PROJECT_STRUCTURE_TR.md)
- Build ve yayın: [../BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md)
- Steam operasyonları: [../STEAM_LEADERBOARD_OPERATIONS_TR.md](../STEAM_LEADERBOARD_OPERATIONS_TR.md)

## Bu Belgeyi Ne İçin Kullanmalı?

- Oyunun hangi sistemlerden oluştuğunu hızlı görmek için
- Yeni bir klasöre veya mod dosyasına dalmadan önce yön bulmak için
- Teknik bir işe başlamadan önce ilgili modül ve dokümana atlamak için

## Lisans

Proprietary
