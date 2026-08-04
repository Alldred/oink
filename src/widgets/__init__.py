"""Dashboard widgets for Oink.

Each widget renders into an assigned rectangle on the canvas.
Add new widgets by subclassing ``Widget`` and registering them in the layout.
"""

from .base import Widget
from .conditions import ConditionsWidget
from .date import DateWidget
from .header import HeaderWidget
from .message import MessageWidget
from .rain import RainForecastWidget
from .sky import SkyTimelineWidget
from .temperature import TemperatureForecastWidget
from .uv import UVForecastWidget
from .whimsy import WhimsyWidget

__all__ = [
    "Widget",
    "ConditionsWidget",
    "DateWidget",
    "HeaderWidget",
    "MessageWidget",
    "RainForecastWidget",
    "SkyTimelineWidget",
    "TemperatureForecastWidget",
    "UVForecastWidget",
    "WhimsyWidget",
]
