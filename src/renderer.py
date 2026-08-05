"""Render a list of widgets onto a Kindle-sized grayscale canvas."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from layout import CANVAS_HEIGHT, CANVAS_WIDTH
from widgets.base import Widget

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Europe/London"


class Renderer:
    """Compose widgets onto a white 600×800 grayscale image."""

    def __init__(
        self,
        widgets: list[Widget],
        *,
        fonts_dir: Path,
        timezone: str = DEFAULT_TIMEZONE,
        width: int = CANVAS_WIDTH,
        height: int = CANVAS_HEIGHT,
    ) -> None:
        self.widgets = widgets
        self.fonts_dir = fonts_dir
        self.timezone = timezone
        self.width = width
        self.height = height

    def render(
        self,
        *,
        now: datetime | None = None,
        weather: Any | None = None,
        weather_stale: bool = False,
        weather_cache_path: Path | None = None,
    ) -> Image.Image:
        """Return a mode-``L`` (8-bit grayscale) Pillow image."""
        try:
            tz = ZoneInfo(self.timezone)
        except Exception as exc:  # noqa: BLE001 - surface timezone mistakes clearly
            raise RuntimeError(
                f"Unknown timezone '{self.timezone}'. "
                "Use an IANA name such as 'Europe/London'."
            ) from exc

        if now is None:
            now = datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)

        image = Image.new("L", (self.width, self.height), color=255)
        draw = ImageDraw.Draw(image)

        context: dict[str, Any] = {
            "now": now,
            "fonts_dir": self.fonts_dir,
            "timezone": self.timezone,
            "width": self.width,
            "height": self.height,
            "weather_stale": weather_stale,
            "_font_cache": {},
        }
        if weather_cache_path is not None:
            context["weather_cache_path"] = weather_cache_path
        if weather is not None:
            context["weather"] = weather

        for widget in self.widgets:
            try:
                widget.prepare(context)
                widget.draw(image, draw, context)
            except Exception as exc:  # noqa: BLE001 - keep other widgets working
                logger.error("Widget '%s' failed: %s", widget.name, exc)
                self._draw_error(draw, widget, str(exc))

        return image

    def save(
        self,
        path: Path,
        *,
        now: datetime | None = None,
        weather: Any | None = None,
        weather_stale: bool = False,
        weather_cache_path: Path | None = None,
    ) -> Path:
        """Render and write a PNG suitable for Kindle ``eips -g``."""
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        image = self.render(
            now=now,
            weather=weather,
            weather_stale=weather_stale,
            weather_cache_path=weather_cache_path,
        )

        # 8-bit grayscale PNG is the widely verified format for eips on
        # firmware 5.x Kindles. Avoid palette/1-bit conversion here.
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            image.save(tmp_path, format="PNG", optimize=True)
            tmp_path.replace(path)
        except OSError as exc:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to write dashboard image to {path}: {exc}") from exc

        logger.info("Wrote %dx%d grayscale PNG to %s", self.width, self.height, path)
        return path

    @staticmethod
    def _draw_error(draw: ImageDraw.ImageDraw, widget: Widget, message: str) -> None:
        """Paint a minimal error placeholder so failures are visible on-device."""
        r = widget.rect
        draw.rectangle([r.x, r.y, r.right - 1, r.bottom - 1], outline=0, width=2)
        draw.text((r.x + 8, r.y + 8), f"{widget.name} error", fill=0)
        draw.text((r.x + 8, r.y + 28), message[:48], fill=0)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
