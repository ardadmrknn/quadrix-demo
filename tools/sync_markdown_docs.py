from __future__ import annotations

import argparse
import re
from pathlib import Path
from textwrap import dedent, indent


ROOT_DIR = Path(__file__).resolve().parent.parent

# Demo deposunun GERÇEK kaynak envanteri (2026-10-11 onarımi):
# - scripts/build/build_windows_exe.ps1 ve scripts/build/steam_upload_macos.sh
#   445a0da (2026-06-14) commit'inde silindi ve geri gelmedi.
# - scripts/build/write_demo_config.py ve scripts/build/build_macos_demo_app.sh
#   repo geçmişinde HİÇ yok (kullanıcı makinesinde kalmış izlenmeyen taslaklar).
# Bu araç yalnızca repoya commit'lenmiş kaynaklardan üretir; PS1 içinden
# SpecFile varsayanı türetilemediği için kanonik demo spec'leri burada
# tanımlanır (packaging/specs/ altında gerçek dosyalardır).
WINDOWS_DEMO_SPEC = 'packaging/specs/tetris_demo.spec'
MAC_DEMO_SPEC = 'packaging/specs/tetris_demo_macos_allinone.spec'
MAC_DEMO_APP_NAME = 'Quadrix Demo'


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
    windows_upload_text = _read_text('tools/steam_upload_playtest.ps1')
    windows_demo_upload_text = _read_text('tools/steam_upload_demo.ps1')
    mac_build_text = _read_text('scripts/build/build_macos_app.sh')
    windows_demo_vdf_text = _read_text('steamworks/scripts/app_build_demo.vdf')
    mac_demo_vdf_text = _read_text('steamworks/scripts/app_build_demo_macos.vdf')
    windows_playtest_vdf_text = _read_text('steamworks/scripts/app_build_playtest.vdf')
    mac_playtest_vdf_text = _read_text('steamworks/scripts/app_build_playtest_macos.vdf')
    ci_text = _read_text('.github/workflows/ci.yml')
    demo_config_text = _read_text('src/demo_config.py')

    # Playtest helper'ının AppBuildScript varsayanı boş bırakılmıştır; runtime'da
    # geçici VDF üretir. Demo sarmalayıcısı (steam_upload_demo.ps1) kendi
    # varsayanını app_build_demo.vdf'ye bağlar.
    windows_app_build_script_raw = _extract_ps1_string_default(windows_upload_text, 'AppBuildScript')
    windows_app_build_script_default_is_synthesized = not windows_app_build_script_raw.strip()

    mac_spec = _clean_repo_relative_path(_extract_shell_assignment(mac_build_text, 'SPEC_FILE'))
    mac_app_name = _extract_shell_assignment(mac_build_text, 'APP_NAME')

    cap_match = re.search(r'(?m)^DEMO_MYSTERY_SCORE_CAP\s*=\s*(\d+)\s*$', demo_config_text)
    if not cap_match:
        raise ValueError('DEMO_MYSTERY_SCORE_CAP not found in src/demo_config.py')
    demo_mystery_score_cap = cap_match.group(1)

    bridge_specs = _relative_paths_for_specs_containing('get_bridge_binaries(')
    windows_version_bump_specs = _relative_paths_for_specs_containing("bump_platform_version(REPO_ROOT, 'windows')")

    ci_has_steam_upload = any(
        token in ci_text
        for token in ('run_app_build', 'steam_upload_demo', 'steam_upload_playtest')
    )

    return {
        'windows_demo_spec': WINDOWS_DEMO_SPEC,
        'mac_demo_spec': MAC_DEMO_SPEC,
        'mac_demo_app_name': MAC_DEMO_APP_NAME,
        'windows_upload_script': 'tools/steam_upload_demo.ps1',
        'windows_playtest_upload_script': 'tools/steam_upload_playtest.ps1',
        'windows_app_build_script': 'steamworks/scripts/app_build_demo.vdf',
        'windows_app_build_script_default_is_synthesized': windows_app_build_script_default_is_synthesized,
        'windows_demo_app_id': _extract_vdf_field(windows_demo_vdf_text, 'AppID'),
        'windows_demo_desc': _extract_vdf_field(windows_demo_vdf_text, 'Desc'),
        'windows_demo_depots': _extract_vdf_depots(windows_demo_vdf_text),
        'windows_demo_vdf_text': windows_demo_vdf_text.rstrip(),
        'mac_demo_app_id': _extract_vdf_field(mac_demo_vdf_text, 'AppID'),
        'mac_demo_desc': _extract_vdf_field(mac_demo_vdf_text, 'Desc'),
        'mac_demo_depots': _extract_vdf_depots(mac_demo_vdf_text),
        'mac_demo_vdf_text': mac_demo_vdf_text.rstrip(),
        'windows_playtest_app_id': _extract_vdf_field(windows_playtest_vdf_text, 'AppID'),
        'windows_playtest_depots': _extract_vdf_depots(windows_playtest_vdf_text),
        'mac_playtest_app_id': _extract_vdf_field(mac_playtest_vdf_text, 'AppID'),
        'mac_playtest_depots': _extract_vdf_depots(mac_playtest_vdf_text),
        'mac_spec': mac_spec,
        'mac_build_script': 'scripts/build/build_macos_app.sh',
        'mac_app_name': mac_app_name,
        'mac_playtest_vdf': 'steamworks/scripts/app_build_playtest_macos.vdf',
        'demo_mystery_score_cap': demo_mystery_score_cap,
        'windows_upload_uses_temp_vdf': '.tmp_app_build_' in windows_upload_text and 'Set-VdfField' in windows_upload_text,
        'windows_upload_checks_content_root_appid': 'ContentRoot AppID' in windows_upload_text,
        'mac_build_compiles_bridge': 'Bridge bulunamadı, derleniyor' in mac_build_text,
        'mac_build_rebuilds_stale_bridge': 'Bridge kaynak dosyası daha yeni, yeniden derleme zorlanıyor' in mac_build_text,
        'bridge_specs': bridge_specs,
        'windows_version_bump_specs': windows_version_bump_specs,
        'ci_has_steam_upload': ci_has_steam_upload,
    }


def render_build_and_upload_doc(context: dict[str, object]) -> str:
    windows_demo_depot_id = context['windows_demo_depots'][0][0] if context['windows_demo_depots'] else 'UNKNOWN'
    mac_demo_depot_id = context['mac_demo_depots'][0][0] if context['mac_demo_depots'] else 'UNKNOWN'
    bridge_specs = _render_bullets(context['bridge_specs'])
    version_specs = _render_bullets(context['windows_version_bump_specs'])
    windows_demo_upload_command = dedent(r'''
        pwsh -File .\tools\steam_upload_demo.ps1 `
            -SteamCmdPath "C:\steamcmd\steamcmd.exe" `
            -SteamUser "BUILD_ACCOUNT" `
            -BuildDescription "Demo build YYYY-MM-DD" `
            -SetLive ""
    ''').strip()
    windows_demo_pyinstaller_command = f'py -m PyInstaller {_to_windows_path(str(context["windows_demo_spec"]))} --noconfirm'

    return _normalize(dedent(
        f"""
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

        - Kanonik demo spec: `{context['windows_demo_spec']}`
        - Kanonik upload helper: `{context['windows_upload_script']}` (playtest helper'ini `Target='demo'` ile sarmalar)
        - Playtest helper (paylasilan cekirdek): `{context['windows_playtest_upload_script']}`
        - Demo AppID: `{context['windows_demo_app_id']}`
        - Demo depot: `{windows_demo_depot_id}`
        - Upload helper temp VDF patchliyor: `{'evet' if context['windows_upload_uses_temp_vdf'] else 'hayir'}`
        - Upload helper ContentRoot AppID kimlik kontrolu yapiyor: `{'evet' if context['windows_upload_checks_content_root_appid'] else 'hayir'}`

        ### macOS (Demo)

        - Kanonik build helper: `{context['mac_build_script']}` (tam surum varsayani; `--spec` ile demo spec secilir)
        - Kanonik demo spec: `{context['mac_demo_spec']}`
        - Demo uygulama adi: `{context['mac_demo_app_name']}.app`
        - Demo AppID: `{context['mac_demo_app_id']}`
        - Demo depot: `{mac_demo_depot_id}`
        - Build helper bridge derleyebiliyor: `{'evet' if context['mac_build_compiles_bridge'] else 'hayir'}`
        - Upload helper: repoda YOK — yukleme manuel steamcmd akisiyla

        ### Otomatik Surum Artirma

        Windows local version bump bu spec dosyalarinda aktif (demo spec'lerinde bump YOK):

        {_indent_block(version_specs)}

        macOS tarafinda local override bump yok; runtime dogrudan `src/version_base.py` surumunu okur.

        ### Bridge Toplayan Spec Dosyalari

        {_indent_block(bridge_specs)}

        ## Onerilen Komutlar

        ### Windows demo build (manuel — helper yok)

        {_indent_block(_render_fenced_block('powershell', windows_demo_pyinstaller_command))}

        Not: derleme oncesi `src/demo_config.py` icinde `IS_DEMO = True` yapilmali, derleme sonrasi geri alinmali (bu gecisi otomatikleyen script repoya commit'lenmemis).

        ### Windows demo upload

        {_indent_block(_render_fenced_block('powershell', windows_demo_upload_command))}

        ### macOS demo build

        {_indent_block(_render_fenced_block('bash', f'./scripts/build/build_macos_app.sh --spec {context["mac_demo_spec"]} --app-name "{context["mac_demo_app_name"]}" --clean'))}

        Dusuk seviye fallback:

        {_indent_block(_render_fenced_block('bash', f'pyinstaller {context["mac_demo_spec"]} --noconfirm'))}

        ### macOS demo upload (manuel — helper yok)

        VDF sablonunda `ContentRoot` ve `BuildOutput` bos birakilmistir; manuel akista once doldurulur:

        {_indent_block(_render_fenced_block('bash', f'steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/app_build_demo_macos.vdf +quit'))}

        ## VDF Politicasi

        - Windows demo helper varsayilan olarak `{context['windows_app_build_script']}` dosyasini kullanir.
        - Playtest helper'in AppBuildScript varsayani bos ise gecici VDF uretir: `{'evet' if context['windows_app_build_script_default_is_synthesized'] else 'hayir'}`
        - Track edilen VDF sablonlarinda makineye ozel `ContentRoot` ve `BuildOutput` degeri tutulmaz.
        - `Desc` alani helper script tarafindan runtime'da override edilebilir; VDF icindeki default deger yalnizca sablon gorevi gorur.

        ### Guncel Windows Demo VDF Sablonu

        {_indent_block(_render_fenced_block('vdf', context['windows_demo_vdf_text']))}

        ### Guncel macOS Demo VDF Sablonu

        {_indent_block(_render_fenced_block('vdf', context['mac_demo_vdf_text']))}

        ## Ne Manuel Kaldi?

        - Steam build komutunu elle calistirmak
        - Steam Guard / partner hesabiyla giris yapmak
        - Steamworks panelinde yuklenen BuildID'yi branch'e atamak
        - Gerekirse Demo `Playable` / branch canli ayarlarini acmak

        ## CI Durumu

        - GitHub Actions Steam upload yapiyor mu: `{'evet' if context['ci_has_steam_upload'] else 'hayir'}`
        - Mevcut CI amaci: test ve lint
        """
    ))


def render_playtest_guide_doc(context: dict[str, object]) -> str:
    windows_depot_id = context['windows_playtest_depots'][0][0] if context['windows_playtest_depots'] else 'UNKNOWN'
    windows_depot_vdf = context['windows_playtest_depots'][0][1] if context['windows_playtest_depots'] else 'UNKNOWN'
    mac_depot_id = context['mac_playtest_depots'][0][0] if context['mac_playtest_depots'] else 'UNKNOWN'
    mac_depot_vdf = context['mac_playtest_depots'][0][1] if context['mac_playtest_depots'] else 'UNKNOWN'
    windows_playtest_upload_command = dedent(r'''
        pwsh -File .\tools\steam_upload_playtest.ps1 `
            -SteamCmdPath "C:\SteamworksSDK\tools\ContentBuilder\builder\steamcmd.exe" `
            -SteamUser "BUILD_ACCOUNT" `
            -BuildDescription "Playtest build YYYY-MM-DD"
    ''').strip()
    windows_playtest_pyinstaller_command = f'py -m PyInstaller {_to_windows_path(str(context["windows_demo_spec"]))} --noconfirm'

    return _normalize(dedent(
        f"""
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

        - Playtest AppID: `{context['windows_playtest_app_id']}`
        - Windows depot: `{windows_depot_id}` via `{windows_depot_vdf}`
        - macOS depot: `{mac_depot_id}` via `{mac_depot_vdf}`
        - Windows playtest helper: `{context['windows_playtest_upload_script']}`
        - macOS upload helper: repoda YOK — manuel steamcmd akisi
        - Windows helper temp VDF patchliyor: `{'evet' if context['windows_upload_uses_temp_vdf'] else 'hayir'}`

        Onemli fark:

        - Artik repo icindeki VDF dosyasina her build icin `Desc`, `ContentRoot` veya `BuildOutput` yazman gerekmiyor.
        - Windows helper bu alanlari gecici VDF olusturarak dolduruyor.
        - Track edilen VDF dosyasinda kalan `Desc` degeri sadece sablon deger.

        ## 3) Windows Playtest Akisi

        ### Build (manuel — build helper repoda yok)

        {_indent_block(_render_fenced_block('powershell', windows_playtest_pyinstaller_command))}

        ### Upload

        {_indent_block(_render_fenced_block('powershell', windows_playtest_upload_command))}

        ## 4) macOS Playtest Akisi

        ### Build

        {_indent_block(_render_fenced_block('bash', './scripts/build/build_macos_app.sh --clean'))}

        ### Upload (manuel — helper repoda yok)

        {_indent_block(_render_fenced_block('bash', f'steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/{context["mac_playtest_vdf"].split("/")[-1]} +quit'))}

        Notlar:

        - macOS yuklemede VDF sablonundaki `ContentRoot`/`BuildOutput` once doldurulur.
        - Stale app tespiti yapan sarmalayici repoda yok; yukleme oncesi taze build alinmalidir.

        ## 5) Guncel VDF Sablonlari

        ### Windows playtest

        {_indent_block(_render_fenced_block('vdf', _read_text('steamworks/scripts/app_build_playtest.vdf').rstrip()))}

        ### macOS playtest

        {_indent_block(_render_fenced_block('vdf', _read_text('steamworks/scripts/app_build_playtest_macos.vdf').rstrip()))}

        ## 6) Kod Degisince Ne Olur?

        - Kod degisikligi tek basina Steam build'ini degistirmez.
        - Sen yeni build aldiginda guncel kod pakete girer.
        - Sen upload yaptiginda yeni build Steam'e gider.
        - Branch'e canli alma adimi hala Steamworks panelinde manuel yapilir.
        """
    ))


def render_bridge_doc(context: dict[str, object]) -> str:
    bridge_specs = _render_bullets(context['bridge_specs'])
    windows_low_level_command = dedent(f'''
        cd steamworks\\steam_net_bridge
        build.bat
        cd ..\\..
        py -m PyInstaller {_to_windows_path(str(context["windows_demo_spec"]))} --noconfirm
    ''').strip()

    return _normalize(dedent(
        f"""
        # EXE / .app Derlemede Steam Bridge Entegrasyonu (Zorunlu)

        > Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
        > Bridge akisi build helper ve spec dosyalarindan cekilen guncel bilgilerle yazilir.

        ## Kisa Cevap

        - `steam_net_bridge` olmadan Online PvP acilmaz.
        - Windows tarafinda build helper repoda YOK: bridge derleme ve PyInstaller adimi manuel.
        - macOS canonical build helper bridge artefact yoksa veya kaynak daha yeniyse yeniden derleyebilir.
        - Asagidaki spec dosyalari bridge binary arar ve paketlemeye ekler.

        ## Bridge Toplayan Spec Dosyalari

        {_indent_block(bridge_specs)}

        ## Canonical Wrapper Akislari

        ### Windows (manuel — helper repoda yok)

        {_indent_block(_render_fenced_block('powershell', windows_low_level_command))}

        Beklenen davranis:

        - Bridge artefact yoksa `steamworks\\steam_net_bridge\\build.bat` elle tetiklenir.
        - Artefactler `local_artifacts\\bridge` altina senkronize edilir.
        - Ardindan `{context['windows_demo_spec']}` ile PyInstaller build'i calisir.

        ### macOS

        {_indent_block(_render_fenced_block('bash', f'./scripts/build/build_macos_app.sh --spec {context["mac_demo_spec"]} --app-name "{context["mac_demo_app_name"]}" --clean'))}

        Beklenen davranis:

        - Bridge artefact yoksa `steamworks/steam_net_bridge/build.sh` tetiklenir.
        - Bridge kaynak dosyasi artefactten yeniyse rebuild zorlanir.
        - Ardindan `{context['mac_demo_spec']}` ile `.app` build'i alinir.

        ## Otomasyon Seviyesi

        - Windows helper bridge derleyebiliyor: repoda helper YOK (445a0da'da silindi)
        - macOS helper bridge derleyebiliyor: `{'evet' if context['mac_build_compiles_bridge'] else 'hayir'}`
        - macOS helper stale bridge rebuild yapiyor: `{'evet' if context['mac_build_rebuilds_stale_bridge'] else 'hayir'}`

        ## Kisa Kontrol Listesi

        - `local_artifacts/bridge` altinda uygun ABI artifact var mi?
        - PyInstaller log'unda `steam_net_bridge eklendi` satiri goruldu mu?
        - Paket build'de Online PvP lobi acma akisi calisiyor mu?
        """
    ))


def render_macos_demo_upload_guide(context: dict[str, object]) -> str:
    mac_demo_depot_id = context['mac_demo_depots'][0][0] if context['mac_demo_depots'] else 'UNKNOWN'
    formatted_cap = f"{int(str(context['demo_mystery_score_cap'])):,}".replace(",", ".")

    return _normalize(dedent(
        f"""
        # macOS Demo Derleme ve Steam Yükleme Rehberi

        > Bu dosya `tools/sync_markdown_docs.py` tarafindan uretilir.
        > Kalici degisiklik icin kaynak script/spec/VDF dosyasini veya sync scriptini guncelle.

        Bu doküman, Quadrix Demo oyununun macOS platformu için derlenmesi ve Steam'e yüklenmesi sırasında izlenen adımları, doğrulanan kuralları ve teknik detayları içerir. İleride yapılacak derleme/yükleme işlemlerinde referans kılavuz olarak kullanılabilir.

        ---

        ## 1. Uygulama Yapısı ve Kurallar (Windows Eşleşmesi)

        Oyun kurallarının Windows demo sürümüyle birebir aynı olması sağlanmıştır:
        - **Mystery (Kart Ustalığı) Modu Sınırı**: Demodaki skor sınırı **{formatted_cap}**'dur. Bu skora ulaşıldığında oyun dondurulur ve "Demo Tamamlandı" paneli açılır.
        - **Konfigürasyon Kaynağı**: `src/demo_config.py` içindeki `DEMO_MYSTERY_SCORE_CAP = {context['demo_mystery_score_cap']}` değişkeni üzerinden yönetilir (bu değeri otomatiklayan `write_demo_config.py` repoya hiç commit'lenmedi).
        - **Demo Modu Aktivasyonu**: Derleme öncesi `src/demo_config.py` içinde `IS_DEMO = True` yapılır; derleme bittiğinde geliştirme ortamının bozulmaması için manuel olarak geri alınır.

        ---

        ## 2. Derleme Süreci (Build)

        ### Hazırlık ve Test
        Derleme öncesi tüm kod tabanının kararlılığını doğrulamak için test suite koşulur:

        ```bash
        ./scripts/test/run_tests.sh -q
        ```

        ### macOS Demo Bundle Derleme
        Build helper'ın `--spec`/`--app-name` geçersiz kılmalarıyla demo paketi üretilir:

        ```bash
        ./scripts/build/build_macos_app.sh --spec {context['mac_demo_spec']} --app-name "{context['mac_demo_app_name']}" --clean
        ```

        - **Üretilen Paket**: `dist/{context['mac_demo_app_name']}.app`
        - **İçerik Kontrolü**: `Contents/MacOS/` altında executable, `Contents/Frameworks/` altında native Steam API dylib'i ve derlenmiş `steam_net_bridge` kütüphanesi entegre edilir.

        ---

        ## 3. Steam'e Yükleme Süreci (Upload)

        Demo macOS upload sarmalayıcısı repoda YOK (`scripts/build/steam_upload_macos.sh`, 445a0da'da silindi). Yükleme manuel steamcmd akışıyla yapılır:

        ### Yükleme Parametreleri
        - **App ID**: `{context['mac_demo_app_id']}` (Quadrix Demo)
        - **Depot ID**: `{mac_demo_depot_id}` (macOS Demo Depot)
        - **VDF Şablonu**: `steamworks/scripts/app_build_demo_macos.vdf` (`ContentRoot`/`BuildOutput` alanları yükleme öncesi doldurulur)

        ### Çalıştırılan Komut (düşük seviye)

        ```bash
        steamcmd +login BUILD_ACCOUNT +run_app_build ./steamworks/scripts/app_build_demo_macos.vdf +quit
        ```

        ### Yükleme Sırasında Doğrulanan Deneyimler
        1. **NFC Normalizasyonu (macOS NFD Fix)**: macOS dosya adlarını ayrıştırılmış (decomposed - NFD) formda tutar. SteamCMD bu encoding'i manifest dosyalarında kabul etmediğinden (HTTP 400), upload öncesi `/tmp/` altındaki tüm dosya adları NFC formuna normalize edilmelidir.
        2. **Steam Guard**: Yükleme sırasında SteamCMD şifre sorar; hesapta tanımlı Steam Guard Mobil Kimlik Doğrulayıcı onayı mobil uygulama üzerinden verilerek oturum açılır.

        ---

        ## 4. Sonraki Adımlar ve Canlıya Alma

        Yüklenen build'in son kullanıcılara ulaşabilmesi için şu adımlar takip edilmelidir:
        1. [Steamworks Partner Paneli](https://partner.steamgames.com)'ne giriş yapın.
        2. **AppID {context['mac_demo_app_id']} (Quadrix Demo)** sayfasına gidin.
        3. **SteamPipe** -> **Builds** sekmesine tıklayın.
        4. Yeni yüklenen derlemeyi (BuildID) uygun test branch'ine (örn: `beta`) ya da doğrudan oyuncuların indirmesi için varsayılan (`default`/`public`) branch'e atayın ve değişiklikleri kaydedin.
        """
    ))


def render_expected_docs() -> dict[Path, str]:
    context = build_context()
    return {
        ROOT_DIR / 'docs' / 'BUILD_AND_UPLOAD.md': render_build_and_upload_doc(context),
        ROOT_DIR / 'docs' / 'STEAM_PLAYTEST_YAYIN_REHBERI_TR.md': render_playtest_guide_doc(context),
        ROOT_DIR / 'docs' / 'EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md': render_bridge_doc(context),
        ROOT_DIR / 'docs' / 'MACOS_DEMO_DERLEME_VE_STEAM_YUKLEME_REHBERI.md': render_macos_demo_upload_guide(context),
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
