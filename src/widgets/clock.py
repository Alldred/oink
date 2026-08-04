"""Clock widget: current date and time for the e-ink dashboard."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from .base import Rect, Widget


class ClockWidget(Widget):
    """Display the dashboard generation date and time."""

    name = "clock"

    def __init__(self, rect: Rect, *, date_format: str = "%A, %-d %B %Y", time_format: str = "%H:%M") -> None:
        super().__init__(rect)
        # %-d is POSIX-only; Windows uses %#d. Prefer a portable fallback below.
        self.date_format = date_format
        self.time_format = time_format

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        now = self.now(context)

        time_font = self.load_font(fonts_dir, size=96, bold=True)
        date_font = self.load_font(fonts_dir, size=28, bold=False)

        time_text = self._format(now, self.time_format, fallback="%H:%M")
        date_text = self._format(now, self.date_format, fallback="%A, %d %B %Y")

        # Time dominates the upper portion of the rect; date sits below.
        r = self.rect
        time_bbox = draw.textbbox((0, 0), time_text, font=time_font)
        time_width = time_bbox[2] - time_bbox[0]
        time_height = time_bbox[3] - time_bbox[1]

        date_bbox = draw.textbbox((0, 0), date_text, font=date_font)
        date_width = date_bbox[2] - date_bbox[0]
        date_height = date_bbox[3] - date_bbox[1]

        gap = 24
        block_height = time_height + gap + date_height
        top = r.y + max(0, (r.height - block_height) // 2)

        time_x = r.x + (r.width - time_width) // 2 - time_bbox[0]
        time_y = top - time_bbox[1]
        draw.text((time_x, time_y), time_text, font=time_font, fill=0)

        date_x = r.x + (r.width - date_width) // 2 - date_bbox[0]
        date_y = top + time_height + gap - date_bbox[1]
        draw.text((date_x, date_y), date_text, font=date_font, fill=0)

    @staticmethod
    def _format(now, fmt: str, *, fallback: str) -> str:
        try:
            return now.strftime(fmt)
        except ValueError:
            return now.strftime(fallback)
