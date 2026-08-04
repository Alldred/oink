"""Date widget: current date for the e-ink dashboard."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from .base import Rect, Widget


class DateWidget(Widget):
    """Display the dashboard generation date at the top of its rect."""

    name = "date"

    def __init__(self, rect: Rect, *, date_format: str = "%A %-d %B") -> None:
        super().__init__(rect)
        # %-d is POSIX-only; Windows uses %#d. Prefer a portable fallback below.
        self.date_format = date_format

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        now = self.now(context)

        date_font = self.load_font(fonts_dir, size=24, bold=False)
        date_text = self._format(now, self.date_format, fallback="%A %d %B")

        r = self.rect
        date_bbox = draw.textbbox((0, 0), date_text, font=date_font)
        date_width = date_bbox[2] - date_bbox[0]

        date_x = r.x + (r.width - date_width) // 2 - date_bbox[0]
        date_y = r.y - date_bbox[1]
        draw.text((date_x, date_y), date_text, font=date_font, fill=0)

    @staticmethod
    def _format(now, fmt: str, *, fallback: str) -> str:
        try:
            return now.strftime(fmt)
        except ValueError:
            return now.strftime(fallback)
