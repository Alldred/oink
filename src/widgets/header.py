"""Date header with a daily animal doodle on the left."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .base import Rect, Widget

# Slot on the left of the header band; animal is centred inside it.
# Wider than tall so landscape doodles (lion, fox, …) don't shrink to fit a square.
ANIMAL_SLOT_PAD = 2
ANIMAL_SLOT_WIDTH_RATIO = 1.45
# After cropping empty margins, fill this fraction of the slot.
ANIMAL_FILL = 0.96


class HeaderWidget(Widget):
    """Daily animal (left) + centred date."""

    name = "header"

    def __init__(self, rect: Rect, *, date_format: str = "%A %-d %B") -> None:
        super().__init__(rect)
        self.date_format = date_format

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, context: dict[str, Any]) -> None:
        now = self.now(context)
        r = self.rect

        slot_h = max(16, r.height - ANIMAL_SLOT_PAD * 2)
        slot_w = max(slot_h, int(round(slot_h * ANIMAL_SLOT_WIDTH_RATIO)))
        self._draw_daily_animal(
            image,
            context,
            slot_x=r.x,
            slot_y=r.y + (r.height - slot_h) // 2,
            slot_w=slot_w,
            slot_h=slot_h,
        )

        date_font = self.font(context, 24, bold=False)
        date_text = self._format(now, self.date_format, fallback="%A %d %B")
        bbox = draw.textbbox((0, 0), date_text, font=date_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = r.x + (r.width - text_w) // 2 - bbox[0]
        y = r.y + (r.height - text_h) // 2 - bbox[1]
        draw.text((x, y), date_text, font=date_font, fill=0)

    def _draw_daily_animal(
        self,
        image: Image.Image,
        context: dict[str, Any],
        *,
        slot_x: int,
        slot_y: int,
        slot_w: int,
        slot_h: int,
    ) -> None:
        animals_dir = context.get("animals_dir")
        if animals_dir is None:
            assets_dir = context.get("assets_dir")
            animals_dir = Path(assets_dir) / "animals" if assets_dir else None
        if animals_dir is None:
            return

        path = _pick_animal(
            Path(animals_dir),
            day=self.now(context).date(),
            randomize=bool(context.get("random_animal")),
        )
        if path is None:
            return

        try:
            rgba = Image.open(path).convert("RGBA")
        except OSError:
            return

        # Drop transparent padding so the doodle fills the slot.
        alpha = rgba.getchannel("A")
        bbox = alpha.point(lambda a: 255 if a > 16 else 0).getbbox()
        if bbox is None:
            return
        rgba = rgba.crop(bbox)

        target_w = max(1, int(slot_w * ANIMAL_FILL))
        target_h = max(1, int(slot_h * ANIMAL_FILL))
        scale = min(target_w / rgba.width, target_h / rgba.height)
        tw = max(1, round(rgba.width * scale))
        th = max(1, round(rgba.height * scale))
        rgba = rgba.resize((tw, th), Image.Resampling.LANCZOS)

        # Line art → pure black ink on the grayscale canvas via the alpha mask.
        ink = Image.new("L", rgba.size, 0)
        alpha = rgba.getchannel("A")
        px = slot_x + (slot_w - tw) // 2
        py = slot_y + (slot_h - th) // 2
        image.paste(ink, (px, py), mask=alpha)

    @staticmethod
    def _format(now, fmt: str, *, fallback: str) -> str:
        try:
            return now.strftime(fmt)
        except ValueError:
            return now.strftime(fallback)


def _pick_animal(animals_dir: Path, *, day, randomize: bool = False) -> Path | None:
    """Pick from ``assets/animals/*.png``.

    Normal builds seed by ``day`` so the animal is stable until midnight.
    Test fixtures set ``random_animal`` so each run can show a different one.
    """
    if not animals_dir.is_dir():
        return None
    paths = sorted(p for p in animals_dir.glob("*.png") if p.is_file())
    if not paths:
        return None
    if randomize:
        return random.choice(paths)
    return random.Random(day.isoformat()).choice(paths)
