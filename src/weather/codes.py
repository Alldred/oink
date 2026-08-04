"""WMO weather interpretation codes → short display labels."""

from __future__ import annotations

# Open-Meteo / WMO WW codes used by the Forecast API.
_WMO_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


def weather_label(code: int) -> str:
    """Return a short English label for a WMO weather code."""
    return _WMO_LABELS.get(int(code), f"Code {code}")


def icon_kind(code: int, *, hour: int | None = None) -> str:
    """Map a WMO code to a drawable icon name."""
    c = int(code)
    night = hour is not None and (hour < 6 or hour >= 21)
    if c == 0:
        return "moon" if night else "sun"
    if c in (1, 2):
        return "partly_night" if night else "partly"
    if c == 3:
        return "cloud"
    if c in (45, 48):
        return "fog"
    if c in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if c in (71, 73, 75, 77, 85, 86):
        return "snow"
    if c in (95, 96, 99):
        return "storm"
    return "cloud"


def uv_category(index: float) -> str:
    """WHO UV Index category label."""
    value = max(0.0, float(index))
    if value < 3:
        return "Low"
    if value < 6:
        return "Moderate"
    if value < 8:
        return "High"
    if value < 11:
        return "Very high"
    return "Extreme"
