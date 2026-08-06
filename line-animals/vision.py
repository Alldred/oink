"""Local vision QA via Ollama — check a line animal against its look prompt.

Diffusion (mflux) and vision (Ollama) must not share RAM: callers unload the
diffusion backend before calling ``verify_animal``, and this module unloads the
VLM when finished.
"""

from __future__ import annotations

import base64
import io
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from PIL import Image

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"

# Extra words that still count as a match for each id.
_ALIASES: dict[str, tuple[str, ...]] = {
    "bird": ("songbird", "sparrow", "finch", "warbler"),
    "rhino": ("rhinoceros",),
    "hippo": ("hippopotamus",),
    "cow": ("cattle", "bull", "heifer"),
    "dog": ("puppy", "hound", "canine"),
    "cat": ("kitten", "feline"),
    "pig": ("hog", "boar", "sow"),
    "sheep": ("lamb", "ewe", "ram"),
    "chicken": ("hen", "rooster", "cockerel"),
    "goose": ("geese",),
}


@dataclass(frozen=True)
class VisionVerdict:
    ok: bool
    seen: str = ""
    reason: str = ""
    fix: str = ""
    error: str = ""

    def summary(self) -> str:
        if self.error:
            return f"vision error: {self.error}"
        if self.ok:
            return f"vision: match ({self.seen or 'ok'})"
        bits = [b for b in (self.reason, f"saw: {self.seen}" if self.seen else "") if b]
        return "vision reject: " + "; ".join(bits)


def ensure_vision_model(model: str, host: str = DEFAULT_OLLAMA_HOST) -> None:
    """Fail fast if Ollama is down; pull the model once if missing."""
    wanted = model.strip()
    if not wanted:
        raise SystemExit("Vision model name is empty.")
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=5) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:
        raise SystemExit(
            f"Ollama is not reachable at {host}. Start it with: ollama serve\n({exc})"
        ) from exc

    names = {m.get("name", "") for m in payload.get("models", [])}
    stems = {n.split(":")[0] for n in names}
    if wanted in names or wanted.split(":")[0] in stems and any(
        n.startswith(wanted.split(":")[0]) for n in names
    ):
        # Accept exact tag or any tag of the same family when user passed untagged name.
        if wanted in names or any(n == wanted or n.startswith(wanted + ":") for n in names):
            return

    if not shutil.which("ollama"):
        raise SystemExit(
            f"Vision model '{wanted}' is not installed and `ollama` CLI was not found.\n"
            f"Install Ollama, then: ollama pull {wanted}"
        )
    print(f"  pulling vision model {wanted} via ollama (one-time) …", flush=True)
    result = subprocess.run(["ollama", "pull", wanted], check=False)
    if result.returncode != 0:
        raise SystemExit(f"Failed to pull vision model '{wanted}' (exit {result.returncode}).")


def unload_vision_model(model: str, host: str = DEFAULT_OLLAMA_HOST) -> None:
    """Ask Ollama to drop the model from memory."""
    body = json.dumps({"model": model, "keep_alive": 0}).encode()
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except Exception:
        pass


def _png_for_vision(png_bytes: bytes, *, size: int = 256) -> bytes:
    """Composite black lines onto white and upscale — VLMs struggle with transparency."""
    with Image.open(io.BytesIO(png_bytes)) as src:
        rgba = src.convert("RGBA")
        rgba = rgba.resize((size, size), Image.Resampling.NEAREST)
        canvas = Image.new("RGB", (size, size), (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("vision model returned no JSON object")
    return json.loads(match.group(0))


def _chat(
    *,
    model: str,
    host: str,
    prompt: str,
    image_png: bytes,
    temperature: float = 0.1,
) -> str:
    body = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature},
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image_png).decode("ascii")],
            }
        ],
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable: {exc}") from exc

    message = payload.get("message") or {}
    content = message.get("content") or payload.get("response") or ""
    if not str(content).strip():
        raise RuntimeError("vision model returned empty content")
    return str(content).strip()


def _match_words(animal_id: str) -> tuple[str, ...]:
    words = [animal_id.lower().replace("_", " "), animal_id.lower().replace("_", "")]
    words.extend(_ALIASES.get(animal_id, ()))
    # Singular/plural soft match
    if animal_id.endswith("y"):
        words.append(animal_id[:-1] + "ies")
    else:
        words.append(animal_id + "s")
    return tuple(dict.fromkeys(w for w in words if w))


def _keyword_hit(animal_id: str, caption: str) -> bool:
    text = caption.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in _match_words(animal_id))


def verify_animal(
    png_bytes: bytes,
    *,
    animal_id: str,
    look: str,
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
) -> VisionVerdict:
    """Blind-caption then JSON-judge; unload the VLM when finished."""
    image = _png_for_vision(png_bytes)
    seen = ""
    try:
        print(f"  vision: describe with {model} …", flush=True)
        blind = _chat(
            model=model,
            host=host,
            image_png=image,
            prompt=(
                "This is a simple black line drawing on a white background. "
                "What animal (or creature) is it? Reply with one short phrase only — "
                "the animal name. If it is not recognisable as an animal, say so."
            ),
        )
        seen = blind.strip().strip("\"'")
        print(f"  vision saw: {seen}", flush=True)

        if not _keyword_hit(animal_id, seen):
            return VisionVerdict(
                ok=False,
                seen=seen,
                reason=f"caption does not look like a {animal_id}",
                fix=(
                    f"Draw a clear simple black outline of a {animal_id}. {look} "
                    f"Make the species unmistakable."
                ),
            )

        print("  vision: checklist judge …", flush=True)
        raw = _chat(
            model=model,
            host=host,
            image_png=image,
            prompt=(
                f"Judge this simple black line-drawing icon.\n"
                f"Target animal: {animal_id}\n"
                f"Expected look: {look}\n\n"
                "Requirements:\n"
                "- It must clearly be that animal (not a different species).\n"
                "- It must be a hollow outline / doodle (thin black strokes with "
                "empty white interior). Reject solid black silhouettes, filled "
                "blobs, and photos.\n"
                "- One subject only, readable when small.\n\n"
                "Reply with ONLY a JSON object:\n"
                '{"ok": true/false, "animal": "<what you see>", '
                '"is_line_drawing": true/false, "reason": "<short>", '
                '"fix": "<positive instruction to fix if not ok, else empty>"}'
            ),
        )
        data = _extract_json(raw)
        ok = bool(data.get("ok")) and bool(data.get("is_line_drawing", True))
        animal_seen = str(data.get("animal") or seen).strip()
        reason = str(data.get("reason") or "").strip()
        fix = str(data.get("fix") or "").strip()
        if ok and not _keyword_hit(animal_id, animal_seen):
            ok = False
            reason = reason or f"judge labelled it '{animal_seen}', not {animal_id}"
            fix = fix or (
                f"Draw a clear simple black outline of a {animal_id}. {look}"
            )
        verdict = VisionVerdict(
            ok=ok,
            seen=animal_seen,
            reason=reason,
            fix=fix,
        )
        print(f"  {verdict.summary()}", flush=True)
        return verdict
    except Exception as exc:
        print(f"  vision QA failed: {exc}", file=sys.stderr)
        return VisionVerdict(ok=False, seen=seen, error=str(exc))
    finally:
        print("  vision: unloading Ollama model …", flush=True)
        unload_vision_model(model, host)
        print("  vision: unload done", flush=True)
