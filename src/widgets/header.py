"""Date header for the dashboard."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from .base import Rect, Widget


class HeaderWidget(Widget):
    """Centred date across the top band."""

    name = "header"

    def __init__(self, rect: Rect, *, date_format: str = "%A %-d %B") -> None:
        super().__init__(rect)
        self.date_format = date_format

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        now = self.now(context)

        date_font = self.load_font(fonts_dir, size=24, bold=False)
        date_text = self._format(now, self.date_format, fallback="%A %d %B")

        r = self.rect
        bbox = draw.textbbox((0, 0), date_text, font=date_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = r.x + (r.width - text_w) // 2 - bbox[0]
        y = r.y + (r.height - text_h) // 2 - bbox[1]
        draw.text((x, y), date_text, font=date_font, fill=0)

    @staticmethod
    def _format(now, fmt: str, *, fallback: str) -> str:
        try:
            return now.strftime(fmt)
        except ValueError:
            return now.strftime(fallback)
