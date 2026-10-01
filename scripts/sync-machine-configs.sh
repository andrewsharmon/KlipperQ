#!/bin/sh
set -eu

# macOS's Perl-backed shasum rejects C.UTF-8 on systems where that locale is
# not installed. These snapshots contain path names and hashes only, so the
# portable C locale also gives deterministic sorting.
LC_ALL=C
LANG=C
export LC_ALL LANG

default_adb=/private/tmp/klipperq-adb/platform-tools/adb
remote_dir=/home/arduino/printer_data/config
serial=${UNO_Q_SERIAL:-}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(dirname -- "$script_dir")
snapshot_parent=$repo_root/machine-config
snapshot_dir=$snapshot_parent/uno-q
checksum_file=$snapshot_parent/uno-q.SHA256SUMS

usage() {
    cat <<EOF
Usage: $(basename "$0") [--serial SERIAL]

Copy the connected UNO Q's complete Klipper/Moonraker machine configuration
directory into:

  $snapshot_dir

The tracked directory is replaced with a current snapshot and a SHA-256
manifest is written to $checksum_file.

  --serial SERIAL  Select a device explicitly instead of auto-discovery
  -h, --help       Show this help

Environment overrides: ADB, UNO_Q_SERIAL
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --serial)
            [ "$#" -ge 2 ] || { echo "--serial requires a value" >&2; exit 2; }
            serial=$2
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
if ! command -v shasum >/dev/null 2>&1; then
    echo "shasum is required to create the snapshot manifest." >&2
    exit 2
fi

if [ -z "$serial" ]; then
    matches=
    for candidate in $("$adb_bin" devices | awk 'NR > 1 && $2 == "device" {print $1}'); do
        if "$adb_bin" -s "$candidate" shell '
            tr "\000" "\n" </proc/device-tree/compatible 2>/dev/null |
                grep -qx "arduino,imola" &&
            test -d /home/arduino/printer_data/config
        ' >/dev/null 2>&1; then
            matches="${matches}${matches:+ }${candidate}"
        fi
    done
    # ADB serials do not contain shell whitespace.
    set -- $matches
    if [ "$#" -eq 0 ]; then
        echo "No connected Arduino UNO Q with a machine config directory was found." >&2
        "$adb_bin" devices -l >&2 || true
        exit 1
    fi
    if [ "$#" -ne 1 ]; then
        echo "Multiple matching UNO Q boards were found; select one with --serial." >&2
        exit 1
    fi
    serial=$1
fi

if [ "$("$adb_bin" -s "$serial" get-state 2>/dev/null || true)" != device ]; then
    echo "The selected UNO Q is not available: $serial" >&2
    "$adb_bin" devices -l >&2 || true
    exit 1
fi
if ! "$adb_bin" -s "$serial" shell "test -d '$remote_dir'"; then
    echo "Machine config directory is missing on $serial: $remote_dir" >&2
    exit 1
fi

mkdir -p "$snapshot_parent"
stage=$(mktemp -d "$snapshot_parent/.uno-q-config.XXXXXX")
previous=$snapshot_parent/.uno-q-previous.$$

cleanup() {
    [ ! -d "$stage" ] || rm -rf -- "$stage"
}
trap cleanup EXIT HUP INT TERM

mkdir "$stage/config"
echo "Copying $serial:$remote_dir ..."
"$adb_bin" -s "$serial" pull "$remote_dir/." "$stage/config"

if ! find "$stage/config" -type f -print -quit | grep -q .; then
    echo "The copied machine config directory contains no files; keeping the prior snapshot." >&2
    exit 1
fi

(
    cd "$stage/config"
    find . -type f -exec shasum -a 256 '{}' \; | sort
) >"$stage/SHA256SUMS"

copied_file_count=$(find "$stage/config" -type f | wc -l | tr -d ' ')
checksum_count=$(wc -l <"$stage/SHA256SUMS" | tr -d ' ')
if [ "$checksum_count" -ne "$copied_file_count" ]; then
    echo "Checksummed $checksum_count of $copied_file_count files; keeping the prior snapshot." >&2
    exit 1
fi

if [ -e "$snapshot_dir" ]; then
    mv "$snapshot_dir" "$previous"
fi
if ! mv "$stage/config" "$snapshot_dir"; then
    [ ! -e "$previous" ] || mv "$previous" "$snapshot_dir"
    echo "Could not install the new snapshot; restored the prior snapshot." >&2
    exit 1
fi
mv "$stage/SHA256SUMS" "$checksum_file"
[ ! -e "$previous" ] || rm -rf -- "$previous"

echo "Saved $copied_file_count files in $snapshot_dir"
echo "Review changes with: git -C $repo_root status --short -- machine-config"
