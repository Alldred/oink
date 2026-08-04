#!/bin/sh
# Refresh the Oink dashboard once (download + display).

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

if ! load_config; then
    show_status "Oink: edit config.sh URL"
    sleep 3
    exit 1
fi

log "Manual refresh requested"
show_status "Oink refreshing..."

# If the daemon is not running, briefly suspend UI so the paint is visible.
# Prefer Start Oink for a lasting display.
_started_ui=0
if ! is_running; then
    suspend_kindle_ui
    _started_ui=1
fi

if download_dashboard; then
    _full="$(next_full_refresh_flag)"
    display_dashboard "$_full"
else
    log "Manual refresh download failed; re-displaying cache if available"
    if [ -f "$DASHBOARD_FILE" ]; then
        display_dashboard 1 || true
    else
        show_status "Oink: download failed"
        sleep 2
    fi
fi

if [ "$_started_ui" -eq 1 ]; then
    show_status "Use Start to keep it"
    sleep 2
    if [ -f "$DASHBOARD_FILE" ]; then
        display_dashboard 1 || true
    fi
fi

exit 0
