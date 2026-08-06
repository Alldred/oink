#!/usr/bin/env python3
"""Generate the Oink Kindle dashboard image.

Usage:
    python src/generate_dashboard.py
    python src/generate_dashboard.py --output public/dashboard.png
    python src/generate_dashboard.py --timezone Europe/London
    python src/generate_dashboard.py --test
    python src/generate_dashboard.py --test stress -o public/dashboard-stress.png
    python src/generate_dashboard.py --tests detail
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Allow running as ``python src/generate_dashboard.py`` without installing a package.
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from layout import build_default_layout
from renderer import DEFAULT_TIMEZONE, Renderer, configure_logging
from weather import FIXTURE_NAMES, build_fixture, fetch_weather_resilient

DEFAULT_WEATHER_CACHE = ROOT_DIR / "public" / ".weather-cache.json"
DETAIL_FIXTURE = "stress"
DETAIL_MINUTES = (0, 15, 30, 45)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 600×800 grayscale dashboard PNG for a jailbroken Kindle.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=(
            "Output PNG path (default: public/dashboard.png, or "
            "public/dashboard-<fixture>.png with --test). For --test detail, a "
            "directory (default: public/dashboard-detail/)."
        ),
    )
    parser.add_argument(
        "--timezone",
        "-t",
        default=DEFAULT_TIMEZONE,
        help=f"IANA timezone for the displayed date (default: {DEFAULT_TIMEZONE})",
    )
    parser.add_argument(
        "--fonts-dir",
        type=Path,
        default=ROOT_DIR / "fonts",
        help="Directory containing Nunito-Regular.ttf / Nunito-Bold.ttf",
    )
    parser.add_argument(
        "--test",
        "--tests",
        nargs="?",
        const="stress",
        default=None,
        metavar="SCENARIO",
        help=(
            "Use synthetic fixture weather instead of Open-Meteo. "
            f"Optional scenario: {', '.join(FIXTURE_NAMES)}, detail (default: stress). "
            "Single fixtures render as of 14:00. "
            "``detail`` writes stress-fixture frames every 15 minutes from 00:00–23:45."
        ),
    )
    parser.add_argument(
        "--weather-cache",
        type=Path,
        default=DEFAULT_WEATHER_CACHE,
        help="JSON cache for last-good Open-Meteo data (used when live fetch fails)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def _quarter_hours() -> list[tuple[int, int]]:
    """00:00, 00:15, …, 23:45."""
    return [(hour, minute) for hour in range(24) for minute in DETAIL_MINUTES]


def run_detail_suite(
    *,
    renderer: Renderer,
    weather,
    timezone: str,
    out_dir: Path,
    weather_cache_path: Path,
) -> Path:
    """Render the stress fixture at every quarter-hour; return the output directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tz = ZoneInfo(timezone)
    base = datetime.now(tz).replace(second=0, microsecond=0)
    frames = _quarter_hours()
    for i, (hour, minute) in enumerate(frames, start=1):
        now = base.replace(hour=hour, minute=minute)
        stamp = f"{hour:02d}{minute:02d}"
        path = out_dir / f"dashboard-{stamp}.png"
        renderer.save(
            path,
            now=now,
            weather=weather,
            weather_stale=False,
            weather_cache_path=weather_cache_path,
            # Keep the animal stable across the day so frames only show clock drift.
            random_animal=False,
        )
        print(f"[{i}/{len(frames)}] {stamp} → {path}")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose)

    fonts_dir = args.fonts_dir.resolve()
    if not (fonts_dir / "Nunito-Regular.ttf").is_file():
        print(
            f"error: bundled font not found at {fonts_dir / 'Nunito-Regular.ttf'}",
            file=sys.stderr,
        )
        return 1

    weather = None
    weather_stale = False
    now = None
    detail = args.test is not None and args.test.strip().lower() == "detail"

    if args.test is not None:
        fixture_name = DETAIL_FIXTURE if detail else args.test
        try:
            weather = build_fixture(fixture_name)
        except ValueError as exc:
            if detail:
                print(f"error: {exc}", file=sys.stderr)
            else:
                print(
                    f"error: {exc}. Or use 'detail' for a 15-minute frame sweep.",
                    file=sys.stderr,
                )
            return 1
        tz = ZoneInfo(args.timezone)
        # Mid-afternoon so Temp/UV "current / rest of day" maxes are interesting.
        now = datetime.now(tz).replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        # Resolve weather up front so a total outage fails the run (CI keeps the
        # previous Pages deploy) instead of publishing five error boxes.
        try:
            weather, weather_stale = fetch_weather_resilient(
                cache_path=args.weather_cache.resolve(),
                timezone=args.timezone,
            )
        except Exception as exc:  # noqa: BLE001 - surface as CLI failure
            print(f"error: weather unavailable: {exc}", file=sys.stderr)
            return 1

    if args.output is None:
        if detail:
            args.output = ROOT_DIR / "public" / "dashboard-detail"
        elif args.test is not None:
            args.output = ROOT_DIR / "public" / f"dashboard-{args.test}.png"
        else:
            args.output = ROOT_DIR / "public" / "dashboard.png"

    try:
        widgets = build_default_layout()
        renderer = Renderer(
            widgets,
            fonts_dir=fonts_dir,
            assets_dir=ROOT_DIR / "assets",
            timezone=args.timezone,
        )
        if detail:
            output = run_detail_suite(
                renderer=renderer,
                weather=weather,
                timezone=args.timezone,
                out_dir=args.output,
                weather_cache_path=args.weather_cache.resolve(),
            )
        else:
            output = renderer.save(
                args.output,
                now=now,
                weather=weather,
                weather_stale=weather_stale,
                weather_cache_path=args.weather_cache.resolve(),
                random_animal=args.test is not None,
            )
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"error: failed to generate dashboard: {exc}", file=sys.stderr)
        return 1

    if detail:
        print(
            f"Detail suite ({DETAIL_FIXTURE} fixture, "
            f"{len(_quarter_hours())} frames) → {output}"
        )
    elif args.test is not None:
        print(f"Test fixture '{args.test}' → {output}")
    elif weather_stale:
        print(f"Dashboard written to {output} (stale weather cache)")
    else:
        print(f"Dashboard written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
