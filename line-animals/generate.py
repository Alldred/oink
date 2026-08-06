#!/usr/bin/env python3
"""Generate simple black line-drawing animals for the Oink dashboard header.

Local mflux (FLUX.2 Klein on Apple Silicon). Outputs 128×128 RGBA PNGs:
pure black strokes on transparent — ready for e-ink. Vision QA via Ollama
checks each image against the animal look (on by default).

    cd line-animals
    ollama serve   # if needed
    uv sync --extra local
    uv run generate.py --list
    uv run generate.py --interactive
    uv run generate.py --only duck fox --interactive
    uv run generate.py --all --overwrite
    uv run generate.py --audit
    uv run generate.py --all --no-verify   # geometry only

Accepted art lands in ``../assets/animals/<id>.png``.
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from backends import (
    ImageBackend,
    begin_local_session,
    create_backend,
    default_steps_for,
    end_local_session,
    normalize_model_name,
    pil_to_png_bytes,
)
from vision import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_VISION_MODEL,
    ensure_vision_model,
    verify_animal,
)

SCRIPT_DIR = Path(__file__).resolve().parent
OINK_ROOT = SCRIPT_DIR.parent
DEFAULT_OUT = OINK_ROOT / "assets" / "animals"
CANDIDATES_DIR = SCRIPT_DIR / "candidates"

# Generate larger, pack down — cleaner strokes at 128.
SOURCE_SIZE = "256x256"
FINAL_SIZE = 128
# Leave ~12–16 px clear margin inside the square (spec for header icons).
SUBJECT_FILL = 0.78
MAX_RETRIES = 3

# Ink post-process: drop pale greys; keep dark strokes as pure black.
INK_LUMA_CUT = 200  # pixels lighter than this become transparent
INK_ALPHA_FLOOR = 40  # then hard-threshold for crisp Kindle pixels


@dataclass(frozen=True)
class Animal:
    """One daily header doodle."""

    id: str
    look: str  # short, subject-first — Klein latches onto opening words


# Whimsy-pool animals first, then a few extras for variety.
ANIMALS: tuple[Animal, ...] = (
    Animal("duck", "A mallard duck in profile, round body, flat bill, small eye."),
    Animal("frog", "A frog sitting side-on, big eye, short legs, smooth rounded body."),
    Animal("otter", "An otter in profile, long body, small rounded ears, whiskers, tapered tail."),
    Animal("newt", "A newt in profile, long slender body, four short legs, long tapering tail."),
    Animal("robin", "A European robin perched side-on, round breast, short beak, thin legs."),
    Animal("pigeon", "A pigeon standing side-on, plump body, small head, short beak."),
    Animal("fox", "A fox in profile, pointed snout, upright ears, bushy tail."),
    Animal("hedgehog", "A hedgehog side-on, round spiny back, pointed snout, tiny legs."),
    Animal("cow", "A cow in profile, blocky body, short horns, udder hint, tail."),
    Animal("sheep", "A sheep in profile, fluffy round body, short legs, small face."),
    Animal(
        "bee",
        "A honeybee in side view as a thin hollow outline: three clear body parts "
        "(round head with two antennae and an eye, oval thorax, longer oval abdomen), "
        "a few horizontal band lines across the abdomen only, two pairs of oval wing "
        "outlines above the thorax, six thin jointed legs — empty magenta interiors, "
        "not a filled blob or a fat cartoon bee.",
    ),
    Animal("bird", "A small songbird perched side-on, round body, short beak, thin legs."),
    Animal("butterfly", "A butterfly with open wings, simple symmetric wing shapes, thin body."),
    Animal("squirrel", "A squirrel side-on, bushy upright tail, small paws, pointed ears."),
    Animal("owl", "An owl facing forward, round face, two big eyes, pointed ear tufts."),
    Animal("mole", "A mole side-on, cylindrical body, pointed snout, paddle feet, tiny eyes."),
    Animal("badger", "A badger in profile, long low body, striped face, short legs."),
    Animal("penguin", "A penguin standing upright, oval body, flippers at sides, small beak."),
    Animal("snail", "A snail side-on, spiral shell, extended body, two eyestalks."),
    Animal("pig", "A pig in profile, round body, snout, floppy ears, curly tail."),
    Animal("cat", "A cat sitting side-on, pointed ears, long tail, simple whiskers."),
    Animal("dog", "A border collie sitting side-on, floppy ears, friendly snout, curled tail."),
    Animal("rabbit", "A rabbit sitting side-on, long upright ears, round body, short tail."),
    Animal("mouse", "A mouse side-on, round ears, pointed snout, long thin tail."),
    Animal("chicken", "A chicken standing side-on, comb on head, short beak, rounded body."),
    Animal("goose", "A goose standing side-on, long neck, flat bill, oval body."),
    Animal("meerkat", "A meerkat standing upright on hind legs, long slender body, pointed snout, dark eye patches."),
    Animal("giraffe", "A giraffe in profile, very long neck, ossicone horns, spotted pattern suggested by outline only, long legs."),
    Animal("moose", "A moose in profile, large body, broad palmate antlers, overhanging snout, humped shoulders."),
    Animal("tiger", "A tiger in profile, powerful body, striped pattern as simple line marks, rounded ears, long tail."),
    Animal("lion", "A lion in profile, male with a full mane, rounded ears, long tail with tuft."),
    Animal("gazelle", "A gazelle in profile, slender body, long thin legs, curved horns, short upright tail."),
    Animal("monkey", "A monkey sitting side-on, long curling tail, round ears, expressive face, grasping hands."),
    Animal("hippo", "A hippo in profile as a thin hollow outline, massive barrel body, huge snout, tiny ears, stubby legs — empty magenta interior, not a black silhouette."),
    Animal("rhino", "A rhinoceros in profile as a thin hollow outline, bulky body, one large horn on the snout, small ears, thick legs — empty magenta interior, not a black silhouette."),
)


STYLE = (
    "Simple black line drawing icon: thin continuous black outline strokes only, "
    "hollow empty interior so the magenta screen shows through the body and gaps, "
    "no solid black fill, no colour fills, no grey shading, no hatching, no gradients, "
    "like a clean minimal icon outline — never a silhouette."
)

FRAMING = (
    "Exactly one subject, centred in the frame, complete and fully visible with a clear "
    "empty magenta margin on every side. Bare backdrop only: no ground, no shadow, "
    "no props, no text, no frame."
)

POSE = "Side view facing left, natural idle pose, readable silhouette when tiny."


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or (SCRIPT_DIR / ".env")
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def prompt_for(animal: Animal, extra: str = "") -> str:
    # Subject first — distilled Klein drops trailing instructions.
    blocks = [
        animal.look,
        f"Simple line drawing of a {animal.id}.",
        STYLE,
        POSE,
        FRAMING,
    ]
    if extra.strip():
        blocks.append(extra.strip().rstrip(".") + ".")
    return "\n\n".join(blocks)


def inkify(image: Image.Image) -> Image.Image:
    """Force surviving pixels to pure black; drop pale / chroma leftovers."""
    import numpy as np

    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    # Ink strength from darkness × existing alpha.
    strength = ((255.0 - luma) / 255.0) * (a / 255.0)
    new_a = np.where(
        (a < 8) | (luma > INK_LUMA_CUT),
        0.0,
        np.where(strength * 255.0 >= INK_ALPHA_FLOOR, 255.0, 0.0),
    )
    out = np.zeros_like(rgba)
    out[..., 3] = new_a
    return Image.fromarray(out.astype(np.uint8), mode="RGBA")


def check_line_cutout(image: Image.Image) -> str:
    """Validate a sparse hollow outline (reject filled silhouettes)."""
    import numpy as np
    from collections import deque

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    ink = rgba[..., 3] > 128
    height, width = ink.shape
    total = width * height
    subject = int(ink.sum()) / total
    if subject < 0.004:
        return "almost no ink — outline failed to draw"
    if subject > 0.28:
        return "too much ink — looks like a filled silhouette, want outline only"

    ys, xs = np.where(ink)
    if len(xs) == 0:
        return "almost no ink — outline failed to draw"
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    sub = ink[y0:y1, x0:x1]
    bbox_area = sub.size
    bbox_ink = float(sub.mean()) if bbox_area else 0.0
    # Thin outlines are sparse inside their bbox; solid blobs pack most of it.
    if bbox_ink > 0.32:
        return "filled silhouette — body is solid black, want hollow outline"

    # Enclosed transparent pockets (holes inside the outline). A filled blob has almost none.
    h, w = sub.shape
    reachable = np.zeros_like(sub, dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not sub[y, x]:
                reachable[y, x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not sub[y, x] and not reachable[y, x]:
                reachable[y, x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not reachable[ny, nx] and not sub[ny, nx]:
                reachable[ny, nx] = True
                q.append((nx, ny))
    enclosed = float(((~sub) & (~reachable)).mean()) if bbox_area else 0.0
    if bbox_ink > 0.18 and enclosed < 0.06:
        return "filled silhouette — no hollow interior inside the outline"

    band = max(2, int(round(min(width, height) * 0.04)))
    border = (
        int(ink[:band, :].sum())
        + int(ink[-band:, :].sum())
        + int(ink[band:-band, :band].sum())
        + int(ink[band:-band, -band:].sum())
    )
    border_total = 2 * band * width + 2 * band * max(0, height - 2 * band)
    if border_total and border / border_total > 0.35:
        return "ink touches the frame edge — need clear margin"
    return ""


def fit_and_pack(image: Image.Image, final_size: int, *, fill: float) -> Image.Image:
    """Centre the outline and scale so the longest side fills ``fill`` of the canvas."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.point(lambda a: 255 if a > 128 else 0).getbbox()
    if bbox is None:
        raise ValueError("empty image after inkify")
    subject = rgba.crop(bbox)
    longest = max(subject.width, subject.height)
    if longest <= 0:
        raise ValueError("empty image after inkify")
    scale = (final_size * fill) / longest
    target = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    subject = subject.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 0))
    canvas.paste(
        subject,
        ((final_size - subject.width) // 2, (final_size - subject.height) // 2),
    )
    # Re-inkify after Lanczos so downscale greys become crisp black again.
    return inkify(canvas)


def process_raw(png_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(png_bytes)) as source:
        image = inkify(source.convert("RGBA"))
        problem = check_line_cutout(image)
        if problem:
            raise ValueError(problem)
        image = fit_and_pack(image, FINAL_SIZE, fill=SUBJECT_FILL)
        problem = check_line_cutout(image)
        if problem:
            raise ValueError(problem)
        return pil_to_png_bytes(image)


def generate_one(
    backend: ImageBackend,
    animal: Animal,
    *,
    model: str,
    extra: str = "",
    max_retries: int = MAX_RETRIES,
    verify: bool = True,
    vision_model: str = DEFAULT_VISION_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
) -> bytes:
    """Diffuse → geometry checks → optional VLM species/style check."""
    prompt_extra = extra
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  diffusion attempt {attempt}/{max_retries} …", flush=True)
            raw = backend.generate(
                prompt=prompt_for(animal, prompt_extra),
                references=[],
                require_alpha=True,
                source_size=SOURCE_SIZE,
                model=model,
                quality="medium",
                max_retries=1,
            )
            print("  inkify / pack …", flush=True)
            png = process_raw(raw)
        except ValueError as exc:
            last_error = exc
            print(f"  cutout validation failed: {exc}; regenerating", file=sys.stderr)
            continue

        if not verify:
            return png

        # Diffusion and VLM must not share unified memory.
        print("  unloading diffusion for vision QA …", flush=True)
        backend.unload()
        verdict = verify_animal(
            png,
            animal_id=animal.id,
            look=animal.look,
            model=vision_model,
            host=ollama_host,
        )
        if verdict.ok:
            return png

        reason = verdict.summary()
        last_error = ValueError(reason)
        print(f"  {reason}; regenerating", file=sys.stderr)
        if verdict.fix:
            prompt_extra = verdict.fix
        elif prompt_extra:
            pass
        else:
            prompt_extra = (
                f"Draw a clear simple black outline of a {animal.id}. {animal.look}"
            )

    assert last_error is not None
    raise last_error


def open_preview(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)])
        else:
            print(f"  preview: {path.resolve()}")
    except OSError as exc:
        print(f"  could not open preview: {exc}", file=sys.stderr)


def interactive_choice(candidate: Path) -> tuple[str, str]:
    open_preview(candidate)
    while True:
        answer = input(
            "  [a]ccept  [A]ccept+quit  [r]etry  [e]dit prompt  [s]kip  [q]uit: "
        ).strip()
        lower = answer.lower()
        if answer == "A":
            return "accept_quit", ""
        if lower in {"a", "accept", ""}:
            return "accept", ""
        if lower in {"r", "retry"}:
            return "retry", ""
        if lower in {"e", "edit"}:
            return "retry", input("  Extra instruction: ").strip()
        if lower in {"s", "skip"}:
            return "skip", ""
        if lower in {"q", "quit"}:
            return "quit", ""
        print("  Please enter a, A, r, e, s, or q.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List animal ids and exit")
    parser.add_argument("--all", action="store_true", help="Generate every animal in the catalog")
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="Generate these animal ids only",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Accepted PNG directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing files")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Preview each candidate and accept/retry/skip",
    )
    parser.add_argument(
        "--model",
        default="flux2-klein-4b",
        help="mflux model (default: flux2-klein-4b)",
    )
    parser.add_argument("--steps", type=int, default=None, help="Override diffusion steps")
    parser.add_argument("--seed", type=int, default=None, help="Fixed seed (default: random)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts only")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Validation retries per animal (default: {MAX_RETRIES})",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Vision-check existing PNGs; keep passes, regenerate failures/missing",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip Ollama vision QA (geometry checks still run; incompatible with --audit)",
    )
    parser.add_argument(
        "--vision-model",
        default=DEFAULT_VISION_MODEL,
        help=f"Ollama vision model (default: {DEFAULT_VISION_MODEL})",
    )
    parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama API host (default: {DEFAULT_OLLAMA_HOST})",
    )
    return parser.parse_args()


def selected_animals(args: argparse.Namespace) -> list[Animal]:
    by_id = {a.id: a for a in ANIMALS}
    if args.only:
        missing = [i for i in args.only if i not in by_id]
        if missing:
            raise SystemExit(f"Unknown animal id(s): {', '.join(missing)}")
        return [by_id[i] for i in args.only]
    if args.all or args.list or args.dry_run or args.interactive or args.audit:
        return list(ANIMALS)
    raise SystemExit("Pass --only <ids…>, --all, --interactive, --audit, or --list")


def accept_animal(
    png: bytes,
    *,
    animal: Animal,
    dest: Path,
    interactive: bool,
) -> tuple[str, str]:
    """Write candidate; optionally ask the user. Returns (action, extra)."""
    candidate = CANDIDATES_DIR / f"{animal.id}.png"
    candidate.write_bytes(png)
    if not interactive:
        dest.write_bytes(png)
        print(f"  wrote {dest}")
        return "accept", ""
    action, extra = interactive_choice(candidate)
    if action in {"accept", "accept_quit"}:
        dest.write_bytes(png)
        print(f"  wrote {dest}")
    elif action == "skip":
        print("  skipped")
    return action, extra


def main() -> int:
    load_dotenv()
    args = parse_args()
    animals = selected_animals(args)

    if args.list:
        for animal in animals:
            print(f"{animal.id:12}  {animal.look}")
        return 0

    if args.dry_run:
        for animal in animals:
            print("=" * 60)
            print(animal.id)
            print(prompt_for(animal))
        return 0

    if args.audit and args.no_verify:
        raise SystemExit("--audit needs vision QA; drop --no-verify")

    out_dir: Path = args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    model = normalize_model_name(args.model)
    steps = args.steps if args.steps is not None else default_steps_for(model)
    verify = not args.no_verify
    if verify:
        ensure_vision_model(args.vision_model, args.ollama_host)
        print(f"Vision QA: {args.vision_model} @ {args.ollama_host}", flush=True)
    else:
        print("Vision QA: off (--no-verify)", flush=True)

    if args.audit:
        print("Mode: audit (keep vision passes; regen failures/missing)", flush=True)

    backend = create_backend(steps=steps, seed=args.seed)
    backend.configure_for_model(model, steps=steps)

    begin_local_session(CANDIDATES_DIR)
    try:
        for animal in animals:
            dest = out_dir / f"{animal.id}.png"

            if args.audit:
                print(f"\n=== {animal.id} ===")
                extra = ""
                if dest.is_file():
                    print("  unloading diffusion for vision QA …", flush=True)
                    backend.unload()
                    verdict = verify_animal(
                        dest.read_bytes(),
                        animal_id=animal.id,
                        look=animal.look,
                        model=args.vision_model,
                        host=args.ollama_host,
                    )
                    if verdict.ok:
                        print(f"  keep {dest}")
                        continue
                    print(f"  {verdict.summary()}; regenerating", flush=True)
                    extra = verdict.fix or (
                        f"Draw a clear simple black outline of a {animal.id}. {animal.look}"
                    )
                else:
                    print("  missing; generating", flush=True)

                while True:
                    try:
                        png = generate_one(
                            backend,
                            animal,
                            model=model,
                            extra=extra,
                            max_retries=args.max_retries,
                            verify=True,
                            vision_model=args.vision_model,
                            ollama_host=args.ollama_host,
                        )
                    except Exception as exc:
                        print(f"  FAILED {animal.id}: {exc}", file=sys.stderr)
                        break
                    action, extra = accept_animal(
                        png, animal=animal, dest=dest, interactive=args.interactive
                    )
                    if action == "accept_quit":
                        return 0
                    if action in {"accept", "skip"}:
                        break
                    if action == "quit":
                        return 0
                    # retry with optional extra from interactive edit
                continue

            if dest.is_file() and not args.overwrite and not args.interactive:
                print(f"skip {animal.id} (exists; use --overwrite)")
                continue

            print(f"\n=== {animal.id} ===")
            extra = ""
            while True:
                try:
                    png = generate_one(
                        backend,
                        animal,
                        model=model,
                        extra=extra,
                        max_retries=args.max_retries,
                        verify=verify,
                        vision_model=args.vision_model,
                        ollama_host=args.ollama_host,
                    )
                except Exception as exc:
                    print(f"  FAILED {animal.id}: {exc}", file=sys.stderr)
                    break

                candidate = CANDIDATES_DIR / f"{animal.id}.png"
                candidate.write_bytes(png)

                if not args.interactive:
                    dest.write_bytes(png)
                    print(f"  wrote {dest}")
                    break

                action, extra = interactive_choice(candidate)
                if action == "accept":
                    dest.write_bytes(png)
                    print(f"  wrote {dest}")
                    break
                if action == "accept_quit":
                    dest.write_bytes(png)
                    print(f"  wrote {dest}")
                    return 0
                if action == "skip":
                    print("  skipped")
                    break
                if action == "quit":
                    return 0
                # retry with optional extra instruction
    finally:
        end_local_session()
        backend.reset()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
