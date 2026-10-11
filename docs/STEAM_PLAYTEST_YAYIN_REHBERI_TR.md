# Steam Playtest Yayin Rehberi (Quadrix Demo)

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
- Windows playtest helper: `tools/steam_upload_playtest.ps1`
- macOS upload helper: repoda YOK — manuel steamcmd akisi
- Windows helper temp VDF patchliyor: `evet`

Onemli fark:

- Artik repo icindeki VDF dosyasina her build icin `Desc`, `ContentRoot` veya `BuildOutput` yazman gerekmiyor.
- Windows helper bu alanlari gecici VDF olusturarak dolduruyor.
- Track edilen VDF dosyasinda kalan `Desc` degeri sadece sablon deger.

## 3) Windows Playtest Akisi

### Build (manuel — build helper repoda yok)

```powershell
py -m PyInstaller packaging\specs\tetris_demo.spec --noconfirm
```

### Upload

```powershell
pwsh -File .\tools\steam_upload_playtest.ps1 `
    -SteamCmdPath "C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" `
    -SteamUser "BUILD_ACCOUNT" `
    -BuildDescription "Playtest build YYYY-MM-DD"
```

## 4) macOS Playtest Akisi

### Build

```bash
./scripts/build/build_macos_app.sh --clean
```

### Upload (manuel — helper repoda yok)

```bash
steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/app_build_playtest_macos.vdf +quit
```

Notlar:

- macOS yuklemede VDF sablonundaki `ContentRoot`/`BuildOutput` once doldurulur.
- Stale app tespiti yapan sarmalayici repoda yok; yukleme oncesi taze build alinmalidir.

## 5) Guncel VDF Sablonlari

### Windows playtest

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

### macOS playtest

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
