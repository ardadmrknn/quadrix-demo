# EXE / .app Derlemede Steam Bridge Entegrasyonu (Zorunlu)

> Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
> Bridge akisi build helper ve spec dosyalarindan cekilen guncel bilgilerle yazilir.

## Kisa Cevap

- `steam_net_bridge` olmadan Online PvP acilmaz.
- Windows tarafinda build helper repoda YOK: bridge derleme ve PyInstaller adimi manuel.
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

### Windows (manuel — helper repoda yok)

```powershell
cd steamworks\steam_net_bridge
build.bat
cd ..\..
py -m PyInstaller packaging\specs\tetris_demo.spec --noconfirm
```

Beklenen davranis:

- Bridge artefact yoksa `steamworks\steam_net_bridge\build.bat` elle tetiklenir.
- Artefactler `local_artifacts\bridge` altina senkronize edilir.
- Ardindan `packaging/specs/tetris_demo.spec` ile PyInstaller build'i calisir.

### macOS

```bash
./scripts/build/build_macos_app.sh --spec packaging/specs/tetris_demo_macos_allinone.spec --app-name "Quadrix Demo" --clean
```

Beklenen davranis:

- Bridge artefact yoksa `steamworks/steam_net_bridge/build.sh` tetiklenir.
- Bridge kaynak dosyasi artefactten yeniyse rebuild zorlanir.
- Ardindan `packaging/specs/tetris_demo_macos_allinone.spec` ile `.app` build'i alinir.

## Otomasyon Seviyesi

- Windows helper bridge derleyebiliyor: repoda helper YOK (445a0da'da silindi)
- macOS helper bridge derleyebiliyor: `evet`
- macOS helper stale bridge rebuild yapiyor: `evet`

## Kisa Kontrol Listesi

- `local_artifacts/bridge` altinda uygun ABI artifact var mi?
- PyInstaller log'unda `steam_net_bridge eklendi` satiri goruldu mu?
- Paket build'de Online PvP lobi acma akisi calisiyor mu?
