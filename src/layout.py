"""Dashboard layout definitions for Kindle Basic 7th generation (600×800).

Widgets are independent and each owns a rectangle. To add a future widget
(weather, calendar, RSS, …), create a class under ``widgets/`` and append it
in ``build_default_layout()``.
"""

from __future__ import annotations

from widgets.base import Rect, Widget
from widgets.clock import ClockWidget
from widgets.message import MessageWidget

# Kindle Basic 7th generation (WP63GW) native resolution.
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 800
MARGIN = 32


def build_default_layout() -> list[Widget]:
    """Return the v1 dashboard layout: clock + status message.

    Layout (portrait, top → bottom):

        ┌────────────────────────────┐
        │          margin            │
        │        CLOCK (date/time)   │
        │                            │
        │        MESSAGE             │
        │          margin            │
        └────────────────────────────┘
    """
    content_width = CANVAS_WIDTH - (MARGIN * 2)
    content_top = MARGIN
    content_height = CANVAS_HEIGHT - (MARGIN * 2)

    # Clock takes the upper ~60%; message sits in the lower band.
    clock_height = int(content_height * 0.60)
    message_top = content_top + clock_height
    message_height = content_height - clock_height

    return [
        ClockWidget(Rect(MARGIN, content_top, content_width, clock_height)),
        MessageWidget(Rect(MARGIN, message_top, content_width, message_height)),
    ]
