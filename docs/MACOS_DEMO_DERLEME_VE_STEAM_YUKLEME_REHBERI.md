# macOS Demo Derleme ve Steam Yükleme Rehberi

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Kalici degisiklik icin kaynak script/spec/VDF dosyasini veya sync scriptini guncelle.

Bu doküman, Quadrix Demo oyununun macOS platformu için derlenmesi ve Steam'e yüklenmesi sırasında izlenen adımları, doğrulanan kuralları ve teknik detayları içerir. İleride yapılacak derleme/yükleme işlemlerinde referans kılavuz olarak kullanılabilir.

---

## 1. Uygulama Yapısı ve Kurallar (Windows Eşleşmesi)

Oyun kurallarının Windows demo sürümüyle birebir aynı olması sağlanmıştır:
- **Mystery (Kart Ustalığı) Modu Sınırı**: Demosundaki skor sınırı **1.000.000**'dur. Bu skora ulaşıldığında oyun dondurulur ve "Demo Tamamlandı" paneli açılır.
- **Konfigürasyon Dosyası**: [write_demo_config.py](file:///Users/burakyasayan/quadrix-demo/scripts/build/write_demo_config.py#L58) dosyasındaki `DEMO_MYSTERY_SCORE_CAP = 1000000` değişkeni üzerinden yönetilir.
- **Demo Modu Aktivasyonu**: Derleme scripti tetiklendiğinde `src/demo_config.py` otomatik olarak `IS_DEMO = True` durumuna getirilir. Derleme bittiğinde geliştirme ortamının bozulmaması için otomatik olarak `IS_DEMO = False` (full sürüm) konumuna geri döndürülür.

---

## 2. Derleme Süreci (Build)

Uygulamanın macOS üzerinde PyInstaller kullanılarak temiz bir şekilde paketlenmesi:

### Hazırlık ve Test
Derleme öncesi tüm kod tabanının kararlılığını doğrulamak için test suite koşulmuştur:

```bash
./scripts/test/run_tests.sh -q
```

### macOS Demo Bundle Derleme
Aşağıdaki komut çalıştırılarak temiz bir `.app` paketi üretilmiştir:

```bash
./scripts/build/build_macos_demo_app.sh --clean
```

- **Üretilen Paket**: `dist/Quadrix Demo.app`
- **İçerik Kontrolü**: `Contents/MacOS/QuadrixDemo` executable dosyası, `Contents/Frameworks/` altında native Steam API dylib'i ve derlenmiş `steam_net_bridge` kütüphanesi entegre edilmiştir.

---

## 3. Steam'e Yükleme Süreci (Upload)

Derlenen demo paketinin Steam Pipe sistemi üzerinden Steam sunucularına aktarılması adımları:

### Yükleme Parametreleri
- **App ID**: `4635310` (Quadrix Demo)
- **Depot ID**: `4635312` (macOS Demo Depot)
- **Steam Build Hesabı**: `vibecode_production`

### Çalıştırılan Komut

```bash
./scripts/build/steam_upload_macos.sh --demo --user vibecode_production --desc "macOS Demo build YYYY-MM-DD"
```

### Yükleme Sırasında Uygulanan Çözümler
1. **NFC Normalizasyonu (macOS NFD Fix)**: macOS işletim sistemi dosya adlarını ayrıştırılmış (decomposed - NFD) formda tutar. SteamCMD bu encoding'i manifest dosyalarında kabul etmediğinden (HTTP 400 hatası vermektedir), upload scripti `/tmp/` altında tüm dosya adlarını NFC formuna normalize etmiştir.
2. **Steam Guard**: Yükleme sırasında SteamCMD şifre sormuş ve ardından hesapta tanımlı olan Steam Guard Mobil Kimlik Doğrulayıcı (Mobile Authenticator) onayı mobil uygulama üzerinden verilerek oturum açılmıştır.

---

## 4. Sonraki Adımlar ve Canlıya Alma

Yüklenen build'in son kullanıcılara ulaşabilmesi için şu adımlar takip edilmelidir:
1. [Steamworks Partner Paneli](https://partner.steamgames.com)'ne giriş yapın.
2. **AppID 4635310 (Quadrix Demo)** sayfasına gidin.
3. **SteamPipe** -> **Builds** sekmesine tıklayın.
4. Yeni yüklenen derlemeyi (BuildID) uygun test branch'ine (örn: `beta` veya `playtest`) ya da doğrudan oyuncuların indirmesi için varsayılan (`default`/`public`) branch'e atayın ve değişiklikleri kaydedin.
