import os
import zipfile
from datetime import date
from xml.sax.saxutils import escape


OUT_PATH = "docs/QUADRIX_Teknik_Detayli_Oyun_Dokumani_2026-03-21.docx"
TODAY = date(2026, 3, 21)

SECTIONS = [
    ("Başlık", "QUADRIX — Aşırı Ayrıntılı Oyun ve Teknik Dokümantasyon"),
    (
        "Meta",
        f"Tarih: {TODAY.strftime('%d.%m.%Y')} | Sürüm referansı: pyproject.toml -> 1.0.26 | Kaynak: repo içi README, docs ve src modül envanteri",
    ),
    (
        "1) Oyun Tanımı",
        "Quadrix, Python 3.12 + pygame-ce ile geliştirilen, klasik Tetris çekirdeğini çok modlu bir ürün yapısına dönüştüren bir arcade/bulmaca oyunudur. Kod tabanı tek bir düz oyun scriptinden ziyade, modüler bir engine + UI + kampanya + Steam + backend proxy yaklaşımıyla organize edilmiştir. Oyunun hedefi, satır temizleme mekaniklerini sadece skor yarışına değil; kampanya hedefleri, mod-spesifik kurallar, kart/güç-up sistemleri, yerel/online PvP akışları ve platforma göre farklı dağıtım senaryolarına da taşımaktır.",
    ),
    (
        "2) Ürün Konumu ve Çalışma Ortamı",
        "Proje bir web oyunu değildir; tamamen Pygame tabanlı masaüstü uygulamadır. Ana giriş noktası kökte main.py olup gerçek oyun akışı src/main.py içinde yürür. Build/dağıtım tarafında PyInstaller spec dosyaları ile Windows/macOS paketleri üretilir. Steam tarafında liderlik tablosu, başarımlar ve ağ özellikleri için client entegrasyonu; ek olarak güvenlik/doğrulama için backend/steam_leaderboard_proxy.py tarafında proxy yaklaşımı mevcuttur.",
    ),
    (
        "3) Yüksek Seviyeli Mimari",
        "Mimari katmanlar halinde okunabilir: (A) çekirdek oyun döngüsü (board/pieces/game), (B) oyun modu katmanı (mode sınıfları ve mod kuralları), (C) kampanya alt sistemi (hedefler, yıldızlar, seviye seçimi), (D) UI/tema/görsel katmanı, (E) ses altyapısı, (F) kullanıcı/profil/başarım katmanı, (G) Steam/leaderboard/PvP ağ katmanı, (H) veri depolama ve ayar yönetimi, (I) test/build/packaging katmanı.",
    ),
    (
        "4) Çekirdek Oyun Mekanikleri",
        "Temel oyun mekanikleri src/game.py, src/board.py, src/pieces.py ve src/constants.py etrafında toplanır. Board veri yapısı satır temizleme, çarpışma doğrulama, kilitleme davranışı ve skor akışının temelini oluşturur. Tetromino tanımları ve dönüş davranışları pieces modülünde toplanır. Gameplay ritmi seviyeye bağlı hızlanma, düşüş zamanlaması, giriş tekrar parametreleri (DAS vb.) ve skor çarpanları üzerinden kontrol edilir. Bu çekirdek, farklı modların üzerine kural ekleyebildiği bir taban sunar.",
    ),
    (
        "5) Oyun Modu Ekosistemi",
        "Kod tabanında standart, ileri ve ekstra modların ayrıştığı bir yapı vardır: src/game_modes.py, src/game_modes_advanced.py ve src/game_modes_extra.py. Sprint/Ultra/Zen/Hardcore gibi modlar temel kuralları farklı hedeflerle sunarken; Survival/Cascade/Daily Challenge benzeri modlar zaman, zorluk eğrisi veya özel hedefler üzerinden davranışı değiştirir. Ayrıca kampanya (src/campaign) ve tutorial (src/tutorial.py) akışları oyunu sadece skor döngüsünden çıkarıp ilerleme odaklı bir yapıya taşır.",
    ),
    (
        "6) Kampanya Alt Sistemi",
        "Kampanya sistemi src/campaign altında izole bir alt paket olarak organize edilir: campaign_mode.py (loop/progress), level_data.py (seviye verileri), objectives.py (hedef sınıfları), power_ups.py (güç-up davranışları), special_blocks.py (özel blok kuralları), campaign_ui.py (ekran katmanı), level_select.py (seçim ekranı ve ölçekleme). Kampanya düzeyinde yıldız bazlı değerlendirme, hedef tamamlanma takibi ve ilerlemenin kayıt edilmesi birlikte çalışır. AGENTS.md notlarına göre başarımlar kampanya ilerleme kaydı sonunda tetiklenir; bu, ürün davranışında kampanya ile achievement sisteminin doğrudan bağlı olduğu anlamına gelir.",
    ),
    (
        "7) PvP ve Çok Oyuncu",
        "İki ayrı çok oyuncu hattı bulunur: yerel PvP (src/pvp_game.py) ve online PvP (src/online_pvp_game.py + Steam networking modülleri). Yerel PvP aynı cihaz üzerinde eşzamanlı oyuncu girişlerini yönetirken; online PvP tarafında oturum/bağlantı/oyun döngüsü için Steam temelli ağ köprüsü kullanılır. Docs klasöründeki ONLINE_PVP_ARCHITECTURE.md ve ONLINE_PVP_FLOW_TR.md dosyaları ağ durum makinesi ve akış notları için referans niteliğindedir.",
    ),
    (
        "8) UI/UX Altyapısı",
        "Menü ve ekran yapısı src/menu.py, src/extras_menu.py, src/guide_screen.py, src/settings_screen_tabbed.py, src/graphics_menu.py ve src/ui_components.py çevresinde toplanır. UI teması src/ui_theme.py ile merkezileştirilmiştir (UIFonts/UIColors/UIStyle). AGENTS.md’de belirtilen ölçekleme kuralları özellikle responsive davranış için kritiktir: menu.py içindeki _menu_panel_content_scale() (1920x1080 referansı), campaign/level_select.py içindeki font ölçeği formülü, extras_menu.py içindeki _extras_ui_scale(). Bu yaklaşım farklı çözünürlüklerde tutarlı panel/typography üretmeyi hedefler.",
    ),
    (
        "9) Render ve Görsellik",
        "Görsel katmanda tema, blok stili ve arka plan efektleri ayrı modüllere bölünmüştür: src/block_styles.py, src/themes.py, src/mode_skins.py, src/background.py, src/background_effects.py, src/renderers/jelly_renderer.py. Bu ayrım, oyun kurallarından bağımsız görsel varyasyon üretimini kolaylaştırır. emoji_renderer ve text_cache gibi yardımcı modüller, hem ifade gücü hem performans tarafında destekleyici rol oynar.",
    ),
    (
        "10) Ses Mimarisi",
        "src/sound.py müzik ve efekt katmanını yönetir. AGENTS.md’de işaretlenen önemli bir davranış: set_music_playlist(shuffle=False) ile shuffle desteği. Bu özellik settings_manager tarafındaki music_shuffle anahtarıyla ürün davranışına bağlanır. Ses sisteminde ürün ölçeği açısından kritik konu; mod/ekran geçişlerinde müzik kuyruğu yönetimi, ses seviyelerinin merkezi ayarlarla tutarlı kalması ve oyundan menüye dönüşte ses durumunun deterministik olmasıdır.",
    ),
    (
        "11) Kullanıcı, Profil, Avatar, Skor",
        "Kullanıcı yönetimi src/user_manager.py ve src/user_screens.py etrafında; avatar üretim/düzenleme src/avatar_editor.py + src/avatar_presets.py ile sağlanır. Skor yönetimi src/score_manager.py; başarımlar src/achievements.py modülünde toplanır. Bu ayrım, gameplay skor hesabı ile meta-progression (başarım/profil) sistemini birbirinden ayırır.",
    ),
    (
        "12) Steam Entegrasyonu",
        "Steam entegrasyon yüzeyi src/steam_integration.py ve src/steam_leaderboards.py dosyalarıdır. Liderlik tablosu akışı gerektiğinde backend/steam_leaderboard_proxy.py üzerinden güvenlik odaklı bir doğrulama/aktarım hattına bağlanabilir. Dokümantasyon tarafında docs/STEAM_* ve SECURITY_REVIEW_STEAM_LEADERBOARD_TR.md dosyaları operasyonel ve güvenlik perspektifini tamamlar.",
    ),
    (
        "13) Lokalizasyon ve Çok Dilli UI",
        "Lokalizasyon merkezi src/localization.py içinde t() fonksiyonu etrafında çalışır. Dil desteği AGENTS.md’ye göre TR, EN, DE, FR, ES, IT, PT, JA, ZH, KO setini içerir. src/ui_language_profile.py dosyası CJK gibi karakter setleri için font/yerleşim uyarlama katmanı sağlar. Ürün kalitesi açısından bu, tek font varsayımı yerine dil-profil yaklaşımı kullanıldığı anlamına gelir.",
    ),
    (
        "14) Ayar Yönetimi ve Depolama",
        "Ayarların ana kontrol noktası src/settings_manager.py dosyasıdır. Veri yazma/güvenilirlik tarafında src/atomic_io.py ve src/data_paths.py gibi modüller platforma göre güvenli okuma-yazma akışı sağlar. Repo belleğinde geçen steam cloud ve save-root notları, uygulamanın yerel + bulut senaryoları için geçiş/migrasyon ihtiyacını ciddiye aldığını gösterir. Bu katman, oyunun bozulmaya dayanıklı kullanıcı verisi hedefi açısından kritiktir.",
    ),
    (
        "15) Girdi ve Platform Katmanı",
        "Klavye/gamepad girdileri src/gamepad_manager.py ve ilgili ayar yapılarıyla yönetilir. Platform farklılıkları src/platform_utils.py, src/file_dialog.py ve src/tk_compat.py ile ele alınır. Bu yapı macOS dahil farklı pencereleme ve dosya diyaloğu davranışlarında koşullu uyumluluk sunar.",
    ),
    (
        "16) Varlık Yönetimi ve Performans",
        "Varlık yükleme tarafında src/asset_manager.py temel rol oynar. Render performansını korumak için text cache ve yüzey cache/LRU benzeri yardımcı modüller kullanılır (örn. text_cache.py, surface_lru_cache.py, effect_surface_cache.py). Amaç, sık çizilen UI/metin/efektlerin tekrar üretim maliyetini düşürmektir.",
    ),
    (
        "17) Proje Yapısı ve İşletimsel Organizasyon",
        "Kök dizin, kodu ve operasyonu ayıran net bir düzen taşır: src (uygulama), tests (doğrulama), scripts (otomasyon), docs (operasyonel/teknik bilgi), packaging/specs/requirements (dağıtım), backend (servis/proxy), assets/music/font/backgrounds (içerik). Bu yapı tek kişilik geliştirmeden ekip ölçeğine geçişte sürdürülebilirlik sağlar.",
    ),
    (
        "18) Test Stratejisi",
        "README ve AGENTS.md’ye göre testler tests altında test_*.py deseniyle çalışır; önerilen komut ./scripts/test/run_tests.sh -q veya pytest’tir. pyproject.toml içinde pytest path ayarları mevcuttur (pythonpath: ., src; testpaths: tests). Bu düzen, import stabilitesi ve CI benzeri çalıştırma için önemlidir.",
    ),
    (
        "19) Build ve Paketleme",
        "Proje PyInstaller tabanlı spec dosyaları kullanır (kökte tetris*.spec, ek olarak packaging/specs). macOS için scripts/build/build_macos_app.sh ve ilişkili dokümanlar (docs/MACOS_* ve BUILD_AND_UPLOAD.md) dağıtım hattını tanımlar. Bu, oyun geliştirmesinin yanında release engineering disiplininin de aktif olduğu anlamına gelir.",
    ),
    (
        "20) Güvenlik ve Operasyon Notları",
        "Leaderboard/Steam akışında güvenlik inceleme dökümanları ve proxy yaklaşımı bulunur. Bu tasarım, client’ın tek başına mutlak güvenilir olmadığı; kritik skor/istatistik yazımlarında sunucu tarafı doğrulamanın tercih edildiğini gösterir. Ayrıca docs klasöründe runbook/checklist türü dosyaların varlığı, canlı ortam operasyonları için prosedür tanımlandığını kanıtlar.",
    ),
    (
        "21) Oyun Deneyimi Açısından Sonuç",
        "Quadrix sadece bir Tetris klonu değil; modüler oyun motoru, kampanya, çoklu oyun modu, profil/başarım, çok dillilik, Steam ekosistemi, yerel/online PvP ve platforma özel dağıtım süreçleri bulunan bir ürün haline gelmiştir. Teknik olarak kod tabanı, prototip oyundan ürünleşmiş masaüstü oyuna geçiş için gereken katmanların çoğunu barındırır.",
    ),
    (
        "22) Dosya Bazlı Hızlı Referans",
        "Ana giriş: main.py ve src/main.py | Çekirdek: src/game.py, src/board.py, src/pieces.py, src/constants.py | Modlar: src/game_modes.py, src/game_modes_advanced.py, src/game_modes_extra.py | Kampanya: src/campaign/* | PvP: src/pvp_game.py, src/online_pvp_game.py | UI: src/menu.py, src/settings_screen_tabbed.py, src/ui_components.py, src/ui_theme.py | Ses: src/sound.py | Steam: src/steam_integration.py, src/steam_leaderboards.py, backend/steam_leaderboard_proxy.py | Lokalizasyon: src/localization.py, src/ui_language_profile.py | Test: tests/ + scripts/test/run_tests.sh | Build: scripts/build/* ve tetris*.spec",
    ),
    (
        "23) Doküman Kaynakları",
        "README.md; docs/PROJECT_STRUCTURE_TR.md; docs/BUILD_AND_UPLOAD.md; docs/ONLINE_PVP_ARCHITECTURE.md; docs/ONLINE_PVP_FLOW_TR.md; docs/STEAM_ACHIEVEMENTS_SETUP.md; docs/STEAM_LEADERBOARD_OPERATIONS_TR.md; docs/SECURITY_REVIEW_STEAM_LEADERBOARD_TR.md; docs/guides/README_FULL.md.",
    ),
    (
        "24) Kapanış",
        "Bu doküman repo içeriğine dayanarak hazırlanmış teknik bir ürün özeti/haritasıdır. Kod seviyesi implementasyon detayları için her modül doğrudan incelenmeli; operasyonel süreçler için docs altındaki ilgili runbook/checklist dosyaları takip edilmelidir.",
    ),
]


def paragraph(text: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def build_document_xml() -> str:
    body_parts = []
    for title, content in SECTIONS:
        body_parts.append(paragraph(title))
        for chunk in content.split("\n"):
            body_parts.append(paragraph(chunk))
        body_parts.append(paragraph(""))

    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
      <w:cols w:space="708"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>
'''


def main() -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'''

    core_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>QUADRIX Teknik Detaylı Oyun Dokümanı</dc:title>
  <dc:creator>GitHub Copilot</dc:creator>
  <cp:lastModifiedBy>GitHub Copilot</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-03-21T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-03-21T00:00:00Z</dcterms:modified>
</cp:coreProperties>
'''

    app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>
'''

    with zipfile.ZipFile(OUT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("_rels/.rels", rels_xml)
        docx_zip.writestr("word/document.xml", build_document_xml())
        docx_zip.writestr("docProps/core.xml", core_xml)
        docx_zip.writestr("docProps/app.xml", app_xml)

    print(OUT_PATH)


if __name__ == "__main__":
    main()
