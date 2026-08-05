"""Shared e-ink chart drawing helpers."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

TIME_LABELS = ((0, "00"), (6, "06"), (12, "12"), (18, "18"))

# Layout columns inside each chart widget.
VERTICAL_LABEL_WIDTH = 26
AXIS_LABEL_WIDTH = 36


def draw_hline(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int, *, fill: int = 160) -> None:
    draw.line([(x0, y), (x1, y)], fill=fill, width=1)


def draw_dashed_vline(
    draw: ImageDraw.ImageDraw,
    x: int,
    y0: int,
    y1: int,
    *,
    fill: int = 180,
    dash: int = 3,
    gap: int = 3,
) -> None:
    y = y0
    while y < y1:
        y_end = min(y + dash, y1)
        draw.line([(x, y), (x, y_end)], fill=fill, width=1)
        y += dash + gap


def draw_time_grid(
    draw: ImageDraw.ImageDraw,
    left: int,
    right: int,
    top: int,
    bottom: int,
    *,
    font: ImageFont.ImageFont | None = None,
    show_labels: bool = False,
) -> None:
    """Vertical dashed marks at 00/06/12/18; optional compact hour labels."""
    for hour, label in TIME_LABELS:
        x = left + int(hour / 24 * (right - left))
        draw_dashed_vline(draw, x, top, bottom, fill=190)
        if show_labels and font is not None:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((x - text_w // 2, bottom + 3), label, font=font, fill=90)


def chart_points(
    values: tuple[float, ...],
    left: int,
    right: int,
    top: int,
    bottom: int,
    *,
    y_for_value,
    smooth: bool = False,
    preserve_values: bool = False,
    steps_per_segment: int = 16,
    soften_passes: int = 3,
    anchor_step: int = 2,
    value_floor: float | None = None,
) -> list[tuple[int, int]]:
    """Map hourly values to canvas points; optional Catmull-Rom curve.

    ``preserve_values=True`` splines through every hourly sample (needed for UV
    so peaks still reach their true level). Otherwise the curve is softened.
    ``value_floor`` clamps spline overshoot (e.g. 0 for rainfall).
    """
    width = right - left
    n = len(values)
    if n == 0:
        return []

    def clamp(value: float) -> float:
        v = float(value)
        return v if value_floor is None else max(value_floor, v)

    if n == 1 or not smooth:
        points: list[tuple[int, int]] = []
        for i, value in enumerate(values):
            x = left + int((i / (n - 1)) * width) if n > 1 else left
            points.append((x, y_for_value(clamp(value), top, bottom)))
        return points

    if preserve_values:
        samples = smooth_series(values, steps_per_segment=steps_per_segment)
    else:
        samples = soft_hourly_curve(
            values,
            steps_per_segment=steps_per_segment,
            soften_passes=soften_passes,
            anchor_step=anchor_step,
        )
    points = []
    for index, value in samples:
        x = left + int((index / (n - 1)) * width)
        points.append((x, y_for_value(clamp(value), top, bottom)))
    return points


def soften_series(values: tuple[float, ...], *, passes: int = 2) -> tuple[float, ...]:
    """Light moving-average so hourly noise doesn't make the curve look jagged."""
    if len(values) < 3:
        return values
    current = [float(v) for v in values]
    for _ in range(max(1, passes)):
        nxt = current[:]
        for i in range(1, len(current) - 1):
            nxt[i] = (current[i - 1] + current[i] * 2.0 + current[i + 1]) / 4.0
        current = nxt
    return tuple(current)


def soft_hourly_curve(
    values: tuple[float, ...],
    *,
    steps_per_segment: int = 16,
    soften_passes: int = 3,
    anchor_step: int = 2,
) -> list[tuple[float, float]]:
    """Soften, thin to sparse anchors, then Catmull-Rom for a gentle curve."""
    softened = soften_series(values, passes=soften_passes)
    n = len(softened)
    if n < 3:
        return [(float(i), float(v)) for i, v in enumerate(softened)]

    step = max(1, int(anchor_step))
    # Keep endpoints and every Nth hour so the spline isn't forced through
    # every hourly wiggle.
    anchor_idx = list(range(0, n, step))
    if anchor_idx[-1] != n - 1:
        anchor_idx.append(n - 1)
    anchors = tuple(softened[i] for i in anchor_idx)

    # Spline in anchor-space, then map parameter back onto hour indices.
    spline = smooth_series(anchors, steps_per_segment=steps_per_segment)
    out: list[tuple[float, float]] = []
    for t, value in spline:
        # t is fractional index in anchor array [0 .. len(anchors)-1]
        lo = int(math.floor(t))
        hi = min(lo + 1, len(anchor_idx) - 1)
        frac = t - lo
        hour = anchor_idx[lo] + (anchor_idx[hi] - anchor_idx[lo]) * frac
        out.append((float(hour), float(value)))
    return out


def smooth_series(
    values: tuple[float, ...],
    *,
    steps_per_segment: int = 16,
) -> list[tuple[float, float]]:
    """Catmull-Rom interpolate samples → denser (index, value) pairs."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [(0.0, float(values[0]))]

    padded = [float(values[0]), *[float(v) for v in values], float(values[-1])]
    out: list[tuple[float, float]] = []
    for i in range(n - 1):
        p0, p1, p2, p3 = padded[i], padded[i + 1], padded[i + 2], padded[i + 3]
        for step in range(steps_per_segment):
            t = step / steps_per_segment
            t2 = t * t
            t3 = t2 * t
            value = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            out.append((float(i) + t, value))
    out.append((float(n - 1), float(values[-1])))
    return out


def draw_now_marker(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    *,
    left: int,
    right: int,
    now,
    hours: int = 24,
    radius: int = 4,
) -> None:
    """Small circle on the curve at the current time-of-day."""
    if len(points) < 2 or hours < 2:
        return
    hour_f = float(now.hour) + now.minute / 60.0 + now.second / 3600.0
    hour_f = max(0.0, min(float(hours - 1), hour_f))
    target_x = left + (hour_f / (hours - 1)) * (right - left)

    # Interpolate along the polyline at target_x so the marker sits on the stroke.
    cx = int(round(target_x))
    cy: int | None = None
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 == x1:
            if abs(x0 - target_x) < 0.5:
                cy = y0
                break
            continue
        lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
        if lo_x <= target_x <= hi_x or (x0 <= target_x <= x1) or (x1 <= target_x <= x0):
            t = (target_x - x0) / (x1 - x0)
            if 0.0 <= t <= 1.0 or lo_x <= target_x <= hi_x:
                cy = int(round(y0 + (y1 - y0) * t))
                break
    if cy is None:
        nearest = min(points, key=lambda p: abs(p[0] - target_x))
        cx, cy = nearest

    r = radius
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255, outline=0, width=2)
    draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=0)


def draw_dotted_curve(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    *,
    fill: int = 40,
    width: int = 2,
    dash: int = 5,
    gap: int = 4,
) -> None:
    """Stroke a polyline with dashes only — no area fill."""
    if len(points) < 2:
        return

    drawing = True
    remaining = float(dash)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx = float(x1 - x0)
        dy = float(y1 - y0)
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            continue
        ux, uy = dx / seg_len, dy / seg_len
        traveled = 0.0
        cx, cy = float(x0), float(y0)
        while traveled < seg_len:
            step = min(remaining, seg_len - traveled)
            nx = cx + ux * step
            ny = cy + uy * step
            if drawing:
                draw.line(
                    [(int(round(cx)), int(round(cy))), (int(round(nx)), int(round(ny)))],
                    fill=fill,
                    width=width,
                )
            cx, cy = nx, ny
            traveled += step
            remaining -= step
            if remaining <= 1e-6:
                drawing = not drawing
                remaining = float(dash if drawing else gap)


def draw_area_curve(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    bottom: int,
    *,
    fill: int = 220,
    stroke: int = 0,
    width: int = 2,
    image: Image.Image | None = None,
) -> None:
    """Fill under a curve and stroke it; supersample when ``image`` is given."""
    if len(points) < 2:
        return
    if image is None:
        polygon = [(points[0][0], bottom), *points, (points[-1][0], bottom)]
        draw.polygon(polygon, fill=fill)
        draw.line(points, fill=stroke, width=width)
        return

    xs = [p[0] for p in points]
    left, right = min(xs), max(xs)
    top = min(p[1] for p in points)
    pad = width + 2
    box = (
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad + 1),
        min(image.height, bottom + pad + 1),
    )
    bw = box[2] - box[0]
    bh = box[3] - box[1]
    if bw < 2 or bh < 2:
        return

    scale = 3
    hr = Image.new("L", (bw * scale, bh * scale), 255)
    hr_draw = ImageDraw.Draw(hr)

    def map_pt(pt: tuple[int, int]) -> tuple[int, int]:
        return ((pt[0] - box[0]) * scale, (pt[1] - box[1]) * scale)

    hr_points = [map_pt(p) for p in points]
    hr_bottom = (bottom - box[1]) * scale
    polygon = [(hr_points[0][0], hr_bottom), *hr_points, (hr_points[-1][0], hr_bottom)]
    hr_draw.polygon(polygon, fill=fill)
    hr_draw.line(hr_points, fill=stroke, width=max(1, width * scale))

    soft = hr.resize((bw, bh), Image.Resampling.LANCZOS)
    # Don't paste white background — it would erase grid lines already drawn.
    mask = soft.point(lambda p: 0 if p >= 248 else 255)
    image.paste(soft, (box[0], box[1]), mask)


def draw_shaded_area_curve(
    image: Image.Image,
    points: list[tuple[int, int]],
    values: tuple[float, ...],
    bottom: int,
    *,
    grey_for_value,
    stroke: int = 0,
    width: int = 2,
) -> None:
    """Intensity-shaded fill under a smoothed curve, supersampled for soft edges."""
    if len(points) < 2 or len(values) != len(points):
        return

    xs = [p[0] for p in points]
    left, right = min(xs), max(xs)
    top = min(p[1] for p in points)
    pad = width + 2
    box = (
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad + 1),
        min(image.height, bottom + pad + 1),
    )
    bw = box[2] - box[0]
    bh = box[3] - box[1]
    if bw < 2 or bh < 2:
        return

    scale = 3
    hr = Image.new("L", (bw * scale, bh * scale), 255)
    hr_draw = ImageDraw.Draw(hr)

    def map_pt(pt: tuple[int, int]) -> tuple[int, int]:
        return ((pt[0] - box[0]) * scale, (pt[1] - box[1]) * scale)

    hr_points = [map_pt(p) for p in points]
    hr_bottom = (bottom - box[1]) * scale
    for i in range(len(hr_points) - 1):
        grey = grey_for_value(max(values[i], values[i + 1]))
        x0, y0 = hr_points[i]
        x1, y1 = hr_points[i + 1]
        hr_draw.polygon([(x0, hr_bottom), (x0, y0), (x1, y1), (x1, hr_bottom)], fill=grey)
    hr_draw.line(hr_points, fill=stroke, width=max(1, width * scale))

    soft = hr.resize((bw, bh), Image.Resampling.LANCZOS)
    mask = soft.point(lambda p: 0 if p >= 248 else 255)
    image.paste(soft, (box[0], box[1]), mask)


def draw_vertical_label(
    image: Image.Image,
    text: str,
    font: ImageFont.ImageFont,
    *,
    x: int,
    center_y: int,
    fill: int = 40,
) -> None:
    """Draw ``text`` rotated 90° (reading bottom→top) centred on ``center_y``."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = 2
    tmp = Image.new("L", (tw + pad * 2, th + pad * 2), 255)
    ImageDraw.Draw(tmp).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=fill)
    rotated = tmp.rotate(90, expand=True, fillcolor=255)
    mask = rotated.point(lambda p: 255 if p < 250 else 0)
    py = center_y - rotated.height // 2
    image.paste(rotated, (x, py), mask)


def draw_metric(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    *,
    right: int,
    top: int,
    fill: int = 0,
    backdrop: int = 255,
    outline: int = 175,
) -> None:
    """Right-aligned metric badge hanging from ``top`` (axis guide y).

    The badge's top edge sits on ``top`` so it continues the chart's top
    horizontal guide line.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 5, 3
    box_right = right - 2
    box_left = box_right - tw - 2 * pad_x
    box_top = top
    box_bottom = top + th + 2 * pad_y
    draw.rounded_rectangle(
        [box_left, box_top, box_right, box_bottom],
        radius=5,
        fill=backdrop,
        outline=outline,
        width=1,
    )
    draw.text(
        (box_left + pad_x - bbox[0], box_top + pad_y - bbox[1]),
        text,
        font=font,
        fill=fill,
    )


def nice_axis_ticks(
    scale_min: float,
    scale_max: float,
    *,
    max_ticks: int = 7,
    steps: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0),
) -> tuple[float, ...]:
    """Return nice axis values, expanding the range to land on round steps.

    The first and last values are the snapped scale bounds to use for plotting.
    """
    lo = float(scale_min)
    hi = float(scale_max)
    if hi <= lo:
        return (lo,)

    best: tuple[float, ...] | None = None
    for step in steps:
        snapped_lo = math.floor(lo / step) * step
        snapped_hi = math.ceil(hi / step) * step
        if snapped_hi <= snapped_lo:
            snapped_hi = snapped_lo + step
        count = int(round((snapped_hi - snapped_lo) / step)) + 1
        ticks = tuple(round(snapped_lo + i * step, 6) for i in range(count))
        if 2 <= len(ticks) <= max_ticks:
            return ticks
        if best is None or abs(len(ticks) - max_ticks) < abs(len(best) - max_ticks):
            best = ticks

    if best is None or len(best) < 2:
        mid = (lo + hi) / 2
        return (lo, mid, hi)
    return best


def y_scale(value: float, scale_min: float, scale_max: float, top: int, bottom: int) -> int:
    span = max(scale_max - scale_min, 1e-6)
    ratio = (float(value) - scale_min) / span
    ratio = max(0.0, min(1.0, ratio))
    return int(bottom - ratio * (bottom - top))


def nice_ceiling(value: float, *, minimum: float) -> float:
    """Round up to a readable scale maximum."""
    target = max(float(value), float(minimum))
    if target <= 1:
        return 1.0
    if target <= 2:
        return 2.0
    if target <= 5:
        return math.ceil(target)
    if target <= 10:
        return math.ceil(target * 2) / 2  # 0.5 steps
    return float(math.ceil(target))


def format_mm(value: float) -> str:
    """Format millimetres compactly for the header."""
    if value < 0.05:
        return "0 mm"
    if value < 10:
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text} mm"
    return f"{value:.0f} mm"


def format_temp(value: float) -> str:
    return f"{round(value):.0f}°"


def format_axis_number(value: float) -> str:
    """Compact numeric axis label (temps keep ° elsewhere)."""
    if abs(value - round(value)) < 0.05:
        return f"{round(value):.0f}"
    return f"{value:.1f}".rstrip("0").rstrip(".")


def value_at_time(values: tuple[float, ...], now) -> float:
    """Linearly interpolate the hourly series at the exact clock time."""
    if not values:
        return 0.0
    hour_f = float(now.hour) + now.minute / 60.0 + now.second / 3600.0
    hour_f = max(0.0, min(float(len(values) - 1), hour_f))
    lo = int(math.floor(hour_f))
    hi = min(lo + 1, len(values) - 1)
    frac = hour_f - lo
    return float(values[lo]) + (float(values[hi]) - float(values[lo])) * frac


def current_and_remaining_max(values: tuple[float, ...], now) -> tuple[float, float]:
    """Return (value at now, max from now through end of day).

    Interpolates between hourly samples so the metric matches the now-marker
    on the curve (flooring to the hour made UV show 4 while the marker sat on 3).
    """
    if not values:
        return 0.0, 0.0
    current = value_at_time(values, now)
    hour_f = float(now.hour) + now.minute / 60.0 + now.second / 3600.0
    hour_f = max(0.0, min(float(len(values) - 1), hour_f))
    # Future whole-hour samples strictly after now; past hour buckets are done.
    next_hour = int(math.floor(hour_f)) + 1
    future = values[next_hour:] if next_hour < len(values) else ()
    rest_max = current if not future else max(current, max(future))
    return current, float(rest_max)
