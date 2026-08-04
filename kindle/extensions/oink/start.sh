#!/bin/sh
# Start Oink: keep the Kindle awake and refresh the dashboard in a loop.
#
# Usage (from KUAL or SSH):
#   ./start.sh
#
# The first invocation detaches a background daemon. A second Start while
# already running is a no-op (duplicate protection).

set -e

OINK_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

# Detach from KUAL so the menu can exit cleanly.
if [ "$1" != "--daemon" ]; then
    if is_running; then
        log "Start requested but Oink is already running (pid $(cat "$PID_FILE"))"
        exit 0
    fi
    log "Launching Oink daemon"
    # Use nohup when available; fall back to plain background.
    if command -v nohup >/dev/null 2>&1; then
        nohup /bin/sh "$OINK_DIR/start.sh" --daemon >/dev/null 2>&1 &
    else
        /bin/sh "$OINK_DIR/start.sh" --daemon >/dev/null 2>&1 &
    fi
    exit 0
fi

# --- daemon ---
load_config || exit 1

if is_running; then
    _existing="$(cat "$PID_FILE")"
    if [ "$_existing" != "$$" ]; then
        log "Daemon not starting; already running as pid $_existing"
        exit 0
    fi
fi

write_pid
prevent_screensaver
log "Oink started (pid $$, refresh=${REFRESH_SECONDS}s, url=$DASHBOARD_URL)"

# Initial fetch + display. If download fails, keep trying — do not wipe a
# previously cached image.
if download_dashboard; then
    _full="$(next_full_refresh_flag)"
    display_dashboard "$_full" || true
else
    log "Initial download failed; displaying cached image if present"
    if [ -f "$DASHBOARD_FILE" ]; then
        display_dashboard 1 || true
    else
        # VERIFIED: eips can also print short status text as a fallback.
        eips 2 2 "Oink: waiting for network" 2>>"$LOG_FILE" || true
    fi
fi

while true; do
    sleep "$REFRESH_SECONDS" || sleep 1800

    # Re-assert keep-awake in case something cleared it.
    prevent_screensaver

    if download_dashboard; then
        _full="$(next_full_refresh_flag)"
        display_dashboard "$_full" || true
    else
        log "Refresh failed; keeping previous dashboard on screen"
        # Still repaint the cached image occasionally so the Kindle UI does
        # not permanently cover it after a sleep/wake or UI redraw.
        if [ -f "$DASHBOARD_FILE" ]; then
            display_dashboard 0 || true
        fi
    fi
done
