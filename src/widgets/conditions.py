"""Overall day conditions."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather, weather_label

from .base import Rect, Widget


class ConditionsWidget(Widget):
    """Show today's dominant condition (temps live on the temperature chart)."""

    name = "conditions"

    def prepare(self, context: dict[str, Any]) -> None:
        get_weather(context)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        weather = get_weather(context)

        title_font = self.load_font(fonts_dir, size=30, bold=True)
        label = weather_label(weather.weather_code)
        r = self.rect
        draw.text((r.x, r.y), label, font=title_font, fill=0)
