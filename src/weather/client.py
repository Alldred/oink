"""Open-Meteo weather fetch for the Oink dashboard."""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
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
FETCH_ATTEMPTS = 2
FETCH_RETRY_DELAY_S = 2.0
HOURS_PER_DAY = 24
# Cap response body so a runaway payload cannot blow memory.
MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class WeatherData:
    """Today's forecast snapshot, plus optional tomorrow hourly overlays."""

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
    # Next-day hourly series for chart overlays (empty when unavailable).
    hourly_precipitation_tomorrow: tuple[float, ...] = ()
    hourly_uv_index_tomorrow: tuple[float, ...] = ()
    hourly_temperature_tomorrow: tuple[float, ...] = ()

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
            "forecast_days": 2,
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
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Open-Meteo HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Open-Meteo network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Open-Meteo request timed out") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Open-Meteo response too large")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RuntimeError("Open-Meteo returned non-UTF-8 body") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Open-Meteo returned invalid JSON") from exc

    return _parse_payload(payload, location=location)


def fetch_weather_resilient(
    *,
    cache_path: Path | None = None,
    timezone: str = "Europe/London",
    location: str = LOCATION_NAME,
    attempts: int = FETCH_ATTEMPTS,
    retry_delay_s: float = FETCH_RETRY_DELAY_S,
) -> tuple[WeatherData, bool]:
    """Fetch weather with retry, falling back to a on-disk cache.

    Returns ``(weather, stale)``. ``stale`` is True when the live fetch failed
    and the cached snapshot was used instead.
    """
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            weather = fetch_weather(timezone=timezone, location=location)
        except Exception as exc:  # noqa: BLE001 - retry then degrade
            last_error = exc
            logger.warning(
                "Open-Meteo fetch attempt %d/%d failed: %s",
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                time.sleep(retry_delay_s)
            continue

        if cache_path is not None:
            try:
                save_weather_cache(cache_path, weather)
            except OSError as exc:
                logger.warning("Could not write weather cache %s: %s", cache_path, exc)
        return weather, False

    if cache_path is not None:
        cached = load_weather_cache(cache_path)
        if cached is not None:
            logger.warning(
                "Using stale weather cache at %s after live fetch failed: %s",
                cache_path,
                last_error,
            )
            return cached, True

    raise RuntimeError(
        f"Open-Meteo unavailable and no weather cache at {cache_path}: {last_error}"
    )


def get_weather(context: dict[str, Any]) -> WeatherData:
    """Return weather from context, fetching once per render if needed."""
    cached = context.get("weather")
    if isinstance(cached, WeatherData):
        return cached
    if isinstance(cached, Exception):
        raise cached

    timezone = str(context.get("timezone") or "Europe/London")
    cache_path = context.get("weather_cache_path")
    path = Path(cache_path) if cache_path else None

    try:
        weather, stale = fetch_weather_resilient(cache_path=path, timezone=timezone)
    except Exception as exc:  # noqa: BLE001 - cache failure so sibling widgets skip refetch
        context["weather"] = exc
        raise

    context["weather"] = weather
    context["weather_stale"] = stale
    return weather


def save_weather_cache(path: Path, weather: WeatherData) -> None:
    """Persist a successful forecast so later failures can degrade gracefully."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(weather)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_weather_cache(path: Path) -> WeatherData | None:
    """Load a previously saved forecast, or None if missing/corrupt."""
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        return WeatherData(
            location=str(payload["location"]),
            weather_code=int(payload["weather_code"]),
            temperature_max=float(payload["temperature_max"]),
            temperature_min=float(payload["temperature_min"]),
            precipitation_sum=float(payload["precipitation_sum"]),
            uv_index_max=float(payload["uv_index_max"]),
            hourly_precipitation=_normalize_hours(
                [_coerce_float(v, default=0.0) for v in payload["hourly_precipitation"]]
            ),
            hourly_uv_index=_normalize_hours(
                [_coerce_float(v, default=0.0) for v in payload["hourly_uv_index"]]
            ),
            hourly_temperature=_normalize_hours(
                [_coerce_float(v, default=0.0) for v in payload["hourly_temperature"]]
            ),
            hourly_weather_code=_normalize_hours_int(
                [_coerce_int(v, default=0) for v in payload["hourly_weather_code"]]
            ),
            hourly_precipitation_tomorrow=_optional_hours(
                payload.get("hourly_precipitation_tomorrow")
            ),
            hourly_uv_index_tomorrow=_optional_hours(
                payload.get("hourly_uv_index_tomorrow")
            ),
            hourly_temperature_tomorrow=_optional_hours(
                payload.get("hourly_temperature_tomorrow")
            ),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable weather cache %s: %s", path, exc)
        return None


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _parse_payload(payload: dict[str, Any], *, location: str) -> WeatherData:
    try:
        daily = payload["daily"]
        hourly = payload["hourly"]
        precip_all = _series_float(hourly["precipitation"])
        uv_all = _series_float(hourly["uv_index"])
        temps_all = _series_float(hourly["temperature_2m"], carry=True)
        codes_all = _series_int(hourly["weather_code"], carry=True)
        return WeatherData(
            location=location,
            weather_code=_coerce_int(daily["weather_code"][0], default=0),
            temperature_max=_coerce_float(daily["temperature_2m_max"][0], default=0.0),
            temperature_min=_coerce_float(daily["temperature_2m_min"][0], default=0.0),
            precipitation_sum=_coerce_float(daily["precipitation_sum"][0], default=0.0),
            uv_index_max=_coerce_float(daily["uv_index_max"][0], default=0.0),
            hourly_precipitation=_hours_for_day(precip_all, 0),
            hourly_uv_index=_hours_for_day(uv_all, 0),
            hourly_temperature=_hours_for_day(temps_all, 0),
            hourly_weather_code=_hours_for_day_int(codes_all, 0),
            hourly_precipitation_tomorrow=_hours_for_day(precip_all, 1),
            hourly_uv_index_tomorrow=_hours_for_day(uv_all, 1),
            hourly_temperature_tomorrow=_hours_for_day(temps_all, 1),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected Open-Meteo payload: {exc}") from exc


def _series_float(values: Any, *, carry: bool = False) -> list[float]:
    if not isinstance(values, list) or not values:
        raise ValueError("hourly series missing or empty")
    out: list[float] = []
    last: float | None = None
    for v in values:
        if v is None and carry and last is not None:
            out.append(last)
            continue
        number = _coerce_float(v, default=0.0 if last is None else last)
        out.append(number)
        last = number
    return out


def _series_int(values: Any, *, carry: bool = False) -> list[int]:
    if not isinstance(values, list) or not values:
        raise ValueError("hourly series missing or empty")
    out: list[int] = []
    last: int | None = None
    for v in values:
        if v is None and carry and last is not None:
            out.append(last)
            continue
        number = _coerce_int(v, default=0 if last is None else last)
        out.append(number)
        last = number
    return out


def _coerce_float(value: Any, *, default: float) -> float:
    if value is None:
        return float(default)
    return float(value)


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None:
        return int(default)
    return int(value)


def _normalize_hours(values: list[float], target: int = HOURS_PER_DAY) -> tuple[float, ...]:
    """Pad or trim to a full local day (handles DST 23/25 hour payloads)."""
    if len(values) >= target:
        return tuple(values[:target])
    pad = values[-1] if values else 0.0
    return tuple(values + [pad] * (target - len(values)))


def _normalize_hours_int(values: list[int], target: int = HOURS_PER_DAY) -> tuple[int, ...]:
    if len(values) >= target:
        return tuple(values[:target])
    pad = values[-1] if values else 0
    return tuple(values + [pad] * (target - len(values)))


def _hours_for_day(values: list[float], day: int) -> tuple[float, ...]:
    """Slice a multi-day hourly series into one local day, or empty if missing."""
    start = day * HOURS_PER_DAY
    chunk = values[start : start + HOURS_PER_DAY]
    if not chunk:
        return ()
    return _normalize_hours(list(chunk))


def _hours_for_day_int(values: list[int], day: int) -> tuple[int, ...]:
    start = day * HOURS_PER_DAY
    chunk = values[start : start + HOURS_PER_DAY]
    if not chunk:
        return ()
    return _normalize_hours_int(list(chunk))


def _optional_hours(raw: Any) -> tuple[float, ...]:
    """Load an optional cached tomorrow series; missing/invalid → empty."""
    if not isinstance(raw, list) or not raw:
        return ()
    return _normalize_hours([_coerce_float(v, default=0.0) for v in raw])
