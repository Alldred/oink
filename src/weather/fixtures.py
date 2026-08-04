"""Synthetic weather fixtures for dashboard stress testing."""

from __future__ import annotations

from weather.client import LOCATION_NAME, WeatherData

# Named scenarios for ``generate_dashboard.py --test``.
FIXTURE_NAMES = ("stress", "calm", "mixed")


def build_fixture(name: str = "stress") -> WeatherData:
    """Return synthetic ``WeatherData`` for the named scenario."""
    key = (name or "stress").strip().lower()
    if key == "stress":
        return stress_weather()
    if key == "calm":
        return calm_weather()
    if key == "mixed":
        return mixed_weather()
    raise ValueError(
        f"Unknown test fixture '{name}'. Choose one of: {', '.join(FIXTURE_NAMES)}"
    )


def stress_weather() -> WeatherData:
    """Edge-case day: UV 11, late heavy rain, wide temp swing, varied sky."""
    # Weather codes: clear night → sun → storm peak → clearing → heavy rain late.
    codes = (
        0, 0, 0, 1,  # 00–03 clear/mainly clear night
        1, 0, 0, 1,  # 04–07
        2, 2, 3, 95,  # 08–11 build to thunderstorm
        96, 95, 80, 3,  # 12–15 storm then showers
        2, 2, 3, 61,  # 16–19
        63, 65, 65, 82,  # 20–23 heavy rain / violent showers at 11pm
    )
    precip = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.2, 0.5, 3.0,
        6.0, 4.0, 1.5, 0.2,
        0.0, 0.0, 0.3, 1.0,
        2.5, 8.0, 12.0, 16.0,  # 23:00 above "High" (15 mm/h)
    )
    # UV climbs to Extreme 11 around midday.
    uv = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.2, 1.0,
        3.0, 5.5, 8.0, 10.0,
        11.0, 10.5, 9.0, 7.0,
        4.5, 2.0, 0.5, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )
    # Hot afternoon, cool night — stresses temp scale.
    temps = (
        12.0, 11.5, 11.0, 10.5,
        10.0, 10.5, 12.0, 15.0,
        19.0, 23.0, 27.0, 30.0,
        32.0, 33.0, 32.5, 31.0,
        28.0, 24.0, 20.0, 17.0,
        15.0, 14.0, 13.0, 12.5,
    )
    return WeatherData(
        location=LOCATION_NAME,
        weather_code=82,
        temperature_max=max(temps),
        temperature_min=min(temps),
        precipitation_sum=round(sum(precip), 1),
        uv_index_max=max(uv),
        hourly_precipitation=precip,
        hourly_uv_index=uv,
        hourly_temperature=temps,
        hourly_weather_code=codes,
    )


def calm_weather() -> WeatherData:
    """Quiet clear day — low UV, no rain, gentle temps."""
    codes = tuple(0 if h < 6 or h >= 21 else (1 if h in (7, 18) else 0) for h in range(24))
    precip = tuple(0.0 for _ in range(24))
    uv = tuple(
        max(0.0, 2.5 * (1.0 - abs(h - 13) / 7.0)) if 7 <= h <= 19 else 0.0
        for h in range(24)
    )
    temps = tuple(14.0 + (4.0 if 11 <= h <= 16 else 0.0) + (h % 3) * 0.2 for h in range(24))
    return WeatherData(
        location=LOCATION_NAME,
        weather_code=0,
        temperature_max=max(temps),
        temperature_min=min(temps),
        precipitation_sum=0.0,
        uv_index_max=max(uv),
        hourly_precipitation=precip,
        hourly_uv_index=uv,
        hourly_temperature=temps,
        hourly_weather_code=codes,
    )


def mixed_weather() -> WeatherData:
    """Partly cloudy with light showers and moderate UV."""
    codes = (
        3, 3, 2, 2,
        2, 1, 1, 2,
        2, 80, 3, 2,
        2, 1, 80, 81,
        3, 2, 2, 3,
        3, 3, 45, 45,
    )
    precip = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.1, 1.2, 0.4, 0.0,
        0.0, 0.0, 0.8, 2.0,
        0.3, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )
    uv = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.3, 1.2,
        2.5, 4.0, 5.0, 5.5,
        6.0, 5.8, 5.0, 3.5,
        2.0, 0.8, 0.2, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )
    temps = (
        9.0, 8.5, 8.0, 7.5,
        7.0, 7.5, 9.0, 11.0,
        13.0, 15.0, 16.5, 17.0,
        18.0, 18.5, 17.5, 16.0,
        14.0, 12.0, 11.0, 10.0,
        9.5, 9.0, 8.5, 8.0,
    )
    return WeatherData(
        location=LOCATION_NAME,
        weather_code=81,
        temperature_max=max(temps),
        temperature_min=min(temps),
        precipitation_sum=round(sum(precip), 1),
        uv_index_max=max(uv),
        hourly_precipitation=precip,
        hourly_uv_index=uv,
        hourly_temperature=temps,
        hourly_weather_code=codes,
    )
