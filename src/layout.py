"""Dashboard layout definitions for Kindle Basic 7th generation (600×800).

Widgets are independent and each owns a rectangle. To add a future widget
(weather, calendar, RSS, …), create a class under ``widgets/`` and append it
in ``build_default_layout()``.
"""

from __future__ import annotations

from widgets.base import Rect, Widget
from widgets.header import HeaderWidget
from widgets.rain import RainForecastWidget
from widgets.sky import SkyTimelineWidget
from widgets.temperature import TemperatureForecastWidget
from widgets.uv import UVForecastWidget
from widgets.whimsy import WhimsyWidget

# Kindle Basic 7th generation (WP63GW) native resolution.
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 800
MARGIN = 14


def build_default_layout() -> list[Widget]:
    """Return the weather dashboard layout.

    Layout (portrait, top → bottom):

        ┌────────────────────────────┐
        │           DATE             │
        │         WHIMSY             │
        │           DAY              │
        │          RAIN              │
        │       TEMPERATURE          │
        │           UV               │
        └────────────────────────────┘
    """
    content_width = CANVAS_WIDTH - (MARGIN * 2)
    content_top = MARGIN

    header_height = 28
    gap = 6
    whimsy_height = 40
    sky_height = 52

    after_header = content_top + header_height
    whimsy_top = after_header + 2
    sky_top = whimsy_top + whimsy_height + gap
    after_day = sky_top + sky_height + gap

    remaining = CANVAS_HEIGHT - MARGIN - after_day
    charts_height = remaining - (gap * 2)

    rain_height = int(charts_height * 0.22)
    lower = charts_height - rain_height
    temp_height = lower // 2
    uv_height = lower - temp_height

    rain_top = after_day
    temp_top = rain_top + rain_height + gap
    uv_top = temp_top + temp_height + gap

    return [
        HeaderWidget(Rect(MARGIN, content_top, content_width, header_height)),
        WhimsyWidget(Rect(MARGIN, whimsy_top, content_width, whimsy_height)),
        SkyTimelineWidget(Rect(MARGIN, sky_top, content_width, sky_height), show_times=False),
        RainForecastWidget(Rect(MARGIN, rain_top, content_width, rain_height), show_times=False),
        TemperatureForecastWidget(Rect(MARGIN, temp_top, content_width, temp_height), show_times=False),
        UVForecastWidget(Rect(MARGIN, uv_top, content_width, uv_height), show_times=True),
    ]
