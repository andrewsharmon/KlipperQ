#!/bin/sh
set -eu

openocd=/opt/openocd/bin/openocd
scripts=/opt/openocd
config=openocd_gpiod.cfg

if [ ! -x "$openocd" ]; then
    echo "OpenOCD is not executable: $openocd" >&2
    exit 1
fi

# A hardware reset on this UNO Q enters STM32 system ROM. Read the stack and
# reset vectors from the currently flashed application so the helper remains
# valid when the Klipper image changes, then start that application explicitly.
exec "$openocd" -d2 -s "$scripts" -f "$config" -c '
    reset_config srst_only srst_push_pull;
    init;
    reset halt;
    set vectors [read_memory 0x08000000 32 2];
    set initial_sp [lindex $vectors 0];
    set reset_pc [expr {[lindex $vectors 1] & 0xfffffffe}];
    if {$initial_sp < 0x20000000 || $initial_sp >= 0x20100000} {
        error "invalid application stack vector";
    }
    if {$reset_pc < 0x08000000 || $reset_pc >= 0x08200000} {
        error "invalid application reset vector";
    }
    reg msp $initial_sp;
    reg xpsr 0x01000000;
    reg pc $reset_pc;
    resume;
    sleep 500;
    shutdown;
'
