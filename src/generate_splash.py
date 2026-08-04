#!/usr/bin/env python3
"""Generate the Kindle-side Oink splash PNG (600×800 grayscale).

Prefers assets/splash-source.png when present; otherwise composes from
assets/logo.png plus a short status line.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 600, 800
OUT = ROOT / "kindle" / "extensions" / "oink" / "splash.png"


def fit_on_canvas(src: Image.Image, size: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    canvas = Image.new("L", size, 255)
    src = src.convert("L")
    src_ratio = src.width / src.height
    tgt_ratio = size[0] / size[1]
    if src_ratio > tgt_ratio:
        new_w = size[0]
        new_h = round(size[0] / src_ratio)
    else:
        new_h = size[1]
        new_w = round(size[1] * src_ratio)
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x = (size[0] - new_w) // 2
    y = (size[1] - new_h) // 2
    canvas.paste(resized, (x, y))
    return canvas


def from_logo(logo_path: Path) -> Image.Image:
    fonts = ROOT / "fonts"
    sub = ImageFont.truetype(str(fonts / "DejaVuSans.ttf"), 28)
    image = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)

    logo = Image.open(logo_path).convert("L")
    max_w = WIDTH - 80
    scale = max_w / logo.width
    logo = logo.resize((max_w, max(1, round(logo.height * scale))), Image.Resampling.LANCZOS)
    x = (WIDTH - logo.width) // 2
    y = HEIGHT // 2 - logo.height // 2 - 40
    image.paste(logo, (x, y))

    text = "starting…"
    bbox = draw.textbbox((0, 0), text, font=sub)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2 - bbox[0], y + logo.height + 36 - bbox[1]), text, font=sub, fill=0)
    return image


def main() -> int:
    source = ROOT / "assets" / "splash-source.png"
    logo = ROOT / "assets" / "logo.png"

    if source.is_file():
        image = fit_on_canvas(Image.open(source))
    elif logo.is_file():
        image = from_logo(logo)
    else:
        print("error: need assets/splash-source.png or assets/logo.png", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, format="PNG", optimize=True)
    print(f"Splash written to {OUT} ({image.size[0]}x{image.size[1]} {image.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
