#!/bin/sh
# Start Oink: keep the Kindle awake and refresh the dashboard in a loop.
#
# Usage (from KUAL or SSH):
#   /bin/sh /mnt/us/extensions/oink/start.sh
#
# Important: KUAL "Start Oink" uses exitmenu=true, so the Kindle home booklet
# redraws AFTER this script returns. The daemon therefore waits briefly and
# paints again so the dashboard is not covered by the home screen.

set -e

# Resolve extension dir from this script's path (works when launched via
# /bin/sh /mnt/us/extensions/oink/start.sh).
case "$0" in
    /*) _script="$0" ;;
    *) _script="$(pwd)/$0" ;;
esac
OINK_DIR="$(CDPATH= cd -- "$(dirname "$_script")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

show_status() {
    # VERIFIED: eips can print short text strings.
    eips 1 1 "$1" 2>/dev/null || /usr/sbin/eips 1 1 "$1" 2>/dev/null || true
}

launch_daemon() {
    # Ignore hangup so KUAL exiting does not kill the loop.
    trap '' HUP

    if command -v setsid >/dev/null 2>&1; then
        setsid /bin/sh "$OINK_DIR/start.sh" --daemon </dev/null >/dev/null 2>&1 &
    elif command -v nohup >/dev/null 2>&1; then
        nohup /bin/sh "$OINK_DIR/start.sh" --daemon </dev/null >/dev/null 2>&1 &
    else
        /bin/sh "$OINK_DIR/start.sh" --daemon </dev/null >/dev/null 2>&1 &
    fi
}

# --- launcher (runs under KUAL) ---
if [ "$1" != "--daemon" ]; then
    if is_running; then
        log "Start requested but Oink is already running (pid $(cat "$PID_FILE"))"
        # Re-paint so the user sees the dashboard even if Home covered it.
        if [ -f "$DASHBOARD_FILE" ]; then
            display_dashboard 1 || true
        fi
        show_status "Oink already running"
        sleep 1
        exit 0
    fi

    if ! load_config; then
        show_status "Oink: edit config.sh URL"
        sleep 3
        exit 1
    fi

    show_status "Oink starting..."
    log "Launching Oink daemon"
    launch_daemon
    # Give the daemon a moment to write its PID before KUAL tears down.
    sleep 1
    exit 0
fi

# --- daemon ---
trap '' HUP

if ! load_config; then
    show_status "Oink: bad config"
    exit 1
fi

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

# Wait for KUAL to exit and the home booklet to finish redrawing, otherwise
# Home covers the first eips paint.
sleep 3

_paint_once() {
    if download_dashboard; then
        _full="$(next_full_refresh_flag)"
        display_dashboard "$_full" || true
        return 0
    fi

    log "Download failed; displaying cached image if present"
    if [ -f "$DASHBOARD_FILE" ]; then
        display_dashboard 1 || true
        return 0
    fi

    show_status "Oink: download failed"
    return 1
}

# Paint twice up front: once after Home settles, once more in case UI redraws.
_paint_once || true
sleep 2
if [ -f "$DASHBOARD_FILE" ]; then
    display_dashboard 1 || true
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
        if [ -f "$DASHBOARD_FILE" ]; then
            display_dashboard 0 || true
        fi
    fi
done
