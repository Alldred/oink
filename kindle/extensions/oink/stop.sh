#!/bin/sh
# Stop Oink and restore the Kindle UI.
# Intentionally no ``set -e``: Stop must always clear PID / resume UI even if
# one step fails (same approach as start.sh).

case "$0" in
    /*) _script="$0" ;;
    *) _script="$(pwd)/$0" ;;
esac
OINK_DIR="$(CDPATH= cd -- "$(dirname "$_script")" && pwd)"
# shellcheck disable=SC1091
. "$OINK_DIR/common.sh"

log "Stop requested"

if [ -f "$PID_FILE" ]; then
    _pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$_pid" ]; then
        log "Sending TERM to pid $_pid"
        kill "$_pid" 2>/dev/null || true
        _i=0
        while [ "$_i" -lt 10 ]; do
            if ! kill -0 "$_pid" 2>/dev/null; then
                break
            fi
            _i=$((_i + 1))
            sleep 1
        done
        if kill -0 "$_pid" 2>/dev/null; then
            log "Process still alive; sending KILL to pid $_pid"
            kill -9 "$_pid" 2>/dev/null || true
        fi
    fi
fi

remove_pid
resume_kindle_ui || log "WARN: resume_kindle_ui reported failure"

# Framework start should bring Home back; clear any stale eips frame first.
eips -c 2>>"$LOG_FILE" || /usr/sbin/eips -c 2>>"$LOG_FILE" || true
sleep 1
return_to_kindle_home || true

log "Oink stopped"
exit 0
