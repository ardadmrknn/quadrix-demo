"""Quadrix tanitim sunumu (.pptx) uretici.

Bu script repodaki mevcut gorsel assetlerini kullanarak Turkce bir Quadrix
pitch sunumu uretir. Cikti `local_artifacts/Quadrix_Sunum.pptx` altina yazilir;
repoya commit edilmesi tasarlanmamistir.

Kullanim:
    /Users/burakyasayan/quadrix-main/local_artifacts/pptx_venv/bin/python \
        tools/build_quadrix_pitch_pptx.py

Tasarim notu:
    - Slayt boyutu 16:9, 1280x720 pt (varsayilan).
    - Koyu lacivert/mor gradient arka plan, neon accent.
    - Tum metin TR, basliklar buyuk, govde okunakli.
"""
from __future__ import annotations

import os
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

# ----- Yollar ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT_DIR = ROOT / "local_artifacts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "Quadrix_Sunum.pptx"

# ----- Renk paleti ----------------------------------------------------------
BG_DARK = RGBColor(0x0B, 0x0E, 0x1F)      # ana arka plan (koyu lacivert)
BG_PANEL = RGBColor(0x14, 0x1A, 0x33)     # panel zemini
ACCENT_CYAN = RGBColor(0x4A, 0xE0, 0xFF)  # neon mavi
ACCENT_PURPLE = RGBColor(0x9B, 0x6CFF & 0xFF, 0xFF)  # mor
ACCENT_PINK = RGBColor(0xFF, 0x4D, 0xA6)  # sicak vurgu
TEXT_WHITE = RGBColor(0xF2, 0xF4, 0xFA)
TEXT_DIM = RGBColor(0xB6, 0xBE, 0xD6)
TEXT_MUTED = RGBColor(0x8A, 0x92, 0xA8)

# Mor netlestirilmis
ACCENT_PURPLE = RGBColor(0x9B, 0x6C, 0xFF)


# ----- Yardimcilar ----------------------------------------------------------
def add_full_bg(slide, color: RGBColor = BG_DARK) -> None:
    """Slayt arka planini duz renkle doldurur."""
    left = top = 0
    width = slide.part.package.presentation_part.presentation.slide_width
    height = slide.part.package.presentation_part.presentation.slide_height
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.line.fill.background()
    rect.shadow.inherit = False
    # arkaya it
    spTree = rect._element.getparent()
    spTree.remove(rect._element)
    spTree.insert(2, rect._element)


def add_band(slide, x_emu, y_emu, w_emu, h_emu, color: RGBColor) -> None:
    """Dekoratif renkli serit/cubuk ekler."""
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x_emu, y_emu, w_emu, h_emu)
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()


def add_text(
    slide,
    text: str,
    left,
    top,
    width,
    height,
    *,
    size: int = 18,
    bold: bool = False,
    color: RGBColor = TEXT_WHITE,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    font_name: str = "Helvetica Neue",
):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor

    lines = text.split("\n") if isinstance(text, str) else list(text)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.name = font_name
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return tb


def add_bullet_list(
    slide,
    items,
    left,
    top,
    width,
    height,
    *,
    size: int = 18,
    color: RGBColor = TEXT_WHITE,
    bullet: str = "▸",
    bullet_color: RGBColor = ACCENT_CYAN,
    line_spacing: float = 1.25,
    font_name: str = "Helvetica Neue",
):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0

    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = line_spacing
        p.alignment = PP_ALIGN.LEFT
        # bullet
        b = p.add_run()
        b.text = f"{bullet}  "
        b.font.name = font_name
        b.font.size = Pt(size)
        b.font.bold = True
        b.font.color.rgb = bullet_color
        # body
        body = p.add_run()
        body.text = item
        body.font.name = font_name
        body.font.size = Pt(size)
        body.font.color.rgb = color
    return tb


def add_image(slide, path: Path, left, top, width=None, height=None):
    if not path.exists():
        return None
    kwargs = {}
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    return slide.shapes.add_picture(str(path), left, top, **kwargs)


def add_panel(slide, left, top, width, height, *, fill: RGBColor = BG_PANEL,
              border: RGBColor | None = None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shp.adjustments[0] = 0.05
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = border
        shp.line.width = Pt(1.25)
    return shp


# ----- Slayt sablonlari -----------------------------------------------------
def slide_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_full_bg(s)

    # Ust serit - mor
    add_band(s, 0, 0, prs.slide_width, Inches(0.18), ACCENT_PURPLE)
    # Alt serit - cyan
    add_band(s, 0, prs.slide_height - Inches(0.12), prs.slide_width, Inches(0.12), ACCENT_CYAN)

    # Logo (varsa)
    logo = ASSETS / "main_theme" / "main_menu_logo.png"
    if logo.exists():
        add_image(s, logo, Inches(0.7), Inches(1.1), height=Inches(2.6))

    # Baslik
    add_text(
        s,
        "QUADRIX",
        Inches(0.7), Inches(3.9),
        Inches(8), Inches(1.1),
        size=72, bold=True, color=TEXT_WHITE,
    )
    add_text(
        s,
        "Cok modlu Tetris turevi · Kart Ustaligi · Steam destekli",
        Inches(0.7), Inches(4.95),
        Inches(11), Inches(0.6),
        size=22, color=ACCENT_CYAN,
    )
    add_text(
        s,
        "Pygame · Python 3.12 · 11 dil · macOS / Windows",
        Inches(0.7), Inches(5.55),
        Inches(11), Inches(0.5),
        size=16, color=TEXT_DIM,
    )

    # Sag dekoratif blok
    accent = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        prs.slide_width - Inches(0.55), Inches(1.0),
        Inches(0.18), Inches(5.5),
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = ACCENT_PINK
    accent.line.fill.background()

    return s


def slide_section(prs, no: str, title: str, subtitle: str = ""):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_full_bg(s)
    add_band(s, 0, 0, prs.slide_width, Inches(0.18), ACCENT_PURPLE)

    add_text(s, no, Inches(0.7), Inches(2.0), Inches(3), Inches(1.4),
             size=110, bold=True, color=ACCENT_CYAN)
    add_text(s, title, Inches(0.7), Inches(3.6), Inches(11), Inches(1.2),
             size=44, bold=True, color=TEXT_WHITE)
    if subtitle:
        add_text(s, subtitle, Inches(0.7), Inches(4.7), Inches(11), Inches(0.7),
                 size=18, color=TEXT_DIM)
    return s


def slide_header(prs, title: str, kicker: str = "") -> "Slide":
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_full_bg(s)
    add_band(s, 0, 0, Inches(0.18), prs.slide_height, ACCENT_CYAN)
    if kicker:
        add_text(s, kicker.upper(), Inches(0.7), Inches(0.45),
                 Inches(11), Inches(0.4),
                 size=12, bold=True, color=ACCENT_PINK)
    add_text(s, title, Inches(0.7), Inches(0.85),
             Inches(11.5), Inches(1.0),
             size=36, bold=True, color=TEXT_WHITE)
    # ince ayrac cizgi
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                              Inches(0.7), Inches(1.85),
                              Inches(1.6), Inches(0.05))
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT_CYAN
    line.line.fill.background()
    return s


def slide_footer(slide, prs, idx: int, total: int):
    add_text(
        slide,
        f"Quadrix · Pitch Deck · {idx:02d} / {total:02d}",
        Inches(0.7), prs.slide_height - Inches(0.45),
        Inches(11.5), Inches(0.3),
        size=10, color=TEXT_MUTED,
    )


# ----- Sunum gövdesi --------------------------------------------------------
def build_presentation():
    prs = Presentation()
    # 16:9 boyut (varsayilan 13.33 x 7.5 inch)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slides_log = []  # (slide, builder)

    # 01 Kapak
    s = slide_cover(prs); slides_log.append(s)

    # 02 Tek bakista
    s = slide_header(prs, "Tek Bakista Quadrix", kicker="Ozet")
    add_bullet_list(
        s,
        [
            "Cok modlu Tetris turevi: 10+ tek oyunculu mod, kampanya, yerel ve online cok oyunculu",
            "Kart Ustaligi (Mystery): bagimsiz card_xp / card_level progression hatti, 31 benzersiz kart ailesi",
            "Steam entegrasyonu: leaderboard, 40 basarim, 17 stat, P2P online PvP koprusu",
            "Yerel co-op: 20×20 ortak board, P1 / P2 izole hareket alanlari",
            "11 dil: TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO",
            "macOS ve Windows uretim build'leri; PyInstaller + Steamworks SDK",
        ],
        Inches(0.7), Inches(2.1),
        Inches(8.4), Inches(5.0),
        size=18, color=TEXT_WHITE,
    )
    # sag taraftaki maskot
    mascot = ASSETS / "maskot" / "cop.png"
    if mascot.exists():
        add_image(s, mascot, Inches(9.4), Inches(2.1), height=Inches(4.2))
    slides_log.append(s)

    # 03 Vizyon / hook
    s = slide_header(prs, "Klasik bloklar, modern derinlik", kicker="Vizyon")
    add_text(
        s,
        "Quadrix; klasik dusen blok hissini koruyup uzerine kart "
        "tabanli ekonomi, kampanya hedefleri ve Steam destekli "
        "rekabet katmanlari ekler. Tek seansta hem rahatlama hem "
        "uzun donem ilerleme sunar.",
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(2.0),
        size=22, color=TEXT_WHITE,
    )
    add_text(
        s,
        "Kor cebi: kasik basina aciklik (pick up & play) + uzun "
        "donem progression (campaign + card mastery + leaderboard)",
        Inches(0.7), Inches(4.2),
        Inches(11.5), Inches(1.0),
        size=16, color=ACCENT_CYAN,
    )
    slides_log.append(s)

    # 04 Modlar overview - mode icons grid
    s = slide_header(prs, "10+ Mod Tek Cati Altinda", kicker="Oyun Modlari")
    mode_icons = [
        ("classic_mode_icon.png", "Classic"),
        ("sprint_mode_icon.png", "Sprint"),
        ("ultra_mode_icon.png", "Ultra"),
        ("zen_mode_icon.png", "Zen"),
        ("tetris2_mode_icon.png", "Quadrix 2"),
        ("mystery_mode_icon.png", "Mystery"),
        ("wide_mode_icon.png", "Wide"),
        ("survival_mode_icon.png", "Survival"),
        ("cascade_mode_icon.png", "Cascade"),
        ("hardcore_mode_icon.png", "Hardcore"),
        ("daily_mode_icon.png", "Daily"),
        ("campaign_mode_icon.png", "Campaign"),
    ]
    cols = 6
    cell_w = Inches(1.85)
    cell_h = Inches(2.0)
    grid_left = Inches(0.7)
    grid_top = Inches(2.2)
    icon_dir = ASSETS / "ui" / "mode_icons"
    for i, (fname, label) in enumerate(mode_icons):
        col = i % cols
        row = i // cols
        cx = grid_left + col * (cell_w + Inches(0.2))
        cy = grid_top + row * (cell_h + Inches(0.3))
        panel = add_panel(s, cx, cy, cell_w, cell_h,
                          fill=BG_PANEL, border=ACCENT_CYAN)
        ipath = icon_dir / fname
        if ipath.exists():
            add_image(s, ipath,
                      cx + Inches(0.45), cy + Inches(0.2),
                      height=Inches(1.05))
        add_text(
            s, label,
            cx, cy + Inches(1.4),
            cell_w, Inches(0.5),
            size=14, bold=True, color=TEXT_WHITE,
            align=PP_ALIGN.CENTER,
        )
    slides_log.append(s)

    # 05 Mystery - Kart Ustaligi
    s = slide_header(prs, "Mystery: Kart Ustaligi", kicker="Imza Mod")
    add_bullet_list(
        s,
        [
            "31 benzersiz kart ailesi, 39 kart ID'si; ortak / nadir / epik / efsanevi seviyeler",
            "Bagimsiz iki progression: board.level oyun temposunu, card_xp ise odul akisini surer",
            "Line clear → kart XP → seviye atlama → 3 kart secimi → aktif efektler",
            "Time capsule restore: pending_level_ups, pending_choices, card_xp tam korunur",
            "External clear (kart/yetenek tetikli temizleme) card_xp uretmez — tek odul, tek prepare_selection",
        ],
        Inches(0.7), Inches(2.1),
        Inches(7.6), Inches(4.6),
        size=17, color=TEXT_WHITE,
    )
    # Sagda kart goselleri (nadirlik kartlari)
    card_dir = ASSETS / "cards"
    rarity = [
        ("common_front.png", "Common"),
        ("uncommon_front.png", "Uncommon"),
        ("rare_front.png", "Rare"),
        ("epic_front.png", "Epic"),
        ("legendary_front.png", "Legendary"),
    ]
    rx = Inches(8.6)
    ry = Inches(2.1)
    card_w = Inches(0.85)
    for i, (fname, _label) in enumerate(rarity):
        cp = card_dir / fname
        if cp.exists():
            add_image(s, cp, rx + i * Inches(0.83), ry, width=card_w)
    add_text(
        s,
        "Common · Uncommon · Rare · Epic · Legendary",
        Inches(8.6), Inches(3.6),
        Inches(4.5), Inches(0.4),
        size=11, color=TEXT_DIM, align=PP_ALIGN.LEFT,
    )

    # alt: kart efekt ikonlari ornek seridi
    perk_icons = [
        "icon_hammer.png", "icon_sniper_shot.png", "icon_laser_drill.png",
        "icon_mini_bomb.png", "icon_freeze_drop.png", "icon_quantum_tunnel.png",
        "icon_time_capsule.png", "icon_nova_burst.png",
    ]
    perk_dir = ASSETS / "ui"
    px = Inches(8.6)
    py = Inches(4.1)
    for i, fname in enumerate(perk_icons):
        ip = perk_dir / fname
        if ip.exists():
            col = i % 4
            row = i // 4
            add_image(
                s, ip,
                px + col * Inches(0.95),
                py + row * Inches(0.95),
                width=Inches(0.85),
            )
    add_text(
        s,
        "Ornek kart efektleri",
        Inches(8.6), Inches(6.05),
        Inches(4.5), Inches(0.4),
        size=11, color=TEXT_DIM,
    )
    slides_log.append(s)

    # 06 Campaign
    s = slide_header(prs, "Campaign + Co-op Campaign", kicker="Tek Oyunculu Derinlik")
    add_bullet_list(
        s,
        [
            "Yildiz tabanli ilerleme; her seviye kendi objective seti ile gelir",
            "Save akisi sonunda otomatik basarim tetikleme (campaign_mode._save_progress)",
            "Yerel iki kisilik Co-op Campaign: ortak board, paylasimli hedefler",
            "Seviye select ekrani: kilitli / acik / hover / selected durumlari ayri art seti",
        ],
        Inches(0.7), Inches(2.1),
        Inches(7.6), Inches(4.4),
        size=17, color=TEXT_WHITE,
    )
    # Sagda level frame ornekleri
    level_dir = ASSETS / "campaign_level"
    samples = [
        ("d1_normal.png", "Normal"),
        ("d2_hover.png", "Hover"),
        ("d3_selected.png", "Selected"),
        ("d4_locked.png", "Locked"),
    ]
    # d1_normal yok, fallback d1_nomal
    if not (level_dir / "d1_normal.png").exists():
        samples[0] = ("d1_nomal.png", "Normal")

    sx = Inches(8.6)
    sy = Inches(2.1)
    cell = Inches(2.0)
    for i, (fname, label) in enumerate(samples):
        col = i % 2
        row = i // 2
        ip = level_dir / fname
        if ip.exists():
            add_image(s, ip,
                      sx + col * (cell + Inches(0.15)),
                      sy + row * (cell + Inches(0.45)),
                      width=cell)
        add_text(
            s, label,
            sx + col * (cell + Inches(0.15)),
            sy + row * (cell + Inches(0.45)) + cell + Inches(0.02),
            cell, Inches(0.35),
            size=11, color=TEXT_DIM, align=PP_ALIGN.CENTER,
        )
    slides_log.append(s)

    # 07 Co-op (yerel)
    s = slide_header(prs, "Yerel Co-op: Ortak Board", kicker="Birlikte Oyna")
    add_bullet_list(
        s,
        [
            "20×20 paylasimli board; midline = 10",
            "P1 sutunlar 0-9, P2 sutunlar 10-19; havada parca carpisma yok",
            "Iki oyuncu icin izole hareket alanlari, ortak satir temizleme",
            "Co-op campaign ile birlestiginde ortak yildiz hedefi akisi",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.0),
        size=18, color=TEXT_WHITE,
    )
    # gorsel: coop panel
    coop_panel = ASSETS / "main_theme" / "coop_panel.png"
    if coop_panel.exists():
        add_image(s, coop_panel, Inches(8.6), Inches(4.2), height=Inches(2.5))
    slides_log.append(s)

    # 08 PvP & Online PvP
    s = slide_header(prs, "Yerel PvP + Online PvP (Steam P2P)", kicker="Rekabet")
    add_bullet_list(
        s,
        [
            "Yerel PvP: tek klavye, iki ayri board",
            "Online PvP: Steam P2P uzerinden eslestirme; native steam_net_bridge",
            "Bridge aktifken Steam pump thread duraklatilir (pause_pump / resume_pump) — segfault korumasi",
            "Mimari ayrim: Python wrapper (steam_networking.py) ile C++ kopru (steam_net_bridge.cpp)",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.4),
        size=17, color=TEXT_WHITE,
    )
    pvp_panel = ASSETS / "main_theme" / "pvp_panel.png"
    if pvp_panel.exists():
        add_image(s, pvp_panel, Inches(8.6), Inches(4.4), height=Inches(2.4))
    slides_log.append(s)

    # 09 Steam entegrasyonu
    s = slide_header(prs, "Steam Entegrasyonu", kicker="Topluluk & Rekabet")
    add_bullet_list(
        s,
        [
            "40 basarim, 17 stat — gercek Steamworks tanimi ile eslesik",
            "Leaderboard: backend proxy (FastAPI) + client SDK koprusu",
            "Daily/Sprint/Ultra modlarina mod-bazli leaderboard adi eslemesi",
            "Build / upload akisi tek kanonik kaynak: scripts/build/* + steamworks/scripts/*.vdf",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.6),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 10 Lokalizasyon
    s = slide_header(prs, "11 Dil, Tek Tum Yuzeyler", kicker="Lokalizasyon")
    add_bullet_list(
        s,
        [
            "TR (kanonik), EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO",
            "Tek t() apisi; localizasyon tablosu eksik anahtarda EN'e fallback eder",
            "CJK font profili ayri (ui_language_profile.py); diakritik / stroke render saglikli",
            "Maskot ve panel efekt gorselleri her dil icin ayri sablon",
        ],
        Inches(0.7), Inches(2.1),
        Inches(7.6), Inches(4.4),
        size=17, color=TEXT_WHITE,
    )
    # mascot localization grid
    locales = [
        "sos_maskot.png",
        "sos_maskot_ingilizce.png",
        "sos_maskot_japonca.png",
        "sos_maskot_korece.png",
        "sos_maskot_çince.png",
        "sos_maskot_almanca.png",
    ]
    lx = Inches(8.6)
    ly = Inches(2.1)
    for i, fname in enumerate(locales):
        col = i % 3
        row = i // 3
        ip = ASSETS / "maskot" / fname
        if ip.exists():
            add_image(
                s, ip,
                lx + col * Inches(1.5),
                ly + row * Inches(2.1),
                width=Inches(1.4),
            )
    slides_log.append(s)

    # 11 UI / tema
    s = slide_header(prs, "Olcekli UI, Tek Font Kaynagi", kicker="Tasarim Disiplini")
    add_bullet_list(
        s,
        [
            "UIFonts (ui_theme.py) tum in-game fontlarinin tek kaynagi — paralel font factory yok",
            "Her ekranin kendi olcekleme fonksiyonu: menu, level select, extras, mystery HUD",
            "Tema, blok stili, arka plan, ses ve muzik shuffle ayarlari",
            "Glass panel + retro aksanli karma estetik",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.5),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 12 Profil ve avatar
    s = slide_header(prs, "Profil, Avatar, Skor", kicker="Oyuncu Hafizasi")
    add_bullet_list(
        s,
        [
            "Cok kullanicili yerel profil; avatar ve istatistik takibi",
            "Mod bazli skor gecmisi; kisisel rekorlar",
            "Steam acildiginda otomatik basarim ve leaderboard senkronu",
            "Workshop / Atolye yuzeyleri ile kisisellestirme alanlari",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.5),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 13 Mimari
    s = slide_header(prs, "Mimari Ozet", kicker="Teknoloji")
    add_bullet_list(
        s,
        [
            "Python 3.12 + Pygame 2.x; src/ altinda modul ailesi",
            "src/game.py + src/board.py: cekirdek dusen blok dongusu",
            "src/game_modes_extra.py: Mystery (MysteryMode + MysteryCardManager)",
            "src/campaign/*: kampanya ve co-op kampanya sistemi",
            "backend/: FastAPI tabanli leaderboard proxy",
            "steamworks/steam_net_bridge/: native C++ kopru (Online PvP)",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(4.6),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 14 Kalite / test
    s = slide_header(prs, "Test ve Kalite Disiplini", kicker="Guvenli Iterasyon")
    add_bullet_list(
        s,
        [
            "./scripts/test/run_tests.sh -q kanonik test giris noktasi",
            "Mystery, campaign, achievement, leaderboard, UI scaling, lokalizasyon icin ayri test cografyalari",
            "Generated markdown'lar tools/sync_markdown_docs.py ile kaynaktan uretilir",
            "AGENTS.md operasyonel rehberi: yuzey -> dogrulama matrisi tek kaynak",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(3.6),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 15 Build & dagitim
    s = slide_header(prs, "Build ve Dagitim", kicker="Yayina Cikis")
    add_bullet_list(
        s,
        [
            "macOS: scripts/build/build_macos_app.sh + steam_upload_macos.sh",
            "Windows: scripts/build/build_windows_exe.ps1 + tools/steam_upload_playtest.ps1",
            "PyInstaller spec dosyalari packaging/specs/ altinda",
            "steam_net_bridge .pyd / .so local_artifacts/bridge/ uzerinden pakete dahil",
            "Steamworks app build VDF: steamworks/scripts/app_build_*.vdf",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(4.4),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 16 Yol haritasi
    s = slide_header(prs, "Yol Haritasi", kicker="Sonraki Adimlar")
    add_bullet_list(
        s,
        [
            "Kart kataloguna yeni aileler ve sinerji efektleri",
            "Online co-op campaign deneme sezonu",
            "Daily mod icin haftalik turnuva ve bolgesel leaderboard",
            "Workshop / Atolye uzerinden topluluk uretimi (tema, blok stili, arka plan)",
            "Erisilebilirlik: renk koru modu, yuksek kontrast tema, tus yeniden bagi",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(4.4),
        size=17, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 17 Neden Quadrix
    s = slide_header(prs, "Neden Quadrix", kicker="Pitch")
    add_bullet_list(
        s,
        [
            "Klasik Tetris hissini koruyup uzerine kart tabanli derinlik koyan az sayidaki yapidan biri",
            "Tek seans: rahatlama (Zen, Classic). Uzun donem: campaign + card mastery + leaderboard",
            "Yerel ve Steam P2P online cok oyunculu — solo limitli degil",
            "11 dil ile gun bir global topluluga yeterli temel",
            "Disiplinli mimari + test kapsami: surdurulebilir surum yayini",
        ],
        Inches(0.7), Inches(2.1),
        Inches(11.5), Inches(4.6),
        size=18, color=TEXT_WHITE,
    )
    slides_log.append(s)

    # 18 Tesekkurler / iletisim
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_full_bg(s)
    add_band(s, 0, 0, prs.slide_width, Inches(0.18), ACCENT_PURPLE)
    add_band(s, 0, prs.slide_height - Inches(0.12), prs.slide_width, Inches(0.12), ACCENT_CYAN)
    add_text(s, "Tesekkurler",
             Inches(0.7), Inches(2.6),
             Inches(11.5), Inches(1.5),
             size=80, bold=True, color=TEXT_WHITE)
    add_text(
        s,
        "Quadrix · klasik bloklar, modern derinlik",
        Inches(0.7), Inches(4.0),
        Inches(11.5), Inches(0.7),
        size=22, color=ACCENT_CYAN,
    )
    add_text(
        s,
        "Demo, build veya teknik soru talepleri icin proje yoneticisine ulasabilirsiniz.",
        Inches(0.7), Inches(4.7),
        Inches(11.5), Inches(0.6),
        size=14, color=TEXT_DIM,
    )
    slides_log.append(s)

    # ---- footers ----------------------------------------------------------
    total = len(slides_log)
    for i, sl in enumerate(slides_log, start=1):
        if i == 1 or i == total:
            continue  # kapak ve son slaytta footer yok
        slide_footer(sl, prs, i, total)

    prs.save(OUT_FILE)
    return OUT_FILE, total


def main():
    out, total = build_presentation()
    rel = out.relative_to(ROOT)
    print(f"Sunum yazildi: {rel}  ({total} slayt)")


if __name__ == "__main__":
    main()
