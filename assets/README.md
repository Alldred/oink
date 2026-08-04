# Brand / source artwork

| File | Purpose |
| --- | --- |
| `logo.png` | Oink wordmark (source). Use in docs, README, future widgets. |
| `splash-source.png` | Full-resolution splash design. |

Device runtime art is generated into `kindle/extensions/oink/`:

```sh
python src/generate_splash.py
```

That writes a **600×800 8-bit grayscale** `splash.png` for Kindle Basic (WP63GW).
