"""Local image generation via mflux (FLUX.2 Klein on Apple Silicon)."""

from __future__ import annotations

import io
import os
import random
import shutil
import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image

# Chroma-key backdrop. Asking for a "transparent background" makes the model paint a
# checkerboard, which then survives background removal; a bright key colour that never
# appears in the artwork keys out cleanly, including gaps between legs.
LOCAL_ALPHA_HINT = """
The background is a flat solid bright magenta chroma-key screen (#FF00FF) covering the
whole frame behind the subject, right into all four corners. The subject itself uses its
own natural colours and contains no magenta.
""".strip()

CHROMA_RGB = (255, 0, 255)
CHROMA_CUT = 100.0
CHROMA_SOFT = 70.0
CHROMA_BORDER_SHARE = 0.5

# Fallback for runs where the model ignores the key colour and paints a plain backdrop.
BACKDROP_RGB = (232, 232, 232)

LOCAL_RUN_LOCK = Path(__file__).resolve().parent / "candidates" / ".local_run.lock"


def configure_local_mlx_env(*, force_safe: bool = False) -> None:
    """
    Tune Metal/MLX before the library is imported.
    Helps avoid GPU command-buffer timeouts on M1/M2 (0000000e Internal Error).
    """
    default_ops = "1" if force_safe else "10"
    os.environ.setdefault("MLX_MAX_OPS_PER_BUFFER", default_ops)
    os.environ.setdefault("AGX_RELAX_CDM_CTXSTORE_TIMEOUT", "1")


def clear_local_mlx_state(*, deep: bool = False) -> None:
    """Drop in-process MLX caches; optionally wipe on-disk Metal compile caches."""
    try:
        import gc

        gc.collect()
        try:
            import mlx.core as mx

            mx.clear_cache()
            # Free allocator arenas so a VLM (Ollama) can claim unified memory next.
            reset_peak = getattr(mx, "reset_peak_memory", None)
            if callable(reset_peak):
                try:
                    reset_peak()
                except Exception:
                    pass
            elif hasattr(mx, "metal") and hasattr(mx.metal, "reset_peak_memory"):
                try:
                    mx.metal.reset_peak_memory()
                except Exception:
                    pass
        except Exception:
            pass
        gc.collect()
    except Exception:
        pass

    if not deep:
        return
    cache_roots = [
        Path.home() / "Library" / "Caches" / "mlx",
        Path.home() / ".cache" / "mlx",
    ]
    for root in cache_roots:
        if not root.is_dir():
            continue
        for child_name in ("metal", "kernels", "compile", "tmp"):
            target = root / child_name
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)


def cleanup_stale_candidates(candidates_dir: Path) -> list[str]:
    """Remove leftover candidate / temp files from a crashed run."""
    if not candidates_dir.is_dir():
        return []
    removed: list[str] = []
    patterns = (
        "*-candidate-*.png",
        "*.png.tmp",
        "*.tmp",
    )
    seen: set[Path] = set()
    for pattern in patterns:
        for path in candidates_dir.glob(pattern):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed


def begin_local_session(candidates_dir: Path) -> None:
    """
    Start a local generation session.
    If the previous run aborted (Metal crash / kill), clean candidates + MLX state.
    """
    unclean = LOCAL_RUN_LOCK.is_file()
    configure_local_mlx_env(force_safe=unclean)
    candidates_dir.mkdir(parents=True, exist_ok=True)
    removed = cleanup_stale_candidates(candidates_dir)
    if unclean:
        print(
            "Previous local run did not finish cleanly (Metal crash / interrupt). "
            "Resetting candidates and MLX runtime caches...",
            flush=True,
        )
        clear_local_mlx_state(deep=True)
    elif removed:
        print(
            f"Cleared {len(removed)} stale candidate file(s) from prior attempts.",
            flush=True,
        )
    else:
        clear_local_mlx_state(deep=False)

    LOCAL_RUN_LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_RUN_LOCK.write_text(f"pid={os.getpid()}\nstarted={time.time():.0f}\n", encoding="utf-8")


def end_local_session() -> None:
    """Mark a clean exit so the next run skips deep reset."""
    try:
        LOCAL_RUN_LOCK.unlink(missing_ok=True)
    except OSError:
        pass
    clear_local_mlx_state(deep=False)


def parse_source_size(source_size: str) -> tuple[int, int]:
    text = source_size.lower().replace("*", "x")
    if "x" not in text:
        raise ValueError(f"Invalid --source-size '{source_size}' (expected WxH, e.g. 1024x1024)")
    width_s, height_s = text.split("x", 1)
    return int(width_s), int(height_s)


def generated_to_pil(generated: Any) -> Image.Image:
    """Normalize mflux / PIL outputs to a Pillow image."""
    if isinstance(generated, Image.Image):
        return generated
    for attr in ("image", "pil_image", "pil"):
        value = getattr(generated, attr, None)
        if isinstance(value, Image.Image):
            return value
    if hasattr(generated, "save"):
        buffer = io.BytesIO()
        try:
            generated.save(buffer)
        except TypeError:
            generated.save(buffer, format="PNG")
        buffer.seek(0)
        return Image.open(buffer).convert("RGBA")
    raise TypeError(f"Unsupported generated image type: {type(generated)!r}")


def pil_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def _colour_distance(rgb: tuple[int, int, int], target: tuple[int, int, int]) -> float:
    return (
        (rgb[0] - target[0]) ** 2
        + (rgb[1] - target[1]) ** 2
        + (rgb[2] - target[2]) ** 2
    ) ** 0.5


def _border_pixels(rgba: Image.Image) -> list[tuple[int, int, int]]:
    width, height = rgba.size
    pixels = rgba.load()
    step = max(1, min(width, height) // 64)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        for y in (0, height - 1):
            samples.append(pixels[x, y][:3])
    for y in range(0, height, step):
        for x in (0, width - 1):
            samples.append(pixels[x, y][:3])
    return samples


def chroma_border_share(image: Image.Image) -> float:
    """How much of the frame edge is the key colour."""
    samples = _border_pixels(image.convert("RGBA"))
    if not samples:
        return 0.0
    keyed = sum(1 for c in samples if _colour_distance(c, CHROMA_RGB) <= CHROMA_CUT)
    return keyed / len(samples)


def knockout_chroma(image: Image.Image) -> Image.Image:
    """
    Key out the magenta screen with a soft edge, then de-spill the remaining fringe.

    Colour distance alone is enough here: nothing in the artwork comes near #FF00FF, so
    enclosed background (between legs, under a chin) drops out along with the surround.
    """
    import numpy as np

    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    red, green, blue = rgba[..., 0], rgba[..., 1], rgba[..., 2]
    distance = np.sqrt(
        (red - CHROMA_RGB[0]) ** 2
        + (green - CHROMA_RGB[1]) ** 2
        + (blue - CHROMA_RGB[2]) ** 2
    )
    alpha = np.clip((distance - CHROMA_CUT) / CHROMA_SOFT, 0.0, 1.0)

    # Partly transparent pixels are subject blended with the screen; pull the magenta cast
    # out of them so edges do not glow pink. Fully opaque pixels keep their real colours,
    # which protects genuinely pink subjects.
    fringe = (alpha > 0.0) & (alpha < 1.0)
    magenta_cast = np.maximum((red + blue) / 2.0 - green, 0.0)
    red = np.where(fringe, red - magenta_cast, red)
    blue = np.where(fringe, blue - magenta_cast, blue)

    out = np.stack(
        [
            np.clip(red, 0, 255),
            np.clip(green, 0, 255),
            np.clip(blue, 0, 255),
            alpha * 255.0,
        ],
        axis=-1,
    ).astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def sample_backdrop_colours(image: Image.Image, *, limit: int = 2) -> list[tuple[int, int, int]]:
    """
    Dominant frame-edge colours, coarsely quantized.

    Returns more than one because models sometimes paint a two-tone "transparency"
    checkerboard, and removing only one of its shades leaves a chequered halo.
    """
    samples = _border_pixels(image.convert("RGBA"))
    if not samples:
        return [BACKDROP_RGB]
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for colour in samples:
        key = (colour[0] // 16, colour[1] // 16, colour[2] // 16)
        buckets.setdefault(key, []).append(colour)
    ranked = sorted(buckets.values(), key=len, reverse=True)
    chosen: list[tuple[int, int, int]] = []
    for group in ranked[:limit]:
        if len(group) / len(samples) < 0.12:
            break
        n = len(group)
        chosen.append(
            (
                sum(c[0] for c in group) // n,
                sum(c[1] for c in group) // n,
                sum(c[2] for c in group) // n,
            )
        )
    return chosen or [BACKDROP_RGB]


def knockout_flat_backdrop(
    image: Image.Image,
    *,
    threshold: float = 48.0,
) -> Image.Image:
    """Flood-fill transparency inward from the edges for a plain painted backdrop."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    targets = sample_backdrop_colours(rgba)
    pixels = rgba.load()
    visited = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height and not visited[y][x]:
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if visited[y][x]:
            continue
        visited[y][x] = True
        r, g, b, a = pixels[x, y]
        if a == 0:
            continue
        if all(_colour_distance((r, g, b), target) > threshold for target in targets):
            continue
        pixels[x, y] = (r, g, b, 0)
        enqueue(x + 1, y)
        enqueue(x - 1, y)
        enqueue(x, y + 1)
        enqueue(x, y - 1)

    return rgba


def remove_backdrop(image: Image.Image) -> Image.Image:
    """Chroma key when the model honoured the magenta screen, flood fill otherwise."""
    if chroma_border_share(image) >= CHROMA_BORDER_SHARE:
        return knockout_chroma(image)
    return knockout_flat_backdrop(image)


class ImageBackend(ABC):
    name: str

    @abstractmethod
    def generate(
        self,
        *,
        prompt: str,
        references: list[Path],
        require_alpha: bool,
        source_size: str,
        model: str,
        quality: str,
        max_retries: int,
        negative_prompt: str | None = None,
    ) -> bytes:
        """Return a PNG byte payload (pre-resize)."""


# Models already wired through mflux. Distilled Klein has no usable negatives; Z-Image
# and Qwen use CFG. Qwen Image Edit is the only path that treats attached photos as
# anatomy/style conditioning instead of Klein's near-verbatim repaint.
SUPPORTED_MODELS = (
    "flux2-klein-4b",
    "flux2-klein-9b",
    "flux2-klein-9b-kv",
    "z-image-turbo",
    "z-image",
    "qwen-image",
    "qwen-image-edit",
)

MODEL_DEFAULT_STEPS: dict[str, int] = {
    "flux2-klein-4b": 4,
    "flux2-klein-9b": 8,
    "flux2-klein-9b-kv": 8,
    "z-image-turbo": 9,
    "z-image": 28,
    "qwen-image": 30,
    "qwen-image-edit": 30,
}

MODEL_DEFAULT_GUIDANCE: dict[str, float] = {
    "z-image": 4.0,
    "qwen-image": 4.0,
    "qwen-image-edit": 4.0,
}

_MODEL_CONFIG_ATTR = {
    "flux2-klein-4b": "flux2_klein_4b",
    "flux2-klein-9b": "flux2_klein_9b",
    "flux2-klein-9b-kv": "flux2_klein_9b_kv",
    "z-image-turbo": "z_image_turbo",
    "z-image": "z_image",
    "qwen-image": "qwen_image",
    "qwen-image-edit": "qwen_image_edit",
}


def normalize_model_name(model: str) -> str:
    key = model.strip().lower().replace("_", "-")
    aliases = {
        "klein-4b": "flux2-klein-4b",
        "klein-9b": "flux2-klein-9b",
        "zimage": "z-image",
        "zimage-turbo": "z-image-turbo",
        "qwen": "qwen-image",
        "qwen-edit": "qwen-image-edit",
        "qwen-edit-plus": "qwen-image-edit",
        "qwen-edit-2509": "qwen-image-edit",
    }
    return aliases.get(key, key)


def model_family(model: str) -> str:
    key = normalize_model_name(model)
    if key.startswith("z-image"):
        return "z-image"
    if key.startswith("flux2-klein"):
        return "flux2-klein"
    if key == "qwen-image-edit":
        return "qwen-image-edit"
    if key == "qwen-image":
        return "qwen-image"
    raise SystemExit(
        f"Unknown local model '{model}'. Supported: {', '.join(SUPPORTED_MODELS)}."
    )


def model_supports_negatives(model: str) -> bool:
    """CFG models that honour negative prompts for hard-species lookalikes."""
    return normalize_model_name(model) in {"z-image", "qwen-image", "qwen-image-edit"}


def model_uses_multi_ref_conditioning(model: str) -> bool:
    """
    True when attached images are read as multi-ref conditioning (anatomy/style roles).

    Klein edit / Z-Image img2img repaint the input closely — do not send photo refs there.
    """
    return model_family(model) == "qwen-image-edit"


def default_steps_for(model: str) -> int:
    return MODEL_DEFAULT_STEPS.get(normalize_model_name(model), 4)


def default_guidance_for(model: str) -> float | None:
    return MODEL_DEFAULT_GUIDANCE.get(normalize_model_name(model))


class LocalMfluxBackend(ImageBackend):
    """Apple Silicon local generation via mflux (FLUX.2 Klein, Z-Image, or Qwen)."""

    name = "local"

    DEFAULT_MODEL = "flux2-klein-4b"
    DEFAULT_STEPS = 4
    DEFAULT_QUANTIZE = 8

    def __init__(
        self,
        *,
        quantize: int = DEFAULT_QUANTIZE,
        steps: int = DEFAULT_STEPS,
        low_ram: bool = True,
        seed: int | None = None,
        guidance: float | None = None,
    ) -> None:
        try:
            from mflux.models.common.config import ModelConfig
            from mflux.models.flux2.variants import Flux2Klein, Flux2KleinEdit
            from mflux.models.qwen.variants.edit.qwen_image_edit import QwenImageEdit
            from mflux.models.qwen.variants.txt2img.qwen_image import QwenImage
            from mflux.models.z_image import ZImage
        except ImportError as exc:
            raise SystemExit(
                "Local backend requires mflux. Install with:\n"
                "  cd line-animals && uv sync --extra local\n"
                f"Import error: {exc}"
            ) from exc

        self._ModelConfig = ModelConfig
        self._Flux2Klein = Flux2Klein
        self._Flux2KleinEdit = Flux2KleinEdit
        self._QwenImage = QwenImage
        self._QwenImageEdit = QwenImageEdit
        self._ZImage = ZImage
        self.quantize = quantize
        self.steps = steps
        self.low_ram = low_ram
        self.seed = seed
        self.guidance = guidance
        self._txt_model: Any | None = None
        self._edit_model: Any | None = None
        self._loaded_model_name: str | None = None
        self._negatives_warned: set[str] = set()
        configure_local_mlx_env(force_safe=LOCAL_RUN_LOCK.is_file())
        clear_local_mlx_state(deep=False)

    def reset(self) -> None:
        """Fully unload diffusion weights so a VLM (or another model) can load."""
        for slot in ("_txt_model", "_edit_model"):
            model = getattr(self, slot, None)
            if model is None:
                continue
            # Break MemorySaver ↔ model cycles so GC can reclaim unified memory.
            try:
                callbacks = getattr(model, "callbacks", None)
                if callbacks is not None and hasattr(callbacks, "clear"):
                    callbacks.clear()
            except Exception:
                pass
            for attr in ("text_encoder", "transformer", "vae", "tokenizer"):
                if hasattr(model, attr):
                    try:
                        setattr(model, attr, None)
                    except Exception:
                        pass
            setattr(self, slot, None)
        self._loaded_model_name = None
        clear_local_mlx_state(deep=False)

    def unload(self) -> None:
        """Alias for reset — exclusive RAM handoff before vision QA."""
        self.reset()

    def configure_for_model(
        self,
        model: str,
        *,
        steps: int | None = None,
        guidance: float | None = None,
    ) -> None:
        """Unload current weights and retarget steps/guidance for a new model."""
        key = normalize_model_name(model)
        self.reset()
        self.steps = default_steps_for(key) if steps is None else steps
        self.guidance = default_guidance_for(key) if guidance is None else guidance

    def _config_for(self, model: str) -> Any:
        key = normalize_model_name(model)
        attr = _MODEL_CONFIG_ATTR.get(key)
        if attr is None or not hasattr(self._ModelConfig, attr):
            supported = ", ".join(SUPPORTED_MODELS)
            raise SystemExit(f"Unknown local model '{model}'. Supported: {supported}.")
        factory = getattr(self._ModelConfig, attr)
        return factory() if callable(factory) else factory

    def _build_model(self, model: str, *, for_edit: bool) -> Any:
        key = normalize_model_name(model)
        family = model_family(key)
        config = self._config_for(key)
        if family == "z-image":
            return self._ZImage(model_config=config, quantize=self.quantize)
        if family == "qwen-image":
            return self._QwenImage(model_config=config, quantize=self.quantize)
        if family == "qwen-image-edit":
            return self._QwenImageEdit(model_config=config, quantize=self.quantize)
        cls = self._Flux2KleinEdit if for_edit else self._Flux2Klein
        return cls(model_config=config, quantize=self.quantize)

    def _ensure_model(self, model: str, *, for_edit: bool) -> Any:
        key = normalize_model_name(model)
        family = model_family(key)
        use_edit_slot = for_edit and family == "flux2-klein"
        slot = "_edit_model" if use_edit_slot else "_txt_model"
        current = getattr(self, slot)
        if (
            current is not None
            and self._loaded_model_name == key
            and not self._model_needs_reload(current)
        ):
            return current
        if current is not None:
            self.reset()
        label = {
            "flux2-klein": "edit" if use_edit_slot else "txt2img",
            "z-image": "txt2img",
            "qwen-image": "txt2img",
            "qwen-image-edit": "multi-ref edit",
        }.get(family, family)
        print(
            f"  loading local {label} model {key} "
            f"(q={self.quantize}, steps={self.steps}; first run downloads weights) ...",
            flush=True,
        )
        loaded = self._build_model(key, for_edit=for_edit)
        self._maybe_enable_memory_saver(loaded)
        setattr(self, slot, loaded)
        self._loaded_model_name = key
        return loaded

    @staticmethod
    def _model_needs_reload(model: Any) -> bool:
        return (
            getattr(model, "text_encoder", object()) is None
            or getattr(model, "transformer", object()) is None
        )

    def _maybe_enable_memory_saver(self, model: Any) -> None:
        if not self.low_ram:
            return
        try:
            from mflux.callbacks.instances.memory_saver import MemorySaver

            # Keep weights across images; still apply the MLX cache limit.
            model.callbacks.register(
                MemorySaver(
                    model=model,
                    keep_transformer=True,
                    cache_limit_bytes=1000**3,
                    num_seeds=2,
                )
            )
        except Exception as exc:
            print(f"  warning: could not enable mflux MemorySaver ({exc})", file=sys.stderr)

    @staticmethod
    def _clear_mlx_cache() -> None:
        clear_local_mlx_state(deep=False)

    def generate(
        self,
        *,
        prompt: str,
        references: list[Path],
        require_alpha: bool,
        source_size: str,
        model: str,
        quality: str,
        max_retries: int,
        negative_prompt: str | None = None,
    ) -> bytes:
        """
        Generate in a subprocess so Ctrl-C can kill Metal/MLX work immediately.

        Set LINE_ANIMALS_NO_SUBPROCESS=1 to force in-process generation (debugging).
        """
        from interruptible import run_in_subprocess

        spec = {
            "quantize": self.quantize,
            "steps": self.steps,
            "low_ram": self.low_ram,
            "seed": self.seed,
            "guidance": self.guidance,
            "prompt": prompt,
            "references": [str(path) for path in references],
            "require_alpha": require_alpha,
            "source_size": source_size,
            "model": model,
            "quality": quality,
            "max_retries": max_retries,
            "negative_prompt": negative_prompt,
        }
        return run_in_subprocess(_generate_job, spec, label="generate", heartbeat_s=0)

    def generate_in_process(
        self,
        *,
        prompt: str,
        references: list[Path],
        require_alpha: bool,
        source_size: str,
        model: str,
        quality: str,
        max_retries: int,
        negative_prompt: str | None = None,
    ) -> bytes:
        del quality  # unused locally
        width, height = parse_source_size(source_size)
        key = normalize_model_name(model)
        family = model_family(key)
        full_prompt = prompt
        if require_alpha:
            full_prompt = f"{prompt.rstrip()}\n\n{LOCAL_ALPHA_HINT}"

        use_negatives = model_supports_negatives(key) and bool(negative_prompt)
        if negative_prompt and not model_supports_negatives(key) and key not in self._negatives_warned:
            self._negatives_warned.add(key)
            print(
                f"  note: model {key} ignores negative prompts; try --model z-image",
                flush=True,
            )

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            seed = self.seed if self.seed is not None else random.randint(0, 2**31 - 1)
            try:
                print(
                    f"  diffusion: seed={seed} steps={self.steps} model={key} …",
                    flush=True,
                )
                if family == "z-image":
                    kwargs: dict[str, Any] = {
                        "seed": seed,
                        "prompt": full_prompt,
                        "num_inference_steps": self.steps,
                        "width": width,
                        "height": height,
                    }
                    if self.guidance is not None:
                        kwargs["guidance"] = self.guidance
                    if use_negatives:
                        kwargs["negative_prompt"] = negative_prompt
                    if references:
                        # Z-Image img2img takes a single path (not multi-ref conditioning).
                        kwargs["image_path"] = str(references[0])
                    generated = self._ensure_model(key, for_edit=False).generate_image(**kwargs)
                elif family == "qwen-image-edit":
                    if not references:
                        raise ValueError(
                            "qwen-image-edit needs at least one reference image "
                            "(use --photo and/or --reference)"
                        )
                    image_paths = [str(path) for path in references]
                    qwen_kwargs: dict[str, Any] = {
                        "seed": seed,
                        "prompt": full_prompt,
                        "image_paths": image_paths,
                        "image_path": image_paths[0],
                        "num_inference_steps": self.steps,
                        "width": width,
                        "height": height,
                        "guidance": self.guidance if self.guidance is not None else 4.0,
                    }
                    if use_negatives:
                        qwen_kwargs["negative_prompt"] = negative_prompt
                    generated = self._ensure_model(key, for_edit=False).generate_image(
                        **qwen_kwargs
                    )
                elif family == "qwen-image":
                    qwen_txt: dict[str, Any] = {
                        "seed": seed,
                        "prompt": full_prompt,
                        "num_inference_steps": self.steps,
                        "width": width,
                        "height": height,
                        "guidance": self.guidance if self.guidance is not None else 4.0,
                    }
                    if use_negatives:
                        qwen_txt["negative_prompt"] = negative_prompt
                    if references:
                        # Single-image img2img only — avoid photos here; use qwen-image-edit.
                        qwen_txt["image_path"] = str(references[0])
                    generated = self._ensure_model(key, for_edit=False).generate_image(
                        **qwen_txt
                    )
                elif references:
                    generated = self._ensure_model(key, for_edit=True).generate_image(
                        seed=seed,
                        prompt=full_prompt,
                        image_paths=[str(path) for path in references],
                        num_inference_steps=self.steps,
                        width=width,
                        height=height,
                    )
                else:
                    generated = self._ensure_model(key, for_edit=False).generate_image(
                        seed=seed,
                        prompt=full_prompt,
                        num_inference_steps=self.steps,
                        width=width,
                        height=height,
                    )
                pil = generated_to_pil(generated)
                print("  diffusion: image ready, removing backdrop …", flush=True)
                if require_alpha:
                    pil = remove_backdrop(pil)
                self._clear_mlx_cache()
                print("  diffusion: backdrop done", flush=True)
                return pil_to_png_bytes(pil)
            except Exception as exc:
                last_error = exc
                print(f"  local generation failed: {exc}; resetting MLX state", flush=True)
                self.reset()
                if attempt == max_retries:
                    break
                time.sleep(0.5)

        assert last_error is not None
        raise last_error


def _generate_job(spec: dict[str, Any]) -> bytes:
    """Top-level worker for spawn — must stay picklable."""
    backend = LocalMfluxBackend(
        quantize=int(spec["quantize"]),
        steps=int(spec["steps"]),
        low_ram=bool(spec["low_ram"]),
        seed=spec.get("seed"),
        guidance=spec.get("guidance"),
    )
    try:
        return backend.generate_in_process(
            prompt=str(spec["prompt"]),
            references=[Path(p) for p in spec.get("references") or []],
            require_alpha=bool(spec["require_alpha"]),
            source_size=str(spec["source_size"]),
            model=str(spec["model"]),
            quality=str(spec.get("quality") or "medium"),
            max_retries=int(spec.get("max_retries") or 1),
            negative_prompt=spec.get("negative_prompt"),
        )
    finally:
        backend.reset()


def create_backend(
    *,
    quantize: int = LocalMfluxBackend.DEFAULT_QUANTIZE,
    steps: int = LocalMfluxBackend.DEFAULT_STEPS,
    low_ram: bool = True,
    seed: int | None = None,
    guidance: float | None = None,
) -> ImageBackend:
    configure_local_mlx_env(force_safe=LOCAL_RUN_LOCK.is_file())
    return LocalMfluxBackend(
        quantize=quantize,
        steps=steps,
        low_ram=low_ram,
        seed=seed,
        guidance=guidance,
    )
