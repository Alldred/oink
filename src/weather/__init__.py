"""Weather data helpers for Oink widgets."""

from .client import (
    LOCATION_NAME,
    WeatherData,
    fetch_weather,
    fetch_weather_resilient,
    get_weather,
    load_weather_cache,
    save_weather_cache,
)
from .codes import icon_kind, uv_category, weather_label
from .fixtures import FIXTURE_NAMES, build_fixture
from .whimsy import pick_whimsy_line, sky_bucket

__all__ = [
    "LOCATION_NAME",
    "WeatherData",
    "FIXTURE_NAMES",
    "build_fixture",
    "fetch_weather",
    "fetch_weather_resilient",
    "get_weather",
    "icon_kind",
    "load_weather_cache",
    "pick_whimsy_line",
    "save_weather_cache",
    "sky_bucket",
    "uv_category",
    "weather_label",
]
