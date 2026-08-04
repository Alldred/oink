#!/bin/sh
# Refresh the Oink dashboard once (download + display).
#
# Usage:
#   ./update.sh           # used by KUAL "Refresh now"
#   ./update.sh --once    # same behaviour; accepted for menu.json params

set -e

OINK_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

load_config || exit 1
prevent_screensaver

log "Manual refresh requested"

if download_dashboard; then
    _full="$(next_full_refresh_flag)"
    display_dashboard "$_full"
    exit $?
fi

log "Manual refresh download failed; re-displaying cache if available"
if [ -f "$DASHBOARD_FILE" ]; then
    display_dashboard 1 || true
    exit 1
fi

eips 2 2 "Oink: download failed" 2>>"$LOG_FILE" || true
exit 1
