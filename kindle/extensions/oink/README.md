# Oink KUAL extension

Kindle-side client for the Oink e-ink dashboard.

Target device: **Kindle Basic, 7th generation (WP63GW), firmware 5.12.2.2**, with a jailbreak and KUAL installed.

## Install

1. Connect the Kindle over USB.
2. Copy this entire `oink` folder to:

   ```text
   /mnt/us/extensions/oink/
   ```

   On the USB mount that usually appears as:

   ```text
   extensions/oink/
   ```

3. Edit `config.sh` and set your GitHub Pages URL:

   ```sh
   DASHBOARD_URL="https://YOUR_GITHUB_USERNAME.github.io/oink/dashboard.png"
   REFRESH_SECONDS=300
   ```

4. Eject the Kindle safely.
5. Open **KUAL** → **Oink**.

## Menu

| Item | Action |
| --- | --- |
| **Start Oink** | Start the background refresh loop, keep the device awake, download + display |
| **Refresh now** | Download and display immediately (also works while Start is running) |
| **Stop Oink** | Kill the loop, re-enable the screensaver, clear the painted image, return home |

**Start returns to Home by design** (KUAL `exitmenu`). The home booklet can redraw over a too-early `eips` paint, so the daemon waits ~3s after Start and paints again. If you only ever see Home, check `logs/oink.log` and confirm `config.sh` has a working PNG URL.

Polls Pages every **5 minutes** by default (`REFRESH_SECONDS`) so a delayed GitHub Actions publish does not leave a long gap. After each paint, Oink overlays the device clock (`HH:MM`) in the upper left via `eips` text (`CLOCK_OVERLAY=1`). Interim re-paints redraw it too, so the clock stays visible and updates about once a minute.

Copy the updated `extensions/oink/` folder onto the Kindle (or at least `config.sh`, `common.sh`, `start.sh`, `update.sh`) and **Stop → Start** for the new loop to take effect.

## Files

| Path | Purpose |
| --- | --- |
| `config.xml` / `menu.json` | KUAL extension metadata |
| `config.sh` | URL + refresh interval |
| `common.sh` | Shared helpers (download, validate, display, keep-awake) |
| `start.sh` | Background loop |
| `update.sh` | One-shot refresh |
| `stop.sh` | Clean shutdown |
| `cache/dashboard.png` | Last good image (created at runtime) |
| `logs/oink.log` | Runtime log (created at runtime) |
| `oink.pid` | Daemon PID file (created at runtime) |

## How the image is displayed

Oink paints the PNG with the stock Kindle utility **`eips`**:

```sh
eips -g /mnt/us/extensions/oink/cache/dashboard.png
eips -f -g /mnt/us/extensions/oink/cache/dashboard.png   # full refresh
```

This is documented on the [MobileRead Eips wiki](https://wiki.mobileread.com/wiki/Eips) and is the standard approach used by other Kindle dashboard projects on firmware 5.x.

**Oink does not open the web browser.** The Kindle downloads a PNG over Wi-Fi and paints it directly to the framebuffer.

### Verified vs assumed commands

See comments at the top of `common.sh`. In short:

- **Verified:** `eips -g`, `eips -f -g`, `eips -c`, `lipc-set-prop com.lab126.powerd preventScreenSaver`
- **Assumed on this device:** `wget` on `PATH`, optional `appmgrd` home booklet launch on Stop

Confirm framebuffer size once over SSH:

```sh
eips -i
```

You should see a 600×800 panel on WP63GW.

## Keep-awake / screensaver

While running, Oink sets:

```sh
lipc-set-prop com.lab126.powerd preventScreenSaver 1
```

On Stop it sets the property back to `0`. This is a **runtime, reversible** setting — no permanent system modification.

Oink intentionally **does not** stop `/etc/init.d/framework`. Leaving the framework running makes Stop safer (no reboot required). The trade-off is that the Kindle UI can occasionally redraw over the dashboard; the refresh loop re-paints the cached image.

### Optional screensaver packages

If you later want the dashboard as a *true* Kindle screensaver (shown when the device sleeps) rather than an always-on loop, community packages such as **linkss / Online Screensaver** are an alternative architecture. They are **not required** for Oink and are a different design. Prefer Oink’s keep-awake loop when the Kindle stays on power.

## Logging

Log file:

```text
/mnt/us/extensions/oink/logs/oink.log
```

Over USB:

```text
extensions/oink/logs/oink.log
```

## Verify the daemon

Over SSH (USBNetwork):

```sh
cat /mnt/us/extensions/oink/oink.pid
ps | grep oink
kill -0 "$(cat /mnt/us/extensions/oink/oink.pid)" && echo running
```

## Stop over USB if KUAL is unavailable

1. Connect USB and open the Kindle drive.
2. Create an empty file named `STOP` inside `extensions/oink/` **or** (preferred) use SSH:

   ```sh
   sh /mnt/us/extensions/oink/stop.sh
   ```

3. If SSH is unavailable, reboot the Kindle. Because Oink does not modify the root filesystem or disable the framework permanently, a reboot returns you to a normal Kindle. You may still want to delete `oink.pid` and clear `preventScreenSaver` after reboot:

   ```sh
   rm -f /mnt/us/extensions/oink/oink.pid
   lipc-set-prop com.lab126.powerd preventScreenSaver 0
   ```

## Uninstall

1. Stop Oink from KUAL (or via `stop.sh`).
2. Delete `/mnt/us/extensions/oink/` (the whole folder).
3. No reboot is required.

## Safety

- All Oink files live under `/mnt/us` (userstore).
- No `mntroot rw`, no cron under `/etc`, no framework stop.
- Failed downloads never replace the last good PNG (HTML error pages are rejected).
