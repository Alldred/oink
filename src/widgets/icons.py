"""Weather icons for the Day timeline.

Three styles (set ``ICON_STYLE``):

- ``weathericons`` — Erik Flowers' Weather Icons font (SIL OFL 1.1)
- ``solid`` — filled geometric shapes drawn with Pillow
- ``outline`` — original line doodles drawn with Pillow
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Default: polished icon font. Switch to "solid" or "outline" to compare.
ICON_STYLE = "weathericons"

# Private-use glyphs from weathericons-regular-webfont.ttf
_WI_GLYPHS = {
    "sun": "\uf00d",           # wi-day-sunny
    "moon": "\uf02e",          # wi-night-clear
    "cloud": "\uf013",         # wi-cloudy
    "partly": "\uf002",        # wi-day-cloudy
    "partly_night": "\uf031",  # wi-night-alt-cloudy
    "rain": "\uf019",          # wi-rain
    "snow": "\uf01b",          # wi-snow
    "fog": "\uf014",           # wi-fog
    "storm": "\uf01e",         # wi-thunderstorm
}

# Bare cloudy/moon fill the box more than composite glyphs (partly, rain…),
# so the cloud *shape* looks bigger there. Nudge those down so cloud weight
# reads closer across kinds at the same ``size``.
_WI_OPTICAL_SCALE = {
    "sun": 1.0,
    "moon": 0.90,
    "cloud": 0.88,
    "partly": 1.0,
    "partly_night": 1.0,
    "rain": 0.96,
    "snow": 0.96,
    "fog": 0.90,
    "storm": 0.94,
}


_WI_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def draw_weather_icon(
    draw: ImageDraw.ImageDraw,
    kind: str,
    *,
    cx: int,
    cy: int,
    size: int,
    fill: int = 0,
    style: str | None = None,
    fonts_dir: Path | None = None,
    image: Image.Image | None = None,
) -> None:
    """Draw a compact icon centred on ``(cx, cy)``."""
    chosen = style or ICON_STYLE
    s = max(10, int(size))
    if chosen == "weathericons" and fonts_dir is not None and image is not None:
        if _draw_font_icon(image, kind, cx=cx, cy=cy, size=s, fill=fill, fonts_dir=fonts_dir):
            return
        # Fall through to solid if the font is missing.
        chosen = "solid"

    if chosen == "solid":
        _draw_solid(draw, kind, cx, cy, s, fill)
    else:
        _draw_outline(draw, kind, cx, cy, s, fill)


def _wi_font(fonts_dir: Path, size: int) -> ImageFont.FreeTypeFont | None:
    path = fonts_dir / "weathericons-regular-webfont.ttf"
    key = (str(path), size)
    cached = _WI_FONT_CACHE.get(key)
    if cached is not None:
        return cached
    if not path.is_file():
        return None
    try:
        font = ImageFont.truetype(str(path), size=size)
    except OSError:
        return None
    _WI_FONT_CACHE[key] = font
    return font


def _draw_font_icon(
    image: Image.Image,
    kind: str,
    *,
    cx: int,
    cy: int,
    size: int,
    fill: int,
    fonts_dir: Path,
) -> bool:
    """Render a Weather Icons glyph fitted into a ``size``×``size`` box.

    Glyphs have uneven ink bounds (moon tiny, cloudy wide). Matching the
    longest edge keeps every kind in the same box. Bare cloudy/moon also
    get a slight optical shrink so their cloud mass doesn't dwarf the
    smaller cloud inside composite glyphs like partly-cloudy.
    """
    optical = _WI_OPTICAL_SCALE.get(kind, 1.0)
    target = max(12, int(round(size * optical)))
    glyph = _WI_GLYPHS.get(kind, _WI_GLYPHS["cloud"])

    probe_px = 64
    font_probe = _wi_font(fonts_dir, probe_px)
    if font_probe is None:
        return False
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    bbox = probe.textbbox((0, 0), glyph, font=font_probe)
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])
    font_size = max(12, int(round(probe_px * target / max(tw, th))))
    font = _wi_font(fonts_dir, font_size)
    if font is None:
        return False

    # Render, crop to ink, and centre by ink *centroid* (not bbox mid).
    # Partly/cloud glyphs are bottom-heavy; bbox-centring makes an enlarged
    # active icon look top-aligned with the cloud mass hanging low.
    bbox = probe.textbbox((0, 0), glyph, font=font)
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])
    pad = 2
    tmp = Image.new("L", (tw + pad * 2, th + pad * 2), 255)
    ImageDraw.Draw(tmp).text((pad - bbox[0], pad - bbox[1]), glyph, font=font, fill=fill)
    ink = tmp.point(lambda p: 0 if p > 250 else 255)
    ink_box = ink.getbbox()
    if ink_box is None:
        return False
    tmp = tmp.crop(ink_box)
    mask = tmp.point(lambda p: 255 if p < 250 else 0)

    # Centroid of dark pixels → visual mass sits on (cx, cy).
    pixels = tmp.load()
    w, h = tmp.size
    mass = 0
    mx = 0.0
    my = 0.0
    for yy in range(h):
        for xx in range(w):
            # Darker = more mass (tmp is grayscale ink on white).
            weight = 255 - pixels[xx, yy]
            if weight < 8:
                continue
            mass += weight
            mx += xx * weight
            my += yy * weight
    if mass <= 0:
        return False
    x = int(round(cx - mx / mass))
    y = int(round(cy - my / mass))
    image.paste(tmp, (x, y), mask)
    return True


# --- Solid geometric style -------------------------------------------------


def _draw_solid(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, s: int, fill: int) -> None:
    if kind == "sun":
        _solid_sun(draw, cx, cy, s, fill)
    elif kind == "moon":
        _solid_moon(draw, cx, cy, s, fill)
    elif kind == "cloud":
        _solid_cloud(draw, cx, cy + 1, s, fill)
    elif kind == "partly":
        _solid_sun(draw, cx - s // 5, cy - s // 5, max(10, s * 2 // 3), fill)
        _solid_cloud(draw, cx + s // 10, cy + s // 8, max(10, s * 3 // 4), fill)
    elif kind == "partly_night":
        _solid_moon(draw, cx - s // 5, cy - s // 6, max(10, s * 2 // 3), fill)
        _solid_cloud(draw, cx + s // 10, cy + s // 8, max(10, s * 3 // 4), fill)
    elif kind == "rain":
        _solid_cloud(draw, cx, cy - s // 6, s, fill)
        for dx in (-s // 4, 0, s // 4):
            x = cx + dx
            draw.line([(x, cy + s // 8), (x - 1, cy + s // 3)], fill=fill, width=max(2, s // 10))
    elif kind == "snow":
        _solid_cloud(draw, cx, cy - s // 6, s, fill)
        for dx in (-s // 4, 0, s // 4):
            _plus(draw, cx + dx, cy + s // 4, max(2, s // 8), fill)
    elif kind == "fog":
        w = max(8, s * 3 // 4)
        for i, dy in enumerate((-s // 4, 0, s // 4)):
            inset = (i % 2) * (s // 7)
            draw.line(
                [(cx - w // 2 + inset, cy + dy), (cx + w // 2 - inset, cy + dy)],
                fill=fill,
                width=max(2, s // 9),
            )
    elif kind == "storm":
        _solid_cloud(draw, cx, cy - s // 6, s, fill)
        bolt = [
            (cx + 1, cy + s // 10),
            (cx - s // 7, cy + s // 4),
            (cx + s // 12, cy + s // 4),
            (cx - s // 8, cy + s // 2),
        ]
        draw.line(bolt, fill=fill, width=max(2, s // 9))
    else:
        _solid_cloud(draw, cx, cy, s, fill)


def _solid_sun(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    r = max(3, s // 4)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    ray = max(r + 3, s // 2)
    w = max(2, s // 12)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw.line(
            [(cx + dx * (r + 2), cy + dy * (r + 2)), (cx + dx * ray, cy + dy * ray)],
            fill=fill,
            width=w,
        )


def _solid_moon(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    r = max(4, s // 3)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    cut = max(3, r * 3 // 4)
    draw.ellipse([cx - r + cut // 2, cy - cut, cx + r + cut // 2, cy + cut], fill=255)


def _solid_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    w = max(8, s * 3 // 4)
    h = max(4, s // 3)
    left = cx - w // 2
    top = cy - h // 2
    draw.ellipse([left, top, left + w // 2 + 3, top + h + 2], fill=fill)
    draw.ellipse([cx - w // 5, top - h // 2 - 1, cx + w // 3 + 2, top + h], fill=fill)
    draw.ellipse([cx - 2, top, left + w, top + h + 2], fill=fill)
    draw.rectangle([left + 2, cy, left + w - 2, top + h + 1], fill=fill)


def _plus(draw: ImageDraw.ImageDraw, cx: int, cy: int, arm: int, fill: int) -> None:
    draw.line([(cx - arm, cy), (cx + arm, cy)], fill=fill, width=max(1, arm // 2))
    draw.line([(cx, cy - arm), (cx, cy + arm)], fill=fill, width=max(1, arm // 2))


# --- Outline doodle style (original) ---------------------------------------


def _draw_outline(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, s: int, fill: int) -> None:
    if kind == "sun":
        _outline_sun(draw, cx, cy, s, fill)
    elif kind == "moon":
        _outline_moon(draw, cx, cy, s, fill)
    elif kind == "cloud":
        _outline_cloud(draw, cx, cy, s, fill)
    elif kind == "partly":
        _outline_sun(draw, cx - s // 5, cy - s // 5, max(10, s * 2 // 3), fill)
        _outline_cloud(draw, cx + s // 8, cy + s // 8, max(10, s * 3 // 4), fill)
    elif kind == "partly_night":
        _outline_moon(draw, cx - s // 5, cy - s // 6, max(10, s * 2 // 3), fill)
        _outline_cloud(draw, cx + s // 8, cy + s // 8, max(10, s * 3 // 4), fill)
    elif kind == "rain":
        _outline_cloud(draw, cx, cy - s // 6, s, fill)
        y0 = cy + s // 6
        for dx in (-s // 4, 0, s // 4):
            x = cx + dx
            draw.line([(x, y0), (x - 1, y0 + s // 4)], fill=fill, width=max(1, s // 14))
    elif kind == "snow":
        _outline_cloud(draw, cx, cy - s // 6, s, fill)
        y = cy + s // 5
        for dx in (-s // 4, 0, s // 4):
            x = cx + dx
            draw.point([(x, y), (x, y + 2), (x - 1, y + 1), (x + 1, y + 1)], fill=fill)
    elif kind == "fog":
        w = max(6, s * 2 // 3)
        for i, dy in enumerate((-s // 5, 0, s // 5)):
            inset = (i % 2) * (s // 8)
            draw.line(
                [(cx - w // 2 + inset, cy + dy), (cx + w // 2 - inset, cy + dy)],
                fill=fill,
                width=max(1, s // 12),
            )
    elif kind == "storm":
        _outline_cloud(draw, cx, cy - s // 6, s, fill)
        bolt = [
            (cx, cy + s // 8),
            (cx - s // 8, cy + s // 5),
            (cx + s // 16, cy + s // 5),
            (cx - s // 10, cy + s // 2),
        ]
        draw.line(bolt, fill=fill, width=max(1, s // 12))
    else:
        _outline_cloud(draw, cx, cy, s, fill)


def _outline_sun(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    r = max(2, s // 5)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=max(1, s // 12))
    ray = max(2, s // 3)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw.line(
            [(cx + dx * (r + 1), cy + dy * (r + 1)), (cx + dx * ray, cy + dy * ray)],
            fill=fill,
            width=max(1, s // 14),
        )


def _outline_moon(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    r = max(3, s // 3)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=max(1, s // 12))
    inset = max(2, r // 2)
    draw.ellipse(
        [cx - r + inset, cy - r, cx + r + inset, cy + r],
        outline=255,
        fill=255,
        width=max(1, s // 10),
    )


def _outline_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill: int) -> None:
    w = max(6, s * 2 // 3)
    h = max(3, s // 3)
    left = cx - w // 2
    top = cy - h // 2
    draw.ellipse([left, top, left + w // 2 + 2, top + h + 2], outline=fill, width=1)
    draw.ellipse([cx - w // 6, top - h // 2, cx + w // 2, top + h], outline=fill, width=1)
    draw.ellipse([cx - 2, top, left + w, top + h + 2], outline=fill, width=1)
    draw.arc([left, top + 1, left + w, top + h + 3], 0, 180, fill=fill, width=1)
