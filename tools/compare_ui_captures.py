# -*- coding: utf-8 -*-
"""Quadrix UI capture karsilastirma araci.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A0 madde 4: S1-S11 olcumlerinin
tekrar uretilebilir hali. Oturum-gecici analiz betiginin repoya tasinmis,
parametrelendirilmis ve JSON cikisli formudur.

Olcumler:
  - content_bbox : arka plandan ayrisan icerik kutusu (8x kucultulmus maske,
                   toplam renk farki > 60). Image-space piksel koordinatidir.
  - bg_color     : kucultulmus goruntunun baskin rengi (arka plan tahmini).
  - center_dev   : icerik kutusu merkezinin ekran merkezinden sapmasi (px).
  - neighbor_diff: 3 ornek cizgide komsu-piksel benzemezligi (DWM ~Nx upscale
                   tespiti: ciftlesme varsa komsu-fark ~0).
  - structural_diff (ikili): 960x540 gri normalize edilmis ortalama mutlak
                   sapma (0-255; kucuk = benzer duzen).

Kullanim:
  py -3 tools/compare_ui_captures.py IMG [IMG ...]
  py -3 tools/compare_ui_captures.py A.png B.png C.png --baseline A.png
  py -3 tools/compare_ui_captures.py IMG --json rapor.json

Notlar:
  - Pillow (PIL) gerektirir; uretim koduna bagimliligi yoktur.
  - JPG DPI metadata'si runtime DPI degildir (kayit: kilavuz Ek D D.1).
  - Kare-basi tahsis kaygisi yoktur: tek-seferlik offline olcum aracidir.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("HATA: Pillow kurulu degil (py -3 -m pip install Pillow)", file=sys.stderr)
    sys.exit(2)

# Karsilastirma olcegi: buyuk goruntuleri ayni olcege normalize et.
DIFF_SIZE = (960, 540)
# Icerik maskesi esigi: arka plandan toplam kanal farki.
BG_DIFF_THRESHOLD = 60
# Icerik kutusu olcumunde kucultme carpani (hiz + gurultu azaltma).
BBOX_DOWNSCALE = 8


def _load(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def bg_color(img: Image.Image) -> tuple[int, int, int]:
    """Kucultulmus goruntunun baskin rengini dondur (arka plan tahmini)."""
    small = img.resize(
        (max(1, img.width // BBOX_DOWNSCALE), max(1, img.height // BBOX_DOWNSCALE))
    )
    colors = small.getcolors(maxcolors=100000) or []
    if not colors:
        return (0, 0, 0)
    return max(colors, key=lambda c: c[0])[1]


def content_bbox(img: Image.Image, bg: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    """Arka plandan ayrisan icerigin bbox'ini tam capda dondur; yoksa None."""
    sw = max(1, img.width // BBOX_DOWNSCALE)
    sh = max(1, img.height // BBOX_DOWNSCALE)
    small = img.resize((sw, sh))
    sp = small.load()
    xs, ys = [], []
    br, bgc, bb = bg
    for yy in range(sh):
        for xx in range(sw):
            r, g, b = sp[xx, yy]
            if abs(r - br) + abs(g - bgc) + abs(b - bb) > BG_DIFF_THRESHOLD:
                xs.append(xx)
                ys.append(yy)
    if not xs:
        return None
    return (
        min(xs) * BBOX_DOWNSCALE,
        min(ys) * BBOX_DOWNSCALE,
        max(xs) * BBOX_DOWNSCALE,
        max(ys) * BBOX_DOWNSCALE,
    )


def neighbor_diff(img: Image.Image) -> dict[str, list[int]]:
    """3 dikey + 3 yatay ornek cizgide komsu-piksel benzemezligi sayimi.

    DWM ~2x upscale tespiti: ciftlesme varsa komsu pikseller ayni renktedir,
    sayim ~0 cikar. Strateji-4 ornekleme (stride 4) DWM 2x durumunda hep
    ayni cifti ornekler; bu bilinclidir.
    """
    px = img.load()
    w, h = img.size
    diffs_v = []
    for y in (h // 4, h // 2, 3 * h // 4):
        d = sum(1 for x in range(0, w - 1, 4) if px[x, y] != px[x + 1, y])
        diffs_v.append(d)
    diffs_h = []
    for x in (w // 4, w // 2, 3 * w // 4):
        d = sum(1 for y in range(0, h - 1, 4) if px[x, y] != px[x, y + 1])
        diffs_h.append(d)
    return {"yatay_cizgiler": diffs_v, "dikey_cizgiler": diffs_h, "ornek_adedi": (w - 1) // 4}


def structural_diff(img_a: Image.Image, img_b: Image.Image) -> float:
    """Iki goruntunun gri-olcekli normalize ort. mutlak sapmasi (0-255)."""
    ga = img_a.convert("L").resize(DIFF_SIZE)
    gb = img_b.convert("L").resize(DIFF_SIZE)
    pa, pb = ga.load(), gb.load()
    total = 0
    for y in range(DIFF_SIZE[1]):
        for x in range(DIFF_SIZE[0]):
            total += abs(pa[x, y] - pb[x, y])
    return total / float(DIFF_SIZE[0] * DIFF_SIZE[1])


def metrics_for(path: str) -> dict:
    """Tek goruntu icin tum olcumleri hesapla."""
    img = _load(path)
    bg = bg_color(img)
    bbox = content_bbox(img, bg)
    result = {
        "dosya": path,
        "boyut": [img.width, img.height],
        "arka_plan": list(bg),
        "komsu_fark": neighbor_diff(img),
    }
    if bbox is None:
        result["icerik_bulundu"] = False
        return result
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    screen_cx = img.width / 2.0
    screen_cy = img.height / 2.0
    result["icerik_bulundu"] = True
    result["icerik_bbox"] = [x0, y0, x1, y1]
    result["icerik_genislik"] = width
    result["icerik_yukseklik"] = height
    result["merkez_sapma_px"] = [round(cx - screen_cx, 1), round(cy - screen_cy, 1)]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Quadrix UI capture olcum/karsilastirma araci (FAZ A0)"
    )
    parser.add_argument("images", nargs="+", help="Olceulecek goruntu dosyalari")
    parser.add_argument("--baseline", help="Yapisal fark referansi (varsayilan: ilk goruntu)")
    parser.add_argument("--json", dest="json_path", help="Raporu JSON olarak yaz")
    args = parser.parse_args(argv)

    report: dict = {"olcumler": []}
    for path in args.images:
        try:
            report["olcumler"].append(metrics_for(path))
        except Exception as exc:  # dosya yok / bozuk
            report["olcumler"].append({"dosya": path, "hata": str(exc)})

    baseline_path = args.baseline or (
        args.images[0] if len(args.images) > 1 else None
    )
    if baseline_path is not None and len(args.images) > 1:
        baseline_img = _load(baseline_path)
        diffs = {}
        for path in args.images:
            if path == baseline_path:
                continue
            diffs[f"{path} vs {baseline_path}"] = round(
                structural_diff(_load(path), baseline_img), 2
            )
        report["yapisal_fark"] = diffs

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
