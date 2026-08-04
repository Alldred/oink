"""Dashboard widgets for Oink.

Each widget renders into an assigned rectangle on the canvas.
Add new widgets by subclassing ``Widget`` and registering them in the layout.
"""

from .base import Widget
from .clock import ClockWidget
from .message import MessageWidget

__all__ = [
    "Widget",
    "ClockWidget",
    "MessageWidget",
]
