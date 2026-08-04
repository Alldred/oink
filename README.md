# Oink

Full-screen e-ink dashboard for a jailbroken Kindle. GitHub Actions generates a PNG, publishes it to GitHub Pages, and a KUAL extension downloads and paints it with `eips`.

Target: Kindle Basic 7th gen (WP63GW), 600×800, firmware 5.12.x, KUAL required.

## Generate locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/generate_dashboard.py
```

Writes `public/dashboard.png`. Optional: `--timezone Europe/London`.

## Publish

1. Push to GitHub.
2. **Settings → Pages → Source: GitHub Actions**.
3. Run **Build and publish dashboard** (or wait for the 30-minute schedule).
4. Image URL: `https://YOUR_USER.github.io/oink/dashboard.png`

## Kindle

1. Copy `kindle/extensions/oink/` to the Kindle as `extensions/oink/`.
2. Set `DASHBOARD_URL` in `extensions/oink/config.sh`.
3. **KUAL → Oink → Start Oink**.

KUAL menu: Start / Refresh now / Stop. Logs: `extensions/oink/logs/oink.log`. Details: [`kindle/extensions/oink/README.md`](kindle/extensions/oink/README.md).

Keep the Kindle on USB power for always-on use. Stop restores screensaver behaviour; uninstall by deleting `extensions/oink/`.

## Add a widget

Subclass `Widget` in `src/widgets/`, export it, place it in `build_default_layout()` in `src/layout.py`.

## Licence

MIT — see [`LICENSE`](LICENSE). DejaVu fonts under `fonts/` keep their upstream licence.
