# Online PvP icin temiz rebuild rehberi

Bu rehber, Windows ve macOS paketlerinin ayni kaynak kod ve temiz bridge ile yeniden uretilmesini saglar.
Amac: lobby visibility gibi platformlar arasi tutarsizliklarda eski artifact kaynakli hatalari sifirlamak.

## Neden gerekli

- Steam lobby private/public bilgisi bridge metadata'si ile tasiniyor.
- Eski bridge binary veya eski paket kalintisi kalirsa bir platform private lobiyi public gorebilir.
- Sadece menu surum numarasini esit yapmak yetmez; temiz rebuild gerekir.

## Windows temiz rebuild

PowerShell:

```powershell
./scripts/build/build_windows_exe.ps1 -Clean -RebuildBridge
```

Ne yapar:
- build/ ve dist/ klasorlerini siler
- local_artifacts/bridge altindaki eski steam_net_bridge artifactlerini siler
- steamworks/steam_net_bridge/build.bat ile bridge'i yeniden derler
- PyInstaller'i temiz modda yeniden calistirir

Varsayilan spec: packaging/specs/tetris.spec

Farkli spec ornegi:

```powershell
./scripts/build/build_windows_exe.ps1 -Clean -RebuildBridge -SpecFile tetris_playtest.spec
```

## macOS temiz rebuild

Terminal:

```bash
./scripts/build/build_macos_app.sh --clean --rebuild-bridge
```

Ne yapar:
- build/ ve dist/ klasorlerini siler
- root'taki eski steam_net_bridge*.so dosyalarini siler
- steamworks/steam_net_bridge/build.sh ile bridge'i yeniden derler
- PyInstaller ile .app paketini temiz modda yeniden olusturur

## Iki platform icin dogrulama

1. Iki cihazda da ayni commit checkout edilsin.
2. Windows paketini temiz rebuild et.
3. macOS paketini temiz rebuild et.
4. macOS'ta ozel lobi kur.
5. Windows lobby listesinde private gorundugunu kontrol et.
6. Windows'ta ozel lobi kur.
7. macOS lobby listesinde private gorundugunu kontrol et.

## Beklenen sonuc

- Her iki tarafta da ozel lobi private gorunmeli.
- Herkese acik lobi public gorunmeli.
- Bridge path farki tek basina belirleyici olmamali; temiz rebuild ile binary uyumsuzlugu ortadan kalkmali.

## Koda eklenen net fix

- Bridge artik lobby olusturulur olusturulmaz visibility ve requires_code metadata'sini C++ tarafinda yazar.
- Python lobby listeleme artik baska bir aktif lobby'nin metadata'sina fallback yapmaz.

Bu iki degisiklik birlikte, macOS private -> Windows public gorunmesi tipindeki capraz yorumlama hatasini kapatmak icin yapildi.