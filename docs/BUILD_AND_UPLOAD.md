# Demo Build & Steam Upload Rehberi

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Kalici degisiklik icin kaynak script/spec/VDF dosyasini veya sync scriptini guncelle.

## Kisa Cevap

- Kod degisince Steam build kendiliginden guncellenmez.
- Guncel kodun pakete girmesi icin build komutunu sen calistirirsin.
- Steam'e yeni build gitmesi icin upload komutunu sen calistirirsin.
- Windows tarafinda build helper repoda YOK (445a0da'da silindi): build manuel PyInstaller ile.
- macOS tarafinda upload helper repoda YOK (445a0da'da silindi): yukleme manuel steamcmd akisiyla.
- CI su an otomatik Steam upload yapmiyor; sadece test/lint calistiriyor.

## Kaynak Gercekler

### Windows (Demo)

- Kanonik demo spec: `packaging/specs/tetris_demo.spec`
- Kanonik upload helper: `tools/steam_upload_demo.ps1` (playtest helper'ini `Target='demo'` ile sarmalar)
- Playtest helper (paylasilan cekirdek): `tools/steam_upload_playtest.ps1`
- Demo AppID: `4635310`
- Demo depot: `4635311`
- Upload helper temp VDF patchliyor: `evet`
- Upload helper ContentRoot AppID kimlik kontrolu yapiyor: `evet`

### macOS (Demo)

- Kanonik build helper: `scripts/build/build_macos_app.sh` (tam surum varsayani; `--spec` ile demo spec secilir)
- Kanonik demo spec: `packaging/specs/tetris_demo_macos_allinone.spec`
- Demo uygulama adi: `Quadrix Demo.app`
- Demo AppID: `4635310`
- Demo depot: `4635312`
- Build helper bridge derleyebiliyor: `evet`
- Upload helper: repoda YOK — yukleme manuel steamcmd akisiyla

### Otomatik Surum Artirma

Windows local version bump bu spec dosyalarinda aktif (demo spec'lerinde bump YOK):

- `packaging/specs/tetris.spec`
- `packaging/specs/tetris_en.spec`
- `packaging/specs/tetris_playtest.spec`

macOS tarafinda local override bump yok; runtime dogrudan `src/version_base.py` surumunu okur.

### Bridge Toplayan Spec Dosyalari

- `packaging/specs/tetris.spec`
- `packaging/specs/tetris_demo.spec`
- `packaging/specs/tetris_demo_macos_allinone.spec`
- `packaging/specs/tetris_en.spec`
- `packaging/specs/tetris_macos.spec`
- `packaging/specs/tetris_macos_allinone.spec`
- `packaging/specs/tetris_playtest.spec`

## Onerilen Komutlar

### Windows demo build (manuel — helper yok)

```powershell
py -m PyInstaller packaging\specs\tetris_demo.spec --noconfirm
```

Not: derleme oncesi `src/demo_config.py` icinde `IS_DEMO = True` yapilmali, derleme sonrasi geri alinmali (bu gecisi otomatikleyen script repoya commit'lenmemis).

### Windows demo upload

```powershell
pwsh -File .\tools\steam_upload_demo.ps1 `
    -SteamCmdPath "C:\steamcmd\steamcmd.exe" `
    -SteamUser "BUILD_ACCOUNT" `
    -BuildDescription "Demo build YYYY-MM-DD" `
    -SetLive ""
```

### macOS demo build

```bash
./scripts/build/build_macos_app.sh --spec packaging/specs/tetris_demo_macos_allinone.spec --app-name "Quadrix Demo" --clean
```

Dusuk seviye fallback:

```bash
pyinstaller packaging/specs/tetris_demo_macos_allinone.spec --noconfirm
```

### macOS demo upload (manuel — helper yok)

VDF sablonunda `ContentRoot` ve `BuildOutput` bos birakilmistir; manuel akista once doldurulur:

```bash
steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/app_build_demo_macos.vdf +quit
```

## VDF Politicasi

- Windows demo helper varsayilan olarak `steamworks/scripts/app_build_demo.vdf` dosyasini kullanir.
- Playtest helper'in AppBuildScript varsayani bos ise gecici VDF uretir: `evet`
- Track edilen VDF sablonlarinda makineye ozel `ContentRoot` ve `BuildOutput` degeri tutulmaz.
- `Desc` alani helper script tarafindan runtime'da override edilebilir; VDF icindeki default deger yalnizca sablon gorevi gorur.

### Guncel Windows Demo VDF Sablonu

```vdf
"AppBuild"
{
    "AppID" "4635310"
    "Desc" "Demo build"
    "SetLive" ""
    "ContentRoot" ""
    "BuildOutput" ""

    "Depots"
    {
        "4635311" "depot_build_demo_windows.vdf"
    }
}
```

### Guncel macOS Demo VDF Sablonu

```vdf
"AppBuild"
{
    "AppID" "4635310"
    "Desc" "Demo macOS build"
    "SetLive" ""
    "ContentRoot" ""
    "BuildOutput" ""

    "Depots"
    {
        "4635312" "depot_build_demo_macos.vdf"
    }
}
```

## Ne Manuel Kaldi?

- Steam build komutunu elle calistirmak
- Steam Guard / partner hesabiyla giris yapmak
- Steamworks panelinde yuklenen BuildID'yi branch'e atamak
- Gerekirse Demo `Playable` / branch canli ayarlarini acmak

## CI Durumu

- GitHub Actions Steam upload yapiyor mu: `hayir`
- Mevcut CI amaci: test ve lint
