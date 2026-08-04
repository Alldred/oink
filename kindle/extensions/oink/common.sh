#!/bin/sh
# Shared helpers for the Oink KUAL extension.
#
# ---------------------------------------------------------------------------
# Command status for Kindle Basic 7th gen (WP63GW), firmware 5.12.2.2
# ---------------------------------------------------------------------------
#
# VERIFIED (documented on MobileRead Wiki / widely used on 5.x firmware):
#   eips -g <png>          Display a PNG full-screen
#   eips -f -g <png>       Full waveform refresh (helps clear ghosting)
#   eips -c                Clear the screen
#   eips -i                Print framebuffer info (use to confirm resolution)
#   lipc-set-prop com.lab126.powerd preventScreenSaver 1
#   lipc-set-prop com.lab126.powerd preventScreenSaver 0
#   lipc-get-prop com.lab126.wifid cmState
#
# REPORTED on firmware 5.12.2.2 specifically (third-party write-ups):
#   Drawing with eips without stopping the Kindle framework works and makes
#   Stop / Home return much safer. Oink follows that approach.
#
# ASSUMED — verify once over SSH / USBNetwork on your device:
#   wget                   BusyBox wget is usually present after jailbreak
#   curl                   Often absent; used only as a fallback
#   lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home
#                          Best-effort return to the home booklet on Stop
#
# NOT used by Oink (intentionally):
#   /etc/init.d/framework stop   — harder to reverse; reboot often needed
#   mntroot rw / root edits      — Oink stays under /mnt/us only
# ---------------------------------------------------------------------------

# When sourced from start/update/stop, prefer the caller's OINK_DIR if set.
# Otherwise resolve from $0 (absolute or relative to cwd).
if [ -z "$OINK_DIR" ] || [ ! -d "$OINK_DIR" ]; then
    case "$0" in
        /*) _oink_script="$0" ;;
        *) _oink_script="$(pwd)/$0" ;;
    esac
    OINK_DIR="$(CDPATH= cd -- "$(dirname "$_oink_script")" && pwd)"
fi
CACHE_DIR="$OINK_DIR/cache"
LOG_DIR="$OINK_DIR/logs"
PID_FILE="$OINK_DIR/oink.pid"
DASHBOARD_FILE="$CACHE_DIR/dashboard.png"
TMP_FILE="$CACHE_DIR/dashboard.png.tmp"
LOG_FILE="$LOG_DIR/oink.log"
CONFIG_FILE="$OINK_DIR/config.sh"
REFRESH_COUNT_FILE="$CACHE_DIR/refresh_count"

export OINK_DIR CACHE_DIR LOG_DIR PID_FILE DASHBOARD_FILE TMP_FILE LOG_FILE CONFIG_FILE REFRESH_COUNT_FILE

mkdir -p "$CACHE_DIR" "$LOG_DIR"

log() {
    _ts="$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)"
    echo "$_ts $*" >> "$LOG_FILE"
}

log_console() {
    log "$@"
    echo "$_ts $*" >&2
}

load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_console "ERROR: missing config at $CONFIG_FILE"
        return 1
    fi
    # shellcheck disable=SC1090
    . "$CONFIG_FILE"

    if [ -z "$DASHBOARD_URL" ] || echo "$DASHBOARD_URL" | grep -q 'USERNAME'; then
        log_console "ERROR: set DASHBOARD_URL in config.sh to your Pages PNG URL"
        return 1
    fi

    if [ -z "$REFRESH_SECONDS" ]; then
        REFRESH_SECONDS=1800
    fi

    if [ -z "$FULL_REFRESH_EVERY" ]; then
        FULL_REFRESH_EVERY=6
    fi

    return 0
}

is_running() {
    if [ ! -f "$PID_FILE" ]; then
        return 1
    fi
    _pid="$(cat "$PID_FILE" 2>/dev/null)"
    if [ -z "$_pid" ]; then
        return 1
    fi
    if kill -0 "$_pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

write_pid() {
    echo "$$" > "$PID_FILE"
}

remove_pid() {
    rm -f "$PID_FILE"
}

prevent_screensaver() {
    # VERIFIED reversible keep-awake approach.
    if ! lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null; then
        lipc-set-prop -i com.lab126.powerd preventScreenSaver 1 2>/dev/null || \
            log "WARN: could not set preventScreenSaver=1"
    fi
}

allow_screensaver() {
    if ! lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null; then
        lipc-set-prop -i com.lab126.powerd preventScreenSaver 0 2>/dev/null || \
            log "WARN: could not set preventScreenSaver=0"
    fi
}

wait_for_wifi() {
    _tries=0
    _state="UNKNOWN"
    while [ "$_tries" -lt 30 ]; do
        _state="$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null || echo UNKNOWN)"
        if [ "$_state" = "CONNECTED" ]; then
            return 0
        fi
        _tries=$((_tries + 1))
        sleep 1
    done
    log "WARN: Wi-Fi not CONNECTED (state=$_state)"
    return 1
}

validate_png() {
    _file="$1"
    if [ ! -f "$_file" ]; then
        return 1
    fi

    _size="$(wc -c < "$_file" | tr -d ' ')"
    if [ -z "$_size" ] || [ "$_size" -lt 100 ]; then
        log "WARN: file too small ($_size bytes)"
        return 1
    fi

    # Reject HTML error pages (GitHub Pages 404s, captive portals, etc.).
    _snip="$(dd if="$_file" bs=256 count=1 2>/dev/null | tr '[:upper:]' '[:lower:]')"
    case "$_snip" in
        *'<!doctype'*|*'<html'*|*'<head'*|*'<title'*) 
            log "WARN: content looks like HTML, not PNG"
            return 1
            ;;
    esac

    # PNG magic: 89 50 4E 47 0D 0A 1A 0A
    # Prefer dd|od — BusyBox od on older Kindles may lack -N.
    _magic="$(dd if="$_file" bs=8 count=1 2>/dev/null | od -An -tx1 2>/dev/null | tr -d ' \n')"
    case "$_magic" in
        89504e470d0a1a0a*) return 0 ;;
    esac

    log "WARN: PNG magic header mismatch (got '$_magic')"
    return 1
}

download_dashboard() {
    load_config || return 1
    wait_for_wifi || true

    rm -f "$TMP_FILE"

    _ok=1
    if command -v wget >/dev/null 2>&1; then
        # ASSUME: BusyBox wget accepts -q -O. Verify on-device if downloads fail.
        if wget -q -O "$TMP_FILE" "$DASHBOARD_URL" 2>>"$LOG_FILE"; then
            _ok=0
        fi
    elif command -v curl >/dev/null 2>&1; then
        # ASSUME: curl is only present if you installed it yourself.
        if curl -fsSL --max-time 60 -o "$TMP_FILE" "$DASHBOARD_URL" 2>>"$LOG_FILE"; then
            _ok=0
        fi
    else
        log "ERROR: neither wget nor curl found on PATH"
        return 1
    fi

    if [ "$_ok" -ne 0 ]; then
        log "ERROR: download failed from $DASHBOARD_URL"
        rm -f "$TMP_FILE"
        return 1
    fi

    if ! validate_png "$TMP_FILE"; then
        log "ERROR: downloaded file is not a valid PNG"
        rm -f "$TMP_FILE"
        return 1
    fi

    mv -f "$TMP_FILE" "$DASHBOARD_FILE"
    log "Downloaded dashboard ($(wc -c < "$DASHBOARD_FILE" | tr -d ' ') bytes)"
    return 0
}

next_full_refresh_flag() {
    load_config || return 1
    _count=0
    if [ -f "$REFRESH_COUNT_FILE" ]; then
        _count="$(cat "$REFRESH_COUNT_FILE" 2>/dev/null || echo 0)"
    fi
    _count=$((_count + 1))
    echo "$_count" > "$REFRESH_COUNT_FILE"

    if [ "$FULL_REFRESH_EVERY" -le 1 ]; then
        echo 1
        return 0
    fi
    if [ $((_count % FULL_REFRESH_EVERY)) -eq 0 ]; then
        echo 1
    else
        echo 0
    fi
}

display_dashboard() {
    _full="${1:-0}"

    if [ ! -f "$DASHBOARD_FILE" ]; then
        log "ERROR: no cached dashboard at $DASHBOARD_FILE"
        return 1
    fi

    # VERIFIED: eips is the stock Kindle utility for painting images.
    if [ "$_full" = "1" ]; then
        if ! eips -f -g "$DASHBOARD_FILE" >/dev/null 2>>"$LOG_FILE"; then
            /usr/sbin/eips -f -g "$DASHBOARD_FILE" >/dev/null 2>>"$LOG_FILE" || {
                log "ERROR: eips -f -g failed"
                return 1
            }
        fi
    else
        if ! eips -g "$DASHBOARD_FILE" >/dev/null 2>>"$LOG_FILE"; then
            /usr/sbin/eips -g "$DASHBOARD_FILE" >/dev/null 2>>"$LOG_FILE" || {
                log "ERROR: eips -g failed"
                return 1
            }
        fi
    fi

    log "Displayed dashboard (full_refresh=$_full)"
    return 0
}

return_to_kindle_home() {
    # ASSUME / VERIFY on 5.12.2.2. Safe no-op if unsupported; Home still works
    # because Oink does not stop the Kindle framework.
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>>"$LOG_FILE" || \
        log "WARN: could not request home booklet; press Home to return"
}
