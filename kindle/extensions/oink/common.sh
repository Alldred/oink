#!/bin/sh
# Shared helpers for the Oink KUAL extension.
#
# ---------------------------------------------------------------------------
# Command status for Kindle Basic 7th gen (WP63GW), firmware 5.12.2.2
# ---------------------------------------------------------------------------
#
# VERIFIED:
#   eips -g / -f -g / -c / -i
#   lipc-set-prop com.lab126.powerd preventScreenSaver 0|1
#   lipc-get-prop com.lab126.wifid cmState
#
# REQUIRED for a persistent dashboard (observed on this device):
#   Leaving the Kindle UI running lets Home redraw over eips within seconds.
#   Oink therefore stops the framework while running and starts it again on Stop.
#   Commands tried in order: /etc/init.d/framework stop|start, then
#   stop framework / start framework (Lab126 wrappers).
#
# ASSUMED — verify on device:
#   wget on PATH
#   killall -STOP/-CONT mesquite (used only when STOP_FRAMEWORK=0)
# ---------------------------------------------------------------------------

# When sourced from start/update/stop, prefer the caller's OINK_DIR if set.
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
UI_STATE_FILE="$OINK_DIR/cache/ui_suspended"
DASHBOARD_FILE="$CACHE_DIR/dashboard.png"
TMP_FILE="$CACHE_DIR/dashboard.png.tmp"
LOG_FILE="$LOG_DIR/oink.log"
CONFIG_FILE="$OINK_DIR/config.sh"
REFRESH_COUNT_FILE="$CACHE_DIR/refresh_count"

export OINK_DIR CACHE_DIR LOG_DIR PID_FILE UI_STATE_FILE DASHBOARD_FILE TMP_FILE LOG_FILE CONFIG_FILE REFRESH_COUNT_FILE

mkdir -p "$CACHE_DIR" "$LOG_DIR"

log() {
    _ts="$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)"
    echo "$_ts $*" >> "$LOG_FILE"
    # Bound log growth on the small Kindle userstore (~512KB cap, keep half).
    _sz="$(wc -c < "$LOG_FILE" 2>/dev/null | tr -d ' ')"
    if [ -n "$_sz" ] && [ "$_sz" -gt 524288 ]; then
        tail -c 262144 "$LOG_FILE" > "$LOG_FILE.rot" 2>/dev/null && \
            mv -f "$LOG_FILE.rot" "$LOG_FILE"
    fi
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
        REFRESH_SECONDS=300
    fi

    if [ -z "$FULL_REFRESH_EVERY" ]; then
        FULL_REFRESH_EVERY=6
    fi

    # Default: stop framework so Home cannot cover the dashboard.
    if [ -z "$STOP_FRAMEWORK" ]; then
        STOP_FRAMEWORK=1
    fi

    # Between downloads, re-paint the cached PNG so any stray UI redraw is undone.
    if [ -z "$REPAINT_SECONDS" ]; then
        REPAINT_SECONDS=60
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

usb_drive_mode_active() {
    # True only for USB mass-storage / drive mode — not wall-charger power.
    # (Oink is meant to stay running on USB power for always-on use.)
    _dms="$(lipc-get-prop com.lab126.volumd driveModeState 2>/dev/null || echo 0)"
    case "$_dms" in
        ''|0) ;;
        *) return 0 ;;
    esac
    # When USBMS claims the userstore it is unmounted from the Kindle side.
    if ! grep -Eq ' /(mnt/us|mnt/base-us) ' /proc/mounts 2>/dev/null; then
        return 0
    fi
    return 1
}

should_self_stop() {
    load_config || true
    if [ -f "$OINK_DIR/STOP" ]; then
        echo "STOP file"
        return 0
    fi
    if [ "${QUIT_ON_USB:-1}" != "0" ] && usb_drive_mode_active; then
        echo "USB drive mode"
        return 0
    fi
    return 1
}

self_stop() {
    # Graceful shutdown from inside the daemon (no kill needed).
    _reason="${1:-requested}"
    log "Self-stop: $_reason"
    rm -f "$OINK_DIR/STOP" 2>/dev/null || true
    remove_pid
    resume_kindle_ui || log "WARN: resume_kindle_ui reported failure"
    eips -c 2>>"$LOG_FILE" || /usr/sbin/eips -c 2>>"$LOG_FILE" || true
    sleep 1
    return_to_kindle_home || true
    log "Oink stopped ($_reason)"
    exit 0
}

framework_stop() {
    if [ -x /etc/init.d/framework ]; then
        /etc/init.d/framework stop >>"$LOG_FILE" 2>&1 && return 0
    fi
    stop framework >>"$LOG_FILE" 2>&1 && return 0
    return 1
}

framework_start() {
    if [ -x /etc/init.d/framework ]; then
        /etc/init.d/framework start >>"$LOG_FILE" 2>&1 && return 0
    fi
    start framework >>"$LOG_FILE" 2>&1 && return 0
    return 1
}

suspend_kindle_ui() {
    # Make the eips framebuffer stick by stopping (or freezing) the UI that
    # otherwise redraws Home over the dashboard.
    load_config || true
    prevent_screensaver

    if [ "$STOP_FRAMEWORK" = "1" ]; then
        log "Stopping Kindle framework so Home cannot cover the dashboard"
        if framework_stop; then
            echo "framework" > "$UI_STATE_FILE"
            sleep 2
            log "Framework stopped"
            return 0
        fi
        log "WARN: framework stop failed; falling back to pillow/mesquite freeze"
    fi

    # Lighter fallback — may be enough on some firmware builds.
    lipc-set-prop com.lab126.pillow disableEnablePillow disable 2>>"$LOG_FILE" || true
    killall -STOP mesquite 2>>"$LOG_FILE" || true
    echo "pillow" > "$UI_STATE_FILE"
    log "Suspended pillow/mesquite"
    return 0
}

resume_kindle_ui() {
    _mode="framework"
    if [ -f "$UI_STATE_FILE" ]; then
        _mode="$(cat "$UI_STATE_FILE" 2>/dev/null || echo framework)"
    fi

    if [ "$_mode" = "pillow" ]; then
        log "Resuming pillow/mesquite"
        killall -CONT mesquite 2>>"$LOG_FILE" || true
        lipc-set-prop com.lab126.pillow disableEnablePillow enable 2>>"$LOG_FILE" || true
    else
        log "Starting Kindle framework"
        if ! framework_start; then
            log "WARN: framework start failed — a reboot may be needed"
        else
            sleep 3
            log "Framework started"
        fi
    fi

    rm -f "$UI_STATE_FILE"
    allow_screensaver
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

    _snip="$(dd if="$_file" bs=256 count=1 2>/dev/null | tr '[:upper:]' '[:lower:]')"
    case "$_snip" in
        *'<!doctype'*|*'<html'*|*'<head'*|*'<title'*)
            log "WARN: content looks like HTML, not PNG"
            return 1
            ;;
    esac

    _magic="$(dd if="$_file" bs=8 count=1 2>/dev/null | od -An -tx1 2>/dev/null | tr -d ' \n')"
    case "$_magic" in
        89504e470d0a1a0a*) ;;
        *)
            log "WARN: PNG magic header mismatch (got '$_magic')"
            return 1
            ;;
    esac

    # IHDR width/height at byte offset 16: expect 600×800 (00 00 02 58 / 00 00 03 20).
    _ihdr="$(dd if="$_file" bs=1 skip=16 count=8 2>/dev/null | od -An -tx1 2>/dev/null | tr -d ' \n')"
    case "$_ihdr" in
        0000025800000320*) return 0 ;;
    esac

    log "WARN: PNG dimensions not 600x800 (IHDR '$_ihdr')"
    return 1
}

download_dashboard() {
    # Prints one of: new | same | fail  (also returns 0 for new/same, 1 for fail)
    load_config || {
        echo fail
        return 1
    }
    wait_for_wifi || true

    rm -f "$TMP_FILE"

    _ok=1
    # Always bound network waits — a hung wget used to freeze the daemon for hours.
    if command -v wget >/dev/null 2>&1; then
        if wget -q -T 60 -t 2 -O "$TMP_FILE" "$DASHBOARD_URL" 2>>"$LOG_FILE"; then
            _ok=0
        fi
    elif command -v curl >/dev/null 2>&1; then
        if curl -fsSL --connect-timeout 20 --max-time 60 -o "$TMP_FILE" "$DASHBOARD_URL" 2>>"$LOG_FILE"; then
            _ok=0
        fi
    else
        log "ERROR: neither wget nor curl found on PATH"
        echo fail
        return 1
    fi

    if [ "$_ok" -ne 0 ]; then
        log "ERROR: download failed from $DASHBOARD_URL"
        rm -f "$TMP_FILE"
        echo fail
        return 1
    fi

    if ! validate_png "$TMP_FILE"; then
        log "ERROR: downloaded file is not a valid PNG"
        rm -f "$TMP_FILE"
        echo fail
        return 1
    fi

    if [ -f "$DASHBOARD_FILE" ] && cmp -s "$TMP_FILE" "$DASHBOARD_FILE"; then
        rm -f "$TMP_FILE"
        log "Downloaded dashboard unchanged"
        echo same
        return 0
    fi

    mv -f "$TMP_FILE" "$DASHBOARD_FILE"
    log "Downloaded dashboard ($(wc -c < "$DASHBOARD_FILE" | tr -d ' ') bytes)"
    echo new
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

    overlay_clock || true
    log "Displayed dashboard (full_refresh=$_full)"
    return 0
}

# eips text grid helpers for top-right HH:MM aligned with the PNG date header.
# Uses a conservative ~16px cell so cols stay on-screen even when the firmware
# text grid is tighter than the common 50-col assumption.
# CLOCK_COL=44 previously drew off-grid and the clock vanished.
# Header date band is y≈14–42 on the 600×800 PNG → eips row 1 matches it.
clock_default_col() {
    _xres=""
    _info="$(eips -i 2>/dev/null || /usr/sbin/eips -i 2>/dev/null || true)"
    if [ -n "$_info" ]; then
        _xres="$(echo "$_info" | grep 'xres:' | head -1 | awk '{print $2}')"
    fi
    case "$_xres" in
        ''|*[!0-9]*) _xres=600 ;;
    esac
    _cols=$((_xres / 16))
    [ "$_cols" -ge 10 ] || _cols=37
    _col=$((_cols - 5 - 1))
    [ "$_col" -ge 1 ] || _col=1
    echo "$_col"
}

overlay_clock() {
    # Local device time, top-right, same band as the centred date header.
    # Redrawn after every paint so interim re-paints do not wipe it.
    load_config || true
    if [ "${CLOCK_OVERLAY:-1}" = "0" ]; then
        return 0
    fi
    if [ -n "${CLOCK_COL:-}" ]; then
        _col="$CLOCK_COL"
    else
        _col="$(clock_default_col)"
    fi
    _row="${CLOCK_ROW:-1}"
    _now="$(date '+%H:%M' 2>/dev/null || date '+%H:%M')"
    [ -n "$_now" ] || return 1
    eips "$_col" "$_row" "$_now" 2>/dev/null || \
        /usr/sbin/eips "$_col" "$_row" "$_now" 2>/dev/null || {
            log "WARN: clock overlay failed (col=$_col row=$_row)"
            return 1
        }
    return 0
}

return_to_kindle_home() {
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>>"$LOG_FILE" || \
        log "WARN: could not request home booklet; press Home after framework restarts"
}

show_status() {
    # Plain eips text — fine for short errors; prefer show_splash for branding.
    eips 1 1 "$1" 2>/dev/null || /usr/sbin/eips 1 1 "$1" 2>/dev/null || true
}

show_splash() {
    # Full-screen PNG via eips (same path as the dashboard). Not limited to text.
    _splash="${1:-$OINK_DIR/splash.png}"
    if [ -f "$_splash" ]; then
        eips -f -g "$_splash" >/dev/null 2>>"$LOG_FILE" || \
            /usr/sbin/eips -f -g "$_splash" >/dev/null 2>>"$LOG_FILE" || \
            show_status "Oink starting..."
    else
        show_status "Oink starting..."
    fi
}
