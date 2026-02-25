from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


def _rgb_to_hsv(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = rgb.astype(np.float32) / 255.0
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    s = np.zeros_like(cmax)
    v = cmax

    nz = delta > 1e-6
    s[nz] = delta[nz] / np.maximum(cmax[nz], 1e-6)

    mr = (cmax == r) & nz
    mg = (cmax == g) & nz
    mb = (cmax == b) & nz

    h[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6
    h[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2
    h[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4
    h = h / 6.0
    return h, s, v


def _pick_bg_colors(rgb: np.ndarray, alpha: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    h, w, _ = rgb.shape
    margin = max(16, min(h, w) // 10)
    border = np.zeros((h, w), dtype=bool)
    border[:margin, :] = True
    border[-margin:, :] = True
    border[:, :margin] = True
    border[:, -margin:] = True
    mask = border & (alpha > 245)
    samples = rgb[mask]
    if samples.size == 0:
        samples = rgb.reshape(-1, 3)

    q = (samples // 4) * 4
    uniq, cnt = np.unique(q, axis=0, return_counts=True)
    order = np.argsort(cnt)[::-1]
    uniq = uniq[order]
    c1 = uniq[0].astype(np.float32)
    c2 = c1.copy()
    for c in uniq[1:]:
        if np.linalg.norm(c.astype(np.float32) - c1) > 12:
            c2 = c.astype(np.float32)
            break
    return c1, c2


def cleanup_sheet(input_path: Path, output_path: Path) -> None:
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3].astype(np.float32)

    _, sat, val = _rgb_to_hsv(arr[..., :3])
    c1, c2 = _pick_bg_colors(arr[..., :3], arr[..., 3])
    d1 = np.linalg.norm(rgb - c1.reshape(1, 1, 3), axis=2)
    d2 = np.linalg.norm(rgb - c2.reshape(1, 1, 3), axis=2)

    checker_like = ((d1 < 22) | (d2 < 22)) & (sat < 0.22) & (val > 0.08) & (val < 0.75)
    dark_bg = (val < 0.12) & (sat < 0.20)
    clear = (checker_like | dark_bg) & (alpha > 15)
    alpha[clear] = 0

    low_alpha = (alpha > 0) & (alpha < 120)
    desat_dark = (sat < 0.28) & (val < 0.35)
    suppress = low_alpha & desat_dark
    alpha[suppress] *= 0.25

    out = arr.copy()
    out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    zero = out[..., 3] == 0
    out[..., 0][zero] = 0
    out[..., 1][zero] = 0
    out[..., 2][zero] = 0
    Image.fromarray(out, mode="RGBA").save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean checker/dark background artifacts from card effect sprite sheets.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()

    inp = args.input
    if not inp.exists():
        raise FileNotFoundError(f"Input not found: {inp}")

    out = args.output
    if out is None:
        out = inp.with_name(inp.stem + "_clean" + inp.suffix)

    cleanup_sheet(inp, out)
    print(f"OK: {out}")


if __name__ == "__main__":
    main()
