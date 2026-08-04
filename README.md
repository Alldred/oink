# Oink

Turn a jailbroken Kindle into a full-screen e-ink dashboard — no local server required.

Oink generates a Kindle-sized PNG on GitHub Actions, publishes it to GitHub Pages, and a small KUAL extension on the Kindle downloads and paints that image with the stock `eips` tool.

```text
GitHub Actions  →  public/dashboard.png  →  GitHub Pages
                                              ↓ Wi-Fi
                                    Kindle KUAL extension
                                              ↓
                                         eips -g  (full-screen)
```

## Hardware target

| Item | Value |
| --- | --- |
| Device | Kindle Basic, 7th generation |
| Model | WP63GW |
| Firmware | 5.12.2.2 (tested design target) |
| Jailbreak | Required |
| Launcher | KUAL |
| Resolution | **600 × 800** |
| Display | Monochrome e-ink |
| Network | Wi-Fi |

Other Kindles can work if you change the canvas size in `src/layout.py` and confirm `eips -i` on the device. Older 5.x firmware with `eips` and `lipc` is the intended compatibility range.

## Design goals

- Lightweight — Python + Pillow only on the generator side; plain shell on the Kindle
- Well documented, modular widgets, easy to extend
- Compatible with older Kindles (no Node, no Docker, no on-device browser UI)
- No local server — GitHub Actions + GitHub Pages are the backend

## Repository layout

```text
oink/
├── src/
│   ├── widgets/
│   │   ├── base.py          # Widget + Rect helpers
│   │   ├── clock.py         # Date + time
│   │   └── message.py       # Status text
│   ├── layout.py            # 600×800 layout
│   ├── renderer.py          # Compose widgets → PNG
│   └── generate_dashboard.py
├── public/
│   └── dashboard.png        # Published artefact
├── kindle/extensions/oink/  # KUAL extension
├── fonts/                   # Bundled DejaVu Sans
├── .github/workflows/
│   └── build-dashboard.yml
├── requirements.txt
└── README.md
```

## How full-screen display works (important)

Oink does **not** use the Kindle web browser.

On firmware 5.x the stock utility **`eips`** can paint a PNG to the framebuffer:

```sh
eips -g /path/to/dashboard.png      # partial refresh
eips -f -g /path/to/dashboard.png   # full refresh (less ghosting)
```

This is documented on the [MobileRead Eips wiki](https://wiki.mobileread.com/wiki/Eips) and matches what other Kindle dashboard projects use. Image guidance used by Oink:

- Exact device resolution: **600 × 800** for WP63GW
- **8-bit grayscale** PNG (`Pillow` mode `L`)
- White background, large fonts, comfortable margins

### Verified vs assumed Kindle commands

| Command | Status |
| --- | --- |
| `eips -g`, `eips -f -g`, `eips -c`, `eips -i` | **Verified** (MobileRead docs + widespread 5.x use) |
| `lipc-set-prop com.lab126.powerd preventScreenSaver 0\|1` | **Verified** pattern for reversible keep-awake |
| `lipc-get-prop com.lab126.wifid cmState` | **Verified** Wi-Fi state check |
| Drawing with `eips` *without* stopping the framework on 5.12.2.2 | **Reported** workable; Oink adopts this for safer Stop |
| `wget` on `PATH` | **Assumed** — confirm on your device (`command -v wget`) |
| `lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home` | **Assumed** best-effort Home return; physical Home still works |

Oink never runs `mntroot rw`, never edits `/etc`, and never stops the Kindle framework. That keeps uninstall and recovery simple.

## Quick start

### 1. Fork / clone and generate locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/generate_dashboard.py
```

Output: `public/dashboard.png` (600×800 grayscale).

Optional flags:

```sh
python src/generate_dashboard.py --timezone Europe/London --output public/dashboard.png
```

### 2. Publish with GitHub Pages

1. Push this repository to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Run the workflow **Build and publish dashboard** (Actions tab → Run workflow), or wait for the 30-minute schedule.
4. Confirm the image URL loads in a browser:

   ```text
   https://YOUR_GITHUB_USERNAME.github.io/oink/dashboard.png
   ```

The workflow lives at `.github/workflows/build-dashboard.yml`. It:

- Runs on `workflow_dispatch` and every 30 minutes
- Uses Python 3.12 + Pillow
- Uploads `public/` with `actions/upload-pages-artifact`
- Deploys with `actions/deploy-pages`
- Requests `pages: write` and `id-token: write`

The clock on the image is the **generation time** in `Europe/London` by default (change the workflow `--timezone` argument if needed).

### 3. Install the KUAL extension

1. Copy `kindle/extensions/oink/` to the Kindle as `extensions/oink/`.
2. Edit `extensions/oink/config.sh`:

   ```sh
   DASHBOARD_URL="https://YOUR_GITHUB_USERNAME.github.io/oink/dashboard.png"
   REFRESH_SECONDS=1800
   ```

3. Open **KUAL → Oink → Start Oink**.

Details, logging, and recovery: [`kindle/extensions/oink/README.md`](kindle/extensions/oink/README.md).

## Running Oink on the Kindle

| KUAL item | Behaviour |
| --- | --- |
| **Start Oink** | Prevents duplicates, records a PID, keeps the device awake, downloads the PNG, paints it full-screen, refreshes on an interval |
| **Refresh now** | One-shot download + display |
| **Stop Oink** | Stops the loop, removes the PID file, restores screensaver behaviour, clears the painted frame, returns toward the Kindle home UI |

While Start is active the Kindle should stay awake via:

```sh
lipc-set-prop com.lab126.powerd preventScreenSaver 1
```

Keep the device on USB power for always-on use.

### Screensaver note

Oink prefers **reversible runtime keep-awake** over permanent screensaver hacks. Community packages (linkss / Online Screensaver) are optional and implement a different “image as screensaver” model — they are **not required**.

## Widget architecture

Each widget receives a rectangle and draws into it:

```python
class Widget:
    def prepare(self, context): ...  # optional data fetch
    def draw(self, image, draw, context): ...
```

v1 layout (`src/layout.py`):

1. **ClockWidget** — current date + time (generation timestamp)
2. **MessageWidget** — `Oink is working!`

To add a widget later (weather, calendar, …):

1. Create `src/widgets/my_widget.py` subclassing `Widget`
2. Export it from `src/widgets/__init__.py`
3. Place it in `build_default_layout()` with a `Rect`

## Logging (Kindle)

```text
/mnt/us/extensions/oink/logs/oink.log
```

## Verify the background process

Over SSH:

```sh
cat /mnt/us/extensions/oink/oink.pid
kill -0 "$(cat /mnt/us/extensions/oink/oink.pid)" && echo running
ps | grep '[s]tart.sh'
```

## Uninstall

1. **KUAL → Oink → Stop Oink**
2. Delete `extensions/oink/` from the Kindle
3. Done — nothing was written outside that folder

## Recovery if the loop misbehaves

**Via KUAL:** Stop Oink.

**Via SSH:**

```sh
sh /mnt/us/extensions/oink/stop.sh
```

**Via USB without SSH:**

1. Reboot the Kindle (framework was never permanently disabled).
2. Optionally delete `extensions/oink/oink.pid`.
3. If the screensaver still seems suppressed after reboot, over SSH run:

   ```sh
   lipc-set-prop com.lab126.powerd preventScreenSaver 0
   ```

## Troubleshooting

### Wi-Fi failures

- Confirm the Kindle is connected (browser or `lipc-get-prop com.lab126.wifid cmState` → `CONNECTED`).
- Oink keeps the previous PNG if a download fails.
- Check `logs/oink.log` for `download failed` lines.

### HTML downloaded instead of PNG

GitHub Pages often returns an HTML 404 page. Oink validates the PNG magic header and rejects HTML. Fix:

1. Open the `DASHBOARD_URL` in a desktop browser — it must be a PNG.
2. Ensure Pages source is **GitHub Actions** and the workflow succeeded.
3. Confirm the path is `/oink/dashboard.png` for a project site named `oink`.

### Kindle sleeping

- Use **Start Oink** (sets `preventScreenSaver`).
- Keep USB power connected for long sessions.
- Re-run Start if something else cleared the property.

### Duplicate processes

Start refuses to launch a second daemon when `oink.pid` points at a live process. If a stale PID file remains after a crash:

```sh
rm -f /mnt/us/extensions/oink/oink.pid
```

Then Start again. Prefer Stop first when possible.

### Ghosting

- Oink periodically uses `eips -f -g` (see `FULL_REFRESH_EVERY` in `config.sh`).
- Set `FULL_REFRESH_EVERY=1` for a full flash every refresh.
- Ensure the PNG is true 8-bit grayscale at 600×800.

### Incorrect timezone

The clock is rendered in CI / locally — not on the Kindle. Change:

```yaml
# .github/workflows/build-dashboard.yml
python src/generate_dashboard.py --timezone Europe/London
```

or pass `--timezone` when generating locally. Use IANA names (`Europe/London`, `America/New_York`, …).

### Image not displaying

1. `eips -i` — confirm resolution.
2. Manually: `eips -f -g /mnt/us/extensions/oink/cache/dashboard.png`
3. Confirm the cached file is a real PNG (`wc -c` should be more than a few KB).
4. Confirm `wget` exists: `command -v wget`

## Roadmap (future widgets)

Structured so each item is an independent widget rectangle:

- [ ] Weather (Open-Meteo)
- [ ] Calendar
- [ ] RSS headlines
- [ ] Train departures
- [ ] Octopus Energy prices
- [ ] Quote of the day
- [ ] Daily photo
- [ ] Home Assistant sensors

## Licence

MIT — see [`LICENSE`](LICENSE).

DejaVu fonts under `fonts/` retain their upstream licence (`fonts/LICENSE`).
