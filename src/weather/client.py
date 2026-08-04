"""Open-Meteo weather fetch for the Oink dashboard."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    import certifi
except ImportError:  # pragma: no cover - optional until deps installed
    certifi = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Thornbury, South Gloucestershire (near Bristol).
THORNBURY_LAT = 51.6094
THORNBURY_LON = -2.5257
LOCATION_NAME = "Thornbury"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_S = 20


@dataclass(frozen=True)
class WeatherData:
    """One local-calendar-day forecast snapshot."""

    location: str
    weather_code: int
    temperature_max: float
    temperature_min: float
    precipitation_sum: float
    uv_index_max: float
    hourly_precipitation: tuple[float, ...]
    hourly_uv_index: tuple[float, ...]
    hourly_temperature: tuple[float, ...]
    hourly_weather_code: tuple[int, ...]

    @property
    def hours(self) -> int:
        return len(self.hourly_precipitation)


def fetch_weather(
    *,
    latitude: float = THORNBURY_LAT,
    longitude: float = THORNBURY_LON,
    timezone: str = "Europe/London",
    location: str = LOCATION_NAME,
) -> WeatherData:
    """Fetch today's daily + hourly forecast from Open-Meteo."""
    params = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "timezone": timezone,
            "forecast_days": 1,
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "uv_index_max",
                ]
            ),
            "hourly": "precipitation,uv_index,temperature_2m,weather_code",
        }
    )
    url = f"{FORECAST_URL}?{params}"
    logger.info("Fetching weather for %s from Open-Meteo", location)
    request = urllib.request.Request(url, headers={"User-Agent": "oink-dashboard/1.0"})
    context = _ssl_context()

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Open-Meteo HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Open-Meteo network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Open-Meteo request timed out") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Open-Meteo returned invalid JSON") from exc

    return _parse_payload(payload, location=location)


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def get_weather(context: dict[str, Any]) -> WeatherData:
    """Return weather from context, fetching once per render if needed."""
    cached = context.get("weather")
    if isinstance(cached, WeatherData):
        return cached
    if isinstance(cached, Exception):
        raise cached

    timezone = str(context.get("timezone") or "Europe/London")
    try:
        weather = fetch_weather(timezone=timezone)
    except Exception as exc:  # noqa: BLE001 - cache failure so sibling widgets skip refetch
        context["weather"] = exc
        raise

    context["weather"] = weather
    return weather


def _parse_payload(payload: dict[str, Any], *, location: str) -> WeatherData:
    try:
        daily = payload["daily"]
        hourly = payload["hourly"]
        precip = tuple(float(v) for v in hourly["precipitation"])
        uv = tuple(float(v) for v in hourly["uv_index"])
        temps = tuple(float(v) for v in hourly["temperature_2m"])
        codes = tuple(int(v) for v in hourly["weather_code"])
        if len(precip) != 24 or len(uv) != 24 or len(temps) != 24 or len(codes) != 24:
            raise ValueError(
                "expected 24 hourly samples, got "
                f"precip={len(precip)} uv={len(uv)} temp={len(temps)} code={len(codes)}"
            )
        return WeatherData(
            location=location,
            weather_code=int(daily["weather_code"][0]),
            temperature_max=float(daily["temperature_2m_max"][0]),
            temperature_min=float(daily["temperature_2m_min"][0]),
            precipitation_sum=float(daily["precipitation_sum"][0]),
            uv_index_max=float(daily["uv_index_max"][0]),
            hourly_precipitation=precip,
            hourly_uv_index=uv,
            hourly_temperature=temps,
            hourly_weather_code=codes,
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected Open-Meteo payload: {exc}") from exc
