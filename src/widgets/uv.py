"""Hourly UV Index forecast with intensity-shaded fill."""

from __future__ import annotations

import math
from typing import Any

from PIL import Image, ImageDraw

from weather import get_weather
from widgets.charts import (
    AXIS_LABEL_WIDTH,
    VERTICAL_LABEL_WIDTH,
    chart_points,
    current_and_remaining_max,
    draw_hline,
    draw_metric,
    draw_now_marker,
    draw_shaded_area_curve,
    draw_time_grid,
    draw_vertical_label,
    smooth_series,
    y_scale,
)

from .base import Rect, Widget


def uv_level(value: float) -> int:
    """Integer UV for display and shading — same rounding as the metric badge."""
    return int(round(float(value)))


def uv_fill_grey(value: float) -> int:
    """Stronger UV → darker grey. 0–3 light, 4–5 mid, 6–7 dark, 8+ black.

    Uses ``uv_level`` so fill bands match the current/max integers (e.g. 3.6
    shows as 4 and gets the mid shade, not the light band from a raw ``< 4``).
    """
    level = uv_level(value)
    if level < 4:
        return 210
    if level < 6:
        return 145
    if level < 8:
        return 75
    return 25


def uv_scale_max(day_peak: float) -> int:
    """Axis top = today's peak + 2 (e.g. max 3 → 5, max 6 → 8)."""
    return max(3, math.ceil(float(day_peak)) + 2)


def uv_axis_ticks(scale_max: int) -> tuple[int, ...]:
    """Every integer from the scale top down to 0."""
    top = max(0, int(scale_max))
    return tuple(range(top, -1, -1))


class UVForecastWidget(Widget):
    """Hourly UV curve scaled to peak+2, with intensity greys."""

    name = "uv"

    def __init__(self, rect: Rect, *, show_times: bool = True) -> None:
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
        values = weather.hourly_uv_index
        now = self.now(context)
        current, rest_max = current_and_remaining_max(values, now)
        day_peak = max(values) if values else 0.0
        scale_max = float(uv_scale_max(day_peak))
        ticks = uv_axis_ticks(int(scale_max))

        chart_left = r.x + VERTICAL_LABEL_WIDTH + AXIS_LABEL_WIDTH
        chart_right = r.right - 2
        chart_top = r.y + 2
        chart_bottom = r.bottom - (14 if self.show_times else 1)
        if chart_bottom <= chart_top + 18 or chart_right <= chart_left + 18:
            return

        def y_for(value: float, top: int, bottom: int) -> int:
            return y_scale(value, 0.0, scale_max, top, bottom)

        axis_x = r.x + VERTICAL_LABEL_WIDTH

        def draw_guides() -> None:
            for tick in ticks:
                y = y_for(tick, chart_top, chart_bottom)
                if tick > 0:
                    draw_hline(draw, chart_left, chart_right, y, fill=175)
                text = str(tick)
                label_bbox = draw.textbbox((0, 0), text, font=axis_font)
                label_h = label_bbox[3] - label_bbox[1]
                if tick == int(scale_max):
                    label_y = chart_top + 1
                elif tick == 0:
                    label_y = chart_bottom - label_h - 1
                else:
                    label_y = y - label_h // 2
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
            preserve_values=True,
        )
        samples = smooth_series(values, steps_per_segment=16)
        sample_values = tuple(v for _, v in samples)
        draw_shaded_area_curve(
            image,
            points,
            sample_values,
            chart_bottom,
            grey_for_value=uv_fill_grey,
        )
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
            "UV",
            label_font,
            x=r.x,
            center_y=(chart_top + chart_bottom) // 2,
        )
        draw_metric(
            draw,
            f"{uv_level(current)} / {uv_level(rest_max)}",
            metric_font,
            right=chart_right,
            top=chart_top,
        )

        if self.show_times:
            meta_font = self.font(context, 11, bold=False)
            stamp = now.strftime("%H:%M")
            if context.get("weather_stale"):
                updated = f"Last updated {stamp} · cached"
            else:
                updated = f"Last updated {stamp}"
            meta_bbox = draw.textbbox((0, 0), updated, font=meta_font)
            meta_w = meta_bbox[2] - meta_bbox[0]
            meta_h = meta_bbox[3] - meta_bbox[1]
            # Sit in the page bottom margin, below the hour axis labels.
            canvas_bottom = int(context["height"])
            draw.text(
                (
                    chart_right - meta_w - meta_bbox[0],
                    canvas_bottom - meta_h - meta_bbox[1] - 3,
                ),
                updated,
                font=meta_font,
                fill=0,
            )
