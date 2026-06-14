# macOS adim adim temiz rebuild rehberi

Bu dosya, macOS cihazda Online PvP private/public lobby problemini kapatmak icin uygulanacak adimlari sirayla anlatir.

## Amac

- macOS paketi ayni committen yeniden uretilecek
- eski bridge artifactleri silinecek
- yeni bridge derlenecek
- temiz .app paketi alinacak
- Windows ile capraz lobby gorunurlugu tekrar test edilecek

## 1. Repo guncelle

Terminal ac.

Repo klasorune gir:

```bash
cd /repo/yolu/quadrix
```

Dogru branch ve dogru committe oldugunu kontrol et:

```bash
git status
git rev-parse HEAD
```

Windows cihazdaki commit ile ayni olmasi gerekir.

## 2. macOS local surum dosyasi gerekmez

Bu akış kaldirildi.

- macOS build artik yerel bir version dosyasi uretmez.
- Surum bilgisi dogrudan src/version_base.py uzerinden kullanilir.

## 3. Steamworks SDK var mi kontrol et

Su dosya mevcut olmali:

```bash
ls steamworks/sdk/public/steam/steam_api.h
```

Eger dosya yoksa bridge derlenmez.

## 4. Python ve PyInstaller hazir mi kontrol et

```bash
python3.12 -c "import PyInstaller, pygame; print('ok')"
```

Eger python3.12 yoksa script python3 ile de devam edebilir, ama tercihen 3.12 kullan.

## 5. Temiz rebuild baslat

Su komutu calistir:

```bash
./scripts/build/build_macos_app.sh --clean --rebuild-bridge
```

Bu komut sunlari yapar:
- build/ klasorunu siler
- dist/ klasorunu siler
- root'taki eski steam_net_bridge*.so dosyalarini siler
- steamworks/steam_net_bridge/build.sh ile bridge'i yeniden derler
- PyInstaller ile temiz .app paketi olusturur

## 6. Build sonrasi kontrol

Su dosyalari kontrol et:

Root'ta yeni bridge olusmus mu:

```bash
ls steam_net_bridge*.so
```

App cikti klasoru olusmus mu:

```bash
ls dist/Quadrix.app
```

Eger bunlar varsa temiz macOS build alinmis demektir.

## 7. Lobby gorunurluk testi

Temiz macOS build alindiktan sonra su sirayla test et:

1. Windows cihazda ozel lobi olustur.
2. macOS lobby listesinde private gorunuyor mu bak.
3. macOS cihazda ozel lobi olustur.
4. Windows lobby listesinde private gorunuyor mu bak.
5. Windows cihazda public lobi olustur.
6. macOS public goruyor mu bak.
7. macOS cihazda public lobi olustur.
8. Windows public goruyor mu bak.

## 8. Beklenen sonuc

- Ozel lobi her iki platformda da private gorunmeli.
- Public lobi her iki platformda da public gorunmeli.

## 9. Sorun devam ederse neye bakilir

1. Iki cihaz ayni committe mi?
2. macOS build gercekten --rebuild-bridge ile alindi mi?
3. Root'ta eski bridge artifacti kaliyor mu?
4. Windows paketi de temiz rebuild edildi mi?

## 10. Gerekli ilgili dosyalar

- scripts/build/build_macos_app.sh
- docs/ONLINE_PVP_CLEAN_REBUILD_TR.md
- docs/MACOS_LOCAL_VERSION_BOOTSTRAP_TR.md
