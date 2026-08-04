#!/usr/bin/env python3
"""Generate the Oink Kindle dashboard image.

Usage:
    python src/generate_dashboard.py
    python src/generate_dashboard.py --output public/dashboard.png
    python src/generate_dashboard.py --timezone Europe/London
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as ``python src/generate_dashboard.py`` without installing a package.
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from layout import build_default_layout
from renderer import DEFAULT_TIMEZONE, Renderer, configure_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 600×800 grayscale dashboard PNG for a jailbroken Kindle.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=ROOT_DIR / "public" / "dashboard.png",
        help="Output PNG path (default: public/dashboard.png)",
    )
    parser.add_argument(
        "--timezone",
        "-t",
        default=DEFAULT_TIMEZONE,
        help=f"IANA timezone for the displayed clock (default: {DEFAULT_TIMEZONE})",
    )
    parser.add_argument(
        "--fonts-dir",
        type=Path,
        default=ROOT_DIR / "fonts",
        help="Directory containing DejaVuSans.ttf / DejaVuSans-Bold.ttf",
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
    if not (fonts_dir / "DejaVuSans.ttf").is_file():
        print(
            f"error: bundled font not found at {fonts_dir / 'DejaVuSans.ttf'}",
            file=sys.stderr,
        )
        return 1

    try:
        widgets = build_default_layout()
        renderer = Renderer(
            widgets,
            fonts_dir=fonts_dir,
            timezone=args.timezone,
        )
        output = renderer.save(args.output)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"error: failed to generate dashboard: {exc}", file=sys.stderr)
        return 1

    print(f"Dashboard written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
