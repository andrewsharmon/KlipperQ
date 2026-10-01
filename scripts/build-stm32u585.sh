#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
firmware_root=${KLIPPER_SRC:-"$project_root/../klipper"}
lima_vm=${LIMA_VM:-arducnc}
limactl=${LIMACTL:-"$project_root/../qstep/tools/bin/limactl"}
cross_prefix=${CROSS_PREFIX:-/home/$(id -un).guest/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-}

if [ ! -x "$limactl" ]; then
    echo "limactl is not executable: $limactl" >&2
    exit 2
fi
if [ ! -f "$firmware_root/test/configs/stm32u585.config" ]; then
    echo "STM32U585 config is missing from: $firmware_root" >&2
    exit 2
fi

guest_script=$(cat <<'EOF'
set -eu
cd "$1"
cp test/configs/stm32u585.config .config
make clean
make olddefconfig
make \
    CROSS_PREFIX="$2" \
    STM32_LIBC=c
scripts/check-software-div.sh .config out/klipper.elf
scripts/check_whitespace.sh
git diff --check
EOF
)

echo "Building STM32U585 firmware in Lima VM '$lima_vm'..."
"$limactl" shell "$lima_vm" -- sh -c "$guest_script" sh "$firmware_root" "$cross_prefix"
python3 "$project_root/scripts/verify-stm32u585.py" --firmware "$firmware_root"
