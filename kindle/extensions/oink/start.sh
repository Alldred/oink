#!/bin/sh
# Start Oink: suspend the Kindle UI, keep awake, refresh the dashboard loop.
#
# Usage:
#   /bin/sh /mnt/us/extensions/oink/start.sh

case "$0" in
    /*) _script="$0" ;;
    *) _script="$(pwd)/$0" ;;
esac
OINK_DIR="$(CDPATH= cd -- "$(dirname "$_script")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

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
        else
            show_splash
        fi
        sleep 1
        exit 0
    fi

    if ! load_config; then
        show_status "Oink: edit config.sh URL"
        sleep 3
        exit 1
    fi

    show_splash
    log "Launching Oink daemon"
    launch_daemon
    sleep 1
    exit 0
fi

# --- daemon ---
# Do not use set -e here: a single failed lipc/wget/eips must not kill the loop.
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
show_splash
# Brief pause so the splash is actually visible on e-ink before we replace it.
sleep 1

# Leave the splash with a full refresh onto the last-good dashboard (if any),
# so startup never sits on splash through a slow/failed download, and splash
# ink is fully cleared rather than ghosting under a partial paint.
_have_cache=0
if [ -f "$DASHBOARD_FILE" ]; then
    log "Full refresh from cache after splash"
    display_dashboard 1 || true
    _have_cache=1
fi

_dl="$(download_dashboard)"
case "$_dl" in
    new)
        log "Initial download: new image"
        display_dashboard 1 || true
        ;;
    same)
        log "Initial download: unchanged"
        # Already full-refreshed from cache above; if this is a first-ever
        # install with no prior cache path, paint now.
        if [ "$_have_cache" -eq 0 ]; then
            display_dashboard 1 || true
        fi
        ;;
    *)
        log "Initial download failed; keeping post-splash image if present"
        if [ "$_have_cache" -eq 0 ]; then
            if [ -f "$DASHBOARD_FILE" ]; then
                display_dashboard 1 || true
            else
                show_status "Oink: download failed"
            fi
        fi
        ;;
esac

_elapsed=0
_since_paint=0
# Poll often enough that plugging into a computer stops Oink quickly, without
# re-painting the e-ink every few seconds.
_POLL_SECONDS=5
while true; do
    sleep "$_POLL_SECONDS" || sleep 5
    _elapsed=$((_elapsed + _POLL_SECONDS))
    _since_paint=$((_since_paint + _POLL_SECONDS))

    _stop_reason="$(should_self_stop || true)"
    if [ -n "$_stop_reason" ]; then
        self_stop "$_stop_reason"
    fi

    if [ "$_since_paint" -lt "$REPAINT_SECONDS" ]; then
        continue
    fi
    _since_paint=0

    prevent_screensaver || true

    if [ "$_elapsed" -ge "$REFRESH_SECONDS" ]; then
        _elapsed=0
        log "Refresh tick"
        _dl="$(download_dashboard)"
        case "$_dl" in
            new)
                _full="$(next_full_refresh_flag || echo 1)"
                display_dashboard "$_full" || true
                ;;
            same)
                log "Remote unchanged; re-painting cache"
                display_dashboard 0 || true
                ;;
            *)
                log "Refresh failed; re-painting cache"
                if [ -f "$DASHBOARD_FILE" ]; then
                    display_dashboard 0 || true
                fi
                ;;
        esac
    else
        # Re-paint cache so any unexpected UI flash is overwritten quickly.
        if [ -f "$DASHBOARD_FILE" ]; then
            display_dashboard 0 || true
        fi
    fi
done
