#!/bin/sh
# Refresh the Oink dashboard once (download + display).
#
# Usage:
#   /bin/sh /mnt/us/extensions/oink/update.sh

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

prevent_screensaver
log "Manual refresh requested"
show_status "Oink refreshing..."

if download_dashboard; then
    _full="$(next_full_refresh_flag)"
    display_dashboard "$_full"
    # Brief pause then re-paint in case Home/UI redraws after KUAL exits.
    sleep 2
    display_dashboard 1 || true
    exit 0
fi

log "Manual refresh download failed; re-displaying cache if available"
if [ -f "$DASHBOARD_FILE" ]; then
    display_dashboard 1 || true
    sleep 2
    display_dashboard 1 || true
    exit 1
fi

show_status "Oink: download failed"
sleep 3
exit 1
