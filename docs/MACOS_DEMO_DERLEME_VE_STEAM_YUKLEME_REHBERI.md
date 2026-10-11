# macOS Demo Derleme ve Steam Yükleme Rehberi

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Kalici degisiklik icin kaynak script/spec/VDF dosyasini veya sync scriptini guncelle.

Bu doküman, Quadrix Demo oyununun macOS platformu için derlenmesi ve Steam'e yüklenmesi sırasında izlenen adımları, doğrulanan kuralları ve teknik detayları içerir. İleride yapılacak derleme/yükleme işlemlerinde referans kılavuz olarak kullanılabilir.

---

## 1. Uygulama Yapısı ve Kurallar (Windows Eşleşmesi)

Oyun kurallarının Windows demo sürümüyle birebir aynı olması sağlanmıştır:
- **Mystery (Kart Ustalığı) Modu Sınırı**: Demodaki skor sınırı **1.000.000**'dur. Bu skora ulaşıldığında oyun dondurulur ve "Demo Tamamlandı" paneli açılır.
- **Konfigürasyon Kaynağı**: `src/demo_config.py` içindeki `DEMO_MYSTERY_SCORE_CAP = 1000000` değişkeni üzerinden yönetilir (bu değeri otomatiklayan `write_demo_config.py` repoya hiç commit'lenmedi).
- **Demo Modu Aktivasyonu**: Derleme öncesi `src/demo_config.py` içinde `IS_DEMO = True` yapılır; derleme bittiğinde geliştirme ortamının bozulmaması için manuel olarak geri alınır.

---

## 2. Derleme Süreci (Build)

### Hazırlık ve Test
Derleme öncesi tüm kod tabanının kararlılığını doğrulamak için test suite koşulur:

```bash
./scripts/test/run_tests.sh -q
```

### macOS Demo Bundle Derleme
Build helper'ın `--spec`/`--app-name` geçersiz kılmalarıyla demo paketi üretilir:

```bash
./scripts/build/build_macos_app.sh --spec packaging/specs/tetris_demo_macos_allinone.spec --app-name "Quadrix Demo" --clean
```

- **Üretilen Paket**: `dist/Quadrix Demo.app`
- **İçerik Kontrolü**: `Contents/MacOS/` altında executable, `Contents/Frameworks/` altında native Steam API dylib'i ve derlenmiş `steam_net_bridge` kütüphanesi entegre edilir.

---

## 3. Steam'e Yükleme Süreci (Upload)

Demo macOS upload sarmalayıcısı repoda YOK (`scripts/build/steam_upload_macos.sh`, 445a0da'da silindi). Yükleme manuel steamcmd akışıyla yapılır:

### Yükleme Parametreleri
- **App ID**: `4635310` (Quadrix Demo)
- **Depot ID**: `4635312` (macOS Demo Depot)
- **VDF Şablonu**: `steamworks/scripts/app_build_demo_macos.vdf` (`ContentRoot`/`BuildOutput` alanları yükleme öncesi doldurulur)

### Çalıştırılan Komut (düşük seviye)

```bash
steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/app_build_demo_macos.vdf +quit
```

### Yükleme Sırasında Doğrulanan Deneyimler
1. **NFC Normalizasyonu (macOS NFD Fix)**: macOS dosya adlarını ayrıştırılmış (decomposed - NFD) formda tutar. SteamCMD bu encoding'i manifest dosyalarında kabul etmediğinden (HTTP 400), upload öncesi `/tmp/` altındaki tüm dosya adları NFC formuna normalize edilmelidir.
2. **Steam Guard**: Yükleme sırasında SteamCMD şifre sorar; hesapta tanımlı Steam Guard Mobil Kimlik Doğrulayıcı onayı mobil uygulama üzerinden verilerek oturum açılır.

---

## 4. Sonraki Adımlar ve Canlıya Alma

Yüklenen build'in son kullanıcılara ulaşabilmesi için şu adımlar takip edilmelidir:
1. [Steamworks Partner Paneli](https://partner.steamgames.com)'ne giriş yapın.
2. **AppID 4635310 (Quadrix Demo)** sayfasına gidin.
3. **SteamPipe** -> **Builds** sekmesine tıklayın.
4. Yeni yüklenen derlemeyi (BuildID) uygun test branch'ine (örn: `beta`) ya da doğrudan oyuncuların indirmesi için varsayılan (`default`/`public`) branch'e atayın ve değişiklikleri kaydedin.
