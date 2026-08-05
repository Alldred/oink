"""Hourly sky / conditions timeline with weather icons."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather, icon_kind
from widgets.charts import (
    AXIS_LABEL_WIDTH,
    VERTICAL_LABEL_WIDTH,
    draw_time_grid,
    draw_vertical_label,
)
from widgets.icons import draw_weather_icon

from .base import Rect, Widget

# Show an icon every 2 hours so glyphs stay readable on 600px e-ink.
ICON_STEP_HOURS = 2


class SkyTimelineWidget(Widget):
    """Compact day strip of sun / cloud / rain icons."""

    name = "day"

    def __init__(self, rect: Rect, *, show_times: bool = False) -> None:
        super().__init__(rect)
        self.show_times = show_times

    def prepare(self, context: dict[str, Any]) -> None:
        get_weather(context)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        weather = get_weather(context)

        label_font = self.font(context, 22, bold=True)
        axis_font = self.font(context, 12, bold=False)

        r = self.rect
        codes = weather.hourly_weather_code

        chart_left = r.x + VERTICAL_LABEL_WIDTH + AXIS_LABEL_WIDTH
        chart_right = r.right - 2
        chart_top = r.y + 2
        chart_bottom = r.bottom - (14 if self.show_times else 2)
        if chart_bottom <= chart_top + 12 or chart_right <= chart_left + 24:
            return

        draw_time_grid(
            draw,
            chart_left,
            chart_right,
            chart_top,
            chart_bottom,
            font=axis_font,
            show_labels=self.show_times,
        )

        width = chart_right - chart_left
        hours = list(range(0, 24, ICON_STEP_HOURS))
        slot = width / 24
        icon_size = min(chart_bottom - chart_top - 4, max(14, int(slot * ICON_STEP_HOURS * 0.75)))
        cy = (chart_top + chart_bottom) // 2

        for hour in hours:
            code = codes[hour] if hour < len(codes) else 3
            kind = icon_kind(code, hour=hour)
            cx = chart_left + int((hour + ICON_STEP_HOURS / 2) * slot)
            draw_weather_icon(
                draw,
                kind,
                cx=cx,
                cy=cy,
                size=icon_size,
                fill=0,
                fonts_dir=fonts_dir,
                image=image,
            )

        draw_vertical_label(
            image,
            "Day",
            label_font,
            x=r.x,
            center_y=(chart_top + chart_bottom) // 2,
        )
