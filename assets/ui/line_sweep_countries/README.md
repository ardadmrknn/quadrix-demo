# Country line-sweep assets

Vendored PNGs for the country-themed Luna-Cat line-sweep skins. The PNGs
in this folder are consumed by the runtime (`src/country_sweep_assets.py`
+ `src/sweep_effects.py`); the SVG sources are **not** shipped because the
runtime cannot guarantee an SVG renderer is present.

Layout per country: `assets/ui/line_sweep_countries/<theme_id>/`

```
flag.png          Opaque rectangular flag (RGB, no alpha) — premium, official look.
provenance.txt    Source URL, license, fetch date.
```

> Note: country silhouettes (political map shapes) used to sit behind the
> flag in the store preview. They were removed, so only `flag.png` ships
> now. The generator no longer downloads any geometry.

## Source pipeline

| Asset | Source | License |
| --- | --- | --- |
| Flag PNG | [flag-icons](https://github.com/lipis/flag-icons) `flags/4x3/<iso2>.svg` | MIT |

`flag-icons` was chosen over Twemoji / Circle-Flags because it provides
official rectangular flags suitable for a premium store treatment.

## Regenerating

Dev-time generator bağımlılığı `.[dev]` içinde tanımlıdır:

```bash
python3.12 -m pip install --user -e ".[dev]"
```

Ardından asset'leri yeniden üretin:

```bash
python3 tools/generate_country_sweep_assets.py            # rebuild all
python3 tools/generate_country_sweep_assets.py --only fr  # rebuild one
python3 tools/generate_country_sweep_assets.py --force    # ignore cache
```

Not: `CairoSVG` bazı sistemlerde yerel Cairo kütüphanesi isteyebilir. Import
veya rasterization aşaması platformda eksik native bağımlılık nedeniyle
başarısız olursa önce sistem Cairo paketini kurup sonra `.[dev]` kurulumunu
yenileyin.

Per the AGENTS.md generated-markdown policy, this README is **not**
emitted by `tools/sync_markdown_docs.py`; it is a small canonical asset
note and may be edited directly when the asset pipeline changes.
