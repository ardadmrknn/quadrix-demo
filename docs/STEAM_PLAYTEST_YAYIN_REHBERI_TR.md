# Steam Playtest Yayin Rehberi (Quadrix)

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Rehberdeki teknik degerler helper script/spec/VDF dosyalarindan cekilir.

Bu rehber Steam tarafinda manuel kalan adimlarla, repo tarafinda otomatiklesen adimlari ayirir.

## 1) Steamworks Panelinde Manuel Hazirlik

1. Playtest AppID icin package, depot ve launch option tanimla.
2. Build hesabinin AppID icin yetkili oldugunu dogrula.
3. Yukleme bittikten sonra BuildID'yi dogru branch'e ata.
4. Gerekirse Playtest `Playable` durumunu ac ve katilim tipini sec.

## 2) Repo Tarafinda Guncel Gercekler

- Playtest AppID: `4428040`
- Windows depot: `4428041` via `depot_build_playtest_windows.vdf`
- macOS depot: `4428043` via `depot_build_macos.vdf`
- Windows upload helper: `tools/steam_upload_playtest.ps1`
- macOS upload helper: `scripts/build/steam_upload_macos.sh`
- Windows helper temp VDF patchliyor: `evet`
- macOS helper temp VDF patchliyor: `evet`

Onemli fark:

- Artik repo icindeki VDF dosyasina her build icin `Desc`, `ContentRoot` veya `BuildOutput` yazman gerekmiyor.
- Helper scriptler bu alanlari gecici VDF olusturarak dolduruyor.
- Track edilen VDF dosyasinda kalan `Desc` degeri sadece sablon deger.

## 3) Windows Playtest Akisi

### Build

```powershell
pwsh -File .\scripts\build\build_windows_exe.ps1 -Clean
```

### Upload

```powershell
pwsh -File .\tools\steam_upload_playtest.ps1 `
    -SteamCmdPath "C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" `
    -SteamUser "BUILD_ACCOUNT" `
    -BuildDescription "Playtest build YYYY-MM-DD"
```

Dusuk seviye fallback:

```powershell
py -m PyInstaller packaging\specs\tetris.spec --noconfirm
"C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" +login BUILD_ACCOUNT +run_app_build ".\steamworks\scripts\app_build_playtest.vdf" +quit
```

## 4) macOS Playtest Akisi

### Build

```bash
./scripts/build/build_macos_app.sh --clean
```

### Upload

```bash
./scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"
```

Notlar:

- Script varsayilan olarak `steamworks/scripts/app_build_playtest_macos.vdf` kullanir.
- `--full` verilirse `steamworks/scripts/app_build_full.vdf` secilir.
- `--build-first` tavsiye edilen guvenli akistir.
- Stale app tespit edilirse upload durdurulur; zorlamak icin `QUADRIX_ALLOW_STALE_UPLOAD=1` gerekir.

## 5) Guncel VDF Sablonlari

### Windows

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

### macOS

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

## 6) Kod Degisince Ne Olur?

- Kod degisikligi tek basina Steam build'ini degistirmez.
- Sen yeni build aldiginda guncel kod pakete girer.
- Sen upload yaptiginda yeni build Steam'e gider.
- Branch'e canli alma adimi hala Steamworks panelinde manuel yapilir.
