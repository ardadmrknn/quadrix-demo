# EXE / .app Derlemede Steam Bridge Entegrasyonu (Zorunlu)

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Bridge akisi build helper ve spec dosyalarindan cekilen guncel bilgilerle yazilir.

## Kisa Cevap

- `steam_net_bridge` olmadan Online PvP acilmaz.
- Windows canonical build helper bridge artefact yoksa derleyebilir.
- macOS canonical build helper bridge artefact yoksa veya kaynak daha yeniyse yeniden derleyebilir.
- Asagidaki spec dosyalari bridge binary arar ve paketlemeye ekler.

## Bridge Toplayan Spec Dosyalari

- `packaging/specs/tetris.spec`
- `packaging/specs/tetris_demo.spec`
- `packaging/specs/tetris_demo_macos_allinone.spec`
- `packaging/specs/tetris_en.spec`
- `packaging/specs/tetris_macos.spec`
- `packaging/specs/tetris_macos_allinone.spec`
- `packaging/specs/tetris_playtest.spec`

## Canonical Wrapper Akislari

### Windows

```powershell
pwsh -File .\scripts\build\build_windows_exe.ps1 -Clean
```

Beklenen davranis:

- Bridge artefact yoksa `steamworks\steam_net_bridge\build.bat` tetiklenir.
- Artefactler `local_artifacts\bridge` altina senkronize edilir.
- Ardindan `packaging/specs/tetris.spec` ile PyInstaller build'i calisir.

### macOS

```bash
./scripts/build/build_macos_app.sh --clean
```

Beklenen davranis:

- Bridge artefact yoksa `steamworks/steam_net_bridge/build.sh` tetiklenir.
- Bridge kaynak dosyasi artefactten yeniyse rebuild zorlanir.
- Ardindan `packaging/specs/tetris_macos_allinone.spec` ile `.app` build'i alinir.

## Low-level Fallback

### Windows

```powershell
cd steamworks\steam_net_bridge
build.bat
cd ..\..
py -m PyInstaller packaging\specs\tetris.spec --noconfirm
```

### macOS

```bash
cd steamworks/steam_net_bridge
chmod +x build.sh
./build.sh
cd ../..
pyinstaller packaging/specs/tetris_macos_allinone.spec --noconfirm
```

## Otomasyon Seviyesi

- Windows helper bridge derleyebiliyor: `evet`
- macOS helper bridge derleyebiliyor: `evet`
- macOS helper stale bridge rebuild yapiyor: `evet`

## Kisa Kontrol Listesi

- `local_artifacts/bridge` altinda uygun ABI artifact var mi?
- PyInstaller log'unda `steam_net_bridge eklendi` satiri goruldu mu?
- Paket build'de Online PvP lobi acma akisi calisiyor mu?
