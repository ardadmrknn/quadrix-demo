from __future__ import annotations

import argparse
import re
from pathlib import Path
from textwrap import dedent, indent


ROOT_DIR = Path(__file__).resolve().parent.parent


def _read_text(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding='utf-8').replace('\r\n', '\n')


def _normalize(text: str) -> str:
    text = text.lstrip('\n').rstrip()
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith('        - ') or line.startswith('        ```'):
            lines.append(line[8:])
            continue
        lines.append(line)
    return '\n'.join(lines) + '\n'


def _clean_repo_relative_path(path: str) -> str:
    normalized = path.replace('\\', '/')
    normalized = re.sub(r'^\./+', '', normalized)
    normalized = re.sub(r'/+', '/', normalized)
    return normalized


def _to_windows_path(path: str) -> str:
    return path.replace('/', '\\')


def _indent_block(text: str, spaces: int = 8) -> str:
    return indent(text, ' ' * spaces)


def _extract_ps1_string_default(text: str, name: str) -> str:
    pattern = rf"\[string\]\${re.escape(name)}\s*=\s*(['\"])(.*?)\1"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f'PowerShell string default not found: {name}')
    return match.group(2)


def _extract_shell_assignment(text: str, name: str) -> str:
    pattern = rf'(?m)^{re.escape(name)}="([^"]*)"$'
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f'Shell assignment not found: {name}')
    return match.group(1)


def _extract_vdf_field(text: str, field_name: str) -> str:
    pattern = rf'"{re.escape(field_name)}"\s*"([^"]*)"'
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f'VDF field not found: {field_name}')
    return match.group(1)


def _extract_vdf_depots(text: str) -> list[tuple[str, str]]:
    depots_match = re.search(r'"Depots"\s*\{(?P<body>.*?)\n\s*\}', text, re.DOTALL)
    if not depots_match:
        return []
    return re.findall(r'"(\d+)"\s*"([^"]+)"', depots_match.group('body'))


def _relative_paths_for_specs_containing(token: str) -> list[str]:
    spec_dir = ROOT_DIR / 'packaging' / 'specs'
    matches: list[str] = []
    for path in sorted(spec_dir.glob('*.spec')):
        if token in path.read_text(encoding='utf-8'):
            matches.append(path.relative_to(ROOT_DIR).as_posix())
    return matches


def _render_bullets(items: list[str]) -> str:
    return '\n'.join(f'- `{item}`' for item in items)


def _render_fenced_block(language: str, body: str) -> str:
    return f'```{language}\n{body.rstrip()}\n```'


def build_context() -> dict[str, object]:
    windows_build_text = _read_text('scripts/build/build_windows_exe.ps1')
    windows_upload_text = _read_text('tools/steam_upload_playtest.ps1')
    mac_build_text = _read_text('scripts/build/build_macos_app.sh')
    mac_upload_text = _read_text('scripts/build/steam_upload_macos.sh')
    windows_vdf_text = _read_text('steamworks/scripts/app_build_playtest.vdf')
    mac_playtest_vdf_text = _read_text('steamworks/scripts/app_build_playtest_macos.vdf')
    ci_text = _read_text('.github/workflows/ci.yml')

    windows_spec = _clean_repo_relative_path(_extract_ps1_string_default(windows_build_text, 'SpecFile'))
    windows_app_build_script = _clean_repo_relative_path(_extract_ps1_string_default(windows_upload_text, 'AppBuildScript'))
    mac_spec = _clean_repo_relative_path(_extract_shell_assignment(mac_build_text, 'SPEC_FILE'))
    mac_app_name = _extract_shell_assignment(mac_build_text, 'APP_NAME')

    windows_app_id = _extract_vdf_field(windows_vdf_text, 'AppID')
    mac_app_id = _extract_vdf_field(mac_playtest_vdf_text, 'AppID')
    windows_desc = _extract_vdf_field(windows_vdf_text, 'Desc')
    mac_desc = _extract_vdf_field(mac_playtest_vdf_text, 'Desc')

    windows_depots = _extract_vdf_depots(windows_vdf_text)
    mac_depots = _extract_vdf_depots(mac_playtest_vdf_text)

    bridge_specs = _relative_paths_for_specs_containing('get_bridge_binaries(')
    windows_version_bump_specs = _relative_paths_for_specs_containing("bump_platform_version(REPO_ROOT, 'windows')")

    ci_has_steam_upload = any(
        token in ci_text
        for token in ('run_app_build', 'steam_upload_playtest', 'steam_upload_macos')
    )

    return {
        'windows_spec': windows_spec,
        'windows_upload_script': 'tools/steam_upload_playtest.ps1',
        'windows_build_script': 'scripts/build/build_windows_exe.ps1',
        'windows_app_build_script': windows_app_build_script,
        'windows_app_id': windows_app_id,
        'windows_desc': windows_desc,
        'windows_depots': windows_depots,
        'windows_vdf_text': windows_vdf_text.rstrip(),
        'windows_upload_uses_temp_vdf': '.tmp_app_build_' in windows_upload_text and 'Set-VdfField' in windows_upload_text,
        'windows_build_compiles_bridge': 'Steam bridge derleniyor' in windows_build_text,
        'mac_spec': mac_spec,
        'mac_build_script': 'scripts/build/build_macos_app.sh',
        'mac_upload_script': 'scripts/build/steam_upload_macos.sh',
        'mac_app_name': mac_app_name,
        'mac_app_id': mac_app_id,
        'mac_desc': mac_desc,
        'mac_depots': mac_depots,
        'mac_playtest_vdf_text': mac_playtest_vdf_text.rstrip(),
        'mac_playtest_vdf': 'steamworks/scripts/app_build_playtest_macos.vdf',
        'mac_full_vdf': 'steamworks/scripts/app_build_full.vdf',
        'mac_upload_uses_temp_vdf': 'TEMP_VDF="/tmp/quadrix_steam_build_' in mac_upload_text,
        'mac_upload_has_build_first': '--build-first' in mac_upload_text,
        'mac_upload_has_stale_guard': 'QUADRIX_ALLOW_STALE_UPLOAD' in mac_upload_text,
        'mac_build_compiles_bridge': 'Bridge bulunamadı, derleniyor' in mac_build_text,
        'mac_build_rebuilds_stale_bridge': 'Bridge kaynak dosyası daha yeni, yeniden derleme zorlanıyor' in mac_build_text,
        'bridge_specs': bridge_specs,
        'windows_version_bump_specs': windows_version_bump_specs,
        'ci_has_steam_upload': ci_has_steam_upload,
    }


def render_build_and_upload_doc(context: dict[str, object]) -> str:
    windows_depot_id = context['windows_depots'][0][0] if context['windows_depots'] else 'UNKNOWN'
    mac_depot_id = context['mac_depots'][0][0] if context['mac_depots'] else 'UNKNOWN'
    bridge_specs = _render_bullets(context['bridge_specs'])
    version_specs = _render_bullets(context['windows_version_bump_specs'])

    return _normalize(dedent(
        f"""
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

        - Canonical build helper: `{context['windows_build_script']}`
        - Canonical upload helper: `{context['windows_upload_script']}`
        - Canonical spec: `{context['windows_spec']}`
        - Playtest AppID: `{context['windows_app_id']}`
        - Playtest depot: `{windows_depot_id}`
        - Upload helper temp VDF patchliyor: `{'evet' if context['windows_upload_uses_temp_vdf'] else 'hayir'}`
        - Build helper bridge derleyebiliyor: `{'evet' if context['windows_build_compiles_bridge'] else 'hayir'}`

        ### macOS

        - Canonical build helper: `{context['mac_build_script']}`
        - Canonical upload helper: `{context['mac_upload_script']}`
        - Canonical spec: `{context['mac_spec']}`
        - Uretilen uygulama adi: `{context['mac_app_name']}.app`
        - Playtest AppID: `{context['mac_app_id']}`
        - Playtest depot: `{mac_depot_id}`
        - Upload helper temp VDF patchliyor: `{'evet' if context['mac_upload_uses_temp_vdf'] else 'hayir'}`
        - Upload helper `--build-first` destekliyor: `{'evet' if context['mac_upload_has_build_first'] else 'hayir'}`
        - Upload helper stale build guard kullaniyor: `{'evet' if context['mac_upload_has_stale_guard'] else 'hayir'}`

        ### Otomatik Sürüm Artirma

        Windows local version bump bu spec dosyalarinda aktif:

        {_indent_block(version_specs)}

        macOS tarafinda local override bump yok; runtime dogrudan `src/version_base.py` surumunu okur.

        ### Bridge Toplayan Spec Dosyalari

        {_indent_block(bridge_specs)}

        ## Onerilen Komutlar

        ### Windows build

        {_indent_block(_render_fenced_block('powershell', 'pwsh -File .\\scripts\\build\\build_windows_exe.ps1 -Clean'))}

        ### Windows upload

        {_indent_block(_render_fenced_block('powershell', dedent('''
        pwsh -File .\\tools\\steam_upload_playtest.ps1 `
            -SteamCmdPath "C:\\steamcmd\\steamcmd.exe" `
            -SteamUser "BUILD_ACCOUNT" `
            -BuildDescription "Playtest build YYYY-MM-DD" `
            -SetLive ""
        ''').strip()))}

        Dusuk seviye fallback:

        {_indent_block(_render_fenced_block('powershell', f'py -m PyInstaller {_to_windows_path(str(context["windows_spec"]))} --noconfirm'))}

        ### macOS build

        {_indent_block(_render_fenced_block('bash', './scripts/build/build_macos_app.sh --clean'))}

        ### macOS upload

        {_indent_block(_render_fenced_block('bash', './scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"'))}

        Dusuk seviye fallback:

        {_indent_block(_render_fenced_block('bash', f'pyinstaller {context["mac_spec"]} --noconfirm'))}

        ## VDF Politicasi

        - Windows helper varsayilan olarak `{context['windows_app_build_script']}` dosyasini kullanir.
        - macOS helper varsayilan olarak `{context['mac_playtest_vdf']}` dosyasini kullanir; `--full` ile `{context['mac_full_vdf']}` secilir.
        - Track edilen VDF sablonlarinda makineye ozel `ContentRoot` ve `BuildOutput` degeri tutulmaz.
        - `Desc` alani helper script tarafindan runtime'da override edilebilir; VDF icindeki default deger yalnizca sablon gorevi gorur.

        ### Guncel Windows Playtest VDF Sablosu

        {_indent_block(_render_fenced_block('vdf', context['windows_vdf_text']))}

        ### Guncel macOS Playtest VDF Sablosu

        {_indent_block(_render_fenced_block('vdf', context['mac_playtest_vdf_text']))}

        ## Ne Manuel Kaldi?

        - Steam build komutunu elle calistirmak
        - Steam Guard / partner hesabiyla giris yapmak
        - Steamworks panelinde yuklenen BuildID'yi branch'e atamak
        - Gerekirse Playtest `Playable` / branch canli ayarlarini acmak

        ## CI Durumu

        - GitHub Actions Steam upload yapiyor mu: `{'evet' if context['ci_has_steam_upload'] else 'hayir'}`
        - Mevcut CI amaci: test ve lint
        """
    ))


def render_playtest_guide_doc(context: dict[str, object]) -> str:
    windows_depot_id = context['windows_depots'][0][0] if context['windows_depots'] else 'UNKNOWN'
    windows_depot_vdf = context['windows_depots'][0][1] if context['windows_depots'] else 'UNKNOWN'
    mac_depot_id = context['mac_depots'][0][0] if context['mac_depots'] else 'UNKNOWN'
    mac_depot_vdf = context['mac_depots'][0][1] if context['mac_depots'] else 'UNKNOWN'

    return _normalize(dedent(
        f"""
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

        - Playtest AppID: `{context['windows_app_id']}`
        - Windows depot: `{windows_depot_id}` via `{windows_depot_vdf}`
        - macOS depot: `{mac_depot_id}` via `{mac_depot_vdf}`
        - Windows upload helper: `{context['windows_upload_script']}`
        - macOS upload helper: `{context['mac_upload_script']}`
        - Windows helper temp VDF patchliyor: `{'evet' if context['windows_upload_uses_temp_vdf'] else 'hayir'}`
        - macOS helper temp VDF patchliyor: `{'evet' if context['mac_upload_uses_temp_vdf'] else 'hayir'}`

        Onemli fark:

        - Artik repo icindeki VDF dosyasina her build icin `Desc`, `ContentRoot` veya `BuildOutput` yazman gerekmiyor.
        - Helper scriptler bu alanlari gecici VDF olusturarak dolduruyor.
        - Track edilen VDF dosyasinda kalan `Desc` degeri sadece sablon deger.

        ## 3) Windows Playtest Akisi

        ### Build

        {_indent_block(_render_fenced_block('powershell', 'pwsh -File .\\scripts\\build\\build_windows_exe.ps1 -Clean'))}

        ### Upload

        {_indent_block(_render_fenced_block('powershell', dedent('''
        pwsh -File .\\tools\\steam_upload_playtest.ps1 `
            -SteamCmdPath "C:\\SteamworksSDK\\tools\\ContentBuilder\\builder\\steamcmd.exe" `
            -SteamUser "BUILD_ACCOUNT" `
            -BuildDescription "Playtest build YYYY-MM-DD"
        ''').strip()))}

        Dusuk seviye fallback:

        {_indent_block(_render_fenced_block('powershell', dedent(f'''
        py -m PyInstaller {_to_windows_path(str(context['windows_spec']))} --noconfirm
        "C:\\SteamworksSDK\\tools\\ContentBuilder\\builder\\steamcmd.exe" +login BUILD_ACCOUNT +run_app_build ".\\{_to_windows_path(str(context['windows_app_build_script']))}" +quit
        ''').strip()))}

        ## 4) macOS Playtest Akisi

        ### Build

        {_indent_block(_render_fenced_block('bash', './scripts/build/build_macos_app.sh --clean'))}

        ### Upload

        {_indent_block(_render_fenced_block('bash', './scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"'))}

        Notlar:

        - Script varsayilan olarak `{context['mac_playtest_vdf']}` kullanir.
        - `--full` verilirse `{context['mac_full_vdf']}` secilir.
        - `--build-first` tavsiye edilen guvenli akistir.
        - Stale app tespit edilirse upload durdurulur; zorlamak icin `QUADRIX_ALLOW_STALE_UPLOAD=1` gerekir.

        ## 5) Guncel VDF Sablonlari

        ### Windows

        {_indent_block(_render_fenced_block('vdf', context['windows_vdf_text']))}

        ### macOS

        {_indent_block(_render_fenced_block('vdf', context['mac_playtest_vdf_text']))}

        ## 6) Kod Degisince Ne Olur?

        - Kod degisikligi tek basina Steam build'ini degistirmez.
        - Sen yeni build aldiginda guncel kod pakete girer.
        - Sen upload yaptiginda yeni build Steam'e gider.
        - Branch'e canli alma adimi hala Steamworks panelinde manuel yapilir.
        """
    ))


def render_bridge_doc(context: dict[str, object]) -> str:
    bridge_specs = _render_bullets(context['bridge_specs'])

    return _normalize(dedent(
        f"""
        # EXE / .app Derlemede Steam Bridge Entegrasyonu (Zorunlu)

        > Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
        > Bridge akisi build helper ve spec dosyalarindan cekilen guncel bilgilerle yazilir.

        ## Kisa Cevap

        - `steam_net_bridge` olmadan Online PvP acilmaz.
        - Windows canonical build helper bridge artefact yoksa derleyebilir.
        - macOS canonical build helper bridge artefact yoksa veya kaynak daha yeniyse yeniden derleyebilir.
        - Asagidaki spec dosyalari bridge binary arar ve paketlemeye ekler.

        ## Bridge Toplayan Spec Dosyalari

        {_indent_block(bridge_specs)}

        ## Canonical Wrapper Akislari

        ### Windows

        {_indent_block(_render_fenced_block('powershell', 'pwsh -File .\\scripts\\build\\build_windows_exe.ps1 -Clean'))}

        Beklenen davranis:

        - Bridge artefact yoksa `steamworks\\steam_net_bridge\\build.bat` tetiklenir.
        - Artefactler `local_artifacts\\bridge` altina senkronize edilir.
        - Ardindan `{context['windows_spec']}` ile PyInstaller build'i calisir.

        ### macOS

        {_indent_block(_render_fenced_block('bash', './scripts/build/build_macos_app.sh --clean'))}

        Beklenen davranis:

        - Bridge artefact yoksa `steamworks/steam_net_bridge/build.sh` tetiklenir.
        - Bridge kaynak dosyasi artefactten yeniyse rebuild zorlanir.
        - Ardindan `{context['mac_spec']}` ile `.app` build'i alinir.

        ## Low-level Fallback

        ### Windows

        {_indent_block(_render_fenced_block('powershell', dedent(f'''
        cd steamworks\\steam_net_bridge
        build.bat
        cd ..\\..
        py -m PyInstaller {_to_windows_path(str(context['windows_spec']))} --noconfirm
        ''').strip()))}

        ### macOS

        {_indent_block(_render_fenced_block('bash', dedent(f'''
        cd steamworks/steam_net_bridge
        chmod +x build.sh
        ./build.sh
        cd ../..
        pyinstaller {context['mac_spec']} --noconfirm
        ''').strip()))}

        ## Otomasyon Seviyesi

        - Windows helper bridge derleyebiliyor: `{'evet' if context['windows_build_compiles_bridge'] else 'hayir'}`
        - macOS helper bridge derleyebiliyor: `{'evet' if context['mac_build_compiles_bridge'] else 'hayir'}`
        - macOS helper stale bridge rebuild yapiyor: `{'evet' if context['mac_build_rebuilds_stale_bridge'] else 'hayir'}`

        ## Kisa Kontrol Listesi

        - `local_artifacts/bridge` altinda uygun ABI artifact var mi?
        - PyInstaller log'unda `steam_net_bridge eklendi` satiri goruldu mu?
        - Paket build'de Online PvP lobi acma akisi calisiyor mu?
        """
    ))


def render_expected_docs() -> dict[Path, str]:
    context = build_context()
    return {
        ROOT_DIR / 'docs' / 'BUILD_AND_UPLOAD.md': render_build_and_upload_doc(context),
        ROOT_DIR / 'docs' / 'STEAM_PLAYTEST_YAYIN_REHBERI_TR.md': render_playtest_guide_doc(context),
        ROOT_DIR / 'docs' / 'EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md': render_bridge_doc(context),
    }


def collect_outdated_docs() -> list[Path]:
    outdated: list[Path] = []
    for path, expected in render_expected_docs().items():
        current = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        if current != expected:
            outdated.append(path)
    return outdated


def write_docs() -> list[Path]:
    updated: list[Path] = []
    for path, expected in render_expected_docs().items():
        current = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        if current == expected:
            continue
        path.write_text(expected, encoding='utf-8')
        updated.append(path)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Sync generated Markdown docs with canonical script/spec/VDF sources.')
    parser.add_argument('--check', action='store_true', help='Fail if generated docs are out of sync.')
    args = parser.parse_args(argv)

    if args.check:
        outdated = collect_outdated_docs()
        if outdated:
            for path in outdated:
                print(path.relative_to(ROOT_DIR).as_posix())
            return 1
        print('Generated Markdown docs are in sync.')
        return 0

    updated = write_docs()
    if updated:
        for path in updated:
            print(f'updated: {path.relative_to(ROOT_DIR).as_posix()}')
    else:
        print('No Markdown doc changes needed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())