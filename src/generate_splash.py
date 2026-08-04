#!/usr/bin/env python3
"""Generate the Kindle-side Oink splash PNG (600×800 grayscale)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 600, 800
MARGIN = 32


def main() -> int:
    fonts = ROOT / "fonts"
    out = ROOT / "kindle" / "extensions" / "oink" / "splash.png"
    title_font = ImageFont.truetype(str(fonts / "DejaVuSans-Bold.ttf"), 72)
    sub_font = ImageFont.truetype(str(fonts / "DejaVuSans.ttf"), 28)

    image = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)

    def centered(text: str, font: ImageFont.ImageFont, y: int) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        x = (WIDTH - width) // 2 - bbox[0]
        draw.text((x, y - bbox[1]), text, font=font, fill=0)

    draw.line([(MARGIN, 220), (WIDTH - MARGIN, 220)], fill=0, width=2)
    centered("Oink", title_font, 280)
    centered("Starting dashboard…", sub_font, 380)
    draw.line([(MARGIN, 480), (WIDTH - MARGIN, 480)], fill=0, width=2)

    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG", optimize=True)
    print(f"Splash written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
