#!/bin/sh
# Start Oink: suspend the Kindle UI, keep awake, refresh the dashboard loop.
#
# Usage:
#   /bin/sh /mnt/us/extensions/oink/start.sh

set -e

case "$0" in
    /*) _script="$0" ;;
    *) _script="$(pwd)/$0" ;;
esac
OINK_DIR="$(CDPATH= cd -- "$(dirname "$_script")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

show_status() {
    eips 1 1 "$1" 2>/dev/null || /usr/sbin/eips 1 1 "$1" 2>/dev/null || true
}

launch_daemon() {
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
log "Oink started (pid $$, refresh=${REFRESH_SECONDS}s, repaint=${REPAINT_SECONDS}s, url=$DASHBOARD_URL)"

# Let KUAL exit and Home draw once, then take the UI down so it cannot cover us.
sleep 2
suspend_kindle_ui

_paint_once() {
    if download_dashboard; then
        display_dashboard 1 || true
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

_paint_once || true

_elapsed=0
while true; do
    sleep "$REPAINT_SECONDS" || sleep 60
    _elapsed=$((_elapsed + REPAINT_SECONDS))

    prevent_screensaver

    if [ "$_elapsed" -ge "$REFRESH_SECONDS" ]; then
        _elapsed=0
        if download_dashboard; then
            _full="$(next_full_refresh_flag)"
            display_dashboard "$_full" || true
        else
            log "Refresh failed; re-painting cache"
            if [ -f "$DASHBOARD_FILE" ]; then
                display_dashboard 0 || true
            fi
        fi
    else
        # Re-paint cache so any unexpected UI flash is overwritten quickly.
        if [ -f "$DASHBOARD_FILE" ]; then
            display_dashboard 0 || true
        fi
    fi
done
