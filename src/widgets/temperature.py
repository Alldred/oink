"""Adaptive hourly temperature forecast chart."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather
from widgets.charts import (
    AXIS_LABEL_WIDTH,
    VERTICAL_LABEL_WIDTH,
    chart_points,
    current_and_remaining_max,
    draw_area_curve,
    draw_hline,
    draw_metric,
    draw_now_marker,
    draw_time_grid,
    draw_vertical_label,
    format_temp,
    nice_axis_ticks,
    y_scale,
)

from .base import Rect, Widget


class TemperatureForecastWidget(Widget):
    """Hourly temperature curve scaled to today's range."""

    name = "temperature"

    def __init__(self, rect: Rect, *, show_times: bool = False) -> None:
        super().__init__(rect)
        self.show_times = show_times

    def prepare(self, context: dict[str, Any]) -> None:
        get_weather(context)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        fonts_dir = context["fonts_dir"]
        weather = get_weather(context)

        label_font = self.load_font(fonts_dir, size=22, bold=True)
        axis_font = self.load_font(fonts_dir, size=12, bold=False)
        metric_font = self.load_font(fonts_dir, size=18, bold=True)

        r = self.rect
        values = weather.hourly_temperature
        now = self.now(context)
        current, rest_max = current_and_remaining_max(values, now)
        lo = min(values)
        hi = max(values)
        span = max(4.0, hi - lo)
        pad = max(0.8, span * 0.1)
        guide_values = nice_axis_ticks(lo - pad, hi + pad, max_ticks=9)
        scale_min = guide_values[0]
        scale_max = guide_values[-1]

        chart_left = r.x + VERTICAL_LABEL_WIDTH + AXIS_LABEL_WIDTH
        chart_right = r.right - 2
        chart_top = r.y + 2
        chart_bottom = r.bottom - (14 if self.show_times else 1)
        if chart_bottom <= chart_top + 18 or chart_right <= chart_left + 18:
            return

        def y_for(value: float, top: int, bottom: int) -> int:
            return y_scale(value, scale_min, scale_max, top, bottom)

        axis_x = r.x + VERTICAL_LABEL_WIDTH
        guide_values = nice_axis_ticks(scale_min, scale_max, max_ticks=7)

        def draw_guides() -> None:
            for label_value in guide_values:
                y = y_for(label_value, chart_top, chart_bottom)
                draw_hline(draw, chart_left, chart_right, y, fill=175)
                text = format_temp(label_value)
                label_bbox = draw.textbbox((0, 0), text, font=axis_font)
                label_h = label_bbox[3] - label_bbox[1]
                label_y = y - label_h // 2
                label_y = max(chart_top + 1, min(label_y, chart_bottom - label_h - 1))
                draw.text((axis_x, label_y), text, font=axis_font, fill=110)
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

        draw_guides()

        points = chart_points(
            values,
            chart_left,
            chart_right,
            chart_top,
            chart_bottom,
            y_for_value=y_for,
            smooth=True,
        )
        draw_area_curve(draw, points, chart_bottom, image=image)
        # Grid on top so curves don't hide axis / time lines.
        draw_guides()
        draw_now_marker(
            draw,
            points,
            left=chart_left,
            right=chart_right,
            now=now,
            hours=len(values),
        )

        draw_vertical_label(
            image,
            "Temp",
            label_font,
            x=r.x,
            center_y=(chart_top + chart_bottom) // 2,
        )
        draw_metric(
            draw,
            f"{format_temp(current)} / {format_temp(rest_max)}",
            metric_font,
            right=chart_right,
            top=chart_top,
        )
