"""Base widget interface for the Oink dashboard renderer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Rect:
    """Pixel rectangle on the dashboard canvas."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2


class Widget(ABC):
    """Independent dashboard widget that paints into a rectangle."""

    name: str = "widget"

    def __init__(self, rect: Rect) -> None:
        self.rect = rect

    def prepare(self, context: dict[str, Any]) -> None:
        """Optional hook to fetch or compute data before drawing.

        Override in subclasses that need network I/O or heavy work.
        Failures should raise clear exceptions; the renderer catches them.
        """

    @abstractmethod
    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        """Render the widget into ``self.rect`` on ``image``."""

    # --- Shared drawing helpers ---

    @staticmethod
    def load_font(fonts_dir: Path, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load a bundled TrueType font, falling back to DejaVu then Pillow default."""
        primary = "Nunito-Bold.ttf" if bold else "Nunito-Regular.ttf"
        fallback = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        for filename in (primary, fallback):
            path = fonts_dir / filename
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def fill_background(self, draw: ImageDraw.ImageDraw, color: int = 255) -> None:
        """Fill the widget rectangle with a solid grayscale colour (0=black, 255=white)."""
        r = self.rect
        draw.rectangle([r.x, r.y, r.right - 1, r.bottom - 1], fill=color)

    def draw_centered_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        *,
        fill: int = 0,
        y_offset: int = 0,
    ) -> None:
        """Draw text horizontally centred in the widget rectangle."""
        r = self.rect
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = r.x + (r.width - text_width) // 2 - bbox[0]
        y = r.y + (r.height - text_height) // 2 - bbox[1] + y_offset
        draw.text((x, y), text, font=font, fill=fill)

    def draw_text_at(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        *,
        x: int | None = None,
        y: int | None = None,
        fill: int = 0,
        anchor: str | None = None,
    ) -> None:
        """Draw text at an absolute position, defaulting to the widget origin."""
        r = self.rect
        draw.text(
            (r.x if x is None else x, r.y if y is None else y),
            text,
            font=font,
            fill=fill,
            anchor=anchor,
        )

    @staticmethod
    def now(context: dict[str, Any]) -> datetime:
        """Return the generation timestamp from the render context."""
        value = context.get("now")
        if isinstance(value, datetime):
            return value
        raise RuntimeError("Render context is missing a timezone-aware 'now' datetime.")
