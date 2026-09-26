#!/bin/sh
set -eu

default_adb=/private/tmp/klipperq-adb/platform-tools/adb
serial=${UNO_Q_SERIAL:-}
local_port=${MAINSAIL_PORT:-8181}
action=start

usage() {
    cat <<EOF
Usage: $(basename "$0") [--restart] [--serial SERIAL] [--port PORT]

Bring the UNO Q Klipper stack online through USB/ADB and verify the complete
Mainsail -> nginx -> Moonraker -> Klippy path.

  --restart        Restart Klipper, Moonraker, and nginx before connecting
  --serial SERIAL  Select a device explicitly instead of auto-discovery
  --port PORT      Mac loopback port (default: $local_port)
  -h, --help       Show this help

Environment overrides: ADB, UNO_Q_SERIAL, MAINSAIL_PORT
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --restart)
            action=restart
            shift
            ;;
        --serial)
            [ "$#" -ge 2 ] || { echo "--serial requires a value" >&2; exit 2; }
            serial=$2
            shift 2
            ;;
        --port)
            [ "$#" -ge 2 ] || { echo "--port requires a value" >&2; exit 2; }
            local_port=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$local_port" in
    ''|*[!0-9]*)
        echo "Port must be a number: $local_port" >&2
        exit 2
        ;;
esac
if [ "$local_port" -lt 1 ] || [ "$local_port" -gt 65535 ]; then
    echo "Port must be between 1 and 65535: $local_port" >&2
    exit 2
fi

if [ -n "${ADB:-}" ]; then
    adb_bin=$ADB
elif command -v adb >/dev/null 2>&1; then
    adb_bin=$(command -v adb)
else
    adb_bin=$default_adb
fi

if [ ! -x "$adb_bin" ]; then
    echo "ADB is not executable: $adb_bin" >&2
    echo "Install Android platform-tools or set ADB=/absolute/path/to/adb." >&2
    exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required for the end-to-end checks." >&2
    exit 2
fi

if [ -z "$serial" ]; then
    matches=
    for candidate in $("$adb_bin" devices | awk 'NR > 1 && $2 == "device" {print $1}'); do
        if "$adb_bin" -s "$candidate" shell '
            tr "\000" "\n" </proc/device-tree/compatible 2>/dev/null |
                grep -qx "arduino,imola" &&
            test -c /dev/ttyHS1 &&
            test -d /home/arduino/klipper &&
            test -d /home/arduino/moonraker &&
            test -d /home/arduino/mainsail
        ' >/dev/null 2>&1; then
            matches="${matches}${matches:+ }${candidate}"
        fi
    done
    # ADB serials do not contain shell whitespace.
    set -- $matches
    if [ "$#" -eq 0 ]; then
        echo "No connected Arduino UNO Q running the Klipper stack was found." >&2
        "$adb_bin" devices -l >&2 || true
        exit 1
    fi
    if [ "$#" -ne 1 ]; then
        echo "Multiple matching UNO Q boards were found; select one with --serial." >&2
        exit 1
    fi
    serial=$1
fi

echo "Waiting for the identified UNO Q over USB/ADB..."
device_state=
attempt=0
while [ "$attempt" -lt 20 ]; do
    device_state=$("$adb_bin" -s "$serial" get-state 2>/dev/null || true)
    [ "$device_state" = device ] && break
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$device_state" != device ]; then
    echo "The selected UNO Q did not become available." >&2
    "$adb_bin" devices -l >&2 || true
    exit 1
fi

if [ "$action" = restart ]; then
    echo "Restarting the UNO Q Klipper stack..."
    "$adb_bin" -s "$serial" shell \
        'systemctl restart klipper.service && systemctl restart moonraker.service && systemctl restart nginx.service'
else
    echo "Starting any inactive UNO Q Klipper services..."
    "$adb_bin" -s "$serial" shell \
        'systemctl start klipper.service moonraker.service nginx.service'
fi

service_states=$("$adb_bin" -s "$serial" shell \
    'systemctl is-active klipper.service moonraker.service nginx.service' | tr -d '\r')
active_count=$(printf '%s\n' "$service_states" | grep -c '^active$' || true)
if [ "$active_count" -ne 3 ]; then
    echo "One or more board services are not active:" >&2
    printf '%s\n' "$service_states" >&2
    exit 1
fi

if ! forward_error=$("$adb_bin" -s "$serial" forward "tcp:$local_port" tcp:80 2>&1); then
    echo "Could not forward Mac port $local_port to the UNO Q: $forward_error" >&2
    echo "Choose another port with --port PORT or MAINSAIL_PORT=PORT." >&2
    exit 1
fi

base_url=http://127.0.0.1:$local_port
echo "Waiting for Moonraker and Klippy through $base_url..."
server_info=
root_code=000
attempt=0
while [ "$attempt" -lt 30 ]; do
    root_code=$(curl --silent --output /dev/null --write-out '%{http_code}' \
        --connect-timeout 1 --max-time 2 "$base_url/" || true)
    server_info=$(curl --silent --connect-timeout 1 --max-time 2 \
        "$base_url/server/info" || true)
    if [ "$root_code" = 200 ] && \
        printf '%s' "$server_info" | grep -q '"klippy_connected":true' && \
        printf '%s' "$server_info" | grep -q '"klippy_state":"ready"'; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ "$root_code" != 200 ] || \
    ! printf '%s' "$server_info" | grep -q '"klippy_connected":true' || \
    ! printf '%s' "$server_info" | grep -q '"klippy_state":"ready"'; then
    echo "The USB forward is present, but the full stack did not become ready." >&2
    printf '%s\n' "$server_info" >&2
    echo "Retry with --restart. If it still fails, inspect:" >&2
    echo "  $adb_bin -s $serial shell systemctl status klipper moonraker nginx" >&2
    exit 1
fi

websocket_code=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --http1.1 --connect-timeout 1 --max-time 2 \
    --header 'Connection: Upgrade' \
    --header 'Upgrade: websocket' \
    --header 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    --header 'Sec-WebSocket-Version: 13' \
    "$base_url/websocket" || true)
if [ "$websocket_code" != 101 ]; then
    echo "Moonraker HTTP is ready, but the Mainsail WebSocket check returned HTTP $websocket_code." >&2
    exit 1
fi

echo "Ready: Klipper, Moonraker, nginx, HTTP API, and WebSocket are healthy."
echo "Mainsail: $base_url/"
