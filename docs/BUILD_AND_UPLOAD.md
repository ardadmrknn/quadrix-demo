# Build & Steam Upload Rehberi

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Kalici degisiklik icin kaynak script/spec/VDF dosyasini veya sync scriptini guncelle.

## Kisa Cevap

- Kod degisince Steam build kendiliginden guncellenmez.
- Guncel kodun pakete girmesi icin build komutunu sen calistirirsin.
- Steam'e yeni build gitmesi icin upload komutunu sen calistirirsin.
- Upload sirasinda `Desc`, `ContentRoot` ve `BuildOutput` alanlari helper script tarafindan gecici VDF uzerinde doldurulur.
- CI su an otomatik Steam upload yapmiyor; sadece test/lint calistiriyor.

## Kaynak Gercekler

### Windows

- Canonical build helper: `scripts/build/build_windows_exe.ps1`
- Canonical upload helper: `tools/steam_upload_playtest.ps1`
- Canonical spec: `packaging/specs/tetris.spec`
- Playtest AppID: `4428040`
- Playtest depot: `4428041`
- Upload helper temp VDF patchliyor: `evet`
- Build helper bridge derleyebiliyor: `evet`

### macOS

- Canonical build helper: `scripts/build/build_macos_app.sh`
- Canonical upload helper: `scripts/build/steam_upload_macos.sh`
- Canonical spec: `packaging/specs/tetris_macos_allinone.spec`
- Uretilen uygulama adi: `Quadrix.app`
- Playtest AppID: `4428040`
- Playtest depot: `4428043`
- Upload helper temp VDF patchliyor: `evet`
- Upload helper `--build-first` destekliyor: `evet`
- Upload helper stale build guard kullaniyor: `evet`

### Otomatik Sürüm Artirma

Windows local version bump bu spec dosyalarinda aktif:

- `packaging/specs/tetris.spec`
- `packaging/specs/tetris_en.spec`
- `packaging/specs/tetris_playtest.spec`

macOS tarafinda local override bump yok; runtime dogrudan `src/version_base.py` surumunu okur.

### Bridge Toplayan Spec Dosyalari

- `packaging/specs/tetris.spec`
- `packaging/specs/tetris_demo.spec`
- `packaging/specs/tetris_demo_linux.spec`
- `packaging/specs/tetris_demo_macos_allinone.spec`
- `packaging/specs/tetris_en.spec`
- `packaging/specs/tetris_linux.spec`
- `packaging/specs/tetris_macos.spec`
- `packaging/specs/tetris_macos_allinone.spec`
- `packaging/specs/tetris_playtest.spec`

## Onerilen Komutlar

### Windows build

```powershell
pwsh -File .\scripts\build\build_windows_exe.ps1 -Clean
```

### Windows upload

```powershell
pwsh -File .\tools\steam_upload_playtest.ps1 `
    -SteamCmdPath "C:\steamcmd\steamcmd.exe" `
    -SteamUser "BUILD_ACCOUNT" `
    -BuildDescription "Playtest build YYYY-MM-DD" `
    -SetLive ""
```

Dusuk seviye fallback:

```powershell
py -m PyInstaller packaging\specs\tetris.spec --noconfirm
```

### macOS build

```bash
./scripts/build/build_macos_app.sh --clean
```

### macOS upload

```bash
./scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"
```

Dusuk seviye fallback:

```bash
pyinstaller packaging/specs/tetris_macos_allinone.spec --noconfirm
```

## VDF Politicasi

- Windows helper varsayilan olarak gecici bir AppBuild VDF uretir; override etmek icin `-AppBuildScript steamworks/scripts/app_build_playtest.vdf` kullanilabilir.
- macOS helper varsayilan olarak `steamworks/scripts/app_build_playtest_macos.vdf` dosyasini kullanir; `--full` ile `steamworks/scripts/app_build_full.vdf` secilir.
- Track edilen VDF sablonlarinda makineye ozel `ContentRoot` ve `BuildOutput` degeri tutulmaz.
- `Desc` alani helper script tarafindan runtime'da override edilebilir; VDF icindeki default deger yalnizca sablon gorevi gorur.

### Guncel Windows Playtest VDF Sablosu

```vdf
"AppBuild"
{
    "AppID" "4428040"
    "Desc" "Playtest build"
    "SetLive" ""
    "ContentRoot" ""
    "BuildOutput" ""

    "Depots"
    {
        "4428041" "depot_build_playtest_windows.vdf"
    }
}
```

### Guncel macOS Playtest VDF Sablosu

```vdf
"AppBuild"
{
    "AppID" "4428040"
    "Desc" "macOS Playtest build 2026-02-19"
    "SetLive" ""
    "ContentRoot" ""
    "BuildOutput" ""

    "Depots"
    {
        "4428043" "depot_build_macos.vdf"
    }
}
```

## Ne Manuel Kaldi?

- Steam build komutunu elle calistirmak
- Steam Guard / partner hesabiyla giris yapmak
- Steamworks panelinde yuklenen BuildID'yi branch'e atamak
- Gerekirse Playtest `Playable` / branch canli ayarlarini acmak

## CI Durumu

- GitHub Actions Steam upload yapiyor mu: `hayir`
- Mevcut CI amaci: test ve lint
