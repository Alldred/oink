# Brand / source artwork

| File | Purpose |
| --- | --- |
| `logo.png` | Oink wordmark (source). Use in docs, README, future widgets. |
| `splash-source.png` | Full-resolution splash design. |
| `animals/*.png` | Daily header doodles: **128×128** RGBA, pure black strokes on transparent. One is picked at random per day for the dashboard header. |

Generate animals locally (Apple Silicon + mflux):

```sh
cd line-animals
uv sync --extra local
uv run generate.py --only duck fox --interactive
uv run generate.py --all --overwrite
```

Device runtime art is generated into `kindle/extensions/oink/`:

```sh
python src/generate_splash.py
```

That writes a **600×800 8-bit grayscale** `splash.png` for Kindle Basic (WP63GW).
