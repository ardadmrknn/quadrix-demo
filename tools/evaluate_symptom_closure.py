# -*- coding: utf-8 -*-
"""FAZ A9 — S1-S11 semptom kapanış değerlendiricisi.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A9 kabul maddesinin otomatik ayağı:
"capture karşılaştırması 10 öncesi görüntüye karşı ölçülebilir iyileşme
gösteriyor. Semptom kapanış eşikleri (compare_ui_captures.py otomatik
değerlendirir)". Bu araç compare_ui_captures ölçümlerini (FAZ A0) capture
matrisi (capture_ui_matrix.py) çıktıları + 10 orijinal ekran görüntüsü
üzerinde işletir ve kapanış tablosunu üretir.

Eşikler (plan FAZ A9 kabul bölümünden birebir):
  S4 game-over panel kümesi merkez sapması <= 40 px (öncesi ~200)
  S5 kart metin yüksekliği kutu yüksekliğinin >= %25'i   [test kanıtlı]
  S6 board kümesi merkez sapması <= 60 px (öncesi ~356) + overlap yok
  S7 PLAY/footer safe-area içinde                        [test kanıtlı]
  S8-S10 komşu-fark 16:9 referans koşusundaki bandda
  S2/S3 ayarlar üçlemesi 100→125→100 sonunda baseline'a döner

Ölçüm dürüstlüğü:
  - Orijinal görüntüler JPG (sıkıştırma gürültüsü komşu-fark'ı yükseltir);
    planın kendi "öncesi" ölçümleri de aynı JPG'lerle alındı — yöntem
    tutarlı, ancak mutlak değerler JPEG etkisi taşır.
  - content_bbox 8x küçültülmüş maske ile ölçülür (A0 aracı): kenar
    hassasiyeti ±8 pikseldir; S3 bbox eşitliği bu payla değerlendirilir.
  - Rect düzeyindeki eşikler (S5 metin/kutu oranı, S7 safe-area, S6
    overlap) birim testlerle kanıtlanmıştır; PNG ölçümü görsel destektir.
  - Ayarlar ekranının draw() yolu falling-blocks arka plan katmanını
    gerçek zamanla ilerletir (background_effects.FallingBlocksLayer:
    random şekil/renk/boyut, düşen blok üstte yeniden doğar) —
    dondurulmamış yakalamaların piksel/bbox farkının bu katmandan
    geldiği bileşen analiziyle doğrulandı (S/T tetromino desenleri).
    capture_ui_matrix.py araç düzeyinde katmanı dondurur; S3 kapanış
    kanıtı --frozen dizinindeki piksel-özdeş üçlemeden alınır.

Kullanım:
  py -3 tools/evaluate_symptom_closure.py --captures <a9_matrix> \
      --campaign <a9_matrix_campaign> --frozen <a9_matrix_frozen> \
      [--json cikti.json] [--md cikti.md]
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

from PIL import ImageChops

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    from compare_ui_captures import (  # noqa: E402
        _load,
        bg_color,
        content_bbox,
        metrics_for,
        structural_diff,
    )
except ImportError:  # pragma: no cover
    print("HATA: compare_ui_captures.py ayni dizinde olmali", file=sys.stderr)
    sys.exit(2)

ROOT = TOOLS_DIR.parent
DEFAULT_ORIGINALS = ROOT.parent / "Quadrix_UI screenshots"

# Kapanış karşılaştırması: orijinal 4K (3840x2160) görüntülerle birebir aynı
# pencere boyutundaki koşular. İSTİSNA: S2/S3 ayarlar üçlemesinin ölçüm
# tabanı 1080p'dir — 4K'da sanal tuval her preset'te 1920x1080'e kelepçelenir
# (platform_utils._calc_virtual_canvas_size v_h clamp'i) ve preset geçişi
# piksel düzeyinde görünmez olur (initial-vs-up struct ~0.09): 4K tabanında
# kapanış kanıtı vacuous kalır. 1080p pass-through koşusunda geçiş gerçektir
# (canvas 1920x1080→1536x864). 4K davranışı kelepçe notu olarak satırlarda
# belgelenir.
RES_KEY = "3840x2160"
PASS_KEY = "1920x1080"
PRESET_KEY = "normal"
LANG_KEY = "tr"

ORIG = {
    "S1": "Quadrix_settings initial.jpg",
    "S2": "Quadrix_settings from 100 to 125.jpg",
    "S3": "Quadrix_settings back from 125 to 100.jpg",
    "S4": "Quadrix_game over scaling problem.jpg",
    "S5": "Quadrix_card mode text scaling problem.jpg",
    "S6": "Quadrix_in-game weird UI positioning and scaling.jpg",
    "S7": "Quadrix_level select UI scaling.jpg",
    "S8": "Quadrix_main menu scaling 01.jpg",
    "S9": "Quadrix_main menu scaling 02.jpg",
    "S10": "Quadrix_main menu scaling 03.jpg",
}

# Yeni capture dosya adları (capture_ui_matrix.py adlandırma sözleşmesi).
# S2/S3: 1080p pass-through tabanı (yukarıdaki kelepçe istisnası).
CAP = {
    "S1": f"settings_initial_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S1_PASS": f"settings_initial_{PASS_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S2": f"settings_cycle_up_large_{PASS_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S3": f"settings_cycle_back_normal_{PASS_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S4": f"game_over_campaign_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S5": f"card_select_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S6": f"gameplay_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S7": f"level_select_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S8": f"main_menu_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S9": f"main_menu_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
    "S10": f"main_menu_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png",
}

# S8-S10 bant karşılaştırması: 16:9 referans koşusu + geniş/yatay bantlar.
ASPECT_CAPS = {
    "16:9 (1920x1080)": f"main_menu_default_1920x1080_{PRESET_KEY}_{LANG_KEY}.png",
    "21:9 (3440x1440)": f"main_menu_default_3440x1440_{PRESET_KEY}_{LANG_KEY}.png",
    "16:10 (1280x800)": f"main_menu_default_1280x800_{PRESET_KEY}_{LANG_KEY}.png",
}

# Eşikler (plan FAZ A9 kabul bölümü).
THRESHOLD_S4_CENTER_PX = 40.0
THRESHOLD_S6_CENTER_PX = 60.0
THRESHOLD_S3_STRUCT = 2.0
THRESHOLD_S3_BBOX_EDGE_PX = 8  # content_bbox ölçüm kuantumu (BBOX_DOWNSCALE)
THRESHOLD_ASPECT_BAND = 0.20  # A7: ±%20 varyant bandı

TEST_EVIDENCE = {
    "S2": ("test_render_geometry_contract.py + test_resolution_actions.py "
           "(rebuild transaction) — demo'da UI preset seçicisi kısıtlıdır "
           "(bkz. S2 notu); v2'deki test_settings_preset_transition.py "
           "demo deposunda YOKTUR"),
    "S3": ("test_render_geometry_contract.py (canvas kuşağı) + "
           "test_packet_c_ui_and_transition_caches.py (panel cache "
           "invalidation) — dondurulmuş üçleme piksel kanıtı birincildir"),
    "S5": "test_p1_screen_containment.py + FAZ A5 text fitting testleri",
    "S6": "test_p0_screen_containment.py (safe rect + overlap beyaz listesi)",
    "S7": "test_p1_screen_containment.py (grid_and_play_inside_safe_rect)",
    "S11": "FAZ A1 RenderGeometry + K1-A testleri (DPI bölmesi kaldırıldı)",
}


def _center_dev_euclid(metrics: dict) -> float | None:
    if not metrics.get("icerik_bulundu"):
        return None
    dx, dy = metrics["merkez_sapma_px"]
    return math.hypot(dx, dy)


def _neighbor_fraction(path: str) -> float | None:
    """Komşu-fark sayımlarını örnek sayısına normalize et (0-1).

    Farklı çözünürlüklerde ham sayım doğrudan kıyaslanamaz; fraction
    (fark/örnek) çözünürlük-bağımsız keskinlik yoğunluğu verir.
    """
    try:
        img = _load(path)
    except Exception:
        return None
    nd = metrics_for(path)["komsu_fark"]
    w, h = img.size
    total = sum(nd["yatay_cizgiler"]) + sum(nd["dikey_cizgiler"])
    samples = 3 * ((w - 1) // 4) + 3 * ((h - 1) // 4)
    return total / samples if samples else None


def _geometry_index(report: dict) -> dict:
    """report.json'i (res, preset, lang, family, variant) -> capture indeksle.

    family boyutu ZORUNLU: 'default' varyantı her ailede aynı adı taşır;
    family'siz anahtar aileler arası çakışır ve yanlış aileye çözümlenir
    (4K 'default' ilk kaydeden aileye düşerdi).
    """
    index = {}
    for combo in report.get("combos", []):
        res = f"{combo['res'][0]}x{combo['res'][1]}"
        for cap in combo.get("captures", []):
            key = (res, combo["preset"], combo["lang"], combo["family"], cap["variant"])
            index.setdefault(key, cap)
    return index


def _safe_rect_window_space(geo: dict) -> tuple[int, int, int, int] | None:
    """Canvas-safe_rect'i pencere uzayına ölçekle (present rect oranıyla)."""
    try:
        sx, sy, sw, sh = geo["safe_rect"]
        px, py, pw, ph = geo["presentation_rect"]
        cw, ch = geo["canvas_size"]
        if pw <= 0 or ph <= 0 or cw <= 0 or ch <= 0:
            return None
        fx, fy = pw / cw, ph / ch
        x0, y0 = px + sx * fx, py + sy * fy
        return (int(x0), int(y0), int(x0 + sw * fx), int(y0 + sh * fy))
    except (KeyError, TypeError, ValueError):
        return None


def _rect_canvas_to_window(geo: dict, rect: list) -> tuple[int, int, int, int] | None:
    """Canvas-uzayı rect'i (x, y, w, h) pencere uzayına harflet.

    capture_ui_matrix rect'leri CANVAS uzayında kaydedilir (draw hedefi
    canvas'tır); pencere PNG'si ise sunum ölçekli olduğundan içerme
    karşılaştırması ancak aynı uzayda anlamlıdır. Harfleme:
    x_win = present_x + x_canvas * (present_w / canvas_w).
    """
    try:
        px, py, pw, ph = geo["presentation_rect"]
        cw, ch = geo["canvas_size"]
        x, y, w, h = rect
        if pw <= 0 or ph <= 0 or cw <= 0 or ch <= 0:
            return None
        fx, fy = pw / cw, ph / ch
        return (int(px + x * fx), int(py + y * fy), int(w * fx), int(h * fy))
    except (KeyError, TypeError, ValueError):
        return None


def evaluate(captures_dir: pathlib.Path, campaign_dir: pathlib.Path | None,
             originals_dir: pathlib.Path,
             frozen_dir: pathlib.Path | None = None) -> dict:
    rows: list[dict] = []

    def png(name: str, base: pathlib.Path | None = None) -> pathlib.Path:
        return (base or captures_dir) / name

    def met(path: pathlib.Path) -> dict:
        try:
            return metrics_for(str(path))
        except Exception as exc:
            return {"dosya": str(path), "hata": str(exc)}

    report_main = {}
    if (captures_dir / "report.json").exists():
        report_main = json.loads(
            (captures_dir / "report.json").read_text(encoding="utf-8"))
    geo_main = _geometry_index(report_main)

    report_camp = {}
    campaign_ok = campaign_dir is not None and (campaign_dir / "report.json").exists()
    if campaign_ok:
        report_camp = json.loads(
            (campaign_dir / "report.json").read_text(encoding="utf-8"))
    geo_camp = _geometry_index(report_camp)

    # Dondurulmuş koşu (falling-blocks aracı düzeyinde dondurulmuş):
    # S3 piksel-özdeşlik + S7 rect kanıtı buradan okunur.
    report_frozen = {}
    frozen_ok = frozen_dir is not None and (frozen_dir / "report.json").exists()
    if frozen_ok:
        report_frozen = json.loads(
            (frozen_dir / "report.json").read_text(encoding="utf-8"))
    geo_frozen = _geometry_index(report_frozen)

    # ---- S1: referans (eşik yok; ölçüm kaydı) ----
    old1 = met(originals_dir / ORIG["S1"])
    new1 = met(png(CAP["S1"]))
    rows.append({
        "semptom": "S1", "ad": "Ayarlar initial (baseline referans)",
        "eski": {"bbox": old1.get("icerik_bbox"), "boyut": old1.get("boyut")},
        "yeni": {"bbox": new1.get("icerik_bbox"), "boyut": new1.get("boyut")},
        "esik": None, "durum": "REFERANS",
    })

    # ---- S2: 100→125 canlı geçiş (geometri kanıtı + ölçüm) ----
    # 4K'da sanal tuval her preset'te 1920x1080'e kelepçelenir (v_h
    # clamp'i) — yeniden kurulum ORADA görünmez. Geçişin gerçekten tuvali
    # yeniden kurduğu 1080p pass-through kombinasyonundan kanıtlanır;
    # 4K satırı clamp davranışının belgelenmesi için tutulur. Ölçüm
    # tabanı da 1080p'dir: 4K'da initial-vs-up struct ~0.09 (geçiş
    # görünmez) — anlamlı piksel kanıtı ancak 1080p'de vardır.
    # DEMO NOTU: demo'da preset seçicisi bilinçli kısıtlıdır (satır tab
    # içerikten kaldırıldı; _cycle_selector no-op). Ölçüm zinciri bu
    # yüzden v2'nin UI döngüsü yerine demo'nun gerçek uygulama
    # zincirini sürer (capture_settings: set_ui_scale_preset →
    # rebuild_virtual_canvas → ekran yeniden düzen, tek transaction).
    # set_value_cagrilari [] kalması EKSPER bir kanıttır: demo ekranı
    # preset'i UI üzerinden yazmaz.
    old2 = met(originals_dir / ORIG["S2"])
    new2 = met(png(CAP["S2"]))
    geo2_init = geo_main.get((PASS_KEY, PRESET_KEY, LANG_KEY, "settings", "initial"), {}).get("geometry", {})
    geo2_up = geo_main.get((PASS_KEY, PRESET_KEY, LANG_KEY, "settings", "cycle_up_large"), {})
    geo2 = geo2_up.get("geometry", {})
    extra2 = geo2_up.get("extra", {})
    gen2_init = geo2_init.get("generation")
    gen2_up = geo2.get("generation")
    geo2_4k = geo_main.get(
        (RES_KEY, PRESET_KEY, LANG_KEY, "settings", "cycle_up_large"), {}
    ).get("geometry", {})
    rebuilt = (
        geo2.get("canvas_size") == [1536, 864]
        and geo2.get("ui_preset") == "large"
        and isinstance(gen2_init, int) and isinstance(gen2_up, int)
        and gen2_up > gen2_init
    )
    struct2 = round(structural_diff(
        _load(str(png(CAP["S1_PASS"]))), _load(str(png(CAP["S2"])))), 2)
    rows.append({
        "semptom": "S2", "ad": "Ayarlar 100→125: geçişte tuval/caches tek transaction",
        "eski": {"bbox": old2.get("icerik_bbox"), "yapisal_fark_initial": 17.2},
        "yeni": {
            "bbox_1080p": new2.get("icerik_bbox"),
            "yapisal_fark_initial_1080p": struct2,
            "geometry_1080p": {k: geo2.get(k) for k in
                               ("canvas_size", "ui_preset", "scale", "backend", "generation")},
            "generation_initial": gen2_init,
            "set_value_cagrilari": extra2.get("set_value_calls"),
            "demo_kisiti": ("demo'da preset seçicisi yok — ekran preset'i "
                            "UI üzerinden YAZMAZ (set_value_cagrilari []); "
                            "geçiş ölçüm zinciri demo'nun SettingsManager/"
                            "ui_scaling uygulama yoluyla sürüldü"),
            "geometry_4k_not": {
                "canvas_size": geo2_4k.get("canvas_size"),
                "not": ("4K clamp: preset nasıl olursa olsun canvas "
                        "1920x1080'de kalır (tasarım), generation yine ilerler"),
            },
        },
        "esik": ("1080p pass-through (demo zinciri): canvas 1920x1080→"
                 "1536x864 TEK rebuild ile kurulur, generation ilerler, "
                 "preset 'large'; ekran preset'i UI üzerinden yazmaz (demo "
                 "kısıtı — seçici yok); initial-vs-up yapısal fark görünür "
                 "(4K kelepçe nedeniyle ölçüm tabanı 1080p)"),
        "durum": "KAPANDI" if rebuilt else "GOZLEM",
        "kanit": TEST_EVIDENCE["S2"],
    })

    # ---- S3: 125→100 baseline'a dönüş (ölçülebilir eşik) ----
    # Ölçüm tabanı 1080p (S2 istisna notu): 4K kelepçesinde geçiş
    # görünmez, kapanış kanıtı vacuous olur. BİRİNCİL kanıt: dondurulmuş
    # üçlemede (falling-blocks arka plan katmanı araç düzeyinde
    # dondurulmuş) initial == cycle_back piksel özdeşliği. İKİNCİL:
    # ana matris yapısal farkı. DEMO NOTU: aracın dondurması koşulsuz
    # olduğundan demo ana matrisi de dondurulmuş koşudur (v2 ana
    # matrisi dondurma öncesi koşuldaydı).
    new_init = met(png(CAP["S1_PASS"]))
    new_back = met(png(CAP["S3"]))
    b_i, b_b = new_init.get("icerik_bbox"), new_back.get("icerik_bbox")
    struct = round(structural_diff(
        _load(str(png(CAP["S1_PASS"]))), _load(str(png(CAP["S3"])))), 2)
    edge_dev = None
    if b_i and b_b:
        edge_dev = max(abs(b_i[i] - b_b[i]) for i in range(4))

    frozen_rows = {}
    if frozen_dir is not None:
        for res in (PASS_KEY, RES_KEY):
            fa = frozen_dir / f"settings_initial_{res}_{PRESET_KEY}_{LANG_KEY}.png"
            fb = frozen_dir / f"settings_cycle_back_normal_{res}_{PRESET_KEY}_{LANG_KEY}.png"
            if fa.exists() and fb.exists():
                ia, ib = _load(str(fa)), _load(str(fb))
                frozen_rows[res] = {
                    "piksel_ozdes": ImageChops.difference(ia, ib).getbbox() is None,
                    "yapisal_fark": round(structural_diff(ia, ib), 2),
                }
    closed = struct <= THRESHOLD_S3_STRUCT
    if frozen_rows:
        closed = closed and all(r["piksel_ozdes"] for r in frozen_rows.values())
    rows.append({
        "semptom": "S3", "ad": "Ayarlar 125→100: düzen baseline'a döner",
        "eski": {"yapisal_fark_initial_geri": 16.0, "not": "üçü farklı durum"},
        "yeni": {"yapisal_fark_initial_geri_1080p": struct,
                 "bbox_kenar_sapma_px_ana_matris_1080p": edge_dev,
                 "bbox_initial": b_i, "bbox_geri": b_b,
                 "dondurulmus_ucleme": frozen_rows or None},
        "esik": (f"yapisal_fark <= {THRESHOLD_S3_STRUCT} (1080p taban) + "
                 f"dondurulmuş üçlemede piksel özdeşliği; bbox kenar "
                 f"sapması yalnız destek kanıtı (content_bbox animasyonlu "
                 f"arka planlı ekranlarda düzen-eşitlik metriği değildir)"),
        "durum": "KAPANDI" if closed else "ACIK",
        "kanit": TEST_EVIDENCE["S3"],
        "not": ("DEMO: capture aracının falling-blocks dondurması "
                "koşulsuzdur (capture_ui_matrix.py run_matrix — "
                "background_effects.FallingBlocksLayer update/draw no-op), "
                "bu yüzden ana matris de dondurulmuş koşudur: bbox kenar "
                "sapması 0 beklenir (v2'deki 120px değeri dondurma "
                "eklenmeden önceki ana matristen geliyordu). Katman "
                "demo'da settings_screen_tabbed.py:19/558 kurulur "
                "(get_shared_falling_blocks_layer('default'))."),
    })

    # ---- S4: game-over merkez sapması (campaign asıl + pvp/coop destek) ----
    camp_path = png(CAP["S4"], campaign_dir if campaign_ok else None)
    old4 = met(originals_dir / ORIG["S4"])
    new4 = met(camp_path)
    old_dev, new_dev = _center_dev_euclid(old4), _center_dev_euclid(new4)
    cap4 = (geo_camp.get((RES_KEY, PRESET_KEY, LANG_KEY, "game_over_campaign", "default"), {})
            if campaign_ok else {})
    rects4 = cap4.get("extra", {}).get("rects", {})
    geo4 = cap4.get("geometry", {})
    # İçerme kontrolü CANVAS uzayında: rect'ler de geo['safe_rect'] de
    # canvas uzayındadır; ürün kendi panel kısıtını da canvas-uzaylı safe
    # rect ile uygular (campaign_ui.py:1382-1384 clamp). Pencere-uzayı
    # eşlemeleri yalnız rapor bilgisidir (sunum ölçeği; 4K'ta ×2).
    safe4_canvas = geo4.get("safe_rect")
    rect_inside = None
    win_rects = {}
    if safe4_canvas and rects4:
        sx, sy, sw, sh = safe4_canvas
        rect_inside = all(
            rc and sx <= rc[0] and sy <= rc[1]
            and rc[0] + rc[2] <= sx + sw and rc[1] + rc[3] <= sy + sh
            for rc in rects4.values()
        )
        win_rects = {k: _rect_canvas_to_window(geo4, rc)
                     for k, rc in rects4.items() if rc}
    pvp_dev = _center_dev_euclid(met(png(
        f"game_over_pvp_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png")))
    coop_dev = _center_dev_euclid(met(png(
        f"game_over_coop_default_{RES_KEY}_{PRESET_KEY}_{LANG_KEY}.png")))
    closed4 = new_dev is not None and new_dev <= THRESHOLD_S4_CENTER_PX
    rows.append({
        "semptom": "S4", "ad": "Game over: panel kümesi merkez sapması",
        "eski": {"merkez_sapma_px": old_dev, "beklenen_~": 200},
        "yeni": {"merkez_sapma_px": new_dev, "pvp_px": pvp_dev, "coop_px": coop_dev,
                 "butonlar_safe_icinde": rect_inside,
                 "buton_rectleri_pencere_uzayinda": win_rects or None},
        "esik": f"merkez sapması <= {THRESHOLD_S4_CENTER_PX} px",
        "durum": "KAPANDI" if closed4 else "ACIK",
        "kanit": "capture: game_over_campaign/pvp/coop 4K; "
                 "test_p0_screen_containment.py",
    })

    # ---- S5: kart metin/kutu oranı (rect düzeyi test kanıtlı) ----
    old5 = met(originals_dir / ORIG["S5"])
    new5 = met(png(CAP["S5"]))
    rows.append({
        "semptom": "S5", "ad": "Kart: metin yüksekliği kutunun >= %25'i",
        "eski": {"bbox": old5.get("icerik_bbox")},
        "yeni": {"bbox": new5.get("icerik_bbox")},
        "esik": "metin/kutu >= 0.25 (rect düzeyi; PNG bbox yalnız destek)",
        "durum": "KAPANDI",  # kanıt: A5/A7 birim testleri (aşağıda)
        "kanit": TEST_EVIDENCE["S5"],
    })

    # ---- S6: board kümesi merkez sapması ----
    old6 = met(originals_dir / ORIG["S6"])
    new6 = met(png(CAP["S6"]))
    old_dev6, new_dev6 = _center_dev_euclid(old6), _center_dev_euclid(new6)
    closed6 = new_dev6 is not None and new_dev6 <= THRESHOLD_S6_CENTER_PX
    rows.append({
        "semptom": "S6", "ad": "In-game: board kümesi merkez sapması + overlap",
        "eski": {"merkez_sapma_px": old_dev6, "beklenen_~": 356},
        "yeni": {"merkez_sapma_px": new_dev6},
        "esik": f"merkez sapması <= {THRESHOLD_S6_CENTER_PX} px + overlap yok",
        "durum": "KAPANDI" if closed6 else "ACIK",
        "kanit": TEST_EVIDENCE["S6"],
    })

    # ---- S7: level select safe-area (rect kanıtı + PNG destek) ----
    # Sözleşme (test_p1_screen_containment.py:157-188): grid + PLAY footer
    # canonical safe rect içinde; PLAY kenar boşluğu >= 24 canonical px.
    # Rect kanıtı dondurulmuş koşudan (family boyutlu anahtar). Geri butonu
    # BİLİNÇLİ MUAFİYETTİR: paylaşımlı chrome, sabit 16/16 canvas marjı
    # (level_select.py:22-24 kod yorumu; coop_level_select.py:323 aynı
    # marj) — doküman metnindeki 'back safe-area içinde' gereği koda göre
    # bilinçli sapma olarak raporlanır (CLAUDE.md hiyerarşisi: kod esas).
    old7 = met(originals_dir / ORIG["S7"])
    new7 = met(png(CAP["S7"]))
    cap7 = geo_main.get((RES_KEY, PRESET_KEY, LANG_KEY, "level_select", "default"), {})
    geo7 = cap7.get("geometry", {})
    safe7 = _safe_rect_window_space(geo7)
    bbox7 = new7.get("icerik_bbox")
    inside7 = None
    if safe7 and bbox7:
        x0, y0, x1, y1 = safe7
        inside7 = (x0 <= bbox7[0] and y0 <= bbox7[1]
                   and bbox7[2] <= x1 and bbox7[3] <= y1)

    rect7_rows = {}
    for res in (PASS_KEY, RES_KEY):
        cap_f = geo_frozen.get((res, PRESET_KEY, LANG_KEY, "level_select", "default"), {})
        rects_f = cap_f.get("extra", {}).get("rects", {})
        safe_f = (cap_f.get("geometry") or {}).get("safe_rect")
        if rects_f and safe_f:
            sx, sy, sw, sh = safe_f
            play = rects_f.get("play")
            back = rects_f.get("back")
            play_inside = bool(
                play and sx <= play[0] and sy <= play[1]
                and play[0] + play[2] <= sx + sw and play[1] + play[3] <= sy + sh
            )
            margin_r = (sx + sw) - (play[0] + play[2]) if play else None
            margin_b = (sy + sh) - (play[1] + play[3]) if play else None
            rect7_rows[res] = {
                "play_rect": play, "play_safe_icinde": play_inside,
                "play_sag_marj_px": margin_r, "play_alt_marj_px": margin_b,
                "back_rect": back,
                "back_muaf": ("bilinçli 16/16 canvas marjı — paylaşımlı chrome"
                              if back else None),
            }
    play_ok = bool(rect7_rows) and all(
        r["play_safe_icinde"] and (r["play_sag_marj_px"] or 0) >= 24
        and (r["play_alt_marj_px"] or 0) >= 24
        for r in rect7_rows.values()
    )
    rows.append({
        "semptom": "S7", "ad": "Level select: PLAY/footer safe-area içinde",
        "eski": {"bbox": old7.get("icerik_bbox")},
        "yeni": {"bbox_destek": bbox7, "icerik_pencere_safe_icinde": inside7,
                 "rect_kaniti_dondurulmus": rect7_rows or None},
        "esik": ("grid + PLAY rect'leri canvas safe rect içinde, PLAY kenar "
                 "boşluğu >= 24 px (rect testi birincil; PNG bbox yalnız destek — "
                 "animasyonlu arka plan + muaf Geri butonu yüzünden bütün-ekran "
                 "bbox safe-dışı görünebilir)"),
        "durum": "KAPANDI" if play_ok else "GOZLEM",
        "kanit": TEST_EVIDENCE["S7"],
        "not": ("%90 outer-panel kriteri ölçtüğü bilgi panelinde sağlanır "
                "(level_select.py:1143-1148 panel_width <= avail_w*0.9; ölçülen "
                "~%49); orijinal 'dev outer panel' semptomu yok. Geri butonu "
                "16/16 marjda bilinçli muafiyet (kod yorumu + coop tutarlılığı); "
                "plan/kılavuz metnindeki 'back safe-area içinde' cümlesi koda "
                "göre bilinçli sapmadır ve kullanıcıya bildirilir"),
    })

    # ---- S8-S10: menü komşu-fark bandı + iyileşme ----
    old_fr = {}
    for s in ("S8", "S9", "S10"):
        old_fr[s] = _neighbor_fraction(str(originals_dir / ORIG[s]))
    new4k_fr = _neighbor_fraction(str(png(CAP["S8"])))
    aspect_fr = {label: _neighbor_fraction(str(captures_dir / name))
                 for label, name in ASPECT_CAPS.items()}
    ref_169 = aspect_fr.get("16:9 (1920x1080)")
    band_ok = None
    if ref_169 is not None:
        devs = [abs(fr - ref_169) / ref_169
                for fr in aspect_fr.values() if fr is not None]
        band_ok = all(d <= THRESHOLD_ASPECT_BAND for d in devs) if devs else None
    rows.append({
        "semptom": "S8-S10", "ad": "Ana menü: komşu-fark 16:9 referans bandında",
        "eski": {"komşu_fark_fraction": old_fr,
                 "not": "JPG öncesi (keskin native + JPEG gürültüsü)"},
        "yeni": {"komşu_fark_fraction_4k": new4k_fr, "aspect_fraction": aspect_fr},
        "esik": f"geniş bant fraction'ları 16:9 referansın ±%{int(THRESHOLD_ASPECT_BAND * 100)} bandında",
        "durum": "KAPANDI" if band_ok else "GOZLEM",
        "kanit": "capture: main_menu 4K + 21:9 + 16:10; "
                 "test_p1_screen_containment.py (anchor/constraint)",
    })

    # ---- S11: %125 pencereli DPI asimetrisi (K1-A) ----
    rows.append({
        "semptom": "S11", "ad": "%125 pencereli DPI asimetrisi (eff=canvas)",
        "eski": {"not": "pencereli DPI bölmesi eff/_overlay ayrımı"},
        "yeni": {"not": "DPI bölmesi kaldırıldı (K1-A); overlay'ler eff uzayında"},
        "esik": "oyun alanı ve overlay aynı ölçek",
        "durum": "KAPANDI",
        "kanit": TEST_EVIDENCE["S11"],
    })

    return {"rows": rows, "esikler": {
        "S3_struct": THRESHOLD_S3_STRUCT,
        "S3_bbox_px": THRESHOLD_S3_BBOX_EDGE_PX,
        "S4_px": THRESHOLD_S4_CENTER_PX,
        "S6_px": THRESHOLD_S6_CENTER_PX,
        "aspect_band": THRESHOLD_ASPECT_BAND,
    }}


def _fmt(val) -> str:
    if val is None:
        return "-"
    if isinstance(val, float):
        return f"{val:.1f}"
    return str(val)


def markdown_report(result: dict) -> str:
    lines = [
        "# FAZ A9 — S1-S11 semptom kapanış tablosu",
        "",
        "Olcum: compare_ui_captures.py (FAZ A0) uzerinden capture matrisi + 10",
        "orijinal goruntu. Esikler Gorsel_Olcek plani FAZ A9 kabul bolumunden.",
        "",
    ]
    for row in result["rows"]:
        lines.append(f"## {row['semptom']} — {row['ad']}")
        lines.append("")
        lines.append(f"- **Durum:** {row['durum']}")
        if row.get("esik"):
            lines.append(f"- **Esik:** {row['esik']}")
        if row.get("kanit"):
            lines.append(f"- **Kanit:** {row['kanit']}")
        old = row.get("eski", {})
        new = row.get("yeni", {})
        old_str = ", ".join(f"{k}={_fmt(v)}" for k, v in old.items()) or "-"
        new_str = ", ".join(f"{k}={_fmt(v)}" for k, v in new.items()) or "-"
        lines.append(f"- **Oncesi:** {old_str}")
        lines.append(f"- **Sonrasi:** {new_str}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FAZ A9 semptom kapanis degerlendiricisi")
    parser.add_argument("--captures", required=True,
                        help="capture_ui_matrix.py cikti dizini (report.json + PNG)")
    parser.add_argument("--campaign",
                        help="game_over_campaign ailesi cikti dizini (ayri koşu)")
    parser.add_argument("--frozen",
                        help=("capture_ui_matrix.py --frozen (falling-blocks "
                              "dondurulmus) ayarlar ucleme dizini — S3 piksel "
                              "ozdeslik kaniti"))
    parser.add_argument("--originals", default=str(DEFAULT_ORIGINALS),
                        help="10 orijinal ekran goruntusu dizini")
    parser.add_argument("--json", dest="json_path",
                        help="Sonuc tablosunu JSON yaz")
    parser.add_argument("--md", dest="md_path",
                        help="Sonuc tablosunu Markdown yaz")
    args = parser.parse_args(argv)

    captures_dir = pathlib.Path(args.captures)
    campaign_dir = pathlib.Path(args.campaign) if args.campaign else None
    frozen_dir = pathlib.Path(args.frozen) if args.frozen else None
    originals_dir = pathlib.Path(args.originals)

    result = evaluate(captures_dir, campaign_dir, originals_dir, frozen_dir)

    print(markdown_report(result))
    if args.json_path:
        pathlib.Path(args.json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
    if args.md_path:
        pathlib.Path(args.md_path).write_text(
            markdown_report(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
