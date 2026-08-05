"""Whimsical weather sentence under the date."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather
from weather.whimsy import pick_whimsy_line

from .base import Rect, Widget


class WhimsyWidget(Widget):
    """One or two lines of weather silliness, centred under the date."""

    name = "whimsy"

    def prepare(self, context: dict[str, Any]) -> None:
        get_weather(context)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        weather = get_weather(context)
        now = self.now(context)
        line = pick_whimsy_line(weather, now.date())

        font = self.font(context, 17, bold=False)
        r = self.rect
        max_width = r.width
        lines = self._wrap(draw, line, font, max_width)
        if not lines:
            return

        # Vertically centre the wrapped block; each line horizontally centred.
        heights = []
        widths = []
        for text in lines:
            bbox = draw.textbbox((0, 0), text, font=font)
            heights.append(bbox[3] - bbox[1])
            widths.append(bbox[2] - bbox[0])
        gap = 2
        block_h = sum(heights) + gap * (len(lines) - 1)
        y = r.y + max(0, (r.height - block_h) // 2)

        for text, h, w in zip(lines, heights, widths):
            bbox = draw.textbbox((0, 0), text, font=font)
            x = r.x + (r.width - w) // 2 - bbox[0]
            draw.text((x, y - bbox[1]), text, font=font, fill=40)
            y += h + gap

    @staticmethod
    def _wrap(
        draw: ImageDraw.ImageDraw,
        text: str,
        font,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            bbox = draw.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        # Cap at two lines; if still long, truncate the second with an ellipsis.
        if len(lines) > 2:
            lines = lines[:2]
        if len(lines) == 2:
            second = lines[1]
            while second:
                bbox = draw.textbbox((0, 0), second, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    break
                second = second[:-1]
            if second != lines[1]:
                trimmed = second.rstrip()
                if len(trimmed) > 1:
                    trimmed = trimmed[:-1].rstrip() + "…"
                lines[1] = trimmed
        return lines
