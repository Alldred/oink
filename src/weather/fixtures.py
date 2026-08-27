"""Synthetic weather fixtures for dashboard stress testing."""

from __future__ import annotations

from weather.client import HOURS_PER_DAY, LOCATION_NAME, WeatherData

# Named scenarios for ``generate_dashboard.py --test``.
FIXTURE_NAMES = ("stress", "calm", "mixed")


def build_fixture(name: str = "stress") -> WeatherData:
    """Return synthetic ``WeatherData`` for the named scenario."""
    key = (name or "stress").strip().lower()
    if key == "stress":
        weather = stress_weather()
    elif key == "calm":
        weather = calm_weather()
    elif key == "mixed":
        weather = mixed_weather()
    else:
        raise ValueError(
            f"Unknown test fixture '{name}'. Choose one of: {', '.join(FIXTURE_NAMES)}"
        )
    return _require_tomorrow(weather)


def _require_tomorrow(weather: WeatherData) -> WeatherData:
    """Fixtures must ship a full next-day overlay for rain / temp / UV charts."""
    series = (
        ("hourly_precipitation_tomorrow", weather.hourly_precipitation_tomorrow),
        ("hourly_temperature_tomorrow", weather.hourly_temperature_tomorrow),
        ("hourly_uv_index_tomorrow", weather.hourly_uv_index_tomorrow),
        ("hourly_weather_code_tomorrow", weather.hourly_weather_code_tomorrow),
    )
    missing = [name for name, values in series if len(values) != HOURS_PER_DAY]
    if missing:
        raise ValueError(
            f"Fixture '{weather.location}' missing tomorrow series: {', '.join(missing)}"
        )
    return weather


def _codes_from_precip(precip: tuple[float, ...], *, clear: int = 0) -> tuple[int, ...]:
    """Rough WMO codes so overnight whimsy can read tomorrow morning."""
    codes: list[int] = []
    for amount in precip:
        if amount >= 8.0:
            codes.append(65)
        elif amount >= 3.0:
            codes.append(81)
        elif amount >= 1.0:
            codes.append(80)
        elif amount >= 0.2:
            codes.append(61)
        else:
            codes.append(clear)
    return tuple(codes)


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
    # Tomorrow: cooler peak, lower UV — dotted overlay should sit below today.
    uv_tomorrow = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.1, 0.6,
        2.0, 3.5, 5.0, 6.5,
        7.0, 6.5, 5.5, 4.0,
        2.5, 1.0, 0.2, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )
    temps_tomorrow = (
        11.0, 10.5, 10.0, 9.5,
        9.0, 9.5, 11.0, 13.0,
        16.0, 19.0, 22.0, 24.0,
        25.0, 25.5, 25.0, 23.5,
        21.0, 18.0, 15.0, 13.0,
        12.0, 11.5, 11.0, 10.5,
    )
    # Tomorrow: lighter morning showers, dry evening — line sits below today's storm.
    precip_tomorrow = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.2,
        1.5, 4.0, 2.0, 0.5,
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.3, 1.0, 0.4,
        0.0, 0.0, 0.0, 0.0,
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
        hourly_precipitation_tomorrow=precip_tomorrow,
        hourly_uv_index_tomorrow=uv_tomorrow,
        hourly_temperature_tomorrow=temps_tomorrow,
        hourly_weather_code_tomorrow=_codes_from_precip(precip_tomorrow),
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
    # Tomorrow a touch warmer / higher UV so the dotted line peeks above today.
    uv_tomorrow = tuple(
        max(0.0, 3.5 * (1.0 - abs(h - 13) / 7.0)) if 7 <= h <= 19 else 0.0
        for h in range(24)
    )
    temps_tomorrow = tuple(
        15.0 + (5.5 if 11 <= h <= 16 else 0.0) + (h % 3) * 0.15 for h in range(24)
    )
    # Tomorrow: brief light showers so the grey line is visible on a dry today.
    precip_tomorrow = tuple(
        1.8 if h in (14, 15) else (0.6 if h in (13, 16) else 0.0) for h in range(24)
    )
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
        hourly_precipitation_tomorrow=precip_tomorrow,
        hourly_uv_index_tomorrow=uv_tomorrow,
        hourly_temperature_tomorrow=temps_tomorrow,
        hourly_weather_code_tomorrow=_codes_from_precip(precip_tomorrow),
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
    uv_tomorrow = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.2, 0.8,
        1.8, 3.0, 4.0, 4.5,
        4.8, 4.5, 3.8, 2.5,
        1.2, 0.4, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )
    temps_tomorrow = (
        8.0, 7.5, 7.0, 6.5,
        6.0, 6.5, 8.0, 10.0,
        12.0, 14.0, 15.5, 16.5,
        17.0, 17.5, 16.5, 15.0,
        13.0, 11.0, 10.0, 9.0,
        8.5, 8.0, 7.5, 7.0,
    )
    precip_tomorrow = (
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.5, 2.5, 5.0, 3.0,
        1.0, 0.2, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
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
        hourly_precipitation_tomorrow=precip_tomorrow,
        hourly_uv_index_tomorrow=uv_tomorrow,
        hourly_temperature_tomorrow=temps_tomorrow,
        hourly_weather_code_tomorrow=_codes_from_precip(precip_tomorrow),
    )
