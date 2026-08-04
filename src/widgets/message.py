"""Simple status / message widget."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from .base import Rect, Widget


class MessageWidget(Widget):
    """Display a short centred status message."""

    name = "message"

    def __init__(self, rect: Rect, *, text: str = "Oink is working!") -> None:
        super().__init__(rect)
        self.text = text

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        font = self.load_font(fonts_dir, size=32, bold=True)
        self.draw_centered_text(draw, self.text, font, fill=0)
