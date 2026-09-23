#!/usr/bin/env python3
"""Сборка иллюстраций empty/error → webp @1x/@2x для public/illustrations.

Читает исходники из frontend/design-src/illustrations/*.png:
  - убирает фон (прозрачность, почти белый, серая «шахматка» Photoshop);
  - обрезает пустые поля;
  - пишет name.webp (длинная сторона 200px) и name@2x.webp (400px).

Запуск из корня репо или из frontend/:
  python3 frontend/scripts/build_images.py
  python3 frontend/scripts/build_images.py empty-sales empty-stock
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]  # frontend/
SRC_DIR = ROOT / "design-src" / "illustrations"
OUT_DIR = ROOT / "public" / "illustrations"

SIZE_1X = 200
SIZE_2X = 400
WHITE_THRESH = 250
ALPHA_THRESH = 8


def is_backdrop(r: int, g: int, b: int, a: int) -> bool:
    """Прозрачность, почти белый или серая шахматка Photoshop (~234/254)."""
    if a <= ALPHA_THRESH:
        return True
    if r >= WHITE_THRESH and g >= WHITE_THRESH and b >= WHITE_THRESH:
        return True
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn <= 8 and mn >= 220:
        return True
    return False


def remove_backdrop(rgba: Image.Image) -> Image.Image:
    out = rgba.copy()
    pixels = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if is_backdrop(r, g, b, a):
                pixels[x, y] = (r, g, b, 0)
    return out


def crop_content(rgba: Image.Image) -> Image.Image:
    pixels = rgba.load()
    w, h = rgba.size
    min_x, min_y = w, h
    max_x, max_y = -1, -1
    for y in range(h):
        for x in range(w):
            if pixels[x, y][3] <= ALPHA_THRESH:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < 0:
        return rgba
    pad = 4
    return rgba.crop(
        (
            max(0, min_x - pad),
            max(0, min_y - pad),
            min(w, max_x + 1 + pad),
            min(h, max_y + 1 + pad),
        )
    )


def fit(im: Image.Image, long_side: int) -> Image.Image:
    w, h = im.size
    if w <= 0 or h <= 0:
        return im
    scale = long_side / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    return im.resize((nw, nh), Image.Resampling.LANCZOS)


def process(src: Path) -> dict:
    name = src.stem
    im = Image.open(src)
    had_alpha = im.mode in ("RGBA", "LA", "PA") or ("transparency" in im.info)
    rgba = crop_content(remove_backdrop(im.convert("RGBA")))
    out_1x = OUT_DIR / f"{name}.webp"
    out_2x = OUT_DIR / f"{name}@2x.webp"
    fit(rgba, SIZE_1X).save(out_1x, "WEBP", quality=82, method=6)
    fit(rgba, SIZE_2X).save(out_2x, "WEBP", quality=82, method=6)
    return {
        "name": name,
        "src": f"{rgba.size[0]}x{rgba.size[1]}",
        "had_alpha": had_alpha,
        "size_1x": Image.open(out_1x).size,
        "size_2x": Image.open(out_2x).size,
    }


def main(argv: list[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC_DIR.is_dir():
        print(f"нет каталога исходников: {SRC_DIR}", file=sys.stderr)
        return 1
    names = argv[1:]
    sources = (
        [SRC_DIR / f"{n}.png" for n in names]
        if names
        else sorted(SRC_DIR.glob("*.png"))
    )
    if not sources:
        print("нечего собирать", file=sys.stderr)
        return 1
    for src in sources:
        if not src.is_file():
            print(f"пропуск (нет файла): {src.name}", file=sys.stderr)
            continue
        info = process(src)
        alpha = "alpha" if info["had_alpha"] else "no-alpha→RGBA"
        print(
            f"{info['name']}: crop {info['src']} → "
            f"{info['size_1x'][0]}x{info['size_1x'][1]} / "
            f"{info['size_2x'][0]}x{info['size_2x'][1]} ({alpha})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
