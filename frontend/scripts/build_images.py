#!/usr/bin/env python3
"""Сборка иллюстраций empty/error → webp @1x/@2x для public/illustrations.

Читает исходники из frontend/design-src/illustrations/*.png:
  - убирает фон (прозрачность, почти белый, серая «шахматка» Photoshop);
  - снимает светлую кайму (fringe) на краях после вырезания с белого;
  - обрезает пустые поля;
  - пишет name.webp (длинная сторона 240px) и name@2x.webp (480px).

Запуск из корня репо или из frontend/:
  python3 frontend/scripts/build_images.py
  python3 frontend/scripts/build_images.py empty-sales empty-stock
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]  # frontend/
SRC_DIR = ROOT / "design-src" / "illustrations"
OUT_DIR = ROOT / "public" / "illustrations"

SIZE_1X = 240
SIZE_2X = 480
# Лёгкий feather края (blur alpha) — мягче «ножниц», без тёмного дыма
SOFTEN_1X = 1.1
SOFTEN_2X = 1.4
WHITE_THRESH = 248
ALPHA_THRESH = 8
# С alpha-исходником белое не ниже этого alpha считается содержимым
OPAQUE_WHITE_ALPHA = 250
# Байк-ин светлая тень/glow: низкий alpha + серый/светлый, не antialias объекта
SOFT_GLOW_ALPHA = 70
SOFT_GLOW_LUMA = 140
SOFT_GLOW_SAT = 40


def luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_backdrop(r: int, g: int, b: int, a: int) -> bool:
    """Прозрачность, почти белый или серая шахматка Photoshop (~234/254)."""
    if a <= ALPHA_THRESH:
        return True
    if r >= WHITE_THRESH and g >= WHITE_THRESH and b >= WHITE_THRESH:
        return True
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn <= 10 and mn >= 215:
        return True
    return False


def has_real_alpha(rgba: Image.Image) -> bool:
    """Исходник уже вырезан (есть заметная прозрачность) — фон задан alpha."""
    hist = rgba.getchannel("A").histogram()
    return sum(hist[: ALPHA_THRESH + 1]) >= 0.05 * sum(hist)


def remove_backdrop(rgba: Image.Image) -> Image.Image:
    # С настоящей alpha непрозрачное белое — это содержимое (бумага чека,
    # экран), а не фон: иначе в тёмной теме сквозь него видно --bg.
    # Полупрозрачное белое — запечённое свечение, его по-прежнему убираем.
    keep_opaque_white = has_real_alpha(rgba)
    out = rgba.copy()
    pixels = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if keep_opaque_white and a >= OPAQUE_WHITE_ALPHA:
                continue
            if is_backdrop(r, g, b, a):
                # RGB=0 при a=0 — иначе LANCZOS смешает белый → светлая кайма
                pixels[x, y] = (0, 0, 0, 0)
    return out


def premultiply(rgba: Image.Image) -> Image.Image:
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                px[x, y] = (0, 0, 0, 0)
            elif a < 255:
                f = a / 255.0
                px[x, y] = (int(round(r * f)), int(round(g * f)), int(round(b * f)), a)
    return out


def unpremultiply(rgba: Image.Image) -> Image.Image:
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                px[x, y] = (0, 0, 0, 0)
            elif a < 255:
                f = 255.0 / a
                px[x, y] = (
                    min(255, int(round(r * f))),
                    min(255, int(round(g * f))),
                    min(255, int(round(b * f))),
                    a,
                )
    return out


def zero_transparent_rgb(rgba: Image.Image) -> Image.Image:
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= ALPHA_THRESH:
                px[x, y] = (0, 0, 0, 0)
    return out


def unmatte_white(rgba: Image.Image) -> Image.Image:
    """Восстановить цвет объекта из антиалиаса поверх белого. Alpha не трогаем."""
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= ALPHA_THRESH:
                px[x, y] = (0, 0, 0, 0)
                continue
            if a >= 250:
                continue
            af = a / 255.0

            def ch(c: int) -> int:
                f = (c - (1.0 - af) * 255.0) / af
                return max(0, min(255, int(round(f))))

            px[x, y] = (ch(r), ch(g), ch(b), a)
    return out


def remove_soft_glow(rgba: Image.Image) -> Image.Image:
    """Только байк-ин светлые тени (серый low-alpha), без срезания AA объекта."""
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= ALPHA_THRESH or a > SOFT_GLOW_ALPHA:
                continue
            sat = max(r, g, b) - min(r, g, b)
            if sat <= SOFT_GLOW_SAT and luma(r, g, b) >= SOFT_GLOW_LUMA:
                px[x, y] = (0, 0, 0, 0)
    return out


def _neighbors8(x: int, y: int, w: int, h: int):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                yield nx, ny


def recolor_light_rim(rgba: Image.Image) -> Image.Image:
    """Светлый ободок у края → цвет более тёмных соседей. Alpha не трогаем (нет «ножниц»)."""
    out = rgba.copy()
    px = out.load()
    src = rgba.copy()
    sp = src.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a <= ALPHA_THRESH:
                continue
            L = luma(r, g, b)
            if L < 145:
                continue
            touches_clear = any(
                sp[nx, ny][3] <= ALPHA_THRESH for nx, ny in _neighbors8(x, y, w, h)
            )
            if not touches_clear:
                continue
            acc_r = acc_g = acc_b = n = 0
            for nx, ny in _neighbors8(x, y, w, h):
                rr, gg, bb, aa = sp[nx, ny]
                if aa < 180:
                    continue
                if luma(rr, gg, bb) <= min(L - 20, 140):
                    acc_r += rr
                    acc_g += gg
                    acc_b += bb
                    n += 1
            if n:
                px[x, y] = (acc_r // n, acc_g // n, acc_b // n, a)
            elif a < 200 and L >= 190:
                # нет опоры — гасим только явный светлый полупрозрачный мусор
                px[x, y] = (0, 0, 0, 0)
    return out


def clean_edges(rgba: Image.Image) -> Image.Image:
    """Unmatte + soft-glow + перекраска светлого ободка. Плавный AA сохраняется."""
    return kill_dark_smoke(
        zero_transparent_rgb(
            recolor_light_rim(remove_soft_glow(unmatte_white(rgba)))
        )
    )


def kill_resize_fringe(rgba: Image.Image) -> Image.Image:
    """После даунскейла: только явный белый мусор с низким alpha, без срезания AA."""
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= ALPHA_THRESH:
                px[x, y] = (0, 0, 0, 0)
                continue
            if a > 60:
                continue
            sat = max(r, g, b) - min(r, g, b)
            if luma(r, g, b) >= 200 and sat <= 55:
                px[x, y] = (0, 0, 0, 0)
    return out


def soften(rgba: Image.Image, radius: float) -> Image.Image:
    """Смягчить силуэт через blur alpha + подтянуть RGB с соседей.

    Не используем blur всего premul-RGBA: он размазывает тёмные объекты
    в «дым» (видно у звёздочек state-no-debts на светлом фоне).
    """
    if radius <= 0:
        return rgba
    src = zero_transparent_rgb(rgba)
    alpha = src.getchannel("A").filter(ImageFilter.GaussianBlur(radius=radius))
    out = src.copy()
    sp = src.load()
    op = out.load()
    ap = alpha.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a0 = sp[x, y]
            a1 = ap[x, y]
            if a1 <= ALPHA_THRESH:
                op[x, y] = (0, 0, 0, 0)
                continue
            if a0 > ALPHA_THRESH:
                # Было содержимое — оставляем цвет, берём смягчённую alpha
                op[x, y] = (r, g, b, a1)
                continue
            # Новая полупрозрачность снаружи: цвет с непрозрачных соседей
            acc_r = acc_g = acc_b = n = 0
            for nx, ny in _neighbors8(x, y, w, h):
                rr, gg, bb, aa = sp[nx, ny]
                if aa >= 180:
                    acc_r += rr
                    acc_g += gg
                    acc_b += bb
                    n += 1
            if n:
                op[x, y] = (acc_r // n, acc_g // n, acc_b // n, a1)
            else:
                op[x, y] = (0, 0, 0, 0)
    return kill_dark_smoke(zero_transparent_rgb(out))


def kill_dark_smoke(rgba: Image.Image) -> Image.Image:
    """Убрать тёмный «дым» — низкий alpha + почти чёрный (артефакт blur/теней)."""
    out = rgba.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= ALPHA_THRESH or a >= 140:
                continue
            L = luma(r, g, b)
            sat = max(r, g, b) - min(r, g, b)
            if L <= 55 or (L <= 85 and sat <= 25):
                px[x, y] = (0, 0, 0, 0)
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
    # Запас под feather после resize
    pad = 12
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
    # Unmatte только на полном размере — после resize alpha уже корректный,
    # повторный unmatte даёт «ножницы» (жёсткий край).
    rgba = crop_content(clean_edges(remove_backdrop(im.convert("RGBA"))))
    out_1x = OUT_DIR / f"{name}.webp"
    out_2x = OUT_DIR / f"{name}@2x.webp"
    premul = premultiply(rgba)
    for path, size in ((out_1x, SIZE_1X), (out_2x, SIZE_2X)):
        radius = SOFTEN_1X if size == SIZE_1X else SOFTEN_2X
        scaled = soften(
            kill_resize_fringe(recolor_light_rim(unpremultiply(fit(premul, size)))),
            radius,
        )
        scaled.save(path, "WEBP", lossless=True, exact=True)
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
