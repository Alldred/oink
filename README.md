# Oink

Full-screen e-ink dashboard for a jailbroken Kindle. GitHub Actions generates a PNG, publishes it to GitHub Pages, and a KUAL extension downloads and paints it with `eips`.
Vibecoded.

Target: Kindle Basic 7th gen (WP63GW), 600×800, firmware 5.12.x, KUAL required.

## Generate locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/generate_dashboard.py
```

Writes `public/dashboard.png` with today's date and Thornbury weather (Open-Meteo). Optional: `--timezone Europe/London`.

Stress-test with synthetic data (no network):

```sh
python src/generate_dashboard.py --test
python src/generate_dashboard.py --test calm
python src/generate_dashboard.py --test mixed
```

Fixtures: `stress` (UV 11, late heavy rain), `calm`, `mixed`. Writes `public/dashboard-<fixture>.png` by default.

## Publish

1. Push to GitHub.
2. **Settings → Pages → Source: GitHub Actions**.
3. Deploy the Cloudflare scheduler in [`cloudflare-scheduler/`](cloudflare-scheduler/) so builds run on a reliable ~15-minute cron (GitHub’s own `schedule` trigger is best-effort and often skips). Or run **Build and publish dashboard** manually via Actions → **Run workflow**.
4. Image URL: `https://YOUR_USER.github.io/oink/dashboard.png`

Full scheduler setup (token permissions, Wrangler, secrets, testing): [`cloudflare-scheduler/README.md`](cloudflare-scheduler/README.md).

## Kindle

1. Copy `kindle/extensions/oink/` to the Kindle as `extensions/oink/`.
2. Set `DASHBOARD_URL` in `extensions/oink/config.sh`.
3. **KUAL → Oink → Start Oink**.

Brand artwork lives in [`assets/`](assets/) (`logo.png`, splash source). Regenerate the on-device splash with `python src/generate_splash.py`.

KUAL menu: Start / Refresh now / Stop. Logs: `extensions/oink/logs/oink.log`. Details: [`kindle/extensions/oink/README.md`](kindle/extensions/oink/README.md).

Keep the Kindle on USB power for always-on use. Stop restores screensaver behaviour; uninstall by deleting `extensions/oink/`.

## Add a widget

Subclass `Widget` in `src/widgets/`, export it, place it in `build_default_layout()` in `src/layout.py`.

## Licence

MIT — see [`LICENSE`](LICENSE). Nunito (SIL OFL) and DejaVu fonts under `fonts/` keep their upstream licences.
