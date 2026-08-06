# Line animals

Local mflux generator for Oink's daily header doodles: simple black line drawings
on transparent PNGs (128×128), for e-ink.

Requires Apple Silicon + [mflux](https://github.com/filipstrand/mflux).

## Setup

```bash
cd line-animals
uv sync --extra local
```

Model weights download from Hugging Face on first use. Put a read token in `.env`
(copy from `.env.example`) to avoid rate limits:

```bash
HF_TOKEN=hf_...
```

## Usage

```bash
uv run generate.py --list
uv run generate.py --interactive
uv run generate.py --only duck fox --interactive
uv run generate.py --all --overwrite
```

Accepted art → `../assets/animals/<id>.png`.

Vision QA runs **by default** via local Ollama (`qwen2.5vl:3b`): the image is
captioned and checked against the animal look. Use `--no-verify` to skip.

```bash
ollama serve          # if not already running
ollama pull qwen2.5vl:3b
```

| Flag | Meaning |
|------|---------|
| `--list` | Show catalog ids |
| `--interactive` | Full catalog with preview; accept / retry / edit |
| `--only …` | Generate these ids only |
| `--all` | Full catalog (no prompts; write immediately) |
| `--audit` | Vision-check existing art; keep OK, regen failures/missing |
| `--overwrite` | Replace existing files |
| `--no-verify` | Skip Ollama vision QA |
| `--vision-model` | Default `qwen2.5vl:3b` |
| `--dry-run` | Print prompts only |
| `--model` | Diffusion model (default `flux2-klein-4b`) |

Prompts ask for hollow black outlines on a magenta chroma screen; post-process keys
the backdrop and thresholds to pure black ink.
