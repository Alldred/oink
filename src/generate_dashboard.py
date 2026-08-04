#!/usr/bin/env python3
"""Generate the Oink Kindle dashboard image.

Usage:
    python src/generate_dashboard.py
    python src/generate_dashboard.py --output public/dashboard.png
    python src/generate_dashboard.py --timezone Europe/London
    python src/generate_dashboard.py --test
    python src/generate_dashboard.py --test stress -o public/dashboard-stress.png
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
from weather import FIXTURE_NAMES, build_fixture


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 600×800 grayscale dashboard PNG for a jailbroken Kindle.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output PNG path (default: public/dashboard.png, or public/dashboard-<fixture>.png with --test)",
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
        nargs="?",
        const="stress",
        default=None,
        metavar="SCENARIO",
        help=(
            "Use synthetic fixture weather instead of Open-Meteo. "
            f"Optional scenario: {', '.join(FIXTURE_NAMES)} (default: stress). "
            "Renders as of 14:00 so current/rest-of-day metrics are meaningful."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


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
    now = None
    if args.test is not None:
        try:
            weather = build_fixture(args.test)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        tz = ZoneInfo(args.timezone)
        # Mid-afternoon so Temp/UV "current / rest of day" maxes are interesting.
        now = datetime.now(tz).replace(hour=14, minute=0, second=0, microsecond=0)

    if args.output is None:
        if args.test is not None:
            args.output = ROOT_DIR / "public" / f"dashboard-{args.test}.png"
        else:
            args.output = ROOT_DIR / "public" / "dashboard.png"

    try:
        widgets = build_default_layout()
        renderer = Renderer(
            widgets,
            fonts_dir=fonts_dir,
            timezone=args.timezone,
        )
        output = renderer.save(args.output, now=now, weather=weather)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"error: failed to generate dashboard: {exc}", file=sys.stderr)
        return 1

    if args.test is not None:
        print(f"Test fixture '{args.test}' → {output}")
    else:
        print(f"Dashboard written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
