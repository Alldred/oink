"""Fixed-scale hourly rain forecast bar chart."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather
from widgets.charts import (
    AXIS_LABEL_WIDTH,
    VERTICAL_LABEL_WIDTH,
    draw_hline,
    draw_metric,
    draw_time_grid,
    draw_vertical_label,
    format_mm,
    y_scale,
)

from .base import Rect, Widget

# Fixed intensity scale so light rain stays visually "light".
LIGHT_MM = 2.5
MODERATE_MM = 7.5
HEAVY_MM = 15.0
BANDS = (("High", HEAVY_MM), ("Med", MODERATE_MM), ("Low", LIGHT_MM))


class RainForecastWidget(Widget):
    """Daily precipitation bars on a fixed Low / Med / High scale."""

    name = "rain"

    def __init__(self, rect: Rect, *, show_times: bool = False) -> None:
        super().__init__(rect)
        self.show_times = show_times

    def prepare(self, context: dict[str, Any]) -> None:
        get_weather(context)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        weather = get_weather(context)

        label_font = self.font(context, 22, bold=True)
        axis_font = self.font(context, 12, bold=False)
        metric_font = self.font(context, 18, bold=True)

        r = self.rect
        values = weather.hourly_precipitation

        chart_left = r.x + VERTICAL_LABEL_WIDTH + AXIS_LABEL_WIDTH
        chart_right = r.right - 2
        chart_top = r.y + 2
        chart_bottom = r.bottom - (14 if self.show_times else 1)
        if chart_bottom <= chart_top + 18 or chart_right <= chart_left + 18:
            return

        def y_for(value: float, top: int, bottom: int) -> int:
            return y_scale(value, 0.0, HEAVY_MM, top, bottom)

        axis_x = r.x + VERTICAL_LABEL_WIDTH
        for name, mm in BANDS:
            y = y_for(mm, chart_top, chart_bottom)
            draw_hline(draw, chart_left, chart_right, y, fill=175)
            label_bbox = draw.textbbox((0, 0), name, font=axis_font)
            label_h = label_bbox[3] - label_bbox[1]
            label_y = chart_top + 1 if name == "High" else y - label_h - 1
            draw.text((axis_x, label_y), name, font=axis_font, fill=110)

        draw_hline(draw, chart_left, chart_right, chart_bottom, fill=130)
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
        slot = width / 24
        bar_width = max(4, int(slot * 0.55))
        for hour, mm in enumerate(values):
            if mm <= 0:
                continue
            bar_top = min(y_for(mm, chart_top, chart_bottom), chart_bottom - 2)
            cx = chart_left + int((hour + 0.5) * slot)
            x0 = cx - bar_width // 2
            draw.rectangle([x0, bar_top, x0 + bar_width, chart_bottom], fill=30)

        draw_vertical_label(
            image,
            "Rain",
            label_font,
            x=r.x,
            center_y=(chart_top + chart_bottom) // 2,
        )
        draw_metric(
            draw,
            format_mm(weather.precipitation_sum),
            metric_font,
            right=chart_right,
            top=chart_top,
        )
